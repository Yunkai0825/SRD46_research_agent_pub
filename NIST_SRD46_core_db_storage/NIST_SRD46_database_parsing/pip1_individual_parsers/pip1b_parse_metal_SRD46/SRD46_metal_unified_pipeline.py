#!/usr/bin/env python
"""
NIST SRD 46 Metal Parsing Pipeline (Unified)
=============================================

Parses metal species from the SRD46 database, extracting:
- Metal ion name and charge
- Pure element symbol (stripped of charge/subscripts)
- SMILES and InChI representations
- Stoichiometric components

Description: Parses metal entries from the NIST SRD46 database,
             generating standardized molecular identifiers and
             structural metadata for downstream integration.

Input: metal__11.csv from SRD46 SQL export
Output: metal_parsed.csv, metal_augmented.csv, metal_entries.json
"""

from __future__ import annotations
import re
import os
import json
import html
import shutil
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any
from collections import Counter
import pandas as pd
import logging

# ═══════════════════════════════════════════════════════════════════════════════
# OPTIONAL RDKIT IMPORT
# ═══════════════════════════════════════════════════════════════════════════════
try:
    from rdkit import Chem
    from rdkit.Chem.inchi import MolFromInchi, MolToInchi, INCHI_AVAILABLE
    RDKIT_AVAILABLE = True
except ImportError:
    RDKIT_AVAILABLE = False
    INCHI_AVAILABLE = False

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
now = datetime.now()
FORMATTED_DATETIME = now.strftime("%Y-%m-%d-%H-%M-%S")

@dataclass
class MetalPipelineConfig:
    """Central configuration for the metal parsing pipeline."""
    
    # ── Root Paths ──────────────────────────────────────────────────────────────
    CODE_ROOT: Path = Path(__file__).resolve().parent
    PROJECT_ROOT: Path = None  # Auto: CODE_ROOT.parent.parent
    
    # ── Input Paths ─────────────────────────────────────────────────────────────
    INPUT_ROOT: Path = None  # Auto: PROJECT_ROOT / "_input"
    CSV_ROOT: Path = None    # Auto: INPUT_ROOT / "SRD46_SQL_and_CSV/Export/CSV files"
    INPUT_METAL_CSV: Path = None  # Auto: CSV_ROOT / "metal__11.csv"
    
    # ── Output Paths ────────────────────────────────────────────────────────────
    BUILD_DIR: Path = None   # Auto: CODE_ROOT / "_build"
    FINAL_OUTPUT_DIR: Path = None  # Auto: PROJECT_ROOT / "_output/pip1b_metal_pipeline_final_output"
    
    # ── Processing Options ──────────────────────────────────────────────────────
    VERBOSE: bool = True
    EXPORT_FLAG: bool = True
    GENERATE_SMILES_INCHI: bool = True  # Use RDKit if available
    
    def __post_init__(self):
        """Auto-fill paths based on roots."""
        if self.PROJECT_ROOT is None:
            self.PROJECT_ROOT = self.CODE_ROOT.parent.parent
        if self.INPUT_ROOT is None:
            self.INPUT_ROOT = self.PROJECT_ROOT / "_input"
        if self.CSV_ROOT is None:
            self.CSV_ROOT = self.INPUT_ROOT / "SRD46_SQL_and_CSV" / "Export" / "CSV files"
        if self.INPUT_METAL_CSV is None:
            self.INPUT_METAL_CSV = self.CSV_ROOT / "metal__11.csv"
        if self.BUILD_DIR is None:
            self.BUILD_DIR = self.CODE_ROOT / "_build"
        if self.FINAL_OUTPUT_DIR is None:
            self.FINAL_OUTPUT_DIR = self.PROJECT_ROOT / "_output" / "pip1b_metal_pipeline_final_output"


# Global config instance
CONFIG = MetalPipelineConfig()

# Primary key column
METAL_PK = "metalID"

# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def print_debug(msg: str) -> None:
    """Print debug message if verbose mode is enabled."""
    if CONFIG.VERBOSE:
        print(msg)


# ═══════════════════════════════════════════════════════════════════════════════
# PERIODIC TABLE DATA
# ═══════════════════════════════════════════════════════════════════════════════

# Common element symbols (for validation)
ELEMENT_SYMBOLS = {
    'H', 'He', 'Li', 'Be', 'B', 'C', 'N', 'O', 'F', 'Ne',
    'Na', 'Mg', 'Al', 'Si', 'P', 'S', 'Cl', 'Ar',
    'K', 'Ca', 'Sc', 'Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn',
    'Ga', 'Ge', 'As', 'Se', 'Br', 'Kr',
    'Rb', 'Sr', 'Y', 'Zr', 'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd',
    'In', 'Sn', 'Sb', 'Te', 'I', 'Xe',
    'Cs', 'Ba', 'La', 'Ce', 'Pr', 'Nd', 'Pm', 'Sm', 'Eu', 'Gd', 'Tb', 'Dy',
    'Ho', 'Er', 'Tm', 'Yb', 'Lu',
    'Hf', 'Ta', 'W', 'Re', 'Os', 'Ir', 'Pt', 'Au', 'Hg', 'Tl', 'Pb', 'Bi',
    'Po', 'At', 'Rn', 'Fr', 'Ra',
    'Ac', 'Th', 'Pa', 'U', 'Np', 'Pu', 'Am', 'Cm', 'Bk', 'Cf', 'Es', 'Fm',
    'Md', 'No', 'Lr', 'Rf', 'Db', 'Sg', 'Bh', 'Hs', 'Mt',
}

# Organic substituent abbreviations in SRD46 (Me, Et, Pr, Bu, Ph, Cet, Vy -> CH3, C2H5, ...).
# Declared once in srd46_pipeline/manual_rules.py (rule MET-02) and re-exported here; the
# regexes below keep working on the same keys. Known clash kept as data: 'Pr' also is
# praseodymium (metal 139, Pr^[3+]); MET-02 ledgers it as suspect_element_clash.
try:
    from srd46_pipeline import manual_rules as _mr
except ImportError:  # standalone use from inside the parser folder: project root = 2 levels up
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from srd46_pipeline import manual_rules as _mr

ORGANIC_SUBSTITUENTS = dict(_mr.MET02_ORGANIC_SUBSTITUENTS)

# ═══════════════════════════════════════════════════════════════════════════════
# REGEX PATTERNS FOR METAL PARSING
# ═══════════════════════════════════════════════════════════════════════════════

# Pattern for SRD46 notation: subscript [_[n]] and superscript [^[charge]]
# Examples: Ag^[+], Cu^[2+], UO_[2]^[2+], Me_[3]Sn^[+]
RE_SUBSCRIPT = re.compile(r'_\[(\d+)\]')
RE_SUPERSCRIPT = re.compile(r'\^(\[[^\]]*\])')
RE_CHARGE_EXTRACT = re.compile(r'\[([+-]?\d*[+-]?)\]')

# HTML tag patterns (from original database)
RE_HTML_SUB = re.compile(r'<sub>(\d+)</sub>', re.IGNORECASE)
RE_HTML_SUP = re.compile(r'<sup>([^<]+)</sup>', re.IGNORECASE)

# Element pattern: uppercase letter optionally followed by lowercase
RE_ELEMENT = re.compile(r'([A-Z][a-z]?)')

# Combined pattern for metal ion: Element + optional subscript + optional charge
RE_METAL_ION = re.compile(
    r'^'
    r'([A-Z][a-z]?)'           # Primary element symbol
    r'(?:_?\[?(\d+)\]?)?'      # Optional subscript count
    r'(?:\^?\[?([+-]?\d*[+-]?)\]?)?'  # Optional charge
    r'$'
)

# Pattern for complex species: multiple components
RE_COMPLEX_COMPONENT = re.compile(
    r'([A-Z][a-z]?)(\d*)'      # Element with optional count
    r'|'
    r'\(([^)]+)\)(\d*)'        # Parenthesized group with optional count
)


# ═══════════════════════════════════════════════════════════════════════════════
# CORE PARSING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def clean_metal_name(raw_name: str) -> str:
    """
    Clean metal name from SRD46 format to standard notation.
    
    Converts: Ag^[+] → Ag+, UO_[2]^[2+] → UO2(2+)
    
    Args:
        raw_name: Raw metal name from SRD46 (e.g., "Ag^[+]", "Cu^[2+]")
        
    Returns:
        Cleaned metal name string
    """
    if not raw_name or pd.isna(raw_name) or raw_name == '\\N':
        return None
    
    s = str(raw_name).strip()
    
    # Convert subscripts: _[n] → n
    s = RE_SUBSCRIPT.sub(r'\1', s)
    
    # Convert superscripts/charges: ^[x] → (x) for display
    s = RE_SUPERSCRIPT.sub(r'\1', s)
    
    # Clean up remaining brackets
    s = s.replace('[', '').replace(']', '')
    
    return s


def parse_charge(charge_str: str) -> int:
    """
    Parse charge string to integer.
    
    Examples:
        "+" → +1
        "2+" → +2
        "-" → -1
        "3-" → -3
        "2-" → -2
        
    Args:
        charge_str: Charge string (e.g., "+", "2+", "2-", "-")
        
    Returns:
        Integer charge value
    """
    if not charge_str or pd.isna(charge_str):
        return 0
    
    s = str(charge_str).strip()
    if not s:
        return 0
    
    # Handle formats: +, 2+, -, 2-, +2, -2
    if s == '+':
        return 1
    elif s == '-':
        return -1
    elif s.endswith('+'):
        num_part = s[:-1]
        return int(num_part) if num_part else 1
    elif s.endswith('-'):
        num_part = s[:-1]
        return -(int(num_part) if num_part else 1)
    elif s.startswith('+'):
        num_part = s[1:]
        return int(num_part) if num_part else 1
    elif s.startswith('-'):
        num_part = s[1:]
        return -(int(num_part) if num_part else 1)
    else:
        try:
            return int(s)
        except ValueError:
            return 0


def extract_charge_from_name(metal_name: str) -> Tuple[str, int, str]:
    """
    Extract charge information from metal name.
    
    Args:
        metal_name: Metal name (e.g., "Ag^[+]", "Cu^[2+]", "UO_[2]^[2+]")
        
    Returns:
        Tuple of (base_formula, charge, charge_str)
    """
    if not metal_name or pd.isna(metal_name):
        return None, 0, None
    
    s = str(metal_name).strip()
    
    # Find superscript pattern ^[...] for charge
    charge_match = RE_SUPERSCRIPT.search(s)
    
    if charge_match:
        charge_bracket = charge_match.group(1)  # e.g., "[2+]"
        # Extract charge value from bracket
        inner_match = RE_CHARGE_EXTRACT.search(charge_bracket)
        if inner_match:
            charge_str = inner_match.group(1)
            charge = parse_charge(charge_str)
        else:
            charge_str = charge_bracket.strip('[]')
            charge = parse_charge(charge_str)
        
        # Base formula is everything before the charge
        base = s[:charge_match.start()]
        # Clean subscripts
        base = RE_SUBSCRIPT.sub(r'\1', base)
        
        return base, charge, charge_str
    else:
        # No explicit charge
        base = RE_SUBSCRIPT.sub(r'\1', s)
        return base, 0, None


def extract_pure_symbol(metal_name: str, name_metal_pur: str = None) -> str:
    """
    Extract the pure element symbol from metal name.
    
    Prioritizes name_metal_pur if available and valid,
    otherwise parses from metal_name.
    
    Args:
        metal_name: Full metal name (e.g., "Ag^[+]")
        name_metal_pur: Pure name from database (e.g., "Ag")
        
    Returns:
        Pure element symbol (e.g., "Ag")
    """
    # First try name_metal_pur if valid
    if name_metal_pur and pd.notna(name_metal_pur) and name_metal_pur != '\\N':
        pur = str(name_metal_pur).strip()
        # Check if it's a valid element or simple formula
        if pur and pur[0].isupper():
            # Remove trailing digits (oxidation state indicators like "2" in "Ag2")
            match = re.match(r'^([A-Z][a-z]?)', pur)
            if match:
                elem = match.group(1)
                if elem in ELEMENT_SYMBOLS:
                    return elem
            # Return as-is if it's a complex formula
            return pur
    
    # Parse from metal_name
    if not metal_name or pd.isna(metal_name):
        return None
    
    s = str(metal_name).strip()
    
    # Remove charge notation
    s = RE_SUPERSCRIPT.sub('', s)
    # Remove subscripts
    s = RE_SUBSCRIPT.sub('', s)
    # Clean brackets
    s = s.replace('[', '').replace(']', '').replace('^', '').replace('_', '')
    
    # Extract first element
    match = re.match(r'^([A-Z][a-z]?)', s)
    if match:
        return match.group(1)
    
    return s if s else None


def parse_metal_formula(metal_name: str) -> Dict[str, Any]:
    """
    Parse metal formula into components.
    
    Handles:
    - Simple ions: Ag^[+] → {'Ag': 1}
    - Oxo species: UO_[2]^[2+] → {'U': 1, 'O': 2}
    - Organometallics: Me_[3]Sn^[+] → {'Me': 3, 'Sn': 1}
    
    Args:
        metal_name: Metal name from SRD46
        
    Returns:
        Dictionary with parsed components
    """
    result = {
        'formula_clean': None,
        'components': {},
        'charge': 0,
        'is_simple_ion': True,
        'is_organometallic': False,
        'primary_metal': None,
        'parse_notes': [],
    }
    
    if not metal_name or pd.isna(metal_name):
        result['parse_notes'].append('Empty or null input')
        return result
    
    s = str(metal_name).strip()
    
    # Extract charge first
    base_formula, charge, charge_str = extract_charge_from_name(s)
    result['charge'] = charge
    
    if not base_formula:
        result['parse_notes'].append('No base formula after charge extraction')
        return result
    
    result['formula_clean'] = base_formula
    
    # Check for organic substituents
    for abbrev in ORGANIC_SUBSTITUENTS:
        if abbrev in base_formula:
            result['is_organometallic'] = True
            result['is_simple_ion'] = False
            break
    
    # Parse components
    # Pattern: Element followed by optional count, or organic group
    components = {}
    remaining = base_formula
    
    # Handle organic substituents first
    for abbrev in sorted(ORGANIC_SUBSTITUENTS.keys(), key=len, reverse=True):
        pattern = rf'{abbrev}(\d*)'
        matches = list(re.finditer(pattern, remaining))
        for m in matches:
            count = int(m.group(1)) if m.group(1) else 1
            components[abbrev] = components.get(abbrev, 0) + count
            remaining = remaining.replace(m.group(0), '', 1)
    
    # Handle parenthesized groups like (OH), (NH2), (NH3)
    paren_pattern = r'\(([^)]+)\)(\d*)'
    for m in re.finditer(paren_pattern, remaining):
        group = m.group(1)
        count = int(m.group(2)) if m.group(2) else 1
        components[f'({group})'] = components.get(f'({group})', 0) + count
        remaining = remaining.replace(m.group(0), '', 1)
    
    # Handle regular elements
    elem_pattern = r'([A-Z][a-z]?)(\d*)'
    for m in re.finditer(elem_pattern, remaining):
        elem = m.group(1)
        count = int(m.group(2)) if m.group(2) else 1
        if elem in ELEMENT_SYMBOLS:
            components[elem] = components.get(elem, 0) + count
            if result['primary_metal'] is None and elem not in {'O', 'H', 'N', 'C', 'S', 'Cl', 'F', 'Br', 'I'}:
                result['primary_metal'] = elem
    
    result['components'] = components
    
    # Determine if simple ion (single metal, no polyatomic groups)
    metal_count = sum(1 for k in components if k in ELEMENT_SYMBOLS and k not in {'O', 'H', 'N', 'C', 'S', 'Cl', 'F', 'Br', 'I'})
    if metal_count == 1 and len(components) == 1:
        result['is_simple_ion'] = True
    elif len(components) > 1 or result['is_organometallic']:
        result['is_simple_ion'] = False
    
    return result


def generate_smiles(metal_name: str, charge: int, components: Dict[str, int]) -> Optional[str]:
    """
    Generate SMILES representation for metal ion.
    
    Args:
        metal_name: Original metal name
        charge: Ion charge
        components: Parsed components dict
        
    Returns:
        SMILES string or None if cannot generate
    """
    if not RDKIT_AVAILABLE:
        # Fallback: generate simple SMILES for simple ions
        if len(components) == 1:
            elem = list(components.keys())[0]
            if elem in ELEMENT_SYMBOLS and components[elem] == 1:
                if charge > 0:
                    return f"[{elem}+{charge}]" if charge > 1 else f"[{elem}+]"
                elif charge < 0:
                    return f"[{elem}{charge}]" if charge < -1 else f"[{elem}-]"
                else:
                    return f"[{elem}]"
        return None
    
    try:
        # Build SMILES for simple ions
        if len(components) == 1:
            elem = list(components.keys())[0]
            if elem in ELEMENT_SYMBOLS and components[elem] == 1:
                # RDKit prefers numeric charge format: [Ag+] for +1, [Fe+3] for +3
                if charge > 0:
                    charge_str = f'+{charge}' if charge > 1 else '+'
                    smiles = f"[{elem}{charge_str}]"
                elif charge < 0:
                    charge_str = f'{charge}' if charge < -1 else '-'
                    smiles = f"[{elem}{charge_str}]"
                else:
                    smiles = f"[{elem}]"
                
                # Validate with RDKit
                mol = Chem.MolFromSmiles(smiles)
                if mol:
                    return smiles
        
        # For complex species, return None (would need manual curation)
        return None
        
    except Exception as e:
        return None


def generate_inchi(smiles: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Generate InChI and InChIKey from SMILES.
    
    Args:
        smiles: SMILES string
        
    Returns:
        Tuple of (InChI, InChIKey) or (None, None) if cannot generate
    """
    if not RDKIT_AVAILABLE or not smiles:
        return None, None
    
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None, None
        
        inchi = Chem.MolToInchi(mol)
        inchikey = Chem.MolToInchiKey(mol) if inchi else None
        
        return inchi, inchikey
        
    except Exception as e:
        return None, None


def parse_parts_used(metal_name: str, parsed: Dict[str, Any]) -> List[str]:
    """
    Generate parts_used list for JSON output.
    
    Args:
        metal_name: Original metal name
        parsed: Parsed formula dictionary
        
    Returns:
        List of parts used in parsing
    """
    parts = []
    
    # Add primary element/formula
    if parsed.get('primary_metal'):
        parts.append(parsed['primary_metal'])
    elif parsed.get('formula_clean'):
        parts.append(parsed['formula_clean'])
    
    # Add charge notation
    if parsed.get('charge', 0) != 0:
        charge = parsed['charge']
        if charge > 0:
            parts.append(f'^+{charge}' if charge > 1 else '^+1')
        else:
            parts.append(f'^{charge}')
    
    return parts if parts else None


def calculate_stoichiometry(components: Dict[str, int]) -> Optional[Dict[str, int]]:
    """
    Calculate element stoichiometry from components.
    
    Args:
        components: Parsed components dict
        
    Returns:
        Stoichiometry dict or None for simple ions
    """
    if not components or len(components) <= 1:
        return None
    
    # Expand organic groups
    stoich = {}
    for key, count in components.items():
        if key in ORGANIC_SUBSTITUENTS:
            # Expand organic group
            expansion = ORGANIC_SUBSTITUENTS[key]
            # Parse expansion (e.g., "CH3" → {'C': 1, 'H': 3})
            for m in re.finditer(r'([A-Z][a-z]?)(\d*)', expansion):
                elem = m.group(1)
                elem_count = int(m.group(2)) if m.group(2) else 1
                stoich[elem] = stoich.get(elem, 0) + elem_count * count
        elif key.startswith('(') and key.endswith(')'):
            # Parenthesized group
            inner = key[1:-1]
            for m in re.finditer(r'([A-Z][a-z]?)(\d*)', inner):
                elem = m.group(1)
                elem_count = int(m.group(2)) if m.group(2) else 1
                stoich[elem] = stoich.get(elem, 0) + elem_count * count
        elif key in ELEMENT_SYMBOLS:
            stoich[key] = stoich.get(key, 0) + count
    
    return stoich if stoich else None


# ═══════════════════════════════════════════════════════════════════════════════
# DATAFRAME PROCESSING
# ═══════════════════════════════════════════════════════════════════════════════

def load_metal_csv(file_path: Path = None) -> pd.DataFrame:
    """
    Load metal CSV file from SRD46 export.
    
    Args:
        file_path: Path to metal CSV file
        
    Returns:
        Loaded DataFrame
    """
    if file_path is None:
        file_path = CONFIG.INPUT_METAL_CSV
    
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"Metal CSV file not found: {file_path}")
    
    print_debug(f"[INFO] Loading metal CSV from: {file_path}")
    
    df = pd.read_csv(file_path, encoding='utf-8')
    
    print_debug(f"[INFO] Loaded {len(df)} metal entries")
    print_debug(f"[INFO] Columns: {list(df.columns)}")
    
    return df


def parse_all_metals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parse all metal entries in the DataFrame.
    
    Adds columns:
    - name_metal_clean: Cleaned metal name
    - symbol_pure: Pure element symbol
    - charge: Ion charge
    - charge_str: Charge as string
    - formula_components: JSON string of components
    - SMILES: SMILES representation
    - InChI: InChI representation
    - InChIKey: InChI key
    - is_simple_ion: True if simple monoatomic ion
    - is_organometallic: True if contains organic groups
    - primary_metal: Primary metal element
    - parts_used: JSON list of parsing components
    - stoichiometry: JSON dict of element counts
    - parse_notes: Any parsing notes/warnings
    
    Args:
        df: DataFrame with metal data
        
    Returns:
        DataFrame with parsed columns added
    """
    df = df.copy()
    
    # Initialize new columns
    new_cols = {
        'name_metal_clean': [],
        'symbol_pure': [],
        'charge': [],
        'charge_str': [],
        'formula_components': [],
        'SMILES': [],
        'InChI': [],
        'InChIKey': [],
        'is_simple_ion': [],
        'is_organometallic': [],
        'primary_metal': [],
        'parts_used': [],
        'stoichiometry': [],
        'parse_notes': [],
    }
    
    # Determine source column
    name_col = 'name_metal' if 'name_metal' in df.columns else df.columns[1]
    pur_col = 'name_metal_pur' if 'name_metal_pur' in df.columns else None
    
    for idx, row in df.iterrows():
        metal_name = row.get(name_col)
        metal_pur = row.get(pur_col) if pur_col else None
        
        # Parse the metal formula
        parsed = parse_metal_formula(metal_name)
        
        # Extract base formula and charge
        base_formula, charge, charge_str = extract_charge_from_name(metal_name)
        
        # Get pure symbol
        symbol_pure = extract_pure_symbol(metal_name, metal_pur)
        
        # Generate SMILES
        smiles = None
        if CONFIG.GENERATE_SMILES_INCHI:
            smiles = generate_smiles(metal_name, charge, parsed['components'])
        
        # Generate InChI
        inchi, inchikey = None, None
        if smiles:
            inchi, inchikey = generate_inchi(smiles)
        
        # Calculate stoichiometry
        stoich = calculate_stoichiometry(parsed['components'])
        
        # Build parts_used
        parts = parse_parts_used(metal_name, parsed)
        
        # Append to columns
        new_cols['name_metal_clean'].append(clean_metal_name(metal_name))
        new_cols['symbol_pure'].append(symbol_pure)
        new_cols['charge'].append(charge)
        new_cols['charge_str'].append(charge_str)
        new_cols['formula_components'].append(json.dumps(parsed['components']) if parsed['components'] else None)
        new_cols['SMILES'].append(smiles)
        new_cols['InChI'].append(inchi)
        new_cols['InChIKey'].append(inchikey)
        new_cols['is_simple_ion'].append(parsed['is_simple_ion'])
        new_cols['is_organometallic'].append(parsed['is_organometallic'])
        new_cols['primary_metal'].append(parsed['primary_metal'])
        new_cols['parts_used'].append(json.dumps(parts) if parts else None)
        new_cols['stoichiometry'].append(json.dumps(stoich) if stoich else None)
        new_cols['parse_notes'].append('; '.join(parsed['parse_notes']) if parsed['parse_notes'] else None)
    
    # Add columns to DataFrame
    for col, values in new_cols.items():
        df[col] = values
    
    return df


def generate_metal_entry_json(row: pd.Series) -> Dict[str, Any]:
    """
    Generate JSON entry for a single metal.
    
    Matches the format shown in the example:
    {
      "metal_id": 2,
      "metal_name_SRD": "Ag^[+]",
      "symbol_pure": "Ag",
      "SMILES": "[Ag+]",
      "InChi": "InChI=1S/Ag/q+1",
      "InChiKey": "FOIXSVOLVBLSDH-UHFFFAOYSA-N",
      "parts_used": ["Ag", "^+1"],
      "parse_notes": null,
      "stoichiometry": null
    }
    
    Args:
        row: DataFrame row with parsed metal data
        
    Returns:
        JSON-serializable dictionary
    """
    # Get metal ID
    metal_id = row.get(METAL_PK) or row.get('metalID')
    
    # Get name column
    name_col = 'name_metal' if 'name_metal' in row.index else row.index[1]
    
    # Parse parts_used if string
    parts_used = row.get('parts_used')
    if isinstance(parts_used, str):
        try:
            parts_used = json.loads(parts_used)
        except:
            parts_used = None
    
    # Parse stoichiometry if string
    stoich = row.get('stoichiometry')
    if isinstance(stoich, str):
        try:
            stoich = json.loads(stoich)
        except:
            stoich = None
    
    entry = {
        'metal_id': int(metal_id) if pd.notna(metal_id) else None,
        'metal_name_SRD': row.get(name_col),
        'symbol_pure': row.get('symbol_pure'),
        'SMILES': row.get('SMILES'),
        'InChi': row.get('InChI'),
        'InChiKey': row.get('InChIKey'),
        'parts_used': parts_used,
        'parse_notes': row.get('parse_notes'),
        'stoichiometry': stoich,
    }
    
    return entry


def generate_all_metal_entries(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Generate JSON entries for all metals.
    
    Args:
        df: Parsed DataFrame
        
    Returns:
        List of metal entry dictionaries
    """
    entries = []
    for idx, row in df.iterrows():
        entry = generate_metal_entry_json(row)
        entries.append(entry)
    return entries


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def export_parsed_csv(df: pd.DataFrame, out_path: Path) -> None:
    """Export parsed DataFrame to CSV."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False, encoding='utf-8')
    print_debug(f"[EXPORT] Saved parsed CSV -> {out_path}")


def export_metal_entries_json(entries: List[Dict], out_path: Path) -> None:
    """Export metal entries as JSON array."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    print_debug(f"[EXPORT] Saved metal entries JSON -> {out_path}")


METAL_COLUMN_METADATA: Dict[str, str] = {
    METAL_PK: "Primary key from SRD46 metal table.",
    "name_metal": "Original metal name from SRD46 (with subscript/superscript notation).",
    "name_metal_pur": "Pure metal name/abbreviation from SRD46.",
    "name_metal_clean": "Cleaned metal name (subscripts/superscripts converted).",
    "symbol_pure": "Pure element symbol (e.g., 'Ag', 'Cu').",
    "charge": "Ion charge as integer.",
    "charge_str": "Charge as string (e.g., '+', '2+', '3-').",
    "formula_components": "JSON dict of formula components and counts.",
    "SMILES": "SMILES representation of the metal ion.",
    "InChI": "InChI identifier.",
    "InChIKey": "InChI key (hashed InChI).",
    "is_simple_ion": "True if simple monoatomic ion (e.g., Ag+).",
    "is_organometallic": "True if contains organic substituents.",
    "primary_metal": "Primary metal element in the species.",
    "parts_used": "JSON list of components used in parsing.",
    "stoichiometry": "JSON dict of element stoichiometry.",
    "parse_notes": "Any parsing notes or warnings.",
    "type": "Metal type code from SRD46.",
    "order": "Ordering value from SRD46.",
    "part_of": "Parent metal reference from SRD46.",
    "preselection": "Preselection flag from SRD46.",
}

# Columns of the compact metal_parsed table (subset of the augmented table)
METAL_PARSED_EXPORT_COLS = [
    METAL_PK, 'name_metal', 'name_metal_pur', 'name_metal_clean',
    'symbol_pure', 'charge', 'charge_str', 'SMILES', 'InChI', 'InChIKey',
    'is_simple_ion', 'is_organometallic', 'primary_metal',
    'parts_used', 'stoichiometry', 'parse_notes',
]


def export_column_metadata(out_path: Path) -> None:
    """Export column metadata documentation."""
    metadata = dict(METAL_COLUMN_METADATA)
    
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2, sort_keys=True)
    print_debug(f"[EXPORT] Saved column metadata -> {out_path}")


def generate_summary_markdown(df: pd.DataFrame, out_path: Path) -> str:
    """
    Generate pipeline summary as Markdown.
    
    Args:
        df: Processed DataFrame
        out_path: Path to save markdown file
        
    Returns:
        Markdown string
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Calculate statistics
    total = len(df)
    simple_ions = df['is_simple_ion'].sum() if 'is_simple_ion' in df.columns else 0
    organometallic = df['is_organometallic'].sum() if 'is_organometallic' in df.columns else 0
    with_smiles = df['SMILES'].notna().sum() if 'SMILES' in df.columns else 0
    with_inchi = df['InChI'].notna().sum() if 'InChI' in df.columns else 0
    
    # Count unique primary metals
    primary_metals = df['primary_metal'].dropna().unique() if 'primary_metal' in df.columns else []
    
    # Charge distribution
    charge_dist = df['charge'].value_counts().sort_index() if 'charge' in df.columns else {}
    
    lines = [
        "# NIST SRD 46 Metal Parsing Pipeline Summary",
        "",
        f"**Generated:** {now_str}",
        f"**Input File:** `{CONFIG.INPUT_METAL_CSV}`",
        f"**Build Directory:** `{CONFIG.BUILD_DIR}`",
        "",
        "---",
        "",
        "## Overview",
        "",
        "| Metric | Count |",
        "|--------|-------|",
        f"| Total metal entries | {total} |",
        f"| Simple ions | {simple_ions} |",
        f"| Organometallic species | {organometallic} |",
        f"| With SMILES | {with_smiles} |",
        f"| With InChI | {with_inchi} |",
        f"| Unique primary metals | {len(primary_metals)} |",
        "",
        "---",
        "",
        "## Charge Distribution",
        "",
        "| Charge | Count |",
        "|--------|-------|",
    ]
    
    for charge, count in charge_dist.items():
        charge_label = f"+{charge}" if charge > 0 else str(charge)
        lines.append(f"| {charge_label} | {count} |")
    
    lines.extend([
        "",
        "---",
        "",
        "## Output Files",
        "",
        "| File | Description |",
        "|------|-------------|",
        f"| `metal_parsed.csv` | Parsed metal data with all columns |",
        f"| `metal_augmented.csv` | Full DataFrame with original + parsed columns |",
        f"| `metal_entries.json` | All entries as JSON array |",
        f"| `metal_columns_meta.json` | Column metadata documentation |",
        "",
        "---",
        "",
        f"*Pipeline completed at {now_str}*",
    ])
    
    md_content = "\n".join(lines)
    
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    print_debug(f"[EXPORT] Saved summary markdown -> {out_path}")
    
    return md_content


def copy_to_final_output(build_dir: Path, final_dir: Path) -> List[Path]:
    """
    Copy core outputs to final output directory.
    
    Args:
        build_dir: Build directory with outputs
        final_dir: Final output directory
        
    Returns:
        List of copied file paths
    """
    final_dir.mkdir(parents=True, exist_ok=True)
    
    core_files = [
        "metal_parsed.csv",
        "metal_augmented.csv",
        "metal_entries.json",
        "metal_columns_meta.json",
    ]
    
    copied = []
    for filename in core_files:
        src = build_dir / filename
        if src.exists():
            dst = final_dir / filename
            shutil.copy2(src, dst)
            copied.append(dst)
            print_debug(f"[COPY] {src.name} -> {final_dir}")
    
    return copied


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def run_metal_pipeline(
    input_path: Path = None,
    build_dir: Path = None,
    export: bool = True,
) -> pd.DataFrame:
    """
    Run the full metal parsing pipeline.
    
    Args:
        input_path: Path to input CSV (default: CONFIG.INPUT_METAL_CSV)
        build_dir: Build output directory (default: CONFIG.BUILD_DIR)
        export: Whether to export results
        
    Returns:
        Processed DataFrame
    """
    if input_path is None:
        input_path = CONFIG.INPUT_METAL_CSV
    if build_dir is None:
        build_dir = CONFIG.BUILD_DIR
    
    build_dir.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Load data
    print_debug("\n[STEP 1] Loading metal CSV...")
    df = load_metal_csv(input_path)
    
    # Step 2: Parse all metals
    print_debug("\n[STEP 2] Parsing metal entries...")
    df = parse_all_metals(df)
    
    # Step 3: Generate statistics
    print_debug("\n[STEP 3] Computing statistics...")
    total = len(df)
    simple_ions = df['is_simple_ion'].sum()
    with_smiles = df['SMILES'].notna().sum()
    with_inchi = df['InChI'].notna().sum()
    
    print_debug(f"  Total entries: {total}")
    print_debug(f"  Simple ions: {simple_ions}")
    print_debug(f"  With SMILES: {with_smiles}")
    print_debug(f"  With InChI: {with_inchi}")
    
    # Step 4: Export
    if export:
        print_debug("\n[STEP 4] Exporting results...")
        
        # Parsed CSV (selected columns)
        export_cols = [c for c in METAL_PARSED_EXPORT_COLS if c in df.columns]
        df_parsed = df[export_cols]
        export_parsed_csv(df_parsed, build_dir / "metal_parsed.csv")
        
        # Full augmented CSV
        export_parsed_csv(df, build_dir / "metal_augmented.csv")
        
        # JSON entries (single aggregate file)
        entries = generate_all_metal_entries(df)
        export_metal_entries_json(entries, build_dir / "metal_entries.json")
        
        # Column metadata
        export_column_metadata(build_dir / "metal_columns_meta.json")
        
        # Summary markdown
        generate_summary_markdown(df, build_dir / f"pipeline_summary_{FORMATTED_DATETIME}.md")
        
        # Copy to final output
        print_debug("\n[STEP 5] Copying to final output directory...")
        CONFIG.FINAL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        copy_to_final_output(build_dir, CONFIG.FINAL_OUTPUT_DIR)
    
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("NIST SRD 46 Metal Parsing Pipeline")
    print("=" * 70)
    print(f"[CONFIG] CODE_ROOT: {CONFIG.CODE_ROOT}")
    print(f"[CONFIG] INPUT_METAL_CSV: {CONFIG.INPUT_METAL_CSV}")
    print(f"[CONFIG] BUILD_DIR: {CONFIG.BUILD_DIR}")
    print(f"[CONFIG] FINAL_OUTPUT_DIR: {CONFIG.FINAL_OUTPUT_DIR}")
    print(f"[CONFIG] Input exists: {CONFIG.INPUT_METAL_CSV.exists()}")
    print(f"[CONFIG] RDKit available: {RDKIT_AVAILABLE}")
    print()
    
    # Run pipeline
    df = run_metal_pipeline()
    
    # Show sample
    if CONFIG.VERBOSE:
        cols_to_show = [
            METAL_PK, 'name_metal', 'symbol_pure', 'charge', 'SMILES', 'is_simple_ion'
        ]
        cols_to_show = [c for c in cols_to_show if c in df.columns]
        print("\n=== Sample parsed data ===")
        with pd.option_context("display.max_colwidth", 60):
            print(df[cols_to_show].head(15))
    
    print("\n" + "=" * 70)
    print("[DONE] Metal parsing pipeline complete.")
    print("=" * 70)
