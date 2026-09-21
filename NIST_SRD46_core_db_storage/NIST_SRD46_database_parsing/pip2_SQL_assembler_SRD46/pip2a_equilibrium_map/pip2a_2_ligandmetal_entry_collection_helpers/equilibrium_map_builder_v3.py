"""
Equilibrium Map Builder v3

Builds equilibrium network maps for metal-ligand pairs from VLM data.

Key features:
- Uses CSV-backed probes (no JSON schema dataclasses)
- Filters by constantType K only
- Soft temperature filter (target ± tolerance)
- Soft ionic strength filter (target ± tolerance)
- Deduplication: for same (metal, ligand, beta), keep closest to target
- Iterative building: find most popular conditions in remaining entries

Usage:
    from equilibrium_map_builder_v3 import build_equilibrium_maps_for_pair
    
    collection = build_equilibrium_maps_for_pair(
        metal_id=112,
        ligand_id=10103,
        max_iterations=5,
    )
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

# =============================================================================
# Logging configuration
# =============================================================================

logger = logging.getLogger(__name__)

def setup_logging(level: int = logging.INFO, log_file: Optional[Path] = None) -> None:
    """Configure logging for the equilibrium map builder.
    
    Args:
        level: Logging level (default: INFO)
        log_file: Optional path to log file
    """
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    
    # Configure logger
    logger.setLevel(level)
    logger.handlers.clear()
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)

# Import helpers
from equilibrium_map_helpers import (
    # Constants
    CONSTANT_TYPE_K,
    DEFAULT_TEMPERATURE,
    DEFAULT_TEMP_TOLERANCE,
    DEFAULT_IONIC_STRENGTH,
    DEFAULT_IONIC_TOLERANCE,
    # Data structures
    EquilibriumNode,
    EquilibriumNetwork,
    ConditionBin,
    MetalLigandEquilibriumMap,
    MetalLigandEquilibriumMapCollection,
    # Species utilities
    _safe_get_scalar,
    # Filtering
    filter_by_constant_type,
    apply_combined_soft_filter,
    deduplicate_by_closest_conditions,
    find_most_popular_conditions,
    bin_conditions,
    # Network building
    create_nodes_from_entries,
    build_all_networks,
)


# =============================================================================
# Path configuration
# =============================================================================

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
INPUT_DIR = BASE_DIR / "_input" / "pip1_parsed_individual_SRD46"

# CSV file paths
VLM_CSV_PATH = INPUT_DIR / "verkn_ligand_metal__16__8-11-2-5-6-14.csv"
BETA_DEF_CSV_PATH = INPUT_DIR / "pip1a_beta_definition_parsed" / "beta_definition_augmented.csv"
METAL_CSV_PATH = INPUT_DIR / "pip1b_metal_parsed" / "metal_augmented.csv"
LIGAND_CSV_PATH = INPUT_DIR / "pip1c_liganden_parsed" / "liganden_w_moldata_qupkake_parsed.csv"


# =============================================================================
# Cached data loaders
# =============================================================================

@lru_cache(maxsize=1)
def load_vlm_data() -> pd.DataFrame:
    """Load the VLM (verkn_ligand_metal) table."""
    if not VLM_CSV_PATH.exists():
        raise FileNotFoundError(f"VLM CSV not found: {VLM_CSV_PATH}")
    return pd.read_csv(VLM_CSV_PATH)


@lru_cache(maxsize=1)
def load_beta_definitions() -> pd.DataFrame:
    """Load beta definitions, indexed by beta_definitionID."""
    if not BETA_DEF_CSV_PATH.exists():
        raise FileNotFoundError(f"Beta definition CSV not found: {BETA_DEF_CSV_PATH}")
    df = pd.read_csv(BETA_DEF_CSV_PATH)
    if "beta_definitionID" in df.columns:
        df = df.set_index("beta_definitionID", drop=False)
    return df


@lru_cache(maxsize=1)
def load_metals() -> pd.DataFrame:
    """Load metals table, indexed by metalID."""
    if not METAL_CSV_PATH.exists():
        raise FileNotFoundError(f"Metal CSV not found: {METAL_CSV_PATH}")
    df = pd.read_csv(METAL_CSV_PATH)
    if "metalID" in df.columns:
        df = df.set_index("metalID", drop=False)
    return df


@lru_cache(maxsize=1)
def load_ligands() -> pd.DataFrame:
    """Load ligands table, indexed by ligandenID."""
    if not LIGAND_CSV_PATH.exists():
        raise FileNotFoundError(f"Ligand CSV not found: {LIGAND_CSV_PATH}")
    df = pd.read_csv(LIGAND_CSV_PATH, low_memory=False)
    if "ligandenID" in df.columns:
        df = df.set_index("ligandenID", drop=False)
    return df


def get_metal_name(metal_id: int) -> Optional[str]:
    """Get metal name by ID."""
    metals_df = load_metals()
    if metal_id in metals_df.index:
        row = metals_df.loc[metal_id]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        return _safe_get_scalar(row.get("name_metal"))
    return None


def get_ligand_name(ligand_id: int) -> Optional[str]:
    """Get ligand name by ID."""
    ligands_df = load_ligands()
    if ligand_id in ligands_df.index:
        row = ligands_df.loc[ligand_id]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        return _safe_get_scalar(row.get("name_ligand"))
    return None


# =============================================================================
# Entry filtering for a metal-ligand pair
# =============================================================================

# VLM column name mapping (actual names use Nr suffix)
VLM_COLS = {
    "vlm_id": "verkn_ligand_metalID",
    "metal_id": "metalNr",
    "ligand_id": "ligandenNr",
    "beta_id": "beta_definitionNr",
    "constant_type": "constanttypNr",
    "temperature": "temperature",
    "ionic_strength": "ionicstrength",
    "constant_value": "constant",
}


def get_entries_for_pair(
    metal_id: int,
    ligand_id: int,
    constant_type: int = CONSTANT_TYPE_K,
) -> pd.DataFrame:
    """Get all VLM entries for a metal-ligand pair.
    
    Args:
        metal_id: Metal ID
        ligand_id: Ligand ID
        constant_type: Filter by constant type (default: K=3)
        
    Returns:
        Filtered DataFrame
    """
    vlm_df = load_vlm_data()
    
    # Filter by metal and ligand (use Nr columns)
    metal_col = VLM_COLS["metal_id"]
    ligand_col = VLM_COLS["ligand_id"]
    mask = (vlm_df[metal_col] == metal_id) & (vlm_df[ligand_col] == ligand_id)
    entries = vlm_df[mask].copy()
    
    logger.debug(f"get_entries_for_pair: M={metal_id}, L={ligand_id} -> {len(entries)} raw entries")
    
    # Filter by constant type
    if constant_type is not None:
        entries = filter_by_constant_type(entries, constant_type)
        logger.debug(f"get_entries_for_pair: After K-type filter -> {len(entries)} entries")
    
    return entries


# =============================================================================
# Single iteration map builder
# =============================================================================

def build_single_iteration_map(
    entries_df: pd.DataFrame,
    metal_id: int,
    ligand_id: int,
    target_temp: float,
    temp_tolerance: float,
    target_ionic: float,
    ionic_tolerance: float,
    iteration: int,
    beta_df: pd.DataFrame,
    metal_name: Optional[str] = None,
    ligand_name: Optional[str] = None,
) -> Tuple[MetalLigandEquilibriumMap, pd.DataFrame]:
    """Build a single equilibrium map for one iteration.
    
    Args:
        entries_df: DataFrame of entries to consider
        metal_id, ligand_id: IDs
        target_temp, temp_tolerance: Temperature target and tolerance
        target_ionic, ionic_tolerance: Ionic strength target and tolerance
        iteration: Iteration number
        beta_df: Beta definitions DataFrame
        metal_name, ligand_name: Optional names
        
    Returns:
        Tuple of (MetalLigandEquilibriumMap, remaining entries DataFrame)
    """
    logger.debug(f"build_single_iteration_map: iter={iteration}, input={len(entries_df)} entries, "
                 f"T={target_temp}±{temp_tolerance}, I={target_ionic}±{ionic_tolerance}")
    
    # 1. Apply soft condition filters
    filtered = apply_combined_soft_filter(
        entries_df,
        target_temp=target_temp,
        temp_tolerance=temp_tolerance,
        target_ionic=target_ionic,
        ionic_tolerance=ionic_tolerance,
    )
    
    logger.debug(f"  -> After soft filter: {len(filtered)} entries (dropped {len(entries_df) - len(filtered)})")
    
    if filtered.empty:
        # Return empty map and original entries
        empty_map = MetalLigandEquilibriumMap(
            metal_id=metal_id,
            ligand_id=ligand_id,
            metal_name=metal_name,
            ligand_name=ligand_name,
            condition=bin_conditions(
                filtered, target_temp, temp_tolerance,
                target_ionic, ionic_tolerance, iteration=iteration
            ),
        )
        logger.debug(f"  -> Empty after soft filter, returning original {len(entries_df)} entries")
        return empty_map, entries_df
    
    # 2. Deduplicate by closest conditions
    deduped, stray = deduplicate_by_closest_conditions(
        filtered,
        target_temp=target_temp,
        target_ionic=target_ionic,
    )
    
    logger.debug(f"  -> After dedup: {len(deduped)} kept, {len(stray)} stray (duplicates)")
    
    # 3. Create nodes from deduped entries
    nodes = create_nodes_from_entries(deduped, beta_df)
    
    logger.debug(f"  -> Created {len(nodes)} nodes from entries")
    
    if not nodes:
        empty_map = MetalLigandEquilibriumMap(
            metal_id=metal_id,
            ligand_id=ligand_id,
            metal_name=metal_name,
            ligand_name=ligand_name,
            condition=bin_conditions(
                deduped, target_temp, temp_tolerance,
                target_ionic, ionic_tolerance, iteration=iteration
            ),
        )
        logger.debug(f"  -> No nodes created, returning original {len(entries_df)} entries")
        return empty_map, entries_df
    
    # 4. Build networks
    networks, vlm_to_network, species_to_nodes = build_all_networks(nodes)
    
    logger.debug(f"  -> Built {len(networks)} networks from {len(nodes)} nodes")
    
    # 5. Create condition bin
    condition = bin_conditions(
        deduped, target_temp, temp_tolerance,
        target_ionic, ionic_tolerance, iteration=iteration
    )
    
    # 6. Collect all species
    all_species: Set[str] = set()
    for network in networks:
        all_species.update(network.all_species)
    
    logger.debug(f"  -> Total species across networks: {len(all_species)}")
    
    # 7. Create map
    eq_map = MetalLigandEquilibriumMap(
        metal_id=metal_id,
        ligand_id=ligand_id,
        metal_name=metal_name,
        ligand_name=ligand_name,
        condition=condition,
        source_vlm_ids=list(nodes.keys()),
        networks={n.network_id: n for n in networks},
        all_species=all_species,
        vlm_to_network=vlm_to_network,
        stray_vlm_ids=list(stray["verkn_ligand_metalID"]) if not stray.empty else [],
    )
    
    # 8. Calculate remaining entries (exclude those used)
    used_vlm_ids = set(nodes.keys())
    vlm_id_col = "verkn_ligand_metalID"
    remaining = entries_df[~entries_df[vlm_id_col].isin(used_vlm_ids)].copy()
    
    return eq_map, remaining


# =============================================================================
# Iterative map builder (main entry point)
# =============================================================================

def build_equilibrium_maps_for_pair(
    metal_id: int,
    ligand_id: int,
    constant_type: int = CONSTANT_TYPE_K,
    initial_target_temp: float = DEFAULT_TEMPERATURE,
    temp_tolerance: float = DEFAULT_TEMP_TOLERANCE,
    initial_target_ionic: float = DEFAULT_IONIC_STRENGTH,
    ionic_tolerance: float = DEFAULT_IONIC_TOLERANCE,
    max_iterations: int = 10,
    min_entries_per_iter: int = 1,
) -> MetalLigandEquilibriumMapCollection:
    """Build all equilibrium maps for a metal-ligand pair iteratively.
    
    Process:
    1. Start with target conditions (25°C, 0.1 ionic)
    2. Build map with entries matching those conditions
    3. From remaining entries, find most popular conditions
    4. Repeat until no entries remain or max iterations
    
    Args:
        metal_id, ligand_id: IDs for the pair
        constant_type: Filter by constant type (default: K=3)
        initial_target_temp, temp_tolerance: Initial temperature target
        initial_target_ionic, ionic_tolerance: Initial ionic target
        max_iterations: Maximum number of iterations
        min_entries_per_iter: Minimum entries needed to continue
        
    Returns:
        MetalLigandEquilibriumMapCollection with all maps
    """
    logger.info(f"build_equilibrium_maps_for_pair: M={metal_id} ({get_metal_name(metal_id)}), "
                f"L={ligand_id} ({get_ligand_name(ligand_id)})")
    
    # Load data
    beta_df = load_beta_definitions()
    metal_name = get_metal_name(metal_id)
    ligand_name = get_ligand_name(ligand_id)
    
    # Get all entries for this pair
    all_entries = get_entries_for_pair(metal_id, ligand_id, constant_type)
    
    logger.info(f"  Found {len(all_entries)} K-type entries for this pair")
    
    # Initialize collection
    collection = MetalLigandEquilibriumMapCollection(
        metal_id=metal_id,
        ligand_id=ligand_id,
        metal_name=metal_name,
        ligand_name=ligand_name,
        total_entries=len(all_entries),
    )
    
    if all_entries.empty:
        logger.info(f"  No entries found, returning empty collection")
        return collection
    
    # Iterative building
    remaining = all_entries.copy()
    current_temp = initial_target_temp
    current_ionic = initial_target_ionic
    
    for iteration in range(max_iterations):
        if len(remaining) < min_entries_per_iter:
            logger.debug(f"  Iter {iteration}: Stopping - only {len(remaining)} entries remaining (min={min_entries_per_iter})")
            break
        
        logger.debug(f"  Iter {iteration}: Processing {len(remaining)} entries at T={current_temp:.1f}, I={current_ionic:.2f}")
        
        # Build map for current conditions
        eq_map, remaining = build_single_iteration_map(
            entries_df=remaining,
            metal_id=metal_id,
            ligand_id=ligand_id,
            target_temp=current_temp,
            temp_tolerance=temp_tolerance,
            target_ionic=current_ionic,
            ionic_tolerance=ionic_tolerance,
            iteration=iteration,
            beta_df=beta_df,
            metal_name=metal_name,
            ligand_name=ligand_name,
        )
        
        # Only add non-empty maps
        if eq_map.networks:
            map_key = f"iter_{iteration}_T{current_temp:.1f}_I{current_ionic:.2f}"
            collection.maps[map_key] = eq_map
            collection.total_networks += len(eq_map.networks)
            logger.debug(f"  Iter {iteration}: Added map '{map_key}' with {len(eq_map.networks)} networks")
            
            # Store nodes
            for network in eq_map.networks.values():
                for node in network.nodes:
                    collection.all_nodes[node.vlm_id] = node
        else:
            logger.debug(f"  Iter {iteration}: No networks built")
        
        # Check if we got any results
        if not eq_map.networks:
            # No entries matched, try finding popular conditions in remaining
            pass  # Fall through to condition finding
        
        # If no remaining entries, we're done
        if remaining.empty:
            logger.debug(f"  Iter {iteration}: No remaining entries, stopping")
            break
        
        # Find most popular conditions in remaining entries
        pop_temp, pop_ionic, pop_count = find_most_popular_conditions(remaining)
        
        logger.debug(f"  Iter {iteration}: Most popular conditions in remaining: T={pop_temp}, I={pop_ionic} ({pop_count} entries)")
        
        if pop_temp is None and pop_ionic is None:
            # Can't determine conditions, done
            logger.debug(f"  Iter {iteration}: Cannot determine popular conditions, stopping")
            break
        
        # Use popular conditions as new target
        if pop_temp is not None:
            current_temp = pop_temp
        if pop_ionic is not None:
            current_ionic = pop_ionic
        
        # If the new conditions are very close to the old ones and we got no results,
        # widen the tolerance slightly for next iteration
        if not eq_map.networks:
            temp_tolerance = min(temp_tolerance * 1.5, 20.0)
            ionic_tolerance = min(ionic_tolerance * 1.5, 1.0)
            logger.debug(f"  Iter {iteration}: Widening tolerances to T±{temp_tolerance:.1f}, I±{ionic_tolerance:.2f}")
    
    # Record unassigned entries
    if not remaining.empty:
        collection.unassigned_vlm_ids = list(remaining["verkn_ligand_metalID"])
        logger.debug(f"  Final: {len(collection.unassigned_vlm_ids)} unassigned entries")
    
    collection.iterations_count = len(collection.maps)
    
    logger.info(f"  Complete: {collection.iterations_count} iterations, {collection.total_networks} networks, "
                f"{len(collection.all_nodes)} nodes, {len(collection.unassigned_vlm_ids)} unassigned")
    
    return collection


# =============================================================================
# Query utilities
# =============================================================================

def summarize_collection(collection: MetalLigandEquilibriumMapCollection) -> Dict[str, Any]:
    """Generate a summary of a map collection."""
    return {
        "metal_id": collection.metal_id,
        "metal_name": collection.metal_name,
        "ligand_id": collection.ligand_id,
        "ligand_name": collection.ligand_name,
        "total_entries": collection.total_entries,
        "total_networks": collection.total_networks,
        "iterations_count": collection.iterations_count,
        "unassigned_count": len(collection.unassigned_vlm_ids),
        "maps": [
            {
                "key": key,
                "condition": eq_map.condition.label() if eq_map.condition else "N/A",
                "network_count": len(eq_map.networks),
                "entry_count": len(eq_map.source_vlm_ids),
            }
            for key, eq_map in collection.maps.items()
        ],
    }


def print_collection_summary(collection: MetalLigandEquilibriumMapCollection) -> None:
    """Print a human-readable summary."""
    summary = summarize_collection(collection)
    
    print(f"\n{'='*60}")
    print(f"Metal-Ligand Equilibrium Map Collection")
    print(f"{'='*60}")
    print(f"Metal: {summary['metal_name']} (ID={summary['metal_id']})")
    print(f"Ligand: {summary['ligand_name']} (ID={summary['ligand_id']})")
    print(f"Total VLM entries (K-type): {summary['total_entries']}")
    print(f"Iterations: {summary['iterations_count']}")
    print(f"Total networks: {summary['total_networks']}")
    print(f"Unassigned entries: {summary['unassigned_count']}")
    
    if summary['maps']:
        print(f"\nMaps:")
        for m in summary['maps']:
            print(f"  - {m['key']}: {m['condition']} | "
                  f"{m['network_count']} networks, {m['entry_count']} entries")
    
    print(f"{'='*60}\n")


# =============================================================================
# Main (for testing)
# =============================================================================

if __name__ == "__main__":
    print("Equilibrium Map Builder v3")
    print(f"VLM path: {VLM_CSV_PATH}")
    print(f"Beta path: {BETA_DEF_CSV_PATH}")
    
    # Test with a known pair
    # Ni(112) + L(10103) has 60 entries
    test_metal = 112
    test_ligand = 10103
    
    print(f"\nBuilding maps for Metal={test_metal}, Ligand={test_ligand}...")
    
    collection = build_equilibrium_maps_for_pair(
        metal_id=test_metal,
        ligand_id=test_ligand,
        max_iterations=5,
    )
    
    print_collection_summary(collection)
    
    # Show some network details
    for key, eq_map in collection.maps.items():
        for net_id, network in eq_map.networks.items():
            print(f"\n{key} / Network {net_id}:")
            print(f"  Nodes: {len(network.nodes)}")
            print(f"  All species: {network.all_species}")
