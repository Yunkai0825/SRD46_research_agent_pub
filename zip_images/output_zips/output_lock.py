"""Cross-process exclusion for replacing output ZIPs and reading their streams."""
from contextlib import contextmanager
import os
import time


@contextmanager
def archive_lock(store, *, exclusive=False):
    store.mkdir(parents=True, exist_ok=True)
    with (store / ".lock").open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            import msvcrt
            class Overlapped(ctypes.Structure):
                _fields_ = [("Internal", ctypes.c_size_t), ("InternalHigh", ctypes.c_size_t),
                            ("Offset", wintypes.DWORD), ("OffsetHigh", wintypes.DWORD),
                            ("hEvent", wintypes.HANDLE)]
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.LockFileEx.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                                         wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(Overlapped)]
            kernel.UnlockFileEx.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                                           wintypes.DWORD, ctypes.POINTER(Overlapped)]
            overlap = Overlapped()
            native = msvcrt.get_osfhandle(handle.fileno())
            while True:
                if kernel.LockFileEx(native, 1 | (2 if exclusive else 0), 0, 1, 0, ctypes.byref(overlap)):
                    break
                code = ctypes.get_last_error()
                if code != 33:
                    raise ctypes.WinError(code)
                time.sleep(.05)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        try:
            yield
        finally:
            if os.name == "nt":
                if not kernel.UnlockFileEx(native, 0, 1, 0, ctypes.byref(overlap)):
                    raise ctypes.WinError(ctypes.get_last_error())
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
