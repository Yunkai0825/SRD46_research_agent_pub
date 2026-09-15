# Speciation Calculation Report: Fe$+2 + Fe$+0 + Fe$+3 + Fe$+6 + EDTA

## System Parameters
- Temperature: 25.0 °C
- Ionic mode: fixed
- Target ionic strength: 0.1 M
- Calculated ionic strength range: 0.00222966 – 0.0239774 M
- Max inert ions: cation 0 M, anion 0 M
- pH range: 2.0 – 12.0
- Points: 101
- Converged: 101/101
- Redox mode: excluded

## Compiled Analytical Totals

| Constraint | Declared value (mol/L) | Meaning |
|------------|------------------------|---------|
| [Fe$+0]_total | 0 | redox-state subtotal |
| [Fe$+2]_total | 0 | redox-state subtotal |
| [Fe$+3]_total | 0.001 | redox-state subtotal |
| [Fe$+6]_total | 0 | redox-state subtotal |
| [ligand_6277]_total | 0.003 | component total |

## Components

| ID | Name | Total (mol/L) | Type |
|-----|------|--------------|------|
| Fe$+0 | Fe(s) | 0.00e+00 | metal |
| Fe$+2 | Fe2+ | 0.00e+00 | metal |
| Fe$+3 | Fe3+ | 1.00e-03 | metal |
| Fe$+6 | Fe(+6) | 0.00e+00 | metal |
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
| Fe2+ | aqueous | Fe$+2:+1 | — | -0.0000 | +0.0000 |
| [Fe(OH)3]- | aqueous | Fe$+2:+1 H:-3 | — | +165.5231 | +165.5231 |
| Fe3+ | aqueous | Fe$+3:+1 | — | -0.0000 | +0.0000 |
| [Fe(OH)]2+ | aqueous | Fe$+3:+1 H:-1 | — | +15.5820 | +15.5820 |
| [Fe2(OH)2]4+ | aqueous | Fe$+3:+2 H:-2 | — | +16.3240 | +16.3240 |
| [Fe(OH)2]+ | aqueous | Fe$+3:+1 H:-2 | — | +40.6266 | +40.6266 |
| [Fe3(OH)4]5+ | aqueous | Fe$+3:+3 H:-4 | — | +35.9585 | +35.9585 |
| [Fe(OH)4]- | aqueous | Fe$+3:+1 H:-4 | — | +123.2861 | +123.2861 |
| [Fe(EDTA)H] | aqueous | L1:+1 Fe$+3:+1 H:+1 | — | -135.8431 | -16.4382 |
| [Fe(EDTA)]- | aqueous | L1:+1 Fe$+3:+1 | — | -143.2631 | -23.8582 |
| [Fe(EDTA)(OH)]2- | aqueous | L1:+1 Fe$+3:+1 H:-1 | — | -101.0832 | +18.3217 |
| [Fe(OH)2](s) | solid | Fe$+2:+1 H:-2 | — | +77.4534 | +77.4534 |
| [FeO(OH)(s,alpha)] | solid | Fe$+3:+1 H:-3 | — | +2.8538 | +2.8538 |
| [Fe(OH)3](s) | solid | Fe$+3:+1 H:-3 | — | +18.2646 | +18.2646 |

## Precipitation

- pH 7.80: [FeO(OH)(s,alpha)] (1.14e-04 M)

## Speciation Analysis

```
=== Fe(s) (Fe$+0) speciation ===
[Fe$+0]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 101/101

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Fe2+ (Fe$+2) speciation ===
[Fe$+2]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 101/101

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Fe3+ (Fe$+3) speciation ===
[Fe$+3]_total = 1.00e-03 M
T = 25.0 °C,  I = 0.1 M
Convergence: 101/101

Species peaks:
  [Fe(EDTA)]-         peak 100.0% at pH 2.7
  [Fe(EDTA)(OH)]2-    peak 84.5% at pH 7.7
  [FeO(OH)(s,alpha)]  peak 100.0% at pH 11.8

Dominant species by pH region:
  pH   2.0–  7.0  →  [Fe(EDTA)]-
  pH   7.0–  8.1  →  [Fe(EDTA)(OH)]2-
  pH   8.1– 12.0  →  [FeO(OH)(s,alpha)]

Crossover pH values:
  [Fe(EDTA)]- ↔ [Fe(EDTA)(OH)]2-  at pH ≈ 6.96  (each ~50%)
  [Fe(EDTA)]- ↔ [FeO(OH)(s,alpha)]  at pH ≈ 7.80  (each ~11%)
  [Fe(EDTA)(OH)]2- ↔ [FeO(OH)(s,alpha)]  at pH ≈ 8.07  (each ~48%)

=== Fe(+6) (Fe$+6) speciation ===
[Fe$+6]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 101/101

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== EDTA (L1) speciation ===
[L1]_total = 3.00e-03 M

Species peaks:
  H4EDTA              peak 17.4% at pH 2.0
  H3EDTA-             peak 27.2% at pH 2.0
  H2EDTA2-            peak 64.2% at pH 3.8
  HEDTA3-             peak 82.2% at pH 8.4
  EDTA                peak 99.8% at pH 12.0
  [Fe(EDTA)]-         peak 33.3% at pH 2.7
  [Fe(EDTA)(OH)]2-    peak 28.2% at pH 7.7

Dominant species by pH region:
  pH   2.0–  2.3  →  [Fe(EDTA)]-
  pH   2.3–  5.6  →  H2EDTA2-
  pH   5.6–  9.4  →  HEDTA3-
  pH   9.4– 12.0  →  EDTA

```
