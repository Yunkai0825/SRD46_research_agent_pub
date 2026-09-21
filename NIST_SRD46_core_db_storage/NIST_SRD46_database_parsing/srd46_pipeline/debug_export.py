"""Debug mode: mirror every intermediate artifact of a stage from the staging store to plain files."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Tuple

from .staging import rows_to_csv_text

if TYPE_CHECKING:  # avoid the import cycle with runner (which imports this module)
    from .runner import Context


def export_stage_debug(ctx: "Context", stage: str) -> Tuple[int, Path]:
    """Write ``<output-dir>/debug/<stage>/`` from the staging content of ``stage``.

    Files: one ``<table>.csv`` per staging table, one ``<key>.json`` per stats entry, ``stage.log``
    (captured output of the wrapped modules), ``stage_info.json`` (status, timing, summary) and
    ``manual_fix_log.csv`` (ledger rows the stage wrote). The folder is rebuilt from scratch so it
    never holds files of an earlier run. Returns (number of files written, folder).
    """
    st = ctx.staging
    out = ctx.paths.debug_dir / stage
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for info in st.list_tables(stage):
        name = info["name"]
        path = out / f"{name}.csv"
        if info["kind"] == "df":
            st.read_df(name).to_csv(path, index=False, encoding="utf-8")
        else:
            fieldnames, rows = st.read_rows(name)
            path.write_text(rows_to_csv_text(rows, fieldnames), encoding="utf-8", newline="")
        n += 1
    for key, value_json in st.conn.execute("SELECT key, value_json FROM _kv WHERE stage=? ORDER BY key", (stage,)):
        (out / f"{key}.json").write_text(json.dumps(json.loads(value_json), indent=2, ensure_ascii=False),
                                         encoding="utf-8")
        n += 1
    row = st.conn.execute("SELECT log FROM _stage_logs WHERE stage=?", (stage,)).fetchone()
    if row is not None:
        (out / "stage.log").write_text(row[0] or "", encoding="utf-8")
        n += 1
    info = st.stage_info(stage)
    if info is not None:
        (out / "stage_info.json").write_text(json.dumps(info, indent=2, ensure_ascii=False, default=str),
                                             encoding="utf-8")
        n += 1
    cur = st.conn.execute("SELECT * FROM manual_fix_log WHERE stage=?", (stage,))
    fixes = cur.fetchall()
    if fixes:
        cols = [d[0] for d in cur.description]
        (out / "manual_fix_log.csv").write_text(rows_to_csv_text([dict(zip(cols, r)) for r in fixes], cols),
                                                encoding="utf-8", newline="")
        n += 1
    return n, out
