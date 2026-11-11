"""LC2_1_ref_eq_card_orchestrator.py
LC2_1 stage orchestrator: system catalog -> free-energy MD card.

Pipeline position
-----------------
LC1_1 produces a *system catalog* (``prompt_NN_system_catalog.json``) that
fixes the correct SRD-46 IDs for every metal / ligand in a chemical system.
LC1_2 (optionally) validates each metal-ligand equilibrium network and
patches database typos, emitting ``lc1_2_eqmap_card.json``.

This orchestrator consumes those LC1 artefacts and drives the LC2_1
ref-eq card initializer end-to-end:

    1.  Build one reference free-energy MD card per (metal, ligand) pair
        (``ref_eq_SRD46_json_cards_builder``).
    2.  Merge the per-pair cards into a single unified free-energy MD card
        for the whole system (``ref_eq_SRD46_md_cards_merger``).  Nothing
        is dropped except truly identical species.

Two input modes (the user may supply either or both):

  * **system catalog only** — the IDs are known but the equilibrium
    networks are not yet fixed; the builder auto-fetches the primary
    network per pair and auto-discovers valence siblings.
  * **system catalog + LC1_2 eqmap card** — the validated/patched
    networks chosen by LC1_2 drive the build (no valence expansion;
    LC1_2 already chose the canonical set).  The catalog still supplies
    the system identity / human-readable name.
  * **LC1_2 eqmap card only** — identity is derived from the card path.

All artefacts for a system land in a single *test folder* named after the
input (e.g. ``prompt_03``):

    <output_dir>/<test_name>/
        free_energy_card.md          <- final merged card
        _ref_cards/                  <- per-pair .md/.json + _eq_maps/
        lc2_1_manifest.json          <- run manifest
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

# ── path bootstrapping ──────────────────────────────────────────
_THIS = Path(__file__).absolute()
_LC2_ROOT = _THIS.parents[1]                # LC2_free_energy_card_building/
_PIPELINE_ROOT = _THIS.parents[2]           # NIST_SRD46_calc_input_building_agentic_pipeline/
_ANALYSIS_ROOT = _THIS.parents[3]           # NIST_SRD46_analysis_agent/
_NUMCALC_ROOT = _ANALYSIS_ROOT / "NIST_SRD46_core_numcalc_pipeline"

for _p in (_PIPELINE_ROOT, _LC2_ROOT, _NUMCALC_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    from LC2_free_energy_card_building.LC2_1_card_initializer.ref_eq_SRD46_json_cards_builder.ref_eq_SRD46_json_cards_builder import (
        build_all_ref_cards,
        build_ref_cards_from_lc1_2_card,
    )
except ModuleNotFoundError:
    if os.name != "nt":
        raise
    _builder_dir = _THIS.parent / "ref_eq_SRD46_json_cards_builder"
    _builder_search = os.path.abspath(os.fspath(_builder_dir))
    if not _builder_search.startswith("\\\\?\\"):
        if _builder_search.startswith("\\\\"):
            _builder_search = "\\\\?\\UNC\\" + _builder_search[2:]
        else:
            _builder_search = "\\\\?\\" + _builder_search
    if _builder_search not in sys.path:
        sys.path.insert(0, _builder_search)
    from ref_eq_SRD46_json_cards_builder import (
        build_all_ref_cards,
        build_ref_cards_from_lc1_2_card,
    )
from LC2_free_energy_card_building.LC2_1_card_initializer.ref_eq_SRD46_md_cards_merger.ref_eq_SRD46_cards_merger import (
    merge_ref_cards,
)


# ═══════════════════════════════════════════════════════════════════
#  System-catalog parsing
# ═══════════════════════════════════════════════════════════════════

def _load_system_catalog(catalog_path: Path) -> dict:
    """Load and return the ``chemical_system`` block from a catalog file."""
    doc = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog = doc.get("system_catalog", doc)
    chem = catalog.get("chemical_system", catalog)
    metals = chem.get("metals") or []
    ligands = chem.get("ligands") or []
    if not metals or not ligands:
        raise ValueError(
            f"System catalog {catalog_path.name} has no metals/ligands "
            f"({len(metals)} metal(s), {len(ligands)} ligand(s))"
        )
    return {"metals": metals, "ligands": ligands}


def _system_name_from_catalog(chem: dict) -> str:
    """Human-readable system label, e.g. 'Fe, Cu / Glycine, Citric acid'."""
    metal_names = [m.get("name") or m.get("element") or str(m.get("db_id"))
                   for m in chem["metals"]]
    ligand_names = [l.get("name") or str(l.get("db_id"))
                    for l in chem["ligands"]]
    return f"{', '.join(metal_names)} / {', '.join(ligand_names)}"


def _catalog_numeric_id(value: object, prefix: str) -> Optional[int]:
    """Parse an integer or canonical ``<prefix>_N`` catalog identifier."""

    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    text = str(value).strip()
    marker = f"{prefix}_"
    if text.startswith(marker):
        text = text[len(marker):]
    if not text.isdigit():
        return None
    result = int(text)
    return result if result > 0 else None


def _ligand_component_contracts(
    chem: Mapping[str, object],
) -> Dict[int, Dict[str, Any]]:
    """Extract explicit catalog-owned ligand component declarations.

    LC1_1 publishes a provenance-bearing ``free_ligand_state`` only when it
    can resolve a ligand that lacks an SRD-46 HxL/pKa/figure reference state.
    Keep that declaration bound to its canonical ligand ID while LC2 builds
    per-pair cards.  Chemical validation remains the component builder's job;
    this seam only prevents the catalog metadata from being discarded.
    """

    contracts: Dict[int, Dict[str, Any]] = {}
    for index, ligand in enumerate(chem.get("ligands") or []):
        if not isinstance(ligand, Mapping):
            continue
        contract = ligand.get("free_ligand_state")
        if contract is None:
            continue
        ligand_id = _catalog_numeric_id(
            ligand.get("db_id") or ligand.get("ligand_id"),
            "ligand",
        )
        if ligand_id is None:
            raise ValueError(
                "A system-catalog ligand with free_ligand_state has no "
                f"usable canonical ligand ID (ligands[{index}])"
            )
        if not isinstance(contract, Mapping):
            raise ValueError(
                f"ligand_{ligand_id}.free_ligand_state must be an object"
            )
        if ligand_id in contracts:
            raise ValueError(
                f"Duplicate free_ligand_state contract for ligand_{ligand_id}"
            )
        # JSON round-trip gives downstream callers an isolated, plain mapping
        # and rejects non-serializable provenance before card construction.
        contracts[ligand_id] = json.loads(json.dumps(
            dict(contract), ensure_ascii=False,
        ))
    return contracts


def _ligand_component_contract_sha256(
    contracts: Mapping[int, Mapping[str, Any]],
) -> Optional[str]:
    """Canonical digest for the exact catalog declarations consumed by LC2."""

    if not contracts:
        return None
    payload = [
        {
            "ligand_id": int(ligand_id),
            "free_ligand_state": contract,
        }
        for ligand_id, contract in sorted(
            contracts.items(), key=lambda item: int(item[0])
        )
    ]
    return hashlib.sha256(json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")).hexdigest()


def _system_catalog_pair_set(chem: dict) -> frozenset[tuple[int, int]]:
    """Expand every catalog metal redox-state ID across every ligand ID."""

    metal_ids: set[int] = set()
    for metal in chem.get("metals") or []:
        if not isinstance(metal, dict):
            continue
        candidates = [metal, *(metal.get("redox_states") or [])]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            metal_id = _catalog_numeric_id(
                candidate.get("db_id") or candidate.get("metal_id"),
                "metal",
            )
            if metal_id is not None:
                metal_ids.add(metal_id)

    ligand_ids: set[int] = set()
    for ligand in chem.get("ligands") or []:
        if not isinstance(ligand, dict):
            continue
        ligand_id = _catalog_numeric_id(
            ligand.get("db_id") or ligand.get("ligand_id"),
            "ligand",
        )
        if ligand_id is not None:
            ligand_ids.add(ligand_id)

    if not metal_ids or not ligand_ids:
        raise ValueError(
            "The active system catalog does not contain usable canonical "
            "metal redox-state and ligand IDs for support eq_map binding"
        )
    return frozenset(
        (metal_id, ligand_id)
        for metal_id in metal_ids
        for ligand_id in ligand_ids
    )


def _file_sha256(path: Path) -> str:
    """Hash the exact catalog artefact used to authorize support pairs."""

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_support_handoff(
    *,
    support_eq_map_path: Union[str, Path, None],
    expected_support_session_id: Optional[str],
    expected_support_eq_map_sha256: Optional[str],
    session_working_map_path: Union[str, Path, None],
    expected_session_working_map_sha256: Optional[str],
) -> None:
    """Require the complete LC1_3 support + session-map publication."""

    enabled_receipts = (
        expected_support_session_id,
        expected_support_eq_map_sha256,
        session_working_map_path,
        expected_session_working_map_sha256,
    )
    if support_eq_map_path is None:
        if any(value is not None for value in enabled_receipts):
            raise ValueError(
                "enabled support receipts require support_eq_map_path"
            )
        return
    if not str(support_eq_map_path).strip():
        raise ValueError("support_eq_map_path must be a nonempty path")
    if not isinstance(expected_support_session_id, str) or not (
        expected_support_session_id.strip()
    ):
        raise ValueError(
            "support_eq_map_path requires expected_support_session_id"
        )
    if re.fullmatch(
        r"[0-9a-f]{64}", str(expected_support_eq_map_sha256)
    ) is None:
        raise ValueError(
            "support_eq_map_path requires an exact lowercase "
            "expected_support_eq_map_sha256"
        )
    if session_working_map_path is None or not str(
        session_working_map_path
    ).strip():
        raise ValueError(
            "support_eq_map_path requires session_working_map_path"
        )
    if re.fullmatch(
        r"[0-9a-f]{64}", str(expected_session_working_map_sha256)
    ) is None:
        raise ValueError(
            "support_eq_map_path requires an exact lowercase "
            "expected_session_working_map_sha256"
        )


def _synthesize_eqmap_card(chem: dict, dest: Path) -> Path:
    """Write a minimal ``equilibrium_networks`` card from the catalog.

    One entry per (metal, ligand) pair with only the IDs filled in; the
    builder auto-fetches the primary network and valence siblings.
    """
    networks: List[dict] = []
    for metal in chem["metals"]:
        metal_id = metal.get("db_id") or metal.get("metal_id")
        if not metal_id:
            # New schema: the per-oxidation-state IDs live in redox_states;
            # use the first (highest-charge) state as the representative.
            for rs in metal.get("redox_states") or []:
                if isinstance(rs, dict) and rs.get("db_id"):
                    metal_id = rs["db_id"]
                    break
        for ligand in chem["ligands"]:
            ligand_id = ligand.get("db_id", ligand.get("ligand_id"))
            networks.append({
                "metal_id": metal_id,
                "ligand_id": ligand_id,
                "metal_name": metal.get("name"),
                "ligand_name": ligand.get("name"),
            })
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps({"equilibrium_networks": networks}, indent=2,
                   ensure_ascii=False),
        encoding="utf-8",
    )
    return dest


def _derive_test_name(
    explicit: Optional[str],
    system_catalog_path: Optional[Path],
    lc1_2_eqmap_card_path: Optional[Path],
) -> str:
    """Resolve the test-folder name for this run."""
    if explicit:
        return explicit
    if system_catalog_path is not None:
        stem = system_catalog_path.stem
        # 'prompt_03_system_catalog' -> 'prompt_03'
        return stem.replace("_system_catalog", "") or stem
    if lc1_2_eqmap_card_path is not None:
        # '.../prompt_03/lc1_2_eqmap_card.json' -> 'prompt_03'
        parent = lc1_2_eqmap_card_path.parent.name
        return parent or lc1_2_eqmap_card_path.stem
    return "lc2_1_system"


# ═══════════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════════

def run_lc2_1(
    system_catalog_path: Union[str, Path, None] = None,
    lc1_2_eqmap_card_path: Union[str, Path, None] = None,
    output_dir: Union[str, Path] = None,
    *,
    test_name: Optional[str] = None,
    auto_hydroxide: bool = False,
    auto_pka: bool = False,
    auto_valence: bool = True,
    atlas_merge: bool = False,
    support_eq_map_path: Union[str, Path, None] = None,
    expected_support_session_id: Optional[str] = None,
    expected_support_eq_map_sha256: Optional[str] = None,
    session_working_map_path: Union[str, Path, None] = None,
    expected_session_working_map_sha256: Optional[str] = None,
) -> dict:
    """Run the LC2_1 ref-eq card stage for one chemical system.

    Parameters
    ----------
    system_catalog_path : path | None
        LC1_1 ``prompt_NN_system_catalog.json`` (defines metal/ligand IDs
        and the human-readable system name).
    lc1_2_eqmap_card_path : path | None
        LC1_2 ``lc1_2_eqmap_card.json`` with validated + patched networks.
        When supplied it drives the build (no valence expansion); the
        catalog, if given too, only supplies the system name.
    support_eq_map_path : path | None
        Enabled-run LC1_3 full native support eq-map.  It is consumed only
        with an LC1_2 base card and merged into session-local working eq maps
        before ordinary equation and free-energy materialization.
    expected_support_session_id, expected_support_eq_map_sha256 : str | None
        Exact enabled-run publication receipt. Both are mandatory with a
        support path and are checked before working-map construction.
    session_working_map_path, expected_session_working_map_sha256
        Exact LC1_3 working-map publication and digest. Both are mandatory
        with a support path and are revalidated before compilation.
    output_dir : path
        Base directory.  All artefacts land in ``output_dir/<test_name>/``.
    test_name : str | None
        Override the test-folder name.  Defaults to the catalog/card name.
    auto_hydroxide, auto_pka, auto_valence, atlas_merge
        Passed through to the builder.  ``auto_valence`` only applies in
        catalog-only mode.

    Returns
    -------
    dict
        Run manifest (also written to ``lc2_1_manifest.json``).
    """
    if system_catalog_path is None and lc1_2_eqmap_card_path is None:
        raise ValueError(
            "run_lc2_1 needs a system_catalog_path and/or a "
            "lc1_2_eqmap_card_path"
        )
    if output_dir is None:
        raise ValueError("run_lc2_1 needs an output_dir")
    _validate_support_handoff(
        support_eq_map_path=support_eq_map_path,
        expected_support_session_id=expected_support_session_id,
        expected_support_eq_map_sha256=expected_support_eq_map_sha256,
        session_working_map_path=session_working_map_path,
        expected_session_working_map_sha256=(
            expected_session_working_map_sha256
        ),
    )

    system_catalog_path = Path(system_catalog_path) if system_catalog_path else None
    lc1_2_eqmap_card_path = (
        Path(lc1_2_eqmap_card_path) if lc1_2_eqmap_card_path else None
    )
    support_eq_map_path = Path(support_eq_map_path) if support_eq_map_path else None
    session_working_map_path = (
        Path(session_working_map_path) if session_working_map_path else None
    )
    if support_eq_map_path is not None and lc1_2_eqmap_card_path is None:
        raise ValueError("support_eq_map_path requires lc1_2_eqmap_card_path")
    if support_eq_map_path is not None and system_catalog_path is None:
        raise ValueError(
            "support_eq_map_path requires system_catalog_path so LC2 can bind "
            "every support pair to the active analysis"
        )
    # ── Resolve identity + output layout ────────────────────────
    test_name = _derive_test_name(
        test_name, system_catalog_path, lc1_2_eqmap_card_path,
    )
    out_root = Path(output_dir) / test_name
    ref_cards_dir = out_root / "_ref_cards"
    ref_cards_dir.mkdir(parents=True, exist_ok=True)

    chem: Optional[dict] = None
    ligand_component_contracts: Dict[int, Dict[str, Any]] = {}
    if system_catalog_path is not None:
        chem = _load_system_catalog(system_catalog_path)
        system_name = _system_name_from_catalog(chem)
        ligand_component_contracts = _ligand_component_contracts(chem)
    else:
        system_name = test_name
    component_contract_kwargs = (
        {"ligand_component_contracts": ligand_component_contracts}
        if ligand_component_contracts else {}
    )
    component_contract_sha256 = _ligand_component_contract_sha256(
        ligand_component_contracts
    )

    # ── Stage 1: build per-pair reference cards ─────────────────
    if lc1_2_eqmap_card_path is not None:
        source = "lc1_2_eqmap_card"
        if support_eq_map_path is None:
            # Keep the disabled invocation identical to the legacy call.
            ref_card_paths = build_ref_cards_from_lc1_2_card(
                lc1_2_eqmap_card_path,
                storage_dir=ref_cards_dir,
                **component_contract_kwargs,
                auto_hydroxide=auto_hydroxide,
                auto_pka=auto_pka,
                atlas_merge=atlas_merge,
            )
        else:
            allowed_system_pairs = _system_catalog_pair_set(chem)
            ref_card_paths = build_ref_cards_from_lc1_2_card(
                lc1_2_eqmap_card_path,
                storage_dir=ref_cards_dir,
                **component_contract_kwargs,
                auto_hydroxide=auto_hydroxide,
                auto_pka=auto_pka,
                atlas_merge=atlas_merge,
                support_eq_map_path=support_eq_map_path,
                expected_support_session_id=expected_support_session_id,
                expected_support_eq_map_sha256=expected_support_eq_map_sha256,
                session_working_map_path=session_working_map_path,
                expected_session_working_map_sha256=(
                    expected_session_working_map_sha256
                ),
                allowed_system_pairs=allowed_system_pairs,
                system_catalog_sha256=_file_sha256(system_catalog_path),
            )
    else:
        source = "system_catalog"
        synth = _synthesize_eqmap_card(
            chem, ref_cards_dir / "_synth_eqmap_from_catalog.json",
        )
        ref_card_paths = build_all_ref_cards(
            synth,
            storage_dir=ref_cards_dir,
            **component_contract_kwargs,
            auto_hydroxide=auto_hydroxide,
            auto_pka=auto_pka,
            auto_valence=auto_valence,
            atlas_merge=atlas_merge,
        )

    if not ref_card_paths:
        raise RuntimeError(
            f"LC2_1 produced no reference cards for {test_name!r}"
        )

    # ── Stage 2: merge into one free-energy card ────────────────
    merged_md, merged_report, srd_srd_collisions = merge_ref_cards(
        ref_card_paths, system_name=system_name,
    )
    merged_path = out_root / "free_energy_card.md"
    merged_path.write_text(merged_md, encoding="utf-8")

    srd_srd_collisions_path = None
    if srd_srd_collisions:
        srd_srd_collisions_path = out_root / "srd_srd_duplicates.json"
        srd_srd_collisions_path.write_text(
            json.dumps(srd_srd_collisions, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ── Manifest ────────────────────────────────────────────────
    manifest = {
        "schema_version": 1,
        "artifact_kind": "LC2_1 deterministic free-energy-card initialization",
        "stage": "LC2_1",
        "test_name": test_name,
        "system_name": system_name,
        "source": source,
        "system_catalog_path": str(system_catalog_path) if system_catalog_path else None,
        "lc1_2_eqmap_card_path": str(lc1_2_eqmap_card_path) if lc1_2_eqmap_card_path else None,
        "output_dir": str(out_root),
        "ref_cards_dir": str(ref_cards_dir),
        "merged_card_path": str(merged_path),
        "n_ref_cards": len(ref_card_paths),
        "n_species_merged": len(merged_report.species),
        "srd_srd_collision_count": len(srd_srd_collisions),
        "srd_srd_collisions_path": (
            str(srd_srd_collisions_path) if srd_srd_collisions_path else None
        ),
        "ref_card_paths": [str(p) for p in ref_card_paths],
        "ligand_component_contract_count": len(ligand_component_contracts),
        "ligand_component_contract_ids": [
            f"ligand_{ligand_id}"
            for ligand_id in sorted(ligand_component_contracts)
        ],
        "ligand_component_contract_sha256": component_contract_sha256,
        "ligand_component_contract_receipts": {
            f"ligand_{ligand_id}": contract.get("receipt_sha256")
            for ligand_id, contract in sorted(
                ligand_component_contracts.items()
            )
        },
        "agent_context": {
            "expected_calls": 0,
            "documented_calls": 0,
            "complete": True,
            "reason": (
                "LC2_1 deterministically consumes reviewed LC1 artifacts; "
                "it invokes no LLM agent inside LC2."
            ),
        },
    }
    if support_eq_map_path is not None:
        compile_manifest_path = ref_cards_dir / "support_eq_map_compile_manifest.json"
        compile_manifest = json.loads(compile_manifest_path.read_text(encoding="utf-8"))
        manifest.update({
            "support_eq_map_path": str(support_eq_map_path),
            "support_eq_map_sha256": compile_manifest["support_eq_map_sha256"],
            "support_session_id": compile_manifest["support_session_id"],
            "expected_support_eq_map_sha256": compile_manifest[
                "expected_support_eq_map_sha256"
            ],
            "expected_support_session_id": compile_manifest[
                "expected_support_session_id"
            ],
            "provenance_binding_verified": compile_manifest[
                "provenance_binding_verified"
            ],
            "session_working_map_path": compile_manifest.get(
                "session_working_map_path"
            ),
            "session_working_map_sha256": compile_manifest.get(
                "session_working_map_sha256"
            ),
            "expected_session_working_map_sha256": compile_manifest.get(
                "expected_session_working_map_sha256"
            ),
            "session_working_map_binding_verified": compile_manifest.get(
                "session_working_map_binding_verified", False
            ),
            "system_catalog_sha256": compile_manifest["system_catalog_sha256"],
            "system_catalog_pair_set_sha256": compile_manifest[
                "system_catalog_pair_set_sha256"
            ],
            "support_node_count": compile_manifest["support_node_count"],
            "support_candidate_count": compile_manifest["support_node_count"],
            "selected_support_node_count": compile_manifest[
                "selected_support_node_count"
            ],
            "materialized_estimated_entry_count": compile_manifest[
                "materialized_estimated_entry_count"
            ],
            "support_compile_manifest_path": str(compile_manifest_path),
        })
    (out_root / "lc2_1_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return manifest


# ═══════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════

def _main(argv: List[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="LC2_1 ref-eq card orchestrator (catalog -> free-energy MD)",
    )
    parser.add_argument(
        "--system-catalog", dest="system_catalog", default=None,
        help="Path to LC1_1 prompt_NN_system_catalog.json",
    )
    parser.add_argument(
        "--lc1-2-card", dest="lc1_2_card", default=None,
        help="Path to LC1_2 lc1_2_eqmap_card.json (optional)",
    )
    parser.add_argument(
        "--support-eq-map", dest="support_eq_map", default=None,
        help="Path to the enabled-run LC1_3 full native support eq-map",
    )
    parser.add_argument(
        "--expected-support-session-id",
        dest="expected_support_session_id",
        default=None,
        help="Exact LC1_3 session ID that published --support-eq-map",
    )
    parser.add_argument(
        "--expected-support-eq-map-sha256",
        dest="expected_support_eq_map_sha256",
        default=None,
        help="Exact SHA-256 receipt for --support-eq-map",
    )
    parser.add_argument(
        "--session-working-map",
        dest="session_working_map",
        default=None,
        help="Path to the LC1_3 validated session working map",
    )
    parser.add_argument(
        "--expected-session-working-map-sha256",
        dest="expected_session_working_map_sha256",
        default=None,
        help="Exact SHA-256 receipt for --session-working-map",
    )
    parser.add_argument(
        "--output-dir", dest="output_dir", required=True,
        help="Base output directory (artefacts land in <output_dir>/<test_name>/)",
    )
    parser.add_argument("--test-name", dest="test_name", default=None)
    parser.add_argument("--auto-hydroxide", action="store_true")
    parser.add_argument("--auto-pka", action="store_true")
    parser.add_argument("--no-valence", dest="auto_valence",
                        action="store_false")
    parser.add_argument("--atlas-merge", action="store_true")
    args = parser.parse_args(argv)

    manifest = run_lc2_1(
        system_catalog_path=args.system_catalog,
        lc1_2_eqmap_card_path=args.lc1_2_card,
        output_dir=args.output_dir,
        test_name=args.test_name,
        auto_hydroxide=args.auto_hydroxide,
        auto_pka=args.auto_pka,
        auto_valence=args.auto_valence,
        atlas_merge=args.atlas_merge,
        support_eq_map_path=args.support_eq_map,
        expected_support_session_id=args.expected_support_session_id,
        expected_support_eq_map_sha256=args.expected_support_eq_map_sha256,
        session_working_map_path=args.session_working_map,
        expected_session_working_map_sha256=(
            args.expected_session_working_map_sha256
        ),
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
