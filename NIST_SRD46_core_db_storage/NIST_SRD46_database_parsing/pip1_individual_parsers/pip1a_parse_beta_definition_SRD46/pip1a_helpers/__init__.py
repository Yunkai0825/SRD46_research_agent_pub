"""
pip1a_helpers - Modular components for beta_definition parsing.
Hybrid approach: token-based counting + component expansion for JSON tree.
"""
from .constants import (
    ParsedConst,
    VALID_ELEMENTS,
    POLYMETAL_HOL_TOKENS,
    POLYMETAL_TOKEN_PATTERN,
    POLYMETAL_HOL_RULES,  # legacy alias
    _SPECIAL_HOL_GROUP_RE,
    _ELEMENT_KEY_RE,
    # Regex patterns
    RE_HTML_SUB_TAGS,
    RE_MLH_SEQ_FULL,
    RE_MLH_TOKEN,
    RE_TRAILING_CHARGE,
    RE_IONIC_CHARGE,
    RE_STRAY_WORDS,
    RE_SIMPLE_TAG_PARENS,
)
from .io_utils import (
    load_beta_definition,
    load_csv_safe,
    print_debug,
    normalize_id,
    augment_with_original_rows,
    maybe_parse_json_columns,
    BD_PK,
)
from .species_parser import (
    parse_species_label_to_basis,
    parse_tokens_to_basis,
    collect_basis_counts,
    species_to_components,
    species_to_components_with_specials,
    strip_brackets,
    strip_nonchemical_annotations,
    clean_formula_artifacts,
    extract_float_groups,
    has_dup_L,
)
from .equation_builder import (
    beta_to_pairs,
    eq_to_sides,
    render_beta_tokens,
    compute_balance_vector,
    balance_from_sides,
    process_equation,
    add_equation_readability_and_balance,
    add_final_equation_columns,
    add_equation_tree,
    add_tree_elemental_diagnostics,
    flag_suspect_L_duplication,
    sides_to_nested_tree,
    element_net_from_tree,
    strings_from_sides,
)
from .hol_autocorrect import (
    apply_polymetal_hol_rule,
    get_polymetal_hol_counts,
    detect_polymetal_cluster,
    species_needs_hol_correction,
    preprocess_beta_definition,
    correct_hol_in_equation,
)
from .diagnostics import (
    # Failure masks and classification
    build_failure_masks,
    select_balance_for_classification,
    classify_unbalanced_row,
    classify_unbalanced_simple,
    # Token counting
    count_extra_tokens,
    # Summary statistics
    compute_summary_stats,
    summarize_unbalanced_causes,
    # Tree-based conservation
    element_mass_conserved_from_tree,
    check_tree_conservation,
    # Breakdown and reporting
    print_unbalanced_breakdown,
    show_examples,
    analyze_preparse_residuals,
    print_run_summary,
    # Log and validation output
    write_summary_log,
    generate_validation_report,
    set_verbose,
)
from .export_utils import (
    # Column definitions
    COLUMN_METADATA,
    CORE_ID_COLS,
    ORIGINAL_DATA_COLS,
    EQUATION_READABLE_COLS,
    EQUATION_STRUCTURE_COLS,
    BALANCE_STATUS_COLS,
    BALANCE_DETAIL_COLS,
    FAILURE_ANALYSIS_COLS,
    VLM_REFERENCE_COLS,
    # VLM lookup functions
    load_vlm_lookup,
    aggregate_vlm_by_beta_definition,
    add_vlm_references,
    # Export functions
    prepare_export_dataframe,
    get_ordered_columns,
    export_success_dataframe,
    export_unsuccessful_dataframe,
    build_augmented_dataframe,
    export_augmented_dataframe,
    export_all,
    write_column_metadata,
)
from .species_library import (
    # Phase classification
    PhaseType,
    SpeciesEntry,
    SpeciesLibrary,
    # Builder functions
    build_species_library_from_df,
    add_species_phase_columns,
    enrich_equation_tree_with_phase,
    classify_reaction_type,
    # Export
    export_species_library,
)

__all__ = [
    # Named tuples
    "ParsedConst",
    # Constants
    "VALID_ELEMENTS",
    "POLYMETAL_HOL_RULES", 
    "BD_PK",
    # Regex
    "_SPECIAL_HOL_GROUP_RE",
    "_ELEMENT_KEY_RE",
    "RE_HTML_SUB_TAGS",
    "RE_MLH_SEQ_FULL",
    "RE_MLH_TOKEN",
    "RE_TRAILING_CHARGE",
    "RE_IONIC_CHARGE",
    "RE_STRAY_WORDS",
    "RE_SIMPLE_TAG_PARENS",
    # I/O
    "load_beta_definition",
    "load_csv_safe",
    "print_debug",
    "normalize_id",
    "augment_with_original_rows",
    "maybe_parse_json_columns",
    # Species parsing (token-based)
    "parse_species_label_to_basis",
    "parse_tokens_to_basis",
    "collect_basis_counts",
    "species_to_components",
    "species_to_components_with_specials",
    "strip_brackets",
    "strip_nonchemical_annotations",
    "clean_formula_artifacts",
    "extract_float_groups",
    "has_dup_L",
    # Equation building
    "beta_to_pairs",
    "eq_to_sides",
    "render_beta_tokens",
    "compute_balance_vector",
    "balance_from_sides",
    "process_equation",
    "add_equation_readability_and_balance",
    "add_final_equation_columns",
    "add_equation_tree",
    "add_tree_elemental_diagnostics",
    "flag_suspect_L_duplication",
    "sides_to_nested_tree",
    "element_net_from_tree",
    "strings_from_sides",
    # HOL autocorrect
    "apply_polymetal_hol_rule",
    "detect_polymetal_cluster",
    "species_needs_hol_correction",
    "preprocess_beta_definition",
    "correct_hol_in_equation",
    # Diagnostics and reporting
    "build_failure_masks",
    "select_balance_for_classification",
    "classify_unbalanced_row",
    "classify_unbalanced_simple",
    "count_extra_tokens",
    "compute_summary_stats",
    "summarize_unbalanced_causes",
    "element_mass_conserved_from_tree",
    "check_tree_conservation",
    "print_unbalanced_breakdown",
    "show_examples",
    "analyze_preparse_residuals",
    "print_run_summary",
    "write_summary_log",
    "generate_validation_report",
    "set_verbose",
    # Export utilities
    "COLUMN_METADATA",
    "CORE_ID_COLS",
    "ORIGINAL_DATA_COLS",
    "EQUATION_READABLE_COLS",
    "EQUATION_STRUCTURE_COLS",
    "BALANCE_STATUS_COLS",
    "BALANCE_DETAIL_COLS",
    "FAILURE_ANALYSIS_COLS",
    "prepare_export_dataframe",
    "get_ordered_columns",
    "export_success_dataframe",
    "export_unsuccessful_dataframe",
    "build_augmented_dataframe",
    "export_augmented_dataframe",
    "export_all",
    "write_column_metadata",
    # Species library and phase classification
    "PhaseType",
    "SpeciesEntry",
    "SpeciesLibrary",
    "build_species_library_from_df",
    "add_species_phase_columns",
    "enrich_equation_tree_with_phase",
    "classify_reaction_type",
    "export_species_library",
]
