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
| Ca$+2.z+2 | Ca2+ | aqueous | -0.0000 | Ca$+2:+1 | Atlas | true |
| [Ca$+2].[OH].[z+1] | [Ca(OH)]+ | aqueous | -13.0400 | [Ca$+2]:+1, [OH]:+1 | SRD-46 | true |
| [Ca$+2].[[H]2[L1]].[z+1] | [Ca(Citr)H2]+ | aqueous | +11.0000 | [Ca$+2]:+1, [[H]2[L1]]:+1 | SRD-46 | true |
| [Ca$+2].[[H][L1]].[z+0] | [Ca(Citr)H] | aqueous | +7.7200 | [Ca$+2]:+1, [[H][L1]]:+1 | SRD-46 | true |
| [Ca$+2].[L1].[z-1] | [Ca(Citr)]- | aqueous | +3.4500 | [Ca$+2]:+1, [L1]:+1 | SRD-46 | true |
| Ca$+2.OH2.z+0(s) | Ca(OH)2 | dissolution | -22.8930 | Ca$+2:+1 H:-2 | Atlas | true |
| [Ca$+2].[[H][L1]].[z+0]_(s) | [CaH(Citric acid)](s) | dissolution | +11.3900 | [Ca$+2]:+1, [[H][L1]]:+1 | SRD-46 | true |
| [Ca$+2]3.[L1]2.[z+0]_(s) | [Ca3(Citric acid)2](s) | dissolution | +17.0300 | [Ca$+2]:+3, [L1]:+2 | SRD-46 | true |
