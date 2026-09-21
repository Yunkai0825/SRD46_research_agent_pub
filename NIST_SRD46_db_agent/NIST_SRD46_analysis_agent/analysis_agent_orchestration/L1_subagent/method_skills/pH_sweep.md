# Method briefing: pH_sweep (1-D speciation vs pH)

## What those curves mean

A pH-speciation sweep is the acid–base and complexation biography of a fixed
set of components at a single, frozen oxidation state. Holding the totals,
temperature, and ionic strength constant, it follows how the element
redistributes itself among protonated, hydrolysed, and complexed forms as the
solution is made more or less acidic. Climb the pH axis and you watch acidic
ligands deprotonate and metals begin to hydrolyse, so one complex or hydroxo
species after another takes the lead; the pH where two forms trade majority is
a crossover, reported as a dominance interval bracketed by the neighbouring
samples, with each form's full fraction-versus-pH profile in the speciation
table. There is deliberately no potential axis — the redox state is fixed, so
nothing here speaks to oxidation or reduction — and whether a form actually
drops out as a solid is a saturation question answered by the concentration /
solid columns, never by the aqueous ladder alone.

## What you receive

    Speciation verdict (*_verdict.md)
    ├─ dominance intervals along pH — label changes bracketed by
    │    adjacent samples
    ├─ per-species summaries
    └─ included / excluded species blocks

Also supplied: `thermodynamic_reference_constants.md` (the only source
for constants you quote; it exposes the card's `log_beta` — call a value
a pKa or another named constant only when the corresponding
reaction/species definition justifies that name); via `list_outputs`:
component fraction-envelope CSVs, full fraction/concentration tables,
`*_state_metrics.csv` (convergence), and PNG paths (never openable).

## Reading hints
- Crossover pH values are grid-bracketed: quote the bracketing samples
  (e.g. "between pH 4.18 and 4.19"), not an interpolated extra digit.
- Dominant = largest fraction, not exclusive; the fraction table backs
  up words like "completely / exclusively / only".
- There is no potential axis: redox states are fixed by the included
  species set; no E-dependent (Pourbaix-style) conclusions.
- Results hold at the card's fixed totals, temperature, and ionic
  strength; generalizations say so.
- Precipitation windows come from saturation columns of the
  full-speciation CSV, not from the aqueous ladder alone.
- Convergence coverage comes first; unconverged samples are not
  evidence.

