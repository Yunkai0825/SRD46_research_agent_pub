from __future__ import annotations

from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC2_free_energy_card_building.LC2_2_card_db_merger.db_pourbaix_atlas.atlas_data import (
    AtlasSpecies,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC2_free_energy_card_building.LC2_2_card_db_merger.db_pourbaix_atlas.atlas_loader import (
    _is_physical_aqueous_atlas_species,
    _ox_state_values,
    atlas_species_for_element,
)


def _species(
    oxidation_state: str,
    *,
    element: str = "Palladium",
    phase: str = "Solid",
    species: str = "Pd2H",
) -> AtlasSpecies:
    return AtlasSpecies(
        phase=phase,
        species=species,
        oxidation_state=oxidation_state,
        mu0_cal=0.0,
        name=species,
        element=element,
        source_file="test",
    )


def test_oxidation_state_parser_covers_corpus_spellings() -> None:
    assert _ox_state_values("-0.5") == [-0.5]
    assert _ox_state_values("+2.67") == [2.67]
    assert _ox_state_values("+III") == [3.0]
    assert _ox_state_values("-I") == [-1.0]
    assert _ox_state_values("+3/+4") == [3.0, 4.0]
    assert _ox_state_values("+8/3 (mixed)") == [8.0 / 3.0]


def test_element_qualified_state_uses_only_central_element() -> None:
    assert _ox_state_values(
        "+2 (Ba), -1 (O)", central_element="Barium",
    ) == [2.0]
    assert _ox_state_values(
        "-1 (H)", central_element="Barium",
    ) == []


def test_physical_filter_rejects_fractional_negative_metal_state() -> None:
    assert not _is_physical_aqueous_atlas_species(_species("-0.5"))
    assert not _is_physical_aqueous_atlas_species(_species("-I"))


def test_physical_filter_keeps_supported_nonnegative_state_spellings() -> None:
    assert _is_physical_aqueous_atlas_species(_species("+III"))
    assert _is_physical_aqueous_atlas_species(_species("+3/+4"))
    assert _is_physical_aqueous_atlas_species(_species("+8/3 (mixed)"))
    assert _is_physical_aqueous_atlas_species(_species(
        "+2 (Ba), -1 (O)",
        element="Barium",
        species="BaO2.H2O",
    ))
    # This cell describes hydrogen, not the central Ba state.
    assert _is_physical_aqueous_atlas_species(_species(
        "-1 (H)",
        element="Barium",
        species="BaH2",
    ))


def test_physical_only_public_api_filters_pd2h_fractional_state(tmp_path) -> None:
    csv_path = tmp_path / "atlas.csv"
    csv_path.write_text(
        "file,element,sub_element,phase,species,oxidation_state,"
        "mu0_cal,mu0_kJ,name\n"
        "13_Palladium.md,Palladium,Palladium,Solid,Pd2H,-0.5,"
        "1097,4.5898,Palladium alpha-hydride\n"
        "13_Palladium.md,Palladium,Palladium,Solid,Pd,0,"
        "0,0,Palladium metal\n"
        "13_Palladium.md,Palladium,Palladium,Dissolved,Pd(2+),+2,"
        "45500,190.372,Palladous ion\n",
        encoding="utf-8",
    )

    physical = {
        item.species
        for item in atlas_species_for_element("Pd", csv_path)
    }
    unfiltered = {
        item.species
        for item in atlas_species_for_element(
            "Pd", csv_path, physical_only=False,
        )
    }

    assert physical == {"Pd", "Pd(2+)"}
    assert unfiltered == {"Pd2H", "Pd", "Pd(2+)"}


def test_promethium_symbol_resolves_to_regenerated_csv_rows() -> None:
    by_symbol = atlas_species_for_element("Pm", physical_only=False)
    by_name = atlas_species_for_element("Promethium", physical_only=False)

    assert by_symbol
    assert {item.species for item in by_symbol} == {
        item.species for item in by_name
    }


def test_caesium_symbol_resolves_to_regenerated_csv_rows() -> None:
    by_symbol = atlas_species_for_element("Cs", physical_only=False)
    by_name = atlas_species_for_element("Caesium", physical_only=False)

    assert by_symbol
    assert {item.species for item in by_symbol} == {
        item.species for item in by_name
    }
