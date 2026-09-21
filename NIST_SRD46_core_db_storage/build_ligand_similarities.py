"""Compute pairwise Tanimoto & Tversky similarities and add them to the fingerprint DB.

Reads ``srd46_ligand_fingerprints.db``, computes Tanimoto and Tversky
coefficients for every ligand pair (MACCS-166 and Morgan-2048), and
writes a ``ligand_similarity`` table into the same database.

Columns stored per pair:
  - tanimoto_maccs         symmetric Tanimoto on MACCS-166
  - tanimoto_morgan        symmetric Tanimoto on Morgan-2048
  - tversky_morgan_1to2    Tversky(fp_1, fp_2, α=0.9, β=0.1)
                           "how much of ligand_1 is retained in ligand_2"
  - tversky_morgan_2to1    Tversky(fp_2, fp_1, α=0.9, β=0.1)
                           "how much of ligand_2 is retained in ligand_1"

Only the upper triangle is stored (ligand_id_1 <= ligand_id_2) to avoid
redundancy.  Diagonal entries (self-similarity) are 1.0 for ligands
with fingerprints.  Pairs involving a ligand without fingerprints get
NULL similarity values.

Usage
-----
    python build_ligand_similarities.py                 # default path
    python build_ligand_similarities.py --db fp.db      # custom path
    python build_ligand_similarities.py --batch 5000    # tune batch size
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
import time
from pathlib import Path

from rdkit.DataStructs import (
    CreateFromBitString,
    BulkTanimotoSimilarity,
    BulkTverskySimilarity,
    ExplicitBitVect,
)

log = logging.getLogger("sim-builder")

_THIS_DIR = Path(__file__).absolute().parent
_DEFAULT_DB = _THIS_DIR / "srd46_ligand_fingerprints.db"

INSERT_BATCH = 50_000  # rows per executemany commit

# Tversky asymmetry weights
# α high → query-weighted ("how much of the query is retained in the target")
TVERSKY_ALPHA = 0.9
TVERSKY_BETA  = 0.1


# ── helpers ──────────────────────────────────────────────────────────

def _bitstring_to_bv(bitstring: str) -> ExplicitBitVect:
    """Reconstruct an RDKit ExplicitBitVect from a '0'/'1' bit string."""
    return CreateFromBitString(bitstring)


def _load_fingerprints(db: sqlite3.Connection):
    """Return (ordered_ids, maccs_dict, morgan_dict).

    *ordered_ids* is a sorted list of every ligand_id.
    *maccs_dict* / *morgan_dict* map ligand_id → ExplicitBitVect
    (only for ligands with fp_status='ok').
    """
    cur = db.execute(
        "SELECT ligand_id, maccs_fingerprint, morgan_fingerprint, fp_status "
        "FROM ligand_fingerprint ORDER BY ligand_id"
    )
    ids: list[int] = []
    maccs: dict[int, ExplicitBitVect] = {}
    morgan: dict[int, ExplicitBitVect] = {}

    for lid, m_bits, g_bits, status in cur:
        ids.append(lid)
        if status == "ok" and m_bits and g_bits:
            maccs[lid] = _bitstring_to_bv(m_bits)
            morgan[lid] = _bitstring_to_bv(g_bits)

    return ids, maccs, morgan


# ── main build ───────────────────────────────────────────────────────

def build(db_path: Path, batch_size: int = INSERT_BATCH) -> None:
    log.info("Opening %s", db_path)
    db = sqlite3.connect(str(db_path))

    ids, maccs_map, morgan_map = _load_fingerprints(db)
    n = len(ids)
    n_ok = len(maccs_map)
    log.info("Loaded %d ligands (%d with fingerprints)", n, n_ok)

    # Pre-compute ordered lists for BulkTanimoto
    ok_ids = sorted(maccs_map)
    ok_maccs = [maccs_map[i] for i in ok_ids]
    ok_morgan = [morgan_map[i] for i in ok_ids]
    ok_id_set = set(ok_ids)

    # id → positional index in ok_* lists
    ok_pos = {lid: idx for idx, lid in enumerate(ok_ids)}

    # Drop old table if re-running
    db.execute("DROP TABLE IF EXISTS ligand_similarity")
    db.execute("""
        CREATE TABLE ligand_similarity (
            ligand_id_1          INTEGER NOT NULL,
            ligand_id_2          INTEGER NOT NULL,
            tanimoto_maccs       REAL,
            tanimoto_morgan      REAL,
            tversky_morgan_1to2  REAL,
            tversky_morgan_2to1  REAL,
            PRIMARY KEY (ligand_id_1, ligand_id_2)
        )
    """)
    db.execute("CREATE INDEX idx_sim_id2 ON ligand_similarity(ligand_id_2)")

    total_pairs = n * (n + 1) // 2
    log.info("Computing %d upper-triangle pairs …", total_pairs)

    t0 = time.perf_counter()
    batch: list[tuple] = []
    written = 0

    for row_num, id_i in enumerate(ids):
        has_i = id_i in ok_id_set

        if has_i:
            pos_i = ok_pos[id_i]
            # BulkTanimoto against ALL ok ligands at once (very fast in C++)
            maccs_sims = BulkTanimotoSimilarity(ok_maccs[pos_i], ok_maccs)
            morgan_sims = BulkTanimotoSimilarity(ok_morgan[pos_i], ok_morgan)
            # Tversky: forward (i→j, α=0.9) and reverse (j→i via swapped weights)
            tv_fwd = BulkTverskySimilarity(ok_morgan[pos_i], ok_morgan,
                                           TVERSKY_ALPHA, TVERSKY_BETA)
            tv_rev = BulkTverskySimilarity(ok_morgan[pos_i], ok_morgan,
                                           TVERSKY_BETA, TVERSKY_ALPHA)
            # Build lookups from ok_id → similarity
            maccs_lut  = {ok_ids[k]: maccs_sims[k]  for k in range(n_ok)}
            morgan_lut = {ok_ids[k]: morgan_sims[k] for k in range(n_ok)}
            tv_fwd_lut = {ok_ids[k]: tv_fwd[k]      for k in range(n_ok)}
            tv_rev_lut = {ok_ids[k]: tv_rev[k]      for k in range(n_ok)}

        # Only emit pairs where id_i <= id_j  (upper triangle)
        for id_j in ids[row_num:]:
            if not has_i or id_j not in ok_id_set:
                batch.append((id_i, id_j, None, None, None, None))
            else:
                batch.append((id_i, id_j,
                              maccs_lut[id_j], morgan_lut[id_j],
                              tv_fwd_lut[id_j], tv_rev_lut[id_j]))

        if len(batch) >= batch_size:
            db.executemany(
                "INSERT INTO ligand_similarity VALUES (?,?,?,?,?,?)", batch
            )
            db.commit()
            written += len(batch)
            batch.clear()
            elapsed = time.perf_counter() - t0
            pct = written / total_pairs * 100
            log.info("  %d / %d  (%.1f%%)  %.0fs elapsed", written, total_pairs, pct, elapsed)

    if batch:
        db.executemany("INSERT INTO ligand_similarity VALUES (?,?,?,?,?,?)", batch)
        db.commit()
        written += len(batch)

    elapsed = time.perf_counter() - t0
    log.info("Done — %d rows written in %.1fs", written, elapsed)

    # Quick sanity counts
    cnt = db.execute("SELECT COUNT(*) FROM ligand_similarity").fetchone()[0]
    null_cnt = db.execute(
        "SELECT COUNT(*) FROM ligand_similarity WHERE tanimoto_maccs IS NULL"
    ).fetchone()[0]
    log.info("Table ligand_similarity: %d rows (%d NULL pairs)", cnt, null_cnt)

    db.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Build pairwise Tanimoto similarity table")
    ap.add_argument("--db", type=Path, default=_DEFAULT_DB,
                    help="Path to srd46_ligand_fingerprints.db")
    ap.add_argument("--batch", type=int, default=INSERT_BATCH,
                    help="Rows per INSERT batch (default 50000)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-5s | %(message)s",
    )
    build(args.db, args.batch)


if __name__ == "__main__":
    main()
