"""
Shared output-file writers for test runners.
=============================================
All writers expect a **standardised result dict** with these keys:

    prompt_id    : str
    prompt_text  : str
    answer       : str
    iterations   : int
    elapsed_s    : float
    timed_out    : bool
    tool_history : list[dict]
    error        : str | None   (optional)
    verdict      : str | None   (optional)
    working_memory : str         (optional)
    final_context  : str         (optional)
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Callable, Optional


# ═══════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════

def get_status(result: dict) -> str:
    """Derive ``'OK'``, ``'ERROR'``, or ``'TIMEOUT'`` from a result dict."""
    answer = result.get("answer", "")
    if result.get("error") or "ERROR" in answer:
        return "ERROR"
    if result.get("timed_out"):
        return "TIMEOUT"
    return "OK"


# ═══════════════════════════════════════════════════════════════════════════
#  Per-prompt result file
# ═══════════════════════════════════════════════════════════════════════════

def write_result_md(
    path: Path,
    result: dict,
    *,
    clean_fn: Optional[Callable[[str], str]] = None,
    include_verdict: bool = False,
) -> None:
    """Write a single result markdown file at *path*.

    Parameters
    ----------
    clean_fn : callable, optional
        If provided, applied to the raw answer text before writing.
    include_verdict : bool
        Append a ``## Verdict`` section if ``result["verdict"]`` is truthy.
    """
    pid = result["prompt_id"]
    answer = clean_fn(result["answer"]) if clean_fn else result["answer"]
    n_tools = len(result.get("tool_history", []))

    lines = [
        f"# Q{pid} — Result",
        "",
        f"**Prompt:** {result['prompt_text']}",
        "",
        f"**Tool calls:** {n_tools}  |  **Time:** {result['elapsed_s']:.1f}s  |  "
        f"**Iterations:** {result['iterations']}  |  **Timed out:** {result.get('timed_out', False)}",
        "",
        "---",
        "",
        "## Answer",
        "",
        answer,
    ]
    if include_verdict and result.get("verdict"):
        lines += ["", "---", "", "## Verdict", "", result["verdict"]]
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
#  Per-prompt tool history / trace file
# ═══════════════════════════════════════════════════════════════════════════

def write_history_md(
    path: Path,
    result: dict,
    *,
    rich_mode: bool = False,
    include_working_memory: bool = False,
) -> None:
    """Write a tool trace / history markdown file.

    Parameters
    ----------
    rich_mode : bool
        If *True*, render full argument JSON, full result text, and agent
        reasoning in collapsible ``<details>`` blocks.  If *False*, show a
        compact step list.
    include_working_memory : bool
        Append a final working-memory snapshot section.
    """
    pid = result["prompt_id"]
    n_tools = len(result.get("tool_history", []))

    lines = [
        f"# Q{pid} — Tool {'History' if rich_mode else 'Trace'}",
        "",
        f"**Prompt:** {result['prompt_text']}",
        "",
        f"**Summary:** {result['elapsed_s']:.1f}s  |  "
        f"{result['iterations']} iterations  |  {n_tools} tools",
        "",
        "---",
        "",
    ]

    history = result.get("tool_history", [])
    if not history:
        lines.append("*No tool calls — answered directly.*")
        lines.append("")
    elif rich_mode:
        _write_rich_history(lines, history)
    else:
        _write_compact_history(lines, history)

    # Optional working-memory snapshot
    if include_working_memory:
        wm = result.get("working_memory", "")
        if wm and wm.strip():
            lines += ["---", "", "## Working Memory (final snapshot)", "", wm.strip(), ""]

    lines += [
        "---",
        "",
        f"**Total:** {n_tools} tool calls  |  {result['elapsed_s']:.1f}s  |  "
        f"{get_status(result)}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_rich_history(lines: list[str], history: list[dict]) -> None:
    """Append rich tool-history steps with collapsible sections."""
    for h in history:
        it = h.get("iteration", "?")
        tn = h.get("tool", "?")
        rc = h.get("result_chars", 0)
        et = h.get("elapsed_s", 0)
        args = h.get("arguments", {})
        full = h.get("result_full", "")
        reasoning = h.get("reasoning", "")

        lines.append(f"### Step {it}: `{tn}` — {rc:,} chars, {et:.1f}s")
        lines.append("")

        if reasoning:
            lines.append("**Agent reasoning:**")
            lines.append(f"> {reasoning[:2000]}")
            if len(reasoning) > 2000:
                lines.append(f"> ...({len(reasoning)} chars total)")
            lines.append("")

        if args:
            args_json = json.dumps(args, indent=2, default=str, ensure_ascii=False)
            lines += [
                "<details><summary>Arguments</summary>", "",
                "```json", args_json, "```",
                "</details>", "",
            ]

        if full:
            preview = full[:300].replace("\n", " ")
            lines += [
                f"<details><summary>Full result ({rc:,} chars) — {preview}...</summary>", "",
                "```", full, "```",
                "</details>", "",
            ]

        lines += ["---", ""]


def _write_compact_history(lines: list[str], history: list[dict]) -> None:
    """Append compact tool-history steps."""
    for step in history:
        args_str = json.dumps({k: "..." for k in step.get("args_keys", [])})
        lines.append(f"### Step {step.get('iteration', '?')}: `{step.get('tool', '?')}`")
        lines.append(f"- **Args:** `{args_str}`")
        lines.append(f"- **Result size:** {step.get('result_chars', 0):,} chars")
        lines.append(f"- **Elapsed:** {step.get('elapsed_s', '?')}s")
        lines.append("")


# ═══════════════════════════════════════════════════════════════════════════
#  Summary + JSON trace
# ═══════════════════════════════════════════════════════════════════════════

def write_summary_md(
    out_dir: Path,
    results: list[dict],
    wall_time: float,
    workers: int,
    *,
    agent_name: str = "Agent",
    include_file_links: bool = False,
    link_subdir: bool = False,
) -> Path:
    """Write ``TEST_SUMMARY_{ts}.md`` and return its path.

    Parameters
    ----------
    include_file_links : bool
        Add per-prompt link columns to the summary table.
    link_subdir : bool
        If *True*, link to ``Q{id}/result.md`` subdir layout;
        otherwise link to ``Q{id}_result.md`` flat layout.
    """
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"TEST_SUMMARY_{ts}.md"

    n_ok = sum(1 for r in results if get_status(r) == "OK")
    n_err = sum(1 for r in results if get_status(r) == "ERROR")
    n_timeout = sum(1 for r in results if get_status(r) == "TIMEOUT")
    total_tools = sum(len(r.get("tool_history", [])) for r in results)
    serial_time = sum(r["elapsed_s"] for r in results)

    mode = "sequential" if workers <= 1 else f"parallel ({workers} workers)"
    lines = [
        f"# {agent_name} Test Summary — {ts}",
        "",
        f"**Mode:** {mode}  |  "
        f"**Total:** {len(results)}  |  **OK:** {n_ok}  |  "
        f"**Error:** {n_err}  |  **Timeout:** {n_timeout}",
        "",
        f"**Wall time:** {wall_time:.0f}s  |  "
        f"**Sum of prompt times:** {serial_time:.0f}s  |  "
        f"**Total tools:** {total_tools}",
    ]
    if workers > 1 and wall_time > 0:
        lines.append(f"**Speedup:** {serial_time / wall_time:.1f}x")

    # ── Table ──
    if include_file_links:
        lines += [
            "",
            "| # | Prompt | Tools | Time | Iters | Status | Result | Trace |",
            "|---|--------|------:|-----:|------:|--------|--------|-------|",
        ]
        for r in results:
            qid = f"Q{r['prompt_id']}"
            prompt_short = r["prompt_text"][:55] + ("..." if len(r["prompt_text"]) > 55 else "")
            status = get_status(r)
            if link_subdir:
                res_link = f"[result]({qid}/result.md)"
                trace_link = f"[trace]({qid}/tool_trace.md)"
            else:
                res_link = f"[result]({qid}_result.md)"
                trace_link = f"[history]({qid}_history.md)"
            lines.append(
                f"| {r['prompt_id']} | {prompt_short} | {len(r.get('tool_history', []))} | "
                f"{r['elapsed_s']:.0f}s | {r['iterations']} | {status} | "
                f"{res_link} | {trace_link} |"
            )
    else:
        lines += [
            "",
            "| # | Prompt | Time | Iters | Tools | Status |",
            "|---|--------|------|-------|-------|--------|",
        ]
        for r in results:
            prompt_short = r["prompt_text"][:60] + ("..." if len(r["prompt_text"]) > 60 else "")
            status = get_status(r)
            lines.append(
                f"| {r['prompt_id']} "
                f"| {prompt_short} "
                f"| {r['elapsed_s']:.0f}s "
                f"| {r['iterations']} "
                f"| {len(r.get('tool_history', []))} "
                f"| {status} |"
            )

    lines.append("")
    lines.append(
        f"**Totals:** {len(results)} prompts  |  "
        f"{total_tools} tool calls  |  {serial_time:.0f}s"
    )
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_json_trace(
    out_dir: Path,
    results: list[dict],
    *,
    exclude_fields: tuple[str, ...] = ("working_memory", "final_context"),
) -> Path:
    """Write ``TEST_TRACE_{ts}.json`` and return its path."""
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"TEST_TRACE_{ts}.json"

    trace_data = []
    for r in results:
        jr = {k: v for k, v in r.items() if k not in exclude_fields}
        for field in exclude_fields:
            if field in r:
                val = r.get(field, "") or ""
                jr[f"{field}_chars"] = len(str(val))
        trace_data.append(jr)

    path.write_text(
        json.dumps(trace_data, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )
    return path
