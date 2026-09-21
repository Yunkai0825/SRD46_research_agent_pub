"""SRD46 Entry Builder - Main Module.

This module provides functions to build ligand, cation, and complex entries
from SRD46 CSV data files (or from in-memory tables registered through
``pip2c_2_entry_builder_helpers.register_table``). The heavy lifting for pKa
extraction and equation parsing is delegated to pip2c_2_entry_builder_helpers.

All lookups are index-based and the per-id builders are memoized, so building
the full set of ~90k complexes is linear in the number of rows.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

# =============================================================================
# Logging configuration
# =============================================================================

logger = logging.getLogger(__name__)

def setup_logging(level: int = logging.INFO, log_file: Optional[Path] = None) -> None:
    """Configure logging for the entry builder.
    
    Args:
        level: Logging level (default: INFO)
        log_file: Optional path to log file
    """
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Configure main logger
    logger.setLevel(level)
    logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)
    
    # Also configure helpers logging
    from pip2c_2_entry_builder_helpers.config import setup_logging as helpers_setup_logging
    helpers_setup_logging(level=level, log_file=log_file)

# Import from local schema modules
from pip2c_1_json_schemas import (
    MissingFieldTracker,
    create_ligand_entry,
    create_cation_entry,
    create_metal_ligand_complex_entry,
    create_references_entry_from_tables,
    create_references_entry_by_ligand_metal,
    get_missing_field_report_text,
)

# Import all helpers from the helpers package
from pip2c_2_entry_builder_helpers import (
    # Config
    BASE_DIR,
    PIP1_PARSED_DIR,
    SRD46_SQL_CSV_DIR,
    FILENAMES,
    DEBUG_FLAG,
    # CSV I/O
    get_col,
    pick,
    pick_any,
    read_csv_dicts,
    find_first_row,
    lookup_row,
    map_by_key,
    collect_comment_like_fields_from_row,
    # pKa builder
    build_pka_block,
    # Equation parser
    parse_equation_tree,
)


# ==============================================================
# Memoization / cached lookup maps
# ==============================================================

_LIGAND_DATA_CACHE: dict[int, dict[str, Any]] = {}
_CATION_DATA_CACHE: dict[int, dict[str, Any]] = {}
_MAP_CACHE: dict[tuple[str, tuple[str, ...]], dict[str, dict[str, Any]]] = {}


def _cached_map(name: str, keys: list[str]) -> dict[str, dict[str, Any]]:
    """map_by_key(read_csv_dicts(name), keys), built once per (table, keys)."""
    cache_key = (name, tuple(keys))
    m = _MAP_CACHE.get(cache_key)
    if m is None:
        m = map_by_key(read_csv_dicts(name), keys)
        _MAP_CACHE[cache_key] = m
    return m


def clear_builder_caches() -> None:
    """Drop memoized ligand/cation dicts and lookup maps (e.g. after re-registering tables)."""
    _LIGAND_DATA_CACHE.clear()
    _CATION_DATA_CACHE.clear()
    _MAP_CACHE.clear()


# ==============================================================
# Entry builders from the csv files
# ==============================================================

_LIGAND_ID_KEYS = ["ligandenID", "ligandenNr", "ligand_id", "ligandNr"]


def build_ligand_data(ligand_id: int) -> dict[str, Any]:
    """Build ligand data dict from SRD46 CSV files.

    Memoized per ligand_id; the returned dict is shared and must be treated as read-only.
    """
    cached = _LIGAND_DATA_CACHE.get(int(ligand_id))
    if cached is not None:
        return cached

    logger.info(f"build_ligand_data: Building ligand {ligand_id}")
    
    # Indexed lookup in the moldata table (registered in-memory table or CSV)
    lig_mol_path = FILENAMES["liganden_moldata"]
    logger.debug(f"build_ligand_data: Searching moldata in: {lig_mol_path}")
    if DEBUG_FLAG:
        print(f"[INFO] Searching moldata in: {lig_mol_path}")
    mol_row = find_first_row(lig_mol_path, _LIGAND_ID_KEYS, ligand_id) or {}
    
    lig_row = lookup_row("liganden", _LIGAND_ID_KEYS, ligand_id) or {}

    # Class lookup
    cls_id = pick(lig_row, "ligand_classNr", "ligand_classID")
    cls_row = None
    if cls_id is not None:
        cls_row = lookup_row("ligand_class", ["ligand_classID", "ligand_classNr"], cls_id) or {}

    # Debug moldata
    if mol_row:
        logger.debug(f"build_ligand_data: Found moldata for ligand {ligand_id}, keys: {len(mol_row.keys())}")
        if DEBUG_FLAG:
            print("[DEBUG] Moldata keys for ligand", ligand_id, ":", sorted(mol_row.keys()))
    else:
        logger.warning(f"build_ligand_data: No moldata row found for ligand {ligand_id}")
        if DEBUG_FLAG:
            print(f"[WARN] No moldata row found for ligand {ligand_id}")

    # Build pKa block using helper
    pka_block = build_pka_block(mol_row, ligand_id)

    # Normalize ligand_class_id to int when possible
    raw_cls_id = pick(lig_row, "ligand_classNr", "ligand_classID")
    try:
        ligand_class_id_val = None if raw_cls_id in (None, "") else int(raw_cls_id)
    except Exception:
        ligand_class_id_val = None

    out = {
        "ligand_id": ligand_id,
        "ligand_name_SRD": pick(lig_row, "name_ligand", default=""),
        "ligand_class_id": ligand_class_id_val,
        "ligand_class_name": pick(cls_row, "name_ligandclass"),
        "formula": pick(lig_row, "formula", default=get_col(mol_row, "formula")),
        "composition": get_col(mol_row, "COMPOSITION"),
        "ligand_SMILES": get_col(mol_row, "SMILES"),
        "ligand_InChi": get_col(mol_row, "InChi"),
        "synonyms": {
            "iupac_name": get_col(mol_row, "IUPAC_NAME"),
            "common_name": get_col(mol_row, "COMMON_NAME"),
        },
        "figure_definition": pick(lig_row, "figure_definition"),
        "definition_HxL": pick_any(mol_row, ["figure_definition_parsed", "definition_HxL"]),
        # Validated against the desalted structure by pip1c_3; the raw salt formula may be neutral.
        "definition_HxL_charge": get_col(mol_row, "figure_definition_charge"),
        "pKa": pka_block,
    }

    # Aggregate comment-like fields
    try:
        notes: list[str] = []
        for src_row in (lig_row, mol_row, cls_row):
            if src_row:
                notes.extend(collect_comment_like_fields_from_row(src_row))
        seen = set()
        deduped = [n for n in notes if not (n in seen or seen.add(n))]
        if deduped:
            out["notes"] = deduped
    except Exception:
        pass

    _LIGAND_DATA_CACHE[int(ligand_id)] = out
    return out


def build_cation_data(metal_id: int) -> dict[str, Any]:
    """Build cation/metal data dict from SRD46 CSV files.

    Memoized per metal_id; the returned dict is shared and must be treated as read-only.
    """
    cached = _CATION_DATA_CACHE.get(int(metal_id))
    if cached is not None:
        return cached

    logger.info(f"build_cation_data: Building metal/cation {metal_id}")

    m_row = lookup_row("metal", ["metalID", "metalNr"], metal_id) or {}
    mp_row = lookup_row("metal_parsed", ["metalID", "metalNr"], metal_id) or {}
    
    logger.debug(f"build_cation_data: metal row found={bool(m_row)}, parsed row found={bool(mp_row)}")

    # Parse JSON-like fields
    def _parse_json_or_split(val, split_char=";"):
        if isinstance(val, str) and val.strip():
            try:
                return json.loads(val)
            except Exception:
                return [p.strip() for p in val.split(split_char) if p.strip()] if split_char else None
        return val

    parts_used = _parse_json_or_split(pick_any(mp_row, ["parts_used"]))
    stoichiometry = _parse_json_or_split(pick_any(mp_row, ["stoichiometry"]), None)
    formula_components = _parse_json_or_split(pick_any(mp_row, ["formula_components"]), None)

    if stoichiometry is None and isinstance(formula_components, dict):
        stoichiometry = formula_components

    # Charge as int
    charge_raw = pick_any(mp_row, ["charge"])
    charge_int = None
    if charge_raw not in (None, "", "\\N"):
        try:
            charge_int = int(float(str(charge_raw)))
        except (ValueError, TypeError):
            pass

    symbol_pure = pick_any(mp_row, ["symbol_pure"]) or pick_any(m_row, ["name_metal_pur"])
    smiles = pick_any(mp_row, ["SMILES", "smiles", "metal_full_smiles"])
    inchi = pick_any(mp_row, ["InChI", "InChi", "inchi", "metal_full_inchi"])
    inchikey = pick_any(mp_row, ["InChIKey", "InChiKey", "inchikey", "metal_full_inchikey"])

    out = {
        "metal_id": metal_id,
        "metal_name_SRD": pick_any(m_row, ["name_metal"], default="") or pick_any(mp_row, ["name_metal"], default=""),
        "symbol_pure": symbol_pure,
        "charge": charge_int,
        "charge_str": pick_any(mp_row, ["charge_str"]),
        "SMILES": smiles,
        "InChi": inchi,
        "InChiKey": inchikey,
        "parts_used": parts_used,
        "stoichiometry": stoichiometry,
        "is_simple_ion": pick_any(mp_row, ["is_simple_ion"]),
        "is_organometallic": pick_any(mp_row, ["is_organometallic"]),
        "primary_metal": pick_any(mp_row, ["primary_metal"]),
        "formula_components": formula_components,
        "parse_notes": pick_any(mp_row, ["parse_notes"]),
    }
    _CATION_DATA_CACHE[int(metal_id)] = out
    return out


def build_complex_data(verkn_id: int) -> dict[str, Any]:
    """Build complex/metal-ligand data dict from SRD46 CSV files."""
    logger.info(f"build_complex_data: Building complex VLM {verkn_id}")
    
    verkn = lookup_row("verkn_ligand_metal", ["verkn_ligand_metalID"], verkn_id) or {}
    
    if not verkn:
        logger.warning(f"build_complex_data: No VLM row found for {verkn_id}")

    # Lookup maps over the reference CSVs (built once, cached)
    const_map = _cached_map("constanttyp", ["constanttypID", "constanttypNr"])
    solv_map = _cached_map("solvent", ["solventID"])
    beta_map = _cached_map("beta_definition", ["beta_definitionID"])
    beta_fix_map = _cached_map("beta_definition_fixed", ["beta_definitionID"])

    # Resolve IDs
    consttyp_nr = str(pick(verkn, "constanttypNr", default=""))
    const_name = pick(const_map.get(consttyp_nr, {}), "name_constanttyp") if consttyp_nr else None

    solv_id = str(pick(verkn, "solventNr", default=""))
    solv_name = pick(solv_map.get(solv_id, {}), "name_solvent") if solv_id else None

    beta_id = str(pick(verkn, "beta_definitionNr", default=""))
    beta_row = beta_map.get(beta_id, {}) if beta_id else {}
    beta_fix_row = beta_fix_map.get(beta_id, {}) if beta_id else {}

    # Parse equation using helper
    eq_result = parse_equation_tree(
        pick_any(beta_fix_row, ["equation_tree_json", "beta_eq_tree_json"]),
        beta_fix_row
    )

    # Numeric values: when the registered verkn table is the canonical one produced by stage
    # raw_canonical (srd46_pipeline; manual rules VLM-01..03 declared in srd46_pipeline/manual_rules.py)
    # it carries parsed *_value columns ('*' placeholders -> None, '(x)' -> x). Standalone CSV
    # runs lack them and fall back to the verbatim strings.
    constant_raw = pick(verkn, "constant")
    canonical = "constant_value" in verkn
    constant_value = pick(verkn, "constant_value") if canonical else constant_raw
    temperature = pick(verkn, "temperature_value") if canonical else pick(verkn, "temperature")
    ionic_strength = pick(verkn, "ionicstrength_value") if canonical else pick(verkn, "ionicstrength")
    in_parentheses = (str(pick(verkn, "constant_in_parentheses", default="0")).strip() == "1") if canonical else None
    # VLM-01 (srd46_pipeline/manual_rules.py): canonical is_placeholder flag ('*' constant rows). Internal only:
    # the SQL exporter writes none of entry_value_raw / in_parentheses / is_placeholder as columns; the same
    # facts reach the cards DB as 'parser:<key>=<value>' notes (NOTE-01, appended below).
    is_placeholder = (str(pick(verkn, "is_placeholder", default="0")).strip() == "1") if canonical else None

    # Carry both existing parser representations into their corresponding card fields.
    equation_python = pick_any(beta_fix_row, ["equation_python", "beta_eq_str_python_final"])
    equation_sides = pick_any(beta_fix_row, ["equation_sides", "beta_eq_sides_final", "beta_eq_sides"])
    stability_info = {
        "equation_python": equation_python,
        "constant": {
            "entry_type": const_name,
            "entry_value": constant_value,
            "entry_value_raw": constant_raw,
            "in_parentheses": in_parentheses,
            "is_placeholder": is_placeholder,
            "constanttypNr": consttyp_nr,
            "constanttypID": pick(const_map.get(consttyp_nr, {}), "constanttypID"),
        },
        "conditions": {
            "temperature_c": temperature,
            "ionic_strength_mol_l": ionic_strength,
            "solvent": {
                "solvent_id": pick(verkn, "solventNr"),
                "name": solv_name,
                "electrolyte_and_composition": pick(verkn, "electrolyte"),
            },
        },
        "equation_info": {
            "raw_definition": pick(beta_row, "name_beta_definition", default=""),
            "normalized_definition": pick(beta_fix_row, "name_beta_definition_fixed"),
            "equation_str": equation_python,
            "equation_sides": equation_sides,
            "equation_tree": eq_result["eq_tree"],
            "LHS_species": eq_result["lhs_species"],
            "RHS_species": eq_result["rhs_species"],
            "HxL_involved": eq_result["hxl_involved"],
            "presence_flags": eq_result["presence_flags"],
            "reaction_type": pick(beta_fix_row, "reaction_type"),
            "element_conserved": pick(beta_fix_row, "element_conserved_final"),
        },
        "audit_timestamp": pick(verkn, "Acc_feld"),
        "error": pick(verkn, "error"),
    }

    out = {
        "complex_system_id": verkn_id,
        "metal_id": pick(verkn, "metalNr", default=0),
        "ligand_id": pick(verkn, "ligandenNr", default=0),
        "beta_definition_id": pick(verkn, "beta_definitionNr", default=0),
        "stability_info": stability_info,
    }

    # Populate structural identifiers from metal/ligand data
    _populate_structural_identifiers(out)

    # Aggregate comment-like fields
    try:
        notes: list[str] = []
        for src_row in (verkn, beta_row, beta_fix_row):
            if src_row:
                notes.extend(collect_comment_like_fields_from_row(src_row))
        seen = set()
        deduped = [n for n in notes if not (n in seen or seen.add(n))]
    except Exception:
        deduped = []
    # NOTE-01 (srd46_pipeline/manual_rules.py): the canonical verkn table carries the parser notes of the
    # row ('parser:<key>=<value>', space-separated, empty when no manual rule fired) in ``parser_tokens``;
    # they go behind the SRD46 footnotes/comments so the original shape of ``notes`` is untouched for
    # rows without rules. Standalone CSV runs have no such column -> nothing appended.
    parser_tokens = str(pick(verkn, "parser_tokens", default="") or "").split()
    deduped.extend(t for t in parser_tokens if t not in deduped)
    if deduped:
        out["stability_info"]["notes"] = deduped

    return out


def _populate_structural_identifiers(out: dict[str, Any]) -> None:
    """Populate metal/ligand structural identifiers in complex output dict."""
    try:
        mid = out.get("metal_id") or 0
        lid = out.get("ligand_id") or 0
        
        mdata = build_cation_data(int(mid)) if mid else {}
        ldata = build_ligand_data(int(lid)) if lid else {}

        if mdata:
            out["metal_SMILES"] = mdata.get("SMILES") or mdata.get("smiles")
            out["metal_InChi"] = mdata.get("InChi") or mdata.get("inchi")
            out["metal_name_SRD"] = mdata.get("metal_name_SRD") or mdata.get("metal_name")

        if ldata:
            # Try to get SMILES from various sources
            pka_hxl = None
            try:
                if isinstance(ldata.get("pKa"), dict):
                    pka_hxl = ldata.get("pKa", {}).get("estimated_pKa", [{}])[0].get("hxl_states", [{}])[0]
            except Exception:
                pass
            
            out["ligand_SMILES"] = (ldata.get("ligand_SMILES") or ldata.get("SMILES") or 
                                    (pick_any(pka_hxl, ["SMILES"]) if pka_hxl else None))
            out["ligand_InChi"] = (ldata.get("ligand_InChi") or ldata.get("InChi") or
                                   (pick_any(pka_hxl, ["InChi"]) if pka_hxl else None))
            out["ligand_name_SRD"] = ldata.get("ligand_name_SRD") or ldata.get("name_ligand")
            out["ligand_class_id"] = ldata.get("ligand_class_id") or ldata.get("ligand_classNr")
            out["ligand_class_name"] = ldata.get("ligand_class_name")
            
            # HxL definition
            ligand_hxl = ldata.get("definition_HxL") or ldata.get("figure_definition_parsed")
            if not ligand_hxl:
                # Try to get from pKa block
                pka_block = ldata.get("pKa") if isinstance(ldata.get("pKa"), dict) else None
                if pka_block:
                    for entries_key in ("measured_pKa", "estimated_pKa"):
                        for entry in (pka_block.get(entries_key) or []):
                            try:
                                hs = entry.get("hxl_states", [])
                                if hs and isinstance(hs[0], dict):
                                    val = hs[0].get("HxL_form")
                                    if val:
                                        ligand_hxl = str(val)
                                        break
                            except Exception:
                                continue
                        if ligand_hxl:
                            break
            if ligand_hxl:
                out["ligand_HxL_definition_SRD"] = ligand_hxl
    except Exception:
        pass


# ==============================================================
# main()
# ==============================================================
def main() -> None:
    """Console smoke test: build a few entries and print them (no files written)."""
    import argparse
    
    parser = argparse.ArgumentParser(description="SRD46 Entry Builder Test")
    parser.add_argument("--debug", action="store_true", help="Enable DEBUG level logging")
    parser.add_argument("--log-file", type=str, help="Path to log file")
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    log_file = Path(args.log_file) if args.log_file else None
    setup_logging(level=log_level, log_file=log_file)
    
    logger.info("Starting SRD46 pip2c entry builder test")
    
    tracker = MissingFieldTracker()
    print("[INFO] Starting SRD46 pip2 entry builder test...")
    print(f"[INFO] Input directories:")
    print(f"       PIP1 parsed: {PIP1_PARSED_DIR}")
    print(f"       SRD46 SQL CSV: {SRD46_SQL_CSV_DIR}")
    print(f"       Log file: {log_file}")
    print()

    # Test 1: Ligand 5760 (Aminoacetic acid / Glycine - from liganden_moldata)
    print("[INFO] Building Ligand entry (ID: 5760)...")
    lig_data = build_ligand_data(5760)
    lig_entry = create_ligand_entry(lig_data, tracker)
    print(f"       Ligand: {lig_entry.ligand_name_SRD if lig_entry else 'N/A'}")
    print(f"       Class: {lig_entry.ligand_class_name if lig_entry else 'N/A'}")
    print(f"       SMILES: {lig_entry.ligand_SMILES if lig_entry else 'N/A'}")

    # Test 2: Metal 106 (Na+ from verkn record 93654)
    print("\n[INFO] Building Metal/Cation entry (ID: 106, Na+)...")
    cat_data = build_cation_data(106)
    cat_entry = create_cation_entry(cat_data, tracker)
    print(f"       Metal: {cat_entry.metal_name_SRD if cat_entry else 'N/A'}")
    print(f"       Symbol: {cat_entry.symbol_pure if cat_entry else 'N/A'}")

    # Test 3: verkn_ligand_metal 93654 (Glycine + Na+, beta_def 812)
    print("\n[INFO] Building Complex entry (VLM ID: 93654, Glycine + Na+)...")
    complex_data = build_complex_data(93654)
    complex_entry = create_metal_ligand_complex_entry(complex_data, tracker)
    print(f"       Complex: metal={complex_entry.metal_id}, ligand={complex_entry.ligand_id}")
    print(f"       Beta def: {complex_entry.beta_definition_name}")
    if complex_entry.stability_info.measured_value:
        mv = complex_entry.stability_info.measured_value[0]
        print(f"       Equation: {mv.equation_info.equation_str}")
        print(f"       LHS species: {[s.species for s in (mv.equation_info.LHS_species or [])]}")
        print(f"       RHS species: {[s.species for s in (mv.equation_info.RHS_species or [])]}")

    # Test 4: Ligand 8872 (Oxalic acid - has multiple pKa equilibrium maps at different T/I)
    print("\n[INFO] Building Ligand entry (ID: 8872) - multiple equilibrium maps...")
    lig_data_multi = build_ligand_data(8872)
    lig_entry_multi = create_ligand_entry(lig_data_multi, tracker)
    print(f"       Ligand: {lig_entry_multi.ligand_name_SRD if lig_entry_multi else 'N/A'}")
    print(f"       Class: {lig_entry_multi.ligand_class_name if lig_entry_multi else 'N/A'}")
    print(f"       SMILES: {lig_entry_multi.ligand_SMILES if lig_entry_multi else 'N/A'}")
    if lig_entry_multi and lig_entry_multi.pKa:
        print(f"       Measured pKa entries: {len(lig_entry_multi.pKa.measured_pKa)}")
        for i, pka in enumerate(lig_entry_multi.pKa.measured_pKa):
            print(f"         [{i+1}] {pka.bracket_from_state}->{pka.bracket_to_state}: pKa={pka.pKa}, T={pka.conditions.temperature_c}°C, I={pka.conditions.ionic_strength_mol_l}")

    # Test 5: references for the complex's ligand/metal pair
    if complex_entry and complex_entry.ligand_id and complex_entry.metal_id:
        table_keys = ["verkn_ligand_metal_literature", "verkn_ligand_metal_literature_sic",
                      "literature", "literature_alt", "paper", "author", "footnote", "verk_literature_author"]
        tables = {k: read_csv_dicts(k) for k in table_keys}
        try:
            refs_entry = create_references_entry_by_ligand_metal(
                int(complex_entry.ligand_id), int(complex_entry.metal_id), tables, tracker
            )
            print(f"\n[INFO] References L{complex_entry.ligand_id}/M{complex_entry.metal_id}: "
                  f"{len(refs_entry.literature)} literature, {len(refs_entry.literature_alt)} literature_alt, "
                  f"{len(refs_entry.authors)} authors, {len(refs_entry.footnotes)} footnotes")
        except Exception as ex:
            print(f"       [WARN] Failed to build reference entry: {ex}")
    
    print("\n=== Missing Field Report ===")
    print(get_missing_field_report_text(tracker))


if __name__ == "__main__":
    main()
