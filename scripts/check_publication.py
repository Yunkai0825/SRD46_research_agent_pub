"""Check local publication content without committing, uploading, or changing data."""
from __future__ import annotations

import argparse
import os
import stat
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 100 * 1024 * 1024
LFS_HEADER = b"version https://git-lfs.github.com/spec/v1"


def git(*args: str, data: bytes | None = None) -> bytes:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, input=data, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def decode(value: bytes) -> str:
    return os.fsdecode(value)


def _io_path(path: Path) -> Path:
    """Use extended Windows paths for filesystem I/O, preserving Git's cwd."""
    value = str(path.absolute())
    if os.name != "nt" or value.startswith("\\\\?\\"):
        return Path(value)
    if value.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + value[2:])
    return Path("\\\\?\\" + value)


def check_worktree() -> tuple[int, list[str]]:
    paths = set(git("ls-files", "--cached", "--others", "--exclude-standard", "-z").split(b"\0"))
    errors: list[str] = []
    count = 0
    requirements = []
    for raw in sorted(paths):
        if not raw:
            continue
        name = decode(raw)
        path = _io_path(ROOT / name)
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue  # Tracked deletions are absent from the next tree.
        except OSError as exc:
            errors.append(f"Cannot inspect {name}: {exc}")
            continue
        if stat.S_ISLNK(info.st_mode):
            errors.append(f"Symbolic link is not an original file: {name}")
            continue
        if not stat.S_ISREG(info.st_mode):
            continue  # Submodule entries are checked in the index below.
        count += 1
        if info.st_size > MAX_BYTES:
            errors.append(f"File exceeds GitHub's 100 MiB limit: {name}")
        with path.open("rb") as stream:
            if stream.read(200).startswith(LFS_HEADER):
                errors.append(f"Git LFS pointer: {name}")
        if path.name.lower().startswith("requirements") and path.suffix.lower() == ".txt":
            requirements.append(name)
    if requirements != ["requirements.txt"]:
        errors.append(f"Expected only root requirements.txt; found: {requirements}")
    for raw in git("ls-files", "--cached", "--ignored", "--exclude-standard", "-z").split(b"\0"):
        if raw:
            errors.append(f"Ignored local file is still tracked: {decode(raw)}")
    for raw in git("ls-files", "--stage", "-z").split(b"\0"):
        if raw and raw.split(b" ", 1)[0] in {b"120000", b"160000"}:
            errors.append(f"Pointer entry in index: {decode(raw.split(bytes([9]), 1)[1])}")
    return count, errors


def check_objects(objects: dict[str, str]) -> tuple[int, list[str]]:
    if not objects:
        return 0, []
    errors = []
    inspect = []
    count = 0
    metadata = git(
        "cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)",
        data=("\n".join(objects) + "\n").encode("ascii"),
    )
    for line in metadata.splitlines():
        fields = line.decode("ascii").split()
        if len(fields) != 3:
            errors.append(f"Missing Git object: {fields[0]}")
            continue
        oid, kind, size_text = fields
        if kind == "tree":
            inspect.append((oid, kind))
            continue
        if kind != "blob":
            continue
        count += 1
        size = int(size_text)
        if size > MAX_BYTES:
            errors.append(f"Git blob exceeds 100 MiB: {objects[oid]}")
        if len(LFS_HEADER) <= size <= 4096:
            inspect.append((oid, kind))
    if inspect:
        payload = git("cat-file", "--batch", data=("\n".join(oid for oid, _ in inspect) + "\n").encode("ascii"))
        offset = 0
        for oid, kind in inspect:
            end = payload.index(b"\n", offset)
            size = int(payload[offset:end].split()[-1])
            content = payload[end + 1:end + 1 + size]
            if kind == "blob" and content.startswith(LFS_HEADER):
                errors.append(f"Git LFS pointer: {objects[oid]}")
            elif kind == "tree":
                # Scan every introduced tree, including intermediate commits.
                # Tree entries contain an octal mode, name, NUL, and raw OID;
                # hash width follows the object ID (SHA-1 or SHA-256).
                entry_offset = 0
                oid_bytes = len(oid) // 2
                while entry_offset < len(content):
                    name_end = content.index(b"\0", entry_offset)
                    mode, raw_name = content[entry_offset:name_end].split(b" ", 1)
                    if mode in {b"120000", b"160000"}:
                        parent = objects[oid]
                        name = decode(raw_name)
                        path = name if parent == oid else f"{parent.rstrip('/')}/{name}"
                        errors.append(f"Pointer entry in outgoing history ({decode(mode)}): {path}")
                    entry_offset = name_end + 1 + oid_bytes
            offset = end + 1 + size + 1
    return count, errors


def check_tree(ref: str | None) -> tuple[int, list[str]]:
    command = ("ls-files", "--stage", "-z") if ref is None else ("ls-tree", "-r", "-z", ref)
    objects: dict[str, str] = {}
    errors = []
    requirements = []
    for row in git(*command).split(b"\0"):
        if not row:
            continue
        metadata, raw_path = row.split(b"\t", 1)
        fields = metadata.decode("ascii").split()
        mode, oid = (fields[0], fields[1]) if ref is None else (fields[0], fields[2])
        path = decode(raw_path)
        basename = Path(path).name.lower()
        if basename.startswith("requirements") and basename.endswith(".txt"):
            requirements.append(path)
        if ref is None and fields[2] != "0":
            errors.append(f"Unresolved merge entry: {path}")
        if mode in {"120000", "160000"}:
            errors.append(f"Pointer entry ({mode}): {path}")
        else:
            objects[oid] = path
    if requirements != ["requirements.txt"]:
        errors.append(f"Expected only root requirements.txt; found: {requirements}")
    count, problems = check_objects(objects)
    return count, errors + problems


def check_push(lines: list[str]) -> tuple[int, list[str]]:
    count = 0
    errors = []
    for line in lines:
        fields = line.split()
        if len(fields) != 4:
            raise ValueError("Expected: local-ref local-oid remote-ref remote-oid")
        local_ref, local_oid, _, remote_oid = fields
        if set(local_oid) == {"0"}:
            continue
        checked, problems = check_tree(local_oid)
        count += checked
        errors.extend(f"{local_ref}: {problem}" for problem in problems)
        revision_args = [local_oid]
        if set(remote_oid) != {"0"}:
            git("cat-file", "-e", remote_oid)  # Never silently omit unavailable history.
            revision_args.append("^" + remote_oid)
        objects = {}
        for row in git("rev-list", "--objects", *revision_args).splitlines():
            oid, _, path = row.partition(b" ")
            objects[oid.decode("ascii")] = decode(path) if path else oid.decode("ascii")
        checked, problems = check_objects(objects)
        count += checked
        errors.extend(f"{local_ref}: {problem}" for problem in problems)
    return count, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--worktree", action="store_true", help="Check files that would be staged (default).")
    modes.add_argument("--index", action="store_true", help="Check the staged Git tree.")
    modes.add_argument("--pre-push", action="store_true", help="Check outgoing refs/objects from hook stdin.")
    args = parser.parse_args()
    try:
        if args.pre_push:
            count, errors = check_push([line.strip() for line in sys.stdin if line.strip()])
        elif args.index:
            count, errors = check_tree(None)
        else:
            count, errors = check_worktree()
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Publication check failed: {exc}", file=sys.stderr)
        return 1
    if errors:
        for error in sorted(set(errors)):
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Publication check passed: {count} files/objects checked; no pointers or oversized files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
