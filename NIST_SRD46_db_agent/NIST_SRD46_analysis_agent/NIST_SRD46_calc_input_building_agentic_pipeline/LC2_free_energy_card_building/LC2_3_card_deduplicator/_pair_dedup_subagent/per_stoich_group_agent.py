"""Per-group deduplication pathway.

One LLM subagent decides which species to keep within a *single*
multi-member core-stoichiometry group.  Dispatched in parallel (one
agent per group) by the LC2_3 orchestrator.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Callable, Dict, List

from ._agent_common import (
    AgentTurnResult,
    agent_turn,
    build_client_and_hooks,
    build_tool_instructions,
    cfg,
    strip_fence,
    write_subagent_context,
)

log = logging.getLogger("Analysis.LC2_3.group")


_SRD_DUP_RE = re.compile(r"\[(srd_\d+) (\d+)/(\d+) (frame|data)\]")


_GROUP_SYSTEM_PROMPT = """\
You are the **LC2_3 per-group deduplication subagent**.

You are given ONE core-stoichiometry group of aqueous / solid / gas
species drawn from the merged databases — SRD-46 (NIST critically-
evaluated reference) and the Pourbaix Atlas (auxiliary).  All members
share the same "core" elemental stoichiometry but may still be
different species (different charge, nuclearity, phase, hydration, or
aligned chemical potential `mu_aligned_kJ`).

A group may also contain **SRD-SRD duplicates** flagged upstream by
LC2_1: the same species imported by more than one reference pair card.
Such rows carry a compact `notes` token `[srd_<set> r/n frame|data]`,
an `.dup<r>` id suffix, and a label frame tag (e.g. `[AgOH @25C]` vs
`[AgOH @20C]`).  Rows sharing one `srd_<set>` id form one duplicate
set; the third token tells you how to treat it:

- `frame` — certified twins: identical SRD-46 record, identical data;
  only the temperature frame of the derived chemical potential differs.
  Keep at most one per set — prefer the frame matching the calculation
  temperature (25C unless the plan states otherwise).  A frame choice,
  not a data-quality judgement; `finalize_group_decision` rejects two
  kept copies of one certified set.
- `data` — same formula but different SRD-46 records (e.g. multinuclear
  or cross-table collisions).  Not auto-gated: judge by the normal plan
  rules like any other rows.

This constraint binds ONLY rows of one certified set; every other group
member (Atlas entries, other phases, genuinely different species) is
judged by the normal plan rules.

Your task: decide which source-qualified species in this group to KEEP
after deduplication, following the deduplication plan supplied in the
user message.  A species is identified by its exact `(name, source)`
pair: two rows with the same name but different sources are distinct,
and twin rows are distinct by their frame-tagged names.  Return the
pairs verbatim via `finalize_group_decision`.

If a CASE-SPECIFIC RECOMMENDATIONS section follows below, the element
supervisor drafted it for THIS calculation; it settles ambiguous
criteria (hydration level, polymorphs, valence coverage, gas admission,
scope) and overrides the general plan's defaults wherever they
conflict.

Output contract
---------------
Call `finalize_group_decision` exactly once with:

  {"keep_species": [
     {"name": "<exact species name>", "source": "<exact source>"},
     ...
   ],
   "rationale":  "<one sentence>"}

Every name and source MUST match one row shown in the user message
exactly.  Do not return the deprecated name-only `keep_names` format.
After a successful `finalize_group_decision` you may emit your answer
block.
"""


def _make_group_tools(
    slot: Dict[str, Any],
    valid_species: List[Dict[str, str]],
) -> Dict[str, Callable]:
    valid_set = {(s["name"], s["source"]) for s in valid_species}
    # Certified SRD-SRD frame-twin sets in THIS group, keyed by set id.
    # kind=frame was certified upstream at LC2_1 (single vlm record and
    # log_beta); kind=data sets stay agent-judged.
    twin_meta: Dict[str, Dict[str, set]] = {}
    for s in valid_species:
        m = _SRD_DUP_RE.search(str(s.get("notes", "") or ""))
        if not m:
            continue
        set_id, _rank, _n, kind = m.groups()
        meta = twin_meta.setdefault(set_id, {"pairs": set(), "kinds": set()})
        meta["pairs"].add((s["name"], s["source"]))
        meta["kinds"].add(kind)
    twin_sets: Dict[str, set] = {
        set_id: meta["pairs"] for set_id, meta in twin_meta.items()
        if len(meta["pairs"]) > 1 and meta["kinds"] == {"frame"}
    }

    def finalize_group_decision(json_payload: str = "") -> str:
        """Capture source-qualified kept species for THIS group.

        Schema: {"keep_species": [{"name": str, "source": str}, ...],
        "rationale": str}.  The selected pairs must be a non-empty
        subset of the rows shown in the user message.
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
        keep = obj.get("keep_species")
        if not isinstance(keep, list) or not all(isinstance(x, dict) for x in keep):
            slot["error"] = "keep_species_not_list_object"
            return "ERROR: `keep_species` must be a list of objects."
        if not keep:
            slot["error"] = "keep_species_empty"
            return "ERROR: `keep_species` must not be empty (never drop entire group)."
        pairs = []
        for item in keep:
            name = item.get("name")
            source = item.get("source")
            if not isinstance(name, str) or not isinstance(source, str):
                slot["error"] = "keep_species_missing_name_or_source"
                return (
                    "ERROR: every `keep_species` object requires string "
                    "`name` and `source` fields."
                )
            pairs.append((name, source))
        if len(set(pairs)) != len(pairs):
            slot["error"] = "keep_species_duplicate"
            return "ERROR: `keep_species` contains a duplicate (name, source) pair."
        unknown = [pair for pair in pairs if pair not in valid_set]
        if unknown:
            slot["error"] = f"unknown_species: {unknown}"
            return (f"ERROR: species not in group: {unknown}. "
                    f"Valid: {sorted(valid_set)}.")
        kept = set(pairs)
        for set_id, members in sorted(twin_sets.items()):
            kept_twins = sorted(members & kept)
            if len(kept_twins) > 1:
                slot["error"] = f"twin_set_overkept: {set_id}"
                return (
                    f"ERROR: {len(kept_twins)} rows of the certified "
                    f"SRD-SRD frame twin set `{set_id}` are kept: "
                    f"{kept_twins}. They are one SRD record rendered in "
                    "different temperature frames — keep at most one of "
                    "them (other group members are unaffected)."
                )
        slot["payload"] = {
            "keep_species": [
                {"name": name, "source": source} for name, source in pairs
            ],
            "rationale":  str(obj.get("rationale", "")).strip(),
        }
        slot["error"] = None
        return f"OK — kept {len(keep)} species."

    return {"finalize_group_decision": finalize_group_decision}


def _format_group_user_msg(
    group: Dict[str, Any],
    plan: str = "",
) -> str:
    species_rows = [
        "| entry_key | family | name | source | charge | mu_aligned_kJ | multiplier | notes |",
        "|-----------|--------|------|--------|-------:|--------------:|-----------:|-------|",
    ]
    for s in group["species"]:
        notes = str(s.get("notes", "") or "").replace("|", "/")
        species_rows.append(
            f"| `{s.get('entry_key', '')}` | {s.get('phase_family', group['phase'])} "
            f"| `{s['name']}` | {s['source']} | {s['charge']:+d} "
            f"| {s['mu_aligned_kJ']:.3f} | {s['multiplier']} "
            f"| {notes or '—'} |"
        )
    plan_block = f"[Deduplication plan]\n{plan}\n\n" if (plan or "").strip() else ""
    return (
        f"{plan_block}"
        f"[Group: elements={','.join(group.get('elements', [])) or 'unassigned'} "
        f"phase={group['phase']} core_label={group['core_label']} "
        f"n_species={len(group['species'])}]\n\n"
        + "\n".join(species_rows)
    )


def run_group_agent(
    *, group_payload: str,
    plan: str = "",
    case_recommendations: str = "",
    subagent_dir: str = "",
    debug: bool = False,
) -> Dict[str, Any]:
    """Runner for ONE multi-member group.  Returns a dict with
    ``decision`` (the GroupDecision as dict) plus call diagnostics.

    The agent is guided by ``plan``: the default dedup plan and the routed
    element instruction.  ``case_recommendations`` is the supervisor-drafted
    block appended to this worker's system prompt."""
    if not str(subagent_dir or "").strip():
        raise ValueError(
            "LC2_3 group agents require subagent_dir so their complete "
            "visible context can be audited."
        )
    group = json.loads(group_payload) if isinstance(group_payload, str) else group_payload
    slot: Dict[str, Any] = {"payload": None, "error": None}
    tools = _make_group_tools(slot, group["species"])

    system_prompt = _GROUP_SYSTEM_PROMPT
    recommendations = (case_recommendations or "").strip()
    if recommendations:
        system_prompt += (
            "\n\nCASE-SPECIFIC RECOMMENDATIONS (element supervisor)\n"
            "----------------------------------------------------\n"
            f"{recommendations}\n"
        )
    system_prompt += "\n\n" + build_tool_instructions(tools)
    user_msg = _format_group_user_msg(group, plan)
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
            required_tools={"finalize_group_decision"},
            # Strict gate: a group verdict must be committed before prose.
            terminal_tools={"finalize_group_decision"},
            hooks=hooks,
            is_subagent=True,
        )
        iterations = result.iterations
        n_tools = len(result.tool_history)
        if subagent_dir:
            write_subagent_context(
                subagent_dir,
                f"LC2_3 group [{group['phase']}::{group['core_label']}]",
                result, tool_prefix="lc2_3_group",
                stage_id="LC2_3.group_dedup",
                role="stoichiometric-group dedup agent",
                phase="dedup",
                system_prompt=system_prompt,
                user_message=user_msg,
                tools=tools,
                required_tools={"finalize_group_decision"},
                memory=[],
                metadata={
                    "phase": group["phase"],
                    "core_label": group["core_label"],
                    "elements": group.get("elements", []),
                },
            )
    except Exception as exc:
        log.error("LC2_3 group agent (%s/%s) raised: %s",
                  group["phase"], group["core_label"], exc, exc_info=debug)
        if subagent_dir:
            write_subagent_context(
                subagent_dir,
                f"LC2_3 group [{group['phase']}::{group['core_label']}]",
                None, tool_prefix="lc2_3_group",
                stage_id="LC2_3.group_dedup",
                role="stoichiometric-group dedup agent",
                phase="dedup",
                system_prompt=system_prompt,
                user_message=user_msg,
                tools=tools,
                required_tools={"finalize_group_decision"},
                memory=[],
                error=f"agent_turn_exception: {exc!r}",
                metadata={
                    "phase": group["phase"],
                    "core_label": group["core_label"],
                    "elements": group.get("elements", []),
                },
            )
        return {
            "decision": None,
            "phase":      group["phase"],
            "core_label": group["core_label"],
            "error":      f"agent_turn_exception: {exc!r}",
            "elapsed_s":  round(time.time() - t0, 3),
            "iterations": 0,
            "n_tools":    0,
        }

    payload = slot["payload"]
    err = slot["error"]
    decision = None
    if payload is not None:
        decision = {
            "phase":      group["phase"],
            "core_label": group["core_label"],
            "keep_species": payload["keep_species"],
            "rationale":  payload["rationale"],
        }
    return {
        "decision":   decision,
        "phase":      group["phase"],
        "core_label": group["core_label"],
        "error":      err,
        "elapsed_s":  round(time.time() - t0, 3),
        "iterations": iterations,
        "n_tools":    n_tools,
    }


__all__ = ["run_group_agent"]
