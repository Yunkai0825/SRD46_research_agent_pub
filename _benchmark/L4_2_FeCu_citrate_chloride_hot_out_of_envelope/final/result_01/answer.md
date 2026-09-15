## Doability

Partially doable: the pipeline solved the joint Cu+Fe+citrate+Cl Pourbaix under the requested totals and produced converged predominance maps for both metals. **Important caveat**: the LC2 free-energy card is populated from SRD-46 constants at 25 C, 1 bar (no T/P-dependent data are encoded — see `LC2/thermodynamic_reference_constants.md`). The requested 250 C / 80 bar hydrothermal conditions cannot be honored numerically; the diagrams below are the 25 C reference behaviour of the specified composition, which is the tool's actual output and the closest the SRD-46 catalog supports. All quantitative pH/E crossovers should be read as isothermal 25 C guideposts, not hydrothermal values.

## Result

- System: Cu 1 mM, Fe 1 mM, citrate 5 mM, Cl 0.1 M, solved jointly (both metals compete for the ligand pools).
- Method: `pourbaix_sweep`, pH ∈ [0, 14], E_V ∈ [−1, 1.2] V vs SHE, final grid ΔpH=0.0125, ΔE=0.0023 V.
- Coverage: 154 379 refined cells + 3 319 coarse cells retained; both element verdicts report 0 disconnected regions and no parser-failure notice, so labels are cleanly assigned everywhere in the box.
- Two verdict maps written, one per principal element (Cu: 8 regions / 13 boundaries; Fe: 7 regions / 13 boundaries).

## Analysis

### Feature roster (features cited below)

**Cu map** (Dms/DmsReg IDs from `..._Cu_verdict.md`):
- `DmsReg_4 {[Cu(Chlo)2]−}`: chlorocuprate(I), the low-E aqueous field; corners `DmsRegEqJnc_9` (pH 0, E −0.138 V), `DmsRegEqJnc_11` (pH 6.675, E −0.138 V), `DmsRegEqJnc_8` (pH 6.95, E −0.035 V), `DmsRegEqJnc_3` (pH 3.26, E 0.327 V), `DmsRegEqJnc_4` (pH 0, E 0.327 V).
- `DmsReg_5 {[Cu2(Citr)2(OH)2]4−}`: dominant Cu(II)-citrate species over most of the mid-pH oxidising region; corners incl. `DmsRegEqJnc_1` (pH 4.86, E 0.144 V), `DmsRegEqJnc_8` (pH 6.95, E −0.035 V), `DmsRegEqJnc_10` (pH 10.275, E 1.2 V), `DmsRegEqJnc_12` (pH 10.275, E −0.026 V).
- `DmsReg_6 {[Cu2(Citr)2(OH)]3−}`: narrow mono-hydroxo Cu(II)-citrate wedge between pH 3.51–4.86.
- `DmsReg_7 {[Cu(Citr)H]}`: very small protonated Cu(II)-citrate field near pH 3.3–3.5.
- `DmsReg_8 {Cu2+}`: free aqua Cu(II) only at pH < 3.26 at high E.
- `DmsReg_1 {Cu}` (metal), `DmsReg_2 {[(Cu2O)0.5](s)}` (cuprite), `DmsReg_3 {CuO(s)}` (tenorite): the reducing / alkaline solid trio.

**Fe map** (from `..._Fe_verdict.md`):
- `DmsReg_2 {[(Fe2O3)0.5(s,alpha)]}` (hematite): the overwhelming Fe(III) sink, corners incl. `DmsRegEqJnc_11` (pH 6.29, E −0.407 V), `DmsRegEqJnc_5` (pH 4.15, E −0.109 V), `DmsRegEqJnc_6` (pH 3.96, E −0.083 V), `DmsRegEqJnc_7` (pH 1.09, E 0.432 V), `DmsRegEqJnc_8` (pH 1.09, E 0.799 V), `DmsRegEqJnc_10` (pH 14, E −0.462 V).
- `DmsReg_6 {Fe2+}`: reducing acid corner (pH < ~4, E below ~ −0.08 to +0.43 V depending on pH).
- `DmsReg_7 {[Fe(Chlo)2]+}`: tiny Fe(III)-chloride sliver at pH 1.04–1.09 between E 0.432 and 0.799 V.
- `DmsReg_4 {[Fe(Citr)]−}`, `DmsReg_5 {[Fe(Citr)H]}`: micro-fields of Fe(II)-citrate wedged along the Fe/Fe(II)/hematite corner near pH 4.15.
- `DmsReg_1 {Fe}` (metal), `DmsReg_3 {FeO4^2−}` (ferrate, only at extreme oxidising E: boundary at pH 1.09/E 0.799 V rising to pH 14/E −0.462 V).

### How Fe partitions

The Fe map is dominated by **hematite** (`DmsReg_2`, solver measure 7.26 — the largest liquid or solid region on the Fe diagram). Hematite blankets essentially the whole diagram from pH ≈ 3 up to pH 14 across the entire environmentally accessible E window (its boundary with Fe(II) runs from `DmsRegEqJnc_6` at (pH 3.96, E −0.083 V) down to `DmsRegEqJnc_11` at (pH 6.29, E −0.407 V), i.e. only reducing acid conditions escape it). Free Fe(II) (`DmsReg_6`, measure 2.31) owns the reducing acid corner; free Fe(III) never becomes a predominant field at all — as soon as hydrolysis exceeds the solubility of Fe2O3 the iron precipitates. Fe(III)-chloride complexes are effectively out-competed: only a 0.48-measure sliver of `[Fe(Chlo)2]+` appears at pH ≈ 1.04–1.09 between E 0.43 and 0.80 V, squeezed between hematite, Fe2+ and ferrate. **Fe(III)-citrate species do not appear anywhere as the dominant form** — despite the card carrying `[Fe(Citr)]` (log β +11.19), `[Fe(Citr)H]+` (+12.35), `[Fe(Citr)(OH)]−` (+8.49) and the dimer `[Fe2(Citr)2(OH)2]2−` (+21.20), all are beaten in the mid-pH region by hematite precipitation. The only citrate footprints on the Fe map are two microscopic Fe(II)-citrate wedges (`[Fe(Citr)]−` measure 0.31, `[Fe(Citr)H]` measure 0.041) tucked at the Fe/hematite/Fe2+ boundary near pH 4.15 — a genuine but volumetrically negligible stabilisation of Fe(II) by the doubly/triply deprotonated citrate. Ferrate `FeO4^2−` only emerges above E ≈ 0.77 V (pH 1.09) rising to E ≈ 0.23 V at pH 7 (E–pH reference line) and 0 V at pH 14 — the standard strongly oxidising Fe(VI) domain, unrelated to ligation.

Practical read: under these totals Fe(III) precipitates as α-Fe2O3 wherever the pot is not both acidic and reducing. Citrate at 5 mM cannot keep Fe(III) soluble against hematite, and 0.1 M Cl only mobilises Fe(III) at pH ≲ 1.

### How Cu partitions

Cu behaves oppositely. Its diagram is split into three broad regimes on the E axis:
- **Reducing / mildly oxidising, all pH ≤ ~7**: `[Cu(Chlo)2]−` (`DmsReg_4`, measure 2.46). This dichlorocuprate(I) anion (log β +6.06 from `Cu+` + 2Cl−) is stabilised by the 0.1 M Cl pool and dominates from pH 0 up to pH ≈ 6.95 across the full E band between the Cu-metal boundary at E ≈ −0.138 V (`DmsRegEq_8`) and the redox line to Cu(II) species at E ≈ 0.32 V (pH < 3) sloping down to E ≈ −0.035 V at pH ~7 (`DmsRegEq_1`). So chloride, not citrate, keeps Cu in solution under acidic reducing conditions.
- **Mid-pH, oxidising**: the Cu(II)-citrate dihydroxo dimer `[Cu2(Citr)2(OH)2]4−` (`DmsReg_5`, measure 6.51 — the single largest region on the Cu map) rules from pH ≈ 4.86 to pH ≈ 10.275 across effectively the entire Cu(II) E range (up to 1.2 V). Its lower boundary against `[Cu(Chlo)2]−` (`DmsRegEq_1`) runs from (pH 4.86, E 0.144 V) up to (pH 6.95, E −0.035 V) — this is the redox couple where Cu(I)-chloride is oxidised into the Cu(II)-citrate dimer. Below pH 4.86 a narrow ladder `[Cu2(Citr)2(OH)]3−` → `[Cu(Citr)H]` → `Cu2+` (`DmsReg_6`, `_7`, `_8`) marks successive citrate protonation and finally the loss of citrate binding to give free Cu2+ at pH < 3.26 at high E.
- **Alkaline, oxidising**: at pH > 10.275 the citrate dimer gives way to `CuO(s)` (tenorite, `DmsReg_3`) — even 5 mM citrate cannot hold 1 mM Cu(II) against CuO precipitation once the OH− activity is large enough. The vertical boundary `DmsRegEq_11` at pH = 10.275 is a non-redox dissolution equilibrium (Cu(II) on both sides).
- **Reducing / alkaline**: cuprite `[(Cu2O)0.5](s)` (`DmsReg_2`) and Cu(0) metal (`DmsReg_1`) fill the reducing side, with cuprite between pH ≈ 6.7 and 14 and E between roughly −0.14 V (acidic) and −0.57 V (alkaline).

Read as competition: chloride wins Cu at low pH & reducing E (Cu(I)Cl2−), citrate wins Cu across the mid-pH oxidising band (Cu2Citr2(OH)2 dimer), hydroxide/oxide wins above pH ≈ 10 (CuO) or below E ≈ −0.14 V at neutral pH (Cu2O then Cu metal). Free Cu2+ has only a small acid corner (pH < 3.26, E > 0.327 V).

### Redox character of key boundaries (from the card oxidation states, per briefing)

Cu(I)/Cu(II) redox lines: `DmsRegEq_1` (Cu(Chlo)2− | Cu2Citr2(OH)2^4−), `DmsRegEq_2`, `DmsRegEq_3`, `DmsRegEq_4` (Cu(Chlo)2− | Cu2+). These are the chloride-to-citrate/hydroxide oxidation transitions. Cu(0)/Cu(I) lines: `DmsRegEq_8` and `DmsRegEq_12`. `DmsRegEq_11` (CuO | Cu2Citr2(OH)2^4−) is non-redox (both Cu(II)) — a pure precipitation boundary. On the Fe map, `DmsRegEq_10` (hematite | Fe2+) is redox (Fe(III)/Fe(II)) whereas `DmsRegEq_12` (hematite | Fe(Chlo)2+) is non-redox (both Fe(III)) — a dissolution equilibrium where Cl− peels Fe(III) off hematite only at pH ≈ 1.04–1.09.

### Joint pot picture

Cu and Fe do not compete much for the ligands in this composition. Fe(III) sinks into hematite over almost the whole diagram, freeing citrate to bind Cu(II) as the dihydroxo dimer through the wide mid-pH oxidising region; the 5 mM citrate pool is comfortably above the 2 × 1 mM Cu(II) stoichiometry needed for that dimer. Chloride at 0.1 M is captured almost exclusively by Cu(I) under reducing acid conditions; Fe(III)-chloride only appears at pH ≲ 1.1. Practically, a hydrothermal pot at these totals would (in the 25 C reference frame) precipitate iron as α-Fe2O3, keep copper dissolved as Cu(I) chloride in acidic reducing zones and as Cu(II)-citrate hydroxo dimer in mid-pH oxidising zones, and shed CuO only above pH ≈ 10.3. Actual 250 C / 80 bar behaviour will shift every boundary — hematite stability grows, Cu(I)-chloride complexes are known to strengthen sharply with T, and citrate itself hydrolyses — so the *pattern* above is a useful qualitative baseline but the numerical crossovers should not be transplanted to hydrothermal conditions without T-corrected constants.

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
- [solver/pourbaix_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu.png](<solver/pourbaix_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu.png>)
- [solver/pourbaix_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe.png](<solver/pourbaix_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe.png>)
- [solver/pourbaix_map_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu.csv](<solver/pourbaix_map_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu.csv>)
- [solver/pourbaix_map_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe.csv](<solver/pourbaix_map_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe.csv>)
- [solver/speciation_full_Cu_+_Fe_+_Citric_acid_+_Chloride_ion.csv](<solver/speciation_full_Cu_+_Fe_+_Citric_acid_+_Chloride_ion.csv>)
- [solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu/topo_features_0d.csv](<solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu/topo_features_0d.csv>)
- [solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu/topo_features_1d.csv](<solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu/topo_features_1d.csv>)
- [solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu/topo_metadata.json](<solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu/topo_metadata.json>)
- [solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu/topo_regions.csv](<solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu/topo_regions.csv>)
- [solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe/topo_features_0d.csv](<solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe/topo_features_0d.csv>)
- [solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe/topo_features_1d.csv](<solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe/topo_features_1d.csv>)
- [solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe/topo_metadata.json](<solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe/topo_metadata.json>)
- [solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe/topo_regions.csv](<solver/topo_csv_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe/topo_regions.csv>)
- [solver/topology_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu.json](<solver/topology_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu.json>)
- [solver/topology_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu_verdict.json](<solver/topology_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu_verdict.json>)
- [solver/topology_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu_verdict.md](<solver/topology_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Cu_verdict.md>)
- [solver/topology_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe.json](<solver/topology_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe.json>)
- [solver/topology_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe_verdict.json](<solver/topology_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe_verdict.json>)
- [solver/topology_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe_verdict.md](<solver/topology_Cu_+_Fe_+_Citric_acid_+_Chloride_ion_Fe_verdict.md>)
- [verdict.json](<verdict.json>)
