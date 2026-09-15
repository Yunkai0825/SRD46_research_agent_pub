"""pKa search route + per-ligand detail."""

from __future__ import annotations

import json as _json
import re
from collections import OrderedDict, defaultdict
from statistics import mean, median

from flask import Blueprint, abort, render_template, request

_PARENT_PACKAGE = (__package__ or "").rpartition(".")[0]

if _PARENT_PACKAGE:
    from .. import db as dbmod
    from ..request_dbs import get_cards
    from ..search_utils import normalize_chem_query
else:
    import db as dbmod
    from request_dbs import get_cards
    from search_utils import normalize_chem_query

pka_bp = Blueprint("pka", __name__, url_prefix="/pka")

PER_PAGE = 50
DEFAULT_PH_TOL = 0.5


def _to_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _resolve_pka_window(pka_min, pka_max, ph_target, ph_tol):
    """Combine explicit pKa range + (pH ± tol) into a single (lo, hi) window."""
    lo = _to_float(pka_min)
    hi = _to_float(pka_max)
    pH = _to_float(ph_target)
    tol = _to_float(ph_tol)
    if pH is not None:
        t = tol if (tol is not None and tol >= 0) else DEFAULT_PH_TOL
        ph_lo, ph_hi = pH - t, pH + t
        lo = ph_lo if lo is None else max(lo, ph_lo)
        hi = ph_hi if hi is None else min(hi, ph_hi)
    return lo, hi


@pka_bp.route("/")
def pka_search():
    db = get_cards()
    q = normalize_chem_query(request.args.get("q", "").strip())
    ligand_id = request.args.get("ligand_id", "", type=str).strip()
    pka_min_raw = request.args.get("pka_min", "", type=str).strip()
    pka_max_raw = request.args.get("pka_max", "", type=str).strip()
    ph_target_raw = request.args.get("ph_target", "", type=str).strip()
    ph_tol_raw = request.args.get("ph_tol", "", type=str).strip()
    bracket_raw = request.args.get("bracket", "", type=str).strip()
    group_by_ligand = request.args.get("group", "ligand") == "ligand"
    page = max(1, request.args.get("page", 1, type=int))

    pka_lo, pka_hi = _resolve_pka_window(pka_min_raw, pka_max_raw,
                                         ph_target_raw, ph_tol_raw)

    has_search = any([q, ligand_id, pka_lo is not None, pka_hi is not None,
                      bracket_raw])

    results, total = [], 0
    grouped = []

    if has_search:
        clauses, params = [], []
        if ligand_id:
            clauses.append("p.ligand_id = ?")
            params.append(int(ligand_id))
        elif q:
            clauses.append("(l.ligand_name_SRD LIKE ? OR l.formula LIKE ? "
                           "OR l.synonym_iupac_name LIKE ? "
                           "OR l.synonym_common_name LIKE ?)")
            params += [f"%{q}%"] * 4
        if pka_lo is not None:
            clauses.append("p.pKa >= ?")
            params.append(pka_lo)
        if pka_hi is not None:
            clauses.append("p.pKa <= ?")
            params.append(pka_hi)
        if bracket_raw:
            b = bracket_raw.replace(" ", "")
            clauses.append("(p.bracket_from_state LIKE ? "
                           "OR p.bracket_to_state LIKE ?)")
            params += [f"%{b}%", f"%{b}%"]

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        if group_by_ligand:
            total = db.execute(
                f"""SELECT COUNT(*) FROM (
                        SELECT p.ligand_id
                        FROM ligand_pka_measured p
                        JOIN ligand_card l ON p.ligand_id = l.ligand_id
                        {where}
                        GROUP BY p.ligand_id
                    )""",
                params,
            ).fetchone()[0]
            offset = (page - 1) * PER_PAGE
            grouped = dbmod.rows_to_dicts(
                db.execute(
                    f"""SELECT p.ligand_id,
                               l.ligand_name_SRD,
                               l.formula,
                               l.ligand_class_name,
                               COUNT(*)               AS n_entries,
                               MIN(p.pKa)             AS pka_min,
                               MAX(p.pKa)             AS pka_max,
                               AVG(p.pKa)             AS pka_avg,
                               COUNT(DISTINCT p.bracket_from_state
                                     || '>' || p.bracket_to_state) AS n_transitions
                        FROM ligand_pka_measured p
                        JOIN ligand_card l ON p.ligand_id = l.ligand_id
                        {where}
                        GROUP BY p.ligand_id, l.ligand_name_SRD,
                                 l.formula, l.ligand_class_name
                        ORDER BY l.ligand_name_SRD
                        LIMIT ? OFFSET ?""",
                    params + [PER_PAGE, offset],
                )
            )
        else:
            total = db.execute(
                f"""SELECT COUNT(*)
                    FROM ligand_pka_measured p
                    JOIN ligand_card l ON p.ligand_id = l.ligand_id
                    {where}""",
                params,
            ).fetchone()[0]
            offset = (page - 1) * PER_PAGE
            results = dbmod.rows_to_dicts(
                db.execute(
                    f"""SELECT p.*, l.ligand_name_SRD, l.formula,
                               l.ligand_class_name
                        FROM ligand_pka_measured p
                        JOIN ligand_card l ON p.ligand_id = l.ligand_id
                        {where}
                        ORDER BY l.ligand_name_SRD, p.pKa
                        LIMIT ? OFFSET ?""",
                    params + [PER_PAGE, offset],
                )
            )

    pages = (total + PER_PAGE - 1) // PER_PAGE if total else 0
    return render_template(
        "pka.html",
        results=results,
        grouped=grouped,
        group_by_ligand=group_by_ligand,
        total=total, page=page, pages=pages,
        q=q, ligand_id=ligand_id,
        pka_min=pka_min_raw, pka_max=pka_max_raw,
        ph_target=ph_target_raw, ph_tol=ph_tol_raw,
        pka_window=(pka_lo, pka_hi),
        bracket=bracket_raw,
        has_search=has_search,
    )


# --- per-ligand pKa detail ----------------------------------------------------

def _state_proton_count(state):
    """Return the count only for a complete single-ligand HxL state label."""
    match = re.fullmatch(r"(?:H(?P<count>[+-]?\d*))?L", str(state or "").strip())
    if match is None:
        return None
    count = match.group("count")
    if count is None:
        return 0
    if count == "":
        return 1
    try:
        return int(count)
    except ValueError:
        return None


def _display_transition(source_from, source_to):
    """Orient known unequal proton counts without altering recorded transition fields."""
    frm, to = str(source_from or "?").strip(), str(source_to or "?").strip()
    from_count, to_count = _state_proton_count(frm), _state_proton_count(to)
    known = from_count is not None and to_count is not None and from_count != to_count
    if known and from_count < to_count:
        frm, to = to, frm
    return frm, to, "acid_to_base" if known else "source"


@pka_bp.route("/ligand/<int:ligand_id>")
def ligand_pka_detail(ligand_id: int):
    db = get_cards()

    cols = ["ligand_id", "ligand_name_SRD", "formula", "ligand_class_name",
            "ligand_SMILES", "ligand_InChi", "definition_HxL",
            "synonym_iupac_name", "synonym_common_name"]
    row = db.execute(
        f"SELECT {', '.join(cols)} FROM ligand_card WHERE ligand_id = ?",
        (ligand_id,),
    ).fetchone()
    if not row:
        abort(404)
    ligand = dict(zip(cols, row))

    rows = dbmod.rows_to_dicts(db.execute(
        """SELECT * FROM ligand_pka_measured
           WHERE ligand_id = ?
           ORDER BY pKa""",
        (ligand_id,),
    ))
    if not rows:
        abort(404)

    # Resolve vlm_id -> a representative stability_id (first per vlm) for linking.
    vlm_ids: set[int] = set()
    for r in rows:
        raw = r.get("vlm_ids_json")
        if isinstance(raw, str):
            try:
                ids = _json.loads(raw)
            except Exception:
                ids = []
        else:
            ids = raw or []
        r["vlm_ids"] = [int(v) for v in (ids or []) if v is not None]
        vlm_ids.update(r["vlm_ids"])

    vlm_to_stability: dict[int, int | None] = {}
    if vlm_ids:
        placeholders = ",".join("?" * len(vlm_ids))
        for vlm, sid in db.execute(
            f"""SELECT c.complex_system_id, MIN(s.stability_id)
                FROM ligandmetal_card c
                JOIN ligandmetal_stability_measured s ON s.card_id = c.card_id
                WHERE c.complex_system_id IN ({placeholders})
                GROUP BY c.complex_system_id""",
            tuple(vlm_ids),
        ).fetchall():
            vlm_to_stability[int(vlm)] = int(sid) if sid is not None else None

    # Group by display direction while keeping source fields, values and VLMs intact.
    groups: "OrderedDict[tuple[str, str], dict]" = OrderedDict()
    for r in rows:
        frm, to, direction = _display_transition(r.get("bracket_from_state"), r.get("bracket_to_state"))
        key = (frm, to)
        groups.setdefault(key, {
            "from": frm,
            "to": to,
            "direction": direction,
            "entries": [],
            "vlm_links": [],
        })["entries"].append(r)

    # Known acid-to-base groups form a descending proton ladder. Unknown/equal
    # counts follow with their recorded direction, rather than an inferred order.
    def _grp_sort_key(item):
        (frm, to), group = item
        if group["direction"] == "acid_to_base":
            return (0, -_state_proton_count(frm), frm, to)
        return (1, 0, frm, to)

    groups = OrderedDict(sorted(groups.items(), key=_grp_sort_key))

    # Compute per-transition stats + flatten VLM links
    summary_rows = []
    for (frm, to), g in groups.items():
        vals = [e["pKa"] for e in g["entries"] if e.get("pKa") is not None]
        g["count"] = len(g["entries"])
        g["pka_min"] = min(vals) if vals else None
        g["pka_max"] = max(vals) if vals else None
        g["pka_mean"] = mean(vals) if vals else None
        g["pka_median"] = median(vals) if vals else None
        seen: set[int] = set()
        for e in g["entries"]:
            for v in e.get("vlm_ids") or []:
                if v in seen:
                    continue
                seen.add(v)
                g["vlm_links"].append({
                    "vlm_id": v,
                    "stability_id": vlm_to_stability.get(v),
                })
        summary_rows.append({
            "from": frm, "to": to, "direction": g["direction"],
            "count": g["count"],
            "pka_min": g["pka_min"], "pka_max": g["pka_max"],
            "pka_mean": g["pka_mean"], "pka_median": g["pka_median"],
        })

    # Tallies for source / quality / conditions
    src_tally: dict[str, int] = defaultdict(int)
    quality_tally: dict[str, int] = defaultdict(int)
    temps, ions = [], []
    for r in rows:
        if r.get("source"): src_tally[r["source"]] += 1
        if r.get("quality"): quality_tally[r["quality"]] += 1
        if r.get("temperature_c") is not None:
            temps.append(r["temperature_c"])
        if r.get("ionic_strength_mol_l") is not None:
            ions.append(r["ionic_strength_mol_l"])

    overall = {
        "n_entries": len(rows),
        "n_transitions": len(groups),
        "pka_min": min((r["pKa"] for r in rows if r.get("pKa") is not None),
                       default=None),
        "pka_max": max((r["pKa"] for r in rows if r.get("pKa") is not None),
                       default=None),
        "T_min": min(temps) if temps else None,
        "T_max": max(temps) if temps else None,
        "I_min": min(ions) if ions else None,
        "I_max": max(ions) if ions else None,
        "sources": dict(src_tally),
        "quality": dict(quality_tally),
    }

    return render_template(
        "ligand_pka_detail.html",
        ligand=ligand,
        groups=list(groups.values()),
        summary=summary_rows,
        overall=overall,
    )
