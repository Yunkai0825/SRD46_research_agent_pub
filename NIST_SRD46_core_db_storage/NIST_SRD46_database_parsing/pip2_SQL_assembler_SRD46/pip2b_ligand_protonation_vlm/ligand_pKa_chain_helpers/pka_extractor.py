"""
pKa Extractor

Extracts pKa values (protonation step constants) from H+ equilibrium map networks.
Each node in an H+ network represents a beta value that may correspond to a 
protonation step.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

# Handle both package import and direct script execution
try:
    from .step_parser import (
        derive_step_from_node,
        edge_to_label,
        parse_stage_from_species,
        stage_to_token,
    )
except ImportError:
    from step_parser import (
        derive_step_from_node,
        edge_to_label,
        parse_stage_from_species,
        stage_to_token,
    )


@dataclass
class PKaRecord:
    """A single pKa record extracted from a node."""
    
    vlm_id: int
    beta_definition_id: int
    beta_definition_name: Optional[str]
    equation_python: Optional[str]
    
    from_stage: int
    to_stage: int
    edge_label: str
    
    constant_value: Optional[float]
    temperature: Optional[float]
    ionic_strength: Optional[float]
    
    is_valid_step: bool
    validation_reason: str
    protons_in_reaction: int
    
    # Raw species for debugging
    lhs_species: List[str] = field(default_factory=list)
    rhs_species: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "vlm_id": str(self.vlm_id),
            "beta_id": str(self.beta_definition_id),
            "from_stage": self.from_stage,
            "to_stage": self.to_stage,
            "edge_label": self.edge_label,
            "constant": self.constant_value,
            "temperature": str(self.temperature) if self.temperature is not None else None,
            "ionicstrength": str(self.ionic_strength) if self.ionic_strength is not None else None,
            "is_valid": self.is_valid_step,
            "reason": self.validation_reason,
            "protons": self.protons_in_reaction,
        }


def extract_pka_from_node(node: Dict) -> Optional[PKaRecord]:
    """Extract pKa record from a single node.
    
    Args:
        node: Node dict from database with species info
        
    Returns:
        PKaRecord or None if node doesn't represent a protonation step
    """
    # Get species sets
    lhs_species = frozenset(node.get("lhs_species", []))
    rhs_species = frozenset(node.get("rhs_species", []))
    
    # Derive step
    from_stage, to_stage, meta = derive_step_from_node(lhs_species, rhs_species)
    
    if from_stage is None or to_stage is None:
        return None
    
    return PKaRecord(
        vlm_id=node["vlm_id"],
        beta_definition_id=node["beta_definition_id"],
        beta_definition_name=node.get("beta_definition_name"),
        equation_python=node.get("equation_python"),
        from_stage=from_stage,
        to_stage=to_stage,
        edge_label=edge_to_label(from_stage, to_stage),
        constant_value=node.get("constant_value"),
        temperature=node.get("temperature"),
        ionic_strength=node.get("ionic_strength"),
        is_valid_step=meta["ok"],
        validation_reason=meta["reason"],
        protons_in_reaction=meta["protons"],
        lhs_species=list(lhs_species),
        rhs_species=list(rhs_species),
    )


def extract_pka_from_network(nodes: List[Dict]) -> List[PKaRecord]:
    """Extract all pKa records from a network's nodes.
    
    Args:
        nodes: List of node dicts from database
        
    Returns:
        List of PKaRecord objects
    """
    records = []
    
    for node in nodes:
        record = extract_pka_from_node(node)
        if record is not None:
            records.append(record)
    
    return records


def extract_all_pka_from_map(
    reader,  # HplusMapReader
    map_id: int,
) -> Dict[str, List[PKaRecord]]:
    """Extract all pKa records from all networks in a map.
    
    Args:
        reader: HplusMapReader instance
        map_id: Map ID to extract from
        
    Returns:
        Dict mapping edge_label to list of PKaRecords
    """
    networks = reader.get_networks_for_map(map_id)
    
    all_records: Dict[str, List[PKaRecord]] = {}
    
    for network in networks:
        nodes = reader.get_nodes_for_network(network["network_db_id"])
        records = extract_pka_from_network(nodes)
        
        for record in records:
            edge = record.edge_label
            if edge not in all_records:
                all_records[edge] = []
            all_records[edge].append(record)
    
    return all_records


def select_preferred_pka(
    records: List[PKaRecord],
    target_temp: float = 25.0,
    target_ionic: float = 0.1,
    prefer_valid_only: bool = True,
) -> Optional[PKaRecord]:
    """Select the preferred pKa record from a list of candidates.
    
    Selection criteria:
    1. Prefer valid steps (is_valid_step = True)
    2. Minimize distance to target conditions
    
    Args:
        records: List of PKaRecord candidates
        target_temp: Target temperature
        target_ionic: Target ionic strength
        prefer_valid_only: If True, only consider valid steps
        
    Returns:
        Best PKaRecord or None
    """
    if not records:
        return None
    
    # Filter to valid only if requested
    candidates = records
    if prefer_valid_only:
        valid = [r for r in records if r.is_valid_step]
        if valid:
            candidates = valid
    
    def score(r: PKaRecord) -> float:
        """Calculate distance score (lower is better)."""
        temp_diff = abs((r.temperature or 25.0) - target_temp)
        ionic_diff = abs((r.ionic_strength or 0.1) - target_ionic)
        return temp_diff + 10.0 * ionic_diff
    
    return min(candidates, key=score)


def group_pka_by_edge(records: List[PKaRecord]) -> Dict[str, List[PKaRecord]]:
    """Group pKa records by their edge label.
    
    Args:
        records: List of PKaRecord objects
        
    Returns:
        Dict mapping edge_label to list of records
    """
    grouped: Dict[str, List[PKaRecord]] = {}
    
    for record in records:
        edge = record.edge_label
        if edge not in grouped:
            grouped[edge] = []
        grouped[edge].append(record)
    
    return grouped


def build_pka_chain_from_records(
    records: List[PKaRecord],
    target_temp: float = 25.0,
    target_ionic: float = 0.1,
) -> Dict[str, Dict]:
    """Build a pKa chain (preferred record per edge) from records.
    
    This produces the same structure as step_constants_pref_json in the 
    original code.
    
    Args:
        records: List of PKaRecord objects
        target_temp: Target temperature
        target_ionic: Target ionic strength
        
    Returns:
        Dict mapping edge_key (e.g., "0->1") to preferred record dict
    """
    grouped = group_pka_by_edge(records)
    
    chain = {}
    for edge, candidates in grouped.items():
        preferred = select_preferred_pka(candidates, target_temp, target_ionic)
        if preferred:
            # Create edge key in format "from->to"
            edge_key = f"{preferred.from_stage}->{preferred.to_stage}"
            
            # Add quality flags
            temp_off = (preferred.temperature is None or 
                       abs(preferred.temperature - target_temp) > 5.0)
            ionic_high = (preferred.ionic_strength is None or 
                         preferred.ionic_strength > 0.2)
            ionic_hard = (preferred.ionic_strength is not None and 
                         preferred.ionic_strength > 0.5)
            
            chain[edge_key] = {
                "vlm_id": str(preferred.vlm_id),
                "beta_id": str(preferred.beta_definition_id),
                "from_stage": preferred.from_stage,
                "to_stage": preferred.to_stage,
                "edge_label": preferred.edge_label,
                "constant": (str(preferred.constant_value) 
                           if preferred.constant_value is not None else None),
                "constant_sic": (str(preferred.constant_value)
                               if preferred.constant_value is not None else None),
                "temperature": (str(preferred.temperature)
                              if preferred.temperature is not None else None),
                "ionicstrength": (str(preferred.ionic_strength)
                                if preferred.ionic_strength is not None else None),
                "flags": {
                    "temp_off": temp_off,
                    "ionic_high": ionic_high,
                    "ionic_hard": ionic_hard,
                },
            }
    
    return chain


def build_pka_all_from_records(records: List[PKaRecord]) -> Dict[str, List[Dict]]:
    """Build all pKa records per edge.
    
    This produces the same structure as step_constants_all_json in the
    original code.
    
    Args:
        records: List of PKaRecord objects
        
    Returns:
        Dict mapping edge_key to list of record dicts
    """
    grouped = group_pka_by_edge(records)
    
    all_json = {}
    for edge, candidates in grouped.items():
        if candidates:
            # Use first candidate to get edge key format
            first = candidates[0]
            edge_key = f"{first.from_stage}->{first.to_stage}"
            
            all_json[edge_key] = [
                {
                    "vlm_id": str(r.vlm_id),
                    "beta_id": str(r.beta_definition_id),
                    "from_stage": r.from_stage,
                    "to_stage": r.to_stage,
                    "edge_label": r.edge_label,
                    "constant": (str(r.constant_value)
                               if r.constant_value is not None else None),
                    "constant_sic": (str(r.constant_value)
                                   if r.constant_value is not None else None),
                    "temperature": (str(r.temperature)
                                  if r.temperature is not None else None),
                    "ionicstrength": (str(r.ionic_strength)
                                    if r.ionic_strength is not None else None),
                }
                for r in candidates
            ]
    
    return all_json
