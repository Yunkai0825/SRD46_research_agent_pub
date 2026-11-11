# solution_activity_models/ — Architecture

> **Davies equation activity coefficient model.**

## Overview

This package provides ionic activity coefficient calculations via the Davies equation,
shared by both the free-energy and fallback solvers. It converts thermodynamic logK
values to apparent (activity-corrected) logK values at a given ionic strength, and
estimates ionic strength from solved concentration profiles.

## Directory Layout

```
solution_activity_models/
├── solution_models_activity_coeff.py    ← all activity functions
└── __init__.py
```

---

## Module: `solution_models_activity_coeff.py`

### Public Functions

| Function | Signature | Returns | Purpose |
|---|---|---|---|
| `davies_log_gamma` | `(charge: int, ionic_strength: float, A: float = 0.5085) → float` | `float` | Davies equation: log₁₀(γ) for a single ion. Returns 0 for charge=0 or I≤0. Valid for I ≲ 0.5 M. |
| `compute_apparent_logK` | `(eq, species, ionic_strength, metal_ids, ligand_ids) → float` | `float` | Activity-corrected logK for one equilibrium: `logK_app = logK_thermo − Σ(ν_products × logγ_products) + Σ(ν_reactants × logγ_reactants)` |
| `compute_all_apparent_logK` | `(equilibria, species, ionic_strength, metal_ids, ligand_ids) → Dict[str, float]` | `Dict` | Batch version — `{eq.id: apparent_logK}` for all equilibria |
| `describe_ionic_state` | `(conc: Dict[str,float], species: Dict[str,Species]) → Dict[str,float]` | `Dict` | Estimate ionic strength from solved concentrations; balance net charge with monovalent inert ions |

### Davies Equation

$$\log_{10} \gamma_i = -A z_i^2 \left( \frac{\sqrt{I}}{1 + \sqrt{I}} - 0.3 I \right)$$

where:
- $A = 0.5085$ (water at 25 °C)
- $z_i$ = ion charge
- $I$ = ionic strength (mol/L)

### Apparent logK Correction

For a formation reaction `Σ nᵢ Compᵢ ⇌ Product`:

$$\log K_{app} = \log K_{thermo} + \log \gamma_{product} - \sum_i n_i \log \gamma_i$$

### Ionic State Estimation

`describe_ionic_state` returns:

| Key | Description |
|---|---|
| `ionic_strength` | $I = \frac{1}{2} \sum_i c_i z_i^2$ |
| `charge_imbalance` | Net charge from all species |
| `inert_cation_conc` | Hypothetical monovalent cation to balance negative charge |
| `inert_anion_conc` | Hypothetical monovalent anion to balance positive charge |

---

## Dependencies

| Import | Source |
|---|---|
| `Species`, `Equilibrium` | `obsolete_fix_import_within)_NIST_SRD46_core_calc_tools.speciation_dataclasses` |
