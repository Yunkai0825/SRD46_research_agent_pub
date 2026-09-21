"""
csv_exporter.py
===============
Export ``SpeciationCurve`` data to CSV files.

Self-contained — usable from pH sweep, Pourbaix speciation extraction,
or any other module that produces a ``SpeciationCurve``.

Outputs
-------
1. ``frac_metal.csv``       — fraction-of-metal(s) vs pH
2. ``frac_ligand.csv``      — fraction-of-ligand(s) vs pH
3. ``log_conc.csv``         — log₁₀[species] vs pH
4. ``concentrations.csv``   — molar concentrations vs pH
5. ``state_metrics.csv``    — ionic strength, convergence, charge balance
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Optional
import sys as _sys
_SP = str(Path(__file__).resolve().parents[2])
if _SP not in _sys.path:
    _sys.path.insert(0, _SP)
from sweep_pipelines._path_utils import long_path, safe_mkdir


def export_speciation_csv(
    curve,
    output_dir: str,
    prefix: str = "",
    *,
    frac_threshold: float = 0.0,
) -> Dict[str, str]:
    """Export a SpeciationCurve to 5 CSV files.

    Parameters
    ----------
    curve : SpeciationCurve
        Solved speciation curve.
    output_dir : str | Path
        Directory to write CSVs into.
    prefix : str
        Filename prefix (e.g. ``"Cu_gly"``).
    frac_threshold : float
        Minimum max-fraction to include a species column (0 = include all).

    Returns
    -------
    Dict mapping file key to file path.
    """
    out = Path(output_dir)
    safe_mkdir(out)
    pfx = f"{prefix}_" if prefix else ""
    paths: Dict[str, str] = {}

    sp_ids = list(curve.species.keys())
    sp_labels = [curve.species[sid].label for sid in sp_ids]

    # ── Helper ────────────────────────────────────────────────
    def _merge_component_fracs(per_component, fallback):
        """Flatten ``{component_id: {species_id: fraction}}`` into a single
        ``{species_id: fraction}`` map covering *every* metal / ligand.

        ``PointResult.frac_M`` / ``frac_L`` are single-component
        convenience copies (first metal / first ligand only); reading them
        directly zeroes out every species belonging to the 2nd..Nth
        component in a multi-metal / multi-ligand system.  The per-component
        ``frac_metals`` / ``frac_ligands`` maps carry the correct
        own-component-normalised fraction for every species, so union them
        here.  For a species shared by more than one component
        (heterobimetallic), keep the larger-magnitude fraction.
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

    def _write(fname, store_fn, key):
        fpath = out / fname
        with open(long_path(fpath), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["pH"] + sp_labels)
            for j, pr in enumerate(curve.results):
                store = store_fn(pr)
                row = [f"{curve.pH_values[j]:.4f}"]
                for sid in sp_ids:
                    row.append(f"{store.get(sid, 0.0):.6e}")
                w.writerow(row)
        paths[key] = str(fpath)

    # ── 4 main CSVs ──────────────────────────────────────────
    _write(f"{pfx}frac_metal.csv",
           lambda pr: _merge_component_fracs(
               getattr(pr, "frac_metals", None), getattr(pr, "frac_M", None)),
           "csv_frac_metal")
    _write(f"{pfx}frac_ligand.csv",
           lambda pr: _merge_component_fracs(
               getattr(pr, "frac_ligands", None), getattr(pr, "frac_L", None)),
           "csv_frac_ligand")
    _write(f"{pfx}log_conc.csv",       lambda pr: getattr(pr, "log_conc", {}), "csv_log_conc")
    _write(f"{pfx}concentrations.csv", lambda pr: getattr(pr, "conc", {}),     "csv_concentrations")

    # ── state_metrics CSV ─────────────────────────────────────
    st_path = out / f"{pfx}state_metrics.csv"
    with open(long_path(st_path), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "pH", "ionic_strength_used", "calculated_ionic_strength",
            "charge_imbalance_eq_per_L", "inert_cation_conc",
            "inert_anion_conc", "converged", "iterations", "residual",
        ])
        for j, pr in enumerate(curve.results):
            w.writerow([
                f"{curve.pH_values[j]:.4f}",
                f"{getattr(pr, 'ionic_strength_used', 0.0):.6e}",
                f"{getattr(pr, 'calculated_ionic_strength', 0.0):.6e}",
                f"{getattr(pr, 'charge_imbalance', 0.0):.6e}",
                f"{getattr(pr, 'inert_cation_conc', 0.0):.6e}",
                f"{getattr(pr, 'inert_anion_conc', 0.0):.6e}",
                int(pr.converged),
                pr.iters,
                f"{pr.residual:.6e}",
            ])
    paths["csv_state_metrics"] = str(st_path)
    return paths


def export_envelope_csv(
    curve,
    output_dir: str,
    prefix: str = "",
    *,
    n_points: int = 29,
    frac_threshold: float = 0.01,
) -> Dict[str, str]:
    """Export sampled fraction envelopes per component.

    One CSV per metal/ligand component, with evenly-spaced pH samples.
    Only species whose max fraction exceeds *frac_threshold* are included.
    """
    out = Path(output_dir)
    safe_mkdir(out)
    pfx = f"{prefix}_" if prefix else ""
    paths: Dict[str, str] = {}

    pH_all = curve.pH_values
    n_total = len(pH_all)
    if n_total == 0:
        return paths
    n_points = max(n_points, 21)
    if n_points >= n_total:
        idx = list(range(n_total))
    else:
        idx = sorted(set(
            int(round(i * (n_total - 1) / (n_points - 1)))
            for i in range(n_points)))

    def _write_component(comp_id):
        sp_list = []
        for sp_id, sp in curve.species.items():
            vals = curve.series_multi(sp_id, comp_id)
            if max(vals) >= frac_threshold:
                sp_list.append((sp_id, sp, vals))
        if not sp_list:
            return
        fpath = out / f"{pfx}envelope_{comp_id}.csv"
        with open(long_path(fpath), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["pH"] + [sp.label for _, sp, _ in sp_list])
            for j in idx:
                row = [f"{pH_all[j]:.4f}"]
                for _, _, vals in sp_list:
                    row.append(f"{vals[j]:.6f}")
                w.writerow(row)
        paths[f"csv_envelope_{comp_id}"] = str(fpath)

    for mid in sorted(getattr(curve, "total_metals", {})):
        _write_component(mid)
    for lid in sorted(getattr(curve, "total_ligands", {})):
        _write_component(lid)
    return paths
