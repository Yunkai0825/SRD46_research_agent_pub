# Speciation Calculation Report: Ni$+2 + Ni$+0 + Ni$+3 + Ni$+4 + Citric acid

## System Parameters
- Temperature: 25.0 °C
- Ionic mode: fixed
- Target ionic strength: 0.1 M
- Calculated ionic strength range: 0.0164203 – 0.0449997 M
- Max inert ions: cation 0 M, anion 0 M
- pH range: 4.0 – 11.0
- Points: 71
- Converged: 71/71
- Redox mode: excluded

## Compiled Analytical Totals

| Constraint | Declared value (mol/L) | Meaning |
|------------|------------------------|---------|
| [Ni$+0]_total | 0 | redox-state subtotal |
| [Ni$+2]_total | 0.001 | redox-state subtotal |
| [Ni$+3]_total | 0 | redox-state subtotal |
| [Ni$+4]_total | 0 | redox-state subtotal |
| [ligand_9058]_total | 0.01 | component total |

## Components

| ID | Name | Total (mol/L) | Type |
|-----|------|--------------|------|
| Ni$+0 | Ni(s) | 0.00e+00 | metal |
| Ni$+2 | Ni2+ | 1.00e-03 | metal |
| Ni$+3 | Ni(+3) | 0.00e+00 | metal |
| Ni$+4 | Ni(+4) | 0.00e+00 | metal |
| L1 | Citric acid | 1.00e-02 | ligand |

## Free-Energy Species Table

| Label | Phase | Stoich | log β | μ°_free (kJ/mol) | μ°_canon (kJ/mol) |
|-------|-------|--------|-------|------------------|-------------------|
| H2O | aqueous | — | — | +1.2557 | +1.2557 |
| H3Citric acid | aqueous | L1:+1 H:+3 | — | -73.6292 | +0.0000 |
| H2Citric acid- | aqueous | L1:+1 H:+2 | — | -57.0769 | +16.5523 |
| HCitric acid2- | aqueous | L1:+1 H:+1 | — | -32.2485 | +41.3808 |
| Citric acid | aqueous | L1:+1 | — | -0.0000 | +73.6292 |
| Ni2+ | aqueous | Ni$+2:+1 | — | +0.0000 | +0.0000 |
| [Ni(OH)]+ | aqueous | H:-1 Ni$+2:+1 | — | +59.3600 | +59.3600 |
| [Ni(OH)2] | aqueous | H:-2 Ni$+2:+1 | — | +108.4461 | +108.4461 |
| [Ni(OH)3]- | aqueous | H:-3 Ni$+2:+1 | — | +171.2308 | +171.2308 |
| [Ni4(OH)4]4+ | aqueous | H:-4 Ni$+2:+4 | — | +158.1031 | +158.1031 |
| [Ni(Citr)H2]+ | aqueous | L1:+1 H:+2 Ni$+2:+1 | — | -66.7800 | +6.8492 |
| [Ni(Citr)H] | aqueous | L1:+1 H:+1 Ni$+2:+1 | — | -50.7414 | +22.8878 |
| [Ni(Citr)2H]3- | aqueous | L1:+2 H:+1 Ni$+2:+1 | — | -75.8552 | +71.4032 |
| [Ni(Citr)]- | aqueous | L1:+1 Ni$+2:+1 | — | -29.5658 | +44.0634 |
| [Ni(Citr)2]4- | aqueous | L1:+2 Ni$+2:+1 | — | -46.4035 | +100.8549 |
| [Ni2(Citr)2(OH)2]4- | aqueous | L1:+2 H:-2 Ni$+2:+2 | — | +24.6572 | +171.9157 |
| Ni(OH)2 | solid | H:-2 Ni$+2:+1 | — | +66.8603 | +66.8603 |

## Precipitation

- pH 9.20: Ni(OH)2 (1.94e-06 M)

## Speciation Analysis

```
=== Ni(s) (Ni$+0) speciation ===
[Ni$+0]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 71/71

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Ni2+ (Ni$+2) speciation ===
[Ni$+2]_total = 1.00e-03 M
T = 25.0 °C,  I = 0.1 M
Convergence: 71/71

Species peaks:
  [Ni(Citr)2H]3-      peak 50.0% at pH 4.0
  [Ni(Citr)]-         peak 15.4% at pH 4.0
  [Ni(Citr)2]4-       peak 96.8% at pH 7.6
  [Ni2(Citr)2(OH)2]4-  peak 26.2% at pH 9.2
  Ni(OH)2             peak 99.9% at pH 11.0

Dominant species by pH region:
  pH   4.0–  4.4  →  [Ni(Citr)2H]3-
  pH   4.4–  9.4  →  [Ni(Citr)2]4-
  pH   9.4– 11.0  →  Ni(OH)2

Crossover pH values:
  [Ni(Citr)2H]3- ↔ [Ni(Citr)2]4-  at pH ≈ 4.30  (each ~43%)
  [Ni(Citr)2]4- ↔ Ni(OH)2  at pH ≈ 9.36  (each ~42%)
  [Ni2(Citr)2(OH)2]4- ↔ Ni(OH)2  at pH ≈ 9.27  (each ~21%)

=== Ni(+3) (Ni$+3) speciation ===
[Ni$+3]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 71/71

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Ni(+4) (Ni$+4) speciation ===
[Ni$+4]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 71/71

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Citric acid (L1) speciation ===
[L1]_total = 1.00e-02 M

Species peaks:
  H2Citric acid-      peak 35.1% at pH 4.0
  HCitric acid2-      peak 51.4% at pH 4.5
  Citric acid         peak 100.0% at pH 11.0
  [Ni(Citr)2H]3-      peak 10.0% at pH 4.0
  [Ni(Citr)2]4-       peak 19.4% at pH 7.6

Dominant species by pH region:
  pH   4.0–  5.1  →  HCitric acid2-
  pH   5.1– 11.0  →  Citric acid

```
