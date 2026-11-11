"""
Argo API configuration — single source of truth for the SRD-46 analysis agent.
==============================================================================
Mirrors :mod:`NIST_SRD46_query_agent.SRD46_query_argo_config` but for the
analysis-side hardcoded pipeline (S1-S8). Step 1 fields feed the shared
``general_db_query_engine``; Step 2 fields are agent-only.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from NIST_SRD46_db_agent.general_db_query_engine.general_argo_engine_helpers.engine_config import EngineConfig


DEFAULT_ANALYSIS_ARGO_API_USER = ""


def _default_api_user() -> str:
    """Return the analysis pipeline's Argo identity.

    The analysis stack owns one account for L0, L1, LD, and all LC agents;
    it must not silently inherit the browser/output-bucket username or a
    generic ``ARGO_API_USER`` left behind by another application.  A
    deployment can still override this pipeline specifically through
    ``SRD46_ANALYSIS_ARGO_API_USER``.

    Mirror the resolved value into ``ARGO_API_USER`` before any optional
    query-agent module is imported.  LC1.3 loads that agent lazily and its
    transport binds the generic environment variable at import time.
    """
    user = os.environ.get(
        "SRD46_ANALYSIS_ARGO_API_USER", DEFAULT_ANALYSIS_ARGO_API_USER
    ).strip()
    if not user:
        user = DEFAULT_ANALYSIS_ARGO_API_USER
    os.environ["ARGO_API_USER"] = user
    return user


@dataclass
class SRD46AnalysisAgentConfig(EngineConfig):
    """Complete configuration for the SRD-46 analysis agent."""

    # ── Step 1: shared engine config ────────────────────────────────
    API_URL: str = field(default_factory=lambda: os.environ.get(
        "ARGO_API_URL", "https://apps-dev.inside.anl.gov/argoapi/api/v1/resource/chat/"))
    API_USER: str = field(default_factory=_default_api_user)
    HEADERS: dict = field(default_factory=lambda: {"Content-Type": "application/json"})

    MODEL: str = "claudeopus47"
    VERDICT_MODEL: str = "claudeopus47"
    PLANNER_MODEL: str = "claudeopus47"

    TEMPERATURE: float = 0.2
    TOP_P: float = 0.9
    MAX_TOKENS: int = 6000
    HTTP_TIMEOUT: int = 600

    # L0 reasoner is checkpoint-only.  This time value drives progressive
    # reminders; the separate turn count is the only ReAct-loop hard bound.
    MAX_TOOL_ITERATIONS: int = 8
    MAX_TURN_SECONDS: int = 600

    # L2 monitors are single-shot.
    # Six turns cover the LD evidence path with room for a second read: list
    # outputs, a compacted parallel read, the cached full results, then the
    # terminal verdict. The time value is a reminder scale, not a deadline.
    L2_MAX_ITERATIONS: int = 6
    L2_MAX_SECONDS: int = 180

    WARN_THRESHOLDS: list[float] = field(default_factory=lambda: [0.65, 0.85, 0.95])
    MAX_WRAP_WARNINGS: int = 3
    MAX_EMPTY_WAITS: int = 3

    TOOL_RESULT_CHAR_LIMIT: int = 24_000
    TOOL_RESULT_HEAD_CHARS: int = 12_000
    TOOL_RESULT_TAIL_CHARS: int = 10_000

    COMPACTION_TRIGGER_CHARS: int = 80_000
    SUMMARY_MAX_CHARS: int = 1000
    GUIDANCE_MAX_TOKENS: int = 150

    VERDICT_TEMPERATURE: float = 0.1
    # A 500-token cap can clip the commit_verdict JSON. Thinking models also
    # spend this cap on hidden reasoning; 1000 can leave no visible text.
    VERDICT_MAX_TOKENS: int = 4000
    COMPACTOR_TEMPERATURE: float = 0.1
    COMPACTOR_MAX_TOKENS: int = 1000
    PLANNER_TEMPERATURE: float = 0.2
    PLANNER_MAX_TOKENS: int = 4000
    PLANNING_MAX_ITERATIONS: int = 3
    PLANNING_MAX_SECONDS: int = 180

    # ── Step 2: agent-specific fields ───────────────────────────────
    L1_MODEL: str = "claudeopus47"
    L2_MODEL: str = "claudeopus47"

    L2_MAX_TOKENS: int = 2000
    REASONING_CAP: int = 10000
    SUBAGENT_MAX_TOKENS: int = 700

    # L1 may need several evidence reads followed by multiple bounded report
    # chunks and one terminal commit. Solver time is credited separately.
    L1_MAX_ITERATIONS: int = 10
    L1_MAX_SECONDS: int = 600
    # The LD agent_turn timeout; 60 s is insufficient for a fresh LD review.
    VERDICT_MAX_SECONDS: int = 180

    # Compaction
    KEEP_RECENT_RESULTS: int = 2
    COMPACTED_MAX_CHARS: int = 500
    MIN_COMPRESS_CHARS: int = 500
    COMPRESS_SHORT_THRESHOLD: int = 1_500
    MAX_RETRY: int = 5
    MAX_IMMEDIATE_RETRY: int = 2
    COMPRESS_MAX_WORDS: int = 500
    COMPRESS_SUMMARY_CHARS: int = 800
    COMPRESS_PREVIEW_CHARS: int = 4_000
    COMPRESS_ORIGINAL_PREVIEW: int = 1_000
    COMPRESS_USER_CONTEXT: int = 500
    COMPACTION_INTERVAL: int = 3
    L1_COMPACTION_INTERVAL: int = 3

    STAGE_COMPACT_BUDGET: int = 4_000
    STAGE_NOTE_CHARS: int = 200
    TRIMMED_PREVIEW_CHARS: int = 800

    VERDICT_MAX_WORDS: int = 150
    SUBAGENT_CHAR_LIMIT: int = 40_000
    BLOCK_CONDENSE_LIMIT: int = 10_000

    # ── Pipeline / LD validator ─────────────────────────────────────
    LD_VALIDATOR_ENABLED: bool = True
    # Uniform per-phase retry budget on LD `contradicted` verdicts.
    PHASE_RETRY_BUDGET: int = 2

    # ── LV validator — review of the L0 final answer ────────────────
    # One agent turn after L0: step 1 flags an answer that is only an
    # intention (``execution_failure``), on which L0 is given the turn
    # back, again and again, until it answers or the bounce pool is spent.
    # Neither the reviews nor the bounce turns are charged to L0's own
    # budget; the bounce turns share a pool of their own, fixed once the
    # main turn ends:  turns = L0's unused turns + L0_BOUNCE_EXTRA_TURNS;
    # reasoning seconds = (L0's unused reasoning time + L0_BOUNCE_EXTRA_SECONDS)
    # × L0_BOUNCE_TIME_FACTOR (pipeline wall time excluded, as in the main
    # turn).  A bounce needs at least one turn and L0_BOUNCE_MIN_SECONDS
    # left in the pool.  Step 2 reviews the synthesis against the L1
    # reports.  Only the conversation tail of LV_CONTEXT_CHARS characters
    # is shown to LV.
    LV_VALIDATOR_ENABLED: bool = True
    L0_BOUNCE_EXTRA_TURNS: int = 5
    L0_BOUNCE_EXTRA_SECONDS: int = 300
    L0_BOUNCE_TIME_FACTOR: float = 2.0
    L0_BOUNCE_MIN_SECONDS: int = 30
    LV_MAX_ITERATIONS: int = 4
    LV_MAX_SECONDS: int = 180
    LV_CONTEXT_CHARS: int = 60_000
    # Write the review's own files (``<session>/LV/agent_response*.md``,
    # ``lv_tool_calls*.md``, ``verdict*.json``).  Off: no LV folder is
    # created; the verdict, hints, waived and enforced checks still reach
    # the manifest phase ``l0_synthesis_review`` and the run history.
    LV_WRITE_ARTIFACTS: bool = False

    # Full LC3 card-building revamps.  This is separate from the local
    # ReAct correction budget inside each L3 agent: a revamp starts again at
    # L3_1 while reusing the already validated LC1/LC2 inputs.  Two revamps
    # permit at most three complete LC3 attempts.
    LC3_MAX_RESTARTS: int = 2

    # Card storage directory (relative to NIST_SRD46_core_calc_tools).
    CARD_STORAGE_SUBDIR: str = "_ref_eq_cards_storage"

    # ── LC1_1 — chemical-system ID alignment sub-agent ─────────────
    # Lightweight LLM agent that resolves free-text metal/ligand mentions
    # in (purpose, tasks) into canonical SRD-46 db_ids. Tools are bounded
    # (search_metal_catalog, search_ligand_catalog, commit_chemical_system).
    LC1_1_MODEL: str = "claudeopus47"
    LC1_1_MAX_TOKENS: int = 3000
    LC1_1_MAX_ITERATIONS: int = 8
    LC1_1_MAX_SECONDS: int = 180

    # ── LC1_2 — Eq-map node validator sub-agent ────────────────────
    # Per-(metal, ligand)-pair LLM curator. The orchestrator builds a
    # draft eq-map + deterministic screen, then — when LC1_2_ENABLED
    # is True — invokes this sub-agent on EVERY pair (no skip route):
    # the agent emits `vlm_overrides` patches (possibly empty) which
    # the patcher applies before card rendering. Set ENABLED=False to
    # skip the LLM step entirely and render the draft as-is.
    LC1_2_ENABLED: bool = True
    LC1_2_MODEL: str = "claudeopus47"
    LC1_2_MAX_TOKENS: int = 3000
    LC1_2_MAX_ITERATIONS: int = 6
    LC1_2_MAX_SECONDS: int = 240

    # Source-backed network repair. All repair agents inherit LC1_2_MODEL.
    # Repair rounds are bounded per affected pair across LC1 and LC2. Review
    # turn and timeout budgets leave room for a terminal decision.
    SOURCE_REPAIR_ENABLED: bool = True
    SOURCE_REPAIR_MAX_ROUNDS: int = 2
    SOURCE_REPAIR_MAX_ITERATIONS: int = 24
    SOURCE_REPAIR_MAX_SECONDS: int = 360
    SOURCE_REPAIR_MAX_TOKENS: int = 6000

    # ── LC1_3 — Query-assisted missing eq-map support ──────────
    # This is a descriptive equilibrium-map enrichment switch. It is
    # unrelated to solver initial-species guesses or concentration pins.
    # Disabled runs use LC1/LC2 without query-assisted enrichment.
    LC1_3_ESTIMATE_EQ_STABILITY_ENABLED: bool = False

    # Deterministic pair-query run bound. Eight covers two Fe oxidation
    # states across DMF, ethylene glycol, methanol, and acetonitrile without
    # silently truncating that enrichment scope.
    LC1_3_MAX_QUERY_RUNS: int = 8

    # Query-estimation and isolated-parser agent budgets.  An empty
    # LC1_3_QUERY_MODEL inherits this analysis agent's MODEL; it must never
    # fall through to the standalone QueryAgent application's model setting.
    # A non-empty LC1_3_QUERY_MODEL remains an explicit per-stage override.
    LC1_3_QUERY_MODEL: str = ""
    LC1_3_QUERY_MAX_ITERATIONS: int = 36
    LC1_3_QUERY_TIMEOUT_S: float = 2000.0
    LC1_3_PARSER_MODEL: str = ""
    # Rounds and timeout leave room for the parser's terminal turn.
    LC1_3_PARSER_MAX_ROUNDS: int = 22
    LC1_3_PARSER_TIMEOUT_S: float = 135.0
    # Parser-output corrections remain inside the isolated parser session; the
    # source chemistry answer is never reformatted by a host-authored retry.
    LC1_3_PARSER_VALIDATION_RETRIES: int = 2
    # Parser cycles the Argo gateway never answered (5xx outage, timeouts,
    # empty envelopes after the client's own retries) are not parser
    # corrections: up to this many in a row, waiting
    # LC1_3_PARSER_TRANSPORT_WAIT_S x streak between them (3 x 60 s rides
    # out a gateway outage of several minutes).
    LC1_3_PARSER_TRANSPORT_RETRIES: int = 3
    LC1_3_PARSER_TRANSPORT_WAIT_S: float = 60.0
    LC1_3_QUERY_CLARIFICATION_RETRIES: int = 2
    LC1_3_QUERY_CLARIFICATION_TOTAL_TIMEOUT_S: float = 3000.0
    # Host continuations when a QueryAgent answer stops at the output cap
    # (Argo usage record, or a high-confidence tail heuristic).  They share
    # the clarification time budget above, never the clarification rounds.
    LC1_3_QUERY_CONTINUATION_RETRIES: int = 2
    # Ceilings that fail closed: at most this many host turns to the
    # QueryAgent per pair (clarifications plus continuations), and none once
    # the assistant-answer transcript the parser reads is this long. A
    # refused continuation is advisory; a refused clarification ends the pair
    # reference_only with the ceiling in the audit. 0 disables a ceiling.
    LC1_3_QUERY_HOST_TURN_CEILING: int = 5
    LC1_3_QUERY_TRANSCRIPT_CHAR_CEILING: int = 60_000
    # Never apply a partial candidate overlay.  LC1_3 first withholds all
    # support when the bounded search is incomplete; the enabled outer LC1
    # gate then fails that build attempt so its ReAct caller can retry instead
    # of silently solving a reduced reference-only system.
    LC1_3_FAILURE_POLICY: str = "reference_only"

    # Preliminary/final union-validator policy knobs.
    LC1_3_REQUIRE_ELEMENT_BALANCE: bool = False
    LC1_3_DUPLICATE_LOGK_TOLERANCE: float = 0.25

    # ── LC2_2 — External-DB card merger (parse + merge, no LLM) ─────
    # LC2_2 consumes ONLY the LC2_1 free_energy_card.md and merges in
    # entries from databases OTHER than SRD-46. It is a pure
    # parse-and-merge stage: no LLM and no deduplication (dedup is the
    # job of LC2_3). Each external-DB pathway is independently
    # toggleable. Defaults: Pourbaix atlas ON, CRC redox OFF. Debug
    # smoke drivers force BOTH on.
    LC2_2_POURBAIX_ENABLED: bool = True
    LC2_2_CRC_REDOX_ENABLED: bool = False
    # When the aqueous self-system species (H⁺ = metal_68, OH⁻ =
    # ligand_10076) are injected upstream (LC1_1 ``water_system``), they
    # are pure references: H⁺ has μ° ≡ 0 (rule R2) and OH⁻ is derived
    # from Kw (rule R3). They therefore do NOT need Pourbaix/CRC redox
    # data merged. When False (default) the water-species elements
    # (H, O) are excluded from the external-DB redox merge; set True to
    # let the merger query the atlas for them as well.
    LC2_2_MERGE_WATER_SPECIES_REDOX: bool = False

    # ── LC2_3 — Element-aware deduplication supervision ───────────
    # Every review turn receives a fresh context. A full re-dedup restores
    # the immutable LC2_2 card/report before dispatching all groups again.
    LC2_3_MAX_FULL_REDEDUP: int = 2
    LC2_3_MAX_REVIEW_TURNS: int = 12


AGENT_CONFIG = SRD46AnalysisAgentConfig()


def resolve_estimate_missing_equilibria(
    override: bool | None = None,
    *,
    config: SRD46AnalysisAgentConfig | None = None,
) -> bool:
    """Resolve the per-run eq-map-estimation gate to one immutable bool.

    ``None`` inherits the shared configuration.  An explicit boolean always
    wins, allowing a caller to disable a globally enabled feature for one run.
    Strict type checking prevents truthy strings or integers from silently
    enabling an LLM/database branch.
    """
    if override is not None:
        if type(override) is not bool:
            raise TypeError("estimate_missing_equilibria must be bool or None")
        return override

    source = AGENT_CONFIG if config is None else config
    configured = source.LC1_3_ESTIMATE_EQ_STABILITY_ENABLED
    if type(configured) is not bool:
        raise TypeError(
            "LC1_3_ESTIMATE_EQ_STABILITY_ENABLED must be configured as bool"
        )
    return configured
