# Deterministic thermodynamic reference constants

- Source card: `free_energy_card.md`
- Selection: species rows whose final LC2 `include` field is `true`.
- Reaction convention: the source card defines `log_beta` as the cumulative formation constant from free components; each row below reports its `stoich` reaction basis and product species. For a protonated ligand, the card convention is `x H+ + L <=> HxL`. Only the `x = 1` single-protonation value is directly the conjugate-acid pKa; higher `x` values are cumulative protonation constants.
- Interpretation: values and source are copied exactly. Do not rename a generic `log_beta` as a pKa, dissolution constant, or another named constant unless that row's reaction/species definition supports it.

| species_id | product label | phase | log_beta | reaction basis (stoich) | source | include |
|---|---|---|---:|---|---|---|
| [H].[OH].[z+0] | [?] | aqueous | -0.2200 | [H]:+1, [OH]:+1 | SRD-46 | true |
| [[H]3[L1]].[z+0] | [H3Citric acid] | aqueous | +12.9000 | [[H]3[L1]]:+1 | SRD-46 | true |
| [[H]2[L1]].[z-1] | [H2Citric acid]- | aqueous | +10.0000 | [[H]2[L1]]:+1 | SRD-46 | true |
| [[H][L1]].[z-2] | [HCitric acid]2- | aqueous | +5.6500 | [[H][L1]]:+1 | SRD-46 | true |
| [L1].[z-3] | [Citric acid] | aqueous | +0.0000 | [L1]:+1 | SRD-46 | true |
| [L2].[z-1] | [Chloride ion] | aqueous | +0.0000 | [L2]:+1 | SRD-46 | true |
| [Cu$+1].[z+1] | [Cu]+ | aqueous | +0.0000 | [Cu$+1]:+1 | SRD-46 | true |
| [Cu$+1]2.[L2]4.[z-2] | [Cu2(Chlo)4]2- | aqueous | +13.0000 | [Cu$+1]:+2, [L2]:+4 | SRD-46 | true |
| [Cu$+1].[L2]2.[z-1] | [Cu(Chlo)2]- | aqueous | +6.0600 | [Cu$+1]:+1, [L2]:+2 | SRD-46 | true |
| [Cu$+1].[L2]3.[z-2] | [Cu(Chlo)3]2- | aqueous | +5.3900 | [Cu$+1]:+1, [L2]:+3 | SRD-46 | true |
| [Cu$+1].[L2].[z+0] | [Cu(Chlo)] | aqueous | +3.1000 | [Cu$+1]:+1, [L2]:+1 | SRD-46 | true |
| [Cu$+2].[z+2] | [Cu]2+ | aqueous | +0.0000 | [Cu$+2]:+1 | SRD-46 | true |
| [Cu$+2].[OH].[z+1] | [Cu(OH)]+ | aqueous | -7.9000 | [Cu$+2]:+1, [OH]:+1 | SRD-46 | true |
| [Cu$+2]2.[OH]2.[z+2] | [Cu2(OH)2]2+ | aqueous | -11.2000 | [Cu$+2]:+2, [OH]:+2 | SRD-46 | true |
| [Cu$+2].[OH]2.[z+0] | [Cu(OH)2] | aqueous | -16.2000 | [Cu$+2]:+1, [OH]:+2 | SRD-46 | true |
| Cu$+2.OH3.z-1 | [HCuO2]- | aqueous | -26.7048 | Cu$+2:+1 H:-3 | Atlas | true |
| [Cu$+2]3.[OH]4.[z+2] | [Cu3(OH)4]2+ | aqueous | -22.5000 | [Cu$+2]:+3, [OH]:+4 | SRD-46 | true |
| Cu$+2.OH4.z-2 | [CuO2]2- | aqueous | -39.8410 | Cu$+2:+1 H:-4 | Atlas | true |
| [Cu$+2].[[H][L1]].[z+0] | [Cu(Citr)H] | aqueous | +9.2600 | [Cu$+2]:+1, [[H][L1]]:+1 | SRD-46 | true |
| [Cu$+2]2.[L1]2.[z-2] | [Cu2(Citr)2]2- | aqueous | +14.5000 | [Cu$+2]:+2, [L1]:+2 | SRD-46 | true |
| [Cu$+2]2.[[H]-1[L1]].[z+0] | [Cu2(Citr)(OH)] | aqueous | +4.8600 | [Cu$+2]:+2, [[H]-1[L1]]:+1 | SRD-46 | true |
| [Cu$+2]2.[[H]-1[L1]].[L1].[z-3] | [Cu2(Citr)2(OH)]3- | aqueous | +11.2000 | [Cu$+2]:+2, [[H]-1[L1]]:+1, [L1]:+1 | SRD-46 | true |
| [Cu$+2]2.[[H]-1[L1]]2.[z-4] | [Cu2(Citr)2(OH)2]4- | aqueous | +6.3400 | [Cu$+2]:+2, [[H]-1[L1]]:+2 | SRD-46 | true |
| [Cu$+2].[L2].[z+1] | [Cu(Chlo)]+ | aqueous | -0.2000 | [Cu$+2]:+1, [L2]:+1 | SRD-46 | true |
| [Fe$+2].[z+2] | [Fe]2+ | aqueous | +0.0000 | [Fe$+2]:+1 | SRD-46 | true |
| [Fe$+2].[OH].[z+1] | [Fe(OH)]+ | aqueous | -9.8000 | [Fe$+2]:+1, [OH]:+1 | SRD-46 | true |
| [Fe$+2].[OH]2.[z+0] | [Fe(OH)2] | aqueous | -35.5000 | [Fe$+2]:+1, [OH]:+2 | SRD-46 | true |
| [Fe$+2].[OH]3.[z-1] | [Fe(OH)3]- | aqueous | -29.0000 | [Fe$+2]:+1, [OH]:+3 | SRD-46 | true |
| [Fe$+2].[OH]4.[z-2] | [Fe(OH)4]2- | aqueous | -46.0000 | [Fe$+2]:+1, [OH]:+4 | SRD-46 | true |
| [Fe$+2].[[H]2[L1]].[z+1] | [Fe(Citr)H2]+ | aqueous | +11.1000 | [Fe$+2]:+1, [[H]2[L1]]:+1 | SRD-46 | true |
| [Fe$+2].[[H][L1]].[z+0] | [Fe(Citr)H] | aqueous | +8.5500 | [Fe$+2]:+1, [[H][L1]]:+1 | SRD-46 | true |
| [Fe$+2].[L1]2.[H].[z-3] | [Fe(Citr)2H]3- | aqueous | +11.7400 | [Fe$+2]:+1, [L1]:+2, [H]:+1 | SRD-46 | true |
| [Fe$+2].[L1].[z-1] | [Fe(Citr)]- | aqueous | +4.4000 | [Fe$+2]:+1, [L1]:+1 | SRD-46 | true |
| [Fe$+2]2.[[H]-1[L1]]2.[z-4] | [Fe2(Citr)2(OH)2]4- | aqueous | -5.4000 | [Fe$+2]:+2, [[H]-1[L1]]:+2 | SRD-46 | true |
| [Fe$+2].[L2].[z+1] | [Fe(Chlo)]+ | aqueous | -0.2000 | [Fe$+2]:+1, [L2]:+1 | SRD-46 | true |
| [Fe$+3].[z+3] | [Fe]3+ | aqueous | +0.0000 | [Fe$+3]:+1 | SRD-46 | true |
| [Fe$+3].[OH].[z+2] | [Fe(OH)]2+ | aqueous | -2.7300 | [Fe$+3]:+1, [OH]:+1 | SRD-46 | true |
| [Fe$+3]2.[OH]2.[z+4] | [Fe2(OH)2]4+ | aqueous | -2.8600 | [Fe$+3]:+2, [OH]:+2 | SRD-46 | true |
| [Fe$+3].[OH]2.[z+1] | [Fe(OH)2]+ | aqueous | -6.2000 | [Fe$+3]:+1, [OH]:+2 | SRD-46 | true |
| [Fe$+3]3.[OH]4.[z+5] | [Fe3(OH)4]5+ | aqueous | -6.3000 | [Fe$+3]:+3, [OH]:+4 | SRD-46 | true |
| [Fe$+3].[OH]4.[z-1] | [Fe(OH)4]- | aqueous | -21.6000 | [Fe$+3]:+1, [OH]:+4 | SRD-46 | true |
| [Fe$+3].[[H][L1]].[z+1] | [Fe(Citr)H]+ | aqueous | +12.3500 | [Fe$+3]:+1, [[H][L1]]:+1 | SRD-46 | true |
| [Fe$+3].[L1].[z+0] | [Fe(Citr)] | aqueous | +11.1900 | [Fe$+3]:+1, [L1]:+1 | SRD-46 | true |
| [Fe$+3].[OH].[L1].[z-1] | [Fe(Citr)(OH)]- | aqueous | +8.4900 | [Fe$+3]:+1, [OH]:+1, [L1]:+1 | SRD-46 | true |
| [Fe$+3]2.[OH]2.[L1]2.[z-2] | [Fe2(Citr)2(OH)2]2- | aqueous | +21.2000 | [Fe$+3]:+2, [OH]:+2, [L1]:+2 | SRD-46 | true |
| [Fe$+3].[L2]2.[z+1] | [Fe(Chlo)2]+ | aqueous | +2.1300 | [Fe$+3]:+1, [L2]:+2 | SRD-46 | true |
| [Fe$+3].[L2].[z+2] | [Fe(Chlo)]2+ | aqueous | +0.7800 | [Fe$+3]:+1, [L2]:+1 | SRD-46 | true |
| Fe$+6.OH8.z-2 | [FeO4]2- | aqueous | -0.0000 | Fe$+6:+1 H:-8 | Atlas | true |
| [Cu$+1].[OH].[z+0]_(s) | [(Cu2O)0.5](s) | dissolution | +0.7000 | [Cu$+1]:+1, [H]:-1 | SRD-46 | true |
| [Cu$+1].[L2].[z+0]_(s) | [Cu(Chloride ion)](s) | dissolution | +6.7300 | [Cu$+1]:+1, [L2]:+1 | SRD-46 | true |
| [Cu$+2].[OH]2.[[z+0(s)[1]]] | [CuO](s) | dissolution | -7.6500 | [Cu$+2]:+1, [H]:-2 | SRD-46 | true |
| Cu$+0.z+0(s) | Cu | dissolution | -0.0000 | Cu$+0:+1 | Atlas | true |
| [Fe$+2].[OH]2.[z+0]_(s) | [Fe(OH)2](s) | dissolution | -13.5700 | [Fe$+2]:+1, [OH]:+2 | SRD-46 | true |
| Fe$+2.Fe$+3(2).OH8.z+0(s) | Fe3O4 (anh.) | dissolution | -7.1252 | Fe$+2:+1 Fe$+3:+2 H:-8 | Atlas | true |
| [Fe$+3].[OH]3.[[z+0(s)[1]]] | [(Fe2O3)0.5(s,alpha)] | dissolution | +0.7000 | [Fe$+3]:+1, [H]:-3 | SRD-46 | true |
| [Fe$+3].[OH]3.[[z+0(s)[2]]] | [FeO(OH)(s,alpha)] | dissolution | -0.5000 | [Fe$+3]:+1, [H]:-3 | SRD-46 | true |
| [Fe$+3].[OH]3.[[z+0(s)[3]]] | [Fe(OH)3](s) | dissolution | -3.2000 | [Fe$+3]:+1, [OH]:+3 | SRD-46 | true |
| Fe$+0.z+0(s) | Fe | dissolution | -0.0000 | Fe$+0:+1 | Atlas | true |
