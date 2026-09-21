"""Ligand similarity search route."""

from flask import Blueprint, render_template, request

_PARENT_PACKAGE = (__package__ or "").rpartition(".")[0]

if _PARENT_PACKAGE:
    from .. import db as dbmod
    from ..request_dbs import get_cards, get_fp
    from ..search_utils import normalize_chem_query
else:
    import db as dbmod
    from request_dbs import get_cards, get_fp
    from search_utils import normalize_chem_query

sim_bp = Blueprint("sim", __name__, url_prefix="/similarity")


@sim_bp.route("/")
def sim_search():
    q = normalize_chem_query(request.args.get("q", "").strip())
    ligand_id = request.args.get("ligand_id", "", type=str).strip()
    top_k = min(request.args.get("top_k", 20, type=int), 100)

    results = []
    ligand_name = ""
    has_search = bool(q or ligand_id)

    if has_search:
        cards = get_cards()

        # Resolve ligand_id from name search
        if not ligand_id and q:
            row = cards.execute(
                "SELECT ligand_id FROM ligand_card WHERE ligand_name_SRD LIKE ? LIMIT 1",
                (f"%{q}%",),
            ).fetchone()
            if row:
                ligand_id = str(row[0])

        if ligand_id:
            lid = int(ligand_id)
            name_row = cards.execute(
                "SELECT ligand_name_SRD FROM ligand_card WHERE ligand_id = ?",
                (lid,),
            ).fetchone()
            ligand_name = name_row[0] if name_row else f"ligand_{lid}"

            fp_db = get_fp()
            sim_rows = dbmod.rows_to_dicts(
                fp_db.execute(
                    """SELECT ligand_id_2 AS ligand_id,
                              tanimoto_maccs, tanimoto_morgan
                       FROM ligand_similarity
                       WHERE ligand_id_1 = ?
                       ORDER BY tanimoto_morgan DESC
                       LIMIT ?""",
                    (lid, top_k),
                )
            )
            for sr in sim_rows:
                name_r = cards.execute(
                    "SELECT ligand_name_SRD, formula FROM ligand_card WHERE ligand_id = ?",
                    (sr["ligand_id"],),
                ).fetchone()
                sr["ligand_name_SRD"] = name_r[0] if name_r else ""
                sr["formula"] = name_r[1] if name_r else ""
            results = sim_rows

    return render_template(
        "similarity.html",
        results=results, ligand_name=ligand_name,
        q=q, ligand_id=ligand_id, top_k=top_k, has_search=has_search,
    )
