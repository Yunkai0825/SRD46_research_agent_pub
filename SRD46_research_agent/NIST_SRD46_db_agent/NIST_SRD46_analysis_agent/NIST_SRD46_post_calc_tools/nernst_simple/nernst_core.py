"""
nernst_core.py — Standard reduction potential table & Nernst equation solver
==============================================================================

Provides:
  - A built-in table of standard reduction potentials for common
    aqueous redox couples (sourced from standard electrochemistry
    references: Bard & Faulkner, CRC Handbook).
  - ``NernstResult`` dataclass holding E vs pH curves.
  - ``compute_nernst_curve()`` — the main calculation that combines
    speciation data with the Nernst equation.
  - ``lookup_e0()`` / ``list_couples()`` — table queries.

The Nernst equation:
    E = E° + (RT / nF) · ln([Ox] / [Red])

When combined with speciation:
    E = E° + (RT / nF) · ln(α_M · C_M,total)
    where α_M is the free-metal fraction from the speciation solver.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ═══════════════════════════════════════════════════════════════
#  Physical constants
# ═══════════════════════════════════════════════════════════════

F_CONST = 96_485.332        # Faraday constant, C/mol
R_CONST = 8.314_462         # Gas constant, J/(mol·K)
LN10    = math.log(10.0)    # ln(10) ≈ 2.302585


# ═══════════════════════════════════════════════════════════════
#  Standard reduction potentials table
# ═══════════════════════════════════════════════════════════════
#  Each entry: (oxidised, reduced, n_electrons, E0_V, notes)
#  Sorted alphabetically by oxidised species.
#  Sources: CRC Handbook 97th ed., Bard-Faulkner Appendix C

@dataclass(frozen=True)
class RedoxCouple:
    """One half-reaction: Ox + n·e⁻ → Red."""
    oxidised:    str          # e.g. "Ag+"
    reduced:     str          # e.g. "Ag"
    n_electrons: int          # number of electrons transferred
    e0_v:        float        # standard reduction potential in V vs SHE
    metal:       str          # canonical metal name (for matching)
    reaction:    str = ""     # full half-reaction string
    notes:       str = ""     # source / conditions

# Built-in table of standard reduction potentials (V vs SHE, 25 °C)
# Source: CRC Handbook of Chemistry and Physics (Vanýsek Electrochemical Series)
#         Bard-Faulkner Appendix C, Milazzo et al. Tables of Standard Electrode Potentials
_E0_TABLE: List[RedoxCouple] = [
    # ══════════════════════════════════════════════════════════════
    #  SILVER (Ag)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Ag+",       "Ag",     1,  0.7996,  "Ag",  "Ag⁺ + e⁻ → Ag"),
    RedoxCouple("Ag2+",      "Ag+",    1,  1.98,    "Ag",  "Ag²⁺ + e⁻ → Ag⁺"),
    RedoxCouple("Ag3+",      "Ag+",    2,  1.9,     "Ag",  "Ag³⁺ + 2e⁻ → Ag⁺"),
    RedoxCouple("AgBr",      "Ag",     1,  0.0713,  "Ag",  "AgBr + e⁻ → Ag + Br⁻"),
    RedoxCouple("AgCl",      "Ag",     1,  0.2223,  "Ag",  "AgCl + e⁻ → Ag + Cl⁻", "sat. KCl"),
    RedoxCouple("AgCN",      "Ag",     1, -0.017,   "Ag",  "AgCN + e⁻ → Ag + CN⁻"),
    RedoxCouple("AgI",       "Ag",     1, -0.15224, "Ag",  "AgI + e⁻ → Ag + I⁻"),
    RedoxCouple("Ag2O",      "Ag",     2,  0.342,   "Ag",  "Ag₂O + H₂O + 2e⁻ → 2Ag + 2OH⁻"),
    RedoxCouple("Ag2S",      "Ag",     2, -0.691,   "Ag",  "Ag₂S + 2e⁻ → 2Ag + S²⁻"),
    RedoxCouple("AgSCN",     "Ag",     1,  0.08951, "Ag",  "AgSCN + e⁻ → Ag + SCN⁻"),
    RedoxCouple("Ag2SO4",    "Ag",     2,  0.654,   "Ag",  "Ag₂SO₄ + 2e⁻ → 2Ag + SO₄²⁻"),

    # ══════════════════════════════════════════════════════════════
    #  ALUMINIUM (Al)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Al3+",      "Al",     3, -1.662,   "Al",  "Al³⁺ + 3e⁻ → Al"),
    RedoxCouple("Al(OH)3",   "Al",     3, -2.31,    "Al",  "Al(OH)₃ + 3e⁻ → Al + 3OH⁻"),
    RedoxCouple("AlF6_3-",   "Al",     3, -2.069,   "Al",  "AlF₆³⁻ + 3e⁻ → Al + 6F⁻"),

    # ══════════════════════════════════════════════════════════════
    #  ARSENIC (As)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("As",        "AsH3",   3, -0.608,   "As",  "As + 3H⁺ + 3e⁻ → AsH₃"),
    RedoxCouple("As2O3",     "As",     6,  0.234,   "As",  "As₂O₃ + 6H⁺ + 6e⁻ → 2As + 3H₂O"),
    RedoxCouple("HAsO2",     "As",     3,  0.248,   "As",  "HAsO₂ + 3H⁺ + 3e⁻ → As + 2H₂O"),
    RedoxCouple("H3AsO4",    "HAsO2",  2,  0.56,    "As",  "H₃AsO₄ + 2H⁺ + 2e⁻ → HAsO₂ + 2H₂O"),

    # ══════════════════════════════════════════════════════════════
    #  GOLD (Au)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Au+",       "Au",     1,  1.692,   "Au",  "Au⁺ + e⁻ → Au"),
    RedoxCouple("Au3+",      "Au",     3,  1.498,   "Au",  "Au³⁺ + 3e⁻ → Au"),
    RedoxCouple("Au3+",      "Au+",    2,  1.401,   "Au",  "Au³⁺ + 2e⁻ → Au⁺"),
    RedoxCouple("AuCl4-",    "Au",     3,  1.002,   "Au",  "AuCl₄⁻ + 3e⁻ → Au + 4Cl⁻"),
    RedoxCouple("AuBr4-",    "Au",     3,  0.854,   "Au",  "AuBr₄⁻ + 3e⁻ → Au + 4Br⁻"),
    RedoxCouple("Au(OH)3",   "Au",     3,  1.45,    "Au",  "Au(OH)₃ + 3H⁺ + 3e⁻ → Au + 3H₂O"),

    # ══════════════════════════════════════════════════════════════
    #  BARIUM (Ba)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Ba2+",      "Ba",     2, -2.912,   "Ba",  "Ba²⁺ + 2e⁻ → Ba"),
    RedoxCouple("Ba(OH)2",   "Ba",     2, -2.99,    "Ba",  "Ba(OH)₂ + 2e⁻ → Ba + 2OH⁻"),

    # ══════════════════════════════════════════════════════════════
    #  BERYLLIUM (Be)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Be2+",      "Be",     2, -1.847,   "Be",  "Be²⁺ + 2e⁻ → Be"),

    # ══════════════════════════════════════════════════════════════
    #  BISMUTH (Bi)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Bi+",       "Bi",     1,  0.5,     "Bi",  "Bi⁺ + e⁻ → Bi"),
    RedoxCouple("Bi3+",      "Bi",     3,  0.308,   "Bi",  "Bi³⁺ + 3e⁻ → Bi"),
    RedoxCouple("Bi3+",      "Bi+",    2,  0.2,     "Bi",  "Bi³⁺ + 2e⁻ → Bi⁺"),
    RedoxCouple("BiO+",      "Bi",     3,  0.32,    "Bi",  "BiO⁺ + 2H⁺ + 3e⁻ → Bi + H₂O"),
    RedoxCouple("Bi2O4",     "BiO+",   2,  1.593,   "Bi",  "Bi₂O₄ + 4H⁺ + 2e⁻ → 2BiO⁺ + 2H₂O"),

    # ══════════════════════════════════════════════════════════════
    #  BROMINE (Br)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Br2(aq)",   "Br-",    2,  1.0873,  "Br",  "Br₂(aq) + 2e⁻ → 2Br⁻"),
    RedoxCouple("Br2(l)",    "Br-",    2,  1.066,   "Br",  "Br₂(l) + 2e⁻ → 2Br⁻"),
    RedoxCouple("HBrO",      "Br-",    2,  1.331,   "Br",  "HBrO + H⁺ + 2e⁻ → Br⁻ + H₂O"),
    RedoxCouple("BrO3-",     "Br-",    6,  1.423,   "Br",  "BrO₃⁻ + 6H⁺ + 6e⁻ → Br⁻ + 3H₂O"),

    # ══════════════════════════════════════════════════════════════
    #  CALCIUM (Ca)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Ca2+",      "Ca",     2, -2.868,   "Ca",  "Ca²⁺ + 2e⁻ → Ca"),
    RedoxCouple("Ca(OH)2",   "Ca",     2, -3.02,    "Ca",  "Ca(OH)₂ + 2e⁻ → Ca + 2OH⁻"),

    # ══════════════════════════════════════════════════════════════
    #  CADMIUM (Cd)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Cd2+",      "Cd",     2, -0.4030,  "Cd",  "Cd²⁺ + 2e⁻ → Cd"),
    RedoxCouple("Cd(OH)2",   "Cd",     2, -0.809,   "Cd",  "Cd(OH)₂ + 2e⁻ → Cd(Hg) + 2OH⁻"),
    RedoxCouple("CdO",       "Cd",     2, -0.783,   "Cd",  "CdO + H₂O + 2e⁻ → Cd + 2OH⁻"),
    RedoxCouple("CdSO4",     "Cd",     2, -0.246,   "Cd",  "CdSO₄ + 2e⁻ → Cd + SO₄²⁻"),

    # ══════════════════════════════════════════════════════════════
    #  CERIUM (Ce)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Ce3+",      "Ce",     3, -2.336,   "Ce",  "Ce³⁺ + 3e⁻ → Ce"),
    RedoxCouple("Ce4+",      "Ce3+",   1,  1.72,    "Ce",  "Ce⁴⁺ + e⁻ → Ce³⁺"),

    # ══════════════════════════════════════════════════════════════
    #  CHLORINE (Cl)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Cl2(g)",    "Cl-",    2,  1.358,   "Cl",  "Cl₂(g) + 2e⁻ → 2Cl⁻"),
    RedoxCouple("HClO",      "Cl2",    1,  1.611,   "Cl",  "HClO + H⁺ + e⁻ → ½Cl₂ + H₂O"),
    RedoxCouple("ClO-",      "Cl-",    2,  0.81,    "Cl",  "ClO⁻ + H₂O + 2e⁻ → Cl⁻ + 2OH⁻"),
    RedoxCouple("ClO3-",     "Cl-",    6,  1.451,   "Cl",  "ClO₃⁻ + 6H⁺ + 6e⁻ → Cl⁻ + 3H₂O"),
    RedoxCouple("ClO4-",     "Cl-",    8,  1.389,   "Cl",  "ClO₄⁻ + 8H⁺ + 8e⁻ → Cl⁻ + 4H₂O"),

    # ══════════════════════════════════════════════════════════════
    #  COBALT (Co)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Co2+",      "Co",     2, -0.28,    "Co",  "Co²⁺ + 2e⁻ → Co"),
    RedoxCouple("Co3+",      "Co2+",   1,  1.92,    "Co",  "Co³⁺ + e⁻ → Co²⁺"),
    RedoxCouple("[Co(NH3)6]3+", "[Co(NH3)6]2+", 1, 0.108, "Co", "[Co(NH₃)₆]³⁺ + e⁻ → [Co(NH₃)₆]²⁺"),
    RedoxCouple("Co(OH)2",   "Co",     2, -0.73,    "Co",  "Co(OH)₂ + 2e⁻ → Co + 2OH⁻"),
    RedoxCouple("Co(OH)3",   "Co(OH)2", 1, 0.17,   "Co",  "Co(OH)₃ + e⁻ → Co(OH)₂ + OH⁻"),

    # ══════════════════════════════════════════════════════════════
    #  CHROMIUM (Cr)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Cr2+",      "Cr",     2, -0.913,   "Cr",  "Cr²⁺ + 2e⁻ → Cr"),
    RedoxCouple("Cr3+",      "Cr",     3, -0.744,   "Cr",  "Cr³⁺ + 3e⁻ → Cr"),
    RedoxCouple("Cr3+",      "Cr2+",   1, -0.407,   "Cr",  "Cr³⁺ + e⁻ → Cr²⁺"),
    RedoxCouple("Cr2O7_2-",  "Cr3+",   6,  1.36,    "Cr",  "Cr₂O₇²⁻ + 14H⁺ + 6e⁻ → 2Cr³⁺ + 7H₂O"),
    RedoxCouple("HCrO4-",    "Cr3+",   3,  1.350,   "Cr",  "HCrO₄⁻ + 7H⁺ + 3e⁻ → Cr³⁺ + 4H₂O"),
    RedoxCouple("CrO2",      "Cr3+",   1,  1.48,    "Cr",  "CrO₂ + 4H⁺ + e⁻ → Cr³⁺ + 2H₂O"),
    RedoxCouple("Cr(OH)3",   "Cr",     3, -1.48,    "Cr",  "Cr(OH)₃ + 3e⁻ → Cr + 3OH⁻"),

    # ══════════════════════════════════════════════════════════════
    #  CESIUM (Cs)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Cs+",       "Cs",     1, -3.026,   "Cs",  "Cs⁺ + e⁻ → Cs"),

    # ══════════════════════════════════════════════════════════════
    #  COPPER (Cu)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Cu+",       "Cu",     1,  0.521,   "Cu",  "Cu⁺ + e⁻ → Cu"),
    RedoxCouple("Cu2+",      "Cu",     2,  0.3419,  "Cu",  "Cu²⁺ + 2e⁻ → Cu"),
    RedoxCouple("Cu2+",      "Cu+",    1,  0.153,   "Cu",  "Cu²⁺ + e⁻ → Cu⁺"),
    RedoxCouple("Cu3+",      "Cu2+",   1,  2.4,     "Cu",  "Cu³⁺ + e⁻ → Cu²⁺"),
    RedoxCouple("Cu2O",      "Cu",     2, -0.360,   "Cu",  "Cu₂O + H₂O + 2e⁻ → 2Cu + 2OH⁻"),
    RedoxCouple("Cu(OH)2",   "Cu",     2, -0.222,   "Cu",  "Cu(OH)₂ + 2e⁻ → Cu + 2OH⁻"),
    RedoxCouple("[Cu(CN)2]-", "Cu",    1,  1.103,   "Cu",  "Cu²⁺ + 2CN⁻ + e⁻ → [Cu(CN)₂]⁻"),
    RedoxCouple("CuI2-",     "Cu",     1,  0.00,    "Cu",  "CuI₂⁻ + e⁻ → Cu + 2I⁻"),

    # ══════════════════════════════════════════════════════════════
    #  EUROPIUM (Eu)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Eu2+",      "Eu",     2, -2.812,   "Eu",  "Eu²⁺ + 2e⁻ → Eu"),
    RedoxCouple("Eu3+",      "Eu",     3, -1.991,   "Eu",  "Eu³⁺ + 3e⁻ → Eu"),
    RedoxCouple("Eu3+",      "Eu2+",   1, -0.363,   "Eu",  "Eu³⁺ + e⁻ → Eu²⁺"),

    # ══════════════════════════════════════════════════════════════
    #  FLUORINE (F)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("F2",        "F-",     2,  2.866,   "F",   "F₂ + 2e⁻ → 2F⁻"),
    RedoxCouple("F2O",       "F-",     4,  2.153,   "F",   "F₂O + 2H⁺ + 4e⁻ → H₂O + 2F⁻"),

    # ══════════════════════════════════════════════════════════════
    #  IRON (Fe)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Fe2+",      "Fe",     2, -0.447,   "Fe",  "Fe²⁺ + 2e⁻ → Fe"),
    RedoxCouple("Fe3+",      "Fe",     3, -0.037,   "Fe",  "Fe³⁺ + 3e⁻ → Fe"),
    RedoxCouple("Fe3+",      "Fe2+",   1,  0.771,   "Fe",  "Fe³⁺ + e⁻ → Fe²⁺"),
    RedoxCouple("[Fe(CN)6]3-", "[Fe(CN)6]4-", 1, 0.358, "Fe", "[Fe(CN)₆]³⁻ + e⁻ → [Fe(CN)₆]⁴⁻"),
    RedoxCouple("[Fe(bipy)3]3+", "[Fe(bipy)3]2+", 1, 1.03, "Fe", "[Fe(bipy)₃]³⁺ + e⁻ → [Fe(bipy)₃]²⁺"),
    RedoxCouple("[Fe(phen)3]3+", "[Fe(phen)3]2+", 1, 1.147, "Fe", "[Fe(phen)₃]³⁺ + e⁻ → [Fe(phen)₃]²⁺"),
    RedoxCouple("Fe(OH)3",   "Fe(OH)2", 1, -0.56,   "Fe",  "Fe(OH)₃ + e⁻ → Fe(OH)₂ + OH⁻"),
    RedoxCouple("HFeO4-",    "Fe3+",   3,  2.07,    "Fe",  "HFeO₄⁻ + 7H⁺ + 3e⁻ → Fe³⁺ + 4H₂O"),

    # ══════════════════════════════════════════════════════════════
    #  GALLIUM (Ga)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Ga3+",      "Ga",     3, -0.549,   "Ga",  "Ga³⁺ + 3e⁻ → Ga"),
    RedoxCouple("Ga+",       "Ga",     1, -0.2,     "Ga",  "Ga⁺ + e⁻ → Ga"),

    # ══════════════════════════════════════════════════════════════
    #  GADOLINIUM (Gd)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Gd3+",      "Gd",     3, -2.279,   "Gd",  "Gd³⁺ + 3e⁻ → Gd"),

    # ══════════════════════════════════════════════════════════════
    #  GERMANIUM (Ge)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Ge2+",      "Ge",     2,  0.24,    "Ge",  "Ge²⁺ + 2e⁻ → Ge"),
    RedoxCouple("Ge4+",      "Ge",     4,  0.124,   "Ge",  "Ge⁴⁺ + 4e⁻ → Ge"),
    RedoxCouple("Ge4+",      "Ge2+",   2,  0.00,    "Ge",  "Ge⁴⁺ + 2e⁻ → Ge²⁺"),
    RedoxCouple("GeO2",      "GeO",    2, -0.118,   "Ge",  "GeO₂ + 2H⁺ + 2e⁻ → GeO + H₂O"),

    # ══════════════════════════════════════════════════════════════
    #  HYDROGEN (H)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("H+",        "H2",     2,  0.0000,  "H",   "2H⁺ + 2e⁻ → H₂"),
    RedoxCouple("H2O",       "H2",     2, -0.8277,  "H",   "2H₂O + 2e⁻ → H₂ + 2OH⁻"),
    RedoxCouple("H2O2",      "H2O",    2,  1.776,   "H",   "H₂O₂ + 2H⁺ + 2e⁻ → 2H₂O"),
    RedoxCouple("HO2",       "H2O2",   1,  1.495,   "H",   "HO₂ + H⁺ + e⁻ → H₂O₂"),

    # ══════════════════════════════════════════════════════════════
    #  HAFNIUM (Hf)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Hf4+",      "Hf",     4, -1.55,    "Hf",  "Hf⁴⁺ + 4e⁻ → Hf"),
    RedoxCouple("HfO2",      "Hf",     4, -1.505,   "Hf",  "HfO₂ + 4H⁺ + 4e⁻ → Hf + 2H₂O"),

    # ══════════════════════════════════════════════════════════════
    #  MERCURY (Hg)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Hg2+",      "Hg",     2,  0.851,   "Hg",  "Hg²⁺ + 2e⁻ → Hg"),
    RedoxCouple("Hg2_2+",    "Hg",     2,  0.7973,  "Hg",  "Hg₂²⁺ + 2e⁻ → 2Hg"),
    RedoxCouple("Hg2+",      "Hg2_2+", 2,  0.920,   "Hg",  "2Hg²⁺ + 2e⁻ → Hg₂²⁺"),
    RedoxCouple("Hg2Cl2",    "Hg",     2,  0.26808, "Hg",  "Hg₂Cl₂ + 2e⁻ → 2Hg + 2Cl⁻", "calomel"),
    RedoxCouple("HgO",       "Hg",     2,  0.0977,  "Hg",  "HgO + H₂O + 2e⁻ → Hg + 2OH⁻"),
    RedoxCouple("Hg(OH)2",   "Hg",     2,  1.034,   "Hg",  "Hg(OH)₂ + 2H⁺ + 2e⁻ → Hg + 2H₂O"),
    RedoxCouple("Hg2SO4",    "Hg",     2,  0.612,   "Hg",  "Hg₂SO₄ + 2e⁻ → 2Hg + SO₄²⁻"),

    # ══════════════════════════════════════════════════════════════
    #  INDIUM (In)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("In+",       "In",     1, -0.14,    "In",  "In⁺ + e⁻ → In"),
    RedoxCouple("In3+",      "In",     3, -0.338,   "In",  "In³⁺ + 3e⁻ → In"),
    RedoxCouple("In3+",      "In+",    2, -0.443,   "In",  "In³⁺ + 2e⁻ → In⁺"),
    RedoxCouple("In(OH)3",   "In",     3, -0.991,   "In",  "In(OH)₃ + 3e⁻ → In + 3OH⁻"),

    # ══════════════════════════════════════════════════════════════
    #  IODINE (I)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("I2",        "I-",     2,  0.5355,  "I",   "I₂ + 2e⁻ → 2I⁻"),
    RedoxCouple("I3-",       "I-",     2,  0.53,    "I",   "I₃⁻ + 2e⁻ → 3I⁻"),
    RedoxCouple("HIO",       "I-",     2,  0.987,   "I",   "HIO + H⁺ + 2e⁻ → I⁻ + H₂O"),
    RedoxCouple("IO3-",      "I-",     6,  1.085,   "I",   "IO₃⁻ + 6H⁺ + 6e⁻ → I⁻ + 3H₂O"),
    RedoxCouple("H5IO6",     "IO3-",   2,  1.439,   "I",   "H₅IO₆ + H⁺ + 2e⁻ → IO₃⁻ + 3H₂O"),

    # ══════════════════════════════════════════════════════════════
    #  IRIDIUM (Ir)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Ir3+",      "Ir",     3,  1.156,   "Ir",  "Ir³⁺ + 3e⁻ → Ir"),
    RedoxCouple("[IrCl6]2-", "[IrCl6]3-", 1, 0.866, "Ir",  "[IrCl₆]²⁻ + e⁻ → [IrCl₆]³⁻"),
    RedoxCouple("[IrCl6]3-", "Ir",     3,  0.77,    "Ir",  "[IrCl₆]³⁻ + 3e⁻ → Ir + 6Cl⁻"),

    # ══════════════════════════════════════════════════════════════
    #  POTASSIUM (K)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("K+",        "K",      1, -2.931,   "K",   "K⁺ + e⁻ → K"),

    # ══════════════════════════════════════════════════════════════
    #  LANTHANUM (La)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("La3+",      "La",     3, -2.379,   "La",  "La³⁺ + 3e⁻ → La"),
    RedoxCouple("La(OH)3",   "La",     3, -2.90,    "La",  "La(OH)₃ + 3e⁻ → La + 3OH⁻"),

    # ══════════════════════════════════════════════════════════════
    #  LITHIUM (Li)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Li+",       "Li",     1, -3.040,   "Li",  "Li⁺ + e⁻ → Li"),

    # ══════════════════════════════════════════════════════════════
    #  MAGNESIUM (Mg)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Mg2+",      "Mg",     2, -2.372,   "Mg",  "Mg²⁺ + 2e⁻ → Mg"),
    RedoxCouple("Mg(OH)2",   "Mg",     2, -2.690,   "Mg",  "Mg(OH)₂ + 2e⁻ → Mg + 2OH⁻"),

    # ══════════════════════════════════════════════════════════════
    #  MANGANESE (Mn)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Mn2+",      "Mn",     2, -1.185,   "Mn",  "Mn²⁺ + 2e⁻ → Mn"),
    RedoxCouple("Mn3+",      "Mn2+",   1,  1.541,   "Mn",  "Mn³⁺ + e⁻ → Mn²⁺"),
    RedoxCouple("MnO2",      "Mn2+",   2,  1.224,   "Mn",  "MnO₂ + 4H⁺ + 2e⁻ → Mn²⁺ + 2H₂O"),
    RedoxCouple("MnO4-",     "MnO4_2-", 1, 0.558,   "Mn",  "MnO₄⁻ + e⁻ → MnO₄²⁻"),
    RedoxCouple("MnO4-",     "MnO2",   3,  1.679,   "Mn",  "MnO₄⁻ + 4H⁺ + 3e⁻ → MnO₂ + 2H₂O"),
    RedoxCouple("MnO4-",     "Mn2+",   5,  1.507,   "Mn",  "MnO₄⁻ + 8H⁺ + 5e⁻ → Mn²⁺ + 4H₂O"),
    RedoxCouple("Mn(OH)2",   "Mn",     2, -1.56,    "Mn",  "Mn(OH)₂ + 2e⁻ → Mn + 2OH⁻"),

    # ══════════════════════════════════════════════════════════════
    #  MOLYBDENUM (Mo)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Mo3+",      "Mo",     3, -0.200,   "Mo",  "Mo³⁺ + 3e⁻ → Mo"),
    RedoxCouple("MoO2",      "Mo",     4, -0.152,   "Mo",  "MoO₂ + 4H⁺ + 4e⁻ → Mo + 2H₂O"),

    # ══════════════════════════════════════════════════════════════
    #  SODIUM (Na)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Na+",       "Na",     1, -2.71,    "Na",  "Na⁺ + e⁻ → Na"),

    # ══════════════════════════════════════════════════════════════
    #  NIOBIUM (Nb)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Nb3+",      "Nb",     3, -1.099,   "Nb",  "Nb³⁺ + 3e⁻ → Nb"),
    RedoxCouple("Nb2O5",     "Nb",    10, -0.644,   "Nb",  "Nb₂O₅ + 10H⁺ + 10e⁻ → 2Nb + 5H₂O"),

    # ══════════════════════════════════════════════════════════════
    #  NEODYMIUM (Nd)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Nd3+",      "Nd",     3, -2.323,   "Nd",  "Nd³⁺ + 3e⁻ → Nd"),
    RedoxCouple("Nd2+",      "Nd",     2, -2.70,    "Nd",  "Nd²⁺ + 2e⁻ → Nd"),

    # ══════════════════════════════════════════════════════════════
    #  NICKEL (Ni)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Ni2+",      "Ni",     2, -0.257,   "Ni",  "Ni²⁺ + 2e⁻ → Ni"),
    RedoxCouple("Ni(OH)2",   "Ni",     2, -0.72,    "Ni",  "Ni(OH)₂ + 2e⁻ → Ni + 2OH⁻"),
    RedoxCouple("NiO",       "Ni2+",   2,  0.72,    "Ni",  "NiO + 4H⁺ + 2e⁻ → Ni²⁺ + 2H₂O"),
    RedoxCouple("NiO2",      "Ni2+",   2,  1.678,   "Ni",  "NiO₂ + 4H⁺ + 2e⁻ → Ni²⁺ + 2H₂O"),
    RedoxCouple("NiO2",      "Ni(OH)2", 2, -0.490,  "Ni",  "NiO₂ + 2H₂O + 2e⁻ → Ni(OH)₂ + 2OH⁻"),

    # ══════════════════════════════════════════════════════════════
    #  NEPTUNIUM (Np)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Np3+",      "Np",     3, -1.856,   "Np",  "Np³⁺ + 3e⁻ → Np"),
    RedoxCouple("Np4+",      "Np3+",   1,  0.147,   "Np",  "Np⁴⁺ + e⁻ → Np³⁺"),

    # ══════════════════════════════════════════════════════════════
    #  OXYGEN (O)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("O2",        "H2O",    4,  1.229,   "O",   "O₂ + 4H⁺ + 4e⁻ → 2H₂O"),
    RedoxCouple("O2",        "H2O2",   2,  0.695,   "O",   "O₂ + 2H⁺ + 2e⁻ → H₂O₂"),
    RedoxCouple("O2",        "OH-",    4,  0.401,   "O",   "O₂ + 2H₂O + 4e⁻ → 4OH⁻"),
    RedoxCouple("O3",        "O2",     2,  2.076,   "O",   "O₃ + 2H⁺ + 2e⁻ → O₂ + H₂O"),
    RedoxCouple("OH",        "OH-",    1,  2.02,    "O",   "OH + e⁻ → OH⁻"),

    # ══════════════════════════════════════════════════════════════
    #  OSMIUM (Os)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("OsO4",      "Os",     8,  0.838,   "Os",  "OsO₄ + 8H⁺ + 8e⁻ → Os + 4H₂O"),
    RedoxCouple("OsO4",      "OsO2",   4,  1.02,    "Os",  "OsO₄ + 4H⁺ + 4e⁻ → OsO₂ + 2H₂O"),

    # ══════════════════════════════════════════════════════════════
    #  LEAD (Pb)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Pb2+",      "Pb",     2, -0.1262,  "Pb",  "Pb²⁺ + 2e⁻ → Pb"),
    RedoxCouple("PbO2",      "Pb2+",   2,  1.455,   "Pb",  "PbO₂ + 4H⁺ + 2e⁻ → Pb²⁺ + 2H₂O"),
    RedoxCouple("PbO2",      "PbO",    2,  0.247,   "Pb",  "PbO₂ + H₂O + 2e⁻ → PbO + 2OH⁻"),
    RedoxCouple("PbO2",      "PbSO4", 2,  1.6913,   "Pb",  "PbO₂ + SO₄²⁻ + 4H⁺ + 2e⁻ → PbSO₄ + 2H₂O"),
    RedoxCouple("PbSO4",     "Pb",     2, -0.3588,  "Pb",  "PbSO₄ + 2e⁻ → Pb + SO₄²⁻"),
    RedoxCouple("PbO",       "Pb",     2, -0.580,   "Pb",  "PbO + H₂O + 2e⁻ → Pb + 2OH⁻"),
    RedoxCouple("PbCl2",     "Pb",     2, -0.2675,  "Pb",  "PbCl₂ + 2e⁻ → Pb + 2Cl⁻"),
    RedoxCouple("PbBr2",     "Pb",     2, -0.284,   "Pb",  "PbBr₂ + 2e⁻ → Pb + 2Br⁻"),
    RedoxCouple("PbI2",      "Pb",     2, -0.365,   "Pb",  "PbI₂ + 2e⁻ → Pb + 2I⁻"),

    # ══════════════════════════════════════════════════════════════
    #  PALLADIUM (Pd)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Pd2+",      "Pd",     2,  0.951,   "Pd",  "Pd²⁺ + 2e⁻ → Pd"),
    RedoxCouple("[PdCl4]2-", "Pd",     2,  0.591,   "Pd",  "[PdCl₄]²⁻ + 2e⁻ → Pd + 4Cl⁻"),
    RedoxCouple("[PdCl6]2-", "[PdCl4]2-", 2, 1.288, "Pd",  "[PdCl₆]²⁻ + 2e⁻ → [PdCl₄]²⁻ + 2Cl⁻"),
    RedoxCouple("Pd(OH)2",   "Pd",     2,  0.07,    "Pd",  "Pd(OH)₂ + 2e⁻ → Pd + 2OH⁻"),

    # ══════════════════════════════════════════════════════════════
    #  PLATINUM (Pt)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Pt2+",      "Pt",     2,  1.18,    "Pt",  "Pt²⁺ + 2e⁻ → Pt"),
    RedoxCouple("[PtCl4]2-", "Pt",     2,  0.755,   "Pt",  "[PtCl₄]²⁻ + 2e⁻ → Pt + 4Cl⁻"),
    RedoxCouple("[PtCl6]2-", "[PtCl4]2-", 2, 0.68,  "Pt",  "[PtCl₆]²⁻ + 2e⁻ → [PtCl₄]²⁻ + 2Cl⁻"),
    RedoxCouple("Pt(OH)2",   "Pt",     2,  0.14,    "Pt",  "Pt(OH)₂ + 2e⁻ → Pt + 2OH⁻"),
    RedoxCouple("PtO2",      "Pt",     4,  1.00,    "Pt",  "PtO₂ + 4H⁺ + 4e⁻ → Pt + 2H₂O"),

    # ══════════════════════════════════════════════════════════════
    #  PLUTONIUM (Pu)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Pu3+",      "Pu",     3, -2.031,   "Pu",  "Pu³⁺ + 3e⁻ → Pu"),
    RedoxCouple("Pu4+",      "Pu3+",   1,  1.006,   "Pu",  "Pu⁴⁺ + e⁻ → Pu³⁺"),
    RedoxCouple("Pu5+",      "Pu4+",   1,  1.099,   "Pu",  "Pu⁵⁺ + e⁻ → Pu⁴⁺"),

    # ══════════════════════════════════════════════════════════════
    #  RADIUM (Ra)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Ra2+",      "Ra",     2, -2.8,     "Ra",  "Ra²⁺ + 2e⁻ → Ra"),

    # ══════════════════════════════════════════════════════════════
    #  RUBIDIUM (Rb)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Rb+",       "Rb",     1, -2.98,    "Rb",  "Rb⁺ + e⁻ → Rb"),

    # ══════════════════════════════════════════════════════════════
    #  RHENIUM (Re)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Re3+",      "Re",     3,  0.300,   "Re",  "Re³⁺ + 3e⁻ → Re"),
    RedoxCouple("ReO4-",     "Re",     7,  0.368,   "Re",  "ReO₄⁻ + 8H⁺ + 7e⁻ → Re + 4H₂O"),
    RedoxCouple("ReO4-",     "ReO2",   3,  0.510,   "Re",  "ReO₄⁻ + 4H⁺ + 3e⁻ → ReO₂ + 2H₂O"),

    # ══════════════════════════════════════════════════════════════
    #  RHODIUM (Rh)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Rh+",       "Rh",     1,  0.600,   "Rh",  "Rh⁺ + e⁻ → Rh"),
    RedoxCouple("Rh3+",      "Rh",     3,  0.758,   "Rh",  "Rh³⁺ + 3e⁻ → Rh"),
    RedoxCouple("[RhCl6]3-", "Rh",     3,  0.431,   "Rh",  "[RhCl₆]³⁻ + 3e⁻ → Rh + 6Cl⁻"),

    # ══════════════════════════════════════════════════════════════
    #  RUTHENIUM (Ru)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Ru2+",      "Ru",     2,  0.455,   "Ru",  "Ru²⁺ + 2e⁻ → Ru"),
    RedoxCouple("Ru3+",      "Ru2+",   1,  0.2487,  "Ru",  "Ru³⁺ + e⁻ → Ru²⁺"),
    RedoxCouple("RuO4",      "Ru",     8,  1.038,   "Ru",  "RuO₄ + 8H⁺ + 8e⁻ → Ru + 4H₂O"),
    RedoxCouple("[Ru(bipy)3]3+", "[Ru(bipy)3]2+", 1, 1.24, "Ru", "[Ru(bipy)₃]³⁺ + e⁻ → [Ru(bipy)₃]²⁺"),
    RedoxCouple("[Ru(NH3)6]3+", "[Ru(NH3)6]2+", 1,  0.10, "Ru",  "[Ru(NH₃)₆]³⁺ + e⁻ → [Ru(NH₃)₆]²⁺"),
    RedoxCouple("[Ru(CN)6]3-", "[Ru(CN)6]4-", 1, 0.86,   "Ru",  "[Ru(CN)₆]³⁻ + e⁻ → [Ru(CN)₆]⁴⁻"),

    # ══════════════════════════════════════════════════════════════
    #  SULFUR (S)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("S",         "S2-",    2, -0.47627, "S",   "S + 2e⁻ → S²⁻"),
    RedoxCouple("S",         "H2S",    2,  0.142,   "S",   "S + 2H⁺ + 2e⁻ → H₂S(aq)"),
    RedoxCouple("S2O8_2-",   "SO4_2-", 2,  2.010,   "S",   "S₂O₈²⁻ + 2e⁻ → 2SO₄²⁻"),
    RedoxCouple("SO4_2-",    "H2SO3",  2,  0.172,   "S",   "SO₄²⁻ + 4H⁺ + 2e⁻ → H₂SO₃ + H₂O"),
    RedoxCouple("H2SO3",     "S",      4,  0.449,   "S",   "H₂SO₃ + 4H⁺ + 4e⁻ → S + 3H₂O"),

    # ══════════════════════════════════════════════════════════════
    #  ANTIMONY (Sb)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Sb",        "SbH3",   3, -0.510,   "Sb",  "Sb + 3H⁺ + 3e⁻ → SbH₃"),
    RedoxCouple("Sb2O3",     "Sb",     6,  0.152,   "Sb",  "Sb₂O₃ + 6H⁺ + 6e⁻ → 2Sb + 3H₂O"),
    RedoxCouple("Sb2O5",     "Sb2O3",  4,  0.671,   "Sb",  "Sb₂O₅(senarm.) + 4H⁺ + 4e⁻ → Sb₂O₃ + 2H₂O"),
    RedoxCouple("SbO+",      "Sb",     3,  0.212,   "Sb",  "SbO⁺ + 2H⁺ + 3e⁻ → Sb + H₂O"),

    # ══════════════════════════════════════════════════════════════
    #  SCANDIUM (Sc)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Sc3+",      "Sc",     3, -2.077,   "Sc",  "Sc³⁺ + 3e⁻ → Sc"),

    # ══════════════════════════════════════════════════════════════
    #  SELENIUM (Se)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Se",        "Se2-",   2, -0.924,   "Se",  "Se + 2e⁻ → Se²⁻"),
    RedoxCouple("Se",        "H2Se",   2, -0.399,   "Se",  "Se + 2H⁺ + 2e⁻ → H₂Se(aq)"),
    RedoxCouple("H2SeO3",    "Se",     4,  0.74,    "Se",  "H₂SeO₃ + 4H⁺ + 4e⁻ → Se + 3H₂O"),
    RedoxCouple("SeO4_2-",   "H2SeO3", 2,  1.151,   "Se",  "SeO₄²⁻ + 4H⁺ + 2e⁻ → H₂SeO₃ + H₂O"),

    # ══════════════════════════════════════════════════════════════
    #  SILICON (Si)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("SiO2",      "Si",     4,  0.857,   "Si",  "SiO₂(quartz) + 4H⁺ + 4e⁻ → Si + 2H₂O"),
    RedoxCouple("SiF6_2-",   "Si",     4, -1.24,    "Si",  "SiF₆²⁻ + 4e⁻ → Si + 6F⁻"),

    # ══════════════════════════════════════════════════════════════
    #  SAMARIUM (Sm)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Sm3+",      "Sm",     3, -2.304,   "Sm",  "Sm³⁺ + 3e⁻ → Sm"),
    RedoxCouple("Sm3+",      "Sm2+",   1, -1.55,    "Sm",  "Sm³⁺ + e⁻ → Sm²⁺"),
    RedoxCouple("Sm2+",      "Sm",     2, -2.68,    "Sm",  "Sm²⁺ + 2e⁻ → Sm"),

    # ══════════════════════════════════════════════════════════════
    #  TIN (Sn)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Sn2+",      "Sn",     2, -0.1375,  "Sn",  "Sn²⁺ + 2e⁻ → Sn"),
    RedoxCouple("Sn4+",      "Sn2+",   2,  0.151,   "Sn",  "Sn⁴⁺ + 2e⁻ → Sn²⁺"),
    RedoxCouple("SnO2",      "Sn",     4, -0.117,   "Sn",  "SnO₂ + 4H⁺ + 4e⁻ → Sn + 2H₂O"),
    RedoxCouple("SnO2",      "Sn",     4, -0.945,   "Sn",  "SnO₂ + 2H₂O + 4e⁻ → Sn + 4OH⁻"),
    RedoxCouple("Sn(OH)6_2-", "HSnO2-", 2, -0.93,   "Sn",  "Sn(OH)₆²⁻ + 2e⁻ → HSnO₂⁻ + 3OH⁻ + H₂O"),

    # ══════════════════════════════════════════════════════════════
    #  STRONTIUM (Sr)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Sr2+",      "Sr",     2, -2.899,   "Sr",  "Sr²⁺ + 2e⁻ → Sr"),
    RedoxCouple("Sr(OH)2",   "Sr",     2, -2.88,    "Sr",  "Sr(OH)₂ + 2e⁻ → Sr + 2OH⁻"),

    # ══════════════════════════════════════════════════════════════
    #  TANTALUM (Ta)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Ta3+",      "Ta",     3, -0.6,     "Ta",  "Ta³⁺ + 3e⁻ → Ta"),
    RedoxCouple("Ta2O5",     "Ta",    10, -0.750,   "Ta",  "Ta₂O₅ + 10H⁺ + 10e⁻ → 2Ta + 5H₂O"),

    # ══════════════════════════════════════════════════════════════
    #  TECHNETIUM (Tc)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Tc2+",      "Tc",     2,  0.400,   "Tc",  "Tc²⁺ + 2e⁻ → Tc"),
    RedoxCouple("TcO4-",     "Tc",     7,  0.472,   "Tc",  "TcO₄⁻ + 8H⁺ + 7e⁻ → Tc + 4H₂O"),
    RedoxCouple("TcO4-",     "TcO2",   3,  0.782,   "Tc",  "TcO₄⁻ + 4H⁺ + 3e⁻ → TcO₂ + 2H₂O"),

    # ══════════════════════════════════════════════════════════════
    #  TELLURIUM (Te)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Te",        "Te2-",   2, -1.143,   "Te",  "Te + 2e⁻ → Te²⁻"),
    RedoxCouple("Te4+",      "Te",     4,  0.568,   "Te",  "Te⁴⁺ + 4e⁻ → Te"),
    RedoxCouple("TeO2",      "Te",     4,  0.593,   "Te",  "TeO₂ + 4H⁺ + 4e⁻ → Te + 2H₂O"),
    RedoxCouple("H6TeO6",    "TeO2",   2,  1.02,    "Te",  "H₆TeO₆ + 2H⁺ + 2e⁻ → TeO₂ + 4H₂O"),

    # ══════════════════════════════════════════════════════════════
    #  THORIUM (Th)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Th4+",      "Th",     4, -1.899,   "Th",  "Th⁴⁺ + 4e⁻ → Th"),
    RedoxCouple("ThO2",      "Th",     4, -1.789,   "Th",  "ThO₂ + 4H⁺ + 4e⁻ → Th + 2H₂O"),

    # ══════════════════════════════════════════════════════════════
    #  TITANIUM (Ti)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Ti2+",      "Ti",     2, -1.630,   "Ti",  "Ti²⁺ + 2e⁻ → Ti"),
    RedoxCouple("Ti3+",      "Ti",     3, -1.37,    "Ti",  "Ti³⁺ + 3e⁻ → Ti"),
    RedoxCouple("Ti3+",      "Ti2+",   1, -0.9,     "Ti",  "Ti³⁺ + e⁻ → Ti²⁺"),
    RedoxCouple("TiO2",      "Ti2+",   2,  0.502,   "Ti",  "TiO₂ + 4H⁺ + 2e⁻ → Ti²⁺ + 2H₂O"),

    # ══════════════════════════════════════════════════════════════
    #  THALLIUM (Tl)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Tl+",       "Tl",     1, -0.336,   "Tl",  "Tl⁺ + e⁻ → Tl"),
    RedoxCouple("Tl3+",      "Tl+",    2,  1.252,   "Tl",  "Tl³⁺ + 2e⁻ → Tl⁺"),
    RedoxCouple("Tl3+",      "Tl",     3,  0.741,   "Tl",  "Tl³⁺ + 3e⁻ → Tl"),
    RedoxCouple("TlBr",      "Tl",     1, -0.658,   "Tl",  "TlBr + e⁻ → Tl + Br⁻"),
    RedoxCouple("TlCl",      "Tl",     1, -0.5568,  "Tl",  "TlCl + e⁻ → Tl + Cl⁻"),
    RedoxCouple("TlI",       "Tl",     1, -0.752,   "Tl",  "TlI + e⁻ → Tl + I⁻"),

    # ══════════════════════════════════════════════════════════════
    #  URANIUM (U)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("U3+",       "U",      3, -1.798,   "U",   "U³⁺ + 3e⁻ → U"),
    RedoxCouple("U4+",       "U3+",    1, -0.607,   "U",   "U⁴⁺ + e⁻ → U³⁺"),
    RedoxCouple("UO2+",      "U4+",    1,  0.612,   "U",   "UO₂⁺ + 4H⁺ + e⁻ → U⁴⁺ + 2H₂O"),
    RedoxCouple("UO2_2+",    "UO2+",   1,  0.062,   "U",   "UO₂²⁺ + e⁻ → UO₂⁺"),
    RedoxCouple("UO2_2+",    "U4+",    2,  0.327,   "U",   "UO₂²⁺ + 4H⁺ + 2e⁻ → U⁴⁺ + 2H₂O"),
    RedoxCouple("UO2_2+",    "U",      6, -1.444,   "U",   "UO₂²⁺ + 4H⁺ + 6e⁻ → U + 2H₂O"),

    # ══════════════════════════════════════════════════════════════
    #  VANADIUM (V)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("V2+",       "V",      2, -1.175,   "V",   "V²⁺ + 2e⁻ → V"),
    RedoxCouple("V3+",       "V2+",    1, -0.255,   "V",   "V³⁺ + e⁻ → V²⁺"),
    RedoxCouple("VO2+",      "V3+",    1,  0.337,   "V",   "VO²⁺ + 2H⁺ + e⁻ → V³⁺ + H₂O"),
    RedoxCouple("VO2+",      "VO2+",   1,  0.991,   "V",   "VO₂⁺ + 2H⁺ + e⁻ → VO²⁺ + H₂O"),
    RedoxCouple("[V(phen)3]3+", "[V(phen)3]2+", 1, 0.14, "V", "[V(phen)₃]³⁺ + e⁻ → [V(phen)₃]²⁺"),

    # ══════════════════════════════════════════════════════════════
    #  TUNGSTEN (W)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("W3+",       "W",      3,  0.1,     "W",   "W³⁺ + 3e⁻ → W"),
    RedoxCouple("WO2",       "W",      4, -0.119,   "W",   "WO₂ + 4H⁺ + 4e⁻ → W + 2H₂O"),
    RedoxCouple("WO3",       "W",      6, -0.090,   "W",   "WO₃ + 6H⁺ + 6e⁻ → W + 3H₂O"),
    RedoxCouple("WO3",       "WO2",    2,  0.036,   "W",   "WO₃ + 2H⁺ + 2e⁻ → WO₂ + H₂O"),

    # ══════════════════════════════════════════════════════════════
    #  YTTRIUM (Y)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Y3+",       "Y",      3, -2.372,   "Y",   "Y³⁺ + 3e⁻ → Y"),

    # ══════════════════════════════════════════════════════════════
    #  YTTERBIUM (Yb)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Yb3+",      "Yb",     3, -2.19,    "Yb",  "Yb³⁺ + 3e⁻ → Yb"),
    RedoxCouple("Yb2+",      "Yb",     2, -1.05,    "Yb",  "Yb²⁺ + 2e⁻ → Yb"),

    # ══════════════════════════════════════════════════════════════
    #  ZINC (Zn)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Zn2+",      "Zn",     2, -0.7618,  "Zn",  "Zn²⁺ + 2e⁻ → Zn"),
    RedoxCouple("Zn(OH)2",   "Zn",     2, -1.249,   "Zn",  "Zn(OH)₂ + 2e⁻ → Zn + 2OH⁻"),
    RedoxCouple("ZnO",       "Zn",     2, -1.260,   "Zn",  "ZnO + H₂O + 2e⁻ → Zn + 2OH⁻"),
    RedoxCouple("ZnO2_2-",   "Zn",     2, -1.215,   "Zn",  "ZnO₂²⁻ + 2H₂O + 2e⁻ → Zn + 4OH⁻"),
    RedoxCouple("ZnOH+",     "Zn",     2, -0.497,   "Zn",  "ZnOH⁺ + H⁺ + 2e⁻ → Zn + H₂O"),

    # ══════════════════════════════════════════════════════════════
    #  ZIRCONIUM (Zr)
    # ══════════════════════════════════════════════════════════════
    RedoxCouple("Zr4+",      "Zr",     4, -1.45,    "Zr",  "Zr⁴⁺ + 4e⁻ → Zr"),
    RedoxCouple("ZrO2",      "Zr",     4, -1.553,   "Zr",  "ZrO₂ + 4H⁺ + 4e⁻ → Zr + 2H₂O"),
    RedoxCouple("ZrO(OH)2",  "Zr",     4, -2.36,    "Zr",  "ZrO(OH)₂ + H₂O + 4e⁻ → Zr + 4OH⁻"),
]


def list_couples(metal: str = "") -> List[RedoxCouple]:
    """Return all redox couples, optionally filtered by metal name."""
    if not metal:
        return list(_E0_TABLE)
    metal_up = metal.strip().upper()
    return [c for c in _E0_TABLE
            if c.metal.upper() == metal_up
            or metal_up in c.oxidised.upper()
            or metal_up in c.reduced.upper()]


def list_available_metals() -> Dict[str, Dict[str, Any]]:
    """Return a summary of available metals and their redox couples.

    Returns
    -------
    dict
        {metal_symbol: {"n_couples": int, "e0_range": (min, max), "couples": [...]}}
    """
    from collections import defaultdict
    summary: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "n_couples": 0, "e0_min": float("inf"), "e0_max": float("-inf"), "couples": []
    })
    for c in _E0_TABLE:
        m = c.metal
        summary[m]["n_couples"] += 1
        summary[m]["e0_min"] = min(summary[m]["e0_min"], c.e0_v)
        summary[m]["e0_max"] = max(summary[m]["e0_max"], c.e0_v)
        summary[m]["couples"].append({
            "oxidised": c.oxidised, "reduced": c.reduced,
            "n": c.n_electrons, "e0_v": c.e0_v, "reaction": c.reaction
        })
    # Convert to regular dict and format e0_range
    result = {}
    for m, data in sorted(summary.items()):
        result[m] = {
            "n_couples": data["n_couples"],
            "e0_range": (round(data["e0_min"], 4), round(data["e0_max"], 4)),
            "couples": data["couples"],
        }
    return result


def lookup_e0(oxidised: str = "", reduced: str = "",
              metal: str = "") -> List[RedoxCouple]:
    """Find E° by (partial) match on oxidised and/or reduced species.

    At least one of oxidised, reduced, or metal must be given.
    """
    hits = list(_E0_TABLE)
    if metal:
        m = metal.strip().upper()
        hits = [c for c in hits if c.metal.upper() == m]
    if oxidised:
        o = oxidised.strip().upper().replace(" ", "")
        hits = [c for c in hits
                if o in c.oxidised.upper().replace(" ", "")]
    if reduced:
        r = reduced.strip().upper().replace(" ", "")
        hits = [c for c in hits
                if r in c.reduced.upper().replace(" ", "")]
    return hits


# ═══════════════════════════════════════════════════════════════
#  Nernst equation solver
# ═══════════════════════════════════════════════════════════════

@dataclass
class NernstPoint:
    """Result at one pH point."""
    pH:            float
    E_V:           float        # reduction potential in V vs SHE
    free_ox_M:     float        # free oxidised species concentration (mol/L)
    free_red_M:    float        # free reduced species concentration (mol/L)
    alpha_ox:      float        # fraction of total that is free oxidised
    ln_Q:          float        # ln(Q) = ln([Ox]/[Red]) or adjusted

@dataclass
class NernstCurve:
    """Complete E vs pH result."""
    couple:       RedoxCouple
    pH_values:    List[float]
    points:       List[NernstPoint]
    total_metal:  float
    temperature:  float = 25.0
    mode:         str   = ""       # description of calculation mode
    system_name:  str   = ""

    def E_series(self) -> List[float]:
        """Extract E(V) array."""
        return [p.E_V for p in self.points]

    def valid_points(self) -> int:
        return sum(1 for p in self.points if math.isfinite(p.E_V))


def _find_free_metal_key(spec_curve: Any) -> str:
    """Determine the free-metal-ion species key from a SpeciationCurve.

    The Gibbs free-energy solver uses structured keys:
      - ``M1.z+2``  → free Cu²⁺   (just component + charge)
      - ``M1.L1.z+2`` → Cu(NH₃)²⁺ complex  (has ``.L``)
      - ``M1.OH.z+1`` → CuOH⁺              (has ``.OH``)

    Returns the key for the *free* (uncomplexed, non-precipitated) metal
    ion, e.g. ``"M1.z+2"``, or ``"M"`` as legacy fallback.
    """
    # Identify the first metal component (usually "M1")
    comp_key = None
    if hasattr(spec_curve, "metal_names") and spec_curve.metal_names:
        comp_key = next(iter(spec_curve.metal_names))
    if not comp_key or not spec_curve.results:
        return "M"  # legacy single-component fallback

    # Pattern: exactly "<comp_key>.z+<digits>" with nothing in between
    pat = re.compile(rf"^{re.escape(comp_key)}\.z\+\d+$")

    pr0 = spec_curve.results[0]
    frac = pr0.frac_metals.get(comp_key, pr0.frac_M) if pr0.frac_metals else pr0.frac_M
    for k in frac:
        if pat.match(k):
            return k

    # Fallback: try legacy "M"
    if "M" in pr0.frac_M:
        return "M"
    return comp_key


def compute_nernst_curve(
    *,
    couple: RedoxCouple,
    speciation_curve: Any = None,
    total_metal: float = 1e-3,
    pH_values: Optional[List[float]] = None,
    temperature: float = 25.0,
    activity_red: float = 1.0,
    mode: str = "auto",
) -> NernstCurve:
    """Compute E vs pH using the Nernst equation.

    Parameters
    ----------
    couple : RedoxCouple
        The half-reaction to evaluate.
    speciation_curve : SpeciationCurve, optional
        If provided, free-metal concentrations at each pH come from the
        speciation solver.  If None, assumes [Ox] = total_metal (no
        complexation).
    total_metal : float
        Total metal concentration in mol/L (used when speciation_curve
        is None, or as fallback).
    pH_values : list[float], optional
        pH array; if None, uses speciation_curve.pH_values or 0–14.
    temperature : float
        Temperature in °C.
    activity_red : float
        Activity of the reduced form (1.0 for solid metal, or
        concentration for dissolved reduced species).
    mode : str
        "speciation" — use speciation data for [Ox].
        "simple"     — assume [Ox] = total_metal (no complexation).
        "auto"       — use speciation if available, else simple.

    Returns
    -------
    NernstCurve
    """
    T_K = temperature + 273.15
    RT_nF = (R_CONST * T_K) / (couple.n_electrons * F_CONST)

    # Determine pH array
    if pH_values is not None:
        phs = list(pH_values)
    elif speciation_curve is not None:
        phs = list(speciation_curve.pH_values)
    else:
        phs = [i * 0.1 for i in range(141)]  # 0.0 to 14.0

    # Determine mode
    use_spec = (speciation_curve is not None
                and mode in ("auto", "speciation"))

    free_key = _find_free_metal_key(speciation_curve) if use_spec else "M"

    results = []
    for i, pH in enumerate(phs):
        if use_spec and i < len(speciation_curve.results):
            pr = speciation_curve.results[i]
            free_ox = pr.conc.get(free_key, 0.0)
            alpha_ox = pr.frac_M.get(free_key, 0.0)
        else:
            free_ox = total_metal
            alpha_ox = 1.0

        # Protect against zero/negative concentrations
        if free_ox <= 0:
            free_ox = 1e-30

        free_red = activity_red

        # Nernst equation: E = E0 + (RT/nF) · ln([Ox]/[Red])
        ln_Q = math.log(free_ox / free_red) if free_red > 0 else 0.0
        E = couple.e0_v + RT_nF * ln_Q

        results.append(NernstPoint(
            pH=pH, E_V=E, free_ox_M=free_ox, free_red_M=free_red,
            alpha_ox=alpha_ox, ln_Q=ln_Q,
        ))

    system_name = (speciation_curve.system_name if speciation_curve
                   else f"{couple.oxidised}/{couple.reduced}")

    effective_mode = "speciation" if use_spec else "simple"

    return NernstCurve(
        couple=couple,
        pH_values=phs,
        points=results,
        total_metal=total_metal,
        temperature=temperature,
        mode=effective_mode,
        system_name=system_name,
    )


def compute_formal_potential(
    *,
    couple: RedoxCouple,
    speciation_curve: Any,
    temperature: float = 25.0,
) -> List[Dict[str, Any]]:
    """Compute the formal (conditional) potential E°' at each pH.

    E°' = E° + (RT/nF) · ln(α_Ox)

    where α_Ox is the fraction of total Ox that is "free" (uncomplexed).
    This is the apparent standard potential corrected for complexation.

    Returns a list of {pH, E_formal_V, alpha_ox} dicts.
    """
    T_K = temperature + 273.15
    RT_nF = (R_CONST * T_K) / (couple.n_electrons * F_CONST)

    free_key = _find_free_metal_key(speciation_curve)

    rows = []
    for pr in speciation_curve.results:
        alpha = pr.frac_M.get(free_key, 0.0)
        if alpha <= 0:
            alpha = 1e-30
        E_f = couple.e0_v + RT_nF * math.log(alpha)
        rows.append({
            "pH":         pr.pH,
            "E_formal_V": round(E_f, 6),
            "alpha_ox":   round(alpha, 6),
        })
    return rows


# ═══════════════════════════════════════════════════════════════
#  Water stability window (H₂/O₂ lines)
# ═══════════════════════════════════════════════════════════════

def water_stability_lines(
    pH_values: List[float],
    temperature: float = 25.0,
    p_gas: float = 1.0,
) -> Tuple[List[float], List[float]]:
    """Return (E_hydrogen, E_oxygen) arrays for the water stability window.

    E_H₂ = 0.000 − 0.05916·pH  (at 25 °C, 1 atm H₂)
    E_O₂ = 1.229 − 0.05916·pH  (at 25 °C, 1 atm O₂)

    Generalised for temperature:
        slope = (RT/F)·ln(10) = 2.303·RT/F
    """
    T_K = temperature + 273.15
    slope = (R_CONST * T_K * LN10) / F_CONST      # ~0.05916 V at 25 °C

    # E° for O₂/H₂O = 1.229 V at 25 °C; slight T correction
    e0_o2 = 1.229  # approximate, valid near 25 °C

    e_h2 = [0.0 - slope * pH for pH in pH_values]
    e_o2 = [e0_o2 - slope * pH for pH in pH_values]
    return e_h2, e_o2
