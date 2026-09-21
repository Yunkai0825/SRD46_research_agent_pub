from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC3_solver_para_card_building import (
    sweep_template_router as router,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC3_solver_para_card_building.freeform_gallery_registry import (
    STAGE_FOLDERS,
    audit_freeform_gallery,
    gallery_dir,
    visible_freeform_gallery_index,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC3_solver_para_card_building.freeform_gallery_validation import (
    CANONICAL_GALLERY_IDS,
)


BLOCKED_TEMPERATURE_ID = "multidimensional-ph-temperature-composition"


def test_repository_registry_hides_only_non_solving_entry() -> None:
    report = audit_freeform_gallery()
    assert set(report["registered_ids"]) == set(CANONICAL_GALLERY_IDS)
    assert set(report["visible_ids"]) == (
        set(CANONICAL_GALLERY_IDS) - {BLOCKED_TEMPERATURE_ID})
    assert set(report["hidden"]) == {BLOCKED_TEMPERATURE_ID}
    assert report["hidden"][BLOCKED_TEMPERATURE_ID][0]["code"] == (
        "solve_status_not_passed")

    for stage in STAGE_FOLDERS:
        index, stage_report = visible_freeform_gallery_index(stage)
        assert list(index) == report["visible_ids"]
        assert stage_report["fingerprint"] == report["fingerprint"]
        for gallery_id, (_, path) in index.items():
            assert path.stem == gallery_id


def test_debug_registry_self_check_runs_every_canonical_solver_case() -> None:
    report = audit_freeform_gallery(run_solve_checks=True)
    assert set(report["solve_checks"]) == set(CANONICAL_GALLERY_IDS)
    for gallery_id in report["visible_ids"]:
        result = report["solve_checks"][gallery_id]
        assert result["status"] == "passed", result
        assert result["all_converged"] is True
        assert result["actual_shape"] == result["expected_shape"]

    blocked = report["solve_checks"][BLOCKED_TEMPERATURE_ID]
    assert blocked["status"] == "failed"
    assert any("temperature is 'Not defined'" in issue
               for issue in blocked["issues"])
    codes = {item["code"] for item in report["hidden"][
        BLOCKED_TEMPERATURE_ID]}
    assert {"solve_status_not_passed", "solve_check_failed"} <= codes


def _write_registry(root: Path, ids: list[str]) -> None:
    def content_hash(gallery_id: str) -> str:
        paths = [gallery_dir(root, stage) / f"{gallery_id}.md"
                 for stage in STAGE_FOLDERS]
        if not all(path.is_file() for path in paths):
            return "0" * 64
        digest = hashlib.sha256()
        for stage, path in zip(STAGE_FOLDERS, paths):
            digest.update(stage.encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()

    entries = {
        gallery_id: {
            "title": f"Title {gallery_id}",
            "revision": 1,
            "content_sha256": content_hash(gallery_id),
            "solve_check": {
                "validator_id": gallery_id,
                "status": "passed",
                "expected_shape": [2],
            },
        }
        for gallery_id in ids
    }
    (root / "freeform_gallery_registry.json").write_text(
        json.dumps({
            "schema_version": 1,
            "required_stages": list(STAGE_FOLDERS),
            "entries": entries,
        }),
        encoding="utf-8",
    )


def _write_slice(
    root: Path,
    stage: str,
    gallery_id: str,
    *,
    frontmatter_id: str | None = None,
) -> Path:
    directory = gallery_dir(root, stage)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{gallery_id}.md"
    path.write_text(
        "\n".join([
            "---",
            f"example_id: {frontmatter_id or gallery_id}",
            f"stage: {stage}",
            "registry_revision: 1",
            f"title: Title {gallery_id}",
            f"summary: Summary for {stage}",
            "---",
            "",
            f"# {stage}",
        ]),
        encoding="utf-8",
    )
    return path


def test_misaligned_and_unregistered_entries_are_quarantined_individually(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    good = "good-entry"
    bad = "bad-entry"
    extra = "unregistered-entry"
    for stage in STAGE_FOLDERS:
        _write_slice(tmp_path, stage, good)
        if stage != "sweep_design":
            _write_slice(tmp_path, stage, bad)
    _write_registry(tmp_path, [good, bad])
    # An unregistered file and a mismatched frontmatter ID are independently
    # quarantined; neither suppresses the good canonical entry.
    _write_slice(tmp_path, "constraints", extra)
    bad_path = gallery_dir(tmp_path, "constraints") / f"{bad}.md"
    bad_path.write_text(
        bad_path.read_text(encoding="utf-8").replace(
            f"example_id: {bad}", "example_id: another-id"),
        encoding="utf-8",
    )

    report = audit_freeform_gallery(root=tmp_path)
    assert report["visible_ids"] == [good]
    assert {bad, extra} <= set(report["hidden"])
    bad_codes = {item["code"] for item in report["hidden"][bad]}
    assert {"id_mismatch", "missing_stage_slice"} <= bad_codes
    assert report["hidden"][extra][0]["code"] == "unregistered_entry"

    monkeypatch.setattr(router, "_ROOT", tmp_path)
    listed = json.loads(router.list_freeform_examples("constraints"))
    assert [item["example_id"] for item in listed] == [good]
    assert router.read_freeform_example(
        bad, stage="constraints").startswith("ERROR: unknown freeform")
    assert router.select_freeform_example(
        bad, "should remain hidden", stage="constraints"
    ).startswith("ERROR: unknown freeform")

    # A post-validation body edit invalidates the registered cross-stage
    # content hash even when all frontmatter still appears aligned.
    good_path = gallery_dir(tmp_path, "constraints") / f"{good}.md"
    good_path.write_text(
        good_path.read_text(encoding="utf-8") + "\nchanged after validation\n",
        encoding="utf-8",
    )
    changed = audit_freeform_gallery(root=tmp_path)
    assert any(item["code"] == "content_hash_mismatch"
               for item in changed["hidden"][good])
