"""
pip3_hxl - Liganden + Molfile HxL Parse Pipeline (pip1c-3)

This package provides modular components for:
1. Merging liganden table with enriched mol_data
2. Parsing figure_definition (HxL notation)
3. Reconciling charges via rule-based corrections
4. Rule-specific diagnostic output generation
"""

from .config import (
    TIMESTAMP, CODE_ROOT, PIPELINE_ROOT, PROJECT_ROOT,
    MOL_DATA_CSV, LIGANDEN_CSV, BUILD_DIR,
    OUTPUT_CSV, DEBUG_CSV, FAILED_CSV, STATS_CSV, STATS_JSON, SUMMARY_MD, LOG_FILE,
    FAILED_MOLDATA_CSV, FAILED_LIGANDEN_CSV,
    VERBOSE, CONSIDER_FORMULA_MISMATCH, AUDIT_SMILES_POLY, EXPORT_COLS,
)
from .logging_utils import log, write_log_file
from .rdkit_setup import RDKit_OK, COUNTERION_MOLS, PARTIAL_SAN
from .parsing import parse_figure_definition, parse_formula_to_dict, canonical_formula, compare_formulas
from .charge_utils import sum_formal_charge, charge_from_molblock_text, charge_from_inchi, has_cyanide_hint
from .rdkit_utils import build_mol, recompute_strings
from .rules import (
    rule1_remove_counterions, rule2_fix_cyanide, rule2b_fix_cyanometalate,
    rule3_fix_polyanions, rule4_looks_desalted_cation, rule4b_harmonize_post_desalting,
    rule5_set_figure_from_molblock_superatom, rule6_fix_figure_for_two_entries,
)
from .processing import process_row
from .diagnostics import manual_review_reason, compute_debug_stats, generate_summary_markdown, validate_exported_csv
from .rule_diagnostics import (
    write_all_diagnostics, generate_diagnostic_stats,
    is_multi_component_inchi, has_formula_mismatch,
)

__all__ = [
    # Config
    "TIMESTAMP", "CODE_ROOT", "PIPELINE_ROOT", "PROJECT_ROOT",
    "MOL_DATA_CSV", "LIGANDEN_CSV", "BUILD_DIR",
    "OUTPUT_CSV", "DEBUG_CSV", "FAILED_CSV", "STATS_CSV", "STATS_JSON", "SUMMARY_MD", "LOG_FILE",
    "FAILED_MOLDATA_CSV", "FAILED_LIGANDEN_CSV",
    "VERBOSE", "CONSIDER_FORMULA_MISMATCH", "AUDIT_SMILES_POLY", "EXPORT_COLS",
    # Logging
    "log", "write_log_file",
    # RDKit
    "RDKit_OK", "COUNTERION_MOLS", "PARTIAL_SAN",
    # Parsing
    "parse_figure_definition", "parse_formula_to_dict", "canonical_formula", "compare_formulas",
    # Charge
    "sum_formal_charge", "charge_from_molblock_text", "charge_from_inchi", "has_cyanide_hint",
    # RDKit utils
    "build_mol", "recompute_strings",
    # Rules
    "rule1_remove_counterions", "rule2_fix_cyanide", "rule2b_fix_cyanometalate",
    "rule3_fix_polyanions", "rule4_looks_desalted_cation", "rule4b_harmonize_post_desalting",
    "rule5_set_figure_from_molblock_superatom", "rule6_fix_figure_for_two_entries",
    # Processing
    "process_row",
    # Diagnostics
    "manual_review_reason", "compute_debug_stats", "generate_summary_markdown", "validate_exported_csv",
    # Rule Diagnostics
    "write_all_diagnostics", "generate_diagnostic_stats",
    "is_multi_component_inchi", "has_formula_mismatch",
]
