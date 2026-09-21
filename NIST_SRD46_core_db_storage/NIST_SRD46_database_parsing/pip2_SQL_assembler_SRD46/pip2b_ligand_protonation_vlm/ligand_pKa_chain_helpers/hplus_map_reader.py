"""
H+ Map Reader

Reads H+ (proton) equilibrium maps from the SQL database and finds
the map closest to target temperature and ionic strength conditions.

The H+ metal ID is typically 68 in the SRD46 database.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Default paths (stand-alone use only; the pipeline passes the equilibrium-map DB explicitly)
BASE_DIR = Path(__file__).resolve().parents[3]          # project root (holds _output/)
DEFAULT_SQL_PATH = BASE_DIR / "_output" / "pip2c_cards_sql" / "srd46_equilibrium_maps.db"
DEFAULT_OUTPUT_PATH = BASE_DIR / "_output" / "pip2b_liganden_pKa_map_output"

# H+ metal ID in SRD46
HPLUS_METAL_ID = 68


@dataclass
class HplusMapInfo:
    """Information about an H+ equilibrium map."""
    collection_id: int
    map_id: int
    ligand_id: int
    ligand_name: Optional[str]
    iteration: int
    temperature: Optional[float]
    ionic_strength: Optional[float]
    network_count: int
    entry_count: int
    
    @property
    def has_conditions(self) -> bool:
        """Check if this map has valid temperature and ionic strength."""
        return self.temperature is not None and self.ionic_strength is not None
    
    def distance_to(self, target_temp: float, target_ionic: float, 
                    temp_weight: float = 1.0, ionic_weight: float = 10.0) -> float:
        """Calculate weighted distance to target conditions.
        
        Args:
            target_temp: Target temperature (°C)
            target_ionic: Target ionic strength (M)
            temp_weight: Weight for temperature difference
            ionic_weight: Weight for ionic strength difference
            
        Returns:
            Weighted distance score (lower is better)
        """
        if not self.has_conditions:
            return float('inf')
        
        temp_diff = abs(self.temperature - target_temp)
        ionic_diff = abs(self.ionic_strength - target_ionic)
        
        return temp_weight * temp_diff + ionic_weight * ionic_diff


class HplusMapReader:
    """Reader for H+ equilibrium maps from SQL database."""
    
    def __init__(self, db_path: Path = DEFAULT_SQL_PATH):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
    
    def __enter__(self) -> "HplusMapReader":
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
    
    def open(self) -> None:
        """Open database connection."""
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
    
    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def list_hplus_collections(self) -> List[Dict]:
        """List all H+ collections (metal_id = HPLUS_METAL_ID).
        
        Returns:
            List of collection dicts with ligand info
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT 
                collection_id, metal_id, ligand_id, metal_name, ligand_name,
                total_entries, total_networks, iterations_count
            FROM eq_map_collection
            WHERE metal_id = ?
            ORDER BY ligand_id
        """, (HPLUS_METAL_ID,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def list_maps_for_ligand(self, ligand_id: int) -> List[HplusMapInfo]:
        """List all H+ maps for a specific ligand.
        
        Args:
            ligand_id: Ligand ID to query
            
        Returns:
            List of HplusMapInfo objects for each map iteration
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT 
                c.collection_id, m.map_id, c.ligand_id, c.ligand_name,
                m.iteration, m.condition_temperature, m.condition_ionic_strength,
                m.network_count, m.entry_count
            FROM eq_map_collection c
            JOIN eq_map m ON c.collection_id = m.collection_id
            WHERE c.metal_id = ? AND c.ligand_id = ?
            ORDER BY m.iteration
        """, (HPLUS_METAL_ID, ligand_id))
        
        results = []
        for row in cursor.fetchall():
            results.append(HplusMapInfo(
                collection_id=row["collection_id"],
                map_id=row["map_id"],
                ligand_id=row["ligand_id"],
                ligand_name=row["ligand_name"],
                iteration=row["iteration"],
                temperature=row["condition_temperature"],
                ionic_strength=row["condition_ionic_strength"],
                network_count=row["network_count"],
                entry_count=row["entry_count"],
            ))
        
        return results
    
    def find_closest_map(
        self,
        ligand_id: int,
        target_temp: float = 25.0,
        target_ionic: float = 0.1,
        temp_weight: float = 1.0,
        ionic_weight: float = 10.0,
    ) -> Optional[HplusMapInfo]:
        """Find the H+ map closest to target conditions for a ligand.
        
        Args:
            ligand_id: Ligand ID
            target_temp: Target temperature (°C)
            target_ionic: Target ionic strength (M)
            temp_weight: Weight for temperature in distance calculation
            ionic_weight: Weight for ionic strength in distance calculation
            
        Returns:
            HplusMapInfo for the closest map, or None if no maps found
        """
        maps = self.list_maps_for_ligand(ligand_id)
        
        if not maps:
            return None
        
        # Find map with minimum distance
        best_map = None
        best_distance = float('inf')
        
        for map_info in maps:
            dist = map_info.distance_to(target_temp, target_ionic, temp_weight, ionic_weight)
            if dist < best_distance:
                best_distance = dist
                best_map = map_info
        
        return best_map
    
    def find_maps_within_tolerance(
        self,
        ligand_id: int,
        target_temp: float = 25.0,
        target_ionic: float = 0.1,
        temp_tolerance: float = 5.0,
        ionic_tolerance: float = 0.15,
    ) -> List[HplusMapInfo]:
        """Find all H+ maps within tolerance of target conditions.
        
        This allows aggregating records from multiple maps that are all
        reasonably close to the target conditions, providing better coverage.
        
        Args:
            ligand_id: Ligand ID
            target_temp: Target temperature (°C)
            target_ionic: Target ionic strength (M)
            temp_tolerance: Maximum temperature deviation (°C)
            ionic_tolerance: Maximum ionic strength deviation (M)
            
        Returns:
            List of HplusMapInfo objects within tolerance, sorted by distance
        """
        maps = self.list_maps_for_ligand(ligand_id)
        
        if not maps:
            return []
        
        # Filter maps within tolerance
        within_tol = []
        for map_info in maps:
            if not map_info.has_conditions:
                continue
            
            temp_ok = abs(map_info.temperature - target_temp) <= temp_tolerance
            ionic_ok = abs(map_info.ionic_strength - target_ionic) <= ionic_tolerance
            
            if temp_ok and ionic_ok:
                within_tol.append(map_info)
        
        # Sort by distance to target (closest first)
        within_tol.sort(key=lambda m: m.distance_to(target_temp, target_ionic))
        
        # If none within strict tolerance, fall back to closest single map
        if not within_tol:
            closest = self.find_closest_map(ligand_id, target_temp, target_ionic)
            if closest:
                return [closest]
        
        return within_tol
    
    def get_networks_for_map(self, map_id: int) -> List[Dict]:
        """Get all networks for a specific map.
        
        Args:
            map_id: Map ID
            
        Returns:
            List of network dicts
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT network_db_id, network_id, node_count, edge_count
            FROM eq_network
            WHERE map_id = ?
            ORDER BY network_id
        """, (map_id,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_nodes_for_network(self, network_db_id: int) -> List[Dict]:
        """Get all nodes for a specific network.
        
        Args:
            network_db_id: Network database ID
            
        Returns:
            List of node dicts with species info
        """
        cursor = self.conn.cursor()
        
        # Get nodes
        cursor.execute("""
            SELECT 
                node_db_id, vlm_id, entry_index,
                metal_id, ligand_id, beta_definition_id,
                beta_definition_name, equation_python,
                constant_type, constant_value,
                temperature, ionic_strength,
                is_duplicate, used_in_map
            FROM eq_node
            WHERE network_db_id = ?
        """, (network_db_id,))
        
        nodes = []
        for row in cursor.fetchall():
            node = dict(row)
            node["lhs_species"] = []
            node["rhs_species"] = []
            nodes.append(node)
        
        # Get species for each node
        node_by_id = {n["node_db_id"]: n for n in nodes}
        
        cursor.execute("""
            SELECT node_db_id, species, side
            FROM eq_node_species
            WHERE node_db_id IN ({})
        """.format(",".join("?" * len(node_by_id))), list(node_by_id.keys()))
        
        for row in cursor.fetchall():
            node = node_by_id.get(row["node_db_id"])
            if node:
                if row["side"] == "LHS":
                    node["lhs_species"].append(row["species"])
                elif row["side"] == "RHS":
                    node["rhs_species"].append(row["species"])
        
        return nodes
    
    def get_all_ligand_ids_with_hplus(self) -> List[int]:
        """Get all ligand IDs that have H+ maps.
        
        Returns:
            List of ligand IDs
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT DISTINCT ligand_id
            FROM eq_map_collection
            WHERE metal_id = ?
            ORDER BY ligand_id
        """, (HPLUS_METAL_ID,))
        
        return [row[0] for row in cursor.fetchall()]


def find_closest_hplus_map(
    ligand_id: int,
    target_temp: float = 25.0,
    target_ionic: float = 0.1,
    db_path: Path = DEFAULT_SQL_PATH,
) -> Optional[HplusMapInfo]:
    """Convenience function to find closest H+ map for a ligand.
    
    Args:
        ligand_id: Ligand ID
        target_temp: Target temperature (°C)
        target_ionic: Target ionic strength (M)
        db_path: Path to SQL database
        
    Returns:
        HplusMapInfo or None
    """
    with HplusMapReader(db_path) as reader:
        return reader.find_closest_map(ligand_id, target_temp, target_ionic)
