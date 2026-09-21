"""
pKa Chain Builder

Main orchestrator that builds complete pKa chains for ligands using 
the H+ equilibrium maps from the SQL database.

Produces output compatible with the original liganden_w_moldata_pKa.csv format.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

# Handle both package import and direct script execution
try:
    from .hplus_map_reader import HplusMapReader, HplusMapInfo, DEFAULT_SQL_PATH, DEFAULT_OUTPUT_PATH
    from .pka_extractor import (
        PKaRecord,
        extract_pka_from_network,
        build_pka_chain_from_records,
        build_pka_all_from_records,
    )
    from .step_parser import stage_to_token
except ImportError:
    from hplus_map_reader import HplusMapReader, HplusMapInfo, DEFAULT_SQL_PATH, DEFAULT_OUTPUT_PATH
    from pka_extractor import (
        PKaRecord,
        extract_pka_from_network,
        build_pka_chain_from_records,
        build_pka_all_from_records,
    )
    from step_parser import stage_to_token


# =============================================================================
# Data structures
# =============================================================================

@dataclass
class PKaStep:
    """A single pKa step (protonation edge)."""
    from_stage: int
    to_stage: int
    constant: Optional[float]
    temperature: Optional[float]
    ionic_strength: Optional[float]
    vlm_id: int
    beta_id: int
    is_valid: bool
    
    @property
    def edge_label(self) -> str:
        return f"{stage_to_token(self.from_stage)}->{stage_to_token(self.to_stage)}"
    
    @property
    def edge_key(self) -> str:
        return f"{self.from_stage}->{self.to_stage}"


@dataclass
class PKaChain:
    """Complete pKa chain for a ligand."""
    ligand_id: int
    ligand_name: Optional[str]
    map_temperature: Optional[float]  # From primary (closest) map
    map_ionic_strength: Optional[float]  # From primary (closest) map
    steps: List[PKaStep] = field(default_factory=list)  # Preferred (one per edge)
    all_steps: List[PKaStep] = field(default_factory=list)  # ALL records from all maps
    
    # Raw JSON representations for backward compatibility
    pref_json: Dict = field(default_factory=dict)
    all_json: Dict = field(default_factory=dict)
    
    @property
    def n_steps(self) -> int:
        """Number of preferred steps (unique edges)."""
        return len(self.steps)
    
    @property
    def n_all_records(self) -> int:
        """Total number of records from all maps."""
        return len(self.all_steps)
    
    def get_records_for_edge(self, from_stage: int, to_stage: int) -> List[PKaStep]:
        """Get all records for a specific edge."""
        return [s for s in self.all_steps 
                if s.from_stage == from_stage and s.to_stage == to_stage]
    
    @property
    def stages(self) -> Set[int]:
        """All stages covered by this chain."""
        s = set()
        for step in self.steps:
            s.add(step.from_stage)
            s.add(step.to_stage)
        return s
    
    def to_pref_json_str(self) -> str:
        """Convert preferred steps to JSON string."""
        return json.dumps(self.pref_json)
    
    def to_all_json_str(self) -> str:
        """Convert all steps to JSON string."""
        return json.dumps(self.all_json)


# =============================================================================
# Single ligand pKa extraction
# =============================================================================

def build_pka_for_ligand(
    ligand_id: int,
    target_temperature: float = 25.0,
    target_ionic_strength: float = 0.1,
    db_path: Path = DEFAULT_SQL_PATH,
    include_all: bool = True,
    temp_tolerance: float = 5.0,
    ionic_tolerance: float = 0.15,
) -> Optional[PKaChain]:
    """Build pKa chain for a single ligand.
    
    Aggregates pKa records from ALL maps within tolerance of target conditions,
    not just the single closest map. This ensures comprehensive coverage when
    multiple maps have similar conditions but different pKa steps.
    
    Args:
        ligand_id: Ligand ID to process
        target_temperature: Target temperature (°C)
        target_ionic_strength: Target ionic strength (M)
        db_path: Path to SQL database
        include_all: Whether to include all candidates (not just preferred)
        temp_tolerance: Temperature tolerance for map selection (°C)
        ionic_tolerance: Ionic strength tolerance for map selection (M)
        
    Returns:
        PKaChain or None if no H+ data for this ligand
    """
    with HplusMapReader(db_path) as reader:
        # Find ALL maps within tolerance (returns closest-first sorted list)
        maps = reader.find_maps_within_tolerance(
            ligand_id, target_temperature, target_ionic_strength,
            temp_tolerance, ionic_tolerance
        )
        
        if not maps:
            return None
        
        # Use closest map's info for the chain metadata
        primary_map = maps[0]
        
        # Aggregate pKa records from ALL maps within tolerance
        all_records: List[PKaRecord] = []
        seen_networks = set()  # Avoid duplicate networks if maps share them
        
        for map_info in maps:
            networks = reader.get_networks_for_map(map_info.map_id)
            
            for network in networks:
                net_id = network["network_db_id"]
                if net_id in seen_networks:
                    continue
                seen_networks.add(net_id)
                
                nodes = reader.get_nodes_for_network(net_id)
                records = extract_pka_from_network(nodes)
                all_records.extend(records)
        
        if not all_records:
            return PKaChain(
                ligand_id=ligand_id,
                ligand_name=primary_map.ligand_name,
                map_temperature=primary_map.temperature,
                map_ionic_strength=primary_map.ionic_strength,
            )
        
        # Build chain structures
        pref_json = build_pka_chain_from_records(
            all_records, target_temperature, target_ionic_strength
        )
        all_json = build_pka_all_from_records(all_records) if include_all else {}
        
        # Convert ALL records to PKaStep objects (from all maps within tolerance)
        all_steps = []
        for rec in all_records:
            all_steps.append(PKaStep(
                from_stage=rec.from_stage,
                to_stage=rec.to_stage,
                constant=rec.constant_value,
                temperature=rec.temperature,
                ionic_strength=rec.ionic_strength,
                vlm_id=rec.vlm_id,
                beta_id=rec.beta_definition_id,
                is_valid=rec.is_valid_step,
            ))
        
        # Sort all_steps by (from_stage, temperature, ionic_strength)
        all_steps.sort(key=lambda s: (s.from_stage, s.temperature or 0, s.ionic_strength or 0))
        
        # Build preferred steps (one per edge, closest to target)
        pref_steps = []
        for edge_key, rec_dict in pref_json.items():
            pref_steps.append(PKaStep(
                from_stage=rec_dict["from_stage"],
                to_stage=rec_dict["to_stage"],
                constant=float(rec_dict["constant"]) if rec_dict.get("constant") else None,
                temperature=float(rec_dict["temperature"]) if rec_dict.get("temperature") else None,
                ionic_strength=float(rec_dict["ionicstrength"]) if rec_dict.get("ionicstrength") else None,
                vlm_id=int(rec_dict["vlm_id"]),
                beta_id=int(rec_dict["beta_id"]),
                is_valid=True,
            ))
        
        # Sort preferred steps by from_stage
        pref_steps.sort(key=lambda s: s.from_stage)
        
        return PKaChain(
            ligand_id=ligand_id,
            ligand_name=primary_map.ligand_name,
            map_temperature=primary_map.temperature,
            map_ionic_strength=primary_map.ionic_strength,
            steps=pref_steps,
            all_steps=all_steps,
            pref_json=pref_json,
            all_json=all_json,
        )


# =============================================================================
# Batch processing
# =============================================================================

def build_pka_for_all_ligands(
    target_temperature: float = 25.0,
    target_ionic_strength: float = 0.1,
    db_path: Path = DEFAULT_SQL_PATH,
    include_all: bool = False,
    verbose: bool = True,
) -> Dict[int, PKaChain]:
    """Build pKa chains for all ligands with H+ data.
    
    Args:
        target_temperature: Target temperature (°C)
        target_ionic_strength: Target ionic strength (M)
        db_path: Path to SQL database
        include_all: Whether to include all candidates
        verbose: Print progress
        
    Returns:
        Dict mapping ligand_id to PKaChain
    """
    results: Dict[int, PKaChain] = {}
    
    with HplusMapReader(db_path) as reader:
        ligand_ids = reader.get_all_ligand_ids_with_hplus()
        
        if verbose:
            print(f"Processing {len(ligand_ids)} ligands with H+ data...")
        
        for i, ligand_id in enumerate(ligand_ids):
            if verbose and (i + 1) % 100 == 0:
                print(f"  [{i + 1}/{len(ligand_ids)}]")
            
            chain = build_pka_for_ligand(
                ligand_id,
                target_temperature,
                target_ionic_strength,
                db_path,
                include_all,
            )
            
            if chain is not None:
                results[ligand_id] = chain
    
    if verbose:
        print(f"Built pKa chains for {len(results)} ligands")
    
    return results


# =============================================================================
# DataFrame output (compatible with original format)
# =============================================================================

def pka_chains_to_dataframe(
    chains: Dict[int, PKaChain],
    include_all_json: bool = False,
) -> pd.DataFrame:
    """Convert pKa chains to DataFrame.
    
    Args:
        chains: Dict of ligand_id -> PKaChain
        include_all_json: Whether to include step_constants_all_json column
        
    Returns:
        DataFrame with columns matching original liganden_w_moldata_pKa format
    """
    rows = []
    
    for ligand_id, chain in chains.items():
        row = {
            "ligandenID": str(ligand_id),
            "ligand_name": chain.ligand_name,
            "n_pka_steps": chain.n_steps,
            "pka_stages": ",".join(str(s) for s in sorted(chain.stages)),
            "map_temperature": chain.map_temperature,
            "map_ionic_strength": chain.map_ionic_strength,
            "step_constants_pref_json": chain.to_pref_json_str(),
        }
        
        if include_all_json:
            row["step_constants_all_json"] = chain.to_all_json_str()
        
        rows.append(row)
    
    return pd.DataFrame(rows)


def attach_pka_to_liganden(
    liganden_df: pd.DataFrame,
    chains: Dict[int, PKaChain],
    include_all_json: bool = False,
    fill_empty_json: bool = True,
) -> pd.DataFrame:
    """Attach pKa data to existing liganden DataFrame.
    
    Args:
        liganden_df: Original liganden DataFrame
        chains: Dict of ligand_id -> PKaChain
        include_all_json: Whether to include step_constants_all_json
        fill_empty_json: Fill missing ligands with empty JSON "{}"
        
    Returns:
        DataFrame with pKa columns added
    """
    df = liganden_df.copy()
    
    # Ensure ligandenID is string for matching
    if "ligandenID" in df.columns:
        df["ligandenID"] = df["ligandenID"].astype(str)
    
    # Build lookup
    pref_lookup = {}
    all_lookup = {}
    
    for ligand_id, chain in chains.items():
        key = str(ligand_id)
        pref_lookup[key] = chain.to_pref_json_str()
        all_lookup[key] = chain.to_all_json_str()
    
    # Add columns
    if "ligandenID" in df.columns:
        df["step_constants_pref_json"] = df["ligandenID"].map(pref_lookup)
        
        if fill_empty_json:
            df["step_constants_pref_json"] = df["step_constants_pref_json"].fillna("{}")
        
        if include_all_json:
            df["step_constants_all_json"] = df["ligandenID"].map(all_lookup)
            if fill_empty_json:
                df["step_constants_all_json"] = df["step_constants_all_json"].fillna("{}")
    
    return df


# =============================================================================
# CLI interface
# =============================================================================

def main():
    """Command-line interface for pKa chain building."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Build pKa chains from H+ equilibrium maps"
    )
    parser.add_argument(
        "--temperature", "-t",
        type=float,
        default=25.0,
        help="Target temperature (°C)"
    )
    parser.add_argument(
        "--ionic", "-i",
        type=float,
        default=0.1,
        help="Target ionic strength (M)"
    )
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Path to SQL database"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Output CSV path"
    )
    parser.add_argument(
        "--ligand",
        type=int,
        default=None,
        help="Process single ligand (for testing)"
    )
    parser.add_argument(
        "--include-all",
        action="store_true",
        help="Include all candidates JSON"
    )
    
    args = parser.parse_args()
    
    db_path = Path(args.db) if args.db else DEFAULT_SQL_PATH
    
    if args.ligand:
        # Single ligand
        chain = build_pka_for_ligand(
            args.ligand,
            args.temperature,
            args.ionic,
            db_path,
            args.include_all,
        )
        
        if chain:
            print(f"Ligand {args.ligand}: {chain.ligand_name}")
            print(f"  Map T={chain.map_temperature}°C, I={chain.map_ionic_strength}M")
            print(f"  Steps: {chain.n_steps}")
            for step in chain.steps:
                print(f"    {step.edge_label}: pKa = {step.constant}")
        else:
            print(f"No H+ data for ligand {args.ligand}")
    
    else:
        # All ligands
        chains = build_pka_for_all_ligands(
            args.temperature,
            args.ionic,
            db_path,
            args.include_all,
        )
        
        df = pka_chains_to_dataframe(chains, args.include_all)
        
        if args.output:
            output_path = Path(args.output)
        else:
            # Use dedicated output directory
            output_path = DEFAULT_OUTPUT_PATH / "ligand_pka_chains.csv"
            output_path.parent.mkdir(parents=True, exist_ok=True)
        
        df.to_csv(output_path, index=False)
        print(f"Saved {len(df)} ligand pKa chains to: {output_path}")


if __name__ == "__main__":
    main()
