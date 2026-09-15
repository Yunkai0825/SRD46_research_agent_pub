## Answer

**Ranking of free [Ni²⁺] at pH 9 (lowest = best scale suppression):**

| Rank | Ligand (10 mM) | Free [Ni²⁺] at pH 9 | Ni(OH)₂(s) at pH 9? | Dominant Ni species |
|------|----------------|---------------------|---------------------|---------------------|
| 1 (best) | **Glycine** | **2.95 × 10⁻⁹ M** (≈ 3 ppb of total Ni) | No — none across pH 4–11 | [Ni(Gly)₃]⁻ (88 %), [Ni(Gly)₂] (12 %) |
| 2 | **Citrate** | **4.03 × 10⁻⁷ M** (0.04 % of total Ni) | No at pH 9; onset at pH 9.2 | [Ni(Cit)₂]⁴⁻ (83 %) + hydroxo-bridged binuclear (14 %) |
| 3 (worst) | **Ammonia** | **8.5 × 10⁻⁷ M** (0.085 % of total Ni) | **Yes — 99.65 % of Ni already precipitated** | Ni(OH)₂(s); ammines only ~0.35 % |

**Glycine wins by a wide margin** — it holds free Ni²⁺ roughly **two orders of magnitude below citrate** and **~300× below ammonia**, and, uniquely, it prevents Ni(OH)₂(s) from forming anywhere in the 4–11 pH window. Citrate is a competent second: it keeps essentially all Ni chelated at pH 9, but the safety margin against precipitation is only ~0.2 pH units. Ammonia is the poorest choice; the low free [Ni²⁺] it produces is deceptive because it comes from Ni(OH)₂ scaling, not from complexation.

### Chemical explanation of the ordering

The winner is set by how much *deprotonated, coordinatively competent* ligand is available at pH 9 and how strongly it binds Ni(II) *in that form*:

- **Glycine** has an ammonium pKa of ~9.6 (log β for H⁺ + Gly⁻ ⇌ HGly = 9.57), so at pH 9 only ~20 % of the ligand pool is free glycinate — but that is plenty, because the cumulative constants log β₁,β₂,β₃ = 5.74, 10.58, 14.10 are enormous. Each glycinate provides an N,O-chelate ring worth ~5 log units. With a 10× ligand excess the tris-glycinato complex [Ni(Gly)₃]⁻ saturates the Ni coordination sphere and pins free Ni²⁺ ~10⁶ times below the Ni(OH)₂ solubility limit (~6 × 10⁻³ M at pH 9). Result: **no precipitation, deepest free-Ni²⁺ suppression, wide operating margin**.

- **Citrate** is fully deprotonated above pH ~5 (pKa₃ ≈ 5.65) and forms a strong bis-chelate [Ni(Cit)₂]⁴⁻ (log β = 8.13) using two carboxylates plus the α-hydroxyl. That single cumulative constant is smaller than glycine's β₃, so citrate cannot drive free Ni²⁺ quite as low. It still keeps ≥99.9 % of Ni chelated at pH 9, but by pH ~9.4 the driving force for Ni²⁺ + 2 OH⁻ → Ni(OH)₂(s) overtakes the chelate — first via a hydroxo-bridged binuclear intermediate, then via bulk precipitate. Adequate at exactly pH 9, but fragile against pH creep.

- **Ammonia** looks strong on paper (log β₁–β₆ = 2.73, 4.89, 6.54, 7.67, 8.33, 8.30) but is crippled by its own pKa: NH₄⁺ has pKa ≈ 9.26, so at pH 9 only ~35 % of the 10 mM total is present as free NH₃ (≈ 3.5 mM). Even the hexammine complex requires β₆·[NH₃]⁶ ≈ 10^8.30·(3.5 × 10⁻³)⁶ ≈ 0.9 to compete — essentially a wash. Consequently ammines capture <0.4 % of the Ni, and Ni(OH)₂(s) takes the remaining ~99.65 %. **The low dissolved Ni is a symptom of scaling, not prevention of it.**

**Underlying principle:** the useful chelator at pH 9 is the one whose deprotonated form is (a) abundant and (b) forms a cumulative complex strong enough to beat the Ni²⁺ + 2 OH⁻ → Ni(OH)₂(s) equilibrium. Glycine's polydentate N,O donation with a large β₃ satisfies both requirements; citrate satisfies them marginally; ammonia's monodentate binding requires much larger free-ligand concentrations than pH-9 ammonium chemistry permits.

**Recommendation:** use glycine at ≥10:1 ligand:Ni to eliminate Ni(OH)₂ scaling with a wide pH margin. Citrate is a viable backup if pH is tightly controlled at ≤9.2. Ammonia at 10 mM is ineffective for this duty; it would need to be raised well above 0.1 M total to compete.

## Validation status: incomplete

## Evidence

- **Glycine (Call 1):** "At pH 9.000: [Ni²⁺] = 2.95 × 10⁻⁹ M … Fraction of Ni_T as free Ni²⁺ = 2.95 × 10⁻⁶ … Dominant Ni species at pH 9: [Ni(Glyc)₃]⁻ at 8.77 × 10⁻⁴ M (87.7 %), with [Ni(Glyc)₂] at 1.22 × 10⁻⁴ M (12.2 %) … The [Ni(OH)₂](s) column of the concentrations CSV is 0.000e+00 at every pH from 4.0 to 11.0."
- **Citrate (Call 2):** "At pH 9.0 free aquated Ni²⁺ = 4.03 × 10⁻⁷ M, i.e. 0.040 % … Essentially all of the metal at pH 9 is in the bis-citrate chelate [Ni(Citr)₂]⁴⁻ (≈ 82.9 %) … the solver reports no solid at pH 9 … precipitation event flagged at pH 9.20 (Ni(OH)₂, 1.94 × 10⁻⁶ M)."
- **Ammonia (Call 3):** "Ni(OH)₂(s): fraction 0.99650 → 9.965 × 10⁻⁴ M as solid; Free Ni²⁺(aq): fraction 8.471 × 10⁻⁴ → [Ni²⁺] ≈ 8.5 × 10⁻⁷ M … the summed ammine fraction at pH 9 is only ~0.35 % of Ni … ammonia does not meaningfully suppress Ni(OH)₂ scaling."
- Convergence: 71/71 samples in every run.

## Final deliverables

- [Result 01](final/result_01/answer.md): Determine free [Ni2+] remaining at pH 9 when Ni(II) is chelated by glycine, to assess suppression of Ni(OH)2 scaling.
- [Result 02](final/result_02/answer.md): Determine free [Ni2+] remaining at pH 9 when Ni(II) is chelated by citrate, to assess suppression of Ni(OH)2 scaling.
- [Result 03](final/result_03/answer.md): Determine free [Ni2+] remaining at pH 9 when Ni(II) is complexed by ammonia, to assess suppression of Ni(OH)2 scaling.
