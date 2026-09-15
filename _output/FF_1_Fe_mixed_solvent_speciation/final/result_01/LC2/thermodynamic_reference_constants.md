# Deterministic thermodynamic reference constants

- Source card: `free_energy_card.md`
- Selection: species rows whose final LC2 `include` field is `true`.
- Reaction convention: the source card defines `log_beta` as the cumulative formation constant from free components; each row below reports its `stoich` reaction basis and product species. For a protonated ligand, the card convention is `x H+ + L <=> HxL`. Only the `x = 1` single-protonation value is directly the conjugate-acid pKa; higher `x` values are cumulative protonation constants.
- Interpretation: values and source are copied exactly. Do not rename a generic `log_beta` as a pKa, dissolution constant, or another named constant unless that row's reaction/species definition supports it.

| species_id | product label | phase | log_beta | reaction basis (stoich) | source | include |
|---|---|---|---:|---|---|---|
| [H].[OH].[z+0] | [?] | aqueous | -0.2200 | [H]:+1, [OH]:+1 | SRD-46 | true |
| [L1].[z+0] | [DMF] | aqueous | +0.0000 | [L1]:+1 | SRD-46 | true |
| [Fe$+2].[z+2] | [Fe]2+ | aqueous | +0.0000 | [Fe$+2]:+1 | SRD-46 | true |
| [Fe$+2].[OH].[z+1] | [Fe(OH)]+ | aqueous | -9.8000 | [Fe$+2]:+1, [OH]:+1 | SRD-46 | true |
| [Fe$+2].[OH]2.[z+0] | [Fe(OH)2] | aqueous | -35.5000 | [Fe$+2]:+1, [OH]:+2 | SRD-46 | true |
| [Fe$+2].[OH]3.[z-1] | [Fe(OH)3]- | aqueous | -29.0000 | [Fe$+2]:+1, [OH]:+3 | SRD-46 | true |
| [Fe$+2].[OH]4.[z-2] | [Fe(OH)4]2- | aqueous | -46.0000 | [Fe$+2]:+1, [OH]:+4 | SRD-46 | true |
| [Fe$+2].[L1]4.[z+2] | [Fe(DMF)4]2+ | aqueous | +2.1000 | [Fe$+2]:+1, [L1]:+4 | SRD46 query estimated values | true |
| [Fe$+2].[L1]3.[z+2] | [Fe(DMF)3]2+ | aqueous | +1.8000 | [Fe$+2]:+1, [L1]:+3 | SRD46 query estimated values | true |
| [Fe$+2].[L1]2.[z+2] | [Fe(DMF)2]2+ | aqueous | +1.5000 | [Fe$+2]:+1, [L1]:+2 | SRD46 query estimated values | true |
| [Fe$+2].[L1].[z+2] | [Fe(DMF)]2+ | aqueous | +1.0000 | [Fe$+2]:+1, [L1]:+1 | SRD46 query estimated values | true |
| [Fe$+3].[z+3] | [Fe]3+ | aqueous | +0.0000 | [Fe$+3]:+1 | SRD-46 | true |
| [Fe$+3].[OH].[z+2] | [Fe(OH)]2+ | aqueous | -2.7300 | [Fe$+3]:+1, [OH]:+1 | SRD-46 | true |
| [Fe$+3]2.[OH]2.[z+4] | [Fe2(OH)2]4+ | aqueous | -2.8600 | [Fe$+3]:+2, [OH]:+2 | SRD-46 | true |
| [Fe$+3].[OH]2.[z+1] | [Fe(OH)2]+ | aqueous | -4.6000 | [Fe$+3]:+1, [OH]:+2 | SRD-46 | true |
| [Fe$+3]3.[OH]4.[z+5] | [Fe3(OH)4]5+ | aqueous | -6.3000 | [Fe$+3]:+3, [OH]:+4 | SRD-46 | true |
| [Fe$+3].[OH]4.[z-1] | [Fe(OH)4]- | aqueous | -21.6000 | [Fe$+3]:+1, [OH]:+4 | SRD-46 | true |
| [Fe$+3].[L1].[z+3] | [Fe(DMF)]3+ | aqueous | +0.8000 | [Fe$+3]:+1, [L1]:+1 | SRD46 query estimated values | true |
| Fe$+6.OH8.z-2 | [FeO4]2- | aqueous | -0.0000 | Fe$+6:+1 H:-8 | Atlas | true |
| [Fe$+2].[OH]2.[z+0]_(s) | [Fe(OH)2](s) | dissolution | -13.5700 | [Fe$+2]:+1, [OH]:+2 | SRD-46 | true |
| Fe$+2.Fe$+3(2).OH8.z+0(s) | Fe3O4 (anh.) | dissolution | -7.1252 | Fe$+2:+1 Fe$+3:+2 H:-8 | Atlas | true |
| [Fe$+3].[OH]3.[[z+0(s)[1]]] | [(Fe2O3)0.5(s,alpha)] | dissolution | +0.7000 | [Fe$+3]:+1, [H]:-3 | SRD-46 | true |
| [Fe$+3].[OH]3.[[z+0(s)[2]]] | [FeO(OH)(s,alpha)] | dissolution | -0.5000 | [Fe$+3]:+1, [H]:-3 | SRD-46 | true |
| [Fe$+3].[OH]3.[[z+0(s)[3]]] | [Fe(OH)3](s) | dissolution | -3.2000 | [Fe$+3]:+1, [OH]:+3 | SRD-46 | true |
| Fe$+0.z+0(s) | Fe | dissolution | -0.0000 | Fe$+0:+1 | Atlas | true |
