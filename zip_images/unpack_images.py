#!/usr/bin/env python3
"""
unpack_images.py -- build an application folder and its Python environment from "zip images".
===================================================================================================

WHAT THIS IS. A folder of zip images holds every file of one or more commits of a git repository as ordinary
zip files, each under 100 MB, plus this script. The script checks the zips, unpacks them into a folder,
restores the repository's big files, installs the Python packages the repository asks for and checks that the
application can start. It needs only Python 3.8 or newer: no git, no unzip program, no other package. It is
the SAME file as ``zip_images/unpack_images.py`` in the repository that made the images, and it is also the
ONE SOURCE OF TRUTH for the image format: the packer imports its constants and readers from here.

THE IMAGE FOLDER (made by ``python -m zip_images pack``)::

    latest.json                      which manifest "latest" means
    manifests/<commit12>.json        one per packed commit: its compartments and environment (format 2; a
                                     format-1 manifest also listed every file, which outgrew 100 MB)
    compartments/<kind>-<hash>.json  one per compartment content (the packer's record): the file rows of
                                     the compartments, read by load_manifest since format 2
    zips/<name>__<key12>_<NNN>.zip   the zip images
    unpack_images.py                 this script
    setup_from_zips.sh, Dockerfile, README.md

COMPARTMENTS. The files are grouped into compartments: a folder of the repository, or the loose files directly
inside a folder that was split. Each compartment has a content key (for a whole folder: its git tree id), and
its zips hold its files with paths RELATIVE TO THE COMPARTMENT FOLDER. A file bigger than one zip is split into
byte chunks named ``<name>.zipimg-chunk-001-of-003`` and so on, joined again here. The manifest lists every
file with its size, sha256 and git mode; every zip with its size and sha256.

COMMANDS (``python3 unpack_images.py --help``):
  install (the default)  check the zips, unpack, restore big files, install packages, check the start
  update                 bring an installed folder to another manifest, rewriting only changed compartments
  verify                 check every zip and every file inside them without writing anything
  check                  compare an installed folder with the manifest it was installed from
  start                  start the application of an installed folder
  info                   show what this image folder holds

PYTHON PACKAGES. ``pip install -r`` of the requirement files the manifest names. When the manifest records
per-platform constraints files ("constraints_by_arch", e.g. the lock files of a Dockerfile's
``-c docker/constraints/linux-${TARGETARCH}-py3.12.txt``), the one of this machine is added as ``-c``: Linux on
x86_64 -> "amd64", Linux on aarch64 / arm64 -> "arm64"; on any other system, or with another Python than the
files were made for, no constraints file is used (one line says so) and pip chooses the versions. The
manifest's "pip_options" (package-index options such as ``--extra-index-url URL``) are passed on online installs.
When the manifest records a pinned pip ("pip_self": the source Dockerfile's ``pip install -c <file> pip``), a
virtual environment first gets that pip (offline: from the packed wheels); if that fails, one warning, and the
packages are installed with the environment's own pip. A system or --target install never changes pip.

BIG FILES. After unpacking, ``<dest>/large_file_packs.py --root <dest> unpack`` rebuilds the big files from their
zip parts. ``install --strip-large-parts`` then runs ``large_file_packs.py --root <dest> strip``, which deletes
the zip parts of every big file that is present and verified (their manifests stay): an image need not carry
the same bytes twice. The generated Dockerfile is its only user; ``check`` counts stripped parts as expected.

EXIT CODES:
  0 success                                   5 restoring the big files failed
  1 wrong usage or an unexpected error        6 installing the Python packages failed
  2 the manifest is missing or unreadable     7 the start check failed
  3 a zip is missing or damaged               8 refused: folder not empty, local changes, or no disk space
  4 unsafe content refused, or an unpacked file does not match its sha256
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import uuid
import subprocess
import sys
import sysconfig
import time
import zipfile
import zlib
from pathlib import Path

# ---------------------------------------------------------------------------------------------------------
# THE FORMAT (the packer imports these; change them only together with a new FORMAT string)
# ---------------------------------------------------------------------------------------------------------
FORMAT = "zip-images/2"                 # 2: the manifest file holds no file rows (inflate_manifest)
FORMATS = ("zip-images/1", FORMAT)     # what this reader accepts; a format-1 manifest carries its rows inline
RECORD_FORMAT = "zip-images-compartment/1"
LATEST_FORMAT = "zip-images-latest/1"
INSTALLED_FORMAT = "zip-images-installed/1"

LATEST_NAME = "latest.json"
MANIFESTS_DIR = "manifests"
RECORDS_DIR = "compartments"
ZIPS_DIR = "zips"
STATE_DIR = ".zip_images"            # inside an installed folder
INSTALLED_NAME = "installed.json"
EXTRA_REQ_NAME = "extra-requirements.txt"
WHEELS_DIR = "wheels"
TARGET_SITE = "site-packages"
VENV_DIR = ".venv"

HARD_LIMIT = 100_000_000             # no zip may reach this size
DEFAULT_LIMIT = 95_000_000           # the packer's default largest zip

KIND_TREE = "tree"                   # a whole folder of the repository (key = its git tree id)
KIND_FILES = "files"                 # the loose files directly inside a folder that was split
KIND_WHEELS = "wheels"               # downloaded wheels for an offline install (not part of the tree)
KINDS = (KIND_TREE, KIND_FILES, KIND_WHEELS)
FILES_LABEL = "(files)"              # compartment name of loose files: "<folder>/(files)", the root: "(files)"
WHEELS_NAME = "(wheels)"

MODE_FILE = "100644"
MODE_EXEC = "100755"
MODE_LINK = "120000"
MODES = (MODE_FILE, MODE_EXEC, MODE_LINK)

CHUNK_TAG = ".zipimg-chunk-"
READ_BLOCK = 1 << 20
SPACE_MARGIN = 256 * 1024 * 1024

EXIT_OK, EXIT_ERROR, EXIT_MANIFEST, EXIT_PARTS = 0, 1, 2, 3
EXIT_UNSAFE, EXIT_LARGE, EXIT_ENV, EXIT_CHECK, EXIT_REFUSED = 4, 5, 6, 7, 8

_HEX64 = re.compile(r"[0-9a-f]{64}")
_ZIP_NAME = re.compile(r"[A-Za-z0-9._-]+\.zip")
_STALE_TEMP = ".zipimg-new."


class ManifestError(Exception):
    """The manifest is missing, unreadable or inconsistent (exit code 2)."""


class PartError(Exception):
    """A zip is missing or damaged (exit code 3)."""


class UnsafeError(Exception):
    """Content that would escape the folder, or bytes that do not match the manifest (exit code 4)."""


# ---------------------------------------------------------------------------------------------------------
# Small shared helpers (the packer uses them too)
# ---------------------------------------------------------------------------------------------------------
def say(msg: str = "") -> None:
    print(msg, flush=True)


def warn(msg: str) -> None:
    print("WARNING: " + msg, flush=True)


def error(msg: str) -> None:
    print("ERROR: " + msg, flush=True)


def mb(n: int) -> str:
    return "{:,.1f}".format(n / 1_000_000)


def is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def is_hex64(x) -> bool:
    return isinstance(x, str) and _HEX64.fullmatch(x) is not None


def json_bytes(obj) -> bytes:
    """UTF-8, LF, sorted keys, two-space indent: the same data always gives the same bytes."""
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def manifest_bytes(manifest: dict) -> bytes:
    """A manifest as bytes: like json_bytes, but a "files" list holds one file per line; an object without
    the key (a format-2 manifest file, an installed record) is written without it."""
    if "files" not in manifest:
        return json_bytes(manifest)
    files = manifest.get("files") or []
    head = dict(manifest)
    head["files"] = "@FILES@"
    text = json.dumps(head, indent=2, sort_keys=True, ensure_ascii=False)
    lines = ",\n".join("    " + json.dumps(f, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
                       for f in files)
    body = "[\n" + lines + "\n  ]" if files else "[]"
    return (text.replace('"@FILES@"', body, 1) + "\n").encode("utf-8")


def write_atomic(path: Path, data: bytes) -> None:
    _metadata_target(path, create_parents=True)
    tmp = path.with_name(".zipimg-state." + uuid.uuid4().hex)
    try:
        with open(_fs_path(tmp), "xb") as fh:
            fh.write(data)
        _metadata_target(path)
        os.replace(_fs_path(tmp), _fs_path(path))
    except BaseException:
        try:
            os.unlink(_fs_path(tmp))
        except OSError:
            pass
        raise


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(_fs_path(path), "rb") as fh:
        while True:
            block = fh.read(READ_BLOCK)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def chunk_entry(name: str, index: int, count: int) -> str:
    """The zip entry name of chunk ``index`` (1-based) of a file split into ``count`` chunks."""
    return "{}{}{:03d}-of-{:03d}".format(name, CHUNK_TAG, index, count)


def check_rel(path, what: str = "path") -> str:
    """A path as the manifest holds it: relative, forward slashes, no '.', '..' or empty steps."""
    if not isinstance(path, str) or not path:
        raise UnsafeError("an empty {}".format(what))
    if "\\" in path or "\0" in path:
        raise UnsafeError("{} {!r}: backslash or NUL".format(what, path))
    if path.startswith("/") or re.match(r"[A-Za-z]:", path):
        raise UnsafeError("{} {!r}: absolute paths are refused".format(what, path))
    steps = path.split("/")
    if any(s in ("", ".", "..") for s in steps):
        raise UnsafeError("{} {!r}: empty, '.' and '..' steps are refused".format(what, path))
    if os.name == "nt" and any(":" in s for s in steps):
        raise UnsafeError("{} {!r}: ':' is not allowed in a file name on Windows".format(what, path))
    return path


def free_bytes(path) -> int:
    """Free bytes the current user may write at ``path`` (quota-aware on Windows)."""
    p = Path(path)
    while not p.exists() and p != p.parent:
        p = p.parent
    if os.name == "nt":
        try:
            import ctypes
            free = ctypes.c_ulonglong(0)
            if ctypes.windll.kernel32.GetDiskFreeSpaceExW(str(p), ctypes.byref(free), None, None):
                return int(free.value)
        except Exception:  # noqa: BLE001 -- fall back to shutil
            pass
    return shutil.disk_usage(str(p)).free


def comp_rel(comp: dict, path: str) -> str:
    """A file's path relative to its compartment folder (= its zip entry name)."""
    base = comp.get("path") or ""
    return path[len(base) + 1:] if base else path


# ---------------------------------------------------------------------------------------------------------
# Manifests
# ---------------------------------------------------------------------------------------------------------
def _check_parts(comp: dict) -> None:
    parts = comp.get("parts")
    if not isinstance(parts, list) or not parts:
        raise ManifestError("compartment {!r}: no parts".format(comp.get("name")))
    for p in parts:
        if not isinstance(p, dict) or not isinstance(p.get("file"), str) or not _ZIP_NAME.fullmatch(p["file"]):
            raise ManifestError("compartment {!r}: a part has a bad file name".format(comp.get("name")))
        if not is_int(p.get("size")) or not 0 < p["size"] < HARD_LIMIT or not is_hex64(p.get("sha256")):
            raise ManifestError("compartment {!r}: part {} has a bad size or sha256".format(comp.get("name"),
                                                                                          p["file"]))


def _check_file(fd: dict, where: str) -> None:
    if not is_int(fd.get("size")) or fd["size"] < 0 or not is_hex64(fd.get("sha256")):
        raise ManifestError("{}: bad size or sha256".format(where))
    if fd.get("mode") not in MODES:
        raise ManifestError("{}: unknown mode {!r}".format(where, fd.get("mode")))
    chunks = fd.get("chunks", 0)
    if not is_int(chunks) or chunks < 0 or chunks == 1:
        raise ManifestError("{}: bad chunk count".format(where))


def validate_manifest(m) -> dict:
    """Check a manifest; raise ManifestError (bad structure) or UnsafeError (a hostile path)."""
    if not isinstance(m, dict):
        raise ManifestError("not a JSON object")
    if m.get("format") not in FORMATS:
        raise ManifestError("format is {!r}, expected one of {} (a newer unpack_images.py may be needed)".format(
            m.get("format"), ", ".join(repr(f) for f in FORMATS)))
    comps = m.get("compartments")
    if not isinstance(comps, list):
        raise ManifestError("'compartments' is not a list")
    by_name = {}
    for c in comps:
        if not isinstance(c, dict) or not isinstance(c.get("name"), str) or c["name"] in by_name:
            raise ManifestError("a compartment has no name or a repeated one")
        if c.get("kind") not in KINDS or not isinstance(c.get("key"), str):
            raise ManifestError("compartment {!r}: bad kind or key".format(c["name"]))
        if c["kind"] == KIND_WHEELS:
            files = c.get("files")
            if not isinstance(files, list):
                raise ManifestError("the wheels compartment has no file list")
            for fd in files:
                if not isinstance(fd, dict):
                    raise ManifestError("the wheels compartment lists a non-object")
                name = check_rel(fd.get("name"), "wheel name")
                if "/" in name:
                    raise UnsafeError("wheel name {!r}: must be a plain file name".format(name))
                _check_file(fd, "wheel " + name)
        else:
            path = c.get("path")
            if not isinstance(path, str):
                raise ManifestError("compartment {!r}: no path".format(c["name"]))
            if path:
                check_rel(path, "compartment path")
        _check_parts(c)
        by_name[c["name"]] = c
    files = m.get("files")
    if not isinstance(files, list):
        raise ManifestError("'files' is not a list")
    seen = set()
    for fd in files:
        if not isinstance(fd, dict):
            raise ManifestError("'files' lists a non-object")
        path = check_rel(fd.get("path"))
        if path in seen:
            raise ManifestError("{!r} is listed twice".format(path))
        seen.add(path)
        if path.split("/", 1)[0] in (STATE_DIR, ".git"):
            raise UnsafeError("{!r}: lies inside a reserved folder".format(path))
        _check_file(fd, path)
        comp = by_name.get(fd.get("compartment"))
        if comp is None or comp["kind"] == KIND_WHEELS:
            raise ManifestError("{!r}: unknown compartment {!r}".format(path, fd.get("compartment")))
        base = comp["path"]
        if base and not path.startswith(base + "/"):
            raise UnsafeError("{!r} does not lie inside its compartment folder {!r}".format(path, base))
        if comp["kind"] == KIND_FILES and "/" in comp_rel(comp, path):
            raise ManifestError("{!r}: a loose-files compartment holds only files directly in its folder".format(
                path))
    env = m.get("environment")
    if env is not None and not isinstance(env, dict):
        raise ManifestError("'environment' is not an object")
    if env:
        _check_environment(env)
    return m


PIP_VALUE_OPTIONS = ("--index-url", "--extra-index-url", "--trusted-host")
PIP_FLAG_OPTIONS = ("--pre", "--prefer-binary")
ARCH_NAMES = ("amd64", "arm64")


def _check_environment(env: dict) -> None:
    """Check optional per-platform constraints and tree-stage environment keys when present."""
    by_arch = env.get("constraints_by_arch")
    if by_arch is not None:
        if not isinstance(by_arch, dict):
            raise ManifestError("'constraints_by_arch' is not an object")
        for arch, path in by_arch.items():
            if arch not in ARCH_NAMES:
                raise ManifestError("'constraints_by_arch' names an unknown platform {!r}".format(arch))
            check_rel(path, "constraints file")
    py = env.get("constraints_python")
    if py is not None and not (isinstance(py, str) and re.fullmatch(r"\d+\.\d+", py)):
        raise ManifestError("'constraints_python' is not a version like '3.12'")
    opts = env.get("pip_options")
    if opts is not None:
        if not isinstance(opts, list) or not all(isinstance(x, str) for x in opts):
            raise ManifestError("'pip_options' is not a list of strings")
        i = 0
        while i < len(opts):
            if opts[i] in PIP_VALUE_OPTIONS and i + 1 < len(opts) and not opts[i + 1].startswith("-"):
                i += 2
            elif opts[i] in PIP_FLAG_OPTIONS:
                i += 1
            else:
                raise ManifestError("'pip_options': {!r} is not an allowed package-index option".format(opts[i]))
    ps = env.get("pip_self")
    if ps is not None:
        if not isinstance(ps, dict) or not isinstance(ps.get("spec"), str) or not re.fullmatch(
                r"pip(?:\s*(?:===?|~=|>=|<=|!=|<|>)\s*[0-9][0-9A-Za-z.+!*]*)?", ps["spec"]):
            raise ManifestError("'pip_self' is not {\"spec\": \"pip...\", \"constraints\": [...]}")
        files = ps.get("constraints", [])
        if not isinstance(files, list):
            raise ManifestError("'pip_self.constraints' is not a list of paths")
        for path in files:
            check_rel(path, "pip constraints file")
    lf = env.get("large_files")
    if isinstance(lf, dict) and "strip" in lf and not isinstance(lf["strip"], bool):
        raise ManifestError("'large_files.strip' is not true or false")
    docker = env.get("docker")
    if docker is None:
        return
    if not isinstance(docker, dict):
        raise ManifestError("'environment.docker' is not an object")
    argument_env = docker.get("argument_env", {})
    if not isinstance(argument_env, dict):
        raise ManifestError("'docker.argument_env' is not an object")
    for key, name in argument_env.items():
        if not (isinstance(key, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key)
                and isinstance(name, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name)
                and name in (docker.get("args") or {})):
            raise ManifestError("'docker.argument_env' must map environment names to declared arguments")
    vols = docker.get("volumes")
    if vols is not None and not (isinstance(vols, list) and all(isinstance(v, str) for v in vols)):
        raise ManifestError("'docker.volumes' is not a list of paths")
    cmd = docker.get("cmd")
    if cmd is not None and not (isinstance(cmd, list) and all(isinstance(c, str) for c in cmd)):
        raise ManifestError("'docker.cmd' is not a list of strings")
    tree = docker.get("tree_stage")
    if tree is not None:
        if not isinstance(tree, dict) or not isinstance(tree.get("context_dir"), str):
            raise ManifestError("'docker.tree_stage' has no context folder")
        runs = tree.get("run", [])
        if not isinstance(runs, list) or not all(isinstance(r, str) for r in runs):
            raise ManifestError("'docker.tree_stage.run' is not a list of strings")
        if not isinstance(tree.get("args", {}), dict):
            raise ManifestError("'docker.tree_stage.args' is not an object")
        for cp in tree.get("copies", []) or []:
            if not (isinstance(cp, dict) and isinstance(cp.get("src"), str) and isinstance(cp.get("dst"), str)):
                raise ManifestError("'docker.tree_stage.copies' holds an entry without src / dst")


def load_json(path: Path):
    try:
        with open(_fs_path(path), "rb") as stream:
            return json.load(stream)
    except FileNotFoundError:
        raise ManifestError("{} does not exist".format(path)) from None
    except (OSError, ValueError) as exc:
        raise ManifestError("{} cannot be read: {}".format(path, exc)) from None


def manifest_path(images: Path, which: str = "latest") -> Path:
    """'latest' (latest.json), a commit prefix (manifests/<prefix>*.json) or a path to a manifest file."""
    which = which or "latest"
    if which == "latest":
        latest = load_json(images / LATEST_NAME)
        name = latest.get("manifest") if isinstance(latest, dict) else None
        if not isinstance(name, str) or "/" not in name:
            raise ManifestError("{} does not name a manifest".format(images / LATEST_NAME))
        rel = check_rel(name, "manifest name")
        return images / rel
    p = Path(which)
    if p.suffix == ".json":
        for cand in (p, images / p):
            if cand.is_file():
                return cand
        raise ManifestError("{} does not exist (also not inside {})".format(which, images))
    if not re.fullmatch(r"[0-9a-fA-F]{4,40}", which):
        raise ManifestError("--manifest must be 'latest', a commit id (4 or more hex digits) or a .json file")
    found = sorted((images / MANIFESTS_DIR).glob(which.lower()[:12] + "*.json"))
    if which.lower()[12:]:
        found = [f for f in found if load_json(f).get("commit", "").startswith(which.lower())]
    if len(found) != 1:
        raise ManifestError("{} manifests match {!r} in {}".format(len(found), which, images / MANIFESTS_DIR))
    return found[0]


def record_name(key: str) -> str:
    """The file name of the packer's record of one compartment content (key <kind>:<hash>): <kind>-<hash>.json."""
    return key.replace(":", "-") + ".json"


def record_path(images: Path, key: str) -> Path:
    """The packer's record of one compartment content: compartments/<kind>-<hash>.json."""
    return images / RECORDS_DIR / record_name(key)


def inflate_manifest(images: Path, m) -> dict:
    """A format-2 manifest file holds no "files": the rows are rebuilt here from the compartment records of
    the image folder (the same rows the packer assembled in memory), in path order. A manifest that carries
    its rows (format 1, or one built in memory) is returned as it is."""
    if not isinstance(m, dict) or m.get("files") is not None or not isinstance(m.get("compartments"), list):
        return m
    rows = []
    for c in m["compartments"]:
        if not isinstance(c, dict) or c.get("kind") == KIND_WHEELS:
            continue
        key, base = c.get("key"), c.get("path")
        if not isinstance(key, str) or not re.fullmatch(r"[a-z]+:[0-9a-f]+", key) or not isinstance(base, str):
            raise ManifestError("compartment {!r}: bad key or path".format(c.get("name")))
        rec = load_json(record_path(images, key))
        if not isinstance(rec, dict) or rec.get("format") != RECORD_FORMAT or rec.get("key") != key \
                or not isinstance(rec.get("files"), list) \
                or (isinstance(c.get("file_count"), int) and c["file_count"] != len(rec["files"])):
            raise ManifestError("compartment {!r}: {} is not its record (format, key or file count)".format(
                c.get("name"), record_path(images, key)))
        for f in rec["files"]:
            if not isinstance(f, dict) or not isinstance(f.get("name"), str):
                raise ManifestError("compartment {!r}: a record row has no name".format(c.get("name")))
            fd = {"path": (base + "/" if base else "") + f["name"], "size": f.get("size"),
                  "sha256": f.get("sha256"), "mode": f.get("mode"), "compartment": c.get("name")}
            if f.get("chunks"):
                fd["chunks"] = f["chunks"]
            rows.append(fd)
    rows.sort(key=lambda fd: fd["path"].encode("utf-8", "surrogatepass"))  # the packer's order; validation judges
    m["files"] = rows
    return m


def slim_manifest(m: dict) -> dict:
    """The manifest as the packer stores it (format 2): everything but the file rows."""
    return {k: v for k, v in m.items() if k != "files"}


def load_manifest(images: Path, which: str = "latest") -> tuple:
    path = manifest_path(images, which)
    return path, validate_manifest(inflate_manifest(images, load_json(path)))


def files_by_compartment(m: dict) -> dict:
    """compartment name -> list of file dicts, each with the extra key "name" (its path inside the zips)."""
    comps = {c["name"]: c for c in m["compartments"]}
    out = {name: [] for name in comps}
    for fd in m["files"]:
        comp = comps[fd["compartment"]]
        item = dict(fd)
        item["name"] = comp_rel(comp, fd["path"])
        out[comp["name"]].append(item)
    for c in m["compartments"]:
        if c["kind"] == KIND_WHEELS:
            out[c["name"]] = [dict(fd) for fd in c["files"]]
    return out


def select_compartments(m: dict, only=None) -> list:
    """The tree compartments whose name matches one of the ``only`` globs (all of them without ``only``).
    A glob also matches every compartment below a matching folder name."""
    tree = [c for c in m["compartments"] if c["kind"] != KIND_WHEELS]
    if not only:
        return tree
    chosen = []
    for c in tree:
        name = c["name"]
        for pat in only:
            pat = pat.rstrip("/")
            if fnmatch.fnmatchcase(name, pat) or name.startswith(pat + "/"):
                chosen.append(c)
                break
    return chosen


def wheels_compartment(m: dict):
    for c in m["compartments"]:
        if c["kind"] == KIND_WHEELS:
            return c
    return None


# ---------------------------------------------------------------------------------------------------------
# Reading the zips
# ---------------------------------------------------------------------------------------------------------
def check_part_files(images: Path, comps: list, full: bool = True) -> list:
    """Problems (plain sentences) with the zips of ``comps``: missing, wrong size, wrong sha256."""
    problems, seen = [], set()
    for c in comps:
        for p in c["parts"]:
            if p["file"] in seen:
                continue
            seen.add(p["file"])
            zp = images / ZIPS_DIR / p["file"]
            try:
                size = zp.stat().st_size
            except OSError:
                problems.append("{} is missing (compartment {})".format(p["file"], c["name"]))
                continue
            if size != p["size"]:
                problems.append("{} has {:,} bytes, the manifest says {:,}".format(p["file"], size, p["size"]))
            elif full and sha256_file(zp) != p["sha256"]:
                problems.append("{} is damaged: its sha256 does not match the manifest".format(p["file"]))
    return problems


def iter_events(images: Path, comp: dict, files: list):
    """Stream a compartment's files out of its zips, in zip order.

    Yields ("begin", file dict), then ("data", bytes) blocks, then ("end", file dict) for every file; the
    chunks of a split file are joined into one begin ... end. Any entry the manifest does not expect, a
    repeated entry, a broken chunk order or a missing entry raises UnsafeError; a damaged zip raises
    PartError."""
    expected = {}
    for fd in files:
        name = check_rel(fd["name"], "entry")
        n = fd.get("chunks", 0)
        if n:
            for i in range(1, n + 1):
                expected[chunk_entry(name, i, n)] = (fd, i, n)
        else:
            expected[name] = (fd, 0, 0)
    seen = set()
    open_fd, next_index = None, 0
    for part in comp["parts"]:
        zp = images / ZIPS_DIR / part["file"]
        try:
            zf = zipfile.ZipFile(str(zp))
        except (OSError, zipfile.BadZipFile) as exc:
            raise PartError("{} cannot be opened as a zip: {}".format(part["file"], exc)) from None
        with zf:
            for info in zf.infolist():
                name = info.filename
                if name not in expected or name in seen:
                    raise UnsafeError("{} holds an entry the manifest does not expect: {!r}".format(
                        part["file"], name))
                seen.add(name)
                fd, i, n = expected[name]
                if i <= 1:
                    if open_fd is not None:
                        raise UnsafeError("{}: the chunks of {!r} are incomplete".format(part["file"],
                                                                                     open_fd["name"]))
                    yield "begin", fd
                    if i == 1:
                        open_fd, next_index = fd, 2
                elif open_fd is not fd or i != next_index:
                    raise UnsafeError("{}: chunk {} of {!r} is out of order".format(part["file"], i, fd["name"]))
                else:
                    next_index += 1
                try:
                    with zf.open(info) as src:
                        while True:
                            block = src.read(READ_BLOCK)
                            if not block:
                                break
                            yield "data", block
                except (zipfile.BadZipFile, zlib.error) as exc:
                    raise PartError("{} is damaged at {!r}: {}".format(part["file"], name, exc)) from None
                if i == 0 or i == n:
                    yield "end", fd
                    open_fd = None
    if open_fd is not None or len(seen) != len(expected):
        missing = sorted(set(expected) - seen)[:3]
        raise UnsafeError("compartment {} is incomplete: {} entries missing (for example {})".format(
            comp["name"], len(expected) - len(seen), missing))


def verify_compartment(images: Path, comp: dict, files: list) -> list:
    """Stream every file of a compartment and compare size + sha256 with the manifest. -> problems."""
    problems = []
    h, n, cur = None, 0, None
    for ev, x in iter_events(images, comp, files):
        if ev == "begin":
            h, n, cur = hashlib.sha256(), 0, x
        elif ev == "data":
            n += len(x)
            if n > cur["size"]:
                raise UnsafeError("{!r} holds more bytes than the manifest says".format(cur["name"]))
            h.update(x)
        elif n != cur["size"] or h.hexdigest() != cur["sha256"]:
            problems.append("{} / {}: the bytes do not match the manifest".format(comp["name"], cur["name"]))
    return problems


def verify_images(images: Path, m: dict, comps: list, log=say) -> int:
    """Check every zip of ``comps`` (size + sha256, < 100 MB) and every file inside them. -> exit code."""
    t0 = time.monotonic()
    for c in comps:
        for p in c["parts"]:
            if p["size"] >= HARD_LIMIT:
                log("PROBLEM: {} is {:,} bytes -- zips must stay under {:,}".format(p["file"], p["size"],
                                                                                    HARD_LIMIT))
                return EXIT_PARTS
    problems = check_part_files(images, comps, full=True)
    for p in problems:
        log("PROBLEM: " + p)
    if problems:
        return EXIT_PARTS
    by_comp = files_by_compartment(m)
    nfiles, nbytes = 0, 0
    for k, c in enumerate(comps, 1):
        files = by_comp.get(c["name"], [])
        try:
            bad = verify_compartment(images, c, files)
        except PartError as exc:
            log("PROBLEM: " + str(exc))
            return EXIT_PARTS
        except UnsafeError as exc:
            log("PROBLEM: " + str(exc))
            return EXIT_UNSAFE
        for p in bad:
            log("PROBLEM: " + p)
        if bad:
            return EXIT_UNSAFE
        nfiles += len(files)
        nbytes += sum(f["size"] for f in files)
        if len(comps) > 20 and (k % 25 == 0 or k == len(comps)):
            log("  checked {} of {} compartments ({} MB of files)".format(k, len(comps), mb(nbytes)))
    nparts = len({p["file"] for c in comps for p in c["parts"]})
    log("Verified: {} compartments, {} zips, {:,} files, {} MB -- every sha256 matches ({:.0f} s)".format(
        len(comps), nparts, nfiles, mb(nbytes), time.monotonic() - t0))
    return EXIT_OK


# ---------------------------------------------------------------------------------------------------------
# Writing files safely
# ---------------------------------------------------------------------------------------------------------
def _umask() -> int:
    mask = os.umask(0)
    os.umask(mask)
    return mask


def _fs_path(path) -> str:
    """Extended Windows I/O without changing system long-path settings."""
    value = os.path.abspath(os.fspath(path))
    if os.name != "nt" or value.startswith("\\\\?\\"):
        return value
    return "\\\\?\\UNC\\" + value[2:] if value.startswith("\\\\") else "\\\\?\\" + value


def _linked(info) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _ordinary_directory(path: Path, create: bool = False) -> None:
    """Check existing ancestors before making any missing child directory."""
    path = path.absolute()
    for folder in reversed([path, *path.parents]):
        try:
            info = os.lstat(_fs_path(folder))
        except FileNotFoundError:
            if not create:
                raise
            try:
                os.mkdir(_fs_path(folder))
            except FileExistsError:
                pass
            info = os.lstat(_fs_path(folder))
        if _linked(info) or not stat.S_ISDIR(info.st_mode):
            raise UnsafeError("Expected an ordinary directory: {}".format(folder))


def _replaceable_leaf(path: Path):
    """A leaf symlink can be replaced atomically; it is never followed."""
    try:
        info = os.lstat(_fs_path(path))
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(info.st_mode):
        return info
    if _linked(info) or not stat.S_ISREG(info.st_mode):
        raise UnsafeError("Refusing to replace a directory, junction or special file: {}".format(path))
    return info


def _metadata_target(path: Path, create_parents: bool = False) -> None:
    parent = path.parent
    if not create_parents:
        while not os.path.lexists(_fs_path(parent)) and parent != parent.parent:
            parent = parent.parent
    _ordinary_directory(parent, create=create_parents)
    info = _replaceable_leaf(path)
    if info is not None and _linked(info):
        raise UnsafeError("Installation metadata cannot be a link: {}".format(path))


def _runtime_outputs_present(dest: Path) -> bool:
    path = dest / "_outputs_user"
    try:
        info = os.lstat(_fs_path(path))
    except FileNotFoundError:
        return False
    if _linked(info) or not stat.S_ISDIR(info.st_mode):
        return True
    with os.scandir(_fs_path(path)) as entries:
        return next(entries, None) is not None


def _published_outputs(manifest: dict) -> bool:
    return any(row.get("path", "").startswith("_outputs_user/")
               or row.get("path") == "docker/output_seed_manifest.json"
               for row in manifest.get("files", []))


class Writer:
    """Writes the files of a folder: inside the folder only, sha256 checked, git modes applied."""

    def __init__(self, dest: Path, skip_same: bool = False):
        self.dest = dest.absolute()
        _ordinary_directory(self.dest, create=True)
        self.real = os.path.normcase(os.path.realpath(_fs_path(self.dest)))
        self.ok_dirs = set()
        self.mask = _umask()
        self.skip_same = skip_same       # update: leave a file alone when it already holds these bytes
        self.written = 0
        self.same = 0
        self.links_as_files = 0
        self._cur = None

    def _inside(self, path: str) -> bool:
        real = os.path.normcase(os.path.realpath(_fs_path(path)))
        try:
            return os.path.commonpath((self.real, real)) == self.real
        except ValueError:
            return False

    def _parent_ok(self, target: Path, create: bool = True) -> None:
        parent = target.parent
        if not self._inside(str(parent)):
            raise UnsafeError("{} would be written outside {} (through a link)".format(target, self.dest))
        _ordinary_directory(parent, create=create)

    def begin(self, fd: dict) -> None:
        rel = check_rel(fd["path"])
        target = self.dest.joinpath(*rel.split("/"))
        self._parent_ok(target)
        current = _replaceable_leaf(target)
        if (self.skip_same and fd["mode"] != MODE_LINK and current is not None
                and stat.S_ISREG(current.st_mode) and not _linked(current)):
            if current.st_size == fd["size"] and sha256_file(target) == fd["sha256"]:
                self._cur = {"fd": fd, "target": target, "skip": True, "h": hashlib.sha256(), "n": 0}
                return
        cur = {"fd": fd, "target": target, "skip": False, "h": hashlib.sha256(), "n": 0}
        if fd["mode"] == MODE_LINK:
            cur["buf"] = bytearray()
        else:
            tmp = target.with_name("{}{}".format(_STALE_TEMP, uuid.uuid4().hex))
            cur["tmp"] = tmp
            cur["fh"] = open(_fs_path(tmp), "xb")
        self._cur = cur

    def data(self, block: bytes) -> None:
        cur = self._cur
        cur["n"] += len(block)
        if cur["n"] > cur["fd"]["size"]:
            self.abort()
            raise UnsafeError("{!r} holds more bytes than the manifest says".format(cur["fd"]["path"]))
        cur["h"].update(block)
        if cur["skip"]:
            return
        if "buf" in cur:
            cur["buf"] += block
        else:
            cur["fh"].write(block)

    def end(self) -> None:
        cur, self._cur = self._cur, None
        fd = cur["fd"]
        if cur["n"] != fd["size"] or cur["h"].hexdigest() != fd["sha256"]:
            if "fh" in cur:
                cur["fh"].close()
                _unlink(cur["tmp"])
            raise UnsafeError("{!r}: the unpacked bytes do not match the manifest's sha256".format(fd["path"]))
        if cur["skip"]:
            target = cur["target"]
            self._parent_ok(target, create=False)
            try:
                before = os.lstat(_fs_path(target))
                if _linked(before) or not stat.S_ISREG(before.st_mode):
                    raise UnsafeError("The unchanged target became a link or non-file: {}".format(target))
                digest = sha256_file(target)
                after = os.lstat(_fs_path(target))
            except OSError as exc:
                raise UnsafeError("Cannot revalidate unchanged target: {}".format(target)) from exc
            identity = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
            if (_linked(after) or not stat.S_ISREG(after.st_mode)
                    or identity(before) != identity(after)
                    or after.st_size != fd["size"] or digest != fd["sha256"]):
                raise UnsafeError("The unchanged target changed during extraction: {}".format(target))
            self.same += 1
            return
        target = cur["target"]
        if "buf" in cur:
            self._make_link(fd, target, bytes(cur["buf"]))
        else:
            cur["fh"].close()
            if os.name != "nt":
                os.chmod(_fs_path(cur["tmp"]), (0o777 if fd["mode"] == MODE_EXEC else 0o666) & ~self.mask)
            self._parent_ok(target, create=False)
            _replaceable_leaf(target)
            os.replace(_fs_path(cur["tmp"]), _fs_path(target))
        self.written += 1

    def _make_link(self, fd: dict, target: Path, raw: bytes) -> None:
        link = raw.decode("utf-8", "surrogateescape")
        if not link or link.startswith("/") or "\\" in link or re.match(r"[A-Za-z]:", link) or "\0" in link:
            raise UnsafeError("{!r} is a link to {!r}: absolute links are refused".format(fd["path"], link))
        depth = fd["path"].count("/")
        up = 0
        for step in link.split("/"):
            if step == "..":
                up += 1
                if up > depth:
                    raise UnsafeError("{!r} is a link to {!r}, outside the folder: refused".format(fd["path"], link))
            elif step not in ("", "."):
                depth += 1
        self._parent_ok(target, create=False)
        _replaceable_leaf(target)
        temporary = target.with_name("{}{}".format(_STALE_TEMP, uuid.uuid4().hex))
        try:
            os.symlink(link, _fs_path(temporary))
        except (OSError, NotImplementedError, AttributeError):
            # Keep link text on platforms without symlink support, like Git.
            # Exclusive creation also refuses a partially created link.
            with open(_fs_path(temporary), "xb") as fh:
                fh.write(raw)
            self.links_as_files += 1
        self._parent_ok(target, create=False)
        _replaceable_leaf(target)
        os.replace(_fs_path(temporary), _fs_path(target))

    def abort(self) -> None:
        cur, self._cur = self._cur, None
        if cur and "fh" in cur:
            try:
                cur["fh"].close()
            finally:
                _unlink(cur["tmp"])


def _unlink(path) -> None:
    try:
        os.unlink(_fs_path(path))
    except OSError:
        pass


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(str(path))


def extract_compartment(images: Path, comp: dict, files: list, writer: Writer) -> None:
    try:
        for ev, x in iter_events(images, comp, files):
            if ev == "begin":
                writer.begin(x)
            elif ev == "data":
                writer.data(x)
            else:
                writer.end()
    except BaseException:
        writer.abort()
        raise


def extract_wheels(images: Path, comp: dict, folder: Path) -> list:
    """Unpack the wheels compartment into ``folder`` (flat). -> the wheel paths."""
    files = [dict(fd, path=fd["name"]) for fd in comp["files"]]
    writer = Writer(folder)
    extract_compartment(images, comp, files, writer)
    return [folder / fd["name"] for fd in comp["files"]]


# ---------------------------------------------------------------------------------------------------------
# Big files (the unpacked tree's own large_file_packs.py, when there is one)
# ---------------------------------------------------------------------------------------------------------
def tool_env(**extra) -> dict:
    """The environment for the helper programs (venv, pip, the big-file tool, the compile check): without
    PYTHONPATH / PYTHONHOME, so modules of the unpacked tree never shadow what those programs import."""
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP")}
    env.update(extra)
    return env


def _large_tool(m: dict):
    lf = (m.get("environment") or {}).get("large_files")
    if isinstance(lf, dict) and isinstance(lf.get("tool"), str) and isinstance(lf.get("store"), str):
        return lf
    return None


def restore_large_files(dest: Path, m: dict) -> int:
    """Run ``<dest>/<tool> --root <dest> unpack`` in a subprocess. -> exit code of this script."""
    lf = _large_tool(m)
    if lf is None:
        return EXIT_OK
    tool = dest / check_rel(lf["tool"], "large-file tool")
    if not tool.is_file() or not (dest / lf["store"]).is_dir():
        return EXIT_OK
    say("Restoring the big files with {} (this can take several minutes) ...".format(lf["tool"]))
    rc = subprocess.call([sys.executable, str(tool), "--root", str(dest), "unpack"], cwd=str(dest),
                         env=tool_env(PYTHONDONTWRITEBYTECODE="1"))
    if rc != 0:
        error("restoring the big files failed (exit code {}); the messages above name the file".format(rc))
        return EXIT_LARGE
    return EXIT_OK


def strip_large_parts(dest: Path, m: dict) -> int:
    """Run ``<dest>/<tool> --root <dest> strip`` (delete the zip parts of the restored big files; their
    manifests stay). -> exit code of this script. A pack the tool keeps (its file is missing or does not
    verify) is a warning: its parts simply stay."""
    lf = _large_tool(m)
    if lf is None:
        say("Big files: --strip-large-parts: these images have no big-file tool -- nothing to strip.")
        return EXIT_OK
    if lf.get("strip") is not True:
        say("Big files: --strip-large-parts: {} of this commit has no `strip` command -- the zip parts stay.".format(
            lf["tool"]))
        return EXIT_OK
    tool = dest / check_rel(lf["tool"], "large-file tool")
    if not tool.is_file() or not (dest / lf["store"]).is_dir():
        return EXIT_OK
    say("Removing the zip parts of the restored big files ({} strip) ...".format(lf["tool"]))
    rc = subprocess.call([sys.executable, str(tool), "--root", str(dest), "strip"], cwd=str(dest),
                         env=tool_env(PYTHONDONTWRITEBYTECODE="1"))
    if rc == 1:
        warn("some big files kept their zip parts (the lines above say why)")
        return EXIT_OK
    if rc != 0:
        error("removing the zip parts failed (exit code {}); the messages above say why".format(rc))
        return EXIT_LARGE
    return EXIT_OK


def stripped_parts(dest: Path, m: dict) -> set:
    """The paths of the zip parts that ``strip`` removed from ``dest`` (read from its stripped record)."""
    lf = _large_tool(m)
    if lf is None:
        return set()
    try:
        store = check_rel(lf["store"], "large-file store")
        data = json.loads((dest / store / ".state" / "stripped.json").read_bytes().decode("utf-8"))
    except (OSError, ValueError, UnsafeError):
        return set()
    packs = data.get("packs") if isinstance(data, dict) else None
    out = set()
    for folder, entry in (packs.items() if isinstance(packs, dict) else ()):
        if isinstance(folder, str) and "/" not in folder and isinstance(entry, dict):
            for part in entry.get("parts") or []:
                if isinstance(part, str) and "/" not in part:
                    out.add("{}/{}/{}".format(store, folder, part))
    return out


def _pack_targets(dest: Path, store: str) -> dict:
    """{target: sha256} of every large-file pack manifest present under ``<dest>/<store>/``."""
    out = {}
    folder = dest / store
    if not folder.is_dir():
        return out
    for mf in sorted(folder.glob("*/manifest.json")):
        try:
            data = json.loads(mf.read_bytes().decode("utf-8"))
            for t in data.get("targets") or []:
                if isinstance(t, str) and is_hex64(data.get("sha256")):
                    out[t] = data["sha256"]
        except (OSError, ValueError, AttributeError):
            continue
    return out


def _drop_stale_originals(dest: Path, store: str, old: dict, new: dict) -> list:
    """Before an update's restore: delete a restored big file whose pack changed, when it still holds the OLD
    packed bytes (so the restore can write the new version). A file edited by hand is left alone."""
    dropped = []
    stamps = {}
    try:
        data = json.loads((dest / store / ".state" / "stamps.json").read_bytes().decode("utf-8"))
        stamps = data.get("stamps") or {}
    except (OSError, ValueError, AttributeError):
        pass
    for target, sha in old.items():
        if new.get(target) == sha:
            continue
        try:
            path = dest / check_rel(target, "large-file target")
        except UnsafeError:
            continue
        if not path.is_file():
            continue
        st = path.stat()
        stamp = stamps.get(target) if isinstance(stamps, dict) else None
        if (isinstance(stamp, dict) and stamp.get("size") == st.st_size and stamp.get("mtime_ns") == st.st_mtime_ns
                and stamp.get("sha256") == sha):
            same = True
        else:
            same = sha256_file(path) == sha
        if same:
            path.unlink()
            dropped.append(target)
        else:
            warn("{} is not the packed version any more -- left alone (the new version is not restored)".format(
                target))
    return dropped


# ---------------------------------------------------------------------------------------------------------
# The Python environment
# ---------------------------------------------------------------------------------------------------------
def _venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _externally_managed() -> bool:
    """PEP 668: the running interpreter refuses `pip install` outside a virtual environment."""
    if sys.prefix != getattr(sys, "base_prefix", sys.prefix):
        return False
    try:
        return (Path(sysconfig.get_path("stdlib")) / "EXTERNALLY-MANAGED").is_file()
    except Exception:  # noqa: BLE001
        return False


def _make_venv(venv: Path) -> bool:
    if os.environ.get("ZIP_IMAGES_TEST_NO_VENV") == "1":     # test hook: behave as if venv were missing
        return False
    py = _venv_python(venv)
    if py.exists():
        return True
    say("Creating the virtual environment {} ...".format(venv))
    proc = subprocess.run([sys.executable, "-m", "venv", str(venv)], stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, env=tool_env())
    ok = proc.returncode == 0 and py.exists()
    if ok:
        ok = subprocess.run([str(py), "-m", "pip", "--version"], stdout=subprocess.DEVNULL, env=tool_env(),
                            stderr=subprocess.DEVNULL).returncode == 0
    if not ok:
        tail = proc.stdout.decode("utf-8", "replace").strip().splitlines()[-1:] if proc.stdout else []
        say("  a virtual environment cannot be made here ({})".format(tail[0] if tail else "no pip inside it"))
        shutil.rmtree(str(venv), ignore_errors=True)
    return ok


def env_fingerprint(m: dict) -> str:
    """What decides the installed packages: requirement files, extra requirements, wheels."""
    env = m.get("environment") or {}
    keep = {"requirements": env.get("requirements"), "constraints": env.get("constraints") or [],
            "requirements_sha256": env.get("requirements_sha256"),
            "extra_requirements": env.get("extra_requirements"),
            "wheels": (wheels_compartment(m) or {}).get("key")}
    for key in ("constraints_by_arch", "constraints_python", "pip_options", "pip_self"):
        if env.get(key):                      # only when present: an older manifest keeps its fingerprint
            keep[key] = env[key]
    return hashlib.sha256(json_bytes(keep)).hexdigest()


def host_arch(system: str = None, machine: str = None):
    """'amd64' / 'arm64' for Linux on x86_64 / aarch64 (arm64), else None."""
    system = platform.system() if system is None else system
    machine = platform.machine() if machine is None else machine
    if str(system).lower() != "linux":
        return None
    mach = str(machine).lower()
    if mach in ("x86_64", "amd64"):
        return "amd64"
    if mach in ("aarch64", "arm64"):
        return "arm64"
    return None


def pick_constraints(env: dict, system: str = None, machine: str = None, python=None) -> tuple:
    """(the per-platform constraints file of this machine or None, the line that says which and why; None
    when the manifest has no per-platform files). ``python`` = (major, minor) of the Python that installs;
    a file made for another Python is not used."""
    by_arch = env.get("constraints_by_arch") or {}
    if not by_arch:
        return None, None
    system = platform.system() if system is None else system
    machine = platform.machine() if machine is None else machine
    arch = host_arch(system, machine)
    pinned = " and ".join("Linux " + a for a in ARCH_NAMES if a in by_arch)
    if arch is None:
        return None, ("Python packages: no constraints file for {} on {} (the pinned versions are for {}); pip "
                      "chooses the versions".format(system or "this system", machine or "this machine", pinned))
    path = by_arch.get(arch)
    if not path:
        return None, ("Python packages: these images hold no constraints file for Linux {} (only for {}); pip "
                      "chooses the versions".format(arch, pinned))
    want = env.get("constraints_python")
    if isinstance(want, str) and python:
        try:
            if tuple(int(x) for x in want.split(".")[:2]) != tuple(python[:2]):
                return None, ("Python packages: {} pins versions for Python {}; this Python is {}.{} -- not used, "
                              "pip chooses the versions".format(path, want, python[0], python[1]))
        except ValueError:
            pass
    return path, "Python packages: constraints {} (Linux {})".format(path, arch)


def choose_install(dest: Path, how: str) -> dict:
    """Where the packages go: {"kind": venv|system|target, "python": path, "site": target folder or None}."""
    if how in ("auto", "venv"):
        venv = dest / VENV_DIR
        if _make_venv(venv):
            return {"kind": "venv", "python": str(_venv_python(venv)), "site": None}
        if how == "venv":
            raise RuntimeError("a virtual environment was asked for (--install venv) but cannot be made; "
                               "install the venv module (Debian/Ubuntu: apt-get install python3-venv) or use "
                               "--install target")
        if _externally_managed():
            say("  this Python refuses system-wide installs (PEP 668): the packages go into {}".format(
                dest / STATE_DIR / TARGET_SITE))
            how = "target"
        else:
            how = "system"
    if how == "system":
        return {"kind": "system", "python": sys.executable, "site": None}
    if how == "target":
        return {"kind": "target", "python": sys.executable, "site": str(dest / STATE_DIR / TARGET_SITE)}
    raise RuntimeError("unknown install kind {!r}".format(how))


def _py_version(python: str):
    try:
        out = subprocess.run([python, "-c", "import sys;print('%d.%d' % sys.version_info[:2])"], env=tool_env(),
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout.decode().strip()
        return tuple(int(x) for x in out.split("."))
    except Exception:  # noqa: BLE001
        return None


def setup_environment(dest: Path, images: Path, m: dict, mode: str, inst: dict, pip_args=(),
                      keep_wheels: bool = False) -> int:
    """Install the packages of the manifest's environment block. -> exit code."""
    if mode == "none":
        say("Python packages: not installed (--env none).")
        return EXIT_OK
    env = m.get("environment") or {}
    reqs = []
    for r in env.get("requirements") or []:
        path = dest / check_rel(r, "requirement file")
        if path.is_file():
            reqs.append(path)
        else:
            warn("the requirement file {} is not in {} (partial unpack?) -- skipped".format(r, dest))
    have = _py_version(inst["python"])
    picked, line = pick_constraints(env, python=have)
    if line:
        say(line)
    cons = []
    for c in list(env.get("constraints") or []) + ([picked] if picked else []):
        path = dest / check_rel(c, "constraint file")
        if path.is_file():
            cons.append(path)
        else:
            warn("the constraint file {} is not in {} -- skipped".format(c, dest))
    extra = [x for x in env.get("extra_requirements") or [] if isinstance(x, str) and x.strip()]
    if extra:
        path = dest / STATE_DIR / EXTRA_REQ_NAME
        write_atomic(path, ("\n".join(extra) + "\n").encode("utf-8"))
        reqs.append(path)
    if not reqs:
        say("Python packages: the manifest names no requirement file present here -- nothing to install.")
        return EXIT_OK
    want = env.get("python_version")
    if isinstance(want, str) and have:
        try:
            if have < tuple(int(x) for x in want.split(".")[:2]):
                warn("the application was packed for Python {}; this Python is {}.{} -- some parts may fail"
                     .format(want, have[0], have[1]))
        except ValueError:
            pass
    cmd = [inst["python"], "-m", "pip", "install", "--disable-pip-version-check", "--no-cache-dir"]
    if inst["kind"] == "target":
        cmd += ["--target", inst["site"]]
    wheel_dir = None
    if mode == "offline":
        comp = wheels_compartment(m)
        if comp is None:
            error("--env offline, but these images hold no wheels (pack them with `pack --wheels`)")
            return EXIT_ENV
        wheel_dir = dest / STATE_DIR / WHEELS_DIR
        say("Unpacking {} wheels for the offline install ...".format(len(comp["files"])))
        try:
            extract_wheels(images, comp, wheel_dir)
        except PartError as exc:
            error(str(exc))
            return EXIT_PARTS
        except UnsafeError as exc:
            error(str(exc))
            return EXIT_UNSAFE
        cmd += ["--no-index", "--find-links", str(wheel_dir)]
    elif env.get("pip_options"):
        cmd += [str(x) for x in env["pip_options"]]
    _install_pinned_pip(dest, env, inst, cmd)
    cmd += list(pip_args)
    for c in cons:
        cmd += ["-c", str(c)]
    for r in reqs:
        cmd += ["-r", str(r)]
    say("Installing the Python packages ({}, {}) -- this can take a while ...".format(
        mode, {"venv": "virtual environment " + str(dest / VENV_DIR), "system": "this Python " + sys.executable,
               "target": "folder " + str(inst["site"])}[inst["kind"]]))
    say("  " + " ".join(cmd))
    rc = subprocess.call(cmd, cwd=str(dest), env=tool_env())
    if wheel_dir is not None and not keep_wheels and rc == 0:
        shutil.rmtree(str(wheel_dir), ignore_errors=True)
    if rc != 0:
        error("pip failed (exit code {}); its messages are above".format(rc))
        return EXIT_ENV
    return EXIT_OK


def _install_pinned_pip(dest: Path, env: dict, inst: dict, head: list) -> None:
    """The manifest's pinned pip ("pip_self") into a virtual environment, before the packages. ``head`` = the
    package install command so far (python -m pip install ... and the index or --no-index options). A failure
    only warns: the packages are then installed with the environment's own pip."""
    ps = env.get("pip_self")
    if not ps or inst.get("kind") != "venv":
        return
    cmd = list(head)
    for c in ps.get("constraints") or []:
        path = dest / check_rel(c, "pip constraints file")
        if path.is_file():
            cmd += ["-c", str(path)]
        else:
            warn("the pip constraints file {} is not in {} -- pip is installed without it".format(c, dest))
    cmd.append(ps["spec"])
    say("Installing the pinned pip first: " + " ".join(cmd))
    rc = subprocess.call(cmd, cwd=str(dest), env=tool_env())
    if rc != 0:
        warn("the pinned pip could not be installed (exit code {}); the packages are installed with the virtual "
             "environment's own pip".format(rc))


# ---------------------------------------------------------------------------------------------------------
# Running the application
# ---------------------------------------------------------------------------------------------------------
def _translate(value: str, workdir, dest: Path) -> str:
    """An environment value written for the image's working folder (``workdir``), moved to ``dest``.
    A ':'-separated list of paths becomes an os.pathsep list; values that name no such path stay as they are."""
    if not workdir or not isinstance(value, str):
        return value
    wd = workdir.rstrip("/") or "/"
    if os.path.normpath(str(dest)) == os.path.normpath(wd):
        return value
    items = value.split(":")
    moved, hit = [], False
    for item in items:
        if item == wd or item.startswith(wd + "/"):
            rest = item[len(wd):].lstrip("/")
            moved.append(str(dest.joinpath(*rest.split("/"))) if rest else str(dest))
            hit = True
        else:
            moved.append(item)
    if not hit:
        return value
    return os.pathsep.join(moved) if len(items) > 1 else moved[0]


def _declared_output_release(m: dict) -> bool:
    return any(row.get("path") == "docker/output_seed_manifest.json" for row in m.get("files", []))


def _mount_helper(dest: Path, inst, arguments: list) -> dict:
    helper = dest / "output_mount.py"
    _metadata_target(helper)
    python = (inst or {}).get("python") or sys.executable
    proc = subprocess.run([python, "-B", str(helper)] + arguments + ["--repo", str(dest)],
                          cwd=str(dest), env=tool_env(PYTHONDONTWRITEBYTECODE="1"),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode:
        # The coordinator reports paths/errors only; it never reads settings values.
        raise RuntimeError("Output preparation failed: " + proc.stderr.decode("utf-8", "replace").strip())
    result = json.loads(proc.stdout.decode("utf-8"))
    if not isinstance(result, dict):
        raise RuntimeError("Output coordinator returned invalid state")
    return result


def prepare_host_release(dest: Path, m: dict, inst) -> None:
    if not _declared_output_release(m):
        return
    # --json: the saved setup as one JSON line on standard output (the summary goes to standard error)
    args = ["prepare", "--source", "tree", "--seed", os.environ.get("CSTEEL_SEED", "1"),
            "--install-outputs", "--json"]
    if os.environ.get("CSTEEL_SEED_CONTEXT"):
        args += ["--generation", os.environ["CSTEEL_SEED_CONTEXT"]]
    _mount_helper(dest, inst, args)


def run_env(dest: Path, m: dict, inst, extra=None) -> dict:
    """The environment variables of the application (the image's ENV lines, moved to ``dest``)."""
    env = dict(os.environ)
    docker = (m.get("environment") or {}).get("docker") or {}
    workdir = docker.get("workdir")
    for pair in docker.get("env") or []:
        if isinstance(pair, list) and len(pair) == 2 and all(isinstance(x, str) for x in pair):
            env[pair[0]] = _translate(pair[1], workdir, dest)
    if inst and inst.get("kind") == "venv":
        vbin = str(Path(inst["python"]).parent)
        env["PATH"] = vbin + os.pathsep + env.get("PATH", "")
        env["VIRTUAL_ENV"] = str(Path(inst["python"]).parent.parent)
    if inst and inst.get("kind") == "target":
        env["PYTHONPATH"] = inst["site"] + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    if _declared_output_release(m):
        env.update(_mount_helper(dest, inst, ["environment"]))
    else:
        env["CSTEEL_CONTAINER"] = "0"
    env.update(extra or {})
    return env


def start_command(m: dict, inst) -> list:
    """ENTRYPOINT + CMD, with the leading ``python`` of each replaced by the Python of the install."""
    env = m.get("environment") or {}
    start = env.get("start") or {}
    cmd = [str(x) for x in start.get("command") or []]
    entry = (env.get("docker") or {}).get("entrypoint")
    heads = {0} | ({len(entry)} if isinstance(entry, list) and 0 < len(entry) < len(cmd) else set())
    for i in sorted(heads):
        if i < len(cmd) and re.fullmatch(r"python(3(\.\d+)?)?", cmd[i]):
            cmd[i] = (inst or {}).get("python") or sys.executable
    return cmd


def start_module(m: dict):
    """The .py file the start check imports: the first argument of the CMD (else of the start command) that
    ends in ``.py`` and names a file of the top folder -- an argument with a ``/`` (a wrapper such as
    ``docker/entrypoint.py``) is skipped."""
    env = m.get("environment") or {}
    cmd = (env.get("docker") or {}).get("cmd")
    if not isinstance(cmd, list) or not cmd:
        cmd = (env.get("start") or {}).get("command") or []
    return next((c for c in cmd[1:] if isinstance(c, str) and c.endswith(".py") and "/" not in c
                 and "\\" not in c), None)


_COMPILE = ("import sys\nbad = 0\nfor f in sys.argv[1:]:\n    try:\n        compile(open(f, 'rb').read(), f, 'exec')\n"
            "    except SyntaxError as e:\n        bad += 1\n        print('  cannot compile %s: %s' % (f, e))\n"
            "sys.exit(1 if bad else 0)\n")


def start_checks(dest: Path, m: dict, inst, env_mode: str) -> int:
    """Compile the root .py files, run the big-file tool's status, import the start module. -> exit code."""
    python = (inst or {}).get("python") or sys.executable
    failed = []
    roots = sorted(f["path"] for f in m["files"] if "/" not in f["path"] and f["path"].endswith(".py")
                   and f["mode"] != MODE_LINK and (dest / f["path"]).is_file())
    if roots:
        rc = subprocess.call([python, "-c", _COMPILE] + [str(dest / r) for r in roots], cwd=str(dest),
                             env=tool_env(PYTHONDONTWRITEBYTECODE="1"))
        say("  check: {} root .py files {}".format(len(roots), "compile" if rc == 0 else "DO NOT compile"))
        if rc != 0:
            failed.append("compile")
    lf = _large_tool(m)
    if lf and (dest / lf["tool"]).is_file():
        proc = subprocess.run([python, str(dest / lf["tool"]), "--root", str(dest), "status"], cwd=str(dest),
                              env=tool_env(PYTHONDONTWRITEBYTECODE="1"),
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        lines = proc.stdout.decode("utf-8", "replace").strip().splitlines()
        summary = [ln for ln in lines if ln.startswith("Summary") or "PROBLEM" in ln]
        say("  check: {} status -> {}".format(lf["tool"], "; ".join(summary) or (lines[-1] if lines else "")))
        if proc.returncode != 0:
            failed.append("large files")
    script = start_module(m)
    if _declared_output_release(m):
        say("  check: application import deferred to protected host start; install checks do not verify app startup")
    elif env_mode == "none":
        say("  check: import of the start module skipped (no packages installed)")
    elif script and (dest / script).is_file():
        module = script[:-3]
        env = run_env(dest, m, inst, {"LARGE_FILES_SELF_CHECK": "0", "PYTHONDONTWRITEBYTECODE": "1"})
        try:
            proc = subprocess.run([python, "-c", "import " + module], cwd=str(dest), env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=900)
            rc, out = proc.returncode, proc.stdout.decode("utf-8", "replace")
        except subprocess.TimeoutExpired:
            rc, out = 1, "timed out after 900 s"
        say("  check: import {} {}".format(module, "works" if rc == 0 else "FAILS"))
        if rc != 0:
            for ln in out.strip().splitlines()[-12:]:
                say("    " + ln)
            failed.append("import")
    if failed:
        error("the start check failed: " + ", ".join(failed))
        return EXIT_CHECK
    return EXIT_OK


def how_to_start(dest: Path, m: dict, inst) -> str:
    cmd = start_command(m, inst)
    if not cmd:
        return "The manifest names no start command."
    here = Path(__file__).resolve()
    return "To start with the saved mount settings:\n  {}{} {} start --dest {}".format(
        "& " if os.name == "nt" else "", _display_quote(sys.executable), _display_quote(str(here)), _display_quote(str(dest)))


def _display_quote(value: str) -> str:
    if os.name == "nt":
        return "'" + value.replace("'", "''") + "'"
    return _q(value)


def _q(s: str) -> str:
    return s if re.fullmatch(r"[\w./:=@+-]+", s) else "'" + s.replace("'", "'\\''") + "'"


# ---------------------------------------------------------------------------------------------------------
# installed.json
# ---------------------------------------------------------------------------------------------------------
def load_installed(dest: Path) -> dict:
    _metadata_target(dest / STATE_DIR / INSTALLED_NAME)
    data = load_json(dest / STATE_DIR / INSTALLED_NAME)
    if not isinstance(data, dict) or data.get("format") != INSTALLED_FORMAT:
        raise ManifestError("{} is not an installed record of this format".format(dest / STATE_DIR / INSTALLED_NAME))
    validate_manifest(data.get("manifest"))
    return data


def save_installed(dest: Path, m: dict, install: dict) -> None:
    record = {"format": INSTALLED_FORMAT, "install": install, "manifest": m}
    write_atomic(dest / STATE_DIR / INSTALLED_NAME, manifest_bytes(record))


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---------------------------------------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------------------------------------
def _default_env(m: dict) -> str:
    """ONLINE by default (the owner's choice); the packed wheels are used only with --env offline."""
    return "online"


def _open(args):
    images = Path(args.images).absolute()
    path, m = load_manifest(images, args.manifest)
    say("Images: {}\nManifest: {} (commit {}, {})".format(images, path.name, m.get("commit", "?")[:12],
                                                          m.get("commit_date", "?")))
    return images, m


def cmd_verify(args) -> int:
    images, m = _open(args)
    comps = select_compartments(m, args.only)
    wc = wheels_compartment(m)
    if wc and not args.only:
        comps = comps + [wc]
    return verify_images(images, m, comps)


def _complete_selection(m: dict, names) -> bool:
    expected = {c["name"] for c in m["compartments"] if c["kind"] != KIND_WHEELS}
    return set(names) == expected


def cmd_install(args) -> int:
    if args.verify_only:
        return cmd_verify(args)
    images, m = _open(args)
    if not args.dest:
        error("--dest is required: the folder to build (for example --dest /app)")
        return EXIT_ERROR
    dest = Path(args.dest).absolute()
    image_tree = getattr(args, "image_tree", False)
    if image_tree and (os.name != "posix" or str(dest) != "/app"
                       or os.environ.get("CSTEEL_IMAGE_BUILD") != "1"):
        error("--image-tree is only valid in the disposable /app image build")
        return EXIT_REFUSED
    if _runtime_outputs_present(dest):
        error("This folder contains runtime outputs. Install into a new code folder and reuse the existing "
              "outputs with CSTEEL_OUTPUTS_DIR; --force does not replace user outputs.")
        return EXIT_REFUSED
    try:
        _metadata_target(dest / STATE_DIR / INSTALLED_NAME)
    except UnsafeError as exc:
        error(str(exc))
        return EXIT_UNSAFE
    comps = select_compartments(m, args.only)
    if not comps:
        error("no compartment matches --only {}".format(args.only))
        return EXIT_ERROR
    complete_selection = _complete_selection(m, [c["name"] for c in comps])
    if not complete_selection and (args.start or image_tree):
        error("A partial install cannot start the application or prepare an image tree")
        return EXIT_REFUSED
    env_mode = args.env or _default_env(m)
    if os.path.lexists(_fs_path(dest / STATE_DIR / INSTALLED_NAME)):
        error("{} already holds an installed copy; use `update` to change it".format(dest))
        return EXIT_REFUSED
    if os.path.lexists(_fs_path(dest)) and not args.force:
        with os.scandir(_fs_path(dest)) as entries:
            nonempty = next(entries, None) is not None
        if nonempty:
            error("{} is not empty; choose an empty folder or add --force".format(dest))
            return EXIT_REFUSED
    need = list(comps)
    wc = wheels_compartment(m)
    if env_mode == "offline":
        if wc is None:
            error("--env offline, but these images hold no wheels (the maintainer packs them with "
                  "`pack --wheels`); nothing was written")
            return EXIT_ENV
        need.append(wc)
    say("Checking {} zips ...".format(len({p["file"] for c in need for p in c["parts"]})))
    problems = check_part_files(images, need, full=True)
    for p in problems:
        error(p)
    if problems:
        error("nothing was written; copy the missing or damaged zips again")
        return EXIT_PARTS
    by_comp = files_by_compartment(m)
    raw = sum(f["size"] for c in comps for f in by_comp[c["name"]])
    free = free_bytes(dest)
    if free < raw + SPACE_MARGIN and not args.force:
        error("not enough free disk space at {}: {} MB needed, {} MB free".format(dest, mb(raw + SPACE_MARGIN),
                                                                                 mb(free)))
        return EXIT_REFUSED
    try:
        _ordinary_directory(dest, create=True)
    except UnsafeError as exc:
        error(str(exc))
        return EXIT_UNSAFE
    t0 = time.monotonic()
    writer = Writer(dest)
    say("Unpacking {} compartments ({} MB) into {} ...".format(len(comps), mb(raw), dest))
    for k, c in enumerate(comps, 1):
        try:
            extract_compartment(images, c, by_comp[c["name"]], writer)
        except PartError as exc:
            error(str(exc))
            return EXIT_PARTS
        except UnsafeError as exc:
            error(str(exc) + " -- unpacking stopped")
            return EXIT_UNSAFE
        if len(comps) <= 20 or k % 25 == 0 or k == len(comps):
            say("  [{}/{}] {} ({} files)".format(k, len(comps), c["name"], len(by_comp[c["name"]])))
    say("Unpacked {:,} files, every sha256 checked ({:.0f} s).".format(writer.written, time.monotonic() - t0))
    if writer.links_as_files:
        warn("{} links were written as small text files (this system cannot make symbolic links)".format(
            writer.links_as_files))
    install = {"at": _now(), "dest": str(dest), "only": list(args.only or []),
               "compartments": [c["name"] for c in comps], "env": env_mode, "large_files": not args.no_large_files,
               "python": None, "kind": None, "site": None, "env_fingerprint": None}
    save_installed(dest, m, install)
    if not args.no_large_files:
        rc = restore_large_files(dest, m)
        if rc:
            return rc
    if args.strip_large_parts:
        if args.no_large_files:
            say("Big files: --strip-large-parts ignored (--no-large-files: nothing was restored).")
        else:
            rc = strip_large_parts(dest, m)
            if rc:
                return rc
            install["strip_large_parts"] = True
            save_installed(dest, m, install)
    inst = None
    if env_mode != "none":
        try:
            inst = choose_install(dest, args.install)
        except RuntimeError as exc:
            error(str(exc))
            return EXIT_ENV
        rc = setup_environment(dest, images, m, env_mode, inst, args.pip_arg or [], args.keep_wheels)
        if rc:
            return rc
        install.update(python=inst["python"], kind=inst["kind"], site=inst["site"],
                       env_fingerprint=env_fingerprint(m))
        save_installed(dest, m, install)
    if image_tree:
        if _declared_output_release(m):
            python = (inst or {}).get("python") or sys.executable
            rc = subprocess.call([python, "-B", str(dest / "output_seed.py"), "verify",
                                  "--root", str(dest / "_outputs_user"),
                                  "--manifest", str(dest / "docker/output_seed_manifest.json")],
                                 cwd=str(dest), env=tool_env(PYTHONDONTWRITEBYTECODE="1"))
            if rc:
                error("The restored image output release is incomplete")
                return EXIT_CHECK
        say("Image tree verified; application imports wait for image preparation and runtime startup.")
    elif complete_selection:
        try:
            prepare_host_release(dest, m, inst)
        except (OSError, ValueError, RuntimeError) as exc:
            error(str(exc))
            return EXIT_CHECK
    if not args.skip_checks and not image_tree and complete_selection:
        say("Start check:")
        rc = start_checks(dest, m, inst, env_mode)
        if rc:
            return rc
    say("\nDone: {} is ready.".format(dest))
    say(how_to_start(dest, m, inst) if complete_selection else "Partial files only; install the complete image into a fresh folder before starting.")
    if args.start:
        if image_tree:
            error("An image build cannot start the host application")
            return EXIT_REFUSED
        return run_start(dest, m, inst)
    return EXIT_OK


def run_start(dest: Path, m: dict, inst) -> int:
    cmd = start_command(m, inst)
    if not cmd:
        error("the manifest names no start command")
        return EXIT_ERROR
    env = run_env(dest, m, inst)
    if _declared_output_release(m):
        required = ["host_databases.py", "zip_images/unpack_images.py"]
        if os.name == "posix":
            required.append("scripts/mount/readonly-start.sh")
        for relative in required:
            path = dest / relative
            _metadata_target(path)
            if not os.path.isfile(_fs_path(path)):
                error("Protected host start requires " + relative)
                return EXIT_CHECK
        python = str(Path((inst or {}).get("python") or sys.executable).absolute())
        if os.name == "nt":
            helper = [python, "-E", "-S", "-B", str(dest / "host_databases.py")]
            rc = subprocess.call(helper + ["protect-windows", "--repo", str(dest)], cwd=str(dest), env=env)
            if rc:
                return rc
            cmd = helper + ["run", "--repo", str(dest), "--runtime-kind", "zip", "--"] + cmd
        elif sys.platform.startswith("linux"):
            cmd = ["/bin/sh", str(dest / "scripts/mount/readonly-start.sh"),
                   "--python", python, "--runtime-kind", "zip", "--"] + cmd
        else:
            error("Protected host start requires Windows or Linux")
            return EXIT_REFUSED
        say("Starting the application with read-only host databases and saved outputs.")
    else:
        say("Starting: " + " ".join(cmd))
    if os.name == "posix":
        os.chdir(str(dest))
        os.execvpe(cmd[0], cmd, env)
    return subprocess.call(cmd, cwd=str(dest), env=env)


def cmd_start(args) -> int:
    dest = Path(args.dest).absolute()
    rec = load_installed(dest)
    if not _complete_selection(rec["manifest"], rec["install"]["compartments"]):
        error("This partial install cannot start the application; install the complete image first")
        return EXIT_REFUSED
    inst = rec["install"] if rec["install"].get("python") else None
    return run_start(dest, rec["manifest"], inst)


def local_changes(dest: Path, files: dict) -> list:
    """Compare ordinary files or symlink objects without following linked ancestors."""
    changed = []
    for path, fd in sorted(files.items()):
        target = dest.joinpath(*path.split("/"))
        try:
            _ordinary_directory(target.parent)
            info = os.lstat(_fs_path(target))
        except FileNotFoundError:
            continue
        except (OSError, UnsafeError):
            changed.append(path)
            continue
        if fd["mode"] == MODE_LINK and stat.S_ISLNK(info.st_mode):
            try:
                raw = os.readlink(_fs_path(target)).encode("utf-8", "surrogateescape")
                if len(raw) == fd["size"] and hashlib.sha256(raw).hexdigest() == fd["sha256"]:
                    continue
            except OSError:
                pass
            changed.append(path)
        elif (_linked(info) or not stat.S_ISREG(info.st_mode)
              or info.st_size != fd["size"] or sha256_file(target) != fd["sha256"]):
            changed.append(path)
    return changed


def cmd_check(args) -> int:
    dest = Path(args.dest).absolute()
    rec = load_installed(dest)
    m = rec["manifest"]
    names = set(rec["install"]["compartments"])
    files = {f["path"]: f for f in m["files"] if f["compartment"] in names}
    changed = local_changes(dest, files)
    absent = [p for p in files if not os.path.lexists(_fs_path(dest.joinpath(*p.split("/"))))]
    stripped = stripped_parts(dest, m)
    missing = [p for p in absent if p not in stripped]
    for p in changed:
        say("changed  " + p)
    for p in missing:
        say("missing  " + p)
    gone = len(absent) - len(missing)
    say("Check: {:,} files of commit {} -- {} changed, {} missing{}".format(
        len(files), m.get("commit", "?")[:12], len(changed), len(missing),
        "; {} zip parts of restored big files removed by strip (expected)".format(gone) if gone else ""))
    return EXIT_OK if not changed and not missing else EXIT_ERROR


def _prune_empty_dirs(dest: Path, paths) -> None:
    for d in sorted({str(Path(p).parent) for p in paths}, key=len, reverse=True):
        cur = dest / d
        while cur != dest and str(cur).startswith(str(dest)):
            try:
                cur.rmdir()
            except OSError:
                break
            cur = cur.parent


def cmd_update(args) -> int:
    dest = Path(args.dest).absolute()
    images = Path(args.images).absolute()
    try:
        rec = load_installed(dest)
    except ManifestError as exc:
        error("{} -- `update` works on a folder made by `install`".format(exc))
        return EXIT_MANIFEST
    old_m, old_inst = rec["manifest"], rec["install"]
    if _runtime_outputs_present(dest) or _published_outputs(old_m):
        error("In-place update would touch published or runtime outputs. Install into a new code folder and "
              "reuse the existing outputs with CSTEEL_OUTPUTS_DIR; --force does not bypass this protection.")
        return EXIT_REFUSED
    path, new_m = load_manifest(images, args.manifest)
    if _published_outputs(new_m):
        error("This release contains outputs. Install it into a new code folder and use CSTEEL_OUTPUTS_DIR "
              "to preserve the existing output mount.")
        return EXIT_REFUSED
    say("Update {}: commit {} -> {} ({})".format(dest, old_m.get("commit", "?")[:12], new_m.get("commit", "?")[:12],
                                                path.name))
    old_names = set(old_inst["compartments"])
    new_sel = select_compartments(new_m, old_inst.get("only") or None)
    old_keys = {c["name"]: c["key"] for c in old_m["compartments"] if c["name"] in old_names}
    changed = [c for c in new_sel if old_keys.get(c["name"]) != c["key"]]
    new_names = {c["name"] for c in new_sel}
    removed = sorted(n for n in old_names if n not in new_names)
    same = [c["name"] for c in new_sel if old_keys.get(c["name"]) == c["key"]]
    old_files = {f["path"]: f for f in old_m["files"] if f["compartment"] in old_names}
    new_by = files_by_compartment(new_m)
    new_files = {f["path"]: f for c in new_sel for f in new_by[c["name"]]}
    rewrite = {f["path"] for c in changed for f in new_by[c["name"]]}
    delete = sorted(p for p in old_files if p not in new_files)
    touched = {p: old_files[p] for p in (rewrite | set(delete)) if p in old_files}
    arriving = {p: new_files[p] for p in rewrite if p not in old_files}
    say("  compartments: {} changed or new, {} removed, {} unchanged".format(len(changed), len(removed), len(same)))
    for c in changed:
        say("    {} {}".format("changed" if c["name"] in old_keys else "new    ", c["name"]))
    for n in removed:
        say("    removed {}".format(n))
    mods = sorted(local_changes(dest, touched) + local_changes(dest, arriving))
    if mods and not args.force:
        for p in mods[:50]:
            error("changed locally: {}".format(p))
        error("{} files that this update would overwrite or delete were changed in {}; nothing was written. "
              "Keep a copy of them, then run again with --force".format(len(mods), dest))
        return EXIT_REFUSED
    if args.dry_run:
        say("  dry run: {} files would be rewritten or checked, {} deleted".format(len(rewrite), len(delete)))
        return EXIT_OK
    problems = check_part_files(images, changed, full=True)
    for p in problems:
        error(p)
    if problems:
        return EXIT_PARTS
    lf = _large_tool(new_m) or _large_tool(old_m)
    lf_changed = bool(lf) and any(n == lf["store"] or n.startswith(lf["store"] + "/")
                                  for n in [c["name"] for c in changed] + removed)
    old_targets = _pack_targets(dest, lf["store"]) if lf_changed else {}
    writer = Writer(dest, skip_same=True)
    for c in changed:
        try:
            extract_compartment(images, c, new_by[c["name"]], writer)
        except PartError as exc:
            error(str(exc))
            return EXIT_PARTS
        except UnsafeError as exc:
            error(str(exc) + " -- update stopped")
            return EXIT_UNSAFE
    for p in delete:
        target = dest.joinpath(*p.split("/"))
        if target.is_symlink() or target.is_file():
            target.unlink()
    _prune_empty_dirs(dest, delete)
    install = dict(old_inst, at=_now(), compartments=sorted(new_names))
    save_installed(dest, new_m, install)
    say("  files: {} written, {} already identical, {} deleted".format(writer.written, writer.same, len(delete)))
    rc = EXIT_OK
    if lf_changed and old_inst.get("large_files", True) and not args.no_large_files:
        dropped = _drop_stale_originals(dest, lf["store"], old_targets, _pack_targets(dest, lf["store"]))
        if dropped:
            say("  big files: {} old versions removed before the restore".format(len(dropped)))
        rc = restore_large_files(dest, new_m)
        if rc:
            return rc
    else:
        say("  big files: unchanged -- not restored again")
    env_mode = args.env or old_inst.get("env") or "none"
    fp_new = env_fingerprint(new_m)
    if env_mode != "none" and (fp_new != old_inst.get("env_fingerprint") or args.env):
        inst = {"kind": old_inst.get("kind"), "python": old_inst.get("python"), "site": old_inst.get("site")}
        if not inst["python"] or not Path(inst["python"]).exists():
            try:
                inst = choose_install(dest, args.install)
            except RuntimeError as exc:
                error(str(exc))
                return EXIT_ENV
        say("  Python packages: the requirements changed -- installing again")
        rc = setup_environment(dest, images, new_m, env_mode, inst, args.pip_arg or [], args.keep_wheels)
        if rc:
            return rc
        install.update(python=inst["python"], kind=inst["kind"], site=inst["site"], env=env_mode,
                       env_fingerprint=fp_new)
        save_installed(dest, new_m, install)
    else:
        say("  Python packages: requirements unchanged -- not installed again")
    say("Updated {} to commit {}.".format(dest, new_m.get("commit", "?")[:12]))
    return rc


def cmd_info(args) -> int:
    images = Path(args.images).absolute()
    found = sorted((images / MANIFESTS_DIR).glob("*.json"))
    try:
        latest = manifest_path(images, "latest").name
    except ManifestError:
        latest = None
    say("Image folder {}: {} manifests".format(images, len(found)))
    for f in found:
        try:
            m = load_json(f)
            t = m.get("totals") or {}
            say("  {}{}  commit {}  {}  {} compartments, {:,} files, {} MB in {} zips".format(
                "* " if f.name == latest else "  ", f.name, m.get("commit", "?")[:12], m.get("commit_date", "?"),
                t.get("compartments", "?"), t.get("files", 0), mb(t.get("zip_bytes", 0)), t.get("zips", "?")))
        except ManifestError as exc:
            say("  " + str(exc))
    say("(* = latest)")
    return EXIT_OK


_HELP = """\
Build an application folder and its Python environment from the zip images in this folder.

commands:
  install  (the default) check the zips, unpack them into --dest, restore the big files, install the
           Python packages and check that the application can start
  update   bring a folder made by `install` to another manifest: only compartments that changed are
           rewritten; files changed by hand stop the update unless --force
  verify   check every zip and every file inside them (sha256) without writing anything
           (the same as `install --verify-only`)
  check    compare an installed folder with the manifest it was installed from
  start    start the application of an installed folder
  info     list the manifests (commits) this image folder holds

big files: the unpacked tree's own large_file_packs.py rebuilds them; --strip-large-parts then deletes
  their zip parts (for an image; the generated Dockerfile uses it)

examples:
  python3 unpack_images.py --dest /app
  python3 unpack_images.py --dest ./app --env none --only '(files)' --only 'Util_Argo_APIs'
  python3 unpack_images.py --verify-only
  python3 unpack_images.py update --dest /app --manifest latest

exit codes: 0 ok, 1 usage or unexpected error, 2 manifest missing or unreadable, 3 a zip missing or
damaged, 4 unsafe content or a sha256 mismatch, 5 big-file restore failed, 6 package install failed,
7 start check failed, 8 refused (folder not empty, local changes, no disk space)
"""

_COMMANDS = ("install", "update", "verify", "check", "start", "info")


def _parser(command: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="unpack_images.py" + ("" if command == "install" else " " + command),
                                description=_HELP, formatter_class=argparse.RawDescriptionHelpFormatter)
    here = str(Path(__file__).absolute().parent)
    if command in ("install", "update", "verify", "info"):
        p.add_argument("--images", default=here, help="the folder of the zip images (default: this script's folder)")
    if command in ("install", "update", "verify"):
        p.add_argument("--manifest", default="latest",
                       help="'latest' (default), a commit id prefix, or a manifest .json file")
    if command in ("install", "update", "check", "start"):
        p.add_argument("--dest", required=command != "install", help="the application folder")
    if command in ("install", "verify"):
        p.add_argument("--only", action="append", metavar="GLOB",
                       help="only compartments whose name matches (repeatable), e.g. '(files)' or 'Util_*'")
    if command in ("install", "update"):
        p.add_argument("--env", choices=("online", "offline", "none"),
                       help="Python packages: online (pip from the internet; the default), offline (the "
                            "wheels packed with `pack --wheels`; no internet needed) or none (files only); "
                            "update: default what install used")
        p.add_argument("--install", default="auto", choices=("auto", "venv", "system", "target"),
                       help="where packages go: auto (a venv at <dest>/.venv when possible, else this Python, "
                            "else <dest>/.zip_images/site-packages), venv, system, target")
        p.add_argument("--system", dest="install", action="store_const", const="system",
                       help="install into this Python (as a plain Dockerfile does); same as --install system")
        p.add_argument("--pip-arg", action="append", metavar="ARG",
                       help="an extra argument for `pip install` (repeatable), e.g. --pip-arg=--index-url=URL")
        p.add_argument("--keep-wheels", action="store_true", help="keep the unpacked wheels after an offline install")
        p.add_argument("--no-large-files", action="store_true", help="do not restore the big files")
        p.add_argument("--force", action="store_true",
                       help="install: use a non-empty folder / ignore the space check; update: overwrite local changes")
    if command == "install":
        p.add_argument("--verify-only", action="store_true", help="check every zip and file; write nothing")
        p.add_argument("--skip-checks", action="store_true", help="skip the start check")
        p.add_argument("--image-tree", action="store_true", help=argparse.SUPPRESS)
        p.add_argument("--start", action="store_true", help="start the application when everything is ready")
        p.add_argument("--strip-large-parts", action="store_true",
                       help="after the big files are restored, delete their zip parts (large_file_packs.py "
                            "strip; the manifests stay) -- for an image, which need not hold both")
    if command == "update":
        p.add_argument("--dry-run", action="store_true", help="show what would change; write nothing")
    return p


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    command = argv.pop(0) if argv and argv[0] in _COMMANDS else "install"
    if command == "install" and argv[:1] in (["-h"], ["--help"]):
        _parser("install").print_help()
        return EXIT_OK
    args = _parser(command).parse_args(argv)
    try:
        return {"install": cmd_install, "update": cmd_update, "verify": cmd_verify, "check": cmd_check,
                "start": cmd_start, "info": cmd_info}[command](args)
    except ManifestError as exc:
        error(str(exc))
        return EXIT_MANIFEST
    except UnsafeError as exc:
        error(str(exc) + " -- refused")
        return EXIT_UNSAFE
    except PartError as exc:
        error(str(exc))
        return EXIT_PARTS
    except KeyboardInterrupt:
        error("interrupted")
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
