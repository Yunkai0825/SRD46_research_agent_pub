"""Render the host's follow-up turns without exposing parser machinery.

The exploration turn of a pair's conversation carries chemistry only.  Every
reporting requirement reaches the QueryAgent afterwards as one of the turns
rendered here: the reporting turn (structured restatement), chemistry
clarifications, and continuations of a cut answer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from ..runtime_support.artifacts import read_text


_TOPIC_TEXT = {
    "target_equilibrium_definition": "which target equilibrium definition the estimate applies to",
    "estimated_log10_K": "the numerical log10 K estimate",
    "uncertainty": "a defensible uncertainty in log10 units",
    "estimation_method": "the chemistry-based estimation method",
    "assumptions": "the chemical and reference-state assumptions",
    "rationale": "the chemical rationale for transferring the evidence",
    "supporting_evidence": "the SRD-46 records, networks, or citations used as evidence",
    "plain_chemistry_conclusion": "the chemistry conclusion in ordinary prose",
}
KNOWN_CLARIFICATION_TOPICS = frozenset(_TOPIC_TEXT)

# Plain words for what the host already holds of one estimate (the numbers
# are rendered from the row itself).
_HELD_TOPIC_WORDS = {
    "estimation_method": "the estimation method",
    "assumptions": "the assumptions",
    "rationale": "the rationale",
    "supporting_evidence": "the evidence records",
    "target_equilibrium_definition": "the target equilibrium",
    "plain_chemistry_conclusion": "the conclusion",
}
# Bounds on the held digest a clarification prompt carries.
HELD_DIGEST_MAX_ROWS = 12
HELD_STATEMENT_CHARS = 160


# Every host follow-up prompt (reporting turn, clarification, continuation)
# begins with this tag: the agent's conversation keeps the budget notices of
# earlier turns, and the tag marks where a new host turn, with a budget of
# its own, begins. The Query runtime's notices name "the turn that began
# with the latest [follow-up] message".
FOLLOW_UP_TAG = "[follow-up] "


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + ", and " + items[-1]


def _number(value: Any) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return f"{float(value):g}"


def _held_lines(held: Iterable[Mapping[str, Any]] | None) -> list[str]:
    """One line per held estimate, in the agent's own words plus its numbers."""

    lines: list[str] = []
    for row in list(held or [])[:HELD_DIGEST_MAX_ROWS]:
        if not isinstance(row, Mapping):
            continue
        statement = " ".join(str(row.get("statement") or "").split())
        if not statement:
            continue
        if len(statement) > HELD_STATEMENT_CHARS:
            statement = statement[: HELD_STATEMENT_CHARS - 1].rstrip() + "…"
        held_parts: list[str] = []
        value = _number(row.get("value"))
        if value is not None:
            uncertainty = _number(row.get("uncertainty"))
            numbers = value if uncertainty is None else f"{value} ± {uncertainty}"
            held_parts.append(f"the value {numbers} (log10 units)")
        for topic in row.get("held_topics") or []:
            word = _HELD_TOPIC_WORDS.get(str(topic))
            if word and word not in held_parts:
                held_parts.append(word)
        missing = [
            _TOPIC_TEXT[str(topic)]
            for topic in (row.get("missing_topics") or [])
            if str(topic) in _TOPIC_TEXT
        ]
        line = statement
        if held_parts:
            line += " — held: " + _join(held_parts)
        if missing:
            line += "; still missing: " + _join(missing)
        lines.append(line)
    return lines


def _evidence_lines(index: Mapping[str, Any] | None) -> list[str]:
    """One line per call that returned records; the rest folded into one."""

    listed: list[str] = []
    folded: list[str] = []
    for row in (index or {}).get("calls") or []:
        if not isinstance(row, Mapping):
            continue
        head = f"#{row.get('call')} {row.get('tool') or 'unknown'}"
        arguments = str(row.get("arguments") or "")
        if arguments:
            head += f"({arguments})"
        ids = [str(token) for token in (row.get("ids") or []) if str(token).strip()]
        if ids:
            total = int(row.get("id_total") or len(ids))
            shown = ", ".join(ids)
            if total > len(ids):
                shown += f" (+{total - len(ids)} more; {total} records in all)"
            listed.append(f"- {head} → {shown}")
        else:
            suffix = " (error)" if str(row.get("status") or "") == "error" else ""
            folded.append(head + suffix)
    lines = list(listed)
    omitted = int((index or {}).get("omitted_with_ids") or 0)
    if omitted:
        lines.append(f"- (+{omitted} more calls that returned records, not listed)")
    if folded:
        more = int((index or {}).get("omitted_without_ids") or 0)
        tail = f" (+{more} more)" if more else ""
        lines.append("- calls that returned no record ids: " + "; ".join(folded) + tail)
    return lines


def render_query_clarification(
    missing_topics: Iterable[str],
    *,
    held: Iterable[Mapping[str, Any]] | None = None,
    evidence_index: Mapping[str, Any] | None = None,
    ungrounded_ids: Iterable[str] | None = None,
) -> str:
    """Ask for the missing chemistry topics only.

    ``held`` (rows from ``parse_speciation_answer.held_digest``) adds the
    host's digest of what it already holds from the agent's answers - each
    estimate quoted in the agent's own words with its bound numbers and what
    is still missing for it - so the agent has no reason to re-emit the
    report.  Nothing host-owned is rendered: the rows carry no beta ids or
    canonical equations.

    When ``supporting_evidence`` is among the topics, ``evidence_index`` (from
    ``parse_speciation_answer.evidence_call_index``) and ``ungrounded_ids``
    add the calls the agent already made with the record ids each returned,
    and the ids its answers cite that no call returned, with the ask to
    re-point, read one record, or withdraw rather than search again.  Both
    carry only the agent's own id tokens.
    """

    topics = sorted({str(value).strip() for value in missing_topics if str(value).strip()})
    if not topics:
        raise ValueError("at least one missing chemistry topic is required")
    unknown = sorted(set(topics) - KNOWN_CLARIFICATION_TOPICS)
    if unknown:
        raise ValueError(f"unknown chemistry clarification topics: {unknown}")
    descriptions = [_TOPIC_TEXT[topic] for topic in topics]
    if len(descriptions) == 1:
        requested = descriptions[0]
    else:
        requested = ", ".join(descriptions[:-1]) + ", and " + descriptions[-1]
    text = (
        f"{FOLLOW_UP_TAG}Please add only the missing chemistry information for "
        f"your preceding estimate: {requested}. Earlier statements you do not "
        "mention stay valid. Do not repeat the full preceding answer unless you "
        "need to correct it, and clearly identify any correction."
    )
    lines = _held_lines(held)
    if lines:
        text += (
            "\n\nFor reference, the host already holds these statements from "
            "your preceding answers, quoted in your own words; do not restate "
            "them, add only what is listed as missing:\n"
            + "\n".join(f"- {line}" for line in lines)
            + "\nIf you correct one of them, restate that estimate complete: "
            "the reaction, the value and the uncertainty together."
        )
    if "supporting_evidence" in topics:
        evidence_lines = _evidence_lines(evidence_index)
        cited = [
            str(token).strip() for token in (ungrounded_ids or []) if str(token).strip()
        ]
        if evidence_lines or cited:
            text += "\n\nFor the evidence, do not run your searches again."
            if evidence_lines:
                text += (
                    " These are the tool calls you already made in this "
                    "conversation and the record ids each returned, as you saw "
                    "them:\n" + "\n".join(evidence_lines)
                )
            if cited:
                text += (
                    ("\n" if evidence_lines else " ")
                    + "Ids your answers cite that no tool call in this "
                    "conversation returned: " + ", ".join(cited) + "."
                )
            text += (
                "\nFor each record you cite: name the call above that returned "
                "it and restate the sentence that rests on it. If the estimate "
                "needs a record none of these calls returned, read it with one "
                "inspect_card call on that id. Otherwise withdraw the citation "
                "and say which of the records above the estimate rests on instead."
            )
    return text


def render_query_reporting_followup() -> str:
    """The host's reporting turn, sent once after the exploration answer.

    The exploration turn is chemistry only; this second
    turn of the same conversation asks the agent to restate the estimates it
    made in the structured form the downstream equilibrium map needs: ids,
    species, conditions, uncertainty and step-by-step provenance with fully
    prefixed identifiers.  The agent keeps every tool for it.  The text lives
    in ``reporting_followup_prompt.md`` next to this module and is
    hash-protected by the contract test.
    """

    text = read_text(
        Path(__file__).with_name("reporting_followup_prompt.md"), encoding="utf-8",
    ).strip()
    if not text:
        raise ValueError("reporting_followup_prompt.md is empty")
    return FOLLOW_UP_TAG + text


# Characters of the cut answer quoted back so the model can resume in place.
CONTINUATION_TAIL_CHARS = 200


def render_query_continuation(tail: str, *, reason: str) -> str:
    """Ask the same conversation to resume an answer that stopped early.

    The host quotes the last characters of the cut answer and asks for the
    remainder only: whole re-emission of what was cut mid-way, then whatever
    was still to come, no repetition of the complete parts.  The parser reads
    the continuation as the tail of the preceding turn.
    """

    excerpt = str(tail or "").rstrip()[-CONTINUATION_TAIL_CHARS:].strip()
    if not excerpt:
        raise ValueError("a continuation needs the tail of the cut answer")
    why = str(reason or "").strip() or "it stopped before its end"
    return (
        f"{FOLLOW_UP_TAG}Your preceding answer appears to have stopped before "
        f"its end ({why}). Its last characters were:\n\n"
        f"{excerpt}\n\n"
        "Resume from exactly that point. Re-emit in full any sentence, table "
        "row, or citation that was cut, then give whatever was still to come. "
        "Do not repeat the parts that were already complete, and do not change "
        "earlier values unless you clearly identify the correction."
    )


# ── Remaining host follow-ups, told to the agent only when close ────────────
# A pair's follow-up stage (the host's clarifications and continuations after
# the exploration answer) is rationed by the host: clarification rounds,
# continuation retries, a host-turn ceiling over both kinds and one wall
# clock. The parser sees them as ``host_turn_budget``; the QueryAgent hears
# about them only when the stage is nearly spent. Each notice names the
# stage it governs: after the current turn, at most HOST_BUDGET_NOTE_LAST_TURNS
# further turn(s) of its kind - or of any kind under the ceiling - remain, or
# HOST_BUDGET_NOTE_TIME_FRACTION of the stage's wall clock is used. The note
# is informational: nothing is blocked by it, and a turn far from every
# limit carries no note.
HOST_BUDGET_NOTE_LAST_TURNS = 1
HOST_BUDGET_NOTE_TIME_FRACTION = 0.75
_HOST_TURN_KINDS = {
    "clarification": (
        "clarification", "clarifications",
        "include everything asked for above in this answer",
    ),
    "continuation": (
        "continuation", "continuations",
        "finish the remainder of the answer in this turn",
    ),
}
_ANY_KIND_WORDS = (
    "follow-up turn of any kind (clarification or continuation)",
    "follow-up turns of any kind (clarifications or continuations)",
)


def render_host_budget_note(
    *,
    kind: str,
    remaining_same_kind: int,
    remaining_any_kind: int | None = None,
    time_used_s: float | None = None,
    time_budget_s: float | None = None,
) -> str:
    """The host-budget note for a clarification or continuation prompt, or "".

    ``remaining_same_kind`` counts the turns of ``kind`` the host could still
    send after the current one; ``remaining_any_kind`` the turns of either
    kind still allowed under the host-turn ceiling (None when no ceiling
    applies).  The smaller of the two binds.  ``time_used_s`` and
    ``time_budget_s`` are the stage's wall clock.  Empty unless the stage is
    close to a limit; the caller appends a non-empty note after the prompt.
    """

    if kind not in _HOST_TURN_KINDS:
        raise ValueError(f"unknown host turn kind: {kind!r}")
    singular, plural, ask = _HOST_TURN_KINDS[kind]
    binding = max(0, int(remaining_same_kind))
    words = (singular, plural)
    if remaining_any_kind is not None and max(0, int(remaining_any_kind)) < binding:
        binding, words = max(0, int(remaining_any_kind)), _ANY_KIND_WORDS
    turns_close = binding <= HOST_BUDGET_NOTE_LAST_TURNS
    time_close = False
    used = budget = 0.0
    if time_budget_s is not None and time_used_s is not None and float(time_budget_s) > 0:
        used = max(0.0, float(time_used_s))
        budget = float(time_budget_s)
        time_close = used / budget >= HOST_BUDGET_NOTE_TIME_FRACTION
    if not turns_close and not time_close:
        return ""
    head = (
        "Host budget note for this pair's follow-up stage (the host's "
        "clarifications and continuations after your exploration answer; it "
        "says nothing about this turn's own tool and time budget): "
    )
    parts: list[str] = []
    if turns_close:
        if binding == 0:
            parts.append(
                f"this is the last {words[0]} the host can send for this pair, "
                f"so {ask}; nothing can be asked for again afterwards."
            )
        else:
            noun = words[0] if binding == 1 else words[1]
            parts.append(
                f"after this turn the host can send at most {binding} more {noun} "
                f"for this pair, so {ask}."
            )
    if time_close:
        percent = int(round(100 * min(1.0, used / budget)))
        clock = (
            f"about {max(0.0, budget - used):.0f} s of the stage's {budget:.0f} s "
            f"wall clock remain ({percent}% used)"
        )
        parts.append(clock[0].upper() + clock[1:] + "." if parts else f"{clock}, so {ask}.")
    return head + " ".join(parts)


__all__ = [
    "FOLLOW_UP_TAG",
    "CONTINUATION_TAIL_CHARS",
    "HELD_DIGEST_MAX_ROWS",
    "HELD_STATEMENT_CHARS",
    "HOST_BUDGET_NOTE_LAST_TURNS",
    "HOST_BUDGET_NOTE_TIME_FRACTION",
    "KNOWN_CLARIFICATION_TOPICS",
    "render_host_budget_note",
    "render_query_clarification",
    "render_query_continuation",
    "render_query_reporting_followup",
]
