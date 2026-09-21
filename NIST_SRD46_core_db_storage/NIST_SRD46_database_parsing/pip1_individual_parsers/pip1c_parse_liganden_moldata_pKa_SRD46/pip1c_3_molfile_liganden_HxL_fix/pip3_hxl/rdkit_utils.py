"""
rdkit_utils.py - RDKit structure manipulation utilities.
"""

from typing import Optional, Dict
import pandas as pd

from .rdkit_setup import RDKit_OK

if RDKit_OK:
    from rdkit import Chem
    from rdkit.Chem.rdmolfiles import MolFromMolBlock, MolToMolBlock, MolFromSmiles
    from rdkit.Chem import inchi as rdkit_inchi


def build_mol(row: pd.Series):
    """
    Build RDKit Mol object from row's molblock or SMILES.
    
    Priority: molblock > SMILES
    
    Args:
        row: DataFrame row with 'molblock' and/or 'SMILES' columns
        
    Returns:
        RDKit Mol object or None
    """
    if not RDKit_OK:
        return None
    
    mol = None
    mb = row.get("molblock")
    smi = row.get("SMILES")
    
    # Try molblock first
    if isinstance(mb, str) and mb.strip():
        try:
            mol = MolFromMolBlock(mb, sanitize=False)
            if mol is not None:
                Chem.SanitizeMol(mol, catchErrors=True)
        except Exception:
            mol = None
    
    # Fall back to SMILES
    if mol is None and isinstance(smi, str) and smi.strip():
        try:
            mol = MolFromSmiles(smi)
            if mol is not None:
                Chem.SanitizeMol(mol, catchErrors=True)
        except Exception:
            mol = None
    
    return mol


def recompute_strings(mol) -> Dict[str, Optional[str]]:
    """
    Recompute molblock, SMILES, and InChI from Mol object.
    
    Args:
        mol: RDKit Mol object
        
    Returns:
        Dict with 'molblock', 'SMILES', 'InChI' keys (values may be None)
    """
    out = {"molblock": None, "SMILES": None, "InChI": None}
    
    if not RDKit_OK or mol is None:
        return out
    
    try:
        out["molblock"] = Chem.MolToMolBlock(mol)
    except Exception:
        pass
    
    try:
        out["SMILES"] = Chem.MolToSmiles(mol)
    except Exception:
        pass
    
    try:
        out["InChI"] = rdkit_inchi.MolToInchi(mol)
    except Exception:
        pass
    
    return out


def smiles_frag_count(smi: Optional[str]) -> Optional[int]:
    """Count fragments in a SMILES string."""
    if not RDKit_OK or not isinstance(smi, str) or not smi.strip():
        return None
    try:
        m = MolFromSmiles(smi)
        if not m:
            return None
        return len(Chem.GetMolFrags(m))
    except Exception:
        return None


def mol_frag_count(mol) -> Optional[int]:
    """Count fragments in a Mol object."""
    if not RDKit_OK or mol is None:
        return None
    try:
        return len(Chem.GetMolFrags(mol))
    except Exception:
        return None
