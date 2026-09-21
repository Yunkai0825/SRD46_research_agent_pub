"""
Parallel dispatch helper for subagent delegation.
===================================================
Wraps ``ThreadPoolExecutor`` with label management, error capture,
and ordered result collection.
"""
from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List

log = logging.getLogger(__name__)


def dispatch_parallel(
    tasks_json: str,
    runner_fn: Callable[..., Dict[str, Any]],
    *,
    max_workers: int = 3,
    runner_kwargs_keys: tuple[str, ...] = ("question", "purpose", "tasks", "context"),
    default_agent: str = "query",
) -> Dict[str, Any]:
    """Parse a JSON task array and dispatch each task via *runner_fn*.

    Parameters
    ----------
    tasks_json : str
        JSON array of task specs.  Each dict must contain ``label``
        and the keys listed in *runner_kwargs_keys*.
    runner_fn : callable
        ``(question, purpose, tasks, context, ...) -> dict``.
        Called once per task.
    max_workers : int
        Maximum concurrent threads.
    runner_kwargs_keys : tuple[str, ...]
        Which keys from each task dict to pass as kwargs to *runner_fn*.
    default_agent : str
        Agent type label for error dicts when *runner_fn* raises.

    Returns
    -------
    dict
        ``{"n_tasks": N, "results": [...]}``.
    """
    try:
        tasks = json.loads(tasks_json) if isinstance(tasks_json, str) else tasks_json
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON — {e}"}
    if not isinstance(tasks, list):
        return {"error": "Expected a JSON array of task specs"}

    effective_workers = min(len(tasks), max_workers)
    log.info("Parallel dispatch: %d tasks, %d workers", len(tasks), effective_workers)

    results: List[Dict[str, Any] | None] = [None] * len(tasks)

    with ThreadPoolExecutor(max_workers=effective_workers) as pool:
        future_to_idx: Dict[Any, int] = {}
        for i, t in enumerate(tasks):
            kwargs = {k: t.get(k, "") for k in runner_kwargs_keys}
            fut = pool.submit(runner_fn, **kwargs)
            future_to_idx[fut] = i

        for fut in as_completed(future_to_idx):
            idx = future_to_idx[fut]
            label = tasks[idx].get("label", f"task_{idx}")
            agent = tasks[idx].get("agent", default_agent)
            try:
                r = fut.result()
                r["label"] = label
                results[idx] = r
            except Exception as e:
                log.warning("Parallel task %d (%s) failed: %s", idx, label, e)
                results[idx] = {"label": label, "error": str(e), "agent": agent}

    return {"n_tasks": len(tasks), "results": results}  # type: ignore[dict-item]
