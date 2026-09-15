"""Literature search route."""

from flask import Blueprint, render_template, request

_PARENT_PACKAGE = (__package__ or "").rpartition(".")[0]

if _PARENT_PACKAGE:
    from .. import db as dbmod
    from ..request_dbs import get_cards
    from ..search_utils import normalize_chem_query
else:
    import db as dbmod
    from request_dbs import get_cards
    from search_utils import normalize_chem_query

lit_bp = Blueprint("lit", __name__, url_prefix="/literature")

PER_PAGE = 50


@lit_bp.route("/")
def lit_search():
    # ref_literature_alt is in cards DB; literature_alt is in literature DB
    # Use cards DB for the common shortcut+citation table
    db = get_cards()
    q = normalize_chem_query(request.args.get("q", "").strip())
    page = max(1, request.args.get("page", 1, type=int))

    results, total = [], 0
    has_search = bool(q)

    if has_search:
        offset = (page - 1) * PER_PAGE
        total = db.execute(
            """SELECT COUNT(*) FROM ref_literature_alt
               WHERE shortcut LIKE ? OR citation LIKE ?""",
            (f"%{q}%", f"%{q}%"),
        ).fetchone()[0]

        results = dbmod.rows_to_dicts(
            db.execute(
                """SELECT * FROM ref_literature_alt
                   WHERE shortcut LIKE ? OR citation LIKE ?
                   ORDER BY shortcut
                   LIMIT ? OFFSET ?""",
                (f"%{q}%", f"%{q}%", PER_PAGE, offset),
            )
        )

    pages = (total + PER_PAGE - 1) // PER_PAGE if total else 0
    return render_template(
        "literature.html",
        results=results, total=total, page=page, pages=pages,
        q=q, has_search=has_search,
    )
