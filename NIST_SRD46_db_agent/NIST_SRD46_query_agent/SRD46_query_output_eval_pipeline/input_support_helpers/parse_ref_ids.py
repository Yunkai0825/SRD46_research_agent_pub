from __future__ import annotations

import re
from pathlib import Path

from ..models import EntityRef

STEP_RE = re.compile(r"^### Step (?P<step>\d+): `(?P<tool>[^`]+)`$", re.MULTILINE)


def parse_ref_ids(path: str | Path) -> list[EntityRef]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return parse_ref_ids_text(text)


def parse_ref_ids_text(text: str) -> list[EntityRef]:
    matches = list(STEP_RE.finditer(text))
    refs: list[EntityRef] = []

    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[start:end]
        step_num = int(match.group("step"))

        for table in _extract_markdown_tables(block):
            headers = [header.strip() for header in table[0]]
            for row in table[1:]:
                cells = dict(zip(headers, row))
                entity_type = (cells.get("type") or "").strip()
                prefixed_id = (cells.get("prefixed_id") or "").strip()
                if not entity_type or not prefixed_id:
                    continue
                label = _clean_optional(cells.get("label"))
                refs.append(
                    EntityRef(
                        entity_type=entity_type,
                        prefixed_id=prefixed_id,
                        name=_clean_optional(cells.get("name")),
                        detail=_clean_optional(cells.get("detail")) or label,
                        step_num=step_num,
                    )
                )
    return refs


def _extract_markdown_tables(block: str) -> list[list[list[str]]]:
    lines = block.splitlines()
    tables: list[list[list[str]]] = []
    index = 0
    while index < len(lines):
        line = lines[index].rstrip()
        if not line.startswith("|"):
            index += 1
            continue
        if index + 1 >= len(lines) or not lines[index + 1].lstrip().startswith("|"):
            index += 1
            continue
        header = _parse_row(lines[index])
        separator = _parse_row(lines[index + 1])
        if not _looks_like_separator(separator):
            index += 1
            continue
        rows = [header]
        index += 2
        while index < len(lines) and lines[index].lstrip().startswith("|"):
            rows.append(_parse_row(lines[index]))
            index += 1
        tables.append(rows)
    return tables


def _parse_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _looks_like_separator(cells: list[str]) -> bool:
    return all(set(cell) <= {"-", ":"} for cell in cells if cell)


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
