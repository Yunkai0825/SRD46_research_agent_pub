## Answer

In a single beaker holding **1 mM Cu²⁺ + 1 mM Zn²⁺ + 1 mM EDTA** at pH 6, 25 °C, I = 0.1 m, **Cu wins the ligand almost completely.** Virtually all of the sub-stoichiometric EDTA (one equivalent split between two metals) ends up on Cu, leaving Zn essentially uncomplexed as free Zn²⁺(aq).

At pH 6 the joint solver returns:

| Metal | EDTA-bound fraction | Free / hydrolysed fraction | Bound : Free ratio |
|-------|--------------------|---------------------------|--------------------|
| Cu(II) | 0.9161 (as [Cu(EDTA)(OH)]³⁻) | 0.0832 (as Cu²⁺) | **≈ 11 : 1** |
| Zn(II) | 0.0839 (as [Zn(EDTA)(OH)]³⁻) | 0.9157 (as Zn²⁺) | **≈ 0.092 : 1 (≈ 1 : 11)** |

So on a mole basis, out of 1 mM EDTA the pot puts **~0.916 mM onto Cu and only ~0.084 mM onto Zn**, a **~10.9-fold preference for Cu**. Cu snaps up virtually the entire ligand pool while Zn is left ~92% aquo.

**Why Cu wins.** EDTA is a hexadentate hard-N/O chelator, and Cu²⁺ is a strongly Jahn–Teller-active borderline Lewis acid whose complex with EDTA (log K₁ ≈ 18.8 for CuEDTA²⁻) is roughly two to three orders of magnitude more stable than the analogous Zn complex (log K₁ ≈ 16.5). When the two metals compete for one equivalent of ligand in the *same* pot, the equilibrium constant for the exchange reaction 
Zn(EDTA)²⁻ + Cu²⁺ ⇌ Cu(EDTA)²⁻ + Zn²⁺ is ~10²·³, i.e. Cu drives Zn off the ligand until the free-metal ratio balances that stability gap. The card here actually stabilises the mixed-hydroxo species [M(EDTA)(OH)]³⁻ at pH 6 (deprotonation of a coordinated water on the six-coordinate chelate); this only widens the Cu preference because Cu's tetragonal geometry accommodates the axial OH particularly well. The ~11:1 partition observed at pH 6 is exactly the thermodynamic signature of that stability-constant difference.

**Chemical interpretation.** In practical terms, one equivalent of EDTA in a Cu/Zn mixture behaves as a Cu-selective mask: it will scavenge Cu²⁺ nearly quantitatively before touching Zn²⁺. Zn remains chemically "available" (as aquo Zn²⁺) for any downstream ligand, indicator, or precipitation step, while Cu is locked into the very stable, anionic Cu–EDTA hydroxo-chelate.

## Run status: timed out

The L0 orchestration reached its iteration or reasoning-time limit. This text is a partial synthesis and must not be treated as a completed or validated run. The structured API result and manifest also set `timed_out: true` and `completion_status: timed_out`.

## Validation status: incomplete

## Evidence

- Verdict, per-element speciation:
  - Cu²⁺ (Cᴛ = 1.00 mM): "Dominant species by pH region: pH 3.0–9.0 → [Cu(EDTA)(OH)]³⁻; peak 91.6% at pH 3.0."
  - Zn²⁺ (Cᴛ = 1.00 mM): "Dominant species by pH region: pH 3.0–7.2 → Zn²⁺; peak 91.6% at pH 3.0"; Zn²⁺ ↔ [Zn(EDTA)(OH)]³⁻ crossover at pH ≈ 7.12.
  - EDTA (L1, Cᴛ = 1.00 mM): "Dominant species by pH region: pH 3.0–9.0 → [Cu(EDTA)(OH)]³⁻."
- Cu envelope at pH 6.000: Cu²⁺ = 0.08319, [Cu(EDTA)(OH)]³⁻ = 0.91612, [Cu(OH)₂](s) = 0 → bound/free = 0.9161 / 0.0832 ≈ 11.0.
- Zn envelope at pH 6.000: Zn²⁺ = 0.91575, [Zn(EDTA)(OH)]³⁻ = 0.08388, Zn(OH)₂(α) = 0 → bound/free = 0.0839 / 0.9157 ≈ 0.0916 (i.e. ≈ 1 : 10.9).
- Ligand distribution at pH 6: EDTA is 91.6% on Cu vs 8.4% on Zn → **~10.9× preference for Cu**, exact complement of the two envelopes (sub-stoichiometric ligand budget conserved to 4 decimals).
- Convergence: 31/31 pH points converged; ionic strength held within 0.0045–0.0065 M of the 0.1 M target; no precipitates present at pH 6 (Cu(OH)₂(s) only appears at pH ≥ 6.6, Zn(OH)₂ at pH ≥ 7.2), so the partition at pH 6 is a clean homogeneous-solution competition.

## Final deliverables

- [Result 01](final/result_01/answer.md): Determine competitive EDTA partitioning between Cu(II) and Zn(II) in a shared beaker where EDTA is sub-stoichiometric relative to the combined metal load.
