"""Durable journal for long-running N-D grid solves.

Every completed coarse point is committed independently.  A restart rebuilds
the exact :class:`NDGrid` from those records and solves only points that were
not durably committed.  Completed coarse grids and final ``SolveResult``
objects receive additional snapshots for fast restart.
"""

from __future__ import annotations

import hashlib
import json
import pickle
from pathlib import Path
from typing import Any, Iterable, Optional, Tuple

import numpy as np

from NIST_SRD46_db_agent.general_db_query_engine.general_checkpointing import (
    DurableCheckpointStore,
    identity_sha256,
)

from .data_types import GridAxis, NDGrid, PointResult, make_empty_grid


def _pickle_identity(value: Any) -> str:
    try:
        payload = pickle.dumps(value, protocol=5)
    except Exception:
        payload = repr(value).encode("utf-8", errors="replace")
    return hashlib.sha256(payload).hexdigest()


def grid_run_identity(
    *,
    axes: Iterable[GridAxis],
    n_basis: int,
    built_system: Any,
    label_elements: Optional[Iterable[str]],
    refine: bool,
    refine_factor: Optional[int],
    n_layers: int,
    bisection_tol: float,
    caller_identity: Any = None,
) -> dict[str, Any]:
    """Return the exact identity contract for one numerical grid."""

    return {
        "contract": "nd-grid-solve/v1",
        "axes": [
            {
                "name": axis.name,
                "values": [float(value) for value in axis.values],
                "display_label": axis.display_label,
                "domain_range": axis.domain_range,
            }
            for axis in axes
        ],
        "n_basis": int(n_basis),
        "built_system_sha256": _pickle_identity(built_system),
        "label_elements": (
            [str(value) for value in label_elements]
            if label_elements is not None else None
        ),
        "refine": bool(refine),
        # Disabled refinement is declared as (n_layers=0, factor=None);
        # record the None faithfully instead of failing on int(None).
        "refine_factor": (
            None if refine_factor is None else int(refine_factor)
        ),
        "n_layers": int(n_layers),
        "bisection_tol": float(bisection_tol),
        "caller_identity": caller_identity,
    }


class NDGridJournal:
    """Identity-bound checkpoint interface used by ``NDGridSolver``."""

    def __init__(self, directory: str | Path, *, identity: Any) -> None:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        self.store = DurableCheckpointStore(
            directory / "nd_grid_checkpoint.sqlite3",
            identity=identity,
        )
        self.identity_sha256 = identity_sha256(identity)

    @staticmethod
    def _point_key(idx: Tuple[int, ...]) -> str:
        return ",".join(str(int(value)) for value in idx)

    def save_point(self, idx: Tuple[int, ...], result: PointResult) -> None:
        """Commit one solver result after it has returned to the caller."""

        self.store.put_pickle("coarse-point", self._point_key(idx), {
            "index": tuple(int(value) for value in idx),
            "point": result,
        })

    def restore_grid(
        self,
        axes: list[GridAxis],
        n_basis: int,
    ) -> NDGrid:
        snapshot = self.store.get_pickle("coarse-grid", "complete", None)
        if isinstance(snapshot, NDGrid):
            self.store.event(
                "coarse_grid_snapshot_reused",
                converged=int(np.sum(snapshot.converged_mask)),
            )
            return snapshot

        grid = make_empty_grid(axes, n_basis)
        restored = 0
        for key in self.store.keys("coarse-point"):
            payload = self.store.get_pickle("coarse-point", key, None)
            if not isinstance(payload, dict):
                continue
            idx = tuple(int(value) for value in payload.get("index") or ())
            point = payload.get("point")
            if len(idx) != grid.ndim or not isinstance(point, PointResult):
                continue
            if any(value < 0 or value >= grid.shape[d]
                   for d, value in enumerate(idx)):
                continue
            grid.points[idx] = point
            if point.converged:
                grid.converged_mask[idx] = True
                grid.x_cache[idx] = point.x
            restored += 1
        if restored:
            self.store.event(
                "coarse_point_journal_replayed",
                restored=restored,
                converged=int(np.sum(grid.converged_mask)),
            )
        return grid

    def mark_phase_complete(self, phase: str, **payload: Any) -> None:
        self.store.put_json("phase", str(phase), {
            "complete": True,
            **payload,
        })
        self.store.event("grid_phase_complete", phase=str(phase), **payload)

    def phase_complete(self, phase: str) -> bool:
        payload = self.store.get_json("phase", str(phase), None)
        return isinstance(payload, dict) and bool(payload.get("complete"))

    def save_coarse_grid(self, grid: NDGrid) -> None:
        self.store.put_pickle("coarse-grid", "complete", grid)
        self.mark_phase_complete(
            "coarse",
            converged=int(np.sum(grid.converged_mask)),
            total=int(np.prod(grid.shape)),
        )

    def load_final_result(self) -> Any:
        return self.store.get_pickle("solve-result", "complete", None)

    def save_final_result(self, result: Any) -> None:
        self.store.put_pickle("solve-result", "complete", result)
        self.store.event("grid_solve_result_committed")

    def save_refinement_layer(
        self,
        *,
        layer: int,
        coarse_grid: NDGrid,
        refined_points: Any,
        x_cache: Any,
    ) -> None:
        self.store.put_pickle("refinement-layer", str(int(layer)), {
            "layer": int(layer),
            "coarse_grid": coarse_grid,
            "refined_points": refined_points,
            "x_cache": x_cache,
        })
        self.store.event(
            "refinement_layer_committed",
            layer=int(layer),
            point_count=len(refined_points or []),
        )

    @staticmethod
    def _refinement_node_key(parent_path: Any) -> str:
        canonical = [
            [int(value) for value in index]
            for index in parent_path
        ]
        return json.dumps(canonical, separators=(",", ":"))

    def save_refinement_node(
        self,
        parent_path: Any,
        node: dict,
        sub_points: np.ndarray,
        sub_labels_per_element: dict[str, np.ndarray],
    ) -> None:
        """Commit one fully solved R^N node as the refinement transaction."""

        # Store the node without descendants: descendants are independent
        # records and are reattached deterministically during replay.
        shallow_node = {
            "axes_vals": [np.asarray(values).copy()
                          for values in node.get("axes_vals") or []],
            "labels": np.asarray(node.get("labels")).copy(),
            "labels_per_element": {
                str(element): np.asarray(labels).copy()
                for element, labels in (
                    node.get("labels_per_element") or {}
                ).items()
            },
            "children": {},
        }
        key = self._refinement_node_key(parent_path)
        self.store.put_pickle("refinement-node", key, {
            "parent_path": tuple(
                tuple(int(value) for value in index)
                for index in parent_path
            ),
            "node": shallow_node,
            "sub_points": sub_points,
            "sub_labels_per_element": sub_labels_per_element,
        })
        self.store.event(
            "refinement_node_committed",
            parent_path=key,
        )

    def load_refinement_nodes(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for key in self.store.keys("refinement-node"):
            payload = self.store.get_pickle("refinement-node", key, None)
            if isinstance(payload, dict):
                records.append(payload)
        records.sort(key=lambda row: (
            len(row.get("parent_path") or ()),
            row.get("parent_path") or (),
        ))
        if records:
            self.store.event(
                "refinement_node_journal_replayed",
                node_count=len(records),
            )
        return records


__all__ = ["NDGridJournal", "grid_run_identity"]
