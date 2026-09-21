"""Restore missing packaged workspace assets, without rebuilding any data.

Run ``python workspace_setup.py`` for the first-run self-check. Only assets in
``packaged_files.json`` are installed; benchmark/freeform ZIPs stay compressed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile
import threading
from zipfile import BadZipFile
from zlib import error as ZlibError

from archive_io import archive_exists, open_zip

ROOT = Path(__file__).absolute().parent
MANIFEST_NAME = "packaged_files.json"
_CHUNK_SIZE = 1024 * 1024
_LOCK = threading.RLock()
_LOG = logging.getLogger(__name__)


class AssetRestoreError(RuntimeError):
    """A packaged asset cannot be restored and no incomplete target was published."""


def _safe_relative(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise AssetRestoreError(f"Invalid {label} in {MANIFEST_NAME}: {value!r}")
    relative = PurePosixPath(value)
    if relative.is_absolute() or any(part in ("", ".", "..") for part in value.split("/")):
        raise AssetRestoreError(f"Invalid {label} in {MANIFEST_NAME}: {value!r}")
    path = root.joinpath(*relative.parts)
    if not path.resolve().is_relative_to(root.resolve()):
        raise AssetRestoreError(f"Packaged {label} escapes the workspace: {value!r}")
    return path


def _entries(root: Path) -> list[dict]:
    manifest = root / MANIFEST_NAME
    try:
        data = json.loads(manifest.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise AssetRestoreError(f"Cannot read {manifest}: {exc}") from exc
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("files"), list):
        raise AssetRestoreError(f"Unsupported or invalid packaged asset manifest: {manifest}")
    entries = []
    targets = set()
    for record in data["files"]:
        if not isinstance(record, dict):
            raise AssetRestoreError(f"Invalid asset entry in {manifest}")
        entry = dict(record)
        target = _safe_relative(root, entry.get("path"), "path")
        archive = _safe_relative(root, entry.get("archive"), "archive")
        if target == archive or not str(archive).lower().endswith(".zip"):
            raise AssetRestoreError(f"Invalid ZIP archive for {target}")
        size = entry.get("size")
        digest = entry.get("sha256")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise AssetRestoreError(f"Invalid byte count for {target}")
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-fA-F]{64}", digest) is None:
            raise AssetRestoreError(f"Invalid SHA-256 digest for {target}")
        key = os.path.normcase(str(target.resolve()))
        if key in targets:
            raise AssetRestoreError(f"Duplicate packaged target: {target}")
        targets.add(key)
        member = entry.get("member", target.name)
        _safe_relative(root, member, "member")
        entry.update(target=target, source=archive, member=member, sha256=digest.lower())
        entries.append(entry)
    return entries


def _verify_file(path: Path, entry: dict) -> None:
    if path.stat().st_size != entry["size"]:
        raise AssetRestoreError(f"Size mismatch for {path}; existing files are never replaced automatically.")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    if digest.hexdigest() != entry["sha256"]:
        raise AssetRestoreError(f"SHA-256 mismatch for {path}; existing files are never replaced automatically.")


def _publish_missing(temporary: Path, target: Path) -> bool:
    """Atomically install a complete file without overwriting a concurrent writer."""
    try:
        if os.name == "nt":
            # Unlike POSIX rename, Windows rename refuses an existing destination.
            os.rename(temporary, target)
        else:
            os.link(temporary, target)
    except FileExistsError:
        if not target.is_file():
            raise AssetRestoreError(f"Cannot install packaged file over a non-file: {target}")
        return False
    return True


def _restore(entry: dict) -> bool:
    target, source = entry["target"], entry["source"]
    if target.is_file():
        return False
    if target.exists() or target.is_symlink():
        raise AssetRestoreError(f"Cannot install packaged file over a non-file: {target}")
    if not archive_exists(source):
        raise AssetRestoreError(
            f"Missing {target}. Its packaged source is also missing: {source} "
            f"(or its {source.stem}.part001-of-NNN.zip archive collection). "
            "Obtain the complete repository archive set and rerun python workspace_setup.py."
        )
    temporary = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open_zip(source) as archive:
            matches = [info for info in archive.infolist() if info.filename == entry["member"]]
            if len(matches) != 1:
                raise AssetRestoreError(f"Expected one {entry['member']!r} in {source}; found {len(matches)}")
            info = matches[0]
            if info.is_dir() or stat.S_ISLNK(info.external_attr >> 16) or info.file_size != entry["size"]:
                raise AssetRestoreError(f"Invalid member type or size for {target} in {source}")
            _LOG.warning("Restoring packaged asset: %s", entry["path"])
            digest, count = hashlib.sha256(), 0
            with archive.open(info) as reader, tempfile.NamedTemporaryFile(
                mode="wb", prefix="." + target.name + ".", suffix=".restore-tmp",
                dir=target.parent, delete=False,
            ) as writer:
                temporary = Path(writer.name)
                while chunk := reader.read(_CHUNK_SIZE):
                    count += len(chunk)
                    if count > entry["size"]:
                        raise AssetRestoreError(f"Expanded size exceeds manifest for {target}")
                    digest.update(chunk)
                    writer.write(chunk)
                writer.flush()
                os.fsync(writer.fileno())
            if count != entry["size"] or digest.hexdigest() != entry["sha256"]:
                raise AssetRestoreError(f"Packaged contents failed size/SHA-256 verification for {target}")
        return _publish_missing(temporary, target)
    except AssetRestoreError:
        raise
    except (OSError, BadZipFile, EOFError, RuntimeError, ValueError, ZlibError) as exc:
        raise AssetRestoreError(f"Cannot restore {target} from {source}: {exc}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def ensure_packaged_file(path: str | Path, *, root: str | Path | None = None) -> bool:
    """Restore a missing manifest-listed file; return whether it was installed.

    Existing files and paths outside this repository are left untouched. Paths
    not listed in the manifest are left for the caller's normal missing-file error.
    """
    target = Path(path).absolute()
    if target.is_file():
        return False
    base = Path(root).absolute() if root is not None else ROOT
    resolved = target.resolve()
    if not resolved.is_relative_to(base.resolve()):
        return False
    with _LOCK:
        for entry in _entries(base):
            if entry["target"].resolve() == resolved:
                return _restore(entry)
    return False


def ensure_packaged_files(*, root: str | Path | None = None, verify: bool = False) -> list[Path]:
    """Install missing manifest assets, optionally hashing existing assets too."""
    base = Path(root).absolute() if root is not None else ROOT
    restored = []
    with _LOCK:
        for entry in _entries(base):
            installed = _restore(entry)
            if installed:
                restored.append(entry["target"])
            elif verify:
                _verify_file(entry["target"], entry)
    return restored


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="also verify SHA-256 of existing packaged assets")
    args = parser.parse_args(argv)
    try:
        restored = ensure_packaged_files(verify=args.verify)
    except AssetRestoreError as exc:
        print(f"Workspace self-check failed: {exc}", file=sys.stderr)
        return 1
    print(f"Workspace self-check passed: {len(restored)} file(s) restored" +
          ("; all packaged assets verified." if args.verify else "."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
