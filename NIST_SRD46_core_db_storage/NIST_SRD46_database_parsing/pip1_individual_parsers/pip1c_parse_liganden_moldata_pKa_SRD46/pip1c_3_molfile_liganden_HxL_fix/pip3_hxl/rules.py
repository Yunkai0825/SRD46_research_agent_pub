"""
rules.py - Charge reconciliation rules for HxL pipeline.

Rule implementations (structure edits first, then metadata-only):
- Rule1: Remove known counter-ions (desalting)
- Rule2: Fix cyanide charge
- Rule2b: Fix cyanometalate anions
- Rule3: Fix polyanions (XO4, XF6, XF4)
- Rule4: Check for desalted cation pattern
- Rule4b: Harmonize post-desalting
- Rule5: Set figure from molblock superatom label
- Rule6: Fix known specific entries
"""

import re
from typing import Optional, Tuple, List
import pandas as pd

from .rdkit_setup import RDKit_OK, COUNTERION_MOLS, _mr
from .parsing import parse_figure_definition
from .charge_utils import sum_formal_charge, charge_from_molblock_text, has_cyanide_hint

# Hand-made decisions of rules 4/5/6 are declared in srd46_pipeline/manual_rules.py
# (HXL-02 name tokens, HXL-03 superatom figures, HXL-04 pinned entries) and only consumed here.

if RDKit_OK:
    from rdkit import Chem


def _frag_info(f) -> Tuple[int, int]:
    """Return (heavy_atom_count, net_formal_charge) for a fragment."""
    heavy = sum(1 for a in f.GetAtoms() if a.GetAtomicNum() > 1)
    chg = sum(a.GetFormalCharge() for a in f.GetAtoms())
    return heavy, int(chg)


# =====================================================================
# Rule 1: Remove Counter-ions
# =====================================================================

def rule1_remove_counterions(mol, target_charge: Optional[int]) -> Tuple[any, str, bool]:
    """
    Drop known counter-ions by template; if multi-fragment still remains, keep the best one.
    
    Args:
        mol: RDKit Mol object
        target_charge: Expected charge of the main fragment
        
    Returns:
        Tuple of (modified_mol, message, changed_bool)
    """
    if not RDKit_OK or mol is None:
        return mol, "", False
    
    try:
        frags = Chem.GetMolFrags(mol, asMols=True, sanitizeFrags=False)
        if len(frags) <= 1:
            return mol, "", False

        keep, removed_templates = [], []
        matched_any = False

        s_frags = []
        for f in frags:
            try:
                Chem.SanitizeMol(f, catchErrors=True)
            except Exception:
                pass
            s_frags.append(f)

        for f in s_frags:
            is_counter = False
            for smi, patt in COUNTERION_MOLS:
                try:
                    if f.GetNumAtoms() == patt.GetNumAtoms() and f.HasSubstructMatch(patt) and patt.HasSubstructMatch(f):
                        removed_templates.append(smi)
                        matched_any = True
                        is_counter = True
                        break
                except Exception:
                    continue
            if not is_counter:
                keep.append(f)

        changed = False
        if len(keep) != 1:
            chosen = None
            if target_charge is not None and target_charge != 0:
                for f in keep if keep else s_frags:
                    if _frag_info(f)[1] == target_charge:
                        chosen = f
                        break
            if chosen is None:
                pool = keep if keep else s_frags
                chosen = max(pool, key=lambda x: _frag_info(x)[0])

            out = chosen
            Chem.SanitizeMol(out, catchErrors=True)
            msg_bits = []
            if removed_templates:
                msg_bits.append("removed known counter-ion(s): " + ", ".join(removed_templates))
            if len(s_frags) > 1:
                ha = _frag_info(chosen)[0]
                if target_charge is not None and target_charge != 0:
                    msg_bits.append(f"kept fragment matching target charge ({target_charge}); heavy_atoms={ha}")
                else:
                    msg_bits.append(f"kept largest fragment; heavy_atoms={ha}")
            return out, "Rule1: " + "; ".join(msg_bits), True

        if removed_templates:
            out = keep[0]
            Chem.SanitizeMol(out, catchErrors=True)
            return out, "Rule1: removed known counter-ion(s): " + ", ".join(removed_templates), True

        return mol, "", False

    except Exception:
        return mol, "", False


# =====================================================================
# Rule 2: Fix Cyanide
# =====================================================================

def rule2_fix_cyanide(mol, hint_texts: List[Optional[str]]) -> Tuple[any, str]:
    """
    Set [C-] on cyanide fragments when hinted by SMILES/InChI.
    
    Args:
        mol: RDKit Mol object
        hint_texts: List of strings to check for cyanide hints
        
    Returns:
        Tuple of (modified_mol, message)
    """
    if not RDKit_OK or mol is None or not any(has_cyanide_hint(t) for t in hint_texts):
        return mol, ""
    
    try:
        frags = Chem.GetMolFrags(mol, asMols=True, sanitizeFrags=False) or [mol]
        changed, new_frags = False, []
        
        for f in frags:
            Chem.SanitizeMol(f, catchErrors=True)
            if f.GetNumAtoms() == 2:
                atoms = [a.GetAtomicNum() for a in f.GetAtoms()]
                bonds = list(f.GetBonds())
                if set(atoms) == {6, 7} and len(bonds) == 1 and bonds[0].GetBondType() == Chem.BondType.TRIPLE:
                    rw = Chem.RWMol(f)
                    for a in rw.GetAtoms():
                        if a.GetAtomicNum() == 6 and a.GetFormalCharge() == 0:
                            a.SetFormalCharge(-1)
                            changed = True
                    new_frags.append(rw.GetMol())
                else:
                    new_frags.append(f)
            else:
                new_frags.append(f)
        
        if not changed:
            return mol, ""
        
        merged = new_frags[0]
        for i in range(1, len(new_frags)):
            merged = Chem.CombineMols(merged, new_frags[i])
        Chem.SanitizeMol(merged, catchErrors=True)
        return merged, "Rule2: set [C-] in cyanide fragment"
    except Exception:
        return mol, ""


# =====================================================================
# Rule 2b: Fix Cyanometalate
# =====================================================================

def rule2b_fix_cyanometalate(mol, target_charge: Optional[int]) -> Tuple[any, str]:
    """
    Fix cyanometalate anions by setting -1 on terminal N atoms.
    
    Args:
        mol: RDKit Mol object
        target_charge: Expected total charge
        
    Returns:
        Tuple of (modified_mol, message)
    """
    if not RDKit_OK or mol is None or target_charge is None or target_charge >= 0:
        return mol, ""
    
    try:
        if any(a.GetFormalCharge() != 0 for a in mol.GetAtoms()):
            return mol, ""

        metals = {Z for Z in range(21, 113)}
        rw = Chem.RWMol(mol)
        cn_units = []

        for b in rw.GetBonds():
            if b.GetBondType() != Chem.BondType.TRIPLE:
                continue
            a1, a2 = b.GetBeginAtom(), b.GetEndAtom()
            Z1, Z2 = a1.GetAtomicNum(), a2.GetAtomicNum()
            if {Z1, Z2} != {6, 7}:
                continue
            n = a1 if Z1 == 7 else a2
            c = a2 if Z1 == 7 else a1
            if any(nb.GetAtomicNum() in metals for nb in c.GetNeighbors() if nb.GetIdx() != n.GetIdx()):
                cn_units.append((n.GetIdx(), c.GetIdx()))

        if not cn_units:
            return mol, ""

        need = -int(target_charge)
        applied = 0
        for n_idx, _ in cn_units:
            if applied >= need:
                break
            at = rw.GetAtomWithIdx(n_idx)
            if at.GetFormalCharge() == 0:
                at.SetFormalCharge(-1)
                applied += 1

        if applied == 0:
            return mol, ""

        out = rw.GetMol()
        Chem.SanitizeMol(out, catchErrors=True)
        return out, f"Rule2b: set −1 on {applied} cyanide N atom(s) in metal–C≡N motifs"
    except Exception:
        return mol, ""


# =====================================================================
# Rule 3: Fix Polyanions
# =====================================================================

def rule3_fix_polyanions(mol, target_charge: Optional[int]) -> Tuple[any, str]:
    """
    Fix common polyanions (XO4, XF6, XF4).
    
    Args:
        mol: RDKit Mol object
        target_charge: Expected total charge
        
    Returns:
        Tuple of (modified_mol, message)
    """
    if not RDKit_OK or mol is None or target_charge is None or target_charge >= 0:
        return mol, ""
    
    try:
        if any(a.GetFormalCharge() != 0 for a in mol.GetAtoms()):
            return mol, ""
        
        rw = Chem.RWMol(mol)
        changed = False
        
        # XO4 patterns (sulfate, selenate, chromate, molybdate, tungstate)
        if target_charge <= -2:
            for a in rw.GetAtoms():
                if a.GetAtomicNum() in (16, 34, 24, 42, 74):
                    o_neigh = [n for n in a.GetNeighbors() if n.GetAtomicNum() == 8]
                    if len(o_neigh) >= 4:
                        for on in o_neigh[:2]:
                            if on.GetFormalCharge() == 0:
                                on.SetFormalCharge(-1)
                                changed = True
        
        # XF6/XF4 patterns (hexafluoro/tetrafluoro anions)
        if not changed and target_charge <= -1:
            for a in rw.GetAtoms():
                Z = a.GetAtomicNum()
                f_neigh = [n for n in a.GetNeighbors() if n.GetAtomicNum() == 9]
                if (Z in (15, 33, 51) and len(f_neigh) >= 6) or (Z == 5 and len(f_neigh) >= 4):
                    f0 = f_neigh[0]
                    if f0.GetFormalCharge() == 0:
                        f0.SetFormalCharge(-1)
                        changed = True
                        break
        
        if not changed:
            return mol, ""
        
        out = rw.GetMol()
        Chem.SanitizeMol(out, catchErrors=True)
        return out, "Rule3: set formal charges for poly-anion fragment (XO4 / XF6 / XF4)"
    except Exception:
        return mol, ""


# =====================================================================
# Rule 4: Check Desalted Cation Pattern
# =====================================================================

def rule4_looks_desalted_cation(row) -> bool:
    """
    Check if row looks like a desalted cation based on name/formula hints.
    
    Args:
        row: DataFrame row or dict-like object
        
    Returns:
        True if pattern matches desalted cation
    """
    names = " ".join(str(row.get(c, "")) for c in ("COMMON_NAME", "IUPAC_NAME", "ligand_name", "name_ligand", "name"))
    
    name_hit = any(k in names.lower() for k in _mr.HXL02_DESALTED_CATION_NAME_TOKENS)
    
    ftxt = row.get("formula") or row.get("Formula") or row.get("FORMULA") or ""
    formula_hit = isinstance(ftxt, str) and bool(re.search(r"[+-]\d*$", ftxt.strip()))
    
    return name_hit or formula_hit


# =====================================================================
# Rule 4b: Harmonize Post-Desalting
# =====================================================================

def rule4b_harmonize_post_desalting(row: pd.Series,
                                    mol_charge: Optional[int],
                                    prior_target: Optional[int]) -> Tuple[Optional[int], str, bool]:
    """
    After Rule1 (desalting), align target/figure to the new charge if needed.
    
    Args:
        row: DataFrame row (modified in place)
        mol_charge: Current molecular charge after desalting
        prior_target: Previous target charge
        
    Returns:
        Tuple of (new_target, message, applied_bool)
    """
    try:
        if (prior_target == 0) and (mol_charge not in (None, 0)) and rule4_looks_desalted_cation(row):
            if row.get("figure_definition_charge") in (0, None):
                base = row.get("figure_definition_parsed") or parse_figure_definition(row.get("figure_definition", ""))[0] or "L"
                q = int(mol_charge)
                suf = ("/+" if q > 0 else "/-") if abs(q) == 1 else f"/{abs(q)}{('+' if q > 0 else '-')}"
                row["figure_definition_original"] = row.get("figure_definition")
                row["figure_definition"] = f"{base}{suf}"
                core2, h2, l2, q2 = parse_figure_definition(row["figure_definition"])
                row["figure_definition_parsed"] = core2
                row["h_count"], row["l_count"] = h2, l2
                row["figure_definition_charge"] = q2
                row["figure_excess_charge"] = q2
            row["looks_desalted_cation"] = True
            return int(mol_charge), "Rule4b: harmonized target/figure to post-desalting charge", True
    except Exception:
        pass
    return prior_target, "", False


# =====================================================================
# Rule 5: Set Figure from Molblock Superatom
# =====================================================================

def rule5_set_figure_from_molblock_superatom(row: pd.Series) -> Tuple[str, bool]:
    """
    Set the figure from a molblock superatom label (HXL-03; e.g. 'Hydrogen selenate' H2SeO4 -> H2L).
    
    Args:
        row: DataFrame row (modified in place)
        
    Returns:
        Tuple of (message, applied_bool)
    """
    mb = row.get("molblock", None)
    if not isinstance(mb, str) or "M  SMT" not in mb:
        return "", False

    labels = []
    for line in mb.splitlines():
        m = re.match(r"^\s*M\s+SMT\s+\d+\s+(.+)\s*$", line)
        if m:
            labels.append(m.group(1).strip())

    hit = next((lab for lab in labels if lab in _mr.HXL03_SUPERATOM_FIGURES), None)
    if hit is None:
        return "", False

    new_fig = _mr.HXL03_SUPERATOM_FIGURES[hit]
    if str(row.get("figure_definition", "")).strip() == new_fig:
        return "", False

    row["figure_definition_original"] = row.get("figure_definition")
    row["figure_definition"] = new_fig

    core2, h2, l2, q2 = parse_figure_definition(new_fig)
    row["figure_definition_parsed"] = core2
    row["h_count"], row["l_count"] = h2, l2
    row["figure_definition_charge"] = q2
    row["figure_excess_charge"] = q2

    return f"Rule5: set figure_definition to '{new_fig}' (from molblock superatom label '{hit}')", True


# =====================================================================
# Rule 6: Fix Known Entries
# =====================================================================

def rule6_fix_figure_for_two_entries(row: pd.Series) -> Tuple[str, bool]:
    """
    Special-case fix for the pinned entries of HXL-04 (ligand ids 6652, 9695).
    
    Args:
        row: DataFrame row (modified in place)
        
    Returns:
        Tuple of (message, applied_bool)
    """
    inchi = str(row.get("InChI", "") or row.get("InChi", "") or row.get("Inchi", ""))
    name_all = " ".join(str(row.get(c, "")) for c in ("ligand_name", "name_ligand", "COMMON_NAME", "IUPAC_NAME")).lower()

    pin_id, pin = next(((lid, p) for lid, p in _mr.HXL04_PINNED_FIGURES.items()
                        if inchi.startswith(p.inchi_prefix) or p.name_fragment in name_all), (None, None))
    if pin is None:
        return "", False

    mb = row.get("molblock")
    q = charge_from_molblock_text(mb)
    if q in (None, 0):
        return "", False

    core = pin.core

    if abs(q) == 1:
        suf = "/+" if q > 0 else "/-"
    else:
        suf = f"/{abs(q)}+" if q > 0 else f"/{abs(q)}-"
    new_fig = f"{core}{suf}"

    if str(row.get("figure_definition", "")).strip() == new_fig:
        return "", False

    row["figure_definition_original"] = row.get("figure_definition")
    row["figure_definition"] = new_fig

    core2, h2, l2, q2 = parse_figure_definition(new_fig)
    row["figure_definition_parsed"] = core2
    row["h_count"], row["l_count"] = h2, l2
    row["figure_definition_charge"] = q2
    row["figure_excess_charge"] = q2

    return f"Rule6: set figure_definition from molblock charge for known entry ({pin_id})", True
