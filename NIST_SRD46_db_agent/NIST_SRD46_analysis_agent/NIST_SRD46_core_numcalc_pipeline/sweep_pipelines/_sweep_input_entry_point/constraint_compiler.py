"""
constraint_compiler.py
======================
Tier-1 (explicit-substitution) constraint engine for the unified
calc-input pipeline.

Pipeline overview::

    raw calc-input dict
        |
        v
    expand_sweep_constraints(raw)         # sweep_constraints_expander
        |
        v
    list[binding]                         # one binding per constrained DOF
        |
        v
    compile_constraints(catalog,          # this module
                        axis_names,
                        bindings)
        |
        v
    CompiledConstraints                   # .apply(axis_coords) -> dict[dof, value]
        |
        v
    build_solver_chain(report,            # sweep_dispatcher
                       compiled_constraints=cc)

Bindings accepted by ``compile_constraints``
--------------------------------------------
Each list element is either:

    1. A **dict** ``{lhs_dof: value_or_subobject}``::

         {"pH": 7.0}                         # scalar
         {"E_V": "0.5 - 0.059 * pH"}         # string-formula
         {"redox": "exclude"}                # enum
         {"activity_model": "davies"}
         {"solids": "include"}
         {"temperature":     {"mode": "fixed", "value_K": 298.15}}
         {"ionic_strength":  {"mode": "auto"}}
         {"[Cu]_total":      0.001}
         {"[ligand_5760]_total": "10 ** log10_L_total"}

    2. A **string** ``"<lhs> = <rhs>"``::

         "[ligand_5760]_total = 10 ** log10_L_total"

LHS must be a single DOF token.  RHS scalars are stored verbatim;
strings are parsed against an AST whitelist and turned into closures.

Tier-2 (implicit / outer-Brent / clamped free species) is OUT OF SCOPE
and routed to ``NotImplementedError``.
"""
from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass, field
from typing import (Any, Callable, Dict, Iterable, List, Mapping, Optional,
                    Sequence, Set, Tuple, Union)


# =====================================================================
# Errors
# =====================================================================

class ConstraintCompileError(ValueError):
    """Raised when a constraint set is malformed or inconsistent."""


LN10 = math.log(10.0)


# =====================================================================
# Catalog dataclasses
# =====================================================================

@dataclass
class MetalDescriptor:
    name:         str
    element:      str
    internal_id:  str                    # reference oxidation-state token
    db_id:        Optional[str] = None
    redox_states: List[str] = field(default_factory=list)


@dataclass
class LigandDescriptor:
    name:         str
    db_id:        str
    internal_id:  str = ""
    smiles:       str = ""
    inchi_key:    str = ""


@dataclass
class ChemicalSystem:
    metals:  List[MetalDescriptor]  = field(default_factory=list)
    ligands: List[LigandDescriptor] = field(default_factory=list)


@dataclass
class SystemCatalog:
    chemical_system:       ChemicalSystem        = field(default_factory=ChemicalSystem)
    freeform_vars_define:  Dict[str, Any]        = field(default_factory=dict)


# =====================================================================
# Catalog construction
# =====================================================================

def build_default_catalog(report: Any) -> SystemCatalog:
    """Build a default ``SystemCatalog`` from a ``FreeEnergyReport``.

    Walks ``report.component_meta`` so each ligand's ``db_id``
    (e.g. ``ligand_5760``) and its placeholder ``internal_id`` (``L1``)
    are kept distinct.  Metals are grouped by element prefix so each
    element gets one :class:`MetalDescriptor` whose ``redox_states``
    lists every internal_id that resolves to the same element.

    The reserved placeholders ``M0`` (H+) and ``L0`` (OH-) are skipped.
    """
    by_elem: Dict[str, MetalDescriptor] = {}
    ligands_by_iid: Dict[str, LigandDescriptor] = {}

    for cm in (getattr(report, "component_meta", []) or []):
        ctype = getattr(cm, "comp_type", "")
        iid   = getattr(cm, "internal_id", "") or ""
        db_id = getattr(cm, "db_id", "") or ""
        name  = getattr(cm, "name", "") or iid

        if ctype == "metal":
            if iid in ("", "M0"):       # skip H+ placeholder
                continue
            element = iid.split("$", 1)[0] if "$" in iid else iid
            if element not in by_elem:
                by_elem[element] = MetalDescriptor(
                    name=element, element=element, internal_id=iid,
                    db_id=db_id or None, redox_states=[iid],
                )
            else:
                cur = by_elem[element]
                if iid not in cur.redox_states:
                    cur.redox_states.append(iid)
                # Prefer a non-empty db_id when one comes along.
                if (not cur.db_id) and db_id:
                    cur.db_id = db_id

        elif ctype == "ligand":
            if iid in ("", "L0"):       # skip OH- placeholder
                continue
            ligands_by_iid[iid] = LigandDescriptor(
                name=name, db_id=(db_id or iid), internal_id=iid,
                smiles=getattr(cm, "smiles", "") or "",
                inchi_key=getattr(cm, "inchi", "") or "",
            )

    # Fallback: if the report has no component_meta, derive from the
    # bare metal_ids / ligand_ids lists.
    if not by_elem:
        for mid in (getattr(report, "metal_ids", []) or []):
            if mid in ("M0",):
                continue
            element = mid.split("$", 1)[0] if "$" in mid else mid
            if element not in by_elem:
                by_elem[element] = MetalDescriptor(
                    name=element, element=element, internal_id=mid,
                    redox_states=[mid],
                )
            else:
                cur = by_elem[element]
                if mid not in cur.redox_states:
                    cur.redox_states.append(mid)
    if not ligands_by_iid:
        l_names = list(getattr(report, "ligand_names", []) or [])
        for i, lid in enumerate(getattr(report, "ligand_ids", []) or []):
            if lid in ("L0",):
                continue
            nm = l_names[i] if i < len(l_names) else lid
            ligands_by_iid[lid] = LigandDescriptor(
                name=nm, db_id=lid, internal_id=lid,
            )

    return SystemCatalog(chemical_system=ChemicalSystem(
        metals=list(by_elem.values()),
        ligands=list(ligands_by_iid.values()),
    ))


def merge_catalog_overrides(base: SystemCatalog,
                            user: Mapping[str, Any]) -> SystemCatalog:
    """Deep-merge user override dict onto an auto-built catalog."""
    if not user:
        return base
    cs_user = (user.get("chemical_system") or {})

    # Metals: resolve every user spelling against all canonical aliases.  A
    # name-only index can duplicate a base descriptor when a user supplies
    # the same metal by element symbol (e.g. base name="Iron", user name="Fe").
    metals: List[MetalDescriptor] = list(base.chemical_system.metals)

    def _metal_aliases(m: MetalDescriptor) -> Set[str]:
        return {
            str(value) for value in
            (m.name, m.element, m.internal_id, m.db_id, *m.redox_states)
            if value
        }

    for u in (cs_user.get("metals") or []):
        user_aliases = {
            str(value) for value in
            (u.get("name"), u.get("element"), u.get("internal_id"),
             u.get("db_id"), *(u.get("redox_states") or []))
            if value
        }
        matches = [m for m in metals if _metal_aliases(m) & user_aliases]
        if len(matches) > 1:
            raise ConstraintCompileError(
                f"metal catalog override aliases {sorted(user_aliases)} are "
                "ambiguous across multiple base components")
        if matches:
            cur = matches[0]
            cur.name        = u.get("name",         cur.name)
            cur.element     = u.get("element",      cur.element)
            cur.internal_id = u.get("internal_id",  cur.internal_id)
            cur.db_id       = u.get("db_id",        cur.db_id)
            if u.get("redox_states"):
                # UNION, not REPLACE: the parsed card is the source of
                # truth for which redox states actually appear in the
                # system; user overrides may add hints (e.g. expected
                # but currently missing states) but must never silently
                # drop a state the card has produced.  See
                # docs note in the analysis-agent README.
                merged = list(cur.redox_states)
                for st in u["redox_states"]:
                    if st not in merged:
                        merged.append(st)
                cur.redox_states = merged
        else:
            key = u.get("name") or u.get("element")
            metals.append(MetalDescriptor(
                name=u.get("name", key),
                element=u.get("element", key),
                internal_id=u.get("internal_id", key),
                db_id=u.get("db_id"),
                redox_states=list(u.get("redox_states") or [u.get("internal_id", key)]),
            ))

    by_lid: Dict[str, LigandDescriptor] = {L.db_id: L for L in base.chemical_system.ligands}
    for u in (cs_user.get("ligands") or []):
        lid = u.get("db_id")
        if lid is None:
            continue
        if lid in by_lid:
            cur = by_lid[lid]
            cur.name        = u.get("name",        cur.name)
            cur.internal_id = u.get("internal_id", cur.internal_id)
            cur.smiles      = u.get("smiles",      cur.smiles)
            cur.inchi_key   = u.get("inchi_key",   cur.inchi_key)
        else:
            by_lid[lid] = LigandDescriptor(
                name=u.get("name", lid), db_id=lid,
                internal_id=u.get("internal_id", lid),
                smiles=u.get("smiles", ""),
                inchi_key=u.get("inchi_key", ""),
            )
    ligands = list(by_lid.values())

    return SystemCatalog(
        chemical_system=ChemicalSystem(metals=metals, ligands=ligands),
        freeform_vars_define=dict(user.get("freeform_vars_define") or
                                  base.freeform_vars_define),
    )


def validate_catalog_against_report(catalog: SystemCatalog, report: Any) -> None:
    """Cross-check that every report metal/ligand is declared and vice versa.

    ``report.metal_ids`` and ``report.ligand_ids`` carry *internal_ids*
    (e.g. ``Cu$+2``, ``L1``).  Compare against
    :class:`MetalDescriptor`/`LigandDescriptor` ``internal_id`` fields
    (and metal ``redox_states``).  The reserved ``M0`` / ``L0``
    placeholders (H+/OH-) are excluded from the comparison.
    """
    rep_m = {m for m in (getattr(report, "metal_ids",  []) or []) if m != "M0"}
    rep_l = {L for L in (getattr(report, "ligand_ids", []) or []) if L != "L0"}
    cat_m: Set[str] = set()
    for m in catalog.chemical_system.metals:
        cat_m.add(m.internal_id)
        cat_m.update(m.redox_states)
    cat_l = {L.internal_id for L in catalog.chemical_system.ligands
             if L.internal_id}

    missing_m = rep_m - cat_m
    missing_l = rep_l - cat_l
    extra_m   = cat_m - rep_m
    extra_l   = cat_l - rep_l

    if missing_m or missing_l:
        raise ConstraintCompileError(
            f"system_catalog missing entries present in card: "
            f"metals={sorted(missing_m)} ligands={sorted(missing_l)}")
    if extra_m or extra_l:
        raise ConstraintCompileError(
            f"system_catalog declares entries not in card: "
            f"metals={sorted(extra_m)} ligands={sorted(extra_l)}")


# =====================================================================
# DOF set derivation
# =====================================================================

# Built-in atomic DOFs (always present).
_INTENSIVE_SCALAR_DOFS = ("pH", "E_V", "a_w")
_ENUM_DOFS = {
    "redox":          {"include", "exclude", "solve"},
    "activity_model": {"ideal", "davies"},
    "solids":         {"include", "exclude"},
}

# Composite DOFs: ``temperature.mode``/``.value_K``,
# ``ionic_strength.mode``/``.value_M``.  Keyed by composite root.
_COMPOSITE_DOFS: Dict[str, Tuple[str, Tuple[str, ...]]] = {
    "temperature":     ("value_K", ("fixed", "auto")),
    "ionic_strength":  ("value_M", ("fixed", "auto")),
}


def derive_dof_set(catalog: SystemCatalog) -> Set[str]:
    """Enumerate every DOF token addressable by a constraint LHS."""
    out: Set[str] = set(_INTENSIVE_SCALAR_DOFS)
    out.update(_ENUM_DOFS)
    for root, (val_key, _modes) in _COMPOSITE_DOFS.items():
        out.add(f"{root}.mode")
        out.add(f"{root}.{val_key}")

    for m in catalog.chemical_system.metals:
        out.add(f"[{m.element}]_total")
        if m.name and m.name != m.element:
            out.add(f"[{m.name}]_total")
        if m.db_id:
            out.add(f"[{m.db_id}]_total")
        out.add(f"[{m.internal_id}]_total")
        for rid in m.redox_states:
            out.add(f"[{rid}]_total")
    for L in catalog.chemical_system.ligands:
        out.add(f"[{L.db_id}]_total")
        if L.internal_id and L.internal_id != L.db_id:
            out.add(f"[{L.internal_id}]_total")
    return out


# =====================================================================
# AST whitelist
# =====================================================================

_AST_BIN_OPS = {ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.FloorDiv}
_AST_UNARY_OPS = {ast.UAdd, ast.USub}
_AST_FUNCS: Dict[str, Callable[..., float]] = {
    "sqrt":  math.sqrt,
    "log":   math.log,
    "log10": math.log10,
    "exp":   math.exp,
    "abs":   abs,
    "min":   min,
    "max":   max,
}
_AST_CONSTS: Dict[str, float] = {
    "pi": math.pi,
    "e":  math.e,
    "R":  8.314462618,
    "F":  96485.33212,
    "T0": 298.15,
}


# Bracket tokens like ``[Cu$+2]_total`` or ``[ligand_5760]_total`` are
# illegal Python identifiers; the pre-pass replaces them with mangled
# identifiers before ``ast.parse``.
_BRACKET_TOKEN_RE = re.compile(
    r"\[([A-Za-z0-9_+\-$.]+)\](?:(_total)|(_tot_axis))?")


def _mangle_bracket_tokens(expr: str) -> Tuple[str, Dict[str, str]]:
    """Replace ``[X]`` / ``[X]_total`` with mangled identifiers."""
    mapping: Dict[str, str] = {}

    def _sub(m: re.Match) -> str:
        full = m.group(0)
        if full not in mapping:
            mangled = "_BR_" + re.sub(r"[^A-Za-z0-9_]", "_", full)
            mapping[full] = mangled
        return mapping[full]

    return _BRACKET_TOKEN_RE.sub(_sub, expr), mapping


def _collect_identifiers(node: ast.AST) -> Set[str]:
    out: Set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            out.add(sub.id)
        elif isinstance(sub, ast.Call):
            if not (isinstance(sub.func, ast.Name) and sub.func.id in _AST_FUNCS):
                raise ConstraintCompileError(
                    f"function not in whitelist: {ast.dump(sub.func)}")
    return out


def _check_ast(node: ast.AST) -> None:
    """Walk the AST and reject anything outside the whitelist."""
    for sub in ast.walk(node):
        if isinstance(sub, (ast.Expression, ast.Load, ast.Name, ast.Constant,
                            ast.Num, ast.UnaryOp, ast.BinOp, ast.Call)):
            if isinstance(sub, ast.BinOp) and type(sub.op) not in _AST_BIN_OPS:
                raise ConstraintCompileError(
                    f"operator not in whitelist: {type(sub.op).__name__}")
            if isinstance(sub, ast.UnaryOp) and type(sub.op) not in _AST_UNARY_OPS:
                raise ConstraintCompileError(
                    f"unary operator not in whitelist: {type(sub.op).__name__}")
            continue
        # operators are not nodes by themselves in 3.9+; allow them
        if isinstance(sub, tuple(_AST_BIN_OPS) + tuple(_AST_UNARY_OPS)):
            continue
        raise ConstraintCompileError(
            f"AST node not in whitelist: {type(sub).__name__}")


def _compile_expr(expr: str) -> Tuple[Callable[[Mapping[str, float]], float], Set[str]]:
    """Compile *expr* to ``(closure, free_identifier_set)``.

    The closure takes a mapping of identifier → numeric value and
    returns a float.  Bracket tokens in the original expression are
    presented to the closure under their *original* spelling.
    """
    mangled_expr, mapping = _mangle_bracket_tokens(expr)
    inv_map = {v: k for k, v in mapping.items()}
    try:
        tree = ast.parse(mangled_expr, mode="eval")
    except SyntaxError as exc:
        raise ConstraintCompileError(
            f"could not parse expression {expr!r}: {exc.msg}") from exc
    _check_ast(tree)
    idents = _collect_identifiers(tree)
    free: Set[str] = set()
    for ident in idents:
        if ident in _AST_FUNCS or ident in _AST_CONSTS:
            continue
        free.add(inv_map.get(ident, ident))

    code = compile(tree, "<expr>", "eval")

    def _closure(env: Mapping[str, float]) -> float:
        local: Dict[str, Any] = dict(_AST_CONSTS)
        local.update(_AST_FUNCS)
        for orig, mangled in mapping.items():
            if orig in env:
                local[mangled] = env[orig]
        for k, v in env.items():
            if k not in mapping:
                local[k] = v
        return float(eval(code, {"__builtins__": {}}, local))

    return _closure, free


# =====================================================================
# Binding normalisation
# =====================================================================

# A normalised binding is one of:
#   ("scalar", lhs, value)
#   ("enum",   lhs, value)
#   ("formula", lhs, expr_str, closure, free_idents)
NormBinding = Tuple[str, str, Any, Any, Any]


def _split_string_binding(s: str) -> Tuple[str, str]:
    """Split ``"<lhs> = <rhs>"`` on the first top-level ``=``."""
    depth = 0
    for i, ch in enumerate(s):
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        elif ch == "=" and depth == 0:
            if s[i + 1:i + 2] == "=":
                continue
            return s[:i].strip(), s[i + 1:].strip()
    raise ConstraintCompileError(f"binding string missing '=': {s!r}")


_LHS_BRACKET_RE = re.compile(r"^\[\s*[A-Za-z0-9_+\-$.]+\s*\](?:_total)?$")
_LHS_BARE_RE    = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


def _validate_lhs_token(lhs: str) -> str:
    s = lhs.strip()
    if _LHS_BRACKET_RE.match(s):
        return re.sub(r"\[\s*", "[", re.sub(r"\s*\]", "]", s))
    if _LHS_BARE_RE.match(s):
        return s
    raise ConstraintCompileError(
        f"LHS is not a single DOF token: {lhs!r} "
        f"(multi-DOF LHS is Tier-2)")


def _flatten_dict_binding(d: Mapping[str, Any]) -> List[Tuple[str, Any]]:
    """Expand one dict binding into ``[(lhs, value), ...]``.

    Composite roots (``temperature`` / ``ionic_strength``) split into
    ``<root>.mode`` and ``<root>.<val_key>`` entries.  Sugar form
    ``{<root>: <number>}`` becomes ``mode=fixed, <val_key>=<number>``.
    """
    out: List[Tuple[str, Any]] = []
    for k, v in d.items():
        lhs = _validate_lhs_token(str(k))
        if lhs in _COMPOSITE_DOFS:
            val_key, modes = _COMPOSITE_DOFS[lhs]
            if isinstance(v, Mapping):
                if "mode" in v:
                    out.append((f"{lhs}.mode", str(v["mode"])))
                if val_key in v:
                    out.append((f"{lhs}.{val_key}", v[val_key]))
                # accept "value_C" alias for temperature
                if lhs == "temperature" and "value_C" in v and val_key == "value_K":
                    out.append((f"{lhs}.value_K",
                                float(v["value_C"]) + 273.15))
            elif isinstance(v, str):
                if v in modes:
                    out.append((f"{lhs}.mode", v))
                else:
                    raise ConstraintCompileError(
                        f"{lhs!r} sugar string must be one of {sorted(modes)}; "
                        f"got {v!r}")
            else:
                # numeric sugar
                out.append((f"{lhs}.mode", "fixed"))
                out.append((f"{lhs}.{val_key}", v))
        else:
            out.append((lhs, v))
    return out


def _classify_value(lhs: str, value: Any) -> NormBinding:
    """Decide whether *value* is a scalar, enum, or formula binding."""
    enum_dom = _ENUM_DOFS.get(lhs)
    # Composite mode sub-fields are enum-ish.
    if lhs.endswith(".mode"):
        root = lhs.split(".", 1)[0]
        if root in _COMPOSITE_DOFS:
            enum_dom = set(_COMPOSITE_DOFS[root][1])

    if enum_dom is not None:
        if not isinstance(value, str):
            raise ConstraintCompileError(
                f"DOF {lhs!r} expects an enum value from {sorted(enum_dom)}; "
                f"got {value!r}")
        if value not in enum_dom:
            raise ConstraintCompileError(
                f"DOF {lhs!r} value {value!r} not in {sorted(enum_dom)}")
        return ("enum", lhs, value, None, None)

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return ("scalar", lhs, float(value), None, None)

    if isinstance(value, str):
        closure, free = _compile_expr(value)
        return ("formula", lhs, value, closure, free)

    raise ConstraintCompileError(
        f"unsupported binding value for {lhs!r}: {value!r}")


# =====================================================================
# Compiled constraints + apply()
# =====================================================================

# Legal model-setting LHS names.  This is vocabulary only; unlike the old
# defaults table it supplies no value to ``CompiledConstraints.apply``.
_MODEL_DOF_NAMES = {
    "pH", "E_V", "a_w", "redox", "activity_model", "solids",
    "temperature.mode", "temperature.value_K",
    "ionic_strength.mode", "ionic_strength.value_M",
}

@dataclass
class SpeciesPin:
    """A Tier-2 per-species concentration constraint.

    A pin fixes ``log10 c_j`` of one aqueous species ``species_id`` to a
    target value (scalar or per-cell formula).  Each pin *releases*
    exactly one component total — named by ``released_component_token``
    (e.g. ``"Cu$+2"`` / ``"ligand_5760"``) — so the augmented Newton
    system stays square (see the solver design doc).

    ``released_component_token`` is resolved by :func:`compile_spec` from
    the report-derived principal-component map.  The numeric indices
    ``aqueous_row`` (row ``j`` into ``log_beta_eff``/``stoich_pq``) and
    ``released_component`` (basis index ``k``) are filled in downstream
    in ``build_solver_chain`` where the built system exists; they stay
    ``-1`` until then.
    """
    species_id:              str
    kind:                    str            # "conc" | "lnconc" | "species"
    target_expr:             str            # compiler-syntax RHS expression
    target_closure:          Any            # closure(env)->float, RHS value
    free_idents:             Set[str]
    released_component_token: str = ""       # component whose total is released
    aqueous_row:             int = -1        # row j (resolved downstream)
    released_component:      int = -1        # basis idx k (resolved downstream)


@dataclass
class PhaseBPin:
    """A redox-state sub-total pin solved by the outer-Brent loop (Phase B).

    Emitted by :func:`compile_constraints` when ``redox=include`` and
    ``E_V`` is a *free* scalar (neither a sweep axis nor pinned) while a
    redox-state-resolved total ``[<redox_id>]_total`` is pinned together
    with its parent element total ``[<element>]_total``.  The per-cell
    solver root-finds ``E_V`` so that the solved sub-total of the
    ``redox_token`` oxidation state equals the (per-cell) target carried
    in :meth:`CompiledConstraints.apply`'s ``[<redox_id>]_total`` entry.

    The element total occupies the basis slot as usual (the redox-state
    bind is superseded for the slot by the element-LHS-wins rule in
    ``build_solver_chain._resolve_per_cell``); this pin only names *which*
    oxidation state the released ``E_V`` must satisfy.
    """
    redox_token:  str                     # e.g. "Cu$+2"
    element:      str                     # e.g. "Cu"
    parent_total_key: str                 # e.g. "[Cu]_total"
    total_key:    str                     # e.g. "[Cu$+2]_total" (apply() key)
    redox_states: Tuple[str, ...] = ()    # all states of the element


@dataclass(frozen=True)
class ExcludedComplementPlan:
    """One excluded-redox subtotal derived from an element balance."""

    element: str
    parent_total_key: str
    explicit_state_keys: Tuple[str, ...]
    derived_state_key: str


@dataclass(frozen=True)
class ConstraintVariableInventory:
    """Canonical semantic classes represented by compiled bindings."""

    parent_element_totals: Tuple[str, ...] = ()
    redox_state_subtotals: Tuple[str, ...] = ()
    component_totals: Tuple[str, ...] = ()
    free_species_targets: Tuple[str, ...] = ()
    intensives: Tuple[str, ...] = ()
    axes: Tuple[str, ...] = ()
    user_variables: Tuple[str, ...] = ()


@dataclass
class CompiledConstraints:
    catalog:    SystemCatalog
    axis_names: Tuple[str, ...]
    bindings:   List[NormBinding]
    eval_order: List[str]                     # ordered LHS list
    species_pins:    List["SpeciesPin"] = field(default_factory=list)
    released_totals: List[int]          = field(default_factory=list)
    phase_b_pins:    List["PhaseBPin"]  = field(default_factory=list)
    excluded_complements: List["ExcludedComplementPlan"] = field(
        default_factory=list)
    variable_inventory: "ConstraintVariableInventory" = field(
        default_factory=ConstraintVariableInventory)

    def apply(self, axis_coords: Mapping[str, Any]) -> Dict[str, Any]:
        """Evaluate all Tier-1 constraints; return a full DOF-value dict."""
        # No physical/model defaults are injected here.  Every value used by
        # a formula must come from an explicit axis, binding, or setting.
        env: Dict[str, Any] = {}
        # Axis coordinates come first; constraints may reference them.
        for k, v in axis_coords.items():
            env[k] = v

        by_lhs = {b[1]: b for b in self.bindings}
        for lhs in self.eval_order:
            kind, _, raw, closure, _free = by_lhs[lhs]
            if kind == "scalar" or kind == "enum":
                env[lhs] = raw
            else:  # formula
                env[lhs] = closure(env)

        # With redox excluded, oxidation states are independent conserved
        # components.  An element total plus k-1 explicit state subtotals is
        # a full-rank declaration; derive the one remaining subtotal at each
        # coordinate instead of inventing a default concentration.
        for plan in self.excluded_complements:
            try:
                parent = float(env[plan.parent_total_key])
                explicit = [float(env[key]) for key in plan.explicit_state_keys]
            except KeyError as exc:
                raise ConstraintCompileError(
                    f"redox-excluded complement for {plan.element!r} is "
                    f"missing evaluated declaration {exc.args[0]!r}") from exc
            values = [parent, *explicit]
            if any(not math.isfinite(value) or value < 0 for value in values):
                raise ConstraintCompileError(
                    f"redox-excluded totals for {plan.element!r} must be "
                    f"finite and >= 0; got parent={parent!r}, "
                    f"subtotals={explicit!r}")
            derived = parent - sum(explicit)
            roundoff_tol = 1.0e-12 * max(
                abs(parent), sum(abs(value) for value in explicit), 1.0e-300)
            if not math.isfinite(derived) or derived < -roundoff_tol:
                raise ConstraintCompileError(
                    f"redox-excluded derived subtotal "
                    f"{plan.derived_state_key} is negative ({derived!r}); "
                    f"the explicit state subtotals exceed "
                    f"{plan.parent_total_key}={parent!r}")
            env[plan.derived_state_key] = max(0.0, derived)

        # A redox-state subtotal is a subset of its parent element balance.
        # Reject an unreachable solve target before the outer potential search
        # rather than clamping E at a search limit and returning a misleading
        # unconverged cell.
        for pin in self.phase_b_pins:
            try:
                parent = float(env[pin.parent_total_key])
                target = float(env[pin.total_key])
            except KeyError as exc:
                raise ConstraintCompileError(
                    f"redox solve plan for {pin.element!r} is missing "
                    f"{exc.args[0]!r}") from exc
            if (not math.isfinite(parent) or parent < 0
                    or not math.isfinite(target) or target < 0):
                raise ConstraintCompileError(
                    f"redox solve totals for {pin.element!r} must be finite "
                    f"and >= 0; parent={parent!r}, target={target!r}")
            tolerance = 1.0e-12 * max(abs(parent), abs(target), 1.0e-300)
            if target > parent + tolerance:
                raise ConstraintCompileError(
                    f"redox-state target {pin.total_key}={target!r} exceeds "
                    f"its parent balance {pin.parent_total_key}={parent!r}")
            if target > parent:
                env[pin.total_key] = parent
        return env

    def resolve_pins(self, env: Mapping[str, Any]
                     ) -> List[Tuple[int, int, float]]:
        """Per-cell: evaluate every species pin's ``log10 c`` target.

        ``env`` is the Tier-1 DOF dict from :meth:`apply` (carries axes,
        intensives, totals, freeform vars).  Returns a list of
        ``(aqueous_row, released_component, log10_target)`` triples.
        """
        out: List[Tuple[int, int, float]] = []
        for pin in self.species_pins:
            val = pin.target_closure(env)
            if pin.kind == "lnconc":
                log10_target = float(val) / LN10
            else:                       # "conc" | "species" -> concentration
                v = float(val)
                if v <= 0.0:
                    raise ConstraintCompileError(
                        f"species pin {pin.species_id!r} target must be a "
                        f"positive concentration; got {v!r}")
                log10_target = math.log10(v)
            out.append((pin.aqueous_row, pin.released_component, log10_target))
        return out


# =====================================================================
# compile_constraints
# =====================================================================

def _normalise_bindings(bindings: Sequence[Any]) -> List[Tuple[str, Any]]:
    """Turn the raw bindings list into a flat ``[(lhs, value), ...]``."""
    out: List[Tuple[str, Any]] = []
    for entry in bindings:
        if isinstance(entry, str):
            lhs, rhs = _split_string_binding(entry)
            lhs_v = _validate_lhs_token(lhs)
            # Numeric RHS short-circuit.
            try:
                num = float(rhs)
                out.append((lhs_v, num))
                continue
            except ValueError:
                pass
            out.append((lhs_v, rhs))
        elif isinstance(entry, Mapping):
            out.extend(_flatten_dict_binding(entry))
        else:
            raise ConstraintCompileError(
                f"binding must be a string or dict; got {type(entry).__name__}")
    return out


def _metal_parent_total_keys(metal: MetalDescriptor) -> Set[str]:
    """Canonical parent-element total keys (never redox-state aliases)."""
    keys = {f"[{metal.element}]_total"}
    if metal.name and metal.name != metal.element:
        keys.add(f"[{metal.name}]_total")
    if metal.db_id:
        keys.add(f"[{metal.db_id}]_total")
    return keys


def _metal_state_total_keys(metal: MetalDescriptor) -> Tuple[str, ...]:
    states = list(dict.fromkeys(metal.redox_states or []))
    if metal.internal_id and metal.internal_id not in states:
        states.append(metal.internal_id)
    return tuple(f"[{state}]_total" for state in states)


def _build_variable_inventory(
    catalog: SystemCatalog,
    axis_names: Sequence[str],
    bound_lhs: Set[str],
) -> ConstraintVariableInventory:
    parent_keys: Set[str] = set()
    state_keys: Set[str] = set()
    component_keys: Set[str] = set()
    for metal in catalog.chemical_system.metals:
        parent_keys.update(_metal_parent_total_keys(metal))
        state_keys.update(_metal_state_total_keys(metal))
    for ligand in catalog.chemical_system.ligands:
        component_keys.add(f"[{ligand.db_id}]_total")
        if ligand.internal_id and ligand.internal_id != ligand.db_id:
            component_keys.add(f"[{ligand.internal_id}]_total")

    intensives = set(_MODEL_DOF_NAMES)
    known = parent_keys | state_keys | component_keys | intensives
    return ConstraintVariableInventory(
        parent_element_totals=tuple(sorted(bound_lhs & parent_keys)),
        redox_state_subtotals=tuple(sorted(bound_lhs & state_keys)),
        component_totals=tuple(sorted(bound_lhs & component_keys)),
        intensives=tuple(sorted(bound_lhs & intensives)),
        axes=tuple(axis_names),
        user_variables=tuple(sorted(bound_lhs - known)),
    )


def _analyse_redox_dofs(
    catalog: SystemCatalog,
    bound_lhs: Set[str],
    *,
    redox_mode: str,
    e_v_bound: bool,
    released_component_tokens: Set[str],
) -> Tuple[List[PhaseBPin], List[ExcludedComplementPlan]]:
    """Validate metal-total rank and construct redox solve plans."""
    phase_b_pins: List[PhaseBPin] = []
    complements: List[ExcludedComplementPlan] = []

    if redox_mode == "exclude" and e_v_bound:
        raise ConstraintCompileError(
            "redox='exclude' requires E_V to be absent")
    if redox_mode == "solve" and e_v_bound:
        raise ConstraintCompileError(
            "redox='solve' requires E_V to be free, not axis/fixed/formula bound")
    if redox_mode == "include" and not e_v_bound:
        raise ConstraintCompileError(
            "redox='include' leaves E_V underdetermined; bind E_V by an axis, "
            "fixed value, or formula, or declare redox='solve' with exactly "
            "one redox-state subtotal target")

    for metal in catalog.chemical_system.metals:
        parents = sorted(_metal_parent_total_keys(metal) & bound_lhs)
        states_all = _metal_state_total_keys(metal)
        states = [key for key in states_all if key in bound_lhs]
        metal_tokens = {
            metal.element, metal.name, metal.internal_id,
            *(metal.redox_states or []),
        }
        released_here = bool(
            {str(token) for token in metal_tokens if token}
            & released_component_tokens)

        if released_here:
            if redox_mode != "include" or not e_v_bound:
                raise ConstraintCompileError(
                    f"species-pin release for metal {metal.element!r} is only "
                    "supported with externally bound redox; excluded/solve "
                    "redox requires a more general nonlinear DOF plan")
            if parents or states:
                raise ConstraintCompileError(
                    f"species pin releases metal component {metal.element!r}, "
                    "but its parent/state total is also bound")
            continue

        if len(parents) > 1:
            raise ConstraintCompileError(
                f"metal {metal.element!r} has multiple aliases bound as its "
                f"parent element total: {parents}")

        # A single-state metal has no redox distribution DOF.  Its state key
        # and parent element key are equivalent ways to declare one component
        # total, but not simultaneous independent constraints.
        if len(states_all) <= 1:
            declarations = set(parents) | set(states)
            if len(declarations) == 0:
                raise ConstraintCompileError(
                    f"metal total for {metal.element!r} is Not defined")
            if len(declarations) > 1:
                raise ConstraintCompileError(
                    f"single-state metal {metal.element!r} has duplicate total "
                    f"declarations: {sorted(declarations)}")
            continue

        if redox_mode == "exclude":
            rank = len(states) + (1 if parents else 0)
            expected = len(states_all)
            if rank < expected:
                missing = sorted(set(states_all) - set(states))
                raise ConstraintCompileError(
                    f"redox-excluded metal {metal.element!r} is rank-deficient: "
                    f"declare all {expected} state subtotals, or one parent "
                    f"element total plus {expected - 1} state subtotals; "
                    f"missing state declarations={missing}")
            if rank > expected:
                raise ConstraintCompileError(
                    f"redox-excluded metal {metal.element!r} is over-determined: "
                    "the parent element total and every state subtotal are bound")
            if parents:
                missing = [key for key in states_all if key not in states]
                if len(missing) != 1:
                    raise ConstraintCompileError(
                        f"redox-excluded metal {metal.element!r} must leave "
                        "exactly one state subtotal for complement derivation")
                complements.append(ExcludedComplementPlan(
                    element=metal.element,
                    parent_total_key=parents[0],
                    explicit_state_keys=tuple(states),
                    derived_state_key=missing[0],
                ))
            continue

        if not parents:
            raise ConstraintCompileError(
                f"redox-enabled metal {metal.element!r} requires one parent "
                "element total; redox-state subtotals are not substitutes for "
                "the conserved element balance")

        if redox_mode == "solve":
            if len(states) > 1:
                raise ConstraintCompileError(
                    f"redox='solve' permits at most one state-subtotal target "
                    f"per metal; {metal.element!r} has {states}")
            if states:
                token = states[0][1:-len("]_total")]
                phase_b_pins.append(PhaseBPin(
                    redox_token=token,
                    element=metal.element,
                    parent_total_key=parents[0],
                    total_key=states[0],
                    redox_states=tuple(key[1:-len("]_total")]
                                       for key in states_all),
                ))
        elif states:
            source = "externally bound E_V" if e_v_bound else "redox='include'"
            raise ConstraintCompileError(
                f"redox-state subtotal {states[0]} over-constrains "
                f"{metal.element!r} with {source}; remove the state target or "
                "declare redox='solve' with E_V absent")

    if redox_mode == "solve" and len(phase_b_pins) != 1:
        raise ConstraintCompileError(
            "redox='solve' requires exactly one global redox-state subtotal "
            "target because the system has one shared E_V degree of freedom; "
            f"got {len(phase_b_pins)}")
    return phase_b_pins, complements


def _validate_ligand_total_dofs(
    catalog: SystemCatalog,
    bound_lhs: Set[str],
    released_component_tokens: Set[str],
) -> None:
    """Require exactly one canonical analytical total per ligand."""
    for ligand in catalog.chemical_system.ligands:
        keys = {f"[{ligand.db_id}]_total"}
        if ligand.internal_id and ligand.internal_id != ligand.db_id:
            keys.add(f"[{ligand.internal_id}]_total")
        declared = sorted(keys & bound_lhs)
        aliases = {str(ligand.db_id), str(ligand.internal_id or "")}
        released = bool((aliases - {""}) & released_component_tokens)
        if released:
            if declared:
                raise ConstraintCompileError(
                    f"species pin releases ligand {ligand.name!r}, but its "
                    f"analytical total is also bound: {declared}")
            continue
        if not declared:
            raise ConstraintCompileError(
                f"ligand total for {ligand.name!r} is Not defined; declare "
                f"one of {sorted(keys)}")
        if len(declared) > 1:
            raise ConstraintCompileError(
                f"ligand {ligand.name!r} has duplicate total aliases bound: "
                f"{declared}")


def compile_constraints(catalog: SystemCatalog,
                        axis_names: Sequence[str],
                        bindings: Sequence[Any],
                        *,
                        axis_dof_tokens: Optional[Set[str]] = None,
                        released_component_tokens: Optional[Set[str]] = None,
                        ) -> CompiledConstraints:
    """Validate + topologically order *bindings* against *catalog*.

    Returns a :class:`CompiledConstraints` ready for per-cell
    ``apply(axis_coords)``.

    ``axis_dof_tokens`` names the catalog DOF tokens (``pH`` / ``E_V``)
    that the sweep axes bind, when the axis *names* differ from the bare
    DOF tokens (e.g. ``"E_V_axis"`` binds ``E_V``).  It is consulted only
    by the redox / Phase-B routing so an axis-bound ``E_V`` is recognised
    even though its passthrough bind was dropped during lowering.
    """
    dof_set = derive_dof_set(catalog)
    axis_set = set(axis_names)
    axis_dof = set(axis_dof_tokens or ())
    released_tokens = set(released_component_tokens or ())
    freeform_vars = set((catalog.freeform_vars_define or {}).keys())

    flat = _normalise_bindings(bindings)

    # ── LHS uniqueness + LHS-in-catalog validation ──────────────────
    seen_lhs: Set[str] = set()
    norm: List[NormBinding] = []
    for lhs, value in flat:
        if lhs in seen_lhs:
            raise ConstraintCompileError(
                f"duplicate constraint for LHS {lhs!r}")
        seen_lhs.add(lhs)
        if lhs in axis_set:
            raise ConstraintCompileError(
                f"LHS {lhs!r} is also a sweep axis; remove the constraint "
                f"or remove the axis")
        if (lhs not in dof_set
                and lhs not in _MODEL_DOF_NAMES
                and lhs not in freeform_vars
                and not lhs.endswith(".mode")):
            raise ConstraintCompileError(
                f"LHS {lhs!r} is not a catalog DOF nor a declared "
                f"freeform variable (known DOFs: pH, E_V, a_w, redox, "
                f"activity_model, solids, <root>.mode/.value_*, "
                f"[<element>|<redox_id>|<ligand_db_id>]_total; "
                f"declared freeform_vars={sorted(freeform_vars)})")
        norm.append(_classify_value(lhs, value))

    # ── Canonical variable classes + redox DOF/rank analysis ───────
    bound = {b[1] for b in norm}
    inventory = _build_variable_inventory(catalog, axis_names, bound)
    _validate_ligand_total_dofs(catalog, bound, released_tokens)
    redox_values = [
        str(binding[2]) for binding in norm
        if binding[0] == "enum" and binding[1] == "redox"
    ]
    if len(redox_values) != 1:
        raise ConstraintCompileError(
            "redox mode is Not defined; bind exactly one of "
            "redox='include', redox='exclude', or redox='solve'")
    redox_mode = redox_values[0]
    e_v_axis = ("E_V" in axis_set) or ("E_V" in axis_dof)
    e_v_bound = e_v_axis or ("E_V" in bound)
    p_h_bound = ("pH" in axis_set) or ("pH" in axis_dof) or ("pH" in bound)
    if not p_h_bound:
        raise ConstraintCompileError(
            "pH is Not defined; bind it by an axis, fixed value, or formula")
    phase_b_pins, excluded_complements = _analyse_redox_dofs(
        catalog,
        bound,
        redox_mode=redox_mode,
        e_v_bound=e_v_bound,
        released_component_tokens=released_tokens,
    )

    # ── Build dependency graph + topo sort ──────────────────────────
    # Each formula binding depends on identifiers that are either axes,
    # other bound LHS names, defaults, or constants.  Any reference to
    # an unknown identifier is an error.
    deps: Dict[str, Set[str]] = {}
    for kind, lhs, _raw, _closure, free in norm:
        if kind != "formula":
            deps[lhs] = set()
            continue
        unresolved: Set[str] = set()
        self_refs: Set[str] = set()
        unbound_freeform: Set[str] = set()
        d: Set[str] = set()
        for ident in (free or set()):
            if ident == lhs:
                self_refs.add(ident)
                continue
            if (ident in axis_set or ident in bound
                    or ident in _AST_CONSTS):
                if ident in bound:
                    d.add(ident)
                continue
            if ident in freeform_vars:
                unbound_freeform.add(ident)
                continue
            unresolved.add(ident)
        if self_refs:
            raise ConstraintCompileError(
                f"constraint for {lhs!r} is self-referential; a released "
                "variable requires an explicit nonlinear solve_for path")
        if unbound_freeform:
            raise ConstraintCompileError(
                f"constraint for {lhs!r} references declared but unbound "
                f"freeform variable(s) {sorted(unbound_freeform)}; bind each "
                "variable or make it a sweep axis")
        if unresolved:
            raise ConstraintCompileError(
                f"constraint for {lhs!r} references unknown identifier(s) "
                f"{sorted(unresolved)}; every freeform identifier MUST be "
                f"a catalog DOF, a sweep_axes name, or declared in "
                f"system_catalog.freeform_vars_define. "
                f"Known: axes={sorted(axis_set)}, bound={sorted(bound)}, "
                f"freeform_vars={sorted(freeform_vars)}")
        deps[lhs] = d

    # Kahn topo sort.
    indeg: Dict[str, int] = {lhs: 0 for lhs in deps}
    rev: Dict[str, Set[str]] = {lhs: set() for lhs in deps}
    for lhs, ds in deps.items():
        for d in ds:
            if d in indeg:
                indeg[lhs] += 1
                rev[d].add(lhs)
    queue = [lhs for lhs, n in indeg.items() if n == 0]
    order: List[str] = []
    while queue:
        # Stable order (sort) for reproducibility.
        queue.sort()
        cur = queue.pop(0)
        order.append(cur)
        for nxt in sorted(rev[cur]):
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)
    if len(order) != len(deps):
        cyc = sorted(set(deps) - set(order))
        raise ConstraintCompileError(
            f"cycle detected among constraints: {cyc}")

    return CompiledConstraints(
        catalog=catalog,
        axis_names=tuple(axis_names),
        bindings=norm,
        eval_order=order,
        phase_b_pins=phase_b_pins,
        excluded_complements=excluded_complements,
        variable_inventory=inventory,
    )


# =====================================================================
# Native lc3_2.v1 spec consumption
# =====================================================================
#
# ``compile_spec`` is the canonical front-end that lowers an
# ``lc3_2.v1`` constraint spec (the AST emitted by the LC3_2 card
# compiler) directly into :class:`CompiledConstraints` -- WITHOUT the
# lossy dict-shape ``sweep_constraints`` intermediate.  Tier-1 binds
# (intensives / totals / couplings) reuse the exact same normalisation
# and validation as :func:`compile_constraints`, so Tier-1 numerics are
# byte-identical to the legacy path.  Tier-2 per-species binds (the
# capability the old schema could not express) become
# :class:`SpeciesPin` entries that the augmented solver honours.

_SPEC_BINOPS = {"+", "-", "*", "/", "**", "%"}
_SPEC_FUNCS = {"log", "log10", "exp", "sqrt", "abs", "pow",
               "sinh", "cosh", "tanh", "min", "max"}


class _SpecExprSerializer:
    """Walk an lc3_2.v1 residual AST -> compiler expression string.

    Mirrors the regression bridge serializer but lives in the numcalc
    core so the spec is consumed natively (no dependency on the
    agentic LC3_2 package).  ``axis_token`` maps a spec axis name onto
    the bare token the compiler's formula grammar uses (``pH`` / ``E_V``).
    """

    def __init__(self, lets: Mapping[str, Any],
                 axis_token: Mapping[str, str]):
        self._lets = lets or {}
        self._axis_token = axis_token or {}

    def emit(self, node: Any) -> str:
        if isinstance(node, Mapping) and "const" in node:
            return repr(float(node["const"]))
        if isinstance(node, Mapping) and "axis" in node:
            name = node["axis"]
            tok = self._axis_token.get(name)
            if tok is None:
                raise ConstraintCompileError(
                    f"axis {name!r} has no formula-token mapping")
            return tok
        if isinstance(node, Mapping) and "ref" in node:
            ref = node["ref"]
            if ref in ("pH", "E_V", "a_w", "temperature", "ionic_strength"):
                return ref
            if ref == "total":
                return f"[{node['id']}]_total"
            if ref in ("conc", "lnconc", "species"):
                raise ConstraintCompileError(
                    f"s.{ref}[{node.get('id')!r}] cannot appear on the "
                    f"right-hand side of a constraint; species references "
                    f"are only permitted as a pinned left-hand side")
            if ref == "let":
                let = self._lets.get(node["name"])
                if let is None:
                    raise ConstraintCompileError(
                        f"unknown let {node['name']!r}")
                return self.emit(let["ast"])
            if ref == "var":
                return str(node["name"])
            raise ConstraintCompileError(f"unhandled ref node: {node!r}")
        if isinstance(node, Mapping) and "op" in node:
            op = node["op"]
            args = node.get("args", [])
            if op in _SPEC_BINOPS:
                if len(args) == 1 and op == "-":
                    return f"(-{self.emit(args[0])})"
                if len(args) != 2:
                    raise ConstraintCompileError(
                        f"binary op {op!r} needs 2 args, got {len(args)}")
                return f"({self.emit(args[0])} {op} {self.emit(args[1])})"
            if op in _SPEC_FUNCS:
                inner = ", ".join(self.emit(a) for a in args)
                return f"{op}({inner})"
            raise ConstraintCompileError(f"unhandled op node: {op!r}")
        raise ConstraintCompileError(f"unrecognised AST node: {node!r}")


def _spec_eq_binds(spec: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    return [b for b in (spec.get("binds") or []) if b.get("op") == "=="]


def _spec_intensive_of_lhs(lhs: Any) -> Optional[str]:
    if isinstance(lhs, Mapping) and lhs.get("ref") in (
            "pH", "E_V", "a_w", "temperature", "ionic_strength"):
        return lhs["ref"]
    return None


def _iter_spec_axis_refs(node: Any) -> Set[str]:
    """Collect every symbolic axis referenced by one native AST node."""
    found: Set[str] = set()
    if isinstance(node, Mapping):
        if "axis" in node:
            found.add(str(node["axis"]))
        for value in node.values():
            found.update(_iter_spec_axis_refs(value))
    elif isinstance(node, (list, tuple)):
        for value in node:
            found.update(_iter_spec_axis_refs(value))
    return found


def _derive_spec_axis_map(
    spec: Mapping[str, Any],
    axis_names: Sequence[str],
    explicit: Optional[Mapping[str, str]] = None,
) -> Dict[str, str]:
    """Map every symbolic LC3 axis to one runtime coordinate name."""
    symbolic = [str(value) for value in (spec.get("axes") or [])]
    runtime = [str(value) for value in axis_names]
    if len(symbolic) != len(set(symbolic)):
        raise ConstraintCompileError(
            f"constraint_spec.axes contains duplicates: {symbolic}")
    if len(runtime) != len(set(runtime)):
        raise ConstraintCompileError(
            f"runtime sweep axes contain duplicates: {runtime}")

    declared = set(symbolic)
    referenced: Set[str] = set()
    inferred: Dict[str, str] = {
        str(key): str(value) for key, value in (explicit or {}).items()
    }
    intensive_owner: Dict[str, str] = {}
    for bind in _spec_eq_binds(spec):
        rhs = bind.get("rhs")
        referenced.update(_iter_spec_axis_refs(rhs))
        if not (isinstance(rhs, Mapping) and set(rhs) == {"axis"}):
            continue
        sym = str(rhs["axis"])
        lhs = bind.get("lhs")
        intensive = _spec_intensive_of_lhs(lhs)
        total = _spec_total_token_of_lhs(lhs)
        if intensive is None and total is None:
            continue
        if intensive is not None:
            previous_owner = intensive_owner.get(sym)
            if previous_owner is not None and previous_owner != intensive:
                raise ConstraintCompileError(
                    f"symbolic axis {sym!r} directly drives multiple "
                    f"intensive DOFs: {previous_owner!r} and {intensive!r}")
            explicit_target = (explicit or {}).get(sym)
            if explicit_target is not None and str(explicit_target) != intensive:
                raise ConstraintCompileError(
                    f"axis_token maps {sym!r} to {explicit_target!r}, but its "
                    f"direct bind drives {intensive!r}")
            intensive_owner[sym] = str(intensive)
            inferred[sym] = str(intensive)
        elif sym not in inferred:
            # A total-only axis is conventionally named by that component.
            # If an intensive already owns the axis, the total simply varies
            # with the same coordinate and must not redefine its identity.
            inferred[sym] = str(total)

    undeclared = referenced - declared
    if undeclared:
        raise ConstraintCompileError(
            f"constraint AST references undeclared axis/axes "
            f"{sorted(undeclared)}")
    unused = declared - referenced
    if unused:
        raise ConstraintCompileError(
            f"constraint_spec.axes declares unused axis/axes {sorted(unused)}")

    runtime_set = set(runtime)
    for sym in sorted(declared - set(inferred)):
        candidates = [sym]
        if sym.endswith("_tot_axis"):
            candidates.append(sym[:-len("_tot_axis")])
        if sym.endswith("_axis"):
            candidates.append(sym[:-len("_axis")])
        candidates.extend(
            value[1:-1] for value in list(candidates)
            if value.startswith("[") and value.endswith("]"))
        matches = [value for value in dict.fromkeys(candidates)
                   if value in runtime_set]
        if len(matches) == 1:
            inferred[sym] = matches[0]

    for sym, physical in inferred.items():
        low = sym.lower()
        if low.startswith("ph") and physical != "pH":
            raise ConstraintCompileError(
                f"pH-like symbolic axis {sym!r} cannot drive {physical!r}")
        if (low.startswith("e_v") or low.startswith("eh")
                or low.startswith("potential")) and physical != "E_V":
            raise ConstraintCompileError(
                f"potential-like symbolic axis {sym!r} cannot drive "
                f"{physical!r}")

    missing_map = declared - set(inferred)
    if missing_map:
        raise ConstraintCompileError(
            f"no physical runtime mapping for symbolic axis/axes "
            f"{sorted(missing_map)}; add a direct axis bind or "
            "constraint_settings.axis_token")
    if set(inferred.values()) != set(runtime) or len(inferred) != len(runtime):
        raise ConstraintCompileError(
            "constraint/runtime axis mismatch: "
            f"symbolic mapping={inferred}, runtime axes={runtime}")
    return inferred


def _spec_total_token_of_lhs(lhs: Any) -> Optional[str]:
    if isinstance(lhs, Mapping) and lhs.get("ref") == "total":
        return lhs["id"]
    return None


def _spec_species_of_lhs(lhs: Any) -> Optional[Tuple[str, str]]:
    """Return ``(kind, species_id)`` for a species LHS, else ``None``."""
    if isinstance(lhs, Mapping) and lhs.get("ref") in (
            "conc", "lnconc", "species"):
        return (lhs["ref"], lhs["id"])
    return None


def _lower_spec(spec: Mapping[str, Any],
                settings: Mapping[str, Any]
                ) -> Tuple[List[Any], List[Dict[str, Any]]]:
    """Lower an lc3_2.v1 spec to ``(tier1_bindings, species_bind_nodes)``.

    ``tier1_bindings`` is the canonical bindings list consumed by
    :func:`compile_constraints` (identical ordering to the legacy
    expander).  ``species_bind_nodes`` collects raw ``conc/lnconc/
    species`` equality binds for Tier-2 pin construction.
    """
    settings = dict(settings or {})
    lets = spec.get("lets", {}) or {}

    # Every declared axis is a legal formula identifier.  pH/E aliases map
    # onto their physical DOF names; arbitrary total axes retain their own
    # name unless settings supplies an explicit alias.
    axis_token: Dict[str, str] = {
        str(axis): str(axis) for axis in (spec.get("axes", []) or [])
    }
    for ax in spec.get("axes", []) or []:
        low = ax.lower()
        if low.startswith("ph"):
            axis_token[ax] = "pH"
        elif low.startswith("e"):
            axis_token[ax] = "E_V"
    axis_token.update(settings.get("axis_token", {}) or {})

    ser = _SpecExprSerializer(lets, axis_token)

    pH_bind: Optional[Dict[str, Any]] = None
    redox_bind: Optional[Dict[str, Any]] = None
    a_w_bind: Optional[Dict[str, Any]] = None
    temp_bind: Optional[Dict[str, Any]] = None
    is_bind: Optional[Dict[str, Any]] = None
    total_binds: List[Dict[str, Any]] = []
    custom_freeform: List[str] = []
    species_nodes: List[Dict[str, Any]] = []

    def _is_const(n: Any) -> bool:
        return isinstance(n, Mapping) and "const" in n

    def _is_axis(n: Any) -> bool:
        return isinstance(n, Mapping) and "axis" in n

    for b in _spec_eq_binds(spec):
        lhs = b.get("lhs")
        rhs = b.get("rhs")

        species = _spec_species_of_lhs(lhs)
        if species is not None:
            species_nodes.append(b)
            continue

        intensive = _spec_intensive_of_lhs(lhs)
        token = _spec_total_token_of_lhs(lhs)

        if intensive is not None:
            if _is_axis(rhs):
                continue
            if intensive == "pH":
                if _is_const(rhs):
                    pH_bind = {"pH": float(rhs["const"])}
                else:
                    custom_freeform.append(f"pH = {ser.emit(rhs)}")
            elif intensive == "E_V":
                if _is_const(rhs):
                    redox_bind = {"E_V": float(rhs["const"])}
                else:
                    custom_freeform.append(f"E_V = {ser.emit(rhs)}")
            elif intensive == "a_w":
                if _is_const(rhs):
                    a_w_bind = {"a_w": float(rhs["const"])}
                else:
                    custom_freeform.append(f"a_w = {ser.emit(rhs)}")
            elif intensive == "temperature":
                if _is_const(rhs):
                    temp_bind = {"temperature":
                                 {"mode": "fixed",
                                  "value_K": float(rhs["const"])}}
                else:
                    raise ConstraintCompileError(
                        "non-constant temperature bind not supported")
            elif intensive == "ionic_strength":
                if _is_const(rhs):
                    is_bind = {"ionic_strength":
                               {"mode": "fixed",
                                "value_M": float(rhs["const"])}}
                else:
                    raise ConstraintCompileError(
                        "non-constant ionic_strength bind not supported")
            continue

        if token is not None:
            if _is_axis(rhs):
                total_binds.append({f"[{token}]_total": ser.emit(rhs)})
                continue
            if _is_const(rhs):
                total_binds.append({f"[{token}]_total": float(rhs["const"])})
            else:
                custom_freeform.append(f"[{token}]_total = {ser.emit(rhs)}")
            continue

        # general coupling bind -> custom_freeform string
        custom_freeform.append(f"{ser.emit(lhs)} = {ser.emit(rhs)}")

    bindings: List[Any] = []
    if pH_bind is not None:
        bindings.append(pH_bind)

    redox_mode = settings.get("redox_mode")
    if redox_mode == "excluded":
        bindings.append({"redox": "exclude"})
    elif redox_mode == "solve":
        bindings.append({"redox": "solve"})
    elif redox_mode in ("axis", "fixed", "freeform"):
        bindings.append({"redox": "include"})
        if redox_bind is not None:
            bindings.append(redox_bind)

    if a_w_bind is not None:
        bindings.append(a_w_bind)

    if temp_bind is not None:
        bindings.append(temp_bind)

    is_mode = settings.get("ionic_strength_mode")
    if is_mode == "auto":
        bindings.append({"ionic_strength": {"mode": "auto"}})
    elif is_bind is not None:
        bindings.append(is_bind)

    if "activity_model" in settings:
        bindings.append({"activity_model": settings["activity_model"]})
    if "solids" in settings:
        bindings.append({"solids": settings["solids"]})

    bindings.extend(total_binds)
    bindings.extend(custom_freeform)

    for name, val in (settings.get("freeform_vars") or {}).items():
        bindings.append({name: float(val)})

    return bindings, species_nodes


def compile_spec(catalog: SystemCatalog,
                 axis_names: Sequence[str],
                 spec: Mapping[str, Any],
                 settings: Optional[Mapping[str, Any]] = None,
                 *,
                 component_of_species: Optional[Mapping[str, str]] = None,
                 species_pins_allowed: bool = False,
                 ) -> CompiledConstraints:
    """Compile an ``lc3_2.v1`` spec (+settings) to ``CompiledConstraints``.

    This is the native, no-fallback replacement for the
    ``expand_sweep_constraints`` -> ``compile_constraints`` chain.

    Tier-1 binds are lowered to the canonical bindings list and run
    through :func:`compile_constraints` unchanged (byte-identical).
    Tier-2 ``s.species`` / ``s.conc`` / ``s.lnconc`` binds become
    :class:`SpeciesPin` entries; each releases one component total so
    the augmented Newton system stays square.

    ``component_of_species`` maps ``species_id -> released component
    token`` (e.g. ``"Cu$+2"`` / ``"ligand_5760"``), derived from the
    report's stoichiometry (principal component of the species).  The
    numeric ``aqueous_row`` / ``released_component`` indices are resolved
    downstream in ``build_solver_chain``.  When species binds are present
    this map MUST be supplied and ``species_pins_allowed`` MUST be true.
    """
    settings = dict(settings or {})

    # Promote any named scalar parameters declared in
    # ``settings['freeform_vars']`` (e.g. ``slope``/``intercept`` for a
    # user-defined Nernst line ``E_V = intercept + slope * pH``) into the
    # catalog's ``freeform_vars_define`` set.  ``_lower_spec`` lowers each
    # one to a scalar binding ``{name: value}``, but ``compile_constraints``
    # only accepts such an LHS (and resolves formula references to it) when
    # the name is a *declared* freeform variable.  Without this promotion a
    # card that drives a DOF from named scalars fails to compile with
    # "LHS '<name>' is not a catalog DOF nor a declared freeform variable".
    fv_settings = settings.get("freeform_vars") or {}
    if fv_settings:
        merged_fv = dict(catalog.freeform_vars_define or {})
        for _name, _val in fv_settings.items():
            merged_fv.setdefault(str(_name), {"value": float(_val)})
        catalog = SystemCatalog(
            chemical_system=catalog.chemical_system,
            freeform_vars_define=merged_fv,
        )

    axis_map = _derive_spec_axis_map(
        spec, axis_names, settings.get("axis_token") or {})
    settings["axis_token"] = axis_map
    tier1_bindings, species_nodes = _lower_spec(spec, settings)

    # General nonlinear/species equations are not silently treated as
    # ordinary scalar declarations.  They require the explicit Tier-2 path
    # and a unique component release supplied by the report adapter.
    if species_nodes and not species_pins_allowed:
        raise ConstraintCompileError(
            "this card pins individual species (s.species/s.conc/s.lnconc) "
            "but no explicit Tier-2 solve/release path is enabled; set "
            "species_pins='allowed' and provide one unique released component")
    if species_nodes and component_of_species is None:
        raise ConstraintCompileError(
            "species pins require one explicit/unique released component per "
            "target; the report-derived component mapping is unavailable")

    # Establish the released analytical components before the Tier-1
    # completeness/rank gate.  A species target replaces exactly one total
    # equation; requiring that same total first and rejecting it later made
    # the explicit Tier-2 path impossible by construction.
    released_tokens_pre: List[str] = []
    if species_nodes:
        for node in species_nodes:
            _kind, sid = _spec_species_of_lhs(node.get("lhs"))
            comp_token = component_of_species.get(sid)
            if comp_token is None:
                raise ConstraintCompileError(
                    f"no principal component is known for pinned species "
                    f"{sid!r} (component_of_species map has no entry)")
            token = str(comp_token)
            if token in released_tokens_pre:
                raise ConstraintCompileError(
                    f"two species pins release the same component {token!r}; "
                    "pin species from distinct components")
            released_tokens_pre.append(token)

    # Tell ``compile_constraints`` which catalog DOF tokens the sweep axes
    # bind.  Spec axes carry physical names (``pH_axis`` / ``E_V_axis``);
    # the redox / Phase-B routing must recognise an axis-bound ``E_V``
    # even though its passthrough bind is dropped during lowering.  Map
    # by the same prefix convention ``_lower_spec`` uses, then honour any
    # explicit ``settings['axis_token']`` overrides.
    axis_dof_tokens: Set[str] = set(axis_map.values())

    compiled = compile_constraints(
        catalog, axis_names, tier1_bindings,
        axis_dof_tokens=axis_dof_tokens,
        released_component_tokens=set(released_tokens_pre))

    if species_nodes:
        compiled.variable_inventory = ConstraintVariableInventory(
            parent_element_totals=(
                compiled.variable_inventory.parent_element_totals),
            redox_state_subtotals=(
                compiled.variable_inventory.redox_state_subtotals),
            component_totals=compiled.variable_inventory.component_totals,
            free_species_targets=tuple(sorted(
                str((_spec_species_of_lhs(node.get("lhs")) or ("", ""))[1])
                for node in species_nodes
            )),
            intensives=compiled.variable_inventory.intensives,
            axes=compiled.variable_inventory.axes,
            user_variables=compiled.variable_inventory.user_variables,
        )

    if not species_nodes:
        return compiled

    # ── Tier-2: species pins ────────────────────────────────────────
    lets = spec.get("lets", {}) or {}
    axis_token: Dict[str, str] = {
        str(axis): str(axis) for axis in (spec.get("axes", []) or [])
    }
    for ax in spec.get("axes", []) or []:
        low = ax.lower()
        if low.startswith("ph"):
            axis_token[ax] = "pH"
        elif low.startswith("e"):
            axis_token[ax] = "E_V"
    axis_token.update(settings.get("axis_token", {}) or {})
    ser = _SpecExprSerializer(lets, axis_token)

    axis_set = set(axis_names)
    bound_lhs = {b[1] for b in compiled.bindings}
    freeform_vars = set((catalog.freeform_vars_define or {}).keys())

    pins: List[SpeciesPin] = []
    released_tokens: List[str] = []
    seen_components: Set[str] = set()
    for b in species_nodes:
        kind, sid = _spec_species_of_lhs(b["lhs"])
        comp_token = component_of_species.get(sid)
        if comp_token is None:
            raise ConstraintCompileError(
                f"no principal component is known for pinned species "
                f"{sid!r} (component_of_species map has no entry)")
        # The released component's total must NOT also be fixed (square DOF).
        if f"[{comp_token}]_total" in bound_lhs:
            raise ConstraintCompileError(
                f"species pin {sid!r} releases component {comp_token!r} but "
                f"that component's total is also fixed; remove the total "
                f"bind (the pin determines it) or drop the pin")
        if comp_token in seen_components:
            raise ConstraintCompileError(
                f"two species pins release the same component "
                f"{comp_token!r}; pin species from distinct components")
        seen_components.add(comp_token)

        rhs = b.get("rhs")
        expr = ser.emit(rhs)
        closure, free = _compile_expr(expr)
        # Validate RHS identifiers resolve (axes / bound DOFs / freeform).
        unresolved = {ident for ident in free
                      if ident not in axis_set and ident not in bound_lhs
                      and ident not in _AST_CONSTS
                      and ident not in freeform_vars}
        if unresolved:
            raise ConstraintCompileError(
                f"species pin {sid!r} RHS references unknown identifier(s) "
                f"{sorted(unresolved)}")

        pins.append(SpeciesPin(
            species_id=sid, kind=kind, target_expr=expr,
            target_closure=closure, free_idents=free,
            released_component_token=comp_token,
        ))
        released_tokens.append(comp_token)

    compiled.species_pins = pins
    # released_totals holds component *tokens* until basis indices are
    # resolved in build_solver_chain (where it is rewritten to ints).
    compiled.released_totals = released_tokens
    return compiled


__all__ = [
    "ConstraintCompileError",
    "MetalDescriptor", "LigandDescriptor",
    "ChemicalSystem", "SystemCatalog",
    "build_default_catalog", "merge_catalog_overrides",
    "validate_catalog_against_report",
    "derive_dof_set",
    "CompiledConstraints", "compile_constraints",
    "SpeciesPin", "compile_spec",
]
