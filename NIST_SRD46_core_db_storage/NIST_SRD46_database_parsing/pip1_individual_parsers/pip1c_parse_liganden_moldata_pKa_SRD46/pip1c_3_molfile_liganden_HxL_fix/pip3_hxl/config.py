"""
config.py - Path configuration and constants for pip1c-3 HxL pipeline.
"""

from pathlib import Path
from datetime import datetime

# =====================================================================
# TIMESTAMP
# =====================================================================
now = datetime.now()
TIMESTAMP = now.strftime("%Y-%m-%d-%H-%M-%S")

# =====================================================================
# PATH CONFIGURATION
# =====================================================================
CODE_ROOT = Path(__file__).resolve().parent.parent  # pip1c_3_molfile_liganden_HxL_fix
PIPELINE_ROOT = CODE_ROOT.parent  # pip1c_parse_liganden_moldata_pKa_SRD46
PROJECT_ROOT = PIPELINE_ROOT.parent.parent  # NIST_SRD46_Correction_and_Parser

# Input 1: Enriched mol_data from pip1c-2
MOL_DATA_CSV = PIPELINE_ROOT / "_build" / "pip1c_2_SMILS_InChi_output" / "mol_data_enriched.csv"

# Input 2: Liganden table from SRD46 database
LIGANDEN_CSV = PROJECT_ROOT / "_input" / "SRD46_SQL_and_CSV" / "Export" / "CSV files" / "liganden__8__7.csv"

# Build: all outputs go to _build/pip1c_3_HxL_output/
BUILD_DIR = PIPELINE_ROOT / "_build" / "pip1c_3_HxL_output"

# Output files
OUTPUT_CSV = BUILD_DIR / "liganden_moldata_HxL_parsed.csv"
DEBUG_CSV = BUILD_DIR / "debug.csv"
FAILED_CSV = BUILD_DIR / "FAILED_HxL.csv"
STATS_CSV = BUILD_DIR / "debug_stats.csv"
STATS_JSON = BUILD_DIR / "debug_stats.json"
SUMMARY_MD = BUILD_DIR / f"HxL_parse_summary_{TIMESTAMP}.md"
LOG_FILE = BUILD_DIR / f"HxL_parse_log_{TIMESTAMP}.txt"

# Orphan entry output files (data integrity failures)
FAILED_MOLDATA_CSV = BUILD_DIR / "FAILED_moldata_no_liganden.csv"  # mol_data entries with no matching liganden
FAILED_LIGANDEN_CSV = BUILD_DIR / "FAILED_liganden_no_molfile.csv"  # liganden entries with no matching molfile

# =====================================================================
# RUNTIME OPTIONS
# =====================================================================
VERBOSE = True
CONSIDER_FORMULA_MISMATCH = False  # If consider formula match in debug
AUDIT_SMILES_POLY = False

# =====================================================================
# EXPORT COLUMNS
# =====================================================================
# Original liganden columns + after-fix columns only
EXPORT_COLS = [
    # Original liganden columns
    "ligandenID", "name_ligand", "ligand_classNr", "figure_definition",
    "link_pictures", "pictures_description", "comment",
    # After-fix columns
    "molblock", "InChI", "SMILES", "COMPOSITION",
    "figure_definition_parsed", "figure_definition_charge", "h_count", "l_count",
    "rules_applied", "mol_string_encoded",
]
