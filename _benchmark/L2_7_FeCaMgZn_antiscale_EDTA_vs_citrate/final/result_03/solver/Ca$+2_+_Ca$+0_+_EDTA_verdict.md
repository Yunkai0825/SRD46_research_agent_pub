# Speciation Calculation Report: Ca$+2 + Ca$+0 + EDTA

## System Parameters
- Temperature: 25.0 °C
- Ionic mode: fixed
- Target ionic strength: 0.1 M
- Calculated ionic strength range: 0.00459455 – 0.0179849 M
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
| [ligand_6277]_total | 0.003 | component total |

## Components

| ID | Name | Total (mol/L) | Type |
|-----|------|--------------|------|
| Ca$+0 | Ca(s) | 0.00e+00 | metal |
| Ca$+2 | Ca2+ | 1.00e-03 | metal |
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
| Ca2+ | aqueous | Ca$+2:+1 | — | -0.0000 | +0.0000 |
| [Ca(OH)]+ | aqueous | Ca$+2:+1 H:-1 | — | +74.4283 | +74.4283 |
| [Ca(EDTA)H]- | aqueous | L1:+1 Ca$+2:+1 H:+1 | — | -78.4808 | +40.9242 |
| [Ca(EDTA)]2- | aqueous | L1:+1 Ca$+2:+1 | — | -60.7869 | +58.6180 |
| [Ca(OH)2](s) | solid | Ca$+2:+1 H:-2 | — | +130.1925 | +130.1925 |

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
  Ca2+                peak 100.0% at pH 2.0
  [Ca(EDTA)]2-        peak 100.0% at pH 11.4

Dominant species by pH region:
  pH   2.0–  4.3  →  Ca2+
  pH   4.3– 12.0  →  [Ca(EDTA)]2-

Crossover pH values:
  Ca2+ ↔ [Ca(EDTA)]2-  at pH ≈ 4.29  (each ~49%)

=== EDTA (L1) speciation ===
[L1]_total = 3.00e-03 M

Species peaks:
  H4EDTA              peak 26.1% at pH 2.0
  H3EDTA-             peak 40.8% at pH 2.0
  H2EDTA2-            peak 94.2% at pH 3.5
  HEDTA3-             peak 65.0% at pH 7.4
  EDTA                peak 66.5% at pH 12.0
  [Ca(EDTA)]2-        peak 33.3% at pH 11.4

Dominant species by pH region:
  pH   2.0–  2.1  →  H3EDTA-
  pH   2.1–  5.6  →  H2EDTA2-
  pH   5.6–  9.4  →  HEDTA3-
  pH   9.4– 12.0  →  EDTA

```
