"""Unresolved beta definitions, source evidence, and orphan references (BETA-01)."""
from __future__ import annotations

from typing import Dict
from typing import Optional
from typing import Tuple
from .registry import Rule, _declare


# BETA-01: ids the parser still leaves unparsed ('*') after BETA-02/03/04, categorised. pip1a
# compares the actual '*' set with this register and ledgers each id as known_unparseable /
# unexpected_unparseable (console warning) / register_stale.
# The former explicit_formula_species category (16 ids naming species by formula,
# e.g. Cr2O7, SiO2(s,quartz), VO2+) is gone - 14 are repaired by BETA-04 tokens + BETA-02 text
# fixes (50, 101) + BETA-03 verbatim equations (449, 461, 1017); 23 and 282 stay unbalanced.
BETA_KNOWN_UNPARSEABLE: Dict[str, Tuple[str, Tuple[int, ...]]] = {
    "unbalanced_as_written": (
        "definition does not balance in M/L/H as written in SRD46 and no single repair is supported by the siblings or the "
        "cited literature (candidates in BETA_UNRESOLVED_CANDIDATES); stored as written, no correction applied",
        (23, 232, 282, 507, 554, 998)),
    "notation_unsupported": (
        "chemically correct as written but needs L = OH- expanded into the O/H count of a polynuclear hydroxo species "
        "(Al13O4(OH)24 Keggin ion), a mapping the tokenizer does not have",
        (367,)),
}
# what was considered for the unresolved ids (kept so the next reader does not redo the search)
BETA_UNRESOLVED_CANDIDATES: Dict[int, str] = {
    23: (
        'CrO4 2-(metal 39)/H2O2, VLM 175377, log K 7.73 (10 C, I=0.1): CrO4 2- + 2 H2O2 + 2 H+ -> CrO5 + '
        '3 H2O balances, but adding denominator H^2 changes the equilibrium convention. Orhanovic & '
        'Wilkins, JACS 89 (1967) 278-282, DOI 10.1021/ja00978a019 remains unavailable. Downloaded '
        'ja00517a026.pdf is a different 1979 arsonated-polystyrene catalysis paper; it supplies no '
        'evidence for this correction.'
    ),
    232: (
        'B3+/D-gluconate, VLM 149292, log K 2.83: adding denominator H, replacing L by HL, or dropping '
        'numerator H defines three different balanced reactions (with water). Lajunen, Hakkinen & '
        'Purokoski, Finn. Chem. Lett. 13 (1986), 21 remains unavailable. The accessible citing abstract '
        'by Verchere & Hlaibi, Polyhedron 6 (1987), 1415-1420, '
        'https://doi.org/10.1016/S0277-5387(00)80903-1 does not define the target gluconate quotient.'
    ),
    282: (
        'Hg+(metal 72)/carbonate, VLM 172896, log K 4.19, I=3: Hietanen & Hogfeldt (1976), Chemica '
        'Scripta 9, 24-29, cited in the NIST mercury review https://doi.org/10.1063/1.555732 p.661, '
        'identifies Hg2CO3(s) and Hg2^2+. The supported species candidate is M2L(s) + 2 H -> M2 + CO2(g) '
        '+ H2O, where M2 is one dimeric ion, not 2 M. However the accessible review transcription pairs '
        '4.19 with CO2(aq) while its introductory equation and numerical cycle 4.19-8.00-9.56=-13.37 '
        'imply CO2(g). The printed table and original paper were unavailable; retain unresolved pending '
        'phase/constant verification. User citation trail: '
        'https://scholar.google.com/scholar?cites=6037701811675621451&as_sdt=400005&sciodt=0,14&hl=en.'
    ),
    507: (
        'MeHg+/meso-DMSA, VLM 156190, log K (-3.6), I=0.5: downloaded Arnold et al., Can. J. Chem. 63 '
        '(1985), 2430, DOI 10.1139/v85-402, pp. 2431-2432 gives log Kf1=18.4, log Kf2=16.9 and '
        'free-ligand pKa=9.42,11.05 at I=0.3 M KNO3. The proposed overall two-metal reaction gives log '
        'K=14.83, and 2 MHL disproportionation gives about 0.97; neither supports -3.6. The approximate '
        'identity -3.6=16.9-9.42-11.05 suggests a stepwise/overall conversion ambiguity, not a unique '
        'repair. Preserve the original value and unresolved quotient.'
    ),
    554: (
        'W6+/citrate, VLM 157726-157728 (log K 31.7, dH -79.5, dS 338.9): H3->H7 with 8 waters or O4->O6 '
        'with 6 waters both balance different reactions. Pyatnitskii & Kravtsova (1968) remains '
        'unavailable. The primary 1991 abstract https://doi.org/10.1039/DT9910001727 reports log '
        'beta214=31.7 for components 2 WO4 2- + Hcit 3- + 4 H+, giving charge -3; neither proposed repair'
        ' matches its proton convention. Equal numerical constants do not establish the conversion from '
        'the 1968 species definition.'
    ),
    998: (
        'Ti/2,3-dihydroxynaphthalene-6-sulfonate, VLM 164464, log K 16.6: denominator L->H2L, '
        "MOL2->MO(HL)2, or removing numerator H^2 defines three different balanced reactions. Sommer's "
        'primary publisher first page https://doi.org/10.1135/cccc19633057 explicitly identifies Ti(IV); '
        "the dump's four-row VLM 164462-164465 block is under Ti(III) 187 while its existing pair "
        'citation (literature 4221, pair-reference 13669) is under Ti(IV) 188. Correcting this source '
        "association does not resolve beta998's quotient. The original numerical table and constant "
        'convention remain unavailable.'
    ),
}
# beta ids referenced by verkn_ligand_metal rows but absent from the beta_definition dump table
# (a fact about the dump; both are filled from the sic table by BETA-02, see BETA_ORPHAN_ROW_FILLS)
BETA_ORPHAN_VERKN_REFS: Dict[int, str] = {
    736: "3 verkn rows reference beta 736; no such beta_definition row in the dump",
    906: "1 verkn row references beta 906; no such beta_definition row in the dump",
}
_declare(Rule("BETA-01", "pip1a_beta_definition", "beta_definition",
              f"{sum(len(v[1]) for v in BETA_KNOWN_UNPARSEABLE.values())} known-unparseable beta ids + "
              f"{len(BETA_ORPHAN_VERKN_REFS)} orphan references are checked and ledgered every run",
              "an unparsed equation that is not in this register is a regression, not a data fact"))


def beta_known_category(beta_id: int) -> Optional[str]:
    for cat, (_, ids) in BETA_KNOWN_UNPARSEABLE.items():
        if beta_id in ids:
            return cat
    return None


__all__ = [
    'BETA_KNOWN_UNPARSEABLE',
    'BETA_UNRESOLVED_CANDIDATES',
    'BETA_ORPHAN_VERKN_REFS',
    'beta_known_category',
]
