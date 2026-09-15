# Speciation Calculation Report: Ni$+2 + Ni$+0 + Ni$+3 + Ni$+4 + Glycine

## System Parameters
- Temperature: 25.0 °C
- Ionic mode: fixed
- Target ionic strength: 0.1 M
- Calculated ionic strength range: 0.000240684 – 0.00392217 M
- Max inert ions: cation 0 M, anion 0 M
- pH range: 4.0 – 11.0
- Points: 71
- Converged: 71/71
- Redox mode: excluded

## Compiled Analytical Totals

| Constraint | Declared value (mol/L) | Meaning |
|------------|------------------------|---------|
| [Ni$+0]_total | 0 | redox-state subtotal |
| [Ni$+2]_total | 0.001 | redox-state subtotal |
| [Ni$+3]_total | 0 | redox-state subtotal |
| [Ni$+4]_total | 0 | redox-state subtotal |
| [ligand_5760]_total | 0.01 | component total |

## Components

| ID | Name | Total (mol/L) | Type |
|-----|------|--------------|------|
| Ni$+0 | Ni(s) | 0.00e+00 | metal |
| Ni$+2 | Ni2+ | 1.00e-03 | metal |
| Ni$+3 | Ni(+3) | 0.00e+00 | metal |
| Ni$+4 | Ni(+4) | 0.00e+00 | metal |
| L1 | Glycine | 1.00e-02 | ligand |

## Free-Energy Species Table

| Label | Phase | Stoich | log β | μ°_free (kJ/mol) | μ°_canon (kJ/mol) |
|-------|-------|--------|-------|------------------|-------------------|
| H2O | aqueous | — | — | +1.2557 | +1.2557 |
| H2Glycine+ | aqueous | L1:+1 H:+2 | — | -67.9215 | -13.2989 |
| HGlycine | aqueous | L1:+1 H:+1 | — | -54.6226 | +0.0000 |
| Glycine | aqueous | L1:+1 | — | -0.0000 | +54.6226 |
| Ni2+ | aqueous | Ni$+2:+1 | — | -0.0000 | +0.0000 |
| [Ni(OH)]+ | aqueous | H:-1 Ni$+2:+1 | — | +59.3600 | +59.3600 |
| [Ni(OH)2] | aqueous | H:-2 Ni$+2:+1 | — | +108.4461 | +108.4461 |
| [Ni(OH)3]- | aqueous | H:-3 Ni$+2:+1 | — | +171.2308 | +171.2308 |
| [Ni4(OH)4]4+ | aqueous | H:-4 Ni$+2:+4 | — | +158.1031 | +158.1031 |
| [Ni(Glyc)]+ | aqueous | L1:+1 Ni$+2:+1 | — | -32.7622 | +21.8605 |
| [Ni(Glyc)2] | aqueous | L1:+2 Ni$+2:+1 | — | -60.3874 | +48.8578 |
| [Ni(Glyc)3]- | aqueous | L1:+3 Ni$+2:+1 | — | -80.4785 | +83.3894 |
| [Ni(OH)2](s) | solid | H:-2 Ni$+2:+1 | — | +73.0585 | +73.0585 |

## Speciation Analysis

```
=== Ni(s) (Ni$+0) speciation ===
[Ni$+0]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 71/71

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Ni2+ (Ni$+2) speciation ===
[Ni$+2]_total = 1.00e-03 M
T = 25.0 °C,  I = 0.1 M
Convergence: 71/71

Species peaks:
  Ni2+                peak 99.1% at pH 4.0
  [Ni(Glyc)]+         peak 52.0% at pH 6.4
  [Ni(Glyc)2]         peak 63.5% at pH 7.4
  [Ni(Glyc)3]-        peak 95.8% at pH 11.0

Dominant species by pH region:
  pH   4.0–  6.1  →  Ni2+
  pH   6.1–  6.8  →  [Ni(Glyc)]+
  pH   6.8–  8.0  →  [Ni(Glyc)2]
  pH   8.0– 11.0  →  [Ni(Glyc)3]-

Crossover pH values:
  Ni2+ ↔ [Ni(Glyc)]+  at pH ≈ 6.07  (each ~45%)
  Ni2+ ↔ [Ni(Glyc)2]  at pH ≈ 6.43  (each ~24%)
  Ni2+ ↔ [Ni(Glyc)3]-  at pH ≈ 6.95  (each ~6%)
  [Ni(Glyc)]+ ↔ [Ni(Glyc)2]  at pH ≈ 6.80  (each ~44%)
  [Ni(Glyc)]+ ↔ [Ni(Glyc)3]-  at pH ≈ 7.38  (each ~18%)
  [Ni(Glyc)2] ↔ [Ni(Glyc)3]-  at pH ≈ 7.98  (each ~48%)

=== Ni(+3) (Ni$+3) speciation ===
[Ni$+3]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 71/71

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Ni(+4) (Ni$+4) speciation ===
[Ni$+4]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 71/71

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Glycine (L1) speciation ===
[L1]_total = 1.00e-02 M

Species peaks:
  HGlycine            peak 99.1% at pH 4.7
  Glycine             peak 68.9% at pH 11.0
  [Ni(Glyc)]+         peak 5.2% at pH 6.4
  [Ni(Glyc)2]         peak 12.7% at pH 7.4
  [Ni(Glyc)3]-        peak 28.7% at pH 11.0

Dominant species by pH region:
  pH   4.0–  9.4  →  HGlycine
  pH   9.4– 11.0  →  Glycine

```
