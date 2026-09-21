"""Direct adapter over the ordinary SRD-46 query-agent conversation API."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from ..runtime_support.artifacts import read_text
from ..runtime_support.runtime_models import LC13Settings, QueryTurn, normalize_query_turn


def _query_agent_root() -> Path:
    here = Path(__file__).absolute()
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
    """Build the pre-resolved prompt plus one LC1.3 chemistry paragraph."""

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
) -> QueryTurn:
    """Run one pre-resolved pair query with ordinary SRD-46 tools.

    Deterministic pair resolution replaces only compound discovery.  A fresh
    scoped research plan is still mandatory before evidence tools or final
    prose are accepted.  The planner receives host-owned chemistry strategy
    guidance; it cannot replace or reopen the resolved target pair.
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
        require_fresh_plan=True,
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
