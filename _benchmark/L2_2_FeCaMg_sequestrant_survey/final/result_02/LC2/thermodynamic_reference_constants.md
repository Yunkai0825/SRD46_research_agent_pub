# Deterministic thermodynamic reference constants

- Source card: `free_energy_card.md`
- Selection: species rows whose final LC2 `include` field is `true`.
- Reaction convention: the source card defines `log_beta` as the cumulative formation constant from free components; each row below reports its `stoich` reaction basis and product species. For a protonated ligand, the card convention is `x H+ + L <=> HxL`. Only the `x = 1` single-protonation value is directly the conjugate-acid pKa; higher `x` values are cumulative protonation constants.
- Interpretation: values and source are copied exactly. Do not rename a generic `log_beta` as a pKa, dissolution constant, or another named constant unless that row's reaction/species definition supports it.

| species_id | product label | phase | log_beta | reaction basis (stoich) | source | include |
|---|---|---|---:|---|---|---|
| [H].[OH].[z+0] | [?] | aqueous | -0.2200 | [H]:+1, [OH]:+1 | SRD-46 | true |
| [[H]4[L1]].[z+1] | [H4HEDTA]+ | aqueous | +16.1850 | [[H]4[L1]]:+1 | SRD-46 | true |
| [[H]3[L1]].[z+0] | [H3HEDTA] | aqueous | +17.7850 | [[H]3[L1]]:+1 | SRD-46 | true |
| [[H]2[L1]].[z-1] | [H2HEDTA]- | aqueous | +15.1650 | [[H]2[L1]]:+1 | SRD-46 | true |
| [[H][L1]].[z-2] | [HHEDTA]2- | aqueous | +9.7850 | [[H][L1]]:+1 | SRD-46 | true |
| [L1].[z-3] | [HEDTA] | aqueous | +0.0000 | [L1]:+1 | SRD-46 | true |
| [Ca$+2].[z+2] | [Ca]2+ | aqueous | +0.0000 | [Ca$+2]:+1 | SRD-46 | true |
| [Ca$+2].[OH].[z+1] | [Ca(OH)]+ | aqueous | -13.0400 | [Ca$+2]:+1, [OH]:+1 | SRD-46 | true |
| [Ca$+2].[L1].[z-1] | [Ca(HEDT)]- | aqueous | +8.1000 | [Ca$+2]:+1, [L1]:+1 | SRD-46 | true |
| [Fe$+2].[z+2] | [Fe]2+ | aqueous | +0.0000 | [Fe$+2]:+1 | SRD-46 | true |
| [Fe$+2].[OH]3.[z-1] | [Fe(OH)3]- | aqueous | -29.0000 | [Fe$+2]:+1, [OH]:+3 | SRD-46 | true |
| [Fe$+3].[z+3] | [Fe]3+ | aqueous | +0.0000 | [Fe$+3]:+1 | SRD-46 | true |
| [Fe$+3].[OH].[z+2] | [Fe(OH)]2+ | aqueous | -2.7300 | [Fe$+3]:+1, [OH]:+1 | SRD-46 | true |
| [Fe$+3]2.[OH]2.[z+4] | [Fe2(OH)2]4+ | aqueous | -2.8600 | [Fe$+3]:+2, [OH]:+2 | SRD-46 | true |
| [Fe$+3].[OH]2.[z+1] | [Fe(OH)2]+ | aqueous | -4.6000 | [Fe$+3]:+1, [OH]:+2 | SRD-46 | true |
| [Fe$+3]3.[OH]4.[z+5] | [Fe3(OH)4]5+ | aqueous | -6.3000 | [Fe$+3]:+3, [OH]:+4 | SRD-46 | true |
| [Fe$+3].[OH]4.[z-1] | [Fe(OH)4]- | aqueous | -21.6000 | [Fe$+3]:+1, [OH]:+4 | SRD-46 | true |
| [Fe$+3].[L1].[z+0] | [Fe(HEDT)] | aqueous | +19.7000 | [Fe$+3]:+1, [L1]:+1 | SRD-46 | true |
| [Fe$+3].[OH].[L1].[z-1] | [Fe(HEDT)(OH)]- | aqueous | +15.8200 | [Fe$+3]:+1, [OH]:+1, [L1]:+1 | SRD-46 | true |
| [Fe$+3].[OH]2.[L1].[z-2] | [Fe(HEDT)(OH)2]2- | aqueous | +6.9900 | [Fe$+3]:+1, [OH]:+2, [L1]:+1 | SRD-46 | true |
| [Fe$+3].[OH]3.[L1].[z-3] | [Fe(HEDT)(OH)3]3- | aqueous | -3.0100 | [Fe$+3]:+1, [OH]:+3, [L1]:+1 | SRD-46 | true |
| [Mg$+2].[z+2] | [Mg]2+ | aqueous | +0.0000 | [Mg$+2]:+1 | SRD-46 | true |
| [Mg$+2].[OH].[z+1] | [Mg(OH)]+ | aqueous | -11.4000 | [Mg$+2]:+1, [OH]:+1 | SRD-46 | true |
| [Mg$+2]2.[OH].[z+3] | [Mg2(OH)]3+ | aqueous | -11.7000 | [Mg$+2]:+2, [OH]:+1 | SRD-46 | true |
| [Mg$+2]4.[OH]4.[z+4] | [Mg4(OH)4]4+ | aqueous | -39.9000 | [Mg$+2]:+4, [OH]:+4 | SRD-46 | true |
| [Mg$+2].[L1].[z-1] | [Mg(HEDT)]- | aqueous | +7.0000 | [Mg$+2]:+1, [L1]:+1 | SRD-46 | true |
| [Ca$+2].[OH]2.[z+0]_(s) | [Ca(OH)2](s) | dissolution | -22.8100 | [Ca$+2]:+1, [OH]:+2 | SRD-46 | true |
| [Fe$+2].[OH]2.[z+0]_(s) | [Fe(OH)2](s) | dissolution | -13.5700 | [Fe$+2]:+1, [OH]:+2 | SRD-46 | true |
| [Fe$+3].[OH]3.[[z+0(s)[1]]] | [(Fe2O3)0.5(s,alpha)] | dissolution | +0.7000 | [Fe$+3]:+1, [H]:-3 | SRD-46 | true |
| [Fe$+3].[OH]3.[[z+0(s)[2]]] | [FeO(OH)(s,alpha)] | dissolution | -0.5000 | [Fe$+3]:+1, [H]:-3 | SRD-46 | true |
| [Fe$+3].[OH]3.[[z+0(s)[3]]] | [Fe(OH)3](s) | dissolution | -3.2000 | [Fe$+3]:+1, [OH]:+3 | SRD-46 | true |
| [Mg$+2].[OH]2.[z+0]_(s) | [Mg(OH)2(s,brucite)] | dissolution | -16.8500 | [Mg$+2]:+1, [OH]:+2 | SRD-46 | true |
