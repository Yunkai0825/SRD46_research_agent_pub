"""Complete neighbour guesses, separate from target conditions and results."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import inspect

import numpy as np


WARM_START_POLICY = "full-phase-state/v2-separate-donor-budget"


@dataclass
class WarmStart:
    x: np.ndarray
    active_solid_ids: tuple[str, ...] = ()
    solid_amounts: dict[str, float] = field(default_factory=dict)
    released_totals: dict[int, float] = field(default_factory=dict)
    system_key: str = ""
    coords: dict[str, float] = field(default_factory=dict)

    def copy(self):
        return deepcopy(self)

    def __array__(self, dtype=None, copy=None):
        return np.array(self.x, dtype=dtype, copy=True)


def seed_from_point(point):
    """Copy a successful donor; failed trial concentrations are never seeds."""
    if (point is None or not getattr(point, "converged", False)
            or getattr(point, "phase_search_timed_out", False)
            or getattr(point, "_timed_out", False)):
        return None
    x = np.asarray(point.x, dtype=float)
    if not np.all(np.isfinite(x)):
        return None
    return WarmStart(
        x.copy(), tuple(getattr(point, "active_solid_ids", ()) or ()),
        dict(getattr(point, "solid_amounts", {}) or {}),
        dict(getattr(point, "_released_totals", {}) or {}),
        getattr(point, "warm_start_key", ""),
        dict(getattr(point, "coords", {}) or {}),
    )


def _accepts_warm_start(fn):
    try:
        return "warm_start" in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False


def solve_seeded(fn, coords, seed):
    """Keep the existing two-argument callback contract for vector-only users."""
    if isinstance(seed, WarmStart):
        donor = seed.copy()
        # Old numeric caches have no phase/model metadata. Preserve their
        # vector-only meaning instead of passing an invalid complete donor.
        has_state = bool(donor.system_key or donor.active_solid_ids
                         or donor.released_totals)
        if has_state and _accepts_warm_start(fn):
            return fn(coords, donor.x.copy(), warm_start=donor)
        return fn(coords, donor.x.copy())
    return fn(coords, None if seed is None else np.asarray(seed).copy())


def blend_seeds(seeds, weights):
    """Blend complete guesses only when they describe the same phase set."""
    vector = sum(w * np.asarray(s) for s, w in zip(seeds, weights))
    if not seeds or not all(isinstance(s, WarmStart) for s in seeds):
        return vector
    first = seeds[0]
    phases = set(first.active_solid_ids)
    if any(s.system_key != first.system_key
           or set(s.active_solid_ids) != phases
           or set(s.released_totals) != set(first.released_totals)
           for s in seeds):
        return vector
    result = first.copy()
    result.x = vector
    result.solid_amounts = {
        sid: sum(w * s.solid_amounts[sid] for s, w in zip(seeds, weights))
        for sid in phases
    }
    result.released_totals = {
        key: sum(w * s.released_totals[key] for s, w in zip(seeds, weights))
        for key in first.released_totals
    }
    result.coords = {}  # a synthetic guess has no single donor coordinate
    return result


class WarmStartCache(dict):
    """Public entries remain ndarrays; full donor states have a separate map."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.points = {}


def remember_point(cache, coords, point):
    if cache is None or seed_from_point(point) is None:
        return
    key = tuple(sorted(coords.items()))
    cache[key] = point.x.copy()
    if isinstance(cache, WarmStartCache):
        cache.points[key] = deepcopy(point)


def cached_seed(cache, key):
    if cache is None:
        return None
    if isinstance(cache, WarmStartCache):
        seed = seed_from_point(cache.points.get(key))
        if seed is not None:
            return seed
    x = cache.get(key)
    return None if x is None else x.copy()
