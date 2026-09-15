# Speciation Calculation Report: Zn$+2 + Zn$+0 + Glycine

## System Parameters
- Temperature: 25.0 °C
- Ionic mode: fixed
- Target ionic strength: 0.1 M
- Calculated ionic strength range: 5.54387e-05 – 0.0037033 M
- Max inert ions: cation 0 M, anion 0 M
- pH range: 2.0 – 12.0
- Points: 101
- Converged: 101/101
- Redox mode: excluded

## Compiled Analytical Totals

| Constraint | Declared value (mol/L) | Meaning |
|------------|------------------------|---------|
| [Zn$+0]_total | 0 | redox-state subtotal |
| [Zn$+2]_total | 0.001 | redox-state subtotal |
| [ligand_5760]_total | 0.005 | component total |

## Components

| ID | Name | Total (mol/L) | Type |
|-----|------|--------------|------|
| Zn$+0 | Zn(s) | 0.00e+00 | metal |
| Zn$+2 | Zn2+ | 1.00e-03 | metal |
| L1 | Glycine | 5.00e-03 | ligand |

## Free-Energy Species Table

| Label | Phase | Stoich | log β | μ°_free (kJ/mol) | μ°_canon (kJ/mol) |
|-------|-------|--------|-------|------------------|-------------------|
| H2O | aqueous | — | — | +1.2557 | +1.2557 |
| H2Glycine+ | aqueous | L1:+1 H:+2 | — | -67.9215 | -13.2989 |
| HGlycine | aqueous | L1:+1 H:+1 | — | -54.6226 | +0.0000 |
| Glycine | aqueous | L1:+1 | — | -0.0000 | +54.6226 |
| Zn2+ | aqueous | Zn$+2:+1 | — | -0.0000 | +0.0000 |
| [Zn(OH)]+ | aqueous | H:-1 Zn$+2:+1 | — | +53.0815 | +53.0815 |
| [Zn(OH)2] | aqueous | H:-2 Zn$+2:+1 | — | +90.1815 | +90.1815 |
| [Zn(OH)3]- | aqueous | H:-3 Zn$+2:+1 | — | +160.3861 | +160.3861 |
| [Zn(OH)4]2- | aqueous | H:-4 Zn$+2:+1 | — | +231.1615 | +231.1615 |
| [Zn(Glyc)]+ | aqueous | L1:+1 Zn$+2:+1 | — | -28.3102 | +26.3125 |
| [Zn(Glyc)2] | aqueous | L1:+2 Zn$+2:+1 | — | -52.4537 | +56.7915 |
| [Zn(Glyc)3]- | aqueous | L1:+3 Zn$+2:+1 | — | -66.2092 | +97.6586 |
| [Zn(Glyc)(OH)] | aqueous | L1:+1 H:-1 Zn$+2:+1 | — | +22.4883 | +77.1109 |
| Zn(OH)2 (alpha) | solid | H:-2 Zn$+2:+1 | — | +61.2036 | +61.2036 |
| Zn | solid | Zn$+0:+1 | — | +0.0000 | +0.0000 |

## Precipitation

- pH 6.50: ZnO (inactive) (1.62e-04 M)

## Speciation Analysis

```
=== Zn(s) (Zn$+0) speciation ===
[Zn$+0]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 101/101

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Zn2+ (Zn$+2) speciation ===
[Zn$+2]_total = 1.00e-03 M
T = 25.0 °C,  I = 0.1 M
Convergence: 101/101

Species peaks:
  Zn2+                peak 100.0% at pH 2.0
  [Zn(Glyc)]+         peak 15.3% at pH 6.5

Dominant species by pH region:
  pH   2.0–  7.2  →  Zn2+
  pH   7.2– 12.0  →  [Zn(Glyc)]+

Crossover pH values:

=== Glycine (L1) speciation ===
[L1]_total = 5.00e-03 M

Species peaks:
  H2Glycine+          peak 68.1% at pH 2.0
  HGlycine            peak 99.6% at pH 5.1
  Glycine             peak 99.8% at pH 12.0

Dominant species by pH region:
  pH   2.0–  2.4  →  H2Glycine+
  pH   2.4–  9.4  →  HGlycine
  pH   9.4– 12.0  →  Glycine

```
