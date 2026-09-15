# Deterministic thermodynamic reference constants

- Source card: `free_energy_card.md`
- Selection: species rows whose final LC2 `include` field is `true`.
- Reaction convention: the source card defines `log_beta` as the cumulative formation constant from free components; each row below reports its `stoich` reaction basis and product species. For a protonated ligand, the card convention is `x H+ + L <=> HxL`. Only the `x = 1` single-protonation value is directly the conjugate-acid pKa; higher `x` values are cumulative protonation constants.
- Interpretation: values and source are copied exactly. Do not rename a generic `log_beta` as a pKa, dissolution constant, or another named constant unless that row's reaction/species definition supports it.

| species_id | product label | phase | log_beta | reaction basis (stoich) | source | include |
|---|---|---|---:|---|---|---|
| [H].[OH].[z+0] | [?] | aqueous | -0.2200 | [H]:+1, [OH]:+1 | SRD-46 | true |
| [[H]3[L1]].[z+2] | [H3Histidine]2+ | aqueous | +13.4500 | [[H]3[L1]]:+1 | SRD-46 | true |
| [[H]2[L1]].[z+1] | [H2Histidine]+ | aqueous | +15.1500 | [[H]2[L1]]:+1 | SRD-46 | true |
| [[H][L1]].[z+0] | [HHistidine] | aqueous | +9.1000 | [[H][L1]]:+1 | SRD-46 | true |
| [L1].[z-1] | [Histidine] | aqueous | +0.0000 | [L1]:+1 | SRD-46 | true |
| [Co$+2].[z+2] | [Co]2+ | aqueous | +0.0000 | [Co$+2]:+1 | SRD-46 | true |
| [Co$+2].[OH].[z+1] | [Co(OH)]+ | aqueous | -9.7000 | [Co$+2]:+1, [OH]:+1 | SRD-46 | true |
| [Co$+2]2.[OH].[z+3] | [Co2(OH)]3+ | aqueous | -11.0000 | [Co$+2]:+2, [OH]:+1 | SRD-46 | true |
| [Co$+2].[OH]2.[z+0] | [Co(OH)2] | aqueous | -18.8000 | [Co$+2]:+1, [OH]:+2 | SRD-46 | true |
| [Co$+2].[OH]3.[z-1] | [Co(OH)3]- | aqueous | -31.5000 | [Co$+2]:+1, [OH]:+3 | SRD-46 | true |
| [Co$+2]4.[OH]4.[z+4] | [Co4(OH)4]4+ | aqueous | -30.5000 | [Co$+2]:+4, [OH]:+4 | SRD-46 | true |
| [Co$+2].[OH]4.[z-2] | [Co(OH)4]2- | aqueous | -46.3000 | [Co$+2]:+1, [OH]:+4 | SRD-46 | true |
| [Co$+2].[[H][L1]].[z+2] | [Co(Hist)H]2+ | aqueous | +11.4900 | [Co$+2]:+1, [[H][L1]]:+1 | SRD-46 | true |
| [Co$+2].[L1]2.[H].[z+1] | [Co(Hist)2H]+ | aqueous | +18.3700 | [Co$+2]:+1, [L1]:+2, [H]:+1 | SRD-46 | true |
| [Co$+2].[L1].[z+1] | [Co(Hist)]+ | aqueous | +6.8700 | [Co$+2]:+1, [L1]:+1 | SRD-46 | true |
| [Co$+2].[L1]2.[z+0] | [Co(Hist)2] | aqueous | +12.3800 | [Co$+2]:+1, [L1]:+2 | SRD-46 | true |
| [Cu$+2].[z+2] | [Cu]2+ | aqueous | +0.0000 | [Cu$+2]:+1 | SRD-46 | true |
| [Cu$+2].[OH].[z+1] | [Cu(OH)]+ | aqueous | -7.9000 | [Cu$+2]:+1, [OH]:+1 | SRD-46 | true |
| [Cu$+2]2.[OH]2.[z+2] | [Cu2(OH)2]2+ | aqueous | -11.2000 | [Cu$+2]:+2, [OH]:+2 | SRD-46 | true |
| [Cu$+2].[OH]2.[z+0] | [Cu(OH)2] | aqueous | -16.2000 | [Cu$+2]:+1, [OH]:+2 | SRD-46 | true |
| [Cu$+2]3.[OH]4.[z+2] | [Cu3(OH)4]2+ | aqueous | -22.5000 | [Cu$+2]:+3, [OH]:+4 | SRD-46 | true |
| [Cu$+2].[[H][L1]]2.[z+2] | [Cu(Hist)2H2]2+ | aqueous | +27.2300 | [Cu$+2]:+1, [[H][L1]]:+2 | SRD-46 | true |
| [Cu$+2].[L1]2.[H].[z+1] | [Cu(Hist)2H]+ | aqueous | +23.8300 | [Cu$+2]:+1, [L1]:+2, [H]:+1 | SRD-46 | true |
| [Cu$+2].[[H][L1]].[z+2] | [Cu(Hist)H]2+ | aqueous | +14.2000 | [Cu$+2]:+1, [[H][L1]]:+1 | SRD-46 | true |
| [Cu$+2].[L1].[z+1] | [Cu(Hist)]+ | aqueous | +10.1600 | [Cu$+2]:+1, [L1]:+1 | SRD-46 | true |
| [Cu$+2].[L1]2.[z+0] | [Cu(Hist)2] | aqueous | +18.0700 | [Cu$+2]:+1, [L1]:+2 | SRD-46 | true |
| [Cu$+2].[OH].[L1].[z+0] | [Cu(Hist)(OH)] | aqueous | +2.1600 | [Cu$+2]:+1, [OH]:+1, [L1]:+1 | SRD-46 | true |
| [Cu$+2].[OH].[L1]2.[z-1] | [Cu(Hist)2(OH)]- | aqueous | +6.6700 | [Cu$+2]:+1, [OH]:+1, [L1]:+2 | SRD-46 | true |
| [Cu$+2]2.[OH]2.[L1]2.[z+0] | [Cu2(Hist)2(OH)2] | aqueous | +8.0000 | [Cu$+2]:+2, [OH]:+2, [L1]:+2 | SRD-46 | true |
| [Ni$+2].[z+2] | [Ni]2+ | aqueous | +0.0000 | [Ni$+2]:+1 | SRD-46 | true |
| [Ni$+2].[OH].[z+1] | [Ni(OH)]+ | aqueous | -10.4000 | [Ni$+2]:+1, [OH]:+1 | SRD-46 | true |
| [Ni$+2].[OH]2.[z+0] | [Ni(OH)2] | aqueous | -19.0000 | [Ni$+2]:+1, [OH]:+2 | SRD-46 | true |
| [Ni$+2].[OH]3.[z-1] | [Ni(OH)3]- | aqueous | -30.0000 | [Ni$+2]:+1, [OH]:+3 | SRD-46 | true |
| [Ni$+2]4.[OH]4.[z+4] | [Ni4(OH)4]4+ | aqueous | -27.7000 | [Ni$+2]:+4, [OH]:+4 | SRD-46 | true |
| [Ni$+2].[[H][L1]].[z+2] | [Ni(Hist)H]2+ | aqueous | +12.2800 | [Ni$+2]:+1, [[H][L1]]:+1 | SRD-46 | true |
| [Ni$+2].[L1]2.[H].[z+1] | [Ni(Hist)2H]+ | aqueous | -20.7700 | [Ni$+2]:+1, [L1]:+2, [H]:+1 | SRD-46 | true |
| [Ni$+2].[L1].[z+1] | [Ni(Hist)]+ | aqueous | +8.6600 | [Ni$+2]:+1, [L1]:+1 | SRD-46 | true |
| [Ni$+2].[L1]2.[z+0] | [Ni(Hist)2] | aqueous | -15.7700 | [Ni$+2]:+1, [L1]:+2 | SRD-46 | true |
| [Co$+2].[OH]2.[z+0]_(s) | [Co(OH)2](s) | dissolution | -13.1000 | [Co$+2]:+1, [OH]:+2 | SRD-46 | true |
| [Cu$+2].[OH]2.[[z+0(s)[2]]] | [Cu(OH)2](s) | dissolution | -8.6800 | [Cu$+2]:+1, [OH]:+2 | SRD-46 | true |
| [Ni$+2].[OH]2.[z+0]_(s) | [Ni(OH)2](s) | dissolution | -12.8000 | [Ni$+2]:+1, [OH]:+2 | SRD-46 | true |
