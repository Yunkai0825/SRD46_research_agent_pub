"""LC3_2 constraint-card normalizer  (constr_normalizer.py)
=========================================================

The L3_2 constraint *designer* is an LLM.  It reliably emits the right
*structure* (``axes`` / ``lets`` / ``binds``) but routinely hallucinates
surface *details* that the strict card compiler then rejects:

  * sub-namespace spellings   ``s.concentration`` -> ``s.conc``,
                              ``s.totals``        -> ``s.total``,
                              ``s.ln_conc``       -> ``s.lnconc``
  * intensive handles         ``s.T`` -> ``s.temperature``,
                              ``s.Eh`` / ``s.potential`` -> ``s.E_V``,
                              ``s.ph`` -> ``s.pH``
  * function names / numpy    ``np.log`` -> ``log``,
                              ``natural_log`` -> ``log``,
                              ``power`` -> ``pow``
  * oxidation-state tokens    ``Fe2+`` / ``Fe^2+`` / ``Fe(2+)`` -> ``Fe$+2``
  * comparison operators      ``"="`` -> ``"=="``, ``"le"`` -> ``"<="``
  * axis attribute access     ``a.pH_axis`` -> ``a["pH_axis"]``

This module rewrites those tokens **only when the canonical form is
unambiguous** -- from a fixed alias table for vocabulary, and, for ids,
only when the rewritten token is an actual catalog id *and* the original
is not.  It therefore can never silently change the meaning of a valid
card.  It NEVER executes the card, only re-parses it with ``ast`` and
edits source spans in place, so **line numbers are preserved** and the
compiler's located error feedback keeps pointing at the agent's original
lines.

Design contract
---------------
* A card that is already canonical is returned byte-for-byte unchanged
  (every existing/regression card is a no-op).
* A token is only rewritten when the destination is provably valid
  (a known intensive / sub-namespace / function, or an id present in the
  supplied component/species pool).  Anything else is left untouched for
  the compiler to reject with its own did-you-mean hint.
* Declared ``let`` names shadow the intensive/sub-namespace alias tables,
  so a user ``let`` named ``T`` is never clobbered into ``temperature``.

Public API
----------
``normalize_card_source(source, *, components, species, intensives=None)``
    -> :class:`NormalizeResult` ``(source, notes)`` where ``notes`` is a
    list of :class:`NormNote` describing each applied rewrite.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

# Canonical vocabularies -- mirror ``constr_code_card_compiler``.  Imported
# when available so the two modules cannot drift; falls back to a local
# copy when the compiler is imported under a different path layout.
try:                                                       # flat import
    from constr_code_card_compiler import (                # type: ignore
        _INTENSIVES as _C_INTENSIVES,
        _STATE_SUBNS as _C_STATE_SUBNS,
        _FUNC_WHITELIST as _C_FUNC_WHITELIST,
    )
except Exception:                                          # pragma: no cover
    try:                                                   # package-relative
        from ...NIST_SRD46_calc_input_building_agentic_pipeline.LC3_solver_para_card_building.LC3_3_constraint_designer._constraint_helpers.constr_code_card_compiler import (  # type: ignore
            _INTENSIVES as _C_INTENSIVES,
            _STATE_SUBNS as _C_STATE_SUBNS,
            _FUNC_WHITELIST as _C_FUNC_WHITELIST,
        )
    except Exception:                                      # last-resort local
        _C_INTENSIVES = ("temperature", "ionic_strength", "pH", "E_V")
        _C_STATE_SUBNS = ("conc", "lnconc", "total", "species")
        _C_FUNC_WHITELIST = {
            "log": "log", "ln": "log", "log10": "log10", "exp": "exp",
            "sqrt": "sqrt", "abs": "abs", "pow": "pow",
            "sinh": "sinh", "cosh": "cosh", "tanh": "tanh",
        }

_DEFAULT_INTENSIVES: Tuple[str, ...] = tuple(_C_INTENSIVES)
_STATE_SUBNS: Tuple[str, ...] = tuple(_C_STATE_SUBNS)
_FUNC_CANON: Set[str] = set(_C_FUNC_WHITELIST)


# ════════════════════════════════════════════════════════════════════
#  Alias tables  (lower-cased lookup keys -> canonical name)
# ════════════════════════════════════════════════════════════════════

# Intensive handles addressable as ``s.<name>``.  Short scientific
# shorthands (T / I / E) are intentionally included -- on the ``s``
# namespace they are unambiguous.
_INTENSIVE_ALIASES: Dict[str, str] = {
    # temperature
    "temp": "temperature", "temperature_k": "temperature",
    "tempk": "temperature", "temp_k": "temperature", "t": "temperature",
    "t_k": "temperature", "tk": "temperature", "temperaturek": "temperature",
    # ionic strength
    "i": "ionic_strength", "ionic": "ionic_strength",
    "ionicstrength": "ionic_strength", "ionic_str": "ionic_strength",
    "istr": "ionic_strength", "mu": "ionic_strength",
    "ionicstr": "ionic_strength", "is": "ionic_strength",
    # pH
    "ph": "pH",
    # redox potential
    "e": "E_V", "eh": "E_V", "e_h": "E_V", "ev": "E_V", "e_v": "E_V",
    "potential": "E_V", "redox_potential": "E_V", "e_redox": "E_V",
    "eredox": "E_V", "e_volt": "E_V", "e_volts": "E_V", "evolts": "E_V",
}

# State sub-namespaces addressable as ``s.<ns>[<id>]``.
_SUBNS_ALIASES: Dict[str, str] = {
    # concentration
    "concentration": "conc", "concentrations": "conc", "concs": "conc",
    "c": "conc", "conc_": "conc",
    # log concentration
    "ln_conc": "lnconc", "log_conc": "lnconc", "logconc": "lnconc",
    "lnc": "lnconc", "ln_concentration": "lnconc",
    "log_concentration": "lnconc", "lnconcentration": "lnconc",
    "lnconcs": "lnconc",
    # totals
    "totals": "total", "tot": "total", "total_conc": "total",
    "totalconc": "total", "tots": "total",
    # dependent species
    "spec": "species", "specie": "species", "sp": "species",
    "specy": "species", "specieses": "species",
}

# Function names -> canonical whitelisted function.  ``ln`` is already
# accepted by the compiler so it is deliberately left untouched.
_FUNC_ALIASES: Dict[str, str] = {
    "natural_log": "log", "loge": "log", "log_e": "log", "ln_": "log",
    "log_10": "log10", "logten": "log10", "log_ten": "log10",
    "exponential": "exp", "exponent": "exp",
    "square_root": "sqrt", "squareroot": "sqrt", "root": "sqrt",
    "absolute": "abs", "absval": "abs", "fabs": "abs",
    "power": "pow",
}

# Module prefixes the compiler does NOT accept -- strip them, keep the
# bare (canonicalised) function.  ``math`` / ``Math`` are accepted by the
# compiler and so are left in place.
_MODULE_STRIP: Set[str] = {"np", "numpy", "scipy", "sp", "nm"}
_MODULE_KEEP: Set[str] = {"math", "Math"}

# Comparison operator strings.
_OP_ALIASES: Dict[str, str] = {
    "=": "==", "eq": "==", "equals": "==", "equal": "==",
    "<": "<=", "le": "<=", "leq": "<=", "lte": "<=", "=<": "<=",
    ">": ">=", "ge": ">=", "geq": ">=", "gte": ">=", "=>": ">=",
}
_OP_CANON: Set[str] = {"==", "<=", ">="}


# ════════════════════════════════════════════════════════════════════
#  Result types
# ════════════════════════════════════════════════════════════════════

@dataclass
class NormNote:
    """One applied rewrite, suitable for surfacing back to the agent."""
    line: Optional[int]
    kind: str            # "subns" | "intensive" | "func" | "id" | "op" | "axis"
    original: str
    replacement: str

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        loc = f"line {self.line}: " if self.line else ""
        return f"{loc}{self.kind}: {self.original!r} -> {self.replacement!r}"


@dataclass
class NormalizeResult:
    source: str
    notes: List[NormNote] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.notes)


@dataclass
class _Edit:
    start: int
    end: int
    new: str
    note: NormNote


# ════════════════════════════════════════════════════════════════════
#  Public entry point
# ════════════════════════════════════════════════════════════════════

def normalize_card_source(
    source: str,
    *,
    components: Sequence[str],
    species: Sequence[str],
    intensives: Optional[Sequence[str]] = None,
) -> NormalizeResult:
    """Canonicalise an agent-emitted constraint card before compilation.

    Returns the (possibly identical) normalized source plus a list of
    :class:`NormNote` describing each rewrite.  On any parse failure the
    original source is returned unchanged (the compiler reports the real
    syntax error against the agent's own text).
    """
    intens: Tuple[str, ...] = (tuple(intensives) if intensives
                               else _DEFAULT_INTENSIVES)
    comp_pool: Set[str] = set(components)
    spec_pool: Set[str] = set(species)

    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError:
        return NormalizeResult(source, [])

    starts = _line_starts(source)
    let_names = _collect_let_names(tree)
    axis_names = _collect_axis_names(tree)

    edits: List[_Edit] = []

    for node in ast.walk(tree):
        # ── s.<attr>  : intensive / sub-namespace canonicalisation ──
        if isinstance(node, ast.Attribute) and _is_name(node.value, "s"):
            _attr_edit(node, intens, let_names, starts, edits)

        # ── <axis_param>.<axis>  ->  <axis_param>["<axis>"] ──
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            _axis_attr_edit(node, axis_names, starts, edits)

        # ── function call name : np./numpy. strip + alias ──
        if isinstance(node, ast.Call):
            _func_edit(node.func, starts, edits)

        # ── s.<ns>[<id>] : oxidation-state token canonicalisation ──
        if isinstance(node, ast.Subscript):
            _subscript_id_edit(node, comp_pool, spec_pool, starts, edits)

        # ── bind {"op": "..."} : comparison-operator canonicalisation ──
        if isinstance(node, ast.Dict):
            _op_edit(node, starts, edits)

    new_source = _apply_edits(source, edits)
    notes = [e.note for e in _kept_edits(edits)]
    notes.sort(key=lambda n: (n.line or 0))
    return NormalizeResult(new_source, notes)


# ════════════════════════════════════════════════════════════════════
#  Per-node edit builders
# ════════════════════════════════════════════════════════════════════

def _attr_edit(node: ast.Attribute, intens: Tuple[str, ...],
               let_names: Set[str], starts: List[int],
               edits: List[_Edit]) -> None:
    attr = node.attr
    if attr in let_names:                       # a declared let shadows aliases
        return
    canon = _canon_attr(attr, intens)
    if canon is None or canon == attr:
        return
    end = _abs(starts, node.end_lineno, node.end_col_offset)
    start = end - len(attr)
    kind = "intensive" if canon in intens else "subns"
    edits.append(_Edit(start, end, canon,
                       NormNote(node.lineno, kind, f"s.{attr}", f"s.{canon}")))


def _axis_attr_edit(node: ast.Attribute, axis_names: Set[str],
                    starts: List[int], edits: List[_Edit]) -> None:
    base = node.value
    assert isinstance(base, ast.Name)
    if base.id == "s" or base.id in _MODULE_STRIP or base.id in _MODULE_KEEP:
        return
    if node.attr not in axis_names:             # only rewrite declared axes
        return
    span = _node_span(node, starts)
    if span is None:
        return
    new = f'{base.id}[{node.attr!r}]'
    edits.append(_Edit(span[0], span[1], new,
                       NormNote(node.lineno, "axis",
                                f"{base.id}.{node.attr}", new)))


def _func_edit(func: ast.AST, starts: List[int], edits: List[_Edit]) -> None:
    new: Optional[str] = None
    original: str = ""
    if isinstance(func, ast.Name):
        original = func.id
        if func.id in _FUNC_CANON:
            return
        new = _FUNC_ALIASES.get(func.id.lower())
    elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        base, attr = func.value.id, func.attr
        original = f"{base}.{attr}"
        if base in _MODULE_KEEP:
            return
        if base in _MODULE_STRIP:
            cand = attr if attr in _FUNC_CANON else _FUNC_ALIASES.get(attr.lower())
            if cand is not None:
                new = cand
    if new is None:
        return
    span = _node_span(func, starts)
    if span is None:
        return
    edits.append(_Edit(span[0], span[1], new,
                       NormNote(getattr(func, "lineno", None), "func",
                                original, new)))


def _subscript_id_edit(node: ast.Subscript, comp_pool: Set[str],
                       spec_pool: Set[str], starts: List[int],
                       edits: List[_Edit]) -> None:
    base = node.value
    if not (isinstance(base, ast.Attribute) and _is_name(base.value, "s")):
        return
    ns = _subns_of(base.attr)
    if ns is None:
        return
    key_node = node.slice
    if not (isinstance(key_node, ast.Constant) and isinstance(key_node.value, str)):
        return
    raw = key_node.value
    pool = _pool_for(ns, comp_pool, spec_pool)
    canon = _canonical_id(raw, pool)
    if canon is None or canon == raw:
        return
    span = _node_span(key_node, starts)
    if span is None:
        return
    edits.append(_Edit(span[0], span[1], repr(canon),
                       NormNote(node.lineno, "id",
                                f"s.{ns}[{raw!r}]", f"s.{ns}[{canon!r}]")))


def _op_edit(node: ast.Dict, starts: List[int], edits: List[_Edit]) -> None:
    for k, v in zip(node.keys, node.values):
        if not (isinstance(k, ast.Constant) and k.value == "op"):
            continue
        if not (isinstance(v, ast.Constant) and isinstance(v.value, str)):
            continue
        raw = v.value
        if raw in _OP_CANON:
            continue
        canon = _OP_ALIASES.get(raw.strip().lower())
        if canon is None:
            continue
        span = _node_span(v, starts)
        if span is None:
            continue
        edits.append(_Edit(span[0], span[1], repr(canon),
                           NormNote(node.lineno, "op", raw, canon)))


# ════════════════════════════════════════════════════════════════════
#  Vocabulary canonicalisation helpers
# ════════════════════════════════════════════════════════════════════

def _canon_attr(attr: str, intens: Tuple[str, ...]) -> Optional[str]:
    """Map an ``s.<attr>`` handle to its canonical intensive / sub-namespace.

    Returns ``None`` when ``attr`` is already canonical or is not a known
    alias.  Alias targets are only accepted when they are active.
    """
    if attr in intens or attr in _STATE_SUBNS:
        return None                              # already canonical
    low = attr.lower()
    # case-only fix against canonical names
    for canon in tuple(intens) + _STATE_SUBNS:
        if low == canon.lower():
            return canon
    tgt = _INTENSIVE_ALIASES.get(low)
    if tgt is not None and tgt in intens:
        return tgt
    tgt = _SUBNS_ALIASES.get(low)
    if tgt is not None and tgt in _STATE_SUBNS:
        return tgt
    return None


def _subns_of(attr: str) -> Optional[str]:
    """Canonical state sub-namespace for ``s.<attr>[...]`` (or ``None``)."""
    if attr in _STATE_SUBNS:
        return attr
    low = attr.lower()
    for canon in _STATE_SUBNS:
        if low == canon.lower():
            return canon
    tgt = _SUBNS_ALIASES.get(low)
    return tgt if tgt in _STATE_SUBNS else None


def _pool_for(ns: str, comp_pool: Set[str], spec_pool: Set[str]) -> Set[str]:
    if ns == "total":
        return comp_pool
    if ns == "species":
        return spec_pool
    return comp_pool | spec_pool                 # conc / lnconc accept either


_DECORATION = str.maketrans({c: "" for c in "^{}()[] "})


def _canonical_id(raw: str, pool: Set[str]) -> Optional[str]:
    """Canonicalise an oxidation-state token against the id ``pool``.

    Maps common charge notations (``Fe2+`` / ``Fe^2+`` / ``Fe(2+)`` /
    ``Fe++`` / ``Fe+2``) onto the ``base$signmag`` form, but **only**
    returns a rewrite when the candidate is actually in ``pool`` and the
    original is not.  Neutral / ligand ids (no trailing charge) and any
    already-valid id are left untouched.
    """
    if raw in pool:
        return None
    t = raw.translate(_DECORATION)
    cands: List[str] = []

    # trailing run of identical signs: Fe++ / Fe--- / Fe+
    m = re.match(r"^(.*?)(\++|-+)$", t)
    if m and m.group(1):
        base, signs = m.group(1), m.group(2)
        sign = "+" if signs[0] == "+" else "-"
        cands.append(f"{base}${sign}{len(signs)}")

    # base + sign + magnitude:  Fe+2 / Fe$+2 / Cu-1
    m = re.match(r"^(.*?)\$?([+-])(\d+)$", t)
    if m and m.group(1):
        base, sign, mag = m.group(1), m.group(2), int(m.group(3))
        cands.append(f"{base}${sign}{mag}")

    # base + magnitude + sign:  Fe2+ / Cu1-
    m = re.match(r"^(.*?)(\d+)([+-])$", t)
    if m and m.group(1):
        base, mag, sign = m.group(1), int(m.group(2)), m.group(3)
        cands.append(f"{base}${sign}{mag}")

    for cand in cands:
        if cand in pool:
            return cand
    return None


# ════════════════════════════════════════════════════════════════════
#  AST / source-span utilities
# ════════════════════════════════════════════════════════════════════

def _is_name(node: ast.AST, ident: str) -> bool:
    return isinstance(node, ast.Name) and node.id == ident


def _line_starts(src: str) -> List[int]:
    starts = [0]
    for i, ch in enumerate(src):
        if ch == "\n":
            starts.append(i + 1)
    return starts


def _abs(starts: List[int], lineno: Optional[int], col: Optional[int]) -> int:
    return starts[(lineno or 1) - 1] + (col or 0)


def _node_span(node: ast.AST, starts: List[int]) -> Optional[Tuple[int, int]]:
    if getattr(node, "end_lineno", None) is None:
        return None
    s = _abs(starts, node.lineno, node.col_offset)
    e = _abs(starts, node.end_lineno, node.end_col_offset)
    return s, e


def _collect_let_names(tree: ast.AST) -> Set[str]:
    names: Set[str] = set()
    for stmt in getattr(tree, "body", []):
        if (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                and _is_name(stmt.targets[0], "lets")
                and isinstance(stmt.value, ast.Dict)):
            for k in stmt.value.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    names.add(k.value)
    return names


def _collect_axis_names(tree: ast.AST) -> Set[str]:
    names: Set[str] = set()
    for stmt in getattr(tree, "body", []):
        if (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                and _is_name(stmt.targets[0], "axes")
                and isinstance(stmt.value, ast.List)):
            for el in stmt.value.elts:
                if isinstance(el, ast.Constant) and isinstance(el.value, str):
                    names.add(el.value)
    return names


def _kept_edits(edits: List[_Edit]) -> List[_Edit]:
    """Drop overlapping edits (keep the earliest-starting span)."""
    ordered = sorted(edits, key=lambda e: (e.start, e.end))
    kept: List[_Edit] = []
    last_end = -1
    for e in ordered:
        if e.start < last_end:
            continue
        kept.append(e)
        last_end = e.end
    return kept


def _apply_edits(source: str, edits: List[_Edit]) -> str:
    kept = _kept_edits(edits)
    out = source
    for e in sorted(kept, key=lambda e: e.start, reverse=True):
        out = out[:e.start] + e.new + out[e.end:]
    return out


# ════════════════════════════════════════════════════════════════════
#  Self-test harness  (stand-in for live-agent prompts)
# ════════════════════════════════════════════════════════════════════

def _selftest() -> int:                          # pragma: no cover
    """Run representative *hallucinated* cards through the normalizer.

    These mirror the kinds of cards the LLM actually emits (correct
    structure, wrong surface detail).  Run with::

        python constr_normalizer.py
    """
    components = ["Cu", "Cu$+2", "Cu$+1", "Fe", "Fe$+3", "Fe$+2",
                  "ligand_5760", "ligand_5937", "Ca", "H"]
    species = ["Fe$+3", "Fe$+2", "Cu$+2", "Cu$+1", "H.L1", "CuL$+1"]

    cases: List[Tuple[str, str]] = [
        ("intensive shorthand", '''
axes = ["pH_axis"]
lets = {}
binds = [
  {"id": "pH", "op": "=", "lhs": lambda s: s.ph, "rhs": lambda a: a.pH_axis},
  {"id": "T",  "op": "==", "lhs": lambda s: s.T,  "rhs": 298.15},
  {"id": "I",  "op": "==", "lhs": lambda s: s.I,  "rhs": 0.1},
  {"id": "E",  "op": "==", "lhs": lambda s: s.Eh, "rhs": 0.0},
]
'''),
        ("oxidation tokens + numpy", '''
axes = ["E_V_axis"]
lets = {"poise": lambda s: s.lnconc["Fe3+"] - s.lnconc["Fe2+"]}
binds = [
  {"id": "fe", "op": "==", "lhs": lambda s: s.poise, "rhs": lambda a: a["E_V_axis"]},
  {"id": "cu", "op": "==", "lhs": lambda s: s.lnconc["Cu^2+"] - s.lnconc["Cu(+1)"], "rhs": 4.605},
  {"id": "ferr", "op": "==", "lhs": lambda s: np.log(s.conc["Fe$+3"]), "rhs": -6.0},
]
'''),
        ("subnamespace + totals spellings", '''
axes = ["pH_axis"]
lets = {}
binds = [
  {"id": "pH", "op": "==", "lhs": lambda s: s.pH, "rhs": lambda a: a["pH_axis"]},
  {"id": "cu", "op": "==", "lhs": lambda s: s.totals["Cu"], "rhs": 0.001},
  {"id": "lg", "op": "==", "lhs": lambda s: s.concentration["ligand_5760"], "rhs": 0.01},
]
'''),
    ]

    failures = 0
    for title, card in cases:
        res = normalize_card_source(card, components=components, species=species)
        print("=" * 68)
        print(f"CASE: {title}   ({len(res.notes)} rewrite(s))")
        for n in res.notes:
            print("   ", n)
        try:
            from constr_code_card_compiler import compile_card  # type: ignore
        except Exception:
            compile_card = None  # type: ignore
        if compile_card is not None:
            try:
                spec = compile_card(res.source, components=components,
                                    species=species, normalize=False)
                print(f"   compile: OK  (K={spec['dof']['K']}, "
                      f"{len(spec['binds'])} binds)")
            except Exception as exc:  # noqa: BLE001
                print(f"   compile: FAILED -- {exc}")
                failures += 1
    print("=" * 68)
    print("SELFTEST", "OK" if failures == 0 else f"FAILED ({failures})")
    return failures


if __name__ == "__main__":                       # pragma: no cover
    raise SystemExit(_selftest())
