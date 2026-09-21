"""
Ligand pKa Chain Helpers

Extracts pKa values (protonation step constants) from H+ equilibrium maps
stored in the SQL database.

Modules:
- hplus_map_reader: Read H+ equilibrium maps from SQL database
- step_parser: Parse HxL stages from species strings
- pka_extractor: Extract pKa values from H+ map networks
- pka_chain_builder: Build complete pKa chains for ligands

Usage:
    from ligand_pKa_chain_helpers import build_pka_for_ligand
    
    result = build_pka_for_ligand(
        ligand_id=10113,
        target_temperature=25.0,
        target_ionic_strength=0.1,
    )
"""

from .hplus_map_reader import (
    HplusMapReader,
    find_closest_hplus_map,
    DEFAULT_SQL_PATH,
    DEFAULT_OUTPUT_PATH,
)
from .step_parser import (
    parse_stage_from_species,
    derive_step_from_node_pair,
    stage_to_token,
)
from .pka_extractor import (
    extract_pka_from_network,
    extract_all_pka_from_map,
)
from .pka_chain_builder import (
    build_pka_for_ligand,
    build_pka_for_all_ligands,
    PKaStep,
    PKaChain,
)

__all__ = [
    # Reader
    "HplusMapReader",
    "find_closest_hplus_map",
    "DEFAULT_SQL_PATH",
    "DEFAULT_OUTPUT_PATH",
    # Parser
    "parse_stage_from_species",
    "derive_step_from_node_pair",
    "stage_to_token",
    # Extractor
    "extract_pka_from_network",
    "extract_all_pka_from_map",
    # Builder
    "build_pka_for_ligand",
    "build_pka_for_all_ligands",
    "PKaStep",
    "PKaChain",
]
