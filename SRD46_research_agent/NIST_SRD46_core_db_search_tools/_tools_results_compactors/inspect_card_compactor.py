"""
Markdown compactor for ``inspect_card()`` results.

Handles all three card types:
  * **metal**  — metal card + ligand-partner table + totals
  * **ligand** — ligand card + pKa table + metal-partner table + totals
  * **vlm**    — full measurement card + speciation + networks + citations

Public API
----------
``compact_inspect_card(data)``
    Returns a complete markdown string.  Auto-detects card type from
    the ``card_type`` key in *data*.  Falls back to raw-key dump for
    unknown types.

Usage::

    from ._tools_results_compactors.inspect_card_compactor import compact_inspect_card
    md = compact_inspect_card(inspect_card("metal_41"))
"""
from __future__ import annotations

import json as _json
from typing import Any


# ── tiny helpers ─────────────────────────────────────────────────────

def _cell(val: Any, max_len: int = 80) -> str:
    """Stringify a value for a markdown table cell, truncating if needed."""
    if val is None or str(val).strip() == "":
        return "***"
    s = str(val)
    if len(s) <= max_len:
        return s
    import re
    m = re.search(r' \([^)]+\)$', s)
    if m:
        suffix = m.group()
        prefix = s[:m.start()]
        avail = max_len - len(suffix) - 1
        if avail > 0:
            return prefix[:avail] + "…" + suffix
    return s[: max_len - 1] + "…"


def _fmt_logk(val: Any) -> str:
    if val is None:
        return "***"
    if isinstance(val, float):
        return f"{val:.2f}"
    return str(val)


def _json_oneline(obj: Any, max_len: int = 120) -> str:
    """Dump a parsed JSON field as a short single-line string."""
    if obj is None:
        return ""
    if isinstance(obj, str):
        s = obj
    else:
        s = _json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return s if len(s) <= max_len else s[: max_len - 1] + "…"


def _equation_summary(card: dict) -> str:
    """Build a concise human-readable equation string from the card."""
    eq_str = card.get("equation_str")
    if eq_str:
        return eq_str

    eq_py = card.get("equation")
    if eq_py:
        return str(eq_py)

    lhs = card.get("LHS_species_json")
    rhs = card.get("RHS_species_json")
    if lhs and rhs:
        def _side(species_list):
            parts = []
            for sp in species_list:
                s = sp.get("species", "?")
                p = sp.get("power", 1.0)
                parts.append(f"{int(p)}{s}" if p != 1.0 else s)
            return " + ".join(parts)
        return f"{_side(lhs)} ⇌ {_side(rhs)}"

    return ""


# ═════════════════════════════════════════════════════════════════
#  Metal card
# ═════════════════════════════════════════════════════════════════

def _fetch_ligand_smiles_for_metal(metal_id: int) -> list[str]:
    """Return all distinct ligand SMILES for partners of *metal_id*."""
    try:
        from .._db_connection import get_cards_db
    except Exception:
        return []
    sql = (
        "SELECT DISTINCT lc.ligand_SMILES "
        "FROM ligandmetal_card c "
        "JOIN ligand_card lc ON lc.ligand_id = c.ligand_id "
        "WHERE c.metal_id = ? AND lc.ligand_SMILES IS NOT NULL "
        "AND lc.ligand_SMILES != ''"
    )
    with get_cards_db() as conn:
        rows = conn.execute(sql, (metal_id,)).fetchall()
    return [r[0] for r in rows]


def _compact_metal(data: dict) -> str:
    pid = data.get("prefix_id", "?")
    card = data.get("card", {})
    partners = data.get("ligand_partners", [])
    total_lp = data.get("total_ligand_partners", "?")
    total_vlm = data.get("total_vlm_measurements", "?")

    name = card.get("metal_name_SRD", card.get("metal_name", "?"))
    symbol = card.get("symbol_pure", "") or "***"
    charge = card.get("charge", "?")
    smiles = card.get("SMILES", "")
    inchi = card.get("InChi", "")
    simple = "✓" if card.get("is_simple_ion") else ""
    orgmet = "✓" if card.get("is_organometallic") else ""

    lines = [
        f"## inspect_card — Metal | {pid}",
        "",
        f"**Name:** {name}  ",
        f"**Symbol:** {symbol} | **Charge:** {charge}  ",
    ]
    if smiles:
        lines.append(f"**SMILES:** `{smiles}`  ")
    if inchi:
        lines.append(f"**InChI:** `{inchi}`  ")
    flags = []
    if simple:
        flags.append("simple-ion")
    if orgmet:
        flags.append("organometallic")
    if flags:
        lines.append(f"**Flags:** {', '.join(flags)}  ")
    lines.append("")
    lines.append(f"**Partners:** {total_lp} ligand(s), {total_vlm} measurement(s) total")
    lines.append("")

    if partners:
        lines.append("| ligand_id | Ligand | # meas |")
        lines.append("|-----------|--------|--------|")
        for p in partners:
            lid = p.get("ligand_id", "?")
            lname = _cell(p.get("ligand_name", "?"), 60)
            n = p.get("n_measurements", "?")
            lines.append(f"| {lid} | {lname} | {n} |")
        if len(partners) < int(total_lp) if isinstance(total_lp, int) else False:
            lines.append(f"| … | *(showing top {len(partners)} of {total_lp})* | |")
    else:
        lines.append("*(no ligand partners)*")

    # ── functional-group statistics across all ligand partners ──
    from .entity_search_compactors import _functional_group_stats
    from .._normalization_helpers.id_prefixer import unprefix_id
    raw_mid = unprefix_id(pid)
    all_smiles = _fetch_ligand_smiles_for_metal(raw_mid)
    fg_lines = _functional_group_stats(all_smiles, title="all ligand partners")
    if fg_lines:
        lines.append("")
        lines.extend(fg_lines)

    lines.append("")
    return "\n".join(lines) + "\n"


# ═════════════════════════════════════════════════════════════════
#  Ligand card
# ═════════════════════════════════════════════════════════════════

def _compact_ligand(data: dict) -> str:
    pid = data.get("prefix_id", "?")
    card = data.get("card", {})
    pkas = data.get("pka_values", [])
    partners = data.get("metal_partners", [])
    total_mp = data.get("total_metal_partners", "?")
    total_vlm = data.get("total_vlm_measurements", "?")

    name = card.get("ligand_name_SRD", card.get("ligand_name", "?"))
    formula = card.get("formula", "") or "***"
    lclass = card.get("ligand_class_name", "") or "***"
    smiles = card.get("ligand_SMILES", "")
    inchi = card.get("ligand_InChi", "")
    hxl = card.get("definition_HxL", "")

    lines = [
        f"## inspect_card — Ligand | {pid}",
        "",
        f"**Name:** {name}  ",
        f"**Formula:** {formula} | **Class:** {lclass}  ",
    ]
    if smiles:
        lines.append(f"**SMILES:** `{smiles}`  ")
    if inchi:
        lines.append(f"**InChI:** `{inchi}`  ")
    if hxl:
        lines.append(f"**HxL definition:** {hxl}  ")
    lines.append("")

    # pKa section
    if pkas:
        lines.append(f"**pKa values:** {len(pkas)}")
        lines.append("")
        lines.append("| source_vlm | pKa | T (°C) | I (M) | From → To | Solvent | Method | Quality |")
        lines.append("|------------|-----|--------|-------|-----------|---------|--------|---------|")
        for pk in pkas:
            svlm = pk.get("source_vlm_id", "?")
            pka_val = _fmt_logk(pk.get("pKa"))
            temp = pk.get("temperature", "***")
            if temp is None: temp = "***"
            ionic = pk.get("ionic_strength", "***")
            if ionic is None: ionic = "***"
            bfrom = pk.get("bracket_from", "")
            bto = pk.get("bracket_to", "")
            bracket = f"{bfrom} → {bto}" if bfrom or bto else "***"
            solvent = _cell(pk.get("solvent", "") or "", 20)
            method = pk.get("method", "") or "***"
            qual = pk.get("quality", "") or "***"
            lines.append(f"| {svlm} | {pka_val} | {temp} | {ionic} | {bracket} | {solvent} | {method} | {qual} |")
    else:
        lines.append("**pKa values:** none")
    lines.append("")

    # Partners section
    lines.append(f"**Partners:** {total_mp} metal(s), {total_vlm} measurement(s) total")
    lines.append("")

    if partners:
        lines.append("| metal_id | Metal | # meas |")
        lines.append("|----------|-------|--------|")
        for p in partners:
            mid = p.get("metal_id", "?")
            mname = _cell(p.get("metal_name", "?"), 40)
            n = p.get("n_measurements", "?")
            lines.append(f"| {mid} | {mname} | {n} |")
        if isinstance(total_mp, int) and len(partners) < total_mp:
            lines.append(f"| … | *(showing top {len(partners)} of {total_mp})* | |")
    else:
        lines.append("*(no metal partners)*")

    lines.append("")
    return "\n".join(lines) + "\n"


# ═════════════════════════════════════════════════════════════════
#  VLM card
# ═════════════════════════════════════════════════════════════════

def _compact_vlm(data: dict) -> str:
    pid = data.get("prefix_id", "?")
    card = data.get("card", {})
    networks = data.get("networks", [])

    metal = card.get("metal_name", "?")
    ligand = card.get("ligand_name", "?")
    mid = card.get("metal_id", "?")
    lid = card.get("ligand_id", "?")
    bdid = card.get("beta_definition_id", "?")
    bdname = card.get("beta_definition_name", "")
    hxl_def = card.get("ligand_HxL_definition", "")
    logk = _fmt_logk(card.get("log_K"))
    ct = card.get("constant_type", "K")
    _DT_MAP = {"K": "log_K", "H": "H_rxn", "S": "S_rxn"}
    data_type = _DT_MAP.get(ct, ct or "***")
    temp = card.get("temperature", "***")
    if temp is None: temp = "***"
    ionic = card.get("ionic_strength", "***")
    if ionic is None: ionic = "***"
    solvent = card.get("solvent", "")
    rxn_type = card.get("reaction_type", "")
    eq = _equation_summary(card)
    uncertainty = card.get("uncertainty", "")
    raw_def = card.get("raw_definition", "")
    norm_def = card.get("normalized_definition", "")
    notes = card.get("notes", "") or ""
    m_smiles = card.get("metal_SMILES", "")
    m_inchi = card.get("metal_InChi", "")
    l_smiles = card.get("ligand_SMILES", "")
    l_inchi = card.get("ligand_InChi", "")

    lines = [
        f"## inspect_card — VLM | {pid}",
        "",
        "### Metal",
        f"**metal_id:** {mid} | **metal_name:** {metal}  ",
    ]
    if m_smiles:
        lines.append(f"**metal_SMILES:** `{m_smiles}`  ")
    if m_inchi:
        lines.append(f"**metal_InChi:** `{m_inchi}`  ")
    lines.append("")

    # ── Ligand ──
    lines.append("### Ligand")
    lines.append(f"**ligand_id:** {lid} | **ligand_name:** {ligand}  ")
    if hxl_def:
        lines.append(f"**ligand_HxL_definition:** {hxl_def}  ")
    if l_smiles:
        lines.append(f"**ligand_SMILES:** `{l_smiles}`  ")
    if l_inchi:
        lines.append(f"**ligand_InChi:** `{l_inchi}`  ")
    lines.append("")

    # ── Stability ──
    vlm_id = card.get("vlm_id", pid)
    lines.append("### Stability")
    lines.append(f"**vlm_id:** {vlm_id}  ")
    lines.append(f"**beta_definition_id:** {bdid} | **beta_definition_name:** {bdname or '***'}  ")
    lines.append(f"**data_type:** {data_type} | **{data_type}:** {logk}  ")
    lines.append(f"**temperature:** {temp} °C | **ionic_strength:** {ionic} M  ")
    if uncertainty:
        lines.append(f"**uncertainty:** {uncertainty}  ")
    if solvent:
        lines.append(f"**solvent:** {solvent} | **reaction_type:** {rxn_type or '***'}  ")
    if eq:
        lines.append(f"**equation:** {eq}  ")
    if raw_def and raw_def != norm_def:
        lines.append(f"**raw_definition:** {raw_def} → **normalized_definition:** {norm_def}  ")

    hxl = card.get("HxL_involved_json")
    pka_bracket_involved = card.get("pKa_bracket_involved", "") or ""
    if hxl or pka_bracket_involved:
        if isinstance(hxl, list):
            hxl_text = ", ".join(str(h) for h in hxl)
        else:
            hxl_text = str(hxl or "***")
        if pka_bracket_involved:
            lines.append(
                f"**Ligand_HxL_involved:** {hxl_text} | **pKa_bracket_involved:** {pka_bracket_involved}  "
            )
        else:
            lines.append(f"**Ligand_HxL_involved:** {hxl_text}  ")

    lhs = card.get("LHS_species_json")
    rhs = card.get("RHS_species_json")
    if lhs and rhs:
        def _side_summary(slist):
            return ", ".join(
                f"{sp.get('species', '?')}^{sp.get('power', 1)}"
                if sp.get("power", 1) != 1
                else sp.get("species", "?")
                for sp in slist
            )
        lines.append(f"**LHS_species:** {_side_summary(lhs)} | **RHS_species:** {_side_summary(rhs)}  ")

    if notes:
        lines.append(f"**notes:** {_cell(notes, 120)}  ")
    lines.append("")

    # ── Networks ──
    lines.append("### Networks")
    if networks:
        lines.append(f"{len(networks)} network(s)")
        lines.append("")
        lines.append("| network_id | Nodes | Edges | node_id | dup? |")
        lines.append("|------------|-------|-------|---------|------|")
        for n in networks:
            nid = n.get("network_id", "?")
            nc = n.get("node_count", "?")
            ec = n.get("edge_count", "?")
            ndid = n.get("node_id", "?")
            dup = "✓" if n.get("is_duplicate") else ""
            lines.append(f"| {nid} | {nc} | {ec} | {ndid} | {dup} |")
    else:
        lines.append("none")
    lines.append("")

    # ── Citations ──
    citations = data.get("citations", []) or []
    total_cit = data.get("total_citations", len(citations))
    lines.append(f"**total_citations:** {total_cit}")
    if citations:
        lines.append("")
        lines.append("| lit_id | shortcut | citation |")
        lines.append("|--------|----------|----------|")
        for c in citations:
            lit = c.get("literature_alt_id", "?")
            sc = c.get("shortcut", "") or "***"
            cite = _cell(c.get("citation", ""), 80)
            lines.append(f"| {lit} | {sc} | {cite} |")
    lines.append("")
    return "\n".join(lines) + "\n"


# ═════════════════════════════════════════════════════════════════
#  Error / not-found
# ═════════════════════════════════════════════════════════════════

def _compact_error(data: dict) -> str:
    pid = data.get("prefix_id", "?")
    err = data.get("error", "unknown error")
    return f"## inspect_card | {pid}\n\n**Error:** {err}\n"


# ═════════════════════════════════════════════════════════════════
#  Public dispatcher
# ═════════════════════════════════════════════════════════════════

def compact_inspect_card(data: dict) -> str:
    """Convert an ``inspect_card()`` result dict to compact markdown.

    Parameters
    ----------
    data : dict
        The return value of ``inspect_card(prefix_id)``.

    Returns
    -------
    str
        Markdown text.
    """
    from ._compactor_helpers import speciation_context_hint

    if not isinstance(data, dict):
        return f"**inspect_card:** unexpected data type {type(data).__name__}\n"

    if "error" in data:
        return _compact_error(data)

    pid = data.get("prefix_id", "")
    if pid.startswith("metal"):
        body = _compact_metal(data)
    elif pid.startswith("ligand"):
        body = _compact_ligand(data)
    elif pid.startswith("vlm"):
        body = _compact_vlm(data)
    else:
        return _compact_error({"prefix_id": pid, "error": f"Unrecognized prefix: {pid}"})
    return body + speciation_context_hint()
