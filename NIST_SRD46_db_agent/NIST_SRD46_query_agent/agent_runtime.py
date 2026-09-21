#!/usr/bin/env python
"""
SRD-46 agent runtime.

This module owns the terminal-chat runtime, system prompt, MCP tool catalog,
tool-call parsing, and MCP session management for the SRD-46 query agent.

Launch:
    python agent_runtime.py
"""

import json
import io
import logging
import os
import re
import sys
import datetime as dt
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).absolute().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from fastmcp.client.transports import StdioTransport
from fastmcp import Client
import mimetypes
import base64

# =============================================================
#  Logging
# =============================================================
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("SRD46-UI")
# Silence noisy third-party loggers
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("charset_normalizer").setLevel(logging.WARNING)

# =============================================================
#  Shared configuration
# =============================================================
from NIST_SRD46_db_agent.NIST_SRD46_query_agent.argo_config import MODEL
from NIST_SRD46_db_agent.NIST_SRD46_query_agent.terminal_chat import PTK, _append_transcript, _open_transcript, read_user_input

# Phase-gating constants  (enforces preplan -> L0 -> plan -> execution order)
PREPLAN_TOOL_NAME = "0_preplan_decision"
L0_DISCOVERY_TOOLS = {
    "search_metals",
    "search_ligands",
    "build_system_catalog",
}
PLAN_TOOL_NAME = "0_plan_search_strategy"

# Map preplan l0_needed tags → actual tool names
L0_TOOL_TAG_MAP = {
    "search_metals": "search_metals",
    "search_ligands": "search_ligands",
    "build_catalog": "build_system_catalog",
    "build_system_catalog": "build_system_catalog",
}


def _get_attr(obj: Any, key: str, default=None):
    if hasattr(obj, key):
        return getattr(obj, key)
    if isinstance(obj, dict):
        return obj.get(key, default)
    try:
        data = obj.model_dump()
        return data.get(key, default)
    except Exception:
        return default


def file_to_data_url(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    mime = mime or "application/octet-stream"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _build_server_transport() -> StdioTransport:
    return StdioTransport(
        command=sys.executable,
        args=["server.py"],
        env=os.environ.copy(),
        cwd=str(Path(__file__).resolve().parent),
        log_file=_subprocess_log_target(),
    )


def _subprocess_log_target():
    """Return a stderr target that Windows can pass to an MCP subprocess.

    Test runners, notebooks, and orchestration wrappers sometimes replace
    ``sys.stderr`` with an in-memory stream.  Such streams may support
    ``write`` while raising from ``fileno()``, which prevents the local MCP
    server from starting.  Preserve the active stderr when it owns a real
    descriptor, otherwise use the interpreter's original stderr and finally
    the platform null device.
    """
    for stream in (sys.stderr, sys.__stderr__):
        if stream is None:
            continue
        try:
            stream.fileno()
        except (AttributeError, io.UnsupportedOperation, OSError, ValueError):
            continue
        return stream
    return Path(os.devnull)


async def list_mcp_tools(client: Client) -> List[Dict[str, Any]]:
    tools = await client.list_tools()
    out: List[Dict[str, Any]] = []
    for t in tools:
        schema = _get_attr(t, "input_schema", None) or _get_attr(t, "inputSchema", None)
        if schema is not None and hasattr(schema, "model_dump"):
            schema = schema.model_dump()
        out.append({
            "name": _get_attr(t, "name"),
            "description": _get_attr(t, "description", ""),
            "input_schema": schema or {},
        })
    return out


def infer_required_l0_tools(preplan_result: str) -> set:
    """Parse preplan JSON result and return the set of L0 tools needed.

    Falls back to ALL L0 tools if parsing fails.
    """
    import json as _json
    try:
        # Strip "[PREPLAN]\n" prefix
        body = preplan_result
        if body.startswith("[PREPLAN]"):
            body = body[body.index("\n") + 1:]
        data = _json.loads(body)
        tags = data.get("l0_needed", None)
        if tags is None:
            # Fallback: infer from metals/ligands lists
            needed = set()
            if data.get("metals"):
                needed.add("search_metals")
            if data.get("ligands"):
                needed.add("search_ligands")
            if data.get("metals") and data.get("ligands"):
                needed.add("build_system_catalog")
            return needed
        return {L0_TOOL_TAG_MAP[t] for t in tags if t in L0_TOOL_TAG_MAP}
    except Exception:
        return set(L0_DISCOVERY_TOOLS)  # safe fallback


# =============================================================
#  Build tool catalog from FastMCP docstrings (auto-generated)
# =============================================================
import asyncio
from NIST_SRD46_db_agent.NIST_SRD46_query_agent.server import mcp as _mcp


def _run_coro_sync(coro):
    """Run an async coroutine synchronously, even when called from inside a
    running event loop (e.g. Jupyter, IPython, or any host that has already
    started asyncio).

    Strategy:
      1. If no loop is currently running -> use ``asyncio.run`` (fast path).
      2. Otherwise run the coroutine in a worker thread with its own loop
         and join on it. This avoids the ``RuntimeError: asyncio.run()
         cannot be called from a running event loop`` that ``asyncio.run``
         raises in nested contexts.
    """
    try:
        asyncio.get_running_loop()
        loop_running = True
    except RuntimeError:
        loop_running = False

    if not loop_running:
        return asyncio.run(coro)

    import threading
    box: dict = {}

    def _runner():
        try:
            box["v"] = asyncio.run(coro)
        except BaseException as exc:  # noqa: BLE001
            box["err"] = exc

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    t.join()
    if "err" in box:
        raise box["err"]
    return box["v"]

# Pull the SQL-WHERE "manual" once — it is appended to ~8 tool docstrings by
# NIST_SRD46_core_db_search_tools/__init__.py so non-agent MCP clients see it per-tool.
# For the agent's SYSTEM_PROMPT we want to inject it ONCE (saves ~28 KB),
# so we strip it from each tool description and append a single copy below
# the TOOLS section.
from NIST_SRD46_core_db_search_tools._search_helpers import (
    WHERE_NORMALIZATION_NOTES as _WHERE_NOTES,
)
_WHERE_NOTES_STRIPPED = _WHERE_NOTES.strip()


def _strip_shared_where_notes(description: str) -> str:
    """Remove the appended WHERE_NORMALIZATION_NOTES block from a tool docstring."""
    if not description:
        return description
    idx = description.find(_WHERE_NOTES_STRIPPED)
    if idx < 0:
        return description
    return description[:idx].rstrip()


def _build_tool_catalog() -> tuple[str, set[str]]:
    """Pull tool names, descriptions, and parameter schemas from FastMCP
    and format them as a compact reference for the system prompt.

    The shared SQL-WHERE manual is stripped per-tool and injected once
    into SYSTEM_PROMPT below, to avoid ~28 KB of repetition across the
    8 SQL-WHERE-aware tools.
    """
    tools = _run_coro_sync(_mcp.list_tools())
    lines = []
    tool_names = set()
    for t in sorted(tools, key=lambda x: x.name):
        tool_names.add(t.name)
        # Build typed signature
        params = t.inputSchema.get("properties", {})
        required = set(t.inputSchema.get("required", []))
        param_parts = []
        for pname, pinfo in params.items():
            ptype = pinfo.get("type", "any")
            suffix = "" if pname in required else "?"
            param_parts.append(f"{pname}{suffix}: {ptype}")
        sig = ", ".join(param_parts)
        lines.append(f"  {t.name}({sig})")
        # Full docstring — indent every line for readability
        raw = _strip_shared_where_notes((t.description or "").strip())
        for dline in raw.splitlines():
            stripped = dline.strip()
            if stripped:
                lines.append(f"    {stripped}")
    return "\n".join(lines), tool_names


_TOOL_CATALOG, _AVAILABLE_TOOL_NAMES = _build_tool_catalog()


def _tool_enabled(tool_name: str) -> bool:
    return tool_name in _AVAILABLE_TOOL_NAMES


_SQL_WHERE_NOTE_TOOLS = [
    "search_stability",
    "search_pka_values",
    "search_pka_ligands",
    "search_networks",
    "db_count_records",
    "db_distribution",
    "db_ranked_pairs",
]
if _tool_enabled("execute_srd46_sql"):
    _SQL_WHERE_NOTE_TOOLS.append("execute_srd46_sql")

_EXECUTION_TOOL_ORDER = [
    "search_stability",
    "search_pka_values",
    "search_pka_ligands",
    "search_networks",
    "search_citations",
    "inspect_card",
    "inspect_literature",
    "db_count_records",
    "db_distribution",
    "db_ranked_pairs",
    "get_table_schema",
    "execute_srd46_sql",
    "search_similar_ligands",
]
_ENABLED_EXECUTION_TOOLS = [
    tool_name for tool_name in _EXECUTION_TOOL_ORDER if _tool_enabled(tool_name)
]

_GLOBAL_RULES = [
    "Never invent numeric values; all factual claims must come from tool results.",
    "Empty result [] means no matching SRD-46 data was found.",
]
if _tool_enabled("execute_srd46_sql"):
    _GLOBAL_RULES.append("Prefer the domain tools over raw SQL.")
    _GLOBAL_RULES.append("If you must use execute_srd46_sql, call get_table_schema first.")
else:
    _GLOBAL_RULES.append("Prefer the domain tools over lower-level database utilities.")
    
_GLOBAL_RULES.extend([
    "For shortcut-code or paper lookups, use search_citations first; do not inspect schema unless search_citations cannot answer.",
    "Final answers should be concise Markdown and cite SRD-46 as the source.",
    "When data supports it, feel free to add 2~3 sentences of chemistry insight (trends, anomalies, or real-world relevance) grounded in the retrieved numbers.",
    "ALWAYS use Markdown tables (| col1 | col2 | ... |) when presenting numeric data, stability constants, conditions, or any structured/comparative results. Never use bullet-point lists for tabular data.",
    "Final numeric values are regex-validated against raw tool results. Quote exact rows/values from tool output; if a value is uncertain, do a narrower follow-up search instead of approximating.",
])
_GLOBAL_RULES_TEXT = "".join(
    f"{idx}. {rule}\n" for idx, rule in enumerate(_GLOBAL_RULES, start=1)
)

# =============================================================
#  System prompt  (auto-built from FastMCP tool catalog)
# =============================================================
SYSTEM_PROMPT = (
    "You are a subagent that answers and explores chemistry questions by querying "
    "NIST SRD-46 database with tools. Have a fun time exploring chemical data!\n\n"

    "TOOL CALL FORMAT:\n"
    "Emit a single <tool_call> block and then stop.\n"
    "Use either a single JSON object or a JSON list of objects:\n"
    "<tool_call>{\"name\": \"tool_name\", \"arguments\": {...}}</tool_call>\n"
    "<tool_call>[{\"name\": \"tool_a\", \"arguments\": {...}}, "
    "{\"name\": \"tool_b\", \"arguments\": {...}}]</tool_call>\n"
    "Multiple tool calls in one turn are allowed only when they are independent "
    "and belong to the same workflow phase.\n\n"

    "MEMORY COMPRESSION:\n"
    "Older tool results are automatically compacted between iterations to keep "
    "context bounded. You will be consulted on which results to compress and "
    "asked to validate summaries.\n\n"

    "TOOLS:\n"
    + _TOOL_CATALOG
    + "\n\n"

    "SQL-WHERE NOTES (applies to "
    + ", ".join(_SQL_WHERE_NOTE_TOOLS)
    + "):\n"
    + _WHERE_NOTES_STRIPPED
    + "\n\n"

    "PREFIXED IDs:\n"
    "All entity IDs use a canonical prefix: metal_N, ligand_N, vlm_N, beta_def_N."
    "Always use these prefixed forms when passing IDs between tools."
    "SQL-WHERE accepts and auto-resolves prefixed forms (c.metal_id = metal_41 → 41).\n\n"

    "GLOBAL RULES:\n"
    + _GLOBAL_RULES_TEXT
    + "\n"

    "MANDATORY WORKFLOW:\n"
    "PHASE 0 — TRIAGE:\n"
    "  Call 0_preplan_decision first with the user's question.\n"
    "  It returns task_type, metals, ligands, l0_needed, and notes.\n\n"
    "PHASE 1 — DISCOVERY:\n"
    "  Call only the required L0 tools from l0_needed:\n"
    "  - search_metals\n"
    "  - search_ligands\n"
    "  - build_system_catalog\n"
    "  If l0_needed is empty, skip this phase.\n"
    "  search_metals and search_ligands are independent — emit them together "
    "in one <tool_call> array to resolve both in parallel. "
    "build_system_catalog must run after them (it needs resolved IDs).\n\n"
    "PHASE 2 — PLAN:\n"
    "  Call 0_plan_search_strategy after the required L0 work is done.\n"
    "  The plan is advisory. You still choose the exact tool calls.\n"
    "  If l0_needed was empty (no discovery needed), you may skip this phase "
    "and go straight to execution.\n\n"
    "PHASE 3 — EXECUTION:\n"
    "  Use the execution tools as needed: "
    + ", ".join(_ENABLED_EXECUTION_TOOLS)
    + ".\n"
    "  You may re-run search_metals or search_ligands later if you discover new entities.\n"
    "  **Parallel execution:** You may emit multiple independent tools as a JSON array in a single <tool_call> block."
    "They will run concurrently to save time. Only group tools that do NOT depend on each other's results.\n"
)


# =============================================================
#  Tool-call parser & executor
# =============================================================

TOOL_CALL_PATTERN = re.compile(
    # r"<tool_call>\s*(\{.*?\})\s*</tool_call>",
    r"<tool_call>\s*(\[.*?\]|\{.*?\})\s*</tool_call>",  # <----SIGNATURE CHANGED
    re.DOTALL,
)

# Fallback: bare JSON tool call without XML tags (ChatGPT-style output)
BARE_TOOL_CALL_PATTERN = re.compile(
    r'\{"name"\s*:\s*"([^"]+)"\s*,\s*"arguments"\s*:\s*(\{[^}]*\})\s*\}',
)


def extract_tool_call(text: str) -> Optional[Any]:
    """Return the first <tool_call> block as parsed JSON, or None.

    Falls back to detecting bare JSON ``{"name":..., "arguments":...}``
    when the model omits the XML wrapper.
    """
    m = TOOL_CALL_PATTERN.search(text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError as e:
            log.warning("[!] Failed to parse tool_call JSON: %s", e)
            return None

    # Fallback: bare JSON tool call (no XML tags)
    m2 = BARE_TOOL_CALL_PATTERN.search(text)
    if m2:
        try:
            obj = json.loads(m2.group(0))
            if "name" in obj and "arguments" in obj:
                log.info("[!] Detected bare JSON tool call (no XML tags): %s",
                         obj.get("name"))
                return obj
        except json.JSONDecodeError:
            pass
    return None


def coerce_tool_calls(parsed_call: Any) -> List[dict]:
    """Normalize parsed tool-call JSON into a list of call dicts."""
    if parsed_call is None:
        return []
    if isinstance(parsed_call, dict):
        return [parsed_call]
    if isinstance(parsed_call, list):
        return [item for item in parsed_call if isinstance(item, dict)]
    return []


def mark_plans_complete(memory: List[Dict[str, str]]) -> None:
    """Mark all active [PLAN] entries as [PLAN:DONE] so they become compressible.

    Called when the agent produces a final answer — the plan has been
    executed (or abandoned) and can now be summarised by the compactor
    in future turns.
    """
    for turn in memory:
        if turn["role"] == "user" and "<tool_result>" in turn["content"]:
            c = turn["content"]
            # Only promote [PLAN] that is NOT already [PLAN:DONE]
            if "[PLAN]\n" in c and "[PLAN:DONE]" not in c:
                turn["content"] = c.replace("[PLAN]\n", "[PLAN:DONE]\n", 1)
                log.info("[P] Promoted [PLAN] → [PLAN:DONE] in memory")


class _ToolErrorResult:
    """Lightweight stand-in for an MCP result when a tool call fails."""
    def __init__(self, tool_name: str, exc: Exception):
        self.tool_name = tool_name
        self.is_error = True

        class _TextContent:
            def __init__(self, text):
                self.text = text
        self.content = [_TextContent(f"[TOOL ERROR] {tool_name}: {exc}")]


class MCPManager:
    def __init__(self):
        self.tools0: List[Dict[str, Any]] = []
        self.tools1: List[Dict[str, Any]] = []
        self.mcp_client0: Client | None = None
        self.mcp_client1: Client | None = None
        self.tool_index: Dict[str, tuple[Dict[str, Any], Client]] = {}
        self.tools: List[Dict[str, Any]] = []

    async def setup(self):
        # Magnet MCP
        transport0 = _build_server_transport()
        self.mcp_client0 = await Client(transport0).__aenter__()
        self.tools0 = await list_mcp_tools(self.mcp_client0)

        # MCP server 2 optional
        # transport1 = StdioTransport(command='python', args=['server2.py'])
        # self.mcp_client1 = await Client(transport1).__aenter__()
        # self.tools1 = await list_mcp_tools(self.mcp_client1)

        # Combine tools
        self.tools = self.tools0  # + self.tools1
        self.tool_index = {t["name"]: (t, self.mcp_client0) for t in self.tools0}
        # self.tool_index.update({t["name"]: (t, self.mcp_client1) for t in self.tools1})

        return self.tools, self.tool_index

    async def call_tool(self, tool_name, args):
        if self.mcp_client0 is None:
            raise RuntimeError("MCPManager.setup() must be called before call_tool().")

        if any(tool['name'] == tool_name for tool in self.tools0):
            result = await self.mcp_client0.call_tool(tool_name, args)
        # elif any(tool['name'] == tool_name for tool in self.tools1):
        #     result = await self.mcp_client1.call_tool(tool_name, args)
        else:
            raise ValueError(f"Tool {tool_name} not found")

        return result

    async def call_tool_safe(self, tool_name, args):
        """Like call_tool but returns a ToolErrorResult on failure instead of raising."""
        try:
            return await self.call_tool(tool_name, args)
        except Exception as exc:
            return _ToolErrorResult(tool_name, exc)

    async def close(self):
        if self.mcp_client0 is not None:
            await self.mcp_client0.__aexit__(None, None, None)
            self.mcp_client0 = None
        if self.mcp_client1 is not None:
            await self.mcp_client1.__aexit__(None, None, None)
            self.mcp_client1 = None


# =============================================================
#  Verdict agent  (independent post-run review)  → postjob_verdict.py
# =============================================================
from NIST_SRD46_db_agent.NIST_SRD46_query_agent.SRD46_tools.postjob_verdict import run_verdict_agent as _run_verdict_agent

# =============================================================
#  Terminal chat loop
# =============================================================

async def run_terminal_chat():
    from NIST_SRD46_db_agent.NIST_SRD46_query_agent.query_agent import agent_turn

    transcript = _open_transcript()
    memory: List[Dict[str, str]] = []

    print()
    print("+----------------------------------------------------------+")
    print("|      SRD-46 Terminal Chatbot  (Argo + MCP Tools)         |")
    print("+----------------------------------------------------------+")
    print()
    print(f"  Model     : {MODEL}")
    print(f"  Transcript: {transcript}")
    print()
    if PTK:
        print("  [Enter]   -> new line")
        print("  [Ctrl+S]  -> send message")
        print("  Type 'exit' -> quit\n")
    else:
        print("  (prompt_toolkit not found -- single-line mode)")
        print("  Type 'exit' to quit.\n")

    '''SETTING UP LLM ENGINE HERE'''
    # llm_engine = LLMEngine()
    # await llm_engine.startup()

    while True:
        # user_input = read_user_input()
        user_input = await asyncio.to_thread(read_user_input)
        if user_input.lower() in {"exit", "quit", "q"}:
            print("\nGoodbye!")
            break
        if not user_input:
            continue

        _append_transcript(transcript, "User", user_input)

        try:
            # answer = await llm_engine.query(user_input)
            answer = await agent_turn(user_input, memory)
        except Exception as e:
            log.exception("Fatal error in agent_turn")
            print(f"\n[X] Error: {e}\n")
            continue

        # --- Verdict agent (independent, not time-limited) -----------
        # try:
        #     verdict = _run_verdict_agent(
        #         user_input, memory, answer,
        #         call_argo=call_argo,
        #         extract_tool_call=extract_tool_call,
        #         verdict_model=VERDICT_MODEL,
        #     )
        # except Exception as e:
        #     log.warning("[V] Verdict agent error: %s", e)
        #     verdict = f"(Verdict unavailable: {e})"

        print(f"\n{'-' * 60}")
        print("Argo:\n")
        print(answer)
        print(f"\n{'.' * 60}")
        # print(f"Verdict Agent:\n")
        # print(verdict)
        print(f"{'-' * 60}\n")

        # _append_transcript(transcript, "Assistant", answer)
        # _append_transcript(transcript, "Verdict", verdict)


# =============================================================
if __name__ == "__main__":
    try:
        asyncio.run(run_terminal_chat())
    except Exception as e:
        print(f"Fatal: {e}", file=sys.stderr)
        sys.exit(1)
