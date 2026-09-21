from __future__ import annotations

from types import SimpleNamespace

from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC2_free_energy_card_building.LC2_4_card_validator._card_validation import (  # noqa: E501
    solver_parse_check as check,
)


def test_solver_parser_bootstrap_includes_pipeline_package_root(monkeypatch) -> None:
    roots = [check._NUMCALC_ROOT, check._PIPELINE_ROOT, check._CARD_HELPERS]
    for root in roots:
        while str(root) in check.sys.path:
            check.sys.path.remove(str(root))

    sentinel = object()
    monkeypatch.setattr(
        check.importlib,
        "import_module",
        lambda name: SimpleNamespace(resolve_card_source=sentinel),
    )

    assert check._load_resolve_card_source() is sentinel
    assert all(str(root) in check.sys.path for root in roots if root.exists())
