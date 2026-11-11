"""Phase-3 plots. Reads the CSVs emitted by ``aggregate.py`` and writes PNGs.

Matplotlib only — no seaborn. CSVs are read with stdlib ``csv`` to avoid a
hard pandas dependency.
"""
from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.lines as mlines  # noqa: E402
import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib import colors as mcolors  # noqa: E402

from .section_policy import DEFAULT_SECTION_POLICY

NON_FILLER_BUCKETS = ("verified", "domain", "unverified")
BUCKET_COLORS = {
    "verified": "#2ca02c",
    "domain": "#1f77b4",
    "unverified": "#d62728",
    "filler": "#7f7f7f",
}
BUCKET_HATCHES = {
    "verified": "////",
    "domain": "....",
    "unverified": "xx",
}
CLAIM_TYPE_COLORS = {
    "counting": "#0d6efd",
    "comparison": "#7c3aed",
    "trend": "#d63384",
    "listing": "#0dcaf0",
    "range": "#fd7e14",
    "exact_value": "#198754",
    "property_attribution": "#6c757d",
    "existence_absence": "#dc3545",
    "calculation": "#6610f2",
    "citation": "#795548",
    "domain_reasoning": "#8b5cf6",
    "filler": "#adb5bd",
}
CLAIM_TYPES = (
    "counting", "comparison", "trend", "listing", "range", "exact_value",
    "property_attribution", "existence_absence", "calculation", "citation",
    "domain_reasoning", "filler",
)
SUPPORT_CLASSES = (
    "direct", "inferred", "domain_knowledge", "unsupported", "no_tool_data",
)


def _read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _f(v: str) -> float:
    if v is None or v == "":
        return float("nan")
    try:
        return float(v)
    except ValueError:
        return float("nan")


def _save(fig, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return out


def _qid_sort_key(qid: str) -> tuple[int, ...]:
    if not qid:
        return (10**9,)
    text = qid[1:] if qid.startswith("Q") else qid
    try:
        return tuple(int(part) for part in text.split("."))
    except ValueError:
        return (10**9,)


def _section_sort_key(section: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in section.split("."))
    except ValueError:
        return (10**9,)


def _major_section(section: str) -> str:
    return DEFAULT_SECTION_POLICY.group_major_section(section)


# ---------------------------------------------------------------------------
# 2.A claim-level plots
# ---------------------------------------------------------------------------

def plot_bucket_share_by_model(csv_dir: Path, fig_dir: Path) -> Path:
    rows = _read_csv(csv_dir / "bucket_rates_by_model.csv")
    models = [r["model"] for r in rows]
    bottom = [0.0] * len(models)
    fig, ax = plt.subplots(figsize=(8, 5))
    for b in NON_FILLER_BUCKETS:
        vals = [_f(r[f"{b}_share"]) for r in rows]
        ax.bar(models, vals, bottom=bottom, color=BUCKET_COLORS[b], label=b)
        bottom = [a + v for a, v in zip(bottom, vals)]
    ax.set_ylabel("Share of non-filler claims")
    ax.set_title("Bucket shares per model (verified / domain / unverified)")
    ax.set_ylim(0, 1)
    ax.legend(loc="upper right")
    return _save(fig, fig_dir / "bucket_share_by_model.png")


def plot_bucket_share_by_section_facet(csv_dir: Path, fig_dir: Path) -> Path:
    rows = _read_csv(csv_dir / "bucket_rates_by_model_section.csv")
    by_model: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_model[r["model"]].append(r)
    models = sorted(by_model)
    n = len(models)
    fig, axes = plt.subplots(1, n, figsize=(4 * n, 4.5), sharey=True)
    if n == 1:
        axes = [axes]
    for ax, model in zip(axes, models):
        items = sorted(by_model[model], key=lambda r: _section_sort_key(r["section"]))
        sections = [r["section"] for r in items]
        bottom = [0.0] * len(sections)
        for b in NON_FILLER_BUCKETS:
            vals = [_f(r[f"{b}_share"]) for r in items]
            ax.bar(sections, vals, bottom=bottom, color=BUCKET_COLORS[b], label=b)
            bottom = [a + v for a, v in zip(bottom, vals)]
        ax.set_title(model)
        ax.set_ylim(0, 1)
        ax.tick_params(axis="x", rotation=45)
    axes[0].set_ylabel("Share of non-filler claims")
    axes[-1].legend(loc="upper right", fontsize=8)
    fig.suptitle("Bucket shares per section, faceted by model")
    return _save(fig, fig_dir / "bucket_share_by_section_facet.png")


def plot_bucket_share_by_major_section_facet(csv_dir: Path, fig_dir: Path) -> Path:
    rows = _read_csv(csv_dir / "bucket_rates_by_model_major_section.csv")
    if not rows:
        raise ValueError("bucket_rates_by_model_major_section.csv is missing or empty")

    by_model: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_model[row["model"]].append(row)

    models = sorted(by_model)
    n = len(models)
    fig, axes = plt.subplots(1, n, figsize=(3.4 * n, 4.6), sharey=True)
    if n == 1:
        axes = [axes]

    for ax, model in zip(axes, models):
        items = sorted(by_model[model], key=lambda row: _section_sort_key(row["major_section"]))
        major_sections = [row["major_section"] for row in items]
        bottom = [0.0] * len(major_sections)
        for bucket in NON_FILLER_BUCKETS:
            vals = [_f(row[f"{bucket}_share"]) for row in items]
            ax.bar(major_sections, vals, bottom=bottom, color=BUCKET_COLORS[bucket], label=bucket)
            bottom = [cur + val for cur, val in zip(bottom, vals)]
        ax.set_title(model)
        ax.set_ylim(0, 1)
        ax.tick_params(axis="x", rotation=0)

    axes[0].set_ylabel("Share of non-filler claims")
    axes[-1].legend(loc="upper right", fontsize=8)
    fig.suptitle("Bucket shares per major section, faceted by model")
    return _save(fig, fig_dir / "bucket_share_by_major_section_facet.png")


def plot_bucket_share_by_section_facet_detailed(csv_dir: Path, fig_dir: Path) -> Path:
    detailed_rows = _read_csv(csv_dir / "support_by_claim_type_model_section.csv")
    totals_rows = _read_csv(csv_dir / "bucket_rates_by_model_section.csv")
    totals = {
        (row["model"], row["section"]): int(row["n_nonfiller"])
        for row in totals_rows
    }
    by_model_section_claim: dict[tuple[str, str], dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(dict))
    for row in detailed_rows:
        key = (row["model"], row["section"])
        ct = row["claim_type"]
        by_model_section_claim[key][ct] = {
            bucket: int(row.get(f"{bucket}_count", 0) or 0)
            for bucket in NON_FILLER_BUCKETS
        }

    models = sorted({model for model, _ in by_model_section_claim})
    n = len(models)
    fig, axes = plt.subplots(1, n, figsize=(4.8 * n, 5.4), sharey=True)
    if n == 1:
        axes = [axes]

    claim_types = [claim_type for claim_type in CLAIM_TYPES if claim_type != "filler"]
    for ax, model in zip(axes, models):
        sections = sorted(
            {section for mdl, section in by_model_section_claim if mdl == model},
            key=_section_sort_key,
        )
        bottom = [0.0] * len(sections)
        for bucket in NON_FILLER_BUCKETS:
            for claim_type in claim_types:
                vals = []
                for section in sections:
                    denom = totals.get((model, section), 0)
                    count = by_model_section_claim.get((model, section), {}).get(claim_type, {}).get(bucket, 0)
                    vals.append((count / denom) if denom else 0.0)
                ax.bar(
                    sections,
                    vals,
                    bottom=bottom,
                    color=mcolors.to_rgba(CLAIM_TYPE_COLORS[claim_type], alpha=0.16),
                    hatch=BUCKET_HATCHES[bucket],
                    width=0.75,
                    edgecolor=CLAIM_TYPE_COLORS[claim_type],
                    linewidth=0.4,
                )
                bottom = [cur + val for cur, val in zip(bottom, vals)]
        ax.set_title(model)
        ax.set_ylim(0, 1)
        ax.tick_params(axis="x", rotation=45)

    axes[0].set_ylabel("Share of non-filler claims")
    bucket_handles = [
        mpatches.Patch(facecolor="white", edgecolor="#222222", hatch=BUCKET_HATCHES[bucket], label=bucket)
        for bucket in NON_FILLER_BUCKETS
    ]
    claim_handles = [
        mpatches.Patch(
            facecolor=mcolors.to_rgba(CLAIM_TYPE_COLORS[claim_type], alpha=0.16),
            edgecolor=CLAIM_TYPE_COLORS[claim_type],
            linewidth=1.0,
            label=claim_type,
        )
        for claim_type in claim_types
    ]
    leg1 = axes[0].legend(handles=bucket_handles, title="grounding bucket pattern", loc="upper left", fontsize=7, title_fontsize=8)
    axes[0].add_artist(leg1)
    fig.legend(
        handles=claim_handles,
        title="claim type color",
        loc="lower center",
        ncol=4,
        fontsize=7,
        title_fontsize=8,
        bbox_to_anchor=(0.5, -0.05),
    )
    fig.suptitle("Detailed bucket shares per section: bucket patterns + claim-type colors")
    return _save(fig, fig_dir / "bucket_share_by_section_facet_detailed.png")


def plot_bucket_share_by_prompt_facet_detailed(csv_dir: Path, fig_dir: Path) -> Path:
    detailed_rows = _read_csv(csv_dir / "support_by_claim_type_model_section.csv")
    totals_rows = _read_csv(csv_dir / "bucket_rates_by_model_section.csv")
    if not detailed_rows or not totals_rows:
        raise ValueError(
            "support_by_claim_type_model_section.csv and bucket_rates_by_model_section.csv are required"
        )

    totals: dict[tuple[str, str], int] = {}
    by_model_section_claim: dict[tuple[str, str], dict[str, int]] = defaultdict(dict)

    for row in totals_rows:
        key = (row["model"], row["section"])
        totals[key] = int(row.get("n_claims", 0) or 0)

    for row in detailed_rows:
        key = (row["model"], row["section"])
        claim_type = row["claim_type"]
        by_model_section_claim[key][claim_type] = int(row.get("row_total", 0) or 0)

    models = sorted({model for model, _ in by_model_section_claim})
    if not models:
        raise ValueError("support_by_claim_type_model_section.csv is missing or empty")

    max_sections = max(
        len({section for model, section in by_model_section_claim if model == current_model})
        for current_model in models
    )
    cols = 2 if len(models) > 1 else 1
    rows_n = (len(models) + cols - 1) // cols
    subplot_w = max(7.0, min(12.0, 0.75 * max_sections + 3.5))
    subplot_h = 5.2
    fig, axes = plt.subplots(
        rows_n,
        cols,
        figsize=(subplot_w * cols, subplot_h * rows_n),
        squeeze=False,
        sharey=True,
    )

    claim_types = list(CLAIM_TYPES)
    for ax, model in zip(axes.ravel(), models):
        sections = sorted(
            {section for current_model, section in by_model_section_claim if current_model == model},
            key=_section_sort_key,
        )
        xs = list(range(len(sections)))
        bottom = [0.0] * len(sections)
        for claim_type in claim_types:
            vals = []
            for section in sections:
                denom = totals.get((model, section), 0)
                count = by_model_section_claim.get((model, section), {}).get(claim_type, 0)
                vals.append((count / denom) if denom else 0.0)
            ax.bar(
                xs,
                vals,
                bottom=bottom,
                color=CLAIM_TYPE_COLORS[claim_type],
                width=0.82,
                edgecolor="#ffffff",
                linewidth=0.25,
            )
            bottom = [cur + val for cur, val in zip(bottom, vals)]

        ax.set_title(model)
        ax.set_ylim(0, 1)
        ax.set_xlim(-0.6, len(sections) - 0.4 if sections else 0.4)
        ax.set_xticks(xs)
        ax.set_xticklabels(sections, rotation=45, ha="right", fontsize=7)
        ax.tick_params(axis="y", labelsize=8)

    for ax in axes.ravel()[len(models):]:
        ax.axis("off")

    axes[0][0].set_ylabel("Share of all claims")
    claim_handles = [
        mpatches.Patch(
            facecolor=CLAIM_TYPE_COLORS[claim_type],
            edgecolor="#ffffff",
            linewidth=0.4,
            label=claim_type,
        )
        for claim_type in claim_types
    ]
    fig.legend(
        handles=claim_handles,
        title="claim type",
        loc="lower center",
        ncol=4,
        fontsize=7,
        title_fontsize=8,
        bbox_to_anchor=(0.5, -0.02),
    )
    fig.suptitle("Claim-type shares per section")
    return _save(fig, fig_dir / "bucket_share_by_prompt_facet_detailed.png")


def plot_claim_type_share_by_major_section_collage(csv_dir: Path, fig_dir: Path) -> Path:
    rows = _read_csv(csv_dir / "claim_type_share_by_model_major_section.csv")
    if not rows:
        raise ValueError("claim_type_share_by_model_major_section.csv is missing or empty")

    models = sorted({row["model"] for row in rows})
    major_sections = sorted({row["major_section"] for row in rows}, key=_section_sort_key)
    shares = {
        (row["major_section"], row["model"], row["claim_type"]): _f(row["claim_share"])
        for row in rows
    }

    fig, axes = plt.subplots(1, len(major_sections), figsize=(3.6 * len(major_sections), 5.2), squeeze=False, sharey=True)
    xs = list(range(len(models)))
    claim_types = list(CLAIM_TYPES)
    for ax, major_section in zip(axes.ravel(), major_sections):
        bottom = [0.0] * len(models)
        for claim_type in claim_types:
            vals = [
                shares.get((major_section, model, claim_type), float("nan"))
                for model in models
            ]
            vals = [0.0 if math.isnan(value) else value for value in vals]
            ax.bar(
                xs,
                vals,
                bottom=bottom,
                color=CLAIM_TYPE_COLORS[claim_type],
                width=0.82,
                edgecolor="#ffffff",
                linewidth=0.25,
            )
            bottom = [cur + val for cur, val in zip(bottom, vals)]
        ax.set_title(f"section {major_section}")
        ax.set_ylim(0, 1)
        ax.set_xticks(xs)
        ax.set_xticklabels(models, rotation=45, ha="right", fontsize=7)
        ax.tick_params(axis="y", labelsize=8)

    axes[0][0].set_ylabel("Share of all claims")
    claim_handles = [
        mpatches.Patch(
            facecolor=CLAIM_TYPE_COLORS[claim_type],
            edgecolor="#ffffff",
            linewidth=0.4,
            label=claim_type,
        )
        for claim_type in claim_types
    ]
    fig.legend(
        handles=claim_handles,
        title="claim type",
        loc="lower center",
        ncol=4,
        fontsize=7,
        title_fontsize=8,
        bbox_to_anchor=(0.5, -0.02),
    )
    fig.suptitle("Claim-type shares by model, faceted by major section")
    return _save(fig, fig_dir / "claim_type_share_by_major_section_collage.png")


def _aggregate_support_by_claim_type_major_section(rows: list[dict]) -> list[dict[str, object]]:
    pooled: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {"verified_count": 0, "domain_count": 0, "unverified_count": 0, "row_total": 0}
    )
    major_sections = sorted({row["major_section"] for row in rows}, key=_section_sort_key)
    for row in rows:
        key = (row["major_section"], row["claim_type"])
        pooled[key]["verified_count"] += int(row.get("verified_count") or 0)
        pooled[key]["domain_count"] += int(row.get("domain_count") or 0)
        pooled[key]["unverified_count"] += int(row.get("unverified_count") or 0)
        pooled[key]["row_total"] += int(row.get("row_total") or 0)

    aggregated: list[dict[str, object]] = []
    for major_section in major_sections:
        for claim_type in CLAIM_TYPES:
            if claim_type == "filler":
                continue
            stats = pooled[(major_section, claim_type)]
            row_total = stats["row_total"]
            aggregated.append(
                {
                    "major_section": major_section,
                    "claim_type": claim_type,
                    "verified_count": stats["verified_count"],
                    "domain_count": stats["domain_count"],
                    "unverified_count": stats["unverified_count"],
                    "row_total": row_total,
                    "verified_share": (stats["verified_count"] / row_total) if row_total else float("nan"),
                    "domain_share": (stats["domain_count"] / row_total) if row_total else float("nan"),
                    "unverified_share": (stats["unverified_count"] / row_total) if row_total else float("nan"),
                }
            )
    return aggregated


def plot_verified_share_by_claim_type_major_section_collage(csv_dir: Path, fig_dir: Path) -> Path:
    rows = _read_csv(csv_dir / "support_by_claim_type_model_major_section.csv")
    if not rows:
        raise ValueError("support_by_claim_type_model_major_section.csv is missing or empty")

    rows = _aggregate_support_by_claim_type_major_section(rows)
    major_sections = sorted({row["major_section"] for row in rows}, key=_section_sort_key)
    claim_types = [claim_type for claim_type in CLAIM_TYPES if claim_type != "filler"]
    shares = {
        (row["major_section"], row["claim_type"], bucket): _f(row[f"{bucket}_share"])
        for row in rows
        for bucket in NON_FILLER_BUCKETS
    }

    fig, axes = plt.subplots(1, len(major_sections), figsize=(5.0 * len(major_sections), 5.4), squeeze=False, sharey=True)
    xs = list(range(len(claim_types)))
    for ax, major_section in zip(axes.ravel(), major_sections):
        bottom = [0.0] * len(claim_types)
        for bucket in NON_FILLER_BUCKETS:
            vals = [shares.get((major_section, claim_type, bucket), float("nan")) for claim_type in claim_types]
            vals = [0.0 if math.isnan(value) else value for value in vals]
            ax.bar(
                xs,
                vals,
                bottom=bottom,
                width=0.82,
                color=BUCKET_COLORS[bucket],
                edgecolor="#ffffff",
                linewidth=0.25,
                label=bucket,
            )
            bottom = [cur + val for cur, val in zip(bottom, vals)]
        ax.set_title(f"section {major_section}")
        ax.set_ylim(0, 1)
        ax.set_xticks(xs)
        ax.set_xticklabels(claim_types, rotation=45, ha="right", fontsize=7)
        ax.tick_params(axis="y", labelsize=8)

    axes[0][0].set_ylabel("Share within claim type")
    bucket_handles = [
        mpatches.Patch(color=BUCKET_COLORS[bucket], label=bucket)
        for bucket in NON_FILLER_BUCKETS
    ]
    fig.legend(bucket_handles, [bucket for bucket in NON_FILLER_BUCKETS], title="bucket", loc="lower center", ncol=len(NON_FILLER_BUCKETS), fontsize=7, title_fontsize=8, bbox_to_anchor=(0.5, -0.02))
    fig.suptitle("Claim-type bucket split, aggregated across models and faceted by major section")
    return _save(fig, fig_dir / "verified_share_by_claim_type_major_section_collage.png")


def plot_verified_share_by_claim_type_model_major_section_heatmap(csv_dir: Path, fig_dir: Path) -> Path:
    rows = _read_csv(csv_dir / "verified_share_by_claim_type_model_major_section_matrix.csv")
    if not rows:
        raise ValueError("verified_share_by_claim_type_model_major_section_matrix.csv is missing or empty")

    major_sections = sorted({row["major_section"] for row in rows}, key=_section_sort_key)
    models = sorted({row["model"] for row in rows})
    claim_types = list(CLAIM_TYPES)
    row_by_key = {(row["major_section"], row["model"]): row for row in rows}

    fig, axes = plt.subplots(1, len(major_sections), figsize=(4.5 * len(major_sections), 4.8), squeeze=False, sharey=True)
    images = []
    for ax, major_section in zip(axes.ravel(), major_sections):
        matrix = np.full((len(models), len(claim_types)), np.nan)
        for y, model in enumerate(models):
            row = row_by_key.get((major_section, model))
            if row is None:
                continue
            for x, claim_type in enumerate(claim_types):
                matrix[y, x] = _f(row.get(claim_type))

        image = ax.imshow(matrix, aspect="auto", cmap="viridis", vmin=0, vmax=1)
        images.append(image)
        ax.set_title(f"section {major_section}")
        ax.set_xticks(range(len(claim_types)))
        ax.set_xticklabels(claim_types, rotation=45, ha="right", fontsize=7)
        ax.set_yticks(range(len(models)))
        ax.set_yticklabels(models, fontsize=8)
        for y in range(len(models)):
            for x in range(len(claim_types)):
                value = matrix[y, x]
                if math.isnan(value):
                    continue
                text_color = "white" if value < 0.55 else "black"
                ax.text(x, y, f"{value:.2f}", ha="center", va="center", fontsize=6, color=text_color)

    axes[0][0].set_ylabel("Model")
    fig.supxlabel("Claim type")
    if images:
        fig.colorbar(images[-1], ax=axes.ravel().tolist(), fraction=0.025, pad=0.02, label="verified fraction")
    fig.suptitle("Verified fraction by claim type and model, faceted by major section")
    return _save(fig, fig_dir / "verified_share_by_claim_type_model_major_section_heatmap.png")


def plot_claim_type_share_by_major_section_facet(csv_dir: Path, fig_dir: Path) -> Path:
    detailed_rows = _read_csv(csv_dir / "support_by_claim_type_model_major_section.csv")
    totals_rows = _read_csv(csv_dir / "bucket_rates_by_model_major_section.csv")
    if not detailed_rows or not totals_rows:
        raise ValueError(
            "support_by_claim_type_model_major_section.csv and bucket_rates_by_model_major_section.csv are required"
        )

    totals: dict[tuple[str, str], int] = {}
    by_model_major_section_claim: dict[tuple[str, str], dict[str, int]] = defaultdict(dict)

    for row in totals_rows:
        key = (row["model"], row["major_section"])
        totals[key] = int(row.get("n_claims", 0) or 0)

    for row in detailed_rows:
        key = (row["model"], row["major_section"])
        by_model_major_section_claim[key][row["claim_type"]] = int(row.get("row_total", 0) or 0)

    models = sorted({model for model, _ in by_model_major_section_claim})
    if not models:
        raise ValueError("support_by_claim_type_model_major_section.csv is missing or empty")

    fig, axes = plt.subplots(1, len(models), figsize=(4.2 * len(models), 5.0), squeeze=False, sharey=True)
    claim_types = list(CLAIM_TYPES)
    for ax, model in zip(axes.ravel(), models):
        major_sections = sorted(
            {major_section for current_model, major_section in by_model_major_section_claim if current_model == model},
            key=_section_sort_key,
        )
        xs = list(range(len(major_sections)))
        bottom = [0.0] * len(major_sections)
        for claim_type in claim_types:
            vals = []
            for major_section in major_sections:
                denom = totals.get((model, major_section), 0)
                count = by_model_major_section_claim.get((model, major_section), {}).get(claim_type, 0)
                vals.append((count / denom) if denom else 0.0)
            ax.bar(
                xs,
                vals,
                bottom=bottom,
                color=CLAIM_TYPE_COLORS[claim_type],
                width=0.82,
                edgecolor="#ffffff",
                linewidth=0.25,
            )
            bottom = [cur + val for cur, val in zip(bottom, vals)]
        ax.set_title(model)
        ax.set_ylim(0, 1)
        ax.set_xlim(-0.6, len(major_sections) - 0.4 if major_sections else 0.4)
        ax.set_xticks(xs)
        ax.set_xticklabels(major_sections, rotation=0, fontsize=8)
        ax.tick_params(axis="y", labelsize=8)

    axes[0][0].set_ylabel("Share of all claims")
    claim_handles = [
        mpatches.Patch(
            facecolor=CLAIM_TYPE_COLORS[claim_type],
            edgecolor="#ffffff",
            linewidth=0.4,
            label=claim_type,
        )
        for claim_type in claim_types
    ]
    fig.legend(
        handles=claim_handles,
        title="claim type",
        loc="lower center",
        ncol=4,
        fontsize=7,
        title_fontsize=8,
        bbox_to_anchor=(0.5, -0.02),
    )
    fig.suptitle("Claim-type shares per major section")
    return _save(fig, fig_dir / "claim_type_share_by_major_section_facet.png")


def plot_class_marker_heatmap(csv_dir: Path, fig_dir: Path, scope: str = "all") -> Path:
    """Heatmap of claim_type x support_class shares."""
    rows = _read_csv(csv_dir / f"class_marker_{scope}_shares.csv")
    if scope == "all":
        # rows already keyed by claim_type
        matrix = []
        for ct in CLAIM_TYPES:
            for r in rows:
                if r["claim_type"] == ct:
                    matrix.append([_f(r[s]) for s in SUPPORT_CLASSES])
                    break
            else:
                matrix.append([float("nan")] * len(SUPPORT_CLASSES))
        fig, ax = plt.subplots(figsize=(7, 6))
        im = ax.imshow(matrix, cmap="viridis", aspect="auto", vmin=0, vmax=1)
        ax.set_xticks(range(len(SUPPORT_CLASSES)))
        ax.set_xticklabels(SUPPORT_CLASSES, rotation=30, ha="right")
        ax.set_yticks(range(len(CLAIM_TYPES)))
        ax.set_yticklabels(CLAIM_TYPES)
        for i, row in enumerate(matrix):
            for j, v in enumerate(row):
                if not math.isnan(v):
                    ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                            color="white" if v < 0.5 else "black", fontsize=8)
        ax.set_title("claim_type × support_class share (pooled)")
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="row share")
        return _save(fig, fig_dir / "class_marker_heatmap_all.png")
    else:
        # one heatmap panel per scope value
        groups: dict[str, list[dict]] = defaultdict(list)
        scope_col = {"model": "model", "section": "section"}.get(scope, scope)
        for r in rows:
            groups[r[scope_col]].append(r)
        keys = sorted(groups)
        n = len(keys)
        cols = min(3, n)
        rows_n = (n + cols - 1) // cols
        fig, axes = plt.subplots(rows_n, cols, figsize=(5 * cols, 4 * rows_n), squeeze=False)
        for idx, key in enumerate(keys):
            ax = axes[idx // cols][idx % cols]
            sub = {r["claim_type"]: r for r in groups[key]}
            mat = [[_f(sub.get(ct, {}).get(s, "")) for s in SUPPORT_CLASSES] for ct in CLAIM_TYPES]
            im = ax.imshow(mat, cmap="viridis", aspect="auto", vmin=0, vmax=1)
            ax.set_xticks(range(len(SUPPORT_CLASSES)))
            ax.set_xticklabels(SUPPORT_CLASSES, rotation=30, ha="right", fontsize=7)
            ax.set_yticks(range(len(CLAIM_TYPES)))
            ax.set_yticklabels(CLAIM_TYPES, fontsize=7)
            ax.set_title(f"{scope}={key}", fontsize=10)
        for idx in range(n, rows_n * cols):
            axes[idx // cols][idx % cols].axis("off")
        fig.suptitle(f"claim_type × support_class share by {scope}")
        return _save(fig, fig_dir / f"class_marker_heatmap_{scope}.png")


# ---------------------------------------------------------------------------
# 2.B batch stability plots
# ---------------------------------------------------------------------------

def plot_prompt_scatter_with_errorbars(csv_dir: Path, fig_dir: Path) -> Path:
    rows = _read_csv(csv_dir / "batch_stability.csv")
    models = sorted({r["model"] for r in rows})
    sections = sorted({r["section"] for r in rows})
    sec_color = {s: plt.cm.tab10(i % 10) for i, s in enumerate(sections)}
    markers = ["o", "s", "^", "D", "v", "P", "X"]
    model_marker = {m: markers[i % len(markers)] for i, m in enumerate(models)}

    fig, ax = plt.subplots(figsize=(10, 6))
    for r in rows:
        x = _f(r["n_claims_mean"])
        y = _f(r["verified_mean"])
        yerr = _f(r["verified_stdev"])
        ax.errorbar(x, y, yerr=yerr, fmt=model_marker[r["model"]],
                    color=sec_color[r["section"]], alpha=0.7, markersize=5,
                    capsize=2, linewidth=0.8)
    # legends: section colors + model markers
    sec_handles = [plt.Line2D([0], [0], marker="o", color="w",
                              markerfacecolor=sec_color[s], markersize=8, label=s)
                   for s in sections]
    mdl_handles = [plt.Line2D([0], [0], marker=model_marker[m], color="black",
                              linestyle="", markersize=7, label=m)
                   for m in models]
    leg1 = ax.legend(handles=sec_handles, title="section", loc="upper left", fontsize=7)
    ax.add_artist(leg1)
    ax.legend(handles=mdl_handles, title="model", loc="lower right", fontsize=7)
    ax.set_xlabel("Mean N_claims per batch")
    ax.set_ylabel("Mean verified_share (error bars = stdev across batches)")
    ax.set_title("Per-prompt verified-share vs claim count, by model/section")
    ax.set_ylim(0, 1)
    return _save(fig, fig_dir / "prompt_scatter_with_errorbars.png")


def plot_saturation_curves(csv_dir: Path, fig_dir: Path) -> Path:
    rows = _read_csv(csv_dir / "coverage_saturation.csv")
    by_section: dict[str, list[dict]] = defaultdict(list)
    # we don't have section in saturation csv — derive from prompt_difficulty
    diff = {r["question_id"]: r["section"] for r in _read_csv(csv_dir / "prompt_difficulty.csv")}
    for r in rows:
        by_section[diff.get(r["question_id"], "?")].append(r)
    sections = sorted(by_section)
    n = len(sections)
    cols = 3
    rows_n = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows_n, cols, figsize=(5 * cols, 3.5 * rows_n), squeeze=False, sharey=True)
    model_color = {}
    for idx, sec in enumerate(sections):
        ax = axes[idx // cols][idx % cols]
        for r in by_section[sec]:
            xs = [i for i in range(1, 6) if r.get(f"cum_after_batch{i}", "") not in ("", None)]
            ys = [_f(r[f"cum_after_batch{i}"]) for i in xs]
            m = r["model"]
            if m not in model_color:
                model_color[m] = plt.cm.tab10(len(model_color) % 10)
            ax.plot(xs, ys, "-o", color=model_color[m], alpha=0.4, markersize=3, linewidth=0.7)
        ax.set_title(f"section {sec}")
        ax.set_xlabel("batch index")
        ax.set_xticks(range(1, 6))
    for idx in range(n, rows_n * cols):
        axes[idx // cols][idx % cols].axis("off")
    handles = [plt.Line2D([0], [0], color=c, marker="o", label=m) for m, c in model_color.items()]
    fig.legend(handles=handles, loc="lower center", ncol=len(model_color), bbox_to_anchor=(0.5, -0.02))
    fig.suptitle("Cumulative unique canonical_ids vs batch index (saturation curves)")
    return _save(fig, fig_dir / "saturation_curves.png")


def plot_best_vs_worst_gap(csv_dir: Path, fig_dir: Path) -> Path:
    rows = _read_csv(csv_dir / "best_vs_worst_batch.csv")
    by_model: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        by_model[r["model"]].append(_f(r["gap"]))
    models = sorted(by_model)
    fig, ax = plt.subplots(figsize=(8, 5))
    for i, m in enumerate(models):
        vals = [v for v in by_model[m] if not math.isnan(v)]
        ax.hist(vals, bins=20, alpha=0.5, label=m)
    ax.set_xlabel("Best - worst verified_share across the 5 batches")
    ax.set_ylabel("Number of prompts")
    ax.set_title("Best-vs-worst-batch gap per model")
    ax.legend()
    return _save(fig, fig_dir / "best_vs_worst_gap.png")


def plot_pairwise_jaccard_heatmap(csv_dir: Path, fig_dir: Path) -> Path:
    rows = _read_csv(csv_dir / "batch_agreement_canonical.csv")
    by_model: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_model[r["model"]].append(r)
    models = sorted(by_model)
    n = len(models)
    cols = min(2, n)
    rows_n = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows_n, cols, figsize=(7 * cols, 4 * rows_n), squeeze=False)
    for idx, m in enumerate(models):
        ax = axes[idx // cols][idx % cols]
        items = sorted(by_model[m], key=lambda r: _f(r["jaccard_mean"]))
        prompts = [r["question_id"] for r in items]
        vals = [[_f(r["jaccard_mean"])] for r in items]
        im = ax.imshow(vals, cmap="RdYlGn", aspect="auto", vmin=0, vmax=1)
        ax.set_yticks(range(len(prompts)))
        ax.set_yticklabels(prompts, fontsize=6)
        ax.set_xticks([0])
        ax.set_xticklabels(["mean Jaccard"])
        ax.set_title(m)
        fig.colorbar(im, ax=ax, fraction=0.05, pad=0.04)
    for idx in range(n, rows_n * cols):
        axes[idx // cols][idx % cols].axis("off")
    fig.suptitle("Per-prompt mean pairwise Jaccard of canonical_ids across the 5 batches")
    return _save(fig, fig_dir / "pairwise_jaccard_heatmap.png")


def plot_pairwise_jaccard_by_model_major_section_heatmap(csv_dir: Path, fig_dir: Path) -> Path:
    rows = _read_csv(csv_dir / "pairwise_jaccard_by_model_major_section.csv")
    if not rows:
        raise ValueError("pairwise_jaccard_by_model_major_section.csv is missing or empty")

    models = sorted({row["model"] for row in rows})
    major_sections = sorted({row["major_section"] for row in rows}, key=_section_sort_key)
    matrix = np.full((len(major_sections), len(models)), np.nan)
    for row in rows:
        y = major_sections.index(row["major_section"])
        x = models.index(row["model"])
        matrix[y, x] = _f(row["jaccard_mean"])

    fig, ax = plt.subplots(figsize=(1.7 * len(models) + 2.5, 1.0 * len(major_sections) + 2.5))
    im = ax.imshow(matrix, aspect="auto", cmap="viridis", vmin=0, vmax=1)
    ax.set_xticks(range(len(models)))
    ax.set_xticklabels(models, rotation=30, ha="right")
    ax.set_yticks(range(len(major_sections)))
    ax.set_yticklabels([f"section {section}" for section in major_sections])
    ax.set_xlabel("Model")
    ax.set_ylabel("Major section")
    ax.set_title("Mean pairwise Jaccard of canonical IDs")
    for y in range(len(major_sections)):
        for x in range(len(models)):
            value = matrix[y, x]
            if math.isnan(value):
                continue
            text_color = "white" if value < 0.55 else "black"
            ax.text(x, y, f"{value:.2f}", ha="center", va="center", fontsize=8, color=text_color)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="mean Jaccard")
    return _save(fig, fig_dir / "pairwise_jaccard_by_model_major_section_heatmap.png")


# ---------------------------------------------------------------------------
# 2.C cross-model & difficulty
# ---------------------------------------------------------------------------

def plot_prompt_difficulty(csv_dir: Path, fig_dir: Path) -> Path:
    rows = _read_csv(csv_dir / "prompt_difficulty.csv")
    metric_field = "verified_ex_domain_mean" if rows and "verified_ex_domain_mean" in rows[0] else "verified_mean"
    rows.sort(key=lambda r: _f(r.get(metric_field, r.get("verified_mean", ""))))
    fig, ax = plt.subplots(figsize=(12, 7))
    major_sections = sorted({_major_section(r["section"]) for r in rows}, key=_section_sort_key)
    sec_color = {section: plt.cm.tab10(i % 10) for i, section in enumerate(major_sections)}
    xs = list(range(len(rows)))
    ys = [_f(r.get(metric_field, r.get("verified_mean", ""))) for r in rows]
    colors = [sec_color[_major_section(r["section"])] for r in rows]
    ax.bar(xs, ys, color=colors)
    rank_labels = [str(int(r.get("difficulty_rank") or (index + 1))) for index, r in enumerate(rows)]
    tick_step = max(1, len(xs) // 18)
    tick_positions = xs[::tick_step]
    tick_labels = rank_labels[::tick_step]
    if xs and tick_positions[-1] != xs[-1]:
        tick_positions.append(xs[-1])
        tick_labels.append(rank_labels[-1])
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, rotation=0, fontsize=7)
    ax.set_xlabel("Difficulty rank")
    ax.set_ylabel("Mean verified share excluding filler & domain claims")
    ax.set_title("Prompt-difficulty ranking (lowest verified share excl. filler/domain = hardest)")
    handles = [plt.Rectangle((0, 0), 1, 1, color=sec_color[section], label=section) for section in major_sections]
    ax.legend(handles=handles, title="major section", fontsize=7)
    return _save(fig, fig_dir / "prompt_difficulty.png")


def plot_cross_model_rank_correlation(csv_dir: Path, fig_dir: Path) -> Path:
    rows = _read_csv(csv_dir / "cross_model_rank_correlation.csv")
    models = sorted({r["model_a"] for r in rows} | {r["model_b"] for r in rows})
    idx = {m: i for i, m in enumerate(models)}
    n = len(models)
    mat = [[1.0] * n for _ in range(n)]
    for r in rows:
        i, j = idx[r["model_a"]], idx[r["model_b"]]
        v = _f(r["spearman"])
        mat[i][j] = mat[j][i] = v
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(mat, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(n)); ax.set_xticklabels(models, rotation=30, ha="right")
    ax.set_yticks(range(n)); ax.set_yticklabels(models)
    for i in range(n):
        for j in range(n):
            ax.text(j, i, f"{mat[i][j]:.2f}", ha="center", va="center", fontsize=9,
                    color="white" if abs(mat[i][j]) > 0.5 else "black")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Spearman ρ")
    ax.set_title("Cross-model Spearman ρ on per-prompt verified_share")
    return _save(fig, fig_dir / "cross_model_rank_correlation.png")


# ---------------------------------------------------------------------------
# 2.D / 2.E / 2.F simple bars
# ---------------------------------------------------------------------------

def plot_eval_mode_buckets(csv_dir: Path, fig_dir: Path) -> Path:
    rows = _read_csv(csv_dir / "eval_mode_profile.csv")
    modes = [r["eval_mode"] for r in rows]
    fig, ax = plt.subplots(figsize=(10, 5))
    bottom = [0.0] * len(modes)
    for b in NON_FILLER_BUCKETS:
        vals = [_f(r[f"bucket_{b}_share"]) for r in rows]
        ax.bar(modes, vals, bottom=bottom, color=BUCKET_COLORS[b], label=b)
        bottom = [a + v for a, v in zip(bottom, vals)]
    ax.set_ylim(0, 1)
    ax.set_ylabel("Share of non-filler claims")
    ax.set_title("Bucket shares by eval_mode (pooled across models)")
    ax.legend()
    ax.tick_params(axis="x", rotation=30)
    return _save(fig, fig_dir / "eval_mode_buckets.png")


def plot_eval_mode_claim_type_composition(csv_dir: Path, fig_dir: Path) -> Path:
    rows = _read_csv(csv_dir / "eval_mode_profile.csv")
    modes = [r["eval_mode"] for r in rows]
    fig, ax = plt.subplots(figsize=(11, 6))
    bottom = [0.0] * len(modes)
    cmap = plt.cm.tab20
    for i, ct in enumerate(CLAIM_TYPES):
        vals = [_f(r[f"ct_{ct}_share"]) for r in rows]
        ax.bar(modes, vals, bottom=bottom, color=cmap(i % 20), label=ct)
        bottom = [a + v for a, v in zip(bottom, vals)]
    ax.set_ylim(0, 1)
    ax.set_ylabel("Share of all claims")
    ax.set_title("Claim-type composition per eval_mode")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=7)
    ax.tick_params(axis="x", rotation=30)
    return _save(fig, fig_dir / "eval_mode_claim_type_composition.png")


def plot_model_prompt_claim_type_heatmap(csv_dir: Path, fig_dir: Path) -> Path:
    rows = _read_csv(csv_dir / "support_by_claim_type_model_prompt.csv")
    if not rows:
        raise ValueError("support_by_claim_type_model_prompt.csv is missing or empty")

    models = sorted({row["model"] for row in rows})
    prompts = sorted({row["question_id"] for row in rows}, key=_qid_sort_key)
    claim_types = list(CLAIM_TYPES)

    totals: dict[tuple[str, str], int] = defaultdict(int)
    shares: dict[tuple[str, str, str], float] = {}
    for row in rows:
        key = (row["model"], row["question_id"])
        totals[key] += int(row.get("row_total", 0) or 0)
    for row in rows:
        key = (row["model"], row["question_id"])
        total = totals.get(key, 0)
        shares[(row["model"], row["question_id"], row["claim_type"])] = (int(row.get("row_total", 0) or 0) / total) if total else float("nan")

    n = len(models)
    cols = 2 if n > 1 else 1
    rows_n = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows_n, cols, figsize=(7.8 * cols, 2.8 + 1.3 * rows_n), squeeze=False, sharey=True)
    vmax = max(
        (
            value
            for value in shares.values()
            if not math.isnan(value)
        ),
        default=1.0,
    )
    vmax = max(vmax, 0.25)
    im = None
    for idx, model in enumerate(models):
        ax = axes[idx // cols][idx % cols]
        matrix = [
            [shares.get((model, prompt, claim_type), float("nan")) for prompt in prompts]
            for claim_type in claim_types
        ]
        im = ax.imshow(matrix, cmap="YlGnBu", aspect="auto", vmin=0, vmax=vmax)
        step = max(1, len(prompts) // 16)
        tick_idx = list(range(0, len(prompts), step))
        ax.set_xticks(tick_idx)
        ax.set_xticklabels([prompts[i] for i in tick_idx], rotation=60, ha="right", fontsize=6)
        ax.set_yticks(range(len(claim_types)))
        labels = ax.set_yticklabels(claim_types, fontsize=7)
        for label, claim_type in zip(labels, claim_types):
            label.set_color(CLAIM_TYPE_COLORS[claim_type])
        ax.set_title(model)
        ax.set_xlabel("prompt")
    for idx in range(n, rows_n * cols):
        axes[idx // cols][idx % cols].axis("off")
    axes[0][0].set_ylabel("claim_type")
    if im is not None:
        fig.colorbar(im, ax=axes.ravel().tolist(), fraction=0.015, pad=0.02, label="share of all claims")
    fig.suptitle("Model × prompt × claim_type share diagram (4-model view)")
    return _save(fig, fig_dir / "model_prompt_claim_type_heatmap.png")


def plot_position_effects(csv_dir: Path, fig_dir: Path) -> Path:
    rows = _read_csv(csv_dir / "position_effects.csv")
    models = sorted({r["model"] for r in rows})
    fig, ax = plt.subplots(figsize=(9, 5))
    width = 0.25
    positions = ("first", "middle", "last")
    for i, pos in enumerate(positions):
        vals = [_f(next((r["verified_share"] for r in rows if r["model"] == m and r["position"] == pos), ""))
                for m in models]
        ax.bar([j + i * width for j in range(len(models))], vals, width=width, label=pos)
    ax.set_xticks([j + width for j in range(len(models))])
    ax.set_xticklabels(models)
    ax.set_ylim(0, 1)
    ax.set_ylabel("verified_share")
    ax.set_title("Verified share by paragraph position, per model")
    ax.legend()
    return _save(fig, fig_dir / "position_effects.png")


def plot_verbosity(csv_dir: Path, fig_dir: Path) -> Path:
    rows = _read_csv(csv_dir / "verbosity_vs_verified.csv")
    bins = sorted({r["text_len_bin"] for r in rows},
                  key=lambda b: int(b.split("-")[0]))
    models = sorted({r["model"] for r in rows})
    fig, ax = plt.subplots(figsize=(9, 5))
    for m in models:
        ys = []
        for b in bins:
            v = next((_f(r["verified_share"]) for r in rows if r["model"] == m and r["text_len_bin"] == b), float("nan"))
            ys.append(v)
        ax.plot(bins, ys, "-o", label=m)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Claim text length (chars)")
    ax.set_ylabel("verified_share")
    ax.set_title("Verified share vs claim text length, per model")
    ax.legend()
    return _save(fig, fig_dir / "verbosity_vs_verified.png")


def plot_top_canonical_ids(csv_dir: Path, fig_dir: Path) -> Path:
    rows = _read_csv(csv_dir / "canonical_id_frequency_top.csv")[:20]
    rows.reverse()
    labels = [r["canonical_id"] for r in rows]
    vals = [int(r["n_batches_cited"]) for r in rows]
    fig, ax = plt.subplots(figsize=(8, 7))
    ax.barh(labels, vals)
    ax.set_xlabel("n_batches citing this canonical_id")
    ax.set_title("Top-20 most-cited canonical_ids (pooled)")
    return _save(fig, fig_dir / "top_canonical_ids.png")


def plot_tool_usage(csv_dir: Path, fig_dir: Path) -> Path:
    rows = [row for row in _read_csv(csv_dir / "tool_usage_distribution.csv") if not row["tool"].startswith("0_")]
    by_model_tool: dict[tuple, int] = defaultdict(int)
    for r in rows:
        by_model_tool[(r["model"], r["tool"])] += int(r["n_invocations"])
    models = sorted({m for m, _ in by_model_tool})
    tools = sorted(
        {t for _, t in by_model_tool},
        key=lambda t: (-sum(by_model_tool[(m, t)] for m in models), t),
    )
    fig, ax = plt.subplots(figsize=(max(10, 0.75 * len(tools) + 4), 6))
    width = 0.8 / max(1, len(models))
    for i, m in enumerate(models):
        vals = [by_model_tool.get((m, t), 0) for t in tools]
        ax.bar([j + i * width for j in range(len(tools))], vals, width=width, label=m)
    ax.set_xticks([j + width * (len(models) - 1) / 2 for j in range(len(tools))])
    ax.set_xticklabels(tools, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("n_invocations (across all batches)")
    ax.set_title("Tool invocations per model (excluding 0_* planning tools)")
    ax.legend()
    return _save(fig, fig_dir / "tool_usage.png")


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def render_all(csv_dir: Path, fig_dir: Path) -> dict[str, Path]:
    fig_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    plotters = [
        ("bucket_share_by_model", plot_bucket_share_by_model),
        ("bucket_share_by_section_facet", plot_bucket_share_by_section_facet),
        ("bucket_share_by_major_section_facet", plot_bucket_share_by_major_section_facet),
        ("bucket_share_by_section_facet_detailed", plot_bucket_share_by_section_facet_detailed),
        ("bucket_share_by_prompt_facet_detailed", plot_bucket_share_by_prompt_facet_detailed),
        ("claim_type_share_by_major_section_facet", plot_claim_type_share_by_major_section_facet),
        ("claim_type_share_by_major_section_collage", plot_claim_type_share_by_major_section_collage),
        ("verified_share_by_claim_type_major_section_collage", plot_verified_share_by_claim_type_major_section_collage),
        ("verified_share_by_claim_type_model_major_section_heatmap", plot_verified_share_by_claim_type_model_major_section_heatmap),
        ("class_marker_heatmap_all", lambda c, f: plot_class_marker_heatmap(c, f, "all")),
        ("class_marker_heatmap_model", lambda c, f: plot_class_marker_heatmap(c, f, "model")),
        ("prompt_scatter_with_errorbars", plot_prompt_scatter_with_errorbars),
        ("saturation_curves", plot_saturation_curves),
        ("best_vs_worst_gap", plot_best_vs_worst_gap),
        ("pairwise_jaccard_heatmap", plot_pairwise_jaccard_heatmap),
        ("pairwise_jaccard_by_model_major_section_heatmap", plot_pairwise_jaccard_by_model_major_section_heatmap),
        ("prompt_difficulty", plot_prompt_difficulty),
        ("cross_model_rank_correlation", plot_cross_model_rank_correlation),
        ("eval_mode_buckets", plot_eval_mode_buckets),
        ("eval_mode_claim_type_composition", plot_eval_mode_claim_type_composition),
        ("model_prompt_claim_type_heatmap", plot_model_prompt_claim_type_heatmap),
        ("position_effects", plot_position_effects),
        ("verbosity_vs_verified", plot_verbosity),
        ("top_canonical_ids", plot_top_canonical_ids),
        ("tool_usage", plot_tool_usage),
    ]
    for name, fn in plotters:
        try:
            written[name] = fn(csv_dir, fig_dir)
        except Exception as exc:  # noqa: BLE001
            print(f"  [plot] {name} failed: {exc}")
    return written


__all__ = ["render_all"]
