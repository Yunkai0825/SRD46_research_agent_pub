"""Read-only views of published answers, verdicts, and final deliverables."""
from __future__ import annotations

import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import markdown
from flask import Blueprint, abort, redirect, render_template, request, send_file, url_for
from markupsafe import Markup

results_bp = Blueprint("results", __name__)
_REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCES = {"benchmark": "Benchmark", "output": "Output"}
ROOTS = {"benchmark": _REPO_ROOT / "_benchmark", "output": _REPO_ROOT / "_output"}
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
_MIME_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
    ".csv": "text/csv", ".tsv": "text/tab-separated-values", ".json": "application/json",
    ".md": "text/markdown", ".txt": "text/plain", ".pdf": "application/pdf", ".svg": "image/svg+xml",
}
_FILE_SUFFIXES = set(_MIME_TYPES)


def _parts(value: str) -> tuple[str, ...]:
    if not value or any(character in value for character in ("\\", ":", "\0")):
        abort(404)
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        abort(404)
    return tuple(parts)


def _root(source: str) -> Path:
    if source not in ROOTS:
        abort(404)
    return ROOTS[source].resolve()


def _case_dir(source: str, case_id: str) -> Path:
    root = _root(source)
    parts = _parts(case_id)
    if len(parts) != 1 or parts[0].startswith(".") or parts[0] == "final":
        abort(404)
    directory = root.joinpath(*parts).resolve()
    if directory.parent != root or not directory.is_dir():
        abort(404)
    if not any((directory / name).is_file() for name in ("answer.md", "verdict.json")):
        abort(404)
    return directory


def _read(path: Path, directory: Path) -> str:
    if not path.resolve().is_relative_to(directory) or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _verdict(path: Path, directory: Path) -> str:
    text = _read(path, directory)
    if not text:
        return ""
    try:
        return json.dumps(json.loads(text), ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        return text


_VERDICT_BADGES = {
    "pass": "success", "partial": "warning", "skipped_some": "warning",
    "fail": "danger", "supported": "success", "contradicted": "danger",
    "inconclusive": "secondary", "timeout": "secondary", "unknown": "secondary",
}


def _metadata(path: Path, directory: Path, identifier: str = "") -> dict:
    try:
        data = json.loads(_read(path, directory))
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    verdict = str(data.get("verdict") or "unknown")
    status = str(data.get("status") or "").lower()
    reason = str(data.get("reason") or "").lower()
    if status in {"timeout", "timed_out"} or reason in {"timeout", "timed_out"}:
        verdict = "timeout"
    notes = data.get("notes") or []
    if not isinstance(notes, list):
        notes = [str(notes)]
    layer = identifier.split("_", 1)[0]
    return {"verdict": verdict, "badge": _VERDICT_BADGES.get(verdict, "secondary"),
            "notes": notes, "prompt": str(data.get("request") or ""),
            "purpose": str(data.get("purpose") or ""),
            "layer": layer if re.fullmatch(r"L\d+", layer) else ""}


def _cost_url(source: str, filename: str, case_id: str | None = None) -> str | None:
    if case_id is None and source != "benchmark":
        return None
    directory = _case_dir(source, case_id) if case_id else _root(source)
    path = directory / filename
    if not path.is_file() or path.resolve().parent != directory:
        return None
    return url_for("results.cost_file", source=source, filename=filename, case_id=case_id)


def _artifact(directory: Path, relative: str) -> Path:
    parts = _parts(relative)
    if parts[0] != "final":
        abort(404)
    path = directory.joinpath(*parts).resolve()
    if (not path.is_relative_to(directory / "final") or not path.is_file()
            or path.suffix.lower() not in _FILE_SUFFIXES):
        abort(404)
    return path


class _AnswerHTML(HTMLParser):
    """Retain document formatting and safe links in saved Markdown."""

    tags = {"p", "br", "hr", "h1", "h2", "h3", "h4", "h5", "h6", "strong",
            "b", "em", "i", "code", "pre", "blockquote", "ul", "ol", "li",
            "table", "thead", "tbody", "tr", "th", "td", "a", "img", "sub", "sup", "del"}
    void_tags = {"br", "hr", "img"}

    def __init__(self, source: str, case_id: str, directory: Path, document: Path):
        super().__init__(convert_charrefs=True)
        self.source, self.case_id = source, case_id
        self.directory, self.document = directory, document
        self.output: list[str] = []

    def _url(self, value: str, image: bool = False) -> str | None:
        try:
            parsed = urlsplit(value)
        except ValueError:
            return None
        if any(ord(character) < 32 for character in value):
            return None
        if parsed.scheme:
            return value if not image and parsed.scheme.lower() in {"https", "http", "mailto"} else None
        if parsed.netloc or parsed.path.startswith("/"):
            return None
        if not parsed.path:
            return value if not image and value.startswith("#") else None
        candidate = (self.document.parent / unquote(parsed.path)).resolve()
        final = self.directory / "final"
        if (not candidate.is_relative_to(final) or not candidate.is_file()
                or candidate.suffix.lower() not in _FILE_SUFFIXES):
            return None
        if image and candidate.suffix.lower() not in _IMAGE_SUFFIXES:
            return None
        relative = candidate.relative_to(self.directory).as_posix()
        return url_for("results.file", source=self.source, case_id=self.case_id, path=relative)

    def handle_starttag(self, tag, attrs):
        if tag not in self.tags:
            return
        allowed = []
        for name, value in attrs:
            if value is None:
                continue
            if (tag == "a" and name == "href") or (tag == "img" and name == "src"):
                value = self._url(value, image=tag == "img")
                if value is not None:
                    allowed.append((name, value))
            elif name == "title" or (tag == "img" and name == "alt"):
                allowed.append((name, value))
        if tag == "img" and not any(name == "src" for name, _ in allowed):
            return
        attributes = "".join(f' {name}="{html.escape(value, quote=True)}"' for name, value in allowed)
        self.output.append(f"<{tag}{attributes}>")

    def handle_endtag(self, tag):
        if tag in self.tags and tag not in self.void_tags:
            self.output.append(f"</{tag}>")

    def handle_data(self, data):
        self.output.append(html.escape(data))


def _answer(path: Path, directory: Path, source: str, case_id: str) -> Markup:
    text = _read(path, directory)
    parser = _AnswerHTML(source, case_id, directory, path)
    parser.feed(markdown.markdown(text, extensions=["tables", "fenced_code", "nl2br"]))
    parser.close()
    return Markup("".join(parser.output))


def _cases(source: str) -> list[dict]:
    root = _root(source)
    directories = set()
    if root.is_dir():
        for directory in root.iterdir():
            if not directory.is_dir() or directory.name.startswith(".") or directory.name == "final":
                continue
            if directory.resolve().parent != root:
                continue
            if any((directory / name).is_file() for name in ("answer.md", "verdict.json")):
                directories.add(directory.name)
    cases = []
    order = lambda name: [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", name)]
    for identifier in sorted(directories, key=order):
        directory = root / identifier
        metadata = _metadata(directory / "verdict.json", directory, identifier)
        cases.append({"source": source, "id": identifier, "title": identifier,
                      **metadata, "answer_head": _read(directory / "answer.md", directory).strip()[:240],
                      "result_count": sum(path.is_dir() for path in directory.glob("final/result_*"))})
    return cases



def _index(source: str):
    query = request.args.get("q", "").strip()
    cases = _cases(source)
    if query:
        cases = [case for case in cases if query.casefold() in case["title"].casefold()]
    return render_template("results_index.html", cases=cases, source=source,
                           sources=SOURCES, query=query,
                           cost_plot=_cost_url(source, "cost_per_prompt.png"),
                           cost_data=_cost_url(source, "cost_per_prompt.csv"))


@results_bp.get("/results/")
def index():
    return redirect(url_for("results.collection", source="benchmark"), code=302)


@results_bp.get("/results/<source>/")
def collection(source):
    _root(source)
    return _index(source)


_STAGE_LABELS = {"LC1": "LC1", "LC2": "LC2", "LC3": "LC3", "LD": "LD",
                 "solver": "Numerical results"}
_STAGE_ORDER = {"LC1": 0, "LC2": 1, "LC3": 2, "LD": 3, "solver": 4, "": 5}


def _result_groups(directory: Path, source: str, case_id: str) -> list[dict]:
    final = directory / "final"
    groups = {}
    if not final.is_dir():
        return []
    for path in sorted(final.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in _FILE_SUFFIXES:
            continue
        if not path.resolve().is_relative_to(final):
            continue
        parts = path.relative_to(final).parts
        group_name = parts[0] if len(parts) > 1 else ""
        group_dir = final / group_name
        group = groups.setdefault(group_name, {
            "title": group_name.replace("_", " ").title() if group_name else "Final deliverables",
            "directory": group_dir, "sections": {},
        })
        group_parts = path.relative_to(group_dir).parts
        stage = group_parts[0] if len(group_parts) > 1 and group_parts[0] in _STAGE_LABELS else ""
        section_dir = group_dir / stage
        section = group["sections"].setdefault(stage, {
            "title": _STAGE_LABELS.get(stage, "Final deliverables"),
            "directory": section_dir, "files": [],
        })
        relative = path.relative_to(directory).as_posix()
        size = path.stat().st_size
        section["files"].append({
            "path": path.relative_to(section_dir).as_posix(),
            "url": url_for("results.file", source=source, case_id=case_id, path=relative),
            "size": f"{size / 1024:,.1f} KB",
            "image": path.suffix.lower() in _IMAGE_SUFFIXES,
        })
    result_groups = []
    for group_name, group in sorted(groups.items()):
        group_dir = group.pop("directory")
        group["answer"] = _answer(group_dir / "answer.md", directory, source, case_id)
        group["verdict"] = _verdict(group_dir / "verdict.json", directory)
        group["metadata"] = _metadata(group_dir / "verdict.json", directory)
        sections = []
        for stage, section in sorted(group["sections"].items(), key=lambda item: _STAGE_ORDER[item[0]]):
            section_dir = section.pop("directory")
            # Root answers are already displayed once at the group level.
            section["answer"] = _answer(section_dir / "answer.md", directory, source, case_id) if stage else ""
            section["verdict"] = _verdict(section_dir / "verdict.json", directory) if stage else ""
            section["figures"] = [item for item in section["files"] if item["image"]]
            sections.append(section)
        group["documents"] = []
        for section in sections:
            if section["title"] == "Final deliverables":
                group["documents"] = [item for item in section["files"] if item["path"] in {"answer.md", "verdict.json"}]
                section["files"] = [item for item in section["files"] if item not in group["documents"]]
        group["figures"] = [item for section in sections for item in section["figures"]]
        group["sections"] = sections
        result_groups.append(group)
    return result_groups


@results_bp.get("/results/<source>/view/<path:case_id>")
def detail(source, case_id):
    directory = _case_dir(source, case_id)
    return render_template(
        "result_detail.html", source=source, sources=SOURCES,
        title=case_id, metadata=_metadata(directory / "verdict.json", directory, case_id),
        answer=_answer(directory / "answer.md", directory, source, case_id),
        verdict=_verdict(directory / "verdict.json", directory),
        result_groups=_result_groups(directory, source, case_id),
        answer_url=url_for("results.document", source=source, case_id=case_id, filename="answer.md"),
        verdict_url=(url_for("results.document", source=source, case_id=case_id, filename="verdict.json")
                     if (directory / "verdict.json").is_file() else None),
        cost_plot=_cost_url(source, "cost_distribution.png", case_id),
        cost_data=_cost_url(source, "cost_distribution.csv", case_id),
    )


@results_bp.get("/results/<source>/file/<path:case_id>")
def file(source, case_id):
    directory = _case_dir(source, case_id)
    path = _artifact(directory, request.args.get("path", ""))
    suffix = path.suffix.lower()
    response = send_file(path, mimetype=_MIME_TYPES[suffix], as_attachment=suffix not in _IMAGE_SUFFIXES)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@results_bp.get("/results/<source>/document/<case_id>/<filename>")
def document(source, case_id, filename):
    if filename not in {"answer.md", "verdict.json"}:
        abort(404)
    directory = _case_dir(source, case_id)
    path = (directory / filename).resolve()
    if path.parent != directory or not path.is_file():
        abort(404)
    response = send_file(path, mimetype="text/plain")
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@results_bp.get("/results/<source>/cost/<filename>")
@results_bp.get("/results/<source>/cost/<case_id>/<filename>")
def cost_file(source, filename, case_id=None):
    if case_id is None and source != "benchmark":
        abort(404)
    names = ({"cost_distribution.png", "cost_distribution.csv"} if case_id
             else {"cost_per_prompt.png", "cost_per_prompt.csv"})
    if filename not in names:
        abort(404)
    directory = _case_dir(source, case_id) if case_id else _root(source)
    path = (directory / filename).resolve()
    if path.parent != directory or not path.is_file():
        abort(404)
    suffix = path.suffix.lower()
    response = send_file(path, mimetype=_MIME_TYPES[suffix], as_attachment=suffix == ".csv")
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@results_bp.get("/analysis/")
@results_bp.get("/eval/")
def legacy_benchmarks():
    return redirect(url_for("results.collection", source="benchmark"), code=302)


@results_bp.get("/analysis/freeform/")
@results_bp.get("/eval/freeform/")
def legacy_output():
    return redirect(url_for("results.collection", source="output"), code=302)
