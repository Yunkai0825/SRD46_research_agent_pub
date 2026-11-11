"""
zip_images.gitsource -- read-only access to a git repository's committed files.
=================================================================================

Everything the packer packs comes from git OBJECTS of a commit (``git ls-tree``, ``git cat-file --batch``),
never from the working tree: a file that is not committed (a key file, a local settings file, an ignored
database) cannot reach an image. No command here writes to the repository.

    repo = GitRepo(path)
    commit = repo.resolve("HEAD")                  -> 40-hex commit id
    info = repo.commit_info(commit)                -> {"tree", "date", "subject"}
    entries = repo.list_tree(commit)               -> [TreeEntry] (blobs, links, submodules AND folders)
    data = repo.blob_bytes(oid)                    -> bytes of one blob
    with repo.blobs() as reader:                   -> one `git cat-file --batch` for many blobs, in order
        reader.request([oid, ...]); stream = reader.next(oid); stream.read(n) ...
"""

from __future__ import annotations

import subprocess
import os
import stat
from pathlib import Path
import threading
from dataclasses import dataclass

from .lifecycle import defer_interrupts


class GitError(RuntimeError):
    """A git command failed or git is not available."""


@dataclass(frozen=True)
class TreeEntry:
    path: str          # repository-relative, forward slashes
    mode: str          # "100644", "100755", "120000", "160000" (submodule), "040000" (folder)
    kind: str          # "blob", "tree", "commit"
    oid: str           # 40-hex object id
    size: int          # bytes (blobs); -1 for folders and submodules


def _run(args: list, cwd: str, data: bytes = None, timeout=None) -> bytes:
    try:
        proc = subprocess.run(["git", "-C", cwd, *args], input=data, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=timeout)
    except FileNotFoundError:
        raise GitError("git is not installed or not on PATH") from None
    if proc.returncode != 0:
        raise GitError("git {} failed: {}".format(" ".join(args[:3]),
                                                 proc.stderr.decode("utf-8", "replace").strip()))
    return proc.stdout


class GitRepo:
    """A repository on disk, read through git's own commands."""

    def __init__(self, path):
        self.path = str(path)
        top = _run(["rev-parse", "--show-toplevel"], self.path).decode("utf-8").strip()
        self.top = top or self.path

    def resolve(self, rev: str) -> str:
        """A revision (HEAD, a branch, a short id) -> its 40-hex commit id."""
        return _run(["rev-parse", "--verify", "--end-of-options", rev + "^{commit}"], self.path).decode().strip()

    def commit_info(self, commit: str) -> dict:
        out = _run(["show", "-s", "--format=%T%x00%cI%x00%s", commit], self.path).decode("utf-8", "replace")
        tree, date, subject = (out.rstrip("\n").split("\0") + ["", "", ""])[:3]
        return {"tree": tree, "date": date, "subject": subject}

    def list_tree(self, commit: str) -> list:
        """Every entry of the commit's tree, folders included (``ls-tree -r -t -l -z``)."""
        raw = _run(["ls-tree", "-r", "-t", "-l", "-z", "--full-tree", commit], self.path)
        out = []
        for rec in raw.split(b"\0"):
            if not rec:
                continue
            meta, _, path = rec.partition(b"\t")
            mode, kind, oid, size = meta.decode("ascii").split()
            try:
                text = path.decode("utf-8")
            except UnicodeDecodeError:
                raise GitError("a path is not valid UTF-8: {!r}".format(path)) from None
            out.append(TreeEntry(text, mode, kind, oid, int(size) if size != "-" else -1))
        return out

    def blob_bytes(self, oid: str) -> bytes:
        return _run(["cat-file", "blob", oid], self.path)

    def blobs(self) -> "BlobReader":
        return BlobReader(self.path)


class BlobStream:
    """One blob of a running ``cat-file --batch``: read(n) until its size is used up."""

    def __init__(self, reader: "BlobReader", oid: str, size: int):
        self.oid, self.size, self.left = oid, size, size
        self._reader = reader

    def read(self, n: int = -1) -> bytes:
        if self.left <= 0:
            return b""
        n = self.left if n is None or n < 0 else min(n, self.left)
        data = self._reader._read_exact(n)
        self.left -= len(data)
        if self.left == 0:
            self._reader._finish()
        return data

    def drain(self) -> None:
        while self.left:
            self.read(1 << 20)


class BlobReader:
    """A ``git cat-file --batch`` process: request object ids in order, then take their contents in order.

    A feeder thread writes the requested ids, so git never waits for us to ask while we read."""

    def __init__(self, path: str):
        executable = "git"
        if os.name == "nt":
            # Git for Windows puts a launcher on PATH. Killing that launcher
            # leaves the actual cat-file process holding both pipes. Use the
            # real binary reported by Git itself, or refuse an unknown layout.
            directory = _run(["--exec-path"], path, timeout=30).decode("utf-8").strip()
            actual = Path(directory) / "git.exe"
            if len(directory.splitlines()) != 1 or not actual.is_absolute():
                raise GitError("Git --exec-path did not name one absolute Windows directory")
            try:
                info = actual.lstat()
            except OSError:
                raise GitError("Cannot locate the Windows Git binary at git --exec-path/git.exe") from None
            if not stat.S_ISREG(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise GitError("Git --exec-path/git.exe must be an ordinary executable file")
            executable = str(actual)
        try:
            self.proc = subprocess.Popen([executable, "-C", path, "cat-file", "--batch"], stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE)
        except FileNotFoundError:
            raise GitError("git is not installed or not on PATH") from None
        self._out = self.proc.stdout
        self._threads = []
        self._open = None
        self.termination_confirmed = False
        self.process_reaped = False
        self.feeders_stopped = False
        self.streams_closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            self.close()
        except BaseException as failure:
            if exc is None:
                raise
            exc.add_note("Git reader cleanup failed: " + type(failure).__name__ + ": " + str(failure))

    def request(self, oids: list) -> None:
        payload = "".join(o + "\n" for o in oids).encode("ascii")

        def feed():
            try:
                self.proc.stdin.write(payload)
                self.proc.stdin.flush()
            except (BrokenPipeError, OSError, ValueError):
                pass

        for t in self._threads:
            t.join()
        t = threading.Thread(target=feed, daemon=True)
        t.start()
        self._threads = [t]

    def _read_exact(self, n: int) -> bytes:
        chunks, left = [], n
        while left:
            data = self._out.read(left)
            if not data:
                raise GitError("git cat-file stopped early")
            chunks.append(data)
            left -= len(data)
        return b"".join(chunks) if len(chunks) != 1 else chunks[0]

    def _readline(self) -> bytes:
        line = self._out.readline()
        if not line.endswith(b"\n"):
            raise GitError("git cat-file stopped early")
        return line[:-1]

    def _finish(self) -> None:
        if self._read_exact(1) != b"\n":
            raise GitError("git cat-file: unexpected output after a blob")
        self._open = None

    def next(self, oid: str) -> BlobStream:
        """The next requested blob; ``oid`` must be the id requested next."""
        if self._open is not None and self._open.left:
            raise GitError("the previous blob was not read to its end")
        header = self._readline().decode("ascii", "replace").split()
        if len(header) < 2 or header[0] != oid:
            raise GitError("git cat-file answered {!r} for {}".format(" ".join(header), oid))
        if header[1] != "blob" or len(header) != 3:
            raise GitError("object {} is {}, not a blob".format(oid, " ".join(header[1:])))
        stream = BlobStream(self, oid, int(header[2]))
        if stream.size == 0:
            self._finish()
        self._open = stream
        return stream

    def close(self) -> None:
        # Stop the read-only child before touching buffered stdin: a feeder can
        # hold that buffer lock while git is blocked writing unread stdout.
        with defer_interrupts():
            failures = []
            try:
                if self.proc.poll() is None:
                    self.proc.terminate()
                self.proc.wait(timeout=30)
            except BaseException as failure:
                failures.append(failure)
                try:
                    if self.proc.poll() is None:
                        self.proc.kill()
                    self.proc.wait(timeout=30)
                except BaseException as fallback:
                    failures.append(fallback)
            if self.proc.poll() is None:
                error = GitError("UNCONFIRMED: git cat-file did not exit")
                for failure in failures:
                    error.add_note(type(failure).__name__)
                raise error
            self.process_reaped = True
            for thread in self._threads:
                try:
                    thread.join(timeout=5)
                except BaseException as failure:
                    failures.append(failure)
                    thread.join(timeout=5)
            if any(thread.is_alive() for thread in self._threads):
                raise GitError("UNCONFIRMED: git request feeder did not stop after child exit")
            self.feeders_stopped = True
            close_failures = []
            for stream in (self.proc.stdin, self.proc.stdout):
                if stream is not None:
                    try:
                        stream.close()
                    except (BrokenPipeError, OSError):
                        # The peer was deliberately stopped after needed bytes.
                        pass
                    except BaseException as failure:
                        close_failures.append(failure)
            self.termination_confirmed = self.process_reaped and self.feeders_stopped
            self.streams_closed = all(stream is None or stream.closed for stream in (self.proc.stdin, self.proc.stdout))
            if close_failures or not self.streams_closed:
                error = GitError("git cat-file pipe close failed")
                raise error from (close_failures[0] if close_failures else None)
            for failure in failures:
                if isinstance(failure, (KeyboardInterrupt, SystemExit)):
                    raise failure
