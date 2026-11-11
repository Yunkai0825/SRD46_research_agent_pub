"""The tool calls the QueryAgent already made, for an evidence follow-up.

When the parser sends ``supporting_evidence`` back, the host does not let the agent search again.  The clarification
prompt lists the calls the agent already made in this conversation with the
record ids each returned, plus the ids its answers cite that no call
returned, and asks it to re-point, read one record, or withdraw.  Everything
here is host-side bookkeeping over the evidence snapshot (one receipt per
successful call: ``history_index``, ``tool``, the observed ids) joined with
the turns' ``tool_history`` (each call's arguments).  Only the agent's own
id tokens are written (``vlm_``, ``ref_eq_net_``, ``lit_``): never the
receipts' beta-definition ids, equations or catalog names, so the Query side
still sees no SRD-46 notation it did not retrieve itself.
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping

# Bounds on what one clarification prompt carries.
EVIDENCE_INDEX_MAX_CALLS = 30
EVIDENCE_INDEX_MAX_IDS_PER_CALL = 8
EVIDENCE_INDEX_ARG_CHARS = 100
UNGROUNDED_IDS_MAX = 40

# Receipt key -> the token prefix the agent saw in the tool results.
_RECEIPT_ID_TOKENS = (
    ("observed_vlm_ids", "vlm_"),
    ("observed_network_ids", "ref_eq_net_"),
    ("observed_literature_ids", "lit_"),
)
# ``prose_cited_unauthorized_ids`` key -> the same prefixes.
_UNAUTHORIZED_ID_TOKENS = (
    ("vlm_ids", "vlm_"),
    ("network_ids", "ref_eq_net_"),
    ("literature_ids", "lit_"),
)


def _ints(values: Any) -> list[int]:
    parsed: set[int] = set()
    for value in values if isinstance(values, (list, tuple, set)) else []:
        if isinstance(value, bool):
            continue
        try:
            parsed.add(int(value))
        except (TypeError, ValueError):
            continue
    return sorted(parsed)


def session_tool_histories(session: Any) -> list[dict[str, Any]]:
    """Dispatch then follow-up tool calls, in the order the receipts index them.

    The same concatenation the clarification coordinator hands to the
    receipt builder, so ``history_index`` lines up with these positions.
    """

    dispatch = getattr(session, "dispatch_turn", None)
    history = list(getattr(dispatch, "tool_history", None) or [])
    for turn in getattr(session, "followup_turns", None) or []:
        history.extend(getattr(turn, "tool_history", None) or [])
    return history


def _short_arguments(arguments: Any, limit: int) -> str:
    """The call's arguments on one short line, as the agent wrote them."""

    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except (TypeError, ValueError):
            pass
    if isinstance(arguments, Mapping):
        parts = []
        for key, value in arguments.items():
            if isinstance(value, str):
                shown = repr(" ".join(value.split()))
            else:
                shown = json.dumps(
                    value, ensure_ascii=False, default=str, separators=(",", ":"),
                )
            parts.append(f"{key}={shown}")
        text = ", ".join(parts)
    elif arguments is None:
        text = ""
    else:
        text = " ".join(str(arguments).split())
    if len(text) > limit:
        text = text[: max(1, limit - 1)].rstrip() + "…"
    return text


def build_evidence_call_index(
    snapshot: Mapping[str, Any] | None,
    histories: Iterable[Mapping[str, Any]] | None,
    *,
    max_calls: int = EVIDENCE_INDEX_MAX_CALLS,
    max_ids_per_call: int = EVIDENCE_INDEX_MAX_IDS_PER_CALL,
    max_arg_chars: int = EVIDENCE_INDEX_ARG_CHARS,
) -> dict[str, Any]:
    """Index the calls the agent made and the record ids each returned.

    ``snapshot`` is the evidence snapshot (``tool_receipts`` with
    ``history_index``, ``tool`` and the observed ids of every successful
    call); ``histories`` the concatenated tool histories the snapshot was
    built from (``session_tool_histories``), which supply the arguments.
    Either alone still yields rows.  One row per call: ``call`` (1-based
    position), ``tool``, ``arguments`` (at most ``max_arg_chars``), ``status``
    (``ok`` with a receipt, ``error``, or ``no_result``), ``ids`` (at most
    ``max_ids_per_call`` tokens, vlm first, then networks, then literature)
    and ``id_total``.  At most ``max_calls`` rows with ids and ``max_calls``
    without are kept; the counts left out are returned beside the rows.
    Beta-definition ids in the receipts are never copied.
    """

    receipts_by_index: dict[int, Mapping[str, Any]] = {}
    for receipt in (snapshot or {}).get("tool_receipts") or []:
        if not isinstance(receipt, Mapping):
            continue
        position = receipt.get("history_index")
        if isinstance(position, bool) or not isinstance(position, int) or position < 0:
            continue
        receipts_by_index[position] = receipt
    history = [
        step if isinstance(step, Mapping) else {} for step in list(histories or [])
    ]
    positions = sorted(set(range(len(history))) | set(receipts_by_index))
    rows: list[dict[str, Any]] = []
    for position in positions:
        step = history[position] if position < len(history) else {}
        receipt = receipts_by_index.get(position)
        tokens: list[str] = []
        for key, prefix in _RECEIPT_ID_TOKENS:
            tokens.extend(f"{prefix}{value}" for value in _ints((receipt or {}).get(key)))
        if bool(step.get("is_error")):
            status = "error"
        elif receipt is not None:
            status = "ok"
        else:
            status = "no_result"
        rows.append({
            "call": position + 1,
            "tool": str(step.get("tool") or (receipt or {}).get("tool") or "unknown"),
            "arguments": _short_arguments(step.get("arguments"), int(max_arg_chars)),
            "status": status,
            "ids": tokens[: max(0, int(max_ids_per_call))],
            "id_total": len(tokens),
        })
    limit = max(0, int(max_calls))
    with_ids = [row for row in rows if row["ids"]]
    without_ids = [row for row in rows if not row["ids"]]
    kept = sorted(with_ids[:limit] + without_ids[:limit], key=lambda row: row["call"])
    return {
        "calls": kept,
        "total_calls": len(rows),
        "omitted_with_ids": max(0, len(with_ids) - limit),
        "omitted_without_ids": max(0, len(without_ids) - limit),
    }


def ungrounded_ids_for_followup(
    state: Any,
    *,
    unauthorized: Mapping[str, Iterable[int]] | None = None,
    limit: int = UNGROUNDED_IDS_MAX,
) -> list[str]:
    """Ids the agent cited that no tool returned, as the agent's own tokens.

    First the anchors the gate named on the active follow-up receipts
    (``details.ungrounded_anchor_vlm_ids`` of their issues), then the rest of
    the host's unauthorized partition (``unauthorized``: vlm, network and
    literature ids the answers name without a tool record), capped at
    ``limit``.  Beta-definition tokens are never included.
    """

    tokens: list[str] = []
    seen: set[str] = set()

    def add(token: str) -> None:
        if token not in seen:
            seen.add(token)
            tokens.append(token)

    try:
        receipts = list(state.active_query_followup_authorizations())
    except Exception:  # a minimal state double without receipts
        receipts = []
    for receipt in receipts:
        for issue in (receipt.get("issues") or []) if isinstance(receipt, Mapping) else []:
            if not isinstance(issue, Mapping):
                continue
            details = issue.get("details")
            if not isinstance(details, Mapping):
                continue
            for value in _ints(details.get("ungrounded_anchor_vlm_ids")):
                add(f"vlm_{value}")
    for key, prefix in _UNAUTHORIZED_ID_TOKENS:
        for value in _ints(list((unauthorized or {}).get(key) or [])):
            add(f"{prefix}{value}")
    return tokens[: max(0, int(limit))]


__all__ = [
    "EVIDENCE_INDEX_ARG_CHARS",
    "EVIDENCE_INDEX_MAX_CALLS",
    "EVIDENCE_INDEX_MAX_IDS_PER_CALL",
    "UNGROUNDED_IDS_MAX",
    "build_evidence_call_index",
    "session_tool_histories",
    "ungrounded_ids_for_followup",
]
