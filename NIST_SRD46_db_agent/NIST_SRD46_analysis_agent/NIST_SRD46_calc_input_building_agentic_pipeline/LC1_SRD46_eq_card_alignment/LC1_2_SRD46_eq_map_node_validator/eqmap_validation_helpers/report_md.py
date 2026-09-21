"""report_md.py — markdown renderers for the eq-map screen pipeline.

Two renderers, each consumed by a different LLM agent:

* :func:`render_screen_md` — the **L2_1_1 validator's** input.  One
  block per node showing flags, severity, the chosen value, and a
  compact neighbour-summary table.  Quick to scan; designed for the
  validator to either confirm "ok / warn but acceptable" or escalate
  a node to L3 with a precise reason.

* :func:`render_neighbors_md` — the **L3 fixer's** input for one node.
  The full sibling collection grouped by (T, I) bucket so the LLM has
  every available datapoint at hand when picking a replacement
  strategy (use-row / median / mean / drop).
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .neighbor_query import NeighborRow
from .node_screen import EqMapScreen, NodeScreen


# ════════════════════════════════════════════════════════════════════
#  Validator-facing report  (one eq-map → one markdown document)
# ════════════════════════════════════════════════════════════════════

def render_screen_md(screen: EqMapScreen) -> str:
    """Render the per-pair screen as ONE condensed table.

    Each row is one node of the eq-map. The agent uses ``inspect_node``
    or ``get_node_neighbors`` to drill into any row whose flags warrant
    a closer look (or whose ``severity`` is not ``ok``).
    """
    lines: List[str] = []
    lines.append(f"# Eq-map screen — {screen.pair_key}")
    lines.append("")
    lines.append(
        f"Request conditions: **T = {screen.request_T_C} °C**, "
        f"**I = {screen.request_I_M} M**"
    )
    lines.append(
        f"Nodes: **{len(screen.nodes)}** "
        f"(critical = {len(screen.critical_node_keys)}, "
        f"warn = {len(screen.warn_node_keys)})"
    )
    lines.append("")
    lines.append("## Per-node summary")
    lines.append("")
    lines.append(
        "| # | node_key | equation | "
        "chosen vlm@T,I = K | "
        "n_K | min / med / mean / max | "
        "nearest@req vlm@T,I = K (ΔT, ΔI) | "
        "flags |"
    )
    lines.append(
        "|--:|----------|----------|"
        "--------------------|"
        "----:|------------------------|"
        "-----------------------------------|"
        "-------|"
    )
    for i, ns in enumerate(screen.nodes, start=1):
        lines.append(_render_node_row(
            i, ns, screen.request_T_C, screen.request_I_M,
        ))
    lines.append("")

    lines.append("## How to drill down")
    lines.append("")
    lines.append(
        "- `inspect_node(node_key)` — re-prints this row plus its "
        "K-sibling summary and nearest-at-request entry."
    )
    lines.append(
        "- `get_node_neighbors(node_key)` — full table of EVERY sibling "
        "vlm row for that (metal, ligand, beta_definition) triple, "
        "bucketed by (T, I), with the currently chosen row marked. "
        "Use this whenever the table row hints at a sign-split / "
        "mean-median gap / nearest-request mismatch and you need to "
        "see the actual values."
    )
    return "\n".join(lines).rstrip() + "\n"


def _render_node_row(
    idx: int,
    ns: NodeScreen,
    request_T_C: float,
    request_I_M: float,
) -> str:
    n = ns.node
    s = ns.K_neighbor_summary
    eqn = (n.equation_str or "(unknown)").replace("|", "\\|")
    chosen = (
        f"vlm_{n.vlm_id}@({n.temperature_C},{n.ionic_strength_M}) = "
        f"{n.constant_type}{n.constant_value:+.3f}"
    )
    if s.get("n", 0) > 0:
        sib_n = s["n"]
        sib_stats = (
            f"{s['min']:+.3f} / {s['median']:+.3f} / "
            f"{s['mean']:+.3f} / {s['max']:+.3f}"
        )
    else:
        sib_n = 0
        sib_stats = "—"
    if ns.nearest_K_at_request:
        nr = ns.nearest_K_at_request
        nearest = (
            f"vlm_{nr['vlm_id']}@({nr['T_C']},{nr['I_M']}) = "
            f"K{nr['K']:+.3f} ({_fmt_delta(nr['dT_C'])} °C, "
            f"{_fmt_delta(nr['dI_M'])} M)"
        )
    else:
        nearest = "—"
    flags = ", ".join(ns.flags) if ns.flags else "—"
    return (
        f"| {idx} | `{n.node_key}` | `{eqn}` "
        f"| {chosen} | {sib_n} | {sib_stats} | {nearest} | `{flags}` |"
    )


# ────────────────────────────────────────────────────────────────────
#  Per-node drill-down (used by `inspect_node` tool)
# ────────────────────────────────────────────────────────────────────

def _render_node_block(
    ns: NodeScreen,
    request_T_C: float,
    request_I_M: float,
) -> List[str]:
    """Verbose per-node block, returned by the `inspect_node` tool."""
    n = ns.node
    out: List[str] = []
    out.append(f"### `{n.node_key}`  — severity: **{ns.severity}**")
    out.append("")
    out.append(f"- equation: `{n.equation_str or '(unknown)'}`")
    out.append(
        f"- chosen vlm_id = **{n.vlm_id}**, "
        f"network_db_id = {n.network_db_id}"
    )
    out.append(
        f"- chosen value: **{n.constant_type} = {n.constant_value:+.3f}** "
        f"@ T = {n.temperature_C} °C, I = {n.ionic_strength_M} M"
    )
    out.append(
        f"- siblings (same metal/ligand/beta_def): "
        f"{ns.n_neighbors} total, {ns.n_K_neighbors} of constant_type='K'"
    )
    if ns.flags:
        out.append(f"- flags: `{', '.join(ns.flags)}`")
    else:
        out.append("- flags: _(none)_")
    if ns.notes:
        out.append("- notes:")
        for note in ns.notes:
            out.append(f"  - {note}")

    if ns.K_neighbor_summary.get("n", 0) > 0:
        s = ns.K_neighbor_summary
        out.append("")
        out.append("Sibling K summary:")
        out.append("")
        out.append("| n | min | median | mean | max |")
        out.append("|---|-----|--------|------|-----|")
        out.append(
            f"| {s['n']} | {s['min']:+.3f} | {s['median']:+.3f} | "
            f"{s['mean']:+.3f} | {s['max']:+.3f} |"
        )

    if ns.nearest_K_at_request:
        n_ = ns.nearest_K_at_request
        out.append("")
        out.append(
            f"Nearest K-sibling to request: vlm_id={n_['vlm_id']}, "
            f"K={n_['K']:+.3f} @ T={n_['T_C']} °C "
            f"(ΔT={_fmt_delta(n_['dT_C'])}), "
            f"I={n_['I_M']} M (ΔI={_fmt_delta(n_['dI_M'])})"
        )
    out.append("")
    out.append(
        "Call `get_node_neighbors(node_key)` to see the full vlm-row "
        "table for this (metal, ligand, beta_definition) triple."
    )
    return out


# ════════════════════════════════════════════════════════════════════
#  L3-fixer-facing report  (one node → all siblings, bucketed)
# ════════════════════════════════════════════════════════════════════

def render_neighbors_md(
    *,
    pair_key: str,
    node_key: str,
    chosen_vlm_id: Optional[int],
    chosen_value: float,
    chosen_constant_type: str,
    chosen_T_C: Optional[float],
    chosen_I_M: Optional[float],
    request_T_C: float,
    request_I_M: float,
    neighbors: Sequence[NeighborRow],
    flags: Optional[Sequence[str]] = None,
    notes: Optional[Sequence[str]] = None,
) -> str:
    lines: List[str] = []
    lines.append(f"# L3 fixer collection — `{node_key}`")
    lines.append("")
    lines.append(f"Pair: `{pair_key}`")
    lines.append(
        f"Request conditions: **T = {request_T_C} °C**, "
        f"**I = {request_I_M} M**"
    )
    lines.append("")
    lines.append("## Currently chosen row")
    lines.append("")
    lines.append(
        f"- vlm_id = **{chosen_vlm_id}**, "
        f"{chosen_constant_type} = **{chosen_value:+.3f}** "
        f"@ T = {chosen_T_C} °C, I = {chosen_I_M} M"
    )
    if flags:
        lines.append(f"- flags: `{', '.join(flags)}`")
    if notes:
        lines.append("- notes:")
        for note in notes:
            lines.append(f"  - {note}")
    lines.append("")

    lines.append("## All siblings for this (metal, ligand, beta_def)")
    lines.append("")
    if not neighbors:
        lines.append("_No siblings found in the database._")
        return "\n".join(lines).rstrip() + "\n"

    buckets = _bucket_by_TI(neighbors)
    lines.append(f"({len(neighbors)} sibling rows in {len(buckets)} (T, I) buckets)")
    lines.append("")
    for (T_key, I_key), rows in sorted(buckets, key=lambda kv: (kv[0][0] or 1e9, kv[0][1] or 1e9)):
        T_label = "?" if T_key is None else f"{T_key} °C"
        I_label = "?" if I_key is None else f"{I_key} M"
        dT = "?" if T_key is None else _fmt_delta(T_key - request_T_C)
        dI = "?" if I_key is None else _fmt_delta(I_key - request_I_M)
        lines.append(f"### Bucket T ≈ {T_label} (ΔT={dT}), I ≈ {I_label} (ΔI={dI})")
        lines.append("")
        lines.append("| vlm_id | type | value | T (°C) | I (M) | source | duplicate | used_in_map |")
        lines.append("|--------|------|-------|--------|-------|--------|-----------|-------------|")
        for r in rows:
            mark = " **←chosen**" if (chosen_vlm_id is not None and r.vlm_id == chosen_vlm_id) else ""
            lines.append(
                f"| {r.vlm_id}{mark} | {r.constant_type} | "
                f"{r.constant_value:+.3f} | {r.temperature_C} | "
                f"{r.ionic_strength_M} | {r.source_table} | "
                f"{int(bool(r.is_duplicate))} | {int(bool(r.used_in_map))} |"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# ════════════════════════════════════════════════════════════════════
#  Helpers
# ════════════════════════════════════════════════════════════════════

_T_BUCKET_C = 5.0
_I_BUCKET_M = 0.05


def _bucket_by_TI(
    rows: Iterable[NeighborRow],
) -> List[Tuple[Tuple[Optional[float], Optional[float]], List[NeighborRow]]]:
    """Group neighbour rows by rounded (T, I) bucket.

    Returns a list of ((T_bucket, I_bucket), rows) tuples so callers
    can sort deterministically.
    """
    grouped: Dict[Tuple[Optional[float], Optional[float]], List[NeighborRow]] = defaultdict(list)
    for r in rows:
        T_key = _round_bucket(r.temperature_C, _T_BUCKET_C)
        I_key = _round_bucket(r.ionic_strength_M, _I_BUCKET_M)
        grouped[(T_key, I_key)].append(r)
    return list(grouped.items())


def _round_bucket(v: Optional[float], step: float) -> Optional[float]:
    if v is None:
        return None
    if math.isnan(v):
        return None
    return round(v / step) * step


def _fmt_delta(v: Optional[float]) -> str:
    if v is None:
        return "?"
    return f"{v:+.2f}"
