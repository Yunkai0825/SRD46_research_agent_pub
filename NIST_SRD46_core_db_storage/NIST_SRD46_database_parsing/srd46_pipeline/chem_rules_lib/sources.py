"""Authoritative MySQL source selection and guarded curation policy (SRC)."""
from __future__ import annotations

from typing import Dict
from ..paths import RAW_DUMP_DIR, RAW_TABLE_FILES
from typing import Tuple
from .registry import Rule, _declare


# =============================================================================
# SRC  raw source policy
# =============================================================================
# Every source table is read from its original mysqldump --tab pair: a .sql
# schema and CP1252 .txt data. Spreadsheet exports are optional historical files.
# source_corrections.py retains guarded beta-definition curation and deterministic
# beta/metal/solvent markup conversion; the raw stage records every application as SRC-02.
CANONICAL_DUMP_DIR = RAW_DUMP_DIR
CANONICAL_DUMP_ENCODING = "cp1252"
CANONICAL_NULL_TOKEN = "\\N"              # kept literally, like the CSV, so downstream pick() semantics do not change
CANONICAL_TABLE_FILES: Dict[str, str] = {   # table -> file stem (<stem>.sql / <stem>.txt)
    "verkn_ligand_metal": RAW_TABLE_FILES["verkn_ligand_metal"],
}
CANONICAL_EXPECTED_ROWS: Dict[str, int] = {"verkn_ligand_metal": 89_824}

RAW_SOURCE_POLICY: Dict[str, Tuple[str, str]] = {
    "verkn_ligand_metal": ("mysqldump_txt", "Original CP1252 values preserve signs, precision, and timestamps"),
    "beta_definition": ("mysqldump_txt_with_rules", "Original definitions plus guarded archived source curation and markup normalization"),
    "metal": ("mysqldump_txt_with_rules", "Original metal names with deterministic HTML sub/sup conversion"),
    "solvent": ("mysqldump_txt_with_rules", "Original solvent names with deterministic HTML sub/sup conversion"),
    "liganden": ("mysqldump_txt", "Original ligand rows and timestamps"),
    "mol_data": ("mysqldump_txt", "Original encoded molecular payloads and timestamps"),
    "literature tables": ("mysqldump_txt", "Original bibliography and measurement/reference associations"),
}
_declare(Rule("SRC-01", "raw_canonical", "verkn_ligand_metal_canonical",
              "verkn_ligand_metal is loaded from the mysqldump .txt, not from the Excel-derived CSV",
              RAW_SOURCE_POLICY["verkn_ligand_metal"][1]))

# Historical CSV audit metadata retained for compatibility; not used to load pipeline inputs.
# csv stem -> (key column, consuming stage)
CSV_LINEAGE_TABLES: Dict[str, Tuple[str, str]] = {
    "beta_definition__2": ("beta_definitionID", "pip1a_beta_definition"),
    "metal__11": ("metalID", "pip1b_metal"),
    "liganden__8__7": ("ligandenID", "pip1c_2_smiles_inchi / pip1c_4_chemical_names"),
    "mol_data__12": ("mol_dataID", "pip1c_1_molfile_decode"),
    "literature_alt__10": ("literature_altID", "literature_db"),
    "literature__9__13": ("literatureID", "literature_db"),
    "paper__13": ("paperID", "literature_db"),
    "author__1": ("authorID", "literature_db"),
    "footnote__6": ("footnoteID", "literature_db"),
    "verk_literature_author__15__9-1": ("verkn_literature_authorID", "literature_db"),
    "verkn_ligand_metal_literature__17__8-11-9-10": ("verkn_ligand_metal_literatureID", "literature_db"),
    "verkn_ligand_metal_literature_sic__18__16-9-10": ("verkn_ligand_metal_literatureID", "literature_db"),
}
# difference classes tolerated per column ("<stem>.<column>" or bare column name); anything else aborts
CSV_LINEAGE_ALLOWED: Dict[str, Tuple[str, ...]] = {
    "Acc_feld": ("date_format", "excel_serial"),                                   # curation timestamp, never parsed downstream
    "beta_definition__2.name_beta_definition": ("markup_normalised", "varchar_limit_completed"),
    "metal__11.name_metal": ("html_to_notation",),
}
BETA_DEFINITION_VARCHAR_LIMIT = 110      # `name_beta_definition` varchar(110) in beta_definition.sql
EXCEL_SERIAL_EPOCH = "1899-12-30"        # Excel 1900 date system
_declare(Rule("SRC-02", "raw_canonical", "(kv source_dump_audit)",
              "Validate original dump tables and apply guarded archived source curation and markup rules",
              "Export CSVs are not runtime inputs; pinned source corrections preserve the curated definitions "
              "while original MySQL values and timestamps remain authoritative"))


__all__ = [
    'CANONICAL_DUMP_DIR',
    'CANONICAL_DUMP_ENCODING',
    'CANONICAL_NULL_TOKEN',
    'CANONICAL_TABLE_FILES',
    'CANONICAL_EXPECTED_ROWS',
    'RAW_SOURCE_POLICY',
    'CSV_LINEAGE_TABLES',
    'CSV_LINEAGE_ALLOWED',
    'BETA_DEFINITION_VARCHAR_LIMIT',
    'EXCEL_SERIAL_EPOCH',
]
