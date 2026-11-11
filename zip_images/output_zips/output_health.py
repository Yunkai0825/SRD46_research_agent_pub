"""Check extraction coverage from directory entries without reading file contents."""
from collections import defaultdict
import json
import os
import zipfile

from ..unpack_images import check_rel


def _complete(base, files, directories=(), alternate=None):
    expected_files, expected_dirs = defaultdict(set), defaultdict(set)
    expected_files[""]

    def directory(name):
        while name:
            parent, _, child = name.rpartition("/")
            expected_dirs[parent].add(os.path.normcase(child))
            expected_files[name]
            name = parent

    for name in directories:
        if name:
            directory(check_rel(name, "unpacked directory"))
    for name in files:
        name = check_rel(name, "unpacked file")
        parent, _, child = name.rpartition("/")
        directory(parent)
        expected_files[parent].add(os.path.normcase(child))
    try:
        bases = [path for path in (base, alternate) if path is not None and path.is_dir()
                 and not path.is_symlink() and not (getattr(path.lstat(), 'st_file_attributes', 0) & 0x400)]
        if not bases:
            return False
        for rel, names in expected_files.items():
            files_here, dirs_here = set(), set()
            for base in bases:
                try:
                    with os.scandir(base / rel) as entries:
                        for entry in entries:
                            key = os.path.normcase(entry.name)
                            if entry.is_symlink() or (getattr(entry.stat(follow_symlinks=False), 'st_file_attributes', 0) & 0x400):
                                continue
                            if entry.is_file(follow_symlinks=False):
                                files_here.add(key)
                            elif entry.is_dir(follow_symlinks=False):
                                dirs_here.add(key)
                except (FileNotFoundError, NotADirectoryError):
                    continue
            if not names.issubset(files_here) or not expected_dirs[rel].issubset(dirs_here):
                return False
    except (FileNotFoundError, NotADirectoryError):
        return False
    return True


def unpack_status(archives):
    """Existing local edits count as unpacked; extraction never overwrites them."""
    missing = []
    for target, doc in archives.runs.items():
        base = archives.root / target
        if not base.is_dir():
            missing.append(target)
            continue
        record = json.loads((archives.store / doc["record"]).read_text("utf-8"))
        if not _complete(base, (f["name"] for f in record["files"]), doc["directories"]):
            missing.append(target)
    web = sorted((archives.root / "_benchmark/_Claude_web_answers").glob("*.zip"))
    for source in web:
        destination = source.parent / source.stem
        with zipfile.ZipFile(source) as archive:
            members = archive.infolist()
        files = [item.filename for item in members if not item.is_dir()]
        dirs = [item.filename.rstrip("/") for item in members if item.is_dir()]
        if not _complete(destination, files, dirs, alternate=source.parent):
            missing.append(source.relative_to(archives.root).as_posix())
    return {"runs": len(archives.runs) + len(web), "missing_runs": len(missing),
            "needs_unpack": bool(missing), "missing": missing}
