# Runs ONE edge case in its own process. Usage: python case_runner.py <case.json>
# Prints exactly one line starting with RESULT_JSON: to stdout at the end.
import json
import sys
import time
import traceback
from pathlib import Path

REPO = Path(__file__).absolute().parents[4]
NUMCALC = REPO / "NIST_SRD46_db_agent" / "NIST_SRD46_analysis_agent" / "NIST_SRD46_core_numcalc_pipeline"
CALC_PIPE = (REPO / "NIST_SRD46_db_agent" / "NIST_SRD46_analysis_agent"
             / "NIST_SRD46_calc_input_building_agentic_pipeline")
CARD_HELPERS = CALC_PIPE / "card_management_helpers"
for p in (str(REPO), str(NUMCALC), str(CALC_PIPE), str(CARD_HELPERS)):
    if p not in sys.path:
        sys.path.insert(0, p)


def tb_frames(exc, n=3):
    frames = []
    for fr in traceback.extract_tb(exc.__traceback__):
        frames.append(f"{fr.filename}:{fr.lineno}: {fr.line or ''}".strip())
    return frames[-n:]


def main():
    case_path = Path(sys.argv[1])
    case = json.loads(case_path.read_text(encoding="utf-8"))
    out_dir = Path(case["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    res = {"case_id": case["case_id"], "ok": False, "exc_type": None, "exc_msg": None,
           "tb_tail": [], "n_out_files": 0, "elapsed_s": None, "returned_keys": None,
           "n_output_paths": None}
    t0 = time.time()
    try:
        from SRD46_numcalculator_api import run_calculation
        result = run_calculation(
            card_source=case["card_md"],
            calc_input=case["calc_input"],
            output_dir=str(out_dir),
            debug=False,
        )
        res["ok"] = True
        if isinstance(result, dict):
            res["returned_keys"] = sorted(result.keys())
            paths = result.get("output_paths") or []
            res["n_output_paths"] = len(paths)
    except BaseException as exc:  # noqa: BLE001 - report everything, suppress nothing
        res["exc_type"] = type(exc).__name__
        res["exc_msg"] = str(exc)[:600]
        res["tb_tail"] = tb_frames(exc)
        print("=== FULL TRACEBACK ===", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
    finally:
        res["elapsed_s"] = round(time.time() - t0, 1)
        try:
            res["n_out_files"] = sum(1 for p in out_dir.rglob("*") if p.is_file())
        except OSError:
            res["n_out_files"] = -1

    sys.stdout.flush()
    sys.stderr.flush()
    print("RESULT_JSON:" + json.dumps(res))


if __name__ == "__main__":
    main()
