#!/usr/bin/env python
"""
Automated test-runner for TEST_PROMPTS.md
=========================================
Parses the markdown table, sends every prompt through the agentic loop,
and writes per-prompt output files organised by model and batch::

    _output/Model_{name}/Q{id}/Q{id}_result_batch{n}.md
    _output/Model_{name}/Q{id}/Q{id}_history_batch{n}.md
    _output/Model_{name}/SUMMARY_batch{n}.md

Usage:
    python run_tests_SRD46_db_subagent.py                    # run all prompts, default model
    python run_tests_SRD46_db_subagent.py 1.1.1 2.1.3        # specific IDs
    python run_tests_SRD46_db_subagent.py --section 3        # all section 3.x prompts
    python run_tests_SRD46_db_subagent.py -j 4               # parallel workers
    python run_tests_SRD46_db_subagent.py -m gpt5 claudeopus46 -r 5   # multi-model, 5 repeats
"""

import argparse
import collections
import datetime as dt
import json
import logging
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

# -- make sure project root is importable -------------------------
# This script lives in <project_root>/BATCH_run_scripts/, so PROJECT_ROOT is parent.parent.
PROJECT_ROOT = Path(__file__).absolute().parent.parent
REPO_ROOT = PROJECT_ROOT.parents[1]
for _path in (REPO_ROOT, PROJECT_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
os.chdir(PROJECT_ROOT)

# -- main agent API ------------------------------------------------
from NIST_SRD46_db_agent.NIST_SRD46_query_agent import argo_config
from NIST_SRD46_db_agent.NIST_SRD46_query_agent.argo_config import API_URL as ARGO_API_URL
from NIST_SRD46_db_agent.NIST_SRD46_query_agent.argo_client import call_argo
from NIST_SRD46_db_agent.NIST_SRD46_query_agent.agent_runtime import extract_tool_call
from NIST_SRD46_db_agent.NIST_SRD46_query_agent.query_agent import run_agent_query_sync
from NIST_SRD46_db_agent.NIST_SRD46_query_agent.SRD46_tools.postjob_verdict import run_verdict_agent as _run_verdict_agent
from NIST_SRD46_core_db_search_tools._tools_results_compactors._agentic_ref_id_extractor import (
    extract_reference_ids as _extract_reference_ids,
    format_reference_ids_section as _format_reference_ids_section,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("TEST-RUNNER")


# ===============================================================
#  0. Shared Argo pacing (global across parallel workers)
# ===============================================================

_ARGO_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_WORKER_CONTEXT = threading.local()
_ORIGINAL_REQUESTS_POST = requests.post
_REQUESTS_PATCH_LOCK = threading.Lock()
_REQUESTS_PATCHED = False
_ARGO_GATE = None


def _set_worker_prompt_id(prompt_id: Optional[str]) -> None:
    """Attach the current prompt ID to this worker thread for logging."""
    _WORKER_CONTEXT.prompt_id = prompt_id


def _get_worker_prompt_id() -> str:
    return getattr(_WORKER_CONTEXT, "prompt_id", "?")


class _ArgoPermit:
    """Represents a single Argo request admitted by the shared gate."""

    def __init__(self, gate: "SharedArgoGate", ticket: int, label: str,
                 queued_s: float):
        self.gate = gate
        self.ticket = ticket
        self.label = label
        self.queued_s = queued_s
        self.started_at = time.monotonic()

    def finish(self, response=None, exc: Optional[BaseException] = None) -> None:
        elapsed_s = time.monotonic() - self.started_at
        status_code = getattr(response, "status_code", None)
        self.gate.release(
            ticket=self.ticket,
            label=self.label,
            queued_s=self.queued_s,
            elapsed_s=elapsed_s,
            status_code=status_code,
            exc=exc,
        )


class SharedArgoGate:
    """Thread-safe pacing gate for all Argo HTTP requests in this process.

    It enforces two global constraints:
      1. Minimum spacing between Argo request launches.
      2. Maximum number of in-flight Argo requests.

    This lets many prompt workers run in parallel without each worker
    independently hammering the Argo endpoint.
    """

    def __init__(self, min_interval_s: float, max_inflight: int,
                 cooldown_s: float):
        self.min_interval_s = max(0.0, float(min_interval_s))
        self.max_inflight = max(1, int(max_inflight))
        self.cooldown_s = max(0.0, float(cooldown_s))
        self._cond = threading.Condition()
        self._next_launch_at = 0.0
        self._active = 0
        self._ticket = 0
        self._stats = collections.Counter()

    def acquire(self, label: str) -> _ArgoPermit:
        wait_started = time.monotonic()
        with self._cond:
            blocked = False
            while True:
                now = time.monotonic()
                if self._active >= self.max_inflight:
                    blocked = True
                    self._cond.wait(timeout=0.10)
                    continue

                wait_for_launch = self._next_launch_at - now
                if wait_for_launch > 0:
                    blocked = True
                    self._cond.wait(timeout=min(wait_for_launch, 0.10))
                    continue

                self._ticket += 1
                ticket = self._ticket
                self._active += 1
                self._next_launch_at = max(now, self._next_launch_at) + self.min_interval_s
                queued_s = now - wait_started
                self._stats["started"] += 1
                if blocked:
                    self._stats["queued"] += 1
                log.info(
                    "[ARGO-GATE] start #%d %s active=%d/%d queued=%.2fs",
                    ticket, label, self._active, self.max_inflight, queued_s,
                )
                return _ArgoPermit(self, ticket, label, queued_s)

    def release(self, *, ticket: int, label: str, queued_s: float,
                elapsed_s: float, status_code: Optional[int],
                exc: Optional[BaseException]) -> None:
        with self._cond:
            self._active = max(0, self._active - 1)
            self._stats["finished"] += 1

            cooldown = False
            if exc is not None:
                cooldown = self.cooldown_s > 0
            elif status_code in _ARGO_RETRYABLE_STATUS_CODES:
                cooldown = self.cooldown_s > 0

            if cooldown:
                self._next_launch_at = max(
                    self._next_launch_at,
                    time.monotonic() + self.cooldown_s,
                )
                self._stats["cooldowns"] += 1

            self._cond.notify_all()

        if exc is not None:
            log.warning(
                "[ARGO-GATE] done  #%d %s status=EXC elapsed=%.2fs queued=%.2fs cooldown=%s err=%s",
                ticket, label, elapsed_s, queued_s, cooldown, exc,
            )
        else:
            log.info(
                "[ARGO-GATE] done  #%d %s status=%s elapsed=%.2fs queued=%.2fs cooldown=%s",
                ticket, label, status_code, elapsed_s, queued_s, cooldown,
            )

    def snapshot(self) -> dict:
        with self._cond:
            return {
                "min_interval_s": self.min_interval_s,
                "max_inflight": self.max_inflight,
                "cooldown_s": self.cooldown_s,
                "active": self._active,
                **dict(self._stats),
            }


def _is_argo_post(url) -> bool:
    return str(url).rstrip("/") == ARGO_API_URL.rstrip("/")


def _extract_argo_payload(kwargs: dict) -> dict:
    payload = kwargs.get("json")
    if isinstance(payload, dict):
        return payload

    data = kwargs.get("data")
    if isinstance(data, bytes):
        data = data.decode("utf-8", errors="ignore")
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _describe_argo_post(kwargs: dict) -> str:
    payload = _extract_argo_payload(kwargs)
    model = payload.get("model", "?")
    system = str(payload.get("system", ""))
    prompt = payload.get("prompt", "")
    if isinstance(prompt, list):
        prompt_len = sum(len(p) for p in prompt if isinstance(p, str))
    elif isinstance(prompt, str):
        prompt_len = len(prompt)
    else:
        prompt_len = 0

    kind = "chat"
    if system.startswith("You are the **Strategy Planner**"):
        kind = "planner"
    elif system.startswith("You are the **Plan Evaluator**"):
        kind = "evaluator"
    elif system.startswith("You are a fast **Triage Agent**"):
        kind = "preplan"

    return (
        f"prompt={_get_worker_prompt_id()} "
        f"kind={kind} model={model} prompt_len={prompt_len}"
    )


def _install_argo_gate(gate: SharedArgoGate) -> None:
    """Monkeypatch requests.post so every Argo HTTP call shares one gate."""
    global _ARGO_GATE, _REQUESTS_PATCHED
    _ARGO_GATE = gate

    with _REQUESTS_PATCH_LOCK:
        if _REQUESTS_PATCHED:
            return

        def _gated_post(url, *args, **kwargs):
            if _ARGO_GATE is None or not _is_argo_post(url):
                return _ORIGINAL_REQUESTS_POST(url, *args, **kwargs)

            permit = _ARGO_GATE.acquire(_describe_argo_post(kwargs))
            try:
                response = _ORIGINAL_REQUESTS_POST(url, *args, **kwargs)
            except Exception as exc:
                permit.finish(exc=exc)
                raise
            permit.finish(response=response)
            return response

        requests.post = _gated_post
        _REQUESTS_PATCHED = True

# ===============================================================
#  1. Parse TEST_PROMPTS.md
# ===============================================================

_TABLE_ROW_RE = re.compile(
    r"^\|\s*(\d+(?:\.\d+)+)\s*\|\s*(.+?)\s*\|$"
)

_SECTION_HEADER_RE = re.compile(
    r"^##\s+(\d+(?:\.\d+)?)\s*[—–-]\s*(.+)$"
)


def parse_prompts(md_path: Path) -> List[dict]:
    """Return a list of {id, section, section_title, prompt}."""
    prompts = []
    current_section = ""
    current_title = ""

    for line in md_path.read_text(encoding="utf-8").splitlines():
        sh = _SECTION_HEADER_RE.match(line)
        if sh:
            current_section = sh.group(1)
            current_title = sh.group(2).strip()
            continue

        m = _TABLE_ROW_RE.match(line)
        if m:
            prompts.append({
                "id":            m.group(1),
                "section":       current_section,
                "section_title": current_title,
                "prompt":        m.group(2).strip(),
            })
    return prompts


# ===============================================================
#  1b. Tool-result statistics extractor (diagnostic only)
# ===============================================================

def _extract_result_stats(result_str: str) -> dict:
    """Parse a tool result string and extract diagnostic stats.

    Returns a dict with keys like:
      row_count, vlm_ids, metal_ids, ligand_ids, network_ids, node_ids,
      log_K_range, unique_metals, unique_ligands, etc.
    Only populated keys are included.

    When the result has been truncated (head+tail with omitted middle),
    json.loads will fail, so we fall back to regex extraction of IDs
    and values from the visible portions.
    """
    stats: dict = {}
    truncated = "chars omitted]" in result_str

    try:
        data = json.loads(result_str)
    except (json.JSONDecodeError, TypeError):
        if not truncated:
            return stats
        # ── Regex fallback for truncated results ──
        return _extract_stats_regex(result_str)

    # Handle single-dict results (e.g. comprehensive_vlm_lookup)
    if isinstance(data, dict):
        stats["type"] = "object"
        stats["top_keys"] = sorted(data.keys())[:15]
        for section_key in ("card", "equilibrium_networks", "citations"):
            if section_key in data:
                val = data[section_key]
                if isinstance(val, list):
                    stats[f"{section_key}_count"] = len(val)
                elif isinstance(val, dict):
                    stats[f"{section_key}_keys"] = sorted(val.keys())[:10]
        return stats

    if not isinstance(data, list):
        return stats

    return _extract_stats_from_rows(data, stats)


def _extract_stats_regex(text: str) -> dict:
    """Extract ID stats from truncated JSON text via regex.

    The text is typically head(3000) + '... [N chars omitted] ...' + tail(2500).
    Both head and tail contain complete JSON objects we can extract from.
    """
    stats: dict = {"truncated": True}

    # Regex patterns for ID fields: "field_name": <integer>
    _ID_PATTERNS = {
        "vlm_id":        re.compile(r'"vlm_id"\s*:\s*(\d+)'),
        "example_vlm_id": re.compile(r'"example_vlm_id"\s*:\s*(\d+)'),
        "metal_id":      re.compile(r'"metal_id"\s*:\s*(\d+)'),
        "ligand_id":     re.compile(r'"ligand_id"\s*:\s*(\d+)'),
        "network_id":    re.compile(r'"network_id"\s*:\s*(\d+)'),
        "node_id":       re.compile(r'"node_id"\s*:\s*(\d+)'),
        "collection_id": re.compile(r'"collection_id"\s*:\s*(\d+)'),
    }
    # Name fields: "field_name": "value"
    _NAME_PATTERNS = {
        "metal_name":   re.compile(r'"metal_name"\s*:\s*"([^"]+)"'),
        "ligand_name":  re.compile(r'"ligand_name"\s*:\s*"([^"]+)"'),
        "ligand_class": re.compile(r'"ligand_class"\s*:\s*"([^"]+)"'),
    }
    # log_K: "log_K": <number>
    _LOG_K_RE = re.compile(r'"log_K"\s*:\s*(-?[\d.]+)')

    for fld, pat in _ID_PATTERNS.items():
        ids = sorted(set(int(m) for m in pat.findall(text)))
        if ids:
            stats[fld + "s"] = ids if len(ids) <= 20 else (
                ids[:10] + ["..."] + ids[-5:]
            )
            stats[fld + "_count"] = len(ids)

    for fld, pat in _NAME_PATTERNS.items():
        names = sorted(set(pat.findall(text)))
        if names:
            stats["unique_" + fld + "s"] = names if len(names) <= 15 else (
                names[:10] + [f"... +{len(names)-10} more"]
            )

    log_k_vals = [float(v) for v in _LOG_K_RE.findall(text)]
    if log_k_vals:
        stats["log_K_range"] = [round(min(log_k_vals), 3),
                                round(max(log_k_vals), 3)]
        stats["log_K_count"] = len(log_k_vals)

    # Estimate row count from the number of vlm_id occurrences (most common key)
    if "vlm_id_count" in stats:
        stats["visible_rows"] = stats["vlm_id_count"]
        stats["note"] = "IDs from visible head+tail only; middle was omitted"

    return stats


def _extract_stats_from_rows(data: list, stats: dict) -> dict:
    """Extract stats from a fully-parsed list of row dicts."""
    stats["row_count"] = len(data)
    if not data:
        return stats

    id_fields = {
        "vlm_id": set(), "example_vlm_id": set(),
        "metal_id": set(), "ligand_id": set(),
        "network_id": set(), "node_id": set(), "collection_id": set(),
        "citation_id": set(),
    }
    name_fields = {"metal_name": set(), "ligand_name": set(), "ligand_class": set()}
    log_k_vals = []

    for row in data:
        if not isinstance(row, dict):
            continue
        for fld, s in id_fields.items():
            if fld in row and row[fld] is not None:
                s.add(row[fld])
        for fld, s in name_fields.items():
            if fld in row and row[fld] is not None:
                s.add(str(row[fld]))
        if "log_K" in row and row["log_K"] is not None:
            try:
                log_k_vals.append(float(row["log_K"]))
            except (ValueError, TypeError):
                pass

    for fld, s in id_fields.items():
        if s:
            sorted_ids = sorted(s)
            stats[fld + "s"] = sorted_ids if len(sorted_ids) <= 20 else (
                sorted_ids[:10] + ["..."] + sorted_ids[-5:]
            )
            stats[fld + "_count"] = len(s)

    for fld, s in name_fields.items():
        if s:
            names = sorted(s)
            stats["unique_" + fld + "s"] = names if len(names) <= 15 else (
                names[:10] + [f"... +{len(names)-10} more"]
            )

    if log_k_vals:
        stats["log_K_range"] = [round(min(log_k_vals), 3),
                                round(max(log_k_vals), 3)]
        stats["log_K_count"] = len(log_k_vals)

    return stats


# ===============================================================
#  2. Output writers
# ===============================================================

OUTPUT_DIR = REPO_ROOT / "_benchmark" / "Query"
VERBOSE_HISTORY = False
CURRENT_MODEL_DIR: Path = OUTPUT_DIR
CURRENT_BATCH: int = 1


def _qid(prompt_id: str) -> str:
    """Convert '1.3' -> 'Q1.3' for filenames."""
    return f"Q{prompt_id}"


# -- Answer cleaner --------------------------------------------------

_TOOL_XML_RE = re.compile(
    r"<tool_(?:call|result)>.*?</tool_(?:call|result)>",
    re.DOTALL,
)
_BARE_TOOL_JSON_RE = re.compile(
    r'\{"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{[^}]*\}\s*\}',
)
_GARBLED_ASSISTANT_RE = re.compile(
    r"^## Assistant.*?$",
    re.MULTILINE,
)
_CONVERSATION_ECHO_RE = re.compile(
    r"^## (?:User|Assistant)\n.*?(?=^## |\Z)",
    re.MULTILINE | re.DOTALL,
)


def _clean_answer(raw: str) -> str:
    """Strip <tool_call>/<tool_result> blocks and echoed conversation
    turns from the LLM's final response, keeping only the substantive
    answer text."""
    # 1. Remove tool XML blocks
    text = _TOOL_XML_RE.sub("", raw)
    # 1b. Remove bare JSON tool calls and garbled ## Assistant to=tool_call lines
    text = _BARE_TOOL_JSON_RE.sub("", text)
    text = _GARBLED_ASSISTANT_RE.sub("", text)
    # 2. Remove echoed ## User / ## Assistant conversation blocks,
    #    but keep the LAST ## Assistant block if present (that's the answer)
    parts = re.split(r"(?=^## (?:User|Assistant|Answer))", text, flags=re.MULTILINE)
    # Keep anything before the first ## User/Assistant and the last Assistant block
    cleaned_parts = []
    for p in parts:
        if p.startswith("## User"):
            continue  # drop echoed user turns
        if p.startswith("## Assistant"):
            p = re.sub(r"^## Assistant\n?", "", p)
        elif p.startswith("## Answer"):
            p = re.sub(r"^## Answer\n?", "", p)
        cleaned_parts.append(p)
    text = "\n".join(cleaned_parts)
    # 3. Collapse excessive blank lines
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    text = text.strip()
    # 4. Fallback: if cleaning removed everything, show raw (minus tool XML)
    if not text:
        fallback = _TOOL_XML_RE.sub("", raw).strip()
        fallback = _BARE_TOOL_JSON_RE.sub("", fallback).strip()
        fallback = _GARBLED_ASSISTANT_RE.sub("", fallback).strip()
        # Take only the last 2000 chars to avoid dumping huge echoed prompts
        if len(fallback) > 2000:
            fallback = "...\n" + fallback[-2000:]
        if fallback:
            text = "*(Agent did not produce a clear final answer. Raw tail below.)*\n\n" + fallback
        else:
            text = "*(Agent did not produce a final answer — only tool calls were emitted.)*"
    return text


# -- Per-prompt file writers -----------------------------------------

def _format_time_breakdown(r: dict) -> str:
    """Format time as '{planning + execution} + {verdict}'."""
    elapsed = r.get("elapsed", 0.0)
    verdict_elapsed = r.get("verdict_elapsed", 0.0)

    plan_tools = {"0_preplan_decision", "0_plan_search_strategy",
                  "search_metals", "search_ligands", "search_similar_ligands",
                  "build_system_catalog"}
    planning_end = 0.0
    for step in r.get("tool_history", []):
        if step.get("tool") in plan_tools:
            planning_end = max(planning_end, step.get("elapsed_at", 0.0))

    if planning_end > 0:
        execution_time = elapsed - planning_end
        return (f"{planning_end:.0f}s planning + {execution_time:.0f}s execution"
                f" + {verdict_elapsed:.0f}s verdict"
                f" = {elapsed + verdict_elapsed:.0f}s total")
    return f"{elapsed:.0f}s query + {verdict_elapsed:.0f}s verdict = {elapsed + verdict_elapsed:.0f}s total"


def write_single_result(r: dict, out_dir: Path, *, batch: int = 1):
    """Write one result file: Q<id>/Q<id>_result_batch<n>.md"""
    answer = _clean_answer(r["answer"])
    verdict = r.get("verdict", "")
    qid = _qid(r['id'])
    lines = [
        f"# {qid} -- Result (batch {batch})",
        f"",
        f"**Section:** {r['section']} -- {r['section_title']}",
        f"",
        f"**Prompt:** {r['prompt']}",
        f"",
        f"**Tool calls:** {r['tool_count']}  |  **Time:** {_format_time_breakdown(r)}",
        f"",
        f"---",
        f"",
        answer,
        f"",
    ]
    if verdict:
        lines.extend([
            f"---",
            f"",
            f"### Verdict & Explanation",
            f"",
            verdict,
            f"",
        ])
    prompt_dir = out_dir / qid
    prompt_dir.mkdir(parents=True, exist_ok=True)
    fp = prompt_dir / f"{qid}_result_batch{batch}.md"
    fp.write_text("\n".join(lines), encoding="utf-8")
    return fp


_SELECTED_CANDIDATES_RE = re.compile(r"selected candidates \[(?P<candidates>[^\]]*)\]", re.IGNORECASE)


def _compactor_round_events(events: list[dict]) -> list[dict]:
    return [event for event in events if event.get("event_kind") == "round_complete"]


def _compactor_summary_metrics(events: list[dict]) -> dict[str, int]:
    metrics = {
        "selection_rounds": 0,
        "candidates_selected": 0,
        "skipped_none": 0,
        "summaries_generated": 0,
        "accepted": 0,
        "validator_skipped": 0,
        "retry_requests": 0,
        "retry_exhausted": 0,
        "max_retry_keep": 0,
        "summary_failed": 0,
    }

    for event in events:
        message = str(event.get("message", ""))
        selected_match = _SELECTED_CANDIDATES_RE.search(message)
        if selected_match:
            metrics["selection_rounds"] += 1
            candidates = [token.strip() for token in selected_match.group("candidates").split(",") if token.strip()]
            metrics["candidates_selected"] += len(candidates)
        elif "chose NONE" in message:
            metrics["selection_rounds"] += 1
            metrics["skipped_none"] += 1

        if "Summary sub-agent produced" in message:
            metrics["summaries_generated"] += 1
        if "ACCEPTED" in message:
            metrics["accepted"] += 1
        if "SKIPPED by validator" in message:
            metrics["validator_skipped"] += 1
        if "RETRY attempt" in message:
            metrics["retry_requests"] += 1
        if "exhausted" in message and "inner retries" in message:
            metrics["retry_exhausted"] += 1
        if "hit MAX_RETRY" in message:
            metrics["max_retry_keep"] += 1
        if "Summary sub-agent failed" in message:
            metrics["summary_failed"] += 1

    return metrics


def _append_compactor_summary(lines: list[str], events: list[dict]) -> None:
    if not events:
        return

    metrics = _compactor_summary_metrics(events)
    round_events = _compactor_round_events(events)
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"### Compactor Activity ({len(events)} events)")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("|--------|------:|")
    lines.append(f"| Selection rounds | {metrics['selection_rounds']} |")
    lines.append(f"| Candidates selected | {metrics['candidates_selected']} |")
    lines.append(f"| Skipped (NONE) | {metrics['skipped_none']} |")
    lines.append(f"| Summaries generated | {metrics['summaries_generated']} |")
    lines.append(f"| Accepted | {metrics['accepted']} |")
    lines.append(f"| Validator skipped | {metrics['validator_skipped']} |")
    lines.append(f"| Retry requests | {metrics['retry_requests']} |")
    lines.append(f"| Retry exhausted | {metrics['retry_exhausted']} |")
    lines.append(f"| Max retry keep | {metrics['max_retry_keep']} |")
    lines.append(f"| Summary sub-agent failed | {metrics['summary_failed']} |")
    lines.append("")
    if round_events:
        lines.append("#### Compactor Rounds")
        lines.append("")
        lines.append("| Iter | Kind | Outcome | Selected | Context Before | Context After | Delta | Selection (s) | Round (s) |")
        lines.append("|------|------|---------|---------:|----------------|---------------|------:|--------------:|----------:|")
        for event in round_events:
            before_chars = event.get("context_chars_before")
            after_chars = event.get("context_chars_after")
            before_turns = event.get("context_turns_before")
            after_turns = event.get("context_turns_after")
            delta = "***"
            if isinstance(before_chars, (int, float)) and isinstance(after_chars, (int, float)):
                delta = f"{int(after_chars - before_chars):+d}"
            before_cell = f"{before_chars} chars / {before_turns} turns"
            after_cell = f"{after_chars} chars / {after_turns} turns"
            selected_cell = f"{event.get('candidates_selected', 0)} / {event.get('candidate_count', 0)}"
            selection_s = event.get("selection_duration_s")
            round_s = event.get("round_duration_s")
            selection_cell = f"{selection_s:.2f}" if isinstance(selection_s, (int, float)) else "***"
            round_cell = f"{round_s:.2f}" if isinstance(round_s, (int, float)) else "***"
            lines.append(
                f"| {event.get('after_iteration', '?')} | {event.get('round_kind', 'session')} | {event.get('outcome', '?')} | {selected_cell} | {before_cell} | {after_cell} | {delta} | {selection_cell} | {round_cell} |"
            )
        lines.append("")
    lines.append("<details><summary>Full compactor log</summary>")
    lines.append("")
    for event in events:
        lines.append(
            f"- **[{event['level']}]** (after iter {event.get('after_iteration', '?')}) {event['message']}"
        )
    lines.append("")
    lines.append("</details>")
    lines.append("")


def write_single_history(r: dict, out_dir: Path, *, batch: int = 1, verbose_history: bool = False):
    """Write one history file: Q<id>/Q<id>_history_batch<n>.md with enriched diagnostics."""
    lines = [
        f"# {_qid(r['id'])} -- Tool History (batch {batch})",
        f"",
        f"**Prompt:** {r['prompt']}",
        f"",
        f"---",
        f"",
    ]
    if not r["tool_history"]:
        lines.append("*No tool calls -- answered directly.*")
        lines.append("")
    else:
        for step_num, step in enumerate(r["tool_history"], 1):
            args_str = json.dumps(step["arguments"], ensure_ascii=False, indent=2)
            display_data = step.get("display_result", step.get("memory_result", step.get("result_full", "")))
            raw_data = step.get("result_full", "")
            parallel_tag = ""
            if step.get("parallel"):
                group_size = step.get("parallel_group", "?")
                parallel_tag = f"  *(parallel {group_size}x)*"
            error_tag = "  **[ERROR]**" if step.get("is_error") else ""
            duration = step.get("duration_s")
            elapsed = step.get("elapsed_at")
            timing_tag = ""
            if duration is not None:
                timing_tag = f"  *[{duration:.1f}s"
                if elapsed is not None:
                    timing_tag += f" @ {elapsed:.0f}s"
                timing_tag += "]*"
            lines.append(f"**Step {step_num}:** `{step['tool']}`{parallel_tag}{error_tag}{timing_tag}")
            lines.append(f"  - Args:")
            lines.append(f"    ```json")
            for arg_line in args_str.splitlines():
                lines.append(f"    {arg_line}")
            lines.append(f"    ```")
            if step.get("is_error"):
                lines.append(f"  - **Error:** {display_data.strip()}")
            lines.append(
                f"  - Agent-facing result: {step.get('display_result_chars', len(display_data))} chars"
            )
            if step.get("immediate_compacted"):
                compaction_kind = step.get("compaction_kind") or "immediate"
                lines.append(f"  - Agent memory: immediate {compaction_kind} compaction applied")
            lines.append(f"")
            lines.append(f"  <details><summary>Agent-facing result</summary>")
            lines.append(f"")
            lines.append(display_data)
            lines.append(f"")
            lines.append(f"  </details>")
            lines.append(f"")
            if verbose_history and raw_data and raw_data != display_data:
                lines.append("  <details><summary>Raw tool output (debug)</summary>")
                lines.append("")
                lines.append("  ```json")
                lines.append(raw_data)
                lines.append("  ```")
                lines.append("")
                lines.append("  </details>")
                lines.append("")

            # ── Enriched result statistics ──
            stats = step.get("result_stats", {})
            if stats:
                is_trunc = stats.get("truncated", False)
                tag = " *(from visible head+tail)*" if is_trunc else ""
                lines.append(f"  - **Result stats{tag}:**")
                if "type" in stats and stats["type"] == "object":
                    lines.append(f"    - Type: single object, keys: {stats.get('top_keys', [])}")
                    for sk in ("card", "equilibrium_networks", "citations"):
                        if f"{sk}_count" in stats:
                            lines.append(f"    - `{sk}`: {stats[f'{sk}_count']} items")
                        elif f"{sk}_keys" in stats:
                            lines.append(f"    - `{sk}`: keys={stats[f'{sk}_keys']}")
                elif "row_count" in stats or "visible_rows" in stats:
                    row_label = stats.get("row_count", stats.get("visible_rows", "?"))
                    lines.append(f"    - Rows: **{row_label}**{' (visible only)' if is_trunc else ''}")
                    for id_fld in ("vlm_id", "example_vlm_id", "metal_id", "ligand_id",
                                   "network_id", "node_id", "collection_id"):
                        count_key = id_fld + "_count"
                        list_key  = id_fld + "s"
                        if count_key in stats:
                            ids_str = ", ".join(str(x) for x in stats[list_key])
                            lines.append(f"    - `{id_fld}`: {stats[count_key]} unique — [{ids_str}]")
                    for name_fld in ("unique_metal_names", "unique_ligand_names",
                                     "unique_ligand_classs"):
                        if name_fld in stats:
                            vals = stats[name_fld]
                            lines.append(f"    - {name_fld}: {vals}")
                    if "log_K_range" in stats:
                        lo, hi = stats["log_K_range"]
                        lines.append(f"    - log_K: {stats['log_K_count']} values, range [{lo}, {hi}]")
            lines.append("")

            # ── Compactor events for this step ──
            tool_name = step.get("tool")
            comp_events = [
                e for e in r.get("compactor_events", [])
                if e.get("after_iteration") == step["iteration"]
                and e.get("for_tool") == tool_name
            ]
            if comp_events:
                lines.append(f"  - **Compactor events** (iter {step['iteration']}, `{tool_name}`):")
                for ev in comp_events:
                    lines.append(f"    - [{ev['level']}] {ev['message']}")
                lines.append("")

    # ── Compactor summary ──
    _append_compactor_summary(lines, r.get("compactor_events", []))

    # ── Error summary ──
    error_steps = [
        (i + 1, s) for i, s in enumerate(r.get("tool_history", []))
        if s.get("is_error")
    ]
    if error_steps:
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append(f"### Tool Errors ({len(error_steps)})")
        lines.append("")
        for step_num, s in error_steps:
            err_msg = s.get("result_full", s.get("display_result", ""))
            lines.append(
                f"- **Step {step_num}** `{s['tool']}` (iter {s.get('iteration', '?')}):"
            )
            lines.append(f"  ```")
            lines.append(f"  {err_msg.strip()}")
            lines.append(f"  ```")
        lines.append("")

    lines.append(f"**Total calls:** {r['tool_count']}  |  "
                  f"**Elapsed:** {r['elapsed']:.1f} s")
    lines.append("")

    qid = _qid(r['id'])
    prompt_dir = out_dir / qid
    prompt_dir.mkdir(parents=True, exist_ok=True)
    fp = prompt_dir / f"{qid}_history_batch{batch}.md"
    fp.write_text("\n".join(lines), encoding="utf-8")

    # -- write companion ref-IDs file --
    ref_lines = [
        f"# {qid} -- Referenced Entity IDs (batch {batch})",
        f"",
        f"**Prompt:** {r['prompt']}",
        f"",
        f"---",
        f"",
    ]
    has_refs = False
    for step_num, step in enumerate(r["tool_history"], 1):
        section = _extract_step_ref_ids(step_num, step)
        if section:
            ref_lines.append(section)
            has_refs = True
    if has_refs:
        ref_fp = prompt_dir / f"{qid}_ref_ids_batch{batch}.md"
        ref_fp.write_text("\n".join(ref_lines), encoding="utf-8")

    return fp


# -- Ref-ID extraction helper -----------------------------------------

def _extract_step_ref_ids(step_num: int, step: dict) -> str:
    """Extract ref IDs from a tool step's raw result and return markdown."""
    if _extract_reference_ids is None:
        return ""
    tool_name = step.get("tool", "")
    raw = step.get("result_full", "")
    # strip special prefixes before parsing
    for pfx in ("[CATALOG]", "[PREPLAN]", "[PLAN]", "[PLAN:DONE]"):
        if raw.lstrip().startswith(pfx):
            raw = raw.lstrip()[len(pfx):].lstrip()
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return ""
    refs = _extract_reference_ids(tool_name, data)
    if not refs:
        return ""
    lines = [
        f"### Step {step_num}: `{tool_name}`",
        _format_reference_ids_section(refs),
        "",
    ]
    return "\n".join(lines)


# -- Streaming history writer -----------------------------------------

class _StreamingHistoryWriter:
    """Appends each tool step to the history file as it happens."""

    def __init__(self, prompt_record: dict, out_dir: Path, *,
                 batch: int = 1, verbose_history: bool = False):
        self._prompt_record = prompt_record
        self._batch = batch
        self._verbose_history = verbose_history
        self._step_count = 0
        self._all_compactor_events: list[dict] = []

        qid = _qid(prompt_record["id"])
        prompt_dir = out_dir / qid
        prompt_dir.mkdir(parents=True, exist_ok=True)
        self._fp = prompt_dir / f"{qid}_history_batch{batch}.md"
        self._ref_fp = prompt_dir / f"{qid}_ref_ids_batch{batch}.md"

        header = "\n".join([
            f"# {qid} -- Tool History (batch {batch})",
            f"",
            f"**Prompt:** {prompt_record['prompt']}",
            f"",
            f"---",
            f"",
        ])
        self._fp.write_text(header, encoding="utf-8")

        ref_header = "\n".join([
            f"# {qid} -- Referenced Entity IDs (batch {batch})",
            f"",
            f"**Prompt:** {prompt_record['prompt']}",
            f"",
            f"---",
            f"",
        ])
        self._ref_fp.write_text(ref_header, encoding="utf-8")

    def on_step(self, event: dict) -> None:
        """Callback invoked after each agent iteration with new tool steps."""
        tool_history = event.get("tool_history", [])
        compactor_events = event.get("compactor_events", [])
        iteration = event.get("iteration", 0)
        elapsed = event.get("elapsed", 0.0)

        new_steps = tool_history[self._step_count:]
        self._all_compactor_events.extend(compactor_events)

        lines: list[str] = []
        ref_lines: list[str] = []
        for step in new_steps:
            self._step_count += 1
            stats = _extract_result_stats(step.get("result_full", ""))
            step["result_stats"] = stats
            lines.extend(self._format_step(self._step_count, step, compactor_events))
            ref_section = _extract_step_ref_ids(self._step_count, step)
            if ref_section:
                ref_lines.append(ref_section)

        if elapsed:
            lines.append(f"*[{elapsed:.0f}s elapsed]*")
            lines.append("")

        if lines:
            with open(self._fp, "a", encoding="utf-8") as f:
                f.write("\n".join(lines))
        if ref_lines:
            with open(self._ref_fp, "a", encoding="utf-8") as f:
                f.write("\n".join(ref_lines))

    def _format_step(self, step_num: int, step: dict,
                     comp_events: list[dict]) -> list[str]:
        """Format a single step block — same format as write_single_history."""
        lines: list[str] = []
        args_str = json.dumps(step["arguments"], ensure_ascii=False, indent=2)
        display_data = step.get("display_result",
                                step.get("memory_result",
                                         step.get("result_full", "")))
        raw_data = step.get("result_full", "")

        parallel_tag = ""
        if step.get("parallel"):
            group_size = step.get("parallel_group", "?")
            parallel_tag = f"  *(parallel {group_size}x)*"
        error_tag = "  **[ERROR]**" if step.get("is_error") else ""
        duration = step.get("duration_s")
        elapsed = step.get("elapsed_at")
        timing_tag = ""
        if duration is not None:
            timing_tag = f"  *[{duration:.1f}s"
            if elapsed is not None:
                timing_tag += f" @ {elapsed:.0f}s"
            timing_tag += "]*"
        lines.append(f"**Step {step_num}:** `{step['tool']}`{parallel_tag}{error_tag}{timing_tag}")
        lines.append(f"  - Args:")
        lines.append(f"    ```json")
        for arg_line in args_str.splitlines():
            lines.append(f"    {arg_line}")
        lines.append(f"    ```")
        if step.get("is_error"):
            lines.append(f"  - **Error:** {display_data.strip()}")
        lines.append(
            f"  - Agent-facing result: "
            f"{step.get('display_result_chars', len(display_data))} chars"
        )
        if step.get("immediate_compacted"):
            compaction_kind = step.get("compaction_kind") or "immediate"
            lines.append(
                f"  - Agent memory: immediate {compaction_kind} compaction applied"
            )
        lines.append("")

        lines.append("  <details><summary>Agent-facing result</summary>")
        lines.append("")
        lines.append(display_data)
        lines.append("")
        lines.append("  </details>")
        lines.append("")
        if self._verbose_history and raw_data and raw_data != display_data:
            lines.append("  <details><summary>Raw tool output (debug)</summary>")
            lines.append("")
            lines.append("  ```json")
            lines.append(raw_data)
            lines.append("  ```")
            lines.append("")
            lines.append("  </details>")
            lines.append("")

        stats = step.get("result_stats", {})
        if stats:
            is_trunc = stats.get("truncated", False)
            tag = " *(from visible head+tail)*" if is_trunc else ""
            lines.append(f"  - **Result stats{tag}:**")
            if "type" in stats and stats["type"] == "object":
                lines.append(
                    f"    - Type: single object, keys: "
                    f"{stats.get('top_keys', [])}"
                )
                for sk in ("card", "equilibrium_networks", "citations"):
                    if f"{sk}_count" in stats:
                        lines.append(f"    - `{sk}`: {stats[f'{sk}_count']} items")
                    elif f"{sk}_keys" in stats:
                        lines.append(f"    - `{sk}`: keys={stats[f'{sk}_keys']}")
            elif "row_count" in stats or "visible_rows" in stats:
                row_label = stats.get("row_count", stats.get("visible_rows", "?"))
                lines.append(
                    f"    - Rows: **{row_label}**"
                    f"{'  (visible only)' if is_trunc else ''}"
                )
                for id_fld in ("vlm_id", "example_vlm_id", "metal_id",
                               "ligand_id", "network_id", "node_id",
                               "collection_id"):
                    count_key = id_fld + "_count"
                    list_key = id_fld + "s"
                    if count_key in stats:
                        ids_str = ", ".join(str(x) for x in stats[list_key])
                        lines.append(
                            f"    - `{id_fld}`: {stats[count_key]} unique "
                            f"— [{ids_str}]"
                        )
                for name_fld in ("unique_metal_names", "unique_ligand_names",
                                 "unique_ligand_classs"):
                    if name_fld in stats:
                        lines.append(f"    - {name_fld}: {stats[name_fld]}")
                if "log_K_range" in stats:
                    lo, hi = stats["log_K_range"]
                    lines.append(
                        f"    - log_K: {stats['log_K_count']} values, "
                        f"range [{lo}, {hi}]"
                    )
        lines.append("")

        iteration = step.get("iteration")
        tool_name = step.get("tool")
        step_events = [
            e for e in comp_events
            if e.get("after_iteration") == iteration
            and e.get("for_tool") == tool_name
        ]
        if step_events:
            lines.append(
                f"  - **Compactor events** (iter {iteration}, `{tool_name}`):"
            )
            for ev in step_events:
                lines.append(f"    - [{ev['level']}] {ev['message']}")
            lines.append("")

        return lines

    def finalize(self, result: dict) -> Path:
        """Append compactor summary + footer, return file path."""
        lines: list[str] = []
        compactor_events = result.get("compactor_events") or self._all_compactor_events

        if self._step_count == 0:
            lines.append("*No tool calls -- answered directly.*")
            lines.append("")

        _append_compactor_summary(lines, compactor_events)

        # ── Error summary ──
        error_steps = [
            (i + 1, s) for i, s in enumerate(result.get("tool_history", []))
            if s.get("is_error")
        ]
        if error_steps:
            lines.append("")
            lines.append("---")
            lines.append("")
            lines.append(f"### Tool Errors ({len(error_steps)})")
            lines.append("")
            for step_num, s in error_steps:
                err_msg = s.get("result_full", s.get("display_result", ""))
                lines.append(
                    f"- **Step {step_num}** `{s['tool']}` "
                    f"(iter {s.get('iteration', '?')}):"
                )
                lines.append(f"  ```")
                lines.append(f"  {err_msg.strip()}")
                lines.append(f"  ```")
            lines.append("")

        # ── Tool call summary table ──
        tool_history = result.get("tool_history", [])
        if tool_history:
            tool_stats: dict[str, dict] = collections.defaultdict(
                lambda: {"calls": 0, "total_s": 0.0, "parallel_with": collections.Counter()}
            )

            # Group parallel batches by shared elapsed_at
            i = 0
            while i < len(tool_history):
                s = tool_history[i]
                dur = s.get("duration_s", 0.0) or 0.0
                tname = s["tool"]
                tool_stats[tname]["calls"] += 1
                tool_stats[tname]["total_s"] += dur

                if s.get("parallel"):
                    batch = [s]
                    ea = s.get("elapsed_at")
                    j = i + 1
                    while j < len(tool_history) and tool_history[j].get("parallel") and tool_history[j].get("elapsed_at") == ea:
                        batch.append(tool_history[j])
                        d2 = tool_history[j].get("duration_s", 0.0) or 0.0
                        t2 = tool_history[j]["tool"]
                        tool_stats[t2]["calls"] += 1
                        tool_stats[t2]["total_s"] += d2
                        j += 1
                    batch_names = [b["tool"] for b in batch]
                    for b in batch:
                        for other in batch_names:
                            if other != b["tool"]:
                                tool_stats[b["tool"]]["parallel_with"][other] += 1
                    i = j
                else:
                    i += 1

            lines.append("")
            lines.append("---")
            lines.append("")
            lines.append(f"### Tool Call Summary")
            lines.append("")
            lines.append("| Tool | Calls | Total (s) | Avg (s) | Parallel with |")
            lines.append("|------|------:|----------:|--------:|---------------|")
            for tname in sorted(tool_stats, key=lambda t: tool_stats[t]["total_s"], reverse=True):
                ts = tool_stats[tname]
                avg = ts["total_s"] / ts["calls"] if ts["calls"] else 0
                par_parts = []
                for other, cnt in ts["parallel_with"].most_common():
                    par_parts.append(f"{other} ({cnt}x)")
                par_str = ", ".join(par_parts) if par_parts else "—"
                lines.append(
                    f"| `{tname}` | {ts['calls']} "
                    f"| {ts['total_s']:.1f} | {avg:.1f} | {par_str} |"
                )
            lines.append("")

        lines.append(
            f"**Total calls:** {result['tool_count']}  |  "
            f"**Elapsed:** {result['elapsed']:.1f} s"
        )
        lines.append("")

        with open(self._fp, "a", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return self._fp


# -- Combined summary writer -----------------------------------------

def write_summary_md(results: List[dict], path: Path, *, model: str = "", batch: int = 1):
    """Write a combined summary table + links to per-prompt files."""
    lines = [
        f"# Test Run Summary -- {model} (batch {batch})",
        f"",
        f"*Generated {dt.datetime.now():%Y-%m-%d %H:%M:%S}*",
        f"",
        f"| # | Prompt | Tools | Time (s) | Result | History |",
        f"|---|--------|------:|--------:|--------|---------|",
    ]
    for r in results:
        qid = _qid(r["id"])
        prompt_short = r["prompt"][:60] + ("..." if len(r["prompt"]) > 60 else "")
        status = "ERROR" if r["answer"].startswith("**ERROR") else "OK"
        lines.append(
            f"| {r['id']} | {prompt_short} | {r['tool_count']} | "
            f"{r['elapsed']:.1f} | {status} [{qid}]({qid}/{qid}_result_batch{batch}.md) | "
            f"[history]({qid}/{qid}_history_batch{batch}.md) |"
        )
    lines.append("")

    total_calls = sum(r["tool_count"] for r in results)
    total_time  = sum(r["elapsed"]    for r in results)
    total_comp  = sum(len(r.get("compactor_events", [])) for r in results)
    lines.append(f"**Totals:** {len(results)} prompts  |  "
                  f"{total_calls} tool calls  |  {total_time:.0f} s  |  "
                  f"{total_comp} compactor events")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    log.info("[F] Wrote %s (%d prompts)", path.name, len(results))


# ===============================================================
#  4. Prompt workers
# ===============================================================

def _write_incremental_outputs(result: dict, *, history_writer: Optional[_StreamingHistoryWriter] = None) -> None:
    """Persist a single prompt result immediately after completion."""
    CURRENT_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    rfp = write_single_result(result, CURRENT_MODEL_DIR, batch=CURRENT_BATCH)
    if history_writer:
        hfp = history_writer.finalize(result)
    else:
        hfp = write_single_history(result, CURRENT_MODEL_DIR, batch=CURRENT_BATCH,
                                   verbose_history=VERBOSE_HISTORY)
    log.info("[F] Wrote %s  &  %s", rfp.name, hfp.name)


def _run_single_prompt(prompt_record: dict, index: int, total: int) -> dict:
    """Run one prompt end-to-end inside a worker thread."""
    prompt_id = prompt_record["id"]
    _set_worker_prompt_id(prompt_id)
    try:
        log.info("=" * 60)
        log.info(">> [%d/%d]  Prompt %s: %s",
                 index, total, prompt_id, prompt_record["prompt"][:80])
        log.info("=" * 60)

        CURRENT_MODEL_DIR.mkdir(parents=True, exist_ok=True)
        history_writer = _StreamingHistoryWriter(
            prompt_record, CURRENT_MODEL_DIR,
            batch=CURRENT_BATCH, verbose_history=VERBOSE_HISTORY,
        )

        t0 = time.time()
        try:
            api_result = run_agent_query_sync(
                prompt_record["prompt"],
                on_step=history_writer.on_step,
            )
            answer = api_result.answer
            memory = api_result.memory
            comp_events = api_result.compactor_events
            tool_history = api_result.tool_history
            for step in tool_history:
                if "result_stats" not in step:
                    step["result_stats"] = _extract_result_stats(
                        step.get("result_full", "")
                    )
            elapsed = api_result.elapsed
        except Exception as e:
            log.exception("[X] Prompt %s failed", prompt_id)
            answer = f"**ERROR:** {e}"
            tool_history = []
            comp_events = []
            memory = []
            elapsed = time.time() - t0

        verdict_t0 = time.time()
        try:
            verdict = _run_verdict_agent(
                prompt_record["prompt"], memory, answer,
                call_argo=call_argo,
                extract_tool_call=extract_tool_call,
                verdict_model=argo_config.VERDICT_MODEL,
                tool_history=tool_history,
            )
        except Exception as e:
            log.warning("[V] Verdict failed for %s: %s", prompt_id, e)
            verdict = f"(Verdict unavailable: {e})"
        verdict_elapsed = time.time() - verdict_t0
        log.info("[V] Verdict for %s (%.1fs): %s", prompt_id, verdict_elapsed, verdict[:120])

        result = {
            **prompt_record,
            "answer":            answer,
            "verdict":           verdict,
            "tool_history":      tool_history,
            "tool_count":        len(tool_history),
            "elapsed":           elapsed,
            "verdict_elapsed":   verdict_elapsed,
            "compactor_events":  comp_events,
            "_history_writer":   history_writer,
        }
        log.info("[OK] Prompt %s done -- %d tool calls, %.1f s",
                 prompt_id, len(tool_history), elapsed)
        return result
    finally:
        _set_worker_prompt_id(None)


def _run_prompts(prompts: List[dict], parallel_workers: int) -> List[dict]:
    """Run prompts sequentially or in parallel and preserve input order."""
    if parallel_workers <= 1:
        results = []
        for i, prompt_record in enumerate(prompts, 1):
            result = _run_single_prompt(prompt_record, i, len(prompts))
            results.append(result)
            hw = result.pop("_history_writer", None)
            _write_incremental_outputs(result, history_writer=hw)
        return results

    ordered_results: Dict[str, dict] = {}
    with ThreadPoolExecutor(
        max_workers=parallel_workers,
        thread_name_prefix="srd46-test",
    ) as executor:
        future_map = {
            executor.submit(_run_single_prompt, prompt_record, i, len(prompts)): prompt_record
            for i, prompt_record in enumerate(prompts, 1)
        }

        completed = 0
        for future in as_completed(future_map):
            prompt_record = future_map[future]
            prompt_id = prompt_record["id"]
            try:
                result = future.result()
            except Exception as e:
                log.exception("[X] Worker crashed for prompt %s", prompt_id)
                result = {
                    **prompt_record,
                    "answer": f"**ERROR:** worker crashed: {e}",
                    "verdict": f"(Verdict unavailable: worker crashed: {e})",
                    "tool_history": [],
                    "tool_count": 0,
                    "elapsed": 0.0,
                    "compactor_events": [],
                }

            ordered_results[prompt_id] = result
            completed += 1
            log.info("[i] Completed %d/%d prompts", completed, len(prompts))
            hw = result.pop("_history_writer", None)
            _write_incremental_outputs(result, history_writer=hw)

    return [ordered_results[p["id"]] for p in prompts]


# ===============================================================
#  5. Main
# ===============================================================

def main():
    parser = argparse.ArgumentParser(description="Run SRD-46 test prompts")
    parser.add_argument("ids", nargs="*",
                        help="Specific prompt IDs to run (e.g. 1.1.1 2.1.3)")
    parser.add_argument("--section", "-s", type=str, default=None,
                        help="Run all prompts in a section (e.g. 3 matches 3.1, 3.2)")
    parser.add_argument("--md", default=str(PROJECT_ROOT / "TEST_PROMPTS.md"),
                        help="Path to the test prompts markdown file")
    parser.add_argument("--parallel", "-j", type=int, default=1,
                        help="Number of prompt workers to run in parallel")
    parser.add_argument("--models", "-m", nargs="+", default=None,
                        help="Model names to test (e.g. gpt5 claudeopus46). "
                             "Default: current MODEL from argo_config")
    parser.add_argument("--repeats", "-r", type=int, default=1,
                        help="Number of repeat batches per model (default: 1)")
    parser.add_argument("--argo-min-interval", type=float, default=2.0,
                        help="Shared minimum spacing between Argo requests "
                             "across all workers (seconds)")
    parser.add_argument("--argo-max-inflight", type=int, default=4,
                        help="Shared maximum number of concurrent Argo "
                             "requests across all workers")
    parser.add_argument("--argo-cooldown", type=float, default=15.0,
                        help="Extra shared cooldown after Argo failures or "
                             "rate-limit responses (seconds)")
    parser.add_argument("--verbose-history", action="store_true", default=False,
                        help="Include full tool result data in history files")
    args = parser.parse_args()

    global VERBOSE_HISTORY, CURRENT_MODEL_DIR, CURRENT_BATCH
    VERBOSE_HISTORY = args.verbose_history

    # Parse prompts
    all_prompts = parse_prompts(Path(args.md))
    log.info("[i] Parsed %d prompts from %s", len(all_prompts), args.md)

    # Filter
    if args.ids:
        prompts = [p for p in all_prompts if p["id"] in args.ids]
    elif args.section:
        sec = args.section
        prompts = [p for p in all_prompts
                   if p["section"] == sec or p["section"].startswith(sec + ".")]
    else:
        prompts = all_prompts

    if not prompts:
        log.error("No prompts matched the filter.")
        sys.exit(1)

    if args.parallel < 1:
        log.error("--parallel must be >= 1")
        sys.exit(1)
    if args.argo_max_inflight < 1:
        log.error("--argo-max-inflight must be >= 1")
        sys.exit(1)

    for order, prompt_record in enumerate(prompts):
        prompt_record["_order"] = order

    models = args.models or [argo_config.MODEL]
    repeats = args.repeats

    log.info(">> Running %d prompt(s): %s",
             len(prompts), ", ".join(p["id"] for p in prompts))
    log.info(">> Models: %s  |  Repeats: %d", ", ".join(models), repeats)
    log.info("[ARGO-GATE] config: parallel=%d min_interval=%.2fs max_inflight=%d cooldown=%.2fs",
             args.parallel, args.argo_min_interval,
             args.argo_max_inflight, args.argo_cooldown)

    _install_argo_gate(
        SharedArgoGate(
            min_interval_s=args.argo_min_interval,
            max_inflight=args.argo_max_inflight,
            cooldown_s=args.argo_cooldown,
        )
    )

    # ── Outer loop: batches × models (all models finish batch N before N+1) ──
    grand_total_calls = 0
    grand_total_time = 0.0

    for batch in range(1, repeats + 1):
        for model_name in models:
            argo_config.MODEL = model_name
            argo_config.PLANNER_MODEL = model_name
            argo_config.VERDICT_MODEL = model_name

            model_dir = OUTPUT_DIR / f"Model_{model_name}"
            model_dir.mkdir(parents=True, exist_ok=True)

            CURRENT_MODEL_DIR = model_dir
            CURRENT_BATCH = batch

            log.info("=" * 60)
            log.info("  BATCH: %d/%d  |  MODEL: %s", batch, repeats, model_name)
            log.info("=" * 60)

            results = _run_prompts(prompts, args.parallel)

            write_summary_md(results, model_dir / f"SUMMARY_batch{batch}.md",
                             model=model_name, batch=batch)

            batch_calls = sum(r["tool_count"] for r in results)
            batch_time = sum(r["elapsed"] for r in results)
            grand_total_calls += batch_calls
            grand_total_time += batch_time

            log.info("[i] Batch %d/%d for %s done: %d calls, %.0f s",
                     batch, repeats, model_name, batch_calls, batch_time)

    # ── Grand summary ──
    gate_stats = _ARGO_GATE.snapshot() if _ARGO_GATE is not None else {}
    log.info("-" * 60)
    log.info("  ALL DONE  --  %d model(s) × %d batch(es) × %d prompt(s)",
             len(models), repeats, len(prompts))
    log.info("  Grand totals: %d tool calls  |  %.0f s",
             grand_total_calls, grand_total_time)
    if gate_stats:
        log.info("  Argo gate => started=%s finished=%s queued=%s cooldowns=%s",
                 gate_stats.get("started", 0),
                 gate_stats.get("finished", 0),
                 gate_stats.get("queued", 0),
                 gate_stats.get("cooldowns", 0))
    log.info("  Output => %s", OUTPUT_DIR)
    log.info("-" * 60)


if __name__ == "__main__":
    main()
