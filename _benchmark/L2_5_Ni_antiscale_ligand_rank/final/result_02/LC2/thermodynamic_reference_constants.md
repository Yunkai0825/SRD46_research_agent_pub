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
| Ni$+2.z+2 | Ni2+ | aqueous | -0.0000 | Ni$+2:+1 | Atlas | true |
| [Ni$+2].[OH].[z+1] | [Ni(OH)]+ | aqueous | -10.4000 | [Ni$+2]:+1, [OH]:+1 | SRD-46 | true |
| [Ni$+2].[OH]2.[z+0] | [Ni(OH)2] | aqueous | -19.0000 | [Ni$+2]:+1, [OH]:+2 | SRD-46 | true |
| [Ni$+2].[OH]3.[z-1] | [Ni(OH)3]- | aqueous | -30.0000 | [Ni$+2]:+1, [OH]:+3 | SRD-46 | true |
| [Ni$+2]4.[OH]4.[z+4] | [Ni4(OH)4]4+ | aqueous | -27.7000 | [Ni$+2]:+4, [OH]:+4 | SRD-46 | true |
| [Ni$+2].[[H]2[L1]].[z+1] | [Ni(Citr)H2]+ | aqueous | +11.7000 | [Ni$+2]:+1, [[H]2[L1]]:+1 | SRD-46 | true |
| [Ni$+2].[[H][L1]].[z+0] | [Ni(Citr)H] | aqueous | +8.8900 | [Ni$+2]:+1, [[H][L1]]:+1 | SRD-46 | true |
| [Ni$+2].[L1]2.[H].[z-3] | [Ni(Citr)2H]3- | aqueous | +13.2900 | [Ni$+2]:+1, [L1]:+2, [H]:+1 | SRD-46 | true |
| [Ni$+2].[L1].[z-1] | [Ni(Citr)]- | aqueous | +5.1800 | [Ni$+2]:+1, [L1]:+1 | SRD-46 | true |
| [Ni$+2].[L1]2.[z-4] | [Ni(Citr)2]4- | aqueous | +8.1300 | [Ni$+2]:+1, [L1]:+2 | SRD-46 | true |
| [Ni$+2]2.[[H]-1[L1]]2.[z-4] | [Ni2(Citr)2(OH)2]4- | aqueous | -4.3200 | [Ni$+2]:+2, [[H]-1[L1]]:+2 | SRD-46 | true |
| Ni$+2.OH2.z+0(s) | Ni(OH)2 | dissolution | -11.7141 | Ni$+2:+1 H:-2 | Atlas | true |
