"""Read-only views of published answers, verdicts, and final deliverables."""
from __future__ import annotations

import html
import json
import posixpath
import unicodedata
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

import markdown
from flask import Blueprint, Response, abort, redirect, render_template, request, send_file, url_for
from markupsafe import Markup

from archive_io import open_zip

from ._result_catalog import (ArchivePath, KINDS, build_catalog, catalog_runs,
                              query_results, resolve_run, prompt_from_result, read_json)

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


def _case_dir(source: str, case_id: str):
    _parts(case_id)
    directory = resolve_run(_root(source), case_id)
    if directory is None:
        abort(404)
    return directory


def _send_artifact(path, mimetype: str, as_attachment: bool = False):
    if not isinstance(path, ArchivePath):
        response = send_file(path, mimetype=mimetype, as_attachment=as_attachment)
    else:
        def chunks():
            with open_zip(path.archive) as archive:
                with archive.open(path.member) as member:
                    while block := member.read(64 * 1024):
                        yield block
        response = Response(chunks(), mimetype=mimetype)
        response.content_length = path.stat().st_size
        filename = path.name
        names = {"filename": filename}
        try:
            filename.encode("ascii")
        except UnicodeEncodeError:
            names = {"filename": unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode("ascii"),
                     "filename*": "UTF-8''" + quote(filename, safe="!#$&+-.^_`|~")}
        response.headers.set("Content-Disposition", "attachment" if as_attachment else "inline", **names)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


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
    manifest = data.get("manifest") or read_json(directory / "manifest.json")
    if not isinstance(manifest, dict):
        manifest = {}
    return {"verdict": verdict, "badge": _VERDICT_BADGES.get(verdict, "secondary"),
            "notes": notes, "prompt": str(data.get("request") or data.get("user_request") or manifest.get("user_request") or ""),
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


def _scientific_relative(parts):
    return (bool(parts) and (parts[0] == "final" or re.fullmatch(r"L1_call_\d+", parts[0]))
            and not any(part.startswith((".", "_")) for part in parts)
            and not any("tool_calls" in part or "run_history" in part for part in parts))


def _artifact(directory: Path, relative: str):
    parts = _parts(relative)
    if not _scientific_relative(parts):
        abort(404)
    path = directory.joinpath(*parts).resolve()
    if (not path.is_relative_to(directory) or not path.is_file()
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
        relative_path = unquote(parsed.path)
        if isinstance(self.document, ArchivePath):
            normalized = posixpath.normpath(posixpath.join(self.document.parent.member, relative_path))
            try:
                candidate = self.document.with_member(normalized)
            except ValueError:
                return None
        else:
            candidate = (self.document.parent / relative_path).resolve()
        if (not candidate.is_relative_to(self.directory) or not candidate.is_file()
                or candidate.suffix.lower() not in _FILE_SUFFIXES):
            return None
        if not _scientific_relative(candidate.relative_to(self.directory).parts):
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
    cases = []
    for run in catalog_runs(_root(source)):
        directory = run["directory"]
        metadata = _metadata(directory / "verdict.json", directory, run["title"])
        cases.append({**run, **metadata, "prompt": run["prompt"], "source": source,
                      "answer_head": _read(directory / "answer.md", directory).strip()[:240]})
    return cases


def _index(source: str):
    query = request.args.get("q", "").strip()
    catalog = build_catalog(_REPO_ROOT, _root(source), include_prompts=source == "benchmark")
    kind = request.args.get("kind") or next((key for key, value in catalog.items() if value["rows"]), "analysis")
    if kind not in KINDS:
        abort(404)
    selected = catalog[kind]
    rows = selected["rows"]
    if query:
        needle = query.casefold()
        rows = [row for row in rows if needle in (row["id"] + " " + row["title"] + " " + row["prompt"]).casefold()]
    for row in rows:
        for runs in row["runs"].values():
            for run in runs:
                metadata = _metadata(run["directory"] / "verdict.json", run["directory"], run["title"])
                run.update({"verdict": metadata["verdict"], "badge": metadata["badge"]})
                if run["batch"] is not None and run["verdict"] == "unknown":
                    run["verdict"] = "saved"
                run["url"] = url_for("results.detail", source=source, case_id=run["id"], batch=run["batch"])
    return render_template("results_index.html", rows=rows, source=source, sources=SOURCES,
                           query=query, kind=kind, kinds=KINDS, catalog=catalog,
                           modes=selected["modes"], run_count=selected["run_count"],
                           cost_plot=_cost_url(source, "cost_per_prompt.png") if kind == "analysis" else None,
                           cost_data=_cost_url(source, "cost_per_prompt.csv") if kind == "analysis" else None)


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
        final = directory
        roots = [path for path in directory.glob("L1_call_*") if path.is_dir()]
    else:
        roots = [final]
    def files_under(folder):
        for child in sorted(folder.iterdir()):
            if not _scientific_relative(child.relative_to(directory).parts):
                continue
            if child.is_dir():
                yield from files_under(child)
            elif child.suffix.lower() in _FILE_SUFFIXES:
                yield child
    for path in (path for root in roots for path in files_under(root)):
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
        group_answer = group_dir / "answer.md"
        if not group_answer.is_file():
            group_answer = group_dir / "l1_report.md"
        group_verdict = group_dir / "verdict.json"
        if not group_verdict.is_file():
            group_verdict = group_dir / "LD" / "verdict.json"
        group["answer"] = _answer(group_answer, directory, source, case_id)
        group["verdict"] = _verdict(group_verdict, directory)
        group["metadata"] = _metadata(group_verdict, directory)
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
    metadata = _metadata(directory / "verdict.json", directory, directory.name)
    query = query_results(directory)
    answer_path = directory / "answer.md"
    batch = None
    if query:
        batch = request.args.get("batch", default=query[0][1], type=int)
        selected = next((entry for entry in query if entry[1] == batch), None)
        if selected is None:
            abort(404)
        answer_path = selected[2]
        metadata["prompt"] = prompt_from_result(answer_path)
        if metadata["verdict"] == "unknown":
            metadata["verdict"] = "saved"
    return render_template(
        "result_detail.html", source=source, sources=SOURCES,
        title=directory.name + (f" · batch {batch}" if batch is not None else ""), metadata=metadata,
        answer=_answer(answer_path, directory, source, case_id),
        verdict=_verdict(directory / "verdict.json", directory),
        result_groups=_result_groups(directory, source, case_id),
        answer_url=url_for("results.document", source=source, case_id=case_id,
                           filename=answer_path.name),
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
    response = _send_artifact(path, mimetype=_MIME_TYPES[suffix], as_attachment=suffix not in _IMAGE_SUFFIXES)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@results_bp.get("/results/<source>/document/<path:case_id>/<filename>")
def document(source, case_id, filename):
    if filename not in {"answer.md", "verdict.json"} and not re.fullmatch(r"Q.+_result_batch\d+\.md", filename):
        abort(404)
    directory = _case_dir(source, case_id)
    path = (directory / filename).resolve()
    if path.parent != directory or not path.is_file():
        abort(404)
    response = _send_artifact(path, mimetype="text/plain")
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@results_bp.get("/results/<source>/cost/<filename>")
@results_bp.get("/results/<source>/cost/<path:case_id>/<filename>")
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
    response = _send_artifact(path, mimetype=_MIME_TYPES[suffix], as_attachment=suffix == ".csv")
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

