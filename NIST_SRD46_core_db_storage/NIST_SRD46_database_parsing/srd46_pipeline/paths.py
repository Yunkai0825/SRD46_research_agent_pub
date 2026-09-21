"""Central path registry for the end-to-end SRD46 pipeline (no I/O at import)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# abspath (not resolve) so a mapped network drive keeps its drive letter instead of the UNC form
PROJECT_ROOT = Path(os.path.abspath(__file__)).parents[1]

# ---------------------------------------------------------------------------
# Raw NIST SRD 46 export (input, read-only)
# ---------------------------------------------------------------------------
RAW_DUMP_DIR = PROJECT_ROOT / "_input" / "SRD46_SQL"
# mysqldump --tab stores each schema in .sql and its rows in a matching .txt file.
RAW_TABLE_FILES = {name: name for name in (
    "author", "beta_definition", "beta_definition_sic", "comments", "constanttyp",
    "footnote", "ligand_class", "liganden", "literature", "literature_alt", "metal",
    "mol_data", "paper", "solvent", "verk_literature_author", "verkn_ligand_metal",
    "verkn_ligand_metal_literature", "verkn_ligand_metal_literature_sic", "verkn_ligand_metal_sic",
)}

# ---------------------------------------------------------------------------
# Locations of the original stage modules wrapped by the pipeline
# ---------------------------------------------------------------------------
PIP1_DIR = PROJECT_ROOT / "pip1_individual_parsers"
PIP1A_DIR = PIP1_DIR / "pip1a_parse_beta_definition_SRD46"
PIP1B_DIR = PIP1_DIR / "pip1b_parse_metal_SRD46"
PIP1C_DIR = PIP1_DIR / "pip1c_parse_liganden_moldata_pKa_SRD46"
PIP1C_1_DIR = PIP1C_DIR / "pip1c_1_molfile_decoding"
PIP1C_2_DIR = PIP1C_DIR / "pip1c_2_SMILS_InChi"
PIP1C_3_DIR = PIP1C_DIR / "pip1c_3_molfile_liganden_HxL_fix"
PIP1C_4_DIR = PIP1C_DIR / "pip1c_4_chemical_names"
PIP1C_5_DIR = PIP1C_DIR / "pip1c_5_Qupkake_pKa_sim"
PIP1C_6_DIR = PIP1C_DIR / "pip1c_6_pKa_molfile_MLenrichment"

PIP2_DIR = PROJECT_ROOT / "pip2_SQL_assembler_SRD46"
PIP2A_HELPERS_DIR = PIP2_DIR / "pip2a_equilibrium_map" / "pip2a_2_ligandmetal_entry_collection_helpers"
PIP2B_HELPERS_DIR = PIP2_DIR / "pip2b_ligand_protonation_vlm" / "ligand_pKa_chain_helpers"
PIP2C_DIR = PIP2_DIR / "pip2c_entry_builder_SQL_assembler"

LEGACY_SCRIPTS = {
    "pip1a": PIP1A_DIR / "SRD46_beta_definition_unified.py",
    "pip1b": PIP1B_DIR / "SRD46_metal_unified_pipeline.py",
    "pip1c_1": PIP1C_1_DIR / "SRD46_pd_molfile_decoding-pip-1.py",
    "pip1c_2": PIP1C_2_DIR / "SRD46_pd_liganden_SMILES_InChi-pip-2.py",
    # pip1c_3 is the `pip3_hxl` package inside PIP1C_3_DIR (imported, not loaded as a script)
    "pip1c_4": PIP1C_4_DIR / "SRD46_pd_chemical_names-pip-4.py",
    "pip1c_5b": PIP1C_5_DIR / "SRD46_pd_qupkake_SDFparsing-pip-5b.py",
    "pip1c_6": PIP1C_6_DIR / "SRD46_pd_liganden_w_moldata_HxLfromQupkake-pip-7.py",
    "literature": PIP2_DIR / "generate_literature_db.py",
}

# ---------------------------------------------------------------------------
# Qupkake (ML pKa) results, pre-computed in a directly queried SQLite bundle.
# Original SDFs/CSV remain supported as explicit legacy inputs. The archived CSV
# rows fill only ligands without an SDF filename (QUP-01), or are the sole source
# when no SDFs exist. New inference is an out-of-band job.
# ---------------------------------------------------------------------------
QUPKAKE_INPUT_DIR = PROJECT_ROOT / "_input" / "Qupkake_ligand_pKa_ML"
QUPKAKE_INPUT_DB_DEFAULT = QUPKAKE_INPUT_DIR / "qupkake_results.db"
QUPKAKE_SDF_DIR_DEFAULT = QUPKAKE_INPUT_DIR / "pip1c_Qupkake_SDF"
QUPKAKE_PARSED_CSV_CANDIDATES = [
    QUPKAKE_INPUT_DIR / "qupkake_pka_liganden.csv",
]

# ---------------------------------------------------------------------------
# Offline PubChem cache seeds: name/SMILES/InChI look-ups collected by the original
# network runs, so that `--pubchem cache-only` reproduces the published enrichment.
# ---------------------------------------------------------------------------
PUBCHEM_SEEDS_DIR = PROJECT_ROOT / "_input" / "PubChem_cache_seeds"
PUBCHEM_SEEDS = {
    "fixed_by_name": PUBCHEM_SEEDS_DIR / "FIXED_by_name.csv",
    "mol_data_enriched": PUBCHEM_SEEDS_DIR / "mol_data_enriched.csv",
    "mol_data_with_names": PUBCHEM_SEEDS_DIR / "mol_data_with_names.csv",
    "failed_names": PUBCHEM_SEEDS_DIR / "FAILED_NAMES.csv",
}

# Reference row counts of the published end products (checked by the verify stage)
REFERENCE_COUNTS = {
    # Expected row counts of a complete run (full pipeline, qupkake=existing).
    #   metal_card / ligand_card      = rows of the metal / liganden dump tables
    #   ligandmetal_card              = rows of verkn_ligand_metal (every VLM row becomes one complex card,
    #                                   including the 10,761 rows with '*' placeholder temperatures)
    #   ligand_pka_measured           = pKa steps from the H+ equilibrium maps (pip2b); includes the HL -> H2L
    #                                   step of ligand 10172 (VLM 178613, log K 1.54) enabled by rule BETA-02
    #                                   (beta definition 101: [I]/[HL][H] -> [H2L]/[HL][H])
    #   ligand_pka_bracket            = 12858 measured HxL windows + 17863 Qupkake states/Q0 fallbacks
    #                                   (17861 from the SDF archive + 2 windows for ligand 10175 from QUP-01)
    #   eq_map_collection / eq_node   = metal-ligand pairs / K-type VLM entries assigned to networks
    #   literature tables             = original dump record counts
    "cards": {"metal_card": 230, "ligand_card": 5750, "ligandmetal_card": 89824,
              "ligand_pka_measured": 8801, "ligand_pka_bracket": 30721},
    "eq": {"eq_map_collection": 21348, "eq_node": 60540},
    "lit": {"literature_alt": 18297, "vlm_literature_sic": 721906},
}
# Accepted-data (non-placeholder) reference counts of the cards DB, derived by manual_rules
# PLACEHOLDER_SPLIT_QUERIES (LIG-04 for ligands, NOTE-01 'parser:placeholder=1' notes for rows/cards):
#   ligand_card                    5750 - 1342 whole-record placeholder ligands ('***' / '********')
#   ligandmetal_stability_measured 89824 - 10758 '*' rows
#   ligandmetal_card               cards with at least one accepted row (one measured row per card)
ACCEPTED_REFERENCE_COUNTS = {"ligand_card": 4408, "ligandmetal_stability_measured": 79066, "ligandmetal_card": 79066}

# Column contract of the card tables read by the downstream consumers (SRD46_research_agent search
# tools / MCP server / database browser, pip3): names AND order as in the pinned srd46_cards.db.
# The pipeline adds no columns (parser provenance travels in ligandmetal_stability_measured.notes,
# manual rule NOTE-01); verify fails when the published schema drifts from this list.
CARDS_SCHEMA_CONTRACT = {
    "ligand_card": ["ligand_id", "ligand_name_SRD", "ligand_class_id", "ligand_class_name", "ligand_SMILES",
                    "ligand_InChi", "formula", "composition", "figure_definition", "definition_HxL",
                    "synonym_iupac_name", "synonym_common_name", "created_at"],
    "ligandmetal_card": ["card_id", "complex_system_id", "metal_id", "ligand_id", "beta_definition_id", "complex_id",
                         "ligand_class_id", "ligand_class_name", "metal_name_SRD", "metal_SMILES", "metal_InChi",
                         "ligand_name_SRD", "ligand_SMILES", "ligand_InChi", "ligand_HxL_definition_SRD",
                         "beta_definition_name", "created_at"],
    "ligandmetal_stability_measured": ["stability_id", "card_id", "constant_type", "constant_value", "temperature_c",
                                       "ionic_strength_mol_l", "solvent_id", "solvent_name", "electrolyte_composition",
                                       "equation_python", "raw_definition", "normalized_definition", "equation_str",
                                       "equation_tree_json", "equation_sides_json", "LHS_species_json",
                                       "RHS_species_json", "HxL_involved_json", "presence_flags_json", "reaction_type",
                                       "element_conserved", "citations_json", "audit_timestamp", "error", "notes"],
}


@dataclass(frozen=True)
class OutputPaths:
    """Files the pipeline writes, derived from one output root.

    Default mode: the four downstream databases in ``cards_dir`` plus the staging work store.
    ``--debug`` additionally exports every intermediate of every stage under ``debug_dir``.
    """

    output_dir: Path = PROJECT_ROOT / "_output"

    @property
    def cards_dir(self) -> Path:
        return self.output_dir / "pip2c_cards_sql"

    @property
    def cards_db(self) -> Path:
        return self.cards_dir / "srd46_cards.db"

    @property
    def eq_db(self) -> Path:
        return self.cards_dir / "srd46_equilibrium_maps.db"

    @property
    def lit_db(self) -> Path:
        return self.cards_dir / "srd46_literature.db"

    @property
    def fingerprints_db(self) -> Path:
        return self.cards_dir / "srd46_ligand_fingerprints.db"

    @property
    def staging_db(self) -> Path:
        return self.output_dir / "srd46_pipeline_staging.db"

    @property
    def debug_dir(self) -> Path:
        return self.output_dir / "debug"

    def all_final(self) -> list[Path]:
        return [self.cards_db, self.eq_db, self.lit_db, self.fingerprints_db]
