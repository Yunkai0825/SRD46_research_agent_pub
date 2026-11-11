# Chemistry-Level Inquiry Prompts for the Calc-Input Building Agent

These prompts are written at the **chemistry inquiry level**. They describe the
*scientific question* the user wants answered. The agent is expected to:

- pick the appropriate `sweep_method` (`pH_sweep`, `pourbaix_sweep`,
  `titration_sweep`, …),
- decide which axes vs. fixed parameters are needed,
- resolve metal / ligand `db_id`s and redox states from the catalog,
- pick reasonable defaults for `temperature`, `ionic_strength`, `activity_model`,
  `solids`, grid resolution, and `grid_refine`,
- choose between simple `_fixed` constraints, composite `constr_1/constr_2`
  constructs, or `_freeform` equations when the chemistry demands it,
- emit both the solver-ready `*_example.json` and the human-readable
  `free_energy_card.md`.

Do not pre-specify schema field names in the prompts — keep them in chemist's
language. One prompt per intended test case.

---

## Prompt 01 — pH speciation of Ca²⁺ with glyphosate

**Purpose:** See how the calcium–glyphosate system speciates across the full pH window.

**Tasks:**
- Scan pH 0 → 14 on a fine 1-D grid.
- Set T = 25 °C and ionic strength ≈ 0.1 M.
- Total calcium ≈ 1 mM, total glyphosate ≈ 10 mM.
- Use the Davies activity model and allow precipitates.

## Prompt 02 — Cu / glycine Pourbaix diagram

**Purpose:** Build a 2-D Pourbaix diagram (pH × E) for Cu in the presence of glycine.

**Tasks:**
- Use 1 mM Cu and 10 mM glycine.
- Cover pH 0–14 and E from −1.0 to +1.5 V.
- Include all accessible Cu oxidation states and let solids form.
- Use a 12 × 12 base grid with adaptive refinement around phase boundaries.
- Standard conditions otherwise (25 °C, I = 0.1 M, Davies).

## Prompt 03 — 3-D Pourbaix with variable water activity (Fe + Cu / glycine + citrate)

**Purpose:** Produce a Pourbaix-style map for a mixed Fe + Cu system chelated by glycine and citrate that also varies water activity, to see how dehydrated conditions move the phase fields.

**Tasks:**
- Use Fe + Cu at 1 mM each and glycine + citric acid at 10 mM each.
- Vary water activity between 0.7 and 1.0.
- Keep pH 0–14 and E −1 to +1.5 V bounds.
- A coarse grid is fine for a first look.

## Prompt 04 — 2-D Pourbaix, mixed Fe + Cu with two ligands (no a_w axis)

**Purpose:** Produce the standard pH–E Pourbaix for the Fe + Cu / glycine + citrate system at unit water activity.

**Tasks:**
- Drop the water-activity axis (unit a_w).
- Use both metals at 1 mM and both ligands at 10 mM.
- Use an 8 × 8 grid with refinement.

## Prompt 05 — Titration of glyphosate against Ca²⁺

**Purpose:** Simulate a titration adding base/titrant into the Ca–glyphosate solution.

**Tasks:**
- Add up to 50 mL of base/titrant along the added-volume axis.
- Use ~100 titration points.
- Use 1 mM Ca and 10 mM glyphosate.
- Set T = 25 °C, I = 0.1 M.
- It is OK if the titration sweep isn't fully wired yet — emit the input card so the solver can flag the gap.

## Prompt 06 — Cu / glycine speciation along the water Nernst line

**Purpose:** Run a 1-D pH sweep of the Cu–glycine system with the potential tracking the water/H⁺ Nernst line.

**Tasks:**
- Use 1 mM Cu and 10 mM glycine; pH 0–14, ~30 points.
- Drive E along the water/H⁺ Nernst line: E = −0.059 × pH.
- Standard 25 °C, I = 0.1 M, Davies, solids on.

## Prompt 07 — Stoichiometric dosing chain in a Fe + Cu / glycine + citrate Pourbaix

**Purpose:** Produce a 2-D Pourbaix for a Fe + Cu / glycine + citrate system using a coupled dosing protocol rather than fixed totals.

**Tasks:**
- Use pH 2–12, E −0.5 to +1.5 V, 6 × 6 grid with refinement.
- Grow the glycine dose with pH: `[L_glycine]_tot = 1e-4 · (1 + 0.5 · pH)`.
- Set citrate to half of the glycine dose.
- Add Fe(II) at 2.1× the glycine dose.
- Balance total Fe against the chelator load plus the Cu(II) pool: `[Fe]_tot = 4.1 · ([L_citrate]_tot + [L_glycine]_tot) + [Cu²⁺]_tot`.
- Keep total Cu fixed at 1 mM with [Cu²⁺] pinned at 0.8 mM (the rest partitions across the other Cu oxidation states via Nernst from the grid).

## Prompt 08 — Over-determined Cu redox partition (element + reference-state pinned)

**Purpose:** Run a Pourbaix for Cu–glycine pinning both the total Cu and the Cu(II) sub-total.

**Tasks:**
- Use pH 0–14, E −1 to +1.5 V, 8 × 8 grid with refinement.
- Pin both the total Cu (1 mM) and the Cu(II) sub-total (0.8 mM).
- Let the remaining Cu(I)/Cu(0)/Cu(−1) populations fall out of Nernst from the grid E.
- Dose glycine pH-dependently: `[L_glycine]_tot = 0.001 + 0.0005 · pH`.

## Prompt 09 — Cu / glycine pH sweep along a user-defined Nernst-style line

**Purpose:** Run a 1-D pH sweep of Cu–glycine driving E along a user-defined Nernst-style line with named scalar parameters.

**Tasks:**
- Use pH 0–14, ~30 points; 1 mM Cu, 5 mM glycine; 25 °C, I = 100 mM.
- Drive E along a line `E = intercept + slope · pH`.
- Supply `slope = −0.059 V/pH` and `intercept = 0 V` as named scalar parameters (so the slope/intercept can be swept later by just changing those numbers).

---

## Notes for the agent

- Resolve `Ca`, `Cu`, `Fe`, `Zn`, `Hg`, … and ligands (`Glycine`, `Citric acid`,
  `Glyphosate`, `Imidazole`, `Hydroxide`, …) against the NIST SRD-46 catalog;
  emit the actual `metal_*` / `ligand_*` `db_id`s and SMILES.
- Always include the proton/hydroxide reference (H⁺ as M0, OH⁻ as L0) in the
  generated `free_energy_card.md`.
- Default to `activity_model: "davies"`, `solids: "include"`, T = 298.15 K,
  I = 0.1 M unless the prompt overrides them.
- Use composite `{"constr_1": ..., "constr_2": ...}` only when the user pins
  more than one quantity for the same element (e.g. Prompts 07, 08).
- Use `custom_freeform` for any RHS equation involving axes or other totals
  (Prompts 06, 07, 08, 09); declare bare-symbol parameters in
  `system_catalog.freeform_vars_define` (Prompt 09).
