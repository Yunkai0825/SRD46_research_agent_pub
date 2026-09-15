#!/usr/bin/env python3
"""Start the local SRD-46 browser and open it in the default web browser."""
from __future__ import annotations

import argparse
import importlib
import os
import secrets
import socket
from pathlib import Path
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser

def _prefer_existing_drive(path: Path) -> Path:
    """Use an existing Windows share mapping to keep Windows paths short."""
    if os.name != "nt" or not str(path).startswith("\\\\"):
        return path
    import ctypes
    from ctypes import wintypes

    try:
        get_connection = ctypes.WinDLL("mpr").WNetGetConnectionW
        get_connection.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR,
                                   ctypes.POINTER(wintypes.DWORD)]
        get_connection.restype = wintypes.DWORD
        candidates = []
        original = str(path)
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            size = wintypes.DWORD(32768)
            remote = ctypes.create_unicode_buffer(size.value)
            if get_connection(letter + ":", remote, ctypes.byref(size)) != 0:
                continue
            share = remote.value.rstrip("\\")
            if original.casefold() == share.casefold():
                candidate = Path(letter + ":\\")
            elif original.casefold().startswith(share.casefold() + "\\"):
                candidate = Path(letter + ":" + original[len(share):])
            else:
                continue
            if candidate.samefile(path):
                candidates.append(candidate)
        return min(candidates, key=lambda candidate: len(str(candidate))) if candidates else path
    except OSError:
        return path


ROOT = _prefer_existing_drive(Path(__file__).absolute().parent)
DEFAULT_PORT = 5046
HEALTH_ROUTES = (
    "/", "/metals/", "/ligands/", "/stability/", "/pka/",
    "/equilibrium/", "/literature/", "/similarity/", "/results/",
    "/results/benchmark/", "/results/output/",
)


def _port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be an integer") from exc
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 0 and 65535")
    return port


def _load_app(db_dir: Path | None = None):
    if db_dir is not None:
        os.environ["SRD46_DB_DIR"] = str(db_dir.expanduser().absolute())
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    # Launching the browser should not fill a clean source checkout with bytecode.
    sys.dont_write_bytecode = True
    module = importlib.import_module("NIST_SRD46_database_browser.app")
    return module.app, module.dbmod


def _open_when_ready(url: str, stop: threading.Event, timeout: float = 30.0,
                     readiness_url: str | None = None, token: str | None = None) -> bool:
    """Wait for our lightweight readiness response before opening the user page."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + timeout
    while not stop.is_set() and time.monotonic() < deadline:
        try:
            with opener.open(readiness_url or url, timeout=1.0) as response:
                ready = response.status == 200
                if token is not None:
                    ready = ready and response.read(128).decode("ascii") == token
            if ready:
                if stop.is_set():
                    return False
                try:
                    opened = webbrowser.open_new_tab(url)
                except (webbrowser.Error, OSError):
                    opened = False
                if not opened:
                    print(f"Open this address in your web browser: {url}", flush=True)
                return bool(opened)
        except (OSError, urllib.error.URLError, UnicodeDecodeError):
            pass
        if stop.wait(0.2):
            return False
    if not stop.is_set():
        print(f"Automatic opening timed out. The server address is {url}", flush=True)
    return False


def _create_server(app, requested_port: int | None):
    from werkzeug.serving import ThreadedWSGIServer

    class LocalServer(ThreadedWSGIServer):
        allow_reuse_address = os.name != "nt"

        def server_bind(self):
            if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            super().server_bind()

    port = DEFAULT_PORT if requested_port is None else requested_port
    try:
        return LocalServer("127.0.0.1", port, app)
    except (OSError, SystemExit):
        if requested_port is not None:
            raise
        print(f"Port {port} is unavailable; selecting a free local port.", flush=True)
        return LocalServer("127.0.0.1", 0, app)


def _database_problems(dbmod) -> list[str]:
    """Detect missing/corrupt databases and unmaterialized Git LFS pointers."""
    problems = []
    for name, exists in dbmod.verify_all_paths().items():
        if not exists:
            problems.append("Missing database: " + name)
            continue
        path = dbmod.CARDS_DB.parent / name
        try:
            with path.open("rb") as reader:
                header = reader.read(128)
        except OSError as exc:
            problems.append(f"Cannot read {name}: {exc}")
            continue
        if header.startswith(b"version https://git-lfs.github.com/spec/v1"):
            problems.append(f"{name} is a Git LFS pointer. Run git lfs install and git lfs pull.")
        elif not header.startswith(b"SQLite format 3\x00"):
            problems.append(f"{name} is not a SQLite database. Obtain the matching database snapshot.")
    return problems


def _check(app, dbmod) -> int:
    failed = False
    with app.test_client() as client:
        for route in HEALTH_ROUTES:
            response = client.get(route, follow_redirects=True)
            print(f"{response.status_code} {route}")
            failed = failed or response.status_code != 200
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=_port, default=None,
                        help="local HTTP port (default: 5046, or a free port when busy; 0 chooses a free port)")
    parser.add_argument("--db-dir", type=Path,
                        help="directory containing the four SRD-46 SQLite databases")
    parser.add_argument("--no-browser", action="store_true",
                        help="start the server without opening a web-browser tab")
    parser.add_argument("--check", action="store_true",
                        help="check database paths and browser pages, then exit")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 11):
        print("Python 3.11 or newer is required.", file=sys.stderr)
        return 2
    try:
        app, dbmod = _load_app(args.db_dir)
    except ModuleNotFoundError as exc:
        print(f"Cannot import {exc.name!r}. Install the browser requirements with:\n"
              f'  "{sys.executable}" -m pip install -r "{ROOT / "requirements.txt"}"',
              file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        print("See docs/INSTALLATION.md for database setup.", file=sys.stderr)
        return 2
    print(f"Database directory: {dbmod.CARDS_DB.parent}", flush=True)
    problems = _database_problems(dbmod)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 2
    if args.check:
        return _check(app, dbmod)

    readiness_token = secrets.token_hex(16)
    readiness_path = "/_srd46_ready/" + readiness_token
    app.add_url_rule(readiness_path, "_srd46_launcher_ready", lambda: readiness_token)
    try:
        server = _create_server(app, args.port)
    except (OSError, SystemExit):
        print(f"Could not start on port {args.port}. Try --port 5047.", file=sys.stderr)
        return 2
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"SRD-46 browser: {url}\nPress Ctrl+C to stop.", flush=True)
    stop = threading.Event()
    if not args.no_browser:
        threading.Thread(
            target=_open_when_ready, args=(url, stop),
            kwargs={"readiness_url": url.rstrip("/") + readiness_path, "token": readiness_token},
            name="srd46-open-browser", daemon=True,
        ).start()
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
