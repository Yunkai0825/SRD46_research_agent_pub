# LC1.3 missing-stability estimation

LC1.3 queries missing-equilibrium evidence and materializes validated estimates when estimation is enabled.

## Runtime flow

1. `dispatch_srd46_query/pair_scopes.py` deterministically canonicalizes the non-water metal and
   ligand IDs already declared by the chemical-system card and creates every
   metal–ligand pair once. Existing equilibrium-map rows are recorded as audit
   context; their presence does not suppress a query because a map may be
   incomplete.
2. `dispatch_srd46_query/` starts one fresh QueryAgent conversation for each
   pair. Its first user message is the ordinary chemistry question in
   `dispatch_query_prompt.md`; it receives no response schema, parser contract,
   reporting format, or host-selected retrieval route. This exploration turn
   is chemistry only, and the QueryAgent keeps the full SRD-46 tool catalog
   (discovery, planning and evidence tools; no call is refused before it
   answers). The first answer is retained unchanged.
3. `dispatch_srd46_query/reporting_followup_orchestrator.py` then sends one
   reporting prompt (`reporting_followup_prompt.md`) in that same
   conversation through the follow-up runner: restate each estimate in a
   structured form (metal and ligand ids, the species as `beta_definition_id`
   with name and equation, conditions, uncertainty, step-by-step provenance
   with fully prefixed identifiers). The accepted report follows the
   exploration answer in the parser transcript, where a later statement of
   an equilibrium governs. A failed reporting turn is advisory: the parser
   then reads the exploration answer alone.
4. `dispatch_srd46_query/evidence_receipts.py` records which canonical SRD-46 IDs actually appeared
   in successful tool results. These are post-hoc integrity receipts, not
   authorization decisions and not evidence-quality classifications. The
   current handoff is v3-only; obsolete v1/v2 policy artifacts are rejected.
5. `parse_speciation_answer/` is a revisioned, tool-driven parser workspace.
   The parser creates partial equilibrium drafts from exact answer excerpts;
   host code supplies canonical identities and topology. Entry and prospective
   network gates classify omissions by owner and prevent partial drafts from
   reaching the assembler.
6. If the QueryAgent clearly estimated a value but omitted chemistry needed to
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
7. `validate_support_eq_map/` independently revalidates identities, numeric
   source bindings, receipt lineage, native topology, and the session working
   map before publication. Any unresolved pair or invalid materialization fails
   closed to the reference-only path.

The LC1.3 QueryAgent uses the standard SRD-46 tool catalog and tool-call syntax.
The standalone MANDATORY WORKFLOW section is left out of its prompt, and in
embedded mode the runtime refuses no tool call: the resolved pair IDs name only
the estimation target, and the agent may run `search_metals`, `search_ligands`,
`build_system_catalog`, the planner and every evidence tool to find analogue
systems. The LC1.3 chemistry context in
`dispatch_srd46_query/query_estimation_system_prompt.md` permits a clearly
labelled chemistry-informed estimate while preserving retrieved values
verbatim. It contains no reporting format, parser schema or machine-output
requirement; those reach the agent only as follow-up prompts after its answer
(the reporting turn, clarifications, continuations). Every such host prompt
begins with `[follow-up]` (`clarification_renderer.FOLLOW_UP_TAG`), and the
Query runtime tells a turn its remaining iterations and seconds only when it is
close to its limits, naming the turn the notice governs (the exploration turn,
or the follow-up turn that began with the latest `[follow-up]` message), so
budgets of different turns are not confused (`query_agent._remaining_budget_notice`).

## Active modules

```text
LC1_3_estimate_eq_stability_dispatch/
  __init__.py                         # stable package API
  LC1_3_estimate_eq_stability_dispatch_orchestrator.py
  README.md
  dispatch_srd46_query/               # pair scope, prompts, query runtime,
                                      # receipts, the reporting turn, clarification
  parse_speciation_answer/            # parser workspace and deterministic gates
  runtime_support/                    # shared models and artifact I/O
  validate_support_eq_map/            # final support-map assembly and validation
```

The public orchestrator coordinates query dispatch, parsing and support-map validation. Estimation is enabled upstream; LC1.3 uses the declared pair scopes to carry out that request.

