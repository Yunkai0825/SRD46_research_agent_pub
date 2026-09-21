"""Read saved benchmark/freeform artifacts, including ZIP members, without extraction.

This is a read-only catalog. Output locations remain declared by their writers.
"""
from __future__ import annotations

import fnmatch
import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

from archive_io import archive_exists, archive_signature, logical_archive_path, open_zip

KINDS = {"analysis": "Analysis Agent", "query": "Query Agent", "main": "Main Agent"}
_QUERY_RESULT = re.compile(r"^(Q.+)_result_batch(\d+)\.md$")
_ANALYSIS_ID = re.compile(r"^(L\d+_\d+)(?:_|$)")


def natural_key(value):
    return tuple((0, int(part)) if part.isdigit() else (1, part.casefold())
                 for part in re.split(r"(\d+)", str(value)))


def _safe_member(name):
    parts = name.rstrip("/").split("/")
    return (bool(name) and not any(p in {"", ".", ".."} for p in parts)
            and not any(c in name for c in ("\\", ":")) and not any(ord(c) < 32 for c in name))


@lru_cache(maxsize=16)
def _zip_index(filename, signature):
    """Cache only central-directory metadata; archives remain closed between reads."""
    with open_zip(filename) as archive:
        files = {entry.filename: entry.file_size for entry in archive.infolist()
                 if not entry.is_dir() and _safe_member(entry.filename)}
    directories = {""}
    for name in files:
        for parent in PurePosixPath(name).parents:
            directories.add("" if str(parent) == "." else parent.as_posix())
    paths = tuple(sorted(set(files) | directories))
    children = {}
    for name in paths:
        if not name:
            continue
        parent = PurePosixPath(name).parent.as_posix()
        children.setdefault("" if parent == "." else parent, []).append(name)
    return files, directories, {parent: tuple(names) for parent, names in children.items()}, paths


@dataclass(frozen=True)
class ArchivePath:
    archive: Path
    member: str = ""
    _snapshot: tuple | None = field(default=None, compare=False, repr=False)

    def __post_init__(self):
        if self.member and not _safe_member(self.member):
            raise ValueError("Unsafe archive member")
        if self._snapshot is None:
            # Descendants share one central-directory metadata snapshot. A newly discovered
            # or resolved archive checks every volume timestamp/size on each request.
            object.__setattr__(self, "_snapshot",
                               _zip_index(str(self.archive), archive_signature(self.archive)))

    def _index(self):
        return self._snapshot

    def with_member(self, member):
        return ArchivePath(self.archive, member, self._snapshot)

    @property
    def name(self):
        return PurePosixPath(self.member).name if self.member else self.archive.name

    @property
    def suffix(self):
        return PurePosixPath(self.member).suffix

    @property
    def parent(self):
        parent = PurePosixPath(self.member).parent.as_posix()
        return self.with_member("" if parent == "." else parent)

    def __truediv__(self, child):
        return self.joinpath(child)

    def joinpath(self, *parts):
        member = "/".join(str(part).replace("\\", "/") for part in parts)
        return self.with_member("/".join(filter(None, (self.member, member))))

    def resolve(self):
        return self

    def is_relative_to(self, other):
        return (isinstance(other, ArchivePath) and self.archive == other.archive
                and (not other.member or self.member == other.member
                     or self.member.startswith(other.member + "/")))

    def relative_to(self, other):
        if not self.is_relative_to(other):
            raise ValueError("Different artifact roots")
        relative = self.member[len(other.member):].lstrip("/")
        return PurePosixPath(relative)

    def is_file(self):
        return self.member in self._index()[0]

    def is_dir(self):
        return self.member in self._index()[1]

    def read_bytes(self):
        with open_zip(self.archive) as archive:
            return archive.read(self.member)

    def read_text(self, encoding="utf-8", errors="strict"):
        return self.read_bytes().decode(encoding, errors)

    def open(self, mode="r", encoding="utf-8", errors="strict"):
        if mode not in {"r", "rb"}:
            raise ValueError("Saved archives are read-only")
        data = self.read_bytes()
        return io.BytesIO(data) if mode == "rb" else io.StringIO(data.decode(encoding, errors))

    def stat(self):
        return SimpleNamespace(st_size=self._index()[0][self.member])

    def iterdir(self):
        for name in self._index()[2].get(self.member, ()):
            yield self.with_member(name)

    def rglob(self, pattern):
        prefix = self.member + "/" if self.member else ""
        for name in self._index()[3]:
            if name.startswith(prefix) and name != self.member and fnmatch.fnmatch(PurePosixPath(name).name, pattern):
                yield self.with_member(name)

    def glob(self, pattern):
        for path in self.rglob("*"):
            relative = path.relative_to(self).as_posix()
            if relative.count("/") == pattern.count("/") and fnmatch.fnmatch(relative, pattern):
                yield path

    def __lt__(self, other):
        return self.member < other.member


ArtifactPath = Path | ArchivePath


def read_json(path):
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, zipfile.BadZipFile):
        return {}


def query_results(directory):
    results = []
    for path in directory.iterdir():
        match = _QUERY_RESULT.fullmatch(path.name)
        if match and path.is_file():
            results.append((match.group(1), int(match.group(2)), path))
    return sorted(results, key=lambda result: result[1])


def _is_run(directory):
    return any((directory / name).is_file() for name in ("answer.md", "verdict.json")) or bool(query_results(directory))


def discover_runs(root):
    """Walk collection containers, stopping before the internals of each real run."""
    if not root.is_dir():
        return []
    found = []

    def walk(directory, identifier, depth=0):
        if depth > 10:
            return
        if identifier and _is_run(directory):
            found.append((identifier, directory))
            return
        seen_archives = set()
        for child in directory.iterdir():
            if (child.name.startswith((".", "__")) or child.name.lstrip("_").casefold().startswith("obsolete")
                    or child.name in {"final", "_cost_audit", "_output_eval", "_evaluation", "_enrichment_cache", "_checkpoints", "_snapshots"}):
                continue
            child_id = "/".join(filter(None, (identifier, child.name)))
            if isinstance(child, Path):
                if not child.resolve().is_relative_to(root.resolve()):
                    continue
                archive = logical_archive_path(child)
                if child.is_file() and archive.suffix.lower() == ".zip":
                    # Independent parts retain one logical archive/run URL.
                    # An ordinary ZIP takes precedence while parts are staged.
                    if archive in seen_archives or (archive != child and archive.is_file()):
                        continue
                    seen_archives.add(archive)
                    archive_id = "/".join(filter(None, (identifier, archive.name)))
                    try:
                        walk(ArchivePath(archive.resolve()), archive_id, depth + 1)
                    except (OSError, zipfile.BadZipFile):
                        continue
            if child.is_dir():
                walk(child, child_id, depth + 1)

    walk(root, "")
    return sorted(found, key=lambda pair: natural_key(pair[0]))


def resolve_run(root, identifier):
    """Resolve a literal repo-relative folder/archive path; no alias manifest."""
    if not _safe_member(identifier):
        return None
    parts = identifier.split("/")
    current = root
    for offset, part in enumerate(parts):
        current = current / part
        if not current.resolve().is_relative_to(root.resolve()):
            return None
        if current.suffix.lower() == ".zip" and archive_exists(current):
            try:
                current = ArchivePath(current.resolve(), "/".join(parts[offset + 1:]))
                return current if current.is_dir() and _is_run(current) else None
            except (OSError, ValueError, zipfile.BadZipFile):
                return None
    return current if current.is_dir() and _is_run(current) else None


def load_prompt_registry(repo):
    """Use the same authored Markdown tables that the batch runners consume."""
    prompts = {kind: {} for kind in KINDS}
    query = repo / "NIST_SRD46_db_agent/NIST_SRD46_query_agent/TEST_PROMPTS.md"
    analysis = repo / "NIST_SRD46_db_agent/NIST_SRD46_analysis_agent/_DEBUG_input/TEST_PROMPTS.md"
    section = ""
    if query.is_file():
        for line in query.read_text(encoding="utf-8-sig").splitlines():
            match = re.match(r"^##\s+([\d.]+)\s+[—-]\s+(.+)", line)
            if match:
                section = match.group(2)
            match = re.match(r"^\|\s*([\d.]+)\s*\|\s*(.*?)\s*\|\s*$", line)
            if match:
                identifier = "Q" + match.group(1)
                prompts["query"][identifier] = {"id": identifier, "title": identifier,
                                                "prompt": match.group(2), "section": section}
    if analysis.is_file():
        for line in analysis.read_text(encoding="utf-8-sig").splitlines():
            match = re.match(r"^\|\s*\d+\s*\|\s*([^|]+?)\s*\|\s*(L\d+_\d+[^|]*?)\s*\|\s*(.*?)\s*\|\s*$", line)
            if match:
                title = match.group(2)
                identifier = _ANALYSIS_ID.match(title).group(1)
                prompts["analysis"][identifier] = {"id": identifier, "title": title,
                                                   "prompt": match.group(3), "section": match.group(1)}
    return prompts


def run_kind(identifier, metadata, is_query=False):
    explicit = str(metadata.get("agent_kind") or metadata.get("agent") or "").lower().replace("_agent", "")
    if explicit in KINDS:
        return explicit
    # A stored manifest may identify the agent even after a run is copied flat.
    kind_parts = identifier.split("/") + str(metadata.get("session_dir") or "").replace("\\", "/").split("/")
    for part in kind_parts:
        normalized = part.casefold().replace("_agent", "")
        if normalized in KINDS:
            return normalized
    return "query" if is_query else "analysis"


def run_mode(identifier, metadata):
    explicit = str(metadata.get("benchmark_mode") or metadata.get("execution_mode") or metadata.get("mode") or "").strip()
    pieces = identifier.lower().replace("-", "_").split("/")
    for piece in ([explicit.lower().replace("-", "_")] if explicit else []) + pieces:
        if "no_ledger" in piece or piece == "noledger":
            return "No ledger"
        if "bare_model" in piece:
            return "Bare model"
        if "ledgered" in piece or piece in {"canonical", "full_framework"}:
            return "Full framework"
    if explicit:
        return explicit.replace("_", " ").strip().capitalize()
    for piece in pieces:
        if piece.startswith("test_run_"):
            mode = re.sub(r"(?:_\d{8}.*)?(?:\.zip)?$", "", piece[9:]).strip("_")
            if mode and not mode[0].isdigit():
                return mode.replace("_", " ").capitalize()
    return "Full framework"


def prompt_from_result(path):
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        head = handle.read(32768)
    match = re.search(r"^\*\*Prompt:\*\*\s*(.+)$", head, re.MULTILINE)
    return match.group(1).strip() if match else ""


def catalog_runs(root):
    runs = []
    for identifier, directory in discover_runs(root):
        metadata = read_json(directory / "verdict.json")
        manifest = metadata.get("manifest") or read_json(directory / "manifest.json")
        if isinstance(manifest, dict):
            metadata = {**manifest, **metadata}
        model = str(metadata.get("model") or next((part[6:] for part in identifier.split("/") if part.startswith("Model_")), ""))
        query = query_results(directory)
        if query:
            for question, batch, document in query:
                runs.append({"id": identifier, "prompt_id": question, "title": question,
                             "kind": run_kind(identifier, metadata, True), "mode": run_mode(identifier, metadata),
                             "prompt": prompt_from_result(document), "batch": batch, "model": model, "metadata": metadata,
                             "result_count": 1, "directory": directory})
        else:
            title = directory.name
            match = _ANALYSIS_ID.match(title)
            runs.append({"id": identifier, "prompt_id": match.group(1) if match else title, "title": title,
                         "kind": run_kind(identifier, metadata), "mode": run_mode(identifier, metadata),
                         "prompt": str(metadata.get("request") or metadata.get("user_request") or metadata.get("prompt") or ""),
                         "batch": None, "model": model, "metadata": metadata, "directory": directory,
                         "result_count": (sum(path.is_dir() for path in directory.glob("final/result_*"))
                                          or sum(path.is_dir() for path in directory.glob("L1_call_*")))})
    return runs


def build_catalog(repo, root, include_prompts=True):
    registry = load_prompt_registry(repo) if include_prompts else {kind: {} for kind in KINDS}
    catalogs = {kind: {identifier: {**prompt, "runs": {}} for identifier, prompt in prompts.items()}
                for kind, prompts in registry.items()}
    modes = {kind: set() for kind in KINDS}
    counts = {kind: 0 for kind in KINDS}
    for run in catalog_runs(root):
        kind, identifier, mode = run["kind"], run["prompt_id"], run["mode"]
        row = catalogs[kind].setdefault(identifier, {"id": identifier, "title": run["title"],
                                                    "prompt": run["prompt"], "section": "", "runs": {}})
        if not row["prompt"]:
            row["prompt"] = run["prompt"]
        row["runs"].setdefault(mode, []).append(run)
        modes[kind].add(mode)
        counts[kind] += 1
    return {kind: {"rows": sorted(rows.values(), key=lambda row: natural_key(row["id"])),
                   "modes": sorted(modes[kind], key=lambda mode: (mode != "Full framework", natural_key(mode))) or ["Full framework"],
                   "run_count": counts[kind]}
            for kind, rows in catalogs.items()}
