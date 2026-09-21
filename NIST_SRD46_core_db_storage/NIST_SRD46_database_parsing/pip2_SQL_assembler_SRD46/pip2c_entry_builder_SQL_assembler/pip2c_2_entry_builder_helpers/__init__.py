"""
pip2c Entry Builder Helpers.

This package contains utility modules for CSV I/O and configuration.
"""
from __future__ import annotations

from .config import (
    BASE_DIR,
    PROJECT_ROOT,
    INPUT_DIR,
    PIP1_PARSED_DIR,
    SRD46_SQL_CSV_DIR,
    FILENAMES,
    COLUMN_ALIASES,
    DEBUG_FLAG,
    setup_logging,
)

from .csv_io_helpers import (
    # Column access helpers
    get_col,
    col_exists,
    pick,
    pick_any,
    # CSV reading functions
    detect_csv_format,
    read_csv_dicts,
    find_first_row,
    stream_find_row,
    first_row_by_id,
    lookup_row,
    map_by_key,
    register_table,
    clear_registered_tables,
    # Utility functions  
    normalize_id,
    collect_comment_like_fields_from_row,
)

from .pka_builder import (
    build_pka_block,
    extract_measured_pka,
    extract_estimated_pka,
)

from .equation_parser import (
    maybe_json,
    parse_equation_tree,
    extract_species_from_tree,
    presence_from_labels,
    extract_hxl_involved,
)

__all__ = [
    # Config
    "BASE_DIR",
    "PROJECT_ROOT", 
    "INPUT_DIR",
    "PIP1_PARSED_DIR",
    "SRD46_SQL_CSV_DIR",
    "FILENAMES",
    "COLUMN_ALIASES",
    "DEBUG_FLAG",
    "setup_logging",
    # CSV I/O
    "get_col",
    "col_exists",
    "pick",
    "pick_any",
    "detect_csv_format",
    "read_csv_dicts",
    "find_first_row",
    "stream_find_row",
    "first_row_by_id",
    "lookup_row",
    "map_by_key",
    "register_table",
    "clear_registered_tables",
    "normalize_id",
    "collect_comment_like_fields_from_row",
    # pKa builder
    "build_pka_block",
    "extract_measured_pka",
    "extract_estimated_pka",
    # Equation parser
    "maybe_json",
    "parse_equation_tree",
    "extract_species_from_tree",
    "presence_from_labels",
    "extract_hxl_involved",
]
