"""Native LC1_2-model tool loop for exact source selection."""
from __future__ import annotations

import json
import time
from copy import deepcopy

from .records import candidate_rows, selected_rows, make_selection, apply_selection, pair_ids, pair_key, digest
from .controller import io_path, write_json, compile_repaired_pairs


def _model_diagnostic(value):
    """Carry scientific issues forward without operator-only execution metadata."""
    if isinstance(value, list):
        return [_model_diagnostic(item) for item in value]
    if not isinstance(value, dict):
        return deepcopy(value)
    if value.get("error_code") == "source_repair_incomplete":
        source = _model_diagnostic(value.get("underlying_source_issue", {}))
        source["previous_review"] = {
            "status": "repair_incomplete", "reason": value.get("reason"),
            "preview_available": bool(value.get("preview_available")),
        }
        for key in ("pair_key", "pair_keys", "issue_key"):
            if key in value:
                source.setdefault(key, deepcopy(value[key]))
        return source
    return {key: _model_diagnostic(item) for key, item in value.items()
            if key not in {"terminal_turns", "max_model_calls"}}


def build_tools(*, card, diagnostic, chemical_system, request_T_C, request_I_M, output_dir):
    """Tool closures are separately testable without any model or network call."""
    key = diagnostic["pair_key"]
    original = next(p for p in card["equilibrium_networks"] if pair_key(p) == key)
    candidates = candidate_rows(*pair_ids(original))
    reaction_groups = {}
    for row in candidates:
        group = reaction_groups.setdefault(int(row["beta_definition_id"]), {
            "beta_definition_id": int(row["beta_definition_id"]), "equation": row.get("equation_python"),
            "network_ids": set(), "source_count": 0})
        group["network_ids"].add(int(row["network_db_id"]))
        group["source_count"] += 1
    groups = [{**g, "network_ids": sorted(g["network_ids"])}
              for _key, g in sorted(reaction_groups.items())]
    state = {"status": None, "card": None, "previews": {}, "events": [], "counter": 0}
    root = io_path(output_dir)
    write_json(root / "all_source_candidates.json", candidates)

    def record(name, arguments, result):
        state["events"].append({"tool": name, "arguments": arguments, "output": result})
        write_json(root / "source_tool_events.json", state["events"])
        text = json.dumps(result, ensure_ascii=False, default=str)
        return "ERROR: " + text if result.get("status") == "invalid" else text

    def list_candidate_reactions(offset: int = 0, limit: int = 10):
        """List all reaction types across networks; follow next_offset until null."""
        offset, limit = max(0, int(offset)), max(1, min(10, int(limit)))
        page = groups[offset:offset + limit]
        state.setdefault("viewed_reactions", set()).update(row["beta_definition_id"] for row in page)
        state["candidates_inspected"] = len(state["viewed_reactions"]) == len(groups)
        return record("list_candidate_reactions", {"offset": offset, "limit": limit},
            {"pair_key": key, "rows": page, "total": len(groups), "offset": offset,
             "next_offset": offset + limit if offset + limit < len(groups) else None,
             "current_vlm_ids": [r["vlm_id"] for r in selected_rows(original, candidates)]})

    def inspect_reaction_sources(beta_definition_id: int, offset: int = 0, limit: int = 20):
        """List VLM IDs, constants and conditions for one reaction, with explicit pagination."""
        offset, limit = max(0, int(offset)), max(1, min(20, int(limit)))
        rows = [r for r in candidates if int(r["beta_definition_id"]) == int(beta_definition_id)]
        fields = ("vlm_id", "network_db_id", "beta_definition_id", "constant_type",
                  "constant_value", "temperature", "ionic_strength", "equation_python")
        return record("inspect_reaction_sources",
            {"beta_definition_id": beta_definition_id, "offset": offset, "limit": limit},
            {"rows": [{k: r.get(k) for k in fields} for r in rows[offset:offset + limit]],
             "total": len(rows), "offset": offset,
             "next_offset": offset + limit if offset + limit < len(rows) else None})

    def inspect_source(vlm_id: int):
        """Read the complete authoritative source row, equation and species mappings for one VLM ID."""
        rows = [r for r in candidates if int(r["vlm_id"]) == int(vlm_id)]
        return record("inspect_source", {"vlm_id": vlm_id}, {"rows": rows})

    def preview_selection(json_payload: str):
        """Compile a complete exact-ID selection without accepting it.

        json_payload: JSON object with vlm_ids (complete retained source rows),
            condition_justification and coverage_justification.
        """
        try:
            payload = json.loads(json_payload)
            if set(payload) - {"vlm_ids", "condition_justification", "coverage_justification"}:
                raise ValueError("Only source IDs and the two justifications may be supplied")
            selection = make_selection(original, **payload, request_T_C=request_T_C,
                                       request_I_M=request_I_M, candidates=candidates)
            revised = deepcopy(card)
            index = next(i for i,p in enumerate(revised["equilibrium_networks"]) if pair_key(p) == key)
            revised["equilibrium_networks"][index] = apply_selection(original, selection)
            state["counter"] += 1
            paths = compile_repaired_pairs(revised, [key], root / f"preview_{state['counter']:02d}",
                                           chemical_system)
            token = digest(revised["equilibrium_networks"][index])
            state["previews"][token] = revised
            result = {"status": "ok", "preview_id": token, "artifacts": paths,
                      "selected_source_rows": selection["source_rows"],
                      "source_conditions": selection["source_conditions"]}
        except Exception as exc:
            result = {"status": "invalid", "error": str(exc),
                      "diagnostic": getattr(exc, "diagnostic", None)}
        return record("preview_selection", {"json_payload": json_payload}, result)

    def commit_selection(preview_id: str):
        """Commit an already successful preview by its exact ID; no new values are accepted."""
        if not state.get("candidates_inspected"):
            return record("commit_selection", {"preview_id": preview_id},
                          {"status": "invalid", "error": "Inspect all candidate reaction types first"})
        revised = state["previews"].get(preview_id)
        if revised is None:
            return record("commit_selection", {"preview_id": preview_id},
                          {"status": "invalid", "error": "A successful preview is required"})
        state.update(status="ok", card=revised)
        return record("commit_selection", {"preview_id": preview_id}, {"status": "ok"})

    def request_human_context(question: str, no_valid_sources: bool = False):
        """Hold this repair with a scientific question (in a batch run no human answers and nothing is solved), or report that no source-backed repair exists."""
        if not question.strip():
            return record("request_human_context", {}, {"status": "invalid", "error": "Question required"})
        state.update(status="no_valid_sources" if no_valid_sources else "needs_human",
                     question=question.strip())
        return record("request_human_context", {"question": question,
                    "no_valid_sources": no_valid_sources}, {"status": state["status"]})

    def reject_selection(reason: str, review_incomplete: bool = False):
        """Reject with a reason; set review_incomplete=true for unfinished review, not missing scientific sources."""
        if not reason.strip() or not isinstance(review_incomplete, bool):
            return record("reject_selection", {}, {"status": "invalid",
                          "error": "A nonempty reason and boolean review_incomplete are required"})
        state.update(status="repair_incomplete" if review_incomplete else "repair_rejected",
                     rejection_reason=reason.strip(), card=None)
        return record("reject_selection", {"reason": reason, "review_incomplete": review_incomplete},
                      {"status": state["status"], "reason": reason.strip()})

    tools = {"list_candidate_reactions": list_candidate_reactions,
             "inspect_reaction_sources": inspect_reaction_sources, "inspect_source": inspect_source,
             "preview_selection": preview_selection, "commit_selection": commit_selection,
             "request_human_context": request_human_context, "reject_selection": reject_selection}
    return tools, state


def run_source_repair(*, card, diagnostic, chemical_system, purpose, tasks,
                      request_T_C, request_I_M, output_dir):
    from NIST_SRD46_db_agent.general_db_query_engine.general_argo_engine_helpers import agent_turn
    from NIST_SRD46_db_agent.general_db_query_engine.general_subagent_skill_schema_and_parser.subworkflow_md_tool_descriptions import build_tool_instructions
    from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.analysis_agent_context_hooks.hook_catalog import build_agent_hooks
    from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.analysis_agent_argo_engine.argo_client import SRD46AnalysisClient
    from SRD46_calc_input_building_config import AGENT_CONFIG as cfg
    root = io_path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    tools, state = build_tools(card=card, diagnostic=diagnostic, chemical_system=chemical_system,
        request_T_C=request_T_C, request_I_M=request_I_M, output_dir=root)
    limits = {
        "max_iterations": int(getattr(cfg, "SOURCE_REPAIR_MAX_ITERATIONS", 16)),
        "max_seconds": int(getattr(cfg, "SOURCE_REPAIR_MAX_SECONDS", 240)),
        "max_tokens": int(getattr(cfg, "SOURCE_REPAIR_MAX_TOKENS", 6000)),
    }
    system = io_path(__file__).with_name("WORKFLOW.md").read_text(encoding="utf-8")
    system += "\n\n" + build_tool_instructions(tools)
    user = json.dumps({"purpose": purpose, "tasks": tasks, "chemical_system": chemical_system,
        "request_T_C": request_T_C, "request_I_M": request_I_M, "diagnostic": _model_diagnostic(diagnostic),
        "execution_limits": limits,
        "selected_pair": next(p for p in card["equilibrium_networks"]
                              if pair_key(p) == diagnostic["pair_key"])}, indent=2, default=str)
    (root / "system_prompt.md").write_text(system, encoding="utf-8")
    (root / "user_message.json").write_text(user, encoding="utf-8")
    write_json(root / "input_card.json", card)
    write_json(root / "input_diagnostic.json", diagnostic)
    client = SRD46AnalysisClient.for_lc1_2()
    client.max_tokens = limits["max_tokens"]
    client._tier = "LC1-source-repair"
    write_json(root / "settings.json", {"model": client.model, **limits,
        "terminal_turns": 1, "max_model_calls": limits["max_iterations"] + 1})
    start = time.monotonic()
    error = None
    execution = {}
    try:
        result = agent_turn(user, system_prompt=system, tools=tools, memory=[], client=client,
            max_iterations=limits["max_iterations"],
            timeout=limits["max_seconds"],
            required_tools={"list_candidate_reactions"},
            terminal_tools={"commit_selection", "request_human_context", "reject_selection"},
            terminal_turn_budget=True,
            hooks=build_agent_hooks(working_memory_loader=lambda: "", guidance_hooks=[]).engine_hooks,
            is_subagent=True)
        write_json(root / "native_tool_history.json", result.tool_history)
        execution = {"timed_out": getattr(result, "timed_out", None),
                     "iterations": getattr(result, "iterations", None)}
        (root / "agent_response.md").write_text(
            f"# Final answer\n\n{result.answer}\n\n# Complete context\n\n{result.final_context}",
            encoding="utf-8")
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    # Only a successful terminal tool selects a card or asks a human question.
    # A compiled preview is evidence of available work, never an implicit commit.
    incomplete = None
    if state["status"] is None or state["status"] == "repair_incomplete":
        if error:
            reason = "agent_execution_error"
        elif state.get("rejection_reason"):
            reason = "review_incomplete"
        elif (execution.get("iterations") or 0) >= limits["max_iterations"]:
            reason = "iteration_budget_exhausted"
        elif execution.get("timed_out"):
            reason = "native_time_budget_exhausted"
        else:
            reason = "no_terminal_decision"
        message = (
            f"Source repair for {diagnostic['pair_key']} ended without a terminal "
            f"selection or human question: {reason}; "
            f"model_turns={execution.get('iterations')}, review_limit={limits['max_iterations']}, "
            f"preview_available={bool(state['previews'])}. "
            "No preview was committed or accepted."
        )
        incomplete = {
            "error_code": "source_repair_incomplete", "repair_scope": "source_selection",
            "pair_key": diagnostic["pair_key"], "pair_keys": [diagnostic["pair_key"]],
            "issue_key": diagnostic.get("issue_key", diagnostic["pair_key"]),
            "failure_stage": "LC1.source_repair", "reason": reason, "message": message,
            "preview_available": bool(state["previews"]),
            "preview_ids": sorted(state["previews"]),
            "limits": {**limits, "terminal_turns": 1, "max_model_calls": limits["max_iterations"] + 1},
            "execution": {**execution, "error": error},
            "underlying_source_issue": deepcopy(diagnostic),
        }
        if state.get("rejection_reason"):
            incomplete["rejection_reason"] = state["rejection_reason"]
    output = {"status": state["status"] or "repair_incomplete", "card": state["card"],
              "question": state.get("question"), "error": error,
              "elapsed_s": time.monotonic() - start, "output_dir": str(root),
              "limits": limits, **execution}
    if incomplete:
        output.update(diagnostic=incomplete, _error=incomplete["message"])
    elif state.get("rejection_reason"):
        output.update(
            _error=state["rejection_reason"],
            diagnostic={**deepcopy(diagnostic), "repair_status": "repair_rejected",
                        "message": state["rejection_reason"], "rejection_reason": state["rejection_reason"]},
        )
    write_json(root / "repair_result.json", output)
    return output
