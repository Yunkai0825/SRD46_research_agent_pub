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
| Ni$+2.z+2 | Ni2+ | aqueous | -0.0000 | Ni$+2:+1 | Atlas | true |
| [Ni$+2].[OH].[z+1] | [Ni(OH)]+ | aqueous | -10.4000 | [Ni$+2]:+1, [OH]:+1 | SRD-46 | true |
| [Ni$+2].[OH]2.[z+0] | [Ni(OH)2] | aqueous | -19.0000 | [Ni$+2]:+1, [OH]:+2 | SRD-46 | true |
| [Ni$+2].[OH]3.[z-1] | [Ni(OH)3]- | aqueous | -30.0000 | [Ni$+2]:+1, [OH]:+3 | SRD-46 | true |
| [Ni$+2]4.[OH]4.[z+4] | [Ni4(OH)4]4+ | aqueous | -27.7000 | [Ni$+2]:+4, [OH]:+4 | SRD-46 | true |
| [Ni$+2].[L1].[z+1] | [Ni(Glyc)]+ | aqueous | +5.7400 | [Ni$+2]:+1, [L1]:+1 | SRD-46 | true |
| [Ni$+2].[L1]2.[z+0] | [Ni(Glyc)2] | aqueous | +10.5800 | [Ni$+2]:+1, [L1]:+2 | SRD-46 | true |
| [Ni$+2].[L1]3.[z-1] | [Ni(Glyc)3]- | aqueous | +14.1000 | [Ni$+2]:+1, [L1]:+3 | SRD-46 | true |
| Ni$+2.OH2.z+0(s) | Ni(OH)2 | dissolution | -11.7141 | Ni$+2:+1 H:-2 | Atlas | true |
| Ni$+2(3).OH8.z+0(s) | Ni3O4.2H2O | dissolution | -151.0072 | Ni$+2:+3 H:-8 | Atlas | true |
| Ni$+3(2).OH6.z+0(s) | Ni2O3.H2O | dissolution | +99.9067 | Ni$+3:+2 H:-6 | Atlas | true |
| Ni$+4.OH4.z+0(s) | NiO2.2H2O | dissolution | -0.0000 | Ni$+4:+1 H:-4 | Atlas | true |
| Ni$+0.z+0(s) | Ni | dissolution | -0.0000 | Ni$+0:+1 | Atlas | true |
