from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.validate_support_eq_map.session_working_map import (
    SessionWorkingMapValidationError,
    adapted_rows_by_pair,
    build_session_working_map,
    validate_session_working_map,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.validate_support_eq_map import validate_support_eq_map_orchestrator as stage4


def _support_document(
    *,
    metal_id: int = 61,
    ligand_id: int = 11422,
    node_db_id: int = -4_000_001,
    vlm_id: int = -5_000_001,
    query_id: str = "q001",
) -> dict:
    provenance = {
        "source": "SRD46 query estimated values",
        "query_id": query_id,
        "query_answer_sha256": "a" * 64,
        "evidence_authorization_context_id": query_id,
        "evidence_authorization_sha256": "b" * 64,
        "evidence_authorization_metadata_key": f"query_authorization.{query_id}",
        "session_vlm_id": vlm_id,
        "topology_source": "beta_def_812",
        "evidence_vlm_ids": ["vlm_95941"],
        "evidence_network_ids": ["ref_eq_net_678"],
        "evidence_citation_ids": ["lit_2971"],
        "estimation_method": "fixture analogue transfer",
        "uncertainty_log10": 0.5,
        "assumptions": ["fixture only"],
        "rationale": "deterministic fixture",
    }
    return {
        "eq_export_metadata": [{
            "key": f"estimated_node.{node_db_id}.provenance",
            "value": json.dumps(provenance, sort_keys=True),
        }],
        "eq_node": [{
            "node_db_id": node_db_id,
            "network_db_id": -3_000_001,
            "vlm_id": vlm_id,
            "entry_index": 0,
            "metal_id": metal_id,
            "ligand_id": ligand_id,
            "beta_definition_id": 812,
            "beta_definition_name": "[ML]/[M][L]",
            "equation_python": "[M] + [L] <=> [ML]",
            "constant_type": "K",
            "constant_value": 1.25,
            "temperature": 25.0,
            "ionic_strength": 0.1,
            "is_duplicate": 0,
            "used_in_map": 1,
        }],
        "eq_node_species": [
            {"node_db_id": node_db_id, "species": "[L]", "side": "LHS"},
            {"node_db_id": node_db_id, "species": "[M]", "side": "LHS"},
            {"node_db_id": node_db_id, "species": "[ML]", "side": "RHS"},
        ],
    }


def test_existing_reference_pair_is_deep_copied_and_patched() -> None:
    base = {
        "pairs": [{
            "metal_id": 61,
            "ligand_id": 11422,
            "selected_network_ids": [678],
            "vlm_overrides": [{"beta_definition_id": 17, "action": "drop_node"}],
        }]
    }
    original = copy.deepcopy(base)
    support = _support_document()

    working = build_session_working_map(
        base_eq_map_card=base,
        support_document=support,
    )
    audit = validate_session_working_map(
        working,
        base_eq_map_card=base,
        support_document=support,
    )

    assert base == original
    assert working is not base
    assert working["pairs"][0] is not base["pairs"][0]
    assert working["pairs"][0]["selected_network_ids"] == [678]
    assert working["pairs"][0]["vlm_overrides"] == original["pairs"][0]["vlm_overrides"]
    assert working["pairs"][0]["estimated_eq_nodes"][0]["node_db_id"] < 0
    assert audit["n_existing_pairs_patched"] == 1
    assert audit["n_new_pairs_constructed"] == 0


def test_flat_production_card_prefixed_ids_are_normalized_without_mutation() -> None:
    base = {
        "_notes": "production LC1_2 flat card",
        "equilibrium_networks": [{
            "eq_network": "ref_eq_net_678",
            "metal_id": "metal_61",
            "ligand_id": "ligand_11422",
            "temperature": 25.0,
            "ionic_strength": 0.1,
            "patch_notes": {"patches": []},
        }],
    }
    original = copy.deepcopy(base)
    working = build_session_working_map(
        base_eq_map_card=base,
        support_document=_support_document(),
    )

    assert base == original
    assert working["pairs"][0]["metal_id"] == 61
    assert working["pairs"][0]["ligand_id"] == 11422
    assert working["pairs"][0]["selected_network_ids"] == [678]


def test_missing_reference_pair_uses_existing_support_only_shape() -> None:
    support = _support_document()
    working = build_session_working_map(
        base_eq_map_card={"equilibrium_networks": []},
        support_document=support,
    )
    audit = validate_session_working_map(
        working,
        base_eq_map_card={"equilibrium_networks": []},
        support_document=support,
    )

    assert working == {
        "pairs": [{
            "metal_id": 61,
            "ligand_id": 11422,
            "selected_network_ids": [],
            "estimated_eq_nodes": adapted_rows_by_pair(support)[(61, 11422)],
        }]
    }
    assert audit["n_existing_pairs_patched"] == 0
    assert audit["n_new_pairs_constructed"] == 1


@pytest.mark.parametrize(
    ("node_db_id", "vlm_id", "query_id", "message"),
    [
        (4_000_001, -5_000_001, "q001", "negative session"),
        (-4_000_001, -5_000_001, "", "lacks query_id"),
    ],
)
def test_session_ids_and_query_provenance_fail_closed(
    node_db_id: int,
    vlm_id: int,
    query_id: str,
    message: str,
) -> None:
    support = _support_document(
        node_db_id=node_db_id,
        vlm_id=vlm_id,
        query_id=query_id,
    )
    working = build_session_working_map(
        base_eq_map_card={"equilibrium_networks": []},
        support_document=support,
    )
    with pytest.raises(SessionWorkingMapValidationError, match=message):
        validate_session_working_map(
            working,
            base_eq_map_card={"equilibrium_networks": []},
            support_document=support,
        )


def test_stage4_validates_before_publishing_working_map_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    support = _support_document()
    events: list[str] = []
    real_build = stage4.build_session_working_map

    monkeypatch.setattr(
        stage4,
        "assemble_support_eq_map",
        lambda **_kwargs: (copy.deepcopy(support), {-4_000_001: {}}),
    )

    def fake_validate(_document: object) -> dict:
        events.append("native_validate")
        return {"n_nodes": 1}

    def observed_build(**kwargs: object) -> dict:
        events.append("working_map_build")
        return real_build(**kwargs)

    monkeypatch.setattr(stage4, "validate_support_eq_map", fake_validate)
    monkeypatch.setattr(stage4, "build_session_working_map", observed_build)

    result = stage4.run_validate_support_eq_map(
        parsed_queries=[],
        base_eq_map_card={"equilibrium_networks": []},
        output_dir=tmp_path,
        session_id="session-working-map-test",
        request_T_C=25.0,
        request_I_M=0.1,
    )

    assert events[:2] == ["native_validate", "native_validate"]
    assert events.index("working_map_build") > events.index("native_validate")
    assert result.session_working_map_path is not None
    working_path = Path(result.session_working_map_path)
    assert working_path.is_file()
    assert result.session_working_map_sha256 == hashlib.sha256(
        working_path.read_bytes()
    ).hexdigest()
    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    assert manifest["session_working_map_path"] == str(working_path)
    assert manifest["session_working_map_sha256"] == result.session_working_map_sha256


def test_stage4_candidate_failure_has_parser_repair_diagnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = SimpleNamespace(query_id="q007", scope={"metal_id": 61, "ligand_id": 11422})
    monkeypatch.setattr(
        stage4,
        "assemble_support_eq_map",
        lambda **_kwargs: (_ for _ in ()).throw(
            ValueError("q007: parsed pair does not match query scope")
        ),
    )

    with pytest.raises(stage4.SupportEqMapMaterializationError) as caught:
        stage4.run_validate_support_eq_map(
            parsed_queries=[query],
            base_eq_map_card={"equilibrium_networks": []},
            output_dir=tmp_path,
            session_id="repair-diagnostic-test",
        )

    diagnostic = caught.value.as_dict()
    assert diagnostic["query_id"] == "q007"
    assert diagnostic["pair_scope"] == {"metal_id": 61, "ligand_id": 11422}
    assert diagnostic["parser_correctable"] is True
    assert diagnostic["fix_hints"]


def test_working_map_failure_is_attributed_to_one_pair_in_multi_query_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queries = [
        SimpleNamespace(query_id="q001", scope={"metal_id": 61, "ligand_id": 9825}),
        SimpleNamespace(query_id="q002", scope={"metal_id": 61, "ligand_id": 11422}),
    ]
    support = _support_document(query_id="q002")
    monkeypatch.setattr(
        stage4,
        "assemble_support_eq_map",
        lambda **_kwargs: (copy.deepcopy(support), {-4_000_001: {}}),
    )
    monkeypatch.setattr(stage4, "validate_support_eq_map", lambda _doc: {"n_nodes": 1})
    monkeypatch.setattr(
        stage4,
        "build_session_working_map",
        lambda **_kwargs: (_ for _ in ()).throw(
            SessionWorkingMapValidationError(
                "beta definition mismatch for metal_61/ligand_11422"
            )
        ),
    )

    with pytest.raises(stage4.SupportEqMapMaterializationError) as caught:
        stage4.run_validate_support_eq_map(
            parsed_queries=queries,
            base_eq_map_card={"equilibrium_networks": []},
            output_dir=tmp_path,
            session_id="multi-query-attribution-test",
        )

    diagnostic = caught.value.as_dict()
    assert diagnostic["query_id"] == "q002"
    assert diagnostic["pair_scope"] == {"metal_id": 61, "ligand_id": 11422}
    assert diagnostic["parser_correctable"] is True
    assert diagnostic["cause_type"].startswith("working_map:")
