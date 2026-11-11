# First-principles API-call reconstruction

Run the native agent code with recorded API responses until the first recorded model API authorization denial, then retry that exact request live. The saved request must match the request reconstructed by the code. A changed prompt, tool observation, model setting, missing event or invalid evidence stops reconstruction before a new model request can be sent through a registered transport.

## Modes and breakpoint

- `regular`: start a fresh run and record API exchanges, runtime clocks and registered tool/state checkpoints. An authorization denial stops execution immediately, before it can become an agent's scientific evidence.
- `reconstruction`: start in a separate, empty destination; replay recorded responses and restore completed registered operations. Re-enter an operation interrupted by the denial. Switch to live execution only when the same denied request is reached and all earlier completed events have been consumed.
- `reconstruction_smoke=True`: in reconstruction mode, stop at that boundary with `BreakpointReached`, without sending the denied request.

The boundary is an HTTP 401/403 or the explicit Argo `ACCESS REVOKED` provider notice carried in an HTTP 200 response. The HTTP 200 detector requires the provider notice delimiters and a blocked-response identifier or zero-token usage; ordinary model prose does not qualify. Timeouts, HTTP 413/429/500, ordinary transport errors, unsuccessful chemistry calculations, validation failures and incomplete answers are not authorization boundaries. Supported transport failures replay with their original exception type and message. Missing original failure text is rejected rather than replaced. Without an explicit boundary declaration, a source with no authorization denial is refused.

`AuthorizationInterrupted`, `BreakpointReached` and `ReconstructionMismatch` are control-flow signals derived from `BaseException`. Catch these explicitly at a launcher boundary. Ordinary `except Exception` handlers must not turn them into tool observations or continue sending requests. An interrupted worker also stops its peers from issuing subsequent requests; requests already in flight cannot be undone.

## Native SRD46 Analysis entry point

The domain adapter is `NIST_SRD46_analysis_agent/analysis_reconstruction.py`. The generic engine contains no chemistry logic. Normal Analysis invocations record automatically:

```python
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent import SRD46_analysis_run
from NIST_SRD46_db_agent.general_db_query_engine.general_first_principle_API_call_reconstruct import (
    AuthorizationInterrupted, BreakpointReached,
)

question = "Your original analysis question"
settings = dict(estimate_missing_equilibria=False)

# A regular invocation: retain this folder if authorization is interrupted.
try:
    result = SRD46_analysis_run(question, session_dir="runs/original", **settings)
except AuthorizationInterrupted:
    pass

# A smoke check: only valid if original contains an authorization breakpoint.
try:
    SRD46_analysis_run(
        question, session_dir="runs/reconstruction_smoke",
        reconstruction_mode="reconstruction",
        reconstruction_source="runs/original",
        reconstruction_smoke=True, **settings,
    )
except BreakpointReached:
    print("Exact denied request reached; no live request sent")

# Once access is restored, use another fresh destination to resume live.
result = SRD46_analysis_run(
    question, session_dir="runs/resumed",
    reconstruction_mode="reconstruction",
    reconstruction_source="runs/original", **settings,
)
```

Use identical question, previous context, round number and API settings. Preserve the original framework/configuration and database versions: reconstruction is not a migration between different workflows. Source files are never overwritten. The original run root or its dedicated ledger directory can be supplied as `reconstruction_source`.

Ordinary startup rejects existing Analysis state before creating a ledger or changing output files. Direct L0 and stage-builder entry points enforce the same boundary. Continuing a run requires the native first-principle ledger; reports, summaries and stage journals cannot replace recorded agent execution. The adapter records the fresh initial scientific inputs. It restores completed build/solver results, working memory, pipeline state, history, counters and artifact bytes. Explicit read-only file/inspection tools replay their original observations. The LC1 PubChem enrichment lookup is also a registered operation, outside its process cache, so replay uses the saved result without another external lookup. Its ordinary lookup failures retain their existing behavior. Other native tools execute normally; their resulting context must still match the next recorded API request. An interrupted pipeline re-enters its native body and consumes its recorded child calls. Completed expensive pipeline operations are not rerun. Internal reconstruction records are hidden from model-facing session file tools; they remain available to external audit.

## Execution and time

### Prepared solver continuation in the same session

Analysis also accepts `reconstruction_mode="resume"` with an **explicit original
ledger** containing a verified `planned_stage_boundary.json`. This is a separate
boundary policy; it does not redefine an ordinary API failure as authorization
denial. Supply the saved `analysis_run.json` settings and the existing session
directory. `reconstruction_smoke=True` stops before the saved solver call with
no live API or solver execution.

```python
import json
from pathlib import Path

run = Path("runs/original")
source = run / "run_provenance/first_principle_reconstruction/attempt_0001"
settings = json.loads((source / "analysis_run.json").read_text())["settings"]
result = SRD46_analysis_run(
    session_dir=run,
    reconstruction_mode="resume",
    reconstruction_source=source,
    **settings,
)
```

The native adapter verifies the exact question, L1 brief, saved source blobs and
current solver-card bytes. It replays the original L0/L1 model exchanges and
completed LC1/LC2/LC3 results without rerunning preparation agents. The already
started L0 and L1 keep their recorded system contexts. L0's original question
and initial memory must match its first saved agent entry before its recorded
prompt is restored. Agents first dispatched after the boundary use current
instructions. Full logical API requests must still match.
This mode uses the same strict reconstruction engine, not a report-based restart.
Before creating a new attempt, the adapter rejects changed or extra nonnumerical
files after the selected boundary. Only the selected solver's numerical
checkpoint files may advance. Later sibling reports, working-memory rows and
validation output are never merged into context. Each session selects its own
verified boundary. A missing record or request mismatch stops execution; there
is no regular-mode resume, FIFO response fallback or fresh-reasoning fallback.

### Manually interrupted model request

Analysis accepts an explicitly selected unanswered request through the ordinary
fresh-folder reconstruction path. This does not use the prepared-solver
adapter or replace its boundary policy. Use the original invocation settings
and select the `started` HTTP event in the original `events.jsonl`:

```python
source = run / "run_provenance/first_principle_reconstruction/attempt_0001"
settings = json.loads((source / "analysis_run.json").read_text())["settings"]
boundary = {"kind": "interrupted_http", "event_id": selected_event_id}  # choose the unanswered event from this ledger
try:
    SRD46_analysis_run(
        session_dir="runs/manual_stop_smoke",  # fresh, separate destination
        reconstruction_mode="reconstruction",
        reconstruction_source=source,
        reconstruction_boundary=boundary,
        reconstruction_smoke=True,
        **settings,
    )
except BreakpointReached:
    print("Saved request context matched; no live request sent")
```

For live continuation, use another fresh destination and omit
`reconstruction_smoke=True`. Do not use a smoke run as the new source. The
boundary belongs to execution control, not the scientific question/settings.

The selected request must have no response or committed outcome. Every earlier
response and registered operation must validate and replay. Only that request
and its enclosing operations may be unfinished; another unfinished parallel
branch or a saved response without a receipt is rejected. The model context
must match the recorded request exactly (apart from declared path/account
bindings). Completed build/solver operations restore their recorded results;
the interrupted operation re-enters its native code and replays completed
children. The first live call reissues the unanswered request. It does not
invent, summarize or append an interrupted assistant response. The original
run, including its unanswered request, remains unchanged as provenance.

An in-flight request may have reached the provider before the process stopped;
the absence of a saved response cannot prove that it was not billed. This mode
requires explicit selection and does not automatically retry arbitrary failed
runs. Changed prompts, tools, model settings or unsupported state still stop
reconstruction before new model work. It is not a migration to a different
scientific workflow. Generic interrupted-operation boundaries remain an
engine capability and are not exposed by the Analysis API.

Native pipeline snapshots retain working memory as both a checked value map and
an ordered JSON string, because its key order is visible in the next model
prompt. Reconstruction preserves that original order. Ledgers containing
only the canonicalized map may fail exact context matching after a completed
pipeline; reconstruction does not reorder that evidence to force a match. Use a fresh run when
the required original state was not recorded.

The shared synchronous and asynchronous ReAct loops record agent identities and clock observations. Each agent has its own replay lane; independent lanes can execute in a different scheduling order without consuming each other's responses. Executor dispatch propagates the lane and parent-operation context. Concurrent agents with indistinguishable initial contexts are rejected rather than guessed. One top-level recording/reconstruction session may be active per process; use separate worker processes for separate Analysis sessions.

After the boundary, time resumes from the recorded logical clock plus new elapsed execution time. Waiting for authorization restoration and replay time do not consume the original reasoning budget. Existing exclusions for untimed tools remain in force. Replayed responses do not add model-token usage to the shared billing counter.

Only declared old-root/new-root path substitutions are allowed when matching and delivering saved context. Original source bytes stay unchanged. Artifact files are restored byte-for-byte; their own internal historical path strings remain historical provenance. A tool that tries to use an unsupported stale path will not silently receive invented evidence.

## Ledger

Each Analysis invocation creates:

```text
run_provenance/first_principle_reconstruction/
  latest.json
  attempt_0001/
    analysis_run.json          # native invocation settings and original root
    session.json              # engine schema and replay bindings
    events.jsonl              # operation/API ordering and ancestry
    calls/                    # complete request payload JSON, response text and receipts
    operations/               # JSON results/state and receipts
    artifacts/                # content-addressed workspace/solver file copies
    inherited_provenance/     # flattened original exchanges and checkpoints
    breakpoint.json           # first actual authorization denial, if present
    exit.json
```

Receipts carry hashes and event boundaries. Authorization headers, cookies and API secrets are not recorded. Requests and responses contain the actual model context and should be treated as private run evidence. The source must be trusted; hashes detect accidental changes, not a maliciously rewritten ledger. State is JSON, never executable pickle.

A reconstruction interrupted by another authorization denial creates its own usable ledger, including restored artifact blobs. Original API exchanges inside a reused completed pipeline remain available in `inherited_provenance`, even though that pipeline does not execute again. This archive is content-addressed and flattened across repeated reconstructions; it is audit evidence, not another executable event stream. Use the newer run as the next source. A smoke-only run is a diagnostic, not a new resumable source with an authorization response.

## Coverage limits

Native Analysis reconstruction covers the in-process Argo/ReAct path, registered
Analysis operations, and embedded Query/MCP requests, tool returns and clocks.
MCP helper requests are sent by the parent through the same native transport.
Control messages stay in the root reconstruction ledger and MCP request
metadata; they are not scientific tool arguments or model instructions.

Estimation runs require native Query/MCP replay records and clocks. Older
completed-turn imports are unsupported, even when their saved turn and memory
are complete: they do not reconstruct individual requests through native code.

Other clients or subprocesses need an explicit adapter before claiming
end-to-end reconstruction.

Older `native_api_calls` folders can be read by the generic controller for transport-only replay and authorization-boundary inspection. They lack the new runtime clocks, lane events and state checkpoints. Passing an old run folder to the native reconstruction API is rejected: a separately verified historical context/checkpoint adapter is required. Replaying a list of old HTTP responses alone is not a native-session reconstruction.

## Live Argo account selection

Pass `live_api_user="authorized_account"` to `SRD46_analysis_run` to select
an account for new live Argo calls. Keep the original configured account while
replaying: recorded requests, prompts, model settings, and tool observations
must still match exactly. The override applies only after the native execution
boundary, and does not alter scientific settings or retry/turn budgets.

The native transport records the actual sent payload in `*.request.json`. If
the account differs from the logical request constructed by the agent, it also
records `*.logical_request.json` in the same provenance ledger. Both have
checksummed receipts; reconstruction permits only the `user` field to differ.
These transport records are not model-facing scientific artifacts.

## Live provider selection

`live_provider` selects the transport for new live requests after verified replay, or for a fresh native invocation. Supported direct providers are `anthropic` and `openai`. The logical model alias and saved conversation still have to match during replay; a `model_map` selects its physical provider model.

```python
provider = {
    "provider": "anthropic",
    "model_map": {"claudeopus47": "claude-opus-4-7"},
    "api_key_env": "ANTHROPIC_API_KEY",
}
result = SRD46_analysis_run(
    session_dir="runs/provider_continuation",
    reconstruction_mode="reconstruction",
    reconstruction_source=source,
    reconstruction_boundary=boundary,
    live_provider=provider,
    **settings,
)
```

First verify the selected boundary in a separate smoke destination with `reconstruction_smoke=True`. Smoke replay sends no provider requests. Keep the intact original ledger as the source for live continuation.

Provider configuration supports a custom endpoint, physical model mappings, `request_parameters`, `timeout_override`, response-model aliases and header/environment bindings. Keys are read from the worker environment. The standalone configuration layer validates these options and exposes them through `scripts/run_analysis.py --guide`.

The transport preserves the logical conversation and records both logical and physical requests. With no explicit override, native caller allowances apply to Anthropic, while direct OpenAI uses its separate default total-completion allowance of 32,000 tokens. Reasoning/thinking settings are omitted by default. Explicit provider settings can alter physical token budgets, sampling, reasoning/thinking and HTTP timeout for new live calls; they do not rewrite the replayed context.

Raw and normalized responses are retained in `provider_calls` with integrity receipts. Credentials and authorization headers are excluded. New calls count toward token accounting; replayed calls do not. Provider selection imposes no spending limit and does not change scientific instructions or turn limits.

### Explicit rewind before a completed request

For an authorized rewind, Analysis accepts `reconstruction_mode="reconstruction"` with `reconstruction_boundary={"kind": "restart_before_http", "event_id": ID, "request_sha256": SHA256}` and a fresh output directory. Select the exact original request from the intact native ledger. Every source receipt is verified; only events preceding that request are replayed or restored. Completed ancestor operations spanning the request are re-entered through their native code, and an unfinished sibling crossing the selected boundary is rejected. The old response and later work stay in the original ledger and cannot enter the new context. After replaying the entire prefix, the full reconstructed request must match the recorded request before a live call can occur. `reconstruction_smoke=True` stops there without live work. This is an explicit first-principle reconstruction boundary, never an automatic retry or report-based restart.

Historical LC2 deduplication workers may have complete request/response records but lack parent IDs because their threads did not inherit context variables. When restoring a completed Analysis pipeline snapshot, the adapter binds these workers only by exact saved system prompt, initial user message, and initial memory from that snapshot. Every covered event must be committed and contained within the owning operation; ambiguous identities, events outside the operation, or unexplained remaining events prevent crossover. Covered original event IDs are recorded on the replayed operation receipt. No source receipt or context is rewritten.

## Standalone publication scope

The bundled `scripts/run_analysis.py` and `scripts/run_ff1.py` launch fresh regular runs. Native reconstruction requires direct use of the Analysis API with an intact ledger and an explicitly supported boundary. Anonymized benchmark traces and packed inspection copies must not be used as exact-replay sources: changed historical paths or content cannot satisfy the original receipts.
