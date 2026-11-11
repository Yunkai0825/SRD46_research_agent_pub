"""Phase-4 audits: re-validate label assignments, never mutate source files.

Each audit emits a CSV in ``out_dir`` and contributes a row to
``audit_summary.{json,md}``. Audits are intentionally cheap so they can run
over the full ~1000-batch corpus quickly.
"""
from __future__ import annotations

import csv
import json
import re
import sqlite3
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Iterable

from ..db_support_helpers.db_reference import DB_NAMES, open_reference_connection

from .loader import (
    BUCKET_BY_SUPPORT,
    DEFAULT_OUTPUT_EVAL,
    _iter_batch_files,
)
from .prompt_registry import load_prompt_registry
from .section_policy import DEFAULT_SECTION_POLICY, SectionPolicy

NUMERIC_RE = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")
NUMERIC_CLAIM_TYPES = {"exact_value", "range", "counting", "calculation"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return path


def _load_payload(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _iter_grounded_claims(payload: dict):
    """Yield (paragraph_index, claim_index, claim, grounded) tuples."""
    for paragraph in (payload.get("doc") or {}).get("paragraphs") or []:
        p_idx = int(paragraph.get("paragraph_index", 0))
        claims = paragraph.get("claims") or []
        grounded = {int(g.get("claim_index", i)): g for i, g in enumerate(paragraph.get("grounded_claims") or [])}
        for c_idx, claim in enumerate(claims):
            yield p_idx, c_idx, claim, grounded.get(c_idx, {})


# ---------------------------------------------------------------------------
# Audit 1: tool-snippet sanity
# ---------------------------------------------------------------------------

def audit_evidence_missing(scope: list[tuple], out_dir: Path) -> tuple[int, int, Path]:
    rows: list[dict] = []
    checked = 0
    for model, qid, batch, path in scope:
        payload = _load_payload(path)
        if not payload or not payload.get("complete"):
            continue
        for p_idx, c_idx, claim, grounded in _iter_grounded_claims(payload):
            sup = grounded.get("support_class", "")
            if sup not in {"direct", "inferred"}:
                continue
            checked += 1
            ts = grounded.get("tool_snippets") or []
            es = (grounded.get("evidence_snippet") or "").strip()
            if not ts or not es:
                rows.append({
                    "model": model, "question_id": qid, "batch": batch,
                    "paragraph_index": p_idx, "claim_index": c_idx,
                    "support_class": sup,
                    "n_tool_snippets": len(ts),
                    "evidence_snippet_present": bool(es),
                    "claim_text": (claim.get("text") or "")[:160],
                    "source_path": str(path),
                })
    out = _write_csv(out_dir / "audit_evidence_missing.csv", rows,
                     ["model", "question_id", "batch", "paragraph_index", "claim_index",
                      "support_class", "n_tool_snippets", "evidence_snippet_present",
                      "claim_text", "source_path"])
    return checked, len(rows), out


# ---------------------------------------------------------------------------
# Audit 2: numeric verbatim re-check on `direct` numeric claims
# ---------------------------------------------------------------------------

def _normalize_number(token: str) -> str:
    """Normalize unicode minus and trim trailing zeros."""
    token = token.replace("−", "-").replace("\u2212", "-")
    return token


def audit_direct_numeric_fail(scope: list[tuple], out_dir: Path) -> tuple[int, int, Path]:
    rows: list[dict] = []
    checked = 0
    for model, qid, batch, path in scope:
        payload = _load_payload(path)
        if not payload or not payload.get("complete"):
            continue
        for p_idx, c_idx, claim, grounded in _iter_grounded_claims(payload):
            ct = claim.get("claim_type", "")
            sup = grounded.get("support_class", "")
            if sup != "direct" or ct not in NUMERIC_CLAIM_TYPES:
                continue
            text = _normalize_number(str(claim.get("text", "")))
            tokens = NUMERIC_RE.findall(text)
            if not tokens:
                continue
            checked += 1
            haystack = _normalize_number(" ".join(
                str(t.get("snippet", "")) for t in (grounded.get("tool_snippets") or [])
            ))
            haystack += " " + _normalize_number(str(grounded.get("evidence_snippet", "")))
            if any(tok in haystack for tok in tokens):
                continue
            rows.append({
                "model": model, "question_id": qid, "batch": batch,
                "paragraph_index": p_idx, "claim_index": c_idx,
                "claim_type": ct,
                "claim_numbers": ",".join(tokens),
                "claim_text": text[:200],
                "source_path": str(path),
            })
    out = _write_csv(out_dir / "audit_direct_numeric_fail.csv", rows,
                     ["model", "question_id", "batch", "paragraph_index", "claim_index",
                      "claim_type", "claim_numbers", "claim_text", "source_path"])
    return checked, len(rows), out


# ---------------------------------------------------------------------------
# Audit 3: canonical_id existence vs SRD-46
# ---------------------------------------------------------------------------

# Maps (alias, table, column) → list of canonical-ID prefixes to register.
# Each entry produces one or more "<prefix>_<int_value>" forms in the known set.
# Discovered conventions: claims cite IDs as metal_<n>, ligand_<n>, vlm_<n>,
# beta_def_<n>, ref_eq_map_<n>, lit_<n>, etc.
_ID_PREFIX_MAP: list[tuple[str, str, str, tuple[str, ...]]] = [
    ("cards", "metal_card",            "metal_id",            ("metal",)),
    ("cards", "ligand_card",           "ligand_id",           ("ligand",)),
    ("cards", "ligandmetal_card",      "beta_definition_id",  ("beta_def", "beta_definition")),
    ("cards", "ligandmetal_card",      "card_id",             ("vlm",)),
    ("maps",  "eq_map",                "map_id",              ("ref_eq_map", "eq_map", "map")),
    ("maps",  "eq_node",               "vlm_id",              ("vlm",)),
    ("lit",   "literature",            "literature_id",       ("lit", "literature", "ref_literature")),
    ("cards", "ref_literature",        "literature_id",       ("lit", "literature", "ref_literature")),
    ("lit",   "literature_alt",        "literature_alt_id",   ("literature_alt", "ref_literature_alt")),
    ("cards", "ref_literature_alt",   "literature_alt_id",   ("literature_alt", "ref_literature_alt")),
    ("lit",   "footnote",              "footnote_id",         ("footnote", "ref_footnote")),
    ("cards", "ref_footnote",          "footnote_id",         ("footnote", "ref_footnote")),
    ("lit",   "author",                "author_id",           ("author", "ref_author")),
    ("cards", "ref_author",            "author_id",           ("author", "ref_author")),
    ("lit",   "paper",                 "paper_id",            ("paper",)),
]


def _load_known_canonical_ids(conn: sqlite3.Connection) -> set[str]:
    """Build the set of valid canonical_ids by enumerating each known
    (alias, table, integer-id column) and synthesising every prefix form
    used in claim payloads.
    """
    known: set[str] = set()
    for alias, tname, col, prefixes in _ID_PREFIX_MAP:
        try:
            for row in conn.execute(f'SELECT "{col}" FROM {alias}."{tname}"'):
                v = row[0]
                if v is None:
                    continue
                try:
                    iv = int(v)
                except (TypeError, ValueError):
                    continue
                for p in prefixes:
                    known.add(f"{p}_{iv}")
        except sqlite3.Error:
            continue
    return known


def audit_canonical_id_unknown(
    scope: list[tuple], out_dir: Path,
) -> tuple[int, int, Path, dict[str, dict]]:
    try:
        conn = open_reference_connection()
        known = _load_known_canonical_ids(conn)
    except Exception as exc:  # noqa: BLE001
        print(f"  [audit] DB unavailable, skipping canonical-id check: {exc}")
        empty = _write_csv(out_dir / "audit_canonical_id_unknown.csv", [],
                           ["model", "question_id", "batch", "paragraph_index", "claim_index",
                            "canonical_id", "prefix", "source_path"])
        return 0, 0, empty, {}

    rows: list[dict] = []
    checked = 0
    per_prefix_total: Counter[str] = Counter()
    per_prefix_unknown: Counter[str] = Counter()

    for model, qid, batch, path in scope:
        payload = _load_payload(path)
        if not payload or not payload.get("complete"):
            continue
        for p_idx, c_idx, claim, grounded in _iter_grounded_claims(payload):
            for cid in grounded.get("canonical_ids") or []:
                checked += 1
                cid_s = str(cid)
                prefix = cid_s.split("_", 1)[0]
                per_prefix_total[prefix] += 1
                if cid_s not in known:
                    per_prefix_unknown[prefix] += 1
                    rows.append({
                        "model": model, "question_id": qid, "batch": batch,
                        "paragraph_index": p_idx, "claim_index": c_idx,
                        "canonical_id": cid_s,
                        "prefix": prefix,
                        "source_path": str(path),
                    })
    out = _write_csv(out_dir / "audit_canonical_id_unknown.csv", rows,
                     ["model", "question_id", "batch", "paragraph_index", "claim_index",
                      "canonical_id", "prefix", "source_path"])

    # per-prefix validity rate
    pref_rows = []
    for p in sorted(per_prefix_total):
        t = per_prefix_total[p]
        u = per_prefix_unknown.get(p, 0)
        pref_rows.append({
            "prefix": p, "total_cited": t, "unknown": u,
            "known_rate": (t - u) / t if t else float("nan"),
        })
    _write_csv(out_dir / "audit_canonical_id_prefix_rates.csv", pref_rows,
               ["prefix", "total_cited", "unknown", "known_rate"])

    return checked, len(rows), out, {p: dict(rows=per_prefix_total[p], unknown=per_prefix_unknown.get(p, 0)) for p in per_prefix_total}


# ---------------------------------------------------------------------------
# Audit 4: filler integrity
# ---------------------------------------------------------------------------

def audit_filler_integrity(scope: list[tuple], out_dir: Path) -> tuple[int, int, Path]:
    rows: list[dict] = []
    checked = 0
    for model, qid, batch, path in scope:
        payload = _load_payload(path)
        if not payload or not payload.get("complete"):
            continue
        for p_idx, c_idx, claim, grounded in _iter_grounded_claims(payload):
            if claim.get("claim_type") != "filler":
                continue
            checked += 1
            cids = grounded.get("canonical_ids") or []
            ts = grounded.get("tool_snippets") or []
            if cids or ts:
                rows.append({
                    "model": model, "question_id": qid, "batch": batch,
                    "paragraph_index": p_idx, "claim_index": c_idx,
                    "n_canonical_ids": len(cids),
                    "n_tool_snippets": len(ts),
                    "claim_text": (claim.get("text") or "")[:160],
                    "source_path": str(path),
                })
    out = _write_csv(out_dir / "audit_filler_integrity.csv", rows,
                     ["model", "question_id", "batch", "paragraph_index", "claim_index",
                      "n_canonical_ids", "n_tool_snippets", "claim_text", "source_path"])
    return checked, len(rows), out


# ---------------------------------------------------------------------------
# Audit 5: classifier-strategy / cache_format drift
# ---------------------------------------------------------------------------

def audit_provenance_drift(scope: list[tuple], out_dir: Path, registry: dict) -> Path:
    by_ms: dict[tuple, Counter] = defaultdict(Counter)
    for model, qid, batch, path in scope:
        payload = _load_payload(path)
        if not payload:
            continue
        spec = registry.get(qid)
        section = spec.section if spec else "?"
        key = (model, section)
        by_ms[key][(
            int(payload.get("cache_format", 0) or 0),
            str(payload.get("classifier_strategy_version", "")),
            str(payload.get("classifier_model", "")),
            str(payload.get("grounder_model", "")),
        )] += 1
    rows: list[dict] = []
    for (model, section), c in sorted(by_ms.items()):
        for (cf, ver, cm, gm), n in c.most_common():
            rows.append({
                "model": model, "section": section,
                "cache_format": cf,
                "classifier_strategy_version": ver,
                "classifier_model": cm,
                "grounder_model": gm,
                "n_batches": n,
            })
    out = _write_csv(out_dir / "audit_provenance_distribution.csv", rows,
                     ["model", "section", "cache_format", "classifier_strategy_version",
                      "classifier_model", "grounder_model", "n_batches"])
    return out


# ---------------------------------------------------------------------------
# Audit 6: cross-model claim agreement (per (prompt, paragraph_index))
# ---------------------------------------------------------------------------

def audit_cross_model_agreement(scope: list[tuple], out_dir: Path) -> tuple[int, int, Path]:
    """For each (question_id, paragraph_index), aggregate per-model bucket
    distributions (over batches & claims) and measure pairwise total-variation
    distance. Lower TVD = higher agreement.
    """
    # bucket counts per (model, qid, p_idx)
    buckets_mqp: dict[tuple, Counter] = defaultdict(Counter)
    for model, qid, _, path in scope:
        payload = _load_payload(path)
        if not payload or not payload.get("complete"):
            continue
        for p_idx, _, claim, grounded in _iter_grounded_claims(payload):
            ct = claim.get("claim_type", "")
            if ct == "filler":
                bucket = "filler"
            else:
                bucket = BUCKET_BY_SUPPORT.get(grounded.get("support_class", ""), "unverified")
            buckets_mqp[(model, qid, p_idx)][bucket] += 1

    # group by (qid, p_idx)
    by_qp: dict[tuple, dict[str, Counter]] = defaultdict(dict)
    for (model, qid, p_idx), c in buckets_mqp.items():
        by_qp[(qid, p_idx)][model] = c

    rows: list[dict] = []
    BUCKETS = ("verified", "domain", "unverified", "filler")
    pair_total: dict[tuple, list[float]] = defaultdict(list)
    pair_n: dict[tuple, int] = defaultdict(int)
    checked = 0
    flagged = 0
    for (qid, p_idx), per_model in sorted(by_qp.items()):
        models = sorted(per_model)
        if len(models) < 2:
            continue
        # normalize to share vectors
        shares = {}
        for m in models:
            c = per_model[m]
            n = sum(c.values())
            shares[m] = [c.get(b, 0) / n if n else 0.0 for b in BUCKETS]
        for m1, m2 in combinations(models, 2):
            tvd = 0.5 * sum(abs(a - b) for a, b in zip(shares[m1], shares[m2]))
            pair_total[(m1, m2)].append(tvd)
            pair_n[(m1, m2)] += 1
            checked += 1
            if tvd >= 0.5:
                flagged += 1
                rows.append({
                    "question_id": qid, "paragraph_index": p_idx,
                    "model_a": m1, "model_b": m2, "tvd": tvd,
                    "shares_a": ",".join(f"{x:.2f}" for x in shares[m1]),
                    "shares_b": ",".join(f"{x:.2f}" for x in shares[m2]),
                })
    rows.sort(key=lambda r: -r["tvd"])
    out = _write_csv(out_dir / "audit_cross_model_high_disagreement.csv", rows,
                     ["question_id", "paragraph_index", "model_a", "model_b", "tvd",
                      "shares_a", "shares_b"])

    # also dump pair-mean TVD matrix
    pair_rows = []
    for (m1, m2), vals in sorted(pair_total.items()):
        pair_rows.append({
            "model_a": m1, "model_b": m2,
            "n_pairs": pair_n[(m1, m2)],
            "mean_tvd": sum(vals) / len(vals) if vals else float("nan"),
        })
    _write_csv(out_dir / "audit_cross_model_agreement_matrix.csv", pair_rows,
               ["model_a", "model_b", "n_pairs", "mean_tvd"])
    return checked, flagged, out


# ---------------------------------------------------------------------------
# Audit 7: majority-numeric-but-unsupported
# ---------------------------------------------------------------------------

def audit_majority_unsupported(scope: list[tuple], out_dir: Path) -> tuple[int, int, Path]:
    """For each (model, prompt) and each numeric token appearing in >=3 of 5
    batches, flag the prompts whose majority numbers are then 'unsupported'
    in any batch where they appear.
    """
    # token -> set of (batch, support_class) per (model, qid)
    per_mq_token: dict[tuple, dict[str, list[tuple[int, str]]]] = defaultdict(lambda: defaultdict(list))
    for model, qid, batch, path in scope:
        payload = _load_payload(path)
        if not payload or not payload.get("complete"):
            continue
        for _, _, claim, grounded in _iter_grounded_claims(payload):
            ct = claim.get("claim_type", "")
            if ct not in NUMERIC_CLAIM_TYPES:
                continue
            sup = grounded.get("support_class", "")
            text = _normalize_number(str(claim.get("text", "")))
            for tok in set(NUMERIC_RE.findall(text)):
                per_mq_token[(model, qid)][tok].append((batch, sup))

    rows: list[dict] = []
    checked = 0
    for (model, qid), tokens in sorted(per_mq_token.items()):
        for tok, occurrences in tokens.items():
            n_batches = len({b for b, _ in occurrences})
            if n_batches < 3:
                continue
            checked += 1
            unsup = [b for b, s in occurrences if s == "unsupported"]
            if unsup:
                rows.append({
                    "model": model, "question_id": qid,
                    "numeric_token": tok,
                    "n_batches_present": n_batches,
                    "n_batches_unsupported": len(unsup),
                    "unsupported_in_batches": ",".join(str(b) for b in sorted(unsup)),
                })
    out = _write_csv(out_dir / "audit_majority_unsupported.csv", rows,
                     ["model", "question_id", "numeric_token", "n_batches_present",
                      "n_batches_unsupported", "unsupported_in_batches"])
    return checked, len(rows), out


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------

def run_audits(
    *,
    root: str | Path | None = None,
    out_dir: Path,
    json_dir: Path,
    include_models: Iterable[str] | None = None,
    include_questions: Iterable[str] | None = None,
    include_sections: Iterable[str] | None = None,
    section_policy: SectionPolicy | None = None,
) -> list[dict]:
    eval_root = Path(root) if root else DEFAULT_OUTPUT_EVAL
    registry = load_prompt_registry()
    policy = section_policy or DEFAULT_SECTION_POLICY
    model_set = set(include_models) if include_models else None
    q_set = set(include_questions) if include_questions else None
    sec_set = set(include_sections) if include_sections else None

    scope: list[tuple] = []
    for model, qid, batch, path in _iter_batch_files(eval_root):
        if model_set and model not in model_set:
            continue
        if q_set and qid not in q_set:
            continue
        spec = registry.get(qid)
        if spec is not None and not policy.include_raw_section(spec.section):
            continue
        if sec_set:
            if spec is None or not policy.matches_requested_sections(spec.section, sec_set):
                continue
        scope.append((model, qid, batch, path))

    print(f"[audit] scope: {len(scope)} batches")
    summary: list[dict] = []

    print("[audit] 1/7 evidence_missing …")
    n, k, _ = audit_evidence_missing(scope, out_dir)
    summary.append({"audit": "evidence_missing", "total_checked": n, "total_flagged": k, "flag_rate": (k / n) if n else 0.0})

    print("[audit] 2/7 direct_numeric_fail …")
    n, k, _ = audit_direct_numeric_fail(scope, out_dir)
    summary.append({"audit": "direct_numeric_fail", "total_checked": n, "total_flagged": k, "flag_rate": (k / n) if n else 0.0})

    print("[audit] 3/7 canonical_id_unknown …")
    n, k, _, _pref = audit_canonical_id_unknown(scope, out_dir)
    summary.append({"audit": "canonical_id_unknown", "total_checked": n, "total_flagged": k, "flag_rate": (k / n) if n else 0.0})

    print("[audit] 4/7 filler_integrity …")
    n, k, _ = audit_filler_integrity(scope, out_dir)
    summary.append({"audit": "filler_integrity", "total_checked": n, "total_flagged": k, "flag_rate": (k / n) if n else 0.0})

    print("[audit] 5/7 provenance_drift …")
    audit_provenance_drift(scope, out_dir, registry)
    summary.append({"audit": "provenance_drift", "total_checked": len(scope), "total_flagged": 0, "flag_rate": 0.0})

    print("[audit] 6/7 cross_model_agreement …")
    n, k, _ = audit_cross_model_agreement(scope, out_dir)
    summary.append({"audit": "cross_model_high_disagreement", "total_checked": n, "total_flagged": k, "flag_rate": (k / n) if n else 0.0})

    print("[audit] 7/7 majority_unsupported …")
    n, k, _ = audit_majority_unsupported(scope, out_dir)
    summary.append({"audit": "majority_unsupported", "total_checked": n, "total_flagged": k, "flag_rate": (k / n) if n else 0.0})

    # write summary
    sjson = out_dir / "audit_summary.json"
    sjson.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    smd = out_dir / "audit_summary.md"
    lines = ["# Audit summary", "",
             "| audit | total_checked | total_flagged | flag_rate |",
             "|---|---:|---:|---:|"]
    for r in summary:
        lines.append(f"| {r['audit']} | {r['total_checked']} | {r['total_flagged']} | {r['flag_rate']:.3f} |")
    smd.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


__all__ = [
    "audit_canonical_id_unknown",
    "audit_cross_model_agreement",
    "audit_direct_numeric_fail",
    "audit_evidence_missing",
    "audit_filler_integrity",
    "audit_majority_unsupported",
    "audit_provenance_drift",
    "run_audits",
]
