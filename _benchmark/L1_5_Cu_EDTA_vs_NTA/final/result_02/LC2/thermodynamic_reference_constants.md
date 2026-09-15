# Deterministic thermodynamic reference constants

- Source card: `free_energy_card.md`
- Selection: species rows whose final LC2 `include` field is `true`.
- Reaction convention: the source card defines `log_beta` as the cumulative formation constant from free components; each row below reports its `stoich` reaction basis and product species. For a protonated ligand, the card convention is `x H+ + L <=> HxL`. Only the `x = 1` single-protonation value is directly the conjugate-acid pKa; higher `x` values are cumulative protonation constants.
- Interpretation: values and source are copied exactly. Do not rename a generic `log_beta` as a pKa, dissolution constant, or another named constant unless that row's reaction/species definition supports it.

| species_id | product label | phase | log_beta | reaction basis (stoich) | source | include |
|---|---|---|---:|---|---|---|
| [H].[OH].[z+0] | [?] | aqueous | -0.2200 | [H]:+1, [OH]:+1 | SRD-46 | true |
| [[H]4[L1]].[z+1] | [H4NTA]+ | aqueous | +9.1700 | [[H]4[L1]]:+1 | SRD-46 | true |
| [[H]3[L1]].[z+0] | [H3NTA] | aqueous | +10.1700 | [[H]3[L1]]:+1 | SRD-46 | true |
| [[H]2[L1]].[z-1] | [H2NTA]- | aqueous | +11.9800 | [[H]2[L1]]:+1 | SRD-46 | true |
| [[H][L1]].[z-2] | [HNTA]2- | aqueous | +9.4600 | [[H][L1]]:+1 | SRD-46 | true |
| [L1].[z-3] | [NTA] | aqueous | +0.0000 | [L1]:+1 | SRD-46 | true |
| [Cu$+1].[z+1] | [Cu]+ | aqueous | +0.0000 | [Cu$+1]:+1 | SRD-46 | true |
| [Cu$+2].[z+2] | [Cu]2+ | aqueous | +0.0000 | [Cu$+2]:+1 | SRD-46 | true |
| [Cu$+2].[OH].[z+1] | [Cu(OH)]+ | aqueous | -7.9000 | [Cu$+2]:+1, [OH]:+1 | SRD-46 | true |
| [Cu$+2]2.[OH]2.[z+2] | [Cu2(OH)2]2+ | aqueous | -11.2000 | [Cu$+2]:+2, [OH]:+2 | SRD-46 | true |
| [Cu$+2].[OH]2.[z+0] | [Cu(OH)2] | aqueous | -16.2000 | [Cu$+2]:+1, [OH]:+2 | SRD-46 | true |
| Cu$+2.OH3.z-1 | [HCuO2]- | aqueous | -26.7048 | Cu$+2:+1 H:-3 | Atlas | true |
| [Cu$+2]3.[OH]4.[z+2] | [Cu3(OH)4]2+ | aqueous | -22.5000 | [Cu$+2]:+3, [OH]:+4 | SRD-46 | true |
| Cu$+2.OH4.z-2 | [CuO2]2- | aqueous | -39.8410 | Cu$+2:+1 H:-4 | Atlas | true |
| [Cu$+2].[[H][L1]].[z+0] | [Cu(NTA)H] | aqueous | +14.3000 | [Cu$+2]:+1, [[H][L1]]:+1 | SRD-46 | true |
| [Cu$+2].[L1].[z-1] | [Cu(NTA)]- | aqueous | +12.7000 | [Cu$+2]:+1, [L1]:+1 | SRD-46 | true |
| [Cu$+2].[L1]2.[z-4] | [Cu(NTA)2]4- | aqueous | +17.4000 | [Cu$+2]:+1, [L1]:+2 | SRD-46 | true |
| [Cu$+2].[OH].[L1].[z-2] | [Cu(NTA)(OH)]2- | aqueous | +3.5000 | [Cu$+2]:+1, [OH]:+1, [L1]:+1 | SRD-46 | true |
| [Cu$+1].[OH].[z+0]_(s) | [(Cu2O)0.5](s) | dissolution | +0.7000 | [Cu$+1]:+1, [H]:-1 | SRD-46 | true |
| [Cu$+2].[OH]2.[[z+0(s)[1]]] | [CuO](s) | dissolution | -7.6500 | [Cu$+2]:+1, [H]:-2 | SRD-46 | true |
| [Cu$+2].[OH]2.[[z+0(s)[2]]] | [Cu(OH)2](s) | dissolution | -8.6800 | [Cu$+2]:+1, [OH]:+2 | SRD-46 | true |
