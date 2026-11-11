"""
orphan_fixer.py -- loss-judged resolution of below-resolution fragments (2-D)
============================================================================

Vocabulary
----------
species     one label of the raster (labels < 0 are unresolved cells: they
            belong to no species, are never passable and never absorbed).
component   4-connected set of cells of one species; T1 self-contact
            bridges count as adjacency (exactly the fixed pass's regions).
orphan      component below one coarse cell that does not touch the raster
            rim, lies entirely in the boundary band and has at least one
            cell inside the detection range.
body        every other component of the species, restricted to the range.
range       the cells under consideration: the union of the trust boxes
            around every raw junction-cluster vertex.
mark        ``cell -> effective label`` override.  The raster is never
            edited; the fixed pass extracts topology from the effective
            label map (raster with marks applied), so junctions, chains and
            regions of the fixed solution are consequences of one merged
            grid -- nothing is absorbed, hidden or re-anchored afterwards.

Rules (applied greedily until no orphan is pending)
---------------------------------------------------
R1  bridge(X): a 4-path from orphan X to its own species -- the body, or
    another pending orphan of that species (a chain) -- through cells whose
    effective label is one X touches and that carry no mark.  Admissible
    length: <= trust reach, <= 2x the unobstructed shortest path (no
    detours), <= |X| (a bridge may not outweigh what it rescues).  Every
    reachable target cell contributes its shortest paths; a path that would
    enclose a species X does not touch (R2) is skipped.  The bridge is the
    admissible path with the smallest loss (R3), then the shortest, then
    the fewest conflicts with other candidates' cells / bridges, then a
    target in the body, then the target with the broadest same-species
    contact, then lexicographic.
R2  A rejoin may only enclose (pocket-fill) cells of species X touches; an
    orphan with no admissible non-enclosing path is dissolved.  Pockets
    already closed by the species' own cells (holes of the body or of X)
    are never filled, and pocket-fill is bounded by one coarse cell: a
    larger pocket closed by the rejoin stays a region of its own.
R3  loss(X) = (regions of OTHER species destroyed, split or made
    unrescuable by X's bridge + newly enclosed cells, their cells): a
    component fully taken counts (1, |K|); a component split counts one
    region per extra piece and the cells taken plus every piece but the
    largest; a pending orphan whose own bridge X blocks counts (1, |Y|);
    enclosed cells always count; bridge cells taken from a body are free
    (the size rule already bounds them), from a below-resolution region
    they count.  Kept orphans are components too.  benefit(X) = (1, |X|).
    Comparison is lexicographic.
R4  Each round: score every pending orphan (bridges of all candidates
    first, then losses against them); take the smallest loss (ties: largest
    benefit); rejoin if loss < benefit and the bridge reaches the body (a
    chained candidate waits); an exact loss == benefit has no winner: the
    orphan and every tied competitor it conflicts with dissolve together;
    otherwise dissolve X into the neighbour it shares most edges with
    (ties: most 8-neighbours, then lowest label); an orphan whose species
    has no body in range is kept and flagged.  Mutually waiting orphans:
    the best one goes straight to the body; a chain that can never reach
    its body is dissolved.
R5  Rejoining marks the bridge cells and the newly enclosed cells as the
    species; dissolving marks the orphan cells as the neighbour.

Enclosure is judged on the 8-connected complement: a diagonal contact
between two wall cells does not seal a pocket (regions are 4-connected;
only T1 bridges join diagonal fragments, and those are a below-resolution
waist, not a wall).

Implementation: components live in a component-id raster relabelled once
per round (``scipy.ndimage.label`` per species when SciPy is available,
a stack walk otherwise); orphans are small and handled as cell sets,
bodies are never materialised as Python sets.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import (
    Any, Callable, Dict, FrozenSet, Iterable, List, Optional, Sequence, Set,
    Tuple,
)

import numpy as np

try:  # fast component labelling; the fallback below is exact but slow
    from scipy import ndimage as _ndimage
except ImportError:  # pragma: no cover - optional dependency
    _ndimage = None

Cell = Tuple[int, int]

_MAX_PATHS_PER_TARGET = 16
_MAX_PATHS_TOTAL = 256
_CROSS = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=bool)


def _nb4(c: Cell) -> Tuple[Cell, Cell, Cell, Cell]:
    return ((c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1))


def _nb8(c: Cell) -> Iterable[Cell]:
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            if di or dj:
                yield (c[0] + di, c[1] + dj)


def _label_mask(mask: np.ndarray) -> Tuple[np.ndarray, int]:
    """4-connected components of a boolean mask: (ids 1..n, n)."""
    if _ndimage is not None:
        lab, n = _ndimage.label(mask, structure=_CROSS)
        return lab.astype(np.int64), int(n)
    lab = np.zeros(mask.shape, dtype=np.int64)
    n = 0
    for seed in zip(*np.nonzero(mask)):
        if lab[seed]:
            continue
        n += 1
        stack = [seed]
        lab[seed] = n
        while stack:
            i, j = stack.pop()
            for c in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
                if (0 <= c[0] < mask.shape[0] and 0 <= c[1] < mask.shape[1]
                        and mask[c] and not lab[c]):
                    lab[c] = n
                    stack.append(c)
    return lab, n


def component_raster(
    labels: np.ndarray,
    bridge_pairs: Iterable[Tuple[Cell, Cell]] = (),
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Component ids of a 2-D label raster.

    4-connectivity within each valid label (labels < 0 get id -1); the
    given diagonal pairs are unioned when both cells still share one
    valid label -- the fixed pass's region semantics.  Returns
    ``(comp, comp_label, comp_size)`` with dense ids ``0..n-1``.
    """
    E = np.asarray(labels)
    comp = np.full(E.shape, -1, dtype=np.int64)
    labels_of: List[int] = []
    next_id = 0
    for s in (int(v) for v in np.unique(E) if v >= 0):
        mask = E == s
        lab, n = _label_mask(mask)
        comp[mask] = lab[mask] - 1 + next_id
        labels_of.extend([s] * n)
        next_id += n
    parent = list(range(next_id))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in bridge_pairs:
        a = (int(a[0]), int(a[1]))
        b = (int(b[0]), int(b[1]))
        if E[a] == E[b] and E[a] >= 0:
            ra, rb = find(int(comp[a])), find(int(comp[b]))
            if ra != rb:
                parent[rb] = ra
    roots = np.fromiter((find(i) for i in range(next_id)), dtype=np.int64,
                        count=next_id)
    uniq, dense = np.unique(roots, return_inverse=True)
    valid = comp >= 0
    comp_dense = np.full(E.shape, -1, dtype=np.int64)
    comp_dense[valid] = dense[comp[valid]]
    n = len(uniq)
    size = np.bincount(comp_dense[valid], minlength=n)
    comp_label = np.asarray(labels_of, dtype=np.int64)[uniq] if n else \
        np.zeros(0, dtype=np.int64)
    return comp_dense, comp_label, size


@dataclass
class _SpeciesState:
    comps: List[int]                       # component ids of the species
    orphans: List[FrozenSet[Cell]]         # pending orphans (cell sets)
    body: Set[Cell]                        # body cells inside the range


@dataclass
class OrphanDecision:
    """One resolved orphan.  ``kind`` is ``rejoin`` / ``dissolve`` / ``keep``."""
    kind: str
    label: int
    cells: FrozenSet[Cell]
    bridge: FrozenSet[Cell] = frozenset()
    enclosed: FrozenSet[Cell] = frozenset()
    target_cell: Optional[Cell] = None
    into_label: Optional[int] = None
    loss: Optional[Tuple[int, int]] = None
    why: str = ""

    def to_record(self, catalog: Dict[int, Any]) -> Dict[str, Any]:
        rec: Dict[str, Any] = {
            "kind": self.kind,
            "label": int(self.label),
            "name": str(catalog.get(int(self.label), self.label)),
            "cells": len(self.cells),
            "cell_indices": [list(c) for c in sorted(self.cells)],
        }
        if self.kind == "rejoin":
            rec["bridge_cells"] = [list(c) for c in sorted(self.bridge)]
            rec["enclosed_cells"] = [list(c) for c in sorted(self.enclosed)]
            rec["target_cell"] = (list(self.target_cell)
                                  if self.target_cell is not None else None)
            rec["loss"] = [int(v) for v in self.loss] if self.loss else None
        elif self.kind == "dissolve":
            rec["into_label"] = int(self.into_label)
            rec["into_name"] = str(
                catalog.get(int(self.into_label), self.into_label))
        if self.why:
            rec["why"] = self.why
        return rec


class OrphanFixer:
    """Greedy loss-judged orphan resolution on a 2-D label raster.

    Parameters
    ----------
    labels : 2-D int array (raw raster).
    in_range : cells under consideration (detection range).
    bridge_pairs : T1 same-label diagonal pairs of the raw raster.
    coarse_cells : raster cells per coarse cell; a component with fewer
        cells is below resolution.  Also bounds pocket-fill.
    trust_steps : per-axis reach in cells; ``max`` bounds a bridge.
    band : optional bool mask; an orphan must lie entirely inside it.
    size_rule : enforce ``len(bridge) <= |X|``.
    trace : record every evaluated candidate path (figure exporters);
        off in production.
    """

    def __init__(
        self,
        labels: np.ndarray,
        in_range: Iterable[Cell],
        bridge_pairs: Iterable[Tuple[Cell, Cell]],
        coarse_cells: float,
        trust_steps: Sequence[int],
        band: Optional[np.ndarray] = None,
        size_rule: bool = True,
        trace: bool = False,
    ):
        self.L = np.asarray(labels)
        if self.L.ndim != 2:
            raise ValueError("OrphanFixer is defined for 2-D rasters only")
        self.NI, self.NJ = (int(v) for v in self.L.shape)
        self.E = self.L.astype(np.int64, copy=True)     # effective labels
        self.marked = np.zeros(self.L.shape, dtype=bool)
        self.range_mask = np.zeros(self.L.shape, dtype=bool)
        for c in in_range:
            self.range_mask[int(c[0]), int(c[1])] = True
        self.in_range: Set[Cell] = {
            (int(i), int(j)) for i, j in np.argwhere(self.range_mask)}
        self.bridge_pairs: List[Tuple[Cell, Cell]] = [
            ((int(a[0]), int(a[1])), (int(b[0]), int(b[1])))
            for a, b in bridge_pairs]
        self.bridge_adj: Dict[Cell, List[Cell]] = {}
        for a, b in self.bridge_pairs:
            self.bridge_adj.setdefault(a, []).append(b)
            self.bridge_adj.setdefault(b, []).append(a)
        self.coarse_cells = float(coarse_cells)
        self.pocket_cap = max(1, int(math.ceil(self.coarse_cells)))
        self.piece_budget = 4 * self.pocket_cap + 8
        self.trust = tuple(int(t) for t in trust_steps)
        self.reach = max(self.trust) if self.trust else 1
        self.band = None if band is None else np.asarray(band, dtype=bool)
        self.size_rule = bool(size_rule)
        self.owner: Dict[Cell, int] = {}
        self.kept: Set[FrozenSet[Cell]] = set()
        self.decisions: List[OrphanDecision] = []
        self.rounds: List[List[Dict[str, Any]]] = []
        self.trace_enabled = bool(trace)
        self.trace: List[Dict[str, Any]] = []
        # Component raster and per-component facts (rebuilt each round).
        self.comp = np.full(self.L.shape, -1, dtype=np.int64)
        self.comp_label = np.zeros(0, dtype=np.int64)
        self.comp_size = np.zeros(0, dtype=np.int64)
        self.comp_orphan_shaped = np.zeros(0, dtype=bool)
        self.comp_in_range = np.zeros(0, dtype=bool)
        self.orphan_cells: Dict[int, FrozenSet[Cell]] = {}

    # ------------------------------------------------------------ basics
    def in_grid(self, c: Cell) -> bool:
        return 0 <= c[0] < self.NI and 0 <= c[1] < self.NJ

    def on_rim(self, c: Cell) -> bool:
        return c[0] in (0, self.NI - 1) or c[1] in (0, self.NJ - 1)

    def eff(self, c: Cell) -> int:
        return int(self.E[c[0], c[1]])

    def effective_labels(self) -> np.ndarray:
        return self.E.astype(self.L.dtype, copy=True)

    def _mark(self, cells: Iterable[Cell], label: int) -> None:
        for c in cells:
            self.owner[c] = int(label)
            self.E[c[0], c[1]] = int(label)
            self.marked[c[0], c[1]] = True

    # ------------------------------------------------- component raster
    def _relabel(self) -> None:
        """Component ids of the effective map: 4-connectivity per species,
        T1 bridge pairs (still same-labelled) unioned."""
        comp_dense, comp_label, size = component_raster(self.E, self.bridge_pairs)
        n = len(size)
        valid = comp_dense >= 0
        rim_ids = np.concatenate([
            comp_dense[0, :], comp_dense[-1, :], comp_dense[:, 0], comp_dense[:, -1]])
        rim = np.zeros(n, dtype=bool)
        rim[np.unique(rim_ids[rim_ids >= 0])] = True
        if self.band is not None:
            band_ids = comp_dense[valid & self.band]
            in_band = np.bincount(band_ids, minlength=n) == size
        else:
            in_band = np.ones(n, dtype=bool)
        range_ids = comp_dense[valid & self.range_mask]
        in_range = np.bincount(range_ids, minlength=n) > 0
        self.comp = comp_dense
        self.comp_label = comp_label
        self.comp_size = size
        self.comp_orphan_shaped = (size < self.coarse_cells) & ~rim & in_band
        self.comp_in_range = in_range
        self.orphan_cells = {}
        for cid in np.flatnonzero(self.comp_orphan_shaped & in_range):
            cells = np.argwhere(comp_dense == cid)
            self.orphan_cells[int(cid)] = frozenset(
                (int(i), int(j)) for i, j in cells)

    def comp_of(self, c: Cell) -> int:
        return int(self.comp[c[0], c[1]])

    def is_orphan_comp(self, cid: int) -> bool:
        return bool(self.comp_orphan_shaped[cid])

    def touched_labels(self, comp: Iterable[Cell], s: int) -> Set[int]:
        comp = set(comp)
        labels = {self.eff(n) for c in comp for n in _nb4(c)
                  if self.in_grid(n) and n not in comp}
        return {t for t in labels if t >= 0 and t != s}

    def majority_neighbour(self, comp: Iterable[Cell]) -> int:
        """Neighbour label with the most shared edges; ties -> most
        8-neighbours -> lowest label."""
        comp = set(comp)
        edges: Dict[int, int] = {}
        corners: Dict[int, int] = {}
        for c in comp:
            for n in _nb4(c):
                if self.in_grid(n) and n not in comp and self.eff(n) >= 0:
                    edges[self.eff(n)] = edges.get(self.eff(n), 0) + 1
            for n in _nb8(c):
                if self.in_grid(n) and n not in comp and self.eff(n) >= 0:
                    corners[self.eff(n)] = corners.get(self.eff(n), 0) + 1
        if not edges:
            return int(self.L[min(comp)])
        return min(edges, key=lambda k: (-edges[k], -corners.get(k, 0), k))

    def contact(self, cell: Cell, s: int) -> int:
        return sum(1 for n in _nb4(cell)
                   if self.in_grid(n) and self.eff(n) == s)

    # --------------------------------------------------------- geometry
    def _flood(
        self, seed: Cell, is_wall: Callable[[Cell], bool], cap: int,
    ) -> Tuple[Set[Cell], bool]:
        """8-connected flood over non-wall cells from ``seed``.

        Returns ``(cells, closed)``: ``closed`` is False as soon as the
        flood reaches the raster rim or exceeds ``cap`` cells (the
        pocket is open, or too large to be a pocket-fill)."""
        seen = {seed}
        queue = deque([seed])
        while queue:
            c = queue.popleft()
            if self.on_rim(c) or len(seen) > cap:
                return seen, False
            for n in _nb8(c):
                if self.in_grid(n) and n not in seen and not is_wall(n):
                    seen.add(n)
                    queue.append(n)
        return seen, True

    def newly_enclosed(
        self, s: int, X: FrozenSet[Cell], bridge: Set[Cell], target: Cell,
    ) -> Set[Cell]:
        """Foreign cells sealed in by adding ``bridge`` to species ``s``
        (walls: every effective ``s`` cell plus the bridge), excluding
        pockets the species' own cells already closed."""
        added = set(bridge) | set(X) | {target}

        def wall_new(c: Cell) -> bool:
            return c in bridge or self.eff(c) == s

        def wall_old(c: Cell) -> bool:
            return self.eff(c) == s

        seeds = sorted({n for a in added for n in _nb8(a)
                        if self.in_grid(n) and not wall_new(n)})
        visited: Set[Cell] = set()
        newly: Set[Cell] = set()
        for seed in seeds:
            if seed in visited:
                continue
            pocket, closed = self._flood(seed, wall_new, self.pocket_cap)
            visited |= pocket
            if not closed:
                continue
            _, closed_before = self._flood(seed, wall_old, self.pocket_cap)
            if closed_before:
                continue
            newly |= pocket
        return newly

    def pieces_after_removal(self, cid: int, removed: Set[Cell]) -> List[int]:
        """Sizes of the pieces component ``cid`` falls into once ``removed``
        cells are taken (ascending).  A budgeted walk settles the common
        case (no split, or a small piece cut off); otherwise the exact
        labelling of the component's bounding box decides."""
        total = int(self.comp_size[cid]) - len(removed)
        if total <= 0:
            return []
        members: Set[Cell] = set()
        for r in removed:
            for n in list(_nb4(r)) + list(self.bridge_adj.get(r, ())):
                if (self.in_grid(n) and n not in removed
                        and self.comp_of(n) == cid):
                    members.add(n)
        if len(members) <= 1:
            return [total]

        def inside(c: Cell) -> bool:
            return (self.in_grid(c) and c not in removed
                    and self.comp_of(c) == cid)

        pending = sorted(members)
        sizes: List[int] = []
        while pending:
            seed = pending.pop(0)
            seen = {seed}
            queue = deque([seed])
            over = False
            while queue:
                c = queue.popleft()
                if len(seen) > self.piece_budget:
                    over = True
                    break
                for n in list(_nb4(c)) + list(self.bridge_adj.get(c, ())):
                    if n not in seen and inside(n):
                        seen.add(n)
                        queue.append(n)
            reached_all = not any(m not in seen for m in pending)
            pending = [m for m in pending if m not in seen]
            if over:
                if reached_all:
                    sizes.append(total - sum(sizes))   # one big piece left
                    break
                return self._pieces_exact(cid, removed)
            sizes.append(len(seen))
        return sorted(sizes)

    def _pieces_exact(self, cid: int, removed: Set[Cell]) -> List[int]:
        rows, cols = np.nonzero(self.comp == cid)
        lo_i, hi_i = int(rows.min()), int(rows.max())
        lo_j, hi_j = int(cols.min()), int(cols.max())
        sub = self.comp[lo_i:hi_i + 1, lo_j:hi_j + 1] == cid
        for r in removed:
            if lo_i <= r[0] <= hi_i and lo_j <= r[1] <= hi_j:
                sub[r[0] - lo_i, r[1] - lo_j] = False
        lab, n = _label_mask(sub)
        parent = list(range(n + 1))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for a, b in self.bridge_pairs:
            if (self.comp_of(a) == cid and self.comp_of(b) == cid
                    and a not in removed and b not in removed):
                ra = find(int(lab[a[0] - lo_i, a[1] - lo_j]))
                rb = find(int(lab[b[0] - lo_i, b[1] - lo_j]))
                if ra != rb:
                    parent[rb] = ra
        sizes: Dict[int, int] = {}
        counts = np.bincount(lab[lab > 0], minlength=n + 1)
        for k in range(1, n + 1):
            root = find(k)
            sizes[root] = sizes.get(root, 0) + int(counts[k])
        return sorted(sizes.values())

    def paths_to_targets(
        self, source: Set[Cell], targets: Set[Cell], passable: Set[Cell],
        max_len: int,
    ) -> List[Tuple[List[Cell], Cell]]:
        """For every target cell reachable within ``max_len`` passable
        cells: its shortest 4-paths (cells strictly between source and
        target), capped per target and in total (deterministic order)."""
        dist = {c: 0 for c in source}
        prevs: Dict[Cell, List[Cell]] = {}
        queue = deque(sorted(source))
        hits: Dict[Cell, Tuple[int, List[Cell]]] = {}
        while queue:
            c = queue.popleft()
            for n in _nb4(c):
                if not self.in_grid(n) or n in source:
                    continue
                if n in targets:
                    d, feeders = hits.setdefault(n, (dist[c], []))
                    if dist[c] == d:
                        feeders.append(c)
                    continue
                if n in passable and dist[c] + 1 <= max_len:
                    if n not in dist:
                        dist[n] = dist[c] + 1
                        prevs[n] = [c]
                        queue.append(n)
                    elif dist[n] == dist[c] + 1:
                        prevs[n].append(c)
        paths: List[Tuple[List[Cell], Cell]] = []
        ordered = sorted(hits.items(), key=lambda kv: (kv[1][0], kv[0]))
        for target, (_d, feeders) in ordered:
            found: List[List[Cell]] = []

            def walk(c, acc):
                if len(found) >= _MAX_PATHS_PER_TARGET:
                    return
                if c in source:
                    found.append(list(reversed(acc)))
                    return
                for p in prevs[c]:
                    walk(p, acc + [c])
            for f in sorted(feeders):
                if f in source:
                    found.append([])
                else:
                    walk(f, [])
            paths.extend((p, target) for p in found)
            if len(paths) >= _MAX_PATHS_TOTAL:
                break
        return paths

    def shortest_paths(
        self, source: Set[Cell], targets: Set[Cell], passable: Set[Cell],
        max_len: int,
    ) -> List[Tuple[List[Cell], Cell]]:
        paths = self.paths_to_targets(source, targets, passable, max_len)
        if not paths:
            return []
        best = min(len(p) for p, _ in paths)
        return [(p, t) for p, t in paths if len(p) == best]

    def _range_cells(self, mask: np.ndarray) -> Set[Cell]:
        return {(int(i), int(j))
                for i, j in np.argwhere(mask & self.range_mask)}

    # ------------------------------------------------------- the rules
    def derive(self) -> Dict[int, _SpeciesState]:
        self._relabel()
        info: Dict[int, _SpeciesState] = {}
        orphan_cell_mask = np.zeros(self.L.shape, dtype=bool)
        valid = self.comp >= 0
        orphan_cell_mask[valid] = self.comp_orphan_shaped[self.comp[valid]]
        for s in (int(v) for v in np.unique(self.comp_label)):
            comps = [int(c) for c in np.flatnonzero(self.comp_label == s)]
            orphans = [self.orphan_cells[c] for c in comps
                       if c in self.orphan_cells
                       and self.orphan_cells[c] not in self.kept]
            body = self._range_cells((self.E == s) & ~orphan_cell_mask)
            info[s] = _SpeciesState(comps=comps, orphans=orphans, body=body)
        return info

    def loss(
        self, s: int, X: FrozenSet[Cell], bridge: Set[Cell], newly: Set[Cell],
        info: Dict[int, _SpeciesState], cached: Dict,
    ) -> Tuple[int, int]:
        """(regions, cells) of OTHER species destroyed, split or made
        unrescuable by taking ``bridge`` and ``newly``."""
        taken = bridge | newly
        mine = bridge | set(X)
        by_comp: Dict[int, Set[Cell]] = {}
        for c in taken:
            cid = self.comp_of(c)
            if cid >= 0:
                by_comp.setdefault(cid, set()).add(c)
        lost_regions, lost_cells = 0, 0
        for t, st in info.items():
            if t == s:
                continue
            pending = set(st.orphans) - {X}
            for cid in st.comps:
                removed = by_comp.get(cid, set())
                cells = self.orphan_cells.get(cid)
                blocked = (cells is not None and cells in pending and bool(
                    (cached.get((t, cells)) or set()) & mine))
                size = int(self.comp_size[cid])
                if blocked or (removed and len(removed) == size):
                    lost_regions += 1
                    lost_cells += size
                elif removed:
                    pieces = self.pieces_after_removal(cid, removed)
                    if len(pieces) > 1:
                        lost_regions += len(pieces) - 1
                        lost_cells += len(removed) + sum(pieces[:-1])
                    else:
                        lost_cells += len(removed & newly)
                        if self.is_orphan_comp(cid):
                            lost_cells += len(removed & bridge)
        return lost_regions, lost_cells

    def candidate(
        self, s: int, X: FrozenSet[Cell], info: Dict[int, _SpeciesState],
        cached: Dict, body_only: bool = False,
    ) -> Dict[str, Any]:
        st = info[s]
        others_same = [] if body_only else [Y for Y in st.orphans if Y != X]
        targets = set(st.body) | (
            set().union(*others_same) if others_same else set())
        touched = self.touched_labels(X, s)
        res: Dict[str, Any] = dict(
            bridge=None, target=None, actual=False, loss=None, why="",
            touched=touched, vetoed=0, n_paths=0, newly=set())
        if not targets:
            res["why"] = "no body in range"
            return res
        free = self._range_cells((self.E != s) & (self.E >= 0))
        direct = self.shortest_paths(set(X), targets, free, self.reach)
        if not direct:
            res["why"] = "beyond trust reach"
            return res
        cap = min(self.reach, 2 * len(direct[0][0]))
        if self.size_rule:
            cap = min(cap, len(X))
        passable = self._range_cells(
            np.isin(self.E, sorted(touched)) & ~self.marked) if touched else set()
        paths = self.paths_to_targets(set(X), targets, passable, cap)
        if not paths:
            res["why"] = ("bridge longer than the orphan"
                          if self.size_rule and len(direct[0][0]) > len(X)
                          else "no admissible bridge")
            return res
        others = [(t, Y) for t, inf in info.items() for Y in inf.orphans if Y != X]
        other_cells = set().union(*(set(Y) for _, Y in others)) if others else set()
        other_bridges = (set().union(*(set(b) for b in cached.values() if b))
                         if cached else set())
        body = st.body
        evaluated = []
        vetoed_paths = []
        for path, target in paths:
            bridge = set(path)
            newly = self.newly_enclosed(s, X, bridge, target)
            if any(self.eff(c) not in touched for c in newly):
                res["vetoed"] += 1
                vetoed_paths.append((path, target, newly))
                continue
            loss = self.loss(s, X, bridge, newly, info, cached)
            key = (loss, len(path),
                   len((bridge | {target}) & (other_cells | other_bridges)),
                   target not in body, -self.contact(target, s), sorted(path))
            evaluated.append((key, path, target, bridge, newly, loss))
        res["n_paths"] = len(paths)
        evaluated.sort(key=lambda e: e[0])
        if self.trace_enabled:
            self.trace.append(dict(
                round=len(self.rounds) + 1, label=s, cells=X, body_only=body_only,
                direct_len=len(direct[0][0]), cap=cap,
                evaluated=[dict(path=list(p), target=t, loss=l, newly=sorted(n),
                                in_body=t in body, contact=self.contact(t, s))
                           for _k, p, t, _b, n, l in evaluated],
                vetoed=[dict(path=list(p), target=t, newly=sorted(n))
                        for p, t, n in vetoed_paths]))
        if not evaluated:
            res["why"] = ("every bridge would enclose a species the orphan "
                          "does not touch")
            return res
        _, path, target, bridge, newly, loss = evaluated[0]
        res.update(bridge=bridge, target=target, actual=target in body,
                   loss=loss, newly=newly)
        return res

    def _dissolve(self, s: int, X: FrozenSet[Cell], why: str) -> None:
        target = self.majority_neighbour(X)
        self._mark(X, target)
        self.decisions.append(OrphanDecision(
            kind="dissolve", label=s, cells=X, into_label=target, why=why))

    def _rejoin(self, s: int, X: FrozenSet[Cell], c: Dict[str, Any],
                why: str = "") -> None:
        self._mark(set(c["bridge"]) | set(c["newly"]), s)
        self.decisions.append(OrphanDecision(
            kind="rejoin", label=s, cells=X, bridge=frozenset(c["bridge"]),
            enclosed=frozenset(c["newly"]), target_cell=c["target"],
            loss=tuple(int(v) for v in c["loss"]), why=why))

    def _keep(self, s: int, X: FrozenSet[Cell], why: str) -> None:
        self.kept.add(X)
        self.decisions.append(OrphanDecision(
            kind="keep", label=s, cells=X, why=why))

    def run(self) -> "OrphanFixer":
        while True:
            info = self.derive()
            pending = [(s, X) for s, st in info.items() for X in st.orphans]
            if not pending:
                break
            cached = {key: self.candidate(key[0], key[1], info, {})["bridge"]
                      for key in pending}
            scored = []
            for s, X in pending:
                c = self.candidate(s, X, info, cached)
                loss = c["loss"] if c["loss"] is not None else (10 ** 9, 10 ** 9)
                scored.append((loss, -len(X), s, min(X), X, c))
            scored.sort(key=lambda t: t[:4])
            self.rounds.append([
                dict(label=s, size=len(X), cells=sorted(X),
                     touched=sorted(c["touched"]), loss=c["loss"],
                     bridge=sorted(c["bridge"]) if c["bridge"] else None,
                     target=c["target"], actual=c["actual"],
                     paths=c["n_paths"], vetoed=c["vetoed"], why=c["why"])
                for _, _, s, _, X, c in scored])
            acted = False
            for loss, _, s, _, X, c in scored:
                benefit = (1, len(X))
                if c["bridge"] is not None and loss < benefit:
                    if not c["actual"]:
                        continue          # waits for the orphan it chains through
                    self._rejoin(s, X, c)
                elif c["bridge"] is not None and loss == benefit and c["actual"]:
                    mine = set(c["bridge"]) | set(X)
                    group = [(s, X, c)]
                    for loss2, _, s2, _, X2, c2 in scored:
                        if X2 == X or c2["bridge"] is None or loss2 != (1, len(X2)):
                            continue
                        if (set(c2["bridge"]) | set(X2)) & mine:
                            group.append((s2, X2, c2))
                    for s2, X2, c2 in group:
                        self._dissolve(
                            s2, X2,
                            f"tie: loss {list(c2['loss'])} == benefit, no winner "
                            f"({len(group)} orphans)")
                elif not info[s].body:
                    self._keep(s, X, "no body in range")
                else:
                    why = (c["why"] if c["bridge"] is None
                           else f"loss {list(loss)} >= benefit {list(benefit)}")
                    self._dissolve(s, X, why)
                acted = True
                break
            if acted:
                continue
            # Every admissible candidate waits for another orphan: the best
            # one goes straight to the body; a chain that cannot is dissolved,
            # a species without a body keeps its fragments.
            direct = []
            for s, X in pending:
                c = self.candidate(s, X, info, cached, body_only=True)
                if c["bridge"] is not None and c["loss"] < (1, len(X)):
                    direct.append((c["loss"], -len(X), s, min(X), X, c))
            if direct:
                direct.sort(key=lambda t: t[:4])
                _, _, s, _, X, c = direct[0]
                self._rejoin(s, X, c, why="direct to body (chain deadlock)")
                continue
            _, _, s, _, X, c = scored[0]
            if info[s].body:
                self._dissolve(s, X, "chain never reaches the body")
            else:
                self._keep(s, X, "no body in range")
        return self

    # --------------------------------------------------------- reporting
    def marks(self) -> List[Dict[str, Any]]:
        return [
            {"cell": [int(c[0]), int(c[1])], "raw_label": int(self.L[c]),
             "effective_label": int(t)}
            for c, t in sorted(self.owner.items())
        ]

    def kept_final(self) -> List[FrozenSet[Cell]]:
        """Kept orphans that survived every later mark unchanged."""
        return sorted(
            (X for X in self.kept if not any(c in self.owner for c in X)),
            key=min)


__all__ = ["Cell", "OrphanDecision", "OrphanFixer", "component_raster"]
