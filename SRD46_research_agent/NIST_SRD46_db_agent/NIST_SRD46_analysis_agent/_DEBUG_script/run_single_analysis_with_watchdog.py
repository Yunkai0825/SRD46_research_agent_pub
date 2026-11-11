"""Run one SRD-46 analysis prompt with logging and heartbeat reminders.

The prompt is read verbatim from one UTF-8 text file. L0 turn/reminder
overrides pass through the public API and do not mutate inner-agent settings.
This monitor never terminates a run because raw wall time crossed a value:
solver and delegated pipeline work intentionally do not count against the
agents' effective-time reminder scales. Only explicit operator interruption
may terminate the child.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import multiprocessing as mp
import queue
import sys
import time
import traceback
from pathlib import Path


_REPO = Path(__file__).absolute().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class _Tee(io.TextIOBase):
    def __init__(self, primary, log_file) -> None:
        self.primary = primary
        self.log_file = log_file

    def write(self, text: str) -> int:  # type: ignore[override]
        for stream in (self.primary, self.log_file):
            try:
                stream.write(text)
                stream.flush()
            except Exception:
                pass
        return len(text)

    def flush(self) -> None:  # type: ignore[override]
        for stream in (self.primary, self.log_file):
            try:
                stream.flush()
            except Exception:
                pass

    def fileno(self) -> int:  # type: ignore[override]
        """Expose a real descriptor so nested subprocesses can inherit it.

        On Windows, ``subprocess`` calls ``fileno()`` on the stream supplied
        for a child's stderr.  Prefer the run log so stderr emitted by local
        MCP servers remains part of the same session record, and fall back to
        the original console stream only if the log stream has no descriptor.
        """
        try:
            return self.log_file.fileno()
        except (AttributeError, io.UnsupportedOperation, OSError, ValueError):
            return self.primary.fileno()

    def isatty(self) -> bool:  # type: ignore[override]
        try:
            return bool(self.primary.isatty())
        except (AttributeError, io.UnsupportedOperation, OSError, ValueError):
            return False


def _child_run(
    prompt: str,
    session_dir: str,
    log_path: str,
    estimate_missing_equilibria: bool,
    l0_max_iterations: int,
    l0_reasoning_timeout_s: float,
    result_queue,
) -> None:
    log_file = Path(log_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8", buffering=1) as fh:
        original_out, original_err = sys.stdout, sys.stderr
        sys.stdout = _Tee(original_out, fh)
        sys.stderr = _Tee(original_err, fh)
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
            stream=sys.stderr,
            force=True,
        )
        for noisy in (
            "httpx", "urllib3", "openai", "matplotlib", "requests", "PIL",
        ):
            logging.getLogger(noisy).setLevel(logging.WARNING)

        started = time.time()
        try:
            from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent import (
                SRD46_analysis_run,
            )

            result = SRD46_analysis_run(
                prompt,
                session_dir=Path(session_dir),
                debug=True,
                estimate_missing_equilibria=estimate_missing_equilibria,
                l0_max_iterations=l0_max_iterations,
                l0_reasoning_timeout_s=l0_reasoning_timeout_s,
            )
            result_queue.put({
                "status": "returned",
                "elapsed_s": time.time() - started,
                "session_dir": result.get("session_dir", session_dir),
                "completion_status": result.get("completion_status"),
                "timed_out": result.get("timed_out"),
                "verdict": (result.get("verdict") or {}).get("verdict"),
                "iterations": result.get("iterations"),
                "n_tool_calls": len(result.get("tool_history") or []),
                "l1_execution_complete": result.get("l1_execution_complete"),
            })
        except BaseException as exc:
            traceback.print_exc()
            result_queue.put({
                "status": "exception",
                "elapsed_s": time.time() - started,
                "session_dir": session_dir,
                "exception_type": type(exc).__name__,
                "exception": str(exc),
            })
        finally:
            try:
                sys.stdout.flush()
                sys.stderr.flush()
            finally:
                sys.stdout, sys.stderr = original_out, original_err


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt-file", required=True, type=Path)
    parser.add_argument("--session-dir", required=True, type=Path)
    parser.add_argument(
        "--wall-reminder-s",
        type=float,
        default=None,
        help=(
            "Optional raw-wall telemetry reminder. It never terminates the "
            "child and is not an agent budget."
        ),
    )
    parser.add_argument("--l0-max-iterations", type=int, required=True)
    parser.add_argument("--l0-reasoning-timeout-s", type=float, required=True)
    parser.add_argument(
        "--estimate-missing-equilibria",
        action="store_true",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    wall_reminder_s = args.wall_reminder_s
    if wall_reminder_s is not None and wall_reminder_s <= 0:
        raise ValueError("--wall-reminder-s must be greater than 0")

    prompt = args.prompt_file.read_text(encoding="utf-8")
    prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    args.session_dir.mkdir(parents=True, exist_ok=True)
    log_path = args.session_dir / "_run.log"
    status_path = args.session_dir / "run_monitor_status.json"

    print(f"prompt_file={args.prompt_file}", flush=True)
    print(f"prompt_chars={len(prompt)}", flush=True)
    print(f"prompt_sha256={prompt_sha256}", flush=True)
    print(f"session_dir={args.session_dir}", flush=True)
    print(
        "budget="
        f"L0:{args.l0_max_iterations} turns/"
        f"{args.l0_reasoning_timeout_s:g}s effective-time reminder scale; "
        f"whole-run:no wall deadline; "
        f"wall telemetry reminder={wall_reminder_s}; "
        f"estimation={args.estimate_missing_equilibria}",
        flush=True,
    )

    ctx = mp.get_context("spawn")
    result_queue = ctx.Queue()
    child = ctx.Process(
        target=_child_run,
        args=(
            prompt,
            str(args.session_dir),
            str(log_path),
            bool(args.estimate_missing_equilibria),
            int(args.l0_max_iterations),
            float(args.l0_reasoning_timeout_s),
            result_queue,
        ),
        name="SRD46-single-analysis",
    )
    started = time.time()
    child.start()
    last_heartbeat = started
    reminder_emitted = False

    try:
        while child.is_alive():
            child.join(timeout=10.0)
            now = time.time()
            elapsed = now - started
            if (
                wall_reminder_s is not None
                and not reminder_emitted
                and elapsed >= wall_reminder_s
            ):
                print(
                    f"[monitor reminder] raw wall elapsed={elapsed:.1f}s "
                    f"crossed {wall_reminder_s:g}s; continuing normally "
                    "because this is not an agent deadline.",
                    flush=True,
                )
                reminder_emitted = True
            if now - last_heartbeat >= 60:
                print(
                    f"[monitor] raw_wall_elapsed={elapsed:.1f}s "
                    "deadline=none "
                    f"child_pid={child.pid}",
                    flush=True,
                )
                last_heartbeat = now
    except KeyboardInterrupt:
        if child.is_alive():
            child.terminate()
            child.join(timeout=30)
            if child.is_alive():
                child.kill()
                child.join(timeout=10)
        summary = {
            "status": "interrupted",
            "elapsed_s": time.time() - started,
            "prompt_file": str(args.prompt_file),
            "prompt_sha256": prompt_sha256,
            "session_dir": str(args.session_dir),
        }
        status_path.write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        raise

    summary = None
    try:
        summary = result_queue.get_nowait()
    except queue.Empty:
        pass

    if summary is None:
        summary = {
            "status": "child_exited_without_summary",
            "elapsed_s": time.time() - started,
            "session_dir": str(args.session_dir),
            "child_exitcode": child.exitcode,
        }

    summary.update({
        "prompt_file": str(args.prompt_file),
        "prompt_chars": len(prompt),
        "prompt_sha256": prompt_sha256,
        "estimate_missing_equilibria": bool(
            args.estimate_missing_equilibria
        ),
        "l0_max_iterations": args.l0_max_iterations,
        "l0_reasoning_timeout_s": args.l0_reasoning_timeout_s,
        "wall_deadline_s": None,
        "wall_reminder_s": wall_reminder_s,
        "wall_reminder_emitted": reminder_emitted,
        "child_exitcode": child.exitcode,
    })
    status_path.write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, default=str), flush=True)

    if summary["status"] == "returned":
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
