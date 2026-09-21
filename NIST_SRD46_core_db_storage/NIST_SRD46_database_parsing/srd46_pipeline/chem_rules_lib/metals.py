"""Metal structure overrides and organic substituent conventions (MET)."""
from __future__ import annotations

from typing import Dict
from typing import Optional
from dataclasses import dataclass
import re
from .registry import Rule, _declare


# =============================================================================
# MET  metal SMILES the formula parser cannot generate
# =============================================================================
# pip1b's ``generate_smiles`` only covers single-element ions; the 70 organometallic / oxo /
# polyatomic "metals" below get their SMILES from this table, keyed by the exact ``name_metal``
# string of the curated metal CSV. pip1b validates every entry with RDKit before use: the sum
# of formal charges must equal the charge parsed from the name and the element counts (with
# explicit H) must equal ``calculate_stoichiometry`` of the parsed components — or the
# ``formula`` override where the parser's Ph = C6H5 expansion is known to be wrong for a
# phenylene bridge. Connectivity is asserted only where the note says so.
@dataclass(frozen=True)
class MetalSmiles:
    smiles: str
    formula: Optional[Dict[str, int]] = None   # element counts incl. H, overrides the parser stoichiometry
    note: str = ""


METAL_SMILES_MANUAL: Dict[str, MetalSmiles] = {
    # actinyl / oxo cations (linear dioxo as written)
    "AmO_[2]^[2+]": MetalSmiles("O=[Am+2]=O"),
    "AmO_[2]^[+]": MetalSmiles("O=[Am+]=O"),
    "NpO_[2]^[2+]": MetalSmiles("O=[Np+2]=O"),
    "NpO_[2]^[+]": MetalSmiles("O=[Np+]=O"),
    "NpO_[3]^[+]": MetalSmiles("O=[Np+](=O)=O"),
    "PuO_[2]^[2+]": MetalSmiles("O=[Pu+2]=O"),
    "PuO_[2]^[+]": MetalSmiles("O=[Pu+]=O"),
    "UO_[2]^[2+]": MetalSmiles("O=[U+2]=O"),
    "UO_[2]^[+]": MetalSmiles("O=[U+]=O"),
    "TcO^[2+]": MetalSmiles("O=[Tc+2]"),
    "TiO^[2+]": MetalSmiles("O=[Ti+2]"),
    "VO^[2+]": MetalSmiles("O=[V+2]"),
    "VO_[2]^[+]": MetalSmiles("O=[V+]=O"),
    "W_[2]O_[4]^[2+]": MetalSmiles("O=[W+]1O[W+](=O)O1",
                                   note="connectivity assumed: di-mu-oxo bridged dioxo-ditungsten; only W2O4 / +2 asserted"),
    "Nb(OH)_[2]^[+]": MetalSmiles("O[Nb+]O", note="as written: niobium with two hydroxo ligands, net +1"),
    # oxo anions / neutral oxides
    "CrO_[4]^[2-]": MetalSmiles("[O-][Cr](=O)(=O)[O-]"),
    "Mo_[2]O_[7]^[2-]": MetalSmiles("[O-][Mo](=O)(=O)O[Mo](=O)(=O)[O-]"),
    "H_[5]TeO_[6]^[-]": MetalSmiles("O[Te](O)(O)(O)(O)[O-]"),
    "OsO_[2]": MetalSmiles("O=[Os]=O"),
    "OsO_[3]": MetalSmiles("O=[Os](=O)=O"),
    "OsO_[4]": MetalSmiles("O=[Os](=O)(=O)=O"),
    "MeReO_[3]": MetalSmiles("C[Re](=O)(=O)=O"),
    # ammonium-type cations
    "NH_[4]^[+]": MetalSmiles("[NH4+]"),
    "MeNH_[3]^[+]": MetalSmiles("C[NH3+]"),
    "EtNH_[3]^[+]": MetalSmiles("CC[NH3+]"),
    "BuNH_[3]^[+]": MetalSmiles("CCCC[NH3+]"),
    "Et_[2]NH_[2]^[+]": MetalSmiles("CC[NH2+]CC"),
    "Et_[3]NH^[+]": MetalSmiles("CC[NH+](CC)CC"),
    "Me_[4]N^[+]": MetalSmiles("C[N+](C)(C)C"),
    "Et_[4]N^[+]": MetalSmiles("CC[N+](CC)(CC)CC"),
    "Pr_[4]N^[+]": MetalSmiles("CCC[N+](CCC)(CCC)CCC"),
    "Bu_[4]N^[+]": MetalSmiles("CCCC[N+](CCCC)(CCCC)CCCC"),
    "CetMe_[3]N^[+]": MetalSmiles("CCCCCCCCCCCCCCCC[N+](C)(C)C", note="Cet = cetyl (n-hexadecyl)"),
    "C(NH_[2])_[3]^[+]": MetalSmiles("NC(N)=[NH2+]", note="guanidinium"),
    # boronic acids (neutral Lewis-acid 'metals')
    "MeB(OH)_[2]": MetalSmiles("CB(O)O"),
    "PhB(OH)_[2]": MetalSmiles("OB(O)c1ccccc1"),
    "m-NO_[2]PhB(OH)_[2]": MetalSmiles("OB(O)c1cccc(c1)[N+](=O)[O-]",
                                       formula={"C": 6, "H": 6, "B": 1, "N": 1, "O": 4},
                                       note="3-nitrophenylboronic acid; Ph is a 1,3-phenylene (C6H4), parser expands Ph as C6H5"),
    # organomercury
    "MeHg^[+]": MetalSmiles("C[Hg+]"),
    "EtHg^[+]": MetalSmiles("CC[Hg+]"),
    "PrHg^[+]": MetalSmiles("CCC[Hg+]"),
    "BuHg^[+]": MetalSmiles("CCCC[Hg+]"),
    "PhHg^[+]": MetalSmiles("[Hg+]c1ccccc1"),
    "O_[3]SPhHg": MetalSmiles("[O-]S(=O)(=O)c1ccc(cc1)[Hg+]",
                              formula={"C": 6, "H": 4, "O": 3, "S": 1, "Hg": 1},
                              note="4-sulfonatophenylmercury(II) zwitterion (para assumed, PCMBS-derived); "
                                   "Ph is a 1,4-phenylene (C6H4), parser expands Ph as C6H5"),
    # organotin
    "MeSn^[3+]": MetalSmiles("C[Sn+3]"),
    "EtSn^[3+]": MetalSmiles("CC[Sn+3]"),
    "Me_[2]Sn^[2+]": MetalSmiles("C[Sn+2]C"),
    "Et_[2]Sn^[2+]": MetalSmiles("CC[Sn+2]CC"),
    "Pr_[2]Sn^[2+]": MetalSmiles("CCC[Sn+2]CCC"),
    "Vy_[2]Sn^[2+]": MetalSmiles("C=C[Sn+2]C=C", note="Vy = vinyl"),
    "Me_[3]Sn^[+]": MetalSmiles("C[Sn+](C)C"),
    "Et_[3]Sn^[+]": MetalSmiles("CC[Sn+](CC)CC"),
    "Pr_[3]Sn^[+]": MetalSmiles("CCC[Sn+](CCC)CCC"),
    "Ph_[3]Sn^[+]": MetalSmiles("c1ccccc1[Sn+](c1ccccc1)c1ccccc1"),
    "ClMe_[2]Sn^[+]": MetalSmiles("C[Sn+](C)Cl"),
    # organolead
    "Me_[2]Pb^[2+]": MetalSmiles("C[Pb+2]C"),
    "Et_[2]Pb^[2+]": MetalSmiles("CC[Pb+2]CC"),
    "Pr_[2]Pb^[2+]": MetalSmiles("CCC[Pb+2]CCC"),
    "Ph_[2]Pb^[2+]": MetalSmiles("c1ccccc1[Pb+2]c1ccccc1"),
    "Me_[3]Pb^[+]": MetalSmiles("C[Pb+](C)C"),
    "Et_[3]Pb^[+]": MetalSmiles("CC[Pb+](CC)CC"),
    "Pr_[3]Pb^[+]": MetalSmiles("CCC[Pb+](CCC)CCC"),
    "Bu_[3]Pb^[+]": MetalSmiles("CCCC[Pb+](CCCC)CCCC"),
    "Ph_[3]Pb^[+]": MetalSmiles("c1ccccc1[Pb+](c1ccccc1)c1ccccc1"),
    # other organometallic / pnictogen cations
    "Me_[2]Au^[+]": MetalSmiles("C[Au+]C"),
    "Me_[2]Ga^[+]": MetalSmiles("C[Ga+]C"),
    "Me_[2]Tl^[+]": MetalSmiles("C[Tl+]C"),
    "Ph_[4]As^[+]": MetalSmiles("c1ccccc1[As+](c1ccccc1)(c1ccccc1)c1ccccc1"),
    "Ph_[4]P^[+]": MetalSmiles("c1ccccc1[P+](c1ccccc1)(c1ccccc1)c1ccccc1"),
    "Ph_[4]Sb^[+]": MetalSmiles("c1ccccc1[Sb+](c1ccccc1)(c1ccccc1)c1ccccc1"),
    "Ph_[3]Sb^[2+]": MetalSmiles("c1ccccc1[Sb+2](c1ccccc1)c1ccccc1"),
}
METAL_SMILES_PARSE_NOTE = "SMILES/InChI from manual rule MET-01 (RDKit-validated against parsed charge and stoichiometry)"
_declare(Rule("MET-01", "pip1b_metal", "metal_augmented",
              f"SMILES/InChI/InChIKey for {len(METAL_SMILES_MANUAL)} polyatomic 'metals' the formula parser leaves empty",
              "generate_smiles() only handles single-element ions; 2,754 complex cards reference these metals"))

_METAL_CHARGE_RE = re.compile(r"\^\[(?P<n>\d*)(?P<sign>[+-])\]\s*$")


def metal_charge_from_name(name_metal: str) -> int:
    """Charge encoded in the ``^[2+]`` / ``^[-]`` markup of a curated metal name (0 if absent)."""
    m = _METAL_CHARGE_RE.search(name_metal)
    if not m:
        return 0
    n = int(m.group("n") or 1)
    return n if m.group("sign") == "+" else -n


# MET-02: organic substituent abbreviations the pip1b formula parser expands to element counts.
# A metal whose base formula contains one of the keys is classified organometallic (the parser
# tests plain substring containment). KNOWN CLASH, kept as the original parser behaviour: the element symbol
# Pr (praseodymium, metal 139 ``Pr^[3+]``) equals the propyl key, so that ion is flagged
# is_organometallic AND is_simple_ion with stoichiometry None (its SMILES ``[Pr+3]`` is still
# right); pip1b ledgers it with status ``suspect_element_clash``.
MET02_ORGANIC_SUBSTITUENTS: Dict[str, str] = {
    "Me": "CH3",      # methyl
    "Et": "C2H5",     # ethyl
    "Pr": "C3H7",     # propyl  (clashes with the element symbol Pr, see above)
    "Bu": "C4H9",     # butyl
    "Ph": "C6H5",     # phenyl
    "Cet": "C16H33",  # cetyl
    "Vy": "C2H3",     # vinyl
}
_declare(Rule("MET-02", "pip1b_metal", "metal_augmented",
              f"{len(MET02_ORGANIC_SUBSTITUENTS)} organic substituent abbreviations (Me, Et, Pr, Bu, Ph, Cet, Vy) drive "
              "organometallic classification and stoichiometry",
              "the curated metal names use these abbreviations (MeHg^[+], Bu_[4]N^[+] ...); the expansion table is a "
              "hand-made convention, not derivable from the dump"))


__all__ = [
    'MetalSmiles',
    'METAL_SMILES_MANUAL',
    'METAL_SMILES_PARSE_NOTE',
    'metal_charge_from_name',
    'MET02_ORGANIC_SUBSTITUENTS',
]
