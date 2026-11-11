"""
Sync shared engine packages from ThermoML → SRD46.
===================================================
Run this script after modifying any shared engine package in the ThermoML workspace
to propagate changes to the SRD46 copy.

Usage:
    python _sync_shared_engine.py          # dry-run (shows what would change)
    python _sync_shared_engine.py --apply  # apply changes
"""

from __future__ import annotations

import argparse
import filecmp
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
THERMOML_ENGINE = (
    REPO_ROOT
    / "ThermoML_research_agent"
    / "NIST_ThermoML_agents"
    / "general_db_query_engine"
)
SRD46_ENGINE = Path(__file__).resolve().parent

SHARED_PACKAGES = [
    "general_argo_engine_helpers",
    "general_hooks_management_helpers",
    "general_subagent_delegation_helpers",
    "general_subagent_skill_schema_and_parser",
    "general_text_context_marker_catalog",
    "general_tool_management_helpers",
]


def _diff_trees(src: Path, dst: Path) -> list[tuple[str, str]]:
    """Return list of (relative_path, status) for files that differ."""
    diffs: list[tuple[str, str]] = []
    for root, _dirs, files in os.walk(src):
        rel_root = Path(root).relative_to(src)
        for f in files:
            if f.endswith((".pyc", ".pyo")) or "__pycache__" in str(rel_root):
                continue
            src_file = Path(root) / f
            dst_file = dst / rel_root / f
            rel = str(rel_root / f)
            if not dst_file.exists():
                diffs.append((rel, "NEW"))
            elif not filecmp.cmp(str(src_file), str(dst_file), shallow=False):
                diffs.append((rel, "CHANGED"))
    # Check for files in dst that don't exist in src (deleted upstream)
    for root, _dirs, files in os.walk(dst):
        rel_root = Path(root).relative_to(dst)
        if "__pycache__" in str(rel_root):
            continue
        for f in files:
            if f.endswith((".pyc", ".pyo")):
                continue
            src_file = src / rel_root / f
            if not src_file.exists():
                diffs.append((str(rel_root / f), "DELETED"))
    return diffs


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync shared engine packages.")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default: dry-run)")
    args = parser.parse_args()

    total_changes = 0
    for pkg in SHARED_PACKAGES:
        src = THERMOML_ENGINE / pkg
        dst = SRD46_ENGINE / pkg
        if not src.exists():
            print(f"  WARNING: source missing: {src}")
            continue
        diffs = _diff_trees(src, dst) if dst.exists() else [("(entire package)", "NEW")]
        if not diffs:
            print(f"  {pkg}: up to date")
            continue
        total_changes += len(diffs)
        print(f"  {pkg}: {len(diffs)} change(s)")
        for rel, status in diffs:
            print(f"    [{status}] {rel}")
        if args.apply:
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            print(f"    → synced")

    if total_changes == 0:
        print("\nAll shared packages are up to date.")
    elif not args.apply:
        print(f"\n{total_changes} change(s) found. Run with --apply to sync.")


if __name__ == "__main__":
    main()
