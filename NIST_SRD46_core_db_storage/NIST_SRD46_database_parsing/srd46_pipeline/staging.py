"""
Staging store: one SQLite file that carries every intermediate between stages.

Two table kinds are supported, mirroring the two data shapes the parser modules use:

* ``df``   - pandas DataFrames. Column dtypes are recorded in a manifest so a table
             reads back with the same dtypes (bool/Int64/int64/float64/string/object).
* ``rows`` - ``csv.DictReader``-style lists of string dicts (all TEXT).

Modules that expect CSV files are fed through an in-memory CSV round trip
(``df_csv_roundtrip`` / ``rows_to_csv_text``) so they see byte-for-byte what they
would have read from disk.
"""
from __future__ import annotations

import csv
import io
import json
import math
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

_META_SQL = """
CREATE TABLE IF NOT EXISTS _tables (
    name TEXT PRIMARY KEY, stage TEXT, kind TEXT, n_rows INTEGER, n_cols INTEGER,
    columns_json TEXT, dtypes_json TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS _kv (key TEXT PRIMARY KEY, stage TEXT, value_json TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS _stages (
    name TEXT PRIMARY KEY, status TEXT, started_at TEXT, finished_at TEXT,
    elapsed_s REAL, detail_json TEXT, error TEXT);
CREATE TABLE IF NOT EXISTS _stage_logs (stage TEXT, run_at TEXT, log TEXT);
CREATE TABLE IF NOT EXISTS pubchem_name_cache (
    name TEXT PRIMARY KEY, status TEXT, cid TEXT, molblock TEXT, source TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS pubchem_smiles_names_cache (
    smiles TEXT PRIMARY KEY, status TEXT, iupac TEXT, title TEXT, error TEXT, source TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS manual_fix_log (
    stage TEXT, table_name TEXT, record_id TEXT, field TEXT, old_value TEXT, new_value TEXT,
    reason TEXT, source TEXT, status TEXT);
"""

_RESERVED = {"_tables", "_kv", "_stages", "_stage_logs", "pubchem_name_cache",
             "pubchem_smiles_names_cache", "manual_fix_log"}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _q(ident: str) -> str:
    return '"' + ident.replace('"', '""') + '"'


def _sanitize_columns(cols: Sequence[Any]) -> List[str]:
    """SQL-safe, unique (case-insensitively - SQLite folds case) column names; originals kept in the manifest."""
    out: List[str] = []
    used: set = set()
    for c in cols:
        s = str(c).replace("\ufeff", "").strip() or "_blank"
        base, n = s, 1
        while s.lower() in used:
            n += 1
            s = f"{base}__{n}"
        used.add(s.lower())
        out.append(s)
    return out


def _dtype_tag(series: pd.Series) -> str:
    d = series.dtype
    if isinstance(d, pd.BooleanDtype):
        return "boolean"
    if pd.api.types.is_bool_dtype(d):
        return "bool"
    if isinstance(d, pd.api.extensions.ExtensionDtype) and pd.api.types.is_integer_dtype(d):
        return "Int64"
    if pd.api.types.is_integer_dtype(d):
        return "int64"
    if pd.api.types.is_float_dtype(d):
        return "float64"
    if isinstance(d, pd.StringDtype):
        return "string"
    if pd.api.types.is_datetime64_any_dtype(d):
        return "datetime"
    return "object"


def _sql_type(tag: str) -> str:
    return {"bool": "INTEGER", "boolean": "INTEGER", "Int64": "INTEGER", "int64": "INTEGER",
            "float64": "REAL", "string": "TEXT", "datetime": "TEXT"}.get(tag, "")


def _is_missing(v: Any) -> bool:
    if v is None or v is pd.NA or v is pd.NaT:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    return False


def _obj_value(v: Any) -> Any:
    """Store object cells the way ``DataFrame.to_csv`` would print them."""
    if _is_missing(v):
        return None
    if isinstance(v, (bool, np.bool_)):
        return "True" if v else "False"
    if isinstance(v, str):
        return v
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        return None if math.isnan(float(v)) else float(v)
    return str(v)


def _column_values(series: pd.Series, tag: str) -> List[Any]:
    if tag == "bool":
        return [int(v) for v in series.tolist()]
    if tag in ("boolean", "Int64"):
        return [None if pd.isna(v) else int(v) for v in series.tolist()]
    if tag == "int64":
        return [int(v) for v in series.tolist()]
    if tag == "float64":
        return [None if math.isnan(v) else float(v) for v in series.astype(float).tolist()]
    if tag == "string":
        return [None if pd.isna(v) else str(v) for v in series.tolist()]
    if tag == "datetime":
        return [None if pd.isna(v) else str(v) for v in series.tolist()]
    return [_obj_value(v) for v in series.tolist()]


def _restore_column(values: List[Any], tag: str) -> pd.Series:
    if tag == "bool":
        return pd.Series([bool(v) for v in values], dtype=bool)
    if tag == "boolean":
        return pd.Series(pd.array([None if v is None else bool(v) for v in values], dtype="boolean"))
    if tag == "Int64":
        return pd.Series(pd.array(values, dtype="Int64"))
    if tag == "int64":
        return pd.Series(values, dtype="int64")
    if tag == "float64":
        return pd.Series([np.nan if v is None else v for v in values], dtype="float64")
    if tag == "string":
        return pd.Series(pd.array(values, dtype="string"))
    s = pd.Series(values, dtype=object)
    return s.where(s.notna(), np.nan) if len(s) else s


class Staging:
    """Thin wrapper over the staging SQLite database."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.execute("PRAGMA journal_mode=DELETE")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.executescript(_META_SQL)
        self.conn.commit()

    def close(self) -> None:
        self.conn.commit()
        self.conn.close()

    # ------------------------------------------------------------------ tables
    def table_exists(self, name: str) -> bool:
        row = self.conn.execute("SELECT 1 FROM _tables WHERE name=?", (name,)).fetchone()
        return row is not None

    def table_info(self, name: str) -> Optional[Dict[str, Any]]:
        row = self.conn.execute(
            "SELECT name, stage, kind, n_rows, n_cols, columns_json, dtypes_json, created_at FROM _tables WHERE name=?",
            (name,)).fetchone()
        if row is None:
            return None
        return {"name": row[0], "stage": row[1], "kind": row[2], "n_rows": row[3], "n_cols": row[4],
                "columns": json.loads(row[5]), "dtypes": json.loads(row[6]) if row[6] else None, "created_at": row[7]}

    def list_tables(self, stage: Optional[str] = None) -> List[Dict[str, Any]]:
        sql = "SELECT name FROM _tables"
        params: Tuple[Any, ...] = ()
        if stage is not None:
            sql += " WHERE stage=?"
            params = (stage,)
        return [self.table_info(r[0]) for r in self.conn.execute(sql + " ORDER BY created_at, name", params)]

    def drop_table(self, name: str) -> None:
        if name in _RESERVED:
            raise ValueError(f"refusing to drop reserved table {name}")
        self.conn.execute(f"DROP TABLE IF EXISTS {_q(name)}")
        self.conn.execute("DELETE FROM _tables WHERE name=?", (name,))
        self.conn.commit()

    def drop_stage_outputs(self, stage: str) -> None:
        """Remove every table / kv / manual-fix row a previous run of ``stage`` produced."""
        for info in self.list_tables(stage):
            self.drop_table(info["name"])
        self.conn.execute("DELETE FROM _kv WHERE stage=?", (stage,))
        self.conn.execute("DELETE FROM manual_fix_log WHERE stage=?", (stage,))
        self.conn.commit()

    def require_table(self, name: str, producer: str) -> None:
        if not self.table_exists(name):
            raise RuntimeError(f"staging table '{name}' missing - run stage '{producer}' first")

    def _register(self, name: str, stage: str, kind: str, n_rows: int, columns: Dict[str, Any],
                  dtypes: Optional[Dict[str, str]]) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO _tables VALUES (?,?,?,?,?,?,?,?)",
            (name, stage, kind, n_rows, len(columns["original"]), json.dumps(columns),
             json.dumps(dtypes) if dtypes is not None else None, _now()))

    # --------------------------------------------------------------- DataFrames
    def write_df(self, name: str, df: pd.DataFrame, stage: str) -> None:
        if name in _RESERVED:
            raise ValueError(f"table name {name} is reserved")
        df = df.reset_index(drop=True)
        original = [str(c) for c in df.columns]
        sql_cols = _sanitize_columns(original)
        tags = [_dtype_tag(df.iloc[:, i]) for i in range(df.shape[1])]
        self.conn.execute(f"DROP TABLE IF EXISTS {_q(name)}")
        decl = ", ".join(f"{_q(c)} {_sql_type(t)}".rstrip() for c, t in zip(sql_cols, tags)) or "_empty INTEGER"
        self.conn.execute(f"CREATE TABLE {_q(name)} ({decl})")
        if df.shape[1]:
            columns = [_column_values(df.iloc[:, i], tags[i]) for i in range(df.shape[1])]
            placeholders = ",".join("?" * len(sql_cols))
            sql = f"INSERT INTO {_q(name)} VALUES ({placeholders})"
            rows = list(zip(*columns)) if columns else []
            for start in range(0, len(rows), 5000):
                self.conn.executemany(sql, rows[start:start + 5000])
        self._register(name, stage, "df", len(df), {"original": original, "sql": sql_cols},
                       dict(zip(sql_cols, tags)))
        self.conn.commit()

    def read_df(self, name: str) -> pd.DataFrame:
        info = self.table_info(name)
        if info is None:
            raise KeyError(f"staging table not found: {name}")
        if info["kind"] != "df":
            raise TypeError(f"staging table {name} is kind={info['kind']}, use read_rows()")
        sql_cols = info["columns"]["sql"]
        original = info["columns"]["original"]
        tags = info["dtypes"] or {}
        if not sql_cols:
            return pd.DataFrame(index=range(info["n_rows"]))
        cur = self.conn.execute(f"SELECT {', '.join(_q(c) for c in sql_cols)} FROM {_q(name)}")
        fetched = cur.fetchall()
        columns = list(zip(*fetched)) if fetched else [() for _ in sql_cols]
        data = {}
        for i, (sc, oc) in enumerate(zip(sql_cols, original)):
            data[i] = _restore_column(list(columns[i]), tags.get(sc, "object"))
        out = pd.DataFrame(data)
        out.columns = original
        return out

    # --------------------------------------------------------------------- rows
    def write_rows(self, name: str, rows: Iterable[Dict[str, Any]], stage: str,
                   fieldnames: Optional[Sequence[str]] = None) -> None:
        if name in _RESERVED:
            raise ValueError(f"table name {name} is reserved")
        rows = list(rows)
        if fieldnames is None:
            fieldnames = list(dict.fromkeys(k for r in rows for k in r.keys()))
        fieldnames = [str(f) for f in fieldnames]
        sql_cols = _sanitize_columns(fieldnames)
        self.conn.execute(f"DROP TABLE IF EXISTS {_q(name)}")
        decl = ", ".join(f"{_q(c)} TEXT" for c in sql_cols) or "_empty INTEGER"
        self.conn.execute(f"CREATE TABLE {_q(name)} ({decl})")
        if sql_cols:
            sql = f"INSERT INTO {_q(name)} VALUES ({','.join('?' * len(sql_cols))})"
            batch = []
            for r in rows:
                batch.append(tuple(None if r.get(f) is None else str(r.get(f)) for f in fieldnames))
                if len(batch) >= 5000:
                    self.conn.executemany(sql, batch)
                    batch = []
            if batch:
                self.conn.executemany(sql, batch)
        self._register(name, stage, "rows", len(rows), {"original": fieldnames, "sql": sql_cols}, None)
        self.conn.commit()

    def read_rows(self, name: str) -> Tuple[List[str], List[Dict[str, str]]]:
        """Return (fieldnames, rows) exactly as csv.DictReader would (NULL -> '')."""
        info = self.table_info(name)
        if info is None:
            raise KeyError(f"staging table not found: {name}")
        sql_cols = info["columns"]["sql"]
        original = info["columns"]["original"]
        if not sql_cols:
            return [], [dict() for _ in range(info["n_rows"])]
        cur = self.conn.execute(f"SELECT {', '.join(_q(c) for c in sql_cols)} FROM {_q(name)}")
        rows = [{oc: ("" if v is None else str(v)) for oc, v in zip(original, rec)} for rec in cur]
        return list(original), rows

    # ----------------------------------------------------------------------- kv
    def put_json(self, key: str, value: Any, stage: str) -> None:
        self.conn.execute("INSERT OR REPLACE INTO _kv VALUES (?,?,?,?)",
                          (key, stage, json.dumps(value, default=str, ensure_ascii=False), _now()))
        self.conn.commit()

    def get_json(self, key: str, default: Any = None) -> Any:
        row = self.conn.execute("SELECT value_json FROM _kv WHERE key=?", (key,)).fetchone()
        return default if row is None else json.loads(row[0])

    # ------------------------------------------------------------------- stages
    def stage_status(self, name: str) -> Optional[str]:
        row = self.conn.execute("SELECT status FROM _stages WHERE name=?", (name,)).fetchone()
        return None if row is None else row[0]

    def stage_info(self, name: str) -> Optional[Dict[str, Any]]:
        row = self.conn.execute(
            "SELECT name, status, started_at, finished_at, elapsed_s, detail_json, error FROM _stages WHERE name=?",
            (name,)).fetchone()
        if row is None:
            return None
        return {"name": row[0], "status": row[1], "started_at": row[2], "finished_at": row[3],
                "elapsed_s": row[4], "detail": json.loads(row[5]) if row[5] else None, "error": row[6]}

    def stage_begin(self, name: str) -> None:
        self.conn.execute("INSERT OR REPLACE INTO _stages VALUES (?,?,?,?,?,?,?)",
                          (name, "running", _now(), None, None, None, None))
        self.conn.commit()

    def stage_ok(self, name: str, elapsed_s: float, detail: Any) -> None:
        self.conn.execute(
            "UPDATE _stages SET status='ok', finished_at=?, elapsed_s=?, detail_json=?, error=NULL WHERE name=?",
            (_now(), elapsed_s, json.dumps(detail, default=str, ensure_ascii=False), name))
        self.conn.commit()

    def stage_failed(self, name: str, elapsed_s: float, error: str) -> None:
        self.conn.execute(
            "UPDATE _stages SET status='failed', finished_at=?, elapsed_s=?, error=? WHERE name=?",
            (_now(), elapsed_s, error, name))
        self.conn.commit()

    def add_stage_log(self, stage: str, text: str) -> None:
        self.conn.execute("DELETE FROM _stage_logs WHERE stage=?", (stage,))
        self.conn.execute("INSERT INTO _stage_logs VALUES (?,?,?)", (stage, _now(), text))
        self.conn.commit()

    def all_stage_info(self) -> List[Dict[str, Any]]:
        names = [r[0] for r in self.conn.execute("SELECT name FROM _stages ORDER BY started_at")]
        return [self.stage_info(n) for n in names]

    # ------------------------------------------------------------ manual fixes
    def log_manual_fixes(self, stage: str, entries: Iterable[Dict[str, Any]]) -> int:
        rows = [(stage, e.get("table_name"), str(e.get("record_id")), e.get("field"),
                 None if e.get("old_value") is None else str(e.get("old_value")),
                 None if e.get("new_value") is None else str(e.get("new_value")),
                 e.get("reason"), e.get("source"), e.get("status", "applied")) for e in entries]
        self.conn.executemany("INSERT INTO manual_fix_log VALUES (?,?,?,?,?,?,?,?,?)", rows)
        self.conn.commit()
        return len(rows)

    # ---------------------------------------------------------- PubChem caches
    def name_cache_get(self, name: str) -> Optional[Dict[str, Any]]:
        row = self.conn.execute(
            "SELECT status, cid, molblock, source FROM pubchem_name_cache WHERE name=?", (name,)).fetchone()
        if row is None:
            return None
        return {"status": row[0], "cid": row[1], "molblock": row[2], "source": row[3]}

    def name_cache_put(self, name: str, status: str, cid: Optional[str], molblock: Optional[str],
                       source: str, overwrite: bool = True) -> None:
        verb = "INSERT OR REPLACE" if overwrite else "INSERT OR IGNORE"
        self.conn.execute(f"{verb} INTO pubchem_name_cache VALUES (?,?,?,?,?,?)",
                          (name, status, cid, molblock, source, _now()))

    def smiles_cache_get(self, smiles: str) -> Optional[Dict[str, Any]]:
        row = self.conn.execute(
            "SELECT status, iupac, title, error, source FROM pubchem_smiles_names_cache WHERE smiles=?",
            (smiles,)).fetchone()
        if row is None:
            return None
        return {"status": row[0], "iupac": row[1], "title": row[2], "error": row[3], "source": row[4]}

    def smiles_cache_put(self, smiles: str, status: str, iupac: Optional[str], title: Optional[str],
                         error: Optional[str], source: str, overwrite: bool = True) -> None:
        verb = "INSERT OR REPLACE" if overwrite else "INSERT OR IGNORE"
        self.conn.execute(f"{verb} INTO pubchem_smiles_names_cache VALUES (?,?,?,?,?,?,?)",
                          (smiles, status, iupac, title, error, source, _now()))

    def cache_counts(self) -> Dict[str, int]:
        out = {}
        for tbl in ("pubchem_name_cache", "pubchem_smiles_names_cache"):
            for status, n in self.conn.execute(f"SELECT status, COUNT(*) FROM {tbl} GROUP BY status"):
                out[f"{tbl}.{status}"] = n
        return out

    def commit(self) -> None:
        self.conn.commit()


# ---------------------------------------------------------------------------
# CSV round-trip helpers (feed file-oriented modules exactly what they would read from disk)
# ---------------------------------------------------------------------------
def df_to_csv_text(df: pd.DataFrame) -> str:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


def df_csv_roundtrip(df: pd.DataFrame, **read_csv_kwargs: Any) -> pd.DataFrame:
    """Return ``pd.read_csv(df.to_csv())`` - the same inference a file-based reader applies."""
    return pd.read_csv(io.StringIO(df_to_csv_text(df)), **read_csv_kwargs)


def csv_text_to_rows(text: str) -> Tuple[List[str], List[Dict[str, str]]]:
    reader = csv.DictReader(io.StringIO(text, newline=""))
    rows = list(reader)
    return list(reader.fieldnames or []), rows


def df_to_rows(df: pd.DataFrame) -> Tuple[List[str], List[Dict[str, str]]]:
    return csv_text_to_rows(df_to_csv_text(df))


def rows_to_csv_text(rows: Iterable[Dict[str, Any]], fieldnames: Sequence[str],
                     quoting: int = csv.QUOTE_MINIMAL) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(fieldnames), quoting=quoting, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return buf.getvalue()


def rows_to_df(rows: Iterable[Dict[str, Any]], fieldnames: Sequence[str], **read_csv_kwargs: Any) -> pd.DataFrame:
    return pd.read_csv(io.StringIO(rows_to_csv_text(rows, fieldnames)), **read_csv_kwargs)
