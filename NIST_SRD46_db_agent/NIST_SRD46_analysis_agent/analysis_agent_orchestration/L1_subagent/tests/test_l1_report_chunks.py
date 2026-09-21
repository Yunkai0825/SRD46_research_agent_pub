from __future__ import annotations

import json
from pathlib import Path

from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.analysis_agent_orchestration.L1_subagent.l1_estimation_audit import (
    _ANALYSIS_CHUNK_MAX_CHARS,
    _make_append_analysis_chunk,
    _make_record_analysis,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.analysis_agent_orchestration.L1_subagent.l1_state import (
    _L1State,
)


def _state(tmp_path: Path) -> _L1State:
    call_dir = tmp_path / "L1_call_01"
    call_dir.mkdir()
    return _L1State(
        purpose="test long report",
        tasks_text="test",
        call_dir=call_dir,
        idx=1,
    )


def test_ordered_chunks_commit_exact_report(tmp_path: Path) -> None:
    state = _state(tmp_path)
    append = _make_append_analysis_chunk(state)
    record = _make_record_analysis(state)
    chunks = [
        "## Doability\nDoable.\n\n",
        "## Result\nUnicode chemistry: Fe³⁺ ⇌ Fe²⁺.\n\n",
        "## Analysis\nThe staged report is complete.",
    ]

    assert append(1, chunks[0], reset=True).startswith("OK")
    assert append(2, chunks[1]).startswith("OK")
    assert append(3, chunks[2]).startswith("OK")
    receipt = record(
        analysis_markdown="",
        artifact_paths="solver/a.csv, solver/b.md",
        expected_chunks=3,
    )

    expected = "".join(chunks)
    assert receipt.startswith("OK")
    assert state.agent_committed_report is True
    assert state.committed_report == expected
    assert state.artifacts == ["solver/a.csv", "solver/b.md"]
    assert (state.call_dir / "l1_report.md").read_text(
        encoding="utf-8"
    ) == expected
    persisted = json.loads(
        (state.call_dir / "l1_analysis.json").read_text(encoding="utf-8")
    )
    assert persisted == {
        "analysis": expected,
        "artifacts": ["solver/a.csv", "solver/b.md"],
    }
    ledger = json.loads(
        (state.call_dir / "l1_report_draft.json").read_text(encoding="utf-8")
    )
    assert ledger["chunk_count"] == 3
    assert ledger["committed"] is True


def test_chunk_replay_is_idempotent_and_order_is_strict(tmp_path: Path) -> None:
    state = _state(tmp_path)
    append = _make_append_analysis_chunk(state)

    assert append(1, "first", reset=True).startswith("OK")
    replay = append(1, "first")
    assert replay.startswith("OK")
    assert "idempotent replay" in replay
    assert state.analysis_draft_chunks == ["first"]

    conflict = append(1, "different")
    assert conflict.startswith("ERROR")
    assert "different content" in conflict
    assert append(3, "third").startswith("ERROR: out-of-order")
    assert append(2, "x" * (_ANALYSIS_CHUNK_MAX_CHARS + 1)).startswith(
        "ERROR: analysis chunk is too large"
    )
    assert state.analysis_draft_chunks == ["first"]


def test_incomplete_or_mixed_staged_commit_is_rejected(tmp_path: Path) -> None:
    state = _state(tmp_path)
    append = _make_append_analysis_chunk(state)
    record = _make_record_analysis(state)

    assert append(1, "## Result\nPart one.\n", reset=True).startswith("OK")
    mismatch = record(
        analysis_markdown="",
        artifact_paths="solver/result.csv",
        expected_chunks=2,
    )
    assert mismatch.startswith("ERROR: staged report is incomplete")
    assert state.agent_committed_report is False
    assert not (state.call_dir / "l1_report.md").exists()

    mixed = record(
        analysis_markdown="inline report",
        expected_chunks=1,
    )
    assert mixed.startswith("ERROR: do not mix")
    assert state.agent_committed_report is False

    assert append(2, "\nPart two.").startswith("OK")
    assert record(
        analysis_markdown="",
        expected_chunks=2,
    ).startswith("OK")
    assert state.committed_report == "## Result\nPart one.\n\nPart two."


def test_short_inline_report_remains_backward_compatible(tmp_path: Path) -> None:
    state = _state(tmp_path)
    record = _make_record_analysis(state)

    receipt = record(
        analysis_markdown="\n## Result\nShort report.\n",
        artifact_paths="solver/result.csv",
    )

    assert receipt.startswith("OK")
    assert state.committed_report == "## Result\nShort report."
    assert state.agent_committed_report is True


def test_enabled_commit_preserves_prose_and_appends_provenance(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    state.estimate_missing_equilibria = True
    state.pipeline_status = {
        "estimated_equilibrium_enrichment": {
            "status": "ok",
            "estimation_search_complete": True,
            "materialized_estimated_entry_count": 1,
            "source": "SRD46 query estimated values",
            "estimated_stability_constants": [
                {
                    "metal_name": "Fe^[2+]",
                    "ligand_name": "DMF",
                    "beta_definition_id": 894,
                    "log10_K": 2.1,
                    "uncertainty_log10": 0.8,
                    "temperature_C": 25.0,
                    "ionic_strength_M": 0.1,
                    "estimation_method": "donor-number interpolation",
                    "evidence_vlm_ids": ["vlm_176061"],
                }
            ],
        }
    }
    record = _make_record_analysis(state)
    prose = "## Doability\nDoable.\n\n## Analysis\nDMF binds weakly."

    receipt = record(analysis_markdown=prose, artifact_paths="solver/a.csv")

    assert receipt.startswith("OK")
    committed = state.committed_report or ""
    assert committed.startswith(prose)
    assert "## Estimated-value provenance (deterministic)" in committed
    assert "search complete" in committed
    assert "donor-number interpolation" in committed
    assert "vlm_176061" in committed
    assert (state.call_dir / "l1_report.md").read_text(
        encoding="utf-8"
    ) == committed


def test_enabled_commit_incomplete_search_appendix_fails_closed(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    state.estimate_missing_equilibria = True
    state.pipeline_status = {
        "estimated_equilibrium_enrichment": {
            "status": "reference_only",
            "estimation_search_complete": False,
            "reference_only_reason": "support_eq_map_validation_failure",
            "failure_summary": {
                "n_parser_failures": 2,
                "n_scope_limit_omissions": 1,
            },
            "estimated_stability_constants": [],
        }
    }
    record = _make_record_analysis(state)

    receipt = record(analysis_markdown="## Result\nReference-only run.")

    assert receipt.startswith("OK")
    committed = state.committed_report or ""
    assert committed.startswith("## Result\nReference-only run.")
    assert "search INCOMPLETE" in committed
    assert "support_eq_map_validation_failure" in committed
    assert "parser failures: 2" in committed
    assert "scope-limit omissions: 1" in committed
    assert "No estimated stability constant was materialized" in committed

