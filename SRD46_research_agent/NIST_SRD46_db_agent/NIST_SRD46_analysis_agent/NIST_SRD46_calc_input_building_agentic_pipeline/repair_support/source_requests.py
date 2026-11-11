"""Bind an LC2 reviewer's source objection to exact existing card entries."""
from __future__ import annotations
import json
import re
from typing import Any, Mapping, Sequence

from .contracts import BroaderReviewRequired, canonical_sha256


def source_repair_bindings(card_text: str, inventory) -> dict[str, dict[str, Any]]:
    from card_management_helpers.free_energy_md_card_reader import parse_free_energy_card_md
    from LC2_free_energy_card_building.LC2_2_card_db_merger._md_card_merge_core.reference_alignment import _parse_stoich
    from LC2_free_energy_card_building.LC2_2_card_db_merger._md_card_merge_core.species_unifier import _phase_bucket
    from .lc2_delta import _rows, _source
    parsed = parse_free_energy_card_md(card_text)
    ids = {cm.internal_id: cm.db_id for cm in parsed.component_meta}
    rows = {(row.data["label"], _source(row.data)): row.data for row in _rows(card_text)}
    bindings = {}
    for entry in inventory:
        if entry.source != "SRD-46":
            continue
        row = rows.get((entry.label, entry.source))
        if row is None:
            raise BroaderReviewRequired("SRD-46 inventory entry is absent from its declared card", entry_key=entry.entry_key)
        if entry.species_id and entry.species_id != row["species_id"]:
            raise BroaderReviewRequired("SRD-46 inventory species_id differs from its declared card row", entry_key=entry.entry_key)
        if _phase_bucket(entry.phase) != _phase_bucket(row["phase"]):
            raise BroaderReviewRequired("SRD-46 inventory phase differs from its declared card row", entry_key=entry.entry_key)
        stoich = _parse_stoich(row["stoich"])
        metal_ids = {ids[key] for key in stoich if ids.get(key, "").startswith("metal_") and ids[key] != "metal_68"}
        ligand_ids = {ids[key] for key in stoich if ids.get(key, "").startswith("ligand_") and ids[key] != "ligand_10076"}
        if not metal_ids and ligand_ids:
            metal_ids = {"metal_68"}
        if metal_ids and not ligand_ids:
            ligand_ids = {"ligand_10076"}
        pairs = sorted(f"{metal}_{ligand}" for metal in metal_ids for ligand in ligand_ids)
        if not pairs:
            continue
        source_text = row.get("calc_source", "") + " " + row.get("additional_notes", "")
        bindings[entry.entry_key] = {
            "pair_keys": pairs, "source_record_ids": sorted(set(re.findall(r"vlm_\d+(?:_patched)?", source_text))),
            "source": entry.source, "species_id": entry.species_id, "label": entry.label,
            "row_identity": {"phase": row["phase"], "source": entry.source, "label": entry.label},
            "source_row": row, "source_row_sha256": canonical_sha256(row),
        }
    return bindings


def validate_source_request(payload: Mapping[str, Any], bindings: Mapping[str, Any],
                            blocking_errors: Sequence[str] = ()) -> dict[str, Any]:
    """Return only evidence-bound diagnostics; model-supplied replacement data are forbidden."""
    if not isinstance(payload, Mapping):
        raise ValueError("Source repair payload must be an object")
    if set(payload) - {"entry_keys", "reason"}:
        raise ValueError("Only entry_keys and reason are permitted; do not supply replacement values or pair IDs")
    keys = payload.get("entry_keys")
    if not isinstance(keys, list) or not keys or not all(isinstance(key, str) for key in keys):
        raise ValueError("entry_keys must be a nonempty list of exact bound entry keys")
    if len(keys) != len(set(keys)) or any(key not in bindings for key in keys):
        raise ValueError("Every entry must have an exact SRD-46 source binding")
    reason = payload.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("Explain the source defect; this is not permission to change chemistry")
    if blocking_errors:
        raise ValueError("Complete the outstanding group reviews before accepting unaffected decisions")
    selected = {key: bindings[key] for key in keys}
    pairs = sorted({pair for row in selected.values() for pair in row["pair_keys"]})
    return {"schema_version": 1, "error_code": "reviewer_source_objection",
            "repair_scope": "source_selection", "message": reason.strip(), "pair_keys": pairs,
            "pair_key": pairs[0] if len(pairs) == 1 else None,
            "issue_key": pairs[0] if len(pairs) == 1 else "+".join(pairs),
            "entry_keys": keys, "source_bindings": selected,
            "unchanged_decisions_accepted": True}
