from .inspect_card_compactor import compact_inspect_card
from .inspect_literature_compactor import compact_inspect_literature
from .entity_search_compactors import compact_search_metals, compact_search_ligands
from .stability_compactor import compact_search_stability
from .network_compactor import compact_search_networks
from .citation_compactor import compact_search_citations
from .similar_ligand_compactor import compact_search_similar_ligands
from .pka_values_compactor import compact_search_pka_values
from .pka_ligands_compactor import compact_search_pka_ligands
from .system_catalog_compactor import compact_system_catalog
from .preplan_compactor import compact_preplan_decision
from .aggregate_compactor import (
    compact_db_count_records,
    compact_db_distribution,
    compact_db_ranked_pairs,
    compact_get_table_schema,
)
from .sql_query_compactor import compact_execute_srd46_sql


# ── _compacts_tools tags for CompactorCatalog auto-wiring ──────
compact_inspect_card._compacts_tools = ("inspect_card",)
compact_inspect_literature._compacts_tools = ("inspect_literature",)
compact_search_metals._compacts_tools = ("search_metals",)
compact_search_ligands._compacts_tools = ("search_ligands",)
compact_search_stability._compacts_tools = ("search_stability",)
compact_search_networks._compacts_tools = ("search_networks",)
compact_search_citations._compacts_tools = ("search_citations",)
compact_search_similar_ligands._compacts_tools = ("search_similar_ligands",)
compact_search_pka_values._compacts_tools = ("search_pka_values",)
compact_search_pka_ligands._compacts_tools = ("search_pka_ligands",)
compact_system_catalog._compacts_tools = ("build_system_catalog", "system_catalog")
compact_preplan_decision._compacts_tools = ("0_preplan_decision",)

COMPACTOR_FUNCTIONS = [
    compact_inspect_card,
    compact_inspect_literature,
    compact_search_metals,
    compact_search_ligands,
    compact_search_stability,
    compact_search_networks,
    compact_search_citations,
    compact_search_similar_ligands,
    compact_search_pka_values,
    compact_search_pka_ligands,
    compact_system_catalog,
    compact_preplan_decision,
    compact_db_count_records,
    compact_db_distribution,
    compact_db_ranked_pairs,
    compact_get_table_schema,
    compact_execute_srd46_sql,
]

__all__ = [
    "compact_inspect_card",
    "compact_inspect_literature",
    "compact_search_metals",
    "compact_search_ligands",
    "compact_search_stability",
    "compact_search_networks",
    "compact_search_citations",
    "compact_search_similar_ligands",
    "compact_search_pka_values",
    "compact_search_pka_ligands",
    "compact_system_catalog",
    "compact_preplan_decision",
    "compact_db_count_records",
    "compact_db_distribution",
    "compact_db_ranked_pairs",
    "compact_get_table_schema",
    "compact_execute_srd46_sql",
    "COMPACTOR_FUNCTIONS",
]
