"""Live analysis-agent runner route.

Mirrors the query-agent runner (``routes/agent.py``) but drives the
multi-layer **analysis agent** (``SRD46_analysis_run``) instead of the
freeform query runner. A run streams live DEBUG log output back to the
browser over Server-Sent Events; on completion the page embeds the standard
analysis **detail** page (``/analysis/<label>``) — including the wall-time
Gantt timeline — in an iframe.

Endpoints
---------
GET  /agent/analysis/                  — launch page
POST /agent/analysis/launch            — start a run (JSON: prompt, model,
                                         max_iterations, timeout, api_user)
GET  /agent/analysis/status/<run_id>   — JSON status snapshot
GET  /agent/analysis/stream/<run_id>   — SSE stream of log lines + status

The analysis agent has no per-call ``model`` / ``timeout`` arguments; those
form fields are applied as temporary overrides on the shared
``AGENT_CONFIG`` singleton for the duration of the run and restored
afterwards so batch runs in the same process are unaffected.
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
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from flask import Blueprint, Response, jsonify, render_template, request

from ._analysis_status import analysis_outcome

analysis_agent_bp = Blueprint(
    "analysis_agent", __name__, url_prefix="/agent/analysis"
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# ``.absolute()`` keeps a short subst-drive path (vs ``.resolve()`` -> long UNC),
# avoiding Windows MAX_PATH on the deep calc-input-building module paths.
_BROWSER_DIR = Path(__file__).absolute().parent.parent
_PROJECT_ROOT = _BROWSER_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from NIST_SRD46_database_browser.logging_utils import (
    restore_logger_levels,
    suppress_noisy_dependency_debug,
)
def _analysis_run_dir() -> Path:
    """Directory new live analysis runs are written to."""
    d = _PROJECT_ROOT / "_output" / "Analysis"
    d.mkdir(parents=True, exist_ok=True)
    return d



# ---------------------------------------------------------------------------
# Run registry
# ---------------------------------------------------------------------------

class AnalysisRun:
    """In-memory state of a single analysis-agent run."""

    def __init__(
        self,
        run_id: str,
        prompt: str,
        model: str,
        max_iterations: Optional[int],
        timeout: Optional[int],
        api_user: Optional[str],
    ) -> None:
        self.run_id = run_id
        self.prompt = prompt
        self.model = model
        self.max_iterations = max_iterations
        self.timeout = timeout
        self.api_user = (api_user or "").strip() or None

        self.status: str = "starting"   # starting|running|completed|error
        self.start_time: float = time.time()
        self.end_time: Optional[float] = None
        self.error: Optional[str] = None

        # Final artifacts (set on completion)
        self.label: Optional[str] = None        # session-dir name
        self.detail_url: Optional[str] = None    # <app_prefix>/analysis/<label>
        self.answer_preview: str = ""
        self.verdict: str = ""
        self.outcome: dict = {}
        self.iterations: Optional[int] = None
        self.timed_out: Optional[bool] = None
        # Mount prefix when served under the master browser (``/srd46``).
        # Empty when this SRD-46 app is run standalone.
        self.app_prefix: str = ""

        # Log buffer (capped) + monotonic per-line index for SSE resume
        self._log_lock = threading.Lock()
        self._log_buf: deque = deque(maxlen=40_000)
        self._log_seq: int = 0

        self._handler: Optional[logging.Handler] = None
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


_runs: dict[str, AnalysisRun] = {}
_runs_lock = threading.Lock()
_active_run_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Logging handler that funnels records into a single AnalysisRun
# ---------------------------------------------------------------------------

class _RunLogHandler(logging.Handler):
    """Funnel captured log records into the run's buffer.

    Attached to the root logger for the lifetime of the run, then removed.
    Captures **all** logging activity while attached, so analysis runs are
    serialized (one at a time).
    """

    _FORMATTER = logging.Formatter(
        "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    def __init__(self, run: AnalysisRun) -> None:
        super().__init__(level=logging.DEBUG)
        self._run = run
        self.setFormatter(self._FORMATTER)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._run.append_log(self.format(record))
        except Exception:
            pass


def _attach_handler(run: AnalysisRun) -> None:
    handler = _RunLogHandler(run)
    run._handler = handler
    root = logging.getLogger()
    if root.level == logging.NOTSET or root.level > logging.DEBUG:
        root.setLevel(logging.DEBUG)
    root.addHandler(handler)


def _detach_handler(run: AnalysisRun) -> None:
    if run._handler is not None:
        try:
            logging.getLogger().removeHandler(run._handler)
        except Exception:
            pass
        run._handler = None


# ---------------------------------------------------------------------------
# Analysis-agent config overrides (model / iteration / timeout / API user)
# ---------------------------------------------------------------------------
#
# ``SRD46_analysis_run`` takes only ``(user_request, *, session_dir, debug)``;
# model selection, the L0 iteration budget and the wall-clock limit live on
# the shared ``AGENT_CONFIG`` singleton. We snapshot the affected fields,
# apply the per-run overrides, and restore them afterwards so the global
# config is left untouched for any subsequent batch run in this process.

_OVERRIDE_FIELDS = (
    "MODEL", "L1_MODEL", "L2_MODEL", "VERDICT_MODEL", "PLANNER_MODEL",
    "MAX_TOOL_ITERATIONS", "MAX_TURN_SECONDS", "API_USER",
)


def _get_agent_config() -> Optional[Any]:
    try:
        from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.SRD46_analysis_argo_config import (
            AGENT_CONFIG,
        )
        return AGENT_CONFIG
    except Exception:
        return None


def _snapshot_config(cfg: Any) -> Dict[str, Any]:
    return {f: getattr(cfg, f, None) for f in _OVERRIDE_FIELDS}


def _apply_overrides(run: AnalysisRun, cfg: Any) -> None:
    if run.api_user:
        os.environ["ARGO_API_USER"] = run.api_user
        try:
            cfg.API_USER = run.api_user
        except Exception:
            pass
        run.append_log(f"[browser] Argo API user set to: {run.api_user}")
    if run.model:
        for field in ("MODEL", "L1_MODEL", "L2_MODEL", "VERDICT_MODEL", "PLANNER_MODEL"):
            try:
                setattr(cfg, field, run.model)
            except Exception:
                pass
        run.append_log(f"[browser] Model set to: {run.model}")
    if run.max_iterations:
        try:
            cfg.MAX_TOOL_ITERATIONS = run.max_iterations
        except Exception:
            pass
    if run.timeout:
        try:
            cfg.MAX_TURN_SECONDS = run.timeout
        except Exception:
            pass


def _restore_config(cfg: Any, snap: Dict[str, Any]) -> None:
    for field, value in snap.items():
        try:
            setattr(cfg, field, value)
        except Exception:
            pass


def _current_default_api_user() -> str:
    """Best-effort read of the currently-configured ANL username."""
    cfg = _get_agent_config()
    if cfg is not None:
        return getattr(cfg, "API_USER", "") or ""
    return os.environ.get("ARGO_API_USER", "") or ""


# ---------------------------------------------------------------------------
# Run execution
# ---------------------------------------------------------------------------

def _safe_label(prompt: str) -> str:
    """Auto-generate a filesystem-safe session label for a browser run."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = re.sub(r"[^A-Za-z0-9]+", "_", prompt.strip())[:32].strip("_")
    return f"Browser_analysis_{stamp}" + (f"_{slug}" if slug else "")


def _execute_run(run: AnalysisRun) -> None:
    """Run the real analysis agent and update *run* with the result."""
    _attach_handler(run)
    noisy_logger_levels = suppress_noisy_dependency_debug()
    cfg = _get_agent_config()
    snap = _snapshot_config(cfg) if cfg is not None else {}
    try:
        run.status = "running"
        run.append_log(
            f"[browser] Launching SRD-46 analysis agent: model={run.model} "
            f"max_iterations={run.max_iterations} timeout={run.timeout}"
        )

        if cfg is not None:
            _apply_overrides(run, cfg)
        else:
            run.append_log(
                "[browser] WARN: analysis AGENT_CONFIG unavailable; "
                "model/API-user overrides not applied."
            )

        from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent import (
            SRD46_analysis_run,
        )

        run.label = _safe_label(run.prompt)
        sess = _analysis_run_dir() / run.label
        sess.mkdir(parents=True, exist_ok=True)
        run.append_log(f"[browser] Session directory: {sess}")

        result = SRD46_analysis_run(
            run.prompt,
            session_dir=sess,
            debug=True,
        )

        run.label = Path(result.get("session_dir", sess)).name
        prefix = (run.app_prefix or "").rstrip("/")
        run.detail_url = f"{prefix}/analysis/{run.label}"

        # File-storage disabled → register this run's output for cleanup (it
        # also lives under the agent dir's _Temp/ subfolder).
        run.iterations = result.get("iterations")
        run.timed_out = result.get("timed_out")
        verdict = result.get("verdict") or {}
        run.outcome = analysis_outcome(result, verdict)
        run.verdict = run.outcome["status"]
        run.answer_preview = (result.get("answer") or "")[:2000]

        run.status = "completed"
        run.append_log(
            f"[browser] Run finished. label={run.label}  "
            f"outcome={run.outcome['label']}  "
            f"{run.outcome['stop_label']}  view: {run.detail_url}"
        )
    except Exception as exc:  # noqa: BLE001 — surface any error to the UI
        run.status = "error"
        run.error = f"{type(exc).__name__}: {exc}"
        run.append_log(f"[browser] ERROR: {run.error}")
        for line in traceback.format_exc().splitlines():
            run.append_log(line)
    finally:
        if cfg is not None:
            _restore_config(cfg, snap)
        restore_logger_levels(noisy_logger_levels)
        run.end_time = time.time()
        _detach_handler(run)
        global _active_run_id
        with _runs_lock:
            if _active_run_id == run.run_id:
                _active_run_id = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@analysis_agent_bp.route("/")
def analysis_agent_page():
    return render_template(
        "analysis_agent.html",
        default_api_user=_current_default_api_user(),
    )


@analysis_agent_bp.route("/launch", methods=["POST"])
def analysis_agent_launch():
    global _active_run_id

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    prompt = (data.get("prompt") or data.get("query") or "").strip()
    if not prompt:
        return jsonify(error="Prompt is required."), 400

    api_user = (data.get("api_user") or _current_default_api_user()).strip()

    model = (data.get("model") or "claudeopus47").strip()

    def _to_int(name: str) -> Optional[int]:
        v = data.get(name)
        if v is None or v == "":
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    max_iterations = _to_int("max_iterations")
    timeout = _to_int("timeout")

    with _runs_lock:
        if _active_run_id and _active_run_id in _runs:
            prev = _runs[_active_run_id]
            if prev.status in ("starting", "running"):
                return jsonify(
                    error="An analysis run is already in progress."
                ), 409

        run_id = uuid.uuid4().hex[:12]
        run = AnalysisRun(
            run_id, prompt, model, max_iterations, timeout, api_user or None
        )
        run.app_prefix = (request.script_root or "").rstrip("/")
        _runs[run_id] = run
        _active_run_id = run_id

    thread = threading.Thread(target=_execute_run, args=(run,), daemon=True)
    run._thread = thread
    thread.start()
    return jsonify(run_id=run_id)


def _status_payload(run: AnalysisRun) -> dict:
    payload = {
        "run_id": run.run_id,
        "status": run.status,
        "elapsed": round(run.elapsed, 2),
        "model": run.model,
    }
    if run.status == "completed":
        payload["label"] = run.label
        payload["detail_url"] = run.detail_url
        payload["answer_preview"] = run.answer_preview
        payload["verdict"] = run.verdict
        payload["outcome"] = run.outcome
        payload["iterations"] = run.iterations
        payload["timed_out"] = run.timed_out
    elif run.status == "error":
        payload["error"] = run.error
    return payload


@analysis_agent_bp.route("/status/<run_id>")
def analysis_agent_status(run_id: str):
    run = _runs.get(run_id)
    if not run:
        return jsonify(error="Run not found."), 404
    return jsonify(_status_payload(run))


@analysis_agent_bp.route("/stream/<run_id>")
def analysis_agent_stream(run_id: str):
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
