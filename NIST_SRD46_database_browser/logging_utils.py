"""Temporary dependency log levels while a local agent streams its own logs."""
import logging

_DEPENDENCY_LOGGERS = ("httpx", "httpcore", "urllib3", "matplotlib", "PIL", "asyncio")

def suppress_noisy_dependency_debug() -> dict[str, int]:
    levels = {name: logging.getLogger(name).level for name in _DEPENDENCY_LOGGERS}
    for name in levels:
        logging.getLogger(name).setLevel(logging.WARNING)
    return levels

def restore_logger_levels(levels: dict[str, int]) -> None:
    for name, level in levels.items():
        logging.getLogger(name).setLevel(level)
