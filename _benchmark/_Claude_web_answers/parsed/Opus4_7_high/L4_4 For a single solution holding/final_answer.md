---
export: Opus4_7
model: claude-opus-4-7
effort: high
run: effort-high_run1
prompt: "L4_4 For a single solution holding"
conversation: https://claude.ai/chat/a9d67de7-3f6f-46dd-9b44-da48061aa6c1
started: 2026-09-17T02:04:00.696875+00:00
finished: 2026-09-17T02:05:05.368072+00:00
stop_reason: end_turn
---
This is an analytical approximation rather than a full numerical speciation run (which would want PHREEQC/MINTEQ with the NEA TDB and something like the Reilly/Neu Pu(IV)–citrate constants). But the qualitative and semi‑quantitative answer is robust because the competing affinities differ by many orders of magnitude.

**Ligand protonation at pH 4, I = 0.1 m**

Aspirin (acetylsalicylic acid) has one relevant pKa ≈ 3.5 (carboxylate); the phenolic OH is blocked by the acetyl group, so it is a **monodentate carboxylate only** — no salicylate‑type O,O chelation. At pH 4, ~75% is ASA⁻, giving [ASA⁻]ᶠʳᵉᵉ ≈ 3.8 mM before metal binding.

Citrate (pKa ≈ 3.13, 4.76, 6.40) at pH 4 is roughly 55% H₂Cit⁻, 38% HCit²⁻, 6% H₃Cit, ~1% Cit³⁻ → [Cit³⁻]ᶠʳᵉᵉ ≈ 5 × 10⁻⁵ M, [HCit²⁻]ᶠʳᵉᵉ ≈ 1.9 mM. Citrate is a strong tri‑/tetra‑dentate α‑hydroxycarboxylate chelator.

(Caveat: aspirin hydrolyzes to salicylate + acetate on a timescale of hours in water; if that happens, salicylate itself would bind Am and Pu much more strongly than aspirin, but still cannot outcompete citrate here.)

**Pu(IV)**

In the absence of ligands, Pu(IV) at pH 4 would be fully hydrolyzed (Pu(OH)₃⁺/Pu(OH)₄(aq)) and prone to intrinsic colloid formation — hydrolysis constants ~log *β*₁₄ ≈ 47. But Pu(IV)–citrate binding is enormous: log β for the 1:2 complex Pu(Cit)₂⁴⁻ is in the low‑to‑mid 30s, and mixed hydroxo‑citrate species Pu(OH)ₓ(Cit)₂ are documented (Boukhalfa, Reilly & Neu, and related work). With 5 mM citrate and 1 mM Pu(IV), citrate strips Pu out of hydrolysis and out of any competition with aspirin.

Estimated dominant Pu form: **Pu(Cit)₂⁴⁻**, with a minor contribution from a mixed hydroxo–citrate **Pu(OH)(Cit)₂⁵⁻** at pH 4. Free Pu³⁺/Pu⁴⁺ and Pu–aspirin species are <<1%; aspirin binding (monodentate carboxylate, effective log K a few units at most) loses to citrate by ~25+ orders of magnitude in overall stability.

**Am(III)**

Am³⁺ hydrolysis is negligible below pH ~6, so at pH 4 the free‑ion baseline is Am³⁺(aq). Relevant constants at I = 0.1: log β(AmCit) ≈ 7.5, log β(AmHCit⁺) ≈ 3.5, log β(Am(Cit)₂³⁻) ≈ 11–12; Am–acetate log β₁ ≈ 1.9 (a reasonable stand‑in for aspirin binding).

Rough mass balance at these free ligand concentrations:
- [AmCit]/[Am³⁺] ≈ 10^7.5 · 5 × 10⁻⁵ ≈ 1.5 × 10³
- [AmHCit⁺]/[Am³⁺] ≈ 10^3.5 · 1.9 × 10⁻³ ≈ 6
- [Am–ASA]/[Am³⁺] ≈ 10² · 3.8 × 10⁻³ ≈ 0.4

Dominant Am form: **AmCit(aq)** (≈90%+), with **Am(HCit)⁺** as the main secondary species (~5–10%) and a small tail of Am(Cit)₂³⁻. Am–aspirin is a per‑mille‑level bystander.

**Bottom line**

Both actinides are captured by citrate, not aspirin. Selectivity is driven by (i) citrate's polydentate α‑hydroxy‑carboxylate chelation versus aspirin's blocked, monodentate carboxylate, and (ii) the very high charge/hardness of Pu(IV), which makes the affinity gap even larger for Pu than for Am. If aspirin has time to hydrolyze to salicylate in your system, salicylate would show up in the Am speciation as a minor Am(Sal)⁺/Am(Sal)₂⁻ contribution but still would not displace citrate from Pu(IV). For publication‑quality numbers, I'd run this in PHREEQC with the NEA TDB plus explicit Pu(IV)–citrate constants (Reilly & Neu 2006 and follow‑ups) and check for colloid/polynuclear Pu — that is the main source of real‑world deviation from a simple mononuclear model.
