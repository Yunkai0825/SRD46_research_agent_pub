# Speciation Calculation Report: Cu$+1 + Cu$+0 + Cu$+2 + Glycine

## System Parameters
- Temperature: 25.0 °C
- Ionic mode: fixed
- Target ionic strength: 0.1 M
- Calculated ionic strength range: 1.4337e-05 – 5.58926e-05 M
- Max inert ions: cation 0 M, anion 0 M
- pH range: 6.5 – 7.5
- Points: 21
- Converged: 21/21
- Redox mode: excluded

## Compiled Analytical Totals

| Constraint | Declared value (mol/L) | Meaning |
|------------|------------------------|---------|
| [Cu$+0]_total | 0 | redox-state subtotal |
| [Cu$+1]_total | 0 | redox-state subtotal |
| [Cu$+2]_total | 0.001 | redox-state subtotal |
| [ligand_5760]_total | 0.01 | component total |

## Components

| ID | Name | Total (mol/L) | Type |
|-----|------|--------------|------|
| Cu$+0 | Cu(s) | 0.00e+00 | metal |
| Cu$+1 | Cu+ | 0.00e+00 | metal |
| Cu$+2 | Cu2+ | 1.00e-03 | metal |
| L1 | Glycine | 1.00e-02 | ligand |

## Free-Energy Species Table

| Label | Phase | Stoich | log β | μ°_free (kJ/mol) | μ°_canon (kJ/mol) |
|-------|-------|--------|-------|------------------|-------------------|
| H2O | aqueous | — | — | +1.2557 | +1.2557 |
| H2Glycine+ | aqueous | L1:+1 H:+2 | — | -67.9215 | -13.2989 |
| HGlycine | aqueous | L1:+1 H:+1 | — | -54.6226 | +0.0000 |
| Glycine | aqueous | L1:+1 | — | -0.0000 | +54.6226 |
| Cu+ | aqueous | Cu$+1:+1 | — | -0.0000 | +0.0000 |
| [Cu(Glyc)2]- | aqueous | L1:+2 Cu$+1:+1 | — | -57.6477 | +51.5975 |
| Cu2+ | aqueous | Cu$+2:+1 | — | -0.0000 | +0.0000 |
| [Cu(OH)]+ | aqueous | Cu$+2:+1 H:-1 | — | +45.0908 | +45.0908 |
| [Cu2(OH)2]2+ | aqueous | Cu$+2:+2 H:-2 | — | +63.9261 | +63.9261 |
| [Cu(OH)2] | aqueous | Cu$+2:+1 H:-2 | — | +92.4646 | +92.4646 |
| HCuO2- | aqueous | Cu$+2:+1 H:-3 | — | +152.4231 | +152.4231 |
| [Cu3(OH)4]2+ | aqueous | Cu$+2:+3 H:-4 | — | +128.4231 | +128.4231 |
| CuO22- | aqueous | Cu$+2:+1 H:-4 | — | +227.4004 | +227.4004 |
| [Cu(Glyc)]+ | aqueous | L1:+1 Cu$+2:+1 | — | -46.7460 | +7.8766 |
| [Cu(Glyc)2] | aqueous | L1:+2 Cu$+2:+1 | — | -86.1861 | +23.0591 |
| [(Cu2O)0.5](s) | solid | Cu$+1:+1 H:-1 | — | -3.9954 | -3.9954 |
| CuO(s) | solid | Cu$+2:+1 H:-2 | — | +43.6638 | +43.6638 |
| [Cu(OH)2](s) | solid | Cu$+2:+1 H:-2 | — | +49.5428 | +49.5428 |
| Cu | solid | Cu$+0:+1 | — | +0.0000 | +0.0000 |

## Speciation Analysis

```
=== Cu(s) (Cu$+0) speciation ===
[Cu$+0]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 21/21

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Cu+ (Cu$+1) speciation ===
[Cu$+1]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 21/21

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Cu2+ (Cu$+2) speciation ===
[Cu$+2]_total = 1.00e-03 M
T = 25.0 °C,  I = 0.1 M
Convergence: 21/21

Species peaks:
  [Cu(Glyc)2]         peak 99.8% at pH 7.5

Dominant species by pH region:
  pH   6.5–  7.5  →  [Cu(Glyc)2]

Crossover pH values:

=== Glycine (L1) speciation ===
[L1]_total = 1.00e-02 M

Species peaks:
  HGlycine            peak 80.1% at pH 6.5
  [Cu(Glyc)2]         peak 20.0% at pH 7.5

Dominant species by pH region:
  pH   6.5–  7.5  →  HGlycine

```
