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
| [Pb$+2].[z+2] | [Pb]2+ | aqueous | +0.0000 | [Pb$+2]:+1 | SRD-46 | true |
| [Pb$+2]2.[OH].[z+3] | [Pb2(OH)]3+ | aqueous | -6.2000 | [Pb$+2]:+2, [OH]:+1 | SRD-46 | true |
| [Pb$+2].[OH].[z+1] | [Pb(OH)]+ | aqueous | -8.0000 | [Pb$+2]:+1, [OH]:+1 | SRD-46 | true |
| [Pb$+2].[OH]2.[z+0] | [Pb(OH)2] | aqueous | -17.1000 | [Pb$+2]:+1, [OH]:+2 | SRD-46 | true |
| [Pb$+2].[OH]3.[z-1] | [Pb(OH)3]- | aqueous | -28.1000 | [Pb$+2]:+1, [OH]:+3 | SRD-46 | true |
| [Pb$+2]4.[OH]4.[z+4] | [Pb4(OH)4]4+ | aqueous | -18.5000 | [Pb$+2]:+4, [OH]:+4 | SRD-46 | true |
| [Pb$+2]3.[OH]4.[z+2] | [Pb3(OH)4]2+ | aqueous | -23.9000 | [Pb$+2]:+3, [OH]:+4 | SRD-46 | true |
| [Pb$+2]6.[OH]8.[z+4] | [Pb6(OH)8]4+ | aqueous | -40.7000 | [Pb$+2]:+6, [OH]:+8 | SRD-46 | true |
| [Pb$+2].[[H][L1]].[z-2] | [Pb(DTPA)H]2- | aqueous | +23.3200 | [Pb$+2]:+1, [[H][L1]]:+1 | SRD-46 | true |
| [Pb$+2]2.[L1].[z-1] | [Pb2(DTPA)]- | aqueous | +22.2100 | [Pb$+2]:+2, [L1]:+1 | SRD-46 | true |
| [Pb$+2].[L1].[z-3] | [Pb(DTPA)]3- | aqueous | +18.8000 | [Pb$+2]:+1, [L1]:+1 | SRD-46 | true |
| [Zn$+2].[z+2] | [Zn]2+ | aqueous | +0.0000 | [Zn$+2]:+1 | SRD-46 | true |
| [Zn$+2].[OH].[z+1] | [Zn(OH)]+ | aqueous | -9.3000 | [Zn$+2]:+1, [OH]:+1 | SRD-46 | true |
| [Zn$+2].[OH]2.[z+0] | [Zn(OH)2] | aqueous | -15.8000 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | true |
| [Zn$+2].[OH]3.[z-1] | [Zn(OH)3]- | aqueous | -28.1000 | [Zn$+2]:+1, [OH]:+3 | SRD-46 | true |
| [Zn$+2].[OH]4.[z-2] | [Zn(OH)4]2- | aqueous | -40.5000 | [Zn$+2]:+1, [OH]:+4 | SRD-46 | true |
| [Zn$+2].[[H][L1]].[z-2] | [Zn(DTPA)H]2- | aqueous | +23.8000 | [Zn$+2]:+1, [[H][L1]]:+1 | SRD-46 | true |
| [Zn$+2]2.[L1].[z-1] | [Zn2(DTPA)]- | aqueous | +22.6800 | [Zn$+2]:+2, [L1]:+1 | SRD-46 | true |
| [Zn$+2].[L1].[z-3] | [Zn(DTPA)]3- | aqueous | +18.2000 | [Zn$+2]:+1, [L1]:+1 | SRD-46 | true |
| [Ca$+2].[OH]2.[z+0]_(s) | [Ca(OH)2](s) | dissolution | -22.8100 | [Ca$+2]:+1, [OH]:+2 | SRD-46 | true |
| Zn$+2.OH2.z+0(s) | Zn(OH)2 (alpha) | dissolution | -10.7230 | Zn$+2:+1 H:-2 | Atlas | true |
