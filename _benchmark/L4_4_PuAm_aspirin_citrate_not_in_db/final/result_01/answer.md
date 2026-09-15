## Doability
Not doable with SRD-46. The pipeline halted at LC1 (eq-card alignment) because the requested metal–ligand combinations are not represented in the database.

## Result
- System requested: Pu(IV) 1 mM + Am(III) 1 mM + acetylsalicylic acid (aspirin) 5 mM + citrate 5 mM, pH 4, 25 °C, I = 0.1 m, joint speciation.
- Method: `pH_sweep` at fixed pH (single-point joint equilibrium).
- Outcome: build stopped at LC1 before any free-energy card, solver-parameter card, or numerical solve was attempted. Deterministic error returned:
  > "SRD-46 has no data for the requested metal-ligand system (not in database): ligand(s) with no complexation data against any requested metal: Acetylsalicylic acid; metal(s) with no complexation data against any requested ligand: Pu. Missing metal x ligand pairs: Pu x Acetylsalicylic acid, Pu x Citric acid, Am x Acetylsalicylic acid."
- Convergence: not applicable — no samples were computed.

## Analysis
Three separate gaps in SRD-46 make this joint speciation impossible to build from the database:

1. **Acetylsalicylic acid (aspirin) has no complexation data against either metal.** SRD-46 does not carry stability constants for aspirin with Pu(IV) or Am(III). This gap is not a matter of ionic-strength extrapolation — the ligand itself is absent from the metal-complexation catalogue for these actinides, so no LC1 row can be aligned. Aspirin is also hydrolytically unstable in aqueous solution (it slowly hydrolyses to salicylate + acetate), which is part of why direct complexation data with hard f-element cations is sparse in critical compilations; any real experiment at pH 4, 25 °C would in fact be dominated by salicylate binding after modest aging. But the pipeline cannot silently substitute salicylate for aspirin, and it correctly refuses to invent an aspirin constant.

2. **Pu is missing from the entire requested ligand set.** SRD-46's core scope is protonation and metal-ligand equilibria for a curated set of metals; Pu(IV) complexation with citrate — even though it is well studied in the actinide literature (Pu(IV)–citrate is known to form very strong 1:1 and 1:2 chelates that dominate Pu(IV) speciation at millimolar citrate near pH 4) — is not present in the SRD-46 slice available to this pipeline. Because Pu has no complexation row against *any* requested ligand, no Pu chemistry can be posed here at all, not even Pu(IV) hydrolysis coupled to ligand competition.

3. **Am × aspirin is missing** for the same reason as (1). Am(III)–citrate data may exist in SRD-46, but the pipeline requires the full requested ligand set to be representable before it will build a joint card; it will not silently drop aspirin and solve a reduced Am–citrate-only problem, because that would answer a different scientific question than the one posed (ligand competition between aspirin and citrate).

Because LC1 stopped before any card was written, there is no free-energy card, no solver-parameter card, no verdict, and no convergence diagnostic to quote. Reporting dominant complexes, bound fractions, or hydrolysis/free-metal fractions here would require fabricating constants, which is disallowed.

**What would make this tractable:**
- Replace aspirin with **salicylic acid / salicylate** (the hydrolysis product actually responsible for metal binding in aged aspirin solutions), which is a standard SRD-46 ligand for many f-elements and would let the aspirin-versus-citrate competition be posed honestly as a salicylate-versus-citrate competition.
- Restrict the metal set to **Am(III) only** (or another actinide/lanthanide surrogate for Pu(IV) that is in SRD-46, e.g. Th(IV) as a common non-redox Pu(IV) analogue) if the scientific interest is the ligand-competition pattern rather than Pu itself.
- Any of these substitutions changes the chemistry and should be requested explicitly at the L0 level rather than assumed here.

## Final deliverables

- [LC1/lc1_sweep_input.json](<LC1/lc1_sweep_input.json>)
- [LC1/status.json](<LC1/status.json>)
- [LD/answer.md](<LD/answer.md>)
- [LD/verdict.json](<LD/verdict.json>)
- [verdict.json](<verdict.json>)
