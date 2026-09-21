#!/usr/bin/env python3
"""
Generate srd46_literature.db – a standalone, fully normalised literature database
built directly from the SRD-46 source CSV exports.

Tables
──────
  literature_alt        18 297  short-code citations  (primary citation mechanism)
  literature               1   full literature entry  (sparse in SRD-46)
  paper               4 429   journal / paper names
  author                135   author records
  footnote              135   footnote records
  verk_literature_author   1   literature ↔ author mapping
  vlm_literature       79 956  ligand+metal ↔ literature link  (by ligandenNr/metalNr)
  vlm_literature_sic  721 906  vlm ↔ literature link           (by verkn_ligand_metalNr)

All IDs, foreign-key constraints, and indexes mirror the original SRD-46 schema.
"""

from __future__ import annotations

import csv
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── paths ────────────────────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).resolve().parent.parent          # project root
CSV_DIR   = BASE_DIR / "_input" / "SRD46_SQL_and_CSV" / "Export" / "CSV files"
OUT_DIR   = BASE_DIR / "_output" / "pip2c_cards_sql"
DB_PATH   = OUT_DIR / "srd46_literature.db"

# source file mapping  (logical name → filename)
CSV_FILES = {
    "literature_alt":                   "literature_alt__10.csv",
    "literature":                       "literature__9__13.csv",
    "paper":                            "paper__13.csv",
    "author":                           "author__1.csv",
    "footnote":                         "footnote__6.csv",
    "verk_literature_author":           "verk_literature_author__15__9-1.csv",
    "verkn_ligand_metal_literature":     "verkn_ligand_metal_literature__17__8-11-9-10.csv",
    "verkn_ligand_metal_literature_sic": "verkn_ligand_metal_literature_sic__18__16-9-10.csv",
}

NULL_SENTINELS = {"\\N", "\\n", ""}


# ── CSV reader ───────────────────────────────────────────────────────────────
def read_csv(name: str) -> Tuple[List[str], List[List[str]]]:
    """Return (header, rows) for a source CSV.  Handles BOM and comma delimiter."""
    path = CSV_DIR / CSV_FILES[name]
    if not path.exists():
        print(f"  [WARN] CSV not found: {path}")
        return [], []

    with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
        reader = csv.reader(fh, delimiter=",")
        header = next(reader, None)
        if header is None:
            return [], []
        # strip whitespace from column names
        header = [h.strip() for h in header]
        rows = [r for r in reader if any(c.strip() for c in r)]
    return header, rows


def _val(raw: str) -> Optional[str]:
    """Return None for NULL sentinels, otherwise stripped value."""
    v = raw.strip()
    return None if v in NULL_SENTINELS else v


def _int(raw: str) -> Optional[int]:
    v = _val(raw)
    if v is None:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def _int_or_null(raw: str) -> Optional[int]:
    """Like _int but also treats 0 as None (used for FK columns where 0 means 'no link')."""
    v = _int(raw)
    return None if v == 0 else v


# ── schema ───────────────────────────────────────────────────────────────────
SCHEMA_SQL = """
-- =====================================================================
-- Reference entity tables
-- =====================================================================

CREATE TABLE IF NOT EXISTS literature_alt (
    literature_alt_id   INTEGER PRIMARY KEY,
    citation            TEXT,
    shortcut            TEXT,
    comment             TEXT
);

CREATE TABLE IF NOT EXISTS literature (
    literature_id   INTEGER PRIMARY KEY,
    paper_id        INTEGER,
    year            INTEGER,
    issue           INTEGER,
    page            INTEGER,
    comment         TEXT,
    FOREIGN KEY (paper_id) REFERENCES paper(paper_id)
);

CREATE TABLE IF NOT EXISTS paper (
    paper_id    INTEGER PRIMARY KEY,
    name        TEXT,
    publisher   TEXT,
    comment     TEXT
);

CREATE TABLE IF NOT EXISTS author (
    author_id   INTEGER PRIMARY KEY,
    name        TEXT,
    email       TEXT,
    comment     TEXT
);

CREATE TABLE IF NOT EXISTS footnote (
    footnote_id INTEGER PRIMARY KEY,
    text        TEXT,
    shortcut    TEXT,
    comment     TEXT
);

-- =====================================================================
-- Linkage / junction tables
-- =====================================================================

CREATE TABLE IF NOT EXISTS verk_literature_author (
    id              INTEGER PRIMARY KEY,
    literature_id   INTEGER NOT NULL,
    author_id       INTEGER NOT NULL,
    comment         TEXT,
    UNIQUE(literature_id, author_id),
    FOREIGN KEY (literature_id) REFERENCES literature(literature_id),
    FOREIGN KEY (author_id)     REFERENCES author(author_id)
);

-- Link table keyed by (ligandenNr, metalNr)
CREATE TABLE IF NOT EXISTS vlm_literature (
    id                  INTEGER PRIMARY KEY,
    ligand_id           INTEGER NOT NULL,
    metal_id            INTEGER NOT NULL,
    literature_id       INTEGER,
    literature_alt_id   INTEGER,
    not_used            INTEGER,
    comment             TEXT,
    FOREIGN KEY (literature_id)     REFERENCES literature(literature_id),
    FOREIGN KEY (literature_alt_id) REFERENCES literature_alt(literature_alt_id)
);

-- Link table keyed by verkn_ligand_metalNr (vlm_id)
CREATE TABLE IF NOT EXISTS vlm_literature_sic (
    id                  INTEGER PRIMARY KEY,
    vlm_id              INTEGER NOT NULL,
    literature_id       INTEGER,
    literature_alt_id   INTEGER,
    not_used            INTEGER,
    comment             TEXT,
    FOREIGN KEY (literature_id)     REFERENCES literature(literature_id),
    FOREIGN KEY (literature_alt_id) REFERENCES literature_alt(literature_alt_id)
);

-- =====================================================================
-- Indexes
-- =====================================================================

CREATE INDEX IF NOT EXISTS idx_lit_alt_shortcut       ON literature_alt(shortcut);
CREATE INDEX IF NOT EXISTS idx_literature_paper        ON literature(paper_id);
CREATE INDEX IF NOT EXISTS idx_vlm_lit_ligand_metal    ON vlm_literature(ligand_id, metal_id);
CREATE INDEX IF NOT EXISTS idx_vlm_lit_lit_id          ON vlm_literature(literature_id);
CREATE INDEX IF NOT EXISTS idx_vlm_lit_lit_alt_id      ON vlm_literature(literature_alt_id);
CREATE INDEX IF NOT EXISTS idx_vlm_sic_vlm             ON vlm_literature_sic(vlm_id);
CREATE INDEX IF NOT EXISTS idx_vlm_sic_lit_id          ON vlm_literature_sic(literature_id);
CREATE INDEX IF NOT EXISTS idx_vlm_sic_lit_alt_id      ON vlm_literature_sic(literature_alt_id);
CREATE INDEX IF NOT EXISTS idx_vla_lit                  ON verk_literature_author(literature_id);
CREATE INDEX IF NOT EXISTS idx_vla_author               ON verk_literature_author(author_id);
"""


# ── loaders ──────────────────────────────────────────────────────────────────
def load_literature_alt(cur: sqlite3.Cursor) -> int:
    """literature_altID, literature_alt, literature_shortcut, comment, Acc_feld"""
    header, rows = read_csv("literature_alt")
    count = 0
    for r in rows:
        if len(r) < 3:
            continue
        lid = _int(r[0])
        if lid is None:
            continue
        cur.execute(
            "INSERT OR IGNORE INTO literature_alt (literature_alt_id, citation, shortcut, comment) VALUES (?,?,?,?)",
            (lid, _val(r[1]), _val(r[2]), _val(r[3]) if len(r) > 3 else None),
        )
        count += 1
    return count


def load_literature(cur: sqlite3.Cursor) -> int:
    """literatureID, paperNr, year, issue, page, comment, Acc_feld"""
    header, rows = read_csv("literature")
    count = 0
    for r in rows:
        if len(r) < 5:
            continue
        lid = _int(r[0])
        if lid is None:
            continue
        cur.execute(
            "INSERT OR IGNORE INTO literature (literature_id, paper_id, year, issue, page, comment) VALUES (?,?,?,?,?,?)",
            (lid, _int(r[1]), _int(r[2]), _int(r[3]), _int(r[4]),
             _val(r[5]) if len(r) > 5 else None),
        )
        count += 1
    return count


def load_paper(cur: sqlite3.Cursor) -> int:
    """paperID, name_paper, publisher, comment, Acc_feld"""
    header, rows = read_csv("paper")
    count = 0
    for r in rows:
        if len(r) < 2:
            continue
        pid = _int(r[0])
        if pid is None:
            continue
        cur.execute(
            "INSERT OR IGNORE INTO paper (paper_id, name, publisher, comment) VALUES (?,?,?,?)",
            (pid, _val(r[1]), _val(r[2]) if len(r) > 2 else None,
             _val(r[3]) if len(r) > 3 else None),
        )
        count += 1
    return count


def load_author(cur: sqlite3.Cursor) -> int:
    """authorID, name_author, email, comment, Acc_feld"""
    header, rows = read_csv("author")
    count = 0
    for r in rows:
        if len(r) < 2:
            continue
        aid = _int(r[0])
        if aid is None:
            continue
        cur.execute(
            "INSERT OR IGNORE INTO author (author_id, name, email, comment) VALUES (?,?,?,?)",
            (aid, _val(r[1]), _val(r[2]) if len(r) > 2 else None,
             _val(r[3]) if len(r) > 3 else None),
        )
        count += 1
    return count


def load_footnote(cur: sqlite3.Cursor) -> int:
    """footnoteID, name_footnote, shortcut, comment, Acc_feld"""
    header, rows = read_csv("footnote")
    count = 0
    for r in rows:
        if len(r) < 3:
            continue
        fid = _int(r[0])
        if fid is None:
            continue
        cur.execute(
            "INSERT OR IGNORE INTO footnote (footnote_id, text, shortcut, comment) VALUES (?,?,?,?)",
            (fid, _val(r[1]), _val(r[2]),
             _val(r[3]) if len(r) > 3 else None),
        )
        count += 1
    return count


def load_verk_literature_author(cur: sqlite3.Cursor) -> int:
    """verkn_literature_authorID, literatureNr, authorNr, comment, Acc_feld"""
    header, rows = read_csv("verk_literature_author")
    count = 0
    for r in rows:
        if len(r) < 3:
            continue
        rid = _int(r[0])
        if rid is None:
            continue
        cur.execute(
            "INSERT OR IGNORE INTO verk_literature_author (id, literature_id, author_id, comment) VALUES (?,?,?,?)",
            (rid, _int(r[1]), _int(r[2]),
             _val(r[3]) if len(r) > 3 else None),
        )
        count += 1
    return count


def load_vlm_literature(cur: sqlite3.Cursor) -> int:
    """verkn_ligand_metal_literatureID, ligandenNr, metalNr, literatureNr,
       literature_altNr, not_used, comment, Acc_feld"""
    header, rows = read_csv("verkn_ligand_metal_literature")
    count = 0
    batch: list = []
    for r in rows:
        if len(r) < 5:
            continue
        rid = _int(r[0])
        if rid is None:
            continue
        batch.append((
            rid, _int(r[1]), _int(r[2]), _int_or_null(r[3]), _int_or_null(r[4]),
            _int(r[5]) if len(r) > 5 else None,
            _val(r[6]) if len(r) > 6 else None,
        ))
        if len(batch) >= 5000:
            cur.executemany(
                "INSERT OR IGNORE INTO vlm_literature "
                "(id, ligand_id, metal_id, literature_id, literature_alt_id, not_used, comment) "
                "VALUES (?,?,?,?,?,?,?)",
                batch,
            )
            count += len(batch)
            batch.clear()
    if batch:
        cur.executemany(
            "INSERT OR IGNORE INTO vlm_literature "
            "(id, ligand_id, metal_id, literature_id, literature_alt_id, not_used, comment) "
            "VALUES (?,?,?,?,?,?,?)",
            batch,
        )
        count += len(batch)
    return count


def load_vlm_literature_sic(cur: sqlite3.Cursor) -> int:
    """verkn_ligand_metal_literatureID, verkn_ligand_metalNr, literatureNr,
       literature_altNr, not_used, comment, Acc_feld"""
    header, rows = read_csv("verkn_ligand_metal_literature_sic")
    count = 0
    batch: list = []
    for r in rows:
        if len(r) < 4:
            continue
        rid = _int(r[0])
        if rid is None:
            continue
        batch.append((
            rid, _int(r[1]), _int_or_null(r[2]), _int_or_null(r[3]),
            _int(r[4]) if len(r) > 4 else None,
            _val(r[5]) if len(r) > 5 else None,
        ))
        if len(batch) >= 10000:
            cur.executemany(
                "INSERT OR IGNORE INTO vlm_literature_sic "
                "(id, vlm_id, literature_id, literature_alt_id, not_used, comment) "
                "VALUES (?,?,?,?,?,?)",
                batch,
            )
            count += len(batch)
            batch.clear()
    if batch:
        cur.executemany(
            "INSERT OR IGNORE INTO vlm_literature_sic "
            "(id, vlm_id, literature_id, literature_alt_id, not_used, comment) "
            "VALUES (?,?,?,?,?,?)",
            batch,
        )
        count += len(batch)
    return count


# ── main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    t0 = time.time()
    print(f"Generating {DB_PATH.name}")
    print(f"  Source CSVs : {CSV_DIR}")
    print(f"  Output      : {DB_PATH}")
    print()

    # Ensure output dir exists
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Remove old DB
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    # FK enforcement deferred until after bulk load (1 known orphan in source data)
    conn.execute("PRAGMA foreign_keys=OFF")
    cur = conn.cursor()

    # Create schema
    cur.executescript(SCHEMA_SQL)
    conn.commit()

    # Load entity tables (order matters for FK references)
    loaders = [
        ("literature_alt",          load_literature_alt),
        ("paper",                   load_paper),
        ("literature",              load_literature),
        ("author",                  load_author),
        ("footnote",                load_footnote),
        ("verk_literature_author",  load_verk_literature_author),
        ("vlm_literature",          load_vlm_literature),
        ("vlm_literature_sic",      load_vlm_literature_sic),
    ]

    stats: Dict[str, int] = {}
    for name, loader in loaders:
        print(f"  Loading {name} ...", end=" ", flush=True)
        n = loader(cur)
        conn.commit()
        stats[name] = n
        print(f"{n:,} rows")

    # Print summary
    elapsed = time.time() - t0
    print(f"\n{'─' * 50}")
    print(f"Database created: {DB_PATH}")
    print(f"Elapsed: {elapsed:.1f}s")
    print()

    # Verification
    print("Table row counts:")
    for tbl in [
        "literature_alt", "literature", "paper", "author", "footnote",
        "verk_literature_author", "vlm_literature", "vlm_literature_sic",
    ]:
        cnt = cur.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f"  {tbl:30s}  {cnt:>10,}")

    # Quick integrity checks
    print()
    orphan_lit = cur.execute("""
        SELECT COUNT(*) FROM vlm_literature v
        LEFT JOIN literature_alt la ON v.literature_alt_id = la.literature_alt_id
        WHERE v.literature_alt_id IS NOT NULL AND v.literature_alt_id != 0 AND la.literature_alt_id IS NULL
    """).fetchone()[0]
    print(f"  vlm_literature → literature_alt orphans: {orphan_lit}")

    orphan_sic = cur.execute("""
        SELECT COUNT(*) FROM vlm_literature_sic v
        LEFT JOIN literature_alt la ON v.literature_alt_id = la.literature_alt_id
        WHERE v.literature_alt_id IS NOT NULL AND v.literature_alt_id != 0 AND la.literature_alt_id IS NULL
    """).fetchone()[0]
    print(f"  vlm_literature_sic → literature_alt orphans: {orphan_sic}")

    orphan_paper = cur.execute("""
        SELECT COUNT(*) FROM literature l
        LEFT JOIN paper p ON l.paper_id = p.paper_id
        WHERE l.paper_id IS NOT NULL AND p.paper_id IS NULL
    """).fetchone()[0]
    print(f"  literature → paper orphans: {orphan_paper}")

    # Sample queries
    print()
    print("Sample literature_alt entries:")
    for row in cur.execute("SELECT * FROM literature_alt LIMIT 3").fetchall():
        print(f"  {row}")

    print()
    print("Sample vlm_literature links (ligand+metal → lit_alt):")
    for row in cur.execute("""
        SELECT v.id, v.ligand_id, v.metal_id, la.shortcut, la.citation
        FROM vlm_literature v
        JOIN literature_alt la ON v.literature_alt_id = la.literature_alt_id
        LIMIT 3
    """).fetchall():
        print(f"  {row}")

    print()
    print("Sample vlm_literature_sic links (vlm_id → lit_alt):")
    for row in cur.execute("""
        SELECT v.id, v.vlm_id, la.shortcut, la.citation
        FROM vlm_literature_sic v
        JOIN literature_alt la ON v.literature_alt_id = la.literature_alt_id
        LIMIT 3
    """).fetchall():
        print(f"  {row}")

    conn.close()
    print(f"\nDone.  {DB_PATH.stat().st_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
