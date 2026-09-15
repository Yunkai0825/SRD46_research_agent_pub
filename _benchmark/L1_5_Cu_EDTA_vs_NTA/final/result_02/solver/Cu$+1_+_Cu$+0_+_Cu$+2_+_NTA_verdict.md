# Speciation Calculation Report: Cu$+1 + Cu$+0 + Cu$+2 + NTA

## System Parameters
- Temperature: 25.0 °C
- Ionic mode: fixed
- Target ionic strength: 0.1 M
- Calculated ionic strength range: 0.00783654 – 0.0209882 M
- Max inert ions: cation 0 M, anion 0 M
- pH range: 3.0 – 10.0
- Points: 71
- Converged: 71/71
- Redox mode: excluded

## Compiled Analytical Totals

| Constraint | Declared value (mol/L) | Meaning |
|------------|------------------------|---------|
| [Cu$+0]_total | 0 | redox-state subtotal |
| [Cu$+1]_total | 0 | redox-state subtotal |
| [Cu$+2]_total | 0.001 | redox-state subtotal |
| [ligand_6165]_total | 0.005 | component total |

## Components

| ID | Name | Total (mol/L) | Type |
|-----|------|--------------|------|
| Cu$+0 | Cu(s) | 0.00e+00 | metal |
| Cu$+1 | Cu+ | 0.00e+00 | metal |
| Cu$+2 | Cu2+ | 1.00e-03 | metal |
| L1 | NTA | 5.00e-03 | ligand |

## Free-Energy Species Table

| Label | Phase | Stoich | log β | μ°_free (kJ/mol) | μ°_canon (kJ/mol) |
|-------|-------|--------|-------|------------------|-------------------|
| H2O | aqueous | — | — | +1.2557 | +1.2557 |
| H4NTA+ | aqueous | L1:+1 H:+4 | — | -52.3395 | +5.7077 |
| H3NTA | aqueous | L1:+1 H:+3 | — | -58.0472 | +0.0000 |
| H2NTA- | aqueous | L1:+1 H:+2 | — | -68.3781 | -10.3309 |
| HNTA2- | aqueous | L1:+1 H:+1 | — | -53.9948 | +4.0525 |
| NTA | aqueous | L1:+1 | — | -0.0000 | +58.0472 |
| Cu+ | aqueous | Cu$+1:+1 | — | -0.0000 | +0.0000 |
| Cu2+ | aqueous | Cu$+2:+1 | — | -0.0000 | +0.0000 |
| [Cu(OH)]+ | aqueous | Cu$+2:+1 H:-1 | — | +45.0908 | +45.0908 |
| [Cu2(OH)2]2+ | aqueous | Cu$+2:+2 H:-2 | — | +63.9261 | +63.9261 |
| [Cu(OH)2] | aqueous | Cu$+2:+1 H:-2 | — | +92.4646 | +92.4646 |
| HCuO2- | aqueous | Cu$+2:+1 H:-3 | — | +152.4231 | +152.4231 |
| [Cu3(OH)4]2+ | aqueous | Cu$+2:+3 H:-4 | — | +128.4231 | +128.4231 |
| CuO22- | aqueous | Cu$+2:+1 H:-4 | — | +227.4004 | +227.4004 |
| [Cu(NTA)H] | aqueous | L1:+1 Cu$+2:+1 H:+1 | — | -81.6200 | -23.5728 |
| [Cu(NTA)]- | aqueous | L1:+1 Cu$+2:+1 | — | -72.4877 | -14.4405 |
| [Cu(NTA)2]4- | aqueous | L1:+2 Cu$+2:+1 | — | -99.3138 | +16.7806 |
| [Cu(NTA)(OH)]2- | aqueous | L1:+1 Cu$+2:+1 H:-1 | — | -19.9769 | +38.0703 |
| [(Cu2O)0.5](s) | solid | Cu$+1:+1 H:-1 | — | -3.9954 | -3.9954 |
| CuO(s) | solid | Cu$+2:+1 H:-2 | — | +43.6638 | +43.6638 |
| [Cu(OH)2](s) | solid | Cu$+2:+1 H:-2 | — | +49.5428 | +49.5428 |

## Speciation Analysis

```
=== Cu(s) (Cu$+0) speciation ===
[Cu$+0]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 71/71

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Cu+ (Cu$+1) speciation ===
[Cu$+1]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 71/71

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Cu2+ (Cu$+2) speciation ===
[Cu$+2]_total = 1.00e-03 M
T = 25.0 °C,  I = 0.1 M
Convergence: 71/71

Species peaks:
  [Cu(NTA)]-          peak 98.9% at pH 3.6
  [Cu(NTA)2]4-        peak 99.4% at pH 8.8

Dominant species by pH region:
  pH   3.0–  6.0  →  [Cu(NTA)]-
  pH   6.0– 10.0  →  [Cu(NTA)2]4-

Crossover pH values:
  [Cu(NTA)]- ↔ [Cu(NTA)2]4-  at pH ≈ 5.93  (each ~50%)

=== NTA (L1) speciation ===
[L1]_total = 5.00e-03 M

Species peaks:
  H2NTA-              peak 8.8% at pH 3.0
  HNTA2-              peak 79.0% at pH 4.3
  NTA                 peak 56.8% at pH 10.0
  [Cu(NTA)]-          peak 19.8% at pH 3.6
  [Cu(NTA)2]4-        peak 39.7% at pH 8.8

Dominant species by pH region:
  pH   3.0–  8.6  →  HNTA2-
  pH   8.6–  9.2  →  [Cu(NTA)2]4-
  pH   9.2– 10.0  →  NTA

```
