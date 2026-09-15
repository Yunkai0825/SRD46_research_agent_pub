# Deterministic thermodynamic reference constants

- Source card: `free_energy_card.md`
- Selection: species rows whose final LC2 `include` field is `true`.
- Reaction convention: the source card defines `log_beta` as the cumulative formation constant from free components; each row below reports its `stoich` reaction basis and product species. For a protonated ligand, the card convention is `x H+ + L <=> HxL`. Only the `x = 1` single-protonation value is directly the conjugate-acid pKa; higher `x` values are cumulative protonation constants.
- Interpretation: values and source are copied exactly. Do not rename a generic `log_beta` as a pKa, dissolution constant, or another named constant unless that row's reaction/species definition supports it.

| species_id | product label | phase | log_beta | reaction basis (stoich) | source | include |
|---|---|---|---:|---|---|---|
| [H].[OH].[z+0] | [?] | aqueous | -0.2200 | [H]:+1, [OH]:+1 | SRD-46 | true |
| [[H][L1]].[z+1] | [HAmmonia]+ | aqueous | +9.2600 | [[H][L1]]:+1 | SRD-46 | true |
| [L1].[z+0] | [Ammonia] | aqueous | +0.0000 | [L1]:+1 | SRD-46 | true |
| Ni$+2.z+2 | Ni2+ | aqueous | -0.0000 | Ni$+2:+1 | Atlas | true |
| [Ni$+2].[OH].[z+1] | [Ni(OH)]+ | aqueous | -10.4000 | [Ni$+2]:+1, [OH]:+1 | SRD-46 | true |
| [Ni$+2].[OH]2.[z+0] | [Ni(OH)2] | aqueous | -19.0000 | [Ni$+2]:+1, [OH]:+2 | SRD-46 | true |
| Ni$+2.OH3.z-1 | [HNiO2]- | aqueous | -29.7836 | Ni$+2:+1 H:-3 | Atlas | true |
| [Ni$+2]4.[OH]4.[z+4] | [Ni4(OH)4]4+ | aqueous | -27.7000 | [Ni$+2]:+4, [OH]:+4 | SRD-46 | true |
| [Ni$+2].[L1]5.[z+2] | [Ni(Ammo)5]2+ | aqueous | +8.3300 | [Ni$+2]:+1, [L1]:+5 | SRD-46 | true |
| [Ni$+2].[L1]6.[z+2] | [Ni(Ammo)6]2+ | aqueous | +8.3000 | [Ni$+2]:+1, [L1]:+6 | SRD-46 | true |
| [Ni$+2].[L1]4.[z+2] | [Ni(Ammo)4]2+ | aqueous | +7.6700 | [Ni$+2]:+1, [L1]:+4 | SRD-46 | true |
| [Ni$+2].[L1]3.[z+2] | [Ni(Ammo)3]2+ | aqueous | +6.5400 | [Ni$+2]:+1, [L1]:+3 | SRD-46 | true |
| [Ni$+2].[L1]2.[z+2] | [Ni(Ammo)2]2+ | aqueous | +4.8900 | [Ni$+2]:+1, [L1]:+2 | SRD-46 | true |
| [Ni$+2].[L1].[z+2] | [Ni(Ammo)]2+ | aqueous | +2.7300 | [Ni$+2]:+1, [L1]:+1 | SRD-46 | true |
| Ni$+2.OH2.z+0(s) | Ni(OH)2 | dissolution | -11.7141 | Ni$+2:+1 H:-2 | Atlas | true |
