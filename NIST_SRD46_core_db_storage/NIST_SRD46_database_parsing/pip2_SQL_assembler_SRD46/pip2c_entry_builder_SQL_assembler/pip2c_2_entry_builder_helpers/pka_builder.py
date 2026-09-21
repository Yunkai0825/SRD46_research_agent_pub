"""pKa block extraction helpers for ligand entries.

Functions to extract measured and estimated pKa data from moldata rows.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional

from .csv_io_helpers import pick_any, find_first_row, get_col, read_csv_dicts
from .config import FILENAMES, DEBUG_FLAG

# =============================================================================
# Logging
# =============================================================================

logger = logging.getLogger(__name__)


def _to_float(x: Any) -> Optional[float]:
    try:
        return None if x in (None, "") else float(x)
    except Exception:
        return None


def _to_int(x: Any) -> Optional[int]:
    try:
        return None if x in (None, "") else int(x)
    except Exception:
        return None


def _extract_measured_from_item(e: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Extract a measured pKa entry from a step_constants item."""
    # Tolerant extraction
    pka_val = e.get("constant") or e.get("pKa") or e.get("value") or e.get("constant_sic")
    edge_label = e.get("edge_label") or e.get("label")
    from_lbl = (e.get("from") or e.get("from_state") or e.get("edge_from") 
                or e.get("edge_label_from") or e.get("bracket_from_state"))
    to_lbl = (e.get("to") or e.get("to_state") or e.get("edge_to") 
              or e.get("edge_label_to") or e.get("bracket_to_state"))
    
    # Parse from edge_label like "L->HL" if explicit labels missing
    if (not from_lbl or not to_lbl) and isinstance(edge_label, str) and "->" in edge_label:
        parts = edge_label.split("->", 1)
        if len(parts) == 2:
            from_lbl = from_lbl or parts[0].strip()
            to_lbl = to_lbl or parts[1].strip()
    
    temp = e.get("temperature") or e.get("temperature_c")
    ionic = e.get("ionicstrength") or e.get("ionic_strength_mol_l")
    solvent_name = e.get("solvent") or None
    electrolyte = e.get("electrolyte") or None
    vlm_id = e.get("vlm_id") or e.get("verkn_ligand_metal_id")

    # Require the key fields to create an entry
    if from_lbl is None or to_lbl is None:
        return None
    
    try:
        pka_f = float(pka_val) if pka_val is not None and str(pka_val).strip() != "" else None
    except Exception:
        pka_f = None
    
    measured_entry = {
        "source": "SRD",
        "bracket_from_state": str(from_lbl),
        "bracket_to_state": str(to_lbl),
        "pKa": pka_f,
        "conditions": {
            "temperature_c": _to_float(temp),
            "ionic_strength_mol_l": _to_float(ionic),
            "solvent": solvent_name,
            "electrolyte": electrolyte,
        },
        "evidence": {
            "verkn_ligand_metal_ids": [v for v in [_to_int(vlm_id)] if v is not None],
            "references": {},
        },
    }
    
    # Resolve structured solvent info using verkn_ligand_metal and solvent CSVs
    try:
        if vlm_id is not None:
            verkn_path = FILENAMES["verkn_ligand_metal"]
            vr = find_first_row(verkn_path, ["verkn_ligand_metalID", "verkn_ligand_metalNr", 
                                             "vlm_id", "vlm", "verknID"], vlm_id) or {}
            if vr:
                solv_nr = None
                for sk in ("solventNr", "solventID", "solvent_id"):
                    if sk in vr and str(vr.get(sk)).strip() != "":
                        solv_nr = vr.get(sk)
                        break
                electroly_local = None
                for ek in ("electrolyte", "electrolyte_and_composition"):
                    if ek in vr and vr.get(ek) not in (None, ""):
                        electroly_local = vr.get(ek)
                        break
                solvent_name_local = None
                if solv_nr is not None:
                    solv_path = FILENAMES["solvent"]
                    sr = find_first_row(solv_path, ["solventID", "solventNr", "solvent_id"], solv_nr) or {}
                    if sr:
                        solvent_name_local = sr.get("name_solvent") or sr.get("name")
                if solv_nr is not None or solvent_name_local is not None or electroly_local is not None:
                    measured_entry["conditions"]["solvent"] = {
                        "solvent_id": (None if solv_nr in (None, "") else 
                                      (int(solv_nr) if str(solv_nr).isdigit() else solv_nr)),
                        "name": (solvent_name_local if solvent_name_local is not None 
                                else measured_entry["conditions"].get("solvent")),
                        "electrolyte_and_composition": electroly_local if electroly_local is not None else None,
                    }
    except Exception:
        pass
    
    return measured_entry


def extract_measured_pka(mol_row: dict[str, Any], ligand_id: int) -> list[dict[str, Any]]:
    """Extract measured pKa entries from step_constants_pref_json in moldata row."""
    measured_list: list[dict[str, Any]] = []
    
    scpj = (get_col(mol_row, "step_constants_pref_json") or 
            get_col(mol_row, "step_constants_json") or 
            get_col(mol_row, "measured_step_constants_json"))
    
    if not isinstance(scpj, str) or not scpj.strip():
        return measured_list
    
    try:
        sc_data = json.loads(scpj)
        
        if isinstance(sc_data, dict):
            # Try list-like keys
            edges = sc_data.get("edges") or sc_data.get("steps") or sc_data.get("data")
            if isinstance(edges, list):
                for e in edges:
                    if isinstance(e, dict):
                        item = _extract_measured_from_item(e)
                        if item:
                            measured_list.append(item)
            else:
                # Dict keyed by transitions like '0->1'
                for key, val in sc_data.items():
                    if isinstance(val, dict):
                        item = _extract_measured_from_item(val)
                        if item:
                            measured_list.append(item)
        elif isinstance(sc_data, list):
            for e in sc_data:
                if isinstance(e, dict):
                    item = _extract_measured_from_item(e)
                    if item:
                        measured_list.append(item)
        
        if measured_list and DEBUG_FLAG:
            sample = measured_list[:3]
            print(f"[DEBUG] Built measured pKa entries: +{len(measured_list)}; sample: {sample}")
            
    except Exception as ex:
        print(f"[WARN] Failed parsing step_constants_pref_json for ligand {ligand_id}: {ex}")
    
    return measured_list


_PKA_CHAIN_INDEX: Optional[dict[str, dict[str, Any]]] = None


def _pka_chain_rows_by_ligand() -> dict[str, dict[str, Any]]:
    """Index preferred_ligand_pka_chains rows by normalized ligandenID (first row wins).

    Reads the table once via read_csv_dicts (registered in-memory table or CSV).
    """
    global _PKA_CHAIN_INDEX
    if _PKA_CHAIN_INDEX is None:
        idx: dict[str, dict[str, Any]] = {}
        for row in read_csv_dicts("preferred_ligand_pka_chains"):
            lid = row.get("ligandenID")
            if lid is None:
                continue
            try:
                key = str(int(str(lid).strip()))
            except (ValueError, TypeError):
                continue
            idx.setdefault(key, row)
        _PKA_CHAIN_INDEX = idx
    return _PKA_CHAIN_INDEX


def reset_pka_chain_index() -> None:
    """Forget the cached pKa-chain index (call after re-registering the table)."""
    global _PKA_CHAIN_INDEX
    _PKA_CHAIN_INDEX = None


def extract_measured_pka_from_pka_chains(ligand_id: int) -> list[dict[str, Any]]:
    """Extract measured pKa from the preferred_ligand_pka_chains table (equilibrium tree data).
    
    This table contains pre-computed pKa chains filtered to prefer entries 
    close to target temperature (25°C) and ionic strength (0.1M).
    Only returns the preferred entries from the equilibrium tree, not all VLM entries.
    """
    measured_list: list[dict[str, Any]] = []
    
    try:
        rows_by_ligand = _pka_chain_rows_by_ligand()
        if not rows_by_ligand:
            if DEBUG_FLAG:
                print(f"[DEBUG] preferred_ligand_pka_chains not available, skipping pKa chain extraction")
            return measured_list

        row = rows_by_ligand.get(str(int(ligand_id)))
        if row is not None:
            # Found the ligand - parse step_constants_pref_json
            scpj = row.get("step_constants_pref_json", "")
            sc_data = None
            if scpj and scpj.strip():
                try:
                    sc_data = json.loads(scpj)
                except json.JSONDecodeError:
                    sc_data = None

            # sc_data is dict keyed by "0->1", "1->2", etc.
            for key, val in (sc_data or {}).items():
                if not isinstance(val, dict):
                    continue
                
                # Extract pKa entry from equilibrium tree data
                vlm_id = val.get("vlm_id")
                pka_val = val.get("constant") or val.get("constant_sic")
                edge_label = val.get("edge_label", "")
                temp = val.get("temperature")
                ionic = val.get("ionicstrength")
                
                # Parse edge_label like "L->HL" to get from/to states
                from_state = None
                to_state = None
                if isinstance(edge_label, str) and "->" in edge_label:
                    parts = edge_label.split("->", 1)
                    if len(parts) == 2:
                        from_state = parts[0].strip()
                        to_state = parts[1].strip()
                
                # Parse pKa value
                try:
                    pka_f = float(pka_val) if pka_val is not None and str(pka_val).strip() != "" else None
                except Exception:
                    pka_f = None
                
                entry = {
                    "source": "SRD",
                    "bracket_from_state": from_state,
                    "bracket_to_state": to_state,
                    "pKa": pka_f,
                    "pKa_type": None,
                    "notes": None,
                    "conditions": {
                        "temperature_c": _to_float(temp),
                        "ionic_strength_mol_l": _to_float(ionic),
                        "solvent": None,
                        "electrolyte": None,
                    },
                    "evidence": {
                        "verkn_ligand_metal_ids": [_to_int(vlm_id)] if vlm_id else [],
                        "references": {},
                    },
                }
                measured_list.append(entry)
        
        if measured_list and DEBUG_FLAG:
            print(f"[DEBUG] Extracted {len(measured_list)} pKa from equilibrium tree for ligand {ligand_id}")
            
    except Exception as ex:
        if DEBUG_FLAG:
            print(f"[WARN] Failed extracting pKa from preferred_ligand_pka_chains: {ex}")
    
    return measured_list


def _has_any_q(row: dict[str, Any], q: int) -> bool:
    """Check if row has any Q-state columns for charge q."""
    keys = [
        f"formula_Q{q}", f"formula_q{q}", f"formula_Q_{q}", f"formula_q_{q}",
        f"smiles_Q{q}", f"smiles_q{q}", f"smiles_Q_{q}", f"smiles_q_{q}",
        f"inchi_Q{q}", f"inchi_q{q}", f"inchi_Q_{q}", f"inchi_q_{q}",
        f"bracket_Q{q}", f"bracket_q{q}", f"bracket_Q_{q}", f"bracket_q_{q}",
    ]
    for kk in keys:
        if kk in row and str(row.get(kk) or "").strip() != "":
            return True
    return False


def _get_q(row: dict[str, Any], base: str, q: int) -> Optional[str]:
    """Get Q-state column value for base field and charge q."""
    return pick_any(row, [f"{base}_Q{q}", f"{base}_q{q}", f"{base}_Q_{q}", f"{base}_q_{q}"])


def _parse_formula_counts(s: str) -> dict[str, int]:
    """Sum element counts across dot-separated fragments."""
    counts: dict[str, int] = {}
    if not s:
        return counts
    parts = re.split(r"[^A-Za-z0-9]+", s)
    token_pat = re.compile(r"([A-Z][a-z]?)(\d*)")
    for part in parts:
        if not part:
            continue
        for el, num in token_pat.findall(part):
            n = int(num) if num else 1
            counts[el] = counts.get(el, 0) + n
    return counts


def _parse_canonical_hxl(hxl: str) -> tuple[int, int]:
    """Returns (H_count, L_count) from HxL form like H3L, H4L2."""
    if not hxl:
        return (0, 1)
    m = re.match(r"^H(\d+)\s*L(\d+)?$", hxl.strip())
    if m:
        h = int(m.group(1))
        l = int(m.group(2)) if m.group(2) else 1
        return (h, l)
    m = re.match(r"^HL(\d+)?$", hxl.strip())
    if m:
        l = int(m.group(1)) if m.group(1) else 1
        return (1, l)
    return (0, 1)


def _infer_hxl_form(canon_hxl: Optional[str], canon_comp: Optional[str], 
                    q: int, comp_q: Optional[str],
                    h_base_num: Optional[int] = None, 
                    l_base_num: Optional[int] = None) -> Optional[str]:
    """Infer HxL form for a given charge state."""
    if not canon_hxl:
        return None
    if not canon_comp or not comp_q:
        return canon_hxl
    
    c0 = _parse_formula_counts(str(canon_comp))
    cq = _parse_formula_counts(str(comp_q))
    h0 = c0.get("H", 0)
    hq = cq.get("H", 0)
    dH = hq - h0
    
    if h_base_num is not None and l_base_num is not None:
        H_base, L_count = h_base_num, l_base_num
    else:
        H_base, L_count = _parse_canonical_hxl(str(canon_hxl))
    
    H_new = max(0, H_base + dH)
    return f"H{H_new}L{'' if L_count == 1 else L_count}"


QUPKAKE_BRACKET_NOTES = (
    "Heuristic protonation windows from sorted Qupkake microscopic site pKa predictions. "
    "The parser changes protonation without re-predicting site constants; boundaries are not "
    "successive macroscopic pKas or validated speciation intervals. "
    "Source model: https://doi.org/10.1021/acs.jctc.4c00328."
)


def extract_estimated_pka(mol_row: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract estimated pKa entries from Q-state columns in moldata row."""
    estimated_list: list[dict[str, Any]] = []
    
    # Collect all charges that appear using regex
    charges: set[int] = set()
    q_pat = re.compile(r"_Q_?(-?\d+)(?:$|_|\b)")
    for k in list(mol_row.keys()):
        if not isinstance(k, str):
            continue
        m = q_pat.search(k)
        if m:
            try:
                qi = int(m.group(1))
                charges.add(qi)
            except Exception:
                pass
    
    # Fallback sweep: check -12..12
    for qi in range(-12, 13):
        if _has_any_q(mol_row, qi):
            charges.add(qi)
    
    # Canonical values for HxL inference
    canonical_hxl = get_col(mol_row, "figure_definition_parsed")
    canonical_comp = get_col(mol_row, "COMPOSITION")
    canonical_h_count = pick_any(mol_row, ["h_count", "H_COUNT", "H_count"])
    canonical_l_count = pick_any(mol_row, ["l_count", "L_COUNT", "L_count"])
    
    try:
        h_base_num = int(canonical_h_count) if canonical_h_count not in (None, "") else None
        l_base_num = int(canonical_l_count) if canonical_l_count not in (None, "") else None
    except Exception:
        h_base_num = None
        l_base_num = None
    
    if charges and DEBUG_FLAG:
        print(f"[DEBUG] Detected Q-states: {sorted(charges)}")
    
    for q in sorted(charges):
        formula_q = _get_q(mol_row, "formula", q)
        bracket_q = _get_q(mol_row, "bracket", q)
        smiles_q = _get_q(mol_row, "smiles", q)
        inchi_q = _get_q(mol_row, "inchi", q)
        comp_q = _get_q(mol_row, "composition", q) or _get_q(mol_row, "COMPOSITION", q) or formula_q
        
        if not any([formula_q, bracket_q, smiles_q, inchi_q]):
            continue
        
        state = {
            "state_id": f"Q{q}",
            "charge": q,
            "formula": None if not formula_q else str(formula_q),
            "HxL_form": _infer_hxl_form(canonical_hxl, canonical_comp, q, comp_q, h_base_num, l_base_num),
            "bracket_label": None if not bracket_q else str(bracket_q),
            "SMILES": None if not smiles_q else str(smiles_q),
            "InChi": None if not inchi_q else str(inchi_q),
            "notes": QUPKAKE_BRACKET_NOTES,
        }
        
        est_entry = {
            "source": "Qupkake",
            "model_name": "Qupkake",
            "notes": QUPKAKE_BRACKET_NOTES,
            "model_version": None,
            "bracket_from_state": f"Q{q}",
            "bracket_to_state": f"Q{q}",
            "pKa": None,
            "hxl_states": [state],
            "conditions": {},
            "evidence": {"verkn_ligand_metal_ids": [], "references": {}},
        }
        estimated_list.append(est_entry)
    
    # Debug summary
    if estimated_list and DEBUG_FLAG:
        try:
            summary = []
            for item in estimated_list[:10]:
                st = item.get("hxl_states", [{}])[0]
                summary.append({
                    "state": st.get("state_id"),
                    "has_formula": bool(st.get("formula")),
                    "has_bracket": bool(st.get("bracket_label")),
                    "has_smiles": bool(st.get("SMILES")),
                    "has_inchi": bool(st.get("InChi")),
                    "HxL_form": st.get("HxL_form"),
                })
            print(f"[DEBUG] Built estimated states: {len(estimated_list)}; sample: {summary}")
        except Exception:
            pass
    
    return estimated_list


def build_pka_block(mol_row: dict[str, Any], ligand_id: int) -> dict[str, Any]:
    """Build complete pKa block with measured and estimated entries.
    
    Uses preferred_ligand_pka_chains.csv which contains pre-computed equilibrium tree data
    filtered to prefer entries close to target T=25°C, I=0.1M.
    """
    logger.debug(f"build_pka_block: Building pKa for ligand {ligand_id}")
    
    # Primary source: equilibrium tree data from preferred_ligand_pka_chains.csv
    measured = extract_measured_pka_from_pka_chains(ligand_id)
    
    # Fallback: try moldata JSON (if step_constants_pref_json exists there)
    if not measured:
        logger.debug(f"build_pka_block: No pKa chains found, trying moldata JSON")
        measured = extract_measured_pka(mol_row, ligand_id)
    
    estimated = extract_estimated_pka(mol_row)
    
    pka_block: dict[str, Any] = {
        "measured_pKa": measured,
        "estimated_pKa": estimated,
    }
    
    logger.debug(f"build_pka_block: ligand {ligand_id} -> measured={len(measured)}, estimated={len(estimated)}")
    
    if DEBUG_FLAG:
        print(f"[DEBUG] pKa counts -> measured: {len(pka_block['measured_pKa'])}, "
              f"estimated: {len(pka_block['estimated_pKa'])}")
    
    return pka_block


def extract_measured_pka_from_vlm(ligand_id: int) -> list[dict[str, Any]]:
    """Extract measured pKa from verkn_ligand_metal table.
    
    In SRD46, pKa values are stored as equilibrium constants where metalNr=68 (H+).
    Uses the pre-parsed equation_tree_json from beta_definition_augmented.csv for state labels.
    """
    measured_list: list[dict[str, Any]] = []
    
    PROTON_METAL_ID = 68  # H+ in SRD46
    
    try:
        vlm_path = FILENAMES.get("verkn_ligand_metal")
        if not vlm_path or not os.path.exists(vlm_path):
            return measured_list
        
        # Use the augmented beta definition file (with pre-parsed equation_tree_json)
        beta_path = FILENAMES.get("beta_definition_fixed")  # Use augmented version
        if not beta_path or not os.path.exists(beta_path):
            # Fallback to basic beta definition
            beta_path = FILENAMES.get("beta_definition")
        
        beta_map: dict[str, dict[str, Any]] = {}
        if beta_path and os.path.exists(beta_path):
            import csv
            with open(beta_path, "r", encoding="utf-8-sig", errors="replace") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    bid = r.get("beta_definitionID") or r.get("beta_definitionNr")
                    if bid:
                        # Normalize ID (remove .0 suffix if float)
                        try:
                            bid_int = int(float(bid))
                            beta_map[str(bid_int)] = r
                        except (ValueError, TypeError):
                            beta_map[str(bid)] = r
        
        import csv
        with open(vlm_path, "r", encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                lig = row.get("ligandenNr") or row.get("ligandenID")
                met = row.get("metalNr") or row.get("metalID")
                
                if lig is None or met is None:
                    continue
                
                try:
                    if int(str(lig)) != int(ligand_id) or int(str(met)) != PROTON_METAL_ID:
                        continue
                except (ValueError, TypeError):
                    continue
                
                # This is a pKa entry
                vlm_id = row.get("verkn_ligand_metalID") or row.get("verkn_ligand_metalNr")
                beta_id = row.get("beta_definitionNr") or row.get("beta_definitionID")
                const = row.get("constant") or row.get("constant_sic")
                temp = row.get("temperature")
                ionic = row.get("ionicstrength")
                
                # Parse pKa value
                try:
                    pka_val = float(const) if const and str(const).strip() not in ("", "\\N") else None
                except Exception:
                    pka_val = None
                
                # Get from/to states from pre-parsed equation_tree_json
                from_state = None
                to_state = None
                beta_name = None
                
                if beta_id:
                    try:
                        beta_id_norm = str(int(float(beta_id)))
                    except (ValueError, TypeError):
                        beta_id_norm = str(beta_id)
                    
                    br = beta_map.get(beta_id_norm, {})
                    beta_name = br.get("name_beta_definition")
                    
                    # Use pre-parsed equation_tree_json
                    tree_str = br.get("equation_tree_json", "")
                    if tree_str and tree_str not in ("", "*"):
                        try:
                            tree = json.loads(tree_str)
                            num_species = [s.get("species_clean", "") for s in tree.get("numerator", [])]
                            denom_species = [s.get("species_clean", "") for s in tree.get("denominator", [])]
                            
                            # For pKa: from_state is the ligand species in denominator (excluding H)
                            # to_state is the ligand species in numerator (excluding H, H2O)
                            from_states = [s for s in denom_species if s not in ("H", "H2O")]
                            to_states = [s for s in num_species if s not in ("H", "H2O")]
                            
                            if from_states:
                                from_state = from_states[0]  # First ligand species
                            if to_states:
                                to_state = to_states[0]  # Product ligand species
                        except (json.JSONDecodeError, TypeError):
                            pass
                
                entry = {
                    "source": "SRD",
                    "bracket_from_state": from_state,
                    "bracket_to_state": to_state,
                    "pKa": pka_val,
                    "pKa_type": None,
                    "notes": beta_name,
                    "conditions": {
                        "temperature_c": _to_float(temp),
                        "ionic_strength_mol_l": _to_float(ionic),
                        "solvent": None,
                        "electrolyte": row.get("electrolyte") if row.get("electrolyte") != "\\N" else None,
                    },
                    "evidence": {
                        "verkn_ligand_metal_ids": [_to_int(vlm_id)] if vlm_id else [],
                        "references": {},
                    },
                }
                measured_list.append(entry)
        
        if measured_list and DEBUG_FLAG:
            print(f"[DEBUG] Extracted {len(measured_list)} measured pKa from VLM for ligand {ligand_id}")
            
    except Exception as ex:
        if DEBUG_FLAG:
            print(f"[WARN] Failed extracting measured pKa from VLM: {ex}")
    
    return measured_list
