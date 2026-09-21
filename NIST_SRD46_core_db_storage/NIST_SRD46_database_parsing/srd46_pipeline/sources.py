"""Read the original MySQL --tab export without spreadsheet CSV dependencies.

The .sql file supplies the table schema; its matching CP1252 .txt file supplies
rows. MySQL is not required, and the dump's SQL is never executed. CSV streams
exist only in memory to adapt the older parsers' input interfaces.
"""
from __future__ import annotations

import csv
import hashlib
import io
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .paths import RAW_DUMP_DIR, RAW_TABLE_FILES
from .chem_rules_lib.source_corrections import normalize_source_rows

DUMP_ENCODING = "cp1252"
NULL_TOKEN = r"\N"
_UNESCAPE = {"0": "\x00", "b": "\b", "n": "\n", "r": "\r", "t": "\t", "Z": "\x1a", "\\": "\\"}
_LFS_HEADER = b"version https://git-lfs.github.com/spec/v1"


class SourceError(ValueError):
    """A missing, malformed, or changed original source cannot be parsed safely."""


def source_paths(key: str, dump_dir: Path | None = None) -> Tuple[Path, Path]:
    root = RAW_DUMP_DIR if dump_dir is None else Path(dump_dir)
    try:
        stem = RAW_TABLE_FILES[key]
    except KeyError as exc:
        raise SourceError(f"unknown SRD46 source table: {key!r}") from exc
    return root / f"{stem}.sql", root / f"{stem}.txt"


def _read_bytes(path: Path) -> bytes:
    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise SourceError(f"original SRD46 source file missing: {path}") from exc
    if raw.startswith(_LFS_HEADER):
        raise SourceError(f"{path} is a Git LFS pointer; fetch the original source with git lfs pull")
    return raw


def parse_create_table_columns(sql_text: str) -> List[str]:
    """Extract columns in declaration order from a mysqldump CREATE TABLE."""
    columns: List[str] = []
    in_body = False
    for line in sql_text.splitlines():
        value = line.strip()
        if value.upper().startswith("CREATE TABLE"):
            in_body = True
            continue
        if not in_body:
            continue
        if value.startswith(")"):
            break
        if value.startswith("`"):
            end = value.find("`", 1)
            if end < 0:
                raise SourceError("unterminated column name in CREATE TABLE")
            columns.append(value[1:end])
    if not columns or len(set(columns)) != len(columns):
        raise SourceError("missing or duplicate column definitions in CREATE TABLE")
    return columns


def unescape_field(field: str) -> str:
    """Decode MySQL --tab escaping, keeping whole-field \\N as a NULL sentinel."""
    if field == NULL_TOKEN or "\\" not in field:
        return field
    result: List[str] = []
    index = 0
    while index < len(field):
        char = field[index]
        if char == "\\" and index + 1 < len(field):
            result.append(_UNESCAPE.get(field[index + 1], field[index + 1]))
            index += 2
        else:
            result.append(char)
            index += 1
    return "".join(result)


def read_mysqldump_tab(sql_path: Path, txt_path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    """Read schema and rows strictly, preserving original value strings and timestamps."""
    columns = parse_create_table_columns(_read_bytes(sql_path).decode("utf-8-sig"))
    text = _read_bytes(txt_path).decode(DUMP_ENCODING)
    rows: List[Dict[str, str]] = []
    for lineno, line in enumerate(text.split("\n"), start=1):
        if line in ("", "\r"):
            continue
        fields = [unescape_field(field) for field in line.removesuffix("\r").split("\t")]
        if len(fields) != len(columns):
            raise SourceError(f"{txt_path.name} line {lineno}: {len(fields)} fields, expected {len(columns)}")
        rows.append(dict(zip(columns, fields)))
    return columns, rows


def read_source_table(key: str, *, dump_dir: Path | None = None,
                      corrections: List[Dict[str, Any]] | None = None) -> Tuple[List[str], List[Dict[str, str]]]:
    """Read a dump table and apply only declared source curation/markup rules."""
    columns, rows = read_mysqldump_tab(*source_paths(key, dump_dir))
    rows, entries = normalize_source_rows(key, columns, rows)
    if corrections is not None:
        corrections.extend(entries)
    return columns, rows


def source_csv(key: str) -> io.StringIO:
    """Return a fresh in-memory compatibility stream; no CSV file is read or written."""
    columns, rows = read_source_table(key)
    buffer = io.StringIO(newline="")
    buffer.name = f"{key} (original MySQL dump)"
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    buffer.seek(0)
    return buffer


def audit_source_tables() -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Validate all original tables and record reproducible file hashes and curation."""
    report: Dict[str, Any] = {}
    corrections: List[Dict[str, Any]] = []
    for key in RAW_TABLE_FILES:
        columns, rows = read_source_table(key, corrections=corrections)
        sql_path, txt_path = source_paths(key)
        report[key] = {
            "columns": columns, "rows": len(rows), "encoding": DUMP_ENCODING,
            "schema": sql_path.name, "data": txt_path.name,
            "schema_sha256": hashlib.sha256(_read_bytes(sql_path)).hexdigest(),
            "data_sha256": hashlib.sha256(_read_bytes(txt_path)).hexdigest(),
        }
        del rows
    return report, corrections
