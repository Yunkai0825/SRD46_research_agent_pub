from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock


_THIS = Path(__file__).resolve()
_PIPELINE_ROOT = _THIS.parents[3]
_ANALYSIS_ROOT = _THIS.parents[4]
_WORKSPACE_ROOT = _THIS.parents[6]
for _path in (_WORKSPACE_ROOT, _PIPELINE_ROOT, _ANALYSIS_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from LC2_free_energy_card_building.LC2_1_card_initializer.native_support_eq_map import (
    ESTIMATED_SOURCE,
    NativeSupportEqMapError,
    load_native_support_eq_map,
    load_session_working_map,
)
from LC2_free_energy_card_building.LC2_1_card_initializer import (
    LC2_1_ref_eq_card_orchestrator as lc2_1_orchestrator,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.dispatch_srd46_query.evidence_receipts import (
    build_evidence_receipt_snapshot,
)
builder = sys.modules[lc2_1_orchestrator.build_ref_cards_from_lc1_2_card.__module__]

equation_builder = sys.modules[
    builder.render_card_from_eq_map_files.__module__.rsplit(".", 1)[0]
    + ".equation_builder"
]
component_builder = sys.modules[
    builder.render_card_from_eq_map_files.__module__.rsplit(".", 1)[0]
    + ".component_builder"
]


@contextmanager
def _explicit_neutral_dmf_component_contract():
    """Supply the synthetic DMF fixture's otherwise-missing component state.

    Real SRD-46 ligand_11422 has neither a canonical HxL/HOL declaration nor
    a pKa-bracket charge.  The native-support tests exercise support-map
    materialization, not inference of those missing chemical fields, so the
    fixture declares both explicitly instead of weakening the production
    fail-loud gate or inventing a runtime default.
    """

    original_fetch = component_builder._fetch_ligand_row
    original_charge = component_builder._ligand_charge_from_brackets

    def fetch_ligand_row(ligand_id: int) -> dict:
        row = original_fetch(ligand_id)
        if ligand_id != 11422:
            return row
        return {
            **row,
            "ligand_HxL_definition": "L",
            "pka_brackets": [{
                "state_id": "L",
                "HxL_form": "L",
                "charge": 0,
                "is_estimated": 0,
            }],
        }

    def ligand_charge(ligand_id: int, **kwargs: object) -> int:
        if ligand_id == 11422:
            return 0
        return original_charge(ligand_id, **kwargs)

    with (
        mock.patch.object(
            component_builder, "_fetch_ligand_row", side_effect=fetch_ligand_row,
        ),
        mock.patch.object(
            component_builder,
            "_ligand_charge_from_brackets",
            side_effect=ligand_charge,
        ),
    ):
        yield


def _canonical_digest(payload: object) -> str:
    return hashlib.sha256(json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_session_working_map(
    root: Path,
    *,
    base_card: dict,
    support_path: Path,
) -> tuple[Path, str]:
    """Publish the same validated session-map shape LC1_3 hands to LC2."""

    support_document = json.loads(support_path.read_text(encoding="utf-8"))
    support_pairs = {
        (int(row["metal_id"]), int(row["ligand_id"]))
        for row in support_document["eq_node"]
    }
    loaded_support = load_native_support_eq_map(
        support_path,
        base_eq_map_card=base_card,
        allowed_system_pairs=support_pairs,
        expected_support_session_id="lc2-native-test",
        expected_support_eq_map_sha256=_file_sha256(support_path),
    )
    pairs: list[dict] = []
    pair_index: dict[tuple[int, int], dict] = {}
    for entry in base_card.get("equilibrium_networks", []):
        pair = (
            int(str(entry["metal_id"]).rsplit("_", 1)[-1]),
            int(str(entry["ligand_id"]).rsplit("_", 1)[-1]),
        )
        target = {
            "metal_id": pair[0],
            "ligand_id": pair[1],
            "selected_network_ids": [
                int(str(entry["eq_network"]).rsplit("_", 1)[-1])
            ],
        }
        pairs.append(target)
        pair_index[pair] = target
    for pair, rows in loaded_support.rows_by_pair.items():
        target = pair_index.get(pair)
        if target is None:
            target = {
                "metal_id": pair[0],
                "ligand_id": pair[1],
                "selected_network_ids": [],
            }
            pairs.append(target)
            pair_index[pair] = target
        target["estimated_eq_nodes"] = json.loads(json.dumps(list(rows)))

    path = root / "session_working_eq_map.json"
    path.write_text(json.dumps({"pairs": pairs}, indent=2), encoding="utf-8")
    digest = _file_sha256(path)
    load_session_working_map(
        path,
        expected_session_working_map_sha256=digest,
        support_rows_by_pair=loaded_support.rows_by_pair,
        base_eq_map_card=base_card,
        allowed_system_pairs=set(pair_index),
    )
    return path, digest


def _native_support_document(
    base_card: dict,
    *,
    metal_id: int = 61,
    ligand_id: int = 11422,
    metal_name: str = "Fe^[3+]",
    ligand_name: str = "N,N-Dimethylformamide (DMF)",
    evidence_vlm_id: int = 95941,
    evidence_network_id: int = 678,
    evidence_citation_id: int = 2971,
    beta_definition_id: int = 812,
    beta_definition_name: str = "[ML]/[M][L]",
    equation_python: str = "[M] + [L] <=> [ML]",
    node_species: tuple[tuple[str, str], ...] = (
        ("[L]", "LHS"),
        ("[M]", "LHS"),
        ("[ML]", "RHS"),
    ),
) -> dict:
    scope = {
        "metal_id": metal_id,
        "metal_name": metal_name,
        "ligand_id": ligand_id,
        "ligand_name": ligand_name,
    }
    authorization = build_evidence_receipt_snapshot(
        tool_history=[{
            "tool": "search_stability",
            "is_error": False,
            "result_full": json.dumps({
                "vlm_id": evidence_vlm_id,
                "beta_definition_id": beta_definition_id,
                "network_db_id": evidence_network_id,
                "literature_alt_id": evidence_citation_id,
            }),
        }],
        scope=scope,
        authorization_context_id="q001",
    )
    authorization.pop("snapshot_sha256", None)
    authorization["snapshot_sha256"] = _canonical_digest(authorization)
    provenance = {
        "source": ESTIMATED_SOURCE,
        "query_id": "q001",
        "query_answer_sha256": "a" * 64,
        "evidence_authorization_context_id": "q001",
        "evidence_authorization_sha256": authorization["snapshot_sha256"],
        "evidence_authorization_metadata_key": "query_authorization.q001",
        "session_vlm_id": -5_000_001,
        "topology_source": f"beta_def_{beta_definition_id}",
        "evidence_vlm_ids": [f"vlm_{evidence_vlm_id}"],
        "evidence_network_ids": [f"ref_eq_net_{evidence_network_id}"],
        "evidence_citation_ids": [f"lit_{evidence_citation_id}"],
        "estimation_method": "analog interpolation",
        "uncertainty_log10": 0.5,
        "assumptions": ["aqueous 1 mol/L standard state"],
        "rationale": "focused LC2 native-map integration fixture",
    }
    return {
        "eq_map_collection": [{
            "collection_id": -1_000_001,
            "metal_id": metal_id,
            "ligand_id": ligand_id,
            "metal_name": metal_name,
            "ligand_name": ligand_name,
            "total_entries": 1,
            "total_networks": 1,
            "iterations_count": 1,
            "unassigned_count": 0,
            "created_at": "2026-08-24T00:00:00+00:00",
        }],
        "eq_map": [{
            "map_id": -2_000_001,
            "collection_id": -1_000_001,
            "map_key": "estimated_iter_0_T25_I0.1",
            "iteration": 0,
            "condition_temperature": 25.0,
            "condition_ionic_strength": 0.1,
            "condition_temp_min": 25.0,
            "condition_temp_max": 25.0,
            "condition_ionic_min": 0.1,
            "condition_ionic_max": 0.1,
            "entry_count": 1,
            "network_count": 1,
            "stray_count": 0,
        }],
        "eq_network": [{
            "network_db_id": -3_000_001,
            "map_id": -2_000_001,
            "network_id": 0,
            "node_count": 1,
            "edge_count": 0,
        }],
        "eq_node": [{
            "node_db_id": -4_000_001,
            "network_db_id": -3_000_001,
            "vlm_id": -5_000_001,
            "entry_index": 0,
            "metal_id": metal_id,
            "ligand_id": ligand_id,
            "beta_definition_id": beta_definition_id,
            "beta_definition_name": beta_definition_name,
            "equation_python": equation_python,
            "constant_type": "K",
            "constant_value": 1.25,
            "temperature": 25.0,
            "ionic_strength": 0.1,
            "is_duplicate": 0,
            "used_in_map": 1,
        }],
        "eq_node_species": [
            {"node_db_id": -4_000_001, "species": species, "side": side}
            for species, side in node_species
        ],
        "eq_edge": [],
        "eq_edge_species": [],
        "eq_network_species": [
            {"network_db_id": -3_000_001, "species": species}
            for species in sorted({species for species, _side in node_species})
        ],
        "eq_map_stray": [],
        "eq_collection_unassigned": [],
        "eq_export_metadata": [
            {"key": "source", "value": ESTIMATED_SOURCE},
            {"key": "authoritative", "value": "false"},
            {"key": "artifact_kind", "value": "session supporting eq_map"},
            {
                "key": "assembly",
                "value": "deterministic parsed-speciation-to-native-eq-map",
            },
            {"key": "session_id", "value": "lc2-native-test"},
            {"key": "base_eq_map_sha256", "value": _canonical_digest(base_card)},
            {
                "key": "query_authorization.q001",
                "value": json.dumps(
                    authorization,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            },
            {
                "key": "estimated_node.-4000001.provenance",
                "value": json.dumps(
                    provenance,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            },
        ],
    }


def _replace_provenance(document: dict, **updates: object) -> None:
    row = next(
        value for value in document["eq_export_metadata"]
        if value["key"] == "estimated_node.-4000001.provenance"
    )
    provenance = json.loads(row["value"])
    provenance.update(updates)
    row["value"] = json.dumps(
        provenance,
        sort_keys=True,
        separators=(",", ":"),
    )


def _replace_authorization(
    document: dict,
    mutate,
    *,
    rebind_provenance_digest: bool,
) -> None:
    row = next(
        value for value in document["eq_export_metadata"]
        if value["key"] == "query_authorization.q001"
    )
    authorization = json.loads(row["value"])
    mutate(authorization)
    authorization.pop("snapshot_sha256", None)
    authorization["snapshot_sha256"] = _canonical_digest(authorization)
    row["value"] = json.dumps(
        authorization,
        sort_keys=True,
        separators=(",", ":"),
    )
    if rebind_provenance_digest:
        _replace_provenance(
            document,
            evidence_authorization_sha256=authorization["snapshot_sha256"],
        )


def _write_system_catalog(
    root: Path,
    *,
    metal_ids: tuple[int, ...] = (61, 62),
    ligand_ids: tuple[int, ...] = (11422,),
) -> Path:
    """Write the nested-redox catalog shape emitted by LC1_1."""

    document = {
        "system_catalog": {
            "chemical_system": {
                "metals": [{
                    "name": "Fe",
                    "element": "Fe",
                    "redox_states": [
                        {
                            "internal_id": f"Fe-redox-{metal_id}",
                            "db_id": f"metal_{metal_id}",
                        }
                        for metal_id in metal_ids
                    ],
                }],
                "ligands": [
                    {
                        "name": "N,N-Dimethylformamide (DMF)",
                        "db_id": f"ligand_{ligand_id}",
                    }
                    for ligand_id in ligand_ids
                ],
            },
        },
    }
    path = root / "system_catalog.json"
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    return path


class NativeSupportEqMapTests(unittest.TestCase):
    def test_loader_preserves_beta_identity_and_internal_row_shape(self) -> None:
        base_card = {"equilibrium_networks": []}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "support.json"
            path.write_text(json.dumps(_native_support_document(base_card)), encoding="utf-8")
            loaded = load_native_support_eq_map(
                path,
                base_eq_map_card=base_card,
                allowed_system_pairs={(61, 11422)},
                expected_support_session_id="lc2-native-test",
                expected_support_eq_map_sha256=_file_sha256(path),
            )

        row = loaded.rows_by_pair[(61, 11422)][0]
        self.assertEqual(row["beta_definition_id"], 812)
        self.assertEqual(row["beta_definition_name"], "[ML]/[M][L]")
        self.assertEqual(row["equation_python"], "[M] + [L] <=> [ML]")
        self.assertEqual(row["node_db_id"], -4_000_001)
        self.assertEqual(row["_estimated_provenance"]["source"], ESTIMATED_SOURCE)
        self.assertEqual(
            set(row),
            {
                "node_db_id", "vlm_id", "constant_type", "log_K",
                "temperature", "ionic_strength", "equation_python",
                "beta_definition_id", "beta_definition_name", "metal_id",
                "ligand_id", "LHS_species_json", "RHS_species_json",
                "_estimated_provenance",
            },
        )

    def test_loader_rejects_obsolete_evidence_receipt_version(self) -> None:
        base_card = {"equilibrium_networks": []}
        document = _native_support_document(base_card)
        _replace_authorization(
            document,
            lambda value: value.update({"authorization_version": 2}),
            rebind_provenance_digest=True,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "obsolete_receipt_version.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(
                NativeSupportEqMapError,
                "current version 3",
            ):
                load_native_support_eq_map(
                    path,
                    base_eq_map_card=base_card,
                    allowed_system_pairs={(61, 11422)},
                    expected_support_session_id="lc2-native-test",
                    expected_support_eq_map_sha256=_file_sha256(path),
                )

    def test_loader_accepts_v3_observed_cross_pair_cross_topology_evidence(self) -> None:
        """V3 records observations; it does not restrict chemistry transfers."""

        base_card = {"equilibrium_networks": []}
        document = _native_support_document(
            base_card,
            metal_id=61,
            ligand_id=11422,
            metal_name="Fe^[3+]",
            ligand_name="N,N-Dimethylformamide (DMF)",
            evidence_vlm_id=166925,
            evidence_network_id=25920,
            evidence_citation_id=8171,
            beta_definition_id=812,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "v3_observed_support.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            loaded = load_native_support_eq_map(
                path,
                base_eq_map_card=base_card,
                allowed_system_pairs={(61, 11422)},
                expected_support_session_id="lc2-native-test",
                expected_support_eq_map_sha256=_file_sha256(path),
            )

        row = loaded.rows_by_pair[(61, 11422)][0]
        self.assertEqual(row["beta_definition_id"], 812)
        self.assertEqual(
            row["_estimated_provenance"]["evidence_vlm_ids"],
            ["vlm_166925"],
        )

    def test_loader_rejects_v3_receipt_union_tampering(self) -> None:
        base_card = {"equilibrium_networks": []}
        document = _native_support_document(
            base_card,
        )
        _replace_authorization(
            document,
            lambda value: value["tool_receipts"][0].update(
                {"observed_vlm_ids": []}
            ),
            rebind_provenance_digest=True,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "v3_bad_union_support.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(
                NativeSupportEqMapError,
                "tool-receipt union",
            ):
                load_native_support_eq_map(
                    path,
                    base_eq_map_card=base_card,
                    allowed_system_pairs={(61, 11422)},
                    expected_support_session_id="lc2-native-test",
                    expected_support_eq_map_sha256=_file_sha256(path),
                )

    def test_loader_rejects_v3_canonical_record_tampering(self) -> None:
        base_card = {"equilibrium_networks": []}
        document = _native_support_document(
            base_card,
        )
        _replace_authorization(
            document,
            lambda value: value["vlm_records"][0].update({"metal_id": 62}),
            rebind_provenance_digest=True,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "v3_bad_canonical_record_support.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(
                NativeSupportEqMapError,
                "canonical record disagrees with SRD-46",
            ):
                load_native_support_eq_map(
                    path,
                    base_eq_map_card=base_card,
                    allowed_system_pairs={(61, 11422)},
                    expected_support_session_id="lc2-native-test",
                    expected_support_eq_map_sha256=_file_sha256(path),
                )

    def test_loader_rejects_tampered_provenance_and_evidence(self) -> None:
        base_card = {"equilibrium_networks": []}
        cases = {
            "source": {"source": "not SRD46 estimation"},
            "query id": {"query_id": "agent-one"},
            "query digest": {"query_answer_sha256": "not-a-sha256"},
            "topology": {"topology_source": "beta_def_79"},
            "noncanonical VLM ID": {"evidence_vlm_ids": [93657]},
            "missing VLM": {"evidence_vlm_ids": ["vlm_999999999"]},
            "wrong-beta VLM": {
                "evidence_vlm_ids": ["vlm_93606"],
                "evidence_network_ids": [],
                "evidence_citation_ids": [],
            },
            "unlinked network": {"evidence_network_ids": ["ref_eq_net_86"]},
            "unlinked citation": {"evidence_citation_ids": ["lit_1"]},
            "method type": {"estimation_method": 17},
            "uncertainty type": {"uncertainty_log10": "0.5"},
            "negative uncertainty": {"uncertainty_log10": -0.5},
            "assumptions type": {"assumptions": ["aqueous", 17]},
            "rationale": {"rationale": "   "},
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index, (label, updates) in enumerate(cases.items()):
                with self.subTest(label=label):
                    document = _native_support_document(base_card)
                    _replace_provenance(document, **updates)
                    path = root / f"tampered_{index}.json"
                    path.write_text(json.dumps(document), encoding="utf-8")
                    with self.assertRaises(NativeSupportEqMapError):
                        load_native_support_eq_map(
                            path,
                            base_eq_map_card=base_card,
                            allowed_system_pairs={(61, 11422)},
                            expected_support_session_id="lc2-native-test",
                            expected_support_eq_map_sha256=_file_sha256(path),
                        )

    def test_loader_rejects_tampered_query_authorization_binding(self) -> None:
        base_card = {"equilibrium_networks": []}
        documents = []

        digest_mismatch = _native_support_document(base_card)
        _replace_provenance(
            digest_mismatch,
            evidence_authorization_sha256="0" * 64,
        )
        documents.append(("node digest mismatch", digest_mismatch))

        scope_mismatch = _native_support_document(base_card)
        _replace_authorization(
            scope_mismatch,
            lambda value: value["scope"].update({"metal_id": 62}),
            rebind_provenance_digest=True,
        )
        documents.append(("snapshot scope mismatch", scope_mismatch))

        evidence_binding_mismatch = _native_support_document(base_card)
        _replace_authorization(
            evidence_binding_mismatch,
            lambda value: value["vlm_records"][0].update({"metal_id": 92}),
            rebind_provenance_digest=True,
        )
        documents.append(("VLM relation mismatch", evidence_binding_mismatch))

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index, (label, document) in enumerate(documents):
                with self.subTest(label=label):
                    path = root / f"authorization_tamper_{index}.json"
                    path.write_text(json.dumps(document), encoding="utf-8")
                    with self.assertRaises(NativeSupportEqMapError):
                        load_native_support_eq_map(
                            path,
                            base_eq_map_card=base_card,
                            allowed_system_pairs={(61, 11422)},
                            expected_support_session_id="lc2-native-test",
                            expected_support_eq_map_sha256=_file_sha256(path),
                        )

    def test_measured_same_beta_wins(self) -> None:
        base_card = {"equilibrium_networks": []}
        document = _native_support_document(base_card)
        support_node = document["eq_node"][0]
        estimated = {
            "node_db_id": support_node["node_db_id"],
            "vlm_id": support_node["vlm_id"],
            "constant_type": "K",
            "log_K": 1.25,
            "temperature": 25.0,
            "ionic_strength": 0.1,
            "equation_python": support_node["equation_python"],
            "beta_definition_id": 812,
            "beta_definition_name": support_node["beta_definition_name"],
            "metal_id": 61,
            "ligand_id": 11422,
            "LHS_species_json": [
                {"species": "[L]", "power": 1, "phase": "aqueous"},
                {"species": "[M]", "power": 1, "phase": "aqueous"},
            ],
            "RHS_species_json": [
                {"species": "[ML]", "power": 1, "phase": "aqueous"},
            ],
            "_estimated_provenance": {"source": ESTIMATED_SOURCE},
        }
        measured = {**estimated, "node_db_id": 10, "vlm_id": 20}
        measured.pop("_estimated_provenance")
        merged = equation_builder._merge_estimated_rows(
            [measured], [estimated], pair={"metal_id": 61, "ligand_id": 11422},
        )
        self.assertEqual(merged, [measured])

    def test_same_reaction_different_beta_fails(self) -> None:
        base_card = {"equilibrium_networks": []}
        document = _native_support_document(base_card)
        node = document["eq_node"][0]
        common = {
            "constant_type": "K",
            "log_K": 1.25,
            "temperature": 25.0,
            "ionic_strength": 0.1,
            "equation_python": node["equation_python"],
            "beta_definition_name": node["beta_definition_name"],
            "metal_id": 61,
            "ligand_id": 11422,
            "LHS_species_json": [
                {"species": "[L]", "power": 1, "phase": "aqueous"},
                {"species": "[M]", "power": 1, "phase": "aqueous"},
            ],
            "RHS_species_json": [
                {"species": "[ML]", "power": 1, "phase": "aqueous"},
            ],
        }
        measured = {
            **common, "node_db_id": 10, "vlm_id": 20,
            "beta_definition_id": 812,
        }
        estimated = {
            **common, "node_db_id": -4_000_001, "vlm_id": -5_000_001,
            "beta_definition_id": 999,
            "_estimated_provenance": {"source": ESTIMATED_SOURCE},
        }
        with self.assertRaisesRegex(ValueError, "reaction/beta-definition collision"):
            equation_builder._merge_estimated_rows(
                [measured], [estimated],
                pair={"metal_id": 61, "ligand_id": 11422},
            )

    def test_measured_win_aggregate_separates_selected_from_materialized(self) -> None:
        base_card = {
            "equilibrium_networks": [{
                "metal_id": 92,
                "ligand_id": 5760,
                "eq_network": "ref_eq_net_19",
                "temperature": 25.0,
                "ionic_strength": 0.1,
                "patch_notes": {"patches": []},
            }],
        }
        document = _native_support_document(
            base_card,
            metal_id=92,
            ligand_id=5760,
            metal_name="Mg^[2+]",
            ligand_name="Aminoacetic acid (Glycine)",
            evidence_vlm_id=93657,
            evidence_network_id=19,
            evidence_citation_id=855,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base_path = root / "lc1_2_eqmap_card.json"
            support_path = root / "measured_pair_support_eq_map.json"
            catalog_path = _write_system_catalog(
                root,
                metal_ids=(92,),
                ligand_ids=(5760,),
            )
            base_path.write_text(json.dumps(base_card), encoding="utf-8")
            support_path.write_text(json.dumps(document, indent=2), encoding="utf-8")
            working_map_path, working_map_sha256 = _write_session_working_map(
                root,
                base_card=base_card,
                support_path=support_path,
            )
            manifest = lc2_1_orchestrator.run_lc2_1(
                system_catalog_path=catalog_path,
                lc1_2_eqmap_card_path=base_path,
                support_eq_map_path=support_path,
                expected_support_session_id="lc2-native-test",
                expected_support_eq_map_sha256=_file_sha256(support_path),
                session_working_map_path=working_map_path,
                expected_session_working_map_sha256=working_map_sha256,
                output_dir=root / "analysis_artifacts",
                test_name="measured_wins_aggregate",
                auto_hydroxide=False,
                # ref_eq_net_19 contains M + HL -> MHL.  Ask LC2 to
                # materialize the real H+/glycine protonation prerequisite.
                auto_pka=True,
            )

            self.assertEqual(manifest["support_candidate_count"], 1)
            self.assertEqual(manifest["selected_support_node_count"], 1)
            self.assertEqual(manifest["materialized_estimated_entry_count"], 0)
            compile_manifest = json.loads(
                Path(manifest["support_compile_manifest_path"]).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(compile_manifest["selected_support_node_count"], 1)
            self.assertEqual(
                compile_manifest["materialized_estimated_entry_count"],
                0,
            )

    def test_support_only_fe_dmf_uses_common_materialization_pipeline(self) -> None:
        base_card = {"equilibrium_networks": []}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base_path = root / "lc1_2_eqmap_card.json"
            support_path = root / "srd46_query_estimated_support_eq_map.json"
            storage = root / "session_ref_cards"
            base_path.write_text(json.dumps(base_card), encoding="utf-8")
            support_document = _native_support_document(base_card)
            support_path.write_text(
                json.dumps(support_document, indent=2), encoding="utf-8",
            )
            working_map_path, working_map_sha256 = _write_session_working_map(
                root,
                base_card=base_card,
                support_path=support_path,
            )
            with _explicit_neutral_dmf_component_contract():
                paths = builder.build_ref_cards_from_lc1_2_card(
                    base_path,
                    storage_dir=storage,
                    auto_hydroxide=False,
                    auto_pka=False,
                    support_eq_map_path=support_path,
                    expected_support_session_id="lc2-native-test",
                    expected_support_eq_map_sha256=_file_sha256(support_path),
                    session_working_map_path=working_map_path,
                    expected_session_working_map_sha256=working_map_sha256,
                    allowed_system_pairs={(61, 11422)},
                    system_catalog_sha256="c" * 64,
                )

            self.assertEqual(len(paths), 1)
            self.assertTrue(paths[0].exists())
            self.assertIn(ESTIMATED_SOURCE, paths[0].read_text(encoding="utf-8"))
            sidecar = json.loads(paths[0].with_suffix(".json").read_text(encoding="utf-8"))
            entries = [
                equilibrium
                for blocks in sidecar["equations"].values()
                for block in blocks
                for equilibrium in block["equilibria"]
            ]
            estimated = [
                row for row in entries
                if row["reference"]["source"] == ESTIMATED_SOURCE
            ]
            self.assertEqual(len(estimated), 1)
            self.assertEqual(estimated[0]["reference"]["source_database_ID"], "session_eq_node_-4000001")
            working_map = json.loads(next(
                (storage / "_working_eq_maps").rglob("maps_with_estimates.json")
            ).read_text(encoding="utf-8"))
            target = working_map["pairs"][0]
            self.assertEqual(target["selected_network_ids"], [])
            self.assertEqual(target["estimated_eq_nodes"][0]["beta_definition_id"], 812)
            self.assertTrue((storage / "support_eq_map_compile_manifest.json").exists())

    def test_support_only_auxiliary_patch_notes_become_vlm_overrides(self) -> None:
        # Regression: FF_1 Fe/DMF merge failure. LC1_2-patched hydrolysis
        # auxiliaries must materialize with the same vlm_overrides as the
        # reference cards, or the shared species clash in the LC2 merge.
        from LC2_free_energy_card_building.LC2_1_card_initializer.native_support_eq_map import (
            build_support_only_working_map,
        )

        aux_patched = {
            "eq_network": "ref_eq_net_27465",
            "metal_id": "metal_61",
            "ligand_id": "ligand_10076",
            "patch_notes": {
                "validated": True,
                "patches": [{
                    "node_key": "metal61_ligand10076_beta840_net27465",
                    "beta_definition_id": 840,
                    "examined_vlm_id": 170807,
                    "examined_value": 23.4,
                    "operation": "set_value",
                    "chosen_value": 21.85,
                    "rationale": "sibling-median outlier patch",
                }],
            },
        }
        aux_unpatched = {
            "eq_network": "ref_eq_net_27433",
            "metal_id": "metal_62",
            "ligand_id": "ligand_10076",
            "patch_notes": {"validated": True, "patches": []},
        }
        with tempfile.TemporaryDirectory() as tmp:
            paths = build_support_only_working_map(
                metal_id=61,
                ligand_id=11422,
                estimated_rows=[],
                auxiliary_networks=[aux_patched, aux_unpatched],
                output_dir=Path(tmp) / "condition_0",
            )
            maps_payload = json.loads(
                Path(paths["maps_json_path"]).read_text(encoding="utf-8")
            )

        by_pair = {
            (pair["metal_id"], pair["ligand_id"]): pair
            for pair in maps_payload["pairs"]
        }
        self.assertNotIn("vlm_overrides", by_pair[(61, 11422)])
        self.assertNotIn("vlm_overrides", by_pair[(62, 10076)])
        overrides = by_pair[(61, 10076)]["vlm_overrides"]
        self.assertEqual(len(overrides), 1)
        self.assertEqual(overrides[0]["action"], "set_value")
        self.assertEqual(overrides[0]["beta_definition_id"], 840)
        self.assertEqual(overrides[0]["vlm_id"], 170807)
        self.assertEqual(overrides[0]["chosen_value"], 21.85)
        self.assertEqual(overrides[0]["metal_id"], 61)
        self.assertEqual(overrides[0]["ligand_id"], 10076)

    def test_current_system_support_only_pair_absent_from_ref_map_is_accepted(self) -> None:
        base_card = {"equilibrium_networks": []}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base_path = root / "lc1_2_eqmap_card.json"
            support_path = root / "srd46_query_estimated_support_eq_map.json"
            catalog_path = _write_system_catalog(root)
            base_path.write_text(json.dumps(base_card), encoding="utf-8")
            support_document = _native_support_document(base_card)
            support_path.write_text(
                json.dumps(support_document, indent=2), encoding="utf-8",
            )
            working_map_path, working_map_sha256 = _write_session_working_map(
                root,
                base_card=base_card,
                support_path=support_path,
            )
            with _explicit_neutral_dmf_component_contract():
                manifest = lc2_1_orchestrator.run_lc2_1(
                    system_catalog_path=catalog_path,
                    lc1_2_eqmap_card_path=base_path,
                    support_eq_map_path=support_path,
                    expected_support_session_id="lc2-native-test",
                    expected_support_eq_map_sha256=_file_sha256(support_path),
                    session_working_map_path=working_map_path,
                    expected_session_working_map_sha256=working_map_sha256,
                    output_dir=root / "analysis_artifacts",
                    test_name="fe_dmf_estimated",
                    auto_hydroxide=False,
                    auto_pka=False,
                )

            self.assertEqual(manifest["support_node_count"], 1)
            self.assertEqual(manifest["selected_support_node_count"], 1)
            self.assertEqual(manifest["materialized_estimated_entry_count"], 1)
            self.assertTrue(manifest["provenance_binding_verified"])
            merged = Path(manifest["merged_card_path"]).read_text(encoding="utf-8")
            self.assertIn(ESTIMATED_SOURCE, merged)
            self.assertIn("session_eq_node_-4000001", merged)
            compile_manifest = json.loads(
                Path(manifest["support_compile_manifest_path"]).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                compile_manifest["allowed_system_pairs"],
                [
                    {"metal_id": 61, "ligand_id": 11422},
                    {"metal_id": 62, "ligand_id": 11422},
                ],
            )
            self.assertEqual(
                compile_manifest["support_session_id"],
                "lc2-native-test",
            )

    def test_valid_unrelated_sidecar_is_rejected_before_working_map_creation(self) -> None:
        base_card = {"equilibrium_networks": []}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base_path = root / "lc1_2_eqmap_card.json"
            support_path = root / "valid_but_unrelated_support_eq_map.json"
            catalog_path = _write_system_catalog(root, metal_ids=(62,))
            output_dir = root / "analysis_artifacts"
            base_path.write_text(json.dumps(base_card), encoding="utf-8")
            support_document = _native_support_document(base_card)
            support_path.write_text(
                json.dumps(support_document, indent=2), encoding="utf-8",
            )
            working_map_path, working_map_sha256 = _write_session_working_map(
                root,
                base_card=base_card,
                support_path=support_path,
            )

            with self.assertRaisesRegex(
                ValueError,
                "outside the active system catalog",
            ):
                lc2_1_orchestrator.run_lc2_1(
                    system_catalog_path=catalog_path,
                    lc1_2_eqmap_card_path=base_path,
                    support_eq_map_path=support_path,
                    expected_support_session_id="lc2-native-test",
                    expected_support_eq_map_sha256=_file_sha256(support_path),
                    session_working_map_path=working_map_path,
                    expected_session_working_map_sha256=working_map_sha256,
                    output_dir=output_dir,
                    test_name="reject_unrelated_pair",
                    auto_hydroxide=False,
                    auto_pka=False,
                )

            ref_cards = output_dir / "reject_unrelated_pair" / "_ref_cards"
            self.assertFalse((ref_cards / "_working_eq_maps").exists())
            self.assertFalse(
                (ref_cards / "support_eq_map_compile_manifest.json").exists()
            )

    def test_same_system_stale_sidecar_provenance_is_rejected_pre_compile(self) -> None:
        base_card = {"equilibrium_networks": []}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base_path = root / "lc1_2_eqmap_card.json"
            support_path = root / "stale_same_system_support_eq_map.json"
            catalog_path = _write_system_catalog(root)
            base_path.write_text(json.dumps(base_card), encoding="utf-8")
            support_document = _native_support_document(base_card)
            support_path.write_text(
                json.dumps(support_document, indent=2), encoding="utf-8",
            )
            working_map_path, working_map_sha256 = _write_session_working_map(
                root,
                base_card=base_card,
                support_path=support_path,
            )
            actual_digest = _file_sha256(support_path)
            cases = {
                "stale session": ("another-lc1-3-session", actual_digest),
                "stale digest": ("lc2-native-test", "f" * 64),
            }

            for index, (label, (session_id, digest)) in enumerate(cases.items()):
                with self.subTest(label=label):
                    output_dir = root / f"analysis_artifacts_{index}"
                    with self.assertRaisesRegex(
                        ValueError,
                        "publication receipt",
                    ):
                        lc2_1_orchestrator.run_lc2_1(
                            system_catalog_path=catalog_path,
                            lc1_2_eqmap_card_path=base_path,
                            support_eq_map_path=support_path,
                            expected_support_session_id=session_id,
                            expected_support_eq_map_sha256=digest,
                            session_working_map_path=working_map_path,
                            expected_session_working_map_sha256=(
                                working_map_sha256
                            ),
                            output_dir=output_dir,
                            test_name="reject_stale_same_system",
                            auto_hydroxide=False,
                            auto_pka=False,
                        )

                    ref_cards = (
                        output_dir / "reject_stale_same_system" / "_ref_cards"
                    )
                    self.assertFalse((ref_cards / "_working_eq_maps").exists())
                    self.assertFalse(
                        (ref_cards / "support_eq_map_compile_manifest.json").exists()
                    )


if __name__ == "__main__":
    unittest.main()
