"""
Strategy Planner for the SRD-46 Database Subagent
==================================================
A specialised LLM-based planning agent that converts free-text user
questions into structured, editable search strategies. The main
ReAct agent calls this as a regular tool, receives a plan, and can
accept / edit / reject / redesign it at any step.

Design philosophy:
  "Like coding but for solution thermodynamics with a real database."
  The planner knows the toolset, the data schema, domain pitfalls,
  and common workflow patterns — so the main agent stays lightweight.

Public API
----------
``plan_search_strategy(question, context, revision_note, system_prompt_module)``
    Returns a plain-text strategy the main agent can follow.  The optional
    module supplements the established planner/evaluator system prompts.
"""

import json
import hashlib
import logging
import os
import time
import requests

log = logging.getLogger("SRD46-Planner")

import sys as _sys
_sys.path.insert(0, str(__import__('pathlib').Path(__file__).absolute().parent.parent))
from NIST_SRD46_db_agent.NIST_SRD46_query_agent import argo_config as _argo_config
from NIST_SRD46_db_agent.NIST_SRD46_query_agent.argo_config import (
    API_URL as _API_URL,
    API_USER as _API_USER,
    HEADERS as _HEADERS,
    is_claude_model,
)


_RAW_SQL_ENABLED = _argo_config.is_mcp_tool_enabled("execute_srd46_sql")
_DB_UTILITY_LINES = [
    "  db_count_records(table, where?)",
    "  db_distribution(table, group_column, where?, limit?)",
    "  db_ranked_pairs(rank_by, limit?, where?)",
    "  get_table_schema(table_name, database)",
]
if _RAW_SQL_ENABLED:
    _DB_UTILITY_LINES.append(
        "  execute_srd46_sql(sql_query, task_description, column_legend, attach_equilibrium?, attach_literature?)"
        "  — ADVANCED / HIGHEST-LEVEL TOOL: most powerful query path, but assumes you are"
        "  oriented around the canonical entities (metal_id, ligand_id, beta_definition_id), the"
        "  cards/stability_measured column semantics, and how those entities constrain each other"
        "  — both chemically (structure ↔ protonation ↔ oxidation state ↔ β-definition) and across"
        "  measurement conditions (T, ionic strength, ionic medium); use"
        "  for multi-table self-joins, custom aggregations, or derived columns (e.g. ΔlogK"
        "  selectivity). task_description (>=40 chars, ONE BRIEF SENTENCE) AND column_legend (dict"
        "  per output column, including SELECT aliases like 'logK_Fe3' and computed cols like"
        "  'delta_logK'; each entry must spell out source table.column or formula, filter/join,"
        "  physical meaning + units + species, and for computed cols the formula AND its"
        "  interpretation) are REQUIRED. Both are preserved verbatim in <tool_context> alongside"
        "  the rows. Bare entity-ID columns (metal_id / ligand_id / beta_definition_id) in your"
        "  SELECT are auto-enriched in the result with the canonical fields the SELECT omitted."
    )

_PLANNER_TOOL_SELECTION_RULE = (
    "- Prefer domain tools before raw SQL.\n"
    if _RAW_SQL_ENABLED
    else "- Prefer domain tools before lower-level database utilities.\n"
)

_EVALUATOR_TOOL_SELECTION_RULE = (
    "   - Prefer search_stability / search_pka_* / search_networks / search_citations /\n"
    "     inspect_card / inspect_literature before raw SQL.\n"
    if _RAW_SQL_ENABLED
    else "   - Prefer search_stability / search_pka_* / search_networks / search_citations /\n"
    "     inspect_card / inspect_literature before lower-level database utilities.\n"
)

_EVALUATOR_REDESIGN_EXAMPLES = [
    "  REDESIGN: Question asks to compare Cu2+ vs Zn2+ but the plan only covers Cu2+. Add Zn2+ and require matched temperature / ionic strength.",
    "  REDESIGN: The plan repeats L0 discovery even though the planner is called after L0 is complete.",
]
if _RAW_SQL_ENABLED:
    _EVALUATOR_REDESIGN_EXAMPLES.insert(
        0,
        "  REDESIGN: Step 2 uses raw SQL even though search_citations or inspect_literature would answer the provenance question directly.",
    )
else:
    _EVALUATOR_REDESIGN_EXAMPLES.insert(
        0,
        "  REDESIGN: Step 2 detours through get_table_schema even though search_citations or inspect_literature would answer the provenance question directly.",
    )


# ═════════════════════════════════════════════════════════════
#  PRE-PLAN DECISION TOOL
# ═════════════════════════════════════════════════════════════

_PREPLAN_SYSTEM = r"""You are a fast **Triage Agent** for a NIST SRD-46 database subagent.
Given a user's chemistry question, decide:
  1. What TASK TYPE is this?  (lookup | comparison | pKa | citation | provenance | exploration | multi-step)
  2. Which METALS should the agent search first?  (give common names)
  3. Which LIGANDS should the agent search first? (give common names)
  4. Which L0 initialisation tools are NEEDED for this question?
  5. Any special notes for the search phase?
  6. What should be PRESERVED when compressing L0 tool results?

L0 TOOLS (only include those actually needed):
  - "search_metals"   — needed when the question involves specific metals
  - "search_ligands"  — needed when the question involves specific ligands
  - "build_system_catalog" — needed when you need species/network overview for resolved metal-ligand pairs
                         (requires at least one metal AND one ligand)
Examples:
  - "log K for Cu-glycine" → all three
  - "pKa of citric acid"  → ["search_metals", "search_ligands", "build_system_catalog"]  (H+ is the metal for pKa)
  - "citation for 62Pc"   → [] (no metals or ligands needed)
  - "all ligands for Zn"  → ["search_metals"] (ligands discovered later via L1)

DOMAIN HINTS:
- "stability constant" / "log K" / "binding" → lookup or comparison
- "pKa" / "dissociation" / "protonation" / "pH" → pKa  (H+ is ALWAYS the metal for these — include metals: ["H+"])
- "citation" / "reference" / "paper" / shortcut code → citation
- "all ligands for metal X" / "survey" → exploration
- Multiple metals or ligands → comparison or multi-step
- If user asks about a metal without specifying oxidation state,
  list BOTH common states (e.g. "Fe(II)" AND "Fe(III)" for iron)
- pKa / dissociation / protonation / pH questions ALWAYS imply H+ as the metal.
  SRD-46 stores H+ as a metal entry — always include metals: ["H+"] for these tasks.
- build_system_catalog is highly recommended to understand the landscape of species and networks for any question involving BOTH metals (including H+) and ligands — it provides a comprehensive overview that guides all subsequent searches.

L0 COMPRESSION HINTS:
After L0 tools run, their results are compressed to free context space.
Provide a dict mapping each L0 tool name to a SHORT exploratory instruction
describing what to preserve.  These should be BROAD and EXPLORATORY — the
agent is still discovering the data landscape, so hints like "explore data
complexity, preserve IDs and structural overview" are better than narrow
instructions like "keep only field X".
If no L0 tools are needed, use "l0_compression_hints": {}.

RESPOND WITH EXACTLY this JSON (no markdown fences, no extra text):
{"task_type": "...", "metals": ["..."], "ligands": ["..."], "l0_needed": ["..."], "notes": "...", "l0_compression_hints": {"tool_name": "hint", ...}}

Keep "notes" to ONE sentence. If no metals or ligands are implied, use [].
If no L0 tools are needed, use "l0_needed": [].
"""


def preplan_decision(question: str) -> str:
    """Lightweight LLM triage: identify task type, metals, and ligands
    of interest BEFORE the agent starts L0 searches.

    Returns a JSON string with keys: task_type, metals, ligands, notes.
    """
    from NIST_SRD46_db_agent.NIST_SRD46_query_agent.argo_config import PREPLAN_TEMPERATURE, PREPLAN_MAX_TOKENS, PREPLAN_TIMEOUT

    log.info("[PP] Pre-plan called: %.120s", question)
    payload = {
        "user":        _API_USER,
        "model":       _argo_config.PLANNER_MODEL,
        "system":      _PREPLAN_SYSTEM,
        "prompt":      [question],
        "stop":        [],
        "temperature": PREPLAN_TEMPERATURE,
        "max_tokens":  PREPLAN_MAX_TOKENS,
    }
    if not is_claude_model(_argo_config.PLANNER_MODEL):
        payload["top_p"] = 0.9
    t0 = time.time()
    last_err = None
    for attempt in range(1, 4):
        try:
            r = requests.post(_API_URL, headers=_HEADERS, json=payload,
                              timeout=PREPLAN_TIMEOUT)
            if r.status_code == 500:
                last_err = f"500: {r.text[:200]}"
                time.sleep(2 * attempt)
                continue
            r.raise_for_status()
            raw = r.json().get("response", "")
            if isinstance(raw, dict):
                raw = json.dumps(raw)
            break
        except requests.RequestException as e:
            last_err = str(e)
            time.sleep(2 * attempt)
    else:
        raise RuntimeError(f"Pre-plan LLM failed after 3 attempts: {last_err}")

    elapsed = time.time() - t0
    log.info("[PP] Pre-plan responded in %.1f s (%d chars)", elapsed, len(raw))

    # Parse — tolerate markdown fences
    import re as _re
    cleaned = _re.sub(r"```(?:json)?\s*", "", raw).replace("```", "").strip()
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        log.warning("[PP] Failed to parse pre-plan JSON: %s", cleaned[:200])
        result = {"task_type": "unknown", "metals": [], "ligands": [],
                  "notes": f"Parse error — raw: {cleaned[:300]}"}

    result["_meta"] = {"model": _argo_config.PLANNER_MODEL, "elapsed_s": round(elapsed, 2)}
    return "[PREPLAN]\n" + json.dumps(result, indent=2)


# ═════════════════════════════════════════════════════════════
#  PLANNER SYSTEM PROMPT
# ═════════════════════════════════════════════════════════════
_PLANNER_SYSTEM = (
        "You are the **Strategy Planner** for a NIST SRD-46 database subagent.\n\n"
        "Your ONLY job: given a user's chemistry question and any resolved context,\n"
        "produce a short search advisory the execution agent can follow.\n"
        "You do NOT execute tools.\n\n"
        "CURRENT TOOL SURFACE:\n"
        "- L0 discovery (already completed before planning when required):\n"
        "  search_metals, search_ligands, build_system_catalog\n"
        "- Core execution (each accepts a full SQL WHERE string with optional\n"
        "  ORDER BY / LIMIT inside the same string, e.g. \"c.metal_id = 41 AND\n"
        "  c.ligand_id IN (5760, 9058) ORDER BY s.constant_value DESC LIMIT 20\"):\n"
        "  search_stability(sql_where_query, ligand_similarity?, include_groups?, exclude_groups?)\n"
        "  search_pka_values(sql_where_query, ligand_similarity?, include_groups?, exclude_groups?)\n"
        "  search_pka_ligands(sql_where_query, ligand_similarity?, include_groups?, exclude_groups?)\n"
        "  search_networks(sql_where_query, ligand_similarity?)\n"
        "  search_citations(sql_where_query)\n"
        "  inspect_card(prefix_id)\n"
        "  inspect_literature(prefix_id)\n"
        "  search_similar_ligands(ligand_id?, ligand_name?, top_k?, metal_ids?, metric?, min_similarity?)\n"
        "- Database utilities:\n"
        + "\n".join(_DB_UTILITY_LINES)
        + "\n\n"
        "ID CONVENTION:\n"
        "All entity IDs use canonical prefixes: metal_N, ligand_N, vlm_N, beta_def_N\n"
        "(e.g. metal_41, ligand_5760, vlm_93847, beta_def_812). inspect_card and\n"
        "inspect_literature accept these directly. SQL-WHERE tools also resolve prefixed\n"
        "IDs automatically (e.g. c.metal_id = metal_41 becomes c.metal_id = 41).\n\n"
        "PLANNING RULES:\n"
        "- Plans should NOT repeat L0 steps. L0 is already done when the planner is called.\n"
        "- Reference resolved prefixed IDs from context, not free-text names, whenever possible.\n"
        + _PLANNER_TOOL_SELECTION_RULE
        + "- For shortcut-code / bibliography lookups, start with search_citations; only fall back to inspect_literature or other lower-level utilities if search_citations cannot answer.\n"
        "- Use inspect_card / inspect_literature for provenance and deep dives on a specific prefix_id.\n"
        "- search_stability, search_pka_values, search_pka_ligands, search_networks, and\n"
        "  search_citations are SQL-WHERE tools. The execution agent writes the WHERE clause;\n"
        "  your job is to say what should be filtered and why.\n"
        "- For comparisons, remind the agent to match temperature and ionic strength conditions.\n"
        "- For iron, copper, and similar cases with multiple oxidation states, cover both unless the user narrows it.\n"
        "- For pKa / protonation questions, H+ is the metal context in SRD-46.\n"
        "- Keep the plan short. Most queries need 2-5 steps.\n\n"
        "OUTPUT FORMAT — plain-text advisory, about 300 tokens max:\n\n"
        "TYPE: <lookup|comparison|pKa|citation|provenance|exploration|multi-step>\n\n"
        "APPROACH:\n"
        "1. <what to look at first, mentioning tool names as suggestions not commands>\n"
        "2. <next step, referencing IDs from context where available>\n"
        "3. …\n\n"
        "WATCH OUT:\n"
        "- <query-specific pitfall — not generic advice>\n\n"
        "DONE WHEN: <one sentence defining success>\n\n"
        "RULES:\n"
        "- 2-5 numbered approach lines typical, max 7.\n"
        "- Skip L0 steps (already done before planner is called).\n"
        "- Reference resolved IDs from context, not human names.\n"
        "- Suggest tools but do NOT dictate exact parameters — the agent decides.\n"
        "- For comparisons, remind the agent to match (T, I) conditions.\n"
        "- Keep pitfalls SPECIFIC to this query.\n"
        "- No JSON, no code fences, no markdown headers.\n"
)


def _compose_system_prompt(base_prompt: str, system_prompt_module: str = "") -> str:
    """Append an optional, lower-priority module to an existing system prompt.

    Returning ``base_prompt`` directly when no module is supplied is
    intentional: ordinary planner and evaluator requests retain their exact
    historical system prompts.  A module supplements the base contract; it
    never replaces or weakens it.
    """
    module = str(system_prompt_module or "").strip()
    if not module:
        return base_prompt
    return (
        base_prompt
        + "\n\n"
        + "SUPPLEMENTAL PLANNING SYSTEM-PROMPT MODULE "
          "(lower priority than the base prompt):\n"
        + "The following caller-supplied instructions refine this planning "
          "task. Follow them only where they do not conflict with the base "
          "prompt above.\n"
        + "<planning_system_prompt_module>\n"
        + module
        + "\n</planning_system_prompt_module>\n"
    )


def _call_planner_llm(
    prompt: str,
    system_prompt_module: str = "",
) -> str:
    """Single Argo API call with the planner system prompt."""
    from NIST_SRD46_db_agent.NIST_SRD46_query_agent.argo_config import PLANNER_TEMPERATURE, PLANNER_MAX_TOKENS, PLANNER_TIMEOUT
    payload = {
        "user":        _API_USER,
        "model":       _argo_config.PLANNER_MODEL,
        "system":      _compose_system_prompt(
            _PLANNER_SYSTEM, system_prompt_module
        ),
        "prompt":      [prompt],
        "stop":        [],
        "temperature": PLANNER_TEMPERATURE,
        "max_tokens":  PLANNER_MAX_TOKENS,
    }
    if not is_claude_model(_argo_config.PLANNER_MODEL):
        payload["top_p"] = 0.9
    last_err = None
    for attempt in range(1, 4):
        try:
            r = requests.post(_API_URL, headers=_HEADERS, json=payload,
                              timeout=PLANNER_TIMEOUT)
            if r.status_code == 500:
                last_err = f"500: {r.text[:200]}"
                time.sleep(2 * attempt)
                continue
            r.raise_for_status()
            text = r.json().get("response", "")
            if isinstance(text, dict):
                text = json.dumps(text)
            return text
        except requests.RequestException as e:
            last_err = str(e)
            time.sleep(2 * attempt)
    raise RuntimeError(f"Planner LLM failed after 3 attempts: {last_err}")


# ═════════════════════════════════════════════════════════════
#  PLAN EVALUATOR SYSTEM PROMPT
# ═════════════════════════════════════════════════════════════
_EVALUATOR_SYSTEM = (
        "You are the **Plan Evaluator** for a NIST SRD-46 database subagent.\n\n"
        "You receive:\n"
        "  1. The user's chemistry question.\n"
        "  2. A plain-text search advisory produced by a planner agent.\n\n"
        "Your job: decide whether the advisory is GOOD ENOUGH to guide execution,\n"
        "or needs REDESIGN.  You know the toolset, the data schema, and common pitfalls.\n\n"
        "EVALUATION CRITERIA:\n\n"
        "A. L0 ALREADY DONE\n"
        "   - Plans should NOT include search_metals, search_ligands, or build_system_catalog.\n"
        "   - Plans should use resolved prefixed IDs from context (metal_N, ligand_N, vlm_N, beta_def_N).\n\n"
        "B. COMPLETENESS\n"
        "   - Does the plan cover every entity or comparison the user asked about?\n"
        "   - For multi-oxidation-state metals, does it cover all relevant states unless narrowed?\n\n"
        "C. TOOL SELECTION\n"
        "   - Are the right current tools suggested?\n"
        + _EVALUATOR_TOOL_SELECTION_RULE
        + "\n"
        "D. CONDITION MATCHING\n"
        "   - For comparisons, does the plan mention matching temperature and ionic strength?\n\n"
        "E. CONCISENESS\n"
        "   - Is the plan 2-7 steps, with no redundant work?\n\n"
        "═══════════════════════════════════════════════════════════════\n"
        " DECISION FORMAT  (respond with EXACTLY one of these)\n"
        "═══════════════════════════════════════════════════════════════\n\n"
        "If the plan is acceptable:\n"
        "  ACCEPT\n\n"
        "If the plan needs changes, respond with:\n"
        "  REDESIGN: <specific, actionable feedback in 1-3 sentences>\n\n"
        "Examples of REDESIGN feedback:\n"
        + "\n".join(_EVALUATOR_REDESIGN_EXAMPLES)
        + "\n\n"
        "RULES:\n"
        "- Be SPECIFIC about what is wrong and how to fix it.\n"
        "- Do NOT redesign plans that are merely suboptimal — only reject ones\n"
        "  with clear errors or missing coverage.\n"
        "- One-word \"ACCEPT\" if the plan is reasonable.\n"
)


def _call_evaluator_llm(
    prompt: str,
    system_prompt_module: str = "",
) -> str:
    """Single Argo API call with the evaluator system prompt."""
    from NIST_SRD46_db_agent.NIST_SRD46_query_agent.argo_config import EVALUATOR_TEMPERATURE, EVALUATOR_MAX_TOKENS, EVALUATOR_TIMEOUT
    payload = {
        "user":        _API_USER,
        "model":       _argo_config.PLANNER_MODEL,
        "system":      _compose_system_prompt(
            _EVALUATOR_SYSTEM, system_prompt_module
        ),
        "prompt":      [prompt],
        "stop":        [],
        "temperature": EVALUATOR_TEMPERATURE,
        "max_tokens":  EVALUATOR_MAX_TOKENS,
    }
    if not is_claude_model(_argo_config.PLANNER_MODEL):
        payload["top_p"] = 0.9
    last_err = None
    for attempt in range(1, 4):
        try:
            r = requests.post(_API_URL, headers=_HEADERS, json=payload,
                              timeout=EVALUATOR_TIMEOUT)
            if r.status_code == 500:
                last_err = f"500: {r.text[:200]}"
                time.sleep(2 * attempt)
                continue
            r.raise_for_status()
            text = r.json().get("response", "")
            if isinstance(text, dict):
                text = json.dumps(text)
            return text.strip()
        except requests.RequestException as e:
            last_err = str(e)
            time.sleep(2 * attempt)
    raise RuntimeError(f"Evaluator LLM failed after 3 attempts: {last_err}")


def _evaluate_plan(
    question: str,
    plan_text: str,
    system_prompt_module: str = "",
) -> str:
    """Ask the evaluator whether a plan is acceptable or needs redesign.

    Returns
    -------
    str
        "ACCEPT" or "REDESIGN: <feedback>"
    """
    prompt = (
        f"USER QUESTION:\n{question}\n\n"
        f"PROPOSED ADVISORY:\n{plan_text}\n\n"
        "Evaluate this advisory against ALL criteria. "
        "Respond with ACCEPT or REDESIGN: <feedback>."
    )
    t0 = time.time()
    raw = _call_evaluator_llm(prompt, system_prompt_module)
    elapsed = time.time() - t0
    log.info("[E] Evaluator responded in %.1f s: %.200s", elapsed, raw)
    return raw


# ═════════════════════════════════════════════════════════════
#  PUBLIC API
# ═════════════════════════════════════════════════════════════

def plan_search_strategy(
    question: str,
    context: str = "",
    revision_note: str = "",
    system_prompt_module: str = "",
) -> str:
    """Ask the planner LLM to produce (or revise) a search strategy.

    Parameters
    ----------
    question : str
        The user's original chemistry question.
    context : str
        Optional context from previous tool results, catalog, or
        earlier plan attempts the main agent wants the planner to
        consider.  Keeps the planner aware of what data has already
        been retrieved.
    revision_note : str
        If non-empty, this is a revision request.  The planner will
        treat ``context`` as the previous plan and apply the edits
        described in ``revision_note``.
    system_prompt_module : str
        Optional supplemental system-prompt instructions for this planning
        task.  They are appended to (and have lower priority than) the
        established planner and evaluator system prompts.  The default empty
        value preserves the historical prompts exactly.

    Returns
    -------
    str
        JSON string with the structured strategy (or an error dict).
    """
    parts = [f"USER QUESTION:\n{question}"]

    if revision_note:
        parts.append(
            f"\nPREVIOUS PLAN / CONTEXT:\n{context}\n\n"
            f"REVISION REQUEST:\n{revision_note}\n\n"
            "Produce an UPDATED plan incorporating the requested changes. "
            "Keep steps that are still valid; modify or add only what is needed."
        )
    elif context:
        parts.append(
            f"\nCONTEXT (prior tool results or catalog):\n{context}\n\n"
            "Use this context to inform your plan — e.g., if metal/ligand IDs "
            "are already resolved, skip the L0 resolution steps."
        )

    prompt = "\n".join(parts)
    log.info("[P] Planner called: question=%.120s… revision=%s",
             question, bool(revision_note))

    t0 = time.time()
    raw = _call_planner_llm(prompt, system_prompt_module)
    elapsed = time.time() - t0
    log.info("[P] Planner responded in %.1f s (%d chars)", elapsed, len(raw))

    plan_text = raw.strip()

    # ── Plan Evaluation (skip for revision requests — already redesigned) ──
    if not revision_note:
        try:
            verdict = _evaluate_plan(
                question, plan_text, system_prompt_module
            )
        except RuntimeError as e:
            log.warning("[E] Evaluator failed, accepting plan as-is: %s", e)
            verdict = "ACCEPT"

        if verdict.upper().startswith("REDESIGN"):
            feedback = verdict.split(":", 1)[1].strip() if ":" in verdict else verdict
            log.info("[E] Plan REJECTED — redesigning: %s", feedback)

            # One retry with evaluator feedback as revision_note
            redesign_parts = [
                f"USER QUESTION:\n{question}",
                f"\nPREVIOUS PLAN / CONTEXT:\n{plan_text}\n\n"
                f"REVISION REQUEST:\n{feedback}\n\n"
                "Produce an UPDATED plan incorporating the requested changes. "
                "Keep steps that are still valid; modify or add only what is needed.",
            ]
            redesign_prompt = "\n".join(redesign_parts)
            t1 = time.time()
            raw2 = _call_planner_llm(
                redesign_prompt, system_prompt_module
            )
            elapsed2 = time.time() - t1
            log.info("[P] Planner redesign responded in %.1f s (%d chars)",
                     elapsed2, len(raw2))
            plan_text = raw2.strip()
            plan_text += f"\n\n[EVAL FEEDBACK: {feedback}]"
            elapsed += elapsed2  # total planning time
        else:
            log.info("[E] Plan ACCEPTED")

    # Attach lightweight metadata as a footer line
    module = str(system_prompt_module or "").strip()
    module_meta = ""
    if module:
        module_sha256 = hashlib.sha256(module.encode("utf-8")).hexdigest()
        module_meta = (
            f", system_prompt_module_sha256={module_sha256}, "
            f"system_prompt_module_chars={len(module)}"
        )
    meta = (
        f"[_meta: model={_argo_config.PLANNER_MODEL}, "
        f"elapsed={elapsed:.1f}s, revision={bool(revision_note)}"
        f"{module_meta}]"
    )
    return f"[PLAN]\n{plan_text}\n{meta}"
