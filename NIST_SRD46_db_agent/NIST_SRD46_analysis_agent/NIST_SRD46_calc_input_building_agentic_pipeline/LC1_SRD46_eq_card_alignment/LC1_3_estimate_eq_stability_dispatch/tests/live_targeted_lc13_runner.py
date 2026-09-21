"""Run one isolated, live LC1.3 system contract and verify LC2 consumption.

This is deliberately not an analysis-agent runner.  It starts at the LC1.3
prompt template, runs the pair dispatcher and parser/network gates, publishes
the native support and session-working maps, and asks the ordinary LC2.1 card
builder to consume those maps.  A prior QueryAgent result can be replayed for
the initial pair turn while any gate-requested clarification remains live.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any


THIS_FILE = Path(__file__).resolve()
WORKSPACE_ROOT = THIS_FILE.parents[6]
PIPELINE_ROOT = THIS_FILE.parents[3]
ANALYSIS_ROOT = THIS_FILE.parents[4]
CORE_NUMCALC_ROOT = ANALYSIS_ROOT / "NIST_SRD46_core_numcalc_pipeline"
for candidate in (WORKSPACE_ROOT, PIPELINE_ROOT, CORE_NUMCALC_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.LC1_3_estimate_eq_stability_dispatch_orchestrator import (  # noqa: E501
    LC13Dependencies,
    build_default_lc1_3_dependencies,
    run_lc1_3,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.dispatch_srd46_query.pair_scopes import (  # noqa: E501
    target_ligands,
    target_metals,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.runtime_support.runtime_models import (  # noqa: E501
    LC13Settings,
    QueryTurn,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC2_free_energy_card_building.LC2_1_card_initializer.native_support_eq_map import (  # noqa: E501
    load_native_support_eq_map,
    load_session_working_map,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC2_free_energy_card_building.LC2_1_card_initializer.LC2_1_ref_eq_card_orchestrator import (  # noqa: E501
    _system_catalog_pair_set,
    run_lc2_1,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC2_free_energy_card_building.LC2_4_card_validator._card_validation.solver_parse_check import (  # noqa: E501
    validate_card_with_solver,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.SRD46_calc_input_building_config import (  # noqa: E501
    AGENT_CONFIG,
)


PAIR_RE = re.compile(
    r"\(metal_(\d+)\).*?\(ligand_(\d+)\)",
    re.DOTALL,
)


def _winlong(path: Path | str) -> str:
    """Return a Windows extended-length path for deep run artefacts."""

    raw = os.path.abspath(os.fspath(path))
    if os.name != "nt" or raw.startswith("\\\\?\\"):
        return raw
    if raw.startswith("\\\\"):
        return "\\\\?\\UNC\\" + raw[2:]
    return "\\\\?\\" + raw


def _read_json(path: Path) -> Any:
    with open(_winlong(path), "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, value: Any) -> None:
    os.makedirs(_winlong(path.parent), exist_ok=True)
    with open(_winlong(path), "w", encoding="utf-8") as handle:
        handle.write(
            json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n"
        )


def _sha256_bytes(path: Path) -> str:
    with open(_winlong(path), "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _chemical_system(system_catalog_path: Path) -> dict[str, Any]:
    payload = _read_json(system_catalog_path)
    value = payload.get("system_catalog", {}).get("chemical_system")
    if not isinstance(value, dict):
        raise ValueError("system catalog has no system_catalog.chemical_system")
    return value


def _query_pairs(chemical_system: dict[str, Any]) -> set[tuple[int, int]]:
    return {
        (metal_id, ligand_id)
        for metal_id, _metal_name in target_metals(chemical_system)
        for ligand_id, _ligand_name in target_ligands(chemical_system)
    }


def _allowed_pairs(chemical_system: dict[str, Any]) -> set[tuple[int, int]]:
    """Use the exact production LC2.1 catalog expansion for map binding."""

    return set(_system_catalog_pair_set(chemical_system))


class ReplayInitialQueryRunner:
    """Replay immutable initial turns and keep clarification calls live."""

    def __init__(
        self,
        source_root: Path,
        live_runner: Any,
        *,
        allow_live_clarification: bool = False,
    ) -> None:
        self.live_runner = live_runner
        self.allow_live_clarification = bool(allow_live_clarification)
        self.sources: dict[tuple[int, int], dict[str, Any]] = {}
        self.events: list[dict[str, Any]] = []
        for scope_path in sorted(source_root.glob("q*/scope.json")):
            query_root = scope_path.parent
            scope = _read_json(scope_path)
            pair = (int(scope["metal_id"]), int(scope["ligand_id"]))
            context = _read_json(query_root / "full_query_agent_context.json")
            manifest = _read_json(
                query_root / "01_dispatch_srd46_query" / "turn_manifest.json"
            )
            self.sources[pair] = {
                "query_id": query_root.name,
                "query_root": str(query_root),
                "scope": scope,
                "context": context,
                "manifest": manifest,
            }

    def __call__(
        self,
        message: str,
        *,
        memory: list[dict[str, str]],
        **kwargs: Any,
    ) -> QueryTurn:
        if memory:
            if not self.allow_live_clarification:
                raise RuntimeError(
                    "replay mode is fixed to the saved QueryAgent answers; "
                    "live clarification is disabled"
                )
            started = time.perf_counter()
            turn = self.live_runner(message, memory=memory, **kwargs)
            self.events.append({
                "mode": "live_clarification",
                "prompt_sha256": _sha256_text(message),
                "elapsed_s": time.perf_counter() - started,
            })
            return turn

        match = PAIR_RE.search(message)
        if match is None:
            raise RuntimeError("cannot identify pair in rendered dispatch prompt")
        pair = (int(match.group(1)), int(match.group(2)))
        source = self.sources.get(pair)
        if source is None:
            raise RuntimeError(f"no replay source exists for pair {pair}")
        context = source["context"]
        stored_memory = list(context.get("conversation_memory") or [])
        if not stored_memory or stored_memory[0].get("role") != "user":
            raise RuntimeError(f"replay source {pair} has no initial user turn")
        original_prompt = str(stored_memory[0].get("content") or "")
        if original_prompt != message:
            raise RuntimeError(
                f"rendered prompt for {pair} is not byte-identical to replay source"
            )
        memory.extend(copy.deepcopy(stored_memory))
        manifest = source["manifest"]
        answer = str(context.get("final_answer") or "")
        self.events.append({
            "mode": "replayed_initial",
            "pair": list(pair),
            "source_query_id": source["query_id"],
            "source_query_root": source["query_root"],
            "prompt_sha256": _sha256_text(message),
            "answer_sha256": _sha256_text(answer),
            "prompt_byte_identical": True,
        })
        return QueryTurn(
            answer=answer,
            memory=memory,
            tool_history=copy.deepcopy(list(context.get("tool_history") or [])),
            compactor_events=copy.deepcopy(
                list(context.get("compactor_events") or [])
            ),
            model_history=copy.deepcopy(list(context.get("model_history") or [])),
            elapsed_s=float(
                manifest.get("elapsed_seconds", manifest.get("elapsed_s", 0.0))
                or 0.0
            ),
            timed_out=bool(manifest.get("timed_out", False)),
            error=(str(manifest.get("error") or "").strip() or None),
        )


def _estimated_equilibria(card_json: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for blocks in (card_json.get("equations") or {}).values():
        for block in blocks or []:
            for row in block.get("equilibria", []) or []:
                reference = row.get("reference") or {}
                if reference.get("source") == "SRD46 query estimated values":
                    rows.append(row)
    return rows


def _verify_solver_ready(
    *,
    result: Any,
    base_card_path: Path,
    base_card: dict[str, Any],
    chemical_system: dict[str, Any],
    system_catalog_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    allowed_pairs = _allowed_pairs(chemical_system)
    if result.status != "ok" or not result.estimation_search_complete:
        raise RuntimeError(
            "LC1.3 did not publish a complete estimated map: "
            f"status={result.status}, reason={result.reference_only_reason}"
        )
    if not result.support_eq_map_path or not result.session_working_map_path:
        raise RuntimeError("LC1.3 reported success without both published maps")

    support = load_native_support_eq_map(
        result.support_eq_map_path,
        base_eq_map_card=base_card,
        allowed_system_pairs=allowed_pairs,
        expected_support_session_id=str(result.session_id),
        expected_support_eq_map_sha256=str(result.support_eq_map_sha256),
    )
    working = load_session_working_map(
        result.session_working_map_path,
        expected_session_working_map_sha256=str(
            result.session_working_map_sha256
        ),
        support_rows_by_pair=support.rows_by_pair,
        base_eq_map_card=base_card,
        allowed_system_pairs=allowed_pairs,
    )
    lc2_output_dir = output_dir / "solver_ready_lc2_1"
    lc2_manifest = run_lc2_1(
        system_catalog_path=system_catalog_path,
        lc1_2_eqmap_card_path=base_card_path,
        output_dir=lc2_output_dir,
        test_name="targeted_support",
        auto_hydroxide=False,
        auto_pka=False,
        support_eq_map_path=result.support_eq_map_path,
        expected_support_session_id=str(result.session_id),
        expected_support_eq_map_sha256=str(result.support_eq_map_sha256),
        session_working_map_path=result.session_working_map_path,
        expected_session_working_map_sha256=str(
            result.session_working_map_sha256
        ),
    )
    card_paths = [Path(value) for value in lc2_manifest["ref_card_paths"]]
    compiled_entries: list[dict[str, Any]] = []
    for card_path in card_paths:
        json_path = Path(card_path).with_suffix(".json")
        if not os.path.exists(_winlong(json_path)):
            continue
        for row in _estimated_equilibria(_read_json(json_path)):
            notes = row.get("patch_notes") or {}
            compiled_entries.append({
                "card_json_path": str(json_path),
                "name": row.get("name"),
                "log_K": row.get("log_K"),
                "beta_definition_id": notes.get("beta_definition_id"),
                "query_id": notes.get("query_id"),
                "source": (row.get("reference") or {}).get("source"),
            })

    support_nodes = [
        {
            "pair": list(pair),
            "node_db_id": row.get("node_db_id"),
            "vlm_id": row.get("vlm_id"),
            "beta_definition_id": row.get("beta_definition_id"),
            "log_K": row.get("log_K"),
            "query_id": (row.get("_estimated_provenance") or {}).get("query_id"),
        }
        for pair, rows in sorted(support.rows_by_pair.items())
        for row in rows
    ]
    compile_manifest_path = Path(lc2_manifest["support_compile_manifest_path"])
    compile_manifest = _read_json(compile_manifest_path)
    if not support_nodes:
        raise RuntimeError("published support map contains no estimated nodes")
    if len(compiled_entries) != len(support_nodes):
        raise RuntimeError(
            "LC2 materialized a different number of estimated entries: "
            f"support={len(support_nodes)}, compiled={len(compiled_entries)}"
        )
    if int(compile_manifest.get("materialized_estimated_entry_count", -1)) != len(
        support_nodes
    ):
        raise RuntimeError("LC2 compile manifest count does not match support map")
    merged_card_path = Path(lc2_manifest["merged_card_path"])
    solver_parse = validate_card_with_solver(merged_card_path)
    if not solver_parse.ok:
        raise RuntimeError(
            "the exact numerical-solver card reader rejected the LC2.1 output: "
            + str(solver_parse.error)
        )
    solver_species = list(getattr(solver_parse.report, "species", []) or [])
    if not solver_species:
        raise RuntimeError("the solver parsed the merged card with zero species")

    return {
        "status": "pass",
        "allowed_system_pairs": [list(pair) for pair in sorted(allowed_pairs)],
        "support_node_count": support.node_count,
        "support_nodes": support_nodes,
        "working_map_pairs": [
            {
                "pair": list(pair),
                "estimated_node_count": len(rows),
            }
            for pair, rows in sorted(working.rows_by_pair.items())
        ],
        "compiled_card_paths": [str(path) for path in card_paths],
        "compiled_estimated_entry_count": len(compiled_entries),
        "compiled_estimated_entries": compiled_entries,
        "compile_manifest_path": str(compile_manifest_path),
        "lc2_1_manifest_path": str(
            Path(lc2_manifest["output_dir"]) / "lc2_1_manifest.json"
        ),
        "merged_card_path": str(merged_card_path),
        "solver_parser_ok": True,
        "solver_parser_qualname": solver_parse.parser_qualname,
        "solver_species_count": len(solver_species),
        "support_eq_map_sha256": support.sha256,
        "session_working_map_sha256": working.sha256,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-card", type=Path, required=True)
    parser.add_argument("--system-catalog", type=Path, required=True)
    parser.add_argument("--request-context", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--replay-query-root", type=Path)
    parser.add_argument(
        "--replay-allow-live-clarification",
        action="store_true",
        help="Permit a gate-requested live follow-up after replayed first turns.",
    )
    parser.add_argument("--temperature-c", type=float, default=25.0)
    parser.add_argument("--ionic-strength-m", type=float, default=0.1)
    parser.add_argument("--query-timeout-s", type=float, default=180.0)
    parser.add_argument("--parser-timeout-s", type=float, default=120.0)
    parser.add_argument("--clarification-timeout-s", type=float, default=120.0)
    parser.add_argument(
        "--verify-existing",
        action="store_true",
        help="Skip all agents and verify the existing lc1_3/LC1_3_manifest.json.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    status_path = output_dir / "targeted_test_status.json"
    replay_runner: ReplayInitialQueryRunner | None = None
    try:
        base_card = _read_json(args.base_card)
        chemical_system = _chemical_system(args.system_catalog)
        request = _read_json(args.request_context)
        settings = LC13Settings.from_config(AGENT_CONFIG)
        settings = replace(
            settings,
            max_query_runs=max(1, len(_query_pairs(chemical_system))),
            query_timeout_s=float(args.query_timeout_s),
            parser_timeout_s=float(args.parser_timeout_s),
            query_clarification_total_timeout_s=float(
                args.clarification_timeout_s
            ),
        )
        if args.verify_existing:
            manifest_path = output_dir / "lc1_3" / "LC1_3_manifest.json"
            manifest = _read_json(manifest_path)
            result = SimpleNamespace(
                status=manifest.get("status"),
                estimation_search_complete=bool(
                    manifest.get("estimation_search_complete")
                ),
                reference_only_reason=manifest.get("reference_only_reason"),
                support_eq_map_path=manifest.get("support_eq_map_path"),
                session_working_map_path=manifest.get(
                    "session_working_map_path"
                ),
                session_id=manifest.get("session_id"),
                support_eq_map_sha256=manifest.get("support_eq_map_sha256"),
                session_working_map_sha256=manifest.get(
                    "session_working_map_sha256"
                ),
                estimated_stability_constants=list(
                    manifest.get("estimated_stability_constants") or []
                ),
                manifest_path=str(manifest_path),
            )
            solver_ready = _verify_solver_ready(
                result=result,
                base_card_path=args.base_card.resolve(),
                base_card=base_card,
                chemical_system=chemical_system,
                system_catalog_path=args.system_catalog.resolve(),
                output_dir=output_dir,
            )
            _write_json(output_dir / "solver_ready_check.json", solver_ready)
            if status_path.exists():
                _write_json(
                    output_dir / "targeted_test_preverification_status.json",
                    _read_json(status_path),
                )
            status = {
                "status": "pass",
                "execution_mode": "verify_existing",
                "elapsed_s": time.perf_counter() - started,
                "lc1_3_manifest_path": str(manifest_path),
                "support_eq_map_path": result.support_eq_map_path,
                "session_working_map_path": result.session_working_map_path,
                "estimated_stability_constants": (
                    result.estimated_stability_constants
                ),
                "solver_ready_check_path": str(
                    output_dir / "solver_ready_check.json"
                ),
            }
            _write_json(status_path, status)
            print("TARGETED_LC13_VERIFY_PASS " + json.dumps(status), flush=True)
            return 0
        dependencies = build_default_lc1_3_dependencies(settings)
        if args.replay_query_root is not None:
            replay_runner = ReplayInitialQueryRunner(
                args.replay_query_root.resolve(),
                dependencies.query_runner,
                allow_live_clarification=args.replay_allow_live_clarification,
            )
            dependencies = LC13Dependencies(
                query_runner=replay_runner,
                query_system_prompt=dependencies.query_system_prompt,
                parser_runner=dependencies.parser_runner,
                catalog=dependencies.catalog,
            )

        input_manifest = {
            "execution_scope": "isolated LC1_3 only",
            "base_card_path": str(args.base_card.resolve()),
            "base_card_sha256": _sha256_bytes(args.base_card),
            "system_catalog_path": str(args.system_catalog.resolve()),
            "system_catalog_sha256": _sha256_bytes(args.system_catalog),
            "request_context_path": str(args.request_context.resolve()),
            "request_context_sha256": _sha256_bytes(args.request_context),
            "replay_query_root": (
                None
                if args.replay_query_root is None
                else str(args.replay_query_root.resolve())
            ),
            "replay_allow_live_clarification": bool(
                args.replay_allow_live_clarification
            ),
            "temperature_C": args.temperature_c,
            "ionic_strength_M": args.ionic_strength_m,
            "settings": settings.__dict__,
        }
        _write_json(output_dir / "targeted_test_input.json", input_manifest)
        print(
            "TARGETED_LC13_START "
            + json.dumps({
                "output_dir": str(output_dir),
                "query_pairs": sorted(_query_pairs(chemical_system)),
                "catalog_pairs": sorted(_allowed_pairs(chemical_system)),
                "replay": args.replay_query_root is not None,
            }),
            flush=True,
        )
        result = run_lc1_3(
            base_eq_map_card=base_card,
            target_chemical_system=chemical_system,
            purpose=str(request.get("purpose") or ""),
            tasks=str(request.get("tasks") or ""),
            chemical_context_plan=request.get("chemical_context_plan"),
            request_T_C=float(args.temperature_c),
            request_I_M=float(args.ionic_strength_m),
            output_dir=output_dir / "lc1_3",
            settings=settings,
            dependencies=dependencies,
        )
        print(
            "TARGETED_LC13_PUBLISHED "
            + json.dumps({
                "status": result.status,
                "complete": result.estimation_search_complete,
                "estimates": len(result.estimated_stability_constants or []),
            }),
            flush=True,
        )
        solver_ready = _verify_solver_ready(
            result=result,
            base_card_path=args.base_card.resolve(),
            base_card=base_card,
            chemical_system=chemical_system,
            system_catalog_path=args.system_catalog.resolve(),
            output_dir=output_dir,
        )
        _write_json(output_dir / "solver_ready_check.json", solver_ready)
        status = {
            "status": "pass",
            "elapsed_s": time.perf_counter() - started,
            "lc1_3_manifest_path": result.manifest_path,
            "support_eq_map_path": result.support_eq_map_path,
            "session_working_map_path": result.session_working_map_path,
            "estimated_stability_constants": result.estimated_stability_constants,
            "solver_ready_check_path": str(
                output_dir / "solver_ready_check.json"
            ),
            "replay_events": [] if replay_runner is None else replay_runner.events,
        }
        _write_json(status_path, status)
        print("TARGETED_LC13_PASS " + json.dumps(status), flush=True)
        return 0
    except BaseException as exc:
        status = {
            "status": "failed",
            "elapsed_s": time.perf_counter() - started,
            "error": f"{type(exc).__name__}: {exc}",
            "replay_events": [] if replay_runner is None else replay_runner.events,
        }
        _write_json(status_path, status)
        print("TARGETED_LC13_FAIL " + json.dumps(status), flush=True)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
