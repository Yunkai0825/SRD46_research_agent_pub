from __future__ import annotations

from types import SimpleNamespace

import pytest

from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC3_solver_para_card_building.LC3_3_constraint_designer import (
    l3_3_constraint_agent as target,
)


def test_rejected_system_override_is_not_reused_for_prompt_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = object()
    authoritative = object()
    rejected_merge = object()
    requested_catalog = {"chemical_system": {"ligands": [{"db_id": "ligand_11422"}]}}
    prompt_inputs: list[object | None] = []

    monkeypatch.setattr(target, "build_default_catalog", lambda _report: authoritative)
    monkeypatch.setattr(
        target,
        "merge_catalog_overrides",
        lambda _catalog, _override: rejected_merge,
    )

    def reject(_catalog: object, _report: object) -> None:
        raise ValueError("requested ligand is absent from the free-energy report")

    monkeypatch.setattr(target, "validate_catalog_against_report", reject)

    def build_prompt(_report: object, override: object | None = None) -> object:
        prompt_inputs.append(override)
        return object()

    monkeypatch.setattr(target, "build_variable_catalog", build_prompt)

    native, _prompt = target._build_aligned_constraint_catalogs(
        report, requested_catalog
    )

    assert native is authoritative
    assert prompt_inputs == [None]


def test_valid_system_override_is_shared_by_native_and_prompt_catalogs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = object()
    authoritative = object()
    accepted_merge = object()
    requested_catalog = {"chemical_system": {"ligands": []}}
    prompt_inputs: list[object | None] = []

    monkeypatch.setattr(target, "build_default_catalog", lambda _report: authoritative)
    monkeypatch.setattr(
        target,
        "merge_catalog_overrides",
        lambda _catalog, _override: accepted_merge,
    )
    monkeypatch.setattr(
        target,
        "validate_catalog_against_report",
        lambda _catalog, _report: None,
    )

    def build_prompt(_report: object, override: object | None = None) -> object:
        prompt_inputs.append(override)
        return object()

    monkeypatch.setattr(target, "build_variable_catalog", build_prompt)

    native, _prompt = target._build_aligned_constraint_catalogs(
        report, requested_catalog
    )

    assert native is accepted_merge
    assert prompt_inputs == [requested_catalog]


def test_compiler_catalog_serialization_replaces_stale_redox_state_list() -> None:
    report = SimpleNamespace(
        component_meta=[
            SimpleNamespace(
                comp_type="metal", internal_id=state, db_id="metal_62",
                name="Iron",
            )
            for state in ("Fe$+3", "Fe$+2", "Fe$+0", "Fe$+6")
        ],
        metal_ids=["Fe$+3", "Fe$+2", "Fe$+0", "Fe$+6"],
        ligand_ids=[],
    )
    compiler_catalog = target.build_default_catalog(report)
    stale = {
        "chemical_system": {
            "metals": [{
                "name": "Fe",
                "element": "Fe",
                "redox_states": ["Fe$+3", "Fe$+2"],
            }],
        },
        "provenance": {"source": "LC1"},
    }

    serialized = target._serialize_compiler_catalog(compiler_catalog, stale)

    assert serialized["provenance"] == {"source": "LC1"}
    assert serialized["chemical_system"]["metals"][0]["redox_states"] == [
        "Fe$+3", "Fe$+2", "Fe$+0", "Fe$+6",
    ]
