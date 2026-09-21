"""Audited equation-side corrections and their retained history (BETA-03)."""
from __future__ import annotations

from typing import Dict
from typing import Tuple
from dataclasses import dataclass
from .registry import Rule, _declare


# BETA-03: equation-side corrections applied AFTER parsing. Each entry replaces the parsed
# sides (numerator = products, denominator = reactants) of one beta id; ``verdict`` says whether
# the corrected sides conserve elements. Inherited corrections retain their history; primary
# literature revisions carry new evidence. The 14 ids now repaired at text level by BETA-02 are removed from the
# active table and kept in BETA03_SUPERSEDED_BY_BETA02 so their original notes stay readable.
# Explicit-formula repairs: 714 is parsed natively once BETA-04 knows Cr2O7/MCr2O7
# (original entry in BETA03_SUPERSEDED_BY_BETA04); 449 was rewritten from unbalanced to balanced
# (original version in BETA03_REVISED); 461 and 1017 are new balanced entries because the parser's
# formatter prints species powers as int() and the water fix adds integer H2O counts only, so a
# 0.5 coefficient can only be carried by a verbatim equation string here.
# The original entry 529 duplicated the sides of 232 (copy-paste error). Its replacement below
# explicitly expands OH and is supported by Ahrland & Bovin (1974), p.1099; beta529 remains distinct.
# CAUTION on the original notes: their "Metal:/Ligand:/VLM:" annotations were checked against the
# canonical dump; for the 16 historically UNBALANCED entries 366, 367, 495, 507, 554, 559, 593,
# 671, 672, 684, 701, 723, 743, 932, 951, 998 the metal and/or ligand id is WRONG (e.g. 554/559
# are W6+/citrate, not V5+/catechol; 671/672/701 are UO2 2+/polymethylene-dinitrilotetraacetates,
# not Al3+/citrate). The pipeline never reads those annotations; the ``evidence`` strings of
# BETA-02, current literature revisions, and BETA_UNRESOLVED_CANDIDATES supersede those annotations.
BETA03_NOTES_WITH_WRONG_ANNOTATIONS: Tuple[int, ...] = (366, 367, 495, 507, 554, 559, 593, 671, 672, 684, 701, 723, 743, 932, 951, 998)
BALANCED = "balanced"
UNBALANCED = "unbalanced_as_written"


@dataclass(frozen=True)
class BetaCorrection:
    numerator: Tuple[Tuple[str, float], ...]     # (species, coefficient) products
    denominator: Tuple[Tuple[str, float], ...]   # (species, coefficient) reactants
    equation: str                                 # human-readable "reactants <=> products"
    notes: str
    verdict: str                                  # BALANCED | UNBALANCED


BETA_EQUATION_CORRECTIONS: Dict[int, BetaCorrection] = {
    #                      BALANCED CORRECTIONS
    #   verdict BALANCED: the corrected sides conserve every element
    # =========================================================================
    # PEROXOCHROMATE - UNFIXABLE DATA ERROR
    # LHS: Cr⁶⁺ + 2 H₂O₂ = Cr + 4H + 4O
    # RHS: CrO₅ = Cr + 5O
    # Element imbalance: +1O, -4H cannot be balanced with H2O or any species
    # =========================================================================
    # 23: unresolved constant convention for CrO4 2- / H2O2; see BETA_UNRESOLVED_CANDIDATES.
    # =========================================================================
    # SOLID PHASE OXIDE DISSOLUTION (MO(s) + H2O → M + OH)
    # Pattern: Metal oxide solid dissolving in water
    # The solid contains O²⁻ which combines with H₂O to form 2OH⁻
    # CRITICAL: Use [OH] instead of [L] for parser compatibility!
    # =========================================================================
    # [M][L]²/[MO(s)]  where L = OH⁻
    # MO(s) + H2O ⇌ M²⁺ + 2OH⁻
    347: BetaCorrection(
        (("[M]", 1), ("[OH]", 2)),
        (("[MO(s)]", 1), ("[H2O]", 1)),
        "[MO(s)] + [H2O] <=> [M] + [OH]^2",
        "Oxide dissolution: MO(s) + H2O → M²⁺ + 2OH⁻. Metals: [41, 208] (Cu²⁺, Zn²⁺), Ligand: 10076 (OH⁻), VLM: "
        "[170745, 170746, 170958, 170959, 170960, 170961]",
        BALANCED),
    # [M][L]²/[MO(s,red)]
    348: BetaCorrection(
        (("[M]", 1), ("[OH]", 2)),
        (("[MO(s,red)]", 1), ("[H2O]", 1)),
        "[MO(s,red)] + [H2O] <=> [M] + [OH]^2",
        "Red form of MO oxide dissolution. Metals: [71, 125] (Hg²⁺, Pb²⁺), Ligand: 10076 (OH⁻), VLM: [171010, "
        "171011, 171012, 171013, 171101]",
        BALANCED),
    # [M][L]²/[MO(s,yellow)]
    349: BetaCorrection(
        (("[M]", 1), ("[OH]", 2)),
        (("[MO(s,yellow)]", 1), ("[H2O]", 1)),
        "[MO(s,yellow)] + [H2O] <=> [M] + [OH]^2",
        "Yellow form of MO oxide dissolution. Metal: 125 (Pb²⁺), Ligand: 10076 (OH⁻), VLM: [171100]",
        BALANCED),
    # [M][L]⁴/[MO2(s)]
    # MO2(s) + 2H2O ⇌ M⁴⁺ + 4OH⁻
    359: BetaCorrection(
        (("[M]", 1), ("[OH]", 4)),
        (("[MO2(s)]", 1), ("[H2O]", 2)),
        "[MO2(s)] + [H2O]^2 <=> [M] + [OH]^4",
        "Dioxide dissolution: MO2(s) + 2H2O → M⁴⁺ + 4OH⁻. Metals: [70, 116, 185, 209] (Hf⁴⁺, Np⁴⁺, Th⁴⁺, Zr⁴⁺), "
        "Ligand: 10076 (OH⁻), VLM: [170562, 170587, 170844, 170845, 170849]",
        BALANCED),
    # [M][L]⁴/[MO2(s,am)]
    360: BetaCorrection(
        (("[M]", 1), ("[OH]", 4)),
        (("[MO2(s,am)]", 1), ("[H2O]", 2)),
        "[MO2(s,am)] + [H2O]^2 <=> [M] + [OH]^4",
        "Amorphous dioxide dissolution. Metal: 193 (U⁴⁺), Ligand: 10076 (OH⁻), VLM: [170580, 170581, 170582]",
        BALANCED),
    # [M][L]³/[(M2O3)0.5(s)]
    # 0.5 M2O3(s) + 1.5 H2O ⇌ M³⁺ + 3OH⁻
    350: BetaCorrection(
        (("[M]", 1), ("[OH]", 3)),
        (("[(M2O3)0.5(s)]", 1), ("[H2O]", 1.5)),
        "[(M2O3)0.5(s)] + [H2O]^1.5 <=> [M] + [OH]^3",
        "Sesquioxide dissolution (half formula unit). Metals: [74, 190] (In³⁺, Tl³⁺), Ligand: 10076 (OH⁻), VLM: "
        "[171178, 171195, 171196]",
        BALANCED),
    # [M][L]³/[(M2O3)0.5(s,alpha)]
    351: BetaCorrection(
        (("[M]", 1), ("[OH]", 3)),
        (("[(M2O3)0.5(s,alpha)]", 1), ("[H2O]", 1.5)),
        "[(M2O3)0.5(s,alpha)] + [H2O]^1.5 <=> [M] + [OH]^3",
        "Alpha form sesquioxide dissolution. Metal: 61 (Fe³⁺), Ligand: 10076 (OH⁻), VLM: [170828]",
        BALANCED),
    # [M][L]³/[MOL(s)] - this is MOOH(s) where L=OH⁻
    # MOL(s) = MOOH(s), but L is distinct from the O in the solid
    # MOL(s) + H2O ⇌ M³⁺ + L + 2OH⁻ (L from solid + 2OH from O+H2O)
    356: BetaCorrection(
        (("[M]", 1), ("[OH]", 3)),
        (("[MO(OH)(s)]", 1), ("[H2O]", 1)),
        "[MOL(s)] + [H2O] <=> [M] + [L] + [OH]^2",
        "Oxyhydroxide dissolution: MOL(s) + H2O → M³⁺ + L + 2OH⁻. Metals: [64, 169] (Ga³⁺, Sc³⁺), Ligand: 10076 "
        "(OH⁻), VLM: [170437, 170438, 171156]",
        BALANCED),
    # [M][L]³/[MOOH(s,alpha)]
    # MOOH(s) has 1 OH and 1 O, so: MOOH + H2O → M + 3OH
    357: BetaCorrection(
        (("[M]", 1), ("[OH]", 3)),
        (("[MOOH(s,alpha)]", 1), ("[H2O]", 1)),
        "[MOOH(s,alpha)] + [H2O] <=> [M] + [OH]^3",
        "Alpha oxyhydroxide dissolution. Metal: 61 (Fe³⁺), Ligand: 10076 (OH⁻), VLM: [170826, 170827]",
        BALANCED),
    # [M][L]/[(M2O)0.5(s)]
    # 0.5 M2O(s) + 0.5 H2O ⇌ M⁺ + OH⁻
    301: BetaCorrection(
        (("[M]", 1), ("[OH]", 1)),
        (("[(M2O)0.5(s)]", 1), ("[H2O]", 0.5)),
        "[(M2O)0.5(s)] + [H2O]^0.5 <=> [M] + [OH]",
        "Suboxide dissolution (half formula unit). Metals: [2, 42] (Ag⁺, Cu⁺), Ligand: 10076 (OH⁻), VLM: "
        "[170869-170881] (11 records)",
        BALANCED),
    # [M][L]²/[(M2OL2)0.5(s)]
    # This is M2O(OH)2(s) = 0.5 formula unit
    # 0.5 M2O(OH)2(s) + 0.5 H2O ⇌ M + 2OH-
    328: BetaCorrection(
        (("[M]", 1), ("[OH]", 2)),
        (("[(M2O(OH)2)0.5(s)]", 1), ("[H2O]", 0.5)),
        "[(M2OL2)0.5(s)] + [H2O]^0.5 <=> [M] + [L] + [OH]",
        "Mixed oxide-hydroxide dissolution. Metal: 125 (Pb²⁺), Ligand: 10076 (OH⁻), VLM: [171099]",
        BALANCED),
    # [M][L]/[ML(H2O)0.5(s)]
    # ML·0.5H2O(s) ⇌ M + L + 0.5H2O (release of hydration water)
    303: BetaCorrection(
        (("[M]", 1), ("[L]", 1), ("[H2O]", 0.5)),
        (("[ML(H2O)0.5(s)]", 1),),
        "[ML(H2O)0.5(s)] <=> [M] + [L] + [H2O]^0.5",
        "Hydrated solid dissolution releasing water. Metal: 25 (Ca²⁺), Ligand: 10147 (HSO₃⁻), VLM: [175559, "
        "175560, 175561]",
        BALANCED),
    # =========================================================================
    # VANADATE SPECIES - VERIFIED BALANCED
    # V is treated as M in these corrections to achieve balance
    # =========================================================================
    # [(VO3)2L2]/[H2VO4]²[H]²[L]²
    # Vanadate dimer-ligand complex formation
    # V is parsed as element in H2VO4, but as part of polymetal token (VO3)2 in product
    17: BetaCorrection(
        (("[(MO3)2L2]", 1), ("[H2O]", 2)),
        (("[H2MO4]", 2), ("[L]", 2)),
        "[H2MO4]^2 + [L]^2 <=> [(MO3)2L2] + [H2O]^2",
        "Vanadate condensation - V is parsed as element in H2VO4 but as part of polymetal token in (VO3)2L2. "
        "Metal: 197 (V⁵⁺), Ligand: 6434 (L-Alanyl-L-histidine), VLM: [114920]",
        BALANCED),
    # [(VO3)3(HL)2]/[(VO3)2(HL)2][VO3]
    # Vanadate trimer formation from dimer
    18: BetaCorrection(
        (("[(MO3)3(HL)2]", 1), ("[H2O]", 1)),
        (("[(MO3)2(HL)2]", 1), ("[H2MO4]", 1)),
        "[(MO3)2(HL)2] + [H2MO4] <=> [(MO3)3(HL)2] + [H2O]",
        "Vanadate oligomerization - same V parsing inconsistency. Metal: 197 (V⁵⁺), Ligand: 6434 "
        "(L-Alanyl-L-histidine), VLM: [114922]",
        BALANCED),
    # [V2O2(OH)5(H-2L)]/[H2VO4]²[H][L]
    # Divanadate with doubly-deprotonated tartrate. M = VO₂⁺ (2 internal O)
    # V2O2 = M2O-2 (2M has 4 internal O, 2 explicit O = -2 net external), H-2L = doubly deprotonated
    552: BetaCorrection(
        (("[M2O-2(OH)5(H-2L)]", 1), ("[H2O]", 1)),
        (("[H2MO2]", 2), ("[H]", 1), ("[L]", 1)),
        "[H2MO2]^2 + [H] + [L] <=> [M2O-2(OH)5(H-2L)] + [H2O]",
        "Divanadate complex with M = VO₂⁺. H-2L = doubly deprotonated ligand. Metal: 202 (VO₂⁺), Ligand: 8955 "
        "(D-Tartaric acid), VLM: [155049]",
        BALANCED),
    # [V2O4(OH)4L2]/[H2VO4]²[H]²[L]²
    # Divanadate-glycolate complex
    557: BetaCorrection(
        (("[M2(OH)4L2]", 1),),
        (("[H2MO2]", 2), ("[L]", 2)),
        "[H2MO2]^2 + [L]^2 <=> [M2(OH)4L2]",
        "Divanadate-ligand complex - same V parsing inconsistency. Metal: 202 (VO₂⁺), Ligand: 8640 (Glycolic "
        "acid), VLM: [147422]",
        BALANCED),
    # =========================================================================
    # H-nL DEPROTONATED SPECIES (Hydroxide-based equilibria) - VERIFIED
    # M(OH)n + mL ⇌ M(H-xL)y + water
    # =========================================================================
    # [HMO(H-2L)2][H]/[M(OH)4][L]²
    # M(OH)4 + 2L ⇌ HMO(H-2L)2 + H + 3H2O
    85: BetaCorrection(
        (("[HMO(H-2L)2]", 1), ("[H]", 1), ("[H2O]", 3)),
        (("[M(OH)4]", 1), ("[L]", 2)),
        "[M(OH)4] + [L]^2 <=> [HMO(H-2L)2] + [H] + [H2O]^3",
        "Hydroxo-complex ligand exchange with deprotonation. Metal: 66 (Ge⁴⁺), Ligand: [9621..9624] (Diols, 4 "
        "ligands), VLM: [166937..166973] (4 entries)",
        BALANCED),
    # [M(H-2L)2][H]/[M(OH)4][L]²
    # M(OH)4 + 2L ⇌ M(H-2L)2 + 4H2O (no explicit H released!)
    158: BetaCorrection(
        (("[M(H-2L)2]", 1), ("[H2O]", 4)),
        (("[M(OH)4]", 1), ("[L]", 2)),
        "[M(OH)4] + [L]^2 <=> [M(H-2L)2] + [H2O]^4",
        "Complete hydroxide-ligand exchange - H absorbed into H2O. Metal: 66 (Ge⁴⁺), Ligand: 9641/9660/9668 "
        "(Sugars), VLM: [167179, 167346, 167383]",
        BALANCED),
    # [M(OH)(H-2L)][H]/[M(OH)3][L]
    # M(OH)3 + L ⇌ M(OH)(H-2L) + 2H2O (no explicit H released!)
    221: BetaCorrection(
        (("[M(OH)(H-2L)]", 1), ("[H2O]", 2)),
        (("[M(OH)3]", 1), ("[L]", 1)),
        "[M(OH)3] + [L] <=> [M(OH)(H-2L)] + [H2O]^2",
        "Ligand displacement of hydroxide - H absorbed into H2O. Metal: 135 (PhB Phenylborate), Ligand: "
        "[9640..9646] (Pentoses, 7 ligands), VLM: [167165..167237] (7 entries)",
        BALANCED),
    # =========================================================================
    # FRACTIONAL STOICHIOMETRY SOLIDS - VERIFIED
    # =========================================================================
    # [M][OH]^1.5[L]^0.25/[M(OH)1.5L0.25(s)]
    278: BetaCorrection(
        (("[M]", 1), ("[OH]", 1.5), ("[L]", 0.25)),
        (("[M(OH)1.5L0.25(s)]", 1),),
        "[M(OH)1.5L0.25(s)] <=> [M] + [OH]^1.5 + [L]^0.25",
        "Fractional stoichiometry solid - OH and L both present. Metal: 41 (Cu²⁺), Ligand: 10148 (HSO₄⁻), VLM: "
        "[176045..176050] (6 entries)",
        BALANCED),
    279: BetaCorrection(
        (("[M]", 1), ("[OH]", 1.5), ("[L]", 0.5)),
        (("[M(OH)1.5L0.5(s)]", 1),),
        "[M(OH)1.5L0.5(s)] <=> [M] + [OH]^1.5 + [L]^0.5",
        "Fractional stoichiometry solid. Metal: 41 (Cu²⁺), Ligand: 10109 (NO₃⁻), VLM: [173999]",
        BALANCED),
    281: BetaCorrection(
        (("[M]", 1), ("[OH]", 1.7), ("[L]", 0.3)),
        (("[M(OH)1.7L0.3(s)]", 1),),
        "[M(OH)1.7L0.3(s)] <=> [M] + [OH]^1.7 + [L]^0.3",
        "Fractional stoichiometry solid. Metal: 41 (Cu²⁺), Ligand: 10167 (ClO₄⁻), VLM: [177916]",
        BALANCED),
    # =========================================================================
    # DINUCLEAR/POLYNUCLEAR COMPLEXES - VERIFIED
    # =========================================================================
    # [M2(OH)2L2]/[M]^2[L]^2 - product has 2OH, needs H2O hydrolysis
    # 2M + 2L + 2H2O ⇌ M2(OH)2L2 + 2H
    432: BetaCorrection(
        (("[M2(OH)2L2]", 1), ("[H]", 2)),
        (("[M]", 2), ("[L]", 2), ("[H2O]", 2)),
        "[M]^2 + [L]^2 + [H2O]^2 <=> [M2(OH)2L2] + [H]^2",
        "Dinuclear hydroxide complex - water hydrolysis provides OH. Metal: 5 (Al³⁺), Ligand: 9058 (Lactic "
        "acid), VLM: [157813]",
        BALANCED),
    # [M2H2L3]/[M][H]^2[L]^3 - original has M:1, should be M:2
    481: BetaCorrection(
        (("[M2H2L3]", 1),),
        (("[M]", 2), ("[H]", 2), ("[L]", 3)),
        "[M]^2 + [H]^2 + [L]^3 <=> [M2H2L3]",
        "DATA ERROR: Original has M:1 in denominator, should be M:2. Metal: 112 (Ni²⁺), Ligand: 7000 (Triglycine "
        "hydrazide), VLM: [121836]",
        BALANCED),
    # [M2H-3L2]/[ML]^2[OH]^2 - complex equilibrium
    # M2H-3L2 = 2M + 2L - 3H
    # Need: 2ML + 2OH ⇌ M2H-3L2 + H + 2H2O
    485: BetaCorrection(
        (("[M2H-3L2]", 1), ("[H]", 1), ("[H2O]", 2)),
        (("[ML]", 2), ("[OH]", 2)),
        "[ML]^2 + [OH]^2 <=> [M2H-3L2] + [H] + [H2O]^2",
        "Dinuclear deprotonated complex - H2O balance for OH. Metal: 74 (In³⁺), Ligand: 7314 (EDTA), VLM: "
        "[127733]",
        BALANCED),
    # =========================================================================
    # VANADYL TETRAMER COMPLEXES - VERIFIED
    # =========================================================================
    # [V4O4(OH)12L2]/[H2VO4]⁴[H]⁴[L]² - vanadyl tetramer with ligand
    # Chemistry: 4 H₂VO₄⁻ + 4 H⁺ + 2 L → V₄O₄(OH)₁₂L₂ (condensation)
    # Treating VO₂ as M: [M4O-4(OH)12L2] means M:4, O:-4+12=8, H:12, L:2
    # Denom = 4×[H2MO2] + 4×H + 2×L = M:4, H:12, O:8, L:2 ✓
    680: BetaCorrection(
        (("[M4O-4(OH)12L2]", 1),),
        (("[H2MO2]", 4), ("[H]", 4), ("[L]", 2)),
        "[H2MO2]^4 + [H]^4 + [L]^2 <=> [M4O-4(OH)12L2]",
        "Vanadyl tetramer condensation - VO₂ treated as M (Metal: 202 VO₂⁺). Metal: 202 (VO₂⁺), Ligand: 8640 "
        "(Glycolic acid), VLM: [147423]",
        BALANCED),
    # [V4O4(OH)8(H-2L)2]/[H2VO4]⁴[H]⁴[L]² - vanadyl tetramer with deprotonated ligand
    # Chemistry: 4 H₂VO₄⁻ + 4 H⁺ + 2 L → V₄O₄(OH)₈(H₋₂L)₂ + 4 H₂O
    # Treating VO₂ as M: [M4O-4(OH)8(H-2L)2] means M:4, O:-4+8=4, H:8-4=4, L:2
    # Plus 4×H₂O = H:8, O:4 → Total Num = M:4, O:8, H:12, L:2
    # Denom = 4×[H2MO2] + 4×H + 2×L = M:4, H:12, O:8, L:2 ✓
    681: BetaCorrection(
        (("[M4O-4(OH)8(H-2L)2]", 1), ("[H2O]", 4)),
        (("[H2MO2]", 4), ("[H]", 4), ("[L]", 2)),
        "[H2MO2]^4 + [H]^4 + [L]^2 <=> [M4O-4(OH)8(H-2L)2] + [H2O]^4",
        "Vanadyl tetramer with deprotonated ligand - VO₂ treated as M. Metal: 202 (VO₂⁺), Ligand: 8955 "
        "(D-Tartaric acid), VLM: [155050]",
        BALANCED),
    # [ML]/[HVO4][L][H]³ - vanadyl complex
    # Chemistry: HVO₄²⁻ + L + 3H⁺ → VO₂L + 2H₂O ... but VO₂⁺ is M, not ML
    # Actual: HMO4 (= HVO4) → M has O inside it. Product ML means M+L bound.
    # But M = VO₂⁺ already has 2 oxygens! So HMO4 = H + VO₂ + O₂ ? Not quite.
    # Let's treat it as: HVO₄ + L + 3H → (product has V+L) + H₂O
    # If reactant has O:4 and we release 4H as 2H₂O, that uses O:2, leaving O:2
    # Those 2O are in VO₂⁺ (M). So ML = VO₂L contains those 2O.
    # Rewrite: numerator must include O in the product
    829: BetaCorrection(
        (("[ML]", 1), ("[H2O]", 2)),
        (("[HMO2]", 1), ("[L]", 1), ("[H]", 3)),
        "[HMO2] + [L] + [H]^3 <=> [ML] + [H2O]^2",
        "Vanadyl-ligand complex - VO₂ treated as M. HMO₄ + L + 3H → MO₂L + 2H₂O. Metal: 202 (VO₂⁺), Ligands: "
        "[5975, 6140, 6165] (EDDA, MIDA, NTA), VLM: [100453, 104777, 105592]",
        BALANCED),
    # [VO3L]/[H2VO4][L] - vanadate-ligand complex
    # Chemistry: H₂VO₄⁻ + L → VO₃L + H₂O (ligand replaces one OH)
    # Treating V as M: [MO3L] / [H2MO4][L] → MO3L + H2O / H2MO4 + L
    # Balance: Num = M:1, O:3, L:1 + H:2, O:1 = M:1, O:4, H:2, L:1
    #          Denom = M:1, H:2, O:4 + L:1 = M:1, H:2, O:4, L:1 ✓
    1020: BetaCorrection(
        (("[MO3L]", 1), ("[H2O]", 1)),
        (("[H2MO4]", 1), ("[L]", 1)),
        "[H2MO4] + [L] <=> [MO3L] + [H2O]",
        "Vanadate-ligand complex - V treated as M (Metal: 197 V⁵⁺). Metal: 197 (V⁵⁺), Ligand: 6434 "
        "(L-Alanyl-L-histidine), VLM: [114918]",
        BALANCED),
    # =========================================================================
    # ARSENITE DISSOLUTION - VERIFIED BALANCED
    # As4O6 solid dissolves with water to form arsenous acid
    # =========================================================================
    # [H3L]/[(As4O6)0.25(s)] where L = AsO3 (arsenous acid)
    # Dissolution: 0.25 As4O6(s) + 1.5 H2O → H3AsO3
    54: BetaCorrection(
        (("[H3L]", 1),),
        (("[(As4O6)0.25(s)]", 1), ("[H2O]", 1.5)),
        "[(As4O6)0.25(s)] + [H2O]^1.5 <=> [H3L]",
        "Arsenite dissolution: 0.25 As4O6(s) + 1.5 H2O → H3AsO3. Metal: 68 (H⁺), Ligand: 10139 (H₃AsO₃), VLM: "
        "[175309]",
        BALANCED),
    # =========================================================================
    # VANADATE HYDRATED SOLIDS - RELEASE H2O
    # =========================================================================
    # [M]³[VO4]²/[M3(VO4)2(H2O)4(s)]
    # Hydrated vanadate solid dissolution - L = VO4 (from H3VO4 = H3L)
    # Solid releases 4 H2O upon dissolution
    618: BetaCorrection(
        (("[M]", 3), ("[L]", 2), ("[H2O]", 4)),
        (("[M3L2(H2O)4(s)]", 1),),
        "[M3L2(H2O)4(s)] <=> [M]^3 + [L]^2 + [H2O]^4",
        "Hydrated vanadate solid dissolution - releases water of crystallization. Metal: 25 (Ca²⁺), Ligand: "
        "10077 (H₃VO₄), VLM: [177437..177445] (9 entries)",
        BALANCED),
    # [M][V4O12]^0.5/[M(VO3)2(H2O)4(s)]  (L = VO4 from H3VO4 = H3L)
    # Metavanadate tetrahydrate dissolution to half a cyclic tetravanadate: M(VO3)2.4H2O(s) -> M + 0.5 V4O12 + 4 H2O.
    # The raw text parses and balances with the corrected BETA-04 token, but the parser's string formatter prints the
    # 0.5 power as ^0; this entry carries the exact string. Composition check: M(VO3)2(H2O)4 = M + 2 L - 2 O + 8 H + 4 O.
    461: BetaCorrection(
        (("[M]", 1), ("[V4O12]", 0.5), ("[H2O]", 4)),
        (("[M(VO3)2(H2O)4(s)]", 1),),
        "[M(VO3)2(H2O)4(s)] <=> [M] + [V4O12]^0.5 + [H2O]^4",
        "Metavanadate tetrahydrate dissolution as written in SRD46 (half V4O12 per formula unit); balanced with the "
        "corrected BETA-04 token M(VO3)2(H2O)4(s) = {M:1, H:8, O:2, L:2}. Metal: 18, 25, 177 (Ba2+, Ca2+, Sr2+), Ligand: "
        "10077 (H3VO4), VLM: [171374, 171375, 171382, 171383, 171391, 171392] (6 entries, log Ksp -3.66 .. -11.92 at 22 C)",
        BALANCED),
    # [VO2]/[(V2O5)0.5(s)][H]  (L = VO4)
    # Half V2O5 dissolving in acid to the dioxovanadium(V) cation: 0.5 V2O5(s) + H+ -> VO2+ + 0.5 H2O.
    # Needs 0.5 H2O; the water fix adds integer counts only (same situation as entry 54).
    1017: BetaCorrection(
        (("[VO2]", 1), ("[H2O]", 0.5)),
        (("[(V2O5)0.5(s)]", 1), ("[H]", 1)),
        "[(V2O5)0.5(s)] + [H] <=> [VO2] + [H2O]^0.5",
        "V2O5 dissolution to VO2+ as written in SRD46 (half formula unit); balanced with the corrected BETA-04 token "
        "(V2O5)0.5(s) = {H:0, O:-1.5, L:1} (the original token value O:-0.5, L:0.5 was wrong). Metal: 68 (H+), Ligand: 10077 (H3VO4), "
        "VLM: [171296 (log K -0.68, 25 C, I = 0), 171297 (dH), 171298 (dS)]",
        BALANCED),
    # [VOL]/[M][H2L] where L = H2O2 (peroxide), M = VO2+
    # Parser sees H2O2 → {H:4, O:2}, VOL → {M:1, O:1, L:1}
    1021: BetaCorrection(
        (("[MO-1L]", 1), ("[H2O]", 1)),
        (("[M]", 1), ("[H2L]", 1)),
        "[M] + [H2L] <=> [MO-1L] + [H2O]",
        "Peroxovanadate - VO₂⁺ + H₂O₂ → VO(O₂) + H₂O. Metal: 202 (VO₂⁺), Ligand: 10143 (H2O2 Hydrogen peroxide), "
        "VLM: [175376]",
        BALANCED),
    # =========================================================================
    # HYDRATED PHOSPHATE SOLID - VERIFIED
    # =========================================================================
    # [M]⁴[H][L]³/[M4HL3(H2O)2.5(s)]
    # Hydrated phosphate solid - should release H2O
    665: BetaCorrection(
        (("[M]", 4), ("[H]", 1), ("[L]", 3), ("[H2O]", 2.5)),
        (("[M4HL3(H2O)2.5(s)]", 1),),
        "[M4HL3(H2O)2.5(s)] <=> [M]^4 + [H] + [L]^3 + [H2O]^2.5",
        "Hydrated phosphate solid dissolution - releases water of crystallization. Metal: 25 (Ca²⁺), Ligand: "
        "10113 (H₃PO₄), VLM: [174379]",
        BALANCED),
    # =========================================================================
    # SOLID METAL/OXIDE/HYDROXIDE DISSOLUTION - VERIFIED
    # =========================================================================
    # [ML][H]/[M(s)] where L = OH⁻, M = Au(I)
    # Au(s) + H2O ⇌ Au(OH) + H (simplified: solid metal dissolving)
    # Actually: Au(s) dissolves with water to form Au+ + OH- + H+ (net: AuOH + H)
    820: BetaCorrection(
        (("[M]", 1), ("[OH]", 1), ("[H]", 1)),
        (("[M(s)]", 1), ("[H2O]", 1)),
        "[M(s)] + [H2O] <=> [M] + [OH] + [H]",
        "Metal dissolution: M(s) + H2O → M⁺ + OH⁻ + H⁺ (equivalent to ML + H). Metal: 13 (Au⁺), Ligand: 10076 "
        "(OH⁻), VLM: [170883]",
        BALANCED),
    # [ML2][H]²/[M(s)] where L = OH⁻
    # Au(s) + 2H2O ⇌ Au(OH)2⁻ + 2H⁺
    849: BetaCorrection(
        (("[M]", 1), ("[OH]", 2), ("[H]", 2)),
        (("[M(s)]", 1), ("[H2O]", 2)),
        "[M(s)] + [H2O]^2 <=> [M] + [OH]^2 + [H]^2",
        "Metal dissolution: M(s) + 2H2O → M⁺ + 2OH⁻ + 2H⁺ (equivalent to ML2 + H^2). Metal: 13 (Au⁺), Ligand: "
        "10076 (OH⁻), VLM: [170884]",
        BALANCED),
    # [ML2]/[H][(M2O3)0.5(s,cubic)] where L = OH⁻
    857: BetaCorrection(
        (("[M]", 1), ("[OH]", 2)),
        (("[H]", 1), ("[(M2O3)0.5(s,cubic)]", 1), ("[H2O]", 0.5)),
        "[H] + [(M2O3)0.5(s,cubic)] + [H2O]^0.5 <=> [M] + [OH]^2",
        "Sesquioxide dissolution: 0.5 M2O3 + H + 0.5 H2O → M³⁺ + 2OH⁻ (where L=OH⁻). Metal: 167 (Sb³⁺), Ligand: "
        "10076 (OH⁻), VLM: [171205]",
        BALANCED),
    # [ML2]/[H][(M2O3)0.5(s,rhombic)] - same as 857 but rhombic polymorph
    858: BetaCorrection(
        (("[M]", 1), ("[OH]", 2)),
        (("[H]", 1), ("[(M2O3)0.5(s,rhombic)]", 1), ("[H2O]", 0.5)),
        "[H] + [(M2O3)0.5(s,rhombic)] + [H2O]^0.5 <=> [M] + [OH]^2",
        "Sesquioxide dissolution (rhombic): same as 857. Metal: 167 (Sb³⁺), Ligand: 10076 (OH⁻), VLM: [171203, "
        "171204]",
        BALANCED),
    # [ML2]/[MO(s,brown)] where L = OH⁻
    # MO(s) + H2O ⇌ M(OH)2 = ML2
    869: BetaCorrection(
        (("[M]", 1), ("[OH]", 2)),
        (("[MO(s,brown)]", 1), ("[H2O]", 1)),
        "[MO(s,brown)] + [H2O] <=> [M] + [OH]^2",
        "Oxide dissolution: MO(s) + H2O → M²⁺ + 2OH⁻ (equivalent to ML2). Metal: 67 (Ge²⁺), Ligand: 10076 (OH⁻), "
        "VLM: [171014]",
        BALANCED),
    # [ML3]/[(M2O3)0.5(s,alpha)] where L = OH⁻
    # 0.5 M2O3 + 1.5 H2O ⇌ M(OH)3 = ML3
    881: BetaCorrection(
        (("[M]", 1), ("[OH]", 3)),
        (("[(M2O3)0.5(s,alpha)]", 1), ("[H2O]", 1.5)),
        "[(M2O3)0.5(s,alpha)] + [H2O]^1.5 <=> [M] + [OH]^3",
        "Sesquioxide dissolution: 0.5 M2O3 + 1.5 H2O → M³⁺ + 3OH⁻ (equivalent to ML3). Metal: 21 (Bi³⁺), Ligand: "
        "10076 (OH⁻), VLM: [171226, 171227]",
        BALANCED),
    # =========================================================================
    # WILDCARD/EMPTY ENTRY - VERIFIED (trivially balanced)
    # =========================================================================
    # Original definition is just "*" - wildcard/unknown
    19: BetaCorrection(
        (),
        (),
        "1 <=> 1",
        "INVALID: Original definition is '*' - cannot be parsed. Metal: [14..186] (186 metals), Ligand: [5760..] "
        "(2514 ligands), VLM: [94034..183474] (10758 entries)",
        BALANCED),
    # =========================================================================
    # PERIODATE DIMERIZATION: H4L(IO4) = dimeric diperiodate (H4I2O10)
    # L = IO6^5- (orthoperiodate from H5IO6), dimer = H4I2O10 = 2L - 2O + 4H
    # Ref: Buist & Lewis (1965) RSC - "Dimerization of periodate in aqueous solution"
    # Reaction: 2 H3IO6^2- + 2H+ → H4I2O10^2- + 2H2O (acid-catalyzed condensation)
    # =========================================================================
    # [H4L(IO4)]/[H3L][H] — H4L(IO4) is the dimer H4I2O10
    # 2 H3L + 2H → H4I2O10 + 2H2O
    20: BetaCorrection(
        (("[H4I2O10]", 1), ("[H2O]", 2)),
        (("[H3L]", 2), ("[H]", 2)),
        "[H3L]^2 + [H]^2 <=> [H4I2O10] + [H2O]^2",
        "Periodate dimerization: 2 H3IO6^2- + 2H+ → H4I2O10^2- + 2H2O. Metal: 68 (H⁺), Ligand: 10174 (H₅IO₆ "
        "Periodic acid), VLM: [178831-178834]",
        BALANCED),
    # [H5L]/[H4L(IO4)][H] — hydration of dimer back to monomer
    # H4I2O10 + 2H + 2H2O → 2 H5L
    69: BetaCorrection(
        (("[H5L]", 2),),
        (("[H4I2O10]", 1), ("[H]", 2), ("[H2O]", 2)),
        "[H4I2O10] + [H]^2 + [H2O]^2 <=> [H5L]^2",
        "Periodate dimer hydrolysis: H4I2O10^2- + 2H+ + 2H2O → 2 H5IO6. Metal: 68 (H⁺), Ligand: 10174 (H₅IO₆ "
        "Periodic acid), VLM: [178835-178838]",
        BALANCED),
    # [(H4O-2L2)]/[H3L]² — direct dimerization with dehydration
    # 2 H3IO6^2- → H4I2O10^4- + 2H+ (no protons consumed, 2 released)
    # Wait - this should be: 2 H3L → H4I2O10 + 2H2O (lose 2H, gain 2H2O)
    # LHS: H:6, RHS: H:4 + 4 = H:8... need to release 2H
    63: BetaCorrection(
        (("[H4I2O10]", 1), ("[H2O]", 2)),
        (("[H3L]", 2), ("[H]", 2)),
        "[H3L]^2 + [H]^2 <=> [H4I2O10] + [H2O]^2",
        "Periodate dimerization: 2 H3IO6^2- + 2H+ → H4I2O10^4- + 2H2O. Same as β=20 (different VLM entries). "
        "Metal: 68 (H⁺), Ligand: 10174 (H₅IO₆), VLM: [178840..178843] (4 entries)",
        BALANCED),
    # =========================================================================
    # PENTANUCLEAR TARTRATE ISOMERIZATION - VERIFIED BALANCED
    # Fixed bracket typo in original database entry
    # =========================================================================
    # [M5(H-2L)(H-1L)3]/[M5(H-2L)2(H-1L)2][H]
    # Isomerization equilibrium between two protonation states of pentanuclear tartrate
    # Num: M5(H-2L)(H-1L)3 = 5M + (1*-2 + 3*-1)H + 4L = 5M - 5H + 4L
    # Denom: M5(H-2L)2(H-1L)2 + H = 5M + (2*-2 + 2*-1)H + 4L + H = 5M - 6H + 4L + H = 5M - 5H + 4L
    # These should balance! The isomerization converts protonation states.
    685: BetaCorrection(
        (("[M5(H-2L)(H-1L)3]", 1),),
        (("[M5(H-2L)2(H-1L)2]", 1), ("[H]", 1)),
        "[M5(H-2L)2(H-1L)2] + [H] <=> [M5(H-2L)(H-1L)3]",
        "Pentanuclear Cu-tartrate isomerization. Fixed bracket typo in original. Metal: 41 (Cu²⁺), Ligand: 8956 "
        "(meso-Tartaric acid), VLM: [95368]",
        BALANCED),
    # L = OH-: expand the hydroxides explicitly; retain beta 529 as its own definition.
    # Ahrland & Bovin, Acta Chem. Scand. A28 (1974), p. 1099: Kd = 4.8 +/- 0.3,
    # log10(Kd) = 0.681, matching the SRD46 rounded log K 0.7 at I = 5 M, 25 C.
    529: BetaCorrection(
        (("[M2(OH)2]", 1), ("[H2O]", 2)),
        (("[M(OH)2]", 2), ("[H]", 2)),
        "[M(OH)2]^2 + [H]^2 <=> [M2(OH)2] + [H2O]^2",
        "Sb(III) hydroxo dimerization: 2 Sb(OH)2+ + 2 H+ -> Sb2(OH)2^4+ + 2 H2O. "
        "Expand L=OH explicitly without merging beta IDs or changing the stored constant. "
        "Ahrland & Bovin (1974), p. 1099, Kd=4.8 +/- 0.3 at I=5 M: log10(4.8)=0.681 agrees with log K=0.7. "
        "Metal: 167 (Sb3+), ligand: 10076 (OH-). DOI: 10.3891/acta.chem.scand.28a-1089; "
        "https://actachemscand.ki.ku.dk/pdf/acta_vol_28a_p1089-1100.pdf",
        BALANCED),
    # [M(OH)2H(H-2L)]/[M(OH)4][L] - borate complex
    232: BetaCorrection(
        (("[M(OH)2H(H-2L)]", 1),),
        (("[M(OH)4]", 1), ("[L]", 1)),
        "[M(OH)4] + [L] <=> [M(OH)2H(H-2L)]",
        "UNBALANCED: H imbalance cannot be resolved with any H2O coefficient. Metal: 15 (B³⁺), Ligand: 8668 "
        "(D-Gluconic acid), VLM: [149292]",
        UNBALANCED),
    # [M2L][H]^2/[ML][H2L] - product has M2 but reactant has M:1
    507: BetaCorrection(
        (("[M2L]", 1), ("[H]", 2)),
        (("[ML]", 1), ("[H2L]", 1)),
        "[ML] + [H2L] <=> [M2L] + [H]^2",
        "UNBALANCED: M and L counts differ; actual system is MeHg+/meso-DMSA, VLM 156190. "
        "Arnold et al. (1985), DOI 10.1139/v85-402 does not support either candidate with log K -3.6; "
        "see BETA_UNRESOLVED_CANDIDATES and BETA_LITERATURE_REVIEW.md.",
        UNBALANCED),
    # =========================================================================
    # ADDITIONAL UNFIXABLE ENTRIES (ELEMENT PARSING INCONSISTENCIES)
    # These fail because the parser treats certain elements differently
    # when they appear as standalone vs inside polymetal tokens
    # =========================================================================
    # --- CARBONATE GAS EVOLUTION ---
    # [M][CO2(g)]/[H]^6[M3OL(s)] where L = CO3
    # CO2(g) is parsed as {M:1, O:2} but original is carbonate system
    282: BetaCorrection(
        (("[M]", 1), ("[(H0O-1L1)(g)]", 1)),
        (("[H]", 6), ("[M3OL(s)]", 1)),
        "[H]^6 + [M3OL(s)] <=> [M] + [(H0O-1L1)(g)]",
        "UNBALANCED: actual metal 72 is Hg+ (one Hg per M), ligand 10096 (carbonate), VLM 172896. "
        "The NIST mercury review, DOI 10.1063/1.555732, p.661 associates 4.19 with Hg2CO3 dissolution to "
        "Hg2^2+, not M3OL(s). Its accessible transcription has conflicting CO2 phase labels; "
        "see BETA_UNRESOLVED_CANDIDATES before changing the numerical constant convention.",
        UNBALANCED),
    # [M]²[H4L]³[OH]⁴/[M2Si3O8(H2O)(s,sepiolite)]^3.5 where L = H2SiO4 (H4SiO4 = H2L, ligand 10101)
    # rewritten (original unbalanced version in BETA03_REVISED): the record is ill-formed in two places -
    # H4L is H4SiO4 written with its real proton count instead of the ligand convention H2L (siblings 32, 1008-1011
    # use H2L for Si(OH)4), and the "exponent" 3.5 on the solid is the hydration number of sepiolite,
    # Mg4Si6O15(OH)2.6H2O = 2 x Mg2Si3O8.3.5H2O (a pure-solid exponent is void in a solubility product).
    # Dissolution: Mg2Si3O8.3.5H2O(s) + 4.5 H2O -> 2 Mg2+ + 3 Si(OH)4 + 4 OH- (mass and charge balanced).
    449: BetaCorrection(
        (("[M]", 2), ("[H2L]", 3), ("[OH]", 4)),
        (("[M2Si3O8(H2O)3.5(s,sepiolite)]", 1), ("[H2O]", 4.5)),
        "[M2Si3O8(H2O)3.5(s,sepiolite)] + [H2O]^4.5 <=> [M]^2 + [H2L]^3 + [OH]^4",
        "Sepiolite dissolution, written per Mg2Si3O8.3.5H2O formula unit; K = [Mg]^2[H4SiO4]^3[OH]^4 is unchanged by the "
        "rewrite (solid activity 1, water not in the quotient). Balanced with the BETA-04 token "
        "M2Si3O8(H2O)3.5(s,sepiolite) = {M:2, H:1, O:-0.5, L:3}. Evidence: ligand 10101 figure is H2L = H4SiO4, so H4L "
        "cannot be the intended species; 3.5 H2O per Mg2Si3O8 is the accepted sepiolite formula. Metal: 92 (Mg2+), "
        "Ligand: 10101 (H4SiO4), VLM: [173008] (log K -38.8 at 50 C, I = 0)",
        BALANCED),
    # [M13O4L24]/[M]^13[L]^32
    # Product has L:24 but reactant has L:32 - clear L imbalance
    367: BetaCorrection(
        (("[M13O4L24]", 1), ("[H2O]", 8)),
        (("[M]", 13), ("[L]", 32), ("[H]", 16)),
        "[M]^13 + [L]^32 + [H]^16 <=> [M13O4L24] + [H2O]^8",
        "UNBALANCED: Al13 Keggin ion - L stoichiometry mismatch (24 vs 32). Metal: 2 (Al³⁺), Ligand: 10107 "
        "(OH⁻), VLM: [171918]",
        UNBALANCED),
    # [M2O4(H-1L)][H2O]⁴/[(MO2(OH)4)2][L][H]³
    # W(VI)-citrate complex; inherited four-water trial remains unbalanced.
    554: BetaCorrection(
        (("[M2O4(H-1L)]", 1), ("[H2O]", 4)),
        (("[(MO2(OH)4)2]", 1), ("[L]", 1), ("[H]", 3)),
        "[(MO2(OH)4)2] + [L] + [H]^3 <=> [M2O4(H-1L)] + [H2O]^4",
        "UNBALANCED: W(VI)-citrate, metal 204, ligand 9058, VLM 157726-157728. "
        "The 1991 beta214 convention (DOI 10.1039/DT9910001727) does not establish a unique correction "
        "of the 1968 quotient; see BETA_UNRESOLVED_CANDIDATES.",
        UNBALANCED),
    # [MH2L2]/[ML][H]^2: the ML denominator lost its ligand subscript.
    # Dhansay-Linder beta122/beta120 = 10^(28.51-13.20) = 10^15.31.
    743: BetaCorrection(
        (("[MH2L2]", 1),),
        (("[ML2]", 1), ("[H]", 2)),
        "[ML2] + [H]^2 <=> [MH2L2]",
        "Fe(II)-N-(phosphonomethyl)iminodiacetate diprotonation: restore ML -> ML2 in the denominator. "
        "Dhansay & Linder, J. Coord. Chem. 28 (1993) 133-145, DOI 10.1080/00958979308035153: "
        "p.135 defines beta_pqr = [M_p L_q H_r]/([M]^p[L]^q[H]^r); Table I, p.139, ligand 4/Fe2+, "
        "gives log beta122 = 28.51 and log beta120 = 13.20, so log K = 15.31. The alternative ML.L "
        "denominator would give 28.51 - 9.86 = 18.65 and is excluded. Recorded log K is unchanged. "
        "Metal: 62 (Fe2+), Ligand: 6193 (H4L), VLM: [106267], 25 C, I = 0.1 M NaCl. "
        "The original VO2+/tyrosine annotation is preserved only in BETA03_REVISED.",
        BALANCED),
    # [MOL3][H]²/[MOL2][L]
    # Num: {M:1, O:1, L:3} + H:2, Denom: {M:1, O:1, L:2} + L:1 = M:1, O:1, L:3
    # Num - Denom = H:2 extra - cannot balance
    998: BetaCorrection(
        (("[MOL3]", 1), ("[H]", 2)),
        (("[MOL2]", 1), ("[L]", 1)),
        "[MOL2] + [L] <=> [MOL3] + [H]^2",
        "UNBALANCED: two excess product protons; titanium/ligand 9483, VLM 164464. "
        "Sommer (1963), DOI 10.1135/cccc19633057 confirms Ti(IV), but the metal association repair "
        "does not choose among the different balanced quotient candidates.",
        UNBALANCED),
}


BETA03_SUPERSEDED_BY_BETA02: Dict[int, Tuple[str, str]] = {   # id -> (original equation, original notes)
    67: ("[H3M2O7] + [H] <=> [H4M2O7L]",
          "DATA ERROR - L appears in product H4M2O7L but not in reactants H3M2O7 + H. Metal: 197 (V⁵⁺), Ligand: "
          "9058 (Citric acid), VLM: [157691]"),
    71: ("[H4M2O7] + [H] <=> [H5M2O7L]",
          "DATA ERROR - L appears in product H5M2O7L but not in reactants H4M2O7 + H. Metal: 197 (V⁵⁺), Ligand: "
          "9058 (Citric acid), VLM: [157692]"),
    190: ("[M(OH)(H-3L)] + [H] <=> [M(H-3L)L]",
          "UNBALANCED: Product has L:2 (M(H-3L)L) but reactant has L:1 - L imbalance. Metal: 43 (Cu³⁺), Ligand: "
          "[6595..6683] (tetra/penta/hexaglycine, 4 ligands), VLM: [116756..117427] (4 entries)"),
    495: ("[ML2] + [H] <=> [M2HL]",
          "UNBALANCED: M2HL requires 2M but ML2 has only 1M. Metal: 61 (Fe³⁺), Ligand: 10107 (OH⁻), VLM: [171878]"),
    366: ("[M]^13 + [HL]^4 <=> [M13O4(OH)24(H-1L)4] + [H]^36",
          "UNBALANCED: Al13 Keggin ion - stoichiometry complex. Metal: 2 (Al³⁺), Ligand: 5888 (1,2-diaminoethane), "
          "VLM: [95679]"),
    559: ("[(MO2(OH)4)2] + [L]^2 + [H]^2 <=> [M2O5(H-1L)2]",
          "UNBALANCED: Divanadate bis-catecholate - similar to 554. Metal: 197 (V⁵⁺), Ligand: 5706 (Catechol), "
          "VLM: [92259]"),
    593: ("[M]^3 + [L]^5 <=> [M3(H-1L)4] + [H]^4",
          "UNBALANCED: Trinuclear Fe(III) - L stoichiometry mismatch (4 vs 5). Metal: 61 (Fe³⁺), Ligand: 5706 "
          "(Catechol), VLM: [92457]"),
    671: ("[M]^4 + [L]^2 <=> [M4(OH)2L2] + [H]^2",
          "UNBALANCED: Tetranuclear Al - complex formula has L counted twice (L + L2 = L3). Metal: 2 (Al³⁺), "
          "Ligand: 5870 (citric acid), VLM: [95336]"),
    672: ("[M]^4 + [L]^2 <=> [M4(OH)4L2] + [H]^4",
          "UNBALANCED: Tetranuclear Al - similar to 671. Metal: 2 (Al³⁺), Ligand: 5870 (citric acid), VLM: [95338]"),
    684: ("[M]^5 + [L]^4 <=> [M5(H-2L)(H-1L)3] + [H]^4",
          "UNBALANCED: Pentanuclear Al - L balance: (H-2L)+(H-1L)3 = 4L but H balance off. Metal: 2 (Al³⁺), "
          "Ligand: 5870 (citric acid), VLM: [95367]"),
    701: ("[M]^6 + [L]^3 <=> [M6L(OH)4L3] + [H]^4",
          "UNBALANCED: Hexanuclear Al - L stoichiometry mismatch (L+L3=4 vs 3). Metal: 2 (Al³⁺), Ligand: 5870 "
          "(citric acid), VLM: [95441]"),
    723: ("[M(H-2L)] + [H] <=> [MH(H-2L)L]",
          "UNBALANCED: L stoichiometry mismatch (product L:2, reactant L:1). Metal: 42 (Cu²⁺), Ligand: 6140 "
          "(MIDA), VLM: [104781]"),
    932: ("[HMO3L] + [H3L] <=> [MO2(HL)2] + [H]",
          "UNBALANCED: O and H imbalance (-1O, -1H) in molybdate-pyrogallol equilibrium. Adding H2O would "
          "overcorrect. Metal: 103 (Mo⁶⁺), Ligand: 8864 (Pyrogallol), VLM: [152667]"),
    951: ("[M(OH)2] + [HL] <=> [M(OH)(H-1L)]",
          "UNBALANCED: Borate complex has O/H imbalance that cannot be resolved. Metal: 15 (B³⁺), Ligand: 8609 "
          "(D-Galactose), VLM: [146690]"),
}
# original BETA-03 entries made redundant by BETA-04 tokens (the raw text now parses and balances natively):
# id -> (tokens that resolve it, original equation, original notes)
BETA03_SUPERSEDED_BY_BETA04: Dict[int, Tuple[Tuple[str, ...], str, str]] = {
    714: (("Cr2O7", "MCr2O7"), "[M] + [(H0O-1L2)] <=> [MCr2O7]",
          "UNBALANCED: Dichromate - Cr2O7 parsed as polymetal token. Metal: 78 (K⁺), 111 (NH₄⁺), Ligand: 10079 "
          "(H₂CrO₄), VLM: [171460..171465] (6 entries)"),
}
# BETA-03 entries whose active correction was rewritten: id -> (original equation, original notes)
BETA03_REVISED: Dict[int, Tuple[str, str]] = {
    743: ("[ML] + [H]^2 <=> [MH2L2]",
          "UNBALANCED: L stoichiometry mismatch (product L:2, reactant L:1). Metal: 202 (VO₂⁺), Ligand: 9145 "
          "(L-Tyrosine), VLM: [158948]"),
    449: ("[M2Si3O8(H2O)(s,sepiolite)]^3 <=> [M]^2 + [H4L]^3 + [OH]^4",
          "Sepiolite dissolution - Si counted as element in solid but L=H4SiO4. Metal: 92 (Mg²⁺), Ligand: 10101 "
          "(H₄SiO₄), VLM: [173008]"),
}
_declare(Rule("BETA-03", "pip1a_beta_definition", "beta_definition",
              f"{len(BETA_EQUATION_CORRECTIONS)} equation-side corrections after parsing "
              f"({sum(1 for c in BETA_EQUATION_CORRECTIONS.values() if c.verdict == BALANCED)} balanced, "
              f"{sum(1 for c in BETA_EQUATION_CORRECTIONS.values() if c.verdict == UNBALANCED)} unbalanced as written)",
              "solid-oxide dissolution with L = OH-, vanadate/periodate condensation and fractional solids need species the "
              "tokenizer cannot infer; unbalanced entries are kept so the ledger shows what was tried"))

def beta_equation_corrections_legacy() -> Dict[int, Dict[str, object]]:
    """BETA-03 in the shape the pip1a parser consumes (``MANUAL_CORRECTIONS``)."""
    return {bid: {"equation_sides": {"numerator": [[s, c] for s, c in e.numerator],
                                     "denominator": [[s, c] for s, c in e.denominator]},
                  "beta_eq_str_python_final": e.equation, "notes": e.notes}
            for bid, e in BETA_EQUATION_CORRECTIONS.items()}


__all__ = [
    'BETA03_NOTES_WITH_WRONG_ANNOTATIONS',
    'BALANCED',
    'UNBALANCED',
    'BetaCorrection',
    'BETA_EQUATION_CORRECTIONS',
    'BETA03_SUPERSEDED_BY_BETA02',
    'BETA03_SUPERSEDED_BY_BETA04',
    'BETA03_REVISED',
    'beta_equation_corrections_legacy',
]
