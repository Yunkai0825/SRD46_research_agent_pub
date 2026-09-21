"""
Data structures for equilibrium network mapping.

Contains dataclasses for nodes, edges, networks, condition bins, and maps.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple


# =============================================================================
# Constants and configuration
# =============================================================================

# ConstantType values (from constanttyp table)
CONSTANT_TYPE_K = 3  # Equilibrium constant (K)
CONSTANT_TYPE_H = 2  # Enthalpy (ΔH)
CONSTANT_TYPE_S = 4  # Entropy (ΔS)
CONSTANT_TYPE_UNSPECIFIED = 1  # Unspecified (*)

CONSTANT_TYPE_NAMES = {
    1: '*',
    2: 'H',
    3: 'K',
    4: 'S',
}

# Default soft filter parameters
DEFAULT_TEMPERATURE = 25.0  # Target temperature (°C)
DEFAULT_TEMP_TOLERANCE = 5.0  # ±5°C tolerance for soft filter
DEFAULT_IONIC_STRENGTH = 0.1  # Target ionic strength
DEFAULT_IONIC_TOLERANCE = 0.15  # ±0.15 tolerance for ionic strength


# =============================================================================
# Node and Edge structures
# =============================================================================

@dataclass
class EquilibriumNode:
    """Represents an equilibrium entry as a node in the network."""
    
    vlm_id: int  # verkn_ligand_metalID
    entry_index: int  # Index in filtered entries DataFrame
    metal_id: int
    ligand_id: int
    beta_definition_id: int
    beta_definition_name: Optional[str]
    equation_python: Optional[str]
    constant_type: str  # 'K', 'H', 'S', '*'
    constant_value: Optional[float]
    temperature: Optional[float]
    ionic_strength: Optional[float]
    lhs_species: FrozenSet[str]  # Species on left-hand side (reactants)
    rhs_species: FrozenSet[str]  # Species on right-hand side (products)
    all_species: FrozenSet[str]  # Union of LHS and RHS
    
    # Flags for tracking
    is_duplicate: bool = False  # True if this is a duplicate entry not used in primary map
    used_in_map: bool = False  # True if included in a map
    
    def __hash__(self):
        return hash(self.vlm_id)
    
    def __eq__(self, other):
        if not isinstance(other, EquilibriumNode):
            return False
        return self.vlm_id == other.vlm_id
    
    def duplicate_key(self) -> Tuple[int, int, int]:
        """Key for identifying duplicates: (metal_id, ligand_id, beta_definition_id)."""
        return (self.metal_id, self.ligand_id, self.beta_definition_id)
    
    def condition_distance(
        self,
        target_temp: float = DEFAULT_TEMPERATURE,
        target_ionic: float = DEFAULT_IONIC_STRENGTH,
        temp_weight: float = 1.0,
        ionic_weight: float = 10.0,
    ) -> float:
        """Calculate distance from target conditions.
        
        Lower is better. Null values get a penalty.
        """
        dist = 0.0
        
        if self.temperature is not None:
            dist += temp_weight * abs(self.temperature - target_temp)
        else:
            dist += temp_weight * 10.0  # Penalty for missing temperature
        
        if self.ionic_strength is not None:
            dist += ionic_weight * abs(self.ionic_strength - target_ionic)
        else:
            dist += ionic_weight * 1.0  # Penalty for missing ionic strength
        
        return dist


@dataclass
class EquilibriumEdge:
    """Represents a connection between two equilibria sharing species."""
    
    node1_vlm_id: int
    node2_vlm_id: int
    shared_species: FrozenSet[str]
    
    def __hash__(self):
        return hash((min(self.node1_vlm_id, self.node2_vlm_id), 
                     max(self.node1_vlm_id, self.node2_vlm_id)))
    
    def __eq__(self, other):
        if not isinstance(other, EquilibriumEdge):
            return False
        return {self.node1_vlm_id, self.node2_vlm_id} == {other.node1_vlm_id, other.node2_vlm_id}


# =============================================================================
# Network and Map structures
# =============================================================================

@dataclass
class EquilibriumNetwork:
    """A connected network of equilibria sharing species."""
    
    network_id: int
    nodes: List[EquilibriumNode] = field(default_factory=list)
    edges: List[EquilibriumEdge] = field(default_factory=list)
    all_species: Set[str] = field(default_factory=set)
    
    # Adjacency for quick lookups: species -> list of vlm_ids
    species_to_nodes: Dict[str, List[int]] = field(default_factory=dict)
    # Node adjacency: vlm_id -> list of connected vlm_ids
    node_adjacency: Dict[int, List[int]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert network to serializable dictionary."""
        return {
            "network_id": self.network_id,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "all_species": sorted(self.all_species),
            "nodes": [
                {
                    "vlm_id": n.vlm_id,
                    "entry_index": n.entry_index,
                    "beta_definition_id": n.beta_definition_id,
                    "beta_definition_name": n.beta_definition_name,
                    "equation_python": n.equation_python,
                    "constant_type": n.constant_type,
                    "constant_value": n.constant_value,
                    "temperature": n.temperature,
                    "ionic_strength": n.ionic_strength,
                    "lhs_species": sorted(n.lhs_species),
                    "rhs_species": sorted(n.rhs_species),
                }
                for n in self.nodes
            ],
            "edges": [
                {
                    "node1_vlm_id": e.node1_vlm_id,
                    "node2_vlm_id": e.node2_vlm_id,
                    "shared_species": sorted(e.shared_species),
                }
                for e in self.edges
            ],
            "species_to_nodes": {k: v for k, v in self.species_to_nodes.items()},
            "node_adjacency": {str(k): v for k, v in self.node_adjacency.items()},
        }


@dataclass
class ConditionBin:
    """Represents a bin of experimental conditions (temperature + ionic strength)."""
    
    temperature: Optional[float]  # Representative temperature
    ionic_strength: Optional[float]  # Representative ionic strength
    temp_range: Tuple[Optional[float], Optional[float]] = (None, None)
    ionic_range: Tuple[Optional[float], Optional[float]] = (None, None)
    iteration: int = 0  # Which iteration this was built in
    
    def __hash__(self):
        return hash((self.temperature, self.ionic_strength, self.iteration))
    
    def __eq__(self, other):
        if not isinstance(other, ConditionBin):
            return False
        return (self.temperature == other.temperature and 
                self.ionic_strength == other.ionic_strength and
                self.iteration == other.iteration)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "temperature": self.temperature,
            "ionic_strength": self.ionic_strength,
            "temp_range": list(self.temp_range),
            "ionic_range": list(self.ionic_range),
            "iteration": self.iteration,
        }
    
    def label(self) -> str:
        """Human-readable label for this condition bin."""
        t = f"T={self.temperature:.1f}" if self.temperature is not None else "T=?"
        i = f"I={self.ionic_strength:.2f}" if self.ionic_strength is not None else "I=?"
        return f"{t}, {i} (iter {self.iteration})"


@dataclass
class MetalLigandEquilibriumMap:
    """Complete equilibrium map for a metal-ligand pair at specific conditions.
    
    Contains potentially multiple disconnected networks.
    """
    
    metal_id: int
    ligand_id: int
    metal_name: Optional[str] = None
    ligand_name: Optional[str] = None
    
    # Condition bin for this map
    condition: Optional[ConditionBin] = None
    
    # Source data
    source_vlm_ids: List[int] = field(default_factory=list)
    
    # Networks (potentially multiple disconnected subgraphs)
    networks: Dict[int, EquilibriumNetwork] = field(default_factory=dict)
    
    # Global species inventory
    all_species: Set[str] = field(default_factory=set)
    
    # VLM ID to network mapping
    vlm_to_network: Dict[int, int] = field(default_factory=dict)
    
    # Stray entries (duplicates not included in primary network)
    stray_vlm_ids: List[int] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert map to serializable dictionary."""
        return {
            "metal_id": self.metal_id,
            "ligand_id": self.ligand_id,
            "metal_name": self.metal_name,
            "ligand_name": self.ligand_name,
            "condition": self.condition.to_dict() if self.condition else None,
            "entry_count": len(self.source_vlm_ids),
            "network_count": len(self.networks),
            "stray_count": len(self.stray_vlm_ids),
            "all_species": sorted(self.all_species),
            "networks": {
                str(k): v.to_dict() for k, v in self.networks.items()
            },
            "vlm_to_network": {str(k): v for k, v in self.vlm_to_network.items()},
            "stray_vlm_ids": self.stray_vlm_ids,
        }


@dataclass
class MetalLigandEquilibriumMapCollection:
    """Collection of equilibrium maps for a metal-ligand pair across iterations."""
    
    metal_id: int
    ligand_id: int
    metal_name: Optional[str] = None
    ligand_name: Optional[str] = None
    
    # Maps indexed by iteration/condition key
    maps: Dict[str, MetalLigandEquilibriumMap] = field(default_factory=dict)
    
    # All nodes (for tracking usage)
    all_nodes: Dict[int, EquilibriumNode] = field(default_factory=dict)
    
    # Unassigned entries after all iterations
    unassigned_vlm_ids: List[int] = field(default_factory=list)
    
    # Summary statistics
    total_entries: int = 0
    total_networks: int = 0
    iterations_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "metal_id": self.metal_id,
            "ligand_id": self.ligand_id,
            "metal_name": self.metal_name,
            "ligand_name": self.ligand_name,
            "total_entries": self.total_entries,
            "total_networks": self.total_networks,
            "iterations_count": self.iterations_count,
            "unassigned_count": len(self.unassigned_vlm_ids),
            "maps": {k: v.to_dict() for k, v in self.maps.items()},
        }


__all__ = [
    # Constants
    "CONSTANT_TYPE_K",
    "CONSTANT_TYPE_H",
    "CONSTANT_TYPE_S",
    "CONSTANT_TYPE_UNSPECIFIED",
    "CONSTANT_TYPE_NAMES",
    "DEFAULT_TEMPERATURE",
    "DEFAULT_TEMP_TOLERANCE",
    "DEFAULT_IONIC_STRENGTH",
    "DEFAULT_IONIC_TOLERANCE",
    # Data structures
    "EquilibriumNode",
    "EquilibriumEdge",
    "EquilibriumNetwork",
    "ConditionBin",
    "MetalLigandEquilibriumMap",
    "MetalLigandEquilibriumMapCollection",
]
