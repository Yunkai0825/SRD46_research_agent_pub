# Method briefing: freeform_sweep (arbitrary-axis sweep)

Axes are whatever the card declares; the per-axis domain and
`// Coordinate order` line fix the meaning of every coordinate list —
pH or `E_V` may or may not be present.

## What this sweep means

A freeform sweep tells the same equilibrium-speciation story, but projected
onto whatever variables the study cares about — total ligand, temperature, a
competing solute, a clamped potential — so each axis carries the chemical
meaning the card gives it rather than a preset pH/E frame. Along one axis it
reads as a ladder of which form predominates and where it yields to the next;
over two or more axes it becomes a predominance map of the very same kind as a
Pourbaix diagram, sharing its features — regions `DmsReg_i` labelled by their
dominant species `Dms_i`, the equal-abundance boundaries `DmsRegEq_i` between
them, and the `DmsRegEqJnc_i` junctions where several converge. Every boundary
is still just the equilibrium where two neighbouring forms are equally
abundant; read it through what its axes mean chemically — call it redox only
when E_V is genuinely one of them — and take the real concentrations and
saturation from the full-speciation table.

## What you receive

    Solver report (freeform_sweep)
    ├─ 1-D sweep: dominance intervals with bracketed label changes
    └─ 2-D and higher: the Pourbaix-briefing schema — regions
         (DmsReg_i with measure + neighbors), codim-1 boundary
         manifolds (DmsRegEq_i), junction features (DmsRegEqJnc_i),
         and one reference line (classified-grid cut) per axis,
         every other axis fixed at its grid sample nearest the
         domain center; values print as full named coordinate
         tuples with units

Also supplied: `thermodynamic_reference_constants.md` (the only source
for constants you quote; it exposes the card's `log_beta` — call a value
a pKa or another named constant only when the corresponding
reaction/species definition justifies that name); via `list_outputs`:
classified-grid / label-map CSVs, the full-speciation CSV, and PNG
paths (never openable).

## Reading hints
- Every interval claim is conditional on the fixed values or bands of
  the remaining axes; a reference line is one grid line, not a
  summary — name its fixed coordinates when quoting from it.
- Units and direction are those of the card's axis definitions.
- Disconnected regions of one species keep their separate verdict IDs
  (never silently collapse them) and stay separate until their measures
  are explicitly aggregated.
- Sweep-limit junctions and frame edges reflect the chosen window, not
  chemistry.
- If `E_V` is an axis, the Pourbaix briefing's electrochemical hints
  apply: redox vs non-redox is read from the free-energy card's formal
  oxidation states, never from a boundary's slope or orientation, and
  E values stay vs SHE, quoted with the co-axis values where they hold.
- Convergence coverage comes first; unconverged samples or cells are
  not evidence.

