"""
CSV I/O helpers for pip2c entry builder.

Provides robust CSV reading with encoding/delimiter detection and caching.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from .config import COLUMN_ALIASES, FILENAMES, DEBUG_FLAG

# =============================================================================
# Logging
# =============================================================================

logger = logging.getLogger(__name__)

# ==============================================================
# Column access helpers
# ==============================================================

def _col_candidates(canonical: str) -> list[str]:
    """Get list of column name candidates for a canonical column name."""
    return COLUMN_ALIASES.get(canonical, [canonical])


def get_col(row: dict[str, Any], canonical: str, default: Any = None) -> Any:
    """Return the first non-empty value for any alias of canonical in row (case-insensitive)."""
    if not row:
        return default
    for cand in _col_candidates(canonical):
        if cand in row and str(row[cand]).strip() != "":
            return row[cand]
    # try case-insensitive fallback
    lower = {k.lower(): v for k, v in row.items()}
    for cand in _col_candidates(canonical):
        if cand.lower() in lower and str(lower[cand.lower()]).strip() != "":
            return lower[cand.lower()]
    return default


def col_exists(row: dict[str, Any], canonical: str) -> bool:
    """Check if a canonical column exists and has a non-empty value."""
    if not row:
        return False
    for cand in _col_candidates(canonical):
        if cand in row and str(row[cand]).strip() != "":
            return True
    lower = {k.lower(): v for k, v in row.items()}
    for cand in _col_candidates(canonical):
        if cand.lower() in lower and str(lower[cand.lower()]).strip() != "":
            return True
    return False


def pick(r: dict[str, Any] | None, *keys: str, default: Any = None) -> Any:
    """Pick first non-empty value from row using given keys."""
    if not r:
        return default
    for k in keys:
        if k in r and str(r[k]).strip() != "":
            return r[k]
    return default


def pick_any(r: dict[str, Any] | None, keys: list[str], default: Any = None) -> Any:
    """Pick first non-empty value from row using given keys (case-insensitive fallback)."""
    if not r:
        return default
    for k in keys:
        if k in r and str(r[k]).strip() != "":
            return r[k]
    # case-insensitive pass
    lower = {kk.lower(): vv for kk, vv in r.items()}
    for k in keys:
        lk = k.lower()
        if lk in lower and str(lower[lk]).strip() != "":
            return lower[lk]
    return default


# ==============================================================
# Encoding detection
# ==============================================================

def _detect_bom_encoding(raw: bytes) -> Optional[str]:
    """Detect encoding from BOM (Byte Order Mark)."""
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if raw.startswith(b"\xff\xfe"):
        return "utf-16-le"
    if raw.startswith(b"\xfe\xff"):
        return "utf-16-be"
    return None


def detect_csv_format(path: str) -> Optional[Tuple[str, str]]:
    """Return (encoding, delimiter) for a CSV by sniffing BOM and delimiters."""
    try:
        with open(path, "rb") as fb:
            sample_bytes = fb.read(65536)
    except Exception:
        return None
    
    enc_candidates: list[str] = []
    bom_enc = _detect_bom_encoding(sample_bytes)
    if bom_enc:
        enc_candidates.append(bom_enc)
    enc_candidates.extend(["utf-8", "cp1252", "latin-1", "utf-16", "utf-16-le", "utf-16-be"])
    
    for enc in enc_candidates:
        try:
            text = sample_bytes.decode(enc, errors="strict")
        except Exception:
            continue
        try:
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(text, delimiters=",;\t|\u0001")
            return enc, dialect.delimiter
        except Exception:
            # trial common delimiters
            for delimiter in [",", ";", "\t", "|"]:
                try:
                    _ensure_large_field_limit()
                    with open(path, "r", encoding=enc, newline="") as f:
                        reader = csv.DictReader(f, delimiter=delimiter)
                        next(reader, None)
                        return enc, delimiter
                except Exception:
                    continue
            continue
    return None


def _detect_header_delimiter(path: str) -> Optional[Tuple[str, str, list[str]]]:
    """Quickly detect (encoding, delimiter, header_fields)."""
    encs = ["utf-8-sig", "utf-8", "cp1252", "latin-1", "utf-16", "utf-16-le", "utf-16-be"]
    delims = [",", ";", "\t", "|"]
    for enc in encs:
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                for d in delims:
                    try:
                        f.seek(0)
                        reader = csv.reader(f, delimiter=d)
                        header = next(reader, None)
                        if not header:
                            continue
                        header = [h.lstrip('\ufeff').strip() if isinstance(h, str) else h for h in header]
                        if len(header) > 1:
                            return enc, d, header
                    except Exception:
                        f.seek(0)
                        continue
        except Exception:
            continue
    return None


def _ensure_large_field_limit() -> None:
    """Ensure csv field size limit is large enough for molfile blobs."""
    try:
        cur_limit = csv.field_size_limit()
        if not cur_limit or cur_limit < 10_000_000:
            csv.field_size_limit(10_000_000)
    except Exception:
        pass


# ==============================================================
# In-memory caches
# ==============================================================

# Keyed by absolute path
_CSV_CACHE: dict[str, list[dict[str, Any]]] = {}
# Row indexes for fast lookup: path -> {key -> {id_value -> row_dict}}
_ROW_INDEX: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
# In-memory tables registered by the end-to-end pipeline (no filesystem access).
# Keyed by logical name AND by the absolute path the logical name resolves to,
# so both read_csv_dicts("liganden_moldata") and find_first_row(FILENAMES[...]) hit it.
_REGISTERED: dict[str, list[dict[str, Any]]] = {}
# Normalized-id indexes for registered/cached tables: cache_key -> key -> {norm_id -> row}
_ID_INDEX: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}


def _resolve_path(name: str) -> str:
    """Resolve a logical table name or filesystem path to an absolute path string."""
    if os.path.isabs(name) or (len(name) > 1 and name[1] == ':'):
        return os.path.abspath(name)
    if name in FILENAMES:
        return os.path.abspath(FILENAMES[name])
    from .config import BASE_DIR
    return os.path.abspath(os.path.join(BASE_DIR, name))


def register_table(name: str, rows: list[dict[str, Any]]) -> None:
    """Register an in-memory table under a logical FILENAMES key (or a path).

    Registered rows take precedence over the filesystem in read_csv_dicts,
    find_first_row and lookup_row. Rows must be plain dicts of strings, i.e.
    what csv.DictReader would have produced from the equivalent CSV file.
    """
    rows = list(rows)
    _REGISTERED[name] = rows
    abs_path = _resolve_path(name)
    _REGISTERED[abs_path] = rows
    _CSV_CACHE[abs_path] = rows
    # Drop stale indexes for this table
    _ROW_INDEX.pop(abs_path, None)
    _ID_INDEX.pop(abs_path, None)


def clear_registered_tables() -> None:
    """Forget all registered tables and derived indexes."""
    for key in list(_REGISTERED.keys()):
        _CSV_CACHE.pop(key, None)
        _ROW_INDEX.pop(key, None)
        _ID_INDEX.pop(key, None)
    _REGISTERED.clear()


def _get_registered(name: str) -> Optional[list[dict[str, Any]]]:
    if name in _REGISTERED:
        return _REGISTERED[name]
    abs_path = _resolve_path(name)
    return _REGISTERED.get(abs_path)


# ==============================================================
# CSV reading functions
# ==============================================================

def stream_find_row(path: str, keys: list[str], id_value: Any) -> Optional[dict[str, Any]]:
    """Stream through CSV to find row matching id_value in any of keys."""
    meta = _detect_header_delimiter(path)
    if not meta:
        return None
    enc, delim, header = meta
    header_map = {str(h).lower(): h for h in header if isinstance(h, str)}
    
    try:
        _ensure_large_field_limit()
        with open(path, "r", encoding=enc, newline="") as f:
            reader = csv.DictReader(f, delimiter=delim)
            id_s = str(id_value)
            for i, row in enumerate(reader, 1):
                # Direct key matches (fast path)
                for k in keys:
                    if k in row and str(row[k]).strip() == id_s:
                        return row
                # Case-insensitive header matching
                for k in keys:
                    kl = k.lower()
                    if kl in header_map:
                        actual = header_map[kl]
                        val = row.get(actual) if actual in row else row.get(k)
                        if val is not None and str(val).strip() == id_s:
                            return row
    except Exception as e:
        print(f"[WARN] stream_find_row failed: {e}")
    return None


def find_first_row(path: str, keys: list[str], id_value: Any) -> Optional[dict[str, Any]]:
    """Find first row matching id_value (exact string match after strip) in any of keys.

    The table is loaded once (or taken from a registered in-memory table) and an
    index per key is built lazily; the first matching row in file order wins,
    exactly like the original streaming scan.
    """
    abs_path = _resolve_path(path)
    rows = _get_registered(path)
    if rows is None:
        rows = read_csv_dicts(path)
    if not rows:
        return None
    _build_row_index(abs_path, keys)
    idx = _ROW_INDEX.get(abs_path, {})
    id_s = str(id_value).strip()
    for k in keys:
        if id_s in idx.get(k, {}):
            return idx[k][id_s]
    return None


def _find_with_pandas(path: str, keys: list[str], id_value: Any) -> Optional[dict[str, Any]]:
    """Try finding row using pandas for large files."""
    try:
        import pandas as pd
        encs = ["utf-16", "utf-16-le", "utf-16-be", "utf-8-sig", "utf-8", "cp1252", "latin-1"]
        delims = ["\t", ",", ";", "|"]
        id_s = str(id_value)
        for enc in encs:
            for sep in delims:
                try:
                    chunks = pd.read_csv(path, sep=sep, engine="python", encoding=enc, chunksize=50000, dtype=str)
                    for chunk in chunks:
                        for k in keys:
                            if k in chunk.columns:
                                m = chunk[chunk[k].astype(str).str.strip() == id_s]
                                if not m.empty:
                                    return m.iloc[0].to_dict()
                except Exception:
                    continue
    except Exception:
        pass
    return None


def read_csv_dicts(name: str) -> list[dict[str, Any]]:
    """Read CSV file and return list of row dicts.
    
    Args:
        name: Either a logical name (key in FILENAMES) or a filesystem path.
    """
    # Registered in-memory tables take precedence over the filesystem
    registered = _get_registered(name)
    if registered is not None:
        return registered

    # Resolve path
    if os.path.isabs(name) or (len(name) > 1 and name[1] == ':'):
        path = name
    elif name in FILENAMES:
        path = FILENAMES[name]
    else:
        from .config import BASE_DIR
        path = os.path.join(BASE_DIR, name)
    
    abs_path = os.path.abspath(path)
    if not os.path.exists(path):
        logger.warning(f"CSV not found: {path}")
        print(f"[WARN] CSV not found: {path}")
        _CSV_CACHE[abs_path] = []
        return []

    # Return cached rows if available
    if abs_path in _CSV_CACHE:
        logger.debug(f"read_csv_dicts: Using cached {len(_CSV_CACHE[abs_path])} rows from {os.path.basename(path)}")
        return _CSV_CACHE[abs_path]

    logger.debug(f"read_csv_dicts: Loading {os.path.basename(path)}...")
    
    # Read binary sample for encoding detection
    try:
        with open(path, "rb") as fb:
            sample_bytes = fb.read(65536)
    except Exception as e:
        print(f"[WARN] Could not open CSV (binary): {path}: {e}")
        _CSV_CACHE[abs_path] = []
        return []

    enc_candidates = []
    bom_enc = _detect_bom_encoding(sample_bytes)
    if bom_enc:
        enc_candidates.append(bom_enc)
    enc_candidates.extend(["utf-8", "cp1252", "latin-1", "utf-16", "utf-16-le", "utf-16-be"])

    rows: list[dict[str, Any]] = []
    for enc in enc_candidates:
        try:
            text = sample_bytes.decode(enc, errors="strict")
        except Exception:
            continue
        try:
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(text, delimiters=",;\t|\u0001")
            delimiter = dialect.delimiter
        except Exception:
            # Try common delimiters
            for delimiter in [",", ";", "\t", "|"]:
                try:
                    _ensure_large_field_limit()
                    with open(path, "r", encoding=enc, newline="") as f:
                        reader = csv.DictReader(f, delimiter=delimiter)
                        rows = list(reader)
                    if rows:
                        _CSV_CACHE[abs_path] = rows
                        return rows
                except Exception:
                    continue
            continue

        # If sniffer worked, read with detected dialect
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                reader = csv.DictReader(f, delimiter=delimiter)
                rows = list(reader)
                if rows:
                    _CSV_CACHE[abs_path] = rows
                    return rows
        except Exception:
            continue

    _CSV_CACHE[abs_path] = rows
    return rows


def _build_row_index(path: str, key_candidates: list[str]) -> None:
    """Build (or extend) a multi-key exact-string index for a table and cache it.

    Keys already indexed are skipped; the first row in table order wins for
    duplicate values (same semantics as a streaming scan).
    """
    abs_path = _resolve_path(path)
    idx_map = _ROW_INDEX.setdefault(abs_path, {})
    missing = [k for k in key_candidates if k not in idx_map]
    if not missing:
        return

    rows = _REGISTERED.get(abs_path)
    if rows is None:
        rows = _CSV_CACHE.get(abs_path)
    if rows is None:
        try:
            if os.path.exists(abs_path):
                rows = read_csv_dicts(abs_path)
            else:
                rows = read_csv_dicts(os.path.basename(abs_path))
        except Exception:
            rows = []

    for k in missing:
        idx_map[k] = {}

    for r in rows:
        lower = None
        for k in missing:
            if k in r:
                if r.get(k) in (None, ""):
                    continue
                v = str(r.get(k)).strip()
            else:
                # Case-insensitive match
                if lower is None:
                    lower = {kk.lower(): vv for kk, vv in r.items() if isinstance(kk, str)}
                lk = k.lower()
                if lk not in lower or lower[lk] in (None, ""):
                    continue
                v = str(lower[lk]).strip()
            if v:
                idx_map[k].setdefault(v, r)


def _build_id_index(name: str, key_candidates: list[str]) -> dict[str, dict[str, dict[str, Any]]]:
    """Build (or extend) a normalize_id()-based index for a table (first row wins)."""
    abs_path = _resolve_path(name)
    idx_map = _ID_INDEX.setdefault(abs_path, {})
    missing = [k for k in key_candidates if k not in idx_map]
    if missing:
        rows = read_csv_dicts(name)
        for k in missing:
            idx_map[k] = {}
        for r in rows:
            for k in missing:
                if k in r:
                    idx_map[k].setdefault(normalize_id(r[k]), r)
    return idx_map


def lookup_row(name: str, keys: list[str], id_value: Any) -> Optional[dict[str, Any]]:
    """Indexed equivalent of first_row_by_id(read_csv_dicts(name), id_value, keys).

    Same semantics (normalize_id comparison, first matching row in table order,
    keys tried in the given order) but O(1) per call after the first.
    """
    idx_map = _build_id_index(name, keys)
    id_s = normalize_id(id_value)
    for k in keys:
        row = idx_map.get(k, {}).get(id_s)
        if row is not None:
            return row
    return None


# ==============================================================
# Utility functions
# ==============================================================

def normalize_id(value: Any) -> str:
    """Normalize ID values - convert '79.0' to '79', strip whitespace."""
    if value is None:
        return ""
    s = str(value).strip()
    try:
        f = float(s)
        if f == int(f):
            return str(int(f))
    except (ValueError, TypeError):
        pass
    return s


def first_row_by_id(rows: list[dict[str, Any]], id_value: Any, possible_keys: list[str]) -> Optional[dict[str, Any]]:
    """Find first row matching id_value in any of possible_keys."""
    id_s = normalize_id(id_value)
    for r in rows:
        for k in possible_keys:
            if k in r and normalize_id(r[k]) == id_s:
                return r
    return None


def map_by_key(rows: list[dict[str, Any]], key_candidates: list[str]) -> dict[str, dict[str, Any]]:
    """Create a lookup dict from rows, keyed by first present key candidate."""
    out: dict[str, dict[str, Any]] = {}
    present_keys = [k for k in key_candidates if rows and k in rows[0]]
    if not present_keys:
        return out
    key = present_keys[0]
    for r in rows:
        out[normalize_id(r.get(key, ""))] = r
    return out


def collect_comment_like_fields_from_row(row: dict[str, Any]) -> list[str]:
    """Scan a CSV row dict for columns that look like comment/note fields.
    
    Returns a list of non-empty trimmed strings.
    """
    out: list[str] = []
    if not row:
        return out
    comment_keys = ("comment", "comments", "note", "notes", "remark", "remarks", 
                    "footnote", "annotation", "parse_notes")
    for k, v in row.items():
        if not isinstance(k, str):
            continue
        lk = k.lower()
        if any(tok in lk for tok in comment_keys):
            try:
                if v is None:
                    continue
                s = str(v).strip()
                if not s or s == "\\N":
                    continue
                out.append(s)
            except Exception:
                continue
    return out
