from __future__ import annotations

import logging
from pathlib import Path
import sys

import pytest


_THIS = Path(__file__).absolute()
_REPO_ROOT = _THIS.parents[6]
_ANALYSIS_ROOT = _THIS.parents[4]
_CALC_ROOT = _THIS.parents[3]
_CORE_ROOT = _ANALYSIS_ROOT / "NIST_SRD46_core_numcalc_pipeline"
_SOLVER_ROOT = _CORE_ROOT / "solvers_and_topology"
for _path in (
    _REPO_ROOT,
    _ANALYSIS_ROOT,
    _CALC_ROOT,
    _CORE_ROOT,
    _SOLVER_ROOT,
):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC2_free_energy_card_building.LC2_2_card_db_merger._md_card_merge_core.reference_alignment import (
    ElementReference,
    align_atlas_species,
    allocate_metal_oxidation_counts,
    compute_decomposition,
    parse_atlas_formula,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC2_free_energy_card_building.LC2_2_card_db_merger._md_card_merge_core.species_unifier import (
    build_unified_species,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC2_free_energy_card_building.LC2_2_card_db_merger.db_pourbaix_atlas.atlas_data import (
    AtlasSpecies,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC2_free_energy_card_building.LC2_2_card_db_merger.db_pourbaix_atlas.atlas_loader import (
    atlas_species_for_element,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC2_free_energy_card_building.LC2_2_card_db_merger.db_pourbaix_atlas.pourbaix_merge import (
    merge_card_hardcoded,
)
from card_management_helpers.free_energy_md_card_reader import (
    parse_free_energy_card_md,
)
from solvers_and_topology._input_solver_helper.built_system_from_dGreport import (
    LN10,
    R_kJ,
    build_from_free_energy_report,
)


VALENCE_TABLE = [
    {
        "element": "Fe",
        "internal_id": "Fe$+2",
        "name": "Fe2+",
        "charge": 2,
        "is_reference": True,
    },
    {
        "element": "Fe",
        "internal_id": "Fe$+3",
        "name": "Fe3+",
        "charge": 3,
        "is_reference": False,
    },
]

FE_REFERENCE = ElementReference(
    element_symbol="Fe",
    element_name="Iron",
    reference_species="Fe2+",
    oxidation_state=2,
    mu0_abs_kJ=-84.9352,
    offset_kJ=84.9352,
)


def _aligned_fe3o4(oxidation_state: str = "+2, +3"):
    source = AtlasSpecies(
        phase="Solid",
        species="Fe3O4 (anh.)",
        oxidation_state=oxidation_state,
        mu0_cal=-242_400.0,
        name="Magnetite, black, cub.",
        element="Iron",
        source_file="12_Iron",
    )
    return align_atlas_species([source], FE_REFERENCE)[0]


def test_fe3o4_mixed_valence_allocation_is_one_fe_ii_two_fe_iii() -> None:
    assert allocate_metal_oxidation_counts("+2, +3", 3, -8, 0) == {
        2: 1,
        3: 2,
    }


def test_fe3o4_keeps_nonempty_card_stoichiometry() -> None:
    unified = build_unified_species(
        {"Fe": [_aligned_fe3o4()]},
        card_aligned=[],
        valence_table=VALENCE_TABLE,
        metal_info={},
        references={"Fe": FE_REFERENCE},
    )

    assert len(unified) == 1
    assert unified[0].raw_stoich == {
        "Fe$+2": 1,
        "Fe$+3": 2,
        "H": -8,
    }
    assert unified[0].core_stoich


def test_fractional_average_oxidation_state_uses_charge_balance() -> None:
    unified = build_unified_species(
        {"Fe": [_aligned_fe3o4("+2.67")]},
        card_aligned=[],
        valence_table=VALENCE_TABLE,
        metal_info={},
        references={"Fe": FE_REFERENCE},
    )

    # +2.67 is the Atlas' two-decimal spelling of 8/3.  Formula charge
    # balance makes the adjacent integral-state allocation unique.
    assert unified[0].raw_stoich == {
        "Fe$+2": 1,
        "Fe$+3": 2,
        "H": -8,
    }
    assert unified[0].extra["n_e"] == "-2"


def test_fractional_average_must_match_formula_charge_balance() -> None:
    assert allocate_metal_oxidation_counts("+2.60", 3, -8, 0) is None


def test_ascii_dot_hydrate_multiplier_is_applied() -> None:
    atoms, charge = parse_atlas_formula("Ni3O4.2H2O", "+2.67")

    assert atoms == {"Ni": 3, "O": 6, "H": 4}
    assert charge == 0
    assert compute_decomposition(atoms, charge, "Ni", 2) == (3, -8, -2, 6)


def test_ni3o4_hydrate_keeps_water_and_mixed_valence_end_to_end() -> None:
    reference = ElementReference(
        element_symbol="Ni",
        element_name="Nickel",
        reference_species="Ni2+",
        oxidation_state=2,
        mu0_abs_kJ=-45.6056,
        offset_kJ=45.6056,
    )
    source = AtlasSpecies(
        phase="Solid",
        species="Ni3O4.2H2O",
        oxidation_state="+2.67",
        mu0_cal=-283_530.0,
        name="Hydrated nickel oxide",
        element="Nickel",
        source_file="12_Nickel",
    )
    aligned = align_atlas_species([source], reference)[0]
    valence_table = [
        {
            "element": "Ni",
            "internal_id": "Ni$+2",
            "name": "Ni2+",
            "charge": 2,
            "is_reference": True,
        },
        {
            "element": "Ni",
            "internal_id": "Ni$+3",
            "name": "Ni3+",
            "charge": 3,
            "is_reference": False,
        },
    ]
    unified = build_unified_species(
        {"Ni": [aligned]},
        card_aligned=[],
        valence_table=valence_table,
        metal_info={},
        references={"Ni": reference},
    )

    assert (aligned.n_H2O, aligned.H_net, aligned.n_electrons) == (6, -8, -2)
    assert unified[0].raw_stoich == {
        "Ni$+2": 1,
        "Ni$+3": 2,
        "H": -8,
    }


def test_middle_dot_hydrate_multiplier_is_applied() -> None:
    atoms, charge = parse_atlas_formula("Ba(OH)2 · 8H2O", "+2")

    assert atoms == {"Ba": 1, "O": 10, "H": 18}
    assert charge == 0


def test_name_only_hydrate_warns_and_keeps_written_formula(caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="RefAlignment"):
        atoms, charge = parse_atlas_formula("Am2O3 (hydr.)", "+3")

    assert atoms == {"Am": 2, "O": 3}
    assert charge == 0
    assert "without an explicit numeric hydrate" in caplog.text


def test_symbolic_hydrate_warns_and_is_not_assumed_to_be_one(caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="RefAlignment"):
        atoms, charge = parse_atlas_formula("Cr(OH)3.nH2O", "+3")

    assert atoms == {"Cr": 1, "O": 3, "H": 3}
    assert charge == 0
    assert "indeterminate hydrate coefficient" in caplog.text


def test_attached_anhydrous_suffix_does_not_hide_charge() -> None:
    atoms, charge = parse_atlas_formula("IO4(-)(anh.)", "+7")

    assert atoms == {"I": 1, "O": 4}
    assert charge == -1


def test_roman_oxidation_state_supports_au_iii() -> None:
    atoms, charge = parse_atlas_formula("Au(3+)", "+III")

    assert atoms == {"Au": 1}
    assert charge == 3
    assert allocate_metal_oxidation_counts(
        "+III",
        1,
        0,
        3,
        central_element="Au",
        available_states=[1, 3],
    ) == {3: 1}


def test_signed_slash_mixed_states_use_charge_balance() -> None:
    assert allocate_metal_oxidation_counts(
        "+3/+4",
        4,
        -14,
        0,
        central_element="Bi",
        available_states=[3, 4, 5],
    ) == {3: 2, 4: 2}


def test_fractional_average_uses_available_pb_ii_pb_iv_states() -> None:
    assert allocate_metal_oxidation_counts(
        "+2.67",
        3,
        -8,
        0,
        central_element="Pb",
        available_states=[2, 4],
    ) == {2: 2, 4: 1}


def test_rational_mixed_state_is_validated_against_formula() -> None:
    assert allocate_metal_oxidation_counts(
        "+16/3 (mixed)",
        3,
        -16,
        0,
        central_element="U",
        available_states=[4, 6],
    ) == {4: 1, 6: 2}
    assert allocate_metal_oxidation_counts(
        "+8/3 (mixed)",
        3,
        -16,
        0,
        central_element="U",
        available_states=[4, 6],
    ) is None


def test_structured_oxidation_state_selects_central_element_only() -> None:
    assert allocate_metal_oxidation_counts(
        "+2 (Ba), -1 (O)",
        1,
        -4,
        0,
        central_element="Ba",
        available_states=[0, 2],
    ) == {2: 1}
    assert allocate_metal_oxidation_counts(
        "-1 (H)",
        1,
        2,
        0,
        central_element="Ba",
        available_states=[0, 2],
    ) is None


def test_integral_state_absent_from_valence_table_is_rejected() -> None:
    assert allocate_metal_oxidation_counts(
        "+3",
        1,
        0,
        3,
        central_element="M",
        available_states=[2, 4],
    ) is None


def test_ignored_formula_text_emits_warning(caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="RefAlignment"):
        atoms, charge = parse_atlas_formula("Fe2O3??", "+3")

    assert atoms == {"Fe": 2, "O": 3}
    assert charge == 0
    assert "contains ignored text after atom parsing" in caplog.text


def test_refreshed_iron_csv_contains_correct_atlas_solids() -> None:
    iron = {species.species: species for species in atlas_species_for_element("Fe")}

    assert iron["Fe(OH)2 (hydr.)"].mu0_cal == -115_570.0
    assert iron["Fe3O4 (anh.)"].mu0_cal == -242_400.0
    assert iron["Fe2O3 (anh.)"].mu0_cal == -177_100.0


def _single_valence_ni_card() -> str:
    """Minimal LC2_1-style card containing Ni(II), and no other Ni state."""
    return """# Free Energy Analysis Card

**System**: Ni / water
**Metals**: [Ni]2+
**Ligands**:

## 1. Notation Conventions

| Symbol | Meaning |
|--------|---------|
| M0 | Always H+ |
| M1 | Metal component: [Ni]2+ |
| L0 | Always OH- |

## 2. Components

### 2.1 Solvent

#### S0: Water (db_id: solvent_1)

| property | value |
|----------|-------|
| name | Water |
| formula | H2O |
| self_dissociation | true |
| dissociation_reaction | H2O <=> H+ + OH- |
| pK | 14.00 |
| K_log10 | -14.00 |

| internal_id | name | charge | stoich_coeff | db_id |
|-------------|------|--------|-------------|-------|
| M0 | [H]+ | +1 | +1 | metal_68 |
| L0 | [OH]- | -1 | +1 | ligand_10076 |

### 2.2 Metals

| internal_id | name | charge | total_M | db_source | db_id |
|-------------|------|--------|---------|-----------|-------|
| M1 | [Ni]2+ | +2 | 0.001 | NIST SRD-46 | metal_112 |

### 2.3 Ligands

(No ligand components.)

### 2.4 Metal Valence Alignment

| element | internal_id | name | charge | is_reference | n_valences |
|---------|-------------|------|--------|--------------|------------|
| Ni | M1 | [Ni]2+ | +2 | true | 1 |

## 3. Canonical Reference States

### 3.1 Component Reference Declarations

| component_id | name | type | reference_form | mu0_ref_kJ | rule | element | charge | is_valence_ref |
|-------------|------|------|----------------|------------|------|---------|--------|----------------|
| M0 | [H]+ | proton | [H]+(aq) | +0.0000 | R2 | *** | +1 | *** |
| M1 | [Ni]2+ | metal | [Ni]2+(aq) | +0.0000 | R1 | Ni | +2 | true |
| L0 | [OH]- | hydroxide | [OH]-(aq) from Kw | +79.9078 | R3 | *** | -1 | *** |

## 4. Settings

### 4.1 Common Settings

| parameter | value | unit |
|-----------|-------|------|
| ionic_strength | 0.1 | mol/L |
| ionic_strength_mode | fixed | - |
| Kw_log10 | -14.00 | - |
| 2.303RT | 5.7077 | kJ/mol |
| RT | 2.478819 | kJ/mol |

## 5. Standard Chemical Potentials

### 5.1 Aqueous Species

| species_id | label | charge | phase | log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich | calc_source | include | additional_notes |
|------------|-------|--------|-------|----------|-------------|--------------|---------------|--------|-------------|---------|------------------|
| [M1].[z+2] | [Ni]2+ | +2 | aqueous | +0.0000 | +0.0000 | +0.0000 | +0.0000 | [M1]:+1 | R1 | true | *** |

### 5.2 Dissolution / Solid Species

(No dissolution species in the LC2_1 input.)

### 5.3 Gas Species

(No gas species in this system.)
"""


def _ni_reference_offsets(card_text: str) -> dict[str, float]:
    offsets: dict[str, float] = {}
    for line in card_text.splitlines():
        if not line.startswith("| Ni$+"):
            continue
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if len(cells) >= 9 and cells[2] == "metal":
            offsets[cells[0]] = float(cells[4])
    return offsets


def test_single_valence_ni_card_roundtrips_to_redox_solver_system() -> None:
    merged, stats = merge_card_hardcoded(
        _single_valence_ni_card(),
        "Ni-water regression",
        elements=["Ni"],
    )
    assert stats["status"] == "ok"

    report = parse_free_energy_card_md(merged)
    report.include_redox = True
    report.include_solids = True
    report.activity_model = "ideal"

    assert report.metal_ids == ["Ni$+2", "Ni$+0", "Ni$+3", "Ni$+4"]
    assert {mid: report.total_metals[mid] for mid in report.metal_ids[1:]} == {
        "Ni$+0": 0.0,
        "Ni$+3": 0.0,
        "Ni$+4": 0.0,
    }
    assert _ni_reference_offsets(merged) == pytest.approx({
        "Ni$+2": 0.0,
        "Ni$+0": 45.6056,
        "Ni$+3": 166.5232,
        "Ni$+4": 304.8462,
    })

    [ni_group] = report.valence_groups
    assert ni_group.element == "Ni"
    assert ni_group.reference_id == "Ni$+2"
    assert sum(entry.is_reference for entry in ni_group.entries) == 1

    species_by_label = {species.label: species for species in report.species}
    expected_stoich = {
        "Ni3O4.2H2O": {"Ni$+2": 1, "Ni$+3": 2, "H": -8},
        "Ni2O3.H2O": {"Ni$+3": 2, "H": -6},
        "NiO2.2H2O": {"Ni$+4": 1, "H": -4},
    }
    for label, stoich in expected_stoich.items():
        assert species_by_label[label].stoich == stoich

    built = build_from_free_energy_report(report)
    diss_index = {label: i for i, label in enumerate(built.diss_labels)}
    solver_factor = LN10 * R_kJ * report.temperature_K
    for label in expected_stoich:
        species = species_by_label[label]
        idx = diss_index[label]
        assert built.diss_s[idx] == pytest.approx(-2.0)
        assert species.log_beta == pytest.approx(
            -species.mu0_canonical / report.factor,
            abs=1e-4,
        )
        assert built.log_K_diss_thermo[idx] == pytest.approx(
            species.log_beta
            - (species.mu_aligned - species.mu0_canonical) / solver_factor
        )
        assert built.diss_logK[idx] == pytest.approx(
            built.log_K_diss_thermo[idx]
        )
