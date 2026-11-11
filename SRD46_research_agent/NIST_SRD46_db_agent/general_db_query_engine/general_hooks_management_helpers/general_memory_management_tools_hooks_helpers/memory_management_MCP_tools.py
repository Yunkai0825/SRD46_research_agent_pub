"""MCP tool definitions that wrap WorkingMemory operations.

Each function below is designed to be registered as an MCP tool that the
L0 orchestrator can call.  They all operate on a single ``WorkingMemory``
instance whose path is set at module level via ``init(path)``.

Public API (MCP tool signatures)
---------------------------------
memory_read(section=None) -> str
memory_append_history(line) -> str
memory_add_result(key, body) -> str
memory_catalog_add(type, num_id, id, name) -> str
memory_catalog_remove(type, num_id) -> str
memory_catalog_list() -> str
memory_compact(section) -> str
memory_reset() -> str
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from .memory_local_storage_io import WorkingMemory

# Thread-local memory instance — each thread gets its own WorkingMemory
# so that parallel test prompts don't clobber each other's paths.
_tls = threading.local()


def init(path: str | Path) -> None:
    """Initialise the WorkingMemory instance for the current thread."""
    wm = WorkingMemory(path)
    _tls.mem = wm


def _require_mem() -> WorkingMemory:
    mem = getattr(_tls, "mem", None)
    if mem is None:
        raise RuntimeError("Memory not initialised — call init(path) first")
    return mem


# ---------------------------------------------------------------------------
# MCP tool implementations
# ---------------------------------------------------------------------------

def memory_read(section: str | None = None) -> str:
    """Read the full working memory or a specific section.

    Parameters
    ----------
    section : str, optional
        One of "ID Catalog", "History", "Results".
        If omitted, returns the entire file.
    """
    mem = getattr(_tls, "mem", None)
    if mem is None:
        return ""
    return mem.read(section)


def memory_append_history(line: str) -> str:
    """Append a one-line entry to the History section.

    Parameters
    ----------
    line : str
        Single-line summary of an action/result.
    """
    _require_mem().append_history(line)
    return "OK"


def memory_add_result(key: str, body: str) -> str:
    """Add a named result entry to the Results section.

    Parameters
    ----------
    key : str
        Result identifier (e.g. "result_1", "hexane_vle").
    body : str
        Markdown body of the result.
    """
    _require_mem().add_result(key, body)
    return "OK"


def memory_catalog_add(type_: str, num_id: int, id_: str, name: str) -> str:
    """Add a row to the protected ID Catalog.

    Parameters
    ----------
    type_ : str
        Entity type: comp, prop, meas, var, constr, ref, phase, solvent.
    num_id : int
        Numeric identifier (bare integer — any type prefix is stripped).
    id_ : str
        String identifier (e.g. "hexane", "activity_coefficient_<comp_id>").
    name : str
        Human-readable name.
    """
    # catalog_add now sanitises num_id internally
    _require_mem().catalog_add(type_, num_id, id_, name)
    return "OK"


def memory_catalog_remove(type_: str, num_id: int) -> str:
    """Remove a row from the ID Catalog.

    Parameters
    ----------
    type_ : str
        Entity type.
    num_id : int
        Numeric identifier to remove (bare integer — any type prefix is stripped).
    """
    _require_mem().catalog_remove(type_, num_id)
    return "OK"


def memory_catalog_list() -> str:
    """List all entries in the ID Catalog as JSON."""
    rows = _require_mem().catalog_list()
    return json.dumps(rows, indent=2)


def memory_compact(section: str, summary_text: str | None = None) -> str:
    """Compact a section by replacing it with a summary.

    Parameters
    ----------
    section : str
        Section name ("History" or "Results"). ID Catalog cannot be compacted.
    summary_text : str, optional
        Pre-computed summary.  If provided, used directly instead of calling
        an external summariser.  This allows the LLM orchestrator to produce
        the summary itself and pass it in.
    """
    if summary_text is not None:
        _require_mem().compact_section(section, lambda _: summary_text)
    else:
        raise ValueError(
            "summary_text is required — the MCP tool does not call LLMs "
            "directly.  The orchestrator should produce the summary."
        )
    return "OK"


def memory_reset() -> str:
    """Reset the working memory to an empty template."""
    _require_mem().reset()
    return "OK"


# ---------------------------------------------------------------------------
# Tool catalog for MCP registration
# ---------------------------------------------------------------------------

TOOL_CATALOG: list[dict[str, Any]] = [
    {
        "name": "memory_read",
        "function": memory_read,
        "description": "Read the full working memory or a specific section.",
        "parameters": {
            "section": {
                "type": "string",
                "description": "Section name (ID Catalog / History / Results). Omit for full file.",
                "required": False,
            },
        },
    },
    {
        "name": "memory_append_history",
        "function": memory_append_history,
        "description": "Append a one-line entry to the History section.",
        "parameters": {
            "line": {"type": "string", "description": "Action summary.", "required": True},
        },
    },
    {
        "name": "memory_add_result",
        "function": memory_add_result,
        "description": "Add a named result entry to the Results section.",
        "parameters": {
            "key": {"type": "string", "description": "Result key.", "required": True},
            "body": {"type": "string", "description": "Markdown body.", "required": True},
        },
    },
    {
        "name": "memory_catalog_add",
        "function": memory_catalog_add,
        "description": "Add a row to the protected ID Catalog.",
        "parameters": {
            "type_": {"type": "string", "description": "Entity type.", "required": True},
            "num_id": {"type": "integer", "description": "Numeric id.", "required": True},
            "id_": {"type": "string", "description": "String id.", "required": True},
            "name": {"type": "string", "description": "Human name.", "required": True},
        },
    },
    {
        "name": "memory_catalog_remove",
        "function": memory_catalog_remove,
        "description": "Remove a row from the ID Catalog.",
        "parameters": {
            "type_": {"type": "string", "description": "Entity type.", "required": True},
            "num_id": {"type": "integer", "description": "Numeric id.", "required": True},
        },
    },
    {
        "name": "memory_catalog_list",
        "function": memory_catalog_list,
        "description": "List all entries in the ID Catalog as JSON.",
        "parameters": {},
    },
    {
        "name": "memory_compact",
        "function": memory_compact,
        "description": "Replace a section with a pre-computed summary.",
        "parameters": {
            "section": {"type": "string", "description": "Section name.", "required": True},
            "summary_text": {"type": "string", "description": "Summary to replace section.", "required": True},
        },
    },
    {
        "name": "memory_reset",
        "function": memory_reset,
        "description": "Reset working memory to empty template.",
        "parameters": {},
    },
]
