# Speciation Calculation Report: Zn$+2 + Zn$+0 + Citric acid

## System Parameters
- Temperature: 25.0 °C
- Ionic mode: fixed
- Target ionic strength: 0.1 M
- Calculated ionic strength range: 0.00226624 – 0.0135014 M
- Max inert ions: cation 0 M, anion 0 M
- pH range: 2.0 – 12.0
- Points: 101
- Converged: 101/101
- Redox mode: excluded

## Compiled Analytical Totals

| Constraint | Declared value (mol/L) | Meaning |
|------------|------------------------|---------|
| [Zn$+0]_total | 0 | redox-state subtotal |
| [Zn$+2]_total | 0.001 | redox-state subtotal |
| [ligand_9058]_total | 0.003 | component total |

## Components

| ID | Name | Total (mol/L) | Type |
|-----|------|--------------|------|
| Zn$+0 | Zn(s) | 0.00e+00 | metal |
| Zn$+2 | Zn2+ | 1.00e-03 | metal |
| L1 | Citric acid | 3.00e-03 | ligand |

## Free-Energy Species Table

| Label | Phase | Stoich | log β | μ°_free (kJ/mol) | μ°_canon (kJ/mol) |
|-------|-------|--------|-------|------------------|-------------------|
| H2O | aqueous | — | — | +1.2557 | +1.2557 |
| H3Citric acid | aqueous | L1:+1 H:+3 | — | -73.6292 | +0.0000 |
| H2Citric acid- | aqueous | L1:+1 H:+2 | — | -57.0769 | +16.5523 |
| HCitric acid2- | aqueous | L1:+1 H:+1 | — | -32.2485 | +41.3808 |
| Citric acid | aqueous | L1:+1 | — | -0.0000 | +73.6292 |
| Zn2+ | aqueous | Zn$+2:+1 | — | -0.0000 | +0.0000 |
| [Zn(OH)]+ | aqueous | H:-1 Zn$+2:+1 | — | +53.0815 | +53.0815 |
| [Zn(OH)2] | aqueous | H:-2 Zn$+2:+1 | — | +90.1815 | +90.1815 |
| [Zn(OH)3]- | aqueous | H:-3 Zn$+2:+1 | — | +160.3861 | +160.3861 |
| [Zn(OH)4]2- | aqueous | H:-4 Zn$+2:+1 | — | +231.1615 | +231.1615 |
| [Zn(Citr)H] | aqueous | L1:+1 H:+1 Zn$+2:+1 | — | -49.2003 | +24.4289 |
| [Zn(Citr)]- | aqueous | L1:+1 Zn$+2:+1 | — | -27.2257 | +46.4035 |
| [Zn(Citr)2]4- | aqueous | L1:+2 Zn$+2:+1 | — | -38.8123 | +108.4461 |
| [Zn2(Citr)2(OH)2]4- | aqueous | L1:+2 H:-2 Zn$+2:+2 | — | +16.5523 | +163.8108 |
| Zn(OH)2 (amorphous) | solid | H:-2 Zn$+2:+1 | — | +69.9146 | +69.9146 |

## Precipitation

- pH 7.10: ZnO (inactive) (1.15e-04 M)

## Speciation Analysis

```
=== Zn(s) (Zn$+0) speciation ===
[Zn$+0]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 101/101

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Zn2+ (Zn$+2) speciation ===
[Zn$+2]_total = 1.00e-03 M
T = 25.0 °C,  I = 0.1 M
Convergence: 101/101

Species peaks:
  Zn2+                peak 99.9% at pH 2.0
  [Zn(Citr)H]         peak 10.8% at pH 3.9
  [Zn(Citr)]-         peak 54.6% at pH 5.0
  [Zn(Citr)2]4-       peak 37.8% at pH 6.2
  [Zn2(Citr)2(OH)2]4-  peak 36.8% at pH 7.1

Dominant species by pH region:
  pH   2.0–  4.4  →  Zn2+
  pH   4.4–  7.0  →  [Zn(Citr)]-
  pH   7.0– 12.0  →  [Zn2(Citr)2(OH)2]4-

Crossover pH values:
  Zn2+ ↔ [Zn(Citr)]-  at pH ≈ 4.35  (each ~43%)
  Zn2+ ↔ [Zn(Citr)2]4-  at pH ≈ 4.91  (each ~21%)
  Zn2+ ↔ [Zn2(Citr)2(OH)2]4-  at pH ≈ 6.52  (each ~9%)
  [Zn(Citr)H] ↔ [Zn(Citr)]-  at pH ≈ 3.63  (each ~9%)
  [Zn(Citr)H] ↔ [Zn(Citr)2]4-  at pH ≈ 4.40  (each ~8%)
  [Zn(Citr)]- ↔ [Zn(Citr)2]4-  at pH ≈ 7.19  (each ~18%)
  [Zn(Citr)]- ↔ [Zn2(Citr)2(OH)2]4-  at pH ≈ 6.95  (each ~33%)
  [Zn(Citr)2]4- ↔ [Zn2(Citr)2(OH)2]4-  at pH ≈ 6.90  (each ~29%)

=== Citric acid (L1) speciation ===
[L1]_total = 3.00e-03 M

Species peaks:
  H3Citric acid       peak 82.7% at pH 2.0
  H2Citric acid-      peak 65.4% at pH 3.3
  HCitric acid2-      peak 49.2% at pH 4.3
  Citric acid         peak 100.0% at pH 12.0
  [Zn(Citr)]-         peak 18.2% at pH 5.0
  [Zn(Citr)2]4-       peak 25.2% at pH 6.2
  [Zn2(Citr)2(OH)2]4-  peak 12.3% at pH 7.1

Dominant species by pH region:
  pH   2.0–  2.7  →  H3Citric acid
  pH   2.7–  4.0  →  H2Citric acid-
  pH   4.0–  5.1  →  HCitric acid2-
  pH   5.1– 12.0  →  Citric acid

```
