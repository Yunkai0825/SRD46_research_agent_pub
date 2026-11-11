"""Canonical registry and quarantine audit for freeform gallery entries.

An entry is agent-visible only when its canonical ID is registered and all
three stage-local Markdown slices agree on that ID, title, stage, and registry
revision.  The registry must also carry a passing deterministic solve status.
Debug audits can re-run the local no-network solver checks.  A bad entry is
quarantined across every stage without suppressing unrelated valid entries.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple


STAGE_FOLDERS: Mapping[str, Tuple[str, str]] = {
    "initial_conditions": (
        "LC3_2_initial_condition_designer", "_standard_initcond_templates"),
    "constraints": (
        "LC3_3_constraint_designer", "_standard_constr_templates"),
    "sweep_design": (
        "LC3_4_sweep_designer", "_standard_sweep_templates"),
}
REGISTRY_FILENAME = "freeform_gallery_registry.json"
CANONICAL_ID_RE = re.compile(r"\A[a-z0-9]+(?:-[a-z0-9]+)*\Z")


def _root(root: Optional[Path] = None) -> Path:
    return Path(root) if root is not None else Path(__file__).absolute().parent


def _readable_path(path: Path) -> Path:
    """Return a Windows extended path when an ordinary path is too long."""
    if str(path).startswith("\\\\?\\"):
        return path
    raw = str(path.absolute())
    if os.name != "nt" or raw.startswith("\\\\?\\") or len(raw) < 248:
        return Path(raw)
    if raw.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + raw.lstrip("\\"))
    return Path("\\\\?\\" + raw)


def read_text(path: Path) -> str:
    """Read UTF-8 text through the long-path-safe representation."""
    return _readable_path(path).read_text(encoding="utf-8")


def _frontmatter(path: Path) -> Dict[str, str]:
    text = read_text(path)
    match = re.match(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", text, re.DOTALL)
    if not match:
        raise ValueError("missing YAML frontmatter")
    values: Dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line or line[:1].isspace():
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip("'\"")
    required = (
        "example_id", "stage", "registry_revision", "title", "summary")
    missing = [key for key in required if not values.get(key)]
    if missing:
        raise ValueError("missing frontmatter field(s): " + ", ".join(missing))
    return values


def gallery_dir(root: Path, stage: str) -> Path:
    if stage not in STAGE_FOLDERS:
        raise ValueError(f"unknown freeform gallery stage {stage!r}")
    agent_folder, template_folder = STAGE_FOLDERS[stage]
    return root / agent_folder / template_folder / "freeform" / "gallery"


def _issue(
    code: str,
    message: str,
    *,
    stage: Optional[str] = None,
    path: Optional[Path] = None,
) -> Dict[str, str]:
    result = {"code": code, "message": message}
    if stage is not None:
        result["stage"] = stage
    if path is not None:
        result["path"] = str(path)
    return result


def _scan_stage(
    root: Path,
    stage: str,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, list[Dict[str, str]]]]:
    """Scan one stage without allowing a bad file to abort the whole scan."""
    directory = gallery_dir(root, stage)
    readable_directory = _readable_path(directory)
    indexed: Dict[str, Dict[str, Any]] = {}
    problems: Dict[str, list[Dict[str, str]]] = {}
    if not readable_directory.is_dir():
        problems.setdefault("__gallery__", []).append(_issue(
            "missing_gallery", f"gallery directory is missing: {directory}",
            stage=stage, path=directory))
        return indexed, problems

    for path in sorted(readable_directory.glob("*.md"),
                       key=lambda item: item.name):
        canonical_id = path.stem
        bucket = problems.setdefault(canonical_id, [])
        readable = _readable_path(path)
        if path.parent != readable_directory or readable.is_symlink():
            bucket.append(_issue(
                "unsafe_path", "gallery entries must be direct non-symlink files",
                stage=stage, path=path))
            continue
        if not readable.is_file():
            bucket.append(_issue(
                "unreadable_file", "gallery entry is not a readable file",
                stage=stage, path=path))
            continue
        if not CANONICAL_ID_RE.fullmatch(canonical_id):
            bucket.append(_issue(
                "invalid_filename_id",
                "gallery filename stem is not a canonical lowercase kebab ID",
                stage=stage, path=path))
            continue
        try:
            values = _frontmatter(path)
        except Exception as exc:
            bucket.append(_issue(
                "invalid_frontmatter", f"{type(exc).__name__}: {exc}",
                stage=stage, path=path))
            continue
        if values["example_id"] != canonical_id:
            bucket.append(_issue(
                "id_mismatch",
                f"filename ID {canonical_id!r} != frontmatter example_id "
                f"{values['example_id']!r}",
                stage=stage, path=path))
            continue
        indexed[canonical_id] = {
            "metadata": {
                "example_id": canonical_id,
                "title": values["title"],
                "summary": values["summary"],
            },
            "frontmatter": values,
            "path": readable,
        }
        if not bucket:
            problems.pop(canonical_id, None)
    return indexed, problems


def _load_registry(root: Path) -> Tuple[Dict[str, Any], Path]:
    path = root / REGISTRY_FILENAME
    raw = json.loads(read_text(path))
    if not isinstance(raw, dict):
        raise ValueError("registry root must be a JSON object")
    if raw.get("schema_version") != 1:
        raise ValueError("registry schema_version must be 1")
    if raw.get("required_stages") != list(STAGE_FOLDERS):
        raise ValueError(
            "registry required_stages must exactly match the LC3 stage order")
    if not isinstance(raw.get("entries"), dict):
        raise ValueError("registry entries must be an object keyed by gallery ID")
    return raw, path


def _fingerprint(root: Path, registry_path: Path) -> str:
    digest = hashlib.sha256()
    candidates = [(REGISTRY_FILENAME, _readable_path(registry_path))]
    for stage in STAGE_FOLDERS:
        directory = gallery_dir(root, stage)
        readable_directory = _readable_path(directory)
        if readable_directory.is_dir():
            candidates.extend(
                (f"{stage}/{path.name}", path)
                for path in sorted(readable_directory.glob("*.md"))
            )
    for label, readable in candidates:
        digest.update(label.encode())
        if readable.is_file():
            digest.update(readable.read_bytes())
    return digest.hexdigest()


def _entry_content_sha256(
    scans: Mapping[str, Mapping[str, Mapping[str, Any]]],
    gallery_id: str,
) -> Optional[str]:
    """Hash the exact three stage slices in canonical stage order."""
    if any(gallery_id not in scans[stage] for stage in STAGE_FOLDERS):
        return None
    digest = hashlib.sha256()
    for stage in STAGE_FOLDERS:
        digest.update(stage.encode("utf-8"))
        digest.update(b"\0")
        path = Path(scans[stage][gallery_id]["path"])
        digest.update(_readable_path(path).read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def audit_freeform_gallery(
    *,
    root: Optional[Path] = None,
    run_solve_checks: bool = False,
) -> Dict[str, Any]:
    """Return visible IDs and structured quarantine reasons.

    ``run_solve_checks`` invokes the real local numerical API for tiny
    canonical cases. It is intended for debug/CI; ordinary agent discovery
    relies on the registered passing status plus structural alignment.
    """
    base = _root(root)
    scans: Dict[str, Dict[str, Dict[str, Any]]] = {}
    scan_problems: Dict[str, list[Dict[str, str]]] = {}
    for stage in STAGE_FOLDERS:
        indexed, problems = _scan_stage(base, stage)
        scans[stage] = indexed
        for gallery_id, issues in problems.items():
            scan_problems.setdefault(gallery_id, []).extend(issues)

    try:
        registry, registry_path = _load_registry(base)
        entries = registry["entries"]
        registry_error = None
    except Exception as exc:
        registry_path = base / REGISTRY_FILENAME
        entries = {}
        registry_error = _issue(
            "invalid_registry", f"{type(exc).__name__}: {exc}",
            path=registry_path)

    file_ids = set().union(*(set(index) for index in scans.values()))
    registered_ids = set(entries)
    candidate_ids = sorted(file_ids | registered_ids | set(scan_problems))
    hidden: Dict[str, list[Dict[str, str]]] = {}
    visible = []
    solve_results: Dict[str, Dict[str, Any]] = {}

    if registry_error is not None:
        hidden["__registry__"] = [registry_error]

    for gallery_id in candidate_ids:
        issues = list(scan_problems.get(gallery_id, []))
        entry = entries.get(gallery_id)
        if entry is None:
            issues.append(_issue(
                "unregistered_entry",
                "gallery file is not keyed by this canonical ID in the registry"))
        elif not isinstance(entry, Mapping):
            issues.append(_issue(
                "invalid_registry_entry", "registry entry must be an object"))
        else:
            if not CANONICAL_ID_RE.fullmatch(gallery_id):
                issues.append(_issue(
                    "invalid_registry_id",
                    "registry key is not a canonical lowercase kebab ID"))
            title = str(entry.get("title") or "")
            revision = entry.get("revision")
            expected_content_hash = str(entry.get("content_sha256") or "")
            if not title:
                issues.append(_issue(
                    "missing_registry_title", "registry title is empty"))
            if not isinstance(revision, int) or revision < 1:
                issues.append(_issue(
                    "invalid_registry_revision",
                    "registry revision must be a positive integer"))
            if not re.fullmatch(r"[0-9a-f]{64}", expected_content_hash):
                issues.append(_issue(
                    "invalid_content_hash",
                    "registry content_sha256 must be a lowercase SHA-256"))

            solve_check = entry.get("solve_check")
            if not isinstance(solve_check, Mapping):
                issues.append(_issue(
                    "missing_solve_check", "registry solve_check is missing"))
            else:
                validator_id = str(solve_check.get("validator_id") or "")
                if validator_id != gallery_id:
                    issues.append(_issue(
                        "validator_id_mismatch",
                        "solve_check.validator_id must equal the canonical ID"))
                if solve_check.get("status") != "passed":
                    reason = str(solve_check.get("reason") or
                                 "registered solve status is not passed")
                    issues.append(_issue("solve_status_not_passed", reason))

            for stage in STAGE_FOLDERS:
                item = scans[stage].get(gallery_id)
                if item is None:
                    issues.append(_issue(
                        "missing_stage_slice",
                        f"canonical entry has no {stage} Markdown slice",
                        stage=stage,
                        path=gallery_dir(base, stage) / f"{gallery_id}.md"))
                    continue
                values = item["frontmatter"]
                if values["stage"] != stage:
                    issues.append(_issue(
                        "stage_mismatch",
                        f"frontmatter stage is {values['stage']!r}",
                        stage=stage, path=item["path"]))
                if values["title"] != title:
                    issues.append(_issue(
                        "title_mismatch",
                        "frontmatter title does not match the registry title",
                        stage=stage, path=item["path"]))
                if str(values["registry_revision"]) != str(revision):
                    issues.append(_issue(
                        "revision_mismatch",
                        "frontmatter registry_revision does not match registry",
                        stage=stage, path=item["path"]))

            actual_content_hash = _entry_content_sha256(scans, gallery_id)
            if (actual_content_hash is not None
                    and expected_content_hash != actual_content_hash):
                issues.append(_issue(
                    "content_hash_mismatch",
                    "one or more stage slices changed after solve validation; "
                    "revalidate and update the registry revision/hash"))

            if run_solve_checks:
                from .freeform_gallery_validation import (
                    run_freeform_gallery_solve_check,
                )
                solve_result = run_freeform_gallery_solve_check(gallery_id)
                solve_results[gallery_id] = solve_result
                if solve_result.get("status") != "passed":
                    issues.append(_issue(
                        "solve_check_failed",
                        "; ".join(solve_result.get("issues") or
                                  ["canonical solve check failed"])))
                elif isinstance(solve_check, Mapping):
                    expected = list(solve_check.get("expected_shape") or [])
                    if expected != list(solve_result.get("actual_shape") or []):
                        issues.append(_issue(
                            "solve_shape_mismatch",
                            f"registered shape {expected} != solve shape "
                            f"{solve_result.get('actual_shape')}"))

        if issues:
            hidden[gallery_id] = issues
        elif registry_error is None:
            visible.append(gallery_id)

    if registry_error is not None:
        visible = []

    return {
        "schema_version": 1,
        "registry_path": str(registry_path),
        "fingerprint": _fingerprint(base, registry_path),
        "run_solve_checks": bool(run_solve_checks),
        "registered_ids": sorted(registered_ids),
        "visible_ids": visible,
        "hidden": hidden,
        "solve_checks": solve_results,
        "all_entries_visible": not hidden,
    }


def visible_freeform_gallery_index(
    stage: str,
    *,
    root: Optional[Path] = None,
    run_solve_checks: bool = False,
) -> Tuple[Dict[str, Tuple[Dict[str, str], Path]], Dict[str, Any]]:
    """Return only common registry-visible entries for one LC3 stage."""
    base = _root(root)
    if stage not in STAGE_FOLDERS:
        raise ValueError(f"unknown freeform gallery stage {stage!r}")
    report = audit_freeform_gallery(
        root=base, run_solve_checks=run_solve_checks)
    scanned, _ = _scan_stage(base, stage)
    index = {
        gallery_id: (dict(scanned[gallery_id]["metadata"]),
                     Path(scanned[gallery_id]["path"]))
        for gallery_id in report["visible_ids"]
        if gallery_id in scanned
    }
    return index, report


def _main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit canonical freeform galleries and quarantine issues")
    parser.add_argument(
        "--solve", action="store_true",
        help="run all local no-network numerical solve checks")
    args = parser.parse_args(argv)
    report = audit_freeform_gallery(run_solve_checks=args.solve)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["all_entries_visible"] else 1


if __name__ == "__main__":  # pragma: no cover - maintenance CLI
    raise SystemExit(_main())
