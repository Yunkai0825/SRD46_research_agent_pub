"""Stage-4 orchestrator: assemble, validate, and publish support eq_map."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..runtime_support.artifacts import (
    mkdir,
    read_bytes,
    read_text,
    write_json,
)
from ..parse_speciation_answer.candidate_schema import ParsedQuery
from ..parse_speciation_answer.srd46_catalog import Catalog
from .support_eq_map_assembler import assemble_support_eq_map
from .support_eq_map_validator import validate_support_eq_map
from .session_working_map import (
    build_session_working_map,
    validate_session_working_map,
)


class SupportEqMapMaterializationError(RuntimeError):
    """Structured stage-4 failure suitable for bounded parser repair."""

    def __init__(
        self,
        *,
        error: str,
        cause_type: str,
        parser_correctable: bool,
        query_id: str | None,
        pair_scope: dict[str, int] | None,
        fix_hints: list[str],
    ) -> None:
        super().__init__(error)
        self.error = error
        self.cause_type = cause_type
        self.parser_correctable = parser_correctable
        self.query_id = query_id
        self.pair_scope = pair_scope
        self.fix_hints = fix_hints

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage": "validate_support_eq_map",
            "query_id": self.query_id,
            "pair_scope": self.pair_scope,
            "error": self.error,
            "fix_hints": list(self.fix_hints),
            "parser_correctable": self.parser_correctable,
            "cause_type": self.cause_type,
        }


@dataclass
class SupportEqMapResult:
    status: str
    support_eq_map_path: str | None
    empty_support_eq_map_path: str | None
    manifest_path: str
    audit: dict[str, Any]
    support_eq_map_sha256: str
    session_working_map_path: str | None = None
    session_working_map_sha256: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "support_eq_map_path": self.support_eq_map_path,
            "empty_support_eq_map_path": self.empty_support_eq_map_path,
            "manifest_path": self.manifest_path,
            "audit": self.audit,
            "support_eq_map_sha256": self.support_eq_map_sha256,
            "session_working_map_path": self.session_working_map_path,
            "session_working_map_sha256": self.session_working_map_sha256,
        }


def _digest_payload(value: Any) -> str:
    raw = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _failure_context(
    exc: Exception,
    parsed_queries: list[ParsedQuery],
    document: dict[str, list[dict[str, Any]]] | None = None,
) -> tuple[str | None, dict[str, int] | None]:
    message = str(exc)
    query_id: str | None = None
    match = re.search(r"\b(q\d+)\b", message)
    if match is not None:
        query_id = match.group(1)
    inferred_pair: dict[str, int] | None = None
    if document is not None and query_id is None:
        metadata = {
            str(row.get("key")): str(row.get("value"))
            for row in document.get("eq_export_metadata", [])
            if isinstance(row, dict)
        }
        node_ids: set[int] = set()
        node_match = re.search(r"eq_node(?:\[|\s)(-?\d+)", message)
        if node_match is not None:
            node_ids.add(int(node_match.group(1)))
        network_match = re.search(r"eq_network(?:\[|\s)(-?\d+)", message)
        if network_match is not None:
            network_id = int(network_match.group(1))
            node_ids.update(
                int(row["node_db_id"])
                for row in document.get("eq_node", [])
                if int(row.get("network_db_id", 0)) == network_id
            )
        map_match = re.search(r"eq_map(?:\[|\s)(-?\d+)", message)
        if map_match is not None:
            map_id = int(map_match.group(1))
            network_ids = {
                int(row["network_db_id"])
                for row in document.get("eq_network", [])
                if int(row.get("map_id", 0)) == map_id
            }
            node_ids.update(
                int(row["node_db_id"])
                for row in document.get("eq_node", [])
                if int(row.get("network_db_id", 0)) in network_ids
            )
        inferred_queries: set[str] = set()
        inferred_pairs: set[tuple[int, int]] = set()
        nodes_by_id = {
            int(row["node_db_id"]): row
            for row in document.get("eq_node", [])
        }
        for node_id in node_ids:
            node = nodes_by_id.get(node_id)
            if node is not None:
                inferred_pairs.add((int(node["metal_id"]), int(node["ligand_id"])))
            try:
                provenance = json.loads(
                    metadata[f"estimated_node.{node_id}.provenance"]
                )
            except (KeyError, TypeError, json.JSONDecodeError):
                continue
            candidate = str(provenance.get("query_id") or "").strip()
            if candidate:
                inferred_queries.add(candidate)
        if len(inferred_queries) == 1:
            query_id = next(iter(inferred_queries))
        if len(inferred_pairs) == 1:
            metal_id, ligand_id = next(iter(inferred_pairs))
            inferred_pair = {"metal_id": metal_id, "ligand_id": ligand_id}
    pair_match = re.search(r"metal_(\d+)/ligand_(\d+)", message)
    if pair_match is not None:
        inferred_pair = {
            "metal_id": int(pair_match.group(1)),
            "ligand_id": int(pair_match.group(2)),
        }
        if query_id is None:
            matching_queries = [
                query.query_id
                for query in parsed_queries
                if int(query.scope.get("metal_id", -1)) == inferred_pair["metal_id"]
                and int(query.scope.get("ligand_id", -1)) == inferred_pair["ligand_id"]
            ]
            if len(matching_queries) == 1:
                query_id = matching_queries[0]
    if query_id is None and len(parsed_queries) == 1:
        query_id = parsed_queries[0].query_id
    selected = next(
        (query for query in parsed_queries if query.query_id == query_id),
        None,
    )
    if selected is None:
        return query_id, inferred_pair
    try:
        return query_id, {
            "metal_id": int(selected.scope["metal_id"]),
            "ligand_id": int(selected.scope["ligand_id"]),
        }
    except (KeyError, TypeError, ValueError):
        return query_id, None


def _materialization_error(
    exc: Exception,
    *,
    parsed_queries: list[ParsedQuery],
    phase: str,
    document: dict[str, list[dict[str, Any]]] | None = None,
) -> SupportEqMapMaterializationError:
    query_id, pair_scope = _failure_context(
        exc,
        parsed_queries,
        document=document,
    )
    message = str(exc)
    candidate_markers = (
        "query scope",
        "evidence authorization",
        "parsed pair",
        "parsed estimate",
        "canonical",
        "beta_def",
        "beta definition",
        "species topology",
        "temperature",
        "ionic strength",
        "condition",
        "disconnected",
        "evidence",
        "query-answer digest",
    )
    marker_match = any(
        marker in message.lower() for marker in candidate_markers
    )
    if phase == "persistence":
        parser_correctable = False
    elif phase == "assembly":
        parser_correctable = marker_match or (
            query_id is not None
            and isinstance(exc, (KeyError, TypeError, ValueError))
        )
    else:
        parser_correctable = marker_match
    if parser_correctable:
        fix_hints = [
            "Re-emit only the failing pair using the closed parsed-speciation schema.",
            "Copy canonical pair IDs, beta definition, equation, and node species exactly from read-only SRD46 receipts.",
            "Preserve the query evidence-authorization snapshot and requested conditions.",
        ]
    else:
        fix_hints = [
            "Do not ask the parser to invent replacement relational IDs or map rows.",
            "Inspect deterministic assembler/storage infrastructure before retrying.",
        ]
    return SupportEqMapMaterializationError(
        error=message,
        cause_type=f"{phase}:{type(exc).__name__}",
        parser_correctable=parser_correctable,
        query_id=query_id,
        pair_scope=pair_scope,
        fix_hints=fix_hints,
    )


def run_validate_support_eq_map(
    *,
    parsed_queries: list[ParsedQuery],
    base_eq_map_card: dict[str, Any],
    output_dir: str | Path,
    session_id: str,
    request_T_C: float | None = None,
    request_I_M: float | None = None,
    catalog: Catalog | None = None,
) -> SupportEqMapResult:
    """Hard-code the complete native support map; no LLM runs here."""

    root = Path(output_dir)
    stage_dir = root / "support_eq_map"
    mkdir(stage_dir, parents=True, exist_ok=True)
    base_digest = _digest_payload(base_eq_map_card)
    try:
        document, provenance = assemble_support_eq_map(
            parsed_queries=parsed_queries,
            session_id=session_id,
            base_eq_map_sha256=base_digest,
            request_T_C=request_T_C,
            request_I_M=request_I_M,
        )
    except Exception as exc:
        raise _materialization_error(
            exc,
            parsed_queries=parsed_queries,
            phase="assembly",
        ) from exc
    try:
        audit = (
            validate_support_eq_map(document)
            if catalog is None
            else validate_support_eq_map(document, catalog=catalog)
        )
    except Exception as exc:
        raise _materialization_error(
            exc,
            parsed_queries=parsed_queries,
            phase="validation",
            document=document,
        ) from exc
    audit["base_eq_map_sha256"] = base_digest
    audit["provenance_nodes"] = len(provenance)
    path = stage_dir / "srd46_query_estimated_support_eq_map.json"
    write_json(path, document)
    persisted = json.loads(read_text(path, encoding="utf-8"))
    try:
        persisted_audit = (
            validate_support_eq_map(persisted)
            if catalog is None
            else validate_support_eq_map(persisted, catalog=catalog)
        )
    except Exception as exc:
        raise _materialization_error(
            exc,
            parsed_queries=parsed_queries,
            phase="persistence",
            document=persisted,
        ) from exc
    if persisted_audit["n_nodes"] != audit["n_nodes"]:
        raise RuntimeError("persisted support eq_map differs from validated in-memory map")
    published_path: str | None = str(path) if audit["n_nodes"] else None
    empty_path: str | None = str(path) if not audit["n_nodes"] else None
    support_eq_map_sha256 = hashlib.sha256(read_bytes(path)).hexdigest()
    session_working_map_path: str | None = None
    session_working_map_sha256: str | None = None
    working_map_audit: dict[str, Any] | None = None
    if audit["n_nodes"]:
        # This is deliberately after native schema/canonical identity/graph
        # validation.  LC2 never sees parser output that skipped those gates.
        try:
            working_map = build_session_working_map(
                base_eq_map_card=base_eq_map_card,
                support_document=document,
            )
            working_map_audit = validate_session_working_map(
                working_map,
                base_eq_map_card=base_eq_map_card,
                support_document=document,
            )
        except Exception as exc:
            raise _materialization_error(
                exc,
                parsed_queries=parsed_queries,
                phase="working_map",
                document=document,
            ) from exc
        working_path = stage_dir / "session_working_eq_map.json"
        write_json(working_path, working_map)
        persisted_working_map = json.loads(
            read_text(working_path, encoding="utf-8")
        )
        try:
            persisted_working_audit = validate_session_working_map(
                persisted_working_map,
                base_eq_map_card=base_eq_map_card,
                support_document=persisted,
            )
        except Exception as exc:
            raise _materialization_error(
                exc,
                parsed_queries=parsed_queries,
                phase="persistence",
                document=persisted,
            ) from exc
        if persisted_working_audit != working_map_audit:
            raise RuntimeError(
                "persisted session working map differs from validated in-memory map"
            )
        session_working_map_path = str(working_path)
        session_working_map_sha256 = hashlib.sha256(
            read_bytes(working_path)
        ).hexdigest()
        audit["session_working_map"] = working_map_audit
    manifest = {
        "stage": "validate_support_eq_map",
        "status": "ok" if audit["n_nodes"] else "no_estimation",
        "source": "SRD46 query estimated values",
        "authoritative": False,
        "request_temperature_C": request_T_C,
        "request_ionic_strength_M": request_I_M,
        "support_eq_map_path": published_path,
        "empty_support_eq_map_path": empty_path,
        "support_eq_map_sha256": support_eq_map_sha256,
        "session_working_map_path": session_working_map_path,
        "session_working_map_sha256": session_working_map_sha256,
        "session_working_map_audit": working_map_audit,
        "audit": audit,
    }
    manifest_path = root / "04_validate_support_eq_map_manifest.json"
    write_json(manifest_path, manifest)
    return SupportEqMapResult(
        status=manifest["status"],
        support_eq_map_path=published_path,
        empty_support_eq_map_path=empty_path,
        manifest_path=str(manifest_path),
        audit=audit,
        support_eq_map_sha256=support_eq_map_sha256,
        session_working_map_path=session_working_map_path,
        session_working_map_sha256=session_working_map_sha256,
    )


__all__ = [
    "SupportEqMapMaterializationError",
    "SupportEqMapResult",
    "run_validate_support_eq_map",
]
