"""
zip_images.wheels -- the optional OFFLINE install: every wheel the requirements need, packed as one compartment.
================================================================================================================

The default environment is ONLINE: the unpacker runs ``pip install -r <files>`` against the package index.
With ``pack --wheels`` the packer also downloads, once per distinct requirement set, every wheel a Linux
install needs, and packs them as the compartment "(wheels)" (big wheels are split into chunks like any big
file). The unpacker then installs with ``pip install --no-index --find-links <unpacked wheels>``, so the
target machine needs no internet at all.

How the wheels are fetched (``download``):

* The platform tags: pip does not widen a ``--platform`` tag to older glibc versions (``manylinux_2_28``
  stays ``manylinux_2_28``; ``manylinux2014`` adds only ``manylinux2010`` and ``manylinux1``), so the default
  names every tag a manylinux_2_28 machine accepts: ``manylinux_2_28`` down to ``manylinux_2_5`` and the
  legacy aliases (``manylinux_platforms``). A wheel tagged only ``manylinux_2_17`` is then found too.
* WITH A LOCK (the source Dockerfile's per-platform constraints file, "constraints_by_arch"): the lock holds
  the whole dependency closure, so every pin is downloaded as it is, with ``--no-deps`` (no resolution on the
  packing machine). A package the lock's header builds from source (``--no-binary <name>`` on its "Resolver:"
  line, e.g. antlr4-python3-runtime) has no wheel on the index: its source archive is downloaded and built
  here with ``pip wheel`` into a wheel, which must be pure Python (``*-none-any.whl``: it then installs on any
  platform); a package that builds a platform-specific wheel stops the download with a clear message. Extra
  requirement lines (``pack --extra-requirement``) are resolved in one more step with the lock as ``-c``.
* WITHOUT A LOCK: one resolving ``pip download --only-binary=:all: ... -r <files>``.
* The pinned pip ("pip_self" of the environment: the source Dockerfile's ``pip install -c <file> pip``) joins
  the set, so the unpacker installs that pip first offline too.
* ``dry_run=True`` downloads nothing: ``pip install --dry-run --ignore-installed`` with the same platform,
  Python and pins answers whether every wheel exists (pip reads only the index and the metadata files); the
  source-only packages are fetched as source archives into a temporary folder (small) and not built.

The versions follow the source Dockerfile's lock: when the manifest records per-platform constraints files
("constraints_by_arch"), the file of the wheels' platform (x86_64 -> amd64, aarch64 -> arm64) is used as above,
and the recorded package-index options ("pip_options", e.g. ``--extra-index-url`` of the CPU torch index) are
passed too, so the offline wheels are the versions a Docker build of the source would install.

The compartment's key is the sha256 of (the requirement files' bytes, the extra requirement lines, the
platforms, the Python version, the extra pip arguments, and -- only when present -- the constraints file and
the package-index options): the same inputs are downloaded and zipped once.
Test and special use: ``pack --wheels-from DIR`` packs the wheels already in DIR instead of downloading
(their names and sha256s join the key).
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .planning import FileItem
from .unpack_images import MODE_FILE, sha256_file, _ordinary_directory


def manylinux_platforms(arch: str = "x86_64") -> tuple:
    """Every manylinux tag a glibc 2.28 machine of ``arch`` accepts, newest first (pip does not widen
    ``--platform`` by itself): manylinux_2_28 ... manylinux_2_5 (aarch64: ... manylinux_2_17) and the aliases."""
    lowest = 17 if arch == "aarch64" else 5
    tags = ["manylinux_2_{}_{}".format(minor, arch) for minor in range(28, lowest - 1, -1)]
    tags += ["manylinux2014_{}".format(arch)]
    if arch != "aarch64":
        tags += ["manylinux2010_{}".format(arch), "manylinux1_{}".format(arch)]
    return tuple(tags)


DEFAULT_PLATFORMS = manylinux_platforms("x86_64")
_ARCH_WORDS = {"amd64": "x86_64", "x86_64": "x86_64", "arm64": "aarch64", "aarch64": "aarch64"}


def platform_tags(values) -> list:
    """``pack --platform`` values as tags: amd64 / x86_64 and arm64 / aarch64 name every manylinux tag of that
    architecture (``manylinux_platforms``); any other value is a tag as it is."""
    tags = []
    for v in values or []:
        for tag in (manylinux_platforms(_ARCH_WORDS[v.lower()]) if v.lower() in _ARCH_WORDS else (v,)):
            if tag not in tags:
                tags.append(tag)
    return tags

_PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?\s*==\s*([^\s;#]+)")
_NO_BINARY = re.compile(r"--no-binary[ =]([^\s]+)")


def canonical(name: str) -> str:
    """A package name as pip compares it (PEP 503)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def read_lock(path) -> tuple:
    """([(name, version)] of a lock file's ``name==version`` lines, {canonical names the lock builds from
    source}: the ``--no-binary <name>`` words of its comment lines, e.g. the "Resolver:" header)."""
    pins, source_only = [], set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("#"):
            for m in _NO_BINARY.finditer(s):
                source_only.update(canonical(x) for x in m.group(1).split(",") if x and not x.startswith(":"))
            continue
        m = _PIN.match(s)
        if m:
            pins.append((m.group(1), m.group(2)))
    return pins, source_only


def arch_of_platforms(platforms) -> str:
    """'amd64' / 'arm64' when every platform tag names that Linux architecture, else None."""
    arches = set()
    for tag in platforms or []:
        t = str(tag).lower()
        if not (t.startswith("manylinux") or t.startswith("musllinux") or t.startswith("linux")):
            return None
        if t.endswith("x86_64"):
            arches.add("amd64")
        elif t.endswith("aarch64"):
            arches.add("arm64")
        else:
            return None
    return arches.pop() if len(arches) == 1 else None


def wheels_key(req_blobs: list, extra: list, platforms: list, python_version: str, pip_args: list,
               local: list = None, cons_blobs: list = (), pip_options: list = (), pip_self: str = None) -> str:
    """``req_blobs`` / ``cons_blobs`` = [(path, bytes)]; ``local`` = [(name, sha256)] for --wheels-from.
    The constraints, the package-index options and the pinned pip change the key only when present (older
    keys stay)."""
    h = hashlib.sha256(b"zip-images wheels/1\n")
    for path, data in req_blobs:
        h.update("req {} {}\n".format(path, hashlib.sha256(data).hexdigest()).encode("utf-8"))
    for line in extra:
        h.update("extra {}\n".format(line).encode("utf-8"))
    h.update("platforms {}\npython {}\npip {}\n".format(" ".join(platforms), python_version,
                                                         " ".join(pip_args)).encode("utf-8"))
    for name, sha in local or []:
        h.update("local {} {}\n".format(name, sha).encode("utf-8"))
    for path, data in cons_blobs or []:
        h.update("constraints {} {}\n".format(path, hashlib.sha256(data).hexdigest()).encode("utf-8"))
    if pip_options:
        h.update("index {}\n".format(" ".join(pip_options)).encode("utf-8"))
    if pip_self:
        h.update("pip_self {}\n".format(pip_self).encode("utf-8"))
    return "wheels:" + h.hexdigest()


def local_wheels(folder: Path) -> list:
    """[(name, sha256)] of the files in a wheel folder (sorted)."""
    return [(p.name, sha256_file(p)) for p in sorted(Path(folder).iterdir()) if p.is_file()]


def _run(cmd: list, log, what: str) -> None:
    log("{}: {}".format(what, " ".join(str(x) for x in cmd)))
    rc = subprocess.call([str(x) for x in cmd])
    if rc != 0:
        raise RuntimeError("{} failed (pip exit code {})".format(what, rc))


def download(req_files: list, extra: list, out_dir: Path, platforms: list, python_version: str,
             pip_args: list, python: str = None, log=print, constraints: list = (),
             pip_options: list = (), lock: Path = None, pip_self: tuple = None, dry_run: bool = False) -> None:
    """Fetch the Linux wheels into ``out_dir`` (raises RuntimeError on failure; see the module text).
    ``constraints`` = constraints files (``-c``); ``lock`` = the one among them that holds the whole closure
    (the lock of the wheels' platform): its pins are fetched one by one with ``--no-deps``;
    ``pip_options`` = the source's package-index options (e.g. ``--extra-index-url URL``); ``pip_self`` =
    (the pip requirement, [its constraints files]) of the source's own pip install, or None; ``dry_run`` =
    only check that everything exists (nothing is written to ``out_dir``)."""
    py = python or sys.executable
    out_dir = Path(out_dir)
    # Keep all download/build scratch beside the selected destination.
    _ordinary_directory(out_dir.parent, create=True)
    work = Path(tempfile.mkdtemp(prefix="zip_images_wheels_", dir=str(out_dir.parent)))
    try:
        target = ["--dry-run", "--ignore-installed", "--target", str(work / "dry_target")]

        def fetch(no_deps: bool) -> list:
            """The command head that fetches Linux wheels (``pip download``, or ``pip install --dry-run``)."""
            cmd = [py, "-m", "pip", "install" if dry_run else "download", "--disable-pip-version-check",
                   "--no-cache-dir", "--only-binary=:all:", "--python-version", python_version]
            cmd += target if dry_run else ["-d", str(out_dir)]
            if no_deps:
                cmd.append("--no-deps")
            for p in platforms:
                cmd += ["--platform", p]
            return cmd + [str(x) for x in pip_options or []] + [str(x) for x in pip_args]

        if not dry_run:
            out_dir.mkdir(parents=True, exist_ok=True)
        pins, source_only = read_lock(lock) if lock else ([], set())
        cons_args = [x for f in constraints or [] for x in ("-c", str(f))]
        if pins:
            binary = [(n, v) for n, v in pins if canonical(n) not in source_only]
            pin_file = work / "lock-binary.txt"
            pin_file.write_text("".join("{}=={}\n".format(n, v) for n, v in binary), encoding="utf-8")
            _run(fetch(True) + cons_args + ["-r", str(pin_file)],
                 log, "Checking wheels (dry run)" if dry_run else "Downloading wheels")
            for name, version in [(n, v) for n, v in pins if canonical(n) in source_only]:
                src = work / ("src_" + canonical(name))
                _run([py, "-m", "pip", "download", "--disable-pip-version-check", "--no-cache-dir", "--no-deps",
                      "--no-binary", name, "-d", str(src)] + [str(x) for x in pip_options or []]
                     + ["{}=={}".format(name, version)], log, "Downloading the source of " + name)
                if dry_run:
                    continue
                archives = [q for q in src.iterdir() if q.is_file()]
                if len(archives) != 1:
                    raise RuntimeError("pip download of the source of {} gave {} files".format(name, len(archives)))
                built = work / ("built_" + canonical(name))
                _run([py, "-m", "pip", "wheel", "--disable-pip-version-check", "--no-cache-dir", "--no-deps",
                      "-w", str(built), str(archives[0])], log, "Building a wheel of " + name)
                wheels = [q for q in built.iterdir() if q.name.endswith(".whl")]
                if len(wheels) != 1 or not wheels[0].name.endswith("-none-any.whl"):
                    raise RuntimeError(
                        "{} {} has no wheel on the index, and its source builds {} here -- not a pure-Python "
                        "wheel, so it cannot be packed for another platform; use the online install".format(
                            name, version, ", ".join(q.name for q in wheels) or "nothing"))
                shutil.copy2(str(wheels[0]), str(out_dir / wheels[0].name))
            if extra:
                extra_file = work / "extra-requirements.txt"
                extra_file.write_text("\n".join(extra) + "\n", encoding="utf-8")
                _run(fetch(False) + cons_args + ["-r", str(extra_file)], log,
                     "Checking the extra requirements (dry run)" if dry_run else "Downloading the extra requirements")
        else:
            cmd = fetch(False) + cons_args + [x for f in req_files for x in ("-r", str(f))]
            if extra:
                extra_file = work / "extra-requirements.txt"
                extra_file.write_text("\n".join(extra) + "\n", encoding="utf-8")
                cmd += ["-r", str(extra_file)]
            _run(cmd, log, "Checking wheels (dry run)" if dry_run else "Downloading wheels")
        if pip_self:
            spec, files = pip_self
            _run(fetch(True) + [x for f in files or [] for x in ("-c", str(f))] + [spec], log,
                 "Checking the pinned pip (dry run)" if dry_run else "Downloading the pinned pip")
    finally:
        primary = sys.exception()
        try:
            work.rmdir()
        except OSError:
            message = "  retained wheel scratch: " + str(work)
            if primary is not None:
                primary.add_note(message)
            try:
                log(message)
            except BaseException as failure:
                if primary is None:
                    raise
                primary.add_note("Wheel scratch reporting failed: " + type(failure).__name__)


def wheel_items(folder: Path) -> list:
    """FileItems for every file of a wheel folder (packed from disk, not from git)."""
    return [FileItem(p.name, MODE_FILE, "", p.stat().st_size, local=str(p))
            for p in sorted(Path(folder).iterdir()) if p.is_file()]
