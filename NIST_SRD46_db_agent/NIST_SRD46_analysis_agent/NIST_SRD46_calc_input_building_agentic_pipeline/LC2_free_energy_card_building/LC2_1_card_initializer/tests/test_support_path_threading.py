from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


_THIS = Path(__file__).resolve()
_PIPELINE_ROOT = _THIS.parents[3]
_ANALYSIS_ROOT = _THIS.parents[4]
_WORKSPACE_ROOT = _THIS.parents[6]
for _path in (_WORKSPACE_ROOT, _PIPELINE_ROOT, _ANALYSIS_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from LC2_free_energy_card_building.LC2_1_card_initializer import (
    LC2_1_ref_eq_card_orchestrator as lc2_1_orchestrator,
)
from LC2_free_energy_card_building import (
    LC2_free_energy_card_orchestrator as lc2_orchestrator,
)
builder = sys.modules[lc2_1_orchestrator.build_ref_cards_from_lc1_2_card.__module__]


class SupportPathThreadingTests(unittest.TestCase):
    def test_dependency_closure_uses_only_validated_h_ligand_and_metal_oh_pairs(self) -> None:
        fe_citrate = {
            "metal_id": "metal_61", "ligand_id": "ligand_9058",
            "eq_network": "ref_eq_net_22182",
        }
        h_citrate = {
            "metal_id": "metal_68", "ligand_id": "ligand_9058",
            "eq_network": "ref_eq_net_22067",
        }
        fe_hydroxide = {
            "metal_id": "metal_61", "ligand_id": "ligand_10076",
            "eq_network": "ref_eq_net_27465",
        }
        unrelated = {
            "metal_id": "metal_41", "ligand_id": "ligand_9058",
            "eq_network": "ref_eq_net_22180",
        }

        dependencies = builder._validated_dependency_networks(
            fe_citrate,
            [unrelated, fe_hydroxide, fe_citrate, h_citrate],
        )

        self.assertEqual(dependencies, [fe_hydroxide, h_citrate])

    def test_enabled_path_refuses_shared_reference_storage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "lc1_2_eqmap_card.json"
            base.write_text('{"equilibrium_networks":[]}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "cannot be written"):
                builder.build_ref_cards_from_lc1_2_card(
                    base,
                    storage_dir=builder._DEFAULT_STORAGE,
                    support_eq_map_path=Path(tmp) / "not-read-because-guard-runs-first.json",
                    expected_support_session_id="threading-test",
                    expected_support_eq_map_sha256="a" * 64,
                    session_working_map_path=Path(tmp) / "not-read-session-map.json",
                    expected_session_working_map_sha256="b" * 64,
                )

    def test_enabled_public_seams_require_exact_session_map_publication(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "lc1_2_eqmap_card.json"
            catalog = root / "system_catalog.json"
            support = root / "support.json"
            base.write_text('{"equilibrium_networks":[]}', encoding="utf-8")
            catalog.write_text(
                json.dumps({
                    "system_catalog": {
                        "chemical_system": {
                            "metals": [{
                                "name": "Fe",
                                "redox_states": [{"db_id": "metal_61"}],
                            }],
                            "ligands": [{"name": "DMF", "db_id": "ligand_11422"}],
                        }
                    }
                }),
                encoding="utf-8",
            )
            support.write_text("{}", encoding="utf-8")
            common = {
                "support_eq_map_path": support,
                "expected_support_session_id": "threading-test",
                "expected_support_eq_map_sha256": "a" * 64,
            }

            with patch.object(builder, "_build_ref_cards_with_native_support_eq_map") as compile_support:
                with self.assertRaisesRegex(
                    ValueError,
                    "requires session_working_map_path",
                ):
                    builder.build_ref_cards_from_lc1_2_card(
                        base,
                        storage_dir=root / "builder",
                        **common,
                    )
            compile_support.assert_not_called()

            with self.assertRaisesRegex(
                ValueError,
                "requires session_working_map_path",
            ):
                lc2_1_orchestrator.run_lc2_1(
                    system_catalog_path=catalog,
                    lc1_2_eqmap_card_path=base,
                    output_dir=root / "orchestrator",
                    **common,
                )
            self.assertFalse((root / "orchestrator").exists())

            with self.assertRaisesRegex(
                ValueError,
                "requires session_working_map_path",
            ):
                lc2_orchestrator.run_lc2(
                    "threading test",
                    system_catalog_path=catalog,
                    lc1_2_eqmap_card_path=base,
                    output_dir=root / "lc2",
                    **common,
                )
            self.assertFalse((root / "lc2").exists())

            with self.assertRaisesRegex(
                ValueError,
                "exact lowercase expected_session_working_map_sha256",
            ):
                builder.build_ref_cards_from_lc1_2_card(
                    base,
                    storage_dir=root / "builder-uppercase-digest",
                    session_working_map_path=root / "session-map.json",
                    expected_session_working_map_sha256="B" * 64,
                    **common,
                )

    def test_none_uses_literal_legacy_builder_without_loading_optional_package(self) -> None:
        optional_prefix = (
            "LC2_free_energy_card_building.LC2_1_card_initializer."
            "native_support_eq_map"
        )
        for module_name in list(sys.modules):
            if module_name == optional_prefix or module_name.startswith(optional_prefix + "."):
                sys.modules.pop(module_name)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "lc1_2_eqmap_card.json"
            pair = {
                "metal_id": "metal_41",
                "ligand_id": "ligand_5760",
                "eq_network": "ref_eq_net_86",
            }
            base.write_text(json.dumps({"equilibrium_networks": [pair]}), encoding="utf-8")
            expected = root / "legacy.md"
            with patch.object(
                builder,
                "build_or_load_ref_card",
                return_value=("legacy", {}, expected),
            ) as legacy:
                result = builder.build_ref_cards_from_lc1_2_card(
                    base,
                    storage_dir=root,
                    auto_hydroxide=False,
                    auto_pka=False,
                    atlas_merge=False,
                )

            self.assertEqual(result, [expected])
            legacy.assert_called_once_with(
                pair,
                storage_dir=root,
                auto_hydroxide=False,
                auto_pka=False,
                atlas_merge=False,
            )
            self.assertFalse(any(
                name == optional_prefix or name.startswith(optional_prefix + ".")
                for name in sys.modules
            ))
            self.assertFalse((root / "support_eq_map_compile_manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
