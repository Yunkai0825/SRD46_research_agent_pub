"""Digest and lineage validation for evidence actually shown to QueryAgent."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from typing import Any, Mapping


class EvidenceGateError(ValueError):
    pass


def _ids(value: Any, where: str) -> list[int]:
    if not isinstance(value, list):
        raise EvidenceGateError(f"{where} must be a list")
    result: list[int] = []
    for item in value:
        if isinstance(item, bool):
            raise EvidenceGateError(f"{where} must contain positive integers")
        try:
            parsed = int(item)
        except (TypeError, ValueError) as exc:
            raise EvidenceGateError(
                f"{where} must contain positive integers"
            ) from exc
        if parsed <= 0:
            raise EvidenceGateError(f"{where} must contain positive integers")
        result.append(parsed)
    if len(result) != len(set(result)):
        raise EvidenceGateError(f"{where} contains duplicate identifiers")
    return result


def _index(snapshot: Mapping[str, Any], key: str, id_key: str) -> dict[int, Mapping[str, Any]]:
    rows = snapshot.get(key)
    if not isinstance(rows, list):
        raise EvidenceGateError(f"{key} must be a list")
    result: dict[int, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise EvidenceGateError(f"{key} must contain objects")
        identifier = _ids([row.get(id_key)], f"{key}.{id_key}")[0]
        if identifier in result:
            raise EvidenceGateError(f"{key} duplicates {id_key}={identifier}")
        result[identifier] = row
    return result


def validate_evidence_snapshot(
    *,
    equilibria: list[Mapping[str, Any]],
    scope: Mapping[str, Any],
    snapshot: Any,
    expected_context_id: str,
    allow_analogue_topology: bool = False,
) -> tuple[dict[str, Any], dict[int, Mapping[str, Any]]]:
    """Validate the immutable v3 receipt and every cited evidence link."""

    if not isinstance(snapshot, Mapping):
        raise EvidenceGateError("query session has no evidence receipt snapshot")
    if snapshot.get("authorization_kind") != "LC1_3 scoped evidence authorization":
        raise EvidenceGateError("unexpected evidence receipt kind")
    if snapshot.get("authorization_version") != 3:
        raise EvidenceGateError("evidence receipt must use version 3")
    claimed = str(snapshot.get("snapshot_sha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", claimed):
        raise EvidenceGateError("evidence receipt digest is missing or invalid")
    digest_payload = dict(snapshot)
    digest_payload.pop("snapshot_sha256", None)
    actual = hashlib.sha256(json.dumps(
        digest_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")).hexdigest()
    if not hmac.compare_digest(claimed, actual):
        raise EvidenceGateError("evidence receipt digest does not verify")
    if snapshot.get("authorization_context_id") != expected_context_id:
        raise EvidenceGateError("evidence receipt belongs to another query session")
    snapshot_scope = snapshot.get("scope")
    if not isinstance(snapshot_scope, Mapping) or (
        int(snapshot_scope.get("metal_id", -1)) != int(scope["metal_id"])
        or int(snapshot_scope.get("ligand_id", -1)) != int(scope["ligand_id"])
    ):
        raise EvidenceGateError("evidence receipt scope does not match the query")

    observed = {
        "vlm": set(_ids(snapshot.get("observed_vlm_ids"), "observed_vlm_ids")),
        "beta": set(_ids(
            snapshot.get("observed_beta_definition_ids"),
            "observed_beta_definition_ids",
        )),
        "network": set(_ids(
            snapshot.get("observed_network_ids"), "observed_network_ids"
        )),
        "literature": set(_ids(
            snapshot.get("observed_literature_ids"), "observed_literature_ids"
        )),
    }
    receipt_unions = {key: set() for key in observed}
    bindings: dict[str, dict[int, set[str]]] = {
        "vlm": {}, "network": {}, "literature": {}
    }
    receipts = snapshot.get("tool_receipts")
    if not isinstance(receipts, list):
        raise EvidenceGateError("tool_receipts must be a list")
    for index, row in enumerate(receipts):
        if not isinstance(row, Mapping):
            raise EvidenceGateError(f"tool_receipts[{index}] is not an object")
        digest = str(row.get("result_sha256") or "")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise EvidenceGateError(f"tool_receipts[{index}] digest is invalid")
        for kind, field in (
            ("vlm", "observed_vlm_ids"),
            ("beta", "observed_beta_definition_ids"),
            ("network", "observed_network_ids"),
            ("literature", "observed_literature_ids"),
        ):
            values = _ids(row.get(field), f"tool_receipts[{index}].{field}")
            receipt_unions[kind].update(values)
            if kind in bindings:
                for value in values:
                    bindings[kind].setdefault(value, set()).add(digest)
    if receipt_unions != observed:
        raise EvidenceGateError("observed IDs do not equal successful tool receipts")

    vlms = _index(snapshot, "vlm_records", "vlm_id")
    networks = _index(snapshot, "network_records", "network_id")
    literature = _index(snapshot, "literature_records", "literature_id")
    if set(vlms) != observed["vlm"] or set(networks) != observed["network"]:
        raise EvidenceGateError("canonical evidence records do not match observed IDs")
    if set(literature) != observed["literature"]:
        raise EvidenceGateError("canonical literature records do not match observed IDs")

    for kind, records in (("vlm", vlms), ("network", networks), ("literature", literature)):
        for identifier, row in records.items():
            receipt_hashes = set(str(value) for value in row.get("receipt_sha256s", []))
            if receipt_hashes != bindings[kind].get(identifier, set()):
                raise EvidenceGateError(
                    f"{kind}_{identifier} receipt bindings do not verify"
                )

    validated_claims: list[dict[str, Any]] = []
    for index, equilibrium in enumerate(equilibria):
        beta_id = int(equilibrium["beta_definition_id"])
        evidence_vlms = set(_ids(
            equilibrium.get("evidence_vlm_ids"),
            f"equilibria[{index}].evidence_vlm_ids",
        ))
        evidence_networks = set(_ids(
            equilibrium.get("evidence_network_ids"),
            f"equilibria[{index}].evidence_network_ids",
        ))
        evidence_citations = set(_ids(
            equilibrium.get("evidence_citation_ids"),
            f"equilibria[{index}].evidence_citation_ids",
        ))
        if beta_id not in observed["beta"]:
            raise EvidenceGateError(f"beta_def_{beta_id} was not shown by a tool")
        if not evidence_vlms:
            raise EvidenceGateError(f"equilibria[{index}] requires evidence VLMs")
        if not evidence_vlms <= observed["vlm"]:
            raise EvidenceGateError("claim cites a VLM not shown by a tool")
        topology_matching_vlms: set[int] = set()
        for vlm_id in evidence_vlms:
            row = vlms[vlm_id]
            if row.get("canonical_status") != "ok":
                raise EvidenceGateError(f"vlm_{vlm_id} is not canonical")
            if beta_id in set(_ids(
                row.get("beta_definition_ids"), f"vlm_{vlm_id}.beta IDs"
            )):
                topology_matching_vlms.add(vlm_id)
        analogue_vlms = evidence_vlms - topology_matching_vlms
        if not topology_matching_vlms and not allow_analogue_topology:
            raise EvidenceGateError(
                f"claim requires at least one cited VLM that supports "
                f"beta_def_{beta_id}"
            )
        if not evidence_networks <= observed["network"]:
            raise EvidenceGateError("claim cites a network not shown by a tool")
        for network_id in evidence_networks:
            row = networks[network_id]
            if row.get("canonical_status") != "ok" or not (
                set(_ids(row.get("vlm_ids"), f"network_{network_id}.vlm_ids"))
                & evidence_vlms
            ):
                raise EvidenceGateError(
                    f"ref_eq_net_{network_id} is not linked to cited evidence"
                )
        if not evidence_citations <= observed["literature"]:
            raise EvidenceGateError("claim cites literature not shown by a tool")
        for citation_id in evidence_citations:
            row = literature[citation_id]
            if row.get("canonical_status") != "ok" or not (
                set(_ids(row.get("vlm_ids"), f"lit_{citation_id}.vlm_ids"))
                & evidence_vlms
            ):
                raise EvidenceGateError(
                    f"lit_{citation_id} is not linked to cited evidence"
                )
        validated_claims.append({
            "equilibrium_index": index,
            "beta_definition_id": beta_id,
            "evidence_vlm_ids": sorted(evidence_vlms),
            "evidence_network_ids": sorted(evidence_networks),
            "evidence_citation_ids": sorted(evidence_citations),
            "matching_beta_vlm_ids": sorted(topology_matching_vlms),
            "analogue_vlm_ids": sorted(analogue_vlms),
            "topology_grounding": (
                "host_resolution_receipt"
                if allow_analogue_topology else "same_beta_evidence"
            ),
        })
    return ({
        "authorization_context_id": expected_context_id,
        "snapshot_sha256": claimed,
        "scope": {
            "metal_id": int(scope["metal_id"]),
            "ligand_id": int(scope["ligand_id"]),
        },
        "validated_claims": validated_claims,
    }, vlms)


# Compatibility spelling used by the native validator while it migrates.
def _validate_evidence_authorization(
    *, source_pair: Mapping[str, Any], scope: Mapping[str, Any], snapshot: Any,
    expected_context_id: str | None,
    allow_analogue_topology: bool = False,
) -> tuple[dict[str, Any], dict[int, Mapping[str, Any]]]:
    if expected_context_id is None:
        raise EvidenceGateError("expected_context_id is required")
    equilibria = source_pair.get("equilibria")
    if not isinstance(equilibria, list):
        raise EvidenceGateError("source_pair.equilibria must be a list")
    return validate_evidence_snapshot(
        equilibria=equilibria,
        scope=scope,
        snapshot=snapshot,
        expected_context_id=expected_context_id,
        allow_analogue_topology=allow_analogue_topology,
    )


__all__ = [
    "EvidenceGateError",
    "_validate_evidence_authorization",
    "validate_evidence_snapshot",
]
