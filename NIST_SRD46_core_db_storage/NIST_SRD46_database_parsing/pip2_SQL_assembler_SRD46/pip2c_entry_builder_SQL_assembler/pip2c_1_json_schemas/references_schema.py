"""
ReferencesEntry schema - shared by ligand and metal-ligand complex entries.

This dataclass models the references block containing literature citations,
authors, and footnotes linked to SRD46 database entries.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from ._utils import MissingFieldTracker, DEFAULT_MISSING_TRACKER, _is_empty


@dataclass
class ReferencesEntry:
    """References block shared by ligand and metal-ligand complex entries."""
    
    @dataclass
    class LiteratureAltRef:
        """Alternative literature reference."""
        literature_alt_id: int
        shortcut: Optional[str] = None
        citation: Optional[str] = None

    @dataclass
    class AuthorRef:
        """Author reference."""
        author_id: int
        name: Optional[str] = None

    @dataclass
    class FootnoteRef:
        """Footnote reference."""
        footnote_id: str
        shortcut: Optional[str] = None
        text: Optional[str] = None

    @dataclass
    class LiteratureRef:
        """Primary literature reference."""
        literature_id: int
        paper_id: Optional[int] = None
        year: Optional[int] = None
        issue: Optional[int] = None
        page: Optional[int] = None
        paper_name: Optional[str] = None

    literature_alt: List['ReferencesEntry.LiteratureAltRef'] = field(default_factory=list)
    literature: List['ReferencesEntry.LiteratureRef'] = field(default_factory=list)
    authors: List['ReferencesEntry.AuthorRef'] = field(default_factory=list)
    footnotes: List['ReferencesEntry.FootnoteRef'] = field(default_factory=list)
    reference_ids: List[Union[int, str]] = field(default_factory=list)


# =============================================================================
# Builder functions
# =============================================================================

def create_references_entry_from_tables(
    vlm_id: int,
    tables: Dict[str, List[Dict[str, Any]]],
    tracker: MissingFieldTracker | None = None,
) -> ReferencesEntry:
    """Build a ReferencesEntry by joining verkn_ligand_metal_literature with literature,
    authors (via verk_literature_author), and footnotes.

    Inputs
    - vlm_id: verkn_ligand_metalID to resolve
    - tables: dict with keys like:
        'verkn_ligand_metal_literature', 'literature', 'literature_alt', 'paper', 'author', 'footnote', 'verk_literature_author'
      Each maps to a list of row dicts.
    """
    tracker = tracker or DEFAULT_MISSING_TRACKER

    def _get(row: Dict[str, Any], keys: List[str]) -> Any:
        for k in keys:
            if k in row and str(row[k]).strip() != "":
                return row[k]
        # tolerant: case-insensitive lookup
        lower = {kk.lower(): vv for kk, vv in row.items()}
        for k in keys:
            lk = k.lower()
            if lk in lower and str(lower[lk]).strip() != "":
                return lower[lk]
        return None

    def _rows(name: str) -> List[Dict[str, Any]]:
        return list(tables.get(name, []) or [])

    vlit_rows = []
    # Combine standard and verbose (_sic) link tables
    for r in _rows("verkn_ligand_metal_literature") + _rows("verkn_ligand_metal_literature_sic"):
        rid = _get(r, ["verkn_ligand_metalID", "verkn_ligand_metalNr", "vlm_id", "vlm", "verknID"])  # tolerant keys
        try:
            if rid is not None and int(str(rid)) == int(vlm_id):
                vlit_rows.append(r)
        except Exception:
            continue

    # Index helpers
    lit_by_id: Dict[str, Dict[str, Any]] = {}
    for r in _rows("literature"):
        lid = _get(r, ["literatureID", "literatureNr", "literature_id"])  # normalize to str
        if lid is not None:
            lit_by_id[str(lid)] = r

    paper_by_id: Dict[str, Dict[str, Any]] = {}
    for r in _rows("paper"):
        pid = _get(r, ["paperID", "paperNr", "paper_id"])  # normalize to str
        if pid is not None:
            paper_by_id[str(pid)] = r

    author_by_id: Dict[str, Dict[str, Any]] = {}
    for r in _rows("author"):
        aid = _get(r, ["authorID", "authorNr", "author_id"])  # normalize to str
        if aid is not None:
            author_by_id[str(aid)] = r

    foot_by_id: Dict[str, Dict[str, Any]] = {}
    for r in _rows("footnote"):
        fid = _get(r, ["footnoteID", "footnoteNr", "footnote_id"])  # normalize to str
        if fid is not None:
            foot_by_id[str(fid)] = r

    # Index literature_alt for details
    alt_by_id: Dict[str, Dict[str, Any]] = {}
    for r in _rows("literature_alt"):
        laid = _get(r, ["literature_altID", "literature_altNr", "literature_alt_id"])  # normalize to str
        if laid is not None:
            alt_by_id[str(laid)] = r

    # Map literature -> author links
    lit_to_authors: Dict[str, List[str]] = {}
    for r in _rows("verk_literature_author"):
        lid = _get(r, ["literatureID", "literatureNr", "literature_id"])
        aid = _get(r, ["authorID", "authorNr", "author_id"])
        if lid is None or aid is None:
            continue
        lit_to_authors.setdefault(str(lid), []).append(str(aid))

    # Build outputs de-duped
    literature_out: Dict[str, ReferencesEntry.LiteratureRef] = {}
    authors_out: Dict[str, ReferencesEntry.AuthorRef] = {}
    footnotes_out: Dict[str, ReferencesEntry.FootnoteRef] = {}

    for link in vlit_rows:
        lid = _get(link, ["literatureID", "literatureNr", "literature_id"])  # literature ref
        if lid is None:
            tracker.mark_empty("ReferencesEntry", "literature")
            continue
        lid_s = str(lid)
        lrow = lit_by_id.get(lid_s, {})
        # derive fields from literature row and paper table
        paper_id = _get(lrow, ["paperNr", "paperID", "paper_id"])
        paper_name = None
        if paper_id is not None:
            prow = paper_by_id.get(str(paper_id))
            if prow:
                paper_name = _get(prow, ["name_paper", "paper_name"]) or paper_name
        lit_obj = ReferencesEntry.LiteratureRef(
            literature_id=int(lid),
            paper_id=(None if _get(lrow, ["paperNr", "paperID", "paper_id"]) is None else int(_get(lrow, ["paperNr", "paperID", "paper_id"]))),
            year=(None if _get(lrow, ["year"]) is None else int(_get(lrow, ["year"]))),
            issue=(None if _get(lrow, ["issue"]) is None else int(_get(lrow, ["issue"]))),
            page=(None if _get(lrow, ["page"]) is None else int(_get(lrow, ["page"]))),
            paper_name=(paper_name or _get(lrow, ["paper_name"]))
        )
        literature_out[lid_s] = lit_obj

        # authors via mapping table
        for aid in lit_to_authors.get(lid_s, []):
            arow = author_by_id.get(str(aid)) or {}
            aname = _get(arow, ["name_author", "name"])  # tolerant
            authors_out[str(aid)] = ReferencesEntry.AuthorRef(
                author_id=int(aid),
                name=(None if aname is None else str(aname)),
            )

        # footnotes attached directly in the link row (if any)
        fids = []
        for key in ["footnoteID", "footnoteNr", "footnote_id", "footnote"]:
            v = _get(link, [key])
            if v is not None:
                fids.append(str(v))
        for fid in fids:
            frow = foot_by_id.get(str(fid)) or {}
            footnotes_out[str(fid)] = ReferencesEntry.FootnoteRef(
                footnote_id=str(fid),
                shortcut=_get(frow, ["shortcut"]),
                text=_get(frow, ["name_footnote", "text"]),
            )

    # literature_alt is often separate; include only if link table carries it explicitly, and fill details if available
    literature_alt_out: Dict[str, ReferencesEntry.LiteratureAltRef] = {}
    for link in vlit_rows:
        laid = _get(link, ["literature_altID", "literature_altNr", "literature_alt_id"])  # optional
        if laid is None:
            continue
        lrow = alt_by_id.get(str(laid)) or {}
        literature_alt_out[str(laid)] = ReferencesEntry.LiteratureAltRef(
            literature_alt_id=int(laid),
            shortcut=_get(lrow, ["literature_shortcut", "shortcut"]),
            citation=_get(lrow, ["literature_alt", "citation"]),
        )

    # Compile into ReferencesEntry
    return ReferencesEntry(
        literature_alt=list(literature_alt_out.values()),
        literature=list(literature_out.values()),
        authors=list(authors_out.values()),
        footnotes=list(footnotes_out.values()),
        reference_ids=[*(list(literature_out.keys())), *(list(footnotes_out.keys()))],
    )


def create_references_entry(data: Dict[str, Any] | None = None, tracker: MissingFieldTracker | None = None) -> ReferencesEntry:
    """Create a ReferencesEntry from a dictionary of reference data."""
    tracker = tracker or DEFAULT_MISSING_TRACKER
    data = data or {}

    # Lists of simple nested refs; rely on dataclass defaults when missing
    le = data.get("literature_alt") or []
    l = data.get("literature") or []
    a = data.get("authors") or []
    f = data.get("footnotes") or []
    rids = data.get("reference_ids") or []

    if not le:
        tracker.mark_empty("ReferencesEntry", "literature_alt")
    if not l:
        tracker.mark_empty("ReferencesEntry", "literature")
    if not a:
        tracker.mark_empty("ReferencesEntry", "authors")
    if not f:
        tracker.mark_empty("ReferencesEntry", "footnotes")
    if not rids:
        tracker.mark_empty("ReferencesEntry", "reference_ids")

    literature_alt = []
    for item in le:
        if not isinstance(item, dict) or "literature_alt_id" not in item or _is_empty(item.get("literature_alt_id")):
            tracker.mark_invalid("ReferencesEntry", "literature_alt")
            continue
        literature_alt.append(ReferencesEntry.LiteratureAltRef(
            literature_alt_id=int(item.get("literature_alt_id")),
            shortcut=(item.get("shortcut") or None),
            citation=(item.get("citation") or None),
        ))

    literature = []
    for item in l:
        if not isinstance(item, dict) or "literature_id" not in item or _is_empty(item.get("literature_id")):
            tracker.mark_invalid("ReferencesEntry", "literature")
            continue
        literature.append(ReferencesEntry.LiteratureRef(
            literature_id=int(item.get("literature_id")),
            paper_id=(None if _is_empty(item.get("paper_id")) else int(item.get("paper_id"))),
            year=(None if _is_empty(item.get("year")) else int(item.get("year"))),
            issue=(None if _is_empty(item.get("issue")) else int(item.get("issue"))),
            page=(None if _is_empty(item.get("page")) else int(item.get("page"))),
            paper_name=(item.get("paper_name") or None),
        ))

    authors = []
    for item in a:
        if not isinstance(item, dict) or "author_id" not in item or _is_empty(item.get("author_id")):
            tracker.mark_invalid("ReferencesEntry", "authors")
            continue
        authors.append(ReferencesEntry.AuthorRef(author_id=int(item.get("author_id")), name=(item.get("name") or None)))

    footnotes = []
    for item in f:
        if not isinstance(item, dict) or "footnote_id" not in item or _is_empty(item.get("footnote_id")):
            tracker.mark_invalid("ReferencesEntry", "footnotes")
            continue
        footnotes.append(ReferencesEntry.FootnoteRef(
            footnote_id=str(item.get("footnote_id")),
            shortcut=(item.get("shortcut") or None),
            text=(item.get("text") or None),
        ))

    return ReferencesEntry(
        literature_alt=literature_alt,
        literature=literature,
        authors=authors,
        footnotes=footnotes,
        reference_ids=[str(x) if not isinstance(x, (int, str)) else x for x in rids],
    )


__all__ = [
    "ReferencesEntry",
    "create_references_entry",
    "create_references_entry_from_tables",
    "create_references_entry_by_ligand_metal",
    "build_reference_indexes",
]


def _get_tolerant(row: Dict[str, Any], keys: List[str]) -> Any:
    """First non-empty value for keys (exact, then case-insensitive); '\\N' counts as empty."""
    for k in keys:
        if k in row and str(row[k]).strip() not in ("", "\\N"):
            return row[k]
    lower = {kk.lower(): vv for kk, vv in row.items()}
    for k in keys:
        if k.lower() in lower and str(lower[k.lower()]).strip() not in ("", "\\N"):
            return lower[k.lower()]
    return None


def build_reference_indexes(tables: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Pre-index the reference tables once so per-pair lookups are O(matching rows).

    Returns a dict with:
      links_by_pair: {(ligand_id, metal_id): [link rows in table order]}  (standard + _sic links)
      alt_by_id, lit_by_id, paper_by_id, author_by_id, foot_by_id: {str(id): row}
      lit_to_authors: {str(literature_id): [str(author_id), ...]}
    Pass the result as ``indexes=`` to create_references_entry_by_ligand_metal.
    """
    def _rows(name: str) -> List[Dict[str, Any]]:
        return list(tables.get(name, []) or [])

    links_by_pair: Dict[tuple, List[Dict[str, Any]]] = {}
    for r in _rows("verkn_ligand_metal_literature") + _rows("verkn_ligand_metal_literature_sic"):
        lig = _get_tolerant(r, ["ligandenNr", "ligandenID", "ligand_id"])
        met = _get_tolerant(r, ["metalNr", "metalID", "metal_id"])
        try:
            if lig is not None and met is not None:
                links_by_pair.setdefault((int(str(lig)), int(str(met))), []).append(r)
        except Exception:
            continue

    def _index(name: str, keys: List[str]) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for r in _rows(name):
            v = _get_tolerant(r, keys)
            if v is not None:
                out[str(v)] = r
        return out

    lit_to_authors: Dict[str, List[str]] = {}
    for r in _rows("verk_literature_author"):
        lid = _get_tolerant(r, ["literatureID", "literatureNr", "literature_id"])
        aid = _get_tolerant(r, ["authorID", "authorNr", "author_id"])
        if lid is not None and aid is not None:
            lit_to_authors.setdefault(str(lid), []).append(str(aid))

    return {
        "links_by_pair": links_by_pair,
        "alt_by_id": _index("literature_alt", ["literature_altID", "literature_altNr", "literature_alt_id"]),
        "lit_by_id": _index("literature", ["literatureID", "literatureNr", "literature_id"]),
        "paper_by_id": _index("paper", ["paperID", "paperNr", "paper_id"]),
        "author_by_id": _index("author", ["authorID", "authorNr", "author_id"]),
        "foot_by_id": _index("footnote", ["footnoteID", "footnoteNr", "footnote_id"]),
        "lit_to_authors": lit_to_authors,
    }


def create_references_entry_by_ligand_metal(
    ligand_id: int,
    metal_id: int,
    tables: Dict[str, List[Dict[str, Any]]],
    tracker: MissingFieldTracker | None = None,
    indexes: Dict[str, Any] | None = None,
) -> ReferencesEntry:
    """Build a ReferencesEntry by joining verkn_ligand_metal_literature with literature,
    authors, and footnotes, matching by ligandenNr + metalNr.

    This is the appropriate function when the link table uses ligand+metal as key
    rather than verkn_ligand_metalID.

    ``indexes`` (from build_reference_indexes) avoids re-scanning/re-indexing the
    tables on every call; when omitted the indexes are built from ``tables``.
    """
    tracker = tracker or DEFAULT_MISSING_TRACKER
    _get = _get_tolerant

    if indexes is None:
        indexes = build_reference_indexes(tables)

    try:
        vlit_rows = indexes["links_by_pair"].get((int(ligand_id), int(metal_id)), [])
    except Exception:
        vlit_rows = []
    alt_by_id = indexes["alt_by_id"]
    lit_by_id = indexes["lit_by_id"]
    paper_by_id = indexes["paper_by_id"]
    author_by_id = indexes["author_by_id"]
    foot_by_id = indexes["foot_by_id"]
    lit_to_authors = indexes["lit_to_authors"]

    # Build de-duped outputs
    literature_alt_out: Dict[str, ReferencesEntry.LiteratureAltRef] = {}
    literature_out: Dict[str, ReferencesEntry.LiteratureRef] = {}
    authors_out: Dict[str, ReferencesEntry.AuthorRef] = {}
    footnotes_out: Dict[str, ReferencesEntry.FootnoteRef] = {}

    for link in vlit_rows:
        # literature_alt reference
        laid = _get(link, ["literature_altNr", "literature_altID", "literature_alt_id"])
        if laid is not None and str(laid) != "0":
            lrow = alt_by_id.get(str(laid)) or {}
            literature_alt_out[str(laid)] = ReferencesEntry.LiteratureAltRef(
                literature_alt_id=int(laid),
                shortcut=_get(lrow, ["literature_shortcut", "shortcut"]),
                citation=_get(lrow, ["literature_alt", "citation"]),
            )

        # literature reference
        lid = _get(link, ["literatureNr", "literatureID", "literature_id"])
        if lid is not None and str(lid) != "0":
            lid_s = str(lid)
            lrow = lit_by_id.get(lid_s, {})
            paper_id = _get(lrow, ["paperNr", "paperID", "paper_id"])
            paper_name = None
            if paper_id is not None:
                prow = paper_by_id.get(str(paper_id))
                if prow:
                    paper_name = _get(prow, ["name_paper", "paper_name"])
            literature_out[lid_s] = ReferencesEntry.LiteratureRef(
                literature_id=int(lid),
                paper_id=(None if paper_id is None else int(paper_id)),
                year=(None if _get(lrow, ["year"]) is None else int(_get(lrow, ["year"]))),
                issue=(None if _get(lrow, ["issue"]) is None else int(_get(lrow, ["issue"]))),
                page=(None if _get(lrow, ["page"]) is None else int(_get(lrow, ["page"]))),
                paper_name=paper_name,
            )
            # authors via mapping table
            for aid in lit_to_authors.get(lid_s, []):
                arow = author_by_id.get(str(aid)) or {}
                aname = _get(arow, ["name_author", "name"])
                authors_out[str(aid)] = ReferencesEntry.AuthorRef(
                    author_id=int(aid),
                    name=(None if aname is None else str(aname)),
                )

        # footnotes
        fid = _get(link, ["footnoteNr", "footnoteID", "footnote_id"])
        if fid is not None and str(fid) != "0" and str(fid) != "\\N":
            frow = foot_by_id.get(str(fid)) or {}
            footnotes_out[str(fid)] = ReferencesEntry.FootnoteRef(
                footnote_id=str(fid),
                shortcut=_get(frow, ["shortcut"]),
                text=_get(frow, ["name_footnote", "text"]),
            )

    return ReferencesEntry(
        literature_alt=list(literature_alt_out.values()),
        literature=list(literature_out.values()),
        authors=list(authors_out.values()),
        footnotes=list(footnotes_out.values()),
        reference_ids=[*list(literature_out.keys()), *list(literature_alt_out.keys())],
    )
