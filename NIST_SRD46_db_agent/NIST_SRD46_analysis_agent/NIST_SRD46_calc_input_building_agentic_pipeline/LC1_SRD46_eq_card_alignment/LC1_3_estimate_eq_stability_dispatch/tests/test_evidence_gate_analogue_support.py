"""Focused contracts for mixed-topology analogue evidence."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest


THIS_FILE = Path(__file__).resolve()
for _path in (THIS_FILE.parents[6],):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.parse_speciation_answer.evidence_gate import (  # noqa: E501
    EvidenceGateError,
    validate_evidence_snapshot,
)


def _digest(payload: dict) -> str:
    return hashlib.sha256(json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")).hexdigest()


def _snapshot(*, matching_beta: bool) -> dict:
    receipt_digest = "1" * 64
    target_beta_ids = [812] if matching_beta else [872]
    payload = {
        "authorization_kind": "LC1_3 scoped evidence authorization",
        "authorization_version": 3,
        "authorization_context_id": "q001",
        "scope": {"metal_id": 61, "ligand_id": 9825},
        "observed_vlm_ids": [168274, 168275],
        "observed_beta_definition_ids": [812, 840, 872],
        "observed_network_ids": [],
        "observed_literature_ids": [],
        "tool_receipts": [{
            "result_sha256": receipt_digest,
            "observed_vlm_ids": [168274, 168275],
            "observed_beta_definition_ids": [812, 840, 872],
            "observed_network_ids": [],
            "observed_literature_ids": [],
        }],
        "vlm_records": [
            {
                "vlm_id": 168274,
                "canonical_status": "ok",
                "beta_definition_ids": [840],
                "receipt_sha256s": [receipt_digest],
            },
            {
                "vlm_id": 168275,
                "canonical_status": "ok",
                "beta_definition_ids": target_beta_ids,
                "receipt_sha256s": [receipt_digest],
            },
        ],
        "network_records": [],
        "literature_records": [],
    }
    payload["snapshot_sha256"] = _digest(payload)
    return payload


def _claim() -> list[dict]:
    return [{
        "beta_definition_id": 812,
        "evidence_vlm_ids": [168274, 168275],
        "evidence_network_ids": [],
        "evidence_citation_ids": [],
    }]


def test_mixed_topology_analogues_are_allowed_with_one_exact_anchor() -> None:
    receipt, _ = validate_evidence_snapshot(
        equilibria=_claim(),
        scope={"metal_id": 61, "ligand_id": 9825},
        snapshot=_snapshot(matching_beta=True),
        expected_context_id="q001",
    )

    assert receipt["validated_claims"][0]["evidence_vlm_ids"] == [168274, 168275]


def test_mixed_topology_analogues_fail_without_an_exact_anchor() -> None:
    with pytest.raises(
        EvidenceGateError,
        match=r"at least one cited VLM that supports beta_def_812",
    ):
        validate_evidence_snapshot(
            equilibria=_claim(),
            scope={"metal_id": 61, "ligand_id": 9825},
            snapshot=_snapshot(matching_beta=False),
            expected_context_id="q001",
        )


def test_cross_topology_only_evidence_requires_host_resolution_mode() -> None:
    receipt, _ = validate_evidence_snapshot(
        equilibria=_claim(),
        scope={"metal_id": 61, "ligand_id": 9825},
        snapshot=_snapshot(matching_beta=False),
        expected_context_id="q001",
        allow_analogue_topology=True,
    )

    diagnostic = receipt["validated_claims"][0]
    assert diagnostic["matching_beta_vlm_ids"] == []
    assert diagnostic["analogue_vlm_ids"] == [168274, 168275]
    assert diagnostic["topology_grounding"] == "host_resolution_receipt"


def test_unobserved_analogue_remains_rejected() -> None:
    claim = _claim()
    claim[0]["evidence_vlm_ids"].append(999999)

    with pytest.raises(EvidenceGateError, match="VLM not shown by a tool"):
        validate_evidence_snapshot(
            equilibria=claim,
            scope={"metal_id": 61, "ligand_id": 9825},
            snapshot=_snapshot(matching_beta=True),
            expected_context_id="q001",
        )


def test_noncanonical_analogue_remains_rejected() -> None:
    snapshot = _snapshot(matching_beta=True)
    snapshot["vlm_records"][0]["canonical_status"] = "conflict"
    snapshot.pop("snapshot_sha256")
    snapshot["snapshot_sha256"] = _digest(snapshot)

    with pytest.raises(EvidenceGateError, match=r"vlm_168274 is not canonical"):
        validate_evidence_snapshot(
            equilibria=_claim(),
            scope={"metal_id": 61, "ligand_id": 9825},
            snapshot=snapshot,
            expected_context_id="q001",
        )
