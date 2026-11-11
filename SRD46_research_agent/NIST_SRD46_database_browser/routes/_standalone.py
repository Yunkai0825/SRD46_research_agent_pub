"""Shared configuration and session ownership for the standalone browser."""
from __future__ import annotations

import threading

from output_settings.runtime import (
    begin_session,
    finish_session,
    configure,
    current_settings,
    restore_configuration,
)

_RUN_LOCK = threading.Lock()


def configured_user() -> str:
    return str(current_settings().get("api_user") or "").strip()


def configured_model(section: str = "analysis") -> str:
    return str(current_settings().get("model") or "claudeopus47")


def model_options(section: str = "analysis") -> list[str]:
    selected = configured_model(section)
    settings = current_settings()
    candidates = ([selected, "claudeopus47", "claudeopus55", "gpt55", "gpt6astra", "gpt6sol"]
                  if settings.get("provider", "argo") == "argo" else [selected])
    return list(dict.fromkeys(candidates))


def reserve_run(run) -> bool:
    """Reserve the process-wide settings shared by Analysis and Query."""
    if not _RUN_LOCK.acquire(blocking=False):
        return False
    run._standalone_slot = True
    return True


def prepare_run(run) -> None:
    run._standalone_previous = current_settings()
    settings = current_settings()
    settings.update(api_user=run.api_user or settings.get("api_user", ""), model=run.model)
    configure(settings=settings)


def finish_run(run) -> None:
    try:
        finish_session()
        previous = getattr(run, "_standalone_previous", None)
        if previous is not None:
            restore_configuration(previous)
    except Exception as exc:
        run.status = "error"
        run.error = f"Session provenance/configuration finalization failed: {type(exc).__name__}: {exc}"
        run.append_log(f"[browser] ERROR: {run.error}")
    finally:
        if getattr(run, "_standalone_slot", False):
            run._standalone_slot = False
            _RUN_LOCK.release()


__all__ = ["begin_session", "configured_user", "configured_model", "model_options",
           "reserve_run", "prepare_run", "finish_run"]
