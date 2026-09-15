# Speciation Calculation Report: Ni$+2 + Ni$+0 + Ni$+3 + Ni$+4 + Citric acid

## System Parameters
- Temperature: 25.0 °C
- Ionic mode: fixed
- Target ionic strength: 0.1 M
- Calculated ionic strength range: 0.00241657 – 0.0225051 M
- Max inert ions: cation 0 M, anion 0 M
- pH range: 2.0 – 12.0
- Points: 101
- Converged: 101/101
- Redox mode: excluded

## Compiled Analytical Totals

| Constraint | Declared value (mol/L) | Meaning |
|------------|------------------------|---------|
| [Ni$+0]_total | 0 | redox-state subtotal |
| [Ni$+2]_total | 0.001 | redox-state subtotal |
| [Ni$+3]_total | 0 | redox-state subtotal |
| [Ni$+4]_total | 0 | redox-state subtotal |
| [ligand_9058]_total | 0.005 | component total |

## Components

| ID | Name | Total (mol/L) | Type |
|-----|------|--------------|------|
| Ni$+0 | Ni(s) | 0.00e+00 | metal |
| Ni$+2 | Ni2+ | 1.00e-03 | metal |
| Ni$+3 | Ni(+3) | 0.00e+00 | metal |
| Ni$+4 | Ni(+4) | 0.00e+00 | metal |
| L1 | Citric acid | 5.00e-03 | ligand |

## Free-Energy Species Table

| Label | Phase | Stoich | log β | μ°_free (kJ/mol) | μ°_canon (kJ/mol) |
|-------|-------|--------|-------|------------------|-------------------|
| H2O | aqueous | — | — | +1.2557 | +1.2557 |
| H3Citric acid | aqueous | L1:+1 H:+3 | — | -73.6292 | +0.0000 |
| H2Citric acid- | aqueous | L1:+1 H:+2 | — | -57.0769 | +16.5523 |
| HCitric acid2- | aqueous | L1:+1 H:+1 | — | -32.2485 | +41.3808 |
| Citric acid | aqueous | L1:+1 | — | -0.0000 | +73.6292 |
| Ni2+ | aqueous | Ni$+2:+1 | — | -0.0000 | +0.0000 |
| [Ni(OH)]+ | aqueous | H:-1 Ni$+2:+1 | — | +59.3600 | +59.3600 |
| [Ni(OH)2] | aqueous | H:-2 Ni$+2:+1 | — | +108.4461 | +108.4461 |
| [Ni(OH)3]- | aqueous | H:-3 Ni$+2:+1 | — | +171.2308 | +171.2308 |
| [Ni4(OH)4]4+ | aqueous | H:-4 Ni$+2:+4 | — | +158.1031 | +158.1031 |
| [Ni(Citr)H2]+ | aqueous | L1:+1 H:+2 Ni$+2:+1 | — | -66.7800 | +6.8492 |
| [Ni(Citr)H] | aqueous | L1:+1 H:+1 Ni$+2:+1 | — | -50.7414 | +22.8878 |
| [Ni(Citr)2H]3- | aqueous | L1:+2 H:+1 Ni$+2:+1 | — | -76.4545 | +70.8039 |
| [Ni(Citr)]- | aqueous | L1:+1 Ni$+2:+1 | — | -29.5658 | +44.0634 |
| [Ni(Citr)2]4- | aqueous | L1:+2 Ni$+2:+1 | — | -47.6878 | +99.5707 |
| [Ni2(Citr)2(OH)2]4- | aqueous | L1:+2 H:-2 Ni$+2:+2 | — | +24.6572 | +171.9157 |
| [Ni(OH)2](s) | solid | H:-2 Ni$+2:+1 | — | +73.0585 | +73.0585 |

## Precipitation

- pH 9.80: [Ni(OH)2](s) (2.07e-04 M)

## Speciation Analysis

```
=== Ni(s) (Ni$+0) speciation ===
[Ni$+0]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 101/101

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Ni2+ (Ni$+2) speciation ===
[Ni$+2]_total = 1.00e-03 M
T = 25.0 °C,  I = 0.1 M
Convergence: 101/101

Species peaks:
  Ni2+                peak 98.2% at pH 2.0
  [Ni(Citr)H]         peak 13.6% at pH 3.5
  [Ni(Citr)2H]3-      peak 35.9% at pH 4.1
  [Ni(Citr)]-         peak 20.4% at pH 3.9
  [Ni(Citr)2]4-       peak 94.9% at pH 7.4
  [Ni2(Citr)2(OH)2]4-  peak 70.8% at pH 9.7
  [Ni(OH)2](s)        peak 99.6% at pH 11.3

Dominant species by pH region:
  pH   2.0–  3.8  →  Ni2+
  pH   3.8–  4.2  →  [Ni(Citr)2H]3-
  pH   4.2–  9.4  →  [Ni(Citr)2]4-
  pH   9.4–  9.9  →  [Ni2(Citr)2(OH)2]4-
  pH   9.9– 12.0  →  [Ni(OH)2](s)

Crossover pH values:
  Ni2+ ↔ [Ni(Citr)2H]3-  at pH ≈ 3.77  (each ~29%)
  Ni2+ ↔ [Ni(Citr)]-  at pH ≈ 3.89  (each ~20%)
  Ni2+ ↔ [Ni(Citr)2]4-  at pH ≈ 3.92  (each ~19%)
  [Ni(Citr)H] ↔ [Ni(Citr)2H]3-  at pH ≈ 3.48  (each ~14%)
  [Ni(Citr)H] ↔ [Ni(Citr)]-  at pH ≈ 3.50  (each ~14%)
  [Ni(Citr)H] ↔ [Ni(Citr)2]4-  at pH ≈ 3.76  (each ~11%)
  [Ni(Citr)2H]3- ↔ [Ni(Citr)]-  at pH ≈ 3.46  (each ~13%)
  [Ni(Citr)2H]3- ↔ [Ni(Citr)]-  at pH ≈ 5.31  (each ~7%)
  [Ni(Citr)2H]3- ↔ [Ni(Citr)2]4-  at pH ≈ 4.18  (each ~35%)
  [Ni(Citr)]- ↔ [Ni(Citr)2]4-  at pH ≈ 3.95  (each ~20%)
  [Ni(Citr)2]4- ↔ [Ni2(Citr)2(OH)2]4-  at pH ≈ 9.35  (each ~49%)
  [Ni(Citr)2]4- ↔ [Ni(OH)2](s)  at pH ≈ 9.80  (each ~21%)
  [Ni2(Citr)2(OH)2]4- ↔ [Ni(OH)2](s)  at pH ≈ 9.90  (each ~42%)

=== Ni(+3) (Ni$+3) speciation ===
[Ni$+3]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 101/101

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Ni(+4) (Ni$+4) speciation ===
[Ni$+4]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 101/101

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Citric acid (L1) speciation ===
[L1]_total = 5.00e-03 M

Species peaks:
  H3Citric acid       peak 82.5% at pH 2.0
  H2Citric acid-      peak 63.0% at pH 3.2
  HCitric acid2-      peak 40.9% at pH 4.4
  Citric acid         peak 100.0% at pH 12.0
  [Ni(Citr)2H]3-      peak 14.4% at pH 4.1
  [Ni(Citr)2]4-       peak 38.0% at pH 7.4
  [Ni2(Citr)2(OH)2]4-  peak 14.2% at pH 9.7

Dominant species by pH region:
  pH   2.0–  2.7  →  H3Citric acid
  pH   2.7–  4.0  →  H2Citric acid-
  pH   4.0–  5.0  →  HCitric acid2-
  pH   5.0–  5.1  →  [Ni(Citr)2]4-
  pH   5.1– 12.0  →  Citric acid

```
