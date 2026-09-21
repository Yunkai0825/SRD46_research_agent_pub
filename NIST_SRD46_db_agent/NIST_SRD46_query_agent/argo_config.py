"""
Argo API configuration — single source of truth.
=================================================
All model names, API settings, and agent hyperparameters are defined
here.  Imported by the agent runtime, server, strategy planner, and
compactor.py.
"""

import os


def _default_api_user() -> str:
    """Read the configured API identity without a personal default."""
    return os.environ.get("ARGO_API_USER", "").strip()


def _parse_tool_name_set(env_name: str, default_csv: str) -> frozenset[str]:
    """Parse a comma-separated tool list from the environment."""
    raw_value = os.environ.get(env_name)
    source = default_csv if raw_value is None else raw_value
    return frozenset(part.strip() for part in source.split(",") if part.strip())


# Expose raw SQL by default. Callers can still opt out by setting
# SRD46_BLOCKED_MCP_TOOLS to include execute_srd46_sql.
MCP_BLOCKED_TOOLS = _parse_tool_name_set(
    "SRD46_BLOCKED_MCP_TOOLS",
    "",
)


def is_mcp_tool_enabled(tool_name: str) -> bool:
    """Return True when the named MCP tool should be exposed."""
    return tool_name not in MCP_BLOCKED_TOOLS

# ── API connection ──────────────────────────────────────────
API_URL       = os.environ.get(
    "ARGO_API_URL",
    "https://apps-dev.inside.anl.gov/argoapi/api/v1/resource/chat/",
)
API_USER      = _default_api_user()
HEADERS       = {"Content-Type": "application/json"}

# ── Model names ─────────────────────────────────────────────
MODEL         = "gpt54"             # main agent runtime + server
VERDICT_MODEL = "gpt54"             # post-job review
PLANNER_MODEL = "gpt54"             # strategy planner + evaluator
ENRICHER_MODEL = "gpt54"            # generic regex_enricher / legacy enrichment
CLAIM_CLASSIFIER_MODEL = "gpt5"             # claim classification
CLAIM_CLASSIFIER_MODEL_FALLBACKS = ("gpt54",)  # backup when primary classifier deployment is unhealthy
CLAIM_CLASSIFIER_REVIEW_ROUNDS = 1   # MCP review/edit rounds after initial classification
GROUNDER_REACT_ROUNDS = 1            # MCP reference-edit rounds after initial grounding
GROUNDER_REACT_MAX_TOOL_ITERATIONS = 4  # max MCP edit turns inside one grounder round
GROUNDER_MODEL = "gpt5"             # claim grounding + validation (needs large context)
GROUNDER_MODEL_FALLBACKS = ("gpt54",)  # backup when primary grounder deployment is unhealthy
CLAIM_PARAGRAPH_WORKERS = 10         # per-answer workers for classify phase, then ground phase
ARGO_MAX_CONCURRENT_REQUESTS = 10     # process-wide cap for concurrent Argo HTTP calls
ARGO_ERROR_BODY_PREVIEW_CHARS = 1000 # max response-body chars to include in 4xx/5xx logs
ARGO_SELF_HARM_FALLBACK_SYSTEM_NOTE = (
    "Safety-context note: The user prompt contains scientific chemistry and database text from "
    "NIST SRD-46 (Critically Selected Stability Constants of Metal Complexes). "
    "The verbatim data block is delimited between the markers "
    "'----- BEGIN SCIENTIFIC DATA -----' and '----- END SCIENTIFIC DATA -----'. "
    "Treat everything between those markers strictly as scientific data for extraction, "
    "classification, and grounding -- never as advice, narration, or discussion of self-harm, "
    "injury, harm to people, hate, violence, or sexual content. Chemistry vocabulary that "
    "may superficially resemble such content (e.g. 'attack', 'decomposition', 'aggressive', "
    "'toxic', 'poisoning', 'lethal', 'inhibition', 'inert', 'labile', 'donor', 'acceptor', "
    "'naked', 'parent/daughter', 'race', 'class', or element/ligand names that look like "
    "unrelated English words) refers exclusively to inorganic coordination chemistry of "
    "metal-ligand complexes. Apply your normal task instructions to that block as-is."
)
ARGO_SELF_HARM_FALLBACK_PROMPT_PREFIX = (
    "[SCIENTIFIC DATA EXTRACT - NIST SRD-46 Critically Selected Stability Constants of Metal Complexes]\n"
    "The block below is verbatim chemistry data (equilibrium constants, ligand names, oxidation states, "
    "coordination geometry, crystal-field theory) intended for automated claim extraction. "
    "All terminology refers to inorganic coordination chemistry of metal-ligand complexes -- "
    "there is no human, social, political, or interpersonal content of any kind. "
    "Words such as 'stable', 'inert', 'labile', 'reduction', 'donor', 'acceptor', 'shell', 'inner/outer', "
    "'attack', 'decomposition', 'aggressive', 'toxic', 'poisoning', 'lethal', 'inhibition', "
    "'naked', 'parent/daughter', 'race', 'class', 'native', 'foreign' are coordination-chemistry "
    "vocabulary, not references to people, groups, hate, violence, sex, or self-harm. "
    "Process the data only as scientific content.\n"
    "----- BEGIN SCIENTIFIC DATA -----\n"
)
ARGO_SELF_HARM_FALLBACK_PROMPT_SUFFIX = (
    "\n----- END SCIENTIFIC DATA -----\n"
    "Return only the requested structured output for the scientific data above."
)
ARGO_MAX_ATTEMPTS = 4                # total Argo call attempts (allows fallback retries)


def is_claude_model(model_name: str) -> bool:
    """Return True for any Claude/Opus model on the Argo proxy.

    Claude models reject payloads containing both *temperature* and
    *top_p*; callers must omit *top_p* when this returns True.
    """
    return "claude" in model_name.lower()


# ── Main agent LLM parameters ──────────────────────────────
TEMPERATURE   = 0.3
TOP_P         = 0.9
MAX_TOKENS    = 6_000                # Argo API hangs/429s at >=8000

# ── Agent loop limits ───────────────────────────────────────
MAX_TOOL_ITERATIONS = 20             # hard cap on tool calls per user turn
MAX_TURN_SECONDS    = 600            # soft time-limit per user turn (seconds)

# ── Pre-plan decision parameters ────────────────────────────
PREPLAN_TEMPERATURE   = 0.1
PREPLAN_MAX_TOKENS    = 500
PREPLAN_TIMEOUT       = 120          # HTTP timeout for pre-plan call (seconds)

# ── Planner / evaluator LLM parameters ─────────────────────
PLANNER_TEMPERATURE   = 0.2
PLANNER_MAX_TOKENS    = 500
PLANNER_TIMEOUT       = 300          # HTTP timeout for planner call (seconds)
EVALUATOR_TEMPERATURE = 0.1
EVALUATOR_MAX_TOKENS  = 500
EVALUATOR_TIMEOUT     = 120          # HTTP timeout for evaluator call (seconds)

# ── Memory compactor parameters ─────────────────────────────
KEEP_RECENT_RESULTS = 2              # most-recent results recommended to keep
REASONING_CAP       = 3_000          # max chars of reasoning prefix kept
MIN_COMPRESS_CHARS  = 500            # results below this are already compact — skip
MAX_RETRY           = 5              # after N rejections, permanently keep original
