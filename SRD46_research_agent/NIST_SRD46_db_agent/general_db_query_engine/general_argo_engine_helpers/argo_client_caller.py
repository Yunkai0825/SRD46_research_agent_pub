"""
ArgoClient — dataclass-based LLM caller for the Argo API.
==========================================================

Uses the Argo ``/chat/`` turn-based endpoint with ``requests.post()``.
Provides both synchronous ``call()`` and asynchronous ``acall()``
methods.  The async variant uses ``asyncio.to_thread()`` to wrap the
synchronous call, keeping the implementation simple and testable.

Factory constructors
--------------------
- ``ArgoClient.with_tier(tier, **overrides)`` — generic tier label.
- ``ArgoClient.for_verdict()``  — post-job quality review client.
- ``ArgoClient.for_compactor()`` — LLM compaction sub-agent client.
- ``ArgoClient.for_planner()``  — strategy-planning client.

Per-agent tier constructors (``for_l0``, ``for_l1``, ``for_l2``) live
in each agent's ``argo_engine_subagent_helpers/argo_client.py`` as
``QueryClient`` / ``AnalysisClient`` subclasses.

Usage
-----
::

    from argo_engine_helpers import ArgoClient

    # Direct construction with overrides
    client = ArgoClient(model="gpt5", temperature=0.1)

    # Synchronous (blocking)
    response = client.call(prompt, system_prompt)

    # Asynchronous (for parallel L2 dispatch)
    response = await client.acall(prompt, system_prompt)

    # Via factory method — reads active EngineConfig
    verdict_client = ArgoClient.for_verdict()
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import requests

from .engine_config import get_config
from ..general_first_principle_API_call_reconstruct import http_post as _reconstruction_post
from ..general_first_principle_API_call_reconstruct import (
    ArgoAccessRevokedError,
    access_revoked_notice,
)
from ..general_hooks_management_helpers.general_context_hooks.stats_references_tracking_hooks import (
    get_active_recorder as _get_stats_recorder,
)
from ..general_text_context_marker_catalog import MARKERS
from .engine_tool_interface_helpers.tool_call_parser import (
    _open_call_start,
    _try_parse_tool_block,
)

log = logging.getLogger("ArgoClient")

# The Argo username a browser run bills (output_paths.argo_api_user_scope, bound
# per run by the run's launcher) wins over the client's own ``api_user`` at call
# time, so two concurrent runs of different users in one process each bill their
# own; without the master (command line) nothing is bound and the field decides.
try:
    from output_paths import argo_api_user as _bound_argo_api_user
except Exception as _exc:  # noqa: BLE001 -- standalone: no master on sys.path (ImportError), else broken
    if not isinstance(_exc, ImportError):
        log.warning("output_paths unavailable (%s): Argo calls bill the client's configured user", _exc)

    def _bound_argo_api_user():
        return None


class ArgoPromptTooLargeError(RuntimeError):
    """Argo rejected a request because its prompt/context was too large.

    This exception is deliberately distinct from transient transport errors so
    a caller may reduce only its optional context and retry once, without
    treating authentication, rate limiting, or connectivity failures as a
    reason to discard evidence.
    """

    def __init__(
        self,
        *,
        status_code: int,
        response_text: str,
        model: str,
        api_url: str,
    ) -> None:
        self.status_code = int(status_code)
        self.response_text = str(response_text)
        self.model = str(model)
        self.api_url = str(api_url)
        preview = " ".join(self.response_text.split())[:500]
        super().__init__(
            f"Argo prompt/context too large (HTTP {self.status_code}) for "
            f"model {self.model!r} at {self.api_url}: {preview or '(empty response)'}"
        )


class ArgoTransportError(RuntimeError):
    """The gateway returned no usable reply for every attempt the client allows.

    Raised where the retry loop gives up: HTTP 5xx, upstream 429, timeouts,
    connection errors.  An HTTP-200 envelope without model text is not one:
    it goes back to the loop as an empty reply, and the loop re-asks.  Distinct
    from ``ArgoAccessRevokedError`` (a block that no retry can clear) and
    from any agent or parser outcome: the request was never answered, so a
    caller that budgets agent corrections should not spend one on it and may
    wait longer than the client's own back-off before sending the same
    request again (a gateway outage of several minutes otherwise exhausts
    such a budget in a few seconds of wall time). This ``RuntimeError``
    reports the attempt count and the final transport error.
    """

    def __init__(self, *, attempts: int, last_error: str) -> None:
        self.attempts = int(attempts)
        self.last_error = str(last_error)
        super().__init__(
            f"Argo API failed after {self.attempts} attempts: {self.last_error}"
        )


def _model_wrote_nothing(body) -> dict | None:
    """Usage facts of an empty reply when the envelope reports them, else ``None``.

    An HTTP-200 envelope whose ``usage`` reports a positive completion count
    (OpenAI ``completion_tokens``, Anthropic ``output_tokens``) carried a
    completion without text, for example a reasoning-only reply.  ``None``
    means the envelope reports no model output (Argo's native envelopes
    carry no usage at all); the reply is handed on either way, the loop's
    host notice then names no counts.
    """
    usage = body.get("usage") if isinstance(body, dict) else None
    if not isinstance(usage, dict):
        return None
    completion = usage.get("completion_tokens", usage.get("output_tokens"))
    if isinstance(completion, bool) or not isinstance(completion, (int, float)) or completion <= 0:
        return None
    details = usage.get("completion_tokens_details")
    reasoning = details.get("reasoning_tokens") if isinstance(details, dict) else None
    return {
        "completion_tokens": int(completion),
        "reasoning_tokens": int(reasoning) if isinstance(reasoning, (int, float)) else None,
        "prompt_tokens": usage.get("prompt_tokens", usage.get("input_tokens")),
    }


# Provider stop reasons (Anthropic ``stop_reason``, OpenAI ``finish_reason``)
# that mean the reply reached its output-token limit, and those that mean
# the provider stopped it (a refusal or content filter).
_LIMIT_STOP_REASONS = frozenset({"max_tokens", "length", "max_output_tokens"})
# A wait barrier that ends the reply (trailing whitespace allowed).
_TRAILING_WAIT_RE = re.compile(
    r"\s*(?:" + MARKERS.wait_re.pattern + r")\s*$", MARKERS.wait_re.flags,
)
_REFUSAL_STOP_REASONS = frozenset({"refusal", "content_filter"})


def _provider_stop(body, max_tokens: int) -> dict:
    """How the envelope says the reply ended.

    ``limit_reached`` comes from the stop reason when the envelope names
    one, else from ``usage`` (completion tokens at or above the requested
    ``max_tokens``); an envelope that reports neither (Argo's native
    envelopes) never counts as having reached the limit.  ``refused`` is
    a refusal or content-filter stop.
    """
    reason = None
    completion = None
    if isinstance(body, dict):
        for key in ("stop_reason", "finish_reason"):
            value = body.get(key)
            if isinstance(value, str) and value.strip():
                reason = value.strip().lower()
                break
        usage = body.get("usage")
        if isinstance(usage, dict):
            value = usage.get("completion_tokens", usage.get("output_tokens"))
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                completion = int(value)
    if reason is not None:
        limit_reached = reason in _LIMIT_STOP_REASONS
    else:
        limit_reached = completion is not None and completion >= max_tokens
    return {
        "stop_reason": reason,
        "completion_tokens": completion,
        "max_tokens": max_tokens,
        "limit_reached": limit_reached,
        "refused": reason in _REFUSAL_STOP_REASONS,
    }


# HTTP 400 is overloaded by the Argo service, so do not classify it from a
# generic word such as "token" or "input" alone.  These phrases each state an
# actual size/length overflow.  HTTP 413 is unambiguous and is handled
# independently in ``_is_prompt_too_large_response``.
_PROMPT_TOO_LARGE_400_MARKERS = (
    "context_length_exceeded",
    "context length exceeded",
    "context window exceeded",
    "maximum context length",
    "max context length",
    "prompt is too long",
    "prompt too long",
    "prompt is too large",
    "prompt too large",
    "input is too long",
    "input too long",
    "input is too large",
    "input too large",
    "payload is too large",
    "payload too large",
    "request entity too large",
    "too many input tokens",
    "too many tokens",
    "input token limit exceeded",
    "token limit exceeded",
    "exceeds the token limit",
    "exceeded the token limit",
    "input tokens exceed",
)


def _is_prompt_too_large_response(status_code: int, response_text: str) -> bool:
    """Return whether an HTTP response clearly reports prompt-size overflow."""

    if int(status_code) == 413:
        return True
    if int(status_code) != 400:
        return False
    normalized = " ".join(str(response_text or "").lower().split())
    return any(marker in normalized for marker in _PROMPT_TOO_LARGE_400_MARKERS)


# ── Best-effort token tally bridge to the master browser (optional) ──────────
_MASTER_RT = None
_MASTER_RT_TRIED = False


def _record_master_tokens(agent: str, body, *, input_chars: int, output_chars: int) -> None:
    """Forward an Argo call's usage/char counts to the shared master tracker.

    No-op when the master runtime is not importable (standalone agent runs).
    """
    global _MASTER_RT, _MASTER_RT_TRIED
    if not _MASTER_RT_TRIED:
        _MASTER_RT_TRIED = True
        try:
            import master_runtime as _rt  # type: ignore
            _MASTER_RT = _rt
        except Exception:
            _MASTER_RT = None
    if _MASTER_RT is None:
        return
    usage = body.get("usage") if isinstance(body, dict) else None
    pt = ct = tt = None
    if isinstance(usage, dict):
        pt = usage.get("prompt_tokens")
        ct = usage.get("completion_tokens")
        tt = usage.get("total_tokens")
    try:
        _MASTER_RT.record_tokens(
            agent, prompt_tokens=pt, completion_tokens=ct, total_tokens=tt,
            input_chars=input_chars, output_chars=output_chars,
        )
    except Exception:
        pass


# A line that is exactly a heading of the engine's own transcript rendering
# (react_loop renders memory as "## User" / "## Assistant" sections).  A
# model turn can never legitimately contain one: it marks the start of a
# continuation the model wrote for the host (see _cut_runaway_reply).
_HOST_HEADING_RE = re.compile(r"^## (?:User|Assistant)[ \t]*\r?$", re.MULTILINE)


@dataclass
class ArgoClient:
    """Dataclass wrapping a single LLM caller configuration.

    Each agent layer (L0 orchestrator, L1 worker, L2 evaluator, verdict)
    creates its own ``ArgoClient`` with the appropriate model, temperature,
    and token budget.
    """

    model: str = field(default_factory=lambda: get_config().MODEL)
    temperature: float = field(default_factory=lambda: get_config().TEMPERATURE)
    top_p: float = field(default_factory=lambda: get_config().TOP_P)
    max_tokens: int = field(default_factory=lambda: get_config().MAX_TOKENS)
    stop: list[str] = field(default_factory=lambda: [MARKERS.tool_call.close])
    max_retries: int = 5
    retry_backoff: float = 2.0
    http_timeout: int = field(default_factory=lambda: get_config().HTTP_TIMEOUT)
    api_url: str = field(default_factory=lambda: get_config().API_URL)
    api_user: str = field(default_factory=lambda: get_config().API_USER)
    _tier: str = ""   # stats-only label (e.g. "L0-main", "L1-subagent")
    # Close a tool call the model left open before its trailing ``<wait/>``
    # (``_fix_stop_token``).  Off: the call reaches the loop's parser
    # unclosed and the model is told it was not closed.
    close_call_before_wait: bool = True
    # Record of the last reply cut by ``_cut_runaway_reply`` (None when the
    # last reply was returned whole); diagnostic only, never sent anywhere.
    last_reply_cut: dict | None = field(default=None, init=False, repr=False, compare=False)
    # Record of the last empty reply the model itself produced (an HTTP-200
    # envelope whose usage shows completion tokens but whose text is empty,
    # e.g. a reasoning-only completion); None after any reply with text.
    # The loop reads it for its host notice; diagnostic otherwise.
    last_empty_reply: dict | None = field(default=None, init=False, repr=False, compare=False)
    # Record of the last reply that reached the provider's output limit
    # inside an incomplete tool call (see ``_unclosed_tool_call`` and
    # ``_provider_stop``); None otherwise, including for a complete but
    # malformed call.  The returned text is unchanged; the ReAct loop
    # reads the record to re-ask such a reply.
    last_reply_unclosed: dict | None = field(default=None, init=False, repr=False, compare=False)
    # Record of the last reply the provider stopped with a refusal or
    # content-filter stop reason, with or without text; None otherwise.
    # The ReAct loop reads it to re-ask such a reply.
    last_reply_refused: dict | None = field(default=None, init=False, repr=False, compare=False)
    # Record of the last reply with text that reached the provider's output
    # limit outside a tool call (a prose answer stopped mid-way) and was not
    # shortened by ``_cut_runaway_reply``; None otherwise.  The ReAct loop
    # reads it to have a final answer continued.
    last_reply_limited: dict | None = field(default=None, init=False, repr=False, compare=False)

    @property
    def billed_api_user(self) -> str:
        """The Argo username this call bills: the run's bound user (output_paths.
        argo_api_user_scope), else the client's own ``api_user``."""
        return _bound_argo_api_user() or self.api_user

    # ── payload builder ──────────────────────────────────────

    def _build_payload(
        self,
        prompt: str,
        system: str,
        *,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        _model = model or self.model
        _stop = stop if stop is not None else self.stop
        _max_tokens = max_tokens or self.max_tokens

        payload: dict[str, Any] = {
            "user":        self.billed_api_user,
            "model":       _model,
            "system":      system,
            "prompt":      [prompt],
            "stop":        _stop,
            "temperature": self.temperature,
            "max_tokens":  _max_tokens,
        }
        if not get_config().is_claude_model(_model):
            payload["top_p"] = self.top_p
        return payload

    @staticmethod
    def _fix_stop_token(text: str, close_before_wait: bool = True) -> str:
        """Re-append </tool_call> if it was stripped by the stop sequence.

        A call the model left open and followed with its trailing
        ``<wait/>`` is closed before that barrier when
        ``close_before_wait`` is on: the loop's parser reads only what
        precedes the first barrier, so a tag appended after it would leave
        the call unread.
        """
        if close_before_wait:
            start, masked = _open_call_start(text)
            if start >= 0 and masked.find(MARKERS.tool_call.close, start) < 0:
                wait = _TRAILING_WAIT_RE.search(text, start)
                if wait is not None:
                    log.info("<< tool call left open before <wait/>; closed it before the barrier")
                    return text[:wait.start()] + MARKERS.tool_call.close + text[wait.start():]
        if MARKERS.tool_call.open in text and MARKERS.tool_call.close not in text:
            text += MARKERS.tool_call.close
        return text

    @staticmethod
    def _unclosed_tool_call(text: str) -> dict[str, Any] | None:
        """Record of a reply that ends inside an incomplete tool call, else None.

        The last ``<tool_call>`` tag outside ``<reasoning>`` blocks that opens
        a call body (the reply ends right after it, or a ``{`` or a ``name(``
        follows it) has no closing tag after it, and the loop's parser cannot
        parse its body; a tag only mentioned in reasoning or prose opens no
        call.  A gateway that applies the stop sequence strips the closing tag
        of every call: a complete call still parses, a malformed one looks the
        same as a cut one, so ``call`` counts the record as a cut only when
        the provider reports the output limit.  Read before
        ``_fix_stop_token`` closes the block.  Returns
        ``{"raw_chars": len(text), "reason": <the parser's failure reason>}``.
        """
        open_tag = MARKERS.tool_call.open
        start, masked = _open_call_start(text)
        if start < 0 or masked.find(MARKERS.tool_call.close, start) >= 0:
            return None
        parsed, reason = _try_parse_tool_block(text[start + len(open_tag):])
        if parsed is not None:
            return None
        return {"raw_chars": len(text), "reason": reason}

    @staticmethod
    def _cut_runaway_reply(text: str) -> tuple[str, dict[str, Any] | None]:
        """Cut a reply that ran past the end of the model's turn.

        When Argo applies no stop sequence, the model can generate up to
        ``max_tokens`` and, after its real tool calls, write the host's side
        of the conversation itself (``<wait/>``, then ``## User`` / ``<tool_result>`` blocks with
        invented results, then further ``## Assistant`` turns).  The turn
        ends at the first wait barrier, which keeps a whole batch of tool
        calls (the ReAct loop discards what follows the barrier anyway);
        unless a host-only marker comes first: a ``<tool_result>`` tag or a
        bare ``## User`` / ``## Assistant`` heading line, which no model turn
        can legitimately contain, ends the turn right there (a fabricated
        turn may carry its own barrier and tool calls, so the barrier alone
        is not trusted).  Markers and barriers are searched outside tool-call
        bodies only.  A reply a gateway already cut at the stop sequence, a
        prose answer, a reasoning-only reply and a reply that would be cut to
        nothing pass unchanged.

        Returns ``(kept_text, record)``; ``record`` is None when nothing was
        cut, else ``{"cut_at": "wait" | "host_marker", "kept_chars",
        "dropped_chars", "dropped_head"}``.
        """
        if not text:
            return text, None
        # Blank out complete tool-call blocks (offsets preserved) so that
        # quoted excerpts inside arguments can never be taken for markers.
        masked = MARKERS.any_tool_call_re.sub(lambda m: " " * len(m.group(0)), text)
        hits = []
        pos = masked.find(MARKERS.tool_result.open)
        if pos >= 0:
            hits.append(pos)
        heading = _HOST_HEADING_RE.search(masked)
        if heading is not None:
            hits.append(heading.start())
        marker = min(hits) if hits else None
        wait = MARKERS.wait_re.search(masked)
        if wait is not None and (marker is None or wait.end() <= marker):
            end, cut_at = wait.end(), "wait"
            kept = text[:end]
        elif marker is not None:
            end, cut_at = marker, "host_marker"
            kept = text[:end].rstrip()
        else:
            return text, None
        if not text[end:].strip() or not kept.strip():
            return text, None
        return kept, {
            "cut_at": cut_at,
            "kept_chars": len(kept),
            "dropped_chars": len(text) - len(kept),
            "dropped_head": text[len(kept):len(kept) + 120],
        }

    # ── synchronous call (turn-based) ────────────────────────

    def call(
        self,
        prompt: str,
        system: str,
        *,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        model: str | None = None,
    ) -> str:
        """Send a prompt to the Argo API and return the full response.

        Parameters
        ----------
        prompt : str
            The full user/conversation prompt.
        system : str
            System message.
        max_tokens, stop, model : optional
            Per-call overrides.

        Returns
        -------
        str
            The model's complete text response.

        Raises
        ------
        RuntimeError
            If all retry attempts are exhausted.
        """
        payload = self._build_payload(
            prompt, system, max_tokens=max_tokens, stop=stop, model=model,
        )
        _model = payload["model"]
        prompt_len = sum(len(p) for p in payload["prompt"]) if isinstance(payload["prompt"], list) else len(payload["prompt"])
        log.info(
            ">> Argo request: model=%s, system=%d chars, prompt=%d chars, max_tokens=%d",
            _model, len(system), prompt_len, payload["max_tokens"],
        )

        last_err: str | None = None
        for attempt in range(1, self.max_retries + 1):
            t0 = time.time()
            try:
                r = _reconstruction_post(
                    payload,
                    lambda: requests.post(
                        self.api_url,
                        headers=get_config().HEADERS,
                        json=payload,
                        timeout=self.http_timeout,
                    ),
                    transport="argo",
                    request_timeout=self.http_timeout,
                    send_payload=lambda actual: requests.post(
                        self.api_url, headers=get_config().HEADERS,
                        json=actual, timeout=self.http_timeout,
                    ),
                )
                elapsed = time.time() - t0

                if _is_prompt_too_large_response(r.status_code, r.text):
                    # Retrying the identical request cannot succeed.  Surface a
                    # typed, non-transient failure immediately so the owning
                    # layer can selectively reduce optional prompt context.
                    raise ArgoPromptTooLargeError(
                        status_code=r.status_code,
                        response_text=r.text,
                        model=_model,
                        api_url=self.api_url,
                    )

                if r.status_code == 500:
                    log.warning(
                        "[!] API 500 (attempt %d/%d, %.1fs): %s",
                        attempt, self.max_retries, elapsed, r.text[:200],
                    )
                    last_err = f"500: {r.text[:200]}"
                    time.sleep(self.retry_backoff * attempt)
                    continue

                if r.status_code == 429:
                    wait = self.retry_backoff * (2 ** attempt)
                    log.warning(
                        "[!] 429 rate-limited (attempt %d/%d, %.1fs); "
                        "backing off %.0fs",
                        attempt, self.max_retries, elapsed, wait,
                    )
                    last_err = f"429: {r.text[:200]}"
                    time.sleep(wait)
                    continue

                # Authentication / authorization failures are NOT transient —
                # retrying the same credentials cannot succeed. Fail fast with
                # an actionable message instead of burning every retry.
                if r.status_code in (401, 403):
                    raise RuntimeError(
                        f"Argo authentication failed (HTTP {r.status_code}). The ANL argoapi "
                        f"rejected the request for user '{self.billed_api_user}' / model '{_model}' at "
                        f"{self.api_url}. This is an upstream credential/endpoint issue, not a "
                        f"problem with the prompt. Check that the ANL username is correct, you are "
                        f"on the ANL network/VPN, and the endpoint/model are available (override "
                        f"the endpoint with the ARGO_API_URL env var if the dev endpoint is down). "
                        f"Server said: {r.text[:300]}"
                    )

                r.raise_for_status()

                # Argo relays a spent usage allowance as HTTP 200 with the
                # notice in an Anthropic-style content block and no
                # "response" field. This is not transient: raise once,
                # never retry.
                revoked = access_revoked_notice(r.status_code, r.text)
                if revoked is not None:
                    notice, response_id = revoked
                    log.error(
                        "[!] Argo access revoked (envelope id=%s): %s",
                        response_id or "-", notice,
                    )
                    raise ArgoAccessRevokedError(
                        status_code=r.status_code,
                        notice=notice,
                        response_id=response_id,
                        model=_model,
                        api_user=self.billed_api_user,
                    )

                body = r.json()
                text = body.get("response", "")
                if isinstance(text, (dict, list)):
                    text = json.dumps(text)
                elif not isinstance(text, str):
                    # A null or odd-typed "response" is no answer either: it
                    # joins the empty-reply retry below instead of crashing.
                    text = str(text or "")
                text, reply_cut = self._cut_runaway_reply(text)
                stop_info = _provider_stop(body, payload["max_tokens"])
                unclosed = self._unclosed_tool_call(text)
                self.last_reply_unclosed = None
                if unclosed is not None and stop_info["limit_reached"]:
                    self.last_reply_unclosed = {**unclosed, "max_tokens": payload["max_tokens"]}
                elif unclosed is not None:
                    log.info(
                        "<< reply ends inside an unparseable tool call but the "
                        "provider reports no output limit (stop_reason=%s, "
                        "completion_tokens=%s of %d); handled as a malformed call",
                        stop_info["stop_reason"], stop_info["completion_tokens"],
                        payload["max_tokens"],
                    )
                self.last_reply_refused = None
                if stop_info["refused"]:
                    self.last_reply_refused = {
                        "stop_reason": stop_info["stop_reason"],
                        "raw_chars": len(text),
                    }
                    log.warning(
                        "[!] Provider stopped the reply (stop_reason=%s) after "
                        "%d chars", stop_info["stop_reason"], len(text),
                    )
                # A count above the requested cap means the route applied a
                # cap of its own, not this request's.
                _completion = stop_info["completion_tokens"]
                self.last_reply_limited = None
                if (
                    text.strip() and stop_info["limit_reached"] and unclosed is None
                    and reply_cut is None
                    and not (_completion is not None and _completion > payload["max_tokens"])
                ):
                    self.last_reply_limited = {
                        "raw_chars": len(text),
                        "max_tokens": payload["max_tokens"],
                        "completion_tokens": _completion,
                    }
                    log.warning(
                        "[!] Reply reached the output limit (%s of %d tokens) "
                        "after %d chars, outside a tool call",
                        _completion, payload["max_tokens"], len(text),
                    )
                text = self._fix_stop_token(text, self.close_call_before_wait)
                self.last_reply_cut = reply_cut
                self.last_empty_reply = None
                if reply_cut is not None:
                    log.info(
                        "<< reply ran past its %s: kept %d chars, dropped %d chars "
                        "of model-written continuation (Argo applied no stop "
                        "sequence; dropped head: %r)",
                        reply_cut["cut_at"], reply_cut["kept_chars"],
                        reply_cut["dropped_chars"], reply_cut["dropped_head"],
                    )

                # Detect upstream 429 relayed as 200 body text
                if text.lstrip().startswith("Error:") and "429" in text[:300]:
                    log.warning(
                        "[!] Upstream 429 in body (attempt %d/%d): %s",
                        attempt, self.max_retries, text[:200],
                    )
                    last_err = f"Upstream 429: {text[:200]}"
                    time.sleep(self.retry_backoff * attempt * 2)
                    continue

                # An HTTP 200 envelope without model text may contain usage
                # for a reasoning-only completion or an empty "response"
                # without usage. Re-sending the identical request can repeat
                # the empty reply, so return it immediately for the loop to
                # re-ask with a host notice. A spent allowance is caught above
                # as a block; HTTP errors keep the retries below.
                if not text.strip():
                    _usage = _model_wrote_nothing(body)
                    self.last_empty_reply = _usage or {
                        "completion_tokens": None, "reasoning_tokens": None,
                        "prompt_tokens": None,
                    }
                    # The reply spent the output limit before any text
                    # (thinking models count hidden reasoning against
                    # max_tokens).  A count above the requested cap means the
                    # route applied a cap of its own, not this request's.
                    _completion = stop_info["completion_tokens"]
                    if stop_info["limit_reached"] and not (
                        _completion is not None and _completion > payload["max_tokens"]
                    ):
                        self.last_empty_reply = {
                            **self.last_empty_reply,
                            "limit_reached": True,
                            "max_tokens": payload["max_tokens"],
                        }
                    log.warning(
                        "[!] Empty model reply (%.1fs): HTTP %d envelope, %s "
                        "completion tokens, no text; handing it to the loop",
                        elapsed, r.status_code,
                        _usage["completion_tokens"] if _usage else "unreported",
                    )
                    if not getattr(r, "replayed", False):
                        _record_master_tokens(
                            self._tier or "SRD46-analysis", body,
                            input_chars=len(system) + prompt_len, output_chars=0,
                        )
                    return ""

                log.info(
                    "<< Argo responded in %.1fs (%d chars)",
                    elapsed, len(text),
                )
                # Best-effort token tally for the master browser live display.
                if not getattr(r, "replayed", False):
                    _record_master_tokens(
                        self._tier or "SRD46-analysis", body,
                        input_chars=len(system) + prompt_len,
                        output_chars=len(text) if isinstance(text, str) else 0,
                    )
                # Side-logging (harmless, never touches context)
                if self._tier:
                    try:
                        _get_stats_recorder().log_argo_call(
                            tier=self._tier,
                            model=_model,
                            system_chars=len(system),
                            prompt_chars=prompt_len,
                            response_chars=len(text),
                            elapsed_s=round(elapsed, 1),
                        )
                    except Exception as exc:
                        log.error("Stats side-logging failed for tier %s: %s", self._tier, exc, exc_info=True)
                return text

            except requests.ReadTimeout:
                elapsed = time.time() - t0
                log.error(
                    "[!] TIMEOUT after %.1fs (attempt %d/%d)",
                    elapsed, attempt, self.max_retries,
                )
                last_err = f"Timeout after {elapsed:.0f}s"
                time.sleep(self.retry_backoff * attempt)

            except requests.ConnectionError as e:
                elapsed = time.time() - t0
                log.error(
                    "[!] Connection error after %.1fs (attempt %d/%d): %s",
                    elapsed, attempt, self.max_retries, e,
                )
                last_err = str(e)
                time.sleep(self.retry_backoff * attempt)

            except requests.RequestException as e:
                elapsed = time.time() - t0
                log.warning(
                    "[!] Request failed after %.1fs (attempt %d/%d): %s",
                    elapsed, attempt, self.max_retries, e,
                )
                last_err = str(e)
                time.sleep(self.retry_backoff * attempt)

        raise ArgoTransportError(
            attempts=self.max_retries, last_error=str(last_err),
        )

    # ── asynchronous call (wraps sync via asyncio.to_thread) ─

    async def acall(
        self,
        prompt: str,
        system: str,
        *,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        model: str | None = None,
    ) -> str:
        """Async version of call() for use with asyncio.gather().

        Uses asyncio.to_thread() to avoid blocking the event loop
        while keeping the implementation simple and tested.
        """
        return await asyncio.to_thread(
            self.call,
            prompt,
            system,
            max_tokens=max_tokens,
            stop=stop,
            model=model,
        )

    # ── convenience constructors ─────────────────────────────
    # Agent-specific factory methods (for_l0, for_l1, etc.) live in
    # each agent's argo_engine_subagent_helpers package.  Only the
    # base constructor is provided here.

    @classmethod
    def with_tier(cls, tier: str, **overrides) -> ArgoClient:
        """Create an ArgoClient with a stats-only tier label + overrides."""
        return cls(_tier=tier, **overrides)

    @classmethod
    def for_verdict(cls) -> ArgoClient:
        """Create an ArgoClient configured for the post-job verdict agent."""
        _cfg = get_config()
        return cls(
            model=_cfg.VERDICT_MODEL,
            temperature=_cfg.VERDICT_TEMPERATURE,
            max_tokens=_cfg.VERDICT_MAX_TOKENS,
            _tier="verdict",
        )

    @classmethod
    def for_compactor(cls) -> ArgoClient:
        """Create an ArgoClient for compression sub-agent calls."""
        _cfg = get_config()
        return cls(temperature=_cfg.COMPACTOR_TEMPERATURE, max_tokens=_cfg.COMPACTOR_MAX_TOKENS, stop=[], _tier="compactor")

    @classmethod
    def for_planner(cls) -> ArgoClient:
        """Create an ArgoClient for strategy planning calls."""
        _cfg = get_config()
        return cls(model=_cfg.PLANNER_MODEL, temperature=_cfg.PLANNER_TEMPERATURE, max_tokens=_cfg.PLANNER_MAX_TOKENS, _tier="planner")
