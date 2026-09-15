"""Ligand similarity search route (Morgan Tanimoto ranking)."""

from flask import Blueprint, render_template, request

_PARENT_PACKAGE = (__package__ or "").rpartition(".")[0]

if _PARENT_PACKAGE:
    from .. import db as dbmod
    from ..request_dbs import get_cards, get_fp
    from ..search_utils import normalize_chem_query, ligand_search_terms
else:
    import db as dbmod
    from request_dbs import get_cards, get_fp
    from search_utils import normalize_chem_query, ligand_search_terms

sim_bp = Blueprint("sim", __name__, url_prefix="/similarity")


@sim_bp.route("/")
def sim_search():
    q = normalize_chem_query(request.args.get("q", "").strip())
    ligand_id = request.args.get("ligand_id", "", type=str).strip()
    raw_top_k = request.args.get("top_k", "20").strip()
    results, candidates = [], []
    ligand_name, message = "", ""
    has_search = bool(q or ligand_id)
    status = 200
    try:
        top_k = int(raw_top_k)
        if not 1 <= top_k <= 100:
            raise ValueError
    except ValueError:
        top_k = 20
        message = "Top K must be an integer from 1 to 100."
        status = 400

    lid = None
    if ligand_id and not message:
        try:
            lid = int(ligand_id)
            if not 1 <= lid <= 9223372036854775807:
                raise ValueError
        except ValueError:
            message = "Ligand ID must be a positive integer."
            status = 400

    if has_search and not message:
        cards = get_cards()
        if lid is None:
            terms = ligand_search_terms(q)
            fields = ("ligand_name_SRD", "synonym_common_name", "synonym_iupac_name")
            where = " OR ".join(f"{field} LIKE ?" for _ in terms for field in fields)
            matches = dbmod.rows_to_dicts(cards.execute(
                f"SELECT ligand_id, ligand_name_SRD, synonym_common_name, synonym_iupac_name "
                f"FROM ligand_card WHERE {where} ORDER BY ligand_name_SRD, ligand_id",
                [f"%{term}%" for term in terms for _ in fields],
            ))
            exact = [row for row in matches if any(
                (row.get(field) or "").casefold() == term.casefold()
                for field in fields for term in terms
            )]
            choices = exact or matches
            if len(choices) == 1:
                lid = choices[0]["ligand_id"]
                ligand_id = str(lid)
            elif choices:
                candidates = choices[:50]
                message = "Several ligands match this name. Select a ligand below or enter its ID."
            else:
                message = "No ligand matches this name."

        if lid is not None:
            name_row = cards.execute(
                "SELECT ligand_name_SRD FROM ligand_card WHERE ligand_id = ?", (lid,),
            ).fetchone()
            if name_row is None:
                message = "Ligand ID was not found."
                status = 404
            else:
                ligand_name = name_row[0]
                fp_db = get_fp()
                sim_rows = dbmod.rows_to_dicts(fp_db.execute(
                    """SELECT ligand_id_2 AS ligand_id, tanimoto_maccs, tanimoto_morgan
                       FROM ligand_similarity
                       WHERE ligand_id_1 = ? AND ligand_id_2 != ?
                         AND tanimoto_morgan IS NOT NULL
                       UNION ALL
                       SELECT ligand_id_1 AS ligand_id, tanimoto_maccs, tanimoto_morgan
                       FROM ligand_similarity
                       WHERE ligand_id_2 = ? AND ligand_id_1 != ?
                         AND tanimoto_morgan IS NOT NULL
                       ORDER BY tanimoto_morgan DESC, ligand_id ASC
                       LIMIT ?""", (lid, lid, lid, lid, top_k),
                ))
                for sr in sim_rows:
                    row = cards.execute(
                        "SELECT ligand_name_SRD, formula FROM ligand_card WHERE ligand_id = ?",
                        (sr["ligand_id"],),
                    ).fetchone()
                    sr["ligand_name_SRD"] = row[0] if row else ""
                    sr["formula"] = row[1] if row else ""
                results = sim_rows
                if not results:
                    message = "No usable Morgan similarity data is available for this ligand."

    return render_template(
        "similarity.html", results=results, ligand_name=ligand_name,
        q=q, ligand_id=ligand_id, top_k=top_k, has_search=has_search,
        message=message, candidates=candidates,
    ), status
