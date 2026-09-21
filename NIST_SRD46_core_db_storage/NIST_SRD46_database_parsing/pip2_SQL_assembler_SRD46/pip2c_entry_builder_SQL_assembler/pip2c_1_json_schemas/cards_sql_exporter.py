"""
Cards SQL Exporter

Exports ligand, metal, and ligand-metal cards to a SQLite database.
Stores all nested structures in normalized tables with JSON fallback for complex fields.

Reference data (literature, authors, footnotes) is stored in separate normalized tables
to avoid duplication. References are linked via verkn_ligand_metal_id (vlm_id).

Usage:
    from cards_sql_exporter import CardsSQLExporter
    
    exporter = CardsSQLExporter("path/to/cards.db")
    exporter.export_ligand(ligand_entry)
    exporter.export_metal(metal_entry)
    exporter.export_ligand_metal(complex_entry)
    exporter.close()
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

# Path configuration
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
OUTPUT_DIR = BASE_DIR / "_output" / "pip2c_cards_sql"
DEFAULT_SQL_PATH = OUTPUT_DIR / "srd46_cards.db"


def _serialize_value(val: Any) -> Any:
    """Serialize a value for SQLite storage."""
    if val is None:
        return None
    if isinstance(val, Enum):
        return val.value
    if isinstance(val, (list, dict, tuple, frozenset)):
        return json.dumps(val, default=str)
    if is_dataclass(val):
        return json.dumps(asdict(val), default=str)
    if isinstance(val, (int, float, str, bool)):
        return val
    return str(val)


def _dataclass_to_dict(obj: Any) -> Dict[str, Any]:
    """Convert dataclass to dict, handling nested structures."""
    if obj is None:
        return {}
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, dict):
        return obj
    return {}


class CardsSQLExporter:
    """Exports cards to SQLite database."""
    
    def __init__(self, db_path: Path = DEFAULT_SQL_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._bulk = False
        self._init_schema()
    
    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn
    
    def _commit(self) -> None:
        """Commit after each export call unless a bulk transaction is open."""
        if not self._bulk:
            self.conn.commit()
    
    def begin_bulk(self) -> None:
        """Start one long transaction (and relax fsync) for bulk export; end with end_bulk()."""
        if self._bulk:
            return
        self.conn.execute("PRAGMA synchronous = OFF")
        self.conn.execute("PRAGMA journal_mode = MEMORY")
        self.conn.execute("BEGIN")
        self._bulk = True
    
    def end_bulk(self) -> None:
        """Commit the bulk transaction and restore per-call commits."""
        if not self._bulk:
            return
        self.conn.commit()
        self._bulk = False
        self.conn.execute("PRAGMA journal_mode = DELETE")
        self.conn.execute("PRAGMA synchronous = FULL")
    
    def close(self) -> None:
        if self._conn:
            if self._bulk:
                self.end_bulk()
            self._conn.commit()
            self._conn.close()
            self._conn = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    # =========================================================================
    # Schema initialization
    # =========================================================================
    
    def _init_schema(self) -> None:
        """Initialize database schema."""
        cursor = self.conn.cursor()
        
        # =====================================================================
        # METAL (Cation) tables
        # =====================================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metal_card (
                metal_id INTEGER PRIMARY KEY,
                metal_name_SRD TEXT NOT NULL,
                symbol_pure TEXT,
                charge INTEGER,
                charge_str TEXT,
                SMILES TEXT,
                InChi TEXT,
                InChiKey TEXT,
                parts_used_json TEXT,
                stoichiometry_json TEXT,
                is_simple_ion INTEGER,
                is_organometallic INTEGER,
                primary_metal TEXT,
                formula_components_json TEXT,
                parse_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # =====================================================================
        # LIGAND tables
        # =====================================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ligand_card (
                ligand_id INTEGER PRIMARY KEY,
                ligand_name_SRD TEXT NOT NULL,
                ligand_class_id INTEGER,
                ligand_class_name TEXT,
                ligand_SMILES TEXT,
                ligand_InChi TEXT,
                formula TEXT,
                composition TEXT,
                figure_definition TEXT,
                definition_HxL TEXT,
                -- Synonyms (flattened)
                synonym_iupac_name TEXT,
                synonym_common_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Schema note: the card tables are the read contract of the downstream agents/tools and carry
        # no parser-provenance columns. Placeholder ligands (LIG-04) are derived: figure_definition =
        # '***' AND formula consists of '*' only (srd46_pipeline/manual_rules.py LIGAND_PLACEHOLDER_SQL).
        
        # Ligand pKa measurements (from equilibrium maps)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ligand_pka_measured (
                pka_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ligand_id INTEGER NOT NULL,
                source TEXT,
                bracket_from_state TEXT,
                bracket_to_state TEXT,
                pKa REAL,
                pKa_type TEXT,
                temperature_c REAL,
                ionic_strength_mol_l REAL,
                solvent_id INTEGER,
                solvent_name TEXT,
                electrolyte TEXT,
                measurement_method TEXT,
                quality TEXT,
                notes TEXT,
                vlm_ids_json TEXT,
                FOREIGN KEY (ligand_id) REFERENCES ligand_card(ligand_id)
            )
        """)
        
        # Ligand pKa bracket states
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ligand_pka_bracket (
                bracket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ligand_id INTEGER NOT NULL,
                is_estimated INTEGER DEFAULT 0,
                state_id TEXT,
                charge INTEGER,
                formula TEXT,
                HxL_form TEXT,
                bracket_label TEXT,
                SMILES TEXT,
                InChi TEXT,
                model_name TEXT,
                model_version TEXT,
                confidence REAL,
                uncertainty REAL,
                notes TEXT,
                FOREIGN KEY (ligand_id) REFERENCES ligand_card(ligand_id)
            )
        """)
        
        # =====================================================================
        # LIGAND-METAL COMPLEX tables
        # =====================================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ligandmetal_card (
                card_id INTEGER PRIMARY KEY AUTOINCREMENT,
                complex_system_id INTEGER NOT NULL,
                metal_id INTEGER NOT NULL,
                ligand_id INTEGER NOT NULL,
                beta_definition_id INTEGER NOT NULL,
                complex_id TEXT,
                ligand_class_id INTEGER,
                ligand_class_name TEXT,
                metal_name_SRD TEXT,
                metal_SMILES TEXT,
                metal_InChi TEXT,
                ligand_name_SRD TEXT,
                ligand_SMILES TEXT,
                ligand_InChi TEXT,
                ligand_HxL_definition_SRD TEXT,
                beta_definition_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(complex_system_id, metal_id, ligand_id, beta_definition_id)
            )
        """)
        # placeholder card (derived, no column): every measured row of the card carries parser:placeholder=1
        
        # Stability measurements (from equilibrium maps)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ligandmetal_stability_measured (
                stability_id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id INTEGER NOT NULL,
                constant_type TEXT,
                constant_value REAL,
                temperature_c REAL,
                ionic_strength_mol_l REAL,
                solvent_id INTEGER,
                solvent_name TEXT,
                electrolyte_composition TEXT,
                equation_python TEXT,
                -- Equation info
                raw_definition TEXT,
                normalized_definition TEXT,
                equation_str TEXT,
                equation_tree_json TEXT,
                equation_sides_json TEXT,
                LHS_species_json TEXT,
                RHS_species_json TEXT,
                HxL_involved_json TEXT,
                presence_flags_json TEXT,
                reaction_type TEXT,
                element_conserved INTEGER,
                -- Citations
                citations_json TEXT,
                audit_timestamp TEXT,
                error TEXT,
                notes TEXT,                      -- str(list): SRD46 footnote ids / comments, then 'parser:<key>=<value>' strings
                                                 -- when a manual rule fired (srd46_pipeline/manual_rules.py NOTE-01;
                                                 -- 'parser:placeholder=1' marks the '*' rows whose values are NULL)
                FOREIGN KEY (card_id) REFERENCES ligandmetal_card(card_id)
            )
        """)
        
        # Stability estimated values
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ligandmetal_stability_estimated (
                estimated_id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id INTEGER NOT NULL,
                source TEXT,
                model_name TEXT,
                model_version TEXT,
                constant_type TEXT,
                constant_value REAL,
                temperature_c REAL,
                ionic_strength_mol_l REAL,
                confidence REAL,
                uncertainty REAL,
                notes TEXT,
                FOREIGN KEY (card_id) REFERENCES ligandmetal_card(card_id)
            )
        """)
        
        # =====================================================================
        # REFERENCE tables (normalized - shared across all cards)
        # =====================================================================
        
        # Literature Alternative References (short citations)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ref_literature_alt (
                literature_alt_id INTEGER PRIMARY KEY,
                shortcut TEXT,
                citation TEXT
            )
        """)
        
        # Primary Literature References
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ref_literature (
                literature_id INTEGER PRIMARY KEY,
                paper_id INTEGER,
                year INTEGER,
                issue INTEGER,
                page INTEGER,
                paper_name TEXT
            )
        """)
        
        # Authors
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ref_author (
                author_id INTEGER PRIMARY KEY,
                name TEXT
            )
        """)
        
        # Footnotes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ref_footnote (
                footnote_id TEXT PRIMARY KEY,
                shortcut TEXT,
                text TEXT
            )
        """)
        
        # =====================================================================
        # REFERENCE LINKAGE tables (junction tables)
        # Links VLM IDs to reference entries for each measurement
        # =====================================================================
        
        # Links pKa measurements (via vlm_id) to literature_alt references
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ref_vlm_literature_alt (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vlm_id INTEGER NOT NULL,
                literature_alt_id INTEGER NOT NULL,
                UNIQUE(vlm_id, literature_alt_id),
                FOREIGN KEY (literature_alt_id) REFERENCES ref_literature_alt(literature_alt_id)
            )
        """)
        
        # Links pKa measurements (via vlm_id) to literature references
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ref_vlm_literature (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vlm_id INTEGER NOT NULL,
                literature_id INTEGER NOT NULL,
                UNIQUE(vlm_id, literature_id),
                FOREIGN KEY (literature_id) REFERENCES ref_literature(literature_id)
            )
        """)
        
        # Links pKa measurements (via vlm_id) to authors
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ref_vlm_author (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vlm_id INTEGER NOT NULL,
                author_id INTEGER NOT NULL,
                UNIQUE(vlm_id, author_id),
                FOREIGN KEY (author_id) REFERENCES ref_author(author_id)
            )
        """)
        
        # Links pKa measurements (via vlm_id) to footnotes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ref_vlm_footnote (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vlm_id INTEGER NOT NULL,
                footnote_id TEXT NOT NULL,
                UNIQUE(vlm_id, footnote_id),
                FOREIGN KEY (footnote_id) REFERENCES ref_footnote(footnote_id)
            )
        """)
        
        # Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ligand_pka_ligand ON ligand_pka_measured(ligand_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ligand_bracket_ligand ON ligand_pka_bracket(ligand_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lm_card_metal ON ligandmetal_card(metal_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lm_card_ligand ON ligandmetal_card(ligand_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lm_stab_card ON ligandmetal_stability_measured(card_id)")
        
        # Reference lookup indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ref_vlm_lit_alt_vlm ON ref_vlm_literature_alt(vlm_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ref_vlm_lit_vlm ON ref_vlm_literature(vlm_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ref_vlm_author_vlm ON ref_vlm_author(vlm_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ref_vlm_footnote_vlm ON ref_vlm_footnote(vlm_id)")
        
        self._commit()
    
    # =========================================================================
    # Export methods
    # =========================================================================
    
    def export_metal(self, entry) -> int:
        """Export a CationEntry to database. Returns metal_id."""
        cursor = self.conn.cursor()
        
        data = _dataclass_to_dict(entry)
        
        cursor.execute("""
            INSERT OR REPLACE INTO metal_card (
                metal_id, metal_name_SRD, symbol_pure, charge, charge_str,
                SMILES, InChi, InChiKey, parts_used_json, stoichiometry_json,
                is_simple_ion, is_organometallic, primary_metal,
                formula_components_json, parse_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("metal_id"),
            data.get("metal_name_SRD"),
            data.get("symbol_pure"),
            data.get("charge"),
            data.get("charge_str"),
            data.get("SMILES"),
            data.get("InChi"),
            data.get("InChiKey"),
            _serialize_value(data.get("parts_used")),
            _serialize_value(data.get("stoichiometry")),
            1 if data.get("is_simple_ion") else (0 if data.get("is_simple_ion") is False else None),
            1 if data.get("is_organometallic") else (0 if data.get("is_organometallic") is False else None),
            data.get("primary_metal"),
            _serialize_value(data.get("formula_components")),
            data.get("parse_notes"),
        ))
        
        self._commit()
        return data.get("metal_id")
    
    def export_ligand(self, entry) -> int:
        """Export a LigandEntry to database. Returns ligand_id."""
        cursor = self.conn.cursor()
        
        data = _dataclass_to_dict(entry)
        
        # Main ligand record
        synonyms = data.get("synonyms") or {}
        
        cursor.execute("""
            INSERT OR REPLACE INTO ligand_card (
                ligand_id, ligand_name_SRD, ligand_class_id, ligand_class_name,
                ligand_SMILES, ligand_InChi, formula, composition,
                figure_definition, definition_HxL,
                synonym_iupac_name, synonym_common_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("ligand_id"),
            data.get("ligand_name_SRD"),
            data.get("ligand_class_id"),
            data.get("ligand_class_name"),
            data.get("ligand_SMILES"),
            data.get("ligand_InChi"),
            data.get("formula"),
            data.get("composition"),
            data.get("figure_definition"),
            data.get("definition_HxL"),
            synonyms.get("iupac_name"),
            synonyms.get("common_name"),
        ))
        
        ligand_id = data.get("ligand_id")
        
        # Delete existing pKa records for this ligand
        cursor.execute("DELETE FROM ligand_pka_measured WHERE ligand_id = ?", (ligand_id,))
        cursor.execute("DELETE FROM ligand_pka_bracket WHERE ligand_id = ?", (ligand_id,))
        
        # Export measured pKa
        pka_block = data.get("pKa") or {}
        for pka in pka_block.get("measured_pKa") or []:
            conditions = pka.get("conditions") or {}
            solvent = conditions.get("solvent") or {}
            evidence = pka.get("evidence") or {}
            
            cursor.execute("""
                INSERT INTO ligand_pka_measured (
                    ligand_id, source, bracket_from_state, bracket_to_state,
                    pKa, pKa_type, temperature_c, ionic_strength_mol_l,
                    solvent_id, solvent_name, electrolyte,
                    measurement_method, quality, notes, vlm_ids_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ligand_id,
                pka.get("source"),
                pka.get("bracket_from_state"),
                pka.get("bracket_to_state"),
                pka.get("pKa"),
                pka.get("pKa_type"),
                conditions.get("temperature_c"),
                conditions.get("ionic_strength_mol_l"),
                solvent.get("solvent_id"),
                solvent.get("name"),
                conditions.get("electrolyte"),
                pka.get("measurement_method"),
                pka.get("quality"),
                pka.get("notes"),
                _serialize_value(evidence.get("verkn_ligand_metal_ids")),
            ))
            
            # Export references to normalized tables
            vlm_ids = evidence.get("verkn_ligand_metal_ids") or []
            references = evidence.get("references") or {}
            self._export_references_for_vlm_ids(vlm_ids, references)
        
        # Export pKa brackets (measured)
        bracket_block = data.get("pKa_bracket") or {}
        for bracket in bracket_block.get("measured_pKa_bracket") or []:
            cursor.execute("""
                INSERT INTO ligand_pka_bracket (
                    ligand_id, is_estimated, state_id, charge, formula,
                    HxL_form, bracket_label, SMILES, InChi, notes
                ) VALUES (?, 0, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ligand_id,
                bracket.get("state_id"),
                bracket.get("charge"),
                bracket.get("formula"),
                bracket.get("HxL_form"),
                bracket.get("bracket_label"),
                bracket.get("SMILES"),
                bracket.get("InChi"),
                bracket.get("notes"),
            ))
        
        # Export pKa brackets (estimated)
        for bracket in bracket_block.get("estimated_pKa_bracket") or []:
            cursor.execute("""
                INSERT INTO ligand_pka_bracket (
                    ligand_id, is_estimated, state_id, charge, formula,
                    HxL_form, bracket_label, SMILES, InChi,
                    model_name, model_version, confidence, uncertainty, notes
                ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ligand_id,
                bracket.get("state_id"),
                bracket.get("charge"),
                bracket.get("formula"),
                bracket.get("HxL_form"),
                bracket.get("bracket_label"),
                bracket.get("SMILES"),
                bracket.get("InChi"),
                bracket.get("model_name"),
                bracket.get("model_version"),
                bracket.get("confidence"),
                bracket.get("uncertainty"),
                bracket.get("notes"),
            ))
        
        self._commit()
        return ligand_id
    
    def export_ligand_metal(self, entry) -> int:
        """Export a MetalLigandComplexEntry to database. Returns card_id."""
        cursor = self.conn.cursor()
        
        data = _dataclass_to_dict(entry)
        
        # Main card record
        cursor.execute("""
            INSERT OR REPLACE INTO ligandmetal_card (
                complex_system_id, metal_id, ligand_id, beta_definition_id,
                complex_id, ligand_class_id, ligand_class_name,
                metal_name_SRD, metal_SMILES, metal_InChi,
                ligand_name_SRD, ligand_SMILES, ligand_InChi,
                ligand_HxL_definition_SRD, beta_definition_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("complex_system_id"),
            data.get("metal_id"),
            data.get("ligand_id"),
            data.get("beta_definition_id"),
            data.get("complex_id"),
            data.get("ligand_class_id"),
            data.get("ligand_class_name"),
            data.get("metal_name_SRD"),
            data.get("metal_SMILES"),
            data.get("metal_InChi"),
            data.get("ligand_name_SRD"),
            data.get("ligand_SMILES"),
            data.get("ligand_InChi"),
            data.get("ligand_HxL_definition_SRD"),
            data.get("beta_definition_name"),
        ))
        
        card_id = cursor.lastrowid
        
        # Export stability info
        stability_info = data.get("stability_info") or {}
        
        # Measured values
        for measured in stability_info.get("measured_value") or []:
            constant = measured.get("constant") or {}
            conditions = measured.get("conditions") or {}
            solvent = conditions.get("solvent") or {}
            eq_info = measured.get("equation_info") or {}
            presence = eq_info.get("presence_flags") or {}
            
            # entry_value_raw / in_parentheses / is_placeholder of the constant block are not columns:
            # the entry builder has already put them into ``notes`` as 'parser:<key>=<value>' (NOTE-01)
            cursor.execute("""
                INSERT INTO ligandmetal_stability_measured (
                    card_id, constant_type, constant_value,
                    temperature_c, ionic_strength_mol_l,
                    solvent_id, solvent_name, electrolyte_composition,
                    equation_python, raw_definition, normalized_definition,
                    equation_str, equation_tree_json, equation_sides_json,
                    LHS_species_json, RHS_species_json, HxL_involved_json,
                    presence_flags_json, reaction_type, element_conserved,
                    citations_json, audit_timestamp, error, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                card_id,
                _serialize_value(constant.get("entry_type")),
                constant.get("entry_value"),
                conditions.get("temperature_c"),
                conditions.get("ionic_strength_mol_l"),
                solvent.get("solvent_id"),
                solvent.get("name"),
                solvent.get("electrolyte_and_composition"),
                measured.get("equation_python"),
                eq_info.get("raw_definition"),
                eq_info.get("normalized_definition"),
                eq_info.get("equation_str"),
                _serialize_value(eq_info.get("equation_tree")),
                _serialize_value(eq_info.get("equation_sides")),
                _serialize_value(eq_info.get("LHS_species")),
                _serialize_value(eq_info.get("RHS_species")),
                _serialize_value(eq_info.get("HxL_involved")),
                _serialize_value(presence),
                eq_info.get("reaction_type"),
                1 if eq_info.get("element_conserved") else (0 if eq_info.get("element_conserved") is False else None),
                _serialize_value(measured.get("citations")),
                measured.get("audit_timestamp"),
                measured.get("error"),
                measured.get("notes"),
            ))
        
        # Estimated values
        for estimated in stability_info.get("estimated_value") or []:
            constant = estimated.get("constant") or {}
            conditions = estimated.get("conditions") or {}
            
            cursor.execute("""
                INSERT INTO ligandmetal_stability_estimated (
                    card_id, source, model_name, model_version,
                    constant_type, constant_value,
                    temperature_c, ionic_strength_mol_l,
                    confidence, uncertainty, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                card_id,
                estimated.get("source"),
                estimated.get("model_name"),
                estimated.get("model_version"),
                _serialize_value(constant.get("entry_type")),
                constant.get("entry_value"),
                conditions.get("temperature_c"),
                conditions.get("ionic_strength_mol_l"),
                estimated.get("confidence"),
                estimated.get("uncertainty"),
                estimated.get("notes"),
            ))
        
        self._commit()
        return card_id
    
    # =========================================================================
    # Reference export helpers
    # =========================================================================
    
    def _export_references_for_vlm_ids(
        self,
        vlm_ids: List[int],
        references: Dict[str, Any],
    ) -> None:
        """Export references to normalized tables and link to VLM IDs.
        
        Args:
            vlm_ids: List of verkn_ligand_metal IDs to link references to
            references: ReferencesEntry dict with literature_alt, literature, authors, footnotes
        """
        if not vlm_ids or not references:
            return
        
        cursor = self.conn.cursor()
        
        # Extract reference lists
        literature_alt_list = references.get("literature_alt") or []
        literature_list = references.get("literature") or []
        authors_list = references.get("authors") or []
        footnotes_list = references.get("footnotes") or []
        
        # Insert literature_alt entries (upsert pattern)
        for lit_alt in literature_alt_list:
            if not isinstance(lit_alt, dict):
                continue
            lit_alt_id = lit_alt.get("literature_alt_id")
            if lit_alt_id is None:
                continue
            
            # Insert or ignore (already exists)
            cursor.execute("""
                INSERT OR IGNORE INTO ref_literature_alt (literature_alt_id, shortcut, citation)
                VALUES (?, ?, ?)
            """, (
                lit_alt_id,
                lit_alt.get("shortcut"),
                lit_alt.get("citation"),
            ))
            
            # Link to each VLM ID
            for vlm_id in vlm_ids:
                cursor.execute("""
                    INSERT OR IGNORE INTO ref_vlm_literature_alt (vlm_id, literature_alt_id)
                    VALUES (?, ?)
                """, (vlm_id, lit_alt_id))
        
        # Insert literature entries
        for lit in literature_list:
            if not isinstance(lit, dict):
                continue
            lit_id = lit.get("literature_id")
            if lit_id is None:
                continue
            
            cursor.execute("""
                INSERT OR IGNORE INTO ref_literature (literature_id, paper_id, year, issue, page, paper_name)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                lit_id,
                lit.get("paper_id"),
                lit.get("year"),
                lit.get("issue"),
                lit.get("page"),
                lit.get("paper_name"),
            ))
            
            for vlm_id in vlm_ids:
                cursor.execute("""
                    INSERT OR IGNORE INTO ref_vlm_literature (vlm_id, literature_id)
                    VALUES (?, ?)
                """, (vlm_id, lit_id))
        
        # Insert author entries
        for author in authors_list:
            if not isinstance(author, dict):
                continue
            author_id = author.get("author_id")
            if author_id is None:
                continue
            
            cursor.execute("""
                INSERT OR IGNORE INTO ref_author (author_id, name)
                VALUES (?, ?)
            """, (
                author_id,
                author.get("name"),
            ))
            
            for vlm_id in vlm_ids:
                cursor.execute("""
                    INSERT OR IGNORE INTO ref_vlm_author (vlm_id, author_id)
                    VALUES (?, ?)
                """, (vlm_id, author_id))
        
        # Insert footnote entries
        for footnote in footnotes_list:
            if not isinstance(footnote, dict):
                continue
            footnote_id = footnote.get("footnote_id")
            if footnote_id is None:
                continue
            
            cursor.execute("""
                INSERT OR IGNORE INTO ref_footnote (footnote_id, shortcut, text)
                VALUES (?, ?, ?)
            """, (
                str(footnote_id),
                footnote.get("shortcut"),
                footnote.get("text"),
            ))
            
            for vlm_id in vlm_ids:
                cursor.execute("""
                    INSERT OR IGNORE INTO ref_vlm_footnote (vlm_id, footnote_id)
                    VALUES (?, ?)
                """, (vlm_id, str(footnote_id)))
    
    def export_references(
        self,
        refs_entry: Any,
        vlm_ids: List[int],
    ) -> None:
        """Export references from a ReferencesEntry dataclass to normalized tables.
        
        This is the public API for exporting references. It accepts either a
        ReferencesEntry dataclass or a dict-like object and links references
        to the provided VLM IDs.
        
        Args:
            refs_entry: ReferencesEntry dataclass or dict with literature_alt,
                       literature, authors, footnotes, reference_ids fields
            vlm_ids: List of verkn_ligand_metal IDs to link references to
        """
        if refs_entry is None or not vlm_ids:
            return
        
        # Convert dataclass to dict if needed
        if is_dataclass(refs_entry):
            refs_dict = asdict(refs_entry)
        elif isinstance(refs_entry, dict):
            refs_dict = refs_entry
        else:
            # Attempt to convert via asdict fallback
            try:
                refs_dict = asdict(refs_entry)
            except Exception:
                return
        
        # Convert nested dataclasses to dicts
        def _convert_nested(items: List) -> List[Dict]:
            result = []
            for item in items:
                if is_dataclass(item):
                    result.append(asdict(item))
                elif isinstance(item, dict):
                    result.append(item)
            return result
        
        refs_dict["literature_alt"] = _convert_nested(refs_dict.get("literature_alt") or [])
        refs_dict["literature"] = _convert_nested(refs_dict.get("literature") or [])
        refs_dict["authors"] = _convert_nested(refs_dict.get("authors") or [])
        refs_dict["footnotes"] = _convert_nested(refs_dict.get("footnotes") or [])
        
        self._export_references_for_vlm_ids(vlm_ids, refs_dict)
        self._commit()
    
    # =========================================================================
    # Batch export methods
    # =========================================================================
    
    def export_all_metals(self, entries: List, verbose: bool = True) -> int:
        """Export multiple metal entries. Returns count."""
        count = 0
        for i, entry in enumerate(entries):
            self.export_metal(entry)
            count += 1
            if verbose and (i + 1) % 100 == 0:
                print(f"  Exported {i + 1} metals...")
        if verbose:
            print(f"  Total metals exported: {count}")
        return count
    
    def export_all_ligands(self, entries: List, verbose: bool = True) -> int:
        """Export multiple ligand entries. Returns count."""
        count = 0
        for i, entry in enumerate(entries):
            self.export_ligand(entry)
            count += 1
            if verbose and (i + 1) % 100 == 0:
                print(f"  Exported {i + 1} ligands...")
        if verbose:
            print(f"  Total ligands exported: {count}")
        return count
    
    def export_all_ligand_metals(self, entries: List, verbose: bool = True) -> int:
        """Export multiple ligand-metal entries. Returns count."""
        count = 0
        for i, entry in enumerate(entries):
            self.export_ligand_metal(entry)
            count += 1
            if verbose and (i + 1) % 1000 == 0:
                print(f"  Exported {i + 1} complexes...")
        if verbose:
            print(f"  Total complexes exported: {count}")
        return count
    
    # =========================================================================
    # Statistics
    # =========================================================================
    
    def get_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        cursor = self.conn.cursor()
        
        stats = {}
        # Core tables
        for table in ["metal_card", "ligand_card", "ligandmetal_card", 
                      "ligand_pka_measured", "ligand_pka_bracket",
                      "ligandmetal_stability_measured", "ligandmetal_stability_estimated"]:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            stats[table] = cursor.fetchone()[0]
        
        # Reference tables
        for table in ["ref_literature_alt", "ref_literature", "ref_author", "ref_footnote",
                      "ref_vlm_literature_alt", "ref_vlm_literature", "ref_vlm_author", "ref_vlm_footnote"]:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[table] = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                # Table may not exist in older databases
                stats[table] = 0
        
        return stats


# =============================================================================
# Convenience function
# =============================================================================

def export_cards_to_sql(
    metals: List = None,
    ligands: List = None,
    complexes: List = None,
    db_path: Path = DEFAULT_SQL_PATH,
    verbose: bool = True,
) -> Dict[str, int]:
    """Export all cards to SQL database."""
    with CardsSQLExporter(db_path) as exporter:
        results = {}
        
        if metals:
            if verbose:
                print(f"Exporting {len(metals)} metal cards...")
            results["metals"] = exporter.export_all_metals(metals, verbose)
        
        if ligands:
            if verbose:
                print(f"Exporting {len(ligands)} ligand cards...")
            results["ligands"] = exporter.export_all_ligands(ligands, verbose)
        
        if complexes:
            if verbose:
                print(f"Exporting {len(complexes)} complex cards...")
            results["complexes"] = exporter.export_all_ligand_metals(complexes, verbose)
        
        results["stats"] = exporter.get_stats()
        
        if verbose:
            print(f"\nDatabase saved to: {db_path}")
            print(f"Stats: {results['stats']}")
        
        return results
