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
| [L2].[z-1] | [Chloride ion] | aqueous | +0.0000 | [L2]:+1 | SRD-46 | true |
| [Cd$+2].[z+2] | [Cd]2+ | aqueous | +0.0000 | [Cd$+2]:+1 | SRD-46 | true |
| [Cd$+2]2.[OH].[z+3] | [Cd2(OH)]3+ | aqueous | -9.4000 | [Cd$+2]:+2, [OH]:+1 | SRD-46 | true |
| [Cd$+2].[OH].[z+1] | [Cd(OH)]+ | aqueous | -10.0000 | [Cd$+2]:+1, [OH]:+1 | SRD-46 | true |
| [Cd$+2].[OH]2.[z+0] | [Cd(OH)2] | aqueous | -20.3000 | [Cd$+2]:+1, [OH]:+2 | SRD-46 | true |
| [Cd$+2].[OH]3.[z-1] | [Cd(OH)3]- | aqueous | -31.7000 | [Cd$+2]:+1, [OH]:+3 | SRD-46 | true |
| [Cd$+2]4.[OH]4.[z+4] | [Cd4(OH)4]4+ | aqueous | -32.8000 | [Cd$+2]:+4, [OH]:+4 | SRD-46 | true |
| [Cd$+2].[OH]4.[z-2] | [Cd(OH)4]2- | aqueous | -64.7000 | [Cd$+2]:+1, [OH]:+4 | SRD-46 | true |
| [Cd$+2].[L1]4.[z+2] | [Cd(Ammo)4]2+ | aqueous | +6.7200 | [Cd$+2]:+1, [L1]:+4 | SRD-46 | true |
| [Cd$+2].[L1]3.[z+2] | [Cd(Ammo)3]2+ | aqueous | +5.9000 | [Cd$+2]:+1, [L1]:+3 | SRD-46 | true |
| [Cd$+2].[L1]2.[z+2] | [Cd(Ammo)2]2+ | aqueous | +4.5600 | [Cd$+2]:+1, [L1]:+2 | SRD-46 | true |
| [Cd$+2].[L1].[z+2] | [Cd(Ammo)]2+ | aqueous | +2.5700 | [Cd$+2]:+1, [L1]:+1 | SRD-46 | true |
| [Cd$+2].[L2]3.[z-1] | [Cd(Chlo)3]- | aqueous | +2.4000 | [Cd$+2]:+1, [L2]:+3 | SRD-46 | true |
| [Cd$+2].[L2]2.[z+0] | [Cd(Chlo)2] | aqueous | +2.0500 | [Cd$+2]:+1, [L2]:+2 | SRD-46 | true |
| [Cd$+2].[L2].[z+1] | [Cd(Chlo)]+ | aqueous | +1.5200 | [Cd$+2]:+1, [L2]:+1 | SRD-46 | true |
| [Zn$+2].[z+2] | [Zn]2+ | aqueous | +0.0000 | [Zn$+2]:+1 | SRD-46 | true |
| [Zn$+2].[OH].[z+1] | [Zn(OH)]+ | aqueous | -9.3000 | [Zn$+2]:+1, [OH]:+1 | SRD-46 | true |
| [Zn$+2].[OH]2.[z+0] | [Zn(OH)2] | aqueous | -15.8000 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | true |
| [Zn$+2].[OH]3.[z-1] | [Zn(OH)3]- | aqueous | -28.1000 | [Zn$+2]:+1, [OH]:+3 | SRD-46 | true |
| [Zn$+2].[OH]4.[z-2] | [Zn(OH)4]2- | aqueous | -40.5000 | [Zn$+2]:+1, [OH]:+4 | SRD-46 | true |
| [Zn$+2].[L1]4.[z+2] | [Zn(Ammo)4]2+ | aqueous | +8.8900 | [Zn$+2]:+1, [L1]:+4 | SRD-46 | true |
| [Zn$+2].[L1]3.[z+2] | [Zn(Ammo)3]2+ | aqueous | +6.8600 | [Zn$+2]:+1, [L1]:+3 | SRD-46 | true |
| [Zn$+2].[L1]2.[z+2] | [Zn(Ammo)2]2+ | aqueous | +4.5000 | [Zn$+2]:+1, [L1]:+2 | SRD-46 | true |
| [Zn$+2].[L1].[z+2] | [Zn(Ammo)]2+ | aqueous | +2.3300 | [Zn$+2]:+1, [L1]:+1 | SRD-46 | true |
| [Zn$+2].[L2].[z+1] | [Zn(Chlo)]+ | aqueous | -0.3000 | [Zn$+2]:+1, [L2]:+1 | SRD-46 | true |
| [Zn$+2].[L2]2.[z+0] | [Zn(Chlo)2] | aqueous | -0.3000 | [Zn$+2]:+1, [L2]:+2 | SRD-46 | true |
| [Cd$+2].[OH]2.[[z+0(s)[1]]] | [Cd(OH)2(s,beta)] | dissolution | -13.6500 | [Cd$+2]:+1, [OH]:+2 | SRD-46 | true |
| Cd$+2.OH2.z+0(s) | CdO | dissolution | -15.7458 | Cd$+2:+1 H:-2 | Atlas | true |
| Cd$+0.z+0(s) | Cd | dissolution | -0.0000 | Cd$+0:+1 | Atlas | true |
| Zn$+2.OH2.z+0(s) | ZnO (inactive) | dissolution | -9.6132 | Zn$+2:+1 H:-2 | Atlas | true |
| Zn$+2.OH2.z+0(s) | Zn(OH)2 (alpha) | dissolution | -10.7230 | Zn$+2:+1 H:-2 | Atlas | true |
| Zn$+0.z+0(s) | Zn | dissolution | -0.0000 | Zn$+0:+1 | Atlas | true |
