"""
Functional-group catalog and RDKit-based substructure filtering.

Provides a named catalog of ~25 coordination-chemistry-relevant functional
groups (as SMARTS patterns) and a post-filter that keeps / removes rows
based on substructure matches.

Public API
----------
``list_functional_groups()``
    Return ``{name: smarts, ...}`` for every group in the catalog.

``filter_by_groups(rows, include, exclude, smiles_key)``
    Apply include / exclude SMARTS filtering to a list of row dicts.
"""

import logging
from typing import Optional

log = logging.getLogger("SRD46")


# ═════════════════════════════════════════════════════════════════════
#  Catalog: name → SMARTS
# ═════════════════════════════════════════════════════════════════════

FUNCTIONAL_GROUP_CATALOG: dict[str, str] = {
    # ── Donor groups (coordination chemistry) ────────────────────
    "carboxyl":        "[CX3](=O)[OX2H1]",
    "carboxylate":     "[CX3](=O)[O-]",
    "primary_amine":   "[NX3;H2;!$(NC=O)]",
    "secondary_amine": "[NX3;H1;!$(NC=O)]",
    "tertiary_amine":  "[NX3;H0;!$(NC=O);!$([nX3])]",
    "hydroxyl":        "[OX2H1;!$(OC=O)]",
    "thiol":           "[SX2H1]",
    "thioether":       "[#16X2;H0;!$([#16]~[!#6])]",
    "phosphate":       "[PX4](=O)([OX2])([OX2])[OX2]",
    "phosphonate":     "[PX4](=O)([OX2])([OX2])[#6]",
    "sulfonate":       "[SX4](=O)(=O)[OX2]",
    "amide":           "[NX3][CX3](=O)",
    "imine":           "[CX3]=[NX2]",
    "nitrile":         "[CX2]#[NX1]",
    "oxime":           "[CX3]=[NX2][OX2H1]",

    # ── Aromatic N-heterocycles ──────────────────────────────────
    "pyridine":        "c1ccncc1",
    "imidazole":       "c1cn[nH]c1",
    "pyrazole":        "c1cc[nH]n1",
    "thiazole":        "c1cscn1",
    "oxazole":         "c1cocn1",

    # ── Other common groups ──────────────────────────────────────
    "phenol":          "[OX2H1]c1ccccc1",
    "ether":           "[OD2;!$(OC=O);!$(Oc)]([#6])[#6]",
    "ester":           "[CX3](=O)[OX2][#6]",
    "ketone":          "[CX3](=O)([#6])[#6]",
    "aldehyde":        "[CX3H1](=O)",
    "nitro":           "[NX3](=O)=O",
    "halide":          "[F,Cl,Br,I]",
    "aromatic_ring":   "a:a",

    # ── Composite biochem motifs ─────────────────────────────────
    "amino_acid":      "[NX3;H2,H1;!$(NC=O)][CX4][CX3](=O)[OX2H1,O-]",
    "peptide_bond":    "[NX3;H1][CX3](=O)[CX4]",
}


# Common synonyms / loose names the agent may emit. Mapped to canonical
# catalog keys above so include_groups=['amino acid'] etc. just works.
_FUNCTIONAL_GROUP_ALIASES: dict[str, str] = {
    "amino":         "primary_amine",
    "amine":         "primary_amine",
    "amines":        "primary_amine",
    "primary_amino": "primary_amine",
    "carboxylic":    "carboxyl",
    "carboxylic_acid": "carboxyl",
    "hydroxy":       "hydroxyl",
    "alcohol":       "hydroxyl",
    "peptide":       "peptide_bond",
    "aminoacid":     "amino_acid",
}


def _normalize_group_key(name: str) -> str:
    """Lowercase + collapse whitespace/hyphens to underscores."""
    return "_".join(name.strip().lower().replace("-", " ").split())


# ═════════════════════════════════════════════════════════════════════
#  Public helpers
# ═════════════════════════════════════════════════════════════════════

def list_functional_groups() -> dict[str, str]:
    """Return ``{name: smarts, ...}`` for every group in the catalog."""
    return dict(FUNCTIONAL_GROUP_CATALOG)


def _resolve_group(name: str) -> tuple[str, str]:
    """Resolve *name* → ``(display_name, smarts)``.

    Lookup order:
      1. Exact catalog hit.
      2. Normalized key (lowercase, spaces/hyphens → underscores) in
         catalog or alias map.
      3. Fall back to treating *name* as a raw SMARTS pattern.
    """
    smarts = FUNCTIONAL_GROUP_CATALOG.get(name)
    if smarts is not None:
        return name, smarts
    key = _normalize_group_key(name)
    smarts = FUNCTIONAL_GROUP_CATALOG.get(key)
    if smarts is not None:
        return key, smarts
    canonical = _FUNCTIONAL_GROUP_ALIASES.get(key)
    if canonical is not None:
        return canonical, FUNCTIONAL_GROUP_CATALOG[canonical]
    return name, name          # assume raw SMARTS


# ═════════════════════════════════════════════════════════════════════
#  Substructure filter
# ═════════════════════════════════════════════════════════════════════

def filter_by_groups(
    rows: list[dict],
    include: Optional[list[str]] = None,
    exclude: Optional[list[str]] = None,
    smiles_key: str = "smiles",
) -> tuple[list[dict], int]:
    """Apply include / exclude functional-group filtering.

    Parameters
    ----------
    rows : list[dict]
        Search result rows; each must have a *smiles_key* field.
    include : list[str] | None
        Group names or raw SMARTS.  A row is kept only if its molecule
        contains **all** of these substructures.
    exclude : list[str] | None
        Group names or raw SMARTS.  A row is excluded if its molecule
        contains **any** of these substructures.
    smiles_key : str
        Dict key that holds the SMILES string (default ``"smiles"``).

    Returns
    -------
    (kept_rows, excluded_count)

    Notes
    -----
    * Rows with missing / unparseable SMILES are **kept** (can't evaluate).
    * Invalid SMARTS patterns are logged and skipped.
    * If RDKit is not installed, filtering is skipped entirely.
    """
    if not include and not exclude:
        return rows, 0

    try:
        from rdkit import Chem          # lazy import
    except ImportError:
        log.warning("RDKit not available — skipping functional-group filtering")
        return rows, 0

    # Compile SMARTS patterns once ────────────────────────────────
    inc_patterns: list[tuple[str, object]] = []
    exc_patterns: list[tuple[str, object]] = []

    for grp_list, pat_list in ((include or [], inc_patterns),
                               (exclude or [], exc_patterns)):
        for name in grp_list:
            display, smarts = _resolve_group(name)
            mol = Chem.MolFromSmarts(smarts)
            if mol is None:
                log.warning(
                    "Invalid functional group %r (resolved to SMARTS %r) — skipped. "
                    "Valid catalog names: %s",
                    display, smarts, ", ".join(sorted(FUNCTIONAL_GROUP_CATALOG)),
                )
                continue
            pat_list.append((display, mol))

    if not inc_patterns and not exc_patterns:
        return rows, 0        # all patterns were invalid → no-op

    # Filter rows ─────────────────────────────────────────────────
    kept: list[dict] = []
    excluded = 0

    for row in rows:
        smi = row.get(smiles_key)
        if not smi:
            kept.append(row)   # no SMILES → can't evaluate → keep
            continue
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            kept.append(row)   # unparseable → keep
            continue

        # Include: must match ALL
        if inc_patterns and not all(mol.HasSubstructMatch(p) for _, p in inc_patterns):
            excluded += 1
            continue

        # Exclude: must match NONE
        if exc_patterns and any(mol.HasSubstructMatch(p) for _, p in exc_patterns):
            excluded += 1
            continue

        kept.append(row)

    return kept, excluded
