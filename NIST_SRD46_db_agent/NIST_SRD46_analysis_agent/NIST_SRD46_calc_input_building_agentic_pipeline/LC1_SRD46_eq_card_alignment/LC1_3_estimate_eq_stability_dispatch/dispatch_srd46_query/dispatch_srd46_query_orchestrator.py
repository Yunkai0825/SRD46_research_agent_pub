"""Dispatch exactly one ordinary SRD-46 chemistry query per canonical pair."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..runtime_support.artifacts import (
    mkdir,
    read_text,
    record_query_turn,
    sha256_text,
    write_json,
    write_text,
)
from ..runtime_support.runtime_models import (
    LC13Settings,
    QueryRunner,
    QuerySession,
    normalize_query_turn,
)
from .evidence_receipts import build_evidence_receipt_snapshot
from .query_agent_runtime import get_query_agent_system_prompt


@dataclass
class DispatchResult:
    sessions: list[QuerySession]
    manifest_path: str

    @property
    def dispatched_sessions(self) -> list[QuerySession]:
        return list(self.sessions)

    def as_dict(self) -> dict[str, Any]:
        return {
            "manifest_path": self.manifest_path,
            "queries": [
                {
                    "query_id": row.query_id,
                    "scope": row.scope,
                    "dispatched": row.dispatch_turn is not None,
                    "answer_sha256": (
                        sha256_text(row.dispatch_turn.answer)
                        if row.dispatch_turn is not None else None
                    ),
                    "artifact_dir": str(row.artifact_dir),
                }
                for row in self.sessions
            ],
        }


def _scope_name_id_pairs(scope: dict[str, Any], entity: str) -> str:
    """Render adjacent canonical name/ID pairs from a single or list scope.

    Normal LC1.3 execution supplies exactly one metal and one ligand per scope.
    Parallel ``*_name_list`` and ``*_id_list`` values are accepted for explicit
    multi-identity queries, but they must be nonempty and positionally aligned.
    """

    singular_name_key = f"{entity}_name"
    singular_id_key = f"{entity}_id"
    list_name_key = f"{entity}_name_list"
    list_id_key = f"{entity}_id_list"
    uses_list_scope = list_name_key in scope or list_id_key in scope

    if uses_list_scope:
        if list_name_key not in scope or list_id_key not in scope:
            raise ValueError(
                f"{list_name_key} and {list_id_key} must be supplied together"
            )
        raw_names = scope[list_name_key]
        raw_ids = scope[list_id_key]
        names = list(raw_names) if isinstance(raw_names, (list, tuple)) else [raw_names]
        identifiers = list(raw_ids) if isinstance(raw_ids, (list, tuple)) else [raw_ids]
    else:
        if singular_name_key not in scope or singular_id_key not in scope:
            raise ValueError(
                f"scope must supply either {singular_name_key}/{singular_id_key} "
                f"or {list_name_key}/{list_id_key}"
            )
        names = [scope[singular_name_key]]
        identifiers = [scope[singular_id_key]]

    if not names or len(names) != len(identifiers):
        raise ValueError(
            f"{entity} names and SRD-46 ids must be nonempty aligned lists"
        )

    pairs: list[str] = []
    for raw_name, raw_identifier in zip(names, identifiers):
        name = str(raw_name).strip()
        if not name:
            raise ValueError(f"{entity} names cannot be empty")
        if isinstance(raw_identifier, bool):
            raise ValueError(f"{entity} SRD-46 ids must be integers")
        try:
            identifier = int(raw_identifier)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{entity} SRD-46 ids must be integers") from exc
        pairs.append(f"{name} ({entity}_{identifier})")
    return "; ".join(pairs)


def _render_prompt(
    *,
    purpose: str,
    scope: dict[str, Any],
    request_T_C: float,
    request_I_M: float,
    chemical_context_plan: str | None = None,
    tasks: str | None = None,
    settings: LC13Settings | None = None,
) -> str:
    """Render only the single chemistry-question paragraph."""

    del chemical_context_plan, tasks, settings
    template = read_text(
        Path(__file__).with_name("dispatch_query_prompt.md"),
        encoding="utf-8",
    )
    rendered = template.format(
        purpose=purpose or "(not supplied)",
        metal_name_id_pairs=_scope_name_id_pairs(scope, "metal"),
        ligand_name_id_pairs=_scope_name_id_pairs(scope, "ligand"),
        temperature=float(request_T_C),
        ionic_strength=float(request_I_M),
    ).strip()
    if "\n" in rendered or "\r" in rendered:
        raise ValueError("dispatch_query_prompt.md must contain exactly one paragraph")
    return rendered


def run_dispatch_srd46_query(
    *,
    sessions: list[QuerySession],
    purpose: str,
    tasks: str,
    chemical_context_plan: str | None,
    request_T_C: float,
    request_I_M: float,
    output_dir: str | Path,
    settings: LC13Settings,
    query_runner: QueryRunner,
    query_system_prompt: str | None = None,
) -> DispatchResult:
    """Run one fresh, unrestricted standard-tool query for every pair scope."""

    requested_T_C = float(request_T_C)
    requested_I_M = float(request_I_M)
    if not math.isfinite(requested_T_C):
        raise ValueError("request_T_C must be finite")
    if not math.isfinite(requested_I_M) or requested_I_M < 0.0:
        raise ValueError("request_I_M must be finite and nonnegative")
    root = Path(output_dir)
    system_prompt = (
        get_query_agent_system_prompt(settings)
        if query_system_prompt is None
        else str(query_system_prompt)
    )

    for session in sessions:
        if session.request_T_C is None or session.request_I_M is None:
            session.request_T_C = requested_T_C
            session.request_I_M = requested_I_M
        elif not math.isclose(
            float(session.request_T_C), requested_T_C,
            rel_tol=0.0, abs_tol=1e-6,
        ) or not math.isclose(
            float(session.request_I_M), requested_I_M,
            rel_tol=0.0, abs_tol=1e-12,
        ):
            raise RuntimeError(
                f"{session.query_id}: query conditions differ from its pair scope"
            )

        prompt = _render_prompt(
            purpose=purpose,
            scope=session.scope,
            request_T_C=requested_T_C,
            request_I_M=requested_I_M,
            chemical_context_plan=chemical_context_plan,
            tasks=tasks,
            settings=settings,
        )
        memory: list[dict[str, str]] = []
        session.memory = memory
        query_dir = session.artifact_dir / "01_dispatch_srd46_query"
        mkdir(query_dir, parents=True, exist_ok=True)
        # Persist the exact model inputs before entering the remote call.  A
        # hard timeout or runner exception must still leave an auditable pair
        # prompt rather than an apparently undispatched empty directory.
        write_text(query_dir / "user_prompt.md", prompt, encoding="utf-8")
        write_text(query_dir / "system_prompt.md", system_prompt, encoding="utf-8")
        try:
            turn = normalize_query_turn(query_runner(
                prompt,
                memory=memory,
                timeout=settings.query_timeout_s,
                max_tool_iterations=settings.query_max_iterations,
            ))
        except Exception as exc:
            write_json(query_dir / "dispatch_failure.json", {
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
                "user_prompt_sha256": sha256_text(prompt),
                "system_prompt_sha256": sha256_text(system_prompt),
            })
            raise
        if turn.memory is not memory:
            raise RuntimeError(
                f"{session.query_id}: query agent replaced its fresh memory object"
            )
        session.dispatch_turn = turn
        record_query_turn(
            turn_dir=query_dir,
            user_prompt=prompt,
            system_prompt=system_prompt,
            turn=turn,
        )
        initial_failure: str | None = None
        if turn.timed_out:
            initial_failure = "query agent reported a timeout"
        elif turn.error:
            initial_failure = f"query agent reported an error: {turn.error}"
        elif not str(turn.answer or "").strip():
            initial_failure = "query agent returned an empty answer"
        if initial_failure is not None:
            write_json(query_dir / "dispatch_failure.json", {
                "status": "failed",
                "error": initial_failure,
                "timed_out": bool(turn.timed_out),
                "runner_error": turn.error,
                "answer_nonempty": bool(str(turn.answer or "").strip()),
                "user_prompt_sha256": sha256_text(prompt),
                "system_prompt_sha256": sha256_text(system_prompt),
            })
            raise RuntimeError(f"{session.query_id}: {initial_failure}")

        receipts = build_evidence_receipt_snapshot(
            tool_history=turn.tool_history,
            scope=session.scope,
            authorization_context_id=session.query_id,
        )
        # The field retains its historical name until all persisted support-map
        # readers migrate; the artifact describes its true post-hoc semantics.
        session.evidence_authorization = receipts
        receipt_path = session.artifact_dir / "evidence_receipts.json"
        write_json(receipt_path, receipts)
        transcript = turn.answer.strip() + "\n"
        write_json(session.artifact_dir / "full_query_agent_context.json", {
            "query_id": session.query_id,
            "scope": session.scope,
            "requested_conditions": {
                "temperature_C": requested_T_C,
                "ionic_strength_M": requested_I_M,
            },
            "conversation_memory": session.memory,
            "tool_history": turn.tool_history,
            "model_history": turn.model_history,
            "compactor_events": turn.compactor_events,
            "evidence_receipts_path": str(receipt_path),
            "evidence_receipts": receipts,
            "parser_source_transcript": transcript,
            "parser_source_transcript_sha256": sha256_text(transcript),
            "final_answer": turn.answer,
            "final_answer_sha256": sha256_text(turn.answer),
        })

    manifest = {
        "stage": "dispatch_srd46_query",
        "execution_contract": "one fresh query-agent call per pair scope",
        "n_sessions": len(sessions),
        "n_dispatched": sum(row.dispatch_turn is not None for row in sessions),
        "queries": [
            {
                "query_id": row.query_id,
                "dispatched": row.dispatch_turn is not None,
                "answer_sha256": (
                    sha256_text(row.dispatch_turn.answer)
                    if row.dispatch_turn is not None else None
                ),
                "artifact_dir": str(row.artifact_dir),
                "evidence_receipts_path": str(
                    row.artifact_dir / "evidence_receipts.json"
                ),
            }
            for row in sessions
        ],
    }
    manifest_path = root / "02_dispatch_srd46_query_manifest.json"
    write_json(manifest_path, manifest)
    return DispatchResult(sessions=sessions, manifest_path=str(manifest_path))


__all__ = [
    "DispatchResult",
    "run_dispatch_srd46_query",
]
