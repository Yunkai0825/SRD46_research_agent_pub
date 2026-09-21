"""Create session-local LC2 working maps from measured and support nodes."""

from __future__ import annotations

import json
import hashlib
import math
import os
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Collection, Iterable, Mapping


ESTIMATED_SOURCE = "SRD46 query estimated values"
_ADAPTED_NODE_FIELDS = {
    "node_db_id", "vlm_id", "constant_type", "log_K", "temperature",
    "ionic_strength", "equation_python", "beta_definition_id",
    "beta_definition_name", "metal_id", "ligand_id", "LHS_species_json",
    "RHS_species_json", "_estimated_provenance",
}


class SessionWorkingMapError(ValueError):
    """The LC1_3 working-map publication is stale, altered, or unsafe."""


@dataclass(frozen=True)
class LoadedSessionWorkingMap:
    path: Path
    sha256: str
    payload: Mapping[str, list[dict[str, Any]]]
    rows_by_pair: Mapping[tuple[int, int], tuple[dict[str, Any], ...]]


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _positive_int(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SessionWorkingMapError(
            f"{where} must be a positive canonical SRD46 identifier"
        )
    return value


def _flat_component_id(value: Any, prefix: str, where: str) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    match = re.fullmatch(rf"{re.escape(prefix)}_(\d+)", str(value).strip())
    if match is None or int(match.group(1)) <= 0:
        raise SessionWorkingMapError(
            f"{where} must identify a canonical {prefix}_N"
        )
    return int(match.group(1))


def _base_selected_pairs(
    base_eq_map_card: Mapping[str, Any],
) -> dict[tuple[int, int], list[int]]:
    selected: dict[tuple[int, int], list[int]] = {}
    if "pairs" in base_eq_map_card:
        raw_pairs = base_eq_map_card.get("pairs")
        if not isinstance(raw_pairs, list):
            raise SessionWorkingMapError("base_eq_map_card.pairs must be a list")
        for index, pair in enumerate(raw_pairs):
            if not isinstance(pair, Mapping):
                raise SessionWorkingMapError(f"base pairs[{index}] must be an object")
            key = (int(pair["metal_id"]), int(pair["ligand_id"]))
            ids = [int(value) for value in pair.get("selected_network_ids", [])]
            selected[key] = ids
        return selected
    networks = base_eq_map_card.get("equilibrium_networks", [])
    if not isinstance(networks, list):
        raise SessionWorkingMapError(
            "base_eq_map_card.equilibrium_networks must be a list"
        )
    for index, entry in enumerate(networks):
        if not isinstance(entry, Mapping):
            raise SessionWorkingMapError(
                f"base equilibrium_networks[{index}] must be an object"
            )
        match = re.fullmatch(r"ref_eq_net_(\d+)", str(entry.get("eq_network", "")))
        if match is None or int(match.group(1)) <= 0:
            raise SessionWorkingMapError(
                f"base equilibrium_networks[{index}].eq_network is not canonical"
            )
        key = (
            _flat_component_id(
                entry["metal_id"], "metal", f"equilibrium_networks[{index}].metal_id"
            ),
            _flat_component_id(
                entry["ligand_id"], "ligand", f"equilibrium_networks[{index}].ligand_id"
            ),
        )
        selected[key] = [int(match.group(1))]
    return selected


def load_session_working_map(
    session_working_map_path: str | Path,
    *,
    expected_session_working_map_sha256: str,
    support_rows_by_pair: Mapping[
        tuple[int, int], Iterable[Mapping[str, Any]]
    ],
    base_eq_map_card: Mapping[str, Any],
    allowed_system_pairs: Collection[tuple[int, int]],
) -> LoadedSessionWorkingMap:
    """Verify LC1_3's map receipt and exact binding to revalidated support rows."""

    if re.fullmatch(
        r"[0-9a-f]{64}", str(expected_session_working_map_sha256)
    ) is None:
        raise SessionWorkingMapError(
            "expected_session_working_map_sha256 must be a lowercase SHA-256 digest"
        )
    path = Path(session_working_map_path).resolve()
    try:
        raw = _read_bytes(path)
    except OSError as exc:
        raise SessionWorkingMapError(
            f"cannot read session working map {path}: {exc}"
        ) from exc
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if actual_sha256 != expected_session_working_map_sha256:
        raise SessionWorkingMapError(
            "session working map SHA-256 does not match the LC1_3 publication receipt"
        )
    try:
        document = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise SessionWorkingMapError(
            f"session working map is not valid JSON: {exc}"
        ) from exc
    if not isinstance(document, dict) or set(document) != {"pairs"}:
        raise SessionWorkingMapError(
            "session working map must use exactly the existing pairs root field"
        )
    if not isinstance(document["pairs"], list):
        raise SessionWorkingMapError("session working map pairs must be a list")

    allowed = {(int(mid), int(lid)) for mid, lid in allowed_system_pairs}
    base_selected = _base_selected_pairs(base_eq_map_card)
    expected = {
        (int(pair[0]), int(pair[1])): tuple(deepcopy(list(rows)))
        for pair, rows in support_rows_by_pair.items()
    }
    actual_rows: dict[tuple[int, int], tuple[dict[str, Any], ...]] = {}
    seen: set[tuple[int, int]] = set()
    for index, pair in enumerate(document["pairs"]):
        if not isinstance(pair, dict):
            raise SessionWorkingMapError(f"pairs[{index}] must be an object")
        required = {"metal_id", "ligand_id", "selected_network_ids"}
        allowed_fields = required | {"vlm_overrides", "estimated_eq_nodes"}
        if not required.issubset(pair) or not set(pair).issubset(allowed_fields):
            raise SessionWorkingMapError(f"pairs[{index}] has an invalid map schema")
        key = (
            _positive_int(pair["metal_id"], f"pairs[{index}].metal_id"),
            _positive_int(pair["ligand_id"], f"pairs[{index}].ligand_id"),
        )
        if key in seen:
            raise SessionWorkingMapError(f"duplicate session working pair {key!r}")
        seen.add(key)
        if key not in allowed:
            raise SessionWorkingMapError(
                f"session working pair metal_{key[0]}/ligand_{key[1]} is outside "
                "the active system catalog"
            )
        selected_ids = pair["selected_network_ids"]
        if not isinstance(selected_ids, list) or any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in selected_ids
        ):
            raise SessionWorkingMapError(
                f"pairs[{index}].selected_network_ids must contain canonical IDs"
            )
        expected_selected = base_selected.get(key, [])
        if selected_ids != expected_selected:
            raise SessionWorkingMapError(
                "session working map changed/fabricated the selected reference "
                f"networks for metal_{key[0]}/ligand_{key[1]}"
            )
        rows = pair.get("estimated_eq_nodes", [])
        if not isinstance(rows, list):
            raise SessionWorkingMapError(
                f"pairs[{index}].estimated_eq_nodes must be a list"
            )
        expected_rows = list(expected.get(key, ()))
        if _canonical_json(rows) != _canonical_json(expected_rows):
            raise SessionWorkingMapError(
                "session working map estimated nodes differ from the revalidated "
                f"support sidecar for metal_{key[0]}/ligand_{key[1]}"
            )
        if rows:
            for row_index, row in enumerate(rows):
                if not isinstance(row, dict) or set(row) != _ADAPTED_NODE_FIELDS:
                    raise SessionWorkingMapError(
                        f"estimated_eq_nodes[{row_index}] has an invalid schema"
                    )
                if int(row["node_db_id"]) >= 0 or int(row["vlm_id"]) >= 0:
                    raise SessionWorkingMapError(
                        "estimated nodes must retain negative session identifiers"
                    )
                if (int(row["metal_id"]), int(row["ligand_id"])) != key:
                    raise SessionWorkingMapError(
                        "estimated node belongs to another chemical pair"
                    )
                provenance = row["_estimated_provenance"]
                if (
                    not isinstance(provenance, dict)
                    or provenance.get("source") != ESTIMATED_SOURCE
                    or int(provenance.get("session_vlm_id", 0)) != int(row["vlm_id"])
                    or not str(provenance.get("query_id") or "").strip()
                ):
                    raise SessionWorkingMapError(
                        "estimated node lacks its session/query provenance binding"
                    )
            actual_rows[key] = tuple(deepcopy(rows))
    if set(actual_rows) != set(expected):
        raise SessionWorkingMapError(
            "session working map support-pair set differs from the native sidecar"
        )
    return LoadedSessionWorkingMap(
        path=path,
        sha256=actual_sha256,
        payload=document,
        rows_by_pair=actual_rows,
    )


def _winlong(path: str | Path) -> str:
    value = os.path.abspath(os.fspath(path))
    if os.name != "nt" or value.startswith("\\\\?\\"):
        return value
    if value.startswith("\\\\"):
        return "\\\\?\\UNC\\" + value[2:]
    return "\\\\?\\" + value


def _read_text(path: str | Path) -> str:
    with open(_winlong(path), "r", encoding="utf-8") as handle:
        return handle.read()


def _read_bytes(path: str | Path) -> bytes:
    with open(_winlong(path), "rb") as handle:
        return handle.read()


def _write_text(path: str | Path, value: str) -> None:
    with open(_winlong(path), "w", encoding="utf-8") as handle:
        handle.write(value)


def _mkdir(path: str | Path) -> None:
    os.makedirs(_winlong(path), exist_ok=True)


def select_rows_at_conditions(
    rows: Iterable[dict[str, Any]],
    *,
    temperature: float,
    ionic_strength: float,
) -> list[dict[str, Any]]:
    """Select the support map iteration matching one LC2 pair card."""

    available = list(rows)
    selected = [
        deepcopy(row)
        for row in available
        if math.isclose(
            float(row["temperature"]), float(temperature),
            rel_tol=0.0, abs_tol=1e-6,
        )
        and math.isclose(
            float(row["ionic_strength"]), float(ionic_strength),
            rel_tol=0.0, abs_tol=1e-12,
        )
    ]
    if not selected:
        conditions = sorted({
            (float(row["temperature"]), float(row["ionic_strength"]))
            for row in available
        })
        raise ValueError(
            "LC1_3 support has no iteration at the pair-card conditions "
            f"T={temperature}, I={ionic_strength}; available={conditions!r}"
        )
    return selected


def amend_measured_working_map(
    *,
    maps_json_path: str | Path,
    metal_id: int,
    ligand_id: int,
    estimated_rows: list[dict[str, Any]],
    output_path: str | Path,
) -> str:
    """Copy a measured selection map and add native support rows to its pair."""

    source = Path(maps_json_path)
    target = Path(output_path)
    if source.resolve() == target.resolve():
        raise ValueError(
            "session working-map output must not overwrite its measured source map"
        )
    payload = json.loads(_read_text(source))
    matches = [
        pair for pair in payload.get("pairs", [])
        if int(pair.get("metal_id")) == int(metal_id)
        and int(pair.get("ligand_id")) == int(ligand_id)
    ]
    if len(matches) != 1:
        raise ValueError(
            "measured working map must contain exactly one target pair for "
            f"metal_{metal_id}/ligand_{ligand_id}; found {len(matches)}"
        )
    matches[0]["estimated_eq_nodes"] = deepcopy(estimated_rows)
    _mkdir(target.parent)
    _write_text(target, json.dumps(payload, indent=2, ensure_ascii=False))
    return str(target)


def _network_id(tag: Any) -> int:
    match = re.search(r"(\d+)$", str(tag))
    if match is None:
        raise ValueError(f"cannot parse authoritative network ID from {tag!r}")
    return int(match.group(1))


def build_support_only_working_map(
    *,
    metal_id: int,
    ligand_id: int,
    estimated_rows: list[dict[str, Any]],
    auxiliary_networks: Iterable[dict[str, Any]],
    output_dir: str | Path,
) -> dict[str, str]:
    """Persist a target support pair plus optional measured auxiliaries.

    The target pair deliberately has ``selected_network_ids=[]``; its only
    rows are the validated negative-ID session nodes.  Auxiliary hydroxide or
    protonation pairs retain their real ``ref_eq_net_*`` selections, and any
    LC1_2 ``patch_notes.patches`` they carry are translated into
    ``vlm_overrides`` exactly as :func:`extract_maps_json` does for the
    reference cards — otherwise the shared dependency species would be
    materialized unpatched and clash with the patched reference card during
    the LC2 merge.
    """
    # Lazy import: keeps this stdlib-only module light and avoids import
    # cycles with the json-cards-builder package at module load time.
    from LC2_free_energy_card_building.LC2_1_card_initializer.ref_eq_SRD46_json_cards_builder.json_cards_builder_helpers.lc1_2_patch_adapter import (
        lc1_2_patches_to_vlm_overrides,
    )

    root = Path(output_dir)
    _mkdir(root)
    ids_payload: dict[str, list[dict[str, int]]] = {
        "metals": [{"metal_id": int(metal_id)}],
        "ligands": [{"ligand_id": int(ligand_id)}],
    }
    maps_payload: dict[str, list[dict[str, Any]]] = {
        "pairs": [{
            "metal_id": int(metal_id),
            "ligand_id": int(ligand_id),
            "selected_network_ids": [],
            "estimated_eq_nodes": deepcopy(estimated_rows),
        }],
    }
    measured_auxiliary: list[dict[str, Any]] = []
    seen_pairs = {(int(metal_id), int(ligand_id))}
    metal_ids = {int(metal_id)}
    ligand_ids = {int(ligand_id)}
    for entry in auxiliary_networks:
        mid = int(str(entry["metal_id"]).split("_")[-1])
        lid = int(str(entry["ligand_id"]).split("_")[-1])
        pair = (mid, lid)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        metal_ids.add(mid)
        ligand_ids.add(lid)
        measured_auxiliary.append(deepcopy(entry))
        aux_pair: dict[str, Any] = {
            "metal_id": mid,
            "ligand_id": lid,
            "selected_network_ids": [_network_id(entry["eq_network"])],
        }
        patches = (entry.get("patch_notes") or {}).get("patches") or []
        if patches:
            aux_pair["vlm_overrides"] = lc1_2_patches_to_vlm_overrides(
                patches, metal_id=mid, ligand_id=lid,
            )
        maps_payload["pairs"].append(aux_pair)
    ids_payload["metals"] = [{"metal_id": value} for value in sorted(metal_ids)]
    ids_payload["ligands"] = [{"ligand_id": value} for value in sorted(ligand_ids)]

    ids_path = root / "ids_working.json"
    maps_path = root / "maps_with_estimates.json"
    augmented_path = root / "augmented_networks_working.json"
    _write_text(ids_path, json.dumps(ids_payload, indent=2))
    _write_text(maps_path, json.dumps(maps_payload, indent=2, ensure_ascii=False))
    _write_text(augmented_path, json.dumps({
            "support_only_target": {
                "metal_id": int(metal_id),
                "ligand_id": int(ligand_id),
                "selected_network_ids": [],
                "estimated_node_db_ids": [
                    int(row["node_db_id"]) for row in estimated_rows
                ],
            },
            "measured_auxiliary_networks": measured_auxiliary,
        }, indent=2, ensure_ascii=False))
    return {
        "ids_json_path": str(ids_path),
        "maps_json_path": str(maps_path),
        "augmented_networks_path": str(augmented_path),
    }


__all__ = [
    "LoadedSessionWorkingMap",
    "SessionWorkingMapError",
    "amend_measured_working_map",
    "build_support_only_working_map",
    "load_session_working_map",
    "select_rows_at_conditions",
]
