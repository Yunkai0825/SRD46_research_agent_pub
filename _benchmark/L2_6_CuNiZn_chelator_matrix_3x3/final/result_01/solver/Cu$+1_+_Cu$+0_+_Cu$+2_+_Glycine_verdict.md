# Speciation Calculation Report: Cu$+1 + Cu$+0 + Cu$+2 + Glycine

## System Parameters
- Temperature: 25.0 °C
- Ionic mode: fixed
- Target ionic strength: 0.1 M
- Calculated ionic strength range: 1.4181e-05 – 0.00239728 M
- Max inert ions: cation 0 M, anion 0 M
- pH range: 3.0 – 11.0
- Points: 81
- Converged: 81/81
- Redox mode: excluded

## Compiled Analytical Totals

| Constraint | Declared value (mol/L) | Meaning |
|------------|------------------------|---------|
| [Cu$+0]_total | 0 | redox-state subtotal |
| [Cu$+1]_total | 0 | redox-state subtotal |
| [Cu$+2]_total | 0.001 | redox-state subtotal |
| [ligand_5760]_total | 0.005 | component total |

## Components

| ID | Name | Total (mol/L) | Type |
|-----|------|--------------|------|
| Cu$+0 | Cu(s) | 0.00e+00 | metal |
| Cu$+1 | Cu+ | 0.00e+00 | metal |
| Cu$+2 | Cu2+ | 1.00e-03 | metal |
| L1 | Glycine | 5.00e-03 | ligand |

## Free-Energy Species Table

| Label | Phase | Stoich | log β | μ°_free (kJ/mol) | μ°_canon (kJ/mol) |
|-------|-------|--------|-------|------------------|-------------------|
| H2O | aqueous | — | — | +1.2557 | +1.2557 |
| H2Glycine+ | aqueous | L1:+1 H:+2 | — | -67.9215 | -13.2989 |
| HGlycine | aqueous | L1:+1 H:+1 | — | -54.6226 | +0.0000 |
| Glycine | aqueous | L1:+1 | — | -0.0000 | +54.6226 |
| Cu+ | aqueous | Cu$+1:+1 | — | -0.0000 | +0.0000 |
| [Cu(Glyc)2]- | aqueous | L1:+2 Cu$+1:+1 | — | -57.6477 | +51.5975 |
| Cu2+ | aqueous | Cu$+2:+1 | — | -0.0000 | +0.0000 |
| [Cu(OH)]+ | aqueous | Cu$+2:+1 H:-1 | — | +45.0908 | +45.0908 |
| [Cu2(OH)2]2+ | aqueous | Cu$+2:+2 H:-2 | — | +63.9261 | +63.9261 |
| [Cu(OH)2] | aqueous | Cu$+2:+1 H:-2 | — | +92.4646 | +92.4646 |
| HCuO2- | aqueous | Cu$+2:+1 H:-3 | — | +152.4231 | +152.4231 |
| [Cu3(OH)4]2+ | aqueous | Cu$+2:+3 H:-4 | — | +128.4231 | +128.4231 |
| CuO22- | aqueous | Cu$+2:+1 H:-4 | — | +227.4004 | +227.4004 |
| [Cu(Glyc)]+ | aqueous | L1:+1 Cu$+2:+1 | — | -46.7460 | +7.8766 |
| [Cu(Glyc)2] | aqueous | L1:+2 Cu$+2:+1 | — | -86.1861 | +23.0591 |
| Cu2O | solid | Cu$+1:+2 H:-2 | — | +2.9706 | +2.9706 |
| CuO(s) | solid | Cu$+2:+1 H:-2 | — | +43.6638 | +43.6638 |
| [Cu(OH)2](s) | solid | Cu$+2:+1 H:-2 | — | +49.5428 | +49.5428 |
| Cu | solid | Cu$+0:+1 | — | +0.0000 | +0.0000 |

## Precipitation

- pH 10.10: CuO(s) (6.63e-05 M)

## Speciation Analysis

```
=== Cu(s) (Cu$+0) speciation ===
[Cu$+0]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 81/81

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Cu+ (Cu$+1) speciation ===
[Cu$+1]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 81/81

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Cu2+ (Cu$+2) speciation ===
[Cu$+2]_total = 1.00e-03 M
T = 25.0 °C,  I = 0.1 M
Convergence: 81/81

Species peaks:
  Cu2+                peak 90.6% at pH 3.0
  [Cu(Glyc)]+         peak 63.0% at pH 4.5
  [Cu(Glyc)2]         peak 100.0% at pH 10.0
  CuO(s)              peak 95.2% at pH 11.0

Dominant species by pH region:
  pH   3.0–  4.0  →  Cu2+
  pH   4.0–  5.2  →  [Cu(Glyc)]+
  pH   5.2– 10.4  →  [Cu(Glyc)2]
  pH  10.4– 11.0  →  CuO(s)

Crossover pH values:
  Cu2+ ↔ [Cu(Glyc)]+  at pH ≈ 3.96  (each ~48%)
  Cu2+ ↔ [Cu(Glyc)2]  at pH ≈ 4.53  (each ~19%)
  [Cu(Glyc)]+ ↔ [Cu(Glyc)2]  at pH ≈ 5.11  (each ~48%)
  [Cu(Glyc)2] ↔ CuO(s)  at pH ≈ 10.38  (each ~50%)

=== Glycine (L1) speciation ===
[L1]_total = 5.00e-03 M

Species peaks:
  H2Glycine+          peak 17.3% at pH 3.0
  HGlycine            peak 88.6% at pH 3.6
  Glycine             peak 95.9% at pH 11.0
  [Cu(Glyc)]+         peak 12.6% at pH 4.5
  [Cu(Glyc)2]         peak 40.0% at pH 10.0

Dominant species by pH region:
  pH   3.0–  9.1  →  HGlycine
  pH   9.1–  9.7  →  [Cu(Glyc)2]
  pH   9.7– 11.0  →  Glycine

```
