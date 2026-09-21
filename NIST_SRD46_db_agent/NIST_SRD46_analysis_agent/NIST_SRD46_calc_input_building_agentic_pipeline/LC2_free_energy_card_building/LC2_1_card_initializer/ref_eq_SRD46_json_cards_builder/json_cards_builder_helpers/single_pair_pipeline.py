"""single_pair_pipeline.py
Build the ref-eq card JSON for a single metal-ligand pair.

Stages:
  1. Build components JSON from IDs        (component_builder)
  2. Build equations + final ref-eq card   (equation_builder)
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

# -- path bootstrapping ----------------------------------------------------
_THIS = Path(__file__).absolute()
_CALC_ROOT = _THIS.parents[3]
if str(_CALC_ROOT) not in sys.path:
    sys.path.insert(0, str(_CALC_ROOT))


# =========================================================================
#  Windows long-path (>260 char MAX_PATH) safe file IO
# =========================================================================

def winlong(path) -> str:
    """Return a filesystem path string safe for >260-char IO on Windows.

    Deeply nested run trees (prompt/LC2/LC2_1/<test>/_ref_cards/<long
    ref-card filename>) can exceed the legacy MAX_PATH (260) limit and
    raise ``FileNotFoundError`` on write.  Prefixing an absolute path
    with the extended-length marker ``\\\\?\\`` lifts the limit.  On
    non-Windows platforms the path is returned unchanged.
    """
    sp = os.fspath(path)
    if os.name != "nt":
        return sp
    ap = os.path.abspath(sp)
    if ap.startswith("\\\\?\\"):
        return ap
    if ap.startswith("\\\\"):                       # UNC share
        return "\\\\?\\UNC\\" + ap[2:]
    return "\\\\?\\" + ap


def write_text_long(path, text: str, *, encoding: str = "utf-8") -> None:
    """``Path.write_text`` that tolerates >260-char paths on Windows."""
    with open(winlong(path), "w", encoding=encoding) as fh:
        fh.write(text)


def read_text_long(path, *, encoding: str = "utf-8") -> str:
    """``Path.read_text`` that tolerates >260-char paths on Windows."""
    with open(winlong(path), "r", encoding=encoding) as fh:
        return fh.read()

# -- sibling imports -------------------------------------------------------
from .component_builder import build_components_from_ids_json
from .equation_builder import build_final_card
from .lc1_2_patch_adapter import lc1_2_patches_to_vlm_overrides


# =========================================================================
#  ID / tag parsing utilities
# =========================================================================

def parse_id(value) -> int:
    """Accept either an integer or a string like 'metal_25' / 'ligand_9058'."""
    if isinstance(value, int):
        return value
    s = str(value).strip()
    numeric = s.split("_")[-1]
    return int(numeric)


def extract_eq_net_id(eq_network_tag: str) -> int:
    """Extract numeric network ID from a tag like 'ref_eq_net_86'."""
    m = re.search(r"(\d+)$", eq_network_tag)
    if not m:
        raise ValueError(f"Cannot parse network ID from {eq_network_tag!r}")
    return int(m.group(1))


# =========================================================================
#  JSON extraction from network lists
# =========================================================================

def extract_ids_json(networks: List[dict]) -> dict:
    """Build minimal IDs JSON from a list of network entries."""
    metals_seen: Dict[int, dict] = {}
    ligands_seen: Dict[int, dict] = {}
    for net in networks:
        mid = parse_id(net["metal_id"])
        lid = parse_id(net["ligand_id"])
        if mid not in metals_seen:
            metals_seen[mid] = {"metal_id": mid}
        if lid not in ligands_seen:
            ligands_seen[lid] = {"ligand_id": lid}
    return {
        "metals": list(metals_seen.values()),
        "ligands": list(ligands_seen.values()),
    }


def extract_maps_json(networks: List[dict]) -> dict:
    """Build maps JSON from a list of network entries.

    When a network entry carries ``patch_notes.patches`` (the shape
    emitted by LC1_2's eq-map validator), the patches are translated
    into legacy ``vlm_overrides`` via
    :func:`lc1_2_patches_to_vlm_overrides` and attached to that pair's
    dict.  Pairs without patches simply have no ``vlm_overrides`` key.
    """
    pairs: List[dict] = []
    for net in networks:
        net_id = extract_eq_net_id(net["eq_network"])
        mid = parse_id(net["metal_id"])
        lid = parse_id(net["ligand_id"])
        pair_dict: Dict[str, object] = {
            "metal_id": mid,
            "ligand_id": lid,
            "selected_network_ids": [net_id],
        }
        patch_notes = net.get("patch_notes") or {}
        patches = patch_notes.get("patches") or []
        if patches:
            pair_dict["vlm_overrides"] = lc1_2_patches_to_vlm_overrides(
                patches, metal_id=mid, ligand_id=lid,
            )
        pairs.append(pair_dict)
    return {"pairs": pairs}


# =========================================================================
#  Pipeline runner - eq-map writer + ref-eq card renderer
# =========================================================================

def write_eq_map_artefacts(
    augmented_networks: List[dict],
    out_dir: Path,
    *,
    file_stem: str = "",
) -> Dict[str, str]:
    """Persist the eq-map artefacts (ids.json + maps.json + augmented).

    Returns absolute paths under the keys ``ids_json_path``,
    ``maps_json_path``, ``augmented_networks_path``.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"_{file_stem}" if file_stem else ""
    ids_path = out_dir / f"ids{suffix}.json"
    maps_path = out_dir / f"maps{suffix}.json"
    aug_path = out_dir / f"augmented_networks{suffix}.json"

    ids_json = extract_ids_json(augmented_networks)
    maps_json = extract_maps_json(augmented_networks)

    write_text_long(ids_path, json.dumps(ids_json, indent=2))
    write_text_long(maps_path, json.dumps(maps_json, indent=2))
    write_text_long(
        aug_path,
        json.dumps(augmented_networks, indent=2, default=str),
    )

    return {
        "ids_json_path": str(ids_path),
        "maps_json_path": str(maps_path),
        "augmented_networks_path": str(aug_path),
    }


def render_card_from_eq_map_files(
    *,
    ids_json_path: str | Path,
    maps_json_path: str | Path,
    temperature: float,
    ionic_strength: float,
    system_name: str = "",
    ligand_component_contracts: Optional[
        Mapping[int, Mapping[str, Any]]
    ] = None,
) -> dict:
    """Build the ref-eq card JSON from already-persisted eq-map JSONs.

    Stages
    ------
    1. ``build_components_from_ids_json``  ->  components JSON
    2. ``build_final_card``                ->  ref-eq card JSON
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        components_path = tmp_dir / "components.json"
        final_card_path = tmp_dir / "final_card.json"

        # Stage 1
        build_components_from_ids_json(
            ids_json_path=str(ids_json_path),
            output_json_path=str(components_path),
            **({
                "ligand_component_contracts": ligand_component_contracts,
            } if ligand_component_contracts else {}),
        )

        # Stage 2
        card_json = build_final_card(
            component_template_json_path=str(components_path),
            selected_map_json_path=str(maps_json_path),
            output_json_path=str(final_card_path),
            temperature=temperature,
            ionic_strength=ionic_strength,
        )

    return card_json
