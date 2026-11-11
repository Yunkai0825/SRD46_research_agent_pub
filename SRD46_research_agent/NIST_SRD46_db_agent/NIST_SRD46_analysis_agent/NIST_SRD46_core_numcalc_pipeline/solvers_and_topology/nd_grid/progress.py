"""
progress.py
===========
Rolling progress lines for the long, otherwise silent solver phases:
the coarse-grid fill, every refinement layer's node solves and the
per-layer bisection scans.

A :class:`ProgressReporter` counts solved cells against a known (or
growing) total and emits one line every ``every`` cells, or when more
than ``PROGRESS_MAX_SILENCE_S`` seconds have passed since the last
line.  Each line carries the success count, the remaining count, the
percentage done, the elapsed time and an estimate of the remaining time
from the mean pace so far.  The cadence is ``PROGRESS_EVERY_CELLS``
for the coarse grid and layer 1, and grows with the layer index by
``PROGRESS_LAYER_SCALE`` (see :func:`cells_per_report`).

Lines go to a ``sink`` (any ``str -> None`` callable).  A sweep driver
passes its own timestamped logger so the lines also land in the run's
log file; without one, :func:`resolve_sink` falls back to ``print``
when ``debug`` is on and to nothing otherwise.  Reporting never raises
into the solver: a failing sink is disabled after its first error.
"""
from __future__ import annotations

import time
from typing import Callable, Dict, Optional

from .settings import (
    PROGRESS_BISECTION_DIV,
    PROGRESS_EVERY_CELLS,
    PROGRESS_LAYER_SCALE,
    PROGRESS_MAX_SILENCE_S,
)

Sink = Callable[[str], None]


def _print_sink(msg: str) -> None:
    print(msg, flush=True)


def resolve_sink(progress_sink: Optional[Sink], debug: bool) -> Optional[Sink]:
    """Explicit sink wins; otherwise ``print`` under ``debug``; else nothing."""
    if progress_sink is not None:
        return progress_sink
    return _print_sink if debug else None


def cells_per_report(layer: int) -> int:
    """Cells between two progress lines for ``layer``.

    ``layer`` 0 is the coarse grid and reports every
    ``PROGRESS_EVERY_CELLS`` cells; refinement layer ``L >= 1`` reports
    every ``PROGRESS_EVERY_CELLS * L * PROGRESS_LAYER_SCALE`` cells
    (never fewer than ``PROGRESS_EVERY_CELLS``).
    """
    mult = max(1.0, float(max(1, int(layer))) * float(PROGRESS_LAYER_SCALE))
    return max(1, int(round(PROGRESS_EVERY_CELLS * mult)))


def fmt_duration(seconds: Optional[float]) -> str:
    """``h:mm:ss`` for a finite non-negative duration, ``--:--`` otherwise."""
    if seconds is None or not (seconds >= 0.0) or seconds == float("inf"):
        return "--:--"
    total = int(round(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:d}:{minutes:02d}:{secs:02d}"


class ProgressReporter:
    """Count work units of one stage and emit rolling progress lines.

    Parameters
    ----------
    stage
        Short stage name printed in every line (``"coarse grid"``,
        ``"layer 2 nodes"``).
    total
        Known number of units; may be raised later with :meth:`set_total`
        when the work set grows (refinement closure targets).
    sink
        ``str -> None`` callable; ``None`` disables the reporter.
    unit
        Plural noun for the units (``"points"``, ``"cells"``).
    layer
        Cadence selector for :func:`cells_per_report`; ``every``
        overrides it.
    show_ok
        Print the success counter (``converged``) in each line.
    progress_fn
        Optional ``() -> int`` returning the number of units actually
        completed; used by the coarse grid, where retries re-attempt
        the same point and the converged mask is the honest measure.
        Without it the tick count is the progress.
    """

    def __init__(
        self,
        stage: str,
        total: int,
        *,
        sink: Optional[Sink],
        unit: str = "cells",
        layer: int = 0,
        every: Optional[int] = None,
        max_silence_s: Optional[float] = None,
        show_ok: bool = True,
        progress_fn: Optional[Callable[[], int]] = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.stage = stage
        self.total = max(0, int(total))
        self.unit = unit
        self.every = max(1, int(every)) if every else cells_per_report(layer)
        self.max_silence_s = (
            float(PROGRESS_MAX_SILENCE_S) if max_silence_s is None
            else float(max_silence_s)
        )
        self.show_ok = show_ok
        self._progress_fn = progress_fn
        self._sink = sink
        self._clock = clock
        self._t0 = clock()
        self._t_last = self._t0
        self._next_mark = self.every
        self.attempts = 0
        self.ok = 0
        self.lines = 0

    # ------------------------------------------------------------------
    @property
    def enabled(self) -> bool:
        return self._sink is not None

    def set_total(self, total: int) -> None:
        """Raise (or set) the expected number of units."""
        self.total = max(0, int(total))

    def done(self) -> int:
        if self._progress_fn is not None:
            try:
                return int(self._progress_fn())
            except Exception:
                return self.attempts
        return self.attempts

    def tick(self, n: int = 1, ok: int = 0) -> None:
        """Record ``n`` finished units, ``ok`` of them successful."""
        self.attempts += int(n)
        self.ok += int(ok)
        if self._sink is None:
            return
        now = self._clock()
        if (self.attempts >= self._next_mark
                or (now - self._t_last) >= self.max_silence_s):
            while self._next_mark <= self.attempts:
                self._next_mark += self.every
            self.emit(now=now)

    def finish(self) -> None:
        """Emit the closing line (only if any unit was recorded)."""
        if self._sink is None or self.attempts == 0:
            return
        self.emit(final=True)

    # ------------------------------------------------------------------
    def format_line(self, now: Optional[float] = None, final: bool = False) -> str:
        now = self._clock() if now is None else now
        elapsed = max(0.0, now - self._t0)
        done = self.done()
        total = max(self.total, done)
        remaining = max(total - done, 0)
        pct = (100.0 * done / total) if total else 100.0
        pace = (elapsed / done) if done > 0 else None
        singular = self.unit[:-1] if self.unit.endswith("s") else self.unit
        if self._progress_fn is not None:
            # Progress *is* the success count (coarse grid: converged mask).
            parts = [f"{done}/{total} {self.unit} converged ({pct:.1f}%)"]
        else:
            parts = [f"{done}/{total} {self.unit} ({pct:.1f}%)"]
            if self.show_ok:
                parts.append(f"{self.ok} converged")
        if final:
            parts.append(f"{fmt_duration(elapsed)} total")
        else:
            parts.append(f"{remaining} remaining")
            if self._progress_fn is not None:
                parts.append(f"{self.attempts} attempts")
            eta = (pace * remaining) if pace is not None else None
            parts.append(f"{fmt_duration(elapsed)} elapsed, ETA {fmt_duration(eta)}")
        if pace is not None:
            parts.append(f"{pace:.2f} s/{singular}")
        head = f"[progress] {self.stage} done:" if final else f"[progress] {self.stage}:"
        return head + " " + ", ".join(parts)

    def emit(self, now: Optional[float] = None, final: bool = False) -> None:
        if self._sink is None:
            return
        now = self._clock() if now is None else now
        line = self.format_line(now=now, final=final)
        self._t_last = now
        self.lines += 1
        try:
            self._sink(line)
        except Exception:
            # A broken console or log file must never stop the solver.
            self._sink = None


class RefinementProgress:
    """Per-layer reporters for the boundary refiner.

    Node solves of every layer are counted through the refiner's
    ``on_node_complete`` hook (see :meth:`wrap_node_hook`): the layer is
    the length of the node's tree path, the units are the node's fine
    cells (``refine_factor ** ndim`` per node) and a cell counts as
    converged when its point solve converged.  Totals are set by the
    scheduler as it learns them (layer 1 up front, deeper layers as the
    closure grows).  Bisection scans get their own reporter per layer.
    """

    def __init__(self, sink: Optional[Sink], refine_factor: int, ndim: int,
                 n_layers: int):
        self.sink = sink
        self.cells_per_node = int(refine_factor) ** int(ndim)
        self.n_layers = int(n_layers)
        self._nodes: Dict[int, ProgressReporter] = {}

    def log(self, msg: str) -> None:
        if self.sink is None:
            return
        try:
            self.sink(msg)
        except Exception:
            self.sink = None

    def nodes(self, layer: int) -> ProgressReporter:
        rep = self._nodes.get(layer)
        if rep is None:
            rep = ProgressReporter(
                f"layer {layer} nodes", 0, sink=self.sink, unit="cells",
                layer=layer,
            )
            self._nodes[layer] = rep
        return rep

    def set_node_total(self, layer: int, n_nodes: int) -> None:
        self.nodes(layer).set_total(int(n_nodes) * self.cells_per_node)

    def node_done(self, cell_path, sub_points) -> None:
        layer = len(cell_path)
        n_cells = int(getattr(sub_points, "size", 0) or 0)
        n_ok = 0
        for point in getattr(sub_points, "flat", ()):
            if point is not None and getattr(point, "converged", False):
                n_ok += 1
        self.nodes(layer).tick(n_cells, n_ok)

    def finish_nodes(self, layer: int) -> None:
        rep = self._nodes.get(layer)
        if rep is not None:
            rep.finish()

    def wrap_node_hook(self, hook: Optional[Callable]) -> Callable:
        """Return an ``on_node_complete`` that counts, then calls ``hook``."""

        def _on_node_complete(cell_path, node, sub_points, sub_labels):
            try:
                self.node_done(cell_path, sub_points)
            except Exception:
                pass
            if hook is not None:
                hook(cell_path, node, sub_points, sub_labels)

        return _on_node_complete

    def bisection(self, layer: int, note: str = "") -> ProgressReporter:
        """Reporter for one layer's bisection scan.

        A transition costs several point solves (up to ``BISECTION_MAX``),
        so the scan reports ``PROGRESS_BISECTION_DIV`` times as often per
        unit as the layer's node solves.
        """
        stage = f"layer {layer} bisection" + (f" ({note})" if note else "")
        every = max(1, cells_per_report(layer) // max(1, int(PROGRESS_BISECTION_DIV)))
        return ProgressReporter(
            stage, 0, sink=self.sink, unit="transitions", layer=layer,
            every=every, show_ok=False,
        )
