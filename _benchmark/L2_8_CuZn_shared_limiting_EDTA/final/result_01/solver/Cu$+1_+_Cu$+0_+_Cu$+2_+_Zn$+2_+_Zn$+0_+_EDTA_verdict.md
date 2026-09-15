# Speciation Calculation Report: Cu$+1 + Cu$+0 + Cu$+2 + Zn$+2 + Zn$+0 + EDTA

## System Parameters
- Temperature: 25.0 °C
- Ionic mode: fixed
- Target ionic strength: 0.1 M
- Calculated ionic strength range: 0.00450019 – 0.0065 M
- Max inert ions: cation 0 M, anion 0 M
- pH range: 3.0 – 9.0
- Points: 31
- Converged: 31/31
- Redox mode: excluded

## Compiled Analytical Totals

| Constraint | Declared value (mol/L) | Meaning |
|------------|------------------------|---------|
| [Cu$+0]_total | 0 | redox-state subtotal |
| [Cu$+1]_total | 0 | redox-state subtotal |
| [Cu$+2]_total | 0.001 | redox-state subtotal |
| [Zn$+0]_total | 0 | redox-state subtotal |
| [Zn$+2]_total | 0.001 | redox-state subtotal |
| [ligand_6277]_total | 0.001 | component total |

## Components

| ID | Name | Total (mol/L) | Type |
|-----|------|--------------|------|
| Cu$+0 | Cu(s) | 0.00e+00 | metal |
| Cu$+1 | Cu+ | 0.00e+00 | metal |
| Cu$+2 | Cu2+ | 1.00e-03 | metal |
| Zn$+0 | Zn(s) | 0.00e+00 | metal |
| Zn$+2 | Zn2+ | 1.00e-03 | metal |
| L1 | EDTA | 1.00e-03 | ligand |

## Free-Energy Species Table

| Label | Phase | Stoich | log β | μ°_free (kJ/mol) | μ°_canon (kJ/mol) |
|-------|-------|--------|-------|------------------|-------------------|
| H2O | aqueous | — | — | +1.2557 | +1.2557 |
| H6EDTA2+ | aqueous | L1:+1 H:+6 | — | -111.4141 | +7.9908 |
| H5EDTA+ | aqueous | L1:+1 H:+5 | — | -111.4141 | +7.9908 |
| H4EDTA | aqueous | L1:+1 H:+4 | — | -119.4049 | +0.0000 |
| H3EDTA- | aqueous | L1:+1 H:+3 | — | -107.8754 | +11.5295 |
| H2EDTA2- | aqueous | L1:+1 H:+2 | — | -93.4920 | +25.9129 |
| HEDTA3- | aqueous | L1:+1 H:+1 | — | -58.1614 | +61.2435 |
| EDTA | aqueous | L1:+1 | — | -0.0000 | +119.4049 |
| Cu+ | aqueous | Cu$+1:+1 | — | -0.0000 | +0.0000 |
| Cu2+ | aqueous | Cu$+2:+1 | — | -0.0000 | +0.0000 |
| [Cu(OH)]+ | aqueous | Cu$+2:+1 H:-1 | — | +45.0908 | +45.0908 |
| [Cu2(OH)2]2+ | aqueous | Cu$+2:+2 H:-2 | — | +63.9261 | +63.9261 |
| [Cu(OH)2] | aqueous | Cu$+2:+1 H:-2 | — | +92.4646 | +92.4646 |
| [Cu3(OH)4]2+ | aqueous | Cu$+2:+3 H:-4 | — | +128.4231 | +128.4231 |
| [Cu(EDTA)H2] | aqueous | L1:+1 Cu$+2:+1 H:+2 | — | -136.2997 | -16.8948 |
| [Cu(EDTA)H]- | aqueous | L1:+1 Cu$+2:+1 H:+1 | — | -124.8843 | -5.4794 |
| [Cu(EDTA)]2- | aqueous | L1:+1 Cu$+2:+1 | — | -107.1905 | +12.2145 |
| [Cu(EDTA)(OH)]3- | aqueous | L1:+1 Cu$+2:+1 H:-1 | — | -172.2581 | -52.8532 |
| Zn2+ | aqueous | Zn$+2:+1 | — | -0.0000 | +0.0000 |
| [Zn(OH)]+ | aqueous | H:-1 Zn$+2:+1 | — | +53.0815 | +53.0815 |
| [Zn(OH)2] | aqueous | H:-2 Zn$+2:+1 | — | +90.1815 | +90.1815 |
| [Zn(OH)3]- | aqueous | H:-3 Zn$+2:+1 | — | +160.3861 | +160.3861 |
| [Zn(OH)4]2- | aqueous | H:-4 Zn$+2:+1 | — | +231.1615 | +231.1615 |
| [Zn(EDTA)H2] | aqueous | L1:+1 H:+2 Zn$+2:+1 | — | -104.4508 | +14.9542 |
| [Zn(EDTA)H]- | aqueous | L1:+1 H:+1 Zn$+2:+1 | — | -111.3000 | +8.1049 |
| [Zn(EDTA)]2- | aqueous | L1:+1 Zn$+2:+1 | — | -94.1769 | +25.2280 |
| [Zn(EDTA)(OH)]3- | aqueous | L1:+1 H:-1 Zn$+2:+1 | — | -160.3861 | -40.9812 |
| [(Cu2O)0.5](s) | solid | Cu$+1:+1 H:-1 | — | -3.9954 | -3.9954 |
| [Cu(OH)2](s) | solid | Cu$+2:+1 H:-2 | — | +49.5428 | +49.5428 |
| Zn(OH)2 (alpha) | solid | H:-2 Zn$+2:+1 | — | +61.2036 | +61.2036 |

## Precipitation

- pH 6.60: [Cu(OH)2](s) (7.65e-05 M)
- pH 7.20: [Cu(OH)2](s) (4.75e-04 M), Zn(OH)2 (alpha) (1.67e-04 M)

## Speciation Analysis

```
=== Cu(s) (Cu$+0) speciation ===
[Cu$+0]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 31/31

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Cu+ (Cu$+1) speciation ===
[Cu$+1]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 31/31

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Cu2+ (Cu$+2) speciation ===
[Cu$+2]_total = 1.00e-03 M
T = 25.0 °C,  I = 0.1 M
Convergence: 31/31

Species peaks:
  Cu2+                peak 8.4% at pH 3.0
  [Cu(EDTA)(OH)]3-    peak 91.6% at pH 3.0
  [Cu(OH)2](s)        peak 47.9% at pH 9.0

Dominant species by pH region:
  pH   3.0–  9.0  →  [Cu(EDTA)(OH)]3-

Crossover pH values:
  Cu2+ ↔ [Cu(OH)2](s)  at pH ≈ 6.55  (each ~6%)

=== Zn(s) (Zn$+0) speciation ===
[Zn$+0]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 31/31

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Zn2+ (Zn$+2) speciation ===
[Zn$+2]_total = 1.00e-03 M
T = 25.0 °C,  I = 0.1 M
Convergence: 31/31

Species peaks:
  Zn2+                peak 91.6% at pH 3.0
  [Zn(EDTA)(OH)]3-    peak 47.9% at pH 9.0
  Zn(OH)2 (alpha)     peak 51.3% at pH 9.0

Dominant species by pH region:
  pH   3.0–  7.2  →  Zn2+
  pH   7.2–  7.8  →  [Zn(EDTA)(OH)]3-
  pH   7.8–  9.0  →  Zn(OH)2 (alpha)

Crossover pH values:
  Zn2+ ↔ [Zn(EDTA)(OH)]3-  at pH ≈ 7.12  (each ~44%)
  Zn2+ ↔ Zn(OH)2 (alpha)  at pH ≈ 7.29  (each ~26%)
  [Zn(EDTA)(OH)]3- ↔ Zn(OH)2 (alpha)  at pH ≈ 7.73  (each ~48%)

=== EDTA (L1) speciation ===
[L1]_total = 1.00e-03 M

Species peaks:
  [Cu(EDTA)(OH)]3-    peak 91.6% at pH 3.0
  [Zn(EDTA)(OH)]3-    peak 47.9% at pH 9.0

Dominant species by pH region:
  pH   3.0–  9.0  →  [Cu(EDTA)(OH)]3-

```
