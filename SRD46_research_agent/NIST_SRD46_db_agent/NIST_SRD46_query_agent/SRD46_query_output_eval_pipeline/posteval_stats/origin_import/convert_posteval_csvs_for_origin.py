from __future__ import annotations

import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "SRD46_query_output_eval_pipeline").exists():
            return candidate
    raise RuntimeError("Could not locate repository root from origin_import folder")


def main() -> int:
    here = Path(__file__).resolve().parent
    repo_root = _find_repo_root(here)
    sys.path.insert(0, str(repo_root))
    from SRD46_query_output_eval_pipeline.posteval_stats.origin_export import populate_origin_import

    result = populate_origin_import(csv_dir=here.parent / "csv", out_root=here.parent)
    print(f"Wrote {len(result['all_csv'])} copy-ready CSVs to {here / 'all_csv'}")
    print(f"Wrote {len(result['plot_ready'])} plot-ready CSVs to {here / 'plot_ready'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
