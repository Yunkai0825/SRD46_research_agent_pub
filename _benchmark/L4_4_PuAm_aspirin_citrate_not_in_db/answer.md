## Answer

This joint speciation **cannot be computed from SRD-46** as posed. The database has no complexation data for the metal–ligand combinations required, and the pipeline correctly refuses to invent constants or silently substitute a different chemistry. Three independent gaps all apply:

1. **Acetylsalicylic acid (aspirin) is not in SRD-46's metal-complexation catalogue for either Pu(IV) or Am(III).** No stability constants exist to bind aspirin to these actinides in the database. (Chemically, aspirin also hydrolyses in water to salicylate + acetate, so real experiments at pH 4 are dominated by salicylate binding — but the pipeline cannot make that substitution on its own.)
2. **Pu is absent from the requested ligand set entirely.** Even the well-known, very strong Pu(IV)–citrate chelates (1:1 and 1:2) that would dominate Pu(IV) speciation at 5 mM citrate near pH 4 in real systems are not carried in the SRD-46 slice available here. With no Pu row against any requested ligand, no Pu chemistry can be posed — not even Pu(IV) hydrolysis coupled to ligand competition.
3. **Am × aspirin is missing** as well. Am(III)–citrate data may be present, but the pipeline will not silently drop aspirin and solve a reduced Am–citrate-only problem, because that answers a *different* scientific question (it removes the very competition you asked about).

Because the run halted at the eq-card alignment step (LC1), no free-energy card, no solver-parameter card, and no numerical solution were produced. There is therefore nothing to quote about dominant Pu or Am complexes, bound fractions, or free-metal residuals — any such number would be fabricated.

**What the chemistry would look like if the data were available** (offered only as context, not as a computed result): at pH 4 with 5 mM citrate, Pu(IV) is expected to be almost entirely sequestered as Pu(IV)–citrate chelates (citrate's α-hydroxy + carboxylate donor set is an excellent match for the hard, highly charged Pu⁴⁺ centre, and Pu(IV) hydrolysis would be strongly suppressed). Am(III), being softer and only trivalent, binds citrate more weakly but should still be predominantly citrate-complexed at 5 mM ligand and pH 4. Salicylate (the aspirin hydrolysis product) is a much weaker competitor than citrate for both cations, so a real "aspirin vs citrate" competition would resolve overwhelmingly in citrate's favour for both metals. None of this is a solver output.

**To make the question tractable in SRD-46**, any of the following substitutions would need to be requested explicitly:
- Replace aspirin with **salicylate** (the actual binding species in aged aspirin solutions), which is a standard SRD-46 ligand.
- Restrict the metal set to **Am(III) only**, or use **Th(IV) as a non-redox Pu(IV) analogue**, if the scientific interest is the ligand-competition pattern rather than Pu itself.

## Evidence
- LC1 deterministic error: *"SRD-46 has no data for the requested metal-ligand system (not in database): ligand(s) with no complexation data against any requested metal: Acetylsalicylic acid; metal(s) with no complexation data against any requested ligand: Pu. Missing metal x ligand pairs: Pu x Acetylsalicylic acid, Pu x Citric acid, Am x Acetylsalicylic acid."*
- Pipeline stage reached: LC1 (eq-card alignment); no free-energy card, solver-parameter card, or numerical solve was attempted.
- Convergence: not applicable — zero samples computed.

## Final deliverables

- [Result 01](final/result_01/answer.md): Compute joint aqueous speciation of a single pot containing Pu(IV) and Am(III) with aspirin (acetylsalicylic acid) and citrate as competing ligands at pH 4, and identify the dominant Pu and Am complexes with each ligand.
