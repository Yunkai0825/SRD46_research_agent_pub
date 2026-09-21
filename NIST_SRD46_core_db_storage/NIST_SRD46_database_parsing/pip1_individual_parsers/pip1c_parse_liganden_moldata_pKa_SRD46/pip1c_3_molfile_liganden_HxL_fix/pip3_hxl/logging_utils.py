"""
logging_utils.py - Logging utilities for pip1c-3 HxL pipeline.
"""

from datetime import datetime
from pathlib import Path
from typing import List

from .config import VERBOSE

# =====================================================================
# LOGGING
# =====================================================================
_log_messages: List[str] = []


def _timestamp_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str, force: bool = False) -> None:
    """Log a message with timestamp."""
    timestamped = f"[{_timestamp_str()}] {msg}"
    _log_messages.append(timestamped)
    if VERBOSE or force:
        print(timestamped, flush=True)


def write_log_file(log_path: Path) -> None:
    """Write all log messages to a file."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(_log_messages))
    print(f"[INFO] Log file written -> {log_path}")


def get_log_messages() -> List[str]:
    """Return a copy of all logged messages."""
    return _log_messages.copy()


def clear_log_messages() -> None:
    """Clear the log message buffer."""
    _log_messages.clear()
