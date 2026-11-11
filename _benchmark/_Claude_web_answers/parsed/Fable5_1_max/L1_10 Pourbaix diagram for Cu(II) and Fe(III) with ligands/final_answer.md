---
export: Fable5_1
model: claude-fable-5-1
effort: max
run: effort-max_run1
prompt: "L1_10 Pourbaix diagram for Cu(II) and Fe(III) with ligands"
conversation: https://claude.ai/chat/fa946bef-32b0-42da-b4ed-0267ac179087
started: 2026-09-17T06:07:32.970902+00:00
finished: 2026-09-17T06:38:35.464432+00:00
stop_reason: tool_use_limit
---
Here is where the work stands. The solver, the full 281 × 251 E–pH grid (70,531 points, all converged), the region/boundary/junction extraction, and the three matplotlib SVG figures (joint, Cu-only, Fe-only) are complete and checked visually; the HTML page has not been assembled yet, so the results are reported here directly.

## System and conventions

1 mM Cu(II), 1 mM Fe(III), 10 mM citrate, 10 mM glycine, 0.1 M Cl⁻, 0.1 M NH₃(total), 25 °C, I = 0.1 m. All log K at I = 0 (MINTEQ v4, NIST 46 for ammines/Cu(I), a few additions), Davies coefficients at I = 0.1 (log γ = −0.107·z²). Predominance = species holding the largest share of the metal (solids counted stoichiometrically); a line is where the two named species have equal share, which is why, e.g., the Fe³⁺/Fe²⁺ line sits at +0.735 V rather than the nominal 0.771 V (activity coefficients plus Fe³⁺ being only ~46 % of Fe(III) because of FeCl²⁺ and FeHCit⁺).

## How Cu and Fe partition

**Copper.** Under oxidizing conditions Cu(II) walks through four ligands with pH: Cu²⁺ (pH < 3.2; CuCl⁺ ~5 %) → CuCit⁻ (3.2–6.2; Cu₂Cit₂²⁻ ~11 %, Cu(Cit)₂⁴⁻ ~6 %) → Cu(Gly)₂ (6.2–11.2, > 99 % at pH 9) → CuO (pH > 11.2). Cu(II) ammines never predominate — glycinate beats them by 3–4 log units. A Cu(I) window exists only where Cl⁻ or NH₃ can stabilize it: CuCl₂⁻ (pH 0–5.3, E 0.12–0.33 V) and Cu(NH₃)₂⁺ (pH 7.1–11.6, E ≈ −0.2 to +0.05 V); between pH 5.3 and 7.1 Cu(I) disproportionates and Cu(II) reduces straight to Cu(s). Cu₂O appears only at pH > 11.6; CuCl(s) never forms. Cu(s) covers everything below ≈ +0.12 V (acid) to ≈ −0.2 V (alkaline).

**Iron.** Fe(III): Fe³⁺ (pH < 1.4) → FeCit (1.4–2.5) → Fe(OH)Cit⁻ (2.5–7.0) → ferrihydrite (pH > 7.0; onset of saturation pH 6.9) → FeO₄²⁻ above E = 2.06 − 0.098·pH (pH > 7). Fe(II): Fe²⁺ (pH < 3.7) → FeHCit (3.7–4.0) → FeCit⁻ (4–9.5) → Fe(Gly)₂ (9.5–10.4) → Fe(OH)₂(s) (10.4–12) → Fe(OH)₃⁻ (> 12). Fe(s) below −0.556 V (acid) sloping to −0.93 V at pH 14. Citrate keeps Fe(III) soluble to pH 7 and Fe(II) soluble to pH 10.4; glycine matters for Fe only in the narrow Fe(Gly)₂ window.

## Principal boundaries (solver-fitted; E in V vs SHE)

Cu: Cu²⁺/CuCl₂⁻ E = 0.325 (pH 0–3.1); CuCl₂⁻/Cu(s) E = 0.124 (pH 0–5.3); Cu²⁺/CuCit⁻ pH 3.18 (CuHCit sliver 3.13–3.17); CuCit⁻/CuCl₂⁻ E = 0.614 − 0.0956 pH; CuCit⁻/Cu(s) E = 0.242 − 0.0234 pH (pH 5.35–6.15); CuCit⁻/Cu(Gly)₂ pH 6.18; Cu(Gly)₂/Cu(s) E = 0.424 − 0.0524 pH (6.2–7.05); Cu(Gly)₂/Cu(NH₃)₂⁺ E = 0.154 − 0.0127 pH (7.1–11.2); Cu(NH₃)₂⁺/Cu(s) curved, ≈ −0.118 V/pH below the NH₄⁺ pKa flattening to −0.20 V above pH 9.5; Cu(Gly)₂/CuO pH 11.18; Cu(NH₃)₂⁺/Cu₂O pH 11.58; Cu₂O/CuO E = 0.655 − 0.0593 pH; Cu(s)/Cu₂O E = 0.476 − 0.0591 pH.

Fe: Fe³⁺/Fe²⁺ E = 0.735 (pH 0–1.35); Fe³⁺/FeCit pH 1.38–1.42; Fe²⁺/FeCit E = 0.979 − 0.173 pH; FeCit/Fe(OH)Cit⁻ pH 2.48; Fe²⁺/Fe(OH)Cit⁻ E = 1.045 − 0.200 pH; Fe²⁺/FeHCit pH 3.68; FeHCit/FeCit⁻ pH 3.98; Fe(OH)Cit⁻/FeCit⁻ E = 0.511 − 0.0592 pH; Fe(OH)Cit⁻/ferrihydrite pH 7.03; FeCit⁻/ferrihydrite E = 1.334 − 0.176 pH; FeO₄²⁻/ferrihydrite E = 2.061 − 0.0983 pH; Fe²⁺/Fe(s) E = −0.556; FeCit⁻/Fe(s) E = −0.557 − 0.0104 pH; FeCit⁻/Fe(Gly)₂ pH 9.52; Fe(Gly)₂/Fe(OH)₂ pH 10.38; ferrihydrite/Fe(OH)₂ E = 0.159 − 0.0593 pH; Fe(s)/Fe(OH)₂ E = −0.047 − 0.0590 pH; Fe(OH)₂/Fe(OH)₃⁻ pH 12.03; ferrihydrite/Fe(OH)₃⁻ E = −0.555; Fe(OH)₃⁻/Fe(s) E = 0.314 − 0.0891 pH.

## Junctions (pH, E; ±0.03, ±0.005)

Cu: (3.15, 0.325) Cu²⁺/CuCit⁻/CuCl₂⁻; (5.33, 0.115) CuCit⁻/CuCl₂⁻/Cu; (6.18, 0.095) CuCit⁻/Cu(Gly)₂/Cu; (7.08, 0.055) Cu(Gly)₂/Cu(NH₃)₂⁺/Cu; (11.22, 0.015) Cu(Gly)₂/Cu(NH₃)₂⁺/CuO; (11.58, −0.035) Cu(NH₃)₂⁺/Cu₂O/CuO; (11.58, −0.205) Cu(NH₃)₂⁺/Cu/Cu₂O.
Fe: (1.4, 0.735) Fe³⁺/Fe²⁺/FeCit; (2.48, 0.555) Fe²⁺/FeCit/Fe(OH)Cit⁻; (3.73, 0.305) Fe²⁺/Fe(OH)Cit⁻/FeHCit; (3.98, 0.275) Fe(OH)Cit⁻/FeCit⁻/FeHCit; (3.67, −0.565) and (3.98, −0.575) with Fe(s); (6.98, 1.385) FeO₄²⁻/HFeO₄⁻/Fe(OH)Cit⁻; (7.12, 1.355) FeO₄²⁻/Fe(OH)Cit⁻/ferrihydrite; (7.12, 0.095) Fe(OH)Cit⁻/FeCit⁻/ferrihydrite; (9.53, −0.335) and (9.53, −0.645); (10.38, −0.455) and (10.38, −0.655); (12.03, −0.555) and (12.03, −0.755).
Notable Cu/Fe crossings: Cu(Gly)₂/Cu(NH₃)₂⁺ × FeCit⁻/ferrihydrite (7.3, 0.055); CuCit⁻/Cu(Gly)₂ × Fe(OH)Cit⁻/FeCit⁻ (6.18, 0.145); Cu(Gly)₂/CuO × FeO₄²⁻/ferrihydrite (11.18, 0.96).

## Key constants in the solver

E°: Cu²⁺/Cu⁺ 0.159, Cu²⁺/Cu 0.339, Fe³⁺/Fe²⁺ 0.771, Fe²⁺/Fe −0.447, FeO₄²⁻/Fe³⁺ 2.20 V (less certain). log β: CuCit⁻ 7.57, Cu(Gly)₂ 15.7, Cu(NH₃)₄²⁺ 11.75, CuCl₂⁻ 5.42 (from Cu⁺), Cu(NH₃)₂⁺ 10.86, FeCit 13.1, Fe(OH)Cit⁻ 10.5 (added; FeCit pKa 2.6, less certain), FeCit⁻ 6.1, Fe(Gly)₂ 8.29; log K_sp-type: ferrihydrite 3.191, CuO 7.644, Cu₂O −1.406, Fe(OH)₂ 13.564. Ligand pKa: citrate 3.13/4.76/6.40, glycine 2.35/9.78, NH₄⁺ 9.24.

## Caveats

Aged Fe oxides (goethite, hematite, magnetite), Cu(OH)₂, Cu-Fe ferrites, polynuclear Fe-citrate and Cu-citrate hydroxo species are excluded; goethite/hematite would greatly expand the Fe(III) solid field, polynuclear Fe-citrate would extend Fe(III) solubility to ~pH 9, and a CuCitH₋₁ species would push the CuCit⁻/Cu(Gly)₂ line to ~pH 8.5. Ligands are treated as redox-inert; I is held at 0.1 even at pH 0 and 14. Solid saturation onsets sit ≤ 0.02 V / 0.25 pH before the drawn 50 % lines.

I have the three figures rendered and the tables assembled; I can publish the page with the interactive diagrams and full constant/boundary tables next.
