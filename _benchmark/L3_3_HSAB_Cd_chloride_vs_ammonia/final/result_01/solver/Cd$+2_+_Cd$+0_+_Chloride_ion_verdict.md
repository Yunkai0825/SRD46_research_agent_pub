# Speciation Calculation Report: Cd$+2 + Cd$+0 + Chloride ion

## System Parameters
- Temperature: 25.0 °C
- Ionic mode: fixed
- Target ionic strength: 0.1 M
- Calculated ionic strength range: 0.0500001 – 0.0503334 M
- Max inert ions: cation 0 M, anion 0 M
- pH range: 2.0 – 12.0
- Points: 51
- Converged: 51/51
- Redox mode: excluded

## Compiled Analytical Totals

| Constraint | Declared value (mol/L) | Meaning |
|------------|------------------------|---------|
| [Cd$+0]_total | 0 | redox-state subtotal |
| [Cd$+2]_total | 0.001 | redox-state subtotal |
| [ligand_10163]_total | 0.1 | component total |

## Components

| ID | Name | Total (mol/L) | Type |
|-----|------|--------------|------|
| Cd$+0 | Cd(s) | 0.00e+00 | metal |
| Cd$+2 | Cd2+ | 1.00e-03 | metal |
| L1 | Chloride ion | 1.00e-01 | ligand |

## Free-Energy Species Table

| Label | Phase | Stoich | log β | μ°_free (kJ/mol) | μ°_canon (kJ/mol) |
|-------|-------|--------|-------|------------------|-------------------|
| H2O | aqueous | — | — | +1.2557 | +1.2557 |
| Chloride ion | aqueous | L1:+1 | — | -0.0000 | +0.0000 |
| Cd2+ | aqueous | Cd$+2:+1 | — | -0.0000 | +0.0000 |
| [Cd2(OH)]3+ | aqueous | Cd$+2:+2 H:-1 | — | +51.0268 | +51.0268 |
| [Cd(OH)]+ | aqueous | Cd$+2:+1 H:-1 | — | +57.6477 | +57.6477 |
| [Cd(OH)2] | aqueous | Cd$+2:+1 H:-2 | — | +115.8661 | +115.8661 |
| [Cd(OH)3]- | aqueous | Cd$+2:+1 H:-3 | — | +180.9338 | +180.9338 |
| [Cd4(OH)4]4+ | aqueous | Cd$+2:+4 H:-4 | — | +187.2123 | +187.2123 |
| [Cd(OH)4]2- | aqueous | Cd$+2:+1 H:-4 | — | +251.1384 | +251.1384 |
| [Cd(Chlo)2] | aqueous | L1:+2 Cd$+2:+1 | — | -14.8400 | -14.8400 |
| [Cd(Chlo)3]- | aqueous | L1:+3 Cd$+2:+1 | — | -13.6985 | -13.6985 |
| [Cd(Chlo)]+ | aqueous | L1:+1 Cd$+2:+1 | — | -8.6757 | -8.6757 |
| [Cd(OH)2(s,beta)] | solid | Cd$+2:+1 H:-2 | — | +77.9100 | +77.9100 |
| Cd | solid | Cd$+0:+1 | — | +0.0000 | +0.0000 |

## Precipitation

- pH 8.80: [Cd(OH)2(s,beta)] (4.09e-04 M)

## Speciation Analysis

```
=== Cd(s) (Cd$+0) speciation ===
[Cd$+0]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 51/51

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Cd2+ (Cd$+2) speciation ===
[Cd$+2]_total = 1.00e-03 M
T = 25.0 °C,  I = 0.1 M
Convergence: 51/51

Species peaks:
  Cd2+                peak 31.5% at pH 2.0
  [Cd(Chlo)2]         peak 28.1% at pH 2.0
  [Cd(Chlo)]+         peak 38.6% at pH 2.0
  [Cd(OH)2(s,beta)]   peak 100.0% at pH 10.8

Dominant species by pH region:
  pH   2.0–  8.8  →  [Cd(Chlo)]+
  pH   8.8– 12.0  →  [Cd(OH)2(s,beta)]

Crossover pH values:
  Cd2+ ↔ [Cd(OH)2(s,beta)]  at pH ≈ 8.72  (each ~24%)
  [Cd(Chlo)2] ↔ [Cd(OH)2(s,beta)]  at pH ≈ 8.71  (each ~22%)
  [Cd(Chlo)]+ ↔ [Cd(OH)2(s,beta)]  at pH ≈ 8.74  (each ~28%)

=== Chloride ion (L1) speciation ===
[L1]_total = 1.00e-01 M

Species peaks:
  Chloride ion        peak 100.0% at pH 12.0

Dominant species by pH region:
  pH   2.0– 12.0  →  Chloride ion

```
