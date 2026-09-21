"""Long-path-safe artifact helpers for LC1.3 query sessions."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, TypeAlias

from .runtime_models import QueryTurn


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
    }
    write_json(turn_dir / "turn_manifest.json", manifest)
    return manifest


__all__ = [
    "logical_path",
    "mkdir",
    "read_bytes",
    "read_text",
    "record_query_turn",
    "sha256_text",
    "write_json",
    "write_text",
]
