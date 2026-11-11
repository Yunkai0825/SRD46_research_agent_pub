"""longpath_io.py
Windows long-path (>260 char MAX_PATH) safe filesystem helpers.

Deeply nested run trees (``prompt/LC2/LC2_1/<test>/_ref_cards/<long
ref-card filename>``) can exceed the legacy ``MAX_PATH`` (260) limit.
Plain ``Path.read_text`` / ``Path.write_text`` / ``Path.exists`` then
raise ``FileNotFoundError`` (or silently report ``False``) even though
the file is perfectly valid.  Prefixing an absolute path with the
extended-length marker ``\\\\?\\`` lifts the limit on Windows; on other
platforms the path is returned unchanged.

Use these helpers at any IO boundary that may touch ref-card / eq-map
artefacts written under the deep LC2 run tree.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

__all__ = ["winlong", "read_text_long", "write_text_long", "exists_long"]


def winlong(path) -> str:
    """Return a filesystem path string safe for >260-char IO on Windows."""
    sp = os.fspath(path)
    if os.name != "nt":
        return sp
    ap = os.path.abspath(sp)
    if ap.startswith("\\\\?\\"):
        return ap
    if ap.startswith("\\\\"):                       # UNC share
        return "\\\\?\\UNC\\" + ap[2:]
    return "\\\\?\\" + ap


def read_text_long(path, *, encoding: str = "utf-8") -> str:
    """``Path.read_text`` that tolerates >260-char paths on Windows.

    Network-share (SMB) run trees can transiently miss a freshly written
    file when it is immediately reopened through a new handle or a
    different path alias, so a bounded backoff retry absorbs those
    glitches; a genuinely absent file still raises after the last try.
    """
    last_error: OSError | None = None
    for attempt, delay in enumerate((0.0, 0.2, 0.5, 1.0)):
        if delay:
            time.sleep(delay)
        try:
            with open(winlong(path), "r", encoding=encoding) as fh:
                return fh.read()
        except (FileNotFoundError, PermissionError, OSError) as exc:
            last_error = exc
    assert last_error is not None
    raise last_error


def write_text_long(path, text: str, *, encoding: str = "utf-8") -> None:
    """``Path.write_text`` that tolerates >260-char paths on Windows."""
    with open(winlong(path), "w", encoding=encoding) as fh:
        fh.write(text)


def exists_long(path) -> bool:
    """``Path.exists`` that tolerates >260-char paths on Windows."""
    return os.path.exists(winlong(path))
