from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest


_PIPELINE_ROOT = Path(__file__).resolve().parents[3]
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from LC2_free_energy_card_building.LC2_1_card_initializer.ref_eq_SRD46_json_cards_builder.json_cards_builder_helpers import (  # noqa: E402
    component_builder,
)


pytestmark = pytest.mark.skipif(
    component_builder.Chem is None or component_builder.MolToInchi is None,
    reason="RDKit is required for free-ligand-state validation",
)


def _contract(
    *,
    ligand_id: int = 11422,
    smiles: str = "CN(C)C=O",
    charge: int = 0,
) -> dict[str, object]:
    molecule = component_builder.Chem.MolFromSmiles(smiles)
    assert molecule is not None
    canonical_smiles = component_builder.Chem.MolToSmiles(molecule)
    payload: dict[str, object] = {
        "canonical_HOL": "L",
        "charge": charge,
        "reference_state_classification": "neutral_nonprotic_free_ligand/v1",
        "provenance": {
            "kind": "PubChem",
            "source_database_ID": f"ligand_{ligand_id}",
            "compound_id": 6228,
            "query_name": "N,N-Dimethylformamide (DMF)",
            "resolved_iupac_name": "N,N-dimethylformamide",
            "canonical_smiles": canonical_smiles,
            "inchi": component_builder.MolToInchi(molecule),
            "source_payload_sha256": "a" * 64,
            "identity_binding": (
                "unique PubChem name result bound to exact SRD-46 ligand ID"
            ),
        },
        "derivation": {
            "rule": "pubchem_rdkit_neutral_nonprotic_free_ligand/v1",
            "formal_charge_method": "RDKit Chem.GetFormalCharge",
            "nonprotic_check": "no non-carbon heteroatom bears hydrogen",
        },
    }
    payload["receipt_sha256"] = hashlib.sha256(json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")).hexdigest()
    return payload


def _unresolved_row() -> dict[str, object]:
    return {
        "ligand_id": "ligand_11422",
        "ligand_name": "N,N-Dimethylformamide (DMF)",
        "ligand_HxL_definition": None,
        "ligand_figure_definition": "***",
        "pka_brackets": [],
        "smiles": None,
        "inchi": None,
    }


def test_valid_dmf_contract_builds_solver_component() -> None:
    contract = _contract()

    component = component_builder._build_ligand_component(
        ligand_id=11422,
        ligand_row=_unresolved_row(),
        spec_id="L1",
        total="Not defined",
        free_ligand_state_contract=contract,
    )

    assert component["HOL"] == "L"
    assert component["charge"] == 0
    assert component["ligand_canonical_HOL"] == {"H": 0, "O": 0, "L": 1}
    assert component["reference"]["source_database_ID"] == "ligand_11422"
    assert component["reference"]["catalog_free_ligand_state"] == contract


def test_contract_is_bound_to_exact_srd46_ligand_id() -> None:
    with pytest.raises(ValueError, match="bound to a different SRD-46 ligand ID"):
        component_builder._validate_free_ligand_state_contract(
            ligand_id=11423,
            contract=_contract(ligand_id=11422),
        )


def test_tampered_contract_receipt_is_rejected_before_use() -> None:
    contract = _contract()
    contract["charge"] = 1

    with pytest.raises(ValueError, match="receipt does not verify"):
        component_builder._build_ligand_component(
            ligand_id=11422,
            ligand_row=_unresolved_row(),
            spec_id="L1",
            total="Not defined",
            free_ligand_state_contract=contract,
        )


def test_receipt_valid_but_protic_structure_is_rejected() -> None:
    contract = _contract(smiles="CCO")

    with pytest.raises(ValueError, match="is not neutral nonprotic"):
        component_builder._validate_free_ligand_state_contract(
            ligand_id=11422,
            contract=contract,
        )


def test_missing_contract_keeps_unresolved_srd46_state_fatal() -> None:
    with pytest.raises(ValueError, match="no explicit canonical HxL/HOL state"):
        component_builder._build_ligand_component(
            ligand_id=11422,
            ligand_row=_unresolved_row(),
            spec_id="L1",
            total="Not defined",
        )
