# Speciation Calculation Report: Ni$+2 + Ni$+0 + Ni$+3 + Ni$+4 + EDTA

## System Parameters
- Temperature: 25.0 °C
- Ionic mode: fixed
- Target ionic strength: 0.1 M
- Calculated ionic strength range: 0.00795959 – 0.0364935 M
- Max inert ions: cation 0 M, anion 0 M
- pH range: 2.0 – 12.0
- Points: 101
- Converged: 101/101
- Redox mode: excluded

## Compiled Analytical Totals

| Constraint | Declared value (mol/L) | Meaning |
|------------|------------------------|---------|
| [Ni$+0]_total | 0 | redox-state subtotal |
| [Ni$+2]_total | 0.001 | redox-state subtotal |
| [Ni$+3]_total | 0 | redox-state subtotal |
| [Ni$+4]_total | 0 | redox-state subtotal |
| [ligand_6277]_total | 0.005 | component total |

## Components

| ID | Name | Total (mol/L) | Type |
|-----|------|--------------|------|
| Ni$+0 | Ni(s) | 0.00e+00 | metal |
| Ni$+2 | Ni2+ | 1.00e-03 | metal |
| Ni$+3 | Ni(+3) | 0.00e+00 | metal |
| Ni$+4 | Ni(+4) | 0.00e+00 | metal |
| L1 | EDTA | 5.00e-03 | ligand |

## Free-Energy Species Table

| Label | Phase | Stoich | log β | μ°_free (kJ/mol) | μ°_canon (kJ/mol) |
|-------|-------|--------|-------|------------------|-------------------|
| H2O | aqueous | — | — | +1.2557 | +1.2557 |
| H6EDTA2+ | aqueous | L1:+1 H:+6 | — | -107.5900 | +7.9908 |
| H5EDTA+ | aqueous | L1:+1 H:+5 | — | -107.5900 | +7.9908 |
| H4EDTA | aqueous | L1:+1 H:+4 | — | -115.5808 | +0.0000 |
| H3EDTA- | aqueous | L1:+1 H:+3 | — | -104.0512 | +11.5295 |
| H2EDTA2- | aqueous | L1:+1 H:+2 | — | -89.6678 | +25.9129 |
| HEDTA3- | aqueous | L1:+1 H:+1 | — | -54.3372 | +61.2435 |
| EDTA | aqueous | L1:+1 | — | -0.0000 | +115.5808 |
| Ni2+ | aqueous | Ni$+2:+1 | — | -0.0000 | +0.0000 |
| [Ni(OH)]+ | aqueous | H:-1 Ni$+2:+1 | — | +59.3600 | +59.3600 |
| [Ni(OH)2] | aqueous | H:-2 Ni$+2:+1 | — | +108.4461 | +108.4461 |
| [Ni(OH)3]- | aqueous | H:-3 Ni$+2:+1 | — | +171.2308 | +171.2308 |
| [Ni4(OH)4]4+ | aqueous | H:-4 Ni$+2:+4 | — | +158.1031 | +158.1031 |
| [Ni(EDTA)H]- | aqueous | L1:+1 H:+1 Ni$+2:+1 | — | -122.7154 | -7.1346 |
| [Ni(EDTA)]2- | aqueous | L1:+1 Ni$+2:+1 | — | -105.0215 | +10.5592 |
| [Ni(EDTA)(OH)]3- | aqueous | L1:+1 H:-1 Ni$+2:+1 | — | -172.9431 | -57.3623 |
| [Ni(OH)2](s) | solid | H:-2 Ni$+2:+1 | — | +73.0585 | +73.0585 |

## Speciation Analysis

```
=== Ni(s) (Ni$+0) speciation ===
[Ni$+0]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 101/101

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Ni2+ (Ni$+2) speciation ===
[Ni$+2]_total = 1.00e-03 M
T = 25.0 °C,  I = 0.1 M
Convergence: 101/101

Species peaks:
  [Ni(EDTA)(OH)]3-    peak 100.0% at pH 2.0

Dominant species by pH region:
  pH   2.0– 12.0  →  [Ni(EDTA)(OH)]3-

Crossover pH values:

=== Ni(+3) (Ni$+3) speciation ===
[Ni$+3]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 101/101

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Ni(+4) (Ni$+4) speciation ===
[Ni$+4]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 101/101

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== EDTA (L1) speciation ===
[L1]_total = 5.00e-03 M

Species peaks:
  H4EDTA              peak 20.9% at pH 2.0
  H3EDTA-             peak 32.7% at pH 2.0
  H2EDTA2-            peak 77.1% at pH 3.8
  HEDTA3-             peak 75.8% at pH 7.1
  EDTA                peak 80.0% at pH 12.0
  [Ni(EDTA)(OH)]3-    peak 20.0% at pH 2.0

Dominant species by pH region:
  pH   2.0–  2.1  →  H3EDTA-
  pH   2.1–  5.6  →  H2EDTA2-
  pH   5.6–  8.7  →  HEDTA3-
  pH   8.7– 12.0  →  EDTA

```
