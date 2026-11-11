"""System-catalog normalizer  (system_catalog_normalizer.py)
============================================================

Reconcile the LC1-derived ``system_catalog`` with the LC2 free-energy
card before it is folded into the calc-input card.

Why this exists
---------------
LC1 enumerates a chemical system's metals together with *every* plausible
oxidation state of each element (e.g. copper -> ``Cu$+3``, ``Cu$+2``,
``Cu$+1``).  LC2 then builds the free-energy card from the species that
actually carry NIST SRD46 thermodynamic data, which is usually a strict
subset (copper glycine systems realise only ``Cu$+2`` / ``Cu$+1`` /
``Cu(0)``).  The numeric solver's
``constraint_compiler.validate_catalog_against_report`` is strict in both
directions and rejects a catalog that declares a metal valence (or
ligand) the card never realises::

    ConstraintCompileError: system_catalog declares entries not in card:
        metals=['Cu$+3'] ligands=[]

This module prunes those phantom entries so the catalog is always a
subset of the card the solver consumes.  It only ever *removes* entries
that the card does not contain, so it can never change the meaning of a
constraint (a constraint can only reference species present in the card).

Public API
----------
``prune_system_catalog_to_report(system_catalog, report)`` -> ``list[str]``
    In-place prune; returns human-readable notes describing each drop.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set


def _report_id_sets(report: Any) -> "tuple[Set[str], Set[str]]":
    """Return ``(metal_ids, ligand_ids)`` present in the card.

    Mirrors ``validate_catalog_against_report``: ``report.metal_ids`` /
    ``report.ligand_ids`` carry the card's *internal_ids* (e.g.
    ``Cu$+2``, ``L1``); the reserved ``M0`` / ``L0`` placeholders
    (H+/OH-) are excluded.
    """
    rep_m = {m for m in (getattr(report, "metal_ids", []) or []) if m != "M0"}
    rep_l = {L for L in (getattr(report, "ligand_ids", []) or []) if L != "L0"}
    return rep_m, rep_l


def prune_system_catalog_to_report(system_catalog: Dict[str, Any],
                                   report: Any) -> List[str]:
    """In-place: drop catalog entries the free-energy card never realises.

    Removes, from ``system_catalog.chemical_system``:

      * metal ``redox_states`` not present in ``report.metal_ids`` (the
        common case: a phantom high oxidation state such as ``Cu$+3``);
      * whole metal entries whose element is absent from the card and
        whose ``redox_states`` all pruned away;
      * ligand entries whose ``internal_id`` is absent from
        ``report.ligand_ids``.

    The mutation keeps the catalog a strict subset of the card so the
    solver's ``validate_catalog_against_report`` accepts it.  Returns a
    list of notes describing every drop (empty when already a subset).
    """
    notes: List[str] = []
    cs = system_catalog.get("chemical_system")
    if not isinstance(cs, dict):
        return notes

    rep_m, rep_l = _report_id_sets(report)

    # ── metals: prune phantom redox states (and empty metal entries) ──
    metals_in = cs.get("metals") or []
    metals_out: List[Any] = []
    for m in metals_in:
        if not isinstance(m, dict):
            metals_out.append(m)
            continue
        states = m.get("redox_states")
        if isinstance(states, list) and states:
            kept = [s for s in states if s in rep_m]
            dropped = [s for s in states if s not in rep_m]
            if dropped:
                label = m.get("name") or m.get("element") or "metal"
                notes.append(
                    f"pruned redox_states {dropped} from metal "
                    f"{label!r} (absent from card)")
                m["redox_states"] = kept
            states = kept
        # Drop a metal that contributes nothing the card realises: no
        # surviving redox state and no element/internal_id match.
        iid = m.get("internal_id")
        elem = m.get("element")
        contributes = bool(states) or (iid in rep_m) or (elem in rep_m)
        if not contributes:
            label = m.get("name") or elem or iid or "metal"
            notes.append(f"dropped metal {label!r} (absent from card)")
            continue
        metals_out.append(m)
    if metals_out != metals_in:
        cs["metals"] = metals_out

    # ── ligands: prune entries absent from the card ──────────────────
    ligands_in = cs.get("ligands") or []
    ligands_out: List[Any] = []
    for L in ligands_in:
        if not isinstance(L, dict):
            ligands_out.append(L)
            continue
        iid = L.get("internal_id")
        # Keep when the card realises this ligand, or when we cannot tell
        # (no internal_id to compare) -- never drop on missing metadata.
        if iid is None or iid in rep_l:
            ligands_out.append(L)
        else:
            label = L.get("name") or L.get("db_id") or iid
            notes.append(f"dropped ligand {label!r} (absent from card)")
    if ligands_out != ligands_in:
        cs["ligands"] = ligands_out

    return notes
