"""
Shared orchestration for sequential + parallel test execution.
===============================================================
Provides :class:`RateLimiter` (thread-safe) and two runner functions
that accept a pluggable ``run_fn(pid, prompt_text) -> dict`` callback.

Also provides :func:`setup_run_log` which attaches a ``FileHandler``
to the root logger so that every log message is captured in a
``run_log.txt`` file inside the test-run output directory.
"""
from __future__ import annotations

import logging
from pathlib import Path
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from ..general_hooks_management_helpers.general_tracking_hooks_output_helpers.output_writers import get_status


# ═══════════════════════════════════════════════════════════════════════════
#  Per-run file logging
# ═══════════════════════════════════════════════════════════════════════════

def setup_run_log(output_dir: Path, filename: str = "run_log.txt") -> logging.FileHandler:
    """Attach a FileHandler to the root logger that writes into *output_dir*.

    Returns the handler so the caller can remove it later if needed.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(output_dir / filename, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-5s | %(name)-18s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logging.getLogger().addHandler(fh)
    return fh


def teardown_run_log(handler: logging.FileHandler) -> None:
    """Flush and remove a file handler previously installed by setup_run_log."""
    handler.flush()
    handler.close()
    logging.getLogger().removeHandler(handler)


# ═══════════════════════════════════════════════════════════════════════════
#  Rate limiter
# ═══════════════════════════════════════════════════════════════════════════

class RateLimiter:
    """Thread-safe minimum-gap enforcer for API calls."""

    def __init__(self, min_gap_s: float = 6.0):
        self._min_gap = min_gap_s
        self._lock = threading.Lock()
        self._last_time = 0.0

    def wait(self):
        with self._lock:
            now = time.monotonic()
            wait_needed = self._last_time + self._min_gap - now
            if wait_needed > 0:
                time.sleep(wait_needed)
            self._last_time = time.monotonic()


# ═══════════════════════════════════════════════════════════════════════════
#  Sequential runner
# ═══════════════════════════════════════════════════════════════════════════

def run_sequential(
    prompts: list[tuple[str, str]],
    run_fn: Callable[[str, str], dict],
    *,
    after_fn: Optional[Callable[[str, dict], None]] = None,
    cooldown: float = 10.0,
    log: Optional[logging.Logger] = None,
) -> list[dict]:
    """Run prompts one-by-one with *cooldown* seconds between them.

    Parameters
    ----------
    prompts : list of (pid, prompt_text)
    run_fn  : ``run_fn(pid, prompt_text) -> result_dict``
    after_fn : optional ``after_fn(pid, result)`` called after each prompt
    cooldown : seconds to sleep between prompts
    """
    _log = log or logging.getLogger(__name__)
    results: list[dict] = []
    for i, (pid, prompt) in enumerate(prompts):
        result = run_fn(pid, prompt)
        results.append(result)
        if after_fn:
            after_fn(pid, result)
        status = get_status(result)
        _log.info(
            "  [%s] Q%s: %d iters, %.0fs, %d tools",
            status, pid, result.get("iterations", 0),
            result.get("elapsed_s", 0), len(result.get("tool_history", [])),
        )
        if i < len(prompts) - 1 and cooldown > 0:
            time.sleep(cooldown)
    return results


# ═══════════════════════════════════════════════════════════════════════════
#  Parallel runner
# ═══════════════════════════════════════════════════════════════════════════

def run_parallel(
    prompts: list[tuple[str, str]],
    run_fn: Callable[[str, str], dict],
    workers: int,
    gap: float,
    *,
    after_fn: Optional[Callable[[str, dict], None]] = None,
    error_template: Optional[Callable[[str, str, Exception], dict]] = None,
    log: Optional[logging.Logger] = None,
) -> list[dict]:
    """Run prompts in parallel with a shared rate limiter.

    Parameters
    ----------
    prompts : list of (pid, prompt_text)
    run_fn  : ``run_fn(pid, prompt_text) -> result_dict``
    workers : max parallel threads
    gap     : min seconds between prompt starts
    after_fn : optional ``after_fn(pid, result)`` called after each prompt
    error_template : optional factory for error result dicts
    """
    _log = log or logging.getLogger(__name__)
    limiter = RateLimiter(min_gap_s=gap)
    results: list[dict] = []
    futures_map: dict = {}

    def _worker(pid: str, prompt_text: str) -> dict:
        limiter.wait()
        _log.info("▶  START Q%s", pid)
        r = run_fn(pid, prompt_text)
        status = get_status(r)
        _log.info(
            "✓  DONE  Q%s  [%s]  %d iters  %.0fs  %d tools",
            pid, status, r.get("iterations", 0),
            r.get("elapsed_s", 0), len(r.get("tool_history", [])),
        )
        return r

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for pid, prompt in prompts:
            fut = pool.submit(_worker, pid, prompt)
            futures_map[fut] = (pid, prompt)

        for fut in as_completed(futures_map):
            pid, prompt_text = futures_map[fut]
            try:
                r = fut.result()
                results.append(r)
                if after_fn:
                    after_fn(pid, r)
            except Exception as e:
                _log.error("Prompt %s raised: %s", pid, e, exc_info=True)
                if error_template:
                    results.append(error_template(pid, prompt_text, e))
                else:
                    results.append({
                        "prompt_id": pid,
                        "prompt_text": prompt_text,
                        "answer": f"ERROR: {e}",
                        "iterations": 0,
                        "elapsed_s": 0.0,
                        "timed_out": False,
                        "tool_history": [],
                        "error": str(e),
                    })

    results.sort(key=lambda r: [int(x) for x in r["prompt_id"].split(".")])
    return results
