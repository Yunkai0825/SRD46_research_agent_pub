# Deterministic thermodynamic reference constants

- Source card: `free_energy_card.md`
- Selection: species rows whose final LC2 `include` field is `true`.
- Reaction convention: the source card defines `log_beta` as the cumulative formation constant from free components; each row below reports its `stoich` reaction basis and product species. For a protonated ligand, the card convention is `x H+ + L <=> HxL`. Only the `x = 1` single-protonation value is directly the conjugate-acid pKa; higher `x` values are cumulative protonation constants.
- Interpretation: values and source are copied exactly. Do not rename a generic `log_beta` as a pKa, dissolution constant, or another named constant unless that row's reaction/species definition supports it.

| species_id | product label | phase | log_beta | reaction basis (stoich) | source | include |
|---|---|---|---:|---|---|---|
| [H].[OH].[z+0] | [?] | aqueous | -0.2200 | [H]:+1, [OH]:+1 | SRD-46 | true |
| [L1].[z-1] | [Chloride ion] | aqueous | +0.0000 | [L1]:+1 | SRD-46 | true |
| [Cd$+2].[z+2] | [Cd]2+ | aqueous | +0.0000 | [Cd$+2]:+1 | SRD-46 | true |
| [Cd$+2]2.[OH].[z+3] | [Cd2(OH)]3+ | aqueous | -8.9400 | [Cd$+2]:+2, [OH]:+1 | SRD-46 | true |
| [Cd$+2].[OH].[z+1] | [Cd(OH)]+ | aqueous | -10.1000 | [Cd$+2]:+1, [OH]:+1 | SRD-46 | true |
| [Cd$+2].[OH]2.[z+0] | [Cd(OH)2] | aqueous | -20.3000 | [Cd$+2]:+1, [OH]:+2 | SRD-46 | true |
| [Cd$+2].[OH]3.[z-1] | [Cd(OH)3]- | aqueous | -31.7000 | [Cd$+2]:+1, [OH]:+3 | SRD-46 | true |
| [Cd$+2]4.[OH]4.[z+4] | [Cd4(OH)4]4+ | aqueous | -32.8000 | [Cd$+2]:+4, [OH]:+4 | SRD-46 | true |
| [Cd$+2].[OH]4.[z-2] | [Cd(OH)4]2- | aqueous | -44.0000 | [Cd$+2]:+1, [OH]:+4 | SRD-46 | true |
| [Cd$+2].[L1]2.[z+0] | [Cd(Chlo)2] | aqueous | +2.6000 | [Cd$+2]:+1, [L1]:+2 | SRD-46 | true |
| [Cd$+2].[L1]3.[z-1] | [Cd(Chlo)3]- | aqueous | +2.4000 | [Cd$+2]:+1, [L1]:+3 | SRD-46 | true |
| [Cd$+2].[L1].[z+1] | [Cd(Chlo)]+ | aqueous | +1.5200 | [Cd$+2]:+1, [L1]:+1 | SRD-46 | true |
| [Cd$+2].[OH]2.[[z+0(s)[1]]] | [Cd(OH)2(s,beta)] | dissolution | -13.6500 | [Cd$+2]:+1, [OH]:+2 | SRD-46 | true |
| Cd$+0.z+0(s) | Cd | dissolution | -0.0000 | Cd$+0:+1 | Atlas | true |
