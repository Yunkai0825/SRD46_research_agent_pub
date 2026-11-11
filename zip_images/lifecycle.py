"""Finish owned cleanup before delivering a repeated console interrupt."""
from contextlib import contextmanager
import signal
import sys
import threading


@contextmanager
def defer_interrupts():
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    primary = sys.exception()
    previous = signal.getsignal(signal.SIGINT)
    if previous == signal.SIG_IGN:
        yield
        return
    requested = []

    def remember(signum, frame):
        requested.append(signum)

    signal.signal(signal.SIGINT, remember)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous)
        if requested:
            active = sys.exception() or primary
            if active is not None:
                active.add_note("Console interrupt deferred until owned cleanup completed")
            else:
                raise KeyboardInterrupt
