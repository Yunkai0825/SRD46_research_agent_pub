"""
SRD46_numcalculator_api.py
==========================
Top-level callable that wires (card source) + (calculation-modes input)
into the appropriate sweep pipeline.

::

    from SRD46_numcalculator_api import run_calculation, load_calc_input

    calc = load_calc_input("my_pourbaix_2d.json")
    result = run_calculation(card_source="path/to/card_dir",
                             calc_input=calc,
                             output_dir="out/")
"""
from __future__ import annotations

import pathlib
import math
import sys
from typing import Any, Dict, Optional, Union
# Path bootstrap: this module sits at the calc-tools root.  Keep the
# drive-letter form after master_browser relaunches from Y:; resolve()
# expands that mapping back to UNC and breaks deep imports on Windows.
_THIS = pathlib.Path(__file__).absolute()
_CALC_ROOT = _THIS.parent
_SOLVERS = _CALC_ROOT / "solvers_and_topology"
_NUMERICAL = _SOLVERS / "numerical_solvers"
for p in (_CALC_ROOT, _SOLVERS, _NUMERICAL):
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_core_numcalc_pipeline.numcalc_input_cards_reader.calc_json_input_reader import (
    CalcInput, load_calc_input, SUPPORTED_SWEEP_METHODS,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_core_numcalc_pipeline.numcalc_input_cards_reader.card_md_input_reader import resolve_card_source

__all__ = [
    "run_calculation",
    "load_calc_input",
    "resolve_card_source",
    "CalcInput",
    "SUPPORTED_SWEEP_METHODS",
]


# -- Helpers ------------------------------------------------------------

def _apply_concentration_overrides(report, calc: CalcInput) -> None:
    """Mutate the report's total_metals / total_ligands in place.

    Override keys are resolved against, in order:
      1. The component's database id from ``component_meta`` (the
         canonical form ``metal_41`` / ``ligand_5760``).
      2. The component's ``internal_id`` (``Cu$+2``; also matches the
         legacy ``M1`` / ``L1`` placeholders).
      3. The component's display name (with whitespace collapsed).
    Unrecognised keys are rejected.  With redox enabled, an element-level
    total is placed on the reference component and the other valences are
    initialized to zero so the total is not duplicated.  With redox
    excluded, every valence is independent and element-level allocation is
    forbidden; the card must declare each redox-state subtotal.
    """
    import re as _re

    # Reference/free-energy cards are thermodynamic templates, not
    # concentration declarations.  Clear every inherited total before
    # applying the calculation card so legacy cached 1 mM/10 mM values and
    # Atlas-only valence totals cannot leak into a run.  Only actual solver
    # basis ids are materialised: ``component_meta`` also contains bookkeeping
    # placeholders (notably M0=H+ and L0=OH-) that are not analytical totals.
    metal_keys = {
        str(mid) for mid in (getattr(report, "metal_ids", []) or []) if mid
    }
    ligand_keys = {
        str(lid) for lid in (getattr(report, "ligand_ids", []) or []) if lid
    }
    for vg in getattr(report, "valence_groups", []) or []:
        metal_keys.update(
            str(getattr(entry, "internal_id", ""))
            for entry in (getattr(vg, "entries", []) or [])
            if getattr(entry, "internal_id", "")
        )
    # Lightweight/manual reports may not expose the id arrays.  In that
    # compatibility case, their existing total dictionaries are the only
    # available basis declaration; do not apply that fallback when basis ids
    # are present because it would preserve stale placeholders.
    if not metal_keys:
        metal_keys.update(str(key) for key in
                          (getattr(report, "total_metals", {}) or {}))
    if not ligand_keys:
        ligand_keys.update(str(key) for key in
                           (getattr(report, "total_ligands", {}) or {}))

    def _name_key(value: Any) -> str:
        return "".join(str(value or "").split()).casefold()

    metal_name_to_iid = {
        _name_key(name): str(mid)
        for mid, name in zip(
            getattr(report, "metal_ids", []) or [],
            getattr(report, "metal_names", []) or [],
        )
        if mid and name
    }
    ligand_name_to_iid = {
        _name_key(name): str(lid)
        for lid, name in zip(
            getattr(report, "ligand_ids", []) or [],
            getattr(report, "ligand_names", []) or [],
        )
        if lid and name
    }

    # Resolve database aliases onto real basis ids.  Never use a metadata
    # placeholder as a storage key merely because it has a database id.
    metal_dbid_to_iid: Dict[str, str] = {}
    ligand_dbid_to_iid: Dict[str, str] = {}
    for cm in getattr(report, "component_meta", []) or []:
        db_id = str(getattr(cm, "db_id", "") or "").strip()
        if not db_id:
            continue
        ctype = getattr(cm, "comp_type", "")
        meta_iid = str(getattr(cm, "internal_id", "") or "")
        if ctype == "metal":
            target = (meta_iid if meta_iid in metal_keys else
                      metal_name_to_iid.get(_name_key(getattr(cm, "name", ""))))
            if target in metal_keys:
                metal_dbid_to_iid[db_id] = target
        elif ctype == "ligand":
            target = (meta_iid if meta_iid in ligand_keys else
                      ligand_name_to_iid.get(_name_key(getattr(cm, "name", ""))))
            if target in ligand_keys:
                ligand_dbid_to_iid[db_id] = target

    report.total_metals = {key: "Not defined" for key in metal_keys}
    report.total_ligands = {key: "Not defined" for key in ligand_keys}

    _LEGACY_M = _re.compile(r"^M\d+$")
    _LEGACY_L = _re.compile(r"^L\d+$")

    def _number(value: Any, label: str) -> float:
        if value == "Not defined" or isinstance(value, bool):
            raise ValueError(f"{label} is 'Not defined'; declare it in the calculation card")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} must be numeric, got {value!r}") from exc
        if not math.isfinite(number) or number < 0:
            raise ValueError(f"{label} must be finite and >= 0, got {value!r}")
        return number

    redox_groups = list(getattr(report, "valence_groups", []) or [])

    # Canonicalise metal declarations before mutating the report.  Parent
    # element totals, excluded-redox component subtotals, and solve-E state
    # targets are different variables even though legacy cards stored all of
    # them in one ``total_metals`` mirror.
    effective_total_metals = dict(calc.total_metals or {})
    settings = getattr(calc, "settings", None) or {}
    redox_mode = settings.get("redox_mode")
    if redox_mode is None:
        for binding in (getattr(calc, "sweep_constraints", None) or []):
            if isinstance(binding, dict) and binding.get("redox") == "solve":
                redox_mode = "solve"
                break
            if isinstance(binding, dict) and binding.get("redox") == "exclude":
                redox_mode = "excluded"
                break
    if redox_mode is None:
        redox_mode = "included" if calc.include_redox else "excluded"

    for vg in redox_groups:
        entries = list(getattr(vg, "entries", []) or [])
        if len(entries) <= 1:
            continue
        state_ids = [str(entry.internal_id) for entry in entries]
        parent_key = str(getattr(vg, "element", ""))
        parent_present = parent_key in effective_total_metals
        state_present = [key for key in state_ids if key in effective_total_metals]

        if redox_mode == "excluded":
            rank = len(state_present) + (1 if parent_present else 0)
            if rank < len(state_ids):
                raise ValueError(
                    f"redox-excluded metal {parent_key!r} is rank-deficient: "
                    f"declare all state subtotals, or its parent total plus "
                    f"{len(state_ids) - 1} state subtotals")
            if rank > len(state_ids):
                raise ValueError(
                    f"redox-excluded metal {parent_key!r} is over-determined: "
                    "the parent total and every state subtotal are declared")
            if parent_present:
                missing = [key for key in state_ids if key not in state_present]
                parent = _number(
                    effective_total_metals[parent_key],
                    f"metal parent total {parent_key!r}",
                )
                explicit = {
                    key: _number(effective_total_metals[key],
                                 f"metal subtotal {key!r}")
                    for key in state_present
                }
                complement = parent - sum(explicit.values())
                roundoff_tol = 1.0e-12 * max(
                    abs(parent), sum(abs(value) for value in explicit.values()),
                    1.0e-300,
                )
                if (not math.isfinite(complement)
                        or complement < -roundoff_tol):
                    raise ValueError(
                        f"derived metal subtotal {missing[0]!r} is negative "
                        f"({complement!r}); explicit state subtotals exceed "
                        f"parent total {parent_key!r}")
                for key in [parent_key, *state_present]:
                    effective_total_metals.pop(key, None)
                effective_total_metals.update(explicit)
                effective_total_metals[missing[0]] = max(0.0, complement)
        elif redox_mode == "solve":
            # The state subtotal is a Phase-B target, not a conserved basis
            # total.  Only the parent total seeds ``C_total``.
            for key in state_present:
                effective_total_metals.pop(key, None)
        elif state_present:
            raise ValueError(
                f"redox-state subtotal(s) {state_present} over-constrain "
                f"{parent_key!r} when E_V is externally specified; remove "
                "them or use redox_mode='solve' with E_V absent")

    if effective_total_metals:
        for k, v in effective_total_metals.items():
            value = _number(v, f"metal total {k!r}")
            if _LEGACY_M.match(k):
                print(
                    f"[calc-input] WARNING: total_metals key {k!r} uses "
                    f"the legacy 'Mi' placeholder. Prefer the canonical "
                    f"metal internal_id (e.g. 'Cu$+2') or db_id "
                    f"(e.g. 'metal_41')."
                )
            if k in metal_dbid_to_iid:
                report.total_metals[metal_dbid_to_iid[k]] = value
            elif k in report.total_metals:
                report.total_metals[k] = value
            else:
                # Element-level declaration for a multi-valence metal.
                matched = False
                for vg in redox_groups:
                    if str(getattr(vg, "element", "")) != k:
                        continue
                    entries = list(getattr(vg, "entries", []) or [])
                    if not calc.include_redox and len(entries) > 1:
                        raise ValueError(
                            f"metal element total {k!r} cannot be allocated "
                            "when redox is excluded; declare a subtotal for "
                            "every independent redox-state component")
                    for entry in entries:
                        report.total_metals[entry.internal_id] = 0.0
                    report.total_metals[vg.reference_id] = value
                    matched = True
                    break
                # Exact display-name declaration for a single valence.
                for mid, mname in zip(report.metal_ids, report.metal_names):
                    if matched:
                        break
                    if mname == k or mname.replace(" ", "") == k:
                        report.total_metals[mid] = value
                        matched = True
                        break
                if not matched:
                    raise ValueError(
                        f"metal total key {k!r} does not match a declared "
                        "element, redox state, internal id, or database id")

    if calc.total_ligands:
        for k, v in calc.total_ligands.items():
            value = _number(v, f"ligand total {k!r}")
            # ``L1`` is also the report's legitimate internal basis id.  The
            # previous warning ran after canonical db_ids had been compiled
            # to that internal id, so a declaration such as ligand_9058 was
            # falsely reported as user-supplied legacy syntax.  Warn only
            # when an L<n> token is not a declared ligand basis id.
            if _LEGACY_L.match(k) and k not in ligand_keys:
                print(
                    f"[calc-input] WARNING: total_ligands key {k!r} uses "
                    f"the legacy 'Li' placeholder. Prefer the canonical "
                    f"ligand db_id (e.g. 'ligand_5760')."
                )
            if k in ligand_dbid_to_iid:
                report.total_ligands[ligand_dbid_to_iid[k]] = value
            elif k in report.total_ligands:
                report.total_ligands[k] = value
            else:
                matched = False
                for lid, lname in zip(report.ligand_ids, report.ligand_names):
                    if lname == k or lname.replace(" ", "") == k:
                        report.total_ligands[lid] = value
                        matched = True
                        break
                if not matched:
                    raise ValueError(
                        f"ligand total key {k!r} does not match a declared "
                        "ligand internal id, name, or database id")


def _validate_solver_physical_inputs(report, calc: CalcInput) -> None:
    """Definitive no-default gate immediately before numerical assembly."""
    issues = calc.validate()
    if calc.temperature_C is None:
        issues.append("temperature is 'Not defined'")

    def _valid(value: Any) -> bool:
        if value == "Not defined" or isinstance(value, bool):
            return False
        try:
            number = float(value)
        except (TypeError, ValueError):
            return False
        return math.isfinite(number) and number >= 0

    grouped_ids = set()
    for vg in getattr(report, "valence_groups", []) or []:
        ids = [entry.internal_id for entry in vg.entries]
        grouped_ids.update(ids)
        missing = [mid for mid in ids if not _valid(report.total_metals.get(mid))]
        if missing:
            issues.append(
                f"metal element {vg.element!r} has Not defined redox totals: {missing}")
    for mid in getattr(report, "metal_ids", []) or []:
        if mid not in grouped_ids and not _valid(report.total_metals.get(mid)):
            issues.append(f"metal total {mid!r} is 'Not defined'")
    for lid in getattr(report, "ligand_ids", []) or []:
        if not _valid(report.total_ligands.get(lid)):
            issues.append(f"ligand total {lid!r} is 'Not defined'")
    if issues:
        raise ValueError(
            "solver blocked: every physical/model input must be explicitly "
            "declared; no defaults are permitted:\n  - "
            + "\n  - ".join(issues))


def _seed_report_totals_from_constraints(report, calc: CalcInput, compiled) -> None:
    """Evaluate declared dynamic totals at the first grid coordinate.

    Axis/formula totals are genuine declarations.  The numerical system still
    needs a finite baseline before its per-cell wrapper can replace ``C_total``;
    use the explicitly declared first grid coordinate rather than inventing a
    fallback concentration.
    """
    if compiled is None:
        return
    coords = {axis.name: float(axis.min) for axis in calc.sweep_axes}
    try:
        derived = compiled.apply(coords)
    except Exception as exc:
        raise ValueError(
            "could not evaluate declared physical inputs at the first sweep "
            f"coordinate {coords}: {exc}") from exc

    # A Tier-2/Phase-B redox-state subtotal is an observation target for the
    # outer potential solve, not a second conserved component total.  The
    # parent element total supplies C_total; copying the state target into the
    # report here would either replace or double-count that baseline before
    # the outer Brent solve has selected E.
    phase_b_target_keys = {
        str(getattr(pin, "total_key"))
        for pin in (getattr(compiled, "phase_b_pins", []) or [])
        if getattr(pin, "total_key", None)
    }
    excluded_parent_keys = {
        str(plan.parent_total_key)
        for plan in (getattr(compiled, "excluded_complements", []) or [])
    }

    ligand_aliases: set[str] = set()
    ligand_alias_to_token: Dict[str, str] = {}
    cs = (calc.system_catalog.get("chemical_system") or {}
          ) if isinstance(calc.system_catalog, dict) else {}
    for ligand in cs.get("ligands") or []:
        if not isinstance(ligand, dict):
            continue
        for key in ("db_id", "internal_id", "name", "id"):
            if ligand.get(key):
                alias = str(ligand[key])
                ligand_aliases.add(alias)
                ligand_alias_to_token[alias] = str(
                    ligand.get("internal_id") or ligand.get("db_id") or alias)

    metal_alias_to_token: Dict[str, str] = {}
    catalog = getattr(compiled, "catalog", None)
    chemical_system = getattr(catalog, "chemical_system", None)
    for metal in (getattr(chemical_system, "metals", []) or []):
        states = list(dict.fromkeys(getattr(metal, "redox_states", []) or []))
        if getattr(metal, "internal_id", None) and metal.internal_id not in states:
            states.append(metal.internal_id)
        if calc.include_redox and len(states) > 1:
            canonical = str(metal.element)
        elif len(states) == 1:
            canonical = str(states[0])
        else:
            canonical = str(metal.element)
        for alias in (getattr(metal, "element", None),
                      getattr(metal, "name", None),
                      getattr(metal, "db_id", None),
                      getattr(metal, "internal_id", None)):
            if alias:
                metal_alias_to_token[str(alias)] = canonical
        for state in states:
            metal_alias_to_token[str(state)] = (
                canonical if calc.include_redox else str(state))

    dynamic_metals: Dict[str, float] = {}
    dynamic_ligands: Dict[str, float] = {}
    for key, value in derived.items():
        if not (isinstance(key, str) and key.startswith("[")
                and key.endswith("]_total")):
            continue
        if key in phase_b_target_keys or key in excluded_parent_keys:
            continue
        token = key[1:-len("]_total")]
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"declared total {key} evaluated to nonnumeric {value!r}") from exc
        if not math.isfinite(number) or number < 0:
            raise ValueError(
                f"declared total {key} evaluated to invalid value {value!r}")
        if token in ligand_aliases:
            dynamic_ligands[ligand_alias_to_token.get(token, token)] = number
        else:
            dynamic_metals[metal_alias_to_token.get(token, token)] = number

    # A Tier-2 species target replaces one analytical-total declaration.  Its
    # declared concentration supplies a deterministic numerical starting
    # value for the released total; the augmented Newton system remains free
    # to solve the actual total.  This is initialization derived from the
    # user's constraint, not a physical default.
    for pin in (getattr(compiled, "species_pins", []) or []):
        raw = float(pin.target_closure(derived))
        concentration = math.exp(raw) if pin.kind == "lnconc" else raw
        if not math.isfinite(concentration) or concentration <= 0:
            raise ValueError(
                f"species pin {pin.species_id!r} evaluates to invalid "
                f"concentration {concentration!r} at {coords}")
        token = str(pin.released_component_token)
        if token in ligand_aliases:
            dynamic_ligands[ligand_alias_to_token.get(token, token)] = concentration
        else:
            dynamic_metals[metal_alias_to_token.get(token, token)] = concentration

    from types import SimpleNamespace
    _apply_concentration_overrides(
        report,
        SimpleNamespace(total_metals=dynamic_metals,
                        total_ligands=dynamic_ligands,
                        include_redox=calc.include_redox),
    )


def _principal_component_map(
    report, species_ids: Optional[set[str]] = None,
) -> Dict[str, str]:
    """Resolve unambiguous species pins to one released component.

    Automatic release is intentionally conservative.  A species carrying
    exactly one conserved metal/ligand component can release that component's
    total.  A complex carrying two or more components is ambiguous and is
    rejected instead of silently choosing a mass balance for the user.
    """
    wanted = set(species_ids or ())
    include_redox = getattr(report, "include_redox", "Not defined")
    if not isinstance(include_redox, bool):
        raise ValueError("redox mode is 'Not defined' while resolving species pins")

    state_to_component: Dict[str, str] = {}
    grouped: set[str] = set()
    for group in (getattr(report, "valence_groups", []) or []):
        states = [str(entry.internal_id) for entry in group.entries]
        grouped.update(states)
        for state in states:
            state_to_component[state] = (
                str(group.element) if include_redox else state)
    for metal_id in (getattr(report, "metal_ids", []) or []):
        token = str(metal_id)
        if token not in grouped:
            state_to_component[token] = token
    ligand_tokens = {
        str(token) for token in (getattr(report, "ligand_ids", []) or [])
    }

    result: Dict[str, str] = {}
    seen: set[str] = set()
    for species in (getattr(report, "species", []) or []):
        sid = str(getattr(species, "species_id", "") or "")
        if wanted and sid not in wanted:
            continue
        seen.add(sid)
        if getattr(species, "phase", "aqueous") != "aqueous":
            raise ValueError(
                f"species pin {sid!r} targets a non-aqueous phase; only "
                "aqueous concentration pins are supported")
        candidates: set[str] = set()
        for token, coefficient in (
                dict(getattr(species, "stoich", None) or {}).items()):
            try:
                present = abs(float(coefficient)) > 0.0
            except (TypeError, ValueError):
                present = False
            if not present:
                continue
            key = str(token)
            if key in state_to_component:
                candidates.add(state_to_component[key])
            elif key in ligand_tokens:
                candidates.add(key)
        if len(candidates) != 1:
            reason = "no conserved component" if not candidates else (
                f"multiple candidate components {sorted(candidates)}")
            raise ValueError(
                f"species pin {sid!r} has {reason}; automatic total release "
                "requires exactly one component")
        result[sid] = next(iter(candidates))

    missing = wanted - seen
    if missing:
        raise ValueError(
            f"species pin target(s) are absent from the aqueous report: "
            f"{sorted(missing)}")
    return result


def _apply_redox_setting(report, calc: CalcInput) -> None:
    """Attach the calc-input ``include_redox`` flag onto the report.

    When ``False``, the system builder retains every declared metal valence
    as an independent conserved component.  Each valence has its own zero
    reference: there is no inter-valence free-energy alignment, no derived
    Nernst coupling, and no potential coordinate.  A declared zero-total
    valence is retained because a dynamic sweep may make it positive later.
    """
    if not isinstance(calc.include_redox, bool):
        raise ValueError(
            "redox mode is 'Not defined'; include_redox must be an explicit boolean")
    setattr(report, "include_redox", calc.include_redox)


def _apply_environment_overrides(report, calc: CalcInput) -> None:
    """Apply explicitly declared thermodynamic/model settings to *report*."""
    if not isinstance(calc.use_activity, bool):
        raise ValueError("use_activity must be an explicitly declared boolean")
    if not isinstance(calc.include_solids, bool):
        raise ValueError("include_solids must be an explicitly declared boolean")
    spec = calc.ionic_strength
    if spec.mode == "none":
        # Disable activity by setting mode to fixed at I=0; downstream
        # solvers also receive use_activity=False.
        report.ionic_strength = 0.0
        report.ionic_mode = "fixed"
    else:
        report.ionic_strength = float(spec.value)
        report.ionic_mode = spec.mode
    # Only ideal and Davies are currently implemented.  Card validation
    # rejects Debye-Huckel before this adapter, so the legacy boolean mirror is
    # an unambiguous model selector rather than a truthiness fallback.
    report.activity_model = "davies" if calc.use_activity else "ideal"
    report.include_solids = calc.include_solids
    if calc.temperature_C is not None:
        report.temperature_C = float(calc.temperature_C)
        report.temperature_K = float(calc.temperature_C) + 273.15


# -- Calc-input -> run_sweep kwargs -------------------------------------

def _build_sweep_params(calc: CalcInput) -> Dict[str, Any]:
    """Translate CalcInput axis/option fields into run_sweep kwargs.

    The resulting dict is passed verbatim as ``**sweep_params`` to
    ``run_sweep``, which forwards them to the per-method handler.
    """
    if not isinstance(calc.use_activity, bool):
        raise ValueError("use_activity must be an explicitly declared boolean")
    if not isinstance(calc.include_solids, bool):
        raise ValueError("include_solids must be an explicitly declared boolean")
    if not isinstance(calc.include_redox, bool):
        raise ValueError("include_redox must be an explicitly declared boolean")
    params: Dict[str, Any] = {
        "use_activity":   calc.use_activity
                           and calc.ionic_strength.mode != "none",
        "include_solids": calc.include_solids,
    }

    method = calc.sweep_method

    if method == "pH_sweep":
        pH_axis = calc.axis_or_default("pH")
        params["pH_range"] = pH_axis.as_range()
        params["n_points"] = int(pH_axis.n_points)

    elif method in ("pourbaix_sweep", "pourbaix"):
        if not calc.include_redox:
            raise ValueError(
                "pourbaix_sweep is incompatible with redox_mode='excluded': "
                "E_V must be absent in that mode; use pH_sweep or another "
                "potential-free route")
        # Unified N-D Pourbaix branch.  ``pH`` and ``E_V`` must both be
        # explicitly declared; ``a_w`` is opt-in: declare an
        # ``a_w`` axis in the CalcInput to upgrade the sweep to 3-D.
        for axis_name, range_key, n_key in (
            ("pH",  "pH_range", "n_pH"),
            ("E_V", "E_range",  "n_E"),
            ("a_w", "aw_range", "n_aw"),
        ):
            axis_spec = calc.axis(axis_name)
            if axis_spec is None:
                if axis_name in ("pH", "E_V"):
                    axis_spec = calc.axis_or_default(axis_name)
                else:
                    continue
            params[range_key] = axis_spec.as_range()
            params[n_key]     = int(axis_spec.n_points)
        params["n_layers"] = calc.grid_refine.n_layers
        params["refine_factor"] = calc.grid_refine.factor

    elif method in ("freeform_sweep", "freeform"):
        # Catch-all N-D handler.  Forward every declared sweep axis as
        # a dict to the freeform handler (which coerces to GridAxis).
        params["axes"] = [
            {"name": ax.name,
             "min":  float(ax.min),
             "max":  float(ax.max),
             "n_points": int(ax.n_points)}
            for ax in calc.sweep_axes
        ]
        params["n_layers"] = calc.grid_refine.n_layers
        params["refine_factor"] = calc.grid_refine.factor

    elif method in ("titration_sweep", "titration"):
        # Titration: forward the single added-volume axis (its name
        # identifies the titrant component) plus any titration metadata
        # the card carries.  The handler builds the dilution model.
        params["axes"] = [
            {"name": ax.name,
             "min":  float(ax.min),
             "max":  float(ax.max),
             "n_points": int(ax.n_points)}
            for ax in calc.sweep_axes
        ]
        env = getattr(calc, "environment", None)
        for key in ("volume_initial_mL", "titrant_conc", "fixed_pH"):
            val = getattr(calc, key, None)
            if val is None:
                val = (calc.extras or {}).get(key)
            if val is None and isinstance(env, dict):
                val = env.get(key)
            if val is None or val == "Not defined":
                raise ValueError(
                    f"titration physical input {key!r} is 'Not defined'")
            params[key] = float(val)

    # (no extra kwargs for any remaining methods)

    return params

# ── Public entry point ───────────────────────────────────────────

def run_calculation(
    card_source: Union[str, pathlib.Path, dict, Any],
    calc_input: Union[str, pathlib.Path, dict, CalcInput],
    *,
    output_dir: Optional[Union[str, pathlib.Path]] = None,
    debug: bool = False,
) -> Dict[str, Any]:
    """Run a calculation end-to-end via the unified sweep dispatcher.

    The resolved ``FreeEnergyReport`` (with environment / concentration
    overrides from ``calc_input`` applied) is forwarded to
    ``sweep_pipelines._sweep_input_entry_point.run_sweep`` with
    ``sweep_type=calc_input.sweep_method``.  All per-method logic lives
    in the dispatcher; this function only adapts the ``CalcInput``
    schema into ``run_sweep`` keyword arguments.
    """
    from sweep_pipelines._sweep_input_entry_point import run_sweep

    # Normalise the calc-modes input.
    if isinstance(calc_input, CalcInput):
        calc = calc_input
    else:
        calc = load_calc_input(calc_input)

    direct_issues = calc.validate()
    if direct_issues:
        raise ValueError(
            "Invalid calculation input; no solver defaults are permitted:\n  - "
            + "\n  - ".join(direct_issues))

    # Resolve & customise the card.
    report = resolve_card_source(
        card_source, temperature_K=calc.temperature_K,
    )
    _apply_environment_overrides(report, calc)
    _apply_redox_setting(report, calc)

    # Output dir: explicit arg > calc_input.output_dir > None
    od = (str(pathlib.Path(output_dir).resolve())
          if output_dir is not None else calc.output_dir)
    if od is not None:
        pathlib.Path(od).mkdir(parents=True, exist_ok=True)

    iso = calc.ionic_strength
    I_arg = None if iso.mode == "none" else float(iso.value)

    sweep_params = _build_sweep_params(calc)

    # ── Schema-v2: build catalog + compile constraints ────────────
    # Legacy JSONs reach this point already translated via the shim
    # in ``load_calc_input``; ``calc.system_catalog`` and
    # ``calc.sweep_constraints`` are populated for both paths.
    compiled = None
    try:
        from sweep_pipelines._sweep_input_entry_point.constraint_compiler import (
            build_default_catalog, merge_catalog_overrides,
            validate_catalog_against_report, compile_constraints,
            compile_spec,
        )
        default_cat = build_default_catalog(report)
        catalog = merge_catalog_overrides(default_cat,
                                          calc.system_catalog or {})
        validate_catalog_against_report(catalog, report)
        axis_names = [a.name for a in calc.sweep_axes]
        if calc.spec is not None:
            # Native lc3_2.v1 path -- no dict-shape intermediate.
            settings = calc.settings or {}
            pins_allowed = (str(settings.get("species_pins", "disabled"))
                            == "allowed")
            pin_species_ids = {
                str(lhs.get("id"))
                for bind in (calc.spec.get("binds") or [])
                if isinstance(bind, dict)
                for lhs in [bind.get("lhs") or {}]
                if lhs.get("ref") in ("species", "conc", "lnconc")
                and lhs.get("id")
            }
            comp_of_species = (
                _principal_component_map(report, pin_species_ids)
                if pins_allowed and pin_species_ids else None)
            compiled = compile_spec(
                catalog, axis_names, calc.spec, settings,
                component_of_species=comp_of_species,
                species_pins_allowed=pins_allowed,
            )
        else:
            bindings = list(calc.sweep_constraints or [])
            # Direct/manual CalcInput callers may populate the compatibility
            # total mirrors without a native spec.  Promote those explicit
            # declarations into the same canonical binding stream before DOF
            # analysis; never mutate report totals ahead of compilation.
            existing_lhs: set[str] = set()
            for binding in bindings:
                if isinstance(binding, dict):
                    existing_lhs.update(str(key) for key in binding)
                elif isinstance(binding, str) and "=" in binding:
                    existing_lhs.add(binding.split("=", 1)[0].strip())
            for key, value in calc.total_metals.items():
                lhs = f"[{key}]_total"
                if lhs not in existing_lhs:
                    bindings.append({lhs: value})
                    existing_lhs.add(lhs)
            for key, value in calc.total_ligands.items():
                lhs = f"[{key}]_total"
                if lhs not in existing_lhs:
                    bindings.append({lhs: value})
                    existing_lhs.add(lhs)
            if "redox" not in existing_lhs:
                bindings.append({
                    "redox": "include" if calc.include_redox else "exclude"
                })
            compiled = compile_constraints(catalog, axis_names, bindings)
    except Exception as exc:
        # Fail loud — constraint compilation is now part of the
        # canonical input path.  Legacy callers passing only legacy
        # fields will have a valid (empty) constraint set after the
        # shim translation; any error here indicates a real problem
        # with the input.
        raise ValueError(
            f"Constraint compilation failed: {exc}") from exc

    _seed_report_totals_from_constraints(report, calc, compiled)
    _validate_solver_physical_inputs(report, calc)

    result = run_sweep(
        report,
        sweep_type=calc.sweep_method,
        output_dir=od,
        ionic_strength=I_arg,
        debug=debug,
        compiled_constraints=compiled,
        **sweep_params,
    )

    result.setdefault("report", report)
    result["sweep_method"] = calc.sweep_method
    result["calc_input"]   = calc
    result["output_dir"]   = od
    return result

