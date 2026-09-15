## Doability
Doable — Ni(II) and glycine are both present in the SRD-46 catalog with the requested aqueous complexes and Ni solid phases, and `pourbaix_sweep` is a supported route.

## Result
- System: Ni (1 mM) + glycine (10 mM), 25 °C, I = 0.1 m, potential vs SHE.
- Method: 2-D `pourbaix_sweep`, pH ∈ [0, 14], E_V ∈ [-1.00, +1.60] V. Coarse grid 66×71; final classified grid ΔpH = 0.0125, ΔE_V = 0.0025 V.
- Convergence: 4686 / 4686 coarse cells converged; refined output 87 833 points . No unconverged cells — all region and boundary claims below rest on fully converged samples.
- Included species (from verdict): Ni²⁺, [Ni(OH)]⁺, [Ni(OH)₂]°, [Ni(OH)₃]⁻, [Ni₄(OH)₄]⁴⁺, [Ni(Glyc)]⁺, [Ni(Glyc)₂]°, [Ni(Glyc)₃]⁻, and solids Ni(OH)₂, Ni₃O₄·2H₂O, Ni₂O₃·H₂O, NiO₂·2H₂O, Ni°.
- Topology: 7 dominant-species labels → 7 connected regions, 10 pairwise boundaries, 4 internal + 8 sweep-limit junctions. No disconnected labels.

## Analysis

### Feature roster (used below)
- `DmsReg_1 {Ni°}` — metal region; corners `DmsRegEqJnc_10`(pH 14, E = -0.7125 V), `DmsRegEqJnc_9`(11.2375, -0.5475 V), `DmsRegEqJnc_4`(7.9125, -0.43 V), `DmsRegEqJnc_5`(6.7625, -0.365 V), `DmsRegEqJnc_6`(6.0625, -0.345 V), `DmsRegEqJnc_7`(0, -0.335 V, sweep limit).
- `DmsReg_7 {Ni²⁺}` — largest region (measure 11.76); bounded by `DmsRegEqJnc_6`(6.0625, -0.345 V) and `DmsRegEqJnc_3`(6.075, 1.6 V, sweep limit) plus the low-pH frame.
- `DmsReg_6 {[Ni(Glyc)]⁺}` — narrow strip; corners `DmsRegEqJnc_5`(6.7625, -0.365 V), `DmsRegEqJnc_6`(6.0625, -0.345 V), `DmsRegEqJnc_2`(6.8, 1.6 V), `DmsRegEqJnc_3`(6.075, 1.6 V).
- `DmsReg_5 {[Ni(Glyc)₂]°}` — corners `DmsRegEqJnc_4`(7.9125, -0.43 V), `DmsRegEqJnc_5`(6.7625, -0.365 V), `DmsRegEqJnc_1`(7.975, 1.6 V), `DmsRegEqJnc_2`(6.8, 1.6 V).
- `DmsReg_4 {[Ni(Glyc)₃]⁻}` — corners `DmsRegEqJnc_9`(11.2375, -0.5475 V), `DmsRegEqJnc_4`(7.9125, -0.43 V), `DmsRegEqJnc_1`(7.975, 1.6 V), `DmsRegEqJnc_8`(11.2375, 1.6 V).
- `DmsReg_2 {Ni(OH)₂(s)}` — high-pH solid; corners `DmsRegEqJnc_10`(14, -0.7125 V), `DmsRegEqJnc_9`(11.2375, -0.5475 V), `DmsRegEqJnc_8`(11.2375, 1.6 V), `DmsRegEqJnc_12`(11.6375, 1.6 V), `DmsRegEqJnc_11`(14, 1.46 V).
- `DmsReg_3 {Ni₂O₃·H₂O(s)}` — small oxidised sliver in the upper-right corner between `DmsRegEqJnc_11`(14, 1.46 V) and `DmsRegEqJnc_12`(11.6375, 1.6 V).
- Boundaries used: `DmsRegEq_3` Ni²⁺|[Ni(Glyc)]⁺ (nearly vertical at pH ≈ 6.06–6.08); `DmsRegEq_2` [Ni(Glyc)]⁺|[Ni(Glyc)₂]° (pH ≈ 6.76–6.80); `DmsRegEq_1` [Ni(Glyc)₂]°|[Ni(Glyc)₃]⁻ (pH ≈ 7.91–7.98); `DmsRegEq_8` Ni(OH)₂|[Ni(Glyc)₃]⁻ (vertical at pH = 11.2375); `DmsRegEq_9` Ni°|Ni(OH)₂ (Nernstian, from (14, -0.7125 V) to (11.2375, -0.5475 V)); `DmsRegEq_10` Ni(OH)₂|Ni₂O₃·H₂O (from (14, 1.46 V) to (11.6375, 1.6 V)).
- Reference lines: pH-line at fixed E_V = 0.30125 V (Ni²⁺ → [Ni(Glyc)]⁺ at pH 6.07–6.08 → [Ni(Glyc)₂]° at 6.79–6.81 → [Ni(Glyc)₃]⁻ at 7.97–7.98 → Ni(OH)₂ at 11.23–11.24); E-line at fixed pH = 6.99 (Ni° up to E ≈ -0.376 V, then [Ni(Glyc)₂]° all the way to +1.599 V).

### Region-by-region reading
**Reduced domain (low E).** Metallic Ni° (`DmsReg_1`) dominates everywhere below a Nernstian floor whose ceiling rises with decreasing pH: at pH 14 the Ni°/Ni(OH)₂ boundary sits at E = -0.7125 V, at pH 11.24 at -0.5475 V, and in the glycinate window it climbs from about -0.43 V (pH 7.91) to -0.345 V (pH 6.06) and stays near -0.335 V down to pH 0. This is the classical Ni²⁺/Ni couple (E°(Ni²⁺/Ni) ≈ -0.25 V vs SHE) shifted to more negative potentials by (i) the 10⁻³ M dilution of the free-ion activity in acid and (ii) glycinate complexation and hydroxide precipitation, which each lower the free Ni²⁺ activity above pH ~6 and thereby stabilise the metal to higher potential — visible as the mild upward tilt of `DmsRegEq_5`/`DmsRegEq_4` between the triple points `DmsRegEqJnc_5` and `DmsRegEqJnc_9`.

**Ni(II) speciation above the metal floor.** In the acidic zone (pH ≲ 6.06) the aqua ion Ni²⁺ (`DmsReg_7`, measure 11.76 — the single largest region) dominates. The Ni²⁺/[Ni(Glyc)]⁺ boundary `DmsRegEq_3` is essentially vertical between (6.0625, -0.345 V) and (6.075, +1.6 V): this is a pure acid–base/complexation switch (formal Ni oxidation state unchanged, so non-redox per the card definition). The chemistry is that glycine's zwitterion loses its ammonium proton with pKa ≈ 9.57 (single-protonation `log_beta` of [HGlycine] in the reference table), so below pH 6 the free-glycinate activity is far too small to compete with hydration despite log β₁ = 5.74 for [Ni(Glyc)]⁺; near pH 6 the product [Gly⁻]·β₁ overtakes water and complexation ignites.

**The Ni-glycinate window.** Between the near-vertical walls `DmsRegEq_3` (pH ≈ 6.07), `DmsRegEq_2` (pH ≈ 6.78) and `DmsRegEq_1` (pH ≈ 7.94), three glycinate complexes stack in order of increasing ligation as pH rises:
- [Ni(Glyc)]⁺ (`DmsReg_6`) between pH ≈ 6.07 and 6.78,
- [Ni(Glyc)₂]° (`DmsReg_5`) between pH ≈ 6.78 and 7.94,
- [Ni(Glyc)₃]⁻ (`DmsReg_4`) between pH ≈ 7.94 and 11.24.

Each stepwise transition (log K₂ = β₂ - β₁ = 4.84; log K₃ = β₃ - β₂ = 3.52 from the reference table) is a non-redox ligand-addition step and the boundaries are correspondingly steep (nearly vertical, with only a tiny Nernstian foot at very negative E where the metal starts to appear). Because all three complexes carry the same Ni(II) formal state, potential barely enters their mutual boundaries — the region walls are pH-driven ligand-binding thresholds, not redox lines. The upper (Ni(OH)₂) wall at pH = 11.2375 (`DmsRegEq_8`, exactly vertical) is where the hydroxide solid finally out-competes even the tris-glycinato complex; at this pH product OH⁻ activity is high enough (pOH ≈ 2.76) that Ni(OH)₂(s) — solubility product log_beta = -11.71 in the reference table — is more stable than any dissolved Ni-glycinate at the imposed 1 mM Ni total.

**Explicit soluble Ni-glycinate predominance window (deliverable).** A soluble Ni-glycinate complex is the dominant Ni species over the compact pH × E band bounded by:
- pH from ≈ 6.06 (Ni²⁺|[Ni(Glyc)]⁺ boundary `DmsRegEq_3`, quoted at 6.0625–6.075) to ≈ 11.24 (Ni(OH)₂|[Ni(Glyc)₃]⁻ boundary `DmsRegEq_8` at 11.2375);
- E from the Ni°/glycinate reductive floor (varying from ≈ -0.345 V at pH 6.06 through -0.365 V at pH 6.76, -0.43 V at pH 7.91, up to -0.5475 V at pH 11.24 — read off `DmsRegEq_7`, `DmsRegEq_5`, `DmsRegEq_4`) upward through the entire remaining water-stability window to the top of the sweep (+1.6 V, sweep-limit junctions `DmsRegEqJnc_1`, `DmsRegEqJnc_2`, `DmsRegEqJnc_3`, `DmsRegEqJnc_8`).

Within this envelope, the dominant glycinate species itself changes with pH: [Ni(Glyc)]⁺ occupies roughly pH 6.06–6.78 (narrow strip, measure 1.42), [Ni(Glyc)₂]° pH 6.78–7.94 (measure 2.35), and [Ni(Glyc)₃]⁻ pH 7.94–11.24 (measure 6.90 — the largest glycinate field, and the piece with the widest pH extent). The centre-E reference line at 0.30125 V reproduces exactly this ladder, confirming the map's topology on the classified grid.

**Oxidising corner.** No dissolved Ni(III/IV) species are included, so above the water oxidation limit at high pH the diagram shows Ni(OH)₂ giving way to the small Ni₂O₃·H₂O(s) sliver (`DmsReg_3`, measure only 0.17) via `DmsRegEq_10` between (14, +1.46 V) and (11.6375, +1.6 V). NiO₂·2H₂O is in the calculation set but does not gain its own field within this sweep box. In practice — beyond the map — these upper-corner fields sit above the O₂/H₂O line and would decompose water; they are correctly identified as thermodynamic majorities under the imposed constraints but are not kinetically accessible in aerated aqueous chemistry.

### Practical takeaway
At 1 mM Ni(II) with a tenfold excess of glycine (10 mM total), glycine sequesters Ni(II) into soluble form over a wide, chemically useful window that spans the full pH range where glycinate is deprotonated enough to bind and Ni²⁺ is not yet forced into Ni(OH)₂: roughly pH 6.1–11.2 across essentially the entire water-oxidation stability range of E. The complexation therefore extends the pH window in which Ni stays dissolved by about 4.6 pH units beyond the Ni²⁺ field (which without ligand would give way to Ni(OH)₂ near pH 8 at 1 mM). This is the range relevant to Ni electroplating baths, catalytic aqueous Ni(II) chemistry, and Ni removal/recovery from complexing waste streams; note that the tris complex [Ni(Glyc)₃]⁻ carries a net negative charge, which matters for ion-exchange or membrane behaviour above pH ≈ 8.

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
- [solver/pourbaix_map_Ni_+_Glycine_Ni.csv](<solver/pourbaix_map_Ni_+_Glycine_Ni.csv>)
- [solver/pourbaix_Ni_+_Glycine_Ni.png](<solver/pourbaix_Ni_+_Glycine_Ni.png>)
- [solver/speciation_full_Ni_+_Glycine.csv](<solver/speciation_full_Ni_+_Glycine.csv>)
- [solver/topo_csv_Ni_+_Glycine_Ni/topo_features_0d.csv](<solver/topo_csv_Ni_+_Glycine_Ni/topo_features_0d.csv>)
- [solver/topo_csv_Ni_+_Glycine_Ni/topo_features_1d.csv](<solver/topo_csv_Ni_+_Glycine_Ni/topo_features_1d.csv>)
- [solver/topo_csv_Ni_+_Glycine_Ni/topo_metadata.json](<solver/topo_csv_Ni_+_Glycine_Ni/topo_metadata.json>)
- [solver/topo_csv_Ni_+_Glycine_Ni/topo_regions.csv](<solver/topo_csv_Ni_+_Glycine_Ni/topo_regions.csv>)
- [solver/topology_Ni_+_Glycine_Ni.json](<solver/topology_Ni_+_Glycine_Ni.json>)
- [solver/topology_Ni_+_Glycine_Ni_verdict.json](<solver/topology_Ni_+_Glycine_Ni_verdict.json>)
- [solver/topology_Ni_+_Glycine_Ni_verdict.md](<solver/topology_Ni_+_Glycine_Ni_verdict.md>)
- [verdict.json](<verdict.json>)
