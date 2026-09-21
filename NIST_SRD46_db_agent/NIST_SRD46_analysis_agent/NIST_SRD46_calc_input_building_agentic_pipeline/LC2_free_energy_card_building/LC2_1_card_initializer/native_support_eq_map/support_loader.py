"""Validate and adapt an LC1_3 full native support eq-map.

The LC1_3 artefact mirrors all eleven tables exported from the authoritative
equilibrium-map database.  It is nevertheless session supporting data: all
generated relational IDs are negative and no row is inserted into either
authoritative SRD46 database.  This module verifies that boundary and adapts
``eq_node`` rows to the exact row grammar consumed by LC2's equation builder.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Collection, Mapping

from NIST_SRD46_core_db_search_tools._db_connection import (
    get_cards_db,
    get_equilibrium_db,
)


ESTIMATED_SOURCE = "SRD46 query estimated values"

NATIVE_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "eq_map_collection": (
        "collection_id", "metal_id", "ligand_id", "metal_name", "ligand_name",
        "total_entries", "total_networks", "iterations_count", "unassigned_count",
        "created_at",
    ),
    "eq_map": (
        "map_id", "collection_id", "map_key", "iteration",
        "condition_temperature", "condition_ionic_strength",
        "condition_temp_min", "condition_temp_max",
        "condition_ionic_min", "condition_ionic_max",
        "entry_count", "network_count", "stray_count",
    ),
    "eq_network": (
        "network_db_id", "map_id", "network_id", "node_count", "edge_count",
    ),
    "eq_node": (
        "node_db_id", "network_db_id", "vlm_id", "entry_index", "metal_id",
        "ligand_id", "beta_definition_id", "beta_definition_name",
        "equation_python", "constant_type", "constant_value", "temperature",
        "ionic_strength", "is_duplicate", "used_in_map",
    ),
    "eq_node_species": ("node_db_id", "species", "side"),
    "eq_edge": ("edge_db_id", "network_db_id", "node1_vlm_id", "node2_vlm_id"),
    "eq_edge_species": ("edge_db_id", "species"),
    "eq_network_species": ("network_db_id", "species"),
    "eq_map_stray": ("map_id", "vlm_id"),
    "eq_collection_unassigned": ("collection_id", "vlm_id"),
    "eq_export_metadata": ("key", "value"),
}

PRIMARY_KEYS: dict[str, tuple[str, ...]] = {
    "eq_map_collection": ("collection_id",),
    "eq_map": ("map_id",),
    "eq_network": ("network_db_id",),
    "eq_node": ("node_db_id",),
    "eq_node_species": ("node_db_id", "species", "side"),
    "eq_edge": ("edge_db_id",),
    "eq_edge_species": ("edge_db_id", "species"),
    "eq_network_species": ("network_db_id", "species"),
    "eq_map_stray": ("map_id", "vlm_id"),
    "eq_collection_unassigned": ("collection_id", "vlm_id"),
    "eq_export_metadata": ("key",),
}

_EQ_SPECIES_RE = re.compile(r"\[([^\]]+)\](\^(\d+))?")


class NativeSupportEqMapError(ValueError):
    """The supplied document is not a safe LC1_3 native support map."""


@dataclass(frozen=True)
class LoadedNativeSupportEqMap:
    path: Path
    payload: Mapping[str, list[dict[str, Any]]]
    sha256: str
    session_id: str
    base_eq_map_sha256: str
    reviewed_base_eq_map_sha256: str
    system_catalog_pair_set_sha256: str
    allowed_system_pairs: tuple[tuple[int, int], ...]
    rows_by_pair: Mapping[tuple[int, int], tuple[dict[str, Any], ...]]
    node_count: int


def _fail(message: str) -> None:
    raise NativeSupportEqMapError(message)


def _canonical_payload_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalize_allowed_system_pairs(
    pairs: Collection[tuple[int, int]],
) -> tuple[tuple[int, int], ...]:
    """Return the active catalog pair set in a stable, validated order."""

    if isinstance(pairs, (str, bytes, bytearray)):
        _fail("allowed_system_pairs must be a collection of (metal_id, ligand_id) pairs")
    normalized: set[tuple[int, int]] = set()
    try:
        candidates = list(pairs)
    except TypeError as exc:
        raise NativeSupportEqMapError(
            "allowed_system_pairs must be a collection of (metal_id, ligand_id) pairs"
        ) from exc
    for index, pair in enumerate(candidates):
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            _fail(f"allowed_system_pairs[{index}] must be a two-item pair")
        metal_id = _integer(
            pair[0], f"allowed_system_pairs[{index}].metal_id", negative=False,
        )
        ligand_id = _integer(
            pair[1], f"allowed_system_pairs[{index}].ligand_id", negative=False,
        )
        normalized.add((metal_id, ligand_id))
    if not normalized:
        _fail("allowed_system_pairs cannot be empty when a support eq_map is supplied")
    return tuple(sorted(normalized))


def _read_document(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        value = os.path.abspath(os.fspath(path))
        if os.name == "nt" and not value.startswith("\\\\?\\"):
            if value.startswith("\\\\"):
                value = "\\\\?\\UNC\\" + value[2:]
            else:
                value = "\\\\?\\" + value
        with open(value, "rb") as handle:
            raw = handle.read()
    except OSError as exc:
        raise NativeSupportEqMapError(f"cannot read support eq_map {path}: {exc}") from exc
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NativeSupportEqMapError(f"support eq_map is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(document, dict):
        _fail("support eq_map root must be an object")
    return document, raw


def _integer(value: Any, field: str, *, negative: bool | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(f"{field} must be an integer")
    if negative is True and value >= 0:
        _fail(f"{field} must be a negative session identifier")
    if negative is False and value <= 0:
        _fail(f"{field} must be a positive canonical SRD46 identifier")
    return value


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(f"{field} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        _fail(f"{field} must be finite")
    return result


def _exact_native_shape(document: Mapping[str, Any]) -> None:
    if set(document) != set(NATIVE_TABLE_COLUMNS):
        _fail(
            "support eq_map tables must be exactly "
            f"{sorted(NATIVE_TABLE_COLUMNS)}"
        )
    for table, columns in NATIVE_TABLE_COLUMNS.items():
        rows = document[table]
        if not isinstance(rows, list):
            _fail(f"{table} must be an array")
        seen: set[tuple[Any, ...]] = set()
        for index, row in enumerate(rows):
            if not isinstance(row, dict) or set(row) != set(columns):
                _fail(f"{table}[{index}] fields must be exactly {list(columns)}")
            primary_key = tuple(row[field] for field in PRIMARY_KEYS[table])
            if primary_key in seen:
                _fail(f"{table}[{index}] duplicates primary key {primary_key!r}")
            seen.add(primary_key)


def _canonical_beta(beta_definition_id: int) -> tuple[str, str, set[tuple[str, str]]]:
    """Re-check the beta ID/name/equation/species identity at consumption."""

    with get_equilibrium_db() as conn:
        identities = conn.execute(
            """
            SELECT DISTINCT beta_definition_name, equation_python
            FROM eq_node
            WHERE beta_definition_id=? AND constant_type='K'
              AND equation_python IS NOT NULL
              AND TRIM(equation_python) NOT IN ('', '*')
            ORDER BY beta_definition_name, equation_python
            """,
            (beta_definition_id,),
        ).fetchall()
        representative = conn.execute(
            """
            SELECT node_db_id
            FROM eq_node
            WHERE beta_definition_id=? AND constant_type='K'
              AND equation_python IS NOT NULL
              AND TRIM(equation_python) NOT IN ('', '*')
            ORDER BY used_in_map DESC, is_duplicate ASC, node_db_id
            LIMIT 1
            """,
            (beta_definition_id,),
        ).fetchone()
        species = set()
        if representative is not None:
            species = {
                (str(row["species"]), str(row["side"]))
                for row in conn.execute(
                    "SELECT species, side FROM eq_node_species "
                    "WHERE node_db_id=? ORDER BY side, species",
                    (representative["node_db_id"],),
                ).fetchall()
            }
    identity_set = {
        (str(row["beta_definition_name"]), str(row["equation_python"]))
        for row in identities
    }
    if len(identity_set) != 1 or not species:
        _fail(
            f"beta_def_{beta_definition_id} has no unique materializable "
            "K-backed SRD46 identity"
        )
    name, equation = next(iter(identity_set))
    return name, equation, species


def _canonical_pair(metal_id: int, ligand_id: int) -> tuple[str, str]:
    with get_cards_db() as conn:
        metal = conn.execute(
            "SELECT metal_name_SRD FROM metal_card WHERE metal_id=?",
            (metal_id,),
        ).fetchone()
        ligand = conn.execute(
            "SELECT ligand_name_SRD FROM ligand_card WHERE ligand_id=?",
            (ligand_id,),
        ).fetchone()
    if metal is None or ligand is None:
        _fail(
            f"metal_{metal_id}/ligand_{ligand_id} does not identify canonical "
            "SRD46 components"
        )
    return str(metal["metal_name_SRD"]), str(ligand["ligand_name_SRD"])


def _prefixed_evidence_ids(
    value: Any,
    *,
    prefix: str,
    field: str,
    required: bool = False,
) -> list[int]:
    """Validate one provenance ID array without accepting coercions."""

    if not isinstance(value, list):
        _fail(f"{field} must be an array of canonical {prefix}_N IDs")
    if required and not value:
        _fail(f"{field} must contain at least one canonical {prefix}_N ID")
    ids: list[int] = []
    pattern = re.compile(rf"{re.escape(prefix)}_([1-9][0-9]*)")
    for index, raw in enumerate(value):
        if not isinstance(raw, str):
            _fail(f"{field}[{index}] must be a canonical {prefix}_N string")
        match = pattern.fullmatch(raw)
        if match is None:
            _fail(f"{field}[{index}] must be a canonical {prefix}_N string")
        ids.append(int(match.group(1)))
    if len(ids) != len(set(ids)):
        _fail(f"{field} cannot contain duplicate IDs")
    return ids


def _positive_id_array(value: Any, *, field: str) -> list[int]:
    """Validate an ordered array of unique positive canonical identifiers."""

    if not isinstance(value, list):
        _fail(f"{field} must be an array of positive canonical identifiers")
    result: list[int] = []
    for index, raw in enumerate(value):
        if isinstance(raw, bool) or not isinstance(raw, int) or raw <= 0:
            _fail(f"{field}[{index}] must be a positive canonical identifier")
        result.append(raw)
    if len(result) != len(set(result)):
        _fail(f"{field} cannot contain duplicate identifiers")
    return result


def _authorization_record_index(
    authorization: Mapping[str, Any],
    *,
    collection: str,
    id_field: str,
    node_id: int,
) -> dict[int, Mapping[str, Any]]:
    """Index one v3 observation-record array without coercing IDs."""

    rows = authorization.get(collection)
    if not isinstance(rows, list):
        _fail(f"eq_node {node_id} authorization {collection} must be an array")
    result: dict[int, Mapping[str, Any]] = {}
    for position, record in enumerate(rows):
        if not isinstance(record, dict):
            _fail(
                f"eq_node {node_id} authorization {collection}[{position}] "
                "must be an object"
            )
        record_id = record.get(id_field)
        if (
            isinstance(record_id, bool)
            or not isinstance(record_id, int)
            or record_id <= 0
            or record_id in result
        ):
            _fail(
                f"eq_node {node_id} authorization {collection} has an "
                f"invalid/duplicate {id_field}"
            )
        result[record_id] = record
    return result


def _validate_v3_canonical_observations(
    *,
    node_id: int,
    vlm_records: Mapping[int, Mapping[str, Any]],
    network_records: Mapping[int, Mapping[str, Any]],
    literature_records: Mapping[int, Mapping[str, Any]],
    cited_vlm_ids: Collection[int],
    cited_network_ids: Collection[int],
    cited_literature_ids: Collection[int],
) -> None:
    """Re-resolve v3 observation records against the canonical databases.

    Version 3 is deliberately *not* a target-pair authorization policy.  This
    routine therefore checks only whether the receipt's claimed VLM, beta,
    network, and literature relationships are real; it never classifies the
    evidence as exact-pair, same-metal, same-ligand, or an analogue.
    """

    cited_vlms = set(cited_vlm_ids)
    cited_networks = set(cited_network_ids)
    cited_literature = set(cited_literature_ids)

    with get_cards_db() as cards, get_equilibrium_db() as equilibrium:
        for vlm_id, record in vlm_records.items():
            card_rows = cards.execute(
                """
                SELECT c.metal_id, c.ligand_id, c.beta_definition_id,
                       c.beta_definition_name, s.constant_type,
                       s.constant_value, s.temperature_c AS temperature,
                       s.ionic_strength_mol_l AS ionic_strength,
                       s.equation_python
                FROM ligandmetal_card c
                JOIN ligandmetal_stability_measured s ON s.card_id=c.card_id
                WHERE c.complex_system_id=? AND s.constant_type='K'
                ORDER BY s.stability_id
                """,
                (vlm_id,),
            ).fetchall()
            node_rows = equilibrium.execute(
                """
                SELECT metal_id, ligand_id, beta_definition_id,
                       beta_definition_name, constant_type, constant_value,
                       temperature, ionic_strength, equation_python,
                       network_db_id
                FROM eq_node
                WHERE vlm_id=?
                ORDER BY node_db_id
                """,
                (vlm_id,),
            ).fetchall()
            literature_rows = cards.execute(
                """
                SELECT literature_alt_id
                FROM ref_vlm_literature_alt
                WHERE vlm_id=?
                ORDER BY literature_alt_id
                """,
                (vlm_id,),
            ).fetchall()

            metal_ids = sorted({
                int(row["metal_id"])
                for row in [*card_rows, *node_rows]
                if row["metal_id"] is not None
            })
            ligand_ids = sorted({
                int(row["ligand_id"])
                for row in [*card_rows, *node_rows]
                if row["ligand_id"] is not None
            })
            beta_ids = sorted({
                int(row["beta_definition_id"])
                for row in [*card_rows, *node_rows]
                if row["beta_definition_id"] is not None
            })
            network_ids = sorted({
                int(row["network_db_id"])
                for row in node_rows
                if row["network_db_id"] is not None
            })
            literature_ids = sorted({
                int(row["literature_alt_id"])
                for row in literature_rows
                if row["literature_alt_id"] is not None
            })
            measured_identities = {
                (
                    row["metal_id"], row["ligand_id"],
                    row["beta_definition_id"], row["beta_definition_name"],
                    row["constant_type"], row["constant_value"],
                    row["temperature"], row["ionic_strength"],
                )
                for row in card_rows
            }
            mapped_identities = {
                (
                    row["metal_id"], row["ligand_id"],
                    row["beta_definition_id"], row["beta_definition_name"],
                    row["constant_type"], row["constant_value"],
                    row["temperature"], row["ionic_strength"],
                )
                for row in node_rows
            }
            canonical_status = "ok"
            if not card_rows:
                canonical_status = "not_found"
            elif len(measured_identities) != 1:
                canonical_status = "conflict"
            elif mapped_identities and any(
                identity != next(iter(measured_identities))
                for identity in mapped_identities
            ):
                canonical_status = "conflict"
            else:
                measured_equations = {
                    row["equation_python"]
                    for row in card_rows
                    if row["equation_python"] not in (None, "", "*")
                }
                mapped_equations = {
                    row["equation_python"]
                    for row in node_rows
                    if row["equation_python"] not in (None, "", "*")
                }
                if measured_equations and mapped_equations != measured_equations:
                    canonical_status = "conflict"

            expected = {
                "canonical_status": canonical_status,
                "metal_id": metal_ids[0] if len(metal_ids) == 1 else None,
                "ligand_id": ligand_ids[0] if len(ligand_ids) == 1 else None,
                "beta_definition_ids": beta_ids,
                "network_ids": network_ids,
                "literature_ids": literature_ids,
            }
            if any(record.get(field) != value for field, value in expected.items()):
                _fail(
                    f"eq_node {node_id} observed vlm_{vlm_id} canonical record "
                    "disagrees with SRD-46"
                )
            if vlm_id in cited_vlms and canonical_status != "ok":
                _fail(
                    f"eq_node {node_id} cited vlm_{vlm_id} has no unambiguous "
                    "canonical SRD-46 record"
                )

        for network_id, record in network_records.items():
            rows = equilibrium.execute(
                """
                SELECT DISTINCT vlm_id, metal_id, ligand_id
                FROM eq_node
                WHERE network_db_id=?
                """,
                (network_id,),
            ).fetchall()
            canonical_vlms = sorted({
                int(row["vlm_id"])
                for row in rows
                if row["vlm_id"] is not None
            })
            canonical_metals = sorted({
                int(row["metal_id"])
                for row in rows
                if row["metal_id"] is not None
            })
            canonical_ligands = sorted({
                int(row["ligand_id"])
                for row in rows
                if row["ligand_id"] is not None
            })
            canonical_status = "ok" if rows else "not_found"
            if (
                record.get("canonical_status") != canonical_status
                or record.get("vlm_ids") != canonical_vlms
                or record.get("metal_ids") != canonical_metals
                or record.get("ligand_ids") != canonical_ligands
            ):
                _fail(
                    f"eq_node {node_id} observed ref_eq_net_{network_id} "
                    "canonical record disagrees with SRD-46"
                )
            if network_id in cited_networks and canonical_status != "ok":
                _fail(
                    f"eq_node {node_id} cited ref_eq_net_{network_id} has no "
                    "canonical SRD-46 record"
                )

        for literature_id, record in literature_records.items():
            rows = cards.execute(
                """
                SELECT DISTINCT rv.vlm_id, la.shortcut, la.citation
                FROM ref_vlm_literature_alt rv
                JOIN ref_literature_alt la
                  ON la.literature_alt_id=rv.literature_alt_id
                WHERE rv.literature_alt_id=?
                ORDER BY rv.vlm_id
                """,
                (literature_id,),
            ).fetchall()
            canonical_vlms = sorted({
                int(row["vlm_id"])
                for row in rows
                if row["vlm_id"] is not None
            })
            shortcuts = sorted({
                str(row["shortcut"])
                for row in rows
                if row["shortcut"] not in (None, "")
            })
            citations = sorted({
                str(row["citation"])
                for row in rows
                if row["citation"] not in (None, "")
            })
            canonical_status = "ok" if rows else "not_found"
            if (
                record.get("canonical_status") != canonical_status
                or record.get("vlm_ids") != canonical_vlms
                or record.get("shortcuts") != shortcuts
                or record.get("citations") != citations
            ):
                _fail(
                    f"eq_node {node_id} observed lit_{literature_id} canonical "
                    "record disagrees with SRD-46"
                )
            if literature_id in cited_literature and canonical_status != "ok":
                _fail(
                    f"eq_node {node_id} cited lit_{literature_id} has no "
                    "canonical SRD-46 record"
                )


def _validate_v3_observed_receipt(
    authorization: Mapping[str, Any],
    *,
    node_id: int,
    beta_definition_id: int,
    cited_vlm_ids: Collection[int],
    cited_network_ids: Collection[int],
    cited_literature_ids: Collection[int],
) -> None:
    """Validate the generic observed-tool receipt introduced by LC1_3 v3."""

    expected_fields = {
        "authorization_kind",
        "authorization_version",
        "authorization_context_id",
        "scope",
        "tool_receipts",
        "observed_vlm_ids",
        "observed_beta_definition_ids",
        "observed_network_ids",
        "observed_literature_ids",
        "vlm_records",
        "network_records",
        "literature_records",
        "snapshot_sha256",
    }
    if set(authorization) != expected_fields:
        _fail(
            f"eq_node {node_id} v3 evidence receipt fields must be exactly "
            f"{sorted(expected_fields)}"
        )

    observed = {
        "vlm": _positive_id_array(
            authorization.get("observed_vlm_ids"),
            field=f"eq_node {node_id} observed_vlm_ids",
        ),
        "beta": _positive_id_array(
            authorization.get("observed_beta_definition_ids"),
            field=f"eq_node {node_id} observed_beta_definition_ids",
        ),
        "network": _positive_id_array(
            authorization.get("observed_network_ids"),
            field=f"eq_node {node_id} observed_network_ids",
        ),
        "literature": _positive_id_array(
            authorization.get("observed_literature_ids"),
            field=f"eq_node {node_id} observed_literature_ids",
        ),
    }
    if not set(cited_vlm_ids).issubset(observed["vlm"]):
        _fail(f"eq_node {node_id} cites a VLM not observed in its tool receipts")
    if beta_definition_id not in observed["beta"]:
        _fail(
            f"eq_node {node_id} beta_def_{beta_definition_id} was not "
            "observed in its tool receipts"
        )
    if not set(cited_network_ids).issubset(observed["network"]):
        _fail(
            f"eq_node {node_id} cites a network not observed in its tool receipts"
        )
    if not set(cited_literature_ids).issubset(observed["literature"]):
        _fail(
            f"eq_node {node_id} cites literature not observed in its tool receipts"
        )

    receipts = authorization.get("tool_receipts")
    if not isinstance(receipts, list) or not receipts:
        _fail(f"eq_node {node_id} v3 tool_receipts must be a non-empty array")
    receipt_unions: dict[str, set[int]] = {
        "vlm": set(), "beta": set(), "network": set(), "literature": set(),
    }
    observed_by_receipt: dict[str, dict[int, set[str]]] = {
        kind: defaultdict(set) for kind in receipt_unions
    }
    history_indices: set[int] = set()
    for position, receipt in enumerate(receipts):
        if not isinstance(receipt, dict):
            _fail(
                f"eq_node {node_id} tool_receipts[{position}] must be an object"
            )
        expected_receipt_fields = {
            "history_index",
            "tool",
            "result_sha256",
            "observed_vlm_ids",
            "observed_beta_definition_ids",
            "observed_network_ids",
            "observed_literature_ids",
        }
        if set(receipt) != expected_receipt_fields:
            _fail(
                f"eq_node {node_id} tool_receipts[{position}] fields must be "
                f"exactly {sorted(expected_receipt_fields)}"
            )
        tool = receipt.get("tool")
        history_index = receipt.get("history_index")
        result_digest = receipt.get("result_sha256")
        if not isinstance(tool, str) or not tool.strip():
            _fail(
                f"eq_node {node_id} tool_receipts[{position}].tool is invalid"
            )
        if (
            isinstance(history_index, bool)
            or not isinstance(history_index, int)
            or history_index < 0
            or history_index in history_indices
        ):
            _fail(
                f"eq_node {node_id} tool_receipts[{position}].history_index is invalid"
            )
        history_indices.add(history_index)
        if not isinstance(result_digest, str) or not re.fullmatch(
            r"[0-9a-f]{64}", result_digest
        ):
            _fail(
                f"eq_node {node_id} tool_receipts[{position}] result digest is invalid"
            )
        receipt_fields = {
            "vlm": "observed_vlm_ids",
            "beta": "observed_beta_definition_ids",
            "network": "observed_network_ids",
            "literature": "observed_literature_ids",
        }
        for kind, field_name in receipt_fields.items():
            ids = _positive_id_array(
                receipt.get(field_name),
                field=f"eq_node {node_id} tool_receipts[{position}].{field_name}",
            )
            receipt_unions[kind].update(ids)
            for identifier in ids:
                observed_by_receipt[kind][identifier].add(result_digest)

    for kind, identifiers in observed.items():
        if receipt_unions[kind] != set(identifiers):
            _fail(
                f"eq_node {node_id} observed {kind} IDs do not equal the "
                "successful tool-receipt union"
            )

    vlm_records = _authorization_record_index(
        authorization,
        collection="vlm_records",
        id_field="vlm_id",
        node_id=node_id,
    )
    network_records = _authorization_record_index(
        authorization,
        collection="network_records",
        id_field="network_id",
        node_id=node_id,
    )
    literature_records = _authorization_record_index(
        authorization,
        collection="literature_records",
        id_field="literature_id",
        node_id=node_id,
    )
    if set(vlm_records) != set(observed["vlm"]):
        _fail(f"eq_node {node_id} observed VLM IDs lack exact v3 records")
    if set(network_records) != set(observed["network"]):
        _fail(f"eq_node {node_id} observed network IDs lack exact v3 records")
    if set(literature_records) != set(observed["literature"]):
        _fail(f"eq_node {node_id} observed literature IDs lack exact v3 records")

    def validate_lineage(
        record: Mapping[str, Any],
        *,
        kind: str,
        identifier: int,
        label: str,
    ) -> None:
        digests = record.get("receipt_sha256s")
        if (
            not isinstance(digests, list)
            or not digests
            or any(
                not isinstance(value, str)
                or not re.fullmatch(r"[0-9a-f]{64}", value)
                for value in digests
            )
            or len(digests) != len(set(digests))
            or set(digests) != observed_by_receipt[kind][identifier]
        ):
            _fail(
                f"eq_node {node_id} observed {label} lacks valid tool-result lineage"
            )

    for vlm_id, record in vlm_records.items():
        validate_lineage(record, kind="vlm", identifier=vlm_id, label=f"vlm_{vlm_id}")
        expected_record_fields = {
            "vlm_id", "canonical_status", "metal_id", "ligand_id",
            "beta_definition_ids", "network_ids", "literature_ids",
            "receipt_sha256s",
        }
        if set(record) != expected_record_fields:
            _fail(
                f"eq_node {node_id} vlm_{vlm_id} record fields are invalid"
            )
        _positive_id_array(
            record.get("beta_definition_ids"),
            field=f"eq_node {node_id} vlm_{vlm_id}.beta_definition_ids",
        )
        _positive_id_array(
            record.get("network_ids"),
            field=f"eq_node {node_id} vlm_{vlm_id}.network_ids",
        )
        _positive_id_array(
            record.get("literature_ids"),
            field=f"eq_node {node_id} vlm_{vlm_id}.literature_ids",
        )

    for network_id, record in network_records.items():
        validate_lineage(
            record,
            kind="network",
            identifier=network_id,
            label=f"ref_eq_net_{network_id}",
        )
        expected_record_fields = {
            "network_id", "canonical_status", "vlm_ids", "metal_ids",
            "ligand_ids", "receipt_sha256s",
        }
        if set(record) != expected_record_fields:
            _fail(
                f"eq_node {node_id} ref_eq_net_{network_id} record fields are invalid"
            )
        _positive_id_array(
            record.get("vlm_ids"),
            field=f"eq_node {node_id} ref_eq_net_{network_id}.vlm_ids",
        )
        _positive_id_array(
            record.get("metal_ids"),
            field=f"eq_node {node_id} ref_eq_net_{network_id}.metal_ids",
        )
        _positive_id_array(
            record.get("ligand_ids"),
            field=f"eq_node {node_id} ref_eq_net_{network_id}.ligand_ids",
        )

    for literature_id, record in literature_records.items():
        validate_lineage(
            record,
            kind="literature",
            identifier=literature_id,
            label=f"lit_{literature_id}",
        )
        expected_record_fields = {
            "literature_id", "canonical_status", "vlm_ids", "shortcuts",
            "citations", "receipt_sha256s",
        }
        if set(record) != expected_record_fields:
            _fail(
                f"eq_node {node_id} lit_{literature_id} record fields are invalid"
            )
        _positive_id_array(
            record.get("vlm_ids"),
            field=f"eq_node {node_id} lit_{literature_id}.vlm_ids",
        )
        for field_name in ("shortcuts", "citations"):
            values = record.get(field_name)
            if not isinstance(values, list) or any(
                not isinstance(value, str) or not value for value in values
            ):
                _fail(
                    f"eq_node {node_id} lit_{literature_id}.{field_name} is invalid"
                )

    cited_vlm_set = set(cited_vlm_ids)
    for network_id in cited_network_ids:
        mutually_linked = {
            vlm_id
            for vlm_id in set(network_records[network_id].get("vlm_ids") or [])
            & cited_vlm_set
            if network_id in set(vlm_records[vlm_id].get("network_ids") or [])
        }
        if not mutually_linked:
            _fail(
                f"eq_node {node_id} ref_eq_net_{network_id} is not "
                "canonically linked to a cited VLM"
            )
    for literature_id in cited_literature_ids:
        mutually_linked = {
            vlm_id
            for vlm_id in set(
                literature_records[literature_id].get("vlm_ids") or []
            ) & cited_vlm_set
            if literature_id in set(
                vlm_records[vlm_id].get("literature_ids") or []
            )
        }
        if not mutually_linked:
            _fail(
                f"eq_node {node_id} lit_{literature_id} is not canonically "
                "linked to a cited VLM"
            )

    _validate_v3_canonical_observations(
        node_id=node_id,
        vlm_records=vlm_records,
        network_records=network_records,
        literature_records=literature_records,
        cited_vlm_ids=cited_vlm_ids,
        cited_network_ids=cited_network_ids,
        cited_literature_ids=cited_literature_ids,
    )


def _validate_estimation_description(
    provenance: Mapping[str, Any], *, node_id: int,
) -> None:
    """Validate the chemistry-facing estimate description common to all versions."""

    method = provenance.get("estimation_method")
    if not isinstance(method, str) or not method.strip():
        _fail(f"eq_node {node_id} estimation_method must be a non-empty string")
    uncertainty = _finite(
        provenance.get("uncertainty_log10"),
        f"eq_node {node_id} uncertainty_log10",
    )
    if uncertainty < 0:
        _fail(f"eq_node {node_id} uncertainty_log10 cannot be negative")
    assumptions = provenance.get("assumptions")
    if not isinstance(assumptions, list) or any(
        not isinstance(value, str) or not value.strip() for value in assumptions
    ):
        _fail(
            f"eq_node {node_id} assumptions must be an array of non-empty strings"
        )
    rationale = provenance.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        _fail(f"eq_node {node_id} rationale must be a non-empty string")


def _validate_estimated_provenance(
    provenance: Any,
    *,
    node_id: int,
    session_vlm_id: int,
    metal_id: int,
    ligand_id: int,
    beta_definition_id: int,
    metadata: Mapping[str, str],
) -> Mapping[str, Any]:
    """Validate provenance types, identifiers, and canonical evidence."""

    if not isinstance(provenance, dict):
        _fail(f"eq_node {node_id} provenance must be an object")
    if provenance.get("source") != ESTIMATED_SOURCE:
        _fail(f"eq_node {node_id} provenance source marker is invalid")
    if provenance.get("session_vlm_id") != session_vlm_id:
        _fail(f"eq_node {node_id} provenance session_vlm_id disagrees")
    if provenance.get("topology_source") != f"beta_def_{beta_definition_id}":
        _fail(f"eq_node {node_id} provenance topology source disagrees")

    query_id = provenance.get("query_id")
    if not isinstance(query_id, str) or not re.fullmatch(
        r"q(?=[0-9]{3,}$)0*[1-9][0-9]*", query_id
    ):
        _fail(f"eq_node {node_id} provenance query_id is invalid")
    answer_digest = provenance.get("query_answer_sha256")
    if not isinstance(answer_digest, str) or not re.fullmatch(
        r"[0-9a-f]{64}", answer_digest
    ):
        _fail(f"eq_node {node_id} provenance query-answer digest is invalid")

    authorization_context_id = provenance.get(
        "evidence_authorization_context_id"
    )
    if authorization_context_id != query_id:
        _fail(
            f"eq_node {node_id} evidence authorization context disagrees with "
            "its query_id"
        )
    authorization_digest = provenance.get("evidence_authorization_sha256")
    if not isinstance(authorization_digest, str) or not re.fullmatch(
        r"[0-9a-f]{64}", authorization_digest
    ):
        _fail(f"eq_node {node_id} evidence authorization digest is invalid")
    authorization_key = f"query_authorization.{query_id}"
    if provenance.get("evidence_authorization_metadata_key") != authorization_key:
        _fail(
            f"eq_node {node_id} evidence authorization metadata key disagrees"
        )
    try:
        authorization_snapshot = json.loads(metadata[authorization_key])
    except KeyError:
        _fail(f"eq_node {node_id} lacks query evidence authorization metadata")
    except json.JSONDecodeError as exc:
        raise NativeSupportEqMapError(
            f"eq_node {node_id} evidence authorization is invalid JSON: {exc}"
        ) from exc
    if not isinstance(authorization_snapshot, dict):
        _fail(f"eq_node {node_id} evidence authorization must be an object")
    authorization_version = authorization_snapshot.get("authorization_version")
    if (
        authorization_snapshot.get("authorization_kind")
        != "LC1_3 scoped evidence authorization"
        or authorization_version != 3
        or authorization_snapshot.get("authorization_context_id") != query_id
    ):
        _fail(
            f"eq_node {node_id} evidence receipt must use current version 3"
        )
    snapshot_scope = authorization_snapshot.get("scope")
    if not isinstance(snapshot_scope, dict) or (
        snapshot_scope.get("metal_id") != metal_id
        or snapshot_scope.get("ligand_id") != ligand_id
    ):
        _fail(f"eq_node {node_id} evidence receipt scope disagrees")
    snapshot_digest = authorization_snapshot.get("snapshot_sha256")
    digest_payload = dict(authorization_snapshot)
    digest_payload.pop("snapshot_sha256", None)
    actual_authorization_digest = _canonical_payload_sha256(digest_payload)
    if (
        snapshot_digest != authorization_digest
        or actual_authorization_digest != authorization_digest
    ):
        _fail(f"eq_node {node_id} evidence receipt digest does not verify")

    vlm_ids = _prefixed_evidence_ids(
        provenance.get("evidence_vlm_ids"),
        prefix="vlm",
        field=f"eq_node {node_id} evidence_vlm_ids",
        required=True,
    )
    network_ids = set(_prefixed_evidence_ids(
        provenance.get("evidence_network_ids"),
        prefix="ref_eq_net",
        field=f"eq_node {node_id} evidence_network_ids",
    ))
    citation_ids = set(_prefixed_evidence_ids(
        provenance.get("evidence_citation_ids"),
        prefix="lit",
        field=f"eq_node {node_id} evidence_citation_ids",
    ))
    _validate_v3_observed_receipt(
        authorization_snapshot,
        node_id=node_id,
        beta_definition_id=beta_definition_id,
        cited_vlm_ids=vlm_ids,
        cited_network_ids=network_ids,
        cited_literature_ids=citation_ids,
    )
    _validate_estimation_description(provenance, node_id=node_id)
    return provenance

def _equation_powers(equation_python: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for match in _EQ_SPECIES_RE.finditer(equation_python):
        result[match.group(1)] = int(match.group(3)) if match.group(3) else 1
    return result


def _adapt_node(
    node: Mapping[str, Any],
    species_rows: list[Mapping[str, Any]],
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    powers = _equation_powers(str(node["equation_python"]))
    lhs: list[dict[str, Any]] = []
    rhs: list[dict[str, Any]] = []
    for row in sorted(species_rows, key=lambda value: (value["side"], value["species"])):
        raw_species = str(row["species"])
        bare_species = raw_species[1:-1] if raw_species.startswith("[") and raw_species.endswith("]") else raw_species
        adapted = {
            "species": raw_species,
            "power": powers.get(bare_species, 1),
            "phase": "solid" if "(s" in raw_species else "aqueous",
        }
        (lhs if row["side"] == "LHS" else rhs).append(adapted)
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
        "_estimated_provenance": dict(provenance),
    }


def load_native_support_eq_map(
    support_eq_map_path: str | Path,
    *,
    base_eq_map_card: Mapping[str, Any],
    allowed_system_pairs: Collection[tuple[int, int]],
    expected_support_session_id: str,
    expected_support_eq_map_sha256: str,
) -> LoadedNativeSupportEqMap:
    """Load, revalidate, and index an LC1_3 native support eq-map.

    LC1_3 records the fetched, pre-review card digest because it necessarily
    runs before LC1_2 review. LC2 receives the reviewed card, records its own
    digest, and validates the native support rows against that working input;
    the two digests are intentionally not required to be equal.

    ``allowed_system_pairs`` is derived from the active LC1_1 system catalog,
    including nested metal redox-state IDs. Every support collection must be
    in that set; the whole sidecar fails before LC2 creates a working map when
    any unrelated pair is present.

    The expected session ID and exact file SHA-256 are the publication receipt
    handed forward by the same LC1_3 run. They are mandatory and checked before
    any support node can reach LC2's working-map builder.
    """

    if (
        not isinstance(expected_support_session_id, str)
        or not expected_support_session_id
    ):
        _fail("expected_support_session_id must be a non-empty string")
    if (
        not isinstance(expected_support_eq_map_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", expected_support_eq_map_sha256) is None
    ):
        _fail("expected_support_eq_map_sha256 must be a lowercase SHA-256 digest")

    allowed_pairs = _normalize_allowed_system_pairs(allowed_system_pairs)
    allowed_pair_set = set(allowed_pairs)
    allowed_pair_digest = _canonical_payload_sha256([
        {"metal_id": metal_id, "ligand_id": ligand_id}
        for metal_id, ligand_id in allowed_pairs
    ])

    path = Path(support_eq_map_path).resolve()
    document, raw = _read_document(path)
    actual_support_sha256 = hashlib.sha256(raw).hexdigest()
    if actual_support_sha256 != expected_support_eq_map_sha256:
        _fail(
            "support eq_map SHA-256 does not match the exact LC1_3 "
            "publication receipt"
        )
    _exact_native_shape(document)

    metadata: dict[str, str] = {}
    for row in document["eq_export_metadata"]:
        if not isinstance(row["key"], str) or not isinstance(row["value"], str):
            _fail("eq_export_metadata key and value must be strings")
        metadata[row["key"]] = row["value"]
    if metadata.get("source") != ESTIMATED_SOURCE:
        _fail(f"eq_export_metadata.source must be {ESTIMATED_SOURCE!r}")
    if metadata.get("authoritative") != "false":
        _fail("support eq_map must declare authoritative=false")
    if metadata.get("artifact_kind") != "session supporting eq_map":
        _fail("support eq_map artifact_kind is not session supporting data")
    if metadata.get("assembly") != "deterministic parsed-speciation-to-native-eq-map":
        _fail("support eq_map assembly marker is not recognized")
    session_id = metadata.get("session_id")
    if not session_id:
        _fail("support eq_map session_id is required")
    if session_id != expected_support_session_id:
        _fail(
            "support eq_map session_id does not match the LC1_3 publication receipt"
        )
    expected_base_digest = _canonical_payload_sha256(base_eq_map_card)
    source_base_digest = metadata.get("base_eq_map_sha256")
    if not isinstance(source_base_digest, str) or not re.fullmatch(
        r"[0-9a-f]{64}", source_base_digest
    ):
        _fail("support eq_map base_eq_map_sha256 must identify its fetched input")

    collections = {row["collection_id"]: row for row in document["eq_map_collection"]}
    maps = {row["map_id"]: row for row in document["eq_map"]}
    networks = {row["network_db_id"]: row for row in document["eq_network"]}
    nodes = {row["node_db_id"]: row for row in document["eq_node"]}
    edges = {row["edge_db_id"]: row for row in document["eq_edge"]}
    if not nodes:
        _fail("published support eq_map contains no estimated eq_node rows")

    maps_by_collection: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for collection_id, collection in collections.items():
        _integer(collection_id, "eq_map_collection.collection_id", negative=True)
        collection_pair = (
            _integer(
                collection["metal_id"],
                "eq_map_collection.metal_id",
                negative=False,
            ),
            _integer(
                collection["ligand_id"],
                "eq_map_collection.ligand_id",
                negative=False,
            ),
        )
        if collection_pair not in allowed_pair_set:
            _fail(
                "support eq_map pair "
                f"metal_{collection_pair[0]}/ligand_{collection_pair[1]} "
                "is outside the active system catalog"
            )
        for field in (
            "total_entries", "total_networks", "iterations_count",
            "unassigned_count",
        ):
            if _integer(collection[field], f"eq_map_collection.{field}") < 0:
                _fail(f"eq_map_collection.{field} cannot be negative")
        if not isinstance(collection["created_at"], str) or not collection["created_at"]:
            _fail(f"eq_map_collection {collection_id} lacks created_at")
        if not str(collection["metal_name"]).strip() or not str(collection["ligand_name"]).strip():
            _fail(f"eq_map_collection {collection_id} lacks canonical names")
        canonical_names = _canonical_pair(
            int(collection["metal_id"]), int(collection["ligand_id"]),
        )
        if (
            str(collection["metal_name"]) != canonical_names[0]
            or str(collection["ligand_name"]) != canonical_names[1]
        ):
            _fail(f"eq_map_collection {collection_id} canonical names disagree with SRD46")

    networks_by_map: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for map_id, map_row in maps.items():
        _integer(map_id, "eq_map.map_id", negative=True)
        if map_row["collection_id"] not in collections:
            _fail(f"eq_map {map_id} references an unknown collection")
        maps_by_collection[map_row["collection_id"]].append(map_row)
        if not isinstance(map_row["map_key"], str) or not map_row["map_key"].startswith("estimated_"):
            _fail(f"eq_map {map_id} must use an estimated session map_key")
        _integer(map_row["iteration"], f"eq_map[{map_id}].iteration")
        temperature = _finite(
            map_row["condition_temperature"],
            f"eq_map[{map_id}].condition_temperature",
        )
        ionic = _finite(map_row["condition_ionic_strength"], f"eq_map[{map_id}].condition_ionic_strength")
        if ionic < 0:
            _fail(f"eq_map {map_id} ionic strength cannot be negative")
        t_min = _finite(map_row["condition_temp_min"], f"eq_map[{map_id}].condition_temp_min")
        t_max = _finite(map_row["condition_temp_max"], f"eq_map[{map_id}].condition_temp_max")
        i_min = _finite(map_row["condition_ionic_min"], f"eq_map[{map_id}].condition_ionic_min")
        i_max = _finite(map_row["condition_ionic_max"], f"eq_map[{map_id}].condition_ionic_max")
        if not (t_min <= temperature <= t_max and i_min <= ionic <= i_max):
            _fail(f"eq_map {map_id} representative conditions lie outside its ranges")
        for field in ("entry_count", "network_count", "stray_count"):
            if _integer(map_row[field], f"eq_map[{map_id}].{field}") < 0:
                _fail(f"eq_map[{map_id}].{field} cannot be negative")

    nodes_by_network: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for network_id, network in networks.items():
        _integer(network_id, "eq_network.network_db_id", negative=True)
        if network["map_id"] not in maps:
            _fail(f"eq_network {network_id} references an unknown map")
        _integer(network["network_id"], f"eq_network[{network_id}].network_id")
        for field in ("node_count", "edge_count"):
            if _integer(network[field], f"eq_network[{network_id}].{field}") < 0:
                _fail(f"eq_network[{network_id}].{field} cannot be negative")
        networks_by_map[network["map_id"]].append(network)

    species_by_node: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for species_row in document["eq_node_species"]:
        node_id = species_row["node_db_id"]
        if node_id not in nodes:
            _fail("eq_node_species references an unknown node")
        if species_row["side"] not in {"LHS", "RHS"} or not str(species_row["species"]).strip():
            _fail(f"eq_node_species for node {node_id} is invalid")
        species_by_node[node_id].append(species_row)

    canonical_beta_cache: dict[int, tuple[str, str, set[tuple[str, str]]]] = {}
    rows_by_pair: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    vlm_to_node: dict[int, dict[str, Any]] = {}
    used_authorization_metadata_keys: set[str] = set()
    for node_id, node in nodes.items():
        _integer(node_id, "eq_node.node_db_id", negative=True)
        if node["network_db_id"] not in networks:
            _fail(f"eq_node {node_id} references an unknown network")
        nodes_by_network[node["network_db_id"]].append(node)
        vlm_id = _integer(node["vlm_id"], f"eq_node[{node_id}].vlm_id", negative=True)
        if vlm_id in vlm_to_node:
            _fail(f"duplicate session vlm_id {vlm_id}")
        vlm_to_node[vlm_id] = node
        _integer(node["entry_index"], f"eq_node[{node_id}].entry_index")
        metal_id = _integer(node["metal_id"], f"eq_node[{node_id}].metal_id", negative=False)
        ligand_id = _integer(node["ligand_id"], f"eq_node[{node_id}].ligand_id", negative=False)
        beta_id = _integer(
            node["beta_definition_id"],
            f"eq_node[{node_id}].beta_definition_id",
            negative=False,
        )
        if node["constant_type"] != "K":
            _fail(f"eq_node {node_id} must use the native K convention")
        _finite(node["constant_value"], f"eq_node[{node_id}].constant_value")
        _finite(node["temperature"], f"eq_node[{node_id}].temperature")
        if _finite(node["ionic_strength"], f"eq_node[{node_id}].ionic_strength") < 0:
            _fail(f"eq_node {node_id} ionic strength cannot be negative")
        if node["is_duplicate"] not in (0, 1) or node["used_in_map"] not in (0, 1):
            _fail(f"eq_node {node_id} flags must be 0/1 integers")
        sides = {row["side"] for row in species_by_node[node_id]}
        if sides != {"LHS", "RHS"}:
            _fail(f"eq_node {node_id} must contain species on both sides")
        network = networks[node["network_db_id"]]
        map_row = maps[network["map_id"]]
        collection = collections[map_row["collection_id"]]
        if (metal_id, ligand_id) != (collection["metal_id"], collection["ligand_id"]):
            _fail(f"eq_node {node_id} pair disagrees with its collection")
        if (
            float(node["temperature"]) != float(map_row["condition_temperature"])
            or float(node["ionic_strength"]) != float(map_row["condition_ionic_strength"])
        ):
            _fail(f"eq_node {node_id} conditions disagree with its map")

        canonical = canonical_beta_cache.get(beta_id)
        if canonical is None:
            canonical = _canonical_beta(beta_id)
            canonical_beta_cache[beta_id] = canonical
        beta_name, equation_python, canonical_species = canonical
        actual_species = {
            (str(row["species"]), str(row["side"]))
            for row in species_by_node[node_id]
        }
        if (
            node["beta_definition_name"] != beta_name
            or node["equation_python"] != equation_python
            or actual_species != canonical_species
        ):
            _fail(f"eq_node {node_id} does not match beta_def_{beta_id}")

        provenance_key = f"estimated_node.{node_id}.provenance"
        try:
            provenance = json.loads(metadata[provenance_key])
        except KeyError:
            _fail(f"eq_node {node_id} lacks estimated provenance metadata")
        except json.JSONDecodeError as exc:
            raise NativeSupportEqMapError(
                f"eq_node {node_id} provenance is invalid JSON: {exc}"
            ) from exc
        provenance = _validate_estimated_provenance(
            provenance,
            node_id=node_id,
            session_vlm_id=vlm_id,
            metal_id=metal_id,
            ligand_id=ligand_id,
            beta_definition_id=beta_id,
            metadata=metadata,
        )
        used_authorization_metadata_keys.add(
            str(provenance["evidence_authorization_metadata_key"])
        )
        rows_by_pair[(metal_id, ligand_id)].append(
            _adapt_node(node, species_by_node[node_id], provenance)
        )

    actual_authorization_metadata_keys = {
        key for key in metadata if key.startswith("query_authorization.")
    }
    if actual_authorization_metadata_keys != used_authorization_metadata_keys:
        _fail(
            "query evidence authorization metadata must correspond exactly to "
            "materialized support nodes"
        )

    edge_species: dict[int, set[str]] = defaultdict(set)
    for row in document["eq_edge_species"]:
        if row["edge_db_id"] not in edges:
            _fail("eq_edge_species references an unknown edge")
        if not isinstance(row["species"], str) or not row["species"]:
            _fail("eq_edge_species.species must be non-empty")
        edge_species[row["edge_db_id"]].add(str(row["species"]))
    edges_by_network: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for edge_id, edge in edges.items():
        _integer(edge_id, "eq_edge.edge_db_id", negative=True)
        if edge["network_db_id"] not in networks:
            _fail(f"eq_edge {edge_id} references an unknown network")
        left = vlm_to_node.get(edge["node1_vlm_id"])
        right = vlm_to_node.get(edge["node2_vlm_id"])
        if left is None or right is None:
            _fail(f"eq_edge {edge_id} references an unknown session VLM")
        if left["network_db_id"] != edge["network_db_id"] or right["network_db_id"] != edge["network_db_id"]:
            _fail(f"eq_edge {edge_id} crosses network boundaries")
        left_species = {row["species"] for row in species_by_node[left["node_db_id"]]}
        right_species = {row["species"] for row in species_by_node[right["node_db_id"]]}
        if edge_species[edge_id] != left_species & right_species:
            _fail(f"eq_edge {edge_id} species do not match endpoint intersection")
        edges_by_network[edge["network_db_id"]].append(edge)

    network_species: dict[int, set[str]] = defaultdict(set)
    for row in document["eq_network_species"]:
        if row["network_db_id"] not in networks:
            _fail("eq_network_species references an unknown network")
        if not isinstance(row["species"], str) or not row["species"]:
            _fail("eq_network_species.species must be non-empty")
        network_species[row["network_db_id"]].add(str(row["species"]))
    for network_id, network in networks.items():
        network_nodes = nodes_by_network[network_id]
        if not network_nodes:
            _fail(f"eq_network {network_id} cannot be empty")
        expected_species = {
            str(row["species"])
            for node in network_nodes
            for row in species_by_node[node["node_db_id"]]
        }
        if network["node_count"] != len(network_nodes):
            _fail(f"eq_network {network_id} node_count is inconsistent")
        if network["edge_count"] != len(edges_by_network[network_id]):
            _fail(f"eq_network {network_id} edge_count is inconsistent")
        network_vlms = {int(node["vlm_id"]) for node in network_nodes}
        adjacency: dict[int, set[int]] = {
            vlm_id: set() for vlm_id in network_vlms
        }
        for edge in edges_by_network[network_id]:
            left = int(edge["node1_vlm_id"])
            right = int(edge["node2_vlm_id"])
            adjacency[left].add(right)
            adjacency[right].add(left)
        reachable: set[int] = set()
        pending = [min(network_vlms)]
        while pending:
            current = pending.pop()
            if current in reachable:
                continue
            reachable.add(current)
            pending.extend(sorted(adjacency[current] - reachable))
        if reachable != network_vlms:
            _fail(
                f"eq_network {network_id} is disconnected; distinct connected "
                "components must remain separate"
            )
        if network_species[network_id] != expected_species:
            _fail(f"eq_network {network_id} species union is inconsistent")

    if document["eq_map_stray"] or document["eq_collection_unassigned"]:
        _fail("session support maps cannot contain measured stray/unassigned IDs")
    for map_id, map_row in maps.items():
        map_networks = networks_by_map[map_id]
        entry_count = sum(len(nodes_by_network[row["network_db_id"]]) for row in map_networks)
        if map_row["network_count"] != len(map_networks) or map_row["entry_count"] != entry_count:
            _fail(f"eq_map {map_id} counts are inconsistent")
        local_network_ids = [int(row["network_id"]) for row in map_networks]
        if len(local_network_ids) != len(set(local_network_ids)):
            _fail(f"eq_map {map_id} has duplicate local network_id values")
        if map_row["stray_count"] != 0:
            _fail(f"eq_map {map_id} cannot contain strays")
    for collection_id, collection in collections.items():
        collection_maps = maps_by_collection[collection_id]
        n_networks = sum(len(networks_by_map[row["map_id"]]) for row in collection_maps)
        n_entries = sum(row["entry_count"] for row in collection_maps)
        if (
            collection["total_networks"] != n_networks
            or collection["total_entries"] != n_entries
            or collection["iterations_count"] != len(collection_maps)
            or collection["unassigned_count"] != 0
        ):
            _fail(f"eq_map_collection {collection_id} counts are inconsistent")

    frozen_rows = {
        pair: tuple(sorted(
            rows,
            key=lambda row: (
                row["temperature"], row["ionic_strength"],
                row["beta_definition_id"], row["node_db_id"],
            ),
        ))
        for pair, rows in rows_by_pair.items()
    }
    return LoadedNativeSupportEqMap(
        path=path,
        payload=document,
        sha256=actual_support_sha256,
        session_id=str(session_id),
        base_eq_map_sha256=source_base_digest,
        reviewed_base_eq_map_sha256=expected_base_digest,
        system_catalog_pair_set_sha256=allowed_pair_digest,
        allowed_system_pairs=allowed_pairs,
        rows_by_pair=frozen_rows,
        node_count=len(nodes),
    )


__all__ = [
    "ESTIMATED_SOURCE",
    "LoadedNativeSupportEqMap",
    "NATIVE_TABLE_COLUMNS",
    "NativeSupportEqMapError",
    "load_native_support_eq_map",
]

