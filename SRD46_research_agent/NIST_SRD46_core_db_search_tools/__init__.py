"""
NIST SRD-46 core database search tools.

Public API
----------
Entity resolution:
    search_metals, search_ligands

Stability:
    search_stability

Networks:
    search_networks

Citations:
    search_citations

pKa:
    search_pka_values, search_pka_ligands

Card inspection:
    inspect_card, inspect_literature

System overview:
    build_system_catalog

Similarity:
    search_similar_ligands

Aggregates:
    db_count_records, db_distribution, db_ranked_pairs,
    get_table_schema

ID helpers:
    parse_prefixed_id, unprefix_id
"""

from .entity_search import search_metals, search_ligands
from .card_inspect import inspect_card, inspect_literature
from .stability_search import search_stability
from .network_search import search_networks
from .citation_search import search_citations
from .pka_search import search_pka_values, search_pka_ligands
from .system_catalog import build_system_catalog
from .similarity_search import search_similar_ligands
from .aggregate_and_sql import (
    db_count_records,
    db_distribution,
    db_ranked_pairs,
    get_table_schema,
    execute_srd46_sql,
)
from ._normalization_helpers.id_prefixer import parse_prefixed_id, unprefix_id, normalize_id_input
from ._normalization_helpers.functional_group_catalog import list_functional_groups

# Append the WHERE-clause normalization "manual" to every public tool that
# accepts a free-form WHERE / SQL string. Single source of truth lives in
# ``_search_helpers.WHERE_NORMALIZATION_NOTES`` so the agent sees the same
# warning everywhere, and we never have to keep N docstrings in sync.
from ._search_helpers import WHERE_NORMALIZATION_NOTES as _WN

for _fn in (
    search_stability,
    search_networks,
    search_pka_values,
    search_pka_ligands,
    db_count_records,
    db_distribution,
    db_ranked_pairs,
    execute_srd46_sql,
):
    _fn.__doc__ = (_fn.__doc__ or "").rstrip() + "\n\n" + _WN

del _fn, _WN

__all__ = [
    "search_metals",
    "search_ligands",
    "inspect_card",
    "inspect_literature",
    "search_stability",
    "search_networks",
    "search_citations",
    "search_pka_values",
    "search_pka_ligands",
    "build_system_catalog",
    "search_similar_ligands",
    "list_functional_groups",
    "db_count_records",
    "db_distribution",
    "db_ranked_pairs",
    "get_table_schema",
    "execute_srd46_sql",
    "parse_prefixed_id",
    "unprefix_id",
    "normalize_id_input",
]
