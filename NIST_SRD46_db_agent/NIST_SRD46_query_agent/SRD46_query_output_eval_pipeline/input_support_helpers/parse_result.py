from __future__ import annotations

import re
from pathlib import Path

from ..models import ResultDoc

SECTION_RE = re.compile(r"^\*\*Section:\*\*\s*(?P<section>.+)$", re.MULTILINE)
PROMPT_RE = re.compile(r"^\*\*Prompt:\*\*\s*(?P<prompt>.+)$", re.MULTILINE)
TOOLS_RE = re.compile(
    r"\*\*Tool calls:\*\*\s*(?P<calls>\d+)\s+\|\s+\*\*Time:\*\*\s*"
    r"(?P<planning>[\d.]+)s planning \+\s*"
    r"(?P<execution>[\d.]+)s execution \+\s*"
    r"(?P<verdict>[\d.]+)s verdict =\s*"
    r"(?P<total>[\d.]+)s total"
)
VERDICT_BLOCK_RE = re.compile(
    r"^### Verdict & Explanation\s*(?P<body>.*)$",
    re.MULTILINE | re.DOTALL,
)
VERDICT_TEXT_RE = re.compile(r"\*\*Verdict:\*\*\s*(?P<verdict>.+)")
EXPLANATION_RE = re.compile(r"\*\*Explanation:\*\*\s*(?P<explanation>.+)", re.DOTALL)


def parse_result(path: str | Path) -> ResultDoc:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return parse_result_text(text)


def parse_result_text(text: str) -> ResultDoc:
    section_match = SECTION_RE.search(text)
    prompt_match = PROMPT_RE.search(text)
    tools_match = TOOLS_RE.search(text)
    verdict_block_match = VERDICT_BLOCK_RE.search(text)

    answer_markdown = _extract_answer_markdown(text, tools_match, verdict_block_match)
    answer_text = _markdown_to_text(answer_markdown)
    verdict_text = None
    explanation_text = None
    verdict_bucket = None

    if verdict_block_match:
        verdict_block = verdict_block_match.group("body").strip()
        verdict_text_match = VERDICT_TEXT_RE.search(verdict_block)
        explanation_match = EXPLANATION_RE.search(verdict_block)
        verdict_text = verdict_text_match.group("verdict").strip() if verdict_text_match else None
        explanation_text = explanation_match.group("explanation").strip() if explanation_match else None
        verdict_bucket = classify_verdict(verdict_text)

    return ResultDoc(
        section_label=section_match.group("section").strip() if section_match else None,
        prompt_text=prompt_match.group("prompt").strip() if prompt_match else "",
        total_tool_calls=int(tools_match.group("calls")) if tools_match else None,
        planning_time_sec=float(tools_match.group("planning")) if tools_match else None,
        execution_time_sec=float(tools_match.group("execution")) if tools_match else None,
        verdict_time_sec=float(tools_match.group("verdict")) if tools_match else None,
        total_time_sec=float(tools_match.group("total")) if tools_match else None,
        answer_markdown=answer_markdown,
        answer_text=answer_text,
        answer_word_count=len(re.findall(r"\b\w+\b", answer_text)),
        verdict_text=verdict_text,
        verdict_bucket=verdict_bucket,
        explanation_text=explanation_text,
    )


def classify_verdict(verdict_text: str | None) -> str | None:
    if not verdict_text:
        return None
    verdict = verdict_text.lower()
    if any(token in verdict for token in ("fully answered", "full answer", "fully", "complete", "completely")):
        return "full"
    if any(token in verdict for token in ("mostly", "largely", "near-complete", "almost")):
        return "mostly_full"
    if any(token in verdict for token in ("partial", "partly", "incomplete")):
        return "partial"
    if any(token in verdict for token in ("failed", "did not", "unable", "could not", "not answer")):
        return "failed"
    if any(token in verdict for token in ("clarification", "clarify", "ambiguous", "under-specified")):
        return "clarification"
    return "other"


def _extract_answer_markdown(
    text: str,
    tools_match: re.Match[str] | None,
    verdict_block_match: re.Match[str] | None,
) -> str:
    if tools_match is None:
        return text.strip()
    separator_start = text.find("\n---", tools_match.end())
    if separator_start == -1:
        body_start = tools_match.end()
    else:
        body_start = separator_start + len("\n---")
    body_end = verdict_block_match.start() if verdict_block_match else len(text)
    return text[body_start:body_end].strip()


def _markdown_to_text(markdown: str) -> str:
    lines: list[str] = []
    in_code_block = False
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if line.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if re.fullmatch(r"\|?[\-\s:|]+\|?", line):
            continue
        if line.startswith("|") and line.endswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            line = " ".join(cell for cell in cells if cell)
        line = re.sub(r"`([^`]*)`", r"\1", line)
        line = re.sub(r"\*\*([^*]+)\*\*", r"\1", line)
        line = re.sub(r"\*([^*]+)\*", r"\1", line)
        line = re.sub(r"^#+\s*", "", line)
        if line.strip():
            lines.append(line.strip())
    return "\n".join(lines).strip()
