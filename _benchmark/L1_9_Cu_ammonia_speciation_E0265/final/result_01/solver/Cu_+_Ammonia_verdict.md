# Speciation Calculation Report: Cu + Ammonia

## System Parameters
- Temperature: 25.0 °C
- Ionic mode: fixed
- Target ionic strength: 0.1 M
- Calculated ionic strength range: 5.54191e-05 – 0.051981 M
- Max inert ions: cation 0 M, anion 0 M
- pH range: 0.0 – 14.0
- Points: 141
- Converged: 141/141
- Redox mode: fixed
- Fixed E_V: +0.265 V

## Compiled Analytical Totals

| Constraint | Declared value (mol/L) | Meaning |
|------------|------------------------|---------|
| [Cu]_total | 0.001 | parent element total |
| [ligand_10103]_total | 0.1 | component total |

## Components

The metal entries below are conserved physical parent-element totals; oxidation-state species are partitioned within each element balance.

| ID | Name | Total (mol/L) | Type |
|-----|------|--------------|------|
| Cu | Cu | 1.00e-03 | metal |
| L1 | Ammonia | 1.00e-01 | ligand |

## Free-Energy Species Table

| Label | Phase | Stoich | log β | μ°_free (kJ/mol) | μ°_canon (kJ/mol) |
|-------|-------|--------|-------|------------------|-------------------|
| H2O | aqueous | — | — | +1.2557 | +1.2557 |
| HAmmonia+ | aqueous | L1:+1 H:+1 | — | -52.8532 | -52.8532 |
| Ammonia | aqueous | L1:+1 | — | -0.0000 | +0.0000 |
| Cu+ | aqueous | Cu$+1:+1 | — | +0.0000 | +0.0000 |
| [Cu(Ammo)2]+ | aqueous | L1:+2 Cu$+1:+1 | — | -56.6203 | -56.6203 |
| Cu2+ | aqueous | Cu$+2:+1 | — | +0.0000 | +0.0000 |
| [Cu(OH)]+ | aqueous | Cu$+2:+1 H:-1 | — | +45.0908 | +45.0908 |
| [Cu2(OH)2]2+ | aqueous | Cu$+2:+2 H:-2 | — | +63.9261 | +63.9261 |
| [Cu(OH)2] | aqueous | Cu$+2:+1 H:-2 | — | +92.4646 | +92.4646 |
| HCuO2- | aqueous | Cu$+2:+1 H:-3 | — | +152.4231 | +152.4231 |
| [Cu3(OH)4]2+ | aqueous | Cu$+2:+3 H:-4 | — | +128.4231 | +128.4231 |
| CuO22- | aqueous | Cu$+2:+1 H:-4 | — | +227.4004 | +227.4004 |
| [Cu(Ammo)4]2+ | aqueous | L1:+4 Cu$+2:+1 | — | -70.2046 | -70.2046 |
| [Cu(Ammo)3]2+ | aqueous | L1:+3 Cu$+2:+1 | — | -58.2185 | -58.2185 |
| [Cu(Ammo)2]2+ | aqueous | L1:+2 Cu$+2:+1 | — | -42.2369 | -42.2369 |
| [Cu(Ammo)]2+ | aqueous | L1:+1 Cu$+2:+1 | — | -23.4015 | -23.4015 |
| Cu2O | solid | Cu$+1:+2 H:-2 | — | +2.9706 | +2.9706 |
| Cu(OH)2 | solid | Cu$+2:+1 H:-2 | — | +52.5092 | +52.5092 |
| Cu | solid | Cu$+0:+1 | — | +0.0000 | +0.0000 |

## Precipitation

- pH 5.30: Cu2O (8.44e-05 M)
- pH 7.20: all solids dissolved
- pH 10.30: Cu(OH)2 (1.24e-04 M)
- pH 13.50: all solids dissolved

## Speciation Analysis

```
=== Cu (Cu) speciation ===
[Cu]_total = 1.00e-03 M
T = 25.0 °C,  I = 0.1 M
Convergence: 141/141

Species peaks:
  [Cu(Ammo)2]+        peak 65.4% at pH 7.2
  Cu2+                peak 98.7% at pH 0.0
  HCuO2-              peak 13.9% at pH 13.5
  CuO22-              peak 95.1% at pH 14.0
  [Cu(Ammo)4]2+       peak 90.8% at pH 10.2
  [Cu(Ammo)3]2+       peak 32.7% at pH 8.2
  [Cu(Ammo)2]2+       peak 15.4% at pH 7.2
  [Cu(Ammo)]2+        peak 9.8% at pH 5.3
  Cu2O                peak 72.0% at pH 6.2
  Cu(OH)2             peak 99.5% at pH 11.7

Dominant species by pH region:
  pH   0.0–  5.6  →  Cu2+
  pH   5.6–  7.0  →  Cu2O
  pH   7.0–  8.2  →  [Cu(Ammo)2]+
  pH   8.2–  8.3  →  [Cu(Ammo)3]2+
  pH   8.3– 10.5  →  [Cu(Ammo)4]2+
  pH  10.5– 13.4  →  Cu(OH)2
  pH  13.4– 14.0  →  CuO22-

Crossover pH values:
  [Cu(Ammo)2]+ ↔ Cu2+  at pH ≈ 6.25  (each ~8%)
  [Cu(Ammo)2]+ ↔ [Cu(Ammo)4]2+  at pH ≈ 8.17  (each ~30%)
  [Cu(Ammo)2]+ ↔ [Cu(Ammo)3]2+  at pH ≈ 8.13  (each ~32%)
  [Cu(Ammo)2]+ ↔ [Cu(Ammo)]2+  at pH ≈ 6.33  (each ~10%)
  [Cu(Ammo)2]+ ↔ Cu2O  at pH ≈ 6.93  (each ~38%)
  Cu2+ ↔ [Cu(Ammo)]2+  at pH ≈ 6.16  (each ~10%)
  Cu2+ ↔ Cu2O  at pH ≈ 5.51  (each ~44%)
  HCuO2- ↔ Cu(OH)2  at pH ≈ 13.44  (each ~13%)
  CuO22- ↔ Cu(OH)2  at pH ≈ 13.32  (each ~45%)
  [Cu(Ammo)4]2+ ↔ [Cu(Ammo)3]2+  at pH ≈ 8.21  (each ~33%)
  [Cu(Ammo)4]2+ ↔ [Cu(Ammo)2]2+  at pH ≈ 7.83  (each ~12%)
  [Cu(Ammo)4]2+ ↔ Cu(OH)2  at pH ≈ 10.45  (each ~48%)
  [Cu(Ammo)3]2+ ↔ [Cu(Ammo)2]2+  at pH ≈ 7.48  (each ~15%)
  [Cu(Ammo)3]2+ ↔ [Cu(Ammo)]2+  at pH ≈ 7.22  (each ~9%)
  [Cu(Ammo)3]2+ ↔ Cu2O  at pH ≈ 7.15  (each ~7%)
  [Cu(Ammo)3]2+ ↔ Cu(OH)2  at pH ≈ 10.26  (each ~8%)
  [Cu(Ammo)2]2+ ↔ [Cu(Ammo)]2+  at pH ≈ 6.97  (each ~10%)
  [Cu(Ammo)2]2+ ↔ Cu2O  at pH ≈ 7.11  (each ~13%)
  [Cu(Ammo)]2+ ↔ Cu2O  at pH ≈ 5.26  (each ~10%)
  [Cu(Ammo)]2+ ↔ Cu2O  at pH ≈ 7.14  (each ~9%)

=== Ammonia (L1) speciation ===
[L1]_total = 1.00e-01 M

Species peaks:
  HAmmonia+           peak 100.0% at pH 0.0
  Ammonia             peak 100.0% at pH 14.0

Dominant species by pH region:
  pH   0.0–  9.3  →  HAmmonia+
  pH   9.3– 14.0  →  Ammonia

```
