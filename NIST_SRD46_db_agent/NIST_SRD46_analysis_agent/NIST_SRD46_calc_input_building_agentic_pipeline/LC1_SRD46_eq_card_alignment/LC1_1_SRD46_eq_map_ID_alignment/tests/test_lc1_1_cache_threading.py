from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace


_PIPELINE_ROOT = Path(__file__).resolve().parents[3]
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from LC1_SRD46_eq_card_alignment.LC1_1_SRD46_eq_map_ID_alignment import (  # noqa: E402
    LC1_1_ID_alignment_subagent as subagent,
)


def test_alignment_threads_call_local_temporary_cache_to_catalog_builder(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def fake_quick_fact_factory(state):
        def quick_fact(**_kwargs):
            state.verified.update({
                "metal_61": {"kind": "metal", "name": "Fe"},
                "ligand_11422": {"kind": "ligand", "name": "DMF"},
            })
            return "verified"
        return quick_fact

    def fake_agent_turn(_message, *, tools, **_kwargs):
        tools["quick_fact"](name="Fe and DMF")
        result = tools["commit_chemical_system"](json_payload=json.dumps({
            "metals": [{"db_id": "metal_61", "name": "Fe"}],
            "ligands": [{"db_id": "ligand_11422", "name": "DMF"}],
        }))
        assert result.startswith("OK")
        return SimpleNamespace(
            tool_history=[],
            answer="committed",
            final_context="test context",
        )

    def fake_build_system_catalog(committed, **kwargs):
        captured["committed"] = committed
        captured.update(kwargs)
        return {
            "system_catalog": {
                "chemical_system": {
                    "metals": committed["metals"],
                    "ligands": committed["ligands"],
                },
            },
        }

    monkeypatch.setattr(subagent, "_make_quick_fact", fake_quick_fact_factory)
    monkeypatch.setattr(
        subagent,
        "parse_workflow",
        lambda _path: {"system_prompt": "test"},
    )
    monkeypatch.setattr(subagent, "build_tool_instructions", lambda _tools: "")
    monkeypatch.setattr(subagent, "agent_turn", fake_agent_turn)
    monkeypatch.setattr(
        subagent,
        "SRD46AnalysisClient",
        SimpleNamespace(for_lc1_1=lambda: object()),
    )
    monkeypatch.setattr(
        subagent,
        "_build_engine_agent_hooks",
        lambda **_kwargs: SimpleNamespace(engine_hooks={}),
    )
    monkeypatch.setattr(
        subagent,
        "build_system_catalog",
        fake_build_system_catalog,
    )

    result = subagent.align_chemical_system(
        "Fe-DMF test",
        session_dir=tmp_path,
        water_system=False,
    )

    expected = (
        tmp_path
        / "LC1_1_call_01"
        / "_temporary"
        / "pubchem_free_ligand_state_cache.json"
    )
    assert captured["free_ligand_state_cache_path"] == expected
    assert captured["water_system"] is False
    assert result["system_catalog"]["chemical_system"]["ligands"] == [
        {"db_id": "ligand_11422", "name": "DMF"},
    ]
