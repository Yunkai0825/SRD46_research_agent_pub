"""dedup_decision_agent.py — calculation-aware dedup addendum generator.

One small LLM agent reads the L0 ``purpose`` + ``tasks`` and emits a
*high-level addendum* to the default dedup plan
(:mod:`dedup_general_plan`).  The addendum tells the per-group and
singleton subagents what THIS calculation needs to preserve or prefer —
most importantly the polymorph / hydration-state and redox-coverage
choices that the static plan deliberately defers.

Why this exists
---------------
Whether two "same-core" solids are redundant is calculation-dependent:

* **Aqueous, room-T speciation / Pourbaix** — the hydrated oxyhydroxide
  (e.g. ``Fe(OH)3`` / ``FeOOH``) is what precipitates from solution, so
  it is usually the phase to keep; the anhydrous oxide (``Fe2O3``,
  hematite) is often the dry / high-T counterpart and can be dropped.
* **Dry / high-temperature / roasting systems** — the reverse: keep the
  anhydrous oxide, drop the hydrated form.
* **Phase-survey / "show everything"** — keep BOTH polymorphs.

The agent encodes that reasoning into a short addendum so the downstream
keep/drop agents act with the right intent instead of a blind default.

Public API
----------
* :func:`build_dedup_plan` — returns ``{"plan", "addendum", ...}``.
* :data:`GENERAL_PLAN_PATH`, :func:`load_general_plan`.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, List

from .._pair_dedup_subagent._agent_common import (
    AgentTurnResult,
    agent_turn,
    build_client_and_hooks,
    build_tool_instructions,
    cfg,
    strip_fence,
    write_subagent_context,
)

log = logging.getLogger("Analysis.LC2_3.decision")

GENERAL_PLAN_PATH = Path(__file__).with_name("dedup_general_plan.md")


def load_general_plan() -> str:
    """Return the default dedup plan markdown (empty string if missing)."""
    try:
        return GENERAL_PLAN_PATH.read_text(encoding="utf-8")
    except OSError as exc:                       # pragma: no cover
        log.warning("dedup_general_plan.md unreadable: %s", exc)
        return ""


_DECISION_SYSTEM_PROMPT = """\
You are the **LC2_3 dedup-decision agent**.

You do NOT keep or drop any species yourself.  You read the scientific
`purpose` + `tasks` for a thermodynamic speciation / Pourbaix
calculation and write a SHORT, high-level **addendum** to the default
deduplication plan.  The per-group and singleton dedup subagents read
the default plan PLUS your addendum to decide which species survive.

The full default plan is given to you in the user message.  It ALREADY
mandates: keep distinct nuclearity (mono- vs polynuclear), keep the full
oxidation-state ladder, keep distinct charge / phase / protonation /
complexation states, never empty a group, and "when unsure, keep".

**Do NOT restate, paraphrase, or re-justify any of those default rules.**
The addendum is ONLY for guidance that the default plan does NOT already
fix — i.e. the one thing it explicitly DEFERS plus anything the purpose
makes calculation-specific:

1. **Polymorph / hydration tie-break** (the only point the default
   defers). Same-core solids that differ only by water content or
   crystal form — tell the subagents which to prefer:
   - Aqueous, near-room-T speciation / Pourbaix → prefer the hydrated
     oxyhydroxide (what precipitates from solution); the anhydrous oxide
     may be dropped.
   - Dry / high-T / roasting / calcination → prefer the anhydrous oxide;
     drop the hydrated form.
   - Phase survey / "include all phases" → keep BOTH.
2. **Scope pruning.** Only if the purpose makes some species clearly out
   of scope (wrong element set, irrelevant phase) that singletons may
   prune — name the criterion, not individual species.

Rules for the addendum:
* **Maximum two lines.** High-level guidance only; no individual species
  unless the purpose names them.
* **Strictly additive / divergent.** Every line must say something the
  default plan does not already say. If a line merely repeats a default
  rule, delete it.
* State preferences as guidance ("prefer the hydrated solid"), not hard
  species lists.
* If the default plan already covers this calculation and the only
  refinement would be the hydration tie-break with no clear preference,
  set `addendum` to exactly `No addendum needed`.  When unsure, bias
  toward KEEPING species.

Output contract
---------------
Call `finalize_dedup_addendum` exactly once with:

  {"addendum": "<markdown bullet list>",
   "rationale": "<one sentence on how purpose/tasks drove it>"}

When NO refinement is needed, use the exact string `No addendum needed`:

  {"addendum": "No addendum needed",
   "rationale": "<one sentence on why the default plan already suffices>"}

After a successful `finalize_dedup_addendum` you may emit your answer
block.
"""


def _make_decision_tools(slot: Dict[str, Any]) -> Dict[str, Callable]:
    import json

    def finalize_dedup_addendum(json_payload: str = "") -> str:
        """Capture the high-level dedup addendum for this calculation.

        Schema: {"addendum": str, "rationale": str}.  ``addendum`` is the
        markdown text appended below the default dedup plan.
        """
        raw = strip_fence(json_payload)
        if not raw:
            slot["error"] = "empty payload"
            return "ERROR: empty `json_payload`."
        try:
            obj = json.loads(raw)
        except Exception as exc:
            slot["error"] = f"json_parse_error: {exc!r}"
            return f"ERROR: json.loads failed: {exc!r}."
        if not isinstance(obj, dict):
            slot["error"] = "payload_not_object"
            return "ERROR: payload must be a JSON object."
        addendum = obj.get("addendum")
        if not isinstance(addendum, str) or not addendum.strip():
            slot["error"] = "addendum_not_str"
            return "ERROR: `addendum` must be a non-empty string."
        slot["payload"] = {
            "addendum":  addendum.strip(),
            "rationale": str(obj.get("rationale", "")).strip(),
        }
        slot["error"] = None
        return "OK — addendum recorded."

    return {"finalize_dedup_addendum": finalize_dedup_addendum}


def _format_user_msg(purpose: str, tasks: str, base_plan: str) -> str:
    body = tasks.strip() if (tasks and tasks.strip()) else "(none)"
    return (
        f"[Purpose: {purpose}]\n"
        f"[Tasks:\n{body}\n]\n\n"
        f"[Default dedup plan you are refining]\n{base_plan}"
    )


def _compose_plan(base_plan: str, addendum: str) -> str:
    """Append the addendum below the base plan under a clear header."""
    norm = addendum.strip().lower().rstrip(".")
    if not addendum.strip() or norm == "no addendum needed":
        return base_plan
    return (
        f"{base_plan.rstrip()}\n\n"
        f"## Calculation-specific addendum\n\n"
        f"{addendum.strip()}\n"
    )


def build_dedup_plan(
    *,
    purpose: str,
    tasks: str,
    subagent_dir: str | Path | None = None,
    debug: bool = False,
) -> Dict[str, Any]:
    """Generate the calculation-aware dedup plan (base + LLM addendum).

    Returns a dict with:
      ``plan``      — base plan + addendum (the text fed to the dedup
                      subagents),
      ``base_plan`` — the default plan markdown,
      ``addendum``  — the LLM addendum (``""`` on failure),
      ``rationale``, ``error``, ``elapsed_s``, ``iterations``, ``n_tools``.

    On any failure the base plan is returned unchanged so dedup still
    runs with safe defaults.
    """
    if subagent_dir is None or not str(subagent_dir).strip():
        raise ValueError(
            "LC2_3 plan agents require subagent_dir so their complete visible "
            "context can be audited."
        )
    base_plan = load_general_plan()
    slot: Dict[str, Any] = {"payload": None, "error": None}
    tools = _make_decision_tools(slot)
    system_prompt = _DECISION_SYSTEM_PROMPT + "\n\n" + build_tool_instructions(tools)
    user_msg = _format_user_msg(purpose, tasks, base_plan)
    client, hooks = build_client_and_hooks()

    t0 = time.time()
    try:
        result: AgentTurnResult = agent_turn(
            user_msg,
            system_prompt=system_prompt,
            tools=tools,
            memory=[],
            client=client,
            max_iterations=cfg.MAX_TOOL_ITERATIONS,
            timeout=cfg.MAX_TURN_SECONDS,
            required_tools={"finalize_dedup_addendum"},
            hooks=hooks,
            is_subagent=True,
        )
        iterations = result.iterations
        n_tools = len(result.tool_history)
        if subagent_dir:
            write_subagent_context(
                subagent_dir,
                "LC2_3 calculation-aware dedup plan",
                result,
                tool_prefix="lc2_3_dedup_plan",
                stage_id="LC2_3.dedup_plan",
                role="dedup-plan agent",
                phase="planning",
                system_prompt=system_prompt,
                user_message=user_msg,
                tools=tools,
                required_tools={"finalize_dedup_addendum"},
                memory=[],
            )
    except Exception as exc:
        log.error("LC2_3 dedup-decision agent raised: %s", exc, exc_info=debug)
        if subagent_dir:
            write_subagent_context(
                subagent_dir,
                "LC2_3 calculation-aware dedup plan",
                None,
                tool_prefix="lc2_3_dedup_plan",
                stage_id="LC2_3.dedup_plan",
                role="dedup-plan agent",
                phase="planning",
                system_prompt=system_prompt,
                user_message=user_msg,
                tools=tools,
                required_tools={"finalize_dedup_addendum"},
                memory=[],
                error=f"agent_turn_exception: {exc!r}",
            )
        return {
            "plan":       base_plan,
            "base_plan":  base_plan,
            "addendum":   "",
            "rationale":  "",
            "error":      f"agent_turn_exception: {exc!r}",
            "elapsed_s":  round(time.time() - t0, 3),
            "iterations": 0,
            "n_tools":    0,
        }

    payload = slot["payload"] or {}
    addendum = payload.get("addendum", "")
    return {
        "plan":       _compose_plan(base_plan, addendum),
        "base_plan":  base_plan,
        "addendum":   addendum,
        "rationale":  payload.get("rationale", ""),
        "error":      slot["error"],
        "elapsed_s":  round(time.time() - t0, 3),
        "iterations": iterations,
        "n_tools":    n_tools,
    }


__all__ = [
    "build_dedup_plan",
    "load_general_plan",
    "GENERAL_PLAN_PATH",
]
