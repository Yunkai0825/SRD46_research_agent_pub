# Speciation Calculation Report: Cd$+2 + Cd$+0 + Ammonia

## System Parameters
- Temperature: 25.0 °C
- Ionic mode: fixed
- Target ionic strength: 0.1 M
- Calculated ionic strength range: 9.57134e-05 – 0.052 M
- Max inert ions: cation 0 M, anion 0 M
- pH range: 2.0 – 12.0
- Points: 101
- Converged: 101/101
- Redox mode: excluded

## Compiled Analytical Totals

| Constraint | Declared value (mol/L) | Meaning |
|------------|------------------------|---------|
| [Cd$+0]_total | 0 | redox-state subtotal |
| [Cd$+2]_total | 0.001 | redox-state subtotal |
| [ligand_10103]_total | 0.1 | component total |

## Components

| ID | Name | Total (mol/L) | Type |
|-----|------|--------------|------|
| Cd$+0 | Cd(s) | 0.00e+00 | metal |
| Cd$+2 | Cd2+ | 1.00e-03 | metal |
| L1 | Ammonia | 1.00e-01 | ligand |

## Free-Energy Species Table

| Label | Phase | Stoich | log β | μ°_free (kJ/mol) | μ°_canon (kJ/mol) |
|-------|-------|--------|-------|------------------|-------------------|
| H2O | aqueous | — | — | +1.2557 | +1.2557 |
| HAmmonia+ | aqueous | L1:+1 H:+1 | — | -52.8532 | -52.8532 |
| Ammonia | aqueous | L1:+1 | — | -0.0000 | +0.0000 |
| Cd2+ | aqueous | Cd$+2:+1 | — | -0.0000 | +0.0000 |
| [Cd2(OH)]3+ | aqueous | Cd$+2:+2 H:-1 | — | +53.6523 | +53.6523 |
| [Cd(OH)]+ | aqueous | Cd$+2:+1 H:-1 | — | +57.6477 | +57.6477 |
| [Cd(OH)2] | aqueous | Cd$+2:+1 H:-2 | — | +115.8661 | +115.8661 |
| [Cd(OH)3]- | aqueous | Cd$+2:+1 H:-3 | — | +180.9338 | +180.9338 |
| [Cd4(OH)4]4+ | aqueous | Cd$+2:+4 H:-4 | — | +187.2123 | +187.2123 |
| [Cd(OH)4]2- | aqueous | Cd$+2:+1 H:-4 | — | +251.1384 | +251.1384 |
| [Cd(Ammo)4]2+ | aqueous | L1:+4 Cd$+2:+1 | — | -38.3557 | -38.3557 |
| [Cd(Ammo)3]2+ | aqueous | L1:+3 Cd$+2:+1 | — | -33.6754 | -33.6754 |
| [Cd(Ammo)2]2+ | aqueous | L1:+2 Cd$+2:+1 | — | -26.0271 | -26.0271 |
| [Cd(Ammo)]2+ | aqueous | L1:+1 Cd$+2:+1 | — | -14.6688 | -14.6688 |
| [Cd(OH)2(s,beta)] | solid | Cd$+2:+1 H:-2 | — | +77.9100 | +77.9100 |

## Precipitation

- pH 9.90: [Cd(OH)2(s,beta)] (1.03e-05 M)

## Speciation Analysis

```
=== Cd(s) (Cd$+0) speciation ===
[Cd$+0]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 101/101

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Cd2+ (Cd$+2) speciation ===
[Cd$+2]_total = 1.00e-03 M
T = 25.0 °C,  I = 0.1 M
Convergence: 101/101

Species peaks:
  Cd2+                peak 100.0% at pH 2.0
  [Cd(Ammo)4]2+       peak 23.7% at pH 9.9
  [Cd(Ammo)3]2+       peak 45.6% at pH 9.8
  [Cd(Ammo)2]2+       peak 48.2% at pH 8.7
  [Cd(Ammo)]2+        peak 47.9% at pH 8.0
  [Cd(OH)2(s,beta)]   peak 99.8% at pH 11.6

Dominant species by pH region:
  pH   2.0–  7.8  →  Cd2+
  pH   7.8–  8.4  →  [Cd(Ammo)]2+
  pH   8.4–  9.3  →  [Cd(Ammo)2]2+
  pH   9.3– 10.1  →  [Cd(Ammo)3]2+
  pH  10.1– 12.0  →  [Cd(OH)2(s,beta)]

Crossover pH values:
  Cd2+ ↔ [Cd(Ammo)3]2+  at pH ≈ 8.35  (each ~10%)
  Cd2+ ↔ [Cd(Ammo)2]2+  at pH ≈ 8.01  (each ~25%)
  Cd2+ ↔ [Cd(Ammo)]2+  at pH ≈ 7.71  (each ~44%)
  [Cd(Ammo)4]2+ ↔ [Cd(Ammo)2]2+  at pH ≈ 10.01  (each ~17%)
  [Cd(Ammo)4]2+ ↔ [Cd(Ammo)]2+  at pH ≈ 9.13  (each ~10%)
  [Cd(Ammo)4]2+ ↔ [Cd(OH)2(s,beta)]  at pH ≈ 9.97  (each ~20%)
  [Cd(Ammo)3]2+ ↔ [Cd(Ammo)2]2+  at pH ≈ 9.21  (each ~39%)
  [Cd(Ammo)3]2+ ↔ [Cd(Ammo)]2+  at pH ≈ 8.71  (each ~23%)
  [Cd(Ammo)3]2+ ↔ [Cd(OH)2(s,beta)]  at pH ≈ 10.02  (each ~32%)
  [Cd(Ammo)2]2+ ↔ [Cd(Ammo)]2+  at pH ≈ 8.32  (each ~40%)
  [Cd(Ammo)2]2+ ↔ [Cd(OH)2(s,beta)]  at pH ≈ 9.97  (each ~21%)

=== Ammonia (L1) speciation ===
[L1]_total = 1.00e-01 M

Species peaks:
  HAmmonia+           peak 100.0% at pH 2.0
  Ammonia             peak 99.8% at pH 12.0

Dominant species by pH region:
  pH   2.0–  9.3  →  HAmmonia+
  pH   9.3– 12.0  →  Ammonia

```
