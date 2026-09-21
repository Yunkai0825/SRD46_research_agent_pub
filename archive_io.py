"""Read ordinary ZIP collections, single ZIPs, and legacy numbered volumes.

``name.part001-of-003.zip`` files are independent, Explorer-readable ZIPs.
Together they expose the logical archive ``name.zip`` without extraction.
Parts may include an ``.outputs`` or ``.checkpoints`` label before ``.zip``
so that the complete readable outputs can be identified without opening parts.
An individually oversized member is stored as ``original.__chunks__/000001-of-N``
(with six-digit counters); reads reconstruct its original bytes in memory-sized
blocks. Filenames encode completeness, with no alias or routing manifest.
"""
from __future__ import annotations

import bisect
import copy
import io
import re
import zipfile
from contextlib import ExitStack, contextmanager
from functools import lru_cache
from pathlib import Path

_VOLUME_NAME = re.compile(r"^(?P<archive>.+\.zip)\.(?P<number>\d{3})$", re.IGNORECASE)
_PART_NAME = re.compile(
    r"^(?P<stem>.+)\.part(?P<number>\d{3})-of-(?P<count>\d{3})"
    r"(?:\.(?P<role>outputs|checkpoints))?\.zip$",
    re.IGNORECASE,
)
_CHUNK_NAME = re.compile(r"^(?P<member>.+)\.__chunks__/(?P<number>\d{6})-of-(?P<count>\d{6})$")


def logical_archive_path(path: Path | str) -> Path:
    """Return the collection's logical ZIP path, or the original ordinary path."""
    path = Path(path)
    match = _PART_NAME.fullmatch(path.name)
    if match:
        return path.with_name(match.group("stem") + ".zip")
    match = _VOLUME_NAME.fullmatch(path.name)
    if match and match.group("number") == "001":
        return path.with_name(match.group("archive"))
    return path


def _collection_parts(path: Path) -> tuple[Path, ...]:
    matches = []
    for child in path.parent.iterdir():
        match = _PART_NAME.fullmatch(child.name)
        if match and child.is_file() and match.group("stem") == path.stem:
            matches.append((int(match.group("number")), int(match.group("count")), child))
    if not matches:
        return ()
    totals = {count for _, count, _ in matches}
    if len(totals) != 1 or 0 in totals:
        raise zipfile.BadZipFile(f"Inconsistent ZIP collection sizes: {path}")
    total = totals.pop()
    matches.sort(key=lambda item: item[0])
    if [number for number, _, _ in matches] != list(range(1, total + 1)):
        raise zipfile.BadZipFile(f"Missing or duplicate ZIP collection parts: {path} (expected {total})")
    return tuple(part for _, _, part in matches)


def _archive_parts(path: Path | str) -> tuple[Path, ...]:
    path = logical_archive_path(path)
    if path.is_file():
        return (path,)
    collection = _collection_parts(path)
    if collection:
        return collection
    prefix = path.name + "."
    parts = sorted(
        (child for child in path.parent.iterdir()
         if child.name.startswith(prefix) and len(child.name) == len(prefix) + 3
         and child.name[len(prefix):].isdigit() and child.is_file()),
        key=lambda child: child.name,
    )
    if not parts:
        raise FileNotFoundError(path)
    for number, part in enumerate(parts, 1):
        expected = f"{path.name}.{number:03d}"
        if part.name != expected:
            raise zipfile.BadZipFile(f"Missing ZIP volume: {path.with_name(expected)}")
    return tuple(parts)


def archive_exists(path: Path | str) -> bool:
    """Whether the archive or any collection part exists; not an integrity check."""
    path = logical_archive_path(path)
    if path.is_file() or path.with_name(path.name + ".001").is_file():
        return True
    if not path.parent.is_dir():
        return False
    return any(match and match.group("stem") == path.stem and child.is_file()
               for child in path.parent.iterdir()
               for match in [_PART_NAME.fullmatch(child.name)])


def archive_signature(path: Path | str) -> tuple[tuple[str, int, int], ...]:
    """Cache key covering every part's path, modification time, and byte count."""
    signature = []
    for part in _archive_parts(path):
        stat = part.stat()
        signature.append((str(part), stat.st_mtime_ns, stat.st_size))
    return tuple(signature)


class _VolumeReader(io.RawIOBase):
    """A seekable read-only file spanning numbered volumes, opening one at a time."""

    def __init__(self, parts: tuple[Path, ...]):
        super().__init__()
        self._parts = parts
        self._offsets = [0]
        self._position = 0
        self._handle = None
        self._handle_index = None
        for part in parts:
            size = part.stat().st_size
            if not size:
                raise zipfile.BadZipFile(f"Empty ZIP volume: {part}")
            self._offsets.append(self._offsets[-1] + size)

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        self._checkClosed()
        return self._position

    def seek(self, offset, whence=io.SEEK_SET):
        self._checkClosed()
        if whence == io.SEEK_SET:
            position = offset
        elif whence == io.SEEK_CUR:
            position = self._position + offset
        elif whence == io.SEEK_END:
            position = self._offsets[-1] + offset
        else:
            raise ValueError("Invalid seek mode")
        if position < 0:
            raise ValueError("Negative seek position")
        self._position = position
        return position

    def readinto(self, buffer):
        self._checkClosed()
        target = memoryview(buffer).cast("B")
        remaining = min(len(target), max(0, self._offsets[-1] - self._position))
        written = 0
        while remaining:
            index = bisect.bisect_right(self._offsets, self._position) - 1
            if self._handle_index != index:
                if self._handle is not None:
                    self._handle.close()
                self._handle = self._parts[index].open("rb")
                self._handle_index = index
            self._handle.seek(self._position - self._offsets[index])
            count = min(remaining, self._offsets[index + 1] - self._position)
            received = self._handle.readinto(target[written:written + count])
            if not received:
                raise OSError(f"ZIP volume changed or was truncated: {self._parts[index]}")
            written += received
            self._position += received
            remaining -= received
        return written

    def close(self):
        if self._handle is not None:
            self._handle.close()
        super().close()


@lru_cache(maxsize=256)
def _crc32_combine(left, right, right_size):
    """Combine finalized ZIP CRCs without reading the uncompressed members."""
    if right_size <= 0:
        return left

    def multiply(matrix, vector):
        result = 0
        position = 0
        while vector:
            if vector & 1:
                result ^= matrix[position]
            vector >>= 1
            position += 1
        return result

    def square(matrix):
        return [multiply(matrix, value) for value in matrix]

    odd = [0xEDB88320] + [1 << bit for bit in range(31)]
    even = square(odd)
    odd = square(even)
    while right_size:
        even = square(odd)
        if right_size & 1:
            left = multiply(even, left)
        right_size >>= 1
        if not right_size:
            break
        odd = square(even)
        if right_size & 1:
            left = multiply(odd, left)
        right_size >>= 1
    return left ^ right


class _ChunkReader(io.RawIOBase):
    """Sequentially stream one logical member from independently checked chunks."""

    def __init__(self, entries, password=None):
        super().__init__()
        self._entries = iter(entries)
        self._password = password
        self._member = None

    def readable(self):
        return True

    def readinto(self, buffer):
        self._checkClosed()
        target = memoryview(buffer).cast("B")
        written = 0
        while written < len(target):
            if self._member is None:
                try:
                    archive, info = next(self._entries)
                except StopIteration:
                    break
                self._member = archive.open(info, "r", pwd=self._password)
            block = self._member.read(len(target) - written)
            if not block:
                self._member.close()
                self._member = None
                continue
            target[written:written + len(block)] = block
            written += len(block)
        return written

    def close(self):
        if self._member is not None:
            self._member.close()
        super().close()


class _ZipCollection:
    """The read-only subset of ZipFile needed by the browser and database setup."""

    def __init__(self, parts):
        self._stack = ExitStack()
        self._closed = False
        self._entries = {}
        self._infos = {}
        self.comment = b""
        chunks = {}
        try:
            for part in parts:
                archive = self._stack.enter_context(zipfile.ZipFile(part, "r"))
                for info in archive.infolist():
                    match = _CHUNK_NAME.fullmatch(info.filename)
                    if match and not info.is_dir():
                        chunks.setdefault(match.group("member"), []).append(
                            (int(match.group("number")), int(match.group("count")), archive, info))
                    elif ".__chunks__/" in info.filename and not info.is_dir():
                        raise zipfile.BadZipFile(f"Malformed member chunk: {info.filename}")
                    elif info.is_dir():
                        # Explicit directory entries may repeat across ordinary ZIPs.
                        if ".__chunks__/" not in info.filename:
                            self._infos.setdefault(info.filename, info)
                            self._entries.setdefault(info.filename, ((archive, info),))
                    else:
                        if info.filename in self._infos:
                            raise zipfile.BadZipFile(f"Duplicate ZIP collection member: {info.filename}")
                        self._infos[info.filename] = info
                        self._entries[info.filename] = ((archive, info),)
            for name, entries in chunks.items():
                if name in self._infos:
                    raise zipfile.BadZipFile(f"Both whole and chunked member exist: {name}")
                totals = {count for _, count, _, _ in entries}
                if len(totals) != 1 or 0 in totals:
                    raise zipfile.BadZipFile(f"Inconsistent chunk counts: {name}")
                total = totals.pop()
                entries.sort(key=lambda item: item[0])
                if [number for number, _, _, _ in entries] != list(range(1, total + 1)):
                    raise zipfile.BadZipFile(f"Missing or duplicate member chunks: {name}")
                logical = copy.copy(entries[0][3])
                logical.filename = name
                logical.orig_filename = name
                logical.file_size = sum(info.file_size for _, _, _, info in entries)
                logical.compress_size = sum(info.compress_size for _, _, _, info in entries)
                crc = 0
                for _, _, _, info in entries:
                    crc = _crc32_combine(crc, info.CRC, info.file_size)
                logical.CRC = crc
                self._infos[name] = logical
                self._entries[name] = tuple((archive, info) for _, _, archive, info in entries)
        except BaseException:
            self.close()
            raise

    def infolist(self):
        return list(self._infos.values())

    def namelist(self):
        return list(self._infos)

    def getinfo(self, name):
        return self._infos[name]

    def open(self, name, mode="r", pwd=None):
        if self._closed:
            raise ValueError("ZIP collection is closed")
        if mode != "r":
            raise ValueError("ZIP collections are read-only")
        name = name.filename if isinstance(name, zipfile.ZipInfo) else name
        entries = self._entries[name]
        archive, info = entries[0]
        if len(entries) == 1 and info.filename == name:
            return archive.open(info, "r", pwd=pwd)
        return io.BufferedReader(_ChunkReader(entries, pwd), buffer_size=256 * 1024)

    def read(self, name, pwd=None):
        with self.open(name, pwd=pwd) as member:
            return member.read()

    def testzip(self):
        for info in self.infolist():
            try:
                with self.open(info) as member:
                    while member.read(1024 * 1024):
                        pass
            except zipfile.BadZipFile:
                return info.filename
        return None

    def close(self):
        self._closed = True
        self._stack.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


@contextmanager
def open_zip(path: Path | str):
    """Read one logical archive, closing all backing files when the context exits.

    Ordinary ZIP parts expose complete files directly in File Explorer. This
    reader unions their literal member paths and streams any explicitly chunked
    oversized member, retaining per-chunk ZIP CRC checks. Missing parts, missing
    chunks, duplicate members, and inconsistent counts fail before files are read.
    Legacy byte-split volumes remain readable, but new publications use ZIP parts.
    """
    parts = _archive_parts(path)
    if len(parts) == 1 and parts[0] == logical_archive_path(path):
        with zipfile.ZipFile(parts[0], "r") as archive:
            yield archive
    elif _PART_NAME.fullmatch(parts[0].name):
        with _ZipCollection(parts) as archive:
            yield archive
    else:
        with _VolumeReader(parts) as raw:
            with io.BufferedReader(raw, buffer_size=256 * 1024) as stream:
                with zipfile.ZipFile(stream, "r") as archive:
                    yield archive
