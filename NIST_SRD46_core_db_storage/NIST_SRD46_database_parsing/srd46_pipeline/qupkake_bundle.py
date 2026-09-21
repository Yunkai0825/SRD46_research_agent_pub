"""Lossless QupKake evidence bundle with directly queryable parsed predictions.

Create once with ``python -m srd46_pipeline.qupkake_bundle create SOURCE OUTPUT``.
The converter uses the existing SDF parser. Readers only query SQLite tables;
source BLOBs retain the original evidence and are never extracted at runtime.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
from urllib.parse import quote

import pandas as pd

_WORKSPACE_ROOT = Path(__file__).absolute().parents[3]
if str(_WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE_ROOT))
from workspace_setup import ensure_packaged_file

FORMAT_VERSION = 1
BASE_COLUMNS = ["ligandennr", "molfile_original", "formula_Q0", "bracket_Q0", "smiles_Q0", "inchi_Q0"]
ARCHIVE_NAME = "qupkake_pka_liganden.csv"
SDF_DIRECTORY = "pip1c_Qupkake_SDF"


def _q(name):
    return '"' + name.replace('"', '""') + '"'


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def open_bundle(path):
    """Open existing inputs read-only, including Windows UNC paths."""
    path = Path(path).absolute()
    ensure_packaged_file(path)
    con = sqlite3.connect("file:" + quote(str(path), safe="/\\:") + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        metadata = dict(con.execute("SELECT key,value_json FROM bundle_metadata"))
        if json.loads(metadata.get("format_version", "null")) != FORMAT_VERSION:
            raise ValueError(f"unsupported QupKake bundle format: {path}")
        if json.loads(metadata.get("status", "null")) != "complete":
            raise ValueError(f"incomplete QupKake bundle: {path}")
    except Exception:
        con.close()
        raise
    return con


def _archive_frame(con):
    columns = json.loads(con.execute("SELECT value_json FROM bundle_metadata WHERE key='archive_columns'").fetchone()[0])
    if not columns:
        return None
    return pd.read_sql_query("SELECT " + ",".join(_q(c) for c in columns) + " FROM archived_prediction ORDER BY _archive_row", con, dtype=str)


def read_predictions(path, limit=None):
    """Return the same SDF frames/statistics as parsing the selected source files."""
    with closing(open_bundle(path)) as con:
        source_rows = list(con.execute("SELECT * FROM sdf_result ORDER BY source_ordinal"))
        selected = source_rows if limit is None else source_rows[:limit]
        count = len(selected)
        predictions = {r["source_ordinal"]: dict(r) for r in con.execute("SELECT * FROM sdf_prediction WHERE source_ordinal < ? ORDER BY source_ordinal", (count,))}
        windows = {}
        charges = set()
        for r in con.execute("SELECT * FROM sdf_window WHERE source_ordinal < ? ORDER BY source_ordinal,charge DESC", (count,)):
            windows.setdefault(r["source_ordinal"], {})[r["charge"]] = dict(r)
            charges.add(r["charge"])
        columns = list(BASE_COLUMNS)
        for charge in sorted(charges, reverse=True):
            columns.extend(f"{field}_Q_{charge}" for field in ("formula", "bracket", "smiles", "inchi"))
        rows = []
        for ordinal, record in predictions.items():
            row = {name: record[name] for name in BASE_COLUMNS}
            for charge in sorted(charges, reverse=True):
                window = windows.get(ordinal, {}).get(charge, {})
                row.update({f"{field}_Q_{charge}": window.get(field, "") for field in ("formula", "bracket", "smiles", "inchi")})
            rows.append(row)
        validation, events = [], []
        skipped = Counter({"empty_sdf": 0, "no_sites": 0, "no_windows": 0})
        filter_stats = Counter()
        for record in selected:
            validation.extend(json.loads(record["validation_json"]))
            events.extend(json.loads(record["events_json"]))
            skipped.update(json.loads(record["skipped_json"]))
            filter_stats.update(json.loads(record["filter_stats_json"]))
        return {
            "wide": pd.DataFrame(rows, columns=columns),
            "validation": pd.DataFrame(validation), "events": pd.DataFrame(events),
            "skipped": dict(skipped), "filter_stats": dict(filter_stats),
            "all_files": [Path(r["path"]) for r in source_rows], "files_parsed": count,
            "archive": _archive_frame(con),
            "metadata": {r["key"]: json.loads(r["value_json"]) for r in con.execute("SELECT * FROM bundle_metadata")},
        }


def create_bundle(source, destination):
    """Package all source-tree bytes and parse active predictions; never delete inputs."""
    from pip1_individual_parsers import stage_pip1c
    from srd46_pipeline.paths import LEGACY_SCRIPTS
    import numpy
    from rdkit import rdBase

    source, destination = Path(source).resolve(), Path(destination).absolute()
    if not source.is_dir():
        raise ValueError(f"missing QupKake source directory: {source}")
    if destination.exists():
        raise FileExistsError(destination)
    files = sorted(p for p in source.rglob("*") if p.is_file())
    if any(p.is_symlink() for p in files):
        raise ValueError("QupKake bundle inputs must be regular files, not symlinks")
    sdf_dir = source / SDF_DIRECTORY
    active = sorted(sdf_dir.glob("*_states*.sdf")) + sorted(sdf_dir.glob("*_states*.sdf.gz"))
    archive = source / ARCHIVE_NAME
    active_set = set(active)
    if not active and not archive.is_file():
        raise ValueError("QupKake source has neither active SDF predictions nor the parsed archive")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=destination.name + ".", suffix=".tmp", dir=destination.parent, delete=False) as handle:
        temporary = Path(handle.name)
    try:
        with closing(sqlite3.connect(str(temporary))) as con:
            con.executescript('''
                CREATE TABLE bundle_metadata (key TEXT PRIMARY KEY, value_json TEXT NOT NULL);
                CREATE TABLE source_files (path TEXT PRIMARY KEY, role TEXT NOT NULL, content BLOB NOT NULL,
                    sha256 TEXT NOT NULL, size_bytes INTEGER NOT NULL, mtime_ns INTEGER NOT NULL);
                CREATE TABLE sdf_result (source_ordinal INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL REFERENCES source_files(path),
                    validation_json TEXT NOT NULL, events_json TEXT NOT NULL, skipped_json TEXT NOT NULL, filter_stats_json TEXT NOT NULL);
                CREATE TABLE sdf_prediction (source_ordinal INTEGER PRIMARY KEY REFERENCES sdf_result(source_ordinal),
                    ligandennr TEXT NOT NULL, molfile_original TEXT NOT NULL, formula_Q0 TEXT NOT NULL,
                    bracket_Q0 TEXT NOT NULL, smiles_Q0 TEXT NOT NULL, inchi_Q0 TEXT NOT NULL);
                CREATE TABLE sdf_window (source_ordinal INTEGER NOT NULL REFERENCES sdf_prediction(source_ordinal),
                    charge INTEGER NOT NULL, formula TEXT NOT NULL, bracket TEXT NOT NULL, smiles TEXT NOT NULL, inchi TEXT NOT NULL,
                    PRIMARY KEY (source_ordinal,charge));
            ''')
            con.execute("PRAGMA foreign_keys=ON")
            snapshots = {}
            for index, path in enumerate(files, 1):
                relative = path.relative_to(source).as_posix()
                before = path.stat()
                content = path.read_bytes()
                after = path.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or len(content) != before.st_size:
                    raise ValueError(f"source changed during conversion: {path}")
                snapshots[path] = (before.st_size, before.st_mtime_ns)
                role = ("active_prediction" if path in active_set else "archived_prediction" if path == archive
                        else "alternate_prediction" if path.suffix.lower() == ".sdf" else "supporting_evidence")
                con.execute("INSERT INTO source_files VALUES (?,?,?,?,?,?)", (relative, role, content, hashlib.sha256(content).hexdigest(), len(content), before.st_mtime_ns))
                if index % 1000 == 0:
                    print(f"Preserved {index}/{len(files)} source files", flush=True)
            captured = {}
            context = SimpleNamespace(options=SimpleNamespace(verbose=False), staging=SimpleNamespace(put_json=lambda key, value, stage: captured.update({key: value})), log=lambda message: None)
            for ordinal, path in enumerate(active):
                wide, validation, events, skipped = stage_pip1c._parse_qupkake_sdfs(context, [path])
                con.execute("INSERT INTO sdf_result VALUES (?,?,?,?,?,?)", (ordinal, path.relative_to(source).as_posix(), _json(validation.to_dict("records")), _json(events.to_dict("records")), _json(skipped), _json(captured["qupkake_filter_stats"])))
                if len(wide) > 1:
                    raise ValueError(f"expected at most one parsed prediction per SDF: {path}")
                for row in wide.to_dict("records"):
                    con.execute("INSERT INTO sdf_prediction VALUES (?,?,?,?,?,?,?)", (ordinal, *(row[c] for c in BASE_COLUMNS)))
                    for column in wide.columns:
                        if column.startswith("formula_Q_"):
                            charge = int(column[len("formula_Q_"):])
                            con.execute("INSERT INTO sdf_window VALUES (?,?,?,?,?,?)", (ordinal, charge, *(row[f"{field}_Q_{charge}"] for field in ("formula", "bracket", "smiles", "inchi"))))
                if (ordinal + 1) % 250 == 0:
                    print(f"Parsed {ordinal + 1}/{len(active)} active SDF files", flush=True)
            archive_columns = []
            archive_rows = 0
            if archive.is_file():
                frame = pd.read_csv(archive, dtype=str, keep_default_na=False, encoding="utf-8-sig")
                archive_columns = list(frame.columns)
                if "ligandennr" not in archive_columns or "_archive_row" in archive_columns:
                    raise ValueError("invalid archived QupKake prediction columns")
                con.execute("CREATE TABLE archived_prediction (_archive_row INTEGER PRIMARY KEY," + ",".join(_q(c) + " TEXT NOT NULL" for c in archive_columns) + ")")
                con.executemany("INSERT INTO archived_prediction VALUES (" + ",".join("?" for _ in range(len(archive_columns) + 1)) + ")", ((index, *row) for index, row in enumerate(frame.itertuples(index=False, name=None))))
                archive_rows = len(frame)
            for path, snapshot in snapshots.items():
                current = path.stat()
                if (current.st_size, current.st_mtime_ns) != snapshot:
                    raise ValueError(f"source changed while predictions were parsed: {path}")
            metadata = {
                "format_version": FORMAT_VERSION, "status": "complete", "created_utc": datetime.now(timezone.utc).isoformat(),
                "source_directory_name": source.name, "source_files": len(files), "active_sdf_files": len(active),
                "archive_name": ARCHIVE_NAME, "archive_columns": archive_columns, "archive_rows": archive_rows,
                "sdf_order": "sorted *_states*.sdf followed by sorted *_states*.sdf.gz in pip1c_Qupkake_SDF",
                "source_policy": "All original tree files are retained verbatim. Only primary-directory SDFs provide active predictions; alternate SDFs and audit files remain evidence.",
                "qup01_policy": "Archived rows fill only IDs with no active SDF filename, including when limiting or skipping SDFs.",
                "versions": {"python": platform.python_version(), "pandas": pd.__version__, "numpy": numpy.__version__, "rdkit": rdBase.rdkitVersion},
                "parser_sha256": {"stage_pip1c.py": hashlib.sha256(Path(stage_pip1c.__file__).read_bytes()).hexdigest(), LEGACY_SCRIPTS["pip1c_5b"].name: hashlib.sha256(LEGACY_SCRIPTS["pip1c_5b"].read_bytes()).hexdigest()},
            }
            con.executemany("INSERT INTO bundle_metadata VALUES (?,?)", ((key, _json(value)) for key, value in metadata.items()))
            con.commit()
            if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or list(con.execute("PRAGMA foreign_key_check")):
                raise ValueError("QupKake bundle failed SQLite integrity checks")
        report = verify_sources(temporary, source)
        if destination.exists():
            raise FileExistsError(destination)
        temporary.rename(destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return report


def verify_sources(bundle, source=None):
    """Verify every retained BLOB hash and optionally every original source file."""
    source = Path(source).resolve() if source is not None else None
    paths = set()
    total_bytes = 0
    roles = Counter()
    with closing(open_bundle(bundle)) as con:
        if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or list(con.execute("PRAGMA foreign_key_check")):
            raise ValueError("QupKake bundle failed SQLite integrity checks")
        for row in con.execute("SELECT * FROM source_files ORDER BY path"):
            path, content = row["path"], row["content"]
            if len(content) != row["size_bytes"] or hashlib.sha256(content).hexdigest() != row["sha256"]:
                raise ValueError(f"QupKake evidence BLOB hash mismatch: {path}")
            if source is not None and hashlib.sha256((source / path).read_bytes()).hexdigest() != row["sha256"]:
                raise ValueError(f"original QupKake file differs from bundle: {path}")
            paths.add(path)
            roles[row["role"]] += 1
            total_bytes += len(content)
        if source is not None:
            original = {p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file() and p.resolve() != Path(bundle).resolve()}
            if original != paths:
                raise ValueError(f"QupKake file inventory differs: original-only={sorted(original-paths)}, bundle-only={sorted(paths-original)}")
        metadata = {r["key"]: json.loads(r["value_json"]) for r in con.execute("SELECT * FROM bundle_metadata")}
        if metadata["source_files"] != len(paths):
            raise ValueError("QupKake bundle source count differs from metadata")
    return {"status": "passed", "source_files": len(paths), "source_bytes": total_bytes, "source_roles": dict(roles), "active_sdf_files": metadata["active_sdf_files"], "archive_rows": metadata["archive_rows"], "original_files_verified": source is not None}


def verify_equivalence(source, bundle):
    """Compare the full original stage with direct SQL including frames and ledger."""
    from pip1_individual_parsers import stage_pip1c
    from srd46_pipeline.paths import OutputPaths
    from srd46_pipeline.runner import Context, Options
    from srd46_pipeline.staging import Staging

    source = Path(source).resolve()
    snapshots = []
    with tempfile.TemporaryDirectory(prefix="srd46-qupkake-equivalence-") as temp:
        for name, options in (
            ("original", Options(qupkake_sdf_dir=source / SDF_DIRECTORY, qupkake_parsed_csv=source / ARCHIVE_NAME)),
            ("sqlite", Options(qupkake_input_db=Path(bundle))),
        ):
            paths = OutputPaths(Path(temp) / name)
            st = Staging(paths.staging_db)
            try:
                stats = stage_pip1c.run_pip1c_5b(Context(paths, st, options))
                frames = {table: st.read_df(table) for table in ("qupkake_pka_liganden", "qupkake_validation", "qupkake_run_events") if st.table_exists(table)}
                ledger = list(st.conn.execute("SELECT * FROM manual_fix_log"))
                filters = st.get_json("qupkake_filter_stats")
                snapshots.append((stats, frames, [tuple(row) for row in ledger], filters))
            finally:
                st.close()
    old, new = snapshots
    if old[1].keys() != new[1].keys():
        raise AssertionError("QupKake stage output table inventories differ")
    for name in old[1]:
        pd.testing.assert_frame_equal(old[1][name], new[1][name])
    if old[0] != new[0] or old[2] != new[2] or old[3] != new[3]:
        raise AssertionError("QupKake statistics, manual-fix ledger or filter counts differ")
    return {"status": "passed", "comparison": "exact values, row/column order, dtypes, stage statistics, QUP-01 ledger and filter statistics", "tables": {name: len(frame) for name, frame in old[1].items()}, "stats": old[0]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("source", type=Path)
    create.add_argument("bundle", type=Path)
    verify = commands.add_parser("verify")
    verify.add_argument("bundle", type=Path)
    verify.add_argument("--source", type=Path)
    verify.add_argument("--compare-stage", action="store_true")
    for command in (create, verify):
        command.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    if args.command == "create":
        result = create_bundle(args.source, args.bundle)
    else:
        result = verify_sources(args.bundle, args.source)
        if args.compare_stage:
            if args.source is None:
                parser.error("--compare-stage requires --source")
            result["stage_equivalence"] = verify_equivalence(args.source, args.bundle)
    text = json.dumps(result, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
