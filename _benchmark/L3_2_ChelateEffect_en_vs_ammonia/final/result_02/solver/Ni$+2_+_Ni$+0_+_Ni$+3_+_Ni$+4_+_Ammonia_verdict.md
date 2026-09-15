# Speciation Calculation Report: Ni$+2 + Ni$+0 + Ni$+3 + Ni$+4 + Ammonia

## System Parameters
- Temperature: 25.0 °C
- Ionic mode: fixed
- Target ionic strength: 0.1 M
- Calculated ionic strength range: 0.0117456 – 0.0119733 M
- Max inert ions: cation 0 M, anion 0 M
- pH range: 6.5 – 7.5
- Points: 21
- Converged: 21/21
- Redox mode: excluded

## Compiled Analytical Totals

| Constraint | Declared value (mol/L) | Meaning |
|------------|------------------------|---------|
| [Ni$+0]_total | 0 | redox-state subtotal |
| [Ni$+2]_total | 0.001 | redox-state subtotal |
| [Ni$+3]_total | 0 | redox-state subtotal |
| [Ni$+4]_total | 0 | redox-state subtotal |
| [ligand_10103]_total | 0.02 | component total |

## Components

| ID | Name | Total (mol/L) | Type |
|-----|------|--------------|------|
| Ni$+0 | Ni(s) | 0.00e+00 | metal |
| Ni$+2 | Ni2+ | 1.00e-03 | metal |
| Ni$+3 | Ni(+3) | 0.00e+00 | metal |
| Ni$+4 | Ni(+4) | 0.00e+00 | metal |
| L1 | Ammonia | 2.00e-02 | ligand |

## Free-Energy Species Table

| Label | Phase | Stoich | log β | μ°_free (kJ/mol) | μ°_canon (kJ/mol) |
|-------|-------|--------|-------|------------------|-------------------|
| H2O | aqueous | — | — | +1.2557 | +1.2557 |
| HAmmonia+ | aqueous | L1:+1 H:+1 | — | -52.8532 | -52.8532 |
| Ammonia | aqueous | L1:+1 | — | -0.0000 | +0.0000 |
| Ni2+ | aqueous | Ni$+2:+1 | — | +0.0000 | +0.0000 |
| [Ni(OH)]+ | aqueous | H:-1 Ni$+2:+1 | — | +59.3600 | +59.3600 |
| [Ni(OH)2] | aqueous | H:-2 Ni$+2:+1 | — | +108.4461 | +108.4461 |
| HNiO2- | aqueous | H:-3 Ni$+2:+1 | — | +169.9959 | +169.9959 |
| [Ni4(OH)4]4+ | aqueous | H:-4 Ni$+2:+4 | — | +158.1031 | +158.1031 |
| [Ni(Ammo)5]2+ | aqueous | L1:+5 Ni$+2:+1 | — | -47.5451 | -47.5451 |
| [Ni(Ammo)6]2+ | aqueous | L1:+6 Ni$+2:+1 | — | -47.3738 | -47.3738 |
| [Ni(Ammo)4]2+ | aqueous | L1:+4 Ni$+2:+1 | — | -43.7780 | -43.7780 |
| [Ni(Ammo)3]2+ | aqueous | L1:+3 Ni$+2:+1 | — | -37.3283 | -37.3283 |
| [Ni(Ammo)2]2+ | aqueous | L1:+2 Ni$+2:+1 | — | -27.9106 | -27.9106 |
| [Ni(Ammo)]2+ | aqueous | L1:+1 Ni$+2:+1 | — | -15.5820 | -15.5820 |
| Ni(OH)2 | solid | H:-2 Ni$+2:+1 | — | +66.8603 | +66.8603 |
| Ni | solid | Ni$+0:+1 | — | +0.0000 | +0.0000 |

## Speciation Analysis

```
=== Ni(s) (Ni$+0) speciation ===
[Ni$+0]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 21/21

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Ni2+ (Ni$+2) speciation ===
[Ni$+2]_total = 1.00e-03 M
T = 25.0 °C,  I = 0.1 M
Convergence: 21/21

Species peaks:
  Ni2+                peak 98.2% at pH 6.5
  [Ni(Ammo)]2+        peak 15.3% at pH 7.5

Dominant species by pH region:
  pH   6.5–  7.5  →  Ni2+

Crossover pH values:

=== Ni(+3) (Ni$+3) speciation ===
[Ni$+3]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 21/21

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Ni(+4) (Ni$+4) speciation ===
[Ni$+4]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 21/21

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Ammonia (L1) speciation ===
[L1]_total = 2.00e-02 M

Species peaks:
  HAmmonia+           peak 99.7% at pH 6.5

Dominant species by pH region:
  pH   6.5–  7.5  →  HAmmonia+

```
