# Deterministic thermodynamic reference constants

- Source card: `free_energy_card.md`
- Selection: species rows whose final LC2 `include` field is `true`.
- Reaction convention: the source card defines `log_beta` as the cumulative formation constant from free components; each row below reports its `stoich` reaction basis and product species. For a protonated ligand, the card convention is `x H+ + L <=> HxL`. Only the `x = 1` single-protonation value is directly the conjugate-acid pKa; higher `x` values are cumulative protonation constants.
- Interpretation: values and source are copied exactly. Do not rename a generic `log_beta` as a pKa, dissolution constant, or another named constant unless that row's reaction/species definition supports it.

| species_id | product label | phase | log_beta | reaction basis (stoich) | source | include |
|---|---|---|---:|---|---|---|
| [H].[OH].[z+0] | [?] | aqueous | -0.2200 | [H]:+1, [OH]:+1 | SRD-46 | true |
| [[H]2[L1]].[z+1] | [H2Glycine]+ | aqueous | +11.9000 | [[H]2[L1]]:+1 | SRD-46 | true |
| [[H][L1]].[z+0] | [HGlycine] | aqueous | +9.5700 | [[H][L1]]:+1 | SRD-46 | true |
| [L1].[z-1] | [Glycine] | aqueous | +0.0000 | [L1]:+1 | SRD-46 | true |
| [Co$+2].[z+2] | [Co]2+ | aqueous | +0.0000 | [Co$+2]:+1 | SRD-46 | true |
| [Co$+2].[OH].[z+1] | [Co(OH)]+ | aqueous | -9.7000 | [Co$+2]:+1, [OH]:+1 | SRD-46 | true |
| [Co$+2]2.[OH].[z+3] | [Co2(OH)]3+ | aqueous | -11.0000 | [Co$+2]:+2, [OH]:+1 | SRD-46 | true |
| [Co$+2].[OH]2.[z+0] | [Co(OH)2] | aqueous | -18.8000 | [Co$+2]:+1, [OH]:+2 | SRD-46 | true |
| [Co$+2].[OH]3.[z-1] | [Co(OH)3]- | aqueous | -31.5000 | [Co$+2]:+1, [OH]:+3 | SRD-46 | true |
| [Co$+2]4.[OH]4.[z+4] | [Co4(OH)4]4+ | aqueous | -30.5000 | [Co$+2]:+4, [OH]:+4 | SRD-46 | true |
| [Co$+2].[OH]4.[z-2] | [Co(OH)4]2- | aqueous | -46.3000 | [Co$+2]:+1, [OH]:+4 | SRD-46 | true |
| [Co$+2].[L1].[z+1] | [Co(Glyc)]+ | aqueous | +4.6700 | [Co$+2]:+1, [L1]:+1 | SRD-46 | true |
| [Co$+2].[L1]2.[z+0] | [Co(Glyc)2] | aqueous | +8.4600 | [Co$+2]:+1, [L1]:+2 | SRD-46 | true |
| [Co$+2].[L1]3.[z-1] | [Co(Glyc)3]- | aqueous | +10.9000 | [Co$+2]:+1, [L1]:+3 | SRD-46 | true |
| [Co$+2].[OH].[L1].[z+0] | [Co(Glyc)(OH)] | aqueous | -5.4200 | [Co$+2]:+1, [OH]:+1, [L1]:+1 | SRD-46 | true |
| [Co$+3].[z+3] | [Co]3+ | aqueous | +0.0000 | [Co$+3]:+1 | SRD-46 | true |
| [Co$+2].[OH]2.[z+0]_(s) | [Co(OH)2](s) | dissolution | -13.1000 | [Co$+2]:+1, [OH]:+2 | SRD-46 | true |
| [Co$+3].[OH]3.[z+0]_(s) | [Co(OH)3](s) | dissolution | +2.3000 | [Co$+3]:+1, [OH]:+3 | SRD-46 | true |
| Co$+0.z+0(s) | Co | dissolution | -0.0000 | Co$+0:+1 | Atlas | true |
