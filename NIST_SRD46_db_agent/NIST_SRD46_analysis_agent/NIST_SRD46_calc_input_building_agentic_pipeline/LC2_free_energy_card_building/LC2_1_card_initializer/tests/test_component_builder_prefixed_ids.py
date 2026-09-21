from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_PIPELINE_ROOT = Path(__file__).resolve().parents[3]
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from LC2_free_energy_card_building.LC2_1_card_initializer.ref_eq_SRD46_json_cards_builder.json_cards_builder_helpers import component_builder

_db_hol_series = component_builder._db_hol_series


def test_db_hol_series_uses_validated_numeric_id_with_prefixed_search_row() -> None:
    row = {
        "ligand_id": "ligand_10103",
        "pka_brackets": [
            {"HxL_form": "L", "is_estimated": 0},
            {"HxL_form": "HL", "is_estimated": 0},
        ],
    }

    assert _db_hol_series(row, ligand_id=10103) == ["HL", "L"]


def test_db_hol_series_keeps_numeric_id_in_validation_context() -> None:
    row = {
        "ligand_id": "ligand_10103",
        "pka_brackets": [{"HxL_form": "HL"}],
    }

    with pytest.raises(ValueError, match="ligand_10103 pKa bracket"):
        _db_hol_series(row, ligand_id=10103)


def test_ligand_component_accepts_prefixed_public_search_id(monkeypatch) -> None:
    row = {
        "ligand_id": "ligand_10103",
        "ligand_name": "Ammonia",
        "ligand_HxL_definition": "HL",
        "pka_brackets": [
            {"HxL_form": "L", "is_estimated": 0},
            {"HxL_form": "HL", "is_estimated": 0},
        ],
    }
    monkeypatch.setattr(
        component_builder,
        "_ligand_charge_from_brackets",
        lambda ligand_id, **_kwargs: 0,
    )

    component = component_builder._build_ligand_component(
        ligand_id=10103,
        ligand_row=row,
        spec_id="L1",
        total="Not defined",
    )

    assert component["reference"]["source_database_ID"] == "ligand_10103"
    assert component["reference"]["canonical_HOL_series"] == ["HL", "L"]


def test_chloride_uses_explicit_free_ligand_reference_from_srd46(
    tmp_path,
) -> None:
    ids_path = tmp_path / "chloride_ids.json"
    ids_path.write_text(
        json.dumps({
            "metals": [{"metal_id": 68}],
            "ligands": [{"ligand_id": 10163}],
        }),
        encoding="utf-8",
    )

    payload = component_builder.build_components_from_ids_json(
        ids_json_path=ids_path,
    )
    chloride = payload["components"]["Chloride ion"]

    assert chloride["HOL"] == "L"
    assert chloride["ligand_canonical_HOL"] == {"H": 0, "O": 0, "L": 1}
    assert chloride["charge"] == -1
    assert chloride["reference"]["figure_definition"] == "L/-"
    assert chloride["reference"]["canonical_HOL_series"] == ["L"]


@pytest.mark.parametrize(
    "definition",
    [None, "***", "HL", "H3L"],
)
def test_missing_or_nonfree_figure_definition_remains_fatal(
    definition,
) -> None:
    row = {
        "ligand_name": "Unresolved ligand",
        "ligand_HxL_definition": None,
        "ligand_figure_definition": definition,
        "pka_brackets": [],
    }

    with pytest.raises(ValueError, match="no explicit canonical"):
        component_builder._build_ligand_component(
            ligand_id=99999,
            ligand_row=row,
            spec_id="L1",
            total="Not defined",
        )


def test_invalid_hxl_placeholder_remains_fatal() -> None:
    row = {
        "ligand_name": "Unresolved ligand",
        "ligand_HxL_definition": "***",
        "ligand_figure_definition": "***",
        "pka_brackets": [],
    }

    with pytest.raises(ValueError, match="declaration .* is invalid"):
        component_builder._build_ligand_component(
            ligand_id=99999,
            ligand_row=row,
            spec_id="L1",
            total="Not defined",
        )


@pytest.mark.parametrize("ligand_id", [10103, 5760, 9058])
def test_public_search_rows_build_without_legacy_cache(tmp_path, ligand_id) -> None:
    ids_path = tmp_path / f"ligand_{ligand_id}_ids.json"
    ids_path.write_text(
        json.dumps({
            "metals": [{"metal_id": 68}],
            "ligands": [{"ligand_id": ligand_id}],
        }),
        encoding="utf-8",
    )

    payload = component_builder.build_components_from_ids_json(
        ids_json_path=ids_path,
    )
    ligand_components = [
        component
        for name, component in payload["components"].items()
        if name not in {"H+", "OH-"}
    ]

    assert len(ligand_components) == 1
    assert (
        ligand_components[0]["reference"]["source_database_ID"]
        == f"ligand_{ligand_id}"
    )
