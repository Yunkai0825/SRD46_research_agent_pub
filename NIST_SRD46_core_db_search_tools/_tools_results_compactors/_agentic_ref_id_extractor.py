"""
Agentic reference-ID extractor — shared by all tool compactors.
================================================================
Scans raw tool-result rows for entity IDs and builds a compact
**Referenced IDs** markdown table appended to every compactor output
that exceeds ``MIN_EMIT_CHARS`` (500).

Three resolution tiers
----------------------
1. **Full-resolved** — ligands (name + SMILES + HxL_def), metals (name),
   beta_defs (id + equation).  These carry enough context for the agent
   to reason without a follow-up lookup.
2. **Prefixed-ID only** — vlm, network, node, literature.  Stored as
   bare ``prefix_id`` strings so the agent can reference them later.
3. **Skip** — aggregate/count tools produce no entity IDs.

Public API
----------
``extract_reference_ids(tool_name, data) → list[RefEntry]``
    Scan raw data and return de-duplicated reference entries.

``format_reference_ids_section(refs) → str``
    Render the entries as a markdown section.

``append_ref_ids_if_needed(tool_name, data, compact_md) → str``
    One-call helper: extract, format, and append to *compact_md*
    when the output exceeds ``MIN_EMIT_CHARS``.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any


MIN_EMIT_CHARS = 500
"""Minimum compact-markdown length before the reference-ID section
is appended.  Matches the agent config ``MIN_COMPRESS_CHARS``."""


# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════

def _ensure_prefix(prefix: str, raw_id: Any) -> str:
    """Return ``prefix_N`` if *raw_id* is a bare int, else pass through.

    IDs coming from the id_prefixer are already strings like ``'metal_41'``.
    Raw DB ints need the prefix prepended.
    """
    s = str(raw_id)
    if s.startswith(f"{prefix}_"):
        return s
    # Some IDs use a different prefix (e.g. ref_eq_net_99)
    if prefix == "ref_eq_net" and s.startswith("ref_eq_net_"):
        return s
    return f"{prefix}_{s}"


# ═══════════════════════════════════════════════════════════════
#  RefEntry — one referenced entity
# ═══════════════════════════════════════════════════════════════

@dataclass
class RefEntry:
    """One referenced entity extracted from tool results."""
    entity_type: str        # metal, ligand, beta_def, vlm, network, lit, node
    prefixed_id: str        # e.g. metal_41, ligand_5760
    name: str = ""          # resolved name (metals, ligands)
    detail: str = ""        # SMILES, HxL_def, equation, etc.


# ═══════════════════════════════════════════════════════════════
#  Per-tool extractors
# ═══════════════════════════════════════════════════════════════

def _extract_from_rows(rows: list[dict]) -> list[RefEntry]:
    """Generic row-list scanner for stability / network / citation / pKa rows."""
    seen: OrderedDict[str, RefEntry] = OrderedDict()

    for r in rows:
        # --- metals ---
        mid = r.get("metal_id")
        if mid is not None:
            key = _ensure_prefix("metal", mid)
            if key not in seen:
                seen[key] = RefEntry("metal", key, name=r.get("metal_name", ""))

        # --- ligands (full resolution) ---
        lid = r.get("ligand_id")
        if lid is not None:
            key = _ensure_prefix("ligand", lid)
            if key not in seen:
                smiles = r.get("ligand_SMILES") or r.get("smiles") or ""
                hxl = r.get("ligand_HxL_definition") or r.get("HxL_canonical") or ""
                name = r.get("ligand_name") or ""
                parts = []
                if smiles:
                    parts.append(f"SMILES: {smiles}")
                if hxl:
                    parts.append(f"HxL: {hxl}")
                seen[key] = RefEntry("ligand", key, name=name, detail="; ".join(parts))

        # --- beta definitions (full resolution) ---
        bid = r.get("beta_definition_id")
        if bid is not None:
            key = _ensure_prefix("beta_def", bid)
            if key not in seen:
                eq = r.get("equation") or r.get("beta_equation") or r.get("equation_str") or ""
                seen[key] = RefEntry("beta_def", key, detail=eq)

        # --- plain IDs ---
        vid = r.get("vlm_id")
        if vid is not None:
            key = _ensure_prefix("vlm", vid)
            if key not in seen:
                seen[key] = RefEntry("vlm", key)

        for _vlm_alias in ("source_vlm_id", "example_vlm_id"):
            _av = r.get(_vlm_alias)
            if _av is not None:
                key = _ensure_prefix("vlm", _av)
                if key not in seen:
                    seen[key] = RefEntry("vlm", key)

        nid = r.get("network_db_id") or r.get("network_id")
        if nid is not None:
            key = _ensure_prefix("ref_eq_net", nid)
            if key not in seen:
                seen[key] = RefEntry("network", key)

        node = r.get("node_id")
        if node is not None:
            key = _ensure_prefix("eq_node", node)
            if key not in seen:
                seen[key] = RefEntry("node", key)

        mid_map = r.get("map_id")
        if mid_map is not None:
            key = _ensure_prefix("ref_eq_map", mid_map)
            if key not in seen:
                seen[key] = RefEntry("map", key)

        pka = r.get("pka_id")
        if pka is not None:
            key = _ensure_prefix("pka", pka)
            if key not in seen:
                seen[key] = RefEntry("pka", key)

        lit = r.get("literature_alt_id") or r.get("lit_id")
        if lit is not None:
            key = _ensure_prefix("lit", lit)
            if key not in seen:
                shortcut = r.get("shortcut") or ""
                seen[key] = RefEntry("lit", key, name=shortcut)

    return list(seen.values())


def _extract_from_similar_ligands(data: dict) -> list[RefEntry]:
    """Extractor for ``search_similar_ligands`` result dict."""
    refs: OrderedDict[str, RefEntry] = OrderedDict()

    def _add_ligand(row: dict) -> None:
        lid = row.get("ligand_id")
        if lid is None:
            return
        key = _ensure_prefix("ligand", lid)
        if key in refs:
            return
        smiles = row.get("smiles") or ""
        hxl = row.get("HxL_canonical") or ""
        parts = []
        if smiles:
            parts.append(f"SMILES: {smiles}")
        if hxl:
            parts.append(f"HxL: {hxl}")
        refs[key] = RefEntry("ligand", key, name=row.get("ligand_name", ""), detail="; ".join(parts))

    def _add_eq_richness(eq: dict) -> None:
        for mc in eq.get("metals_covered") or []:
            mid = mc.get("metal_id")
            if mid is not None:
                key = _ensure_prefix("metal", mid)
                if key not in refs:
                    refs[key] = RefEntry("metal", key, name=mc.get("metal_name", ""))
        for tm in eq.get("top_maps") or []:
            mid = tm.get("metal_id")
            if mid is not None:
                key = _ensure_prefix("metal", mid)
                if key not in refs:
                    refs[key] = RefEntry("metal", key, name=tm.get("metal_name", ""))
            lid = tm.get("ligand_id")
            if lid is not None:
                key = _ensure_prefix("ligand", lid)
                if key not in refs:
                    refs[key] = RefEntry("ligand", key, name=tm.get("ligand_name", ""))

    _add_ligand(data.get("query_ligand") or {})
    _add_eq_richness(data.get("query_eq_richness") or {})

    for sim in data.get("similar_ligands") or []:
        _add_ligand(sim)
        _add_eq_richness(sim.get("eq_richness") or {})

    return list(refs.values())


def _extract_from_search_ligands(data: dict) -> list[RefEntry]:
    """Extractor for ``search_ligands`` result dict (has 'results' list)."""
    refs: OrderedDict[str, RefEntry] = OrderedDict()
    for row in data.get("results") or []:
        lid = row.get("ligand_id")
        if lid is not None:
            key = _ensure_prefix("ligand", lid)
            if key not in refs:
                smiles = row.get("smiles") or ""
                hxl = row.get("ligand_HxL_definition") or ""
                parts = []
                if smiles:
                    parts.append(f"SMILES: {smiles}")
                if hxl:
                    parts.append(f"HxL: {hxl}")
                refs[key] = RefEntry("ligand", key, name=row.get("ligand_name", ""), detail="; ".join(parts))
    return list(refs.values())


def _extract_from_search_metals(rows: list[dict]) -> list[RefEntry]:
    """Extractor for ``search_metals`` result list."""
    refs: OrderedDict[str, RefEntry] = OrderedDict()
    for row in rows:
        mid = row.get("metal_id")
        if mid is not None:
            key = _ensure_prefix("metal", mid)
            if key not in refs:
                refs[key] = RefEntry("metal", key, name=row.get("metal_name", ""))
    return list(refs.values())


def _extract_from_inspect_card(data: dict) -> list[RefEntry]:
    """Extractor for ``inspect_card`` / ``inspect_literature`` result dict."""
    refs: OrderedDict[str, RefEntry] = OrderedDict()

    pid = data.get("prefix_id", "")
    if pid:
        if pid.startswith("metal_"):
            card = data.get("card") or {}
            refs[pid] = RefEntry("metal", pid, name=card.get("metal_name", "") or card.get("metal_name_SRD", ""))
            for lp in data.get("ligand_partners") or []:
                lid = lp.get("ligand_id")
                if lid is not None:
                    key = _ensure_prefix("ligand", lid)
                    if key not in refs:
                        refs[key] = RefEntry("ligand", key, name=lp.get("ligand_name", ""))

        elif pid.startswith("ligand_"):
            card = data.get("card") or {}
            smiles = card.get("ligand_SMILES") or card.get("smiles") or ""
            hxl = card.get("definition_HxL") or card.get("ligand_HxL_definition") or ""
            parts = []
            if smiles:
                parts.append(f"SMILES: {smiles}")
            if hxl:
                parts.append(f"HxL: {hxl}")
            refs[pid] = RefEntry("ligand", pid, name=card.get("ligand_name_SRD", ""), detail="; ".join(parts))
            for mp in data.get("metal_partners") or []:
                mid = mp.get("metal_id")
                if mid is not None:
                    key = _ensure_prefix("metal", mid)
                    if key not in refs:
                        refs[key] = RefEntry("metal", key, name=mp.get("metal_name", ""))
            for pk in data.get("pka_values") or []:
                pka = pk.get("pka_id")
                if pka is not None:
                    key = _ensure_prefix("pka", pka)
                    if key not in refs:
                        refs[key] = RefEntry("pka", key)
                sv = pk.get("source_vlm_id")
                if sv is not None:
                    key = _ensure_prefix("vlm", sv)
                    if key not in refs:
                        refs[key] = RefEntry("vlm", key)

        elif pid.startswith("vlm_"):
            refs[pid] = RefEntry("vlm", pid)
            card = data.get("card") or {}
            for col, etype, prefix in (
                ("metal_id", "metal", "metal"),
                ("ligand_id", "ligand", "ligand"),
                ("beta_definition_id", "beta_def", "beta_def"),
            ):
                val = card.get(col)
                if val is not None:
                    key = _ensure_prefix(prefix, val)
                    if key not in refs:
                        name = ""
                        if etype == "metal":
                            name = card.get("metal_name", "")
                        elif etype == "ligand":
                            name = card.get("ligand_name", "")
                        detail = ""
                        if etype == "beta_def":
                            detail = card.get("equation") or card.get("equation_str") or ""
                        refs[key] = RefEntry(etype, key, name=name, detail=detail)
            for net in data.get("networks") or []:
                nid = net.get("network_id") or net.get("network_db_id")
                if nid is not None:
                    key = _ensure_prefix("ref_eq_net", nid)
                    if key not in refs:
                        refs[key] = RefEntry("network", key)
                node = net.get("node_id")
                if node is not None:
                    key = _ensure_prefix("eq_node", node)
                    if key not in refs:
                        refs[key] = RefEntry("node", key)

    for cit in data.get("citations") or []:
        lit = cit.get("literature_alt_id") or cit.get("lit_id")
        if lit is not None:
            key = _ensure_prefix("lit", lit)
            if key not in refs:
                refs[key] = RefEntry("lit", key, name=cit.get("shortcut", ""))

    return list(refs.values())


def _extract_from_system_catalog(data: dict) -> list[RefEntry]:
    """Extractor for ``build_system_catalog`` result dict.

    Structure: ``{"pairs": [{metal_id, ligand_id, species_catalog,
    vlm_ids, beta_definition_ids, equilibrium_maps, ...}], "summary": ...}``
    """
    refs: OrderedDict[str, RefEntry] = OrderedDict()

    for pair in data.get("pairs") or []:
        mid = pair.get("metal_id")
        if mid is not None:
            key = _ensure_prefix("metal", mid)
            if key not in refs:
                refs[key] = RefEntry("metal", key, name=pair.get("metal_name", ""))

        lid = pair.get("ligand_id")
        if lid is not None:
            key = _ensure_prefix("ligand", lid)
            if key not in refs:
                hxl = pair.get("definition_HxL") or ""
                detail = f"HxL: {hxl}" if hxl else ""
                refs[key] = RefEntry("ligand", key, name=pair.get("ligand_name", ""), detail=detail)

        for sp in pair.get("species_catalog") or []:
            bid = sp.get("beta_definition_id")
            if bid is not None:
                key = _ensure_prefix("beta_def", bid)
                if key not in refs:
                    eq = sp.get("equation_str") or ""
                    refs[key] = RefEntry("beta_def", key, detail=eq)

        for vid in pair.get("vlm_ids") or []:
            if vid is not None:
                key = _ensure_prefix("vlm", vid)
                if key not in refs:
                    refs[key] = RefEntry("vlm", key)

        for eq_row in pair.get("equilibrium_maps") or []:
            nid = eq_row.get("network_id") or eq_row.get("network_db_id")
            if nid is not None:
                key = _ensure_prefix("ref_eq_net", nid)
                if key not in refs:
                    refs[key] = RefEntry("network", key)

    return list(refs.values())


# ═══════════════════════════════════════════════════════════════
#  Dispatcher
# ═══════════════════════════════════════════════════════════════

def _extract_rows_from_dict_key(data: Any, key: str) -> list[RefEntry]:
    """Pull a ``list[dict]`` from ``data[key]`` and scan with ``_extract_from_rows``."""
    if not isinstance(data, dict):
        return []
    rows = data.get(key)
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        return _extract_from_rows(rows)
    return []


_TOOL_EXTRACTORS = {
    # list[dict] tools → generic row scanner
    "search_stability":       lambda d: _extract_from_rows(d) if isinstance(d, list) else [],
    "search_networks":        lambda d: _extract_from_rows(d) if isinstance(d, list) else [],
    "search_citations":       lambda d: _extract_from_rows(d) if isinstance(d, list) else [],
    "search_pka_values":      lambda d: _extract_from_rows(d) if isinstance(d, list) else [],
    "search_pka_ligands":     lambda d: _extract_from_rows(d) if isinstance(d, list) else [],
    # dict tools → specialised extractors
    "search_similar_ligands": lambda d: _extract_from_similar_ligands(d) if isinstance(d, dict) else [],
    "search_ligands":         lambda d: _extract_from_search_ligands(d) if isinstance(d, dict) else [],
    "search_metals":          lambda d: _extract_from_search_metals(d) if isinstance(d, list) else [],
    "inspect_card":           lambda d: _extract_from_inspect_card(d) if isinstance(d, dict) else [],
    "inspect_literature":     lambda d: _extract_from_inspect_card(d) if isinstance(d, dict) else [],
    "build_system_catalog":   lambda d: _extract_from_system_catalog(d) if isinstance(d, dict) else [],
    "system_catalog":         lambda d: _extract_from_system_catalog(d) if isinstance(d, dict) else [],
    # aggregate tools → scan nested row lists for any entity IDs
    "db_ranked_pairs":        lambda d: _extract_rows_from_dict_key(d, "results"),
    "db_distribution":        lambda d: _extract_rows_from_dict_key(d, "groups"),
    "db_count_records":       lambda d: [],
    "get_table_schema":       lambda d: [],
    "0_preplan_decision":     lambda d: [],
}


def extract_reference_ids(tool_name: str, data: Any) -> list[RefEntry]:
    """Scan *data* (raw tool result) and return de-duplicated RefEntry list.

    Returns an empty list for tools that have no meaningful entity IDs
    (aggregate tools, memory tools, etc.).
    """
    extractor = _TOOL_EXTRACTORS.get(tool_name)
    if extractor is None:
        return []
    try:
        return extractor(data)
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════
#  Markdown formatter
# ═══════════════════════════════════════════════════════════════

def format_reference_ids_section(refs: list[RefEntry]) -> str:
    """Render *refs* as a compact markdown section.

    Full-resolved entities (metal, ligand, beta_def) get their own
    table with name/detail columns.  Plain-ID entities (vlm, network,
    lit, node) are listed in a separate lightweight table.
    """
    if not refs:
        return ""

    resolved = [r for r in refs if r.entity_type in ("metal", "ligand", "beta_def")]
    plain = [r for r in refs if r.entity_type not in ("metal", "ligand", "beta_def")]

    lines: list[str] = ["", "### Referenced entity IDs"]

    if resolved:
        lines.append("| type | prefixed_id | name | detail |")
        lines.append("|------|-------------|------|--------|")
        for r in resolved:
            lines.append(f"| {r.entity_type} | {r.prefixed_id} | {_esc(r.name)} | {_esc(r.detail)} |")

    if plain:
        lines.append("")
        lines.append("| type | prefixed_id | label |")
        lines.append("|------|-------------|-------|")
        for r in plain:
            label = r.name or ""
            lines.append(f"| {r.entity_type} | {r.prefixed_id} | {_esc(label)} |")

    lines.append("")
    return "\n".join(lines)


def _esc(val: Any) -> str:
    """Escape pipe characters for markdown table cells."""
    s = str(val) if val else ""
    return s.replace("|", "\\|")


# ═══════════════════════════════════════════════════════════════
#  One-call helper
# ═══════════════════════════════════════════════════════════════

def append_ref_ids_if_needed(
    tool_name: str,
    data: Any,
    compact_md: str,
) -> str:
    """Extract reference IDs and append them to *compact_md*.

    The section is only appended when ``len(compact_md) >= MIN_EMIT_CHARS``.
    This keeps short results (error messages, empty results) uncluttered.
    """
    if len(compact_md) < MIN_EMIT_CHARS:
        return compact_md
    refs = extract_reference_ids(tool_name, data)
    if not refs:
        return compact_md
    return compact_md + format_reference_ids_section(refs)
