# Speciation Calculation Report: Ni$+2 + Ni$+0 + Ni$+3 + Ni$+4 + Glycine + Ammonia

## System Parameters
- Temperature: 25.0 °C
- Ionic mode: fixed
- Target ionic strength: 0.1 M
- Calculated ionic strength range: 0.00168798 – 0.00401651 M
- Max inert ions: cation 0 M, anion 0 M
- pH range: 6.0 – 10.0
- Points: 41
- Converged: 41/41
- Redox mode: excluded

## Compiled Analytical Totals

| Constraint | Declared value (mol/L) | Meaning |
|------------|------------------------|---------|
| [Ni$+0]_total | 0 | redox-state subtotal |
| [Ni$+2]_total | 0.001 | redox-state subtotal |
| [Ni$+3]_total | 0 | redox-state subtotal |
| [Ni$+4]_total | 0 | redox-state subtotal |
| [ligand_10103]_total | 0.005 | component total |
| [ligand_5760]_total | 0.005 | component total |

## Components

| ID | Name | Total (mol/L) | Type |
|-----|------|--------------|------|
| Ni$+0 | Ni(s) | 0.00e+00 | metal |
| Ni$+2 | Ni2+ | 1.00e-03 | metal |
| Ni$+3 | Ni(+3) | 0.00e+00 | metal |
| Ni$+4 | Ni(+4) | 0.00e+00 | metal |
| L1 | Glycine | 5.00e-03 | ligand |
| L2 | Ammonia | 5.00e-03 | ligand |

## Free-Energy Species Table

| Label | Phase | Stoich | log β | μ°_free (kJ/mol) | μ°_canon (kJ/mol) |
|-------|-------|--------|-------|------------------|-------------------|
| H2O | aqueous | — | — | +1.2557 | +1.2557 |
| H2Glycine+ | aqueous | L1:+1 H:+2 | — | -67.9215 | -13.2989 |
| HGlycine | aqueous | L1:+1 H:+1 | — | -54.6226 | +0.0000 |
| Glycine | aqueous | L1:+1 | — | -0.0000 | +54.6226 |
| HAmmonia+ | aqueous | L2:+1 H:+1 | — | -52.8532 | -52.8532 |
| Ammonia | aqueous | L2:+1 | — | -0.0000 | +0.0000 |
| Ni2+ | aqueous | Ni$+2:+1 | — | -0.0000 | +0.0000 |
| [Ni(OH)]+ | aqueous | H:-1 Ni$+2:+1 | — | +59.3600 | +59.3600 |
| [Ni(OH)2] | aqueous | H:-2 Ni$+2:+1 | — | +108.4461 | +108.4461 |
| [Ni(OH)3]- | aqueous | H:-3 Ni$+2:+1 | — | +171.2308 | +171.2308 |
| [Ni4(OH)4]4+ | aqueous | H:-4 Ni$+2:+4 | — | +158.1031 | +158.1031 |
| [Ni(Glyc)]+ | aqueous | L1:+1 Ni$+2:+1 | — | -32.7622 | +21.8605 |
| [Ni(Glyc)2] | aqueous | L1:+2 Ni$+2:+1 | — | -60.3874 | +48.8578 |
| [Ni(Glyc)3]- | aqueous | L1:+3 Ni$+2:+1 | — | -80.4785 | +83.3894 |
| [Ni(Ammo)5]2+ | aqueous | L2:+5 Ni$+2:+1 | — | -47.5451 | -47.5451 |
| [Ni(Ammo)6]2+ | aqueous | L2:+6 Ni$+2:+1 | — | -47.3738 | -47.3738 |
| [Ni(Ammo)4]2+ | aqueous | L2:+4 Ni$+2:+1 | — | -43.7780 | -43.7780 |
| [Ni(Ammo)3]2+ | aqueous | L2:+3 Ni$+2:+1 | — | -37.3283 | -37.3283 |
| [Ni(Ammo)2]2+ | aqueous | L2:+2 Ni$+2:+1 | — | -27.9106 | -27.9106 |
| [Ni(Ammo)]2+ | aqueous | L2:+1 Ni$+2:+1 | — | -15.5820 | -15.5820 |
| [Ni(OH)2](s) | solid | H:-2 Ni$+2:+1 | — | +73.0585 | +73.0585 |

## Speciation Analysis

```
=== Ni(s) (Ni$+0) speciation ===
[Ni$+0]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 41/41

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Ni2+ (Ni$+2) speciation ===
[Ni$+2]_total = 1.00e-03 M
T = 25.0 °C,  I = 0.1 M
Convergence: 41/41

Species peaks:
  Ni2+                peak 68.5% at pH 6.0
  [Ni(Glyc)]+         peak 51.8% at pH 6.8
  [Ni(Glyc)2]         peak 63.3% at pH 7.8
  [Ni(Glyc)3]-        peak 85.1% at pH 10.0

Dominant species by pH region:
  pH   6.0–  6.5  →  Ni2+
  pH   6.5–  7.2  →  [Ni(Glyc)]+
  pH   7.2–  8.5  →  [Ni(Glyc)2]
  pH   8.5– 10.0  →  [Ni(Glyc)3]-

Crossover pH values:
  Ni2+ ↔ [Ni(Glyc)]+  at pH ≈ 6.41  (each ~45%)
  Ni2+ ↔ [Ni(Glyc)2]  at pH ≈ 6.79  (each ~24%)
  Ni2+ ↔ [Ni(Glyc)3]-  at pH ≈ 7.34  (each ~6%)
  [Ni(Glyc)]+ ↔ [Ni(Glyc)2]  at pH ≈ 7.18  (each ~44%)
  [Ni(Glyc)]+ ↔ [Ni(Glyc)3]-  at pH ≈ 7.82  (each ~18%)
  [Ni(Glyc)2] ↔ [Ni(Glyc)3]-  at pH ≈ 8.48  (each ~48%)

=== Ni(+3) (Ni$+3) speciation ===
[Ni$+3]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 41/41

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Ni(+4) (Ni$+4) speciation ===
[Ni$+4]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 41/41

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Glycine (L1) speciation ===
[L1]_total = 5.00e-03 M

Species peaks:
  HGlycine            peak 93.2% at pH 6.0
  Glycine             peak 35.1% at pH 10.0
  [Ni(Glyc)]+         peak 10.4% at pH 6.8
  [Ni(Glyc)2]         peak 25.3% at pH 7.8
  [Ni(Glyc)3]-        peak 51.1% at pH 10.0

Dominant species by pH region:
  pH   6.0–  8.9  →  HGlycine
  pH   8.9– 10.0  →  [Ni(Glyc)3]-

=== Ammonia (L2) speciation ===
[L2]_total = 5.00e-03 M

Species peaks:
  HAmmonia+           peak 99.9% at pH 6.0
  Ammonia             peak 84.6% at pH 10.0

Dominant species by pH region:
  pH   6.0–  9.3  →  HAmmonia+
  pH   9.3– 10.0  →  Ammonia

```
