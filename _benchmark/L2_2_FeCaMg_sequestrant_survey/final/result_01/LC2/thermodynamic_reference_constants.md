# Deterministic thermodynamic reference constants

- Source card: `free_energy_card.md`
- Selection: species rows whose final LC2 `include` field is `true`.
- Reaction convention: the source card defines `log_beta` as the cumulative formation constant from free components; each row below reports its `stoich` reaction basis and product species. For a protonated ligand, the card convention is `x H+ + L <=> HxL`. Only the `x = 1` single-protonation value is directly the conjugate-acid pKa; higher `x` values are cumulative protonation constants.
- Interpretation: values and source are copied exactly. Do not rename a generic `log_beta` as a pKa, dissolution constant, or another named constant unless that row's reaction/species definition supports it.

| species_id | product label | phase | log_beta | reaction basis (stoich) | source | include |
|---|---|---|---:|---|---|---|
| [H].[OH].[z+0] | [?] | aqueous | -0.2200 | [H]:+1, [OH]:+1 | SRD-46 | true |
| [[H]8[L1]].[z+3] | [H8DTPA]3+ | aqueous | +25.6800 | [[H]8[L1]]:+1 | SRD-46 | true |
| [[H]7[L1]].[z+2] | [H7DTPA]2+ | aqueous | +25.7800 | [[H]7[L1]]:+1 | SRD-46 | true |
| [[H]6[L1]].[z+1] | [H6DTPA]+ | aqueous | +26.4800 | [[H]6[L1]]:+1 | SRD-46 | true |
| [[H]5[L1]].[z+0] | [H5DTPA] | aqueous | +28.0800 | [[H]5[L1]]:+1 | SRD-46 | true |
| [[H]4[L1]].[z-1] | [H4DTPA]- | aqueous | +26.0800 | [[H]4[L1]]:+1 | SRD-46 | true |
| [[H]3[L1]].[z-2] | [H3DTPA]2- | aqueous | +23.3800 | [[H]3[L1]]:+1 | SRD-46 | true |
| [[H]2[L1]].[z-3] | [H2DTPA]3- | aqueous | +19.1000 | [[H]2[L1]]:+1 | SRD-46 | true |
| [[H][L1]].[z-4] | [HDTPA]4- | aqueous | +10.5000 | [[H][L1]]:+1 | SRD-46 | true |
| [L1].[z-5] | [DTPA] | aqueous | +0.0000 | [L1]:+1 | SRD-46 | true |
| [Ca$+2].[z+2] | [Ca]2+ | aqueous | +0.0000 | [Ca$+2]:+1 | SRD-46 | true |
| [Ca$+2].[OH].[z+1] | [Ca(OH)]+ | aqueous | -13.0400 | [Ca$+2]:+1, [OH]:+1 | SRD-46 | true |
| [Ca$+2].[[H][L1]].[z-2] | [Ca(DTPA)H]2- | aqueous | +16.8600 | [Ca$+2]:+1, [[H][L1]]:+1 | SRD-46 | true |
| [Ca$+2]2.[L1].[z-1] | [Ca2(DTPA)]- | aqueous | +12.3500 | [Ca$+2]:+2, [L1]:+1 | SRD-46 | true |
| [Ca$+2].[L1].[z-3] | [Ca(DTPA)]3- | aqueous | +10.7500 | [Ca$+2]:+1, [L1]:+1 | SRD-46 | true |
| [Fe$+2].[z+2] | [Fe]2+ | aqueous | +0.0000 | [Fe$+2]:+1 | SRD-46 | true |
| [Fe$+2].[OH].[z+1] | [Fe(OH)]+ | aqueous | -9.8000 | [Fe$+2]:+1, [OH]:+1 | SRD-46 | true |
| [Fe$+2].[OH]2.[z+0] | [Fe(OH)2] | aqueous | -35.5000 | [Fe$+2]:+1, [OH]:+2 | SRD-46 | true |
| [Fe$+2].[OH]3.[z-1] | [Fe(OH)3]- | aqueous | -29.0000 | [Fe$+2]:+1, [OH]:+3 | SRD-46 | true |
| [Fe$+2].[OH]4.[z-2] | [Fe(OH)4]2- | aqueous | -46.0000 | [Fe$+2]:+1, [OH]:+4 | SRD-46 | true |
| [Fe$+2].[[H][L1]].[z-2] | [Fe(DTPA)H]2- | aqueous | +21.5000 | [Fe$+2]:+1, [[H][L1]]:+1 | SRD-46 | true |
| [Fe$+2]2.[L1].[z-1] | [Fe2(DTPA)]- | aqueous | +19.1800 | [Fe$+2]:+2, [L1]:+1 | SRD-46 | true |
| [Fe$+2].[L1].[z-3] | [Fe(DTPA)]3- | aqueous | +16.2000 | [Fe$+2]:+1, [L1]:+1 | SRD-46 | true |
| [Fe$+2].[OH].[L1].[z-4] | [Fe(DTPA)(OH)]4- | aqueous | +7.4300 | [Fe$+2]:+1, [OH]:+1, [L1]:+1 | SRD-46 | true |
| [Fe$+2].[OH]2.[L1].[z-5] | [Fe(DTPA)(OH)2]5- | aqueous | -1.9800 | [Fe$+2]:+1, [OH]:+2, [L1]:+1 | SRD-46 | true |
| [Fe$+3].[z+3] | [Fe]3+ | aqueous | +0.0000 | [Fe$+3]:+1 | SRD-46 | true |
| [Fe$+3].[OH].[z+2] | [Fe(OH)]2+ | aqueous | -2.7300 | [Fe$+3]:+1, [OH]:+1 | SRD-46 | true |
| [Fe$+3]2.[OH]2.[z+4] | [Fe2(OH)2]4+ | aqueous | -2.8600 | [Fe$+3]:+2, [OH]:+2 | SRD-46 | true |
| [Fe$+3].[OH]2.[z+1] | [Fe(OH)2]+ | aqueous | -6.1500 | [Fe$+3]:+1, [OH]:+2 | SRD-46 | true |
| [Fe$+3]3.[OH]4.[z+5] | [Fe3(OH)4]5+ | aqueous | -6.3000 | [Fe$+3]:+3, [OH]:+4 | SRD-46 | true |
| [Fe$+3].[OH]4.[z-1] | [Fe(OH)4]- | aqueous | -21.6000 | [Fe$+3]:+1, [OH]:+4 | SRD-46 | true |
| [Fe$+3].[[H][L1]].[z-1] | [Fe(DTPA)H]- | aqueous | +31.5600 | [Fe$+3]:+1, [[H][L1]]:+1 | SRD-46 | true |
| [Fe$+3].[L1].[z-2] | [Fe(DTPA)]2- | aqueous | +28.0000 | [Fe$+3]:+1, [L1]:+1 | SRD-46 | true |
| [Fe$+3].[OH].[L1].[z-3] | [Fe(DTPA)(OH)]3- | aqueous | +18.3400 | [Fe$+3]:+1, [OH]:+1, [L1]:+1 | SRD-46 | true |
| [Mg$+2].[z+2] | [Mg]2+ | aqueous | +0.0000 | [Mg$+2]:+1 | SRD-46 | true |
| [Mg$+2].[OH].[z+1] | [Mg(OH)]+ | aqueous | -11.4000 | [Mg$+2]:+1, [OH]:+1 | SRD-46 | true |
| [Mg$+2]2.[OH].[z+3] | [Mg2(OH)]3+ | aqueous | -11.7000 | [Mg$+2]:+2, [OH]:+1 | SRD-46 | true |
| [Mg$+2]4.[OH]4.[z+4] | [Mg4(OH)4]4+ | aqueous | -39.9000 | [Mg$+2]:+4, [OH]:+4 | SRD-46 | true |
| [Mg$+2].[[H][L1]].[z-2] | [Mg(DTPA)H]2- | aqueous | +16.2300 | [Mg$+2]:+1, [[H][L1]]:+1 | SRD-46 | true |
| [Mg$+2]2.[L1].[z-1] | [Mg2(DTPA)]- | aqueous | +11.3400 | [Mg$+2]:+2, [L1]:+1 | SRD-46 | true |
| [Mg$+2].[L1].[z-3] | [Mg(DTPA)]3- | aqueous | +9.2700 | [Mg$+2]:+1, [L1]:+1 | SRD-46 | true |
| [Ca$+2].[OH]2.[z+0]_(s) | [Ca(OH)2](s) | dissolution | -22.8100 | [Ca$+2]:+1, [OH]:+2 | SRD-46 | true |
| [Fe$+2].[OH]2.[z+0]_(s) | [Fe(OH)2](s) | dissolution | -13.5700 | [Fe$+2]:+1, [OH]:+2 | SRD-46 | true |
| [Fe$+3].[OH]3.[[z+0(s)[2]]] | [FeO(OH)(s,alpha)] | dissolution | -0.5000 | [Fe$+3]:+1, [H]:-3 | SRD-46 | true |
| [Fe$+3].[OH]3.[[z+0(s)[3]]] | [Fe(OH)3](s) | dissolution | -3.2000 | [Fe$+3]:+1, [OH]:+3 | SRD-46 | true |
| [Mg$+2].[OH]2.[z+0]_(s) | [Mg(OH)2(s,brucite)] | dissolution | -16.8600 | [Mg$+2]:+1, [OH]:+2 | SRD-46 | true |
