"""Long-path-safe artifact helpers for LC1.3 query sessions."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, TypeAlias

from .runtime_models import QuerySession, QueryTurn


PathLike: TypeAlias = str | os.PathLike[str]


def logical_path(path: PathLike) -> Path:
    """Return an ordinary logical path, stripping Windows I/O prefixes."""

    raw = os.fspath(path)
    if os.name != "nt":
        return Path(raw)
    extended_unc = "\\\\?\\UNC\\"
    broken_unc = "\\?\\UNC\\"
    extended_local = "\\\\?\\"
    broken_local = "\\?\\"
    while True:
        previous = raw
        if raw.startswith(extended_unc):
            raw = "\\\\" + raw[len(extended_unc):]
        elif raw.startswith(broken_unc):
            raw = "\\\\" + raw[len(broken_unc):]
        elif raw.startswith(extended_local):
            raw = raw[len(extended_local):]
        elif raw.startswith(broken_local):
            raw = raw[len(broken_local):]
        if raw == previous:
            break
    return Path(raw)


def _io_path(path: PathLike) -> Path:
    candidate = logical_path(path)
    if os.name != "nt":
        return candidate
    resolved = str(logical_path(candidate.resolve(strict=False)))
    if resolved.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + resolved[2:])
    return Path("\\\\?\\" + resolved)


def mkdir(
    path: PathLike,
    mode: int = 0o777,
    parents: bool = False,
    exist_ok: bool = False,
) -> None:
    _io_path(path).mkdir(mode=mode, parents=parents, exist_ok=exist_ok)


def write_text(path: PathLike, data: str, *, encoding: str = "utf-8") -> int:
    return _io_path(path).write_text(data, encoding=encoding)


def read_text(path: PathLike, *, encoding: str = "utf-8") -> str:
    return _io_path(path).read_text(encoding=encoding)


def read_bytes(path: PathLike) -> bytes:
    return _io_path(path).read_bytes()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_json(path: Path, payload: Any) -> None:
    mkdir(path.parent, parents=True, exist_ok=True)
    write_text(
        path,
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def _read_json(path: Path, default: Any) -> Any:
    return json.loads(read_text(path)) if _io_path(path).is_file() else default


def _fenced(value: str, language: str = "") -> str:
    # Preserve arbitrary model/tool text, including embedded Markdown fences.
    longest = max((len(x) for x in re.findall(r"`+", value)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}{language}\n{value}\n{fence}\n"


def _record_readable_turn(turn_dir: Path, user_prompt: str, system_prompt: str,
                          turn: QueryTurn) -> None:
    """Standalone-equivalent readable artifacts, without another agent run."""
    write_text(turn_dir / "result.md", "# Query result\n\n## User prompt\n\n" +
               _fenced(user_prompt) + "\n## System prompt\n\n" + _fenced(system_prompt) +
               "\n## Answer\n\n" + turn.answer)
    history = ["# Full tool history\n\n"]
    for index, step in enumerate(turn.tool_history, 1):
        history.append(f"## Step {index}: {step.get('tool', 'unknown')}\n\n")
        history.append(_fenced(json.dumps(step, ensure_ascii=False, indent=2, default=str), "json"))
    if not turn.tool_history:
        history.append("No tool calls were recorded.\n")
    write_text(turn_dir / "history.md", "\n".join(history))
    context = ["# Full conversation\n\n"]
    for index, message in enumerate(turn.memory, 1):
        context.append(f"## Message {index}: {message.get('role', 'unknown')}\n\n")
        context.append(_fenced(str(message.get("content", ""))))
    write_text(turn_dir / "conversation.md", "\n".join(context))
    rounds = ["# Full model history\n\n"]
    for index, entry in enumerate(turn.model_history, 1):
        rounds.append(f"## Model round {index}\n\n")
        rounds.append(_fenced(json.dumps(entry, ensure_ascii=False, indent=2, default=str), "json"))
    write_text(turn_dir / "model_history.md", "\n".join(rounds))
    raw_history = json.dumps(turn.tool_history, ensure_ascii=False, default=str)
    ids = sorted(set(re.findall(r"\b(?:metal|ligand|vlm|beta_def|network|node|collection|literature)_\d+\b", raw_history)))
    write_text(turn_dir / "ref_ids.md", "# Referenced entity IDs\n\n" +
               ("\n".join(f"- `{value}`" for value in ids) if ids else "No prefixed entity IDs were recorded.") + "\n")


def _copy_referenced_files(turn_dir: Path, history: list[dict[str, Any]]) -> None:
    """Copy explicit local file references without rewriting raw tool results."""
    candidates: set[str] = set()

    path_keys = {"artifact_path", "artifact_paths", "output_path", "output_paths",
                 "output_file", "output_files", "file_path", "export_path",
                 "generated_file", "generated_path", "artifacts", "files", "path"}

    def visit(value: Any, key: str = "") -> None:
        if isinstance(value, dict):
            for child_key, item in value.items():
                visit(item, str(child_key).lower())
        elif isinstance(value, list):
            for item in value:
                visit(item, key)
        elif isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith(("{", "[")):
                try:
                    visit(json.loads(stripped))
                except (ValueError, TypeError):
                    pass
            if key in path_keys and re.match(r"^(?:[A-Za-z]:[\\/]|\\\\|/)", stripped) and "\n" not in stripped:
                candidates.add(stripped)

    visit(history)
    records = []
    for source in sorted(candidates):
        path = logical_path(source)
        row: dict[str, Any] = {"source_path": source}
        try:
            if path.suffix.lower() in {".db", ".sqlite", ".sqlite3", ".py", ".pyc"}:
                row["status"] = "external_database_or_code_reference"
            elif not _io_path(path).is_file():
                row["status"] = "missing_or_not_a_file"
            else:
                data = read_bytes(path)
                digest = hashlib.sha256(data).hexdigest()
                target = turn_dir / "referenced_files" / f"{digest[:16]}_{path.name}"
                mkdir(target.parent, parents=True, exist_ok=True)
                _io_path(target).write_bytes(data)
                row.update(status="copied", sha256=digest,
                           local_path=target.relative_to(turn_dir).as_posix())
        except (OSError, ValueError) as exc:
            # Artifact failures must not turn a native returned query into a
            # scientific rejection. Preserve the missing-copy evidence.
            row.update(status="copy_failed", error_type=type(exc).__name__)
        records.append(row)
    write_json(turn_dir / "referenced_files.json", {
        "scope": "Explicit generated/output file references in recorded tool results; databases/code and ordinary scientific source references are not copied. Raw results are unchanged.",
        "files": records,
    })


def next_query_followup_directory(session: QuerySession) -> tuple[Path, int]:
    """Allocate by persisted attempts, not the number of accepted answers."""
    root = session.artifact_dir / "query_agent_followups"
    indices = []
    if _io_path(root).is_dir():
        for path in _io_path(root).glob("followup_*"):
            match = re.fullmatch(r"followup_(\d+)", path.name)
            if match:
                indices.append(int(match.group(1)))
    index = max(indices, default=0) + 1
    directory = root / f"followup_{index:02d}"
    mkdir(directory, parents=True, exist_ok=False)
    return directory, index


def record_query_context(session: QuerySession) -> dict[str, Any]:
    """Refresh the aggregate from durable turn snapshots, including failures."""
    root = session.artifact_dir
    turn_dirs = [root / "01_dispatch_srd46_query"]
    followup_root = root / "query_agent_followups"
    if _io_path(followup_root).is_dir():
        turn_dirs.extend(followup_root / p.name for p in sorted(_io_path(followup_root).glob("followup_*")))
    summaries, all_tools, all_models, all_compaction = [], [], [], []
    latest_memory, latest_answer = [], ""
    for directory in turn_dirs:
        manifest = _read_json(directory / "turn_manifest.json", None)
        failure = _read_json(directory / "query_failure.json", None)
        if manifest is None and failure is None:
            continue
        canonical = _read_json(directory / "query_turn.json", None)
        if canonical is None:
            canonical = _read_json(directory / "partial_query_state.json", _read_json(directory / "runtime_state.json", {}))
        tools = canonical.get("tool_history", _read_json(directory / "tool_history.json", []))
        models = canonical.get("model_history", _read_json(directory / "model_history.json", []))
        all_tools.extend(tools)
        all_models.extend(models)
        all_compaction.extend(_read_json(directory / "compactor_events.json", []))
        latest_memory = canonical.get("memory", _read_json(directory / "memory.json", latest_memory))
        answer_path = directory / "answer.md"
        latest_answer = canonical.get("answer", read_text(answer_path) if _io_path(answer_path).is_file() else "")
        # logical_path strips extended Windows prefixes for portable local links.
        relative = logical_path(directory).relative_to(logical_path(root)).as_posix()
        summaries.append({"artifact_dir": relative, "manifest": manifest,
                          "failure": failure, "answer": latest_answer})
    initial_failed = _io_path(root / "01_dispatch_srd46_query" / "query_failure.json").is_file()
    accepted_turns = ([session.dispatch_turn] if session.dispatch_turn is not None and not initial_failed else []) + list(session.followup_turns)
    transcript = "\n\n".join(turn.answer.strip() for turn in accepted_turns if turn.answer.strip())
    payload = {
        "query_id": session.query_id, "scope": session.scope,
        "requested_conditions": {"temperature_C": session.request_T_C, "ionic_strength_M": session.request_I_M},
        "conversation_memory": latest_memory, "tool_history": all_tools,
        "model_history": all_models, "compactor_events": all_compaction,
        "evidence_receipts_path": str(root / "evidence_receipts.json"),
        "evidence_receipts": dict(session.evidence_authorization or {}),
        "parser_source_transcript": transcript,
        "parser_source_transcript_sha256": sha256_text(transcript),
        "final_answer": latest_answer, "final_answer_sha256": sha256_text(latest_answer),
        "accepted_final_answer": accepted_turns[-1].answer if accepted_turns else "",
        "turns": summaries, "latest_turn_failed": bool(summaries and summaries[-1]["failure"]),
        "aggregation_contract": "All recorded initial/followup turns; failed returns remain artifacts and do not become accepted parser evidence.",
    }
    write_json(root / "full_query_agent_context.json", payload)
    return payload


def record_query_failure(*, turn_dir: Path, code: str, message: str,
                         memory: list[dict[str, str]], elapsed_s: float) -> None:
    mkdir(turn_dir, parents=True, exist_ok=True)
    # Preserve the returned memory snapshot if one was already exported.
    if not _io_path(turn_dir / "memory.json").is_file():
        write_json(turn_dir / "memory.json", memory)
    if not _io_path(turn_dir / "query_turn.json").is_file():
        partial = _read_json(turn_dir / "runtime_state.json", {})
        partial.setdefault("memory", memory)
        write_json(turn_dir / "partial_query_state.json", partial)
        for key in ("memory", "tool_history", "model_history", "compactor_events"):
            write_json(turn_dir / f"{key}.json", partial.get(key, []))
        _record_readable_turn(
            turn_dir, read_text(turn_dir / "user_prompt.md"), read_text(turn_dir / "system_prompt.md"),
            QueryTurn(answer=str(partial.get("answer", "")), memory=partial["memory"],
                      tool_history=partial.get("tool_history", []), model_history=partial.get("model_history", []),
                      compactor_events=partial.get("compactor_events", []), error=message),
        )
        _copy_referenced_files(turn_dir, partial.get("tool_history", []))
        result_path = turn_dir / "result.md"
        write_text(result_path, "**Incomplete query: no normal return was received.**\n\n" + read_text(result_path))
    write_json(turn_dir / "query_failure.json", {
        "status": "failed", "code": code, "message": message, "elapsed_s": elapsed_s,
    })


def record_query_turn(
    *,
    turn_dir: Path,
    user_prompt: str,
    system_prompt: str,
    turn: QueryTurn,
) -> dict[str, Any]:
    """Persist the complete context exposed by the query-agent runtime."""

    mkdir(turn_dir, parents=True, exist_ok=True)
    write_text(turn_dir / "user_prompt.md", user_prompt, encoding="utf-8")
    write_text(turn_dir / "system_prompt.md", system_prompt, encoding="utf-8")
    write_text(turn_dir / "answer.md", turn.answer, encoding="utf-8")
    write_json(turn_dir / "memory.json", turn.memory)
    write_json(turn_dir / "tool_history.json", turn.tool_history)
    write_json(turn_dir / "compactor_events.json", turn.compactor_events)
    write_json(turn_dir / "model_history.json", turn.model_history)
    write_json(turn_dir / "query_turn.json", {
        "answer": turn.answer, "memory": turn.memory,
        "tool_history": turn.tool_history, "model_history": turn.model_history,
        "compactor_events": turn.compactor_events, "elapsed_s": turn.elapsed_s,
        "timed_out": bool(turn.timed_out), "error": turn.error,
        "output_budget": getattr(turn, "output_budget", None),
        "user_prompt": user_prompt, "system_prompt": system_prompt,
    })
    _record_readable_turn(turn_dir, user_prompt, system_prompt, turn)
    _copy_referenced_files(turn_dir, turn.tool_history)
    manifest = {
        "answer_sha256": sha256_text(turn.answer),
        "user_prompt_sha256": sha256_text(user_prompt),
        "system_prompt_sha256": sha256_text(system_prompt),
        "memory_turns": len(turn.memory),
        "tool_calls": len(turn.tool_history),
        "model_rounds": len(turn.model_history),
        "elapsed_s": turn.elapsed_s,
        "timed_out": bool(turn.timed_out),
        "error": turn.error,
        "answer_nonempty": bool(str(turn.answer or "").strip()),
        # Usage/stop record of the answer round; output_truncated True means
        # the answer stopped at the QueryAgent output cap.
        "output_budget": getattr(turn, "output_budget", None),
    }
    write_json(turn_dir / "turn_manifest.json", manifest)
    return manifest


__all__ = [
    "logical_path",
    "mkdir",
    "read_bytes",
    "read_text",
    "record_query_turn",
    "record_query_context",
    "record_query_failure",
    "next_query_followup_directory",
    "sha256_text",
    "write_json",
    "write_text",
]
