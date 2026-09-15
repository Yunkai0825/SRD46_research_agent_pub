Verdict: **supported**.

The calculation's claims are consistent with the persisted solver artifacts:

- **Convergence & system parameters** (verdict.md): 101/101 grid points converged, calculated I range 0.00796–0.0365 M, pH 2–12, redox excluded, totals 1 mM Zn(II) and 5 mM EDTA — all match L1's numbers.
- **Dominant Zn species**: verdict.md's Zn²⁺ speciation block reports `pH 2.0–12.0 → [Zn(EDTA)(OH)]3-` with a 100.0 % peak at pH 10.3, exactly what L1 asserts.
- **EDTA ligand ladder**: verdict.md gives dominance windows H3EDTA⁻ (2.0–2.1), H2EDTA²⁻ (2.1–5.6), HEDTA³⁻ (5.6–9.4), EDTA⁴⁻ (9.4–12.0) — identical to L1's wording.
- **Mixed-hydroxo peak in ligand accounting**: verdict.md lists `[Zn(EDTA)(OH)]3- peak 20.0% at pH 10.3`, matching L1's stoichiometric argument (1 mM of 5 mM L bound).
- **Reference constants** cited by L1 are traced to `../LC2/thermodynamic_reference_constants.md`: log β([Zn(EDTA)(OH)]³⁻) = +28.10, log β([Zn(EDTA)]²⁻) = +16.50, cumulative EDTA protonation β values 20.92 / 18.90 / 16.38 / 10.19 — all copied correctly, with the correct cumulative-vs-pKa distinction respected.
- **No precipitation** claim is consistent with the dominance-only Zn(II) block and with the amorphous Zn(OH)2 dissolution log β = -12.25 being unattainable given sub-attomolar free Zn²⁺.
- The pH-7 free [Zn²⁺] value (~5×10⁻³³ M) was not individually digit-verified, but is qualitatively consistent with the mixed-hydroxo chelate dominance and ligand excess; no contradicting evidence appears in the reviewed artifacts.

The selectivity-matrix implication (EDTA does not discriminate Cu vs Zn at pH 7) is a reasonable summary of this single-metal run and is properly framed as pending comparison with the Cu- and Ni-EDTA columns. No hints required.
