"""component_unifier.py
Merge component metadata across multiple FreeEnergyReports.

Components with the same ``db_id`` (e.g. ``"metal_41"``) are treated
as identical and mapped to a single unified ID.  H⁺ (M0) and OH⁻ (L0)
are always shared.
"""
from __future__ import annotations

import copy
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Tuple

# ── path bootstrapping ──────────────────────────────────────────
_THIS = Path(__file__).absolute()
_CALC_ROOT = _THIS.parents[3]                       # NIST_SRD46_core_calc_tools/
if str(_CALC_ROOT) not in sys.path:
    sys.path.insert(0, str(_CALC_ROOT))

from thermodynamics_helpers.gibbs_value_calc_from_logK_eq_map_helpers.free_energy_network_calc_helper import (
    FreeEnergyReport,
    ComponentMeta,
)


def unify_components(
    reports: List[FreeEnergyReport],
) -> Tuple[
    List[ComponentMeta],            # unified component list
    List[Dict[str, str]],           # per-report old_id → new_id mapping
    Dict[str, float | str],         # unified total_metals
    Dict[str, float | str],         # unified total_ligands
    List[str],                      # unified metal_ids
    List[str],                      # unified ligand_ids
    List[str],                      # unified metal_names
    List[str],                      # unified ligand_names
    Dict[str, int],                 # unified metal_charges
    Dict[str, int],                 # unified ligand_charges
]:
    """Merge component metadata across reports, deduplicating by db_id.

    Components with the same ``db_id`` (e.g. ``"metal_41"``) are treated
    as identical and mapped to a single unified ID.  H⁺ (M0) and OH⁻ (L0)
    are always shared.
    """
    # db_id → unified ComponentMeta
    seen_metals: OrderedDict[str, ComponentMeta] = OrderedDict()
    seen_ligands: OrderedDict[str, ComponentMeta] = OrderedDict()

    # Per-report remapping: old_id → new_id
    remaps: List[Dict[str, str]] = []

    for report in reports:
        remap: Dict[str, str] = {"H": "H", "OH": "OH"}
        for cm in report.component_meta:
            if cm.comp_type == "metal":
                if cm.db_id not in seen_metals:
                    seen_metals[cm.db_id] = copy.deepcopy(cm)
                remap[cm.internal_id] = seen_metals[cm.db_id].internal_id
            elif cm.comp_type == "ligand":
                if cm.db_id not in seen_ligands:
                    seen_ligands[cm.db_id] = copy.deepcopy(cm)
                remap[cm.internal_id] = seen_ligands[cm.db_id].internal_id
        remaps.append(remap)

    # Re-index metals to M1, M2, … and ligands to L1, L2, …
    metal_list = list(seen_metals.values())
    ligand_list = list(seen_ligands.values())

    # Build final metal index (skip H+ which stays as internal_id from first report)
    metal_ids: List[str] = []
    metal_names: List[str] = []
    metal_charges: Dict[str, int] = {}
    total_metals: Dict[str, float | str] = {}

    # Build unified ID mapping: old db_id → new sequential ID
    metal_reindex: Dict[str, str] = {}
    metal_idx = 1
    for cm in metal_list:
        old_id = cm.internal_id
        if cm.db_id.startswith("metal_68"):
            # H+ — keep original
            metal_reindex[cm.db_id] = old_id
            continue
        new_id = f"M{metal_idx}"
        metal_reindex[cm.db_id] = new_id
        cm.internal_id = new_id
        metal_ids.append(new_id)
        metal_names.append(cm.name)
        metal_charges[new_id] = cm.charge
        total_metals[new_id] = cm.total
        metal_idx += 1

    ligand_reindex: Dict[str, str] = {}
    ligand_ids: List[str] = []
    ligand_names: List[str] = []
    ligand_charges: Dict[str, int] = {}
    total_ligands: Dict[str, float | str] = {}
    ligand_idx = 1
    for cm in ligand_list:
        old_id = cm.internal_id
        if cm.db_id.startswith("ligand_10076"):
            # OH- — keep original
            ligand_reindex[cm.db_id] = old_id
            continue
        new_id = f"L{ligand_idx}"
        ligand_reindex[cm.db_id] = new_id
        cm.internal_id = new_id
        ligand_ids.append(new_id)
        ligand_names.append(cm.name)
        ligand_charges[new_id] = cm.charge
        total_ligands[new_id] = cm.total
        ligand_idx += 1

    # Update per-report remaps to use final unified IDs
    for i, report in enumerate(reports):
        remap = remaps[i]
        for cm in report.component_meta:
            if cm.comp_type == "metal":
                remap[cm.internal_id] = metal_reindex.get(cm.db_id, cm.internal_id)
            elif cm.comp_type == "ligand":
                remap[cm.internal_id] = ligand_reindex.get(cm.db_id, cm.internal_id)

    unified_meta = metal_list + ligand_list

    return (
        unified_meta,
        remaps,
        total_metals,
        total_ligands,
        metal_ids,
        ligand_ids,
        metal_names,
        ligand_names,
        metal_charges,
        ligand_charges,
    )
