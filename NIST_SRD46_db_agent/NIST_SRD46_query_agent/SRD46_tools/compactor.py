"""
Memory compaction module  (compactor.py)
========================================
Summarises old tool-result turns via an LLM sub-agent so the
conversation prompt stays bounded across many tool iterations.

After compression, the **main Argo agent** is shown the proposed
summary and decides whether to ACCEPT or REJECT it.  If rejected,
the original result is tagged ``[RETRY]`` and can be offered again
in any future compression round — Argo decides when to stop retrying.

Separated from the terminal runtime so it can be tested, reused, or swapped
independently.  The actual LLM call is injected as *argo_fn* to
avoid circular imports with the terminal runtime.
"""

import logging
import json
import re
from typing import Callable, Dict, List

log = logging.getLogger("SRD46-compactor")

# ------------------------------------------------------------------
#  Constants & regex
# ------------------------------------------------------------------

TOOL_RESULT_TAG_RE = re.compile(
    r"<tool_result>\n(.*?)\n</tool_result>", re.DOTALL
)

# How many of the *most-recent* tool-result turns to **recommend**
# keeping in full.  This is a SOFT bound — Argo can override it and
# compress recent results too if context is overwhelmed.
import sys as _sys
from pathlib import Path as _Path
_REPO_ROOT = _Path(__file__).absolute().parents[3]
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))
from NIST_SRD46_db_agent.NIST_SRD46_query_agent.argo_config import (
    KEEP_RECENT_RESULTS,
    REASONING_CAP,
    MIN_COMPRESS_CHARS,
    MAX_RETRY,
)

# Regex to parse [RETRY:N] prefix and extract the attempt count
_RETRY_RE = re.compile(r"^\[RETRY:(\d+)\]\s*")


from NIST_SRD46_core_db_search_tools._tools_results_compactors import (
    COMPACTOR_FUNCTIONS as _COMPACTOR_FUNCTIONS,
)

_HARDCODED_COMPACTORS: Dict[str, Callable[[object], str]] = {}
for _fn in _COMPACTOR_FUNCTIONS:
    for _tool_name in getattr(_fn, "_compacts_tools", ()):
        _HARDCODED_COMPACTORS[_tool_name] = _fn

_SPECIAL_RESULT_PREFIXES = ("[CATALOG]", "[PREPLAN]", "[PLAN]", "[PLAN:DONE]")

# ── Sub-agent prompts ────────────────────────────────────────────

SUMMARY_SYSTEM = (
    "You are a data-compression assistant. "
    "Follow the INSTRUCTION to compress the RESULT. "
    "Stay within the CHARACTER BUDGET given in the instruction. "
    "No raw JSON. Use compact prose or a small table."
)

# ── Validation prompt (sent to the *main* Argo) ─────────────────

_VALIDATE_SYSTEM = (
    "You are reviewing a compressed tool result.\n"
    "Reply with EXACTLY one of:\n"
    "  ACCEPT\n"
    "  SKIP\n"
    "  RETRY: <why rejected> — <what the summary should fix>\n"
    "Example: RETRY: summary drops per-species ionic-strength ranges "
    "— preserve the ionic-strength values for each log K"
)

_VALIDATE_PROMPT_TMPL = (
    "USER OBJECTIVE: {objective}\n\n"
    "TOOL: {tool_context}\n"
    "COMPRESSION PURPOSE: {purpose}\n"
    "PRESERVATION TASK: {task}\n"
    "ORIGINAL: {original_chars} chars → SUMMARY: {summary_chars} chars "
    "({ratio:.0f}% reduction)\n\n"
    "ORIGINAL (first 800 chars):\n{original}\n\n"
    "PROPOSED SUMMARY:\n{summary}\n\n"
    "Does the summary preserve enough detail for the stated task? "
    "ACCEPT / SKIP / RETRY: <why rejected> — <what to fix>"
)

# Regex to extract tool name from <tool_call> JSON in assistant turns
_TOOL_NAME_RE = re.compile(
    r'<tool_call>\s*(?:\[\s*)?\{[^}]*"name"\s*:\s*"([^"]+)"', re.DOTALL
)

# ------------------------------------------------------------------
#  Public helpers
# ------------------------------------------------------------------

def summarise_tool_result(
    body: str,
    instruction: str,
    user_objective: str,
    argo_fn: Callable[..., str],
) -> str:
    """Call the LLM as a summary sub-agent using the given instruction.

    Parameters
    ----------
    body : str
        Raw tool-result text.
    instruction : str
        Free-text compression instruction (from ``<compress>`` tag or
        the default).
    user_objective : str
        The user's original question, for context.
    argo_fn : callable
        ``call_argo(prompt, system, *, stop)`` – injected to avoid
        circular imports.

    Returns
    -------
    str
        A concise summary within the character budget.
    """
    # 30% of original, floor 800 chars
    char_budget = max(800, int(len(body) * 0.30))
    # Token budget: dense tabular/numeric output (logK tables, equations,
    # chemical formulas) tokenises at ~2–3 chars/token, so the naive
    # `char_budget // 4` (~4 chars/token, English prose) caused mid-sentence
    # truncation that the validator then flagged as RETRY. Use ~2 chars/token
    # plus a small headroom so the model can actually emit `char_budget` chars.
    token_budget = max(400, char_budget // 2 + 64)

    budget_line = (
        f"\nCHARACTER BUDGET: ≤ {char_budget} chars. "
        f"The original is {len(body)} chars."
    )
    prompt = f"INSTRUCTION: {instruction}{budget_line}\n"
    if user_objective:
        prompt += f"USER OBJECTIVE: {user_objective}\n"
    prompt += (
        f"\nRESULT ({len(body)} chars):\n"
        f"{body}"
    )
    try:
        summary = argo_fn(prompt, SUMMARY_SYSTEM, stop=[],
                          max_tokens=token_budget)
        log.info("[M] Summary sub-agent produced %d-char summary "
                 "(budget=%d, tokens=%d)", len(summary), char_budget,
                 token_budget)
        return summary
    except Exception as e:
        # Sub-agent failed: return the ORIGINAL body unchanged rather than
        # silently truncating to a fixed-length preview. The downstream
        # validator will see summary == original (0% reduction) and SKIP,
        # which keeps the full tool result in memory for the next round.
        log.warning(
            "[M] Summary sub-agent failed: %s — keeping original %d-char body intact",
            e, len(body),
        )
        return body


def _strip_special_prefixes(body: str) -> tuple[str, list[str]]:
    stripped = body.lstrip()
    prefixes: list[str] = []
    changed = True
    while changed:
        changed = False
        for prefix in _SPECIAL_RESULT_PREFIXES:
            if stripped.startswith(prefix):
                prefixes.append(prefix)
                stripped = stripped[len(prefix):].lstrip()
                changed = True
    return stripped, prefixes


def _summarise_with_hardcoded_compactor(tool_name: str, body: str) -> str | None:
    compact_fn = _HARDCODED_COMPACTORS.get(tool_name)
    if compact_fn is None:
        return None

    stripped, prefixes = _strip_special_prefixes(body)
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        return None

    try:
        compact_md = compact_fn(data)
        compact_md = compact_md.strip()
        for prefix in reversed(prefixes):
            compact_md = f"{prefix}\n{compact_md}"
        return compact_md
    except Exception as exc:
        log.warning("[M] Hardcoded compactor failed for %s: %s", tool_name, exc)
        return None


def _cell(value, max_len: int = 80) -> str:
    if value is None:
        return "***"
    text = str(value).replace("\n", " ").strip()
    if not text:
        return "***"
    return text if len(text) <= max_len else text[: max_len - 1] + "..."


def _render_generic_json(tool_name: str, data: object) -> str:
    if isinstance(data, list):
        if not data:
            return f"## {tool_name}\n\n*(no results)*"
        if all(isinstance(item, dict) for item in data):
            keys = list(data[0].keys())[:8]
            lines = [f"## {tool_name} - {len(data)} row(s)", ""]
            lines.append("| " + " | ".join(keys) + " |")
            lines.append("|" + "|".join("-" * (len(k) + 2) for k in keys) + "|")
            for row in data[:25]:
                lines.append("| " + " | ".join(_cell(row.get(k)) for k in keys) + " |")
            if len(data) > 25:
                lines.append("")
                lines.append(f"... {len(data) - 25} more row(s) omitted")
            return "\n".join(lines)
        lines = [f"## {tool_name} - {len(data)} item(s)", ""]
        for item in data[:25]:
            lines.append(f"- {_cell(item, 120)}")
        if len(data) > 25:
            lines.append(f"- ... {len(data) - 25} more item(s)")
        return "\n".join(lines)

    if isinstance(data, dict):
        if "results" in data and isinstance(data["results"], list):
            header_bits = []
            for key in ("count", "total_rows", "total_sql_matches", "excluded_by_groups", "limit"):
                if key in data and not isinstance(data[key], (dict, list)):
                    header_bits.append(f"{key}={_cell(data[key], 30)}")
            title = f"## {tool_name}"
            if header_bits:
                title += " - " + ", ".join(header_bits)
            lines = [title, ""]
            rows = data["results"]
            if rows and all(isinstance(item, dict) for item in rows):
                keys = list(rows[0].keys())[:8]
                lines.append("| " + " | ".join(keys) + " |")
                lines.append("|" + "|".join("-" * (len(k) + 2) for k in keys) + "|")
                for row in rows[:25]:
                    lines.append("| " + " | ".join(_cell(row.get(k)) for k in keys) + " |")
                if len(rows) > 25:
                    lines.append("")
                    lines.append(f"... {len(rows) - 25} more row(s) omitted")
                return "\n".join(lines)
            lines.append(f"- results: {len(rows)} item(s)")
            return "\n".join(lines)

        lines = [f"## {tool_name}", ""]
        scalar_items = []
        nested_items = []
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                nested_items.append((key, value))
            else:
                scalar_items.append((key, value))
        for key, value in scalar_items:
            lines.append(f"- {key}: {_cell(value, 120)}")
        for key, value in nested_items:
            if isinstance(value, list):
                lines.append(f"- {key}: {len(value)} item(s)")
            elif isinstance(value, dict):
                lines.append(f"- {key}: {len(value)} field(s)")
        return "\n".join(lines)

    return f"## {tool_name}\n\n{_cell(data, 400)}"


def _summarise_with_generic_renderer(tool_name: str, body: str) -> str | None:
    stripped, prefixes = _strip_special_prefixes(body)
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        return None

    rendered = _render_generic_json(tool_name, data).strip()
    for prefix in reversed(prefixes):
        rendered = f"{prefix}\n{rendered}"
    return rendered


def compact_tool_result_immediately(
    tool_name: str,
    body: str,
) -> tuple[str, bool, str | None]:
    """Return the agent-facing tool result text.

    If a deterministic compactor exists for ``tool_name``, the agent sees
    that compacted markdown immediately. Otherwise the function tries a
    generic markdown renderer for JSON payloads before falling back to the
    raw tool output.
    """
    summary = _summarise_with_hardcoded_compactor(tool_name, body)
    used_kind = "hardcoded"
    if summary is None:
        summary = _summarise_with_generic_renderer(tool_name, body)
        used_kind = "generic"
    if summary is None:
        return body, False, None
    immediate = f"[summary]\n{summary}"
    kind = "hardcoded compactor" if used_kind == "hardcoded" else "generic markdown renderer"
    log.info("[M] %s used for %s (%d chars)",
             kind.capitalize(), tool_name, len(immediate),
             extra={"for_tool": tool_name})
    return immediate, True, used_kind


def validate_compression(
    original: str,
    summary: str,
    user_objective: str,
    tool_context: str,
    argo_fn: Callable[..., str],
    purpose: str = "",
    task: str = "",
) -> tuple[str, str | None]:
    """Ask the main Argo whether the compression is acceptable.

    Returns ``('accept', None)``, ``('retry', refinement_instruction)``,
    or ``('skip', None)``.
    """
    original_chars = len(original)
    summary_chars = len(summary)
    ratio = (1 - summary_chars / max(original_chars, 1)) * 100
    prompt = _VALIDATE_PROMPT_TMPL.format(
        objective=user_objective or "(general query)",
        tool_context=tool_context or "(unknown tool call)",
        purpose=purpose or "(not specified)",
        task=task or "(not specified)",
        original_chars=original_chars,
        summary_chars=summary_chars,
        ratio=ratio,
        original=original[:800],
        summary=summary,
    )
    try:
        raw = argo_fn(
            prompt, _VALIDATE_SYSTEM, stop=[], max_tokens=60,
        ).strip()
        upper = raw.upper()
        log.info("[M] Main-agent validation: %r", raw[:80])
        if "ACCEPT" in upper:
            return "accept", None
        if "RETRY" in upper:
            colon_idx = raw.find(":")
            refinement = raw[colon_idx + 1:].strip() if colon_idx >= 0 else ""
            return "retry", refinement or "improve the summary"
        return "skip", None
    except Exception as e:
        log.warning("[M] Validation call failed: %s — accepting by default", e)
        return "accept", None


# ── Selection prompt — Argo picks WHICH results to compress ──────

_SELECT_SYSTEM = (
    "You are managing conversation memory for an SRD-46 database agent. "
    "You will see a list of tool results that could be compressed "
    "to free up context space. For each result you choose to compress, "
    "provide a PURPOSE (why this result can be safely compressed now) "
    "and a TASK (what broader objective the compressed summary should "
    "preserve data for).\n\n"
    "Items marked *★RECENT* are the most recent outputs — keep them "
    "unless context is very large. "
    "Items marked *↻RETRY×N* had N previous compression attempts that "
    "were all rejected — higher N means compression is harder.\n\n"
    "Reply format — one line per selected candidate:\n"
    "  NUM: purpose=\"...\" task=\"...\"\n"
    "Reply 'NONE' to skip compression entirely."
)

_SELECT_PROMPT_TMPL = (
    "USER OBJECTIVE: {objective}\n\n"
    "CONTEXT WINDOW: {ctx_chars:,} chars across {ctx_turns} turns "
    "(target: ≤15,000 chars). {ctx_pressure}\n\n"
    "The following tool results are candidates for compression.\n"
    "Items marked *★RECENT* are the {keep_n} most recent. "
    "Items marked *↻RETRY×N* had N failed compression attempts.\n\n"
    "{candidate_list}\n\n"
    "Which of these should be compressed? For each, provide purpose "
    "and task on one line:\n"
    "  NUM: purpose=\"why it can be compressed\" task=\"what to preserve\"\n"
    "Or reply 'NONE' to keep them all."
)

_SELECT_LINE_RE = re.compile(
    r'(\d+)\s*:\s*purpose\s*=\s*"([^"]*)"\s*task\s*=\s*"([^"]*)"',
    re.IGNORECASE,
)


def _select_targets(
    candidates: List[dict],
    user_objective: str,
    argo_fn: Callable[..., str],
    ctx_chars: int = 0,
    ctx_turns: int = 0,
) -> List[dict]:
    """Ask the main Argo which candidates to compress.

    The agent provides a PURPOSE and TASK for each selected candidate
    so the compression sub-agent knows what data to preserve.

    Returns list of ``{'num': int, 'purpose': str, 'task': str}``
    dicts.  Empty list means "compress nothing this round."
    """
    listing = []
    for c in candidates:
        flags = ""
        if c.get("is_recent"):
            flags += " *★RECENT*"
        retry_n = c.get("retry_count", 0)
        if retry_n:
            flags += f" *↻RETRY×{retry_n}*"
        listing.append(
            f"  [{c['num']}] {c['tool_name']}  ({c['chars']} chars){flags}\n"
            f"       Preview: {c['preview'][:150]}..."
        )
    if ctx_chars > 20000:
        ctx_pressure = "⚠ CRITICAL — aggressively compress to reduce context."
    elif ctx_chars > 15000:
        ctx_pressure = "⚠ Over target — compress more candidates."
    elif ctx_chars > 10000:
        ctx_pressure = "Approaching target — consider compressing older results."
    else:
        ctx_pressure = "Within target — compress only if clearly beneficial."
    prompt = _SELECT_PROMPT_TMPL.format(
        objective=user_objective or "(general query)",
        keep_n=KEEP_RECENT_RESULTS,
        candidate_list="\n".join(listing),
        ctx_chars=ctx_chars,
        ctx_turns=ctx_turns,
        ctx_pressure=ctx_pressure,
    )
    try:
        reply = argo_fn(prompt, _SELECT_SYSTEM, stop=[])
        log.info("[M] Compress-selection reply: %r", reply.strip()[:120])
        if "NONE" in reply.upper():
            return []
        valid = {c["num"] for c in candidates}
        chosen = []
        for m in _SELECT_LINE_RE.finditer(reply):
            num = int(m.group(1))
            if num in valid:
                chosen.append({
                    "num": num,
                    "purpose": m.group(2).strip(),
                    "task": m.group(3).strip(),
                })
        if not chosen:
            log.warning("[M] Could not parse selection response — skipping")
        return chosen
    except Exception as e:
        log.warning("[M] Selection call failed (%s) — skipping compression", e)
        return []


_INNER_MAX_RETRY = 3


def _memory_context_stats(memory: List[Dict[str, str]]) -> tuple[int, int]:
    return sum(len(turn.get("content", "")) for turn in memory), len(memory)


def _compress_one_candidate(
    cand: dict,
    sel: dict,
    memory: List[Dict[str, str]],
    user_objective: str,
    argo_fn: Callable[..., str],
    round_kind: str = "session",
) -> None:
    """Compress + validate one candidate with up to _INNER_MAX_RETRY attempts.

    Each candidate modifies only ``memory[cand['idx']]``, so multiple
    instances can run in parallel on different candidates without locking.
    """
    idx = cand["idx"]
    content = memory[idx]["content"]
    m = TOOL_RESULT_TAG_RE.search(content)
    if not m:
        return
    raw_body = m.group(1)
    retry_match = _RETRY_RE.match(raw_body)
    prev_count = int(retry_match.group(1)) if retry_match else 0
    body = raw_body[retry_match.end():] if retry_match else raw_body

    tool_context = cand["tool_name"]
    if idx > 0 and memory[idx - 1]["role"] == "assistant":
        tc_text = memory[idx - 1]["content"]
        tc_start = tc_text.find("<tool_call>")
        tc_end = tc_text.find("</tool_call>")
        if tc_start >= 0 and tc_end >= 0:
            tool_context = tc_text[tc_start:tc_end + len("</tool_call>")]
            if len(tool_context) > 300:
                tool_context = tool_context[:300] + "..."

    purpose = sel["purpose"]
    task = sel["task"]
    refinement = None
    candidate_t0 = __import__("time").perf_counter()
    log.info("[M/%s] START candidate memory[%d] %s (%d chars)",
             round_kind, idx, cand["tool_name"], len(body),
             extra={
                 "event_kind": "candidate_start",
                 "round_kind": round_kind,
                 "for_tool": cand["tool_name"],
                 "candidate_idx": idx,
                 "candidate_tool": cand["tool_name"],
                 "original_chars": len(body),
             })

    for attempt in range(1, _INNER_MAX_RETRY + 1):
        instruction = (
            f"Compress this {cand['tool_name']} result. "
            f"Purpose: {purpose}. Task: {task}. "
            f"Preserve data relevant to the task."
        )
        if refinement:
            instruction += f" IMPORTANT: {refinement}"

        summary_text = None
        if attempt == 1:
            summary_text = _summarise_with_hardcoded_compactor(cand["tool_name"], body)
        if summary_text is None:
            summary_text = summarise_tool_result(
                body, instruction, user_objective, argo_fn
            )

        verdict, new_refinement = validate_compression(
            body, summary_text, user_objective, tool_context, argo_fn,
            purpose=purpose, task=task,
        )

        if verdict == "accept":
            compact = f"[summary] {summary_text}"
            memory[idx]["content"] = f"<tool_result>\n{compact}\n</tool_result>"
            candidate_duration = __import__("time").perf_counter() - candidate_t0
            log.info("[M] Compacted memory[%d]: %d→%d chars "
                     "(ACCEPTED, attempt %d/%d)",
                     idx, len(body), len(compact), attempt, _INNER_MAX_RETRY,
                     extra={
                         "event_kind": "candidate_complete",
                         "round_kind": round_kind,
                         "for_tool": cand["tool_name"],
                         "candidate_idx": idx,
                         "candidate_tool": cand["tool_name"],
                         "outcome": "accepted",
                         "attempts_used": attempt,
                         "duration_s": round(candidate_duration, 3),
                         "original_chars": len(body),
                         "final_chars": len(compact),
                     })
            return
        if verdict == "skip":
            candidate_duration = __import__("time").perf_counter() - candidate_t0
            log.info("[M] memory[%d] SKIPPED by validator "
                     "(attempt %d/%d, %d chars)",
                     idx, attempt, _INNER_MAX_RETRY, len(body),
                     extra={
                         "event_kind": "candidate_complete",
                         "round_kind": round_kind,
                         "for_tool": cand["tool_name"],
                         "candidate_idx": idx,
                         "candidate_tool": cand["tool_name"],
                         "outcome": "validator_skipped",
                         "attempts_used": attempt,
                         "duration_s": round(candidate_duration, 3),
                         "original_chars": len(body),
                         "final_chars": len(body),
                     })
            return
        log.info("[M] memory[%d] RETRY attempt %d/%d: %s",
                 idx, attempt, _INNER_MAX_RETRY, new_refinement)
        refinement = new_refinement

    new_count = prev_count + 1
    memory[idx]["content"] = (
        f"<tool_result>\n[RETRY:{new_count}] {body}\n</tool_result>"
    )
    candidate_duration = __import__("time").perf_counter() - candidate_t0
    log.info("[M] memory[%d] exhausted %d inner retries, "
             "marked RETRY:%d (%d chars)",
             idx, _INNER_MAX_RETRY, new_count, len(body),
             extra={
                 "event_kind": "candidate_complete",
                 "round_kind": round_kind,
                 "for_tool": cand["tool_name"],
                 "candidate_idx": idx,
                 "candidate_tool": cand["tool_name"],
                 "outcome": "retry_exhausted",
                 "attempts_used": _INNER_MAX_RETRY,
                 "duration_s": round(candidate_duration, 3),
                 "original_chars": len(body),
                 "final_chars": len(body),
             })


async def compact_memory(
    memory: List[Dict[str, str]],
    argo_fn: Callable[..., str],
) -> None:
    """Compress old tool-result blocks with Argo-driven selection + validation.

    Flow:
      0. Build a list of compressible (old) tool results.
      1. Ask main Argo WHICH of those to compress (selection step).
      2. For each selected result, sub-agent compresses it (parallel).
      3. Main Argo validates; on RETRY, refine and retry (up to 3×).
      4. ACCEPT → replace with ``[summary]``; exhausted → ``[RETRY:N+1]``.

    Results not selected by Argo, and the most-recent
    ``KEEP_RECENT_RESULTS`` results, are left untouched.
    """
    import asyncio

    user_objective = ""
    for turn in memory:
        if turn["role"] == "user" and "<tool_result>" not in turn["content"]:
            user_objective = turn["content"][:500]
            break

    round_t0 = __import__("time").perf_counter()
    ctx_chars_before, ctx_turns_before = _memory_context_stats(memory)
    log.info("[M] START session compaction round: %d chars across %d turns",
             ctx_chars_before, ctx_turns_before,
             extra={
                 "event_kind": "round_start",
                 "round_kind": "session",
                 "context_chars_before": ctx_chars_before,
                 "context_turns_before": ctx_turns_before,
             })

    tr_indices = [
        i for i, turn in enumerate(memory)
        if turn["role"] == "user" and "<tool_result>" in turn["content"]
    ]
    eligible = tr_indices
    recent_cutoff = max(0, len(tr_indices) - KEEP_RECENT_RESULTS)

    # ── Build candidate list ──────────────────────────────────────
    candidates: List[dict] = []
    for pos, idx in enumerate(eligible):
        content = memory[idx]["content"]
        m = TOOL_RESULT_TAG_RE.search(content)
        if not m:
            continue
        body = m.group(1)
        if body.startswith("[PLAN]") and not body.startswith("[PLAN:DONE]"):
            continue

        retry_match = _RETRY_RE.match(body)
        retry_count = int(retry_match.group(1)) if retry_match else 0
        display_body = body[retry_match.end():] if retry_match else body

        # Immediate, tool-specific compactors prefix their evidence-preserving
        # output with ``[summary]``.  That output is already the authoritative
        # bounded representation of the tool receipt.  Sending it through the
        # learned session compactor again can erase identifiers or numerical
        # values that the hardcoded compactor deliberately retained.
        if display_body.startswith("[summary]"):
            continue

        if len(display_body) < MIN_COMPRESS_CHARS:
            continue

        if retry_count >= MAX_RETRY:
            memory[idx]["content"] = (
                f"<tool_result>\n{display_body}\n</tool_result>"
            )
            log.info("[M] memory[%d] hit MAX_RETRY=%d — permanently "
                     "keeping original (%d chars)",
                     idx, MAX_RETRY, len(display_body))
            continue

        tool_name = "(unknown)"
        if idx > 0 and memory[idx - 1]["role"] == "assistant":
            tn = _TOOL_NAME_RE.search(memory[idx - 1]["content"])
            if tn:
                tool_name = tn.group(1)

        candidates.append({
            "num":       len(candidates) + 1,
            "idx":       idx,
            "tool_name": tool_name,
            "preview":   display_body[:200].replace("\n", " "),
            "chars":     len(display_body),
            "is_recent":     pos >= recent_cutoff,
            "retry_count":  retry_count,
        })

    if not candidates:
        round_duration = __import__("time").perf_counter() - round_t0
        log.info("[M] Session compaction round skipped: no eligible candidates",
                 extra={
                     "event_kind": "round_complete",
                     "round_kind": "session",
                     "outcome": "no_candidates",
                     "candidates_selected": 0,
                     "candidate_count": 0,
                     "tasks_run": 0,
                     "context_chars_before": ctx_chars_before,
                     "context_chars_after": ctx_chars_before,
                     "context_turns_before": ctx_turns_before,
                     "context_turns_after": ctx_turns_before,
                     "selection_duration_s": 0.0,
                     "round_duration_s": round(round_duration, 3),
                 })
        return

    # ── Context window metrics ────────────────────────────────────
    log.info("[M] Context window: %d chars across %d turns",
             ctx_chars_before, ctx_turns_before)

    # ── Selection (single LLM call) ──────────────────────────────
    selection_t0 = __import__("time").perf_counter()
    chosen = await asyncio.to_thread(
        _select_targets, candidates, user_objective, argo_fn,
        ctx_chars_before, ctx_turns_before,
    )
    selection_duration = __import__("time").perf_counter() - selection_t0
    if not chosen:
        round_duration = __import__("time").perf_counter() - round_t0
        log.info("[M] Argo chose NONE — skipping compression this round.")
        log.info("[M] Session compaction round complete without changes",
                 extra={
                     "event_kind": "round_complete",
                     "round_kind": "session",
                     "outcome": "none",
                     "candidates_selected": 0,
                     "candidate_count": len(candidates),
                     "tasks_run": 0,
                     "context_chars_before": ctx_chars_before,
                     "context_chars_after": ctx_chars_before,
                     "context_turns_before": ctx_turns_before,
                     "context_turns_after": ctx_turns_before,
                     "selection_duration_s": round(selection_duration, 3),
                     "round_duration_s": round(round_duration, 3),
                 })
        return
    chosen_by_num = {sel["num"]: sel for sel in chosen}
    log.info("[M] Argo selected candidates %s for compression",
             [s["num"] for s in chosen])

    # ── Parallel compress + validate (with inner retry) ──────────
    tasks = []
    for cand in candidates:
        if cand["num"] not in chosen_by_num:
            continue
        sel = chosen_by_num[cand["num"]]
        tasks.append(asyncio.to_thread(
            _compress_one_candidate,
            cand, sel, memory, user_objective, argo_fn, "session",
        ))

    if tasks:
        log.info("[M] Running %d compression task(s) in parallel", len(tasks))
        await asyncio.gather(*tasks)

    ctx_chars_after, ctx_turns_after = _memory_context_stats(memory)
    round_duration = __import__("time").perf_counter() - round_t0
    log.info("[M] Session compaction round complete: %d→%d chars across %d→%d turns in %.2fs",
             ctx_chars_before, ctx_chars_after,
             ctx_turns_before, ctx_turns_after, round_duration,
             extra={
                 "event_kind": "round_complete",
                 "round_kind": "session",
                 "outcome": "completed",
                 "candidates_selected": len(chosen),
                 "candidate_count": len(candidates),
                 "tasks_run": len(tasks),
                 "context_chars_before": ctx_chars_before,
                 "context_chars_after": ctx_chars_after,
                 "context_turns_before": ctx_turns_before,
                 "context_turns_after": ctx_turns_after,
                 "selection_duration_s": round(selection_duration, 3),
                 "round_duration_s": round(round_duration, 3),
             })


# ═════════════════════════════════════════════════════════════
#  L0 hint-driven compression (runs once after L0 completes)
# ═════════════════════════════════════════════════════════════

async def compact_l0_with_hints(
    memory: List[Dict[str, str]],
    l0_hints: Dict[str, str],
    argo_fn: Callable[..., str],
) -> None:
    """Compress L0 tool results using preplan-provided hints.

    Unlike ``compact_memory`` this skips the LLM selection step — every
    L0 tool result whose tool name appears in *l0_hints* is compressed
    using the corresponding hint as purpose/task.  The inner retry loop
    (up to ``_INNER_MAX_RETRY``) is reused.

    This runs **once** right after L0 completes and before the planner
    fires.  The hints are exploratory/broad (e.g. "preserve IDs, explore
    data complexity") and are discarded after this pass — they have no
    effect on later execution-phase Tier 2 compression.
    """
    import asyncio

    if not l0_hints:
        return

    round_t0 = __import__("time").perf_counter()
    ctx_chars_before, ctx_turns_before = _memory_context_stats(memory)
    log.info("[M/L0] START L0 hint-driven compaction round: %d chars across %d turns (%d hint(s))",
             ctx_chars_before, ctx_turns_before, len(l0_hints),
             extra={
                 "event_kind": "round_start",
                 "round_kind": "l0",
                 "context_chars_before": ctx_chars_before,
                 "context_turns_before": ctx_turns_before,
             })

    user_objective = ""
    for turn in memory:
        if turn["role"] == "user" and "<tool_result>" not in turn["content"]:
            user_objective = turn["content"][:500]
            break

    tasks = []
    for idx, turn in enumerate(memory):
        if turn["role"] != "user" or "<tool_result>" not in turn["content"]:
            continue
        m = TOOL_RESULT_TAG_RE.search(turn["content"])
        if not m:
            continue
        body = m.group(1)
        if body.startswith("[summary]"):
            continue
        if len(body) < MIN_COMPRESS_CHARS:
            continue

        tool_name = "(unknown)"
        if idx > 0 and memory[idx - 1]["role"] == "assistant":
            tn = _TOOL_NAME_RE.search(memory[idx - 1]["content"])
            if tn:
                tool_name = tn.group(1)

        hint = l0_hints.get(tool_name)
        if hint is None:
            continue

        sel = {
            "purpose": f"L0 discovery — {hint}",
            "task": hint,
        }
        cand = {
            "idx": idx,
            "tool_name": tool_name,
            "num": idx,
        }
        tasks.append(asyncio.to_thread(
            _compress_one_candidate,
            cand, sel, memory, user_objective, argo_fn, "l0",
        ))

    if tasks:
        log.info("[M/L0] Running %d L0 hint-driven compression(s) in parallel",
                 len(tasks))
        await asyncio.gather(*tasks)
        ctx_chars_after, ctx_turns_after = _memory_context_stats(memory)
        round_duration = __import__("time").perf_counter() - round_t0
        log.info("[M/L0] L0 compaction round complete: %d→%d chars across %d→%d turns in %.2fs",
                 ctx_chars_before, ctx_chars_after,
                 ctx_turns_before, ctx_turns_after, round_duration,
                 extra={
                     "event_kind": "round_complete",
                     "round_kind": "l0",
                     "outcome": "completed",
                     "candidates_selected": len(tasks),
                     "candidate_count": len(tasks),
                     "tasks_run": len(tasks),
                     "context_chars_before": ctx_chars_before,
                     "context_chars_after": ctx_chars_after,
                     "context_turns_before": ctx_turns_before,
                     "context_turns_after": ctx_turns_after,
                     "selection_duration_s": 0.0,
                     "round_duration_s": round(round_duration, 3),
                 })
    else:
        log.info("[M/L0] No L0 results matched compression hints — skipping")
        round_duration = __import__("time").perf_counter() - round_t0
        log.info("[M/L0] L0 compaction round skipped: no matching results",
                 extra={
                     "event_kind": "round_complete",
                     "round_kind": "l0",
                     "outcome": "no_matches",
                     "candidates_selected": 0,
                     "candidate_count": 0,
                     "tasks_run": 0,
                     "context_chars_before": ctx_chars_before,
                     "context_chars_after": ctx_chars_before,
                     "context_turns_before": ctx_turns_before,
                     "context_turns_after": ctx_turns_before,
                     "selection_duration_s": 0.0,
                     "round_duration_s": round(round_duration, 3),
                 })
