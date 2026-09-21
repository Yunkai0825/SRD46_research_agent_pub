"""Build the session-local selection map consumed by LC2.

The native eleven-table support artefact remains the validation and provenance
authority.  This module only adapts its already-validated nodes into the
existing LC2 ``maps.json`` grammar and attaches them to a deep copy of the
selected reference pair.  It never writes to an SRD-46 database or mutates the
fetched LC1_2 card supplied by the caller.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from copy import deepcopy
from typing import Any, Mapping

from .support_eq_map_assembler import ESTIMATED_SOURCE


_EQ_SPECIES_RE = re.compile(r"\[([^\]]+)\](\^(\d+))?")
_ADAPTED_NODE_FIELDS = {
    "node_db_id",
    "vlm_id",
    "constant_type",
    "log_K",
    "temperature",
    "ionic_strength",
    "equation_python",
    "beta_definition_id",
    "beta_definition_name",
    "metal_id",
    "ligand_id",
    "LHS_species_json",
    "RHS_species_json",
    "_estimated_provenance",
}
_PAIR_REQUIRED_FIELDS = {"metal_id", "ligand_id", "selected_network_ids"}
_PAIR_ALLOWED_FIELDS = _PAIR_REQUIRED_FIELDS | {
    "vlm_overrides",
    "estimated_eq_nodes",
}


class SessionWorkingMapValidationError(ValueError):
    """A proposed session working map is not safe for LC2 consumption."""


def _fail(message: str) -> None:
    raise SessionWorkingMapValidationError(message)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _positive_id(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        _fail(f"{where} must be a positive canonical SRD46 identifier")
    return value


def _component_id(value: Any, prefix: str, where: str) -> int:
    """Accept the established flat-card integer or ``prefix_N`` spelling."""

    if isinstance(value, int) and not isinstance(value, bool):
        return _positive_id(value, where)
    match = re.fullmatch(rf"{re.escape(prefix)}_(\d+)", str(value).strip())
    if match is None or int(match.group(1)) <= 0:
        _fail(f"{where} must identify a canonical {prefix}_N")
    return int(match.group(1))


def _network_id(value: Any, where: str) -> int:
    if isinstance(value, bool):
        _fail(f"{where} must identify a canonical ref_eq_net_N")
    if isinstance(value, int):
        return _positive_id(value, where)
    match = re.fullmatch(r"ref_eq_net_(\d+)", str(value).strip())
    if match is None or int(match.group(1)) <= 0:
        _fail(f"{where} must identify a canonical ref_eq_net_N")
    return int(match.group(1))


def _base_pairs(base_eq_map_card: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return a deep-copied canonical ``pairs`` selection map.

    LC1 normally supplies its flat ``equilibrium_networks`` card.  Accepting an
    existing ``pairs`` payload too makes this boundary reusable after LC1_2
    review and, importantly, preserves any established ``vlm_overrides``.
    """

    if not isinstance(base_eq_map_card, Mapping):
        _fail("base_eq_map_card must be an object")
    if "pairs" in base_eq_map_card:
        raw_pairs = base_eq_map_card.get("pairs")
        if not isinstance(raw_pairs, list):
            _fail("base_eq_map_card.pairs must be a list")
        pairs = deepcopy(raw_pairs)
    else:
        networks = base_eq_map_card.get("equilibrium_networks", [])
        if not isinstance(networks, list):
            _fail("base_eq_map_card.equilibrium_networks must be a list")
        pairs = []
        for index, entry in enumerate(networks):
            if not isinstance(entry, Mapping):
                _fail(f"equilibrium_networks[{index}] must be an object")
            pairs.append({
                "metal_id": _component_id(
                    entry.get("metal_id"),
                    "metal",
                    f"equilibrium_networks[{index}].metal_id",
                ),
                "ligand_id": _component_id(
                    entry.get("ligand_id"),
                    "ligand",
                    f"equilibrium_networks[{index}].ligand_id",
                ),
                "selected_network_ids": [
                    _network_id(
                        entry.get("eq_network"),
                        f"equilibrium_networks[{index}].eq_network",
                    )
                ],
            })

    seen: set[tuple[int, int]] = set()
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(pairs):
        if not isinstance(raw, Mapping):
            _fail(f"pairs[{index}] must be an object")
        pair = deepcopy(dict(raw))
        metal_id = _positive_id(pair.get("metal_id"), f"pairs[{index}].metal_id")
        ligand_id = _positive_id(pair.get("ligand_id"), f"pairs[{index}].ligand_id")
        selected = pair.get("selected_network_ids")
        if not isinstance(selected, list):
            _fail(f"pairs[{index}].selected_network_ids must be a list")
        selected_ids = [
            _network_id(value, f"pairs[{index}].selected_network_ids")
            for value in selected
        ]
        if len(selected_ids) != len(set(selected_ids)):
            _fail(f"pairs[{index}].selected_network_ids contains duplicates")
        key = (metal_id, ligand_id)
        if key in seen:
            _fail(
                "working map contains duplicate pair "
                f"metal_{metal_id}/ligand_{ligand_id}"
            )
        seen.add(key)
        pair["metal_id"] = metal_id
        pair["ligand_id"] = ligand_id
        pair["selected_network_ids"] = selected_ids
        normalized.append(pair)
    return normalized


def _equation_powers(equation_python: str) -> dict[str, int]:
    powers: dict[str, int] = {}
    for match in _EQ_SPECIES_RE.finditer(equation_python):
        powers[match.group(1)] = int(match.group(3)) if match.group(3) else 1
    return powers


def _adapt_node(
    node: Mapping[str, Any],
    species_rows: list[Mapping[str, Any]],
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    """Mirror LC2's established native-node adapter without importing LC2."""

    powers = _equation_powers(str(node["equation_python"]))
    lhs: list[dict[str, Any]] = []
    rhs: list[dict[str, Any]] = []
    for species_row in sorted(
        species_rows,
        key=lambda value: (str(value["side"]), str(value["species"])),
    ):
        raw_species = str(species_row["species"])
        bare_species = (
            raw_species[1:-1]
            if raw_species.startswith("[") and raw_species.endswith("]")
            else raw_species
        )
        adapted = {
            "species": raw_species,
            "power": powers.get(bare_species, 1),
            "phase": "solid" if "(s" in raw_species else "aqueous",
        }
        (lhs if species_row["side"] == "LHS" else rhs).append(adapted)
    return {
        "node_db_id": int(node["node_db_id"]),
        "vlm_id": int(node["vlm_id"]),
        "constant_type": str(node["constant_type"]),
        "log_K": float(node["constant_value"]),
        "temperature": float(node["temperature"]),
        "ionic_strength": float(node["ionic_strength"]),
        "equation_python": str(node["equation_python"]),
        "beta_definition_id": int(node["beta_definition_id"]),
        "beta_definition_name": str(node["beta_definition_name"]),
        "metal_id": int(node["metal_id"]),
        "ligand_id": int(node["ligand_id"]),
        "LHS_species_json": lhs,
        "RHS_species_json": rhs,
        "_estimated_provenance": deepcopy(dict(provenance)),
    }


def adapted_rows_by_pair(
    support_document: Mapping[str, list[dict[str, Any]]],
) -> dict[tuple[int, int], list[dict[str, Any]]]:
    """Adapt validated native nodes into the existing LC2 row grammar."""

    metadata = {
        str(row["key"]): str(row["value"])
        for row in support_document["eq_export_metadata"]
    }
    species_by_node: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for row in support_document["eq_node_species"]:
        species_by_node[int(row["node_db_id"])].append(row)
    rows: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for node in support_document["eq_node"]:
        node_id = int(node["node_db_id"])
        key = f"estimated_node.{node_id}.provenance"
        try:
            provenance = json.loads(metadata[key])
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise SessionWorkingMapValidationError(
                f"eq_node {node_id} lacks valid estimated provenance"
            ) from exc
        pair = (int(node["metal_id"]), int(node["ligand_id"]))
        rows[pair].append(
            _adapt_node(node, species_by_node[node_id], provenance)
        )
    return {
        pair: sorted(
            pair_rows,
            key=lambda row: (
                float(row["temperature"]),
                float(row["ionic_strength"]),
                int(row["beta_definition_id"]),
                int(row["node_db_id"]),
            ),
        )
        for pair, pair_rows in sorted(rows.items())
    }


def build_session_working_map(
    *,
    base_eq_map_card: Mapping[str, Any],
    support_document: Mapping[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    """Deep-copy selected pairs and attach validated estimated nodes.

    Existing selected network IDs are retained verbatim as canonical integers.
    A support pair absent from the selected reference card is represented by the
    established ``selected_network_ids: []`` convention; no fake reference ID
    or renamed map structure is introduced.
    """

    source_snapshot = _canonical_json(base_eq_map_card)
    pairs = _base_pairs(base_eq_map_card)
    index = {
        (int(pair["metal_id"]), int(pair["ligand_id"])): pair
        for pair in pairs
    }
    for pair_key, estimated_rows in adapted_rows_by_pair(support_document).items():
        target = index.get(pair_key)
        if target is None:
            target = {
                "metal_id": pair_key[0],
                "ligand_id": pair_key[1],
                "selected_network_ids": [],
            }
            pairs.append(target)
            index[pair_key] = target
        target["estimated_eq_nodes"] = deepcopy(estimated_rows)
    if _canonical_json(base_eq_map_card) != source_snapshot:
        raise RuntimeError("base_eq_map_card changed during session-map assembly")
    return {"pairs": pairs}


def validate_session_working_map(
    document: Any,
    *,
    base_eq_map_card: Mapping[str, Any],
    support_document: Mapping[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Validate map schema, namespaces, provenance, and exact support binding."""

    if not isinstance(document, dict) or set(document) != {"pairs"}:
        _fail("session working map root must contain exactly the existing pairs field")
    pairs = document["pairs"]
    if not isinstance(pairs, list):
        _fail("session working map pairs must be a list")

    base_pairs = {
        (int(pair["metal_id"]), int(pair["ligand_id"])): pair
        for pair in _base_pairs(base_eq_map_card)
    }
    expected_rows = adapted_rows_by_pair(support_document)
    seen: set[tuple[int, int]] = set()
    estimated_pair_count = 0
    estimated_node_count = 0
    existing_patched_count = 0
    new_pair_count = 0
    for index, pair in enumerate(pairs):
        if not isinstance(pair, dict):
            _fail(f"pairs[{index}] must be an object")
        missing = _PAIR_REQUIRED_FIELDS - set(pair)
        extra = set(pair) - _PAIR_ALLOWED_FIELDS
        if missing or extra:
            _fail(
                f"pairs[{index}] has invalid fields; missing={sorted(missing)}, "
                f"extra={sorted(extra)}"
            )
        metal_id = _positive_id(pair["metal_id"], f"pairs[{index}].metal_id")
        ligand_id = _positive_id(pair["ligand_id"], f"pairs[{index}].ligand_id")
        pair_key = (metal_id, ligand_id)
        if pair_key in seen:
            _fail(f"duplicate working pair metal_{metal_id}/ligand_{ligand_id}")
        seen.add(pair_key)
        selected = pair["selected_network_ids"]
        if not isinstance(selected, list):
            _fail(f"pairs[{index}].selected_network_ids must be a list")
        selected_ids = [
            _network_id(value, f"pairs[{index}].selected_network_ids")
            for value in selected
        ]
        if len(selected_ids) != len(set(selected_ids)):
            _fail(f"pairs[{index}].selected_network_ids contains duplicates")

        base_pair = base_pairs.get(pair_key)
        if base_pair is None:
            if selected_ids:
                _fail(
                    "new session pair cannot fabricate selected reference networks for "
                    f"metal_{metal_id}/ligand_{ligand_id}"
                )
        elif selected_ids != list(base_pair["selected_network_ids"]):
            _fail(
                "session map changed the selected reference networks for "
                f"metal_{metal_id}/ligand_{ligand_id}"
            )

        rows = pair.get("estimated_eq_nodes", [])
        if not isinstance(rows, list):
            _fail(f"pairs[{index}].estimated_eq_nodes must be a list")
        expected = expected_rows.get(pair_key, [])
        if _canonical_json(rows) != _canonical_json(expected):
            _fail(
                "estimated_eq_nodes do not exactly match the validated native "
                f"support nodes for metal_{metal_id}/ligand_{ligand_id}"
            )
        if not rows:
            continue
        estimated_pair_count += 1
        estimated_node_count += len(rows)
        existing_patched_count += int(base_pair is not None)
        new_pair_count += int(base_pair is None)
        for row_index, row in enumerate(rows):
            if not isinstance(row, dict) or set(row) != _ADAPTED_NODE_FIELDS:
                _fail(
                    f"pairs[{index}].estimated_eq_nodes[{row_index}] has an "
                    "invalid adapted-node schema"
                )
            if int(row["node_db_id"]) >= 0 or int(row["vlm_id"]) >= 0:
                _fail("estimated nodes must retain negative session identifiers")
            if int(row["metal_id"]) != metal_id or int(row["ligand_id"]) != ligand_id:
                _fail("estimated node pair identity differs from its working pair")
            _positive_id(
                row["beta_definition_id"],
                f"pairs[{index}].estimated_eq_nodes[{row_index}].beta_definition_id",
            )
            provenance = row["_estimated_provenance"]
            if not isinstance(provenance, dict):
                _fail("estimated node provenance must be an object")
            if provenance.get("source") != ESTIMATED_SOURCE:
                _fail("estimated node provenance source marker is invalid")
            if int(provenance.get("session_vlm_id", 0)) != int(row["vlm_id"]):
                _fail("estimated node provenance does not bind its session VLM ID")
            if not str(provenance.get("query_id") or "").strip():
                _fail("estimated node provenance lacks query_id")

    missing_support_pairs = sorted(set(expected_rows) - seen)
    if missing_support_pairs:
        _fail(f"session working map omitted support pairs {missing_support_pairs!r}")
    return {
        "status": "ok",
        "n_pairs": len(pairs),
        "n_estimated_pairs": estimated_pair_count,
        "n_estimated_nodes": estimated_node_count,
        "n_existing_pairs_patched": existing_patched_count,
        "n_new_pairs_constructed": new_pair_count,
    }


__all__ = [
    "SessionWorkingMapValidationError",
    "adapted_rows_by_pair",
    "build_session_working_map",
    "validate_session_working_map",
]
