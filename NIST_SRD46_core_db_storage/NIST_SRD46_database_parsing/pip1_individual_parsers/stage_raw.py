"""
Stage raw_canonical: load verkn_ligand_metal from the mysqldump --tab export.

Manual rules applied here (declared in :mod:`srd46_pipeline.manual_rules`):
  SRC-01  the ``.txt`` dump is the authority for this table, not the Excel-derived CSV
  VLM-01  '*' placeholder rows -> NULL values, is_placeholder=1
  VLM-02  '(x)' -> x, constant_in_parentheses=1
  VLM-03  '30tv'/'35tv' -> 30/35
  VLM-04  four guarded Sommer Ti(IV) rows: metal 187 -> 188; original ID retained
  VLM-00  anything else non-numeric -> NULL + ledger status 'unparsed'

Output table ``verkn_ligand_metal_canonical`` = the 16 verbatim dump columns (strings, ``\\N``
kept literally as in the CSV) + derived columns metalNr_raw, metalNr_value, constant_raw, constant_value,
constant_in_parentheses, temperature_value, ionicstrength_value, is_placeholder, applied_rules,
parser_tokens (space-separated NOTE-01 ``parser:<key>=<value>`` strings; pip2c appends them to
the card notes because the published cards schema carries no extra column).
SRC-02 validates the original .sql schemas and matching .txt rows for every source
table. Pinned beta-definition corrections and deterministic markup normalization
are applied from parser rules and recorded in the ledger. The source_dump_audit
records row counts, schemas, encodings, and file hashes. No export CSV is read.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

import pandas as pd

from srd46_pipeline import manual_rules as mr
from srd46_pipeline.sources import audit_source_tables, read_mysqldump_tab
from srd46_pipeline.runner import Context, PipelineError

STAGE = "raw_canonical"
TABLE = "verkn_ligand_metal"
OUT_TABLE = "verkn_ligand_metal_canonical"
DERIVED_COLS = ["metalNr_raw", "metalNr_value", "constant_raw", "constant_value", "constant_in_parentheses",
                "temperature_value", "ionicstrength_value", "is_placeholder", "applied_rules", "parser_tokens"]

def run(ctx: Context) -> Dict[str, Any]:
    st = ctx.staging
    stem = mr.CANONICAL_TABLE_FILES[TABLE]
    sql_path = mr.CANONICAL_DUMP_DIR / f"{stem}.sql"
    txt_path = mr.CANONICAL_DUMP_DIR / f"{stem}.txt"
    for p in (sql_path, txt_path):
        if not p.is_file():
            raise PipelineError(f"raw_canonical: canonical dump file missing: {p}")
    ctx.log(f"raw_canonical: {TABLE} <- {txt_path.name} ({mr.CANONICAL_DUMP_ENCODING}) [rule SRC-01]")
    columns, rows = read_mysqldump_tab(sql_path, txt_path)
    expected = mr.CANONICAL_EXPECTED_ROWS.get(TABLE)
    if expected is not None and len(rows) != expected:
        raise PipelineError(f"raw_canonical: {TABLE} has {len(rows)} rows, expected {expected}")
    for col in ("verkn_ligand_metalID",) + mr.VLM_NUMERIC_FIELDS:
        if col not in columns:
            raise PipelineError(f"raw_canonical: column {col!r} missing from {sql_path.name}")

    # Check all exact row signatures and complete target coverage before any staging write.
    try:
        mr.validate_vlm_metal_correction_rows(rows)
    except ValueError as exc:
        raise PipelineError(f"raw_canonical: {exc}") from exc

    # Check all schemas, rows, and pinned source corrections before staging any output.
    source_audit, source_fixes = audit_source_tables()
    source_ledger = [{"table_name": entry["table"], "record_id": entry["record_id"],
                      "field": entry["column"], "old_value": entry["original"],
                      "new_value": entry["replacement"], "reason": entry["provenance"],
                      "source": mr.ledger_source(entry["rule_id"]), "status": "applied"}
                     for entry in source_fixes]

    # --- manual rules VLM-00..04, row by row; every application -> ledger ------------------
    ledger: List[Dict[str, Any]] = []
    derived_rows: List[Dict[str, Any]] = []
    rule_counts: Counter = Counter()
    for r in rows:
        derived, entries = mr.derive_vlm_fields(r)
        derived_rows.append(derived)
        for e in entries:
            e["table_name"] = OUT_TABLE
            e["record_id"] = r["verkn_ligand_metalID"]
            rule_counts[f"{e['source']}:{e['status']}"] += 1
            ledger.append(e)
    n_logged = st.log_manual_fixes(STAGE, source_ledger + ledger)

    df = pd.DataFrame(rows, columns=columns)
    for col in DERIVED_COLS:
        df[col] = [d[col] for d in derived_rows]
    for col in ("constant_value", "temperature_value", "ionicstrength_value"):
        df[col] = pd.to_numeric(df[col], errors="raise").astype("float64")
    for col in ("constant_in_parentheses", "is_placeholder"):
        df[col] = df[col].astype("int64")
    st.write_df(OUT_TABLE, df, STAGE)

    st.put_json("raw_canonical_rule_counts", dict(rule_counts), STAGE)
    st.put_json("source_dump_audit", source_audit, STAGE)
    st.commit()
    unparsed = {k: v for k, v in rule_counts.items() if k.endswith(":unparsed")}
    if unparsed:
        ctx.log(f"raw_canonical: WARNING values left NULL as unparsed (see manual_fix_log): {unparsed}")
    ctx.log(f"raw_canonical: {len(rows)} measured rows; {len(source_audit)} original dump tables validated; "
            f"{len(source_fixes)} source curation/markup corrections recorded")
    return {"rows": len(rows), "columns": len(columns), "placeholders": int(df["is_placeholder"].sum()),
            "constant_in_parentheses": int(df["constant_in_parentheses"].sum()),
            "constant_values": int(df["constant_value"].notna().sum()),
            "ledger_rows": n_logged, "rule_counts": dict(rule_counts),
            "source_tables": len(source_audit), "source_corrections": len(source_fixes)}
