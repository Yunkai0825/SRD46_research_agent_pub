## Doability
Doable: Zn + Cl⁻ Pourbaix sweep over pH 0–14, E −1.5…+1.5 V vs SHE at 1 mM Zn(tot), 0.1 M Cl⁻(tot). Ran successfully via `pourbaix_sweep`.

## Result
- System: Zn (0.001 M) + Chloride ion (0.1 M), 25 °C, I = 0.1 m implicit in the SRD-46/Atlas selection.
- Method: `pourbaix_sweep`, SHE reference; final classified grid ΔpH = 0.0125, ΔE = 0.003125 V.
- Included Zn species (from the LC2 card projection): Zn²⁺, ZnOH⁺, Zn(OH)₂(aq), Zn(OH)₃⁻, Zn(OH)₄²⁻, ZnCl⁺, ZnCl₂(aq), ZnO (inactive), Zn(OH)₂(α), Zn(s). No higher chloro-complexes (ZnCl₃⁻, ZnCl₄²⁻) were retained by the eq-card alignment against SRD-46, so those fields cannot appear here by construction.
- Convergence: 3967 coarse + 53035 refined cells recorded; 364 coarse cells excluded (~0.6 %). Inspected rows all show `converged=1` with residuals ~2×10⁻¹¹, so the classified grid is trustworthy evidence.
- Topology stats: 4 dominant-species labels, 4 regions, 5 boundary curves, 2 internal triple junctions, 4 sweep-limit junctions.

### Feature roster (used below)
- **DmsReg_1 {Zn(s)}** — metal field; corners `DmsRegEqJnc_1 (pH 14, E −1.331 V)`, `DmsRegEqJnc_5 (pH 13.463, E −1.269 V)`, `DmsRegEqJnc_6 (pH 6.588, E −0.863 V)`, `DmsRegEqJnc_2 (pH 0, E −0.863 V)`.
- **DmsReg_4 {Zn²⁺(aq)}** — acidic soluble field; corners `DmsRegEqJnc_2`, `DmsRegEqJnc_6`, `DmsRegEqJnc_4 (pH 6.588, E 1.5 V)` — lower-right box of the map.
- **DmsReg_2 {ZnO (inactive)}** — largest region; corners `DmsRegEqJnc_6`, `DmsRegEqJnc_5`, `DmsRegEqJnc_3 (pH 13.463, E 1.5 V)`, `DmsRegEqJnc_4`.
- **DmsReg_3 {[Zn(OH)₄]²⁻(aq)}** — strongly alkaline soluble field; corners `DmsRegEqJnc_1`, `DmsRegEqJnc_5`, `DmsRegEqJnc_3`.
- **DmsRegEq_2** Zn|Zn²⁺: horizontal line at E = −0.8625 V from pH 0 to 6.588 (redox, no protons — pure Zn²⁺+2e⁻⇌Zn).
- **DmsRegEq_5** Zn|ZnO: sloped from (13.463, −1.269 V) to (6.588, −0.863 V) — redox with protons.
- **DmsRegEq_1** Zn|[Zn(OH)₄]²⁻: (14, −1.331 V) → (13.463, −1.269 V) — redox with hydroxide.
- **DmsRegEq_4** ZnO|Zn²⁺: vertical at pH 6.5875 from E −0.863 V up to +1.5 V — non-redox (both are Zn(II)); dissolution/hydrolysis boundary.
- **DmsRegEq_3** ZnO|[Zn(OH)₄]²⁻: vertical at pH 13.4625 from E −1.269 V up to +1.5 V — non-redox amphoteric dissolution.
- Reference line along pH at E = −0.0016 V (near map center): Zn²⁺ from pH 0.006–6.581 → ZnO(inactive) from 6.594–13.456 → [Zn(OH)₄]²⁻ from 13.469–13.994; transitions bracketed at [6.581, 6.594] and [13.456, 13.469].
- Reference line along E at pH 6.994: Zn(s) from −1.498 to −0.886 V → ZnO(inactive) up to +1.498 V; transition bracketed at [−0.886, −0.883] V.
## Analysis

**Global topology.** Only four predominance fields appear: metallic Zn at the bottom-left (reducing/acidic-to-alkaline), an acidic Zn²⁺(aq) window, a very broad ZnO(inactive) region occupying most of the oxidised half of the map, and a narrow alkaline [Zn(OH)₄]²⁻(aq) sliver above pH ≈ 13.46. The two internal triple points `DmsRegEqJnc_6 (pH 6.588, E −0.863 V)` and `DmsRegEqJnc_5 (pH 13.463, E −1.269 V)` are the classic Zn–Pourbaix nodes where the Zn(0)/Zn(II) couple meets the two Zn(II) dissolution equilibria on the acid and alkaline sides of ZnO.

**No chloro-complex fields.** ZnCl⁺ and ZnCl₂(aq) were included in the calculation but never win a cell. The reason is straight from the card: `log β₁(ZnCl⁺) = +0.4` and `log β₂(ZnCl₂) = +0.6` (SRD-46). At [Cl⁻] = 0.1 M this gives fractional occupancies of order 10^(0.4)·0.1 ≈ 0.25 for ZnCl⁺ and 10^(0.6)·0.01 ≈ 0.04 for ZnCl₂ relative to Zn²⁺, so Zn²⁺ remains the dominant Zn(II) form throughout the acid field even in 0.1 M chloride. ZnCl₃⁻ and ZnCl₄²⁻ are not in the retained species list (they were dropped during eq-card alignment against SRD-46), so this map cannot report on them — a study aiming at those tetrahedral complexes would need much higher [Cl⁻] (multi-molar brines) and an expanded eq-card selection.

**Boundaries and their chemistry.**
- `DmsRegEq_2 (Zn|Zn²⁺)` is flat at E = −0.8625 V because it is the pure Zn²⁺ + 2 e⁻ ⇌ Zn(s) couple: no H⁺ or OH⁻ is exchanged, so pH does not shift it. At [Zn²⁺] = 10⁻³ M and E° = −0.7626 V (SHE), Nernst gives E = −0.7626 + (0.0592/2)·log(10⁻³) = −0.851 V, in agreement with the mapped −0.863 V (small offset from activity treatment and weak side-equilibria).
- `DmsRegEq_4 (ZnO|Zn²⁺)` is vertical at pH 6.5875 because both sides are Zn(II) — it is the acid-side dissolution ZnO(s) + 2 H⁺ ⇌ Zn²⁺ + H₂O. With the card's ZnO(inactive) `log K = −9.6132` and [Zn²⁺] = 10⁻³ M: pH ≈ ½·(9.61 + 3) = 6.31, close to the mapped 6.59; residual difference from included aqueous hydroxo speciation and activity corrections.
- `DmsRegEq_3 ([Zn(OH)₄]²⁻|ZnO)` is vertical at pH 13.4625 — the amphoteric alkaline dissolution ZnO(s) + H₂O + 2 OH⁻ ⇌ Zn(OH)₄²⁻. Combining `log β₄ = −40.5` with ZnO `log K = −9.6132` and the card's Kw gives redissolution near pH ≈ 13.4 at [Zn(II)] = 10⁻³ M, matching the map.
- `DmsRegEq_5 (Zn|ZnO)` slopes with pH because it exchanges electrons and protons (ZnO + 2 H⁺ + 2 e⁻ ⇌ Zn + H₂O); measured slope from (6.588, −0.863 V) to (13.463, −1.269 V) is ΔE/ΔpH = −0.406/6.875 ≈ −0.059 V/pH — the textbook 2 e⁻/2 H⁺ Nernst slope. `DmsRegEq_1 (Zn|[Zn(OH)₄]²⁻)` is redox with hydroxide transfer and appears only at the extreme alkaline corner.

- `DmsRegEq_3 ([Zn(OH)₄]²⁻|ZnO)` is vertical at pH 13.4625 — the amphoteric alkaline dissolution ZnO(s) + H₂O + 2 OH⁻ ⇌ Zn(OH)₄²⁻. Combining the card's `log β₄ = −40.5` for Zn²⁺+4 OH⁻ ⇌ Zn(OH)₄²⁻ with ZnO dissolution `log K = −9.6132` and Kw (`log Kw = −14.22` from the card row [H][OH]) gives an alkaline redissolution near pH ≈ 13.4 for [Zn(II)] = 10⁻³ M, matching the map.
- `DmsRegEq_5 (Zn|ZnO)` slopes with pH because it exchanges electrons *and* protons (ZnO + 2 H⁺ + 2 e⁻ ⇌ Zn + H₂O); its measured slope from (pH 6.588, −0.863 V) to (pH 13.463, −1.269 V) is ΔE/ΔpH = −0.406/6.875 ≈ −0.059 V/pH, i.e. the textbook two-electron/two-proton Nernst slope. Likewise `DmsRegEq_1 (Zn|[Zn(OH)₄]²⁻)` is redox with hydroxide transfer and appears only at the extreme alkaline corner.

**First hydroxide/oxide precipitation along E = +0.2 V.** The reference-line cut nearest the map center at E = −0.0016 V already places the Zn²⁺→ZnO transition in the bracket pH ∈ [6.5813, 6.5938]. Since the entire ZnO|Zn²⁺ boundary is the vertical, non-redox line `DmsRegEq_4` at pH 6.5875 (compact polyline from E = −0.863 V straight up to E = +1.5 V), the crossing at any E within [−0.863 V, +1.5 V] — including the requested E = +0.2 V — occurs at the same pH ≈ 6.59 (grid-resolved to ±0.0125). So along E = +0.2 V vs SHE the first Zn solid encountered on raising pH from 0 is **ZnO (inactive)**, appearing at pH ≈ 6.59. Zn(OH)₂(α) is retained in the card (`log K_sp = −10.72`, more soluble than ZnO by ≈1.1 log units) but never becomes the dominant Zn(II)-bearing solid — ZnO wins the free-energy competition everywhere the map shows a Zn(II) solid.

**Log K / log β values actually used** (from the reference-constants table, LC2 card):
- Aqueous Zn(II) hydrolysis (cumulative Zn²⁺ + n OH⁻ ⇌ Zn(OH)ₙ^(2−n)): log β₁ = −9.30 (ZnOH⁺), log β₂ = −15.80 (Zn(OH)₂ aq), log β₃ = −28.10 (Zn(OH)₃⁻), log β₄ = −40.50 (Zn(OH)₄²⁻).
- Aqueous Zn(II)–chloride (cumulative Zn²⁺ + n Cl⁻ ⇌ ZnClₙ^(2−n)): log β₁ = +0.40 (ZnCl⁺), log β₂ = +0.60 (ZnCl₂ aq). No ZnCl₃⁻/ZnCl₄²⁻ in the retained set.
- Solids (dissolution as written on the card, Zn²⁺ balance with H:−2): ZnO(inactive) log K = −9.6132; Zn(OH)₂(α) log K = −10.7230; Zn(s) log K = 0.
- Water: the card row [H][OH] gives log β = −0.22 for H⁺ + OH⁻ ⇌ H₂O in its activity convention, corresponding to the usual K_w = 10⁻¹⁴ at 25 °C after the standard sign flip.

**Practical read-out.** In 0.1 M Cl⁻ background, zinc corrosion chemistry is essentially unchanged from pure aqueous: Zn dissolves as Zn²⁺ up to pH ≈ 6.6, precipitates as ZnO across the wide window pH 6.6–13.5, and redissolves as zincate above pH ≈ 13.5. Chloride at 0.1 M does not open a soluble chloro-complex predominance window and does not shift the ZnO precipitation edge measurably (ZnCl⁺ and ZnCl₂(aq) are minor side species, at most ~25 % and ~4 % of the Zn²⁺ level, respectively). To see ZnCl⁺/ZnCl₂/ZnCl₃⁻/ZnCl₄²⁻ predominance one would need much higher chloride activity (seawater-and-above brines) and reinstatement of the higher chloro-complexes in the eq-card.

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
- [solver/pourbaix_map_Zn_+_Chloride_ion_Zn.csv](<solver/pourbaix_map_Zn_+_Chloride_ion_Zn.csv>)
- [solver/pourbaix_Zn_+_Chloride_ion_Zn.png](<solver/pourbaix_Zn_+_Chloride_ion_Zn.png>)
- [solver/speciation_full_Zn_+_Chloride_ion.csv](<solver/speciation_full_Zn_+_Chloride_ion.csv>)
- [solver/topo_csv_Zn_+_Chloride_ion_Zn/topo_features_0d.csv](<solver/topo_csv_Zn_+_Chloride_ion_Zn/topo_features_0d.csv>)
- [solver/topo_csv_Zn_+_Chloride_ion_Zn/topo_features_1d.csv](<solver/topo_csv_Zn_+_Chloride_ion_Zn/topo_features_1d.csv>)
- [solver/topo_csv_Zn_+_Chloride_ion_Zn/topo_metadata.json](<solver/topo_csv_Zn_+_Chloride_ion_Zn/topo_metadata.json>)
- [solver/topo_csv_Zn_+_Chloride_ion_Zn/topo_regions.csv](<solver/topo_csv_Zn_+_Chloride_ion_Zn/topo_regions.csv>)
- [solver/topology_Zn_+_Chloride_ion_Zn.json](<solver/topology_Zn_+_Chloride_ion_Zn.json>)
- [solver/topology_Zn_+_Chloride_ion_Zn_verdict.json](<solver/topology_Zn_+_Chloride_ion_Zn_verdict.json>)
- [solver/topology_Zn_+_Chloride_ion_Zn_verdict.md](<solver/topology_Zn_+_Chloride_ion_Zn_verdict.md>)
- [verdict.json](<verdict.json>)
