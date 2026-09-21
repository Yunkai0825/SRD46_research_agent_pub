"""
pH Sweep Export â€” CSV export, verdict, envelope, and output orchestration.
==========================================================================
All output-generation logic for pH sweep results:

  - ``export_csv()``              â€” full-resolution CSV (5 files)
  - ``export_envelope_csv()``     â€” sampled fraction envelopes per component
  - ``generate_dp_envelope_csv()``â€” Douglas-Peucker simplified concentration envelope
  - ``read_envelope_csv()``       â€” read a DP envelope CSV back
  - ``write_verdict_document()``  â€” pure-calculation verdict markdown
  - ``generate_all_output()``     â€” master orchestrator (plots + CSV + verdict)

Also provides sweep-registry metadata (``SWEEP_ID``, ``sweep_fn``, etc.).
"""
from __future__ import annotations

import csv
import json as _json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_core_numcalc_pipeline.thermodynamics_helpers.speciation_dataclasses import SpeciationCurve
from sweep_pipelines._path_utils import long_path

# â”€â”€ Sweep-registry metadata â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

from .pH_sweep_main import run_pH_sweep

sweep_fn = run_pH_sweep

SWEEP_ID = "pH_sweep"
SWEEP_DESCRIPTION = (
    "Standard pH sweep: linearly sample pH from pH_min to pH_max, "
    "solve Gibbs free-energy minimisation at each point with "
    "continuation seeding and bidirectional retry."
)
SWEEP_PARAMS = {
    "pH_min": {"type": "float", "required": True,
               "description": "pH sweep lower bound"},
    "pH_max": {"type": "float", "required": True,
               "description": "pH sweep upper bound"},
    "n_points": {"type": "int", "required": True,
                 "description": "Number of pH grid points"},
    "use_activity": {"type": "bool", "required": True,
                     "description": "Apply Davies activity corrections"},
    "include_solids": {"type": "bool", "required": True,
                       "description": "Include solid/dissolution equilibria"},
}


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  Full-resolution CSV export
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def export_csv(
    curve: SpeciationCurve,
    output_dir: Path | str,
    prefix: str = "",
) -> Dict[str, str]:
    """Export speciation data as CSV files.

    Creates five CSV files:
      - ``<prefix>_frac_metal.csv``       â€” fraction-of-metal vs pH
      - ``<prefix>_frac_ligand.csv``      â€” fraction-of-ligand vs pH
      - ``<prefix>_log_conc.csv``         â€” log10[species] vs pH
      - ``<prefix>_concentrations.csv``   â€” molar concentrations vs pH
      - ``<prefix>_state_metrics.csv``    â€” ionic-strength and convergence vs pH
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    pfx = f"{prefix}_" if prefix else ""

    sp_ids = list(curve.species.keys())
    sp_labels = [curve.species[sid].label for sid in sp_ids]
    paths: Dict[str, str] = {}

    def _merge_component_fracs(
        per_component: Dict[str, Dict[str, float]],
        fallback: Dict[str, float],
    ) -> Dict[str, float]:
        """Flatten ``{component_id: {species_id: fraction}}`` into a single
        ``{species_id: fraction}`` map covering *every* metal / ligand.

        ``PointResult.frac_M`` / ``frac_L`` are single-component
        convenience copies (first metal / first ligand only).  Reading them
        directly zeroes out every species that belongs to the 2nd..Nth
        component in a multi-metal / multi-ligand system, which is exactly
        why ``frac_metal.csv`` showed only the first metal populated.  The
        per-component ``frac_metals`` / ``frac_ligands`` maps carry the
        correct own-component-normalised fraction for every species, so we
        union them here.  For the rare species shared by more than one
        component (heterobimetallic), keep the larger-magnitude fraction so
        the column reflects the species' dominant owning component.
        """
        if not per_component:
            return fallback or {}
        merged: Dict[str, float] = {}
        for cid in sorted(per_component):
            for sid, val in per_component[cid].items():
                prev = merged.get(sid)
                if prev is None or abs(val) > abs(prev):
                    merged[sid] = val
        return merged

    def _write(fname: str, store_fn, key: str) -> str:
        fpath = out / fname
        with open(long_path(fpath), "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["pH"] + sp_labels)
            for j, pr in enumerate(curve.results):
                store = store_fn(pr)
                row = [f"{curve.pH_values[j]:.4f}"]
                for sid in sp_ids:
                    row.append(f"{store.get(sid, 0.0):.6e}")
                writer.writerow(row)
        paths[key] = str(fpath)
        return str(fpath)

    _write(f"{pfx}frac_metal.csv",
           lambda pr: _merge_component_fracs(pr.frac_metals, pr.frac_M),
           "csv_frac_metal")
    _write(f"{pfx}frac_ligand.csv",
           lambda pr: _merge_component_fracs(pr.frac_ligands, pr.frac_L),
           "csv_frac_ligand")
    _write(f"{pfx}log_conc.csv",        lambda pr: pr.log_conc, "csv_log_conc")
    _write(f"{pfx}concentrations.csv",  lambda pr: pr.conc,     "csv_concentrations")

    state_path = out / f"{pfx}state_metrics.csv"
    state_provenance = list(curve.state_provenance or [])
    run_params = dict(curve.run_params or {})
    total_columns: List[str] = []
    for group_name in (
        "parent_element_totals", "redox_state_subtotals", "component_totals",
    ):
        for key in (run_params.get(group_name) or {}):
            if key not in total_columns:
                total_columns.append(key)
    with open(long_path(state_path), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "pH", "E_V", "redox_mode", *total_columns,
            "ionic_strength_used", "calculated_ionic_strength",
            "charge_imbalance_eq_per_L", "inert_cation_conc",
            "inert_anion_conc", "converged", "iterations", "residual",
        ])
        for j, pr in enumerate(curve.results):
            state = state_provenance[j] if j < len(state_provenance) else {}
            E_V = state.get("E_V", run_params.get("fixed_E_V"))
            E_text = "" if E_V is None else f"{float(E_V):.12g}"
            redox_mode = state.get(
                "redox_mode", run_params.get("redox_mode", ""))
            total_values = []
            for key in total_columns:
                value = state.get(key)
                total_values.append(
                    "" if value is None else f"{float(value):.12g}")
            writer.writerow([
                f"{curve.pH_values[j]:.4f}",
                E_text,
                redox_mode,
                *total_values,
                f"{pr.ionic_strength_used:.6e}",
                f"{pr.calculated_ionic_strength:.6e}",
                f"{pr.charge_imbalance:.6e}",
                f"{pr.inert_cation_conc:.6e}",
                f"{pr.inert_anion_conc:.6e}",
                int(pr.converged),
                pr.iters,
                f"{pr.residual:.6e}",
            ])
    paths["csv_state_metrics"] = str(state_path)
    return paths


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  Envelope CSV â€” sampled fractions per component
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def export_envelope_csv(
    curve: SpeciationCurve,
    output_dir: Path | str,
    prefix: str = "",
    n_points: int = 29,
    frac_threshold: float = 0.01,
) -> Dict[str, str]:
    """Export sampled envelope fractions per component as CSV files.

    One CSV per metal and per ligand component, with *n_points*
    evenly-spaced pH samples and only species above *frac_threshold*.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    pfx = f"{prefix}_" if prefix else ""
    paths: Dict[str, str] = {}

    pH_all = curve.pH_values
    n_total = len(pH_all)
    if n_total == 0:
        return paths
    if n_points < 21:
        n_points = 25
    if n_points >= n_total:
        sample_idx = list(range(n_total))
    else:
        sample_idx = sorted(set(
            int(round(i * (n_total - 1) / (n_points - 1)))
            for i in range(n_points)
        ))

    def _write_component(component_id: str) -> None:
        sp_list: List[Tuple[str, Any, List[float]]] = []
        for sp_id, sp in curve.species.items():
            vals = curve.series_multi(sp_id, component_id)
            if max(vals) >= frac_threshold:
                sp_list.append((sp_id, sp, vals))
        if not sp_list:
            return
        fname = f"{pfx}envelope_{component_id}.csv"
        fpath = out / fname
        with open(long_path(fpath), "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["pH"] + [sp.label for _, sp, _ in sp_list])
            for j in sample_idx:
                row = [f"{pH_all[j]:.4f}"]
                for _, _, vals in sp_list:
                    row.append(f"{vals[j]:.6f}")
                writer.writerow(row)
        paths[f"csv_envelope_{component_id}"] = str(fpath)

    for mid in sorted(curve.total_metals):
        _write_component(mid)
    for lid in sorted(curve.total_ligands):
        _write_component(lid)
    return paths


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  Douglas-Peucker concentration envelope
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

CONC_FLOOR = 1e-9
MAX_ENVELOPE_POINTS = 10


def _simplify_to_n(
    pts: List[Tuple[float, float]], target_n: int,
) -> List[Tuple[float, float]]:
    """Select ~target_n representative points via farthest-point insertion.

    Delegates to the shared topology-compactor ``subsample_to_n_points`` helper
    which performs greedy RDP-style selection in normalised coordinate space.
    """
    if len(pts) <= target_n:
        return pts
    from .._output_and_plotting._output_topology_compactor.simplifier_rdp import subsample_to_n_points
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x_range = (min(xs), max(xs)) if xs else (0.0, 1.0)
    y_range = (min(ys), max(ys)) if ys else (0.0, 1.0)
    simplified, _ = subsample_to_n_points(
        pts, n=target_n, pH_range=x_range, E_range=y_range)
    return simplified


def generate_dp_envelope_csv(
    curve: SpeciationCurve,
    output_dir: str,
    prefix: str = "",
) -> Dict[str, Any]:
    """Generate Douglas-Peucker simplified concentration envelope CSV.

    For each species with peak concentration >= CONC_FLOOR, the curve
    is filtered, split into contiguous segments, and each segment is
    DP-simplified to ~MAX_ENVELOPE_POINTS points on log-concentration.

    Returns dict with ``status``, ``file_path``, ``species_count``,
    ``segment_counts``, ``total_columns``.
    """
    pH_all = curve.pH_values
    envelope_data: Dict[str, List[Dict]] = {}

    for sp_id, sp in curve.species.items():
        conc_vals = curve.series(sp_id, "conc")
        peak = max(conc_vals) if conc_vals else 0.0
        if peak < CONC_FLOOR:
            continue

        segments: List[List[Tuple[float, float]]] = []
        current_seg: List[Tuple[float, float]] = []
        for pH, c in zip(pH_all, conc_vals):
            if c >= CONC_FLOOR:
                current_seg.append((pH, c))
            else:
                if current_seg:
                    segments.append(current_seg)
                    current_seg = []
        if current_seg:
            segments.append(current_seg)
        if not segments:
            continue

        species_segs = []
        for seg_idx, seg_pts in enumerate(segments):
            log_pts = [(p, math.log10(c)) for p, c in seg_pts]
            simplified_log = _simplify_to_n(log_pts, MAX_ENVELOPE_POINTS)
            simplified = [(p, 10.0 ** lc) for p, lc in simplified_log]
            species_segs.append({"seg": seg_idx + 1, "points": simplified})
        envelope_data[sp.label] = species_segs

    if not envelope_data:
        return {"status": "ok", "note": "No species above 1e-9 M."}

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    pfx = f"{prefix}_" if prefix else ""
    fname = f"{pfx}concentration_envelope.csv"
    fpath = out / fname

    columns: List[Tuple[str, str, List[Tuple[float, float]]]] = []
    for label, segs in sorted(envelope_data.items()):
        for s in segs:
            seg_tag = f"_seg{s['seg']}" if len(segs) > 1 else ""
            columns.append((
                f"pH_{label}{seg_tag}",
                f"conc_{label}{seg_tag}",
                s["points"],
            ))

    max_rows = max(len(pts) for _, _, pts in columns) if columns else 0
    with open(long_path(fpath), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        header = []
        for col_ph, col_c, _ in columns:
            header.extend([col_ph, col_c])
        writer.writerow(header)
        for row_idx in range(max_rows):
            row = []
            for _, _, pts in columns:
                if row_idx < len(pts):
                    row.append(f"{pts[row_idx][0]:.4f}")
                    row.append(f"{pts[row_idx][1]:.3g}")
                else:
                    row.extend(["", ""])
            writer.writerow(row)

    return {
        "status": "ok",
        "file_path": str(fpath),
        "species_count": len(envelope_data),
        "segment_counts": {lbl: len(segs) for lbl, segs in envelope_data.items()},
        "total_columns": len(columns) * 2,
    }


def read_envelope_csv(file_path: str) -> Dict[str, Any]:
    """Read and return the concentration envelope CSV as text.

    Returns dict with ``status``, ``file_path``, ``content``.
    """
    p = Path(long_path(file_path))
    if not p.exists():
        return {"status": "error", "error": f"File not found: {file_path}"}
    text = p.read_text(encoding="utf-8")
    return {"status": "ok", "file_path": str(Path(file_path)), "content": text}


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  Verdict document (calculation-based, no LLM)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def _stoich_str(stoich: Dict[str, int]) -> str:
    """Compact display string for a stoich dict."""
    if not stoich:
        return "\u2014"
    parts = []
    for k in sorted(stoich, key=lambda k: (0 if k.startswith("M") else 1 if k.startswith("L") else 2, k)):
        parts.append(f"{k}:{stoich[k]:+d}")
    return " ".join(parts)


def write_verdict_document(
    curve: SpeciationCurve,
    output_dir: Path,
    prefix: str = "",
) -> str:
    """Write a calculation-based verdict document (``verdict.md``).

    Contains system metadata, equilibria table, dominant species,
    crossover pH values, and precipitation summary.
    """
    from sweep_pipelines._output_and_plotting.speciation_curves.speciation_output_compressor import (
        summarise_multi_speciation,
    )

    pfx = f"{prefix}_" if prefix else ""
    fpath = output_dir / f"{pfx}verdict.md"
    n = len(curve.pH_values)
    lines: List[str] = []

    lines.append(f"# Speciation Calculation Report: {curve.system_name}")
    lines.append("")
    lines.append("## System Parameters")
    lines.append(f"- Temperature: {curve.temperature} \u00b0C")
    lines.append(f"- Ionic mode: {curve.ionic_mode}")
    lines.append(f"- Target ionic strength: {curve.target_ionic_str:.6g} M")
    _conv_I = [r.calculated_ionic_strength for r in curve.results if r.converged]
    lines.append(
        f"- Calculated ionic strength range: "
        f"{(min(_conv_I) if _conv_I else 0.0):.6g}"
        f" \u2013 {(max(_conv_I) if _conv_I else 0.0):.6g} M"
    )
    lines.append(
        f"- Max inert ions: cation {max((r.inert_cation_conc for r in curve.results), default=0.0):.6g} M, "
        f"anion {max((r.inert_anion_conc for r in curve.results), default=0.0):.6g} M"
    )
    lines.append(f"- pH range: {curve.pH_values[0]:.1f} \u2013 {curve.pH_values[-1]:.1f}")
    lines.append(f"- Points: {n}")
    lines.append(f"- Converged: {curve.n_converged()}/{n}")
    run_params = dict(curve.run_params or {})
    redox_mode = run_params.get("redox_mode")
    if redox_mode:
        lines.append(f"- Redox mode: {redox_mode}")
    if run_params.get("fixed_E_V") is not None:
        lines.append(
            f"- Fixed E_V: {float(run_params['fixed_E_V']):+.12g} V")
    elif run_params.get("E_V_range") is not None:
        E_lo, E_hi = run_params["E_V_range"]
        lines.append(
            f"- E_V range: {float(E_lo):+.12g} \u2013 {float(E_hi):+.12g} V")
    lines.append("")

    total_groups = (
        ("parent_element_totals", "parent element total"),
        ("redox_state_subtotals", "redox-state subtotal"),
        ("component_totals", "component total"),
    )
    compiled_totals = [
        (key, value, description)
        for group_name, description in total_groups
        for key, value in (run_params.get(group_name) or {}).items()
    ]
    if compiled_totals:
        lines.append("## Compiled Analytical Totals")
        lines.append("")
        lines.append("| Constraint | Declared value (mol/L) | Meaning |")
        lines.append("|------------|------------------------|---------|")
        for key, value, description in compiled_totals:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                value_text = f"{float(value):.6g}"
            else:
                value_text = f"`{value}`"
            lines.append(f"| {key} | {value_text} | {description} |")
        lines.append("")

    lines.append("## Components")
    if run_params.get("parent_element_totals"):
        lines.append("")
        lines.append(
            "The metal entries below are conserved physical parent-element "
            "totals; oxidation-state species are partitioned within each "
            "element balance."
        )
    lines.append("")
    lines.append("| ID | Name | Total (mol/L) | Type |")
    lines.append("|-----|------|--------------|------|")
    for mid in sorted(curve.total_metals):
        name = curve.metal_names.get(mid, mid)
        conc = curve.total_metals[mid]
        lines.append(f"| {mid} | {name} | {conc:.2e} | metal |")
    for lid in sorted(curve.total_ligands):
        name = curve.ligand_names.get(lid, lid)
        conc = curve.total_ligands[lid]
        lines.append(f"| {lid} | {name} | {conc:.2e} | ligand |")
    lines.append("")

    is_fe = getattr(curve, "method", "free_energy") == "free_energy"
    if is_fe:
        lines.append("## Free-Energy Species Table")
        lines.append("")
        lines.append("| Label | Phase | Stoich | log \u03b2 | \u03bc\u00b0_free (kJ/mol) | \u03bc\u00b0_canon (kJ/mol) |")
        lines.append("|-------|-------|--------|-------|------------------|-------------------|")
        eq_by_sp = {eq.species_id: eq for eq in curve.equilibria}
        for sp_id, sp in curve.species.items():
            eq = eq_by_sp.get(sp_id)
            logk_str = f"{eq.log_k:+.4f}" if eq else "\u2014"
            st = _stoich_str(sp.stoich)
            mu_f = f"{sp.mu0_free_kJ:+.4f}" if sp.mu0_free_kJ is not None else "\u2014"
            mu_c = f"{sp.mu0_canonical_kJ:+.4f}" if sp.mu0_canonical_kJ is not None else "\u2014"
            lines.append(f"| {sp.label} | {sp.phase} | {st} | {logk_str} | {mu_f} | {mu_c} |")
    else:
        lines.append("## Equilibria Used")
        lines.append("")
        lines.append("| Label | Phase | Stoich | log K (apparent) |")
        lines.append("|-------|-------|--------|------------------|")
        eq_by_sp = {eq.species_id: eq for eq in curve.equilibria}
        for sp_id, sp in curve.species.items():
            eq = eq_by_sp.get(sp_id)
            logk_str = f"{eq.log_k:.4f}" if eq else "\u2014"
            st = _stoich_str(sp.stoich)
            lines.append(f"| {sp.label} | {sp.phase} | {st} | {logk_str} |")
    lines.append("")

    any_solid = any(r.solid_amounts for r in curve.results)
    if any_solid:
        lines.append("## Precipitation")
        lines.append("")
        prev_set: set = set()
        for r in curve.results:
            cur_set = set(r.solid_amounts.keys()) if r.solid_amounts else set()
            if cur_set != prev_set:
                if cur_set:
                    parts = []
                    for sid, amt in r.solid_amounts.items():
                        sp = curve.species.get(sid)
                        lbl = sp.label if sp else sid
                        parts.append(f"{lbl} ({amt:.2e} M)")
                    lines.append(f"- pH {r.pH:.2f}: {', '.join(parts)}")
                elif prev_set:
                    lines.append(f"- pH {r.pH:.2f}: all solids dissolved")
                prev_set = cur_set
        lines.append("")

    lines.append("## Speciation Analysis")
    lines.append("")
    lines.append("```")
    lines.append(summarise_multi_speciation(curve))
    lines.append("```")

    Path(long_path(fpath)).write_text("\n".join(lines), encoding="utf-8")
    return str(fpath)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  Master orchestrator: generate all pH sweep output
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def generate_all_output(
    curve: SpeciationCurve,
    output_dir: Path | str,
    prefix: str = "",
    *,
    input_data: dict | None = None,
    run_params: dict | None = None,
    publication: bool = False,
) -> Dict[str, str]:
    """Generate all pH sweep output: plots, CSVs, envelope, verdict.

    Parameters
    ----------
    curve      : solved SpeciationCurve
    output_dir : target directory
    prefix     : filename prefix
    input_data : input JSON that entered the solver (saved as JSON)
    run_params : solver run parameters (saved as JSON)

    Returns dict mapping output keys to file paths.
    """
    from .pH_sweep_plot import (
        plot_component_phase_balance, plot_fraction, plot_log_conc,
        plot_multi_fraction,
    )
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        raise ImportError("matplotlib required â€“ pip install matplotlib")

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    pfx = f"{prefix}_" if prefix else ""
    paths: Dict[str, str] = {}

    if input_data is None and curve.input_json is not None:
        input_data = curve.input_json
    if run_params is None and curve.run_params is not None:
        run_params = curve.run_params

    # â”€â”€ Plots â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Iterate the *canonical* component IDs (curve.metal_names /
    # ligand_names keys) â€” these are guaranteed to have entries in
    # `frac_metals` / `frac_ligands`.  Filter out any junk element-only
    # symbols that may have leaked into ``total_metals`` from upstream
    # callers (SRD46_numcalculator_api falls back to inserting the raw
    # user key, e.g. "Cu", when no metal_id match is found; those keys
    # have no matching frac series and would render blank PNGs).
    if curve.is_multi:
        canonical_metal_ids  = list(curve.metal_names.keys())
        canonical_ligand_ids = list(curve.ligand_names.keys())

        def _has_fraction_data(cid: str, frac_field: str) -> bool:
            """True if any converged result has at least one species fraction
            recorded for ``cid``.  Skips components with zero total (e.g.
            unused valence states like ``Cu$+1`` when only ``Cu$+2`` was
            specified) â€” plotting those produces blank PNGs."""
            for r in curve.results:
                if not getattr(r, "converged", False):
                    continue
                d = getattr(r, frac_field, {}).get(cid)
                if d:
                    return True
            return False

        canonical_metal_ids  = [m for m in canonical_metal_ids
                                if _has_fraction_data(m, "frac_metals")]
        canonical_ligand_ids = [l for l in canonical_ligand_ids
                                if _has_fraction_data(l, "frac_ligands")]

        def _fname_token(cid: str, fallback_name: str) -> str:
            """Strip the ``$+N`` valence suffix for a clean filename."""
            head = cid.split("$", 1)[0]
            return head if head else (fallback_name or cid)

        for mid in canonical_metal_ids:
            token = _fname_token(mid, curve.metal_names.get(mid, mid))
            fname = f"{pfx}frac_{token}.png"
            fig = plot_multi_fraction(curve, mid, save_path=out / fname,
                                      publication=publication)
            plt.close(fig)
            paths[f"frac_{token}"] = str(out / fname)
            phase_fname = f"{pfx}phase_balance_{token}.png"
            fig = plot_component_phase_balance(
                curve, mid, save_path=out / phase_fname,
                publication=publication)
            plt.close(fig)
            paths[f"phase_balance_{token}"] = str(out / phase_fname)
        for lid in canonical_ligand_ids:
            token = _fname_token(lid, curve.ligand_names.get(lid, lid))
            fname = f"{pfx}frac_{token}.png"
            fig = plot_multi_fraction(curve, lid, save_path=out / fname,
                                      publication=publication)
            plt.close(fig)
            paths[f"frac_{token}"] = str(out / fname)
        if canonical_metal_ids:
            first_token = _fname_token(
                canonical_metal_ids[0],
                curve.metal_names.get(canonical_metal_ids[0], ""),
            )
            paths["frac_metal"] = paths.get(f"frac_{first_token}", "")
        if canonical_ligand_ids:
            first_token = _fname_token(
                canonical_ligand_ids[0],
                curve.ligand_names.get(canonical_ligand_ids[0], ""),
            )
            paths["frac_ligand"] = paths.get(f"frac_{first_token}", "")
    else:
        fig = plot_fraction(curve, "M", save_path=out / f"{pfx}frac_metal.png",
                            publication=publication)
        plt.close(fig)
        paths["frac_metal"] = str(out / f"{pfx}frac_metal.png")

        fig = plot_fraction(curve, "L", save_path=out / f"{pfx}frac_ligand.png",
                            publication=publication)
        plt.close(fig)
        paths["frac_ligand"] = str(out / f"{pfx}frac_ligand.png")

    fig = plot_log_conc(curve, save_path=out / f"{pfx}log_conc.png",
                        publication=publication)
    plt.close(fig)
    paths["log_conc"] = str(out / f"{pfx}log_conc.png")

    # â”€â”€ CSV data export â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    csv_paths = export_csv(curve, out, prefix=prefix)
    paths.update(csv_paths)

    # â”€â”€ Envelope CSV (sampled fractions) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    env_paths = export_envelope_csv(curve, out, prefix=prefix)
    paths.update(env_paths)

    # â”€â”€ Verdict document â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    verdict_path = write_verdict_document(curve, out, prefix=prefix)
    paths["verdict"] = verdict_path

    # â”€â”€ Input card + run parameters â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if input_data is not None:
        fp = out / f"{pfx}input_speciation_card.json"
        Path(long_path(fp)).write_text(
            _json.dumps(input_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        paths["input_speciation_card"] = str(fp)
    if run_params is not None:
        fp = out / f"{pfx}run_params.json"
        Path(long_path(fp)).write_text(
            _json.dumps(run_params, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        paths["run_params_json"] = str(fp)

    return paths

