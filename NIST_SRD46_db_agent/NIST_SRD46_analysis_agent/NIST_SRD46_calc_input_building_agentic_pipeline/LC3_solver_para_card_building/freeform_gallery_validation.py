"""Deterministic, no-network solve checks for canonical freeform galleries.

The gallery Markdown is generic guidance, but every canonical gallery ID is
paired with a tiny concrete calculation having the same axis/constraint
structure.  These checks enter through the real public numerical API and are
used by the registry audit in debug mode and by permanent regression tests.
They never call an LLM, Argo, SRD retrieval, or an external database.
"""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple


CANONICAL_GALLERY_IDS: Tuple[str, ...] = (
    "concentration-ph-fixed-ratio-map",
    "conserved-moles-dilution-path",
    "fixed-ph-concentration-ratio-path",
    "multidimensional-ph-temperature-composition",
    "nernst-coupled-ph-path",
    "redox-excluded-parent-plus-state",
    "redox-solved-state-target",
    "two-inventory-axis-map",
)

T_K = 298.15


@lru_cache(maxsize=1)
def _core_symbols() -> Dict[str, Any]:
    """Import the local numerical API lazily to keep normal routing cheap."""
    analysis_root = Path(__file__).resolve().parents[2]
    core_root = analysis_root / "NIST_SRD46_core_numcalc_pipeline"
    if str(core_root) not in sys.path:
        sys.path.insert(0, str(core_root))

    import numpy as np
    from SRD46_numcalculator_api import run_calculation
    from thermodynamics_helpers.gibbs_value_calc_from_logK_eq_map_helpers.free_energy_network_calc_helper import (
        FreeEnergyReport,
        SpeciesEnergy,
        ValenceGroup,
        ValenceGroupEntry,
    )

    return {
        "np": np,
        "run_calculation": run_calculation,
        "FreeEnergyReport": FreeEnergyReport,
        "SpeciesEnergy": SpeciesEnergy,
        "ValenceGroup": ValenceGroup,
        "ValenceGroupEntry": ValenceGroupEntry,
    }


def _species(species_id: str, token: str, charge: int) -> Any:
    symbols = _core_symbols()
    return symbols["SpeciesEnergy"](
        species_id=species_id,
        original_id=species_id,
        label=species_id,
        stoich={token: 1},
        charge=charge,
        phase="aqueous",
        log_beta=0.0,
        app_log_beta=0.0,
        mu0_free=0.0,
        mu0_canonical=0.0,
        mu_aligned=0.0,
        include=True,
    )


def _report(*, redox_pair: bool) -> Any:
    symbols = _core_symbols()
    np = symbols["np"]
    factor = np.log(10.0) * 8.314e-3 * T_K
    if redox_pair:
        metal_ids = ["Fe$+2", "Fe$+3"]
        metal_names = ["Fe2+", "Fe3+"]
        metal_charges = {"Fe$+2": 2, "Fe$+3": 3}
        species = [
            _species("Fe2_aq", "Fe$+2", 2),
            _species("Fe3_aq", "Fe$+3", 3),
        ]
        entries = [
            symbols["ValenceGroupEntry"](
                internal_id="Fe$+2", name="Fe2+", charge=2,
                is_reference=True,
            ),
            symbols["ValenceGroupEntry"](
                internal_id="Fe$+3", name="Fe3+", charge=3,
                is_reference=False,
            ),
        ]
        valence_groups = [symbols["ValenceGroup"](
            element="Fe",
            entries=entries,
            reference_id="Fe$+2",
            n_valences=2,
        )]
        ligand_ids = []
        ligand_names = []
        ligand_charges: Dict[str, int] = {}
    else:
        metal_ids = ["Cu$+2"]
        metal_names = ["Cu2+"]
        metal_charges = {"Cu$+2": 2}
        species = [
            _species("Cu_aq", "Cu$+2", 2),
            _species("L_aq", "ligand_5760", 0),
        ]
        valence_groups = []
        ligand_ids = ["ligand_5760"]
        ligand_names = ["Glycine"]
        ligand_charges = {"ligand_5760": 0}

    return symbols["FreeEnergyReport"](
        temperature_K=T_K,
        temperature_C=T_K - 273.15,
        RT=8.314e-3 * T_K,
        factor=factor,
        Kw_log=-14.0,
        species=species,
        reactions=[],
        canonical_info={},
        rulebook=None,
        metal_ids=metal_ids,
        ligand_ids=ligand_ids,
        metal_names=metal_names,
        ligand_names=ligand_names,
        total_metals={token: "Not defined" for token in metal_ids},
        total_ligands={token: "Not defined" for token in ligand_ids},
        ionic_strength="Not defined",
        ionic_mode="Not defined",
        metal_charges=metal_charges,
        ligand_charges=ligand_charges,
        valence_groups=valence_groups,
        redox_couples=[],
    )


def _bind(ref: str, rhs: Mapping[str, Any],
          component_id: str | None = None) -> Dict[str, Any]:
    lhs: Dict[str, Any] = {"ref": ref}
    if component_id is not None:
        lhs["id"] = component_id
    return {"op": "==", "lhs": lhs, "rhs": dict(rhs)}


def _const(value: float) -> Dict[str, float]:
    return {"const": float(value)}


def _axis(name: str) -> Dict[str, str]:
    return {"axis": name}


def _op(operator: str, *args: Mapping[str, Any]) -> Dict[str, Any]:
    return {"op": operator, "args": [dict(arg) for arg in args]}


def _single_system_catalog() -> Dict[str, Any]:
    return {
        "chemical_system": {
            "metals": [{
                "name": "Cu", "element": "Cu", "internal_id": "Cu$+2",
                "redox_states": ["Cu$+2"],
            }],
            "ligands": [{
                "name": "Glycine", "db_id": "ligand_5760",
                "internal_id": "ligand_5760", "smiles": "NCC(=O)O",
            }],
        },
    }


def _redox_system_catalog() -> Dict[str, Any]:
    return {
        "chemical_system": {
            "metals": [{
                "name": "Fe", "element": "Fe", "internal_id": "Fe$+2",
                "redox_states": ["Fe$+2", "Fe$+3"],
            }],
            "ligands": [],
        },
    }


def _card(
    *,
    axes: Sequence[str],
    sweep_axes: Sequence[Mapping[str, Any]],
    binds: Sequence[Mapping[str, Any]],
    redox_mode: str,
    ionic_strength_mode: str,
    redox_pair: bool = False,
    activity_model: str = "ideal",
) -> Dict[str, Any]:
    return {
        "sweep_method": "freeform_sweep",
        "system_catalog": (
            _redox_system_catalog() if redox_pair
            else _single_system_catalog()
        ),
        "constraint_settings": {
            "activity_model": activity_model,
            "solids": "exclude",
            "redox_mode": redox_mode,
            "ionic_strength_mode": ionic_strength_mode,
        },
        "constraint_spec": {
            "schema_version": "lc3_2.v1",
            "axes": list(axes),
            "dof": {
                "K": len(binds),
                "charge_balance_enforced": False,
            },
            "lets": {},
            "binds": [dict(item) for item in binds],
        },
        "sweep_axes": [dict(item) for item in sweep_axes],
        "grid_refine": {"mode": "none"},
    }


def _single_case(gallery_id: str) -> Tuple[Dict[str, Any], Tuple[int, ...]]:
    t_bind = _bind("temperature", _const(T_K))
    i_bind = _bind("ionic_strength", _const(0.1))
    ph_fixed = _bind("pH", _const(7.0))
    e_fixed = _bind("E_V", _const(0.25))

    if gallery_id == "nernst-coupled-ph-path":
        binds = [
            _bind("pH", _axis("pH_axis")),
            _bind("E_V", _op("*", _const(-0.059), _axis("pH_axis"))),
            t_bind,
            i_bind,
            _bind("total", _const(1.0e-3), "Cu"),
            _bind("total", _const(1.0e-2), "ligand_5760"),
        ]
        card = _card(
            axes=["pH_axis"],
            sweep_axes=[{"name": "pH", "min": 6.0, "max": 8.0,
                         "n_points": 3}],
            binds=binds,
            redox_mode="freeform",
            ionic_strength_mode="fixed",
            activity_model="davies",
        )
        return card, (3,)

    if gallery_id == "fixed-ph-concentration-ratio-path":
        binds = [
            _bind("total", _axis("Cu_total_axis"), "Cu"),
            _bind("total", _op("*", _const(10.0),
                                {"ref": "total", "id": "Cu"}),
                  "ligand_5760"),
            ph_fixed, e_fixed, t_bind, i_bind,
        ]
        card = _card(
            axes=["Cu_total_axis"],
            sweep_axes=[{"name": "Cu", "min": 1.0e-4, "max": 2.0e-4,
                         "n_points": 2}],
            binds=binds,
            redox_mode="fixed",
            ionic_strength_mode="fixed",
            activity_model="davies",
        )
        return card, (2,)

    if gallery_id == "concentration-ph-fixed-ratio-map":
        binds = [
            _bind("pH", _axis("pH_axis")),
            _bind("total", _axis("Cu_total_axis"), "Cu"),
            _bind("total", _op("*", _const(2.0),
                                {"ref": "total", "id": "Cu"}),
                  "ligand_5760"),
            t_bind,
        ]
        card = _card(
            axes=["pH_axis", "Cu_total_axis"],
            sweep_axes=[
                {"name": "pH", "min": 6.0, "max": 8.0, "n_points": 2},
                {"name": "Cu", "min": 1.0e-4, "max": 2.0e-4,
                 "n_points": 2},
            ],
            binds=binds,
            redox_mode="excluded",
            ionic_strength_mode="auto",
        )
        return card, (2, 2)

    if gallery_id == "conserved-moles-dilution-path":
        denominator = _op(
            "+", _const(0.100),
            _op("*", _const(1.0e-3), _axis("V_added_mL")),
        )
        binds = [
            _bind("total", _op("/", _const(1.0e-4), denominator), "Cu"),
            _bind("total", _op("/", _const(2.0e-4), denominator),
                  "ligand_5760"),
            ph_fixed,
            t_bind,
        ]
        card = _card(
            axes=["V_added_mL"],
            sweep_axes=[{"name": "V_added_mL", "min": 0.0, "max": 10.0,
                         "n_points": 2}],
            binds=binds,
            redox_mode="excluded",
            ionic_strength_mode="auto",
        )
        return card, (2,)

    if gallery_id == "multidimensional-ph-temperature-composition":
        binds = [
            _bind("pH", _axis("pH_axis")),
            _bind("temperature", _axis("temperature_axis")),
            _bind("total", _axis("Cu_total_axis"), "Cu"),
            _bind("total", _op("*", _const(2.0),
                                {"ref": "total", "id": "Cu"}),
                  "ligand_5760"),
        ]
        card = _card(
            axes=["pH_axis", "temperature_axis", "Cu_total_axis"],
            sweep_axes=[
                {"name": "pH", "min": 6.0, "max": 8.0, "n_points": 2},
                {"name": "temperature", "min": 293.15, "max": 303.15,
                 "n_points": 2},
                {"name": "Cu", "min": 1.0e-4, "max": 2.0e-4,
                 "n_points": 2},
            ],
            binds=binds,
            redox_mode="excluded",
            ionic_strength_mode="auto",
        )
        return card, (2, 2, 2)

    if gallery_id == "two-inventory-axis-map":
        binds = [
            _bind("total", _axis("Cu_total_axis"), "Cu"),
            _bind("total", _axis("glycine_total_axis"), "ligand_5760"),
            ph_fixed, e_fixed, t_bind, i_bind,
        ]
        card = _card(
            axes=["Cu_total_axis", "glycine_total_axis"],
            sweep_axes=[
                {"name": "Cu", "min": 1.0e-4, "max": 2.0e-4,
                 "n_points": 2},
                {"name": "ligand_5760", "min": 1.0e-3, "max": 2.0e-3,
                 "n_points": 2},
            ],
            binds=binds,
            redox_mode="fixed",
            ionic_strength_mode="fixed",
            activity_model="davies",
        )
        return card, (2, 2)

    raise KeyError(gallery_id)


def _redox_case(gallery_id: str) -> Tuple[Dict[str, Any], Tuple[int, ...]]:
    mode = {
        "redox-excluded-parent-plus-state": "excluded",
        "redox-solved-state-target": "solve",
    }.get(gallery_id)
    if mode is None:
        raise KeyError(gallery_id)
    state_value = 4.0e-4 if mode == "excluded" else 2.5e-4
    binds = [
        _bind("pH", _axis("pH_axis")),
        _bind("temperature", _const(T_K)),
        _bind("ionic_strength", _const(0.0)),
        _bind("total", _const(1.0e-3), "Fe"),
        _bind("total", _const(state_value), "Fe$+3"),
    ]
    card = _card(
        axes=["pH_axis"],
        sweep_axes=[{"name": "pH", "min": 6.0, "max": 8.0,
                     "n_points": 3}],
        binds=binds,
        redox_mode=mode,
        ionic_strength_mode="fixed",
        redox_pair=True,
    )
    return card, (3,)


def gallery_validation_card(gallery_id: str) -> Dict[str, Any]:
    """Return the exact complete calc-input card shown as gallery support."""
    canonical = str(gallery_id or "").strip()
    if canonical not in CANONICAL_GALLERY_IDS:
        raise KeyError(f"unknown canonical freeform gallery ID {canonical!r}")
    card, _ = (
        _redox_case(canonical) if canonical.startswith("redox-")
        else _single_case(canonical)
    )
    return deepcopy(card)


def gallery_validation_case(
    gallery_id: str,
) -> Tuple[Any, Dict[str, Any], Tuple[int, ...]]:
    """Return the concrete report, card, and expected grid shape for one ID."""
    canonical = str(gallery_id or "").strip()
    if canonical not in CANONICAL_GALLERY_IDS:
        raise KeyError(f"unknown canonical freeform gallery ID {canonical!r}")
    redox_pair = canonical.startswith("redox-")
    card, expected_shape = (
        _redox_case(canonical) if redox_pair else _single_case(canonical)
    )
    return _report(redox_pair=redox_pair), card, expected_shape


def _points(result: Mapping[str, Any]) -> Iterable[Any]:
    return result["grid"].points.flat


@lru_cache(maxsize=None)
def run_freeform_gallery_solve_check(gallery_id: str) -> Dict[str, Any]:
    """Run one canonical case and return a JSON-safe validation record."""
    canonical = str(gallery_id or "").strip()
    try:
        report, card, expected_shape = gallery_validation_case(canonical)
        result = _core_symbols()["run_calculation"](report, card)
        np = _core_symbols()["np"]
        grid = result["grid"]
        issues = []
        if tuple(grid.shape) != tuple(expected_shape):
            issues.append(
                f"expected grid shape {expected_shape}, got {tuple(grid.shape)}")
        if not bool(np.all(grid.converged_mask)):
            issues.append("one or more canonical grid points did not converge")
        points = list(_points(result))
        for point in points:
            for value in point.conc.values():
                if not np.isfinite(float(value)):
                    issues.append("non-finite aqueous concentration")
                    break

        if canonical in {
            "fixed-ph-concentration-ratio-path",
            "concentration-ph-fixed-ratio-map",
            "multidimensional-ph-temperature-composition",
        }:
            expected_ratio = (
                10.0 if canonical == "fixed-ph-concentration-ratio-path"
                else 2.0
            )
            for point in points:
                ratio = point.conc["L_aq"] / point.conc["Cu_aq"]
                if not np.isclose(ratio, expected_ratio, rtol=2e-5):
                    issues.append("derived ligand/metal ratio is incorrect")
                    break
        elif canonical == "conserved-moles-dilution-path":
            for point in points:
                ratio = point.conc["L_aq"] / point.conc["Cu_aq"]
                if not np.isclose(ratio, 2.0, rtol=2e-5):
                    issues.append("dilution did not preserve the mole ratio")
                    break
        elif canonical == "redox-excluded-parent-plus-state":
            for point in points:
                if not np.isclose(point.conc["Fe2_aq"], 6.0e-4, rtol=2e-5):
                    issues.append("redox-excluded complement is incorrect")
                    break
        elif canonical == "redox-solved-state-target":
            for point in points:
                if point.E_V is None or not np.isfinite(float(point.E_V)):
                    issues.append("solved potential is absent or non-finite")
                    break
                if not np.isclose(point.conc["Fe3_aq"], 2.5e-4,
                                  rtol=3e-4):
                    issues.append("redox state target is not satisfied")
                    break

        return {
            "gallery_id": canonical,
            "status": "passed" if not issues else "failed",
            "expected_shape": list(expected_shape),
            "actual_shape": list(grid.shape),
            "n_points": len(points),
            "all_converged": bool(np.all(grid.converged_mask)),
            "issues": issues,
        }
    except Exception as exc:
        return {
            "gallery_id": canonical,
            "status": "failed",
            "expected_shape": None,
            "actual_shape": None,
            "n_points": 0,
            "all_converged": False,
            "issues": [f"{type(exc).__name__}: {exc}"],
        }


def run_all_freeform_gallery_solve_checks() -> Dict[str, Dict[str, Any]]:
    """Run all registered canonical solve checks in deterministic ID order."""
    return {
        gallery_id: run_freeform_gallery_solve_check(gallery_id)
        for gallery_id in CANONICAL_GALLERY_IDS
    }
