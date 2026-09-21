from __future__ import annotations

import json
from pathlib import Path

from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.runtime_support.artifacts import (
    _io_path,
    logical_path,
    read_bytes,
    read_text,
    record_query_turn,
    write_json,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.runtime_support.runtime_models import (
    QueryTurn,
)


def _deep_output_root(tmp_path: Path) -> Path:
    root = tmp_path
    policy_tail = Path("query_agents") / "q001" / "evidence_receipts.json"
    index = 0
    while len(str((root / policy_tail).absolute())) <= 300:
        root /= f"lc1_3_artifact_segment_{index:02d}"
        index += 1
    return root


def test_record_query_turn_then_receipts_round_trip_beyond_max_path(
    tmp_path: Path,
) -> None:
    output_root = _deep_output_root(tmp_path)
    artifact_dir = output_root / "query_agents" / "q001"
    turn_dir = artifact_dir / "01_dispatch_srd46_query"
    receipt_path = artifact_dir / "evidence_receipts.json"
    stage_manifest_path = output_root / "02_dispatch_srd46_query_manifest.json"
    turn = QueryTurn(
        answer="bounded answer",
        memory=[{"role": "assistant", "content": "bounded answer"}],
        tool_history=[{"tool": "search_stability", "status": "ok"}],
        compactor_events=[],
        model_history=[{"round": 1}],
        elapsed_s=0.25,
    )

    assert len(str(receipt_path.absolute())) > 260
    assert not str(receipt_path).startswith("\\\\?\\")

    record_query_turn(
        turn_dir=turn_dir,
        user_prompt="bounded prompt",
        system_prompt="bounded system prompt",
        turn=turn,
    )
    write_json(receipt_path, {"query_id": "q001", "kind": "evidence_receipts"})
    write_json(
        stage_manifest_path,
        {
            "query_id": "q001",
            "artifact_dir": str(artifact_dir),
            "evidence_receipts_path": str(receipt_path),
        },
    )

    turn_manifest = json.loads(
        read_text(turn_dir / "turn_manifest.json", encoding="utf-8")
    )
    receipts = json.loads(read_bytes(receipt_path).decode("utf-8"))
    stage_manifest = json.loads(read_text(stage_manifest_path, encoding="utf-8"))
    assert turn_manifest["tool_calls"] == 1
    assert receipts == {"query_id": "q001", "kind": "evidence_receipts"}
    assert read_text(turn_dir / "answer.md", encoding="utf-8") == "bounded answer"
    assert stage_manifest["artifact_dir"] == str(artifact_dir)
    assert stage_manifest["evidence_receipts_path"] == str(receipt_path)
    assert "\\\\?\\" not in json.dumps(stage_manifest)


def test_nested_or_single_slash_extended_unc_is_normalized() -> None:
    ordinary = (
        r"\\fileserver.example.invalid\research$\workspace"
        r"\SRD46_research_agent\repair_coordinator\q001"
    )
    broken = (
        r"\?\UNC\fileserver.example.invalid\research$\workspace"
        r"\SRD46_research_agent\repair_coordinator\q001"
    )
    nested = (
        r"\\?\UNC\?\UNC\fileserver.example.invalid\research$"
        r"\workspace\SRD46_research_agent\repair_coordinator\q001"
    )

    assert str(logical_path(broken)) == ordinary
    assert str(logical_path(nested)) == ordinary
    assert str(_io_path(nested)).startswith(
        r"\\?\UNC\fileserver.example.invalid\research$"
    )
    assert "\\UNC\\?\\UNC\\" not in str(_io_path(nested))
