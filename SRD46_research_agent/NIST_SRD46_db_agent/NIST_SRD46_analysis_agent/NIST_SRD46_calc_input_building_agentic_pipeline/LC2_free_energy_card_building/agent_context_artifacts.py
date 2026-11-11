"""Lossless, self-describing audit artifacts for every LC2 agent turn."""

from __future__ import annotations

import inspect
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


SCHEMA_VERSION = 1
CONTEXT_MANIFEST_NAME = "agent_context_manifest.json"
REQUIRED_CONTEXT_FILE_KEYS = frozenset({
    "system_prompt",
    "user_message",
    "memory",
    "tool_registry",
    "answer",
    "final_context",
    "tool_calls",
})


def _display_path(path: Path) -> str:
    """Drive-letter absolute form for records.

    ``.absolute()`` — never ``.resolve()`` — so Windows mapped drives are not
    rewritten into their ~30-character-longer UNC form (which pushed deep
    LC2_3 bundle manifests over MAX_PATH and silently dropped them).  Any
    ``\\\\?\\`` long-path prefix used for I/O is stripped from the record.
    """
    text = str(path.absolute())
    if text.startswith("\\\\?\\UNC\\"):
        return "\\\\" + text[8:]
    if text.startswith("\\\\?\\"):
        return text[4:]
    return text


def _io_path(path: Path, *, force: bool = False) -> Path:
    """Long-path-safe handle for file I/O on Windows.

    Windows file APIs reject drive-letter paths at/over 260 characters unless
    they carry the ``\\\\?\\`` extended prefix.  Deep LC2_3 audit trees
    (session dir + generation + group slug + manifest name) legitimately
    cross that line, so every read/write in this module routes through here.
    ``force=True`` prefixes even short paths — required for recursive walks,
    where a short root must still descend into over-limit subdirectories
    (children of a prefixed root inherit the prefix).
    """
    if os.name != "nt":
        return path
    text = str(path.absolute())
    if text.startswith("\\\\?\\") or (len(text) < 250 and not force):
        return path
    if text.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + text[2:])
    return Path("\\\\?\\" + text)


def _write_text(path: Path, value: Any) -> None:
    _io_path(path).write_text(
        str(value if value is not None else ""), encoding="utf-8"
    )


def _file_record(path: Path) -> dict[str, Any]:
    data = _io_path(path).read_bytes()
    return {
        "path": _display_path(path),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _context_bundle_complete(payload: Mapping[str, Any]) -> bool:
    """Verify that a context manifest still resolves to its recorded files."""
    context = payload.get("context")
    if not isinstance(context, Mapping):
        return False
    files = context.get("files")
    integrity = context.get("file_integrity")
    if not isinstance(files, Mapping) or not isinstance(integrity, Mapping):
        return False
    if not REQUIRED_CONTEXT_FILE_KEYS.issubset(files):
        return False
    for key, raw_path in files.items():
        record = integrity.get(key)
        if not isinstance(raw_path, str) or not isinstance(record, Mapping):
            return False
        path = Path(raw_path)
        if not _io_path(path).is_file():
            return False
        try:
            current = _file_record(path)
        except OSError:
            return False
        if (
            current["path"] != record.get("path")
            or current["bytes"] != record.get("bytes")
            or current["sha256"] != record.get("sha256")
        ):
            return False
    return True


def verify_agent_context_manifest(manifest_path: str | Path) -> bool:
    """Return whether one persisted context manifest and all child files agree."""
    try:
        payload = json.loads(
            _io_path(Path(manifest_path)).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return False
    return _context_bundle_complete(payload)


def _tool_registry(tools: Mapping[str, Callable]) -> str:
    lines = [
        "# Available tools",
        "",
        "The exact tool instructions are also part of `system_prompt.md`. This "
        "registry records the callable names, signatures, and docstrings exposed "
        "for this turn.",
        "",
    ]
    for name, fn in tools.items():
        try:
            signature = str(inspect.signature(fn))
        except (TypeError, ValueError):
            signature = "(...)"
        lines.extend((
            f"## `{name}{signature}`",
            "",
            (inspect.getdoc(fn) or "_(no docstring)_"),
            "",
        ))
    return "\n".join(lines)


def write_agent_context_bundle(
    out_dir: str | Path,
    *,
    stage_id: str,
    stage_label: str,
    role: str,
    phase: str,
    system_prompt: str,
    user_message: str,
    tools: Mapping[str, Callable],
    required_tools: Sequence[str],
    memory: Sequence[Mapping[str, Any]],
    result: Any = None,
    error: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    runtime: Mapping[str, Any] | None = None,
) -> Path:
    """Persist exact supplied context and complete audit-visible turn results.

    This function is intentionally best-effort at call sites, but when it
    succeeds it never truncates prompts, tool arguments, or tool results.
    Internal model-reasoning fields are deliberately excluded; they are not
    part of the agent's supplied context or its controller-consumed output.
    """
    out = Path(out_dir)
    _io_path(out).mkdir(parents=True, exist_ok=True)

    files = {
        "system_prompt": "system_prompt.md",
        "user_message": "user_message.md",
        "memory": "memory.json",
        "tool_registry": "tool_registry.md",
        "answer": "agent_answer.md",
        "final_context": "final_context.md",
        "tool_calls": "tool_calls.json",
        "compatibility_response": "agent_response.md",
    }
    _write_text(out / files["system_prompt"], system_prompt)
    _write_text(out / files["user_message"], user_message)
    _io_path(out / files["memory"]).write_text(
        json.dumps(list(memory), indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    _write_text(out / files["tool_registry"], _tool_registry(tools))

    answer = getattr(result, "answer", "") if result is not None else ""
    final_context = (
        getattr(result, "final_context", "") if result is not None else ""
    )
    raw_tool_history = list(
        (getattr(result, "tool_history", []) if result is not None else []) or []
    )
    tool_history = [
        {key: value for key, value in dict(row).items() if key != "reasoning"}
        for row in raw_tool_history
    ]
    _write_text(out / files["answer"], answer)
    _write_text(out / files["final_context"], final_context)
    _io_path(out / files["tool_calls"]).write_text(
        json.dumps(tool_history, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    _write_text(
        out / files["compatibility_response"],
        f"# {stage_label} agent response\n\n"
        "## Final answer (text emitted by the agent)\n\n"
        f"{answer or '_(empty)_'}\n\n"
        "## Final context\n\n"
        f"{final_context or '_(empty)_'}\n",
    )
    file_paths = {
        key: _display_path(out / name) for key, name in files.items()
    }
    file_integrity = {
        key: _file_record(out / name) for key, name in files.items()
    }

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "LC2 agent context",
        "stage_id": stage_id,
        "stage_label": stage_label,
        "role": role,
        "phase": phase,
        "context": {
            "fresh_context": len(memory) == 0,
            "memory_message_count": len(memory),
            "available_tools": list(tools),
            "required_tools": sorted(set(required_tools)),
            "files": file_paths,
            "file_integrity": file_integrity,
            "audit_boundary": (
                "Exact controller-supplied context and audit-visible outputs; "
                "private model reasoning is neither supplied context nor exported."
            ),
        },
        "result": {
            "status": "error" if error else "completed",
            "error": error,
            "audit_scope": (
                "returned_turn_context_and_results"
                if result is not None
                else "initial_context_and_controller_exception_only"
            ),
            "iterations": int(getattr(result, "iterations", 0) or 0),
            "elapsed_seconds": float(
                getattr(result, "elapsed_seconds", 0.0) or 0.0
            ),
            "timed_out": bool(getattr(result, "timed_out", False)),
            "tool_call_count": len(tool_history),
        },
        "runtime": {
            "argo_api_user": (
                os.environ.get("SRD46_ANALYSIS_ARGO_API_USER")
                or os.environ.get("ARGO_API_USER")
            ),
            **dict(runtime or {}),
        },
        "metadata": dict(metadata or {}),
    }
    manifest_path = out / CONTEXT_MANIFEST_NAME
    _io_path(manifest_path).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return manifest_path


def write_agent_context_index(root: str | Path) -> tuple[Path, Path]:
    """Index every context bundle below *root* in JSON and Markdown."""
    base = Path(root)
    manifests = []
    # Walk via the force-prefixed handle so bundles whose manifest path
    # crosses MAX_PATH are still enumerated and readable (a short root
    # cannot otherwise descend into over-limit subdirectories).
    for path in sorted(_io_path(base, force=True).rglob(CONTEXT_MANIFEST_NAME)):
        try:
            payload = json.loads(_io_path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        manifests.append({
            "manifest_path": _display_path(path),
            "stage_id": payload.get("stage_id"),
            "stage_label": payload.get("stage_label"),
            "role": payload.get("role"),
            "phase": payload.get("phase"),
            "status": (payload.get("result") or {}).get("status"),
            "tool_call_count": (payload.get("result") or {}).get(
                "tool_call_count"
            ),
            "fresh_context": (payload.get("context") or {}).get(
                "fresh_context"
            ),
            "bundle_complete": _context_bundle_complete(payload),
        })

    complete_count = sum(bool(item["bundle_complete"]) for item in manifests)

    json_path = base / "agent_context_index.json"
    md_path = base / "agent_context_index.md"
    json_path.write_text(
        json.dumps({
            "schema_version": SCHEMA_VERSION,
            "artifact_kind": "LC2 agent context index",
            "root": _display_path(base),
            "agent_turn_count": len(manifests),
            "complete_agent_turn_count": complete_count,
            "all_context_bundles_complete": complete_count == len(manifests),
            "agent_turns": manifests,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    lines = [
        "# LC2 agent-context index",
        "",
        "Each row points to an audit bundle containing the exact system prompt, "
        "user message, initial memory, tool registry, full tool calls/results, "
        "agent answer, and final accumulated context for one agent turn.",
        "",
        f"Bundle integrity: **{complete_count}/{len(manifests)} complete**.",
        "",
        "| stage | role | phase | status | fresh | bundle | tools | manifest |",
        "|-------|------|-------|--------|-------|--------|------:|----------|",
    ]
    for item in manifests:
        lines.append(
            f"| {item['stage_id']} | {item['role']} | {item['phase']} "
            f"| {item['status']} | {str(item['fresh_context']).lower()} "
            f"| {str(item['bundle_complete']).lower()} "
            f"| {item['tool_call_count']} | `{item['manifest_path']}` |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


__all__ = [
    "CONTEXT_MANIFEST_NAME",
    "REQUIRED_CONTEXT_FILE_KEYS",
    "verify_agent_context_manifest",
    "write_agent_context_bundle",
    "write_agent_context_index",
]
