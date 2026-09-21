"""
charge_utils.py - Charge extraction utilities.
"""

import re
from typing import Optional

from .rdkit_setup import RDKit_OK

if RDKit_OK:
    from rdkit import Chem

# =====================================================================
# Charge Code Mappings (V2000 molfile format)
# =====================================================================
_CHARGE_CODE_MAP = {1: +3, 2: +2, 3: +1, 4: 0, 5: -1, 6: -2, 7: -3}
CODE2FORMAL = {0: 0, 1: +3, 2: +2, 3: +1, 4: 0, 5: -1, 6: -2, 7: -3}


def sum_formal_charge(mol) -> Optional[int]:
    """
    Sum all formal charges on atoms in a molecule.
    
    Args:
        mol: RDKit Mol object
        
    Returns:
        Total formal charge, or None if RDKit unavailable or mol is None
    """
    if not RDKit_OK or mol is None:
        return None
    try:
        return int(sum(a.GetFormalCharge() for a in mol.GetAtoms()))
    except Exception:
        return None


def charge_from_molblock_text(mb: Optional[str]) -> Optional[int]:
    """
    Parse V2000 molblock for charge from M CHG entries and atom-line charge codes.
    
    Args:
        mb: Molblock string
        
    Returns:
        Total charge parsed from molblock, or None/0 if not found
    """
    if not isinstance(mb, str) or not mb.strip():
        return None

    total = 0
    seen_any_charge = False
    code_map = {0: 0, 1: +3, 2: +2, 3: +1, 5: -1, 6: -2, 7: -3}

    for raw in mb.splitlines():
        line = raw.rstrip()

        # M  CHG property line
        if line.startswith("M  CHG"):
            nums = re.findall(r"[-+]?\d+", line)
            if not nums:
                continue
            try:
                n_pairs = int(nums[0])
                vals = list(map(int, nums[1:]))
                for i in range(0, min(len(vals), 2 * n_pairs), 2):
                    total += vals[i + 1]
                    seen_any_charge = True
            except Exception:
                pass
            continue

        # Atom line with charge code
        m = re.match(
            r"^\s*-?\d+\.\d+\s+-?\d+\.\d+\s+-?\d+\.\d+\s+([A-Za-z]{1,3})\s+(.+)$",
            line
        )
        if m:
            tail = m.group(2).split()
            if len(tail) >= 2:
                try:
                    chg_code = int(tail[1])
                    if chg_code in code_map and code_map[chg_code] != 0:
                        total += code_map[chg_code]
                        seen_any_charge = True
                except Exception:
                    pass

    return total if seen_any_charge else 0


def charge_from_inchi(inchi: Optional[str]) -> Optional[int]:
    """
    Extract charge from InChI string (/q and /p layers).
    
    Args:
        inchi: InChI string
        
    Returns:
        Total charge, or None if not found
    """
    if not inchi or not isinstance(inchi, str):
        return None

    q_total = 0
    m_q = re.search(r"/q([^/]+)", inchi)
    if m_q:
        for part in m_q.group(1).split(";"):
            part = part.strip()
            if part:
                try:
                    q_total += int(part)
                except Exception:
                    pass

    p_val = 0
    m_p = re.search(r"/p([+-]?\d+)", inchi)
    if m_p:
        try:
            p_val = int(m_p.group(1))
        except Exception:
            p_val = 0

    if (m_q or m_p):
        return q_total + p_val
    return None


def has_cyanide_hint(text: Optional[str]) -> bool:
    """Check if text contains cyanide SMILES pattern."""
    return isinstance(text, str) and ("C#N" in text or "[C-]#N" in text)
