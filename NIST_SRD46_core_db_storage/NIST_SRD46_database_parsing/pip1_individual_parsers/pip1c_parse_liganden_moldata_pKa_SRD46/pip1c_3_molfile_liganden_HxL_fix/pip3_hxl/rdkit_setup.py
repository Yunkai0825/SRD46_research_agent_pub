"""
rdkit_setup.py - RDKit initialization and counter-ion templates.
"""

from typing import List, Tuple, Any

# =====================================================================
# RDKit Import (safe)
# =====================================================================
try:
    from rdkit import Chem
    from rdkit.Chem.rdmolfiles import MolFromMolBlock, MolToMolBlock, MolFromSmiles
    RDKit_OK = True
    RD_ERR = ""
except Exception as e:
    RDKit_OK = False
    RD_ERR = str(e)
    Chem = None  # type: ignore

# =====================================================================
# Counter-ion Templates for Desalting (Rule1)
# =====================================================================
# Declared once in srd46_pipeline/manual_rules.py (rule HXL-01; the HXL-02/03/04 constants
# used by rules.py live there too) and re-exported here in the list shape this package uses.
try:
    from srd46_pipeline import manual_rules as _mr
except ImportError:  # standalone use from inside the parser package: project root = 4 levels up
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[4]))
    from srd46_pipeline import manual_rules as _mr

COUNTERION_TEMPLATES = list(_mr.HXL01_COUNTERION_TEMPLATES)

# Pre-parsed counter-ion Mol objects
COUNTERION_MOLS: List[Tuple[str, Any]] = []

if RDKit_OK and Chem is not None:
    for smi in COUNTERION_TEMPLATES:
        try:
            m = Chem.MolFromSmiles(smi)
            if m:
                COUNTERION_MOLS.append((smi, m))
        except Exception:
            pass

# =====================================================================
# Sanitization Flags
# =====================================================================
# Flags we want *on* (everything except the valence check)
PARTIAL_SAN = None

if RDKit_OK and Chem is not None:
    from rdkit import RDLogger
    RDLogger.DisableLog("rdApp.error")
    RDLogger.DisableLog("rdApp.warning")
    PARTIAL_SAN = (Chem.SanitizeFlags.SANITIZE_ALL ^
                   Chem.SanitizeFlags.SANITIZE_PROPERTIES)
