"""
reference_alignment.py — Reference Alignment Network (RefAlignNet)
=================================================================
Merges species from SRD-46 speciation cards and Pourbaix atlas onto a
single energy reference per element, with full Pourbaix-style decomposition.

Reference Selection Rule (per element)
--------------------------------------
1. Filter to dissolved atlas species only.
2. Pick the lowest positive integer oxidation state group.
3. Within that group, pick the species with the shortest formula
   (free aquo ion, e.g. Fe2+ for iron, Cu(+) for copper).
4. This species becomes the canonical reference: mu_aligned = 0.

Alignment
---------
Atlas species:
    mu_aligned = mu_abs_kJ(species) - n_M * mu_abs_kJ(ref) - n_O * mu_abs_kJ(H2O)
    where n_O is the oxygen count in the species formula (each O comes from H2O).

Card (SRD-46) species:
    mu_aligned = mu_canon_kJ + SUM(stoich_Mi * valence_offset(Mi))
    This is already on the same energy scale (ref ion + H2O components = 0).

Stoichiometric Decomposition
-----------------------------
Each species is decomposed relative to the reference ion:
    n_M * M^(z_ref) + n_H2O * H2O -> Species + n_H+ * H+ + n_e * e-

Where:
    n_M   = number of metal atoms in the formula
    n_H2O = number of O atoms in the formula
    n_H+  = 2*n_O - n_H_in_formula
    n_e   = n_M*z_ref + H_net - z_species
    H_net = n_H_in_formula - 2*n_O   (negative = OH-rich)
"""
from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..db_pourbaix_atlas.atlas_data import AtlasSpecies, _SYMBOL_TO_NAME
from .reference_state_converter import cal_to_kJ, CAL_TO_J, F_CONST

log = logging.getLogger("RefAlignment")

# Standard Pourbaix atlas convention: mu(H2O,l) = -56690 cal
MU0_H2O_CAL = -56_690.0
MU0_H2O_KJ = cal_to_kJ(MU0_H2O_CAL)  # ~ -237.19 kJ/mol


# ======================================================================
#  Data containers
# ======================================================================

@dataclass
class ElementReference:
    """Canonical reference ion for one element."""
    element_symbol: str
    element_name: str       # atlas name, e.g. "Iron"
    reference_species: str  # e.g. "Fe2+"
    oxidation_state: int
    mu0_abs_kJ: float       # absolute DGf **per metal atom** in kJ/mol
    offset_kJ: float        # = -mu0_abs_kJ (so ref has aligned = 0)
    n_metal_in_ref: int = 1 # metal atoms in the reference formula (2 for Hg2^2+)


@dataclass
class AlignedAtlasSpecies:
    """An atlas species aligned to the element reference."""
    species: str
    element: str
    phase: str
    oxidation_state: str
    charge: int
    mu0_abs_kJ: float
    mu0_aligned_kJ: float   # Pourbaix decomposition (incl H2O)
    n_metal: int
    H_net: int               # net proton count (negative = OH equiv.)
    n_electrons: int          # electrons consumed (negative = oxidation)
    n_H2O: int                # water molecules consumed in formation
    formula_atoms: Dict[str, int] = field(default_factory=dict)
    name: str = ""


@dataclass
class AlignedCardSpecies:
    """A card (SRD-46) species aligned to the element reference."""
    species_id: str
    label: str
    phase: str
    charge: int
    mu0_canon_kJ: float
    mu0_aligned_kJ: float
    stoich_str: str
    metal_stoich: Dict[str, int] = field(default_factory=dict)
    ligand_stoich: Dict[str, int] = field(default_factory=dict)
    H_net: int = 0
    n_electrons: int = 0
    source: str = "SRD-46"
    source_record_id: str = ""
    additional_notes: str = ""


@dataclass
class CrossRef:
    """Cross-reference between atlas and card species."""
    atlas_species: str
    card_species_id: str
    card_label: str
    atlas_aligned_kJ: float
    card_aligned_kJ: float
    delta_kJ: float
    match_key: str  # (element, n_M, H_net, charge, phase_type)


# ======================================================================
#  Atlas formula parser
# ======================================================================

# Descriptive suffixes to strip from species names
_SUFFIX_RE = re.compile(
    r'\s*\((?:anh(?:ydr?)?|hydr?|amorph|hex|rhomb|cub|mon|orth|tetr|'
    r'f\.c\.|alpha|beta|'
    r'gamma|white|red|green|grey|brown|blue|black|yellow|colourless|light'
    r'|dark|scarlet|orange|violet|pink|lustrous|metallic)'
    r'[^)]*\)\.?\s*$',
    re.IGNORECASE,
)

_BARE_PHASE_SUFFIX_RE = re.compile(
    r'\s+(?:anh(?:ydr?)?|hydr?)\.\s*$',
    re.IGNORECASE,
)

# Standard formal oxidation states used for charge balance. Only O and H are
# fixed; every other ("central") element uses the oxidation_state the Pourbaix
# Atlas records for that row. This is pure charge conservation
# (charge = Σ oxidation states) and contains no element-identity heuristics.
_FORMAL_OX: Dict[str, int] = {"O": -2, "H": 1}

_ROMAN_OX: Dict[str, int] = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
}

_STRUCTURED_OX_RE = re.compile(
    r'([+-]?(?:\d+(?:\.\d+)?(?:/\d+)?|[IVX]+))'
    r'\s*\(([A-Z][a-z]?)\)',
)


def _simple_oxidation_value(token: str) -> Optional[float]:
    """Parse one Arabic, Roman, or rational oxidation-state token."""
    clean = token.strip()
    sign = 1
    if clean.startswith(("+", "-")):
        if clean[0] == "-":
            sign = -1
        clean = clean[1:].strip()

    roman = _ROMAN_OX.get(clean.upper())
    if roman is not None and clean.isalpha():
        return float(sign * roman)

    fraction = re.fullmatch(r'(\d+)\s*/\s*(\d+)', clean)
    if fraction:
        denominator = int(fraction.group(2))
        if denominator == 0:
            return None
        return sign * int(fraction.group(1)) / denominator

    try:
        value = sign * float(clean)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def _structured_oxidation_token(
    oxidation_state: str,
    central_element: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """Return an element-qualified oxidation token when one is available.

    The boolean indicates whether the cell used structured labels at all.
    Without an explicit central element, a unique label other than H or O is
    accepted; otherwise the caller must conservatively leave it unresolved.
    """
    matches = _STRUCTURED_OX_RE.findall(oxidation_state)
    if not matches:
        return False, None

    if central_element:
        selected = [
            token
            for token, element in matches
            if element.casefold() == central_element.casefold()
        ]
        return True, selected[0] if len(selected) == 1 else None

    selected = [
        token for token, element in matches if element not in {"H", "O"}
    ]
    return True, selected[0] if len(selected) == 1 else None


def _atoms_from_core(core: str) -> Dict[str, int]:
    """Parse a charge-stripped formula core into {element: count}.

    Expands parenthesised groups, e.g. ``Fe(OH)2`` ->
    ``{Fe: 1, O: 2, H: 2}``, and applies coefficients on dot-separated
    adducts, e.g. ``Ni3O4.2H2O`` -> ``{Ni: 3, O: 6, H: 4}``.

    Both the ASCII full stop and the middle-dot spellings used by the Atlas
    source are accepted.  A dot is treated as an adduct separator only when
    the following segment starts like a chemical formula; punctuation in
    annotations such as ``(anh.alpha)`` is therefore left alone.
    An indeterminate hydrate such as ``.nH2O`` is explicitly ignored with
    a warning instead of being silently interpreted as one water molecule.
    """
    def _expand(match: re.Match) -> str:
        group_text = match.group(1)
        n = int(match.group(2)) if match.group(2) else 1
        inner = re.findall(r'([A-Z][a-z]?)(\d*)', group_text)
        parts = []
        for el, cnt in inner:
            if not el:
                continue
            c = int(cnt) if cnt else 1
            parts.append(f"{el}{c * n}")
        return ''.join(parts)

    symbolic_hydrate = re.search(
        r'\s*[.\u00b7\u22c5]\s*[a-z]\s*H2O\s*$',
        core,
    )
    if symbolic_hydrate:
        log.warning(
            "Formula %s has an indeterminate hydrate coefficient; "
            "ignoring the symbolic hydrate term",
            core,
        )
        core = core[:symbolic_hydrate.start()]

    atoms: Dict[str, int] = {}
    ignored_fragments: List[str] = []
    segments = re.split(
        r'\s*[.\u00b7\u22c5]\s*(?=(?:\d+)?[A-Z])',
        core,
    )
    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue

        coefficient = 1
        leading = re.match(r'^(\d+)(?=[A-Z(])', segment)
        if leading:
            coefficient = int(leading.group(1))
            segment = segment[leading.end():]

        # Repeating the substitution also handles nested simple groups after
        # their innermost group has been expanded.
        expanded = segment
        while True:
            expanded, replacements = re.subn(
                r'\(([A-Za-z0-9]+)\)(\d*)', _expand, expanded,
            )
            if replacements == 0:
                break

        atom_pattern = r'([A-Z][a-z]?)(\d*)'
        for m in re.finditer(atom_pattern, expanded):
            el = m.group(1)
            cnt = int(m.group(2)) if m.group(2) else 1
            atoms[el] = atoms.get(el, 0) + coefficient * cnt
        residue = re.sub(atom_pattern, '', expanded)
        residue = re.sub(r'\s+', '', residue)
        if residue:
            ignored_fragments.append(residue)

    if ignored_fragments:
        log.warning(
            "Formula %s contains ignored text after atom parsing: %s",
            core,
            ", ".join(ignored_fragments),
        )
    return atoms


def _warn_name_only_hydrate(species_str: str) -> None:
    """Warn when hydration is named but no numeric primary formula is given."""
    marker = re.search(
        r'(?:\(\s*hydr?\.?|\bhydr?\.)',
        species_str,
        flags=re.IGNORECASE,
    )
    if marker is None:
        return
    primary_formula = species_str[:marker.start()]
    if re.search(
        r'[.\u00b7\u22c5]\s*\d*H2O',
        primary_formula,
    ):
        return
    log.warning(
        "Atlas species %s names a hydrated phase without an explicit numeric "
        "hydrate in the primary formula; retaining the written base formula",
        species_str,
    )


def _charge_balance(
    atoms: Dict[str, int], central_ox: Optional[int]
) -> Optional[int]:
    """Net ionic charge from Σ(formal oxidation states).

    O and H take their standard formal states (-2, +1); every other element
    takes ``central_ox`` (the Atlas oxidation_state for the row). Returns
    None when undetermined - a non-O/H element is present but no
    oxidation_state was supplied - so the caller can fall back.
    """
    total = 0
    for el, n in atoms.items():
        if el in _FORMAL_OX:
            total += _FORMAL_OX[el] * n
        elif central_ox is None:
            return None
        else:
            total += central_ox * n
    return total


def _normalise_ox(
    oxidation_state,
    central_element: Optional[str] = None,
) -> Optional[int]:
    """Coerce an int / oxidation-state string ("+7", "+2, +3") to int|None."""
    if oxidation_state is None:
        return None
    if isinstance(oxidation_state, int):
        return oxidation_state
    return _parse_ox_numeric(
        str(oxidation_state), central_element=central_element,
    )


def parse_atlas_formula(
    species_str: str,
    oxidation_state=None,
) -> Tuple[Dict[str, int], int]:
    """Parse an atlas species formula into (atom_counts, charge).

    The Pourbaix Atlas writes ionic charge inconsistently across element
    files, and the bare ``<formula><digit><sign>`` form is genuinely
    ambiguous: in "Fe2+" the digit is the charge (+2), but in "MnO4-" the
    identical-looking trailing digit is an oxygen subscript (charge -1). No
    structural/element rule separates them (e.g. "FeOH2+" contains an O yet
    its digit is the charge). The only reliable discriminator is charge
    conservation, so when ``oxidation_state`` (the row's formal oxidation
    state for the central element) is supplied, the ambiguous case is
    resolved by whichever reading satisfies charge = Σ(oxidation states).
    Unambiguous forms - parenthesised "(2-)" and repeated-sign "++"/"--" -
    are handled directly and need no oxidation state.

    Handles: Fe2+, Cu(2+), HFeO2(-), Fe(OH)2(+), MnO4-, MnO4--, HMnO2-,
             HSO4-, S2-, Mn++, Fe2O3, Cu2O, etc.
    """
    central_ox = _normalise_ox(oxidation_state)

    # Step 1: strip descriptive suffixes and trailing parenthetical
    # annotations. A whitespace-preceded trailing "(...)" is always an
    # annotation in this DB ("Dy3+ (Dy+++)", "Fe(OH)2 (hydr.)",
    # "CoO hyd. (Co(OH)2)"); charge parentheses like "(2-)" are never
    # space-preceded, so this never strips a real charge.
    _warn_name_only_hydrate(species_str)
    clean = _SUFFIX_RE.sub('', species_str).strip()
    clean = re.sub(r'\s+\(.*\)\s*$', '', clean).strip()
    clean = _BARE_PHASE_SUFFIX_RE.sub('', clean).strip()

    # Step 2: extract charge from the end
    charge = 0

    m = re.search(r'\((\d*)([\+\-])\)\s*$', clean)
    if m:
        # (n+)/(n-): unambiguous parenthesised charge, e.g. CrO4(2-)
        n = int(m.group(1)) if m.group(1) else 1
        charge = n if m.group(2) == '+' else -n
        clean = clean[:m.start()].strip()
    else:
        m = re.search(r'(\d*)([\+\-]+)\s*$', clean)
        if m:
            digits, signs = m.group(1), m.group(2)
            sign = 1 if signs[0] == '+' else -1
            if len(signs) > 1:
                # Repeated signs encode magnitude unambiguously (Mn++,
                # MnO4--); any preceding digit stays as a formula subscript.
                charge = sign * len(signs)
                clean = clean[:m.start(2)].strip()
            elif not digits:
                # Lone sign: charge ±1 (OH-, HS-, Cs+).
                charge = sign
                clean = clean[:m.start(2)].strip()
            else:
                # Single sign preceded by a digit -> AMBIGUOUS. Decide by
                # charge conservation, with no element-identity heuristics:
                #   subscript reading: keep digit, charge = ±1   (MnO4-)
                #   charge reading:    drop digit, charge = ±digit (Fe2+)
                # Keep whichever reading's Σ(oxidation states) matches its
                # implied charge.
                core_keep = clean[:m.start(2)]      # digit kept -> subscript
                core_drop = clean[:m.start(1)]      # digit dropped -> charge
                q_sub = sign
                q_chg = sign * int(digits)
                bal_sub = _charge_balance(
                    _atoms_from_core(core_keep), central_ox)
                bal_chg = _charge_balance(
                    _atoms_from_core(core_drop), central_ox)
                if bal_chg == q_chg and bal_sub != q_sub:
                    charge, clean = q_chg, core_drop.strip()
                else:
                    # Subscript reading - also the safe default on a tie or
                    # when neither balances (e.g. peroxide-type HO2-, where
                    # O is not -2). Never re-eats an O subscript as charge.
                    charge, clean = q_sub, core_keep.strip()

    # Step 3: parse atoms from the charge-stripped core
    atoms = _atoms_from_core(clean)
    return atoms, charge


def compute_decomposition(
    atoms: Dict[str, int],
    charge: int,
    metal_symbol: str,
    z_ref: int,
) -> Tuple[int, int, int, int]:
    """Compute Pourbaix decomposition from formula.

    Returns (n_metal, H_net, n_electrons, n_H2O).

    Formation half-reaction:
        n_M * M^(z_ref) + n_H2O * H2O -> Species + n_H+ * H+ + n_e * e-

    H_net = n_H_formula - 2*n_O_formula   (negative = OH-rich)
    n_e = n_M*z_ref + H_net - z_species   (negative = oxidation from ref)
    n_H2O = n_O_formula
    """
    n_M = atoms.get(metal_symbol, 0)
    n_H = atoms.get('H', 0)
    n_O = atoms.get('O', 0)

    H_net = n_H - 2 * n_O
    n_e = n_M * z_ref + H_net - charge
    n_H2O = n_O

    return n_M, H_net, n_e, n_H2O


# ======================================================================
#  Reference selection
# ======================================================================

def _parse_ox_numeric(
    ox_str: str,
    central_element: Optional[str] = None,
) -> Optional[int]:
    """Parse a single integral Arabic or Roman oxidation state."""
    structured, selected = _structured_oxidation_token(
        ox_str, central_element=central_element,
    )
    if structured:
        if selected is None:
            return None
        ox_str = selected

    clean = re.sub(
        r'\s*\(\s*mixed\s*\)\s*$', '', ox_str, flags=re.IGNORECASE,
    ).strip()
    if (
        "," in clean
        or ";" in clean
        or re.search(r'/\s*[+-]', clean)
    ):
        return None
    value = _simple_oxidation_value(clean)
    if value is None or not value.is_integer():
        return None
    return int(value)


def integral_oxidation_states(
    oxidation_state: str,
    central_element: Optional[str] = None,
) -> List[int]:
    """Return the explicitly named integral states in an Atlas cell.

    Rounded or rational average states are deliberately omitted: they can be
    allocated only after a real set of integral valences is known.  Element-
    qualified cells are reduced to the central element before parsing, so a
    row such as ``+2 (Ba), -1 (O)`` contributes Ba(II), not O(-I).
    """
    raw_state = str(oxidation_state or "").strip()
    structured, selected = _structured_oxidation_token(
        raw_state, central_element=central_element,
    )
    if structured:
        if selected is None:
            return []
        raw_state = selected
    raw_state = re.sub(
        r'\s*\(\s*mixed\s*\)\s*$',
        '',
        raw_state,
        flags=re.IGNORECASE,
    ).strip()

    exact_fraction = bool(re.fullmatch(
        r'[+-]?\d+\s*/\s*\d+', raw_state,
    ))
    if not exact_fraction:
        raw_state = re.sub(r'/\s*(?=[+-])', ',', raw_state)

    states: List[int] = []
    for token in raw_state.replace(";", ",").split(","):
        value = _simple_oxidation_value(token)
        if value is None or not value.is_integer():
            continue
        state = int(value)
        if state not in states:
            states.append(state)
    return states


def allocate_metal_oxidation_counts(
    oxidation_state: str,
    n_metal: int,
    H_net: int,
    charge: int,
    central_element: Optional[str] = None,
    available_states: Optional[List[int]] = None,
) -> Optional[Dict[int, int]]:
    """Allocate metal atoms among the Atlas row's oxidation states.

    A single integral oxidation state maps every metal atom to that state.
    For a mixed-valence row, charge balance supplies the additional
    constraint::

        sum(n_i) = n_metal
        sum(z_i * n_i) = charge - H_net

    The allocation is returned only when those equations have one unique
    non-negative integer solution.  This resolves ``Fe3O4`` with the Atlas
    cell ``+2, +3`` to one Fe(II) and two Fe(III) atoms.  A single fractional
    label such as ``+2.67`` is treated as a rounded average only when the
    formula-derived average agrees within the precision written in the Atlas
    cell.  The atoms are then allocated between the nearest bracketing states
    actually present in ``available_states``; this distinguishes, for
    example, M(II)/M(III) oxides from Pb(II)/Pb(IV) oxide without hard-coded
    element rules.
    """
    if n_metal <= 0:
        return {}

    raw_state = str(oxidation_state or "").strip()
    structured, selected = _structured_oxidation_token(
        raw_state, central_element=central_element,
    )
    if structured:
        if selected is None:
            return None
        raw_state = selected
    raw_state = re.sub(
        r'\s*\(\s*mixed\s*\)\s*$',
        '',
        raw_state,
        flags=re.IGNORECASE,
    ).strip()

    exact_fraction = bool(re.fullmatch(
        r'[+-]?\d+\s*/\s*\d+', raw_state,
    ))
    if not exact_fraction:
        # A slash followed by another signed value denotes a list of states,
        # as in the Atlas spelling ``+3/+4``, rather than a rational mean.
        raw_state = re.sub(r'/\s*(?=[+-])', ',', raw_state)

    tokens = [
        token.strip()
        for token in raw_state.replace(";", ",").split(",")
        if token.strip()
    ]
    states: List[int] = []
    fractional_state: Optional[Tuple[float, Optional[int]]] = None
    for token in tokens:
        token = token.strip()
        value = _simple_oxidation_value(token)
        if value is None:
            return None
        if not value.is_integer():
            # An average oxidation state is meaningful only as the sole
            # value in the cell.  Its number of decimal places records the
            # rounding tolerance used by the source table.
            if len(tokens) != 1:
                return None
            numeric = token.replace("+", "")
            mantissa = numeric.lower().split("e", 1)[0]
            decimal_places = None if exact_fraction else (
                len(mantissa.rsplit(".", 1)[1]) if "." in mantissa else 0
            )
            fractional_state = (value, decimal_places)
            continue
        state = int(value)
        if state not in states:
            states.append(state)

    target_oxidation_sum = charge - H_net
    if fractional_state is not None:
        stated_average, decimal_places = fractional_state
        formula_average = target_oxidation_sum / n_metal
        rounding_tolerance = (
            1e-12 if decimal_places is None
            else 0.5 * 10.0 ** (-decimal_places) + 1e-12
        )
        if not math.isclose(
            stated_average,
            formula_average,
            rel_tol=0.0,
            abs_tol=rounding_tolerance,
        ):
            return None

        usable_states = sorted({
            int(state)
            for state in (available_states or [])
            if isinstance(state, int)
        })
        if not usable_states:
            return None
        if formula_average.is_integer():
            integral_average = int(formula_average)
            return (
                {integral_average: n_metal}
                if integral_average in usable_states
                else None
            )

        lower = [state for state in usable_states if state < formula_average]
        upper = [state for state in usable_states if state > formula_average]
        if not lower or not upper:
            return None
        low_state = max(lower)
        high_state = min(upper)
        span = high_state - low_state
        high_numerator = target_oxidation_sum - low_state * n_metal
        if high_numerator % span:
            return None
        high_count = high_numerator // span
        low_count = n_metal - high_count
        if low_count < 0 or high_count < 0:
            return None
        return {
            state: count
            for state, count in (
                (low_state, low_count),
                (high_state, high_count),
            )
            if count
        }

    if not states:
        return None
    if (
        available_states is not None
        and any(state not in available_states for state in states)
    ):
        return None
    if len(states) == 1:
        return {states[0]: n_metal}

    solutions: List[Dict[int, int]] = []

    def search(index: int, remaining: int, running_sum: int,
               counts: Dict[int, int]) -> None:
        if len(solutions) > 1:
            return
        state = states[index]
        if index == len(states) - 1:
            count = remaining
            if running_sum + state * count == target_oxidation_sum:
                solution = {z: n for z, n in counts.items() if n}
                if count:
                    solution[state] = count
                solutions.append(solution)
            return
        for count in range(remaining + 1):
            counts[state] = count
            search(
                index + 1,
                remaining - count,
                running_sum + state * count,
                counts,
            )
            if len(solutions) > 1:
                break
        counts.pop(state, None)

    search(0, n_metal, 0, {})
    return solutions[0] if len(solutions) == 1 else None


def select_element_references(
    atlas_by_element: Dict[str, List[AtlasSpecies]],
    valence_table: List[dict],
) -> Dict[str, ElementReference]:
    """Select ONE canonical reference per element from atlas.

    Parameters
    ----------
    atlas_by_element : {element_name: [AtlasSpecies]}
    valence_table    : parsed section 2.4 rows

    Returns
    -------
    {element_symbol: ElementReference}
    """
    refs: Dict[str, ElementReference] = {}

    # Determine which elements we need from the valence table
    elements_needed = {}
    for row in valence_table:
        sym = row["element"]
        if row["is_reference"]:
            elements_needed[sym] = int(
                str(row["charge"]).replace("+", "")
            )

    for symbol, z_ref in elements_needed.items():
        # Resolve symbol to atlas element name
        el_name = _SYMBOL_TO_NAME.get(symbol, symbol)
        atlas_species = atlas_by_element.get(el_name, [])
        if not atlas_species:
            log.warning("No atlas data for element %s (%s)", symbol, el_name)
            continue

        # Find dissolved species at the reference oxidation state
        dissolved_ref = [
            s for s in atlas_species
            if s.phase == "Dissolved"
            and _parse_ox_numeric(
                s.oxidation_state, central_element=symbol,
            ) == z_ref
        ]
        if not dissolved_ref:
            log.warning("No dissolved atlas species at ox=%+d for %s",
                        z_ref, symbol)
            continue

        # Pick shortest formula (simplest ion)
        ref_sp = min(dissolved_ref, key=lambda s: len(s.species))
        mu_abs_formula = cal_to_kJ(ref_sp.mu0_cal)

        # Normalize to per-atom: critical for multi-atom references
        # like Hg2(2+) where mu_abs is for the whole dimer.
        ref_atoms, _ = parse_atlas_formula(
            ref_sp.species, oxidation_state=z_ref)
        n_M_ref = ref_atoms.get(symbol, 1)
        mu_abs_per_atom = mu_abs_formula / n_M_ref

        refs[symbol] = ElementReference(
            element_symbol=symbol,
            element_name=el_name,
            reference_species=ref_sp.species,
            oxidation_state=z_ref,
            mu0_abs_kJ=mu_abs_per_atom,
            offset_kJ=-mu_abs_per_atom,
            n_metal_in_ref=n_M_ref,
        )
        log.info("Reference for %s: %s (ox=%+d, n_M=%d, mu_abs_per_atom=%.3f kJ)",
                 symbol, ref_sp.species, z_ref, n_M_ref, mu_abs_per_atom)

    return refs


# ======================================================================
#  Atlas alignment
# ======================================================================

def align_atlas_species(
    atlas_species: List[AtlasSpecies],
    ref: ElementReference,
) -> List[AlignedAtlasSpecies]:
    """Align all atlas species for one element to the reference.

    mu_aligned = mu_abs(species) - n_M * mu_abs(ref) - n_O * mu_abs(H2O)
    """
    results: List[AlignedAtlasSpecies] = []

    for sp in atlas_species:
        atoms, charge = parse_atlas_formula(
            sp.species, oxidation_state=sp.oxidation_state)
        n_M, H_net, n_e, n_H2O = compute_decomposition(
            atoms, charge, ref.element_symbol, ref.oxidation_state,
        )

        mu_abs = cal_to_kJ(sp.mu0_cal)
        mu_aligned = (
            mu_abs
            - n_M * ref.mu0_abs_kJ
            - n_H2O * MU0_H2O_KJ
        )

        results.append(AlignedAtlasSpecies(
            species=sp.species,
            element=ref.element_symbol,
            phase=sp.phase,
            oxidation_state=sp.oxidation_state,
            charge=charge,
            mu0_abs_kJ=round(mu_abs, 4),
            mu0_aligned_kJ=round(mu_aligned, 4),
            n_metal=n_M,
            H_net=H_net,
            n_electrons=n_e,
            n_H2O=n_H2O,
            formula_atoms=atoms,
            name=sp.name,
        ))

    # Sort by mu_aligned
    results.sort(key=lambda s: s.mu0_aligned_kJ)
    return results


# ======================================================================
#  Card species parser
# ======================================================================

def parse_card_section5(card_text: str) -> List[dict]:
    """Parse section 5.1 and 5.2 tables from the MD card.

    Handles the current card format where each section contains
    multiple sub-tables separated by ``####`` sub-headers.  All
    sub-tables within a section are parsed until the next ``### ``
    section boundary.

    Returns list of dicts with keys:
        species_id, label, charge, phase, log_beta,
        mu0_free_kJ, mu0_canon_kJ, stoich, include, source,
        source_record_id, additional_notes
    """
    species_list: List[dict] = []

    for section_tag, phase_label in [
        ("5.1", "aqueous"),
        ("5.2", "dissolution"),
    ]:
        # Find section header
        pattern = re.compile(
            rf'^###?\s*{re.escape(section_tag)}\s',
            re.MULTILINE,
        )
        m = pattern.search(card_text)
        if not m:
            continue

        block = card_text[m.end():]
        lines = block.split("\n")

        # Scan ALL sub-tables until a ### section boundary
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Stop at next ### section (but not #### sub-headers)
            if line.startswith("### ") and not line.startswith("#### "):
                break

            # Look for a table header with species_id
            if not (line.startswith("|") and "species_id" in line):
                i += 1
                continue

            # Parse column headers
            headers = [h.strip() for h in line.split("|")[1:-1]]

            def _col(name: str, hdrs=headers) -> int:
                try:
                    return hdrs.index(name)
                except ValueError:
                    return -1

            col_sid = _col("species_id")
            col_label = _col("label")
            col_charge = _col("charge")
            col_logb = _col("log_beta")
            col_muf = _col("mu0_free_kJ")
            col_muc = _col("mu0_canon_kJ")
            col_stoich = _col("stoich")
            col_incl = _col("include")
            col_calc_source = _col("calc_source")
            col_source = _col("source")
            col_notes = _col("additional_notes")

            required_columns = {
                "species_id": col_sid,
                "charge": col_charge,
                "log_beta": col_logb,
                "mu0_free_kJ": col_muf,
                "mu0_canon_kJ": col_muc,
                "stoich": col_stoich,
                "include": col_incl,
            }
            missing = sorted(name for name, col in required_columns.items() if col < 0)
            if missing:
                raise ValueError(
                    f"Section {section_tag} species table lacks required columns: {missing}")

            # Skip separator row
            i += 1
            if i < len(lines) and "---" in lines[i]:
                i += 1

            # Read data rows
            while i < len(lines):
                row = lines[i].strip()
                if not row.startswith("|"):
                    break
                cells = [c.strip() for c in row.split("|")[1:-1]]
                if len(cells) < 4 or "---" in cells[0]:
                    i += 1
                    continue

                def _get(col: int, default: str = "", cs=cells) -> str:
                    return cs[col] if 0 <= col < len(cs) else default

                calc_source = _get(col_source) or _get(col_calc_source)
                notes = _get(col_notes)
                estimated_source = "SRD46 query estimated values"
                if calc_source == estimated_source or (
                    '"source":"SRD46 query estimated values"' in notes
                ):
                    source = estimated_source
                else:
                    source = calc_source if calc_source in {"Atlas", "CRC"} else "SRD-46"
                record_match = re.search(
                    r'"candidate_ids":\[([^\]]*)\]', notes,
                )
                source_record_id = ""
                if record_match:
                    source_record_id = ", ".join(
                        value.strip().strip('"')
                        for value in record_match.group(1).split(",")
                        if value.strip()
                    )
                species_id = _get(col_sid).strip()
                if not species_id or species_id == "Not defined":
                    raise ValueError(f"Section {section_tag} has a species with no species_id")
                charge_text = _get(col_charge).replace("+", "").strip()
                try:
                    charge_number = float(charge_text)
                except ValueError as exc:
                    raise ValueError(
                        f"species {species_id!r} has invalid charge {_get(col_charge)!r}") from exc
                if not math.isfinite(charge_number) or not charge_number.is_integer():
                    raise ValueError(
                        f"species {species_id!r} charge must be a finite integer")
                include_text = _get(col_incl).replace("*", "").strip().lower()
                if include_text not in {"true", "false"}:
                    raise ValueError(
                        f"species {species_id!r} include must be exactly true or false")
                stoich = _get(col_stoich).strip()
                if not stoich or stoich == "Not defined":
                    raise ValueError(f"species {species_id!r} stoichiometry is Not defined")
                species_list.append({
                    "species_id": species_id,
                    "label": _get(col_label),
                    "charge": int(charge_number),
                    "phase": phase_label,
                    "log_beta": _required_float(
                        _get(col_logb), field="log_beta", species_id=species_id),
                    "mu0_free_kJ": _required_float(
                        _get(col_muf), field="mu0_free_kJ", species_id=species_id),
                    "mu0_canon_kJ": _required_float(
                        _get(col_muc), field="mu0_canon_kJ", species_id=species_id),
                    "stoich": stoich,
                    "include": include_text == "true",
                    "source": source,
                    "source_record_id": source_record_id,
                    "additional_notes": notes,
                })
                i += 1

    return species_list


def _required_float(s: str, *, field: str, species_id: str) -> float:
    s = s.strip().lstrip("+")
    if not s or s in ("—", "–", "Not defined"):
        raise ValueError(f"species {species_id!r} field {field!r} is Not defined")
    try:
        value = float(s)
    except ValueError as exc:
        raise ValueError(
            f"species {species_id!r} field {field!r} must be numeric") from exc
    if not math.isfinite(value):
        raise ValueError(f"species {species_id!r} field {field!r} must be finite")
    return value


def _parse_stoich(stoich_str: str) -> Dict[str, int]:
    """Parse stoich string into dict.

    Handles:
      - Old format: ``M1:+1 H:-2``
      - Bracket format: ``[M1]:+1, [L1]:+1, [H]:-2``
      - Compound bracket tokens: ``[[H][L1]]:+1``, ``[[H]-1[L1]]:+2``
        These are expanded into individual components:
        ``[[H]-1[L1]]:+2`` → ``{H: -2, L1: 2}``
    """
    result: Dict[str, int] = {}
    _compound_sub_re = re.compile(r'\[([^\]]+)\](-?\d+)?')
    for tok in re.split(r'[,\s]+', stoich_str):
        if ":" not in tok:
            continue
        key, val = tok.split(":", 1)
        key = key.strip()
        try:
            outer_mult = int(val.strip())
        except ValueError:
            continue
        # Compound bracket token: [[H][L1]]:+1 or [[H]-1[L1]]:+2
        if key.startswith("[["):
            inner = key[1:-1]  # strip outer brackets
            for m in _compound_sub_re.finditer(inner):
                sub_key = m.group(1)
                sub_mult = int(m.group(2)) if m.group(2) else 1
                result[sub_key] = result.get(sub_key, 0) + sub_mult * outer_mult
        else:
            key = key.strip("[]")
            result[key] = result.get(key, 0) + outer_mult
    return result


# ======================================================================
#  Card species alignment
# ======================================================================

def align_card_species(
    card_species: List[dict],
    valence_offsets: Dict[str, float],
    metal_info: Dict[str, dict],
    element_ref_charges: Dict[str, int],
) -> List[AlignedCardSpecies]:
    """Align card species using valence offsets.

    Parameters
    ----------
    card_species : parsed from section 5
    valence_offsets : {internal_id: offset_kJ} from compute_valence_offsets
    metal_info : {internal_id: {"element": str, "charge": int}}
    element_ref_charges : {element_symbol: z_ref}

    Returns
    -------
    List of AlignedCardSpecies.
    """
    results: List[AlignedCardSpecies] = []

    for sp in card_species:
        stoich = _parse_stoich(sp["stoich"])
        mu_canon = sp["mu0_canon_kJ"]

        # Compute aligned mu = mu_canon + sum(offset * stoich_count)
        shift = 0.0
        for comp_id, count in stoich.items():
            if comp_id in valence_offsets:
                shift += count * valence_offsets[comp_id]
        mu_aligned = mu_canon + shift

        # Separate metals, ligands, H, OH
        # Metal IDs are those present in metal_info; ligands start with "L"
        metal_stoich = {}
        ligand_stoich = {}
        H_net = 0
        for comp_id, count in stoich.items():
            if comp_id in metal_info:
                metal_stoich[comp_id] = count
            elif comp_id.startswith("L"):
                ligand_stoich[comp_id] = count
            elif comp_id == "H":
                H_net += count
            elif comp_id == "OH":
                H_net -= count   # each OH ≡ H₂O − H⁺ → H_net -= 1

        # Compute electron count from metal valence differences
        n_electrons = 0
        for mid, count in metal_stoich.items():
            info = metal_info.get(mid)
            if info:
                z_ref = element_ref_charges.get(info["element"], 0)
                z_metal = info["charge"]
                n_electrons += count * (z_ref - z_metal)

        results.append(AlignedCardSpecies(
            species_id=sp["species_id"],
            label=sp["label"],
            phase=sp["phase"],
            charge=sp["charge"],
            mu0_canon_kJ=mu_canon,
            mu0_aligned_kJ=round(mu_aligned, 4),
            stoich_str=sp["stoich"],
            metal_stoich=metal_stoich,
            ligand_stoich=ligand_stoich,
            H_net=H_net,
            n_electrons=n_electrons,
            source=sp.get("source") or "SRD-46",
            source_record_id=sp.get("source_record_id", ""),
            additional_notes=sp.get("additional_notes", ""),
        ))

    results.sort(key=lambda s: s.mu0_aligned_kJ)
    return results


# ======================================================================
#  Cross-reference matching
# ======================================================================

def _phase_bucket(phase: str) -> str:
    if phase.lower() in ("dissolved", "aqueous"):
        return "aq"
    return "solid"


def cross_reference(
    atlas_aligned: List[AlignedAtlasSpecies],
    card_aligned: List[AlignedCardSpecies],
    metal_info: Dict[str, dict],
) -> List[CrossRef]:
    """Match species appearing in both databases.

    Match key: (element, n_metal_total, H_net, charge, phase_bucket)
    Only matches species with no ligands (atlas has no ligand data).
    """
    # Build atlas lookup
    atlas_lookup: Dict[tuple, AlignedAtlasSpecies] = {}
    for sp in atlas_aligned:
        key = (sp.element, sp.n_metal, sp.H_net, sp.charge,
               _phase_bucket(sp.phase))
        atlas_lookup[key] = sp

    matches: List[CrossRef] = []

    for csp in card_aligned:
        if csp.ligand_stoich:
            continue  # skip ligand-containing species (no atlas equivalent)

        # Determine element(s) and total metal count
        total_metals_by_el: Dict[str, int] = {}
        for mid, count in csp.metal_stoich.items():
            info = metal_info.get(mid, {})
            el = info.get("element", "")
            if el:
                total_metals_by_el[el] = total_metals_by_el.get(el, 0) + count

        # Only match single-element species against atlas
        if len(total_metals_by_el) != 1:
            continue

        el, n_M = next(iter(total_metals_by_el.items()))
        key = (el, n_M, csp.H_net, csp.charge, _phase_bucket(csp.phase))
        asp = atlas_lookup.get(key)
        if asp is None:
            continue

        delta = abs(asp.mu0_aligned_kJ - csp.mu0_aligned_kJ)
        matches.append(CrossRef(
            atlas_species=_normalize_atlas_name(asp.species, asp.charge),
            card_species_id=csp.species_id,
            card_label=csp.label,
            atlas_aligned_kJ=asp.mu0_aligned_kJ,
            card_aligned_kJ=csp.mu0_aligned_kJ,
            delta_kJ=round(delta, 4),
            match_key=str(key),
        ))

    return matches


# ======================================================================
#  Atlas name normalisation (match SRD-46 bracket convention)
# ======================================================================

_RE_PAREN_CHARGE = re.compile(r'\((\d*)[+-]\)\s*$')     # Cu(2+), FeO4(2-)
_RE_TRAIL_CHARGE = re.compile(r'(\d*)[+-]\s*$')           # Fe2+, FeOH2+
_RE_BARE_ELEMENT = re.compile(r'^[A-Z][a-z]?$')           # Fe, Cu, O ...


def _normalize_atlas_name(raw_name: str, charge: int) -> str:
    """Normalise an Atlas species formula to SRD-46 bracket convention.

    Rules (matching ``_charge_label`` in speciation agent):
    - Neutral (z=0) → formula unchanged (no brackets).
    - Charged bare-element ion → ``Fe2+``, ``Cu+`` (no brackets).
    - Charged complex → ``[FeO4]2-``, ``[Fe(OH)2]+`` (brackets).
    """
    formula = raw_name.strip()
    if charge == 0:
        return formula

    # 1) Strip parenthesised charge suffix  Cu(2+) → Cu
    m = _RE_PAREN_CHARGE.search(formula)
    if m:
        formula = formula[:m.start()].rstrip()
    else:
        # 2) Strip trailing unparenthesised charge  Fe2+ → Fe, FeOH2+ → FeOH
        m2 = _RE_TRAIL_CHARGE.search(formula)
        if m2:
            formula = formula[:m2.start()].rstrip()

    # Build charge suffix
    if charge == 1:
        suffix = "+"
    elif charge == -1:
        suffix = "-"
    elif charge > 0:
        suffix = f"{charge}+"
    else:
        suffix = f"{abs(charge)}-"

    # Bare element symbol → no brackets  (Fe2+, Cu+)
    if _RE_BARE_ELEMENT.match(formula):
        return f"{formula}{suffix}"

    # Complex formula → brackets  [FeO4]2-, [Fe(OH)2]+
    return f"[{formula}]{suffix}"


# ======================================================================
#  Pourbaix ID mapping  (M1 → Fe$1, M2 → Fe$2, etc.)
# ======================================================================

def build_pourbaix_id_map(valence_table: List[dict]) -> Dict[str, str]:
    """Build mapping from internal_id → Pourbaix ID ``{element}${charge}``.

    The charge of the reference ion is encoded directly in the ID.
    The ``$`` separator prevents the LLM from confusing the number
    with the element valence.

    Example::

        {"M4": "Cu$+1", "M1": "Cu$+2", "M2": "Fe$+2", "M3": "Fe$+3"}
    """
    id_map: Dict[str, str] = {}
    for row in valence_table:
        el = row["element"]
        charge = int(str(row["charge"]).replace("+", ""))
        id_map[row["internal_id"]] = f"{el}${charge:+d}"
    return id_map


def remap_to_pourbaix_ids(
    valence_table: List[dict],
    valence_offsets: Dict[str, float],
    metal_info: Dict[str, dict],
    id_map: Dict[str, str],
) -> Tuple[List[dict], Dict[str, float], Dict[str, dict]]:
    """Remap internal IDs in valence_table, offsets, and metal_info.

    Returns (new_valence_table, new_offsets, new_metal_info).
    """
    new_vt = []
    for row in valence_table:
        new_row = dict(row)
        old_id = row["internal_id"]
        new_row["original_id"] = old_id
        new_row["internal_id"] = id_map.get(old_id, old_id)
        new_vt.append(new_row)

    new_off = {id_map.get(k, k): v for k, v in valence_offsets.items()}
    new_mi = {id_map.get(k, k): v for k, v in metal_info.items()}
    return new_vt, new_off, new_mi


def remap_card_species(
    card_species: List[dict],
    id_map: Dict[str, str],
) -> List[dict]:
    """Remap internal IDs in parsed card species dicts.

    Rewrites ``species_id`` and ``stoich`` fields to use Pourbaix IDs.
    """
    _RE_MID = re.compile(r'\bM\d+')

    def _replace(m: re.Match) -> str:
        return id_map.get(m.group(), m.group())

    result = []
    for sp in card_species:
        new_sp = dict(sp)
        new_sp["species_id"] = _RE_MID.sub(_replace, sp["species_id"])
        new_sp["stoich"] = _RE_MID.sub(_replace, sp["stoich"])
        result.append(new_sp)
    return result


# ======================================================================
#  Atlas → card convention helpers
# ======================================================================

# 2.303 * R * T  at 25 °C  (kJ/mol)
_2303RT_KJ = 2.302585093 * 8.314462 * 298.15 / 1000.0   # ≈ 5.70769


def _build_ox_to_mid(valence_table: List[dict]) -> Dict[Tuple[str, int], str]:
    """Build reverse map: (element, ox_state_int) → internal_id."""
    m: Dict[Tuple[str, int], str] = {}
    for row in valence_table:
        ox = int(str(row["charge"]).replace("+", ""))
        m[(row["element"], ox)] = row["internal_id"]
    return m


def _atlas_to_card_stoich(
    sp: "AlignedAtlasSpecies",
    ox_to_mid: Dict[Tuple[str, int], str],
) -> Tuple[Dict[str, int], Optional[str]]:
    """Map atlas species → card M(i)/H stoich dict.

    Returns (stoich_dict, mid_or_None).
    mid_or_None is the internal_id if the oxidation state maps, else None.
    """
    stoich: Dict[str, int] = {}
    allocations = allocate_metal_oxidation_counts(
        sp.oxidation_state,
        sp.n_metal,
        sp.H_net,
        sp.charge,
        central_element=sp.element,
        available_states=sorted(
            ox for element, ox in ox_to_mid if element == sp.element
        ),
    )
    mapped_ids: List[str] = []
    if allocations is not None:
        for ox_num, count in allocations.items():
            if count == 0:
                continue
            comp = ox_to_mid.get(
                (sp.element, ox_num), f"{sp.element}${ox_num:+d}",
            )
            stoich[comp] = stoich.get(comp, 0) + count
            mapped_ids.append(comp)
    elif sp.n_metal:
        # This compatibility helper has no ElementReference argument.  Keep
        # the element/count rather than returning an empty composition or
        # truncating an approximate average oxidation state.
        stoich[sp.element] = sp.n_metal
    if sp.H_net != 0:
        stoich["H"] = sp.H_net
    mid = mapped_ids[0] if len(mapped_ids) == 1 else None
    return stoich, mid


def _stoich_to_id(
    stoich: Dict[str, int],
    charge: int,
    phase_bucket: str,
) -> str:
    """Generate a card-style species_id from a stoich dict.

    Examples:
        {M2: 1, H: -1}  charge=+2  → "M2.OH.z+2"
        {M1: 2, H: -6}  charge=0   solid → "M1(2).OH6.z+0(s)"
        {M2: 1}          charge=+3  → "M2.z+3"
    """
    parts: List[str] = []

    # Metals / unmapped components (sorted)
    for k in sorted(stoich.keys()):
        if k == "H":
            continue
        v = stoich[k]
        if v == 0:
            continue
        if v == 1:
            parts.append(k)
        else:
            parts.append(f"{k}({v})")

    # H component
    h = stoich.get("H", 0)
    if h > 0:
        parts.append("H" if h == 1 else f"H{h}")
    elif h < 0:
        ah = abs(h)
        parts.append("OH" if ah == 1 else f"OH{ah}")

    # Charge
    parts.append(f"z{charge:+d}")

    sid = ".".join(parts) if parts else f"z{charge:+d}"
    if phase_bucket == "solid":
        sid += "(s)"
    return sid


def _stoich_to_str(stoich: Dict[str, int]) -> str:
    """Generate card stoich string, e.g. 'Fe$1:+1 H:-1'."""
    parts: List[str] = []
    # Sort: metals/element IDs first, then ligands (L*), then H
    for k in sorted(stoich.keys(), key=lambda x: (
        1 if x.startswith("L") else 2 if x == "H" else 0,
        x,
    )):
        v = stoich[k]
        if v != 0:
            parts.append(f"{k}:{v:+d}")
    return " ".join(parts) if parts else ""

