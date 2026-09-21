"""Explicit species-to-component mappings for beta equations (BETA-04)."""
from __future__ import annotations

from typing import Dict
from .registry import Rule, _declare


# BETA-04: polymetal HOL tokens. The tokenizer counts H, O and L (and M) per species; these
# oxo-cluster formulas are expanded to (H, O, L[, M]) counts relative to n x the base ligand
# (L = the fully deprotonated figure unit of the ligand, see liganden_moldata_HxL_parsed).
# Carried from pip1a_helpers.constants.POLYMETAL_HOL_TOKENS (original comments kept; their
# "beta=" annotations are NOT verified - the ledger rows with status token_used are the record
# of what a token actually resolves). Relative to that original table,
# 8 wrong values were corrected (SO2(g), the three SiO2(s,*) phases, (V2O5)0.5(s), M(VO3)2(H2O)4(s),
# M3(VO4)2(H2O)4(s), CrO5) and 6 tokens added (Cr2O7, MCr2O7, S2O5, GeO2(s,hexagonal),
# GeO2(s,tetragonal), M2Si3O8(H2O)3.5(s,sepiolite)); each row carries its derivation; the tokenizer
# matches a token only at position 0 of a species label or at a token boundary, and the
# water fix adds INTEGER H2O counts only (fractional water needs a BETA-03 entry: 54, 449, 1017).
BETA_POLYMETAL_HOL_TOKENS: Dict[str, Dict[str, float]] = {
    # ─────────────────────────────────────────────────────────────────────────
    # Molybdate clusters (L = MoO4²⁻ from H₂MoO₄, ligand 10080)
    # nL has n×4 = 4n oxygens; Mo_n O_m means excess O = m - 4n
    # ─────────────────────────────────────────────────────────────────────────
    "Mo7O24": {"H": 0, "O": -4, "L": 7},  # 7×4=28, 24-28=-4 | β=49,60,94,945 L=10080 M=68(H⁺)
    "HMo7O24": {"H": 1, "O": -4, "L": 7},  # β=94 (denominator) L=10080 M=68(H⁺)
    "H2Mo7O24": {"H": 2, "O": -4, "L": 7},  # β=49,60 L=10080 M=68(H⁺)
    "H3Mo7O24": {"H": 3, "O": -4, "L": 7},  # β=60 L=10080 M=68(H⁺)
    "Mo6O21": {"H": 0, "O": -3, "L": 6},  # 6×4=24, 21-24=-3 | β=912 L=10080 M=5(Al³⁺)
    "Mo2O7": {"H": 0, "O": -1, "L": 2},  # 2×4=8, 7-8=-1 | (no direct beta, theoretical)
    "HMo2O7": {"H": 1, "O": -1, "L": 2},  # (theoretical, protonated dimolybdate)
    "H2Mo2O7": {"H": 2, "O": -1, "L": 2},  # (theoretical)
    "Mo8O26": {"H": 0, "O": -6, "L": 8},  # 8×4=32, 26-32=-6 | (no direct beta)
    "Mo6O19": {"H": 0, "O": -5, "L": 6},  # 6×4=24, 19-24=-5 | (no direct beta)
    "Mo10O34": {"H": 0, "O": -6, "L": 10},  # 10×4=40, 34-40=-6 | (no direct beta)
    "Mo12O36": {"H": 0, "O": -12, "L": 12},  # 12×4=48, 36-48=-12 | (no direct beta)
    "Mo19O59": {"H": 0, "O": -17, "L": 19},  # 19×4=76, 59-76=-17 | β=924 L=10080 M=68(H⁺)
    "MoO3(s)": {"H": 0, "O": -1, "L": 1},  # 1×4=4, 3-4=-1 | β=18,19,20,293,460,1018,1019 L=various M=various
    # ─────────────────────────────────────────────────────────────────────────
    # Tungstate clusters (L = WO4²⁻ from H₂WO₄, ligand 10081)
    # nL has n×4 = 4n oxygens; W_n O_m means excess O = m - 4n
    # ─────────────────────────────────────────────────────────────────────────
    "W7O24": {"H": 0, "O": -4, "L": 7},  # 7×4=28, 24-28=-4 | (no direct beta)
    "HW7O24": {"H": 1, "O": -4, "L": 7},  # (theoretical)
    "H2W7O24": {"H": 2, "O": -4, "L": 7},  # (theoretical)
    "W2O7": {"H": 0, "O": -1, "L": 2},  # 2×4=8, 7-8=-1 | (no direct beta)
    "W6O19": {"H": 0, "O": -5, "L": 6},  # 6×4=24, 19-24=-5 | (no direct beta)
    "W6O21": {"H": 0, "O": -3, "L": 6},  # 6×4=24, 21-24=-3 | β=99,100 L=10081 M=68(H⁺)
    "HW6O21": {"H": 1, "O": -3, "L": 6},  # β=99,100 L=10081 M=68(H⁺)
    "W10O32": {"H": 0, "O": -8, "L": 10},  # 10×4=40, 32-40=-8 | (no direct beta)
    "W12O36": {"H": 0, "O": -12, "L": 12},  # 12×4=48, 36-48=-12 | (no direct beta)
    "W12O41": {"H": 0, "O": -7, "L": 12},  # 12×4=48, 41-48=-7 | β=52,62,98,1022 L=10081 M=68(H⁺)
    "HW12O41": {"H": 1, "O": -7, "L": 12},  # β=52,98 L=10081 M=68(H⁺)
    "H2W12O41": {"H": 2, "O": -7, "L": 12},  # β=52,62 L=10081 M=68(H⁺)
    "H3W12O41": {"H": 3, "O": -7, "L": 12},  # β=62 L=10081 M=68(H⁺)
    "WO3(s)": {"H": 0, "O": -1, "L": 1},  # 1×4=4, 3-4=-1 | β=293,460 M=alkali,L=various
    # ─────────────────────────────────────────────────────────────────────────
    # Vanadate clusters (L = VO4³⁻ from H₃VO₄, ligand 10077)
    # nL has n×4 oxygens; V_n O_m means excess O = m - 4n
    # ─────────────────────────────────────────────────────────────────────────
    "VO2": {"H": 0, "O": -2, "L": 1},  # 1×4=4, 2-4=-2 | (no direct beta)
    "VO3": {"H": 0, "O": -1, "L": 1},  # 1×4=4, 3-4=-1 | β=16,17,18,294,461,1019,1020 L=various M=various
    "V2O7": {"H": 0, "O": -1, "L": 2},  # 2×4=8, 7-8=-1 | β=96,460,1013 L=10077 M=68,18,25,177
    "HV2O7": {"H": 1, "O": -1, "L": 2},  # β=96 L=10077 M=68(H⁺)
    "V3O9": {"H": 0, "O": -3, "L": 3},  # 3×4=12, 9-12=-3 | (no direct beta)
    "V4O12": {"H": 0, "O": -4, "L": 4},  # 4×4=16, 12-16=-4 | β=461,1014,1015 L=10077 M=various
    "V4O13": {"H": 0, "O": -3, "L": 4},  # 4×4=16, 13-16=-3 | β=97,1015 L=10077 M=68(H⁺)
    "HV4O13": {"H": 1, "O": -3, "L": 4},  # β=97,1015 L=10077 M=68(H⁺)
    "V5O15": {"H": 0, "O": -5, "L": 5},  # 5×4=20, 15-20=-5 | β=1016 L=10077 M=68(H⁺)
    "V6O16": {"H": 0, "O": -8, "L": 6},  # 6×4=24, 16-24=-8 | β=362 L=10077 M=18,177(Ba,Sr)
    "V10O28": {"H": 0, "O": -12, "L": 10},  # 10×4=40, 28-40=-12 | β=50,51,61,95,590,626,810,1000 L=10077 M=various
    "HV10O28": {"H": 1, "O": -12, "L": 10},  # β=51,95,810 L=10077 M=68,alkali
    "H2V10O28": {"H": 2, "O": -12, "L": 10},  # β=50,51,61 L=10077 M=68(H⁺)
    "H3V10O28": {"H": 3, "O": -12, "L": 10},  # β=61 L=10077 M=68(H⁺)
    "V12O31": {"H": 0, "O": -17, "L": 12},  # 12×4=48, 31-48=-17 | β=361 L=10077 M=18,25,177(Ba,Ca,Sr)
    "MVO3(s)": {"M": 1, "H": 0, "O": -1, "L": 1},  # same as VO3 | β=294,461 M=alkali,L=various
    "MV12O31(s)": {"M": 1, "H": 0, "O": -17, "L": 12},  # same as V12O31 | β=361 M=alkali,L=10077
    "MV6O16(s)": {"M": 1, "H": 0, "O": -8, "L": 6},  # same as V6O16 | β=362 M=alkali,L=10077
    "M2V2O7(H2O)2(s)": {"M": 2, "H": 4, "O": 1, "L": 2},  # 2M + 2L(O8) - O + 2 H2O | β=460 M=18,25,177 L=10077
    # corrected (was H:4,O:3): M + 2 VO3 + 4 H2O = M + 2L(O8) - 2 O + H8O4 -> H:8, O:2 | β=461 (BETA-03) M=18,25,177 L=10077
    "M(VO3)2(H2O)4(s)": {"M": 1, "H": 8, "O": 2, "L": 2},
    # corrected (was H:4,O:0): 3M + 2L + 4 H2O -> H:8, O:4 | β=618 names it but BETA-03 rewrites 618 with L labels, so unused
    "M3(VO4)2(H2O)4(s)": {"M": 3, "H": 8, "O": 4, "L": 2},
    "M3V10O28(s)": {"M": 3, "H": 0, "O": -12, "L": 10},  # same as V10O28 | β=1000 M=alkali,L=10077
    "MHV10O28": {"M": 1, "H": 1, "O": -12, "L": 10},  # β=810 M=alkali,L=10077
    "MV10O28": {"M": 1, "H": 0, "O": -12, "L": 10},  # β=50,51,61,95,590,626 M=alkali,L=10077
    # corrected (was O:-0.5,L:0.5): half V2O5 = VO2.5 = L(VO4) - 1.5 O | β=1017 (BETA-03 supplies the 0.5 H2O) L=10077 M=68
    "(V2O5)0.5(s)": {"H": 0, "O": -1.5, "L": 1},
    # ─────────────────────────────────────────────────────────────────────────
    # Peroxochromate: M = CrO4 2- (metal 39 is the chromate ion), L = O2 (peroxide, H2O2 = H2L, ligand 10143)
    # CrO5 = CrO(O2)2 = Cr1 O5 = M(Cr1 O4) + 2 L(O4) - 3 O
    # corrected (was O:+1, derived as if M were bare Cr). β=23 [CrO5]/[M][H2L]^2 still does not balance
    # (H:-4, O:-3 as written; CrO4 2- + 2 H2O2 + 2 H+ -> CrO5 + 3 H2O needs an [H]^2 the record lacks) -> BETA-01
    # ─────────────────────────────────────────────────────────────────────────
    "CrO5": {"M": 1, "H": 0, "O": -3, "L": 2},
    # ─────────────────────────────────────────────────────────────────────────
    # Simple oxo-anion condensates / oxides named by formula (L = figure unit of the ligand)
    # ─────────────────────────────────────────────────────────────────────────
    "CO2(g)": {"O": -1, "L": 1},  # CO2 = L(CO3) - O | β=33 [H2L]/[CO2(g)] (balances with 1 H2O), β=282 (stays unbalanced) L=10096
    "Cr2O7": {"H": 0, "O": -1, "L": 2},  # dichromate = 2 L(CrO4) - O | β=22 [Cr2O7]/[HL]^2 (2 HCrO4- -> Cr2O7 2- + H2O), 714 L=10079
    "MCr2O7": {"M": 1, "H": 0, "O": -1, "L": 2},  # M+ dichromate ion pair | β=714 [MCr2O7]/[M][Cr2O7] M=78(K+),111(NH4+) L=10079
    "S2O5": {"H": 0, "O": -1, "L": 2},  # disulfite = 2 L(SO3) - O | β=1001 [S2O5]/[HL]^2 (2 HSO3- -> S2O5 2- + H2O) L=10147
    "SO2(g)": {"H": 0, "O": -1, "L": 1},  # corrected (original O:-2,L:0.5 read it as half SiO2): SO2 = L(SO3) - O | β=41 [H2L]/[SO2(g)] L=10147
    "GeO2(s,hexagonal)": {"H": -2, "O": -2, "L": 1},  # GeO2 = L(H2GeO4, figure H2L of 10102) - H2 - O2 | β=34 [H2L]/[GeO2(s,hexagonal)] M=68
    "GeO2(s,tetragonal)": {"H": -2, "O": -2, "L": 1},  # as above | β=35 [H2L]/[GeO2(s,tetragonal)] M=68
    # ─────────────────────────────────────────────────────────────────────────
    # Periodate: L = IO₆ (from H₅IO₆ = H5L, ligand 10174), M = H⁺ or alkali
    # L contains I:1, O:6. IO4 has O:4 → diff from L: O:-2
    # ─────────────────────────────────────────────────────────────────────────
    "IO4": {"H": 0, "O": -2, "L": 1},  # IO4: I1O4, L: I1O6 → O:-2 | β=20,69,102,299,811
    "IO3": {"H": 0, "O": -3, "L": 1},  # IO3: I1O3, L: I1O6 → O:-3
    "HIO4": {"H": 1, "O": -2, "L": 1},  # HIO4 = IO4 + H | β=102
    "H4I2O10": {"H": 4, "O": -2, "L": 2},  # H4I2O10: I2O10H4, 2L: I2O12 → H:4,O:-2
    "MIO4(s)": {"M": 1, "H": 0, "O": -2, "L": 1},  # same as IO4 | β=69
    "MIO4": {"M": 1, "H": 0, "O": -2, "L": 1},  # same as IO4 | β=20,299,811
    # ─────────────────────────────────────────────────────────────────────────
    # Silicate polymers: L = H₂SiO₄ (from H₄SiO₄ = H2L, ligand 10101), M = H⁺
    # L contains H:2, Si:1, O:4. nL has Si:n, O:4n, H:2n
    # Token = species - nL: H_diff = species_H - 2n, O_diff = species_O - 4n
    # ─────────────────────────────────────────────────────────────────────────
    "Si2O7": {"H": -4, "O": -1, "L": 2},  # Si2O7(H:0,O:7) - 2L(H:4,O:8) = H:-4,O:-1 | β=1008
    "Si3O10": {"H": -6, "O": -2, "L": 3},  # Si3O10(H:0,O:10) - 3L(H:6,O:12) = H:-6,O:-2 | β=1009
    "Si3O9": {"H": -6, "O": -3, "L": 3},  # Si3O9(H:0,O:9) - 3L(H:6,O:12) = H:-6,O:-3 | β=1010 (cyclic)
    "Si4O12": {"H": -8, "O": -4, "L": 4},  # Si4O12(H:0,O:12) - 4L(H:8,O:16) = H:-8,O:-4 | β=1011 (cyclic)
    "Si2O3(OH)4": {"H": 0, "O": -1, "L": 2},  # Si2O7H4(H:4,O:7) - 2L(H:4,O:8) = H:0,O:-1 | β=1008
    "Si2O2(OH)5": {"H": 1, "O": -1, "L": 2},  # Si2O7H5(H:5,O:7) - 2L(H:4,O:8) = H:1,O:-1 | β=1007
    "Si3O5(OH)5": {"H": -1, "O": -2, "L": 3},  # Si3O10H5(H:5,O:10) - 3L(H:6,O:12) = H:-1,O:-2 | β=1009
    "Si3O5(OH)5(linear)": {"H": -1, "O": -2, "L": 3},  # same as Si3O5(OH)5 | β=1009
    "Si3O6(OH)3(cyclo)": {"H": -3, "O": -3, "L": 3},  # Si3O9H3(H:3,O:9) - 3L(H:6,O:12) = H:-3,O:-3 | β=1010
    "Si4O8(OH)4": {"H": -4, "O": -4, "L": 4},  # Si4O12H4(H:4,O:12) - 4L(H:8,O:16) = H:-4,O:-4 | β=1012
    "Si4O7(OH)5(cyclo)": {"H": -3, "O": -4, "L": 4},  # Si4O12H5(H:5,O:12) - 4L(H:8,O:16) = H:-3,O:-4 | β=1011
    # corrected (original O:-2,L:0.5 "half SiO2 unit" never balanced): SiO2 = L(H2SiO4) - H2 - O2, so
    # SiO2(s) + 2 H2O -> H2L (= Si(OH)4) | β=40 quartz, 39 cristobalite, 38 amorphous; L=10101 M=68
    "SiO2(s,quartz)": {"H": -2, "O": -2, "L": 1},
    "SiO2(s,cristobalite)": {"H": -2, "O": -2, "L": 1},
    "SiO2(s,am)": {"H": -2, "O": -2, "L": 1},
    # sepiolite Mg4Si6O15(OH)2.6H2O = 2 x Mg2Si3O8.3.5H2O: 2M + 3L(H:6,O:12) + H1 - O0.5 | β=449 (BETA-03) M=92(Mg2+) L=10101
    "M2Si3O8(H2O)3.5(s,sepiolite)": {"M": 2, "H": 1, "O": -0.5, "L": 3},
    # ─────────────────────────────────────────────────────────────────────────
    # Antimonate polymers: L = H₄SbO₅ (from H₅SbO₅ = HL, ligand 10142), M = H⁺
    # L contains H:4, Sb:1, O:5. nL has Sb:n, O:5n, H:4n
    # Sb12(OH)64 = Sb12O64H64: 12L → Sb:12, O:60, H:48 → diff: H:+16, O:+4
    # Sb12(OH)65 = Sb12O65H65: 12L → Sb:12, O:60, H:48 → diff: H:+17, O:+5
    # ─────────────────────────────────────────────────────────────────────────
    "Sb12O64": {"H": 16, "O": 4, "L": 12},  # β=1002 L=10142 M=68(H⁺)
    "Sb12(OH)64": {"H": 16, "O": 4, "L": 12},  # same as Sb12O64 | β=1002,1003 L=10142 M=68(H⁺)
    "Sb12(OH)65": {"H": 17, "O": 5, "L": 12},  # β=1003 (denominator) L=10142 M=68(H⁺)
    "Sb12(OH)66": {"H": 18, "O": 6, "L": 12},  # β=1004 (denominator) L=10142 M=68(H⁺)
    "Sb12(OH)67": {"H": 19, "O": 7, "L": 12},  # β=1005 (denominator) L=10142 M=68(H⁺)
    # ─────────────────────────────────────────────────────────────────────────
    # Arsenite polymers: L = AsO₃ (from H₃AsO₃ = H3L, ligand 10139), M = H⁺
    # L contains As:1, O:3. (As4O6)0.25 = As1O1.5 → 1L: O:3 → diff: O:-1.5
    # β=54 [H3L]/[(As4O6)0.25(s)] needs 1.5 H2O; the water fix is integer-only, so BETA-03 54 supplies it
    # ─────────────────────────────────────────────────────────────────────────
    "(As4O6)0.25(s)": {"H": 0, "O": -1.5, "L": 1},  # β=54 L=10139 M=68(H⁺)
}
_declare(Rule("BETA-04", "pip1a_beta_definition", "beta_definition",
              f"{len(BETA_POLYMETAL_HOL_TOKENS)} polymetal oxo-cluster tokens expanded to H/O/L(/M) counts by the tokenizer",
              "Mo7O24, V10O28, W12O41 ... cannot be derived from M/L/H symbols; each token is a hand-made chemistry mapping"))


__all__ = [
    'BETA_POLYMETAL_HOL_TOKENS',
]
