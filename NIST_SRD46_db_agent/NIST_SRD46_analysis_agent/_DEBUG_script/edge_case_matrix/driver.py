# Builds the edge-case matrix, runs each case in its own subprocess, classifies outcomes.
import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).absolute().parent
REPO_ROOT = Path(__file__).absolute().parents[4]
PY = sys.executable
RUNNER = HERE / "case_runner.py"
TIMEOUT_S = 900

CRASH_TYPES = {"TypeError", "KeyError", "AttributeError", "IndexError", "ZeroDivisionError"}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def a_base(template, ph_n=11, ev_n=9):
    c = copy.deepcopy(template)
    for ax in c["sweep_axes"]:
        if ax["name"] == "pH":
            ax["n_points"] = ph_n
        elif ax["name"] == "E_V":
            ax["n_points"] = ev_n
    return c


def set_bind_and_init(c, bind_id, value):
    """Set a scalar condition in BOTH constraint_spec.binds and _initial_conditions.inits."""
    hit = False
    for b in c["constraint_spec"]["binds"]:
        if b["id"] == bind_id and "const" in b.get("rhs", {}):
            b["rhs"]["const"] = value
            hit = True
    for init in c.get("_initial_conditions", {}).get("inits", []):
        if init["id"] == bind_id:
            init["value"] = value
            hit = True
    if not hit:
        raise RuntimeError(f"driver bug: no bind/init with id {bind_id!r}")
    return c


def build_cases(a_card, a_calc, b_card, b_calc):
    a_template = load(a_calc)
    b_template = load(b_calc)
    cases = []

    def add(case_id, card, calc):
        cases.append({"case_id": case_id, "card_md": str(card), "calc_input": calc})

    # --- Pourbaix (system A) ---
    add("baseline_none", a_card, a_base(a_template))

    c = a_base(a_template, 7, 9); c["grid_refine"] = {"mode": "boundary", "n_layers": 1, "factor": 2}
    add("boundary_1layer", a_card, c)

    c = a_base(a_template, 7, 9); c["grid_refine"] = {"mode": "boundary", "n_layers": 2, "factor": 2}
    add("boundary_2layer", a_card, c)

    c = a_base(a_template); c["grid_refine"] = {"mode": "none", "factor": 4}
    add("none_with_factor", a_card, c)

    c = a_base(a_template); c["grid_refine"] = {"mode": "boundary", "n_layers": 0, "factor": 2}
    add("boundary_zero_layers", a_card, c)

    c = a_base(a_template); c["grid_refine"] = {"mode": "boundary", "n_layers": 1}
    add("boundary_missing_factor", a_card, c)

    c = a_base(a_template); c["grid_refine"] = {"mode": "adaptive"}
    add("bogus_mode", a_card, c)

    c = a_base(a_template); del c["grid_refine"]
    add("missing_grid_refine", a_card, c)

    add("tiny_2x2", a_card, a_base(a_template, 2, 2))

    add("single_point_axis", a_card, a_base(a_template, 1, 9))

    c = a_base(a_template)
    for ax in c["sweep_axes"]:
        if ax["name"] == "E_V":
            ax["min"] = 0.0; ax["max"] = 0.0
    add("degenerate_axis", a_card, c)

    c = a_base(a_template)
    for ax in c["sweep_axes"]:
        if ax["name"] == "pH":
            ax["min"] = 14.0; ax["max"] = 0.0
    add("reversed_axis", a_card, c)

    c = a_base(a_template)
    c["sweep_axes"] = [ax for ax in c["sweep_axes"] if ax["name"] == "pH"]
    add("one_axis_pourbaix", a_card, c)

    c = a_base(a_template)
    c["sweep_axes"].append({"name": "T_C", "min": 25.0, "max": 50.0, "n_points": 3})
    add("three_axes_pourbaix", a_card, c)

    c = a_base(a_template)
    for ax in c["sweep_axes"]:
        if ax["name"] == "pH":
            ax["name"] = "Ph"
    add("axis_name_typo", a_card, c)

    c = a_base(a_template); c["sweep_method"] = "nernst_sweep"
    add("unknown_sweep_method", a_card, c)

    add("zero_ionic_strength", a_card, set_bind_and_init(a_base(a_template), "I", 0.0))
    add("zero_total_Fe", a_card, set_bind_and_init(a_base(a_template), "Fe", 0.0))
    add("negative_total_Fe", a_card, set_bind_and_init(a_base(a_template), "Fe", -0.001))

    # --- pH sweep (system B) ---
    def b_base(n=25):
        c = copy.deepcopy(b_template)
        c["sweep_axes"][0]["n_points"] = n
        return c

    add("ph_baseline", b_card, b_base())

    c = b_base(); c["grid_refine"] = {"mode": "boundary", "n_layers": 1, "factor": 2}
    add("ph_with_refinement", b_card, c)

    c = b_base()
    c["sweep_axes"][0]["min"] = 14.0; c["sweep_axes"][0]["max"] = 0.0
    add("ph_axis_reversed", b_card, c)

    add("ph_single_point", b_card, b_base(1))

    return cases


def classify(rec):
    """Return (classification, rationale)."""
    if rec.get("timeout"):
        return "HANG", f"subprocess timeout after {TIMEOUT_S}s"
    if rec.get("driver_error"):
        return "CRASH", "runner produced no RESULT_JSON line: " + rec["driver_error"][:200]
    if rec["ok"]:
        if rec["n_out_files"] >= 1:
            return "PASS_OK", f"returned dict, {rec['n_out_files']} output files"
        return "CRASH", "returned without raising but wrote zero output files"
    et = rec["exc_type"]
    solve_started = rec["n_out_files"] > 0
    if et in CRASH_TYPES:
        return "CRASH", f"{et} is a crash-class exception"
    if solve_started:
        return "CRASH", f"{et} raised after solve began ({rec['n_out_files']} files already in out dir)"
    msg = (rec["exc_msg"] or "").strip()
    if len(msg) >= 15:
        return "PASS_REJECTED", f"{et} with explanatory message before any solving (0 files written)"
    return "CRASH", f"{et} with opaque/empty message: {msg!r}"


def _existing_file(value):
    path = Path(value).expanduser().absolute()
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"Input file does not exist: {path}")
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run solver edge cases using two explicitly supplied input systems.")
    parser.add_argument("--a-card", required=True, type=_existing_file,
                        help="System A (Fe Pourbaix) free-energy Markdown card")
    parser.add_argument("--a-calc", required=True, type=_existing_file,
                        help="System A calculation-input JSON card")
    parser.add_argument("--b-card", required=True, type=_existing_file,
                        help="System B (Cu-ammonia pH sweep) free-energy Markdown card")
    parser.add_argument("--b-calc", required=True, type=_existing_file,
                        help="System B calculation-input JSON card")
    parser.add_argument("--output-dir", type=Path,
                        default=REPO_ROOT / "_output" / "Diagnostics" / "edge_case_matrix")
    parser.add_argument("case_ids", nargs="*", help="Optional case IDs to run")
    args = parser.parse_args(argv)
    cases = build_cases(args.a_card, args.a_calc, args.b_card, args.b_calc)
    run_root = args.output_dir.expanduser().absolute()
    cases_dir = run_root / "cases"
    logs_dir = run_root / "logs"
    out_root = run_root / "out"
    for directory in (cases_dir, logs_dir, out_root):
        directory.mkdir(parents=True, exist_ok=True)
    results_path = run_root / "results.jsonl"
    results_path.write_text("", encoding="utf-8")

    only = set(args.case_ids)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")

    print(f"{len(cases)} cases built")
    summary = []
    for case in cases:
        cid = case["case_id"]
        if only and cid not in only:
            continue
        out_dir = out_root / cid
        if not out_dir.resolve().is_relative_to(out_root.resolve()):
            raise ValueError(f"Case output escapes the output directory: {out_dir}")
        if out_dir.exists():
            shutil.rmtree(out_dir)
        case["out_dir"] = str(out_dir)
        case_file = cases_dir / f"{cid}.json"
        case_file.write_text(json.dumps(case, indent=1), encoding="utf-8")

        print(f"[{time.strftime('%H:%M:%S')}] {cid} ...", flush=True)
        t0 = time.time()
        rec = {"case_id": cid, "ok": False, "exc_type": None, "exc_msg": None,
               "tb_tail": [], "n_out_files": 0, "timeout": False, "driver_error": None}
        try:
            proc = subprocess.run(
                [PY, "-u", str(RUNNER), str(case_file)],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=TIMEOUT_S, env=env, cwd=str(HERE),
            )
            log = (logs_dir / f"{cid}.log")
            log.write_text(
                f"# exit={proc.returncode} elapsed={time.time()-t0:.1f}s\n"
                f"===== STDOUT =====\n{proc.stdout}\n===== STDERR =====\n{proc.stderr}\n",
                encoding="utf-8")
            line = next((ln for ln in reversed(proc.stdout.splitlines())
                         if ln.startswith("RESULT_JSON:")), None)
            if line is None:
                rec["driver_error"] = (proc.stderr or proc.stdout or "no output").strip()[-400:]
            else:
                rec.update(json.loads(line[len("RESULT_JSON:"):]))
        except subprocess.TimeoutExpired as te:
            rec["timeout"] = True
            (logs_dir / f"{cid}.log").write_text(
                f"# TIMEOUT after {TIMEOUT_S}s\n===== STDOUT =====\n{te.stdout or ''}\n"
                f"===== STDERR =====\n{te.stderr or ''}\n", encoding="utf-8")
            try:
                rec["n_out_files"] = sum(1 for p in out_dir.rglob("*") if p.is_file())
            except OSError:
                pass

        cls, why = classify(rec)
        rec["classification"] = cls
        rec["rationale"] = why
        rec["wall_s"] = round(time.time() - t0, 1)
        with results_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        summary.append((cid, cls, rec.get("exc_type"), (rec.get("exc_msg") or "")[:90]))
        print(f"    -> {cls} ({why}) [{rec['wall_s']}s]", flush=True)

    print("\n===== SUMMARY =====")
    for cid, cls, et, msg in summary:
        print(f"{cid:26s} {cls:14s} {et or '-':16s} {msg}")
    from collections import Counter
    print("\ncounts:", dict(Counter(c for _, c, _, _ in summary)))


if __name__ == "__main__":
    main()
