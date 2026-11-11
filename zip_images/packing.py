"""
zip_images.packing -- build, reuse, verify and prune the zip images of commits.
===============================================================================

THE STORE (a folder anywhere, for example N:\\_publish_images)::

    README.md, unpack_images.py, setup_from_zips.sh, Dockerfile, .dockerignore   (for the latest manifest)
    latest.json                       {"manifest": "manifests/<commit12>.json", ...}
    manifests/<commit12>.json         one per packed commit (format: see unpack_images.py)
    compartments/<kind>-<hash>.json   one RECORD per compartment content: its files (name, size, sha256,
                                      mode, chunks) and its zips (file, size, sha256, entries)
    zips/<slug>__<key12>_<NNN>.zip    the zips (each < 100,000,000 bytes)
    .tmp/                             unique work folders; failed builds and downloaded wheels are retained

REUSE. Before building a compartment the packer looks for its record. When the record exists, lists the same
files and every zip is present with its recorded size, the compartment is REUSED: nothing is read from git,
nothing is written. This is what makes a small fix cheap: after a one-line change only the compartment that
holds the file gets a new key and new zips.

BUILDING. The files of a compartment are read from ``git cat-file --batch`` in entry-name order, compressed
by a few threads (zlib releases the GIL) and placed IN ORDER into parts of at most ``limit`` bytes (default
95,000,000). A file larger than ``limit - reserve`` is split into raw chunks first. Already-compressed types
(.zip, .png, .whl, ...) are stored. The finished zips are read back (their directory must list exactly what
was written) and moved into ``zips/``; the record is written LAST, so an interrupted build leaves nothing that
looks complete.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import time
import uuid
import zlib
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import VERSION
from .environment import DEFAULT_PYTHON, build_environment
from .gitsource import GitRepo
from .lifecycle import defer_interrupts
from .planning import DEFAULT_CAP, Compartment, build_tree, entry_sort_key, make_slug, plan, read_config, stored_type, excluded_paths, select_entries, key_filtered_folders
from .store_files import write_store_files
from .unpack_images import (DEFAULT_LIMIT, FORMAT, HARD_LIMIT, KIND_WHEELS, LATEST_FORMAT, LATEST_NAME,
                            MANIFESTS_DIR, RECORD_FORMAT, RECORDS_DIR, WHEELS_NAME, ZIPS_DIR, ManifestError,
                            chunk_entry, free_bytes, json_bytes, load_json, load_manifest, manifest_bytes, mb,
                            slim_manifest, validate_manifest, verify_images, write_atomic, _ordinary_directory)
from .wheels import DEFAULT_PLATFORMS, arch_of_platforms, download, local_wheels, wheel_items, wheels_key
from .zipwriter import DEFAULT_LEVEL, PartWriter, prepare, read_back

TMP_DIR = ".tmp"
MIN_LIMIT = 16_384
MAX_PENDING = 4096


def reserve_for(limit: int) -> int:
    """Bytes kept free in a part for headers and the central directory when a chunk fills it alone."""
    return max(4096, min(1_000_000, limit // 20))


def default_workers() -> int:
    return max(1, min(4, os.cpu_count() or 1))


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---------------------------------------------------------------------------------------------------------
# The store
# ---------------------------------------------------------------------------------------------------------
class Store:
    def __init__(self, root):
        self.root = Path(root).absolute()
        self.zips = self.root / ZIPS_DIR
        self.records = self.root / RECORDS_DIR
        self.manifests = self.root / MANIFESTS_DIR
        self.tmp = self.root / TMP_DIR

    def ensure(self) -> None:
        for d in (self.zips, self.records, self.manifests, self.tmp):
            _ordinary_directory(d, create=True)

    def record_path(self, key: str) -> Path:
        return self.records / (key.replace(":", "-") + ".json")

    def load_record(self, key: str, comp: Compartment = None):
        """The record of ``key`` when it is complete (and, with ``comp``, lists exactly its files), else None."""
        path = self.record_path(key)
        if not path.is_file():
            return None
        try:
            rec = json.loads(path.read_bytes().decode("utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(rec, dict) or rec.get("format") != RECORD_FORMAT or rec.get("key") != key:
            return None
        for p in rec.get("parts") or [None]:
            if not isinstance(p, dict):
                return None
            try:
                if (self.zips / p["file"]).stat().st_size != p["size"]:
                    return None
            except (OSError, KeyError, TypeError):
                return None
        if comp is not None:
            want = sorted((comp.entry_name(i), i.size, i.mode) for i in comp.files)
            have = sorted((f.get("name"), f.get("size"), f.get("mode")) for f in rec.get("files") or [])
            if want != have:
                return None
        return rec

    def save_record(self, rec: dict) -> None:
        write_atomic(self.record_path(rec["key"]), json_bytes(rec))

    def manifest_files(self) -> list:
        return sorted(self.manifests.glob("*.json")) if self.manifests.is_dir() else []

    def latest_manifest(self):
        try:
            data = load_json(self.root / LATEST_NAME)
            return self.root / data["manifest"]
        except (ManifestError, KeyError, TypeError):
            return None


# ---------------------------------------------------------------------------------------------------------
# Sources of file bytes
# ---------------------------------------------------------------------------------------------------------
class GitSource:
    """Blobs of a commit, through one ``git cat-file --batch``."""

    def __init__(self, repo: GitRepo):
        self.repo = repo
        self.reader = None

    def __enter__(self):
        self.reader = self.repo.blobs()
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            self.reader.close()
        except BaseException as failure:
            if exc is None:
                raise
            exc.add_note("Git reader cleanup failed: " + type(failure).__name__ + ": " + str(failure))

    def stream(self, items: list):
        self.reader.request([it.oid for it in items])
        for it in items:
            s = self.reader.next(it.oid)
            if s.size != it.size:
                raise RuntimeError("{}: git says {:,} bytes, the listing said {:,}".format(it.path, s.size, it.size))
            yield it, s
            s.drain()


class DiskSource:
    """Files on disk (the wheels)."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def stream(self, items: list):
        for it in items:
            with open(it.local, "rb") as fh:
                yield it, fh


def _read_exact(stream, n: int) -> bytes:
    if n == 0:
        return b""
    data = stream.read(n)
    if len(data) == n:
        return data
    chunks, left = [data], n - len(data)
    while left:
        more = stream.read(left)
        if not more:
            raise RuntimeError("a file got shorter while it was packed")
        chunks.append(more)
        left -= len(more)
    return b"".join(chunks)


def _prepare_hashed(name, mode, raw, level, store):
    return prepare(name, mode, raw, level, store), hashlib.sha256(raw).hexdigest()


def _prepare_plain(name, mode, raw, level, store):
    return prepare(name, mode, raw, level, store), None


# ---------------------------------------------------------------------------------------------------------
# Building one compartment
# ---------------------------------------------------------------------------------------------------------
def _scratch_folder(store, purpose):
    _ordinary_directory(store.tmp, create=True)
    work = store.tmp / (purpose + "." + str(os.getpid()) + "." + uuid.uuid4().hex)
    work.mkdir()
    _ordinary_directory(work)
    return work


def _retained(work, log, primary=None):
    message = "  retained scratch: " + str(work)
    if primary is not None:
        primary.add_note(message)
    try:
        log(message)
    except BaseException as failure:
        if primary is None:
            raise
        primary.add_note("Scratch reporting failed: " + type(failure).__name__)


def _finish_scratch(work, log):
    # Remove only an empty directory; never recursively remove partial work.
    primary = sys.exception()
    try:
        work.rmdir()
    except OSError:
        _retained(work, log, primary)


def build_compartment(store: Store, comp: Compartment, source, *, limit: int = DEFAULT_LIMIT,
                      level: int = DEFAULT_LEVEL, workers: int = None, log=print) -> dict:
    """Zip one compartment into ``store`` and write its record. -> the record."""
    if not MIN_LIMIT <= limit < HARD_LIMIT:
        raise ValueError("the zip limit must be between {:,} and {:,} bytes".format(MIN_LIMIT, HARD_LIMIT - 1))
    chunk_raw = limit - reserve_for(limit)
    slug, key12 = make_slug(comp.name), comp.key_hex[:12]
    work = _scratch_folder(store, "build")
    try:
        log("  build scratch: " + str(work))
        parts, files_out = [], []
        state = {"writer": None, "inflight": 0}
        window = max(2 * limit, 256 * 1024 * 1024)
        pending = deque()

        def close_writer():
            w = state["writer"]
            size, sha, n = w.close()
            read_back(w.path, w.entries)
            parts.append({"file": w.path.name, "size": size, "sha256": sha, "entries": n})
            state["writer"] = None

        def place(entry):
            w = state["writer"]
            if w is not None and not w.fits(entry):
                close_writer()
            if state["writer"] is None:
                state["writer"] = PartWriter(work / "{}__{}_{:03d}.zip".format(slug, key12, len(parts) + 1), limit)
                if not state["writer"].fits(entry):
                    raise RuntimeError("{} does not fit into an empty zip of {:,} bytes".format(entry.name, limit))
            state["writer"].add(entry)

        def drain(keep_bytes: int):
            while pending and (state["inflight"] > keep_bytes or len(pending) > MAX_PENDING):
                fut, rec, nbytes = pending.popleft()
                entry, sha = fut.result()
                if rec is not None:
                    rec["sha256"] = sha
                place(entry)
                state["inflight"] -= nbytes

        pool = ThreadPoolExecutor(max_workers=workers or default_workers())
        try:
            for item, stream in source.stream(comp.files):
                name = comp.entry_name(item)
                keep = stored_type(name)
                rec = {"name": name, "size": item.size, "mode": item.mode}
                files_out.append(rec)
                if item.size > chunk_raw:
                    n = -(-item.size // chunk_raw)
                    h, left = hashlib.sha256(), item.size
                    for i in range(1, n + 1):
                        raw = _read_exact(stream, min(chunk_raw, left))
                        left -= len(raw)
                        h.update(raw)
                        pending.append((pool.submit(_prepare_plain, chunk_entry(name, i, n), item.mode, raw, level, keep),
                                        None, len(raw)))
                        state["inflight"] += len(raw)
                        drain(window)
                    rec["sha256"] = h.hexdigest()
                    rec["chunks"] = n
                else:
                    raw = _read_exact(stream, item.size)
                    pending.append((pool.submit(_prepare_hashed, name, item.mode, raw, level, keep), rec, len(raw)))
                    state["inflight"] += len(raw)
                    drain(window)
            drain(-1)
            if state["writer"] is not None:
                close_writer()
            with defer_interrupts():
                pool.shutdown(wait=True)
        except BaseException as primary:
            with defer_interrupts():
                writer = state["writer"]
                if writer is not None:
                    for attempt in range(2):
                        try:
                            writer.abort(keep=True)
                        except BaseException as failure:
                            primary.add_note("close partial ZIP failed: " + type(failure).__name__)
                        if writer.fh.closed:
                            break
                    if not writer.fh.closed:
                        primary.add_note("UNCONFIRMED: partial ZIP handle remains open")
                actions = [("cancel compression", fut.cancel) for fut, _, _ in pending]
                for label, action in actions:
                    try:
                        action()
                    except BaseException as failure:
                        primary.add_note(label + " failed: " + type(failure).__name__)
                for attempt in range(2):
                    try:
                        pool.shutdown(wait=True)
                        break
                    except BaseException as failure:
                        primary.add_note("Join compression workers failed: " + type(failure).__name__)
                else:
                    primary.add_note("UNCONFIRMED: compression workers did not complete shutdown")
            raise
        store.zips.mkdir(parents=True, exist_ok=True)
        for p in parts:
            src, dst = work / p["file"], store.zips / p["file"]
            if dst.exists() and dst.stat().st_size == p["size"] and _sha(dst) == p["sha256"]:
                src.unlink()
            else:
                os.replace(str(src), str(dst))
        record = {"format": RECORD_FORMAT, "key": comp.key, "kind": comp.kind, "slug": slug,
                  "files": files_out, "parts": parts, "raw_bytes": comp.raw_bytes,
                  "zip_bytes": sum(p["size"] for p in parts), "packed_at": _now(),
                  "params": {"limit": limit, "level": level, "chunk_raw": chunk_raw, "zlib": zlib.ZLIB_RUNTIME_VERSION}}
        store.save_record(record)
        _finish_scratch(work, log)
        return record
    except BaseException as primary:
        _retained(work, log, primary)
        raise


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# ---------------------------------------------------------------------------------------------------------
# Planning a commit
# ---------------------------------------------------------------------------------------------------------
def _validate_store_location(repo_top, store_path, excludes):
    """Reject recursive in-repo publication and linked ancestors before any store writes."""
    top = Path(repo_top).absolute()
    store = Path(store_path).absolute()
    existing = store
    while not os.path.lexists(existing):
        if existing == existing.parent:
            break
        existing = existing.parent
    _ordinary_directory(existing)
    top_real, store_real = os.path.normcase(os.path.realpath(top)), os.path.normcase(os.path.realpath(store))
    try:
        within = os.path.commonpath((top_real, store_real)) == top_real
    except ValueError:
        within = False
    if within:
        relative = os.path.relpath(os.path.realpath(store), os.path.realpath(top)).replace(os.sep, "/")
        if not any(relative == p or relative.startswith(p + "/") for p in excludes):
            raise ValueError("An in-repository image store must be listed under exclude in committed zip_images.json")


def plan_commit(repo_path, rev: str, store_path=None, cap: int = None) -> dict:
    """The compartments of a commit and, with a store, which of them it already holds."""
    repo = GitRepo(repo_path)
    commit = repo.resolve(rev)
    info = repo.commit_info(commit)
    entries = repo.list_tree(commit)
    config = read_config(repo, entries)
    excludes = excluded_paths(config)
    entries = select_entries(entries, excludes)
    if store_path is not None:
        _validate_store_location(repo.top, store_path, excludes)
    cap = int(cap or config.get("cap") or DEFAULT_CAP)
    root, skipped = build_tree(entries, info["tree"])
    key_filtered_folders(root, excludes)
    comps = plan(root, cap, config.get("split"), config.get("whole"))
    store = Store(store_path) if store_path else None
    rows, first = [], {}                 # an identical folder twice in one commit is built once ("same")
    for c in comps:
        rec = store.load_record(c.key, c) if store else None
        same = first.setdefault(c.key, c.name)
        same = None if same == c.name else same
        rows.append({"comp": c, "record": rec, "reused": rec is not None or same is not None, "same_as": same,
                     "zip_bytes": rec["zip_bytes"] if rec else c.est_bytes})
    return {"repo": repo, "commit": commit, "info": info, "entries": entries, "config": config, "cap": cap,
            "skipped": skipped, "rows": rows}


def print_plan(p: dict, log=print, detail: bool = True) -> dict:
    rows = p["rows"]
    if detail:
        log("{:<7} {:>6} {:>10} {:>10}  {}".format("status", "files", "raw MB", "zip MB", "compartment"))
        for r in rows:
            c = r["comp"]
            est = ("" if r["record"] else "~") + mb(r["zip_bytes"])
            status = "same" if r["same_as"] and not r["record"] else "reuse" if r["reused"] else "new"
            log("{:<7} {:>6} {:>10} {:>10}  {}{}".format(status, len(c.files),
                                                         mb(c.raw_bytes), est, c.name,
                                                         "" if c.kind != "files" else "  [loose files]"))
    new = [r for r in rows if not r["reused"]]
    same = sum(1 for r in rows if r["same_as"] and not r["record"])
    tot = {"compartments": len(rows), "files": sum(len(r["comp"].files) for r in rows),
           "raw_bytes": sum(r["comp"].raw_bytes for r in rows), "zip_bytes": sum(r["zip_bytes"] for r in rows),
           "new": len(new), "new_raw": sum(r["comp"].raw_bytes for r in new),
           "new_zip_estimate": sum(r["zip_bytes"] for r in new), "reused": len(rows) - len(new) - same,
           "same": same}
    log("Plan for commit {} ({}): {} compartments, {:,} files, {} MB raw, about {} MB of zips "
        "(cap {} MB per folder)".format(p["commit"][:12], p["info"]["date"], tot["compartments"], tot["files"],
                                        mb(tot["raw_bytes"]), mb(tot["zip_bytes"]), mb(p["cap"])))
    log("  {} compartments would be built ({} MB raw, about {} MB of new zips), {} reused from the store{}".format(
        tot["new"], mb(tot["new_raw"]), mb(tot["new_zip_estimate"]), tot["reused"],
        ", {} identical to another folder of this commit (built once)".format(same) if same else ""))
    if excluded_paths(p["config"]):
        log("  excluded artifact prefixes: " + ", ".join(excluded_paths(p["config"])))
    if p["skipped"]:
        log("  not packed (submodules): " + ", ".join(e.path for e in p["skipped"]))
    return tot


# ---------------------------------------------------------------------------------------------------------
# PACK
# ---------------------------------------------------------------------------------------------------------
def pack(repo_path, rev: str, store_path, *, limit: int = DEFAULT_LIMIT, cap: int = None,
         level: int = DEFAULT_LEVEL, workers: int = None, python_version: str = DEFAULT_PYTHON,
         extra_requirements=(), wheels: bool = False, platforms=None, pip_args=(), wheels_from=None,
         set_latest: bool = True, check_space: bool = True, log=print) -> dict:
    """Pack one commit into the store; reuse every compartment the store already holds. -> a summary."""
    if not MIN_LIMIT <= limit < HARD_LIMIT:
        raise ValueError("--limit must be between {:,} and {:,} bytes".format(MIN_LIMIT, HARD_LIMIT - 1))
    t0 = time.monotonic()
    p = plan_commit(repo_path, rev, store_path, cap)
    repo, commit, info = p["repo"], p["commit"], p["info"]
    store = Store(store_path)
    tot = print_plan(p, log, detail=False)
    if check_space:
        need = int(tot["new_zip_estimate"] * 1.15) + 200_000_000
        free = free_bytes(store.root)
        if free < need:
            raise OSError("not enough free space at {}: about {} MB needed, {} MB free (use --no-space-check to "
                          "try anyway)".format(store.root, mb(need), mb(free)))
    store.ensure()
    built, reused, written = [], [], 0
    records, by_key = {}, {}          # an identical folder twice in one commit is built once
    oid_by_path = {e.path: e.oid for e in p["entries"] if e.kind == "blob"}
    with GitSource(repo) as src:
        for k, row in enumerate(p["rows"], 1):
            c = row["comp"]
            if row["reused"] or c.key in by_key:
                records[c.name] = row["record"] or by_key[c.key]
                reused.append(c.name)
                continue
            t1 = time.monotonic()
            rec = build_compartment(store, c, src, limit=limit, level=level, workers=workers, log=log)
            records[c.name] = by_key[c.key] = rec
            built.append(c.name)
            written += rec["zip_bytes"]
            log("  built {} [{}/{}]: {} files, {} MB -> {} MB in {} zips ({:.0f} s)".format(
                c.name, k, len(p["rows"]), len(rec["files"]), mb(rec["raw_bytes"]), mb(rec["zip_bytes"]),
                len(rec["parts"]), time.monotonic() - t1))
    shas = {}
    for row in p["rows"]:
        c = row["comp"]
        for f in records[c.name]["files"]:
            shas[(c.path + "/" if c.path else "") + f["name"]] = f["sha256"]
    extra = list(extra_requirements or [])
    env = build_environment(lambda path: repo.blob_bytes(oid_by_path[path]), shas, python_version=python_version,
                            extra_requirements=extra, config=p["config"], revision=commit)
    for note in env.get("notes") or []:
        log("  note: " + note)
    wheel_comp = None
    if wheels or wheels_from:
        wheel_comp, wrec, wbuilt = _pack_wheels(store, repo, oid_by_path, env, platforms or list(DEFAULT_PLATFORMS),
                                                python_version, list(pip_args or []), wheels_from, limit, level,
                                                workers, log)
        if wbuilt:
            built.append(WHEELS_NAME)
            written += wrec["zip_bytes"]
        else:
            reused.append(WHEELS_NAME)
    manifest = _assemble(p, records, env, wheel_comp, limit, level)
    validate_manifest(manifest)
    mpath = store.manifests / (commit[:12] + ".json")
    write_atomic(mpath, manifest_bytes(slim_manifest(manifest)))  # format 2: the rows stay in the records
    if set_latest:
        write_atomic(store.root / LATEST_NAME, json_bytes({
            "format": LATEST_FORMAT, "manifest": MANIFESTS_DIR + "/" + mpath.name, "commit": commit,
            "commit_date": info["date"], "packed_at": manifest["packed_at"]}))
        write_store_files(store.root, manifest)
    elif not (store.root / "unpack_images.py").exists():
        write_store_files(store.root, manifest, only_unpacker=True)
    try:
        store.tmp.rmdir()
    except OSError:
        pass
    result = {"commit": commit, "manifest": str(mpath), "built": built, "reused": reused, "bytes_written": written,
              "totals": manifest["totals"], "seconds": round(time.monotonic() - t0, 1), "latest": set_latest}
    log("Packed commit {}: {} compartments built ({} MB of new zips), {} reused; {} zips, {} MB in all; "
        "manifest {} ({:.0f} s){}".format(commit[:12], len(built), mb(written), len(reused),
                                          manifest["totals"]["zips"], mb(manifest["totals"]["zip_bytes"]), mpath.name,
                                          result["seconds"], "" if set_latest else " -- latest.json NOT changed"))
    return result


def _pack_wheels(store, repo, oid_by_path, env, platforms, python_version, pip_args, wheels_from, limit, level,
                 workers, log):
    pip_self = env.get("pip_self") or None
    req_paths = env["requirements"] + env.get("constraints", [])
    req_paths += [p for p in (pip_self or {}).get("constraints") or [] if p not in req_paths]
    blobs = [(pth, repo.blob_bytes(oid_by_path[pth])) for pth in req_paths]
    local = local_wheels(Path(wheels_from)) if wheels_from else None
    # The source's lock for the wheels' platform and its package-index options (the versions a Docker build of
    # the source installs); a lock made for another Python is not used.
    arch = arch_of_platforms(platforms)
    lock = (env.get("constraints_by_arch") or {}).get(arch) if arch else None
    if lock and env.get("constraints_python") and env["constraints_python"] != python_version:
        log("  note: {} pins versions for Python {}, the wheels are for {} -- not used".format(
            lock, env["constraints_python"], python_version))
        lock = None
    elif env.get("constraints_by_arch") and not lock:
        log("  note: no constraints file for the wheel platforms {} -- pip chooses the versions".format(
            " ".join(platforms)))
    cons_blobs = [(lock, repo.blob_bytes(oid_by_path[lock]))] if lock else []
    options = [str(x) for x in env.get("pip_options") or []]
    key = wheels_key(blobs, env["extra_requirements"], platforms, python_version, pip_args, local, cons_blobs,
                     options, (pip_self or {}).get("spec"))
    comp = Compartment(WHEELS_NAME, KIND_WHEELS, None, key, [])
    folder = Path(wheels_from) if wheels_from else None
    rec = store.load_record(key)
    built = False
    if rec is None:
        work = _scratch_folder(store, "wheels")
        try:
            if folder is None:
                reqdir = work / "req"
                reqdir.mkdir(parents=True, exist_ok=True)
                written = {}
                for pth, data in blobs + cons_blobs:
                    f = reqdir / pth.replace("/", "__")
                    f.write_bytes(data)
                    written[pth] = f
                files = [written[p] for p in env["requirements"]]
                cons = [written[p] for p in env.get("constraints", [])] + ([written[lock]] if lock else [])
                self_spec = (pip_self["spec"], [written[p] for p in pip_self.get("constraints") or []]) \
                    if pip_self else None
                folder = work / "wheels"
                download(files, env["extra_requirements"], folder, platforms, python_version, pip_args, log=log,
                         constraints=cons, pip_options=options, lock=written[lock] if lock else None,
                         pip_self=self_spec)
            comp.files = sorted(wheel_items(folder), key=lambda i: entry_sort_key(i.path))
            if not comp.files:
                raise RuntimeError("no wheels in {} -- nothing to pack for the offline install".format(folder))
            comp.raw_bytes = sum(i.size for i in comp.files)
            with DiskSource() as src:
                rec = build_compartment(store, comp, src, limit=limit, level=level, workers=workers, log=log)
            built = True
            log("  built {}: {} wheels, {} MB -> {} MB".format(WHEELS_NAME, len(rec["files"]), mb(rec["raw_bytes"]),
                                                              mb(rec["zip_bytes"])))
        finally:
            _finish_scratch(work, log)
    env["wheels"] = {"key": key, "platforms": platforms, "python_version": python_version, "pip_args": pip_args,
                     "source": "folder" if wheels_from else "pip download"}
    if lock:
        env["wheels"]["constraints"] = lock
    if options:
        env["wheels"]["pip_options"] = options
    entry = {"name": WHEELS_NAME, "kind": KIND_WHEELS, "path": None, "key": key, "file_count": len(rec["files"]),
             "raw_bytes": rec["raw_bytes"], "zip_bytes": rec["zip_bytes"],
             "parts": [{"file": q["file"], "size": q["size"], "sha256": q["sha256"]} for q in rec["parts"]],
             "files": [dict(f) for f in rec["files"]]}
    return entry, rec, built


def _assemble(p: dict, records: dict, env: dict, wheel_comp, limit: int, level: int) -> dict:
    comps, files = [], []
    for row in p["rows"]:
        c = row["comp"]
        rec = records[c.name]
        comps.append({"name": c.name, "kind": c.kind, "path": c.path, "key": c.key, "file_count": len(rec["files"]),
                      "raw_bytes": rec["raw_bytes"], "zip_bytes": rec["zip_bytes"],
                      "parts": [{"file": q["file"], "size": q["size"], "sha256": q["sha256"]} for q in rec["parts"]]})
        for f in rec["files"]:
            fd = {"path": (c.path + "/" if c.path else "") + f["name"], "size": f["size"], "sha256": f["sha256"],
                  "mode": f["mode"], "compartment": c.name}
            if f.get("chunks"):
                fd["chunks"] = f["chunks"]
            files.append(fd)
    files.sort(key=lambda f: entry_sort_key(f["path"]))
    if wheel_comp is not None:
        comps.append(wheel_comp)
    zips = {q["file"]: q["size"] for c in comps for q in c["parts"]}
    info = p["info"]
    return {"format": FORMAT, "commit": p["commit"], "tree": info["tree"], "commit_date": info["date"],
            "subject": info["subject"], "packed_at": _now(),
            "packer": {"tool": "zip_images", "version": VERSION, "python": platform.python_version(),
                       "zlib": zlib.ZLIB_RUNTIME_VERSION},
            "params": {"limit": limit, "cap": p["cap"], "level": level, "exclude": excluded_paths(p["config"])},
            "totals": {"compartments": len(comps), "files": len(files), "raw_bytes": sum(f["size"] for f in files),
                       "zips": len(zips), "zip_bytes": sum(zips.values())},
            "skipped": [e.path for e in p["skipped"]], "compartments": comps, "files": files, "environment": env}


# ---------------------------------------------------------------------------------------------------------
# VERIFY and PRUNE
# ---------------------------------------------------------------------------------------------------------
def verify_store(store_path, which: str = "latest", log=print) -> int:
    """Stream-check the zips and files of one manifest ('latest', a commit prefix) or of 'all'. -> exit code."""
    store = Store(store_path)
    paths = store.manifest_files() if which == "all" else [None]
    done, rc = set(), 0
    for mp in paths:
        path, m = load_manifest(store.root, str(mp) if mp else which)
        comps = [c for c in m["compartments"] if c["key"] not in done]
        log("Verifying {} (commit {}): {} compartments{}".format(
            path.name, m["commit"][:12], len(comps),
            "" if len(comps) == len(m["compartments"]) else " not checked yet"))
        rc = rc or verify_images(store.root, m, comps, log=log)
        done.update(c["key"] for c in comps)
    return rc


def prune(store_path, keep: int = 1, yes: bool = False, log=print) -> dict:
    """Keep the zips of the ``keep`` most recently packed manifests (and of latest.json's); list or delete the rest."""
    store = Store(store_path)
    found = []
    for mp in store.manifest_files():
        try:
            m = load_json(mp)
            found.append((m.get("packed_at", ""), mp, m))
        except ManifestError:
            found.append(("", mp, None))
    latest = store.latest_manifest()
    found.sort(key=lambda x: (x[0], bool(latest) and x[1].name == latest.name), reverse=True)
    kept = [x for i, x in enumerate(found) if (i < keep and x[2]) or (latest and x[1].name == latest.name)]
    kept_names = {x[1].name for x in kept}
    keys, zips = set(), set()
    for _, _, m in kept:
        for c in m["compartments"]:
            keys.add(c["key"])
            zips.update(q["file"] for q in c["parts"])
    drop_manifests = [x[1] for x in found if x[1].name not in kept_names]
    drop_records = [r for r in sorted(store.records.glob("*.json")) if r.stem.replace("-", ":", 1) not in keys] \
        if store.records.is_dir() else []
    drop_zips = [z for z in sorted(store.zips.glob("*.zip")) if z.name not in zips] if store.zips.is_dir() else []
    freed = sum(z.stat().st_size for z in drop_zips)
    log("Prune {}: keeping {} manifests ({}), {} zips; {} {} manifests, {} records, {} zips ({} MB)".format(
        store.root, len(kept), ", ".join(sorted(kept_names)) or "none", len(zips),
        "deleting" if yes else "would delete", len(drop_manifests), len(drop_records), len(drop_zips), mb(freed)))
    for f in drop_manifests + drop_records + drop_zips:
        log(("  deleted " if yes else "  would delete ") + str(f.relative_to(store.root)))
        if yes:
            f.unlink()
    if yes and store.tmp.is_dir():
        log("  scratch retained separately: " + str(store.tmp))
    if not yes and (drop_manifests or drop_zips or drop_records):
        log("(nothing deleted: run again with --yes)")
    return {"kept": sorted(kept_names), "manifests": [f.name for f in drop_manifests],
            "records": [f.name for f in drop_records], "zips": [f.name for f in drop_zips], "bytes": freed,
            "deleted": yes}
