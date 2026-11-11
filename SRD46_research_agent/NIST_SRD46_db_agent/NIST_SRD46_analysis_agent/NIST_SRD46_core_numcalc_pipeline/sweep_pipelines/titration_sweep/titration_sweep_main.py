"""
Titration Sweep Main — incremental titrant addition with dilution.
==================================================================
Simulates adding a titrant to a fixed-volume solution and tracks
speciation as a function of the added titrant volume.

The titration is modelled as a 1-D sweep over the *added volume*
``V_added_mL`` and is solved through the **same** unified solver / N-D
grid / export pipeline as the freeform sweep.  The only titration-
specific logic lives here, in the construction of the per-cell totals:

    f(V)             = V0 / (V0 + V)          # dilution factor
    [analyte]_tot(V) = [analyte]_0 * f(V)     # every pre-loaded total dilutes
    [titrant]_tot(V) = C_titrant * V / (V0 + V)

These relations are emitted as *formula bindings* against the
``V_added_mL`` axis and compiled with the standard constraint compiler,
so the freeform solver drives them per cell with no bespoke solver code.

Notes / current limitations
---------------------------
* Speciation is evaluated at an explicitly declared **fixed pH**.  A true
  free-pH titration (solving pH from proton/charge balance as base is
  added) needs a charge-balance solver mode that is not yet available;
  this handler therefore reports speciation vs. added titrant at a
  pinned pH rather than a full pH-vs-volume titration curve.
* The titrant identity is taken from the single declared sweep axis
  (the LC3 card names that axis after the titrant component id, e.g.
  ``ligand_10076`` for hydroxide).  If it does not resolve to a catalog
  component the sweep still runs as a pure dilution scan.

Public API
----------
- ``run_titration_sweep`` — canonical entry point.
"""
from __future__ import annotations

import pathlib
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np


SWEEP_ID = "titration_sweep"
SWEEP_DESCRIPTION = (
    "Titration sweep: simulate incremental addition of a titrant to "
    "a fixed-volume solution, tracking speciation vs. added volume "
    "(with dilution of pre-loaded totals)."
)
SWEEP_PARAMS = {
    "axes":               {"type": "list[dict]", "required": True,
                           "description": "Single added-volume axis spec "
                                          "{name, min, max, n_points}."},
    "volume_initial_mL":  {"type": "float", "required": True,
                           "description": "Initial solution volume V0 (mL)."},
    "titrant_conc":       {"type": "float", "required": True,
                           "description": "Titrant stock concentration (mol/L)."},
    "fixed_pH":           {"type": "float", "required": True,
                           "description": "pH at which speciation is evaluated."},
}


# ------------------------------------------------------------------
#  Helpers
# ------------------------------------------------------------------

def _token_of_total_key(key: str) -> Optional[str]:
    """``"[ligand_5937]_total"`` -> ``"ligand_5937"`` (else ``None``)."""
    if key.startswith("[") and key.endswith("]_total"):
        return key[1:-len("]_total")]
    return None


def _resolve_titrant_token(axis_name: str, catalog: Any) -> Optional[str]:
    """Match the declared axis name to a catalog component token.

    The LC3 titration card names the swept axis after the titrant
    component id (a metal element / redox-state id or a ligand db_id /
    internal_id).  Return the token if it resolves, else ``None``.
    """
    name = (axis_name or "").strip()
    if not name:
        return None
    cs = getattr(catalog, "chemical_system", None)
    if cs is None:
        return None
    for m in getattr(cs, "metals", []) or []:
        if name in ({m.element, m.name, m.internal_id} | set(m.redox_states or [])):
            return name
    for L in getattr(cs, "ligands", []) or []:
        if name in {L.db_id, L.internal_id, L.name}:
            return name
    return None


def _extract_base_totals(compiled_constraints: Any) -> Dict[str, float]:
    """Pull the pre-loaded ``[token]_total`` values from the card.

    Evaluates the incoming compiled constraints with no axis coordinates
    (the card's analyte totals are plain scalar binds) and returns
    ``{token: value}`` for every ``[token]_total`` present.
    """
    out: Dict[str, float] = {}
    if compiled_constraints is None:
        return out
    try:
        env = compiled_constraints.apply({})
    except Exception:
        return out
    for key, val in env.items():
        tok = _token_of_total_key(str(key))
        if tok is not None and isinstance(val, (int, float)):
            out[tok] = float(val)
    # Excluded-redox complement plans expose both the parent equation and
    # every derived state subtotal in ``apply``.  Downstream recompilation
    # must carry the independent state totals only, not the redundant parent.
    for plan in (getattr(compiled_constraints, "excluded_complements", []) or []):
        parent_key = str(plan.parent_total_key)
        tok = _token_of_total_key(parent_key)
        if tok is not None:
            out.pop(tok, None)
    return out


# ------------------------------------------------------------------
#  Public API
# ------------------------------------------------------------------

def run_titration_sweep(
    report,
    *,
    axes: Optional[Sequence[Any]] = None,
    output_dir: Optional[Union[str, pathlib.Path]] = None,
    ionic_strength: Optional[float] = None,
    temperature_K: Optional[float] = None,
    volume_initial_mL: Optional[float] = None,
    titrant_conc: Optional[float] = None,
    fixed_pH: Optional[float] = None,
    debug: bool = False,
    prefix: Optional[str] = None,
    compiled_constraints: Optional[Any] = None,
    **_ignored,
) -> Dict[str, Any]:
    """Run a 1-D titration (added-volume) sweep with dilution.

    Parameters
    ----------
    report
        Resolved ``FreeEnergyReport`` (totals already applied).
    axes
        One axis spec ``{name, min, max, n_points}`` describing the
        added-volume range; ``name`` identifies the titrant component.
    volume_initial_mL
        Initial solution volume ``V0`` (mL) for the dilution model.
    titrant_conc
        Titrant stock concentration (mol/L).
    fixed_pH
        pH at which speciation is evaluated (see module note).
    compiled_constraints
        The card's compiled constraints — used only to read the
        pre-loaded analyte totals and the component catalog.

    Returns
    -------
    dict
        The freeform-sweep result bundle (``report``, ``built``,
        ``grid``, ``per_element``, ``topologies``, ``output_paths``).
    """
    from sweep_pipelines.freeform_sweep.freeform_sweep_main import (
        run_freeform_sweep,
    )
    from sweep_pipelines._sweep_input_entry_point.constraint_compiler import (
        build_default_catalog,
        compile_constraints,
    )

    if not axes:
        raise ValueError(
            "titration_sweep requires one added-volume axis "
            "({name, min, max, n_points}).")
    a0 = axes[0]
    if not isinstance(a0, dict):
        raise ValueError(
            f"titration_sweep axis must be a dict spec; got {type(a0).__name__}")
    lo_raw = a0.get("min", a0.get("low", "Not defined"))
    hi_raw = a0.get("max", a0.get("high", "Not defined"))
    n_raw = a0.get("n_points", a0.get("n", "Not defined"))
    if "Not defined" in (lo_raw, hi_raw, n_raw):
        raise ValueError(
            "titration axis min, max, and n_points must all be declared")
    if any(isinstance(value, bool) for value in (lo_raw, hi_raw, n_raw)):
        raise ValueError("titration axis numeric fields cannot be booleans")
    v_min = float(lo_raw)
    v_max = float(hi_raw)
    n_pts = int(n_raw)
    if (not np.isfinite(v_min) or not np.isfinite(v_max)
            or v_max <= v_min or n_pts < 2):
        raise ValueError(
            "titration axis must have finite increasing bounds and n_points >= 2")
    titrant_axis_name = str(a0.get("name", "")).strip()
    if not titrant_axis_name:
        raise ValueError("titration axis name is 'Not defined'")

    AX = "V_added_mL"
    if any(value is None for value in (volume_initial_mL, titrant_conc, fixed_pH)):
        raise ValueError(
            "titration physical inputs volume_initial_mL, titrant_conc, and "
            "fixed_pH must all be explicitly declared")
    if any(isinstance(value, bool)
           for value in (volume_initial_mL, titrant_conc, fixed_pH)):
        raise ValueError("titration physical inputs cannot be booleans")
    V0 = float(volume_initial_mL)
    if V0 <= 0.0:
        raise ValueError(f"volume_initial_mL must be > 0; got {V0!r}")
    titrant_conc = float(titrant_conc)
    fixed_pH = float(fixed_pH)
    if (not np.isfinite(V0) or not np.isfinite(titrant_conc)
            or titrant_conc < 0 or not np.isfinite(fixed_pH)):
        raise ValueError(
            "titration physical inputs must be finite and titrant_conc >= 0")

    catalog = (getattr(compiled_constraints, "catalog", None)
               or build_default_catalog(report))
    base_totals = _extract_base_totals(compiled_constraints)
    titrant_token = _resolve_titrant_token(titrant_axis_name, catalog)

    # Build the per-cell totals as formula bindings against the volume
    # axis: every pre-loaded total dilutes; the titrant total grows.  The
    # redox declaration is part of the physical model, so preserve it when
    # recompiling instead of allowing ``compile_constraints`` to infer its
    # historical redox-enabled default.
    include_redox = getattr(report, "include_redox", "Not defined")
    if not isinstance(include_redox, bool):
        raise ValueError(
            "redox mode is 'Not defined' on the solver report; declare "
            "redox_mode explicitly before running a titration sweep"
        )
    dilution = f"({V0!r} / ({V0!r} + {AX}))"
    redox_binding = (
        "solve"
        if getattr(compiled_constraints, "phase_b_pins", None)
        else ("include" if include_redox else "exclude")
    )
    binds: List[Any] = [
        {"redox": redox_binding},
        {"pH": float(fixed_pH)},
    ]
    for token, base in base_totals.items():
        if titrant_token is not None and token == titrant_token:
            continue
        binds.append({f"[{token}]_total": f"{float(base)!r} * {dilution}"})
    if titrant_token is not None:
        binds.append({
            f"[{titrant_token}]_total":
                f"{float(titrant_conc)!r} * {AX} / ({V0!r} + {AX})"
        })

    compiled = compile_constraints(catalog, [AX], binds)

    if debug:
        print(f"[titration_sweep] titrant={titrant_token!r} "
              f"V0={V0} mL  C_titrant={titrant_conc} M  "
              f"V_added=[{v_min}, {v_max}] mL  n={n_pts}  pH={fixed_pH}")
        diluted = [t for t in base_totals if t != titrant_token]
        print(f"[titration_sweep] diluted totals: {diluted}")

    volume_axis = {
        "name": AX,
        "min": v_min,
        "max": v_max,
        "n_points": n_pts,
        "display_label": "V added (mL)",
    }

    return run_freeform_sweep(
        report,
        axes=[volume_axis],
        output_dir=output_dir,
        ionic_strength=ionic_strength,
        temperature_K=temperature_K,
        refine_factor=None,
        n_layers=0,
        debug=debug,
        prefix=prefix,
        compiled_constraints=compiled,
    )


sweep_fn = run_titration_sweep

