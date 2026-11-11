"""Filesystem-only long-path handling; never use these forms in agent context."""
from __future__ import annotations

import os
from pathlib import Path


def display_path(path: str | Path) -> Path:
    """Return a normal native path without Windows' extended-length prefix."""
    text = os.fspath(path)
    if text.startswith("\\\\?\\UNC\\"):
        text = "\\\\" + text[8:]
    elif text.startswith("\\\\?\\"):
        text = text[4:]
    return Path(text)


def filesystem_path(path: str | Path) -> Path:
    """Return an absolute extended Windows path for internal file I/O only.

    Public session paths, saved scientific paths and prompts retain their
    normal spelling. Other operating systems receive the original Path.
    """
    value = Path(path)
    if os.name != "nt":
        return value
    text = os.fspath(value)
    if text.startswith("\\\\?\\"):
        return value
    text = str(value.absolute())
    if text.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + text[2:])
    return Path("\\\\?\\" + text)
