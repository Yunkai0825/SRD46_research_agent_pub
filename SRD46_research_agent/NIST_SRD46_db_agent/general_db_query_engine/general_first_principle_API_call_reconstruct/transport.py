"""HTTP response preservation and narrowly scoped authorization detection."""
from __future__ import annotations

import json
from typing import Any


def http_post(payload: Any, live_call, *, transport: str = "argo", lane: str = "",
              send_payload=None, request_timeout=None):
    """Use the active recorder/reconstructor, otherwise preserve direct I/O."""
    from .controller import current_session
    session = current_session()
    if session is None:
        return send_payload(payload) if send_payload is not None else live_call()
    return session.http_call(payload, live_call, transport=transport, lane=lane,
                             send_payload=send_payload, request_timeout=request_timeout)


class RecordedResponse:
    """The requests.Response surface used by the native turn-based callers."""

    def __init__(self, status_code: int, text: str):
        self.status_code = int(status_code)
        self.text = text
        self.content = text.encode("utf-8")
        self.headers: dict[str, str] = {}
        self.replayed = True

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    def json(self, **kwargs: Any) -> Any:
        return json.loads(self.text, **kwargs)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(
                f"Recorded HTTP {self.status_code}", response=self,
            )


def authorization_denied(status_code: int, text: str) -> bool:
    """Recognize access denial, never ordinary rate/transport/model errors.

    Argo also sends a zero-token provider notice in an HTTP 200 Anthropic
    envelope. A model's ordinary prose mentioning authorization is not enough.
    """
    if int(status_code) in (401, 403):
        return True
    if int(status_code) != 200:
        return False
    try:
        body = json.loads(text)
    except (TypeError, ValueError):
        return False
    if not isinstance(body, dict):
        return False
    content = body.get("content")
    parts = [str(item.get("text", "")) for item in content
             if isinstance(item, dict)] if isinstance(content, list) else []
    response = body.get("response")
    if isinstance(response, str):
        parts.append(response)
    notice = "\n".join(parts).upper()
    if "ACCESS REVOKED" not in notice:
        return False
    blocked_id = str(body.get("id", "")).startswith("msg_blocked_")
    usage = body.get("usage", {})
    zero_usage = isinstance(usage, dict) and (
        usage.get("input_tokens") == 0 and usage.get("output_tokens") == 0
    )
    explicit_notice = (
        "IMPORTANT USAGE NOTICE FROM ARGO" in notice
        and "END NOTICE FROM ARGO" in notice
    )
    return explicit_notice and (blocked_id or zero_usage)


class ArgoAccessRevokedError(RuntimeError):
    """Argo refused the request because the user's usage allowance is spent.

    The gateway relays the block as an HTTP 200 Anthropic envelope whose only
    text is the usage notice ("IMPORTANT USAGE NOTICE FROM ARGO ... ACCESS
    REVOKED ... END NOTICE FROM ARGO") and whose id starts with
    ``msg_blocked_``; the ``response`` field the turn-based clients read is
    absent, so without this check the block reads as an empty reply. Retrying the
    identical request cannot succeed until Argo restores access, so the
    clients raise this once and never retry it.
    """

    def __init__(
        self,
        *,
        status_code: int,
        notice: str,
        response_id: str = "",
        model: str = "",
        api_user: str = "",
    ) -> None:
        self.status_code = int(status_code)
        self.notice = str(notice)
        self.response_id = str(response_id or "")
        self.model = str(model or "")
        self.api_user = str(api_user or "")
        who = f" for user {self.api_user!r}" if self.api_user else ""
        what = f" (model {self.model!r})" if self.model else ""
        envelope = f", envelope id {self.response_id}" if self.response_id else ""
        super().__init__(
            f"Argo access revoked{who}{what}: HTTP {self.status_code}{envelope}; "
            f"the gateway said: {self.notice} Not retried: the same request cannot "
            "succeed until Argo restores access (the notice names whom to contact)."
        )


def access_revoked_notice(status_code: int, text: str) -> tuple[str, str] | None:
    """``(notice, envelope_id)`` when ``authorization_denied`` holds, else None.

    The notice is the gateway's own text collapsed to one line of at most 400
    characters, for error messages and manifests; request headers are never
    part of it.
    """
    if not authorization_denied(status_code, text):
        return None
    try:
        body = json.loads(text)
    except (TypeError, ValueError):
        body = None
    parts: list[str] = []
    response_id = ""
    if isinstance(body, dict):
        content = body.get("content")
        if isinstance(content, list):
            parts.extend(
                str(item.get("text", "")) for item in content if isinstance(item, dict)
            )
        response = body.get("response")
        if isinstance(response, str):
            parts.append(response)
        response_id = str(body.get("id", "") or "")
    notice = " ".join("\n".join(parts).split())
    if not notice:
        notice = " ".join(str(text or "").split()) or f"HTTP {int(status_code)} access denied"
    return notice[:400], response_id
