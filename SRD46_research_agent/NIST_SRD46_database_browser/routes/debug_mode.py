"""Site-wide debug mode for the SRD-46 browser.

When debug mode is *off* (the default), pages that would otherwise expose
internal agent state — preplan, plan, tool results, agent-workflow diagram,
and verbose terminal logs — render with those panels hidden. To unlock them,
the user submits a passcode on the dashboard which is verified against
:data:`_DEFAULT_DEBUG_PASSCODE` (or the ``SRD46_DEBUG_PASSCODE`` env var) and
stored as a flag in the Flask session for the rest of the browsing session.

The same flag is used by:

- ``routes/agent.py``  — SSE log filter
- ``templates/agent.html``  — agent-page panel visibility
- ``templates/eval_run.html``  — eval / freeform panel visibility
"""

from __future__ import annotations

import hmac
import os

from flask import Blueprint, redirect, request, session, url_for

try:
    import master_runtime as _master_runtime
except Exception:  # pragma: no cover - standalone fallback
    _master_runtime = None

debug_bp = Blueprint("debug_mode", __name__, url_prefix="/debug-mode")

# ---------------------------------------------------------------------------
# Passcode resolution
# ---------------------------------------------------------------------------
_DEBUG_PASSCODE_ENV = "SRD46_DEBUG_PASSCODE"
# 400-character alphanumeric default. Override via the env var above.
_DEFAULT_DEBUG_PASSCODE = (
    "0J9zk4a4UQ9xl5BHzjbV7uQfoUoFHgPj683KnokZPG3pfz4icxj2kVDeBz9OefVrJonUjIOF9DAEwXZq"
    "eoz4mWHhd3eqhykbYCzk1o7JkdKSyiBxGs8NIQryLajfVntDsauiZ3MsoUl1YpjlnChZSZ38XLgILYNK"
    "m7Y82ZenK5JDgVwD92ncWi1M8CRLwZ30nhZ7Eib74I1Qn4yhGdg0WGocj72oA0u9daIw3eiyN8ihzqRS"
    "WF6cOGXtVRISMSysVTVFhHQ8fA77ejdIhISGU49V2eDrK1aBnikMvek5CpBo5wrTHq9OovGoyzo9MHmh"
    "sGtATuOK9ydG1cOP7VUNyZHgx5YlleW3b3jg0NHPMg5fWyDUIMVNs1uFIoUP9xpjoAdwp8mkBbrkMpcl"
)

_SESSION_KEY = "srd46_debug_on"


def expected_passcode() -> str:
    """Return the currently-configured debug passcode."""
    return (os.environ.get(_DEBUG_PASSCODE_ENV) or _DEFAULT_DEBUG_PASSCODE).strip()


def verify_passcode(code: str) -> bool:
    code = (code or "").strip()
    if not code:
        return False
    return hmac.compare_digest(code, expected_passcode())


def is_debug_mode() -> bool:
    """Use the master browser's site-wide debug state when available."""
    if _master_runtime is not None:
        try:
            return bool(_master_runtime.debug_enabled())
        except Exception:
            return False
    try:
        return bool(session.get(_SESSION_KEY, False))
    except RuntimeError:
        # Outside of a request context.
        return False


# ---------------------------------------------------------------------------
# Routes — enable / disable
# ---------------------------------------------------------------------------

def _safe_next(default_endpoint: str = "index") -> str:
    nxt = request.form.get("next") or request.args.get("next") or ""
    # Only allow same-origin paths to prevent open redirects.
    if nxt.startswith("/") and not nxt.startswith("//"):
        return nxt
    return url_for(default_endpoint)


@debug_bp.route("/enable", methods=["POST"])
def enable():
    code = (request.form.get("debug_passcode") or "").strip()
    if verify_passcode(code):
        if _master_runtime is not None:
            # Persist in the active user's settings (kept across sessions).
            # Guest can never hold debug mode; the runtime enforces it.
            try:
                if not _master_runtime.is_guest_user():
                    _master_runtime.update_settings(debug_mode=True)
            except Exception:
                pass
        else:
            session[_SESSION_KEY] = True
            session.permanent = True
    return redirect(_safe_next())


@debug_bp.route("/disable", methods=["POST"])
def disable():
    if _master_runtime is not None:
        try:
            _master_runtime.update_settings(debug_mode=False)
        except Exception:
            pass
    session.pop(_SESSION_KEY, None)
    return redirect(_safe_next())
