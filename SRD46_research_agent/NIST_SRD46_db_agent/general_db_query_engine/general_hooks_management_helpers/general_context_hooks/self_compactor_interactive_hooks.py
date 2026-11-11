"""
Self-compactor interactive hooks — shared LLM-driven memory compaction.
======================================================================
Canonical 3-step compaction cycle shared by both the **query** and
**analysis** ThermoML agents:

  1. **SELECTION**   — LLM picks WHICH results to compress (or SKIP all).
  2. **COMPRESSION** — sub-agent summarises (guided by ``<compress>`` tag).
  3. **VALIDATION**  — LLM replies ACCEPT / RETRY / SKIP.
     - ACCEPT → replace memory slot with the summary.
     - RETRY  → immediately re-compress (up to ``MAX_IMMEDIATE_RETRY``).
     - SKIP   → tag ``[RETRY:N+1]`` and try again next cycle.

Also contains the **compaction guidance hook** — the reminder template
and response parser used by ``react_loop.py`` to ask the main agent
for compaction purpose/tasks before invoking the compactor.

Each agent passes its own ``cfg`` module so all numeric limits
(``COMPRESS_MAX_WORDS``, ``KEEP_RECENT_RESULTS``, etc.) are
per-agent tunable.

Usage (compaction)::

    from ...general_context_hooks.self_compactor_interactive_hooks import compact_memory

    receipt = compact_memory(memory, argo_fn, cfg,
                             purpose="…", tasks="…")

Usage (guidance hook)::

    from ...general_context_hooks.self_compactor_interactive_hooks import (
        build_compaction_reminder, parse_compaction_guidance,
    )
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from types import ModuleType
from typing import Callable, Dict, List, Set

from ...general_text_context_marker_catalog import MARKERS

TAG_TOOL_CALL_OPEN = MARKERS.tool_call.open
TAG_TOOL_CALL_CLOSE = MARKERS.tool_call.close
TAG_TOOL_RESULT_OPEN = MARKERS.tool_result.open
TAG_TOOL_RESULT_CLOSE = MARKERS.tool_result.close
TAG_COMPRESS_OPEN = MARKERS.compress.open
TAG_COMPRESS_CLOSE = MARKERS.compress.close
TAG_COMPACTION_REMINDER_OPEN = MARKERS.compaction_reminder.open
TAG_COMPACTION_REMINDER_CLOSE = MARKERS.compaction_reminder.close
TAG_COMPACTION_GUIDANCE_OPEN = MARKERS.compaction_guidance.open
TAG_COMPACTION_GUIDANCE_CLOSE = MARKERS.compaction_guidance.close
TOOL_RESULT_TAG_RE = MARKERS.tool_result_re
COMPRESS_TAG_RE = MARKERS.compress_re
_TOOL_NAME_RE = MARKERS.tool_call_name_re
_COMPACTION_GUIDANCE_RE = MARKERS.compaction_guidance_re
_RETRY_RE = MARKERS.retry_re

log = logging.getLogger("compactor-hook")

_COMPACTION_REMINDER_TMPL = (
    f"{TAG_COMPACTION_REMINDER_OPEN}\n"
    "Context is {total_chars} chars at turn {iteration}. "
    "You may compact old tool results to free space, or SKIP if "
    "the context is still manageable or you are about to give a final answer.\n\n"
    f"Reply inside {TAG_COMPACTION_GUIDANCE_OPEN}…{TAG_COMPACTION_GUIDANCE_CLOSE} tags with exactly two lines:\n"
    "  PURPOSE: one sentence — your current goal (or why you want to skip)\n"
    "  TASKS: what to preserve — or SKIP to defer compaction\n\n"
    "Examples:\n"
    f"  {TAG_COMPACTION_GUIDANCE_OPEN}\n"
    "  PURPOSE: context is only {total_chars} chars, still well within budget\n"
    "  TASKS: SKIP\n"
    f"  {TAG_COMPACTION_GUIDANCE_CLOSE}\n\n"
    f"  {TAG_COMPACTION_GUIDANCE_OPEN}\n"
    "  PURPOSE: gathering binary-pair viscosity data, need space for better reasoning\n"
    "  TASKS: preserve block IDs, DOIs, and data-point counts; drop raw tables\n"
    f"  {TAG_COMPACTION_GUIDANCE_CLOSE}\n"
    f"{TAG_COMPACTION_REMINDER_CLOSE}"
)


def build_compaction_reminder(total_chars: int, iteration: int) -> str:
    """Return the reminder message to inject into the conversation."""
    return _COMPACTION_REMINDER_TMPL.format(
        total_chars=total_chars, iteration=iteration,
    )


def parse_compaction_guidance(response: str) -> tuple[str, str]:
    """Extract ``(purpose, tasks)`` from an LLM response.

    Returns ``("", "")`` if no ``<compaction_guidance>`` block is found.
    A tasks value of ``"SKIP"`` means the agent wants to defer.
    """
    m = _COMPACTION_GUIDANCE_RE.search(response)
    if not m:
        return ("", "")
    text = m.group(1).strip()
    # Check for bare SKIP at the start
    if text.upper().startswith("SKIP"):
        return (text, "SKIP")
    purpose = ""
    tasks = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("PURPOSE:"):
            purpose = stripped.split(":", 1)[1].strip()
        elif stripped.upper().startswith("TASKS:"):
            tasks = stripped.split(":", 1)[1].strip()
    if not purpose and text:
        purpose = text[:200]
    return (purpose, tasks)


# ═══════════════════════════════════════════════════════════════
#  Sub-agent prompts  (parametrised via cfg at call time)
# ═══════════════════════════════════════════════════════════════

def _summary_system(cfg: ModuleType | None, domain_hint: str = "") -> str:
    """Build the SUMMARY_SYSTEM prompt, respecting the caller's cfg."""
    max_words = getattr(cfg, "COMPRESS_MAX_WORDS", 500) if cfg else 500
    base = (
        "You are a data-compression assistant for a ThermoML database agent"
    )
    if domain_hint:
        base += f" {domain_hint}"
    base += ".\n"
    return (
        f"{base}"
        "The RESULT contains output from a tool call.  "
        "Follow the INSTRUCTION to compress it.\n"
        f"Output ≤ {max_words} words.  ALWAYS preserve:\n"
        "  - Identifiers (comp_ids, prop_ids, DOIs, block IDs)\n"
        "  - Numeric values (data points, block counts, temperatures)\n"
        "  - Status indicators (errors, warnings, empty results)\n"
        "  - Structural relationships (which compounds in which blocks)\n"
        "  - Any fitting coefficients, R², RMSE values\n"
        "Use compact prose or tables.  Drop formatting noise, "
        "repeated boilerplate, and raw JSON arrays."
    )


_VALIDATE_SYSTEM = (
    "You are reviewing a compressed version of a tool result. "
    "The TOOL CALL and its ORIGINAL RESULT will be replaced in the "
    "conversation memory by the PROPOSED SUMMARY. "
    "Decide whether the summary preserves enough information "
    "for the USER OBJECTIVE.\n"
    "Reply with EXACTLY one word:\n"
    "  ACCEPT — summary is good, use it\n"
    "  RETRY  — try compressing again (e.g., summary missed something)\n"
    "  SKIP   — keep the original as-is (e.g., compressing isn't worth it)"
)

_VALIDATE_PROMPT_TMPL = (
    "USER OBJECTIVE: {objective}\n"
    "COMPACTION PURPOSE: {purpose}\n"
    "COMPACTION TASKS: {tasks}\n\n"
    "TOOL CALL BEING REPLACED:\n{tool_context}\n\n"
    "ORIGINAL RESULT (first {preview_chars} chars):\n{original}\n\n"
    "PROPOSED SUMMARY (will replace the above in memory):\n{summary}\n\n"
    "Compression attempt {attempt} of {max_attempts} for this result.\n"
    "Does the summary preserve enough detail for the stated purpose/tasks?\n"
    "Reply ACCEPT, RETRY, or SKIP."
)

_SELECT_SYSTEM = (
    "You are managing conversation memory for a ThermoML database agent. "
    "You will see a list of tool results that could be compressed "
    "to free up context space.  Choose which ones to compress. "
    "IMPORTANT: Compaction is OPTIONAL.  Replying 'SKIP' is perfectly "
    "fine — especially when candidates are small, have high retry counts, "
    "or the agent still needs them. "
    "Items marked *★RECENT* are the most recent outputs — keeping them "
    "is usually a good idea since the agent may still reference them, "
    "but you MAY compress them too if the context is very large. "
    "Items marked *↻RETRY×N* had N previous compression attempts that "
    "were all rejected — you should SKIP these (higher N means the "
    "result is very hard to compress). "
    "Items marked *🔒PROTECTED* are critical results and MUST NOT be "
    "compressed — skip them. "
    "Reply with ONLY a comma-separated list of the numbers you want to "
    "compress (e.g. '1,3').  Reply 'SKIP' to skip compression entirely. "
    "When in doubt, prefer 'SKIP'."
)

_SELECT_PROMPT_TMPL = (
    "USER OBJECTIVE: {objective}\n"
    "COMPACTION PURPOSE: {purpose}\n"
    "COMPACTION TASKS: {tasks}\n\n"
    "The following tool results are candidates for compression.\n"
    "Items marked *★RECENT* are the {keep_n} most recent — keeping "
    "them is recommended but not mandatory.  Items marked *🔒PROTECTED* "
    "MUST NOT be compressed.  Items marked *↻RETRY* have already "
    "failed compression and should generally be skipped.\n\n"
    "{candidate_list}\n\n"
    "Which of these should be compressed?  Reply with a comma-separated "
    "list of numbers (e.g. '1,3') or 'SKIP' to skip compression.\n"
    "Compaction is optional — 'SKIP' is a perfectly valid answer.\n"
    "Use the COMPACTION PURPOSE and TASKS to decide which results "
    "can safely be compressed vs. which are still needed."
)

_SELECT_RE = re.compile(r"\d+")


# ═══════════════════════════════════════════════════════════════
#  Public functions
# ═══════════════════════════════════════════════════════════════

def summarise_tool_result(
    body: str,
    instruction: str,
    user_objective: str,
    argo_fn: Callable[..., str],
    cfg: ModuleType | None = None,
    purpose: str = "",
    tasks: str = "",
    domain_hint: str = "",
    reasoning_hook: Callable[[str, str], None] | None = None,
) -> str:
    """Call the LLM as a summary sub-agent using the given instruction."""
    short_thresh = getattr(cfg, "COMPRESS_SHORT_THRESHOLD", 1_500) if cfg else 1_500
    preview_chars = getattr(cfg, "COMPRESS_PREVIEW_CHARS", 4_000) if cfg else 4_000
    max_chars = getattr(cfg, "COMPRESS_SUMMARY_CHARS", 800) if cfg else 800
    fallback_chars = getattr(cfg, "COMPACTED_MAX_CHARS", 500) if cfg else 500

    if len(body) < short_thresh:
        instruction = (
            f"{instruction}\n"
            f"IMPORTANT: The original is only {len(body)} chars. "
            f"Your summary MUST be shorter than {len(body)} chars. "
            "Be extremely concise — a 1-3 sentence summary is fine."
        )
    prompt = f"INSTRUCTION: {instruction}\n"
    if user_objective:
        prompt += f"USER OBJECTIVE: {user_objective}\n"
    if purpose:
        prompt += f"COMPACTION PURPOSE: {purpose}\n"
    if tasks:
        prompt += f"COMPACTION TASKS: {tasks}\n"
    prompt += (
        f"\nRESULT ({len(body)} chars, first {preview_chars} shown):\n"
        f"{body[:preview_chars]}"
    )
    try:
        summary = argo_fn(prompt, _summary_system(cfg, domain_hint), stop=[])
        if reasoning_hook is not None:
            try:
                reasoning_hook("interactive-compact/summarise", summary)
            except Exception as exc:
                log.error("Reasoning hook failed during summary compaction: %s", exc, exc_info=True)
        if len(summary) > max_chars:
            summary = summary[:max_chars] + "…"
        log.info("[C] Summary sub-agent produced %d-char summary", len(summary))
        return summary
    except Exception as e:
        log.warning("[C] Summary sub-agent failed: %s — falling back to preview", e, exc_info=True)
        preview = body[:fallback_chars].replace("\n", " ")
        return f"Returned {len(body)} chars. Preview: {preview}..."


def validate_compression(
    original: str,
    summary: str,
    user_objective: str,
    tool_context: str,
    argo_fn: Callable[..., str],
    cfg: ModuleType | None = None,
    attempt: int = 1,
    max_attempts: int = 2,
    purpose: str = "",
    tasks: str = "",
    reasoning_hook: Callable[[str, str], None] | None = None,
) -> str:
    """Ask the main Argo whether the compression is acceptable.

    Returns one of: ``'ACCEPT'``, ``'RETRY'``, ``'SKIP'``.
    """
    preview_chars = getattr(cfg, "COMPRESS_ORIGINAL_PREVIEW", 1_000) if cfg else 1_000
    prompt = _VALIDATE_PROMPT_TMPL.format(
        objective=user_objective or "(general query)",
        purpose=purpose or "(auto-triggered)",
        tasks=tasks or "(not specified)",
        tool_context=tool_context or "(unknown tool call)",
        original=original[:preview_chars],
        summary=summary,
        preview_chars=preview_chars,
        attempt=attempt,
        max_attempts=max_attempts,
    )
    try:
        raw_resp = argo_fn(prompt, _VALIDATE_SYSTEM, stop=[])
        if reasoning_hook is not None:
            try:
                reasoning_hook("interactive-compact/validate", raw_resp)
            except Exception as exc:
                log.error("Reasoning hook failed during compaction validation: %s", exc, exc_info=True)
        raw = raw_resp.strip().upper()
        if raw.startswith("ACCEPT"):
            verdict = "ACCEPT"
        elif raw.startswith("RETRY"):
            verdict = "RETRY"
        else:
            verdict = "SKIP"
        log.info("[C] Validation: %s (raw=%r, attempt %d/%d)",
                 verdict, raw[:30], attempt, max_attempts)
        return verdict
    except Exception as e:
        log.warning("[C] Validation call failed: %s — skipping by default", e, exc_info=True)
        return "SKIP"


def _select_targets(
    candidates: List[dict],
    user_objective: str,
    argo_fn: Callable[..., str],
    cfg: ModuleType | None = None,
    purpose: str = "",
    tasks: str = "",
    reasoning_hook: Callable[[str, str], None] | None = None,
) -> List[int]:
    """Ask the main Argo which candidates to compress."""
    keep_n = getattr(cfg, "KEEP_RECENT_RESULTS", 2) if cfg else 2
    listing = []
    for c in candidates:
        flags = ""
        if c.get("protected"):
            flags += " *🔒PROTECTED*"
        if c.get("is_recent"):
            flags += " *★RECENT*"
        retry_n = c.get("retry_count", 0)
        if retry_n:
            flags += f" *↻RETRY×{retry_n}*"
        listing.append(
            f"  [{c['num']}] {c['tool_name']}  ({c['chars']} chars){flags}\n"
            f"       Preview: {c['preview'][:150]}..."
        )
    prompt = _SELECT_PROMPT_TMPL.format(
        objective=user_objective or "(general query)",
        purpose=purpose or "(auto-triggered)",
        tasks=tasks or "(not specified)",
        keep_n=keep_n,
        candidate_list="\n".join(listing),
    )
    try:
        raw_resp = argo_fn(prompt, _SELECT_SYSTEM, stop=[])
        if reasoning_hook is not None:
            try:
                reasoning_hook("interactive-compact/select", raw_resp)
            except Exception as exc:
                log.error("Reasoning hook failed during compaction target selection: %s", exc, exc_info=True)
        reply = raw_resp.strip().upper()
        log.info("[C] Selection reply: %r", reply[:60])
        if "SKIP" in reply or "NONE" in reply:
            return []
        nums = [int(x) for x in _SELECT_RE.findall(reply)]
        valid = {c["num"] for c in candidates if not c.get("protected")}
        return [n for n in nums if n in valid]
    except Exception as e:
        log.warning("[C] Selection call failed (%s) — skipping compaction", e, exc_info=True)
        return []


# ═══════════════════════════════════════════════════════════════
#  Main compaction entry point
# ═══════════════════════════════════════════════════════════════

def compact_memory(
    memory: List[Dict[str, str]],
    argo_fn: Callable[..., str],
    cfg: ModuleType | None = None,
    *,
    purpose: str = "",
    tasks: str = "",
    protect_tools: Set[str] | None = None,
    domain_hint: str = "",
    reasoning_hook: Callable[[str, str], None] | None = None,
) -> str:
    """Compress old tool-result blocks with LLM-driven selection + validation.

    Parameters
    ----------
    memory : list[dict]
        Mutable conversation history (role/content dicts).
    argo_fn : callable
        ``fn(prompt, system, stop=…) -> str`` — LLM caller.
    cfg : module, optional
        Agent config module supplying numeric limits.  Falls back to
        sensible defaults when ``None``.
    purpose : str
        One-sentence compaction goal from the guidance hook.
    tasks : str
        What data/results the agent says must be preserved.
    protect_tools : set[str], optional
        Tool names whose results must NEVER be compressed (e.g. fitting
        tools in the analysis agent).
    domain_hint : str
        Extra context appended to the summary system prompt
        (e.g. ``"that fits Redlich-Kister models"``).

    Returns
    -------
    str
        Short compaction receipt (empty if nothing compacted).
    """
    _protect = protect_tools or set()
    _keep_recent = getattr(cfg, "KEEP_RECENT_RESULTS", 2) if cfg else 2
    _min_chars = getattr(cfg, "MIN_COMPRESS_CHARS", 500) if cfg else 500
    _max_retry = getattr(cfg, "MAX_RETRY", 5) if cfg else 5
    _max_imm = getattr(cfg, "MAX_IMMEDIATE_RETRY", 2) if cfg else 2
    _user_ctx = getattr(cfg, "COMPRESS_USER_CONTEXT", 500) if cfg else 500

    # Extract user objective for context
    user_objective = ""
    for turn in memory:
        if turn["role"] == "user" and TAG_TOOL_RESULT_OPEN not in turn["content"]:
            user_objective = turn["content"][:_user_ctx]
            break

    if purpose:
        log.info("[C] Compaction guidance — PURPOSE: %s", purpose[:120])
    if tasks:
        log.info("[C] Compaction guidance — TASKS: %s", tasks[:120])

    # Find all tool-result turns
    tr_indices = [
        i for i, turn in enumerate(memory)
        if turn["role"] == "user" and TAG_TOOL_RESULT_OPEN in turn["content"]
    ]

    recent_cutoff = max(0, len(tr_indices) - _keep_recent)

    # Build candidate list
    candidates: List[dict] = []
    for pos, idx in enumerate(tr_indices):
        content = memory[idx]["content"]
        m = TOOL_RESULT_TAG_RE.search(content)
        if not m:
            continue
        body = m.group(1)
        if body.startswith("[summary]"):
            continue
        if body.startswith("[CATALOG]"):
            continue

        retry_match = _RETRY_RE.match(body)
        retry_count = int(retry_match.group(1)) if retry_match else 0
        display_body = body[retry_match.end():] if retry_match else body

        if len(display_body) < _min_chars:
            continue

        if retry_count >= _max_retry:
            memory[idx]["content"] = (
                f"{TAG_TOOL_RESULT_OPEN}\n{display_body}\n{TAG_TOOL_RESULT_CLOSE}"
            )
            log.info("[C] memory[%d] hit MAX_RETRY=%d — permanently keeping",
                     idx, _max_retry)
            continue

        # Extract tool name from preceding assistant turn
        tool_name = "(unknown)"
        if idx > 0 and memory[idx - 1]["role"] == "assistant":
            tn = _TOOL_NAME_RE.search(memory[idx - 1]["content"])
            if tn:
                tool_name = tn.group(1)

        is_protected = tool_name in _protect

        candidates.append({
            "num":         len(candidates) + 1,
            "idx":         idx,
            "tool_name":   tool_name,
            "preview":     display_body[:200].replace("\n", " "),
            "chars":       len(display_body),
            "is_recent":   pos >= recent_cutoff,
            "retry_count": retry_count,
            "protected":   is_protected,
        })

    if not candidates:
        return ""

    # Step 0: Ask Argo which ones to compress
    chosen_nums = _select_targets(
        candidates, user_objective, argo_fn, cfg,
        purpose=purpose, tasks=tasks,
        reasoning_hook=reasoning_hook,
    )
    if not chosen_nums:
        log.info("[C] Argo chose SKIP — skipping compression this round.")
        return ""
    chosen_set = set(chosen_nums)
    log.info("[C] Selected candidates %s for compression", chosen_nums)

    _compacted_items: List[str] = []

    # Steps 1-3: Compress + Validate each chosen candidate
    total_attempts = _max_imm + 1
    for cand in candidates:
        if cand["num"] not in chosen_set:
            continue
        if cand.get("protected"):
            continue
        idx = cand["idx"]
        content = memory[idx]["content"]
        m = TOOL_RESULT_TAG_RE.search(content)
        if not m:
            continue
        raw_body = m.group(1)
        retry_match = _RETRY_RE.match(raw_body)
        prev_count = int(retry_match.group(1)) if retry_match else 0
        body = raw_body[retry_match.end():] if retry_match else raw_body

        # Get compression instruction from <compress> tags
        instruction = None
        next_idx = idx + 1
        if next_idx < len(memory) and memory[next_idx]["role"] == "assistant":
            cm = COMPRESS_TAG_RE.search(memory[next_idx]["content"])
            if cm:
                instruction = cm.group(1).strip()
        if not instruction and idx > 0 and memory[idx - 1]["role"] == "assistant":
            cm = COMPRESS_TAG_RE.search(memory[idx - 1]["content"])
            if cm:
                instruction = cm.group(1).strip()
        if not instruction:
            instruction = (
                f"Compress this {cand['tool_name']} result. "
                "Keep all DOIs, block numbers, compound IDs, data counts, "
                "and temperature/pressure ranges. "
                "Drop raw data rows and JSON formatting noise."
            )

        # Extract tool context
        tool_context = cand["tool_name"]
        if idx > 0 and memory[idx - 1]["role"] == "assistant":
            tc_text = memory[idx - 1]["content"]
            tc_start = tc_text.find(TAG_TOOL_CALL_OPEN)
            tc_end = tc_text.find(TAG_TOOL_CALL_CLOSE)
            if tc_start >= 0 and tc_end >= 0:
                tool_context = tc_text[tc_start:tc_end + len(TAG_TOOL_CALL_CLOSE)]
                if len(tool_context) > 300:
                    tool_context = tool_context[:300] + "..."

        # Inner retry loop: compress → validate → ACCEPT/RETRY/SKIP
        for attempt in range(1, total_attempts + 1):
            summary_text = summarise_tool_result(
                body, instruction, user_objective, argo_fn,
                cfg=cfg, purpose=purpose, tasks=tasks,
                domain_hint=domain_hint,
                reasoning_hook=reasoning_hook,
            )
            verdict = validate_compression(
                body, summary_text, user_objective, tool_context, argo_fn,
                cfg=cfg, attempt=attempt, max_attempts=total_attempts,
                purpose=purpose, tasks=tasks,
                reasoning_hook=reasoning_hook,
            )

            if verdict == "ACCEPT":
                compact = f"[summary] {summary_text}"
                memory[idx]["content"] = (
                    f"{TAG_TOOL_RESULT_OPEN}\n{compact}\n{TAG_TOOL_RESULT_CLOSE}"
                )
                _compacted_items.append(
                    f"{cand['tool_name']} ({len(body)}→{len(compact)} chars)"
                )
                log.info("[C] Compacted memory[%d]: %d→%d chars "
                         "(ACCEPTED on attempt %d)",
                         idx, len(body), len(compact), attempt)
                break

            if verdict == "RETRY" and attempt < total_attempts:
                log.info("[C] memory[%d]: RETRY requested (attempt %d/%d)",
                         idx, attempt, total_attempts)
                continue

            # SKIP or last-attempt RETRY
            new_count = prev_count + 1
            memory[idx]["content"] = (
                f"{TAG_TOOL_RESULT_OPEN}\n[RETRY:{new_count}] {body}\n{TAG_TOOL_RESULT_CLOSE}"
            )
            log.info("[C] memory[%d]: %s on attempt %d — "
                     "tagged [RETRY:%d] (%d chars)",
                     idx, verdict, attempt, new_count, len(body))
            break

    if not _compacted_items:
        return ""
    receipt = f"Compacted {len(_compacted_items)} result(s): "
    receipt += "; ".join(_compacted_items)
    if purpose:
        receipt += f" | Purpose: {purpose[:100]}"
    return receipt


# ═══════════════════════════════════════════════════════════════
#  Base dataclass — subclass in each agent's interactive_hooks/
# ═══════════════════════════════════════════════════════════════

@dataclass
class InteractiveCompactor:
    """LLM-driven compaction engine — one instance per agent.

    Subclass in ``<agent>_context_hooks/interactive_hooks/`` and
    override *cfg*, *protect_tools*, and *domain_hint* to customise
    compaction behaviour per agent.
    """

    cfg: ModuleType | None = None
    protect_tools: Set[str] = field(default_factory=set)
    domain_hint: str = ""
    reasoning_hook: Callable[[str, str], None] | None = None

    # ── Delegate methods (use stored config) ─────────────────

    def summarise(
        self,
        body: str,
        instruction: str,
        user_objective: str,
        argo_fn: Callable[..., str],
        *,
        purpose: str = "",
        tasks: str = "",
    ) -> str:
        return summarise_tool_result(
            body, instruction, user_objective, argo_fn,
            cfg=self.cfg, purpose=purpose, tasks=tasks,
            domain_hint=self.domain_hint,
            reasoning_hook=self.reasoning_hook,
        )

    def validate(
        self,
        original: str,
        summary: str,
        user_objective: str,
        tool_context: str,
        argo_fn: Callable[..., str],
        **kwargs,
    ) -> str:
        return validate_compression(
            original, summary, user_objective, tool_context, argo_fn,
            cfg=self.cfg, **kwargs,
        )

    def compact(
        self,
        memory: List[Dict[str, str]],
        argo_fn: Callable[..., str],
        *,
        purpose: str = "",
        tasks: str = "",
    ) -> str:
        return compact_memory(
            memory, argo_fn, cfg=self.cfg,
            purpose=purpose, tasks=tasks,
            protect_tools=self.protect_tools,
            domain_hint=self.domain_hint,
            reasoning_hook=self.reasoning_hook,
        )
