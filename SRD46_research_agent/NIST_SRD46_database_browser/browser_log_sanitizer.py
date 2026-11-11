"""Logging helpers for browser-run terminal capture."""

from __future__ import annotations

import logging
from collections.abc import Mapping


_NOISY_DEPENDENCY_LOGGERS = (
    "matplotlib",
    "matplotlib.font_manager",
    "PIL",
    "PIL.PngImagePlugin",
    "pubchempy",
    "urllib3",
    "urllib3.connectionpool",
)


def suppress_noisy_dependency_debug() -> dict[str, int]:
    """Raise noisy dependency loggers to WARNING while root DEBUG is captured."""
    previous: dict[str, int] = {}
    for name in _NOISY_DEPENDENCY_LOGGERS:
        logger = logging.getLogger(name)
        previous[name] = logger.level
        if logger.level == logging.NOTSET or logger.level < logging.WARNING:
            logger.setLevel(logging.WARNING)
    return previous


def restore_logger_levels(previous: Mapping[str, int]) -> None:
    """Restore logger levels returned by suppress_noisy_dependency_debug()."""
    for name, level in previous.items():
        logging.getLogger(name).setLevel(level)
