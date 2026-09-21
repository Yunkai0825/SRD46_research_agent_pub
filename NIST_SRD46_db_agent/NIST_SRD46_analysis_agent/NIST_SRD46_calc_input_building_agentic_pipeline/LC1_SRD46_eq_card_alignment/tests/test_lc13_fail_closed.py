from __future__ import annotations

import sys
import types
from pathlib import Path
from types import SimpleNamespace

from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment import (  # noqa: E501
    LC1_eq_card_alignment_orchestrator as orch,
)


_LC13_MODULE = (
    f"{orch.__package__}."
    "LC1_3_estimate_eq_stability_dispatch."
    "LC1_3_estimate_eq_stability_dispatch_orchestrator"
)
_SETTINGS_MODULE = (
    f"{orch.__package__}."
    "LC1_3_estimate_eq_stability_dispatch."
    "runtime_support.runtime_models"
)


def _install_common_stubs(monkeypatch, tmp_path: Path):
    catalog = {
        "chemical_system": {
            "metals": [{"id": "metal_test", "name": "Fe"}],
            "ligands": [{"id": "ligand_test", "name": "DMF"}],
        }
    }
    monkeypatch.setattr(
        orch,
        "align_chemical_system",
        lambda *args, **kwargs: {"status": "ok", "system_catalog": catalog},
    )
    monkeypatch.setattr(
        orch,
        "fetch_lc1_2_eq_map_card",
        lambda **kwargs: {"entries": []},
    )

    settings_module = types.ModuleType(_SETTINGS_MODULE)

    class _Settings:
        @classmethod
        def from_config(cls, config):
            return cls()

    settings_module.LC13Settings = _Settings
    monkeypatch.setitem(sys.modules, _SETTINGS_MODULE, settings_module)
    return catalog


def _install_lc13_module(monkeypatch, runner):
    module = types.ModuleType(_LC13_MODULE)
    module.build_default_lc1_3_dependencies = lambda settings: object()
    module.run_lc1_3 = runner
    monkeypatch.setitem(sys.modules, _LC13_MODULE, module)


def test_enabled_lc13_runtime_error_fails_before_reference_review(
    monkeypatch, tmp_path
):
    _install_common_stubs(monkeypatch, tmp_path)
    reviewed = []
    monkeypatch.setattr(
        orch,
        "review_lc1_2_eq_map_card",
        lambda **kwargs: reviewed.append(kwargs),
    )

    def _raise(**kwargs):
        raise RuntimeError("local MCP transport failed")

    _install_lc13_module(monkeypatch, _raise)
    result = orch.run_lc1(
        "Fe and DMF",
        output_dir=tmp_path / "runtime_failure",
        estimate_missing_equilibria=True,
    )

    assert result["status"] == "failed"
    assert result["lc1_2"] is None
    assert reviewed == []
    assert result["lc1_3"]["estimation_search_complete"] is False
    assert "local MCP transport failed" in result["_error"]


def test_enabled_incomplete_search_fails_before_reference_review(
    monkeypatch, tmp_path
):
    _install_common_stubs(monkeypatch, tmp_path)
    reviewed = []
    monkeypatch.setattr(
        orch,
        "review_lc1_2_eq_map_card",
        lambda **kwargs: reviewed.append(kwargs),
    )

    incomplete = SimpleNamespace(
        status="reference_only",
        estimation_search_complete=False,
        reference_only_reason="parser_failures",
        as_dict=lambda: {
            "status": "reference_only",
            "estimation_search_complete": False,
            "reference_only_reason": "parser_failures",
        },
    )
    _install_lc13_module(monkeypatch, lambda **kwargs: incomplete)
    result = orch.run_lc1(
        "Fe and DMF",
        output_dir=tmp_path / "incomplete",
        estimate_missing_equilibria=True,
    )

    assert result["status"] == "failed"
    assert reviewed == []
    assert result["lc1_3"]["reference_only_reason"] == (
        "lc1_3_incomplete_search"
    )
    assert "parser_failures" in result["_error"]


def test_enabled_complete_no_estimation_continues_reference_review(
    monkeypatch, tmp_path
):
    _install_common_stubs(monkeypatch, tmp_path)
    reviewed = []
    card_path = tmp_path / "reviewed.json"
    card_path.write_text("{}", encoding="utf-8")

    def _review(**kwargs):
        reviewed.append(kwargs)
        return {
            "status": "ok",
            "eq_map_card_path": str(card_path),
            "manifest_path": str(tmp_path / "review.json"),
        }

    monkeypatch.setattr(orch, "review_lc1_2_eq_map_card", _review)
    complete = SimpleNamespace(
        status="ok",
        estimation_search_complete=True,
        reference_only_reason=None,
        support_eq_map_path=None,
        session_id="test-session",
        support_eq_map_sha256=None,
        session_working_map_path=None,
        session_working_map_sha256=None,
        as_dict=lambda: {
            "status": "ok",
            "estimation_search_complete": True,
            "reference_only_reason": None,
            "support_eq_map_path": None,
        },
    )
    _install_lc13_module(monkeypatch, lambda **kwargs: complete)
    result = orch.run_lc1(
        "Fe and DMF",
        output_dir=tmp_path / "complete_no_estimation",
        estimate_missing_equilibria=True,
    )

    assert result["status"] == "ok"
    assert len(reviewed) == 1
    assert result["support_eq_map_path"] is None


def test_disabled_path_keeps_reference_lc1_2_route(monkeypatch, tmp_path):
    _install_common_stubs(monkeypatch, tmp_path)
    card_path = tmp_path / "legacy_reviewed.json"
    card_path.write_text("{}", encoding="utf-8")
    fetched = []
    reviewed = []

    def _fetch(**kwargs):
        fetched.append(kwargs)
        return {"equilibrium_networks": []}

    def _review(**kwargs):
        reviewed.append(kwargs)
        return {
            "status": "ok",
            "eq_map_card_path": str(card_path),
            "manifest_path": str(tmp_path / "legacy_manifest.json"),
        }

    monkeypatch.setattr(orch, "fetch_lc1_2_eq_map_card", _fetch)
    monkeypatch.setattr(orch, "review_lc1_2_eq_map_card", _review)
    monkeypatch.setattr(orch, "sibling_metal_rows", lambda element: [])

    result = orch.run_lc1(
        "Fe and DMF",
        output_dir=tmp_path / "disabled",
        estimate_missing_equilibria=False,
    )

    assert result["status"] == "ok"
    assert len(fetched) == 1
    assert len(reviewed) == 1
    assert reviewed[0]["card"] == {"equilibrium_networks": []}
    assert "lc1_3" not in result
    assert not (
        tmp_path / "disabled" / "LC1_3_estimate_eq_stability_dispatch"
    ).exists()


_PU_AM_CATALOG = {
    "chemical_system": {
        "metals": [
            {"name": "H", "element": "H", "water_species": True,
             "redox_states": [{"internal_id": "H$+1", "db_id": "metal_68"}]},
            {"name": "Pu", "element": "Pu",
             "redox_states": [{"internal_id": "Pu$+4", "db_id": "metal_149"},
                              {"internal_id": "Pu$+3", "db_id": "metal_148"}]},
            {"name": "Am", "element": "Am",
             "redox_states": [{"internal_id": "Am$+3", "db_id": "metal_6"}]},
        ],
        "ligands": [
            {"name": "Acetylsalicylic acid", "db_id": "ligand_8701",
             "internal_id": "L1"},
            {"name": "Citric acid", "db_id": "ligand_9058", "internal_id": "L2"},
            {"name": "Hydroxide ion", "db_id": "ligand_10076",
             "internal_id": "L0", "water_species": True},
        ],
    }
}
# What SRD-46 actually holds for this grid: only Am3+/citrate plus protonation
# and hydrolysis rows (H+/ligand, metal/OH-).
_PU_AM_CARD = {
    "equilibrium_networks": [
        {"metal_id": 68, "ligand_id": 8701},
        {"metal_id": 68, "ligand_id": 9058},
        {"metal_id": 68, "ligand_id": 10076},
        {"metal_id": 149, "ligand_id": 10076},
        {"metal_id": 148, "ligand_id": 10076},
        {"metal_id": 6, "ligand_id": 9058},
        {"metal_id": 6, "ligand_id": 10076},
    ]
}


def test_pair_coverage_ignores_water_species_and_finds_uncovered(monkeypatch):
    monkeypatch.setattr(orch, "sibling_metal_rows", lambda element: [])
    cov = orch.pair_coverage(
        _PU_AM_CATALOG["chemical_system"], _PU_AM_CARD
    )

    assert cov["requested_metals"] == ["Pu", "Am"]
    assert cov["requested_ligands"] == ["Acetylsalicylic acid", "Citric acid"]
    assert cov["covered_pairs"] == [["Am", "Citric acid"]]
    assert cov["uncovered_ligands"] == ["Acetylsalicylic acid"]
    assert cov["uncovered_metals"] == ["Pu"]
    assert cov["complete"] is False
    assert "Pu" in orch.coverage_gate_error(cov)
    assert "Acetylsalicylic acid" in orch.coverage_gate_error(cov)


def test_pair_coverage_passes_when_only_single_pairs_are_missing(monkeypatch):
    monkeypatch.setattr(orch, "sibling_metal_rows", lambda element: [])
    card = {
        "equilibrium_networks": _PU_AM_CARD["equilibrium_networks"]
        + [{"metal_id": 149, "ligand_id": 8701}]   # Pu4+/aspirin now present
    }
    cov = orch.pair_coverage(_PU_AM_CATALOG["chemical_system"], card)

    assert cov["missing_pairs"] == [["Pu", "Citric acid"],
                                    ["Am", "Acetylsalicylic acid"]]
    assert cov["uncovered_ligands"] == []
    assert cov["uncovered_metals"] == []
    assert orch.coverage_gate_error(cov) is None


def test_disabled_path_coverage_gate_fails_closed(monkeypatch, tmp_path):
    _install_common_stubs(monkeypatch, tmp_path)
    monkeypatch.setattr(
        orch,
        "align_chemical_system",
        lambda *args, **kwargs: {
            "status": "ok", "system_catalog": _PU_AM_CATALOG,
        },
    )
    monkeypatch.setattr(orch, "sibling_metal_rows", lambda element: [])
    monkeypatch.setattr(
        orch, "fetch_lc1_2_eq_map_card", lambda **kwargs: _PU_AM_CARD
    )
    reviewed = []
    monkeypatch.setattr(
        orch,
        "review_lc1_2_eq_map_card",
        lambda **kwargs: reviewed.append(kwargs),
    )

    result = orch.run_lc1(
        "Pu(IV) and Am(III) with aspirin and citrate",
        output_dir=tmp_path / "gate",
        estimate_missing_equilibria=False,
    )

    assert result["status"] == "failed"
    assert reviewed == []
    assert result["lc1_2"] is None
    assert result["eq_map_card_path"] is None
    assert result["coverage"]["uncovered_metals"] == ["Pu"]
    assert "not in database" in result["_error"]
    assert "Pu x Acetylsalicylic acid" in result["_error"]
    summary = (tmp_path / "gate" / "summary" / "LC1_summary.json").read_text(
        encoding="utf-8"
    )
    assert "uncovered_ligands" in summary
