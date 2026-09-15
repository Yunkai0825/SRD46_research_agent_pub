# Deterministic thermodynamic reference constants

- Source card: `free_energy_card.md`
- Selection: species rows whose final LC2 `include` field is `true`.
- Reaction convention: the source card defines `log_beta` as the cumulative formation constant from free components; each row below reports its `stoich` reaction basis and product species. For a protonated ligand, the card convention is `x H+ + L <=> HxL`. Only the `x = 1` single-protonation value is directly the conjugate-acid pKa; higher `x` values are cumulative protonation constants.
- Interpretation: values and source are copied exactly. Do not rename a generic `log_beta` as a pKa, dissolution constant, or another named constant unless that row's reaction/species definition supports it.

| species_id | product label | phase | log_beta | reaction basis (stoich) | source | include |
|---|---|---|---:|---|---|---|
| [H].[OH].[z+0] | [?] | aqueous | -0.2200 | [H]:+1, [OH]:+1 | SRD-46 | true |
| [[H]3[L1]].[z+1] | [H3Cysteine]+ | aqueous | +16.5800 | [[H]3[L1]]:+1 | SRD-46 | true |
| [[H]2[L1]].[z+0] | [H2Cysteine] | aqueous | +18.4800 | [[H]2[L1]]:+1 | SRD-46 | true |
| [[H][L1]].[z-1] | [HCysteine]- | aqueous | +10.3000 | [[H][L1]]:+1 | SRD-46 | true |
| [L1].[z-2] | [Cysteine] | aqueous | +0.0000 | [L1]:+1 | SRD-46 | true |
| [Co$+2].[z+2] | [Co]2+ | aqueous | +0.0000 | [Co$+2]:+1 | SRD-46 | true |
| [Co$+2].[OH].[z+1] | [Co(OH)]+ | aqueous | -9.7000 | [Co$+2]:+1, [OH]:+1 | SRD-46 | true |
| [Co$+2]2.[OH].[z+3] | [Co2(OH)]3+ | aqueous | -11.0000 | [Co$+2]:+2, [OH]:+1 | SRD-46 | true |
| [Co$+2].[OH]2.[z+0] | [Co(OH)2] | aqueous | -18.8000 | [Co$+2]:+1, [OH]:+2 | SRD-46 | true |
| [Co$+2].[OH]3.[z-1] | [Co(OH)3]- | aqueous | -31.5000 | [Co$+2]:+1, [OH]:+3 | SRD-46 | true |
| [Co$+2]4.[OH]4.[z+4] | [Co4(OH)4]4+ | aqueous | -30.5000 | [Co$+2]:+4, [OH]:+4 | SRD-46 | true |
| [Co$+2].[OH]4.[z-2] | [Co(OH)4]2- | aqueous | -46.3000 | [Co$+2]:+1, [OH]:+4 | SRD-46 | true |
| [Co$+2].[L1].[z+0] | [Co(Cyst)] | aqueous | +8.1400 | [Co$+2]:+1, [L1]:+1 | SRD-46 | true |
| [Co$+2].[L1]2.[z-2] | [Co(Cyst)2]2- | aqueous | +14.4800 | [Co$+2]:+1, [L1]:+2 | SRD-46 | true |
| [Co$+2]2.[L1]3.[z-2] | [Co2(Cyst)3]2- | aqueous | +26.3000 | [Co$+2]:+2, [L1]:+3 | SRD-46 | true |
| [Co$+2]3.[L1]4.[z-2] | [Co3(Cyst)4]2- | aqueous | +38.0000 | [Co$+2]:+3, [L1]:+4 | SRD-46 | true |
| [Co$+3].[z+3] | [Co]3+ | aqueous | +0.0000 | [Co$+3]:+1 | SRD-46 | true |
| [Cu$+1].[z+1] | [Cu]+ | aqueous | +0.0000 | [Cu$+1]:+1 | SRD-46 | true |
| [Cu$+2].[z+2] | [Cu]2+ | aqueous | +0.0000 | [Cu$+2]:+1 | SRD-46 | true |
| [Cu$+2].[OH].[z+1] | [Cu(OH)]+ | aqueous | -7.9000 | [Cu$+2]:+1, [OH]:+1 | SRD-46 | true |
| [Cu$+2]2.[OH]2.[z+2] | [Cu2(OH)2]2+ | aqueous | -11.2000 | [Cu$+2]:+2, [OH]:+2 | SRD-46 | true |
| [Cu$+2].[OH]2.[z+0] | [Cu(OH)2] | aqueous | -16.2000 | [Cu$+2]:+1, [OH]:+2 | SRD-46 | true |
| Cu$+2.OH3.z-1 | [HCuO2]- | aqueous | -26.7048 | Cu$+2:+1 H:-3 | Atlas | true |
| [Cu$+2]3.[OH]4.[z+2] | [Cu3(OH)4]2+ | aqueous | -22.5000 | [Cu$+2]:+3, [OH]:+4 | SRD-46 | true |
| Cu$+2.OH4.z-2 | [CuO2]2- | aqueous | -39.8410 | Cu$+2:+1 H:-4 | Atlas | true |
| [Ni$+2].[z+2] | [Ni]2+ | aqueous | +0.0000 | [Ni$+2]:+1 | SRD-46 | true |
| [Ni$+2].[OH].[z+1] | [Ni(OH)]+ | aqueous | -10.4000 | [Ni$+2]:+1, [OH]:+1 | SRD-46 | true |
| [Ni$+2].[OH]2.[z+0] | [Ni(OH)2] | aqueous | -19.0000 | [Ni$+2]:+1, [OH]:+2 | SRD-46 | true |
| [Ni$+2].[OH]3.[z-1] | [Ni(OH)3]- | aqueous | -30.0000 | [Ni$+2]:+1, [OH]:+3 | SRD-46 | true |
| [Ni$+2]4.[OH]4.[z+4] | [Ni4(OH)4]4+ | aqueous | -27.7000 | [Ni$+2]:+4, [OH]:+4 | SRD-46 | true |
| [Ni$+2].[[H][L1]].[z+1] | [Ni(Cyst)H]+ | aqueous | +14.6400 | [Ni$+2]:+1, [[H][L1]]:+1 | SRD-46 | true |
| [Ni$+2].[L1].[z+0] | [Ni(Cyst)] | aqueous | +9.7900 | [Ni$+2]:+1, [L1]:+1 | SRD-46 | true |
| [Ni$+2].[L1]2.[z-2] | [Ni(Cyst)2]2- | aqueous | +19.9000 | [Ni$+2]:+1, [L1]:+2 | SRD-46 | true |
| [Ni$+2]2.[L1]3.[z-2] | [Ni2(Cyst)3]2- | aqueous | +33.0000 | [Ni$+2]:+2, [L1]:+3 | SRD-46 | true |
| [Ni$+2]3.[L1]4.[z-2] | [Ni3(Cyst)4]2- | aqueous | +45.7000 | [Ni$+2]:+3, [L1]:+4 | SRD-46 | true |
| [Co$+2].[OH]2.[z+0]_(s) | [Co(OH)2](s) | dissolution | -13.1000 | [Co$+2]:+1, [OH]:+2 | SRD-46 | true |
| [Co$+3].[OH]3.[z+0]_(s) | [Co(OH)3](s) | dissolution | +2.3000 | [Co$+3]:+1, [OH]:+3 | SRD-46 | true |
| [Cu$+1].[OH].[z+0]_(s) | [(Cu2O)0.5](s) | dissolution | +0.7000 | [Cu$+1]:+1, [H]:-1 | SRD-46 | true |
| [Cu$+2].[OH]2.[[z+0(s)[2]]] | [Cu(OH)2](s) | dissolution | -8.6800 | [Cu$+2]:+1, [OH]:+2 | SRD-46 | true |
| [Ni$+2].[OH]2.[z+0]_(s) | [Ni(OH)2](s) | dissolution | -12.8000 | [Ni$+2]:+1, [OH]:+2 | SRD-46 | true |
