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
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import requests

from .engine_config import get_config
from ..general_hooks_management_helpers.general_context_hooks.stats_references_tracking_hooks import (
    get_active_recorder as _get_stats_recorder,
)
from ..general_text_context_marker_catalog import MARKERS

log = logging.getLogger("ArgoClient")


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
            "user":        self.api_user,
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
    def _fix_stop_token(text: str) -> str:
        """Re-append </tool_call> if it was stripped by the stop sequence."""
        if MARKERS.tool_call.open in text and MARKERS.tool_call.close not in text:
            text += MARKERS.tool_call.close
        return text

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
                r = requests.post(
                    self.api_url,
                    headers=get_config().HEADERS,
                    json=payload,
                    timeout=self.http_timeout,
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
                        f"rejected the request for user '{self.api_user}' / model '{_model}' at "
                        f"{self.api_url}. This is an upstream credential/endpoint issue, not a "
                        f"problem with the prompt. Check that the ANL username is correct, you are "
                        f"on the ANL network/VPN, and the endpoint/model are available (override "
                        f"the endpoint with the ARGO_API_URL env var if the dev endpoint is down). "
                        f"Server said: {r.text[:300]}"
                    )

                r.raise_for_status()

                body = r.json()
                text = body.get("response", "")
                if isinstance(text, dict):
                    text = json.dumps(text)
                text = self._fix_stop_token(text)

                # Detect upstream 429 relayed as 200 body text
                if text.lstrip().startswith("Error:") and "429" in text[:300]:
                    log.warning(
                        "[!] Upstream 429 in body (attempt %d/%d): %s",
                        attempt, self.max_retries, text[:200],
                    )
                    last_err = f"Upstream 429: {text[:200]}"
                    time.sleep(self.retry_backoff * attempt * 2)
                    continue

                log.info(
                    "<< Argo responded in %.1fs (%d chars)",
                    elapsed, len(text),
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

        raise RuntimeError(
            f"Argo API failed after {self.max_retries} attempts: {last_err}"
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
