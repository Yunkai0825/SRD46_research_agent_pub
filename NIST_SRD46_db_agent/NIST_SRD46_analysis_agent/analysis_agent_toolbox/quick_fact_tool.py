"""LC1 quick-fact adapter over the existing SRD-46 query search tools."""

from __future__ import annotations

from typing import Any

from NIST_SRD46_core_db_search_tools import (
    parse_prefixed_id,
    search_ligands,
    search_metals,
)


def _exclude_for(prefix: str, exclude_ids: str) -> str | None:
    """Convert LC1 prefixed exclude IDs into the numeric CSV the shared search tools expect."""
    ids: list[str] = []
    for token in (exclude_ids or "").split(","):
        token = token.strip()
        if not token:
            continue
        if token.isdigit():
            ids.append(token)
            continue
        try:
            parsed_prefix, numeric_id = parse_prefixed_id(token)
        except ValueError:
            continue
        if parsed_prefix == prefix:
            ids.append(str(numeric_id))
    return ",".join(ids) or None


def _metal_match(row: dict[str, Any]) -> dict[str, Any]:
    pid = str(row.get("metal_id") or "")
    return {
        "entity_type": "metal",
        "prefix_id": pid,
        "name": row.get("metal_name") or row.get("symbol") or pid,
        "symbol": row.get("symbol") or "",
        "charge": row.get("charge"),
        "smiles": row.get("smiles") or "",
    }


def _ligand_match(row: dict[str, Any]) -> dict[str, Any]:
    pid = str(row.get("ligand_id") or "")
    return {
        "entity_type": "ligand",
        "prefix_id": pid,
        "name": row.get("ligand_name") or row.get("common_name") or pid,
        "formula": row.get("formula") or "",
        "ligand_class": row.get("ligand_class") or "",
        "smiles": row.get("smiles") or "",
    }


def _append_unique(matches: list[dict[str, Any]], rows: list[dict[str, Any]]) -> None:
    seen = {row.get("prefix_id") for row in matches}
    for row in rows:
        pid = row.get("prefix_id")
        if pid and pid not in seen:
            matches.append(row)
            seen.add(pid)


def _lookup_prefixed(prefix_id: str, limit: int) -> list[dict[str, Any]]:
    try:
        prefix, numeric_id = parse_prefixed_id(prefix_id)
    except ValueError:
        return []
    if prefix == "metal":
        return [_metal_match(row) for row in search_metals(metal_id=numeric_id, limit=limit)]
    if prefix == "ligand":
        data = search_ligands(ligand_id=numeric_id, limit=limit)
        return [_ligand_match(row) for row in data.get("results", [])]
    return []


def quick_fact(
    *,
    name: str = "",
    smiles: str = "",
    prefix_id: str = "",
    exclude_ids: str = "",
    limit: int = 12,
) -> dict[str, Any]:
    """Return compact metal/ligand search hits for LC1 ID alignment."""
    matches: list[dict[str, Any]] = []

    if prefix_id:
        matches.extend(_lookup_prefixed(prefix_id, limit))
    else:
        metal_exclude = _exclude_for("metal", exclude_ids)
        ligand_exclude = _exclude_for("ligand", exclude_ids)
        if name:
            _append_unique(
                matches,
                [_metal_match(row) for row in search_metals(name=name, limit=limit, exclude=metal_exclude)],
            )
            ligand_data = search_ligands(name=name, limit=limit, exclude=ligand_exclude)
            _append_unique(
                matches,
                [_ligand_match(row) for row in ligand_data.get("results", [])],
            )
        if smiles:
            _append_unique(
                matches,
                [_metal_match(row) for row in search_metals(smiles=smiles, limit=limit, exclude=metal_exclude)],
            )
            ligand_data = search_ligands(smiles=smiles, limit=limit, exclude=ligand_exclude)
            _append_unique(
                matches,
                [_ligand_match(row) for row in ligand_data.get("results", [])],
            )

    return {
        "query": {
            "name": name,
            "smiles": smiles,
            "prefix_id": prefix_id,
            "exclude_ids": exclude_ids,
        },
        "matches": matches[:limit],
        "count": len(matches[:limit]),
    }


def compact_quick_fact(data: dict[str, Any]) -> str:
    """Return a compact markdown table for LLM-facing search output."""
    matches = list(data.get("matches") or [])
    if not matches:
        return "_(no matches)_"

    rows = [
        "| type | prefix_id | name | detail |",
        "|---|---|---|---|",
    ]
    for row in matches:
        kind = str(row.get("entity_type") or "")
        pid = str(row.get("prefix_id") or "")
        name = str(row.get("name") or "")
        if kind == "metal":
            detail = f"symbol={row.get('symbol') or ''}; charge={row.get('charge')}"
        else:
            detail = f"formula={row.get('formula') or ''}; class={row.get('ligand_class') or ''}"
        rows.append(f"| {kind} | {pid} | {name} | {detail} |")
    return "\n".join(rows)
