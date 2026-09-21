"""
Configuration for pip2c entry builder.

Contains paths, filenames, and column alias mappings.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

# =============================================================================
# Logging configuration
# =============================================================================

logger = logging.getLogger(__name__)

def setup_logging(level: int = logging.INFO, log_file: Optional[Path] = None) -> None:
    """Configure logging for pip2c entry builder.
    
    Args:
        level: Logging level (default: INFO)
        log_file: Optional path to log file
    """
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Get the pip2c root logger
    pip2c_logger = logging.getLogger('pip2c_2_entry_builder_helpers')
    pip2c_logger.setLevel(level)
    pip2c_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    pip2c_logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        pip2c_logger.addHandler(file_handler)
        
    # Also configure the main module logger
    logger.setLevel(level)
    logger.handlers.clear()
    logger.addHandler(console_handler)
    if log_file:
        logger.addHandler(file_handler)

# Base directory (pip2c_entry_builder_SQL_assembler)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEBUG_FLAG = False  # Legacy flag - use logging instead

# Root of the project (NIST_SRD46_Correction_and_Parser) - go up 2 more levels
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))

# Input directories (parsed data from pip1)
INPUT_DIR = os.path.join(PROJECT_ROOT, "_input")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "_output")
PIP1_PARSED_DIR = os.path.join(INPUT_DIR, "pip1_parsed_individual_SRD46")
SRD46_SQL_CSV_DIR = os.path.join(INPUT_DIR, "SRD46_SQL_and_CSV", "Export", "CSV files")

# CSV files expected with full paths (tolerant: missing files will be skipped)
FILENAMES: dict[str, str] = {
    # Parsed data from pip1 (augmented/enriched).
    # NOTE: the end-to-end pipeline (srd46_pipeline/) registers these three tables
    # in memory via csv_io_helpers.register_table(); the paths are the standalone fallback.
    "liganden_moldata": os.path.join(PIP1_PARSED_DIR, "pip1c_liganden_parsed", "liganden_w_moldata_qupkake_parsed.csv"),
    "beta_definition_fixed": os.path.join(PIP1_PARSED_DIR, "pip1a_beta_definition_parsed", "beta_definition_augmented.csv"),
    "metal_parsed": os.path.join(PIP1_PARSED_DIR, "pip1b_metal_parsed", "metal_augmented.csv"),
    
    # pKa chain data from equilibrium tree (preferred T/I filtered)
    "preferred_ligand_pka_chains": os.path.join(PIP1_PARSED_DIR, "pip2b_liganden_pKa_map_output", "preferred_ligand_pka_chains.csv"),
    
    # Original SRD46 SQL export CSV files
    "liganden": os.path.join(SRD46_SQL_CSV_DIR, "liganden__8__7.csv"),
    "ligand_class": os.path.join(SRD46_SQL_CSV_DIR, "ligand_class__7.csv"),
    "metal": os.path.join(SRD46_SQL_CSV_DIR, "metal__11.csv"),
    "verkn_ligand_metal": os.path.join(SRD46_SQL_CSV_DIR, "verkn_ligand_metal__16__8-11-2-5-6-14.csv"),
    "constanttyp": os.path.join(SRD46_SQL_CSV_DIR, "constanttyp__5.csv"),
    "solvent": os.path.join(SRD46_SQL_CSV_DIR, "solvent__14.csv"),
    "beta_definition": os.path.join(SRD46_SQL_CSV_DIR, "beta_definition__2.csv"),
    
    # Citation tables
    "verkn_ligand_metal_literature": os.path.join(SRD46_SQL_CSV_DIR, "verkn_ligand_metal_literature__17__8-11-9-10.csv"),
    "verkn_ligand_metal_literature_sic": os.path.join(SRD46_SQL_CSV_DIR, "verkn_ligand_metal_literature_sic__18__16-9-10.csv"),
    "literature": os.path.join(SRD46_SQL_CSV_DIR, "literature__9__13.csv"),
    "literature_alt": os.path.join(SRD46_SQL_CSV_DIR, "literature_alt__10.csv"),
    "paper": os.path.join(SRD46_SQL_CSV_DIR, "paper__13.csv"),
    "author": os.path.join(SRD46_SQL_CSV_DIR, "author__1.csv"),
    "footnote": os.path.join(SRD46_SQL_CSV_DIR, "footnote__6.csv"),
    "verk_literature_author": os.path.join(SRD46_SQL_CSV_DIR, "verk_literature_author__15__9-1.csv"),
}

# Central column alias dictionary to normalize common column names used across CSVs.
# Keys are canonical names used in code; values are lists of synonyms appearing in CSVs.
COLUMN_ALIASES: dict[str, list[str]] = {
    # ligand moldata
    "ligand_id": ["ligandenID", "ligandenNr", "ligand_id", "ligandNr"],
    "name_ligand": ["name_ligand", "ligand_name_SRD", "name"],
    "SMILES": ["SMILES", "smiles", "smiles_main", "smiles_canonical"],
    "InChi": ["InChi", "inchi", "inchi_main", "inchi_canonical", "InChI"],
    "IUPAC_NAME": ["IUPAC_NAME", "iupac_name"],
    "COMMON_NAME": ["COMMON_NAME", "common_name"],
    "COMPOSITION": ["COMPOSITION", "composition"],
    "figure_definition_parsed": ["figure_definition_parsed", "definition_HxL"],
    # generic keys used elsewhere
    "constanttypID": ["constanttypID", "constanttypNr"],
    "beta_definitionID": ["beta_definitionID", "beta_definitionNr"],
    # beta_definition augmented columns
    "equation_tree_json": ["equation_tree_json", "beta_eq_tree_json"],
    "equation_python": ["equation_python", "beta_eq_str_python_final", "equation_str"],
    "species_list_aqueous": ["species_list_aqueous", "species_list_all"],
}
