"""Closed structural, graph, provenance, and SRD46-identity validation."""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from typing import Any

from ..parse_speciation_answer.srd46_catalog import (
    Catalog,
    inspect_beta_definition_record,
    inspect_chemical_pair_record,
    inspect_evidence_records,
)
from ..parse_speciation_answer.evidence_gate import (
    _validate_evidence_authorization,
)
from ..parse_speciation_answer.canonical_topology import (
    validate_topology_resolution_receipt,
)
from .native_eq_map_schema import NATIVE_TABLE_COLUMNS, PRIMARY_KEYS
from .support_eq_map_assembler import ESTIMATED_SOURCE


class SupportEqMapValidationError(ValueError):
    pass


def _fail(message: str) -> None:
    raise SupportEqMapValidationError(message)


def _integer(value: Any, where: str, *, negative: bool | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(f"{where} must be INTEGER")
    if negative is True and value >= 0:
        _fail(f"{where} must be a negative session-local identifier")
    if negative is False and value <= 0:
        _fail(f"{where} must be a positive canonical SRD46 identifier")
    return value


def _finite(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(f"{where} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        _fail(f"{where} must be finite")
    return result


def _metadata_float(value: Any, where: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        _fail(f"{where} must encode a number")
    if not math.isfinite(result):
        _fail(f"{where} must be finite")
    return result


def _prefixed_positive(value: Any, prefix: str, where: str) -> int:
    match = re.fullmatch(rf"{re.escape(prefix)}_(\d+)", str(value).strip())
    if match is None or int(match.group(1)) <= 0:
        _fail(f"{where} must be a positive {prefix}_N identifier")
    return int(match.group(1))


def _validate_exact_shape(document: Any) -> None:
    if not isinstance(document, dict) or set(document) != set(NATIVE_TABLE_COLUMNS):
        _fail(
            "support eq_map top-level tables must be exactly "
            f"{sorted(NATIVE_TABLE_COLUMNS)}"
        )
    for table, columns in NATIVE_TABLE_COLUMNS.items():
        rows = document[table]
        if not isinstance(rows, list):
            _fail(f"{table} must be a list")
        for index, row in enumerate(rows):
            if not isinstance(row, dict) or set(row) != set(columns):
                _fail(
                    f"{table}[{index}] fields must be exactly {list(columns)}"
                )
        keys = PRIMARY_KEYS[table]
        seen: set[tuple[Any, ...]] = set()
        for index, row in enumerate(rows):
            pk = tuple(row[key] for key in keys)
            if pk in seen:
                _fail(f"{table}[{index}] duplicates primary key {pk!r}")
            seen.add(pk)


def validate_support_eq_map(
    document: Any,
    *,
    catalog: Catalog | None = None,
) -> dict[str, Any]:
    """Validate a deterministic support map and return a compact audit."""

    _validate_exact_shape(document)
    metadata = {row["key"]: row["value"] for row in document["eq_export_metadata"]}
    if metadata.get("source") != ESTIMATED_SOURCE:
        _fail(f"eq_export_metadata.source must be {ESTIMATED_SOURCE!r}")
    if metadata.get("authoritative") != "false":
        _fail("support eq_map must be explicitly non-authoritative")
    for required in ("artifact_kind", "assembly", "session_id", "base_eq_map_sha256"):
        if not isinstance(metadata.get(required), str) or not metadata[required]:
            _fail(f"eq_export_metadata.{required} is required")
    request_temperature: float | None = None
    request_ionic_strength: float | None = None
    if "request_temperature_C" in metadata:
        request_temperature = _metadata_float(
            metadata["request_temperature_C"],
            "eq_export_metadata.request_temperature_C",
        )
    if "request_ionic_strength_M" in metadata:
        request_ionic_strength = _metadata_float(
            metadata["request_ionic_strength_M"],
            "eq_export_metadata.request_ionic_strength_M",
        )
        if request_ionic_strength < 0:
            _fail("eq_export_metadata.request_ionic_strength_M cannot be negative")

    collections = {row["collection_id"]: row for row in document["eq_map_collection"]}
    maps = {row["map_id"]: row for row in document["eq_map"]}
    networks = {row["network_db_id"]: row for row in document["eq_network"]}
    nodes = {row["node_db_id"]: row for row in document["eq_node"]}
    edges = {row["edge_db_id"]: row for row in document["eq_edge"]}

    for collection_id, row in collections.items():
        _integer(collection_id, "eq_map_collection.collection_id", negative=True)
        _integer(row["metal_id"], "eq_map_collection.metal_id", negative=False)
        _integer(row["ligand_id"], "eq_map_collection.ligand_id", negative=False)
        if not isinstance(row["metal_name"], str) or not row["metal_name"]:
            _fail("eq_map_collection.metal_name is required")
        if not isinstance(row["ligand_name"], str) or not row["ligand_name"]:
            _fail("eq_map_collection.ligand_name is required")
        for field in ("total_entries", "total_networks", "iterations_count", "unassigned_count"):
            _integer(row[field], f"eq_map_collection.{field}")
            if row[field] < 0:
                _fail(f"eq_map_collection.{field} cannot be negative")
        if not isinstance(row["created_at"], str) or not row["created_at"]:
            _fail("eq_map_collection.created_at is required")
        pair_receipt = inspect_chemical_pair_record(
            row["metal_id"], row["ligand_id"], catalog=catalog
        )
        if pair_receipt.get("status") != "ok":
            _fail(f"unknown SRD46 chemical pair components for collection {collection_id}")
        if (
            row["metal_name"] != pair_receipt["metal_name"]
            or row["ligand_name"] != pair_receipt["ligand_name"]
        ):
            _fail(f"canonical chemical names disagree for collection {collection_id}")

    maps_by_collection: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for map_id, row in maps.items():
        _integer(map_id, "eq_map.map_id", negative=True)
        if row["collection_id"] not in collections:
            _fail(f"eq_map {map_id} has unknown collection_id")
        maps_by_collection[row["collection_id"]].append(row)
        if not isinstance(row["map_key"], str) or not row["map_key"].startswith("estimated_"):
            _fail(f"eq_map {map_id} must have an estimated session map_key")
        _integer(row["iteration"], f"eq_map[{map_id}].iteration")
        temperature = _finite(row["condition_temperature"], "condition_temperature")
        ionic = _finite(row["condition_ionic_strength"], "condition_ionic_strength")
        if ionic < 0:
            _fail(f"eq_map {map_id} ionic strength cannot be negative")
        t_min = _finite(row["condition_temp_min"], "condition_temp_min")
        t_max = _finite(row["condition_temp_max"], "condition_temp_max")
        i_min = _finite(row["condition_ionic_min"], "condition_ionic_min")
        i_max = _finite(row["condition_ionic_max"], "condition_ionic_max")
        if not (t_min <= temperature <= t_max and i_min <= ionic <= i_max):
            _fail(f"eq_map {map_id} representative conditions fall outside ranges")
        for field in ("entry_count", "network_count", "stray_count"):
            _integer(row[field], f"eq_map[{map_id}].{field}")

    networks_by_map: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for network_id, row in networks.items():
        _integer(network_id, "eq_network.network_db_id", negative=True)
        if row["map_id"] not in maps:
            _fail(f"eq_network {network_id} has unknown map_id")
        networks_by_map[row["map_id"]].append(row)
        _integer(row["network_id"], f"eq_network[{network_id}].network_id")
        _integer(row["node_count"], f"eq_network[{network_id}].node_count")
        _integer(row["edge_count"], f"eq_network[{network_id}].edge_count")

    nodes_by_network: dict[int, list[dict[str, Any]]] = defaultdict(list)
    vlm_to_node: dict[int, dict[str, Any]] = {}
    species_by_node: dict[int, set[str]] = defaultdict(set)
    sides_by_node: dict[int, set[str]] = defaultdict(set)
    for row in document["eq_node_species"]:
        if row["node_db_id"] not in nodes:
            _fail("eq_node_species references unknown node_db_id")
        if not isinstance(row["species"], str) or not row["species"]:
            _fail("eq_node_species.species is required")
        if row["side"] not in {"LHS", "RHS"}:
            _fail("eq_node_species.side must be LHS or RHS")
        species_by_node[row["node_db_id"]].add(row["species"])
        sides_by_node[row["node_db_id"]].add(row["side"])

    beta_cache: dict[int, dict[str, Any]] = {}
    provenance_by_node: dict[int, dict[str, Any]] = {}
    used_authorization_metadata_keys: set[str] = set()
    for node_id, row in nodes.items():
        _integer(node_id, "eq_node.node_db_id", negative=True)
        if row["network_db_id"] not in networks:
            _fail(f"eq_node {node_id} has unknown network_db_id")
        nodes_by_network[row["network_db_id"]].append(row)
        vlm_id = _integer(row["vlm_id"], f"eq_node[{node_id}].vlm_id", negative=True)
        if vlm_id in vlm_to_node:
            _fail(f"duplicate session vlm_id {vlm_id}")
        vlm_to_node[vlm_id] = row
        _integer(row["entry_index"], f"eq_node[{node_id}].entry_index")
        metal_id = _integer(row["metal_id"], f"eq_node[{node_id}].metal_id", negative=False)
        ligand_id = _integer(row["ligand_id"], f"eq_node[{node_id}].ligand_id", negative=False)
        beta_id = _integer(
            row["beta_definition_id"],
            f"eq_node[{node_id}].beta_definition_id",
            negative=False,
        )
        if row["constant_type"] != "K":
            _fail(f"eq_node {node_id} constant_type must be K")
        _finite(row["constant_value"], f"eq_node[{node_id}].constant_value")
        temperature = _finite(
            row["temperature"], f"eq_node[{node_id}].temperature"
        )
        ionic = _finite(row["ionic_strength"], f"eq_node[{node_id}].ionic_strength")
        if ionic < 0:
            _fail(f"eq_node {node_id} ionic strength cannot be negative")
        if request_temperature is not None and not math.isclose(
            temperature,
            request_temperature,
            rel_tol=0.0,
            abs_tol=1e-6,
        ):
            _fail(f"eq_node {node_id} temperature differs from analysis request")
        if request_ionic_strength is not None and not math.isclose(
            ionic,
            request_ionic_strength,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            _fail(f"eq_node {node_id} ionic strength differs from analysis request")
        if row["is_duplicate"] not in (0, 1) or row["used_in_map"] not in (0, 1):
            _fail(f"eq_node {node_id} flags must be SQLite 0/1 integers")
        if sides_by_node[node_id] != {"LHS", "RHS"}:
            _fail(f"eq_node {node_id} must have species on both sides")
        beta = beta_cache.setdefault(
            beta_id,
            inspect_beta_definition_record(beta_id, catalog=catalog),
        )
        if beta.get("status") != "ok":
            _fail(f"eq_node {node_id} beta_def_{beta_id} is not materializable")
        if (
            row["beta_definition_name"] != beta["beta_definition_name"]
            or row["equation_python"] != beta["equation_python"]
        ):
            _fail(f"eq_node {node_id} beta definition identity does not match SRD46")
        if sorted(
            (item["species"], item["side"]) for item in beta["node_species"]
        ) != sorted(
            (item["species"], item["side"])
            for item in document["eq_node_species"]
            if item["node_db_id"] == node_id
        ):
            _fail(f"eq_node {node_id} species topology does not match beta_def_{beta_id}")
        network = networks[row["network_db_id"]]
        map_row = maps[network["map_id"]]
        collection = collections[map_row["collection_id"]]
        if (metal_id, ligand_id) != (collection["metal_id"], collection["ligand_id"]):
            _fail(f"eq_node {node_id} chemical pair disagrees with collection")
        if (
            row["temperature"] != map_row["condition_temperature"]
            or row["ionic_strength"] != map_row["condition_ionic_strength"]
        ):
            _fail(f"eq_node {node_id} conditions disagree with eq_map")
        provenance_key = f"estimated_node.{node_id}.provenance"
        if provenance_key not in metadata:
            _fail(f"eq_node {node_id} lacks native metadata provenance")
        try:
            provenance = json.loads(metadata[provenance_key])
        except (TypeError, json.JSONDecodeError) as exc:
            _fail(f"eq_node {node_id} provenance JSON is invalid: {exc}")
        if provenance.get("source") != ESTIMATED_SOURCE:
            _fail(f"eq_node {node_id} provenance source marker is wrong")
        estimation_method = provenance.get("estimation_method")
        if not isinstance(estimation_method, str) or not estimation_method.strip():
            _fail(f"eq_node {node_id} estimation_method is required")
        uncertainty = _finite(
            provenance.get("uncertainty_log10"),
            f"eq_node[{node_id}].uncertainty_log10",
        )
        if uncertainty < 0:
            _fail(f"eq_node {node_id} uncertainty_log10 cannot be negative")
        provenance_by_node[node_id] = provenance
        if provenance.get("session_vlm_id") != vlm_id:
            _fail(f"eq_node {node_id} provenance session_vlm_id is inconsistent")
        if provenance.get("topology_source") != f"beta_def_{beta_id}":
            _fail(f"eq_node {node_id} provenance topology_source is inconsistent")
        if not isinstance(provenance.get("query_id"), str) or not provenance["query_id"]:
            _fail(f"eq_node {node_id} provenance query_id is required")
        if not re.fullmatch(r"[0-9a-f]{64}", str(provenance.get("query_answer_sha256"))):
            _fail(f"eq_node {node_id} provenance query-answer digest is invalid")
        annotation = provenance.get("agent_annotation")
        if annotation is not None:
            # Optional because gate previews are assembled before annotation;
            # when present it must be the parser's complete standalone digest.
            if not isinstance(annotation, dict):
                _fail(f"eq_node {node_id} agent_annotation must be an object")
            discussion = annotation.get("discussion")
            if not isinstance(discussion, str) or not discussion.strip():
                _fail(f"eq_node {node_id} agent_annotation discussion is empty")
            id_lists: dict[str, list[str]] = {}
            for id_key in ("core_source_ids", "secondary_source_ids"):
                values = annotation.get(id_key) or []
                if not isinstance(values, list) or any(
                    not isinstance(item, str)
                    or not re.fullmatch(r"(?:vlm|ref_eq_net|lit)_[1-9]\d*", item)
                    for item in values
                ):
                    _fail(
                        f"eq_node {node_id} agent_annotation {id_key} must be "
                        "a list of prefixed source IDs"
                    )
                id_lists[id_key] = list(values)
            if not id_lists["core_source_ids"]:
                _fail(
                    f"eq_node {node_id} agent_annotation core_source_ids is empty"
                )
            cited = (
                set(provenance.get("evidence_vlm_ids") or [])
                | set(provenance.get("evidence_network_ids") or [])
                | set(provenance.get("evidence_citation_ids") or [])
            )
            if not set(id_lists["core_source_ids"]) <= cited:
                _fail(
                    f"eq_node {node_id} agent_annotation core_source_ids cite "
                    "evidence outside the node's cited records"
                )
            if set(id_lists["core_source_ids"]) & set(
                id_lists["secondary_source_ids"]
            ):
                _fail(
                    f"eq_node {node_id} agent_annotation core and secondary "
                    "source IDs overlap"
                )
        topology_resolution = provenance.get("topology_resolution")
        has_host_topology_resolution = topology_resolution is not None
        if has_host_topology_resolution:
            try:
                validate_topology_resolution_receipt(
                    topology_resolution,
                    beta_definition_id=beta_id,
                    beta_definition_name=str(row["beta_definition_name"]),
                    equation_python=str(row["equation_python"]),
                    query_id=str(provenance.get("query_id") or ""),
                    answer_sha256=str(provenance.get("query_answer_sha256") or ""),
                )
            except Exception as exc:
                _fail(
                    f"eq_node {node_id} topology-resolution receipt is invalid: {exc}"
                )
        authorization_context_id = provenance.get(
            "evidence_authorization_context_id"
        )
        if authorization_context_id != provenance["query_id"]:
            _fail(
                f"eq_node {node_id} evidence authorization context does not "
                "match its query_id"
            )
        authorization_sha256 = str(
            provenance.get("evidence_authorization_sha256") or ""
        )
        if not re.fullmatch(r"[0-9a-f]{64}", authorization_sha256):
            _fail(
                f"eq_node {node_id} evidence authorization digest is invalid"
            )
        authorization_key = f"query_authorization.{authorization_context_id}"
        if provenance.get("evidence_authorization_metadata_key") != authorization_key:
            _fail(
                f"eq_node {node_id} evidence authorization metadata key is "
                "inconsistent"
            )
        if authorization_key not in metadata:
            _fail(
                f"eq_node {node_id} lacks its query evidence authorization snapshot"
            )
        try:
            authorization_snapshot = json.loads(metadata[authorization_key])
        except (TypeError, json.JSONDecodeError) as exc:
            _fail(
                f"eq_node {node_id} evidence authorization JSON is invalid: {exc}"
            )
        if authorization_snapshot.get("snapshot_sha256") != authorization_sha256:
            _fail(
                f"eq_node {node_id} evidence authorization digest changed during "
                "hardcoded assembly"
            )
        used_authorization_metadata_keys.add(authorization_key)
        evidence_ids = provenance.get("evidence_vlm_ids") or []
        if not evidence_ids:
            _fail(f"eq_node {node_id} requires evidence VLM IDs")
        evidence_vlm_ids = [
            _prefixed_positive(value, "vlm", "evidence_vlm_ids")
            for value in evidence_ids
        ]
        evidence_network_ids = [
            _prefixed_positive(value, "ref_eq_net", "evidence_network_ids")
            for value in provenance.get("evidence_network_ids", [])
        ]
        evidence_citation_ids = [
            _prefixed_positive(value, "lit", "evidence_citation_ids")
            for value in provenance.get("evidence_citation_ids", [])
        ]
        try:
            authorization_receipt, _authorized_vlms = (
                _validate_evidence_authorization(
                    source_pair={
                        "equilibria": [{
                            "beta_definition_id": beta_id,
                            "evidence_vlm_ids": evidence_vlm_ids,
                            "evidence_network_ids": evidence_network_ids,
                            "evidence_citation_ids": evidence_citation_ids,
                        }],
                    },
                    scope={"metal_id": metal_id, "ligand_id": ligand_id},
                    snapshot=authorization_snapshot,
                    expected_context_id=provenance["query_id"],
                    allow_analogue_topology=has_host_topology_resolution,
                )
            )
        except Exception as exc:
            _fail(
                f"eq_node {node_id} evidence authorization no longer validates: {exc}"
            )
        if authorization_receipt["snapshot_sha256"] != authorization_sha256:
            _fail(
                f"eq_node {node_id} evidence authorization receipt digest changed"
            )
        expected_topology_diagnostics = authorization_receipt[
            "validated_claims"
        ][0]
        if (
            has_host_topology_resolution
            and provenance.get("evidence_topology_diagnostics")
            != expected_topology_diagnostics
        ):
            _fail(
                f"eq_node {node_id} evidence topology diagnostics changed"
            )
        evidence = inspect_evidence_records(evidence_ids, catalog=catalog)
        if evidence.get("status") != "ok":
            _fail(f"eq_node {node_id} evidence is missing or conflicting")
        if not has_host_topology_resolution and not any(
            int(card["beta_definition_id"]) == beta_id
            for evidence_row in evidence["records"]
            for card in evidence_row.get("cards_rows", [])
        ):
            _fail(f"eq_node {node_id} evidence does not ground beta_def_{beta_id}")
        mapped_network_ids = {
            int(mapped["network_db_id"])
            for evidence_row in evidence["records"]
            for mapped in evidence_row.get("eq_node_rows", [])
            if mapped.get("network_db_id") is not None
        }
        claimed_network_ids = set(evidence_network_ids)
        if not claimed_network_ids.issubset(mapped_network_ids):
            _fail(f"eq_node {node_id} cites an unrelated equilibrium network")
        linked_citation_ids = {
            int(citation["literature_alt_id"])
            for evidence_row in evidence["records"]
            for citation in evidence_row.get("citation_rows", [])
            if citation.get("literature_alt_id") is not None
        }
        claimed_citation_ids = set(evidence_citation_ids)
        if not claimed_citation_ids.issubset(linked_citation_ids):
            _fail(f"eq_node {node_id} cites literature unrelated to its evidence VLMs")

    actual_authorization_metadata_keys = {
        key for key in metadata if key.startswith("query_authorization.")
    }
    if actual_authorization_metadata_keys != used_authorization_metadata_keys:
        _fail(
            "query evidence authorization metadata must correspond exactly to "
            "materialized support nodes"
        )

    edges_by_network: dict[int, list[dict[str, Any]]] = defaultdict(list)
    edge_species: dict[int, set[str]] = defaultdict(set)
    for row in document["eq_edge_species"]:
        if row["edge_db_id"] not in edges:
            _fail("eq_edge_species references unknown edge_db_id")
        if not isinstance(row["species"], str) or not row["species"]:
            _fail("eq_edge_species.species is required")
        edge_species[row["edge_db_id"]].add(row["species"])
    for edge_id, row in edges.items():
        _integer(edge_id, "eq_edge.edge_db_id", negative=True)
        if row["network_db_id"] not in networks:
            _fail(f"eq_edge {edge_id} has unknown network_db_id")
        edges_by_network[row["network_db_id"]].append(row)
        left = vlm_to_node.get(row["node1_vlm_id"])
        right = vlm_to_node.get(row["node2_vlm_id"])
        if left is None or right is None:
            _fail(f"eq_edge {edge_id} references unknown session VLM endpoint")
        if left["network_db_id"] != row["network_db_id"] or right["network_db_id"] != row["network_db_id"]:
            _fail(f"eq_edge {edge_id} endpoints are outside its network")
        shared = species_by_node[left["node_db_id"]] & species_by_node[right["node_db_id"]]
        if edge_species[edge_id] != shared:
            _fail(f"eq_edge {edge_id} species do not equal endpoint intersection")

    network_species: dict[int, set[str]] = defaultdict(set)
    for row in document["eq_network_species"]:
        if row["network_db_id"] not in networks:
            _fail("eq_network_species references unknown network_db_id")
        network_species[row["network_db_id"]].add(row["species"])
    for network_id, row in networks.items():
        network_nodes = nodes_by_network[network_id]
        if not network_nodes:
            _fail(f"eq_network {network_id} cannot be empty")
        if row["node_count"] != len(network_nodes):
            _fail(f"eq_network {network_id} node_count is inconsistent")
        if row["edge_count"] != len(edges_by_network[network_id]):
            _fail(f"eq_network {network_id} edge_count is inconsistent")
        node_vlms = {int(node["vlm_id"]) for node in network_nodes}
        adjacency: dict[int, set[int]] = {
            vlm_id: set() for vlm_id in node_vlms
        }
        for edge in edges_by_network[network_id]:
            left = int(edge["node1_vlm_id"])
            right = int(edge["node2_vlm_id"])
            adjacency[left].add(right)
            adjacency[right].add(left)
        reachable: set[int] = set()
        pending = [min(node_vlms)]
        while pending:
            current = pending.pop()
            if current in reachable:
                continue
            reachable.add(current)
            pending.extend(sorted(adjacency[current] - reachable))
        if reachable != node_vlms:
            _fail(
                f"eq_network {network_id} is disconnected; distinct connected "
                "components must be emitted as separate native networks"
            )
        expected_species = {
            species
            for node in network_nodes
            for species in species_by_node[node["node_db_id"]]
        }
        if network_species[network_id] != expected_species:
            _fail(f"eq_network {network_id} network species union is inconsistent")

    for map_id, row in maps.items():
        map_networks = networks_by_map[map_id]
        if row["network_count"] != len(map_networks):
            _fail(f"eq_map {map_id} network_count is inconsistent")
        local_network_ids = [int(network["network_id"]) for network in map_networks]
        if len(local_network_ids) != len(set(local_network_ids)):
            _fail(f"eq_map {map_id} has duplicate local network_id values")
        entry_count = sum(len(nodes_by_network[net["network_db_id"]]) for net in map_networks)
        if row["entry_count"] != entry_count:
            _fail(f"eq_map {map_id} entry_count is inconsistent")
        if row["stray_count"] != 0:
            _fail("generated support maps cannot contain stray measured VLM IDs")
    if document["eq_map_stray"] or document["eq_collection_unassigned"]:
        _fail("generated support maps cannot contain stray/unassigned VLM IDs")
    for collection_id, row in collections.items():
        collection_maps = maps_by_collection[collection_id]
        network_count = sum(len(networks_by_map[item["map_id"]]) for item in collection_maps)
        entry_count = sum(item["entry_count"] for item in collection_maps)
        if row["total_networks"] != network_count or row["total_entries"] != entry_count:
            _fail(f"eq_map_collection {collection_id} counts are inconsistent")
        if row["iterations_count"] != len(collection_maps) or row["unassigned_count"] != 0:
            _fail(f"eq_map_collection {collection_id} iteration/unassigned counts are inconsistent")

    pair_names = {
        (int(row["metal_id"]), int(row["ligand_id"])): (
            str(row["metal_name"]),
            str(row["ligand_name"]),
        )
        for row in collections.values()
    }
    estimated_stability_constants = []
    for row in sorted(
        nodes.values(),
        key=lambda value: (
            int(value["metal_id"]),
            int(value["ligand_id"]),
            int(value["beta_definition_id"]),
            float(value["temperature"]),
            float(value["ionic_strength"]),
        ),
    ):
        pair = (int(row["metal_id"]), int(row["ligand_id"]))
        metal_name, ligand_name = pair_names[pair]
        provenance = provenance_by_node[int(row["node_db_id"])]
        estimated_stability_constants.append({
            "metal_id": pair[0],
            "metal_name": metal_name,
            "ligand_id": pair[1],
            "ligand_name": ligand_name,
            "beta_definition_id": int(row["beta_definition_id"]),
            "beta_definition_name": str(row["beta_definition_name"]),
            "equation_python": str(row["equation_python"]),
            "constant_type": "K",
            "log10_K": float(row["constant_value"]),
            "temperature_C": float(row["temperature"]),
            "ionic_strength_M": float(row["ionic_strength"]),
            "session_vlm_id": int(row["vlm_id"]),
            "uncertainty_log10": float(provenance["uncertainty_log10"]),
            "estimation_method": str(provenance["estimation_method"]),
            "evidence_vlm_ids": list(provenance["evidence_vlm_ids"]),
            # None on gate previews; the committed path always attaches one.
            "agent_annotation": provenance.get("agent_annotation"),
            "source": ESTIMATED_SOURCE,
        })

    return {
        "status": "ok",
        "source": ESTIMATED_SOURCE,
        "n_collections": len(collections),
        "n_maps": len(maps),
        "n_networks": len(networks),
        "n_nodes": len(nodes),
        "n_edges": len(edges),
        "beta_definition_ids": sorted(beta_cache),
        "estimated_stability_constants": estimated_stability_constants,
        "pair_counts": dict(Counter(
            f"metal_{row['metal_id']}__ligand_{row['ligand_id']}"
            for row in nodes.values()
        )),
    }


__all__ = [
    "SupportEqMapValidationError",
    "validate_support_eq_map",
]
