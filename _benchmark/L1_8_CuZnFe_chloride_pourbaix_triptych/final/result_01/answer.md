## Doability
Doable — Cu with chloride and hydroxide ligands is well represented in SRD-46; pourbaix_sweep is the appropriate method for the requested E–pH map.

## Result
- System: Cu (total 1 mM) + Cl⁻ (total 0.1 M) at 25 °C, I ≈ 0.1 m, potentials vs SHE.
- Method: `pourbaix_sweep` over pH∈[0,14], E∈[−1.0,+1.5] V; final classified grid ΔpH=0.008, ΔE=0.002 V.
- Convergence: coarse pass 3249 unrefined cells + 85 649 refined cells; the CSV header lists `n_coarse_excluded: 372` (cells decomposed and replaced by refined subcells — not unconverged evidence) and every inspected row carries `converged=1`. All 15 aqueous species and the 3 stable solids (Cu, Cu₂O, CuO) participate.
- Topology: 5 dominant-species regions, 7 boundary curves, 8 junctions (3 internal, 5 at sweep limits); no disconnected regions.

### Feature roster
- `DmsReg_1 {Cu}` (metal): frame-limit junctions `DmsRegEqJnc_7` (pH 14, E=−0.349 V), `DmsRegEqJnc_5` (pH 6.46, E=+0.097 V, triple with Cu₂O and CuCl₂⁻), `DmsRegEqJnc_3` (pH 0, E=+0.097 V). Extent: pH 0–14 with an upper E-cap that rises from −0.349 V at pH 14 to +0.097 V for pH ≤ 6.46.
- `DmsReg_2 {Cu₂O(s)}`: bounded by `DmsRegEqJnc_7`, `DmsRegEqJnc_5`, `DmsRegEqJnc_6` (pH 6.468, E=+0.277 V, triple with CuO and CuCl₂⁻), `DmsRegEqJnc_8` (pH 14, E=−0.169 V). A narrow wedge between Cu and CuO for pH ≳ 6.46.
- `DmsReg_3 {CuO(s)}`: corners `DmsRegEqJnc_6`, `DmsRegEqJnc_8`, `DmsRegEqJnc_2` (pH 5.74, E=+0.381 V, triple with CuCl₂⁻ and Cu²⁺), `DmsRegEqJnc_4` (pH 5.596, E=+1.5 V, sweep limit). Dominates the oxidising, near-neutral to alkaline zone.
- `DmsReg_4 {[CuCl₂]⁻}`: corners `DmsRegEqJnc_3`, `DmsRegEqJnc_5`, `DmsRegEqJnc_6`, `DmsRegEqJnc_2`, `DmsRegEqJnc_1` (pH 0, E=+0.381 V). A quasi-rectangular Cu(I) solubility window: pH 0 to ≈5.7–6.47, E ≈ +0.097 to +0.381 V.
- `DmsReg_5 {Cu²⁺}`: corners `DmsRegEqJnc_1`, `DmsRegEqJnc_2`, `DmsRegEqJnc_4`. Acidic-oxidising wedge pH 0 to ≈5.6, E above +0.381 V.
- Reference lines: at E=+0.25 V the pH line shows CuCl₂⁻ (pH 0–6.464) → Cu₂O (6.472–6.92) → CuO (6.928–14); at pH 7 the E line shows Cu (E ≤ +0.064 V) → Cu₂O (+0.066 to +0.244 V) → CuO (+0.246 to +1.5 V).

## Analysis
**Overall map.** Copper in 0.1 M chloride at 1 mM total organises into five predominance fields: metallic Cu at low E across the whole pH range, a thin Cu₂O(s) band above it in near-neutral to alkaline conditions, CuO(s) as the oxidised solid at pH ≳ 5.6, a Cu(I)–chloro-complex `[CuCl₂]⁻` pool in acid at intermediate potentials, and the Cu²⁺ aqua ion in the acidic-oxidising corner. Note that although CuCl(s) (nantokite, log K_sp cited below) and Cu(OH)₂(s) are in the calculation, neither wins any grid cell at these totals — CuCl(s) is undersaturated because [Cl⁻]=0.1 M with only ~10⁻³ M Cu(I) keeps IAP below K_sp (see below), and Cu(OH)₂ is metastable versus CuO in this card.

**Cu(I)–chloro window.** `DmsReg_4 {[CuCl₂]⁻}` — the *only* soluble chloro-complex that becomes a majority species — occupies the box bounded by `DmsRegEqJnc_3` (pH 0, +0.097 V), `DmsRegEqJnc_1` (pH 0, +0.381 V), `DmsRegEqJnc_2` (pH 5.74, +0.381 V) and `DmsRegEqJnc_5`/`DmsRegEqJnc_6` (pH ≈6.46–6.47, +0.097 to +0.277 V). Its lower edge `DmsRegEq_2` (Cu | CuCl₂⁻) is essentially horizontal at E≈+0.097 V from pH 0 to 6.46: this is the Cu(0)/Cu(I) couple stabilised by chloride complexation, well below the +0.52 V of the bare Cu⁺/Cu couple because β₂([CuCl₂]⁻)=10⁶·⁰⁶ pulls the Cu(I) activity down by ~6 log units at [Cl⁻]=0.1 M. Its upper edge `DmsRegEq_1` (CuCl₂⁻ | Cu²⁺) sits at E≈+0.381 V from pH 0 to 5.74, i.e. the Cu(II)/Cu(I)-chloride couple, again depressed relative to the +0.153 V Cu²⁺/Cu⁺ standard couple only in the sense that chloride raises Cu(I) stability. In this system the higher chloro-cuprates [CuCl₃]²⁻ (log β₃=+5.39), [Cu₂Cl₄]²⁻ (log β=+13.0) and neutral CuCl (log β₁=+3.10) never dominate because at [Cl⁻]=0.1 M their higher-order Cl dependences make [CuCl₂]⁻ the winning stoichiometry. The Cu(II)–chloride complex [CuCl]⁺ (log β₁=+0.20) is far too weak to compete with free Cu²⁺.

**First hydroxide/oxide solid along E=+0.2 V.** The E=+0.25 V reference line brackets the CuCl₂⁻ → Cu₂O transition between pH 6.464 and 6.472. The E=+0.2 V horizontal is not printed directly, but the geometry of `DmsRegEq_4` (Cu₂O | CuCl₂⁻), a nearly vertical curve running from (pH 6.46, +0.097 V) up to (pH 6.468, +0.277 V), pins the CuCl₂⁻ → Cu₂O(s) crossover to **pH ≈ 6.46–6.47** at any E in that segment, including +0.2 V. Cu(I) oxide is therefore the first Cu solid to appear on the +0.2 V isopotential. Cu(II) oxide CuO(s) does not appear on E=+0.2 V (that line crosses Cu | Cu₂O first at low E, then Cu₂O | CuO at pH 14 near −0.169 V — CuO takes over above the Cu₂O wedge at higher E, entering the line only above E≈+0.246 V at pH 7, per the E-reference cut). Chemically, this is hydrolytic precipitation: as pH rises, OH⁻ activity climbs enough for Cu(I) to condense as Cu₂O rather than remain as [CuCl₂]⁻ (the reaction 2 [CuCl₂]⁻ + H₂O ⇌ Cu₂O(s) + 4 Cl⁻ + 2 H⁺).

**Cu²⁺ / CuO frontier.** `DmsRegEq_5` (CuO | Cu²⁺) descends from (pH 5.596, +1.5 V) to (pH 5.74, +0.381 V) — a nearly vertical acid–base line: Cu²⁺ + H₂O ⇌ CuO(s) + 2 H⁺ with card log K_sp(CuO) implying precipitation at pH ≈ 5.6 for [Cu²⁺]_tot ≈ 1 mM. Above +0.381 V the line is straight-vertical (pure acid–base); below, it tilts toward higher pH as it merges into the Cu(I) fields at the triple point `DmsRegEqJnc_2` (pH 5.74, +0.381 V). At pH 7 (E-reference line) CuO takes over from Cu₂O at +0.246 V, i.e. the Cu(I)/Cu(II) oxide couple: Cu₂O + H₂O ⇌ 2 CuO + 2 H⁺ + 2 e⁻.

**Constants actually used (from `LC2/thermodynamic_reference_constants.md`).** All values are LC2 log β from free components (Cu⁺, Cu²⁺, Cl⁻, OH⁻; H⁺ implicit) at I=0.1 m.
- Cu(I)–chloride complexes (β from Cu⁺ + n Cl⁻): log β₁(CuCl°) = +3.10; log β₂([CuCl₂]⁻) = +6.06; log β₃([CuCl₃]²⁻) = +5.39; log β([Cu₂Cl₄]²⁻) = +13.00.
- Cu(II)–chloride: log β₁([CuCl]⁺) = +0.20.
- Cu(II) hydrolysis (β from Cu²⁺ + n OH⁻): log β₁([CuOH]⁺) = −7.90; log β₂,₂([Cu₂(OH)₂]²⁺) = −11.20; log β₂([Cu(OH)₂]°) = −16.20; log β₄,₃([Cu₃(OH)₄]²⁺) = −22.50; and the H-basis rows [HCuO₂]⁻ log β = −26.7048 and [CuO₂]²⁻ log β = −39.8410 (Atlas source).
- Solids (dissolution log K as written in the card): Cu(0) log K = 0 (metal reference); Cu₂O written as ½Cu₂O ⇌ Cu⁺ + OH⁻ − H⁺ with log K = +0.70; CuCl(s) (nantokite) Cu⁺ + Cl⁻ ⇌ CuCl(s) with log K = +6.73; CuO(s) with Cu²⁺:+1, H:−2 basis log K = −7.65; Cu(OH)₂(s) with Cu²⁺ + 2 OH⁻ log K = −8.68.
- Water: log K_w-style row `[H][OH]` = −0.22 (activity-corrected auto-ionisation at I=0.1 m).

**Practical read-out.** In 0.1 M chloride, the corrosion-relevant Cu(I) solubility window `[CuCl₂]⁻` extends from pH 0 up to ~6.46 and from ~+0.10 V up to ~+0.38 V (SHE). Above ~+0.38 V and below pH ~5.6 copper mobilises as Cu²⁺; at pH ≳ 6.5 with modest oxidation potential the metal passivates first as Cu₂O and then as CuO. Along the +0.2 V isopotential, precipitation of the first Cu solid (Cu₂O) occurs at pH ≈ 6.46 — a lower pH than the Cl-free case would predict, because chloride stabilises Cu(I) into a solubility window that reaches this near-neutral onset.

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
- [solver/pourbaix_Cu_+_Chloride_ion_Cu.png](<solver/pourbaix_Cu_+_Chloride_ion_Cu.png>)
- [solver/pourbaix_map_Cu_+_Chloride_ion_Cu.csv](<solver/pourbaix_map_Cu_+_Chloride_ion_Cu.csv>)
- [solver/speciation_full_Cu_+_Chloride_ion.csv](<solver/speciation_full_Cu_+_Chloride_ion.csv>)
- [solver/topo_csv_Cu_+_Chloride_ion_Cu/topo_features_0d.csv](<solver/topo_csv_Cu_+_Chloride_ion_Cu/topo_features_0d.csv>)
- [solver/topo_csv_Cu_+_Chloride_ion_Cu/topo_features_1d.csv](<solver/topo_csv_Cu_+_Chloride_ion_Cu/topo_features_1d.csv>)
- [solver/topo_csv_Cu_+_Chloride_ion_Cu/topo_metadata.json](<solver/topo_csv_Cu_+_Chloride_ion_Cu/topo_metadata.json>)
- [solver/topo_csv_Cu_+_Chloride_ion_Cu/topo_regions.csv](<solver/topo_csv_Cu_+_Chloride_ion_Cu/topo_regions.csv>)
- [solver/topology_Cu_+_Chloride_ion_Cu.json](<solver/topology_Cu_+_Chloride_ion_Cu.json>)
- [solver/topology_Cu_+_Chloride_ion_Cu_verdict.json](<solver/topology_Cu_+_Chloride_ion_Cu_verdict.json>)
- [solver/topology_Cu_+_Chloride_ion_Cu_verdict.md](<solver/topology_Cu_+_Chloride_ion_Cu_verdict.md>)
- [verdict.json](<verdict.json>)
