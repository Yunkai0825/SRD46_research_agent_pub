# Method briefing: pourbaix_sweep (predominance map, pH × E_V [× a_w])

`pH` and `E_V` are always axes; an optional `a_w` axis makes the sweep
3-D. The verdict is dimension-generic: regions fill the ambient space,
boundaries are codim-1 manifolds (curves in 2-D, surfaces in 3-D), and
junctions are lower-dimensional features. `// Coordinate order` at the
top of the topology details fixes the meaning of every coordinate list.

## What this map means

A Pourbaix map is the stability atlas of one element across acidity (pH) and
oxidising power (the potential E_V — how electron-poor the solution is held).
Read across it, it tells the element's chemical story: which oxidation state
endures, and within that state whether the element sits as the free aqua ion,
as hydrolysed hydroxo species, as a dissolved complex, or as a solid oxide /
hydroxide / metal. Each predominance field is one such form winning the
element's mass balance — a `DmsReg_i` region wearing its dominant-species
label `Dms_i`. The curve between two fields (`DmsRegEq_i`) is the
condition where those two forms are equally abundant — the equilibrium of
the reaction that interconverts them. Whether that reaction is redox is
read from the free-energy card, never from the line's shape: compare the
element's formal oxidation state in the two labels, and a change means
electrons are traded (redox) while no change marks an acid–base,
hydrolysis, complexation, or dissolution step. Orientation is not
mechanism — a non-redox boundary is not forced to stand vertical, since
speciation and activities can tilt it or even carry it horizontally, and a
redox couple that also exchanges protons merely leans with pH. Where
several fields meet (`DmsRegEqJnc_i`) those species coexist at once. Predominance is a
thermodynamic majority, not purity — lesser forms linger alongside, and the
real amounts, solubilities, and whether a solid truly precipitates are
questions for the full-speciation table, not the region label.

## Verdict schema (one `*_verdict.md` per principal element)

    Solver report (pourbaix_sweep)
    ├─ System — components, constraints, potential reference,
    │    per-axis domain, coarse and final grid spacing
    ├─ Dominant species catalog — Dms_i ↔ species label
    ├─ Topology stats — counts of regions, boundary manifolds,
    │    internal vs sweep-limit junctions; disconnected dominant
    │    species with their region IDs
    ├─ Reference line (classified-grid cut) along <axis> — one per
    │    axis: a 1-D dominance ladder on ONE grid line, every other
    │    axis fixed at its grid sample nearest the domain center
    │    (the pH line runs at the map's center E_V, the E_V line at
    │    the map's center pH); all values print as full named
    │    (pH, E_V[, a_w]) tuples with units; label changes bracketed
    │    by adjacent samples
    └─ Topology details (// Coordinate order: ...) — every list is
       split into `####` subsections and its canonical IDs increment
       down the page in that grouped order:
       ├─ regions — grouped by phase (solid, then liquid); DmsReg_i
       │    {label}: measure in the solver frame, neighboring regions
       │    (DmsReg_j via DmsRegEq_k), junction-feature list
       ├─ boundary manifolds — grouped by phase pair × label redox
       │    (liquid–liquid, solid–liquid, solid–solid; each split into
       │    redox / non-redox by the card's formal oxidation states);
       │    DmsRegEq_i: region pair, intrinsic dimension, compact
       │    simplified geometry (e.g. polyline)
       └─ junction features — grouped by how many coexisting species
            are solid (all liquid, one solid, two solids, …);
            DmsRegEqJnc_i: exact grid coordinates,
            `At sweep limit: true|false`

## Canonical Topology Prefixed ID hierarchy

Each family name extends the previous one, mirroring how the features
nest — a label owns regions, a region pair shares a boundary, and
boundaries end or meet in junctions:

| Canonical family | Feature | Codimension |
|---|---|---|
| `Dms_i` | dominant-species label (catalog entry) | — |
| `DmsReg_i` | connected region owned by one `Dms` label | 0 |
| `DmsRegEq_i` | boundary manifold between two `DmsReg` regions | 1 |
| `DmsRegEqJnc_i` | junction where `DmsRegEq` manifolds meet or hit the frame | ≥ 2 |

Numeric suffixes increment down each rendered table in its grouped
display order — regions by phase, boundaries by phase pair × label
redox, junctions by solid count — so within a family the IDs read 1, 2,
3… top to bottom; the numbers do not necessarily carry correlation
across families (`DmsReg_3` might or might not be related to `Dms_3` or
`DmsRegEq_3`). Features are related only through
the explicit cross-references in their record sections: a dominatn-species 
label marks every region it owns (all its region IDs are collected in the
disconnected-species entry), a region names its neighbors and the boundary 
connecting each pair, a boundary names its region pair and junction features, 
a junction names its coordinates. Vice versa.

These IDs are the exact handles accepted by `inspect_topology_feature`,
which returns that one record — its cross-reference IDs plus lossless
coordinates listed in `// Coordinate order` (reference lines are not
ID-addressed; re-read them with `inspect_verdict_section`). The
`topo_csv_*` feature CSVs use the same canonical IDs in their `id` and
cross-reference columns; their `source_id` columns are solver-internal
linkage only — never cite or query a bare numeric source id.

## Feature roster (cite once, then refer by ID)

When the answer leans on the topology, open it with a short roster of
the features actually used — one line each, fully identified there, so
later text can refer to the bare ID and any inconsistency between a
claim and its roster entry is caught and corrected before finishing:

- `DmsReg_i`: dominant-species label + the region's corner junctions
  (`DmsRegEqJnc_*`) with their (pH, E_V[, a_w]) coordinates — the
  corners frame a bounding box, not the region's actual shape (an
  island region without junctions: say so, give approximate extent
  from its boundary's compact vertices).
- `DmsRegEq_i`: the two dominant species / `DmsReg` pair it
  separates + its per-axis (pH, E_V[, a_w]) span — a straight-line
  summary, not the actual curved manifold.
- `DmsRegEqJnc_i`: coexisting species with their phases + exact
  (pH, E_V[, a_w]) location + `At sweep limit` status.
- Reference line: which axis it runs along + the fixed
  center-coordinate tuple it was taken at.

Also supplied: `thermodynamic_reference_constants.md` (the only source
for constants you quote; it exposes the card's `log_beta` — call a value
a pKa or another named constant only when the corresponding
reaction/species definition justifies that name); via `list_outputs`:
integer label-map / cell-table CSVs (the exact classified grid), the
full-speciation CSV (concentrations, solids, saturation, convergence),
and PNG paths.
PNGs can never be opened — all geometry comes from the records above.

## Reading hints
- Claims are per-axis conditional: a pH window holds at stated E_V
  (and a_w) values or bands, and vice versa. Never flatten the map
  into a single pH ladder.
- A reference line is one grid line, not a summary; quote it only
  with its fixed coordinates stated. Slices elsewhere generally
  differ.
- Sequence-along-an-edge questions (e.g. what touches the metal region
  as pH rises): the region's neighbor list plus ordered junction
  coordinates answer this; one reference line or textbook habit does
  not.
- Helpful practice: draw a mental (pH, E_V[, a_w]) map — place each
  roster region by its corner junctions, connect neighbors across
  their boundaries — then walk each reference line through it: the
  predicted label sequence must reproduce that line's printed ladder
  at its fixed coordinates, and each crossed boundary's span must
  contain the bracketed transition. On a mismatch, fix the map or the
  claim before finishing.
- A species may own several disconnected regions; keep their separate
  verdict IDs (never silently collapse them), aggregate their measures
  before any "largest / dominant" claim, and say what was compared
  (single regions vs species totals, one element vs all).
- `At sweep limit: true` junctions and frame edges reflect the chosen
  window, not chemical stability limits or true triple points.
- Exact numbers come from junction coordinates and bracketed grid
  transitions on the final classified label grid; compact polylines are
  simplified and support topology, shape, and approximate location only.
- Redox vs non-redox is a label property read from the free-energy
  card, never a geometric estimate: compare the element's formal
  oxidation state in the two dominant-species labels — changed ⇒ redox,
  unchanged ⇒ non-redox (acid–base, hydrolysis, complexation,
  dissolution). Do not infer redox from a Nernst slope or a boundary's
  tilt; a non-redox boundary can still slope or run horizontally through
  speciation, so orientation never settles mechanism. E values stay vs
  SHE, quoted with the pH (and a_w) where they hold.
- The tables are split into `####` subsections — regions by phase,
  boundaries by phase pair × label redox, junctions by solid count —
  and canonical IDs increment within each family in that order; a label
  whose card phase or formal oxidation state cannot be resolved lands in
  a `… unresolved` subsection rather than a guessed one.
- A `// PARSER FAILURE — species attribute resolution: …` line under
  `## Topology details` means the card's phase/oxidation attributes could
  not be parsed (unsupported card shape in this workflow); the features
  are then listed ungrouped. You decide credibility: cross-check the
  free-energy card before quoting any phase or redox claim.
- Convergence coverage comes first; unconverged cells are not evidence.

