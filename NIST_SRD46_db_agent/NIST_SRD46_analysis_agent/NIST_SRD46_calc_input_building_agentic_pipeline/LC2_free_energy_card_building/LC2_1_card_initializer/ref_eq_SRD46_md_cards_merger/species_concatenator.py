"""species_concatenator.py
Concatenate and deduplicate species and equilibrium metadata
across multiple FreeEnergyReports.

Nothing is dropped based on data source — every distinct species is
merged.  Only repeated copies of the same remapped species identity and
thermodynamic payload are deduplicated (e.g. an Fe–OH or H–Citrate
dependency shared between cards).  Distinct phases may have identical
bulk stoichiometry, charge, and phase class and must remain separate.

Species IDs follow the ref-eq card convention: dot-separated
bracket-tokenized component keys (e.g. ``[Fe$+3].[L2].[z+0]``).  When a
component is re-indexed during the merge, the species_id is rebuilt by
substituting the remapped component key in each bracket token.
"""
from __future__ import annotations

import copy
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── path bootstrapping ──────────────────────────────────────────
_THIS = Path(__file__).absolute()
_CALC_ROOT = _THIS.parents[3]                       # calc-input-building pipeline
if str(_CALC_ROOT) not in sys.path:
    sys.path.insert(0, str(_CALC_ROOT))

from thermodynamics_helpers.gibbs_value_calc_from_logK_eq_map_helpers.free_energy_network_calc_helper import (
    FreeEnergyReport,
    SpeciesEnergy,
    EquilibriumMeta,
)


# ═══════════════════════════════════════════════════════════════════
#  Stoichiometry remapping
# ═══════════════════════════════════════════════════════════════════

_HXL_KEY_RE = re.compile(r'^H(-?\d*)(L\d+)$')   # H-1L1, H2L2, HL1


def remap_stoich(
    stoich: Dict[str, int],
    remap: Dict[str, str],
) -> Dict[str, int]:
    """Apply component remap to a stoichiometry dict."""
    result: Dict[str, int] = {}
    for key, val in stoich.items():
        new_key = remap.get(key, key)
        result[new_key] = result.get(new_key, 0) + val
    if result.get("H") == 0:
        result.pop("H", None)
    return result


def remap_stoich_hlx(
    stoich_hlx: Optional[List[Tuple[str, int]]],
    remap: Dict[str, str],
) -> Optional[List[Tuple[str, int]]]:
    """Apply component remap to stoich_hlx tuples.

    Handles compound HxLy keys (e.g. ``'H-1L1'``) by decomposing,
    remapping the ligand portion, and reconstructing.
    """
    if stoich_hlx is None:
        return None
    result = []
    for key, count in stoich_hlx:
        m = _HXL_KEY_RE.match(key)
        if m:
            h_part, lig = m.group(1), m.group(2)
            new_lig = remap.get(lig, lig)
            new_key = f"H{h_part}{new_lig}"
            result.append((new_key, count))
        else:
            new_key = remap.get(key, key)
            result.append((new_key, count))
    return result


# ═══════════════════════════════════════════════════════════════════
#  Dedup helpers
# ═══════════════════════════════════════════════════════════════════

def stoich_signature(stoich: Dict[str, int]) -> str:
    """Canonical string for dedup comparison."""
    return "|".join(f"{k}:{v}" for k, v in sorted(stoich.items()))



# ═══════════════════════════════════════════════════════════════════
#  Species concatenation
# ═══════════════════════════════════════════════════════════════════

def _frame_tag(t_c: object, rank: int, tags_collide: bool) -> str:
    """Human-readable frame tag for a duplicate copy's label.

    T is rounded to whole degrees: card temperatures are re-derived from
    the stored 2.303RT factor, so 25 C comes back as e.g. 24.9467 C.
    """
    base = f"@{round(t_c):g}C" if isinstance(t_c, (int, float)) else "@?C"
    return f"{base}#{rank}" if tags_collide else base


def _dup_species_id(sid: str, rank: int) -> str:
    """Append a ``.dup<rank>`` token (kept before any ``(s)`` suffix so the
    md tokenizer/detokenizer round-trips it as an opaque component)."""
    if sid.endswith("(s)"):
        return f"{sid[:-3]}.dup{rank}(s)"
    return f"{sid}.dup{rank}"


def concatenate_species(
    reports: List[FreeEnergyReport],
    remaps: List[Dict[str, str]],
    provenances: Optional[List[Dict[str, object]]] = None,
) -> Tuple[List[SpeciesEnergy], List[Dict[str, object]]]:
    """Merge species from all reports, dropping only repeated copies.

    At this stage nothing is dropped based on data source — every
    distinct species is preserved.  A remapped ``species_id`` identifies
    a species (including parser-assigned suffixes for polymorphs with the
    same formula).  An identical repeated dependency is collapsed.

    Conflicting payloads under one remapped identity — typically the same
    SRD-46 hydroxide backbone imported by several pair cards whose card
    frames differ (majority-vote data temperatures, e.g. 20 °C vs 25 °C)
    — are ALL kept: ids gain ``.dup<n>`` suffixes, labels gain ``@<T>C``
    frame tags (so the downstream ``(label, source)`` join key stays
    unique), and each copy's ``additional_notes`` gets a compact token
    ``[srd_<set> r/n frame|data]``.  Full provenance (base id, vlm
    chain, source card, T, I, 2.303RT) is returned in the collision
    records — persisted by the orchestrator as ``srd_srd_duplicates
    .json`` — so the card itself stays low-noise for downstream agents
    while LC2_3/LC2_4 gates can still certify twin sets automatically.

    Returns ``(species, collisions)``.
    """
    if provenances is None:
        provenances = [
            {
                "card": f"card_{i + 1:02d}",
                "T_C": getattr(report, "temperature_C", None),
                "I_M": getattr(report, "ionic_strength", None),
                "factor": getattr(report, "factor", None),
            }
            for i, report in enumerate(reports)
        ]

    order: List[Tuple[str, int, str]] = []
    entries: Dict[Tuple[str, int, str], List[Dict[str, object]]] = {}

    for i, report in enumerate(reports):
        remap = remaps[i]
        prov = provenances[i]
        for se in report.species:
            new_se = copy.deepcopy(se)
            new_se.stoich = remap_stoich(new_se.stoich, remap)
            new_se.stoich_hlx = remap_stoich_hlx(new_se.stoich_hlx, remap)

            # Rebuild species_id from remapped stoich
            old_parts = new_se.species_id.split(".")
            new_parts = []
            for part in old_parts:
                # Try to remap the base key
                remapped = False
                for old_key, new_key in remap.items():
                    if old_key == new_key:
                        continue
                    if part.startswith(old_key):
                        new_parts.append(part.replace(old_key, new_key, 1))
                        remapped = True
                        break
                if not remapped:
                    new_parts.append(part)
            new_se.species_id = ".".join(new_parts)

            identity = (new_se.species_id, new_se.charge, new_se.phase)
            fingerprint = (
                new_se.label,
                tuple(sorted(new_se.stoich.items())),
                new_se.vlm_id,
                new_se.log_beta,
                new_se.app_log_beta,
                new_se.mu0_free,
                new_se.mu0_canonical,
                new_se.mu_aligned,
                new_se.include,
            )
            if identity not in entries:
                entries[identity] = []
                order.append(identity)
            entries[identity].append(
                {"fp": fingerprint, "se": new_se, "prov": prov}
            )

    all_species: List[SpeciesEnergy] = []
    collisions: List[Dict[str, object]] = []

    for identity in order:
        # Collapse exact repeats (identical fingerprint), keeping first.
        uniq: List[Dict[str, object]] = []
        seen_fp: set = set()
        for entry in entries[identity]:
            if entry["fp"] in seen_fp:
                continue
            seen_fp.add(entry["fp"])
            uniq.append(entry)

        if len(uniq) == 1:
            all_species.append(uniq[0]["se"])
            continue

        # Divergent payloads share one identity: keep every copy, tagged.
        def _rank_key(entry: Dict[str, object]) -> Tuple[float, float, str]:
            se = entry["se"]
            t = entry["prov"].get("T_C")
            t_val = float(t) if isinstance(t, (int, float)) else float("-inf")
            return (-se.log_beta, -t_val, str(entry["prov"].get("card", "")))

        ranked = sorted(uniq, key=_rank_key)
        n = len(ranked)
        t_tags = [entry["prov"].get("T_C") for entry in ranked]
        tags_collide = len({f"{round(t):g}" if isinstance(t, (int, float))
                            else "?" for t in t_tags}) < n

        base_sid, charge, phase = identity
        vlm_ids = {entry["se"].vlm_id for entry in ranked}
        log_betas = {entry["se"].log_beta for entry in ranked}
        kind = "frame" if len(vlm_ids) == 1 and len(log_betas) == 1 else "data"

        copies_record: List[Dict[str, object]] = []
        set_id = f"srd_{len(collisions) + 1}"
        for rank, entry in enumerate(ranked, 1):
            se = entry["se"]
            prov = entry["prov"]
            t_c = prov.get("T_C")
            i_m = prov.get("I_M")
            factor = prov.get("factor")
            se.species_id = _dup_species_id(base_sid, rank)
            se.label = f"{se.label} {_frame_tag(t_c, rank, tags_collide)}"
            # Compact in-card token only; full provenance (base, vlm,
            # card, T, I, 2.303RT) lives in srd_srd_duplicates.json.
            marker = f"[{set_id} {rank}/{n} {kind}]"
            prior = (se.additional_notes or "").strip()
            se.additional_notes = f"{prior}; {marker}" if prior else marker
            all_species.append(se)
            copies_record.append({
                "species_id": se.species_id,
                "label": se.label,
                "card": prov.get("card"),
                "T_C": t_c,
                "I_M": i_m,
                "factor_2303RT": factor,
                "vlm_id": se.vlm_id,
                "log_beta": se.log_beta,
                "mu0_canonical": se.mu0_canonical,
                "mu_aligned": se.mu_aligned,
            })

        collisions.append({
            "set_id": set_id,
            "identity": {
                "species_id": base_sid,
                "charge": charge,
                "phase": phase,
            },
            "kind": kind,
            "copies": copies_record,
        })

    return all_species, collisions


# ═══════════════════════════════════════════════════════════════════
#  Equilibrium meta concatenation
# ═══════════════════════════════════════════════════════════════════

def concatenate_eq_meta(
    reports: List[FreeEnergyReport],
) -> List[EquilibriumMeta]:
    """Merge equilibrium metadata, deduplicating by db_id (vlm_id)."""
    seen_vlm: set = set()
    merged: List[EquilibriumMeta] = []
    for report in reports:
        for em in report.equilibrium_meta:
            if em.db_id in seen_vlm:
                continue
            seen_vlm.add(em.db_id)
            merged.append(copy.deepcopy(em))
    return merged
