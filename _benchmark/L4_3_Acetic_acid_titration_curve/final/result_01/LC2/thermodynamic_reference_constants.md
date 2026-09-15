# Deterministic thermodynamic reference constants

- Source card: `free_energy_card.md`
- Selection: species rows whose final LC2 `include` field is `true`.
- Reaction convention: the source card defines `log_beta` as the cumulative formation constant from free components; each row below reports its `stoich` reaction basis and product species. For a protonated ligand, the card convention is `x H+ + L <=> HxL`. Only the `x = 1` single-protonation value is directly the conjugate-acid pKa; higher `x` values are cumulative protonation constants.
- Interpretation: values and source are copied exactly. Do not rename a generic `log_beta` as a pKa, dissolution constant, or another named constant unless that row's reaction/species definition supports it.

| species_id | product label | phase | log_beta | reaction basis (stoich) | source | include |
|---|---|---|---:|---|---|---|
| [H].[OH].[z+0] | [?] | aqueous | -0.2200 | [H]:+1, [OH]:+1 | SRD-46 | true |
| [[H][L1]].[z+0] | [HAcetic acid] | aqueous | +4.5600 | [[H][L1]]:+1 | SRD-46 | true |
| [L1].[z-1] | [Acetic acid] | aqueous | +0.0000 | [L1]:+1 | SRD-46 | true |
| [Na$+1].[z+1] | [Na]+ | aqueous | +0.0000 | [Na$+1]:+1 | SRD-46 | true |
| Na$+1.OH.z+0(s) | NaOH | dissolution | -21.3895 | Na$+1:+1 H:-1 | Atlas | true |
