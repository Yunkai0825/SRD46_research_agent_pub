"""Direct adapter over the ordinary SRD-46 query-agent conversation API."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from ..runtime_support.artifacts import read_text
from ..runtime_support.runtime_models import LC13Settings, QueryTurn, normalize_query_turn


def _query_agent_root() -> Path:
    here = Path(__file__).resolve()
    db_agent = next(
        parent for parent in here.parents
        if parent.name == "NIST_SRD46_db_agent"
    )
    return db_agent / "NIST_SRD46_query_agent"


def render_query_estimation_mode_prompt() -> str:
    """Return the sole LC1.3-specific system-prompt paragraph."""

    return read_text(
        Path(__file__).with_name("query_estimation_system_prompt.md"),
        encoding="utf-8",
    ).strip()


def render_query_estimation_planner_prompt() -> str:
    """Return host-owned guidance for the scoped analogue-search planner."""

    return read_text(
        Path(__file__).with_name("query_estimation_planner_prompt.md"),
        encoding="utf-8",
    ).strip()


def get_query_agent_system_prompt(
    settings: LC13Settings | None = None,
) -> str:
    """Build the exploration-turn system prompt.

    The standalone QueryAgent prompt (tool catalog, call syntax, global rules)
    without its MANDATORY WORKFLOW section and memory-compression note, two
    rules reworded so a clearly labelled estimate is allowed, plus the LC1.3
    chemistry paragraph.  Chemistry only: no reporting format and no parser
    requirement reaches the exploration turn; those are follow-up prompts.
    """

    del settings
    root = _query_agent_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from NIST_SRD46_db_agent.NIST_SRD46_query_agent.agent_runtime import (  # noqa: PLC0415
        SYSTEM_PROMPT,
    )

    prompt = str(SYSTEM_PROMPT)
    prompt = prompt.replace(
        "Never invent numeric values; all factual claims must come from tool "
        "results.",
        "Retrieved numeric values must be reproduced faithfully; clearly label "
        "new chemistry-informed values as estimates.",
    )
    prompt = prompt.replace(
        "Final numeric values are regex-validated against raw tool results. "
        "Quote exact rows/values from tool output; if a value is uncertain, do "
        "a narrower follow-up search instead of approximating.",
        "Quote retrieved numeric values exactly and clearly label any new "
        "chemistry-informed estimate as an estimate.",
    )
    prompt = prompt.replace(
        "MEMORY COMPRESSION:\nOlder tool results are automatically compacted "
        "between iterations to keep context bounded. You will be consulted on "
        "which results to compress and asked to validate summaries.\n\n",
        "",
    )
    prompt = prompt.split("\nMANDATORY WORKFLOW:\n", 1)[0].rstrip()
    return prompt + "\n\n" + render_query_estimation_mode_prompt()


def run_query_agent(
    user_message: str,
    *,
    memory: list[dict[str, str]] | None = None,
    timeout: float,
    max_tool_iterations: int,
    model: str | None = None,
    system_prompt_override: str | None = None,
    fresh_plan: bool = True,
) -> QueryTurn:
    """Run one turn of a pair's conversation with the full SRD-46 tool catalog.

    The host-resolved metal and ligand ids name only the estimation target;
    the embedded QueryAgent explores SRD-46 freely with every tool (discovery,
    planning and evidence tools) and no call is refused before it answers.
    On the first turn the runtime still expects one successful
    ``0_plan_search_strategy`` before it accepts a final answer; the planner
    receives host-owned chemistry strategy guidance and cannot reopen the
    target pair.  ``fresh_plan=False`` is for the host's later turns in the
    same conversation (the reporting turn, clarifications, continuations):
    the plan and evidence already stand in memory, so the runtime accepts an
    addendum without a new plan call.
    """

    root = _query_agent_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from NIST_SRD46_db_agent.NIST_SRD46_query_agent.query_agent import (  # noqa: PLC0415
        run_agent_query_sync,
    )

    supplied_memory = [] if memory is None else memory
    raw: Any = run_agent_query_sync(
        user_message,
        memory=supplied_memory,
        timeout=int(timeout),
        max_tool_iterations=int(max_tool_iterations),
        system_prompt_override=(
            get_query_agent_system_prompt()
            if system_prompt_override is None
            else system_prompt_override
        ),
        planner_system_prompt_module=render_query_estimation_planner_prompt(),
        pre_resolved_workflow=True,
        require_fresh_plan=bool(fresh_plan),
        enable_memory_compaction=False,
        model_override=model or None,
    )
    result = normalize_query_turn(raw)
    if result.memory is not supplied_memory:
        raise RuntimeError(
            "SRD-46 query agent replaced the caller-owned conversation memory"
        )
    return result


__all__ = [
    "get_query_agent_system_prompt",
    "render_query_estimation_mode_prompt",
    "render_query_estimation_planner_prompt",
    "run_query_agent",
]
