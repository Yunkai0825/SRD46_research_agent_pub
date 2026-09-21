"""Long-path helper for Windows (MAX_PATH=260 workaround).

Shared across all sweep pipelines and downstream output/plotting helpers.
"""
from __future__ import annotations
import os
import pathlib
from typing import Union


def long_path(p: Union[str, pathlib.Path]) -> str:
    """Return *p* converted to a Windows extended-length path if needed.

    On non-Windows systems (or paths already prefixed), returns ``os.fspath(p)``.
    """
    s = os.fspath(p)
    if os.name != "nt":
        return s
    if s.startswith("\\\\?\\"):
        return s
    try:
        s_abs = os.path.abspath(s)
    except Exception:
        s_abs = s
    if len(s_abs) < 240:
        return s_abs
    if s_abs.startswith("\\\\"):  # UNC
        return "\\\\?\\UNC\\" + s_abs[2:]
    return "\\\\?\\" + s_abs


def safe_mkdir(p: Union[str, pathlib.Path]) -> None:
    """``os.makedirs(long_path(p), exist_ok=True)`` — long-path safe on Windows."""
    os.makedirs(long_path(p), exist_ok=True)
