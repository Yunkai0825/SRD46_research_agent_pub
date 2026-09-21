---
export: Opus4_7
model: claude-opus-4-7
effort: max
run: effort-max_run1
prompt: "L1_11 Pourbaix diagram for Cu-Fe electrodeposition electrolyte"
conversation: https://claude.ai/chat/ba745218-ee4b-4220-9311-92d2cb701d78
started: 2026-09-17T08:31:48.701316+00:00
finished: 2026-09-17T09:18:30.900421+00:00
stop_reason: end_turn
---
Report is written. Before publishing, let me check whether any published artifact type is a better fit than a plain HTML page.

None of the ready-made types fit a dense scientific report with embedded diagrams — a Docs artifact would strip the images and formatting, Slides would fragment the flow. I'll publish the HTML page directly.

[Coupled Cu · Fe Pourbaix diagram — citrate / glycine / NH₃ / Cl⁻ electrolyte](cu_fe_pourbaix_report.html)

The report is published. Here's what I built and what the map says.

**What's in the report**

Section 02 lists the full thermodynamic database I used — 48 aqueous complexes across the four oxidation states, 4 solids, and 6 aquo redox couples — every log β and log Kₛₚ with its formation reaction. Section 04 is the two-panel Pourbaix map (Cu on the left, Fe on the right), Section 06 gives closed-form equations for every boundary line drawn, Section 07 lists all 18 triple-point junctions with pH and E coordinates, and Section 05 tabulates the full reduction chain at each integer pH.

**How Cu and Fe actually partition**

For **Cu(II)**, aqueous Cu²⁺ vanishes above pH ≈ 3.5. Between pH 4 and 8 the picture is *Cu-citrate* — CuHCit → CuCit⁻ → Cu(Cit)₂⁴⁻. From pH 8 to 11.4, Cu(Gly)₂ beats Cu(NH₃)₄²⁺ by about 2 log units. Cu(OH)₂(s) precipitates only above pH ≈ 11.4. For **Cu(I)**, chloride carries a CuCl₂⁻/CuCl₃²⁻ window at pH 0–4, Cu(I) disproportionates through pH 5–7 (no aqueous window), and ammonia reopens a Cu(NH₃)₂⁺ window from pH 7 to 11.5. Cu₂O(s) forms only in a narrow wedge above pH 11.5.

For **Fe(III)**, only pH 0–1 has bare Fe³⁺/FeCl²⁺; from pH 1 upward citrate takes over completely (FeHCit⁺ → FeCit → Fe(Cit)₂³⁻ → hydroxo-citrate species), and amorphous Fe(OH)₃ finally saturates at pH ≈ 7.5 — a **4-pH-unit upshift** from the citrate-free diagram. For **Fe(II)**, Fe²⁺ holds to pH ≈ 3.7, then FeHCit/FeCit⁻ through pH 9, Fe(Gly)₂ in a small window, and Fe(OH)₂(s) above pH 9.4.

**The most consequential number**

The Fe(III)/Fe(II) conditional potential falls from +0.73 V at pH 0 to −0.67 V at pH 14 — a **1.4 V collapse**, driven almost entirely by citrate binding Fe(III) far more strongly than Fe(II). That inversion is what makes the whole diagram surprising: in the citrate/glycine/NH₃ bath, Fe(III) is not the strong oxidiser it is in dilute acid.
