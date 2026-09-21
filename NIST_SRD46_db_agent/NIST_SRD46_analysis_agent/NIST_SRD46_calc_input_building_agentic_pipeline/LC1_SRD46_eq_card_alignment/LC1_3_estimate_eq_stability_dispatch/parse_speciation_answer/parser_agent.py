"""Tool-using parser agent for ordinary QueryAgent chemistry prose."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from NIST_SRD46_db_agent.general_db_query_engine.general_argo_engine_helpers import (
    agent_turn,
)
from NIST_SRD46_db_agent.general_db_query_engine.general_subagent_skill_schema_and_parser.subworkflow_md_tool_descriptions import (
    build_tool_instructions,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.analysis_agent_argo_engine.argo_client import (
    SRD46AnalysisClient,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.analysis_agent_context_hooks import (
    build_agent_hooks as _build_engine_agent_hooks,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.SRD46_calc_input_building_config import (
    AGENT_CONFIG,
)

from ..runtime_support.artifacts import read_text
from ..runtime_support.runtime_models import LC13Settings
from .candidate_schema import ParserAction, ParserCycleResult
from .parser_batch_policy import ParserBatchPolicy
from .parser_gate_service import ParserGateService
from .parser_tools import ParserToolbox
from .source_grounding import is_admissible_query_agent_prose


PARSER_SYSTEM_PROMPT = read_text(
    Path(__file__).with_name("parser_prompt.md"), encoding="utf-8"
).strip()


def run_parser_agent(
    *,
    service: ParserGateService,
    settings: LC13Settings,
    artifact_dir: Path,
    feedback: str | None = None,
) -> ParserCycleResult:
    """Run one fresh parser cycle over the revisioned host workspace."""

    del artifact_dir  # stage orchestrator owns persistence
    if not service.state.answer_turns or any(
        not is_admissible_query_agent_prose(answer)
        for answer in service.state.answer_turns
    ):
        service.record_query_agent_gap(
            code="missing_plain_chemistry_conclusion",
            message="no admissible ordinary chemistry answer is available",
            missing_topics=["plain_chemistry_conclusion"],
        )
        service.state.set_terminal(
            ParserAction.REQUEST_FOLLOWUP,
            "no admissible ordinary chemistry answer is available",
            ["plain_chemistry_conclusion"],
        )
        return ParserCycleResult(
            action=ParserAction.REQUEST_FOLLOWUP,
            reason=service.state.terminal_reason,
            missing_topics=list(service.state.terminal_missing_topics),
        )

    toolbox = ParserToolbox(service)
    tools = toolbox.tools()
    batch_policy = ParserBatchPolicy(service)
    prompt = PARSER_SYSTEM_PROMPT + "\n\n" + build_tool_instructions(tools)
    message = (
        "QueryAgent assistant answers (the only scientific source):\n\n"
        + service.state.transcript
    )
    if feedback:
        message += (
            "\n\nHost parser-cycle feedback (not chemical evidence):\n"
            + str(feedback)
        )
    client = SRD46AnalysisClient(
        model=settings.parser_model or AGENT_CONFIG.LC1_2_MODEL,
        max_tokens=AGENT_CONFIG.LC1_2_MAX_TOKENS,
        _tier="LC1_3-parser-gate",
    )
    engine_agent_hooks = _build_engine_agent_hooks(
        working_memory_loader=lambda: "",
        batch_validator=batch_policy.validate,
        guidance_hooks=[],
    )
    started = time.perf_counter()
    try:
        result: Any = agent_turn(
            message,
            system_prompt=prompt,
            tools=tools,
            memory=[],
            client=client,
            max_iterations=settings.parser_max_rounds,
            timeout=settings.parser_timeout_s,
            required_tools={"finish_parser_cycle"},
            terminal_tools={"finish_parser_cycle"},
            hooks=engine_agent_hooks.engine_hooks,
            is_subagent=True,
            # Parser results are bounded validation records whose exact
            # receipts/errors are required on the next turn. Avoid the shared
            # parallel-stage compactor and its transient inspect-batch tool.
            uncompacted_tools=set(tools),
        )
        if service.state.terminal_action is None:
            service.state.set_terminal(
                ParserAction.PARSER_REVISE,
                "parser ended without a terminal tool commit",
            )
        return ParserCycleResult(
            action=service.state.terminal_action,
            reason=service.state.terminal_reason,
            missing_topics=list(service.state.terminal_missing_topics),
            tool_history=list(result.tool_history or []),
            agent_answer=str(result.answer or ""),
            final_context=str(result.final_context or ""),
            elapsed_s=time.perf_counter() - started,
        )
    except Exception as exc:
        service.state.set_terminal(
            ParserAction.PARSER_REVISE,
            f"{type(exc).__name__}: {exc}",
        )
        return ParserCycleResult(
            action=ParserAction.PARSER_REVISE,
            reason=service.state.terminal_reason,
            elapsed_s=time.perf_counter() - started,
            error=service.state.terminal_reason,
        )


__all__ = ["PARSER_SYSTEM_PROMPT", "run_parser_agent"]
