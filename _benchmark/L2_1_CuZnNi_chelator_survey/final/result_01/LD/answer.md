Verdict: **supported**.

The calculation's key claims match the on-disk artifacts:

- The verdict file confirms 21/21 pH samples converged over pH 6.0–8.0, ionic strength 0.0212–0.0228 M, redox excluded, totals [Cu²⁺]=[Ni²⁺]=[Zn²⁺]=1.00 mM and [EDTA]=5.00 mM.
- Dominant species for each metal is [M(EDTA)(OH)]³⁻ across the entire pH 6–8 window (Cu peak 100% at pH 7.0, Zn peak 100% at pH 7.0, Ni peak 100% at pH 7.8), exactly as reported.
- Free-ligand distribution: HEDTA³⁻ peak 39.0% at pH 7.4, each M(EDTA)(OH) fraction 20.0% of ligand — matches the report.
- log[M²⁺] values from `_log_conc.csv` at pH 6.0 (−31.95 Cu, −32.07 Ni, −29.87 Zn) and the two-decade-per-pH-unit slope reproduce the free-metal table and the ~10^{+2.08} Zn/Cu and 10^{−0.12} Ni/Cu ratios cited.
- Solid phases (CuO, Cu(OH)₂, NiO, Zn(OH)₂) are pinned at the −50 log floor throughout, supporting the "no precipitation" claim.
- The Δlog β argument (30.18 Cu, 30.30 Ni, 28.10 Zn for [M(EDTA)(OH)]³⁻) is consistent with the free-species table's μ° values and reproduces the observed ratios.

The selectivity conclusion (EDTA is a saturating, essentially non-selective sequesterer for all three metals at pH 6–8, with only ~2 log units Cu-over-Zn preference and Ni bound marginally more tightly than Cu) follows directly from the data.
