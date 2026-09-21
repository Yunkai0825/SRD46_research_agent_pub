# LC1.3 missing-stability estimation

LC1.3 is a direct, opt-in estimation path. It no longer has a separate
“determine estimation needed” agent, analogue router, functional-group map,
pair-specific tool allowlist, custom planner, or answer-reorganization loop.

## Runtime flow

1. `dispatch_srd46_query/pair_scopes.py` deterministically canonicalizes the non-water metal and
   ligand IDs already declared by the chemical-system card and creates every
   metal–ligand pair once. Existing equilibrium-map rows are recorded as audit
   context; their presence does not suppress a query because a map may be
   incomplete.
2. `dispatch_srd46_query/` starts one fresh QueryAgent conversation for each
   pair. Its first user message is the ordinary chemistry question in
   `dispatch_query_prompt.md`; it receives no response schema, parser contract,
   or host-selected retrieval route. The first answer is retained unchanged.
3. `dispatch_srd46_query/evidence_receipts.py` records which canonical SRD-46 IDs actually appeared
   in successful tool results. These are post-hoc integrity receipts, not
   authorization decisions and not evidence-quality classifications. The
   current handoff is v3-only; obsolete v1/v2 policy artifacts are rejected.
4. `parse_speciation_answer/` is a revisioned, tool-driven parser workspace.
   The parser creates partial equilibrium drafts from exact answer excerpts;
   host code supplies canonical identities and topology. Entry and prospective
   network gates classify omissions by owner and prevent partial drafts from
   reaching the assembler.
5. If the QueryAgent clearly estimated a value but omitted chemistry needed to
   materialize it, `dispatch_srd46_query/query_clarification_coordinator.py`
   sends a narrow follow-up
   in that same conversation. The follow-up asks only for the missing chemistry
   and does not expose a schema or ask the QueryAgent to rewrite its answer.
   Only topics authorized by a deterministic QueryAgent-owned gate may trigger
   that call. The authorization is bound to the unchanged QueryAgent answer
   and evidence snapshot, so parser-only draft cleanup cannot erase it; a new
   QueryAgent answer invalidates it. Parser correction and QueryAgent
   clarification each
   have independent bounds; an empty, errored, timed-out, late, or
   memory-replacing clarification fails closed without publication.
6. `validate_support_eq_map/` independently revalidates identities, numeric
   source bindings, receipt lineage, native topology, and the session working
   map before publication. Any unresolved pair or invalid materialization fails
   closed to the reference-only path.

The LC1.3 QueryAgent uses the standard SRD-46 tool catalog and tool-call syntax.
Its preplanning/discovery workflow is removed from the LC1.3 prompt because the
pair IDs are already canonical and the runtime is explicitly pre-resolved. The
LC1.3 chemistry context in
`dispatch_srd46_query/query_estimation_system_prompt.md` permits a clearly
labelled chemistry-informed estimate while preserving retrieved values
verbatim. It contains no parser schema or machine-output requirement.

## Active modules

```text
LC1_3_estimate_eq_stability_dispatch/
  __init__.py                         # stable package API
  LC1_3_estimate_eq_stability_dispatch_orchestrator.py
  README.md
  dispatch_srd46_query/               # pair scope, prompts, query runtime,
                                      # receipts, and clarification
  parse_speciation_answer/            # parser workspace and deterministic gates
  runtime_support/                    # shared models and artifact I/O
  validate_support_eq_map/            # final support-map assembly and validation
  tests/                               # LC1.3 unit and end-to-end contracts
```

The LC1.3 root intentionally contains only its stable package entry point,
public orchestrator, and documentation. The removed
`determine_estimation_needed/` directory, dead field-extraction parser, and
compiled caches must not be restored. Estimation need is expressed by enabling
LC1.3 upstream; LC1.3 itself does not run a second agent to reinterpret that
decision.
