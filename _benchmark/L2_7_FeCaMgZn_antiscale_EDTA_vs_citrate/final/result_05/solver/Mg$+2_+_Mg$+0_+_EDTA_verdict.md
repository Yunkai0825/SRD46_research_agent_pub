# Speciation Calculation Report: Mg$+2 + Mg$+0 + EDTA

## System Parameters
- Temperature: 25.0 °C
- Ionic mode: fixed
- Target ionic strength: 0.1 M
- Calculated ionic strength range: 0.00459462 – 0.0179978 M
- Max inert ions: cation 0 M, anion 0 M
- pH range: 2.0 – 12.0
- Points: 101
- Converged: 101/101
- Redox mode: excluded

## Compiled Analytical Totals

| Constraint | Declared value (mol/L) | Meaning |
|------------|------------------------|---------|
| [Mg$+0]_total | 0 | redox-state subtotal |
| [Mg$+2]_total | 0.001 | redox-state subtotal |
| [ligand_6277]_total | 0.003 | component total |

## Components

| ID | Name | Total (mol/L) | Type |
|-----|------|--------------|------|
| Mg$+0 | Mg(s) | 0.00e+00 | metal |
| Mg$+2 | Mg2+ | 1.00e-03 | metal |
| L1 | EDTA | 3.00e-03 | ligand |

## Free-Energy Species Table

| Label | Phase | Stoich | log β | μ°_free (kJ/mol) | μ°_canon (kJ/mol) |
|-------|-------|--------|-------|------------------|-------------------|
| H2O | aqueous | — | — | +1.2557 | +1.2557 |
| H6EDTA2+ | aqueous | L1:+1 H:+6 | — | -107.5900 | +7.9908 |
| H5EDTA+ | aqueous | L1:+1 H:+5 | — | -107.5900 | +7.9908 |
| H4EDTA | aqueous | L1:+1 H:+4 | — | -115.5808 | +0.0000 |
| H3EDTA- | aqueous | L1:+1 H:+3 | — | -104.0512 | +11.5295 |
| H2EDTA2- | aqueous | L1:+1 H:+2 | — | -89.6678 | +25.9129 |
| HEDTA3- | aqueous | L1:+1 H:+1 | — | -54.3372 | +61.2435 |
| EDTA | aqueous | L1:+1 | — | -0.0000 | +115.5808 |
| Mg2+ | aqueous | Mg$+2:+1 | — | -0.0000 | +0.0000 |
| [Mg(OH)]+ | aqueous | Mg$+2:+1 H:-1 | — | +65.0677 | +65.0677 |
| [Mg2(OH)]3+ | aqueous | Mg$+2:+2 H:-1 | — | +66.7800 | +66.7800 |
| [Mg4(OH)4]4+ | aqueous | Mg$+2:+4 H:-4 | — | +227.7369 | +227.7369 |
| [Mg(EDTA)H]- | aqueous | Mg$+2:+1 L1:+1 H:+1 | — | -73.0014 | +42.5794 |
| [Mg(EDTA)]2- | aqueous | Mg$+2:+1 L1:+1 | — | -50.1706 | +65.4101 |
| [Mg(OH)2(s,brucite)] | solid | Mg$+2:+1 H:-2 | — | +96.2317 | +96.2317 |

## Speciation Analysis

```
=== Mg(s) (Mg$+0) speciation ===
[Mg$+0]_total = 0.00e+00 M
T = 25.0 °C,  I = 0.1 M
Convergence: 101/101

Species peaks:

Dominant species by pH region:

Crossover pH values:

=== Mg2+ (Mg$+2) speciation ===
[Mg$+2]_total = 1.00e-03 M
T = 25.0 °C,  I = 0.1 M
Convergence: 101/101

Species peaks:
  Mg2+                peak 100.0% at pH 2.0
  [Mg(EDTA)]2-        peak 100.0% at pH 10.2

Dominant species by pH region:
  pH   2.0–  5.0  →  Mg2+
  pH   5.0– 12.0  →  [Mg(EDTA)]2-

Crossover pH values:
  Mg2+ ↔ [Mg(EDTA)]2-  at pH ≈ 4.91  (each ~49%)

=== EDTA (L1) speciation ===
[L1]_total = 3.00e-03 M

Species peaks:
  H4EDTA              peak 26.1% at pH 2.0
  H3EDTA-             peak 40.8% at pH 2.0
  H2EDTA2-            peak 95.9% at pH 3.8
  HEDTA3-             peak 63.2% at pH 7.1
  EDTA                peak 66.6% at pH 12.0
  [Mg(EDTA)]2-        peak 33.3% at pH 10.2

Dominant species by pH region:
  pH   2.0–  2.1  →  H3EDTA-
  pH   2.1–  5.6  →  H2EDTA2-
  pH   5.6–  8.7  →  HEDTA3-
  pH   8.7– 12.0  →  EDTA

```
