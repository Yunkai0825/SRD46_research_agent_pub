"""Answer sources and the reference-answer selection of the analysis results browser.

One benchmark prompt (``L1_6``, ``L2_3``, ``FF_1`` ...) can have answers from
three kinds of source; each answer has one id:

* ``bench:<label>``          a curated run under the Benchmark analysis root
* ``user:<label>``           a run under the active user's analysis roots
                             (``<model folder>/<run>`` or a direct run)
* ``web:<config>/<folder>``  a Claude-web reference answer under
                             ``_Claude_web_answers/parsed/<config>/<folder>/``

The reference answer chosen for a prompt is stored in
``_output/_answer_selection.json``::

    {"version": 1,
     "references": {"L1_6": {"answer": "user:Opus4.7/L1_6_20261030",
                             "chosen_by": "account-1",
                             "at": "2026-11-04T18:30:00+00:00"}}}

The browser writes only the active user's file; the Benchmark bucket's file
(if a curated default is ever shipped) is read as the fallback.  Reading never
writes.  Nothing here imports Flask: the route module builds the URLs.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from zip_images.output_zips.output_reader import OutputPath, output_path
from typing import Any, Dict, List, Optional, Tuple

SELECTION_FILENAME = "_answer_selection.json"
SELECTION_VERSION = 1
WEB_ANSWERS_DIRNAME = "_Claude_web_answers"
WEB_PARSED_DIRNAME = "parsed"
ANSWER_KINDS = ("bench", "user", "web")

_PID_RE = re.compile(r"^(L[1-4]_\d+|FF_\d+)(?![0-9])")
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
_MD_LINK_RE = re.compile(r"(!?\[[^\]]*\]\()([^)\s]+)(\))")


# ---------------------------------------------------------------------------
# Prompt ids and answer ids
# ---------------------------------------------------------------------------

def short_pid(text: Optional[str]) -> str:
    """``L1_6`` from a catalog key, a compact run name or a web answer folder name."""
    match = _PID_RE.match(text or "")
    return match.group(1) if match else ""


def valid_pid(text: Optional[str]) -> bool:
    return bool(text) and short_pid(text) == text


def _clean_parts(rest: str, min_parts: int, max_parts: int) -> Optional[List[str]]:
    if not rest or "\\" in rest or ":" in rest or "\x00" in rest:
        return None
    parts = rest.split("/")
    if not min_parts <= len(parts) <= max_parts:
        return None
    if any(not part or part in {".", ".."} or part.startswith("_") for part in parts):
        return None
    return parts


def parse_answer_id(answer_id: Any) -> Optional[Tuple[str, str]]:
    """``("user", "Opus4.7/L1_6_20261030")`` or None when the id is malformed."""
    if not isinstance(answer_id, str) or ":" not in answer_id:
        return None
    kind, rest = answer_id.split(":", 1)
    if kind not in ANSWER_KINDS:
        return None
    parts = _clean_parts(rest, 1, 4)
    if parts is None:
        return None
    if kind == "web" and len(parts) != 2:
        return None
    return kind, rest


# ---------------------------------------------------------------------------
# The per-bucket selection file
# ---------------------------------------------------------------------------

def selection_path(root: Path) -> Path:
    return (root if isinstance(root, OutputPath) else Path(root)) / SELECTION_FILENAME


def read_selection(root: Path) -> Dict[str, Any]:
    """The selection document of one bucket root; an empty one when absent or broken."""
    path = selection_path(root)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        doc = {}
    if not isinstance(doc, dict):
        doc = {}
    refs = doc.get("references")
    if not isinstance(refs, dict):
        refs = {}
    clean: Dict[str, Dict[str, Any]] = {}
    for pid, entry in refs.items():
        if not valid_pid(pid) or not isinstance(entry, dict):
            continue
        if parse_answer_id(entry.get("answer")) is None:
            continue
        clean[pid] = dict(entry)
    return {"version": SELECTION_VERSION, "references": clean}


def set_reference(root: Path, pid: str, answer_id: Optional[str], user: str,
                  note: str = "") -> Optional[Dict[str, Any]]:
    """Store (or with ``answer_id=None`` clear) the reference of ``pid`` in one bucket.

    Returns the stored entry, or None after a clear.  The file is rewritten
    atomically (temporary file + replace) and only the one entry changes.
    """
    if not valid_pid(pid):
        raise ValueError(f"not a prompt id: {pid!r}")
    if answer_id is not None and parse_answer_id(answer_id) is None:
        raise ValueError(f"not an answer id: {answer_id!r}")
    root = Path(root)
    doc = read_selection(root)
    entry: Optional[Dict[str, Any]] = None
    if answer_id is None:
        doc["references"].pop(pid, None)
    else:
        entry = {
            "answer": answer_id,
            "chosen_by": user or "",
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        if note:
            entry["note"] = str(note)[:500]
        doc["references"][pid] = entry
    doc["references"] = dict(sorted(doc["references"].items()))
    root.mkdir(parents=True, exist_ok=True)
    path = selection_path(root)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return entry


def merged_references(default_roots: List[Path], own_root: Path) -> Dict[str, Dict[str, Any]]:
    """pid -> entry, the user's own file winning over the defaults.

    Each entry carries ``own`` (True when it comes from ``own_root``) and
    ``source_file`` (the file it was read from).
    """
    merged: Dict[str, Dict[str, Any]] = {}
    for root in list(default_roots) + [own_root]:
        own = Path(root) == Path(own_root)
        for pid, entry in read_selection(root)["references"].items():
            item = dict(entry)
            item["own"] = own
            item["source_file"] = str(selection_path(root))
            merged[pid] = item
    return merged


# ---------------------------------------------------------------------------
# Claude-web reference answers
# ---------------------------------------------------------------------------

def web_parsed_dir(analysis_root: Path) -> Path:
    return output_path(analysis_root) / WEB_ANSWERS_DIRNAME / WEB_PARSED_DIRNAME


def web_configs(parsed_root: Path) -> List[str]:
    """Export configurations (``Opus4_7_high`` ...): the non-underscore folders of ``parsed/``."""
    try:
        return sorted(p.name for p in output_path(parsed_root).iterdir()
                      if p.is_dir() and not p.name.startswith("_"))
    except OSError:
        return []


def web_answer_dirs(parsed_root: Path, config: str) -> List[Path]:
    """The answer folders of one configuration (each holds ``final_answer.md``)."""
    base = output_path(parsed_root) / config
    try:
        return sorted(p for p in base.iterdir()
                      if p.is_dir() and not p.name.startswith("_") and (p / "final_answer.md").is_file())
    except OSError:
        return []


def web_source_name(config: str) -> str:
    """``Opus4_7_high`` -> ``web Opus 4.7 high``."""
    text = config.replace("_", " ")
    text = re.sub(r"(?<=\d) (?=\d)", ".", text)          # 4 7 -> 4.7
    text = re.sub(r"(?<=[A-Za-z])(?=\d)", " ", text)     # Opus4.7 -> Opus 4.7
    return "web " + text


def _parse_iso(text: Any) -> Optional[datetime]:
    if not isinstance(text, str) or not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def web_front_matter(folder: Path, limit: int = 4000) -> Dict[str, Any]:
    """Front matter of ``final_answer.md`` plus what the folder holds.

    Keys: pid, title, model, effort, run, prompt, conversation, started,
    finished, elapsed_s, stop_reason, images (file names), html_files.
    """
    folder = output_path(folder)
    meta: Dict[str, Any] = {
        "pid": short_pid(folder.name),
        "title": folder.name[len(short_pid(folder.name)):].strip() if short_pid(folder.name) else folder.name,
        "model": "", "effort": "", "run": "", "prompt": "", "conversation": "",
        "started": "", "finished": "", "elapsed_s": None, "stop_reason": "",
        "images": [], "html_files": [],
    }
    try:
        head = (folder / "final_answer.md").read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        head = ""
    if head.startswith("---"):
        end = head.find("\n---", 3)
        if end > 0:
            for raw in head[3:end].splitlines():
                if ":" not in raw:
                    continue
                key, value = raw.split(":", 1)
                key, value = key.strip(), value.strip().strip('"')
                if key in meta and key not in ("pid", "title", "images", "html_files", "elapsed_s"):
                    meta[key] = value
    started, finished = _parse_iso(meta["started"]), _parse_iso(meta["finished"])
    if started and finished and finished >= started:
        meta["elapsed_s"] = (finished - started).total_seconds()
    try:
        for p in sorted(folder.iterdir()):
            if not p.is_file():
                continue
            if p.suffix.lower() in _IMAGE_SUFFIXES:
                meta["images"].append(p.name)
            elif p.suffix.lower() in {".html", ".htm"}:
                meta["html_files"].append(p.name)
    except OSError:
        pass
    return meta


def strip_front_matter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            rest = text[end + 4:]
            return rest.lstrip("\r\n")
    return text


def rewrite_relative_links(markdown: str, folder: Path, url_for_file) -> str:
    """Point ``](name.png)`` links at files that exist in ``folder`` to ``url_for_file(name)``."""
    folder = output_path(folder)

    def repl(match: "re.Match[str]") -> str:
        target = match.group(2)
        if "://" in target or target.startswith(("/", "#", "data:")):
            return match.group(0)
        name = target.split("#", 1)[0]
        if "/" in name or "\\" in name or name in {".", ".."}:
            return match.group(0)
        if not (folder / name).is_file():
            return match.group(0)
        return match.group(1) + url_for_file(name) + match.group(3)

    return _MD_LINK_RE.sub(repl, markdown)


# ---------------------------------------------------------------------------
# Matrix rows
# ---------------------------------------------------------------------------

def catalog_rows(meta: Dict[str, Dict[str, str]]) -> List[Dict[str, Any]]:
    """One row per catalog prompt in catalog order: pid, key, layer, title, prompt."""
    rows: List[Dict[str, Any]] = []
    seen: Dict[str, Dict[str, Any]] = {}
    for key, info in meta.items():
        pid = short_pid(key)
        if not pid:
            continue
        title = key[len(pid):].strip("_").replace("_", " ")
        if pid in seen:
            seen[pid]["title"] += " / " + title
            continue
        row = {"pid": pid, "key": key, "layer": info.get("layer", ""), "title": title,
               "prompt": info.get("prompt", "")}
        seen[pid] = row
        rows.append(row)
    return rows


def chip_text(label: str) -> str:
    """Short chip text for a run: its date suffix (``1030``), else the name after the prompt id."""
    name = label.rsplit("/", 1)[-1]
    match = re.search(r"_(\d{4})(\d{4})$", name)
    if match:
        return match.group(2)
    rest = name[len(short_pid(name)):].strip("_") or name
    return rest if len(rest) <= 14 else rest[:13] + "…"
