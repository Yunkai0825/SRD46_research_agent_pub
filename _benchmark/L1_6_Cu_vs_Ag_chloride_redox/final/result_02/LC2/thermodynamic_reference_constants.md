# Deterministic thermodynamic reference constants

- Source card: `free_energy_card.md`
- Selection: species rows whose final LC2 `include` field is `true`.
- Reaction convention: the source card defines `log_beta` as the cumulative formation constant from free components; each row below reports its `stoich` reaction basis and product species. For a protonated ligand, the card convention is `x H+ + L <=> HxL`. Only the `x = 1` single-protonation value is directly the conjugate-acid pKa; higher `x` values are cumulative protonation constants.
- Interpretation: values and source are copied exactly. Do not rename a generic `log_beta` as a pKa, dissolution constant, or another named constant unless that row's reaction/species definition supports it.

| species_id | product label | phase | log_beta | reaction basis (stoich) | source | include |
|---|---|---|---:|---|---|---|
| [H].[OH].[z+0] | [?] | aqueous | -0.2200 | [H]:+1, [OH]:+1 | SRD-46 | true |
| [L1].[z-1] | [Chloride ion] | aqueous | +0.0000 | [L1]:+1 | SRD-46 | true |
| Ag$+1.z+1 | Ag+ | aqueous | -0.0000 | Ag$+1:+1 | Atlas | true |
| [Ag$+1].[OH].[z+0].[dup1] | [Ag(OH)] @25C | aqueous | -12.0000 | [Ag$+1]:+1, [OH]:+1 | SRD-46 | true |
| [Ag$+1].[OH]2.[z-1].[dup1] | [Ag(OH)2]- @25C | aqueous | -24.0100 | [Ag$+1]:+1, [OH]:+2 | SRD-46 | true |
| [Ag$+1].[L1]2.[z-1] | [Ag(Chlo)2]- | aqueous | +5.6700 | [Ag$+1]:+1, [L1]:+2 | SRD-46 | true |
| [Ag$+1].[L1]3.[z-2] | [Ag(Chlo)3]2- | aqueous | +5.2000 | [Ag$+1]:+1, [L1]:+3 | SRD-46 | true |
| [Ag$+1].[L1].[z+0] | [Ag(Chlo)] | aqueous | +3.4500 | [Ag$+1]:+1, [L1]:+1 | SRD-46 | true |
| [Ag$+1].[L1]4.[z-3] | [Ag(Chlo)4]3- | aqueous | -5.3200 | [Ag$+1]:+1, [L1]:+4 | SRD-46 | true |
| Ag$+1(2).OH2.z+0(s) | Ag2O | dissolution | -12.6406 | Ag$+1:+2 H:-2 | Atlas | true |
| [Ag$+1].[L1].[z+0]_(s) | [Ag(Chloride ion)](s) | dissolution | +10.4000 | [Ag$+1]:+1, [L1]:+1 | SRD-46 | true |
| Ag$+0.z+0(s) | Ag | dissolution | -0.0000 | Ag$+0:+1 | Atlas | true |
