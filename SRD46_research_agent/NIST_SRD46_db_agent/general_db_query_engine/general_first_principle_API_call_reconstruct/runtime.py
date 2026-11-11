"""Small native-runtime hooks for deterministic agent lanes and reminder time.

Outside an explicitly active reconstruction session these helpers call the
original functions directly. They do not replace prompts or summarize history.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import copy_context
from functools import wraps
import hashlib
import inspect
import json
import sys
import threading
import time
from types import ModuleType
from typing import Callable, Iterator
from weakref import WeakKeyDictionary

from .controller import current_session


# The engine can be imported under both its short and package-qualified names.
# Lane occurrence accounting must remain shared across those module aliases.
_STATE_KEY = "_general_first_principle_reconstruction_agent_runtime_v1"
_state = sys.modules.setdefault(_STATE_KEY, ModuleType(_STATE_KEY))
if not hasattr(_state, "lock"):
    _state.lock = threading.RLock()
    _state.sessions = WeakKeyDictionary()


@contextmanager
def _agent_lane(function: Callable, args: tuple, kwargs: dict) -> Iterator[None]:
    session = current_session()
    if session is None:
        yield
        return

    # Capture before the native loop appends the user message or mutates memory.
    bound = inspect.signature(function).bind(*args, **kwargs)
    arguments = bound.arguments
    identity = {
        "entrypoint": function.__name__,
        "system_prompt": arguments.get("system_prompt", ""),
        "user_message": arguments.get("user_message", ""),
        "memory": arguments.get("memory", []),
    }
    encoded = json.dumps(session.canonicalize(identity), ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    fingerprint = hashlib.sha256(encoded).hexdigest()
    with _state.lock:
        tracking = _state.sessions.setdefault(session, {"active": set(), "counts": {}})
        if fingerprint in tracking["active"]:
            session.reject(
                "concurrent agents have identical initial contexts; assign distinct "
                "native agent contexts before recording/reconstruction"
            )
        occurrence = tracking["counts"].get(fingerprint, 0) + 1
        tracking["counts"][fingerprint] = occurrence
        tracking["active"].add(fingerprint)
    lane = f"react:{function.__name__}:{fingerprint}:{occurrence}"
    try:
        if not session.live:
            # A relocated run may introduce root bindings only at replay time.
            # Reuse the saved lane after matching its raw initial context;
            # hashing the newly canonicalized context alone would change it.
            lane = session.recorded_operation_lane("runtime.agent_enter", identity) or lane
        with session.lane(lane):
            # A lightweight entry event checks the initial context even for a
            # loop that exits without making a model call.
            session.operation("runtime.agent_enter", identity, lambda: None)
            yield
    finally:
        with _state.lock:
            tracking["active"].discard(fingerprint)


def agent_scope(function: Callable) -> Callable:
    """Give each native sync/async agent turn a stable, isolated event lane."""
    if inspect.iscoroutinefunction(function):
        @wraps(function)
        async def asynchronous(*args, **kwargs):
            if current_session() is None:
                return await function(*args, **kwargs)
            with _agent_lane(function, args, kwargs):
                return await function(*args, **kwargs)
        return asynchronous

    @wraps(function)
    def synchronous(*args, **kwargs):
        if current_session() is None:
            return function(*args, **kwargs)
        with _agent_lane(function, args, kwargs):
            return function(*args, **kwargs)
    return synchronous


def clock(live_clock: Callable[[], float] = time.time) -> float:
    """Replay native clock observations; exclude the interruption from live time.

    Absolute recorded values preserve the original time reminders and credits
    for untimed tools. After the denied request is reached, the native clock
    advances from that request's recorded time, including new execution time
    but excluding the pause between sessions and the reconstruction itself.
    """
    session = current_session()
    if session is None:
        return live_clock()

    def observe() -> float:
        if session.mode == "reconstruction":
            anchor = session.live_clock_anchor
            started = session.live_started_monotonic
            if not session.live or anchor is None or started is None:
                session.reject("live clock reached before authorization breakpoint")
            return anchor + max(0.0, time.monotonic() - started)
        return live_clock()

    return float(session.operation("runtime.clock", {}, observe))


def preserve_context(function: Callable) -> Callable:
    """Carry the current agent lane through a native executor submission."""
    if current_session() is None:
        return function
    context = copy_context()

    @wraps(function)
    def invoke(*args, **kwargs):
        return context.run(function, *args, **kwargs)
    return invoke


def recorded_operation(name: str) -> Callable:
    """Record each invocation of a synchronous operation with JSON-safe data.

    Apply outside a result cache: logical cache hits also need an event so a
    fresh process can replay them without re-running the underlying I/O.
    """
    if not isinstance(name, str) or not name:
        raise ValueError("recorded operation requires a nonempty name")

    def decorate(function: Callable) -> Callable:
        if inspect.iscoroutinefunction(function):
            raise TypeError("recorded_operation requires a synchronous function")
        signature = inspect.signature(function)

        @wraps(function)
        def invoke(*args, **kwargs):
            session = current_session()
            if session is None:
                return function(*args, **kwargs)
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            return session.operation(name, dict(bound.arguments),
                                     lambda: function(*args, **kwargs))

        for attribute in ("cache_clear", "cache_info", "cache_parameters"):
            if hasattr(function, attribute):
                setattr(invoke, attribute, getattr(function, attribute))
        return invoke

    return decorate
