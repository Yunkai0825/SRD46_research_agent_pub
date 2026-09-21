"""
calc_json_input_reader.py
=============
Schema, dataclasses, and JSON loader for the **calculation-modes**
input file consumed by :func:`SRD46_numcalculator_api.run_calculation`.

Schema layout::

    {
      "sweep_method":   "pH_sweep" | "pourbaix_sweep"
                      | "titration_sweep",            // required

      "sweep_axes": [                                  // optional
        {"name": "pH",  "min": 0.0, "max": 14.0, "n_points": 71},
        {"name": "E_V", "min": -1.0, "max": 1.5, "n_points": 30},
        {"name": "a_w", "min": 0.7, "max": 1.0, "n_points":  3}
      ],

      "system_catalog": {                              // required (may be {})
        "chemical_system": {
          "metals":  [{"name": "Cu", "element": "Cu",
                       "internal_id": "Cu$+2", ...}],
          "ligands": [{"name": "Glycine", "db_id": "ligand_5760",
                       "internal_id": "L1",  "smiles": "..."}]
        },
        "freeform_vars_define": { ... }                // optional
      },

      "sweep_constraints": {                           // dict-shape (v3)
        // intensive toggles
        "pH_constr":             "pH_axis"|"pH_fixed"|"pH_freeform",
        "redox_constr":          "E_V_axis"|"E_V_fixed"|"E_V_freeform"
                                |"E_V_solve"|"excluded",
        "temperature_constr":    "temperature_fixed"|"temperature_axis",
        "ionic_strength_constr": "ionic_strength_fixed"
                                |"ionic_strength_auto"
                                |"ionic_strength_axis",

        // direct enum values
        "activity_model": "ideal"|"davies",
        "solids":         "include"|"exclude",

        // per-element / per-ligand toggles
        "[Cu]_constr":           "[Cu]_tot_fixed"|"[Cu]_tot_axis"
                                |"[Cu]_tot_freeform",
        "[ligand_5760]_constr":  "...same suffixes...",

        // composite [value, unit] entries (or bare scalars
        // already in canonical units; "auto" pass-through)
        "initial_condition": {
          "pH":              [7.0, "pH"],
          "E_V":             [0.0, "V"],
          "temperature":     [25.0, "C"],
          "ionic_strength":  [100.0, "mM"],
          "[Cu]_total":            [1.0, "mM"],
          "[ligand_5760]_total":   [10.0, "mM"]
        },

        // Tier-1 freeform pool: <eq-name>: "<single-DOF lhs> = <rhs>"
        "custom_freeform": {
          "nernst_line": "E_V = -0.059 * pH"
        }
      },

      "grid_refine": {"mode": "boundary", "factor": 2,
                      "n_layers": 2},                    // required
      "output_dir": null,                              // optional
      "_notes": "free text"
    }

The dict-shape ``sweep_constraints`` block is expanded into the
canonical list-of-bindings used by the constraint compiler via
:func:`sweep_constraints_expander.expand_sweep_constraints`.  The
legacy-style top-level fields (``temperature_C``, ``ionic_strength``,
``concentrations``, ``use_activity``, ``include_solids``,
``include_redox``) are still present on :class:`CalcInput` as an
internal mirror populated by ``_extract_environment_overrides`` so
the downstream ``_apply_concentration_overrides`` plumbing in
``SRD46_numcalculator_api`` works unchanged.

The schema is permissive: unknown top-level keys are preserved in
``CalcInput.extras`` so downstream code can read them.
"""
from __future__ import annotations

import json
import math
import os
import pathlib
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple, Union


NOT_DEFINED = "Not defined"


# ── Supported sweep methods ────────────────────────────────────────

SUPPORTED_SWEEP_METHODS: Tuple[str, ...] = (
    "pH_sweep",
    "pourbaix_sweep",
    "titration_sweep",
    "freeform_sweep",
)

# Axis names each sweep method recognises (extras accepted for advanced use).
# ``pourbaix_sweep`` is the unified N-D handler: include only ``pH`` and ``E_V``
# for the standard 2-D Pourbaix; add ``a_w`` to upgrade to a 3-D sweep.
_RECOGNISED_AXES: Dict[str, Tuple[str, ...]] = {
    "pH_sweep":        ("pH",),
    "pourbaix_sweep":  ("pH", "E_V", "a_w"),
    "titration_sweep": ("V_added_mL",),
    # freeform_sweep accepts any axis name; validation skipped below.
    "freeform_sweep":  (),
}

# ── Dataclasses ────────────────────────────────────────────────────

@dataclass
class SweepAxis:
    """One sweep axis.

    ``name`` is the physical quantity (``pH``, ``E_V``, ``a_w``,
    ``V_added_mL``).  Use one entry per axis; the registered method
    decides which axes it consumes.
    """
    name:      str
    min:       float
    max:       float
    n_points:  int

    def as_range(self) -> Tuple[float, float]:
        return (float(self.min), float(self.max))

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "min": float(self.min),
                "max": float(self.max), "n_points": int(self.n_points)}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SweepAxis":
        if not isinstance(d, dict):
            raise ValueError(f"sweep_axes entry must be an object, got {d!r}")
        missing = [key for key in ("name", "n_points") if key not in d]
        # Accept either {min,max} or {range:[lo,hi]}
        if "range" in d and "min" not in d:
            try:
                lo, hi = d["range"]
            except Exception as exc:
                raise ValueError(
                    f"sweep axis range must contain [min, max], got {d.get('range')!r}") from exc
            d = {**d, "min": lo, "max": hi}
        missing.extend(key for key in ("min", "max") if key not in d)
        if missing:
            raise ValueError(
                f"sweep axis has Not defined field(s) {sorted(set(missing))}: {d}")
        if any(d.get(key) == NOT_DEFINED
               for key in ("name", "min", "max", "n_points")):
            raise ValueError(f"sweep axis contains {NOT_DEFINED!r}: {d}")
        if any(isinstance(d.get(key), bool)
               for key in ("min", "max", "n_points")):
            raise ValueError(f"sweep axis numeric fields cannot be booleans: {d}")
        try:
            axis = cls(
                name=str(d["name"]).strip(),
                min=float(d["min"]),
                max=float(d["max"]),
                n_points=int(d["n_points"]),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(f"sweep axis fields must be explicit numeric values: {d}") from exc
        if not axis.name:
            raise ValueError(f"sweep axis name is {NOT_DEFINED!r}: {d}")
        if not math.isfinite(axis.min) or not math.isfinite(axis.max):
            raise ValueError(f"sweep axis bounds must be finite: {d}")
        return axis


@dataclass
class IonicStrengthSpec:
    """Ionic strength specification.

    ``mode``:
      - ``"fixed"`` — use ``value`` (mol/L) throughout the sweep.
      - ``"auto"``  — re-iterate ionic strength from the speciation.
      - ``"none"``  — disable activity corrections (γ ≡ 1).
    """
    mode:  str
    value: float

    def to_dict(self) -> Dict[str, Any]:
        return {"mode": self.mode, "value": float(self.value)}

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> "IonicStrengthSpec":
        if d is None:
            raise ValueError(
                "ionic-strength mode is Not defined; explicitly declare "
                "fixed, auto, or none")
        if not isinstance(d, dict) or "mode" not in d or d.get("mode") == NOT_DEFINED:
            raise ValueError(
                "ionic_strength.mode is Not defined; explicitly declare "
                "fixed, auto, or none")
        mode = str(d["mode"]).lower()
        if mode not in ("fixed", "auto", "none"):
            raise ValueError(
                f"ionic_strength.mode must be fixed|auto|none, got {mode!r}")
        if mode == "fixed":
            if "value" not in d or d.get("value") == NOT_DEFINED:
                raise ValueError(
                    "fixed ionic strength requires an explicitly declared value")
            if isinstance(d["value"], bool):
                raise ValueError("ionic_strength.value cannot be boolean")
            try:
                value = float(d["value"])
            except (TypeError, ValueError) as exc:
                raise ValueError("ionic_strength.value must be numeric") from exc
            if not math.isfinite(value) or value < 0:
                raise ValueError("ionic_strength.value must be finite and >= 0")
        else:
            # No fixed physical value exists in auto/none mode.  Zero is an
            # internal neutral placeholder, not an assumed calculation input.
            value = 0.0
        return cls(mode=mode, value=value)


@dataclass
class GridRefineSpec:
    """Explicit grid-refinement policy used by calculation cards.

    ``mode='none'`` disables refinement without numeric fields.  Boundary
    mode requires ``n_layers>=1`` and ``factor>=2``.
    """
    mode: str
    n_layers: int = 0
    factor: Optional[int] = None

    def __post_init__(self) -> None:
        from sweep_pipelines._sweep_input_entry_point.grid_refinement_contract import (
            normalize_grid_refinement_declaration,
        )

        is_none = (
            isinstance(self.mode, str)
            and self.mode.strip().lower() == "none"
        )
        if is_none and self.n_layers != 0:
            raise ValueError(
                "grid_refine mode 'none' must omit n_layers "
                "(internal disabled value is 0)"
            )
        declared_layers = None if is_none else self.n_layers
        self.mode, self.n_layers, self.factor = normalize_grid_refinement_declaration(
            mode=self.mode,
            n_layers=declared_layers,
            factor=self.factor,
        )

    def to_dict(self) -> Dict[str, Any]:
        if self.mode == "none":
            return {"mode": "none"}
        return {
            "mode": "boundary",
            "factor": int(self.factor),
            "n_layers": int(self.n_layers),
        }

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> "GridRefineSpec":
        if d is None:
            raise ValueError(
                "calc-input JSON missing required 'grid_refine' block; "
                "use {'mode': 'none'} to disable refinement explicitly"
            )
        if not isinstance(d, dict):
            raise ValueError("'grid_refine' must be a JSON object")
        if "mode" not in d:
            raise ValueError("grid_refine.mode is Not defined")
        mode = d["mode"]
        normalized_mode = mode.strip().lower() if isinstance(mode, str) else None
        if normalized_mode not in ("none", "boundary"):
            raise ValueError(
                f"grid_refine.mode must be 'none' or 'boundary', got {mode!r}"
            )
        if normalized_mode == "none":
            if "factor" in d or "n_layers" in d:
                raise ValueError(
                    "grid_refine mode 'none' must omit factor and n_layers"
                )
            return cls(mode="none")
        if "n_layers" not in d:
            raise ValueError("grid_refine.n_layers is Not defined")
        if "factor" not in d:
            raise ValueError("grid_refine.factor is Not defined")
        return cls(mode=mode, n_layers=d["n_layers"], factor=d["factor"])


@dataclass
class CalcInput:
    """Parsed calculation-modes input."""
    sweep_method:     str
    sweep_axes:       List[SweepAxis]
    ionic_strength:   IonicStrengthSpec
    temperature_C:    Optional[float]
    total_metals:     Dict[str, float]
    total_ligands:    Dict[str, float]
    use_activity:     bool
    include_solids:   bool
    include_redox:    bool
    grid_refine:      GridRefineSpec
    output_dir:       Optional[str]                 = None
    extras:           Dict[str, Any]                = field(default_factory=dict)

    # ── Sweep-constraints fields ───────────────────────────
    # Populated by ``load_calc_input``.  ``sweep_constraints`` carries
    # the canonical list-of-bindings produced by
    # ``sweep_constraints_expander.expand_sweep_constraints``.
    system_catalog:   Dict[str, Any]                = field(default_factory=dict)
    sweep_constraints: List[Any]                    = field(default_factory=list)

    # ── Native lc3_2.v1 constraint spec ────────────────────────
    # When the calc-input carries a ``constraint_spec`` block the loader
    # stores the raw lc3_2.v1 spec + settings sidecar here and leaves
    # ``sweep_constraints`` empty.  ``run_calculation`` then compiles them
    # natively via ``constraint_compiler.compile_spec`` (no dict-shape
    # intermediate).  ``spec is None`` selects the legacy dict-shape path.
    spec:             Optional[Dict[str, Any]]      = None
    settings:         Dict[str, Any]                = field(default_factory=dict)

    # ── Convenience ────────────────────────────────────────────

    def axis(self, name: str) -> Optional[SweepAxis]:
        for ax in self.sweep_axes:
            if ax.name == name:
                return ax
        return None

    def axis_or_default(self, name: str) -> SweepAxis:
        ax = self.axis(name)
        if ax is not None:
            return ax
        raise KeyError(
            f"Sweep method '{self.sweep_method}' requires an explicitly "
            f"declared '{name}' axis; its value is {NOT_DEFINED!r}")

    @property
    def temperature_K(self) -> Optional[float]:
        if self.temperature_C is None:
            return None
        return float(self.temperature_C) + 273.15

    # ── Serialisation ──────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "sweep_method":   self.sweep_method,
            "sweep_axes":     [a.to_dict() for a in self.sweep_axes],
            "ionic_strength": self.ionic_strength.to_dict(),
            "temperature_C":  self.temperature_C,
            "concentrations": {
                "total_metals":  dict(self.total_metals),
                "total_ligands": dict(self.total_ligands),
            },
            "grid_refine":    self.grid_refine.to_dict(),
            "use_activity":   self.use_activity,
            "include_solids": self.include_solids,
            "include_redox":  self.include_redox,
            "output_dir":     self.output_dir,
        }

        if self.extras:
            d.update(self.extras)
        return d

    # ── Validation ─────────────────────────────────────────────

    def validate(self) -> List[str]:
        """Return a list of human-readable issues (empty == OK)."""
        issues: List[str] = []
        if self.sweep_method not in SUPPORTED_SWEEP_METHODS:
            issues.append(
                f"unknown sweep_method '{self.sweep_method}'. "
                f"Supported: {SUPPORTED_SWEEP_METHODS}")
            return issues
        for name, value in (
            ("use_activity", self.use_activity),
            ("include_solids", self.include_solids),
            ("include_redox", self.include_redox),
        ):
            if not isinstance(value, bool):
                issues.append(
                    f"{name} must be an explicitly declared boolean, got {value!r}")
        if self.temperature_C is None or isinstance(self.temperature_C, bool):
            issues.append(
                "temperature_C must be an explicitly declared finite numeric value")
        else:
            try:
                temperature_c = float(self.temperature_C)
            except (TypeError, ValueError):
                issues.append("temperature_C must be numeric")
            else:
                if not math.isfinite(temperature_c) or temperature_c <= -273.15:
                    issues.append(
                        "temperature_C must be finite and above absolute zero")
        if not isinstance(self.ionic_strength, IonicStrengthSpec):
            issues.append(
                "ionic_strength must explicitly declare mode and value")
        else:
            ionic_mode = self.ionic_strength.mode
            if ionic_mode not in {"fixed", "auto", "none"}:
                issues.append(
                    f"ionic_strength.mode must be fixed|auto|none, got {ionic_mode!r}")
            ionic_value = self.ionic_strength.value
            if isinstance(ionic_value, bool):
                issues.append("ionic_strength.value cannot be boolean")
            else:
                try:
                    ionic_number = float(ionic_value)
                except (TypeError, ValueError):
                    issues.append("ionic_strength.value must be numeric")
                else:
                    if not math.isfinite(ionic_number) or ionic_number < 0:
                        issues.append(
                            "ionic_strength.value must be finite and >= 0")
        if not isinstance(self.grid_refine, GridRefineSpec):
            issues.append(
                "grid_refine must explicitly declare n_layers and, when "
                "enabled, factor")
        else:
            from sweep_pipelines._sweep_input_entry_point.grid_refinement_contract import (
                normalize_grid_refinement_declaration,
            )
            if (self.grid_refine.mode == "none"
                    and self.grid_refine.n_layers != 0):
                issues.append(
                    "grid_refine mode 'none' must have internal n_layers=0")
            try:
                normalize_grid_refinement_declaration(
                    mode=self.grid_refine.mode,
                    n_layers=(None if self.grid_refine.mode == "none"
                              else self.grid_refine.n_layers),
                    factor=self.grid_refine.factor,
                )
            except ValueError as exc:
                issues.append(str(exc))
        required_axes = {
            "pH_sweep": {"pH"},
            "pourbaix_sweep": {"pH", "E_V"},
            "titration_sweep": {"V_added_mL"},
        }.get(self.sweep_method, set())
        if not self.sweep_axes:
            issues.append("sweep_axes is Not defined; declare every axis range and resolution")
        recognised = _RECOGNISED_AXES[self.sweep_method]
        seen_names = set()
        for ax in self.sweep_axes:
            if not isinstance(ax, SweepAxis):
                issues.append(f"sweep axis must be a SweepAxis object, got {ax!r}")
                continue
            if ax.name in seen_names:
                issues.append(f"duplicate sweep axis '{ax.name}'")
            seen_names.add(ax.name)
            numeric_invalid = any(
                isinstance(value, bool) for value in (ax.min, ax.max, ax.n_points))
            try:
                axis_min = float(ax.min)
                axis_max = float(ax.max)
                axis_n = float(ax.n_points)
            except (TypeError, ValueError):
                numeric_invalid = True
                axis_min = axis_max = axis_n = float("nan")
            if (numeric_invalid or not all(math.isfinite(value)
                                           for value in (axis_min, axis_max, axis_n))
                    or not axis_n.is_integer()):
                issues.append(
                    f"axis '{ax.name}' bounds and n_points must be finite numerics; "
                    "booleans are not permitted")
                continue
            if axis_n < 2:
                issues.append(
                    f"axis '{ax.name}' n_points must be ≥ 2 (got {ax.n_points})")
            if axis_max <= axis_min:
                issues.append(
                    f"axis '{ax.name}' max ({ax.max}) must exceed min ({ax.min})")
            # freeform_sweep accepts any axis name; otherwise advise on
            # non-standard names for the declared method.
            if recognised and ax.name not in recognised:
                issues.append(
                    f"axis '{ax.name}' not standard for {self.sweep_method} "
                    f"(expected one of {recognised})")
        missing_axes = sorted(required_axes - seen_names)
        if missing_axes:
            issues.append(
                f"required sweep axis/axes are Not defined: {missing_axes}")
        for label, values in (("metal", self.total_metals),
                              ("ligand", self.total_ligands)):
            for key, value in values.items():
                if isinstance(value, bool):
                    issues.append(
                        f"{label} total {key!r} must be a finite value >= 0")
                    continue
                try:
                    number = float(value)
                except (TypeError, ValueError):
                    issues.append(
                        f"{label} total {key!r} must be a finite value >= 0")
                    continue
                if not math.isfinite(number) or number < 0:
                    issues.append(
                        f"{label} total {key!r} must be a finite value >= 0")
        return issues


# ── JSON I/O ──────────────────────────────────────────────────────

def _extract_environment_overrides(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Extract environment-mirror fields from a calc-input dict.

    Downstream code (``_apply_concentration_overrides`` in
    ``SRD46_numcalculator_api``) still reads ``temperature_C``,
    ``ionic_strength``, ``concentrations``, ``use_activity``,
    ``include_solids``, ``include_redox``.  These live inside
    ``sweep_constraints.initial_condition`` and the intensive
    ``*_constr`` toggles -- this helper synthesises the legacy-style
    mirror dict so the rest of the loader is unchanged.

    Bracket-token semantics (initial_condition keys ``[X]_total``):
      * ``[<element>]_total``       -> ``concentrations.total_metals[<element>]``
      * ``[<ligand_db_id>]_total``  -> ``concentrations.total_ligands[<ligand_db_id>]``

    Routing rule: tokens declared in ``system_catalog.chemical_system``
    are routed by that declaration; otherwise tokens matching
    ``ligand_\\d+`` are treated as ligand db_ids and everything else as
    a metal element / internal_id.
    """
    sc = raw.get("sweep_constraints") or {}
    if not isinstance(sc, dict):
        return {}
    ic = sc.get("initial_condition") or {}
    if not isinstance(ic, dict):
        ic = {}

    # Normalise composite [value, unit] / bare-scalar entries into
    # canonical-unit floats before any downstream consumer reads them.
    from sweep_pipelines._sweep_input_entry_point.initial_condition_normalizer import (
        normalize_initial_condition,
        InitialConditionUnitError,
    )
    sys_cat_pre = raw.get("system_catalog") or {}
    fvars_pre = (sys_cat_pre.get("freeform_vars_define") or {}
                 ) if isinstance(sys_cat_pre, dict) else {}
    try:
        ic = normalize_initial_condition(ic, fvars_pre)
    except InitialConditionUnitError as exc:
        raise ValueError(str(exc)) from exc

    out: Dict[str, Any] = {}

    # Temperature: canonical key is ``temperature`` (K, scalar).
    if "temperature" in ic:
        try:
            tK = float(ic["temperature"])
            out["temperature_K"] = tK
            out["temperature_C"] = tK - 273.15
        except (TypeError, ValueError):
            pass

    # Ionic strength: canonical key is ``ionic_strength``
    # (number for fixed, "auto" string for auto).  The toggle wins.
    is_constr = sc.get("ionic_strength_constr")
    if is_constr == "ionic_strength_auto":
        out["ionic_strength"] = {"mode": "auto", "value": 0.0}
    elif "ionic_strength" in ic:
        v = ic["ionic_strength"]
        if isinstance(v, str) and v.lower() == "auto":
            out["ionic_strength"] = {"mode": "auto", "value": 0.0}
        else:
            try:
                out["ionic_strength"] = {"mode": "fixed", "value": float(v)}
            except (TypeError, ValueError):
                pass

    # Activity model / solids / redox toggles
    am = sc.get("activity_model")
    if am is not None:
        out["use_activity"] = (str(am) != "ideal")
    sol = sc.get("solids")
    if sol is not None:
        out["include_solids"] = (str(sol) == "include")
    if sc.get("redox_constr") == "excluded":
        out["include_redox"] = False
    else:
        out["include_redox"] = True

    # Concentrations: scan initial_condition for [X]_total entries.
    catalog = raw.get("system_catalog") or {}
    cs = catalog.get("chemical_system") or {}
    elem_names: set = set()
    metal_iids: set = set()
    for m in (cs.get("metals") or []):
        if m.get("name"):    elem_names.add(m["name"])
        if m.get("element"): elem_names.add(m["element"])
        if m.get("internal_id"): metal_iids.add(m["internal_id"])
        for rid in (m.get("redox_states") or []):
            metal_iids.add(rid)
    ligand_db_ids = {L.get("db_id") for L in (cs.get("ligands") or [])
                     if L.get("db_id") is not None}

    import re as _re
    _LIGAND_DBID_RE = _re.compile(r"^ligand_\d+$")

    total_metals: Dict[str, float] = {}
    total_ligands: Dict[str, float] = {}
    for k, v in ic.items():
        if not (isinstance(k, str) and k.startswith("[") and k.endswith("]_total")):
            continue
        token = k[1:-len("]_total")]
        try:
            value = float(v)
        except (TypeError, ValueError):
            continue
        if token in ligand_db_ids or _LIGAND_DBID_RE.match(token):
            total_ligands[token] = value
        elif token in elem_names or token in metal_iids:
            total_metals[token] = value
        else:
            # No catalog hint and no ligand_<n> pattern -> treat as metal.
            total_metals[token] = value
    if total_metals or total_ligands:
        out["concentrations"] = {
            "total_metals":  total_metals,
            "total_ligands": total_ligands,
        }

    return out


def _extract_environment_overrides_from_spec(
        spec: Dict[str, Any],
        settings: Dict[str, Any],
        system_catalog: Dict[str, Any]) -> Dict[str, Any]:
    """Environment-mirror fields straight from an ``lc3_2.v1`` spec.

    Native counterpart of :func:`_extract_environment_overrides` for the
    dict-shape schema.  Spec ``const`` values are already in canonical
    units (K, mol/L), so no unit normalisation is applied.

    Reads only ``op == "=="`` binds whose RHS is a literal ``{"const": v}``
    (axis-driven binds carry ``{"axis": ...}`` and are intentionally
    skipped — they vary per cell and are not environment baselines).
    """
    out: Dict[str, Any] = {}
    binds = [b for b in (spec.get("binds") or []) if b.get("op") == "=="]

    def _const_of(lhs_ref: str, lhs_id: Optional[str] = None):
        for b in binds:
            lhs = b.get("lhs") or {}
            if lhs.get("ref") != lhs_ref:
                continue
            if lhs_id is not None and lhs.get("id") != lhs_id:
                continue
            rhs = b.get("rhs") or {}
            if isinstance(rhs, dict) and "const" in rhs:
                try:
                    return float(rhs["const"])
                except (TypeError, ValueError):
                    return None
        return None

    # Temperature (K)
    tK = _const_of("temperature")
    if tK is not None:
        out["temperature_K"] = tK
        out["temperature_C"] = tK - 273.15

    # Ionic strength: settings mode wins; const supplies the fixed value.
    is_mode = str(settings["ionic_strength_mode"])
    if is_mode == "auto":
        out["ionic_strength"] = {"mode": "auto", "value": 0.0}
    elif is_mode == "none":
        out["ionic_strength"] = {"mode": "none", "value": 0.0}
    elif is_mode == "fixed":
        isv = _const_of("ionic_strength")
        if isv is not None:
            out["ionic_strength"] = {"mode": "fixed", "value": isv}
    else:
        raise ValueError(
            f"ionic_strength_mode={is_mode!r} is not yet supported by the "
            "numerical input adapter; use an explicitly declared fixed, "
            "auto, or none mode")

    # Activity model / solids / redox
    am = settings.get("activity_model")
    if am is not None:
        out["use_activity"] = (str(am) != "ideal")
    sol = settings.get("solids")
    if sol is not None:
        out["include_solids"] = (str(sol) == "include")
    out["include_redox"] = (str(settings.get("redox_mode")) != "excluded")

    # Totals -> total_metals / total_ligands (same routing as dict-shape).
    cs = (system_catalog.get("chemical_system") or {}
          ) if isinstance(system_catalog, dict) else {}
    elem_names: set = set()
    metal_iids: set = set()
    for m in (cs.get("metals") or []):
        if m.get("name"):    elem_names.add(m["name"])
        if m.get("element"): elem_names.add(m["element"])
        if m.get("internal_id"): metal_iids.add(m["internal_id"])
        for rid in (m.get("redox_states") or []):
            metal_iids.add(rid)
    ligand_db_ids = {L.get("db_id") for L in (cs.get("ligands") or [])
                     if L.get("db_id") is not None}

    import re as _re
    _LIGAND_DBID_RE = _re.compile(r"^ligand_\d+$")

    total_metals: Dict[str, float] = {}
    total_ligands: Dict[str, float] = {}
    for b in binds:
        lhs = b.get("lhs") or {}
        if lhs.get("ref") != "total":
            continue
        rhs = b.get("rhs") or {}
        if not (isinstance(rhs, dict) and "const" in rhs):
            continue
        token = lhs.get("id")
        try:
            value = float(rhs["const"])
        except (TypeError, ValueError):
            continue
        if token in ligand_db_ids or _LIGAND_DBID_RE.match(str(token)):
            total_ligands[str(token)] = value
        elif token in elem_names or token in metal_iids:
            total_metals[str(token)] = value
        else:
            total_metals[str(token)] = value
    if total_metals or total_ligands:
        out["concentrations"] = {
            "total_metals":  total_metals,
            "total_ligands": total_ligands,
        }

    return out


def _numeric_const_bind_ids(spec: Dict[str, Any], ref: str) -> set[str]:
    ids: set[str] = set()
    for bind in spec.get("binds") or []:
        if not isinstance(bind, dict) or bind.get("op") != "==":
            continue
        lhs = bind.get("lhs") or {}
        rhs = bind.get("rhs") or {}
        if lhs.get("ref") != ref or not isinstance(rhs, dict) or "const" not in rhs:
            continue
        value = rhs.get("const")
        if value == NOT_DEFINED or isinstance(value, bool):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            ids.add(str(lhs.get("id") or ""))
    return ids


def _has_numeric_const_bind(spec: Dict[str, Any], ref: str) -> bool:
    return "" in _numeric_const_bind_ids(spec, ref)


def _validate_native_declarations(
        raw: Dict[str, Any], spec: Dict[str, Any],
        settings: Dict[str, Any], system_catalog: Dict[str, Any],
) -> None:
    """Reject a native calculation card with any implicit model input."""
    issues: list[str] = []
    allowed = {
        "activity_model": {"ideal", "davies"},
        "solids": {"include", "exclude"},
        "redox_mode": {"axis", "fixed", "freeform", "solve", "excluded"},
        "ionic_strength_mode": {"fixed", "auto", "none"},
    }
    for key, values in allowed.items():
        value = settings.get(key, NOT_DEFINED)
        if value == NOT_DEFINED:
            issues.append(f"constraint_settings.{key} is {NOT_DEFINED!r}")
        elif key == "activity_model" and value == "debye_huckel":
            issues.append(
                "constraint_settings.activity_model='debye_huckel' is not "
                "implemented; declare 'ideal' or 'davies'")
        elif str(value) not in values:
            issues.append(
                f"constraint_settings.{key}={value!r}; allowed: {sorted(values)}")

    if not _has_numeric_const_bind(spec, "temperature"):
        issues.append(
            f"temperature is {NOT_DEFINED!r}; declare a finite constant in constraint_spec.binds")

    ionic_mode = settings.get("ionic_strength_mode")
    if ionic_mode == "fixed" and not _has_numeric_const_bind(spec, "ionic_strength"):
        issues.append(
            f"fixed ionic strength is {NOT_DEFINED!r}; declare its finite value")

    redox_mode = settings.get("redox_mode")
    e_binds = [
        bind for bind in (spec.get("binds") or [])
        if isinstance(bind, dict) and bind.get("op") == "=="
        and (bind.get("lhs") or {}).get("ref") == "E_V"
    ]
    e_axes = [
        axis for axis in (raw.get("sweep_axes") or [])
        if isinstance(axis, dict) and axis.get("name") == "E_V"
    ]
    if len(e_binds) > 1:
        issues.append("E_V has multiple declarations; declare exactly one redox DOF")
    e_rhs = (e_binds[0].get("rhs") or {}) if len(e_binds) == 1 else {}
    if redox_mode == "excluded":
        if e_binds or e_axes:
            issues.append(
                "redox_mode='excluded' requires E_V to be absent; remove its bind and axis")
    elif redox_mode == "fixed":
        value = e_rhs.get("const", NOT_DEFINED)
        if (len(e_binds) != 1 or value == NOT_DEFINED
                or isinstance(value, bool)):
            issues.append("redox_mode='fixed' requires one finite constant E_V bind")
        else:
            try:
                if not math.isfinite(float(value)):
                    raise ValueError
            except (TypeError, ValueError):
                issues.append("redox_mode='fixed' requires one finite constant E_V bind")
        if e_axes:
            issues.append("redox_mode='fixed' must not declare an E_V sweep axis")
    elif redox_mode == "axis":
        if len(e_binds) != 1 or "axis" not in e_rhs or not e_axes:
            issues.append(
                "redox_mode='axis' requires one E_V axis bind and a declared E_V axis")
    elif redox_mode == "freeform":
        if (len(e_binds) != 1 or not e_rhs
                or "const" in e_rhs or "axis" in e_rhs):
            issues.append(
                "redox_mode='freeform' requires one explicit formula E_V bind")
        if e_axes:
            issues.append("redox_mode='freeform' must not declare an E_V sweep axis")
    elif redox_mode == "solve":
        if e_binds or e_axes:
            issues.append(
                "redox_mode='solve' requires E_V to be absent so the solver "
                "can determine it from one state-subtotal target")

    species_binds = [
        bind for bind in (spec.get("binds") or [])
        if isinstance(bind, dict)
        and ((bind.get("lhs") or {}).get("ref")
             in {"species", "conc", "lnconc"})
    ]
    if species_binds and settings.get("species_pins") != "allowed":
        issues.append(
            "individual-species constraints require "
            "constraint_settings.species_pins='allowed'")

    if not raw.get("sweep_axes"):
        issues.append(
            f"sweep_axes is {NOT_DEFINED!r}; declare every range and resolution")
    if issues:
        raise ValueError(
            "calculation card has undeclared physical/model inputs; no solver "
            "defaults are permitted:\n  - " + "\n  - ".join(issues))


def _validate_legacy_declarations(
        raw: Dict[str, Any], system_catalog: Dict[str, Any]) -> None:
    """Apply the same explicit-input contract to dict-shape cards."""
    sc = raw.get("sweep_constraints")
    if not isinstance(sc, dict):
        raise ValueError(
            "sweep_constraints is Not defined; physical/model inputs must be explicit")
    issues: list[str] = []
    for key in ("activity_model", "solids", "redox_constr",
                "ionic_strength_constr", "temperature_constr"):
        if sc.get(key, NOT_DEFINED) == NOT_DEFINED:
            issues.append(f"sweep_constraints.{key} is {NOT_DEFINED!r}")
    activity_model = sc.get("activity_model", NOT_DEFINED)
    if activity_model == "debye_huckel":
        issues.append(
            "sweep_constraints.activity_model='debye_huckel' is not "
            "implemented; declare 'ideal' or 'davies'")
    elif activity_model != NOT_DEFINED and activity_model not in {"ideal", "davies"}:
        issues.append(
            f"sweep_constraints.activity_model={activity_model!r}; allowed: "
            "['davies', 'ideal']")
    solids = sc.get("solids", NOT_DEFINED)
    if solids != NOT_DEFINED and solids not in {"include", "exclude"}:
        issues.append(
            f"sweep_constraints.solids={solids!r}; allowed: ['exclude', 'include']")
    ic = sc.get("initial_condition")
    if not isinstance(ic, dict):
        ic = {}
    if sc.get("temperature_constr") != "temperature_axis" \
            and ic.get("temperature", NOT_DEFINED) == NOT_DEFINED:
        issues.append(f"temperature is {NOT_DEFINED!r}")
    if sc.get("ionic_strength_constr") == "ionic_strength_fixed" \
            and ic.get("ionic_strength", NOT_DEFINED) == NOT_DEFINED:
        issues.append(f"fixed ionic strength is {NOT_DEFINED!r}")
    redox_constr = sc.get("redox_constr")
    e_axes = [axis for axis in (raw.get("sweep_axes") or [])
              if isinstance(axis, dict) and axis.get("name") == "E_V"]
    e_fixed = ic.get("E_V", NOT_DEFINED) != NOT_DEFINED
    freeform = sc.get("custom_freeform") or {}
    e_freeform = any(
        isinstance(value, str) and value.strip().startswith("E_V")
        for value in (freeform.values() if isinstance(freeform, dict) else [])
    )
    if redox_constr == "excluded" and (e_axes or e_fixed or e_freeform):
        issues.append("redox_constr='excluded' requires E_V to be absent")
    elif redox_constr == "E_V_fixed" and (not e_fixed or e_axes or e_freeform):
        issues.append("redox_constr='E_V_fixed' requires only an explicit fixed E_V")
    elif redox_constr == "E_V_axis" and (not e_axes or e_fixed or e_freeform):
        issues.append("redox_constr='E_V_axis' requires only a declared E_V axis")
    elif redox_constr == "E_V_freeform" and (not e_freeform or e_axes or e_fixed):
        issues.append("redox_constr='E_V_freeform' requires only an E_V formula")
    elif redox_constr == "E_V_solve" and (e_freeform or e_axes or e_fixed):
        issues.append(
            "redox_constr='E_V_solve' requires E_V to be absent")
    if not raw.get("sweep_axes"):
        issues.append(f"sweep_axes is {NOT_DEFINED!r}")
    if issues:
        raise ValueError(
            "calculation card has undeclared physical/model inputs; no solver "
            "defaults are permitted:\n  - " + "\n  - ".join(issues))


def _catalog_for_declaration_compile(system_catalog: Dict[str, Any]):
    """Build the compiler catalog without requiring a resolved thermo card."""
    from sweep_pipelines._sweep_input_entry_point.constraint_compiler import (
        ChemicalSystem,
        LigandDescriptor,
        MetalDescriptor,
        SystemCatalog,
    )

    cs = (system_catalog.get("chemical_system") or {}
          ) if isinstance(system_catalog, dict) else {}
    metals = []
    for raw_metal in cs.get("metals") or []:
        if not isinstance(raw_metal, dict):
            continue
        states = []
        for entry in raw_metal.get("redox_states") or []:
            if isinstance(entry, dict):
                token = (entry.get("internal_id") or entry.get("id")
                         or entry.get("name"))
            else:
                token = entry
            if token not in (None, "", NOT_DEFINED):
                states.append(str(token))
        element = str(raw_metal.get("element") or raw_metal.get("name")
                      or raw_metal.get("internal_id") or "")
        internal_id = str(raw_metal.get("internal_id")
                          or (states[0] if states else element))
        if not states:
            states = [internal_id]
        metals.append(MetalDescriptor(
            name=str(raw_metal.get("name") or element),
            element=element,
            internal_id=internal_id,
            db_id=raw_metal.get("db_id"),
            redox_states=states,
        ))

    ligands = []
    for raw_ligand in cs.get("ligands") or []:
        if not isinstance(raw_ligand, dict):
            continue
        db_id = str(raw_ligand.get("db_id")
                    or raw_ligand.get("internal_id")
                    or raw_ligand.get("name") or "")
        ligands.append(LigandDescriptor(
            name=str(raw_ligand.get("name") or db_id),
            db_id=db_id,
            internal_id=str(raw_ligand.get("internal_id") or db_id),
            smiles=str(raw_ligand.get("smiles") or ""),
            inchi_key=str(raw_ligand.get("inchi_key") or ""),
        ))
    return SystemCatalog(
        chemical_system=ChemicalSystem(metals=metals, ligands=ligands),
        freeform_vars_define=dict(
            system_catalog.get("freeform_vars_define") or {}),
    )


def _validate_compiled_declarations(
    raw: Dict[str, Any],
    system_catalog: Dict[str, Any],
    *,
    spec: Optional[Dict[str, Any]] = None,
    settings: Optional[Dict[str, Any]] = None,
    bindings: Optional[List[Any]] = None,
) -> None:
    """Run completeness/rank checks once on canonical compiled variables."""
    from sweep_pipelines._sweep_input_entry_point.constraint_compiler import (
        compile_constraints,
        compile_spec,
    )

    catalog = _catalog_for_declaration_compile(system_catalog)
    axis_names = [
        str(axis.get("name")) for axis in (raw.get("sweep_axes") or [])
        if isinstance(axis, dict) and axis.get("name")
    ]
    try:
        if spec is not None:
            has_species_pins = any(
                isinstance(bind, dict)
                and ((bind.get("lhs") or {}).get("ref")
                     in {"species", "conc", "lnconc"})
                for bind in (spec.get("binds") or [])
            )
            if has_species_pins and (settings or {}).get(
                    "species_pins") == "allowed":
                # The loader has no thermodynamic report and therefore cannot
                # resolve a species to the one total released by the augmented
                # solver.  Defer the canonical compile to run_calculation(),
                # where the report-aware map is available.
                return
            compile_spec(catalog, axis_names, spec, settings or {})
        else:
            compile_constraints(catalog, axis_names, bindings or [])
    except Exception as exc:
        raise ValueError(
            f"calculation card constraint/DOF validation failed: {exc}") from exc


def load_calc_input(source: Union[str, pathlib.Path, Dict[str, Any]]) -> CalcInput:
    """Parse a calculation-modes JSON file (or in-memory dict).

    The dict-shape ``sweep_constraints`` block is expanded into the
    canonical list-of-bindings used by the constraint compiler via
    :func:`sweep_constraints_expander.expand_sweep_constraints`.
    """
    if isinstance(source, (str, pathlib.Path)):
        # Windows long-path workaround (>260 chars on UNC).
        _src = os.fspath(source)
        if os.name == "nt":
            _abs = os.path.abspath(_src)
            if not _abs.startswith("\\\\?\\") and len(_abs) >= 240:
                _abs = ("\\\\?\\UNC\\" + _abs[2:]) if _abs.startswith("\\\\") else ("\\\\?\\" + _abs)
            _src = _abs
        with open(_src, "r", encoding="utf-8") as _fh:
            text = _fh.read()
        raw = json.loads(text)
    else:
        raw = dict(source)

    if "sweep_method" not in raw:
        raise ValueError("calc-input JSON missing required 'sweep_method'")

    if "system_catalog" not in raw:
        raise ValueError(
            "calc-input JSON missing required 'system_catalog' block. "
            "It is the canonical record of the chemical system and must "
            "declare 'chemical_system.metals' and/or 'chemical_system.ligands'.")
    sys_cat = raw.get("system_catalog")
    if not isinstance(sys_cat, dict):
        raise ValueError("'system_catalog' must be a JSON object")
    cs = sys_cat.get("chemical_system")
    if not isinstance(cs, dict) or not (cs.get("metals") or cs.get("ligands")):
        raise ValueError(
            "'system_catalog.chemical_system' must declare at least one "
            "metal or ligand entry (no implicit auto-build).")

    # ── Native lc3_2.v1 path: ``constraint_spec`` (+ optional
    #    ``constraint_settings``) replaces the dict-shape
    #    ``sweep_constraints``.  Compiled natively downstream via
    #    ``constraint_compiler.compile_spec`` — no expander, no
    #    dict-shape bindings. ─────────────────────────────────────
    native_spec = raw.get("constraint_spec")
    if native_spec is not None:
        if not isinstance(native_spec, dict):
            raise ValueError("'constraint_spec' must be a JSON object")
        native_settings = raw.get("constraint_settings")
        if not isinstance(native_settings, dict):
            raise ValueError("'constraint_settings' must be a JSON object")
        _validate_native_declarations(
            raw, native_spec, native_settings, sys_cat)
        _validate_compiled_declarations(
            raw, sys_cat, spec=native_spec, settings=native_settings)
        env_overrides = _extract_environment_overrides_from_spec(
            native_spec, native_settings, sys_cat)

        sweep_method = str(raw["sweep_method"])
        axes = [SweepAxis.from_dict(d) for d in (raw.get("sweep_axes") or [])]
        conc = env_overrides.get("concentrations") or {}
        total_metals  = {str(k): float(v)
                         for k, v in (conc.get("total_metals") or {}).items()}
        total_ligands = {str(k): float(v)
                         for k, v in (conc.get("total_ligands") or {}).items()}

        extras_n: Dict[str, Any] = {}
        handled_n = {
            "sweep_method", "sweep_axes", "grid_refine", "output_dir",
            "system_catalog", "sweep_constraints",
            "constraint_spec", "constraint_settings",
        }
        for k, val in raw.items():
            if k not in handled_n and not k.startswith("_"):
                extras_n[k] = val

        temp_Cn = env_overrides.get("temperature_C")
        ci_n = CalcInput(
            sweep_method=sweep_method,
            sweep_axes=axes,
            ionic_strength=IonicStrengthSpec.from_dict(
                env_overrides.get("ionic_strength")),
            temperature_C=(float(temp_Cn) if temp_Cn is not None else None),
            total_metals=total_metals,
            total_ligands=total_ligands,
            grid_refine=GridRefineSpec.from_dict(raw.get("grid_refine")),
            use_activity=env_overrides["use_activity"],
            include_solids=env_overrides["include_solids"],
            include_redox=env_overrides["include_redox"],
            output_dir=(str(raw["output_dir"])
                        if raw.get("output_dir") is not None else None),
            extras=extras_n,
            system_catalog=dict(sys_cat or {}),
            sweep_constraints=[],
            spec=dict(native_spec),
            settings=dict(native_settings),
        )
        issues_n = ci_n.validate()
        advisories_n = [s for s in issues_n
                        if s.startswith("axis '") and "not standard" in s]
        fatal_n = [s for s in issues_n if s not in advisories_n]
        if fatal_n:
            raise ValueError(
                "Invalid calc-input JSON:\n  - " + "\n  - ".join(fatal_n))
        return ci_n

    _validate_legacy_declarations(raw, sys_cat)

    from sweep_pipelines._sweep_input_entry_point.sweep_constraints_expander import (
        expand_sweep_constraints,
    )
    bindings        = expand_sweep_constraints(raw)
    _validate_compiled_declarations(
        raw, sys_cat, bindings=list(bindings))
    env_overrides   = _extract_environment_overrides(raw)

    sweep_method = str(raw["sweep_method"])
    axes = [SweepAxis.from_dict(d) for d in (raw.get("sweep_axes") or [])]

    conc = env_overrides.get("concentrations") or {}
    total_metals  = {str(k): float(v) for k, v in (conc.get("total_metals")  or {}).items()}
    total_ligands = {str(k): float(v) for k, v in (conc.get("total_ligands") or {}).items()}

    extras: Dict[str, Any] = {}
    handled = {
        "sweep_method", "sweep_axes", "grid_refine", "output_dir",
        "system_catalog", "sweep_constraints",
    }
    for k, val in raw.items():
        if k not in handled and not k.startswith("_"):
            extras[k] = val

    temp_C = env_overrides.get("temperature_C")

    ci = CalcInput(
        sweep_method=sweep_method,
        sweep_axes=axes,
        ionic_strength=IonicStrengthSpec.from_dict(env_overrides.get("ionic_strength")),
        temperature_C=(float(temp_C) if temp_C is not None else None),
        total_metals=total_metals,
        total_ligands=total_ligands,
        grid_refine=GridRefineSpec.from_dict(raw.get("grid_refine")),
        use_activity=env_overrides["use_activity"],
        include_solids=env_overrides["include_solids"],
        include_redox=env_overrides["include_redox"],
        output_dir=(str(raw["output_dir"])
                    if raw.get("output_dir") is not None else None),
        extras=extras,
        system_catalog=dict(raw.get("system_catalog", {}) or {}),
        sweep_constraints=list(bindings),
    )
    issues = ci.validate()
    advisories = [s for s in issues if s.startswith("axis '") and "not standard" in s]
    fatal      = [s for s in issues if s not in advisories]
    if fatal:
        raise ValueError(
            "Invalid calc-input JSON:\n  - " + "\n  - ".join(fatal))
    return ci


def dump_calc_input(calc: CalcInput,
                    path: Union[str, pathlib.Path]) -> pathlib.Path:
    """Write a ``CalcInput`` back to JSON."""
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(calc.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return p
