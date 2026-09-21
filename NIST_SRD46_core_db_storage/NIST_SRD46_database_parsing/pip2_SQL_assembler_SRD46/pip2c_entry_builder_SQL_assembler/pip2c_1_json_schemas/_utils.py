"""
Shared utilities for SRD46 schema builders.

This module contains common helper classes and functions used across
all schema builder modules.
"""
from __future__ import annotations

from typing import Any, Dict, List


class MissingFieldTracker:
    """Collects counts of missing/empty/invalid fields per class.

    Usage
    - Pass an instance to create_* / update_* helpers.
    - Call .as_dict() or .summary_text() to get a report.
    """

    def __init__(self) -> None:
        # structure: { class_name: { field_name: {"missing": int, "empty": int, "invalid": int} } }
        self._counts: Dict[str, Dict[str, Dict[str, int]]] = {}

    def _ensure(self, class_name: str, field_name: str) -> Dict[str, int]:
        cn = self._counts.setdefault(class_name, {})
        return cn.setdefault(field_name, {"missing": 0, "empty": 0, "invalid": 0})

    def mark_missing(self, class_name: str, field_name: str) -> None:
        self._ensure(class_name, field_name)["missing"] += 1

    def mark_empty(self, class_name: str, field_name: str) -> None:
        self._ensure(class_name, field_name)["empty"] += 1

    def mark_invalid(self, class_name: str, field_name: str) -> None:
        self._ensure(class_name, field_name)["invalid"] += 1

    def merge(self, other: "MissingFieldTracker") -> None:
        for cls, fields in other._counts.items():
            for f, reasons in fields.items():
                tgt = self._ensure(cls, f)
                for k, v in reasons.items():
                    tgt[k] = tgt.get(k, 0) + v

    def reset(self) -> None:
        self._counts.clear()

    def as_dict(self) -> Dict[str, Dict[str, Dict[str, int]]]:
        return {cls: {f: reasons.copy() for f, reasons in fields.items()} for cls, fields in self._counts.items()}

    def summary_text(self) -> str:
        lines: List[str] = ["Missing/Empty/Invalid field report:"]
        for cls in sorted(self._counts.keys()):
            lines.append(f"- {cls}:")
            for f in sorted(self._counts[cls].keys()):
                r = self._counts[cls][f]
                total = r.get("missing", 0) + r.get("empty", 0) + r.get("invalid", 0)
                lines.append(
                    f"    • {f}: total={total} (missing={r.get('missing',0)}, empty={r.get('empty',0)}, invalid={r.get('invalid',0)})"
                )
        return "\n".join(lines)


# A default tracker that can be shared if one isn't provided explicitly
DEFAULT_MISSING_TRACKER = MissingFieldTracker()


# Simple in-memory cache for JSON files loaded from disk. Keyed by absolute path.
_JSON_CACHE: Dict[str, Any] = {}


def _is_empty(value: Any) -> bool:
    """Define 'empty' for the purposes of data quality reporting.

    - None is empty
    - "" (after str() and strip) is empty
    - empty list/dict/set/tuple are empty
    - numeric 0 is NOT empty
    """
    if value is None:
        return True
    if isinstance(value, (list, dict, set, tuple)):
        return len(value) == 0
    if isinstance(value, str):
        return value.strip() == ""
    return False


def _load_json_like(obj: Any) -> Any:
    """Utility: accept a path, JSON string, dict, or already-parsed object and return a dict/list/object.

    - If obj is a str and os.path.exists(obj): load file as JSON
    - If obj is a str that looks like JSON, attempt json.loads
    - If obj is a dict/list, return as-is
    - Otherwise return obj
    """
    try:
        import os as _os, json as _json
        # Cache file-path loads to avoid repeated open/parse of the same file.
        if isinstance(obj, str):
            # path on disk
            if _os.path.exists(obj):
                abspath = _os.path.abspath(obj)
                cached = _JSON_CACHE.get(abspath)
                if cached is not None:
                    return cached
                with open(abspath, "r", encoding="utf-8") as fh:
                    parsed = _json.load(fh)
                try:
                    _JSON_CACHE[abspath] = parsed
                except Exception:
                    # If caching fails for any reason, still return parsed object
                    pass
                return parsed
            # maybe a JSON string
            s = obj.strip()
            if s.startswith("{") or s.startswith("["):
                try:
                    return _json.loads(s)
                except Exception:
                    return obj
        # already a mapping or list
        if isinstance(obj, (dict, list)):
            return obj
    except Exception:
        pass
    return obj


# Convenience: public debugging helpers
def get_missing_field_report(tracker: MissingFieldTracker | None = None) -> Dict[str, Dict[str, Dict[str, int]]]:
    """Return the aggregated missing/empty/invalid counts as a dict."""
    return (tracker or DEFAULT_MISSING_TRACKER).as_dict()


def get_missing_field_report_text(tracker: MissingFieldTracker | None = None) -> str:
    """Return a human-readable summary of missing field counts."""
    return (tracker or DEFAULT_MISSING_TRACKER).summary_text()


__all__ = [
    "MissingFieldTracker",
    "DEFAULT_MISSING_TRACKER",
    "_is_empty",
    "_load_json_like",
    "_JSON_CACHE",
    "get_missing_field_report",
    "get_missing_field_report_text",
]
