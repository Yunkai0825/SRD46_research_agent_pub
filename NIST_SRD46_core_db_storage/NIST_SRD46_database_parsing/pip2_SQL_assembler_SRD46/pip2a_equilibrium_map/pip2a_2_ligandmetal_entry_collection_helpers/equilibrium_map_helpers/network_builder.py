"""
Network building utilities for equilibrium maps.

Handles:
- Node creation from entries
- Edge creation based on shared species
- Connected component detection (BFS)
- Network assembly
"""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Dict, FrozenSet, List, Optional, Set, Tuple, Union

import pandas as pd

from .data_structures import (
    CONSTANT_TYPE_NAMES,
    EquilibriumNode,
    EquilibriumEdge,
    EquilibriumNetwork,
)
from .species_utils import (
    _safe_get_scalar,
    _parse_json_safe,
    extract_species_from_beta_definition,
)


# =============================================================================
# Helper functions
# =============================================================================

def _safe_float(val) -> Optional[float]:
    """Safely convert a value to float, handling strings with parentheses like '(-0.5)'."""
    if val is None or pd.isna(val):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        # Try stripping parentheses
        if isinstance(val, str):
            cleaned = val.strip().strip('()').strip()
            try:
                return float(cleaned)
            except (ValueError, TypeError):
                pass
        return None


# =============================================================================
# Node creation
# =============================================================================

def create_node_from_entry(
    entry_row: pd.Series,
    entry_index: int,
    beta_df: pd.DataFrame,
    vlm_id_col: str = "verkn_ligand_metalID",
    metal_col: str = "metalNr",
    ligand_col: str = "ligandenNr",
    beta_col: str = "beta_definitionNr",
    constant_type_col: str = "constanttypNr",
    constant_val_col: str = "constant",
    temp_col: str = "temperature",
    ionic_col: str = "ionicstrength",
) -> Optional[EquilibriumNode]:
    """Create an EquilibriumNode from a VLM entry row.
    
    Args:
        entry_row: Row from VLM DataFrame
        entry_index: Index of this row
        beta_df: Beta definitions DataFrame (indexed by betaDefinitionID)
        Column name arguments for customization
        
    Returns:
        EquilibriumNode or None if creation fails
    """
    try:
        vlm_id = int(_safe_get_scalar(entry_row[vlm_id_col]))
        metal_id = int(_safe_get_scalar(entry_row[metal_col]))
        ligand_id = int(_safe_get_scalar(entry_row[ligand_col]))
        beta_id = int(_safe_get_scalar(entry_row[beta_col]))
        
        # Get constant type
        ct_nr = _safe_get_scalar(entry_row.get(constant_type_col))
        constant_type = CONSTANT_TYPE_NAMES.get(ct_nr, '?') if ct_nr is not None else '?'
        
        # Get constant value (handle strings with parentheses like '(-0.5)')
        const_val = _safe_get_scalar(entry_row.get(constant_val_col))
        if const_val is not None and not pd.isna(const_val):
            constant_value = _safe_float(const_val)
        else:
            constant_value = None
        
        # Get temperature
        temp_val = _safe_get_scalar(entry_row.get(temp_col))
        if temp_val is not None and not pd.isna(temp_val):
            temperature = _safe_float(temp_val)
        else:
            temperature = None
        
        # Get ionic strength
        ionic_val = _safe_get_scalar(entry_row.get(ionic_col))
        if ionic_val is not None and not pd.isna(ionic_val):
            ionic_strength = _safe_float(ionic_val)
        else:
            ionic_strength = None
        
        # Look up beta definition
        beta_name = None
        equation_python = None
        lhs_species = frozenset()
        rhs_species = frozenset()
        all_species = frozenset()
        
        if beta_id in beta_df.index:
            beta_row = beta_df.loc[beta_id]
            
            # Handle duplicate index case
            if isinstance(beta_row, pd.DataFrame):
                beta_row = beta_row.iloc[0]
            
            beta_name = _safe_get_scalar(beta_row.get("name_beta_definition"))
            equation_python = _safe_get_scalar(beta_row.get("equation_python"))
            
            # Extract species
            lhs_species, rhs_species, all_species = extract_species_from_beta_definition(
                beta_row, beta_id
            )
        
        return EquilibriumNode(
            vlm_id=vlm_id,
            entry_index=entry_index,
            metal_id=metal_id,
            ligand_id=ligand_id,
            beta_definition_id=beta_id,
            beta_definition_name=beta_name,
            equation_python=equation_python,
            constant_type=constant_type,
            constant_value=constant_value,
            temperature=temperature,
            ionic_strength=ionic_strength,
            lhs_species=lhs_species,
            rhs_species=rhs_species,
            all_species=all_species,
        )
        
    except Exception as e:
        # Log error but don't crash
        print(f"Warning: Failed to create node from entry {entry_index}: {e}")
        return None


def create_nodes_from_entries(
    entries_df: pd.DataFrame,
    beta_df: pd.DataFrame,
    **kwargs,
) -> Dict[int, EquilibriumNode]:
    """Create nodes from all entries in a DataFrame.
    
    Args:
        entries_df: VLM entries DataFrame
        beta_df: Beta definitions DataFrame
        **kwargs: Column name overrides
        
    Returns:
        Dict mapping vlm_id to EquilibriumNode
    """
    nodes: Dict[int, EquilibriumNode] = {}
    vlm_id_col = kwargs.get("vlm_id_col", "verkn_ligand_metalID")
    
    for idx, row in entries_df.iterrows():
        node = create_node_from_entry(row, idx, beta_df, **kwargs)
        if node:
            nodes[node.vlm_id] = node
    
    return nodes


# =============================================================================
# Edge creation
# =============================================================================

def find_edges_by_shared_species(
    nodes: Dict[int, EquilibriumNode],
    min_shared: int = 1,
) -> Tuple[List[EquilibriumEdge], Dict[str, List[int]]]:
    """Find all edges between nodes based on shared species.
    
    Args:
        nodes: Dict mapping vlm_id to node
        min_shared: Minimum number of shared species for an edge
        
    Returns:
        Tuple of (list of edges, species_to_nodes mapping)
    """
    # Build species -> nodes mapping
    species_to_nodes: Dict[str, List[int]] = defaultdict(list)
    
    for vlm_id, node in nodes.items():
        for species in node.all_species:
            species_to_nodes[species].append(vlm_id)
    
    # Find edges
    edges: List[EquilibriumEdge] = []
    seen_pairs: Set[Tuple[int, int]] = set()
    
    for vlm_id, node in nodes.items():
        for species in node.all_species:
            for other_vlm_id in species_to_nodes[species]:
                if other_vlm_id == vlm_id:
                    continue
                
                # Canonical pair (smaller first)
                pair = (min(vlm_id, other_vlm_id), max(vlm_id, other_vlm_id))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                
                # Calculate shared species
                other_node = nodes[other_vlm_id]
                shared = node.all_species & other_node.all_species
                
                if len(shared) >= min_shared:
                    edges.append(EquilibriumEdge(
                        node1_vlm_id=pair[0],
                        node2_vlm_id=pair[1],
                        shared_species=frozenset(shared),
                    ))
    
    return edges, dict(species_to_nodes)


# =============================================================================
# Connected component detection (BFS)
# =============================================================================

def find_connected_components(
    nodes: Dict[int, EquilibriumNode],
    edges: List[EquilibriumEdge],
) -> List[Set[int]]:
    """Find connected components using BFS.
    
    Args:
        nodes: Dict mapping vlm_id to node
        edges: List of edges
        
    Returns:
        List of sets, each containing vlm_ids of a connected component
    """
    if not nodes:
        return []
    
    # Build adjacency list
    adjacency: Dict[int, Set[int]] = defaultdict(set)
    for edge in edges:
        adjacency[edge.node1_vlm_id].add(edge.node2_vlm_id)
        adjacency[edge.node2_vlm_id].add(edge.node1_vlm_id)
    
    # BFS to find components
    visited: Set[int] = set()
    components: List[Set[int]] = []
    
    for start_vlm_id in nodes.keys():
        if start_vlm_id in visited:
            continue
        
        # BFS from this node
        component: Set[int] = set()
        queue = deque([start_vlm_id])
        
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            
            visited.add(current)
            component.add(current)
            
            # Add neighbors
            for neighbor in adjacency.get(current, set()):
                if neighbor not in visited:
                    queue.append(neighbor)
        
        if component:
            components.append(component)
    
    return components


# =============================================================================
# Network building
# =============================================================================

def build_network_from_component(
    network_id: int,
    component_vlm_ids: Set[int],
    nodes: Dict[int, EquilibriumNode],
    edges: List[EquilibriumEdge],
    species_to_nodes: Dict[str, List[int]],
) -> EquilibriumNetwork:
    """Build an EquilibriumNetwork from a connected component.
    
    Args:
        network_id: ID for this network
        component_vlm_ids: Set of vlm_ids in this component
        nodes: All nodes
        edges: All edges
        species_to_nodes: Species to node mapping
        
    Returns:
        EquilibriumNetwork object
    """
    # Filter nodes
    component_nodes = [nodes[vlm_id] for vlm_id in component_vlm_ids]
    
    # Filter edges
    component_edges = [
        e for e in edges
        if e.node1_vlm_id in component_vlm_ids and e.node2_vlm_id in component_vlm_ids
    ]
    
    # Collect all species
    all_species: Set[str] = set()
    for node in component_nodes:
        all_species.update(node.all_species)
    
    # Filter species_to_nodes for this component
    component_species_to_nodes: Dict[str, List[int]] = {}
    for species in all_species:
        component_species_to_nodes[species] = [
            vlm_id for vlm_id in species_to_nodes.get(species, [])
            if vlm_id in component_vlm_ids
        ]
    
    # Build node adjacency
    node_adjacency: Dict[int, List[int]] = defaultdict(list)
    for edge in component_edges:
        node_adjacency[edge.node1_vlm_id].append(edge.node2_vlm_id)
        node_adjacency[edge.node2_vlm_id].append(edge.node1_vlm_id)
    
    return EquilibriumNetwork(
        network_id=network_id,
        nodes=component_nodes,
        edges=component_edges,
        all_species=all_species,
        species_to_nodes=component_species_to_nodes,
        node_adjacency=dict(node_adjacency),
    )


def build_all_networks(
    nodes: Dict[int, EquilibriumNode],
) -> Tuple[List[EquilibriumNetwork], Dict[int, int], Dict[str, List[int]]]:
    """Build all networks from a set of nodes.
    
    Args:
        nodes: Dict mapping vlm_id to node
        
    Returns:
        Tuple of (list of networks, vlm_to_network mapping, species_to_nodes mapping)
    """
    # Find edges
    edges, species_to_nodes = find_edges_by_shared_species(nodes)
    
    # Find connected components
    components = find_connected_components(nodes, edges)
    
    # Build networks
    networks: List[EquilibriumNetwork] = []
    vlm_to_network: Dict[int, int] = {}
    
    for network_id, component in enumerate(components):
        network = build_network_from_component(
            network_id=network_id,
            component_vlm_ids=component,
            nodes=nodes,
            edges=edges,
            species_to_nodes=species_to_nodes,
        )
        networks.append(network)
        
        for vlm_id in component:
            vlm_to_network[vlm_id] = network_id
    
    return networks, vlm_to_network, species_to_nodes


__all__ = [
    # Node creation
    "create_node_from_entry",
    "create_nodes_from_entries",
    # Edge creation
    "find_edges_by_shared_species",
    # Connected components
    "find_connected_components",
    # Network building
    "build_network_from_component",
    "build_all_networks",
]
