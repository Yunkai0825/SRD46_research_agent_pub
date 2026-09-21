"""
data_types.py
=============
Core data structures for the N-D grid solver and topology pipeline.

Replaces legacy ``pourbaix_core`` data classes with dimension-agnostic
equivalents.  Every downstream module (labeler, detector, refiner,
topology extractors, sweep pipelines) operates on these types.

Mapping from legacy types:
    PourbaixPointResult  ->  PointResult
    PourbaixGridResult   ->  NDGrid
    BoundaryCell         ->  BoundaryCellND
    RefinedBoundaryPoint ->  RefinedBoundaryPointND
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from itertools import product
from typing import (
    Any, Callable, Dict, FrozenSet, List, Optional, Sequence, Tuple, Union,
)


# ---------------------------------------------------------------------------
#  Grid axis
# ---------------------------------------------------------------------------

@dataclass
class GridAxis:
    """One axis of an N-D grid.

    Parameters
    ----------
    name : str
        Machine-readable identifier, e.g. ``"pH"``, ``"E_V"``,
        ``"water_content"``.  Used as key in ``PointResult.coords``.
    values : np.ndarray
        1-D array of monotonically spaced sample coordinates.
    display_label : str
        Human-readable label for plots (e.g. ``"E / V vs SHE"``).
        Defaults to *name* if left empty.
    domain_range : tuple(float, float), optional
        Exact lower and upper fenceposts of the declared sweep domain.
        This normally equals the first and last sample coordinates.  It can
        differ for a cropped, cell-centred refinement raster whose outer
        sample centres lie half a fine cell inside the declared domain.
    """
    name: str
    values: np.ndarray
    display_label: str = ""
    domain_range: Optional[Tuple[float, float]] = None

    def __post_init__(self):
        self.values = np.asarray(self.values, dtype=np.float64)
        if self.values.ndim != 1:
            raise ValueError(f"GridAxis '{self.name}' values must be 1-D")
        if self.domain_range is not None:
            if len(self.domain_range) != 2:
                raise ValueError(
                    f"GridAxis '{self.name}' domain_range must contain "
                    "exactly two values"
                )
            lower, upper = (float(v) for v in self.domain_range)
            if not np.isfinite(lower) or not np.isfinite(upper):
                raise ValueError(
                    f"GridAxis '{self.name}' domain_range must be finite"
                )
            if lower > upper:
                raise ValueError(
                    f"GridAxis '{self.name}' domain_range must be ordered"
                )
            self.domain_range = (lower, upper)
        if not self.display_label:
            self.display_label = self.name

    @property
    def n(self) -> int:
        """Number of sample points along this axis."""
        return len(self.values)

    @property
    def range(self) -> Tuple[float, float]:
        """Exact declared domain, falling back to the sample endpoints."""
        if self.domain_range is not None:
            return self.domain_range
        return self.sample_range

    @property
    def sample_range(self) -> Tuple[float, float]:
        """First and last stored sample-centre coordinates."""
        return (float(self.values[0]), float(self.values[-1]))

    @property
    def spacing(self) -> float:
        """Average spacing between adjacent sample points."""
        if self.n < 2:
            return 0.0
        return (self.values[-1] - self.values[0]) / (self.n - 1)


# ---------------------------------------------------------------------------
#  Point result (unified)
# ---------------------------------------------------------------------------

@dataclass
class PointResult:
    """Solution at one grid point in any N-D sweep.

    Replaces both ``PourbaixPointResult`` (2-D) and ``GibbsPointResult``
    (1-D).  Coordinate values live in *coords* rather than dedicated
    fields; convenience properties (``.pH``, ``.E_V``, ``.pe``) provide
    backward-compatible access.
    """
    coords: Dict[str, float]
    converged: bool
    iterations: int
    residual: float
    x: np.ndarray                                       # (n_basis,) log10 concentrations

    log_conc: Dict[str, float]                          # species_id -> log10(conc)
    conc: Dict[str, float]                              # species_id -> conc (mol/L)
    frac_element: Dict[str, Dict[str, float]]           # element -> {species: fraction}
    frac_ligand: Dict[str, Dict[str, float]]            # ligand  -> {species: fraction}

    active_solid_ids: List[str]
    solid_amounts: Dict[str, float]                     # solid_id -> n_s (mol/L)
    saturation_indices: Dict[str, float]                # solid_id -> SI

    # Solid thermodynamic-reference diagnostics.  Raw saturation indices are
    # retained above for card-equation compatibility; the normalized values
    # below are the comparable quantities per primitive closed-component
    # formula used by the active-set phase selection.
    saturation_reference_scales: Dict[str, float] = field(default_factory=dict)
    saturation_reference_frames: Dict[str, Tuple[int, ...]] = field(default_factory=dict)
    normalized_formation_affinities: Dict[str, float] = field(default_factory=dict)
    formation_driving_energies_kJ_per_mol_reference: Dict[str, float] = field(
        default_factory=dict
    )
    thermodynamic_tie_active_sets: List[List[str]] = field(default_factory=list)
    thermodynamic_ambiguity_active_sets: List[List[str]] = field(default_factory=list)
    phase_search_timed_out: bool = False

    # Labelling — assigned by labeler after grid solve
    label_per_element: Optional[Dict[str, str]] = None  # element -> dominant species id
    label_solids: Optional[FrozenSet[str]] = None       # set of active solid ids
    label: Optional[Tuple] = None                       # composite label

    # ---- convenience accessors ----

    @property
    def pH(self) -> Optional[float]:
        return self.coords.get("pH")

    @property
    def E_V(self) -> Optional[float]:
        return self.coords.get("E_V")

    @property
    def pe(self) -> Optional[float]:
        e = self.coords.get("E_V")
        if e is None:
            return None
        from support_TD_helpers.TD_constants_entry_point import NERNST_FACTOR
        # E = -NERNST_FACTOR * log10(a_e) and pe = -log10(a_e).
        return e / NERNST_FACTOR


# ---------------------------------------------------------------------------
#  N-D grid
# ---------------------------------------------------------------------------

@dataclass
class NDGrid:
    """N-dimensional grid of :class:`PointResult` solutions.

    Replaces ``PourbaixGridResult``.  The grid shape is derived from the
    list of :class:`GridAxis` objects.  All array fields share the same
    leading shape ``(*grid_shape,)``.
    """
    axes: List[GridAxis]
    points: np.ndarray              # (*grid_shape,) dtype=object -> PointResult
    converged_mask: np.ndarray      # (*grid_shape,) dtype=bool
    x_cache: np.ndarray             # (*grid_shape, n_basis) dtype=float64

    # Labelling (set by labeler)
    labels: Optional[np.ndarray] = None                                # (*grid_shape,) int32
    label_catalog: Optional[Dict[int, str]] = None
    labels_per_element: Optional[Dict[str, np.ndarray]] = None
    label_catalog_per_element: Optional[Dict[str, Dict[int, str]]] = None

    # Refinement storage
    #
    # Recursive hybrid-grid representation populated by the refiner.
    # Maps coarse cell multi-index (i,j,...) to a layer-1 node.  Each
    # node is a dict with keys:
    #   - "axes_vals": List[np.ndarray]  — R sub-cell centre positions
    #                                       per axis covering the parent
    #                                       cell, width = parent_size / R.
    #   - "labels":    np.ndarray shape (R,)*ndim — solver-converged
    #                                       label at each sub-cell centre.
    #   - "children":  Dict[Tuple[int,...], node] — sub_idx -> deeper
    #                                       node for further-refined
    #                                       sub-cells.  Empty if leaf.
    #
    # The structure encodes the actual refined grid produced by the
    # refiner with NO interpolation, averaging, or extrapolation.
    refined_cells: Optional[Dict[Tuple[int, ...], dict]] = None

    # ---- shape helpers ----

    @property
    def ndim(self) -> int:
        return len(self.axes)

    @property
    def shape(self) -> Tuple[int, ...]:
        return tuple(ax.n for ax in self.axes)

    @property
    def axis_names(self) -> List[str]:
        return [ax.name for ax in self.axes]

    def axis_index(self, name: str) -> int:
        """Return the position of the axis named *name*."""
        for i, ax in enumerate(self.axes):
            if ax.name == name:
                return i
        raise KeyError(f"No axis named '{name}'")

    def coords_at(self, idx: Tuple[int, ...]) -> Dict[str, float]:
        """Return the physical coordinates at multi-index *idx*."""
        return {ax.name: float(ax.values[idx[i]])
                for i, ax in enumerate(self.axes)}

    # ---- backward compatibility helpers ----

    @property
    def pH_values(self) -> Optional[np.ndarray]:
        """Return pH axis values if present (for 2-D compat)."""
        try:
            return self.axes[self.axis_index("pH")].values
        except KeyError:
            return None

    @property
    def E_values(self) -> Optional[np.ndarray]:
        """Return E_V axis values if present (for 2-D compat)."""
        try:
            return self.axes[self.axis_index("E_V")].values
        except KeyError:
            return None


# ---------------------------------------------------------------------------
#  Boundary cell (N-D)
# ---------------------------------------------------------------------------

@dataclass
class BoundaryCellND:
    """One canonical facet between axis-adjacent cells with different labels.

    ``index`` identifies the lower-index incident cell and ``axis`` identifies
    its +1 neighbour.  The record is deliberately not duplicated: topology
    consumes the unique facet, while refinement expands it to every in-domain
    cell touching any vertex of that facet.  Replaces ``BoundaryCell`` (which
    stored ``i_E, i_pH, direction``).
    """
    index: Tuple[int, ...]      # multi-index of the lower incident cell
    axis: int                   # axis dimension along which the transition occurs
    axis_name: str              # human-readable axis name ("pH", "E_V", ...)
    left_label: int
    right_label: int
    btype: str                  # "aqueous_crossover" | "solid_onset" | "solid_solid"


# ---------------------------------------------------------------------------
#  Refined boundary point (N-D)
# ---------------------------------------------------------------------------

@dataclass
class RefinedBoundaryPointND:
    """A high-resolution boundary point found by bisection in N-D.

    Replaces ``RefinedBoundaryPoint`` (which stored ``pH, E_V``).
    """
    coords: Dict[str, float]   # axis_name -> coordinate value
    left_label: int
    right_label: int
    btype: str
    bisection_axis: int         # which axis dimension was bisected

    # Path from the root coarse cell down through the LayerNode tree
    # to the leaf sub-cell this point sits inside.  Each entry is a
    # multi-index of length ndim:
    #   parent_path[0] = coarse cell index (i,j,...)
    #   parent_path[k] = sub_idx within the layer-k LayerNode for k>=1
    # Empty / None for unattached points.
    parent_path: Optional[Tuple[Tuple[int, ...], ...]] = None

    # Principal element whose per-element label map produced this
    # transition.  Appended after the pre-existing ``parent_path`` field
    # so older positional construction remains compatible.  The field
    # is optional because legacy callers may still create untagged
    # points; the refiner now sets it explicitly.
    element_name: Optional[str] = None


# ---------------------------------------------------------------------------
#  Topology output types (N-D generic)
# ---------------------------------------------------------------------------

@dataclass
class TopologyRegion:
    """One connected region of a single label in the grid.

    Dimensionality: N-D volume (interval in 1-D, area in 2-D, volume
    in 3-D).
    """
    id: int
    label: int
    name: str
    measure: float              # length (1D), area (2D), volume (3D)
    boundary_ids: List[int]     # IDs of boundaries that border this region
    # Topology-fixer verdicts ("below_resolution_orphan_kept": a fragment
    # whose species has no body in range, kept as is;
    # "absorbed_below_resolution_fragments": the region received fixer
    # marks).  Empty for untouched regions and in the raw solution.
    flags: List[str] = field(default_factory=list)


@dataclass
class TopologyBoundary:
    """An (N-1)-dimensional manifold separating two regions.

    The *geometry* field holds a dimension-specific representation:
    - 1D: ``float`` — single coordinate value (crossover point)
    - 2D: ``List[Tuple[float, float]]`` — polyline
    - 3D: mesh vertices + faces (future)
    """
    id: int
    left_label: int
    right_label: int
    btype: str
    geometry: Any               # dimension-specific
    junction_ids: List[int] = field(default_factory=list)
    cell_indices: List[Tuple[int, ...]] = field(default_factory=list)
    # Per-geometry-point RDP anchor eligibility (2-D chains).  False marks
    # vertices demoted by the topology fixer (T1 self-contact waists);
    # empty = legacy, every point eligible.
    anchor_flags: List[bool] = field(default_factory=list)


@dataclass
class TopologyJunction:
    """An (N-2)-dimensional intersection where 3+ boundaries meet.

    - 1D: no junctions
    - 2D: triple point (0-D point)
    - 3D: triple line (1-D curve) or quadruple point
    """
    id: int
    coords: Dict[str, float]   # N-D coordinates
    adjacent_labels: List[int]  # >= 3 labels meeting here
    is_domain_edge: bool = False
    geometry: Any = None        # for 1-D+ junctions in 3-D+
    intrinsic_dim: int = 0      # 0 = point, 1 = curve, …
    cell_indices: List[Tuple[int, ...]] = field(default_factory=list)
    # Exact fence-post vertices belonging to this junction feature.  Kept as
    # a trailing field for backward positional compatibility.  In N-D a
    # clustered junction's centroid is display geometry, not an incidence
    # key; topology builders must match these discrete vertices instead.
    vertex_indices: List[Tuple[int, ...]] = field(default_factory=list)


@dataclass
class TopologyND:
    """Complete N-D topology result.

    Returned by the dimension dispatcher.
    """
    ndim: int
    regions: List[TopologyRegion]
    boundaries: List[TopologyBoundary]
    junctions: List[TopologyJunction]
    label_catalog: Dict[int, str]
    settings: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
#  Compact topology types (dimension-agnostic)
# ---------------------------------------------------------------------------

@dataclass
class CompactFeature:
    """A topological feature at any intrinsic dimension.

    Replaces the legacy dimension-specific types (``TriplePoint``,
    ``TopologyEdge``) with a single unified representation.

    *geometry_raw* holds the zig-zag grid-resolution geometry from the
    upstream topology mapper.  *geometry_compact* holds the simplified
    version produced by the manifold simplifier.

    Geometry conventions by intrinsic dimension:
    - dim 0: ``Dict[str, float]``  — coordinate dict
    - dim 1: ``List[Tuple[float, ...]]``  — polyline in N-D ambient space
    - dim 2: ``(np.ndarray, np.ndarray)``  — (vertices [V×N], triangles [T×3])
    - dim k: ``List[Dict[str, float]]``  — thinned point cloud (fallback)
    """
    id: int
    dim: int                    # intrinsic dimension (0=point, 1=curve, 2=surface)
    labels: List[int]           # adjacent region labels (2 for boundary, 3+ for junction)
    btype: str                  # aqueous_crossover | solid_onset | solid_solid
    geometry_raw: Any           # from extraction (grid resolution)
    geometry_compact: Any = None  # from simplifier
    boundary_ids: List[int] = field(default_factory=list)  # IDs of (dim-1) features
    is_domain_edge: bool = False
    simplification_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CompactRegion:
    """One connected region — replaces ``TopologyFace``."""
    id: int
    label: int
    name: str
    measure: float              # length (1-D), area (2-D), volume (3-D)
    boundary_ids: List[int] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)  # topology-fixer verdicts


@dataclass
class CompactTopologyND:
    """Complete compacted N-D topology.

    Replaces ``TopologyMap`` with a dimension-agnostic representation.
    Features are grouped by intrinsic dimension: ``features[0]`` are
    critical points, ``features[1]`` are curves, ``features[2]`` are
    surfaces, etc.
    """
    ndim: int
    features: Dict[int, List[CompactFeature]]   # dim → features
    regions: List[CompactRegion]
    label_catalog: Dict[int, str]
    axis_names: List[str]
    axis_ranges: Dict[str, Tuple[float, float]]
    settings: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
#  Neighbor offset utilities
# ---------------------------------------------------------------------------

def cardinal_offsets(ndim: int) -> List[Tuple[int, ...]]:
    """Return the 2*ndim cardinal neighbor offsets for an N-D grid.

    Each offset is +-1 along exactly one axis, all others zero.
    Example for ndim=2: [(-1,0), (1,0), (0,-1), (0,1)]
    """
    offsets: List[Tuple[int, ...]] = []
    for d in range(ndim):
        for delta in (-1, +1):
            o = [0] * ndim
            o[d] = delta
            offsets.append(tuple(o))
    return offsets


def all_offsets(ndim: int) -> List[Tuple[int, ...]]:
    """Return all 3^ndim - 1 neighbor offsets (cardinal + diagonal)."""
    return [d for d in product((-1, 0, 1), repeat=ndim)
            if any(x != 0 for x in d)]


def in_bounds(idx: Tuple[int, ...], shape: Tuple[int, ...]) -> bool:
    """Check whether multi-index *idx* is within grid bounds."""
    return all(0 <= idx[d] < shape[d] for d in range(len(shape)))


def add_offset(idx: Tuple[int, ...],
               offset: Tuple[int, ...]) -> Tuple[int, ...]:
    """Element-wise addition of two multi-index tuples."""
    return tuple(i + d for i, d in zip(idx, offset))


# ---------------------------------------------------------------------------
#  Grid factory
# ---------------------------------------------------------------------------

def make_empty_grid(axes: List[GridAxis], n_basis: int) -> NDGrid:
    """Create an empty :class:`NDGrid` ready for solving.

    Allocates ``points``, ``converged_mask``, and ``x_cache`` arrays
    filled with ``None``/``False``/``NaN`` respectively.
    """
    shape = tuple(ax.n for ax in axes)
    points = np.empty(shape, dtype=object)
    converged_mask = np.zeros(shape, dtype=bool)
    x_cache = np.full((*shape, n_basis), np.nan, dtype=np.float64)
    return NDGrid(
        axes=axes,
        points=points,
        converged_mask=converged_mask,
        x_cache=x_cache,
    )
