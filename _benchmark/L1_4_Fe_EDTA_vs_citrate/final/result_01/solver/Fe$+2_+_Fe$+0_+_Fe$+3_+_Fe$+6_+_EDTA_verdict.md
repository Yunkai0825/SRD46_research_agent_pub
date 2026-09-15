# Speciation Calculation Report: Fe$+2 + Fe$+0 + Fe$+3 + Fe$+6 + EDTA

## System Parameters
- Temperature: 25.0 °C
- Ionic mode: fixed
- Target ionic strength: 0.1 M
- Calculated ionic strength range: 0.00870146 – 0.0295598 M
- Max inert ions: cation 0 M, anion 0 M
- pH range: 4.0 – 9.0
- Points: 51
- Converged: 51/51
- Redox mode: excluded

## Compiled Analytical Totals

| Constraint | Declared value (mol/L) | Meaning |
|------------|------------------------|---------|
| [Fe$+0]_total | 0 | redox-state subtotal |
| [Fe$+2]_total | 0 | redox-state subtotal |
| [Fe$+3]_total | 0.001 | redox-state subtotal |
| [Fe$+6]_total | 0 | redox-state subtotal |
| [ligand_6277]_total | 0.005 | component total |

## Components

| ID | Name | Total (mol/L) | Type |
|-----|------|--------------|------|
| Fe$+0 | Fe(s) | 0.00e+00 | metal |
| Fe$+2 | Fe2+ | 0.00e+00 | metal |
| Fe$+3 | Fe3+ | 1.00e-03 | metal |
| Fe$+6 | Fe(+6) | 0.00e+00 | metal |
| L1 | EDTA | 5.00e-03 | ligand |

## Free-Energy Species Table

| Label | Phase | Stoich | log β | μ°_free (kJ/mol) | μ°_canon (kJ/mol) |
|-------|-------|--------|-------|------------------|-------------------|
| H2O | aqueous | — | — | +1.2557 | +1.2557 |
| H6EDTA2+ | aqueous | L1:+1 H:+6 | — | -106.4485 | +9.1323 |
| H5EDTA+ | aqueous | L1:+1 H:+5 | — | -107.5900 | +7.9908 |
| H4EDTA | aqueous | L1:+1 H:+4 | — | -115.5808 | +0.0000 |
| H3EDTA- | aqueous | L1:+1 H:+3 | — | -104.0512 | +11.5295 |
| H2EDTA2- | aqueous | L1:+1 H:+2 | — | -89.6678 | +25.9129 |
| HEDTA3- | aqueous | L1:+1 H:+1 | — | -54.3372 | +61.2435 |
| EDTA | aqueous | L1:+1 | — | -0.0000 | +115.5808 |
| Fe2+ | aqueous | Fe$+2:+1 | — | -0.0000 | +0.0000 |
| [Fe(OH)3]- | aqueous | Fe$+2:+1 H:-3 | — | +165.5231 | +165.5231 |
| Fe3+ | aqueous | Fe$+3:+1 | — | -0.0000 | +0.0000 |
| [Fe(OH)]2+ | aqueous | Fe$+3:+1 H:-1 | — | +15.5820 | +15.5820 |
| [Fe2(OH)2]4+ | aqueous | Fe$+3:+2 H:-2 | — | +16.3240 | +16.3240 |
| [Fe(OH)2]+ | aqueous | Fe$+3:+1 H:-2 | — | +26.2554 | +26.2554 |
| [Fe3(OH)4]5+ | aqueous | Fe$+3:+3 H:-4 | — | +35.9585 | +35.9585 |
| [Fe(OH)4]- | aqueous | Fe$+3:+1 H:-4 | — | +123.2861 | +123.2861 |
| [Fe(EDTA)H] | aqueous | L1:+1 Fe$+3:+1 H:+1 | — | -135.8431 | -20.2623 |
| [Fe(EDTA)]- | aqueous | L1:+1 Fe$+3:+1 | — | -143.2631 | -27.6823 |
| [Fe(EDTA)(OH)]2- | aqueous | L1:+1 Fe$+3:+1 H:-1 | — | -101.0832 | +14.4975 |
| [Fe(OH)2](s) | solid | Fe$+2:+1 H:-2 | — | +77.4534 | +77.4534 |
| [Fe(OH)3](s) | solid | Fe$+3:+1 H:-3 | — | +18.2646 | +18.2646 |

## Speciation Analysis

```
=== Fe(s) (Fe$+0) speciation ===
[Fe$+0]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 51/51

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Fe2+ (Fe$+2) speciation ===
[Fe$+2]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 51/51

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Fe3+ (Fe$+3) speciation ===
[Fe$+3]_total = 1.00e-03 M
T = 25.0 °C,  I = 0.1 M
Convergence: 51/51

Species peaks:
  [Fe(EDTA)]-         peak 99.9% at pH 4.0
  [Fe(EDTA)(OH)]2-    peak 99.1% at pH 9.0

Dominant species by pH region:
  pH   4.0–  7.0  →  [Fe(EDTA)]-
  pH   7.0–  9.0  →  [Fe(EDTA)(OH)]2-

Crossover pH values:
  [Fe(EDTA)]- ↔ [Fe(EDTA)(OH)]2-  at pH ≈ 6.96  (each ~50%)

=== Fe(+6) (Fe$+6) speciation ===
[Fe$+6]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 51/51

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== EDTA (L1) speciation ===
[L1]_total = 5.00e-03 M

Species peaks:
  H2EDTA2-            peak 76.9% at pH 4.0
  HEDTA3-             peak 75.8% at pH 7.1
  EDTA                peak 54.7% at pH 9.0
  [Fe(EDTA)]-         peak 20.0% at pH 4.0
  [Fe(EDTA)(OH)]2-    peak 19.8% at pH 9.0

Dominant species by pH region:
  pH   4.0–  5.6  →  H2EDTA2-
  pH   5.6–  8.7  →  HEDTA3-
  pH   8.7–  9.0  →  EDTA

```
