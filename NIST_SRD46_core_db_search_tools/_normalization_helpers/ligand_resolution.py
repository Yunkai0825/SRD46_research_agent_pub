"""
Ligand identifier resolution for SRD-46.

Resolution pipeline (first match wins):
  1. InChI string   → RDKit canonicalize
  2. SMILES string  → RDKit → canonical InChI + SMILES
  3. Common name    → PubChemPy → RDKit canonicalize
"""

import logging

log = logging.getLogger("SRD46")

# ── RDKit (optional) ─────────────────────────────────────────────────

try:
    from rdkit import Chem
    from rdkit.Chem.inchi import MolFromInchi, MolToInchi
    _HAS_RDKIT = True
except ImportError:
    _HAS_RDKIT = False
    log.warning("RDKit not available — chemical canonicalization disabled")


# ── RDKit canonicalization helpers ────────────────────────────────────

def _canonicalize_inchi(inchi: str) -> str | None:
    """Validate and re-canonicalize an InChI string through RDKit."""
    if not _HAS_RDKIT or not inchi:
        return inchi
    mol = MolFromInchi(inchi, sanitize=True)
    if mol is None:
        return inchi
    canon = MolToInchi(mol)
    return canon or inchi


def _smiles_to_inchi(smiles: str) -> str | None:
    """Convert a SMILES string to canonical InChI via RDKit."""
    if not _HAS_RDKIT or not smiles:
        return None
    mol = Chem.MolFromSmiles(smiles, sanitize=True)
    if mol is None:
        return None
    return MolToInchi(mol)


def _canonical_smiles(smiles: str) -> str | None:
    """Return the RDKit canonical SMILES, or the input unchanged."""
    if not _HAS_RDKIT or not smiles:
        return smiles
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return smiles
    return Chem.MolToSmiles(mol)


# ── Chemical identifier parsing ──────────────────────────────────────

def _parse_chemical_identifier(input_str: str) -> dict:
    """Parse any chemical identifier (InChI, SMILES, or name) to canonical forms.

    Returns ``{"inchi": str|None, "smiles": str|None, "iupac": str|None,
               "source": str}``
    """
    result = {"inchi": None, "smiles": None, "iupac": None, "source": "none"}
    if not input_str or not input_str.strip():
        return result

    s = input_str.strip()

    # 1. Already an InChI string?
    if s.startswith("InChI="):
        result["inchi"] = _canonicalize_inchi(s)
        result["source"] = "inchi_direct"
        if _HAS_RDKIT:
            mol = MolFromInchi(s, sanitize=True)
            if mol:
                result["smiles"] = Chem.MolToSmiles(mol)
        log.info("   -> parsed InChI directly: %s", s[:60])
        return result

    # 2. Try as SMILES (RDKit, suppress parse-error noise)
    if _HAS_RDKIT:
        from rdkit import RDLogger
        _lg = RDLogger.logger()
        _lg.setLevel(RDLogger.ERROR + 1)
        mol = Chem.MolFromSmiles(s, sanitize=True)
        _lg.setLevel(RDLogger.WARNING)
        if mol is not None:
            result["inchi"] = MolToInchi(mol)
            result["smiles"] = Chem.MolToSmiles(mol)
            result["source"] = "smiles_rdkit"
            log.info("   -> parsed SMILES '%s' → InChI=%s",
                     s, (result["inchi"] or "")[:60])
            return result

    # 3. Name → PubChemPy → canonicalize with RDKit
    result = _resolve_via_pubchem(s)
    return result


def _resolve_via_pubchem(name: str) -> dict:
    """Resolve a common chemical name via PubChemPy, canonicalize with RDKit."""
    result = {"inchi": None, "smiles": None, "iupac": None, "source": "none"}
    try:
        import pubchempy as pcp
        compounds = pcp.get_compounds(name, "name")
        if compounds:
            c = compounds[0]
            raw_inchi = getattr(c, "inchi", None)
            raw_smiles = (getattr(c, "connectivity_smiles", None)
                          or getattr(c, "canonical_smiles", None)
                          or getattr(c, "smiles", None))
            result["iupac"] = getattr(c, "iupac_name", None)
            result["source"] = "pubchem"

            if raw_inchi:
                result["inchi"] = _canonicalize_inchi(raw_inchi)
            if raw_smiles:
                result["smiles"] = _canonical_smiles(raw_smiles)
            if not result["inchi"] and result["smiles"]:
                result["inchi"] = _smiles_to_inchi(result["smiles"])

            log.info("   -> PubChem resolved '%s': InChI=%s  SMILES=%s",
                     name,
                     (result["inchi"] or "")[:50],
                     (result["smiles"] or "")[:50])
    except Exception as e:
        log.warning("   -> PubChem lookup failed for '%s': %s", name, e)

    return result


# ── Main resolution function ─────────────────────────────────────────

_LIGAND_RESOLVE_CACHE: dict[str, dict] = {}


def _resolve_ligand_identifiers(name: str) -> dict:
    """Resolve a chemical identifier to canonical InChI (+ SMILES, IUPAC).

    Resolution pipeline (first match wins):
      1. InChI string   → RDKit canonicalize
      2. SMILES string  → RDKit → canonical InChI + SMILES
      3. Common name    → PubChemPy → RDKit canonicalize

    Returns ``{"inchi": str|None, "smiles": str|None, "iupac": str|None}``
    """
    key = name.lower().strip()
    if key in _LIGAND_RESOLVE_CACHE:
        return _LIGAND_RESOLVE_CACHE[key]

    parsed = _parse_chemical_identifier(name)
    result = {k: parsed[k] for k in ("inchi", "smiles", "iupac")}

    _LIGAND_RESOLVE_CACHE[key] = result
    return result
