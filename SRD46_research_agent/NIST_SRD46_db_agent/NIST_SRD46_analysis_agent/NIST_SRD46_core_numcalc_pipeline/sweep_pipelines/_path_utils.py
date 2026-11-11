"""Long-path helper for Windows (MAX_PATH=260 workaround).

Shared across all sweep pipelines and downstream output/plotting helpers.
"""
from __future__ import annotations
import os
import pathlib
import re
from typing import Union


def compact_output_prefix(prefix: str, output_dir=None) -> str:
    """Collapse repeated metal-valence tokens only for long output paths.

    Reserve 64 characters for artifact suffixes and snapshot subdirectories.
    The same prefix must be used for related CSVs, plots, topology and verdicts.
    Chemical names, species IDs and checkpoint identities are not modified.
    """
    parent = pathlib.Path(output_dir or ".").resolve()
    candidate = str(parent / prefix)
    if candidate.startswith("\\\\?\\UNC\\"):
        candidate = "\\\\" + candidate[8:]
    elif candidate.startswith("\\\\?\\"):
        candidate = candidate[4:]
    units = lambda text: len(text.encode("utf-16-le")) // 2
    if units(candidate) + 64 < 260 and units(prefix) + 64 <= 255:
        return prefix

    parts = []
    elements = set()
    for token in prefix.split("_+_"):
        # '-' has already become '_' in the sweep filename sanitizer.
        match = re.fullmatch(r"([A-Z][a-z]?)\$[+_\-]?\d+", token)
        if match:
            element = match.group(1)
            if element not in elements:
                parts.append(element)
                elements.add(element)
        else:
            parts.append(token)
    return "_+_".join(parts)


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
