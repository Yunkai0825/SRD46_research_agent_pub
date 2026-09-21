from __future__ import annotations

from pathlib import Path

import pytest

from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.analysis_agent_orchestration.L1_subagent import (
    l1_subagent as l1,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.analysis_agent_orchestration.L1_subagent.l1_method_skills import (
    KNOWN_SWEEP_METHODS,
    canonical_method,
    get_method_briefing,
    infer_sweep_methods,
    render_method_briefing,
)


def _state(tmp_path: Path) -> l1._L1State:
    call_dir = tmp_path / "L1_call_01"
    (call_dir / "solver").mkdir(parents=True)
    l1._SESSION["session_dir"] = tmp_path
    l1._SESSION["history"] = None
    return l1._L1State(
        purpose="test system",
        tasks_text="run the requested sweep",
        call_dir=call_dir,
        idx=1,
    )


def _fake_pipeline_for(sweep_method: str, verdict: Path):
    def fake_pipeline(*_args, **_kwargs):
        return {
            "status": "ok",
            "solver": {
                "sweep_method": sweep_method,
                "output_paths": [str(verdict)],
            },
        }

    return fake_pipeline


def test_every_known_method_has_briefing() -> None:
    for method in KNOWN_SWEEP_METHODS:
        text = get_method_briefing(method)
        assert text, f"missing briefing for {method}"
        assert "## Reading hints" in text
    pourbaix = get_method_briefing("pourbaix_sweep") or ""
    assert "## Verdict schema" in pourbaix
    assert "## Canonical Topology Prefixed ID hierarchy" in pourbaix
    for family in ("Dms_i", "DmsReg_i", "DmsRegEq_i", "DmsRegEqJnc_i"):
        assert f"`{family}`" in pourbaix


def test_alias_and_unknown_method_resolution() -> None:
    assert canonical_method("pourbaix") == "pourbaix_sweep"
    assert canonical_method(" PH_SWEEP ") == "pH_sweep"
    assert get_method_briefing("pourbaix") == get_method_briefing(
        "pourbaix_sweep"
    )
    assert get_method_briefing("volume_sweep") is None
    assert render_method_briefing("") is None


def test_pipeline_result_injects_pourbaix_briefing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _state(tmp_path)
    verdict = state.call_dir / "solver" / "topology_demo_verdict.md"
    verdict.write_text("# Solver verdict\n\nVERDICT_SENTINEL\n", encoding="utf-8")
    monkeypatch.setattr(
        l1, "run_pipeline", _fake_pipeline_for("pourbaix_sweep", verdict)
    )
    tool = l1._make_run_pipeline(state)

    first = tool()
    assert "[METHOD BRIEFING — pourbaix_sweep]" in first
    assert "Never flatten the map" in first
    assert "VERDICT_SENTINEL" in first
    assert first.index("[METHOD BRIEFING") < first.index("VERDICT_SENTINEL")

    cached = tool()
    assert '"already_ran": true' in cached
    assert "[METHOD BRIEFING — pourbaix_sweep]" in cached


def test_pipeline_result_briefing_matches_method(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _state(tmp_path)
    verdict = state.call_dir / "solver" / "speciation_demo_verdict.md"
    verdict.write_text("# Solver verdict\n", encoding="utf-8")
    monkeypatch.setattr(
        l1, "run_pipeline", _fake_pipeline_for("pH_sweep", verdict)
    )
    result = l1._make_run_pipeline(state)()
    assert "[METHOD BRIEFING — pH_sweep]" in result
    assert "[METHOD BRIEFING — pourbaix_sweep]" not in result
    assert "Never flatten the map" not in result


def test_pipeline_result_without_known_method_has_no_briefing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _state(tmp_path)
    verdict = state.call_dir / "solver" / "odd_demo_verdict.md"
    verdict.write_text("# Solver verdict\n", encoding="utf-8")
    monkeypatch.setattr(l1, "run_pipeline", _fake_pipeline_for("", verdict))
    result = l1._make_run_pipeline(state)()
    assert "[METHOD BRIEFING" not in result


def test_infer_sweep_methods_from_dispatch_text() -> None:
    assert infer_sweep_methods(
        "Build the Cu–glycine Pourbaix predominance map"
    ) == ("pourbaix_sweep",)
    assert infer_sweep_methods("an Eh-pH diagram for Fe") == (
        "pourbaix_sweep",
    )
    assert infer_sweep_methods("titration of glycine with NaOH") == (
        "titration_sweep",
    )
    assert infer_sweep_methods("speciation versus pH for citrate") == (
        "pH_sweep",
    )
    # Ambiguous text names two methods; word boundaries reject substrings.
    assert set(
        infer_sweep_methods("pourbaix map, then a titration follow-up")
    ) == {"pourbaix_sweep", "titration_sweep"}
    assert infer_sweep_methods("the side-phase behavior") == ()
    assert infer_sweep_methods("") == ()


def test_system_prompt_gets_briefing_for_unambiguous_diagram_task(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    state.purpose = "Cu Pourbaix predominance map"
    state.tasks_text = "Map Cu predominance over pH 0-14 and E -1 to 1.5 V."
    prompt = l1._build_l1_system_prompt(state)
    assert "[METHOD BRIEFING — pourbaix_sweep]" in prompt
    assert "Never flatten the map" in prompt
    assert state.briefed_methods == ["pourbaix_sweep"]


def test_system_prompt_skips_briefing_for_ambiguous_task(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    state.purpose = "Pourbaix map plus titration curve"
    state.tasks_text = "Do a pourbaix sweep, then a titration sweep."
    prompt = l1._build_l1_system_prompt(state)
    # The workflow text itself mentions the literal placeholder, so assert
    # on rendered-block markers only.
    assert "[METHOD BRIEFING — pourbaix_sweep]" not in prompt
    assert "[METHOD BRIEFING — titration_sweep]" not in prompt
    assert "[END METHOD BRIEFING]" not in prompt
    assert state.briefed_methods == []


def test_pipeline_result_dedups_prebriefed_method(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _state(tmp_path)
    state.briefed_methods = ["pourbaix_sweep"]
    verdict = state.call_dir / "solver" / "topology_demo_verdict.md"
    verdict.write_text("# Solver verdict\n", encoding="utf-8")
    monkeypatch.setattr(
        l1, "run_pipeline", _fake_pipeline_for("pourbaix_sweep", verdict)
    )
    result = l1._make_run_pipeline(state)()
    assert (
        "[METHOD BRIEFING — pourbaix_sweep] is already part of your system "
        "instructions" in result
    )
    assert "Never flatten the map" not in result


def test_pipeline_result_keeps_full_briefing_on_method_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _state(tmp_path)
    state.briefed_methods = ["pourbaix_sweep"]
    verdict = state.call_dir / "solver" / "speciation_demo_verdict.md"
    verdict.write_text("# Solver verdict\n", encoding="utf-8")
    monkeypatch.setattr(
        l1, "run_pipeline", _fake_pipeline_for("pH_sweep", verdict)
    )
    result = l1._make_run_pipeline(state)()
    assert "[METHOD BRIEFING — pH_sweep]" in result
    assert "already part of your system instructions" not in result
