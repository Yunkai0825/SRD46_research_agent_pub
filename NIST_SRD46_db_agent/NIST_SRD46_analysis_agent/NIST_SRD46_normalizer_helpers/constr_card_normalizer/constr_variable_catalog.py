"""L3_2 variable catalog  (constr_variable_catalog.py)
====================================================

Builds the *authoritative* catalog of every variable the constraint
designer may reference, mirroring the lc3_2 card namespace **exactly** so
the LLM never has to guess a token.  The catalog is derived from the
solver's own ``FreeEnergyReport`` (via ``build_default_catalog`` for the
total/basis tokens and ``report.species`` for the dependent-species
tokens) — i.e. the same source the downstream solver consumes.

Namespace mirrored (see ``constr_code_card_compiler``)::

    s.E_V                  # electron / redox handle
    s.pH                   # proton handle
    s.temperature
    s.ionic_strength
    s.total["<id>"]        # element / valence / ligand totals
    s.species["<id>"]      # one dependent aqueous/solid/gas species
    s.conc["<id>"]         # = exp(lnconc)   (component OR species id)
    s.lnconc["<id>"]       # natural-log concentration

The requested presentation groups variables as:

    electron_species : s.E_V
    proton_species   : s.pH
    ligand_species   : per ligand -> {total, member species}
    metal_element    : per element -> {element total, per valence ->
                                       {valence total, member species}}

Returns a :class:`VariableCatalog` carrying both the rendered text (for
the LLM prompt) and the flat ``components`` / ``species`` id sets (for
``compile_card``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple


# Reserved intensive handles addressable as ``s.<name>`` (mirrors
# ``constr_code_card_compiler._INTENSIVES``).
INTENSIVES: Tuple[str, ...] = ("temperature", "ionic_strength", "pH", "E_V")

# Cap on species listed per group so a large system (FeCu has 50+) keeps
# the prompt bounded.
_MAX_SPECIES_PER_GROUP = 60


@dataclass
class VariableCatalog:
    """Result of :func:`build_variable_catalog`."""
    components: List[str]                 # valid ids for s.total[...] (+ conc/lnconc)
    species:    List[str]                 # valid ids for s.species[...] (+ conc/lnconc)
    intensives: List[str] = field(default_factory=lambda: list(INTENSIVES))
    text:       str = ""                  # rendered catalog for the prompt
    structured: Dict[str, Any] = field(default_factory=dict)


# ── helpers ─────────────────────────────────────────────────────────

def _species_phase_tag(phase: str) -> str:
    p = (phase or "").lower()
    if p == "aqueous":
        return "aq"
    if p in ("dissolution", "solid"):
        return "solid"
    if p == "gas":
        return "gas"
    return p or "?"


def _dedup_keep_order(items: Sequence[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out


def _coerce_redox_id(rs: Any) -> str:
    """Normalise a redox-state entry to its string id.

    ``merge_catalog_overrides`` unions whatever the system-catalog
    override supplies into ``redox_states``; the LC1 catalog stores these
    as dicts (``{"db_id": ..., "internal_id": ...}``) rather than bare
    valence strings, so coerce them to the internal/db id here.
    """
    if isinstance(rs, str):
        return rs
    if isinstance(rs, dict):
        return str(rs.get("internal_id") or rs.get("db_id")
                   or rs.get("id") or rs.get("name") or "")
    return str(rs)



def build_variable_catalog(
    report: Any,
    system_catalog: Optional[Dict[str, Any]] = None,
) -> VariableCatalog:
    """Build the variable catalog from a ``FreeEnergyReport``.

    Parameters
    ----------
    report
        A ``FreeEnergyReport`` (from ``resolve_card_source``).  Provides
        ``component_meta`` and ``species``.
    system_catalog
        Optional L1/L2 ``system_catalog`` override dict (same shape
        ``merge_catalog_overrides`` consumes); used only to honour metal
        display-name overrides.  Token ids always come from the report.
    """
    # Import here so the module stays importable without the numcalc
    # path bootstrap until it is actually used.
    from sweep_pipelines._sweep_input_entry_point.constraint_compiler import (
        build_default_catalog, merge_catalog_overrides,
    )

    catalog = build_default_catalog(report)
    if system_catalog:
        try:
            catalog = merge_catalog_overrides(catalog, system_catalog)
        except Exception:
            pass  # keep the authoritative base on any override mismatch

    metals = catalog.chemical_system.metals
    ligands = catalog.chemical_system.ligands

    # Normalise redox-state entries to bare string ids: override merges
    # can leave dicts in ``redox_states`` (see _coerce_redox_id).
    for m in metals:
        m.redox_states = _dedup_keep_order(
            [rid for rid in (_coerce_redox_id(r) for r in m.redox_states) if rid]
        )


    # Index species by the valence tokens / ligand internal-ids they
    # contain (per ``SpeciesEnergy.stoich`` keys), keeping label + phase.
    species_records: List[Dict[str, Any]] = []
    species_ids_all: List[str] = []
    for sp in (getattr(report, "species", []) or []):
        if not getattr(sp, "include", True):
            continue
        sid = getattr(sp, "species_id", "") or ""
        if not sid:
            continue
        stoich = dict(getattr(sp, "stoich", {}) or {})
        rec = {
            "id":     sid,
            "label":  getattr(sp, "label", "") or "",
            "phase":  _species_phase_tag(getattr(sp, "phase", "")),
            "stoich": stoich,
        }
        species_records.append(rec)
        species_ids_all.append(sid)

    def _species_for_key(key: str) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        seen: Set[str] = set()
        for rec in species_records:
            if key in rec["stoich"] and rec["id"] not in seen:
                seen.add(rec["id"])
                out.append(rec)
        return out

    # ── flat id sets for compile_card ──────────────────────────────
    components: List[str] = []
    for m in metals:
        components.append(m.element)
        if m.name and m.name != m.element:
            components.append(m.name)
        for rid in m.redox_states:
            components.append(rid)
    for L in ligands:
        components.append(L.db_id)
        if L.internal_id and L.internal_id != L.db_id:
            components.append(L.internal_id)
    components = _dedup_keep_order(components)
    species_ids = _dedup_keep_order(species_ids_all)

    # ── structured tree ────────────────────────────────────────────
    structured: Dict[str, Any] = {
        "intensives": {
            "electron": "E_V", "proton": "pH",
            "temperature": "temperature", "ionic_strength": "ionic_strength",
        },
        "ligands": [],
        "metals": [],
    }

    def _render_species(recs: List[Dict[str, Any]], indent: str) -> List[str]:
        lines: List[str] = []
        shown = recs[:_MAX_SPECIES_PER_GROUP]
        for rec in shown:
            tag = "" if rec["phase"] == "aq" else f"  [{rec['phase']}]"
            label = f"  # {rec['label']}" if rec["label"] else ""
            lines.append(f'{indent}s.species["{rec["id"]}"]{label}{tag}')
        extra = len(recs) - len(shown)
        if extra > 0:
            lines.append(f"{indent}... (+{extra} more)")
        if not recs:
            lines.append(f"{indent}_(none)_")
        return lines

    # ── render ─────────────────────────────────────────────────────
    out: List[str] = []
    out.append("# VARIABLE CATALOG -- the EXACT handles you may reference.")
    out.append("# Use these names verbatim; do NOT invent or guess ids.")
    out.append("# Concentration handles s.conc[\"<id>\"] / s.lnconc[\"<id>\"]")
    out.append("#   accept any component id OR species id listed below.")
    out.append("")
    out.append("## Intensives (scalar handles)")
    out.append("  s.E_V              # electron / redox potential (V)")
    out.append("  s.pH               # proton activity (-log10 a_H+)")
    out.append("  s.temperature      # K")
    out.append("  s.ionic_strength   # mol/L")
    out.append("")

    out.append("## Ligand species")
    for L in ligands:
        recs = _species_for_key(L.internal_id) if L.internal_id else []
        alias = (f'  (alias s.total["{L.internal_id}"])'
                 if L.internal_id and L.internal_id != L.db_id else "")
        out.append(f"- {L.name}  (id {L.db_id}, internal {L.internal_id})")
        out.append(f'    total:    s.total["{L.db_id}"]{alias}')
        out.append("    species:")
        out.extend(_render_species(recs, "      "))
        structured["ligands"].append({
            "name": L.name, "db_id": L.db_id, "internal_id": L.internal_id,
            "total": f'[{L.db_id}]_total',
            "species": [r["id"] for r in recs],
        })
    if not ligands:
        out.append("  _(no ligands)_")
    out.append("")

    out.append("## Metal element species")
    for m in metals:
        elem_alias = (f'  (alias s.total["{m.name}"])'
                      if m.name and m.name != m.element else "")
        out.append(f"- {m.element}  (element)")
        out.append(f'    element total: s.total["{m.element}"]'
                   f'{elem_alias}'
                   f'   # sum over ALL oxidation states')
        out.append("    oxidation states:")
        m_struct = {
            "element": m.element, "name": m.name,
            "element_total": f'[{m.element}]_total',
            "valences": [],
        }
        for rid in m.redox_states:
            recs = _species_for_key(rid)
            out.append(f"    - {rid}")
            out.append(f'        total:   s.total["{rid}"]')
            out.append("        species:")
            out.extend(_render_species(recs, "          "))
            m_struct["valences"].append({
                "valence": rid, "total": f'[{rid}]_total',
                "species": [r["id"] for r in recs],
            })
        structured["metals"].append(m_struct)
    if not metals:
        out.append("  _(no metals)_")

    return VariableCatalog(
        components=components,
        species=species_ids,
        intensives=list(INTENSIVES),
        text="\n".join(out),
        structured=structured,
    )
