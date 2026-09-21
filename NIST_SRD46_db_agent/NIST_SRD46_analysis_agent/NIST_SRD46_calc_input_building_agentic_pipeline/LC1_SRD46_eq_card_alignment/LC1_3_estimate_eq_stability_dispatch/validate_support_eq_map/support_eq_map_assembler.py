"""Hard-coded conversion from parsed pair speciation to native eq-map rows."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from ..parse_speciation_answer.candidate_schema import ParsedQuery
from .native_eq_map_schema import empty_native_eq_map


ESTIMATED_SOURCE = "SRD46 query estimated values"


@dataclass
class _IdAllocator:
    collection: int = -1_000_000
    map_id: int = -2_000_000
    network: int = -3_000_000
    node: int = -4_000_000
    vlm: int = -5_000_000
    edge: int = -6_000_000

    def _next(self, name: str) -> int:
        value = getattr(self, name) - 1
        setattr(self, name, value)
        return value

    def collection_id(self) -> int:
        return self._next("collection")

    def map_db_id(self) -> int:
        return self._next("map_id")

    def network_db_id(self) -> int:
        return self._next("network")

    def node_db_id(self) -> int:
        return self._next("node")

    def vlm_id(self) -> int:
        return self._next("vlm")

    def edge_db_id(self) -> int:
        return self._next("edge")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _deduplicate_claims(
    parsed_queries: Iterable[ParsedQuery],
    *,
    request_T_C: float | None = None,
    request_I_M: float | None = None,
) -> list[dict[str, Any]]:
    by_identity: dict[tuple[Any, ...], dict[str, Any]] = {}
    for parsed in parsed_queries:
        pairs = parsed.parsed_speciation.get("chemical_pairs", [])
        if not isinstance(pairs, list) or len(pairs) != 1:
            raise ValueError(
                f"{parsed.query_id}: stage-4 input must contain exactly one pair"
            )
        if not re.fullmatch(r"[0-9a-f]{64}", str(parsed.answer_sha256)):
            raise ValueError(
                f"{parsed.query_id}: query-answer digest is missing or invalid"
            )
        snapshot = parsed.evidence_authorization
        if not isinstance(snapshot, dict):
            raise ValueError(
                f"{parsed.query_id}: evidence authorization snapshot is missing"
            )
        snapshot_digest = str(snapshot.get("snapshot_sha256") or "")
        if not re.fullmatch(r"[0-9a-f]{64}", snapshot_digest):
            raise ValueError(
                f"{parsed.query_id}: evidence authorization digest is invalid"
            )
        if not hmac.compare_digest(
            snapshot_digest,
            str(parsed.evidence_authorization_sha256 or ""),
        ):
            raise ValueError(
                f"{parsed.query_id}: parsed evidence authorization digest changed"
            )
        digest_payload = dict(snapshot)
        digest_payload.pop("snapshot_sha256", None)
        actual_snapshot_digest = hashlib.sha256(
            _canonical_json(digest_payload).encode("utf-8")
        ).hexdigest()
        if not hmac.compare_digest(snapshot_digest, actual_snapshot_digest):
            raise ValueError(
                f"{parsed.query_id}: evidence authorization snapshot does not verify"
            )
        if snapshot.get("authorization_context_id") != parsed.query_id:
            raise ValueError(
                f"{parsed.query_id}: evidence authorization belongs to another query"
            )
        snapshot_scope = snapshot.get("scope")
        if not isinstance(snapshot_scope, dict) or (
            int(snapshot_scope.get("metal_id", -1))
            != int(parsed.scope["metal_id"])
            or int(snapshot_scope.get("ligand_id", -1))
            != int(parsed.scope["ligand_id"])
        ):
            raise ValueError(
                f"{parsed.query_id}: evidence authorization scope changed"
            )
        for pair in pairs:
            actual_pair = (int(pair["metal_id"]), int(pair["ligand_id"]))
            expected_pair = (
                int(parsed.scope["metal_id"]),
                int(parsed.scope["ligand_id"]),
            )
            if actual_pair != expected_pair:
                raise ValueError(
                    f"{parsed.query_id}: parsed pair {actual_pair} does not match "
                    f"query scope {expected_pair}"
                )
            for equilibrium in pair.get("equilibria", []):
                temperature = float(equilibrium["temperature"])
                ionic_strength = float(equilibrium["ionic_strength"])
                if request_T_C is not None and not math.isclose(
                    temperature,
                    float(request_T_C),
                    rel_tol=0.0,
                    abs_tol=1e-6,
                ):
                    raise ValueError(
                        f"{parsed.query_id}: estimated temperature {temperature} "
                        f"does not match requested {float(request_T_C)}"
                    )
                if request_I_M is not None and not math.isclose(
                    ionic_strength,
                    float(request_I_M),
                    rel_tol=0.0,
                    abs_tol=1e-12,
                ):
                    raise ValueError(
                        f"{parsed.query_id}: estimated ionic strength "
                        f"{ionic_strength} does not match requested "
                        f"{float(request_I_M)}"
                    )
                identity = (
                    actual_pair[0],
                    actual_pair[1],
                    int(equilibrium["beta_definition_id"]),
                    temperature,
                    ionic_strength,
                )
                claim = {
                    "query_id": parsed.query_id,
                    "answer_sha256": parsed.answer_sha256,
                    "evidence_authorization_context_id": snapshot[
                        "authorization_context_id"
                    ],
                    "evidence_authorization_sha256": snapshot_digest,
                    "evidence_authorization": snapshot,
                    "metal_id": int(pair["metal_id"]),
                    "metal_name": pair["metal_name"],
                    "ligand_id": int(pair["ligand_id"]),
                    "ligand_name": pair["ligand_name"],
                    **equilibrium,
                }
                existing = by_identity.get(identity)
                if existing is None:
                    by_identity[identity] = claim
                    continue
                provenance_fields = {
                    "query_id",
                    "answer_sha256",
                    "evidence_authorization_context_id",
                    "evidence_authorization_sha256",
                    "evidence_authorization",
                    # The annotation is per-query interpretive provenance, not
                    # claim identity; two queries may word it differently.
                    "agent_annotation",
                }
                comparable_old = {
                    k: v for k, v in existing.items()
                    if k not in provenance_fields
                }
                comparable_new = {
                    k: v for k, v in claim.items()
                    if k not in provenance_fields
                }
                if comparable_old != comparable_new:
                    raise ValueError(
                        "conflicting parsed estimates for "
                        f"metal_{identity[0]}/ligand_{identity[1]}/"
                        f"beta_def_{identity[2]} at T={identity[3]}, I={identity[4]}"
                    )
    return [by_identity[key] for key in sorted(by_identity)]


def _claim_species(claim: dict[str, Any]) -> frozenset[str]:
    """Return the canonical species vertices carried by one beta topology."""

    return frozenset(
        str(row["species"])
        for row in claim.get("node_species", [])
        if isinstance(row, dict) and str(row.get("species") or "").strip()
    )


def _connected_claim_components(
    claims: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    """Partition claims into native networks by species-overlap connectivity.

    Native ``eq_network`` rows represent connected reaction graphs.  Sharing a
    pair and condition is enough to share an ``eq_map``, but it is not enough
    to share a network.  Components and their members retain the already
    deterministic claim order so generated IDs remain stable.
    """

    species = [_claim_species(claim) for claim in claims]
    if any(not values for values in species):
        raise ValueError("every parsed equilibrium must have canonical node_species")

    remaining = set(range(len(claims)))
    components: list[list[dict[str, Any]]] = []
    while remaining:
        seed = min(remaining)
        remaining.remove(seed)
        stack = [seed]
        component = {seed}
        while stack:
            current = stack.pop()
            neighbours = [
                candidate
                for candidate in sorted(remaining)
                if species[current] & species[candidate]
            ]
            for candidate in neighbours:
                remaining.remove(candidate)
                component.add(candidate)
                stack.append(candidate)
        components.append([claims[index] for index in sorted(component)])
    return components


def assemble_support_eq_map(
    *,
    parsed_queries: Iterable[ParsedQuery],
    session_id: str,
    base_eq_map_sha256: str,
    request_T_C: float | None = None,
    request_I_M: float | None = None,
    created_at: str | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], dict[int, dict[str, Any]]]:
    """Deterministically assemble every native table and every native field."""

    timestamp = created_at or datetime.now(timezone.utc).isoformat()
    claims = _deduplicate_claims(
        parsed_queries,
        request_T_C=request_T_C,
        request_I_M=request_I_M,
    )
    document = empty_native_eq_map()
    allocator = _IdAllocator()
    provenance_by_node: dict[int, dict[str, Any]] = {}
    authorization_by_query: dict[str, dict[str, Any]] = {}
    grouped_pairs: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for claim in claims:
        grouped_pairs[(claim["metal_id"], claim["ligand_id"])].append(claim)

    for pair_key in sorted(grouped_pairs):
        pair_claims = grouped_pairs[pair_key]
        collection_id = allocator.collection_id()
        condition_groups: dict[tuple[float, float], list[dict[str, Any]]] = defaultdict(list)
        for claim in pair_claims:
            condition_groups[(
                float(claim["temperature"]),
                float(claim["ionic_strength"]),
            )].append(claim)
        component_groups: dict[
            tuple[float, float], list[list[dict[str, Any]]]
        ] = {}
        for condition_key, raw_claims in condition_groups.items():
            ordered_claims = sorted(
                raw_claims,
                key=lambda row: int(row["beta_definition_id"]),
            )
            component_groups[condition_key] = _connected_claim_components(
                ordered_claims
            )
        document["eq_map_collection"].append({
            "collection_id": collection_id,
            "metal_id": pair_key[0],
            "ligand_id": pair_key[1],
            "metal_name": pair_claims[0]["metal_name"],
            "ligand_name": pair_claims[0]["ligand_name"],
            "total_entries": len(pair_claims),
            "total_networks": sum(
                len(components) for components in component_groups.values()
            ),
            "iterations_count": len(condition_groups),
            "unassigned_count": 0,
            "created_at": timestamp,
        })

        for map_iteration, condition_key in enumerate(sorted(condition_groups)):
            temperature, ionic_strength = condition_key
            components = component_groups[condition_key]
            condition_claims = [
                claim for component in components for claim in component
            ]
            map_id = allocator.map_db_id()
            document["eq_map"].append({
                "map_id": map_id,
                "collection_id": collection_id,
                "map_key": (
                    f"estimated_iter_{map_iteration}_T{temperature:.6g}_"
                    f"I{ionic_strength:.6g}"
                ),
                "iteration": map_iteration,
                "condition_temperature": temperature,
                "condition_ionic_strength": ionic_strength,
                "condition_temp_min": temperature,
                "condition_temp_max": temperature,
                "condition_ionic_min": ionic_strength,
                "condition_ionic_max": ionic_strength,
                "entry_count": len(condition_claims),
                "network_count": len(components),
                "stray_count": 0,
            })

            entry_index = 0
            for network_index, component_claims in enumerate(components):
                network_db_id = allocator.network_db_id()
                node_records: list[tuple[dict[str, Any], dict[str, Any]]] = []
                for claim in component_claims:
                    node_db_id = allocator.node_db_id()
                    vlm_id = allocator.vlm_id()
                    node = {
                        "node_db_id": node_db_id,
                        "network_db_id": network_db_id,
                        "vlm_id": vlm_id,
                        "entry_index": entry_index,
                        "metal_id": pair_key[0],
                        "ligand_id": pair_key[1],
                        "beta_definition_id": int(claim["beta_definition_id"]),
                        "beta_definition_name": claim["beta_definition_name"],
                        "equation_python": claim["equation_python"],
                        "constant_type": "K",
                        "constant_value": float(claim["constant_value"]),
                        "temperature": temperature,
                        "ionic_strength": ionic_strength,
                        "is_duplicate": 0,
                        "used_in_map": 1,
                    }
                    entry_index += 1
                    document["eq_node"].append(node)
                    for species_row in claim["node_species"]:
                        document["eq_node_species"].append({
                            "node_db_id": node_db_id,
                            "species": species_row["species"],
                            "side": species_row["side"],
                        })
                    provenance = {
                        "source": ESTIMATED_SOURCE,
                        "query_id": claim["query_id"],
                        "query_answer_sha256": claim["answer_sha256"],
                        "evidence_authorization_context_id": claim[
                            "evidence_authorization_context_id"
                        ],
                        "evidence_authorization_sha256": claim[
                            "evidence_authorization_sha256"
                        ],
                        "evidence_authorization_metadata_key": (
                            "query_authorization."
                            f"{claim['evidence_authorization_context_id']}"
                        ),
                        "session_vlm_id": vlm_id,
                        "topology_source": f"beta_def_{int(claim['beta_definition_id'])}",
                        "topology_resolution": claim.get("topology_resolution"),
                        "evidence_topology_diagnostics": claim.get(
                            "evidence_topology_diagnostics"
                        ),
                        "evidence_vlm_ids": [
                            f"vlm_{int(value)}" for value in claim["evidence_vlm_ids"]
                        ],
                        "evidence_network_ids": [
                            f"ref_eq_net_{int(value)}"
                            for value in claim["evidence_network_ids"]
                        ],
                        "evidence_citation_ids": [
                            f"lit_{int(value)}"
                            for value in claim["evidence_citation_ids"]
                        ],
                        "estimation_method": claim["estimation_method"],
                        "uncertainty_log10": claim["uncertainty_log10"],
                        "assumptions": claim["assumptions"],
                        "rationale": claim["rationale"],
                        "agent_annotation": claim.get("agent_annotation"),
                    }
                    provenance_by_node[node_db_id] = provenance
                    existing_authorization = authorization_by_query.get(
                        claim["query_id"]
                    )
                    if (
                        existing_authorization is not None
                        and existing_authorization != claim["evidence_authorization"]
                    ):
                        raise ValueError(
                            f"{claim['query_id']}: conflicting evidence "
                            "authorization snapshots"
                        )
                    authorization_by_query[claim["query_id"]] = claim[
                        "evidence_authorization"
                    ]
                    node_records.append((node, claim))

                edges: list[dict[str, Any]] = []
                for left_index, (left_node, left_claim) in enumerate(node_records):
                    left_species = {
                        row["species"] for row in left_claim["node_species"]
                    }
                    for right_node, right_claim in node_records[left_index + 1 :]:
                        shared = sorted(
                            left_species
                            & {
                                row["species"]
                                for row in right_claim["node_species"]
                            }
                        )
                        if not shared:
                            continue
                        edge_db_id = allocator.edge_db_id()
                        edge = {
                            "edge_db_id": edge_db_id,
                            "network_db_id": network_db_id,
                            "node1_vlm_id": left_node["vlm_id"],
                            "node2_vlm_id": right_node["vlm_id"],
                        }
                        edges.append(edge)
                        document["eq_edge"].append(edge)
                        for species in shared:
                            document["eq_edge_species"].append({
                                "edge_db_id": edge_db_id,
                                "species": species,
                            })
                network_species = sorted({
                    row["species"]
                    for _node, claim in node_records
                    for row in claim["node_species"]
                })
                document["eq_network"].append({
                    "network_db_id": network_db_id,
                    "map_id": map_id,
                    "network_id": network_index,
                    "node_count": len(node_records),
                    "edge_count": len(edges),
                })
                for species in network_species:
                    document["eq_network_species"].append({
                        "network_db_id": network_db_id,
                        "species": species,
                    })

    metadata = {
        "source": ESTIMATED_SOURCE,
        "authoritative": "false",
        "artifact_kind": "session supporting eq_map",
        "assembly": "deterministic parsed-speciation-to-native-eq-map",
        "session_id": session_id,
        "base_eq_map_sha256": base_eq_map_sha256,
    }
    if request_T_C is not None:
        metadata["request_temperature_C"] = str(float(request_T_C))
    if request_I_M is not None:
        metadata["request_ionic_strength_M"] = str(float(request_I_M))
    for key, value in metadata.items():
        document["eq_export_metadata"].append({"key": key, "value": value})
    for query_id in sorted(authorization_by_query):
        document["eq_export_metadata"].append({
            "key": f"query_authorization.{query_id}",
            "value": _canonical_json(authorization_by_query[query_id]),
        })
    for node_db_id in sorted(provenance_by_node):
        document["eq_export_metadata"].append({
            "key": f"estimated_node.{node_db_id}.provenance",
            "value": _canonical_json(provenance_by_node[node_db_id]),
        })
    return document, provenance_by_node


__all__ = ["ESTIMATED_SOURCE", "assemble_support_eq_map"]
