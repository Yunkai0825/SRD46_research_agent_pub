"""
zip_images.planning -- cut a commit's tree into compartments.
=============================================================

A COMPARTMENT is the unit that is zipped, stored, reused and updated as a whole: a folder of the repository,
or the loose files directly inside a folder that was split. Planned top down:

  * the root is always split: its loose files are the compartment "(files)", each sub-folder is planned;
  * a folder whose raw size is <= the cap (default 150 MB) is ONE compartment (kind "tree");
  * a bigger folder is split: each sub-folder is planned, and its loose files become "<folder>/(files)"
    (kind "files"). Loose files that alone exceed the cap are cut into groups "<folder>/(files 1)",
    "(files 2)", ... at boundaries chosen from the file NAMES (a boundary follows a file whose name hash
    ends a group once the group holds a quarter of the cap), so adding or changing one file disturbs only
    its own group and, at most, the next one.

Each compartment is CONTENT-ADDRESSED. Its key is ``tree:<git tree id of the folder>`` for a whole folder
and ``files:<sha256>`` over the sorted (mode, blob id, name) list for loose files. The zips hold paths
relative to the compartment folder, so the key alone decides the zip contents: the same key in the store
means the compartment is reused, never rebuilt.

THE OPTIONAL CONFIG ``zip_images.json`` at the repository root (read from the COMMIT, like everything else):

    {
      "cap": 150000000,                 the folder size cap in bytes (the --cap option wins over it)
      "split": ["some/folder"],         always split these folders, even when they are under the cap
      "exclude": ["zip_images/published"],     committed artifact stores omitted from images
      "whole": ["other/folder"],        keep these folders as one compartment, even when over the cap
      "large_files": {"tool": "large_file_packs.py", "store": "_large_files"},   or null to switch off
      "extra_requirements": ["plotly", "pandas"],   Python packages installed on top of the Dockerfile's
      "start_check_env": {"NAME": "value"}          (reserved; not used yet)
    }
"""

from __future__ import annotations

import hashlib
import json
import posixpath
import re
from dataclasses import dataclass, field

from .unpack_images import FILES_LABEL, KIND_FILES, KIND_TREE, check_rel

DEFAULT_CAP = 150_000_000
CONFIG_NAME = "zip_images.json"
MIN_GROUP_SHARE = 4            # a loose-files group may end once it holds cap / MIN_GROUP_SHARE bytes
GROUP_MODULUS = 4              # ... after a file whose name hash is 0 modulo this

# Deflate ratio guesses for the plan's estimate (the real pack measures).
_STORED = {".zip", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".gz", ".tgz", ".7z", ".whl", ".xz", ".txz", ".bz2",
           ".zst", ".mp4", ".mp3", ".mov", ".avi", ".mkv", ".jar", ".docx", ".xlsx", ".pptx", ".odt", ".ods",
           ".npz", ".heic", ".woff", ".woff2", ".opju"}
_TEXT = {".py", ".md", ".txt", ".json", ".jsonl", ".csv", ".tsv", ".html", ".htm", ".js", ".css", ".xml", ".yaml",
         ".yml", ".log", ".ipynb", ".svg", ".sql", ".out", ".ini", ".cfg", ".toml", ".rst", ".tex", ".dat", ".sh",
         ".ps1", ".bat", ".r", ".c", ".h", ".cpp", ".java", ".ts", ".mjs", ".cif", ".mol", ".sdf", ".pdb"}
_DB = {".db", ".sqlite", ".sqlite3"}


def stored_type(name: str) -> bool:
    """Already-compressed file types: zipped without recompression."""
    return posixpath.splitext(name.lower())[1] in _STORED


def estimate_ratio(name: str) -> float:
    ext = posixpath.splitext(name.lower())[1]
    if ext in _STORED:
        return 1.0
    if ext in _TEXT:
        return 0.25
    if ext in _DB:
        return 0.35
    if ext == ".pdf":
        return 0.9
    return 0.6


@dataclass
class FileItem:
    path: str                   # repository-relative path (or a plain file name for wheels)
    mode: str
    oid: str                    # git blob id ("" for files read from disk)
    size: int
    local: str = ""             # a file on disk (wheels); empty for git blobs


@dataclass
class Folder:
    path: str
    oid: str
    files: list = field(default_factory=list)
    subs: dict = field(default_factory=dict)
    size: int = 0
    count: int = 0


@dataclass
class Compartment:
    name: str
    kind: str
    path: str                   # folder relative to the repository root ("" = the root); None for wheels
    key: str
    files: list                 # FileItem, sorted by entry name (UTF-8 bytes)
    raw_bytes: int = 0
    est_bytes: int = 0
    skipped: list = field(default_factory=list)   # submodules and other entries that are not packed

    def entry_name(self, item: FileItem) -> str:
        if not self.path:
            return item.path
        return item.path[len(self.path) + 1:]

    @property
    def key_hex(self) -> str:
        return self.key.split(":", 1)[1]

    @property
    def slug(self) -> str:
        return make_slug(self.name)


def make_slug(name: str) -> str:
    """A readable, file-name-safe form of a compartment name, at most 60 characters."""
    text = name
    if text == FILES_LABEL:
        text = "root_files"
    text = re.sub(r"\((files(?: \d+)?)\)", lambda m: m.group(1).replace(" ", ""), text)
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._-") or "root"
    if len(text) > 60:
        text = text[:28].rstrip("._-") + "--" + text[-30:].lstrip("._-")
    return text


def entry_sort_key(name: str) -> bytes:
    return name.encode("utf-8")


def build_tree(entries: list, root_oid: str) -> tuple:
    """(root Folder, skipped entries) from a GitRepo.list_tree() listing."""
    root = Folder("", root_oid)
    folders = {"": root}
    skipped = []
    for e in entries:
        if e.kind == "tree":
            folders[e.path] = Folder(e.path, e.oid)
    for path, f in folders.items():
        if path:
            parent = posixpath.dirname(path)
            folders[parent].subs[posixpath.basename(path)] = f
    for e in entries:
        if e.kind == "tree":
            continue
        if e.kind != "blob":
            skipped.append(e)            # submodules (160000): a commit id, no bytes to pack
            continue
        folder = folders[posixpath.dirname(e.path)]
        folder.files.append(FileItem(e.path, e.mode, e.oid, e.size))
    _sizes(root)
    return root, skipped


def _sizes(f: Folder) -> None:
    f.size = sum(x.size for x in f.files)
    f.count = len(f.files)
    for sub in f.subs.values():
        _sizes(sub)
        f.size += sub.size
        f.count += sub.count


def _all_files(f: Folder) -> list:
    out = list(f.files)
    for sub in f.subs.values():
        out.extend(_all_files(sub))
    return out


def files_key(items: list, base: str) -> str:
    h = hashlib.sha256(b"zip-images files/1\n")
    for it in sorted(items, key=lambda x: entry_sort_key(_rel(x.path, base))):
        h.update("{} {} {}\n".format(it.mode, it.oid, _rel(it.path, base)).encode("utf-8"))
    return "files:" + h.hexdigest()


def _rel(path: str, base: str) -> str:
    return path[len(base) + 1:] if base else path


def _group_loose(items: list, base: str, cap: int) -> list:
    """Cut a folder's loose files into groups at name-hash boundaries (stable under small changes)."""
    items = sorted(items, key=lambda x: entry_sort_key(_rel(x.path, base)))
    if sum(i.size for i in items) <= cap:
        return [items]
    groups, cur, size = [], [], 0
    for it in items:
        cur.append(it)
        size += it.size
        name_hash = hashlib.sha1(_rel(it.path, base).encode("utf-8")).digest()[0]
        if size >= cap or (size >= cap // MIN_GROUP_SHARE and name_hash % GROUP_MODULUS == 0):
            groups.append(cur)
            cur, size = [], 0
    if cur:
        groups.append(cur)
    return groups


def _compartment(name: str, kind: str, path: str, key: str, items: list) -> Compartment:
    c = Compartment(name, kind, path, key, [])
    c.files = sorted(items, key=lambda x: entry_sort_key(c.entry_name(x)))
    c.raw_bytes = sum(i.size for i in items)
    c.est_bytes = estimate_zip_bytes(c)
    return c


def estimate_zip_bytes(c: Compartment) -> int:
    total = 22
    for it in c.files:
        name = len(c.entry_name(it).encode("utf-8"))
        total += 76 + 2 * name + int(it.size * estimate_ratio(it.path))
    return total


def plan(root: Folder, cap: int = DEFAULT_CAP, split=(), whole=()) -> list:
    """The compartments of a tree, in a stable order (by name)."""
    split, whole = set(split or ()), set(whole or ())
    out = []

    def loose(folder: Folder):
        if not folder.files:
            return
        base_name = (folder.path + "/" if folder.path else "") + FILES_LABEL
        groups = _group_loose(folder.files, folder.path, cap)
        for n, items in enumerate(groups, 1):
            name = base_name if len(groups) == 1 else base_name[:-1] + " {})".format(n)
            out.append(_compartment(name, KIND_FILES, folder.path, files_key(items, folder.path), items))

    def walk(folder: Folder):
        if folder.path and folder.count and folder.path not in split and (
                folder.size <= cap or folder.path in whole):
            out.append(_compartment(folder.path, KIND_TREE, folder.path, "tree:" + folder.oid, _all_files(folder)))
            return
        loose(folder)
        for name in sorted(folder.subs):
            walk(folder.subs[name])

    walk(root)
    out.sort(key=lambda c: entry_sort_key(c.name))
    return out


def read_config(repo, entries: list) -> dict:
    """The optional zip_images.json of the commit (from git), or {}."""
    for e in entries:
        if e.path == CONFIG_NAME and e.kind == "blob":
            try:
                data = json.loads(repo.blob_bytes(e.oid).decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as exc:
                raise ValueError("{} in the commit is not valid JSON: {}".format(CONFIG_NAME, exc)) from None
            if not isinstance(data, dict):
                raise ValueError("{} must hold a JSON object".format(CONFIG_NAME))
            return data
    return {}


def excluded_paths(config: dict) -> list:
    """Explicit commit-relative artifact prefixes; no globbing or implicit ignore rules."""
    values = config.get("exclude", [])
    if not isinstance(values, list) or any(not isinstance(x, str) for x in values):
        raise ValueError("zip_images.json exclude must be a list of relative paths")
    result = []
    for value in values:
        check_rel(value, "excluded path")
        if value != value.strip("/") or any(part.casefold() in (".git", CONFIG_NAME) for part in value.split("/")):
            raise ValueError("Invalid excluded artifact path: " + value)
        if value.casefold() in [x.casefold() for x in result]:
            raise ValueError("Duplicate excluded artifact path: " + value)
        result.append(value)
    return sorted(result)


def select_entries(entries: list, prefixes: list) -> list:
    return [entry for entry in entries
            if not any(entry.path == prefix or entry.path.startswith(prefix + "/") for prefix in prefixes)]


def key_filtered_folders(root: Folder, prefixes: list) -> None:
    """Key affected folders from selected bytes even before the excluded store exists."""
    def visit(folder):
        if any(not folder.path or prefix.startswith(folder.path + "/") for prefix in prefixes):
            folder.oid = files_key(_all_files(folder), folder.path).split(":", 1)[1]
        for child in folder.subs.values():
            visit(child)
    visit(root)
