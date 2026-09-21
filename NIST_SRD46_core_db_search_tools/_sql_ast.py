"""SQL AST-based normalization for SRD46 search-tool inputs.

Background
----------
The legacy normalization pipeline used regex substitutions over raw SQL text,
which had several systemic failures:

* `\\bSELECT\\b` keyword check rejected legitimate sub-SELECTs
  (``EXISTS (SELECT …)``, ``IN (SELECT …)``).
* Same regex matched ``SELECT`` inside string literals, e.g.
  ``WHERE note = 'we will SELECT later'`` was wrongly rejected.
* Prefix-ID rewriter (``metal_41`` → ``41``) corrupted substrings inside
  string literals: ``LIKE '%metal_41 complex%'`` had ``metal_41`` silently
  rewritten to ``41``.
* Column-rewrite tables (``s.value`` → ``s.constant_value`` etc.) used
  ``\\b…\\b`` boundaries that also fired inside string literals.

This module replaces those regexes with sqlglot-based AST traversal that
respects token boundaries and string-literal vs. identifier context, and
allows read-only sub-SELECTs.

All public functions are *string-in / string-out* so call-sites do not need
to know about the AST.
"""

from __future__ import annotations

import logging
import re
from typing import Callable, Optional

import sqlglot
from sqlglot import exp

log = logging.getLogger("SRD46")


_DIALECT = "sqlite"

# Identifier prefixes that the public agent emits as decorated row IDs
# (e.g. ``metal_41``, ``ligand_812``, ``beta_def_77``). When such an
# identifier appears in a SQL clause as a Column reference (NOT a string
# literal), it is the user's shorthand for the bare integer.
_PREFIXED_ID_RE = re.compile(
    r"^(metal|ligand|vlm|beta_def|pka|ref_eq_map|ref_eq_net|lit|eq_node)_(\d+)$"
)

# Top-level node types that mean "this is a write operation". Sub-Selects are
# explicitly allowed; only DDL/DML at any depth is rejected.
_WRITE_NODE_TYPES: tuple[type, ...] = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Alter,
    exp.Create,
    exp.TruncateTable,
    exp.AlterColumn,
)
# sqlglot exposes some of these only in newer versions; be tolerant.
for _name in ("Replace", "Pragma", "AttachStatement", "Attach", "Detach"):
    _node = getattr(exp, _name, None)
    if isinstance(_node, type):
        _WRITE_NODE_TYPES = _WRITE_NODE_TYPES + (_node,)

# PRAGMAs that are pure schema/config inspection and have no side effects.
# When the root SQL is one of these (with no assignment form), the read-only
# validator allows it through even though Pragma is in _WRITE_NODE_TYPES.
# Refs: https://www.sqlite.org/pragma.html
_SAFE_READONLY_PRAGMAS: frozenset[str] = frozenset({
    "table_info",
    "table_xinfo",
    "index_list",
    "index_info",
    "index_xinfo",
    "foreign_key_list",
    "database_list",
    "collation_list",
    "compile_options",
    "function_list",
    "module_list",
    "pragma_list",
    "integrity_check",
    "quick_check",
    "schema_version",
    "user_version",
    "page_count",
    "page_size",
    "encoding",
    "freelist_count",
})

_PRAGMA_HEAD_RE = re.compile(
    r"^\s*PRAGMA\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(\(|;|$)",
    re.IGNORECASE,
)


# ── parse / render helpers ───────────────────────────────────────────


def _parse_where_fragment(fragment: str) -> tuple[exp.Expression, exp.Expression]:
    """Parse a WHERE-clause fragment by wrapping it in a stub SELECT.

    Returns ``(root_select_tree, where_predicate_node)``.
    """
    wrapped = f"SELECT 1 FROM _stub WHERE {fragment}"
    tree = sqlglot.parse_one(wrapped, dialect=_DIALECT)
    where = tree.find(exp.Where)
    if where is None:
        raise ValueError("Failed to parse WHERE fragment.")
    return tree, where.this


def _parse_orderby_fragment(fragment: str) -> tuple[exp.Expression, exp.Expression]:
    wrapped = f"SELECT 1 FROM _stub ORDER BY {fragment}"
    tree = sqlglot.parse_one(wrapped, dialect=_DIALECT)
    order = tree.find(exp.Order)
    if order is None:
        raise ValueError("Failed to parse ORDER BY fragment.")
    return tree, order


def _render_where(tree: exp.Expression) -> str:
    rendered = tree.sql(dialect=_DIALECT)
    # Slice off everything up to and including the first " WHERE "
    m = re.search(r"\sWHERE\s", rendered, re.IGNORECASE)
    return rendered[m.end():] if m else rendered


def _render_orderby(tree: exp.Expression) -> str:
    rendered = tree.sql(dialect=_DIALECT)
    m = re.search(r"\sORDER\s+BY\s", rendered, re.IGNORECASE)
    return rendered[m.end():] if m else rendered


def _build_column(name: str, table: Optional[str]) -> exp.Column:
    return exp.column(name, table=table) if table else exp.column(name)


def _split_qualified(text: str) -> tuple[Optional[str], str]:
    """Split ``"a.b"`` → ``("a", "b")``; ``"x"`` → ``(None, "x")``."""
    if "." in text:
        a, b = text.split(".", 1)
        return a, b
    return None, text


# ── AST-level transformations ────────────────────────────────────────


def _ast_validate_read_only(tree: exp.Expression) -> None:
    """Reject any DDL/DML node anywhere in the tree.

    Read-only sub-SELECTs (``EXISTS (SELECT …)``, ``IN (SELECT …)``,
    scalar subqueries) are explicitly allowed.
    """
    bad = tree.find(*_WRITE_NODE_TYPES)
    if bad is not None:
        kind = type(bad).__name__.upper()
        raise ValueError(f"Write/DDL operations blocked: {kind}")


def _ast_resolve_prefixed_ids(tree: exp.Expression) -> exp.Expression:
    """Rewrite ``Column(name='metal_41')`` → ``Literal.number(41)``.

    String literals are NOT touched because they are ``exp.Literal`` nodes,
    not ``exp.Column`` nodes — the AST cleanly separates the two.
    """
    def visit(node: exp.Expression) -> exp.Expression:
        if isinstance(node, exp.Column) and not node.table:
            m = _PREFIXED_ID_RE.match(node.name)
            if m:
                return exp.Literal.number(m.group(2))
        return node
    return tree.transform(visit, copy=False)


def _ast_apply_rewrites(tree: exp.Expression, rewrites: dict[str, str]) -> exp.Expression:
    """Apply column / table rewrites against AST identifier nodes only.

    Each ``key → value`` entry may be:
      * ``"a.b" → "c.d"`` — qualified column rename (matches Column nodes
        with the exact ``table.column`` pair).
      * ``"b" → "c.d"`` — column-name rename that re-qualifies; matches
        any Column with name ``b`` regardless of existing table prefix.
      * ``"b" → "c"`` — bare-name rename. Matches BOTH Column nodes named
        ``b`` (any qualifier) AND Table nodes named ``b``.

    String literals are never touched.
    """
    if not rewrites:
        return tree

    parsed: list[tuple[Optional[str], str, Optional[str], str]] = []
    for k, v in rewrites.items():
        kt, kc = _split_qualified(k)
        vt, vc = _split_qualified(v)
        parsed.append((kt, kc, vt, vc))

    def visit(node: exp.Expression) -> exp.Expression:
        if isinstance(node, exp.Column):
            ntbl = node.table or None
            nname = node.name
            for kt, kc, vt, vc in parsed:
                if kt is not None:
                    if ntbl == kt and nname == kc:
                        return _build_column(vc, vt)
                else:
                    if nname == kc:
                        # Bare-name match: re-qualify if value is qualified;
                        # otherwise preserve original qualifier.
                        return _build_column(vc, vt if vt is not None else ntbl)
            return node
        if isinstance(node, exp.Table):
            for kt, kc, vt, vc in parsed:
                if kt is None and vt is None and node.name == kc:
                    new = exp.to_table(vc, dialect=_DIALECT)
                    # preserve alias if any
                    if node.alias:
                        new.set("alias", node.args.get("alias"))
                    return new
            return node
        return node

    return tree.transform(visit, copy=False)


_DJANGO_SUFFIX = "__like"


def _ast_fix_django_filters(tree: exp.Expression) -> exp.Expression:
    """Rewrite ``col__like = 'val'`` → ``col LIKE 'val'``.

    Walks ``EQ`` nodes whose LHS Column name ends with ``__like``. String
    literals containing ``__like`` are unaffected because they are
    ``Literal`` nodes, not ``Column`` nodes.
    """
    def visit(node: exp.Expression) -> exp.Expression:
        if isinstance(node, exp.EQ):
            left = node.this
            right = node.expression
            if isinstance(left, exp.Column) and left.name.endswith(_DJANGO_SUFFIX):
                stripped = left.name[: -len(_DJANGO_SUFFIX)]
                new_left = _build_column(stripped, left.table or None)
                return exp.Like(this=new_left, expression=right)
        return node
    return tree.transform(visit, copy=False)


def _ast_expand_ligand_id_with_similar(
    tree: exp.Expression, all_ids: list[int],
) -> tuple[exp.Expression, bool]:
    """Replace ``ligand_id = N`` (any qualifier) with ``ligand_id IN (…)``.

    Also handles the single-element form ``ligand_id IN (N)`` so callers
    that emit IN-lists with one entry get the same widening behaviour.

    Returns ``(new_tree, replaced)``.
    """
    if not all_ids:
        return tree, False
    replaced = False

    def visit(node: exp.Expression) -> exp.Expression:
        nonlocal replaced
        if isinstance(node, exp.EQ):
            left = node.this
            right = node.expression
            if isinstance(left, exp.Column) and left.name == "ligand_id":
                if isinstance(right, exp.Literal) and right.is_int:
                    replaced = True
                    return exp.In(
                        this=left,
                        expressions=[exp.Literal.number(i) for i in all_ids],
                    )
        # Single-element IN is morally an EQ — widen it the same way.
        if isinstance(node, exp.In):
            left = node.this
            if isinstance(left, exp.Column) and left.name == "ligand_id":
                items = node.args.get("expressions") or []
                if (
                    len(items) == 1
                    and isinstance(items[0], exp.Literal)
                    and items[0].is_int
                ):
                    replaced = True
                    return exp.In(
                        this=left,
                        expressions=[exp.Literal.number(i) for i in all_ids],
                    )
        return node

    new = tree.transform(visit, copy=False)
    return new, replaced


def _ast_extract_ligand_info(tree: exp.Expression) -> dict:
    """Pull the first ``ligand_id = N`` and / or ``ligand_name [LIKE|=] '…'``
    constraint out of a parsed predicate.

    Caveats: this walker is **branch-blind** — it picks the first match
    anywhere in the tree (including inside sub-SELECTs and AND/OR
    branches). Callers using it for the 0-row similarity fallback should
    be aware that a ligand seed extracted from a branch whose 0-row
    cause was actually a *different* predicate (e.g. a tight numeric
    filter) may produce misleading "similar ligand" rows. We accept that
    trade-off because the alternative — null-result reasoning — would
    require running the query multiple times.
    """
    info: dict = {}
    for node in tree.walk():
        if isinstance(node, exp.EQ):
            left, right = node.this, node.expression
            if (
                isinstance(left, exp.Column)
                and left.name == "ligand_id"
                and isinstance(right, exp.Literal)
                and right.is_int
                and "ligand_id" not in info
            ):
                info["ligand_id"] = int(right.this)
            # NEW: ligand_name = 'glycine' (exact match) also seeds similarity.
            elif (
                isinstance(left, exp.Column)
                and left.name in ("ligand_name", "ligand_name_SRD")
                and isinstance(right, exp.Literal)
                and right.is_string
                and "ligand_name" not in info
            ):
                value = (right.this or "").strip()
                if value:
                    info["ligand_name"] = value
        if isinstance(node, exp.Like):
            left, right = node.this, node.expression
            if (
                isinstance(left, exp.Column)
                and left.name in ("ligand_name", "ligand_name_SRD")
                and isinstance(right, exp.Literal)
                and right.is_string
                and "ligand_name" not in info
            ):
                # strip leading/trailing % from the literal value
                value = right.this
                value = value.strip("%")
                if value:
                    info["ligand_name"] = value
    return info


# ── chemistry-literal normalization ──────────────────────────────────
#
# Rewrites string literals on the right-hand side of EQ / NEQ / LIKE / IN
# predicates whose left-hand side targets a known chemistry column.
# Composite WHERE clauses (AND/OR/NOT, parens, subqueries) are handled
# automatically because each predicate node is visited independently
# during tree.transform().

# Column names whose string literals should be folded through the
# metal-charge canonicalizer ("Cu2+" -> "Cu^[2+]").
_METAL_NAME_COLUMNS: frozenset[str] = frozenset({
    "metal_name",
    "metal_name_SRD",
    "symbol",
    "metal_symbol",
})

# Column names whose string literals should be RDKit-canonicalized as SMILES.
_SMILES_COLUMNS: frozenset[str] = frozenset({
    "smiles",
    "SMILES",
    "metal_smiles",
    "ligand_smiles",
    "canonical_smiles",
})

# Column names whose string literals should be RDKit-canonicalized as InChI.
_INCHI_COLUMNS: frozenset[str] = frozenset({
    "inchi",
    "InChI",
    "metal_inchi",
    "ligand_inchi",
})

# Column names whose string literals should be normalized to SRD-46's
# stored constant-type codes.
_CONSTANT_TYPE_COLUMNS: frozenset[str] = frozenset({
    "constant_type",
})

_CONSTANT_TYPE_LITERAL_MAP: dict[str, str] = {
    "k": "K",
    "logk": "K",
    "logkappa": "K",
    "h": "H",
    "deltah": "H",
    "enthalpy": "H",
    "reactionenthalpy": "H",
    "s": "S",
    "deltas": "S",
    "entropy": "S",
    "reactionentropy": "S",
    "β": "β",
    "beta": "β",
    "logβ": "β",
    "logbeta": "β",
    "cumulative": "β",
    "cumulativebeta": "β",
    "overallbeta": "β",
}


def _norm_metal_literal(value: str) -> str:
    """Canonicalize a metal-name literal (``Cu2+`` -> ``Cu^[2+]``).

    Wildcard characters (``%``, ``_``) in LIKE patterns are preserved.
    """
    if not value:
        return value
    # Lazy import — avoids a circular dependency at module load time.
    from ._normalization_helpers.chem_query import normalize_chem_query
    return normalize_chem_query(value)


def _norm_smiles_literal(value: str) -> str:
    """RDKit-canonicalize a SMILES literal; return input unchanged on failure."""
    if not value or "%" in value or "_" in value:
        # Leave LIKE patterns alone — RDKit can't parse partial SMILES.
        return value
    try:
        from ._normalization_helpers.ligand_resolution import _canonical_smiles
    except Exception:
        return value
    out = _canonical_smiles(value)
    return out or value


def _norm_inchi_literal(value: str) -> str:
    """RDKit-canonicalize an InChI literal; return input unchanged on failure."""
    if not value or "%" in value:
        return value
    try:
        from ._normalization_helpers.ligand_resolution import _canonicalize_inchi
    except Exception:
        return value
    out = _canonicalize_inchi(value)
    return out or value


def _norm_constant_type_literal(value: str) -> str:
    """Normalize human-friendly constant-type names to SRD-46 storage codes.

    Examples:
      ``log K`` / ``logK`` -> ``K``
      ``ΔH`` / ``delta H`` -> ``H``
      ``ΔS`` / ``delta S`` -> ``S``
      ``beta`` / ``logβ`` -> ``β``
    """
    if not value:
        return value
    key = (
        value.strip()
        .lower()
        .replace("_", "")
        .replace("-", "")
        .replace(" ", "")
        .replace("Δ", "")
        .replace("δ", "")
    )
    return _CONSTANT_TYPE_LITERAL_MAP.get(key, value)


def _column_normalizer(col_name: str) -> Optional[Callable[[str], str]]:
    """Return the literal-normalizer for a chemistry column, or ``None``."""
    if col_name in _METAL_NAME_COLUMNS:
        return _norm_metal_literal
    if col_name in _SMILES_COLUMNS:
        return _norm_smiles_literal
    if col_name in _INCHI_COLUMNS:
        return _norm_inchi_literal
    if col_name in _CONSTANT_TYPE_COLUMNS:
        return _norm_constant_type_literal
    return None


def _rewrite_string_literal(node: exp.Literal, fn: Callable[[str], str]) -> exp.Literal:
    """Apply ``fn`` to a string-literal node, preserving the literal flag."""
    new_val = fn(node.this)
    if new_val == node.this:
        return node
    return exp.Literal.string(new_val)


def _ast_normalize_chem_literals(tree: exp.Expression) -> exp.Expression:
    """Walk EQ / NEQ / Like / In predicates and canonicalize chemistry literals.

    Visits each comparison node independently, so AND/OR/NOT, parens,
    sub-SELECTs, and arbitrary nesting all work without special-casing.
    Non-chemistry predicates and string literals on non-chemistry columns
    are left alone.
    """
    def _normalize_lhs(left: exp.Expression) -> Optional[Callable[[str], str]]:
        if not isinstance(left, exp.Column):
            return None
        return _column_normalizer(left.name)

    def visit(node: exp.Expression) -> exp.Expression:
        # EQ  /  NEQ
        if isinstance(node, (exp.EQ, exp.NEQ)):
            fn = _normalize_lhs(node.this)
            rhs = node.expression
            if fn and isinstance(rhs, exp.Literal) and rhs.is_string:
                node.set("expression", _rewrite_string_literal(rhs, fn))
            return node

        # LIKE  /  ILIKE  /  NOT LIKE  (sqlglot wraps NOT LIKE as exp.Not over Like)
        if isinstance(node, (exp.Like, getattr(exp, "ILike", exp.Like))):
            fn = _normalize_lhs(node.this)
            rhs = node.expression
            if fn and isinstance(rhs, exp.Literal) and rhs.is_string:
                node.set("expression", _rewrite_string_literal(rhs, fn))
            return node

        # IN  /  NOT IN
        if isinstance(node, exp.In):
            fn = _normalize_lhs(node.this)
            if fn:
                items = node.args.get("expressions") or []
                changed = False
                new_items = []
                for it in items:
                    if isinstance(it, exp.Literal) and it.is_string:
                        new_it = _rewrite_string_literal(it, fn)
                        if new_it is not it:
                            changed = True
                        new_items.append(new_it)
                    else:
                        new_items.append(it)
                if changed:
                    node.set("expressions", new_items)
            return node

        return node

    return tree.transform(visit, copy=False)


# ── metal-name English-alias expansion ───────────────────────────────
#
# `_ast_normalize_chem_literals` only canonicalizes a literal *in place*
# (e.g. ``Cu2+`` → ``Cu^[2+]``). It does NOT bridge English/oxidation-state
# aliases ("copper(II)", "cupric") to the DB form, because those expansions
# may produce multiple equivalent strings. This walker handles that case
# by rewriting the predicate to an IN-list using ``_expand_metal_name``.
#
# Behaviour:
#   * EQ on metal-name col + string literal → IN (terms…) if expansion
#     produced >1 distinct term.
#   * NEQ → NOT IN (terms…) so exclusions cover the canonical form too.
#   * IN  → IN with each element expanded and unioned (deduped).
#   * NOT IN → same expansion (sqlglot models it as exp.Not(exp.In(…))).
#   * LIKE / NOT LIKE WITH wildcards (``%`` / ``_``) → left alone (the
#     agent chose substring match, and the chem-literal pass already
#     folded charge notation inside the wildcards).
#   * LIKE / NOT LIKE WITHOUT wildcards → treated as EQ and expanded.
#     Many agents emit ``LIKE 'cupric'`` when they really wanted ``=``;
#     without this rewrite the predicate would silently match nothing.
#   * LHS may be the bare column OR ``LOWER(col)`` / ``UPPER(col)`` —
#     the case wrapper is preserved and expansion terms are
#     case-transformed to match.
#
# This addresses the GPT-5.4 failure mode where the agent writes
# ``WHERE metal_name_SRD = 'copper(II)'``, gets 0 rows because the DB
# stores ``'Cu^[2+]'``, and gives up after one attempt.


def _expand_metal_terms(value: str) -> list[str]:
    """Return deduped expansion terms for a metal-name literal.

    Always includes the original (already canonicalized) value, plus any
    additional search variants returned by ``_expand_metal_name``.
    """
    if not value:
        return [value]
    # Lazy import — avoids circular dependency at module load time.
    from ._normalization_helpers.metal_resolution import _expand_metal_name
    try:
        terms = _expand_metal_name(value)
    except Exception:
        return [value]
    # Preserve original first; dedupe while keeping order stable.
    out: list[str] = []
    seen: set[str] = set()
    for t in [value] + list(terms or []):
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _make_in_list(
    lhs: exp.Expression, terms: list[str], *, negated: bool = False,
) -> exp.Expression:
    """Build ``lhs IN ('t1', 't2', …)`` (or ``NOT IN`` if ``negated``).

    ``lhs`` may be a bare ``exp.Column`` or any wrapping expression
    (e.g. ``LOWER(col)``); it is copied verbatim into the IN node.
    """
    in_node = exp.In(
        this=lhs.copy(),
        expressions=[exp.Literal.string(t) for t in terms],
    )
    return exp.Not(this=in_node) if negated else in_node


def _metal_lhs_info(node: exp.Expression):
    """Inspect a comparison LHS for a metal-name column reference.

    Recognizes both bare ``metal_name_SRD`` and the common case-folding
    wrappers ``LOWER(metal_name_SRD)`` / ``UPPER(metal_name_SRD)`` that
    agents emit when they want case-insensitive matching.

    Returns ``(lhs_node_to_keep, transform_fn)`` if the LHS is a metal-name
    reference, else ``(None, None)``. ``transform_fn`` is the case
    transform to apply to expansion terms so they match the wrapped LHS:
    identity for bare columns, ``str.lower`` / ``str.upper`` for the
    wrapped forms. ``lhs_node_to_keep`` is the ORIGINAL LHS expression
    (kept intact in any rewrite) so semantics are preserved.
    """
    if isinstance(node, exp.Column) and node.name in _METAL_NAME_COLUMNS:
        return node, (lambda s: s)
    if isinstance(node, exp.Lower):
        inner = node.this
        if isinstance(inner, exp.Column) and inner.name in _METAL_NAME_COLUMNS:
            return node, str.lower
    if isinstance(node, exp.Upper):
        inner = node.this
        if isinstance(inner, exp.Column) and inner.name in _METAL_NAME_COLUMNS:
            return node, str.upper
    return None, None


def _expand_metal_terms_with_case(value: str, case_fn) -> list[str]:
    """Expand a metal literal then apply a case transform, deduping."""
    raw = _expand_metal_terms(value)
    out: list[str] = []
    seen: set[str] = set()
    for t in raw:
        ct = case_fn(t)
        if ct and ct not in seen:
            seen.add(ct)
            out.append(ct)
    return out


def _ast_expand_metal_name_literals(tree: exp.Expression) -> exp.Expression:
    """Expand metal-name English aliases inside EQ / NEQ / LIKE / IN predicates.

    Handles bare metal-name columns AND ``LOWER(col)`` / ``UPPER(col)``
    case-folding wrappers (the wrapper is preserved on the LHS; expansion
    terms are case-transformed to match).

    For ``LIKE 'literal'`` with no ``%``/``_`` wildcards, the predicate
    is rewritten to an IN-list (the agent clearly meant exact match).
    LIKE patterns that DO contain wildcards are left alone (substring
    match was intended).

    Composite WHEREs work for free because each comparison node is
    visited independently by ``tree.transform``.
    """

    def visit(node: exp.Expression) -> exp.Expression:
        # EQ → IN  (only when expansion adds new terms)
        if isinstance(node, exp.EQ):
            lhs, case_fn = _metal_lhs_info(node.this)
            rhs = node.expression
            if lhs is not None and isinstance(rhs, exp.Literal) and rhs.is_string:
                if "%" not in rhs.this and "_" not in rhs.this:
                    terms = _expand_metal_terms_with_case(rhs.this, case_fn)
                    if len(terms) > 1:
                        return _make_in_list(lhs, terms, negated=False)
            return node

        # NEQ → NOT IN
        if isinstance(node, exp.NEQ):
            lhs, case_fn = _metal_lhs_info(node.this)
            rhs = node.expression
            if lhs is not None and isinstance(rhs, exp.Literal) and rhs.is_string:
                if "%" not in rhs.this and "_" not in rhs.this:
                    terms = _expand_metal_terms_with_case(rhs.this, case_fn)
                    if len(terms) > 1:
                        return _make_in_list(lhs, terms, negated=True)
            return node

        # LIKE / ILIKE without wildcards → treat as EQ → expand to IN
        # (LIKE patterns with % or _ are left alone — the agent picked
        # substring match deliberately.)
        if isinstance(node, (exp.Like, getattr(exp, "ILike", exp.Like))):
            lhs, case_fn = _metal_lhs_info(node.this)
            rhs = node.expression
            if lhs is not None and isinstance(rhs, exp.Literal) and rhs.is_string:
                if "%" not in rhs.this and "_" not in rhs.this:
                    terms = _expand_metal_terms_with_case(rhs.this, case_fn)
                    if len(terms) > 1:
                        return _make_in_list(lhs, terms, negated=False)
            return node

        # IN  /  NOT IN  (sqlglot wraps NOT IN as exp.Not over exp.In)
        if isinstance(node, exp.In):
            lhs, case_fn = _metal_lhs_info(node.this)
            if lhs is not None:
                items = node.args.get("expressions") or []
                expanded: list[str] = []
                seen: set[str] = set()
                changed = False
                for it in items:
                    if isinstance(it, exp.Literal) and it.is_string:
                        if "%" in it.this or "_" in it.this:
                            ct = case_fn(it.this)
                            if ct not in seen:
                                seen.add(ct)
                                expanded.append(ct)
                            continue
                        terms = _expand_metal_terms_with_case(it.this, case_fn)
                        if len(terms) > 1:
                            changed = True
                        for t in terms:
                            if t not in seen:
                                seen.add(t)
                                expanded.append(t)
                    else:
                        # Non-literal element — bail out, leave node alone.
                        return node
                if changed:
                    node.set(
                        "expressions",
                        [exp.Literal.string(t) for t in expanded],
                    )
            return node

        return node

    return tree.transform(visit, copy=False)


# ── public string-in / string-out API ────────────────────────────────


def validate_read_only(sql_or_clause: str, *, kind: str = "sql") -> None:
    """Reject DDL/DML in either a full SQL statement or a clause fragment.

    ``kind`` is one of ``"sql"`` (full statement), ``"where"``, or
    ``"order_by"``.
    """
    if not sql_or_clause or not sql_or_clause.strip():
        return
    # Short-circuit: allow whitelisted read-only PRAGMAs without parsing.
    # The form must be ``PRAGMA <name>`` or ``PRAGMA <name>(args)`` only —
    # the assignment form ``PRAGMA <name> = <value>`` is rejected because
    # it can mutate connection state.
    if kind == "sql":
        m = _PRAGMA_HEAD_RE.match(sql_or_clause)
        if m:
            pname = m.group(1).lower()
            tail = sql_or_clause[m.end():]
            if "=" in tail:
                raise ValueError(
                    f"Write/DDL operations blocked: PRAGMA assignment "
                    f"({pname} = ...) is not allowed"
                )
            if pname not in _SAFE_READONLY_PRAGMAS:
                raise ValueError(
                    f"Write/DDL operations blocked: PRAGMA {pname} is not in "
                    f"the read-only allow-list. Allowed: "
                    f"{sorted(_SAFE_READONLY_PRAGMAS)}"
                )
            return  # safe read-only PRAGMA — accept
    try:
        if kind == "sql":
            tree = sqlglot.parse_one(sql_or_clause, dialect=_DIALECT)
        elif kind == "where":
            tree, _ = _parse_where_fragment(sql_or_clause)
        elif kind == "order_by":
            tree, _ = _parse_orderby_fragment(sql_or_clause)
        else:
            raise ValueError(f"Unknown kind={kind!r}")
    except sqlglot.errors.SqlglotError as e:
        raise ValueError(f"SQL parse error: {e}") from e
    _ast_validate_read_only(tree)


def resolve_prefixed_ids(clause: str, *, kind: str = "where") -> str:
    """AST-aware version of the legacy :func:`resolve_prefixed_ids` regex.

    Rewrites bare prefix-ID identifiers (``metal_41`` → ``41``) only when
    they appear as Column references, never inside string literals.
    Falls back to returning the input unchanged if parsing fails (so
    callers always get *something* back).
    """
    if not clause or not clause.strip():
        return clause
    try:
        if kind == "sql":
            tree = sqlglot.parse_one(clause, dialect=_DIALECT)
            new_tree = _ast_resolve_prefixed_ids(tree)
            return new_tree.sql(dialect=_DIALECT)
        if kind == "order_by":
            tree, _ = _parse_orderby_fragment(clause)
            _ast_resolve_prefixed_ids(tree)
            return _render_orderby(tree)
        # default: where
        tree, _ = _parse_where_fragment(clause)
        _ast_resolve_prefixed_ids(tree)
        return _render_where(tree)
    except sqlglot.errors.SqlglotError as e:
        log.warning("resolve_prefixed_ids: parse failed (%s); returning unchanged", e)
        return clause


def apply_rewrites(clause: str, rewrites: dict[str, str], *, kind: str = "where") -> str:
    """Apply a ``{wrong: correct}`` rewrite table to a clause via AST."""
    if not clause or not clause.strip() or not rewrites:
        return clause
    try:
        if kind == "sql":
            tree = sqlglot.parse_one(clause, dialect=_DIALECT)
            new_tree = _ast_apply_rewrites(tree, rewrites)
            return new_tree.sql(dialect=_DIALECT)
        if kind == "order_by":
            tree, _ = _parse_orderby_fragment(clause)
            _ast_apply_rewrites(tree, rewrites)
            return _render_orderby(tree)
        tree, _ = _parse_where_fragment(clause)
        _ast_apply_rewrites(tree, rewrites)
        return _render_where(tree)
    except sqlglot.errors.SqlglotError as e:
        log.warning("apply_rewrites: parse failed (%s); returning unchanged", e)
        return clause


def fix_django_filters(clause: str, *, kind: str = "where") -> str:
    """AST-aware version of the legacy ``_fix_django_filters`` regex."""
    if not clause or "__like" not in clause.lower():
        return clause
    try:
        if kind == "sql":
            tree = sqlglot.parse_one(clause, dialect=_DIALECT)
            new_tree = _ast_fix_django_filters(tree)
            return new_tree.sql(dialect=_DIALECT)
        if kind == "order_by":
            return clause  # nonsensical for ORDER BY
        tree, _ = _parse_where_fragment(clause)
        _ast_fix_django_filters(tree)
        return _render_where(tree)
    except sqlglot.errors.SqlglotError as e:
        log.warning("fix_django_filters: parse failed (%s); returning unchanged", e)
        return clause


def expand_ligand_id_with_similar(
    where: str, all_ids: list[int],
) -> tuple[str, bool]:
    """Rewrite ``ligand_id = N`` → ``ligand_id IN (…)`` via AST.

    Returns ``(new_where, was_replaced)``.
    """
    if not where or not all_ids:
        return where, False
    try:
        tree, _ = _parse_where_fragment(where)
        _, replaced = _ast_expand_ligand_id_with_similar(tree, all_ids)
        return (_render_where(tree), replaced) if replaced else (where, False)
    except sqlglot.errors.SqlglotError as e:
        log.warning("expand_ligand_id_with_similar: parse failed (%s)", e)
        return where, False


def extract_ligand_from_where(where: str) -> dict:
    """AST-aware version of :func:`extract_ligand_from_where`.

    Prefixed IDs (``ligand_5760``) are resolved to raw integers before
    extraction so callers can pass agent-friendly clauses like
    ``c.ligand_id = ligand_5760`` directly.
    """
    if not where or not where.strip():
        return {}
    try:
        tree, _ = _parse_where_fragment(where)
    except sqlglot.errors.SqlglotError:
        return {}
    _ast_resolve_prefixed_ids(tree)
    return _ast_extract_ligand_info(tree)


def normalize_clause(
    clause: str,
    *,
    rewrites: Optional[dict[str, str]] = None,
    kind: str = "where",
) -> str:
    """Run the full normalization pipeline on a clause in canonical order.

    Order of operations (each step is AST-based, so string literals are
    always preserved):

      1. ``apply_rewrites`` — column/table aliasing.
      2. ``fix_django_filters`` — ``col__like=`` → ``col LIKE``.
      3. ``normalize_chem_literals`` — fold ``Cu2+``/SMILES/InChI literals
         to canonical form (only on chemistry columns).
      4. ``expand_metal_name_literals`` — expand English / oxidation-state
         metal-name aliases to IN-lists (``copper(II)`` → ``IN ('copper(II)',
         'copper', 'Cu2+', 'Cu^[2+]')``); NEQ becomes NOT IN.
      5. ``resolve_prefixed_ids`` — ``metal_41`` → ``41``.
      6. ``validate_read_only`` — reject DDL/DML; allow nested SELECTs.

    Each step is best-effort: if parsing fails at any stage, the input
    string is returned unchanged at that step (and validation is skipped).
    """
    if not clause or not clause.strip():
        return clause

    if rewrites:
        clause = apply_rewrites(clause, rewrites, kind=kind)
    if "__like" in clause.lower():
        clause = fix_django_filters(clause, kind=kind)
    clause = normalize_chem_literals(clause, kind=kind)
    clause = expand_metal_name_literals(clause, kind=kind)
    clause = resolve_prefixed_ids(clause, kind=kind)
    validate_read_only(clause, kind=kind)
    return clause


def normalize_chem_literals(clause: str, *, kind: str = "where") -> str:
    """Canonicalize chemistry-related string literals in a clause.

    Walks the AST and rewrites the right-hand side of comparisons whose
    left-hand side targets a known chemistry column:

      * metal-name columns (``metal_name_SRD``, ``symbol``, …): fold
        ``Cu2+`` / ``Cu²⁺`` / ``Cu+2`` / ``Cu^2+`` to ``Cu^[2+]`` via
        :func:`normalize_chem_query`.
      * SMILES columns (``smiles``, ``ligand_smiles``, …): RDKit
        canonical SMILES.
      * InChI columns (``inchi``, ``ligand_inchi``, …): RDKit
        canonical InChI.

    Composite predicates (``AND``/``OR``/``NOT``, parens, sub-SELECTs,
    ``IN (...)``, ``NOT IN (...)``, ``LIKE``/``NOT LIKE``) all work
    automatically — each comparison node is visited independently. LIKE
    patterns containing ``%`` or ``_`` are folded by the metal helper
    (which only rewrites the symbol+charge substring) but left alone by
    the SMILES/InChI helpers (RDKit can't parse partial structures).

    Returns the original clause unchanged if parsing fails.
    """
    if not clause or not clause.strip():
        return clause
    try:
        if kind == "sql":
            tree = sqlglot.parse_one(clause, dialect=_DIALECT)
            _ast_normalize_chem_literals(tree)
            return tree.sql(dialect=_DIALECT)
        if kind == "order_by":
            # ORDER BY rarely contains literals, but support it for completeness.
            tree, _ = _parse_orderby_fragment(clause)
            _ast_normalize_chem_literals(tree)
            return _render_orderby(tree)
        # default: where
        tree, _ = _parse_where_fragment(clause)
        _ast_normalize_chem_literals(tree)
        return _render_where(tree)
    except sqlglot.errors.SqlglotError as e:
        log.warning("normalize_chem_literals: parse failed (%s); returning unchanged", e)
        return clause


def expand_metal_name_literals(clause: str, *, kind: str = "where") -> str:
    """Expand English / oxidation-state / alias metal names inside predicates.

    Rewrites ``metal_name_SRD = 'copper(II)'`` to
    ``metal_name_SRD IN ('copper(II)', 'copper', 'Cu2+', 'Cu^[2+]')`` so
    the canonical DB form is matched. Mirrors the behaviour of
    ``search_metals(name=…)`` for free-form WHERE clauses.

    NEQ becomes ``NOT IN``; IN-lists have each element expanded and
    deduped; LIKE / NOT LIKE are left alone (substring match already
    covers most aliases once :func:`normalize_chem_literals` has folded
    the charge notation inside the wildcards).

    Composite predicates (``AND``/``OR``/``NOT``, parens, sub-SELECTs)
    work automatically — each comparison is visited independently.
    Returns the input unchanged if parsing fails.
    """
    if not clause or not clause.strip():
        return clause
    try:
        if kind == "sql":
            tree = sqlglot.parse_one(clause, dialect=_DIALECT)
            _ast_expand_metal_name_literals(tree)
            return tree.sql(dialect=_DIALECT)
        if kind == "order_by":
            return clause  # nonsensical for ORDER BY
        tree, _ = _parse_where_fragment(clause)
        _ast_expand_metal_name_literals(tree)
        return _render_where(tree)
    except sqlglot.errors.SqlglotError as e:
        log.warning(
            "expand_metal_name_literals: parse failed (%s); returning unchanged", e
        )
        return clause


# ── full sql_where_query splitter ────────────────────────────────────


_LEADING_WHERE_RE = re.compile(r"^\s*WHERE\s+", re.IGNORECASE)
_TAIL_KEYWORDS = {"ORDER", "LIMIT", "GROUP", "HAVING"}


def parse_sql_where_query(query: str) -> tuple[str, str, str]:
    """Split an agent-supplied ``sql_where_query`` into ``(where, order_by, limit)``.

    The agent passes a single string that may contain a WHERE predicate,
    an optional ``ORDER BY`` clause, and an optional ``LIMIT``. The
    leading ``WHERE`` keyword is optional. Examples:

      * ``"c.metal_id = 41"``
      * ``"WHERE c.metal_id = 41"``
      * ``"c.metal_id = 41 ORDER BY s.constant_value DESC LIMIT 20"``
      * ``"ORDER BY s.constant_value DESC LIMIT 5"``  → where defaults to ``1=1``
      * ``""`` / ``None``                              → ``("1=1", "", "")``

    Returns three strings, each WITHOUT its leading keyword
    (``order_by`` is the bare expression list, ``limit`` is the bare
    integer expression). Raises ``ValueError`` on parse failure.
    """
    s = (query or "").strip()
    if not s:
        return "1=1", "", ""

    # Strip optional leading WHERE
    s = _LEADING_WHERE_RE.sub("", s, count=1).strip()
    if not s:
        return "1=1", "", ""

    # Allow a query that begins with ORDER/LIMIT/GROUP/HAVING (i.e. no
    # predicate at all) by padding the WHERE with 1=1.
    head = s.split(None, 1)[0].upper()
    inner = f"1=1 {s}" if head in _TAIL_KEYWORDS else s

    wrapped = f"SELECT 1 FROM _stub WHERE {inner}"
    try:
        tree = sqlglot.parse_one(wrapped, dialect=_DIALECT)
    except sqlglot.errors.SqlglotError as e:
        raise ValueError(f"Failed to parse sql_where_query: {e}") from e

    where_node = tree.find(exp.Where)
    where_sql = (
        where_node.this.sql(dialect=_DIALECT)
        if where_node and where_node.this is not None
        else "1=1"
    )

    order_node = tree.args.get("order")
    if order_node is not None:
        order_exprs = order_node.args.get("expressions") or []
        order_sql = ", ".join(e.sql(dialect=_DIALECT) for e in order_exprs)
    else:
        order_sql = ""

    limit_node = tree.args.get("limit")
    if limit_node is not None and limit_node.expression is not None:
        limit_sql = limit_node.expression.sql(dialect=_DIALECT)
    else:
        limit_sql = ""

    return where_sql, order_sql, limit_sql
