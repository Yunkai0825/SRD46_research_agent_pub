"""Carry native support provenance across the legacy report boundary."""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping

from .support_loader import ESTIMATED_SOURCE


def _entry_record(entry: Mapping[str, Any]) -> dict[str, Any]:
    reference = entry.get("reference") or {}
    patch_notes = entry.get("patch_notes") or {}
    provenance = patch_notes.get("provenance") or {}
    return {
        "source": ESTIMATED_SOURCE,
        "source_database_ID": str(reference.get("source_database_ID") or ""),
        "beta_definition_id": patch_notes.get("beta_definition_id"),
        "beta_definition_name": patch_notes.get("beta_definition_name"),
        "session_node_db_id": patch_notes.get("session_node_db_id"),
        "session_vlm_id": patch_notes.get("session_vlm_id"),
        "evidence_vlm_ids": list(provenance.get("evidence_vlm_ids") or []),
        "evidence_network_ids": list(provenance.get("evidence_network_ids") or []),
        "evidence_citation_ids": list(provenance.get("evidence_citation_ids") or []),
        "estimation_method": provenance.get("estimation_method"),
        "uncertainty_log10": provenance.get("uncertainty_log10"),
        "assumptions": list(provenance.get("assumptions") or []),
        "rationale": provenance.get("rationale"),
        "query_id": provenance.get("query_id"),
        "query_answer_sha256": provenance.get("query_answer_sha256"),
        "evidence_authorization_context_id": provenance.get(
            "evidence_authorization_context_id"
        ),
        "evidence_authorization_sha256": provenance.get(
            "evidence_authorization_sha256"
        ),
    }


def decorate_report_with_estimated_provenance(
    report: Any,
    estimated_entries: Iterable[Mapping[str, Any]],
) -> Any:
    """Mark species whose cumulative-beta chain uses a support eq_node.

    The existing free-energy calculator keeps the source record IDs in the
    cumulative chain but has no field for arbitrary equilibrium metadata.
    This enabled-only adapter attaches the native provenance after numerical
    conversion and serializes it into ``additional_notes`` for the MD reader.
    """

    records = {
        record["source_database_ID"]: record
        for record in (_entry_record(entry) for entry in estimated_entries)
        if record["source_database_ID"]
    }
    for species in getattr(report, "species", []):
        chain_ids = {
            value.strip()
            for value in str(getattr(species, "vlm_id", "") or "").split(",")
            if value.strip()
        }
        used = [records[value] for value in sorted(chain_ids & set(records))]
        if not used:
            continue
        marker = json.dumps(
            {"source": ESTIMATED_SOURCE, "eq_nodes": used},
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        prior = str(getattr(species, "additional_notes", "") or "").strip()
        species.additional_notes = f"{prior}; {marker}".strip("; ")
        species.source = ESTIMATED_SOURCE
        species.source_record_id = ", ".join(
            record["source_database_ID"] for record in used
        )
    return report


__all__ = ["decorate_report_with_estimated_provenance"]
