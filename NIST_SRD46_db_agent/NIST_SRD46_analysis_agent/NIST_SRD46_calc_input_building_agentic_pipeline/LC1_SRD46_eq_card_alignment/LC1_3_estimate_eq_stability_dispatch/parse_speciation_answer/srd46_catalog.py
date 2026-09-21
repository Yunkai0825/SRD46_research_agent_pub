"""Read-only canonical chemistry catalog used by parser and publication gates."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Protocol

from NIST_SRD46_core_db_search_tools._db_connection import (
    get_cards_db,
    get_equilibrium_db,
)


class Catalog(Protocol):
    def inspect_pair(self, metal_id: int, ligand_id: int) -> dict[str, Any]: ...
    def inspect_beta(self, beta_definition_id: int) -> dict[str, Any]: ...
    def enumerate_materializable_betas(self) -> dict[str, Any]: ...
    def inspect_evidence(self, vlm_ids: list[int]) -> dict[str, Any]: ...


def _positive_id(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a positive integer")
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return parsed


def _prefixed_id(value: Any, prefix: str, label: str) -> int:
    text = str(value).strip()
    if text.startswith(prefix + "_"):
        text = text[len(prefix) + 1:]
    return _positive_id(text, label)


@contextmanager
def _query_only(factory):
    with factory() as connection:
        connection.execute("PRAGMA query_only = ON")
        yield connection


class SRD46Catalog:
    """Canonical identities read from the installed SRD-46 databases."""

    def inspect_pair(self, metal_id: int, ligand_id: int) -> dict[str, Any]:
        mid = _positive_id(metal_id, "metal_id")
        lid = _positive_id(ligand_id, "ligand_id")
        with _query_only(get_cards_db) as connection:
            metal = connection.execute(
                "SELECT metal_id, metal_name_SRD FROM metal_card WHERE metal_id=?",
                (mid,),
            ).fetchone()
            ligand = connection.execute(
                "SELECT ligand_id, ligand_name_SRD, ligand_SMILES, definition_HxL "
                "FROM ligand_card WHERE ligand_id=?",
                (lid,),
            ).fetchone()
            exact_count = int(connection.execute(
                "SELECT COUNT(*) FROM ligandmetal_card "
                "WHERE metal_id=? AND ligand_id=?",
                (mid, lid),
            ).fetchone()[0])
        if metal is None or ligand is None:
            return {
                "status": "not_found",
                "metal_id": mid,
                "ligand_id": lid,
                "metal_found": metal is not None,
                "ligand_found": ligand is not None,
            }
        return {
            "status": "ok",
            "metal_id": mid,
            "metal_name": metal["metal_name_SRD"],
            "ligand_id": lid,
            "ligand_name": ligand["ligand_name_SRD"],
            "ligand_smiles": ligand["ligand_SMILES"],
            "ligand_definition_HxL": ligand["definition_HxL"],
            "exact_measured_card_count": exact_count,
        }

    @lru_cache(maxsize=2048)
    def inspect_beta(self, beta_definition_id: int) -> dict[str, Any]:
        beta_id = _positive_id(beta_definition_id, "beta_definition_id")
        with _query_only(get_equilibrium_db) as connection:
            identities = connection.execute(
                """
                SELECT DISTINCT beta_definition_name, equation_python
                FROM eq_node
                WHERE beta_definition_id=? AND constant_type='K'
                  AND equation_python IS NOT NULL
                  AND TRIM(equation_python) NOT IN ('', '*')
                ORDER BY beta_definition_name, equation_python
                """,
                (beta_id,),
            ).fetchall()
            representative = connection.execute(
                """
                SELECT node_db_id, beta_definition_name, equation_python
                FROM eq_node
                WHERE beta_definition_id=? AND constant_type='K'
                  AND equation_python IS NOT NULL
                  AND TRIM(equation_python) NOT IN ('', '*')
                ORDER BY used_in_map DESC, is_duplicate ASC, node_db_id
                LIMIT 1
                """,
                (beta_id,),
            ).fetchone()
            species = [] if representative is None else [
                {"species": row["species"], "side": row["side"]}
                for row in connection.execute(
                    "SELECT species, side FROM eq_node_species "
                    "WHERE node_db_id=? ORDER BY side, species",
                    (representative["node_db_id"],),
                ).fetchall()
            ]
        if representative is None or not identities or not species:
            return {
                "status": "not_materializable",
                "beta_definition_id": beta_id,
                "reason": "no K-backed eq_node with a complete reaction",
            }
        distinct = {
            (row["beta_definition_name"], row["equation_python"])
            for row in identities
        }
        if len(distinct) != 1:
            return {
                "status": "conflict",
                "beta_definition_id": beta_id,
                "identities": [list(value) for value in sorted(distinct)],
            }
        name, equation = next(iter(distinct))
        return {
            "status": "ok",
            "beta_definition_id": beta_id,
            "beta_definition_name": name,
            "equation_python": equation,
            "node_species": species,
            "constant_type": "K",
            "materializable": True,
        }

    @lru_cache(maxsize=1)
    def _materializable_beta_catalog(self) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
        """Build one deterministic, read-only index of canonical K topologies.

        Topology resolution is downstream schema assembly, so its search space
        is the installed canonical beta catalog rather than the subset of beta
        IDs happened to be mentioned or observed by the QueryAgent.  The
        database is scanned once per process.  Conflicting beta identities and
        definitions without a materializable reaction are recorded but never
        exposed as matching candidates.
        """

        with _query_only(get_equilibrium_db) as connection:
            rows = connection.execute(
                """
                SELECT beta_definition_id, beta_definition_name,
                       equation_python, node_db_id, used_in_map, is_duplicate
                FROM eq_node
                WHERE beta_definition_id IS NOT NULL
                  AND beta_definition_id > 0
                  AND constant_type='K'
                  AND equation_python IS NOT NULL
                  AND TRIM(equation_python) NOT IN ('', '*')
                ORDER BY beta_definition_id, used_in_map DESC,
                         is_duplicate ASC, node_db_id
                """
            ).fetchall()

            grouped: dict[int, list[Any]] = {}
            for row in rows:
                grouped.setdefault(int(row["beta_definition_id"]), []).append(row)

            representative_ids: list[int] = []
            representatives: dict[int, Any] = {}
            conflicts: dict[int, list[list[str]]] = {}
            for beta_id, beta_rows in grouped.items():
                identities = {
                    (
                        str(row["beta_definition_name"] or "").strip(),
                        str(row["equation_python"] or "").strip(),
                    )
                    for row in beta_rows
                }
                if len(identities) != 1 or any(
                    not name or not equation or name == "*" or equation == "*"
                    for name, equation in identities
                ):
                    conflicts[beta_id] = [
                        [name, equation] for name, equation in sorted(identities)
                    ]
                    continue
                representative = beta_rows[0]
                representatives[beta_id] = representative
                representative_ids.append(int(representative["node_db_id"]))

            # Keep this compatible with SQLite builds whose host-parameter
            # limit is 999.  One connection and bounded chunks are far cheaper
            # than reopening the database once for every beta definition.
            species_by_node: dict[int, list[dict[str, Any]]] = {}
            chunk_size = 500
            for start in range(0, len(representative_ids), chunk_size):
                chunk = representative_ids[start:start + chunk_size]
                placeholders = ",".join("?" for _ in chunk)
                for row in connection.execute(
                    "SELECT node_db_id, species, side FROM eq_node_species "
                    f"WHERE node_db_id IN ({placeholders}) "
                    "ORDER BY node_db_id, side, species",
                    tuple(chunk),
                ).fetchall():
                    species_by_node.setdefault(int(row["node_db_id"]), []).append({
                        "species": row["species"],
                        "side": row["side"],
                    })

        records: list[dict[str, Any]] = []
        excluded: list[dict[str, Any]] = []
        for beta_id in sorted(grouped):
            if beta_id in conflicts:
                excluded.append({
                    "status": "conflict",
                    "beta_definition_id": beta_id,
                    "identities": conflicts[beta_id],
                })
                continue
            representative = representatives[beta_id]
            node_db_id = int(representative["node_db_id"])
            species = species_by_node.get(node_db_id, [])
            if not species:
                excluded.append({
                    "status": "not_materializable",
                    "beta_definition_id": beta_id,
                    "reason": "representative K reaction has no node species",
                })
                continue
            records.append({
                "status": "ok",
                "beta_definition_id": beta_id,
                "beta_definition_name": str(
                    representative["beta_definition_name"]
                ),
                "equation_python": str(representative["equation_python"]),
                "node_species": species,
                "constant_type": "K",
                "materializable": True,
            })
        return tuple(records), tuple(excluded)

    def enumerate_materializable_betas(self) -> dict[str, Any]:
        """Return all unambiguous materializable canonical beta definitions."""

        records, excluded = self._materializable_beta_catalog()
        return {
            "status": "ok",
            "records": deepcopy(list(records)),
            "excluded": deepcopy(list(excluded)),
            "materializable_count": len(records),
            "excluded_count": len(excluded),
        }

    def inspect_evidence(self, vlm_ids: list[int]) -> dict[str, Any]:
        records: list[dict[str, Any]] = []
        for raw_id in vlm_ids:
            vlm_id = _positive_id(raw_id, "vlm_id")
            with _query_only(get_cards_db) as connection:
                measured = [dict(row) for row in connection.execute(
                    """
                    SELECT c.complex_system_id AS vlm_id, c.metal_id, c.ligand_id,
                           c.beta_definition_id, c.beta_definition_name,
                           s.constant_type, s.constant_value,
                           s.temperature_c AS temperature,
                           s.ionic_strength_mol_l AS ionic_strength,
                           s.equation_python, s.solvent_name
                    FROM ligandmetal_card c
                    JOIN ligandmetal_stability_measured s ON s.card_id=c.card_id
                    WHERE c.complex_system_id=? AND s.constant_type='K'
                    ORDER BY s.stability_id
                    """,
                    (vlm_id,),
                ).fetchall()]
                citations = [dict(row) for row in connection.execute(
                    """
                    SELECT la.literature_alt_id, la.shortcut, la.citation
                    FROM ref_vlm_literature_alt rv
                    JOIN ref_literature_alt la
                      ON la.literature_alt_id=rv.literature_alt_id
                    WHERE rv.vlm_id=? ORDER BY la.literature_alt_id
                    """,
                    (vlm_id,),
                ).fetchall()]
            with _query_only(get_equilibrium_db) as connection:
                mapped = [dict(row) for row in connection.execute(
                    """
                    SELECT vlm_id, metal_id, ligand_id, beta_definition_id,
                           beta_definition_name, constant_type, constant_value,
                           temperature, ionic_strength, equation_python,
                           network_db_id, node_db_id
                    FROM eq_node WHERE vlm_id=? ORDER BY node_db_id
                    """,
                    (vlm_id,),
                ).fetchall()]
            status = "ok"
            reason = None
            measured_identity = {
                (
                    row["metal_id"], row["ligand_id"],
                    row["beta_definition_id"], row["beta_definition_name"],
                    row["constant_type"], row["constant_value"],
                    row["temperature"], row["ionic_strength"],
                )
                for row in measured
            }
            mapped_identity = {
                (
                    row["metal_id"], row["ligand_id"],
                    row["beta_definition_id"], row["beta_definition_name"],
                    row["constant_type"], row["constant_value"],
                    row["temperature"], row["ionic_strength"],
                )
                for row in mapped
            }
            if not measured:
                status, reason = "not_found", "no measured K record"
            elif len(measured_identity) != 1:
                status, reason = "conflict", "multiple measured identities"
            elif mapped_identity and mapped_identity != measured_identity:
                status, reason = "conflict", "cards/map identities disagree"
            records.append({
                "status": status,
                "vlm_id": vlm_id,
                "conflict_reason": reason,
                "cards_rows": measured,
                "eq_node_rows": mapped,
                "citation_rows": citations,
            })
        return {
            "status": (
                "ok" if all(row["status"] == "ok" for row in records)
                else "conflict"
            ),
            "records": records,
        }


@dataclass
class StaticCatalog:
    """In-memory catalog for deterministic parser-gate tests."""

    pairs: dict[tuple[int, int], dict[str, Any]] = field(default_factory=dict)
    betas: dict[int, dict[str, Any]] = field(default_factory=dict)
    evidence: dict[int, dict[str, Any]] = field(default_factory=dict)

    def inspect_pair(self, metal_id: int, ligand_id: int) -> dict[str, Any]:
        return deepcopy(self.pairs.get(
            (int(metal_id), int(ligand_id)),
            {"status": "not_found", "metal_id": metal_id, "ligand_id": ligand_id},
        ))

    def inspect_beta(self, beta_definition_id: int) -> dict[str, Any]:
        return deepcopy(self.betas.get(
            int(beta_definition_id),
            {"status": "not_materializable", "beta_definition_id": beta_definition_id},
        ))

    def enumerate_materializable_betas(self) -> dict[str, Any]:
        records: list[dict[str, Any]] = []
        excluded: list[dict[str, Any]] = []
        for beta_id in sorted(self.betas):
            row = deepcopy(self.betas[beta_id])
            status = row.get("status")
            if status == "ok" and row.get("materializable", True):
                records.append(row)
            else:
                excluded.append(row)
        return {
            "status": "ok",
            "records": records,
            "excluded": excluded,
            "materializable_count": len(records),
            "excluded_count": len(excluded),
        }

    def inspect_evidence(self, vlm_ids: list[int]) -> dict[str, Any]:
        rows = [deepcopy(self.evidence.get(
            int(value),
            {"status": "not_found", "vlm_id": int(value), "cards_rows": [],
             "eq_node_rows": [], "citation_rows": []},
        )) for value in vlm_ids]
        return {
            "status": "ok" if all(row.get("status") == "ok" for row in rows) else "conflict",
            "records": rows,
        }


DEFAULT_CATALOG = SRD46Catalog()


def inspect_chemical_pair_record(
    metal_id: int, ligand_id: int, *, catalog: Catalog | None = None
) -> dict[str, Any]:
    return (catalog or DEFAULT_CATALOG).inspect_pair(
        _prefixed_id(metal_id, "metal", "metal_id"),
        _prefixed_id(ligand_id, "ligand", "ligand_id"),
    )


def inspect_beta_definition_record(
    beta_definition_id: int, *, catalog: Catalog | None = None
) -> dict[str, Any]:
    return (catalog or DEFAULT_CATALOG).inspect_beta(
        _prefixed_id(beta_definition_id, "beta_def", "beta_definition_id")
    )


def enumerate_materializable_beta_records(
    *, catalog: Catalog | None = None
) -> dict[str, Any]:
    """Enumerate the complete canonical topology search space read-only."""

    return (catalog or DEFAULT_CATALOG).enumerate_materializable_betas()


def inspect_evidence_records(
    vlm_ids: list[int], *, catalog: Catalog | None = None
) -> dict[str, Any]:
    return (catalog or DEFAULT_CATALOG).inspect_evidence([
        _prefixed_id(value, "vlm", "vlm_id") for value in vlm_ids
    ])


__all__ = [
    "Catalog",
    "DEFAULT_CATALOG",
    "SRD46Catalog",
    "StaticCatalog",
    "enumerate_materializable_beta_records",
    "inspect_beta_definition_record",
    "inspect_chemical_pair_record",
    "inspect_evidence_records",
]
