"""
sweep_constraints_expander.py
=============================
Translate the user-facing dict-shape ``sweep_constraints`` block from
calc-input JSON into the canonical list-of-bindings consumed by
:func:`constraint_compiler.compile_constraints`.

This module is a thin formatter only.  All semantic validation
(LHS in catalog, cycles, AST whitelist, Tier-2 routing, composite-DOF
flattening) lives in ``constraint_compiler``.

Input shape (excerpt)::

    "sweep_constraints": {
      "pH_constr":             "pH_axis"|"pH_fixed"|"pH_freeform",
      "redox_constr":          "E_V_axis"|"E_V_fixed"|"E_V_freeform"|"E_V_solve"|"excluded",
      "temperature_constr":    "temperature_fixed"|"temperature_axis",
      "ionic_strength_constr": "ionic_strength_fixed"|"ionic_strength_auto"|"ionic_strength_axis",
      "activity_model": "ideal"|"davies",
      "solids":         "include"|"exclude",
      "[<element_or_ligand>]_constr": "[<token>]_tot_fixed"|"[<token>]_tot_axis"|"[<token>]_tot_freeform",
      "initial_condition": { ... composite [value, unit] entries
                              (or bare scalars in canonical units) ... },
      "custom_freeform":   { "<eq-name>": "<lhs> = <rhs>" }
    }

Output: ``list[dict | str]`` ready for ``compile_constraints``.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Tuple

from .initial_condition_normalizer import (
    InitialConditionUnitError,
    normalize_initial_condition,
)


class SweepConstraintsExpandError(ValueError):
    """Raised when the dict-shape ``sweep_constraints`` cannot be expanded."""


# Toggle key -> (DOF root used in initial_condition, allowed values)
_INTENSIVE_TOGGLES = {
    "pH_constr":             ("pH",
                              {"pH_axis", "pH_fixed", "pH_freeform"}),
    "redox_constr":          ("E_V",
                              {"E_V_axis", "E_V_fixed",
                               "E_V_freeform", "E_V_solve", "excluded"}),
    "temperature_constr":    ("temperature",
                              {"temperature_axis",
                               "temperature_fixed",
                               "temperature_freeform"}),
    "ionic_strength_constr": ("ionic_strength",
                              {"ionic_strength_axis",
                               "ionic_strength_fixed",
                               "ionic_strength_auto",
                               "ionic_strength_freeform"}),
}

_DIRECT_VALUE_KEYS = {
    "activity_model": {"ideal", "davies"},
    "solids":         {"include", "exclude"},
}

_BRACKET_CONSTR_RE = re.compile(r"^\[([A-Za-z0-9_+\-$.]+)\]_constr$")
_BRACKET_TOKEN_RE  = re.compile(r"^\[([A-Za-z0-9_+\-$.]+)\]_(.+)$")
_META_KEYS = {"initial_condition", "custom_freeform"}


def _iter_constr_tokens(raw_value: Any, key_for_err: str) -> List[str]:
    """Return the list of token strings for one ``_constr`` value.

    Accepts EITHER:
      * a plain string (single token), or
      * a JSON object like ``{"constr_1": "<tok>", "constr_2": "<tok>"}``
        whose values are concatenated in key order. Keys must match
        ``constr_<int>`` so the user intent (and ordering) is explicit.
    """
    if isinstance(raw_value, str):
        return [raw_value.strip()]
    if isinstance(raw_value, Mapping):
        out: List[Tuple[int, str]] = []
        for k, v in raw_value.items():
            if not isinstance(k, str) or not k.startswith("constr_"):
                raise SweepConstraintsExpandError(
                    f"{key_for_err}: object-form keys must look like "
                    f"'constr_1', 'constr_2', ...; got {k!r}")
            try:
                idx = int(k[len("constr_"):])
            except ValueError:
                raise SweepConstraintsExpandError(
                    f"{key_for_err}: object-form key {k!r} must be "
                    f"'constr_<integer>'")
            if not isinstance(v, str):
                raise SweepConstraintsExpandError(
                    f"{key_for_err}[{k!r}] must be a string token")
            out.append((idx, v.strip()))
        out.sort(key=lambda t: t[0])
        return [s for _, s in out]
    raise SweepConstraintsExpandError(
        f"{key_for_err}: value must be a string or "
        f"object-of-strings; got {type(raw_value).__name__}")


def expand_sweep_constraints(raw: Mapping[str, Any]) -> List[Any]:
    """Expand the dict-shape ``sweep_constraints`` into a bindings list.

    Missing or ``None`` ``sweep_constraints`` -> ``[]``.
    """
    sc = raw.get("sweep_constraints")
    if sc is None:
        return []
    if not isinstance(sc, Mapping):
        raise SweepConstraintsExpandError(
            "'sweep_constraints' must be a JSON object")

    ic = sc.get("initial_condition") or {}
    if not isinstance(ic, Mapping):
        raise SweepConstraintsExpandError(
            "'sweep_constraints.initial_condition' must be a JSON object")

    # Normalise every initial_condition entry into canonical units.
    sys_cat_pre = raw.get("system_catalog") or {}
    fvars_pre = (sys_cat_pre.get("freeform_vars_define") or {}
                 ) if isinstance(sys_cat_pre, Mapping) else {}
    try:
        ic = normalize_initial_condition(ic, fvars_pre)
    except InitialConditionUnitError as exc:
        raise SweepConstraintsExpandError(str(exc)) from exc

    bindings: List[Any] = []

    # ── Intensive toggles ───────────────────────────────────────────
    for tkey, (dof, allowed) in _INTENSIVE_TOGGLES.items():
        if tkey not in sc:
            continue
        tokens = _iter_constr_tokens(sc[tkey], tkey)
        for val in tokens:
            if val not in allowed:
                raise SweepConstraintsExpandError(
                    f"'{tkey}' token must be one of {sorted(allowed)}; "
                    f"got {val!r}")

            # ``*_axis`` and ``*_freeform`` emit no binding from the toggle
            # itself -- the axis or the custom_freeform equation supplies it.
            if val.endswith("_axis") or val.endswith("_freeform"):
                if dof == "E_V":
                    bindings.append({"redox": "include"})
                continue

            if dof == "pH":            # pH_fixed
                if "pH" not in ic:
                    raise SweepConstraintsExpandError(
                        "'pH_fixed' requires initial_condition.pH")
                bindings.append({"pH": float(ic["pH"])})

            elif dof == "E_V":         # E_V_fixed | E_V_solve | excluded
                if val == "excluded":
                    bindings.append({"redox": "exclude"})
                elif val == "E_V_solve":
                    bindings.append({"redox": "solve"})
                else:
                    bindings.append({"redox": "include"})
                    if "E_V" not in ic:
                        raise SweepConstraintsExpandError(
                            "'E_V_fixed' requires initial_condition.E_V")
                    bindings.append({"E_V": float(ic["E_V"])})

            elif dof == "temperature":  # temperature_fixed
                if "temperature" in ic:
                    v = ic["temperature"]
                    if isinstance(v, str) and v.lower() == "auto":
                        raise SweepConstraintsExpandError(
                            "'temperature_fixed' requires a numeric "
                            "initial_condition.temperature (got 'auto'); "
                            "use temperature_constr='temperature_auto' instead")
                    bindings.append({"temperature":
                                     {"mode": "fixed", "value_K": float(v)}})
                else:
                    raise SweepConstraintsExpandError(
                        "'temperature_fixed' requires initial_condition.temperature "
                        "(scalar in K)")

            elif dof == "ionic_strength":  # ionic_strength_fixed | _auto
                if val == "ionic_strength_auto":
                    bindings.append({"ionic_strength": {"mode": "auto"}})
                else:
                    if "ionic_strength" not in ic:
                        raise SweepConstraintsExpandError(
                            "'ionic_strength_fixed' requires "
                            "initial_condition.ionic_strength (mol/L)")
                    v = ic["ionic_strength"]
                    if isinstance(v, str) and v.lower() == "auto":
                        raise SweepConstraintsExpandError(
                            "'ionic_strength_fixed' got 'auto' for "
                            "initial_condition.ionic_strength; use "
                            "ionic_strength_constr='ionic_strength_auto' instead")
                    bindings.append({"ionic_strength":
                                     {"mode": "fixed", "value_M": float(v)}})

    # ── Direct enum values (activity_model / solids) ────────────────
    for tkey, allowed in _DIRECT_VALUE_KEYS.items():
        if tkey not in sc:
            continue
        val = str(sc[tkey])
        if val not in allowed:
            raise SweepConstraintsExpandError(
                f"'{tkey}' must be one of {sorted(allowed)}; got {val!r}")
        bindings.append({tkey: val})

    # ── Bracket toggles: [X]_constr ─────────────────────────────────
    seen: set = set()
    for k, v in sc.items():
        if (k in _INTENSIVE_TOGGLES or k in _DIRECT_VALUE_KEYS
                or k in _META_KEYS):
            continue
        m = _BRACKET_CONSTR_RE.match(k)
        if m is None:
            raise SweepConstraintsExpandError(
                f"unrecognised key in sweep_constraints: {k!r}")
        token = m.group(1)
        if token in seen:
            raise SweepConstraintsExpandError(
                f"duplicate '_constr' entry for token {token!r}")
        seen.add(token)
        for sub in _iter_constr_tokens(v, k):
            tm = _BRACKET_TOKEN_RE.match(sub)
            if tm is None:
                raise SweepConstraintsExpandError(
                    f"unrecognised value for {k!r}: {sub!r} "
                    f"(expected '[<id>]_<suffix>')")
            sub_target, sub_suffix = tm.group(1), tm.group(2)
            if sub_suffix == "tot_fixed":
                ic_key = f"[{sub_target}]_total"
                if ic_key not in ic:
                    raise SweepConstraintsExpandError(
                        f"'{k}' contains '{sub}' which requires "
                        f"initial_condition[{ic_key!r}]")
                bindings.append({ic_key: float(ic[ic_key])})
            elif sub_suffix == "tot_axis":
                ic_key = f"[{sub_target}]_total"
                axis_names = {
                    str(axis.get("name"))
                    for axis in (raw.get("sweep_axes") or [])
                    if isinstance(axis, Mapping) and axis.get("name")
                }
                candidates = [
                    name for name in
                    (sub, sub_target, ic_key, f"[{sub_target}]_tot_axis")
                    if name in axis_names
                ]
                candidates = list(dict.fromkeys(candidates))
                if len(candidates) != 1:
                    raise SweepConstraintsExpandError(
                        f"'{k}' contains '{sub}' but its total-axis binding "
                        f"is {'missing' if not candidates else 'ambiguous'}; "
                        f"declare exactly one matching sweep axis (found "
                        f"{candidates})")
                bindings.append({ic_key: candidates[0]})
            elif sub_suffix in ("tot_freeform", "freeform"):
                # The custom_freeform equation supplies this binding.
                continue
            else:
                raise SweepConstraintsExpandError(
                    f"unrecognised value for {k!r}: {sub!r} "
                    f"(unknown suffix {sub_suffix!r})")

    # ── Custom freeform pool: pass each "<lhs> = <rhs>" through ─────
    cf = sc.get("custom_freeform") or {}
    if cf and not isinstance(cf, Mapping):
        raise SweepConstraintsExpandError(
            "'sweep_constraints.custom_freeform' must be a JSON object")
    for eq_name, eq_str in cf.items():
        if not isinstance(eq_str, str):
            raise SweepConstraintsExpandError(
                f"custom_freeform[{eq_name!r}] must be a string '<lhs> = <rhs>'")
        bindings.append(eq_str)

    # ── Freeform-variable scalars supplied via initial_condition ────
    # When a custom_freeform equation references an identifier that is
    # neither a DOF nor a sweep axis, the identifier MUST be declared
    # in ``system_catalog.freeform_vars_define`` (enforced by the
    # compiler). If such a variable is also given a numeric value in
    # ``initial_condition``, emit a binding so the compiler treats it
    # as a constant for evaluation.
    sys_cat = raw.get("system_catalog") or {}
    fvars = (sys_cat.get("freeform_vars_define") or {}) if isinstance(sys_cat, Mapping) else {}
    axis_names = {a.get("name") for a in (raw.get("sweep_axes") or [])
                  if isinstance(a, Mapping)}
    for var_name in fvars:
        if not isinstance(var_name, str):
            continue
        if var_name in axis_names:
            continue                # supplied by the sweep axis
        if var_name in ic:
            try:
                bindings.append({var_name: float(ic[var_name])})
            except (TypeError, ValueError):
                raise SweepConstraintsExpandError(
                    f"initial_condition[{var_name!r}] for declared "
                    f"freeform variable must be numeric; got {ic[var_name]!r}")

    return bindings


__all__ = ["expand_sweep_constraints", "SweepConstraintsExpandError"]
