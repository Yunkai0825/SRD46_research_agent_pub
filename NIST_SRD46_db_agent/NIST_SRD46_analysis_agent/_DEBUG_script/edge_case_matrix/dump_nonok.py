import json
from pathlib import Path

def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="Show unsuccessful edge-case results.")
    parser.add_argument("results", type=Path, help="Path to results.jsonl from driver.py")
    args = parser.parse_args(argv)
    res = args.results
    for line in res.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["classification"] == "PASS_OK":
            continue
        print("=" * 100)
        print(f"{r['case_id']} -> {r['classification']}  [{r['wall_s']}s]  {r['exc_type']}")
        print("MSG:", (r.get("exc_msg") or "").strip())
        print("TB tail:")
        for f in r.get("tb_tail") or []:
            print("   ", f)


if __name__ == "__main__":
    main()
