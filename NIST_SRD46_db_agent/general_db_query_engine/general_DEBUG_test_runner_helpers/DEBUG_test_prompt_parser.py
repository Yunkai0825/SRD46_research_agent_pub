"""
Prompt parsers for test_prompts.md files.
=========================================
Two styles:
  - parse_prompts_with_sections():  returns [{id, section, prompt}, ...]
  - parse_prompts_simple():         returns [(id, prompt_text), ...]
"""
from __future__ import annotations

import re
from pathlib import Path


# ── With-sections parser (used by query agent) ─────────────────────────────

_TABLE_ROW_RE = re.compile(
    r"^\|\s*(?P<id>\d+\.\d+)\s*\|\s*(?P<prompt>.+?)\s*\|$"
)
_SECTION_RE = re.compile(r"^## (\d+)\s*[-—]?\s*(.*)$")


def parse_prompts_with_sections(path: Path) -> list[dict]:
    """Parse test_prompts.md into ``[{id, section, prompt}, ...]``."""
    prompts: list[dict] = []
    current_section = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        sm = _SECTION_RE.match(line)
        if sm:
            current_section = sm.group(1)
            continue
        m = _TABLE_ROW_RE.match(line)
        if m:
            prompts.append({
                "id": m.group("id"),
                "section": current_section,
                "prompt": m.group("prompt").strip(),
            })
    return prompts


# ── Simple parser (used by analysis / main agents) ─────────────────────────

_SIMPLE_PROMPT_RE = re.compile(
    r"\|\s*(\d+\.\d+)\s*\|\s*(.+?)\s*\|", re.MULTILINE,
)


def parse_prompts_simple(path: Path) -> list[tuple[str, str]]:
    """Parse test_prompts.md into ``[(id, prompt_text), ...]``."""
    text = path.read_text(encoding="utf-8")
    results: list[tuple[str, str]] = []
    for m in _SIMPLE_PROMPT_RE.finditer(text):
        pid, prompt = m.group(1), m.group(2).strip()
        if pid.replace(".", "").isdigit() and not prompt.startswith("Prompt"):
            results.append((pid, prompt))
    return results
