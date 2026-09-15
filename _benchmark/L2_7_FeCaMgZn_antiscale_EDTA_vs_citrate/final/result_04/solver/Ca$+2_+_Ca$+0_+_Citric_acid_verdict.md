# Speciation Calculation Report: Ca$+2 + Ca$+0 + Citric acid

## System Parameters
- Temperature: 25.0 °C
- Ionic mode: fixed
- Target ionic strength: 0.1 M
- Calculated ionic strength range: 0.0022647 – 0.013793 M
- Max inert ions: cation 0 M, anion 0 M
- pH range: 2.0 – 12.0
- Points: 101
- Converged: 101/101
- Redox mode: excluded

## Compiled Analytical Totals

| Constraint | Declared value (mol/L) | Meaning |
|------------|------------------------|---------|
| [Ca$+0]_total | 0 | redox-state subtotal |
| [Ca$+2]_total | 0.001 | redox-state subtotal |
| [ligand_9058]_total | 0.003 | component total |

## Components

| ID | Name | Total (mol/L) | Type |
|-----|------|--------------|------|
| Ca$+0 | Ca(s) | 0.00e+00 | metal |
| Ca$+2 | Ca2+ | 1.00e-03 | metal |
| L1 | Citric acid | 3.00e-03 | ligand |

## Free-Energy Species Table

| Label | Phase | Stoich | log β | μ°_free (kJ/mol) | μ°_canon (kJ/mol) |
|-------|-------|--------|-------|------------------|-------------------|
| H2O | aqueous | — | — | +1.2557 | +1.2557 |
| H3Citric acid | aqueous | L1:+1 H:+3 | — | -73.6292 | +0.0000 |
| H2Citric acid- | aqueous | L1:+1 H:+2 | — | -57.0769 | +16.5523 |
| HCitric acid2- | aqueous | L1:+1 H:+1 | — | -32.2485 | +41.3808 |
| Citric acid | aqueous | L1:+1 | — | -0.0000 | +73.6292 |
| Ca2+ | aqueous | Ca$+2:+1 | — | +0.0000 | +0.0000 |
| [Ca(OH)]+ | aqueous | Ca$+2:+1 H:-1 | — | +74.4283 | +74.4283 |
| [Ca(Citr)H2]+ | aqueous | L1:+1 Ca$+2:+1 H:+2 | — | -62.7846 | +10.8446 |
| [Ca(Citr)H] | aqueous | L1:+1 Ca$+2:+1 H:+1 | — | -44.0634 | +29.5658 |
| [Ca(Citr)]- | aqueous | L1:+1 Ca$+2:+1 | — | -19.6915 | +53.9377 |
| Ca(OH)2 | solid | Ca$+2:+1 H:-2 | — | +130.6663 | +130.6663 |
| [CaH(Citric acid)](s) | solid | L1:+1 Ca$+2:+1 H:+1 | — | -65.0106 | +8.6186 |
| [Ca3(Citric acid)2](s) | solid | L1:+2 Ca$+2:+3 | — | -97.2020 | +50.0565 |

## Speciation Analysis

```
=== Ca(s) (Ca$+0) speciation ===
[Ca$+0]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 101/101

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Ca2+ (Ca$+2) speciation ===
[Ca$+2]_total = 1.00e-03 M
T = 25.0 °C,  I = 0.1 M
Convergence: 101/101

Species peaks:
  Ca2+                peak 99.8% at pH 2.0
  [Ca(Citr)]-         peak 28.5% at pH 9.1

Dominant species by pH region:
  pH   2.0– 12.0  →  Ca2+

Crossover pH values:

=== Citric acid (L1) speciation ===
[L1]_total = 3.00e-03 M

Species peaks:
  H3Citric acid       peak 82.7% at pH 2.0
  H2Citric acid-      peak 66.9% at pH 3.3
  HCitric acid2-      peak 61.2% at pH 4.4
  Citric acid         peak 90.8% at pH 12.0
  [Ca(Citr)]-         peak 9.5% at pH 9.1

Dominant species by pH region:
  pH   2.0–  2.7  →  H3Citric acid
  pH   2.7–  4.0  →  H2Citric acid-
  pH   4.0–  5.1  →  HCitric acid2-
  pH   5.1– 12.0  →  Citric acid

```
