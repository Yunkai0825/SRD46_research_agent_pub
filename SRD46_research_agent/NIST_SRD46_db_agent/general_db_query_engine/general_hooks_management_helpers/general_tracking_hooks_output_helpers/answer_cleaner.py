"""
Clean up raw LLM answers for display.
======================================
Strips tool-call XML, echoed conversation turns, and bare JSON artefacts
from the final answer text before writing to result files.
"""
from __future__ import annotations

import re

_TOOL_XML_RE = re.compile(
    r"<tool_(?:call|result)>.*?</tool_(?:call|result)>", re.DOTALL,
)

# Per-iteration LD validator answer tags emitted by the L0 orchestrator.
# When an LD validation loop runs, each pass's reorganized answer is
# wrapped in ``<answer_LD_i>...</answer_LD_i>``. The visible final answer
# is the highest-index block; if no LD tags are present, fall back to the
# raw text (which may itself contain a single ``<answer>...</answer>``).
_LD_ANSWER_BLOCK_RE = re.compile(
    r"<answer_LD_(\d+)>\s*(.*?)\s*</answer_LD_\1>",
    re.DOTALL | re.IGNORECASE,
)


def _extract_latest_ld_answer(raw: str) -> str | None:
    """Return the body of the highest-index ``<answer_LD_i>`` block, or None."""
    if not raw or "<answer_LD_" not in raw:
        return None
    matches = list(_LD_ANSWER_BLOCK_RE.finditer(raw))
    if not matches:
        return None
    latest = max(matches, key=lambda m: int(m.group(1)))
    return latest.group(2).strip()


def clean_answer(raw: str) -> str:
    """Strip tool XML and echoed conversation turns from the final answer.

    If the orchestrator emitted ``<answer_LD_i>`` per-iteration tags
    (LD validator loop), extract the highest-index block and clean it.
    """
    ld_latest = _extract_latest_ld_answer(raw)
    if ld_latest is not None:
        raw = ld_latest
    text = _TOOL_XML_RE.sub("", raw)
    parts = re.split(r"(?=^## (?:User|Assistant))", text, flags=re.MULTILINE)
    cleaned = []
    for p in parts:
        if p.startswith("## User"):
            continue
        if p.startswith("## Assistant"):
            p = re.sub(r"^## Assistant\n", "", p)
        cleaned.append(p)
    text = "\n".join(cleaned)
    text = re.sub(r"\n{4,}", "\n\n\n", text).strip()
    if not text:
        fallback = _TOOL_XML_RE.sub("", raw).strip()
        if len(fallback) > 2000:
            fallback = "...\n" + fallback[-2000:]
        text = (
            "*(No clear final answer — raw tail below.)*\n\n" + fallback
            if fallback
            else "*(No answer)*"
        )
    return text
