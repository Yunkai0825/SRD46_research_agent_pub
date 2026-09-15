## Answer

I can't answer this question from the SRD-46 pipeline, because the question is about **kinetics** and SRD-46 is a **thermodynamic** database.

Specifically, you're asking for:

- **Formation rate constants** (k_f, units of M⁻¹ s⁻¹ or similar) for Cu–glycine, Cu–EDTA, Zn–glycine, and Zn–EDTA complex formation, and
- **Half-lives** for Cu²⁺ and Zn²⁺ to redistribute between the two ligands at pH 6.

None of these are stored in NIST SRD-46. SRD-46 contains only **equilibrium** quantities — stepwise and cumulative stability constants (log K, log β), enthalpies, and related thermodynamic data for metal–ligand complexation. It contains no rate constants, no activation energies, and no relaxation times, so the pipeline cannot compute a formation rate or a half-life for you, no matter how the question is phrased. Running the pipeline would only return the equilibrium distribution of Cu(II) and Zn(II) between glycine and EDTA at pH 6 — i.e. *where* the system ends up, not *how fast* it gets there.

For context on what is chemically expected (this is general knowledge, not a pipeline result):

- Cu(II) and Zn(II) complexation with simple aminocarboxylates like glycine and EDTA is generally **fast** on laboratory timescales. Water-exchange rates on Cu²⁺ (~10⁹ s⁻¹) and Zn²⁺ (~10⁷–10⁸ s⁻¹) are very high, and Eigen–Wilkins-type formation rate constants for these metals with unprotonated aminocarboxylate donors are typically 10⁶–10⁹ M⁻¹ s⁻¹.
- Ligand-exchange (redistribution) between glycine and EDTA at pH 6 and millimolar concentrations would typically equilibrate on a timescale ranging from milliseconds (direct associative pathways) to seconds or minutes (if it must proceed through proton-assisted dissociation of a protonated EDTA intermediate, which matters at pH 6 where H₂EDTA²⁻ / HEDTA³⁻ are significant).

But the **specific numbers** you asked for — the actual k_f values and the actual half-life at your stated conditions — must come from a **kinetics** data source (e.g. the primary stopped-flow / T-jump literature for Cu–EDTA and Zn–EDTA exchange, or compilations by Margerum, Wilkins, or Eigen), not from SRD-46.

If you'd instead like the **equilibrium** partitioning — i.e. at pH 6, how the 1 mM Cu(II) and 1 mM Zn(II) split between glycine, EDTA, hydroxide, and free aquo forms in that single pot — I can dispatch that calculation for you. Just say the word.

## Validation status: incomplete

## Evidence

- No calculation call was made: the requested quantities (formation rate constants, half-life for ligand redistribution) are kinetic and lie outside SRD-46, which is a compilation of equilibrium stability constants and related thermodynamic data.
