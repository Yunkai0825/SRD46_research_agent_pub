"""
processing.py - Row processing pipeline for HxL parsing and charge reconciliation.
"""

from typing import List, Optional
import pandas as pd

from .config import CONSIDER_FORMULA_MISMATCH
from .rdkit_setup import RDKit_OK
from .parsing import parse_figure_definition, compare_formulas
from .charge_utils import sum_formal_charge, charge_from_molblock_text, charge_from_inchi
from .rdkit_utils import build_mol, recompute_strings, smiles_frag_count, mol_frag_count
from .rules import (
    rule1_remove_counterions, rule2_fix_cyanide, rule2b_fix_cyanometalate,
    rule3_fix_polyanions, rule4_looks_desalted_cation, rule4b_harmonize_post_desalting,
    rule5_set_figure_from_molblock_superatom, rule6_fix_figure_for_two_entries,
)

if RDKit_OK:
    from rdkit import Chem
    from rdkit.Chem.rdmolfiles import MolFromMolBlock, MolFromSmiles


def process_row(row: pd.Series) -> pd.Series:
    """
    Process a single row: parse figure_definition, reconcile charges, apply rules.
    
    Args:
        row: DataFrame row with molecular data
        
    Returns:
        Modified row with parsed/fixed data and validation flags
    """
    core, h_count, l_count, fig_chg = parse_figure_definition(row.get("figure_definition", ""))

    notes: List[str] = []
    rules_applied: List[str] = []

    # Initialize output columns
    row["figure_definition_parsed"] = core
    row["figure_definition_charge"] = fig_chg
    row["h_count"] = h_count
    row["l_count"] = l_count
    row["figure_excess_charge"] = fig_chg
    row["correction_applied"] = ""
    row["figure_definition_original"] = row.get("figure_definition", "")
    row["looks_desalted_cation"] = False
    row["rule4_check_ok"] = None

    # InChI charge (/q layer)
    inchi_text = None
    for k in ("InChI", "InChi", "Inchi"):
        if k in row and isinstance(row[k], str):
            inchi_text = row[k]
            break
    inchi_chg = charge_from_inchi(inchi_text)
    row["inchi_charge_value"] = inchi_chg

    # Store ORIGINAL values BEFORE any rule modifications (for diagnostics)
    row["SMILES_before"] = row.get("SMILES", "")
    row["InChI_before"] = row.get("InChI", "")
    row["molblock_before"] = row.get("molblock", "")

    # Build ORIGINAL mol and get charge BEFORE rules
    orig_mb = row.get("molblock")
    orig_smi = row.get("SMILES")
    orig_mol = None
    
    if RDKit_OK:
        if isinstance(orig_mb, str) and orig_mb.strip():
            try:
                orig_mol = MolFromMolBlock(orig_mb, sanitize=False)
                if orig_mol is not None:
                    Chem.SanitizeMol(orig_mol, catchErrors=True)
            except Exception:
                orig_mol = None
        if orig_mol is None and isinstance(orig_smi, str) and orig_smi.strip():
            try:
                orig_mol = MolFromSmiles(orig_smi)
                if orig_mol is not None:
                    Chem.SanitizeMol(orig_mol, catchErrors=True)
            except Exception:
                orig_mol = None

    rdkit_charge_before = sum_formal_charge(orig_mol) if orig_mol is not None else None
    if rdkit_charge_before is None:
        rdkit_charge_before = charge_from_molblock_text(orig_mb)

    if rdkit_charge_before is None and isinstance(orig_mb, str) and orig_mb.strip():
        rdkit_charge_before = 0

    row["rdkit_charge_before"] = rdkit_charge_before
    row["pre_molblock_frag_count"] = mol_frag_count(orig_mol)
    row["pre_smiles_frag_count"] = smiles_frag_count(row.get("SMILES"))

    # Formula vs COMPOSITION comparison
    formula_text = row.get("formula") if "formula" in row else (row.get("Formula") if "Formula" in row else row.get("FORMULA"))
    composition_text = row.get("COMPOSITION")
    f_status, f_same, f_can_a, f_can_b = compare_formulas(formula_text, composition_text)
    row["formula_comp_status"] = f_status
    row["formula_vs_composition_same"] = True if f_same is True else (False if f_same is False else None)
    row["formula_canonical"] = f_can_a
    row["composition_canonical"] = f_can_b

    # Rule4: harmonize figure charge for desalted cations
    if (
        (row.get("figure_definition_charge") in (0, None)) and
        (rdkit_charge_before is not None) and (rdkit_charge_before != 0) and
        rule4_looks_desalted_cation(row)
    ):
        new_q = int(rdkit_charge_before)
        base = core or "L"
        suf = ("/+" if new_q == 1 else "/-" if new_q == -1 else f"/{abs(new_q)}{'+' if new_q > 0 else '-'}")
        row["figure_definition"] = f"{base}{suf}"

        core2, h2, l2, q2 = parse_figure_definition(row["figure_definition"])
        row["figure_definition_parsed"] = core2
        row["h_count"] = h2
        row["l_count"] = l2
        row["figure_definition_charge"] = q2
        row["figure_excess_charge"] = q2
        fig_chg = q2

        row["looks_desalted_cation"] = True
        rules_applied.append("Rule4")
        notes.append(f"Rule4: harmonized figure charge to desalted cation ({row.get('figure_definition_original', '')} -> {row['figure_definition']})")

        row["rule4_check_ok"] = bool(q2 == rdkit_charge_before)
        if not row["rule4_check_ok"]:
            notes.append(f"Rule4: CHECK FAILED (fig={q2} vs pre-molblock={rdkit_charge_before})")

    # Rule5: set figure from molblock superatom label
    msg5, applied5 = rule5_set_figure_from_molblock_superatom(row)
    if applied5:
        notes.append(msg5)
        rules_applied.append("Rule5")
        fig_chg = row.get("figure_definition_charge", fig_chg)

    # Rule6: fix figure_definition for two specific entries
    msg6, applied6 = rule6_fix_figure_for_two_entries(row)
    if applied6:
        notes.append(msg6)
        rules_applied.append("Rule6")
        core, h_count, l_count, fig_chg = parse_figure_definition(row.get("figure_definition", ""))
        row["figure_definition_parsed"] = core
        row["h_count"] = h_count
        row["l_count"] = l_count
        row["figure_definition_charge"] = fig_chg
        row["figure_excess_charge"] = fig_chg

    # Target charge precedence: InChI > figure_definition
    target = inchi_chg if inchi_chg is not None else fig_chg

    # Working copy for structure rules
    mol = None
    if RDKit_OK and orig_mol is not None:
        try:
            mol = Chem.Mol(orig_mol)
        except Exception:
            mol = orig_mol
    if mol is None:
        mol = build_mol(row)

    mol_charge = sum_formal_charge(mol)

    # Always attempt desalting if polymolecular
    ran_rule1 = False
    frag_count = mol_frag_count(mol)
    if RDKit_OK and mol is not None and frag_count and frag_count > 1:
        mol_r1, msg, changed = rule1_remove_counterions(mol, target)
        if msg:
            notes.append(msg)
        if changed:
            rules_applied.append("Rule1")
            ran_rule1 = True
            mol = mol_r1
            s = recompute_strings(mol)
            if s.get("molblock"):
                row["molblock"] = s["molblock"]
            if s.get("SMILES"):
                row["SMILES"] = s["SMILES"]
            if s.get("InChI"):
                row["InChI"] = s["InChI"]
            mol_charge = sum_formal_charge(mol)
            if mol_charge is None:
                mol_charge = charge_from_molblock_text(row.get("molblock", ""))
            new_target, msg4, applied4 = rule4b_harmonize_post_desalting(row, mol_charge, target)
            if applied4:
                target = new_target
                notes.append(msg4)
                rules_applied.append("Rule4b")

    # Apply charge-fixing rules only if mismatch vs target
    mismatch = (mol_charge is not None and target is not None and mol_charge != target)
    if RDKit_OK and mol is not None and mismatch:
        if not ran_rule1:
            mol, msg, changed = rule1_remove_counterions(mol, target)
            if msg:
                notes.append(msg)
            if changed:
                rules_applied.append("Rule1")

        mol2, msg = rule2_fix_cyanide(mol, [row.get("SMILES", ""), inchi_text])
        if msg:
            notes.append(msg)
            rules_applied.append("Rule2")
            mol = mol2

        mol2b, msg = rule2b_fix_cyanometalate(mol, target)
        if msg:
            notes.append(msg)
            rules_applied.append("Rule2b")
            mol = mol2b

        mol3, msg = rule3_fix_polyanions(mol, target)
        if msg:
            notes.append(msg)
            rules_applied.append("Rule3")
            mol = mol3

        s = recompute_strings(mol)
        if s.get("molblock"):
            row["molblock"] = s["molblock"]
        if s.get("SMILES"):
            row["SMILES"] = s["SMILES"]
        if s.get("InChI"):
            row["InChI"] = s["InChI"]
        mol_charge = sum_formal_charge(mol)

        if mol_charge is None:
            mol_charge = charge_from_molblock_text(row.get("molblock", ""))

    # Post-processing fragment counts
    row["post_molblock_frag_count"] = mol_frag_count(mol)
    row["post_smiles_frag_count"] = smiles_frag_count(row.get("SMILES"))
    row["correction_applied"] = "; ".join(n for n in notes if n)
    row["rules_applied"] = ";".join(rules_applied) if rules_applied else ""

    # Validation
    row["target_charge"] = target
    row["rdkit_charge_after"] = mol_charge if mol_charge is not None else charge_from_molblock_text(row.get("molblock", ""))
    row["validation_ok"] = (row["rdkit_charge_after"] == target) if (target is not None) else False
    
    if not row["validation_ok"]:
        if target is None and fig_chg is not None:
            row["validation_ok"] = (row["rdkit_charge_after"] == fig_chg)
        if not row["validation_ok"]:
            notes.append("Validation: target charge unknown" if target is None else f"Validation: charge {row['rdkit_charge_after']} != target {target}")

    # Baseline figure vs ORIGINAL molblock
    fig_vs_mol_mismatch = (fig_chg is not None) and (rdkit_charge_before is not None) and (fig_chg != rdkit_charge_before)
    row["figure_vs_molblock_charge_mismatch"] = bool(fig_vs_mol_mismatch)
    row["figure_vs_molblock_charge_same"] = (not fig_vs_mol_mismatch) if (fig_chg is not None and rdkit_charge_before is not None) else None
    row["debug_reason"] = (
        f"Figure vs ORIGINAL molblock charge mismatch: figure={fig_chg}, molblock={rdkit_charge_before}"
        if fig_vs_mol_mismatch else ""
    )

    # Pipeline flags
    row["pipeline_success"] = bool(row["validation_ok"])
    row["needs_manual_review"] = bool(
        (not row["pipeline_success"]) or
        (row["rules_applied"]) or
        bool(fig_vs_mol_mismatch) or
        (CONSIDER_FORMULA_MISMATCH and (row["formula_comp_status"] in ("different", "unparsed")))
    )

    row["correction_applied"] = "; ".join(n for n in notes if n)
    return row
