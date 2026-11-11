"""Optional, task-local persistence for embedded query conversations.

No scope means no filesystem or logging changes. The MCP subprocess receives
only its own artifact directory in a copied environment; process-global
stdout/stderr and parent environment are never redirected.
"""
from __future__ import annotations

import base64
import contextvars
import json
import logging
import os
import threading
import time
import traceback
import uuid
from contextlib import contextmanager
from pathlib import Path

MCP_ARTIFACT_ENV = "SRD46_QUERY_MCP_ARTIFACT_DIR"
MCP_SCOPE_ENV = "SRD46_QUERY_MCP_SCOPE_ID"
_active = contextvars.ContextVar("srd46_query_artifact_sink", default=None)


def _io_path(path):
    path = Path(path)
    if os.name != "nt":
        return path
    raw = str(path.absolute())
    if raw.startswith("\\\\?\\"):
        return path
    if raw.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + raw[2:])
    return Path("\\\\?\\" + raw)


def _write_json(path, value):
    _io_path(path).write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def _replace(temporary, target):
    """Publish a staged file with the shared retry for SMB sharing failures."""
    from NIST_SRD46_db_agent.general_db_query_engine.general_checkpointing import replace_with_retry
    replace_with_retry(_io_path(temporary), _io_path(target))


class _ScopeFilter(logging.Filter):
    def __init__(self, sink):
        super().__init__()
        self.sink = sink

    def filter(self, record):
        return _active.get() is self.sink


class _Sink:
    def __init__(self, directory):
        self.directory = Path(directory).absolute()
        self.scope_id = uuid.uuid4().hex
        _io_path(self.directory).mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.events = _io_path(self.directory / "runtime_events.jsonl").open(
            "a", encoding="utf-8", buffering=1,
        )
        self.stderr = _io_path(self.directory / "mcp_stderr.log").open(
            "a", encoding="utf-8", buffering=1,
        )
        self.handler = logging.FileHandler(
            _io_path(self.directory / "runtime.log"), encoding="utf-8",
        )
        self.handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s | %(message)s",
        ))
        self.handler.addFilter(_ScopeFilter(self))


def current_artifact_dir():
    sink = _active.get()
    return sink.directory if sink is not None else None


def current_scope_id():
    sink = _active.get()
    return sink.scope_id if sink is not None else None


def raise_if_mcp_authorization_denied():
    """Promote only this query invocation's durable child HTTP denial."""
    sink = _active.get()
    if sink is None:
        return
    marker = sink.directory / f"mcp_authorization_denied_{sink.scope_id}.json"
    if not _io_path(marker).is_file():
        return
    receipt = json.loads(_io_path(marker).read_text(encoding="utf-8"))
    if receipt.get("scope_id") != sink.scope_id:
        raise RuntimeError("MCP authorization receipt belongs to a different query scope")
    from NIST_SRD46_db_agent.general_db_query_engine.general_first_principle_API_call_reconstruct import AuthorizationInterrupted
    record_event("authorization_denied", receipt)
    raise AuthorizationInterrupted(
        "Authorization denied by embedded query MCP transport; receipt: " + str(marker)
    )


def mcp_stderr_target():
    sink = _active.get()
    return sink.stderr if sink is not None else None


def record_event(kind, payload):
    sink = _active.get()
    if sink is None:
        return
    event = {"kind": kind, "timestamp": time.time(), "pid": os.getpid(),
             "thread_id": threading.get_ident(), "payload": payload}
    with sink.lock:
        sink.events.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
        sink.events.flush()


def record_state(**state):
    """Persist caller-visible state after each completed tool and on exit."""
    sink = _active.get()
    if sink is None:
        return
    with sink.lock:
        temporary = sink.directory / "runtime_state.json.tmp"
        _write_json(temporary, state)
        _replace(temporary, sink.directory / "runtime_state.json")


@contextmanager
def query_artifact_scope(artifact_dir, *, user_prompt=None, system_prompt=None):
    """Record one query turn without changing its model or tool interface."""
    sink = _Sink(artifact_dir)
    token = _active.set(sink)
    root = logging.getLogger()
    root.addHandler(sink.handler)
    started = time.time()
    status = "running"
    error = None
    try:
        record_event("query_scope_start", {
            "user_prompt": user_prompt, "system_prompt": system_prompt,
            "scope_id": sink.scope_id,
        })
        yield sink.directory
        status = "returned"
    except BaseException as exc:
        status = "error"
        error = {"type": type(exc).__name__, "message": str(exc),
                 "traceback": "".join(traceback.format_exception(exc))}
        record_event("query_scope_error", error)
        raise
    finally:
        try:
            record_event("query_scope_end", {"status": status})
            _write_json(sink.directory / "runtime_manifest.json", {
                "status": status, "started": started, "finished": time.time(),
                "scope_id": sink.scope_id,
                "error": error, "files": ["runtime.log", "mcp_stderr.log", "runtime_events.jsonl"],
            })
        finally:
            root.removeHandler(sink.handler)
            sink.handler.close()
            sink.events.close()
            sink.stderr.close()
            _active.reset(token)


def record_http_post(post, url, **kwargs):
    """Pass one native planner HTTP attempt through unchanged and save evidence.

    Only the explicit query scope or this MCP child's private environment can
    enable recording. Authentication/request headers and cookies are omitted.
    Ordinary responses/errors retain their native behavior. Authorization
    denial is recorded in full, then interrupts the child before retries or
    planner fallback can convert a provider failure into model context.
    """
    from NIST_SRD46_db_agent.general_db_query_engine.general_first_principle_API_call_reconstruct.query_bridge import child_http
    native_post = post
    post = lambda address, **options: child_http(native_post, address, **options)
    directory = current_artifact_dir()
    if directory is None:
        child_directory = os.environ.get(MCP_ARTIFACT_ENV, "").strip()
        directory = Path(child_directory) if child_directory else None
    if directory is None:
        return post(url, **kwargs)
    attempts = directory / "mcp_http_calls"
    _io_path(attempts).mkdir(parents=True, exist_ok=True)
    attempt = attempts / f"{time.time_ns()}_{os.getpid()}_{uuid.uuid4().hex}"
    _io_path(attempt).mkdir()
    # Native planner calls use JSON bodies, never authentication in the body.
    request = {"method": "POST", "url": url, "json": kwargs.get("json"),
               "timeout": kwargs.get("timeout"), "started": time.time()}
    _write_json(attempt / "request.json", request)
    try:
        response = post(url, **kwargs)
    except BaseException as exc:
        _write_json(attempt / "error.json", {
            "type": type(exc).__name__, "finished": time.time(),
            "detail": "Exception text omitted because transport errors may contain credentials.",
        })
        raise
    else:
        content = response.content
        _write_json(attempt / "response.json", {
            "status_code": response.status_code, "body_text": response.text,
            "body_base64": base64.b64encode(content).decode("ascii"),
            "finished": time.time(),
        })
        from NIST_SRD46_db_agent.general_db_query_engine.general_first_principle_API_call_reconstruct import (
            AuthorizationInterrupted, authorization_denied,
        )
        if authorization_denied(response.status_code, response.text):
            scope_id = current_scope_id() or os.environ.get(MCP_SCOPE_ENV, "").strip()
            receipt = {
                "schema": "srd46-query-mcp-authorization-denial/v1",
                "scope_id": scope_id,
                "http_status": response.status_code,
                "attempt": attempt.relative_to(directory).as_posix(),
                "request_file": "request.json", "response_file": "response.json",
                "recorded": time.time(),
            }
            _write_json(attempt / "authorization_denied.json", receipt)
            if scope_id:
                # Publish atomically; other concurrent parent tool tasks may
                # observe the marker as soon as this child records the denial.
                marker = directory / f"mcp_authorization_denied_{scope_id}.json"
                temporary = attempt / "authorization_marker.tmp"
                _write_json(temporary, receipt)
                _replace(temporary, marker)
            raise AuthorizationInterrupted(
                "Authorization denied by embedded query MCP transport; raw response saved"
            )
        return response


__all__ = ["MCP_ARTIFACT_ENV", "MCP_SCOPE_ENV", "current_artifact_dir", "current_scope_id", "mcp_stderr_target",
           "raise_if_mcp_authorization_denied",
           "query_artifact_scope", "record_event", "record_state", "record_http_post"]
