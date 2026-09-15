# Speciation Calculation Report: Co$+2 + Co$+0 + Co$+3 + Co$+4 + Glycine

## System Parameters
- Temperature: 25.0 °C
- Ionic mode: fixed
- Target ionic strength: 0.1 M
- Calculated ionic strength range: 0.000798731 – 0.0017017 M
- Max inert ions: cation 0 M, anion 0 M
- pH range: 6.5 – 7.5
- Points: 11
- Converged: 11/11
- Redox mode: excluded

## Compiled Analytical Totals

| Constraint | Declared value (mol/L) | Meaning |
|------------|------------------------|---------|
| [Co$+0]_total | 0 | redox-state subtotal |
| [Co$+2]_total | 0.001 | redox-state subtotal |
| [Co$+3]_total | 0 | redox-state subtotal |
| [Co$+4]_total | 0 | redox-state subtotal |
| [ligand_5760]_total | 0.01 | component total |

## Components

| ID | Name | Total (mol/L) | Type |
|-----|------|--------------|------|
| Co$+0 | Co(s) | 0.00e+00 | metal |
| Co$+2 | Co2+ | 1.00e-03 | metal |
| Co$+3 | Co3+ | 0.00e+00 | metal |
| Co$+4 | Co(+4) | 0.00e+00 | metal |
| L1 | Glycine | 1.00e-02 | ligand |

## Free-Energy Species Table

| Label | Phase | Stoich | log β | μ°_free (kJ/mol) | μ°_canon (kJ/mol) |
|-------|-------|--------|-------|------------------|-------------------|
| H2O | aqueous | — | — | +1.2557 | +1.2557 |
| H2Glycine+ | aqueous | L1:+1 H:+2 | — | -67.9215 | -13.2989 |
| HGlycine | aqueous | L1:+1 H:+1 | — | -54.6226 | +0.0000 |
| Glycine | aqueous | L1:+1 | — | -0.0000 | +54.6226 |
| Co2+ | aqueous | Co$+2:+1 | — | -0.0000 | +0.0000 |
| [Co(OH)]+ | aqueous | Co$+2:+1 H:-1 | — | +55.3646 | +55.3646 |
| [Co2(OH)]3+ | aqueous | Co$+2:+2 H:-1 | — | +62.7846 | +62.7846 |
| [Co(OH)2] | aqueous | Co$+2:+1 H:-2 | — | +107.3046 | +107.3046 |
| [Co(OH)3]- | aqueous | Co$+2:+1 H:-3 | — | +179.7923 | +179.7923 |
| [Co4(OH)4]4+ | aqueous | Co$+2:+4 H:-4 | — | +174.0846 | +174.0846 |
| [Co(OH)4]2- | aqueous | Co$+2:+1 H:-4 | — | +264.2661 | +264.2661 |
| [Co(Glyc)]+ | aqueous | L1:+1 Co$+2:+1 | — | -26.6549 | +27.9677 |
| [Co(Glyc)2] | aqueous | L1:+2 Co$+2:+1 | — | -48.2871 | +60.9581 |
| [Co(Glyc)3]- | aqueous | L1:+3 Co$+2:+1 | — | -62.2138 | +101.6540 |
| [Co(Glyc)(OH)] | aqueous | L1:+1 Co$+2:+1 H:-1 | — | +30.9357 | +85.5583 |
| Co3+ | aqueous | Co$+3:+1 | — | -0.0000 | +0.0000 |
| [Co(OH)2](s) | solid | Co$+2:+1 H:-2 | — | +74.7708 | +74.7708 |
| [Co(OH)3](s) | solid | Co$+3:+1 H:-3 | — | -13.1277 | -13.1277 |
| Co | solid | Co$+0:+1 | — | +0.0000 | +0.0000 |

## Speciation Analysis

```
=== Co(s) (Co$+0) speciation ===
[Co$+0]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 11/11

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Co2+ (Co$+2) speciation ===
[Co$+2]_total = 1.00e-03 M
T = 25.0 °C,  I = 0.1 M
Convergence: 11/11

Species peaks:
  Co2+                peak 80.0% at pH 6.5
  [Co(Glyc)]+         peak 51.3% at pH 7.5
  [Co(Glyc)2]         peak 23.9% at pH 7.5

Dominant species by pH region:
  pH   6.5–  7.2  →  Co2+
  pH   7.2–  7.5  →  [Co(Glyc)]+

Crossover pH values:
  Co2+ ↔ [Co(Glyc)]+  at pH ≈ 7.15  (each ~45%)
  Co2+ ↔ [Co(Glyc)2]  at pH ≈ 7.50  (each ~24%)

=== Co3+ (Co$+3) speciation ===
[Co$+3]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 11/11

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Co(+4) (Co$+4) speciation ===
[Co$+4]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 11/11

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Glycine (L1) speciation ===
[L1]_total = 1.00e-02 M

Species peaks:
  HGlycine            peak 97.8% at pH 6.5
  [Co(Glyc)]+         peak 5.1% at pH 7.5

Dominant species by pH region:
  pH   6.5–  7.5  →  HGlycine

```
