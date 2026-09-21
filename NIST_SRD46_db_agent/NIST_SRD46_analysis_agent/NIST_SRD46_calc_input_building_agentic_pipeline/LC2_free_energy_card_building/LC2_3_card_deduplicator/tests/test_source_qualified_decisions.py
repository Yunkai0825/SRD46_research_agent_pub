from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


_THIS = Path(__file__).resolve()
_PIPELINE_ROOT = _THIS.parents[3]
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from card_management_helpers.dedup_md_card_reader import (  # noqa: E402
    DedupGroup,
    DedupReport,
    DedupSpecies,
)
from LC2_free_energy_card_building.LC2_3_card_deduplicator._dedup_engine.decision_apply import (  # noqa: E402,E501
    compute_drop_keys,
    decisions_from_dicts,
)
from LC2_free_energy_card_building.LC2_3_card_deduplicator._pair_dedup_subagent.per_stoich_group_agent import (  # noqa: E402,E501
    _format_group_user_msg,
    _make_group_tools,
)
from LC2_free_energy_card_building.LC2_3_card_deduplicator._pair_dedup_subagent.singleton_agent import (  # noqa: E402,E501
    _build_singleton_group_decisions,
    _format_singletons_user_msg,
    _make_singleton_tools,
)
from LC2_free_energy_card_building.LC2_3_card_deduplicator.lc2_3_dedup_agent import (  # noqa: E402,E501
    _render_report,
)


def _species(name: str, source: str) -> DedupSpecies:
    return DedupSpecies(
        name=name,
        source=source,
        charge=1,
        multiplier=1,
        mu_aligned_kJ=-10.0,
        phase="aqueous",
        core_label="Fe_3_1_H_-2",
    )


def _report(*species: DedupSpecies) -> DedupReport:
    return DedupReport(
        system_name="Fe test",
        baseline_source="SRD-46",
        sources_present=["SRD-46", "Atlas"],
        component_mapping=[],
        groups=[DedupGroup(
            phase="aqueous",
            core_label="Fe_3_1_H_-2",
            species=list(species),
        )],
        totals={},
    )


def test_source_qualified_decision_can_drop_same_named_atlas_species():
    report = _report(
        _species("[Fe(OH)2]+", "SRD-46"),
        _species("[Fe(OH)2]+", "Atlas"),
    )
    decisions = decisions_from_dicts([{
        "phase": "aqueous",
        "core_label": "Fe_3_1_H_-2",
        "keep_species": [{"name": "[Fe(OH)2]+", "source": "SRD-46"}],
        "rationale": "Prefer the evaluated SRD-46 entry.",
    }])

    dropped, notes, audit = compute_drop_keys(report, decisions)

    assert dropped == {("[Fe(OH)2]+", "Atlas")}
    assert ("[Fe(OH)2]+", "Atlas") in notes
    assert [row["decision"] for row in audit] == ["kept", "dropped"]


def test_ambiguous_legacy_name_only_decision_fails_loudly():
    report = _report(
        _species("[Fe(OH)2]+", "SRD-46"),
        _species("[Fe(OH)2]+", "Atlas"),
    )
    decisions = decisions_from_dicts([{
        "phase": "aqueous",
        "core_label": "Fe_3_1_H_-2",
        "keep_names": ["[Fe(OH)2]+"],
    }])

    with pytest.raises(ValueError, match="Ambiguous legacy LC2_3 keep_names"):
        compute_drop_keys(report, decisions)


def test_unambiguous_legacy_name_only_decision_remains_supported():
    report = _report(
        _species("[Fe(OH)2]+", "SRD-46"),
        _species("[FeOH]2+", "Atlas"),
    )
    decisions = decisions_from_dicts([{
        "phase": "aqueous",
        "core_label": "Fe_3_1_H_-2",
        "keep_names": ["[Fe(OH)2]+"],
    }])

    dropped, _, _ = compute_drop_keys(report, decisions)

    assert dropped == {("[FeOH]2+", "Atlas")}


def test_group_without_verdict_is_explicitly_not_examined():
    report = _report(_species("[Fe(OH)2]+", "SRD-46"))

    dropped, notes, audit = compute_drop_keys(report, [])

    assert dropped == set()
    assert notes == {}
    assert audit[0]["decision"] == "not examined"
    assert audit[0]["rationale"] == "no decision supplied"


def test_group_tool_requires_and_preserves_exact_name_source_pair():
    slot = {"payload": None, "error": None}
    tool = _make_group_tools(slot, [
        {"name": "[Fe(OH)2]+", "source": "SRD-46"},
        {"name": "[Fe(OH)2]+", "source": "Atlas"},
    ])["finalize_group_decision"]

    reply = tool(json.dumps({
        "keep_species": [{"name": "[Fe(OH)2]+", "source": "SRD-46"}],
        "rationale": "Prefer SRD-46.",
    }))

    assert reply.startswith("OK")
    assert slot["payload"]["keep_species"] == [
        {"name": "[Fe(OH)2]+", "source": "SRD-46"}
    ]

    legacy_reply = tool(json.dumps({
        "keep_names": ["[Fe(OH)2]+"],
        "rationale": "Ambiguous old contract.",
    }))
    assert legacy_reply.startswith("ERROR")


def test_singleton_decision_uses_source_qualified_identity():
    singletons = [{
        "phase": "solid",
        "core_label": "Fe_3_1_H_-3",
        "species": [{"name": "[Fe(OH)3](s)", "source": "SRD-46"}],
    }]
    rows = [{
        "phase": "solid",
        "core_label": "Fe_3_1_H_-3",
        "keep": True,
        "rationale": "Valid singleton.",
    }]

    decisions = _build_singleton_group_decisions(singletons, rows)

    assert decisions[0]["keep_species"] == [
        {"name": "[Fe(OH)3](s)", "source": "SRD-46"}
    ]
    assert "keep_names" not in decisions[0]


def test_singleton_tool_rejects_string_boolean():
    slot = {"payload": None, "error": None}
    tool = _make_singleton_tools(
        slot, [("solid", "Fe$+2:1 H:-2")]
    )["finalize_singleton_decisions"]

    response = tool(json.dumps({"decisions": [{
        "phase": "solid",
        "core_label": "Fe$+2:1 H:-2",
        "keep": "false",
        "rationale": "Malformed model output.",
    }]}))

    assert response.startswith("ERROR")
    assert slot["payload"] is None


def test_worker_messages_use_supervisor_plan_without_raw_user_fields():
    group = {
        "elements": ["Cu"],
        "phase": "solid",
        "core_label": "Cu$+2:1 H:-2",
        "species": [{
            "entry_key": "DEDUP-test",
            "phase_family": "hydrated_solid",
            "name": "[Cu(OH)2](s)",
            "source": "SRD-46",
            "charge": 0,
            "mu_aligned_kJ": 1.0,
            "multiplier": 1,
        }],
    }

    messages = (
        _format_group_user_msg(group, "SUPERVISOR PLAN"),
        _format_singletons_user_msg([group], "SUPERVISOR PLAN"),
    )
    for message in messages:
        assert "SUPERVISOR PLAN" in message
        assert "[Original calculation purpose]" not in message
        assert "[Original requested tasks]" not in message


def test_dispatch_summary_displays_source_qualified_survivor():
    report = _report(
        _species("[Fe(OH)2]+", "SRD-46"),
        _species("[Fe(OH)2]+", "Atlas"),
    )
    decision = {
        "phase": "aqueous",
        "core_label": "Fe_3_1_H_-2",
        "keep_species": [{"name": "[Fe(OH)2]+", "source": "SRD-46"}],
        "rationale": "Prefer SRD-46.",
    }

    rendered = _render_report(
        call_index=1,
        out_card=Path("deduplicated.md"),
        merged_card_path=Path("merged.md"),
        report_obj=report,
        multi=report.groups,
        singles=[],
        decisions=[decision],
        edit_audit=[],
        failures=[],
        elapsed_llm=0.0,
        elapsed=0.0,
        n_iters=1,
        n_tool_calls=1,
    )

    assert "`[Fe(OH)2]+` [SRD-46]" in rendered
    assert "| phase | core_label | keep_species | rationale |" in rendered
