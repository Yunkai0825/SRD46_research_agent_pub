"""Stage registry, run loop (resume / atomic failure / visible staleness) and final verification."""
from __future__ import annotations

import sqlite3
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .debug_export import export_stage_debug
from .legacy import capture_output
from .paths import ACCEPTED_REFERENCE_COUNTS, CARDS_SCHEMA_CONTRACT, REFERENCE_COUNTS, OutputPaths
from .staging import Staging


class PipelineError(RuntimeError):
    pass


@dataclass
class Options:
    pubchem_mode: str = "cache-then-network"      # cache-then-network | cache-only | network
    qupkake_mode: str = "existing"                # existing | off
    qupkake_input_db: Optional[Path] = None
    qupkake_sdf_dir: Optional[Path] = None
    qupkake_parsed_csv: Optional[Path] = None
    limit: Optional[int] = None
    verbose: bool = False
    debug: bool = False                           # export every intermediate artifact to <output-dir>/debug/


class Context:
    def __init__(self, paths: OutputPaths, staging: Staging, options: Options):
        self.paths = paths
        self.staging = staging
        self.options = options
        self._console = sys.stdout

    def log(self, msg: str) -> None:
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)                      # captured (and echoed when verbose)
        if not self.options.verbose and sys.stdout is not self._console:
            try:
                self._console.write(line + "\n")
            except UnicodeEncodeError:
                self._console.write(line.encode("ascii", "replace").decode("ascii") + "\n")
            self._console.flush()

    @property
    def limit(self) -> Optional[int]:
        return self.options.limit


def _stage_table() -> List[tuple]:
    from pip1_individual_parsers import stage_raw, stage_pip1a, stage_pip1b, stage_pip1c
    from pip2_SQL_assembler_SRD46 import stage_pip2a, stage_pip2b, stage_pip2c, stage_literature, stage_pip2d
    return [
        ("raw_canonical", stage_raw.run),
        ("pip1a_beta_definition", stage_pip1a.run),
        ("pip1b_metal", stage_pip1b.run),
        ("pip1c_1_molfile_decode", stage_pip1c.run_pip1c_1),
        ("pip1c_2_smiles_inchi", stage_pip1c.run_pip1c_2),
        ("pip1c_3_hxl_parse", stage_pip1c.run_pip1c_3),
        ("pip1c_4_chemical_names", stage_pip1c.run_pip1c_4),
        ("pip1c_5b_qupkake_parse", stage_pip1c.run_pip1c_5b),
        ("pip1c_6_qupkake_merge", stage_pip1c.run_pip1c_6),
        ("pip2a_equilibrium_maps", stage_pip2a.run),
        ("pip2b_ligand_pka_chains", stage_pip2b.run),
        ("pip2c_cards", stage_pip2c.run),
        ("literature_db", stage_literature.run),
        ("pip2d_ligand_similarity", stage_pip2d.run),
        ("verify", verify),
    ]


STAGE_ORDER = ["raw_canonical",
               "pip1a_beta_definition", "pip1b_metal", "pip1c_1_molfile_decode", "pip1c_2_smiles_inchi",
               "pip1c_3_hxl_parse", "pip1c_4_chemical_names", "pip1c_5b_qupkake_parse", "pip1c_6_qupkake_merge",
               "pip2a_equilibrium_maps", "pip2b_ligand_pka_chains", "pip2c_cards", "literature_db",
               "pip2d_ligand_similarity", "verify"]


def _span(first: str, last: str) -> List[str]:
    return STAGE_ORDER[STAGE_ORDER.index(first):STAGE_ORDER.index(last) + 1]


STAGE_GROUPS = {
    "all": STAGE_ORDER,
    "raw": _span("raw_canonical", "raw_canonical"),
    "pip1": _span("raw_canonical", "pip1c_6_qupkake_merge"),
    "pip1c": _span("pip1c_1_molfile_decode", "pip1c_6_qupkake_merge"),
    "pip2": _span("pip2a_equilibrium_maps", "pip2d_ligand_similarity"),
    "descriptors": ["pip2d_ligand_similarity"],
}


def resolve_stages(spec: str) -> List[str]:
    wanted: List[str] = []
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        if token in STAGE_GROUPS:
            wanted.extend(STAGE_GROUPS[token])
        elif token in STAGE_ORDER:
            wanted.append(token)
        else:
            raise PipelineError(f"unknown stage '{token}'. Known: {', '.join(STAGE_ORDER)}; groups: {', '.join(STAGE_GROUPS)}")
    # keep pipeline order, dedupe
    return [s for s in STAGE_ORDER if s in wanted]


def run(ctx: Context, stages: List[str], resume: bool) -> None:
    funcs = dict(_stage_table())
    st = ctx.staging
    for name in stages:
        status = st.stage_status(name)
        if resume and status == "ok":
            info = st.stage_info(name) or {}
            ctx.log(f"skip {name} (ok at {info.get('finished_at')})")
            continue
        ctx.log(f"=== {name} ===")
        # Everything downstream of a re-run stage is now stale - make it visible and non-skippable.
        for later in STAGE_ORDER[STAGE_ORDER.index(name) + 1:]:
            if st.stage_status(later) == "ok":
                st.conn.execute("UPDATE _stages SET status='stale' WHERE name=?", (later,))
        st.conn.commit()
        st.stage_begin(name)
        st.drop_stage_outputs(name)
        t0 = time.time()
        error: Optional[str] = None
        detail: Dict[str, Any] = {}
        with capture_output(ctx.options.verbose) as tee:
            try:
                detail = funcs[name](ctx) or {}
            except BaseException:
                error = traceback.format_exc()
        elapsed = time.time() - t0
        log_text = tee.getvalue()
        st.add_stage_log(name, log_text)
        if error is not None:
            st.stage_failed(name, elapsed, error)
        else:
            st.stage_ok(name, elapsed, detail)
            summary = ", ".join(f"{k}={v}" for k, v in detail.items() if not isinstance(v, (dict, list)))
            ctx.log(f"--- {name} ok in {elapsed:.1f}s {summary}")
        if ctx.options.debug:
            n_files, debug_dir = export_stage_debug(ctx, name)
            ctx.log(f"    debug: {n_files} artifact file(s) -> {debug_dir}")
        if error is not None:
            if not ctx.options.verbose:
                tail = log_text.strip().splitlines()[-25:]
                if tail:
                    ctx.log(f"--- last output of {name} ---")
                    for line in tail:
                        ctx.log("    " + line)
            ctx.log(f"!!! {name} FAILED after {elapsed:.1f}s (log stored in staging _stage_logs)")
            raise PipelineError(f"stage {name} failed:\n{error}")


# ---------------------------------------------------------------------------
# Final verification
# ---------------------------------------------------------------------------
def _count(db: Path, table: str) -> Optional[int]:
    try:
        con = sqlite3.connect(str(db))
        try:
            return con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        finally:
            con.close()
    except sqlite3.Error:
        return None


def verify(ctx: Context) -> Dict[str, Any]:
    p = ctx.paths
    report: Dict[str, Any] = {"limited": ctx.limit is not None, "qupkake_mode": ctx.options.qupkake_mode,
                              "databases": {}, "counts": []}
    missing = [str(f) for f in p.all_final() if not f.exists()]
    for f in p.all_final():
        report["databases"][f.name] = {"path": str(f), "exists": f.exists(),
                                       "bytes": f.stat().st_size if f.exists() else None}
    checks = [("cards", p.cards_db), ("eq", p.eq_db), ("lit", p.lit_db)]
    problems: List[str] = []
    ctx.log(f"{'database':<28}{'table':<24}{'rows':>10}{'reference':>10}  flag")
    for key, db in checks:
        for table, ref in REFERENCE_COUNTS[key].items():
            n = _count(db, table) if db.exists() else None
            if n is None:
                flag = "MISSING"
            elif n == 0:
                flag = "EMPTY"
            elif n < ref:
                flag = "LOW" if not report["limited"] else "limited"
            elif n > ref:
                flag = "HIGH"
            else:
                flag = "ok"
            if flag in ("MISSING", "EMPTY"):
                problems.append(f"{db.name}.{table}: {flag}")
            report["counts"].append({"db": db.name, "table": table, "rows": n, "reference": ref, "flag": flag})
            ctx.log(f"{db.name:<28}{table:<24}{str(n):>10}{ref:>10}  {flag}")
    if ctx.options.qupkake_mode == "off":
        ctx.log("note: qupkake=off -> ligand pKa bracket columns fall back to Q0 defaults (bracket counts differ)")

    # Cards DB contract + provenance (manual rules NOTE-01 / LIG-04):
    #   1. the three card tables carry exactly the columns the downstream readers expect (no drift);
    #   2. accepted (SRD46 data) vs placeholder ('*' / '***') split, derived from notes tokens and
    #      the LIG-04 SQL; accepted counts against ACCEPTED_REFERENCE_COUNTS;
    #   3. documented equivalence 'parser:placeholder=1' <=> constant_type '*';
    #   4. LIG-04 invariant: a placeholder ligand carries no accepted measured row.
    if p.cards_db.exists():
        from . import manual_rules as mr
        con = sqlite3.connect(str(p.cards_db))
        try:
            schema_ok = True
            for table, expected in CARDS_SCHEMA_CONTRACT.items():
                actual = [r[1] for r in con.execute(f'PRAGMA table_info("{table}")').fetchall()]
                if actual != expected:
                    schema_ok = False
                    problems.append(f"{p.cards_db.name}.{table}: columns differ from the downstream contract "
                                    f"(extra={sorted(set(actual) - set(expected))}, "
                                    f"missing={sorted(set(expected) - set(actual))}, order_ok={sorted(actual) == sorted(expected)})")
            report["cards_schema_contract_ok"] = schema_ok
            ctx.log(f"cards schema contract ({', '.join(CARDS_SCHEMA_CONTRACT)}): {'ok' if schema_ok else 'DRIFT'}")

            split: Dict[str, Dict[str, int]] = {}
            if schema_ok:
                for table, query in mr.PLACEHOLDER_SPLIT_QUERIES.items():
                    p_, a_, n_ = con.execute(query).fetchone()
                    split[table] = {"placeholder": int(p_ or 0), "accepted": int(a_ or 0), "total": int(n_ or 0)}
                    ref = ACCEPTED_REFERENCE_COUNTS.get(table)
                    flag = "ok" if ref is None or ref == split[table]["accepted"] else ("limited" if report["limited"] else "DIFF")
                    ctx.log(f"{p.cards_db.name:<28}{table + ' (accepted)':<24}{str(split[table]['accepted']):>10}{str(ref or ''):>10}  {flag}"
                            f"   placeholder={split[table]['placeholder']}")
                star_rows = con.execute(mr.PLACEHOLDER_CONSTANT_TYPE_SQL).fetchone()[0]
                report["placeholder_rows_constant_type_star"] = star_rows
                if star_rows != split["ligandmetal_stability_measured"]["placeholder"]:
                    problems.append(f"NOTE-01: {split['ligandmetal_stability_measured']['placeholder']} rows carry "
                                    f"{mr.PLACEHOLDER_NOTE} but {star_rows} rows have constant_type '*'")
                leaks = con.execute(mr.ACCEPTED_ROWS_ON_PLACEHOLDER_LIGANDS_SQL).fetchone()[0]
                report["accepted_rows_on_placeholder_ligands"] = leaks
                if leaks:
                    problems.append(f"LIG-04 invariant violated: {leaks} accepted measured rows belong to placeholder ligands")
                else:
                    ctx.log(f"LIG-04 invariant ok: placeholder ligands carry 0 accepted measured rows; "
                            f"{star_rows} placeholder rows == constant_type '*' rows")
            report["placeholder_split"] = split
            if schema_ok:
                # Both published equation representations must survive the entry-builder/schema handoff.
                mismatch = con.execute("""
                    SELECT COUNT(*) FROM ligandmetal_stability_measured
                    WHERE equation_python IS NOT equation_str
                """).fetchone()[0]
                missing_sides = con.execute("""
                    SELECT COUNT(*) FROM ligandmetal_stability_measured
                    WHERE equation_python IS NOT NULL AND TRIM(equation_python) NOT IN ('', '*')
                      AND CASE WHEN json_valid(equation_sides_json)
                               THEN COALESCE(json_type(equation_sides_json, '$.numerator') = 'array'
                                         AND json_type(equation_sides_json, '$.denominator') = 'array', 0)
                               ELSE 0 END = 0
                """).fetchone()[0]
                report["card_equation_export"] = {"representation_mismatches": mismatch,
                                                  "parsed_equations_without_sides": missing_sides}
                if mismatch or missing_sides:
                    problems.append(f"card equation export: {mismatch} representation mismatches, "
                                    f"{missing_sides} parsed equations without structured sides")
                ctx.log(f"card equation export: {mismatch} representation mismatches, "
                        f"{missing_sides} parsed equations without structured sides")
        finally:
            con.close()
    # Fingerprints and the complete upper-triangle similarity table must match the cards source.
    if p.cards_db.is_file() and p.fingerprints_db.is_file():
        from pip2_SQL_assembler_SRD46.pip2d_ligand_similarity import verify_database
        try:
            report["ligand_similarity"] = verify_database(p.cards_db, p.fingerprints_db)
            ctx.log("ligand fingerprints/similarities: source, rows, pairs and metadata verified")
        except (ValueError, sqlite3.Error, OSError) as exc:
            report["ligand_similarity"] = {"ok": False, "error": str(exc)}
            problems.append(f"{p.fingerprints_db.name}: {exc}")
    report["problems"] = problems
    ctx.staging.put_json("verification", report, "verify")
    if missing:
        raise PipelineError("final databases missing: " + ", ".join(missing))
    if problems:
        raise PipelineError("verification problems: " + "; ".join(problems))
    return {"databases": len(p.all_final()), "problems": 0, "limited": report["limited"]}
