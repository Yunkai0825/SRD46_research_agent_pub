"""
zip_images.zipwriter -- deterministic zip parts with exact size accounting.
===========================================================================

Why a small writer of its own instead of ``zipfile.ZipFile.write``: every entry is compressed ONCE, before
it is placed, so the packer knows its exact size in the zip and can start a new part before a zip would
pass the limit. The bytes are fully determined by the entries: fixed date (1980-01-01 00:00), fixed
"made by unix" attributes carrying the git mode, entries in the given order, no extra fields, no comments.
The same files with the same zlib library therefore always give byte-identical zips (and sha256s).

The format is the classic zip (no ZIP64): a part stays under 100 MB and holds at most MAX_ENTRIES entries,
and no entry reaches 4 GiB (the packer splits big files into chunks first). Any unzip tool, and Python's
``zipfile``, reads these zips.
"""

from __future__ import annotations

import hashlib
import os
import struct
import zlib
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .unpack_images import HARD_LIMIT, MODE_EXEC, MODE_LINK

LOCAL = struct.Struct("<IHHHHHIIIHH")             # 30 bytes + name
CENTRAL = struct.Struct("<IHHHHHHIIIHHHHHII")     # 46 bytes + name
END = struct.Struct("<IHHHHIIH")                  # 22 bytes
SIG_LOCAL, SIG_CENTRAL, SIG_END = 0x04034B50, 0x02014B50, 0x06054B50
VERSION = 20                                      # 2.0: deflate
MADE_BY = (3 << 8) | VERSION                      # "unix", so the mode bits mean what they say
DOS_TIME, DOS_DATE = 0, (0 << 9) | (1 << 5) | 1   # 1980-01-01 00:00:00
FLAG_UTF8 = 0x800
STORED, DEFLATED = 0, 8
MAX_ENTRIES = 60_000                              # stays well under the classic 65,535
DEFAULT_LEVEL = 6

_ATTR = {MODE_EXEC: 0o100755, MODE_LINK: 0o120777}


def external_attr(mode: str) -> int:
    return _ATTR.get(mode, 0o100644) << 16


@dataclass
class Entry:
    """One zip member, already compressed."""
    name: str
    mode: str
    data: bytes              # the bytes as stored in the zip
    method: int
    crc: int
    size: int                # uncompressed size

    @property
    def name_bytes(self) -> bytes:
        return self.name.encode("utf-8")

    @property
    def flags(self) -> int:
        return FLAG_UTF8 if not self.name.isascii() else 0

    def cost(self) -> int:
        """Bytes this entry adds to a zip: local header + data + central record."""
        n = len(self.name_bytes)
        return LOCAL.size + n + len(self.data) + CENTRAL.size + n


def prepare(name: str, mode: str, raw: bytes, level: int = DEFAULT_LEVEL, store: bool = False) -> Entry:
    """Compress ``raw`` (raw deflate at ``level``) unless ``store`` or unless deflate would not make it smaller."""
    crc = zlib.crc32(raw) & 0xFFFFFFFF
    if raw and not store:
        c = zlib.compressobj(level, zlib.DEFLATED, -15)
        data = c.compress(raw) + c.flush()
        if len(data) < len(raw):
            return Entry(name, mode, data, DEFLATED, crc, len(raw))
    return Entry(name, mode, raw, STORED, crc, len(raw))


def overhead() -> int:
    return END.size


class PartWriter:
    """A zip being written: ``fits(entry)`` says whether the entry keeps it within ``limit``."""

    def __init__(self, path: Path, limit: int):
        if not 0 < limit < HARD_LIMIT:
            raise ValueError("the zip limit must be under {:,} bytes".format(HARD_LIMIT))
        self.path = Path(path)
        self.limit = limit
        self.fh = open(self.path, "wb")
        self.sha = hashlib.sha256()
        self.offset = 0
        self.central = []
        self.central_size = 0
        self.entries = []            # (name, size, crc) for the read-back check

    def fits(self, e: Entry) -> bool:
        if len(self.central) >= MAX_ENTRIES:
            return False
        return self.offset + self.central_size + e.cost() + END.size <= self.limit

    def _write(self, b: bytes) -> None:
        self.fh.write(b)
        self.sha.update(b)
        self.offset += len(b)

    def add(self, e: Entry) -> None:
        nb = e.name_bytes
        at = self.offset
        self._write(LOCAL.pack(SIG_LOCAL, VERSION, e.flags, e.method, DOS_TIME, DOS_DATE, e.crc, len(e.data),
                               e.size, len(nb), 0) + nb)
        self._write(e.data)
        rec = CENTRAL.pack(SIG_CENTRAL, MADE_BY, VERSION, e.flags, e.method, DOS_TIME, DOS_DATE, e.crc,
                           len(e.data), e.size, len(nb), 0, 0, 0, 0, external_attr(e.mode), at) + nb
        self.central.append(rec)
        self.central_size += len(rec)
        self.entries.append((e.name, e.size, e.crc))

    def close(self) -> tuple:
        """Write the central directory; -> (size, sha256, entry count)."""
        start = self.offset
        for rec in self.central:
            self._write(rec)
        n = len(self.central)
        self._write(END.pack(SIG_END, 0, 0, n, n, self.central_size, start, 0))
        self.fh.close()
        size = self.offset
        if size >= HARD_LIMIT or size > self.limit:
            raise RuntimeError("{} came out at {:,} bytes -- over the limit".format(self.path.name, size))
        return size, self.sha.hexdigest(), n

    def abort(self, *, keep: bool = False) -> None:
        try:
            self.fh.close()
        finally:
            if not keep:
                try:
                    os.unlink(self.path)
                except OSError:
                    pass


def read_back(path: Path, entries: list) -> None:
    """Open a written zip with Python's zipfile and compare its directory with what was written (no
    decompression: the full stream check is `verify`)."""
    with zipfile.ZipFile(str(path)) as zf:
        got = [(i.filename, i.file_size, i.CRC) for i in zf.infolist()]
    if got != entries:
        raise RuntimeError("{} does not read back as written".format(path.name))
