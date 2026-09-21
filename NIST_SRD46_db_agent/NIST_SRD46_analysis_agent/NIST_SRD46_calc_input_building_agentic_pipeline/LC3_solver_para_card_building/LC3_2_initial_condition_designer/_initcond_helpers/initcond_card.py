"""LC3_2 initial-condition card validator  (initcond_card.py)
============================================================

Parses an agent-emitted *initial-condition card* -- a small Python module
string with a single top-level ``inits`` list written in the SAME lambda
surface syntax as the LC3_3 constraint card -- and validates it into a
compact structured list of KNOWN / ASSUMED scalar pins.

CRITICAL: the card is **parsed with ``ast`` and NEVER executed.**  An
initial condition is a constant assignment (``s.temperature == 298.15``);
unlike the constraint card it carries no sweep axes and no freeform
coupling expressions -- only literal numbers.  This keeps the layer's
output a drop-in subset of the constraint binds the LC3_3 agent writes.

The card shape (mirrors the constraint bind triplet so the constraint
designer can lift entries verbatim)::

    inits = [
      {"id": "T",  "lhs": lambda s: s.temperature,    "value": 298.15, "basis": "known"},
      {"id": "I",  "lhs": lambda s: s.ionic_strength, "value": 0.1,    "basis": "assumed"},
      {"id": "Cu", "lhs": lambda s: s.total["Cu"],    "value": 1e-3,   "basis": "assumed"},
    ]

* ``id``    -- optional short tag (defaults to the handle).
* ``lhs``   -- required ``lambda s: <handle>`` over one solver-state
               handle (intensive or ``s.<ns>["<id>"]``).
* value     -- required literal number; key ``value`` OR ``rhs``.
* ``basis`` -- ``"known"`` (fixed by the task) or ``"assumed"``
               (a reasonable default); defaults to ``"assumed"``.
* ``op``    -- optional; if present must be ``"=="``.
* ``note``  -- optional free-text rationale.

Public API
----------
``compile_initcond_card(source, *, components, species, intensives=None)
    -> InitCondResult``
    Returns the validated result, or raises ``InitCondCompileError`` whose
    ``.issues`` is a list of ``{"line", "msg"}`` located errors.
``render_initcond_brief(result) -> str``
    Renders the validated pins as a code-style brief for the LC3_3 prompt.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple


# Reserved intensive names addressable as ``s.<name>`` (mirrors
# ``constr_code_card_compiler._INTENSIVES``).
_INTENSIVES: Tuple[str, ...] = ("temperature", "ionic_strength", "pH", "E_V")

# Sub-namespaces addressable as ``s.<ns>["<id>"]`` (mirrors
# ``constr_code_card_compiler._STATE_SUBNS``).
_STATE_SUBNS: Tuple[str, ...] = ("conc", "lnconc", "total", "species")

_BASES = ("known", "assumed")


# ════════════════════════════════════════════════════════════════════
#  Result / error types
# ════════════════════════════════════════════════════════════════════

@dataclass
class InitCondPin:
    """One validated initial-condition pin."""
    id: str                      # short tag
    ref: str                     # intensive name OR sub-namespace ("total" ...)
    handle_id: Optional[str]     # the "<id>" for a sub-namespace handle
    value: float                 # the literal scalar
    basis: str                   # "known" | "assumed"
    note: str = ""
    line: Optional[int] = None

    @property
    def handle(self) -> str:
        if self.handle_id is None:
            return f"s.{self.ref}"
        return f's.{self.ref}["{self.handle_id}"]'


@dataclass
class InitCondResult:
    """Result of :func:`compile_initcond_card`."""
    pins: List[InitCondPin] = field(default_factory=list)
    source: str = ""             # the (possibly normalized) card source

    @property
    def known(self) -> List[InitCondPin]:
        return [p for p in self.pins if p.basis == "known"]

    @property
    def assumed(self) -> List[InitCondPin]:
        return [p for p in self.pins if p.basis == "assumed"]


class InitCondCompileError(Exception):
    """Raised when an initial-condition card fails to parse or validate.

    ``issues`` is a list of ``{"line": int|None, "msg": str}`` located
    errors suitable for feeding back to the agent for repair.
    """

    def __init__(self, issues: Sequence[Dict[str, Any]]):
        self.issues: List[Dict[str, Any]] = list(issues)
        super().__init__("; ".join(self.format_lines()))

    def format_lines(self) -> List[str]:
        out: List[str] = []
        for it in self.issues:
            ln = it.get("line")
            loc = f"line {ln}: " if ln else ""
            out.append(loc + str(it.get("msg", "")))
        return out


# ════════════════════════════════════════════════════════════════════
#  Helpers
# ════════════════════════════════════════════════════════════════════

def _did_you_mean(token: str, pool: Sequence[str], k: int = 3) -> str:
    """Cheap suggestion string for an unknown id."""
    import difflib
    hits = difflib.get_close_matches(token, list(pool), n=k, cutoff=0.5)
    return f"  did you mean: {', '.join(hits)}?" if hits else ""


def _const_number(node: ast.AST) -> Optional[float]:
    """Return a literal number from a Constant or unary +/- Constant."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)) \
            and isinstance(node.operand, ast.Constant) \
            and isinstance(node.operand.value, (int, float)) \
            and not isinstance(node.operand.value, bool):
        v = float(node.operand.value)
        return -v if isinstance(node.op, ast.USub) else v
    return None


def _resolve_handle(
    body: ast.AST,
    ctx_components: Set[str],
    ctx_species: Set[str],
    ctx_intensives: Set[str],
    issues: List[Dict[str, Any]],
    line: Optional[int],
) -> Optional[Tuple[str, Optional[str]]]:
    """Resolve a ``lambda s:`` body to ``(ref, handle_id)`` or record an issue.

    Accepts ``s.<intensive>`` and ``s.<ns>["<id>"]``; nothing else.
    """
    # s.<intensive>
    if isinstance(body, ast.Attribute) and isinstance(body.value, ast.Name) \
            and body.value.id == "s":
        name = body.attr
        if name in ctx_intensives:
            return (name, None)
        if name in _STATE_SUBNS:
            issues.append({"line": line,
                           "msg": f's.{name} needs an id: write s.{name}["<id>"]'})
            return None
        issues.append({"line": line,
                       "msg": f"unknown intensive handle s.{name}; "
                              f"valid: {', '.join(sorted(ctx_intensives))}"})
        return None

    # s.<ns>["<id>"]
    if isinstance(body, ast.Subscript) and isinstance(body.value, ast.Attribute) \
            and isinstance(body.value.value, ast.Name) and body.value.value.id == "s":
        ns = body.value.attr
        if ns not in _STATE_SUBNS:
            issues.append({"line": line,
                           "msg": f"unknown sub-namespace s.{ns}; "
                                  f"valid: {', '.join(_STATE_SUBNS)}"})
            return None
        key_node = body.slice
        if isinstance(key_node, ast.Index):           # py<3.9 compatibility
            key_node = key_node.value                  # type: ignore[attr-defined]
        if not (isinstance(key_node, ast.Constant) and isinstance(key_node.value, str)):
            issues.append({"line": line,
                           "msg": f's.{ns}[...] id must be a string literal'})
            return None
        hid = key_node.value
        if ns == "total":
            pool, label = ctx_components, "component"
        elif ns == "species":
            pool, label = ctx_species, "species"
        else:                                          # conc / lnconc: either
            pool = ctx_components | ctx_species
            label = "component or species"
        if hid not in pool:
            issues.append({"line": line,
                           "msg": f'unknown {label} id "{hid}" for s.{ns}[...]'
                                  + _did_you_mean(hid, sorted(pool))})
            return None
        return (ns, hid)

    issues.append({"line": line,
                   "msg": "lhs must be lambda s: s.<intensive> or "
                          's.<ns>["<id>"] (a single handle, no expression)'})
    return None


def _lambda_body(node: ast.AST, issues: List[Dict[str, Any]],
                 line: Optional[int]) -> Optional[ast.AST]:
    """Validate a ``lambda s: <body>`` node and return its body."""
    if not isinstance(node, ast.Lambda):
        issues.append({"line": line, "msg": "lhs must be a lambda: lambda s: ..."})
        return None
    args = node.args
    names = [a.arg for a in args.args]
    if names != ["s"]:
        issues.append({"line": line,
                       "msg": f"lhs lambda must take exactly one arg 's' "
                              f"(got {names or 'none'})"})
        return None
    return node.body


# ════════════════════════════════════════════════════════════════════
#  Public API
# ════════════════════════════════════════════════════════════════════

def compile_initcond_card(
    source: str,
    *,
    components: Sequence[str],
    species: Sequence[str],
    intensives: Optional[Sequence[str]] = None,
    source_name: str = "initial_condition_card.py",
) -> InitCondResult:
    """Validate an initial-condition card into a list of pins.

    Parameters
    ----------
    source
        The Python card module string with a top-level ``inits`` list.
    components, species
        The authoritative id pools (from ``build_variable_catalog``).
    intensives
        Override the default intensive handle set.
    """
    comp_set: Set[str] = set(components or ())
    spec_set: Set[str] = set(species or ())
    int_set: Set[str] = set(intensives or _INTENSIVES)

    issues: List[Dict[str, Any]] = []
    try:
        tree = ast.parse(source, filename=source_name)
    except SyntaxError as exc:
        raise InitCondCompileError(
            [{"line": exc.lineno, "msg": f"card is not valid Python: {exc.msg}"}]
        )

    # Find the top-level ``inits = [...]`` assignment.
    inits_node: Optional[ast.AST] = None
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            for tgt in stmt.targets:
                if isinstance(tgt, ast.Name) and tgt.id == "inits":
                    inits_node = stmt.value
    if inits_node is None:
        raise InitCondCompileError(
            [{"line": None, "msg": "card must define a top-level `inits = [...]` list"}]
        )
    if not isinstance(inits_node, (ast.List, ast.Tuple)):
        raise InitCondCompileError(
            [{"line": getattr(inits_node, "lineno", None),
              "msg": "`inits` must be a list of dicts"}]
        )

    pins: List[InitCondPin] = []
    seen_handles: Set[str] = set()
    for elt in inits_node.elts:
        line = getattr(elt, "lineno", None)
        if not isinstance(elt, ast.Dict):
            issues.append({"line": line, "msg": "each `inits` entry must be a dict"})
            continue
        fields: Dict[str, ast.AST] = {}
        for k_node, v_node in zip(elt.keys, elt.values):
            if isinstance(k_node, ast.Constant) and isinstance(k_node.value, str):
                fields[k_node.value] = v_node

        # op (optional, must be "==")
        op_node = fields.get("op")
        if op_node is not None:
            if not (isinstance(op_node, ast.Constant) and op_node.value == "=="):
                issues.append({"line": line,
                               "msg": 'op (if given) must be "==" for an '
                                      'initial condition'})

        # lhs handle
        lhs_node = fields.get("lhs")
        if lhs_node is None:
            issues.append({"line": line, "msg": "entry missing `lhs`"})
            continue
        body = _lambda_body(lhs_node, issues, line)
        if body is None:
            continue
        resolved = _resolve_handle(body, comp_set, spec_set, int_set, issues, line)
        if resolved is None:
            continue
        ref, handle_id = resolved

        # value (key `value` or `rhs`)
        val_node = fields.get("value", fields.get("rhs"))
        if val_node is None:
            issues.append({"line": line,
                           "msg": "entry missing a literal `value` (or `rhs`)"})
            continue
        value = _const_number(val_node)
        if value is None:
            issues.append({"line": line,
                           "msg": "`value` must be a literal number (an initial "
                                  "condition is a constant, not an expression)"})
            continue

        # basis (optional)
        basis = "assumed"
        basis_node = fields.get("basis")
        if basis_node is not None:
            if isinstance(basis_node, ast.Constant) and basis_node.value in _BASES:
                basis = basis_node.value
            else:
                issues.append({"line": line,
                               "msg": f"basis must be one of {_BASES}"})

        # note (optional)
        note = ""
        note_node = fields.get("note")
        if isinstance(note_node, ast.Constant) and isinstance(note_node.value, str):
            note = note_node.value

        # id tag (optional)
        tag = ""
        id_node = fields.get("id")
        if isinstance(id_node, ast.Constant) and isinstance(id_node.value, str):
            tag = id_node.value
        pin = InitCondPin(
            id=tag or (handle_id or ref),
            ref=ref, handle_id=handle_id, value=value,
            basis=basis, note=note, line=line,
        )
        if pin.handle in seen_handles:
            issues.append({"line": line,
                           "msg": f"duplicate initial condition for {pin.handle}"})
            continue
        seen_handles.add(pin.handle)
        pins.append(pin)

    if issues:
        raise InitCondCompileError(issues)

    return InitCondResult(pins=pins, source=source)


def render_initcond_brief(result: InitCondResult) -> str:
    """Render the validated pins as a code-style brief for the LC3_3 prompt."""
    if not result.pins:
        return "# INITIAL CONDITIONS -- none declared (no values fixed up front)."
    lines: List[str] = [
        "# INITIAL CONDITIONS -- values already KNOWN or ASSUMED for this system.",
        "# These are drop-in constant binds: reuse them verbatim in your card",
        "# unless a value is swept on an axis.  'known' = fixed by the task;",
        "# 'assumed' = a reasonable default you may override with justification.",
        "inits = [",
    ]
    width = max((len(p.handle) for p in result.pins), default=0)
    for p in result.pins:
        note = f'  # {p.note}' if p.note else ""
        lines.append(
            f'  {{"lhs": lambda s: {p.handle.ljust(width)}, '
            f'"rhs": {p.value!r}, "basis": "{p.basis}"}},{note}'
        )
    lines.append("]")
    return "\n".join(lines)
