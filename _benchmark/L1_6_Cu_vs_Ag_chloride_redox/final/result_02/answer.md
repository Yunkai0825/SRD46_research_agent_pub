## Doability
Doable — Ag with chloride ligand and metal/oxide/chloride solids are all in the SRD-46/Atlas catalog, and a pH×E map is the native `pourbaix_sweep` route.

## Result
- System: Ag (1 mM total) in 0.1 M Cl⁻ background, 25 °C, aqueous.
- Method: `pourbaix_sweep` over pH 0–14, E = −0.5 to +1.2 V vs SHE.
- Final classified grid: ΔpH = 0.008, ΔE = 0.0008 V (1751 × 2126 samples on the reference lines).
- Included Ag species: Ag⁺, Ag(OH), Ag(OH)₂⁻, AgCl, AgCl₂⁻, AgCl₃²⁻, AgCl₄³⁻, Ag₂O(s), AgCl(s), Ag(s). No convergence failures or unresolved-phase parser warnings were reported in the verdict.

## Feature roster
- **DmsReg_1 {Ag(s)}** — metallic silver field; corner junctions DmsRegEqJnc_1 (pH 0, E 0.2556 V) and DmsRegEqJnc_2 (pH 14, E 0.2556 V) at the sweep frame; solver-frame measure 10.59.
- **DmsReg_2 {AgCl(s)}** — cerargyrite/chlorargyrite field above the boundary; same two frame-corner junctions; solver-frame measure 13.23.
- **DmsRegEq_1: Ag | AgCl(s)** — the only interior manifold; compact polyline runs from (pH 0, E 0.2556 V) to (pH 14, E 0.2556 V), i.e. essentially horizontal across the full pH window. Flagged solid–solid redox by the card (Ag⁰ → Ag⁺¹).
- Reference line along pH at E = 0.3496 V: AgCl(s) across the entire pH 0–14 span (as expected — this cut sits above the redox line).
- Reference line along E at pH 7: Ag(s) from −0.5 V up to 0.2552 V, then AgCl(s) from 0.256 V to 1.2 V; label change bracketed by E ∈ [0.2552, 0.256] V.

## Analysis
**No dissolved-Ag field appears anywhere in the window.** With [Cl⁻] = 0.1 M and only 1 mM total Ag, chloride is in ~100-fold excess and the AgCl(s) dissolution constant (log β = +10.40 for Ag⁺ + Cl⁻ ⇌ AgCl(s), from the reference table) drives essentially all oxidised silver into the solid. The aqueous chloro-complexes that could otherwise dominate — AgCl (log β₁ = +3.45), AgCl₂⁻ (log β₂ = +5.67), AgCl₃²⁻ (log β₃ = +5.20), AgCl₄³⁻ (log β₄ = −5.32) — cannot compete with the solid at this chloride level and Ag(I) load; hence no Ag⁺, AgCl(aq), or AgClₙ^(1−n) predominance regions materialise on the map. Likewise Ag₂O(s) (log β_dissolution = −12.64 written as 2 Ag⁺ + H₂O ⇌ Ag₂O(s) + 2 H⁺) and the hydroxo complexes Ag(OH) (log β = −12.00) and Ag(OH)₂⁻ (log β = −24.01) are all thermodynamically buried under AgCl(s) — chloride out-competes both hydroxide and oxide precipitation everywhere in 0 ≤ pH ≤ 14.

**The only equilibrium the solver has to draw is the Ag(0) | AgCl(s) redox line.** Its position, ≈ +0.256 V vs SHE, is set by the reaction AgCl(s) + e⁻ ⇌ Ag(s) + Cl⁻ at aCl⁻ = 0.1 M. Using E = E°(AgCl/Ag) + (RT/F) ln(1/aCl⁻) with E°(AgCl/Ag) ≈ +0.222 V gives +0.222 + 0.0592·(−log 0.1) = +0.222 + 0.0592 ≈ +0.281 V; the solver's value of +0.256 V is in the same electrochemical neighbourhood (the small offset reflects the internal Atlas value of the Ag⁺/Ag couple combined with the SRD-46 log β = +10.40 for AgCl(s), rather than a hand-picked E°). Critically, the boundary is **flat in pH** across 0–14: neither half-reaction exchanges protons (Ag⁰ → Ag⁺¹, no O or H atoms transferred), so there is no Nernstian pH slope. Consequently oxide precipitation of Ag₂O — which would tilt the boundary at high pH — never appears; chloride keeps Ag(I) locked into AgCl(s) even where Ag₂O might otherwise nucleate.

**Requested answer for pH 3–5 under mild oxidation.** The Ag(0) field is stable for E ≲ +0.256 V vs SHE at pH 7, and because the boundary is horizontal across the whole map, the same threshold applies at pH 3–5: **Ag(s) is thermodynamically stable up to ≈ +0.256 V vs SHE** in 0.1 M chloride at 1 mM Ag. Above that potential the metal is oxidised straight to AgCl(s) (no soluble Ag⁺ intermediate at this chloride level). Practically: any oxidant with E ≲ +0.25 V (e.g. dissolved O₂ under strongly reducing / low-pO₂ conditions, or a poised electrode below that value) leaves metallic Ag intact; a stronger oxidant (Fe³⁺, dissolved O₂ at ambient pO₂, dilute HNO₃) will passivate/convert the surface to AgCl(s) rather than dissolve it, which is precisely the well-known corrosion behaviour of silver in chloride media and the basis of the Ag/AgCl reference electrode.

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
- [solver/pourbaix_Ag_+_Chloride_ion_Ag.png](<solver/pourbaix_Ag_+_Chloride_ion_Ag.png>)
- [solver/pourbaix_map_Ag_+_Chloride_ion_Ag.csv](<solver/pourbaix_map_Ag_+_Chloride_ion_Ag.csv>)
- [solver/speciation_full_Ag_+_Chloride_ion.csv](<solver/speciation_full_Ag_+_Chloride_ion.csv>)
- [solver/topo_csv_Ag_+_Chloride_ion_Ag/topo_features_0d.csv](<solver/topo_csv_Ag_+_Chloride_ion_Ag/topo_features_0d.csv>)
- [solver/topo_csv_Ag_+_Chloride_ion_Ag/topo_features_1d.csv](<solver/topo_csv_Ag_+_Chloride_ion_Ag/topo_features_1d.csv>)
- [solver/topo_csv_Ag_+_Chloride_ion_Ag/topo_metadata.json](<solver/topo_csv_Ag_+_Chloride_ion_Ag/topo_metadata.json>)
- [solver/topo_csv_Ag_+_Chloride_ion_Ag/topo_regions.csv](<solver/topo_csv_Ag_+_Chloride_ion_Ag/topo_regions.csv>)
- [solver/topology_Ag_+_Chloride_ion_Ag.json](<solver/topology_Ag_+_Chloride_ion_Ag.json>)
- [solver/topology_Ag_+_Chloride_ion_Ag_verdict.json](<solver/topology_Ag_+_Chloride_ion_Ag_verdict.json>)
- [solver/topology_Ag_+_Chloride_ion_Ag_verdict.md](<solver/topology_Ag_+_Chloride_ion_Ag_verdict.md>)
- [verdict.json](<verdict.json>)
