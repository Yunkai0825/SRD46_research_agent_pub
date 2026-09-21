from __future__ import annotations

from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC3_solver_para_card_building.LC3_3_constraint_designer.l3_3_constraint_agent import (
    _physical_axis_names,
)


def test_ph_and_potential_symbolic_axes_map_to_solver_coordinates() -> None:
    spec = {
        "axes": ["pH_axis", "E_V_axis"],
        "binds": [
            {
                "lhs": {"ref": "pH"},
                "rhs": {"axis": "pH_axis"},
            },
            {
                "lhs": {"ref": "E_V"},
                "rhs": {"axis": "E_V_axis"},
            },
        ],
    }

    assert _physical_axis_names(spec) == ["pH", "E_V"]


def test_total_axis_maps_to_component_token() -> None:
    spec = {
        "axes": ["citrate_tot_axis"],
        "binds": [{
            "lhs": {"ref": "total", "id": "ligand_9058"},
            "rhs": {"axis": "citrate_tot_axis"},
        }],
    }

    assert _physical_axis_names(spec) == ["ligand_9058"]


def test_formula_only_axis_uses_physical_suffix_fallback() -> None:
    spec = {
        "axes": ["temperature_axis"],
        "binds": [{
            "lhs": {"ref": "total", "id": "ligand_9058"},
            "rhs": {
                "formula": "scale * temperature_axis",
                "vars": {"temperature_axis": {"axis": "temperature_axis"}},
            },
        }],
    }

    assert _physical_axis_names(spec) == ["temperature"]
