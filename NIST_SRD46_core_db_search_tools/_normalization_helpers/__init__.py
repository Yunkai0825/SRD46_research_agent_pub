"""
Chemical name resolution helpers for SRD-46.

Re-exports the key public functions from the metal and ligand sub-modules
and the ID-prefix utilities.
"""

from .metal_resolution import (
    _expand_metal_name,
    _normalize_metal_query,
    _extract_symbol_charge_query,
    _ELEMENT_SYMBOLS,
)

from .ligand_resolution import (
    _resolve_ligand_identifiers,
)

from .id_prefixer import (
    prefix_id_value,
    prefix_ids_in_row,
    prefix_ids_in_rows,
    parse_prefixed_id,
    unprefix_id,
    normalize_id_input,
)
