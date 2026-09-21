"""Ligand name recovery, pinned structures, stereochemistry, and placeholders (LIG)."""
from __future__ import annotations

from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Sequence
from typing import Tuple
from dataclasses import dataclass
import re
from .registry import Rule, _declare


# =============================================================================
# LIG  ligand name recovery (PubChem)
# =============================================================================
# LIG-01: pip1c_2 recovers a molblock for ligands without a usable molfile (858 '*' ligands)
# by looking the SRD46 name up in PubChem. SRD46 names often carry a trailing parenthetical
# synonym ("...acid (glycine)"), or stereo/racemic prefixes PubChem's name resolver rejects.
# The exact name is always tried first; variants are tried in the order declared below, and
# a hit is recorded with the variant and rule id (RECOVERY_NAME / RECOVERY_SOURCE + ledger).
#
# Guards (each one was added because the unguarded rule produced a WRONG structure for a real
# SRD46 name; the offending names are quoted):
#   * the parenthetical must be preceded by whitespace - "Ethylenediimino-2,2'-bis(3-hydroxy-
#     propanoic acid)", "Cyclo(L-methionyl-L-histidyl)", "Hydrogen manganate(VI)" are one name
#   * an all-caps acronym is not looked up on its own - "(TPHP)" resolves to triphenyl phosphate
#   * counter-ion words are not synonyms - "2-Hydroxy-N,N,N-trimethylanilinium (iodide)"
#   * identity-changing descriptors block both variants - "Hematoxylin (oxidized)" is hematein
#   * a variant hit whose structure has more than one fragment (a salt: dye synonyms resolve to
#     their sodium salts) is rejected and ledgered, the ligand stays a placeholder
#   * LIG01_EXCLUDE_NAMES: names whose SRD46 parenthetical is itself wrong
_LIG_TRAILING_PAREN_RE = re.compile(r"^(?P<head>.*?\S)\s+\((?P<inner>[^()]+)\)\s*$")
_LIG_NOT_A_SYNONYM_RE = re.compile(r"^(?:[+\-\u00b1]|\+/-|[RSEZ]|[RS],?[RS]|\d+[+\-]?|[IVX]+|.{1,2})$")
_LIG_ACRONYM_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-\.'/]*$")          # no lowercase letter at all
_LIG_STEREO_PREFIX_RE = re.compile(r"^(?:(?:DL|D|L|threo|erythro|meso|cis|trans|allo)-)+")
LIG01_COUNTER_ION_WORDS = frozenset({
    "iodide", "chloride", "bromide", "fluoride", "nitrate", "sulfate", "sulphate", "perchlorate",
    "acetate", "hydrochloride", "hydrobromide", "sodium salt", "potassium salt", "ammonium salt",
})
LIG01_IDENTITY_DESCRIPTORS = frozenset({
    "oxidized", "oxidised", "reduced", "hydrate", "dihydrate", "anhydrous", "dimer", "trimer", "polymer",
    "oxide", "salt", "ester", "amide", "lactone", "anhydride", "hydrochloride", "sodium", "potassium",
})
LIG01_REJECT_MULTI_FRAGMENT = True
LIG01_EXCLUDE_NAMES: Dict[str, str] = {
    "Carnitine (Vitamine B1)": "SRD46's parenthetical is wrong (carnitine is 'vitamin BT'); PubChem resolves "
                               "'Vitamine B1' to thiamine",
}


def _lig_split(name: str) -> Optional[Tuple[str, str]]:
    m = _LIG_TRAILING_PAREN_RE.match(name.strip())
    if not m:
        return None
    head, inner = m.group("head").strip(), m.group("inner").strip()
    if inner.lower() in LIG01_IDENTITY_DESCRIPTORS:
        return None
    return head, inner


def _lig_paren_inner(name: str) -> Optional[str]:
    split = _lig_split(name)
    if split is None:
        return None
    inner = split[1]
    if (not inner or _LIG_NOT_A_SYNONYM_RE.match(inner) or not re.search(r"[A-Za-z]{3}", inner)
            or _LIG_ACRONYM_RE.match(inner) or inner.lower() in LIG01_COUNTER_ION_WORDS):
        return None
    return inner


def _lig_paren_head(name: str) -> Optional[str]:
    split = _lig_split(name)
    if split is None:
        return None
    head = split[0].rstrip(",;").strip()
    if not head or head.endswith("-") or not re.search(r"[A-Za-z]{3}", head):
        return None                                   # "Glycine, N-(2-)" -> head "Glycine, N-" is not a name
    return head


def _lig_strip_prefix(name: str) -> Optional[str]:
    stripped = _LIG_STEREO_PREFIX_RE.sub("", name.strip())
    return stripped if stripped and stripped != name.strip() else None


LIGAND_NAME_VARIANT_RULES: List[Tuple[str, str, Callable[[str], Optional[str]]]] = [
    ("LIG-01a", "trailing parenthetical taken as the synonym to look up", _lig_paren_inner),
    ("LIG-01b", "trailing parenthetical dropped", _lig_paren_head),
    ("LIG-01c", "stereo/racemic prefix dropped (DL-, D-, L-, threo-, erythro-, meso-, cis-, trans-, allo-)", _lig_strip_prefix),
]
for _rid, _summary, _ in LIGAND_NAME_VARIANT_RULES:
    _declare(Rule(_rid, "pip1c_2_smiles_inchi", "mol_data_enriched",
                  f"PubChem name lookup retried with variant: {_summary}",
                  "SRD46 ligand names carry synonyms/prefixes PubChem's exact-name resolver rejects; "
                  "guards: whitespace before '(', no acronyms/counter-ions/identity descriptors, "
                  "single-fragment structure, LIG01_EXCLUDE_NAMES"))


def ligand_name_variants(name: str) -> List[Tuple[str, str]]:
    """Ordered (variant, rule_id) list for one SRD46 ligand name; the exact name is excluded."""
    base = (name or "").strip()
    if not base or base in LIG01_EXCLUDE_NAMES:
        return []
    seen = {base}
    out: List[Tuple[str, str]] = []
    for rule_id, _, fn in LIGAND_NAME_VARIANT_RULES:
        variant = fn(base)
        if variant and variant not in seen:
            out.append((variant, rule_id))
            seen.add(variant)
    for variant, rule_id in list(out):                    # second order: prefix strip on the parenthetical variants
        if rule_id != "LIG-01c":
            second = _lig_strip_prefix(variant)
            if second and second not in seen:
                out.append((second, f"{rule_id}+LIG-01c"))
                seen.add(second)
    return out


def ligand_variant_source(rule_id: str) -> str:
    """RECOVERY_SOURCE value written for a variant hit."""
    return f"PubChem (name variant {rule_id})"


def ligand_variant_structure_ok(molblock: str) -> Tuple[bool, str]:
    """Structure guard for LIG-01 hits: (accepted, reason). Multi-fragment = salt form -> rejected."""
    from rdkit import Chem   # noqa: WPS433
    mol = Chem.MolFromMolBlock(molblock, sanitize=False)
    if mol is None:
        return False, "RDKit cannot read the recovered molblock"
    n_frag = len(Chem.GetMolFrags(mol))
    if LIG01_REJECT_MULTI_FRAGMENT and n_frag > 1:
        return False, f"{n_frag} disconnected fragments (salt / counter-ion form) - SRD46 ligands are single species"
    return True, ""


# LIG-01d: pinned PubChem lookups. For a few ligands neither the exact SRD46 name nor any
# LIG-01a..c variant resolves (acronym blocked by the guard, one-word name unknown to PubChem,
# or the acronym resolves to a WRONG compound). The entry pins the lookup name AND the expected
# CID and parent formula; a hit that does not match both is rejected (ledgered), never applied.
# Multi-fragment records (salts) are reduced to the largest organic fragment, neutralised, and
# accepted only when the parent formula matches the pin.
@dataclass(frozen=True)
class PinnedLookup:
    ligand_id: str            # SRD46 ligandenID (the pin is keyed by the exact SRD46 name; the id is asserted)
    lookup_name: str          # name sent to PubChem
    cid: int                  # PubChem CID the lookup must return
    parent_formula: str       # molecular formula of the accepted (desalted, neutral) structure
    why: str


LIG01_PINNED_LOOKUPS: Dict[str, PinnedLookup] = {
    "3-(Tris(hydroxymethyl)methylamino)propanesulfonic acid (TAPS)": PinnedLookup(
        "10517", "TAPS", 121591, "C7H17NO6S",
        "acronym blocked by the LIG-01 all-caps guard; 'TAPS' = CID 121591, single fragment, matches the name"),
    "1,8-Dihydroxy-2-(4-sulfophenylazo)naphthalene-3,4-disulfonic acid (SPADNS)": PinnedLookup(
        "11133", "SPADNS", 90221, "C16H12N2O11S3",
        "acronym blocked by the guard; PubChem record is the trisodium salt (4 fragments) -> desalted to the free acid"),
    'Diethylenetrinitrilopentaacetic acid N,N"-bis(methylamide) (DTPA-BMA)': PinnedLookup(
        "6362", "DTPA-BMA", 60755, "C16H29N5O8",
        "accepted ligand (43 accepted VLM rows) without molfile; SRD46 formula C16H21N5O8 is 8 H short of the "
        "named compound (PubChem C16H29N5O8), the SRD46 formula is kept as written"),
    "Diphosphopyridinenucleotide (DPN)": PinnedLookup(
        "10805", "Diphosphopyridine nucleotide", 5892, "C21H27N7O14P2",
        "one-word SRD46 name is unknown to PubChem and the acronym 'DPN' resolves to a WRONG compound "
        "(CID 102614, a bis-hydroxyphenyl propionitrile); DPN = NAD+ (CID 5892)"),
}
_declare(Rule("LIG-01d", "pip1c_2_smiles_inchi", "mol_data_enriched",
              f"{len(LIG01_PINNED_LOOKUPS)} pinned PubChem lookups (name -> CID + parent formula asserted; salts desalted)",
              "names where the exact string and every variant fail or resolve wrongly; each pin was checked against PubChem"))


def ligand_pinned_source() -> str:
    return "PubChem (pinned lookup LIG-01d)"


def desalt_to_parent(molblock: str, expected_formula: str) -> Tuple[Optional[str], str]:
    """Reduce a PubChem molblock to its neutral largest organic fragment.

    Returns ``(parent_molblock, reason)``; ``parent_molblock`` is None when the result does not
    have ``expected_formula``. Single-fragment neutral inputs pass through unchanged (formula checked).
    """
    from rdkit import Chem                                   # noqa: WPS433
    from rdkit.Chem import rdMolDescriptors
    from rdkit.Chem.MolStandardize import rdMolStandardize
    mol = Chem.MolFromMolBlock(molblock)
    if mol is None:
        return None, "RDKit cannot read the recovered molblock"
    n_frag = len(Chem.GetMolFrags(mol))
    if n_frag > 1 or Chem.GetFormalCharge(mol) != 0:
        chooser = rdMolStandardize.LargestFragmentChooser(preferOrganic=True)
        mol = rdMolStandardize.Uncharger().uncharge(chooser.choose(mol))
    formula = rdMolDescriptors.CalcMolFormula(mol)
    if formula != expected_formula:
        return None, f"parent formula {formula} != pinned {expected_formula} ({n_frag} fragments in the PubChem record)"
    if not mol.HasProp("_Name") or not mol.GetProp("_Name").strip():
        mol.SetProp("_Name", "parent (LIG-01d)")             # non-empty title line: the wrapped worker modules strip() the block
    return Chem.MolToMolBlock(mol), ("desalted from %d fragments" % n_frag if n_frag > 1 else "single fragment")


# LIG-03: stereoisomer pairs. SRD46 lists threo/erythro, meso/threo and cis/trans isomers as
# separate ligands; LIG-01c drops the prefix, so both members resolve to the same stereo-
# unspecified PubChem record and end up with IDENTICAL InChI/SMILES. The register pins the
# stereo-specific PubChem record for each member (isomeric SMILES + InChIKey checked by
# validate()); the molblock is rebuilt from the SMILES with 2D coordinates so the wedge bonds
# carry the stereo into the V2000 block.
@dataclass(frozen=True)
class StereoStructure:
    name: str                 # exact SRD46 name (asserted against the liganden table)
    cid: int
    smiles: str               # isomeric SMILES of the PubChem record
    inchikey: str             # InChIKey of that record (self-check)
    why: str


LIG03_STEREO_STRUCTURES: Dict[str, StereoStructure] = {
    "10188": StereoStructure("threo-4-Hydroxy-DL-glutamic acid", 192790,
                             "C([C@@H](C(=O)O)N)[C@@H](C(=O)O)O", "HBDWQSHEVMSFGY-HRFVKAFMSA-N",
                             "threo = (2S,4S)/(2R,4R) pair; the (2S,4S) enantiomer stands for the racemate"),
    "10189": StereoStructure("erythro-4-Hydroxy-DL-glutamic acid", 440854,
                             "C([C@@H](C(=O)O)N)[C@H](C(=O)O)O", "HBDWQSHEVMSFGY-STHAYSLISA-N",
                             "erythro = (2S,4R)/(2R,4S) pair; the (2S,4R) enantiomer stands for the racemate"),
    "10211": StereoStructure("meso-2,4-Diaminopentanedioic acid", 10441979,
                             "C([C@H](C(=O)O)N)[C@@H](C(=O)O)N", "LOPLXECQBMXEBQ-WSOKHJQSSA-N",
                             "meso (2R,4S) diaminoglutaric acid"),
    "10212": StereoStructure("threo-2,4-Diaminopentanedioic acid", 10953828,
                             "C([C@@H](C(=O)O)N)[C@@H](C(=O)O)N", "LOPLXECQBMXEBQ-HRFVKAFMSA-N",
                             "threo = (2S,4S)/(2R,4R); the (2S,4S) enantiomer stands for the racemate"),
    "10234": StereoStructure("cis-4-Methylpipecolic acid", 56976029,
                             "C[C@@H]1CCN[C@@H](C1)C(=O)O", "UQHCHLWYGMSPJC-RITPCOANSA-N",
                             "cis (2S,4S) 4-methylpiperidine-2-carboxylic acid; one enantiomer stands for the racemate"),
    "10235": StereoStructure("trans-4-Methylpipecolic acid", 44631639,
                             "C[C@H]1CCN[C@@H](C1)C(=O)O", "UQHCHLWYGMSPJC-WDSKDSINSA-N",
                             "trans (2S,4R) 4-methylpiperidine-2-carboxylic acid; one enantiomer stands for the racemate"),
}
_declare(Rule("LIG-03", "pip1c_2_smiles_inchi", "mol_data_enriched",
              f"{len(LIG03_STEREO_STRUCTURES)} stereoisomer ligands get their stereo-specific PubChem structure",
              "LIG-01c prefix stripping made threo/erythro, meso/threo and cis/trans pairs identical in InChI"))


def ligand_stereo_source() -> str:
    return "PubChem stereo-specific record (LIG-03)"


def stereo_molblock(entry: StereoStructure) -> str:
    """V2000 molblock with wedge bonds from the pinned isomeric SMILES."""
    from rdkit import Chem                                   # noqa: WPS433
    from rdkit.Chem import AllChem
    mol = Chem.MolFromSmiles(entry.smiles)
    if mol is None:
        raise ValueError(f"LIG-03: RDKit cannot parse {entry.smiles!r}")
    mol.SetProp("_Name", f"PubChem CID {entry.cid} (LIG-03)")   # non-empty title line: the wrapped worker modules strip() the block
    AllChem.Compute2DCoords(mol)
    Chem.WedgeMolBonds(mol, mol.GetConformer())
    return Chem.MolToMolBlock(mol)


# LIG-04: ligand-level placeholder rule. 1342 SRD46 ligands are whole-record placeholders
# (figure_definition '***', formula '********', and every VLM row of theirs has constant '*';
# the two sets are identical in the dump). ligand_card has no notes column
# and its schema is frozen (NOTE-01), so the verdict is DERIVED from figure_definition + formula
# (LIGAND_PLACEHOLDER_SQL); pip2c ledgers it per ligand and verify re-checks the invariant
# "placeholder ligands carry no accepted measured row" on every run. The rows stay.
LIGAND_PLACEHOLDER_FIGURE = "***"
_LIGAND_PLACEHOLDER_FORMULA_RE = re.compile(r"^\*+$")
LIGAND_STRUCTURE_PLACEHOLDERS = frozenset({"", "*"})
_declare(Rule("LIG-04", "pip2c_cards", "ligand_card",
              "placeholder ligand := figure_definition '***' AND formula '***...' (derived, ledgered; no column)",
              "1342 whole-record placeholder ligands == the ligands whose VLM rows are all '*'; the rule makes accepted-only diffs possible"))


def ligand_placeholder_fields(figure_definition: object, formula: object, smiles: object) -> List[str]:
    """Names of the placeholder-valued ligand fields (figure_definition / formula / smiles)."""
    out: List[str] = []
    if str(figure_definition or "").strip() == LIGAND_PLACEHOLDER_FIGURE:
        out.append("figure_definition")
    if _LIGAND_PLACEHOLDER_FORMULA_RE.match(str(formula or "").strip()):
        out.append("formula")
    if str(smiles or "").strip() in LIGAND_STRUCTURE_PLACEHOLDERS:
        out.append("smiles")
    return out


def ligand_is_placeholder(fields: Sequence[str]) -> bool:
    """Whole-record placeholder = figure_definition AND formula are placeholders (structure may be PubChem-recovered)."""
    return "figure_definition" in fields and "formula" in fields


# LIG-02: pip1c_4 asks PubChem for IUPAC/common names by SMILES; some SMILES that RDKit
# accepts are rejected by PubChem's standardiser (HTTP 400). For those rows the SRD46 ligand
# name itself is sent to the name endpoint instead. Cached in pubchem_smiles_names_cache
# under the key ``name:<name>``.
LIG02_TRIGGER_SUBSTRING = "HTTP 400"
LIG02_CACHE_PREFIX = "name:"
PUBCHEM_NAME_PROPERTY_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/property/IUPACName,Title/JSON"
_declare(Rule("LIG-02", "pip1c_4_chemical_names", "mol_data_with_names",
              "IUPAC/common name looked up by SRD46 ligand name when the SMILES query returns HTTP 400",
              "PubChem's structure standardiser rejects a few valid SMILES; the name endpoint still resolves them"))


__all__ = [
    'LIG01_COUNTER_ION_WORDS',
    'LIG01_IDENTITY_DESCRIPTORS',
    'LIG01_REJECT_MULTI_FRAGMENT',
    'LIG01_EXCLUDE_NAMES',
    'LIGAND_NAME_VARIANT_RULES',
    'ligand_name_variants',
    'ligand_variant_source',
    'ligand_variant_structure_ok',
    'PinnedLookup',
    'LIG01_PINNED_LOOKUPS',
    'ligand_pinned_source',
    'desalt_to_parent',
    'StereoStructure',
    'LIG03_STEREO_STRUCTURES',
    'ligand_stereo_source',
    'stereo_molblock',
    'LIGAND_PLACEHOLDER_FIGURE',
    'LIGAND_STRUCTURE_PLACEHOLDERS',
    'ligand_placeholder_fields',
    'ligand_is_placeholder',
    'LIG02_TRIGGER_SUBSTRING',
    'LIG02_CACHE_PREFIX',
    'PUBCHEM_NAME_PROPERTY_URL',
]
