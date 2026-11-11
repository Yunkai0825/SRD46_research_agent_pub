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
    # Parser cycles the Argo gateway never answered (outage, timeouts: the
    # client's own retries exhausted).  They do not spend a correction retry;
    # the host waits ``parser_transport_wait_s`` × streak between them and
    # fails the pair closed after ``parser_transport_retries`` in a row.
    parser_transport_retries: int = 3
    parser_transport_wait_s: float = 60.0
    query_clarification_retries: int = 2
    query_clarification_total_timeout_s: float = 600.0
    # Host continuations of an answer that stopped at the QueryAgent output
    # cap.  They share the clarification time budget above but never count
    # as chemistry clarification rounds.
    query_continuation_retries: int = 2
    # Ceilings that fail closed. Host turns are clarifications plus
    # continuations together; the transcript ceiling is the size in
    # characters of the assistant answers the parser reads. The host checks
    # both before every turn it would send: a refused continuation is
    # advisory, a refused clarification ends the pair reference_only with
    # the ceiling recorded. 0 disables a ceiling.
    query_host_turn_ceiling: int = 5
    query_transcript_char_ceiling: int = 60_000

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
            parser_transport_retries=int(
                getattr(config, "LC1_3_PARSER_TRANSPORT_RETRIES", 3)
            ),
            parser_transport_wait_s=float(
                getattr(config, "LC1_3_PARSER_TRANSPORT_WAIT_S", 60.0)
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
            query_continuation_retries=int(
                getattr(config, "LC1_3_QUERY_CONTINUATION_RETRIES", 2)
            ),
            query_host_turn_ceiling=int(
                getattr(config, "LC1_3_QUERY_HOST_TURN_CEILING", 5)
            ),
            query_transcript_char_ceiling=int(
                getattr(config, "LC1_3_QUERY_TRANSCRIPT_CHAR_CEILING", 60_000)
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
        if values.parser_transport_retries < 0:
            raise ValueError("LC1_3_PARSER_TRANSPORT_RETRIES cannot be negative")
        if values.parser_transport_wait_s < 0:
            raise ValueError("LC1_3_PARSER_TRANSPORT_WAIT_S cannot be negative")
        if values.query_clarification_retries < 0:
            raise ValueError("LC1_3_QUERY_CLARIFICATION_RETRIES cannot be negative")
        if values.query_clarification_total_timeout_s <= 0:
            raise ValueError(
                "LC1_3_QUERY_CLARIFICATION_TOTAL_TIMEOUT_S must be positive"
            )
        if values.query_continuation_retries < 0:
            raise ValueError("LC1_3_QUERY_CONTINUATION_RETRIES cannot be negative")
        if values.query_host_turn_ceiling < 0:
            raise ValueError("LC1_3_QUERY_HOST_TURN_CEILING cannot be negative")
        if values.query_transcript_char_ceiling < 0:
            raise ValueError("LC1_3_QUERY_TRANSCRIPT_CHAR_CEILING cannot be negative")
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
    # Usage and stop reason of the model round that produced ``answer``
    # (``argo_client`` records them per round); ``output_truncated`` True
    # means the answer stopped at the output cap.  None when unknown.
    output_budget: dict[str, Any] | None = None


_OUTPUT_BUDGET_KEYS = (
    "max_tokens", "prompt_tokens", "completion_tokens", "finish_reason",
    "output_truncated", "output_chars",
)


def answer_output_budget(
    explicit: Any, model_history: list[Any], answer: str,
) -> dict[str, Any] | None:
    """The final answer's output budget.

    An explicit record wins.  Otherwise the model round whose response is the
    answer text supplies it (falling back to the last round with a response),
    so a final answer cut at ``max_tokens`` is visible without touching the
    agent's result type.
    """

    if isinstance(explicit, dict):
        return dict(explicit)
    wanted = str(answer or "").strip()
    chosen: dict[str, Any] | None = None
    chosen_round: int | None = None
    fallback: tuple[int, dict[str, Any]] | None = None
    for index in range(len(model_history) - 1, -1, -1):
        record = model_history[index]
        if not isinstance(record, dict) or not isinstance(record.get("response"), str):
            continue
        if fallback is None:
            fallback = (index, record)
        if wanted and record["response"].strip() == wanted:
            chosen, chosen_round = record, index
            break
    matched = chosen is not None
    if chosen is None and fallback is not None:
        chosen_round, chosen = fallback
    if chosen is None:
        return None
    budget = chosen.get("output_budget")
    if not isinstance(budget, dict):
        return None
    summary = {key: budget.get(key) for key in _OUTPUT_BUDGET_KEYS}
    summary["source"] = "argo_usage"
    summary["model_round"] = int(chosen_round) + 1
    summary["answer_round_matched"] = matched
    return summary


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
    # The host's reporting turn (the second turn of the conversation, after
    # the free exploration answer): the accepted turn and the sha256 of its
    # prompt.  None when the turn was not run or was not accepted; the parser
    # then reads the exploration answer alone.
    reporting_turn: QueryTurn | None = None
    reporting_prompt_sha256: str | None = None


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
    answer = str(getter("answer", "") or "")
    model_history = list(getter("model_history", []) or [])
    return QueryTurn(
        answer=answer,
        memory=memory,
        tool_history=list(getter("tool_history", []) or []),
        compactor_events=list(getter("compactor_events", []) or []),
        model_history=model_history,
        output_budget=answer_output_budget(
            getter("output_budget", None), model_history, answer,
        ),
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
    "answer_output_budget",
    "QuerySession",
    "QueryTurn",
    "normalize_query_turn",
]
