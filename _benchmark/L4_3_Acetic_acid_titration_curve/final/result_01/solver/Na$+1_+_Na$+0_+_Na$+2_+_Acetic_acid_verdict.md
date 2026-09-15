# Speciation Calculation Report: Na$+1 + Na$+0 + Na$+2 + Acetic acid

## System Parameters
- Temperature: 25.0 °C
- Ionic mode: fixed
- Target ionic strength: 0.001 M
- Calculated ionic strength range: 1.4742e-05 – 0.005 M
- Max inert ions: cation 0 M, anion 0 M
- pH range: 2.0 – 12.0
- Points: 101
- Converged: 101/101
- Redox mode: excluded

## Compiled Analytical Totals

| Constraint | Declared value (mol/L) | Meaning |
|------------|------------------------|---------|
| [Na$+0]_total | 0 | redox-state subtotal |
| [Na$+1]_total | 0 | redox-state subtotal |
| [Na$+2]_total | 0 | redox-state subtotal |
| [ligand_8465]_total | 0.01 | component total |

## Components

| ID | Name | Total (mol/L) | Type |
|-----|------|--------------|------|
| Na$+0 | Na(s) | 0.00e+00 | metal |
| Na$+1 | Na+ | 0.00e+00 | metal |
| Na$+2 | Na(+2) | 0.00e+00 | metal |
| L1 | Acetic acid | 1.00e-02 | ligand |

## Free-Energy Species Table

| Label | Phase | Stoich | log β | μ°_free (kJ/mol) | μ°_canon (kJ/mol) |
|-------|-------|--------|-------|------------------|-------------------|
| H2O | aqueous | — | — | +1.2557 | +1.2557 |
| HAcetic acid | aqueous | L1:+1 H:+1 | — | -26.0271 | +0.0000 |
| Acetic acid | aqueous | L1:+1 | — | -0.0000 | +26.0271 |
| Na+ | aqueous | Na$+1:+1 | — | -0.0000 | +0.0000 |
| NaOH | solid | H:-1 Na$+1:+1 | — | +122.0849 | +122.0849 |

## Speciation Analysis

```
=== Na(s) (Na$+0) speciation ===
[Na$+0]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.001 M
Convergence: 101/101

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Na+ (Na$+1) speciation ===
[Na$+1]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.001 M
Convergence: 101/101

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Na(+2) (Na$+2) speciation ===
[Na$+2]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.001 M
Convergence: 101/101

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Acetic acid (L1) speciation ===
[L1]_total = 1.00e-02 M

Species peaks:
  HAcetic acid        peak 99.7% at pH 2.0
  Acetic acid         peak 100.0% at pH 12.0

Dominant species by pH region:
  pH   2.0–  4.6  →  HAcetic acid
  pH   4.6– 12.0  →  Acetic acid

```
