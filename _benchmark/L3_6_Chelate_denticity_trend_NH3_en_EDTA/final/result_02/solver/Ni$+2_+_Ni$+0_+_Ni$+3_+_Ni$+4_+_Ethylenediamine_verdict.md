# Speciation Calculation Report: Ni$+2 + Ni$+0 + Ni$+3 + Ni$+4 + Ethylenediamine

## System Parameters
- Temperature: 25.0 °C
- Ionic mode: fixed
- Target ionic strength: 0.1 M
- Calculated ionic strength range: 0.0322725 – 0.0531416 M
- Max inert ions: cation 0 M, anion 0 M
- pH range: 6.5 – 7.5
- Points: 11
- Converged: 11/11
- Redox mode: excluded

## Compiled Analytical Totals

| Constraint | Declared value (mol/L) | Meaning |
|------------|------------------------|---------|
| [Ni$+0]_total | 0 | redox-state subtotal |
| [Ni$+2]_total | 0.001 | redox-state subtotal |
| [Ni$+3]_total | 0 | redox-state subtotal |
| [Ni$+4]_total | 0 | redox-state subtotal |
| [ligand_7029]_total | 0.03 | component total |

## Components

| ID | Name | Total (mol/L) | Type |
|-----|------|--------------|------|
| Ni$+0 | Ni(s) | 0.00e+00 | metal |
| Ni$+2 | Ni2+ | 1.00e-03 | metal |
| Ni$+3 | Ni(+3) | 0.00e+00 | metal |
| Ni$+4 | Ni(+4) | 0.00e+00 | metal |
| L1 | Ethylenediamine | 3.00e-02 | ligand |

## Free-Energy Species Table

| Label | Phase | Stoich | log β | μ°_free (kJ/mol) | μ°_canon (kJ/mol) |
|-------|-------|--------|-------|------------------|-------------------|
| H2O | aqueous | — | — | +1.2557 | +1.2557 |
| H2Ethylenediamine2+ | aqueous | L1:+1 H:+2 | — | -97.2020 | -97.2020 |
| HEthylenediamine+ | aqueous | L1:+1 H:+1 | — | -56.6203 | -56.6203 |
| Ethylenediamine | aqueous | L1:+1 | — | -0.0000 | +0.0000 |
| Ni2+ | aqueous | Ni$+2:+1 | — | -0.0000 | +0.0000 |
| [Ni(OH)]+ | aqueous | H:-1 Ni$+2:+1 | — | +59.3600 | +59.3600 |
| [Ni(OH)2] | aqueous | H:-2 Ni$+2:+1 | — | +108.4461 | +108.4461 |
| [Ni(OH)3]- | aqueous | H:-3 Ni$+2:+1 | — | +171.2308 | +171.2308 |
| [Ni4(OH)4]4+ | aqueous | H:-4 Ni$+2:+4 | — | +158.1031 | +158.1031 |
| [Ni(Ethy)3]2+ | aqueous | L1:+3 Ni$+2:+1 | — | -99.9417 | -99.9417 |
| [Ni(Ethy)2]2+ | aqueous | L1:+2 Ni$+2:+1 | — | -76.7114 | -76.7114 |
| [Ni(Ethy)]2+ | aqueous | L1:+1 Ni$+2:+1 | — | -41.6662 | -41.6662 |
| Ni(OH)2 | solid | H:-2 Ni$+2:+1 | — | +66.8603 | +66.8603 |

## Speciation Analysis

```
=== Ni(s) (Ni$+0) speciation ===
[Ni$+0]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 11/11

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Ni2+ (Ni$+2) speciation ===
[Ni$+2]_total = 1.00e-03 M
T = 25.0 °C,  I = 0.1 M
Convergence: 11/11

Species peaks:
  [Ni(Ethy)3]2+       peak 42.2% at pH 7.5
  [Ni(Ethy)2]2+       peak 84.3% at pH 6.9
  [Ni(Ethy)]2+        peak 33.2% at pH 6.5

Dominant species by pH region:
  pH   6.5–  7.5  →  [Ni(Ethy)2]2+

Crossover pH values:
  [Ni(Ethy)3]2+ ↔ [Ni(Ethy)]2+  at pH ≈ 6.92  (each ~8%)

=== Ni(+3) (Ni$+3) speciation ===
[Ni$+3]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 11/11

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Ni(+4) (Ni$+4) speciation ===
[Ni$+4]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 11/11

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Ethylenediamine (L1) speciation ===
[L1]_total = 3.00e-02 M

Species peaks:
  H2Ethylenediamine2+  peak 82.2% at pH 6.5
  HEthylenediamine+   peak 55.0% at pH 7.5
  [Ni(Ethy)2]2+       peak 5.6% at pH 6.9

Dominant species by pH region:
  pH   6.5–  7.4  →  H2Ethylenediamine2+
  pH   7.4–  7.5  →  HEthylenediamine+

```
