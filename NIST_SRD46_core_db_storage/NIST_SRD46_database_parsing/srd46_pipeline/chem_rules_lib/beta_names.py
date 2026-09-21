"""Beta definition text repairs and missing source-row recovery (BETA-02)."""
from __future__ import annotations

from typing import Dict
from typing import Tuple
from dataclasses import dataclass
from .registry import Rule, _declare


# =============================================================================
# BETA  beta_definition: text repairs, polymetal tokens, side corrections, unparseable register
# =============================================================================
# pip1a turns each SRD46 beta_definition (HTML sub/sup markup over M/L/H symbols) into a
# balanced species equation. Four hand-made layers sit on top of the tokenizer, applied in
# this order:
#   BETA-02  raw-text repairs BEFORE parsing: typos and ill-formed definitions, each guarded by
#            the exact raw string (a changed raw string -> status 'stale', never a silent apply);
#            plus two beta rows that verkn_ligand_metal references but the dump lacks, filled
#            from the sic table.
#   BETA-04  polymetal HOL tokens the tokenizer needs (Mo7O24 = 7 L - 4 O, ...).
#   BETA-03  equation-side corrections AFTER parsing for definitions the tokenizer cannot
#            balance (solid oxides with L = OH-, vanadate condensation, ...); the verdict of each
#            entry (balanced / unbalanced as written) is recorded and ledgered.
#   BETA-01  the register of ids that still end unparsed ('*'), compared with reality every run.
# History: BETA-02/03/04 were MANUAL_NAME_FIXES / MANUAL_CORRECTIONS / POLYMETAL_HOL_TOKENS in
# pip1a_helpers (manual_corrections.py, constants.py); those modules now re-export from here.
# The original fix notes are kept byte-identical; the repairs added since carry an ``evidence`` string.

# mojibake seen in older exports of the beta text; inert on the current dump (kept as a guard)
BETA02_TEXT_REPLACEMENTS: Tuple[Tuple[str, str], ...] = (("\u00e2\u20ac\u201c", "-"), ("\u00e2\u20ac\u2122", "'"))


@dataclass(frozen=True)
class BetaNameFix:
    raw: str             # exact name_beta_definition of the raw CSV (guard)
    fixed: str           # text handed to the parser instead
    notes: str           # what is wrong and what the repair is
    evidence: str = ""   # how the repair was established (siblings, literature, SRD46 values)


BETA_NAME_FIXES: Dict[int, BetaNameFix] = {
    # ----- original MANUAL_NAME_FIXES: typos in the curated CSV (raw/fixed/notes verbatim) ------------
    280: BetaNameFix(
        raw="[M(OH)<sub>1.5</sub>L<sub>0.5</sub>/[M(OH)<sub>1.5</sub>L<sub>0.5</sub>(s)]",
        fixed="[M(OH)<sub>1.5</sub>L<sub>0.5</sub>]/[M(OH)<sub>1.5</sub>L<sub>0.5</sub>(s)]",
        notes="Missing closing bracket on the numerator species."),
    329: BetaNameFix(
        raw="[M][L]<sup>2</sup>/ML<sub>2</sub>(H<sub>2</sub>O)(s)",
        fixed="[M][L]<sup>2</sup>/[ML<sub>2</sub>(H<sub>2</sub>O)(s)]",
        notes="Denominator solid species lacks concentration brackets."),
    367: BetaNameFix(
        raw="[M<sub>13</sub>O<sub>4</sub>L<sub>24</sub>]/[M]<sup>13</sup></sup>[L]<sup>32</sup>",
        fixed="[M<sub>13</sub>O<sub>4</sub>L<sub>24</sub>]/[M]<sup>13</sup>[L]<sup>32</sup>",
        notes="Stray duplicated </sup> tag. Stoichiometry itself stays unbalanced (see MANUAL_CORRECTIONS[367])."),
    657: BetaNameFix(
        raw="[M<sub>4</sub>(H<sub>-2</sub>L)(H<sub>-1</sub>L)<sub>2</sub>][H]<sup>4</sup>/M<sup>4</sup>4[L]<sup>3</sup>",
        fixed="[M<sub>4</sub>(H<sub>-2</sub>L)(H<sub>-1</sub>L)<sub>2</sub>][H]<sup>4</sup>/[M]<sup>4</sup>[L]<sup>3</sup>",
        notes="Denominator metal term written as 'M<sup>4</sup>4' instead of '[M]<sup>4</sup>'."),
    719: BetaNameFix(
        raw="MH(H<sub>-2</sub>L)(H<sub>-1</sub>L)/M(H<sub>-2</sub>L)(H<sub>-1</sub>L).H",
        fixed="[MH(H<sub>-2</sub>L)(H<sub>-1</sub>L)]/[M(H<sub>-2</sub>L)(H<sub>-1</sub>L)][H]",
        notes="No concentration brackets at all; trailing '.H' means multiplication by [H]."),
    875: BetaNameFix(
        raw="[ML<sub>3</sub>][H]<sup>2</sup>/[M(OH)<sub>4</sub>][H<sub>2</sub>L]<sup></sup>3",
        fixed="[ML<sub>3</sub>][H]<sup>2</sup>/[M(OH)<sub>4</sub>][H<sub>2</sub>L]<sup>3</sup>",
        notes="Exponent 3 placed outside an empty <sup></sup> pair."),
    # ----- ill-formed definitions repaired with sibling / literature evidence ------------------------
    67: BetaNameFix(
        raw="[H<sub>4</sub>M<sub>2</sub>O<sub>7</sub>L]/[H<sub>3</sub>M<sub>2</sub>O<sub>7</sub>][H]",
        fixed="[H<sub>4</sub>M<sub>2</sub>O<sub>7</sub>L]/[H<sub>3</sub>M<sub>2</sub>O<sub>7</sub>L][H]",
        notes="denominator species lacks the ligand: stepwise protonation H3M2O7L + H -> H4M2O7L of the dimeric "
              "vanadate-citrate complex (added L)",
        evidence="Ehde, Andersson & Pettersson, Acta Chem. Scand. 43 (1989) 136 (DOI 10.3891/acta.chem.scand.43-0136): "
                 "log beta(p,q,r) of (H+)p(H2VO4-)q(Cit3-)r = 12.84 (1,2,1), 19.68 (2,2,1) [= SRD46 beta 66], 24.12 (3,2,1); "
                 "SRD46 value 6.84 (VLM 157691) = 19.68 - 12.84 exactly"),
    71: BetaNameFix(
        raw="[H<sub>5</sub>M<sub>2</sub>O<sub>7</sub>L]/[H<sub>4</sub>M<sub>2</sub>O<sub>7</sub>][H]",
        fixed="[H<sub>5</sub>M<sub>2</sub>O<sub>7</sub>L]/[H<sub>4</sub>M<sub>2</sub>O<sub>7</sub>L][H]",
        notes="denominator species lacks the ligand: stepwise protonation H4M2O7L + H -> H5M2O7L (added L)",
        evidence="same paper as 67: SRD46 value 4.44 (VLM 157692) = 24.12 - 19.68 exactly"),
    190: BetaNameFix(
        raw="[M(H<sub>-3</sub>L)L]/[M(OH)(H<sub>-3</sub>L)][H]",
        fixed="[M(H<sub>-3</sub>L)]/[M(OH)(H<sub>-3</sub>L)][H]",
        notes="stray trailing L in the numerator: M(H-3L)L -> M(H-3L); the constant is the protonation of the hydroxo "
              "Cu(III)-peptide complex (M(OH)(H-3L) + H -> M(H-3L) + H2O)",
        evidence="sibling definitions 724 [MH(H-3L)]/[M(H-3L)][H] and 722 use M(H-3L) as the species; SRD46 values 11.4-12.1 "
                 "(Cu3+ / tetra-, penta-, hexaglycine, tetraalanine) match the pKa of the coordinated water in Cu(III)-peptide "
                 "complexes (Neubecker, Kirksey, Chellappa & Margerum, Inorg. Chem. 18 (1979) 444, DOI 10.1021/ic50192a051); "
                 "the only single-token change that balances"),
    346: BetaNameFix(
        raw="[M][L]<sup>2</sup>/[ML<sub>2</sub>.H<sub>2</sub>O(s,schoepite)]",
        fixed="[M][L]<sup>2</sup>/[ML<sub>2</sub>(H<sub>2</sub>O)(s,schoepite)]",
        notes="hydrate dot notation inside the species (same repair as fix 329): ML2.H2O(s,schoepite) -> "
              "ML2(H2O)(s,schoepite); composition unchanged",
        evidence="notation only; parser probe gives the balanced dissolution [ML2(H2O)(s,schoepite)] <=> [M] + [L]^2 + [H2O] "
                 "(329 [ML2(H2O)(s)] and 353 (s,name) show both notations tokenize)"),
    366: BetaNameFix(
        raw="[M<sub>13</sub>O<sub>4</sub>(OH)<sub>24</sub>(H<sub>-1</sub>L)<sub>4</sub>][H]<sup>36</sup>/[M]<sup>13</sup>[HL]<sup>4</sup>",
        fixed="[M<sub>13</sub>O<sub>4</sub>(OH)<sub>24</sub>L<sub>4</sub>][H]<sup>36</sup>/[M]<sup>13</sup>[HL]<sup>4</sup>",
        notes="numerator ligand written as (H-1L)4 although the definition is in the H+/Al3+/HL(lactic acid) component set; "
              "the (-36,13,4) species is Al13O4(OH)24 L4^3+ -> L4",
        evidence="Marklund & Ohman, Acta Chem. Scand. 44 (1990) 228 (DOI 10.3891/acta.chem.scand.44-0228): species "
                 "H-36 Al13 (HL)4^3+, log beta(-36,13,4) = -106.9 in 0.6 M NaCl = SRD46 value exactly; components H+, Al3+, "
                 "HL = lactic acid, so -36 H on 13 Al3+ + 4 HL is Al13O4(OH)24 L4 (the written (H-1L)4 would be (-40,13,4))"),
    495: BetaNameFix(
        raw="[M<sub>2</sub>HL]/[ML<sub>2</sub>][H]",
        fixed="[M<sub>2</sub>HL]/[M<sub>2</sub>L][H]",
        notes="denominator ML2 -> M2L: protonation of the binuclear complex (M2L + H -> M2HL)",
        evidence="sibling definitions of Be2+ / amino(phenyl)methylenediphosphonic acid: ML 16.20, MHL/ML.H 4.50, M2L 23.41; "
                 "no ML2 species is reported and M2HL/ML2.H cannot balance in M; single-token fix"),
    559: BetaNameFix(
        raw="[M<sub>2</sub>O<sub>5</sub>(H<sub>-1</sub>L)<sub>2</sub>]/[(MO<sub>2</sub>(OH)<sub>4</sub>)<sub>2</sub>][L]<sup>2</sup>[H]<sup>2</sup>",
        fixed="[M<sub>2</sub>O<sub>5</sub>(H<sub>-1</sub>L)<sub>2</sub>]/[(MO<sub>2</sub>(OH)<sub>4</sub>)<sub>2</sub>][L]<sup>2</sup>[H]<sup>4</sup>",
        notes="[H]^2 -> [H]^4: condensing two MO2(OH)4 units with two L into M2O5(H-1L)2 releases 7 H2O and needs 4 H+",
        evidence="sibling 560 [M2O5(H-1L)L]/[M2O5(H-1L)2][H] establishes M2O5(H-1L)2 as the species; mass and charge balance "
                 "both require H^4 (554 of the same series stays unresolved: two balanced readings)"),
    593: BetaNameFix(
        raw="[M<sub>3</sub>(H<sub>-1</sub>L)<sub>4</sub>][H]<sup>4</sup>/[M]<sup>3</sup>[L]<sup>5</sup>",
        fixed="[M<sub>3</sub>(H<sub>-1</sub>L)<sub>4</sub>][H]<sup>4</sup>/[M]<sup>3</sup>[L]<sup>4</sup>",
        notes="[L]^5 -> [L]^4: the trinuclear species carries four ligands (M3(H-1L)4)",
        evidence="siblings 374 [M2(H-1L)2][H]^2/[M]^2[L]^2 and 381 use the same H-1L convention with L count = ligands in the "
                 "product; Fe3+/malate polynuclear species (Timberlake, J. Chem. Soc. (1964) 5078); single-token fix"),
    671: BetaNameFix(
        raw="[M<sub>4</sub>L(OH)<sub>2</sub>L<sub>2</sub>][H]<sup>2</sup>/[M]<sup>4</sup>[L]<sup>2</sup>",
        fixed="[M<sub>4</sub>(OH)<sub>2</sub>L<sub>2</sub>][H]<sup>2</sup>/[M]<sup>4</sup>[L]<sup>2</sup>",
        notes="stray leading L in the numerator: M4L(OH)2L2 -> M4(OH)2L2, a hydrolysed dimer of M2L units (M:L = 2:1 as in the denominator)",
        evidence="denominator [M]^4[L]^2 fixes M:L = 2:1 while the written product has L:3; siblings M2L and M2(OH)L of UO2 2+ / "
                 "polymethylenediaminetetraacetates show the (M2L)n(OH)m series; Simoes Goncalves, Almeida Mota & Frausto da Silva, "
                 "Talanta 31 (1984) 531 (DOI 10.1016/0039-9140(84)80134-4) report 2:1 chelates with hydrolysis/polymerisation constants"),
    672: BetaNameFix(
        raw="[M<sub>4</sub>L(OH)<sub>4</sub>L<sub>2</sub>][H]<sup>4</sup>/[M]<sup>4</sup>[L]<sup>2</sup>",
        fixed="[M<sub>4</sub>(OH)<sub>4</sub>L<sub>2</sub>][H]<sup>4</sup>/[M]<sup>4</sup>[L]<sup>2</sup>",
        notes="stray leading L in the numerator: M4L(OH)4L2 -> M4(OH)4L2 (same series as 671)",
        evidence="as 671"),
    701: BetaNameFix(
        raw="[M<sub>6</sub>L(OH)<sub>4</sub>L<sub>3</sub>][H]<sup>4</sup>/[M]<sup>6</sup>[L]<sup>3</sup>",
        fixed="[M<sub>6</sub>(OH)<sub>4</sub>L<sub>3</sub>][H]<sup>4</sup>/[M]<sup>6</sup>[L]<sup>3</sup>",
        notes="stray leading L in the numerator: M6L(OH)4L3 -> M6(OH)4L3 (trimer of M2L units; same series as 671)",
        evidence="as 671 (denominator [M]^6[L]^3 fixes M:L = 2:1)"),
    684: BetaNameFix(
        raw="[M<sub>5</sub>(H<sub>-2</sub>L)(H<sub>-1</sub>L)<sub>3</sub>][H]<sup>4</sup>/[M]<sup>5</sup>[L]<sup>4</sup>",
        fixed="[M<sub>5</sub>(H<sub>-2</sub>L)(H<sub>-1</sub>L)<sub>3</sub>][H]<sup>5</sup>/[M]<sup>5</sup>[L]<sup>4</sup>",
        notes="[H]^4 -> [H]^5: M5(H-2L)(H-1L)3 releases five protons from four L",
        evidence="Johansson, Acta Chem. Scand. A34 (1980) 507 (DOI 10.3891/acta.chem.scand.34a-0507), Table 1: Cu_p T_q H_r "
                 "(5,4,-5) beta = 1.09e4 -> log 4.04 = SRD46 value exactly; (6,4,-7) = sibling 698; the sic dump text reads H5"),
    723: BetaNameFix(
        raw="[MH(H<sub>-2</sub>L)L]/[M(H<sub>-2</sub>L)][H]",
        fixed="[MH(H<sub>-2</sub>L)]/[M(H<sub>-2</sub>L)][H]",
        notes="stray trailing L in the numerator: MH(H-2L)L -> MH(H-2L) (protonation of the M(H-2L) complex)",
        evidence="sibling 729 [MH2(H-2L)]/[MH(H-2L)][H] uses MH(H-2L) as the species, 831 [ML]/[M(H-2L)][H]^2 the parent; "
                 "Ni2+ / GlyGlyHis (Bannister, Raycheba & Margerum, Inorg. Chem. 21 (1982) 1106); single-token fix that balances"),
    932: BetaNameFix(
        raw="[MO<sub>2</sub>(HL)<sub>2</sub>][H]/[HMO<sub>3</sub>L][H<sub>3</sub>L]",
        fixed="[MO<sub>2</sub>(HL)<sub>2</sub>]/[HMO<sub>3</sub>L][H<sub>3</sub>L]",
        notes="stray [H] in the numerator: HMO3L + H3L -> MO2(HL)2 + H2O",
        evidence="siblings 91 [HMO2L2]/[MO4][H3L]^2 and 88 [HMO2(HL)2]/[MO2(HL)2][H] (Mo6+ / pyrogallol; Soni & Bartusek, "
                 "J. Inorg. Nucl. Chem. 33 (1971) 2557) establish MO2(HL)2; the only single-token change that balances"),
    951: BetaNameFix(
        raw="[M(OH)(H<sub>-1</sub>L)]/[M(OH)<sub>2</sub>][HL]",
        fixed="[M(OH)(H<sub>-1</sub>L)][H]/[M(OH)<sub>2</sub>][HL]",
        notes="missing [H] in the numerator: boronic-acid ester formation M(OH)2 + HL -> M(OH)(H-1L) + H (+ H2O) releases a proton",
        evidence="SRD46 values -2.68 / -1.82 / -0.72 (MeB(OH)2, PhB(OH)2, m-NO2PhB(OH)2 with mandelic acid) are negative, i.e. "
                 "K = [ester][H+]/[B(OH)2][HL] as in Babcock & Pizer, Inorg. Chem. 19 (1980) 56; the alternative repair "
                 ".HL -> .L would give positive log K"),
    # ----- explicit-formula definitions (species named by formula instead of M/L/H symbols) ----------
    50: BetaNameFix(
        raw="[H<sub>2</sub>V<sub>10</sub>O<sub>28</sub>][H]<sup>14</sup>/[VO<sub>2</sub><sup>+</sup>]<sup>10</sup>",
        fixed="[H<sub>2</sub>V<sub>10</sub>O<sub>28</sub>][H]<sup>14</sup>/[VO<sub>2</sub>]<sup>10</sup>",
        notes="ionic charge written inside the species bracket (VO2+): the tokenizer knows VO2 (BETA-04) but not a bare '+' "
              "charge mark; decavanadate condensation 10 VO2+ + 8 H2O -> H2V10O28 4- + 14 H+",
        evidence="SRD46 writes species without charge marks everywhere else (sibling 1018 [VO2]/[H2L][H]^2 names the same cation "
                 "VO2); mass and charge balance both hold for the written stoichiometry (+10 = -4 + 14); parser probe gives "
                 "[VO2]^10 + [H2O]^8 <=> [H2V10O28] + [H]^14, element-conserved with the water fix"),
    101: BetaNameFix(
        raw="[I]/[HL][H]",
        fixed="[H<sub>2</sub>L]/[HL][H]",
        notes="product written as the bare iodine(I) cation 'I': in the H+/HOI (HL, ligand 10172) component set the species "
              "I+ (aq) = H2OI+ is H2L (HOI + H+ -> H2OI+); [I] would be counted as the element iodine",
        evidence="only definition of ligand 10172 besides 79 [HL]/[L][H]; SRD46 value log K = 1.54 (VLM 178613, 25 C, I = 0) is "
                 "the protonation constant of hypoiodous acid to H2OI+ (Bell & Gelles, J. Chem. Soc. (1951) 2734, 'the halogen "
                 "cations in aqueous solution', not accessed; pKa(H2OI+) ~ 1.4 in later iodine speciation work) - consistent "
                 "with H2L and with no other M/L/H species; parses and balances without water"),
}
BETA02_LEGACY_IDS: Tuple[int, ...] = (280, 329, 367, 657, 719, 875)   # the six original MANUAL_NAME_FIXES (no evidence string)


@dataclass(frozen=True)
class BetaOrphanRow:
    name: str        # name_beta_definition in the CSV markup, fed to the parser
    sic: str         # verbatim text of beta_definition_sic (the dump's plain-text twin table)
    notes: str
    evidence: str


# verkn_ligand_metal references two beta ids that have no beta_definition row in the dump; the
# plain-text sic table has them. pip1a appends these rows before parsing (ledger status row_filled).
BETA_ORPHAN_ROW_FILLS: Dict[int, BetaOrphanRow] = {
    736: BetaOrphanRow(
        name="[MH<sub>2</sub>L]/[M][H<sub>2</sub>L]", sic="MH2L/M.H2L",
        notes="adduct of the diprotonated ligand: M + H2L -> MH2L",
        evidence="VLM 142041/142053 (Cu2+ + two aminophosphonic acids, log K 7.61/8.92) and 161200 (Fe3+ / m-aminosalicylic "
                 "acid, 3.96); sibling 170 [M(H2L)2]/[M][H2L]^2 uses the same convention; parses and balances"),
    906: BetaOrphanRow(
        name="[ML<sub>5</sub>]/[M(OH)L<sub>5</sub>][H]", sic="ML5/MOHL5.H",
        notes="protonation of the hydroxo-pentaammine: M(OH)L5 + H -> ML5 (+ H2O)",
        evidence="VLM 173312: Co3+ / NH3, log K 6.33 = pKa of [Co(NH3)5(H2O)]3+ (6.2-6.6 in the literature); parses and balances"),
}
_declare(Rule("BETA-02", "pip1a_beta_definition", "beta_definition",
              f"{len(BETA_NAME_FIXES)} raw-text repairs (6 original typo fixes + {len(BETA_NAME_FIXES) - 6} ill-formed definitions "
              f"repaired with evidence) and {len(BETA_ORPHAN_ROW_FILLS)} orphan rows filled from the sic table, before parsing",
              "each repair is guarded by the exact raw string and carries its evidence; the raw text stays in name_beta_definition"))

def beta_name_fixes_legacy() -> Dict[int, Dict[str, str]]:
    """BETA-02 in the shape the pip1a parser consumes (``MANUAL_NAME_FIXES``: id -> raw/fixed/notes)."""
    return {bid: {"raw": f.raw, "fixed": f.fixed, "notes": f.notes} for bid, f in BETA_NAME_FIXES.items()}


__all__ = [
    'BETA02_TEXT_REPLACEMENTS',
    'BetaNameFix',
    'BETA_NAME_FIXES',
    'BETA02_LEGACY_IDS',
    'BetaOrphanRow',
    'BETA_ORPHAN_ROW_FILLS',
    'beta_name_fixes_legacy',
]
