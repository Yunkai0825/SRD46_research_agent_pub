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
        # Session-relative path of the QueryAgent answer bound by the
        # parser; omitted when the map has no recorded path.
        **(
            {"query_answer_path": str(provenance["query_answer_path"])}
            if provenance.get("query_answer_path") else {}
        ),
        "evidence_authorization_context_id": provenance.get(
            "evidence_authorization_context_id"
        ),
        "evidence_authorization_sha256": provenance.get(
            "evidence_authorization_sha256"
        ),
    }


ESTIMATED_TAG = "estimated"


def estimated_source_label(records: Iterable[Mapping[str, Any]]) -> str:
    """The card's source cell for a session-estimated species.

    ``estimated: <answer.md path>`` names the QueryAgent answer file(s) the
    estimate came from (several joined with ``; ``); without a recorded
    path the legacy ``ESTIMATED_SOURCE`` label is kept.
    """

    paths: list[str] = []
    for record in records:
        path = str(record.get("query_answer_path") or "").strip()
        if path and path not in paths:
            paths.append(path)
    if not paths:
        return ESTIMATED_SOURCE
    return f"{ESTIMATED_TAG}: " + "; ".join(paths)


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
        # The marker lives in a Markdown table cell and every card reader
        # splits rows on "|"; the parser's prose holds Markdown tables, so
        # the pipe is written as its JSON escape (same text after loads).
        marker = marker.replace("|", "\\u007c")
        prior = str(getattr(species, "additional_notes", "") or "").strip()
        species.additional_notes = f"{prior}; {marker}".strip("; ")
        species.source = estimated_source_label(used)
        species.source_record_id = ", ".join(
            record["source_database_ID"] for record in used
        )
    return report


__all__ = [
    "ESTIMATED_TAG",
    "decorate_report_with_estimated_provenance",
    "estimated_source_label",
]
