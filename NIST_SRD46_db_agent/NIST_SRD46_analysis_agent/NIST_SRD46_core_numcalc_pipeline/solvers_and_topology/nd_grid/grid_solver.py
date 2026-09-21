"""
grid_solver.py
==============
Sole public face of ``solvers_and_topology``.

``NDGridSolver`` is the ONE container that owns the entire grid-level
pipeline.  ``NDGridSolver.solve()`` is the ONE public method.  Sweep
drivers (pH, Pourbaix, titration, …) build their inputs
(axes, ``point_solve_fn``, ``built_system``) and configure ``solve()``
through its keyword flags; they never call internal stages directly.

All stage implementations live in sub-modules of ``nd_grid/`` and
``solvers_and_topology/_output_topology_mapper/``; they are imported
by ``NDGridSolver`` only and are considered package-private.

Public surface
--------------
- ``NDGridSolver``    — the solver class
- ``SolveResult``     — result bundle returned by ``solve()``
- ``ElementResult``   — per-element entry inside ``SolveResult``
- ``SolveFn``         — type alias for the point-solve callable
- ``SeedStrategy``    — type alias for the seed-strategy callable

Usage::

    solver = NDGridSolver(point_solve_fn, built.n_basis,
                          built_system=built)
    result = solver.solve(
        axes=[GridAxis("pH", pH_vals)],
        refine=False,                            # 1-D pH speciation
    )
    grid     = result.grid
    topology = result.per_element["Fe"].topology

For a refined solve, each per-element result also contains the final
effective label raster used to rebuild its topology.  Output layers consume
that exact raster rather than independently reconstructing or falling back to
the coarse field.
"""

from __future__ import annotations

import time
import numpy as np
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .data_types import (
    GridAxis, NDGrid, PointResult,
    BoundaryCellND, RefinedBoundaryPointND, TopologyND,
    cardinal_offsets,
    make_empty_grid,
)
from .settings import (
    POINT_TIMEOUT_S,
    REFINE_FACTOR, REFINE_LAYERS, BISECTION_TOL,
    DEBUG,
)
from .grid_solver_sweep_retry_patching.solver_sweep_and_seed import (
    default_seed, bfs_fill, axis_sweeps,
)
from .grid_solver_sweep_retry_patching.solver_retry_helpers import (
    backscan_retry, interpolation_retry,
)


# Type alias for the solve function supplied by the caller.
# Signature: (coords_dict, x0_guess) -> PointResult
SolveFn = Callable[[Dict[str, float], Optional[np.ndarray]], PointResult]

# Type alias for the seed strategy callable.
# Receives the grid, returns list of multi-indices to try as seeds.
SeedStrategy = Callable[[NDGrid], List[Tuple[int, ...]]]
EffectiveLabelMap = Tuple[
    List[np.ndarray], np.ndarray, Dict[int, str],
]

# Per-layer callback invoked by ``solve()`` after each refinement
# layer.  Signature:
#   cb(coarse_grid, element_name, boundaries,
#      layer_idx, current_refined_pts, x_cache)
# The callback receives only raw refiner state; any presentation
# artefacts (e.g. a fine label raster snapshot) are the caller's
# responsibility to assemble.  Multi-element refinement is solved once:
# callbacks are consequently emitted layer-major, in ``label_elements``
# order within each layer, and elements without coarse facets are omitted.
PerLayerCallback = Callable[
    [NDGrid, str, List[BoundaryCellND],
     int, List[RefinedBoundaryPointND], Dict],
    None,
]


# ==================================================================
#  Result bundles — the ONLY shape ``solve()`` returns
# ==================================================================

@dataclass
class ElementResult:
    """Per-element output bundle produced by ``NDGridSolver.solve``.

    ``topology`` describes the final requested resolution.  After an
    adaptive refinement it is rebuilt from ``effective_label_map`` and is
    never the coarse seed graph with refined points merely spliced into its
    geometry.  ``coarse_topology`` and ``coarse_boundaries`` retain that
    upstream diagnostic state explicitly.  ``boundaries`` remains a
    compatibility alias for the canonical coarse facets used to seed the
    scheduler.

    Fields are ``None`` / empty when the corresponding phase was disabled.
    In a multi-element run, ``x_cache`` is the shared coordinate-to-solution
    cache from the single physical refinement solve; each element therefore
    references the same mapping.
    """

    topology: Optional[TopologyND] = None
    boundaries: List[BoundaryCellND] = field(default_factory=list)
    refined_points: List[RefinedBoundaryPointND] = field(default_factory=list)
    x_cache: Dict = field(default_factory=dict)
    coarse_topology: Optional[TopologyND] = None
    coarse_boundaries: List[BoundaryCellND] = field(default_factory=list)
    effective_label_map: Optional[EffectiveLabelMap] = None


@dataclass
class SolveResult:
    """Result bundle returned by ``NDGridSolver.solve``.

    Attributes
    ----------
    grid
        The coarse, labelled :class:`NDGrid`.
    per_element
        ``{element_name: ElementResult}`` for every element that
        was processed (see ``solve(label_elements=...)``).
    """

    grid: NDGrid
    per_element: Dict[str, ElementResult] = field(default_factory=dict)


class NDGridSolver:
    """The ONE container for the entire grid-level pipeline.

    The solver is agnostic to the physical meaning of the axes.
    The caller supplies a ``point_solve_fn`` that maps coordinate
    values to a :class:`PointResult` and (when labelling / refinement
    are requested) a ``built_system`` describing the chemistry.

    The single public method :meth:`solve` chains every stage
    end-to-end:

        1. Build empty grid.
        2. Seed.
        3. BFS flood-fill.
        4. Axis sweeps (fill dead zones).
        5. Back-scan retry.
        6. Interpolation retry.
        7. Label per principal element.
        8. For each requested element:
           a. Find boundary cells.
           b. (Optional) Multi-layer cascaded boundary refinement
              with optional per-layer callback (raw refiner state).
           c. Preserve the coarse diagnostic topology.
           d. For a refined run, assemble one final effective label field and
              rebuild junctions, boundaries, and regions exclusively from it.

    Output layers reuse ``ElementResult.effective_label_map`` so serialized
    topology, label fields, and plots share one causal source.

    Sweep drivers configure behaviour via :meth:`solve` flags only;
    they never call private stage methods directly.
    """

    def __init__(
        self,
        point_solve_fn: SolveFn,
        n_basis: int,
        built_system: Any = None,
        debug: bool = DEBUG,
    ):
        self.point_solve_fn = point_solve_fn
        self.n_basis = n_basis
        self.built_system = built_system
        self.debug = debug

    # ==================================================================
    #  THE PUBLIC ENTRY POINT — single orchestrator
    # ==================================================================

    def solve(
        self,
        axes: List[GridAxis],
        *,
        # ---- coarse phase (always runs) ----
        seed_strategy: Optional[SeedStrategy] = None,
        point_timeout_s: float = POINT_TIMEOUT_S,
        # ---- label / boundary / refine / topology / fine-map ----
        label_elements: Optional[List[str]] = None,
        refine: bool = True,
        refine_factor: int = REFINE_FACTOR,
        n_layers: int = REFINE_LAYERS,
        bisection_tol: float = BISECTION_TOL,
        per_layer_callback: Optional[PerLayerCallback] = None,
        checkpoint_dir: Optional[str | Path] = None,
        checkpoint_identity: Any = None,
        resume: bool = True,
    ) -> SolveResult:
        """Run the entire N-D grid pipeline end-to-end.

        Parameters
        ----------
        axes
            Ordered list of axes.  The first axis varies slowest
            (outermost index).
        seed_strategy
            ``fn(grid) -> List[Tuple[int,...]]`` returning multi-indices
            to use as initial seed points.  Default: grid center.
        point_timeout_s
            Wall-clock timeout per coarse-grid point.
        label_elements
            Elements to process (labelling + boundary + refine +
            topology + fine map).  ``None`` → use
            ``built_system.principal_elements``.
        refine
            If ``True`` (default), run multi-layer boundary refinement.
            Sweep drivers that only need the coarse grid + topology
            (e.g. 1-D pH speciation) pass ``refine=False``.
        refine_factor
            Sub-grid factor per refinement layer.
        n_layers
            Number of cascaded refinement layers.
        bisection_tol
            Bisection tolerance forwarded to the refiner.
        per_layer_callback
            Optional callable invoked after every refinement layer
            with raw refiner state
            ``(coarse_grid, element_name, boundaries, layer_idx,
              current_refined_pts, x_cache)``.  Use this to render
              per-layer snapshots from the caller's side.
              No-op when ``refine=False``.  See
              :data:`PerLayerCallback`.

        Returns
        -------
        SolveResult
            Bundle with ``grid`` (labelled coarse grid) and
            ``per_element[name]`` populated for every element listed
            in ``label_elements``.
        """
        journal = None
        if checkpoint_dir is not None and resume:
            from .checkpointing import NDGridJournal, grid_run_identity

            identity = grid_run_identity(
                axes=axes,
                n_basis=self.n_basis,
                built_system=self.built_system,
                label_elements=label_elements,
                refine=refine,
                refine_factor=refine_factor,
                n_layers=n_layers,
                bisection_tol=bisection_tol,
                caller_identity=checkpoint_identity,
            )
            journal = NDGridJournal(checkpoint_dir, identity=identity)
            completed = journal.load_final_result()
            if isinstance(completed, SolveResult):
                if self.debug:
                    print(
                        "[grid_solver] Reusing checksummed final grid "
                        f"checkpoint from {checkpoint_dir}",
                        flush=True,
                    )
                return completed

        # ---- Stage 1: coarse N-D solve ----
        grid = self._solve_coarse_grid_nd(
            axes, seed_strategy, point_timeout_s, journal=journal)

        # If no labelling was requested we are done.
        if label_elements is None and self.built_system is None:
            if self.debug:
                print("[grid_solver] No built_system supplied and no "
                      "label_elements given — returning coarse grid only.",
                      flush=True)
            return SolveResult(grid=grid, per_element={})

        if self.built_system is None:
            raise ValueError(
                "NDGridSolver.solve(): label_elements were requested but "
                "built_system was not supplied to the constructor. "
                "Pass built_system=... when instantiating NDGridSolver."
            )

        # ---- Stage 2: label the grid ----
        self._label(grid)

        elems = (
            list(label_elements)
            if label_elements is not None
            else list(self.built_system.principal_elements)
        )

        per_element: Dict[str, ElementResult] = {}

        # ---- Stage 3a: detect canonical transition facets per element ----
        # BoundaryCellND is an oriented FACET record: ``index`` is the
        # lower-index incident cell and ``axis`` points to the other cell.
        # Keep those records unique for topology.  The refiner separately
        # expands every facet to all cells touching any of its vertices.
        boundaries_by_element: Dict[str, List[BoundaryCellND]] = {}
        for elem in elems:
            if self.debug:
                print(f"[grid_solver] --- element {elem} ---", flush=True)
            boundaries_by_element[elem] = self._find_boundaries(grid, elem)

        # ---- Stage 3b: refine the union once for all elements ----
        # Solving separately per element used to overwrite the shared
        # refinement tree and could solve the same physical sub-cell more
        # than once.  A single scheduler now labels every principal element
        # at each solved coordinate and tags its emitted transition points.
        all_boundary_facets = [
            bc
            for elem in elems
            for bc in boundaries_by_element[elem]
        ]

        wrapped_cb: Optional[Callable] = None
        if refine and all_boundary_facets and (
            per_layer_callback is not None or journal is not None
        ):
            _ucb = per_layer_callback

            def wrapped_cb(
                layer_idx, current_pts, xc,
                _g=grid, _elems=tuple(elems),
                _boundaries=boundaries_by_element, _cb=_ucb,
                _debug=self.debug,
            ):
                if journal is not None:
                    journal.save_refinement_layer(
                        layer=layer_idx,
                        coarse_grid=_g,
                        refined_points=current_pts,
                        x_cache=xc or {},
                    )
                for _elem in _elems:
                    # Preserve the former per-element callback contract:
                    # elements with no detected coarse transition facets did
                    # not run a refiner and therefore emitted no layer event.
                    if not _boundaries[_elem]:
                        continue
                    _elem_pts = [
                        rp for rp in current_pts
                        if getattr(rp, "element_name", None) == _elem
                    ]
                    if _cb is not None:
                        try:
                            _cb(
                                _g, _elem, _boundaries[_elem], layer_idx,
                                _elem_pts, xc or {},
                            )
                        except Exception as _exc:
                            if _debug:
                                print(
                                    f"[grid_solver] per_layer_callback "
                                    f"raised at layer {layer_idx} "
                                    f"({_elem}): {_exc}",
                                    flush=True,
                                )

        if refine and all_boundary_facets:
            all_refined_pts, shared_x_cache = self._refine_boundaries(
                grid, all_boundary_facets,
                refine_factor=refine_factor,
                n_layers=n_layers,
                bisection_tol=bisection_tol,
                on_layer_complete=wrapped_cb,
                journal=journal,
            )
        else:
            all_refined_pts, shared_x_cache = [], {}

        # ---- Stage 3c: isolate element geometry and extract topology ----
        # The coarse graph is retained only as an explicitly named
        # diagnostic.  A refined run rebuilds the complete topology from one
        # final effective label field, so upstream facets/junctions cannot be
        # restored after disappearing or pin a downstream feature in place.
        build_final_topology = bool(refine and n_layers >= 1)
        for elem in elems:
            boundaries = boundaries_by_element[elem]
            refined_pts = [
                rp for rp in all_refined_pts
                if getattr(rp, "element_name", None) in (None, elem)
            ]
            coarse_topology = self._extract_topology(
                grid, refined_pts, elem, boundary_cells=boundaries,
            )
            coarse_topology.settings.update({
                "resolution": (
                    "coarse_diagnostic"
                    if build_final_topology else "coarse_final"
                ),
                "is_final": not build_final_topology,
            })

            effective_label_map = None
            topology = coarse_topology
            if build_final_topology:
                # Lazy imports keep the core solver importable without the
                # output stack while still making the public result honest.
                # Failure is intentionally propagated: a refined solve must
                # never fall back silently to its coarse topology.
                from .effective_label_map import (
                    build_and_patch_effective_label_map,
                )
                from .effective_topology import extract_effective_topology

                effective_label_map = build_and_patch_effective_label_map(
                    grid,
                    elem,
                    point_solve_fn=self.point_solve_fn,
                    built_system=self.built_system,
                    x_cache=shared_x_cache,
                    refine_factor=refine_factor ** n_layers,
                    debug=self.debug,
                )
                topology, _, _, _, _ = extract_effective_topology(
                    grid,
                    effective_label_map,
                    debug=self.debug,
                )

            per_element[elem] = ElementResult(
                topology=topology,
                boundaries=boundaries,
                refined_points=refined_pts,
                x_cache=shared_x_cache,
                coarse_topology=coarse_topology,
                coarse_boundaries=boundaries,
                effective_label_map=effective_label_map,
            )

        solve_result = SolveResult(grid=grid, per_element=per_element)
        if journal is not None:
            journal.save_final_result(solve_result)
        return solve_result

    # ==================================================================
    #  Stage 1 — coarse N-D grid solve (private)
    # ==================================================================

    def _solve_coarse_grid_nd(
        self,
        axes: List[GridAxis],
        seed_strategy: Optional[SeedStrategy],
        point_timeout_s: float,
        journal: Any = None,
    ) -> NDGrid:
        """Build and solve an N-D coarse grid (5-phase pipeline).

        Phases (each delegated to ``grid_solver_sweep_retry_patching``):
          1. seed                  — inline (here)
          2. BFS flood-fill        — :func:`bfs_fill`
          3. axis sweeps           — :func:`axis_sweeps`
          4. back-scan retry       — :func:`backscan_retry`
          5. interpolation retry   — :func:`interpolation_retry`
        """
        grid = (
            journal.restore_grid(axes, self.n_basis)
            if journal is not None
            else make_empty_grid(axes, self.n_basis)
        )
        ndim = grid.ndim
        shape = grid.shape
        total = int(np.prod(shape))
        card_off = cardinal_offsets(ndim)

        n_converged = int(np.sum(grid.converged_mask))
        t0 = time.time()

        if self.debug:
            dims_str = " x ".join(f"{ax.name}[{ax.n}]" for ax in axes)
            print(f"[nd_grid] Starting solve: {dims_str} = {total} points",
                  flush=True)

        # ── Phase 1: seed ──
        seed_indices = (
            seed_strategy(grid) if seed_strategy is not None
            else [default_seed(shape)]
        )
        for seed_idx in seed_indices:
            if grid.converged_mask[seed_idx]:
                continue
            coords = grid.coords_at(seed_idx)
            result = self.point_solve_fn(coords, None)
            grid.points[seed_idx] = result
            if journal is not None:
                journal.save_point(seed_idx, result)
            if result.converged:
                grid.converged_mask[seed_idx] = True
                grid.x_cache[seed_idx] = result.x
                n_converged += 1

        if self.debug:
            print(f"[nd_grid] Seed phase: {n_converged} converged",
                  flush=True)
        if journal is not None:
            journal.mark_phase_complete(
                "seed", converged=int(np.sum(grid.converged_mask))
            )

        # ── Phase 2: BFS flood-fill ──
        if journal is None or not journal.phase_complete("bfs"):
            n_converged += bfs_fill(
                grid,
                card_off,
                self.point_solve_fn,
                debug=self.debug,
                on_point_complete=(
                    journal.save_point if journal is not None else None
                ),
            )
            if journal is not None:
                journal.mark_phase_complete(
                    "bfs", converged=int(np.sum(grid.converged_mask))
                )

        if self.debug:
            pct = 100 * n_converged / total if total else 0
            elapsed = time.time() - t0
            print(f"[nd_grid] BFS fill: {n_converged}/{total} "
                  f"({pct:.1f}%) in {elapsed:.1f}s", flush=True)

        # ── Phase 3: axis sweeps ──
        if journal is None or not journal.phase_complete("axis_sweeps"):
            n_converged += axis_sweeps(
                grid,
                self.point_solve_fn,
                debug=self.debug,
                on_point_complete=(
                    journal.save_point if journal is not None else None
                ),
            )
            if journal is not None:
                journal.mark_phase_complete(
                    "axis_sweeps",
                    converged=int(np.sum(grid.converged_mask)),
                )

        # ── Phase 4: back-scan retry ──
        if journal is None or not journal.phase_complete("backscan"):
            n_converged += backscan_retry(
                grid,
                card_off,
                self.point_solve_fn,
                debug=self.debug,
                on_point_complete=(
                    journal.save_point if journal is not None else None
                ),
            )
            if journal is not None:
                journal.mark_phase_complete(
                    "backscan", converged=int(np.sum(grid.converged_mask))
                )

        # ── Phase 5: interpolation retry ──
        if journal is None or not journal.phase_complete("interpolation"):
            n_converged += interpolation_retry(
                grid,
                point_timeout_s,
                self.point_solve_fn,
                debug=self.debug,
                on_point_complete=(
                    journal.save_point if journal is not None else None
                ),
            )
            if journal is not None:
                journal.mark_phase_complete(
                    "interpolation",
                    converged=int(np.sum(grid.converged_mask)),
                )

        if self.debug:
            pct = 100 * n_converged / total if total else 0
            print(f"[nd_grid] Final: {n_converged}/{total} converged "
                  f"({pct:.1f}%)", flush=True)

        if journal is not None:
            journal.save_coarse_grid(grid)

        return grid

# ======================================================================
#  Private stage methods (re-attached onto NDGridSolver below)
# ======================================================================
#
#  Every private stage method delegates to a sub-module implementation
#  file inside ``nd_grid/`` (or the topology dispatcher).  No business
#  logic lives here — ``grid_solver`` is strictly a container.  These
#  methods are leading-underscore: callers MUST go through
#  :meth:`NDGridSolver.solve`.
# ----------------------------------------------------------------------


def _ngs_label(self, grid: NDGrid) -> NDGrid:
    """Label the coarse grid in-place using ``labeler.label_grid_nd``."""
    from .grid_dynamic_refiner.labeler import label_grid_nd
    return label_grid_nd(grid, self.built_system, debug=self.debug)


def _ngs_find_boundaries(
    self, grid: NDGrid, element_name: str,
) -> List[BoundaryCellND]:
    """Detect boundary cells for one element."""
    from .grid_dynamic_refiner.boundary_detector import (
        detect_boundary_cells_nd,
    )
    return detect_boundary_cells_nd(
        grid, element_name=element_name, debug=self.debug,
    )


def _ngs_refine_boundaries(
    self,
    grid: NDGrid,
    boundary_cells: List[BoundaryCellND],
    *,
    refine_factor: int,
    n_layers: int,
    bisection_tol: float,
    on_layer_complete: Optional[Callable] = None,
    journal: Any = None,
) -> Tuple[List[RefinedBoundaryPointND], Dict]:
    """Multi-layer cascaded refinement; always collects ``x_cache``."""
    from .grid_dynamic_refiner.boundary_refiner import (
        refine_boundaries_multilayer_nd,
    )
    result = refine_boundaries_multilayer_nd(
        grid, boundary_cells, self.point_solve_fn, self.built_system,
        refine_factor=refine_factor,
        n_layers=n_layers,
        bisection_tol=bisection_tol,
        debug=self.debug,
        collect_x_cache=True,
        on_layer_complete=on_layer_complete,
        on_node_complete=(
            journal.save_refinement_node if journal is not None else None
        ),
        resume_node_records=(
            journal.load_refinement_nodes()
            if journal is not None else None
        ),
    )
    # When ``collect_x_cache=True`` the refiner returns a 2-tuple.
    if isinstance(result, tuple) and len(result) == 2:
        return result
    return result, {}


def _ngs_extract_topology(
    self,
    grid: NDGrid,
    refined_points: List[RefinedBoundaryPointND],
    element_name: str,
    boundary_cells: Optional[List[BoundaryCellND]] = None,
) -> TopologyND:
    """Run topology extraction against one element's label-map view.

    ``NDGrid.labels`` is a compatibility alias for the first principal
    element.  Reusing it for every requested element corrupts junction and
    region topology in multi-metal systems.  A shallow view keeps the solved
    points and shared refinement tree while rebinding the active labels and
    catalog to *element_name*.  The original canonical facet records are
    passed explicitly so topology never sees the refiner's expanded target
    cell set.
    """
    try:
        from .._output_topology_mapper.topology_dispatcher import (
            extract_topology,
        )
    except ImportError:
        from _output_topology_mapper.topology_dispatcher import (
            extract_topology,
        )
    import copy

    topology_grid = copy.copy(grid)
    if grid.labels_per_element and element_name in grid.labels_per_element:
        topology_grid.labels = grid.labels_per_element[element_name]
    if (grid.label_catalog_per_element
            and element_name in grid.label_catalog_per_element):
        topology_grid.label_catalog = \
            grid.label_catalog_per_element[element_name]

    return extract_topology(
        topology_grid,
        refined_points=refined_points,
        built_system=self.built_system,
        debug=self.debug,
        element_name=element_name,
        boundary_cells=boundary_cells,
    )


# ----------------------------------------------------------------------
#  Attach the private stage methods onto NDGridSolver.
# ----------------------------------------------------------------------
NDGridSolver._label                   = _ngs_label
NDGridSolver._find_boundaries         = _ngs_find_boundaries
NDGridSolver._refine_boundaries       = _ngs_refine_boundaries
NDGridSolver._extract_topology        = _ngs_extract_topology

