"""Self-contained section/eval-mode lookup for posteval_stats.

Parses ``TEST_PROMPTS.md`` to map question IDs (``Q1.2.3``) to their section
prefix and eval mode without depending on the migrated ``prompt_registry``
module that lives only in ``_srd46_migrate``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..input_support_helpers.scan import REPO_ROOT

EVAL_MODE_BY_PREFIX = {
    "1.1": "direct_lookup",
    "1.2": "provenance",
    "2.1": "comparison",
    "2.2": "aggregate",
    "3.1": "multi_step",
    "3.2": "thermo_reasoning",
    "4": "hypothesis",
    "5.1": "ambiguous",
    "5.2": "negative",
}

SECTION_RE = re.compile(r"^##\s+(?P<prefix>[\d.]+)\s+[—-]\s+(?P<title>.+)$")
ROW_RE = re.compile(r"^\|\s*(?P<qid>[\d.]+)\s*\|\s*(?P<prompt>.+?)\s*\|$")


@dataclass(slots=True, frozen=True)
class PromptSpec:
    question_id: str
    section: str
    section_title: str
    eval_mode: str


def _eval_mode_for_section(section_prefix: str) -> str:
    for prefix, mode in sorted(EVAL_MODE_BY_PREFIX.items(), key=lambda kv: len(kv[0]), reverse=True):
        if section_prefix == prefix or section_prefix.startswith(prefix + ".") or section_prefix.startswith(prefix):
            return mode
    return "unknown"


def load_prompt_registry(path: str | Path | None = None) -> dict[str, PromptSpec]:
    prompt_path = Path(path) if path else Path(__file__).absolute().parents[2] / "TEST_PROMPTS.md"
    text = prompt_path.read_text(encoding="utf-8", errors="replace")

    current_prefix: str | None = None
    current_title: str | None = None
    prompts: dict[str, PromptSpec] = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        section_match = SECTION_RE.match(line)
        if section_match:
            current_prefix = section_match.group("prefix")
            current_title = section_match.group("title").strip()
            continue

        row_match = ROW_RE.match(line)
        if not row_match or line.startswith("| # |"):
            continue
        if current_prefix is None:
            continue

        bare_qid = row_match.group("qid")
        if bare_qid == "#" or not re.match(r"^\d", bare_qid):
            continue

        prompts[f"Q{bare_qid}"] = PromptSpec(
            question_id=f"Q{bare_qid}",
            section=current_prefix,
            section_title=current_title or "",
            eval_mode=_eval_mode_for_section(current_prefix),
        )
    return prompts


__all__ = ["EVAL_MODE_BY_PREFIX", "PromptSpec", "load_prompt_registry"]
