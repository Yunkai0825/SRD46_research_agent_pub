"""Contracts for the gated per-draft annotation phase (annotate, rebind, commit)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


THIS_FILE = Path(__file__).resolve()
for _path in (THIS_FILE.parents[6],):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.parse_speciation_answer.candidate_schema import (  # noqa: E501
    GateReport,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.parse_speciation_answer.parser_batch_policy import (  # noqa: E501
    ParserBatchPolicy,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.parse_speciation_answer.parser_gate_service import (  # noqa: E501
    ParserGateService,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.parse_speciation_answer.parser_tools import (  # noqa: E501
    ParserToolbox,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.parse_speciation_answer.parser_working_state import (  # noqa: E501
    ParserWorkingState,
)


def _service(tmp_path: Path) -> ParserGateService:
    state = ParserWorkingState.create(
        query_id="q001",
        scope={"metal_id": 61, "ligand_id": 9825},
        request_T_C=25.0,
        request_I_M=0.1,
        base_eq_map_card={"equilibrium_networks": []},
        initial_answer=(
            "For beta_def_872 I estimate log10 K = 20.4 with uncertainty 0.5 "
            "using vlm_93785 in ref_eq_net_55, linked to lit_88, by analogue "
            "transfer."
        ),
        evidence_snapshot={
            "observed_beta_definition_ids": [872],
            "observed_vlm_ids": [93785, 100001],
            "observed_network_ids": [55],
            "observed_literature_ids": [88],
        },
    )
    state.create_draft({
        "beta_definition_id": 872,
        "constant_value": 20.4,
        "evidence_vlm_ids": [93785],
        "evidence_network_ids": [55],
        "estimation_method": "analogue transfer",
        "assumptions": ["the same reference state"],
        "rationale": "HIDA chelates the metal",
    })
    return ParserGateService(
        state=state,
        base_eq_map_card={"equilibrium_networks": []},
        session_id="annotation-test",
        artifact_dir=tmp_path,
    )


def _seal(service: ParserGateService, *, receipt: str = "a" * 64) -> None:
    """Fabricate the post-network-gate state annotate_draft depends on."""

    draft = service.state.drafts["d001"]
    draft.canonical_equilibrium = {
        "beta_definition_id": 872,
        "constant_value": 20.4,
    }
    draft.entry_gate_receipt_sha256 = receipt
    service.state.record_report(GateReport(
        gate="network",
        status="pass",
        state_revision=service.state.revision,
    ))


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "discussion": (
            "Analogue transfer from vlm_93785 in ref_eq_net_55 gives "
            "log10 K = 20.4 for the fully chelated one-to-one complex."
        ),
        "core_source_ids": ["ref_eq_net_55", "vlm_93785"],
    }
    payload.update(overrides)
    return payload


def test_annotate_requires_sealed_current_revision(tmp_path: Path) -> None:
    service = _service(tmp_path)

    with pytest.raises(ValueError, match="unknown draft_id"):
        service.annotate_draft("d999", _payload())
    with pytest.raises(ValueError, match="run run_network_gate first, then"):
        service.annotate_draft("d001", _payload())

    # A network pass alone is not enough: the draft needs its entry receipt.
    service.state.record_report(GateReport(
        gate="network",
        status="pass",
        state_revision=service.state.revision,
    ))
    with pytest.raises(ValueError, match="no current entry-gate receipt"):
        service.annotate_draft("d001", _payload())

    # A pass from an older revision never authorizes annotation.
    _seal(service)
    service.state.update_draft("d001", {"rationale": "revised rationale"})
    with pytest.raises(ValueError, match="current\\s+workspace revision"):
        service.annotate_draft("d001", _payload())


def test_annotate_rejects_malformed_payloads(tmp_path: Path) -> None:
    service = _service(tmp_path)
    _seal(service)

    with pytest.raises(ValueError, match="unknown keys"):
        service.annotate_draft("d001", _payload(note="extra"))
    with pytest.raises(ValueError, match="must be one string"):
        service.annotate_draft("d001", _payload(discussion=20.4))
    with pytest.raises(ValueError, match="too short"):
        service.annotate_draft("d001", _payload(discussion="log10 K = 20.4"))
    with pytest.raises(ValueError, match="exceeds"):
        service.annotate_draft("d001", _payload(discussion="x" * 1300))
    with pytest.raises(ValueError, match="must stand alone"):
        service.annotate_draft("d001", _payload(discussion=(
            "The value 20.4 follows the same transfer argument already "
            "written for draft d002; see its annotation for details."
        )))


def test_annotate_enforces_source_id_roles(tmp_path: Path) -> None:
    service = _service(tmp_path)
    _seal(service)
    plain = (
        "The transfer argument lands the cumulative constant at 20.4 "
        "under matched reference conditions."
    )

    with pytest.raises(ValueError, match="must be a list"):
        service.annotate_draft(
            "d001", _payload(core_source_ids="vlm_93785"),
        )
    with pytest.raises(ValueError, match="malformed source IDs"):
        service.annotate_draft(
            "d001", _payload(core_source_ids=["93785"]),
        )
    with pytest.raises(ValueError, match="at least one load-bearing source"):
        service.annotate_draft(
            "d001", _payload(discussion=plain, core_source_ids=[]),
        )
    with pytest.raises(ValueError, match="not cited evidence"):
        service.annotate_draft(
            "d001", _payload(discussion=plain, core_source_ids=["lit_88"]),
        )
    with pytest.raises(ValueError, match="never observed"):
        service.annotate_draft("d001", _payload(
            secondary_source_ids=["vlm_999999"],
        ))
    with pytest.raises(ValueError, match="both core_source_ids and"):
        service.annotate_draft("d001", _payload(
            secondary_source_ids=["vlm_93785"],
        ))
    with pytest.raises(ValueError, match="neither core_source_ids nor"):
        service.annotate_draft("d001", _payload(discussion=(
            "Analogue transfer anchored by vlm_93785 and corroborated by "
            "lit_88 gives log10 K = 20.4 for the chelate."
        ), core_source_ids=["vlm_93785"]))
    with pytest.raises(ValueError, match="state the committed value"):
        service.annotate_draft("d001", _payload(discussion=(
            "The answer argues by analogue transfer from the cited network "
            "records without restating the number here."
        )))

    # Observed-but-uncited IDs are legal exactly once declared as secondary.
    result = service.annotate_draft("d001", _payload(
        discussion=(
            "Analogue transfer anchored by vlm_93785 and corroborated by "
            "lit_88 gives log10 K = 20.4 for the chelate."
        ),
        core_source_ids=["vlm_93785"],
        secondary_source_ids=["lit_88"],
    ))
    assert result["status"] == "annotated"


def test_annotate_stores_replaces_and_never_bumps_revision(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    _seal(service)
    revision = service.state.revision

    first = service.annotate_draft("d001", _payload(discussion=(
        # beta_def mentions need no declaration; only vlm/network/lit do.
        "For beta_def_872 the transfer argument gives log10 K = 20.4 "
        "from the single anchor record."
    ), core_source_ids=["vlm_93785"]))
    assert first["status"] == "annotated"
    assert first["replaced_previous"] is False
    assert first["liveness"] == "annotated"

    second = service.annotate_draft("d001", _payload())
    assert second["replaced_previous"] is True
    assert second["annotation_sha256"] != first["annotation_sha256"]

    assert service.state.revision == revision
    assert service.network_passed_at_current_revision()
    assert service.annotation_gaps() == []
    stored = service.state.annotations["d001"]
    assert stored.core_source_ids == ["ref_eq_net_55", "vlm_93785"]
    assert stored.bound_entry_receipt_sha256 == "a" * 64
    events = [event["event"] for event in service.state.events]
    assert events.count("draft_annotated") == 2

    snapshot = service.state.as_dict()
    assert snapshot["annotations"][0]["draft_id"] == "d001"
    assert snapshot["annotations"][0]["liveness"] == "annotated"


def test_annotation_lifecycle_stale_rebind_discard(tmp_path: Path) -> None:
    service = _service(tmp_path)
    _seal(service)
    service.annotate_draft("d001", _payload())
    annotation = service.state.annotations["d001"]
    assert service.state.annotation_liveness("d001") == "annotated"

    # Any draft mutation clears receipts: the annotation dangles as stale.
    service.state.update_draft("d001", {"rationale": "sharper rationale"})
    assert service.state.annotation_liveness("d001") == "stale"
    assert service.annotation_gaps() == [
        {"draft_id": "d001", "liveness": "stale"},
    ]

    # Re-seal with unchanged canonical content: the annotation auto-rebinds.
    service.state.drafts["d001"].entry_gate_receipt_sha256 = "b" * 64
    service.state.rebind_annotation(
        "d001",
        entry_receipt_sha256="b" * 64,
        canonical_sha256_value=annotation.bound_canonical_sha256,
    )
    assert annotation.bound_entry_receipt_sha256 == "b" * 64
    assert service.state.annotation_liveness("d001") == "annotated"
    assert "annotation_rebound" in [
        event["event"] for event in service.state.events
    ]

    # Re-seal with changed canonical content: the annotation stays stale.
    service.state.drafts["d001"].entry_gate_receipt_sha256 = "c" * 64
    service.state.rebind_annotation(
        "d001",
        entry_receipt_sha256="c" * 64,
        canonical_sha256_value="0" * 64,
    )
    assert annotation.bound_entry_receipt_sha256 == "b" * 64
    assert service.state.annotation_liveness("d001") == "stale"

    service.state.discard_draft("d001")
    assert service.state.annotations == {}
    dropped = [
        event for event in service.state.events
        if event["event"] == "draft_discarded"
    ]
    assert dropped[-1]["details"]["annotation_dropped"] is True


def test_commit_preblock_lists_annotation_gaps(tmp_path: Path) -> None:
    service = _service(tmp_path)
    policy = ParserBatchPolicy(service)
    commit = [{
        "name": "finish_parser_cycle",
        "arguments": {"action": "commit"},
    }]

    _seal(service)
    blocked = policy.validate(list(commit), {}) or ""
    assert "annotate_equilibrium_draft for: d001 (unannotated)" in blocked

    service.annotate_draft("d001", _payload())
    assert policy.validate(list(commit), {}) is None

    # After a mutation the network pre-block fires first; once the gate
    # passes again at the new revision the stale annotation blocks commit.
    service.state.update_draft("d001", {"rationale": "revised rationale"})
    assert "current workspace revision" in (policy.validate(list(commit), {}) or "")
    service.state.record_report(GateReport(
        gate="network",
        status="pass",
        state_revision=service.state.revision,
    ))
    assert "d001 (stale)" in (policy.validate(list(commit), {}) or "")


def test_toolbox_annotate_call_is_individually_recoverable(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    _seal(service)
    toolbox = ParserToolbox(service)
    assert "annotate_equilibrium_draft" in toolbox.tools()

    # A truncated payload fails only this call and leaves no annotation.
    with pytest.raises(ValueError, match="annotation_json must be one JSON"):
        toolbox.annotate_equilibrium_draft(
            draft_id="d001",
            annotation_json='{"discussion": "truncated',
        )
    assert service.state.annotations == {}

    result = json.loads(toolbox.annotate_equilibrium_draft(
        draft_id="d001",
        annotation_json=json.dumps(_payload()),
    ))
    assert result["status"] == "annotated"

    inspected = json.loads(toolbox.inspect_drafts())
    assert inspected["annotations"][0]["draft_id"] == "d001"
    assert inspected["annotations"][0]["liveness"] == "annotated"

    contract = service.parser_context()["annotation_contract"]
    assert contract["tool"] == "annotate_equilibrium_draft"
    assert any("stand alone" in rule for rule in contract["rules"])
