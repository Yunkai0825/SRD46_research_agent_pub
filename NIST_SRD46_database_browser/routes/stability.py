"""Stability constants search route."""

import json as _json

from flask import Blueprint, abort, render_template, request

from ._measurement_display import optional_text, plain_definition

_PARENT_PACKAGE = (__package__ or "").rpartition(".")[0]

if _PARENT_PACKAGE:
    from .. import db as dbmod
    from ..request_dbs import get_cards, get_eq, get_lit
    from ..search_utils import normalize_chem_query
else:
    import db as dbmod
    from request_dbs import get_cards, get_eq, get_lit
    from search_utils import normalize_chem_query

stability_bp = Blueprint("stability", __name__, url_prefix="/stability")

PER_PAGE = 50


@stability_bp.route("/")
def stability_search():
    db = get_cards()
    metal_id = request.args.get("metal_id", "", type=str).strip()
    ligand_id = request.args.get("ligand_id", "", type=str).strip()
    metal_q = normalize_chem_query(request.args.get("metal_q", "").strip())
    ligand_q = normalize_chem_query(request.args.get("ligand_q", "").strip())
    page = max(1, request.args.get("page", 1, type=int))

    results, total = [], 0

    # Build query if we have search parameters
    has_search = any([metal_id, ligand_id, metal_q, ligand_q])
    if has_search:
        clauses, params = [], []

        if metal_id:
            clauses.append("c.metal_id = ?")
            params.append(int(metal_id))
        elif metal_q:
            clauses.append("(m.metal_name_SRD LIKE ? OR m.symbol_pure LIKE ?)")
            params += [f"%{metal_q}%", f"%{metal_q}%"]

        if ligand_id:
            clauses.append("c.ligand_id = ?")
            params.append(int(ligand_id))
        elif ligand_q:
            clauses.append("l.ligand_name_SRD LIKE ?")
            params.append(f"%{ligand_q}%")

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        offset = (page - 1) * PER_PAGE

        total = db.execute(
            f"""SELECT COUNT(*)
                FROM ligandmetal_card c
                JOIN metal_card m ON c.metal_id = m.metal_id
                JOIN ligand_card l ON c.ligand_id = l.ligand_id
                JOIN ligandmetal_stability_measured s ON s.card_id = c.card_id
                {where}""",
            params,
        ).fetchone()[0]

        results = dbmod.rows_to_dicts(
            db.execute(
                f"""SELECT c.card_id, m.metal_id, m.metal_name_SRD, m.symbol_pure AS metal_symbol,
                           l.ligand_id, l.ligand_name_SRD, l.formula AS ligand_formula,
                           s.stability_id, s.constant_type, s.constant_value,
                           s.temperature_c, s.ionic_strength_mol_l,
                           s.equation_python, s.element_conserved
                    FROM ligandmetal_card c
                    JOIN metal_card m ON c.metal_id = m.metal_id
                    JOIN ligand_card l ON c.ligand_id = l.ligand_id
                    JOIN ligandmetal_stability_measured s ON s.card_id = c.card_id
                    {where}
                    ORDER BY m.metal_name_SRD, l.ligand_name_SRD, s.constant_type
                    LIMIT ? OFFSET ?""",
                params + [PER_PAGE, offset],
            )
        )

    pages = (total + PER_PAGE - 1) // PER_PAGE if total else 0
    return render_template(
        "stability.html",
        results=results, total=total, page=page, pages=pages,
        metal_id=metal_id, ligand_id=ligand_id,
        metal_q=metal_q, ligand_q=ligand_q, has_search=has_search,
    )


@stability_bp.route("/entry/<int:stability_id>")
def vlm_detail(stability_id):
    db = get_cards()
    sql = """
        SELECT c.card_id,
               c.complex_system_id     AS vlm_id,
               c.metal_id,
               c.ligand_id,
               c.beta_definition_id,
               c.beta_definition_name,
               c.ligand_class_name,
               c.metal_name_SRD        AS metal_name,
               c.ligand_name_SRD       AS ligand_name,
               c.ligand_HxL_definition_SRD AS ligand_HxL_definition,
               c.metal_SMILES,
               c.metal_InChi,
               c.ligand_SMILES,
               c.ligand_InChi,
               s.stability_id,
               s.constant_type,
               s.constant_value        AS measurement_value,
               s.temperature_c         AS temperature,
               s.ionic_strength_mol_l  AS ionic_strength,
               s.solvent_name          AS solvent,
               s.electrolyte_composition AS electrolyte,
               s.equation_python       AS equation,
               s.equation_str,
               s.raw_definition,
               s.normalized_definition,
               s.reaction_type,
               s.element_conserved,
               s.LHS_species_json,
               s.RHS_species_json,
               s.HxL_involved_json,
               s.equation_tree_json,
               s.citations_json,
               s.error                 AS uncertainty,
               s.notes
        FROM   ligandmetal_card c
        JOIN   ligandmetal_stability_measured s ON s.card_id = c.card_id
        WHERE  s.stability_id = ?
    """
    rows = dbmod.rows_to_dicts(db.execute(sql, (stability_id,)))
    if not rows:
        abort(404)
    vlm = rows[0]
    vlm["source_convention_review"] = "parser:source_convention_review=1" in (vlm.get("notes") or "")
    for key in ("metal_SMILES", "metal_InChi", "ligand_SMILES", "ligand_InChi", "ligand_class_name",
                "solvent", "electrolyte", "uncertainty", "notes"):
        vlm[key] = optional_text(vlm.get(key))
    for key in ("beta_definition_name", "ligand_HxL_definition"):
        vlm[key] = plain_definition(vlm.get(key))
    kind = vlm.get("constant_type")
    vlm["measurement_label"] = {"K": "log K / β", "H": "ΔH", "S": "ΔS"}.get(kind, "Value")
    vlm["measurement_title"] = {"K": "Stability constant", "H": "Reaction enthalpy",
                                "S": "Reaction entropy"}.get(kind, "Measurement")
    # The SQL export identifies H/S but does not record which of SRD46's dual
    # kcal/kJ or cal/J display units was exported. Preserve values without guessing units.
    vlm["units_unrecorded"] = kind in ("H", "S")
    equation = str(vlm.get("equation") or vlm.get("equation_str") or "").strip()
    vlm["equation_unresolved"] = vlm.get("element_conserved") == 0 or equation in ("", "*")

    for key in ("LHS_species_json", "RHS_species_json", "HxL_involved_json", "equation_tree_json", "citations_json"):
        raw = vlm.get(key)
        if isinstance(raw, str):
            try:
                vlm[key] = _json.loads(raw)
            except Exception:
                pass

    # Build species -> phase map from equation_tree_json (phase defaults to 'aqueous').
    phase_map = {}
    tree = vlm.get("equation_tree_json")
    if isinstance(tree, dict):
        for side in ("numerator", "denominator"):
            for item in tree.get(side, []) or []:
                sp = item.get("species")
                ph = item.get("phase") or "aqueous"
                if sp:
                    phase_map[sp] = ph
    vlm["phase_map"] = phase_map

    vlm_id = vlm.get("vlm_id")

    networks = []
    if vlm_id is not None:
        try:
            eq_db = get_eq()
            networks = dbmod.rows_to_dicts(eq_db.execute(
                """SELECT n.network_db_id AS network_id,
                          n.node_count, n.edge_count,
                          nd.node_db_id  AS node_id,
                          nd.is_duplicate
                   FROM   eq_node nd
                   JOIN   eq_network n ON n.network_db_id = nd.network_db_id
                   WHERE  nd.vlm_id = ?""",
                (vlm_id,),
            ))
        except Exception:
            pass

    citations = []
    if vlm_id is not None:
        try:
            lit_db = get_lit()
            citations = dbmod.rows_to_dicts(lit_db.execute(
                """SELECT la.literature_alt_id, la.shortcut, la.citation
                   FROM   vlm_literature_sic sic
                   JOIN   literature_alt la ON la.literature_alt_id = sic.literature_alt_id
                   WHERE  sic.vlm_id = ?
                   ORDER BY la.shortcut, la.literature_alt_id""",
                (vlm_id,),
            ))
        except Exception:
            pass

    # System catalog: every (system × measurement) for this (metal, ligand) pair.
    # Grouped by complex_system_id (= vlm_id) so users can see all β-definitions
    # available for the pair, with logK / T aggregates per system.
    system_catalog = []
    if vlm.get("metal_id") is not None and vlm.get("ligand_id") is not None:
        system_catalog = dbmod.rows_to_dicts(db.execute(
            """SELECT c.complex_system_id              AS vlm_id,
                      c.beta_definition_id,
                      c.beta_definition_name,
                      MIN(s.stability_id)              AS first_stability_id,
                      COUNT(s.stability_id)            AS n_entries,
                      MIN(CASE WHEN s.constant_type = 'K' THEN s.constant_value END)            AS logK_min,
                      MAX(CASE WHEN s.constant_type = 'K' THEN s.constant_value END)            AS logK_max,
                      AVG(CASE WHEN s.constant_type = 'K' THEN s.constant_value END)            AS logK_avg,
                      MIN(s.temperature_c)             AS T_min,
                      MAX(s.temperature_c)             AS T_max,
                      MIN(s.ionic_strength_mol_l)      AS I_min,
                      MAX(s.ionic_strength_mol_l)      AS I_max
               FROM   ligandmetal_card c
               JOIN   ligandmetal_stability_measured s ON s.card_id = c.card_id
               WHERE  c.metal_id = ? AND c.ligand_id = ?
               GROUP BY c.complex_system_id, c.beta_definition_id, c.beta_definition_name
               ORDER BY n_entries DESC, c.beta_definition_name""",
            (vlm["metal_id"], vlm["ligand_id"]),
        ))

    for system in system_catalog:
        system["beta_definition_name"] = plain_definition(system.get("beta_definition_name"))

    return render_template(
        "vlm_detail.html",
        vlm=vlm, networks=networks, citations=citations,
        system_catalog=system_catalog,
    )
