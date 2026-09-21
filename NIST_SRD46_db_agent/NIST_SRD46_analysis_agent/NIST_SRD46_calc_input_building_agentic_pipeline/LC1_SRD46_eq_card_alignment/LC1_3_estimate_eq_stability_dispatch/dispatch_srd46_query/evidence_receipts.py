"""Post-hoc evidence receipts for an unrestricted SRD-46 query session.

This module deliberately contains no chemistry search policy.  It inspects
only successful ``result_full`` values that were actually returned to the
query agent, records the identifiers visible in those values, and resolves
their canonical relationships from the read-only SRD-46 databases.  The
result keeps the historical ``evidence_authorization`` outer field names so
that existing parser and assembler handoffs remain compatible.
"""

from __future__ import annotations

import hashlib
import json
import re
from contextlib import contextmanager
from typing import Any, Iterable, Mapping

from NIST_SRD46_core_db_search_tools._db_connection import (
    get_cards_db,
    get_equilibrium_db,
)

_PREFIX_PATTERNS = {
    "vlm": re.compile(r"(?i)\bvlm_(\d+)\b"),
    "beta": re.compile(r"(?i)\bbeta_def_(\d+)\b"),
    "network": re.compile(r"(?i)\b(?:ref_eq_net|network)_(\d+)\b"),
    "literature": re.compile(r"(?i)\b(?:lit|literature)_(\d+)\b"),
}
_COMPACT_PREFIX_PATTERNS = {
    "vlm": re.compile(r"(?i)\bvlm_\(\s*([\d,\s]+)\)"),
    "beta": re.compile(r"(?i)\bbeta_def_\(\s*([\d,\s]+)\)"),
    "network": re.compile(
        r"(?i)\b(?:ref_eq_net|network)_\(\s*([\d,\s]+)\)"
    ),
    "literature": re.compile(
        r"(?i)\b(?:lit|literature)_\(\s*([\d,\s]+)\)"
    ),
}

_NUMERIC_ID_KEYS = {
    "vlm": {
        "vlm_id",
        "vlm_ids",
        "source_vlm_id",
        "example_vlm_id",
        "complex_system_id",
        "complex_system_ids",
    },
    "beta": {
        "beta_definition_id",
        "beta_definition_ids",
        "beta_def_id",
        "beta_def_ids",
    },
    "network": {
        "network_id",
        "network_ids",
        "network_db_id",
        "network_db_ids",
        "ref_eq_net_id",
        "ref_eq_net_ids",
    },
    "literature": {
        "literature_id",
        "literature_ids",
        "literature_alt_id",
        "literature_alt_ids",
        "citation_id",
        "citation_ids",
        "evidence_citation_ids",
    },
}


@contextmanager
def _query_only(connection_factory):
    """Open a host database connection with writes disabled."""

    with connection_factory() as connection:
        connection.execute("PRAGMA query_only = ON")
        yield connection


def _positive_id(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float):
        return int(value) if value > 0 and value.is_integer() else None
    text = str(value or "").strip()
    match = re.fullmatch(r"(?:[A-Za-z][A-Za-z0-9_-]*[_-])?(\d+)", text)
    if not match:
        return None
    parsed = int(match.group(1))
    return parsed if parsed > 0 else None


def _collect_numeric_values(value: Any, target: set[int]) -> None:
    if isinstance(value, (list, tuple, set)):
        for item in value:
            _collect_numeric_values(item, target)
        return
    parsed = _positive_id(value)
    if parsed is not None:
        target.add(parsed)


def _walk_structured_ids(value: Any, observed: dict[str, set[int]]) -> None:
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key).strip().lower()
            for kind, keys in _NUMERIC_ID_KEYS.items():
                if key in keys:
                    _collect_numeric_values(child, observed[kind])
                    break
            _walk_structured_ids(child, observed)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _walk_structured_ids(child, observed)


def _extract_observed_ids(raw_result: str) -> dict[str, list[int]]:
    observed: dict[str, set[int]] = {
        "vlm": set(),
        "beta": set(),
        "network": set(),
        "literature": set(),
    }
    for kind, pattern in _PREFIX_PATTERNS.items():
        observed[kind].update(int(match) for match in pattern.findall(raw_result))
    for kind, pattern in _COMPACT_PREFIX_PATTERNS.items():
        for match in pattern.findall(raw_result):
            observed[kind].update(
                int(value.strip())
                for value in match.split(",")
                if value.strip()
            )
    try:
        structured = json.loads(raw_result)
    except (TypeError, ValueError, json.JSONDecodeError):
        structured = None
    if structured is not None:
        _walk_structured_ids(structured, observed)
    return {kind: sorted(values) for kind, values in observed.items()}


def _raw_result(row: Mapping[str, Any]) -> str | None:
    if bool(row.get("is_error")):
        return None
    if "result_full" not in row or row.get("result_full") is None:
        return None
    value = row.get("result_full")
    if isinstance(value, str):
        raw = value
    else:
        raw = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )
    if not raw.strip() or raw.lstrip().upper().startswith("[TOOL ERROR]"):
        return None
    return raw


def _receipt_bindings(
    receipts: Iterable[Mapping[str, Any]],
    id_key: str,
) -> dict[int, list[str]]:
    bindings: dict[int, set[str]] = {}
    for receipt in receipts:
        digest = str(receipt["result_sha256"])
        for value in receipt[id_key]:
            bindings.setdefault(int(value), set()).add(digest)
    return {key: sorted(values) for key, values in bindings.items()}


def _chunks(values: list[int], size: int = 800) -> Iterable[list[int]]:
    for start in range(0, len(values), size):
        yield values[start:start + size]


def _canonical_vlm_records(
    vlm_ids: list[int],
    receipt_sha256s: Mapping[int, list[str]],
) -> list[dict[str, Any]]:
    if not vlm_ids:
        return []
    cards_by_vlm: dict[int, list[dict[str, Any]]] = {
        value: [] for value in vlm_ids
    }
    nodes_by_vlm: dict[int, list[dict[str, Any]]] = {
        value: [] for value in vlm_ids
    }
    citations_by_vlm: dict[int, list[dict[str, Any]]] = {
        value: [] for value in vlm_ids
    }
    with _query_only(get_cards_db) as connection:
        for batch in _chunks(vlm_ids):
            placeholders = ",".join("?" for _ in batch)
            card_rows = connection.execute(
                f"""
                SELECT c.complex_system_id AS vlm_id, c.metal_id, c.ligand_id,
                       c.beta_definition_id, c.beta_definition_name,
                       s.constant_type, s.constant_value,
                       s.temperature_c AS temperature,
                       s.ionic_strength_mol_l AS ionic_strength,
                       s.equation_python
                FROM ligandmetal_card c
                JOIN ligandmetal_stability_measured s ON s.card_id=c.card_id
                WHERE c.complex_system_id IN ({placeholders})
                  AND s.constant_type='K'
                ORDER BY c.complex_system_id, s.stability_id
                """,
                batch,
            ).fetchall()
            for row in card_rows:
                cards_by_vlm[int(row["vlm_id"])].append(dict(row))
            citation_rows = connection.execute(
                f"""
                SELECT rv.vlm_id, rv.literature_alt_id
                FROM ref_vlm_literature_alt rv
                WHERE rv.vlm_id IN ({placeholders})
                ORDER BY rv.vlm_id, rv.literature_alt_id
                """,
                batch,
            ).fetchall()
            for row in citation_rows:
                citations_by_vlm[int(row["vlm_id"])].append(dict(row))
    with _query_only(get_equilibrium_db) as connection:
        for batch in _chunks(vlm_ids):
            placeholders = ",".join("?" for _ in batch)
            node_rows = connection.execute(
                f"""
                SELECT vlm_id, metal_id, ligand_id, beta_definition_id,
                       beta_definition_name, constant_type, constant_value,
                       temperature, ionic_strength, equation_python,
                       network_db_id
                FROM eq_node
                WHERE vlm_id IN ({placeholders})
                ORDER BY vlm_id, node_db_id
                """,
                batch,
            ).fetchall()
            for row in node_rows:
                nodes_by_vlm[int(row["vlm_id"])].append(dict(row))

    records: list[dict[str, Any]] = []
    for vlm_id in vlm_ids:
        card_rows = cards_by_vlm[vlm_id]
        node_rows = nodes_by_vlm[vlm_id]
        citation_rows = citations_by_vlm[vlm_id]
        metal_ids = sorted({
            int(row["metal_id"])
            for row in [*card_rows, *node_rows]
            if row.get("metal_id") is not None
        })
        ligand_ids = sorted({
            int(row["ligand_id"])
            for row in [*card_rows, *node_rows]
            if row.get("ligand_id") is not None
        })
        beta_ids = sorted({
            int(row["beta_definition_id"])
            for row in [*card_rows, *node_rows]
            if row.get("beta_definition_id") is not None
        })
        network_ids = sorted({
            int(row["network_db_id"])
            for row in node_rows
            if row.get("network_db_id") is not None
        })
        literature_ids = sorted({
            int(row["literature_alt_id"])
            for row in citation_rows
            if row.get("literature_alt_id") is not None
        })
        measured_identities = {
            (
                row.get("metal_id"),
                row.get("ligand_id"),
                row.get("beta_definition_id"),
                row.get("beta_definition_name"),
                row.get("constant_type"),
                row.get("constant_value"),
                row.get("temperature"),
                row.get("ionic_strength"),
            )
            for row in card_rows
        }
        mapped_identities = {
            (
                row.get("metal_id"),
                row.get("ligand_id"),
                row.get("beta_definition_id"),
                row.get("beta_definition_name"),
                row.get("constant_type"),
                row.get("constant_value"),
                row.get("temperature"),
                row.get("ionic_strength"),
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
                row.get("equation_python")
                for row in card_rows
                if row.get("equation_python") not in (None, "", "*")
            }
            mapped_equations = {
                row.get("equation_python")
                for row in node_rows
                if row.get("equation_python") not in (None, "", "*")
            }
            if measured_equations and mapped_equations != measured_equations:
                canonical_status = "conflict"
        records.append({
            "vlm_id": vlm_id,
            "canonical_status": canonical_status,
            "metal_id": metal_ids[0] if len(metal_ids) == 1 else None,
            "ligand_id": ligand_ids[0] if len(ligand_ids) == 1 else None,
            "beta_definition_ids": beta_ids,
            "network_ids": network_ids,
            "literature_ids": literature_ids,
            "receipt_sha256s": list(receipt_sha256s.get(vlm_id, [])),
        })
    return sorted(records, key=lambda row: int(row["vlm_id"]))


def _canonical_network_records(
    network_ids: list[int],
    receipt_sha256s: Mapping[int, list[str]],
) -> list[dict[str, Any]]:
    rows_by_network: dict[int, list[dict[str, Any]]] = {
        value: [] for value in network_ids
    }
    with _query_only(get_equilibrium_db) as connection:
        for batch in _chunks(network_ids):
            placeholders = ",".join("?" for _ in batch)
            rows = connection.execute(
                f"""
                SELECT DISTINCT network_db_id, vlm_id, metal_id, ligand_id
                FROM eq_node
                WHERE network_db_id IN ({placeholders})
                ORDER BY network_db_id, vlm_id, metal_id, ligand_id
                """,
                batch,
            ).fetchall()
            for row in rows:
                rows_by_network[int(row["network_db_id"])].append(dict(row))
    return [{
        "network_id": network_id,
        "canonical_status": "ok" if rows_by_network[network_id] else "not_found",
        "vlm_ids": sorted({
            int(row["vlm_id"])
            for row in rows_by_network[network_id]
            if row["vlm_id"] is not None
        }),
        "metal_ids": sorted({
            int(row["metal_id"])
            for row in rows_by_network[network_id]
            if row["metal_id"] is not None
        }),
        "ligand_ids": sorted({
            int(row["ligand_id"])
            for row in rows_by_network[network_id]
            if row["ligand_id"] is not None
        }),
        "receipt_sha256s": list(receipt_sha256s.get(network_id, [])),
    } for network_id in network_ids]


def _canonical_literature_records(
    literature_ids: list[int],
    receipt_sha256s: Mapping[int, list[str]],
) -> list[dict[str, Any]]:
    rows_by_literature: dict[int, list[dict[str, Any]]] = {
        value: [] for value in literature_ids
    }
    with _query_only(get_cards_db) as connection:
        for batch in _chunks(literature_ids):
            placeholders = ",".join("?" for _ in batch)
            rows = connection.execute(
                f"""
                SELECT DISTINCT rv.literature_alt_id, rv.vlm_id,
                                la.shortcut, la.citation
                FROM ref_vlm_literature_alt rv
                JOIN ref_literature_alt la
                  ON la.literature_alt_id=rv.literature_alt_id
                WHERE rv.literature_alt_id IN ({placeholders})
                ORDER BY rv.literature_alt_id, rv.vlm_id
                """,
                batch,
            ).fetchall()
            for row in rows:
                rows_by_literature[int(row["literature_alt_id"])].append(
                    dict(row)
                )
    return [{
        "literature_id": literature_id,
        "canonical_status": (
            "ok" if rows_by_literature[literature_id] else "not_found"
        ),
        "vlm_ids": sorted({
            int(row["vlm_id"])
            for row in rows_by_literature[literature_id]
        }),
        "shortcuts": sorted({
            str(row["shortcut"])
            for row in rows_by_literature[literature_id]
            if row["shortcut"] not in (None, "")
        }),
        "citations": sorted({
            str(row["citation"])
            for row in rows_by_literature[literature_id]
            if row["citation"] not in (None, "")
        }),
        "receipt_sha256s": list(receipt_sha256s.get(literature_id, [])),
    } for literature_id in literature_ids]


def build_evidence_authorization_snapshot(
    *,
    tool_history: Iterable[Mapping[str, Any]],
    scope: Mapping[str, Any],
    authorization_context_id: str,
) -> dict[str, Any]:
    """Build an immutable version-3 receipt snapshot from returned tool data."""

    metal_id = _positive_id(scope.get("metal_id"))
    ligand_id = _positive_id(scope.get("ligand_id"))
    if metal_id is None or ligand_id is None:
        raise ValueError("scope must contain positive metal_id and ligand_id")
    context_id = str(authorization_context_id or "").strip()
    if not context_id:
        raise ValueError("authorization_context_id must be non-empty")

    tool_receipts: list[dict[str, Any]] = []
    for history_index, row in enumerate(tool_history):
        if not isinstance(row, Mapping):
            continue
        raw = _raw_result(row)
        if raw is None:
            continue
        observed = _extract_observed_ids(raw)
        tool_receipts.append({
            "history_index": history_index,
            "tool": str(row.get("tool") or row.get("name") or "unknown"),
            "result_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            "observed_vlm_ids": observed["vlm"],
            "observed_beta_definition_ids": observed["beta"],
            "observed_network_ids": observed["network"],
            "observed_literature_ids": observed["literature"],
        })

    observed_vlms = sorted({
        int(value)
        for receipt in tool_receipts
        for value in receipt["observed_vlm_ids"]
    })
    observed_betas = sorted({
        int(value)
        for receipt in tool_receipts
        for value in receipt["observed_beta_definition_ids"]
    })
    observed_networks = sorted({
        int(value)
        for receipt in tool_receipts
        for value in receipt["observed_network_ids"]
    })
    observed_literature = sorted({
        int(value)
        for receipt in tool_receipts
        for value in receipt["observed_literature_ids"]
    })

    vlm_bindings = _receipt_bindings(
        tool_receipts, "observed_vlm_ids"
    )
    network_bindings = _receipt_bindings(
        tool_receipts, "observed_network_ids"
    )
    literature_bindings = _receipt_bindings(
        tool_receipts, "observed_literature_ids"
    )
    payload: dict[str, Any] = {
        "authorization_kind": "LC1_3 scoped evidence authorization",
        "authorization_version": 3,
        "authorization_context_id": context_id,
        "scope": {
            "metal_id": metal_id,
            "metal_name": scope.get("metal_name"),
            "ligand_id": ligand_id,
            "ligand_name": scope.get("ligand_name"),
        },
        "tool_receipts": tool_receipts,
        "observed_vlm_ids": observed_vlms,
        "observed_beta_definition_ids": observed_betas,
        "observed_network_ids": observed_networks,
        "observed_literature_ids": observed_literature,
        "vlm_records": _canonical_vlm_records(observed_vlms, vlm_bindings),
        "network_records": _canonical_network_records(
            observed_networks, network_bindings
        ),
        "literature_records": _canonical_literature_records(
            observed_literature, literature_bindings
        ),
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    payload["snapshot_sha256"] = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()
    return payload


# A shorter name for callers that no longer use the legacy terminology.
build_evidence_receipt_snapshot = build_evidence_authorization_snapshot


__all__ = [
    "build_evidence_authorization_snapshot",
    "build_evidence_receipt_snapshot",
]
