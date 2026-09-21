"""
LC2_3 dedup — decision apply (post-LLM).
=========================================

This is the *post-LLM* half of the LC2_3 deterministic engine.  Given a
set of per-group keep decisions (produced by the LLM pathways in
``_pair_dedup_subagent``) it maps them onto species and edits the merged
card markdown.

LC2_3 does **not** re-merge anything.  LC2_2 has already produced the
final merged card (``free_energy_card.md``) and a companion report
(``deduplication_check.md``) that enumerates every core-stoichiometry
group.  The *pre-LLM* half (group splitting + payload building) lives in
:mod:`.group_dispatch`.

One concept governs everything here: **a deduplication decision is made
per core-stoichiometry group** (``(phase, core_label)``).  A decision
lists the source-qualified species identities, ``(name, source)``, that
survive; everybody else in the group is excluded.

Join key
--------
The report's ``species`` value equals the card's Section-5 ``label`` and
the report ``source`` equals the card ``source`` ("SRD-46" / "Atlas").
A species is therefore uniquely identified across the card by the pair
``(name, source)`` — phase-independent — which is exactly the key the
card editor matches on.

Public surface
--------------
* :class:`GroupDecision`          — keep decision for one group.
* :func:`decisions_from_dicts`    — parse raw decision dicts.
* :func:`compute_drop_keys`       — decisions → dropped ``(name, source)``.
* :func:`apply_decisions_to_card` — write the deduplicated card text.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path as _Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

# ── path bootstrap: import LC2's shared card-format helpers as a bare
#    top-level package (lives in the pipeline root), never via the heavy
#    NIST_SRD46_analysis_agent package __init__ chain. ──────────────────
_PIPELINE_ROOT = _Path(__file__).absolute().parents[3]
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from card_management_helpers.dedup_md_card_reader import DedupReport
from card_management_helpers.free_energy_md_card_editor import (
    EditRow,
    SpeciesKey,
    exclude_species,
)

log = logging.getLogger("Analysis.LC2_3.apply")


# ════════════════════════════════════════════════════════════════════
#  Decision
# ════════════════════════════════════════════════════════════════════

@dataclass
class GroupDecision:
    """Per-group keep decision.

    ``keep_species`` lists exact ``(name, source)`` pairs matching the
    report and card.  ``keep_names`` is a compatibility field for old
    persisted decisions; it is accepted only when every selected name
    resolves to exactly one species in the group.
    """
    phase:      str
    core_label: str
    keep_names: Optional[List[str]] = None
    rationale:  str = ""
    keep_species: Optional[List[SpeciesKey]] = None

    @property
    def key(self) -> Tuple[str, str]:
        return (self.phase, self.core_label)


# ════════════════════════════════════════════════════════════════════
#  Decision parsing + drop computation
# ════════════════════════════════════════════════════════════════════

def decisions_from_dicts(raw: Iterable[Dict[str, Any]]) -> List[GroupDecision]:
    """Build :class:`GroupDecision` objects from raw dicts (e.g. the LLM
    pathway outputs).

    New decisions must use ``keep_species`` objects containing both
    ``name`` and ``source``.  Legacy ``keep_names`` decisions remain
    readable, but ambiguity is checked against the report later by
    :func:`compute_drop_keys`.
    """
    out: List[GroupDecision] = []
    for d in raw or []:
        if not isinstance(d, dict):
            continue
        try:
            has_qualified = "keep_species" in d
            has_legacy = "keep_names" in d
            if has_qualified and has_legacy:
                raise ValueError(
                    "decision cannot contain both keep_species and keep_names"
                )
            if not has_qualified and not has_legacy:
                raise ValueError(
                    "decision must contain keep_species (or legacy keep_names)"
                )

            keep_species: Optional[List[SpeciesKey]] = None
            keep_names: Optional[List[str]] = None
            if has_qualified:
                raw_species = d["keep_species"]
                if not isinstance(raw_species, list):
                    raise ValueError("keep_species must be a list")
                keep_species = []
                for item in raw_species:
                    if not isinstance(item, dict):
                        raise ValueError(
                            "each keep_species item must be an object"
                        )
                    name = item.get("name")
                    source = item.get("source")
                    if not isinstance(name, str) or not isinstance(source, str):
                        raise ValueError(
                            "each keep_species item requires string name and source"
                        )
                    keep_species.append((name, source))
            else:
                raw_names = d["keep_names"]
                if not isinstance(raw_names, list) or not all(
                    isinstance(name, str) for name in raw_names
                ):
                    raise ValueError("keep_names must be a list of strings")
                keep_names = list(raw_names)

            out.append(GroupDecision(
                phase      = str(d["phase"]),
                core_label = str(d["core_label"]),
                keep_species = keep_species,
                keep_names = keep_names,
                rationale  = str(d.get("rationale", "")).strip(),
            ))
        except KeyError as exc:
            log.warning("Ignoring malformed decision %r: missing %s", d, exc)
        except ValueError as exc:
            raise ValueError(f"Invalid LC2_3 decision {d!r}: {exc}") from exc
    return out


def _resolve_keep_set(group: Any, decision: GroupDecision) -> Set[SpeciesKey]:
    """Resolve one decision to exact report identities.

    Source-qualified decisions are validated directly.  A legacy
    name-only decision is safe only when every selected name occurs once
    in the group; otherwise keeping one database row while dropping the
    other cannot be represented and execution stops loudly.
    """
    available = {(s.name, s.source) for s in group.species}

    if decision.keep_species is not None:
        keep_set = set(decision.keep_species)
        unknown = sorted(keep_set - available)
        if unknown:
            raise ValueError(
                "LC2_3 decision selects species not present in group "
                f"{group.key}: {unknown}; available={sorted(available)}"
            )
        return keep_set

    if decision.keep_names is None:
        raise ValueError(f"LC2_3 decision for group {group.key} has no keep selector")

    by_name: Dict[str, Set[SpeciesKey]] = {}
    for species_key in available:
        by_name.setdefault(species_key[0], set()).add(species_key)

    keep_set: Set[SpeciesKey] = set()
    for name in decision.keep_names:
        matches = by_name.get(name, set())
        if not matches:
            raise ValueError(
                f"Legacy LC2_3 keep_names entry {name!r} is not present "
                f"in group {group.key}"
            )
        if len(matches) != 1:
            raise ValueError(
                f"Ambiguous legacy LC2_3 keep_names entry {name!r} in group "
                f"{group.key}: matches {sorted(matches)}. Use source-qualified "
                "keep_species instead."
            )
        keep_set.update(matches)
    return keep_set


def compute_drop_keys(
    report:    DedupReport,
    decisions: Iterable[GroupDecision],
) -> Tuple[Set[SpeciesKey], Dict[SpeciesKey, str], List[Dict[str, Any]]]:
    """Map decisions onto species and compute the dropped set.

    Groups without a decision are kept intact (identity) — LC2_3 never
    drops a species unless an explicit decision says so.  Their audit mark
    is ``not examined`` rather than ``kept`` so an inherited include value
    cannot be mistaken for an agent deduplication verdict.

    Returns ``(drop_keys, notes_by_key, audit)`` where *drop_keys* is a
    set of ``(name, source)`` pairs, *notes_by_key* maps each dropped key
    to the group rationale, and *audit* lists one row per species.
    """
    by_key: Dict[Tuple[str, str], GroupDecision] = {d.key: d for d in decisions}

    drop_keys:    Set[SpeciesKey] = set()
    notes_by_key: Dict[SpeciesKey, str] = {}
    audit:        List[Dict[str, Any]] = []

    for g in report.groups:
        dec = by_key.get(g.key)
        keep_set = _resolve_keep_set(g, dec) if dec is not None else None
        for s in g.species:
            sk: SpeciesKey = (s.name, s.source)
            row = {
                "phase":         g.phase,
                "core_label":    g.core_label,
                "name":          s.name,
                "source":        s.source,
                "mu_aligned_kJ": s.mu_aligned_kJ,
                "rationale":     dec.rationale if dec else "no decision supplied",
            }
            if keep_set is None:
                row["decision"] = "not examined"
            elif sk in keep_set:
                row["decision"] = "kept"
            else:
                row["decision"] = "dropped"
                drop_keys.add(sk)
                if dec and dec.rationale:
                    notes_by_key[sk] = dec.rationale
            audit.append(row)

    log.info(
        "Dedup computed: %d dropped / %d species over %d groups (%d decisions)",
        len(drop_keys), len(audit), len(report.groups), len(by_key),
    )
    return drop_keys, notes_by_key, audit


def apply_decisions_to_card(
    card_text: str,
    report:    DedupReport,
    decisions: Iterable[GroupDecision],
) -> Tuple[str, List[Dict[str, Any]], List[EditRow]]:
    """Apply keep/drop decisions to the merged card markdown.

    Dropped species are flagged ``include = false`` in Section 5 (the
    reader treats that as an excluded species) and annotated with the
    group rationale.  No species is ever removed outright, preserving a
    full audit trail in the card.

    Returns ``(new_card_text, decision_audit, edit_audit)``.
    """
    decisions = list(decisions)
    drop_keys, notes_by_key, audit = compute_drop_keys(report, decisions)
    new_text, edit_audit = exclude_species(
        card_text, drop_keys, notes_by_key=notes_by_key,
    )
    return new_text, audit, edit_audit


__all__ = [
    "GroupDecision",
    "decisions_from_dicts",
    "compute_drop_keys",
    "apply_decisions_to_card",
]
