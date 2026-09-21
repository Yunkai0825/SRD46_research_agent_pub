"""
Deterministic Python wrappers around the SRD-46 calc tools.
==========================================================

Every wrapper takes ``purpose: str`` and ``tasks: str`` as the
first two required arguments (so audit logs see the agent's intent),
plus the actual call-specific kwargs. Each returns a small typed dict
suitable for direct re-injection into a system prompt.

These wrappers are the only Python surface the L1 phase workers ever
call. They are deliberately thin — the heavy logic lives in the
upstream calc-tools modules; this layer enforces the catalog contract
(``purpose``/``tasks``) and returns a uniform-shape dict for the
hardcoded LD validator + the L2 monitors to consume.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

log = logging.getLogger("analysis.calc_wrappers")

# ── path bootstrap so we can import the calc tool modules cleanly ─────
# NOTE: do NOT call ``.resolve()`` here -- on Windows mapped drives that
# point at a UNC share, ``resolve()`` rewrites the path into the UNC
# form (\\server\share\...).  Python's package finder gets confused
# when the same package is reachable via two distinct sys.path roots
# (the mapped-drive one used by the rest of the test harness and the
# UNC one we'd insert here), and sub-package imports start failing
# with ``ModuleNotFoundError`` even though the file exists.
_HERE = Path(__file__).absolute()
_INPUT_ROOT = _HERE.parents[1] / "NIST_SRD46_calc_input_building_agentic_pipeline"
_NUMCALC_ROOT = _HERE.parents[1] / "NIST_SRD46_core_numcalc_pipeline"
for _root in (_INPUT_ROOT, _NUMCALC_ROOT):
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

# Runtime cards use the shared freeform output tree, not legacy source caches.
CARD_STORAGE_DIR: Path = _HERE.parents[3] / "_output" / "Analysis" / "_ref_eq_cards_storage"


# ════════════════════════════════════════════════════════════════════
#  Contract enforcement
# ════════════════════════════════════════════════════════════════════

class CatalogContractError(ValueError):
    """Raised when ``purpose``/``tasks`` are missing or empty."""


def _require_purpose_tasks(purpose: Any, tasks: Any) -> tuple[str, str]:
    if not isinstance(purpose, str) or not purpose.strip():
        raise CatalogContractError(
            "Missing or empty 'purpose'. Every analysis-agent tool/dispatcher "
            "must declare a non-empty purpose string."
        )
    if not isinstance(tasks, str) or not tasks.strip():
        raise CatalogContractError(
            "Missing or empty 'tasks'. Every analysis-agent tool/dispatcher "
            "must declare a non-empty free-text tasks string."
        )
    return purpose.strip(), tasks.strip()


# ════════════════════════════════════════════════════════════════════
#  S2 — card builder / merger / enricher
# ════════════════════════════════════════════════════════════════════

def find_existing_cards(
    *,
    purpose: str,
    tasks: str,
    metal_ids: Sequence[Union[int, str]],
    ligand_ids: Sequence[Union[int, str]],
    storage_dir: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Glob ``_ref_eq_cards_storage/`` for cards matching the given pairs.

    Returns ``{"hits": [{metal_id, ligand_id, md_path, json_path}, ...],
              "missing_pairs": [(m,l), ...]}``.
    """
    _require_purpose_tasks(purpose, tasks)
    storage = Path(storage_dir) if storage_dir else CARD_STORAGE_DIR
    storage.mkdir(parents=True, exist_ok=True)
    metal_ids = [str(m).replace("metal_", "") for m in metal_ids]
    ligand_ids = [str(l).replace("ligand_", "") for l in ligand_ids]

    hits: List[Dict[str, Any]] = []
    missing: List[tuple[str, str]] = []
    for m in metal_ids:
        for l in ligand_ids:
            pat = f"refeqcard_metal_{m}_ligand_{l}_*.md"
            md_matches = sorted(storage.glob(pat))
            if md_matches:
                md = md_matches[0]
                hits.append({
                    "metal_id": m,
                    "ligand_id": l,
                    "md_path": str(md),
                    "json_path": str(md.with_suffix(".json")),
                })
            else:
                missing.append((m, l))
    return {"hits": hits, "missing_pairs": missing,
            "storage_dir": str(storage)}


def wrap_build_pair_eq_map(
    *,
    purpose: str,
    tasks: str,
    pair_entry: Dict[str, Any],
    storage_dir: Optional[Union[str, Path]] = None,
    eq_map_dir: Optional[Union[str, Path]] = None,
    auto_hydroxide: bool = True,
    auto_pka: bool = True,
) -> Dict[str, Any]:
    """Build the **draft eq-map** for one (metal, ligand) pair.

    First half of the card-build pipeline: resolves IDs, augments with
    hydroxide + pKa networks, persists ``ids.json`` / ``maps.json`` /
    ``augmented_networks.json`` (versioned ``_v0``).  Stops *before*
    the equation builder runs, so the L2_1_1 validator + L3 fixer can
    inspect / patch the selected_map JSON before card rendering.

    Returns the full ``eq_map_meta`` dict (see
    ``build_or_load_ref_pair_eq_map`` docstring).
    """
    _require_purpose_tasks(purpose, tasks)
    from ..NIST_SRD46_calc_input_building_agentic_pipeline.LC2_free_energy_card_building.LC2_1_card_initializer.ref_eq_SRD46_json_cards_builder.ref_eq_SRD46_json_cards_builder import (
        build_or_load_ref_pair_eq_map,
    )
    storage = Path(storage_dir) if storage_dir else CARD_STORAGE_DIR
    return build_or_load_ref_pair_eq_map(
        pair_entry,
        storage_dir=storage,
        eq_map_dir=eq_map_dir,
        auto_hydroxide=auto_hydroxide,
        auto_pka=auto_pka,
    )


def wrap_render_pair_card(
    *,
    purpose: str,
    tasks: str,
    eq_map_meta: Dict[str, Any],
    storage_dir: Optional[Union[str, Path]] = None,
    atlas_merge: bool = False,
) -> Dict[str, Any]:
    """Render a per-pair MD card from a (possibly patched) eq-map.

    Second half of the card-build pipeline.  Returns ``{"card_path",
    "n_components", "n_species"}`` mirroring
    :func:`wrap_build_or_load_ref_card`.
    """
    _require_purpose_tasks(purpose, tasks)
    from ..NIST_SRD46_calc_input_building_agentic_pipeline.LC2_free_energy_card_building.LC2_1_card_initializer.ref_eq_SRD46_json_cards_builder.ref_eq_SRD46_json_cards_builder import (
        render_ref_pair_card_from_eq_map,
    )
    storage = Path(storage_dir) if storage_dir else CARD_STORAGE_DIR
    _md_text, card_json, card_path = render_ref_pair_card_from_eq_map(
        eq_map_meta,
        storage_dir=storage,
        atlas_merge=atlas_merge,
    )
    n_components = 0
    n_species = 0
    if isinstance(card_json, dict):
        n_components = _safe_len(card_json, "components")
        n_species = _safe_len(card_json, "species")
    return {
        "card_path": str(card_path),
        "n_components": n_components,
        "n_species": n_species,
    }


def wrap_build_or_load_ref_card(
    *,
    purpose: str,
    tasks: str,
    pair_entry: Dict[str, Any],
    storage_dir: Optional[Union[str, Path]] = None,
    auto_hydroxide: bool = True,
    auto_pka: bool = True,
    atlas_merge: bool = False,
) -> Dict[str, Any]:
    """Build or load a reference card using the LC2 card initializer.

    Returns ``{"card_path": str, "n_components": int, "n_species": int}``.
    """
    _require_purpose_tasks(purpose, tasks)
    from ..NIST_SRD46_calc_input_building_agentic_pipeline.LC2_free_energy_card_building.LC2_1_card_initializer.ref_eq_SRD46_json_cards_builder.ref_eq_SRD46_json_cards_builder import (
        build_or_load_ref_card,
    )
    storage = Path(storage_dir) if storage_dir else CARD_STORAGE_DIR
    _md_text, report_dict, card_path = build_or_load_ref_card(
        pair_entry,
        storage_dir=storage,
        auto_hydroxide=auto_hydroxide,
        auto_pka=auto_pka,
        atlas_merge=atlas_merge,
    )
    return {
        "card_path": str(card_path),
        "n_components": _safe_len(report_dict, "components"),
        "n_species": _safe_len(report_dict, "species"),
    }


def wrap_merge_ref_cards(
    *,
    purpose: str,
    tasks: str,
    ref_card_paths: Sequence[Union[str, Path]],
    system_name: str,
    out_dir: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Merge reference cards with the LC2 initializer; persist merged MD.

    Return the merged path, counts, and source collision audit.
    """
    _require_purpose_tasks(purpose, tasks)
    from ..NIST_SRD46_calc_input_building_agentic_pipeline.LC2_free_energy_card_building.LC2_1_card_initializer.ref_eq_SRD46_md_cards_merger.ref_eq_SRD46_cards_merger import (
        merge_ref_cards,
    )
    merged_md, merged_report, collisions = merge_ref_cards(
        list(ref_card_paths), system_name=system_name,
    )
    out_dir = Path(out_dir) if out_dir else (CARD_STORAGE_DIR / "_merged")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"merged_{system_name or 'system'}.md"
    out_path.write_text(merged_md, encoding="utf-8")
    return {
        "merged_card_path": str(out_path),
        "n_species":   _safe_attr_len(merged_report, "species"),
        "n_reactions": _safe_attr_len(merged_report, "reactions"),
        "srd_srd_collisions": collisions,
    }


def wrap_enrich_card(
    *,
    purpose: str,
    tasks: str,
    card_path: Union[str, Path],
    system_name: str,
    elements: Optional[List[str]] = None,
    dedup_instruction: Optional[Dict[str, Any]] = None,
    out_dir: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Enrich a card using the current deterministic LC2 Pourbaix merge.

    LC2_2 retains all merged species and reports potential duplicates.
    ``dedup_instruction`` is accepted and logged for compatibility, but
    filtering belongs to LC2_3 and is not applied by this wrapper.
    """
    _require_purpose_tasks(purpose, tasks)
    if dedup_instruction is not None and not isinstance(dedup_instruction, dict):
        raise CatalogContractError("'dedup_instruction' must be a dict or None.")
    log.info("enrich_card dedup_instruction=%s", dedup_instruction)

    from ..NIST_SRD46_calc_input_building_agentic_pipeline.LC2_free_energy_card_building.LC2_2_card_db_merger.db_pourbaix_atlas.pourbaix_merge import (
        merge_card_hardcoded,
    )
    card_path = Path(card_path)
    enriched_md, stats = merge_card_hardcoded(
        card_path.read_text(encoding="utf-8"),
        system_name=system_name,
        elements=elements,
        dedup_instruction=dedup_instruction,
    )
    stats = dict(stats)
    dedup_md = stats.pop("dedup_md", "")
    # Internal grouped dataclasses support LC2_3; tool results are JSON data.
    stats.pop("_grouped", None)
    out_dir = Path(out_dir) if out_dir else card_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    enriched_path = out_dir / (card_path.stem + "_enriched.md")
    enriched_path.write_text(enriched_md, encoding="utf-8")
    dedup_path = out_dir / (card_path.stem + "_dedup.md")
    dedup_path.write_text(dedup_md or "", encoding="utf-8")
    return {
        "enriched_card_path": str(enriched_path),
        "dedup_md_path":      str(dedup_path),
        "stats":              stats,
        "dedup_instruction_applied": {},
        "dedup_instruction_requested": dedup_instruction or {},
    }



# ════════════════════════════════════════════════════════════════════
#  S3 / S5 — read-only card parsing
# ════════════════════════════════════════════════════════════════════

def wrap_parse_card(
    *,
    purpose: str,
    tasks: str,
    card_path: Union[str, Path],
) -> Dict[str, Any]:
    """Parse a free-energy MD card and return summary counts + name lists."""
    _require_purpose_tasks(purpose, tasks)
    from ..NIST_SRD46_calc_input_building_agentic_pipeline.card_management_helpers.free_energy_md_card_reader import (
        parse_free_energy_card_md,
    )
    report = parse_free_energy_card_md(Path(card_path))
    metals  = list(getattr(report, "metal_names", []) or [])
    ligands = list(getattr(report, "ligand_names", []) or [])
    species = list(getattr(report, "species", []) or [])
    rxn     = list(getattr(report, "reactions", []) or [])
    species_names = [getattr(s, "name", str(s)) for s in species]
    return {
        "card_path": str(card_path),
        "metals": metals,
        "ligands": ligands,
        "n_species":   len(species),
        "n_reactions": len(rxn),
        "species_names": species_names[:200],   # truncate for prompt size
    }


# ════════════════════════════════════════════════════════════════════
#  S4 — calc-input validation
# ════════════════════════════════════════════════════════════════════

def wrap_validate_calc_input(
    *,
    purpose: str,
    tasks: str,
    calc_input_dict: Dict[str, Any],
    card_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Validate a candidate ``CalcInput`` dict.

    Runs the calc-tool's own ``CalcInput.validate`` (returns issue list)
    *and*, when a ``card_path`` is provided, runs
    ``constraint_compiler.validate_catalog_against_report`` to surface
    per-axis DOF errors.
    """
    _require_purpose_tasks(purpose, tasks)
    issues: List[str] = []

    # 1) Basic schema
    try:
        from ..NIST_SRD46_core_numcalc_pipeline.numcalc_input_cards_reader.calc_json_input_reader import load_calc_input
        ci = load_calc_input(dict(calc_input_dict))
        issues.extend(list(ci.validate() or []))
    except Exception as exc:                       # pragma: no cover
        issues.append(f"calc_input_load_error:{exc!r}")
        return {"ok": False, "issues": issues}

    # 2) Optional constraint compiler against the assembled report
    if card_path is not None:
        try:
            from ..NIST_SRD46_calc_input_building_agentic_pipeline.card_management_helpers.free_energy_md_card_reader import (
                parse_free_energy_card_md,
            )
            from ..NIST_SRD46_core_numcalc_pipeline.sweep_pipelines._sweep_input_entry_point.constraint_compiler import (
                build_default_catalog,
                merge_catalog_overrides,
                validate_catalog_against_report,
            )
            report = parse_free_energy_card_md(Path(card_path))
            sys_cat_raw = ci.system_catalog if hasattr(ci, "system_catalog") else None
            # ``ci.system_catalog`` is a plain dict (per CalcInput dataclass);
            # the constraint compiler expects a typed ``SystemCatalog``.
            # Build a default catalog from the report and merge the user
            # overrides on top of it.
            base_catalog = build_default_catalog(report)
            if isinstance(sys_cat_raw, dict) and sys_cat_raw:
                sys_cat = merge_catalog_overrides(base_catalog, sys_cat_raw)
            else:
                sys_cat = base_catalog
            validate_catalog_against_report(sys_cat, report)
        except Exception as exc:
            issues.append(f"constraint_compiler:{type(exc).__name__}:{exc}")

    return {"ok": not issues, "issues": issues}


# ════════════════════════════════════════════════════════════════════
#  S6 — run_calculation
# ════════════════════════════════════════════════════════════════════

def wrap_run_calculation(
    *,
    purpose: str,
    tasks: str,
    card_path: Union[str, Path],
    calc_input_dict: Dict[str, Any],
    output_dir: Union[str, Path],
    debug: bool = False,
) -> Dict[str, Any]:
    """Run the unified calculator and return only file-system pointers.

    Numbers (grids / reports) are intentionally *not* returned in the
    dict — downstream prose generation (S8) must read them via the L2
    inspector that wraps ``extract_topology``, never from this dict.
    """
    _require_purpose_tasks(purpose, tasks)
    from ..NIST_SRD46_core_numcalc_pipeline.SRD46_numcalculator_api import run_calculation
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = run_calculation(
        card_source=Path(card_path),
        calc_input=dict(calc_input_dict),
        output_dir=out_dir,
        debug=debug,
    )
    out_paths = result.get("output_paths") or []
    return {
        "output_dir": str(out_dir),
        "sweep_method": result.get("sweep_method", ""),
        "output_paths": [str(p) for p in out_paths],
        "n_output_files": len(out_paths),
    }


# ════════════════════════════════════════════════════════════════════
#  S7 — topology extraction (read-only)
# ════════════════════════════════════════════════════════════════════

def wrap_extract_topology(
    *,
    purpose: str,
    tasks: str,
    output_dir: Union[str, Path],
) -> str:
    """Render a compact markdown report of the result-grid topology.

    The string returned is the **raw markdown for re-injection** into
    L0's C4 prompt — no LLM compaction must intervene.
    """
    _require_purpose_tasks(purpose, tasks)
    out = Path(output_dir)
    # Try to find a saved grid pickle / JSON the calc tool emits.
    summary_paths = sorted(out.glob("**/topology*.md"))
    if summary_paths:
        return summary_paths[0].read_text(encoding="utf-8")
    # Fallback: enumerate output files so the prose layer at least has
    # something deterministic to reference.
    files = sorted(out.rglob("*"))
    lines = [f"# Output inventory for {out.name}", ""]
    for f in files:
        if f.is_file():
            lines.append(f"- `{f.relative_to(out)}` ({f.stat().st_size} B)")
    return "\n".join(lines)


# ════════════════════════════════════════════════════════════════════
#  Internal helpers
# ════════════════════════════════════════════════════════════════════

def _safe_len(obj: Any, key: str) -> int:
    try:
        v = obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)
        return len(v) if v is not None else 0
    except Exception:
        return 0


def _safe_attr_len(obj: Any, attr: str) -> int:
    try:
        return len(getattr(obj, attr, []) or [])
    except Exception:
        return 0
