"""Excerpts of an analysis run's answer: load the run's excerpt file, highlight the answer (eval mode).

The excerpts of a run live in its own output folder, ``<run>/_eval/excerpts.json``; the editor of
the run page writes that file through ``apply_edit``.  Highlighting works on the rendered answer:
segments are located in the page's text with whitespace collapsed, so one quoted statement can
cross ``<strong>`` and list tags, and each stretch of text is wrapped on its own so the markup
stays valid.  No Flask import.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import threading
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

EVAL_DIRNAME = "_eval"
EXCERPT_FILENAME = "excerpts.json"
_TAG = re.compile(r"(<[^>]+>)")
MARK_CLASS = {"✓": "ok", "≈": "near", "✗": "bad", "○": "open", "": "plain"}
MARK_ORDER = ("✓", "≈", "✗", "○")
COVERAGE_LABEL = {"covered": "covered", "partial": "partly covered", "none": "not excerpted"}


def excerpt_path(run_dir: Path) -> Path:
    """Where a run's excerpts are stored: ``<run>/_eval/excerpts.json``."""
    return (run_dir if hasattr(run_dir, 'archives') else Path(run_dir)) / EVAL_DIRNAME / EXCERPT_FILENAME


def editable_run(run_dir: Path) -> bool:
    """Editing needs an unpacked answer and ordinary files within its run folder."""
    root = getattr(run_dir, 'local', run_dir)
    try:
        if not root.is_dir() or not (root / 'answer.md').is_file():
            return False
        for path in (root, root / 'answer.md', root / EVAL_DIRNAME, root / EVAL_DIRNAME / EXCERPT_FILENAME):
            if path.is_symlink() or (path.exists() and getattr(path.lstat(), 'st_file_attributes', 0) & 0x400):
                return False
            path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def find_run(run_dir: Path) -> Optional[Dict[str, Any]]:
    """The excerpt entry of a run folder, or None when it has none (a broken file counts as none).

    The file holds one object: {"case", "note", "answer_md5", "excerpts": [...], "core": [...]}."""
    path = excerpt_path(run_dir)
    if not path.is_file():
        return None
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(entry, dict) or not isinstance(entry.get("excerpts"), list):
        return None
    return entry


def inline_html(text: str) -> str:
    """Panel-row notation to HTML: **bold**, ^{sup}, _{sub}.  Everything else is escaped."""
    out = html.escape(text or "", quote=False)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"\^\{([^}]*)\}", r"<sup>\1</sup>", out)
    return re.sub(r"_\{([^}]*)\}", r"<sub>\1</sub>", out)


def _collapse(text: str) -> Tuple[str, List[int]]:
    """Text with whitespace runs reduced to one space, plus each kept char's raw index."""
    kept: List[str] = []
    raw: List[int] = []
    previous_space = True
    for index, ch in enumerate(text):
        if ch.isspace():
            if previous_space:
                continue
            kept.append(" ")
            previous_space = True
        else:
            kept.append(ch)
            previous_space = False
        raw.append(index)
    return "".join(kept), raw


def _locate(collapsed: str, segment: Any, cursor: int = 0) -> Optional[Tuple[int, int]]:
    """Span of one segment, a string or {"text", "in"} ("in" is a longer string that makes
    a short quote unambiguous).  Searches from ``cursor`` first so a statement's parts
    follow each other, then from the start."""
    if isinstance(segment, dict):
        text = " ".join(str(segment.get("text", "")).split())
        anchor = " ".join(str(segment.get("in", text)).split())
    else:
        text = anchor = " ".join(str(segment).split())
    if not text:
        return None
    where = collapsed.find(anchor, cursor)
    if where < 0:
        where = collapsed.find(anchor)
    if where < 0:
        return None
    inner = anchor.find(text)
    if inner < 0:
        return None
    start = where + inner
    return start, start + len(text)


def annotate(document_html: str, spans: Iterable[Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
    """Wrap every located segment of ``spans`` in the rendered HTML.

    A span is {"id", "layer": "excerpt"|"core", "cls", "chip", "segments"}.  Returns the new
    HTML and {"missing": {span id: [segment text]}, "excerpted_chars", "total_chars"}.
    """
    spans = list(spans)
    tokens = _TAG.split(document_html or "")
    pieces: List[str] = []
    token_range: List[Optional[Tuple[int, int]]] = []
    length = 0
    for index, token in enumerate(tokens):
        if index % 2:
            token_range.append(None)
            continue
        text = html.unescape(token)
        pieces.append(text)
        token_range.append((length, length + len(text)))
        length += len(text)
    plain = "".join(pieces)
    collapsed, raw = _collapse(plain)

    owners: List[List[int]] = [[] for _ in plain]
    starts: Dict[int, List[int]] = {}
    missing: Dict[str, List[str]] = {}
    for span_index, span in enumerate(spans):
        cursor = 0
        first = True
        for segment in span.get("segments") or []:
            found = _locate(collapsed, segment, cursor)
            if found is None:
                text = segment.get("text") if isinstance(segment, dict) else segment
                missing.setdefault(str(span.get("id")), []).append(str(text))
                continue
            cursor = found[1]
            raw_start, raw_end = raw[found[0]], raw[found[1] - 1] + 1
            for at in range(raw_start, raw_end):
                owners[at].append(span_index)
            if first and span.get("chip"):
                starts.setdefault(raw_start, []).append(span_index)
                first = False

    def is_excerpt(i: int) -> bool:
        return spans[i].get("layer") == "excerpt"

    excerpted = sum(1 for chars in owners if any(is_excerpt(i) for i in chars))
    out: List[str] = []
    for index, token in enumerate(tokens):
        if index % 2:
            out.append(token)
            continue
        token_span = token_range[index]
        if token_span is None or token_span[0] == token_span[1]:
            out.append(token)
            continue
        if not any(owners[token_span[0]:token_span[1]]) and not any(
                at in starts for at in range(*token_span)):
            out.append(token)
            continue
        at = token_span[0]
        while at < token_span[1]:
            current = owners[at]
            stop = at + 1
            while stop < token_span[1] and owners[stop] == current and stop not in starts:
                stop += 1
            for chip_owner in starts.get(at, []):
                span = spans[chip_owner]
                out.append(f'<span class="xm-chip xm-{span.get("cls", "plain")}" '
                           f'data-x="{html.escape(str(span.get("id")))}">{html.escape(str(span.get("chip")))}</span>')
            chunk = html.escape(plain[at:stop], quote=False)
            if current:
                out.append(_mark_open(spans, current) + chunk + "</mark>")
            else:
                out.append(chunk)
            at = stop
    return "".join(out), {
        "missing": missing,
        "excerpted_chars": excerpted,
        "total_chars": len(plain),
    }


def _mark_open(spans: List[Dict[str, Any]], owners: List[int]) -> str:
    excerpts = [spans[i] for i in owners if spans[i].get("layer") == "excerpt"]
    cores = [spans[i] for i in owners if spans[i].get("layer") == "core"]
    classes = ["xm"]
    if excerpts:
        classes += ["xm-e", f"xm-{excerpts[0].get('cls', 'plain')}"]
    if cores:
        classes.append("xm-c")
    ids = " ".join(html.escape(str(spans[i].get("id"))) for i in owners)
    return f'<mark class="{" ".join(classes)}" data-x="{ids}">'


def eval_view(answer_bytes: bytes, answer_html: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    """Everything the eval panel renders for one run."""
    excerpts = [dict(row) for row in entry.get("excerpts") or []]
    core = [dict(row) for row in entry.get("core") or []]
    spans: List[Dict[str, Any]] = []
    for row in excerpts:
        row["cls"] = MARK_CLASS.get(row.get("mark", ""), "plain")
        row["statement_html"] = inline_html(row.get("statement", ""))
        row["note_html"] = inline_html(row.get("note", ""))
        chip = str(row.get("n")) if row.get("source") == "panel" else f"t{row.get('n')}"
        row["chip"] = chip
        spans.append({"id": row["id"], "layer": "excerpt", "cls": row["cls"], "chip": chip,
                      "segments": row.get("segments")})
    for row in core:
        spans.append({"id": row["id"], "layer": "core", "segments": row.get("segments")})
    marked_html, result = annotate(answer_html, spans)
    for row in excerpts:
        row["missing"] = result["missing"].get(row["id"], [])
    for row in core:
        row["missing"] = result["missing"].get(row["id"], [])
        row["coverage_label"] = COVERAGE_LABEL.get(row.get("coverage"), row.get("coverage", ""))
    panel_rows = [row for row in excerpts if row.get("source") == "panel"]
    expected = entry.get("answer_md5", "")
    actual = hashlib.md5(answer_bytes or b"").hexdigest()
    return {
        "html": marked_html,
        "excerpts": excerpts,
        "core": core,
        "case": entry.get("case", ""),
        "note": entry.get("note", ""),
        "mark_counts": {m: sum(1 for r in panel_rows if r.get("mark") == m) for m in MARK_ORDER},
        "has_marks": any(r.get("mark") in MARK_ORDER for r in panel_rows),
        "reason_rows": sum(1 for r in panel_rows if r.get("kind") == "reason"),
        "panel_rows": len(panel_rows),
        "coverage_counts": {key: sum(1 for r in core if r.get("coverage") == key) for key in COVERAGE_LABEL},
        "excerpted_pct": round(100 * result["excerpted_chars"] / result["total_chars"]) if result["total_chars"] else 0,
        "missing_count": sum(len(v) for v in result["missing"].values()),
        "answer_changed": bool(expected) and expected != actual,
        "editor_rows": [_editor_row(row) for row in excerpts],
        "kinds": sorted({DEFAULT_KIND, "reason", "number"} | {str(r.get("kind")) for r in excerpts if r.get("kind")}),
    }


# ---------------------------------------------------------------------------
# Editing: one row is created, changed or deleted per request, and the whole file is
# rewritten.  A part chosen in the page arrives as offsets into the answer's collapsed text
# (the same text ``annotate`` searches) together with the selected text, and is stored as a
# segment that ``_locate`` finds at exactly that place: the bare text when that is enough,
# otherwise {"text", "in"} with the shortest surrounding stretch that makes it unambiguous.
# ---------------------------------------------------------------------------
DEFAULT_KIND = "claim"
TEXT_FIELDS = ("fig", "kind", "statement", "note", "verbatim_diff")
PART_JOIN = " … "
_EDIT_LOCK = threading.Lock()


class EditError(ValueError):
    """An edit that cannot be applied; ``status`` is the HTTP status the route answers with."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _segment_text(segment: Any) -> str:
    text = segment.get("text", "") if isinstance(segment, dict) else segment
    return " ".join(str(text).split())


def _editor_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """The stored fields of a row, as the page's editor needs them."""
    return {
        "id": row.get("id"),
        "fig": row.get("fig", ""),
        "badge": list(row.get("badge") or []),
        "kind": row.get("kind", ""),
        "mark": row.get("mark", ""),
        "statement": row.get("statement", ""),
        "note": row.get("note", ""),
        "verbatim_diff": row.get("verbatim_diff", ""),
        "parts": [_segment_text(s) for s in row.get("segments") or []],
        "missing": [" ".join(str(text).split()) for text in row.get("missing") or []],
    }


def file_version(run_dir: Path) -> str:
    """md5 of the stored excerpt file, "" when there is none.  An edit names the version it
    was made on, so a second tab or another person cannot overwrite a newer file unseen."""
    try:
        return hashlib.md5(excerpt_path(run_dir).read_bytes()).hexdigest()
    except OSError:
        return ""


def answer_text(answer_html: str) -> str:
    """The rendered answer's text with whitespace collapsed: the text segments are located in."""
    tokens = _TAG.split(answer_html or "")
    return _collapse("".join(html.unescape(t) for i, t in enumerate(tokens) if not i % 2))[0]


def _selected_span(collapsed: str, part: Dict[str, Any]) -> Tuple[int, int]:
    """Span of a part chosen in the page: the occurrence of its text nearest the given offset
    (the offset alone decides between repeats of the same words)."""
    text = " ".join(str(part.get("text", "")).split())
    if not text:
        raise EditError("An empty selection cannot be a part.")
    try:
        start = int(part.get("start", 0))
    except (TypeError, ValueError):
        raise EditError("A part's offset must be a number.")
    hits: List[int] = []
    at = collapsed.find(text)
    while at >= 0:
        hits.append(at)
        at = collapsed.find(text, at + 1)
    if not hits:
        raise EditError(f"The selected text is not in this answer: {text[:80]}")
    begin = min(hits, key=lambda hit: abs(hit - start))
    return begin, begin + len(text)


def _segment_at(collapsed: str, start: int, end: int, cursor: int) -> Any:
    """The shortest segment that ``_locate`` (searching from ``cursor``) finds at start:end."""
    text = collapsed[start:end]
    if _locate(collapsed, text, cursor) == (start, end):
        return text
    for match in re.finditer(r"\S+", collapsed[end:]):
        segment = {"text": text, "in": collapsed[start:end + match.end()]}
        if _locate(collapsed, segment, cursor) == (start, end):
            return segment
    for match in reversed(list(re.finditer(r"\S+", collapsed[:start]))):
        segment = {"text": text, "in": collapsed[match.start():end]}
        if _locate(collapsed, segment, cursor) == (start, end):
            return segment
    raise EditError(f"This passage cannot be told apart from its repeats: {text[:80]}")


def _positions(collapsed: str, segments: List[Any]) -> List[Optional[Tuple[int, int]]]:
    """Where ``annotate`` finds each segment of one row (None for a segment it misses)."""
    found: List[Optional[Tuple[int, int]]] = []
    cursor = 0
    for segment in segments:
        span = _locate(collapsed, segment, cursor)
        found.append(span)
        if span is not None:
            cursor = span[1]
    return found


def _rebuild_segments(collapsed: str, old: List[Any], parts: List[Any]) -> List[Any]:
    """The segments of a row after its parts were edited.

    ``parts`` lists {"keep": i} for a stored segment and {"start", "text"} for a new
    selection.  Found parts are stored in the order they appear in the answer; a stored
    segment that is not found in this answer is kept as it is, at the end."""
    old_spans = _positions(collapsed, old)
    wanted: List[Tuple[Optional[Tuple[int, int]], Any]] = []
    for part in parts:
        if not isinstance(part, dict):
            raise EditError("Each part must be an object.")
        if "keep" in part:
            try:
                index = int(part["keep"])
            except (TypeError, ValueError):
                raise EditError("A kept part must name a stored part by its number.")
            if not 0 <= index < len(old):
                raise EditError("A kept part names a part this row does not have.")
            wanted.append((old_spans[index], old[index]))
        else:
            wanted.append((_selected_span(collapsed, part), None))
    found = sorted({span: original for span, original in reversed(wanted) if span is not None}.items())
    segments: List[Any] = []
    cursor = 0
    for span, original in found:
        if original is not None and _locate(collapsed, original, cursor) == span:
            segments.append(original)
        else:
            segments.append(_segment_at(collapsed, span[0], span[1], cursor))
        cursor = span[1]
    return segments + [original for span, original in wanted if span is None]


def _joined(segments: List[Any]) -> str:
    return PART_JOIN.join(_segment_text(s) for s in segments)


def _find_row(rows: List[Dict[str, Any]], row_id: Any) -> Dict[str, Any]:
    for row in rows:
        if row.get("id") == row_id:
            return row
    raise EditError(f"No excerpt row {row_id!r} in this run.", 404)


def _new_row(entry: Dict[str, Any]) -> Dict[str, Any]:
    taken = {str(r.get("id")) for r in (entry.get("excerpts") or []) + (entry.get("core") or [])}
    number = 1 + max([int(i[1:]) for i in taken if re.fullmatch(r"e\d+", i)] or [0])
    while f"e{number}" in taken:
        number += 1
    panel_numbers = [r.get("n") for r in entry["excerpts"] if r.get("source") == "panel" and isinstance(r.get("n"), int)]
    return {"id": f"e{number}", "fig": "", "n": 1 + max(panel_numbers or [0]), "badge": [], "mark": "",
            "kind": DEFAULT_KIND, "statement": "", "note": "", "segments": [], "verbatim_diff": "", "source": "panel"}


def _set_fields(row: Dict[str, Any], fields: Any) -> None:
    if not isinstance(fields, dict):
        raise EditError("The row's fields must be an object.")
    for key in TEXT_FIELDS:
        if key in fields:
            row[key] = str(fields[key] or "").strip()
    if "mark" in fields:
        mark = str(fields["mark"] or "").strip()
        if mark not in MARK_CLASS:
            raise EditError(f"Unknown mark {mark!r}; use one of ✓ ≈ ✗ ○ or none.")
        row["mark"] = mark
    if "badge" in fields:
        badge = fields["badge"]
        items = badge.split(",") if isinstance(badge, str) else badge
        if not isinstance(items, list):
            raise EditError("The sub-label must be text or a list.")
        row["badge"] = [str(item).strip() for item in items if str(item).strip()]
    if not row.get("kind"):
        row["kind"] = DEFAULT_KIND


def _all_found(collapsed: str, entry: Dict[str, Any]) -> bool:
    rows = (entry.get("excerpts") or []) + (entry.get("core") or [])
    return all(span is not None for row in rows for span in _positions(collapsed, row.get("segments") or []))


def _write_entry(path: Path, entry: Dict[str, Any]) -> None:
    path = getattr(path, 'local', path)
    if not editable_run(path.parent.parent):
        raise EditError('Unpack the run before editing; linked output paths cannot be edited.', 403)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.excerpts-', suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(json.dumps(entry, ensure_ascii=False, indent=1) + '\n')
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def apply_edit(run_dir: Path, answer_bytes: bytes, answer_html: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """``_apply_edit`` under a lock, so two requests cannot both pass the version check."""
    with _EDIT_LOCK:
        return _apply_edit(run_dir, answer_bytes, answer_html, body)


def _apply_edit(run_dir: Path, answer_bytes: bytes, answer_html: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """Apply one edit to ``<run>/_eval/excerpts.json`` and write the file (created when missing).

    ``body``: {"action": "create"|"update"|"delete", "version": file_version as the page saw it,
    "id": row id (update, delete), "row": {field: value}, "parts": [...] (create; update when
    the parts change)}.  The statement follows the parts while it is empty or still the parts
    joined with " … "; a statement written by hand is kept.  ``answer_md5`` is set to the
    current answer once every stored segment is found in it.  Returns {"id", "version"}."""
    if str(body.get("version") or "") != file_version(run_dir):
        raise EditError("The excerpt file changed since this page was loaded. Reload the page and edit again.", 409)
    path = excerpt_path(run_dir)
    if path.is_file():
        entry = find_run(run_dir)
        if entry is None:
            raise EditError(f"{EVAL_DIRNAME}/{EXCERPT_FILENAME} of this run is not a readable excerpt file.", 409)
    else:
        entry = {"case": "", "note": "", "answer_md5": "", "excerpts": [], "core": []}
    rows: List[Dict[str, Any]] = entry["excerpts"]
    collapsed = answer_text(answer_html)
    action = body.get("action")
    parts = body.get("parts")
    if parts is not None and not isinstance(parts, list):
        raise EditError("The parts must be a list.")
    if action == "delete":
        row = _find_row(rows, body.get("id"))
        rows.remove(row)
    elif action in ("create", "update"):
        if action == "create":
            row = _new_row(entry)
            if not parts:
                raise EditError("Select a passage of the answer for the new excerpt first.")
        else:
            row = _find_row(rows, body.get("id"))
        parts_before = _joined(row.get("segments") or [])
        _set_fields(row, body.get("row") or {})
        if parts is not None:
            if not parts:
                raise EditError("An excerpt needs at least one part; delete the row instead.")
            row["segments"] = _rebuild_segments(collapsed, list(row.get("segments") or []), parts)
            if row.get("statement") == parts_before:
                row["statement"] = ""
        if not row.get("statement"):
            row["statement"] = _joined(row.get("segments") or [])
        if action == "create":
            rows.append(row)
    else:
        raise EditError("The action must be create, update or delete.")
    if not entry.get("answer_md5") or _all_found(collapsed, entry):
        entry["answer_md5"] = hashlib.md5(answer_bytes or b"").hexdigest()
    _write_entry(path, entry)
    return {"id": row.get("id"), "version": file_version(run_dir)}
