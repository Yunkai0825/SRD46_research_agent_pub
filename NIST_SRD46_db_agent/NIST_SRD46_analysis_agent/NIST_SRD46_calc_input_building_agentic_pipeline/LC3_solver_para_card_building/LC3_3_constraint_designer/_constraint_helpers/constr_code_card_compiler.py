"""LC3_2 freeform constraint-card compiler  (lc3_2_card_compiler.py)
====================================================================

Parses an agent-emitted *constraint card* — a small Python module string
with three top-level bindings ``axes`` / ``lets`` / ``binds`` written in
lambda surface syntax — and compiles it into the solver-facing
``lc3_2.v1`` residual specification.

CRITICAL: the card is **parsed with ``ast`` and NEVER executed**.  Bind
expressions reference *solver unknowns* (``s.lnconc["Fe$+2"]`` etc.) that
do not exist at design time; they are symbolic residuals, not values.
There is no ``eval``/``exec`` anywhere in this module.

Pipeline (see ``_Future_plan_full_freeform/readme.md`` §1–§5):

    ast.parse(card)
      -> structural walk (extract axes / lets / binds)
      -> per-expression allowlist walk -> residual-AST nodes
      -> semantic validation:
           (1) id resolution against the L2 namespace
           (2) lets form an acyclic DAG
           (3) DOF count == K  (number of '==' binds)
           (4) numeric Jacobian-rank independence at a feasible sample
           (5) domain guards on log / sqrt / division
      -> canonical ``lc3_2.v1`` JSON dict

Public API
----------
``compile_card(source, *, components, species, intensives=None,
               expected_K=None, charge_balance_enforced=False) -> dict``
    Returns the ``lc3_2.v1`` spec dict, or raises ``CardCompileError``
    whose ``.issues`` is a list of ``{"line", "msg"}`` located errors.

The emitted AST node grammar:

    {"op": <sym>, "args": [<node>, ...]}      # operator / function
    {"ref": "lnconc"|"conc"|"total"|"species", "id": <str>}
    {"ref": "temperature"|"ionic_strength"|"pH"|"E_V"}
    {"ref": "let", "name": <str>}
    {"const": <number>}
    {"axis": <str>}
"""

from __future__ import annotations

import ast
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

try:                                              # numpy backs the rank check
    import numpy as _np
except Exception:                                 # pragma: no cover
    _np = None


SCHEMA_VERSION = "lc3_2.v1"

# Reserved intensive names addressable as ``s.<name>``.  ``E_V`` is a
# *passthrough* redox handle: the solver consumes it as a fixed grid
# parameter (Strategy B), so an ``s.E_V`` bind never becomes a residual
# row -- it is intercepted and routed to the existing redox input path.
_INTENSIVES: Tuple[str, ...] = ("temperature", "ionic_strength", "pH", "E_V")

# Sub-namespaces addressable as ``s.<ns>[<id>]``.
_STATE_SUBNS: Tuple[str, ...] = ("conc", "lnconc", "total", "species")

# Whitelisted callable functions (readme §2).  ``ln`` is natural log and
# normalises onto ``log``.
_FUNC_WHITELIST: Dict[str, str] = {
    "log": "log", "ln": "log", "log10": "log10", "exp": "exp",
    "sqrt": "sqrt", "abs": "abs", "pow": "pow",
    "sinh": "sinh", "cosh": "cosh", "tanh": "tanh",
}

# Binary operators -> emitted op symbol.
_BINOP_SYM: Dict[type, str] = {
    ast.Add: "+", ast.Sub: "-", ast.Mult: "*",
    ast.Div: "/", ast.Pow: "**", ast.Mod: "%",
}

_VALID_OPS = ("==", "<=", ">=")


# ════════════════════════════════════════════════════════════════════
#  Errors
# ════════════════════════════════════════════════════════════════════

class CardCompileError(Exception):
    """Raised when a card fails to parse, validate, or compile.

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


@dataclass
class _Ctx:
    """Mutable accumulator threaded through the structural/expr walks."""
    components: Set[str]
    species: Set[str]
    intensives: Set[str]
    axes: List[str] = field(default_factory=list)
    let_names: Set[str] = field(default_factory=set)
    # name -> set of let names it references (for DAG acyclicity)
    let_deps: Dict[str, Set[str]] = field(default_factory=dict)
    issues: List[Dict[str, Any]] = field(default_factory=list)

    def err(self, node: Optional[ast.AST], msg: str) -> None:
        ln = getattr(node, "lineno", None)
        self.issues.append({"line": ln, "msg": msg})


# ════════════════════════════════════════════════════════════════════
#  Top-level structural extraction
# ════════════════════════════════════════════════════════════════════

def _module_assignments(source: str, ctx: _Ctx) -> Dict[str, ast.AST]:
    """Parse the card module and return its top-level ``axes/lets/binds``.

    Rejects any top-level statement other than a bare docstring or a
    simple assignment to one of the three reserved names.
    """
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError as exc:
        raise CardCompileError([{"line": exc.lineno,
                                 "msg": f"syntax error: {exc.msg}"}])

    found: Dict[str, ast.AST] = {}
    for stmt in tree.body:
        # Allow a module docstring / bare string expressions.
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) \
                and isinstance(stmt.value.value, str):
            continue
        if not isinstance(stmt, ast.Assign):
            ctx.err(stmt, "only assignments to axes / lets / binds are "
                          "allowed at the top level")
            continue
        if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
            ctx.err(stmt, "assignment must target a single bare name")
            continue
        name = stmt.targets[0].id
        if name not in ("axes", "lets", "binds"):
            ctx.err(stmt, f"unexpected top-level name {name!r}; only "
                          f"axes / lets / binds are allowed")
            continue
        found[name] = stmt.value
    return found


def _extract_axes(node: ast.AST, ctx: _Ctx) -> List[str]:
    if not isinstance(node, ast.List):
        ctx.err(node, "axes must be a list of string handles")
        return []
    out: List[str] = []
    for el in node.elts:
        if isinstance(el, ast.Constant) and isinstance(el.value, str):
            out.append(el.value)
        else:
            ctx.err(el, "axes entries must be string literals")
    if len(set(out)) != len(out):
        ctx.err(node, "axes handles must be unique")
    return out


# ════════════════════════════════════════════════════════════════════
#  Expression walk  (lambda body -> residual-AST node)
# ════════════════════════════════════════════════════════════════════

def _lambda_body(node: ast.AST, ctx: _Ctx, *, where: str
                 ) -> Tuple[Optional[ast.AST], Optional[str]]:
    """Unwrap a ``lambda <param>: <expr>`` and return ``(body, param)``."""
    if not isinstance(node, ast.Lambda):
        ctx.err(node, f"{where} must be a lambda")
        return None, None
    args = node.args
    if (args.posonlyargs or args.kwonlyargs or args.vararg or args.kwarg
            or len(args.args) != 1 or args.defaults):
        ctx.err(node, f"{where} lambda must take exactly one parameter")
        return None, None
    return node.body, args.args[0].arg


def _expr(node: ast.AST, param: str, ctx: _Ctx,
          *, refs: Set[Tuple[str, str]]) -> Dict[str, Any]:
    """Walk one expression node against the allowlist -> residual node.

    ``param`` is the bound lambda parameter (``s`` for state, ``a`` for
    axes).  ``refs`` collects ``(kind, id)`` leaf references for later
    space / guard / rank analysis.
    """
    # ── numeric constant ──
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            ctx.err(node, f"only numeric constants allowed, got {node.value!r}")
            return {"const": 0.0}
        return {"const": float(node.value)}

    # ── unary +/- ──
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.USub):
            inner = _expr(node.operand, param, ctx, refs=refs)
            if "const" in inner:
                return {"const": -inner["const"]}
            return {"op": "*", "args": [{"const": -1.0}, inner]}
        if isinstance(node.op, ast.UAdd):
            return _expr(node.operand, param, ctx, refs=refs)
        ctx.err(node, "unsupported unary operator")
        return {"const": 0.0}

    # ── binary op ──
    if isinstance(node, ast.BinOp):
        sym = _BINOP_SYM.get(type(node.op))
        if sym is None:
            ctx.err(node, f"unsupported binary operator {type(node.op).__name__}")
            return {"const": 0.0}
        return {"op": sym, "args": [
            _expr(node.left, param, ctx, refs=refs),
            _expr(node.right, param, ctx, refs=refs),
        ]}

    # ── function call ──
    if isinstance(node, ast.Call):
        fn = _call_name(node.func)
        if fn is None or fn not in _FUNC_WHITELIST:
            ctx.err(node, f"call to non-whitelisted function "
                          f"{fn or '<expr>'!r}; allowed: "
                          f"{sorted(set(_FUNC_WHITELIST))}")
            return {"const": 0.0}
        if node.keywords:
            ctx.err(node, "keyword arguments are not allowed in calls")
        return {"op": _FUNC_WHITELIST[fn],
                "args": [_expr(a, param, ctx, refs=refs) for a in node.args]}

    # ── subscript: s.<ns>[id]  or  a[axis] ──
    if isinstance(node, ast.Subscript):
        return _subscript(node, param, ctx, refs=refs)

    # ── attribute: s.temperature / s.<let> ──
    if isinstance(node, ast.Attribute):
        return _attribute(node, param, ctx, refs=refs)

    if isinstance(node, ast.Name):
        ctx.err(node, f"bare name {node.id!r} is not addressable; use "
                      f"s.conc[...]/s.lnconc[...]/s.total[...]/s.species[...], "
                      f"s.<intensive>, s.<let>, or a[<axis>]")
        return {"const": 0.0}

    ctx.err(node, f"disallowed expression node {type(node).__name__}")
    return {"const": 0.0}


def _call_name(func: ast.AST) -> Optional[str]:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
            and func.value.id in ("math", "Math"):
        return func.attr
    return None


def _const_str_key(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _subscript(node: ast.Subscript, param: str, ctx: _Ctx,
               *, refs: Set[Tuple[str, str]]) -> Dict[str, Any]:
    key = _const_str_key(node.slice)
    base = node.value

    # a[<axis>]  — only valid for the axes parameter
    if isinstance(base, ast.Name):
        if base.id != param:
            ctx.err(node, f"unknown subscript base {base.id!r}")
            return {"const": 0.0}
        if param == "s":
            ctx.err(node, "state must be addressed via a sub-namespace "
                          "(s.conc/s.lnconc/s.total/s.species), not s[...]")
            return {"const": 0.0}
        if key is None:
            ctx.err(node, "axis subscript key must be a string literal")
            return {"const": 0.0}
        if key not in ctx.axes:
            ctx.err(node, f"axis {key!r} is not declared in `axes` "
                          f"({ctx.axes})")
        refs.add(("axis", key))
        return {"axis": key}

    # s.<ns>[<id>]
    if isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name) \
            and base.value.id == "s":
        ns = base.attr
        if ns not in _STATE_SUBNS:
            ctx.err(node, f"unknown state sub-namespace s.{ns}; allowed: "
                          f"{list(_STATE_SUBNS)}")
            return {"const": 0.0}
        if key is None:
            ctx.err(node, f"s.{ns}[...] key must be a string-literal id")
            return {"const": 0.0}
        if not _id_valid(ns, key, ctx):
            ctx.err(node, _id_error(ns, key, ctx))
        refs.add((ns, key))
        return {"ref": ns, "id": key}

    ctx.err(node, "unsupported subscript target")
    return {"const": 0.0}


def _attribute(node: ast.Attribute, param: str, ctx: _Ctx,
               *, refs: Set[Tuple[str, str]]) -> Dict[str, Any]:
    if not (isinstance(node.value, ast.Name) and node.value.id == "s"):
        ctx.err(node, "attribute access is only allowed on the state param `s`")
        return {"const": 0.0}
    if param != "s":
        ctx.err(node, f"`s` is not bound in this lambda (param is {param!r})")
        return {"const": 0.0}
    attr = node.attr
    if attr in ctx.intensives:
        refs.add(("intensive", attr))
        return {"ref": attr}
    if attr in _STATE_SUBNS:
        ctx.err(node, f"s.{attr} must be subscripted with an id, e.g. "
                      f"s.{attr}[\"<id>\"]")
        return {"const": 0.0}
    if attr in ctx.let_names:
        refs.add(("let", attr))
        return {"ref": "let", "name": attr}
    ctx.err(node, f"unknown reference s.{attr}; not an intensive "
                  f"{sorted(ctx.intensives)}, a state sub-namespace, or a "
                  f"declared let {sorted(ctx.let_names)}")
    return {"const": 0.0}


def _id_valid(ns: str, key: str, ctx: _Ctx) -> bool:
    if ns == "total":
        return key in ctx.components
    if ns == "species":
        return key in ctx.species
    # conc / lnconc accept either a component (basis) id or a species id
    return key in ctx.components or key in ctx.species


def _id_error(ns: str, key: str, ctx: _Ctx) -> str:
    if ns == "total":
        pool = sorted(ctx.components)
        what = "component/basis id"
    elif ns == "species":
        pool = sorted(ctx.species)
        what = "species id"
    else:
        pool = sorted(ctx.components | ctx.species)
        what = "component or species id"
    hint = _did_you_mean(key, pool)
    tail = f" (did you mean {hint!r}?)" if hint else ""
    show = pool[:24] + (["…"] if len(pool) > 24 else [])
    return (f"s.{ns}[{key!r}] is not a known {what}{tail}; "
            f"valid ids include: {show}")


def _did_you_mean(key: str, pool: Sequence[str]) -> Optional[str]:
    import difflib
    m = difflib.get_close_matches(key, list(pool), n=1, cutoff=0.6)
    return m[0] if m else None


# ════════════════════════════════════════════════════════════════════
#  Space + domain-guard analysis on emitted nodes
# ════════════════════════════════════════════════════════════════════

def _walk_refs(node: Dict[str, Any], let_asts: Dict[str, Dict[str, Any]],
               seen: Set[str]) -> Set[str]:
    """Collect the set of leaf ref-kinds in a node, resolving let-refs."""
    kinds: Set[str] = set()
    if "const" in node or "axis" in node:
        return kinds
    if "ref" in node:
        r = node["ref"]
        if r == "let":
            name = node["name"]
            if name in seen:
                return kinds
            seen.add(name)
            sub = let_asts.get(name)
            if sub is not None:
                kinds |= _walk_refs(sub, let_asts, seen)
            return kinds
        kinds.add(r)
        return kinds
    for a in node.get("args", []):
        kinds |= _walk_refs(a, let_asts, seen)
    return kinds


def _space_of(node: Dict[str, Any],
              let_asts: Dict[str, Dict[str, Any]]) -> str:
    """A node lives in ``log`` space iff every leaf ref is ``lnconc``."""
    kinds = _walk_refs(node, let_asts, set())
    if kinds and kinds <= {"lnconc"}:
        return "log"
    return "real"


def _domain_guard_of(node: Dict[str, Any]) -> Optional[str]:
    """Detect the guard a node needs.

    * a division whose *denominator* references a concentration-like
      quantity (conc / lnconc / total / species) -> ``denom>0``.  A
      division by a strictly-positive intensive (temperature,
      ionic_strength) needs no guard.
    * ``log`` / ``log10`` of an argument -> ``arg>0``.
    * ``sqrt`` of an argument -> ``arg>=0``.

    ``None`` when the node is guard-free.
    """
    if _needs_denom_guard(node):
        return "denom>0"
    if _contains_op(node, {"log", "log10"}):
        return "arg>0"
    if _contains_op(node, {"sqrt"}):
        return "arg>=0"
    return None


def _needs_denom_guard(node: Dict[str, Any]) -> bool:
    if "op" in node:
        if node["op"] == "/":
            args = node.get("args", [])
            if len(args) == 2 and _refs_conc_like(args[1]):
                return True
        return any(_needs_denom_guard(a) for a in node.get("args", []))
    return False


def _refs_conc_like(node: Dict[str, Any]) -> bool:
    if "ref" in node:
        return node["ref"] in ("conc", "lnconc", "total", "species")
    if "op" in node:
        return any(_refs_conc_like(a) for a in node.get("args", []))
    return False


def _contains_op(node: Dict[str, Any], ops: Set[str]) -> bool:
    if "op" in node:
        if node["op"] in ops:
            return True
        return any(_contains_op(a, ops) for a in node.get("args", []))
    return False


# ════════════════════════════════════════════════════════════════════
#  Numeric Jacobian-rank independence check
# ════════════════════════════════════════════════════════════════════

def _eval_node(node: Dict[str, Any], env: Dict[Tuple[str, str], float],
               let_vals: Dict[str, float], axis_vals: Dict[str, float],
               let_asts: Dict[str, Dict[str, Any]]) -> float:
    """Numerically evaluate a residual-AST node at a sample point.

    This is OUR ast (already allowlisted) — pure arithmetic over a Python
    dict of sample values.  Used only by the rank check.
    """
    if "const" in node:
        return float(node["const"])
    if "axis" in node:
        return axis_vals.get(node["axis"], 0.0)
    if "ref" in node:
        r = node["ref"]
        if r == "let":
            name = node["name"]
            return _eval_node(let_asts[name], env, let_vals, axis_vals, let_asts)
        if r == "conc":
            return math.exp(env[("lnconc", node["id"])])
        if r == "lnconc":
            return env[("lnconc", node["id"])]
        if r == "species":
            return env[("lnconc", node["id"])]
        if r == "total":
            return env[("total", node["id"])]
        # intensive
        return env[("intensive", r)]
    op = node["op"]
    a = [_eval_node(x, env, let_vals, axis_vals, let_asts)
         for x in node.get("args", [])]
    if op == "+":
        return a[0] + a[1]
    if op == "-":
        return a[0] - a[1] if len(a) == 2 else -a[0]
    if op == "*":
        return a[0] * a[1]
    if op == "/":
        return a[0] / a[1]
    if op == "**":
        return a[0] ** a[1]
    if op == "%":
        return a[0] % a[1]
    if op == "log":
        return math.log(a[0])
    if op == "log10":
        return math.log10(a[0])
    if op == "exp":
        return math.exp(a[0])
    if op == "sqrt":
        return math.sqrt(a[0])
    if op == "abs":
        return abs(a[0])
    if op == "pow":
        return a[0] ** a[1]
    if op == "sinh":
        return math.sinh(a[0])
    if op == "cosh":
        return math.cosh(a[0])
    if op == "tanh":
        return math.tanh(a[0])
    raise ValueError(f"unknown op {op}")


def _collect_unknowns(nodes: Sequence[Dict[str, Any]],
                      let_asts: Dict[str, Dict[str, Any]]
                      ) -> List[Tuple[str, str]]:
    out: Set[Tuple[str, str]] = set()

    def rec(n: Dict[str, Any], seen: Set[str]) -> None:
        if "const" in n or "axis" in n:
            return
        if "ref" in n:
            r = n["ref"]
            if r == "let":
                name = n["name"]
                if name in seen:
                    return
                seen.add(name)
                if name in let_asts:
                    rec(let_asts[name], seen)
                return
            if r in ("conc", "lnconc", "species"):
                out.add(("lnconc", n["id"]))
            elif r == "total":
                out.add(("total", n["id"]))
            else:
                out.add(("intensive", r))
            return
        for a in n.get("args", []):
            rec(a, seen)

    for nd in nodes:
        rec(nd, set())
    return sorted(out)


def _rank_check(eq_residuals: List[Dict[str, Any]],
                let_asts: Dict[str, Dict[str, Any]],
                axes: Sequence[str], ctx: _Ctx) -> None:
    """Assemble ∂(residual)/∂(unknown) at random feasible points and
    require full row rank == number of ``==`` binds (readme §4.4)."""
    if _np is None or not eq_residuals:
        return
    unknowns = _collect_unknowns(eq_residuals, let_asts)
    if not unknowns:
        return
    n_eq = len(eq_residuals)
    rng = _np.random.default_rng(12345)

    def sample_env() -> Dict[Tuple[str, str], float]:
        env: Dict[Tuple[str, str], float] = {}
        for kind, ident in unknowns:
            if kind == "lnconc":
                env[(kind, ident)] = float(rng.uniform(-12.0, -1.0))
            elif kind == "total":
                env[(kind, ident)] = float(rng.uniform(1e-4, 1e-1))
            else:  # intensive
                if ident == "temperature":
                    env[(kind, ident)] = float(rng.uniform(280.0, 360.0))
                elif ident == "ionic_strength":
                    env[(kind, ident)] = float(rng.uniform(0.01, 0.5))
                elif ident == "E_V":
                    env[(kind, ident)] = float(rng.uniform(-1.0, 1.5))
                else:  # pH
                    env[(kind, ident)] = float(rng.uniform(1.0, 13.0))
        return env

    axis_vals = {ax: 0.0 for ax in axes}
    h = 1e-6
    rank = -1
    for _attempt in range(6):
        env = sample_env()
        J = _np.zeros((n_eq, len(unknowns)))
        ok = True
        try:
            for i, res in enumerate(eq_residuals):
                for j, var in enumerate(unknowns):
                    base = env[var]
                    env[var] = base + h
                    fp = _eval_node(res, env, {}, axis_vals, let_asts)
                    env[var] = base - h
                    fm = _eval_node(res, env, {}, axis_vals, let_asts)
                    env[var] = base
                    J[i, j] = (fp - fm) / (2 * h)
        except (ValueError, ZeroDivisionError, OverflowError):
            ok = False
        if not ok:
            continue
        rank = int(_np.linalg.matrix_rank(J, tol=1e-9))
        break
    if rank < 0:
        ctx.issues.append({"line": None,
                           "msg": "could not evaluate the constraint set at a "
                                  "feasible sample point (check domain guards)"})
        return
    if rank < n_eq:
        ctx.issues.append({"line": None,
                           "msg": f"the {n_eq} equality binds are not "
                                  f"independent (Jacobian rank {rank} < "
                                  f"{n_eq}); some binds are redundant or "
                                  f"contradictory over the unknowns "
                                  f"{[f'{k}:{i}' for k, i in unknowns]}"})


# ════════════════════════════════════════════════════════════════════
#  lets / binds compilation
# ════════════════════════════════════════════════════════════════════

def _compile_lets(node: ast.AST, ctx: _Ctx
                  ) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    """Compile the ``lets`` dict; returns (emitted_lets, name->ast map)."""
    emitted: Dict[str, Any] = {}
    let_asts: Dict[str, Dict[str, Any]] = {}
    if not isinstance(node, ast.Dict):
        ctx.err(node, "lets must be a dict of name -> lambda")
        return emitted, let_asts

    # Pre-register all let names so intra-let references resolve; the DAG
    # check below catches cycles.
    names_in_order: List[Tuple[str, ast.AST]] = []
    for k, v in zip(node.keys, node.values):
        name = _const_str_key(k)
        if name is None:
            ctx.err(k, "let keys must be string-literal names")
            continue
        if not name.isidentifier():
            ctx.err(k, f"let name {name!r} must be a valid identifier")
            continue
        ctx.let_names.add(name)
        names_in_order.append((name, v))

    for name, v in names_in_order:
        body, param = _lambda_body(v, ctx, where=f"let {name!r}")
        if body is None:
            continue
        if param != "s":
            ctx.err(v, f"let {name!r} lambda parameter must be `s`")
        refs: Set[Tuple[str, str]] = set()
        node_ast = _expr(body, param or "s", ctx, refs=refs)
        let_asts[name] = node_ast
        ctx.let_deps[name] = {r[1] for r in refs if r[0] == "let"}

    # DAG acyclicity (readme §4.2).
    cyc = _find_cycle(ctx.let_deps)
    if cyc:
        ctx.err(node, f"lets form a reference cycle: {' -> '.join(cyc)}")

    # Now that the DAG is known, compute space + guard per let.
    for name, _v in names_in_order:
        if name not in let_asts:
            continue
        spc = _space_of(let_asts[name], let_asts)
        entry: Dict[str, Any] = {"space": spc, "ast": let_asts[name]}
        guard = _domain_guard_of(let_asts[name])
        if guard:
            entry["domain_guard"] = guard
        emitted[name] = entry
    return emitted, let_asts


def _find_cycle(deps: Dict[str, Set[str]]) -> Optional[List[str]]:
    WHITE, GREY, BLACK = 0, 1, 2
    color: Dict[str, int] = {n: WHITE for n in deps}
    stack: List[str] = []

    def dfs(n: str) -> Optional[List[str]]:
        color[n] = GREY
        stack.append(n)
        for m in deps.get(n, ()):
            if m not in color:
                continue
            if color[m] == GREY:
                i = stack.index(m)
                return stack[i:] + [m]
            if color[m] == WHITE:
                r = dfs(m)
                if r:
                    return r
        stack.pop()
        color[n] = BLACK
        return None

    for n in deps:
        if color[n] == WHITE:
            r = dfs(n)
            if r:
                return r
    return None


def _compile_binds(node: ast.AST, ctx: _Ctx,
                   let_asts: Dict[str, Dict[str, Any]]
                   ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Compile ``binds``; returns (emitted_binds, equality_residual_nodes)."""
    emitted: List[Dict[str, Any]] = []
    eq_residuals: List[Dict[str, Any]] = []
    if not isinstance(node, ast.List):
        ctx.err(node, "binds must be a list of bind dicts")
        return emitted, eq_residuals

    seen_ids: Set[str] = set()
    for entry in node.elts:
        if not isinstance(entry, ast.Dict):
            ctx.err(entry, "each bind must be a dict")
            continue
        fields: Dict[str, ast.AST] = {}
        for k, v in zip(entry.keys, entry.values):
            key = _const_str_key(k)
            if key is None:
                ctx.err(k, "bind keys must be string literals")
                continue
            fields[key] = v

        bid_node = fields.get("id")
        bid = _const_str_key(bid_node) if bid_node is not None else None
        if not bid:
            ctx.err(entry, "bind is missing a string 'id'")
            bid = f"_bind_{len(emitted)}"
        if bid in seen_ids:
            ctx.err(entry, f"duplicate bind id {bid!r}")
        seen_ids.add(bid)

        op = "=="
        if "op" in fields:
            op_s = _const_str_key(fields["op"])
            if op_s not in _VALID_OPS:
                ctx.err(fields["op"], f"bind {bid!r}: op must be one of "
                                      f"{list(_VALID_OPS)}")
            else:
                op = op_s

        if "lhs" not in fields:
            ctx.err(entry, f"bind {bid!r} is missing 'lhs'")
            continue
        if "rhs" not in fields:
            ctx.err(entry, f"bind {bid!r} is missing 'rhs'")
            continue

        lhs_refs: Set[Tuple[str, str]] = set()
        lhs_body, lhs_param = _lambda_body(fields["lhs"], ctx,
                                           where=f"bind {bid!r} lhs")
        if lhs_body is None:
            continue
        if lhs_param != "s":
            ctx.err(fields["lhs"], f"bind {bid!r} lhs lambda parameter must be `s`")
        lhs_node = _expr(lhs_body, lhs_param or "s", ctx, refs=lhs_refs)

        rhs_refs: Set[Tuple[str, str]] = set()
        rhs_node = _compile_rhs(fields["rhs"], ctx, bid, refs=rhs_refs)

        bind_obj: Dict[str, Any] = {
            "id": bid,
            "op": op,
            "lhs": lhs_node,
            "rhs": rhs_node,
            "residual": "lhs - rhs",
        }
        guard = _bind_guard(lhs_node, rhs_node, lhs_refs, rhs_refs, let_asts)
        if guard:
            bind_obj["domain_guard"] = guard
        if op != "==":
            bind_obj["kind"] = "feasibility"
        else:
            eq_residuals.append({"op": "-", "args": [lhs_node, rhs_node]})
        emitted.append(bind_obj)

    return emitted, eq_residuals


def _compile_rhs(node: ast.AST, ctx: _Ctx, bid: str,
                 *, refs: Set[Tuple[str, str]]) -> Dict[str, Any]:
    """The rhs is either a bare numeric constant expression or a lambda."""
    if isinstance(node, ast.Lambda):
        body, param = _lambda_body(node, ctx, where=f"bind {bid!r} rhs")
        if body is None:
            return {"const": 0.0}
        if param not in ("s", "a"):
            ctx.err(node, f"bind {bid!r} rhs lambda parameter must be `s` or `a`")
            param = param or "a"
        return _expr(body, param, ctx, refs=refs)
    # Bare constant (possibly an arithmetic of constants) — compile then fold.
    folded = _expr(node, "s", ctx, refs=refs)
    return _fold_const(folded)


def _fold_const(node: Dict[str, Any]) -> Dict[str, Any]:
    if "op" in node:
        args = [_fold_const(a) for a in node.get("args", [])]
        if all("const" in a for a in args):
            try:
                val = _eval_node({"op": node["op"], "args": args},
                                 {}, {}, {}, {})
                return {"const": float(val)}
            except Exception:
                return {"op": node["op"], "args": args}
        return {"op": node["op"], "args": args}
    return node


def _bind_guard(lhs: Dict[str, Any], rhs: Dict[str, Any],
                lhs_refs: Set[Tuple[str, str]], rhs_refs: Set[Tuple[str, str]],
                let_asts: Dict[str, Dict[str, Any]]) -> Optional[str]:
    # If the lhs is a single let-ref to a guarded let, inherit it.
    for side in (lhs, rhs):
        if side.get("ref") == "let":
            sub = let_asts.get(side["name"])
            if sub is not None and _domain_guard_of(sub):
                return f"from:{side['name']}"
    # Otherwise a direct guard need on either side.
    direct = _domain_guard_of(lhs) or _domain_guard_of(rhs)
    return direct


# ════════════════════════════════════════════════════════════════════
#  Public entry point
# ════════════════════════════════════════════════════════════════════

def compile_card(
    source: str,
    *,
    components: Sequence[str],
    species: Sequence[str],
    intensives: Optional[Sequence[str]] = None,
    expected_K: Optional[int] = None,
    charge_balance_enforced: bool = False,
    source_name: str = "card.py",
    normalize: bool = True,
) -> Dict[str, Any]:
    """Compile a constraint card into the ``lc3_2.v1`` spec dict.

    Parameters
    ----------
    source
        The agent-emitted card module text (axes / lets / binds).
    components
        Valid component/basis ids (addressable by ``s.total[...]`` and
        ``s.conc/s.lnconc[...]``).
    species
        Valid dependent-species ids (addressable by ``s.species[...]`` and
        ``s.conc/s.lnconc[...]``).
    intensives
        Reserved intensive names (defaults to temperature / ionic_strength /
        pH).
    expected_K
        If given, the number of degrees of freedom the physics leaves open;
        the count of ``==`` binds must equal it.
    charge_balance_enforced
        Recorded into ``dof`` and used for the pH-binding rule.

    Raises
    ------
    CardCompileError
        With a list of located ``issues`` when the card is invalid.
    """
    ctx = _Ctx(
        components=set(components),
        species=set(species),
        intensives=set(intensives) if intensives else set(_INTENSIVES),
    )

    # Self-heal the surface details the LLM reliably hallucinates (handle
    # spellings, oxidation-state tokens, np.* functions, "=" ops, ...)
    # *before* the strict allowlist/id walk.  Line numbers are preserved,
    # and a already-canonical card is returned unchanged, so this only
    # ever rescues cards the compiler would otherwise reject.
    if normalize:
        try:
            from constr_normalizer import normalize_card_source  # type: ignore
        except Exception:                                        # pragma: no cover
            try:
                from .....NIST_SRD46_normalizer_helpers.constr_card_normalizer.constr_normalizer import (  # type: ignore
                    normalize_card_source,
                )
            except Exception:
                normalize_card_source = None                     # type: ignore
        if normalize_card_source is not None:
            try:
                source = normalize_card_source(
                    source,
                    components=components,
                    species=species,
                    intensives=intensives or _INTENSIVES,
                ).source
            except Exception:                                    # pragma: no cover
                pass        # normalization must never break compilation

    found = _module_assignments(source, ctx)
    for required in ("axes", "lets", "binds"):
        if required not in found:
            ctx.err(None, f"card must define a top-level `{required}`")
    if ctx.issues and ("axes" not in found or "binds" not in found):
        raise CardCompileError(ctx.issues)

    ctx.axes = _extract_axes(found["axes"], ctx) if "axes" in found else []
    emitted_lets, let_asts = (_compile_lets(found["lets"], ctx)
                              if "lets" in found else ({}, {}))
    emitted_binds, eq_residuals = _compile_binds(found["binds"], ctx, let_asts)

    # DOF count == K (readme §4.3).
    k_count = len(eq_residuals)
    if expected_K is not None and k_count != expected_K:
        ctx.issues.append({"line": None,
                           "msg": f"DOF mismatch: found {k_count} equality "
                                  f"bind(s) but the physics leaves K="
                                  f"{expected_K} degree(s) of freedom to "
                                  f"close; add or remove '==' binds"})

    # pH-binding rule (readme §4.3).
    if charge_balance_enforced:
        if _binds_touch_ph(eq_residuals, let_asts):
            ctx.issues.append({"line": None,
                               "msg": "charge balance is enforced by the "
                                      "physics so pH is internal; remove the "
                                      "bind that pins pH / conc['H']"})

    # Numeric independence (readme §4.4).
    _rank_check(eq_residuals, let_asts, ctx.axes, ctx)

    if ctx.issues:
        raise CardCompileError(ctx.issues)

    spec: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source_card": source_name,
        "axes": ctx.axes,
        "dof": {"K": k_count,
                "charge_balance_enforced": bool(charge_balance_enforced)},
        "lets": emitted_lets,
        "binds": emitted_binds,
    }
    return spec


def _binds_touch_ph(eq_residuals: Sequence[Dict[str, Any]],
                    let_asts: Dict[str, Dict[str, Any]]) -> bool:
    for res in eq_residuals:
        kinds = _walk_refs(res, let_asts, set())
        # pH is referenced either as the intensive 'pH' or conc['H'].
        if "pH" in kinds:
            return True
    # also catch direct conc['H'] usage
    def has_h(n: Dict[str, Any], seen: Set[str]) -> bool:
        if "ref" in n:
            if n["ref"] in ("conc", "lnconc") and n.get("id") == "H":
                return True
            if n["ref"] == "let":
                nm = n["name"]
                if nm in seen:
                    return False
                seen.add(nm)
                sub = let_asts.get(nm)
                return has_h(sub, seen) if sub else False
            return False
        return any(has_h(a, seen) for a in n.get("args", []))
    return any(has_h(res, set()) for res in eq_residuals)
