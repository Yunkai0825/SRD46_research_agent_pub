"""Advisory integrity signals for the QueryAgent answer turns.

The host flags tail shapes that suggest an answer stopped at the output cap.
When output-budget metadata supplies an ``output_truncated`` verdict, the
turn summary records it; an explicit False suppresses the tail heuristic.
The advisory signals travel in ``inspect_parser_context`` (``answer_turns``),
the workspace record and the stage audit; they never fail a gate themselves.
"""

from __future__ import annotations

import re
from typing import Any

# Heuristic character threshold for truncation confidence. At or above this
# length, any suspicious tail signal is classified as high confidence.
NEAR_OUTPUT_CAP_CHARS = 8_000
_TAIL_CHARS = 120
_SCAN_CHARS = 400
_MIN_PROSE_LINE = 24
_CLEAN_END_RE = re.compile(r"""[.!?:;)\]}|>*`"'”’_~]\s*$""")
_HEADING_OR_LIST_RE = re.compile(r"^\s*(?:#{1,6}\s|[-*+]\s|\d+[.)]\s)")
_BRACKET_PAIRS = (
    ("(", ")", "parenthesis"),
    ("[", "]", "bracket"),
    ("{", "}", "brace"),
)


def suspect_truncation(text: str) -> dict[str, Any] | None:
    """Return a structured suspicion when ``text`` looks cut off, else None.

    Signals: an opener left unclosed in the tail window, an odd inline-code
    or bold marker on the last line, a table row without its closing pipe,
    or a prose last line that ends without terminal punctuation. Confidence
    is ``high`` when the answer is near the output cap (any signal: a cut can
    fall in plain prose, mid-word, with nothing left open) or when a
    structural signal coincides with a second signal; otherwise ``low``.
    """

    body = str(text or "").rstrip()
    if not body:
        return None
    last_line = body.rsplit("\n", 1)[-1].strip()
    window = body[-_SCAN_CHARS:]
    signals: list[str] = []
    for opener, closer, name in _BRACKET_PAIRS:
        if window.count(opener) > window.count(closer):
            signals.append(f"unclosed {name} in the last {_SCAN_CHARS} characters")
    if last_line.count("`") % 2:
        signals.append("unclosed inline code on the last line")
    if last_line.count("**") % 2:
        signals.append("unclosed bold marker on the last line")
    if last_line.startswith("|") and not last_line.endswith("|"):
        signals.append("the last table row has no closing pipe")
    elif (
        len(last_line) >= _MIN_PROSE_LINE
        and not _CLEAN_END_RE.search(last_line)
        and not _HEADING_OR_LIST_RE.match(last_line)
    ):
        signals.append("the last line ends without terminal punctuation")
    if not signals:
        return None
    near_cap = len(body) >= NEAR_OUTPUT_CAP_CHARS
    structural = any(
        signal.startswith("unclosed") or "table row" in signal for signal in signals
    )
    confidence = (
        "high"
        if near_cap or (structural and len(signals) >= 2)
        else "low"
    )
    return {
        "suspected": True,
        "confidence": confidence,
        "signals": signals,
        "chars": len(body),
        "near_output_cap": near_cap,
        "tail": body[-_TAIL_CHARS:],
    }


_BUDGET_SUMMARY_KEYS = ("max_tokens", "completion_tokens", "finish_reason", "output_truncated")


def answer_turn_summaries(
    turns: list[str], meta: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Per-turn role, size, opening words and the truncation signals.

    ``meta`` carries one record per turn: ``kind`` (``initial``,
    ``reporting``, ``clarification`` or ``continuation``) and the Argo
    ``output_budget`` of the round that wrote the turn.  The usage record is authoritative where
    it exists: ``output_truncated`` True is a certain cut, False silences the
    tail heuristic (the model stopped on its own).  Without a record only the
    heuristic ``truncation_suspected`` speaks.
    """

    rows: list[dict[str, Any]] = []
    counts = {"clarification": 0, "continuation": 0, "reporting": 0}
    for index, turn in enumerate(turns, 1):
        stripped = str(turn or "").strip()
        info = meta[index - 1] if meta and index - 1 < len(meta) else None
        info = info if isinstance(info, dict) else {}
        kind = str(info.get("kind") or ("initial" if index == 1 else "clarification"))
        if kind == "initial":
            role = "initial answer"
        elif kind == "reporting":
            counts["reporting"] += 1
            role = (
                "report: the host asked the QueryAgent to restate the estimates "
                "of its exploration answer in a structured form; where it "
                "differs from an earlier turn, this later statement governs"
            )
        elif kind == "continuation":
            counts["continuation"] += 1
            role = (
                f"continuation {counts['continuation']}: the host asked the "
                "QueryAgent to resume the preceding cut answer; read it as that "
                "answer's tail"
            )
        else:
            counts["clarification"] += 1
            role = f"follow-up addendum {counts['clarification']}"
        row: dict[str, Any] = {
            "turn": index,
            "role": role,
            "kind": kind,
            "chars": len(stripped),
            "head": stripped[:80],
        }
        budget = info.get("output_budget")
        verdict = budget.get("output_truncated") if isinstance(budget, dict) else None
        if isinstance(budget, dict):
            row["output_budget"] = {key: budget.get(key) for key in _BUDGET_SUMMARY_KEYS}
        if verdict is not None:
            row["output_truncated"] = bool(verdict)
        flag = suspect_truncation(stripped)
        if flag is not None and verdict is not False:
            row["truncation_suspected"] = flag
        rows.append(row)
    return rows


__all__ = ["NEAR_OUTPUT_CAP_CHARS", "answer_turn_summaries", "suspect_truncation"]
