Verdict: **supported**.

The calculation's key claims were checked against the verdict, envelope-derived dominance windows, precipitation block, and frac_ligand.csv:

- Convergence 101/101 and I range 0.0044–0.0574 M match `state_metrics.csv`/verdict.
- Cu(II) dominance regions (Cu²⁺ 2.0–3.7; [Cu(Glyc)]⁺ 3.7–4.8; [Cu(Glyc)₂] 4.8–11.6; Cu(OH)₂ 11.6–12.0), peak values, and crossover pH values reproduce the verdict block verbatim.
- Zn(II) dominance windows and peaks (including [Zn(Ammo)₄]²⁺ peak 12.3 % at pH 9.3 and Zn(OH)₂(α) peak 99 % at pH 11.2) match the verdict.
- Precipitation onsets (Zn(OH)₂(α) first at pH 7.40, Cu(OH)₂ at pH 11.40) reproduce the verdict "Precipitation" block.
- Glycine partitioning (Cu(Glyc)₂ peaking at 20 % of glycine pool at pH 8.2, Zn-glycinates ≤ 5.9 %) is consistent with the L1 speciation table.
- Ammonia pool is overwhelmingly HAmmonia⁺/Ammonia and metal-ammine fractions are negligible, as confirmed by the frac_ligand.csv rows.
- Reference log β values cited (Cu(Glyc)₂ +15.10, Cu(Ammo)₄ +12.30, Zn(Glyc)₂ +9.19) are consistent with the μ° values in the verdict free-energy table (they reproduce these β's on conversion).

The qualitative conclusions — Cu(II) is masked by bis-glycinate to ~pH 11.5, Zn(II) hydrolyses first near pH 7.4, neither metal is ever ammine-dominated, and Cu owns the glycine sink while Zn is the (very minor) main user of ammonia — all follow from the data.
