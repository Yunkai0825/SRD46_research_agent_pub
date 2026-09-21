"""
merger_orchestrator.py — shared LC2_2 merge helpers.
====================================================
Deterministic helper functions used by the LC2_2 external-DB merge
pipeline (``db_Pourbaix_atlas_interface.atlas_enrich_pipeline``):

  * card / valence parsing offsets and 2.303RT extraction
  * Atlas-only oxidation-state discovery + offset computation
  * Atlas species-ID generation and stoich formatting
  * pre-computation of per-species enrichment fields

This module is intentionally LLM-free and contains **no deduplication**
logic: resolving duplicate species across SRD-46 / external DBs is the
responsibility of LC2_3 (``LC2_3_card_deduplicator``).
"""
from __future__ import annotations

import logging
import math
import re
from typing import Dict, List, Optional, Set

from .species_unifier import (
    CoreGroup,
    UnifiedSpecies,
)

log = logging.getLogger("MergerOrch")

SKIP_ELEMENTS = {"C", "H", "O", "Carbon", "Hydrogen", "Oxygen"}
# Subset of SKIP_ELEMENTS that corresponds to the aqueous self-system
# (water) species H⁺/OH⁻. Excluded from the external-DB redox merge
# unless ``merge_water_species_redox`` is enabled (these species are
# pure references: H⁺ μ° ≡ 0, OH⁻ derived from Kw).
WATER_SPECIES_ELEMENTS = {"H", "O", "Hydrogen", "Oxygen"}
_RE_POURBAIX_ID = re.compile(r'^([A-Z][a-z]*)\$([+-]\d+)$')


# ======================================================================
#  Shared card-header / valence-table parsers
#  (used by every external-DB interface: db_pourbaix_atlas, db_crc_redox)
# ======================================================================

def _parse_card_metals(card_text: str) -> List[str]:
    """Extract metal names from the card header."""
    m = re.search(r"\*\*Metals\*\*:\s*(.+)", card_text)
    if not m:
        return []
    return [name.strip() for name in m.group(1).split(",") if name.strip()]


def _parse_card_valence_table(card_text: str) -> List[dict]:
    """Parse Section 2.4 Metal Valence Alignment table."""
    valences = []
    match = re.search(r"###?\s*2\.4\s+Metal\s+Valence", card_text)
    if not match:
        return valences

    block = card_text[match.end():]
    for line in block.split("\n"):
        line = line.strip()
        if not line.startswith("|"):
            if valences:
                break
            continue
        cells = [c.strip() for c in line.split("|")]
        cells = [c for c in cells if c]
        if len(cells) < 5 or cells[0] in ("element", "---"):
            continue
        if "---" in cells[0]:
            continue
        charge_text = cells[3].replace("+", "")
        try:
            charge_number = float(charge_text)
        except ValueError as exc:
            raise ValueError(
                f"valence row {cells[1]!r} has an invalid charge {cells[3]!r}") from exc
        if not math.isfinite(charge_number) or not charge_number.is_integer():
            raise ValueError(
                f"valence row {cells[1]!r} charge must be a finite integer")
        ref_text = cells[4].strip().lower()
        if ref_text not in {"true", "false"}:
            raise ValueError(
                f"valence row {cells[1]!r} is_reference must be true or false")
        valences.append({
            "element": cells[0],
            "internal_id": cells[1],
            "name": cells[2],
            "charge": int(charge_number),
            "is_reference": ref_text == "true",
        })
    return valences


def _element_from_metal_name(name: str) -> str:
    """Extract element name from metal ion name.

    Examples: 'Fe2+' -> 'Fe', 'Cu2+' -> 'Cu', '[Cu]2+' -> 'Cu'
    """
    name = name.strip()
    if name.startswith("["):
        m = re.match(r'\[([A-Za-z]+)\]', name)
        if m:
            return m.group(1)
    return re.sub(r"[\d+\-]+$", "", name)


# ======================================================================
#  Helpers
# ======================================================================

def _build_metal_info(valence_table: List[dict]) -> Dict[str, dict]:
    info: Dict[str, dict] = {}
    for row in valence_table:
        info[row["internal_id"]] = {
            "element": row["element"],
            "charge": int(str(row["charge"]).replace("+", "")),
            "name": row["name"],
        }
    return info


def _parse_2303rt(card_text: str) -> float:
    """Extract the explicitly declared positive 2.303RT value."""
    m = re.search(r"2\.303RT\s*\|\s*([+\-\d.eE]+)", card_text)
    if not m:
        raise ValueError(
            "free-energy card has no explicit 2.303RT value; LC2 merge cannot "
            "invent a reference temperature")
    value = float(m.group(1))
    if not math.isfinite(value) or value <= 0:
        raise ValueError("free-energy card 2.303RT must be finite and > 0")
    return value


# ======================================================================
#  Atlas-only oxidation state handling
# ======================================================================

def _discover_atlas_only_ids(
    grouped: Dict[str, List[CoreGroup]],
    valence_offsets: Dict[str, float],
) -> Set[str]:
    """Find metal IDs used in stoich that don't appear in valence_offsets."""
    extra_ids: Set[str] = set()
    for groups in grouped.values():
        for g in groups:
            for sp in g.species:
                for comp_id in sp.raw_stoich:
                    if comp_id in valence_offsets:
                        continue
                    if _RE_POURBAIX_ID.match(comp_id):
                        extra_ids.add(comp_id)
    return extra_ids


def _compute_atlas_only_offsets(
    extra_ids: Set[str],
    grouped: Dict[str, List[CoreGroup]],
) -> Dict[str, float]:
    """Compute valence offsets for Atlas-only oxidation states.

    For each Atlas-only metal ID, find a species containing no other metal
    valence and use its aligned energy *per target metal atom* as the
    component offset.  The per-atom normalization is essential for anchors
    such as ``Ni2O3.H2O``: its formula energy cannot be assigned to each of
    two ``Ni$+3`` components.  Mixed-valence phases are never used as an
    implicit single-valence anchor.
    """
    offsets: Dict[str, float] = {}
    for atlas_id in extra_ids:
        best_offset: Optional[float] = None
        best_rank: Optional[tuple] = None
        for phase_name, groups in grouped.items():
            for g in groups:
                for sp in g.species:
                    if sp.source != "Atlas":
                        continue
                    target_count = sp.raw_stoich.get(atlas_id, 0)
                    if target_count <= 0:
                        continue
                    metal_ids = {
                        comp_id
                        for comp_id, count in sp.raw_stoich.items()
                        if count and _RE_POURBAIX_ID.match(comp_id)
                    }
                    if metal_ids != {atlas_id}:
                        continue
                    if not math.isfinite(float(sp.mu_aligned_kJ)):
                        continue

                    non_target_components = sum(
                        1
                        for comp_id, count in sp.raw_stoich.items()
                        if count and comp_id != atlas_id
                    )
                    rank = (
                        non_target_components,
                        target_count != 1,
                        sp.multiplier,
                        phase_name != "aqueous",
                        sp.name,
                    )
                    candidate = float(sp.mu_aligned_kJ) / target_count
                    if best_rank is None or rank < best_rank:
                        best_rank = rank
                        best_offset = candidate
        if best_offset is None or not math.isfinite(best_offset):
            raise ValueError(
                f"Atlas-only valence {atlas_id!r} has no finite pure-valence "
                "anchor species"
            )
        offsets[atlas_id] = best_offset
        log.info("Atlas-only offset %s = %.4f", atlas_id, offsets[atlas_id])
    return offsets


def _build_atlas_metal_dicts(
    extra_ids: Set[str],
) -> List[Dict]:
    """Build metadata dicts for Atlas-only metals (for §2.2/2.4/3.1)."""
    metals: List[Dict] = []
    for pid in sorted(extra_ids):
        m = _RE_POURBAIX_ID.match(pid)
        if not m:
            continue
        el = m.group(1)
        chg = int(m.group(2))
        name = f"{el}({chg:+d})" if chg != 0 else f"{el}(s)"
        metals.append({
            "internal_id": pid,
            "name": name,
            "element": el,
            "charge": chg,
        })
    return metals


# ======================================================================
#  Species-ID generator for Atlas species in Section 5 notation
# ======================================================================

def _atlas_species_id(
    raw_stoich: Dict[str, int],
    charge: int,
    phase: str,
) -> str:
    """Generate a species_id from stoich, charge, and phase.

    Produces dot-separated component tokens matching the card convention:
    ``Fe$+3.OH2.z+1`` or ``Fe$+2.OH2.z+0(s)``
    """
    parts: List[str] = []
    # Order: metal/element IDs, then L*, then H
    keys = sorted(raw_stoich.keys(), key=lambda k: (
        1 if k.startswith("L") else 2 if k == "H" else 0, k))
    for k in keys:
        v = raw_stoich[k]
        if v == 0:
            continue
        if k == "H":
            if v < 0:
                oh = abs(v)
                parts.append(f"OH{oh}" if oh > 1 else "OH")
            else:
                parts.append(f"H{v}" if v > 1 else "H")
        else:
            if abs(v) > 1:
                parts.append(f"{k}({abs(v)})")
            else:
                parts.append(k)

    charge_str = f"z{charge:+d}"
    sid = ".".join(parts) + f".{charge_str}"
    if phase in ("solid", "dissolution"):
        sid += "(s)"
    return sid


def _stoich_dict_to_str(stoich: Dict[str, int]) -> str:
    """Convert stoich dict → card-style string: ``Fe$+2:+1 H:-3``."""
    keys = sorted(stoich.keys(), key=lambda k: (
        1 if k.startswith("L") else 2 if k == "H" else 0, k))
    parts = []
    for k in keys:
        v = stoich[k]
        if v == 0:
            continue
        parts.append(f"{k}:{v:+d}")
    return " ".join(parts)


# ======================================================================
#  Pre-compute enrichment fields for all unified species (for Card-3)
# ======================================================================

def _precompute_enrichment_fields(
    grouped: Dict[str, List[CoreGroup]],
    card_by_id: Dict[str, dict],
    original_id_map: Dict[str, str],
    full_offsets: Dict[str, float],
    factor_2303RT: float,
) -> None:
    """Populate extra fields on every UnifiedSpecies (mutates in place).

    After this call every species carries:
      species_id, original_id, phase, log_beta,
      mu0_free_kJ, mu0_canon_kJ, stoich_str
    in its ``extra`` dict, ready for Card-3 output.
    """
    if not math.isfinite(factor_2303RT) or factor_2303RT <= 0:
        raise ValueError("2.303RT must be explicitly declared, finite, and > 0")

    def required_card_number(card: dict, key: str, species_id: str) -> float:
        if key not in card or card[key] in (None, "", "Not defined"):
            raise ValueError(
                f"species {species_id!r} has {key}='Not defined' in the LC2 input card")
        if isinstance(card[key], bool):
            raise ValueError(f"species {species_id!r} field {key!r} cannot be boolean")
        try:
            value = float(card[key])
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"species {species_id!r} field {key!r} must be numeric") from exc
        if not math.isfinite(value):
            raise ValueError(f"species {species_id!r} field {key!r} must be finite")
        return value

    for phase_key in ("aqueous", "solid", "gas"):
        for group in grouped.get(phase_key, []):
            for sp in group.species:
                card_phase = "dissolution" if phase_key == "solid" else phase_key

                if sp.source != "Atlas":
                    sid = sp.extra.get("species_id", "")
                    if not sid or sid not in card_by_id:
                        raise ValueError(
                            f"LC2 species {sid or '<missing>'!r} has no source-card row")
                    cd = card_by_id[sid]
                    sp.extra["original_id"] = original_id_map.get(sid, sid)
                    sp.extra["phase"] = card_phase
                    sp.extra["log_beta"] = f"{required_card_number(cd, 'log_beta', sid):+.4f}"
                    sp.extra["mu0_free_kJ"] = f"{required_card_number(cd, 'mu0_free_kJ', sid):+.4f}"
                    if "mu_canon_kJ" not in sp.extra:
                        sp.extra["mu_canon_kJ"] = f"{required_card_number(cd, 'mu0_canon_kJ', sid):+.4f}"
                    if "stoich_str" not in sp.extra:
                        stoich = str(cd.get("stoich", "")).strip()
                        if not stoich or stoich == "Not defined":
                            raise ValueError(
                                f"species {sid!r} stoichiometry is Not defined")
                        sp.extra["stoich_str"] = stoich
                else:
                    # Atlas species — compute log_beta, mu values
                    shift = 0.0
                    for cid, count in sp.raw_stoich.items():
                        if _RE_POURBAIX_ID.match(cid):
                            if cid not in full_offsets:
                                raise ValueError(
                                    f"Atlas species references valence {cid!r} with no energy offset")
                            shift += count * full_offsets[cid]
                    mu_canon = sp.mu_aligned_kJ - shift
                    mu_free = mu_canon
                    log_beta = -mu_free / factor_2303RT
                    stoich_str = _stoich_dict_to_str(sp.raw_stoich)
                    sid = _atlas_species_id(sp.raw_stoich, sp.charge, card_phase)

                    sp.extra["species_id"] = sid
                    sp.extra["original_id"] = "Atlas"
                    sp.extra["phase"] = card_phase
                    sp.extra["log_beta"] = f"{log_beta:+.4f}"
                    sp.extra["mu0_free_kJ"] = f"{mu_free:+.4f}"
                    sp.extra["mu_canon_kJ"] = f"{mu_canon:+.4f}"
                    sp.extra["stoich_str"] = stoich_str

