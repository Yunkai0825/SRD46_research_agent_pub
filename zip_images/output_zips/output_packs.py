"""Package output directories with the shared zip_images compartment writer."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from ..packing import Compartment, DiskSource, build_compartment
from .output_layout import OutputStore
from ..planning import FileItem
from ..unpack_images import check_part_files, check_rel, json_bytes, verify_compartment, write_atomic


def fs_path(value):
    path = os.path.abspath(os.fspath(value))
    if os.name == "nt" and not path.startswith("\\\\?\\"):
        path = "\\\\?\\UNC\\" + path[2:] if path.startswith("\\\\") else "\\\\?\\" + path
    return Path(path)


def inventory(root, target):
    """Record every regular file and directory, including Windows long paths."""
    base = fs_path(root) / check_rel(target, "output directory")
    if not base.resolve().is_relative_to(fs_path(root).resolve()):
        raise ValueError("Output directory escapes the repository")
    if not base.exists():
        return [], {}, {}
    ancestor = base
    while ancestor != fs_path(root):
        metadata = ancestor.lstat()
        if ancestor.is_symlink() or (getattr(metadata, "st_file_attributes", 0) & 0x400):
            raise ValueError("Output directory contains a link: " + str(ancestor))
        ancestor = ancestor.parent
    items, times, directories = [], {}, {}
    pending = [(base, "")]
    while pending:
        directory, rel = pending.pop()
        directories[rel] = directory.stat().st_mtime_ns
        with os.scandir(directory) as entries:
            for entry in entries:
                name = (rel + "/" if rel else "") + entry.name
                if entry.is_symlink() or (entry.stat(follow_symlinks=False).st_file_attributes & 0x400 if os.name == "nt" else False):
                    raise ValueError("Output archives do not accept symbolic links: " + name)
                if entry.is_dir(follow_symlinks=False):
                    pending.append((Path(entry.path), name))
                elif entry.is_file(follow_symlinks=False):
                    stat = entry.stat(follow_symlinks=False)
                    times[name] = [stat.st_size, stat.st_mtime_ns]
                    items.append(FileItem(target + "/" + name, "100644", "", stat.st_size, entry.path))
                else:
                    raise ValueError("Not a regular output file: " + name)
    items.sort(key=lambda item: item.path.encode("utf-8"))
    return items, times, directories


def pack_run(root, target, *, limit=95_000_000, delete=(), log=print):
    """Create and fully verify a run archive. Keep its original files in place."""
    if not 0 < limit < 100_000_000:
        raise ValueError("Output ZIP parts must be smaller than 100 MB")
    root = fs_path(root)
    target = check_rel(target.replace("\\", "/"), "output directory")
    if target.split("/")[0] not in {"_benchmark", "_output"}:
        raise ValueError("Only _benchmark and _output directories can be packed")
    items, times, directories = inventory(root, target)
    store = OutputStore(root / "_output_archives", target)
    store.ensure()
    catalog = store.root / "runs"
    catalog.mkdir(exist_ok=True)
    name = hashlib.sha256(target.encode()).hexdigest() + ".json"
    descriptor_path = catalog / name
    if descriptor_path.is_file():
        from .output_update import update_run
        descriptor = json.loads(descriptor_path.read_text("utf-8"))
        return update_run(store, descriptor_path, descriptor, items, times, directories,
                          delete=[check_rel(value, "deleted file") for value in delete], log=log)
    if not items or delete:
        raise ValueError("A new output archive requires files and cannot contain deletion requests")
    # Hash file bytes so the existing content-addressed writer can be reused safely.
    digest = hashlib.sha256()
    for item in items:
        digest.update(item.path.encode("utf-8") + b"\0")
        with open(item.local, "rb") as stream:
            while block := stream.read(4 << 20):
                digest.update(block)
        digest.update(b"\0" + str(item.size).encode() + b"\0")
    key = "tree:" + digest.hexdigest()
    comp = Compartment(target, "tree", target, key, items, sum(item.size for item in items))
    record = store.load_record(key, comp)
    if record is None:
        with DiskSource() as source:
            record = build_compartment(store, comp, source, limit=limit, log=log)
    checks = dict(record, name=target)
    errors = check_part_files(store.part_root, [checks], full=True)
    if not errors:
        errors = verify_compartment(store.part_root, checks, record["files"])
    if errors:
        raise RuntimeError("Archive verification failed: " + "; ".join(errors))
    _, after, after_dirs = inventory(root, target)
    if times != after or directories.keys() != after_dirs.keys():
        changed_files = [name for name in times.keys() | after.keys() if times.get(name) != after.get(name)]
        changed_dirs = [name for name in directories.keys() | after_dirs.keys() if directories.get(name) != after_dirs.get(name)]
        raise RuntimeError("Output metadata changed during packing: " + target + "; files="
                           + repr(changed_files[:10]) + "; directories=" + repr(changed_dirs[:10]))
    descriptor = {
        "format": "srd46-output-archive-v1", "target": target,
        "record": "compartments/" + key.replace(":", "-") + ".json",
        "mtimes_ns": {name: info[1] for name, info in times.items()},
        "directories": after_dirs,
    }
    from .output_timing import solver_index
    descriptor["solver_events"] = solver_index(target, record["files"], items)
    write_atomic(catalog / name, json_bytes(descriptor))
    return {"target": target, "files": len(items), "raw_bytes": comp.raw_bytes,
            "zip_bytes": record["zip_bytes"], "parts": len(record["parts"]), "verified": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", nargs="*", help="Repository-relative run directories")
    parser.add_argument("--root", type=Path, default=Path(__file__).absolute().parents[2])
    parser.add_argument("--all-benchmark", action="store_true", help="Pack each model/run directory")
    parser.add_argument("--limit", type=int, default=95_000_000)
    parser.add_argument("--delete", action="append", default=[], help="Explicitly remove a run-relative archived file (one target only)")
    args = parser.parse_args(argv)
    targets = list(args.targets)
    if args.delete and (len(targets) != 1 or args.all_benchmark):
        parser.error("--delete requires exactly one explicit run target")
    if args.all_benchmark:
        root = fs_path(args.root)
        catalog = root / "_output_archives/runs"
        archived = {json.loads(path.read_text("utf-8"))["target"] for path in catalog.glob("*.json")}
        base = root / "_benchmark"
        for model in sorted(base.iterdir()) if base.is_dir() else []:
            if model.is_dir() and not model.name.startswith("_"):
                for run in sorted(model.iterdir()):
                    if run.is_dir() and not run.name.startswith("_"):
                        target = run.relative_to(root).as_posix()
                        if target in archived or inventory(root, target)[0]:
                            targets.append(target)
        targets.extend(sorted(target for target in archived if target.startswith("_benchmark/")))
    for target in dict.fromkeys(targets):
        print(json.dumps(pack_run(args.root, target, limit=args.limit, delete=args.delete)), flush=True)


if __name__ == "__main__":
    main()
