# Speciation Calculation Report: Co$+2 + Co$+0 + Co$+3 + Co$+4 + Ethylenediamine

## System Parameters
- Temperature: 25.0 °C
- Ionic mode: fixed
- Target ionic strength: 0.1 M
- Calculated ionic strength range: 0.00078771 – 0.0219999 M
- Max inert ions: cation 0 M, anion 0 M
- pH range: 2.0 – 12.0
- Points: 101
- Converged: 101/101
- Redox mode: excluded

## Compiled Analytical Totals

| Constraint | Declared value (mol/L) | Meaning |
|------------|------------------------|---------|
| [Co$+0]_total | 0 | redox-state subtotal |
| [Co$+2]_total | 0.001 | redox-state subtotal |
| [Co$+3]_total | 0 | redox-state subtotal |
| [Co$+4]_total | 0 | redox-state subtotal |
| [ligand_7029]_total | 0.01 | component total |

## Components

| ID | Name | Total (mol/L) | Type |
|-----|------|--------------|------|
| Co$+0 | Co(s) | 0.00e+00 | metal |
| Co$+2 | Co2+ | 1.00e-03 | metal |
| Co$+3 | Co3+ | 0.00e+00 | metal |
| Co$+4 | Co(+4) | 0.00e+00 | metal |
| L1 | Ethylenediamine | 1.00e-02 | ligand |

## Free-Energy Species Table

| Label | Phase | Stoich | log β | μ°_free (kJ/mol) | μ°_canon (kJ/mol) |
|-------|-------|--------|-------|------------------|-------------------|
| H2O | aqueous | — | — | +1.2557 | +1.2557 |
| H2Ethylenediamine2+ | aqueous | L1:+1 H:+2 | — | -97.2020 | -97.2020 |
| HEthylenediamine+ | aqueous | L1:+1 H:+1 | — | -56.6203 | -56.6203 |
| Ethylenediamine | aqueous | L1:+1 | — | -0.0000 | +0.0000 |
| Co2+ | aqueous | Co$+2:+1 | — | -0.0000 | +0.0000 |
| [Co(OH)]+ | aqueous | Co$+2:+1 H:-1 | — | +55.3646 | +55.3646 |
| [Co2(OH)]3+ | aqueous | Co$+2:+2 H:-1 | — | +62.7846 | +62.7846 |
| [Co(OH)2] | aqueous | Co$+2:+1 H:-2 | — | +107.3046 | +107.3046 |
| [Co(OH)3]- | aqueous | Co$+2:+1 H:-3 | — | +179.7923 | +179.7923 |
| [Co4(OH)4]4+ | aqueous | Co$+2:+4 H:-4 | — | +174.0846 | +174.0846 |
| [Co(OH)4]2- | aqueous | Co$+2:+1 H:-4 | — | +264.2661 | +264.2661 |
| [Co(Ethy)3]2+ | aqueous | L1:+3 Co$+2:+1 | — | -76.4831 | -76.4831 |
| [Co(Ethy)2]2+ | aqueous | L1:+2 Co$+2:+1 | — | -57.6477 | -57.6477 |
| [Co(Ethy)]2+ | aqueous | L1:+1 Co$+2:+1 | — | -31.3923 | -31.3923 |
| [Co(OH)2](s) | solid | Co$+2:+1 H:-2 | — | +74.7708 | +74.7708 |

## Precipitation

- pH 11.70: [Co(OH)2](s) (1.30e-04 M)

## Speciation Analysis

```
=== Co(s) (Co$+0) speciation ===
[Co$+0]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 101/101

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Co2+ (Co$+2) speciation ===
[Co$+2]_total = 1.00e-03 M
T = 25.0 °C,  I = 0.1 M
Convergence: 101/101

Species peaks:
  Co2+                peak 100.0% at pH 2.0
  [Co(Ethy)3]2+       peak 93.1% at pH 11.5
  [Co(Ethy)2]2+       peak 68.6% at pH 8.1
  [Co(Ethy)]2+        peak 57.9% at pH 7.2
  [Co(OH)2](s)        peak 62.2% at pH 12.0

Dominant species by pH region:
  pH   2.0–  7.0  →  Co2+
  pH   7.0–  7.6  →  [Co(Ethy)]2+
  pH   7.6–  8.8  →  [Co(Ethy)2]2+
  pH   8.8– 12.0  →  [Co(Ethy)3]2+
  pH  12.0– 12.0  →  [Co(OH)2](s)

Crossover pH values:
  Co2+ ↔ [Co(Ethy)2]2+  at pH ≈ 7.25  (each ~21%)
  Co2+ ↔ [Co(Ethy)]2+  at pH ≈ 6.96  (each ~47%)
  [Co(Ethy)3]2+ ↔ [Co(Ethy)2]2+  at pH ≈ 8.79  (each ~49%)
  [Co(Ethy)3]2+ ↔ [Co(Ethy)]2+  at pH ≈ 8.14  (each ~15%)
  [Co(Ethy)3]2+ ↔ [Co(OH)2](s)  at pH ≈ 11.90  (each ~48%)
  [Co(Ethy)2]2+ ↔ [Co(Ethy)]2+  at pH ≈ 7.58  (each ~46%)
  [Co(Ethy)2]2+ ↔ [Co(OH)2](s)  at pH ≈ 11.65  (each ~6%)

=== Co3+ (Co$+3) speciation ===
[Co$+3]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 101/101

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Co(+4) (Co$+4) speciation ===
[Co$+4]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 101/101

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Ethylenediamine (L1) speciation ===
[L1]_total = 1.00e-02 M

Species peaks:
  H2Ethylenediamine2+  peak 100.0% at pH 2.0
  HEthylenediamine+   peak 70.1% at pH 8.4
  Ethylenediamine     peak 88.2% at pH 12.0
  [Co(Ethy)3]2+       peak 27.9% at pH 11.5
  [Co(Ethy)2]2+       peak 13.7% at pH 8.1
  [Co(Ethy)]2+        peak 5.8% at pH 7.2

Dominant species by pH region:
  pH   2.0–  7.4  →  H2Ethylenediamine2+
  pH   7.4– 10.0  →  HEthylenediamine+
  pH  10.0– 12.0  →  Ethylenediamine

```
