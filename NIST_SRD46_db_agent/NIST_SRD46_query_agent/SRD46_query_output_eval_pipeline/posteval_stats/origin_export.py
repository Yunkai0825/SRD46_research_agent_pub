from __future__ import annotations

import csv
import json
from pathlib import Path

from .section_policy import DEFAULT_SECTION_POLICY


def _section_sort_key(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def _major_section(value: str) -> str:
    return DEFAULT_SECTION_POLICY.group_major_section(value)


CLAIM_TYPE_COLUMN_ORDER = [
    "exact_value",
    "listing",
    "range",
    "comparison",
    "counting",
    "existence_absence",
    "citation",
    "trend",
    "domain_reasoning",
    "property_attribution",
    "calculation",
    "filler",
]


def _ordered_claim_types(rows: list[dict[str, str]]) -> list[str]:
    discovered = {row["claim_type"] for row in rows if row.get("claim_type")}
    preferred = [claim_type for claim_type in CLAIM_TYPE_COLUMN_ORDER if claim_type in discovered]
    extras = sorted(discovered - set(preferred))
    return [*preferred, *extras]


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value)


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    return fieldnames, rows


def _sanitize_cell(value: str | None) -> str:
    if value is None:
        return ""
    text = str(value)
    return "" if text.lower() == "nan" else text


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _copy_all_csvs(csv_dir: Path, target_dir: Path) -> list[Path]:
    written: list[Path] = []
    target_dir.mkdir(parents=True, exist_ok=True)
    for source in sorted(csv_dir.glob("*.csv")):
        fieldnames, rows = _read_csv(source)
        if not fieldnames:
            dest = target_dir / source.name
            dest.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            written.append(dest)
            continue
        cleaned_rows = [
            {field: _sanitize_cell(row.get(field)) for field in fieldnames}
            for row in rows
        ]
        written.append(_write_csv(target_dir / source.name, fieldnames, cleaned_rows))
    return written


def _write_verified_share_heatmap_csvs(csv_dir: Path, target_dir: Path) -> list[Path]:
    source = csv_dir / "verified_share_by_claim_type_model_major_section_matrix.csv"
    if not source.exists():
        return []
    fieldnames, rows = _read_csv(source)
    raw_claim_types = [field for field in fieldnames if field not in {"major_section", "model"}]
    raw_set = set(raw_claim_types)
    claim_types = [ct for ct in CLAIM_TYPE_COLUMN_ORDER if ct in raw_set]
    claim_types.extend(ct for ct in raw_claim_types if ct not in claim_types)
    written: list[Path] = []
    for major_section in sorted({row["major_section"] for row in rows}, key=_section_sort_key):
        section_rows = [
            {"model": row["model"], **{claim_type: _sanitize_cell(row.get(claim_type)) for claim_type in claim_types}}
            for row in rows
            if row["major_section"] == major_section
        ]
        written.append(
            _write_csv(
                target_dir / f"verified_share_heatmap_section_{major_section}.csv",
                ["model", *claim_types],
                section_rows,
            )
        )
    return written


def _write_verified_share_by_claim_type_section_csvs(csv_dir: Path, target_dir: Path) -> list[Path]:
    source = csv_dir / "verified_share_by_claim_type_model_major_section.csv"
    if not source.exists():
        return []
    _fieldnames, rows = _read_csv(source)
    claim_types = _ordered_claim_types(rows)
    written: list[Path] = []
    for major_section in sorted({row["major_section"] for row in rows}, key=_section_sort_key):
        models = sorted({row["model"] for row in rows if row["major_section"] == major_section})
        row_by_key = {
            (row["claim_type"], row["model"]): row
            for row in rows
            if row["major_section"] == major_section
        }
        matrix_rows = []
        for claim_type in claim_types:
            matrix_row = {"claim_type": claim_type}
            for model in models:
                matrix_row[model] = _sanitize_cell((row_by_key.get((claim_type, model)) or {}).get("verified_share"))
            matrix_rows.append(matrix_row)
        written.append(
            _write_csv(
                target_dir / f"verified_share_by_claim_type_section_{major_section}.csv",
                ["claim_type", *models],
                matrix_rows,
            )
        )
    return written


def _write_pairwise_jaccard_matrix(csv_dir: Path, target_dir: Path) -> list[Path]:
    source = csv_dir / "pairwise_jaccard_by_model_major_section.csv"
    if not source.exists():
        return []
    _fieldnames, rows = _read_csv(source)
    models = sorted({row["model"] for row in rows})
    major_sections = sorted({row["major_section"] for row in rows}, key=_section_sort_key)
    row_by_key = {(row["major_section"], row["model"]): row for row in rows}
    matrix_rows = []
    for major_section in major_sections:
        row = {"major_section": major_section}
        for model in models:
            record = row_by_key.get((major_section, model), {})
            row[model] = _sanitize_cell(record.get("jaccard_mean"))
        matrix_rows.append(row)
    return [
        _write_csv(
            target_dir / "pairwise_jaccard_by_model_major_section_matrix.csv",
            ["major_section", *models],
            matrix_rows,
        )
    ]


def _write_claim_type_share_csvs(csv_dir: Path, target_dir: Path) -> list[Path]:
    source = csv_dir / "claim_type_share_by_model_major_section.csv"
    if not source.exists():
        return []
    _fieldnames, rows = _read_csv(source)
    claim_types = _ordered_claim_types(rows)
    written: list[Path] = []
    for major_section in sorted({row["major_section"] for row in rows}, key=_section_sort_key):
        models = sorted({row["model"] for row in rows if row["major_section"] == major_section})
        row_by_key = {
            (row["model"], row["claim_type"]): row
            for row in rows
            if row["major_section"] == major_section
        }
        matrix_rows = []
        for model in models:
            matrix_row = {"model": model}
            for claim_type in claim_types:
                matrix_row[claim_type] = _sanitize_cell((row_by_key.get((model, claim_type)) or {}).get("claim_share"))
            matrix_rows.append(matrix_row)
        written.append(
            _write_csv(
                target_dir / f"claim_type_share_section_{major_section}.csv",
                ["model", *claim_types],
                matrix_rows,
            )
        )
    return written


def _write_bucket_share_model_csvs(csv_dir: Path, target_dir: Path) -> list[Path]:
    source = csv_dir / "bucket_rates_by_model_major_section.csv"
    if not source.exists():
        return []
    _fieldnames, rows = _read_csv(source)
    models = sorted({row["model"] for row in rows})
    written: list[Path] = []
    for model in models:
        model_rows = []
        for row in sorted((item for item in rows if item["model"] == model), key=lambda item: _section_sort_key(item["major_section"])):
            model_rows.append(
                {
                    "major_section": row["major_section"],
                    "verified": _sanitize_cell(row.get("verified_share")),
                    "domain": _sanitize_cell(row.get("domain_share")),
                    "unverified": _sanitize_cell(row.get("unverified_share")),
                }
            )
        written.append(
            _write_csv(
                target_dir / f"bucket_share_major_section_{_safe_name(model)}.csv",
                ["major_section", "verified", "domain", "unverified"],
                model_rows,
            )
        )
    return written


def _write_claim_type_share_model_csvs(csv_dir: Path, target_dir: Path) -> list[Path]:
    source = csv_dir / "claim_type_share_by_model_major_section.csv"
    if not source.exists():
        return []
    _fieldnames, rows = _read_csv(source)
    models = sorted({row["model"] for row in rows})
    claim_types = _ordered_claim_types(rows)
    written: list[Path] = []
    for model in models:
        major_sections = sorted({row["major_section"] for row in rows if row["model"] == model}, key=_section_sort_key)
        row_by_key = {
            (row["major_section"], row["claim_type"]): row
            for row in rows
            if row["model"] == model
        }
        model_rows = []
        for major_section in major_sections:
            matrix_row = {"major_section": major_section}
            for claim_type in claim_types:
                matrix_row[claim_type] = _sanitize_cell((row_by_key.get((major_section, claim_type)) or {}).get("claim_share"))
            model_rows.append(matrix_row)
        written.append(
            _write_csv(
                target_dir / f"claim_type_share_major_section_{_safe_name(model)}.csv",
                ["major_section", *claim_types],
                model_rows,
            )
        )
    return written


def _write_tool_usage_top15_matrix(csv_dir: Path, target_dir: Path) -> list[Path]:
    source = csv_dir / "tool_usage_distribution.csv"
    if not source.exists():
        return []
    _fieldnames, rows = _read_csv(source)
    rows = [row for row in rows if not row["tool"].startswith("0_")]
    models = sorted({row["model"] for row in rows})
    if not models:
        return []
    by_model_tool: dict[tuple[str, str], int] = {}
    tool_totals: dict[str, int] = {}
    for row in rows:
        key = (row["model"], row["tool"])
        count = int(row.get("n_invocations") or 0)
        by_model_tool[key] = by_model_tool.get(key, 0) + count
        tool_totals[row["tool"]] = tool_totals.get(row["tool"], 0) + count
    tools = [
        tool
        for tool, _count in sorted(tool_totals.items(), key=lambda item: (-item[1], item[0]))
    ]
    matrix_rows = []
    for tool in tools:
        row = {"tool": tool}
        for model in models:
            row[model] = str(by_model_tool.get((model, tool), 0))
        matrix_rows.append(row)
    return [
        _write_csv(
            target_dir / "tool_usage_top15_by_model.csv",
            ["tool", *models],
            matrix_rows,
        )
    ]


def _write_prompt_difficulty_major_section(csv_dir: Path, target_dir: Path) -> list[Path]:
    source = csv_dir / "prompt_difficulty.csv"
    if not source.exists():
        return []
    _fieldnames, rows = _read_csv(source)
    def _difficulty_metric(row: dict[str, str]) -> float:
        for field in ("verified_ex_domain_mean", "verified_mean"):
            value = row.get(field)
            if value in (None, ""):
                continue
            try:
                return float(value)
            except ValueError:
                continue
        return 1.0

    ranked_rows = []
    for index, row in enumerate(sorted(rows, key=_difficulty_metric), start=1):
        ranked_rows.append(
            {
                "difficulty_rank": str(index),
                "question_id": row["question_id"],
                "section": _major_section(row["section"]),
                "eval_mode": row.get("eval_mode") or "",
                "n_scored_runs": _sanitize_cell(row.get("n_scored_runs")),
                "verified_ex_domain_mean": _sanitize_cell(row.get("verified_ex_domain_mean")),
                "verified_ex_domain_stdev": _sanitize_cell(row.get("verified_ex_domain_stdev")),
                "unverified_ex_domain_mean": _sanitize_cell(row.get("unverified_ex_domain_mean")),
                "verified_mean": _sanitize_cell(row.get("verified_mean")),
                "verified_stdev": _sanitize_cell(row.get("verified_stdev")),
                "unverified_mean": _sanitize_cell(row.get("unverified_mean")),
                "n_runs": _sanitize_cell(row.get("n_runs")),
                "n_models": _sanitize_cell(row.get("n_models")),
            }
        )
    return [
        _write_csv(
            target_dir / "prompt_difficulty_major_section.csv",
            [
                "difficulty_rank",
                "question_id",
                "section",
                "eval_mode",
                "n_scored_runs",
                "verified_ex_domain_mean",
                "verified_ex_domain_stdev",
                "unverified_ex_domain_mean",
                "verified_mean",
                "verified_stdev",
                "unverified_mean",
                "n_runs",
                "n_models",
            ],
            ranked_rows,
        )
    ]


def _script_text() -> str:
    return """from __future__ import annotations

import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / \"SRD46_query_output_eval_pipeline\").exists():
            return candidate
    raise RuntimeError(\"Could not locate repository root from origin_import folder\")


def main() -> int:
    here = Path(__file__).resolve().parent
    repo_root = _find_repo_root(here)
    sys.path.insert(0, str(repo_root))
    from NIST_SRD46_db_agent.NIST_SRD46_query_agent.SRD46_query_output_eval_pipeline.posteval_stats.origin_export import populate_origin_import

    result = populate_origin_import(csv_dir=here.parent / \"csv\", out_root=here.parent)
    print(f\"Wrote {len(result['all_csv'])} copy-ready CSVs to {here / 'all_csv'}\")
    print(f\"Wrote {len(result['plot_ready'])} plot-ready CSVs to {here / 'plot_ready'}\")
    return 0


if __name__ == \"__main__\":
    raise SystemExit(main())
"""


def populate_origin_import(*, csv_dir: Path, out_root: Path) -> dict[str, list[Path] | Path]:
    origin_dir = out_root / "origin_import"
    all_csv_dir = origin_dir / "all_csv"
    plot_ready_dir = origin_dir / "plot_ready"

    copied = _copy_all_csvs(csv_dir, all_csv_dir)
    plot_ready = []
    plot_ready.extend(_write_verified_share_heatmap_csvs(csv_dir, plot_ready_dir))
    plot_ready.extend(_write_verified_share_by_claim_type_section_csvs(csv_dir, plot_ready_dir))
    plot_ready.extend(_write_pairwise_jaccard_matrix(csv_dir, plot_ready_dir))
    plot_ready.extend(_write_claim_type_share_csvs(csv_dir, plot_ready_dir))
    plot_ready.extend(_write_bucket_share_model_csvs(csv_dir, plot_ready_dir))
    plot_ready.extend(_write_claim_type_share_model_csvs(csv_dir, plot_ready_dir))
    plot_ready.extend(_write_tool_usage_top15_matrix(csv_dir, plot_ready_dir))
    plot_ready.extend(_write_prompt_difficulty_major_section(csv_dir, plot_ready_dir))

    script_path = origin_dir / "convert_posteval_csvs_for_origin.py"
    script_path.write_text(_script_text(), encoding="utf-8")

    readme_path = origin_dir / "README.md"
    readme_path.write_text(
        "\n".join(
            [
                "# Origin Import Bundle",
                "",
                "- `all_csv/`: normalized copies of every CSV under `../csv/` with `nan` cells blanked for OriginPro import.",
                "- `plot_ready/`: extra wide tables for heatmaps, verified-share and claim-type major-section facets, per-model major-section stacked bars, tool-usage grouped bars, and prompt-difficulty ranking.",
                "- `convert_posteval_csvs_for_origin.py`: rerun the export after any CSV changes.",
                "",
                "Typical usage:",
                "",
                "```bash",
                "python convert_posteval_csvs_for_origin.py",
                "```",
            ]
        ),
        encoding="utf-8",
    )

    manifest_path = origin_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "source_csv_dir": str(csv_dir),
                "all_csv": [path.name for path in copied],
                "plot_ready": [path.name for path in plot_ready],
                "script": script_path.name,
                "readme": readme_path.name,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    return {
        "origin_dir": origin_dir,
        "all_csv": copied,
        "plot_ready": plot_ready,
        "script": script_path,
        "readme": readme_path,
        "manifest": manifest_path,
    }


__all__ = ["populate_origin_import"]