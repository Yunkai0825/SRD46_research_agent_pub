#!/usr/bin/env python3
"""
Large-file packs: big files kept in git as ordinary zip parts under 100 MB.
===========================================================================

WHY. Some git hosts (GitHub) refuse any single file over 100 MB, and this repository's push law allows only
ORIGINAL files to be pushed -- never a Git LFS pointer. So every big file is stored in the repository as a
short series of ordinary zip files ("parts"), each well under 100 MB, while the big file itself is left out of
git (listed in .gitignore). Each time the master browser starts it runs :func:`self_check`, which restores
("unpacks") every big file that is missing. The manual for people is ``_large_files/README.md``.

THE STORE. ``_large_files/`` beside this module. One folder per distinct file CONTENT, named
``<file name>__<first 12 hex digits of its sha256>``, holding ``manifest.json`` and ``part_001.zip``,
``part_002.zip``, ... Every part is a normal zip that any unzip tool opens; it holds ONE member, a contiguous
slice of the original bytes named ``<file name>.part_001`` and so on. Joining the members in order gives the
original file back byte for byte; the manifest carries the sha256 of the whole file, of every slice and of
every zip. Identical files at several paths share one folder whose manifest lists every path ("targets").
The list of packed files is DATA (the manifests); this module knows no folder or project names.

HOW THE PARTS ARE CUT (deterministic). The file is read in blocks (1 MiB at the default limit) and streamed
into a zip member with deflate level 6 while the zip's size on disk is watched; the part ends before the next
block could push the zip past ``part_limit`` (95,000,000 bytes by default) after keeping a reserve for the
compressor's buffered tail. So a file that compresses well needs fewer parts. If a finished zip still ends up
over the limit, the same part is written again with a shorter slice. No part holds more than 1 GiB of raw
bytes, so no zip ever needs the ZIP64 extension (older unzip tools open every part). Every zip entry carries a
fixed date (1980-01-01) and fixed attributes, so packing the same bytes twice with the same zlib gives
byte-identical parts. Each part is read back and checked (zip sha256, member sha256) before it is kept, and
no part may reach 100,000,000 bytes whatever the parameters say.

LOCAL STATE (never committed; the generated .gitignore block ignores it): ``_large_files/.state/``
  ``stamps.json``         per target: size + modification time + sha256 last proven on this machine, and
                          ``"packed": true`` when those bytes were a packed version (restored from the parts,
                          or hashed or packed here while they matched a manifest). When a file's size and time
                          still match, the self-check trusts it without reading it; after a newer manifest
                          arrives, such a stamp proves the file is the earlier packed version, untouched since
                          (``unpack --update-stale`` replaces it; a file changed here is never overwritten).
  ``replaced_pointers/``  the text of every Git LFS pointer stub the self-check replaced with the real file.
  ``packing.<pid>/``      a pack being built (renamed into place when complete).
  ``stripped.json``       the packs whose zip parts `strip` removed from this copy (manifests kept).

IGNORE FILES: `pack` keeps ONE generated block in the root ``.gitignore`` (the originals, the state folder)
and, when the repository has one, in the root ``.dockerignore`` (the originals and the whole store: an
image never carries them; a container reads the originals through read-only folder mounts, restored
beforehand on the writable side). READ-ONLY COPIES: the self-check never writes into a folder it cannot
write (see :func:`self_check`).

COMMANDS (``python large_file_packs.py --help``): status, check, unpack, pack, scan, forget, strip.
  ``strip`` is for a zip or image copy whose big files are already restored: it deletes the zip parts of
  every pack whose files are present and verified, keeps the manifests and records the packs in
  ``.state/stripped.json``; refused where a ``.git`` folder exists unless ``--force``. A stripped pack's
  missing parts are expected (status, check); a missing file of a stripped pack cannot be restored and is
  reported as "stripped_missing"; `pack` of its file rebuilds the parts and drops the record.
  ``scan`` (and ``pack --scan``) list the files git tracks, so they need a git checkout; in a copy without
  one they say so and exit 2.
THE FUNCTION THE MASTER BROWSER CALLS: :func:`self_check` -- it never raises. Its mode comes from the
environment variable ``LARGE_FILES_SELF_CHECK``: ``0`` = off (or ``master_browser.py --no-large-files``);
``size`` = size mode (a file without a stamp of this machine counts as ok when its size is right and is
never hashed -- for containers, whose stamps do not survive a re-creation); anything else or unset = full
(such a file is hashed once and stamped). Missing files and pointer stubs are restored in every mode, and
the `unpack` command always runs the full check.

Stdlib only.

Run:
    python large_file_packs.py status
    python large_file_packs.py pack --scan
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import logging
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath

# ---------------------------------------------------------------------------
# Constants (the limits are parameters of pack(); these are the defaults)
# ---------------------------------------------------------------------------
FORMAT = "large-file-pack/1"
STORE_DIR = "_large_files"
STATE_DIR = ".state"
MANIFEST_NAME = "manifest.json"
STAMPS_NAME = "stamps.json"
POINTERS_DIR = "replaced_pointers"
STRIPPED_NAME = "stripped.json"
STRIPPED_FORMAT = "large-file-stripped/1"

DEFAULT_THRESHOLD = 100_000_000   # `pack --scan` packs every tracked file of this many bytes or more
DEFAULT_PART_LIMIT = 95_000_000   # every zip part stays at or under this size
HARD_LIMIT = 100_000_000          # no zip part may reach this size, whatever the parameters say
MIN_PART_LIMIT = 4_096
MAX_MEMBER = 1 << 30              # raw bytes per part at most: every zip stays classic (no ZIP64)
COMPRESS_LEVEL = 6
ZIP_DATE = (1980, 1, 1, 0, 0, 0)
SPACE_MARGIN = 64 * 1024 * 1024   # free space kept on top of the file's size before unpacking
POINTER_HEADER = b"version https://git-lfs.github.com/spec/v1"
POINTER_MAX = 1024
TEMP_TAG = ".unpacking."
STALE_TEMP_SECONDS = 600
STALE_KEPT_PREFIX = "large files: changed on this machine, not overwritten: "   # `unpack --update-stale`, exit 3
ENV_SWITCH = "LARGE_FILES_SELF_CHECK"
MODE_FULL = "full"                # the self-check's modes (see env_mode)
MODE_SIZE = "size"
MODE_OFF = "off"
READ_BLOCK = 1 << 20
PROGRESS_SECONDS = 5.0

GITIGNORE_BEGIN = "# >>> large-file packs (generated by large_file_packs.py -- do not edit by hand)"
GITIGNORE_END = "# <<< large-file packs"
GITIGNORE_STATE = "/" + STORE_DIR + "/" + STATE_DIR + "/"
GITIGNORE_TEMP = "*" + TEMP_TAG + "[0-9]*"
# .dockerignore anchors every pattern at the build context's root, so its temp rule needs the `**/`
DOCKERIGNORE_STORE = "/" + STORE_DIR + "/"
DOCKERIGNORE_TEMP = "**/" + GITIGNORE_TEMP

_HEX64 = re.compile(r"[0-9a-f]{64}")
_PART_FILE = re.compile(r"part_[0-9]{3,}\.zip")
_POINTER_OID = re.compile(rb"^oid sha256:([0-9a-f]{64})\s*$", re.M)


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------
class _Say:
    """One voice over a logging.Logger, a print-like callable, or nothing (this module's own logger)."""

    def __init__(self, log=None):
        self._log = log if log is not None else logging.getLogger("large-file-packs")

    def _emit(self, level: str, msg: str) -> None:
        try:
            fn = getattr(self._log, level, None)
            if callable(fn):
                fn(msg)
            elif callable(self._log):
                self._log(msg if level == "info" else f"{level.upper()}: {msg}")
        except Exception:  # noqa: BLE001 -- a message must never break the work
            pass

    def info(self, msg: str) -> None:
        self._emit("info", msg)

    def warning(self, msg: str) -> None:
        self._emit("warning", msg)

    def error(self, msg: str) -> None:
        self._emit("error", msg)


class _Printer:
    """The command line's voice: plain lines on stdout."""

    def info(self, msg: str) -> None:
        print(msg, flush=True)

    def warning(self, msg: str) -> None:
        print("WARNING: " + msg, flush=True)

    def error(self, msg: str) -> None:
        print("ERROR: " + msg, flush=True)


class _Progress:
    """Counts bytes and says how far along a long job is, at most every PROGRESS_SECONDS."""

    def __init__(self, say: _Say, label: str, total: int):
        self.say, self.label, self.total = say, label, total
        self.done = 0
        self.next = time.monotonic() + PROGRESS_SECONDS

    def __call__(self, n: int) -> None:
        self.done += n
        now = time.monotonic()
        if now >= self.next:
            self.next = now + PROGRESS_SECONDS
            self.say.info(f"  {self.label}: {_mb(self.done)} of {_mb(self.total)} MB")


def _mb(n: int) -> str:
    return f"{n / 1_000_000:,.1f}"


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _is_hex(x) -> bool:
    return isinstance(x, str) and _HEX64.fullmatch(x) is not None


def _check_rel(rel) -> str:
    """A target path as the manifests hold it: relative, forward slashes, no '.', '..' or empty steps."""
    if not isinstance(rel, str) or not rel.strip():
        raise ValueError("an empty path")
    if "\\" in rel or "\0" in rel:
        raise ValueError(f"{rel!r}: use forward slashes")
    if rel.startswith("/") or PureWindowsPath(rel).drive:
        raise ValueError(f"{rel!r}: must be relative to the repository folder")
    steps = rel.split("/")
    if any(s in ("", ".", "..") for s in steps):
        raise ValueError(f"{rel!r}: empty, '.' and '..' steps are not allowed")
    if steps[0] in (STORE_DIR, ".git"):
        raise ValueError(f"{rel!r}: lies inside {steps[0]}/")
    return rel


def _rel_of(root: Path, text: str) -> str:
    """A path typed on the command line (relative to the repository folder, or absolute) -> a target path."""
    p = Path(text)
    if p.is_absolute():
        try:
            rel = os.path.relpath(p, root)
        except ValueError:
            raise ValueError(f"{text}: not inside {root}") from None
        if rel == ".." or rel.startswith(".." + os.sep):
            raise ValueError(f"{text}: not inside {root}")
    else:
        rel = text
    rel = rel.replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]
    return _check_rel(rel)


def _hash_file(path: Path, progress=None) -> str:
    """sha256 of a file's bytes. Every hash of a whole file goes through here (the test counts the calls)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(READ_BLOCK)
            if not block:
                break
            h.update(block)
            if progress is not None:
                progress(len(block))
    return h.hexdigest()


def _write_bytes_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    try:
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def _json_bytes(obj) -> bytes:
    """UTF-8, LF, sorted keys, two-space indent: the same data always gives the same bytes."""
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _pointer_text(path: Path, size: int) -> bytes | None:
    """The file's bytes when it is a Git LFS pointer stub (<= 1024 bytes, the spec's first line), else None."""
    if size > POINTER_MAX:
        return None
    data = path.read_bytes()
    first = data.split(b"\n", 1)[0].rstrip(b"\r")
    return data if first == POINTER_HEADER else None


def _pointer_oid(data: bytes) -> str | None:
    m = _POINTER_OID.search(data)
    return m.group(1).decode("ascii") if m else None


# ---------------------------------------------------------------------------
# Manifests and packs
# ---------------------------------------------------------------------------
def _check_manifest(m) -> dict:
    """Validate a manifest; raise ValueError in plain words when anything is off."""
    if not isinstance(m, dict):
        raise ValueError("not a JSON object")
    if m.get("format") != FORMAT:
        raise ValueError(f"format is {m.get('format')!r}, expected {FORMAT!r}")
    targets = m.get("targets")
    if not isinstance(targets, list):
        raise ValueError("'targets' is not a list")
    for t in targets:
        _check_rel(t)
    if len(set(targets)) != len(targets):
        raise ValueError("'targets' lists a path twice")
    size = m.get("size")
    if not _is_int(size) or size < 0:
        raise ValueError("'size' is not a whole number")
    if not _is_hex(m.get("sha256")):
        raise ValueError("'sha256' is not 64 lowercase hex digits")
    for key in ("threshold", "part_limit"):
        if not _is_int(m.get(key)):
            raise ValueError(f"'{key}' is not a whole number")
    parts = m.get("parts")
    if not isinstance(parts, list):
        raise ValueError("'parts' is not a list")
    offset, files = 0, set()
    for i, p in enumerate(parts, 1):
        if not isinstance(p, dict):
            raise ValueError(f"part {i} is not an object")
        f, member = p.get("file"), p.get("member")
        if not isinstance(f, str) or not _PART_FILE.fullmatch(f) or f in files:
            raise ValueError(f"part {i}: bad or repeated file name {f!r}")
        files.add(f)
        if (not isinstance(member, str) or not member or member in (".", "..")
                or "/" in member or "\\" in member):
            raise ValueError(f"part {i}: bad member name {member!r}")
        if p.get("offset") != offset:
            raise ValueError(f"part {i}: offset {p.get('offset')!r}, expected {offset}")
        length = p.get("length")
        if not _is_int(length) or length <= 0:
            raise ValueError(f"part {i}: bad length")
        zsize = p.get("zip_size")
        if not _is_int(zsize) or not 0 < zsize < HARD_LIMIT:
            raise ValueError(f"part {i}: zip_size missing or not under {HARD_LIMIT:,} bytes")
        if not _is_hex(p.get("sha256")) or not _is_hex(p.get("zip_sha256")):
            raise ValueError(f"part {i}: bad sha256")
        offset += length
    if offset != size:
        raise ValueError(f"the parts hold {offset:,} bytes, the manifest says {size:,}")
    return m


class Pack:
    """One folder of the store: its manifest and its parts."""

    def __init__(self, folder: Path, manifest: dict):
        self.dir = folder
        self.m = manifest

    @property
    def targets(self) -> list:
        return self.m["targets"]

    @property
    def size(self) -> int:
        return self.m["size"]

    @property
    def sha256(self) -> str:
        return self.m["sha256"]

    @property
    def parts(self) -> list:
        return self.m["parts"]

    @property
    def zip_bytes(self) -> int:
        return sum(p["zip_size"] for p in self.parts)

    def save(self) -> None:
        self.m["targets"] = sorted(self.m["targets"])
        _write_bytes_atomic(self.dir / MANIFEST_NAME, _json_bytes(self.m))


def _load_packs(store: Path) -> tuple[list, list]:
    """(packs, problems): every readable pack folder, and (folder name, message) for each broken one."""
    packs, problems = [], []
    try:
        entries = sorted(os.scandir(store), key=lambda e: e.name)
    except (FileNotFoundError, NotADirectoryError):
        return [], []
    for e in entries:
        if e.name.startswith(".") or not e.is_dir():
            continue
        try:
            raw = (Path(e.path) / MANIFEST_NAME).read_bytes()
            packs.append(Pack(Path(e.path), _check_manifest(json.loads(raw.decode("utf-8")))))
        except FileNotFoundError:
            problems.append((e.name, "has no manifest.json"))
        except Exception as exc:  # noqa: BLE001 -- any broken manifest is reported, never fatal
            problems.append((e.name, f"unreadable manifest: {exc}"))
    return packs, problems


def _claims(packs: list) -> tuple[dict, list]:
    """(target -> pack, [(target, message)] for a target that two packs both claim)."""
    claims, conflicts = {}, []
    for pk in packs:
        for rel in pk.targets:
            if rel in claims:
                conflicts.append((rel, f"claimed by both {claims[rel].dir.name} and {pk.dir.name}"))
            else:
                claims[rel] = pk
    return claims, conflicts


def _remove_pack_dir(folder: Path) -> bool:
    """Delete a pack folder -- only the files this module writes. False when anything else is inside."""
    for e in list(os.scandir(folder)):
        if e.is_file() and (e.name == MANIFEST_NAME or _PART_FILE.fullmatch(e.name)
                            or ".tmp." in e.name):
            os.unlink(e.path)
    try:
        folder.rmdir()
    except OSError:
        return False
    return True


def _pack_folder_name(base: str, sha: str) -> str:
    return f"{base[:80]}__{sha[:12]}"


# ---------------------------------------------------------------------------
# Stamps (local to this machine)
# ---------------------------------------------------------------------------
def _load_stamps(store: Path) -> dict:
    try:
        data = json.loads((store / STATE_DIR / STAMPS_NAME).read_text("utf-8"))
        stamps = data.get("stamps") if isinstance(data, dict) else None
        return dict(stamps) if isinstance(stamps, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_stamps(store: Path, stamps: dict) -> None:
    _write_bytes_atomic(store / STATE_DIR / STAMPS_NAME,
                        _json_bytes({"format": "large-file-stamps/1", "stamps": stamps}))


def _stamp(st: os.stat_result, sha: str, packed: bool = False) -> dict:
    """This machine's proof of a file: its size, modification time and sha256; ``packed`` = those bytes were a
    packed version (restored from its parts, or hashed or packed here while they matched a manifest)."""
    stamp = {"size": st.st_size, "mtime_ns": st.st_mtime_ns, "sha256": sha}
    if packed:
        stamp["packed"] = True
    return stamp


def _earlier_packed(path: Path, pk: Pack, stamp) -> bool:
    """True when this machine's stamp proves the file holds an EARLIER packed version, untouched since: the
    stamp says its bytes were a packed version, their sha256 is not the manifest's any more, and the file's
    size and modification time are still the stamp's."""
    if not (isinstance(stamp, dict) and stamp.get("packed") is True
            and _is_hex(stamp.get("sha256")) and stamp.get("sha256") != pk.sha256):
        return False
    try:
        st = path.stat()
    except OSError:
        return False
    return (stat.S_ISREG(st.st_mode) and stamp.get("size") == st.st_size
            and stamp.get("mtime_ns") == st.st_mtime_ns)


# ---------------------------------------------------------------------------
# Stripped packs (local to this copy; see `strip`)
# ---------------------------------------------------------------------------
def _load_stripped(store: Path) -> dict:
    """{pack folder name: record} of the packs whose parts `strip` removed from this copy."""
    try:
        data = json.loads((store / STATE_DIR / STRIPPED_NAME).read_text("utf-8"))
        packs = data.get("packs") if isinstance(data, dict) else None
        return {k: v for k, v in packs.items() if isinstance(v, dict)} if isinstance(packs, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_stripped(store: Path, rec: dict) -> None:
    """Write the stripped record; an empty record removes the file."""
    path = store / STATE_DIR / STRIPPED_NAME
    if not rec:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return
    _write_bytes_atomic(path, _json_bytes({"format": STRIPPED_FORMAT, "packs": rec}))


def _parts_missing(pk: Pack) -> bool:
    """True when at least one of the pack's zip parts is not on disk."""
    return any(not (pk.dir / p["file"]).is_file() for p in pk.parts)


def _is_stripped(pk: Pack, rec) -> bool:
    """True when `strip` recorded this pack AND some of its parts are really gone (parts put back -- by
    `pack`, or copied in by hand -- make it an ordinary pack again)."""
    if not rec:
        return False
    entry = rec.get(pk.dir.name)
    if not isinstance(entry, dict) or entry.get("sha256", pk.sha256) != pk.sha256:
        return False
    return _parts_missing(pk)


def _clean_stripped(store: Path, packs: list, rec: dict) -> bool:
    """Drop the records of packs that are gone or whole again. -> True when the record changed."""
    by_name = {pk.dir.name: pk for pk in packs}
    keep = {name: entry for name, entry in rec.items()
            if name in by_name and _is_stripped(by_name[name], rec)}
    if keep == rec:
        return False
    _save_stripped(store, keep)
    rec.clear()
    rec.update(keep)
    return True


def _quick_state(path: Path, pk: Pack, stamp) -> str:
    """ok / missing / pointer stub / changed / unverified / not a file -- without reading a big file."""
    try:
        st = path.stat()
    except FileNotFoundError:
        return "missing"
    if not stat.S_ISREG(st.st_mode):
        return "not a file"
    if st.st_size <= POINTER_MAX and _pointer_text(path, st.st_size) is not None:
        return "pointer stub"
    if (isinstance(stamp, dict) and stamp.get("size") == st.st_size
            and stamp.get("mtime_ns") == st.st_mtime_ns):
        return "ok" if stamp.get("sha256") == pk.sha256 else "changed"
    if st.st_size != pk.size:
        return "changed"
    return "unverified"


# ---------------------------------------------------------------------------
# Restoring a file from its parts
# ---------------------------------------------------------------------------
def _clear_stale_temps(target: Path, say: _Say) -> None:
    """Remove this target's temp files left by an interrupted unpack (older than STALE_TEMP_SECONDS)."""
    if not target.parent.is_dir():
        return
    pattern = glob.escape(str(target.parent)) + os.sep + glob.escape(target.name + TEMP_TAG) + "*"
    for name in glob.glob(pattern):
        try:
            if time.time() - os.stat(name).st_mtime > STALE_TEMP_SECONDS:
                os.unlink(name)
                say.info(f"large files: removed a left-over temp file {name}")
        except OSError:
            pass


def _restore(root: Path, pk: Pack, rel: str, say: _Say) -> None:
    """Write the target from its parts. Raises on any problem; never leaves a partial target behind."""
    target = root / rel
    for part in pk.parts:
        zp = pk.dir / part["file"]
        try:
            zsize = zp.stat().st_size
        except FileNotFoundError:
            raise FileNotFoundError(f"part {zp.name} of {pk.dir.name} is missing") from None
        if zsize != part["zip_size"] or _hash_file(zp) != part["zip_sha256"]:
            raise ValueError(f"part {zp.name} of {pk.dir.name} is damaged (its sha256 does not match)")
    anchor = target.parent
    while not anchor.exists() and anchor != anchor.parent:
        anchor = anchor.parent
    free = shutil.disk_usage(anchor).free
    if free < pk.size + SPACE_MARGIN:
        raise OSError(f"not enough free disk space: needs {_mb(pk.size + SPACE_MARGIN)} MB, "
                      f"{_mb(free)} MB free")
    _clear_stale_temps(target, say)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f"{target.name}{TEMP_TAG}{os.getpid()}")
    progress = _Progress(say, f"unpacking {rel}", pk.size)
    try:
        whole = hashlib.sha256()
        done = 0
        with open(tmp, "wb") as out:
            for part in pk.parts:
                with zipfile.ZipFile(pk.dir / part["file"]) as zf:
                    info = zf.getinfo(part["member"])
                    if info.file_size != part["length"]:
                        raise ValueError(f"{part['file']}: its member holds {info.file_size:,} bytes, "
                                         f"the manifest says {part['length']:,}")
                    h, n = hashlib.sha256(), 0
                    with zf.open(info) as src:
                        while True:
                            block = src.read(READ_BLOCK)
                            if not block:
                                break
                            n += len(block)
                            if n > part["length"]:
                                raise ValueError(f"{part['file']}: more bytes than the manifest says")
                            out.write(block)
                            h.update(block)
                            whole.update(block)
                            progress(len(block))
                    if n != part["length"] or h.hexdigest() != part["sha256"]:
                        raise ValueError(f"{part['file']}: the unpacked bytes do not match the manifest")
                    done += n
        if done != pk.size or whole.hexdigest() != pk.sha256:
            raise ValueError("the joined file does not match the manifest's size and sha256")
        os.replace(tmp, target)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def _keep_pointer(store: Path, rel: str, data: bytes) -> Path:
    """Save a replaced pointer stub's text under .state/replaced_pointers/ (the path in the file name)."""
    folder = store / STATE_DIR / POINTERS_DIR
    folder.mkdir(parents=True, exist_ok=True)
    base = rel.replace("/", "__")
    n = 1
    while True:
        cand = folder / (f"{base}.pointer.txt" if n == 1 else f"{base}.pointer.{n}.txt")
        if not cand.exists():
            cand.write_bytes(data)
            return cand
        if cand.read_bytes() == data:
            return cand
        n += 1


# ---------------------------------------------------------------------------
# THE SELF-CHECK (the master browser calls this at every start; `unpack` too)
# ---------------------------------------------------------------------------
def env_mode(environ=None) -> str:
    """The self-check's mode from ``LARGE_FILES_SELF_CHECK``: ``0`` -> "off", ``size`` -> "size" (case and
    surrounding spaces ignored), anything else or unset -> "full"."""
    value = str((os.environ if environ is None else environ).get(ENV_SWITCH, "") or "").strip()
    if value == "0":
        return MODE_OFF
    if value.lower() == MODE_SIZE:
        return MODE_SIZE
    return MODE_FULL


def _note(problems, path: str, state: str, detail: str) -> None:
    """One entry of the self-check's ``problems`` list (see self_check)."""
    if problems is not None:
        problems.append({"path": path, "state": state, "detail": detail})


def self_check(root, log=None, *, honour_env: bool = True, mode: str | None = None,
               managed_prefixes=(), update_stale: bool = False) -> dict:
    """Restore every packed file that is missing (or is a Git LFS pointer stub). NEVER RAISES.

    For each target of each manifest under ``<root>/_large_files/``:
      missing        -> the parts are verified, free space checked, the file rebuilt beside the target as
                        ``<name>.unpacking.<pid>``, verified (size + sha256) and moved into place.
      pointer stub   -> its text is kept under ``.state/replaced_pointers/``, then restored like a missing one.
                        When ``.state/`` cannot be written (a read-only store) the text is not kept (a warning
                        says so) and the restore goes on.
      ok             -> size + modification time match this machine's stamp of the right sha256: nothing read.
      no stamp       -> full mode: the file is hashed once; a match writes the stamp, so the next start reads
                        nothing. Size mode: a right size counts as ok, counted under "size_only"; never hashed.
      changed        -> a warning by name; the file is NEVER overwritten (refresh it with `pack <path>`).
      earlier packed -> "changed" too, unless ``update_stale``: this machine's stamp proves the file holds an
                        earlier packed version, untouched since (a newer manifest arrived, for example by a
                        pull), so it is restored from the new parts like a missing one, counted under
                        "updated". A file changed on this machine (no such proof) is never overwritten.
      stripped       -> missing (or a pointer stub) while `strip` removed the pack's parts from this copy:
                        a warning, counted under "stripped_missing"; nothing can be restored.
    READ-ONLY COPIES (a read-only mount of the repository, a container's `:ro` database folders): nothing is
    ever written into a folder this process cannot write --
      missing / pointer stub in a read-only folder -> a warning naming the fix (restore it on the writable
                        side with `python large_file_packs.py unpack`), counted under "read_only"; no part is read.
      no stamp while the store itself is read-only -> the stamp could not be remembered, so the file is NOT
                        hashed at every start: a right size counts as ok, counted under "size_only"
                        (`python large_file_packs.py check` hashes everything when wanted).
    MODE: ``mode`` when given ("full", "size" or "off"); else ``LARGE_FILES_SELF_CHECK`` (see env_mode) when
    ``honour_env``; else "full" (``honour_env=False`` is the explicit `unpack` command). "off" does nothing.
    Targets under managed_prefixes belong to an already verified deployment release and are
    counted as delegated without reading or restoring their writable copies. This is opt-in;
    explicit unpack/check commands retain their complete original-file behavior.
    Every error is caught per target, logged and counted. No store, no manifests -> no-op.
    Returns {"ok", "unpacked", "pointer_stubs", "changed", "read_only", "size_only", "errors", "targets",
    "skipped", "seconds", "mode", "stripped_missing", "problems", "delegated", "updated"} ("size_only" files are
    also counted in "ok"; "updated" stays 0 without ``update_stale``). "problems" lists {"path", "state",
    "detail"} with state "missing_read_only",
    "pointer_stub_read_only", "changed", "stripped_missing" or "error" ("path" is the target, or
    ``_large_files/<folder>`` for a broken pack, or "" when the whole check stopped).
    """
    t0 = time.monotonic()
    result = {"ok": 0, "unpacked": 0, "pointer_stubs": 0, "changed": 0, "read_only": 0, "size_only": 0,
              "errors": 0, "targets": 0, "skipped": False, "seconds": 0.0,
              "mode": MODE_FULL, "stripped_missing": 0, "problems": [], "delegated": [], "updated": 0}
    problems_out = result["problems"]
    say = _Say(log)
    try:
        if not isinstance(managed_prefixes, (tuple, list)):
            raise ValueError("managed_prefixes must be a list or tuple of relative directory paths")
        prefixes = tuple(_check_rel(prefix) for prefix in managed_prefixes)
        if mode is None:
            mode = env_mode() if honour_env else MODE_FULL
        if mode not in (MODE_FULL, MODE_SIZE, MODE_OFF):
            raise ValueError(f"unknown mode {mode!r} (full, size or off)")
        result["mode"] = mode
        if mode == MODE_OFF:
            result["skipped"] = True
            say.info(f"large files: self-check switched off ({ENV_SWITCH}=0)")
            return result
        root = Path(root)
        store = root / STORE_DIR
        if not store.is_dir():
            return result
        packs, problems = _load_packs(store)
        if not packs and not problems:
            return result
        for folder, msg in problems:
            result["errors"] += 1
            say.error(f"large files: {STORE_DIR}/{folder} {msg}")
            _note(problems_out, f"{STORE_DIR}/{folder}", "error", msg)
        claims, conflicts = _claims(packs)
        bad = set()
        for rel, msg in conflicts:
            result["errors"] += 1
            bad.add(rel)
            say.error(f"large files: {rel} {msg} -- left alone")
            _note(problems_out, rel, "error", f"{msg} -- left alone")
        stamps = _load_stamps(store)
        before = dict(stamps)
        stamps_writable = _can_write_dir(store / STATE_DIR)
        stripped = _load_stripped(store)
        for pk in packs:
            for rel in pk.targets:
                result["targets"] += 1
                if rel in bad or claims.get(rel) is not pk:
                    continue
                if any(rel.startswith(prefix + "/") for prefix in prefixes):
                    result["delegated"].append(rel)
                    result["targets"] -= 1
                    continue
                try:
                    outcome = _settle(root, store, pk, rel, stamps, say, stamps_writable,
                                      mode=mode, stripped=stripped, problems=problems_out,
                                      update_stale=update_stale)
                    if outcome == "size_only":
                        result["ok"] += 1
                    result[outcome] += 1
                except Exception as exc:  # noqa: BLE001 -- per target: log, count, go on
                    result["errors"] += 1
                    say.error(f"large files: {rel}: {exc}")
                    _note(problems_out, rel, "error", str(exc))
        if stamps != before:
            try:
                _save_stamps(store, stamps)
            except Exception as exc:  # noqa: BLE001
                say.warning(f"large files: could not save the stamps ({exc}); the next start re-checks")
    except Exception as exc:  # noqa: BLE001 -- the server must start whatever happens
        result["errors"] += 1
        say.error(f"large files: self-check stopped early: {exc}")
        _note(problems_out, "", "error", f"self-check stopped early: {exc}")
    result["seconds"] = round(time.monotonic() - t0, 2)
    line = (f"large files: {result['targets']} checked -- {result['ok']} ok, {result['unpacked']} unpacked, "
            f"{result['pointer_stubs']} pointer stubs replaced, {result['changed']} changed (not overwritten), "
            f"{result['errors']} errors ({result['seconds']:.1f} s)")
    if result["updated"]:
        line += f"; {result['updated']} updated from an earlier packed version"
    if result["delegated"]:
        line += f"; {len(result['delegated'])} targets managed by the output release"
    if result["read_only"]:
        line += (f"; {result['read_only']} missing in read-only folders (restore them on the writable side: "
                 f"`python large_file_packs.py unpack`)")
    if result["stripped_missing"]:
        line += (f"; {result['stripped_missing']} missing whose parts were stripped from this copy "
                 f"(not restored)")
    if result["size_only"]:
        if result["mode"] == MODE_SIZE:
            line += f"; {result['size_only']} checked by size only ({ENV_SWITCH}=size)"
        else:
            line += f"; {result['size_only']} checked by size only (read-only store)"
    if result["targets"] or result["errors"] or result["delegated"]:
        warn = result["changed"] or result["errors"] or result["read_only"] or result["stripped_missing"]
        (say.warning if warn else say.info)(line)
    return result


def _can_write_dir(folder: Path) -> bool:
    """True when this process may create files in FOLDER, or in its nearest existing parent when FOLDER does
    not exist yet. A read-only mount answers False (POSIX access(2) reports EROFS); on Windows a folder always
    answers True and a refused write still surfaces as an error of that target."""
    anchor = Path(folder)
    while not anchor.exists() and anchor != anchor.parent:
        anchor = anchor.parent
    return os.access(anchor, os.W_OK)


def _settle(root: Path, store: Path, pk: Pack, rel: str, stamps: dict, say: _Say,
            stamps_writable: bool = True, *, mode: str = MODE_FULL, stripped=None, problems=None,
            update_stale: bool = False) -> str:
    """One target of the self-check -> 'ok' | 'unpacked' | 'pointer_stubs' | 'changed' | 'read_only' |
    'size_only' | 'stripped_missing' | 'updated'. Raises on errors. Never writes into a folder this process
    cannot write. ``mode`` "size" never hashes an existing file; ``stripped`` is the record of `strip`;
    ``problems`` (a list) receives the {"path", "state", "detail"} entries of self_check; ``update_stale``
    replaces a file whose stamp proves it holds an earlier packed version, untouched since."""
    path = root / rel
    stamp = stamps.get(rel)
    state = _quick_state(path, pk, stamp)
    if state == "ok":
        if stamps_writable and stamp.get("packed") is not True:
            stamps[rel] = dict(stamp, packed=True)      # a stamp of an older version of this tool
        return "ok"
    if state == "not a file":
        raise ValueError("is not a regular file -- left alone")
    if state in ("missing", "pointer stub") and _is_stripped(pk, stripped):
        if state == "missing":
            say.warning(f"large files: {rel} is missing and its parts were stripped from this copy -- "
                        f"not restored")
            _note(problems, rel, "stripped_missing",
                  "missing, and its parts were stripped from this copy -- not restored")
        else:
            say.warning(f"large files: {rel} is a Git LFS pointer stub, not the data, and its parts were "
                        f"stripped from this copy -- not restored")
            _note(problems, rel, "stripped_missing",
                  "a Git LFS pointer stub, not the data, and its parts were stripped from this copy -- "
                  "not restored")
        return "stripped_missing"
    if state in ("missing", "pointer stub") and not _can_write_dir(path.parent):
        what = "is missing" if state == "missing" else "is a Git LFS pointer stub, not the data,"
        say.warning(f"large files: {rel} {what} and its folder is read-only here -- not restored; restore it "
                    f"on the writable side (`python large_file_packs.py unpack` in a writable copy)")
        if state == "missing":
            _note(problems, rel, "missing_read_only",
                  "missing, and its folder is read-only here -- restore it on the writable side "
                  "(`python large_file_packs.py unpack`)")
        else:
            _note(problems, rel, "pointer_stub_read_only",
                  "a Git LFS pointer stub, not the data, and its folder is read-only here -- restore it on "
                  "the writable side (`python large_file_packs.py unpack`)")
        return "read_only"
    if state == "unverified" and (mode == MODE_SIZE or not stamps_writable):
        return "size_only"
    if state in ("missing", "pointer stub"):
        outcome = "unpacked"
        if state == "pointer stub":
            outcome = "pointer_stubs"
            data = path.read_bytes()
            kept = None
            if stamps_writable:
                try:
                    kept = _keep_pointer(store, rel, data)
                except OSError:
                    kept = None
            oid = _pointer_oid(data)
            same = ("it named these same bytes" if oid == pk.sha256
                    else f"it named another version (sha256 {oid[:12] if oid else 'unknown'}...)")
            if kept is not None:
                say.warning(f"large files: {rel} is a Git LFS pointer stub, not the data ({same}); "
                            f"its text is kept at {kept}; restoring the packed file")
            else:
                say.warning(f"large files: {rel}: could not keep the pointer text (read-only store)")
                say.warning(f"large files: {rel} is a Git LFS pointer stub, not the data ({same}); "
                            f"restoring the packed file")
        say.info(f"large files: restoring {rel} ({_mb(pk.size)} MB from {len(pk.parts)} parts)")
        _restore(root, pk, rel, say)
        if stamps_writable:     # a read-only store keeps no stamps (no "could not save the stamps" warning)
            stamps[rel] = _stamp(path.stat(), pk.sha256, packed=True)
        return outcome
    if state == "unverified":
        say.info(f"large files: verifying {rel} ({_mb(pk.size)} MB, first check on this machine)")
        st = path.stat()
        sha = _hash_file(path, _Progress(say, f"verifying {rel}", st.st_size))
        # the same bytes as an earlier stamp of a packed version (only the time changed) stay "packed"
        earlier = isinstance(stamp, dict) and stamp.get("packed") is True and stamp.get("sha256") == sha
        stamps[rel] = stamp = _stamp(st, sha, packed=sha == pk.sha256 or earlier)
        if sha == pk.sha256:
            return "ok"
    elif (update_stale and stamps_writable and isinstance(stamp, dict) and stamp.get("packed") is True
          and stamp.get("sha256") != pk.sha256):
        st = path.stat()
        if (stat.S_ISREG(st.st_mode) and st.st_size == stamp.get("size")
                and st.st_mtime_ns != stamp.get("mtime_ns")):
            # the size of the earlier packed version this machine stamped, only the time differs: hash it once
            say.info(f"large files: verifying {rel} ({_mb(st.st_size)} MB): its time changed since this machine "
                     f"stamped an earlier packed version")
            sha = _hash_file(path, _Progress(say, f"verifying {rel}", st.st_size))
            stamps[rel] = stamp = _stamp(st, sha, packed=sha == stamp.get("sha256"))
    if _earlier_packed(path, pk, stamp):
        if not update_stale:
            say.warning(f"large files: {rel} holds an earlier packed version (sha256 {stamp['sha256'][:12]}...), "
                        f"unchanged since this machine restored, verified or packed it -- not overwritten; "
                        f"`python large_file_packs.py unpack --update-stale` replaces it with the packed version")
            _note(problems, rel, "changed", "holds an earlier packed version -- not overwritten "
                                            "(`python large_file_packs.py unpack --update-stale` replaces it)")
            return "changed"
        if not _can_write_dir(path.parent):
            raise PermissionError("holds an earlier packed version, but its folder is read-only here -- not "
                                  "updated; update it on the writable side")
        say.info(f"large files: updating {rel}: it holds an earlier packed version (sha256 "
                 f"{stamp['sha256'][:12]}...), unchanged since this machine restored, verified or packed it "
                 f"({_mb(pk.size)} MB from {len(pk.parts)} parts)")
        _restore(root, pk, rel, say)
        if stamps_writable:
            stamps[rel] = _stamp(path.stat(), pk.sha256, packed=True)
        return "updated"
    if update_stale:
        say.warning(f"large files: {rel} was changed on this machine: it is neither its packed version nor an "
                    f"earlier packed version restored or verified here -- not overwritten")
    else:
        say.warning(f"large files: {rel} changed since it was packed -- not overwritten; run "
                    f"`python large_file_packs.py pack {rel}` to refresh its parts")
    _note(problems, rel, "changed", "changed since it was packed -- not overwritten")
    return "changed"


# ---------------------------------------------------------------------------
# Building a pack
# ---------------------------------------------------------------------------
def _zipinfo(member: str) -> zipfile.ZipInfo:
    """A zip entry with a fixed date and fixed attributes (the same bytes give the same zip)."""
    zi = zipfile.ZipInfo(member, date_time=ZIP_DATE)
    zi.compress_type = zipfile.ZIP_DEFLATED
    zi.create_system = 3                 # "unix", so the attributes below mean rw-r--r-- everywhere
    zi.external_attr = 0o100644 << 16
    if hasattr(zi, "compress_level"):    # Python 3.13+
        zi.compress_level = COMPRESS_LEVEL
    else:                                # Python 3.7-3.12
        zi._compresslevel = COMPRESS_LEVEL
    return zi


def _write_part(src, offset: int, avail: int, zip_path: Path, member: str, part_limit: int) -> tuple:
    """Write one zip holding the longest slice from ``offset`` that keeps the zip within part_limit.

    Returns (slice length, sha256 of the slice). Deterministic: the stop point depends only on the bytes,
    the limit and zlib's output.
    """
    block = min(READ_BLOCK, max(1024, part_limit // 32))
    reserve = min(READ_BLOCK, max(2048, part_limit // 8))
    max_len = min(avail, MAX_MEMBER)
    while True:
        src.seek(offset)
        h, n = hashlib.sha256(), 0
        with open(zip_path, "wb") as raw, zipfile.ZipFile(raw, "w", allowZip64=False) as zf, \
                zf.open(_zipinfo(member), "w") as w:
            while n < max_len:
                want = min(block, max_len - n)
                if n and raw.tell() + want + want // 256 + 64 + reserve > part_limit:
                    break
                data = src.read(want)
                if len(data) != want:
                    raise OSError("the file got shorter while it was being packed")
                w.write(data)
                h.update(data)
                n += want
        zsize = zip_path.stat().st_size
        if zsize <= part_limit:
            return n, h.hexdigest()
        if n <= 1:
            raise RuntimeError(f"cannot fit even one byte into a zip of {part_limit:,} bytes")
        max_len = max(1, min(n - 1, n * part_limit // zsize * 9 // 10))


def _verify_part(zip_path: Path, member: str, length: int, raw_sha: str, whole) -> tuple:
    """Read a written part back: one member, the right length and sha256. Feeds ``whole``. -> (size, sha)."""
    zsize = zip_path.stat().st_size
    zsha = _hash_file(zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        infos = zf.infolist()
        if len(infos) != 1 or infos[0].filename != member or infos[0].file_size != length:
            raise RuntimeError(f"{zip_path.name} does not read back as written")
        h = hashlib.sha256()
        with zf.open(infos[0]) as src:
            while True:
                block = src.read(READ_BLOCK)
                if not block:
                    break
                h.update(block)
                whole.update(block)
    if h.hexdigest() != raw_sha:
        raise RuntimeError(f"{zip_path.name} does not unpack to the bytes that went in")
    return zsize, zsha


def _build_pack(root: Path, store: Path, rel: str, part_limit: int, threshold: int, say: _Say) -> tuple:
    """Pack one file into a new store folder. -> (Pack, the stat the pack was made from)."""
    tmp, manifest, st0 = _cut_parts(root, store, rel, part_limit, threshold, say)
    try:
        final = store / _pack_folder_name(PurePosixPath(rel).name, manifest["sha256"])
        if final.exists():
            raise FileExistsError(f"{final.name} already exists with other contents -- check it by hand")
        os.replace(tmp, final)
        return Pack(final, manifest), st0
    except BaseException:
        try:
            _remove_pack_dir(tmp)
        except OSError:
            pass
        raise


def _refill_parts(root: Path, store: Path, pk: Pack, rel: str, say: _Say) -> os.stat_result:
    """Cut the parts of a stripped pack again from its file (which must match the manifest), with the
    pack's own part limit, and put them into the pack's folder. -> the stat the parts were made from."""
    tmp, manifest, st0 = _cut_parts(root, store, rel, pk.m["part_limit"], pk.m["threshold"], say)
    try:
        if manifest["sha256"] != pk.sha256 or manifest["size"] != pk.size:
            raise RuntimeError("the file no longer matches its pack")
        for part in pk.parts:              # whatever the strip left behind
            try:
                (pk.dir / part["file"]).unlink()
            except FileNotFoundError:
                pass
        for part in manifest["parts"]:
            os.replace(tmp / part["file"], pk.dir / part["file"])
        pk.m["parts"] = manifest["parts"]
        pk.save()
        return st0
    finally:
        try:
            _remove_pack_dir(tmp)
        except OSError:
            pass


def _cut_parts(root: Path, store: Path, rel: str, part_limit: int, threshold: int, say: _Say) -> tuple:
    """Cut one file into verified zip parts in a temp folder of the store (manifest written there too).
    -> (the temp folder, the manifest, the stat the parts were made from). Removes the folder on error."""
    path = root / rel
    st0 = path.stat()
    size = st0.st_size
    base = PurePosixPath(rel).name
    tmp = store / STATE_DIR / f"packing.{os.getpid()}"
    if tmp.exists():
        _remove_pack_dir(tmp)
    tmp.mkdir(parents=True)
    try:
        whole = hashlib.sha256()
        parts, offset, index = [], 0, 1
        progress = _Progress(say, f"packing {rel}", size)
        with open(path, "rb") as src:
            while offset < size:
                fname, member = f"part_{index:03d}.zip", f"{base}.part_{index:03d}"
                zpath = tmp / fname
                length, raw_sha = _write_part(src, offset, size - offset, zpath, member, part_limit)
                zsize, zsha = _verify_part(zpath, member, length, raw_sha, whole)
                if zsize >= HARD_LIMIT or zsize > part_limit:
                    raise RuntimeError(f"{fname} came out at {zsize:,} bytes -- over the limit")
                parts.append({"file": fname, "member": member, "offset": offset, "length": length,
                              "sha256": raw_sha, "zip_size": zsize, "zip_sha256": zsha})
                offset += length
                index += 1
                progress(length)
        st1 = path.stat()
        if (st1.st_size, st1.st_mtime_ns) != (st0.st_size, st0.st_mtime_ns):
            raise RuntimeError("the file changed while it was being packed")
        sha = whole.hexdigest()
        manifest = _check_manifest({"format": FORMAT, "targets": [rel], "size": size, "sha256": sha,
                                    "parts": parts, "threshold": threshold, "part_limit": part_limit})
        _write_bytes_atomic(tmp / MANIFEST_NAME, _json_bytes(manifest))
        return tmp, manifest, st0
    except BaseException:
        try:
            _remove_pack_dir(tmp)
        except OSError:
            pass
        raise


def _release(pk: Pack, rel: str) -> None:
    """Take a target out of a pack; an emptied manifest is saved first, the folder is pruned later."""
    pk.targets.remove(rel)
    pk.save()


def _refill(root, store, pk: Pack, rel: str, stamps: dict, say: _Say) -> str:
    """Give a stripped pack its parts back from its (verified) file. -> 'packed'."""
    st_used = _refill_parts(root, store, pk, rel, say)
    stamps[rel] = _stamp(st_used, pk.sha256, packed=True)
    say.info(f"refilled  {rel} -> {pk.dir.name} ({len(pk.parts)} parts made again; `strip` had removed "
             f"them from this copy)")
    return "packed"


def _pack_one(root, store, rel, packs, claims, stamps, threshold, part_limit, say, stripped=None) -> str:
    """-> 'unchanged' | 'joined' | 'packed'. Raises on problems. A stripped pack (see `strip`) whose file
    still matches gets its parts made again ('packed')."""
    path = root / rel
    try:
        st = path.stat()
    except FileNotFoundError:
        raise FileNotFoundError("not found") from None
    if not stat.S_ISREG(st.st_mode):
        raise ValueError("is not a regular file")
    if _pointer_text(path, st.st_size) is not None:
        raise ValueError("is a Git LFS pointer stub, not the data -- restore the real file first "
                         "(python large_file_packs.py unpack)")
    cur = claims.get(rel)
    sha = None
    if cur is not None and st.st_size == cur.size:
        stamp = stamps.get(rel)
        if (isinstance(stamp, dict) and stamp.get("size") == st.st_size
                and stamp.get("mtime_ns") == st.st_mtime_ns and stamp.get("sha256") == cur.sha256):
            if _is_stripped(cur, stripped):
                return _refill(root, store, cur, rel, stamps, say)
            say.info(f"unchanged {rel}")
            return "unchanged"
        sha = _hash_file(path, _Progress(say, f"hashing {rel}", st.st_size))
        if sha == cur.sha256:
            stamps[rel] = _stamp(st, sha, packed=True)
            if _is_stripped(cur, stripped):
                return _refill(root, store, cur, rel, stamps, say)
            say.info(f"unchanged {rel}")
            return "unchanged"
    twins = [pk for pk in packs if pk is not cur and pk.size == st.st_size]
    if twins:
        if sha is None:
            sha = _hash_file(path, _Progress(say, f"hashing {rel}", st.st_size))
        for pk in twins:
            if pk.sha256 == sha:
                if _is_stripped(pk, stripped):
                    _refill_parts(root, store, pk, rel, say)
                    say.info(f"refilled  {pk.dir.name} from {rel} (`strip` had removed its parts)")
                pk.targets.append(rel)
                pk.save()
                if cur is not None:
                    _release(cur, rel)
                claims[rel] = pk
                stamps[rel] = _stamp(st, sha, packed=True)
                say.info(f"joined    {rel} -> {pk.dir.name} (the same bytes as a file already packed)")
                return "joined"
    new, st_used = _build_pack(root, store, rel, part_limit, threshold, say)
    packs.append(new)
    if cur is not None:
        _release(cur, rel)
    claims[rel] = new
    stamps[rel] = _stamp(st_used, new.sha256, packed=True)
    say.info(f"packed    {rel} -> {new.dir.name} ({len(new.parts)} parts, "
             f"{_mb(new.size)} MB -> {_mb(new.zip_bytes)} MB)")
    return "packed"


def _prune(packs: list, say: _Say) -> list:
    """Remove every pack folder that no target uses any more."""
    removed = []
    for pk in list(packs):
        if pk.targets:
            continue
        if _remove_pack_dir(pk.dir):
            removed.append(pk.dir.name)
            packs.remove(pk)
            say.info(f"removed   {STORE_DIR}/{pk.dir.name} (no file uses it any more)")
        else:
            say.warning(f"{STORE_DIR}/{pk.dir.name} is no longer used but holds other files -- left in place")
    return removed


def pack(root, paths=(), *, scan: bool = False, threshold: int = DEFAULT_THRESHOLD,
         part_limit: int = DEFAULT_PART_LIMIT, log=None) -> dict:
    """Make or refresh packs for ``paths`` (and, with ``scan``, for every tracked file >= threshold plus
    every packed file present on disk). Unchanged files are skipped; a changed file gets a new pack and
    its old folder is removed when nothing else uses it. Rewrites the .gitignore block. Never runs a git
    command that writes. Returns counts, bytes and the lists of paths by outcome."""
    if not MIN_PART_LIMIT <= part_limit < HARD_LIMIT:
        raise ValueError(f"part_limit must be at least {MIN_PART_LIMIT:,} and under {HARD_LIMIT:,} bytes")
    t0 = time.monotonic()
    say = _Say(log)
    root = Path(root)
    store = root / STORE_DIR
    result = {"packed": [], "unchanged": [], "joined": [], "errors": [], "removed": [],
              "gitignore_changed": False, "seconds": 0.0}
    packs, problems = _load_packs(store)
    claims, conflicts = _claims(packs)
    if problems or conflicts:
        for name, msg in problems:
            say.error(f"{STORE_DIR}/{name} {msg}")
        for rel, msg in conflicts:
            say.error(f"{rel} {msg}")
        say.error("nothing packed: repair or remove the folders named above first")
        result["errors"] = [n for n, _ in problems] + [r for r, _ in conflicts]
        return result
    wanted = {_rel_of(root, p) for p in paths}
    if scan:
        wanted |= {rel for rel, _ in find_large_tracked(root, threshold)}
        wanted |= {rel for rel in claims if (root / rel).is_file()}
    store.mkdir(exist_ok=True)
    stamps = _load_stamps(store)
    stripped = _load_stripped(store)
    for rel in sorted(wanted):
        try:
            outcome = _pack_one(root, store, rel, packs, claims, stamps, threshold, part_limit, say,
                                stripped=stripped)
            result[outcome].append(rel)
        except Exception as exc:  # noqa: BLE001 -- one file's problem never stops the others
            result["errors"].append(rel)
            say.error(f"{rel}: {exc}")
    _save_stamps(store, stamps)
    result["removed"] = _prune(packs, say)
    if stripped:
        try:
            _clean_stripped(store, packs, stripped)
        except Exception as exc:  # noqa: BLE001
            say.warning(f"the record of stripped packs was not updated: {exc}")
    try:
        result["gitignore_changed"] = update_gitignore(root, [t for pk in packs for t in pk.targets])
    except Exception as exc:  # noqa: BLE001
        result["errors"].append(".gitignore")
        say.error(f".gitignore not updated: {exc}")
    result["packs"] = len(packs)
    result["parts"] = sum(len(pk.parts) for pk in packs)
    result["data_bytes"] = sum(pk.size for pk in packs)
    result["zip_bytes"] = sum(pk.zip_bytes for pk in packs)
    result["targets"] = sorted(t for pk in packs for t in pk.targets)
    result["seconds"] = round(time.monotonic() - t0, 1)
    return result


def forget(root, paths, log=None) -> dict:
    """Stop packing ``paths``: take them out of their manifests (a pack no file uses is removed), drop their
    stamps and rewrite the .gitignore block. The files themselves are never touched."""
    say = _Say(log)
    root = Path(root)
    store = root / STORE_DIR
    packs, problems = _load_packs(store)
    claims, _ = _claims(packs)
    stamps = _load_stamps(store)
    result = {"forgotten": [], "errors": [], "removed": []}
    for text in paths:
        try:
            rel = _rel_of(root, text)
            pk = claims.pop(rel, None)
            if pk is None:
                raise ValueError("is not in any pack")
            _release(pk, rel)
            stamps.pop(rel, None)
            result["forgotten"].append(rel)
            say.info(f"forgotten {rel} (the file itself is untouched; git no longer ignores it)")
        except Exception as exc:  # noqa: BLE001
            result["errors"].append(text)
            say.error(f"{text}: {exc}")
    if result["forgotten"]:
        _save_stamps(store, stamps)
        result["removed"] = _prune(packs, say)
        stripped = _load_stripped(store)
        if stripped:
            try:
                _clean_stripped(store, packs, stripped)
            except Exception as exc:  # noqa: BLE001
                say.warning(f"the record of stripped packs was not updated: {exc}")
        try:
            if problems:
                raise ValueError("some manifests are unreadable")
            update_gitignore(root, [t for pk in packs for t in pk.targets])
        except Exception as exc:  # noqa: BLE001
            say.warning(f"the .gitignore block was not rewritten: {exc}")
    return result


# ---------------------------------------------------------------------------
# The .gitignore block
# ---------------------------------------------------------------------------
def _gitignore_line(rel: str) -> str:
    """An anchored ignore rule matching exactly this path (gitignore's special characters escaped)."""
    s = "".join("\\" + ch if ch in "\\*?[" else ch for ch in rel)
    stripped = s.rstrip(" ")
    s = stripped + "\\ " * (len(s) - len(stripped))
    return "/" + s


def update_gitignore(root, targets) -> bool:
    """Write the ONE generated block of the root .gitignore -- and of the root .dockerignore when there is
    one; everything outside the block stays byte for byte. Replaced in place when present, appended at the
    end otherwise, removed when nothing is packed. Keeps each file's line ending (CRLF or LF).
    The .dockerignore block leaves the whole store and every packed original out of a container image: the
    originals reach a container through its (read-only) folder mounts, restored beforehand on the writable
    side (``python large_file_packs.py unpack``). -> True when a file changed."""
    root = Path(root)
    rules = sorted({_gitignore_line(t) for t in targets})
    changed = _update_ignore_block(root / ".gitignore", [GITIGNORE_STATE, GITIGNORE_TEMP], rules)
    docker = root / ".dockerignore"
    if docker.is_file():
        changed = _update_ignore_block(docker, [DOCKERIGNORE_STORE, DOCKERIGNORE_TEMP], rules) or changed
    return changed


def _update_ignore_block(path: Path, fixed: list, rules: list) -> bool:
    """The generated block of one ignore file (see update_gitignore). -> True when the file changed."""
    data = path.read_bytes() if path.exists() else b""
    nl = "\r\n" if b"\r\n" in data else "\n"
    text = data.decode("utf-8", "surrogateescape")
    lines = text.splitlines(keepends=True)
    bare = [ln.rstrip("\r\n") for ln in lines]
    block = ""
    if rules:
        block = "".join(ln + nl for ln in [GITIGNORE_BEGIN, *fixed, *rules, GITIGNORE_END])
    if GITIGNORE_BEGIN in bare:
        begin = bare.index(GITIGNORE_BEGIN)
        try:
            end = bare.index(GITIGNORE_END, begin + 1)
        except ValueError:
            raise ValueError(f"{path.name} has the start marker of the large-file block but no end marker "
                             f"({GITIGNORE_END!r}) -- fix it by hand") from None
        new = "".join(lines[:begin]) + block + "".join(lines[end + 1:])
    elif block:
        head = text
        if head and not head.endswith("\n"):
            head += nl
        if head and not head.endswith("\n\n") and not head.endswith("\n\r\n"):
            head += nl
        new = head + block
    else:
        return False
    if new == text:
        return False
    _write_bytes_atomic(path, new.encode("utf-8", "surrogateescape"))
    return True


# ---------------------------------------------------------------------------
# Git (read-only)
# ---------------------------------------------------------------------------
def _git_lines(root: Path, *args: str) -> list:
    proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError("git " + " ".join(args[:2]) + " failed: "
                           + proc.stderr.decode("utf-8", "replace").strip())
    return [p for p in proc.stdout.decode("utf-8", "surrogateescape").split("\0") if p]


class NoGitCheckout(RuntimeError):
    """`scan` (and `pack --scan`) in a copy that has no git repository, or with no git on PATH."""


def _tracked_files(root: Path) -> list:
    """Every path `git ls-files` lists (read-only). Raises NoGitCheckout when ``root`` has no ``.git``
    (a zip or image copy) or git is not on PATH."""
    if not (Path(root) / ".git").exists():
        raise NoGitCheckout(f"scan needs a git checkout: it lists the files git tracks, and {root} has no git "
                            f"repository (a zip or image copy). Nothing to scan here.")
    if shutil.which("git") is None:
        raise NoGitCheckout("scan needs git on PATH")
    return _git_lines(root, "ls-files", "-z")


def find_large_tracked(root, threshold: int = DEFAULT_THRESHOLD) -> list:
    """[(path, size on disk)] for every tracked file of ``threshold`` bytes or more (outside the store).
    One directory listing per folder instead of one stat per file (fast on network shares)."""
    root = Path(root)
    by_dir: dict = {}
    for rel in _tracked_files(root):
        if rel.split("/", 1)[0] == STORE_DIR:
            continue
        d, _, name = rel.rpartition("/")
        by_dir.setdefault(d, set()).add(name)
    found = []
    for d, names in by_dir.items():
        try:
            it = os.scandir(root / d if d else root)
        except OSError:
            continue
        with it:
            for e in it:
                if e.name not in names:
                    continue
                try:
                    if e.is_file(follow_symlinks=False):
                        size = e.stat(follow_symlinks=False).st_size
                        if size >= threshold:
                            found.append((f"{d}/{e.name}" if d else e.name, size))
                except OSError:
                    pass
    return sorted(found)


def _still_tracked(root: Path, targets: list) -> list | None:
    """The targets git still tracks (None when git cannot tell)."""
    try:
        out = set()
        for i in range(0, len(targets), 50):
            out.update(_git_lines(root, "--literal-pathspecs", "ls-files", "-z", "--", *targets[i:i + 50]))
        return sorted(out)
    except Exception:  # noqa: BLE001
        return None


def _quote(rel: str) -> str:
    """A path quoted for both PowerShell and bash."""
    return "'" + rel + "'" if "'" not in rel else '"' + rel + '"'


def git_steps(root, targets: list) -> list:
    """The git commands the owner runs once so the parts replace the big files in git (printed, never run)."""
    tracked = _still_tracked(Path(root), sorted(targets))
    if tracked is None:
        tracked = sorted(targets)
    steps = [f"git rm --cached -- {_quote(rel)}" for rel in tracked]
    steps.append(f"git add -- {STORE_DIR} .gitignore")
    return steps


# ---------------------------------------------------------------------------
# status / check
# ---------------------------------------------------------------------------
def status(root) -> dict:
    """Fast, read-only: every pack, its targets and their states (no big file is read)."""
    root = Path(root)
    store = root / STORE_DIR
    packs, problems = _load_packs(store)
    _, conflicts = _claims(packs)
    problems = [f"{STORE_DIR}/{n} {m}" for n, m in problems] + [f"{r} {m}" for r, m in conflicts]
    stamps = _load_stamps(store)
    stripped = _load_stripped(store)
    rows, n_stripped = [], 0
    for pk in packs:
        is_stripped = _is_stripped(pk, stripped)
        n_stripped += is_stripped
        for part in pk.parts:
            zp = pk.dir / part["file"]
            try:
                if zp.stat().st_size != part["zip_size"]:
                    problems.append(f"{STORE_DIR}/{pk.dir.name}/{part['file']} has the wrong size")
            except FileNotFoundError:
                if not is_stripped:          # parts stripped from this copy are expected to be gone
                    problems.append(f"{STORE_DIR}/{pk.dir.name}/{part['file']} is missing")
        for rel in pk.targets:
            state = _quick_state(root / rel, pk, stamps.get(rel))
            if is_stripped and state == "missing":
                state = "stripped missing"
            rows.append({"target": rel, "pack": pk.dir.name, "size": pk.size, "parts": len(pk.parts),
                         "state": state, "stripped": is_stripped})
    return {"packs": len(packs), "parts": sum(len(pk.parts) for pk in packs),
            "data_bytes": sum(pk.size for pk in packs), "zip_bytes": sum(pk.zip_bytes for pk in packs),
            "rows": sorted(rows, key=lambda r: r["target"]), "problems": problems,
            "stripped_packs": n_stripped}


def check(root, log=None) -> dict:
    """Full, read-only: hash every part and every present target.
    -> {"problems": n, "ok": n, "missing": n, "parts_ok": n, "stripped": n} ("stripped" = packs whose parts
    `strip` removed from this copy: their missing parts are expected, not problems)."""
    say = _Say(log)
    root = Path(root)
    packs, problems = _load_packs(root / STORE_DIR)
    _, conflicts = _claims(packs)
    stripped = _load_stripped(root / STORE_DIR)
    out = {"problems": 0, "ok": 0, "missing": 0, "parts_ok": 0, "stripped": 0}
    for name, msg in problems:
        out["problems"] += 1
        say.error(f"{STORE_DIR}/{name} {msg}")
    for rel, msg in conflicts:
        out["problems"] += 1
        say.error(f"{rel} {msg}")
    for pk in packs:
        is_stripped = _is_stripped(pk, stripped)
        if is_stripped:
            out["stripped"] += 1
            say.info(f"stripped  {STORE_DIR}/{pk.dir.name}: parts stripped (expected in this copy)")
        for part in pk.parts:
            zp = pk.dir / part["file"]
            if is_stripped and not zp.is_file():
                continue
            try:
                good = zp.stat().st_size == part["zip_size"] and _hash_file(zp) == part["zip_sha256"]
            except FileNotFoundError:
                good = False
            if good:
                out["parts_ok"] += 1
            else:
                out["problems"] += 1
                say.error(f"{STORE_DIR}/{pk.dir.name}/{part['file']} is missing or damaged")
        for rel in pk.targets:
            path = root / rel
            state = _quick_state(path, pk, None)
            if state == "missing" and is_stripped:
                out["missing"] += 1
                say.info(f"missing   {rel} -- its parts were stripped from this copy, so it cannot be "
                         f"restored here")
            elif state == "missing":
                out["missing"] += 1
                say.info(f"missing   {rel} -- `python large_file_packs.py unpack` restores it")
            elif state in ("pointer stub", "not a file"):
                out["problems"] += 1
                say.error(f"{rel} is a {state}, not the packed file")
            elif state != "changed" and _hash_file(path, _Progress(say, f"hashing {rel}", pk.size)) == pk.sha256:
                out["ok"] += 1
                say.info(f"ok        {rel}")
            else:
                out["problems"] += 1
                say.error(f"{rel} changed since it was packed (run `python large_file_packs.py pack {rel}`)")
    return out


# ---------------------------------------------------------------------------
# strip (for a zip or image copy whose big files are already restored)
# ---------------------------------------------------------------------------
def _strip_reason(root: Path, pk: Pack, claims: dict, bad: set, stamps: dict, say: _Say) -> str | None:
    """Why this pack must keep its parts (None when every file of it is present and verified). A file
    without a matching stamp is hashed once; its new stamp lands in ``stamps``."""
    if not pk.targets:
        return "no file uses it"
    for rel in pk.targets:
        if rel in bad or claims.get(rel) is not pk:
            return f"{rel} is claimed by another pack"
        path = root / rel
        state = _quick_state(path, pk, stamps.get(rel))
        if state == "ok":
            continue
        if state == "missing":
            return f"{rel} is missing"
        if state == "pointer stub":
            return f"{rel} is a Git LFS pointer stub, not the data"
        if state == "not a file":
            return f"{rel} is not a regular file"
        if state == "unverified":
            st = path.stat()
            sha = _hash_file(path, _Progress(say, f"verifying {rel}", st.st_size))
            stamps[rel] = _stamp(st, sha, packed=sha == pk.sha256)
            if sha == pk.sha256:
                continue
        return f"{rel} does not match its manifest"
    return None


def strip(root, *, dry_run: bool = False, force: bool = False, log=None) -> dict:
    """Delete the zip parts of every pack whose files are present and verified, keep the manifests, and
    record the packs in ``.state/stripped.json`` -- for a zip or image copy that no longer needs them.

    A file is verified by this machine's stamp of the right sha256, else by a full hash. The record is
    written BEFORE any part is deleted. A pack keeps its parts when a file of it is missing, is a pointer
    stub or does not match. Refused (nothing read, nothing deleted) when ``<root>/.git`` exists, unless
    ``force``: in a git checkout the parts are tracked files. ``dry_run`` changes nothing. One line per pack:
    ``strip: <folder>: <n> parts removed (<mb> MB)`` or ``strip: <folder>: kept (<reason>)``.
    Returns {"refused": None or the reason, "stripped": [folders], "kept": [(folder, reason)], "parts": n,
    "bytes": n, "dry_run": bool}.
    """
    say = _Say(log)
    root = Path(root)
    store = root / STORE_DIR
    result = {"refused": None, "stripped": [], "kept": [], "parts": 0, "bytes": 0, "dry_run": bool(dry_run)}
    if (root / ".git").exists() and not force:
        result["refused"] = (f"{root} is a git checkout (it has a .git folder), where the zip parts are tracked "
                             f"files -- nothing deleted; add --force to strip anyway")
        return result
    packs, problems = _load_packs(store)
    claims, conflicts = _claims(packs)
    bad = {rel for rel, _ in conflicts}
    stamps = _load_stamps(store)
    before = dict(stamps)
    rec = _load_stripped(store)

    def keep(folder: str, reason: str) -> None:
        result["kept"].append((folder, reason))
        say.info(f"strip: {folder}: kept ({reason})")

    for name, msg in problems:
        keep(name, msg)
    for pk in packs:
        folder = pk.dir.name
        present = [p for p in pk.parts if (pk.dir / p["file"]).is_file()]
        if not present and _is_stripped(pk, rec):
            result["stripped"].append(folder)
            say.info(f"strip: {folder}: 0 parts removed ({_mb(0)} MB)")
            continue
        try:
            reason = _strip_reason(root, pk, claims, bad, stamps, say)
        except Exception as exc:  # noqa: BLE001 -- one pack's problem never stops the others
            reason = f"could not verify it: {exc}"
        if reason:
            keep(folder, reason)
            continue
        n, nbytes = len(present), sum(p["zip_size"] for p in present)
        if dry_run:
            result["stripped"].append(folder)
            result["parts"] += n
            result["bytes"] += nbytes
            say.info(f"strip: {folder}: {n} parts would be removed ({_mb(nbytes)} MB)")
            continue
        entry = {"target": sorted(pk.targets)[0], "sha256": pk.sha256, "parts": [p["file"] for p in pk.parts]}
        if len(pk.targets) > 1:
            entry["targets"] = sorted(pk.targets)
        try:
            rec[folder] = entry
            _save_stripped(store, rec)
        except Exception as exc:  # noqa: BLE001
            rec.pop(folder, None)
            keep(folder, f"could not write {STORE_DIR}/{STATE_DIR}/{STRIPPED_NAME}: {exc}")
            continue
        removed, rbytes, err = 0, 0, None
        for p in present:
            try:
                (pk.dir / p["file"]).unlink()
            except FileNotFoundError:
                continue
            except OSError as exc:
                err = f"could not delete {p['file']}: {exc}; {removed} parts removed"
                break
            removed += 1
            rbytes += p["zip_size"]
        result["parts"] += removed
        result["bytes"] += rbytes
        if err:
            keep(folder, err)
            continue
        result["stripped"].append(folder)
        say.info(f"strip: {folder}: {removed} parts removed ({_mb(rbytes)} MB)")
    if not dry_run:
        try:
            _clean_stripped(store, packs, rec)
        except Exception as exc:  # noqa: BLE001
            say.warning(f"the record of stripped packs was not tidied: {exc}")
        if stamps != before:
            try:
                _save_stamps(store, stamps)
            except Exception as exc:  # noqa: BLE001
                say.warning(f"could not save the stamps ({exc})")
    return result


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------
_HELP = """\
Big files (100 MB or more) are kept in git as zip parts under 100 MB in the folder _large_files/,
because GitHub refuses bigger files and this repository pushes only original files (no Git LFS).
The master browser restores any missing big file from its parts each time it starts.
The manual: _large_files/README.md.

commands:
  status   Quick look, reads no big file: every packed file and its state
           (ok / missing / pointer stub / changed / unverified).
  check    Full check, changes nothing: hashes every part and every packed file present.
           Exit code 1 when anything is damaged or changed (a missing file is only noted).
  unpack   Restore every packed file that is missing or is a Git LFS pointer stub -- the same
           routine the master browser runs at start. Never overwrites a file that changed.
           --update-stale: also replace a file that holds an EARLIER packed version, proven by
           this machine's stamp (it restored or verified that version, and the file is untouched
           since) -- the update after a pull brought newer parts. A file changed on this machine
           is still never overwritten: each one is named on a line "large files: changed on this
           machine, not overwritten: <path>" and the exit code is 3.
  pack     Make or refresh the parts: `pack PATH ...` for named files, `pack --scan` for every
           tracked file of 100,000,000 bytes or more plus every file already packed. Unchanged
           files are skipped. Rewrites the generated block of .gitignore and prints the git
           commands to run once. Never runs a git command that writes.
  scan     List tracked files of 100,000,000 bytes or more that are not packed yet
           (exit code 1 when there are any). Needs a git checkout: in a zip or image copy it
           says so and exits with code 2 (so does `pack --scan`).
  forget   Stop packing the named files: their parts are removed and git no longer ignores
           them. The files themselves are not touched.
  strip    For a zip or image copy whose big files are already restored: delete the zip parts of
           every pack whose files are present and verified, keep the manifests, and record the
           packs in _large_files/.state/stripped.json. --dry-run changes nothing. Refused (exit
           code 2) where a .git folder exists, unless --force. Exit code 1 when some pack kept its
           parts (a file of it is missing or does not match). A missing file of a stripped pack
           cannot be restored in that copy; `pack` of its file makes the parts again.

the self-check at master start (environment variable LARGE_FILES_SELF_CHECK):
  0        off.
  size     a file with no stamp of this machine counts as ok when its size is right (never
           hashed); missing files and pointer stubs are still restored.
  unset    full (anything else too): such a file is hashed once and stamped.
  `unpack` always runs the full check.

examples:
  python large_file_packs.py status
  python large_file_packs.py pack --scan
  python large_file_packs.py pack data/big_table.db
  python large_file_packs.py strip --dry-run
"""


def _print_status(root: Path) -> int:
    rep = status(root)
    print(f"Large-file packs in {root / STORE_DIR}: {rep['packs']} packs, {rep['parts']} parts, "
          f"{_mb(rep['zip_bytes'])} MB of zips holding {_mb(rep['data_bytes'])} MB of data")
    counts: dict = {}
    for r in rep["rows"]:
        counts[r["state"]] = counts.get(r["state"], 0) + 1
        print(f"  {r['state']:<13} {_mb(r['size']):>10} MB  {r['parts']:>3} parts  {r['target']}"
              + ("  (parts stripped)" if r.get("stripped") else ""))
    for p in rep["problems"]:
        print("  PROBLEM: " + p)
    print("Summary: " + (", ".join(f"{n} {s}" for s, n in sorted(counts.items())) or "nothing packed"))
    if counts.get("unverified"):
        print("  (unverified = not yet proven on this machine; the next master start or `check` hashes it)")
    if rep.get("stripped_packs"):
        print(f"  ({rep['stripped_packs']} packs with their parts stripped = `strip` removed their zip parts from "
              f"this copy, as expected; a missing file of such a pack cannot be restored here)")
    return 1 if rep["problems"] else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="large_file_packs.py", description=_HELP,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=str(Path(__file__).absolute().parent),
                        help="the repository folder (default: the folder of this file)")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True
    sub.add_parser("status", help="quick look at every packed file (reads no big file)")
    sub.add_parser("check", help="hash every part and every packed file present (changes nothing)")
    p_unpack = sub.add_parser("unpack", help="restore every missing packed file (what the master does at start)")
    p_unpack.add_argument("--update-stale", action="store_true",
                          help="also replace a file whose stamp of this machine proves it holds an earlier "
                               "packed version, untouched since (after a newer manifest arrived); a file changed "
                               "on this machine is never overwritten: it is named, and the exit code is 3")
    p_pack = sub.add_parser("pack", help="make or refresh parts for named files or with --scan")
    p_pack.add_argument("paths", nargs="*", help="files to pack, relative to the repository folder")
    p_pack.add_argument("--scan", action="store_true",
                        help="also every tracked file at or over --threshold and every file already packed")
    p_pack.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD,
                        help=f"size in bytes that --scan treats as big (default {DEFAULT_THRESHOLD:,})")
    p_pack.add_argument("--part-limit", type=int, default=DEFAULT_PART_LIMIT,
                        help=f"largest size of one zip part in bytes (default {DEFAULT_PART_LIMIT:,}; "
                             f"always under {HARD_LIMIT:,})")
    p_scan = sub.add_parser("scan", help="list tracked big files that are not packed yet")
    p_scan.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD,
                        help=f"size in bytes treated as big (default {DEFAULT_THRESHOLD:,})")
    p_forget = sub.add_parser("forget", help="stop packing the named files (the files stay)")
    p_forget.add_argument("paths", nargs="+", help="packed files, relative to the repository folder")
    p_strip = sub.add_parser("strip", help="delete the zip parts of packs whose files are present and verified "
                                           "(for a zip or image copy)")
    p_strip.add_argument("--dry-run", action="store_true", help="say what would be removed; change nothing")
    p_strip.add_argument("--force", action="store_true",
                         help="strip even though the folder is a git checkout (has a .git folder)")
    args = parser.parse_args(argv)
    root = Path(args.root)
    out = _Printer()

    if args.command == "status":
        return _print_status(root)
    if args.command == "check":
        res = check(root, log=out)
        print(f"Check: {res['ok']} files ok, {res['missing']} missing, {res['parts_ok']} parts ok, "
              f"{res['problems']} problems"
              + (f", {res['stripped']} packs with their parts stripped" if res.get("stripped") else ""))
        return 1 if res["problems"] else 0
    if args.command == "strip":
        res = strip(root, dry_run=args.dry_run, force=args.force, log=out)
        if res["refused"]:
            print("strip refused: " + res["refused"], file=sys.stderr, flush=True)
            return 2
        if not res["stripped"] and not res["kept"]:
            print("Nothing to strip: no packs in " + str(root / STORE_DIR))
            return 0
        verb = "would be stripped" if res["dry_run"] else "stripped"
        print(f"Strip: {len(res['stripped'])} packs {verb} ({res['parts']} parts, {_mb(res['bytes'])} MB), "
              f"{len(res['kept'])} kept their parts")
        return 1 if res["kept"] else 0
    if args.command == "unpack":
        res = self_check(root, log=out, honour_env=False, update_stale=args.update_stale)
        if not res["targets"] and not res["errors"]:
            print("Nothing to unpack: no packs in " + str(root / STORE_DIR))
        if res["errors"] or res["read_only"] or res["stripped_missing"]:
            return 1
        if args.update_stale and res["changed"]:
            # one line per file, for people and for scripts: STALE_KEPT_PREFIX + the path
            for p in res["problems"]:
                if p.get("state") == "changed":
                    print(STALE_KEPT_PREFIX + p["path"], flush=True)
            return 3
        return 0
    if args.command == "scan":
        try:
            packs, _ = _load_packs(root / STORE_DIR)
            claims, _ = _claims(packs)
            found = [(r, s) for r, s in find_large_tracked(root, args.threshold) if r not in claims]
        except NoGitCheckout as exc:
            print(str(exc), file=sys.stderr, flush=True)
            return 2
        except Exception as exc:  # noqa: BLE001
            out.error(str(exc))
            return 2
        for rel, size in found:
            print(f"  {_mb(size):>10} MB  {rel}")
        print(f"{len(found)} tracked files of {args.threshold:,} bytes or more are not packed yet"
              + (" -- pack them with: python large_file_packs.py pack --scan" if found else "."))
        return 1 if found else 0
    if args.command == "forget":
        res = forget(root, args.paths, log=out)
        if res["forgotten"]:
            print("Next (once): git add -- _large_files .gitignore   -- then commit. The forgotten files are "
                  "no longer ignored: delete them, or add them back to git if they are small enough.")
        return 1 if res["errors"] else 0
    # pack
    if not args.paths and not args.scan:
        print("Nothing named: give file paths, or --scan (see --help). Refreshing the .gitignore block only.")
    try:
        res = pack(root, args.paths, scan=args.scan, threshold=args.threshold,
                   part_limit=args.part_limit, log=out)
    except NoGitCheckout as exc:
        print(str(exc), file=sys.stderr, flush=True)
        return 2
    except Exception as exc:  # noqa: BLE001
        out.error(str(exc))
        return 2
    print(f"Pack: {len(res['packed'])} packed, {len(res['joined'])} joined an identical pack, "
          f"{len(res['unchanged'])} unchanged, {len(res['errors'])} errors, "
          f"{len(res['removed'])} unused packs removed ({res['seconds']:.0f} s)")
    if "packs" in res:
        print(f"Store: {res['packs']} packs, {res['parts']} parts, {_mb(res['zip_bytes'])} MB of zips "
              f"for {_mb(res['data_bytes'])} MB of data; .gitignore "
              + ("updated" if res["gitignore_changed"] else "already up to date"))
        steps = git_steps(root, res["targets"])
        if len(steps) > 1 or res["packed"] or res["joined"] or res["removed"] or res["gitignore_changed"]:
            print("\nNext, once, from the repository folder (this tool never runs them):")
            for s in steps:
                print("  " + s)
            print("Then commit as usual. `git rm --cached` only takes the big files out of git's index;"
                  " they stay on disk and .gitignore now keeps them out.")
    return 1 if res["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
