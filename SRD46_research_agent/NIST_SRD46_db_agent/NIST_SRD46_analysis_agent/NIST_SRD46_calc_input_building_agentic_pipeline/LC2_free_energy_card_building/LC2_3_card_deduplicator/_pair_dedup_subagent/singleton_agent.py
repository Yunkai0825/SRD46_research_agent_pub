"""Singleton-batch deduplication pathway.

A single LLM subagent reviews *all* single-member groups (one species
each) in one shot and decides, per species, whether to keep or drop it
based on L0 purpose / chemical sense.  By construction there is no
within-group duplicate choice — the agent only prunes out-of-scope or
nonsensical singletons.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from ._agent_common import (
    AgentTurnResult,
    agent_turn,
    build_client_and_hooks,
    build_tool_instructions,
    cfg,
    strip_fence,
    write_subagent_context,
)

log = logging.getLogger("Analysis.LC2_3.singleton")


_SINGLETON_SYSTEM_PROMPT = """\
You are the **LC2_3 singleton-batch deduplication subagent**.

You are given a list of single-member groups (one species each, by
core stoichiometry).  By definition there is no within-group duplicate
choice to make. Review them against the supplied element-level chemistry
instructions: keep valid in-scope entries, but an instruction may exclude a
whole alternative solid-model branch even when each member is a singleton.
Never call a distinct mixed-valence phase a duplicate merely because it is
excluded from the selected phase model.

If a CASE-SPECIFIC RECOMMENDATIONS section follows below, the element
supervisor drafted it for THIS calculation; it settles ambiguous criteria
(hydration level, polymorphs, valence coverage, gas admission, scope) and
overrides the general plan's defaults wherever they conflict.

Keep is the default verdict: when nothing is out of scope, keeping every
singleton is the correct outcome — never invent drops to appear useful.

Output contract
---------------
Call `finalize_singleton_decisions` exactly once with:

  {"decisions": [
     {"phase":      "<aqueous|solid|gas>",
      "core_label": "<core_label as given>",
      "keep":       true | false,
      "rationale":  "<one sentence>"},
     ...
  ]}

Every singleton supplied in the user message must appear in the
returned `decisions` array.  After a successful
`finalize_singleton_decisions` you may emit your answer block.
"""


# Auto-filled base note. Calculation-specific element instructions are appended
# because phase-family coherence necessarily spans distinct core groups.
_SINGLETON_NOTE = (
    "Each species is the only member of its core-stoichiometry group after "
    "LC2_2 alignment, so it is not a within-group duplicate. Apply the "
    "element instruction when deciding whether its phase branch is in scope."
)


def _make_singleton_tools(
    slot: Dict[str, Any],
    valid_keys: List[Tuple[str, str]],
) -> Dict[str, Callable]:
    valid_set = set(valid_keys)

    def finalize_singleton_decisions(json_payload: str = "") -> str:
        """Capture keep/drop verdicts for every supplied singleton.

        Schema: {"decisions":[{"phase","core_label","keep","rationale"}]}.
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
        if not isinstance(obj, dict) or not isinstance(obj.get("decisions"), list):
            slot["error"] = "decisions_not_list"
            return "ERROR: payload must be `{'decisions':[...]}`."
        rows = obj["decisions"]
        seen: set = set()
        out: List[Dict[str, Any]] = []
        for r in rows:
            if not isinstance(r, dict):
                slot["error"] = "row_not_object"
                return "ERROR: each decision must be an object."
            try:
                key = (str(r["phase"]), str(r["core_label"]))
                keep = r["keep"]
            except KeyError as exc:
                slot["error"] = f"missing_key: {exc!r}"
                return f"ERROR: missing key {exc!r} in a decision row."
            if type(keep) is not bool:
                slot["error"] = f"keep_not_boolean: {keep!r}"
                return "ERROR: `keep` must be a JSON boolean."
            if key not in valid_set:
                slot["error"] = f"unknown_key: {key}"
                return f"ERROR: ({key}) not in supplied singletons."
            seen.add(key)
            out.append({
                "phase":      key[0],
                "core_label": key[1],
                "keep":       keep,
                "rationale":  str(r.get("rationale", "")).strip(),
            })
        missing = sorted(valid_set - seen)
        if missing:
            slot["error"] = f"missing: {missing}"
            return f"ERROR: missing decisions for {missing}."
        slot["payload"] = out
        slot["error"] = None
        return f"OK — recorded {len(out)} singleton verdicts."

    return {"finalize_singleton_decisions": finalize_singleton_decisions}


def _format_singletons_user_msg(
    singletons: List[Dict[str, Any]],
    plan: str = "",
) -> str:
    rows = [
        "| elements | phase | family | core_label | name | source | charge | mu_aligned_kJ |",
        "|----------|-------|--------|------------|------|--------|-------:|--------------:|",
    ]
    for g in singletons:
        s = g["species"][0]
        rows.append(
            f"| {', '.join(g.get('elements', [])) or '—'} | {g['phase']} "
            f"| {s.get('phase_family', g['phase'])} | `{g['core_label']}` | `{s['name']}` "
            f"| {s['source']} | {s['charge']:+d} | {s['mu_aligned_kJ']:.3f} |"
        )
    instruction_block = (
        f"{_SINGLETON_NOTE}\n\n{plan}" if (plan or "").strip() else _SINGLETON_NOTE
    )
    return (
        f"[Deduplication plan and element instructions]\n{instruction_block}\n\n"
        f"[Singletons: n={len(singletons)}]\n\n" + "\n".join(rows)
    )


def _build_singleton_group_decisions(
    singletons: List[Dict[str, Any]],
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Convert singleton keep/drop rows to source-qualified decisions."""
    decisions: List[Dict[str, Any]] = []
    for row in rows:
        match: Optional[Dict[str, Any]] = next(
            (
                group
                for group in singletons
                if group["phase"] == row["phase"]
                and group["core_label"] == row["core_label"]
            ),
            None,
        )
        if match is None:
            continue
        only = match["species"][0]
        decisions.append({
            "phase": row["phase"],
            "core_label": row["core_label"],
            "keep_species": ([{
                "name": only["name"],
                "source": only["source"],
            }] if row["keep"] else []),
            "rationale": row["rationale"],
        })
    return decisions


def run_singletons_agent(
    *, singletons_payload: str,
    plan: str = "",
    case_recommendations: str = "",
    subagent_dir: str = "",
    debug: bool = False,
) -> Dict[str, Any]:
    """Runner for the batched singleton agent.  Returns a dict with a
    ``decisions`` list (GroupDecision dicts) plus call diagnostics.

    Singletons receive the same element-level instructions as multi-member
    groups so distinct phases such as Fe3O4 participate in coherent branch
    selection even though they are not duplicates.  ``case_recommendations``
    is the supervisor-drafted block appended to this worker's system
    prompt."""
    if not str(subagent_dir or "").strip():
        raise ValueError(
            "LC2_3 singleton agents require subagent_dir so their complete "
            "visible context can be audited."
        )
    singletons = (json.loads(singletons_payload)
                  if isinstance(singletons_payload, str) else singletons_payload)
    valid_keys = [(g["phase"], g["core_label"]) for g in singletons]
    slot: Dict[str, Any] = {"payload": None, "error": None}
    tools = _make_singleton_tools(slot, valid_keys)

    system_prompt = _SINGLETON_SYSTEM_PROMPT
    recommendations = (case_recommendations or "").strip()
    if recommendations:
        system_prompt += (
            "\n\nCASE-SPECIFIC RECOMMENDATIONS (element supervisor)\n"
            "----------------------------------------------------\n"
            f"{recommendations}\n"
        )
    system_prompt += "\n\n" + build_tool_instructions(tools)
    user_msg = _format_singletons_user_msg(singletons, plan)
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
            required_tools={"finalize_singleton_decisions"},
            # Strict gate: singleton verdicts must be committed before prose.
            terminal_tools={"finalize_singleton_decisions"},
            hooks=hooks,
            is_subagent=True,
        )
        iterations = result.iterations
        n_tools = len(result.tool_history)
        if subagent_dir:
            write_subagent_context(
                subagent_dir, "LC2_3 singletons",
                result, tool_prefix="lc2_3_singletons",
                stage_id="LC2_3.singleton_dedup",
                role="singleton-batch dedup agent",
                phase="dedup",
                system_prompt=system_prompt,
                user_message=user_msg,
                tools=tools,
                required_tools={"finalize_singleton_decisions"},
                memory=[],
                metadata={"group_count": len(singletons)},
            )
    except Exception as exc:
        log.error("L2_1_3 singleton agent raised: %s", exc, exc_info=debug)
        if subagent_dir:
            write_subagent_context(
                subagent_dir, "LC2_3 singletons",
                None, tool_prefix="lc2_3_singletons",
                stage_id="LC2_3.singleton_dedup",
                role="singleton-batch dedup agent",
                phase="dedup",
                system_prompt=system_prompt,
                user_message=user_msg,
                tools=tools,
                required_tools={"finalize_singleton_decisions"},
                memory=[],
                error=f"agent_turn_exception: {exc!r}",
                metadata={"group_count": len(singletons)},
            )
        return {
            "decisions":  None,
            "error":      f"agent_turn_exception: {exc!r}",
            "elapsed_s":  round(time.time() - t0, 3),
            "iterations": 0,
            "n_tools":    0,
        }

    rows = slot["payload"] or []
    # Preserve the sole species' full card-editor identity so this
    # pathway uses the same contract as the multi-member pathway.
    decisions = _build_singleton_group_decisions(singletons, rows)
    return {
        "decisions":  decisions,
        "error":      slot["error"],
        "elapsed_s":  round(time.time() - t0, 3),
        "iterations": iterations,
        "n_tools":    n_tools,
    }


__all__ = ["run_singletons_agent"]
