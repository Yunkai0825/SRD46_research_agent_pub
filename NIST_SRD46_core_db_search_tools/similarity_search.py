"""
Ligand structural-similarity search.

Ranks ligands by MACCS/Morgan/Tversky similarity using the pre-computed
``srd46_ligand_fingerprints.db`` and enriches results with
equilibrium-map coverage from the equilibrium and cards databases.
"""

import logging
import math
import re
from numbers import Integral, Real
import sqlite3
import time
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from ._db_connection import get_cards_db, get_equilibrium_db, FINGERPRINT_DB
from workspace_setup import ensure_packaged_file
from .entity_search import search_ligands
from ._normalization_helpers.id_prefixer import (
    prefix_ids_in_row,
    prefix_ids_in_rows,
    unprefix_id,
)

log = logging.getLogger("SRD46")

SIMILARITY_METRICS = (
    "tanimoto_morgan",
    "tanimoto_maccs",
    "tversky_query_in_target",
    "tversky_target_in_query",
)
MAX_TOP_K = 100


def _positive_entity_id(value, kind: str) -> int:
    """Accept an integer or an exact canonical ID, without lossy coercion."""
    if isinstance(value, Integral) and not isinstance(value, bool) and 0 < value <= 2**63 - 1:
        return int(value)
    if isinstance(value, str):
        match = re.fullmatch(rf"(?:{kind}_)?([1-9][0-9]*)", value.strip())
        if match and len(match.group(1)) <= 19:
            numeric_id = int(match.group(1))
            if numeric_id <= 2**63 - 1:
                return numeric_id
    raise ValueError(f"{kind}_id must be in 1..{2**63 - 1}, as an integer or {kind}_N identifier")


def _validate_search_options(top_k, metric, min_similarity, metal_ids):
    if isinstance(top_k, bool) or not isinstance(top_k, Integral) or not 1 <= top_k <= MAX_TOP_K:
        raise ValueError(f"top_k must be an integer between 1 and {MAX_TOP_K}")
    if not isinstance(metric, str) or metric not in SIMILARITY_METRICS:
        raise ValueError(f"metric must be one of: {', '.join(SIMILARITY_METRICS)}")
    if (isinstance(min_similarity, bool) or not isinstance(min_similarity, Real)
            or not 0 <= min_similarity <= 1 or not math.isfinite(min_similarity)):
        raise ValueError("min_similarity must be a finite number between 0 and 1")
    if metal_ids is not None:
        if not isinstance(metal_ids, (list, tuple)):
            raise ValueError("metal_ids must be a list of metal identifiers")
        metal_ids = list(dict.fromkeys(_positive_entity_id(v, "metal") for v in metal_ids))
    return int(top_k), float(min_similarity), metal_ids


# The 1 GiB immutable corpus lives on a mapped SMB share in production.
# Fresh MCP workers can see the file before SQLite can acquire/open it; the
# former 0.35 s aggregate retry window was repeatedly too short in live LC1_3
# runs.  Keep retries bounded, read-only, and specific to the open error.
_FP_OPEN_ATTEMPTS = 6
_FP_OPEN_RETRY_BASE_SECONDS = 0.25


def _rows_to_dicts(cursor) -> list[dict]:
    return [dict(row) for row in cursor.fetchall()]


# ── fingerprint DB access ────────────────────────────────────────────

def _fingerprint_readonly_uri(path: Path) -> str:
    """Return a canonical SQLite URI for the immutable fingerprint corpus.

    Windows SQLite accepts a mapped drive as ``file:///N:/...``.  A UNC path
    needs a different spelling: :meth:`Path.as_uri` produces a non-empty URI
    authority (``file://server/share/...``), which standard SQLite rejects
    unless it was compiled with ``SQLITE_ALLOW_URI_AUTHORITY``.  Keep the UNC
    host in the path instead (``file:////server/share/...``), with an empty
    authority.  Percent-encoding also prevents spaces, ``#``, ``?``, or the
    ``$`` commonly present in Windows share names from changing URI parsing.
    """

    absolute = path.absolute()
    path_text = str(absolute)
    if path_text.startswith(("\\\\", "//")):
        # absolute.as_posix() starts with ``//server/share``; the extra
        # ``file://`` prefix deliberately yields four slashes after ``file:``.
        base_uri = "file://" + quote(absolute.as_posix(), safe="/:")
    else:
        base_uri = absolute.as_uri()
    return f"{base_uri}?mode=ro&immutable=1"


def _get_fp_db() -> sqlite3.Connection:
    path = FINGERPRINT_DB.absolute()
    ensure_packaged_file(path)
    if not path.is_file():
        raise FileNotFoundError(f"Fingerprint DB not found: {path}")
    uri = _fingerprint_readonly_uri(path)
    for attempt in range(_FP_OPEN_ATTEMPTS):
        try:
            conn = sqlite3.connect(uri, uri=True, timeout=5.0)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.OperationalError as exc:
            transient_open_error = "unable to open database file" in str(exc).lower()
            if not transient_open_error or attempt + 1 >= _FP_OPEN_ATTEMPTS:
                raise
            delay = _FP_OPEN_RETRY_BASE_SECONDS * (2 ** attempt)
            log.warning(
                "Fingerprint DB open failed (attempt %d/%d); retrying in %.2fs: %s",
                attempt + 1,
                _FP_OPEN_ATTEMPTS,
                delay,
                exc,
            )
            time.sleep(delay)


# ── resolve query ligand ─────────────────────────────────────────────

def _resolve_ligand_id(
    ligand_id: Optional[int | str] = None,
    ligand_name: Optional[str] = None,
) -> int:
    if ligand_id is not None:
        return _positive_entity_id(ligand_id, "ligand")
    if not isinstance(ligand_name, str) or not ligand_name.strip():
        raise ValueError("Provide either ligand_id or a nonempty ligand_name")
    # The database stores the neutral acid graph under its common acid name.
    # Resolve this exact common conjugate-base request without choosing a
    # methyl-citrate derivative or an isocitric-acid substring match.
    name = {"citrate": "citric acid"}.get(ligand_name.strip().casefold(), ligand_name.strip())
    hits = search_ligands(name=name, limit=5)
    results = hits.get("results", []) if isinstance(hits, dict) else hits
    if not results:
        raise ValueError(f"No ligand found for name={ligand_name!r}")
    exact_name = re.compile(r"(?:^|\()\s*" + re.escape(name) + r"\s*(?:\)|$)", re.IGNORECASE)
    exact_hits = [r for r in results if exact_name.search(r.get("ligand_name") or "")]
    if len(exact_hits) == 1:
        return unprefix_id(exact_hits[0]["ligand_id"])
    if len(results) > 1:
        candidates = ", ".join(str(r["ligand_id"]) for r in results)
        raise ValueError(f"Ambiguous ligand_name={ligand_name!r}; provide ligand_id (matches: {candidates})")
    return unprefix_id(results[0]["ligand_id"])


# ── similarity ranking ───────────────────────────────────────────────

def _fetch_top_similar(
    fp_db: sqlite3.Connection,
    query_id: int,
    top_k: int,
    metric: str = "tanimoto_morgan",
    min_similarity: float = 0.0,
) -> list[dict]:
    # Only validated column aliases enter SQL. Thresholds and IDs remain bound.
    top_k, min_similarity, _ = _validate_search_options(top_k, metric, min_similarity, None)
    sql = f"""
        SELECT * FROM (
            SELECT ligand_id_2 AS similar_id,
                   tanimoto_maccs, tanimoto_morgan,
                   tversky_morgan_1to2 AS tversky_query_in_target,
                   tversky_morgan_2to1 AS tversky_target_in_query
            FROM ligand_similarity
            WHERE ligand_id_1 = ? AND ligand_id_2 != ?
            UNION ALL
            SELECT ligand_id_1 AS similar_id,
                   tanimoto_maccs, tanimoto_morgan,
                   tversky_morgan_2to1 AS tversky_query_in_target,
                   tversky_morgan_1to2 AS tversky_target_in_query
            FROM ligand_similarity
            WHERE ligand_id_2 = ? AND ligand_id_1 != ?
        )
        WHERE {metric} IS NOT NULL AND {metric} >= ?
        ORDER BY {metric} DESC, similar_id ASC
        LIMIT ?
    """
    return _rows_to_dicts(fp_db.execute(sql, (query_id, query_id, query_id, query_id, min_similarity, top_k)))


# ── metadata enrichment ──────────────────────────────────────────────

def _fetch_ligand_info(cards_conn, ligand_ids: list[int]) -> dict[int, dict]:
    if not ligand_ids:
        return {}
    placeholders = ",".join("?" * len(ligand_ids))
    sql = f"""
        SELECT ligand_id, ligand_name_SRD AS ligand_name,
               ligand_SMILES AS smiles, definition_HxL AS HxL_canonical
        FROM   ligand_card
        WHERE  ligand_id IN ({placeholders})
    """
    rows = cards_conn.execute(sql, ligand_ids).fetchall()
    return {r["ligand_id"]: dict(r) for r in rows}


# ── equilibrium map richness ─────────────────────────────────────────

def _fetch_eq_richness(
    eq_conn: sqlite3.Connection,
    ligand_id: int,
    metal_ids: Optional[list[int]] = None,
) -> dict:
    metal_sql = """
        SELECT c.metal_id, c.metal_name, c.total_entries
        FROM   eq_map_collection c
        WHERE  c.ligand_id = ?
        ORDER BY c.total_entries DESC
    """
    metal_rows = [dict(r) for r in eq_conn.execute(metal_sql, (ligand_id,)).fetchall()]

    if metal_ids:
        mid_set = set(metal_ids)
        filtered_metals = [m for m in metal_rows if m["metal_id"] in mid_set]
    else:
        filtered_metals = metal_rows

    if metal_ids:
        placeholders = ",".join("?" * len(metal_ids))
        top_sql = f"""
            SELECT c.collection_id, c.metal_id, c.metal_name,
                   c.ligand_id, c.ligand_name, c.total_entries, c.total_networks
            FROM   eq_map_collection c
            WHERE  c.ligand_id = ?
              AND  c.metal_id IN ({placeholders})
            ORDER BY c.total_entries DESC
            LIMIT 10
        """
        top_rows = eq_conn.execute(top_sql, [ligand_id] + metal_ids).fetchall()
    else:
        top_sql = """
            SELECT c.collection_id, c.metal_id, c.metal_name,
                   c.ligand_id, c.ligand_name, c.total_entries, c.total_networks
            FROM   eq_map_collection c
            WHERE  c.ligand_id = ?
            ORDER BY c.total_entries DESC
            LIMIT 10
        """
        top_rows = eq_conn.execute(top_sql, (ligand_id,)).fetchall()

    beta_sql = """
        SELECT COUNT(DISTINCT nd.beta_definition_id) AS n_beta
        FROM   eq_node nd
        JOIN   eq_network nw ON nw.network_db_id = nd.network_db_id
        JOIN   eq_map m ON m.map_id = nw.map_id
        JOIN   eq_map_collection c ON c.collection_id = m.collection_id
        WHERE  c.ligand_id = ?
    """
    beta_params = [ligand_id]
    if metal_ids:
        beta_sql += " AND c.metal_id IN (" + ",".join("?" for _ in metal_ids) + ")"
        beta_params.extend(metal_ids)
    try:
        n_beta = eq_conn.execute(beta_sql, beta_params).fetchone()[0]
    except Exception:
        n_beta = None

    return {
        "metals_covered": filtered_metals,
        "n_metals": len(filtered_metals),
        "n_beta_defs": n_beta,
        "top_maps": [dict(r) for r in top_rows],
    }


# ── public API ───────────────────────────────────────────────────────

def search_similar_ligands(
    ligand_id: Optional[int | str] = None,
    ligand_name: Optional[str] = None,
    top_k: int = 10,
    metal_ids: Optional[list[int | str]] = None,
    *,
    metric: str = "tanimoto_morgan",
    min_similarity: float = 0.0,
) -> dict:
    """Rank other ligands using one of four stored fingerprint metrics.

    ``metric`` is tanimoto_morgan (default), tanimoto_maccs,
    tversky_query_in_target, or tversky_target_in_query. Tversky uses
    alpha=0.9/beta=0.1: query-in-target penalizes bits unique to the query
    more heavily; target-in-query reverses that direction. Fingerprint
    containment is not a substructure proof or an affinity prediction.

    ``top_k`` is an integer in 1..100. ``min_similarity`` is an inclusive
    finite threshold in [0, 1], applied before limiting at full precision.
    NULL selected scores and the query itself are excluded. Ties use ID
    order. ``metal_ids`` filters equilibrium coverage, not structure ranks.

    Existing family_score (MACCS) and similarity_score (Morgan) retain
    their meanings; ranking_score corresponds to the selected metric.
    All displayed scores are rounded to four decimals. A valid query with
    no qualifying hits returns an empty list without a fingerprint error.
    """
    top_k, min_similarity, metal_ids = _validate_search_options(top_k, metric, min_similarity, metal_ids)
    qid = _resolve_ligand_id(ligand_id, ligand_name)
    log.info("Similarity search: query ligand_id=%d, top_k=%d, metric=%s, min_similarity=%s, metal_ids=%s",
             qid, top_k, metric, min_similarity, metal_ids)

    fp_db = _get_fp_db()
    try:
        query_fp = fp_db.execute("SELECT fp_status AS status FROM ligand_fingerprint WHERE ligand_id = ?", (qid,)).fetchone()
        if query_fp is None or query_fp["status"] != "ok":
            return {
                "query_ligand": {"ligand_id": f"ligand_{qid}"},
                "error": ("Ligand was not found in the fingerprint database." if query_fp is None
                          else "No usable fingerprint data available for this ligand."),
                "error_code": "ligand_not_found" if query_fp is None else "no_fingerprint_data",
                "fingerprint_status": query_fp["status"] if query_fp is not None else None,
                "metric": metric, "min_similarity": min_similarity,
                "similar_ligands": [],
            }
        ranked = _fetch_top_similar(fp_db, qid, top_k, metric, min_similarity)
    finally:
        fp_db.close()

    all_ids = [qid] + [r["similar_id"] for r in ranked]

    with get_cards_db() as cards_conn:
        info_map = _fetch_ligand_info(cards_conn, all_ids)

    query_info = info_map.get(qid, {"ligand_id": qid})

    with get_equilibrium_db() as eq_conn:
        query_richness = _fetch_eq_richness(eq_conn, qid, metal_ids)

        results = []
        for r in ranked:
            sid = r["similar_id"]
            lig_info = info_map.get(sid, {"ligand_id": sid})
            eq_rich = _fetch_eq_richness(eq_conn, sid, metal_ids)

            results.append({
                "ligand_id": sid,
                "ligand_name": lig_info.get("ligand_name"),
                "smiles": lig_info.get("smiles"),
                "HxL_canonical": lig_info.get("HxL_canonical"),
                "family_score": (round(r["tanimoto_maccs"], 4)
                                 if r["tanimoto_maccs"] is not None else None),
                "similarity_score": (round(r["tanimoto_morgan"], 4)
                                     if r["tanimoto_morgan"] is not None else None),
                "ranking_score": round(r[metric], 4),
                "tversky_query_in_target": round(r["tversky_query_in_target"], 4)
                    if r["tversky_query_in_target"] is not None else None,
                "tversky_target_in_query": round(r["tversky_target_in_query"], 4)
                    if r["tversky_target_in_query"] is not None else None,
                "eq_richness": eq_rich,
            })

    # ── Prefix IDs in all nested structures ──
    prefix_ids_in_row(query_info)
    prefix_ids_in_rows(query_richness.get("metals_covered", []))
    prefix_ids_in_rows(query_richness.get("top_maps", []))
    for sim in results:
        prefix_ids_in_row(sim)
        eq_r = sim.get("eq_richness", {})
        prefix_ids_in_rows(eq_r.get("metals_covered", []))
        prefix_ids_in_rows(eq_r.get("top_maps", []))

    response = {
        "metric": metric,
        "min_similarity": min_similarity,
        "query_ligand": query_info,
        "query_eq_richness": query_richness,
        "metal_filter": [f"metal_{m}" for m in metal_ids] if metal_ids else metal_ids,
        "similar_ligands": results,
    }

    if not results:
        response["message"] = "No other ligands meet the selected metric and minimum similarity."
    return response
