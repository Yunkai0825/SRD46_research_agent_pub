"""Markdown compactor for ``search_networks()`` results.

Equilibrium networks link a metal-ligand pair to a graph of speciation
nodes (MLₙ species) and their associated beta-definition steps.

Three rendering tiers (threshold: 5 000 chars)
-----------------------------------------------
1. **Full** — one subsection per metal-ligand pair listing every network
   with its nodes, beta definitions, and condition ranges.
2. **Compact** — global beta_def legend + pair summary table (pair,
   n_networks, n_nodes, condition ranges) + separate table for the
   network with the most nodes + global-max detail block.
3. **Ultra-compact** — pair summary table with an inline ``max_net_id``
   column (no separate max-node table) + global-max detail block.

Public API
----------
``compact_network(rows)``
    Returns ``list[str]`` of markdown lines (no heading).
``compact_search_networks(data)``
    Returns a complete markdown string with ``## search_networks``
    heading and row count.
"""
from __future__ import annotations

from collections import OrderedDict, defaultdict

from ._compactor_helpers import speciation_context_hint, _cell, _esc, _ctype, _num, _range_str


# ═════════════════════════════════════════════════════════════════════
#  Public entry point — dispatcher
# ═════════════════════════════════════════════════════════════════════

def compact_network(rows: list[dict]) -> list[str]:
    """Return markdown lines for network results.

    Automatically picks full → compact → ultra-compact based on output
    length (threshold: 5 000 chars).
    """
    lines = _network_full(rows)
    full_text = "\n".join(lines)
    if len(full_text) <= 5000:
        return lines
    return _network_summary(rows)


# ═════════════════════════════════════════════════════════════════════
#  Full per-section layout
# ═════════════════════════════════════════════════════════════════════

def _network_full(rows: list[dict]) -> list[str]:
    """Full per-section network rendering (original layout)."""
    groups: OrderedDict[tuple, list[dict]] = OrderedDict()
    for r in rows:
        metal_id = r.get("metal_id", "?")
        metal_name = r.get("metal_name", "") or metal_id
        lig_id = r.get("ligand_id", "?")
        lig_name = r.get("ligand_name", "") or lig_id
        hxl = r.get("ligand_HxL_definition", "") or "***"
        groups.setdefault((metal_id, metal_name, lig_id, lig_name, hxl), []).append(r)

    lines: list[str] = []
    lines.append(
        "> **Reference equilibrium networks** — each network is built "
        "around room-temperature (≈20–25 °C) and low ionic-strength "
        "(≈0 M) anchor conditions.\n"
    )

    for (mid, mname, lid, lname, hxl), group_rows in groups.items():
        metal_disp = _esc(mname)
        lig_disp = _cell(lname, 60)

        # -- sub-group by network_db_id to merge nodes per network --
        nets: OrderedDict[str, list[dict]] = OrderedDict()
        for r in group_rows:
            nid = r.get("network_db_id", "?")
            nets.setdefault(str(nid), []).append(r)

        # -- collect all beta_def id→equation pairs across the group --
        beta_legend: OrderedDict[str, str] = OrderedDict()
        for r in group_rows:
            bid = r.get("beta_definition_id")
            if bid and bid not in beta_legend:
                eq = r.get("equation", "") or ""
                beta_legend[bid] = eq

        smiles = group_rows[0].get("ligand_SMILES", "") or "***"
        lines.append(
            f"### {metal_disp} + {lig_disp} — {len(nets)} network(s)"
        )
        lines.append(f"metal_id: {mid} | ligand_id: {lid} | ligand_def_HxL: {hxl} | ligand_SMILES: {smiles}\n")

        # -- beta_def legend table --
        lines.append("| beta_def | equation |")
        lines.append("|----------|----------|")
        for bid, eq in beta_legend.items():
            lines.append(f"| {bid} | `{_esc(eq)}` |" if eq else f"| {bid} | — |")
        lines.append("")

        # -- main network table --
        lines.append(
            "| network_id | node_counts | edge_counts | T_range | I_range "
            "| vlm_ids | beta_def_ids | type | values |"
        )
        lines.append(
            "|------------|-------------|-------------|---------|---------|"
            "------------|--------------|------|--------|"
        )

        for net_id, net_rows in nets.items():
            first = net_rows[0]
            node_c = first.get("node_count", "?")
            edge_c = first.get("edge_count", "?")
            t_range = _range_str(first.get("temp_min"), first.get("temp_max"))
            i_range = _range_str(first.get("ionic_min"), first.get("ionic_max"))
            vlm_ids = {r.get("vlm_id") for r in net_rows}

            # Collect beta_def ids ranked by ascending value
            beta_val: dict[str, float] = {}
            for r in net_rows:
                bid = r.get("beta_definition_id")
                val = r.get("log_K")
                if bid and bid not in beta_val:
                    beta_val[bid] = float(val) if val is not None else 0.0
            beta_ids = sorted(beta_val, key=lambda b: beta_val[b])

            # Preserve concrete evidence identity. A downstream agent cannot
            # cite or inspect a measurement represented only by a count.
            vlm_col = "; ".join(
                sorted(str(value) for value in vlm_ids if value)
            )

            # beta_def column: full tokenized names when ≤3, else "N diff beta_def"
            if len(beta_ids) <= 3:
                beta_col = "; ".join(beta_ids)
            else:
                beta_col = f"{len(beta_ids)} diff beta_def"

            # Group values by constant type → compute range per type
            by_type: dict[str, list[float]] = defaultdict(list)
            for r in net_rows:
                ctype = _ctype(r.get("constant_type"))
                val = r.get("log_K")
                if val is not None:
                    by_type[ctype].append(float(val))

            type_labels = []
            value_ranges = []
            for ct, vals in by_type.items():
                type_labels.append(ct)
                if len(vals) == 1:
                    value_ranges.append(_num(vals[0]))
                else:
                    lo, hi = min(vals), max(vals)
                    value_ranges.append(f"{_num(lo)}~{_num(hi)}")

            type_col = "; ".join(type_labels)
            val_col = "; ".join(value_ranges)

            lines.append(
                f"| {net_id} | {node_c} | {edge_c} | {t_range} | {i_range} "
                f"| {vlm_col} | {beta_col} | {type_col} | {val_col} |"
            )

        # -- detail table for the first (reference-state) network --
        first_net_id = next(iter(nets))
        first_net_rows = nets[first_net_id]
        first_r = first_net_rows[0]
        first_node_c = first_r.get("node_count", "?")
        first_t = _range_str(first_r.get("temp_min"), first_r.get("temp_max"))
        first_i = _range_str(first_r.get("ionic_min"), first_r.get("ionic_max"))
        lines.append(
            f"\n#### Reference-state network: {first_net_id} "
            f"({first_node_c} nodes)"
        )
        lines.append(
            f"> First network — reference conditions "
            f"(T {first_t} °C, I {first_i} M).\n"
        )
        lines.append("| vlm_id | beta_def | equation | type | value |")
        lines.append("|--------|----------|----------|------|-------|")
        for r in sorted(first_net_rows,
                        key=lambda r: float(r.get("log_K") or 0)):
            bid = r.get("beta_definition_id", "?")
            eq = _esc(r.get("equation", "") or "")
            ctype = _ctype(r.get("constant_type"))
            val = _num(r.get("log_K"))
            vlm_id = r.get("vlm_id", "?")
            lines.append(
                f"| {vlm_id} | {bid} | `{eq}` | {ctype} | {val} |"
            )

        lines.append("")
    return lines


# ═════════════════════════════════════════════════════════════════════
#  Compact / ultra-compact summary layout
# ═════════════════════════════════════════════════════════════════════

def _network_summary(rows: list[dict]) -> list[str]:
    """Collapsed layout used when the full output exceeds ~5 000 chars.

    Layout
    ------
    1. Global beta_def legend table
    2. One-row-per-pair summary table (T/I range, net count, max-node
       network detail inline)
    3. Detail section for the global max-node network

    If the result still exceeds 5 000 chars, the separate max-node
    table is dropped and ``max_net_id`` is folded into the summary
    table instead (ultra-compact).
    """
    # --- group rows ---
    groups: OrderedDict[tuple, list[dict]] = OrderedDict()
    for r in rows:
        mid = r.get("metal_id", "?")
        mname = r.get("metal_name", "") or mid
        lid = r.get("ligand_id", "?")
        lname = r.get("ligand_name", "") or lid
        hxl = r.get("ligand_HxL_definition", "") or "***"
        groups.setdefault((mid, mname, lid, lname, hxl), []).append(r)

    # --- global beta_def legend ---
    beta_legend: OrderedDict[str, str] = OrderedDict()
    for r in rows:
        bid = r.get("beta_definition_id")
        if bid and bid not in beta_legend:
            beta_legend[bid] = r.get("equation", "") or ""

    lines: list[str] = []
    lines.append(
        "> **Reference equilibrium networks (compact)** — each network is "
        "built around room-temperature (≈20–25 °C) and low ionic-strength "
        "(≈0 M) anchor conditions.\n"
    )

    # -- global beta_def legend --
    lines.append("### Beta-definition legend")
    lines.append("| beta_def | equation |")
    lines.append("|----------|----------|")
    for bid, eq in beta_legend.items():
        lines.append(f"| {bid} | `{_esc(eq)}` |" if eq else f"| {bid} | — |")
    lines.append("")

    # --- build per-pair summary + track global max-node network ---
    global_max_nodes = 0
    global_max_detail: list[dict] = []
    global_max_pair_key: tuple | None = None
    global_max_net_id: str = ""

    pair_summaries: list[dict] = []
    for key, group_rows in groups.items():
        mid, mname, lid, lname, hxl = key

        # sub-group by network
        nets: OrderedDict[str, list[dict]] = OrderedDict()
        for r in group_rows:
            nid = str(r.get("network_db_id", "?"))
            nets.setdefault(nid, []).append(r)

        # overall T/I range across all networks in this pair
        temps = [r.get("temp_min") for r in group_rows] + [r.get("temp_max") for r in group_rows]
        ionics = [r.get("ionic_min") for r in group_rows] + [r.get("ionic_max") for r in group_rows]
        temps = [t for t in temps if t is not None]
        ionics = [i for i in ionics if i is not None]
        t_range = _range_str(min(temps), max(temps)) if temps else "***"
        i_range = _range_str(min(ionics), max(ionics)) if ionics else "***"

        # find max-node network in this pair
        max_net_id = max(nets, key=lambda n: max(
            r.get("node_count", 0) or 0 for r in nets[n]))
        max_net_rows = nets[max_net_id]
        max_node_count = max(r.get("node_count", 0) or 0 for r in max_net_rows)

        # inline detail: beta_def→logK for the richest network
        beta_val: dict[str, float] = {}
        for r in max_net_rows:
            bid = r.get("beta_definition_id")
            val = r.get("log_K")
            if bid and bid not in beta_val:
                beta_val[bid] = float(val) if val is not None else 0.0
        sorted_bids = sorted(beta_val, key=lambda b: beta_val[b])

        # max-node network columns (same format as full-mode table)
        max_first = max_net_rows[0]
        max_edge_c = max_first.get("edge_count", "?")
        max_t_range = _range_str(max_first.get("temp_min"), max_first.get("temp_max"))
        max_i_range = _range_str(max_first.get("ionic_min"), max_first.get("ionic_max"))
        max_vlm_ids = {r.get("vlm_id") for r in max_net_rows}
        max_vlm_col = "; ".join(
            sorted(str(value) for value in max_vlm_ids if value)
        )

        if len(sorted_bids) <= 3:
            max_beta_col = "; ".join(sorted_bids)
        else:
            max_beta_col = f"{len(sorted_bids)} diff beta_def"

        max_by_type: dict[str, list[float]] = defaultdict(list)
        for r in max_net_rows:
            ctype = _ctype(r.get("constant_type"))
            val = r.get("log_K")
            if val is not None:
                max_by_type[ctype].append(float(val))
        max_type_labels = []
        max_value_ranges = []
        for ct, vals in max_by_type.items():
            max_type_labels.append(ct)
            if len(vals) == 1:
                max_value_ranges.append(_num(vals[0]))
            else:
                lo, hi = min(vals), max(vals)
                max_value_ranges.append(f"{_num(lo)}~{_num(hi)}")
        max_type_col = "; ".join(max_type_labels)
        max_val_col = "; ".join(max_value_ranges)

        ligand_smiles = group_rows[0].get("ligand_SMILES", "") or "***"

        pair_summaries.append({
            "metal": _esc(mname), "metal_id": mid,
            "ligand": _cell(lname, 40), "ligand_id": lid, "HxL": hxl,
            "ligand_SMILES": ligand_smiles,
            "T_range": t_range, "I_range": i_range,
            "net_count": len(nets), "max_nodes": max_node_count,
            "max_net_id": max_net_id, "max_edge_counts": max_edge_c,
            "max_T_range": max_t_range, "max_I_range": max_i_range,
            "max_vlm_ids": max_vlm_col, "max_beta_def_ids": max_beta_col,
            "max_type": max_type_col, "max_values": max_val_col,
        })

        if max_node_count > global_max_nodes:
            global_max_nodes = max_node_count
            global_max_detail = max_net_rows
            global_max_pair_key = key
            global_max_net_id = max_net_id

    # --- helper: build global max-node detail lines ---
    def _global_max_detail_lines() -> list[str]:
        detail: list[str] = []
        if global_max_pair_key and global_max_detail:
            mid, mname, lid, lname, hxl = global_max_pair_key
            detail.append(
                f"### Global max-node network: {_esc(mname)} + {_cell(lname, 60)}"
            )
            detail.append(
                f"network_id: {global_max_net_id} | metal_id: {mid} | "
                f"ligand_id: {lid} | ligand_def_HxL: {hxl} | "
                f"nodes: {global_max_nodes}\n"
            )
            detail.append("| vlm_id | beta_def | equation | type | value |")
            detail.append("|--------|----------|----------|------|-------|")
            for r in sorted(global_max_detail,
                            key=lambda r: float(r.get("log_K") or 0)):
                bid = r.get("beta_definition_id", "?")
                eq = _esc(r.get("equation", "") or "")
                ctype = _ctype(r.get("constant_type"))
                val = _num(r.get("log_K"))
                vlm_id = r.get("vlm_id", "?")
                detail.append(
                    f"| {vlm_id} | {bid} | `{eq}` | {ctype} | {val} |"
                )
            detail.append("")
        return detail

    # --- try full compact layout (summary + max-node table + global detail) ---
    full_lines: list[str] = list(lines)

    full_lines.append("### Metal-ligand pair summary")
    full_lines.append(
        "| metal | metal_id | ligand | ligand_id | HxL "
        "| T_range | I_range | net_count | max_nodes | ligand_SMILES |"
    )
    full_lines.append(
        "|-------|----------|--------|-----------|-----"
        "|---------|---------|-----------|----------|---------------|"
    )
    for s in pair_summaries:
        full_lines.append(
            f"| {s['metal']} | {s['metal_id']} | {s['ligand']} | {s['ligand_id']} "
            f"| {s['HxL']} | {s['T_range']} | {s['I_range']} | {s['net_count']} "
            f"| {s['max_nodes']} | {s['ligand_SMILES']} |"
        )
    full_lines.append("")

    full_lines.append("### Max-node network per pair")
    full_lines.append(
        "| metal | metal_id | ligand | ligand_id "
        "| max_net_id | max_nodes | max_edge_counts "
        "| max_T_range | max_I_range | max_vlm_ids "
        "| max_beta_def_ids | max_type | max_values |"
    )
    full_lines.append(
        "|-------|----------|--------|----------"
        "|------------|-----------|------------------"
        "|-------------|-------------|----------------"
        "|------------------|----------|------------|"
    )
    for s in pair_summaries:
        full_lines.append(
            f"| {s['metal']} | {s['metal_id']} | {s['ligand']} | {s['ligand_id']} "
            f"| {s['max_net_id']} "
            f"| {s['max_nodes']} | {s['max_edge_counts']} "
            f"| {s['max_T_range']} | {s['max_I_range']} "
            f"| {s['max_vlm_ids']} | {s['max_beta_def_ids']} "
            f"| {s['max_type']} | {s['max_values']} |"
        )
    full_lines.append("")
    full_lines.extend(_global_max_detail_lines())

    if len("\n".join(full_lines)) <= 5000:
        return full_lines

    # --- ultra-compact: merge max_net_id into summary, drop max-node table ---
    lines.append("### Metal-ligand pair summary")
    lines.append(
        "| metal | metal_id | ligand | ligand_id | HxL "
        "| T_range | I_range | net_count | max_nodes | max_net_id | max_vlm_ids | ligand_SMILES |"
    )
    lines.append(
        "|-------|----------|--------|-----------|-----"
        "|---------|---------|-----------|----------|------------|-------------|---------------|"
    )
    for s in pair_summaries:
        lines.append(
            f"| {s['metal']} | {s['metal_id']} | {s['ligand']} | {s['ligand_id']} "
            f"| {s['HxL']} | {s['T_range']} | {s['I_range']} | {s['net_count']} "
            f"| {s['max_nodes']} | {s['max_net_id']} | {s['max_vlm_ids']} "
            f"| {s['ligand_SMILES']} |"
        )
    lines.append("")
    lines.extend(_global_max_detail_lines())

    return lines


def compact_search_networks(data: list[dict] | dict) -> str:
    """Compact markdown for ``search_networks()`` results."""
    # wrap_tool() wraps list results as {"results": [...], "n_results": N}
    if isinstance(data, dict):
        data = data.get("results", data)
    if not isinstance(data, list):
        return f"**search_networks:** unexpected data type {type(data).__name__}\n"
    if not data:
        return "## search_networks\n\n*(no results)*\n" + speciation_context_hint()
    n = len(data)
    lines = [f"## search_networks \u2014 {n} row(s)", ""]
    lines.extend(compact_network(data))
    lines.append("")
    return "\n".join(lines) + "\n" + speciation_context_hint()
