"""Stage literature: normalised literature database from the original SRD-46 MySQL dump -> srd46_literature.db."""
from __future__ import annotations

import sqlite3
from typing import Any, Dict

from srd46_pipeline.legacy import load_script
from srd46_pipeline.paths import LEGACY_SCRIPTS
from srd46_pipeline.publish import publish, temp_path
from srd46_pipeline.runner import Context
from srd46_pipeline.sources import read_source_table

STAGE = "literature_db"
LOADERS = ["literature_alt", "paper", "literature", "author", "footnote",
           "verk_literature_author", "vlm_literature", "vlm_literature_sic"]   # FK order


def _read_source_rows(name: str) -> tuple[list[str], list[list[str]]]:
    """Adapt ordered MySQL fields to the existing literature loaders without coercion."""
    columns, rows = read_source_table(name)
    return columns, [[row[column] for column in columns] for row in rows]


def run(ctx: Context) -> Dict[str, Any]:
    mod = load_script(LEGACY_SCRIPTS["literature"], "srd46_legacy_literature")
    mod.read_csv = _read_source_rows

    lit_db = ctx.paths.lit_db
    lit_db.parent.mkdir(parents=True, exist_ok=True)
    tmp = temp_path(lit_db)
    stats: Dict[str, int] = {}
    conn = sqlite3.connect(str(tmp))
    try:
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.execute("PRAGMA synchronous=OFF")
        conn.execute("PRAGMA foreign_keys=OFF")      # 1 known orphan link in the source data is kept as is
        cur = conn.cursor()
        cur.executescript(mod.SCHEMA_SQL)
        conn.commit()
        for name in LOADERS:
            n = getattr(mod, f"load_{name}")(cur)
            conn.commit()
            stats[name] = int(n)
            ctx.log(f"literature: {name}: {n:,} rows")
        conn.execute("PRAGMA synchronous=FULL")
        conn.commit()
    finally:
        conn.close()
    publish(tmp, lit_db)
    ctx.staging.put_json("literature_stats", stats, STAGE)
    return {**stats, "db": str(lit_db)}
