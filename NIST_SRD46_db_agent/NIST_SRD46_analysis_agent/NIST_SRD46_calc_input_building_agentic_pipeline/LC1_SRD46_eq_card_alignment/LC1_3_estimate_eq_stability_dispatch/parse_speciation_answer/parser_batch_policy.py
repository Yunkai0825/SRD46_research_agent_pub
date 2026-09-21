"""Pre-execution sequencing policy for the revisioned LC1_3 parser tools.

The general ReAct engine permits several tool calls in one model response.  That
is useful for independent lookups, but parser tools form an ordered transaction:
draft mutation, draft checks, entry gates, the whole-network gate, and terminal
commit.  For a mixed batch this policy retains only the earliest transaction
phase and discards later dependent calls before the engine executes the batch.
"""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from .parser_gate_service import ParserGateService


log = logging.getLogger("NISTsrd46-UI")


_TOOL_PHASE = {
    "inspect_parser_context": (0, "inspect"),
    "inspect_drafts": (0, "inspect"),
    "create_equilibrium_draft": (1, "draft"),
    "update_equilibrium_draft": (1, "draft"),
    "discard_draft": (1, "draft"),
    "check_draft": (2, "check"),
    "run_entry_gate": (3, "entry"),
    "run_network_gate": (4, "network"),
    "annotate_equilibrium_draft": (5, "annotate"),
    "finish_parser_cycle": (6, "finish"),
}

_PHASE_ORDER = (
    "inspect",
    "create/revise",
    "check",
    "entry",
    "network (one call)",
    "annotate (after a passed network gate; one call per draft, batchable)",
    "finish (one call, after a passed current-revision network gate and a "
    "live annotation per draft)",
)


def _blocked_report(names: list[str], reason: str) -> str:
    lines = [
        "LC1_3 parser batch blocked before execution. Parser state is "
        "revisioned, so dependent phases cannot share one tool batch.",
        "Required phase order: " + " -> ".join(_PHASE_ORDER) + ".",
        "Resubmit only the indicated phase, then wait for its result.",
        "",
    ]
    lines.extend(f"**\u2717 {name}** \u2014 {reason}" for name in names)
    return "\n".join(lines)


class ParserBatchPolicy:
    """Validate parser tool batches against transaction-phase boundaries."""

    def __init__(self, service: ParserGateService) -> None:
        self.service = service

    def _current_network_passed(self) -> bool:
        return self.service.network_passed_at_current_revision()

    def validate(
        self,
        tool_calls: list[dict[str, Any]],
        tools: dict[str, Callable[..., Any]],
        *,
        hooks: Any = None,
    ) -> str | None:
        """Return guidance when a parser batch is unsafe to execute.

        The ``tools`` and ``hooks`` parameters intentionally match the general
        analysis-agent batch-validator contract. Unknown tool names remain the
        shared engine's responsibility.
        """

        del tools, hooks
        names = [str(call.get("name") or "") for call in tool_calls]
        known = [
            (index, call, name, *_TOOL_PHASE[name])
            for index, (call, name) in enumerate(zip(tool_calls, names))
            if name in _TOOL_PHASE
        ]
        if not known:
            return None

        earliest_rank = min(rank for _, _, _, rank, _ in known)
        retained_indices = [
            index for index, _, _, rank, _ in known if rank == earliest_rank
        ]
        phase = next(
            phase for _, _, _, rank, phase in known if rank == earliest_rank
        )
        if phase in {"network", "finish"}:
            retained_indices = retained_indices[:1]

        retained_index_set = set(retained_indices)
        retained = [tool_calls[index] for index in retained_indices]
        discarded_names = [
            name for index, name in enumerate(names)
            if index not in retained_index_set
        ]
        if discarded_names:
            retained_names = [str(call.get("name") or "") for call in retained]
            log.info(
                "LC1_3 parser batch truncated to earliest phase %s: kept=%s "
                "discarded=%s",
                phase,
                retained_names,
                discarded_names,
            )
            # The shared engine and its compacted assistant-memory renderer use
            # this list by reference. Thus only calls that will actually run
            # remain visible as executed tool calls.
            tool_calls[:] = retained

        if phase == "finish":
            arguments = tool_calls[0].get("arguments") or {}
            action = str(arguments.get("action") or "").strip()
            if action == "commit":
                if not self._current_network_passed():
                    return _blocked_report(
                        [str(tool_calls[0].get("name") or "finish_parser_cycle")],
                        "commit requires a passed network gate for the current "
                        "workspace revision; run run_network_gate separately "
                        "first",
                    )
                gaps = self.service.annotation_gaps()
                if gaps:
                    listing = ", ".join(
                        f"{gap['draft_id']} ({gap['liveness']})" for gap in gaps
                    )
                    return _blocked_report(
                        [str(tool_calls[0].get("name") or "finish_parser_cycle")],
                        "commit requires a live annotation for every draft; "
                        f"call annotate_equilibrium_draft for: {listing}",
                    )

        return None


__all__ = ["ParserBatchPolicy"]
