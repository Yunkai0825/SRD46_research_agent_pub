"""Workflow-skill markdown parser.

Reads a workflow ``.md`` file that follows the schema defined in
``_workflow_parsing_schema.md`` and returns a structured dict used by the
orchestrator to assemble agent prompts.

Public API
----------
parse_workflow(path) -> dict
    Parse a workflow markdown file and return structured sections.

render_prompt(parsed, *, purpose, instruction, context="", id_catalog="") -> str
    Substitute template variables and return the final prompt string.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_H2_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)

_TOOL_LINE_RE = re.compile(
    r"^-\s+(?P<sig>[^—\n]+?)(?:\s+—\s+(?P<desc>.+))?$",
    re.MULTILINE,
)

_PHASE_HEADER_RE = re.compile(
    r"^##\s+phase_(?P<num>\d+):\s*(?P<name>.+)$",
    re.MULTILINE,
)

_TOOLS_LINE_RE = re.compile(
    r"^tools:\s*\[(?P<groups>[^\]]*)\]\s*$",
    re.MULTILINE,
)

_PARALLEL_RE = re.compile(
    r"^parallel_dispatch:\s*\{(?P<body>[^}]*)\}\s*$",
    re.MULTILINE,
)

_JSON_FENCE_RE = re.compile(
    r"```json\s*\n(?P<body>.*?)```",
    re.DOTALL,
)

_SYSTEM_PROMPT_TAG_RE = re.compile(
    r"<system_prompt>\s*\n?(.*?)\n?\s*</system_prompt>",
    re.DOTALL,
)


def _extract_front_matter(text: str) -> tuple[dict, str]:
    """Return (front_matter_dict, remaining_text)."""
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("Missing YAML front-matter (need two --- delimiters)")
    fm = yaml.safe_load(parts[1])
    if not isinstance(fm, dict):
        raise ValueError("Front-matter must be a YAML mapping")
    for key in ("agent_id", "layer", "parent"):
        if key not in fm:
            raise ValueError(f"Front-matter missing required key: {key}")
    body = parts[2]
    return fm, body


def _split_h1_sections(body: str) -> dict[str, str]:
    """Split body into {heading: content} by H1 boundaries."""
    positions = [(m.start(), m.group(1).strip()) for m in _H1_RE.finditer(body)]
    sections: dict[str, str] = {}
    for i, (start, heading) in enumerate(positions):
        # content runs from end of this heading line to start of next section
        line_end = body.index("\n", start) + 1 if "\n" in body[start:] else len(body)
        end = positions[i + 1][0] if i + 1 < len(positions) else len(body)
        sections[heading] = body[line_end:end].strip()
    return sections


def _parse_tools(section_text: str) -> dict[str, list[dict[str, str]]]:
    """Parse ## group headers and tool bullet lines."""
    groups: dict[str, list[dict[str, str]]] = {}
    current_group: str | None = None
    for line in section_text.splitlines():
        h2 = re.match(r"^##\s+(.+)$", line)
        if h2:
            current_group = h2.group(1).strip()
            groups[current_group] = []
            continue
        if current_group is None:
            continue
        m = _TOOL_LINE_RE.match(line)
        if m:
            sig = m.group("sig").strip()
            desc = (m.group("desc") or "").strip()
            # extract bare name from signature
            name = sig.split("(")[0].strip() if "(" in sig else sig
            groups[current_group].append(
                {"name": name, "signature": sig, "description": desc}
            )
    return groups


def _parse_phases(section_text: str) -> list[dict[str, Any]]:
    """Parse phase sub-sections."""
    phases: list[dict[str, Any]] = []
    headers = list(_PHASE_HEADER_RE.finditer(section_text))
    for i, m in enumerate(headers):
        start = m.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(section_text)
        block = section_text[start:end].strip()

        # tools: [group1, group2]
        tools_m = _TOOLS_LINE_RE.search(block)
        tool_groups = (
            [g.strip() for g in tools_m.group("groups").split(",") if g.strip()]
            if tools_m
            else []
        )

        # parallel_dispatch: {tool_group: ..., fan_out_over: ..., max_concurrent: N}
        parallel = None
        par_m = _PARALLEL_RE.search(block)
        if par_m:
            parallel = {}
            for kv in par_m.group("body").split(","):
                kv = kv.strip()
                if ":" not in kv:
                    continue
                k, v = kv.split(":", 1)
                k, v = k.strip(), v.strip()
                # coerce max_concurrent to int
                if k == "max_concurrent":
                    v = int(v)
                parallel[k] = v
            parallel.setdefault("max_concurrent", 8)

        # guidance: everything after "guidance:" line
        guidance = ""
        gm = re.search(r"^guidance:\s*\|?\s*$", block, re.MULTILINE)
        if gm:
            guidance = block[gm.end():].strip()
        elif re.search(r"^guidance:\s*(.+)$", block, re.MULTILINE):
            guidance = re.search(r"^guidance:\s*(.+)$", block, re.MULTILINE).group(1).strip()

        phases.append(
            {
                "number": int(m.group("num")),
                "name": m.group("name").strip(),
                "tools": tool_groups,
                "parallel_dispatch": parallel,
                "guidance": guidance,
            }
        )
    return phases


def _parse_output_schema(section_text: str) -> dict | None:
    """Extract the first fenced JSON block.

    Tolerates trailing commas (common LLM output) by stripping them
    before parsing.
    """
    m = _JSON_FENCE_RE.search(section_text)
    if not m:
        return None
    body = m.group("body")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        # Strip trailing commas before } or ]
        cleaned = re.sub(r",\s*([}\]])", r"\1", body)
        return json.loads(cleaned)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_workflow(path: str | Path) -> dict[str, Any]:
    """Parse a workflow markdown file into a structured dict.

    Parameters
    ----------
    path : str or Path
        Path to the ``.md`` workflow skill file.

    Returns
    -------
    dict with keys: front_matter, system_prompt, tools, prompt_template,
    output_schema, phases.
    """
    text = Path(path).read_text(encoding="utf-8")
    front_matter, body = _extract_front_matter(text)

    # <system_prompt>…</system_prompt> tags for system prompt extraction
    sp_match = _SYSTEM_PROMPT_TAG_RE.search(body)
    if not sp_match:
        raise ValueError(
            f"Workflow {Path(path).name} is missing <system_prompt>…</system_prompt> tags. "
            "All workflow files must wrap their system prompt content in these tags."
        )
    system_prompt = sp_match.group(1).strip()

    sections = _split_h1_sections(body)

    return {
        "front_matter": front_matter,
        "system_prompt": system_prompt,
        "tools": _parse_tools(sections.get("Tools", "")),
        "prompt_template": sections.get("Prompt Template", ""),
        "output_schema": _parse_output_schema(sections.get("Output Schema", "")),
        "phases": _parse_phases(sections.get("Phases", "")),
    }


def render_prompt(
    parsed: dict[str, Any],
    *,
    purpose: str = "",
    instruction: str = "",
    context: str = "",
    id_catalog: str = "",
) -> str:
    """Substitute template variables into the prompt template.

    Parameters
    ----------
    parsed : dict
        Output of ``parse_workflow()``.
    purpose, instruction, context, id_catalog : str
        Values to insert into ``{{variable}}`` placeholders.

    Returns
    -------
    str  — the rendered prompt ready for the agent.
    """
    tmpl = parsed.get("prompt_template", "")
    replacements = {
        "purpose": purpose,
        "instruction": instruction,
        "context": context,
        "id_catalog": id_catalog,
    }
    for var, val in replacements.items():
        tmpl = tmpl.replace("{{" + var + "}}", val)
    return tmpl
