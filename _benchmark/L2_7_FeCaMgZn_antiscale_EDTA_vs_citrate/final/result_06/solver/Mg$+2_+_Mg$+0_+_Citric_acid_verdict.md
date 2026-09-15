# Speciation Calculation Report: Mg$+2 + Mg$+0 + Citric acid

## System Parameters
- Temperature: 25.0 °C
- Ionic mode: fixed
- Target ionic strength: 0.1 M
- Calculated ionic strength range: 0.00226629 – 0.0138423 M
- Max inert ions: cation 0 M, anion 0 M
- pH range: 2.0 – 12.0
- Points: 101
- Converged: 101/101
- Redox mode: excluded

## Compiled Analytical Totals

| Constraint | Declared value (mol/L) | Meaning |
|------------|------------------------|---------|
| [Mg$+0]_total | 0 | redox-state subtotal |
| [Mg$+2]_total | 0.001 | redox-state subtotal |
| [ligand_9058]_total | 0.003 | component total |

## Components

| ID | Name | Total (mol/L) | Type |
|-----|------|--------------|------|
| Mg$+0 | Mg(s) | 0.00e+00 | metal |
| Mg$+2 | Mg2+ | 1.00e-03 | metal |
| L1 | Citric acid | 3.00e-03 | ligand |

## Free-Energy Species Table

| Label | Phase | Stoich | log β | μ°_free (kJ/mol) | μ°_canon (kJ/mol) |
|-------|-------|--------|-------|------------------|-------------------|
| H2O | aqueous | — | — | +1.2557 | +1.2557 |
| H3Citric acid | aqueous | L1:+1 H:+3 | — | -73.6292 | +0.0000 |
| H2Citric acid- | aqueous | L1:+1 H:+2 | — | -57.0769 | +16.5523 |
| HCitric acid2- | aqueous | L1:+1 H:+1 | — | -32.2485 | +41.3808 |
| Citric acid | aqueous | L1:+1 | — | -0.0000 | +73.6292 |
| Mg2+ | aqueous | Mg$+2:+1 | — | -0.0000 | +0.0000 |
| [Mg(OH)]+ | aqueous | Mg$+2:+1 H:-1 | — | +65.0677 | +65.0677 |
| [Mg2(OH)]3+ | aqueous | Mg$+2:+2 H:-1 | — | +66.7800 | +66.7800 |
| [Mg4(OH)4]4+ | aqueous | Mg$+2:+4 H:-4 | — | +227.7369 | +227.7369 |
| [Mg(Citr)H2]+ | aqueous | Mg$+2:+1 L1:+1 H:+2 | — | -61.0723 | +12.5569 |
| [Mg(Citr)H] | aqueous | Mg$+2:+1 L1:+1 H:+1 | — | -42.8077 | +30.8215 |
| [Mg(Citr)]- | aqueous | Mg$+2:+1 L1:+1 | — | -19.5774 | +54.0518 |
| [Mg(OH)2(s,brucite)] | solid | Mg$+2:+1 H:-2 | — | +96.2317 | +96.2317 |
| Mg | solid | Mg$+0:+1 | — | +0.0000 | +0.0000 |

## Precipitation

- pH 10.20: [Mg(OH)2(s,brucite)] (3.24e-04 M)

## Speciation Analysis

```
=== Mg(s) (Mg$+0) speciation ===
[Mg$+0]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 101/101

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Mg2+ (Mg$+2) speciation ===
[Mg$+2]_total = 1.00e-03 M
T = 25.0 °C,  I = 0.1 M
Convergence: 101/101

Species peaks:
  Mg2+                peak 99.9% at pH 2.0
  [Mg(Citr)]-         peak 27.6% at pH 8.3
  [Mg(OH)2(s,brucite)]  peak 100.0% at pH 12.0

Dominant species by pH region:
  pH   2.0– 10.3  →  Mg2+
  pH  10.3– 12.0  →  [Mg(OH)2(s,brucite)]

Crossover pH values:
  Mg2+ ↔ [Mg(OH)2(s,brucite)]  at pH ≈ 10.24  (each ~41%)
  [Mg(Citr)]- ↔ [Mg(OH)2(s,brucite)]  at pH ≈ 10.17  (each ~21%)

=== Citric acid (L1) speciation ===
[L1]_total = 3.00e-03 M

Species peaks:
  H3Citric acid       peak 82.7% at pH 2.0
  H2Citric acid-      peak 67.1% at pH 3.3
  HCitric acid2-      peak 61.5% at pH 4.4
  Citric acid         peak 100.0% at pH 12.0
  [Mg(Citr)]-         peak 9.2% at pH 8.3

Dominant species by pH region:
  pH   2.0–  2.7  →  H3Citric acid
  pH   2.7–  4.0  →  H2Citric acid-
  pH   4.0–  5.1  →  HCitric acid2-
  pH   5.1– 12.0  →  Citric acid

```
