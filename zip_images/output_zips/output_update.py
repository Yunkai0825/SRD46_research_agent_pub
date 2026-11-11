"""Rewrite affected output ZIP parts in place, preserving all other parts."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import zipfile

from .output_lock import archive_lock
from ..planning import stored_type
from ..unpack_images import check_part_files, chunk_entry, json_bytes, verify_compartment, write_atomic
from ..zipwriter import Entry, LOCAL, SIG_LOCAL, PartWriter, prepare, read_back


def _sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(4 << 20):
            digest.update(block)
    return digest.hexdigest()


def _copied_entry(path, info, mode):
    with path.open("rb") as source:
        source.seek(info.header_offset)
        header = LOCAL.unpack(source.read(LOCAL.size))
        if header[0] != SIG_LOCAL or header[3] != info.compress_type or header[6] != info.CRC:
            raise OSError("ZIP member header mismatch: " + info.filename)
        name = source.read(header[-2])
        if name.decode("utf-8" if info.flag_bits & 0x800 else "cp437") != info.filename:
            raise OSError("ZIP member name mismatch")
        source.seek(header[-1], 1)
        data = source.read(info.compress_size)
        if len(data) != info.compress_size:
            raise OSError("Truncated ZIP payload")
    return Entry(info.filename, mode, data, info.compress_type, info.CRC, info.file_size)


class _StagedParts:
    def __init__(self, store, staged):
        self.store, self.staged = store, staged

    def __truediv__(self, name):
        if name == "zips":
            return self
        candidate = self.staged / name
        return candidate if candidate.is_file() else self.store.zips / name


def recover_update(store):
    """Roll back an interrupted replacement before an updater proceeds."""
    pending = store.root / "update_pending.json"
    if not pending.exists():
        return
    doc = json.loads(pending.read_text("utf-8"))
    work = store.root / doc["work"]
    if not work.resolve().is_relative_to(store.tmp.resolve()):
        raise ValueError("Invalid archive update recovery directory")
    if any(Path(name).name != name for name in doc["replacements"] + doc["new_parts"]):
        raise ValueError("Invalid archive recovery part name")
    for name in ("record", "catalog"):
        if not (store.root / doc[name]).resolve().is_relative_to(store.root.resolve()):
            raise ValueError("Invalid archive recovery metadata path")
    zip_directory = store.root / doc["zip_directory"]
    if not zip_directory.resolve().is_relative_to((store.root / "zips").resolve()):
        raise ValueError("Invalid archive recovery ZIP directory")
    if not doc.get("committed"):
        for name in doc["replacements"]:
            backup = work / "backup" / name
            dest = zip_directory / name
            if backup.exists():
                os.replace(backup, dest)
            elif name in doc["new_parts"] and dest.exists():
                dest.unlink()
        for name in ("record", "catalog"):
            dest = store.root / doc[name]
            write_atomic(dest, (work / (name + ".before")).read_bytes())
    pending.unlink()
    shutil.rmtree(work)


def update_run(store, catalog, descriptor, items, times, directories, *, delete=(), log=print):
    """Overlay loose files; rewrite only changed parts. Missing loose files survive."""
    from .output_packs import inventory
    with archive_lock(store.root, exclusive=True):
        recover_update(store)
        descriptor = json.loads(catalog.read_text("utf-8"))
        record_path = store.root / descriptor["record"]
        previous = json.loads(record_path.read_text("utf-8"))
        old = {fd["name"]: fd for fd in previous["files"]}
        changed, hashes = {}, {}
        target = descriptor["target"]
        for item in items:
            name = item.path[len(target) + 1:]
            hashes[name] = _sha(Path(item.local))
            if name not in old or old[name]["sha256"] != hashes[name] or old[name]["mode"] != item.mode:
                changed[name] = item
        removed, deleted_dirs = set(), set()
        for requested in delete:
            prefix = requested.rstrip("/") + "/"
            matches = {name for name in old if name == requested or name.startswith(prefix)}
            matching_dirs = {name for name in descriptor["directories"]
                             if name == requested or name.startswith(prefix)}
            if not matches and not matching_dirs:
                raise ValueError("Cannot delete an unknown archived path: " + requested)
            removed.update(matches)
            deleted_dirs.update(matching_dirs)
        if removed & changed.keys():
            raise ValueError("Remove the loose file before explicitly deleting it from the archive")
        added_dirs = directories.keys() - descriptor["directories"].keys()
        if not changed and not removed and not deleted_dirs and not added_dirs:
            return dict(target=target, files=len(old), raw_bytes=previous["raw_bytes"],
                        zip_bytes=previous["zip_bytes"], parts=len(previous["parts"]),
                        updated_files=0, rewritten_parts=[], verified=True)

        owners, touched, infos = {}, set(), []
        for name, fd in old.items():
            chunks = fd.get("chunks", 0)
            for member in ([chunk_entry(name, i, chunks) for i in range(1, chunks + 1)] if chunks else [name]):
                owners[member] = name
        for index, part in enumerate(previous["parts"]):
            with zipfile.ZipFile(store.zips / part["file"]) as archive:
                members = archive.infolist()
            infos.append(members)
            if any(owners[info.filename] in changed or owners[info.filename] in removed for info in members):
                touched.add(index)
        new_names = set(changed) - old.keys()
        if new_names:
            touched.add(len(previous["parts"]) - 1)
        spans = []
        for index in sorted(touched):
            if spans and index == spans[-1][1] + 1:
                spans[-1][1] = index
            else:
                spans.append([index, index])
        checked = dict(previous, name=target, parts=[previous["parts"][i] for i in sorted(touched) if i >= 0])
        errors = check_part_files(store.part_root, [checked], full=True)
        if errors:
            raise OSError("; ".join(errors))
        work = Path(tempfile.mkdtemp(prefix="update.", dir=store.tmp))
        staged = work / "zips"
        staged.mkdir()
        limit, chunk_raw = previous["params"]["limit"], previous["params"]["chunk_raw"]
        level = previous["params"]["level"]
        result_files = {name: dict(fd) for name, fd in old.items() if name not in removed}
        used_names = {path.name for path in store.zips.iterdir()}
        prefix = hashlib.sha256(target.encode("utf-8")).hexdigest()[:20]
        additional = 0
        writer = None

        def fresh_entries(name):
            item = changed[name]
            chunks = -(-item.size // chunk_raw) if item.size > chunk_raw else 0
            result_files[name] = dict(name=name, size=item.size, mode=item.mode, sha256=hashes[name])
            if chunks:
                result_files[name]["chunks"] = chunks
            with open(item.local, "rb") as source:
                for i in range(1, (chunks or 1) + 1):
                    raw = source.read(chunk_raw) if chunks else source.read()
                    member = chunk_entry(name, i, chunks) if chunks else name
                    yield prepare(member, item.mode, raw, level, stored_type(name))

        try:
            replacements, new_parts = {}, []
            for first, last in spans:
                slots = [previous["parts"][i]["file"] for i in range(max(0, first), last + 1)]
                output_parts, emitted = [], set()

                def entries():
                    for index in range(max(0, first), last + 1):
                        for info in infos[index]:
                            name = owners[info.filename]
                            if name in removed:
                                continue
                            if name in changed:
                                if name not in emitted:
                                    emitted.add(name)
                                    yield from fresh_entries(name)
                            else:
                                yield _copied_entry(store.zips / previous["parts"][index]["file"], info, old[name]["mode"])
                    if last == len(previous["parts"]) - 1:
                        for name in sorted(new_names):
                            yield from fresh_entries(name)

                def close_part():
                    nonlocal writer
                    size, sha, count = writer.close()
                    read_back(writer.path, writer.entries)
                    if _sha(writer.path) != sha:
                        raise OSError("Written ZIP checksum mismatch")
                    output_parts.append(dict(file=writer.path.name, size=size, sha256=sha, entries=count))
                    writer = None

                for entry in entries():
                    if writer is not None and not writer.fits(entry):
                        close_part()
                    if writer is None:
                        slot = len(output_parts)
                        if slot < len(slots):
                            name = slots[slot]
                        else:
                            while True:
                                additional += 1
                                name = previous["slug"] + "__" + prefix + "__part_" + str(additional).zfill(4) + ".zip"
                                if name not in used_names:
                                    used_names.add(name)
                                    new_parts.append(name)
                                    break
                        writer = PartWriter(staged / name, limit)
                    if not writer.fits(entry):
                        raise ValueError("An output member exceeds the ZIP part limit")
                    writer.add(entry)
                if writer is not None:
                    close_part()
                replacements[first] = (last, output_parts)

            parts, index = [], 0
            if -1 in replacements:
                parts.extend(replacements[-1][1])
            while index < len(previous["parts"]):
                if index in replacements:
                    last, updated = replacements[index]
                    parts.extend(updated)
                    index = last + 1
                else:
                    parts.append(previous["parts"][index])
                    index += 1
            record = dict(previous, files=sorted(result_files.values(), key=lambda fd: fd["name"]), parts=parts,
                          raw_bytes=sum(fd["size"] for fd in result_files.values()),
                          zip_bytes=sum(part["size"] for part in parts))
            record["revision_sha256"] = hashlib.sha256(json_bytes(record["files"])).hexdigest()
            errors = verify_compartment(_StagedParts(store, staged), dict(record, name=target), record["files"])
            if errors:
                raise OSError("; ".join(errors))
            _, after, after_dirs = inventory(store.root.parent, target)
            if times != after or directories.keys() != after_dirs.keys():
                changed_files = [name for name in times.keys() | after.keys() if times.get(name) != after.get(name)]
                changed_dirs = [name for name in directories.keys() | after_dirs.keys() if directories.get(name) != after_dirs.get(name)]
                raise RuntimeError("Loose output metadata changed during ZIP update; files="
                                   + repr(changed_files[:10]) + "; directories=" + repr(changed_dirs[:10]))
            metadata = dict(descriptor)
            from .output_timing import solver_index
            metadata["solver_events"] = solver_index(target, record["files"], items,
                                                     descriptor.get("solver_events"))
            metadata["mtimes_ns"] = {name: stamp for name, stamp in descriptor["mtimes_ns"].items() if name not in removed}
            metadata["mtimes_ns"].update({name: value[1] for name, value in times.items() if name not in removed})
            metadata["directories"] = dict(descriptor["directories"], **after_dirs)
            for name in deleted_dirs:
                metadata["directories"].pop(name, None)

            (work / "backup").mkdir()
            (work / "record.before").write_bytes(record_path.read_bytes())
            (work / "catalog.before").write_bytes(catalog.read_bytes())
            final_names = {part["file"] for part in parts}
            obsolete = [part["file"] for part in previous["parts"] if part["file"] not in final_names]
            changed_parts = [path.name for path in staged.iterdir()]
            journal = dict(work=work.relative_to(store.root).as_posix(), replacements=changed_parts + obsolete,
                           zip_directory=store.zips.relative_to(store.root).as_posix(),
                           new_parts=new_parts, record=descriptor["record"],
                           catalog=catalog.relative_to(store.root).as_posix(), committed=False)
            write_atomic(store.root / "update_pending.json", json_bytes(journal))
            for name in journal["replacements"]:
                live = store.zips / name
                if live.exists():
                    os.replace(live, work / "backup" / name)
                if (staged / name).exists():
                    os.replace(staged / name, live)
            write_atomic(record_path, json_bytes(record))
            write_atomic(catalog, json_bytes(metadata))
            journal["committed"] = True
            write_atomic(store.root / "update_pending.json", json_bytes(journal))
            recover_update(store)
            return dict(target=target, files=len(record["files"]), raw_bytes=record["raw_bytes"],
                        zip_bytes=record["zip_bytes"], parts=len(parts), updated_files=len(changed),
                        deleted_files=len(removed), rewritten_parts=changed_parts, verified=True)
        except BaseException:
            if writer is not None:
                writer.abort()
            if (store.root / "update_pending.json").exists():
                recover_update(store)
            elif work.exists():
                if not work.resolve().is_relative_to(store.tmp.resolve()):
                    raise ValueError("Invalid archive scratch directory")
                shutil.rmtree(work)
            raise
