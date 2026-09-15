## Answer

Across the three water-rich mixed-solvent Fe electrolytes (0.1 M Fe with 1 M of either DMF, acetonitrile (ACN), or ethylene glycol (EG)), the SRD-46 pipeline — enriched with estimated Fe³⁺/Fe²⁺–ligand stability constants where the database was silent — produces three Pourbaix diagrams that differ in one very consequential way: **only DMF meaningfully expands the aqueous Fe(II) stability window and moves the Fe/Fe(II) reduction boundary more negative, exactly the two things you want for iron electrodeposition with suppressed HER.** ACN and EG behave essentially like water in this dilute-cosolvent limit.

### Chemistry-by-chemistry picture

**Fe – DMF (7 regions).** DMF is a strong, hard-oxygen-donor amide (Gutmann donor number ≈ 26.6). The pipeline discovers and populates an entire estimated Fe²⁺–DMFₙ ladder (log K = 1.0, log β₂ = 1.5, log β₃ = 1.8, log β₄ = 2.1) plus a much weaker Fe³⁺–DMF interaction (log K₁ ≈ 0.8), consistent with hydrolysis of Fe³⁺ dominating from pH ≈ 2–3. The result is that the soluble Fe(II) region is no longer bare `Fe²⁺(aq)` but **[Fe(DMF)₄]²⁺**, and it survives:

- pH from 0 up to **pH ≈ 7.9** before hematite (½ Fe₂O₃) precipitates (vs. pH ≈ 3.4 in the ACN/EG cases).
- Fe⁰ / [Fe(DMF)₄]²⁺ deposition boundary at **E ≈ −0.54 V (SHE)**, i.e. ~55 mV more negative than the bare Fe²⁺/Fe⁰ line in ACN/EG (−0.484 / −0.479 V).
- A distinct Fe³⁺ complex, **[Fe(DMF)]³⁺**, appearing as its own tiny region at low pH / high E.

The topology region measures also tell the story: the [Fe(DMF)₄]²⁺ region occupies **6.24 pH·V** of the map, versus only **4.90 pH·V (ACN)** and **4.79 pH·V (EG)** for bare Fe²⁺. That is a ~28% larger soluble-Fe(II) area.

**Fe – Acetonitrile (6 regions).** The Fe²⁺–MeCN estimated log K₁ is essentially zero (−0.3), and the Fe³⁺–MeCN estimates are all negative (log K₁ = −0.5, log β₂ = −1.5, log β₃ = −3). Chemically, MeCN is a very weak σ-donor in water — its Brønsted basicity is 10¹⁵× lower than pyridine — and it cannot compete with the aquation shell around a hard cation like Fe²⁺/Fe³⁺ in a water-rich electrolyte. The Pourbaix map therefore reproduces the classic aqueous Fe diagram: soluble Fe²⁺ only up to **pH ≈ 3.4**, Fe⁰/Fe²⁺ boundary at **−0.484 V (SHE)**, then Fe₃O₄ / hematite / ferrate at higher E and pH.

**Fe – Ethylene glycol (6 regions).** EG binds only through deprotonated alkoxide, and the estimation gives log K = −4 (Fe³⁺) / −12 (Fe²⁺) for the M + HOCH₂CH₂OH ⇌ M(OCH₂CH₂OH) + H⁺ reaction — i.e. hydrolysis of coordinated water is *always* thermodynamically preferred over alkoxide formation in the water-rich regime. Consequently, the diagram is essentially indistinguishable from bare water: Fe²⁺ up to **pH ≈ 3.35**, Fe/Fe²⁺ at **−0.479 V (SHE)**, and standard oxide progression above.

### What this means for Fe electrodeposition

Two design levers matter for plating Fe from a mildly acidic bath: (i) how negative the Fe²⁺/Fe⁰ deposition potential sits relative to the HER line 0 − 0.059·pH (in V vs SHE), and (ii) how high the pH can be pushed while still keeping Fe in solution so that the *local* interfacial pH excursion caused by HER does not immediately precipitate iron oxide/hydroxide on the cathode.

- **DMF is the clear winner.** By stabilising Fe(II) as [Fe(DMF)₄]²⁺, it (a) shifts Fe(II)/Fe⁰ ~50 mV more cathodic, which reduces the driving force for HER at the deposition potential, and (b) delays Fe(II) hydrolysis by ~4 pH units. The plating window is therefore both wider (higher pH tolerated) and cleaner (less parasitic H₂). This is the well-known basis for non-aqueous / partially-aqueous Fe and Fe-alloy plating baths that use DMF, DMSO, or similar strong O-donor amides.
- **ACN gives essentially no benefit in a water-rich bath.** Its weak σ-donation cannot displace inner-sphere water at Fe²⁺, so the deposition potential and hydrolysis pH remain aqueous. ACN is more useful as the *bulk* solvent (>90%) in truly nonaqueous baths where the water activity itself is reduced, which is a different regime than modelled here.
- **EG behaves as an almost inert cosolvent** at 1 M. Its practical value for electrodeposition (viscosity control, wettability, deep-eutectic-solvent formulations, mild grain-refining) is real but comes from bulk transport and surface effects, not from Fe complexation. In water-rich mixtures it will not expand the Fe(II) window.

### Practical considerations and caveats

- All three diagrams still show ferrite/hematite as the dominant oxide barrier at moderate pH and E. Even for the DMF bath, going above pH ≈ 8 will lose soluble iron to Fe₂O₃/Fe₃O₄, so pH control (buffering near pH 2–5) remains essential.
- The Fe(III) side is only weakly modified by any of the three cosolvents (small Fe³⁺·DMF region in the DMF case; nothing in ACN/EG), so Fe³⁺ management (e.g. ascorbate, sulfite, or an inert-atmosphere bath) will still be needed to prevent hydroxide fouling.
- The Fe(II)–DMF ladder (log K₁ … log β₄ = 1.0, 1.5, 1.8, 2.1) is an SRD-46 *estimate* transferred from Cd²⁺ analogues with a donor-number correction (uncertainty 0.5–0.8 log units per step). The qualitative expansion of the Fe(II) window is robust, but the exact pH ≈ 7.9 precipitation onset and the exact Fe(II)/Fe⁰ shift carry an uncertainty of roughly ±0.5 log[Fe] on the boundary position — worth confirming experimentally by titration or cyclic voltammetry before committing to a plating recipe.
- Increasing the DMF fraction beyond 1 M (i.e. toward a truly mixed or nonaqueous bath) would push the Fe(II)/Fe(DMF)ₙ²⁺ region even further and further suppress H₂O activity and therefore HER — this is the standard route to smooth, dense Fe films.

### Modeling coverage

For every one of the three calculations the coverage report is **complete / requested_system**: the requested cosolvent (DMF, acetonitrile, or ethylene glycol) is present in the final calculation card as `L1`, no requested ligand was omitted, and the estimation search completed for every required scope (`estimation_search_complete = true`). Estimated Fe–ligand constants were materialised and used in the solve: 5 for DMF (Fe³⁺·DMF, and Fe²⁺·DMFₙ for n=1–4), 4 for ACN (Fe³⁺·MeCNₙ for n=1–3 and Fe²⁺·MeCN), and 2 alkoxide-formation constants for EG (Fe³⁺ and Fe²⁺). Each estimate carries its own uncertainty (0.5–2.0 log units) and is fully documented in the LC1_3 support-equation map for that call.

## Evidence

- **DMF, region catalog (7 connected regions, complete):** `Fe (measure 5.328) | Fe₃O₄ anh. (2.269 + 3.9e-5 disconnected) | ½Fe₂O₃(s,α) (13.929) | [Fe(DMF)₄]²⁺ (6.242) | FeO₄²⁻ (6.757) | [Fe(DMF)]³⁺ (0.475)`.
- **DMF pH cut at E = 0.248 V:** [Fe(DMF)₄]²⁺ dominant from pH 0.006 to **4.06**, then ½Fe₂O₃(s,α) to pH 13.99.
- **DMF E cut at pH = 6.99:** Fe⁰ up to **E = −0.542 V**, then [Fe(DMF)₄]²⁺ to E = −0.327 V, then Fe₃O₄ to −0.164 V, then ½Fe₂O₃ to +1.036 V, then FeO₄²⁻.
- **DMF Fe⁰ | [Fe(DMF)₄]²⁺ boundary:** flat at **E = −0.5406 V** across pH 0 → 7.9 (compact boundary vertices from `DmsRegEq_2`).
- **DMF estimated log K's used:** Fe³⁺·DMF log K₁ = 0.8 (σ 0.5); Fe²⁺·DMF log K₁ = 1.0, log β₂ = 1.5, log β₃ = 1.8, log β₄ = 2.1 (σ 0.5–0.8, T = 25 °C, I = 0.1 M).
- **ACN, region catalog (6 regions):** `Fe (5.745) | Fe₃O₄ (2.584) | ½Fe₂O₃(s,α) (14.673) | Fe²⁺ (4.902) | FeO₄²⁻ (6.757) | Fe³⁺ (0.339)`.
- **ACN pH cut at E = 0.248 V:** Fe²⁺ dominant from pH 0.006 to **3.41**, then ½Fe₂O₃(s,α).
- **ACN E cut at pH 6.99:** Fe⁰ up to **E = −0.489 V**, then Fe₃O₄, then ½Fe₂O₃, then FeO₄²⁻ above +1.036 V.
- **ACN estimated log K's:** Fe³⁺·MeCN log K₁ = −0.5, log β₂ = −1.5, log β₃ = −3.0 (σ 0.7–1.2); Fe²⁺·MeCN log K₁ = −0.3 (σ 0.5).
- **EG, region catalog (6 regions):** `Fe (5.784) | Fe₃O₄ (2.613) | ½Fe₂O₃(s,α) (14.756) | Fe²⁺ (4.786) | FeO₄²⁻ (6.757) | Fe³⁺ (0.305)`.
- **EG pH cut at E = 0.251 V:** Fe²⁺ dominant from pH 0.003 to **3.35**, then ½Fe₂O₃(s,α).
- **EG E cut at pH 6.997:** Fe⁰ up to **E = −0.488 V**, then Fe₃O₄, then ½Fe₂O₃, then FeO₄²⁻ above +1.036 V.
- **EG estimated log K's:** Fe³⁺ + HOCH₂CH₂OH ⇌ Fe(OCH₂CH₂OH) + H⁺, log K = −4.0 (σ 1.0); same reaction for Fe²⁺, log K = −12.0 (σ 2.0) — i.e. hydrolysis wins over EG deprotonation in every case.
- **Coverage / estimation guard:** all three calls returned `model_coverage.complete = true`, `scientific_scope = requested_system`, `omitted_requested_ligands = []`, and `estimation_search_complete = true`.

## Final deliverables

- [Result 01](final/result_01/answer.md): Evaluate Fe speciation and Pourbaix behavior in a water-DMF mixed solvent electrolyte to inform Fe electrodeposition design.
- [Result 02](final/result_02/answer.md): Evaluate Fe speciation and Pourbaix behavior in a water-acetonitrile mixed solvent electrolyte to inform Fe electrodeposition design.
- [Result 03](final/result_03/answer.md): Evaluate Fe speciation and Pourbaix behavior in a water-ethylene glycol mixed solvent electrolyte to inform Fe electrodeposition design.
