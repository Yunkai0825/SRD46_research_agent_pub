"""Deterministic canonical pair construction for direct LC1.3 queries."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from NIST_SRD46_core_db_search_tools._db_connection import get_cards_db

from ..runtime_support.artifacts import mkdir, write_json
from ..runtime_support.runtime_models import LC13Settings, QuerySession


_METAL_RE = re.compile(r"^(?:metal_)?(\d+)$")
_LIGAND_RE = re.compile(r"^(?:ligand_)?(\d+)$")
_NETWORK_RE = re.compile(r"^(?:ref_eq_net_)?(\d+)$")


@dataclass
class PairScopeResult:
    """Canonical pair sessions selected for one direct-query run."""

    sessions: list[QuerySession]
    manifest_path: str
    omitted_scopes: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "manifest_path": self.manifest_path,
            "n_scopes": len(self.sessions),
            "n_omitted_scopes": len(self.omitted_scopes),
            "omitted_scopes": self.omitted_scopes,
            "queries": [
                {
                    "query_id": row.query_id,
                    "scope": row.scope,
                    "artifact_dir": str(row.artifact_dir),
                }
                for row in self.sessions
            ],
        }


def _numeric_id(value: Any, pattern: re.Pattern[str]) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    match = pattern.fullmatch(str(value).strip())
    return int(match.group(1)) if match else None


def _canonical_name(table: str, id_column: str, name_column: str, value: int) -> str | None:
    with get_cards_db() as conn:
        row = conn.execute(
            f"SELECT {name_column} FROM {table} WHERE {id_column}=?",
            (value,),
        ).fetchone()
    return None if row is None else str(row[name_column])


def target_metals(chemical_system: dict[str, Any]) -> list[tuple[int, str]]:
    """Return canonical non-water SRD metal/oxidation-state identities."""

    rows: list[tuple[int, str]] = []
    seen: set[int] = set()
    for entry in chemical_system.get("metals", []) or []:
        if not isinstance(entry, dict) or bool(entry.get("water_species")):
            continue
        redox_states = entry.get("redox_states")
        candidates = list(redox_states) if isinstance(redox_states, list) else []
        candidates.append(entry)
        for candidate in candidates:
            if not isinstance(candidate, dict) or bool(candidate.get("water_species")):
                continue
            value = _numeric_id(
                candidate.get("db_id") or candidate.get("metal_id"),
                _METAL_RE,
            )
            if value is None or value in seen:
                continue
            name = _canonical_name(
                "metal_card", "metal_id", "metal_name_SRD", value
            )
            if name is None:
                continue
            rows.append((value, name))
            seen.add(value)
    return sorted(rows)


def target_ligands(chemical_system: dict[str, Any]) -> list[tuple[int, str]]:
    """Return canonical non-water SRD ligand identities."""

    rows: list[tuple[int, str]] = []
    seen: set[int] = set()
    for entry in chemical_system.get("ligands", []) or []:
        if not isinstance(entry, dict) or bool(entry.get("water_species")):
            continue
        value = _numeric_id(
            entry.get("db_id") or entry.get("ligand_id"),
            _LIGAND_RE,
        )
        if value is None or value in seen:
            continue
        name = _canonical_name(
            "ligand_card", "ligand_id", "ligand_name_SRD", value
        )
        if name is None:
            continue
        rows.append((value, name))
        seen.add(value)
    return sorted(rows)


def build_pair_scopes(
    *,
    chemical_system: dict[str, Any],
    base_eq_map_card: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build every canonical metal-ligand pair once.

    Existing map rows are attached only as audit information.  They do not
    suppress a query because map presence does not prove that every requested
    equilibrium or condition is complete.
    """

    reference_by_pair: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for row in base_eq_map_card.get("equilibrium_networks", []) or []:
        if not isinstance(row, dict):
            continue
        metal_id = _numeric_id(row.get("metal_id"), _METAL_RE)
        ligand_id = _numeric_id(row.get("ligand_id"), _LIGAND_RE)
        if metal_id is None or ligand_id is None:
            continue
        key = (metal_id, ligand_id)
        reference_by_pair.setdefault(key, []).append(row)
    for row in base_eq_map_card.get("pairs", []) or []:
        if not isinstance(row, dict):
            continue
        metal_id = _numeric_id(row.get("metal_id"), _METAL_RE)
        ligand_id = _numeric_id(row.get("ligand_id"), _LIGAND_RE)
        selected = row.get("selected_network_ids")
        if (
            metal_id is None or ligand_id is None
            or not isinstance(selected, list)
        ):
            continue
        coverage = reference_by_pair.setdefault((metal_id, ligand_id), [])
        for network_id in selected:
            parsed_network_id = _numeric_id(
                network_id, _NETWORK_RE
            )
            if parsed_network_id is not None:
                coverage.append({
                    "metal_id": metal_id,
                    "ligand_id": ligand_id,
                    "eq_network": f"ref_eq_net_{parsed_network_id}",
                })

    scopes: list[dict[str, Any]] = []
    for metal_id, metal_name in target_metals(chemical_system):
        for ligand_id, ligand_name in target_ligands(chemical_system):
            coverage = reference_by_pair.get((metal_id, ligand_id), [])
            scopes.append({
                "metal_id": metal_id,
                "metal_name": metal_name,
                "ligand_id": ligand_id,
                "ligand_name": ligand_name,
                "base_reference_network_count": len(coverage),
                "base_reference_networks": coverage,
            })
    return scopes


def run_prepare_pair_scopes(
    *,
    base_eq_map_card: dict[str, Any],
    target_chemical_system: dict[str, Any],
    purpose: str,
    tasks: str,
    chemical_context_plan: str | None,
    output_dir: str | Path,
    settings: LC13Settings,
    request_T_C: float,
    request_I_M: float,
) -> PairScopeResult:
    """Create fresh query sessions without invoking any model or search tool."""

    temperature = float(request_T_C)
    ionic_strength = float(request_I_M)
    if not math.isfinite(temperature):
        raise ValueError("request_T_C must be finite")
    if not math.isfinite(ionic_strength) or ionic_strength < 0.0:
        raise ValueError("request_I_M must be finite and nonnegative")

    root = Path(output_dir)
    query_root = root / "query_agents"
    mkdir(query_root, parents=True, exist_ok=True)
    write_json(root / "00_parent_request_context.json", {
        "artifact_kind": "LC1_3 parent request context",
        "estimation_enabled": True,
        "purpose": purpose,
        "tasks": tasks,
        "chemical_context_plan": chemical_context_plan,
        "query_interface": (
            "Each canonical pair receives one fresh, ordinary-prose chemistry "
            "question; parent prose is not appended to that pair question."
        ),
    })

    all_scopes = build_pair_scopes(
        chemical_system=target_chemical_system,
        base_eq_map_card=base_eq_map_card,
    )
    selected = all_scopes[: settings.max_query_runs]
    omitted_scopes = [
        {
            "metal_id": row["metal_id"],
            "metal_name": row["metal_name"],
            "ligand_id": row["ligand_id"],
            "ligand_name": row["ligand_name"],
            "reason": "LC1_3_MAX_QUERY_RUNS limit",
        }
        for row in all_scopes[settings.max_query_runs :]
    ]
    sessions: list[QuerySession] = []
    for index, scope in enumerate(selected, start=1):
        query_id = f"q{index:03d}"
        artifact_dir = query_root / query_id
        mkdir(artifact_dir, parents=True, exist_ok=True)
        write_json(artifact_dir / "scope.json", scope)
        sessions.append(QuerySession(
            query_id=query_id,
            scope=scope,
            artifact_dir=artifact_dir,
            memory=[],
            request_T_C=temperature,
            request_I_M=ionic_strength,
        ))

    manifest = {
        "stage": "prepare_pair_scopes",
        "selection_rule": "all canonical non-water metal-ligand pairs",
        "model_calls": 0,
        "tool_calls": 0,
        "n_scopes": len(sessions),
        "n_total_scopes": len(all_scopes),
        "n_omitted_scopes": len(omitted_scopes),
        "omitted_scopes": omitted_scopes,
        "queries": [
            {
                "query_id": row.query_id,
                "scope": row.scope,
                "artifact_dir": str(row.artifact_dir),
            }
            for row in sessions
        ],
    }
    manifest_path = root / "01_prepare_pair_scopes_manifest.json"
    write_json(manifest_path, manifest)
    return PairScopeResult(
        sessions=sessions,
        manifest_path=str(manifest_path),
        omitted_scopes=omitted_scopes,
    )


__all__ = [
    "PairScopeResult",
    "build_pair_scopes",
    "run_prepare_pair_scopes",
    "target_ligands",
    "target_metals",
]
