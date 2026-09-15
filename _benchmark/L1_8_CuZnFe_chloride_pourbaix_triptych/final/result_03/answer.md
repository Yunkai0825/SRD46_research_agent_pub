## Doability
Doable. Fe (with Fe(II) and Fe(III) redox states) and chloride are both in SRD-46 with hydrolysis, chloro-complex, and iron-solid data, and a two-axis pH×E Pourbaix sweep is directly supported.

## Result
- System: Fe = 1.0 mM total, Chloride ion = 0.1 M total, SHE reference, T = 25 °C, I = 0.1 m.
- Method: `pourbaix_sweep` over pH ∈ [0, 14], E_V ∈ [-1.0, +1.5] V.
- Final classified grid: ΔpH = 0.0125, ΔE = 0.003125 V (1120 × 800 cells).
- Convergence (from map/speciation headers): 0 fixer marks on the classified label map; 81 235 refined cells all converged (`converged=1`); 3042 coarse cells retained also converged. Coverage is complete — no unconverged evidence discarded.
- All Fe chloro-complexes available in SRD-46 were *included* in the calculation: [Fe(Chlo)]+ (Fe(II), log β = −0.20), [Fe(Chlo)]2+ (Fe(III), log β = +0.78), [Fe(Chlo)2]+ (Fe(III), log β = +2.13). No FeCl3, FeCl4−, or FeCl4²− is present in the SRD-46 card projected here.

## Analysis

### Topology (dominant species catalog and regions)
Seven dominant species emerge (7 labels, 7 connected regions, 10 pairwise boundaries, 4 internal triple points, 8 sweep-limit junctions):

- Solids: **Fe(0)** (DmsReg_1), **Fe3O4** (DmsReg_2), **α-Fe2O3/hematite** projection `[(Fe2O3)0.5(s,α)]` (DmsReg_3, the largest region, solver-frame measure 13.2).
- Aqueous: **Fe²⁺** (DmsReg_5, measure 6.11), **FeO4²⁻** ferrate (DmsReg_6, measure 7.23), **Fe³⁺** (DmsReg_7, small wedge, measure 0.81), and a thin high-pH/reducing sliver of **[Fe(OH)3]⁻** (DmsReg_4, measure 0.028).

Feature roster used below (all coordinates in (pH, E_V/V)):
- DmsRegEqJnc_1 {Fe²⁺, Fe³⁺}: (0, +0.7719) — at sweep limit (left edge).
- DmsRegEqJnc_2 {Fe²⁺, Fe³⁺, hematite}: (1.1875, +0.7719) — internal triple point.
- DmsRegEqJnc_4 {Fe(0), Fe²⁺}: (0, −0.5375) — sweep limit.
- DmsRegEqJnc_10 {Fe(0), Fe3O4, Fe²⁺}: (7.8375, −0.5375) — internal triple.
- DmsRegEqJnc_11 {Fe3O4, hematite, Fe²⁺}: (6.0375, −0.1062) — internal triple.
- DmsRegEqJnc_12 {Fe3O4, hematite}: (14, −0.5781) — sweep limit.
- DmsRegEqJnc_9 {Fe(0), [Fe(OH)3]⁻, Fe3O4}: (13.3125, −0.8594) — internal triple.
- DmsRegEqJnc_3 {Fe(0), [Fe(OH)3]⁻}: (14, −0.9219) — sweep limit.
- DmsRegEqJnc_6 {hematite, FeO4²⁻}: (14, +0.3063), DmsRegEqJnc_7 {hematite, FeO4²⁻}: (1.9125, +1.5), DmsRegEqJnc_8 {hematite, Fe³⁺}: (1.1125, +1.5) — sweep limits.
- DmsRegEq_3 {Fe(0)|Fe²⁺}: flat at E = −0.5375 V, spanning pH 0 → 7.8375 (redox, oxidation state 0→+II).
- DmsRegEq_1 {Fe²⁺|Fe³⁺}: flat at E = +0.7719 V, pH 0 → 1.1875 (redox, +II→+III).
- DmsRegEq_4 {hematite|Fe²⁺}: slopes down from (1.1875, +0.7719) through (1.6125, +0.675), (1.4, +0.7156) and back to (6.0375, −0.1062) — redox (Fe(III) solid ↔ Fe(II) aq), leans with pH as expected for a proton-coupled couple.
- DmsRegEq_6 {hematite|Fe³⁺}: nearly vertical from (1.1875, +0.7719) up through (1.1125, +1.5) — non-redox dissolution of hematite to Fe³⁺, hence essentially a pH boundary at pH ≈ 1.11–1.19.
- DmsRegEq_5 {hematite|FeO4²⁻}: tilts from (14, +0.3063) up to (1.9125, +1.5) — redox (+III → +VI), strongly proton-coupled.
- DmsRegEq_10 {Fe3O4|hematite}: from (14, −0.5781) up to (6.0375, −0.1062) — the mixed→ferric-oxide redox transition.

### Are there soluble chloro-complex predominance windows?
**No.** Despite 0.1 M Cl⁻ (100× the total iron), none of the Fe–chloride complexes appears as a dominant-species label anywhere on the map. This is the direct thermodynamic consequence of the SRD-46 constants that were actually used (from `LC2/thermodynamic_reference_constants.md`):

- Fe(II): log β([FeCl]⁺) = −0.20 — negative; even at [Cl⁻] = 0.1 M this gives [FeCl⁺]/[Fe²⁺] ≈ 10^(−0.20) · 0.1 ≈ 0.063, so FeCl⁺ never overtakes free Fe²⁺.
- Fe(III): log β1 = +0.78 ([FeCl]²⁺), log β2 = +2.13 ([FeCl2]⁺). Ratios at 0.1 M Cl⁻: [FeCl²⁺]/[Fe³⁺] ≈ 10^0.78·0.1 ≈ 0.60; [FeCl2⁺]/[Fe³⁺] ≈ 10^2.13·0.01 ≈ 1.3. So Fe–Cl(III) complexes are of the *same order* as Fe³⁺ in the Fe³⁺ wedge but never individually dominant, and this wedge itself is small (pH < ~1.1, E > +0.77 V). Higher chlorides (FeCl3, FeCl4⁻) are simply not in the SRD-46 catalog used and cannot appear.

Practically, at 0.1 M Cl⁻ the chloride medium slightly stabilises Fe(III) in solution and marginally lowers the free Fe³⁺ activity, but the Fe(III) wedge is still narrow because hematite is thermodynamically favoured above pH ≈ 1.11 in this projection.

### First iron solid along the horizontal line E = +0.20 V vs SHE
The reference line at E_V = +0.2484 V (grid sample nearest E = +0.20 V) shows:
- pH 0.006 – 4.019: **Fe²⁺** (aq).
- pH 4.031 – 13.994: **α-Fe2O3** (hematite projection).
- Label change bracketed by adjacent samples at pH ∈ [4.019, 4.031].

So on the E = +0.2 V isopotential the first iron solid to appear is the ferric oxide **α-Fe2O3** at pH ≈ **4.02–4.03**. No Fe(OH)3(s) predominance window occurs because that solid was excluded by the model selection (Fe(OH)3(s) and Fe2O3(anh.) are in the "excluded" list of the calculation species roster), and FeOOH(s,α), although included with log K(dissolution) = −0.50, never wins over hematite (log K = +0.70 for the (Fe2O3)0.5 projection — a more negative dissolution constant would be needed to displace it). Fe3O4 does not appear along this line because +0.2 V is well above the Fe3O4|Fe2O3 boundary (which lies at E ≲ −0.11 V for pH ≳ 6).

### Constants the solver actually used (from `LC2/thermodynamic_reference_constants.md`)
Cumulative formation constants log β (aqueous, from free components; SRD-46 unless noted):

- Fe(II) hydrolysis: [Fe(OH)]⁺ −9.80; [Fe(OH)2]⁰ −35.50; [Fe(OH)3]⁻ −29.00; [Fe(OH)4]²⁻ −46.00.
- Fe(III) hydrolysis: [Fe(OH)]²⁺ −2.73; [Fe2(OH)2]⁴⁺ −2.86; [Fe(OH)2]⁺ −4.60; [Fe3(OH)4]⁵⁺ −6.30; [Fe(OH)4]⁻ −21.60.
- Fe–Cl: [Fe(Chlo)]⁺ (Fe(II)) −0.20; [Fe(Chlo)]²⁺ (Fe(III)) +0.78; [Fe(Chlo)2]⁺ (Fe(III)) +2.13.
- FeO4²⁻ (Fe(VI)): log β = 0.0000 (Atlas placeholder for the ferrate reference).
- Water: [H][OH] log β = −0.22 (this is the projected value for the H⁺+OH⁻ product row on this card; not pKw = 14 — it is the row's own convention, not renamed here).

Solid dissolution constants (log K_diss, listed as `log_beta` on dissolution rows):
- [Fe(OH)2](s) −13.57 (SRD-46).
- Fe3O4 (anhydrous, Atlas): −7.1252 (per one Fe(II)·Fe2(III)·(OH)8 formula unit, stoich Fe²⁺:1, Fe³⁺:2, H:−8).
- [(Fe2O3)0.5(s,α)] hematite projection: +0.70 (per ½Fe2O3, Fe³⁺:1, H:−3).
- [FeO(OH)(s,α)] α-FeOOH goethite projection: −0.50 (Fe³⁺:1, H:−3).
- Fe(0): 0.0 (Atlas reference).

Note the report's `logβ = −0.22` for the H·OH row and the hematite row's positive +0.70 are the exact card entries as printed; naming them pKw or a solubility product would require the row's own reaction definition to support that name, so they are left as-is.

### Caveats
- Two solid–liquid boundaries (DmsRegEq_7 Fe3O4|[Fe(OH)3]⁻, DmsRegEq_8 Fe3O4|Fe²⁺) and DmsRegEq_9 (Fe|Fe3O4) are printed under `redox unresolved` — the solver could not parse the card's oxidation-state attribute for one side. Cross-checking the card: Fe3O4 is a mixed-valent Fe(II)/Fe(III) oxide, [Fe(OH)3]⁻ is Fe(II), so DmsRegEq_7 is a genuine mixed-valent (partial) redox transition; DmsRegEq_8 (Fe3O4↔Fe²⁺) is also partially redox (average +8/3 → +2); DmsRegEq_9 (Fe⁰↔Fe3O4) is clearly redox. Their geometry is trustworthy; only the auto-classification of the "redox" tag failed.
- The hematite projection `[(Fe2O3)0.5(s,α)]` (Atlas-normalised per one Fe) is the ferric oxide phase that wins throughout the ferric-oxide field; FeOOH(s,α) is present in the model but never predominates at 1 mM Fe.
- No Fe(OH)2(s) region appears; along pH ~ 7 the Fe(II)|Fe3O4 boundary at E ≈ −0.16 V (from the E-axis reference line at pH 6.99) preempts any Fe(OH)2 window at this total Fe.
- Chloride does not create a chloro-complex predominance region at [Cl⁻] = 0.1 M; higher chloride (seawater 0.5 M, brines ≥1 M) or lower pH would be needed, and the missing FeCl3⁰ / FeCl4⁻ species in the card would need to be added to see the classic ferric-chloride-brine complexation.

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
- [solver/pourbaix_Fe_+_Chloride_ion_Fe.png](<solver/pourbaix_Fe_+_Chloride_ion_Fe.png>)
- [solver/pourbaix_map_Fe_+_Chloride_ion_Fe.csv](<solver/pourbaix_map_Fe_+_Chloride_ion_Fe.csv>)
- [solver/speciation_full_Fe_+_Chloride_ion.csv](<solver/speciation_full_Fe_+_Chloride_ion.csv>)
- [solver/topo_csv_Fe_+_Chloride_ion_Fe/topo_features_0d.csv](<solver/topo_csv_Fe_+_Chloride_ion_Fe/topo_features_0d.csv>)
- [solver/topo_csv_Fe_+_Chloride_ion_Fe/topo_features_1d.csv](<solver/topo_csv_Fe_+_Chloride_ion_Fe/topo_features_1d.csv>)
- [solver/topo_csv_Fe_+_Chloride_ion_Fe/topo_metadata.json](<solver/topo_csv_Fe_+_Chloride_ion_Fe/topo_metadata.json>)
- [solver/topo_csv_Fe_+_Chloride_ion_Fe/topo_regions.csv](<solver/topo_csv_Fe_+_Chloride_ion_Fe/topo_regions.csv>)
- [solver/topology_Fe_+_Chloride_ion_Fe.json](<solver/topology_Fe_+_Chloride_ion_Fe.json>)
- [solver/topology_Fe_+_Chloride_ion_Fe_verdict.json](<solver/topology_Fe_+_Chloride_ion_Fe_verdict.json>)
- [solver/topology_Fe_+_Chloride_ion_Fe_verdict.md](<solver/topology_Fe_+_Chloride_ion_Fe_verdict.md>)
- [verdict.json](<verdict.json>)
