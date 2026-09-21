"""LC1.3 direct-query, answer-parser, and deterministic publication flow."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...SRD46_calc_input_building_config import AGENT_CONFIG
from .runtime_support.artifacts import logical_path, mkdir, write_json
from .dispatch_srd46_query.dispatch_srd46_query_orchestrator import (
    run_dispatch_srd46_query,
)
from .dispatch_srd46_query.pair_scopes import run_prepare_pair_scopes
from .parse_speciation_answer.parse_speciation_answer_orchestrator import (
    run_parse_speciation_answer,
)
from .parse_speciation_answer.srd46_catalog import Catalog
from .dispatch_srd46_query.query_agent_runtime import (
    get_query_agent_system_prompt,
    run_query_agent,
)
from .runtime_support.runtime_models import LC13Settings, ParserRunner, QueryRunner
from .validate_support_eq_map.validate_support_eq_map_orchestrator import (
    SupportEqMapMaterializationError,
    run_validate_support_eq_map,
)


@dataclass(frozen=True)
class LC13Dependencies:
    query_runner: QueryRunner
    query_system_prompt: str
    parser_runner: ParserRunner | None = None
    catalog: Catalog | None = None


@dataclass
class LC13Result:
    status: str
    output_dir: str
    support_eq_map_path: str | None
    manifest_path: str
    pair_scope: dict[str, Any]
    dispatch: dict[str, Any]
    parse: dict[str, Any]
    validate: dict[str, Any]
    withheld_support_eq_map_path: str | None = None
    session_id: str | None = None
    support_eq_map_sha256: str | None = None
    estimation_search_complete: bool = True
    reference_only_reason: str | None = None
    failure_summary: dict[str, Any] | None = None
    estimated_stability_constants: list[dict[str, Any]] | None = None
    repair_coordinator: dict[str, Any] | None = None
    session_working_map_path: str | None = None
    session_working_map_sha256: str | None = None
    withheld_session_working_map_path: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "output_dir": self.output_dir,
            "support_eq_map_path": self.support_eq_map_path,
            "manifest_path": self.manifest_path,
            "pair_scope": self.pair_scope,
            "dispatch": self.dispatch,
            "parse": self.parse,
            "validate": self.validate,
            "withheld_support_eq_map_path": self.withheld_support_eq_map_path,
            "session_id": self.session_id,
            "support_eq_map_sha256": self.support_eq_map_sha256,
            "estimation_search_complete": self.estimation_search_complete,
            "reference_only_reason": self.reference_only_reason,
            "failure_summary": self.failure_summary,
            "estimated_stability_constants": list(
                self.estimated_stability_constants or []
            ),
            "repair_coordinator": dict(self.repair_coordinator or {}),
            "session_working_map_path": self.session_working_map_path,
            "session_working_map_sha256": self.session_working_map_sha256,
            "withheld_session_working_map_path": (
                self.withheld_session_working_map_path
            ),
        }


@dataclass
class _FailedSupportValidation:
    error: str
    manifest_path: str
    status: str = "reference_only"
    support_eq_map_path: str | None = None
    empty_support_eq_map_path: str | None = None
    support_eq_map_sha256: str | None = None
    session_working_map_path: str | None = None
    session_working_map_sha256: str | None = None
    audit: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "support_eq_map_path": None,
            "empty_support_eq_map_path": None,
            "support_eq_map_sha256": None,
            "session_working_map_path": None,
            "session_working_map_sha256": None,
            "manifest_path": self.manifest_path,
            "audit": dict(self.audit or {}),
            "error": self.error,
        }


def build_default_lc1_3_dependencies(
    settings: LC13Settings | None = None,
) -> LC13Dependencies:
    """Bind the standard query agent and isolated answer parser lazily."""

    effective = settings or LC13Settings.from_config(AGENT_CONFIG)
    query_system_prompt = get_query_agent_system_prompt(effective)
    # LC1.3 embeds the otherwise-standalone QueryAgent.  Resolve its model at
    # this analysis-owned boundary so a hand-built settings object with an
    # empty query_model cannot fall through to the QueryAgent application's
    # independent argo_config.MODEL default.
    query_model = str(effective.query_model or "").strip()
    if not query_model:
        query_model = str(AGENT_CONFIG.MODEL or "").strip()
    if not query_model:
        raise ValueError(
            "LC1.3 embedded QueryAgent requires a non-empty analysis model"
        )

    def configured_query_runner(*args: Any, **kwargs: Any) -> Any:
        return run_query_agent(
            *args,
            model=query_model,
            system_prompt_override=query_system_prompt,
            **kwargs,
        )

    return LC13Dependencies(
        query_runner=configured_query_runner,
        query_system_prompt=query_system_prompt,
        parser_runner=None,
    )


def _validate_with_parser_repairs(
    *,
    parsed: Any,
    sessions: list[Any],
    base_eq_map_card: dict[str, Any],
    root: Path,
    session_id: str,
    request_T_C: float,
    request_I_M: float,
    settings: LC13Settings,
    catalog: Catalog | None = None,
) -> tuple[Any, dict[str, Any] | None, list[dict[str, Any]]]:
    """Independently re-run publication validation after parser-gate commit.

    Parser correction and QueryAgent clarification now happen before commit in
    the revisioned parser workspace.  Stage 4 is deliberately an independent,
    single fail-closed check rather than a second hidden parser continuation.
    """

    del sessions, settings
    attempts: list[dict[str, Any]] = []
    try:
        validated = run_validate_support_eq_map(
            parsed_queries=parsed.parsed_queries,
            base_eq_map_card=base_eq_map_card,
            output_dir=root,
            session_id=session_id,
            request_T_C=request_T_C,
            request_I_M=request_I_M,
            catalog=catalog,
        )
        attempts.append({"attempt": 1, "status": "pass"})
        return validated, None, attempts
    except SupportEqMapMaterializationError as exc:
        diagnostic = exc.as_dict()
        attempts.append({"attempt": 1, "diagnostic": diagnostic})
        return None, {
            "kind": "support_eq_map_validation_failure",
            **diagnostic,
            "repair_action": "reference_only",
            "interpretation": (
                "Independent publication validation disagreed with the "
                "already committed parser/network gate."
            ),
        }, attempts
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        attempts.append({"attempt": 1, "error": error})
        return None, {
            "kind": "support_eq_map_validation_failure",
            "error": error,
            "repair_action": "reference_only",
            "parser_correctable": False,
        }, attempts


def run_lc1_3(
    *,
    base_eq_map_card: dict[str, Any],
    target_chemical_system: dict[str, Any],
    purpose: str,
    tasks: str,
    chemical_context_plan: str | None,
    request_T_C: float,
    request_I_M: float,
    output_dir: str | Path,
    settings: LC13Settings | None = None,
    dependencies: LC13Dependencies | None = None,
) -> LC13Result:
    """Run scoping, initial queries, gated parsing/clarification, and publication."""

    root = logical_path(output_dir)
    mkdir(root, parents=True, exist_ok=True)
    effective = settings or LC13Settings.from_config(AGENT_CONFIG)
    deps = dependencies or build_default_lc1_3_dependencies(effective)
    session_id = uuid.uuid4().hex

    pair_scope = run_prepare_pair_scopes(
        base_eq_map_card=base_eq_map_card,
        target_chemical_system=target_chemical_system,
        purpose=purpose,
        tasks=tasks,
        chemical_context_plan=chemical_context_plan,
        output_dir=root,
        settings=effective,
        request_T_C=request_T_C,
        request_I_M=request_I_M,
    )
    dispatch = run_dispatch_srd46_query(
        sessions=pair_scope.sessions,
        purpose=purpose,
        tasks=tasks,
        chemical_context_plan=chemical_context_plan,
        request_T_C=request_T_C,
        request_I_M=request_I_M,
        output_dir=root,
        settings=effective,
        query_runner=deps.query_runner,
        query_system_prompt=deps.query_system_prompt,
    )
    parsed = run_parse_speciation_answer(
        sessions=dispatch.sessions,
        output_dir=root,
        settings=effective,
        base_eq_map_card=base_eq_map_card,
        session_id=session_id,
        query_runner=deps.query_runner,
        query_system_prompt=deps.query_system_prompt,
        parser_runner=deps.parser_runner,
        catalog=deps.catalog,
    )
    validated, validation_failure, materialization_attempts = (
        _validate_with_parser_repairs(
            parsed=parsed,
            sessions=dispatch.sessions,
            base_eq_map_card=base_eq_map_card,
            root=root,
            session_id=session_id,
            request_T_C=request_T_C,
            request_I_M=request_I_M,
            settings=effective,
            catalog=deps.catalog,
        )
    )
    repair_audit = dict(getattr(parsed, "repair_audit", {}) or {})
    repair_audit["support_eq_map_materialization_attempts"] = (
        materialization_attempts
    )
    if validation_failure is not None:
        failure_manifest = root / "04_validate_support_eq_map_failure.json"
        write_json(failure_manifest, {
            "stage": "validate_support_eq_map",
            "status": "reference_only",
            "materialization_attempts": materialization_attempts,
            **validation_failure,
        })
        validated = _FailedSupportValidation(
            error=str(validation_failure.get("error") or "validation failed"),
            manifest_path=str(failure_manifest),
            audit=validation_failure,
        )

    validation_audit = getattr(validated, "audit", None)
    if not isinstance(validation_audit, dict):
        validation_audit = {}
    estimated_stability_constants = list(
        validation_audit.get("estimated_stability_constants") or []
    )
    parser_failures = [
        dict(row) if isinstance(row, dict) else {"error": str(row)}
        for row in (parsed.failures or [])
    ]
    omitted_scopes = list(pair_scope.omitted_scopes)
    estimation_search_complete = (
        not parser_failures
        and not omitted_scopes
        and validation_failure is None
    )

    status = validated.status
    published_support_path = validated.support_eq_map_path
    published_support_sha256 = (
        validated.support_eq_map_sha256 if published_support_path else None
    )
    published_working_map_path = getattr(
        validated, "session_working_map_path", None
    )
    published_working_map_sha256 = (
        getattr(validated, "session_working_map_sha256", None)
        if published_working_map_path else None
    )
    withheld_support_path: str | None = None
    withheld_working_map_path: str | None = None
    reference_only_reason: str | None = None
    failure_summary: dict[str, Any] | None = None
    if not estimation_search_complete:
        if effective.failure_policy != "reference_only":
            raise ValueError(
                f"unsupported LC1_3 failure policy: {effective.failure_policy!r}"
            )
        withheld_support_path = published_support_path
        withheld_working_map_path = published_working_map_path
        published_support_path = None
        published_support_sha256 = None
        published_working_map_path = None
        published_working_map_sha256 = None
        status = "reference_only"
        reasons: list[str] = []
        if parser_failures:
            reasons.append("parser_failures")
        if omitted_scopes:
            reasons.append("scope_limit_omissions")
        if validation_failure is not None:
            reasons.append("support_eq_map_validation_failure")
        reference_only_reason = "_and_".join(reasons)
        failure_summary = {
            "kind": "incomplete_estimation_search",
            "n_parser_failures": len(parser_failures),
            "parser_failures": parser_failures,
            "n_scope_limit_omissions": len(omitted_scopes),
            "scope_limit_omissions": omitted_scopes,
            "support_eq_map_validation_failure": validation_failure,
            "repair_coordinator": repair_audit,
            "all_estimated_support_withheld": True,
            "reference_path_continued": True,
        }

    manifest = {
        "status": status,
        "estimation_enabled": True,
        "session_id": session_id,
        "source": "SRD46 query estimated values",
        "free_energy_conversion_performed": False,
        "support_eq_map_path": published_support_path,
        "support_eq_map_sha256": published_support_sha256,
        "withheld_support_eq_map_path": withheld_support_path,
        "session_working_map_path": published_working_map_path,
        "session_working_map_sha256": published_working_map_sha256,
        "withheld_session_working_map_path": withheld_working_map_path,
        "scope_limit_omissions": omitted_scopes,
        "estimation_search_complete": estimation_search_complete,
        "reference_only_reason": reference_only_reason,
        "failure_summary": failure_summary,
        "estimated_stability_constants": estimated_stability_constants,
        "repair_coordinator": repair_audit,
        "stages": {
            "prepare_pair_scopes": pair_scope.as_dict(),
            "dispatch_srd46_query": dispatch.as_dict(),
            "parse_speciation_answer": parsed.as_dict(),
            "validate_support_eq_map": validated.as_dict(),
        },
    }
    manifest_path = root / "LC1_3_manifest.json"
    write_json(manifest_path, manifest)
    return LC13Result(
        status=status,
        output_dir=str(root),
        support_eq_map_path=published_support_path,
        manifest_path=str(manifest_path),
        pair_scope=pair_scope.as_dict(),
        dispatch=dispatch.as_dict(),
        parse=parsed.as_dict(),
        validate=validated.as_dict(),
        withheld_support_eq_map_path=withheld_support_path,
        session_id=session_id,
        support_eq_map_sha256=published_support_sha256,
        estimation_search_complete=estimation_search_complete,
        reference_only_reason=reference_only_reason,
        failure_summary=failure_summary,
        estimated_stability_constants=estimated_stability_constants,
        repair_coordinator=repair_audit,
        session_working_map_path=published_working_map_path,
        session_working_map_sha256=published_working_map_sha256,
        withheld_session_working_map_path=withheld_working_map_path,
    )


__all__ = [
    "LC13Dependencies",
    "LC13Result",
    "build_default_lc1_3_dependencies",
    "run_lc1_3",
]
