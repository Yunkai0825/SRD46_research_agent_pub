"""
ReAct helpers — parameter normalisation, result truncation, dataclasses.
"""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from typing import Callable, Dict

from ..engine_config import get_config

log = logging.getLogger("NISTsrd46-UI")

# Adaptive compaction threshold — when the flat prompt exceeds this
# many chars, trigger the LLM-driven compaction cycle.  This is NOT
# a hard cap; it's a heuristic trigger.  The LLM decides what to
# compress (if anything) via the 3-step select→compress→validate cycle.


def _get_compaction_trigger_chars() -> int:
    """Return the active COMPACTION_TRIGGER_CHARS from agent config."""
    return get_config().COMPACTION_TRIGGER_CHARS


# ═══════════════════════════════════════════════════════════════
#  Parameter alias normalization
# ═══════════════════════════════════════════════════════════════

# Map common LLM mistakes to correct parameter names.
# Keys: (tool_name, wrong_param), Values: correct_param.
# A catch-all key of ("*", wrong_param) applies to all tools.
_PARAM_ALIASES: Dict[tuple[str, str], str] = {
    ("*", "query"):        "question",
    ("*", "compound"):     "compounds",
    ("*", "property"):     "properties",
    ("*", "measurement"):  "measurements",
    ("*", "temp"):         "temp_range",
    ("*", "doi"):          "literature",
}


def _normalize_args(tool_name: str, args: dict, fn: Callable) -> dict:
    """Normalize argument names using alias map + signature matching."""
    sig = inspect.signature(fn)
    valid_params = set(sig.parameters)

    # Accept **kwargs functions as-is
    if any(p.kind == inspect.Parameter.VAR_KEYWORD
           for p in sig.parameters.values()):
        return args

    normalized = {}
    for k, v in args.items():
        # Direct match
        if k in valid_params:
            normalized[k] = v
            continue
        # Tool-specific alias
        alias = _PARAM_ALIASES.get((tool_name, k))
        if alias and alias in valid_params:
            normalized[alias] = v
            continue
        # Catch-all alias
        alias = _PARAM_ALIASES.get(("*", k))
        if alias and alias in valid_params:
            normalized[alias] = v
            continue
        # Case-insensitive fallback
        k_lower = k.lower()
        for p in valid_params:
            if p.lower() == k_lower:
                normalized[p] = v
                break
        # else: silently drop unknown params (LLM hallucination)

    return normalized


_POSITIONAL_KINDS = (
    inspect.Parameter.POSITIONAL_ONLY,
    inspect.Parameter.POSITIONAL_OR_KEYWORD,
)


def _bind_positional_args(tool_calls: list[dict], tools: Dict[str, Callable]) -> None:
    """Bind Python-style positional values to parameter names, in place.

    ``tool_call_parser`` keeps the values of ``name(1, x=2)`` under the
    reserved key ``positional``.  They bind to the tool's positional
    parameters in declaration order, as a Python call would, before batch
    pre-validation sees the call.  A value that cannot bind (unknown tool,
    surplus value, or a name also given as a keyword) is logged loudly and
    left out; the tool then reports its own missing parameters.
    """
    for tc in tool_calls:
        positional = tc.pop("positional", None)
        if not positional:
            continue
        name = tc.get("name", "")
        args = tc.get("arguments")
        if not isinstance(args, dict):
            args = {}
            tc["arguments"] = args
        fn = tools.get(name)
        params: list[str] = []
        if fn is not None:
            try:
                params = [
                    p.name for p in inspect.signature(fn).parameters.values()
                    if p.kind in _POSITIONAL_KINDS
                ]
            except (TypeError, ValueError):
                params = []
        bound: list[str] = []
        unbound = 0
        for param, value in zip(params, positional):
            if param in args:
                unbound += 1
                continue
            args[param] = value
            bound.append(param)
        unbound += max(0, len(positional) - len(params))
        if bound:
            log.info(
                "Tool call %r: bound positional argument(s) to %s",
                name, bound,
            )
        if unbound:
            log.warning(
                "Tool call %r: %d positional argument(s) could not be bound "
                "(%s) and were left out",
                name, unbound,
                "unknown tool" if fn is None else f"parameters {params}",
            )


# ═══════════════════════════════════════════════════════════════
#  Result truncation (head + tail)
# ═══════════════════════════════════════════════════════════════

def truncate_result(text: str) -> str:
    """No-op pass-through (kept for API compatibility).

    Tool results have no hard character cap here. Shaping the result for
    the LLM context is the responsibility of the Layer-1
    deterministic compactors and the Layer-2 KEEP/DISCARD subagent.
    Returning the raw text preserves full evidence for the validator
    and for re-injection.
    """
    return text


# ═══════════════════════════════════════════════════════════════
#  AgentTurnResult dataclass
# ═══════════════════════════════════════════════════════════════

@dataclass
class AgentTurnResult:
    """Result of a single agent_turn() execution."""
    answer: str
    iterations: int
    elapsed_seconds: float
    tool_history: list[dict] = field(default_factory=list)
    timed_out: bool = False
    final_context: str = ""
