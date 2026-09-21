"""
Equilibrium Map Helpers Package

Provides utilities for building equilibrium network maps from VLM data.
"""

from .data_structures import (
    # Constants
    CONSTANT_TYPE_K,
    CONSTANT_TYPE_H,
    CONSTANT_TYPE_S,
    CONSTANT_TYPE_UNSPECIFIED,
    CONSTANT_TYPE_NAMES,
    DEFAULT_TEMPERATURE,
    DEFAULT_TEMP_TOLERANCE,
    DEFAULT_IONIC_STRENGTH,
    DEFAULT_IONIC_TOLERANCE,
    # Data structures
    EquilibriumNode,
    EquilibriumEdge,
    EquilibriumNetwork,
    ConditionBin,
    MetalLigandEquilibriumMap,
    MetalLigandEquilibriumMapCollection,
)

from .species_utils import (
    # JSON utilities (internal but exposed for use)
    _safe_get_scalar,
    _parse_json_safe,
    # Species extraction
    extract_species_from_equation_tree,
    extract_species_from_beta_definition,
)

from .filtering import (
    # Constant type filtering
    filter_by_constant_type,
    # Soft filters
    apply_soft_temperature_filter,
    apply_soft_ionic_filter,
    apply_combined_soft_filter,
    # Deduplication
    calculate_condition_distance,
    deduplicate_by_closest_conditions,
    # Condition analysis
    find_most_popular_conditions,
    bin_conditions,
)

from .network_builder import (
    # Node creation
    create_node_from_entry,
    create_nodes_from_entries,
    # Edge creation
    find_edges_by_shared_species,
    # Connected components
    find_connected_components,
    # Network building
    build_network_from_component,
    build_all_networks,
)


__all__ = [
    # === Constants ===
    "CONSTANT_TYPE_K",
    "CONSTANT_TYPE_H",
    "CONSTANT_TYPE_S",
    "CONSTANT_TYPE_UNSPECIFIED",
    "CONSTANT_TYPE_NAMES",
    "DEFAULT_TEMPERATURE",
    "DEFAULT_TEMP_TOLERANCE",
    "DEFAULT_IONIC_STRENGTH",
    "DEFAULT_IONIC_TOLERANCE",
    
    # === Data structures ===
    "EquilibriumNode",
    "EquilibriumEdge",
    "EquilibriumNetwork",
    "ConditionBin",
    "MetalLigandEquilibriumMap",
    "MetalLigandEquilibriumMapCollection",
    
    # === Species utilities ===
    "_safe_get_scalar",
    "_parse_json_safe",
    "extract_species_from_equation_tree",
    "extract_species_from_beta_definition",
    
    # === Filtering ===
    "filter_by_constant_type",
    "apply_soft_temperature_filter",
    "apply_soft_ionic_filter",
    "apply_combined_soft_filter",
    "calculate_condition_distance",
    "deduplicate_by_closest_conditions",
    "find_most_popular_conditions",
    "bin_conditions",
    
    # === Network building ===
    "create_node_from_entry",
    "create_nodes_from_entries",
    "find_edges_by_shared_species",
    "find_connected_components",
    "build_network_from_component",
    "build_all_networks",
]
