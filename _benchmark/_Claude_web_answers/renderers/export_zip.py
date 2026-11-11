"""Read a self-contained model archive or legacy "Claude Export" run by run.

Consolidated archives hold <configuration>/<prompt_id>/run.json and original
messages/artifacts in that same run folder. No provenance mapping is needed.

A legacy export holds <prompt>/<effort-LEVEL_runN>/ folders, each with messages.json, transcript.md,
artifacts/ (artifacts/sandbox/ for sandbox files) and sandbox_manifest.json. The top folder
inside the zip can have any name (or none), so runs are found by their messages.json files.

    exp = Export("N:/Document/Opus4_7.zip")
    exp.group                    # "Opus4_7" (file or folder name)
    for run in exp.runs():       # sorted L1_1, L1_2, ... then max, high, medium, low
        run.prompt, run.run_name, run.effort, run.run_no
        run.messages()           # parsed messages.json
        run.files("artifacts/")  # {relative path in run: reader}
        run.read("artifacts/x.png")
"""
import json, re, zipfile
from pathlib import Path, PurePosixPath

EFFORT_RANK = {"max": 0, "high": 1, "medium": 2, "low": 3}


def _zip_name(info):
    n = info.filename
    if not info.flag_bits & 0x800:  # not flagged UTF-8: Windows tools often wrote cp437
        try:
            n = n.encode("cp437").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return n.replace("\\", "/")


def prompt_sort_key(prompt):
    m = re.match(r"L(\d+)_(\d+)", prompt)
    return (int(m.group(1)), int(m.group(2))) if m else (999, 999)


class Run:
    def __init__(self, export, prefix, prompt, run_name, metadata=None):
        self.export, self.prefix, self.prompt, self.run_name = export, prefix, prompt, run_name
        self.metadata = metadata or {}
        m = re.match(r"effort-(\w+?)_run(\d+)$", run_name)
        self.effort = m.group(1) if m else run_name
        self.run_no = int(m.group(2)) if m else 1
        self.rel = f"{prompt}/{run_name}"
        self._messages = None

    @property
    def prompt_id(self):
        return self.metadata.get("prompt_id", self.prompt.split(" ", 1)[0])

    @property
    def group(self):
        return self.metadata.get("export", self.export.group)

    @property
    def render_prefix(self):
        return self.prefix.rstrip("/") if self.metadata else f"{self.group}/{self.rel}"

    @property
    def config(self):
        """Folder name used by the parsed tree, e.g. Opus4_7_high (or Opus4_7_high_run2)."""
        return self.metadata.get("config", f"{self.group}_{self.effort}" + ("" if self.run_no == 1 else f"_run{self.run_no}"))

    def read(self, rel):
        return self.export._read(self.prefix + rel)

    def exists(self, rel):
        return (self.prefix + rel) in self.export._names

    def messages(self):
        if self._messages is None:
            self._messages = json.loads(self.read("messages.json").decode("utf-8"))
        return self._messages

    def manifest(self):
        return json.loads(self.read("sandbox_manifest.json").decode("utf-8")) if self.exists("sandbox_manifest.json") else {}

    def files(self, under=""):
        """relative path in the run -> full name, for files under `under` (e.g. 'artifacts/')."""
        p = self.prefix + under
        return {n[len(self.prefix):]: n for n in self.export._names if n.startswith(p) and not n.endswith("/")}

    def sort_key(self):
        return prompt_sort_key(self.prompt) + (EFFORT_RANK.get(self.effort, 9), self.run_no)


class Export:
    def __init__(self, path):
        self.path = Path(path)
        self.group = self.path.stem if self.path.suffix.lower() == ".zip" else self.path.name
        if self.path.is_dir():
            self._zip = None
            self._names = {p.relative_to(self.path).as_posix(): p for p in self.path.rglob("*") if p.is_file()}
        else:
            self._zip = zipfile.ZipFile(self.path)
            self._names = {}
            for info in self._zip.infolist():
                self._names[_zip_name(info)] = info
        self._runs = []
        metadata_names = sorted(n for n in self._names if len(PurePosixPath(n).parts) == 3 and n.endswith("/run.json"))
        self.is_consolidated = bool(metadata_names)
        for n in metadata_names:
            meta = json.loads(self._read(n).decode("utf-8"))
            config, prompt_id, _ = PurePosixPath(n).parts
            if meta.get("schema_version") != 1 or meta.get("config") != config or meta.get("prompt_id") != prompt_id:
                raise ValueError(f"Invalid consolidated run metadata: {n}")
            prefix = n[:-len("run.json")]
            if prefix + "messages.json" not in self._names:
                raise ValueError(f"Consolidated run has no original messages.json: {n}")
            self._runs.append(Run(self, prefix, meta["prompt"], meta["run_name"], meta))
        for n in self._names:
            if self.is_consolidated:
                break
            parts = PurePosixPath(n).parts
            if parts[-1] != "messages.json" or len(parts) < 3:
                continue
            prompt, run_name = parts[-3], parts[-2]
            prefix = "/".join(parts[:-1]) + "/"
            self._runs.append(Run(self, prefix, prompt, run_name))
        self._runs.sort(key=Run.sort_key)
        self.top = ""
        if self._runs:
            parts = PurePosixPath(self._runs[0].prefix).parts
            self.top = "/".join(parts[:-2]) + ("/" if len(parts) > 2 else "")

    def _read(self, name):
        obj = self._names[name]
        if self._zip is None:
            return Path(obj).read_bytes()
        return self._zip.read(obj)

    def read_top(self, rel):
        n = self.top + rel
        return self._read(n) if n in self._names else None

    def runs(self):
        return list(self._runs)

    def close(self):
        if self._zip is not None:
            self._zip.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def shown_branch(conv):
    """Messages on the branch claude.ai shows (root -> current leaf), in order."""
    by = {m["uuid"]: m for m in conv["chat_messages"]}
    out, u = [], conv.get("current_leaf_message_uuid")
    while u in by:
        out.append(by[u])
        u = by[u]["parent_message_uuid"]
    return out[::-1]
