"""Sample the solver's rolling progress lines when an agent reads a log.

The solver writes one ``[progress] <stage>: ...`` line every few hundred
cells and a closing ``[progress] <stage> done: ...`` line per stage (see
``nd_grid/progress.py``).  A long sweep leaves hundreds of them in
``solver/sweep_log.txt``; the full record stays on disk, and an agent
reading the file sees a few representative lines per stage instead.

Per stage run the first line, the last line (normally the ``done`` line)
and evenly spaced lines in between are kept, ``PROGRESS_LINES_PER_STAGE``
in all.  Each omitted stretch becomes one marker line in place.  Every
other line is returned unchanged and in order.
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

PROGRESS_LINES_PER_STAGE = 5

# Optional ``[timestamp] `` prefix, then the progress tag and the stage
# name up to its colon (``done`` marks the stage's closing line).
_PROGRESS_LINE_RE = re.compile(
    r"^(?:\[[^\]\n]*\]\s+)?\[progress\] (?P<stage>[^:\n]+?)(?P<done> done)?:"
)


def _kept_positions(n: int, keep: int) -> set:
    """Indices ``0 .. n-1`` to keep: first, last and evenly spaced."""
    if n <= keep:
        return set(range(n))
    if keep <= 1:
        return {n - 1}
    return {round(k * (n - 1) / (keep - 1)) for k in range(keep)}


def sample_progress_lines(
    text: str, keep: int = PROGRESS_LINES_PER_STAGE,
) -> Tuple[str, int]:
    """Return ``(sampled_text, omitted_count)`` for ``text``.

    A stage run is the sequence of progress lines of one stage name up
    to and including its ``done`` line; a line with the same name after
    that ``done`` line starts a new run.  A run that ends without a
    ``done`` line (an interrupted sweep) continues into the next lines
    of that name.  Lines are split at ``\\n`` only.  Text without
    progress lines is returned unchanged with count 0.
    """
    if "[progress] " not in text:
        return text, 0
    lines = [line for line in re.split(r"(?<=\n)", text) if line]
    run_of: Dict[int, Tuple[str, int]] = {}
    runs: Dict[Tuple[str, int], List[int]] = {}
    open_run: Dict[str, int] = {}
    n_runs: Dict[str, int] = {}
    for i, line in enumerate(lines):
        match = _PROGRESS_LINE_RE.match(line)
        if match is None:
            continue
        stage = match.group("stage")
        if stage not in open_run:
            open_run[stage] = n_runs.get(stage, 0)
            n_runs[stage] = open_run[stage] + 1
        key = (stage, open_run[stage])
        run_of[i] = key
        runs.setdefault(key, []).append(i)
        if match.group("done"):
            del open_run[stage]

    drop = set()
    for positions in runs.values():
        kept = _kept_positions(len(positions), keep)
        drop.update(p for k, p in enumerate(positions) if k not in kept)
    if not drop:
        return text, 0

    out: List[str] = []
    pending_stage, pending_n = None, 0

    def flush() -> None:
        nonlocal pending_n
        if pending_n:
            out.append(
                f"[progress] … {pending_n} more '{pending_stage}' "
                "line(s) omitted here\n"
            )
            pending_n = 0

    for i, line in enumerate(lines):
        if i in drop:
            stage = run_of[i][0]
            if stage != pending_stage:
                flush()
                pending_stage = stage
            pending_n += 1
            continue
        flush()
        out.append(line)
    flush()
    sampled = "".join(out)
    if not text.endswith(("\n", "\r")) and sampled.endswith("\n") and lines and (
        len(lines) - 1 in drop
    ):
        sampled = sampled[:-1]
    return sampled, len(drop)


def progress_sampling_note(omitted: int, keep: int = PROGRESS_LINES_PER_STAGE) -> str:
    """Header fragment for a read whose progress lines were sampled."""
    if omitted <= 0:
        return ""
    return (
        f"; solver progress sampled to {keep} lines per stage, "
        f"{omitted} omitted"
    )
