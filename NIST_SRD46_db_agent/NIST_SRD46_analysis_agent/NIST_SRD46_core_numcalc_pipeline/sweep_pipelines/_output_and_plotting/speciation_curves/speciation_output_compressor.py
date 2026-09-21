"""
speciation_output_compressor.py â€” Text summaries and curve envelopes.
======================================================================

Produces compact text representations of speciation results for
LLM consumption (no matplotlib dependency):

  - ``summarise_speciation``          â€” crossover points, dominant species
  - ``sample_curve_envelope``         â€” sampled fraction table
  - ``summarise_multi_speciation``    â€” multi-component summary
  - ``sample_multi_curve_envelope``   â€” multi-component sampled tables

All functions accept a ``SpeciationCurve`` from ``speciation_dataclasses``.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_core_numcalc_pipeline.thermodynamics_helpers.speciation_dataclasses import (
    SpeciationCurve,
    Species,
)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  Text summary â€” crossover points, dominant species by pH region
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def summarise_speciation(
    curve: SpeciationCurve,
    component: str = "M",
    frac_threshold: float = 0.05,
) -> str:
    """Return a multi-line text summary of the speciation diagram.

    Identifies:
      - Crossover pH values (where two species swap dominance)
      - Dominant species in each pH region
      - Peak fraction and its pH for every species
    """
    kind = "frac_M" if component == "M" else "frac_L"
    pH = curve.pH_values
    n = len(pH)
    if n == 0:
        return "No data."

    # gather fraction arrays
    sp_list: List[Tuple[str, Species, List[float]]] = []
    for sp_id, sp in curve.species.items():
        vals = curve.series(sp_id, kind)
        if max(vals) >= frac_threshold:
            sp_list.append((sp_id, sp, vals))

    lines: List[str] = []
    lines.append(f"=== Speciation summary ({component}-centred) ===")
    lines.append(f"System : {curve.system_name}")
    lines.append(f"[{component}]_total = {curve.total_M if component=='M' else curve.total_L:.2e} M")
    lines.append(f"T = {curve.temperature} \u00b0C,  I = {curve.ionic_str} M")
    lines.append(f"Convergence: {curve.n_converged()}/{n}")
    lines.append("")

    # peak info
    lines.append("Species peaks:")
    for sp_id, sp, vals in sp_list:
        peak = max(vals)
        ipk  = vals.index(peak)
        lines.append(f"  {sp.label:18s}  peak {peak:.1%} at pH {pH[ipk]:.1f}")
    lines.append("")

    # dominant species per pH
    lines.append("Dominant species by pH region:")
    prev_dom = ""
    region_start = pH[0]
    for j in range(n):
        best_id = ""
        best_v  = -1.0
        for sp_id, sp, vals in sp_list:
            if vals[j] > best_v:
                best_v  = vals[j]
                best_id = sp_id
        if best_id != prev_dom:
            if prev_dom:
                sp_obj = curve.species[prev_dom]
                lines.append(
                    f"  pH {region_start:5.1f}\u2013{pH[j]:5.1f}  \u2192  {sp_obj.label}")
            prev_dom = best_id
            region_start = pH[j]
    if prev_dom:
        sp_obj = curve.species[prev_dom]
        lines.append(
            f"  pH {region_start:5.1f}\u2013{pH[-1]:5.1f}  \u2192  {sp_obj.label}")
    lines.append("")

    # crossover points (50 / 50 crossings)
    lines.append("Crossover pH values (where two species are equal):")
    for i_a in range(len(sp_list)):
        for i_b in range(i_a + 1, len(sp_list)):
            _, sp_a, va = sp_list[i_a]
            _, sp_b, vb = sp_list[i_b]
            for j in range(1, n):
                diff_prev = va[j-1] - vb[j-1]
                diff_curr = va[j]   - vb[j]
                if diff_prev * diff_curr < 0:    # sign change
                    # linear interp
                    frac = abs(diff_prev) / (abs(diff_prev) + abs(diff_curr))
                    cross_pH = pH[j-1] + frac * (pH[j] - pH[j-1])
                    cross_fr = va[j-1] + frac * (va[j] - va[j-1])
                    if cross_fr >= frac_threshold:
                        lines.append(
                            f"  {sp_a.label} \u2194 {sp_b.label}  at pH \u2248 {cross_pH:.2f}"
                            f"  (each ~{cross_fr:.0%})")

    return "\n".join(lines)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  Curve envelope sampler â€” text-based "preview" of the diagram
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def sample_curve_envelope(
    curve: SpeciationCurve,
    component: str = "M",
    n_points: int = 25,
    frac_threshold: float = 0.01,
) -> str:
    """Sample speciation curves at *n_points* evenly-spaced pH values
    and return a compact text table.
    """
    if n_points < 21:
        n_points = 25

    kind = "frac_M" if component == "M" else "frac_L"
    pH_all = curve.pH_values
    n_total = len(pH_all)
    if n_total == 0:
        return "No data in curve."

    if n_points >= n_total:
        sample_idx = list(range(n_total))
    else:
        sample_idx = [
            int(round(i * (n_total - 1) / (n_points - 1)))
            for i in range(n_points)
        ]
        seen: set = set()
        deduped: list = []
        for idx in sample_idx:
            if idx not in seen:
                seen.add(idx)
                deduped.append(idx)
        sample_idx = deduped

    sp_list: List[Tuple[str, Species, List[float]]] = []
    for sp_id, sp in curve.species.items():
        vals = curve.series(sp_id, kind)
        if max(vals) >= frac_threshold:
            sp_list.append((sp_id, sp, vals))

    if not sp_list:
        return "No species above threshold."

    col_w = max(10, max(len(sp.label) for _, sp, _ in sp_list) + 1)
    hdr_parts = [f"{'pH':>6s}"]
    for _, sp, _ in sp_list:
        hdr_parts.append(f"{sp.label:>{col_w}s}")
    header = "  ".join(hdr_parts)
    sep = "-" * len(header)

    lines: List[str] = []
    lines.append(f"=== Curve envelope ({component}-centred, {len(sample_idx)} sample points) ===")
    lines.append(f"System: {curve.system_name}")
    lines.append(f"Total pH range: {pH_all[0]:.1f} \u2013 {pH_all[-1]:.1f}")
    lines.append("")
    lines.append(header)
    lines.append(sep)

    for j in sample_idx:
        row_parts = [f"{pH_all[j]:6.2f}"]
        for _, sp, vals in sp_list:
            v = vals[j]
            if v < 0.001:
                row_parts.append(f"{'\u2014':>{col_w}s}")
            else:
                row_parts.append(f"{v:>{col_w}.1%}")
        lines.append("  ".join(row_parts))

    lines.append(sep)
    lines.append("")
    lines.append("Reading guide:")
    lines.append("  \u2022 Each column is one species; values are fraction of total "
                 f"{'metal' if component == 'M' else 'ligand'}.")
    lines.append("  \u2022 '\u2014' means < 0.1 % (negligible).")
    lines.append("  \u2022 Look for the pH where a species rises from \u2014 to a "
                 "significant % \u2192 that's where it starts forming.")
    lines.append("  \u2022 Where two species are both near 50 % \u2192 crossover pH.")
    lines.append("  \u2022 The species with the highest % at a given pH is dominant.")

    return "\n".join(lines)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  Multi-component summary & envelope
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def summarise_multi_speciation(
    curve: SpeciationCurve,
    frac_threshold: float = 0.05,
) -> str:
    """Multi-component speciation summary (one section per metal and ligand)."""
    if not curve.is_multi:
        return (summarise_speciation(curve, "M") + "\n\n"
                + summarise_speciation(curve, "L"))

    parts: List[str] = []
    pH = curve.pH_values
    n = len(pH)

    for mid in sorted(curve.total_metals):
        m_name = curve.metal_names.get(mid, mid)
        C = curve.total_metals[mid]
        parts.append(f"=== {m_name} ({mid}) speciation ===")
        parts.append(f"[{mid}]_total = {C:.2e} M")
        parts.append(f"T = {curve.temperature} \u00b0C,  I = {curve.ionic_str} M")
        parts.append(f"Convergence: {curve.n_converged()}/{n}")
        parts.append("")

        sp_list: List[Tuple[str, Species, List[float]]] = []
        for sp_id, sp in curve.species.items():
            vals = curve.series_multi(sp_id, mid)
            if max(vals) >= frac_threshold:
                sp_list.append((sp_id, sp, vals))

        parts.append("Species peaks:")
        for sp_id, sp, vals in sp_list:
            peak = max(vals)
            ipk = vals.index(peak)
            parts.append(f"  {sp.label:18s}  peak {peak:.1%} at pH {pH[ipk]:.1f}")
        parts.append("")

        parts.append("Dominant species by pH region:")
        prev_dom = ""
        region_start = pH[0]
        for j in range(n):
            best_id, best_v = "", -1.0
            for sp_id, sp, vals in sp_list:
                if vals[j] > best_v:
                    best_v, best_id = vals[j], sp_id
            if best_id != prev_dom:
                if prev_dom:
                    parts.append(
                        f"  pH {region_start:5.1f}\u2013{pH[j]:5.1f}  \u2192  "
                        f"{curve.species[prev_dom].label}")
                prev_dom = best_id
                region_start = pH[j]
        if prev_dom:
            parts.append(
                f"  pH {region_start:5.1f}\u2013{pH[-1]:5.1f}  \u2192  "
                f"{curve.species[prev_dom].label}")
        parts.append("")

        # Crossover points
        parts.append("Crossover pH values:")
        for i_a in range(len(sp_list)):
            for i_b in range(i_a + 1, len(sp_list)):
                _, sp_a, va = sp_list[i_a]
                _, sp_b, vb = sp_list[i_b]
                for j in range(1, n):
                    dp = va[j-1] - vb[j-1]
                    dc = va[j] - vb[j]
                    if dp * dc < 0:
                        frac = abs(dp) / (abs(dp) + abs(dc))
                        cpH = pH[j-1] + frac * (pH[j] - pH[j-1])
                        cfr = va[j-1] + frac * (va[j] - va[j-1])
                        if cfr >= frac_threshold:
                            parts.append(
                                f"  {sp_a.label} \u2194 {sp_b.label}  "
                                f"at pH \u2248 {cpH:.2f}  (each ~{cfr:.0%})")
        parts.append("")

    for lid in sorted(curve.total_ligands):
        l_name = curve.ligand_names.get(lid, lid)
        C = curve.total_ligands[lid]
        parts.append(f"=== {l_name} ({lid}) speciation ===")
        parts.append(f"[{lid}]_total = {C:.2e} M")
        parts.append("")

        sp_list = []
        for sp_id, sp in curve.species.items():
            vals = curve.series_multi(sp_id, lid)
            if max(vals) >= frac_threshold:
                sp_list.append((sp_id, sp, vals))

        parts.append("Species peaks:")
        for sp_id, sp, vals in sp_list:
            peak = max(vals)
            ipk = vals.index(peak)
            parts.append(f"  {sp.label:18s}  peak {peak:.1%} at pH {pH[ipk]:.1f}")
        parts.append("")

        parts.append("Dominant species by pH region:")
        prev_dom = ""
        region_start = pH[0]
        for j in range(n):
            best_id, best_v = "", -1.0
            for sp_id, sp, vals in sp_list:
                if vals[j] > best_v:
                    best_v, best_id = vals[j], sp_id
            if best_id != prev_dom:
                if prev_dom:
                    parts.append(
                        f"  pH {region_start:5.1f}\u2013{pH[j]:5.1f}  \u2192  "
                        f"{curve.species[prev_dom].label}")
                prev_dom = best_id
                region_start = pH[j]
        if prev_dom:
            parts.append(
                f"  pH {region_start:5.1f}\u2013{pH[-1]:5.1f}  \u2192  "
                f"{curve.species[prev_dom].label}")
        parts.append("")

    return "\n".join(parts)


def sample_multi_curve_envelope(
    curve: SpeciationCurve,
    n_points: int = 25,
    frac_threshold: float = 0.01,
) -> str:
    """Sample multi-component speciation curves and return tables per metal/ligand."""
    if not curve.is_multi:
        return (sample_curve_envelope(curve, "M", n_points, frac_threshold)
                + "\n\n"
                + sample_curve_envelope(curve, "L", n_points, frac_threshold))

    pH_all = curve.pH_values
    n_total = len(pH_all)
    if n_total == 0:
        return "No data."
    if n_points < 21:
        n_points = 25

    if n_points >= n_total:
        sample_idx = list(range(n_total))
    else:
        sample_idx = sorted(set(
            int(round(i * (n_total - 1) / (n_points - 1)))
            for i in range(n_points)
        ))

    parts: List[str] = []

    for mid in sorted(curve.total_metals):
        m_name = curve.metal_names.get(mid, mid)
        sp_list: List[Tuple[str, Species, List[float]]] = []
        for sp_id, sp in curve.species.items():
            vals = curve.series_multi(sp_id, mid)
            if max(vals) >= frac_threshold:
                sp_list.append((sp_id, sp, vals))

        if not sp_list:
            continue

        col_w = max(10, max(len(sp.label) for _, sp, _ in sp_list) + 1)
        hdr = "  ".join([f"{'pH':>6s}"] +
                        [f"{sp.label:>{col_w}s}" for _, sp, _ in sp_list])
        sep = "-" * len(hdr)

        parts.append(f"=== {m_name} ({mid}) \u2014 {len(sample_idx)} sample points ===")
        parts.append(hdr)
        parts.append(sep)
        for j in sample_idx:
            row_parts = [f"{pH_all[j]:6.2f}"]
            for _, sp, vals in sp_list:
                v = vals[j]
                row_parts.append(
                    f"{'\u2014':>{col_w}s}" if v < 0.001
                    else f"{v:>{col_w}.1%}")
            parts.append("  ".join(row_parts))
        parts.append(sep)
        parts.append("")

    for lid in sorted(curve.total_ligands):
        l_name = curve.ligand_names.get(lid, lid)
        sp_list = []
        for sp_id, sp in curve.species.items():
            vals = curve.series_multi(sp_id, lid)
            if max(vals) >= frac_threshold:
                sp_list.append((sp_id, sp, vals))

        if not sp_list:
            continue

        col_w = max(10, max(len(sp.label) for _, sp, _ in sp_list) + 1)
        hdr = "  ".join([f"{'pH':>6s}"] +
                        [f"{sp.label:>{col_w}s}" for _, sp, _ in sp_list])
        sep = "-" * len(hdr)

        parts.append(f"=== {l_name} ({lid}) \u2014 {len(sample_idx)} sample points ===")
        parts.append(hdr)
        parts.append(sep)
        for j in sample_idx:
            row_parts = [f"{pH_all[j]:6.2f}"]
            for _, sp, vals in sp_list:
                v = vals[j]
                row_parts.append(
                    f"{'\u2014':>{col_w}s}" if v < 0.001
                    else f"{v:>{col_w}.1%}")
            parts.append("  ".join(row_parts))
        parts.append(sep)
        parts.append("")

    return "\n".join(parts)
