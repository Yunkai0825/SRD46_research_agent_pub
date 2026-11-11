"""
speciation_json_input_parser.py â€” Parse speciation JSON schema into solver data.
==================================================================================

Reads a JSON file (or dict) conforming to SPECIATION_INPUT_SCHEMA.md and
converts it to the Species/Equilibrium structures that the Newton-Raphson
solver consumes.

Key transformations performed:
  1. Token resolution  â€” ``<M{i}>``/``<L{j}>`` tokens â†’ real component names.
  2. Water-reference seeding â€” H2O is an activity-one solvent anchor while
     H+ and OH- remain the declared proton/hydroxide derived components.
  3. Stepwise â†’ cumulative â€” intermediate species are resolved to a fixed
     point independent of source row order, accumulating log Î² values.
  4. OHâ» â†’ Hâº convention â€” via Kw correction.
  5. Dissolution handling â€” solid Ksp â†’ formation constant (sign flip + Kw).

Public API
----------
- ``ParsedSystem``  â€” dataclass holding all parsed data
- ``parse_speciation_json()`` â€” main entry point
"""
from __future__ import annotations

import json
import logging
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── path bootstrap: import the numcalc solver's speciation dataclasses as a
#    bare top-level package (rooted at NIST_SRD46_analysis_agent/, where the
#    numcalc pipeline lives) WITHOUT going through the
#    `NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.` package prefix, whose
#    __init__ eagerly imports the full analysis-agent
#    stack. ────────────────────────────────────────────────────────────────
_ANALYSIS_ROOT = Path(__file__).absolute().parents[5]   # NIST_SRD46_analysis_agent/
if str(_ANALYSIS_ROOT) not in sys.path:
    sys.path.insert(0, str(_ANALYSIS_ROOT))

from NIST_SRD46_calc_input_building_agentic_pipeline.repair_support.contracts import SourceRepairRequired, canonical_sha256, source_identity

from NIST_SRD46_core_numcalc_pipeline.thermodynamics_helpers.speciation_dataclasses import (
    Kw_LOG,
    Species, SpeciesType, Equilibrium,
    stoich_count,
)

_LOG = logging.getLogger(__name__)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  Output data class
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

@dataclass
class ParsedSystem:
    """All data extracted from a speciation JSON input file."""
    species:       Dict[str, Species]
    equilibria:    List[Equilibrium]
    metal_ids:     List[str]            # ["M1", "M2", ...]  (M0=H+ reserved)
    ligand_ids:    List[str]            # ["L1", "L2", ...]  (L0=OH- reserved)
    total_metals:  Dict[str, float | str]  # numeric or "Not defined"
    total_ligands: Dict[str, float | str]  # numeric or "Not defined"
    ionic_strength: float
    ionic_mode:    str
    metal_names:   Dict[str, str]       # {"M1": "Fe2+", ...}
    ligand_names:  Dict[str, str]       # {"L1": "citrate", ...}
    vlm_map:       Dict[str, str] = field(default_factory=dict)  # {parser sp_id â†’ vlm_id}


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  Main entry point
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def parse_speciation_json(source) -> ParsedSystem:
    """Parse a speciation JSON file or dict into solver-ready structures.

    Parameters
    ----------
    source : str, Path, or dict
        File path or pre-loaded dict conforming to the input schema.

    Returns
    -------
    ParsedSystem
    """
    if isinstance(source, (str, Path)):
        with open(source, encoding="utf-8") as fh:
            data = json.load(fh)
    else:
        data = source

    components = data["components"]
    if not isinstance(components, dict) or not components:
        raise ValueError("components must be a non-empty object")
    ionic_strength, ionic_mode = _parse_ionic_strength_settings(data)
    equations = data.get("equations", {})
    if not isinstance(equations, dict):
        raise ValueError("equations must be an object")

    # â”€â”€ 1. Parse component catalog â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    h_token: Optional[str] = None
    oh_token: Optional[str] = None
    real_metals: List[Tuple] = []      # (token, name, charge, total)
    real_ligands: List[Tuple] = []     # (token, name, charge, total)
    component_tokens: set = set()
    component_charges: Dict[str, int] = {}

    for name, info in components.items():
        if not isinstance(info, dict):
            raise ValueError(f"component {name!r} must be an object")
        token = str(info.get("spec_id", "")).strip()
        if not token or token == "Not defined":
            raise ValueError(f"component {name!r} spec_id is Not defined")
        if token in component_tokens:
            raise ValueError(f"duplicate component spec_id {token!r}")
        comp_type = info.get("type")
        if comp_type not in {"metal", "ligand"}:
            raise ValueError(
                f"component {name!r} type must be explicitly metal or ligand")
        component_tokens.add(token)
        component_charges[token] = _parse_component_charge(
            info.get("charge"), name=name)

        if name == "H+":
            h_token = token
        elif name == "OH-":
            oh_token = token
        elif info["type"] == "metal":
            real_metals.append((
                token, name, info["charge"],
                _parse_component_total(info.get("total"), name=name),
            ))
        elif info["type"] == "ligand":
            real_ligands.append((
                token, name, info["charge"],
                _parse_component_total(info.get("total"), name=name),
            ))

    # Stable sort by token (e.g. M1 before M2)
    real_metals.sort(key=lambda x: x[0])
    real_ligands.sort(key=lambda x: x[0])

    # M0=H+, L0=OH- are reserved.  Real metals start at M1, ligands at L1.
    token_to_metal_idx = {m[0]: i + 1 for i, m in enumerate(real_metals)}
    token_to_ligand_idx = {l[0]: i + 1 for i, l in enumerate(real_ligands)}

    # â”€â”€ 2. Free species â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    species: Dict[str, Species] = {}
    equilibria: List[Equilibrium] = []

    metal_ids: List[str] = []
    ligand_ids: List[str] = []
    total_metals: Dict[str, float | str] = {}
    total_ligands: Dict[str, float | str] = {}
    metal_names_map: Dict[str, str] = {}
    ligand_names_map: Dict[str, str] = {}

    for i, (token, name, charge, total) in enumerate(real_metals):
        sp_id = f"M{i + 1}"       # M1, M2, â€¦ (M0 = H+ reserved)
        metal_ids.append(sp_id)
        total_metals[sp_id] = total
        metal_names_map[sp_id] = name
        species[sp_id] = Species(
            id=sp_id, label=name, stype=SpeciesType.METAL,
            charge=charge, phase="aqueous",
            metal_idx=i + 1, ligand_idx=-1,
            stoich={f"M{i + 1}": 1},
        )

    for j, (token, name, charge, total) in enumerate(real_ligands):
        sp_id = f"L{j + 1}"       # L1, L2, â€¦ (L0 = OH- reserved)
        ligand_ids.append(sp_id)
        total_ligands[sp_id] = total
        ligand_names_map[sp_id] = name
        species[sp_id] = Species(
            id=sp_id, label=name, stype=SpeciesType.LIGAND,
            charge=charge, phase="aqueous",
            metal_idx=-1, ligand_idx=j + 1,
            stoich={f"L{j + 1}": 1},
        )

    # â”€â”€ 3. Formula registry (cumulative logÎ² from free comps) â”€
    # Registry keys are the CANONICAL form of the angle-bracketed formulas
    # that the equation builder produces (e.g. "<M1>", "<L1>", "<H>",
    # "<OH>"; see :func:`_canonical_formula_key`), while composition values
    # use bare spec_ids ("M1", "L1", "H", "OH").  Liquid water is the
    # activity-one solvent reference, not another conserved component:
    # its empty composition and zero cumulative logK make H2O disappear from
    # reaction balances without inventing an independent water DOF.
    _registry: Dict[str, _FormulaRecord] = {}
    for name, info in components.items():
        token = info["spec_id"]
        _registry[_canonical_formula_key(f"<{token}>")] = _FormulaRecord(
            composition={token: 1}, cum_logK=0.0,
        )
    _registry[_canonical_formula_key("H2O")] = _FormulaRecord(
        composition={}, cum_logK=0.0)

    seen_sp_ids: set = set()

    # â”€â”€ 4. Process every equation block â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # equations is an object with two arrays:
    #   metal_ligand_system_aqueous_only  / â€¦_dissociation_only
    # Each array entry has {metal_ligand_system, equilibria}.
    _EQ_SECTION_KEYS = (
        "metal_ligand_system_aqueous_only",
        "metal_ligand_system_dissociation_only",
    )
    flat_blocks = []
    for key in _EQ_SECTION_KEYS:
        flat_blocks.extend(equations.get(key, []))

    vlm_map: Dict[str, str] = {}

    # Resolve the reaction graph to a fixed point.  SRD-46 rows are not
    # guaranteed to be stored in dependency order (a protonation ladder may
    # arrive H2L -> H3L, HL -> H2L, H + L -> HL).  A single source-order pass
    # therefore dropped chemically resolvable entries.  Deferred reactions
    # are retried only after another reaction has registered a new formula.
    pending = [
        eq_entry
        for block in flat_blocks
        for eq_entry in block["equilibria"]
    ]
    while pending:
        deferred = []
        made_progress = False
        for eq_entry in pending:
            status = _process_one_equilibrium(
                eq_entry=eq_entry,
                registry=_registry,
                component_tokens=component_tokens,
                component_charges=component_charges,
                h_token=h_token,
                oh_token=oh_token,
                token_to_metal_idx=token_to_metal_idx,
                token_to_ligand_idx=token_to_ligand_idx,
                real_metals=real_metals,
                real_ligands=real_ligands,
                species_out=species,
                equilibria_out=equilibria,
                seen_sp_ids=seen_sp_ids,
                vlm_map_out=vlm_map,
            )
            if status == "deferred":
                deferred.append(eq_entry)
            elif status == "resolved":
                made_progress = True
        if not deferred:
            break
        if not made_progress:
            unresolved = []
            unresolved_rows = []
            for eq_entry in deferred:
                if not eq_entry.get("include_calculation", False):
                    continue
                formulas = {
                    str(item["species"])
                    for side in ("LHS", "RHS")
                    for item in eq_entry.get(side, [])
                }
                missing = sorted(
                    formula for formula in formulas
                    if _canonical_formula_key(
                        _normalize_legacy_hydroxide_formula(
                            formula, h_token=h_token, oh_token=oh_token))
                    not in _registry)
                reference = eq_entry.get("reference") or {}
                source_id = reference.get("source_database_ID") or "unknown"
                equation = eq_entry.get("equation_str") or "<equation unavailable>"
                unresolved_rows.append({"source_id": source_id, "missing_formulas": missing,
                                        "equation": equation, "reference": reference})
                unresolved.append(
                    f"{source_id}: missing={missing!r}; equation={equation}"
                )
            if unresolved:
                message = ("included equilibrium graph is unresolved after "
                           "fixed-point dependency propagation; no reactions were "
                           "silently dropped:\n  - " + "\n  - ".join(unresolved))
                raise SourceRepairRequired({
                    **source_identity(data),
                    "error_code": "unanchored_equilibrium_graph",
                    "repair_scope": "source_selection",
                    "source_path": str(source) if isinstance(source, (str, Path)) else None,
                    "input_sha256": canonical_sha256(data),
                    "components": components,
                    "unresolved_reactions": unresolved_rows,
                    "message": message,
                }, message)
            break
        pending = deferred

    return ParsedSystem(
        species=species,
        equilibria=equilibria,
        metal_ids=metal_ids,
        ligand_ids=ligand_ids,
        total_metals=total_metals,
        total_ligands=total_ligands,
        ionic_strength=ionic_strength,
        ionic_mode=ionic_mode,
        metal_names=metal_names_map,
        ligand_names=ligand_names_map,
        vlm_map=vlm_map,
    )


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  Internal helpers
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

@dataclass
class _FormulaRecord:
    """Tracks a known formula's composition and cumulative logÎ².

    ``composition`` is per ONE formula unit of the registered formula.  It
    holds floats when the source formula itself is fractional
    (``<M1>(<OH>)1.5<L1>0.5(s)``: {M1: 1, OH: 1.5, L1: 0.5}) so that later
    rows citing that formula with their own power stay exact; the emitted
    solver species is scaled to integers separately (:func:`_integral_scale`).
    """
    composition: Dict[str, float]   # {component_token: stoich_count}
    cum_logK:    float
    vlm_ids:     set = field(default_factory=set)  # all VLM records that contributed


_PHASE_TAG_RE = re.compile(r"\((?:s(?:,[^)]*)?|g)\)$")
_COUNT_RE = re.compile(r"-?\d+(?:\.\d+)?")
_ELEMENT_RE = re.compile(r"[A-Z][a-z]*")
_LOWER_TAG_RE = re.compile(r"^[a-z.\-]+$")


def _format_count(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else repr(round(float(value), 9))


def _canonical_formula_key(formula: str) -> str:
    """Canonical registry key of an equation-builder formula.

    The equation builder spells the same species differently depending on
    how the SRD-46 row wrote it: the hydroxide pair's ``[ML2]`` becomes
    ``<M1><OH>2`` while ``[M(OH)2]`` becomes ``<M1>(<OH>)2``, and
    ``<M1>2(<H>-1<L1>)2`` is ``<M1>2<H>-2<L1>2``.  Exact-string registry
    lookups cannot identify these equivalent spellings.

    The key is the sorted multiset of tokens with their counts (parenthesised
    groups multiplied through, decimal and negative counts allowed), plus
    verbatim isomer tags such as ``(cis)`` and the trailing phase tag
    (``(s)``, ``(s,goethite)``, ``(g)``).  Component tokens ``<...>`` and
    literal element symbols (``O`` of ``<M1>O(s)``, ``Mo`` of ``Mo7O24``)
    are distinct token kinds.  Any character outside that grammar makes the
    function return the formula unchanged (identity matching only), so an
    unforeseen spelling can never alias two different species.
    """
    text = formula.strip()
    phase = ""
    phase_match = _PHASE_TAG_RE.search(text)
    if phase_match:
        phase = phase_match.group(0)
        text = text[: phase_match.start()]
    counts: Dict[str, float] = {}
    tags: List[str] = []

    def read_count(pos: int) -> Tuple[float, int]:
        match = _COUNT_RE.match(text, pos)
        if match:
            return float(match.group(0)), match.end()
        return 1.0, pos

    def walk(start: int, stop: int, factor: float) -> bool:
        pos = start
        while pos < stop:
            ch = text[pos]
            if ch == "<":
                end = text.find(">", pos, stop)
                if end < 0:
                    return False
                token = text[pos + 1:end]
                count, pos = read_count(end + 1)
                counts[f"<{token}>"] = counts.get(f"<{token}>", 0.0) + count * factor
            elif ch == "(":
                depth = 1
                end = pos + 1
                while end < stop and depth:
                    if text[end] == "(":
                        depth += 1
                    elif text[end] == ")":
                        depth -= 1
                    end += 1
                if depth:
                    return False
                inner_start, inner_stop = pos + 1, end - 1
                count, pos = read_count(end)
                inner = text[inner_start:inner_stop]
                if _LOWER_TAG_RE.match(inner):
                    tags.append(f"({inner})")
                elif not walk(inner_start, inner_stop, factor * count):
                    return False
            elif ch.isupper():
                match = _ELEMENT_RE.match(text, pos)
                if match is None:
                    return False
                symbol = match.group(0)
                count, pos = read_count(match.end())
                counts[symbol] = counts.get(symbol, 0.0) + count * factor
            else:
                return False
        return True

    if not text or not walk(0, len(text), 1.0):
        return formula
    items = [f"{token}:{_format_count(count)}" for token, count in sorted(counts.items())
             if abs(count) > 1e-12]
    return "".join(items) + "".join(sorted(tags)) + phase


_MAX_INTEGRAL_SCALE = 24


def _tidy_counts(composition: Dict[str, float]) -> Dict[str, float]:
    """Drop zero counts; an integral float becomes an int, a fraction is
    rounded to 9 digits (the shared :func:`stoich_count` convention)."""
    tidy: Dict[str, float] = {}
    for token, count in composition.items():
        if abs(count) <= 1e-12:
            continue
        tidy[token] = stoich_count(count)
    return tidy


def _integral_charge(charge: float, *, formula: str, detail: str = "") -> int:
    """Return the species charge as an int; a fractional charge is an error.

    A fractional formula unit (``<M1>(<OH>)1.5<L1>0.5(s)``) carries fractional
    counts into the solver, but its charge must still be a whole number
    (2 - 1.5 - 0.5 = 0 here); a fraction left over means the row's powers do
    not describe one species IN THIS COMPONENT BASIS and the card must not
    pretend otherwise.  The card fails loud (the file's law: no reaction is
    dropped silently); the row's own ``include_calculation: false`` is the
    recorded way to leave it out, and ``detail`` names what the refusal
    needs (the VLM row, the counts, the component charges).
    """
    if abs(charge - round(charge)) > 1e-9:
        raise ValueError(
            f"species {formula!r} resolves to a fractional charge "
            f"{round(charge, 9)!r}{detail}")
    return int(round(charge))


def _integral_scale(
    composition: Dict[str, float],
    cum_logK: float,
    *,
    formula: str,
) -> Tuple[Dict[str, int], float, int]:
    """Smallest whole-number multiple of a fractional composition.

    This report utility scales the composition and log beta to a whole
    formula unit (n = 2 for ``Cu(OH)1.5Cl0.5(s)`` -> ``Cu2(OH)3Cl``).
    It is not applied to emitted solver species, which carry SRD-46's
    fractional formula units as written. Returns
    ``(integer composition, scaled cum_logK, n)``; n == 1 when the
    composition is already integral.
    """
    for n in range(1, _MAX_INTEGRAL_SCALE + 1):
        scaled = {token: count * n for token, count in composition.items()}
        if all(abs(value - round(value)) <= 1e-9 for value in scaled.values()):
            return ({token: int(round(value)) for token, value in scaled.items()
                     if int(round(value)) != 0},
                    cum_logK * n, n)
    raise ValueError(
        f"species {formula!r} has a fractional composition {composition!r} that no "
        f"integer multiple up to {_MAX_INTEGRAL_SCALE} makes whole")


def _parse_component_total(value: Any, *, name: str) -> float | str:
    """Preserve an explicitly undefined reference-card total.

    Component totals in an SRD reference card are metadata placeholders;
    they are not solver inputs.  A calculation card must replace every
    ``"Not defined"`` value before numerical construction.  Reject other
    strings here so misspellings cannot later turn into an implicit zero.
    """
    if value == "Not defined":
        return "Not defined"
    if value is None:
        raise ValueError(
            f"component {name!r} is missing 'total'; use the literal "
            "'Not defined' in a reference card or declare a numeric total")
    if isinstance(value, bool):
        raise ValueError(f"component {name!r} total must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"component {name!r} total must be numeric or exactly "
            "'Not defined', got {value!r}") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"component {name!r} total must be finite and >= 0")
    return number


def _parse_component_charge(value: Any, *, name: str) -> int:
    if value is None or value == "Not defined" or isinstance(value, bool):
        raise ValueError(f"component {name!r} charge is Not defined")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"component {name!r} charge must be numeric") from exc
    if not math.isfinite(number) or not number.is_integer():
        raise ValueError(f"component {name!r} charge must be a finite integer")
    return int(number)


def _parse_ionic_strength_settings(data: dict[str, Any]) -> tuple[float, str]:
    if "ionic_strength_mode" not in data:
        raise ValueError(
            "ionic_strength_mode is Not defined; explicitly declare fixed or auto")
    raw_mode = data["ionic_strength_mode"]
    if not isinstance(raw_mode, str):
        raise ValueError("ionic_strength_mode must be the string 'fixed' or 'auto'")
    ionic_mode = raw_mode.strip().lower()
    if ionic_mode not in {"fixed", "auto"}:
        raise ValueError(f"Unsupported ionic_strength_mode: {ionic_mode!r}")
    if "ionic_strength" not in data:
        raise ValueError("ionic_strength value is Not defined")
    raw_strength = data["ionic_strength"]
    if isinstance(raw_strength, bool) or raw_strength is None:
        raise ValueError("ionic_strength must be an explicit numeric value")
    if isinstance(raw_strength, str) and raw_strength.strip().lower() == "auto":
        if ionic_mode != "auto":
            raise ValueError("ionic_strength='auto' contradicts fixed ionic_strength_mode")
        ionic_strength = 0.0
    else:
        try:
            ionic_strength = float(raw_strength)
        except (TypeError, ValueError) as exc:
            raise ValueError("ionic_strength must be an explicit numeric value") from exc
    if not math.isfinite(ionic_strength) or ionic_strength < 0:
        raise ValueError("ionic_strength must be finite and >= 0")
    return ionic_strength, ionic_mode


def _validate_equilibrium_side(value: Any, *, side: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"equilibrium {side} must be a non-empty list")
    validated: list[dict[str, Any]] = []
    for index, entry in enumerate(value):
        context = f"equilibrium {side}[{index}]"
        if not isinstance(entry, dict):
            raise ValueError(f"{context} must be an object")
        species = entry.get("species")
        if species is None or not str(species).strip():
            raise ValueError(f"{context} species is Not defined")
        if "power" not in entry or isinstance(entry["power"], bool):
            raise ValueError(f"{context} power is Not defined")
        try:
            power_number = float(entry["power"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{context} power must be numeric") from exc
        # SRD-46 writes fractional powers for half-formula-unit solids
        # (``[OH]^1.5 + [L]^0.5``), so a power is any finite positive number;
        # it stays an int when integral.
        if not math.isfinite(power_number) or power_number <= 0:
            raise ValueError(f"{context} power must be a finite positive number")
        power: int | float = (int(power_number) if power_number.is_integer()
                              else power_number)
        phase = entry.get("phase")
        if phase is None or not str(phase).strip():
            raise ValueError(f"{context} phase is Not defined")
        phase = str(phase).strip().lower()
        if phase not in {"aqueous", "solid", "dissolution", "gas"}:
            raise ValueError(f"{context} phase is unsupported: {phase!r}")
        validated.append({**entry, "species": str(species),
                          "power": power, "phase": phase})
    return validated


def _normalize_legacy_hydroxide_formula(
    formula: str,
    *,
    h_token: Optional[str],
    oh_token: Optional[str],
) -> str:
    """Migrate the exact hydroxide corruption emitted by the old scanner.

    Historical generated cards can contain ``O<H>`` or ``<O<H>>`` because
    the former equation builder interpreted the H in an already-seen OH token
    as a proton placeholder.  This is a lossless grammar repair, not a
    chemical fallback: both spellings unambiguously denote the declared
    hydroxide component.
    """
    if not h_token or not oh_token:
        return formula
    corrupt = f"O<{h_token}>"
    repaired = formula.replace(f"<{corrupt}>", f"<{oh_token}>")
    return repaired.replace(corrupt, f"<{oh_token}>")


def _process_one_equilibrium(
    *,
    eq_entry: dict,
    registry: Dict[str, _FormulaRecord],
    component_tokens: set,
    component_charges: Dict[str, int],
    h_token: Optional[str],
    oh_token: Optional[str],
    token_to_metal_idx: Dict[str, int],
    token_to_ligand_idx: Dict[str, int],
    real_metals: list,
    real_ligands: list,
    species_out: Dict[str, Species],
    equilibria_out: List[Equilibrium],
    seen_sp_ids: set,
    vlm_map_out: Dict[str, str],
) -> str:
    """Resolve a single equilibrium entry and append Species/Equilibrium."""

    # â”€â”€ Check include_calculation flag â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if not isinstance(eq_entry, dict):
        raise ValueError("equilibrium entry must be an object")
    if "include_calculation" not in eq_entry \
            or not isinstance(eq_entry["include_calculation"], bool):
        raise ValueError(
            "equilibrium include_calculation must be explicitly true or false")
    include = eq_entry["include_calculation"]

    raw_log_k = eq_entry.get("log_K")
    if raw_log_k is None or isinstance(raw_log_k, bool):
        raise ValueError("equilibrium log_K is Not defined")
    try:
        logK = float(raw_log_k)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"equilibrium log_K must be numeric, got {raw_log_k!r}") from exc
    if not math.isfinite(logK):
        raise ValueError("equilibrium log_K must be finite")
    lhs_entries = _validate_equilibrium_side(eq_entry.get("LHS"), side="LHS")
    rhs_entries = _validate_equilibrium_side(eq_entry.get("RHS"), side="RHS")
    for item in lhs_entries + rhs_entries:
        item["species"] = _normalize_legacy_hydroxide_formula(
            item["species"], h_token=h_token, oh_token=oh_token,
        )

    # â”€â”€ Identify the ONE unknown formula â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    all_formulas: set = set()
    for e in lhs_entries:
        all_formulas.add(e["species"])
    for e in rhs_entries:
        all_formulas.add(e["species"])

    # Registry lookups go through the canonical key so that the same species
    # written two ways (``<M1><OH>2`` / ``<M1>(<OH>)2``) is one entry.
    key_of = {f: _canonical_formula_key(f) for f in all_formulas}
    unknown_formulas = [f for f in all_formulas if key_of[f] not in registry]

    if len(unknown_formulas) == 0:
        return "complete"              # redundant / all-known reaction
    if len({key_of[f] for f in unknown_formulas}) > 1:
        return "deferred"              # retry after prerequisites resolve

    unknown_formula = unknown_formulas[0]
    unknown_key = key_of[unknown_formula]
    unknown_on_lhs = any(key_of[e["species"]] == unknown_key for e in lhs_entries)

    # â”€â”€ Determine phase of the unknown â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    is_dissolution = False
    is_gas = False
    product_phase = "aqueous"
    for e in lhs_entries + rhs_entries:
        if key_of[e["species"]] == unknown_key:
            product_phase = e["phase"]
            if product_phase == "solid":
                is_dissolution = True
                product_phase = "dissolution"
            elif product_phase == "gas":
                # ``[CO2(g)] + [H2O] <=> [H2L]``: the gas is a species of the
                # card (its own id, the "Gas Species" block of the md card)
                # but never a solver unknown.
                is_gas = True
            break

    # â”€â”€ Compute cumulative logÎ² and composition â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Convention:
    #   unknown on RHS  â†’  logÎ² = +logK + Î£(LHSÂ·Î²) âˆ’ Î£(RHS_knownÂ·Î²)
    #   unknown on LHS  â†’  logÎ² = âˆ’logK + Î£(RHSÂ·Î²) âˆ’ Î£(LHS_knownÂ·Î²)
    sign = -1 if unknown_on_lhs else 1
    unknown_side = lhs_entries if unknown_on_lhs else rhs_entries
    other_side = rhs_entries if unknown_on_lhs else lhs_entries
    source = [e for e in other_side if key_of[e["species"]] != unknown_key]
    drain = [e for e in unknown_side if key_of[e["species"]] != unknown_key]
    # The unknown's own power: ``[M]^2 + [L]^2 <=> [ML]^2`` defines TWO
    # formula units, so the accumulated composition and log K are divided
    # by it below.  A token that also appears on the other side nets out.
    unknown_power = (sum(e["power"] for e in unknown_side
                         if key_of[e["species"]] == unknown_key)
                     - sum(e["power"] for e in other_side
                           if key_of[e["species"]] == unknown_key))
    if unknown_power <= 0:
        raise ValueError(
            f"species {unknown_formula!r} has a net power of {unknown_power} "
            "in the equation that defines it")

    cum_logK = sign * logK
    composition: Dict[str, float] = {}
    # Collect all VLM IDs from this equilibrium and all chain dependencies
    _this_vlm = eq_entry.get("reference", {}).get("source_database_ID", "")
    contributing_vlms: set = {_this_vlm} if _this_vlm else set()

    for e in source:
        pwr = e["power"]
        rec = registry.get(key_of[e["species"]])
        if rec is None:
            continue                   # shouldn't happen
        cum_logK += pwr * rec.cum_logK
        contributing_vlms |= rec.vlm_ids
        for tk, cnt in rec.composition.items():
            composition[tk] = composition.get(tk, 0) + pwr * cnt

    for e in drain:
        pwr = e["power"]
        rec = registry.get(key_of[e["species"]])
        if rec is None:
            continue
        cum_logK -= pwr * rec.cum_logK
        contributing_vlms |= rec.vlm_ids
        for tk, cnt in rec.composition.items():
            composition[tk] = composition.get(tk, 0) - pwr * cnt

    if unknown_power != 1:
        cum_logK /= unknown_power
        composition = {tk: cnt / unknown_power for tk, cnt in composition.items()}
    composition = _tidy_counts(composition)

    # Register the formula with its full VLM chain. The record keeps the
    # composition per formula unit as written (fractions included) so that a
    # later row citing ``[M(OH)1.5L0.5(s)]^2`` stays exact. The species
    # emitted to the solver carries the same fractions: SRD-46's
    # half-formula-unit solids are not scaled to a whole formula unit.
    registry[unknown_key] = _FormulaRecord(
        composition=dict(composition), cum_logK=cum_logK,
        vlm_ids=contributing_vlms,
    )

    # â”€â”€ OH â†’ H convention + Kw correction â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    n_oh = composition.get(oh_token, 0) if oh_token else 0
    h_count = composition.get(h_token, 0) if h_token else 0
    r = h_count - n_oh
    final_logK = cum_logK + n_oh * Kw_LOG

    # â”€â”€ Identify real metal and real ligand â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    metal_idx = -1
    p = 0
    for tk, mi in token_to_metal_idx.items():
        cnt = composition.get(tk, 0)
        if cnt != 0:
            p = cnt
            metal_idx = mi
            break

    ligand_idx = -1
    q = 0
    for tk, li in token_to_ligand_idx.items():
        cnt = composition.get(tk, 0)
        if cnt != 0:
            q = cnt
            ligand_idx = li
            break

    # â”€â”€ Build stoich dict (captures ALL metals and ligands) â”€â”€â”€
    stoich: Dict[str, float] = {}  # int when integral, float for a fractional formula unit
    for tk, mi in token_to_metal_idx.items():
        cnt = composition.get(tk, 0)
        if cnt != 0:
            stoich[f"M{mi}"] = cnt
    for tk, li in token_to_ligand_idx.items():
        cnt = composition.get(tk, 0)
        if cnt != 0:
            stoich[f"L{li}"] = cnt
    if r != 0:
        stoich["H"] = r

    # â”€â”€ Parse HxLy grouped stoichiometry (display-only) â”€â”€â”€â”€â”€â”€
    stoich_hlx = _validated_formula_hlx(
        unknown_formula,
        h_token or "H",
        oh_token or "OH",
        token_to_metal_idx,
        token_to_ligand_idx,
        stoich,
    )

    # â”€â”€ Species type â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if p == 0 and q > 0 and r > 0:
        stype = SpeciesType.PROTONATED_LIGAND
    else:
        stype = SpeciesType.COMPLEX

    # â”€â”€ Species ID â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    sp_id = _make_sp_id(metal_idx, ligand_idx, p, q, r, is_dissolution,
                        is_gas=is_gas)
    if sp_id in seen_sp_ids:
        # Several formulas can share one stoichiometry: solids (goethite vs
        # hematite), isomers (cis / trans), a species spelled two ways the
        # canonical key does not unify.  Keep every one so the most stable
        # is selected (solids) or the concentrations add (isomers); a
        # dropped species would silently lose its SRD-46 constant.  Solids
        # use the ``_s2`` shape; an aqueous id ends in a digit
        # (``...p1q2``), so its suffix is ``_2`` rather than a bare ``2``.
        joiner = "" if sp_id.endswith(("_s", "_g")) else "_"
        n = 2
        while f"{sp_id}{joiner}{n}" in seen_sp_ids:
            n += 1
        if not is_dissolution:
            _LOG.warning(
                "species %r shares the stoichiometry of %s; kept as %s",
                unknown_formula, sp_id, f"{sp_id}{joiner}{n}")
        sp_id = f"{sp_id}{joiner}{n}"
    seen_sp_ids.add(sp_id)

    # â”€â”€ Skip disabled equilibria (formula already registered) â”€
    if not include:
        return "resolved"

    # â”€â”€ Compute product charge from composition â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # After the include gate on purpose: a row the card-building layer has
    # switched off (``include_calculation: false``) only registers its
    # formula for the rows that cite it; its charge is never judged, so a
    # known defective row can be left out without failing the card.
    charge_sum = 0.0
    for tk, cnt in composition.items():
        if tk not in component_charges:
            raise ValueError(
                f"resolved stoichiometry references component {tk!r} with no charge")
        charge_sum += cnt * component_charges[tk]
    charge = _integral_charge(
        charge_sum, formula=unknown_formula,
        detail=(f" (row {_this_vlm or 'unknown'}; counts {composition!r}; "
                f"component charges "
                f"{ {tk: component_charges[tk] for tk in composition}!r}); "
                "the row's powers do not describe one species in this "
                "component basis -- set its include_calculation to false "
                "to leave it out"),
    )

    # â”€â”€ Display label â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if is_dissolution or is_gas:
        # Resolve formula tokens to produce a readable solid / gas name.
        # Tokens in the formula are angle-bracketed: <M1>, <L1>, <H>, <OH>.
        label = unknown_formula
        for tok, mi_ in token_to_metal_idx.items():
            label = label.replace(
                f"<{tok}>", real_metals[mi_ - 1][1].rstrip("+-0123456789"))
        if oh_token:
            label = label.replace(f"<{oh_token}>", "(OH)")
        if h_token:
            label = label.replace(f"<{h_token}>", "H")
        for tok, li_ in token_to_ligand_idx.items():
            label = label.replace(f"<{tok}>", f"({real_ligands[li_ - 1][1]})")
        # A fractional formula unit keeps its written counts in the label:
        # Cu(OH)1.5(Chloride ion)0.5(s) stays as SRD-46 wrote it.
    elif composition == {h_token: 1, oh_token: 1}:
        # The water self-ion product [<H>] + [<OH>] <=> [<H><OH>] has no
        # metal, ligand or net proton, so _build_label has nothing to name.
        label = "H2O"
    else:
        m_name = real_metals[metal_idx - 1][1] if metal_idx > 0 else ""
        l_name = real_ligands[ligand_idx - 1][1] if ligand_idx > 0 else ""
        label = _build_label(m_name, l_name, p, q, r,
                             is_dissolution, charge)

    # â”€â”€ Create Species â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    sp = Species(
        id=sp_id, label=label, stype=stype,
        charge=charge, phase=product_phase,
        metal_idx=metal_idx, ligand_idx=ligand_idx,
        stoich=dict(stoich),
        stoich_hlx=stoich_hlx,
    )
    species_out[sp_id] = sp

    # â”€â”€ Record VLM provenance (parser sp_id â†’ all contributing VLM IDs) â”€
    # contributing_vlms is the full set propagated through the logÎ² chain.
    if contributing_vlms:
        vlm_map_out[sp_id] = ", ".join(sorted(contributing_vlms))

    # â”€â”€ Create Equilibrium â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    eq_label = eq_entry.get("constant_type", "") or f"Î²({sp_id})"
    eq = Equilibrium(
        id=f"beta_{sp_id}", label=eq_label,
        log_k=final_logK, species_id=sp_id,
        stoich=dict(stoich),
    )
    equilibria_out.append(eq)
    return "resolved"


# â”€â”€ HxLy formula parser â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _parse_formula_hlx(
    formula: str,
    h_token: str,
    oh_token: str,
    token_to_metal_idx: Dict[str, int],
    token_to_ligand_idx: Dict[str, int],
) -> Optional[List[Tuple[str, int]]]:
    """Parse a formula string into HxLy grouped stoichiometry.

    Returns a list of ``(component_key, count)`` tuples representing the
    grouped structure of the species, or ``None`` if parsing yields nothing.

    Examples::

        "<M1>2(<H>-1<L2>)<L2>"  â†’  [("M1", 2), ("H-1L2", 1), ("L2", 1)]
        "<M1><H><L1>"           â†’  [("M1", 1), ("HL1", 1)]
        "<M1>(<OH>)3"           â†’  [("M1", 1), ("OH", 3)]
    """
    clean = _PHASE_TAG_RE.sub('', formula)
    if not clean:
        return None

    result: List[Tuple[str, int]] = []
    i = 0
    pending_h: Optional[int] = None

    while i < len(clean):
        if clean[i] == '(':
            depth = 1
            j = i + 1
            while j < len(clean) and depth > 0:
                if clean[j] == '(':
                    depth += 1
                elif clean[j] == ')':
                    depth -= 1
                j += 1
            group_content = clean[i + 1 : j - 1]
            i = j
            group_count, i = _read_count_at(clean, i)

            h_in_group, lig_in_group, oh_in_group = _parse_group_tokens(
                group_content, h_token, oh_token, token_to_ligand_idx,
            )
            if lig_in_group:
                total_h = h_in_group + (pending_h or 0)
                hlx = _make_hlx_key(total_h, lig_in_group)
                result.append((hlx, group_count))
            elif oh_in_group > 0:
                result.append(("OH", oh_in_group * group_count))
            pending_h = None

        elif clean[i] == '<':
            j = clean.index('>', i)
            token = clean[i + 1 : j]
            i = j + 1
            count, i = _read_count_at(clean, i)

            if token in token_to_metal_idx:
                if pending_h is not None:
                    result.append(("H", pending_h))
                    pending_h = None
                result.append((token, count))
            elif token == h_token:
                pending_h = (pending_h or 0) + count
            elif token == oh_token:
                if pending_h is not None:
                    result.append(("H", pending_h))
                    pending_h = None
                result.append(("OH", count))
            elif token in token_to_ligand_idx:
                if pending_h is not None:
                    hlx = _make_hlx_key(pending_h, token)
                    result.append((hlx, count))
                    pending_h = None
                else:
                    result.append((token, count))
        else:
            i += 1

    if pending_h is not None:
        result.append(("H", pending_h))

    return result or None


def _validated_formula_hlx(
    formula: str,
    h_token: str,
    oh_token: str,
    token_to_metal_idx: Dict[str, int],
    token_to_ligand_idx: Dict[str, int],
    expected_stoich: Dict[str, int],
) -> Optional[List[Tuple[str, int]]]:
    """Return grouped display stoichiometry only when it is lossless.

    Some source formulas contain literal atoms outside the registered token
    grammar (for example ``<M1>O(s)``).  In that case the formula parser can
    recognize a prefix but cannot encode the complete reaction-derived
    stoichiometry.  Returning ``None`` makes the card writer use the complete
    flat representation instead of serializing the partial prefix.
    """

    grouped = _parse_formula_hlx(
        formula,
        h_token,
        oh_token,
        token_to_metal_idx,
        token_to_ligand_idx,
    )
    if grouped and _flatten_hlx_stoich(grouped) == expected_stoich:
        return grouped
    return None


def _read_count_at(s: str, i: int) -> Tuple[int, int]:
    """Read an optional integer count at position *i*."""
    if i >= len(s):
        return 1, i
    m = re.match(r'-?\d+', s[i:])
    if m:
        return int(m.group()), i + m.end()
    return 1, i


def _parse_group_tokens(
    content: str,
    h_token: str,
    oh_token: str,
    token_to_ligand_idx: Dict[str, int],
) -> Tuple[int, Optional[str], int]:
    """Parse tokens inside a parenthesized group.

    Returns ``(h_sum, ligand_key_or_None, oh_count)``.
    """
    h_sum = 0
    lig_key: Optional[str] = None
    oh_count = 0
    i = 0
    while i < len(content):
        if content[i] == '<':
            j = content.index('>', i)
            token = content[i + 1 : j]
            i = j + 1
            count, i = _read_count_at(content, i)
            if token == h_token:
                h_sum += count
            elif token == oh_token:
                oh_count += count
            elif token in token_to_ligand_idx:
                lig_key = token
        else:
            i += 1
    return h_sum, lig_key, oh_count


def _make_hlx_key(h_count: int, lig_key: str) -> str:
    """Build an HxLy key string from proton count and ligand key."""
    if h_count == 0:
        return lig_key
    elif h_count == 1:
        return f"H{lig_key}"
    else:
        return f"H{h_count}{lig_key}"


_HXL_COMPONENT_RE = re.compile(r"^H(-?\d*)(L\d+)$")


def _flatten_hlx_stoich(
    grouped: List[Tuple[str, int]],
) -> Dict[str, int]:
    """Expand grouped HxL/OH display tokens to the solver's flat basis."""

    flat: Dict[str, int] = {}
    for key, count in grouped:
        match = _HXL_COMPONENT_RE.match(key)
        if match:
            h_text, ligand_key = match.groups()
            h_count = int(h_text) if h_text else 1
            flat["H"] = flat.get("H", 0) + h_count * count
            flat[ligand_key] = flat.get(ligand_key, 0) + count
        elif key == "OH":
            flat["H"] = flat.get("H", 0) - count
        else:
            flat[key] = flat.get(key, 0) + count
    return {key: value for key, value in flat.items() if value != 0}


# â”€â”€ ID & label helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _make_sp_id(
    metal_idx: int, ligand_idx: int,
    p: float, q: float, r: float,
    is_dissolution: bool,
    is_gas: bool = False,
) -> str:
    """Build a unique species ID string.

    ``is_gas`` appends ``_g`` so ``[CO2(g)]`` does not collide with aqueous
    ``H2L`` of the same stoichiometry. Integral counts print as integers
    (``M1_L1_p2q1OH3_s``); a fractional formula unit prints its counts as
    written (``M1_L1_p1q0.5OH1.5_s``).
    """
    p_text, q_text = _format_count(p), _format_count(q)
    if p == 0 and q > 0 and r > 0:
        # Protonated ligand; the ligand count is part of the id so that
        # HL and HL2 (p=0, r=1, q=1 vs 2) stay two species.
        sp_id = f"H{_format_count(r)}_L{ligand_idx}"
        if q != 1:
            sp_id += f"q{q_text}"
    elif metal_idx >= 0 and ligand_idx >= 0:
        sp_id = f"M{metal_idx}_L{ligand_idx}_p{p_text}q{q_text}"
        if r > 0:
            sp_id += f"H{_format_count(r)}"
        elif r < 0:
            sp_id += f"OH{_format_count(abs(r))}"
    elif metal_idx >= 0:
        sp_id = f"M{metal_idx}_p{p_text}q0"
        if r > 0:
            sp_id += f"H{_format_count(r)}"
        elif r < 0:
            sp_id += f"OH{_format_count(abs(r))}"
    else:
        # Fallback (rare)
        sp_id = f"p{p_text}q{q_text}r{_format_count(r)}"
    if is_dissolution:
        sp_id += "_s"
    if is_gas:
        sp_id += "_g"
    return sp_id


def _build_label(
    metal_name: str, ligand_name: str,
    p: int, q: int, r: int,
    is_dissolution: bool,
    charge: int = 0,
) -> str:
    """Build a human-readable display label with charge.

    Format examples:
      [Fe(OH)4]2-    (charge -2)
      [Fe(OH)]+      (charge +1)
      Fe(citr)H      (charge  0, no brackets)
      [Fe2(citr)2(OH)2]4-
    """
    parts: List[str] = []

    # Protonated ligand (no metal)
    if p == 0 and q > 0 and r > 0:
        h_part = "H" if r == 1 else f"H{r}"
        formula = f"{h_part}{ligand_name}"
        return _charge_label(formula, charge)

    # Metal part
    if metal_name and p > 0:
        m = metal_name.rstrip("+-0123456789")
        parts.append(m if p == 1 else f"{m}{p}")

    # Ligand part
    if ligand_name and q > 0:
        l_abbr = ligand_name[:4]
        parts.append(f"({l_abbr})" if q == 1 else f"({l_abbr}){q}")

    # Proton / hydroxide part
    if r > 0:
        parts.append("H" if r == 1 else f"H{r}")
    elif r < 0:
        n_oh = abs(r)
        parts.append("(OH)" if n_oh == 1 else f"(OH){n_oh}")

    formula = "".join(parts)
    if is_dissolution:
        formula += "(s)"
    label = _charge_label(formula, charge) if not is_dissolution else formula
    return label or "?"


def _charge_label(formula: str, charge: int) -> str:
    """Wrap a formula with charge annotation.

    Neutral â†’ ``Fe(citr)H``  (no brackets)
    Â±1     â†’ ``[Fe(OH)]+`` / ``[Fe(OH)4]-``
    |n|>1  â†’ ``[Fe(OH)4]2-`` / ``[Fe2(OH)2]4+``
    """
    if charge == 0:
        return formula
    if charge == 1:
        suffix = "+"
    elif charge == -1:
        suffix = "-"
    elif charge > 0:
        suffix = f"{charge}+"
    else:
        suffix = f"{abs(charge)}-"
    return f"[{formula}]{suffix}"
