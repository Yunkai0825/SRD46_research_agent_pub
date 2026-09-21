"""
Shared agentic subagent — tool-level ReAct KEEP/DISCARD compaction.
====================================================================
Parametrised implementation used by **both** the query agent and the
analysis agent.  Each provides its own ``client_factory`` (lazy LLM
client) and ``cfg`` (AGENT_CONFIG with SUBAGENT_* fields).

The subagent receives:
  - compact markdown produced by hardcoded compactors
  - the caller tool's PURPOSE and TASKS

…and decides whether to KEEP (extract structured data) or DISCARD
(explain + suggest refinement).

Thread-safe: no module-level mutable state.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict

from ...general_hooks_management_helpers.general_context_hooks.history_tracking_hooks import (
    history_recorder as _history_recorder,
)
from ...general_hooks_management_helpers.general_context_hooks.stats_references_tracking_hooks import (
    recorder as _stats_recorder,
)

log = logging.getLogger("agentic-subagent")


# ═══════════════════════════════════════════════════════════════
#  ToolResult — returned by wrapped tools when subagent is active
# ═══════════════════════════════════════════════════════════════

@dataclass
class ToolResult:
    """Carries both the raw dict (for working memory) and the subagent
    text (for the main agent's conversation context).

    ``agent_turn`` will call ``str(result)`` for non-dict, non-str
    return values, which triggers ``__str__`` → ``.text``.

    If the subagent chose to DISCARD, ``discarded`` is True and
    ``.text`` contains an explanation + refinement suggestion.
    """
    raw: dict
    text: str
    discarded: bool = False

    def __str__(self) -> str:
        return self.text


# ═══════════════════════════════════════════════════════════════
#  ReAct-style subagent system prompt (built per-call)
# ═══════════════════════════════════════════════════════════════

def _build_system_prompt(max_tokens: int, pipeline_label: str) -> str:
    return f"""\
You are a data-extraction subagent inside a ThermoML thermodynamic
{pipeline_label} pipeline, **with your answers parsed by hardcoded parsers**.  You receive:

- **PURPOSE**: Why the main agent called this tool.
- **TASKS**: What specific information to extract and highlight.
- **RAW DATA**: The tool output, already compacted to markdown.

You MUST follow this ReAct loop:

### Step 1 — Thought  (wrapped in <thought>...</thought>)
Reason about the RAW DATA:
- Does it contain what PURPOSE and TASKS ask for?
- Are there errors, missing fields, or unexpected values?
- Is the data usable, or should the main agent retry with different parameters?

### Step 2 — Action  (one line: <action>KEEP</action> or <action>DISCARD</action>)

### Step 3 — Output

**If KEEP:**
1. A 1-2 short paragraphs of **summary/verdict** answering PURPOSE & TASKS.  Preserve key
   num_ids (with names), DOI, block_number, and identifiers that map to raw data.
2. If applicable, 1-3 **markdown tables or JSON snippets** with the structured data
   requested by TASKS.  Must preserve exact numeric values (DOIs, block
   numbers, IDs, coefficients, R², RMSE, pure-component values, temperatures).
3. A **Referenced entity IDs** section listing the entity prefixed_ids
   (formatted as ``type_N``, e.g. ``metal_41``, ``ligand_5760``,
   ``vlm_93847``, ``beta_def_12``, ``lit_790``, ``ref_eq_net_29749``) that appear in the RAW DATA and are
   relevant to PURPOSE/TASKS.  Split into two sub-tables:

   ### Referenced entity IDs
   #### Resolved entities
   | type | prefix_id | name | detail |
   |------|-----------|------|--------|
   (Entities whose human-readable name/description appears in the data.
   Include the name and any defining detail — SMILES, formula, equation,
   HxL definition, etc.  One row per unique entity.)

   #### Reference IDs
   | type | prefix_id |
   |------|-----------|
   (IDs that appear in the data but have no additional name or detail
   to resolve — measurement IDs, literature IDs, network IDs, etc.)

   Include ONLY IDs that actually appear in the RAW DATA tables.
   Do NOT fabricate or infer IDs.  Omit this section if no prefixed
   IDs are present.

**If DISCARD:**
1. A 1-2 sentence **explanation** of why the result is not useful.
2. A 1-2 sentence **refinement suggestion** — what the main agent should change
   (different parameters, alternative tool, broader/narrower query, etc.)
   to get a usable result.

Rules:
- Include ONLY key identifiers and data relevant to TASKS — omit irrelevant columns.
- Do NOT add interpretation beyond what the raw data shows.
- STRICTLY based on the RAW DATA — no outside knowledge or assumptions.
- Keep total output ≤ {max_tokens} tokens (tables count toward limit).
"""


# ═══════════════════════════════════════════════════════════════
#  Parsing helpers
# ═══════════════════════════════════════════════════════════════

_THOUGHT_RE = re.compile(r"<thought>(.*?)</thought>", re.DOTALL)
_ACTION_RE  = re.compile(r"<action>\s*(KEEP|DISCARD)\s*</action>", re.IGNORECASE)


def parse_subagent_response(text: str) -> tuple[str, str, str]:
    """Parse a ReAct subagent response into (thought, action, output).

    Returns
    -------
    thought : str
        Content of the <thought> block (empty if absent).
    action : str
        'KEEP' or 'DISCARD' (defaults to 'KEEP' if tag is missing).
    output : str
        Everything after the <action> tag.
    """
    thought = ""
    m = _THOUGHT_RE.search(text)
    if m:
        thought = m.group(1).strip()

    action = "KEEP"  # default — treat missing tag as keep
    m_act = _ACTION_RE.search(text)
    if m_act:
        action = m_act.group(1).upper()

    # Output = everything after the action tag (or after thought if no action)
    if m_act:
        output = text[m_act.end():].strip()
    elif m:
        output = text[m.end():].strip()
    else:
        output = text.strip()

    return thought, action, output


# ═══════════════════════════════════════════════════════════════
#  Subagent call — parametrised core
# ═══════════════════════════════════════════════════════════════

def call_tool_subagent(
    tool_name: str,
    purpose: str,
    tasks: str,
    compact_md: str,
    raw: dict,
    *,
    client_factory: Callable,
    cfg: Any,
    pipeline_label: str = "query",
    reasoning_hook: Callable[[str, str], None] | None = None,
) -> ToolResult:
    """Send (purpose, tasks, compact_md) to a ReAct-style LLM subagent.

    Parameters
    ----------
    tool_name : str
        Name of the calling tool (for logging).
    purpose : str
        1-2 paragraph explanation of *why* the main agent is calling.
    tasks : str
        1-2 paragraph description of *what* to extract.
    compact_md : str
        Hardcoded markdown compaction of the raw result.
    raw : dict
        The original raw dict (preserved for working memory).
    client_factory : callable
        ``() -> ArgoClient`` — lazy constructor for the LLM client.
    cfg : object
        Agent config with attrs: SUBAGENT_CHAR_LIMIT,
        SUBAGENT_MAX_TOKENS.
    pipeline_label : str
        ``"query"`` or ``"analysis"`` — inserted into the system prompt.

    Returns
    -------
    ToolResult
        ``.raw`` = original dict, ``.text`` = subagent output,
        ``.discarded`` = True if subagent chose DISCARD.
    """
    # ── Oversized-result guard ────────────────────────────────
    _CHAR_LIMIT = cfg.SUBAGENT_CHAR_LIMIT
    if len(compact_md) > _CHAR_LIMIT:
        est_tokens = len(compact_md) // 4
        table_rows = sum(1 for ln in compact_md.splitlines()
                         if ln.strip().startswith("|"))
        key_lines = []
        for k, v in raw.items():
            if isinstance(v, list):
                key_lines.append(f"  - `{k}`: list[{len(v)}]")
            elif isinstance(v, dict):
                key_lines.append(f"  - `{k}`: dict({len(v)} keys)")
            elif isinstance(v, str):
                key_lines.append(f"  - `{k}`: str({len(v)} chars)")
            else:
                key_lines.append(f"  - `{k}`: {type(v).__name__}")
        preview = compact_md[:500]
        if len(compact_md) > 500:
            preview += "\n... (truncated)"
        notice = (
            f"**Tool `{tool_name}` result too large for subagent "
            f"(~{est_tokens:,} tokens / {len(compact_md):,} chars "
            f"after hardcoded compaction).**\n\n"
            f"### Result Stats\n"
            f"- **After compaction:** {len(compact_md):,} chars (~{est_tokens:,} tokens)\n"
            f"- **Markdown table rows:** {table_rows}\n"
            f"- **Top-level keys:**\n" + "\n".join(key_lines) + "\n"
            f"\n### Preview (first 500 chars)\n```\n{preview}\n```\n\n"
            f"**Action required:** Narrow the query (add filters, reduce limit) "
            f"to bring the result under ~10k tokens, or call a more specific tool."
        )
        log.warning(
            "Skipping subagent for %s: compact_md=%d chars (limit=%d)",
            tool_name, len(compact_md), _CHAR_LIMIT,
        )
        # Real-time history: oversized guard
        try:
            _history_recorder.log_oversized_guard(tool_name, len(compact_md), notice[:500])
            _history_recorder.log_subagent_event(
                tool_name=tool_name, event="OVERSIZED",
                detail=f"compact_md={len(compact_md):,} chars > limit={_CHAR_LIMIT:,}",
                output_chars=len(notice),
            )
        except Exception as exc:
            log.error("Failed to record oversized guard for %s: %s", tool_name, exc, exc_info=True)
        return ToolResult(raw=raw, text=notice)

    # ── Extract error/query context from raw dict ──────────
    _ctx_parts = []
    if isinstance(raw, dict):
        if raw.get("error"):
            _ctx_parts.append(f"**Error from tool:** {raw['error']}")
        if raw.get("n_results") == 0:
            _ctx_parts.append("**Note:** Tool returned 0 results.")
        qp = raw.get("query_params")
        if qp:
            qp_str = json.dumps(qp, indent=2, default=str, ensure_ascii=False)
            _ctx_parts.append(f"**Query parameters used:**\n```json\n{qp_str}\n```")
    _context_block = ("### CONTEXT\n" + "\n".join(_ctx_parts) + "\n\n") if _ctx_parts else ""

    prompt = (
        f"## Tool: `{tool_name}`\n\n"
        f"### PURPOSE\n{purpose}\n\n"
        f"### TASKS\n{tasks}\n\n"
        f"{_context_block}"
        f"### RAW DATA\n{compact_md}"
    )

    system = _build_system_prompt(cfg.SUBAGENT_MAX_TOKENS, pipeline_label)

    try:
        _sa_t0 = time.perf_counter()
        response = client_factory().call(
            prompt,
            system,
            max_tokens=cfg.SUBAGENT_MAX_TOKENS,
        )
        _sa_elapsed = time.perf_counter() - _sa_t0

        # ── Record compactor reasoning before stripping ───────
        if reasoning_hook is not None:
            try:
                reasoning_hook(f"subagent/{tool_name}", response)
            except Exception as exc:
                log.error("Reasoning hook failed for %s: %s", tool_name, exc, exc_info=True)

        thought, action, output = parse_subagent_response(response)

        if thought:
            log.info("Subagent thought for %s: %.120s...", tool_name, thought)

        if action == "DISCARD":
            log.info(
                "Subagent DISCARDED %s result (%d chars). Reason: %.120s",
                tool_name, len(compact_md), output[:120],
            )
            # Side-logging subagent verdict
            try:
                _stats_recorder.log_subagent_verdict(
                    tool_name=tool_name,
                    verdict="DISCARD",
                    subagent_output_chars=len(output),
                    subagent_elapsed_s=round(_sa_elapsed, 1),
                )
            except Exception as exc:
                log.error("Failed to record DISCARD verdict for %s: %s", tool_name, exc, exc_info=True)
            discard_text = (
                f"**\u26a0 Tool `{tool_name}` result discarded by subagent.**\n\n"
                f"{output}"
            )
            # Real-time history: subagent DISCARD
            try:
                _history_recorder.log_subagent_event(
                    tool_name=tool_name, event="DISCARD",
                    detail=output[:200], output_chars=len(discard_text),
                    elapsed_s=round(_sa_elapsed, 1),
                )
            except Exception as exc:
                log.error("Failed to record DISCARD history for %s: %s", tool_name, exc, exc_info=True)
            return ToolResult(raw=raw, text=discard_text, discarded=True)

        # KEEP path
        log.info(
            "Subagent for %s returned %d chars (KEEP)",
            tool_name, len(output),
        )
        # Side-logging subagent verdict
        try:
            _stats_recorder.log_subagent_verdict(
                tool_name=tool_name,
                verdict="KEEP",
                subagent_output_chars=len(output),
                subagent_elapsed_s=round(_sa_elapsed, 1),
            )
        except Exception as exc:
            log.error("Failed to record KEEP verdict for %s: %s", tool_name, exc, exc_info=True)
        # Real-time history: subagent KEEP
        try:
            _history_recorder.log_subagent_event(
                tool_name=tool_name, event="KEEP",
                detail=output[:200], output_chars=len(output),
                elapsed_s=round(_sa_elapsed, 1),
            )
        except Exception as exc:
            log.error("Failed to record KEEP history for %s: %s", tool_name, exc, exc_info=True)
        return ToolResult(raw=raw, text=output)

    except Exception as e:
        log.warning("Subagent call failed for %s: %s", tool_name, e, exc_info=True)
        # Graceful fallback: return the compacted markdown directly
        text = f"**[Subagent unavailable — raw compact result]**\n\n{compact_md}"
        # Real-time history: subagent FALLBACK
        try:
            _history_recorder.log_subagent_event(
                tool_name=tool_name, event="FALLBACK",
                detail=str(e)[:200], output_chars=len(text),
            )
        except Exception as exc:
            log.error("Failed to record FALLBACK history for %s: %s", tool_name, exc, exc_info=True)
        return ToolResult(raw=raw, text=text)


# ═══════════════════════════════════════════════════════════════
#  Base dataclass — subclass in each agent's compactor_hooks/
# ═══════════════════════════════════════════════════════════════

@dataclass
class ToolResultCompactor:
    """Unified tool-result compaction: hardcoded dict→markdown + agentic
    KEEP/DISCARD via ReAct subagent.

    Subclass in ``<agent>_context_hooks/compactor_hooks/`` and set
    *client_factory*, *cfg*, *pipeline_label*, and *compactor_registry*.

    Two-layer pipeline
    ------------------
    1. ``compact_tool_result(tool_name, data)`` — applies the hardcoded
       dict→markdown compactor registered in *compactor_registry*.
    2. ``call(tool_name, purpose, tasks, compact_md, raw)`` — sends the
       markdown to the LLM subagent for KEEP/DISCARD triage.
    3. ``compact_and_call(tool_name, purpose, tasks, raw)`` — convenience
       method that chains both steps.
    """

    client_factory: Callable | None = None
    cfg: Any = None
    pipeline_label: str = "query"
    compactor_registry: Dict[str, Any] = field(default_factory=dict)
    reasoning_hook: Callable[[str, str], None] | None = None

    # ── Layer 1: hardcoded dict→markdown ────────────────────

    def compact_tool_result(self, tool_name: str, data: dict) -> str:
        """Look up the compactor for *tool_name* and return markdown.

        Falls back to a truncated JSON dump when no compactor is
        registered or the compactor raises.
        """
        fn = self.compactor_registry.get(tool_name)
        if fn is not None:
            try:
                return fn(data)
            except Exception as e:
                log.warning("Compactor for %s failed: %s", tool_name, e, exc_info=True)
        # Fallback — raw JSON dump (no truncation; full strings policy)
        raw_json = json.dumps(data, indent=2, default=str)
        return f"**{tool_name}** (raw):\n```json\n{raw_json}\n```\n"

    # ── Layer 2: agentic KEEP/DISCARD ───────────────────────

    def call(
        self,
        tool_name: str,
        purpose: str,
        tasks: str,
        compact_md: str,
        raw: dict,
    ) -> ToolResult:
        if self.client_factory is None:
            raise RuntimeError("ToolResultCompactor.client_factory not set")
        return call_tool_subagent(
            tool_name, purpose, tasks, compact_md, raw,
            client_factory=self.client_factory,
            cfg=self.cfg,
            pipeline_label=self.pipeline_label,
            reasoning_hook=self.reasoning_hook,
        )

    # ── Convenience: both layers in one call ────────────────

    def compact_and_call(
        self,
        tool_name: str,
        purpose: str,
        tasks: str,
        raw: dict,
    ) -> ToolResult:
        """Hardcoded compaction → agentic subagent in a single step."""
        compact_md = self.compact_tool_result(tool_name, raw)
        return self.call(tool_name, purpose, tasks, compact_md, raw)
