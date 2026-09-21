"""free_energy_md_card_reader.py
Parse a Free-Energy Markdown Card back into a ``FreeEnergyReport``.

This is the inverse of ``free_energy_md_card_generation.py``.  Given
the markdown text (or a ``.md`` file path), it reconstructs the full
``FreeEnergyReport`` dataclass that the Gibbs minimiser needs.

The parser extracts data from the fixed-format markdown tables in
Sections 2–5.  The solver only needs the species free energies from
Section 5.

Design goals:
  • The MD card is the canonical input — JSON is not required.
  • Solver-bound chemistry is strict: charge, phase, standard-energy,
    stoichiometry, and inclusion fields may not be inferred from blanks.
    Descriptive sections remain optional.
  • ``excluded_species`` is read from the header line
    ``**Excluded species**: …`` and from the species table
    (species removed from Section 5 are implicitly excluded).
"""
from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from card_management_helpers.longpath_io import exists_long, read_text_long
from thermodynamics_helpers.gibbs_value_calc_from_logK_eq_map_helpers.free_energy_network_calc_helper import (
    FreeEnergyReport,
    SpeciesEnergy,
    ComponentMeta,
    EquilibriumMeta,
    SolventMeta,
    ValenceGroup,
    ValenceGroupEntry,
    LigandMicroValence,
)
from thermodynamics_helpers.gibbs_value_calc_from_logK_eq_map_helpers.canonical_standard_state_rulebook import (
    CanonicalRuleBook,
    CanonicalRef,
)

R_kJ = 8.314e-3
LN10 = math.log(10)

# ══════════════════════════════════════════════════════════════════
#  Low-level markdown table parser
# ══════════════════════════════════════════════════════════════════

_PIPE_RE = re.compile(r"(?:^\||\|$)")  # leading/trailing pipes
_SEP_RE = re.compile(r"^\|[\s:|-]+\|$")  # separator row  |---|---|


def _parse_md_table(lines: List[str], start: int) -> Tuple[List[Dict[str, str]], int]:
    """Parse a pipe-delimited markdown table starting at *start*.

    Returns (list-of-row-dicts, next-line-index-after-table).
    Each row dict maps column-header → cell-value (stripped strings).
    """
    if start >= len(lines):
        return [], start

    # Find header row (first row starting with |)
    idx = start
    while idx < len(lines) and not lines[idx].strip().startswith("|"):
        # Stop if we hit a section heading — no table in this section
        if lines[idx].strip().startswith("#"):
            return [], idx
        idx += 1
    if idx >= len(lines):
        return [], idx

    header_line = lines[idx].strip()
    headers = [h.strip() for h in _PIPE_RE.sub("", header_line).split("|")]
    idx += 1

    # Skip separator row
    if idx < len(lines) and _SEP_RE.match(lines[idx].strip()):
        idx += 1

    # Parse data rows
    rows: List[Dict[str, str]] = []
    while idx < len(lines):
        line = lines[idx].strip()
        if not line.startswith("|"):
            break
        if _SEP_RE.match(line):
            idx += 1
            continue
        cells = [c.strip() for c in _PIPE_RE.sub("", line).split("|")]
        row = {}
        for i, h in enumerate(headers):
            row[h] = cells[i] if i < len(cells) else ""
        rows.append(row)
        idx += 1

    return rows, idx


def _find_section(lines: List[str], heading_prefix: str) -> int:
    """Return the line index of the first heading matching *heading_prefix*, or -1."""
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#") and heading_prefix in stripped:
            return i
    return -1


def _parse_stoich(stoich_str: str) -> Dict[str, int]:
    """Parse bracket-tokenized stoich, e.g. '[Cu$+2]:+1, [L1]:+1, [H]:-2'.

    Also accepts nested HxLy bracket notation: '[[H]-1[L2]]:+1, [[H]2[L1]]:+1'.
    Also accepts legacy formats: '[L]2:+1' and 'Cu$+2:+1 L1:+1 H:-2'.
    """
    if not stoich_str or stoich_str == "\u2014":
        raise ValueError("species stoichiometry is Not defined")
    d: Dict[str, int] = {}
    # Normalise: comma-separated → split on commas; legacy space-separated → split on spaces
    parts = [p.strip() for p in stoich_str.replace(",", " ").split() if p.strip()]
    _hlx_bracket_re = re.compile(r'^\[\[H\](-?\d*)\[([^\]]+)\]\]:([+-]?\d+)$')
    _bracket_re = re.compile(r'^\[([^\]]+)\](\d*):([+-]?\d+)$')
    for token in parts:
        if ":" not in token:
            raise ValueError(f"malformed species stoichiometry token {token!r}")
        # Nested HxLy brackets: [[H]-1[L2]]:+1 → H-1L2
        m = _hlx_bracket_re.match(token)
        if m:
            h_digits, lig, val = m.group(1), m.group(2), m.group(3)
            key = f"H{h_digits}{lig}"  # e.g. H-1L2, H2L1, HL1
            d[key] = int(val)
            continue
        m = _bracket_re.match(token)
        if m:
            base, idx, val = m.group(1), m.group(2), m.group(3)
            key = base + idx  # e.g. [L]2 → L2, [L1] → L1, [Cu$+2] → Cu$+2
            d[key] = int(val)
        else:
            # Legacy format: key:value
            key, val = token.split(":", 1)
            if not key:
                raise ValueError(f"malformed species stoichiometry token {token!r}")
            try:
                d[key] = int(val)
            except ValueError as exc:
                raise ValueError(
                    f"malformed species stoichiometry coefficient in {token!r}") from exc
    if not d:
        raise ValueError("species stoichiometry is Not defined")
    return d


_DETOK_RE = re.compile(r'\[([^\]]+)\](\d*)')
_HXL_DETOK_RE = re.compile(r'^\[\[H\](-?\d*)\[([^\]]+)\]\](\d*)$')

def _detokenize_species_id(tok_id: str) -> str:
    """Convert bracket-tokenized species_id back to internal format.

    [Cu$+2]2.[L2]2.[z-2]         -> Cu$+2(2).L2(2).z-2
    [Cu$+1]2.[OH]2.[z+0]_(s)     -> Cu$+1(2).OH2.z+0(s)
    [Fe$+3].[L1].[H].[z+3]       -> Fe$+3.L1.H.z+3
    [[H]-1[L2]].[Cu$+2].[z-1]    -> H-1L2.Cu$+2.z-1
    """
    # Handle _(s) suffix
    solid = ""
    if tok_id.endswith("_(s)"):
        solid = "(s)"
        tok_id = tok_id[:-4]
    # Also accept legacy (s) suffix
    elif tok_id.endswith("(s)"):
        solid = "(s)"
        tok_id = tok_id[:-3]

    tokens = tok_id.split(".")
    result = []
    for tok in tokens:
        # Nested HxLy bracket: [[H]-1[L2]] → H-1L2, [[H]2[L1]]3 → H2L1(3)
        m = _HXL_DETOK_RE.fullmatch(tok)
        if m:
            h_digits, lig, count = m.group(1), m.group(2), m.group(3)
            key = f"H{h_digits}{lig}"
            if count and count != "1":
                result.append(f"{key}({count})")
            else:
                result.append(key)
            continue
        m = _DETOK_RE.fullmatch(tok)
        if m:
            base, count = m.group(1), m.group(2)
            if base.startswith("z"):
                # Charge token — no count
                result.append(base)
            elif base in ("OH", "H") and count:
                # OH2 / H3 — count is suffix
                result.append(f"{base}{count}")
            elif count and count != "1":
                # Component with count > 1 → parens
                result.append(f"{base}({count})")
            else:
                result.append(base)
        else:
            # Not bracket-tokenized — pass through (legacy format)
            result.append(tok)
    return ".".join(result) + solid


def _detokenize_label(label: str) -> str:
    """Remove bracket tokenization from a species label.

    [Cu]2+ → Cu2+,  [HGlycine] → HGlycine,  [Cu(OH)2](s) → Cu(OH)2(s).
    Already-plain labels and coordination-bracket labels ([Cu(OH)]+) pass through.
    """
    if not label.startswith("["):
        return label
    # Already a coordination-compound bracket like [Cu(OH)]+
    # These have the pattern [<stuff with parens>]<charge>
    # but our tokenized format is [<simple name>]<charge>
    # Detect by checking for nested parens inside the brackets
    inner_end = label.rfind("]")
    if inner_end < 0:
        return label
    inner = label[1:inner_end]
    suffix = label[inner_end + 1:]
    # If inner has parens, it's a coordination bracket → leave as-is
    if "(" in inner and "[" not in inner:
        return label
    return inner + suffix


_VLM_RE = re.compile(r'vlm_\d+')


def _parse_vlm_from_calc_source(calc_source: str) -> str:
    """Extract VLM IDs from a calc_source cell.

    - ``"vlm_93862"``              → ``"vlm_93862"``
    - ``"vlm_93862, vlm_93847"``   → ``"vlm_93862, vlm_93847"``
    - ``"R1: μ°≡0 (aquo-ion ref)"`` → ``""``  (reference species)
    - ``"RULE 1: ..."``             → ``""``  (legacy long format)
    """
    matches = _VLM_RE.findall(calc_source)
    if matches:
        return ", ".join(matches)
    return ""


_HXL_KEY_RE = re.compile(r'^H(-?\d*)(L\d+)$')  # H-1L2, H2L1, HL1


def _decompose_hlx_stoich(
    raw: Dict[str, int],
) -> Tuple[Dict[str, int], Optional[List[Tuple[str, int]]]]:
    """Decompose HxLy grouped stoich into flat stoich + stoich_hlx.

    If the stoich dict contains HxLy keys (e.g. ``H-1L2``, ``HL1``)
    or ``OH`` keys, decompose them into the flat ``{M:p, L:q, H:r}``
    convention and return the original grouped form as ``stoich_hlx``.

    Returns ``(raw, None)`` when no HxLy/OH keys are detected.
    """
    has_hlx = False
    flat: Dict[str, int] = {}
    hlx: List[Tuple[str, int]] = []

    for key, count in raw.items():
        m = _HXL_KEY_RE.match(key)
        if m:
            h_str = m.group(1)
            h_per = int(h_str) if h_str else 1
            lig_key = m.group(2)
            hlx.append((key, count))
            flat["H"] = flat.get("H", 0) + h_per * count
            flat[lig_key] = flat.get(lig_key, 0) + count
            has_hlx = True
            continue
        if key == "OH":
            hlx.append((key, count))
            flat["H"] = flat.get("H", 0) - count
            has_hlx = True
            continue
        flat[key] = flat.get(key, 0) + count
        hlx.append((key, count))

    if flat.get("H") == 0:
        flat.pop("H", None)
    if has_hlx:
        return flat, hlx
    return raw, None


def _strip_placeholder(s: str) -> str:
    """Strip the ``***`` empty-field placeholder to an empty string."""
    s = s.strip()
    return "" if s == "***" else s


def _safe_float(s: str, default: float = 0.0) -> float:
    s = _strip_placeholder(s)
    if not s or s == "—":
        return default
    try:
        return float(s)
    except ValueError:
        return default


def _required_text(value: str, *, field: str, context: str) -> str:
    text = _strip_placeholder(str(value or ""))
    if not text or text == "—" or text == "Not defined":
        raise ValueError(f"{context} has {field}={text or 'Not defined'!r}")
    return text


def _required_float(value: str, *, field: str, context: str) -> float:
    text = _required_text(value, field=field, context=context).lstrip("+")
    try:
        number = float(text)
    except ValueError as exc:
        raise ValueError(
            f"{context} field {field!r} must be numeric, got {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"{context} field {field!r} must be finite")
    return number


def _required_int(value: str, *, field: str, context: str) -> int:
    number = _required_float(value, field=field, context=context)
    if not number.is_integer():
        raise ValueError(
            f"{context} field {field!r} must be an integer, got {value!r}")
    return int(number)


def _required_bool(value: str, *, field: str, context: str) -> bool:
    text = _required_text(value, field=field, context=context).lower()
    if text not in {"true", "false"}:
        raise ValueError(
            f"{context} field {field!r} must be exactly true or false, got {value!r}")
    return text == "true"


def _required_phase(value: str, *, context: str) -> str:
    phase = _required_text(value, field="phase", context=context).lower()
    if phase not in {"aqueous", "dissolution", "solid", "gas"}:
        raise ValueError(
            f"{context} phase must be aqueous, dissolution, solid, or gas; "
            f"got {value!r}")
    return phase


def _parse_declared_total(s: str, *, component_id: str) -> float | str:
    """Parse a component total without converting missing data to zero."""
    value = _strip_placeholder(s)
    if value == "Not defined":
        return "Not defined"
    if not value or value == "—":
        raise ValueError(
            f"component {component_id!r} has no total; write the literal "
            "'Not defined' in a reference card or a numeric value")
    try:
        number = float(value)
    except ValueError as exc:
        raise ValueError(
            f"component {component_id!r} total must be numeric or exactly "
            f"'Not defined', got {s!r}") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(
            f"component {component_id!r} total must be finite and >= 0")
    return number


def _safe_int(s: str, default: int = 0) -> int:
    s = _strip_placeholder(s)
    if not s or s == "—":
        return default
    # Handle "+2", "-1" etc
    try:
        return int(s)
    except ValueError:
        return default


# ══════════════════════════════════════════════════════════════════
#  Main reader
# ══════════════════════════════════════════════════════════════════

def parse_free_energy_card_md(
    source: Union[str, Path],
) -> FreeEnergyReport:
    """Parse a Free-Energy Markdown Card into a ``FreeEnergyReport``.

    Parameters
    ----------
    source : str or Path
        Either the markdown text itself, or a path to a ``.md`` file.

    Returns
    -------
    FreeEnergyReport
        Fully populated report suitable for the Gibbs minimiser.
    """
    if isinstance(source, Path) or (isinstance(source, str) and
                                     not source.startswith("#") and
                                     Path(source).suffix == ".md" and
                                     exists_long(source)):
        text = read_text_long(source)
    else:
        text = source

    lines = text.splitlines()

    # ── Header fields ─────────────────────────────────────────
    system_name = ""
    metal_names_hdr: List[str] = []
    ligand_names_hdr: List[str] = []
    excluded_species: List[str] = []
    for line in lines[:20]:
        line_s = line.strip()
        if line_s.startswith("**System**:"):
            system_name = line_s.split(":", 1)[1].strip()
        elif line_s.startswith("**Metals**:"):
            raw = line_s.split(":", 1)[1].strip()
            metal_names_hdr = [_detokenize_label(m.strip()) for m in raw.split(",") if m.strip()]
        elif line_s.startswith("**Ligands**:"):
            raw = line_s.split(":", 1)[1].strip()
            ligand_names_hdr = [_detokenize_label(lg.strip()) for lg in raw.split(",") if lg.strip()]
        elif line_s.startswith("**Excluded species**:"):
            raw = line_s.split(":", 1)[1].strip()
            if raw and raw.lower() != "(none)":
                excluded_species = [s.strip() for s in raw.split(",") if s.strip()]

    # ── Section 2: Components ─────────────────────────────────
    component_meta: List[ComponentMeta] = []
    metal_ids: List[str] = []
    ligand_ids: List[str] = []
    metal_names: List[str] = []
    ligand_names: List[str] = []
    total_metals: Dict[str, float | str] = {}
    total_ligands: Dict[str, float | str] = {}
    metal_charges: Dict[str, int] = {}
    ligand_charges: Dict[str, int] = {}
    solvents: List[SolventMeta] = []

    # 2.1 Solvent
    sec21 = _find_section(lines, "2.1 Solvent")
    if sec21 >= 0:
        # Find each solvent sub-section (#### S0: Water ...)
        idx = sec21 + 1
        while idx < len(lines):
            line_s = lines[idx].strip()
            if line_s.startswith("### ") or line_s.startswith("## "):
                break  # next major section
            if line_s.startswith("#### "):
                # Parse solvent header: "#### S0: Water (db_id: solvent_1)"
                solv_match = re.match(
                    r"####\s+(S\d+):\s+(.+?)\s*\(db_id:\s*(.+?)\)",
                    line_s,
                )
                if solv_match is None:
                    raise ValueError(
                        f"malformed solvent declaration {line_s!r}; solvent identity "
                        "may not be inferred")
                solv_id = solv_match.group(1)
                solv_name = solv_match.group(2).strip()
                solv_db_id = solv_match.group(3).strip()

                # Parse properties table
                rows, idx = _parse_md_table(lines, idx + 1)
                props = {r.get("property", ""): r.get("value", "") for r in rows}
                formula = _required_text(
                    props.get("formula", ""), field="formula",
                    context=f"solvent {solv_id!r}")
                self_diss = _required_bool(
                    props.get("self_dissociation", ""), field="self_dissociation",
                    context=f"solvent {solv_id!r}")
                diss_reaction = props.get("dissociation_reaction", "")
                pK = _required_float(
                    props.get("pK", ""), field="pK", context=f"solvent {solv_id!r}")
                K_log10 = _required_float(
                    props.get("K_log10", ""), field="K_log10",
                    context=f"solvent {solv_id!r}")
                if self_diss:
                    _required_text(
                        diss_reaction, field="dissociation_reaction",
                        context=f"solvent {solv_id!r}")

                # Parse dissociation species table (if self_dissociation)
                diss_species: List[str] = []
                if self_diss and idx < len(lines):
                    rows2, idx = _parse_md_table(lines, idx)
                    for row in rows2:
                        iid = row.get("internal_id", "")
                        name = _detokenize_label(row.get("name", ""))
                        context = f"solvent dissociation species {iid!r}"
                        charge = _required_int(
                            row.get("charge", ""), field="charge", context=context)
                        db_id_raw = row.get("db_id", "")
                        # Treat *** placeholder as empty
                        db_id_val = "" if db_id_raw.strip() == "***" else db_id_raw.strip()
                        diss_species.append(iid)
                        # Add H+ and OH- to component_meta
                        comp_type = "metal" if iid.startswith("M") else "ligand"
                        component_meta.append(ComponentMeta(
                            internal_id=iid, name=name,
                            comp_type=comp_type, charge=charge,
                            total=0.0, db_source="", db_id=db_id_val,
                        ))

                solvents.append(SolventMeta(
                    internal_id=solv_id,
                    name=solv_name,
                    formula=formula,
                    db_id=solv_db_id,
                    self_dissociation=self_diss,
                    dissociation_species=diss_species,
                    dissociation_reaction=diss_reaction,
                    pK=pK,
                    K_log10=K_log10,
                ))
            else:
                idx += 1

    # 2.2 Metals
    sec22 = _find_section(lines, "2.2 Metals")
    if sec22 >= 0:
        rows, _ = _parse_md_table(lines, sec22 + 1)
        for row in rows:
            iid = row.get("internal_id", "")
            name = _detokenize_label(row.get("name", ""))
            context = f"metal component {iid!r}"
            charge = _required_int(
                row.get("charge", ""), field="charge", context=context)
            total = _parse_declared_total(
                row.get("total_M", ""), component_id=iid)
            db_source = _strip_placeholder(row.get("db_source", ""))
            db_id = _strip_placeholder(row.get("db_id", ""))
            component_meta.append(ComponentMeta(
                internal_id=iid, name=name, comp_type="metal",
                charge=charge, total=total,
                db_source=db_source, db_id=db_id,
            ))
            metal_ids.append(iid)
            metal_names.append(name)
            total_metals[iid] = total
            metal_charges[iid] = charge

    # 2.3 Ligands
    sec23 = _find_section(lines, "2.3 Ligands")
    if sec23 >= 0:
        rows, _ = _parse_md_table(lines, sec23 + 1)
        for row in rows:
            iid = row.get("internal_id", "")
            name = _detokenize_label(row.get("name", ""))
            context = f"ligand component {iid!r}"
            charge = _required_int(
                row.get("charge", ""), field="charge", context=context)
            total = _parse_declared_total(
                row.get("total_M", ""), component_id=iid)
            db_source = _strip_placeholder(row.get("db_source", ""))
            db_id = _strip_placeholder(row.get("db_id", ""))
            smiles = _strip_placeholder(row.get("smiles", ""))
            # Parse canonical_HOL / canonical_HxL — bracket or legacy format
            hol_str = _strip_placeholder(row.get("canonical_HxL", "") or row.get("canonical_HOL", ""))
            hol = None
            # Double-bracket species format: [[H]3[L2]], [[H][L1]], [[L1]]
            # Outer brackets denote combined species vs separate components
            m_bracket = re.match(r"\[(?:\[H\](\d*))?\[([^\]]+)\]\]$", hol_str)
            if not m_bracket:
                # Backwards compat: single-bracket format [H]3[L2], [H][L1], [L1]
                m_bracket = re.match(r"(?:\[H\](\d*))?\[([^\]]+)\]$", hol_str)
            if m_bracket:
                h_part = m_bracket.group(1)
                h_count = int(h_part) if h_part else (1 if "[H]" in hol_str else 0)
                hol = {"H": h_count, "O": 0, "L": 1}
            else:
                # Legacy format: H2O0L1
                m_legacy = re.match(r"H(\d+)O(\d+)L(\d+)", hol_str)
                if m_legacy:
                    hol = {"H": int(m_legacy.group(1)), "O": int(m_legacy.group(2)), "L": int(m_legacy.group(3))}
            if hol is None:
                raise ValueError(
                    f"ligand component {iid!r} has no valid canonical_HxL declaration")
            component_meta.append(ComponentMeta(
                internal_id=iid, name=name, comp_type="ligand",
                charge=charge, total=total,
                db_source=db_source, db_id=db_id,
                smiles=smiles, canonical_HOL=hol,
            ))
            ligand_ids.append(iid)
            ligand_names.append(name)
            total_ligands[iid] = total
            ligand_charges[iid] = charge

    # Use header names as fallback if section 2 is missing/empty
    if not metal_names and metal_names_hdr:
        for i, mn in enumerate(metal_names_hdr):
            iid = f"M{i + 1}"
            metal_ids.append(iid)
            metal_names.append(mn)
    if not ligand_names and ligand_names_hdr:
        for j, ln in enumerate(ligand_names_hdr):
            iid = f"L{j + 1}"
            ligand_ids.append(iid)
            ligand_names.append(ln)

    # 2.4 Metal Valence Alignment (optional)
    valence_groups: List[ValenceGroup] = []
    sec24 = _find_section(lines, "2.4 Metal Valence Alignment")
    if sec24 >= 0:
        rows, _ = _parse_md_table(lines, sec24 + 1)
        # Group rows by element
        _elem_entries: Dict[str, List[ValenceGroupEntry]] = {}
        _elem_ref: Dict[str, str] = {}
        for row in rows:
            elem = row.get("element", "")
            iid = row.get("internal_id", "")
            name = _detokenize_label(row.get("name", ""))
            context = f"metal valence {iid!r}"
            charge = _required_int(
                row.get("charge", ""), field="charge", context=context)
            is_ref = _required_bool(
                row.get("is_reference", ""), field="is_reference", context=context)
            entry = ValenceGroupEntry(
                internal_id=iid, name=name, charge=charge,
                is_reference=is_ref,
            )
            _elem_entries.setdefault(elem, []).append(entry)
            if is_ref:
                _elem_ref[elem] = iid
        for elem in sorted(_elem_entries):
            entries = _elem_entries[elem]
            ref_id = _elem_ref.get(elem, entries[0].internal_id if entries else "")
            valence_groups.append(ValenceGroup(
                element=elem, entries=entries,
                reference_id=ref_id, n_valences=len(entries),
            ))

    # 2.5 Ligand Micro-Valence Analysis (optional)
    ligand_micro_valences: List[LigandMicroValence] = []
    sec25 = _find_section(lines, "2.5 Ligand Micro-Valence Analysis")
    if sec25 >= 0:
        rows, _ = _parse_md_table(lines, sec25 + 1)
        # Group rows by ligand_id
        _mv_data: Dict[str, dict] = {}
        for row in rows:
            lid = row.get("ligand_id", "")
            lname = _detokenize_label(row.get("ligand_name", ""))
            smiles = row.get("smiles", "")
            aelem = row.get("atom_element", "")
            os_raw = row.get("oxidation_states", "[]")
            is_dyn = row.get("is_dynamic", "false").strip().lower() == "true"
            # Parse "[+3, +3, 0, +1, 0, +3]"
            os_list = []
            for tok in os_raw.strip("[] ").split(","):
                tok = tok.strip()
                if tok:
                    os_list.append(_safe_int(tok))
            if lid not in _mv_data:
                _mv_data[lid] = {"name": lname, "smiles": smiles,
                                 "os": {}, "dynamic": []}
            _mv_data[lid]["os"][aelem] = os_list
            if is_dyn:
                _mv_data[lid]["dynamic"].append(aelem)
        for lid in sorted(_mv_data):
            d = _mv_data[lid]
            ligand_micro_valences.append(LigandMicroValence(
                ligand_id=lid, ligand_name=d["name"],
                smiles=d["smiles"],
                atom_os_summary=d["os"],
                dynamic_atoms=sorted(set(d["dynamic"])),
            ))

    # ── Section 3: Canonical Reference States ─────────────────
    sec3 = _find_section(lines, "3. Canonical Reference States")
    canonical_refs: Dict[int, CanonicalRef] = {}
    canonical_info: Dict[int, dict] = {}
    rulebook_notes: List[str] = []
    if sec3 >= 0:
        # 3.1 Component Reference Declarations (informational, not needed for solver)
        # Just skip — the solver uses canonical_refs from 3.2

        # 3.2 Ligand Canonical Resolution
        sec32 = _find_section(lines, "3.2 Ligand Canonical Resolution")
        if sec32 >= 0:
            rows, end32 = _parse_md_table(lines, sec32 + 1)
            for row in rows:
                lid_str = row.get("ligand_id", "")
                lig_idx = int(lid_str.replace("L", "")) if lid_str.startswith("L") else 0
                lig_name = _detokenize_label(row.get("ligand_name", ""))
                context = f"canonical ligand row {lid_str!r}"
                declared_H = _required_int(
                    row.get("declared_H", ""), field="declared_H", context=context)
                resolved_H = _required_int(
                    row.get("resolved_H", ""), field="resolved_H", context=context)
                log_beta = _required_float(
                    row.get("log_beta_HxL", ""), field="log_beta_HxL", context=context)
                mu_shift = _required_float(
                    row.get("mu_shift_kJ", ""), field="mu_shift_kJ", context=context)
                strategy = row.get("strategy", "exact")
                canonical_refs[lig_idx] = CanonicalRef(
                    ligand_idx=lig_idx,
                    ligand_name=lig_name,
                    canonical_H=declared_H,
                    resolved_H=resolved_H,
                    log_beta_HxL=log_beta,
                    mu_shift_kJ=mu_shift,
                    strategy=strategy,
                )
                canonical_info[lig_idx] = {
                    "name": lig_name,
                    "canonical_H": resolved_H,
                    "log_beta_HxL": log_beta,
                    "strategy": strategy,
                }
        else:
            # Fallback: try parsing old-style table directly under Section 3
            rows, end3 = _parse_md_table(lines, sec3 + 1)
            for row in rows:
                lid_str = row.get("ligand_id", "")
                if not lid_str.startswith("L"):
                    continue
                lig_idx = int(lid_str.replace("L", ""))
                lig_name = _detokenize_label(row.get("ligand_name", ""))
                context = f"canonical ligand row {lid_str!r}"
                declared_H = _required_int(
                    row.get("declared_H", ""), field="declared_H", context=context)
                resolved_H = _required_int(
                    row.get("resolved_H", ""), field="resolved_H", context=context)
                log_beta = _required_float(
                    row.get("log_beta_HxL", ""), field="log_beta_HxL", context=context)
                mu_shift = _required_float(
                    row.get("mu_shift_kJ", ""), field="mu_shift_kJ", context=context)
                strategy = row.get("strategy", "exact")
                canonical_refs[lig_idx] = CanonicalRef(
                    ligand_idx=lig_idx,
                    ligand_name=lig_name,
                    canonical_H=declared_H,
                    resolved_H=resolved_H,
                    log_beta_HxL=log_beta,
                    mu_shift_kJ=mu_shift,
                    strategy=strategy,
                )
                canonical_info[lig_idx] = {
                    "name": lig_name,
                    "canonical_H": resolved_H,
                    "log_beta_HxL": log_beta,
                    "strategy": strategy,
                }

        # 3.3 Edge Case Notes
        sec33 = _find_section(lines, "3.3 Edge Case Notes")
        if sec33 >= 0:
            for i in range(sec33 + 1, min(sec33 + 20, len(lines))):
                ln = lines[i].strip()
                if ln.startswith("- "):
                    rulebook_notes.append(ln[2:])
                elif ln.startswith("#"):
                    break

    # ── Section 4: Settings ───────────────────────────────────
    # Try 4.1 Common Settings first, fall back to 4. Settings
    sec4 = _find_section(lines, "4.1 Common Settings")
    if sec4 < 0:
        sec4 = _find_section(lines, "4. Settings")
    temperature_K: Optional[float] = None
    temperature_C: Optional[float] = None
    ionic_strength: float | str = "Not defined"
    ionic_mode = "Not defined"
    Kw_log: Optional[float] = None
    factor: Optional[float] = None
    RT: Optional[float] = None
    if sec4 >= 0:
        rows, _ = _parse_md_table(lines, sec4 + 1)
        for row in rows:
            param = row.get("parameter", "").strip()
            val = row.get("value", "").strip()
            unit = row.get("unit", "").strip()
            if param == "temperature" and unit == "K":
                temperature_K = _required_float(
                    val, field="temperature", context="free-energy card settings")
            elif param == "temperature" and unit == "°C":
                temperature_C = _required_float(
                    val, field="temperature", context="free-energy card settings")
            elif param == "ionic_strength":
                if val == "Not defined":
                    ionic_strength = "Not defined"
                else:
                    ionic_strength = _required_float(
                        val, field="ionic_strength", context="free-energy card settings")
                    if ionic_strength < 0:
                        raise ValueError("free-energy card ionic_strength must be >= 0")
            elif param == "ionic_strength_mode":
                if val == "Not defined":
                    ionic_mode = "Not defined"
                else:
                    ionic_mode = _required_text(
                        val, field="ionic_strength_mode",
                        context="free-energy card settings").lower()
                    if ionic_mode not in {"fixed", "auto", "none"}:
                        raise ValueError(
                            "free-energy card ionic_strength_mode must be fixed, auto, or none")
            elif param == "Kw_log10":
                Kw_log = _required_float(
                    val, field="Kw_log10", context="free-energy card settings")
            elif param == "2.303RT":
                factor = _required_float(
                    val, field="2.303RT", context="free-energy card settings")
            elif param == "RT":
                RT = _required_float(
                    val, field="RT", context="free-energy card settings")

    if factor is None or factor <= 0:
        raise ValueError("free-energy card has no finite positive 2.303RT declaration")
    if RT is None or RT <= 0:
        raise ValueError("free-energy card has no finite positive RT declaration")
    # Derive temperature only from an explicitly stored thermodynamic factor.
    if temperature_K is None:
        temperature_K = factor / (2.303 * 8.314e-3)
    if temperature_C is None:
        temperature_C = temperature_K - 273.15

    # 4.2 Per Metal–Ligand Pair Conditions — extract ref_eq_net IDs and T/I
    _pair_net_ids: Dict[str, List[int]] = {}
    sec42 = _find_section(lines, "4.2 Per Metal")
    if sec42 >= 0:
        rows42, _ = _parse_md_table(lines, sec42 + 1)
        _all_t: List[float] = []
        _all_i: List[float] = []
        for row in rows42:
            pair_raw = _strip_placeholder(row.get("pair", ""))
            # Detokenize pair names: "[Cu]2+ + [Glycine]" → "Cu2+ + Glycine"
            # Split on " + " (with spaces) to avoid breaking charges like 2+
            pair = " + ".join(_detokenize_label(p.strip()) for p in pair_raw.split(" + ")) if pair_raw else ""
            net_str = _strip_placeholder(row.get("ref_eq_net", ""))
            if pair and net_str:
                ids = []
                for tok in net_str.split(","):
                    tok = tok.strip()
                    if tok.isdigit():
                        ids.append(int(tok))
                _pair_net_ids[pair] = ids
            # Parse T/I ranges (may use ~ for ranges)
            t_raw = _strip_placeholder(row.get("T_source (°C)", ""))
            i_raw = _strip_placeholder(row.get("I_source (mol/L)", ""))
            for t_tok in t_raw.replace("~", " ").split():
                tv = _safe_float(t_tok)
                if tv > 0:
                    _all_t.append(tv)
            for i_tok in i_raw.replace("~", " ").split():
                iv = _safe_float(i_tok, -1)
                if iv >= 0:
                    _all_i.append(iv)
        # Pair rows describe source conditions.  They may supply a reference
        # ionic strength, but do not silently declare a solver ionic mode.
        # Source-condition ionic strengths remain in the per-pair/equilibrium
        # metadata and never become an undeclared solver environment value.

    # ── Section 5: Standard Chemical Potentials ───────────────
    species_list: List[SpeciesEnergy] = []

    def _parse_species_rows(rows: List[Dict[str, str]]) -> None:
        """Parse species table rows and append to species_list."""
        for row in rows:
            species_id_raw = row.get("species_id", "")
            context = f"species row {species_id_raw or '<missing>'!r}"
            _required_text(species_id_raw, field="species_id", context=context)
            species_id = _detokenize_species_id(species_id_raw)
            original_id = _detokenize_species_id(
                row.get("original_id", species_id_raw)
            )
            label = _detokenize_label(row.get("label", ""))
            charge = _required_int(
                row.get("charge", ""), field="charge", context=context)
            phase = _required_phase(row.get("phase", ""), context=context)
            log_beta = _required_float(
                row.get("log_beta", ""), field="log_beta", context=context)
            mu0_free = _required_float(
                row.get("mu0_free_kJ", ""), field="mu0_free_kJ", context=context)
            mu0_canon = _required_float(
                row.get("mu0_canon_kJ", ""), field="mu0_canon_kJ", context=context)
            mu_aligned = _required_float(
                row.get("mu_aligned_kJ", ""), field="mu_aligned_kJ", context=context)
            stoich_raw = _parse_stoich(row.get("stoich", ""))
            stoich, stoich_hlx = _decompose_hlx_stoich(stoich_raw)
            inc = _required_bool(
                row.get("include", ""), field="include", context=context)
            notes = _strip_placeholder(row.get("additional_notes", ""))
            # Extract vlm_id from calc_source or source column (enriched cards
            # use "source" instead of "calc_source")
            calc_source = _strip_placeholder(
                row.get("calc_source", "") or row.get("source", "")
            )
            vlm_id = _parse_vlm_from_calc_source(calc_source)

            species_list.append(SpeciesEnergy(
                species_id=species_id,
                original_id=original_id,
                label=label,
                stoich=stoich,
                stoich_hlx=stoich_hlx,
                charge=charge,
                phase=phase,
                log_beta=log_beta,
                app_log_beta=log_beta,  # will be recomputed at solve time
                mu0_free=mu0_free,
                mu0_canonical=mu0_canon,
                mu_aligned=mu_aligned,
                include=inc,
                additional_notes=notes,
                vlm_id=vlm_id,
            ))
            if not inc:
                excluded_species.append(species_id)

    for sub_heading in ("5.1 Aqueous Species", "5.2 Dissolution", "5.3 Gas Species"):
        sec5x = _find_section(lines, sub_heading)
        if sec5x < 0:
            continue
        # Find end of this subsection (next ### or ## heading)
        sec5x_end = len(lines)
        for i in range(sec5x + 1, len(lines)):
            stripped = lines[i].strip()
            if stripped.startswith("### ") or stripped.startswith("## "):
                sec5x_end = i
                break
        # Scan for all tables within the subsection (may have #### sub-headers)
        idx = sec5x + 1
        while idx < sec5x_end:
            stripped = lines[idx].strip()
            if stripped.startswith("####"):
                # Skip #### sub-header, table follows
                idx += 1
                continue
            if stripped.startswith("|"):
                rows, idx = _parse_md_table(lines, idx)
                _parse_species_rows(rows)
            else:
                idx += 1

    # 5.4 Supportive Thermodynamic Data — extract Kw and electron data
    nernst_factor: float = 0.0
    sec54 = _find_section(lines, "5.4 Supportive Thermodynamic Data")
    if sec54 >= 0:
        rows, _ = _parse_md_table(lines, sec54 + 1)
        for row in rows:
            # Support both old format (solvent_id) and new format (entity_id)
            entity = (row.get("entity_id") or row.get("solvent_id", "")).strip()
            prop = row.get("property", "").strip()
            val_str = row.get("value", "").strip()
            if prop == "pKw":
                Kw_log = -_required_float(
                    val_str, field="pKw",
                    context="supportive thermodynamic data")
            elif entity == "e-" and prop == "nernst_factor":
                nernst_factor = _required_float(
                    val_str, field="nernst_factor",
                    context="supportive thermodynamic data")

    if not species_list:
        raise ValueError(
            "free-energy card contains no solver species in Section 5")
    if Kw_log is None:
        raise ValueError("free-energy card has no explicit Kw_log10/pKw value")
    if not solvents:
        raise ValueError(
            "free-energy card has no explicit solvent declaration; water may not be inferred")
    if ionic_mode != "Not defined" and ionic_strength == "Not defined":
        raise ValueError(
            "free-energy card declares ionic_strength_mode but no ionic_strength value")

    # ── Section 6: Equilibrium Map Coverage ─────────────────────
    eq_meta_list: List[EquilibriumMeta] = []
    sec62 = _find_section(lines, "6.2 Per-Entry Detail")
    if sec62 >= 0:
        rows, _ = _parse_md_table(lines, sec62 + 1)
        for row in rows:
            vlm_id = _strip_placeholder(row.get("vlm_id", ""))
            eq_str = _strip_placeholder(row.get("equation", ""))
            context = f"equilibrium metadata row {vlm_id or '<missing>'!r}"
            log_k = _required_float(
                row.get("stepwise_logK", ""), field="stepwise_logK", context=context)
            t_c = _required_float(
                row.get("T_°C", ""), field="T_°C", context=context)
            i_m = _required_float(
                row.get("I_M", ""), field="I_M", context=context)
            if i_m < 0:
                raise ValueError(f"{context} I_M must be >= 0")
            incl_str = _required_text(
                row.get("included", ""), field="included", context=context).lower()
            if incl_str not in {"yes", "no", "true", "false"}:
                raise ValueError(
                    f"{context} included must be yes/no or true/false")
            included = incl_str in {"yes", "true"}
            species_str = _strip_placeholder(row.get("species_in_card", ""))

            # Derive metal/ligand system from species labels (best effort)
            metal_sys: List[str] = []
            ligand_sys: List[str] = []
            for mname in metal_names:
                if mname in eq_str:
                    metal_sys.append(mname)
            for lname in ligand_names:
                if lname in eq_str:
                    ligand_sys.append(lname)
            # Fallback: use all metals/ligands if none detected
            if not metal_sys:
                metal_sys = list(metal_names)
            if not ligand_sys:
                ligand_sys = list(ligand_names)

            # Look up ref_eq_net_ids from Section 4.2 pair map
            pair_key = ", ".join(metal_sys) + " + " + ", ".join(ligand_sys)
            net_ids = _pair_net_ids.get(pair_key, [])

            eq_meta_list.append(EquilibriumMeta(
                equation_str=eq_str.replace("\\|", "|"),
                log_K=log_k,
                constant_type="stepwise",
                T_source_C=t_c,
                I_source_M=i_m,
                db_source="NIST SRD-46",
                db_id=vlm_id,
                include=included,
                metal_system=metal_sys,
                ligand_system=ligand_sys,
                ref_eq_net_ids=list(net_ids),
            ))

    # ── Build rulebook ────────────────────────────────────────
    rulebook: Optional[CanonicalRuleBook] = None
    if canonical_refs:
        rulebook = CanonicalRuleBook(
            refs=canonical_refs,
            temperature_K=temperature_K,
            factor=factor,
            notes=rulebook_notes,
        )

    # ── Assemble FreeEnergyReport ─────────────────────────────
    return FreeEnergyReport(
        temperature_K=temperature_K,
        temperature_C=temperature_C,
        RT=RT,
        factor=factor,
        Kw_log=Kw_log,
        species=species_list,
        reactions=[],
        canonical_info=canonical_info,
        rulebook=rulebook,
        metal_ids=metal_ids,
        ligand_ids=ligand_ids,
        metal_names=metal_names,
        ligand_names=ligand_names,
        total_metals=total_metals,
        total_ligands=total_ligands,
        ionic_strength=ionic_strength,
        ionic_mode=ionic_mode,
        metal_charges=metal_charges,
        ligand_charges=ligand_charges,
        consistency_ok=True,
        inconsistencies=[],
        component_meta=component_meta,
        equilibrium_meta=eq_meta_list,
        excluded_species=excluded_species,
        solvents=solvents,
        notes=[],
        valence_groups=valence_groups,
        redox_couples=[],
        ligand_micro_valences=ligand_micro_valences,
    )
