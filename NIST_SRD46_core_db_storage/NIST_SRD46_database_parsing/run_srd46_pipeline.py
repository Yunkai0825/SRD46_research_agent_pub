#!/usr/bin/env python
"""
End-to-end NIST SRD 46 parser: original MySQL dump (.sql schemas + .txt rows, with codified source corrections) -> four SQLite end products.

    python run_srd46_pipeline.py                      # full rebuild into _output/
    python run_srd46_pipeline.py --resume             # continue after a failed stage
    python run_srd46_pipeline.py --stages pip2c_cards,literature_db,descriptors,verify
    python run_srd46_pipeline.py --stages descriptors,verify # descriptors from an existing cards DB
    python run_srd46_pipeline.py --qupkake off        # no ML pKa states available
    python run_srd46_pipeline.py --pubchem cache-only # fully offline (archived PubChem answers)
    python run_srd46_pipeline.py --limit 50 --output-dir _output/_smoke   # quick smoke test
    python run_srd46_pipeline.py --debug              # also export every intermediate to <output-dir>/debug/
    python run_srd46_pipeline.py --status             # show stage table of the staging DB
    python run_srd46_pipeline.py --list-rules         # every manual rule (srd46_pipeline/chem_rules_lib)

Files written by default: the four downstream databases <output-dir>/pip2c_cards_sql/{srd46_cards.db,
srd46_equilibrium_maps.db, srd46_literature.db, srd46_ligand_fingerprints.db} and the work store <output-dir>/srd46_pipeline_staging.db
(every hand-off table, stats, logs, PubChem caches, manual-fix ledger; enables --resume and partial
--stages runs). With --debug every stage additionally exports its intermediate tables (CSV), stats
(JSON), captured log and ledger rows to <output-dir>/debug/<stage>/.

Schema contract: srd46_cards.db keeps exactly the columns its downstream consumers read
(srd46_pipeline/paths.py CARDS_SCHEMA_CONTRACT, checked by the verify stage). What the manual
rules derive per measured row ('*' placeholder, '(x)' tentative value, '30tv' temperature) is
carried inside ligandmetal_stability_measured.notes as 'parser:<key>=<value>' strings, e.g.
['135', 'parser:rules=VLM-01', 'parser:placeholder=1', 'parser:constant_raw=*', ...];
rows without a manual rule keep their notes untouched. Grammar + SQL filters: --list-rules (NOTE-01).

Requires an interpreter with rdkit, pandas, numpy and requests; an interpreter without rdkit fails in pip1c_2.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Manual rules FIRST: the compatibility facade loads the chem_rules_lib families and
# validates their shared registry before any stage runs.
from srd46_pipeline import manual_rules

from srd46_pipeline import runner
from srd46_pipeline.paths import PROJECT_ROOT, OutputPaths
from srd46_pipeline.runner import Context, Options, PipelineError, STAGE_GROUPS, STAGE_ORDER
from srd46_pipeline.staging import Staging


def _parse_args(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stages", default="all",
                    help="comma list of stage names or groups (%s); default all" % ", ".join(STAGE_GROUPS))
    ap.add_argument("--resume", action="store_true", help="skip stages already 'ok' in the staging DB")
    ap.add_argument("--pubchem", choices=["cache-then-network", "cache-only", "network"], default="cache-then-network",
                    help="PubChem access: archived cache first then network (default), cache only, or network only")
    ap.add_argument("--qupkake", choices=["existing", "off"], default="existing",
                    help="'existing' = query the Qupkake SQLite bundle (legacy SDF/CSV supported); 'off' = no ML pKa")
    ap.add_argument("--qupkake-input-db", type=Path, default=None,
                    help="QupKake SQLite evidence/prediction bundle (default: _input/Qupkake_ligand_pKa_ML/qupkake_results.db)")
    ap.add_argument("--qupkake-sdf-dir", type=Path, default=None,
                    help="folder with <ligandID>_states.sdf files (default: env QUPKAKE_SDF_DIR or _input/Qupkake_ligand_pKa_ML/pip1c_Qupkake_SDF)")
    ap.add_argument("--qupkake-parsed-csv", type=Path, default=None,
                    help="pre-parsed qupkake_pka_liganden.csv to use when no SDF states exist")
    ap.add_argument("--limit", type=int, default=None, help="cap Qupkake files / eq-map pairs / card ids (smoke test)")
    ap.add_argument("--output-dir", type=Path, default=OutputPaths().output_dir)
    ap.add_argument("--verbose", action="store_true", help="echo the wrapped modules' output live (else stored in staging)")
    ap.add_argument("--debug", action="store_true",
                    help="export every intermediate artifact (staging tables as CSV, stats as JSON, stage log, "
                         "manual-fix ledger rows) to <output-dir>/debug/<stage>/ after each stage")
    ap.add_argument("--status", action="store_true", help="print the stage table of the staging DB and exit")
    ap.add_argument("--list-stages", action="store_true")
    ap.add_argument("--list-rules", action="store_true", help="print every declared manual rule and exit")
    return ap.parse_args(argv)


def _print_status(st: Staging) -> None:
    rows = st.all_stage_info()
    if not rows:
        print("no stages recorded")
        return
    print(f"{'stage':<28}{'status':<9}{'finished':<21}{'elapsed_s':>10}  detail")
    for r in rows:
        detail = r.get("detail") or {}
        short = ", ".join(f"{k}={v}" for k, v in detail.items() if not isinstance(v, (dict, list)))[:90]
        print(f"{r['name']:<28}{r['status']:<9}{str(r.get('finished_at') or ''):<21}{(r.get('elapsed_s') or 0):>10.1f}  {short}")


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    args = _parse_args(argv)
    rules_summary = manual_rules.validate()          # raises ValueError on a malformed rule: abort before any stage
    if args.list_rules:
        print("\n".join(manual_rules.describe()))
        return 0
    if args.list_stages:
        print("\n".join(STAGE_ORDER))
        return 0
    out_dir = args.output_dir if args.output_dir.is_absolute() else PROJECT_ROOT / args.output_dir
    paths = OutputPaths(out_dir)
    st = Staging(paths.staging_db)
    try:
        if args.status:
            _print_status(st)
            return 0
        opts = Options(pubchem_mode=args.pubchem, qupkake_mode=args.qupkake, qupkake_input_db=args.qupkake_input_db,
                       qupkake_sdf_dir=args.qupkake_sdf_dir,
                       qupkake_parsed_csv=args.qupkake_parsed_csv, limit=args.limit, verbose=args.verbose,
                       debug=args.debug)
        ctx = Context(paths, st, opts)
        stages = runner.resolve_stages(args.stages)
        ctx.log(f"manual rules: {rules_summary['rules']} declared in srd46_pipeline/chem_rules_lib "
                f"({rules_summary['metal_smiles']} metal SMILES, {rules_summary['beta_known_unparseable']} known-unparseable "
                f"beta ids, {rules_summary['ligand_name_variant_rules']} ligand-name variant rules); --list-rules for details")
        ctx.log(f"SRD46 pipeline: {len(stages)} stage(s) -> {out_dir}  (pubchem={opts.pubchem_mode}, "
                f"qupkake={opts.qupkake_mode}, limit={opts.limit}, resume={args.resume}, debug={opts.debug})")
        runner.run(ctx, stages, resume=args.resume)
        ctx.log("done")
        return 0
    except PipelineError as exc:
        lines = str(exc).strip().splitlines()
        print("\nPIPELINE FAILED: " + lines[0], file=sys.stderr)
        for line in lines[-12:] if len(lines) > 1 else []:
            print("    " + line, file=sys.stderr)
        print("  full traceback + captured output are stored in the staging DB (_stages/_stage_logs); "
              "fix and re-run with --resume", file=sys.stderr)
        return 1
    finally:
        st.close()


if __name__ == "__main__":
    sys.exit(main())
