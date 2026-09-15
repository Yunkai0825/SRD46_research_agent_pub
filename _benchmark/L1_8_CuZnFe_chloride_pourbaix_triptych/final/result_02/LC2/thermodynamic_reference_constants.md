# Deterministic thermodynamic reference constants

- Source card: `free_energy_card.md`
- Selection: species rows whose final LC2 `include` field is `true`.
- Reaction convention: the source card defines `log_beta` as the cumulative formation constant from free components; each row below reports its `stoich` reaction basis and product species. For a protonated ligand, the card convention is `x H+ + L <=> HxL`. Only the `x = 1` single-protonation value is directly the conjugate-acid pKa; higher `x` values are cumulative protonation constants.
- Interpretation: values and source are copied exactly. Do not rename a generic `log_beta` as a pKa, dissolution constant, or another named constant unless that row's reaction/species definition supports it.

| species_id | product label | phase | log_beta | reaction basis (stoich) | source | include |
|---|---|---|---:|---|---|---|
| [H].[OH].[z+0] | [?] | aqueous | -0.2200 | [H]:+1, [OH]:+1 | SRD-46 | true |
| [L1].[z-1] | [Chloride ion] | aqueous | +0.0000 | [L1]:+1 | SRD-46 | true |
| [Zn$+2].[z+2] | [Zn]2+ | aqueous | +0.0000 | [Zn$+2]:+1 | SRD-46 | true |
| [Zn$+2].[OH].[z+1] | [Zn(OH)]+ | aqueous | -9.3000 | [Zn$+2]:+1, [OH]:+1 | SRD-46 | true |
| [Zn$+2].[OH]2.[z+0] | [Zn(OH)2] | aqueous | -15.8000 | [Zn$+2]:+1, [OH]:+2 | SRD-46 | true |
| [Zn$+2].[OH]3.[z-1] | [Zn(OH)3]- | aqueous | -28.1000 | [Zn$+2]:+1, [OH]:+3 | SRD-46 | true |
| [Zn$+2].[OH]4.[z-2] | [Zn(OH)4]2- | aqueous | -40.5000 | [Zn$+2]:+1, [OH]:+4 | SRD-46 | true |
| [Zn$+2].[L1]2.[z+0] | [Zn(Chlo)2] | aqueous | +0.6000 | [Zn$+2]:+1, [L1]:+2 | SRD-46 | true |
| [Zn$+2].[L1].[z+1] | [Zn(Chlo)]+ | aqueous | +0.4000 | [Zn$+2]:+1, [L1]:+1 | SRD-46 | true |
| Zn$+2.OH2.z+0(s) | ZnO (inactive) | dissolution | -9.6132 | Zn$+2:+1 H:-2 | Atlas | true |
| Zn$+2.OH2.z+0(s) | Zn(OH)2 (alpha) | dissolution | -10.7230 | Zn$+2:+1 H:-2 | Atlas | true |
| Zn$+0.z+0(s) | Zn | dissolution | -0.0000 | Zn$+0:+1 | Atlas | true |
