"""Ligands browse & detail routes."""

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

ligands_bp = Blueprint("ligands", __name__, url_prefix="/ligands")

PER_PAGE = 30


@ligands_bp.route("/")
def ligands_list():
    db = get_cards()
    q = normalize_chem_query(request.args.get("q", "").strip())
    cls = request.args.get("cls", "").strip()
    page = max(1, request.args.get("page", 1, type=int))
    offset = (page - 1) * PER_PAGE

    clauses, params = [], []
    if q:
        clauses.append("(l.ligand_name_SRD LIKE ? OR l.formula LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    if cls:
        clauses.append("l.ligand_class_name = ?")
        params.append(cls)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    total = db.execute(
        f"SELECT COUNT(*) FROM ligand_card l {where}", params
    ).fetchone()[0]

    rows = dbmod.rows_to_dicts(
        db.execute(
            f"""SELECT l.ligand_id, l.ligand_name_SRD, l.formula,
                       l.ligand_class_name, l.ligand_SMILES,
                       (SELECT COUNT(*) FROM ligandmetal_card c
                        WHERE c.ligand_id = l.ligand_id) AS entry_count
                FROM ligand_card l {where}
                ORDER BY l.ligand_name_SRD
                LIMIT ? OFFSET ?""",
            params + [PER_PAGE, offset],
        )
    )

    # For the class filter dropdown
    classes = dbmod.rows_to_dicts(
        db.execute(
            """SELECT DISTINCT ligand_class_name FROM ligand_card
               WHERE ligand_class_name IS NOT NULL
               ORDER BY ligand_class_name"""
        )
    )

    pages = (total + PER_PAGE - 1) // PER_PAGE
    return render_template(
        "ligands.html",
        ligands=rows, q=q, cls=cls, classes=classes,
        page=page, pages=pages, total=total,
    )


@ligands_bp.route("/<int:ligand_id>")
def ligand_detail(ligand_id):
    db = get_cards()
    lig = db.execute(
        "SELECT * FROM ligand_card WHERE ligand_id = ?", (ligand_id,)
    ).fetchone()
    if lig is None:
        return "Ligand not found", 404
    lig = dict(lig)

    # pKa data
    pkas = dbmod.rows_to_dicts(
        db.execute(
            """SELECT * FROM ligand_pka_measured
               WHERE ligand_id = ?
               ORDER BY pKa""",
            (ligand_id,),
        )
    )

    # pKa brackets
    brackets = dbmod.rows_to_dicts(
        db.execute(
            """SELECT * FROM ligand_pka_bracket
               WHERE ligand_id = ?
               ORDER BY charge DESC""",
            (ligand_id,),
        )
    )

    # Metals with stability data
    metals = dbmod.rows_to_dicts(
        db.execute(
            """SELECT m.metal_id, m.metal_name_SRD, m.symbol_pure, m.charge,
                      COUNT(DISTINCT c.beta_definition_id)  AS n_beta_defs,
                      COUNT(DISTINCT c.complex_system_id) AS n_systems,
                      COUNT(s.stability_id)               AS n_entries,
                      MIN(s.constant_value)               AS logK_min,
                      MAX(s.constant_value)               AS logK_max
               FROM ligandmetal_card c
               JOIN metal_card m ON c.metal_id = m.metal_id
               LEFT JOIN ligandmetal_stability_measured s ON s.card_id = c.card_id
               WHERE c.ligand_id = ?
               GROUP BY m.metal_id
               ORDER BY n_entries DESC LIMIT 50""",
            (ligand_id,),
        )
    )

    stats = dict(db.execute(
        """SELECT COUNT(DISTINCT c.metal_id)             AS n_metals,
                  COUNT(DISTINCT c.beta_definition_id)   AS n_beta_defs,
                  COUNT(DISTINCT c.complex_system_id)    AS n_systems,
                  COUNT(s.stability_id)                  AS n_measurements,
                  MIN(s.constant_value)                  AS logK_min,
                  MAX(s.constant_value)                  AS logK_max,
                  AVG(s.constant_value)                  AS logK_avg
           FROM   ligandmetal_card c
           LEFT JOIN ligandmetal_stability_measured s ON s.card_id = c.card_id
           WHERE  c.ligand_id = ?""",
        (ligand_id,),
    ).fetchone() or {})
    stats["n_pka"] = len(pkas)

    return render_template(
        "ligand_detail.html",
        lig=lig, pkas=pkas, brackets=brackets, metals=metals, stats=stats,
    )
