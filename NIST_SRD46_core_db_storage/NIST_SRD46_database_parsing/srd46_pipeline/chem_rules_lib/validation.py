"""Cross-family consistency checks and the public rule listing."""
from __future__ import annotations

from typing import Dict
from typing import List
import re
from .beta_corrections import (
    BALANCED,
    BETA03_REVISED,
    BETA03_SUPERSEDED_BY_BETA02,
    BETA03_SUPERSEDED_BY_BETA04,
    BETA_EQUATION_CORRECTIONS,
    UNBALANCED,
)
from .beta_names import BETA02_LEGACY_IDS, BETA_NAME_FIXES, BETA_ORPHAN_ROW_FILLS
from .beta_unresolved import BETA_KNOWN_UNPARSEABLE, BETA_ORPHAN_VERKN_REFS, BETA_UNRESOLVED_CANDIDATES
from .beta_tokens import BETA_POLYMETAL_HOL_TOKENS
from .hxl import HXL01_COUNTERION_TEMPLATES, HXL04_PINNED_FIGURES
from .ligands import (
    LIG01_EXCLUDE_NAMES,
    LIG01_PINNED_LOOKUPS,
    LIG03_STEREO_STRUCTURES,
    LIGAND_NAME_VARIANT_RULES,
    ligand_is_placeholder,
    ligand_name_variants,
    ligand_placeholder_fields,
    stereo_molblock,
)
from .metals import MET02_ORGANIC_SUBSTITUENTS, METAL_SMILES_MANUAL, metal_charge_from_name
from .measurements import (
    PARSER_NOTES_DOC,
    PARSER_NOTE_PREFIX,
    PLACEHOLDER_NOTE,
    PLACEHOLDER_SPLIT_QUERIES,
    VLM_METAL_CORRECTIONS,
    VLM_SOURCE_FIELDS,
    VLM_SOURCE_REVIEWS,
    VLM_SOURCE_REVIEW_REFERENCES,
    VLM_SOURCE_REVIEW_EQUATION,
    validate_vlm_source_review_rows,
    VLM_TEMPERATURE_SUFFIX,
    parse_parser_notes,
    parse_vlm_number,
    parser_note,
    vlm_parser_notes,
)
from .policies import REF01_HPLUS_METAL_ID, REF01_IONIC_STRENGTH_TOLERANCE_M, REF01_TEMPERATURE_TOLERANCE_C
from .registry import RULES


# =============================================================================
# validate / describe
# =============================================================================
def validate() -> Dict[str, int]:
    """Structural self-check of every declared rule; raises ValueError on the first defect.

    Returns a small summary dict for the start-up banner.
    """
    problems: List[str] = []
    for rid in RULES:
        if not re.match(r"^[A-Z]+-\d{2}[a-z]?$", rid):
            problems.append(f"rule id {rid!r} does not match FAMILY-NN")
    for rid, correction in VLM_METAL_CORRECTIONS.items():
        if set(correction.expected) != set(VLM_SOURCE_FIELDS):
            problems.append(f"VLM-04 {rid}: guard must include all 16 source columns")
        if correction.expected.get("verkn_ligand_metalID") != rid:
            problems.append(f"VLM-04 {rid}: guard record ID differs from rule key")
        if (not correction.metal_id.isdigit() or correction.metal_id == correction.expected.get("metalNr")
                or not correction.evidence):
            problems.append(f"VLM-04 {rid}: missing evidence or invalid/unchanged corrected metal ID")
    if "VLM-05" not in RULES or RULES["VLM-05"].stage != "pip2c_cards":
        problems.append("VLM-05 source review rule missing or declared in wrong stage")
    for rid, review in VLM_SOURCE_REVIEWS.items():
        if set(review.expected) != set(VLM_SOURCE_FIELDS):
            problems.append(f"VLM-05 {rid}: guard must include all 16 source columns")
        if review.expected.get("verkn_ligand_metalID") != rid or not review.note:
            problems.append(f"VLM-05 {rid}: record identity or review evidence missing")
    if not VLM_SOURCE_REVIEWS or not VLM_SOURCE_REVIEW_EQUATION:
        problems.append("VLM-05 source review targets or expected equation missing")
    try:
        validate_vlm_source_review_rows([r.expected for r in VLM_SOURCE_REVIEWS.values()],
                                        VLM_SOURCE_REVIEW_REFERENCES)
        if parse_parser_notes(parser_note("source_convention_review", 1)) != {"source_convention_review": "1"}:
            problems.append("VLM-05 source review parser marker does not round trip")
    except ValueError as exc:
        problems.append(str(exc))
    if any(v is None for v in VLM_TEMPERATURE_SUFFIX.values()):
        problems.append("VLM-03 map has a None value")
    for probe, expect in (("(3.5)", 3.5), ("(-0.25)", -0.25), ("( 12 )", 12.0), ("(1e-3)", 1e-3)):
        val, in_paren, rid, _ = parse_vlm_number("constant", probe)
        if not (in_paren and rid == "VLM-02" and val == expect):
            problems.append(f"VLM-02 regex does not parse {probe!r} -> {val}")
    if parse_vlm_number("constant", "-3.5") != (-3.5, False, None, None):
        problems.append("plain negative constant mis-parsed")
    if parse_vlm_number("temperature", "30tv")[:2] != (30.0, False):
        problems.append("VLM-03 lookup failed")
    if parse_vlm_number("constant", "*")[2] != "VLM-00":
        problems.append("placeholder token must be handled before parse_vlm_number")

    seen_beta: Dict[int, str] = {}
    for cat, (_, ids) in BETA_KNOWN_UNPARSEABLE.items():
        for bid in ids:
            if bid in seen_beta:
                problems.append(f"beta id {bid} listed twice ({seen_beta[bid]} and {cat})")
            seen_beta[bid] = cat
    for bid in BETA_ORPHAN_VERKN_REFS:
        if bid in seen_beta:
            problems.append(f"beta id {bid} is both an orphan reference and a known-unparseable id")
    if set(BETA_ORPHAN_ROW_FILLS) != set(BETA_ORPHAN_VERKN_REFS):
        problems.append("BETA-02 orphan row fills must cover exactly the declared orphan references")
    for bid, fix in BETA_NAME_FIXES.items():
        if fix.raw == fix.fixed:
            problems.append(f"BETA-02 {bid}: fixed text equals raw text")
        if fix.fixed.count("[") != fix.fixed.count("]") or "/" not in fix.fixed:
            problems.append(f"BETA-02 {bid}: fixed text is not a bracketed numerator/denominator expression")
        if bid not in BETA02_LEGACY_IDS and not fix.evidence:
            problems.append(f"BETA-02 {bid}: repair without evidence string")
        if bid in seen_beta and bid != 367:      # 367: original tag repair, still unparseable (notation)
            problems.append(f"BETA-02 {bid}: text repaired AND listed as known-unparseable")
        if bid in BETA_EQUATION_CORRECTIONS and bid != 367:
            problems.append(f"BETA-02 {bid}: also has a BETA-03 side correction (would undo the repair)")
    for bid in BETA03_SUPERSEDED_BY_BETA02:
        if bid in BETA_EQUATION_CORRECTIONS or bid not in BETA_NAME_FIXES:
            problems.append(f"BETA-03 superseded id {bid} must be absent from the active table and present in BETA-02")
    for bid, (tokens, _, _) in BETA03_SUPERSEDED_BY_BETA04.items():
        if bid in BETA_EQUATION_CORRECTIONS or bid in BETA_NAME_FIXES or bid in seen_beta:
            problems.append(f"BETA-03 id {bid} superseded by BETA-04 must not appear in BETA-02/03 or the BETA-01 register")
        for tok in tokens:
            if tok not in BETA_POLYMETAL_HOL_TOKENS:
                problems.append(f"BETA-03 id {bid}: superseding token {tok!r} is not declared in BETA-04")
    for bid, (original_eq, _) in BETA03_REVISED.items():
        if bid not in BETA_EQUATION_CORRECTIONS or BETA_EQUATION_CORRECTIONS[bid].equation == original_eq:
            problems.append(f"BETA-03 revised id {bid} must have an active entry that differs from the original equation")
    for bid, corr in BETA_EQUATION_CORRECTIONS.items():
        if corr.verdict not in (BALANCED, UNBALANCED):
            problems.append(f"BETA-03 {bid}: verdict {corr.verdict!r}")
        if any(c <= 0 for _, c in corr.numerator + corr.denominator):
            problems.append(f"BETA-03 {bid}: non-positive coefficient")
        if corr.verdict == UNBALANCED and bid not in seen_beta:
            problems.append(f"BETA-03 {bid}: unbalanced correction but id not in the BETA-01 register")
        if corr.verdict == BALANCED and bid in seen_beta:
            problems.append(f"BETA-03 {bid}: balanced correction but id still in the BETA-01 register")
    for bid in BETA_UNRESOLVED_CANDIDATES:
        if bid not in seen_beta:
            problems.append(f"BETA-01 candidates listed for {bid} which is not in the register")
    for key, counts in BETA_POLYMETAL_HOL_TOKENS.items():
        if not key.strip() or "L" not in counts:
            problems.append(f"BETA-04 token {key!r} lacks an L count")
    if len({k.lower() for k in BETA_POLYMETAL_HOL_TOKENS}) != len(BETA_POLYMETAL_HOL_TOKENS):
        problems.append("BETA-04 tokens collide case-insensitively (the tokenizer regex is IGNORECASE)")
    if set(MET02_ORGANIC_SUBSTITUENTS) != {"Me", "Et", "Pr", "Bu", "Ph", "Cet", "Vy"}:
        problems.append("MET-02 substituent set changed; pip1b regexes assume these keys")
    if len(set(HXL01_COUNTERION_TEMPLATES)) != len(HXL01_COUNTERION_TEMPLATES):
        problems.append("HXL-01 duplicate counter-ion template")
    for lid, pin in HXL04_PINNED_FIGURES.items():
        if not pin.inchi_prefix.startswith("InChI=1S/") or pin.core not in ("L", "HL", "H2L", "H3L"):
            problems.append(f"HXL-04 {lid}: malformed pin")
    if not (REF01_TEMPERATURE_TOLERANCE_C > 0 and REF01_IONIC_STRENGTH_TOLERANCE_M > 0 and REF01_HPLUS_METAL_ID == 68):
        problems.append("REF-01 policy constants out of range")

    for name, entry in METAL_SMILES_MANUAL.items():
        if not entry.smiles.strip():
            problems.append(f"MET-01 {name!r}: empty SMILES")
        if entry.formula is not None and any(n <= 0 for n in entry.formula.values()):
            problems.append(f"MET-01 {name!r}: non-positive element count in formula override")
    try:
        from rdkit import Chem   # noqa: WPS433
        for name, entry in METAL_SMILES_MANUAL.items():
            mol = Chem.MolFromSmiles(entry.smiles)
            if mol is None:
                problems.append(f"MET-01 {name!r}: RDKit cannot parse SMILES {entry.smiles!r}")
                continue
            q = Chem.GetFormalCharge(mol)
            if q != metal_charge_from_name(name):
                problems.append(f"MET-01 {name!r}: SMILES charge {q} != name charge {metal_charge_from_name(name)}")
    except ImportError:                                  # RDKit absent: pip1b will refuse to apply MET-01
        pass

    variants = ligand_name_variants("DL-2-Aminopropanoic acid (alanine)")
    if [v for v, _ in variants][:3] != ["alanine", "DL-2-Aminopropanoic acid", "2-Aminopropanoic acid (alanine)"]:
        problems.append(f"LIG-01 variant generation changed: {variants}")
    for probe in ("Ethylenediimino-2,2'-bis(3-hydroxypropanoic acid)", "Cyclo(L-methionyl-L-histidyl)",
                  "Hydrogen manganate(VI)", "Hematoxylin (oxidized)", "Carnitine (Vitamine B1)"):
        if ligand_name_variants(probe):
            problems.append(f"LIG-01 guard failed: {probe!r} -> {ligand_name_variants(probe)}")
    if ligand_name_variants("Tetraethylenepentanitriloheptakis(methylenephosphonic acid) (TPHP)") != \
            [("Tetraethylenepentanitriloheptakis(methylenephosphonic acid)", "LIG-01b")]:
        problems.append("LIG-01 acronym guard failed for '(TPHP)'")
    if ligand_name_variants("2-Hydroxy-N,N,N-trimethylanilinium (iodide)") != [("2-Hydroxy-N,N,N-trimethylanilinium", "LIG-01b")]:
        problems.append("LIG-01 counter-ion guard failed for '(iodide)'")
    pin_ids = [p.ligand_id for p in LIG01_PINNED_LOOKUPS.values()]
    if len(set(pin_ids)) != len(pin_ids):
        problems.append("LIG-01d: a ligand id is pinned twice")
    for name in LIG01_PINNED_LOOKUPS:
        if name in LIG03_STEREO_STRUCTURES or name in LIG01_EXCLUDE_NAMES:
            problems.append(f"LIG-01d pin {name!r} collides with another register")
    try:
        from rdkit import Chem   # noqa: WPS433
        keys: Dict[str, str] = {}
        for lid, entry in LIG03_STEREO_STRUCTURES.items():
            mol = Chem.MolFromSmiles(entry.smiles)
            key = Chem.MolToInchiKey(mol) if mol is not None else None
            if key != entry.inchikey:
                problems.append(f"LIG-03 {lid}: InChIKey of SMILES {key} != pinned {entry.inchikey}")
            if key in keys:
                problems.append(f"LIG-03 {lid} and {keys[key]} pin the same structure")
            keys[key or lid] = lid
            if Chem.MolFromMolBlock(stereo_molblock(entry).strip()) is None or \
                    Chem.MolToInchiKey(Chem.MolFromMolBlock(stereo_molblock(entry).strip())) != entry.inchikey:
                problems.append(f"LIG-03 {lid}: rebuilt molblock loses the stereo (or does not survive strip())")
    except ImportError:
        pass
    if ligand_placeholder_fields("***", "********", "*") != ["figure_definition", "formula", "smiles"] or \
            ligand_placeholder_fields("H2L", "C2H4", "CC") or not ligand_is_placeholder(["figure_definition", "formula"]) \
            or ligand_is_placeholder(["smiles"]):
        problems.append("LIG-04 placeholder helpers changed")

    # NOTE-01 round trip on the three row shapes that occur in SRD46
    probes = [
        ({"constant": "*", "temperature": "*", "ionicstrength": "*"}, ["VLM-01"], True, False,
         {"rules": "VLM-01", "placeholder": "1", "constant_raw": "*", "temperature_raw": "*", "ionicstrength_raw": "*"}),
        ({"constant": "(-0.6)", "temperature": "25", "ionicstrength": "0.1"}, ["VLM-02"], False, True,
         {"rules": "VLM-02", "constant_raw": "(-0.6)", "constant_in_parentheses": "1"}),
        ({"constant": "(-29.3)", "temperature": "30tv", "ionicstrength": "1.0"}, ["VLM-02", "VLM-03:temperature"], False, True,
         {"rules": "VLM-02+VLM-03", "constant_raw": "(-29.3)", "constant_in_parentheses": "1", "temperature_raw": "30tv"}),
    ]
    for row, applied, ph, paren, expected in probes:
        tokens = vlm_parser_notes(row, applied, ph, paren)
        notes_value = str(["48"] + tokens)                        # the shape pip2c writes into notes
        if parse_parser_notes(notes_value) != expected or any(not t.startswith(PARSER_NOTE_PREFIX) for t in tokens):
            problems.append(f"NOTE-01 round trip failed for {row}: {tokens} -> {parse_parser_notes(notes_value)}")
        if (PLACEHOLDER_NOTE in notes_value) != ph:
            problems.append(f"NOTE-01 placeholder marker mismatch for {row}")
    if vlm_parser_notes({"constant": "1.5"}, [], False, False) or parse_parser_notes(None) or parse_parser_notes("['48']"):
        problems.append("NOTE-01: rows without rules must carry no parser note")
    for bad in ("a b", "x'y", "1,2", "[3]"):
        try:
            parser_note("constant_raw", bad)
            problems.append(f"NOTE-01: unsafe value {bad!r} accepted")
        except ValueError:
            pass
    if set(PLACEHOLDER_SPLIT_QUERIES) != {"ligand_card", "ligandmetal_card", "ligandmetal_stability_measured"}:
        problems.append("NOTE-01: PLACEHOLDER_SPLIT_QUERIES must cover the three card tables")

    if problems:
        raise ValueError("manual_rules.validate(): " + "; ".join(problems))
    return {"rules": len(RULES), "metal_smiles": len(METAL_SMILES_MANUAL),
            "beta_name_fixes": len(BETA_NAME_FIXES), "beta_orphan_row_fills": len(BETA_ORPHAN_ROW_FILLS),
            "beta_equation_corrections": len(BETA_EQUATION_CORRECTIONS), "beta_polymetal_tokens": len(BETA_POLYMETAL_HOL_TOKENS),
            "beta_known_unparseable": len(seen_beta), "beta_orphan_refs": len(BETA_ORPHAN_VERKN_REFS),
            "hxl_counterion_templates": len(HXL01_COUNTERION_TEMPLATES), "hxl_pinned_figures": len(HXL04_PINNED_FIGURES),
            "ligand_name_variant_rules": len(LIGAND_NAME_VARIANT_RULES),
            "ligand_pinned_lookups": len(LIG01_PINNED_LOOKUPS), "ligand_stereo_structures": len(LIG03_STEREO_STRUCTURES),
            "temperature_suffix_map": len(VLM_TEMPERATURE_SUFFIX),
            "vlm_metal_corrections": len(VLM_METAL_CORRECTIONS),
            "vlm_source_reviews": len(VLM_SOURCE_REVIEWS)}

def describe() -> List[str]:
    """One line per declared rule for the start-up banner / --list-rules, then the NOTE-01 grammar."""
    width = max(len(r.id) for r in RULES.values())
    lines = [f"{r.id:<{width}}  [{r.stage} -> {r.table}]  {r.summary}" for r in sorted(RULES.values(), key=lambda r: r.id)]
    return lines + [""] + PARSER_NOTES_DOC.rstrip("\n").split("\n")


__all__ = [
    'validate',
    'describe',
]
