from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from ..models import RunArtifacts


REPO_ROOT = Path(__file__).absolute().parents[4]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "_output" / "Query"
MODEL_DIR_RE = re.compile(r"^Model_(?P<model>.+)$")
# Question ids are either dotted integers (Q1.2.3) for the curated test set or
# alphanumeric tokens (Qfree_20260423_143000) for freeform queries.
ARTIFACT_RE = re.compile(
    r"^(?P<question_id>Q[\w.-]+)_(?P<kind>history|ref_ids|result)_batch(?P<batch>\d+)\.md$"
)
LEGACY_RE = re.compile(
    r"^(?P<question_id>Q[\w.-]+)_(?P<kind>history|ref_ids|result)(?:_batch(?P<batch>\d+))?\.md$"
)
SUMMARY_RE = re.compile(r"^SUMMARY(?:_batch(?P<batch>\d+))?\.md$")


def _resolve_output_roots(output_roots: Iterable[str | Path] | None) -> list[Path]:
    names = list(output_roots or [DEFAULT_OUTPUT_ROOT])
    roots: list[Path] = []
    for name in names:
        path = Path(name)
        if not path.is_absolute():
            path = REPO_ROOT / path
        if path.exists() and path.is_dir():
            roots.append(path)
    return sorted(roots)


def _infer_legacy_model(output_root: Path) -> str:
    if output_root.name == "_output":
        return "default"
    return output_root.name.removeprefix("_output_").removeprefix("_output") or "default"


def scan_outputs(
    output_roots: Iterable[str | Path] | None = None,
    *,
    strict: bool = False,
) -> list[RunArtifacts]:
    grouped: dict[tuple[str, str, str, int], dict[str, Path]] = defaultdict(dict)

    for output_root in _resolve_output_roots(output_roots):
        for child in sorted(output_root.iterdir()):
            if not child.is_dir():
                continue
            model_match = MODEL_DIR_RE.match(child.name)
            if model_match:
                _scan_model_batch_root(output_root, child, grouped)
            elif child.name.startswith("Q"):
                _scan_legacy_qdir(output_root, child, grouped)

        _scan_legacy_flat_root(output_root, grouped)

    artifacts = _materialize_manifest(grouped)
    if strict:
        partials = [artifact for artifact in artifacts if not artifact.is_complete]
        if partials:
            details = ", ".join(
                f"{artifact.model}:{artifact.question_id}:batch{artifact.batch} missing {artifact.missing_artifacts}"
                for artifact in partials[:8]
            )
            raise ValueError(f"Found incomplete runs in strict mode: {details}")
    return artifacts


def _scan_model_batch_root(
    output_root: Path,
    model_dir: Path,
    grouped: dict[tuple[str, str, str, int], dict[str, Path]],
) -> None:
    model = model_dir.name.replace("Model_", "", 1)
    summary_by_batch: dict[int, Path] = {}
    for summary in model_dir.glob("SUMMARY*.md"):
        match = SUMMARY_RE.match(summary.name)
        if match:
            summary_by_batch[int(match.group("batch") or 0)] = summary

    for qdir in sorted(model_dir.glob("Q*")):
        if not qdir.is_dir():
            continue
        for path in sorted(qdir.glob("*.md")):
            match = ARTIFACT_RE.match(path.name)
            if not match:
                continue
            batch = int(match.group("batch"))
            key = (output_root.name, model, match.group("question_id"), batch)
            grouped[key][match.group("kind")] = path
            if batch in summary_by_batch:
                grouped[key]["summary"] = summary_by_batch[batch]


def _scan_legacy_qdir(
    output_root: Path,
    qdir: Path,
    grouped: dict[tuple[str, str, str, int], dict[str, Path]],
) -> None:
    model = _infer_legacy_model(output_root)
    for path in sorted(qdir.glob("*.md")):
        match = LEGACY_RE.match(path.name)
        if not match:
            continue
        batch = int(match.group("batch") or 0)
        key = (output_root.name, model, match.group("question_id"), batch)
        grouped[key][match.group("kind")] = path


def _scan_legacy_flat_root(
    output_root: Path,
    grouped: dict[tuple[str, str, str, int], dict[str, Path]],
) -> None:
    model = _infer_legacy_model(output_root)
    summary_by_batch: dict[int, Path] = {}
    for summary in output_root.glob("SUMMARY*.md"):
        match = SUMMARY_RE.match(summary.name)
        if match:
            summary_by_batch[int(match.group("batch") or 0)] = summary

    for path in sorted(output_root.glob("Q*.md")):
        match = LEGACY_RE.match(path.name)
        if not match:
            continue
        batch = int(match.group("batch") or 0)
        key = (output_root.name, model, match.group("question_id"), batch)
        grouped[key][match.group("kind")] = path
        if batch in summary_by_batch:
            grouped[key]["summary"] = summary_by_batch[batch]


def _materialize_manifest(
    grouped: dict[tuple[str, str, str, int], dict[str, Path]]
) -> list[RunArtifacts]:
    artifacts: list[RunArtifacts] = []
    for (output_root, model, question_id, batch), paths in sorted(
        grouped.items(), key=lambda item: (item[0][0], item[0][1], _qid_sort_key(item[0][2]), item[0][3])
    ):
        artifact = RunArtifacts(
            output_root=output_root,
            model=model,
            question_id=question_id,
            batch=batch,
            history_path=paths.get("history"),
            ref_ids_path=paths.get("ref_ids"),
            result_path=paths.get("result"),
            summary_path=paths.get("summary"),
            is_complete=all(paths.get(name) is not None for name in ("history", "ref_ids", "result")),
        )
        artifacts.append(artifact)
    return artifacts


def summarize_manifest(artifacts: list[RunArtifacts]) -> dict[str, object]:
    by_model: dict[str, dict[str, object]] = {}
    partial_runs: list[dict[str, object]] = []

    for artifact in artifacts:
        model_summary = by_model.setdefault(
            artifact.model,
            {
                "complete_runs": 0,
                "partial_runs": 0,
                "missing_artifact_types": defaultdict(int),
                "batch_coverage": defaultdict(int),
            },
        )
        if artifact.is_complete:
            model_summary["complete_runs"] += 1
        else:
            model_summary["partial_runs"] += 1
            partial_runs.append(
                {
                    "output_root": artifact.output_root,
                    "model": artifact.model,
                    "question_id": artifact.question_id,
                    "batch": artifact.batch,
                    "missing_artifacts": artifact.missing_artifacts,
                }
            )
            for missing in artifact.missing_artifacts:
                model_summary["missing_artifact_types"][missing] += 1
        model_summary["batch_coverage"][artifact.batch] += 1

    normalized_models: dict[str, dict[str, object]] = {}
    for model, summary in by_model.items():
        normalized_models[model] = {
            "complete_runs": summary["complete_runs"],
            "partial_runs": summary["partial_runs"],
            "missing_artifact_types": dict(summary["missing_artifact_types"]),
            "batch_coverage": {str(batch): count for batch, count in sorted(summary["batch_coverage"].items())},
        }

    return {
        "total_runs": len(artifacts),
        "complete_runs": sum(1 for artifact in artifacts if artifact.is_complete),
        "partial_runs": len(partial_runs),
        "models": normalized_models,
        "partials": partial_runs,
    }


def _qid_sort_key(question_id: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", question_id))
