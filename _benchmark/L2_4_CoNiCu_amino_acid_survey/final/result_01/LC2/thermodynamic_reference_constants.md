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
| [Cu$+1].[z+1] | [Cu]+ | aqueous | +0.0000 | [Cu$+1]:+1 | SRD-46 | true |
| [Cu$+1].[L1]2.[z-1] | [Cu(Glyc)2]- | aqueous | +10.1000 | [Cu$+1]:+1, [L1]:+2 | SRD-46 | true |
| [Cu$+2].[z+2] | [Cu]2+ | aqueous | +0.0000 | [Cu$+2]:+1 | SRD-46 | true |
| [Cu$+2].[OH].[z+1] | [Cu(OH)]+ | aqueous | -7.9000 | [Cu$+2]:+1, [OH]:+1 | SRD-46 | true |
| [Cu$+2]2.[OH]2.[z+2] | [Cu2(OH)2]2+ | aqueous | -11.2000 | [Cu$+2]:+2, [OH]:+2 | SRD-46 | true |
| [Cu$+2].[OH]2.[z+0] | [Cu(OH)2] | aqueous | -16.2000 | [Cu$+2]:+1, [OH]:+2 | SRD-46 | true |
| Cu$+2.OH3.z-1 | [HCuO2]- | aqueous | -26.7048 | Cu$+2:+1 H:-3 | Atlas | true |
| [Cu$+2]3.[OH]4.[z+2] | [Cu3(OH)4]2+ | aqueous | -22.5000 | [Cu$+2]:+3, [OH]:+4 | SRD-46 | true |
| Cu$+2.OH4.z-2 | [CuO2]2- | aqueous | -39.8410 | Cu$+2:+1 H:-4 | Atlas | true |
| [Cu$+2].[L1].[z+1] | [Cu(Glyc)]+ | aqueous | +8.1900 | [Cu$+2]:+1, [L1]:+1 | SRD-46 | true |
| [Cu$+2].[L1]2.[z+0] | [Cu(Glyc)2] | aqueous | +15.1000 | [Cu$+2]:+1, [L1]:+2 | SRD-46 | true |
| [Ni$+2].[z+2] | [Ni]2+ | aqueous | +0.0000 | [Ni$+2]:+1 | SRD-46 | true |
| [Ni$+2].[OH].[z+1] | [Ni(OH)]+ | aqueous | -10.4000 | [Ni$+2]:+1, [OH]:+1 | SRD-46 | true |
| [Ni$+2].[OH]2.[z+0] | [Ni(OH)2] | aqueous | -19.0000 | [Ni$+2]:+1, [OH]:+2 | SRD-46 | true |
| [Ni$+2].[OH]3.[z-1] | [Ni(OH)3]- | aqueous | -30.0000 | [Ni$+2]:+1, [OH]:+3 | SRD-46 | true |
| [Ni$+2]4.[OH]4.[z+4] | [Ni4(OH)4]4+ | aqueous | -27.7000 | [Ni$+2]:+4, [OH]:+4 | SRD-46 | true |
| [Ni$+2].[L1].[z+1] | [Ni(Glyc)]+ | aqueous | +5.7400 | [Ni$+2]:+1, [L1]:+1 | SRD-46 | true |
| [Ni$+2].[L1]2.[z+0] | [Ni(Glyc)2] | aqueous | +10.5800 | [Ni$+2]:+1, [L1]:+2 | SRD-46 | true |
| [Ni$+2].[L1]3.[z-1] | [Ni(Glyc)3]- | aqueous | +14.1000 | [Ni$+2]:+1, [L1]:+3 | SRD-46 | true |
| [Co$+2].[OH]2.[z+0]_(s) | [Co(OH)2](s) | dissolution | -13.1000 | [Co$+2]:+1, [OH]:+2 | SRD-46 | true |
| Co$+2.OH2.z+0(s) | CoO | dissolution | -15.0201 | Co$+2:+1 H:-2 | Atlas | true |
| Co$+2(3).OH8.z+0(s) | Co3O4 | dissolution | -71.3436 | Co$+2:+3 H:-8 | Atlas | true |
| [Co$+3].[OH]3.[z+0]_(s) | [Co(OH)3](s) | dissolution | +2.3000 | [Co$+3]:+1, [OH]:+3 | SRD-46 | true |
| Co$+4.OH4.z+0(s) | CoO2 | dissolution | -0.0000 | Co$+4:+1 H:-4 | Atlas | true |
| Co$+0.z+0(s) | Co | dissolution | -0.0000 | Co$+0:+1 | Atlas | true |
| [Cu$+1].[OH].[z+0]_(s) | [(Cu2O)0.5](s) | dissolution | +0.7000 | [Cu$+1]:+1, [H]:-1 | SRD-46 | true |
| [Cu$+2].[OH]2.[[z+0(s)[1]]] | [CuO](s) | dissolution | -7.6500 | [Cu$+2]:+1, [H]:-2 | SRD-46 | true |
| [Cu$+2].[OH]2.[[z+0(s)[2]]] | [Cu(OH)2](s) | dissolution | -8.6800 | [Cu$+2]:+1, [OH]:+2 | SRD-46 | true |
| Cu$+0.z+0(s) | Cu | dissolution | -0.0000 | Cu$+0:+1 | Atlas | true |
| Ni$+2.OH2.z+0(s) | NiO | dissolution | -11.9413 | Ni$+2:+1 H:-2 | Atlas | true |
| [Ni$+2].[OH]2.[z+0]_(s) | [Ni(OH)2](s) | dissolution | -12.8000 | [Ni$+2]:+1, [OH]:+2 | SRD-46 | true |
| Ni$+2(3).OH8.z+0(s) | Ni3O4.2H2O | dissolution | -151.0072 | Ni$+2:+3 H:-8 | Atlas | true |
| Ni$+3(2).OH6.z+0(s) | Ni2O3.H2O | dissolution | +99.9067 | Ni$+3:+2 H:-6 | Atlas | true |
| Ni$+4.OH4.z+0(s) | NiO2.2H2O | dissolution | -0.0000 | Ni$+4:+1 H:-4 | Atlas | true |
| Ni$+0.z+0(s) | Ni | dissolution | -0.0000 | Ni$+0:+1 | Atlas | true |
