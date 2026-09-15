# Speciation Calculation Report: Fe$+2 + Fe$+0 + Fe$+3 + Fe$+6 + Citric acid

## System Parameters
- Temperature: 25.0 °C
- Ionic mode: fixed
- Target ionic strength: 0.1 M
- Calculated ionic strength range: 0.00672425 – 0.0224987 M
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
| [ligand_9058]_total | 0.005 | component total |

## Components

| ID | Name | Total (mol/L) | Type |
|-----|------|--------------|------|
| Fe$+0 | Fe(s) | 0.00e+00 | metal |
| Fe$+2 | Fe2+ | 0.00e+00 | metal |
| Fe$+3 | Fe3+ | 1.00e-03 | metal |
| Fe$+6 | Fe(+6) | 0.00e+00 | metal |
| L1 | Citric acid | 5.00e-03 | ligand |

## Free-Energy Species Table

| Label | Phase | Stoich | log β | μ°_free (kJ/mol) | μ°_canon (kJ/mol) |
|-------|-------|--------|-------|------------------|-------------------|
| H2O | aqueous | — | — | +1.2557 | +1.2557 |
| H3Citric acid | aqueous | L1:+1 H:+3 | — | -73.6292 | +0.0000 |
| H2Citric acid- | aqueous | L1:+1 H:+2 | — | -57.0769 | +16.5523 |
| HCitric acid2- | aqueous | L1:+1 H:+1 | — | -32.2485 | +41.3808 |
| Citric acid | aqueous | L1:+1 | — | -0.0000 | +73.6292 |
| Fe3+ | aqueous | Fe$+3:+1 | — | -0.0000 | +0.0000 |
| [Fe(OH)]2+ | aqueous | Fe$+3:+1 H:-1 | — | +15.5820 | +15.5820 |
| [Fe2(OH)2]4+ | aqueous | Fe$+3:+2 H:-2 | — | +16.3240 | +16.3240 |
| [Fe(OH)2]+ | aqueous | Fe$+3:+1 H:-2 | — | +34.8169 | +34.8169 |
| [Fe3(OH)4]5+ | aqueous | Fe$+3:+3 H:-4 | — | +35.9585 | +35.9585 |
| [Fe(OH)4]- | aqueous | Fe$+3:+1 H:-4 | — | +123.2861 | +123.2861 |
| [Fe(Citr)H]+ | aqueous | L1:+1 Fe$+3:+1 H:+1 | — | -70.4900 | +3.1392 |
| [Fe(Citr)] | aqueous | L1:+1 Fe$+3:+1 | — | -63.8691 | +9.7602 |
| [Fe(Citr)(OH)]- | aqueous | L1:+1 Fe$+3:+1 H:-1 | — | -48.4583 | +25.1709 |
| [Fe2(Citr)2(OH)2]2- | aqueous | L1:+2 Fe$+3:+2 H:-2 | — | -121.0031 | +26.2554 |
| [Fe(OH)3](s) | solid | Fe$+3:+1 H:-3 | — | +18.2646 | +18.2646 |

## Precipitation

- pH 6.10: [Fe(OH)3](s) (2.99e-04 M)

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
  [Fe(Citr)(OH)]-     peak 12.7% at pH 6.0
  [Fe2(Citr)2(OH)2]2-  peak 87.3% at pH 6.0
  [Fe(OH)3](s)        peak 100.0% at pH 8.9

Dominant species by pH region:
  pH   4.0–  6.2  →  [Fe2(Citr)2(OH)2]2-
  pH   6.2–  9.0  →  [Fe(OH)3](s)

Crossover pH values:
  [Fe(Citr)(OH)]- ↔ [Fe(OH)3](s)  at pH ≈ 6.04  (each ~12%)
  [Fe2(Citr)2(OH)2]2- ↔ [Fe(OH)3](s)  at pH ≈ 6.15  (each ~45%)

=== Fe(+6) (Fe$+6) speciation ===
[Fe$+6]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 51/51

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Citric acid (L1) speciation ===
[L1]_total = 5.00e-03 M

Species peaks:
  H2Citric acid-      peak 33.9% at pH 4.0
  HCitric acid2-      peak 50.7% at pH 4.5
  Citric acid         peak 100.0% at pH 9.0
  [Fe2(Citr)2(OH)2]2-  peak 17.5% at pH 6.0

Dominant species by pH region:
  pH   4.0–  5.1  →  HCitric acid2-
  pH   5.1–  9.0  →  Citric acid

```
