"""Phase-5 narrative report generator.

Reads the CSVs/JSONs emitted by ``aggregate.py`` and ``revalidate.py`` and
produces a single ``REPORT.md`` summarising the most actionable findings.
"""
from __future__ import annotations

from collections import Counter
import csv
import json
from pathlib import Path

NON_FILLER_BUCKETS = ("verified", "domain", "unverified")


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _f(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _fmt_pct(v) -> str:
    f = _f(v)
    return "n/a" if f != f else f"{f * 100:5.1f}%"


def _fmt_f(v, n: int = 3) -> str:
    f = _f(v)
    return "n/a" if f != f else f"{f:.{n}f}"


def _table(headers: list[str], aligns: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |"]
    out.append("|" + "|".join("---" + (":" if a == "right" else "") for a in aligns) + "|")
    for r in rows:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


# ---------------------------------------------------------------------------

def _sec_corpus(out_root: Path) -> str:
    incomplete = _read_csv(out_root / "_data" / "incomplete_batches.csv")
    bm = _read_csv(out_root / "csv" / "bucket_rates_by_model.csv")
    total_records = sum(int(r["n_claims"]) for r in bm)
    total_batches = 0
    try:
        meta = json.loads((out_root / "_data" / "load_meta.json").read_text(encoding="utf-8"))
        total_batches = meta.get("n_batches_scanned", 0)
    except (OSError, json.JSONDecodeError):
        pass
    lines = [
        "## 1. Corpus",
        "",
        f"- Total claim rows analysed: **{total_records:,}**",
        f"- Models in scope: **{len(bm)}**",
        f"- Incomplete batches skipped: **{len(incomplete)}**",
    ]
    if total_batches:
        lines.append(f"- Total batches scanned: **{total_batches:,}**")
    return "\n".join(lines)


def _sec_eval_answer_gaps(out_root: Path) -> str:
    rows = _read_csv(out_root / "_data" / "evaluation_answer_gaps.csv")
    if not rows:
        return (
            "## 1A. Evaluation answer gaps\n\n"
            "- No missing or incomplete evaluation-answer artifacts were detected in `_output_eval/`."
        )

    by_type = Counter(row["gap_type"] for row in rows)
    by_model = Counter(row["model"] for row in rows)
    body = [
        [
            model,
            str(total),
            str(sum(1 for row in rows if row["model"] == model and row["gap_type"] == "missing_answer")),
            str(sum(1 for row in rows if row["model"] == model and row["gap_type"] == "missing_claims")),
            str(sum(1 for row in rows if row["model"] == model and row["gap_type"] == "incomplete_claims")),
            str(sum(1 for row in rows if row["model"] == model and row["gap_type"] == "unreadable_claims")),
        ]
        for model, total in sorted(by_model.items())
    ]
    return (
        "## 1A. Evaluation answer gaps\n\n"
        f"- Runs with missing extracted answers: **{by_type.get('missing_answer', 0)}**\n"
        f"- Runs with missing claim-evaluation payloads: **{by_type.get('missing_claims', 0)}**\n"
        f"- Runs with incomplete claim-evaluation payloads: **{by_type.get('incomplete_claims', 0)}**\n"
        f"- Runs with unreadable claim-evaluation payloads: **{by_type.get('unreadable_claims', 0)}**\n"
        f"- Detailed gap report: `{out_root / 'MISSING_EVALUATION_ANSWERS_REPORT.md'}`\n\n"
        + _table(
            ["model", "total_gaps", "missing_answer", "missing_claims", "incomplete_claims", "unreadable_claims"],
            ["left", "right", "right", "right", "right", "right"],
            body,
        )
    )


def _sec_per_model(out_root: Path) -> str:
    rows = _read_csv(out_root / "csv" / "bucket_rates_by_model.csv")
    rows.sort(key=lambda r: -_f(r["verified_share"]))
    body = []
    for r in rows:
        body.append([
            r["model"],
            f"{int(r['n_claims']):,}",
            _fmt_pct(r["verified_share"]),
            _fmt_pct(r["domain_share"]),
            _fmt_pct(r["unverified_share"]),
            _fmt_pct(r["filler_share"]),
        ])
    return ("## 2. Per-model 4-bucket shares\n\n"
            + _table(
                ["model", "n_claims", "verified", "domain", "unverified", "filler"],
                ["left", "right", "right", "right", "right", "right"],
                body,
            ))


def _sec_difficulty(out_root: Path, k: int = 5) -> str:
    rows = _read_csv(out_root / "csv" / "prompt_difficulty.csv")
    if not rows:
        return ""
    metric_field = "verified_ex_domain_mean" if "verified_ex_domain_mean" in rows[0] else "verified_mean"
    stdev_field = "verified_ex_domain_stdev" if "verified_ex_domain_stdev" in rows[0] else "verified_stdev"
    rows_sorted = sorted(rows, key=lambda r: _f(r.get(metric_field, r.get("verified_mean", ""))))
    hardest = rows_sorted[:k]
    easiest = list(reversed(rows_sorted[-k:]))
    def _fmt(rs):
        return _table(
            ["question_id", "section", "verified ex-domain", "stdev", "n_models"],
            ["left", "left", "right", "right", "right"],
            [[r["question_id"], r.get("section", "?"),
              _fmt_pct(r.get(metric_field, r.get("verified_mean"))), _fmt_f(r.get(stdev_field, r.get("verified_stdev"))),
              r.get("n_models", "?")] for r in rs],
        )
    return ("## 3. Hardest / easiest prompts\n\n"
            f"### {k} hardest (lowest verified share after excluding filler and domain claims)\n\n" + _fmt(hardest)
            + f"\n\n### {k} easiest\n\n" + _fmt(easiest))


def _sec_unstable(out_root: Path, k: int = 5) -> str:
    rows = _read_csv(out_root / "csv" / "prompt_instability.csv")
    if not rows:
        return ""
    rows_sorted = sorted(rows, key=lambda r: -_f(r.get("max_within_model_stdev", "0")))
    body = [[r["question_id"], r.get("section", "?"),
             _fmt_f(r.get("max_within_model_stdev")),
             _fmt_f(r.get("mean_within_model_stdev")),
             r.get("n_models", "?")]
            for r in rows_sorted[:k]]
    return ("## 4. Most unstable prompts (highest per-model stdev across batches)\n\n"
            + _table(
                ["question_id", "section", "max stdev", "mean stdev", "n_models"],
                ["left", "left", "right", "right", "right"],
                body,
            ))


def _sec_eval_mode(out_root: Path) -> str:
    rows = _read_csv(out_root / "csv" / "eval_mode_profile.csv")
    if not rows:
        return ""
    body = []
    for r in rows:
        match = "✓" if r.get("matches_expected", "") in {"True", "true", "1"} else "✗"
        body.append([
            r["eval_mode"],
            f"{int(r.get('n_claims', 0)):,}",
            _fmt_pct(r["bucket_verified_share"]),
            _fmt_pct(r["bucket_unverified_share"]),
            r.get("dominant_claim_type", "?"),
            r.get("expected_dominant", "?"),
            match,
        ])
    return ("## 5. Per-eval-mode profile (expected vs actual)\n\n"
            + _table(
                ["eval_mode", "n_claims", "verified", "unverified",
                 "dominant_ct", "expected", "match"],
                ["left", "right", "right", "right", "left", "left", "left"],
                body,
            ))


def _sec_cross_model(out_root: Path) -> str:
    rows = _read_csv(out_root / "csv" / "cross_model_rank_correlation.csv")
    if not rows:
        return ""
    body = [[r["model_a"], r["model_b"], _fmt_f(r["spearman"]),
             r.get("n_prompts", "?")] for r in rows]
    return ("## 6. Cross-model rank correlation (per-prompt verified_share)\n\n"
            + _table(
                ["model_a", "model_b", "Spearman ρ", "n_prompts"],
                ["left", "left", "right", "right"],
                body,
            ))


def _sec_audit(out_root: Path) -> str:
    spath = out_root / "audit" / "audit_summary.json"
    if not spath.exists():
        return ("## 7. Re-validation audit\n\n"
                "_Audit step not yet run — invoke `python -m SRD46_query_output_eval_pipeline.posteval_stats audit`._")
    summary = json.loads(spath.read_text(encoding="utf-8"))
    body = []
    for r in summary:
        body.append([
            r["audit"],
            f"{int(r['total_checked']):,}",
            f"{int(r['total_flagged']):,}",
            _fmt_pct(r["flag_rate"]),
        ])
    return ("## 7. Re-validation audit headline\n\n"
            + _table(
                ["audit", "total_checked", "total_flagged", "flag_rate"],
                ["left", "right", "right", "right"],
                body,
            ))


def _sec_top_offenders(out_root: Path, audit: str, group_col: str, k: int = 5) -> str:
    """For an audit CSV, list the top-k offending values for ``group_col``."""
    path = out_root / "audit" / f"audit_{audit}.csv"
    rows = _read_csv(path)
    if not rows:
        return ""
    from collections import Counter
    c = Counter(r.get(group_col, "?") for r in rows)
    body = [[k_, str(v)] for k_, v in c.most_common(k)]
    return (f"### Top-{k} {group_col} for `{audit}` ({len(rows)} flags total)\n\n"
            + _table([group_col, "n_flags"], ["left", "right"], body))


def write_missing_evaluation_answers_report(out_root: Path) -> Path:
    out_root = Path(out_root)
    rows = _read_csv(out_root / "_data" / "evaluation_answer_gaps.csv")
    by_type = Counter(row["gap_type"] for row in rows)
    by_model = Counter(row["model"] for row in rows)
    sections: list[str] = [
        "# Missing evaluation answers report",
        "",
        "_Auto-generated by `SRD46_query_output_eval_pipeline.posteval_stats.report.write_missing_evaluation_answers_report`._",
        "",
    ]

    if not rows:
        sections.extend(
            [
                "No missing or incomplete evaluation-answer artifacts were detected.",
                "",
                f"Full corpus report: `{out_root / 'REPORT.md'}`",
                "",
            ]
        )
    else:
        sections.extend(
            [
                "## Summary",
                "",
                f"- Total affected runs: **{len(rows)}**",
                f"- Missing extracted answers: **{by_type.get('missing_answer', 0)}**",
                f"- Missing claim-evaluation payloads: **{by_type.get('missing_claims', 0)}**",
                f"- Incomplete claim-evaluation payloads: **{by_type.get('incomplete_claims', 0)}**",
                f"- Unreadable claim-evaluation payloads: **{by_type.get('unreadable_claims', 0)}**",
                "",
                "## Affected models",
                "",
                _table(
                    ["model", "affected_runs"],
                    ["left", "right"],
                    [[model, str(count)] for model, count in sorted(by_model.items())],
                ),
                "",
                "## Affected runs",
                "",
                _table(
                    ["model", "question_id", "section", "batch", "gap_type", "reason"],
                    ["left", "left", "left", "right", "left", "left"],
                    [
                        [
                            row["model"],
                            row["question_id"],
                            row["section"],
                            row["batch"],
                            row["gap_type"],
                            row["reason"],
                        ]
                        for row in rows
                    ],
                ),
                "",
                "## Artifact inventory",
                "",
                f"- Full gap CSV: `{out_root / '_data' / 'evaluation_answer_gaps.csv'}`",
                f"- Full corpus report: `{out_root / 'REPORT.md'}`",
                "",
            ]
        )

    out_path = out_root / "MISSING_EVALUATION_ANSWERS_REPORT.md"
    out_path.write_text("\n".join(sections), encoding="utf-8")
    return out_path


def write_report(out_root: Path) -> Path:
    out_root = Path(out_root)
    sections: list[str] = [
        "# Post-evaluation statistics report",
        "",
        "_Auto-generated by `SRD46_query_output_eval_pipeline.posteval_stats.report.write_report`._",
        "",
        _sec_corpus(out_root),
        "",
        _sec_eval_answer_gaps(out_root),
        "",
        _sec_per_model(out_root),
        "",
        _sec_difficulty(out_root),
        "",
        _sec_unstable(out_root),
        "",
        _sec_eval_mode(out_root),
        "",
        _sec_cross_model(out_root),
        "",
        _sec_audit(out_root),
        "",
    ]
    # If audit ran, add top-offender breakdowns
    if (out_root / "audit" / "audit_summary.json").exists():
        sections.append("## 8. Top offenders by audit\n")
        for audit, col in [
            ("evidence_missing", "question_id"),
            ("direct_numeric_fail", "question_id"),
            ("canonical_id_unknown", "prefix"),
            ("majority_unsupported", "question_id"),
        ]:
            block = _sec_top_offenders(out_root, audit, col)
            if block:
                sections.append(block)
                sections.append("")

    sections += [
        "## Files emitted",
        "",
        f"- CSV tables: `{out_root / 'csv'}`",
        f"- JSON twins: `{out_root / 'json'}`",
        f"- Figures: `{out_root / 'figures'}`",
        f"- Origin import bundle: `{out_root / 'origin_import'}`",
        f"- Audit CSVs: `{out_root / 'audit'}`",
        f"- Long-form claim table: `{out_root / '_data' / 'claims_long.csv'}`",
        f"- Evaluation-answer gap CSV: `{out_root / '_data' / 'evaluation_answer_gaps.csv'}`",
        f"- Missing evaluation answers report: `{out_root / 'MISSING_EVALUATION_ANSWERS_REPORT.md'}`",
        "",
    ]
    out_path = out_root / "REPORT.md"
    out_path.write_text("\n".join(sections), encoding="utf-8")
    write_missing_evaluation_answers_report(out_root)
    return out_path


__all__ = ["write_missing_evaluation_answers_report", "write_report"]
