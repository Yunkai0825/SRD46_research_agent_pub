"""Small element-aware instruction agent used before LC2_3 fan-out."""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence

from ...LC2_2_card_db_merger.element_inventory import (
    ElementInventoryEntry,
    inventory_by_element,
)
from ...LC2_3_card_deduplicator._pair_dedup_subagent._agent_common import (
    AgentTurnResult,
    agent_turn,
    build_client_and_hooks,
    build_tool_instructions,
    cfg,
    strip_fence,
    write_subagent_context,
)


_SYSTEM_PROMPT = """\
You are the expert chemist and electrochemist supervising element-level
deduplication for a speciation calculation. Instruction phase: from the purpose
and the LC2_2 inventory grouped by element, you DESIGN the case-specific system
prompt for every child dedup agent and commit it together with one short
instruction per element. Review phase: inspect the regenerated table and either
correct it, redispatch selected workers, request a full redo, or commit it
final.

**WHAT COUNTS AS A DUPLICATE**
Entries are duplicates when keeping both puts redundant descriptions of the same
physical state on one hull at the given context. Shared composition alone does 
not make them duplicates; differing provenance alone does not make them distinct. 
They are distinct if they can compete for different regions of the pH-potential plane for 
a given context and scenario. This also differs by element — Au and Fe might or might not 
need different treatment depending on the context.

**DESIGN QUESTIONS** (think each one through before drafting; a child agent sees
one group at a time and cannot arbitrate any of these — your case-specific
recommendations must answer the ones that matter here)
- What is this system trying to do — corrosion, electrodeposition, battery,
  catalysis, sensing, solution preparation / stability / instability? If the
  purpose leaves the scenario open, which one do you adopt, and why?
- Which working concentration and context govern aqueous identity — is the
  1e-6 M corrosion convention even appropriate here? Which protonation states
  and polynuclear complexes are real at that regime, and which formula
  spellings are mere notation?
- Hydrated solids, anhydrous solids, or both? What water activity and
  temperature does the scenario imply, and which hydration levels of the same
  chemistry genuinely compete on this hull?
- Are carbonates or other counterion solids competing phases here, or out of
  scope?
- Do mixed-valence / non-stoichiometric oxides stand as distinct redox-chain
  members in this scenario, or are they covered by preferred phases?
- Which phase question is being asked — which phase is STABLE (collapse
  polymorphs to the ground state) or which phase FORMS (retain them)? Is the
  μ spread inside the method's error bar anyway?
- Which elemental reference solids must stay? Do any gases have solved
  equilibria or fugacity constraints, or would they be decorative?
- Does one answer hold for every element in this system (Au and Fe may not
  deserve the same treatment), or do your element instructions need to
  diverge?
These questions deliberately pull against each other; answering them for THIS
calculation, before any child agent runs, is your core task.

**WORKER TEMPLATE** (what each child dedup agent already has)
Children are single-shot workers: one agent per multi-member stoichiometry
group, one batched agent for all singletons, and the same templates rerun on
targeted redispatch. Their fixed template enforces only mechanics: decide the
rows shown, return exact (name, source) pairs via a finalize tool, never empty
a group. Their user message stacks the general dedup plan (static defaults),
your per-element instructions, and the species table (entry_key, family, name,
source, charge, mu_aligned_kJ, multiplier). Your case-specific recommendations
are appended verbatim to each child's SYSTEM prompt — for the automatic
fan-out and every dispatched rerun — and are the ONLY calculation-aware
guidance anywhere in their context: no other agent refines the plan. Do not
restate mechanics or general-plan rules; write only your resolutions.

**HOW TO WRITE**
Case-specific recommendations (the child system-prompt block): a short markdown
bullet list — one bullet per design question you resolved, stating the decision
and the assumption behind it. Element instructions: one or two plain-text
sentences per element — the rule plus its assumption, concrete enough to
dispatch on, transparent enough for a chemist to audit. No redundancy: say so
and stop. Diagram-changing ambiguity (including a missing complex of an implied
ligand or counterion): name it, never resolve it silently. A no-duplicate
outcome is legitimate and normal: a multi-member group of distinct states keeps
every member, and the singleton batch's default verdict is keep — it exists to
prune out-of-scope branches, never to force drops.

**SESSION LIFECYCLE**
Your commits drive the batches; you never converse with workers. Instruction:
one `commit_element_instructions` call carries BOTH the case-specific
recommendations and one instruction per element. Your turn then PAUSES while
the controller deterministically fans out every worker from exactly that
committed guidance and returns the results to you as a refreshed context
(current table + latest diff, no prior conversation). If the inventory needs
no deduplication at all — no true duplicates and no out-of-scope singletons —
commit the same call with `skip_dedup: true`: no workers run, every entry
receives a deterministic keep-all verdict, and the untouched table still
returns to you for review. Only skip when every element instruction states no
redundancy; when unsure, run the batch. Review:
`set_entry_include` fixes one entry, `dispatch_target_dedup` reruns one or a
few groups with targeted guidance, `redo_all_dedup` (optionally with revised
case recommendations) re-commits and reruns the whole batch — only when a
committed rule itself is wrong. A commit-time flag requests explicit review —
fix the selection or `commit_final` with confirmation and a chemistry
rationale. Only a successful `commit_final` completes the session.

**TOOL REFERENCE**
Only the tools exposed for the current phase are callable; their generated tool
descriptions below are authoritative.
- `commit_element_instructions({"case_recommendations":str,
  "instructions":[{"element":str,"instruction":str}, ...],
  "skip_dedup"?:boolean})`
- `set_entry_include({"entry_key":str,"include":boolean,"reason":str})`
- `dispatch_target_dedup({"entry_keys":[str,...],"guidance":str,"reason":str})`
- `redo_all_dedup({"instructions":{"<element>":str,...},"reason":str,
  "case_recommendations"?:str})`
- `commit_final({"summary":str,"confirm_warnings"?:boolean,
  "warning_rationale"?:str})`
"""


@dataclass
class ElementDedupOrchestrationSession:
    """One agent identity spanning instruction and review phases."""

    client: Any
    hooks: Any
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    instructions: Dict[str, str] = field(default_factory=dict)
    case_recommendations: str = ""
    phase: str = "instruction"
    closed: bool = False


# Bounds the supervisor-drafted child system-prompt block.
_MAX_RECOMMENDATION_CHARS = 2400


def _validate_case_recommendations(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return (
            "ERROR: `case_recommendations` must be a non-empty string — the "
            "markdown block appended to every child dedup agent's system "
            "prompt."
        )
    if len(value) > _MAX_RECOMMENDATION_CHARS:
        return (
            f"ERROR: `case_recommendations` exceeds "
            f"{_MAX_RECOMMENDATION_CHARS} characters; state only the resolved "
            "design choices."
        )
    return None


def _sentence_count(text: str) -> int:
    pieces = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text.strip()) if p.strip()]
    return len(pieces)


def _make_instruction_tools(
    slot: Dict[str, Any], elements: List[str],
) -> Dict[str, Callable]:
    expected = set(elements)

    def commit_element_instructions(json_payload: str = "") -> str:
        """Record the child system-prompt block plus one instruction per element.

        Schema: {"case_recommendations":str,
        "instructions":[{"element":str,"instruction":str}, ...],
        "skip_dedup"?:boolean}.  ``case_recommendations`` is appended to every
        child dedup agent's system prompt; each instruction is one or two
        sentences.  ``skip_dedup: true`` skips the worker batch entirely:
        every entry gets a deterministic keep-all verdict and the table goes
        straight to your review.  Skip only when no deduplication or scope
        pruning is needed anywhere.
        """
        try:
            obj = json.loads(strip_fence(json_payload))
        except Exception as exc:
            slot["error"] = f"json_parse_error: {exc!r}"
            return f"ERROR: invalid JSON: {exc!r}"
        recommendations = obj.get("case_recommendations") if isinstance(obj, dict) else None
        recommendation_error = _validate_case_recommendations(recommendations)
        if recommendation_error:
            slot["error"] = "case_recommendations_invalid"
            return recommendation_error
        skip_dedup = obj.get("skip_dedup", False) if isinstance(obj, dict) else False
        if type(skip_dedup) is not bool:
            slot["error"] = "skip_dedup_not_boolean"
            return "ERROR: `skip_dedup`, when given, must be a JSON boolean."
        rows = obj.get("instructions") if isinstance(obj, dict) else None
        if not isinstance(rows, list):
            slot["error"] = "instructions_not_list"
            return "ERROR: `instructions` must be a list."
        parsed: Dict[str, str] = {}
        for row in rows:
            if not isinstance(row, dict):
                slot["error"] = "instruction_not_object"
                return "ERROR: every instruction row must be an object."
            element = row.get("element")
            instruction = row.get("instruction")
            if element not in expected or not isinstance(instruction, str):
                slot["error"] = f"invalid_instruction: {row!r}"
                return f"ERROR: invalid element/instruction row {row!r}."
            if element in parsed:
                slot["error"] = f"duplicate_element: {element}"
                return f"ERROR: duplicate instruction for {element}."
            count = _sentence_count(instruction)
            if count not in (1, 2):
                slot["error"] = f"sentence_count_{element}: {count}"
                return f"ERROR: {element} instruction must contain one or two sentences."
            parsed[element] = instruction.strip()
        missing = sorted(expected - set(parsed))
        extra = sorted(set(parsed) - expected)
        if missing or extra:
            slot["error"] = f"coverage: missing={missing}, extra={extra}"
            return f"ERROR: exact element coverage required; missing={missing}, extra={extra}."
        slot["instructions"] = dict(sorted(parsed.items()))
        slot["case_recommendations"] = recommendations.strip()
        slot["skip_dedup"] = skip_dedup
        slot["error"] = None
        if skip_dedup:
            return (
                f"OK — recorded guidance for {len(parsed)} elements; the "
                "worker batch will be SKIPPED with deterministic keep-all "
                "verdicts and the table returned for your review."
            )
        return (
            f"OK — recorded the child system-prompt block and instructions "
            f"for {len(parsed)} elements."
        )

    return {"commit_element_instructions": commit_element_instructions}


def _render_inventory(inventory: Iterable[ElementInventoryEntry]) -> str:
    lines: List[str] = []
    for element, entries in inventory_by_element(inventory).items():
        lines += [
            f"### Element {element}",
            "| key | phase | family | core | label | source | mu_aligned_kJ |",
            "|-----|-------|--------|------|-------|--------|--------------:|",
        ]
        for entry in entries:
            lines.append(
                f"| `{entry.entry_key}` | {entry.phase} | {entry.phase_family} "
                f"| `{entry.core_label}` | `{entry.label}` | {entry.source} "
                f"| {entry.mu_aligned_kJ:+.3f} |"
            )
        lines.append("")
    return "\n".join(lines)


def build_element_instructions(
    *,
    purpose: str,
    tasks: str,
    inventory: List[ElementInventoryEntry],
    subagent_dir: str | Path,
    debug: bool = False,
) -> Dict[str, Any]:
    """Start one orchestration session and gate on instruction commit."""
    elements = list(inventory_by_element(inventory))
    if not elements:
        return {
            "instructions": None, "session": None,
            "error": "empty_element_inventory", "iterations": 0, "n_tools": 0,
        }

    slot: Dict[str, Any] = {"instructions": None, "error": None}
    client, hooks = build_client_and_hooks()
    session = ElementDedupOrchestrationSession(client=client, hooks=hooks)
    tools = _make_instruction_tools(slot, elements)
    system_prompt = (
        _SYSTEM_PROMPT
        + "\n\nCURRENT PHASE: INSTRUCTION\n"
        + "Commit the case-specific recommendations plus the complete "
        + "instruction set in one call; the worker batch is gated on this "
        + "single action and its results will return to you for review.\n\n"
        + build_tool_instructions(tools)
    )
    user_msg = (
        f"[Orchestration session]\n{session.session_id}\n\n"
        f"[Calculation purpose]\n{purpose}\n\n"
        f"[Requested tasks]\n{tasks}\n\n"
        f"[Complete element inventory]\n{_render_inventory(inventory)}"
    )
    started = time.time()
    try:
        result: AgentTurnResult = agent_turn(
            user_msg,
            system_prompt=system_prompt,
            tools=tools,
            memory=[],
            client=session.client,
            max_iterations=cfg.MAX_TOOL_ITERATIONS,
            timeout=cfg.MAX_TURN_SECONDS,
            required_tools={"commit_element_instructions"},
            # Strict gate: prose cannot end the turn until the commit tool
            # succeeds (validator ERROR returns do not count as success).
            terminal_tools={"commit_element_instructions"},
            hooks=session.hooks,
            is_subagent=True,
        )
        write_subagent_context(
            subagent_dir,
            "LC2 element instruction supervisor",
            result,
            tool_prefix="lc2_element_instruction",
            stage_id="LC2_3.element_instruction",
            role="element dedup orchestrator",
            phase="instruction",
            system_prompt=system_prompt,
            user_message=user_msg,
            tools=tools,
            required_tools={"commit_element_instructions"},
            memory=[],
            metadata={"session_id": session.session_id, "elements": elements},
        )
        committed = slot.get("instructions")
        committed_recommendations = str(slot.get("case_recommendations") or "")
        if committed:
            session.instructions = dict(committed)
            session.case_recommendations = committed_recommendations
            session.phase = "dedup"
        return {
            "instructions": committed,
            "case_recommendations": committed_recommendations or None,
            "skip_dedup": bool(slot.get("skip_dedup")),
            "session": session,
            # A successful commit is authoritative: the model may keep
            # polishing after its first OK and a LATER rejected attempt must
            # not poison the phase (observed 2026-09-05: two OK commits
            # followed by one rejected re-commit failed LC2_3 closed even
            # though valid instructions were latched).  Only report an error
            # when nothing was ever committed.
            "error": (
                None if committed
                else (slot.get("error") or "instruction_not_committed")
            ),
            "iterations": result.iterations,
            "n_tools": len(result.tool_history),
            "elapsed_s": round(time.time() - started, 3),
        }
    except Exception as exc:
        write_subagent_context(
            subagent_dir,
            "LC2 element instruction supervisor",
            None,
            tool_prefix="lc2_element_instruction",
            stage_id="LC2_3.element_instruction",
            role="element dedup orchestrator",
            phase="instruction",
            system_prompt=system_prompt,
            user_message=user_msg,
            tools=tools,
            required_tools={"commit_element_instructions"},
            memory=[],
            error=f"agent_turn_exception: {exc!r}",
            metadata={"session_id": session.session_id, "elements": elements},
        )
        return {
            "instructions": None,
            "session": session,
            "error": f"agent_turn_exception: {exc!r}",
            "iterations": 0,
            "n_tools": 0,
            "elapsed_s": round(time.time() - started, 3),
        }


def _make_review_tools(
    slot: Dict[str, Any],
    *,
    session: ElementDedupOrchestrationSession,
    inventory: Sequence[ElementInventoryEntry],
    blocking_warnings: Sequence[str],
    full_restarts_remaining: int,
    blocking_errors: Sequence[str] = (),
) -> Dict[str, Callable]:
    valid_entries = {entry.entry_key: entry for entry in inventory}
    valid_elements = set(session.instructions)

    def _latch(action: Dict[str, Any]) -> str | None:
        if slot.get("action") is not None:
            return "ERROR: one action is already recorded for this refreshed turn."
        slot["action"] = action
        return None

    def set_entry_include(json_payload: str = "") -> str:
        """Set one exact row. Schema: {entry_key, include:boolean, reason}."""
        try:
            obj = json.loads(strip_fence(json_payload))
        except Exception as exc:
            return f"ERROR: invalid JSON: {exc!r}"
        if not isinstance(obj, dict):
            return "ERROR: payload must be an object."
        entry_key, include, reason = (
            obj.get("entry_key"), obj.get("include"), obj.get("reason")
        )
        if entry_key not in valid_entries:
            return f"ERROR: unknown entry_key {entry_key!r}."
        if type(include) is not bool:
            return "ERROR: include must be a JSON boolean."
        if not isinstance(reason, str) or not reason.strip():
            return "ERROR: a non-empty chemistry reason is required."
        error = _latch({
            "kind": "set_entry_include", "entry_key": entry_key,
            "include": include, "reason": reason.strip(),
        })
        return error or f"OK — {entry_key} will be set to {str(include).lower()}."

    def redo_all_dedup(json_payload: str = "") -> str:
        """Restart from LC2_2. Schema: {instructions:{element:text}, reason,
        case_recommendations?:str} — the optional block replaces the child
        system-prompt recommendations for the rerun."""
        if full_restarts_remaining <= 0:
            return "ERROR: the full re-deduplication limit has been reached."
        try:
            obj = json.loads(strip_fence(json_payload))
        except Exception as exc:
            return f"ERROR: invalid JSON: {exc!r}"
        updates = obj.get("instructions") if isinstance(obj, dict) else None
        reason = obj.get("reason") if isinstance(obj, dict) else None
        if not isinstance(updates, dict) or not updates:
            return "ERROR: instructions must be a non-empty object."
        if not isinstance(reason, str) or not reason.strip():
            return "ERROR: a non-empty restart reason is required."
        revised_recommendations = obj.get("case_recommendations")
        if revised_recommendations is not None:
            recommendation_error = _validate_case_recommendations(
                revised_recommendations
            )
            if recommendation_error:
                return recommendation_error
        clean: Dict[str, str] = {}
        for element, instruction in updates.items():
            if element not in valid_elements or not isinstance(instruction, str):
                return f"ERROR: invalid instruction target {element!r}."
            if _sentence_count(instruction) not in (1, 2):
                return f"ERROR: {element} instruction must be one or two sentences."
            clean[element] = instruction.strip()
        action: Dict[str, Any] = {
            "kind": "redo_all_dedup", "instructions": clean,
            "reason": reason.strip(),
        }
        if isinstance(revised_recommendations, str):
            action["case_recommendations"] = revised_recommendations.strip()
        error = _latch(action)
        return error or "OK — dedup will restart from immutable LC2_2 inputs."

    def dispatch_target_dedup(json_payload: str = "") -> str:
        """Redispatch selected group workers.

        Schema: {entry_keys:[str,...], guidance:str, reason:str}.  Every entry
        key is deterministically mapped to its complete stoichiometric group;
        the worker decides the whole group, not just the named row.
        """
        try:
            obj = json.loads(strip_fence(json_payload))
        except Exception as exc:
            return f"ERROR: invalid JSON: {exc!r}"
        if not isinstance(obj, dict):
            return "ERROR: payload must be an object."
        entry_keys = obj.get("entry_keys")
        guidance = obj.get("guidance")
        reason = obj.get("reason")
        if not isinstance(entry_keys, list) or not entry_keys:
            return "ERROR: entry_keys must be a non-empty list."
        if len(entry_keys) > 8:
            return "ERROR: target at most eight entries per refreshed turn."
        if any(not isinstance(key, str) or key not in valid_entries for key in entry_keys):
            return "ERROR: every entry_key must identify a current inventory row."
        clean_keys = list(dict.fromkeys(entry_keys))
        if not isinstance(guidance, str) or not guidance.strip():
            return "ERROR: non-empty targeted chemistry guidance is required."
        if not isinstance(reason, str) or not reason.strip():
            return "ERROR: a non-empty redispatch reason is required."
        error = _latch({
            "kind": "dispatch_target_dedup",
            "entry_keys": clean_keys,
            "guidance": guidance.strip(),
            "reason": reason.strip(),
        })
        return error or (
            "OK — selected entry keys will be mapped to complete groups and "
            "redispatched."
        )

    def commit_final(json_payload: str = "") -> str:
        """Commit final table and close session.

        Schema: {summary:str, confirm_warnings?:boolean,
        warning_rationale?:str}.  When flags are present the agent must either
        fix them first or explicitly confirm them with a chemistry rationale.
        """
        try:
            obj = json.loads(strip_fence(json_payload))
        except Exception as exc:
            return f"ERROR: invalid JSON: {exc!r}"
        summary = obj.get("summary") if isinstance(obj, dict) else None
        # Several supported agent models naturally emit ``final_summary``
        # from the tool's name. Accept that unambiguous spelling while keeping
        # the persisted controller action canonical as ``summary``.
        if not isinstance(summary, str) and isinstance(obj, dict):
            summary = obj.get("final_summary")
        if not isinstance(summary, str) or not summary.strip():
            return (
                "ERROR: missing required string key `summary` (the alias "
                "`final_summary` is also accepted). Example: "
                '{"summary":"Reviewed final selection."}'
            )
        if blocking_errors:
            return (
                "ERROR: these incomplete dedup results cannot be confirmed; "
                "redispatch the affected targets or restart before committing: "
                + " | ".join(blocking_errors)
            )
        if blocking_warnings:
            confirmed = obj.get("confirm_warnings")
            rationale = obj.get("warning_rationale")
            if type(confirmed) is not bool or not confirmed:
                return (
                    "ERROR: review these commit flags, then either fix the table "
                    "or call commit_final again with confirm_warnings=true and "
                    "a chemistry warning_rationale: "
                    + " | ".join(blocking_warnings)
                )
            if not isinstance(rationale, str) or not rationale.strip():
                return (
                    "ERROR: warning_rationale is required when confirming "
                    "commit-time flags."
                )
        else:
            rationale = ""
        error = _latch({
            "kind": "commit_final",
            "summary": summary.strip(),
            "confirmed_warnings": list(blocking_warnings),
            "warning_rationale": rationale.strip(),
        })
        if error:
            return error
        return "OK — final-table commit recorded for controller confirmation."

    return {
        "set_entry_include": set_entry_include,
        "dispatch_target_dedup": dispatch_target_dedup,
        "redo_all_dedup": redo_all_dedup,
        "commit_final": commit_final,
    }


def run_element_review_phase(
    *,
    session: ElementDedupOrchestrationSession,
    purpose: str,
    tasks: str,
    inventory: Sequence[ElementInventoryEntry],
    post_report: str,
    element_table: str,
    latest_diff: str,
    blocking_warnings: Sequence[str],
    blocking_errors: Sequence[str],
    full_restarts_remaining: int,
    subagent_dir: str | Path,
    debug: bool = False,
) -> Dict[str, Any]:
    """Resume the same agent with refreshed, non-accumulated context."""
    if session.closed:
        return {"action": None, "error": "session_already_closed", "iterations": 0, "n_tools": 0}
    if session.phase not in {"dedup", "review"}:
        return {"action": None, "error": f"invalid_session_phase:{session.phase}", "iterations": 0, "n_tools": 0}
    session.phase = "review"

    slot: Dict[str, Any] = {"action": None}
    tools = _make_review_tools(
        slot, session=session, inventory=inventory,
        blocking_warnings=blocking_warnings,
        full_restarts_remaining=full_restarts_remaining,
        blocking_errors=blocking_errors,
    )
    system_prompt = (
        _SYSTEM_PROMPT
        + "\n\nCURRENT PHASE: REVIEW\n"
        + "Inspect the refreshed table and latest diff. Prefer targeted redispatch "
        + "for localized group errors; commit final only when satisfactory.\n\n"
        + build_tool_instructions(tools)
    )
    instructions = "\n".join(
        f"- {element}: {text}" for element, text in sorted(session.instructions.items())
    )
    committed_recommendations = (
        session.case_recommendations.strip() or "- none committed"
    )
    warnings = "\n".join(f"- {item}" for item in blocking_warnings) or "- none"
    errors = "\n".join(f"- {item}" for item in blocking_errors) or "- none"
    user_msg = (
        f"[Orchestration session]\n{session.session_id}\n\n"
        f"[Calculation purpose]\n{purpose}\n\n"
        f"[Requested tasks]\n{tasks}\n\n"
        f"[Committed case-specific recommendations — in every child system prompt]\n"
        f"{committed_recommendations}\n\n"
        f"[Committed element instructions]\n{instructions}\n\n"
        f"[Commit-time chemistry flags]\n{warnings}\n\n"
        f"[Unconfirmable incomplete-result errors]\n{errors}\n\n"
        f"[Latest diff only]\n{latest_diff}\n\n"
        f"[Current element table]\n{element_table}\n\n"
        f"[Current post-deduplication report]\n{post_report}"
    )
    started = time.time()
    try:
        result: AgentTurnResult = agent_turn(
            user_msg, system_prompt=system_prompt, tools=tools, memory=[],
            client=session.client, max_iterations=cfg.MAX_TOOL_ITERATIONS,
            timeout=cfg.MAX_TURN_SECONDS, required_tools=set(tools),
            # Strict gate: each refreshed review turn must land exactly one
            # successful action (the latch rejects a second one).
            terminal_tools=set(tools),
            hooks=session.hooks, is_subagent=True,
        )
        write_subagent_context(
            subagent_dir, "LC2 element orchestration review phase", result,
            tool_prefix="lc2_element_orchestrator_review",
            stage_id="LC2_3.element_review",
            role="element dedup orchestrator",
            phase="review",
            system_prompt=system_prompt,
            user_message=user_msg,
            tools=tools,
            required_tools=set(tools),
            memory=[],
            metadata={
                "session_id": session.session_id,
                "blocking_warnings": list(blocking_warnings),
                "blocking_errors": list(blocking_errors),
                "full_restarts_remaining": full_restarts_remaining,
            },
        )
        return {
            "action": slot.get("action"),
            "error": None if slot.get("action") else "no_review_action",
            "iterations": result.iterations,
            "n_tools": len(result.tool_history),
            "elapsed_s": round(time.time() - started, 3),
            "session_id": session.session_id,
        }
    except Exception as exc:
        write_subagent_context(
            subagent_dir, "LC2 element orchestration review phase", None,
            tool_prefix="lc2_element_orchestrator_review",
            stage_id="LC2_3.element_review",
            role="element dedup orchestrator",
            phase="review",
            system_prompt=system_prompt,
            user_message=user_msg,
            tools=tools,
            required_tools=set(tools),
            memory=[],
            error=f"agent_turn_exception: {exc!r}",
            metadata={
                "session_id": session.session_id,
                "blocking_warnings": list(blocking_warnings),
                "blocking_errors": list(blocking_errors),
                "full_restarts_remaining": full_restarts_remaining,
            },
        )
        return {
            "action": None, "error": f"agent_turn_exception: {exc!r}",
            "iterations": 0, "n_tools": 0,
            "elapsed_s": round(time.time() - started, 3),
            "session_id": session.session_id,
        }


__all__ = [
    "ElementDedupOrchestrationSession",
    "build_element_instructions",
    "run_element_review_phase",
]
