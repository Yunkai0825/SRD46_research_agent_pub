"""Claude-web answers: the stored archives, the files of one run and its working trace.

The web answers folder holds, beside ``parsed/`` (final answers with their
figures), one zip archive per export.  An archive keeps every run in full
under ``<config>/<prompt id>/``: the files Claude presented, the sandbox
working files, the chat previews, the saved pages and the conversation
record.  This module reads those archives in place (nothing is extracted to
disk) and turns ``conversation.json`` into a step-by-step trace.

No Flask here: the routes in ``analysis.py`` pass URL builders and the
markdown renderer in, so the functions can be tested on a temporary folder.
"""

from __future__ import annotations

import csv
import html
import io
import json
import re
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, List, Optional, Tuple

SUMMARY_DIRNAME = "_summary"
TIMING_DIRNAME = "timing_comparison"

TEXT_PREVIEW_BYTES = 400_000     # text shown inline in the file viewer; the rest by download
TABLE_PREVIEW_ROWS = 200         # CSV rows shown inline
TRACE_FIELD_CHARS = 200_000      # one tool input or output shown in the trace

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
_HTML_SUFFIXES = {".html", ".htm"}
_CODE_SUFFIXES = {".py", ".js", ".sh", ".r", ".m", ".ipynb", ".css", ".yaml", ".yml", ".toml", ".ini"}
_TEXT_SUFFIXES = {".txt", ".log", ".dat", ".tsv"}
_UUID_NAME = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.\w+$", re.IGNORECASE)

_RECORD_FILES = ("README.md", "final_answer.md", "transcript.md", "conversation.json", "messages.json",
                 "run.json", "sandbox_manifest.json")

GROUPS = (
    ("presented", "Presented to the user",
     "the files Claude handed over with the answer"),
    ("rendered", "Figures and pages of the answer",
     "figures, saved pages and their screenshots, as placed beside the final answer"),
    ("sandbox", "Sandbox working files",
     "scripts, data and intermediate figures recovered from the working directory"),
    ("previews", "Chat previews",
     "images Claude looked at while working, in order, intermediate versions included"),
    ("record", "Record",
     "the final answer, the transcript and the conversation export"),
)


# ---------------------------------------------------------------------------
# File kinds and small formatters
# ---------------------------------------------------------------------------

def file_kind(name: str) -> str:
    """How the viewer shows a file: image, html, table, markdown, json, code, text, pdf or binary."""
    suffix = PurePosixPath(name).suffix.lower()
    if suffix in _IMAGE_SUFFIXES:
        return "image"
    if suffix in _HTML_SUFFIXES:
        return "html"
    if suffix == ".csv":
        return "table"
    if suffix == ".md":
        return "markdown"
    if suffix == ".json":
        return "json"
    if suffix in _CODE_SUFFIXES:
        return "code"
    if suffix in _TEXT_SUFFIXES:
        return "text"
    if suffix == ".pdf":
        return "pdf"
    return "binary"


def is_active_content(name: str) -> bool:
    """Files a browser would run scripts from when opened directly (model-written pages, SVG)."""
    return PurePosixPath(name).suffix.lower() in _HTML_SUFFIXES | {".svg"}


def human_size(n: Optional[int]) -> str:
    if n is None:
        return ""
    size = float(n)
    for unit in ("B", "kB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return ""


def human_duration(seconds: Any) -> str:
    try:
        value = float(seconds)
    except (TypeError, ValueError):
        return ""
    if value < 0:
        return ""
    if value < 60:
        return f"{value:.0f} s"
    minutes, sec = divmod(int(round(value)), 60)
    if minutes < 60:
        return f"{minutes} min {sec:02d} s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes:02d} min"


def clean_member(rel: str) -> str:
    """A member path as the archive spells it: forward slashes, no leading slash, no dot segments."""
    parts = [p for p in (rel or "").replace("\\", "/").split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        return ""
    return "/".join(parts)


# ---------------------------------------------------------------------------
# Archives
# ---------------------------------------------------------------------------

_archive_cache: Dict[str, Dict[str, Any]] = {}


def _archive_info(zip_path: Path) -> Optional[Dict[str, Any]]:
    """Members and run index of one archive, cached until the file changes."""
    try:
        stat = zip_path.stat()
    except OSError:
        return None
    key = str(zip_path)
    stamp = (stat.st_mtime_ns, stat.st_size)
    cached = _archive_cache.get(key)
    if cached is not None and cached["stamp"] == stamp:
        return cached
    try:
        with zip_path.open("rb") as source, zipfile.ZipFile(source) as archive:
            sizes = {i.filename: i.file_size for i in archive.infolist() if not i.is_dir()}
            index: Any = []
            if "runs_index.json" in sizes:
                index = json.loads(archive.read("runs_index.json").decode("utf-8", "replace"))
    except (OSError, ValueError, zipfile.BadZipFile):
        return None
    runs: Dict[Tuple[str, str], str] = {}
    for entry in index if isinstance(index, list) else []:
        if not isinstance(entry, dict):
            continue
        config, pid = str(entry.get("config") or ""), str(entry.get("prompt_id") or "")
        if config and pid:
            runs[(config, pid)] = f"{config}/{pid}/"
    if not runs:  # no index: every <config>/<prompt id>/ folder that holds a final answer is a run
        for name in sizes:
            parts = name.split("/")
            if len(parts) == 3 and parts[2] == "final_answer.md":
                runs[(parts[0], parts[1])] = f"{parts[0]}/{parts[1]}/"
    info = {"stamp": stamp, "path": zip_path, "sizes": sizes, "runs": runs}
    _archive_cache[key] = info
    return info


def find_run(web_dir: Path, config: str, pid: str) -> Optional[Dict[str, Any]]:
    """The archived copy of one run: ``{"zip": path, "prefix": "<config>/<pid>/", "files": {rel: size}}``."""
    try:
        zips = sorted(p for p in web_dir.iterdir() if p.suffix.lower() == ".zip" and p.is_file())
    except OSError:
        return None
    for zip_path in zips:
        info = _archive_info(zip_path)
        if info is None:
            continue
        prefix = info["runs"].get((config, pid))
        if prefix is None:
            continue
        files = {name[len(prefix):]: size for name, size in info["sizes"].items() if name.startswith(prefix)}
        folders = []
        for unpacked in (web_dir / zip_path.stem / config / pid, web_dir / config / pid):
            try:
                unpacked.resolve().relative_to(web_dir.resolve())
            except (OSError, ValueError):
                continue
            if unpacked.is_dir():
                folders.append(unpacked)
        for unpacked in reversed(folders):
            files.update(folder_files(unpacked))
        return {"zip": zip_path, "prefix": prefix, "files": files, "folders": folders}
    for parent in [web_dir] + [p for p in web_dir.iterdir() if p.is_dir() and p.name != "parsed"]:
        unpacked = parent / config / pid
        try:
            unpacked.resolve().relative_to(web_dir.resolve())
        except (OSError, ValueError):
            continue
        if (unpacked / "final_answer.md").is_file():
            return {"zip": None, "prefix": "", "files": folder_files(unpacked), "folder": unpacked}
    return None


def read_member(run: Dict[str, Any], rel: str, limit: Optional[int] = None) -> Optional[bytes]:
    """Bytes of one file of an archived run; only names the archive lists are read."""
    rel = clean_member(rel)
    if not rel or rel not in run["files"]:
        return None
    try:
        for folder in run.get("folders", [run["folder"]] if run.get("folder") is not None else []):
            local = folder / rel
            local.resolve().relative_to(folder.resolve())
            if local.is_file():
                with local.open("rb") as handle:
                    return handle.read() if limit is None else handle.read(limit)
        if run["zip"] is None:
            return None
        with run["zip"].open("rb") as source, zipfile.ZipFile(source) as archive:
            with archive.open(run["prefix"] + rel) as handle:
                return handle.read() if limit is None else handle.read(limit)
    except (OSError, KeyError, ValueError, zipfile.BadZipFile):
        return None


def folder_files(folder: Path) -> Dict[str, int]:
    """``{rel: size}`` of a parsed answer folder (used when no archive holds the run)."""
    files: Dict[str, int] = {}
    try:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                files[path.relative_to(folder).as_posix()] = path.stat().st_size
    except OSError:
        pass
    return files


def _group_of(rel: str) -> str:
    if rel.startswith("artifacts/sandbox/"):
        return "sandbox"
    if rel.startswith("artifacts/"):
        return "presented"
    if rel.startswith("view_images/"):
        return "previews"
    if "/" not in rel and rel in _RECORD_FILES:
        return "record"
    return "rendered" if file_kind(rel) in ("image", "html", "pdf") else "record"


def _shown_name(rel: str, group: str) -> str:
    if group == "sandbox":
        return rel[len("artifacts/sandbox/"):]
    if group == "presented":
        return rel[len("artifacts/"):]
    if group == "previews":
        return rel[len("view_images/"):]
    return rel


def group_files(files: Dict[str, int]) -> List[Dict[str, Any]]:
    """The files of a run in the viewer's groups; empty groups are left out.

    Chat previews are stored twice (numbered in viewing order, and under the
    id the conversation refers to): the listing shows the numbered copy when
    both exist.  ``messages.json`` repeats ``conversation.json`` and is left out.
    """
    numbered_previews = any(
        rel.startswith("view_images/") and not _UUID_NAME.match(rel.rsplit("/", 1)[-1]) for rel in files)
    buckets: Dict[str, List[Dict[str, Any]]] = {key: [] for key, _title, _note in GROUPS}
    for rel in sorted(files, key=lambda r: (r.count("/"), r.casefold())):
        group = _group_of(rel)
        if group == "previews" and numbered_previews and _UUID_NAME.match(rel.rsplit("/", 1)[-1]):
            continue
        if rel == "messages.json" and "conversation.json" in files:
            continue
        buckets[group].append({
            "rel": rel, "name": _shown_name(rel, group), "size": files[rel],
            "size_text": human_size(files[rel]), "kind": file_kind(rel),
        })
    record_order = {name: i for i, name in enumerate(_RECORD_FILES)}
    buckets["record"].sort(key=lambda f: (record_order.get(f["rel"], len(record_order)), f["rel"].casefold()))
    return [{"key": key, "title": title, "note": note, "files": buckets[key],
             "bytes": human_size(sum(f["size"] for f in buckets[key]))}
            for key, title, note in GROUPS if buckets[key]]


def reports(files: Dict[str, int]) -> List[Dict[str, Any]]:
    """Saved pages beside the answer, each with its stored screenshot when there is one."""
    found = []
    for rel in sorted(files):
        if "/" in rel or file_kind(rel) != "html":
            continue
        stem = PurePosixPath(rel).stem
        shot = next((c for c in (f"page_{stem}.png", f"rendered_{stem}.png", f"{stem}.png") if c in files), "")
        found.append({"rel": rel, "screenshot": shot, "size_text": human_size(files[rel])})
    return found


# ---------------------------------------------------------------------------
# File previews
# ---------------------------------------------------------------------------

def decode_text(data: bytes) -> str:
    return data.decode("utf-8", "replace").replace("\r\n", "\n")


def table_preview(text: str, max_rows: int = TABLE_PREVIEW_ROWS) -> Dict[str, Any]:
    """Header and first rows of a CSV file; the delimiter is the one the header line uses most."""
    text = text.lstrip("﻿\n")
    delimiter = max(",;\t", key=text.split("\n", 1)[0].count)
    rows: List[List[str]] = []
    total = 0
    for row in csv.reader(io.StringIO(text), delimiter=delimiter):
        if not any(cell.strip() for cell in row):
            continue
        total += 1
        if len(rows) <= max_rows:
            rows.append(row)
    header = rows[0] if rows else []
    body = rows[1:max_rows + 1]
    width = max([len(header)] + [len(r) for r in body] or [0])
    return {"header": header + [""] * (width - len(header)),
            "rows": [r + [""] * (width - len(r)) for r in body],
            "n_rows": max(total - 1, 0), "shown": len(body)}


def pretty_json(text: str) -> str:
    try:
        return json.dumps(json.loads(text), indent=1, ensure_ascii=False)
    except ValueError:
        return text


# ---------------------------------------------------------------------------
# Run statistics (parsed/_summary/runs.csv)
# ---------------------------------------------------------------------------

_stats_cache: Dict[str, Dict[str, Any]] = {}


def run_stats(parsed_root: Path) -> Dict[str, Dict[str, str]]:
    """``"<config>/<folder>" -> row`` of the harness run table; empty when the table is absent."""
    path = parsed_root / SUMMARY_DIRNAME / "runs.csv"
    try:
        stat = path.stat()
    except OSError:
        return {}
    stamp = (stat.st_mtime_ns, stat.st_size)
    cached = _stats_cache.get(str(path))
    if cached is not None and cached["stamp"] == stamp:
        return cached["rows"]
    rows: Dict[str, Dict[str, str]] = {}
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                key = (row.get("parsed_folder") or "").replace("\\", "/").strip("/")
                if key:
                    rows[key] = row
    except (OSError, csv.Error):
        return {}
    _stats_cache[str(path)] = {"stamp": stamp, "rows": rows}
    return rows


def _number(row: Dict[str, str], key: str) -> Optional[float]:
    try:
        return float(row.get(key) or "")
    except ValueError:
        return None


def _count(row: Dict[str, str], key: str) -> int:
    value = _number(row, key)
    return int(value) if value is not None else 0


def solver_excluded_timing(parsed_root: Path, config: str, pid: str) -> Dict[str, Any]:
    """Use the saved per-conversation timing audit, matched by configuration and prompt."""
    path = parsed_root.parent / TIMING_DIRNAME / "all_run_timings.csv"
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            matches = [row for row in csv.DictReader(handle)
                       if row.get("config") == config and row.get("prompt_id") == pid]
    except (OSError, csv.Error):
        matches = []
    if len(matches) != 1:
        return {"elapsed_s": None, "active_s": None, "note": "Solver-excluded timing is unavailable."}
    row = matches[0]
    qualifiers = [label for key, label in (("estimated", "estimated"), ("upper_bound", "upper bound"))
                  if row.get(key, "").lower() == "true"]
    note = "Saved timing audit, excluding solver execution"
    if qualifiers:
        note += "; " + ", ".join(qualifiers)
    return {"elapsed_s": _number(row, "non_solver_wall_s"), "active_s": _number(row, "non_solver_active_s"),
            "note": note + "."}


def stat_facts(row: Dict[str, str], timing=None) -> List[Dict[str, str]]:
    """The run facts of the header strip, in reading order; absent values are left out."""
    facts: List[Dict[str, str]] = []

    def add(label: str, value: str, title: str = "") -> None:
        if value:
            facts.append({"label": label, "value": value, "title": title})

    timing = timing or {}
    add("time excluding solver", human_duration(timing.get("elapsed_s")), timing.get("note", ""))
    add("active excluding solver", human_duration(timing.get("active_s")), timing.get("note", ""))
    add("thinking", human_duration(_number(row, "thinking_s")))
    add("tools (including solver)", human_duration(_number(row, "tool_s")))
    for one, many, key in (("tool call", "tool calls", "tool_calls"),
                           ("web search", "web searches", "web_searches"),
                           ("web page read", "web pages read", "pages_fetched"),
                           ("script written", "scripts written", "scripts_written"),
                           ("code line", "code lines", "code_lines_written"),
                           ("figure", "figures", "images"),
                           ("published page", "published pages", "html_reports"),
                           ("presented file", "presented files", "artifacts"),
                           ("sandbox file", "sandbox files", "sandbox_files")):
        n = _count(row, key)
        add(one if n == 1 else many, str(n) if n else "")
    segments = _count(row, "segments")
    if segments > 1:
        add("segments", str(segments),
            f"{_count(row, 'typed_continues')} typed and {_count(row, 'auto_continues')} automatic continuations")
    return facts


# ---------------------------------------------------------------------------
# Working trace (conversation.json)
# ---------------------------------------------------------------------------

def _parse_time(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _span(block: Dict[str, Any]) -> Optional[float]:
    start, stop = _parse_time(block.get("start_timestamp")), _parse_time(block.get("stop_timestamp"))
    if start is None or stop is None:
        return None
    return max((stop - start).total_seconds(), 0.0)


def _took(seconds: Optional[float]) -> str:
    """Duration of a step; steps under a second show none."""
    return human_duration(seconds) if seconds is not None and seconds >= 1 else ""


def _clock(seconds: Optional[float]) -> str:
    if seconds is None:
        return ""
    total = int(max(seconds, 0))
    hours, rest = divmod(total, 3600)
    return f"{hours}:{rest // 60:02d}:{rest % 60:02d}" if hours else f"{rest // 60}:{rest % 60:02d}"


def shown_branch(conversation: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], int]:
    """(messages of the branch the chat shows, number of messages on other branches).

    The export keeps every regenerated or edited message; the shown branch is
    the chain from ``current_leaf_message_uuid`` back through the parents.
    """
    messages = [m for m in conversation.get("chat_messages") or [] if isinstance(m, dict)]
    by_id = {m.get("uuid"): m for m in messages}
    leaf = by_id.get(conversation.get("current_leaf_message_uuid"))
    if leaf is None:
        return messages, 0
    chain: List[Dict[str, Any]] = []
    seen: set = set()
    node: Optional[Dict[str, Any]] = leaf
    while node is not None and node.get("uuid") not in seen:
        seen.add(node.get("uuid"))
        chain.append(node)
        node = by_id.get(node.get("parent_message_uuid"))
    chain.reverse()
    return chain, len(messages) - len(chain)


def _field(label: str, value: Any) -> Optional[Dict[str, Any]]:
    """One tool input or output as a labelled text block."""
    if value is None or value == "" or value == [] or value == {}:
        return None
    if not isinstance(value, str):
        value = json.dumps(value, indent=1, ensure_ascii=False)
    cut = len(value) - TRACE_FIELD_CHARS
    if cut > 0:
        value = value[:TRACE_FIELD_CHARS]
    lines = value.count("\n") + 1
    return {"label": label, "text": value, "lines": lines, "cut": max(cut, 0),
            "long": lines > 12 or len(value) > 900}


def _tool_title(block: Dict[str, Any]) -> str:
    data = block.get("input") if isinstance(block.get("input"), dict) else {}
    for key in ("description", "query", "url", "title", "label"):
        if isinstance(data.get(key), str) and data[key].strip():
            return data[key].strip()
    message = block.get("message")
    return message.strip() if isinstance(message, str) else ""


def _tool_fields(block: Dict[str, Any]) -> List[Dict[str, Any]]:
    data = block.get("input")
    if not isinstance(data, dict):
        field = _field("input", data)
        return [field] if field else []
    fields = []
    for key, value in data.items():
        if key == "description":
            continue
        field = _field(key, value)
        if field:
            fields.append(field)
    return fields


def _result_into(step: Dict[str, Any], block: Dict[str, Any], files: Dict[str, int],
                 url_for_member: Callable[[str], str]) -> None:
    """Attach a tool result to its call: output text, links found, images viewed, files handed over."""
    step["has_result"] = True
    step["is_error"] = bool(block.get("is_error"))
    content = block.get("content")
    parts = content if isinstance(content, list) else ([{"type": "text", "text": content}] if content else [])
    for part in parts:
        if not isinstance(part, dict):
            continue
        kind = part.get("type")
        if kind == "text":
            text = part.get("text") or ""
            shell = None
            if step["name"] == "bash_tool":
                try:
                    shell = json.loads(text)
                except ValueError:
                    shell = None
            if isinstance(shell, dict) and {"stdout", "stderr", "returncode"} & set(shell):
                code = shell.get("returncode")
                step["returncode"] = code
                if code not in (0, None):
                    step["is_error"] = True
                for label in ("stdout", "stderr"):
                    field = _field(label, shell.get(label))
                    if field:
                        step["outputs"].append(field)
            else:
                field = _field("result", text)
                if field:
                    step["outputs"].append(field)
        elif kind == "knowledge":
            url = part.get("url") or ""
            meta = part.get("metadata") if isinstance(part.get("metadata"), dict) else {}
            step["links"].append({"title": part.get("title") or url, "url": url,
                                  "site": meta.get("site_domain") or meta.get("site_name") or ""})
        elif kind == "image":
            rel = next((r for r in files if r.startswith(f"view_images/{part.get('file_uuid')}.")), "")
            step["images"].append({"url": url_for_member(rel) if rel else "", "rel": rel})
        elif kind == "local_resource":
            name = PurePosixPath(str(part.get("file_path") or "")).name or str(part.get("name") or "")
            rel = f"artifacts/{name}" if f"artifacts/{name}" in files else ""
            step["handed"].append({"name": name, "rel": rel})


def build_trace(conversation: Dict[str, Any], files: Dict[str, int],
                render_markdown: Callable[[str], str],
                url_for_member: Callable[[str], str]) -> Dict[str, Any]:
    """The shown branch of a conversation as messages of steps (thinking, text, tool calls).

    ``files`` is the run's ``{rel: size}`` listing (to link viewed images and
    handed-over files); thinking is stored as summaries only, so that is what
    a thinking step shows.
    """
    messages, n_other = shown_branch(conversation)
    origin: Optional[datetime] = None
    out: List[Dict[str, Any]] = []
    counts = {"thinking": 0, "text": 0, "tool": 0, "errors": 0}
    tools: Dict[str, int] = {}
    for message in messages:
        sender = "human" if message.get("sender") == "human" else "assistant"
        blocks = [b for b in message.get("content") or [] if isinstance(b, dict)]
        if not blocks and message.get("text"):
            blocks = [{"type": "text", "text": message["text"]}]
        steps: List[Dict[str, Any]] = []
        by_call: Dict[str, Dict[str, Any]] = {}
        for block in blocks:
            start = _parse_time(block.get("start_timestamp"))
            if origin is None and start is not None:
                origin = start
            base = {"at": _clock((start - origin).total_seconds()) if start and origin else "",
                    "took": _took(_span(block))}
            kind = block.get("type")
            if kind == "text":
                text = block.get("text") or ""
                if not text.strip():
                    continue
                counts["text"] += 1
                steps.append({**base, "kind": "text", "html": render_markdown(text)})
            elif kind == "thinking":
                notes = [s.get("summary") for s in block.get("summaries") or []
                         if isinstance(s, dict) and s.get("summary")]
                counts["thinking"] += 1
                steps.append({**base, "kind": "thinking", "notes": notes,
                              "text": block.get("thinking") or ""})
            elif kind == "tool_use":
                name = str(block.get("name") or "tool")
                counts["tool"] += 1
                tools[name] = tools.get(name, 0) + 1
                step = {**base, "kind": "tool", "name": name, "title": _tool_title(block),
                        "fields": _tool_fields(block), "outputs": [], "links": [], "images": [],
                        "handed": [], "has_result": False, "is_error": False, "returncode": None,
                        "called": block.get("start_timestamp")}
                steps.append(step)
                by_call[str(block.get("id"))] = step
            elif kind == "tool_result":
                step = by_call.get(str(block.get("tool_use_id")))
                if step is None:
                    step = {**base, "kind": "tool", "name": str(block.get("name") or "tool"), "title": "",
                            "fields": [], "outputs": [], "links": [], "images": [], "handed": [],
                            "has_result": False, "is_error": False, "returncode": None, "called": None}
                    steps.append(step)
                _result_into(step, block, files, url_for_member)
                # a call lasts from its start to the end of its result
                whole = _took(_span({"start_timestamp": step["called"],
                                     "stop_timestamp": block.get("stop_timestamp")}))
                step["took"] = whole or step["took"]
        for step in steps:
            if step["kind"] == "tool" and step["is_error"]:
                counts["errors"] += 1
        created = _parse_time(message.get("created_at"))
        out.append({"sender": sender, "steps": steps,
                    "created": created.strftime("%Y-%m-%d %H:%M UTC") if created else "",
                    "stop_reason": message.get("stop_reason") or "",
                    "compacted": bool(message.get("compaction_summary"))})
    return {"messages": out, "n_other_branches": n_other, "counts": counts,
            "tools": sorted(tools.items(), key=lambda item: (-item[1], item[0]))}


# ---------------------------------------------------------------------------
# Final answer: files it names
# ---------------------------------------------------------------------------

_PRESENTED_LINE = re.compile(r"(Presented file: <code>)([^<]+)(</code>)")


def link_presented_files(answer_html: str, files: Dict[str, int], url_for_view: Callable[[str], str]) -> str:
    """Turn "Presented file: <code>name</code>" into a link to the file viewer when the file is stored."""
    def swap(match: "re.Match[str]") -> str:
        name = match.group(2).strip()
        rel = f"artifacts/{name}"
        if rel not in files:
            return match.group(0)
        href = html.escape(url_for_view(rel), quote=True)
        return f'{match.group(1)}<a href="{href}">{match.group(2)}</a>{match.group(3)}'

    return _PRESENTED_LINE.sub(swap, answer_html)


# ---------------------------------------------------------------------------
# Overview tab: prompt x configuration table, summary files
# ---------------------------------------------------------------------------

def _pid_order(pid: str) -> Tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", pid)) or (0,)


def overview(parsed_root: Path, answers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Rows (one per prompt) and columns (one per configuration) of the web answers of one root.

    ``answers`` are the web answer chips of the answer scan (id, label, pid,
    source_name, url, prompt, elapsed_s).
    """
    stats = run_stats(parsed_root)
    columns: Dict[str, str] = {}
    rows: Dict[str, Dict[str, Any]] = {}
    for answer in answers:
        config = answer["label"].split("/", 1)[0]
        columns.setdefault(config, answer["source_name"])
        row = rows.setdefault(answer["pid"], {"pid": answer["pid"], "title": answer["prompt"], "cells": {}})
        stat = stats.get(answer["label"], {})
        row["cells"][config] = {
            "url": answer["url"], "is_reference": answer.get("is_reference", False),
            "time": human_duration(answer.get("elapsed_s")),
            "tool_calls": _count(stat, "tool_calls"),
            "files": _count(stat, "artifacts") + _count(stat, "sandbox_files"),
            "figures": _count(stat, "images"), "pages": _count(stat, "html_reports"),
            "incomplete": (stat.get("incomplete") or "").strip().lower() in ("1", "true", "yes"),
            "stop": (stat.get("stop_reasons_str") or "").strip(),
        }
    ordered = sorted(rows.values(), key=lambda r: (r["pid"][:2], _pid_order(r["pid"])))
    return {"columns": sorted(columns.items(), key=lambda item: item[1].casefold()), "rows": ordered,
            "n_answers": len(answers)}


_SUMMARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".svg", ".csv", ".md", ".json", ".pdf", ".txt"}


def summary_file(web_dir: Path, area: str, rel: str) -> Optional[Path]:
    """A file of the run summary (``area`` "summary") or the timing comparison ("timing"), else None."""
    rel = clean_member(rel)
    base = {"summary": web_dir / "parsed" / SUMMARY_DIRNAME, "timing": web_dir / TIMING_DIRNAME}.get(area)
    if base is None or not rel or PurePosixPath(rel).suffix.lower() not in _SUMMARY_SUFFIXES:
        return None
    target = base.joinpath(*rel.split("/"))
    return target if target.is_file() else None


def summary_tables(web_dir: Path) -> List[Dict[str, Any]]:
    """The data tables of the summary and the timing comparison, for the download list."""
    tables = []
    for area, base in (("summary", web_dir / "parsed" / SUMMARY_DIRNAME), ("timing", web_dir / TIMING_DIRNAME)):
        try:
            names = sorted(p.name for p in base.iterdir() if p.is_file() and p.suffix.lower() == ".csv")
        except OSError:
            continue
        for name in names:
            tables.append({"area": area, "name": name, "size_text": human_size((base / name).stat().st_size)})
    return tables


def timing_plots(web_dir: Path) -> List[str]:
    """Names of the pictures of the framework-versus-web timing comparison."""
    try:
        return sorted(p.name for p in (web_dir / TIMING_DIRNAME).iterdir()
                      if p.is_file() and p.suffix.lower() == ".png")
    except OSError:
        return []


def rewrite_links(markdown: str, url_for_target: Callable[[str], str]) -> str:
    """Replace the relative link targets of a markdown text by ``url_for_target(target)``.

    Absolute links, anchors and site paths are left alone.  When
    ``url_for_target`` returns an empty string (no page for that target) the
    link is dropped and its text kept, so the page shows no dead link.
    """
    def swap(match: "re.Match[str]") -> str:
        target = match.group(3).strip()
        if re.match(r"^[a-z][a-z0-9+.-]*:|^[/#]", target, re.IGNORECASE):
            return match.group(0)
        url = url_for_target(target)
        if not url:
            return match.group(2)
        return f"{match.group(1)}[{match.group(2)}]({url})"

    return re.sub(r"(!?)\[([^\]\n]*)\]\(([^)\s]+)\)", swap, markdown)
