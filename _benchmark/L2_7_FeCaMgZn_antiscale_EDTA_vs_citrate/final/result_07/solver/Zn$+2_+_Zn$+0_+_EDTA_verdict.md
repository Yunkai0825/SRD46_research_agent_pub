# Speciation Calculation Report: Zn$+2 + Zn$+0 + EDTA

## System Parameters
- Temperature: 25.0 °C
- Ionic mode: fixed
- Target ionic strength: 0.1 M
- Calculated ionic strength range: 0.00622979 – 0.0204849 M
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
| [ligand_6277]_total | 0.003 | component total |

## Components

| ID | Name | Total (mol/L) | Type |
|-----|------|--------------|------|
| Zn$+0 | Zn(s) | 0.00e+00 | metal |
| Zn$+2 | Zn2+ | 1.00e-03 | metal |
| L1 | EDTA | 3.00e-03 | ligand |

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
| Zn2+ | aqueous | Zn$+2:+1 | — | -0.0000 | +0.0000 |
| [Zn(OH)]+ | aqueous | H:-1 Zn$+2:+1 | — | +53.0815 | +53.0815 |
| [Zn(OH)2] | aqueous | H:-2 Zn$+2:+1 | — | +90.1815 | +90.1815 |
| [Zn(OH)3]- | aqueous | H:-3 Zn$+2:+1 | — | +160.3861 | +160.3861 |
| [Zn(OH)4]2- | aqueous | H:-4 Zn$+2:+1 | — | +231.1615 | +231.1615 |
| [Zn(EDTA)H2] | aqueous | L1:+1 H:+2 Zn$+2:+1 | — | -104.4508 | +14.9542 |
| [Zn(EDTA)H]- | aqueous | L1:+1 H:+1 Zn$+2:+1 | — | -111.3000 | +8.1049 |
| [Zn(EDTA)]2- | aqueous | L1:+1 Zn$+2:+1 | — | -94.1769 | +25.2280 |
| [Zn(EDTA)(OH)]3- | aqueous | L1:+1 H:-1 Zn$+2:+1 | — | -160.3861 | -40.9812 |
| Zn(OH)2 (alpha) | solid | H:-2 Zn$+2:+1 | — | +61.2036 | +61.2036 |

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
  [Zn(EDTA)(OH)]3-    peak 100.0% at pH 11.2

Dominant species by pH region:
  pH   2.0– 12.0  →  [Zn(EDTA)(OH)]3-

Crossover pH values:

=== EDTA (L1) speciation ===
[L1]_total = 3.00e-03 M

Species peaks:
  H4EDTA              peak 17.4% at pH 2.0
  H3EDTA-             peak 27.2% at pH 2.0
  H2EDTA2-            peak 64.2% at pH 3.8
  HEDTA3-             peak 65.0% at pH 7.4
  EDTA                peak 66.5% at pH 12.0
  [Zn(EDTA)(OH)]3-    peak 33.3% at pH 11.2

Dominant species by pH region:
  pH   2.0–  2.3  →  [Zn(EDTA)(OH)]3-
  pH   2.3–  5.6  →  H2EDTA2-
  pH   5.6–  9.4  →  HEDTA3-
  pH   9.4– 12.0  →  EDTA

```
