"""File-backed structured-markdown working memory.

The working memory is a single ``.md`` file with three sections:

1. **ID Catalog** — protected table of num_ids/ids.  Never auto-compacted.
2. **History**    — append-only log of agent actions.  Compactable.
3. **Results**    — indexed findings from search/analysis.  Compactable.

Public API
----------
WorkingMemory(path)
    .read(section=None)           -> str   (full file or one section)
    .append_history(line)         -> None
    .add_result(key, body)        -> None
    .catalog_add(type, num_id, id, name) -> None
    .catalog_remove(type, num_id) -> None
    .catalog_list()               -> list[dict]
    .compact_section(section, summariser) -> None
    .reset()                      -> None  (re-initialise to empty template)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable


_TEMPLATE = """\
# Working Memory

## ID Catalog
<!-- PROTECTED — never compacted. Auto-populated by catalog ops. -->
### Resolved Entities
| type | num_id | id | name |
|------|--------|----|------|

### Reference IDs
| type | num_id | id | name |
|------|--------|----|------|

## History
<!-- Append-only log. Compactable when >30 entries. -->

## Results
<!-- Indexed findings. Compactable per-entry. -->
"""

_KNOWN_SECTIONS = frozenset({"ID Catalog", "History", "Results"})
_SECTION_RE = re.compile(r"^## (.+)$", re.MULTILINE)
_CATALOG_ROW_RE = re.compile(
    r"^\|\s*(?P<type>\w+)\s*\|\s*(?P<num_id>\w+_\d+)\s*\|\s*(?P<id>[^|]+?)\s*\|\s*(?P<name>[^|]+?)\s*\|$",
    re.MULTILINE,
)
# Strip leading type prefix from num_id values that arrive as strings
# e.g. "comp_63" → 63,  "prop_1" → 1,  63 → 63
_PREFIX_NUM_RE = re.compile(r"^[a-z]+_(\d+)$", re.IGNORECASE)

# Entity types stored as plain reference IDs (separate sub-table)
_REF_ONLY_FILE_TYPES = frozenset({"vlm", "lit", "network", "node"})
# Sub-table header markers within '## ID Catalog'
_RESOLVED_HEADER = "### Resolved Entities"
_REF_HEADER = "### Reference IDs"


class WorkingMemory:
    """Read/write interface over a structured-md working-memory file."""

    def __init__(self, path: str | Path):
        self._path = Path(path)
        if not self._path.exists():
            self.reset()

    # -- low-level I/O -----------------------------------------------------

    def _load(self) -> str:
        return self._path.read_text(encoding="utf-8")

    def _save(self, text: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(text, encoding="utf-8")

    # -- section slicing ---------------------------------------------------

    @staticmethod
    def _section_bounds(text: str, section: str) -> tuple[int, int]:
        """Return (start, end) byte offsets of the *body* of ``## section``.

        Only the three known sections (ID Catalog, History, Results) are
        treated as boundaries — any ``## …`` headers that the LLM injects
        inside result bodies are ignored.
        """
        headers = [
            m for m in _SECTION_RE.finditer(text)
            if m.group(1).strip() in _KNOWN_SECTIONS
        ]
        for i, m in enumerate(headers):
            if m.group(1).strip() == section:
                body_start = m.end() + 1  # skip newline after heading
                body_end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
                return body_start, body_end
        raise KeyError(f"Section '## {section}' not found in memory file")

    # -- public API --------------------------------------------------------

    def read(self, section: str | None = None) -> str:
        """Return full file or a specific ``## section`` body."""
        text = self._load()
        if section is None:
            return text
        start, end = self._section_bounds(text, section)
        return text[start:end].strip()

    def append_history(self, line: str) -> None:
        """Append a one-line entry to the History section."""
        text = self._load()
        start, end = self._section_bounds(text, "History")
        body = text[start:end].rstrip()
        new_body = body + "\n" + f"- {line}" + "\n"
        self._save(text[:start] + new_body + "\n" + text[end:])

    @staticmethod
    def _escape_body(body: str) -> str:
        """Downgrade ``## `` headers in *body* to ``### `` to avoid breaking section parsing."""
        return re.sub(r"^## ", "### ", body, flags=re.MULTILINE)

    def add_result(self, key: str, body: str) -> None:
        """Add or replace a ``### key`` entry in the Results section."""
        body = self._escape_body(body)
        text = self._load()
        start, end = self._section_bounds(text, "Results")
        section_body = text[start:end]
        # Replace existing entry with same key (if any)
        key_re = re.compile(
            rf"^### {re.escape(key)}\n.*?(?=^### |\Z)",
            re.MULTILINE | re.DOTALL,
        )
        if key_re.search(section_body):
            new_section = key_re.sub(f"### {key}\n{body}\n", section_body, count=1)
            self._save(text[:start] + new_section + text[end:])
        else:
            existing = section_body.rstrip()
            entry = f"\n### {key}\n{body}\n"
            self._save(text[:start] + existing + entry + "\n" + text[end:])

    # -- catalog ops -------------------------------------------------------

    def catalog_list(self) -> list[dict]:
        """Return all catalog rows as dicts."""
        text = self.read("ID Catalog")
        return [m.groupdict() for m in _CATALOG_ROW_RE.finditer(text)]

    @staticmethod
    def _bare_num_id(num_id) -> int:
        """Coerce *num_id* to a bare integer, stripping any type prefix(es).

        Handles: 63, "63", "comp_63", "prop_1", "comp_comp_116".
        Falls back to extracting the first integer found in the string.
        """
        if isinstance(num_id, int):
            return num_id
        s = str(num_id).strip()
        # Extract trailing integer after the last underscore
        m = re.search(r"_(\d+)$", s)
        if m:
            return int(m.group(1))
        # Fallback: first integer anywhere in the string
        m = re.search(r"(\d+)", s)
        if m:
            return int(m.group(1))
        # Last resort: plain int conversion (may raise ValueError)
        return int(s)

    def catalog_add(self, type_: str, num_id: int, id_: str, name: str) -> None:
        """Add a row to the ID Catalog (no-op if already present).

        Resolved entities (metal, ligand, beta_def, comp, prop, …) go
        under ``### Resolved Entities``.  Reference-only types (vlm, lit,
        network, node) go under ``### Reference IDs``.  Deduplicates by
        ``prefix_id``.
        """
        num_id = self._bare_num_id(num_id)
        prefix_id = f"{type_}_{num_id}"
        existing = self.catalog_list()
        for row in existing:
            if row["num_id"] == prefix_id:
                return  # already present
        text = self._load()
        start, end = self._section_bounds(text, "ID Catalog")
        body = text[start:end]
        new_row = f"| {type_} | {prefix_id} | {id_} | {name} |"

        # Determine target sub-table header
        target_header = _REF_HEADER if type_ in _REF_ONLY_FILE_TYPES else _RESOLVED_HEADER

        # Find the target sub-table within the section body
        header_pos = body.find(target_header)
        if header_pos != -1:
            # Find the last table row in this sub-table (before next ### or section end)
            after_header = header_pos + len(target_header)
            next_sub = body.find("\n###", after_header)
            if next_sub == -1:
                # No further sub-table — insert before section end
                insert_region = body[after_header:]
            else:
                insert_region = body[after_header:next_sub]

            # Find end of last row in the sub-table
            last_pipe = insert_region.rfind("|")
            if last_pipe != -1:
                # Insert after the line containing the last pipe
                nl = insert_region.find("\n", last_pipe)
                if nl == -1:
                    insert_at = after_header + len(insert_region)
                else:
                    insert_at = after_header + nl + 1
            else:
                # Sub-table has header row only, insert after separator
                insert_at = after_header + len(insert_region)

            abs_insert = start + insert_at
            self._save(text[:abs_insert] + new_row + "\n" + text[abs_insert:])
        else:
            # Fallback for old-format files without sub-tables: append at end
            rstripped = body.rstrip()
            self._save(
                text[:start] + rstripped + "\n" + new_row + "\n\n" + text[end:]
            )

    def catalog_remove(self, type_: str, num_id: int) -> None:
        """Remove a row from the ID Catalog by type + num_id."""
        num_id = self._bare_num_id(num_id)
        prefix_id = f"{type_}_{num_id}"
        text = self._load()
        start, end = self._section_bounds(text, "ID Catalog")
        body = text[start:end]
        pattern = re.compile(
            rf"^\|\s*{re.escape(type_)}\s*\|\s*{re.escape(prefix_id)}\s*\|.*\|.*\|\s*$",
            re.MULTILINE,
        )
        new_body = pattern.sub("", body)
        # collapse double blank lines
        new_body = re.sub(r"\n{3,}", "\n\n", new_body)
        self._save(text[:start] + new_body + text[end:])

    # -- compaction --------------------------------------------------------

    def compact_section(
        self, section: str, summariser: Callable[[str], str]
    ) -> None:
        """Replace a section body with a summary produced by *summariser*.

        *summariser* is a callable(str) -> str.  Typically an LLM call that
        condenses the text.  The ID Catalog section is never compactable.
        """
        if section == "ID Catalog":
            raise ValueError("ID Catalog is protected and cannot be compacted")
        text = self._load()
        start, end = self._section_bounds(text, section)
        old_body = text[start:end].strip()
        summary = summariser(old_body)
        self._save(text[:start] + "\n" + summary.strip() + "\n\n" + text[end:])

    # -- reset -------------------------------------------------------------

    def reset(self) -> None:
        """Re-initialise the memory file to the empty template."""
        self._save(_TEMPLATE)
