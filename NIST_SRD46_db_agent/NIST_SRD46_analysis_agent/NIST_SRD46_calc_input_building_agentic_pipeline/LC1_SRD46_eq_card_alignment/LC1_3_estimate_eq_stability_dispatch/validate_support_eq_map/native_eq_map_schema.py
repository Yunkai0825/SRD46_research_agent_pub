"""Frozen native table/column contract of ``srd46_equilibrium_maps.db``."""

from __future__ import annotations

from typing import Any


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


def empty_native_eq_map() -> dict[str, list[dict[str, Any]]]:
    return {table: [] for table in NATIVE_TABLE_COLUMNS}


__all__ = [
    "NATIVE_TABLE_COLUMNS",
    "PRIMARY_KEYS",
    "empty_native_eq_map",
]
