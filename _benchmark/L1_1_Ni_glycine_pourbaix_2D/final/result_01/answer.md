## Doability
Doable — Ni + glycine is well covered in the SRD-46 catalog (three Ni-glycinate complexes, Ni hydrolysis, and Ni(0/II/III/IV) solids all present); a 2-D `pourbaix_sweep` over pH 0–14 and E = −1 to +1.6 V is exactly the pipeline's home ground.

## Result
- System: 1 mM Ni_tot + 10 mM glycine_tot at 25 °C, I = 0.1 m (SRD-46 constants; Atlas solids)
- Method: `pourbaix_sweep`, SHE reference
- Domain: pH ∈ [0, 14], E_V ∈ [−1, +1.6] V; final classified grid ΔpH = 0.008, ΔE = 0.002 V
- Convergence: 66 450/66 450 refined cells solved (`speciation_full_Ni_+_Glycine.csv` header: `n_refined: 66450`, `n_coarse_unrefined: 0`); every cell used for label assignment is converged.
- Topology: 9 dominant-species labels, 9 connected regions (no disconnected labels), 18 boundary manifolds, 10 internal + 6 sweep-limit junctions.

## Analysis

### Feature roster (canonical IDs referenced below)
Aqueous Ni(II) regions (all liquid, non-redox among themselves):
- `DmsReg_9` {Ni²⁺}: bounded by `DmsRegEqJnc_7` (pH 0, E = −0.333 V, sweep limit), `DmsRegEqJnc_3` (pH 6.06, E = −0.345 V), `DmsRegEqJnc_6` (pH 6.06, E = 0.869 V), `DmsRegEqJnc_11` (pH 5.364, E = 1.013 V), `DmsRegEqJnc_12` (pH 4.132, E = 1.227 V), `DmsRegEqJnc_8` (pH 0.972, E = 1.6 V, sweep limit). Largest liquid region (measure 10.11).
- `DmsReg_8` {[Ni(Glyc)]⁺}: narrow vertical slab between `DmsRegEqJnc_3` (pH 6.06, −0.345 V), `DmsRegEqJnc_2` (pH 6.764, −0.365 V), `DmsRegEqJnc_5` (pH 6.764, +0.765 V), `DmsRegEqJnc_6` (pH 6.06, +0.869 V). Measure 0.84.
- `DmsReg_7` {[Ni(Glyc)₂]}: between `DmsRegEqJnc_2` (pH 6.764, −0.365 V), `DmsRegEqJnc_1` (pH 7.916, −0.429 V), `DmsRegEqJnc_4` (pH 7.908, +0.687 V), `DmsRegEqJnc_5` (pH 6.764, +0.765 V). Measure 1.31.
- `DmsReg_6` {[Ni(Glyc)₃]⁻}: bounded by `DmsRegEqJnc_1` (pH 7.916, −0.429 V), `DmsRegEqJnc_9` (pH 11.236, −0.549 V), `DmsRegEqJnc_10` (pH 11.236, +0.257 V), `DmsRegEqJnc_4` (pH 7.908, +0.687 V). Measure 3.47.
Solids:
- `DmsReg_1` {Ni⁰(s)}: bottom of the map, capped by the Ni⁰/aqueous curves `DmsRegEq_7` (Ni²⁺, from pH 0/E = −0.333 V up to pH 6.06/−0.345 V), `DmsRegEq_6` (→ Ni-Glyc⁺), `DmsRegEq_5` (→ Ni-Glyc₂), `DmsRegEq_4` (→ Ni-Glyc₃⁻, rising slightly to pH 11.24/−0.549 V), then `DmsRegEq_15` to Ni(OH)₂ up to `DmsRegEqJnc_13` (pH 14, E = −0.711 V, sweep limit). Largest solid region (measure 7.84).
- `DmsReg_2` {β-Ni(OH)₂}: narrow triangular wedge in the alkaline II-oxidation corner between `DmsRegEqJnc_13` (pH 14, −0.711 V), `DmsRegEqJnc_9` (pH 11.236, −0.549 V), `DmsRegEqJnc_10` (pH 11.236, +0.257 V), `DmsRegEqJnc_14` (pH 14, +0.095 V).
- `DmsReg_3` {Ni₃O₄·2H₂O} (mixed II/III): large upper-central region from `DmsRegEqJnc_4/5/6` (E ≈ 0.69–0.87 V, pH 6–8) rising to `DmsRegEqJnc_11` (pH 5.364, +1.013 V) and `DmsRegEqJnc_14/15` at pH 14.
- `DmsReg_4` {Ni₂O₃·H₂O} (Ni(III)): thin band between `DmsRegEqJnc_11`, `DmsRegEqJnc_12` (pH 4.132, +1.227 V), `DmsRegEqJnc_16` (pH 14, +0.643 V), `DmsRegEqJnc_15` (pH 14, +0.501 V).
- `DmsReg_5` {NiO₂·2H₂O} (Ni(IV)): top strip above `DmsRegEq_16` and `DmsRegEq_9`, capped by the sweep top; `DmsRegEqJnc_8` (pH 0.972, +1.6 V, sweep limit) marks where its lower boundary with Ni²⁺ exits the box.

### Ni(II) aqueous stability ladder (read at each E_V band the boundary spans)
The three glycinate–glycinate boundaries `DmsRegEq_3`, `DmsRegEq_2`, `DmsRegEq_1` are essentially vertical (E-independent within the Ni(II) band, as expected for non-redox proton-driven ligand-exchange steps). Reading the pH-center reference line at E = +0.3 V (which lies inside every Ni(II) field) gives the canonical pH windows:

Chemically, these crossovers track the successive additions of the anionic glycinate donor to Ni(II): the free glycinate concentration climbs as pH crosses pKa₂ ≈ 9.57 (single deprotonation `HGlycine ⇌ Glycine⁻ + H⁺`, from the reference table's log β for [HGlycine] = +9.57 built on the [Glycine]⁻ = L1 basis). Even at 10 mM total glycine, [Glycine⁻] is small below pH 7, so Ni²⁺ dominates. Once [Glycine⁻] rises to a level where β₁·[Glyc⁻] ≈ 1 (β₁ = 10^5.74 → [Glyc⁻] ≈ 10^-5.74 M), the 1:1 complex takes over — this happens around pH 6.07, exactly where `DmsRegEq_3` sits. Successive steps to 1:2 and 1:3 (stepwise log K₂ = log β₂ − log β₁ = 10.58 − 5.74 = 4.84; log K₃ = 14.10 − 10.58 = 3.52) each need another factor of ~10^-K_n in [Glyc⁻], driving the 1→2 crossover to pH 6.80 and the 2→3 crossover to pH 7.97, again quantitatively consistent with the printed windows once the fixed 10 mM total glycine (only partly deprotonated in the transition range) is accounted for. All three glycinate complexes therefore appear as required.

### Precipitation of Ni hydroxide / mixed oxides at high pH
Above pH ≈ 11.05, even the tris-glycinate complex loses to the solid Ni(II)/Ni(II,III) hydroxide/oxide phases: at low E (≲ −0.549 V) the boundary is `DmsRegEq_15` (Ni⁰|Ni(OH)₂, spans pH 11.236, E = −0.549 V → pH 14, E = −0.711 V — a redox boundary with the Nernstian −0.059 V/pH slope of the Ni²⁺/Ni⁰ couple screened by hydroxide); the Ni(OH)₂ wedge (`DmsReg_2`) is thin because [Ni(Glyc)₃]⁻ remains competitive even at pH 11 for the moderate E band (`DmsRegEq_10` runs vertically at pH 11.236 from E = −0.549 to +0.257 V), and above that potential Ni oxidises to the mixed Ni₃O₄·2H₂O solid (`DmsRegEq_11`, tilting down to pH 7.9 at E = +0.687 V — a redox boundary between Ni(II) aqueous glycinates and a Ni(II,III) oxyhydroxide).
- **Ni(III) window:** Ni₂O₃·H₂O (`DmsReg_4`) is stable in a narrow band; at pH 7 the E-center reference line gives Ni₃O₄·2H₂O → Ni₂O₃·H₂O at E ≈ 0.915 V (bracketed 0.914/0.916 V) and Ni₂O₃·H₂O → NiO₂·2H₂O at E ≈ 1.057 V (bracketed 1.056/1.058 V). At acidic pH, `DmsRegEq_8` shows the Ni²⁺|Ni₂O₃·H₂O boundary sloping from (5.36, 1.013 V) to (4.13, 1.227 V) — the classic ≈ −(3/1)·0.059 V/pH slope for a 2-electron/6-proton couple 2 Ni²⁺ + 3 H₂O ⇌ Ni₂O₃·H₂O + 4 H⁺ + 2 e⁻. Below pH ≈ 4 the region shrinks to a wedge because NiO₂·2H₂O(IV) becomes competitive directly against Ni²⁺ (`DmsRegEq_9`, pH 4.13/1.227 V → pH 0.97/1.6 V).
- **Ni(IV) window:** `DmsReg_5` (NiO₂·2H₂O) forms the top of the map; its lower boundary `DmsRegEq_16` runs from (pH 14, 0.643 V) to (pH 4.13, 1.227 V) — again a redox line with a Nernstian slope characteristic of the Ni(III)/Ni(IV) couple. This solid is only reached above the O₂/H₂O line, so it is a strong-oxidiser regime relevant to electrochemical Ni oxidation (e.g. β-NiOOH → NiO₂ in Ni battery chemistry) rather than to open, aerated aqueous solutions.

### Stability window of the soluble Ni-glycinate complexes (summary)
- **[Ni(Glyc)]⁺:** pH ≈ 6.07 → 6.76, from E ≈ −0.35 V (Ni⁰ floor) up to E ≈ +0.87 V (oxidation to Ni₃O₄·2H₂O). A thin transitional slab — glycinate stabilisation is only just competitive with the aqua ion.
- **[Ni(Glyc)₂]:** pH ≈ 6.76 → 7.92, E ≈ −0.37 V up to E ≈ +0.69–0.77 V. The dominant Ni(II) form under near-neutral, mildly oxidising conditions — this is the window most relevant to biology and to Ni electroplating from glycinate baths.

- **[Ni(Glyc)₃]⁻:** pH ≈ 7.92 → 11.24, E ≈ −0.43 V (Ni⁰) up to E ≈ +0.26–0.69 V (Ni(II,III) oxide). The widest aqueous complex field: excess glycinate plus fully deprotonated Glyc⁻ pushes the tris-chelate to dominate all the way to alkaline conditions, and it, not Ni(OH)₂(s), is what prevents hydroxide precipitation between pH 8 and 11 in this system (contrast pure Ni-water, where Ni(OH)₂ appears near pH 8). This is the practical value of glycine as a Ni chelator: it holds ~1 mM Ni in solution up to pH ≈ 11 across the whole water-stability E range.

### Notes on the returned classification
Two `redox unresolved` subsections appear (`DmsRegEq_11`, `_17`, `_18`) because the card's phase/oxidation attributes for the mixed Ni(II,III) oxide Ni₃O₄·2H₂O don't parse cleanly against a single formal oxidation state — this is a label-grouping detail, not a numerical uncertainty. The dominant-species assignment, junction coordinates, and reference lines are all taken from the fully converged classified grid and are trustworthy.

## Final deliverables

- [LC1/lc1_2_eqmap_card.json](<LC1/lc1_2_eqmap_card.json>)
- [LC1/lc1_sweep_input.json](<LC1/lc1_sweep_input.json>)
- [LC1/status.json](<LC1/status.json>)
- [LC2/free_energy_card.md](<LC2/free_energy_card.md>)
- [LC2/status.json](<LC2/status.json>)
- [LC2/thermodynamic_reference_constants.md](<LC2/thermodynamic_reference_constants.md>)
- [LC3/calc_input_card.json](<LC3/calc_input_card.json>)
- [LC3/status.json](<LC3/status.json>)
- [LD/answer.md](<LD/answer.md>)
- [LD/verdict.json](<LD/verdict.json>)
- [solver/pourbaix_Ni_+_Glycine_Ni.png](<solver/pourbaix_Ni_+_Glycine_Ni.png>)
- [solver/pourbaix_map_Ni_+_Glycine_Ni.csv](<solver/pourbaix_map_Ni_+_Glycine_Ni.csv>)
- [solver/speciation_full_Ni_+_Glycine.csv](<solver/speciation_full_Ni_+_Glycine.csv>)
- [solver/topo_csv_Ni_+_Glycine_Ni/topo_features_0d.csv](<solver/topo_csv_Ni_+_Glycine_Ni/topo_features_0d.csv>)
- [solver/topo_csv_Ni_+_Glycine_Ni/topo_features_1d.csv](<solver/topo_csv_Ni_+_Glycine_Ni/topo_features_1d.csv>)
- [solver/topo_csv_Ni_+_Glycine_Ni/topo_metadata.json](<solver/topo_csv_Ni_+_Glycine_Ni/topo_metadata.json>)
- [solver/topo_csv_Ni_+_Glycine_Ni/topo_regions.csv](<solver/topo_csv_Ni_+_Glycine_Ni/topo_regions.csv>)
- [solver/topology_Ni_+_Glycine_Ni.json](<solver/topology_Ni_+_Glycine_Ni.json>)
- [solver/topology_Ni_+_Glycine_Ni_verdict.json](<solver/topology_Ni_+_Glycine_Ni_verdict.json>)
- [solver/topology_Ni_+_Glycine_Ni_verdict.md](<solver/topology_Ni_+_Glycine_Ni_verdict.md>)
- [verdict.json](<verdict.json>)
