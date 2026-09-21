"""
reference_state_converter.py — Convert Pourbaix atlas free energies to canonical frame.
======================================================================================
The Pourbaix atlas uses **absolute** free enthalpies of formation in
**calories** (referencing the element in its standard state = 0).

The free-energy card uses **relative** standard chemical potentials
in **kJ/mol**, with the free aquo ion set as μ° = 0 for each metal
component (RULE 1).

This module provides the conversion bridge.

Key relationships
-----------------
* 1 cal = 4.184 J  →  multiply cal by 0.004184 to get kJ
* Offset for metal component Mᵢ:
    offset_kJ = 0 − μ°_atlas(Mᵢ_aquo_ion, kJ)
    μ°_canon(species) = μ°_atlas(species, kJ) + offset_kJ

* Redox couple E° between two oxidation states:
    E° = −(μ°_red − μ°_ox) / (n·F)      (using absolute μ° in J/mol)
"""
from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ..db_pourbaix_atlas.atlas_data import AtlasSpecies, _SYMBOL_TO_NAME

log = logging.getLogger("RefStateConv")

# ── Physical constants ────────────────────────────────────────
CAL_TO_J  = 4.184               # 1 thermochemical calorie = 4.184 J
F_CONST   = 96_485.332          # Faraday constant, C/mol

# Regex for counting metal atoms in simple dissolved-ion formulas.
# Matches: Element + optional subscript + sign-or-paren (to distinguish
# "Fe2+" (1 atom, charge 2+) from "Hg2(2+)" (2 atoms, charge 2+)).
# Key rule: a digit followed by +/- is a CHARGE, not a subscript.
# A digit followed by ( or another letter/digit-without-sign is a subscript.
_METAL_SUBSCRIPT_RE = re.compile(
    r'^([A-Z][a-z]?)(\d+)(?=[A-Z(])'   # subscript only if followed by letter or (
)


def _metal_atom_count(formula: str, element_symbol: str) -> int:
    """Return the number of metal atoms in a simple ion formula.

    Works for reference dissolved ions: Fe2+, Hg2(2+), Cu(+), etc.
    Distinguishes subscripts from charges:
      - "Fe2+" → 1 (the 2 is charge, not subscript)
      - "Hg2(2+)" → 2 (the first 2 is subscript before '(')
      - "Cu2O" → 2 (subscript before 'O')
    Falls back to 1 if parsing fails.
    """
    m = _METAL_SUBSCRIPT_RE.match(formula)
    if m and m.group(1) == element_symbol:
        return int(m.group(2))
    return 1


# ══════════════════════════════════════════════════════════════
#  Data containers
# ══════════════════════════════════════════════════════════════

@dataclass
class CanonicalSpecies:
    """An atlas species converted to the canonical kJ reference frame."""
    species: str
    phase: str
    oxidation_state: str
    mu0_abs_kJ: float       # absolute μ° in kJ/mol (converted from cal)
    mu0_canon_kJ: float     # relative μ° in the card's canonical frame
    element: str
    source_file: str


@dataclass
class RedoxCoupleAtlas:
    """A redox couple derived from atlas absolute free energies."""
    oxidised_species: str
    reduced_species: str
    oxidised_ox_state: str
    reduced_ox_state: str
    n_electrons: int
    E0_V: float             # standard potential vs SHE
    dG_kJ: float            # ΔG° of the half-reaction in kJ/mol
    element: str
    source: str = "Pourbaix atlas"


# ══════════════════════════════════════════════════════════════
#  Conversion functions
# ══════════════════════════════════════════════════════════════

def cal_to_kJ(cal_value: float) -> float:
    """Convert calories to kJ."""
    return cal_value * CAL_TO_J / 1000.0


def atlas_to_canonical_kJ(
    atlas_species: List[AtlasSpecies],
    reference_aquo_ions: Optional[Dict[str, str]] = None,
) -> Tuple[List[CanonicalSpecies], Dict[str, float]]:
    """Convert atlas species to canonical kJ reference frame.

    The reference aquo ion for each oxidation state group is the
    dissolved species whose oxidation state is the lowest positive
    integer (typically Mⁿ⁺).  Its canonical μ° is set to 0.

    Parameters
    ----------
    atlas_species : list of AtlasSpecies from the parser
    reference_aquo_ions : optional dict mapping oxidation state → species name
                          to override automatic reference selection

    Returns
    -------
    (canonical_species, offsets)
    canonical_species : list of CanonicalSpecies
    offsets : dict mapping oxidation_state → offset_kJ applied
    """
    if reference_aquo_ions is None:
        reference_aquo_ions = {}

    # Group by oxidation state to find reference ions
    by_ox: Dict[str, List[AtlasSpecies]] = {}
    for s in atlas_species:
        ox = s.oxidation_state.strip()
        by_ox.setdefault(ox, []).append(s)

    # For each oxidation state, find the reference (dissolved, simplest ion)
    offsets: Dict[str, float] = {}
    for ox, group in by_ox.items():
        if ox in reference_aquo_ions:
            ref_name = reference_aquo_ions[ox]
            ref = next((s for s in group if s.species == ref_name), None)
        else:
            # Auto-detect: prefer dissolved species with simplest formula
            dissolved = [s for s in group if s.phase == "Dissolved"]
            if dissolved:
                # Prefer the shortest formula (usually the free ion)
                ref = min(dissolved, key=lambda s: len(s.species))
            else:
                ref = None

        if ref is not None:
            mu_abs_kJ = cal_to_kJ(ref.mu0_cal)
            offsets[ox] = -mu_abs_kJ
            log.info("Reference for ox=%s: %s (μ°_abs=%.2f kJ, offset=%.2f kJ)",
                     ox, ref.species, mu_abs_kJ, offsets[ox])
        else:
            offsets[ox] = 0.0
            log.warning("No dissolved reference found for ox=%s", ox)

    # Convert all species
    canonical: List[CanonicalSpecies] = []
    for s in atlas_species:
        mu_abs = cal_to_kJ(s.mu0_cal)
        ox = s.oxidation_state.strip()
        offset = offsets.get(ox, 0.0)
        mu_canon = mu_abs + offset

        canonical.append(CanonicalSpecies(
            species=s.species,
            phase=s.phase,
            oxidation_state=ox,
            mu0_abs_kJ=mu_abs,
            mu0_canon_kJ=mu_canon,
            element=s.element,
            source_file=s.source_file,
        ))

    return canonical, offsets


# ══════════════════════════════════════════════════════════════
#  Redox couple extraction
# ══════════════════════════════════════════════════════════════

def _parse_ox_state_numeric(ox_str: str) -> Optional[float]:
    """Parse oxidation state string to a number (e.g. '+3' → 3, '0' → 0)."""
    s = ox_str.strip().replace("+", "")
    if "," in s:
        # Mixed oxidation state (e.g. "+2, +3") — skip
        return None
    try:
        return float(s)
    except ValueError:
        return None


def extract_redox_couples(
    atlas_species: List[AtlasSpecies],
) -> List[RedoxCoupleAtlas]:
    """Extract all possible redox couples from atlas species.

    For each pair of dissolved species with different oxidation states
    of the same element, compute E° using:
        E° = −ΔG° / (n·F)
    where ΔG° = μ°(reduced) − μ°(oxidised) − n·μ°(e⁻)
    and μ°(e⁻) = 0 by convention.

    Parameters
    ----------
    atlas_species : list of AtlasSpecies from the parser

    Returns
    -------
    List of RedoxCoupleAtlas with E° vs SHE.
    """
    couples: List[RedoxCoupleAtlas] = []

    # Group dissolved species by element
    dissolved = [s for s in atlas_species if s.phase == "Dissolved"]

    # Group by oxidation state (numeric)
    by_ox: Dict[float, List[AtlasSpecies]] = {}
    for s in dissolved:
        ox_num = _parse_ox_state_numeric(s.oxidation_state)
        if ox_num is not None:
            by_ox.setdefault(ox_num, []).append(s)

    # Also include "0" oxidation state solids (pure metals)
    metals = [s for s in atlas_species
              if s.phase == "Solid" and s.oxidation_state.strip() == "0"]
    if metals:
        by_ox.setdefault(0.0, []).extend(metals)

    # Generate couples between all pairs of different oxidation states
    ox_values = sorted(by_ox.keys())
    for i, ox_high in enumerate(ox_values):
        for ox_low in ox_values[:i]:
            n_e = int(round(ox_high - ox_low))
            if n_e <= 0:
                continue

            for s_ox in by_ox[ox_high]:
                for s_red in by_ox[ox_low]:
                    mu_ox_J = s_ox.mu0_cal * CAL_TO_J
                    mu_red_J = s_red.mu0_cal * CAL_TO_J
                    dG_J = mu_red_J - mu_ox_J   # ΔG = μ(red) - μ(ox)
                    dG_kJ = dG_J / 1000.0
                    E0 = -dG_J / (n_e * F_CONST)

                    couples.append(RedoxCoupleAtlas(
                        oxidised_species=s_ox.species,
                        reduced_species=s_red.species,
                        oxidised_ox_state=s_ox.oxidation_state,
                        reduced_ox_state=s_red.oxidation_state,
                        n_electrons=n_e,
                        E0_V=round(E0, 4),
                        dG_kJ=round(dG_kJ, 2),
                        element=s_ox.element,
                    ))

    log.info("Extracted %d redox couples", len(couples))
    return couples


# ══════════════════════════════════════════════════════════════
#  Valence offset computation (for Pourbaix card §5 embedding)
# ══════════════════════════════════════════════════════════════

def compute_valence_offsets(
    atlas_species: List[AtlasSpecies],
    valence_table: List[dict],
) -> Dict[str, float]:
    """Compute μ° offsets for non-reference metals from atlas data.

    For a multi-valent element (e.g. Fe2+/Fe3+), the reference metal
    (``is_reference=true`` in §2.4) gets offset = 0.  Non-reference
    metals get an offset derived from the atlas E°:

        offset_kJ = n × F_CONST × E° / 1000

    where E° is computed from the atlas absolute μ° of the two
    dissolved reference ions.

    Parameters
    ----------
    atlas_species : atlas entries for ONE element
    valence_table : parsed §2.4 rows (dicts with keys
                    ``element``, ``internal_id``, ``name``, ``charge``,
                    ``is_reference``)

    Returns
    -------
    dict mapping ``internal_id`` → ``offset_kJ``
    (reference metals have offset 0; non-reference metals have the
    redox-derived offset).
    """
    offsets: Dict[str, float] = {}

    if not valence_table:
        return offsets

    # Group valence entries by element
    by_element: Dict[str, List[dict]] = {}
    for row in valence_table:
        by_element.setdefault(row["element"], []).append(row)

    for element, entries in by_element.items():
        ref_entry = next((e for e in entries if e["is_reference"]), None)
        if ref_entry is None:
            for e in entries:
                offsets[e["internal_id"]] = 0.0
            continue

        offsets[ref_entry["internal_id"]] = 0.0
        ref_charge = int(ref_entry["charge"].replace("+", "")) if isinstance(ref_entry["charge"], str) else int(ref_entry["charge"])

        # Resolve element symbol → full atlas name for filtering
        atlas_element_name = _SYMBOL_TO_NAME.get(element, element)

        # Filter dissolved species to THIS element only
        dissolved = [
            s for s in atlas_species
            if s.phase == "Dissolved"
            and s.element.lower() == atlas_element_name.lower()
        ]
        if not dissolved:
            for e in entries:
                offsets.setdefault(e["internal_id"], 0.0)
            continue

        # Group dissolved species by numeric oxidation state
        by_ox: Dict[int, List[AtlasSpecies]] = {}
        for s in dissolved:
            ox_num = _parse_ox_state_numeric(s.oxidation_state)
            if ox_num is not None:
                by_ox.setdefault(int(ox_num), []).append(s)

        # Reference ion: dissolved species in ref_charge oxidation state,
        # shortest formula (free ion)
        ref_atlas_ions = by_ox.get(ref_charge, [])
        if not ref_atlas_ions:
            for e in entries:
                offsets.setdefault(e["internal_id"], 0.0)
            log.warning("No atlas ion found for reference ox state %+d of %s",
                        ref_charge, element)
            continue
        ref_atlas = min(ref_atlas_ions, key=lambda s: len(s.species))
        # Normalize to per-atom: critical for multi-atom references
        # like Hg2(2+) where mu0_cal is for the whole dimer.
        n_M_ref = _metal_atom_count(ref_atlas.species, element)
        mu_ref_J = ref_atlas.mu0_cal * CAL_TO_J / n_M_ref  # per-atom μ° in J/mol

        for entry in entries:
            if entry["is_reference"]:
                continue

            nonref_charge = int(entry["charge"].replace("+", "")) if isinstance(entry["charge"], str) else int(entry["charge"])
            nonref_atlas_ions = by_ox.get(nonref_charge, [])
            if not nonref_atlas_ions:
                offsets[entry["internal_id"]] = 0.0
                log.warning("No atlas ion for ox state %+d of %s",
                            nonref_charge, element)
                continue

            nonref_atlas = min(nonref_atlas_ions, key=lambda s: len(s.species))
            # Also normalize non-ref to per-atom (e.g. if a dimer exists
            # at a different oxidation state)
            n_M_nonref = _metal_atom_count(nonref_atlas.species, element)
            mu_nonref_J = nonref_atlas.mu0_cal * CAL_TO_J / n_M_nonref

            # E° for the half-reaction (per atom): nonref + n·e⁻ → ref
            n_e = abs(nonref_charge - ref_charge)
            if n_e == 0:
                offsets[entry["internal_id"]] = 0.0
                continue

            # ΔG° per atom = μ°_per_atom(ref) − μ°_per_atom(nonref)
            dG_J = mu_ref_J - mu_nonref_J
            E0_V = -dG_J / (n_e * F_CONST)

            # offset = n·F·E° / 1000  (kJ/mol)
            offset_kJ = n_e * F_CONST * E0_V / 1000.0

            offsets[entry["internal_id"]] = round(offset_kJ, 4)
            log.info(
                "Valence offset for %s (%s): E°=%.4f V, offset=%.4f kJ/mol",
                entry["name"], entry["internal_id"], E0_V, offset_kJ,
            )

    return offsets
