"""LC2_2_card_db_merger_orchestrator.py
LC2_2 stage orchestrator: external-DB card merger (parse + merge only).

Pipeline position
-----------------
LC2_1 emits a single SRD-46 ``free_energy_card.md`` per chemical system.
LC2_2 consumes ONLY that card and merges in entries from databases OTHER
than SRD-46.  It is a **pure parse-and-merge** stage:

  * No LLM is invoked.
  * No deduplication is performed — duplicate / overlapping species across
    SRD-46 and the external DBs are *kept*.  Resolving duplicates is the
    job of LC2_3.

Each external-DB pathway is independently toggleable via the shared
analysis config (``SRD46AnalysisAgentConfig``):

  * ``LC2_2_POURBAIX_ENABLED``   — Pourbaix atlas merge   (default: ON)
  * ``LC2_2_CRC_REDOX_ENABLED``  — CRC redox embedding     (default: OFF)
  * ``LC2_2_MERGE_WATER_SPECIES_REDOX`` — merge atlas redox data for the
                                  aqueous self-system elements H/O
                                  (H⁺/OH⁻)                  (default: OFF)

Debug smoke drivers force BOTH pathways on.

All artefacts for a system land in a single *test folder* named after the
input card's parent directory (e.g. ``prompt_03``):

    <output_dir>/<test_name>/
        free_energy_card.md          <- merged card (SRD-46 + external DBs)
        lc2_2_manifest.json          <- run manifest
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Union

# ── path bootstrapping ──────────────────────────────────────────
_THIS = Path(__file__).absolute()
_LC2_2_ROOT = _THIS.parents[0]              # LC2_2_card_db_merger/
_LC2_ROOT = _THIS.parents[1]                # LC2_free_energy_card_building/
_PIPELINE_ROOT = _THIS.parents[2]           # NIST_SRD46_calc_input_building_agentic_pipeline/
_ANALYSIS_ROOT = _THIS.parents[3]           # NIST_SRD46_analysis_agent/
_DB_AGENT_ROOT = _THIS.parents[4]           # NIST_SRD46_db_agent/
_SRD46_ROOT = _THIS.parents[5]              # SRD46_research_agent/
_NUMCALC_ROOT = _ANALYSIS_ROOT / "NIST_SRD46_core_numcalc_pipeline"

for _p in (_PIPELINE_ROOT, _LC2_ROOT, _NUMCALC_ROOT, _ANALYSIS_ROOT, _SRD46_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# Import the shared analysis config directly as a top-level module. The
# wrapper ``SRD46_calc_input_building_config`` would otherwise fall back to
# an absolute import that triggers the heavy ``NIST_SRD46_analysis_agent``
# package ``__init__`` chain; importing the bare module avoids that.
try:
    from SRD46_analysis_argo_config import AGENT_CONFIG as cfg  # noqa: E402
except Exception:  # pragma: no cover - fallback for packaged imports
    from SRD46_calc_input_building_config import AGENT_CONFIG as cfg  # noqa: E402

from LC2_free_energy_card_building.LC2_2_card_db_merger.db_pourbaix_atlas.pourbaix_merge import (  # noqa: E402
    merge_card_hardcoded,
)
from LC2_free_energy_card_building.LC2_2_card_db_merger.db_crc_redox.crc_redox_merge import (  # noqa: E402
    embed_redox_in_card,
)
from LC2_free_energy_card_building.LC2_2_card_db_merger._md_card_merge_core.merge_helpers import (  # noqa: E402,E501
    _parse_card_valence_table,
)
from LC2_free_energy_card_building.LC2_2_card_db_merger.element_inventory import (  # noqa: E402,E501
    build_element_inventory,
    inventory_to_json,
    render_element_inventory,
)


# ═══════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════

def _derive_test_name(
    explicit: Optional[str], lc2_1_card_path: Path,
) -> str:
    """Resolve the test-folder name for this run.

    ``.../LC2_1_output/prompt_03/free_energy_card.md`` -> ``prompt_03``.
    """
    if explicit:
        return explicit
    parent = lc2_1_card_path.parent.name
    return parent or lc2_1_card_path.stem


def _system_name_from_card(card_text: str, fallback: str) -> str:
    """Best-effort system label from the card title line."""
    for line in card_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            title = stripped.lstrip("#").strip()
            # Drop a leading "Free Energy Card:" style prefix if present.
            if ":" in title:
                title = title.split(":", 1)[1].strip()
            if title:
                return title
        if stripped:
            break
    return fallback


# ═══════════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════════

def run_lc2_2(
    lc2_1_card_path: Union[str, Path],
    output_dir: Union[str, Path],
    *,
    test_name: Optional[str] = None,
    enable_pourbaix: Optional[bool] = None,
    enable_crc: Optional[bool] = None,
    elements: Optional[List[str]] = None,
    merge_water_species_redox: Optional[bool] = None,
) -> dict:
    """Run the LC2_2 external-DB merge stage for one chemical system.

    Parameters
    ----------
    lc2_1_card_path : path
        The LC2_1 ``free_energy_card.md`` (the ONLY input).
    output_dir : path
        Base directory.  Artefacts land in ``output_dir/<test_name>/``.
    test_name : str | None
        Override the test-folder name.  Defaults to the card's parent dir.
    enable_pourbaix : bool | None
        Enable the Pourbaix-atlas merge.  ``None`` -> config default
        (``LC2_2_POURBAIX_ENABLED``).
    enable_crc : bool | None
        Enable CRC redox embedding.  ``None`` -> config default
        (``LC2_2_CRC_REDOX_ENABLED``).
    elements : list[str] | None
        Override the element set queried from the atlas.  ``None`` ->
        auto-detect from the card metals.
    merge_water_species_redox : bool | None
        Merge atlas redox data for the aqueous self-system elements
        (H, O / H⁺, OH⁻). ``None`` -> config default
        (``LC2_2_MERGE_WATER_SPECIES_REDOX``, normally False). When
        False these pure-reference species are excluded from the
        external-DB redox merge.

    Returns
    -------
    dict
        Run manifest (also written to ``lc2_2_manifest.json``).
    """
    lc2_1_card_path = Path(lc2_1_card_path)
    if not lc2_1_card_path.exists():
        raise FileNotFoundError(f"LC2_1 card not found: {lc2_1_card_path}")
    if output_dir is None:
        raise ValueError("run_lc2_2 needs an output_dir")

    if enable_pourbaix is None:
        enable_pourbaix = bool(getattr(cfg, "LC2_2_POURBAIX_ENABLED", True))
    if enable_crc is None:
        enable_crc = bool(getattr(cfg, "LC2_2_CRC_REDOX_ENABLED", False))
    if merge_water_species_redox is None:
        merge_water_species_redox = bool(
            getattr(cfg, "LC2_2_MERGE_WATER_SPECIES_REDOX", False)
        )

    test_name = _derive_test_name(test_name, lc2_1_card_path)
    out_root = Path(output_dir) / test_name
    out_root.mkdir(parents=True, exist_ok=True)

    card_text = lc2_1_card_path.read_text(encoding="utf-8")
    system_name = _system_name_from_card(card_text, test_name)

    merged_md = card_text
    pathways: List[str] = []
    pourbaix_stats: Optional[dict] = None

    # ── Pathway 1: Pourbaix atlas merge (LLM-free, no dedup) ─────
    if enable_pourbaix:
        merged_md, pourbaix_stats = merge_card_hardcoded(
            merged_md, system_name, elements=elements,
            merge_water_species_redox=merge_water_species_redox,
        )
        pathways.append("pourbaix")

    merged_path = out_root / "free_energy_card.md"
    merged_path.write_text(merged_md, encoding="utf-8")

    # ── Merge/alignment report (intermediate artefact) ──────────
    # The Pourbaix merge produces ``dedup_md``: a read-only view of the
    # cross-source core-stoichiometry groups + per-species misalignment.
    # Written alongside the card so downstream stages / humans can audit
    # the merge before any deduplication happens.
    dedup_report_path: Optional[Path] = None
    if pourbaix_stats and pourbaix_stats.get("dedup_md"):
        dedup_report_path = out_root / "deduplication_check.md"
        dedup_report_path.write_text(pourbaix_stats["dedup_md"], encoding="utf-8")

    # The element inventory is a deterministic LC2_2 artefact.  It keeps
    # entries from distinct core groups co-visible by chemical element so
    # LC2_3 can reason across Fe(OH)2 / Fe3O4 / Fe2O3 rather than treating
    # each stoichiometric group in isolation.
    element_inventory_path: Optional[Path] = None
    element_inventory_md_path: Optional[Path] = None
    grouped = (pourbaix_stats or {}).get("_grouped")
    if grouped:
        inventory = build_element_inventory(
            grouped,
            _parse_card_valence_table(merged_md),
            merged_md,
        )
        element_inventory_path = out_root / "element_inventory.json"
        element_inventory_md_path = out_root / "element_inventory.md"
        element_inventory_path.write_text(
            inventory_to_json(inventory), encoding="utf-8",
        )
        element_inventory_md_path.write_text(
            render_element_inventory(inventory), encoding="utf-8",
        )

    # ── Pathway 2: CRC redox embedding (in-place on the card) ────
    crc_stats: Optional[dict] = None
    if enable_crc:
        crc_stats = embed_redox_in_card(merged_path, write_back=True)
        pathways.append("crc_redox")
        # Re-read so the round-trip / manifest reflects CRC edits.
        merged_md = merged_path.read_text(encoding="utf-8")

    # ── Manifest ────────────────────────────────────────────────
    manifest = {
        "schema_version": 1,
        "artifact_kind": "LC2_2 deterministic database merge",
        "stage": "LC2_2",
        "test_name": test_name,
        "system_name": system_name,
        "lc2_1_card_path": str(lc2_1_card_path),
        "output_dir": str(out_root),
        "merged_card_path": str(merged_path),
        "dedup_report_path": str(dedup_report_path) if dedup_report_path else None,
        "element_inventory_path": (
            str(element_inventory_path) if element_inventory_path else None
        ),
        "element_inventory_md_path": (
            str(element_inventory_md_path) if element_inventory_md_path else None
        ),
        "enable_pourbaix": enable_pourbaix,
        "enable_crc": enable_crc,
        "pathways_applied": pathways,
        "pourbaix_stats": _manifest_safe(pourbaix_stats),
        "crc_stats": _manifest_safe(crc_stats),
        "agent_context": {
            "expected_calls": 0,
            "documented_calls": 0,
            "complete": True,
            "reason": "LC2_2 is deterministic and invokes no LLM agent.",
        },
    }
    (out_root / "lc2_2_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return manifest


def _manifest_safe(stats: Optional[dict]) -> Optional[dict]:
    """Strip non-JSON-serialisable / bulky entries from a stats dict."""
    if not stats:
        return stats
    drop = {"_grouped", "dedup_md", "dedup_subagent_audit"}
    out: Dict[str, object] = {}
    for k, v in stats.items():
        if k in drop:
            continue
        try:
            json.dumps(v)
        except (TypeError, ValueError):
            out[k] = str(v)
        else:
            out[k] = v
    return out


# ═══════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════

def _main(argv: List[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="LC2_2 external-DB card merger (parse + merge, no LLM)",
    )
    parser.add_argument(
        "--card", dest="card", required=True,
        help="Path to the LC2_1 free_energy_card.md",
    )
    parser.add_argument(
        "--output-dir", dest="output_dir", required=True,
        help="Base output directory (artefacts land in <output_dir>/<test_name>/)",
    )
    parser.add_argument("--test-name", dest="test_name", default=None)
    grp_pb = parser.add_mutually_exclusive_group()
    grp_pb.add_argument("--pourbaix", dest="enable_pourbaix",
                        action="store_true", default=None)
    grp_pb.add_argument("--no-pourbaix", dest="enable_pourbaix",
                        action="store_false")
    grp_crc = parser.add_mutually_exclusive_group()
    grp_crc.add_argument("--crc", dest="enable_crc",
                         action="store_true", default=None)
    grp_crc.add_argument("--no-crc", dest="enable_crc",
                         action="store_false")
    args = parser.parse_args(argv)

    manifest = run_lc2_2(
        lc2_1_card_path=args.card,
        output_dir=args.output_dir,
        test_name=args.test_name,
        enable_pourbaix=args.enable_pourbaix,
        enable_crc=args.enable_crc,
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
