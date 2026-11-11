"""micro_valence_calculator.py — Atom-level oxidation-state analysis for organic ligands.

Uses RDKit and Pauling electronegativity to assign formal oxidation states
to every heavy atom in a molecule.  The results feed into the
``LigandMicroValence`` table in the free-energy MD card, enabling the
Pourbaix builder to identify redox-active centres in organic ligands (e.g.
thiol S in cysteine, N in amino-acids, etc.).

If RDKit is not installed the module exposes the same public API but returns
``None`` for any SMILES input.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional, Tuple

try:
    from rdkit import Chem
    _HAS_RDKIT = True
except ImportError:
    _HAS_RDKIT = False

# Pauling electronegativity — exhaustive periodic table
# Ref: https://en.wikipedia.org/wiki/Template:Periodic_table_(electronegativity_by_Pauling_scale)
# Noble gases (He, Ne, Ar) and superheavy elements (Rf–Og) omitted (no accepted values).
# Pm, Eu, Yb have no reliable single value; Pauling gives a range of 1.1–1.2.
_EN: Dict[str, float] = {
    # Period 1
    "H":  2.20,
    # Period 2
    "Li": 0.98, "Be": 1.57, "B":  2.04, "C":  2.55, "N":  3.04,
    "O":  3.44, "F":  3.98,
    # Period 3
    "Na": 0.93, "Mg": 1.31, "Al": 1.61, "Si": 1.90, "P":  2.19,
    "S":  2.58, "Cl": 3.16,
    # Period 4
    "K":  0.82, "Ca": 1.00, "Sc": 1.36, "Ti": 1.54, "V":  1.63,
    "Cr": 1.66, "Mn": 1.55, "Fe": 1.83, "Co": 1.88, "Ni": 1.91,
    "Cu": 1.90, "Zn": 1.65, "Ga": 1.81, "Ge": 2.01, "As": 2.18,
    "Se": 2.55, "Br": 2.96, "Kr": 3.00,
    # Period 5
    "Rb": 0.82, "Sr": 0.95, "Y":  1.22, "Zr": 1.33, "Nb": 1.60,
    "Mo": 2.16, "Tc": 1.90, "Ru": 2.20, "Rh": 2.28, "Pd": 2.20,
    "Ag": 1.93, "Cd": 1.69, "In": 1.78, "Sn": 1.96, "Sb": 2.05,
    "Te": 2.10, "I":  2.66, "Xe": 2.60,
    # Period 6
    "Cs": 0.79, "Ba": 0.89, "Lu": 1.27, "Hf": 1.30, "Ta": 1.50,
    "W":  2.36, "Re": 1.90, "Os": 2.20, "Ir": 2.20, "Pt": 2.28,
    "Au": 2.54, "Hg": 2.00, "Tl": 1.62, "Pb": 1.87, "Bi": 2.02,
    "Po": 2.00, "At": 2.20, "Rn": 2.20,
    # Period 7 (with accepted values)
    "Fr": 0.79, "Ra": 0.90, "Lr": 1.30,
    # Lanthanides
    "La": 1.10, "Ce": 1.12, "Pr": 1.13, "Nd": 1.14, "Pm": 1.15,
    "Sm": 1.17, "Eu": 1.15, "Gd": 1.20, "Tb": 1.21, "Dy": 1.22,
    "Ho": 1.23, "Er": 1.24, "Tm": 1.25, "Yb": 1.15,
    # Actinides
    "Ac": 1.10, "Th": 1.30, "Pa": 1.50, "U":  1.38, "Np": 1.36,
    "Pu": 1.28, "Am": 1.30, "Cm": 1.28, "Bk": 1.30, "Cf": 1.30,
    "Es": 1.30, "Fm": 1.30, "Md": 1.30, "No": 1.30,
}

# Elements considered potentially redox-active in organic ligands.
_DYNAMIC_CANDIDATES = {"C", "N", "S", "P", "Se", "As"}


def compute_atom_oxidation_states(smiles: str) -> Optional[List[Tuple[int, str, int]]]:
    """Assign oxidation states to every heavy atom in *smiles*.

    Returns a list of ``(atom_index, element_symbol, oxidation_state)``
    tuples, or ``None`` if the SMILES is invalid / RDKit unavailable.

    **Algorithm** — electronegativity-partitioned bonding electrons:

    For each atom A with bonds to neighbours Bₖ:

        OS(A)  =  formal_charge(A)
                  + Σ_over_bonds_to_more_electroneg_partner  (n_bond_e / 2)
                  − Σ_over_bonds_to_less_electroneg_partner  (n_bond_e / 2)

    Equal-electronegativity bonds (e.g. C−C) are split evenly and
    contribute zero.
    """
    if not _HAS_RDKIT:
        return None
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    # Add explicit hydrogens so H-bond contributions are counted.
    mol = Chem.AddHs(mol)
    try:
        Chem.Kekulize(mol, clearAromaticFlags=True)
    except Exception:
        pass  # fall back to aromatic representation

    results: List[Tuple[int, str, int]] = []
    for atom in mol.GetAtoms():
        sym = atom.GetSymbol()
        en_self = _EN.get(sym, 2.5)
        os = atom.GetFormalCharge()
        for bond in atom.GetBonds():
            other = bond.GetOtherAtom(atom)
            en_other = _EN.get(other.GetSymbol(), 2.5)
            n_e = int(bond.GetBondTypeAsDouble() * 2)  # 2 for single, 4 for double, …
            half = n_e // 2
            if en_other > en_self:
                os += half      # electrons shift to partner → atom is oxidised
            elif en_other < en_self:
                os -= half      # electrons shift to atom → atom is reduced
        results.append((atom.GetIdx(), sym, os))
    return results


def summarise_oxidation_states(
    smiles: str,
) -> Optional[Tuple[Dict[str, List[int]], List[str]]]:
    """Summarise oxidation states per element and flag dynamic atoms.

    Returns ``(atom_os_summary, dynamic_atoms)`` or ``None``.

    *atom_os_summary* maps element symbol → sorted list of per-atom OS
    values (only heavy atoms, H excluded).

    *dynamic_atoms* lists element symbols that appear with more than one
    distinct OS value **and** are in the ``_DYNAMIC_CANDIDATES`` set.
    """
    raw = compute_atom_oxidation_states(smiles)
    if raw is None:
        return None

    summary: Dict[str, List[int]] = defaultdict(list)
    for _idx, sym, os in raw:
        if sym == "H":
            continue
        summary[sym].append(os)

    # Sort per-element lists for readability
    summary = {k: sorted(v) for k, v in sorted(summary.items())}

    dynamic: List[str] = []
    for sym, os_list in summary.items():
        if sym in _DYNAMIC_CANDIDATES and len(set(os_list)) > 1:
            dynamic.append(sym)
    dynamic.sort()

    return dict(summary), dynamic
