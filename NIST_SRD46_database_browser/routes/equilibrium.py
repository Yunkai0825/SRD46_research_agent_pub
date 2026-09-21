"""Equilibrium network browse routes."""

from flask import Blueprint, render_template, request, redirect, url_for

_PARENT_PACKAGE = (__package__ or "").rpartition(".")[0]

if _PARENT_PACKAGE:
    from .. import db as dbmod
    from ..request_dbs import get_eq, get_cards
    from ..search_utils import normalize_chem_query
else:
    import db as dbmod
    from request_dbs import get_eq, get_cards
    from search_utils import normalize_chem_query

eq_bp = Blueprint("eq", __name__, url_prefix="/equilibrium")

PER_PAGE = 30


@eq_bp.route("/")
def eq_search():
    db = get_eq()
    metal_q = normalize_chem_query(request.args.get("metal_q", "").strip())
    ligand_q = normalize_chem_query(request.args.get("ligand_q", "").strip())
    metal_id = request.args.get("metal_id", "", type=str).strip()
    ligand_id = request.args.get("ligand_id", "", type=str).strip()
    legacy_q = normalize_chem_query(request.args.get("q", "").strip())
    if legacy_q and not metal_q and not ligand_q and not metal_id and not ligand_id:
        metal_q = legacy_q
        ligand_q = legacy_q
    page = max(1, request.args.get("page", 1, type=int))

    results, total = [], 0
    has_search = bool(metal_q or ligand_q or metal_id or ligand_id)

    if has_search:
        offset = (page - 1) * PER_PAGE
        clauses, params = [], []

        if metal_id:
            clauses.append("metal_id = ?")
            params.append(int(metal_id))
        elif metal_q:
            clauses.append("metal_name LIKE ?")
            params.append(f"%{metal_q}%")

        if ligand_id:
            clauses.append("ligand_id = ?")
            params.append(int(ligand_id))
        elif ligand_q:
            clauses.append("ligand_name LIKE ?")
            params.append(f"%{ligand_q}%")

        where = "WHERE " + " AND ".join(clauses)

        total = db.execute(
            f"SELECT COUNT(*) FROM eq_map_collection {where}",
            params,
        ).fetchone()[0]

        results = dbmod.rows_to_dicts(
            db.execute(
                f"""SELECT * FROM eq_map_collection {where}
                   ORDER BY collection_id
                   LIMIT ? OFFSET ?""",
                params + [PER_PAGE, offset],
            )
        )

    pages = (total + PER_PAGE - 1) // PER_PAGE if total else 0
    return render_template(
        "equilibrium.html",
        results=results, total=total, page=page, pages=pages,
        metal_q=metal_q, ligand_q=ligand_q,
        metal_id=metal_id, ligand_id=ligand_id,
        has_search=has_search,
    )


@eq_bp.route("/collection/<int:collection_id>")
def collection_detail(collection_id):
    """Single-page hierarchical browser: collection → maps → networks → nodes/edges."""
    db = get_eq()
    collection = db.execute(
        "SELECT * FROM eq_map_collection WHERE collection_id = ?", (collection_id,)
    ).fetchone()
    if collection is None:
        return "Collection not found", 404
    collection = dict(collection)

    # 1) all maps in this collection
    maps = dbmod.rows_to_dicts(db.execute(
        """SELECT m.*, COUNT(DISTINCT n.network_db_id) AS network_count_actual,
                  COALESCE(SUM(n.node_count), 0) AS total_nodes,
                  COALESCE(SUM(n.edge_count), 0) AS total_edges
           FROM eq_map m
           LEFT JOIN eq_network n ON n.map_id = m.map_id
           WHERE m.collection_id = ?
           GROUP BY m.map_id
           ORDER BY m.iteration""",
        (collection_id,),
    ))
    map_ids = [m["map_id"] for m in maps]

    # 2) all networks across all maps (single query then attach children)
    networks_by_map = {mid: [] for mid in map_ids}
    network_db_ids = []
    net_index = {}
    if map_ids:
        placeholders = ",".join("?" * len(map_ids))
        net_rows = dbmod.rows_to_dicts(db.execute(
            f"""SELECT * FROM eq_network
                WHERE map_id IN ({placeholders})
                ORDER BY map_id, network_id""",
            map_ids,
        ))
        for n in net_rows:
            n["species_list"] = []
            n["nodes"] = []
            n["edges"] = []
            networks_by_map[n["map_id"]].append(n)
            network_db_ids.append(n["network_db_id"])
            net_index[n["network_db_id"]] = n

    if network_db_ids:
        ph = ",".join("?" * len(network_db_ids))

        # 2a) species per network
        for r in db.execute(
            f"SELECT network_db_id, species FROM eq_network_species "
            f"WHERE network_db_id IN ({ph}) ORDER BY species",
            network_db_ids,
        ):
            net_index[r[0]]["species_list"].append(r[1])

        # 2b) nodes
        node_rows = dbmod.rows_to_dicts(db.execute(
            f"""SELECT * FROM eq_node
                WHERE network_db_id IN ({ph})
                ORDER BY network_db_id, entry_index""",
            network_db_ids,
        ))
        node_index = {}
        for nd in node_rows:
            nd["lhs_species"] = []
            nd["rhs_species"] = []
            net_index[nd["network_db_id"]]["nodes"].append(nd)
            node_index[nd["node_db_id"]] = nd

        if node_index:
            np_ = ",".join("?" * len(node_index))
            for r in db.execute(
                f"SELECT node_db_id, species, side FROM eq_node_species "
                f"WHERE node_db_id IN ({np_})",
                list(node_index.keys()),
            ):
                if r[2] == "LHS":
                    node_index[r[0]]["lhs_species"].append(r[1])
                else:
                    node_index[r[0]]["rhs_species"].append(r[1])

        # 2c) edges
        edge_rows = dbmod.rows_to_dicts(db.execute(
            f"""SELECT * FROM eq_edge
                WHERE network_db_id IN ({ph})
                ORDER BY network_db_id, edge_db_id""",
            network_db_ids,
        ))
        edge_index = {}
        for e in edge_rows:
            e["shared_species"] = []
            net_index[e["network_db_id"]]["edges"].append(e)
            edge_index[e["edge_db_id"]] = e

        if edge_index:
            ep = ",".join("?" * len(edge_index))
            for r in db.execute(
                f"SELECT edge_db_id, species FROM eq_edge_species "
                f"WHERE edge_db_id IN ({ep}) ORDER BY species",
                list(edge_index.keys()),
            ):
                edge_index[r[0]]["shared_species"].append(r[1])

    # 3) strays per map
    strays_by_map = {mid: [] for mid in map_ids}
    if map_ids:
        placeholders = ",".join("?" * len(map_ids))
        for r in db.execute(
            f"SELECT map_id, vlm_id FROM eq_map_stray "
            f"WHERE map_id IN ({placeholders}) ORDER BY vlm_id",
            map_ids,
        ):
            strays_by_map[r[0]].append(r[1])

    for m in maps:
        m["networks"] = networks_by_map.get(m["map_id"], [])
        m["strays"] = strays_by_map.get(m["map_id"], [])

    # 4) unassigned VLMs
    unassigned = [r[0] for r in db.execute(
        "SELECT vlm_id FROM eq_collection_unassigned WHERE collection_id = ? ORDER BY vlm_id",
        (collection_id,),
    )]

    # 5) vlm_id -> stability_id back-link map
    cards_db = get_cards()
    vlm_ids = set(unassigned) | {v for vs in strays_by_map.values() for v in vs}
    for n in net_index.values():
        for nd in n["nodes"]:
            vlm_ids.add(nd["vlm_id"])
    stab_map = {}
    if vlm_ids:
        vlm_list = sorted(vlm_ids)
        placeholders = ",".join("?" * len(vlm_list))
        for r in cards_db.execute(
            f"""SELECT c.complex_system_id AS vlm_id, MIN(s.stability_id) AS stability_id
                FROM ligandmetal_card c
                JOIN ligandmetal_stability_measured s ON s.card_id = c.card_id
                WHERE c.complex_system_id IN ({placeholders})
                GROUP BY c.complex_system_id""",
            vlm_list,
        ):
            stab_map[r[0]] = r[1]

    return render_template(
        "collection_detail.html",
        collection=collection, maps=maps,
        unassigned=unassigned, stab_map=stab_map,
    )


# Back-compat redirects: deep links land on collection page at right anchor.

@eq_bp.route("/map/<int:map_id>")
def map_detail(map_id):
    db = get_eq()
    row = db.execute(
        "SELECT collection_id FROM eq_map WHERE map_id = ?", (map_id,)
    ).fetchone()
    if row is None:
        return "Map not found", 404
    return redirect(
        url_for("eq.collection_detail", collection_id=row[0]) + f"#map-{map_id}"
    )


@eq_bp.route("/network/<int:network_db_id>")
def network_detail(network_db_id):
    db = get_eq()
    row = db.execute(
        """SELECT m.collection_id
           FROM eq_network n
           JOIN eq_map m ON m.map_id = n.map_id
           WHERE n.network_db_id = ?""",
        (network_db_id,),
    ).fetchone()
    if row is None:
        return "Network not found", 404
    return redirect(
        url_for("eq.collection_detail", collection_id=row[0])
        + f"#network-{network_db_id}"
    )
