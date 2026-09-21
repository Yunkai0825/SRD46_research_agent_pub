from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from NIST_SRD46_db_agent.general_db_query_engine.general_subagent_skill_schema_and_parser.subworkflow_md_tool_descriptions import (
    build_tool_instructions,
)

from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC3_solver_para_card_building.sweep_template_router import (
    append_freeform_gallery_note,
    build_sweep_skill_context,
    get_freeform_gallery_note,
    get_sweep_skill_tools,
    list_sweep_design_skills,
    primary_skill_id_for_method,
    read_sweep_design_skill,
    skill_selection_record,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC3_solver_para_card_building.LC3_2_initial_condition_designer import (
    l3_2_initial_condition_agent as l3_2,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC3_solver_para_card_building.LC3_1_method_decider import (
    l3_1_method_agent as l3_1,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC3_solver_para_card_building.LC3_2_initial_condition_designer._initcond_helpers.initcond_card import (
    InitCondPin,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC3_solver_para_card_building.LC3_3_constraint_designer import (
    l3_3_constraint_agent as l3_3,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC3_solver_para_card_building.LC3_4_sweep_designer import (
    l3_4_sweep_agent as l3_4,
)


def test_three_family_headers_and_standard_routing() -> None:
    headers = json.loads(list_sweep_design_skills())
    assert [item["skill_id"] for item in headers] == [
        "speciation-path-design",
        "predominance-map-design",
        "freeform-sweep-design",
    ]
    assert primary_skill_id_for_method("pH_sweep") == "speciation-path-design"
    assert primary_skill_id_for_method("titration_sweep") == "speciation-path-design"
    assert primary_skill_id_for_method("pourbaix_sweep") == "predominance-map-design"
    assert primary_skill_id_for_method("freeform_sweep") == (
        "freeform-sweep-design")
    selected = skill_selection_record("freeform_sweep")
    assert selected["primary_skill"] == "freeform-sweep-design"
    assert selected["selection"] == "standard-method"
    assert selected["compatible_skill_ids"] == []
    for item in headers:
        assert item["compatible_methods"] == []


def test_family_selection_rejects_method_mismatch() -> None:
    try:
        skill_selection_record("pH_sweep", "predominance-map-design")
    except ValueError as exc:
        assert "standard method" in str(exc)
    else:  # pragma: no cover - assertion aid
        raise AssertionError("mismatched standard skill was accepted")

    with pytest.raises(ValueError, match="standard method"):
        skill_selection_record("freeform_sweep", "speciation-path-design")


def test_standard_pourbaix_cannot_leave_l3_1_with_one_axis() -> None:
    rejected = l3_1._finalize_method("pourbaix_sweep", 1)
    assert "requires dof >= 2" in rejected
    accepted = l3_1._finalize_method("pourbaix_sweep", 2)
    assert accepted.startswith("OK")


def test_progressive_context_loads_only_primary_stage_detail() -> None:
    context = build_sweep_skill_context("pH_sweep", "constraints")
    assert "Primary skill declared for this standard method: speciation-path-design" in context
    assert "# L3_3 template: speciation/path constraints" in context
    assert "# L3_3 template: predominance-map constraints" not in context
    # The alternative remains discoverable by its cheap header.
    assert "predominance-map-design" in context

    freeform = build_sweep_skill_context("freeform_sweep", "sweep_design")
    assert "Primary skill declared for this standard method: freeform-sweep-design" in freeform
    assert "Freeform example-gallery protocol" in freeform
    assert "list_freeform_examples" in freeform

    selected_freeform = build_sweep_skill_context(
        "freeform_sweep", "sweep_design", "freeform-sweep-design")
    assert "persisted skill selection" in selected_freeform


def test_bounded_skill_reads_and_tool_surface() -> None:
    text = read_sweep_design_skill("predominance-map-design", "sweep_design")
    assert "# L3_4 template: predominance-map sweep design" in text
    assert "# L3_2 template" not in text
    assert read_sweep_design_skill("missing", "overview").startswith("ERROR:")
    assert read_sweep_design_skill(
        "speciation-path-design", "missing-section").startswith("ERROR:")
    tools = get_sweep_skill_tools("constraints")
    assert set(tools) == {
        "list_sweep_design_skills", "read_sweep_design_skill",
        "list_freeform_examples", "read_freeform_example",
        "select_freeform_example",
    }
    reader = tools["read_sweep_design_skill"]
    assert list(inspect.signature(reader).parameters) == ["skill_id"]
    alternative = reader("predominance-map-design")
    assert "# L3_3 template: predominance-map constraints" in alternative
    assert "# L3_2 template" not in alternative
    assert "# L3_4 template" not in alternative

    # The generated model-facing schema must not offer another-stage reads.
    instructions = build_tool_instructions(tools)
    reader_line = next(
        line for line in instructions.splitlines()
        if line.startswith("- read_sweep_design_skill(")
    )
    assert "skill_id=''" in reader_line
    assert "section" not in reader_line

    assert list(inspect.signature(
        tools["list_freeform_examples"]).parameters) == []
    assert list(inspect.signature(
        tools["read_freeform_example"]).parameters) == ["example_id"]
    assert list(inspect.signature(
        tools["select_freeform_example"]).parameters) == [
            "example_id", "rationale"]

    instructions = build_tool_instructions(tools)
    assert "stage=" not in next(
        line for line in instructions.splitlines()
        if line.startswith("- read_freeform_example("))


def test_all_post_method_agents_register_skill_tools() -> None:
    for stage, method, builder, required, expected_heading in (
        ("initial_conditions", "pH_sweep", l3_2._build_agent_tools,
         "commit_initial_conditions",
         "# L3_2 template: predominance-map initial conditions"),
        ("constraints", "pH_sweep", l3_3._build_agent_tools,
         "compile_constraint_card",
         "# L3_3 template: predominance-map constraints"),
        ("sweep_design", "pH_sweep", l3_4._build_agent_tools,
         "finalize_sweep_grid",
         "# L3_4 template: predominance-map sweep design"),
    ):
        build_sweep_skill_context(method, stage)
        tools = builder()
        assert required in tools
        assert "list_sweep_design_skills" in tools
        assert "read_sweep_design_skill" in tools
        assert "list_freeform_examples" in tools
        assert "read_freeform_example" in tools
        assert "select_freeform_example" in tools
        assert tools["list_freeform_examples"]().startswith("ERROR:")
        alternative = tools["read_sweep_design_skill"](
            "predominance-map-design")
        assert expected_heading in alternative
        assert sum(
            marker in alternative
            for marker in ("# L3_2 template", "# L3_3 template", "# L3_4 template")
        ) == 1


@pytest.mark.parametrize(
    ("stage", "builder", "slice_heading"),
    (
        ("initial_conditions", l3_2._build_agent_tools, "# L3_2 slice"),
        ("constraints", l3_3._build_agent_tools, "# L3_3 slice"),
        ("sweep_design", l3_4._build_agent_tools, "# L3_4 slice"),
    ),
)
def test_real_stage_agent_tools_expose_slice_before_complete_card(
    stage, builder, slice_heading,
) -> None:
    build_sweep_skill_context("freeform_sweep", stage)
    tools = builder()
    headers = json.loads(tools["list_freeform_examples"]())
    assert headers

    rendered = tools["read_freeform_example"](headers[0]["example_id"])
    support_heading = (
        "## Supporting reference: complete validated calculation card"
    )
    assert rendered.startswith("[FREEFORM EXAMPLE]")
    assert rendered.index(slice_heading) < rendered.index(support_heading)

    primary_slice, supporting = rendered.split(support_heading, 1)
    for foreign_heading in {"# L3_2 slice", "# L3_3 slice", "# L3_4 slice"} - {
        slice_heading
    }:
        assert foreign_heading not in primary_slice
    assert '"sweep_method": "freeform_sweep"' in supporting
    assert '"constraint_spec"' in supporting
    assert '"sweep_axes"' in supporting
    assert "[example text truncated" not in rendered
    assert rendered.rstrip().endswith("```")


def test_l3_2_user_message_makes_freeform_recommendation_optional() -> None:
    message = l3_2._build_user_message(
        "purpose", "tasks", "freeform_sweep", 1, "catalog", "snapshot"
    )
    assert "best_example` may remain null" in message
    assert "select one best structural analogue" not in message


@pytest.mark.parametrize(
    ("stage", "module", "submit", "request_restart", "extra_resets"),
    (
        (
            "initial_conditions", l3_2, l3_2._commit_initial_conditions,
            l3_2._request_lc3_restart, {},
        ),
        (
            "constraints", l3_3, l3_3._compile_constraint_card,
            l3_3._request_lc3_restart, {},
        ),
        (
            "sweep_design", l3_4, l3_4._finalize_sweep_grid,
            l3_4._request_lc3_restart,
            {"calc_input": None, "failure_scope": None},
        ),
    ),
)
def test_failed_freeform_submission_preserves_gallery_note_in_latest_attempt(
    stage, module, submit, request_restart, extra_resets, monkeypatch,
) -> None:
    build_sweep_skill_context("freeform_sweep", stage)
    tools = get_sweep_skill_tools(stage)
    headers = json.loads(tools["list_freeform_examples"]())
    assert tools["read_freeform_example"](headers[0]["example_id"]).startswith(
        "[FREEFORM EXAMPLE]"
    )
    expected_note = get_freeform_gallery_note(stage)

    monkeypatch.setitem(module._SESSION, "_sweep_method", "freeform_sweep")
    for key, value in {
        "latest_attempt": None,
        "gallery_note": None,
        "restart_request": None,
        **extra_resets,
    }.items():
        monkeypatch.setitem(module._FINAL_SLOT, key, value)

    result = submit()
    assert result.startswith("ERROR:")
    assert module._FINAL_SLOT["gallery_note"] == expected_note
    assert (
        module._FINAL_SLOT["latest_attempt"]["freeform_gallery_note"]
        == expected_note
    )

    # A stage can inspect more guidance after seeing the ReAct error and then
    # request a whole-LC3 restart. The sealed restart artifact must capture
    # that newer inspection state, not only the state at the failed submit.
    assert tools["read_freeform_example"](headers[1]["example_id"]).startswith(
        "[FREEFORM EXAMPLE]"
    )
    refreshed_note = get_freeform_gallery_note(stage)
    assert request_restart("the failed premise must be redesigned").startswith(
        "OK_RESTART_REQUESTED:"
    )
    assert (
        module._FINAL_SLOT["latest_attempt"]["freeform_gallery_note"]
        == refreshed_note
    )


def test_stage_skills_define_only_their_direct_submission_contract() -> None:
    contracts = {
        "initial_conditions": {
            "required": {
                "commit_initial_conditions", "card_source", "inits", "notes",
                "activity_model", "solids", "redox_mode",
                "ionic_strength_mode", "freeform_vars_json", "deferred_json",
            },
            "foreign": {
                "compile_constraint_card", "finalize_sweep_grid",
                "axes_json", "grid_refine_json", "expected_K",
            },
        },
        "constraints": {
            "required": {
                "compile_constraint_card", "card_source", "expected_K",
                "axes", "lets", "binds",
            },
            "foreign": {
                "commit_initial_conditions", "finalize_sweep_grid",
                "axes_json", "grid_refine_json", "sweep_skill_id",
            },
        },
        "sweep_design": {
            "required": {
                "finalize_sweep_grid", "axes_json", "grid_refine_json",
                "name", "min", "max", "n_points",
            },
            "foreign": {
                "commit_initial_conditions", "compile_constraint_card",
                "card_source", "expected_K", "deferred_json",
                "activity_model", "redox_mode",
            },
        },
    }
    downstream_only = {
        "topology", "label-map", "full-speciation", "verdict",
        "artifact path", "rdp", "convergence coverage", "per-point table",
        "state diagnostic", "saturation index",
    }

    for stage, contract in contracts.items():
        for skill_id in (
            "speciation-path-design", "predominance-map-design",
            "freeform-sweep-design",
        ):
            text = read_sweep_design_skill(skill_id, stage)
            lowered = text.lower()
            for token in contract["required"]:
                assert token in text, (stage, skill_id, token)
            for token in contract["foreign"]:
                assert token not in text, (stage, skill_id, token)
            for phrase in downstream_only:
                assert phrase not in lowered, (stage, skill_id, phrase)
            assert '"known-or-assumed"' not in text


def test_l3_2_explicit_deferral_preserves_strict_completeness(monkeypatch) -> None:
    monkeypatch.setitem(l3_2._SESSION, "_components", ["Fe", "Fe$+3", "ligand_1"])
    monkeypatch.setitem(
        l3_2._SESSION,
        "_intensives",
        ["temperature", "ionic_strength", "pH", "E_V"],
    )
    monkeypatch.setitem(
        l3_2._SESSION,
        "_catalog_structured",
        {
            "metals": [{
                "element": "Fe", "name": "Iron",
                "valences": [{"valence": "Fe$+3"}],
            }],
            "ligands": [{
                "db_id": "ligand_1", "internal_id": "L1", "name": "citrate",
            }],
        },
    )
    pins = [InitCondPin(
        id="T", ref="temperature", handle_id=None, value=298.15,
        basis="known", note="task declaration",
    )]
    raw = json.dumps([
        {"handle": 's.total["Fe"]', "role": "swept",
         "note": "analytical concentration axis"},
        {"handle": 's.total["ligand_1"]', "role": "derived",
         "note": "constant ligand-to-metal relation"},
    ])
    deferred, parse_issues = l3_2._parse_deferred_conditions(raw, pins)
    assert parse_issues == []
    settings = {
        "activity_model": "davies",
        "solids": "include",
        "redox_mode": "excluded",
        "ionic_strength_mode": "auto",
    }
    assert l3_2._required_declaration_issues(pins, settings, deferred) == []

    _, overlap_issues = l3_2._parse_deferred_conditions(
        json.dumps([{
            "handle": "s.temperature", "role": "swept", "note": "axis",
        }]),
        pins,
    )
    assert any("both pinned and deferred" in issue for issue in overlap_issues)


def test_freeform_gallery_trace_selection_and_downstream_note() -> None:
    context = build_sweep_skill_context(
        "freeform_sweep", "initial_conditions")
    assert "freeform-sweep-design" in context
    assert "best_example may remain null" in context
    tools = get_sweep_skill_tools()
    listed = json.loads(tools["list_freeform_examples"]())
    assert len(listed) >= 2
    first, second = listed[0]["example_id"], listed[1]["example_id"]

    empty_note = get_freeform_gallery_note()
    assert empty_note["best_example"] is None
    assert empty_note["inspected_examples"] == []
    uninspected = tools["select_freeform_example"](
        first, "looks relevant")
    assert uninspected.startswith("ERROR:")
    assert "read" in uninspected
    traversal = tools["read_freeform_example"]("../SKILL.md")
    assert traversal.startswith("ERROR:")
    assert get_freeform_gallery_note()["inspected_examples"] == []

    # Repeated reads are unique. Read the eventual best example second so the
    # completed hand-off proves that the helper reorders it best-first.
    assert "[FREEFORM EXAMPLE]" in tools["read_freeform_example"](second)
    tools["read_freeform_example"](second)
    bounded = tools["read_freeform_example"](first)
    assert len(bounded) <= 12_000
    selected = tools["select_freeform_example"](
        first, "Its coupled path most closely matches the requested controls.")
    assert selected.startswith("OK:")

    note = get_freeform_gallery_note()
    assert note["stage"] == "initial_conditions"
    assert note["best_example"] == first
    assert note["best_example_rationale"].startswith("Its coupled path")
    assert [item["example_id"] for item in note["inspected_examples"]] == [
        first, second]

    downstream = build_sweep_skill_context(
        "freeform_sweep", "constraints", prior_gallery_notes=[note])
    assert "Prior freeform-gallery inspection notes" in downstream
    assert '"stage": "initial_conditions"' in downstream
    assert f'"best_example": "{first}"' in downstream
    # Building a downstream stage starts a fresh current-stage trace.
    fresh_note = get_freeform_gallery_note()
    assert fresh_note["stage"] == "constraints"
    assert fresh_note["best_example"] is None
    assert fresh_note["inspected_examples"] == []


def test_freeform_galleries_share_ids_and_keep_stage_local_slices() -> None:
    ids_by_stage = {}
    forbidden_by_stage = {
        "initial_conditions": ("axes =", "binds =", "axes_json ="),
        "constraints": ("card_source:", "axes_json =", "grid_refine_json ="),
        "sweep_design": ("card_source:", "axes =", "binds =", "expected_K="),
    }
    for stage in ("initial_conditions", "constraints", "sweep_design"):
        build_sweep_skill_context("freeform_sweep", stage)
        tools = get_sweep_skill_tools()
        headers = json.loads(tools["list_freeform_examples"]())
        ids_by_stage[stage] = [item["example_id"] for item in headers]
        for item in headers:
            text = tools["read_freeform_example"](item["example_id"])
            assert "## Supporting reference: complete validated calculation card" in text
            primary_slice, supporting = text.split(
                "## Supporting reference: complete validated calculation card",
                1,
            )
            for foreign in forbidden_by_stage[stage]:
                assert foreign not in primary_slice, (
                    stage, item["example_id"], foreign)
            assert '"sweep_method": "freeform_sweep"' in supporting
            assert '"constraint_spec"' in supporting
            assert '"sweep_axes"' in supporting

    assert ids_by_stage["initial_conditions"]
    assert ids_by_stage["initial_conditions"] == ids_by_stage["constraints"]
    assert ids_by_stage["constraints"] == ids_by_stage["sweep_design"]


def test_build_context_resets_same_stage_gallery_trace() -> None:
    build_sweep_skill_context("freeform_sweep", "sweep_design")
    tools = get_sweep_skill_tools()
    example_id = json.loads(tools["list_freeform_examples"]())[0]["example_id"]
    tools["read_freeform_example"](example_id)
    tools["select_freeform_example"](example_id, "best available pattern")
    assert get_freeform_gallery_note()["best_example"] == example_id

    build_sweep_skill_context("freeform_sweep", "sweep_design")
    reset_note = get_freeform_gallery_note()
    assert reset_note["best_example"] is None
    assert reset_note["inspected_examples"] == []


def test_gallery_note_is_appended_once_per_stage_without_mutating_card() -> None:
    build_sweep_skill_context("freeform_sweep", "initial_conditions")
    tools = get_sweep_skill_tools()
    empty_note = get_freeform_gallery_note()
    original = {"_meta": {"keep": True}, "sweep_method": "freeform_sweep"}
    with_empty = append_freeform_gallery_note(original, empty_note)
    assert "freeform_gallery_notes" not in original["_meta"]
    stored_empty = with_empty["_meta"]["freeform_gallery_notes"][0]
    assert stored_empty["best_example"] is None
    assert stored_empty["inspected_examples"] == []

    example = json.loads(tools["list_freeform_examples"]())[0]
    tools["read_freeform_example"](example["example_id"])
    inspected_note = get_freeform_gallery_note()
    assert inspected_note["best_example"] is None
    with_inspected = append_freeform_gallery_note(with_empty, inspected_note)
    stored_inspected = with_inspected["_meta"]["freeform_gallery_notes"][0]
    assert stored_inspected["best_example"] is None
    assert [item["example_id"] for item in
            stored_inspected["inspected_examples"]] == [example["example_id"]]

    tools["select_freeform_example"](
        example["example_id"], "closest initial-condition pattern")
    first_note = get_freeform_gallery_note()

    with_first = append_freeform_gallery_note(with_inspected, first_note)
    notes = with_first["_meta"]["freeform_gallery_notes"]
    assert [note["stage"] for note in notes] == ["initial_conditions"]

    replacement = dict(first_note)
    replacement["best_example_rationale"] = "revised after a local retry"
    replaced = append_freeform_gallery_note(with_first, replacement)
    notes = replaced["_meta"]["freeform_gallery_notes"]
    assert len(notes) == 1
    assert notes[0]["best_example_rationale"].startswith("revised")

    nullable = dict(first_note)
    nullable["best_example"] = None
    nullable_result = append_freeform_gallery_note(replaced, nullable)
    nullable_note = nullable_result["_meta"]["freeform_gallery_notes"][0]
    assert nullable_note["best_example"] is None
    assert nullable_note["best_example_rationale"] == ""

    uninspected_best = dict(first_note)
    uninspected_best["best_example"] = "not-inspected"
    with pytest.raises(ValueError, match="must have been inspected"):
        append_freeform_gallery_note(replaced, uninspected_best)


def _inspect_first_freeform_example(stage: str) -> dict:
    tools = get_sweep_skill_tools(stage)
    example = json.loads(tools["list_freeform_examples"]())[0]
    assert tools["read_freeform_example"](
        example["example_id"]).startswith("[FREEFORM EXAMPLE]")
    note = get_freeform_gallery_note(stage)
    assert note["best_example"] is None
    return note


def test_freeform_stage_tools_accept_nullable_gallery_recommendations(
    monkeypatch,
) -> None:
    # L3_2 accepts an empty advisory gallery note.
    build_sweep_skill_context("freeform_sweep", "initial_conditions")
    for key, value in {
        "_sweep_method": "freeform_sweep",
        "_components": [],
        "_species": [],
        "_intensives": ["temperature", "ionic_strength", "pH", "E_V"],
        "_catalog_structured": {},
    }.items():
        monkeypatch.setitem(l3_2._SESSION, key, value)
    for key in ("pins", "source", "settings", "deferred", "skill_record",
                "gallery_note", "error", "latest_attempt", "restart_request"):
        monkeypatch.setitem(l3_2._FINAL_SLOT, key, None)
    source = '''
inits = [
  {"id":"T", "lhs":lambda s:s.temperature,
   "value":298.15, "basis":"known"},
  {"id":"pH", "lhs":lambda s:s.pH,
   "value":7.0, "basis":"known"},
]
'''
    accepted = l3_2._commit_initial_conditions(
        source, activity_model="ideal", solids="exclude",
        redox_mode="excluded", ionic_strength_mode="none")
    assert accepted.startswith("OK")
    initial_note = get_freeform_gallery_note("initial_conditions")
    assert initial_note["best_example"] is None
    assert initial_note["inspected_examples"] == []
    assert l3_2._FINAL_SLOT["gallery_note"] == initial_note

    # L3_3 records an inspection without requiring a recommendation.
    build_sweep_skill_context(
        "freeform_sweep", "constraints", prior_gallery_notes=[initial_note])
    for key, value in {
        "_sweep_method": "freeform_sweep",
        "_components": [],
        "_species": [],
        "_catalog_obj": None,
        "_settings": {
            "activity_model": "ideal", "solids": "exclude",
            "redox_mode": "excluded", "ionic_strength_mode": "none",
        },
        "_deferred_conditions": [],
    }.items():
        monkeypatch.setitem(l3_3._SESSION, key, value)
    for key in ("payload", "bindings", "gallery_note", "error",
                "latest_attempt", "restart_request"):
        monkeypatch.setitem(l3_3._FINAL_SLOT, key, None)
    constraint_source = '''
axes = ["pH_axis"]
lets = {}
binds = [
  {"id":"pH", "op":"==", "lhs":lambda s:s.pH,
   "rhs":lambda a:a["pH_axis"]},
  {"id":"T", "op":"==", "lhs":lambda s:s.temperature,
   "rhs":lambda s:298.15},
]
'''
    constraint_note = _inspect_first_freeform_example("constraints")
    accepted = l3_3._compile_constraint_card(constraint_source, "2")
    assert accepted.startswith("OK")
    assert l3_3._FINAL_SLOT["gallery_note"] == constraint_note

    # L3_4 includes another empty advisory note in the exact loader card.
    build_sweep_skill_context(
        "freeform_sweep", "sweep_design",
        prior_gallery_notes=[initial_note, constraint_note])
    for key, value in {
        "_sweep_method": "freeform_sweep",
        "_dof": 1,
        "_card": {"sweep_method": "freeform_sweep", "_meta": {
            "freeform_gallery_notes": [initial_note, constraint_note]}},
        "_spec": {"axes": ["pH_axis"], "binds": []},
        "_settings": {},
        "_system_catalog": {},
    }.items():
        monkeypatch.setitem(l3_4._SESSION, key, value)
    for key in ("payload", "calc_input", "error", "failure_scope",
                "latest_attempt", "restart_request", "gallery_note"):
        monkeypatch.setitem(l3_4._FINAL_SLOT, key, None)
    axes = '[{"name":"pH","min":6,"max":8,"n_points":3}]'
    monkeypatch.setattr(l3_4, "load_calc_input", lambda _card: object())
    sweep_note = get_freeform_gallery_note("sweep_design")
    assert sweep_note["best_example"] is None
    assert sweep_note["inspected_examples"] == []
    accepted = l3_4._finalize_sweep_grid(axes, '{"mode":"none"}')
    assert accepted.startswith("OK")
    notes = l3_4._FINAL_SLOT["calc_input"]["_meta"][
        "freeform_gallery_notes"]
    assert [note["stage"] for note in notes] == [
        "initial_conditions", "constraints", "sweep_design"]
    assert notes[-1] == sweep_note


def test_l3_3_enforces_deferred_roles() -> None:
    deferred = [
        {"handle": 's.total["Fe"]', "role": "swept"},
        {"handle": 's.total["ligand_1"]', "role": "derived"},
    ]
    spec = l3_3.compile_card(
        '''
axes = ["[Fe]_tot_axis"]
lets = {}
binds = [
  {"id": "M", "op": "==", "lhs": lambda s: s.total["Fe"],
   "rhs": lambda a: a["[Fe]_tot_axis"]},
  {"id": "L", "op": "==", "lhs": lambda s: s.total["ligand_1"],
   "rhs": lambda s: 2.0 * s.total["Fe"]},
]
''',
        components=["Fe", "ligand_1"],
        species=[],
        expected_K=2,
    )
    assert l3_3._validate_deferred_closures(spec, deferred) == []

    fixed_spec = {"binds": list(spec["binds"])}
    fixed_spec["binds"][1] = dict(fixed_spec["binds"][1])
    fixed_spec["binds"][1]["rhs"] = {"const": 0.01}
    issues = l3_3._validate_deferred_closures(fixed_spec, deferred)
    assert any("was fixed to a constant" in issue for issue in issues)


def test_refinement_knobs_have_no_hidden_subfield_defaults(monkeypatch) -> None:
    monkeypatch.setitem(l3_4._SESSION, "_dof", 2)
    result = l3_4._finalize_sweep_grid(
        '[{"name":"pH","min":0,"max":1,"n_points":2},'
        '{"name":"E_V","min":0,"max":1,"n_points":2}]',
        '{"mode":"boundary","factor":2}',
    )
    assert "requires explicit n_layers" in result


def test_refinement_mode_is_mandatory_and_none_is_explicit() -> None:
    try:
        l3_4._parse_refinement_design("Not defined", dof=2)
    except ValueError as exc:
        assert "Not defined" in str(exc)
    else:  # pragma: no cover - assertion aid
        raise AssertionError("undefined refinement design was accepted")

    grid_refine, design = l3_4._parse_refinement_design(
        '{"mode":"none"}', dof=1)
    assert grid_refine == {"mode": "none"}
    assert design == {"mode": "none"}


def test_l3_4_classifies_constraint_catalog_failure_as_upstream() -> None:
    assert not l3_4._loader_rejection_is_grid_repairable(ValueError(
        "calculation card constraint/DOF validation failed: "
        "LHS '[Fe$+0]_total' is not a catalog DOF"
    ))
    assert l3_4._loader_rejection_is_grid_repairable(ValueError(
        "Invalid calc-input JSON: required sweep axis/axes are Not defined"
    ))


def test_l3_4_fatal_upstream_failure_is_locked_without_loader_retry(
    monkeypatch,
) -> None:
    for key, value in {
        "_card": {},
        "_sweep_method": "pH_sweep",
        "_dof": 1,
        "_spec": {"axes": ["pH_axis"]},
        "_settings": {},
        "_system_catalog": {},
    }.items():
        monkeypatch.setitem(l3_4._SESSION, key, value)
    for key in ("payload", "calc_input", "error", "failure_scope"):
        monkeypatch.setitem(l3_4._FINAL_SLOT, key, None)

    loader_calls = 0

    def reject(_native):
        nonlocal loader_calls
        loader_calls += 1
        raise ValueError(
            "calculation card constraint/DOF validation failed: "
            "LHS '[Fe$+0]_total' is not a catalog DOF"
        )

    monkeypatch.setattr(l3_4, "load_calc_input", reject)
    arguments = (
        '[{"name":"pH","min":4,"max":9,"n_points":51}]',
        '{"mode":"none"}',
    )

    first = l3_4._finalize_sweep_grid(*arguments)
    second = l3_4._finalize_sweep_grid(*arguments)

    assert first.startswith("FATAL_UPSTREAM:")
    assert second.startswith("RESTART_LOCKED:")
    assert l3_4._FINAL_SLOT["failure_scope"] == "upstream"
    assert "Fe$+0" in l3_4._FINAL_SLOT["error"]
    assert l3_4._FINAL_SLOT["restart_request"]["automatic"] is True
    assert (l3_4._FINAL_SLOT["restart_request"]["error"]
            == l3_4._FINAL_SLOT["error"])
    assert loader_calls == 1


def test_restart_request_requires_a_current_stage_error(monkeypatch) -> None:
    stages = (l3_1, l3_2, l3_3, l3_4)
    for stage in stages:
        monkeypatch.setitem(stage._FINAL_SLOT, "error", None)
        monkeypatch.setitem(stage._FINAL_SLOT, "restart_request", None)
        result = stage._request_lc3_restart("reconsider an earlier premise")
        assert result.startswith("ERROR:")
        assert stage._FINAL_SLOT["restart_request"] is None


def test_restart_request_requires_a_direct_attempt(monkeypatch) -> None:
    for stage in (l3_1, l3_2, l3_3, l3_4):
        monkeypatch.setitem(stage._FINAL_SLOT, "error", "synthetic_error")
        monkeypatch.setitem(stage._FINAL_SLOT, "latest_attempt", None)
        monkeypatch.setitem(stage._FINAL_SLOT, "restart_request", None)
        result = stage._request_lc3_restart("reconsider an earlier premise")
        assert result.startswith("ERROR:")
        assert "directly emitted" in result
        assert stage._FINAL_SLOT["restart_request"] is None


def test_each_stage_can_request_restart_after_its_deterministic_error(
    monkeypatch,
) -> None:
    # L3_1: invalid live-registry method.
    monkeypatch.setitem(l3_1._FINAL_SLOT, "restart_request", None)
    assert l3_1._finalize_method("not-a-method", 1).startswith("ERROR:")
    assert l3_1._request_lc3_restart("method premise must change").startswith(
        "OK_RESTART_REQUESTED:")

    # L3_2/L3_3: empty directly emitted cards fail before catalog access.
    monkeypatch.setitem(l3_2._FINAL_SLOT, "restart_request", None)
    assert l3_2._commit_initial_conditions(card_source="").startswith("ERROR:")
    assert l3_2._request_lc3_restart("initial premise must change").startswith(
        "OK_RESTART_REQUESTED:")

    monkeypatch.setitem(l3_3._FINAL_SLOT, "restart_request", None)
    assert l3_3._compile_constraint_card(card_source="").startswith("ERROR:")
    assert l3_3._request_lc3_restart("constraint premise must change").startswith(
        "OK_RESTART_REQUESTED:")

    # L3_4: empty grid is a deterministic local grid error.
    for key in ("payload", "calc_input", "error", "failure_scope",
                "latest_attempt", "restart_request"):
        monkeypatch.setitem(l3_4._FINAL_SLOT, key, None)
    assert l3_4._finalize_sweep_grid("").startswith("ERROR:")
    assert l3_4._request_lc3_restart("axis premise must change").startswith(
        "OK_RESTART_REQUESTED:")

    for stage, expected in (
        (l3_1, "LC3_1"), (l3_2, "LC3_2"),
        (l3_3, "LC3_3"), (l3_4, "LC3_4"),
    ):
        request = stage._FINAL_SLOT["restart_request"]
        assert request["requested_by"] == expected
        assert request["error"] == stage._FINAL_SLOT["error"]
        assert stage._FINAL_SLOT["latest_attempt"]["arguments"]

    attempts_before = {
        stage: json.dumps(stage._FINAL_SLOT["latest_attempt"], sort_keys=True)
        for stage in (l3_1, l3_2, l3_3, l3_4)
    }
    for stage in (l3_1, l3_2, l3_3, l3_4):
        duplicate = stage._request_lc3_restart("duplicate")
        assert duplicate.startswith("ERROR:")
        assert "duplicate" in duplicate

    locked_results = (
        l3_1._finalize_method("pH_sweep", 1),
        l3_2._commit_initial_conditions(card_source="inits = []"),
        l3_3._compile_constraint_card(card_source="axes=[]\nlets={}\nbinds=[]"),
        l3_4._finalize_sweep_grid(
            '[{"name":"pH","min":0,"max":1,"n_points":2}]',
            '{"mode":"none"}',
        ),
    )
    assert all(result.startswith("RESTART_LOCKED:")
               for result in locked_results)
    for stage in (l3_1, l3_2, l3_3, l3_4):
        assert (json.dumps(stage._FINAL_SLOT["latest_attempt"], sort_keys=True)
                == attempts_before[stage])


def test_restart_context_is_injected_as_prior_evidence() -> None:
    context = {
        "requested_by": "LC3_4",
        "error": "upstream_calc_input_invalid:example",
        "latest_attempt_artifact_path": "prior/latest_attempt.json",
    }
    for stage in (l3_1, l3_2, l3_3, l3_4):
        rendered = stage._render_restart_context(context)
        assert "LC3 RESTART CONTEXT" in rendered
        assert context["error"] in rendered
        assert context["latest_attempt_artifact_path"] in rendered


def test_l3_1_restart_result_persists_direct_attempt(
    monkeypatch, tmp_path: Path,
) -> None:
    def fake_agent_turn(_message, **kwargs):
        tools = kwargs["tools"]
        assert tools["finalize_method"]("not-a-method", 1).startswith("ERROR:")
        assert tools["request_lc3_restart"](
            "the selected method premise must be reconsidered"
        ).startswith("OK_RESTART_REQUESTED:")
        return l3_1.AgentTurnResult(
            answer="restart requested", iterations=2, elapsed_seconds=0.0,
            tool_history=[], final_context="test",
        )

    monkeypatch.setattr(l3_1, "agent_turn", fake_agent_turn)
    monkeypatch.setattr(l3_1.SRD46AnalysisClient, "for_l1", lambda: object())
    l3_1.configure_l3_1_session(session_dir=tmp_path / "session")
    result = l3_1.run_l3_1(
        purpose="test", tasks="test",
        fixed_card_path=tmp_path / "unused.md",
        output_dir=tmp_path / "out",
        restart_context={"error": "prior failure"},
    )

    assert result["status"] == "restart_requested"
    assert result["restart_request"]["error"] == result["_error"]
    attempt_path = Path(result["latest_attempt_artifact_path"])
    assert attempt_path.is_file()
    attempt = json.loads(attempt_path.read_text(encoding="utf-8"))
    assert attempt["tool"] == "finalize_method"
    assert attempt["arguments"]["sweep_method"] == "not-a-method"
    assert (Path(result["output_dir"]) / "restart_request.json").is_file()


def test_l3_4_fatal_loader_error_returns_automatic_restart_artifacts(
    monkeypatch, tmp_path: Path,
) -> None:
    card_path = tmp_path / "calc_input_card.json"
    card_path.write_text(json.dumps({
        "sweep_method": "pH_sweep",
        "_meta": {
            "dof": 1,
            "sweep_skill_selection": {
                "primary_skill": "speciation-path-design",
            },
        },
        "constraint_spec": {"axes": ["pH_axis"], "binds": []},
        "constraint_settings": {},
        "system_catalog": {},
    }), encoding="utf-8")

    def reject(_native):
        raise ValueError(
            "calculation card constraint/DOF validation failed: stale catalog"
        )

    def fake_agent_turn(_message, **kwargs):
        result = kwargs["tools"]["finalize_sweep_grid"](
            '[{"name":"pH","min":4,"max":9,"n_points":51}]',
            '{"mode":"none"}',
        )
        assert result.startswith("FATAL_UPSTREAM:")
        # Deliberately do not call request_lc3_restart: fatal classification
        # must create it deterministically.
        return l3_4.AgentTurnResult(
            answer="upstream failure reported", iterations=1,
            elapsed_seconds=0.0, tool_history=[], final_context="test",
        )

    monkeypatch.setattr(l3_4, "load_calc_input", reject)
    monkeypatch.setattr(l3_4, "agent_turn", fake_agent_turn)
    monkeypatch.setattr(l3_4.SRD46AnalysisClient, "for_l1", lambda: object())
    l3_4.configure_l3_4_session(session_dir=tmp_path / "session")
    result = l3_4.run_l3_4(
        purpose="test", tasks="test",
        calc_input_card_path=card_path,
        output_dir=tmp_path / "out",
        restart_context={"error": "prior failure"},
    )

    assert result["status"] == "restart_requested"
    assert result["failure_scope"] == "upstream"
    assert result["restart_request"]["automatic"] is True
    assert result["restart_request"]["error"] == result["_error"]
    attempt_path = Path(result["latest_attempt_artifact_path"])
    assert attempt_path.is_file()
    attempt = json.loads(attempt_path.read_text(encoding="utf-8"))
    assert attempt["tool"] == "finalize_sweep_grid"
    assert "n_points" in attempt["arguments"]["axes_json"]
    assert attempt["assembled_calc_input"]["sweep_axes"] == [
        {"name": "pH", "min": 4.0, "max": 9.0, "n_points": 51}
    ]
    assert attempt["assembled_calc_input"]["grid_refine"] == {"mode": "none"}
    assert (Path(result["output_dir"]) / "restart_request.json").is_file()
