"""
topology_fixer.py -- post-extraction topology fixer (the resolution rulebook)
=============================================================================

Extraction is rule-free: the raw topology reports the label raster
exactly, sub-cell solver artifacts included, and is preserved unchanged
as the audit reference.  This module analyzes that raw result together
with its raster and produces ``FixDecisions``; a second extraction pass
runs on the *effective label map* those decisions define.  The fixed
topology is what compaction, labeling, plotting, the verdict report and
the agent consume: it is the topology of one deep-merged grid, so no
feature is ever absorbed, hidden or re-anchored after extraction.

Stages (2-D only; higher dimensions pass through unfixed):

T1 -- same-label merge.  A vertex whose 2x2 label window repeats one
    label on a diagonal while both off-diagonal cells differ is a
    self-contact: the repeated label pinches through a below-resolution
    waist.  The diagonal cell pair becomes a connectivity *bridge*
    (the fragments are one region) and the vertex is *demoted* (never a
    junction candidate; compaction may not anchor a control point on
    it).  The perfect checkerboard is withheld -- both diagonals would
    claim the same window, so the configuration is symmetric and stays
    unresolved.  T1 runs twice: on the raw raster (the components the
    orphan stage reasons about) and on the effective map (the fixed
    pass's own bridges and demotions).

T2 -- orphan resolution (``orphan_fixer.OrphanFixer``).  Inside the
    detection range -- the union of the trust boxes around every raw
    junction-cluster vertex -- every species is treated alike.  A
    component below one coarse cell that does not touch the rim (the
    domain edge is not evidence) and lies in the boundary band is an
    *orphan*; the rest of its species is its *body*.  An orphan is
    rejoined to its body through a bridge of marked cells (shortest
    admissible 4-path, no longer than the trust reach, twice the
    unobstructed distance or the orphan itself), dissolved into the
    neighbour it shares most edges with, or kept and flagged when its
    species has no body in range.  Which happens is judged by loss:
    the regions of other species a rejoin would destroy, split or make
    unrescuable, against the one region it rescues; orphans are
    processed greedily, smallest loss first.  Decisions are cell
    *marks* (``raw label -> effective label``); the raster is never
    edited.  See the rule book in ``orphan_fixer``.

Fixed pass.  ``extract_topology_nd`` on the effective label map with
these decisions: T1 bridges and demotions of the effective map, region
flags (``below_resolution_orphan_kept`` on kept orphans,
``absorbed_below_resolution_fragments`` on regions that received
marks), no junction clustering -- junctions are where three effective
regions meet, and a junction cluster may legitimately vanish when the
fragments that produced it are merged away (a U whose garbled centre is
filled leaves two-region boundary only).

Trust.  ``TOPO_FIX_TOLERANCE`` per-axis units; default is
``TOPO_FIX_TOLERANCE_FACTOR`` coarse cells (falling back to the
extraction raster's own spacing when no coarse grid is known): labels
were decided at the coarse scale, so structure below it is jitter, not
evidence.  ``TOPO_FIX_TOLERANCE_SCALE`` keeps the trust pinned to the
coarse cell across refinement layers.  The trust sizes the detection
range and bounds bridges; ``TOPO_FIX_ORPHAN_CELL_FACTOR`` coarse cells
(raster-cell count) is the below-resolution threshold.

Band confinement.  The effective raster interleaves genuinely refined
cells (the scheduler solves only the facet-vertex-incident band) with
coarse-inherited copies expanded by ``np.repeat``.  Fix evidence found
in copied territory is not solver data, so every decision is confined
to the label-boundary band: depth 1 is every cell incident to a vertex
of a label-changing facet (the refiner's own rule, corner cells
included), each further ``TOPO_FIX_BAND_DEPTH`` step one 8-connected
ring.  T1 bridges must lie in the band; orphans must lie entirely in
it.  Bridge marks are relabels, not evidence, and may cross copied
territory.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Set, Tuple

import numpy as np

# Settings live at the solvers_and_topology root (same pattern as the
# sibling modules: package-relative import of solver_settings fails
# under pytest, so the root is put on sys.path explicitly).
_SOLVERS_ROOT = str(Path(__file__).resolve().parents[2])
if _SOLVERS_ROOT not in sys.path:
    sys.path.insert(0, _SOLVERS_ROOT)

from solver_settings import (  # noqa: E402
    TOPO_FIX_BAND_DEPTH,
    TOPO_FIX_ENABLE,
    TOPO_FIX_ORPHAN_CELL_FACTOR,
    TOPO_FIX_TOLERANCE,
    TOPO_FIX_TOLERANCE_FACTOR,
    TOPO_FIX_TOLERANCE_SCALE,
)

from .orphan_fixer import OrphanFixer, component_raster

Cell = Tuple[int, ...]
Vertex = Tuple[int, ...]

FLAG_ORPHAN_KEPT = "below_resolution_orphan_kept"
FLAG_ABSORBED = "absorbed_below_resolution_fragments"


# ------------------------------------------------------------------
#  Decisions contract (consumed by the second extraction pass)
# ------------------------------------------------------------------

@dataclass
class FixDecisions:
    """Mechanical instructions for the fixed extraction pass.

    effective_labels : the deep-merged raster the fixed pass extracts
        from (raw raster with ``marks`` applied); None = raw raster.
    marks : cell -> effective label overrides (audit trail; the raster
        itself is never edited).
    demoted_vertices : fence-post vertex indices of the effective map
        that are self-contacts.  The junction finder skips them; the
        boundary builder marks their coordinates as non-anchorable.
    bridges : same-label diagonal cell pairs of the effective map that
        connect region fragments across a self-contact.
    trust_steps : per-axis Chebyshev reach for identical-label-set
        junction clustering in the fixed pass.  Empty (the default and
        what the analysis emits): every junction vertex of the effective
        map is its own junction -- the merge already happened on the
        grid.
    region_flags : minimum cell index of a fixed-pass component -> flag
        list, attached to the matching ``TopologyRegion``.
    report : JSON-ready record stored under settings["topology_fix"].
    """

    demoted_vertices: Set[Vertex] = field(default_factory=set)
    bridges: List[Tuple[Cell, Cell]] = field(default_factory=list)
    trust_steps: Tuple[int, ...] = ()
    region_flags: Dict[Cell, List[str]] = field(default_factory=dict)
    effective_labels: Optional[np.ndarray] = None
    marks: Dict[Cell, int] = field(default_factory=dict)
    report: Dict[str, Any] = field(default_factory=dict)


# ------------------------------------------------------------------
#  Tolerance -> per-axis steps
# ------------------------------------------------------------------

def fix_tolerance(
    axes: Sequence,
    coarse_axes: Optional[Sequence] = None,
) -> Dict[str, float]:
    """Per-axis trust distance in axis units.

    ``TOPO_FIX_TOLERANCE`` overrides everything (exact, never scaled);
    otherwise ``TOPO_FIX_TOLERANCE_FACTOR`` cells per axis.  With
    ``TOPO_FIX_TOLERANCE_SCALE`` (default) the cell is the COARSE one,
    so the trust radius scales with the refined grid at each layer;
    disabled, it is one cell of the current raster.  Either way the
    coarse fallback is the raster's own spacing.
    """
    if TOPO_FIX_TOLERANCE:
        return {str(k): float(v) for k, v in TOPO_FIX_TOLERANCE.items()}
    scale = TOPO_FIX_TOLERANCE_SCALE and coarse_axes is not None
    source = coarse_axes if scale else axes
    factor = float(TOPO_FIX_TOLERANCE_FACTOR)
    tol: Dict[str, float] = {}
    by_name = {str(ax.name): ax for ax in source}
    for ax in axes:
        ref = by_name.get(str(ax.name), ax)
        tol[str(ax.name)] = factor * float(_axis_spacing(ref))
    return tol


def _axis_spacing(axis: Any) -> float:
    values = getattr(axis, "values", None)
    if values is not None and len(values) >= 2:
        return float(np.median(np.diff(np.asarray(values, dtype=float))))
    spacing = getattr(axis, "spacing", None)
    return float(spacing) if spacing else 1.0


def trust_steps_for(
    axes: Sequence,
    tolerance: Dict[str, float],
) -> Tuple[int, ...]:
    """Tolerance -> integer Chebyshev steps per axis (>= 1)."""
    steps: List[int] = []
    for ax in axes:
        spacing = _axis_spacing(ax)
        radius = float(tolerance.get(str(ax.name), spacing))
        steps.append(max(1, int(radius / spacing + 1e-9)))
    return tuple(steps)


def orphan_cell_threshold(
    axes: Sequence,
    coarse_axes: Optional[Sequence],
    tolerance: Dict[str, float],
) -> float:
    """Raster cells below which a component is below resolution.

    ``TOPO_FIX_ORPHAN_CELL_FACTOR`` coarse cells, each spanning
    ``coarse spacing / raster spacing`` raster cells per axis.  Without
    a coarse grid the trust radius is the only resolution statement
    available and stands in for the coarse spacing.
    """
    coarse_by_name = {str(ax.name): ax for ax in (coarse_axes or [])}
    cells = float(TOPO_FIX_ORPHAN_CELL_FACTOR)
    for ax in axes:
        spacing = _axis_spacing(ax)
        coarse = coarse_by_name.get(str(ax.name))
        span = (_axis_spacing(coarse) if coarse is not None
                else float(tolerance.get(str(ax.name), spacing)))
        cells *= max(span / spacing, 1.0)
    return round(cells, 6)


# ------------------------------------------------------------------
#  Boundary band (confines all fix evidence)
# ------------------------------------------------------------------

def boundary_band_2d(labels: np.ndarray, depth: int) -> np.ndarray:
    """Cells the refiner would have solved around every label change.

    Depth 1 is every cell incident to a vertex of a label-changing
    facet (any differing value counts, unresolved ``-1`` included --
    the solver's own uncertainty is boundary evidence): the two cells
    of the facet plus their neighbours along the facet, i.e. the
    refiner's ``get_facet_vertex_incident_indices`` footprint.  Each
    further step dilates by one 8-connected ring.  ``depth <= 0``
    disables confinement and returns an all-true mask.
    """
    if depth <= 0:
        return np.ones(labels.shape, dtype=bool)
    band = np.zeros(labels.shape, dtype=bool)
    n0, n1 = labels.shape
    for i, j in np.argwhere(labels[:-1, :] != labels[1:, :]):
        band[i:i + 2, max(j - 1, 0):min(j + 2, n1)] = True
    for i, j in np.argwhere(labels[:, :-1] != labels[:, 1:]):
        band[max(i - 1, 0):min(i + 2, n0), j:j + 2] = True
    for _ in range(int(depth) - 1):
        band = _dilate_8(band)
    return band


def _dilate_8(mask: np.ndarray) -> np.ndarray:
    grown = mask.copy()
    grown[:-1, :] |= mask[1:, :]
    grown[1:, :] |= mask[:-1, :]
    grown[:, :-1] |= mask[:, 1:]
    grown[:, 1:] |= mask[:, :-1]
    grown[:-1, :-1] |= mask[1:, 1:]
    grown[1:, 1:] |= mask[:-1, :-1]
    grown[:-1, 1:] |= mask[1:, :-1]
    grown[1:, :-1] |= mask[:-1, 1:]
    return grown


# ------------------------------------------------------------------
#  T1: self-contact scan (vectorized over all 2x2 windows)
# ------------------------------------------------------------------

def _self_contact_scan_2d(
    labels: np.ndarray,
) -> Tuple[Set[Vertex], List[Tuple[Cell, Cell]]]:
    """All self-contact vertices and their same-label diagonal bridges.

    Window at cells (i, j)..(i+1, j+1) is interior vertex (i+1, j+1).
    A diagonal is a self-contact when its label repeats, is valid, both
    off-diagonal cells differ from it, and the off-diagonal pair is not
    itself a matching valid pair (perfect checkerboard: symmetric, no
    winner, withheld).  The two diagonal conditions are mutually
    exclusive under the checkerboard guard.
    """
    l00 = labels[:-1, :-1]
    l01 = labels[:-1, 1:]
    l10 = labels[1:, :-1]
    l11 = labels[1:, 1:]
    main_pair = (l00 == l11) & (l00 >= 0)
    anti_pair = (l01 == l10) & (l01 >= 0)
    diag_main = main_pair & (l01 != l00) & (l10 != l00) & ~anti_pair
    diag_anti = anti_pair & (l00 != l01) & (l11 != l01) & ~main_pair

    demoted: Set[Vertex] = set()
    bridges: List[Tuple[Cell, Cell]] = []
    for i, j in np.argwhere(diag_main):
        i, j = int(i), int(j)
        demoted.add((i + 1, j + 1))
        bridges.append(((i, j), (i + 1, j + 1)))
    for i, j in np.argwhere(diag_anti):
        i, j = int(i), int(j)
        demoted.add((i + 1, j + 1))
        bridges.append(((i, j + 1), (i + 1, j)))
    return demoted, bridges


# ------------------------------------------------------------------
#  Components with bridges (the fixed pass's regions, precomputed)
# ------------------------------------------------------------------

def bridge_adjacency(
    bridges: Sequence[Tuple[Cell, Cell]],
) -> Dict[Cell, List[Cell]]:
    """Bridge list -> symmetric cell adjacency for BFS labeling."""
    adj: Dict[Cell, List[Cell]] = defaultdict(list)
    for cell_a, cell_b in bridges:
        adj[cell_a].append(cell_b)
        adj[cell_b].append(cell_a)
    return dict(adj)


def label_components(
    labels: np.ndarray,
    shape: Tuple[int, ...],
    bridges: Optional[Dict[Cell, List[Cell]]] = None,
) -> List[Tuple[int, Set[Cell]]]:
    """Same-label connected components: cardinal adjacency plus bridges.

    Shared by the fixer (analysis) and the region builder (fixed pass)
    so both see identical components.  Bridges are pre-validated
    same-label pairs; no guard is re-applied here.
    """
    bridges = bridges or {}
    visited = np.zeros(shape, dtype=bool)
    components: List[Tuple[int, Set[Cell]]] = []
    ndim = len(shape)
    for seed in np.ndindex(*shape):
        if visited[seed]:
            continue
        lbl = int(labels[seed])
        if lbl < 0:
            visited[seed] = True
            continue
        stack = [seed]
        visited[seed] = True
        cells: Set[Cell] = {seed}
        while stack:
            cur = stack.pop()
            for dim in range(ndim):
                for delta in (-1, 1):
                    nxt = list(cur)
                    nxt[dim] += delta
                    if not (0 <= nxt[dim] < shape[dim]):
                        continue
                    nxt_t = tuple(nxt)
                    if visited[nxt_t] or int(labels[nxt_t]) != lbl:
                        continue
                    visited[nxt_t] = True
                    cells.add(nxt_t)
                    stack.append(nxt_t)
            for nxt_t in bridges.get(cur, ()):
                if visited[nxt_t] or int(labels[nxt_t]) != lbl:
                    continue
                visited[nxt_t] = True
                cells.add(nxt_t)
                stack.append(nxt_t)
        components.append((lbl, cells))
    return components


# ------------------------------------------------------------------
#  Junction clusters (gate for T2)
# ------------------------------------------------------------------

def _within_steps(
    va: Sequence[int], vb: Sequence[int], steps: Sequence[int],
) -> bool:
    return all(abs(int(a) - int(b)) <= int(s)
               for a, b, s in zip(va, vb, steps))


def _junction_vertices(
    raw_junctions: Sequence,
) -> List[Tuple[Vertex, FrozenSet[int]]]:
    """(vertex, label set) for every true meeting point (>= 3 labels).

    Two-label domain-edge junctions are chain bookkeeping, not evidence
    of a multi-phase neighborhood, and are excluded.
    """
    verts: List[Tuple[Vertex, FrozenSet[int]]] = []
    for junction in raw_junctions:
        label_set = frozenset(
            int(v) for v in getattr(junction, "adjacent_labels", ()) or ())
        if len(label_set) < 3:
            continue
        for v_idx in getattr(junction, "vertex_indices", ()) or ():
            verts.append((tuple(int(c) for c in v_idx), label_set))
    return verts


def _cluster_raw_junctions(
    raw_junctions: Sequence,
    trust_steps: Tuple[int, ...],
) -> List[List[Tuple[Vertex, FrozenSet[int]]]]:
    """Union-find over raw junction vertices: within trust and sharing
    >= 2 labels.  Singletons are kept (an isolated waist still gates)."""
    verts = _junction_vertices(raw_junctions)
    parent = list(range(len(verts)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a in range(len(verts)):
        for b in range(a + 1, len(verts)):
            if not _within_steps(verts[a][0], verts[b][0], trust_steps):
                continue
            if len(verts[a][1] & verts[b][1]) < 2:
                continue
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

    groups: Dict[int, List[Tuple[Vertex, FrozenSet[int]]]] = defaultdict(list)
    for idx, item in enumerate(verts):
        groups[find(idx)].append(item)
    return [sorted(group, key=lambda item: item[0])
            for _, group in sorted(
                groups.items(),
                key=lambda kv: min(item[0] for item in kv[1]))]


# ------------------------------------------------------------------
#  Detection range (trust boxes around junction clusters)
# ------------------------------------------------------------------

def detection_range_2d(
    clusters: Sequence[Sequence[Tuple[Vertex, FrozenSet[int]]]],
    trust_steps: Tuple[int, ...],
    shape: Tuple[int, int],
) -> np.ndarray:
    """Cells within the per-axis trust reach of any cluster vertex.

    Vertex ``(vi, vj)`` sits between cells ``vi-1 | vi`` and
    ``vj-1 | vj``; the box spans ``trust`` cells to either side.
    """
    mask = np.zeros(shape, dtype=bool)
    t0, t1 = (int(t) for t in trust_steps)
    for cluster in clusters:
        for (vi, vj), _label_set in cluster:
            mask[max(vi - t0, 0):min(vi + t0, shape[0]),
                 max(vj - t1, 0):min(vj + t1, shape[1])] = True
    return mask


def _tri_vertices_2d(
    labels: np.ndarray,
    demoted: Set[Vertex],
) -> Set[Vertex]:
    """Interior fence-post vertices where >= 3 valid labels meet."""
    l00 = labels[:-1, :-1]
    l01 = labels[:-1, 1:]
    l10 = labels[1:, :-1]
    l11 = labels[1:, 1:]
    stack = np.stack([l00, l01, l10, l11], axis=0)
    valid = stack >= 0
    distinct = np.zeros(l00.shape, dtype=int)
    for k in range(4):
        fresh = valid[k].copy()
        for m in range(k):
            fresh &= ~(valid[m] & (stack[m] == stack[k]))
        distinct += fresh
    verts = {(int(i) + 1, int(j) + 1) for i, j in np.argwhere(distinct >= 3)}
    return verts - set(demoted)


# ------------------------------------------------------------------
#  Analysis entry point
# ------------------------------------------------------------------

@dataclass
class FixerInputs:
    """Everything the orphan stage is run on (also what figure
    exporters replay with a traced ``OrphanFixer``)."""
    tolerance: Dict[str, float]
    trust_steps: Tuple[int, ...]
    orphan_cells: float
    band_depth: int
    band: np.ndarray
    bridges_raw: List[Tuple[Cell, Cell]]
    clusters: List[List[Tuple[Vertex, FrozenSet[int]]]]
    range_mask: np.ndarray

    def make_fixer(self, labels: np.ndarray, trace: bool = False) -> OrphanFixer:
        in_range = [(int(i), int(j)) for i, j in np.argwhere(self.range_mask)]
        return OrphanFixer(
            labels, in_range, self.bridges_raw, self.orphan_cells,
            self.trust_steps, band=self.band, trace=trace,
        )


def fixer_inputs_2d(
    grid: Any,
    raw_topology: Any,
    coarse_axes: Optional[Sequence] = None,
) -> FixerInputs:
    """Trust, band, raw T1 bridges, junction clusters and detection range
    of a raw 2-D topology."""
    labels = np.asarray(grid.labels)
    axes = list(grid.axes)
    shape = (int(labels.shape[0]), int(labels.shape[1]))
    tolerance = fix_tolerance(axes, coarse_axes=coarse_axes)
    trust_steps = trust_steps_for(axes, tolerance)
    orphan_cells = orphan_cell_threshold(axes, coarse_axes, tolerance)
    band_depth = int(TOPO_FIX_BAND_DEPTH or 0)

    # T1 on the raw raster: the components the orphan stage reasons
    # about.  Bridges are band-gated (an invariant at depth >= 1: both
    # cells of a self-contact window are facet-incident).
    band_raw = boundary_band_2d(labels, band_depth)
    _, bridges_all = _self_contact_scan_2d(labels)
    bridges_raw = [(a, b) for a, b in bridges_all
                   if band_raw[a] and band_raw[b]]

    # Detection range: trust boxes around every raw junction-cluster
    # vertex.  Clusters are analysis bookkeeping (which vertices belong
    # to one neighbourhood); they never merge anything themselves.
    clusters = _cluster_raw_junctions(
        getattr(raw_topology, "junctions", ()) or (), trust_steps)
    range_mask = detection_range_2d(clusters, trust_steps, shape)
    return FixerInputs(
        tolerance=tolerance, trust_steps=trust_steps,
        orphan_cells=orphan_cells, band_depth=band_depth, band=band_raw,
        bridges_raw=bridges_raw, clusters=clusters, range_mask=range_mask,
    )


def analyze_fixes_2d(
    grid: Any,
    raw_topology: Any,
    coarse_axes: Optional[Sequence] = None,
    debug: bool = False,
) -> Optional[FixDecisions]:
    """Analyze a raw 2-D topology and emit the decisions for the fixed
    pass.  Returns ``None`` when the fixer is disabled or the grid is
    not 2-D (callers then keep the raw solution as final)."""
    labels = np.asarray(grid.labels)
    if not TOPO_FIX_ENABLE or labels.ndim != 2:
        return None
    shape = (int(labels.shape[0]), int(labels.shape[1]))
    catalog = getattr(raw_topology, "label_catalog", {}) or {}

    inputs = fixer_inputs_2d(grid, raw_topology, coarse_axes)
    tolerance = inputs.tolerance
    trust_steps = inputs.trust_steps
    orphan_cells = inputs.orphan_cells
    band_depth = inputs.band_depth
    band_raw = inputs.band
    bridges_raw = inputs.bridges_raw
    clusters = inputs.clusters
    range_mask = inputs.range_mask

    # T2: orphan resolution -> cell marks -> effective label map.
    fixer = inputs.make_fixer(labels).run()
    marks = dict(fixer.owner)
    effective = fixer.effective_labels()

    # T1 on the effective map: the fixed pass's bridges and demotions.
    band_eff = boundary_band_2d(effective, band_depth)
    _, bridges_eff_all = _self_contact_scan_2d(effective)
    bridges: List[Tuple[Cell, Cell]] = []
    demoted: Set[Vertex] = set()
    for cell_a, cell_b in bridges_eff_all:
        if band_eff[cell_a] and band_eff[cell_b]:
            bridges.append((cell_a, cell_b))
            demoted.add(tuple(max(a, b) for a, b in zip(cell_a, cell_b)))

    # Region flags on the fixed pass's components (effective map, its
    # own T1 bridges), keyed by each component's minimum cell exactly as
    # the region builder discovers them.
    comp, _comp_label, comp_size = component_raster(effective, bridges)
    flat = comp.ravel()
    order = np.flatnonzero(flat >= 0)[::-1]
    first_flat = np.full(len(comp_size), -1, dtype=np.int64)
    first_flat[flat[order]] = order          # reverse walk leaves the minimum
    comp_min: Dict[int, Cell] = {
        cid: (int(idx // shape[1]), int(idx % shape[1]))
        for cid, idx in enumerate(first_flat) if idx >= 0}

    def comp_key(cell: Cell) -> Optional[Cell]:
        cid = int(comp[cell[0], cell[1]])
        return comp_min.get(cid) if cid >= 0 else None

    region_flags: Dict[Cell, List[str]] = {}
    kept = fixer.kept_final()
    kept_cells: Set[Cell] = set().union(*kept) if kept else set()
    for X in kept:
        key = comp_key(min(X))
        if key is not None:
            flags = region_flags.setdefault(key, [])
            if FLAG_ORPHAN_KEPT not in flags:
                flags.append(FLAG_ORPHAN_KEPT)
    touched_keys: Set[Cell] = set()
    for decision in fixer.decisions:
        cells = (decision.cells | decision.bridge if decision.kind == "rejoin"
                 else decision.cells if decision.kind == "dissolve" else ())
        for c in cells:
            key = comp_key(c)
            if key is not None:
                touched_keys.add(key)
    for key in touched_keys:
        flags = region_flags.setdefault(key, [])
        if FLAG_ABSORBED not in flags:
            flags.append(FLAG_ABSORBED)

    # Per-cluster accounting: how many raw junction vertices each
    # neighbourhood had, and how many the effective map still has in
    # the same boxes.  A cluster consumed entirely (0 left) is a valid
    # outcome -- the fragments that produced it were merged away.
    tri_eff = _tri_vertices_2d(effective, demoted)
    cluster_records: List[Dict[str, Any]] = []
    for cluster in clusters:
        box = detection_range_2d([cluster], trust_steps, shape)
        left = sorted(
            v for v in tri_eff
            if any(box[ci, cj]
                   for ci in (v[0] - 1, v[0]) for cj in (v[1] - 1, v[1])
                   if 0 <= ci < shape[0] and 0 <= cj < shape[1]))
        cluster_records.append({
            "raw_vertices": [list(v) for v, _ in cluster],
            "labels": sorted({int(l) for _, ls in cluster for l in ls}),
            "cells_in_range": int(box.sum()),
            "fixed_vertices": [list(v) for v in left],
            "consumed": not left,
        })

    decisions = [d.to_record(catalog) for d in fixer.decisions]
    n_kind = {k: sum(1 for d in fixer.decisions if d.kind == k)
              for k in ("rejoin", "dissolve", "keep")}
    report: Dict[str, Any] = {
        "applied": True,
        "tolerance": {k: float(v) for k, v in tolerance.items()},
        "tolerance_factor": float(TOPO_FIX_TOLERANCE_FACTOR),
        "tolerance_scale_with_refine": bool(TOPO_FIX_TOLERANCE_SCALE),
        "trust_steps": [int(s) for s in trust_steps],
        "orphan_cell_threshold": float(orphan_cells),
        "band_depth": band_depth,
        "band_cells": int(band_raw.sum()),
        "range_cells": int(range_mask.sum()),
        "junction_vertices": sum(len(c) for c in clusters),
        "junction_clusters": len(clusters),
        "clusters": cluster_records,
        "t1_bridges_raw": len(bridges_raw),
        "t1_bridges": len(bridges),
        "self_contact_vertices": len(demoted),
        "orphans_rejoined": n_kind["rejoin"],
        "orphans_dissolved": n_kind["dissolve"],
        "orphans_kept": n_kind["keep"],
        "decisions": decisions,
        "marks": fixer.marks(),
        "rounds": len(fixer.rounds),
        "kept_cells": len(kept_cells),
    }
    if debug:
        print(
            "[topology_fixer] "
            f"{len(clusters)} clusters, {int(range_mask.sum())} cells in "
            f"range, {n_kind['rejoin']} rejoined / {n_kind['dissolve']} "
            f"dissolved / {n_kind['keep']} kept, {len(marks)} marks, "
            f"{len(bridges)} effective-map T1 bridges",
            flush=True,
        )
    return FixDecisions(
        demoted_vertices=demoted,
        bridges=bridges,
        trust_steps=(),
        region_flags=region_flags,
        effective_labels=effective,
        marks=marks,
        report=report,
    )
