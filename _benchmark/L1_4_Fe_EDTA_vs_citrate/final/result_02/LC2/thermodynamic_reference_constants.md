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
| [Fe$+3].[z+3] | [Fe]3+ | aqueous | +0.0000 | [Fe$+3]:+1 | SRD-46 | true |
| [Fe$+3].[OH].[z+2] | [Fe(OH)]2+ | aqueous | -2.7300 | [Fe$+3]:+1, [OH]:+1 | SRD-46 | true |
| [Fe$+3]2.[OH]2.[z+4] | [Fe2(OH)2]4+ | aqueous | -2.8600 | [Fe$+3]:+2, [OH]:+2 | SRD-46 | true |
| [Fe$+3].[OH]2.[z+1] | [Fe(OH)2]+ | aqueous | -6.1000 | [Fe$+3]:+1, [OH]:+2 | SRD-46 | true |
| [Fe$+3]3.[OH]4.[z+5] | [Fe3(OH)4]5+ | aqueous | -6.3000 | [Fe$+3]:+3, [OH]:+4 | SRD-46 | true |
| [Fe$+3].[OH]4.[z-1] | [Fe(OH)4]- | aqueous | -21.6000 | [Fe$+3]:+1, [OH]:+4 | SRD-46 | true |
| [Fe$+3].[[H][L1]].[z+1] | [Fe(Citr)H]+ | aqueous | +12.3500 | [Fe$+3]:+1, [[H][L1]]:+1 | SRD-46 | true |
| [Fe$+3].[L1].[z+0] | [Fe(Citr)] | aqueous | +11.1900 | [Fe$+3]:+1, [L1]:+1 | SRD-46 | true |
| [Fe$+3].[OH].[L1].[z-1] | [Fe(Citr)(OH)]- | aqueous | +8.4900 | [Fe$+3]:+1, [OH]:+1, [L1]:+1 | SRD-46 | true |
| [Fe$+3]2.[OH]2.[L1]2.[z-2] | [Fe2(Citr)2(OH)2]2- | aqueous | +21.2000 | [Fe$+3]:+2, [OH]:+2, [L1]:+2 | SRD-46 | true |
| [Fe$+3].[OH]3.[[z+0(s)[3]]] | [Fe(OH)3](s) | dissolution | -3.2000 | [Fe$+3]:+1, [OH]:+3 | SRD-46 | true |
