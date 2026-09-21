"""Import the stand-alone parser scripts (hyphenated file names, no package) as modules and capture their console output."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
from pathlib import Path
from types import ModuleType
from typing import Iterable, Iterator, Optional


def ensure_sys_path(*dirs: Path) -> None:
    for d in dirs:
        s = str(Path(d))
        if s not in sys.path:
            sys.path.insert(0, s)


def load_script(path: Path, module_name: str, sys_path_extra: Iterable[Path] = ()) -> ModuleType:
    """Import ``path`` under ``module_name`` (cached in sys.modules)."""
    if module_name in sys.modules:
        return sys.modules[module_name]
    ensure_sys_path(*sys_path_extra)
    path = Path(path)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


class _Tee(io.TextIOBase):
    """Write-through stream: captures everything, optionally echoes to the console."""

    def __init__(self, echo_to: Optional[io.TextIOBase]):
        self.buffer_ = io.StringIO()
        self.echo_to = echo_to

    def write(self, s: str) -> int:  # type: ignore[override]
        self.buffer_.write(s)
        if self.echo_to is not None:
            try:
                self.echo_to.write(s)
            except UnicodeEncodeError:
                self.echo_to.write(s.encode("ascii", "replace").decode("ascii"))
        return len(s)

    def flush(self) -> None:
        if self.echo_to is not None:
            self.echo_to.flush()

    def getvalue(self) -> str:
        return self.buffer_.getvalue()

    @property
    def encoding(self) -> str:  # type: ignore[override]
        return "utf-8"

    def isatty(self) -> bool:
        return False


@contextlib.contextmanager
def capture_output(verbose: bool) -> Iterator[_Tee]:
    """Capture stdout/stderr of the wrapped module; echo live when ``verbose``."""
    tee = _Tee(sys.stdout if verbose else None)
    with contextlib.redirect_stdout(tee), contextlib.redirect_stderr(tee):
        yield tee
