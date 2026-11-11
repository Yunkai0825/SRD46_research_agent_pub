# Source-backed LC1 validation and repair

The normal LC1 flow compiles the selected measured-source networks before
the node reviewer runs, then checks source provenance and compiles again after
that review. Compilation uses the same component, species-dependency and
free-energy builders as LC2. A missing formation anchor therefore fails here
before an incomplete card reaches deduplication or the solver.

The repair agent uses the configured LC1_2 model. It can inspect all reaction
types and source networks for the affected catalog pair, select exact existing
VLM rows, preview the native compiler, commit a successful preview, or return
a question. It cannot edit constants, equations, source conditions or chemical
identities. Its system instructions are in WORKFLOW.md; the rendered system
prompt, user message, effective settings, full candidate snapshot, tool events,
native tool history and final context are saved in each attempt folder.
The complete input diagnostic is retained separately from the reviewer-facing
message. A prior incomplete attempt contributes its source issue and failure
reason, while operator-only terminal-turn metadata stays out of that message.

Source selections retain complete database rows, a canonical row digest,
actual source T/I and written condition/coverage reasoning. Selecting a
sibling row carries that sibling's own metadata. Copying a sibling's number
onto the old row through a legacy set_value patch is rejected by the post
gate. Useful protonation-chain coverage is considered explicitly when adding
an anchor; compiler success alone does not establish scientific adequacy.

The configured defaults are two repair attempts per affected catalog pair,
twenty-four review turns, a 360-second native timeout setting and 6000 output
tokens.
The final five review prompts display their current turn as i/24
(20/24 through 24/24; all turns when the configured limit is at most five).
Operator settings also
record one additional terminal-only turn; its availability is not disclosed
to the reviewer until it arrives. That turn can commit an already compiled
preview, explicitly reject with a reason, or ask a genuine scientific question.
It cannot search or compile new evidence. The opt-in engine stops immediately
after a valid terminal decision and makes at most twenty-five model calls,
without a separate model summary or context-compaction call.
The timeout follows the existing agent engine's reminder/deadline semantics;
the result also records iterations and timed_out. No separate model role or
fallback is introduced. Source ambiguities return needs_human or
no_valid_sources and do not become an accepted LC1 result. An execution that
ends without a terminal decision returns repair_incomplete, with the reason,
limits, execution flags, available preview IDs and underlying source issue.
It does not invent a human question or accept a preview. A validated terminal
commit remains accepted if the native result also carries a timeout flag;
the terminal-turn mode makes no final narration call. The controller carries the execution cause and actual
per-pair attempt counts through LC1 to its caller.

ensure_validated_selection binds its durable receipt to the input card,
chemical catalog, scientific brief, requested conditions, supplied diagnostic,
workflow and implementation hashes. Every invocation gets a fresh directory.
The budget is reserved before dispatch, and checkpoints preserve candidate
selections and seen scientific signatures. A compatible saved candidate is
compiled again before reuse. Repeated proposals cannot obtain another attempt
by changing only their explanation. Corrupt receipts fail closed. A process
killed while holding validation.lock leaves the lock for explicit recovery;
ordinary exceptions release it while preserving the reserved attempt.

Public interfaces:

- ensure_validated_selection(...): validated card, report, diagnostic and
  cumulative source_repair_attempts_by_issue.
- repair_lc1_selection(previous_lc1=..., diagnostic=..., ...): the same scoped
  repair applied to a saved LC1 result. The original system catalog is retained
  unchanged and the revised card is written under the new attempt.
- compile_repaired_pairs(card, pair_keys, output_dir,
  chemical_system=None): deterministic pair cards, including authoritative
  selected H/ligand and metal/OH prerequisites. Pass chemical_system to retain
  catalog-owned ligand basis contracts.

Exact selections are propagated through the LC1 node screen and native
LC2 maps/equation builder. The source selection digest is included in the
reference-card filename; old network-only caches are bypassed for these
selections.
