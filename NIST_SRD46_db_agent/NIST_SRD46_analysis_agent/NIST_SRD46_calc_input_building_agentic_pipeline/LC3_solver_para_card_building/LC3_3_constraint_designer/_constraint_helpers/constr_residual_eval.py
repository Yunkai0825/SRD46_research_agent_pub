"""lc3_2 residual-spec evaluator — the solver-facing kernel.

The ``lc3_2.v1`` spec emitted by :mod:`lc3_2_card_compiler` describes the
*extra* equations the augmented Newton solver must satisfy on top of the
thermodynamic mass-balance rows.  Each ``==`` bind contributes one
residual row ``r = lhs - rhs`` over the solver state.

This module turns that JSON into a numeric ``(residuals, jacobian)``
callable.  The Jacobian is **analytic**: a single forward-mode pass
carries each node's value together with its gradient w.r.t. the unknown
vector, so the solver never needs finite differences for these rows.

State / unknown model (mirrors the compiler's ``_collect_unknowns``):

* ``("lnconc", id)``  — log-concentration unknown ``x``.  ``s.lnconc[id]``
  and ``s.species[id]`` read ``x`` directly; ``s.conc[id]`` reads
  ``exp(x)``.
* ``("total", id)``   — analytic total for a component.
* ``("intensive", name)`` — ``temperature`` / ``ionic_strength`` / ``pH``.

``axes`` are *inputs* (LC3_3 attaches a grid); they are held fixed per
grid point and never differentiated.

No ``eval``/``exec`` is used: the spec is a plain dict of allow-listed
AST nodes and we walk it.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence, Tuple

try:
    import numpy as _np
except Exception:                       # pragma: no cover
    _np = None

Unknown = Tuple[str, str]               # (kind, id)
Node = Dict[str, Any]


# ════════════════════════════════════════════════════════════════════
#  Unknown collection (mirror of compiler._collect_unknowns)
# ════════════════════════════════════════════════════════════════════

def _collect_unknowns(nodes: Sequence[Node],
                      let_asts: Dict[str, Node]) -> List[Unknown]:
    out: set[Unknown] = set()

    def rec(n: Node, seen: set[str]) -> None:
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


# ════════════════════════════════════════════════════════════════════
#  Forward-mode value+gradient evaluation
# ════════════════════════════════════════════════════════════════════

class _Dual:
    """A value paired with its gradient over the unknown vector."""
    __slots__ = ("v", "g")

    def __init__(self, v: float, g: "_np.ndarray"):
        self.v = v
        self.g = g


class ResidualSystem:
    """Numeric residual + analytic Jacobian for the ``==`` binds.

    Parameters
    ----------
    spec : dict
        A ``lc3_2.v1`` spec (output of ``compile_card``).
    """

    def __init__(self, spec: Dict[str, Any]):
        if _np is None:                 # pragma: no cover
            raise RuntimeError("numpy is required for ResidualSystem")
        self.spec = spec
        self.let_asts: Dict[str, Node] = {
            name: body["ast"] for name, body in spec.get("lets", {}).items()
        }
        self.eq_binds: List[Dict[str, Any]] = [
            b for b in spec.get("binds", []) if b.get("op", "==") == "=="
        ]
        residual_nodes = [
            {"op": "-", "args": [b["lhs"], b["rhs"]]} for b in self.eq_binds
        ]
        self.residual_nodes = residual_nodes
        self.bind_ids = [b["id"] for b in self.eq_binds]
        self.unknowns: List[Unknown] = _collect_unknowns(
            [n for b in self.eq_binds for n in (b["lhs"], b["rhs"])],
            self.let_asts,
        )
        self.index: Dict[Unknown, int] = {
            u: i for i, u in enumerate(self.unknowns)
        }
        self.n = len(self.unknowns)
        self.m = len(self.eq_binds)

    # ── public API ──────────────────────────────────────────────────
    def state_vector(self, state: Dict[Unknown, float]) -> "_np.ndarray":
        """Pack a ``{(kind,id): value}`` dict into the ordered vector."""
        x = _np.zeros(self.n)
        for u, i in self.index.items():
            if u not in state:
                raise KeyError(f"state is missing unknown {u}")
            x[i] = state[u]
        return x

    def residuals(self, x: "_np.ndarray",
                  axes: Dict[str, float]) -> "_np.ndarray":
        f = _np.empty(self.m)
        for k, node in enumerate(self.residual_nodes):
            f[k] = self._eval(node, x, axes).v
        return f

    def residual_and_jacobian(
        self, x: "_np.ndarray", axes: Dict[str, float]
    ) -> Tuple["_np.ndarray", "_np.ndarray"]:
        f = _np.empty(self.m)
        J = _np.zeros((self.m, self.n))
        for k, node in enumerate(self.residual_nodes):
            d = self._eval(node, x, axes)
            f[k] = d.v
            J[k, :] = d.g
        return f, J

    # ── forward-mode core ───────────────────────────────────────────
    def _eval(self, node: Node, x: "_np.ndarray",
              axes: Dict[str, float]) -> _Dual:
        if "const" in node:
            return _Dual(float(node["const"]), _np.zeros(self.n))
        if "axis" in node:
            return _Dual(float(axes.get(node["axis"], 0.0)), _np.zeros(self.n))
        if "ref" in node:
            return self._eval_ref(node, x, axes)
        return self._eval_op(node, x, axes)

    def _seed(self, u: Unknown) -> "_np.ndarray":
        g = _np.zeros(self.n)
        g[self.index[u]] = 1.0
        return g

    def _eval_ref(self, node: Node, x: "_np.ndarray",
                  axes: Dict[str, float]) -> _Dual:
        r = node["ref"]
        if r == "let":
            return self._eval(self.let_asts[node["name"]], x, axes)
        if r == "lnconc" or r == "species":
            u = ("lnconc", node["id"])
            return _Dual(x[self.index[u]], self._seed(u))
        if r == "conc":
            u = ("lnconc", node["id"])
            v = math.exp(x[self.index[u]])
            return _Dual(v, v * self._seed(u))      # d/dx exp(x) = exp(x)
        if r == "total":
            u = ("total", node["id"])
            return _Dual(x[self.index[u]], self._seed(u))
        # intensive
        u = ("intensive", r)
        return _Dual(x[self.index[u]], self._seed(u))

    def _eval_op(self, node: Node, x: "_np.ndarray",
                 axes: Dict[str, float]) -> _Dual:
        op = node["op"]
        a = [self._eval(arg, x, axes) for arg in node.get("args", [])]
        if op == "+":
            return _Dual(a[0].v + a[1].v, a[0].g + a[1].g)
        if op == "-":
            if len(a) == 1:
                return _Dual(-a[0].v, -a[0].g)
            return _Dual(a[0].v - a[1].v, a[0].g - a[1].g)
        if op == "*":
            return _Dual(a[0].v * a[1].v, a[0].v * a[1].g + a[1].v * a[0].g)
        if op == "/":
            v0, v1 = a[0].v, a[1].v
            return _Dual(v0 / v1, (a[0].g * v1 - v0 * a[1].g) / (v1 * v1))
        if op == "**" or op == "pow":
            return self._pow(a[0], a[1])
        if op == "%":
            # derivative w.r.t. the dividend only (divisor treated piecewise)
            return _Dual(math.fmod(a[0].v, a[1].v), a[0].g.copy())
        if op == "log":
            return _Dual(math.log(a[0].v), a[0].g / a[0].v)
        if op == "log10":
            return _Dual(math.log10(a[0].v), a[0].g / (a[0].v * math.log(10.0)))
        if op == "exp":
            e = math.exp(a[0].v)
            return _Dual(e, e * a[0].g)
        if op == "sqrt":
            s = math.sqrt(a[0].v)
            return _Dual(s, a[0].g / (2.0 * s))
        if op == "abs":
            sign = 1.0 if a[0].v >= 0 else -1.0
            return _Dual(abs(a[0].v), sign * a[0].g)
        if op == "sinh":
            return _Dual(math.sinh(a[0].v), math.cosh(a[0].v) * a[0].g)
        if op == "cosh":
            return _Dual(math.cosh(a[0].v), math.sinh(a[0].v) * a[0].g)
        if op == "tanh":
            t = math.tanh(a[0].v)
            return _Dual(t, (1.0 - t * t) * a[0].g)
        raise ValueError(f"unknown op {op!r}")

    @staticmethod
    def _pow(base: _Dual, expo: _Dual) -> _Dual:
        b, e = base.v, expo.v
        v = b ** e
        # d/dx b^e = e*b^(e-1)*b' + b^e*ln(b)*e'
        g = e * (b ** (e - 1.0)) * base.g
        if _np.any(expo.g != 0.0) and b > 0.0:
            g = g + v * math.log(b) * expo.g
        return _Dual(v, g)


def build_residual_system(spec: Dict[str, Any]) -> ResidualSystem:
    """Convenience factory mirroring the compiler's public surface."""
    return ResidualSystem(spec)
