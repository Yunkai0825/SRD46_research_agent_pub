from __future__ import annotations

from types import SimpleNamespace

from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch import (
    LC1_3_estimate_eq_stability_dispatch_orchestrator as orchestrator,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.runtime_support.runtime_models import (
    LC13Settings,
    QueryTurn,
)
from NIST_SRD46_db_agent.NIST_SRD46_query_agent import argo_config as standalone_config


def _config(*, analysis_model: str, query_model: str) -> SimpleNamespace:
    return SimpleNamespace(
        MODEL=analysis_model,
        LC1_3_MAX_QUERY_RUNS=2,
        LC1_3_QUERY_MODEL=query_model,
        LC1_3_QUERY_MAX_ITERATIONS=3,
        LC1_3_QUERY_TIMEOUT_S=10.0,
        LC1_3_PARSER_MAX_ROUNDS=4,
        LC1_3_PARSER_TIMEOUT_S=11.0,
        LC1_3_PARSER_MODEL="parser-model",
        LC1_3_FAILURE_POLICY="reference_only",
    )


def test_blank_lc13_query_model_inherits_analysis_model() -> None:
    settings = LC13Settings.from_config(
        _config(analysis_model="analysis-opus", query_model="  ")
    )
    assert settings.query_model == "analysis-opus"


def test_explicit_lc13_query_model_wins_over_analysis_model() -> None:
    settings = LC13Settings.from_config(
        _config(analysis_model="analysis-opus", query_model="stage-opus")
    )
    assert settings.query_model == "stage-opus"


def test_embedded_runner_passes_analysis_model_without_mutating_standalone(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_run_query_agent(*args, **kwargs):
        captured.update(kwargs)
        return QueryTurn(answer="ok", memory=kwargs.get("memory", []))

    monkeypatch.setattr(orchestrator, "run_query_agent", fake_run_query_agent)
    monkeypatch.setattr(
        orchestrator, "get_query_agent_system_prompt", lambda settings: "prompt"
    )
    monkeypatch.setattr(orchestrator.AGENT_CONFIG, "MODEL", "analysis-opus")
    monkeypatch.setattr(standalone_config, "MODEL", "standalone-gpt")

    settings = LC13Settings(
        max_query_runs=2,
        query_model="",
        query_max_iterations=3,
        query_timeout_s=10.0,
        parser_max_rounds=4,
        parser_timeout_s=11.0,
        parser_model="parser-model",
        failure_policy="reference_only",
    )
    dependencies = orchestrator.build_default_lc1_3_dependencies(settings)
    dependencies.query_runner(
        "question", memory=[], timeout=10.0, max_tool_iterations=3
    )

    assert captured["model"] == "analysis-opus"
    assert standalone_config.MODEL == "standalone-gpt"

