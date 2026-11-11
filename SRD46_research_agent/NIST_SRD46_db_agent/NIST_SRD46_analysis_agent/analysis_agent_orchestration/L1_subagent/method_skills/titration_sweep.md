# Method briefing: titration_sweep (1-D vs added titrant volume)

## What those curves mean

A titration sweep tells the same equilibrium story while one solution is
progressively poured into another, marching along added-titrant volume at a
held pH rather than along pH itself. At each volume the solver re-solves the
whole mixed, diluted system, so the curve traces how the element's speciation
shifts as reagent accumulates — complexes assembling, a ligand saturating, a
sink slowly filling — with the real fractions and concentrations at every step
in the per-step table. Equivalence and inflection points are genuine features
of that solved curve (taken from the bracketing samples), marking where a
stoichiometric ratio is reached; because dilution by the titrant is already
folded into every total, any buffering or sharpness is whatever the local
curve actually does, not what an idealised titration formula would promise.

## What you receive

    Titration verdict (*_verdict.md)
    ├─ dominance intervals along V_added_mL — label changes bracketed
    │    by adjacent samples
    └─ included / excluded species blocks

Also supplied: `thermodynamic_reference_constants.md` (the only source
for constants you quote; it exposes the card's `log_beta` — call a value
a pKa or another named constant only when the corresponding
reaction/species definition justifies that name); via `list_outputs`:
per-step species fraction/concentration CSVs, state metrics
(convergence), and PNG paths (never openable).

## Reading hints
- The axis is added titrant volume, not pH: features map to pH or pM
  only through the solved CSV columns at that volume, never through
  ideal-titration formulas.
- Equivalence points are solved-curve features (crossovers or
  inflections); quote them from the bracketing samples.
- Dilution by the titrant is part of the solved state: per-step totals
  come from the CSV, not the initial analytical values.
- Buffering claims rest on the actual local slope between samples, not
  textbook intuition about the ligand.
- Convergence coverage comes first; unconverged samples are not
  evidence.

