from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace


# ``resolve()`` expands the mapped N: drive to a substantially longer UNC
# spelling on Windows; ``absolute()`` preserves the importable mapped path.
_THIS = Path(__file__).absolute()
_PIPELINE_ROOT = _THIS.parents[3]
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from card_management_helpers.dedup_md_card_reader import (  # noqa: E402
    DedupGroup,
    DedupReport,
    DedupSpecies,
)
from LC2_free_energy_card_building.LC2_3_card_deduplicator._element_dedup_orchestrator.instruction_agent import (  # noqa: E402,E501
    ElementDedupOrchestrationSession,
    _make_instruction_tools as make_instruction_tools,
    _make_review_tools as make_review_tools,
    run_element_review_phase,
)
from LC2_free_energy_card_building.LC2_2_card_db_merger.element_inventory import (  # noqa: E402,E501
    build_element_inventory,
    inventory_by_element,
)
from LC2_free_energy_card_building.LC2_3_card_deduplicator._element_dedup_orchestrator.review_report import (  # noqa: E402,E501
    materialize_review,
    solid_family_warnings,
)
from LC2_free_energy_card_building.LC2_3_card_deduplicator._dedup_engine.group_dispatch import (  # noqa: E402,E501
    group_to_payload,
)


def _card(rows):
    lines = [
        "# test card",
        "",
        "| species_id | label | source | phase | include | additional_notes |",
        "|------------|-------|--------|-------|---------|------------------|",
    ]
    for sid, label, source in rows:
        lines.append(f"| {sid} | {label} | {source} | dissolution | true | |")
    return "\n".join(lines) + "\n"


def _unified(label, core, *, source="Atlas", species_id="", elements=("Fe",)):
    return SimpleNamespace(
        name=label,
        source=source,
        phase="solid",
        charge=0,
        mu_aligned_kJ=1.0,
        raw_stoich=dict(core),
        core_stoich=dict(core),
        multiplier=1,
        elements=elements,
        extra={"species_id": species_id, "element": "Fe"},
    )


def _inventory_fixture():
    fe3o4 = _unified(
        "Fe3O4 (anh.)",
        {"Fe$+2": 1, "Fe$+3": 2, "H": -8},
        species_id="Fe$+2.Fe$+3(2).OH8.z+0(s)",
    )
    fe2o3 = _unified("Fe2O3 (anh.)", {"Fe$+3": 1, "H": -3})
    feoh2 = _unified("Fe(OH)2 (hydr.)", {"Fe$+2": 1, "H": -2})
    feoh3 = _unified("Fe(OH)3 (hydr.)", {"Fe$+3": 1, "H": -3})
    metal = _unified("Fe", {"Fe$+0": 1})
    grouped = {"aqueous": [], "gas": [], "solid": [
        SimpleNamespace(core_label="Fe$+2:1 Fe$+3:2 H:-8", phase="solid", species=[fe3o4]),
        SimpleNamespace(core_label="Fe$+3:1 H:-3", phase="solid", species=[fe2o3, feoh3]),
        SimpleNamespace(core_label="Fe$+2:1 H:-2", phase="solid", species=[feoh2]),
        SimpleNamespace(core_label="Fe$+0:1", phase="solid", species=[metal]),
    ]}
    rows = [
        (sp.extra.get("species_id", f"sid-{idx}"), sp.name, sp.source)
        for idx, sp in enumerate((fe3o4, fe2o3, feoh2, feoh3, metal), start=1)
    ]
    inventory = build_element_inventory(
        grouped,
        [
            {"internal_id": "Fe$+0", "element": "Fe"},
            {"internal_id": "Fe$+2", "element": "Fe"},
            {"internal_id": "Fe$+3", "element": "Fe"},
        ],
        _card(rows),
    )
    return inventory, _card(rows)


def test_fe3o4_and_fe2o3_share_fe_anhydrous_review_section():
    inventory, _ = _inventory_fixture()
    fe_rows = inventory_by_element(inventory)["Fe"]
    anhydrous = {row.label for row in fe_rows if row.phase_family == "anhydrous_solid"}
    hydrated = {row.label for row in fe_rows if row.phase_family == "hydrated_solid"}
    elemental = {row.label for row in fe_rows if row.phase_family == "elemental_solid"}

    assert "Fe3O4 (anh.)" in anhydrous
    assert "Fe2O3 (anh.)" in anhydrous
    assert hydrated == {"Fe(OH)2 (hydr.)", "Fe(OH)3 (hydr.)"}
    assert elemental == {"Fe"}
    fe3o4 = next(row for row in fe_rows if row.label == "Fe3O4 (anh.)")
    assert fe3o4.core_label == "Fe$+2:1 Fe$+3:2 H:-8"
    assert fe3o4.core_label != next(
        row.core_label for row in fe_rows if row.label == "Fe2O3 (anh.)"
    )


def test_inventory_and_dispatch_are_stable_and_singleton_gets_element():
    inventory, _ = _inventory_fixture()
    reordered = list(reversed(inventory))
    assert [row.entry_key for row in inventory_by_element(inventory)["Fe"]] == [
        row.entry_key for row in inventory_by_element(reordered)["Fe"]
    ]

    fe3o4 = next(row for row in inventory if row.label == "Fe3O4 (anh.)")
    group = DedupGroup(
        phase="solid",
        core_label=fe3o4.core_label,
        species=[DedupSpecies(
            name=fe3o4.label,
            source=fe3o4.source,
            charge=0,
            multiplier=1,
            mu_aligned_kJ=fe3o4.mu_aligned_kJ,
            phase="solid",
            core_label=fe3o4.core_label,
        )],
    )
    payload = group_to_payload(group, inventory)
    assert payload["elements"] == ["Fe"]
    assert payload["species"][0]["phase_family"] == "anhydrous_solid"


def test_instruction_tool_enforces_exact_coverage_and_sentence_limit():
    slot = {"instructions": None, "error": None}
    tool = make_instruction_tools(slot, ["Fe"])["commit_element_instructions"]
    ok = tool(json.dumps({
        "case_recommendations": "- Aqueous room-T scenario: prefer hydrated solids.",
        "instructions": [{
            "element": "Fe",
            "instruction": "Use the hydrated branch. Retain elemental iron as its reference solid.",
        }],
    }))
    assert ok.startswith("OK")
    assert slot["case_recommendations"].startswith("- Aqueous")

    bad = tool(json.dumps({
        "case_recommendations": "- Aqueous room-T scenario: prefer hydrated solids.",
        "instructions": [{
            "element": "Fe",
            "instruction": "One. Two. Three.",
        }],
    }))
    assert bad.startswith("ERROR")


def test_commit_requires_case_recommendations_and_redo_can_revise_them():
    slot = {"instructions": None, "error": None}
    tool = make_instruction_tools(slot, ["Fe"])["commit_element_instructions"]
    missing = tool(json.dumps({"instructions": [{
        "element": "Fe",
        "instruction": "Use the hydrated branch.",
    }]}))
    assert missing.startswith("ERROR")
    assert "case_recommendations" in missing
    assert slot["instructions"] is None

    session = ElementDedupOrchestrationSession(
        client=object(), hooks=object(),
        instructions={"Fe": "Use the hydrated branch."}, phase="review",
    )
    review_slot = {"action": None}
    tools = make_review_tools(
        review_slot,
        session=session,
        inventory=[],
        blocking_warnings=[],
        blocking_errors=[],
        full_restarts_remaining=1,
    )
    response = tools["redo_all_dedup"](json.dumps({
        "instructions": {"Fe": "Use anhydrous solids only."},
        "reason": "The scenario is a dry calcination.",
        "case_recommendations": "- Dry high-T scenario: prefer anhydrous oxides.",
    }))
    assert response.startswith("OK")
    assert review_slot["action"]["case_recommendations"].startswith("- Dry")


def test_commit_gate_accepts_skip_dedup_for_no_duplicate_inventories():
    slot = {"instructions": None, "error": None}
    tool = make_instruction_tools(slot, ["Fe"])["commit_element_instructions"]
    bad = tool(json.dumps({
        "case_recommendations": "- No duplicates present.",
        "skip_dedup": "yes",
        "instructions": [{
            "element": "Fe",
            "instruction": "No redundancy; keep every entry.",
        }],
    }))
    assert bad.startswith("ERROR")
    assert slot["instructions"] is None

    ok = tool(json.dumps({
        "case_recommendations": "- No duplicates; all entries chemically distinct.",
        "skip_dedup": True,
        "instructions": [{
            "element": "Fe",
            "instruction": "No redundancy; keep every entry.",
        }],
    }))
    assert ok.startswith("OK")
    assert "SKIPPED" in ok
    assert slot["skip_dedup"] is True

    default = tool(json.dumps({
        "case_recommendations": "- Aqueous scenario: prefer hydrated solids.",
        "instructions": [{
            "element": "Fe",
            "instruction": "Keep the hydrated branch.",
        }],
    }))
    assert default.startswith("OK")
    assert slot["skip_dedup"] is False


def _report_for_inventory(inventory):
    groups = []
    for row in inventory:
        groups.append(DedupGroup(
            phase=row.phase,
            core_label=row.core_label,
            species=[DedupSpecies(
                name=row.label,
                source=row.source,
                charge=row.charge,
                multiplier=row.multiplier,
                mu_aligned_kJ=row.mu_aligned_kJ,
                phase=row.phase,
                core_label=row.core_label,
            )],
        ))
    return DedupReport(
        system_name="Fe",
        baseline_source="SRD-46",
        sources_present=["Atlas"],
        component_mapping=[],
        groups=groups,
        totals={},
    )


def test_override_true_false_is_rematerialized_from_original():
    inventory, original_card = _inventory_fixture()
    report = _report_for_inventory(inventory)
    target = next(row for row in inventory if row.label == "Fe3O4 (anh.)")
    decisions = [{
        "phase": target.phase,
        "core_label": target.core_label,
        "keep_species": [],
        "rationale": "Initial hydrated-model decision.",
    }]
    dropped = materialize_review(
        original_card_text=original_card,
        report=report,
        decision_dicts=decisions,
        overrides={},
        inventory=inventory,
    )
    assert dropped.include_by_key[target.species_key] is False

    restored = materialize_review(
        original_card_text=original_card,
        report=report,
        decision_dicts=decisions,
        overrides={target.entry_key: (True, "Switch to anhydrous model.")},
        inventory=inventory,
    )
    assert restored.include_by_key[target.species_key] is True
    assert restored.rationale_by_key[target.species_key].endswith(
        "Switch to anhydrous model."
    )
    # Materialisation starts from the immutable card and the final state equals
    # its original true value, so no stale drop/restore annotation accumulates.
    assert restored.card_text.count("Switch to anhydrous model") == 0
    assert original_card.count("Switch to anhydrous model") == 0


def test_phase_family_warning_blocks_unexplained_mixture_and_allows_survey():
    inventory, _ = _inventory_fixture()
    selected = {row.species_key: True for row in inventory}
    warnings = solid_family_warnings(
        inventory=inventory,
        include_by_key=selected,
        instructions={"Fe": "Retain chemically useful iron solids."},
        purpose="aqueous Pourbaix calculation",
        tasks="map stable phases",
    )
    assert warnings and warnings[0].startswith("Fe:")

    no_warnings = solid_family_warnings(
        inventory=inventory,
        include_by_key=selected,
        instructions={"Fe": "Retain both hydrated and anhydrous branches for a phase survey."},
        purpose="phase comparison",
        tasks="compare hydrated and anhydrous solids",
    )
    assert no_warnings == []

    real_prompt_no_warnings = solid_family_warnings(
        inventory=inventory,
        include_by_key=selected,
        instructions={
            "Fe": "Retain Fe3O4, alpha-Fe2O3, FeOOH, Fe(OH)2, and Fe(OH)3 as distinct competing phases."
        },
        purpose="aqueous Fe electrodeposition Pourbaix calculation",
        tasks="Include Fe hydroxides/oxides and mark the H2/H2O line.",
    )
    assert real_prompt_no_warnings == []

    generic_compare_still_warns = solid_family_warnings(
        inventory=inventory,
        include_by_key=selected,
        instructions={"Fe": "Retain chemically useful iron solids."},
        purpose="Compare Fe-EDTA versus Fe-citrate solubility.",
        tasks="Build two aqueous speciation calculations.",
    )
    assert generic_compare_still_warns


def test_review_tools_latch_one_action_and_fail_closed_on_warning():
    inventory, _ = _inventory_fixture()
    instructions = {"Fe": "Use the anhydrous solid branch."}
    session = ElementDedupOrchestrationSession(
        client=object(), hooks=object(), instructions=instructions, phase="review",
    )
    slot = {"action": None}
    tools = make_review_tools(
        slot,
        session=session,
        inventory=inventory,
        blocking_warnings=["Fe: unresolved mixture"],
        full_restarts_remaining=1,
    )
    assert tools["commit_final"](json.dumps({"summary": "Looks correct."})).startswith("ERROR")
    target = inventory[0]
    assert tools["set_entry_include"](json.dumps({
        "entry_key": target.entry_key,
        "include": False,
        "reason": "Remove the alternative hydration branch.",
    })).startswith("OK")
    assert tools["redo_all_dedup"](json.dumps({
        "instructions": {"Fe": "Use anhydrous solids only."},
        "reason": "Restart.",
    })).startswith("ERROR")


def test_commit_can_explicitly_confirm_flag_after_react_challenge():
    inventory, _ = _inventory_fixture()
    session = ElementDedupOrchestrationSession(
        client=object(), hooks=object(),
        instructions={"Fe": "Retain both phase families."}, phase="review",
    )
    slot = {"action": None}
    tools = make_review_tools(
        slot,
        session=session,
        inventory=inventory,
        blocking_warnings=["Fe: hydrated and anhydrous branches coexist."],
        full_restarts_remaining=1,
    )
    challenged = tools["commit_final"](json.dumps({"summary": "Reviewed."}))
    assert challenged.startswith("ERROR")
    confirmed = tools["commit_final"](json.dumps({
        "summary": "Reviewed and retained both phase branches.",
        "confirm_warnings": True,
        "warning_rationale": (
            "The requested phase survey explicitly compares both branches."
        ),
    }))
    assert confirmed.startswith("OK")
    assert slot["action"]["kind"] == "commit_final"
    assert slot["action"]["confirmed_warnings"]


def test_commit_accepts_unambiguous_final_summary_alias():
    inventory, _ = _inventory_fixture()
    session = ElementDedupOrchestrationSession(
        client=object(), hooks=object(),
        instructions={"Fe": "Retain the selected Fe phases."}, phase="review",
    )
    slot = {"action": None}
    tools = make_review_tools(
        slot,
        session=session,
        inventory=inventory,
        blocking_warnings=[],
        blocking_errors=[],
        full_restarts_remaining=1,
    )

    response = tools["commit_final"](json.dumps({
        "final_summary": "Reviewed final selection.",
    }))

    assert response.startswith("OK")
    assert slot["action"]["summary"] == "Reviewed final selection."


def test_commit_cannot_confirm_unexamined_worker_results():
    inventory, _ = _inventory_fixture()
    session = ElementDedupOrchestrationSession(
        client=object(), hooks=object(),
        instructions={"Fe": "Retain the supported iron phase sequence."},
        phase="review",
    )
    slot = {"action": None}
    tools = make_review_tools(
        slot,
        session=session,
        inventory=inventory,
        blocking_warnings=["Fe: hydrated and anhydrous branches coexist."],
        blocking_errors=["solid::Fe$+2:1 H:-2 was not examined."],
        full_restarts_remaining=1,
    )

    response = tools["commit_final"](json.dumps({
        "summary": "Attempt to waive every flag.",
        "confirm_warnings": True,
        "warning_rationale": "Both phase families are intentional.",
    }))

    assert response.startswith("ERROR")
    assert "cannot be confirmed" in response
    assert slot["action"] is None


def test_review_tool_dispatches_entry_keys_to_targeted_dedup_action():
    inventory, _ = _inventory_fixture()
    session = ElementDedupOrchestrationSession(
        client=object(), hooks=object(),
        instructions={"Fe": "Keep distinct iron phases."}, phase="review",
    )
    slot = {"action": None}
    tools = make_review_tools(
        slot,
        session=session,
        inventory=inventory,
        blocking_warnings=[],
        blocking_errors=[],
        full_restarts_remaining=1,
    )
    first, second = inventory[0], inventory[1]
    response = tools["dispatch_target_dedup"](json.dumps({
        "entry_keys": [first.entry_key, second.entry_key, first.entry_key],
        "guidance": "Reassess these complete groups as distinct Fe phases.",
        "reason": "The first pass over-collapsed the solid sequence.",
    }))

    assert response.startswith("OK")
    assert slot["action"] == {
        "kind": "dispatch_target_dedup",
        "entry_keys": [first.entry_key, second.entry_key],
        "guidance": "Reassess these complete groups as distinct Fe phases.",
        "reason": "The first pass over-collapsed the solid sequence.",
    }
    assert tools["commit_final"](json.dumps({
        "summary": "Too late in the same turn.",
    })).startswith("ERROR")


def test_same_agent_session_uses_refreshed_empty_memory(monkeypatch, tmp_path):
    inventory, _ = _inventory_fixture()
    import LC2_free_energy_card_building.LC2_3_card_deduplicator._element_dedup_orchestrator.instruction_agent as module

    calls = []
    client = object()
    session = ElementDedupOrchestrationSession(
        client=client,
        hooks=object(),
        instructions={"Fe": "Use anhydrous solids only."},
        phase="review",
    )

    def fake_agent_turn(user_msg, **kwargs):
        calls.append({"user_msg": user_msg, "memory": kwargs["memory"], "client": kwargs["client"]})
        if len(calls) == 1:
            reply = kwargs["tools"]["set_entry_include"](json.dumps({
                "entry_key": inventory[0].entry_key,
                "include": False,
                "reason": "Remove this competing branch.",
            }))
            tool_name = "set_entry_include"
        else:
            reply = kwargs["tools"]["commit_final"](json.dumps({"summary": "Accepted."}))
            tool_name = "commit_final"
        assert reply.startswith("OK")
        return SimpleNamespace(
            iterations=1,
            tool_history=[{"tool": tool_name}],
            answer="done",
            final_context="fresh",
        )

    monkeypatch.setattr(module, "agent_turn", fake_agent_turn)
    kwargs = dict(
        purpose="test",
        tasks="test",
        inventory=inventory,
        post_report="CURRENT REPORT",
        element_table="CURRENT TABLE",
        blocking_warnings=[],
        blocking_errors=[],
        full_restarts_remaining=1,
        debug=False,
    )
    first = run_element_review_phase(
        session=session,
        **kwargs,
        latest_diff="FIRST DIFF",
        subagent_dir=tmp_path / "one",
    )
    second = run_element_review_phase(
        session=session,
        **kwargs,
        latest_diff="SECOND DIFF",
        subagent_dir=tmp_path / "two",
    )
    assert first["action"]["kind"] == "set_entry_include"
    assert second["action"]["kind"] == "commit_final"
    assert [call["memory"] for call in calls] == [[], []]
    assert calls[0]["client"] is calls[1]["client"] is client
    assert "FIRST DIFF" not in calls[1]["user_msg"]
    assert "SECOND DIFF" in calls[1]["user_msg"]


def test_commit_flag_is_reacted_to_inside_same_review_turn(monkeypatch, tmp_path):
    inventory, _ = _inventory_fixture()
    import LC2_free_energy_card_building.LC2_3_card_deduplicator._element_dedup_orchestrator.instruction_agent as module

    session = ElementDedupOrchestrationSession(
        client=object(), hooks=object(),
        instructions={"Fe": "Retain both supported phase branches."},
        phase="review",
    )
    calls = []

    def fake_agent_turn(user_msg, **kwargs):
        calls.append(user_msg)
        first = kwargs["tools"]["commit_final"](json.dumps({
            "summary": "Initial commit attempt.",
        }))
        assert first.startswith("ERROR")
        second = kwargs["tools"]["commit_final"](json.dumps({
            "summary": "Confirmed after reviewing the commit flag.",
            "confirm_warnings": True,
            "warning_rationale": (
                "Both branches are intentionally retained for this survey."
            ),
        }))
        assert second.startswith("OK")
        return SimpleNamespace(
            iterations=2,
            tool_history=[
                {"tool": "commit_final", "result_full": first},
                {"tool": "commit_final", "result_full": second},
            ],
            answer="committed",
            final_context="challenge then confirmation",
        )

    monkeypatch.setattr(module, "agent_turn", fake_agent_turn)
    result = run_element_review_phase(
        session=session,
        purpose="phase survey",
        tasks="retain both branches",
        inventory=inventory,
        post_report="CURRENT REPORT",
        element_table="CURRENT TABLE",
        latest_diff="CURRENT DIFF",
        blocking_warnings=["Fe: review the mixed solid branches."],
        blocking_errors=[],
        full_restarts_remaining=1,
        subagent_dir=tmp_path / "review",
        debug=False,
    )

    assert len(calls) == 1
    assert result["action"]["kind"] == "commit_final"
    assert result["action"]["confirmed_warnings"] == [
        "Fe: review the mixed solid branches."
    ]
