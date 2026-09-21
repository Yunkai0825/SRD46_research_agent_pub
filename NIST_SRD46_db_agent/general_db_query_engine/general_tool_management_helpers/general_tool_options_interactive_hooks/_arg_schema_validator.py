"""
Argument-schema batch validator — generic malformed-arg pre-execution react.
============================================================================
A ``batch_validator``-contract callable for the ``SYNC_BATCH_PRE_VALIDATE``
anchor.  It validates every tool call in a batch (single calls included)
against the *real* function signature BEFORE execution:

* **Auto-fixes** unambiguous mistakes in place (mutating the call's
  ``arguments`` dict) so no turn is wasted:
  - ``arguments`` emitted as a JSON string → parsed to an object;
  - dict/list passed where a ``str`` param is annotated → ``json.dumps``;
  - scalars passed where ``str`` is annotated → ``str(value)``;
  - numeric strings / integral floats where ``int``/``float`` annotated;
  - ``"true"/"false"/0/1`` where ``bool`` annotated.
* **Blocks** with an actionable per-tool report when a call is malformed
  in a way that cannot be fixed mechanically:
  - ``arguments`` is not a JSON object at all;
  - unknown parameter names that signature/alias/case matching cannot
    place (``_normalize_args`` would silently DROP them, so the tool
    would run with defaults — the classic silent-typo failure);
  - values whose type contradicts a simple annotation and cannot be
    coerced (e.g. a dict where a number is expected).

Missing parameters are deliberately NOT checked — tools in this codebase
declare defaults and produce their own domain errors for empty inputs.
The scope here is strictly *malformed* calls.

The returned report follows the ``validate_batch`` format contract that
``react_loop`` parses (``**✗ name**`` markers), so blocked tools get
per-tool ``[validation blocked]`` history entries and the agent can fix
the arguments and re-submit — or drop the call and try different tools.
"""

from __future__ import annotations

import inspect
import json
import logging
import typing
from typing import Any, Callable, Mapping

_log = logging.getLogger(__name__)

_P = inspect.Parameter

_SIMPLE_TYPES = (str, int, float, bool)


def _resolve_param_name(
    tool_name: str,
    key: str,
    valid_params: set[str],
) -> str | None:
    """Mirror ``_normalize_args`` name resolution; None = would be dropped."""
    if key in valid_params:
        return key
    # Alias maps live next to _normalize_args; import lazily to avoid
    # a circular import at module load time.
    from ...general_argo_engine_helpers.engine_react_helpers.react_helpers import (
        _PARAM_ALIASES,
    )
    alias = _PARAM_ALIASES.get((tool_name, key)) or _PARAM_ALIASES.get(("*", key))
    if alias and alias in valid_params:
        return alias
    key_lower = key.lower()
    for p in valid_params:
        if p.lower() == key_lower:
            return p
    return None


def _unwrap_annotation(annotation: Any) -> type | None:
    """Return the simple target type of an annotation, or None to skip.

    Handles plain types, ``Optional[T]`` / ``Union[T, None]`` and
    string annotations (``from __future__ import annotations``).
    Anything more complex returns None (no type enforcement).
    """
    if annotation is _P.empty or annotation is None:
        return None
    if isinstance(annotation, str):
        cleaned = annotation.replace("Optional[", "").rstrip("]").strip()
        return {t.__name__: t for t in _SIMPLE_TYPES}.get(cleaned)
    origin = typing.get_origin(annotation)
    if origin is typing.Union:
        non_none = [a for a in typing.get_args(annotation) if a is not type(None)]
        if len(non_none) == 1:
            annotation = non_none[0]
        else:
            return None
    if annotation in _SIMPLE_TYPES:
        return annotation
    return None


def _coerce_value(target: type, value: Any) -> tuple[bool, Any, str]:
    """Try to coerce *value* to *target* type.

    Returns ``(ok, coerced_value, problem)``.  ``ok`` False means the
    value is malformed and cannot be fixed mechanically; ``problem``
    then describes the mismatch.
    """
    if target is str:
        if isinstance(value, str):
            return True, value, ""
        if isinstance(value, (dict, list)):
            return True, json.dumps(value), ""
        if isinstance(value, (int, float, bool)):
            return True, str(value), ""
        return False, value, f"expected a string, got {type(value).__name__}"
    if target is bool:
        if isinstance(value, bool):
            return True, value, ""
        if isinstance(value, int) and value in (0, 1):
            return True, bool(value), ""
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in ("true", "yes", "1"):
                return True, True, ""
            if lowered in ("false", "no", "0"):
                return True, False, ""
        return False, value, f"expected a boolean, got {value!r}"
    if target is int:
        if isinstance(value, bool):
            return True, int(value), ""
        if isinstance(value, int):
            return True, value, ""
        if isinstance(value, float) and value.is_integer():
            return True, int(value), ""
        if isinstance(value, str):
            try:
                return True, int(value.strip()), ""
            except ValueError:
                pass
        return False, value, f"expected an integer, got {value!r}"
    if target is float:
        if isinstance(value, bool):
            return False, value, f"expected a number, got {value!r}"
        if isinstance(value, (int, float)):
            return True, float(value), ""
        if isinstance(value, str):
            try:
                return True, float(value.strip()), ""
            except ValueError:
                pass
        return False, value, f"expected a number, got {value!r}"
    return True, value, ""  # pragma: no cover — filtered by _unwrap_annotation


def _check_one_call(
    tc: dict,
    tools: Mapping[str, Callable[..., Any]],
) -> list[str]:
    """Validate/auto-fix ONE tool call in place; return problem lines."""
    tool_name = str(tc.get("name") or "")
    fn = tools.get(tool_name)
    if fn is None:
        return []  # unknown tool → the execution path reports it with the tool list

    args = tc.get("arguments", {})

    # arguments emitted as a JSON string → parse (auto-fix)
    if isinstance(args, str):
        try:
            parsed = json.loads(args)
        except (json.JSONDecodeError, TypeError):
            parsed = None
        if isinstance(parsed, dict):
            args = parsed
            tc["arguments"] = args
            _log.info("Arg validator: parsed JSON-string arguments for %s", tool_name)
        else:
            return [
                "`arguments` must be a JSON object "
                f"({{\"param\": value, ...}}), got the string {args[:80]!r}."
            ]
    if args is None:
        args = {}
        tc["arguments"] = args
    if not isinstance(args, dict):
        return [
            "`arguments` must be a JSON object "
            f"({{\"param\": value, ...}}), got {type(args).__name__}."
        ]

    try:
        sig = inspect.signature(fn)
    except (ValueError, TypeError):
        return []
    params = sig.parameters
    if any(p.kind == _P.VAR_KEYWORD for p in params.values()):
        return []  # **kwargs tools accept anything
    valid_params = {
        n for n, p in params.items()
        if p.kind not in (_P.VAR_POSITIONAL, _P.POSITIONAL_ONLY)
    }

    problems: list[str] = []
    fixed: dict[str, Any] = {}
    for key, value in args.items():
        resolved = _resolve_param_name(tool_name, key, valid_params)
        if resolved is None:
            accepted = ", ".join(f"`{n}`" for n in sorted(valid_params)) or "(none)"
            problems.append(
                f"unknown parameter `{key}` (would be silently dropped). "
                f"Accepted parameters: {accepted}."
            )
            continue

        target = _unwrap_annotation(params[resolved].annotation)
        if target is None:
            fixed[resolved] = value
            continue
        if value is None:
            problems.append(
                f"parameter `{resolved}` got null — pass a {target.__name__} "
                "or omit the argument to use its default."
            )
            continue
        ok, coerced, problem = _coerce_value(target, value)
        if not ok:
            problems.append(f"parameter `{resolved}`: {problem}.")
            continue
        if coerced is not value:
            _log.info(
                "Arg validator: coerced %s.%s from %s to %s",
                tool_name, resolved, type(value).__name__, target.__name__,
            )
        fixed[resolved] = coerced

    if not problems:
        tc["arguments"] = fixed
    return problems


def validate_batch_args(
    tool_calls: list[dict],
    tools: Mapping[str, Callable[..., Any]],
    *,
    hooks: Any = None,
) -> str | None:
    """Batch-validator contract entry point (single calls included).

    Auto-fixes what it can in place.  Returns ``None`` when every call
    is well-formed (execution proceeds), or a per-tool guidance report
    (execution is skipped; the agent corrects and re-submits).
    """
    del hooks
    blocked: list[tuple[str, list[str]]] = []
    ready: list[str] = []
    for tc in tool_calls:
        name = str(tc.get("name") or "?")
        problems = _check_one_call(tc, tools)
        if problems:
            blocked.append((name, problems))
        else:
            ready.append(name)

    if not blocked:
        return None

    parts: list[str] = []
    for name, problems in blocked:
        detail = "\n".join(f"- {p}" for p in problems)
        parts.append(f"**\u2717 {name}** — needs correction:\n{detail}")
    if ready:
        parts.append(
            f"**\u2713 {', '.join(ready)}** — well-formed "
            "(held back by the batch)"
        )
    parts.append(
        "_Fix the malformed argument(s) and re-submit the corrected tool "
        "call(s), or drop them and re-submit only the well-formed ones._"
    )
    return "\n\n".join(parts)


__all__ = ["validate_batch_args"]
