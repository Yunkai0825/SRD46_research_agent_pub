"""Ligand protonation and molfile charge-reconciliation rules (HXL)."""
from __future__ import annotations

from typing import Dict
from typing import Tuple
from dataclasses import dataclass
from .registry import Rule, _declare


# =============================================================================
# HXL  liganden molfile charge reconciliation (pip1c_3, pip3_hxl rules)
# =============================================================================
# pip3_hxl reconciles the molfile charge of each ligand with its HxL figure definition through
# eight rules. Rules 2/2b/3 are algorithmic (cyanide, cyanometalate, XO4/XF6 polyanions) and
# carry no hand-made data. The four below are data-driven and declared here; pip3_hxl imports
# the data from this module. pip1c_3 ledgers each row on which one of them fired (the module's
# ``rules_applied`` / ``correction_applied`` columns say which).
HXL01_COUNTERION_TEMPLATES: Tuple[str, ...] = (
    "[Cl-]", "[Br-]", "[I-]", "[F-]", "[OH-]", "O=[N+]([O-])[O-]", "[O-]N(=O)=O", "[O-]N=O",
    "[O-]S(=O)(=O)[O-]", "OS(=O)(=O)[O-]", "[O-]C(=O)[O-]", "OC(=O)[O-]", "[O-]P(=O)([O-])[O-]",
    "O=P([O-])([O-])O", "OP(=O)(O)[O-]", "[O-]Cl(=O)(=O)=O", "O=[Cl](=O)(=O)[O-]", "F[B-](F)(F)F",
    "F[P-](F)(F)(F)(F)F", "F[As-](F)(F)(F)(F)F", "F[Sb-](F)(F)(F)(F)F", "Cl[Al-](Cl)(Cl)Cl", "F[Al-](F)(F)F",
    "O=S(=O)([O-])C(F)(F)F", "C(F)(F)(F)S(=O)(=O)[O-]", "CS(=O)(=O)[O-]", "CC1=CC=C(C)C(S(=O)(=O)[O-])=C1",
    "CC(=O)[O-]", "[O-]C#N", "[N-]C#S", "S=C=[N-]",
)
_declare(Rule("HXL-01", "pip1c_3_hxl_parse", "liganden_moldata_HxL_parsed",
              f"Rule1: {len(HXL01_COUNTERION_TEMPLATES)} counter-ion SMILES templates removed from multi-fragment molfiles (desalting)",
              "SRD46 molfiles of salts carry the counter-ion; the HxL figure describes the ligand ion alone"))

# Rule4/4b: a ligand whose name carries one of these tokens (or whose formula ends in a charge)
# was drawn as a salt; after desalting the figure charge is harmonised to the remaining cation.
HXL02_DESALTED_CATION_NAME_TOKENS: Tuple[str, ...] = (
    "(nitrate", "(chloride", "(bromide", "(iodide", "(sulfate", "(phosphate",
    "(acetate", "(triflate", "(tosylate", "(mesylate", "(perchlorate",
)
_declare(Rule("HXL-02", "pip1c_3_hxl_parse", "liganden_moldata_HxL_parsed",
              f"Rule4/4b: {len(HXL02_DESALTED_CATION_NAME_TOKENS)} salt-name tokens mark desalted cations whose figure charge is harmonised",
              "the figure definition of a salt entry is written for the neutral salt, not for the cation left after Rule1"))

# Rule5: molblock superatom label -> figure definition (one known entry, hydrogen selenate).
HXL03_SUPERATOM_FIGURES: Dict[str, str] = {"H2SeO4": "H2L"}
_declare(Rule("HXL-03", "pip1c_3_hxl_parse", "liganden_moldata_HxL_parsed",
              "Rule5: figure_definition from the molblock superatom label (H2SeO4 -> H2L)",
              "the molfile is a single superatom, so the HxL parse has nothing else to read"))


# Rule6: two ligands whose figure definition contradicts the molblock charge; identified by
# InChI prefix or a name fragment, the core is pinned and the charge suffix comes from the molblock.
@dataclass(frozen=True)
class PinnedFigure:
    inchi_prefix: str
    name_fragment: str   # lower-case substring of any name column
    core: str            # HxL core the charge suffix is appended to


HXL04_PINNED_FIGURES: Dict[int, PinnedFigure] = {
    6652: PinnedFigure("InChI=1S/C21H28N6O6/", "benzoxymethyl)histidine", "HL"),
    9695: PinnedFigure("InChI=1S/C48H60N12O14/", "hexaoxacyclooctadecane", "L"),
}
_declare(Rule("HXL-04", "pip1c_3_hxl_parse", "liganden_moldata_HxL_parsed",
              f"Rule6: figure core pinned for {len(HXL04_PINNED_FIGURES)} ligands (6652 -> HL, 9695 -> L), charge from the molblock",
              "their stored figure definitions do not match the drawn structure's charge"))


__all__ = [
    'HXL01_COUNTERION_TEMPLATES',
    'HXL02_DESALTED_CATION_NAME_TOKENS',
    'HXL03_SUPERATOM_FIGURES',
    'PinnedFigure',
    'HXL04_PINNED_FIGURES',
]
