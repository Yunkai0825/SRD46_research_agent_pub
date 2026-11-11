"""Read output files from disk first, or directly from verified ZIP compartments."""
from __future__ import annotations

import fnmatch
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import shutil
import threading
from types import SimpleNamespace
import uuid
import zipfile

from .output_packs import fs_path
from .output_lock import archive_lock
from .output_layout import PartRoot
from ..unpack_images import check_rel, chunk_entry, iter_events, check_part_files


def _relative(value):
    return check_rel(value, "archive path")


class OutputArchives:
    """A directory overlay. Reading never extracts or modifies output files."""

    def __init__(self, root):
        self.root = fs_path(root)
        self._resolved_root = self.root.resolve()
        self.store = self.root / "_output_archives"
        self.runs = {}
        self.files = {}
        self.dirs = {"": set()}
        self.dir_times = {}
        self._loaded = set()
        self._members = {}
        self._verified_parts = {}
        self._lock = threading.RLock()
        self.web_archives = sorted((self.root / "_benchmark/_Claude_web_answers").glob("*.zip"))
        catalog = self.store / "runs"
        if not catalog.is_dir():
            return
        for path in sorted(catalog.glob("*.json")):
            doc = json.loads(path.read_text("utf-8"))
            if doc.get("format") != "srd46-output-archive-v1":
                raise ValueError("Unknown output archive format")
            target = _relative(doc["target"])
            if target.split("/")[0] not in {"_benchmark", "_output"} or target in self.runs:
                raise ValueError("Invalid or duplicate output target: " + target)
            record = _relative(doc["record"])
            if not record.startswith("compartments/"):
                raise ValueError("Invalid archive record path")
            self.runs[target] = doc
            doc["_catalog"] = path
            self._add_dir(target)
            for rel, mtime in doc["directories"].items():
                directory = target + ("/" + _relative(rel) if rel else "")
                self._add_dir(directory)
                self.dir_times[directory] = int(mtime)

    def _add_dir(self, rel):
        self.dirs.setdefault(rel, set())
        while rel:
            parent, _, name = rel.rpartition("/")
            self.dirs.setdefault(parent, set()).add(name)
            rel = parent

    def _load(self, rel):
        target = next((p for p in self.runs if rel == p or rel.startswith(p + "/")), None)
        if target is None:
            return
        if (self.store / "update_pending.json").exists():
            raise RuntimeError("Archive replacement is in progress or needs recovery; finish or rerun the pack command")
        with self._lock:
            doc = self.runs[target]
            stamp = ((self.store / doc["record"]).stat().st_mtime_ns, doc["_catalog"].stat().st_mtime_ns)
            if target in self._loaded and doc.get("_stamp") == stamp:
                return
            fresh = json.loads(doc["_catalog"].read_text("utf-8"))
            doc.update(fresh)
            for name in [name for name in self.files if name.startswith(target + "/")]:
                self.files.pop(name)
            for name in [name for name in self.dirs if name == target or name.startswith(target + "/")]:
                self.dirs.pop(name)
                self.dir_times.pop(name, None)
            self._add_dir(target)
            self._members.pop(target, None)
            record = json.loads((self.store / doc["record"]).read_text("utf-8"))
            parts = record["parts"]
            for part in parts:
                if PurePosixPath(_relative(part["file"])).name != part["file"]:
                    raise ValueError("Invalid ZIP part path")
                if not 0 <= part["size"] < 100_000_000:
                    raise ValueError("Oversize ZIP part")
            for fd in record["files"]:
                name = _relative(fd["name"])
                if fd["mode"] not in {"100644", "100755"}:
                    raise ValueError("Output archives may contain only regular files")
                full = target + "/" + name
                if full in self.files:
                    raise ValueError("Duplicate archive file: " + full)
                self.files[full] = (target, fd)
                parent, _, basename = full.rpartition("/")
                self._add_dir(parent)
                self.dirs[parent].add(basename)
            doc["record_data"] = record
            doc["_stamp"] = stamp
            for relpath, ns in doc["directories"].items():
                directory = target + ("/" + relpath if relpath else "")
                self._add_dir(directory)
                self.dir_times[directory] = ns
            self._loaded.add(target)

    def rel(self, value):
        path = fs_path(value)
        for base in (self.root, self._resolved_root):
            try:
                return path.relative_to(base).as_posix().removeprefix("./")
            except ValueError:
                pass
        return None

    def path(self, value):
        if isinstance(value, OutputPath) and value.archives is self:
            return value
        return OutputPath(self, fs_path(value))

    def file(self, rel):
        self._load(rel)
        return self.files.get(rel)

    def children(self, rel):
        self._load(rel)
        return self.dirs.get(rel, set())

    def _locations(self, target):
        with self._lock:
            if target in self._members:
                return self._members[target]
            doc = self.runs[target]
            record = doc["record_data"]
            expected = set()
            for fd in record["files"]:
                n = fd.get("chunks", 0)
                expected.update(chunk_entry(fd["name"], i, n) for i in range(1, n + 1)) if n else expected.add(fd["name"])
            members = {}
            for part in record["parts"]:
                path = self.store / "zips" / target / part["file"]
                if path.stat().st_size != part["size"]:
                    raise OSError("ZIP part size mismatch: " + part["file"])
                with zipfile.ZipFile(path) as archive:
                    for info in archive.infolist():
                        if info.filename not in expected or info.filename in members:
                            raise OSError("Unexpected or duplicate ZIP member: " + info.filename)
                        members[info.filename] = (path, info.file_size)
            if set(members) != expected:
                raise OSError("Incomplete archive: " + target)
            self._members[target] = members
            return members

    def open(self, rel):
        lock = archive_lock(self.store)
        lock.__enter__()
        try:
            stream = self._open_locked(rel)
            stream.raw.on_close = lambda: lock.__exit__(None, None, None)
            return stream
        except BaseException:
            lock.__exit__(None, None, None)
            raise

    def _open_locked(self, rel):
        entry = self.file(rel)
        if entry is None:
            raise FileNotFoundError(rel)
        target, fd = entry
        members = self._locations(target)
        n = fd.get("chunks", 0)
        names = [chunk_entry(fd["name"], i, n) for i in range(1, n + 1)] if n else [fd["name"]]
        chunks = [(members[name][0], name, members[name][1]) for name in names]
        if sum(item[2] for item in chunks) != fd["size"]:
            raise OSError("Archive file size mismatch: " + rel)
        parts = {p["file"]: p for p in self.runs[target]["record_data"]["parts"]}
        for path in {item[0] for item in chunks}:
            part = parts[path.name]
            stamp = path.stat()
            identity = (stamp.st_size, stamp.st_mtime_ns, stamp.st_ctime_ns, part["sha256"])
            with self._lock:
                if self._verified_parts.get(path) != identity:
                    digest = hashlib.sha256()
                    with path.open("rb") as source:
                        while block := source.read(4 << 20):
                            digest.update(block)
                    if stamp.st_size != part["size"] or digest.hexdigest() != part["sha256"]:
                        raise OSError("ZIP checksum mismatch: " + path.name)
                    self._verified_parts[path] = identity
        stream = io.BufferedReader(_ArchiveStream(chunks))
        stream.expected_sha256 = fd["sha256"]
        return stream

    def _safe_destination(self, dest):
        if not dest.resolve().is_relative_to(self._resolved_root):
            raise ValueError("Extraction path escapes output root")
        parent = dest
        while parent != self.root:
            if os.path.lexists(parent):
                metadata = parent.lstat()
                if parent.is_symlink() or (getattr(metadata, "st_file_attributes", 0) & 0x400):
                    raise ValueError("Extraction refuses linked paths")
            if parent == parent.parent:
                raise ValueError("Extraction path is outside the output root")
            parent = parent.parent

    def unpack_status(self):
        from .output_health import unpack_status
        with archive_lock(self.store):
            return unpack_status(self)

    def extract(self, progress=lambda **kwargs: None):
        with archive_lock(self.store):
            return self._extract_locked(progress)

    def _extract_locked(self, progress):
        """Unpack missing files only, checking hashes and preserving existing files."""
        written = skipped = 0
        for target, doc in self.runs.items():
            self._load(target)
            record = dict(doc["record_data"], name=target)
            part_root = PartRoot(self.store / "zips" / target)
            errors = check_part_files(part_root, [record], full=True)
            if errors:
                raise OSError("; ".join(errors))
            directory_times = {}
            for rel, recorded_ns in doc["directories"].items():
                directory = self.root / target / rel
                self._safe_destination(directory)
                directory_times[directory] = directory.stat().st_mtime_ns if directory.exists() else recorded_ns
                directory.mkdir(parents=True, exist_ok=True)
            handle = tmp = dest = None
            try:
                for event, data in iter_events(part_root, record, record["files"]):
                    if event == "begin":
                        dest = self.root / target / _relative(data["name"])
                        self._safe_destination(dest)
                        digest, size = hashlib.sha256(), 0
                        if os.path.lexists(dest):
                            skipped += 1
                        else:
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            tmp = dest.with_name(".unpack-" + uuid.uuid4().hex)
                            handle = tmp.open("xb")
                    elif event == "data":
                        digest.update(data)
                        size += len(data)
                        if handle is not None:
                            handle.write(data)
                    else:
                        if size != data["size"] or digest.hexdigest() != data["sha256"]:
                            raise OSError("Archive checksum mismatch: " + data["name"])
                        if handle is not None:
                            handle.close()
                            handle = None
                            mtime = doc["mtimes_ns"][data["name"]]
                            os.utime(tmp, ns=(mtime, mtime))
                            try:
                                if os.name == "nt":
                                    os.rename(tmp, dest)  # Windows rename never replaces an existing file.
                                else:
                                    os.link(tmp, dest)
                                    tmp.unlink()
                                written += 1
                            except FileExistsError:
                                skipped += 1
                                tmp.unlink()
                            tmp = None
                        progress(written=written, skipped=skipped, run=target)
            finally:
                if handle is not None:
                    handle.close()
                if tmp is not None and tmp.exists():
                    tmp.unlink()
                for directory, ns in sorted(directory_times.items(), key=lambda item: len(item[0].parts), reverse=True):
                    os.utime(directory, ns=(ns, ns))
        self.web_archives = sorted((self.root / "_benchmark/_Claude_web_answers").glob("*.zip"))
        for source in self.web_archives:
            destination = source.parent / source.stem
            self._safe_destination(destination)
            with zipfile.ZipFile(source) as archive:
                for info in archive.infolist():
                    name = _relative(info.filename.rstrip("/"))
                    if stat.S_ISLNK(info.external_attr >> 16):
                        raise ValueError("Web archive contains a symbolic link")
                    dest = destination / name
                    self._safe_destination(dest)
                    if info.is_dir():
                        dest.mkdir(parents=True, exist_ok=True)
                        continue
                    if os.path.lexists(dest):
                        skipped += 1
                        continue
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    tmp = dest.with_name(".unpack-" + uuid.uuid4().hex)
                    try:
                        with archive.open(info) as handle, tmp.open("xb") as output:
                            shutil.copyfileobj(handle, output, length=1 << 20)
                        try:
                            if os.name == "nt":
                                os.rename(tmp, dest)
                            else:
                                os.link(tmp, dest)
                                tmp.unlink()
                            written += 1
                        except FileExistsError:
                            skipped += 1
                    finally:
                        if tmp.exists():
                            tmp.unlink()
                    progress(written=written, skipped=skipped, run=source.name)
        return {"written": written, "skipped": skipped}


class _ArchiveStream(io.RawIOBase):
    """Seekable stream joining the existing packer's chunk members."""

    def __init__(self, chunks):
        self.chunks = chunks
        self.position = 0
        self.length = sum(item[2] for item in chunks)
        self._zip = self._stream = None
        self._index = None
        self.on_close = None

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        pos = offset if whence == 0 else self.position + offset if whence == 1 else self.length + offset if whence == 2 else -1
        if pos < 0:
            raise ValueError("Invalid seek position")
        self.position = pos
        return pos

    def readinto(self, buffer):
        if self.position >= self.length:
            return 0
        start = 0
        for index, (path, name, size) in enumerate(self.chunks):
            if self.position < start + size:
                if self._index != index:
                    self._close_member()
                    self._zip = zipfile.ZipFile(path)
                    self._stream = self._zip.open(name)
                    self._index = index
                self._stream.seek(self.position - start)
                data = self._stream.read(min(len(buffer), start + size - self.position))
                buffer[:len(data)] = data
                self.position += len(data)
                return len(data)
            start += size
        return 0

    def _close_member(self):
        if self._stream is not None:
            self._stream.close()
        if self._zip is not None:
            self._zip.close()
        self._stream = self._zip = None

    def close(self):
        self._close_member()
        if self.on_close is not None:
            callback, self.on_close = self.on_close, None
            callback()
        super().close()


class OutputPath(os.PathLike):
    """The read-only Path operations used by the results browser."""

    def __init__(self, archives, path):
        self.archives, self.local = archives, path

    def __fspath__(self):
        return str(self.local)

    def __str__(self):
        return str(self.local)

    def __repr__(self):
        return f"OutputPath({str(self)!r})"

    def __hash__(self):
        return hash(self.local)

    def __eq__(self, other):
        return self.local == (other.local if isinstance(other, OutputPath) else other)

    def __lt__(self, other):
        return str(self) < str(other)

    def __truediv__(self, part):
        return self.archives.path(self.local / part)

    def joinpath(self, *parts):
        return self.archives.path(self.local.joinpath(*parts))

    @property
    def parent(self):
        return self.archives.path(self.local.parent)

    @property
    def name(self):
        return self.local.name

    @property
    def stem(self):
        return self.local.stem

    @property
    def suffix(self):
        return self.local.suffix

    @property
    def rel(self):
        value = self.archives.rel(self.local)
        return "" if value == "." else value

    @property
    def archived(self):
        rel = self.rel
        return rel is not None and any(rel == target or rel.startswith(target + "/") for target in self.archives.runs)

    def absolute(self):
        return self.archives.path(self.local.absolute())

    def resolve(self, strict=False):
        return self.archives.path(self.local.resolve(strict=strict))

    def relative_to(self, other):
        return self.local.relative_to(fs_path(other))

    def as_posix(self):
        return self.local.as_posix()

    def exists(self):
        if self.local.exists():
            return True
        if self.rel is None:
            return False
        self.archives._load(self.rel)
        return self.rel in self.archives.dirs or self.rel in self.archives.files

    def is_file(self):
        if os.path.lexists(self.local):
            return self.local.is_file()
        return self.rel is not None and self.archives.file(self.rel) is not None

    def is_dir(self):
        if os.path.lexists(self.local):
            return self.local.is_dir()
        if self.rel is None:
            return False
        self.archives._load(self.rel)
        return self.rel in self.archives.dirs

    def stat(self):
        if os.path.lexists(self.local):
            return self.local.stat()
        rel = self.rel
        entry = self.archives.file(rel) if rel is not None else None
        if entry:
            target, fd = entry
            ns = self.archives.runs[target]["mtimes_ns"][fd["name"]]
            return SimpleNamespace(st_size=fd["size"], st_mtime=ns / 1e9, st_mtime_ns=ns, st_mode=stat.S_IFREG | 0o644)
        if rel in self.archives.dirs:
            ns = self.archives.dir_times.get(rel, 0)
            return SimpleNamespace(st_size=0, st_mtime=ns / 1e9, st_mtime_ns=ns, st_mode=stat.S_IFDIR | 0o755)
        raise FileNotFoundError(str(self))

    def iterdir(self):
        if not self.is_dir():
            raise NotADirectoryError(str(self))
        names = set(self.archives.children(self.rel)) if self.rel is not None else set()
        if self.local.is_dir():
            names.update(p.name for p in self.local.iterdir())
        for name in sorted(names):
            yield self / name

    def glob(self, pattern):
        parts = pattern.replace("\\", "/").split("/")
        if parts[0] == "**":
            yield from self.glob("/".join(parts[1:]) or "*")
            for child in self.iterdir():
                if child.is_dir():
                    yield from child.glob(pattern)
            return
        for child in self.iterdir():
            if fnmatch.fnmatch(child.name, parts[0]):
                if len(parts) == 1:
                    yield child
                elif child.is_dir():
                    yield from child.glob("/".join(parts[1:]))

    def rglob(self, pattern):
        return self.glob("**/" + pattern)

    def open(self, mode="r", buffering=-1, encoding=None, errors=None, newline=None):
        if mode not in {"r", "rb", "rt"}:
            raise ValueError("Output archive paths are read-only")
        if os.path.lexists(self.local):
            return self.local.open(mode, buffering=buffering, encoding=encoding, errors=errors, newline=newline)
        if self.rel is None:
            raise FileNotFoundError(str(self))
        stream = self.archives.open(self.rel)
        return stream if "b" in mode else io.TextIOWrapper(stream, encoding=encoding, errors=errors, newline=newline)

    def read_bytes(self):
        if os.path.lexists(self.local):
            return self.local.read_bytes()
        with self.open("rb") as stream:
            data = stream.read()
            expected = stream.expected_sha256
        if hashlib.sha256(data).hexdigest() != expected:
            raise OSError("Archive checksum mismatch: " + str(self))
        return data

    def read_text(self, encoding=None, errors=None):
        if os.path.lexists(self.local):
            return self.local.read_text(encoding=encoding, errors=errors)
        # Match pathlib's universal-newline decoding.
        with io.TextIOWrapper(io.BytesIO(self.read_bytes()), encoding=encoding, errors=errors) as stream:
            return stream.read()


_default = None


def default_archives():
    global _default
    if _default is None:
        _default = OutputArchives(Path(__file__).absolute().parents[2])
    return _default


def output_path(value):
    return value if isinstance(value, OutputPath) else default_archives().path(value)
