"""Small cross-stage runtime records for the direct LC1.3 query flow."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class LC13Settings:
    """Immutable execution bounds for one enabled LC1.3 run.

    Query routing, analogue selection, and retrieval-tool limits deliberately do
    not live here.  The ordinary SRD-46 query agent chooses its own evidence
    search; LC1.3 supplies only model, time, turn, and fail-closed publication
    bounds.
    """

    max_query_runs: int
    query_model: str
    query_max_iterations: int
    query_timeout_s: float
    parser_max_rounds: int
    parser_timeout_s: float
    parser_model: str
    failure_policy: str
    parser_validation_retries: int = 2
    query_clarification_retries: int = 2
    query_clarification_total_timeout_s: float = 600.0

    @classmethod
    def from_config(cls, config: Any) -> "LC13Settings":
        explicit_query_model = str(
            getattr(config, "LC1_3_QUERY_MODEL", "") or ""
        ).strip()
        analysis_model = str(getattr(config, "MODEL", "") or "").strip()
        query_model = explicit_query_model or analysis_model
        if not query_model:
            raise ValueError(
                "LC1.3 requires either LC1_3_QUERY_MODEL or the analysis "
                "agent MODEL to be non-empty"
            )
        values = cls(
            max_query_runs=int(config.LC1_3_MAX_QUERY_RUNS),
            query_model=query_model,
            query_max_iterations=int(config.LC1_3_QUERY_MAX_ITERATIONS),
            query_timeout_s=float(config.LC1_3_QUERY_TIMEOUT_S),
            parser_max_rounds=int(config.LC1_3_PARSER_MAX_ROUNDS),
            parser_timeout_s=float(config.LC1_3_PARSER_TIMEOUT_S),
            parser_model=str(config.LC1_3_PARSER_MODEL or ""),
            failure_policy=str(config.LC1_3_FAILURE_POLICY),
            parser_validation_retries=int(
                getattr(config, "LC1_3_PARSER_VALIDATION_RETRIES", 2)
            ),
            query_clarification_retries=int(
                getattr(config, "LC1_3_QUERY_CLARIFICATION_RETRIES", 2)
            ),
            query_clarification_total_timeout_s=float(
                getattr(
                    config,
                    "LC1_3_QUERY_CLARIFICATION_TOTAL_TIMEOUT_S",
                    600.0,
                )
            ),
        )
        if values.max_query_runs <= 0:
            raise ValueError("LC1_3_MAX_QUERY_RUNS must be positive")
        if values.query_max_iterations <= 0 or values.parser_max_rounds <= 0:
            raise ValueError("LC1_3 agent iteration limits must be positive")
        if values.query_timeout_s <= 0 or values.parser_timeout_s <= 0:
            raise ValueError("LC1_3 timeouts must be positive")
        if values.failure_policy != "reference_only":
            raise ValueError("LC1_3_FAILURE_POLICY must be 'reference_only'")
        if values.parser_validation_retries < 0:
            raise ValueError("LC1_3_PARSER_VALIDATION_RETRIES cannot be negative")
        if values.query_clarification_retries < 0:
            raise ValueError("LC1_3_QUERY_CLARIFICATION_RETRIES cannot be negative")
        if values.query_clarification_total_timeout_s <= 0:
            raise ValueError(
                "LC1_3_QUERY_CLARIFICATION_TOTAL_TIMEOUT_S must be positive"
            )
        return values


@dataclass
class QueryTurn:
    """Normalized result from one turn of the existing SRD-46 query agent."""

    answer: str
    memory: list[dict[str, str]]
    tool_history: list[dict[str, Any]] = field(default_factory=list)
    compactor_events: list[dict[str, Any]] = field(default_factory=list)
    model_history: list[dict[str, Any]] = field(default_factory=list)
    elapsed_s: float = 0.0
    timed_out: bool = False
    error: str | None = None


QueryRunner = Callable[..., QueryTurn]
ParserRunner = Callable[..., Any]


@dataclass
class QuerySession:
    """One fresh, canonical metal-ligand query and its downstream artifacts."""

    query_id: str
    scope: dict[str, Any]
    artifact_dir: Path
    memory: list[dict[str, str]] = field(default_factory=list)
    request_T_C: float | None = None
    request_I_M: float | None = None
    dispatch_turn: QueryTurn | None = None
    followup_turns: list[QueryTurn] = field(default_factory=list)
    evidence_authorization: dict[str, Any] | None = None


def normalize_query_turn(value: Any) -> QueryTurn:
    """Normalize the production query result or a focused test double."""

    if isinstance(value, QueryTurn):
        return value
    if isinstance(value, dict):
        getter = value.get
    else:
        getter = lambda name, default=None: getattr(value, name, default)
    memory = getter("memory", [])
    if not isinstance(memory, list):
        raise TypeError("query-agent result.memory must be a list")
    return QueryTurn(
        answer=str(getter("answer", "") or ""),
        memory=memory,
        tool_history=list(getter("tool_history", []) or []),
        compactor_events=list(getter("compactor_events", []) or []),
        model_history=list(getter("model_history", []) or []),
        elapsed_s=float(
            getter(
                "elapsed_seconds",
                getter("elapsed", getter("elapsed_s", 0.0)),
            )
            or 0.0
        ),
        timed_out=bool(getter("timed_out", False)),
        error=(
            str(getter("error", getter("_error", "")) or "").strip()
            or None
        ),
    )


__all__ = [
    "LC13Settings",
    "ParserRunner",
    "QueryRunner",
    "QuerySession",
    "QueryTurn",
    "normalize_query_turn",
]
