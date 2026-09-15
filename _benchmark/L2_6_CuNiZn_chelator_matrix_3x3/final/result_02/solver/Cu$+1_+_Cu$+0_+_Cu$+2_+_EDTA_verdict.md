# Speciation Calculation Report: Cu$+1 + Cu$+0 + Cu$+2 + EDTA

## System Parameters
- Temperature: 25.0 °C
- Ionic mode: fixed
- Target ionic strength: 0.1 M
- Calculated ionic strength range: 0.00795959 – 0.0364698 M
- Max inert ions: cation 0 M, anion 0 M
- pH range: 2.0 – 12.0
- Points: 51
- Converged: 51/51
- Redox mode: excluded

## Compiled Analytical Totals

| Constraint | Declared value (mol/L) | Meaning |
|------------|------------------------|---------|
| [Cu$+0]_total | 0 | redox-state subtotal |
| [Cu$+1]_total | 0 | redox-state subtotal |
| [Cu$+2]_total | 0.001 | redox-state subtotal |
| [ligand_6277]_total | 0.005 | component total |

## Components

| ID | Name | Total (mol/L) | Type |
|-----|------|--------------|------|
| Cu$+0 | Cu(s) | 0.00e+00 | metal |
| Cu$+1 | Cu+ | 0.00e+00 | metal |
| Cu$+2 | Cu2+ | 1.00e-03 | metal |
| L1 | EDTA | 5.00e-03 | ligand |

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
| HCuO2- | aqueous | Cu$+2:+1 H:-3 | — | +152.4231 | +152.4231 |
| [Cu3(OH)4]2+ | aqueous | Cu$+2:+3 H:-4 | — | +128.4231 | +128.4231 |
| CuO22- | aqueous | Cu$+2:+1 H:-4 | — | +227.4004 | +227.4004 |
| [Cu(EDTA)H2] | aqueous | L1:+1 Cu$+2:+1 H:+2 | — | -136.2997 | -16.8948 |
| [Cu(EDTA)H]- | aqueous | L1:+1 Cu$+2:+1 H:+1 | — | -124.8843 | -5.4794 |
| [Cu(EDTA)]2- | aqueous | L1:+1 Cu$+2:+1 | — | -107.1905 | +12.2145 |
| [Cu(EDTA)(OH)]3- | aqueous | L1:+1 Cu$+2:+1 H:-1 | — | -172.2581 | -52.8532 |
| [(Cu2O)0.5](s) | solid | Cu$+1:+1 H:-1 | — | -3.9954 | -3.9954 |
| CuO(s) | solid | Cu$+2:+1 H:-2 | — | +43.6638 | +43.6638 |
| [Cu(OH)2](s) | solid | Cu$+2:+1 H:-2 | — | +49.5428 | +49.5428 |
| Cu | solid | Cu$+0:+1 | — | +0.0000 | +0.0000 |

## Speciation Analysis

```
=== Cu(s) (Cu$+0) speciation ===
[Cu$+0]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 51/51

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Cu+ (Cu$+1) speciation ===
[Cu$+1]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 51/51

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Cu2+ (Cu$+2) speciation ===
[Cu$+2]_total = 1.00e-03 M
T = 25.0 °C,  I = 0.1 M
Convergence: 51/51

Species peaks:
  [Cu(EDTA)(OH)]3-    peak 100.0% at pH 9.4

Dominant species by pH region:
  pH   2.0– 12.0  →  [Cu(EDTA)(OH)]3-

Crossover pH values:

=== EDTA (L1) speciation ===
[L1]_total = 5.00e-03 M

Species peaks:
  H4EDTA              peak 20.9% at pH 2.0
  H3EDTA-             peak 32.7% at pH 2.0
  H2EDTA2-            peak 77.1% at pH 3.8
  HEDTA3-             peak 78.0% at pH 7.4
  EDTA                peak 79.8% at pH 12.0
  [Cu(EDTA)(OH)]3-    peak 20.0% at pH 9.4

Dominant species by pH region:
  pH   2.0–  2.2  →  H3EDTA-
  pH   2.2–  5.6  →  H2EDTA2-
  pH   5.6–  9.4  →  HEDTA3-
  pH   9.4– 12.0  →  EDTA

```
