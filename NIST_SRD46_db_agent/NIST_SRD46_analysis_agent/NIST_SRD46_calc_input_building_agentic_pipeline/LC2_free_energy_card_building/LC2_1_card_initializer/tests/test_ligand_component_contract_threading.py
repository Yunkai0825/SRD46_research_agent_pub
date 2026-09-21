from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


_THIS = Path(__file__).resolve()
_PIPELINE_ROOT = _THIS.parents[3]
_ANALYSIS_ROOT = _THIS.parents[4]
_WORKSPACE_ROOT = _THIS.parents[6]
for _path in (_WORKSPACE_ROOT, _PIPELINE_ROOT, _ANALYSIS_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from LC2_free_energy_card_building.LC2_1_card_initializer import (
    LC2_1_ref_eq_card_orchestrator as orchestrator,
)


builder = sys.modules[orchestrator.build_ref_cards_from_lc1_2_card.__module__]
single_pair = sys.modules[builder.render_card_from_eq_map_files.__module__]


def _contract() -> dict:
    payload = {
        "canonical_HOL": "L",
        "charge": 0,
        "reference_state_classification": "neutral_nonprotic_free_ligand/v1",
        "provenance": {
            "kind": "PubChem",
            "compound_id": 6228,
            "query_name": "N,N-Dimethylformamide",
            "resolved_iupac_name": "N,N-dimethylformamide",
            "canonical_smiles": "CN(C)C=O",
            "inchi": "InChI=1S/C3H7NO/c1-4(2)3-5/h3H,1-2H3",
            "identity_binding": "unique match for canonical SRD-46 ligand name",
        },
        "derivation": {
            "rule": "pubchem_rdkit_neutral_nonprotic_free_ligand/v1",
            "formal_charge_method": "RDKit Chem.GetFormalCharge",
            "nonprotic_check": "no N/O/P/S atom bears hydrogen",
        },
    }
    payload["receipt_sha256"] = hashlib.sha256(json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")).hexdigest()
    return payload


class LigandComponentContractThreadingTests(unittest.TestCase):
    def test_catalog_extraction_keeps_id_binding_and_canonical_digest(self) -> None:
        contract = _contract()
        chem = {
            "metals": [{"name": "Fe", "redox_states": [{"db_id": "metal_61"}]}],
            "ligands": [{
                "name": "DMF",
                "db_id": "ligand_11422",
                "free_ligand_state": contract,
            }],
        }

        contracts = orchestrator._ligand_component_contracts(chem)

        self.assertEqual(contracts, {11422: contract})
        self.assertIsNot(contracts[11422], contract)
        self.assertRegex(
            orchestrator._ligand_component_contract_sha256(contracts) or "",
            r"^[0-9a-f]{64}$",
        )

    def test_run_lc2_1_threads_contract_for_lc1_2_and_records_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            contract = _contract()
            catalog = root / "system_catalog.json"
            base = root / "lc1_2_eqmap_card.json"
            catalog.write_text(json.dumps({
                "system_catalog": {"chemical_system": {
                    "metals": [{
                        "name": "Fe",
                        "redox_states": [{"db_id": "metal_61"}],
                    }],
                    "ligands": [{
                        "name": "DMF",
                        "db_id": "ligand_11422",
                        "free_ligand_state": contract,
                    }],
                }}
            }), encoding="utf-8")
            base.write_text('{"equilibrium_networks":[]}', encoding="utf-8")
            fake_card = root / "pair.md"

            with patch.object(
                orchestrator,
                "build_ref_cards_from_lc1_2_card",
                return_value=[fake_card],
            ) as build, patch.object(
                orchestrator,
                "merge_ref_cards",
                return_value=("merged", SimpleNamespace(species=[])),
            ):
                manifest = orchestrator.run_lc2_1(
                    system_catalog_path=catalog,
                    lc1_2_eqmap_card_path=base,
                    output_dir=root / "out",
                    test_name="dmf",
                )

            self.assertEqual(
                build.call_args.kwargs["ligand_component_contracts"],
                {11422: contract},
            )
            self.assertEqual(manifest["ligand_component_contract_count"], 1)
            self.assertEqual(
                manifest["ligand_component_contract_receipts"],
                {"ligand_11422": contract["receipt_sha256"]},
            )
            self.assertRegex(
                manifest["ligand_component_contract_sha256"] or "",
                r"^[0-9a-f]{64}$",
            )

    def test_run_lc2_1_threads_contract_for_catalog_only_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            contract = _contract()
            catalog = root / "system_catalog.json"
            catalog.write_text(json.dumps({
                "system_catalog": {"chemical_system": {
                    "metals": [{
                        "name": "Fe",
                        "redox_states": [{"db_id": "metal_61"}],
                    }],
                    "ligands": [{
                        "name": "DMF",
                        "db_id": "ligand_11422",
                        "free_ligand_state": contract,
                    }],
                }}
            }), encoding="utf-8")
            fake_card = root / "pair.md"

            with patch.object(
                orchestrator,
                "build_all_ref_cards",
                return_value=[fake_card],
            ) as build, patch.object(
                orchestrator,
                "merge_ref_cards",
                return_value=("merged", SimpleNamespace(species=[])),
            ):
                orchestrator.run_lc2_1(
                    system_catalog_path=catalog,
                    output_dir=root / "out",
                    test_name="dmf",
                )

            self.assertEqual(
                build.call_args.kwargs["ligand_component_contracts"],
                {11422: contract},
            )

    def test_lc1_2_builder_threads_contract_to_ordinary_and_native_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            contract_map = {11422: _contract()}
            pair = {
                "metal_id": "metal_61",
                "ligand_id": "ligand_11422",
                "eq_network": "ref_eq_net_1",
            }
            base = root / "lc1_2_eqmap_card.json"
            base.write_text(json.dumps({"equilibrium_networks": [pair]}), encoding="utf-8")
            expected = root / "pair.md"

            with patch.object(
                builder,
                "build_or_load_ref_card",
                return_value=("", {}, expected),
            ) as ordinary:
                builder.build_ref_cards_from_lc1_2_card(
                    base,
                    storage_dir=root,
                    ligand_component_contracts=contract_map,
                    auto_hydroxide=False,
                    auto_pka=False,
                )
            self.assertEqual(
                ordinary.call_args.kwargs["ligand_component_contracts"],
                contract_map,
            )

            with patch.object(
                builder,
                "_build_ref_cards_with_native_support_eq_map",
                return_value=[],
            ) as native:
                builder.build_ref_cards_from_lc1_2_card(
                    base,
                    storage_dir=root / "native",
                    support_eq_map_path=root / "support.json",
                    expected_support_session_id="session",
                    expected_support_eq_map_sha256="a" * 64,
                    session_working_map_path=root / "working.json",
                    expected_session_working_map_sha256="b" * 64,
                    allowed_system_pairs={(61, 11422)},
                    system_catalog_sha256="c" * 64,
                    ligand_component_contracts=contract_map,
                )
            self.assertEqual(
                native.call_args.kwargs["ligand_component_contracts"],
                contract_map,
            )

    def test_render_forwards_contract_to_component_builder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ids = root / "ids.json"
            maps = root / "maps.json"
            ids.write_text("{}", encoding="utf-8")
            maps.write_text("{}", encoding="utf-8")
            contract_map = {11422: _contract()}

            with patch.object(
                single_pair,
                "build_components_from_ids_json",
                return_value={"components": {}},
            ) as components, patch.object(
                single_pair,
                "build_final_card",
                return_value={"components": {}, "equations": {}},
            ):
                single_pair.render_card_from_eq_map_files(
                    ids_json_path=ids,
                    maps_json_path=maps,
                    temperature=25.0,
                    ionic_strength=0.1,
                    ligand_component_contracts=contract_map,
                )

            self.assertEqual(
                components.call_args.kwargs["ligand_component_contracts"],
                contract_map,
            )

    def test_contract_card_bypasses_legacy_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            contract_map = {11422: _contract()}
            pair = {
                "metal_id": "metal_61",
                "ligand_id": "ligand_11422",
                "eq_network": "ref_eq_net_1",
            }
            meta = {
                "metal_id": 61,
                "ligand_id": 11422,
                "eq_net_id": 1,
                "temperature": 25.0,
                "ionic_strength": 0.1,
                "system_name": "Fe / DMF",
                "ids_json_path": str(root / "ids.json"),
                "maps_json_path": str(root / "maps.json"),
                "augmented_networks": [],
                "patches": [],
            }

            with patch.object(builder, "find_existing_ref_card") as cache, patch.object(
                builder,
                "build_or_load_ref_pair_eq_map",
                return_value=meta,
            ), patch.object(
                builder,
                "render_ref_pair_card_from_eq_map",
                return_value=("", {}, root / "new.md"),
            ) as render:
                builder.build_or_load_ref_card(
                    pair,
                    storage_dir=root,
                    ligand_component_contracts=contract_map,
                )

            cache.assert_not_called()
            self.assertEqual(
                render.call_args.kwargs["ligand_component_contracts"],
                contract_map,
            )

    def test_contract_digest_is_part_of_ordinary_card_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            contract_map = {11422: _contract()}
            meta = {
                "metal_id": 61,
                "ligand_id": 11422,
                "eq_net_id": 1,
                "temperature": 25.0,
                "ionic_strength": 0.1,
                "system_name": "Fe / DMF",
                "ids_json_path": str(root / "ids.json"),
                "maps_json_path": str(root / "maps.json"),
                "augmented_networks": [],
                "patches": [],
            }

            with patch.object(
                builder,
                "render_card_from_eq_map_files",
                return_value={"components": {}, "equations": {}},
            ), patch.object(
                builder,
                "build_ref_card_filename",
                return_value="base-card",
            ), patch.object(
                builder,
                "parse_ref_eq_json_card",
                return_value=SimpleNamespace(),
            ), patch.object(
                builder,
                "generate_free_energy_card_md",
                return_value="card",
            ):
                _md, _card, path = builder.render_ref_pair_card_from_eq_map(
                    meta,
                    storage_dir=root,
                    ligand_component_contracts=contract_map,
                )

            digest = builder._ligand_component_contract_sha256(contract_map)
            self.assertEqual(
                path.name,
                f"base-card_component-{digest[:16]}.md",
            )


if __name__ == "__main__":
    unittest.main()
