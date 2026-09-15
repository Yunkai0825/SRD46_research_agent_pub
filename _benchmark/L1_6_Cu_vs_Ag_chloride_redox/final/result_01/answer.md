## Doability
Doable. Cu with chloride background is a well-posed Pourbaix problem for this toolkit; the LC2 free-energy card carries Cu(0), Cu(I)/Cu(II) aqueous species (including Cu(I)–Cl complexes), and the relevant solids (CuCl(s), Cu2O(s), CuO(s), Cu(OH)2(s)). The pipeline executed the pourbaix_sweep once and returned status=ok.

## Result
- System: Cu total = 1 mM; chloride (L1) total = 0.1 M; SHE reference; 25 °C.
- Sweep box: pH ∈ [0, 14], E_V ∈ [-0.5, +1.2] V.
- Final classified-grid spacing: ΔpH = 0.008, ΔE_V = 0.8 mV.
- Convergence coverage (from `solver/speciation_full_Cu_+_Chloride_ion.csv` header): 106 028 refined cells + 5627 coarse-unrefined cells retained; 479 coarse cells were excluded from the refined map — a small fraction (≈0.4 % of the coarse grid), so the reported topology is well-covered.
- 5 dominant-species labels, 5 connected regions, 7 pairwise boundaries, 3 internal junctions (Jnc_2, Jnc_5, Jnc_6) plus 5 sweep-limit junctions.

Dominant-species catalog:
- Dms_1 = Cu(0) (metal)
- Dms_2 = Cu2O(s) (written as [(Cu2O)0.5](s))
- Dms_3 = CuO(s)
- Dms_4 = [CuCl2]- (dissolved Cu(I) chloro-complex)
- Dms_5 = Cu2+

No Cu(OH)2(s), no CuCl(s), and no aqueous Cu+/CuCl/CuCl3^2-/Cu2Cl4^2- ever wins a region under these conditions — they were included in the calculation but out-competed everywhere.
## Analysis

### Layout of the map
Five dominant fields tile the (pH, E_V) window. The catalog (Dms_1..Dms_5) is: Cu(0) metal, cuprite [(Cu2O)0.5](s) (i.e. Cu2O written per‑Cu), tenorite CuO(s), the Cu(I) chloro‑complex [CuCl2]−, and the free Cu2+ aqua ion. Notably absent as a predominant field is CuCl(s): the card includes it (log_beta_dis = +6.73) but it is nowhere dominant at 1 mM Cu / 0.1 M Cl−, because [CuCl2]− is more stable than either Cu+ or CuCl(s) at these activities. No hydrolysed Cu(II) aqueous species and no Cu(OH)2(s) dominates either — CuO is the thermodynamically preferred Cu(II) solid.

### Roster of features bounding the Cu(0) region (DmsReg_1)
- DmsReg_1 {Cu}: measure 6.68 (largest single region after CuO). Corners: DmsRegEqJnc_7 (pH=14, E_V=−0.3492 V, sweep limit), DmsRegEqJnc_5 (pH=6.46, E_V=0.0964 V, triple point Cu | Cu2O | [CuCl2]−), DmsRegEqJnc_3 (pH=0, E_V=0.0964 V, sweep limit). Cu occupies everything below a nearly horizontal ceiling at E_V ≈ +0.096 V from pH 0 to pH 6.46, then a sloped ceiling rising in pH and falling in E_V to (pH=14, −0.349 V).
- DmsRegEq_2 {Cu | [CuCl2]−}: solid–liquid redox curve, flat at E_V = 0.0964 V from pH 0 to pH 6.46. This is the operative Cu(0)/Cu(I) boundary in acidic solution.
- DmsRegEq_6 {Cu | Cu2O}: solid–solid redox curve from (pH=6.46, 0.0964 V) to (pH=14, −0.349 V) — a ~59 mV/pH slope characteristic of a 1 e−/1 H+ couple.
- DmsRegEqJnc_5: triple point where Cu, Cu2O and [CuCl2]− coexist at (pH=6.46, E_V=+0.096 V). This is the acidic‑side terminus of the Cu(0) ceiling.### Constants bounding the Cu(0) region (from the LC2 reference table)

The Cu(0) region is delimited by two half-reactions read from the free-energy card `log_beta` values:

1. **Cu | [Cu(Chlo)2]-** (DmsRegEq_2, flat at E_V ≈ 0.096 V for pH 0–6.46). This is the Cu(I)-chloride reductive dissolution boundary. The card supplies log β = +6.06 for the cumulative formation of [Cu(Chlo)2]- from Cu+ + 2 Cl-, and Cu+/Cu is set by the atlas (log_beta = 0 for Cu+ and Cu(s) written as component references; the effective E° for Cu+/Cu on this convention corresponds to the standard +0.52 V vs SHE). At [Cl-] = 0.1 M and [Cu]_tot = 10⁻³ M, the strong chloride complexation shifts the operative Cu(0)/Cu(I,aq) potential downward by roughly RT/F × log₁₀(β₂·[Cl-]²) ≈ 0.059 × (6.06 − 2) ≈ 0.24 V, giving ~0.28 → 0.096 V. Chemically: chloride stabilises Cu(I) as the soluble [CuCl₂]- complex enough that dissolution of metallic Cu becomes thermodynamically favoured at only ~+0.10 V vs SHE — well within the "mildly oxidising" band.

2. **Cu | [(Cu₂O)0.5](s)** (DmsRegEq_6, sloping from (pH=6.46, E_V=0.096 V) to (pH=14, E_V=−0.349 V)). This is the classical 2 Cu + H₂O ⇌ Cu₂O + 2 H+ + 2 e- couple. The card supplies the dissolution log β = +0.70 for [(Cu₂O)0.5](s) written as Cu+ + H₂O ⇌ ½Cu₂O + H+ (i.e. K_s0 for the ½-formula = 10^+0.70). Combined with Cu+/Cu, this reproduces the expected Nernstian slope of −0.059 V/pH: the boundary drops by (−0.349 − 0.096)/(14 − 6.46) = −0.059 V/pH, exactly the 1 H+/1 e- ratio.### The Cu(0) region at mildly acidic pH and weakly oxidising E

The key qualitative result for the question posed: at pH ~3–5 and E in the 0 to +0.3 V band, Cu(0) is NOT the stable phase — that band lies entirely inside the [Cu(Chlo)2]- field. The reference line along E_V at pH=7 shows Cu(s) yielding to [(Cu2O)0.5](s) at E in [0.0648, 0.0656] V; but at more acidic pH, the Cu / [Cu(Chlo)2]- boundary (DmsRegEq_2) is essentially flat at E = 0.0964 V from pH 0 to pH 6.46. So the copper metal is oxidatively dissolved above ~0.10 V vs SHE across the entire acidic-to-near-neutral pH range, going straight into the anionic Cu(I) dichloro complex rather than into a Cu(II) aqua/hydroxo form.

Mechanistically: 0.1 M Cl− is high enough that log β2 = +6.06 for [CuCl2]- overwhelms the modest Cu+ stability, so the Cu(I) oxidation state is thermodynamically rescued from disproportionation and appears as a wide horizontal slab. The very small pH dependence of DmsRegEq_2 (envelope endpoints identical to within 0.8 mV over 6.46 pH units) confirms this is a pure one-electron oxidation Cu(s) + 2 Cl− ⇌ [CuCl2]- + e−, with no protons exchanged (non-proton-coupled redox, though the card flags it redox by definition).

Practical implication for the stated question: to REDUCE Cu(II)/Cu(I) to Cu(0) in 0.1 M Cl− at pH 3–5, one must reach E below ≈ +0.10 V vs SHE. At E = 0 V, pH 3–5, Cu(0) IS the stable phase (the Cu region extends from E=−0.5 V up to the ≈+0.096 V ceiling).### Practical implications for Cu(0) recovery in mildly acidic chloride

To reduce dissolved Cu (present as [CuCl2]- at pH 3-5, 0.1 M Cl-, 1 mM Cu) to Cu metal, the applied potential must be driven below the Cu | [CuCl2]- line at E_V = +0.0964 V vs SHE. This is the deterministic result the solver used: the Cu(I) chloride complex, not free Cu+ or Cu2O, is the aqueous form that has to be discharged. The window is wide in pH (0 to ~6.46) but narrow in potential: only ~30 mV of overpotential separates the Cu | [CuCl2]- line at +0.0964 V from the [CuCl2]- | Cu2+ line at +0.3804 V that bounds the aqueous Cu(I) field from above. At mildly oxidising potentials in the 0 to +0.3 V window requested:

- E ~ 0 V, pH 3-5: on the Cu (metal) side of the DmsRegEq_2 line — copper deposits / does not corrode.
- E ~ +0.1 V, pH 3-5: sits at or just above the Cu | [CuCl2]- line — copper dissolves as [CuCl2]-. This is the classical chloride-assisted corrosion of copper.
- E ~ +0.3 V, pH 3-5: still in the [CuCl2]- field; oxidation to Cu(II) (Cu2+) requires crossing +0.3804 V.

At higher pH (>~6.46), CuCl aqueous complexation loses out to hydroxide/oxide chemistry and Cu2O then CuO precipitate; the Cu(0) upper bound in the alkaline branch runs from (pH=14, E_V=-0.3492 V) to (pH=6.46, E_V=+0.0964 V), a classic Nernstian slope for the 2 Cu + H2O -> Cu2O + 2H+ + 2e- couple.

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
