from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest


_THIS = Path(__file__).resolve()
_PIPELINE_ROOT = _THIS.parents[3]
_ANALYSIS_ROOT = _THIS.parents[4]
_WORKSPACE_ROOT = _THIS.parents[6]
for _path in (_WORKSPACE_ROOT, _PIPELINE_ROOT, _ANALYSIS_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from LC2_free_energy_card_building.LC2_1_card_initializer.native_support_eq_map import (
    SessionWorkingMapError,
    amend_measured_working_map,
    load_session_working_map,
)


def _estimated_row() -> dict:
    return {
        "node_db_id": -4_000_001,
        "vlm_id": -5_000_001,
        "constant_type": "K",
        "log_K": 1.25,
        "temperature": 25.0,
        "ionic_strength": 0.1,
        "equation_python": "[M] + [L] <=> [ML]",
        "beta_definition_id": 812,
        "beta_definition_name": "[ML]/[M][L]",
        "metal_id": 61,
        "ligand_id": 11422,
        "LHS_species_json": [
            {"species": "[L]", "power": 1, "phase": "aqueous"},
            {"species": "[M]", "power": 1, "phase": "aqueous"},
        ],
        "RHS_species_json": [
            {"species": "[ML]", "power": 1, "phase": "aqueous"},
        ],
        "_estimated_provenance": {
            "source": "SRD46 query estimated values",
            "query_id": "q001",
            "session_vlm_id": -5_000_001,
            "evidence_vlm_ids": ["vlm_95941"],
        },
    }


def _write_map(path: Path, payload: dict) -> str:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_lc2_verifies_and_consumes_lc1_session_working_map(tmp_path: Path) -> None:
    row = _estimated_row()
    published_payload = {
        "pairs": [{
            "metal_id": 61,
            "ligand_id": 11422,
            "selected_network_ids": [678],
            "estimated_eq_nodes": [row],
        }]
    }
    published_path = tmp_path / "session_working_eq_map.json"
    digest = _write_map(published_path, published_payload)
    base_card = {
        "equilibrium_networks": [{
            "metal_id": "metal_61",
            "ligand_id": "ligand_11422",
            "eq_network": "ref_eq_net_678",
        }]
    }

    loaded = load_session_working_map(
        published_path,
        expected_session_working_map_sha256=digest,
        support_rows_by_pair={(61, 11422): [row]},
        base_eq_map_card=base_card,
        allowed_system_pairs={(61, 11422)},
    )
    measured_path = tmp_path / "reviewed_maps.json"
    reviewed_payload = {
        "pairs": [{
            "metal_id": 61,
            "ligand_id": 11422,
            "selected_network_ids": [678],
            "vlm_overrides": [{"beta_definition_id": 17, "action": "drop_node"}],
        }]
    }
    measured_path.write_text(json.dumps(reviewed_payload, indent=2), encoding="utf-8")
    with pytest.raises(ValueError, match="must not overwrite"):
        amend_measured_working_map(
            maps_json_path=measured_path,
            metal_id=61,
            ligand_id=11422,
            estimated_rows=list(loaded.rows_by_pair[(61, 11422)]),
            output_path=measured_path,
        )
    output_path = tmp_path / "maps_with_estimates.json"
    amend_measured_working_map(
        maps_json_path=measured_path,
        metal_id=61,
        ligand_id=11422,
        estimated_rows=list(loaded.rows_by_pair[(61, 11422)]),
        output_path=output_path,
    )

    assert json.loads(measured_path.read_text(encoding="utf-8")) == reviewed_payload
    consumed = json.loads(output_path.read_text(encoding="utf-8"))
    assert consumed["pairs"][0]["selected_network_ids"] == [678]
    assert consumed["pairs"][0]["vlm_overrides"] == reviewed_payload["pairs"][0]["vlm_overrides"]
    assert consumed["pairs"][0]["estimated_eq_nodes"] == [row]


def test_lc2_rejects_stale_or_tampered_session_working_map(tmp_path: Path) -> None:
    row = _estimated_row()
    path = tmp_path / "session_working_eq_map.json"
    digest = _write_map(path, {
        "pairs": [{
            "metal_id": 61,
            "ligand_id": 11422,
            "selected_network_ids": [],
            "estimated_eq_nodes": [row],
        }]
    })
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(SessionWorkingMapError, match="SHA-256"):
        load_session_working_map(
            path,
            expected_session_working_map_sha256=digest,
            support_rows_by_pair={(61, 11422): [row]},
            base_eq_map_card={"equilibrium_networks": []},
            allowed_system_pairs={(61, 11422)},
        )
