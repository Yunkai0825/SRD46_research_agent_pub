# Deterministic thermodynamic reference constants

- Source card: `free_energy_card.md`
- Selection: species rows whose final LC2 `include` field is `true`.
- Reaction convention: the source card defines `log_beta` as the cumulative formation constant from free components; each row below reports its `stoich` reaction basis and product species. For a protonated ligand, the card convention is `x H+ + L <=> HxL`. Only the `x = 1` single-protonation value is directly the conjugate-acid pKa; higher `x` values are cumulative protonation constants.
- Interpretation: values and source are copied exactly. Do not rename a generic `log_beta` as a pKa, dissolution constant, or another named constant unless that row's reaction/species definition supports it.

| species_id | product label | phase | log_beta | reaction basis (stoich) | source | include |
|---|---|---|---:|---|---|---|
| [H].[OH].[z+0] | [?] | aqueous | -0.2200 | [H]:+1, [OH]:+1 | SRD-46 | true |
| [[H]3[L1]].[z+0] | [H3Citric acid] | aqueous | +12.9000 | [[H]3[L1]]:+1 | SRD-46 | true |
| [[H]2[L1]].[z-1] | [H2Citric acid]- | aqueous | +10.0000 | [[H]2[L1]]:+1 | SRD-46 | true |
| [[H][L1]].[z-2] | [HCitric acid]2- | aqueous | +5.6500 | [[H][L1]]:+1 | SRD-46 | true |
| [L1].[z-3] | [Citric acid] | aqueous | +0.0000 | [L1]:+1 | SRD-46 | true |
| [Zn$+2].[z+2] | [Zn]2+ | aqueous | +0.0000 | [Zn$+2]:+1 | SRD-46 | true |
| [Zn$+2].[OH].[z+1] | [Zn(OH)]+ | aqueous | -9.3000 | [Zn$+2]:+1, [OH]:+1 | SRD-46 | true |
| [Zn$+2].[OH]2.[z+0] | [Zn(OH)2] | aqueous | -15.8000 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | true |
| [Zn$+2].[OH]3.[z-1] | [Zn(OH)3]- | aqueous | -28.1000 | [Zn$+2]:+1, [OH]:+3 | SRD-46 | true |
| [Zn$+2].[OH]4.[z-2] | [Zn(OH)4]2- | aqueous | -40.5000 | [Zn$+2]:+1, [OH]:+4 | SRD-46 | true |
| [Zn$+2].[[H][L1]].[z+0] | [Zn(Citr)H] | aqueous | +8.6200 | [Zn$+2]:+1, [[H][L1]]:+1 | SRD-46 | true |
| [Zn$+2].[L1].[z-1] | [Zn(Citr)]- | aqueous | +4.7700 | [Zn$+2]:+1, [L1]:+1 | SRD-46 | true |
| [Zn$+2].[L1]2.[z-4] | [Zn(Citr)2]4- | aqueous | +6.8000 | [Zn$+2]:+1, [L1]:+2 | SRD-46 | true |
| [Zn$+2]2.[[H]-1[L1]]2.[z-4] | [Zn2(Citr)2(OH)2]4- | aqueous | -2.9000 | [Zn$+2]:+2, [[H]-1[L1]]:+2 | SRD-46 | true |
| Zn$+2.OH2.z+0(s) | ZnO (inactive) | dissolution | -9.6132 | Zn$+2:+1 H:-2 | Atlas | true |
| Zn$+2.OH2.z+0(s) | Zn(OH)2 (alpha) | dissolution | -10.7230 | Zn$+2:+1 H:-2 | Atlas | true |
| Zn$+2.OH2.z+0(s) | Zn(OH)2 (amorphous) | dissolution | -12.2492 | Zn$+2:+1 H:-2 | Atlas | true |
