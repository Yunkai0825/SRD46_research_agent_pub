"""Plot generation for the tool statistics bundle."""
from __future__ import annotations

import csv
import textwrap
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

TOP_N = 10
TOP_CHAIN_N = 15


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _f(value: str | None) -> float:
    try:
        return float(value or "nan")
    except ValueError:
        return float("nan")


def _top_rows(rows: list[dict[str, str]], *, sort_key: str, limit: int = TOP_N) -> list[dict[str, str]]:
    return sorted(rows, key=lambda row: _f(row.get(sort_key)), reverse=True)[:limit]


def _wrap_label(text: str, width: int = 42) -> str:
    return textwrap.fill(text, width=width, break_long_words=False, break_on_hyphens=False)


def _section_sort_key(section: str) -> tuple[tuple[int, object], ...]:
    key: list[tuple[int, object]] = []
    for token in (section or "").split("."):
        if token.isdigit():
            key.append((0, int(token)))
        else:
            key.append((1, token))
    return tuple(key)


def _save(fig: plt.Figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return path


def _plot_overall_usage_latency(rows: list[dict[str, str]], fig_dir: Path) -> Path | None:
    if not rows:
        return None
    usage_rows = list(reversed(_top_rows(rows, sort_key="n_calls")))
    latency_rows = list(reversed(_top_rows(rows, sort_key="duration_mean_sec")))
    fig, axes = plt.subplots(1, 2, figsize=(15, 7))

    axes[0].barh([row["tool_name"] for row in usage_rows], [_f(row["n_calls"]) for row in usage_rows], color="#2c7fb8")
    axes[0].set_title("Top 10 tools by call count")
    axes[0].set_xlabel("Calls")

    axes[1].barh([row["tool_name"] for row in latency_rows], [_f(row["duration_mean_sec"]) for row in latency_rows], color="#d95f0e")
    axes[1].set_title("Top 10 tools by mean step-header duration")
    axes[1].set_xlabel("Mean seconds")

    return _save(fig, fig_dir / "overall_usage_latency_top10.png")


def _plot_model_preferences(rows: list[dict[str, str]], fig_dir: Path) -> Path | None:
    if not rows:
        return None
    totals: dict[str, float] = defaultdict(float)
    models = sorted({row["model"] for row in rows})
    for row in rows:
        totals[row["tool_name"]] += _f(row.get("n_calls"))
    tools = [name for name, _ in sorted(totals.items(), key=lambda item: item[1], reverse=True)[:TOP_N]]
    if not tools or not models:
        return None

    data = {model: [] for model in models}
    row_by_key = {(row["model"], row["tool_name"]): row for row in rows}
    for model in models:
        for tool in tools:
            data[model].append(_f((row_by_key.get((model, tool)) or {}).get("call_share")) * 100)

    fig, ax = plt.subplots(figsize=(14, 7))
    x = np.arange(len(tools))
    width = 0.18 if len(models) >= 4 else 0.22
    palette = ["#1b9e77", "#d95f02", "#7570b3", "#e7298a", "#66a61e"]
    for index, model in enumerate(models):
        offset = (index - (len(models) - 1) / 2) * width
        ax.bar(x + offset, data[model], width=width, label=model, color=palette[index % len(palette)])

    ax.set_xticks(x)
    ax.set_xticklabels(tools, rotation=30, ha="right")
    ax.set_ylabel("Call share (%)")
    ax.set_title("Top 10 tool preferences by model")
    ax.legend()
    return _save(fig, fig_dir / "tool_preferences_by_model_top10.png")


def _plot_tool_duration_by_model(rows: list[dict[str, str]], fig_dir: Path) -> Path | None:
    if not rows:
        return None
    models = sorted({row["model"] for row in rows})
    mean_by_tool: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        value = _f(row.get("duration_mean_sec"))
        if not np.isnan(value):
            mean_by_tool[row["tool_name"]].append(value)
    tools = [
        name
        for name, values in sorted(
            mean_by_tool.items(),
            key=lambda item: (-sum(item[1]) / len(item[1]), item[0]),
        )
        if values
    ]
    if not tools or not models:
        return None

    row_by_key = {(row["model"], row["tool_name"]): row for row in rows}
    fig, ax = plt.subplots(figsize=(max(12, 0.8 * len(tools) + 4), 7))
    x = np.arange(len(tools))
    width = min(0.8 / max(1, len(models)), 0.22)
    palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]

    for index, model in enumerate(models):
        values = [_f((row_by_key.get((model, tool)) or {}).get("duration_mean_sec")) for tool in tools]
        values = [0.0 if np.isnan(value) else value for value in values]
        offset = (index - (len(models) - 1) / 2) * width
        ax.bar(x + offset, values, width=width, label=model, color=palette[index % len(palette)])

    ax.set_xticks(x)
    ax.set_xticklabels(tools, rotation=35, ha="right")
    ax.set_ylabel("Mean successful step-header seconds per call")
    ax.set_title("Mean step-header time by model (failed calls excluded, 0_* tools hidden)")
    ax.legend(ncol=2 if len(models) > 3 else 1)
    return _save(fig, fig_dir / "tool_duration_by_model.png")


def _plot_tool_wall_time_by_model(rows: list[dict[str, str]], fig_dir: Path) -> Path | None:
    if not rows:
        return None
    models = sorted({row["model"] for row in rows})
    mean_by_tool: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        value = _f(row.get("wall_mean_sec"))
        if not np.isnan(value):
            mean_by_tool[row["tool_name"]].append(value)
    tools = [
        name
        for name, values in sorted(
            mean_by_tool.items(),
            key=lambda item: (-sum(item[1]) / len(item[1]), item[0]),
        )
        if values
    ]
    if not tools or not models:
        return None

    row_by_key = {(row["model"], row["tool_name"]): row for row in rows}
    fig, ax = plt.subplots(figsize=(max(12, 0.8 * len(tools) + 4), 7))
    x = np.arange(len(tools))
    width = min(0.8 / max(1, len(models)), 0.22)
    palette = ["#264653", "#2a9d8f", "#e9c46a", "#f4a261", "#e76f51"]

    for index, model in enumerate(models):
        values = [_f((row_by_key.get((model, tool)) or {}).get("wall_mean_sec")) for tool in tools]
        values = [0.0 if np.isnan(value) else value for value in values]
        offset = (index - (len(models) - 1) / 2) * width
        ax.bar(x + offset, values, width=width, label=model, color=palette[index % len(palette)])

    ax.set_xticks(x)
    ax.set_xticklabels(tools, rotation=35, ha="right")
    ax.set_ylabel("Mean successful wall seconds per timed call")
    ax.set_title("Mean deduced tool-call wall time by model (excludes final pre-answer group)")
    ax.legend(ncol=2 if len(models) > 3 else 1)
    return _save(fig, fig_dir / "tool_wall_time_by_model.png")


def _plot_tool_argo_duration_by_model(rows: list[dict[str, str]], fig_dir: Path) -> Path | None:
    if not rows:
        return None
    models = sorted({row["model"] for row in rows})
    mean_by_tool: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        value = _f(row.get("argo_duration_mean_sec"))
        if not np.isnan(value):
            mean_by_tool[row["tool_name"]].append(value)
    tools = [
        name
        for name, values in sorted(
            mean_by_tool.items(),
            key=lambda item: (-sum(item[1]) / len(item[1]), item[0]),
        )
        if values
    ]
    if not tools or not models:
        return None

    row_by_key = {(row["model"], row["tool_name"]): row for row in rows}
    fig, ax = plt.subplots(figsize=(max(12, 0.8 * len(tools) + 4), 7))
    x = np.arange(len(tools))
    width = min(0.8 / max(1, len(models)), 0.22)
    palette = ["#003f5c", "#7a5195", "#ef5675", "#ffa600", "#2f4b7c"]

    for index, model in enumerate(models):
        values = [_f((row_by_key.get((model, tool)) or {}).get("argo_duration_mean_sec")) for tool in tools]
        values = [0.0 if np.isnan(value) else value for value in values]
        offset = (index - (len(models) - 1) / 2) * width
        ax.bar(x + offset, values, width=width, label=model, color=palette[index % len(palette)])

    ax.set_xticks(x)
    ax.set_xticklabels(tools, rotation=35, ha="right")
    ax.set_ylabel("Mean Argo analysis seconds per timed call")
    ax.set_title("Mean Argo analysis time by model (recorded _meta timing, including planning tools)")
    ax.legend(ncol=2 if len(models) > 3 else 1)
    return _save(fig, fig_dir / "tool_argo_duration_by_model.png")


def _plot_compactor_context_by_model(rows: list[dict[str, str]], fig_dir: Path) -> Path | None:
    rows = [row for row in rows if row.get("model")]
    if not rows:
        return None
    rows = sorted(rows, key=lambda row: row["model"])
    models = [row["model"] for row in rows]
    context_chars_before = [0.0 if np.isnan(_f(row.get("selected_context_chars_mean"))) else _f(row.get("selected_context_chars_mean")) for row in rows]
    context_chars_after = [0.0 if np.isnan(_f(row.get("selected_next_context_chars_mean"))) else _f(row.get("selected_next_context_chars_mean")) for row in rows]
    context_turns = [0.0 if np.isnan(_f(row.get("context_turns_mean"))) else _f(row.get("context_turns_mean")) for row in rows]
    next_context_coverage = [0.0 if np.isnan(_f(row.get("selected_next_context_coverage_rate"))) else _f(row.get("selected_next_context_coverage_rate")) * 100 for row in rows]

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    x = np.arange(len(models))
    width = 0.35
    axes[0].bar(x - width / 2, context_chars_before, width=width, color="#3a86ff", label="before selected compaction")
    axes[0].bar(x + width / 2, context_chars_after, width=width, color="#4cc9f0", label="next observed window after (excl. skipped/failed)")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(models, rotation=25)
    axes[0].set_title("Compactor context length by model")
    axes[0].set_ylabel("Mean chars around compaction round")
    axes[0].tick_params(axis="x", rotation=25)
    axes[0].legend(fontsize=8)
    max_chars = max(context_chars_before + context_chars_after + [1.0])
    for index, value in enumerate(next_context_coverage):
        axes[0].text(x[index] + width / 2, context_chars_after[index] + max_chars * 0.02, f"{value:.0f}%", ha="center", va="bottom", fontsize=8)

    axes[1].bar(models, context_turns, color="#8338ec")
    axes[1].set_title("Compactor context turns by model")
    axes[1].set_ylabel("Mean turns at compression round")
    axes[1].tick_params(axis="x", rotation=25)
    return _save(fig, fig_dir / "compactor_context_by_model.png")


def _plot_compactor_selection_by_model(rows: list[dict[str, str]], fig_dir: Path) -> Path | None:
    rows = [row for row in rows if row.get("model")]
    if not rows:
        return None
    rows = sorted(rows, key=lambda row: row["model"])
    models = [row["model"] for row in rows]
    x = np.arange(len(models))
    width = 0.35

    selected_candidate_mean = [0.0 if np.isnan(_f(row.get("selected_candidate_mean"))) else _f(row.get("selected_candidate_mean")) for row in rows]
    parallel_task_mean = [0.0 if np.isnan(_f(row.get("parallel_task_mean"))) else _f(row.get("parallel_task_mean")) for row in rows]
    selected_round_rate = [0.0 if np.isnan(_f(row.get("selected_round_rate"))) else _f(row.get("selected_round_rate")) * 100 for row in rows]
    none_round_rate = [0.0 if np.isnan(_f(row.get("none_round_rate"))) else _f(row.get("none_round_rate")) * 100 for row in rows]

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    axes[0].bar(x - width / 2, selected_candidate_mean, width=width, label="selected candidates", color="#2a9d8f")
    axes[0].bar(x + width / 2, parallel_task_mean, width=width, label="parallel tasks", color="#e9c46a")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(models, rotation=25)
    axes[0].set_ylabel("Mean count per selection round")
    axes[0].set_title("Compactor selection load by model")
    axes[0].legend()

    axes[1].bar(x - width / 2, selected_round_rate, width=width, label="selected", color="#264653")
    axes[1].bar(x + width / 2, none_round_rate, width=width, label="none", color="#e76f51")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(models, rotation=25)
    axes[1].set_ylabel("Rate of selection rounds (%)")
    axes[1].set_title("Compactor selection outcomes by model")
    axes[1].legend()
    return _save(fig, fig_dir / "compactor_selection_by_model.png")


def _plot_compactor_retry_by_model(rows: list[dict[str, str]], fig_dir: Path) -> Path | None:
    rows = [row for row in rows if row.get("model")]
    if not rows:
        return None
    rows = sorted(rows, key=lambda row: row["model"])
    models = [row["model"] for row in rows]
    retry_totals = [0.0 if np.isnan(_f(row.get("retry_events_total"))) else _f(row.get("retry_events_total")) for row in rows]
    accepted_totals = [0.0 if np.isnan(_f(row.get("accepted_events_total"))) else _f(row.get("accepted_events_total")) for row in rows]
    skipped_totals = [0.0 if np.isnan(_f(row.get("skipped_events_total"))) else _f(row.get("skipped_events_total")) for row in rows]
    exhausted_totals = [0.0 if np.isnan(_f(row.get("retry_exhausted_events_total"))) else _f(row.get("retry_exhausted_events_total")) for row in rows]

    x = np.arange(len(models))
    width = 0.18
    fig, ax = plt.subplots(figsize=(12, 5.5))
    ax.bar(x - 1.5 * width, retry_totals, width=width, label="retry", color="#ef476f")
    ax.bar(x - 0.5 * width, accepted_totals, width=width, label="accepted", color="#06d6a0")
    ax.bar(x + 0.5 * width, skipped_totals, width=width, label="skipped", color="#ffd166")
    ax.bar(x + 1.5 * width, exhausted_totals, width=width, label="retry exhausted", color="#6d597a")
    ax.set_xticks(x)
    ax.set_xticklabels(models, rotation=25)
    ax.set_ylabel("Event count")
    ax.set_title("Compactor validator and retry activity by model")
    ax.legend(ncol=2)
    return _save(fig, fig_dir / "compactor_retry_by_model.png")


def _plot_compactor_trigger_summary_by_model(rows: list[dict[str, str]], fig_dir: Path) -> Path | None:
    rows = [row for row in rows if row.get("model")]
    if not rows:
        return None
    rows = sorted(rows, key=lambda row: row["model"])
    models = [row["model"] for row in rows]
    x = np.arange(len(models))
    width = 0.2

    triggered = [0.0 if np.isnan(_f(row.get("triggered_rounds"))) else _f(row.get("triggered_rounds")) for row in rows]
    triggered_success = [0.0 if np.isnan(_f(row.get("normal_run_triggered_rounds"))) else _f(row.get("normal_run_triggered_rounds")) for row in rows]
    none = [0.0 if np.isnan(_f(row.get("none_rounds"))) else _f(row.get("none_rounds")) for row in rows]
    l0_no_match = [0.0 if np.isnan(_f(row.get("l0_no_match_rounds"))) else _f(row.get("l0_no_match_rounds")) for row in rows]
    trigger_rates = [0.0 if np.isnan(_f(row.get("run_trigger_rate"))) else _f(row.get("run_trigger_rate")) * 100 for row in rows]
    runs_with_triggered = [0.0 if np.isnan(_f(row.get("runs_with_triggered_compaction"))) else _f(row.get("runs_with_triggered_compaction")) for row in rows]
    triggered_success_run_rates = [0.0 if np.isnan(_f(row.get("triggered_success_run_rate"))) else _f(row.get("triggered_success_run_rate")) * 100 for row in rows]
    runs_with_triggered_success = [0.0 if np.isnan(_f(row.get("runs_with_triggered_success"))) else _f(row.get("runs_with_triggered_success")) for row in rows]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    axes[0].bar(x - 1.5 * width, triggered, width=width, label="triggered", color="#1982c4")
    axes[0].bar(x - 0.5 * width, triggered_success, width=width, label="triggered-success", color="#00a6a6")
    axes[0].bar(x + 0.5 * width, none, width=width, label="none", color="#ff924c")
    axes[0].bar(x + 1.5 * width, l0_no_match, width=width, label="l0 no-match", color="#6a4c93")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(models, rotation=25)
    axes[0].set_ylabel("Turn count")
    axes[0].set_title("Compactor turn types by model")
    axes[0].legend(ncol=2)

    run_width = 0.34
    axes[1].bar(x - run_width / 2, runs_with_triggered, width=run_width, color="#2a9d8f", label=">=1 triggered turn")
    axes[1].bar(x + run_width / 2, runs_with_triggered_success, width=run_width, color="#1f7a8c", label=">=1 triggered-success turn")
    max_value = max(runs_with_triggered + runs_with_triggered_success + [1.0])
    for index, value in enumerate(runs_with_triggered):
        axes[1].text(x[index] - run_width / 2, value + max_value * 0.02, f"{trigger_rates[index]:.1f}%", ha="center", va="bottom", fontsize=8)
    for index, value in enumerate(runs_with_triggered_success):
        axes[1].text(x[index] + run_width / 2, value + max_value * 0.02, f"{triggered_success_run_rates[index]:.1f}%", ha="center", va="bottom", fontsize=8)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(models, rotation=25)
    axes[1].set_ylabel("Runs with >=1 turn")
    axes[1].set_title("Runs with compactor triggers by model")
    axes[1].legend(fontsize=8)
    axes[1].tick_params(axis="x", rotation=25)
    return _save(fig, fig_dir / "compactor_trigger_summary_by_model.png")


def _plot_run_timing(rows: list[dict[str, str]], fig_dir: Path) -> Path | None:
    if not rows:
        return None
    rows = sorted(rows, key=lambda row: _f(row.get("total_mean_sec")), reverse=True)
    models = [row["model"] for row in rows]
    planning = [_f(row.get("planning_mean_sec")) for row in rows]
    execution = [_f(row.get("execution_mean_sec")) for row in rows]
    verdict = [_f(row.get("verdict_mean_sec")) for row in rows]
    error_rates = [_f(row.get("error_run_rate")) * 100 for row in rows]
    x = np.arange(len(models))

    fig, ax = plt.subplots(figsize=(11, 7))
    ax.bar(x, planning, label="Planning", color="#1f78b4")
    ax.bar(x, execution, bottom=planning, label="Execution", color="#33a02c")
    bottoms = [planning[index] + execution[index] for index in range(len(planning))]
    ax.bar(x, verdict, bottom=bottoms, label="Verdict", color="#ff7f00")
    for index, row in enumerate(rows):
        total = _f(row.get("total_mean_sec"))
        ax.text(x[index], total + 15, f"{total:.0f}s\nerr {error_rates[index]:.1f}%", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.set_ylabel("Mean seconds")
    ax.set_title("Run timing by model")
    ax.legend()
    return _save(fig, fig_dir / "run_timing_by_model.png")


def _plot_run_timing_by_model_section(rows: list[dict[str, str]], fig_dir: Path) -> Path | None:
    if not rows:
        return None

    models = sorted({row["model"] for row in rows})
    major_sections = sorted({row["major_section"] for row in rows}, key=_section_sort_key)
    if not models or not major_sections:
        return None

    row_by_key = {(row["model"], row["major_section"]): row for row in rows}
    warning_threshold = _f(rows[0].get("warning_threshold_sec"))

    fig, ax = plt.subplots(figsize=(max(11, 1.2 * len(major_sections) + 4), 7))
    x = np.arange(len(major_sections))
    width = min(0.8 / max(1, len(models)), 0.22)
    palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]
    planning_label_added = False

    for index, model in enumerate(models):
        offset = (index - (len(models) - 1) / 2) * width
        bar_x = x + offset
        totals = [_f((row_by_key.get((model, section)) or {}).get("total_mean_sec")) for section in major_sections]
        totals = [0.0 if np.isnan(value) else value for value in totals]
        planning = [_f((row_by_key.get((model, section)) or {}).get("planning_mean_sec")) for section in major_sections]
        ax.bar(bar_x, totals, width=width, label=model, color=palette[index % len(palette)])
        valid_planning = [value for value in planning if not np.isnan(value)]
        if valid_planning:
            ax.scatter(
                bar_x,
                planning,
                marker="_",
                s=280,
                linewidths=2.2,
                color="#003f5c",
                label="planning mean (per model & section)" if not planning_label_added else None,
                zorder=4,
            )
            planning_label_added = True

    if not np.isnan(warning_threshold):
        ax.axhline(
            warning_threshold,
            color="#8c1d18",
            linestyle="--",
            linewidth=1.7,
            label=f"warning threshold ({warning_threshold:.0f}s)",
        )
    ax.set_xticks(x)
    ax.set_xticklabels(major_sections)
    ax.set_xlabel("Prompt major section")
    ax.set_ylabel("Mean total seconds per run")
    ax.set_title("Prompt-run time by major section and model")
    ax.legend(ncol=2 if len(models) > 3 else 1)
    return _save(fig, fig_dir / "run_timing_by_model_section.png")


def _plot_prompt_tool_heatmap(rows: list[dict[str, str]], fig_dir: Path) -> Path | None:
    if not rows:
        return None
    prompt_totals: dict[str, float] = defaultdict(float)
    tool_totals: dict[str, float] = defaultdict(float)
    for row in rows:
        prompt_totals[row["question_id"]] += _f(row.get("n_calls"))
        tool_totals[row["tool_name"]] += _f(row.get("n_calls"))
    prompts = [name for name, _ in sorted(prompt_totals.items(), key=lambda item: item[1], reverse=True)[:TOP_N]]
    tools = [name for name, _ in sorted(tool_totals.items(), key=lambda item: item[1], reverse=True)[:TOP_N]]
    if not prompts or not tools:
        return None

    row_by_key = {(row["question_id"], row["tool_name"]): row for row in rows}
    matrix = np.zeros((len(prompts), len(tools)))
    for p_index, prompt in enumerate(prompts):
        for t_index, tool in enumerate(tools):
            row = row_by_key.get((prompt, tool))
            matrix[p_index, t_index] = (_f(row.get("call_share")) * 100) if row else 0.0

    fig, ax = plt.subplots(figsize=(12, 8))
    image = ax.imshow(matrix, cmap="YlGnBu", aspect="auto")
    ax.set_xticks(np.arange(len(tools)))
    ax.set_xticklabels(tools, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(prompts)))
    ax.set_yticklabels(prompts)
    ax.set_title("Prompt-tool affinity heatmap (top 10 prompts x top 10 tools)")
    for p_index in range(len(prompts)):
        for t_index in range(len(tools)):
            value = matrix[p_index, t_index]
            if value > 0:
                ax.text(t_index, p_index, f"{value:.1f}", ha="center", va="center", fontsize=7)
    fig.colorbar(image, ax=ax, label="Call share (%)")
    return _save(fig, fig_dir / "prompt_tool_affinity_heatmap_top10.png")


def _plot_failures(rows: list[dict[str, str]], fig_dir: Path) -> Path | None:
    if not rows:
        return None
    rows = list(reversed(_top_rows(rows, sort_key="n_failures")))
    labels = [_wrap_label(f"{row['tool_name']}: {row.get('error_reason') or row.get('error_category') or ''}", width=48) for row in rows]
    values = [_f(row.get("n_failures")) for row in rows]
    fig, ax = plt.subplots(figsize=(13, 8))
    ax.barh(labels, values, color="#c51b8a")
    ax.set_xlabel("Failures")
    ax.set_title("Top 10 tool failures by reason")
    return _save(fig, fig_dir / "tool_failures_top10.png")


def _plot_parallel_patterns(rows: list[dict[str, str]], fig_dir: Path) -> Path | None:
    if not rows:
        return None
    rows = list(reversed(_top_rows(rows, sort_key="n_occurrences")))
    labels = [_wrap_label(row["group_signature"], width=42) for row in rows]
    values = [_f(row.get("n_occurrences")) for row in rows]
    walls = [_f(row.get("mean_wall_sec")) for row in rows]
    fig, ax = plt.subplots(figsize=(13, 8))
    ax.barh(labels, values, color="#756bb1")
    if values:
        offset = max(values) * 0.01
        for index, wall in enumerate(walls):
            ax.text(values[index] + offset, index, f"{wall:.0f}s", va="center", fontsize=8)
    ax.set_xlabel("Occurrences")
    ax.set_title("Top 10 parallel batch patterns")
    return _save(fig, fig_dir / "parallel_batch_patterns_top10.png")


def _plot_workflow_snippets(rows: list[dict[str, str]], fig_dir: Path) -> Path | None:
    if not rows:
        return None
    rows = list(reversed(_top_rows(rows, sort_key="n_occurrences")))
    labels = [_wrap_label(row["snippet"], width=50) for row in rows]
    values = [_f(row.get("n_occurrences")) for row in rows]
    fig, ax = plt.subplots(figsize=(13, 8))
    ax.barh(labels, values, color="#2ca25f")
    ax.set_xlabel("Occurrences")
    ax.set_title("Top 10 workflow snippets")
    return _save(fig, fig_dir / "workflow_snippets_top10.png")


def _plot_second_order_tool_chains(overall_rows: list[dict[str, str]], model_rows: list[dict[str, str]], fig_dir: Path) -> Path | None:
    if not overall_rows or not model_rows:
        return None

    models = sorted({row["model"] for row in model_rows})
    chains = [row["chain"] for row in sorted(overall_rows, key=lambda row: _f(row.get("n_occurrences")), reverse=True)[:TOP_CHAIN_N]]
    if not models or not chains:
        return None

    row_by_key = {(row["model"], row["chain"]): row for row in model_rows}
    fig, ax = plt.subplots(figsize=(max(14, 0.9 * len(chains) + 4), 7))
    x = np.arange(len(chains))
    width = min(0.8 / max(1, len(models)), 0.22)
    palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]

    for index, model in enumerate(models):
        heights = [_f((row_by_key.get((model, chain)) or {}).get("n_occurrences")) for chain in chains]
        heights = [0.0 if np.isnan(value) else value for value in heights]
        offset = (index - (len(models) - 1) / 2) * width
        ax.bar(x + offset, heights, width=width, label=model, color=palette[index % len(palette)])

    ax.set_xticks(x)
    ax.set_xticklabels([_wrap_label(chain, width=24) for chain in chains], rotation=35, ha="right")
    ax.set_ylabel("Occurrences across runs")
    ax.set_title("Top-15 second-order tool chains per model (excluding 0_* tools)")
    ax.legend(ncol=2 if len(models) > 3 else 1)
    return _save(fig, fig_dir / "tool_chain_second_order_top15.png")


def render_all(csv_dir: str | Path, fig_dir: str | Path) -> list[Path]:
    csv_root = Path(csv_dir)
    out_root = Path(fig_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for maybe_path in (
        _plot_overall_usage_latency(_read_csv(csv_root / "tool_usage_overall.csv"), out_root),
        _plot_model_preferences(_read_csv(csv_root / "tool_usage_by_model.csv"), out_root),
        _plot_tool_duration_by_model(_read_csv(csv_root / "tool_usage_by_model.csv"), out_root),
        _plot_tool_wall_time_by_model(_read_csv(csv_root / "tool_wall_timing_by_model.csv"), out_root),
        _plot_tool_argo_duration_by_model(_read_csv(csv_root / "tool_argo_timing_by_model.csv"), out_root),
        _plot_compactor_trigger_summary_by_model(_read_csv(csv_root / "compactor_trigger_summary_by_model.csv"), out_root),
        _plot_compactor_context_by_model(_read_csv(csv_root / "compactor_rounds_by_model.csv"), out_root),
        _plot_compactor_selection_by_model(_read_csv(csv_root / "compactor_rounds_by_model.csv"), out_root),
        _plot_compactor_retry_by_model(_read_csv(csv_root / "compactor_rounds_by_model.csv"), out_root),
        _plot_run_timing(_read_csv(csv_root / "run_timing_by_model.csv"), out_root),
        _plot_run_timing_by_model_section(_read_csv(csv_root / "run_timing_by_model_major_section.csv"), out_root),
        _plot_prompt_tool_heatmap(_read_csv(csv_root / "tool_usage_by_prompt.csv"), out_root),
        _plot_failures(_read_csv(csv_root / "tool_failures_by_reason.csv"), out_root),
        _plot_parallel_patterns(_read_csv(csv_root / "parallel_batch_patterns.csv"), out_root),
        _plot_workflow_snippets(_read_csv(csv_root / "workflow_snippets.csv"), out_root),
        _plot_second_order_tool_chains(
            _read_csv(csv_root / "tool_chain_second_order_overall.csv"),
            _read_csv(csv_root / "tool_chain_second_order_by_model.csv"),
            out_root,
        ),
    ):
        if maybe_path is not None:
            written.append(maybe_path)
    return written


__all__ = ["TOP_N", "render_all"]
