## Answer

This calculation could not be completed: the SRD-46 database does not carry the aqueous complexation data needed to place both U(VI) and Th(IV) on a common 18-crown-6 basis, and the pipeline aborted at the eq-card alignment stage before any free-energy card or solver run was built. No numerical speciation was produced.

The chemical reason is straightforward. 18-crown-6 is a hard-cation macrocycle whose aqueous binding to actinyl and tetravalent-actinide cations is weak and sparsely tabulated. Uranyl (UO₂²⁺) is a linear dioxocation that prefers equatorial O/N donors in its equatorial plane rather than sitting inside a crown cavity, and Th⁴⁺ is generally too large and too strongly hydrated to be a good fit for the 18-crown-6 cavity in water. As a result, at least one of the metal–crown pairs the joint pot requires has no usable entries in SRD-46, and the alignment step cannot assemble a consistent equilibrium set for the four-component mixture.

The EDTA half of the problem is not the blocker — both UO₂-EDTA and Th-EDTA complexation, plus the H₄EDTA/H₃EDTA⁻/H₂EDTA²⁻/HEDTA³⁻/EDTA⁴⁻ protonation ladder, are well covered by SRD-46. So a tractable reformulation would be either:

- **Drop the crown ether** and compute the joint U(VI)/Th(IV) + EDTA pot at pH 5 — this would resolve cleanly and show how the two metals partition on EDTA (chemically one would expect Th(IV), with its very large log K for Th-EDTA, to sequester EDTA preferentially over uranyl at pH 5), or
- **Replace 18-crown-6** with an aminopolycarboxylate or macrocycle for which SRD-46 carries actinide binding constants (e.g. DTPA, NTA).

I did not fabricate dominant complexes, fractions, or partitioning numbers, because with LC1 aborted there is no computed evidence to cite.

## Evidence
- calculation: `status="failed"`, `stage="LC1"`, `error="LC1 failed"`, elapsed 28.6 s.
- `list_outputs` returned empty — no `*_verdict.md`, no free-energy card, no solver CSVs were written.
- LC1 (eq-card alignment) is the step that matches every requested metal/ligand pair against SRD-46 equilibrium entries before any downstream card or solve; a hard failure there with zero partial artifacts indicates the {U(VI), Th(IV)} × {18-crown-6, EDTA} joint system could not be assembled from tabulated data.

## Final deliverables

- [Result 01](final/result_01/answer.md): Compute the joint aqueous speciation of a single pot containing U(VI) and Th(IV) with 18-crown-6 and EDTA at pH 5, identifying the dominant uranyl-crown and thorium-crown complexes alongside the EDTA species.
