"""
anthropic_argo_adapter.py — drop-in Anthropic backend for ``ArgoClient``.
========================================================================

Purpose
-------
Let the existing SRD46/Argo engine run against the **direct Anthropic
Messages API** instead of the ANL ``argoapi`` ``/chat/`` endpoint, with
**zero changes** to :mod:`argo_client_caller`, the ReAct loop, the history
recorder, or any agent config.

Ported 2026-09-05 from the ThermoML twin
(``NIST_ThermoML_agents/general_db_query_engine/general_argo_engine_helpers/
anthropic_argo_adapter.py``) with three SRD46-specific deltas:

1. ``_default_session_resolver`` uses this engine generation's module-level
   ``history_recorder`` singleton (no ``get_active_history_recorder`` here).
2. ``install(extra_modules=...)`` — SRD46 has a *second* HTTP seam: the
   standalone query agent's ``NIST_SRD46_query_agent/argo_client.py`` owns
   its own ``requests`` reference.  The bootstrap passes that module here so
   both agents route through the same shim.
3. The shim's ``post()`` also accepts ``data=<json str>`` payloads (the
   query agent's LangChain path posts that way) and defaults ``max_tokens``
   when a payload omits it (Anthropic requires the field).

How it stays 1-1 with the Argo transcript
-----------------------------------------
:meth:`ArgoClient.call` records every LLM call to the run-history session
event log via ``begin_argo_event`` / ``end_argo_event`` (the "Argo
transcript": model / tier / system_chars / prompt_chars / response_chars /
elapsed_s / attempts / verbatim text / status).  This adapter intercepts
only the innermost ``requests.post(...)`` HTTP boundary, so **the entire
``call()`` body — payload build, retry ladder, stop-token fix-up, stats,
and both transcript hooks — executes unchanged**.  The transcript row is
therefore identical to an Argo-backed run except for the model-generated
text itself, and the recorded ``model`` label stays the Argo name
(``claudeopus47``), because the intercept happens *after* the payload
(and its transcript event) are built.

Translation (Argo payload ⇄ Anthropic Messages)
-----------------------------------------------
Argo request              →  Anthropic ``/v1/messages`` request
  user                    →  (dropped; Anthropic auth is the API key)
  model  "claudeopus47"   →  model  "claude-opus-4-7"  (see MODEL_MAP)
  system <str>            →  system <str>              (omitted if empty)
  prompt ["...", ...]     →  messages=[{role:user, content:"\n".join(...)}]
  stop   ["</tool_call>"] →  stop_sequences (empty/blank entries dropped)
  temperature <float>     →  DROPPED (deprecated 400 on claude-opus-4-7+)
  max_tokens <int>        →  max_tokens (defaulted if absent)
  top_p (non-claude only) →  top_p

Anthropic response        →  Argo response body
  content[*].text (join)  →  response  <str>
  usage.input_tokens      →  usage.prompt_tokens
  usage.output_tokens     →  usage.completion_tokens
  input+output            →  usage.total_tokens

The Anthropic API is inherently **turn-based, tool-less (no ``tools`` sent),
and un-cached** here — matching the requested "identical setting".

Usage
-----
::

    import anthropic_argo_adapter as adapter
    adapter.install()                 # reads ANTHROPIC_API_KEY from env
    ...                               # run agents exactly as before
    adapter.uninstall()               # restore the real requests module

Passive capture (automatic, inspection-only)
--------------------------------------------
Every call made inside an active agent session is recorded automatically to
``<session run dir>/anthropic_raw_capture.jsonl`` — the **complete raw
Anthropic response** (full text content, ``usage`` incl. any cache counters,
``stop_reason``, ``model`` id) together with the response headers and the
translated request.  Pass ``install(capture_path=...)`` or set the
``ANTHROPIC_ADAPTER_CAPTURE`` env var to also capture out-of-session calls
to a fallback ``.jsonl`` file (or directory).  This is a read-only
side-channel: it never changes what ``ArgoClient`` receives, so agent
behavior is identical whether or not capture is on.  The request auth
headers (and therefore the API key) are never recorded.

The API key is read from the ``ANTHROPIC_API_KEY`` environment variable and
is never written to disk or logged.
"""

from __future__ import annotations

import datetime as _dt
import itertools
import json as _json
import logging
import os
import sys
import threading
import time as _time
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Iterable

import requests as _real_requests

from . import argo_client_caller as _argo_module

log = logging.getLogger("anthropic-argo-adapter")

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

#: Argo model name → Anthropic model id.  SRD46 analysis configs use
#: ``claudeopus47``; the rest are provided for completeness.  Unknown
#: names (e.g. the query agent's ``gpt54``/``gpt5``) fall back to
#: :data:`DEFAULT_ANTHROPIC_MODEL` with a warning.
MODEL_MAP: dict[str, str] = {
    "claudeopus46":   "claude-opus-4-6",
    "claudeopus47":   "claude-opus-4-7",
    "claudeopus48":   "claude-opus-4-8",
    "claudeopus45":   "claude-opus-4-5-20251101",
    "claudeopus5":    "claude-opus-5",
    "claudesonnet46": "claude-sonnet-4-6",
    "claudesonnet45": "claude-sonnet-4-5-20250929",
    "claudesonnet5":  "claude-sonnet-5",
    "claudehaiku45":  "claude-haiku-4-5-20251001",
    "claudefable5":   "claude-fable-5",
    "claudefable51":  "claude-fable-5-1",
}
DEFAULT_ANTHROPIC_MODEL = "claude-opus-4-6"

#: Anthropic requires ``max_tokens``; used when an (older-client) payload
#: omits it.
DEFAULT_MAX_TOKENS = 8192


def map_model(argo_model: str, model_map: dict[str, str] | None = None) -> str:
    """Resolve an Argo model name to an Anthropic model id."""
    m = (model_map or MODEL_MAP)
    key = (argo_model or "").strip().lower()
    if key in m:
        return m[key]
    log.warning("Unknown Argo model %r → defaulting to %s",
                argo_model, DEFAULT_ANTHROPIC_MODEL)
    return DEFAULT_ANTHROPIC_MODEL


# ── pure translation: Argo payload → Anthropic request ──────────────────

def argo_payload_to_anthropic(
    payload: dict[str, Any],
    *,
    model_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Translate an Argo ``/chat/`` payload into an Anthropic Messages
    request.  Pure function — no I/O, no key handling."""
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dict")

    prompt = payload.get("prompt", "")
    if isinstance(prompt, list):
        content = "\n".join(str(p) for p in prompt)
    else:
        content = str(prompt)

    max_tokens = payload.get("max_tokens")
    req: dict[str, Any] = {
        "model": map_model(payload.get("model", ""), model_map),
        "max_tokens": int(max_tokens) if max_tokens is not None else DEFAULT_MAX_TOKENS,
        "messages": [{"role": "user", "content": content}],
    }

    system = payload.get("system", "")
    if isinstance(system, str) and system.strip():
        req["system"] = system

    # temperature is NOT forwarded: Anthropic rejects it as deprecated on
    # claude-opus-4-7+ (400 invalid_request_error), so the Argo value is
    # dropped for every mapped model.

    stop = payload.get("stop", [])
    if isinstance(stop, list):
        seqs = [s for s in stop if isinstance(s, str) and s.strip()]
        if seqs:
            req["stop_sequences"] = seqs

    # top_p is only present for non-Claude Argo models; forward if given.
    if "top_p" in payload and payload["top_p"] is not None:
        req["top_p"] = float(payload["top_p"])

    return req


# ── pure translation: Anthropic response → Argo body ────────────────────

def anthropic_body_to_argo(anthropic_json: dict[str, Any]) -> dict[str, Any]:
    """Translate an Anthropic Messages response into an Argo ``/chat/``
    response body (``{"response": str, "usage": {...}}``)."""
    if not isinstance(anthropic_json, dict):
        raise TypeError("anthropic_json must be a dict")

    blocks = anthropic_json.get("content", []) or []
    text = "".join(
        b.get("text", "")
        for b in blocks
        if isinstance(b, dict) and b.get("type") == "text"
    )

    body: dict[str, Any] = {"response": text}

    usage = anthropic_json.get("usage")
    if isinstance(usage, dict):
        pt = usage.get("input_tokens")
        ct = usage.get("output_tokens")
        body["usage"] = {
            "prompt_tokens": pt,
            "completion_tokens": ct,
            "total_tokens": (pt + ct) if isinstance(pt, int) and isinstance(ct, int) else None,
        }
    return body


# ── fake requests.Response returned to ArgoClient.call() ────────────────

class _FakeResponse:
    """Minimal stand-in for ``requests.Response`` exposing exactly the
    surface :meth:`ArgoClient.call` touches: ``status_code``, ``text``,
    ``json()`` and ``raise_for_status()``."""

    def __init__(self, status_code: int, text: str, body: dict | None):
        self.status_code = status_code
        self.text = text
        self._body = body

    def json(self) -> Any:
        if self._body is None:
            return _json.loads(self.text)
        return self._body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise _real_requests.HTTPError(
                f"{self.status_code} error: {self.text[:300]}")


# ── passive capture of raw Anthropic exchanges (inspection side-channel) ─
#
# ALWAYS ON for calls made inside an active agent session: each record is
# appended to ``<session run dir>/anthropic_raw_capture.jsonl``.  A path via
# install(capture_path=...) or the ANTHROPIC_ADAPTER_CAPTURE env var only
# adds a fallback file for out-of-session calls (no session dir resolvable).
# Records one JSON object per LLM call (translated request, HTTP status,
# response headers, and the *complete* raw Anthropic response body) to a
# .jsonl file.  Purely observational: wrapped so a capture failure can never
# disturb the ArgoClient call path, and the request auth headers (API key)
# are never recorded.

_capture_path: Path | None = None
_capture_counter = itertools.count(1)
_capture_lock = threading.Lock()
_capture_resolver: Callable[[], Path | None] | None = None


def set_capture_resolver(fn: Callable[[], Path | None] | None) -> None:
    """Override the per-call capture routing (None restores the default:
    the active agent session's run directory)."""
    global _capture_resolver
    _capture_resolver = fn


def _default_session_resolver() -> Path | None:
    """Directory of the active agent session, if any — routes each captured
    call into the run folder it belongs to.

    Two sources, in order: the query-agent generation's module-level
    ``history_recorder`` singleton (thread-local run state), then the
    ``SRD46_ANALYSIS_SESSION_DIR`` env var published by
    ``SRD46_analysis_run`` (the analysis agent never starts the recorder)."""
    try:
        from ..general_hooks_management_helpers.general_context_hooks.history_tracking_hooks import (
            history_recorder,
        )
        out = getattr(history_recorder._state(), "out_path", None)
        if out:
            return Path(out).parent
    except Exception:
        pass
    sess = os.environ.get("SRD46_ANALYSIS_SESSION_DIR")
    return Path(sess) if sess else None


def enable_capture(path: str | Path) -> Path:
    """Turn on passive capture.  A ``path`` ending in ``.jsonl`` is used as
    the output file; otherwise it is treated as a directory and a
    timestamped ``anthropic_capture_*.jsonl`` is created inside it."""
    global _capture_path, _capture_counter
    p = Path(path)
    if p.suffix.lower() == ".jsonl":
        p.parent.mkdir(parents=True, exist_ok=True)
    else:
        p.mkdir(parents=True, exist_ok=True)
        p = p / f"anthropic_capture_{_dt.datetime.now():%Y%m%d_%H%M%S}.jsonl"
    _capture_path = p
    _capture_counter = itertools.count(1)
    log.info("Anthropic passive capture ENABLED → %s", p)
    return p


def disable_capture() -> None:
    """Turn off passive capture (leaves any existing file in place)."""
    global _capture_path
    _capture_path = None


def get_capture_path() -> Path | None:
    """Current capture file, or ``None`` when capture is disabled."""
    return _capture_path


def _extract_text(raw_body: Any) -> str:
    if not isinstance(raw_body, dict):
        return ""
    return "".join(
        b.get("text", "")
        for b in (raw_body.get("content") or [])
        if isinstance(b, dict) and b.get("type") == "text"
    )


def _capture_exchange(*, argo_payload: dict, anthropic_req: dict,
                      status_code: int, headers: Any, raw_body: Any,
                      raw_text: str, elapsed_s: float) -> None:
    """Append one raw exchange to the capture file.  Never raises.

    Routing: when an agent session is active in this context, the record
    goes to ``<session run dir>/anthropic_raw_capture.jsonl`` (no
    configuration needed); otherwise it falls back to the path configured
    via :func:`enable_capture`, or is skipped if none is set."""
    base = _capture_path
    try:
        resolver = _capture_resolver or _default_session_resolver
        try:
            session_dir = resolver()
        except Exception:
            session_dir = None
        path = (Path(session_dir) / "anthropic_raw_capture.jsonl"
                if session_dir else base)
        if path is None:
            return
        prompt = argo_payload.get("prompt", "")
        prompt_chars = (sum(len(str(p)) for p in prompt)
                        if isinstance(prompt, list) else len(str(prompt)))
        system = argo_payload.get("system", "")
        record: dict[str, Any] = {
            "seq": None,
            "ts": _dt.datetime.now().isoformat(timespec="milliseconds"),
            "elapsed_s": round(float(elapsed_s), 3),
            "argo_model": argo_payload.get("model"),
            "anthropic_model": anthropic_req.get("model"),
            "status_code": status_code,
            "system_chars": len(system) if isinstance(system, str) else 0,
            "prompt_chars": prompt_chars,
            "response_chars": len(_extract_text(raw_body)),
            "request": anthropic_req,
            "response_headers": dict(headers) if headers else {},
            "response": raw_body if raw_body is not None else {"_raw_text": raw_text},
        }
        with _capture_lock:
            record["seq"] = next(_capture_counter)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(_json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:  # passive: must never disturb the call path
        log.warning("passive capture failed (ignored): %s", exc)


# ── requests-module shim that redirects Argo POSTs to Anthropic ─────────

class _AnthropicRequestsShim:
    """Drop-in replacement for the ``requests`` module *as used by*
    :mod:`argo_client_caller` (and the query agent's ``argo_client``) —
    provides ``post`` plus the exception classes referenced in the
    callers' except-ladders."""

    # ArgoClient catches these three names off the module.
    ReadTimeout = _real_requests.ReadTimeout
    ConnectionError = _real_requests.ConnectionError
    RequestException = _real_requests.RequestException
    # Older callers may reach exceptions via ``requests.exceptions.*``.
    exceptions = _real_requests.exceptions

    def __init__(self, api_key: str, model_map: dict[str, str] | None = None):
        if not api_key:
            raise ValueError("api_key must be non-empty")
        self._api_key = api_key
        self._model_map = model_map or MODEL_MAP

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

    def post(self, url, headers=None, json=None, data=None, timeout=None, **_kw):
        """Intercept the Argo POST, call Anthropic, return an Argo-shaped
        :class:`_FakeResponse`.  Real ``requests`` exceptions propagate so
        ArgoClient's timeout/connection retry ladder still works.

        Accepts the payload either as ``json=<dict>`` (engine + query
        ``_post_argo``) or ``data=<json str>`` (query LangChain path)."""
        if isinstance(json, dict):
            argo_payload = json
        elif isinstance(data, (str, bytes)):
            try:
                argo_payload = _json.loads(data)
            except Exception:
                argo_payload = {}
            if not isinstance(argo_payload, dict):
                argo_payload = {}
        else:
            argo_payload = {}
        anthropic_req = argo_payload_to_anthropic(argo_payload, model_map=self._model_map)

        t0 = _time.perf_counter()
        r = _real_requests.post(
            ANTHROPIC_URL, headers=self._headers(),
            json=anthropic_req, timeout=timeout,
        )
        elapsed = _time.perf_counter() - t0

        status = r.status_code
        try:
            raw_body = r.json()
        except Exception:
            raw_body = None

        # Passive side-channel: record the full raw exchange, then continue
        # exactly as before.  Capture reads r only; it changes nothing the
        # caller sees.
        _capture_exchange(
            argo_payload=argo_payload, anthropic_req=anthropic_req,
            status_code=status, headers=r.headers,
            raw_body=raw_body, raw_text=r.text, elapsed_s=elapsed,
        )

        if status == 200 and isinstance(raw_body, dict):
            argo_body = anthropic_body_to_argo(raw_body)
            return _FakeResponse(200, _json.dumps(argo_body), argo_body)

        # Remap Anthropic transient-overload codes onto ArgoClient's 500
        # retry/backoff branch; pass auth/rate-limit codes through verbatim
        # so its fast-fail (401/403) and 429-backoff paths trigger as designed.
        if status in (503, 529):
            status = 500
        return _FakeResponse(status, r.text, None)


# ── install / uninstall ─────────────────────────────────────────────────

# module → its real ``requests`` reference while the shim is installed
_installed_originals: dict[ModuleType, Any] = {}


def install(*, api_key: str | None = None,
            model_map: dict[str, str] | None = None,
            capture_path: str | Path | None = None,
            extra_modules: Iterable[ModuleType] | None = None,
            ) -> _AnthropicRequestsShim:
    """Redirect ``ArgoClient``'s HTTP calls to the Anthropic Messages API.

    Reads the key from ``ANTHROPIC_API_KEY`` if ``api_key`` is omitted.
    Idempotent-safe: records each real module reference once so
    :func:`uninstall` restores them.

    ``extra_modules`` — additional modules whose module-level ``requests``
    should be replaced by the same shim (SRD46: the standalone query
    agent's ``argo_client``).

    If ``capture_path`` is given (or the ``ANTHROPIC_ADAPTER_CAPTURE`` env
    var is set), passive capture of every raw Anthropic response is enabled
    via :func:`enable_capture` — inspection only, no behavior change.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set (and no api_key passed). "
            "Set it in the environment before install().")
    shim = _AnthropicRequestsShim(key, model_map)
    for mod in (_argo_module, *(extra_modules or ())):
        if mod not in _installed_originals:
            _installed_originals[mod] = mod.requests
        mod.requests = shim
    # Dual-import sweep: deep LC modules import the engine via the short
    # "general_db_query_engine..." path, creating a SECOND module object
    # for the same file that still holds the real ``requests`` (its calls
    # would silently hit the real Argo endpoint). Patch every sys.modules
    # entry whose leaf is an argo client, whatever package alias it lives
    # under. Callers must re-run install() after importing agent code.
    for _name, _mod in list(sys.modules.items()):
        if _mod is None:
            continue
        if _name.rsplit(".", 1)[-1] not in ("argo_client_caller", "argo_client"):
            continue
        _r = getattr(_mod, "requests", None)
        if _r is None or isinstance(_r, _AnthropicRequestsShim):
            continue
        if _mod not in _installed_originals:
            _installed_originals[_mod] = _r
        _mod.requests = shim
    cap = capture_path if capture_path is not None else os.environ.get("ANTHROPIC_ADAPTER_CAPTURE")
    if cap:
        enable_capture(cap)
    log.info("Anthropic adapter installed on %d module(s) (ArgoClient → %s).",
             len(_installed_originals), ANTHROPIC_URL)
    return shim


def uninstall() -> None:
    """Restore the real ``requests`` module in every patched module."""
    global _installed_originals
    for mod, original in _installed_originals.items():
        mod.requests = original
    if _installed_originals:
        _installed_originals = {}
        log.info("Anthropic adapter uninstalled (real requests restored).")


def is_installed() -> bool:
    """True while :mod:`argo_client_caller` is routed through the adapter."""
    return isinstance(getattr(_argo_module, "requests", None), _AnthropicRequestsShim)
