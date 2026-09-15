"""Metals browse & detail routes."""

from flask import Blueprint, render_template, request

from ._measurement_display import optional_text

_PARENT_PACKAGE = (__package__ or "").rpartition(".")[0]

if _PARENT_PACKAGE:
    from .. import db as dbmod
    from ..request_dbs import get_cards
    from ..search_utils import normalize_chem_query
else:
    import db as dbmod
    from request_dbs import get_cards
    from search_utils import normalize_chem_query

metals_bp = Blueprint("metals", __name__, url_prefix="/metals")

PER_PAGE = 30


@metals_bp.route("/")
def metals_list():
    db = get_cards()
    q = normalize_chem_query(request.args.get("q", "").strip())
    page = max(1, request.args.get("page", 1, type=int))
    offset = (page - 1) * PER_PAGE

    where, params = "", []
    if q:
        where = "WHERE m.metal_name_SRD LIKE ? OR m.symbol_pure LIKE ?"
        params = [f"%{q}%", f"%{q}%"]

    total = db.execute(
        f"SELECT COUNT(*) FROM metal_card m {where}", params
    ).fetchone()[0]

    rows = dbmod.rows_to_dicts(
        db.execute(
            f"""SELECT m.metal_id, m.metal_name_SRD, m.symbol_pure, m.charge,
                       m.SMILES, m.InChi,
                       (SELECT COUNT(*) FROM ligandmetal_card c
                        WHERE c.metal_id = m.metal_id) AS entry_count
                FROM metal_card m {where}
                ORDER BY m.metal_name_SRD
                LIMIT ? OFFSET ?""",
            params + [PER_PAGE, offset],
        )
    )

    pages = (total + PER_PAGE - 1) // PER_PAGE
    return render_template(
        "metals.html", metals=rows, q=q, page=page, pages=pages, total=total
    )


@metals_bp.route("/<int:metal_id>")
def metal_detail(metal_id):
    db = get_cards()
    metal = db.execute(
        "SELECT * FROM metal_card WHERE metal_id = ?", (metal_id,)
    ).fetchone()
    if metal is None:
        return "Metal not found", 404
    metal = dict(metal)
    for key in ("SMILES", "InChi"):
        metal[key] = optional_text(metal.get(key))

    stats = dict(db.execute(
        """SELECT COUNT(DISTINCT c.ligand_id)            AS n_ligands,
                  COUNT(DISTINCT c.beta_definition_id)   AS n_beta_defs,
                  COUNT(DISTINCT c.complex_system_id)    AS n_systems,
                  COUNT(s.stability_id)                  AS n_measurements,
                  MIN(CASE WHEN s.constant_type = 'K' THEN s.constant_value END)                  AS logK_min,
                  MAX(CASE WHEN s.constant_type = 'K' THEN s.constant_value END)                  AS logK_max,
                  AVG(CASE WHEN s.constant_type = 'K' THEN s.constant_value END)                  AS logK_avg
           FROM   ligandmetal_card c
           LEFT JOIN ligandmetal_stability_measured s ON s.card_id = c.card_id
           WHERE  c.metal_id = ?""",
        (metal_id,),
    ).fetchone() or {})

    ligands = dbmod.rows_to_dicts(
        db.execute(
            """SELECT l.ligand_id, l.ligand_name_SRD, l.formula,
                      COUNT(DISTINCT c.beta_definition_id)  AS n_beta_defs,
                      COUNT(DISTINCT c.complex_system_id) AS n_systems,
                      COUNT(s.stability_id)               AS n_entries,
                      MIN(CASE WHEN s.constant_type = 'K' THEN s.constant_value END)               AS logK_min,
                      MAX(CASE WHEN s.constant_type = 'K' THEN s.constant_value END)               AS logK_max
               FROM ligandmetal_card c
               JOIN ligand_card l ON c.ligand_id = l.ligand_id
               LEFT JOIN ligandmetal_stability_measured s ON s.card_id = c.card_id
               WHERE c.metal_id = ?
               GROUP BY l.ligand_id
               ORDER BY n_entries DESC LIMIT 50""",
            (metal_id,),
        )
    )

    return render_template("metal_detail.html", metal=metal, ligands=ligands, stats=stats)
