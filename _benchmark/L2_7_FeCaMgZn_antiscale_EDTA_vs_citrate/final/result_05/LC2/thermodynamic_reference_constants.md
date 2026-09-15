# Deterministic thermodynamic reference constants

- Source card: `free_energy_card.md`
- Selection: species rows whose final LC2 `include` field is `true`.
- Reaction convention: the source card defines `log_beta` as the cumulative formation constant from free components; each row below reports its `stoich` reaction basis and product species. For a protonated ligand, the card convention is `x H+ + L <=> HxL`. Only the `x = 1` single-protonation value is directly the conjugate-acid pKa; higher `x` values are cumulative protonation constants.
- Interpretation: values and source are copied exactly. Do not rename a generic `log_beta` as a pKa, dissolution constant, or another named constant unless that row's reaction/species definition supports it.

| species_id | product label | phase | log_beta | reaction basis (stoich) | source | include |
|---|---|---|---:|---|---|---|
| [H].[OH].[z+0] | [?] | aqueous | -0.2200 | [H]:+1, [OH]:+1 | SRD-46 | true |
| [[H]6[L1]].[z+2] | [H6EDTA]2+ | aqueous | +18.8500 | [[H]6[L1]]:+1 | SRD-46 | true |
| [[H]5[L1]].[z+1] | [H5EDTA]+ | aqueous | +18.8500 | [[H]5[L1]]:+1 | SRD-46 | true |
| [[H]4[L1]].[z+0] | [H4EDTA] | aqueous | +20.2500 | [[H]4[L1]]:+1 | SRD-46 | true |
| [[H]3[L1]].[z-1] | [H3EDTA]- | aqueous | +18.2300 | [[H]3[L1]]:+1 | SRD-46 | true |
| [[H]2[L1]].[z-2] | [H2EDTA]2- | aqueous | +15.7100 | [[H]2[L1]]:+1 | SRD-46 | true |
| [[H][L1]].[z-3] | [HEDTA]3- | aqueous | +9.5200 | [[H][L1]]:+1 | SRD-46 | true |
| [L1].[z-4] | [EDTA] | aqueous | +0.0000 | [L1]:+1 | SRD-46 | true |
| [Mg$+2].[z+2] | [Mg]2+ | aqueous | +0.0000 | [Mg$+2]:+1 | SRD-46 | true |
| [Mg$+2].[OH].[z+1] | [Mg(OH)]+ | aqueous | -11.4000 | [Mg$+2]:+1, [OH]:+1 | SRD-46 | true |
| [Mg$+2]2.[OH].[z+3] | [Mg2(OH)]3+ | aqueous | -11.7000 | [Mg$+2]:+2, [OH]:+1 | SRD-46 | true |
| [Mg$+2]4.[OH]4.[z+4] | [Mg4(OH)4]4+ | aqueous | -39.9000 | [Mg$+2]:+4, [OH]:+4 | SRD-46 | true |
| [Mg$+2].[[H][L1]].[z-1] | [Mg(EDTA)H]- | aqueous | +12.7900 | [Mg$+2]:+1, [[H][L1]]:+1 | SRD-46 | true |
| [Mg$+2].[L1].[z-2] | [Mg(EDTA)]2- | aqueous | +8.7900 | [Mg$+2]:+1, [L1]:+1 | SRD-46 | true |
| [Mg$+2].[OH]2.[z+0]_(s) | [Mg(OH)2(s,brucite)] | dissolution | -16.8600 | [Mg$+2]:+1, [OH]:+2 | SRD-46 | true |
