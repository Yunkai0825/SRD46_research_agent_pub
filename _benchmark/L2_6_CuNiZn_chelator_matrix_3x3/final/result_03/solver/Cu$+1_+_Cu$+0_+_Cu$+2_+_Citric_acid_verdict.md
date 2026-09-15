# Speciation Calculation Report: Cu$+1 + Cu$+0 + Cu$+2 + Citric acid

## System Parameters
- Temperature: 25.0 °C
- Ionic mode: fixed
- Target ionic strength: 0.1 M
- Calculated ionic strength range: 0.00243453 – 0.0224967 M
- Max inert ions: cation 0 M, anion 0 M
- pH range: 2.0 – 12.0
- Points: 101
- Converged: 101/101
- Redox mode: excluded

## Compiled Analytical Totals

| Constraint | Declared value (mol/L) | Meaning |
|------------|------------------------|---------|
| [Cu$+0]_total | 0 | redox-state subtotal |
| [Cu$+1]_total | 0 | redox-state subtotal |
| [Cu$+2]_total | 0.001 | redox-state subtotal |
| [ligand_9058]_total | 0.005 | component total |

## Components

| ID | Name | Total (mol/L) | Type |
|-----|------|--------------|------|
| Cu$+0 | Cu(s) | 0.00e+00 | metal |
| Cu$+1 | Cu+ | 0.00e+00 | metal |
| Cu$+2 | Cu2+ | 1.00e-03 | metal |
| L1 | Citric acid | 5.00e-03 | ligand |

## Free-Energy Species Table

| Label | Phase | Stoich | log β | μ°_free (kJ/mol) | μ°_canon (kJ/mol) |
|-------|-------|--------|-------|------------------|-------------------|
| H2O | aqueous | — | — | +1.2557 | +1.2557 |
| H3Citric acid | aqueous | L1:+1 H:+3 | — | -73.6292 | +0.0000 |
| H2Citric acid- | aqueous | L1:+1 H:+2 | — | -57.0769 | +16.5523 |
| HCitric acid2- | aqueous | L1:+1 H:+1 | — | -32.2485 | +41.3808 |
| Citric acid | aqueous | L1:+1 | — | -0.0000 | +73.6292 |
| Cu+ | aqueous | Cu$+1:+1 | — | -0.0000 | +0.0000 |
| Cu2+ | aqueous | Cu$+2:+1 | — | -0.0000 | +0.0000 |
| [Cu(OH)]+ | aqueous | Cu$+2:+1 H:-1 | — | +45.0908 | +45.0908 |
| [Cu2(OH)2]2+ | aqueous | Cu$+2:+2 H:-2 | — | +63.9261 | +63.9261 |
| [Cu(OH)2] | aqueous | Cu$+2:+1 H:-2 | — | +92.4646 | +92.4646 |
| HCuO2- | aqueous | Cu$+2:+1 H:-3 | — | +152.4231 | +152.4231 |
| [Cu3(OH)4]2+ | aqueous | Cu$+2:+3 H:-4 | — | +128.4231 | +128.4231 |
| CuO22- | aqueous | Cu$+2:+1 H:-4 | — | +227.4004 | +227.4004 |
| [Cu(Citr)H] | aqueous | L1:+1 Cu$+2:+1 H:+1 | — | -52.8532 | +20.7760 |
| [Cu2(Citr)2]2- | aqueous | L1:+2 Cu$+2:+2 | — | -82.7615 | +64.4969 |
| [Cu2(Citr)(OH)] | aqueous | L1:+1 Cu$+2:+2 H:-1 | — | -27.7394 | +45.8898 |
| [Cu2(Citr)2(OH)]3- | aqueous | L1:+2 Cu$+2:+2 H:-1 | — | -63.9261 | +83.3323 |
| [Cu2(Citr)2(OH)2]4- | aqueous | L1:+2 Cu$+2:+2 H:-2 | — | -36.1868 | +111.0717 |
| [(Cu2O)0.5](s) | solid | Cu$+1:+1 H:-1 | — | -3.9954 | -3.9954 |
| [Cu(OH)2](s) | solid | Cu$+2:+1 H:-2 | — | +49.5428 | +49.5428 |

## Precipitation

- pH 10.90: [Cu(OH)2](s) (3.40e-05 M)

## Speciation Analysis

```
=== Cu(s) (Cu$+0) speciation ===
[Cu$+0]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 101/101

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Cu+ (Cu$+1) speciation ===
[Cu$+1]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 101/101

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Cu2+ (Cu$+2) speciation ===
[Cu$+2]_total = 1.00e-03 M
T = 25.0 °C,  I = 0.1 M
Convergence: 101/101

Species peaks:
  Cu2+                peak 99.4% at pH 2.0
  [Cu(Citr)H]         peak 17.1% at pH 3.1
  [Cu2(Citr)2]2-      peak 7.8% at pH 3.4
  [Cu2(Citr)2(OH)]3-  peak 55.8% at pH 3.7
  [Cu2(Citr)2(OH)2]4-  peak 100.0% at pH 9.6
  [Cu(OH)2](s)        peak 98.9% at pH 12.0

Dominant species by pH region:
  pH   2.0–  3.4  →  Cu2+
  pH   3.4–  4.1  →  [Cu2(Citr)2(OH)]3-
  pH   4.1– 11.1  →  [Cu2(Citr)2(OH)2]4-
  pH  11.1– 12.0  →  [Cu(OH)2](s)

Crossover pH values:
  Cu2+ ↔ [Cu2(Citr)2(OH)]3-  at pH ≈ 3.32  (each ~35%)
  Cu2+ ↔ [Cu2(Citr)2(OH)2]4-  at pH ≈ 3.50  (each ~16%)
  [Cu(Citr)H] ↔ [Cu2(Citr)2]2-  at pH ≈ 3.68  (each ~5%)
  [Cu(Citr)H] ↔ [Cu2(Citr)2(OH)]3-  at pH ≈ 3.16  (each ~17%)
  [Cu(Citr)H] ↔ [Cu2(Citr)2(OH)2]4-  at pH ≈ 3.42  (each ~12%)
  [Cu2(Citr)2]2- ↔ [Cu2(Citr)2(OH)2]4-  at pH ≈ 3.33  (each ~8%)
  [Cu2(Citr)2(OH)]3- ↔ [Cu2(Citr)2(OH)2]4-  at pH ≈ 4.00  (each ~47%)
  [Cu2(Citr)2(OH)2]4- ↔ [Cu(OH)2](s)  at pH ≈ 11.09  (each ~50%)

=== Citric acid (L1) speciation ===
[L1]_total = 5.00e-03 M

Species peaks:
  H3Citric acid       peak 82.7% at pH 2.0
  H2Citric acid-      peak 60.7% at pH 3.1
  HCitric acid2-      peak 50.7% at pH 4.5
  Citric acid         peak 99.8% at pH 12.0
  [Cu2(Citr)2(OH)]3-  peak 11.2% at pH 3.7
  [Cu2(Citr)2(OH)2]4-  peak 20.0% at pH 9.6

Dominant species by pH region:
  pH   2.0–  2.7  →  H3Citric acid
  pH   2.7–  4.0  →  H2Citric acid-
  pH   4.0–  5.1  →  HCitric acid2-
  pH   5.1– 12.0  →  Citric acid

```
