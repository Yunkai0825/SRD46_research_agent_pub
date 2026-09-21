"""SRD-46 agent runner route.

Wires the browser's *Agent* page to the real freeform-query runner
(`freeform_runner.run_freeform_query`) and streams live DEBUG-level log
output back to the browser via Server-Sent Events.

Endpoints
---------
GET  /agent/                  — launch page
POST /agent/launch            — start a run (JSON: prompt, model, max_turns,
                                timeout, simulate)
GET  /agent/stream/<run_id>   — SSE stream of log lines + status
GET  /agent/status/<run_id>   — JSON status snapshot

The page renders the live terminal log in real time. When the run finishes,
it embeds the standard ``/eval/<model>/<qid>/<batch>`` page in an iframe so
the user sees the full claim-analysis / preplan / plan / tool-results panels
on the same page, with the terminal pushed to the bottom.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
import time
import traceback
import uuid
from collections import deque
from pathlib import Path
from typing import Optional

from flask import Blueprint, Response, jsonify, render_template, request


agent_bp = Blueprint("agent", __name__, url_prefix="/agent")


# Project root (one level above the browser package)
# ``.absolute()`` keeps a short subst-drive path (vs ``.resolve()`` -> long UNC).
_BROWSER_DIR = Path(__file__).absolute().parent.parent
_PROJECT_ROOT = _BROWSER_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
from NIST_SRD46_database_browser.logging_utils import (  # noqa: E402
    restore_logger_levels,
    suppress_noisy_dependency_debug,
)

class AgentRun:
    """In-memory state of a single agent run (real or simulated)."""

    def __init__(
        self,
        run_id: str,
        prompt: str,
        model: str,
        max_turns: Optional[int],
        timeout: Optional[int],
        simulate: bool,
        skip_claim_validation: bool = False,
        api_user: Optional[str] = None,
    ) -> None:
        self.run_id = run_id
        self.prompt = prompt
        self.model = model
        self.max_turns = max_turns
        self.timeout = timeout
        self.simulate = simulate
        self.skip_claim_validation = skip_claim_validation
        self.api_user = (api_user or "").strip() or None

        self.status: str = "starting"   # starting|running|completed|error
        self.start_time: float = time.time()
        self.end_time: Optional[float] = None
        self.error: Optional[str] = None

        # Final artifacts (set on completion)
        self.qid: Optional[str] = None
        self.eval_url: Optional[str] = None
        self.answer_preview: str = ""
        # Mount prefix when served under the master browser
        # (``/srd46``). Empty when this SRD-46 app is run standalone.
        self.app_prefix: str = ""
        # Simulation-only markdown panels (preplan / plan / tool results /
        # history) shown between the answer and terminal log on the page.
        self.preplan_md: str = ""
        self.plan_md: str = ""
        self.tool_results_md: str = ""
        self.history_md: str = ""
        self.flow_mermaid: str = ""

        # Real-time log file written to <out_dir>/agent_log_batch1.log during
        # a real run (mirrors what the user sees streamed in the terminal).
        self.log_file_path: Optional[Path] = None

        # Log buffer (capped) + monotonic per-line index for SSE resume
        self._log_lock = threading.Lock()
        self._log_buf: deque = deque(maxlen=20_000)
        self._log_seq: int = 0

        self._handler: Optional[logging.Handler] = None
        self._file_handler: Optional[logging.Handler] = None
        self._thread: Optional[threading.Thread] = None

    # -- log API -----------------------------------------------------------

    def append_log(self, line: str) -> None:
        with self._log_lock:
            self._log_seq += 1
            self._log_buf.append((self._log_seq, line))

    def logs_since(self, last_seq: int) -> tuple[int, list[str]]:
        with self._log_lock:
            if not self._log_buf:
                return last_seq, []
            out: list[str] = []
            new_last = last_seq
            for seq, line in self._log_buf:
                if seq > last_seq:
                    out.append(line)
                    new_last = seq
            return new_last, out

    @property
    def elapsed(self) -> float:
        end = self.end_time or time.time()
        return end - self.start_time


_runs: dict[str, AgentRun] = {}
_runs_lock = threading.Lock()
_active_run_id: Optional[str] = None


# ---------------------------------------------------------------------------
# ANL Argo API user propagation
# ---------------------------------------------------------------------------
#
# argo_config.API_USER is read into module-level *names* by argo_client.py and
# strategy_planner.py at import time (``from argo_config import API_USER``).
# Mutating argo_config.API_USER alone therefore does NOT change the value used
# by callers that already imported it. To make the per-run username effective
# for every Argo HTTP call this process makes, we patch every known binding.
#
# This is intentionally tolerant: any module that has not yet been imported
# is simply skipped, and the env var ARGO_API_USER is also updated so any
# subsequently-imported module picks up the same value as its default.

def _apply_api_user(api_user: str) -> None:
    """Set ``api_user`` as the active ANL Argo username everywhere in-process."""
    api_user = (api_user or "").strip()
    if not api_user:
        return

    os.environ["ARGO_API_USER"] = api_user

    try:
        from NIST_SRD46_db_agent.NIST_SRD46_query_agent import argo_config
        argo_config.API_USER = api_user
    except Exception:
        pass

    # Update bindings already imported from the package configuration.
    package = "NIST_SRD46_db_agent.NIST_SRD46_query_agent"
    for module_name, attribute in (
        (f"{package}.argo_client", "API_USER"),
        (f"{package}.SRD46_tools.strategy_planner", "_API_USER"),
        (f"{package}.terminal_chat", "API_USER"),
    ):
        module = sys.modules.get(module_name)
        if module is not None and hasattr(module, attribute):
            setattr(module, attribute, api_user)


def _current_default_api_user() -> str:
    """Read the configured API username, if supplied locally."""
    try:
        from NIST_SRD46_db_agent.NIST_SRD46_query_agent import argo_config
        return os.environ.get("ARGO_API_USER") or argo_config.API_USER or ""
    except Exception:
        return os.environ.get("ARGO_API_USER", "") or ""


# ---------------------------------------------------------------------------
# Logging handler that funnels records into a single AgentRun
# ---------------------------------------------------------------------------

class _RunLogHandler(logging.Handler):
    """Funnel captured log records into the run's buffer.

    Attached to the root logger for the lifetime of the run, then removed.
    Note: this captures **all** logging activity in the process while the
    handler is attached, so the browser must serialize runs (one at a time).
    """

    _FORMATTER = logging.Formatter(
        "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    def __init__(self, run: AgentRun) -> None:
        super().__init__(level=logging.DEBUG)
        self._run = run
        self.setFormatter(self._FORMATTER)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._run.append_log(self.format(record))
        except Exception:
            pass


def _attach_handler(run: AgentRun) -> None:
    handler = _RunLogHandler(run)
    run._handler = handler
    root = logging.getLogger()
    if root.level == logging.NOTSET or root.level > logging.DEBUG:
        root.setLevel(logging.DEBUG)
    root.addHandler(handler)


def _attach_file_handler(run: AgentRun, log_path: Path) -> None:
    """Attach a FileHandler that mirrors all log records to *log_path*."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logging.getLogger().addHandler(fh)
    run._file_handler = fh
    run.log_file_path = log_path


def _detach_handler(run: AgentRun) -> None:
    if run._handler is not None:
        try:
            logging.getLogger().removeHandler(run._handler)
        except Exception:
            pass
        run._handler = None
    if run._file_handler is not None:
        try:
            logging.getLogger().removeHandler(run._file_handler)
            run._file_handler.close()
        except Exception:
            pass
        run._file_handler = None


# ---------------------------------------------------------------------------
# Run execution
# ---------------------------------------------------------------------------

def _execute_real_run(run: AgentRun) -> None:
    """Run the real freeform query and update *run* with the result."""
    _attach_handler(run)
    noisy_logger_levels = suppress_noisy_dependency_debug()
    try:
        run.status = "running"
        run.append_log(
            f"[browser] Launching SRD-46 agent: model={run.model} "
            f"max_turns={run.max_turns} timeout={run.timeout}"
        )

        from NIST_SRD46_db_agent.NIST_SRD46_query_agent import freeform_runner

        # Apply the per-run ANL API user before any Argo call goes out.
        if run.api_user:
            try:
                _apply_api_user(run.api_user)
                run.append_log(f"[browser] Argo API user set to: {run.api_user}")
            except Exception as exc:  # noqa: BLE001
                run.append_log(f"[browser] WARN: could not set API user ({exc})")

        # Pre-compute qid so we can mkdir the run's out_dir up front and
        # mirror live logs to <out_dir>/agent_log_batch1.log.
        run.qid = freeform_runner._new_freeform_qid()
        _output_root, _eval_root = freeform_runner.resolve_roots()
        out_dir = _output_root / f"Model_{run.model}" / run.qid
        log_path = out_dir / "agent_log_batch1.log"
        try:
            _attach_file_handler(run, log_path)
            run.append_log(f"[browser] Real-time log file: {log_path}")
        except Exception as exc:  # noqa: BLE001
            run.append_log(f"[browser] WARN: could not open log file ({exc})")

        result = freeform_runner.run_freeform_query(
            run.prompt,
            model=run.model,
            timeout=run.timeout,
            max_turns=run.max_turns,
            qid=run.qid,
            title="Browser freeform query",
            enrich=True,
            enrich_claims=not run.skip_claim_validation,
            enable_sql=True,
        )

        run.qid = result["qid"]
        prefix = (run.app_prefix or "").rstrip("/")
        run.eval_url = f"{prefix}/eval/{run.model}/{run.qid}/1"

        # Best-effort short answer preview for the quick-summary box
        try:
            answer_path = result.get("answer_path")
            if answer_path and Path(answer_path).exists():
                txt = Path(answer_path).read_text(encoding="utf-8", errors="replace")
                run.answer_preview = txt[:2000]
            else:
                rp = Path(result["result_path"])
                if rp.exists():
                    run.answer_preview = rp.read_text(encoding="utf-8", errors="replace")[:2000]
        except Exception:  # pragma: no cover — preview is best-effort
            pass

        run.status = "completed"
        run.append_log(
            f"[browser] Run complete. qid={run.qid}  view: {run.eval_url}"
        )
        if run.log_file_path is not None:
            run.append_log(f"[browser] Real-time log saved to: {run.log_file_path}")

    except Exception as exc:  # noqa: BLE001 — surface any error to the UI
        run.status = "error"
        run.error = f"{type(exc).__name__}: {exc}"
        run.append_log(f"[browser] ERROR: {run.error}")
        for line in traceback.format_exc().splitlines():
            run.append_log(line)
    finally:
        run.end_time = time.time()
        restore_logger_levels(noisy_logger_levels)
        _detach_handler(run)
        global _active_run_id
        with _runs_lock:
            if _active_run_id == run.run_id:
                _active_run_id = None


# ---------------------------------------------------------------------------
# Simulated run — replays canned Q1.1.1 (Cu(II)–glycine) artifacts so the UI
# can be exercised offline without spending real Argo budget.
# ---------------------------------------------------------------------------

from . import _simulation_data as _sim  # noqa: E402  (after Blueprint defn)


def _execute_simulated_run(run: AgentRun) -> None:
    """Replay a canned log sequence + answer / panels for the demo UI."""
    try:
        run.status = "running"
        for delay, level, msg in _sim.SIM_LOG_SCRIPT:
            time.sleep(delay)
            ts = time.strftime("%H:%M:%S")
            run.append_log(f"{ts} | {level:<5} | {msg}")
        run.status = "completed"
        run.qid = "Qfree_simulated"
        run.eval_url = ""  # simulation has no real eval page
        run.answer_preview = _sim.SIM_ANSWER_MD
        run.preplan_md = _sim.SIM_PREPLAN_MD
        run.plan_md = _sim.SIM_PLAN_MD
        run.tool_results_md = _sim.SIM_TOOL_RESULTS_MD
        run.history_md = _sim.SIM_HISTORY_MD
        run.flow_mermaid = _sim.SIM_FLOW_MERMAID
        run.append_log("[browser] Simulated run complete (eval iframe not loaded)")
    except Exception as exc:  # noqa: BLE001
        run.status = "error"
        run.error = f"{type(exc).__name__}: {exc}"
        run.append_log(f"[browser] ERROR: {run.error}")
    finally:
        run.end_time = time.time()
        global _active_run_id
        with _runs_lock:
            if _active_run_id == run.run_id:
                _active_run_id = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@agent_bp.route("/")
def agent_page():
    return render_template(
        "agent.html",
        default_api_user=_current_default_api_user(),
    )


@agent_bp.route("/launch", methods=["POST"])
def agent_launch():
    global _active_run_id

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    prompt = (data.get("prompt") or data.get("query") or "").strip()
    if not prompt:
        return jsonify(error="Prompt is required."), 400

    model = (data.get("model") or "gpt54").strip()
    # Simulate is intentionally not exposed in the current UI but kept in the
    # backend for future re-enablement. It is only triggered when an explicit
    # truthy ``simulate`` field is posted (e.g. via curl during development).
    simulate = bool(data.get("simulate", False))
    api_user = (data.get("api_user") or _current_default_api_user()).strip()

    def _to_int(name: str) -> Optional[int]:
        v = data.get(name)
        if v is None or v == "":
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    max_turns = _to_int("max_turns")
    timeout = _to_int("timeout")
    skip_claim_validation = bool(data.get("skip_claim_validation", False))

    with _runs_lock:
        if _active_run_id and _active_run_id in _runs:
            prev = _runs[_active_run_id]
            if prev.status in ("starting", "running"):
                return jsonify(error="An agent run is already in progress."), 409

        run_id = uuid.uuid4().hex[:12]
        run = AgentRun(run_id, prompt, model, max_turns, timeout, simulate,
                       skip_claim_validation=skip_claim_validation,
                       api_user=api_user or None)
        run.app_prefix = (request.script_root or "").rstrip("/")
        _runs[run_id] = run
        _active_run_id = run_id

    target = _execute_simulated_run if simulate else _execute_real_run
    thread = threading.Thread(target=target, args=(run,), daemon=True)
    run._thread = thread
    thread.start()
    return jsonify(run_id=run_id, simulate=simulate)


def _status_payload(run: AgentRun) -> dict:
    payload = {
        "run_id": run.run_id,
        "status": run.status,
        "elapsed": round(run.elapsed, 2),
        "model": run.model,
        "simulate": run.simulate,
    }
    if run.status == "completed":
        payload["qid"] = run.qid
        payload["eval_url"] = run.eval_url
        payload["answer_preview"] = run.answer_preview
        payload["preplan_md"] = run.preplan_md
        payload["plan_md"] = run.plan_md
        payload["tool_results_md"] = run.tool_results_md
        payload["history_md"] = run.history_md
        payload["flow_mermaid"] = run.flow_mermaid
        if run.log_file_path is not None:
            payload["log_file_path"] = str(run.log_file_path)
    elif run.status == "error":
        payload["error"] = run.error
    return payload


@agent_bp.route("/status/<run_id>")
def agent_status(run_id: str):
    run = _runs.get(run_id)
    if not run:
        return jsonify(error="Run not found."), 404
    return jsonify(_status_payload(run))


@agent_bp.route("/stream/<run_id>")
def agent_stream(run_id: str):
    """SSE endpoint that pushes new log lines + status until the run ends."""
    run = _runs.get(run_id)
    if not run:
        return jsonify(error="Run not found."), 404

    def _sse(event: str, data: dict, event_id: Optional[int] = None) -> str:
        prefix = f"id: {event_id}\n" if event_id is not None else ""
        return f"{prefix}event: {event}\ndata: {json.dumps(data, default=str)}\n\n"

    # After a proxy/network cut the browser reconnects with the last log seq.
    try:
        resume_seq = int(request.headers.get("Last-Event-ID") or 0)
    except (TypeError, ValueError):
        resume_seq = 0

    def generate():
        _KEEPALIVE_S = 15  # comment frame beats reverse-proxy read timeouts (60 s default)
        last_seq = resume_seq
        last_status = ""
        idle_deadline = time.time() + 60 * 60  # 1 h hard idle cap
        next_keepalive = time.time() + _KEEPALIVE_S

        # Initial status + any logs already buffered
        yield _sse("status", _status_payload(run))
        last_status = run.status
        new_seq, new_lines = run.logs_since(last_seq)
        if new_lines:
            last_seq = new_seq
            filtered = new_lines
            if filtered:
                yield _sse("log", {"lines": filtered}, event_id=new_seq)

        while True:
            ro = _runs.get(run_id)
            if ro is None:
                yield _sse("error", {"msg": "Run vanished"})
                break

            sent = False
            new_seq, new_lines = ro.logs_since(last_seq)
            if new_lines:
                last_seq = new_seq
                idle_deadline = time.time() + 60 * 60
                filtered = new_lines
                if filtered:
                    yield _sse("log", {"lines": filtered}, event_id=new_seq)
                    sent = True

            if ro.status != last_status:
                last_status = ro.status
                yield _sse("status", _status_payload(ro))
                sent = True

            if ro.status in ("completed", "error"):
                # Drain any straggler lines, then close
                new_seq, new_lines = ro.logs_since(last_seq)
                if new_lines:
                    last_seq = new_seq
                    filtered = new_lines
                    if filtered:
                        yield _sse("log", {"lines": filtered}, event_id=new_seq)
                yield _sse("done", _status_payload(ro))
                break

            if time.time() > idle_deadline:
                yield _sse("error", {"msg": "Idle timeout"})
                break

            if sent:
                next_keepalive = time.time() + _KEEPALIVE_S
            elif time.time() >= next_keepalive:
                yield ": keepalive\n\n"
                next_keepalive = time.time() + _KEEPALIVE_S

            time.sleep(0.5)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
