"""Phase-2 aggregation: claim-level, batch-level, prompt-level statistics.

Stdlib only. Reads :class:`ClaimRecord` rows and emits the family of CSV /
JSON tables described in the plan.
"""
from __future__ import annotations

import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Iterable, Sequence

from .loader import BUCKETS, ClaimRecord
from .section_policy import DEFAULT_SECTION_POLICY

# Canonical orderings for stable output --------------------------------------
CLAIM_TYPES = (
    "counting", "comparison", "trend", "listing", "range", "exact_value",
    "property_attribution", "existence_absence", "calculation", "citation",
    "domain_reasoning", "filler",
)
SUPPORT_CLASSES = (
    "direct", "inferred", "domain_knowledge", "unsupported", "no_tool_data",
)
NON_FILLER_BUCKETS = ("verified", "domain", "unverified")
CONSTANT_PEER_OUTLIER_Z = 3.0


def _major_section(section: str) -> str:
    return DEFAULT_SECTION_POLICY.group_major_section(section)


def _record_major_section(record: ClaimRecord) -> str:
    return record.major_section or _major_section(record.section)


def _group_eval_mode(recs: list[ClaimRecord]) -> str:
    modes = sorted({record.eval_mode for record in recs if record.eval_mode})
    if not modes:
        return ""
    if len(modes) == 1:
        return modes[0]
    return "mixed"

# Eval mode -> expected dominant claim_type (for 2.D narrative table)
EVAL_MODE_EXPECTED_DOMINANT = {
    "direct_lookup": "exact_value",
    "provenance": "citation",
    "comparison": "comparison",
    "aggregate": "counting",
    "multi_step": "exact_value",
    "thermo_reasoning": "domain_reasoning",
    "hypothesis": "domain_reasoning",
    "ambiguous": "existence_absence",
    "negative": "existence_absence",
}


# ---------------------------------------------------------------------------
# Statistical helpers
# ---------------------------------------------------------------------------

def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a proportion. Returns (lo, hi). NaN if n=0."""
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def safe_mean(xs: Sequence[float]) -> float:
    return statistics.fmean(xs) if xs else float("nan")


def safe_stdev(xs: Sequence[float]) -> float:
    if len(xs) < 2:
        return 0.0
    return statistics.stdev(xs)


def sibling_zscore(value: float, peers: Sequence[float]) -> float:
    """Compare one value against its sibling distribution.

    Using the full-group mean/stdev with only 5 batches makes a 2-sigma cutoff
    effectively unreachable because the candidate point inflates the stdev.
    Leave-one-out comparison matches the intended question: does this batch look
    anomalous relative to its sibling runs?
    """
    if not peers:
        return 0.0
    mean = safe_mean(peers)
    stdev = safe_stdev(peers)
    if stdev > 0:
        return (value - mean) / stdev
    if math.isclose(value, mean, rel_tol=0.0, abs_tol=1e-12):
        return 0.0
    if value > mean:
        return CONSTANT_PEER_OUTLIER_Z
    if value < mean:
        return -CONSTANT_PEER_OUTLIER_Z
    return 0.0


# ---------------------------------------------------------------------------
# Generic CSV writers
# ---------------------------------------------------------------------------

def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return path


def _dump_json_twin(csv_path: Path, rows: list[dict], json_dir: Path) -> Path:
    json_dir.mkdir(parents=True, exist_ok=True)
    out = json_dir / (csv_path.stem + ".json")
    with out.open("w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2, default=_json_default)
    return out


def _json_default(o):
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    raise TypeError(f"unserializable: {type(o)}")


# ---------------------------------------------------------------------------
# 2.A Claim-level grouped tables
# ---------------------------------------------------------------------------

def _bucket_row(group_key: dict, recs: list[ClaimRecord]) -> dict:
    n_total = len(recs)
    counts = Counter(r.bucket for r in recs)
    n_filler = counts.get("filler", 0)
    n_nonfiller = n_total - n_filler

    row = dict(group_key)
    row["n_claims"] = n_total
    row["n_nonfiller"] = n_nonfiller
    row["n_batches"] = len({(r.model, r.question_id, r.batch) for r in recs})
    row["filler_share"] = n_filler / n_total if n_total else float("nan")
    for b in NON_FILLER_BUCKETS:
        c = counts.get(b, 0)
        row[f"{b}_count"] = c
        row[f"{b}_share"] = c / n_nonfiller if n_nonfiller else float("nan")
        lo, hi = wilson_ci(c, n_nonfiller)
        row[f"{b}_ci_lo"] = lo
        row[f"{b}_ci_hi"] = hi
    return row


def _group_by(recs: list[ClaimRecord], keyfn) -> dict[tuple, list[ClaimRecord]]:
    out: dict[tuple, list[ClaimRecord]] = defaultdict(list)
    for r in recs:
        out[keyfn(r)].append(r)
    return out


_BUCKET_FIELDS_BASE = [
    "n_claims", "n_nonfiller", "n_batches", "filler_share",
] + [
    f"{b}_{suffix}"
    for b in NON_FILLER_BUCKETS
    for suffix in ("count", "share", "ci_lo", "ci_hi")
]


def emit_bucket_rates(
    recs: list[ClaimRecord], out_dir: Path, json_dir: Path
) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    key_funcs = {
        "model": lambda r: (r.model,),
        "section": lambda r: (r.section,),
        "prompt": lambda r: (r.question_id,),
        "model_section": lambda r: (r.model, r.section),
        "model_major_section": lambda r: (r.model, _record_major_section(r)),
        "model_prompt": lambda r: (r.model, r.question_id),
        "eval_mode": lambda r: (r.eval_mode,),
    }
    label_funcs = {
        "model": lambda members: {"model": members[0].model},
        "section": lambda members: {"section": members[0].section, "eval_mode": _group_eval_mode(members)},
        "prompt": lambda members: {"question_id": members[0].question_id, "section": members[0].section, "eval_mode": _group_eval_mode(members)},
        "model_section": lambda members: {"model": members[0].model, "section": members[0].section, "eval_mode": _group_eval_mode(members)},
        "model_major_section": lambda members: {"model": members[0].model, "major_section": _record_major_section(members[0])},
        "model_prompt": lambda members: {"model": members[0].model, "question_id": members[0].question_id, "section": members[0].section, "eval_mode": _group_eval_mode(members)},
        "eval_mode": lambda members: {"eval_mode": members[0].eval_mode},
    }
    extra_cols = {
        "model": ["model"],
        "section": ["section", "eval_mode"],
        "prompt": ["question_id", "section", "eval_mode"],
        "model_section": ["model", "section", "eval_mode"],
        "model_major_section": ["model", "major_section"],
        "model_prompt": ["model", "question_id", "section", "eval_mode"],
        "eval_mode": ["eval_mode"],
    }

    for name in key_funcs:
        groups = _group_by(recs, key_funcs[name])
        rows = []
        for _, members in sorted(groups.items()):
            label = label_funcs[name](members)
            rows.append(_bucket_row(label, members))
        rows.sort(key=lambda r: tuple(r.get(c, "") for c in extra_cols[name]))
        path = out_dir / f"bucket_rates_by_{name}.csv"
        _write_csv(path, rows, extra_cols[name] + _BUCKET_FIELDS_BASE)
        _dump_json_twin(path, rows, json_dir)
        written[name] = path
    return written


def emit_class_marker(
    recs: list[ClaimRecord], out_dir: Path, json_dir: Path
) -> dict[str, Path]:
    """12 x 5 contingency tables of claim_type x support_class."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    key_funcs = {
        "all": lambda r: ("all",),
        "model": lambda r: (r.model,),
        "section": lambda r: (r.section,),
        "prompt": lambda r: (r.question_id,),
        "model_section": lambda r: (r.model, r.section),
        "model_prompt": lambda r: (r.model, r.question_id),
    }
    label_cols = {
        "all": [],
        "model": ["model"],
        "section": ["section"],
        "prompt": ["question_id", "section"],
        "model_section": ["model", "section"],
        "model_prompt": ["model", "question_id", "section"],
    }
    label_funcs = {
        "all": lambda r: {},
        "model": lambda r: {"model": r.model},
        "section": lambda r: {"section": r.section},
        "prompt": lambda r: {"question_id": r.question_id, "section": r.section},
        "model_section": lambda r: {"model": r.model, "section": r.section},
        "model_prompt": lambda r: {"model": r.model, "question_id": r.question_id, "section": r.section},
    }

    sup_cols = list(SUPPORT_CLASSES)
    count_fields = label_cols.copy()
    share_fields = label_cols.copy()

    for name, kf in key_funcs.items():
        groups = _group_by(recs, kf)
        count_rows: list[dict] = []
        share_rows: list[dict] = []
        for _, members in sorted(groups.items()):
            label = label_funcs[name](members[0])
            cell = Counter((r.claim_type, r.support_class) for r in members)
            for ct in CLAIM_TYPES:
                row_total = sum(cell.get((ct, s), 0) for s in SUPPORT_CLASSES)
                count_row = dict(label)
                count_row["claim_type"] = ct
                count_row["row_total"] = row_total
                share_row = dict(count_row)
                for s in SUPPORT_CLASSES:
                    c = cell.get((ct, s), 0)
                    count_row[s] = c
                    share_row[s] = (c / row_total) if row_total else float("nan")
                count_rows.append(count_row)
                share_rows.append(share_row)

        cols = label_cols[name] + ["claim_type"] + sup_cols + ["row_total"]
        cpath = out_dir / f"class_marker_{name}.csv"
        spath = out_dir / f"class_marker_{name}_shares.csv"
        _write_csv(cpath, count_rows, cols)
        _write_csv(spath, share_rows, cols)
        _dump_json_twin(cpath, count_rows, json_dir)
        _dump_json_twin(spath, share_rows, json_dir)
        written[name] = cpath
    return written


def emit_support_by_claim_type(
    recs: list[ClaimRecord], out_dir: Path, json_dir: Path
) -> dict[str, Path]:
    """12 x 4 collapsed bucket view of claim_type x bucket."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    key_funcs = {
        "all": (lambda r: ("all",), lambda r: {}, []),
        "section": (lambda r: (r.section,), lambda r: {"section": r.section}, ["section"]),
        "prompt": (lambda r: (r.question_id,), lambda r: {"question_id": r.question_id, "section": r.section}, ["question_id", "section"]),
        "model": (lambda r: (r.model,), lambda r: {"model": r.model}, ["model"]),
        "model_section": (lambda r: (r.model, r.section), lambda r: {"model": r.model, "section": r.section}, ["model", "section"]),
        "model_major_section": (lambda r: (r.model, _record_major_section(r)), lambda r: {"model": r.model, "major_section": _record_major_section(r)}, ["model", "major_section"]),
        "model_prompt": (lambda r: (r.model, r.question_id), lambda r: {"model": r.model, "question_id": r.question_id, "section": r.section}, ["model", "question_id", "section"]),
    }
    for name, (kf, lf, cols) in key_funcs.items():
        groups = _group_by(recs, kf)
        rows: list[dict] = []
        for _, members in sorted(groups.items()):
            label = lf(members[0])
            cell = Counter((r.claim_type, r.bucket) for r in members)
            for ct in CLAIM_TYPES:
                row_total = sum(cell.get((ct, b), 0) for b in BUCKETS)
                row = dict(label)
                row["claim_type"] = ct
                row["row_total"] = row_total
                for b in BUCKETS:
                    c = cell.get((ct, b), 0)
                    row[f"{b}_count"] = c
                    row[f"{b}_share"] = (c / row_total) if row_total else float("nan")
                rows.append(row)
        out = out_dir / f"support_by_claim_type_{name}.csv"
        fields = cols + ["claim_type"] + [f"{b}_{s}" for b in BUCKETS for s in ("count", "share")] + ["row_total"]
        _write_csv(out, rows, fields)
        _dump_json_twin(out, rows, json_dir)
        written[name] = out
    return written


def emit_claim_type_share_by_model_major_section(
    recs: list[ClaimRecord], out_dir: Path, json_dir: Path
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    groups = _group_by(recs, lambda r: (r.model, _record_major_section(r)))
    rows: list[dict] = []
    for (model, major_section), members in sorted(groups.items()):
        total = len(members)
        counts = Counter(r.claim_type for r in members)
        for claim_type in CLAIM_TYPES:
            claim_count = counts.get(claim_type, 0)
            rows.append(
                {
                    "model": model,
                    "major_section": major_section,
                    "claim_type": claim_type,
                    "claim_count": claim_count,
                    "claim_share": (claim_count / total) if total else float("nan"),
                    "n_claims": total,
                }
            )
    path = out_dir / "claim_type_share_by_model_major_section.csv"
    _write_csv(path, rows, ["model", "major_section", "claim_type", "claim_count", "claim_share", "n_claims"])
    _dump_json_twin(path, rows, json_dir)
    return path


def emit_verified_share_by_claim_type_model_major_section(
    recs: list[ClaimRecord], out_dir: Path, json_dir: Path
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    groups = _group_by(recs, lambda r: (r.model, _record_major_section(r)))
    rows: list[dict] = []
    for (model, major_section), members in sorted(groups.items()):
        cell = Counter((r.claim_type, r.bucket) for r in members)
        for claim_type in CLAIM_TYPES:
            row_total = sum(cell.get((claim_type, bucket), 0) for bucket in BUCKETS)
            verified_count = cell.get((claim_type, "verified"), 0)
            rows.append(
                {
                    "model": model,
                    "major_section": major_section,
                    "claim_type": claim_type,
                    "verified_count": verified_count,
                    "row_total": row_total,
                    "verified_share": (verified_count / row_total) if row_total else float("nan"),
                }
            )
    path = out_dir / "verified_share_by_claim_type_model_major_section.csv"
    _write_csv(path, rows, ["model", "major_section", "claim_type", "verified_count", "row_total", "verified_share"])
    _dump_json_twin(path, rows, json_dir)
    return path


def emit_verified_share_by_claim_type_model_major_section_matrix(
    recs: list[ClaimRecord], out_dir: Path, json_dir: Path
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    groups = _group_by(recs, lambda r: (r.model, _record_major_section(r)))
    rows: list[dict] = []
    for (model, major_section), members in sorted(groups.items()):
        cell = Counter((r.claim_type, r.bucket) for r in members)
        row = {
            "major_section": major_section,
            "model": model,
        }
        for claim_type in CLAIM_TYPES:
            row_total = sum(cell.get((claim_type, bucket), 0) for bucket in BUCKETS)
            verified_count = cell.get((claim_type, "verified"), 0)
            row[claim_type] = (verified_count / row_total) if row_total else float("nan")
        rows.append(row)
    path = out_dir / "verified_share_by_claim_type_model_major_section_matrix.csv"
    _write_csv(path, rows, ["major_section", "model", *CLAIM_TYPES])
    _dump_json_twin(path, rows, json_dir)
    return path


# ---------------------------------------------------------------------------
# 2.B Batch-as-repeated-sample
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class BatchSummary:
    model: str
    question_id: str
    section: str
    eval_mode: str
    batch: int
    n_claims: int
    n_nonfiller: int
    verified_share: float
    domain_share: float
    unverified_share: float
    filler_share: float
    n_canonical_unique: int
    n_tool_snippets_total: int
    mean_text_len: float
    canonical_ids: tuple
    numeric_tokens: tuple
    major_section: str = ""


_NUMERIC_RE = __import__("re").compile(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")
_NUMERIC_CLAIM_TYPES = {"exact_value", "range", "counting", "calculation"}


def _extract_numeric_tokens(recs: list[ClaimRecord], texts: dict[tuple, str]) -> set[str]:
    """Return numeric tokens drawn from the claim text of numeric-typed claims.

    NB: claim text isn't on ClaimRecord directly; we approximate using the
    grounder's evidence_snippet via texts mapping when available. For the
    batch-summary path we instead pull tokens from the source claim text by
    re-loading; here we use a pre-supplied map keyed by (paragraph_index,
    claim_index).
    """
    tokens: set[str] = set()
    for r in recs:
        if r.claim_type not in _NUMERIC_CLAIM_TYPES:
            continue
        t = texts.get((r.paragraph_index, r.claim_index), "")
        for m in _NUMERIC_RE.findall(t):
            tokens.add(m)
    return tokens


def summarize_batches(
    recs: list[ClaimRecord], claim_texts: dict[tuple, dict[tuple, str]] | None = None,
) -> list[BatchSummary]:
    """Build one :class:`BatchSummary` per (model, question_id, batch).

    ``claim_texts`` maps (model, question_id, batch) -> {(p_idx, c_idx): text}.
    If absent, numeric_tokens will be empty.
    """
    by_batch: dict[tuple, list[ClaimRecord]] = defaultdict(list)
    for r in recs:
        by_batch[(r.model, r.question_id, r.batch)].append(r)

    out: list[BatchSummary] = []
    for key, members in sorted(by_batch.items()):
        model, qid, batch = key
        n = len(members)
        counts = Counter(r.bucket for r in members)
        n_filler = counts.get("filler", 0)
        n_nonfiller = n - n_filler
        canon: set[str] = set()
        n_snip = 0
        text_lens: list[int] = []
        for r in members:
            n_snip += r.n_tool_snippets
            text_lens.append(r.text_len)
        # canonical_ids are not stored on ClaimRecord; supplement via claim_texts caller path below
        # — they're recomputed in the loader-side enrichment. To avoid changing
        # ClaimRecord signature, expose 0 here; revalidate.py uses raw payload.
        first = members[0]
        share = lambda b: (counts.get(b, 0) / n_nonfiller) if n_nonfiller else float("nan")
        texts_for_batch = (claim_texts or {}).get(key, {})
        nums = _extract_numeric_tokens(members, texts_for_batch)
        out.append(
            BatchSummary(
                model=model,
                question_id=qid,
                section=first.section,
                eval_mode=first.eval_mode,
                batch=batch,
                n_claims=n,
                n_nonfiller=n_nonfiller,
                verified_share=share("verified"),
                domain_share=share("domain"),
                unverified_share=share("unverified"),
                filler_share=(n_filler / n) if n else float("nan"),
                n_canonical_unique=len(canon),
                n_tool_snippets_total=n_snip,
                mean_text_len=safe_mean(text_lens),
                canonical_ids=tuple(),
                numeric_tokens=tuple(sorted(nums)),
                major_section=_record_major_section(first),
            )
        )
    return out


def _exclude_domain_bucket_shares(summary: BatchSummary) -> tuple[float, float]:
    if math.isnan(summary.verified_share) or math.isnan(summary.unverified_share):
        return (float("nan"), float("nan"))
    denom = summary.verified_share + summary.unverified_share
    if denom <= 0:
        return (float("nan"), float("nan"))
    return (summary.verified_share / denom, summary.unverified_share / denom)


def emit_batch_stability(summaries: list[BatchSummary], out_dir: Path, json_dir: Path) -> Path:
    by_mp: dict[tuple, list[BatchSummary]] = defaultdict(list)
    for s in summaries:
        by_mp[(s.model, s.question_id)].append(s)
    rows: list[dict] = []
    for (model, qid), bs in sorted(by_mp.items()):
        n_batches = len(bs)
        counts = [b.n_claims for b in bs]
        v = [b.verified_share for b in bs if not math.isnan(b.verified_share)]
        d = [b.domain_share for b in bs if not math.isnan(b.domain_share)]
        u = [b.unverified_share for b in bs if not math.isnan(b.unverified_share)]
        f = [b.filler_share for b in bs if not math.isnan(b.filler_share)]
        # composite stability: 1 - mean of bucket-share stdevs (clamped to [0,1])
        stdevs = [safe_stdev(x) for x in (v, d, u, f)]
        stability = 1.0 - safe_mean(stdevs)
        rows.append({
            "model": model,
            "question_id": qid,
            "section": bs[0].section,
            "eval_mode": bs[0].eval_mode,
            "n_batches": n_batches,
            "n_claims_mean": safe_mean(counts),
            "n_claims_stdev": safe_stdev(counts),
            "n_claims_min": min(counts) if counts else 0,
            "n_claims_max": max(counts) if counts else 0,
            "verified_mean": safe_mean(v),
            "verified_stdev": safe_stdev(v),
            "domain_mean": safe_mean(d),
            "domain_stdev": safe_stdev(d),
            "unverified_mean": safe_mean(u),
            "unverified_stdev": safe_stdev(u),
            "filler_mean": safe_mean(f),
            "filler_stdev": safe_stdev(f),
            "stability_score": stability,
        })
    rows.sort(key=lambda r: (r["model"], r["question_id"]))
    cols = list(rows[0].keys()) if rows else []
    path = out_dir / "batch_stability.csv"
    _write_csv(path, rows, cols)
    _dump_json_twin(path, rows, json_dir)
    return path


def emit_batch_outliers(summaries: list[BatchSummary], out_dir: Path, json_dir: Path) -> Path:
    by_mp: dict[tuple, list[BatchSummary]] = defaultdict(list)
    for s in summaries:
        by_mp[(s.model, s.question_id)].append(s)
    rows: list[dict] = []
    for (model, qid), bs in sorted(by_mp.items()):
        if len(bs) < 3:
            continue
        for idx, b in enumerate(bs):
            v_peers = [
                other.verified_share
                for j, other in enumerate(bs)
                if j != idx and not math.isnan(other.verified_share)
            ]
            c_peers = [other.n_claims for j, other in enumerate(bs) if j != idx]
            verified_defined = not math.isnan(b.verified_share)
            v_z = sibling_zscore(b.verified_share, v_peers) if verified_defined else 0.0
            c_z = sibling_zscore(float(b.n_claims), [float(v) for v in c_peers])
            if abs(v_z) >= 2.0 or abs(c_z) >= 2.0:
                rows.append({
                    "model": model, "question_id": qid, "batch": b.batch,
                    "section": b.section, "eval_mode": b.eval_mode,
                    "n_claims": b.n_claims, "n_claims_z": c_z,
                    "verified_share": b.verified_share if verified_defined else None,
                    "verified_share_z": v_z if verified_defined else None,
                })
    rows.sort(key=lambda r: (
        -max(abs(r["n_claims_z"]), abs(r["verified_share_z"] or 0.0)),
        r["model"],
        r["question_id"],
        r["batch"],
    ))
    cols = ["model", "question_id", "batch", "section", "eval_mode",
            "n_claims", "n_claims_z", "verified_share", "verified_share_z"]
    path = out_dir / "batch_outliers.csv"
    _write_csv(path, rows, cols)
    _dump_json_twin(path, rows, json_dir)
    return path


def emit_batch_agreement_canonical(
    canonical_by_batch: dict[tuple, set[str]],
    out_dir: Path,
    json_dir: Path,
) -> Path:
    """Pairwise canonical_id Jaccard across the 5 batches per (model, qid)."""
    by_mp: dict[tuple, list[tuple[int, set[str]]]] = defaultdict(list)
    for (model, qid, batch), ids in canonical_by_batch.items():
        by_mp[(model, qid)].append((batch, ids))

    rows: list[dict] = []
    detail: dict[str, dict] = {}
    for (model, qid), batches in sorted(by_mp.items()):
        batches.sort()
        if len(batches) < 2:
            continue
        sims = [jaccard(a, b) for (_, a), (_, b) in combinations(batches, 2)]
        # 5x5 matrix
        n = len(batches)
        matrix = [[1.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                matrix[i][j] = matrix[j][i] = jaccard(batches[i][1], batches[j][1])
        rows.append({
            "model": model, "question_id": qid,
            "n_batches": n,
            "jaccard_mean": safe_mean(sims),
            "jaccard_min": min(sims),
            "jaccard_max": max(sims),
            "n_unique_union": len(set().union(*[ids for _, ids in batches])),
        })
        detail[f"{model}|{qid}"] = {
            "batch_indices": [b for b, _ in batches],
            "matrix": matrix,
        }
    path = out_dir / "batch_agreement_canonical.csv"
    _write_csv(path, rows, ["model", "question_id", "n_batches", "jaccard_mean", "jaccard_min", "jaccard_max", "n_unique_union"])
    _dump_json_twin(path, rows, json_dir)
    sidecar = json_dir / "batch_agreement_canonical_matrices.json"
    sidecar.write_text(json.dumps(detail, indent=2, default=_json_default), encoding="utf-8")
    return path


def emit_pairwise_jaccard_by_model_major_section(
    canonical_by_batch: dict[tuple, set[str]],
    summaries: list[BatchSummary],
    out_dir: Path,
    json_dir: Path,
) -> Path:
    by_q_major = {
        summary.question_id: (summary.major_section or _major_section(summary.section))
        for summary in summaries
    }
    by_mp: dict[tuple, list[tuple[int, set[str]]]] = defaultdict(list)
    for (model, question_id, batch), ids in canonical_by_batch.items():
        by_mp[(model, question_id)].append((batch, ids))

    per_prompt_rows: list[dict] = []
    for (model, question_id), batches in sorted(by_mp.items()):
        batches.sort()
        if len(batches) < 2:
            continue
        sims = [jaccard(a, b) for (_, a), (_, b) in combinations(batches, 2)]
        per_prompt_rows.append(
            {
                "model": model,
                "question_id": question_id,
                "major_section": by_q_major.get(question_id, ""),
                "jaccard_mean": safe_mean(sims),
            }
        )

    groups: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in per_prompt_rows:
        groups[(row["model"], row["major_section"])].append(row["jaccard_mean"])

    rows: list[dict] = []
    for (model, major_section), vals in sorted(groups.items()):
        clean_vals = [value for value in vals if not math.isnan(value)]
        rows.append(
            {
                "model": model,
                "major_section": major_section,
                "n_prompts": len(clean_vals),
                "jaccard_mean": safe_mean(clean_vals),
                "jaccard_min": min(clean_vals) if clean_vals else float("nan"),
                "jaccard_max": max(clean_vals) if clean_vals else float("nan"),
            }
        )
    path = out_dir / "pairwise_jaccard_by_model_major_section.csv"
    _write_csv(path, rows, ["model", "major_section", "n_prompts", "jaccard_mean", "jaccard_min", "jaccard_max"])
    _dump_json_twin(path, rows, json_dir)
    return path


def emit_batch_agreement_numeric(
    summaries: list[BatchSummary], out_dir: Path, json_dir: Path
) -> Path:
    by_mp: dict[tuple, list[BatchSummary]] = defaultdict(list)
    for s in summaries:
        by_mp[(s.model, s.question_id)].append(s)
    rows: list[dict] = []
    for (model, qid), bs in sorted(by_mp.items()):
        n = len(bs)
        if n < 2:
            continue
        # token -> count of batches it appears in
        tcount: Counter[str] = Counter()
        for b in bs:
            for t in set(b.numeric_tokens):
                tcount[t] += 1
        n_unique = len(tcount)
        if n_unique == 0:
            continue
        ks = {k: sum(1 for v in tcount.values() if v >= k) for k in (2, 3, 4, 5) if k <= n}
        rows.append({
            "model": model, "question_id": qid, "n_batches": n,
            "n_unique_numeric_tokens": n_unique,
            "share_in_ge2": ks.get(2, 0) / n_unique,
            "share_in_ge3": (ks.get(3, 0) / n_unique) if 3 in ks else None,
            "share_in_ge4": (ks.get(4, 0) / n_unique) if 4 in ks else None,
            "share_in_ge5": (ks.get(5, 0) / n_unique) if 5 in ks else None,
            "share_in_all_batches": (sum(1 for v in tcount.values() if v == n) / n_unique) if n_unique else float("nan"),
        })
    path = out_dir / "batch_agreement_numeric.csv"
    _write_csv(path, rows, list(rows[0].keys()) if rows else [])
    _dump_json_twin(path, rows, json_dir)
    return path


def emit_coverage_saturation(
    canonical_by_batch: dict[tuple, set[str]], out_dir: Path, json_dir: Path
) -> Path:
    by_mp: dict[tuple, list[tuple[int, set[str]]]] = defaultdict(list)
    for (model, qid, batch), ids in canonical_by_batch.items():
        by_mp[(model, qid)].append((batch, ids))
    rows: list[dict] = []
    for (model, qid), bs in sorted(by_mp.items()):
        bs.sort()
        seen: set[str] = set()
        cum: list[int] = []
        for _, ids in bs:
            seen |= ids
            cum.append(len(seen))
        row = {"model": model, "question_id": qid, "n_batches": len(bs)}
        for i, c in enumerate(cum, start=1):
            row[f"cum_after_batch{i}"] = c
        for i in range(len(cum) + 1, 6):
            row[f"cum_after_batch{i}"] = ""
        # delta from batch1 to last: how much exploration after first batch
        row["delta_b1_to_last"] = (cum[-1] - cum[0]) if cum else 0
        row["saturation_ratio"] = (cum[0] / cum[-1]) if cum and cum[-1] else float("nan")
        rows.append(row)
    cols = ["model", "question_id", "n_batches"] + [f"cum_after_batch{i}" for i in range(1, 6)] + ["delta_b1_to_last", "saturation_ratio"]
    path = out_dir / "coverage_saturation.csv"
    _write_csv(path, rows, cols)
    _dump_json_twin(path, rows, json_dir)
    return path


def emit_best_vs_worst_batch(summaries: list[BatchSummary], out_dir: Path, json_dir: Path) -> Path:
    by_mp: dict[tuple, list[BatchSummary]] = defaultdict(list)
    for s in summaries:
        by_mp[(s.model, s.question_id)].append(s)
    rows: list[dict] = []
    for (model, qid), bs in sorted(by_mp.items()):
        if len(bs) < 2:
            continue
        vs = [(b.verified_share, b.batch) for b in bs if not math.isnan(b.verified_share)]
        if len(vs) < 2:
            continue
        best_v, best_b = max(vs)
        worst_v, worst_b = min(vs)
        rows.append({
            "model": model, "question_id": qid,
            "section": bs[0].section, "eval_mode": bs[0].eval_mode,
            "n_batches": len(bs),
            "best_verified_share": best_v, "best_batch": best_b,
            "worst_verified_share": worst_v, "worst_batch": worst_b,
            "gap": best_v - worst_v,
        })
    rows.sort(key=lambda r: -r["gap"])
    cols = list(rows[0].keys()) if rows else []
    path = out_dir / "best_vs_worst_batch.csv"
    _write_csv(path, rows, cols)
    _dump_json_twin(path, rows, json_dir)
    return path


def emit_claim_count_by_batch_position(summaries: list[BatchSummary], out_dir: Path, json_dir: Path) -> Path:
    by_pos: dict[tuple, list[BatchSummary]] = defaultdict(list)
    for s in summaries:
        by_pos[(s.model, s.batch)].append(s)
    rows: list[dict] = []
    for (model, batch), bs in sorted(by_pos.items()):
        counts = [b.n_claims for b in bs]
        v = [b.verified_share for b in bs if not math.isnan(b.verified_share)]
        rows.append({
            "model": model, "batch_index": batch,
            "n_prompts": len(bs),
            "n_claims_mean": safe_mean(counts),
            "n_claims_stdev": safe_stdev(counts),
            "verified_share_mean": safe_mean(v),
            "verified_share_stdev": safe_stdev(v),
        })
    path = out_dir / "claim_count_distribution_by_batch.csv"
    _write_csv(path, rows, ["model", "batch_index", "n_prompts", "n_claims_mean", "n_claims_stdev", "verified_share_mean", "verified_share_stdev"])
    _dump_json_twin(path, rows, json_dir)
    return path


# ---------------------------------------------------------------------------
# 2.C Prompt difficulty / cross-model
# ---------------------------------------------------------------------------

def emit_prompt_difficulty(summaries: list[BatchSummary], out_dir: Path, json_dir: Path) -> Path:
    by_q: dict[str, list[BatchSummary]] = defaultdict(list)
    for s in summaries:
        by_q[s.question_id].append(s)
    rows: list[dict] = []
    for qid, bs in sorted(by_q.items()):
        v = [b.verified_share for b in bs if not math.isnan(b.verified_share)]
        u = [b.unverified_share for b in bs if not math.isnan(b.unverified_share)]
        ex_domain = [_exclude_domain_bucket_shares(b) for b in bs]
        v_ex_domain = [verified for verified, _ in ex_domain if not math.isnan(verified)]
        u_ex_domain = [unverified for _, unverified in ex_domain if not math.isnan(unverified)]
        rows.append({
            "question_id": qid,
            "section": bs[0].section,
            "eval_mode": bs[0].eval_mode,
            "n_runs": len(bs),
            "n_scored_runs": len(v_ex_domain),
            "n_models": len({b.model for b in bs}),
            "verified_mean": safe_mean(v),
            "verified_stdev": safe_stdev(v),
            "unverified_mean": safe_mean(u),
            "unverified_stdev": safe_stdev(u),
            "verified_ex_domain_mean": safe_mean(v_ex_domain),
            "verified_ex_domain_stdev": safe_stdev(v_ex_domain),
            "unverified_ex_domain_mean": safe_mean(u_ex_domain),
            "unverified_ex_domain_stdev": safe_stdev(u_ex_domain),
        })
    rows.sort(
        key=lambda r: (
            r["verified_ex_domain_mean"]
            if not math.isnan(r["verified_ex_domain_mean"])
            else 1.0
        )
    )
    for i, row in enumerate(rows, start=1):
        row["difficulty_rank"] = i
    path = out_dir / "prompt_difficulty.csv"
    _write_csv(path, rows, ["difficulty_rank"] + [k for k in rows[0] if k != "difficulty_rank"] if rows else [])
    _dump_json_twin(path, rows, json_dir)
    return path


def emit_prompt_instability(summaries: list[BatchSummary], out_dir: Path, json_dir: Path) -> Path:
    """Mean across models of per-(model, prompt) batch stdev."""
    per_mp: dict[tuple, list[float]] = defaultdict(list)
    for s in summaries:
        per_mp[(s.model, s.question_id)].append(s.verified_share)
    stdev_by_mp = {k: safe_stdev([x for x in v if not math.isnan(x)]) for k, v in per_mp.items()}

    by_q: dict[str, list[float]] = defaultdict(list)
    by_q_section: dict[str, str] = {}
    for s in summaries:
        by_q_section[s.question_id] = s.section
    for (_, qid), sd in stdev_by_mp.items():
        by_q[qid].append(sd)
    rows: list[dict] = []
    for qid, sds in sorted(by_q.items()):
        rows.append({
            "question_id": qid,
            "section": by_q_section.get(qid, ""),
            "n_models": len(sds),
            "mean_within_model_stdev": safe_mean(sds),
            "max_within_model_stdev": max(sds) if sds else float("nan"),
        })
    rows.sort(key=lambda r: -r["mean_within_model_stdev"] if not math.isnan(r["mean_within_model_stdev"]) else 0)
    path = out_dir / "prompt_instability.csv"
    _write_csv(path, rows, list(rows[0].keys()) if rows else [])
    _dump_json_twin(path, rows, json_dir)
    return path


def emit_cross_model_rank_correlation(summaries: list[BatchSummary], out_dir: Path, json_dir: Path) -> Path:
    """Spearman rank correlation of per-prompt verified_share between every pair of models."""
    per_mq: dict[tuple, list[float]] = defaultdict(list)
    for s in summaries:
        per_mq[(s.model, s.question_id)].append(s.verified_share)
    mean_per_mq = {k: safe_mean([x for x in v if not math.isnan(x)]) for k, v in per_mq.items()}
    models = sorted({m for m, _ in mean_per_mq})
    questions = sorted({q for _, q in mean_per_mq})

    def vec(model: str) -> list[float]:
        return [mean_per_mq.get((model, q), float("nan")) for q in questions]

    rows: list[dict] = []
    for m1, m2 in combinations(models, 2):
        v1, v2 = vec(m1), vec(m2)
        # drop NaN aligned
        pairs = [(a, b) for a, b in zip(v1, v2) if not (math.isnan(a) or math.isnan(b))]
        rho = _spearman([a for a, _ in pairs], [b for _, b in pairs])
        rows.append({"model_a": m1, "model_b": m2, "n_prompts": len(pairs), "spearman": rho})
    path = out_dir / "cross_model_rank_correlation.csv"
    _write_csv(path, rows, ["model_a", "model_b", "n_prompts", "spearman"])
    _dump_json_twin(path, rows, json_dir)
    return path


def _spearman(x: list[float], y: list[float]) -> float:
    if len(x) < 2:
        return float("nan")
    rx = _ranks(x)
    ry = _ranks(y)
    n = len(x)
    mean_rx = sum(rx) / n
    mean_ry = sum(ry) / n
    num = sum((a - mean_rx) * (b - mean_ry) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mean_rx) ** 2 for a in rx) * sum((b - mean_ry) ** 2 for b in ry))
    return num / den if den else float("nan")


def _ranks(xs: list[float]) -> list[float]:
    indexed = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(indexed):
        j = i
        while j + 1 < len(indexed) and xs[indexed[j + 1]] == xs[indexed[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[indexed[k]] = avg
        i = j + 1
    return ranks


def emit_cross_model_agreement_canonical(
    canonical_by_batch: dict[tuple, set[str]], out_dir: Path, json_dir: Path
) -> Path:
    """Per prompt: pairwise Jaccard of (union-over-batches) canonical_id sets between models."""
    by_mq: dict[tuple, set[str]] = defaultdict(set)
    for (model, qid, _), ids in canonical_by_batch.items():
        by_mq[(model, qid)] |= ids
    by_q: dict[str, dict[str, set[str]]] = defaultdict(dict)
    for (model, qid), ids in by_mq.items():
        by_q[qid][model] = ids
    rows: list[dict] = []
    for qid, models in sorted(by_q.items()):
        if len(models) < 2:
            continue
        names = sorted(models)
        sims = [jaccard(models[a], models[b]) for a, b in combinations(names, 2)]
        rows.append({
            "question_id": qid,
            "n_models": len(names),
            "jaccard_mean": safe_mean(sims),
            "jaccard_min": min(sims),
            "jaccard_max": max(sims),
        })
    path = out_dir / "cross_model_agreement_canonical.csv"
    _write_csv(path, rows, ["question_id", "n_models", "jaccard_mean", "jaccard_min", "jaccard_max"])
    _dump_json_twin(path, rows, json_dir)
    return path


# ---------------------------------------------------------------------------
# 2.D Eval-mode profile
# ---------------------------------------------------------------------------

def emit_eval_mode_profile(recs: list[ClaimRecord], out_dir: Path, json_dir: Path) -> Path:
    by_mode: dict[str, list[ClaimRecord]] = defaultdict(list)
    for r in recs:
        by_mode[r.eval_mode].append(r)
    rows: list[dict] = []
    for mode, members in sorted(by_mode.items()):
        n = len(members)
        ct_counts = Counter(r.claim_type for r in members)
        substantive_ct_counts = Counter(r.claim_type for r in members if r.claim_type != "filler")
        bucket_counts = Counter(r.bucket for r in members)
        n_filler = bucket_counts.get("filler", 0)
        n_nonfiller = n - n_filler
        dominant_ct = substantive_ct_counts.most_common(1)[0][0] if substantive_ct_counts else (ct_counts.most_common(1)[0][0] if ct_counts else "")
        expected = EVAL_MODE_EXPECTED_DOMINANT.get(mode, "")
        row = {
            "eval_mode": mode,
            "n_claims": n,
            "n_nonfiller": n_nonfiller,
            "dominant_claim_type": dominant_ct,
            "expected_dominant": expected,
            "matches_expected": dominant_ct == expected,
        }
        for ct in CLAIM_TYPES:
            row[f"ct_{ct}_share"] = ct_counts.get(ct, 0) / n if n else float("nan")
        for b in BUCKETS:
            denom = n if b == "filler" else n_nonfiller
            row[f"bucket_{b}_share"] = (bucket_counts.get(b, 0) / denom) if denom else float("nan")
        rows.append(row)
    path = out_dir / "eval_mode_profile.csv"
    cols = list(rows[0].keys()) if rows else []
    _write_csv(path, rows, cols)
    _dump_json_twin(path, rows, json_dir)
    return path


# ---------------------------------------------------------------------------
# 2.E Position & verbosity effects
# ---------------------------------------------------------------------------

def _position_bucket(p_idx: int, max_idx: int) -> str:
    if max_idx <= 0:
        return "first"
    if p_idx == 0:
        return "first"
    if p_idx == max_idx:
        return "last"
    return "middle"


def emit_position_effects(recs: list[ClaimRecord], out_dir: Path, json_dir: Path) -> Path:
    # Determine max paragraph_index per (model, question_id, batch)
    max_p: dict[tuple, int] = {}
    for r in recs:
        k = (r.model, r.question_id, r.batch)
        cur = max_p.get(k)
        if cur is None or r.paragraph_index > cur:
            max_p[k] = r.paragraph_index
    by_pos: dict[tuple, list[ClaimRecord]] = defaultdict(list)
    for r in recs:
        pos = _position_bucket(r.paragraph_index, max_p[(r.model, r.question_id, r.batch)])
        by_pos[(r.model, pos)].append(r)
    rows: list[dict] = []
    for (model, pos), members in sorted(by_pos.items(), key=lambda kv: (kv[0][0], ["first", "middle", "last"].index(kv[0][1]))):
        n = len(members)
        c = Counter(r.bucket for r in members)
        n_filler = c.get("filler", 0)
        n_nonfiller = n - n_filler
        row = {
            "model": model, "position": pos, "n_claims": n,
            "filler_share": n_filler / n if n else float("nan"),
        }
        for b in NON_FILLER_BUCKETS:
            row[f"{b}_share"] = c.get(b, 0) / n_nonfiller if n_nonfiller else float("nan")
        rows.append(row)
    path = out_dir / "position_effects.csv"
    _write_csv(path, rows, list(rows[0].keys()) if rows else [])
    _dump_json_twin(path, rows, json_dir)
    return path


_TEXT_BINS = [(0, 50), (50, 150), (150, 500), (500, 10**9)]


def _text_bin_label(n: int) -> str:
    for lo, hi in _TEXT_BINS:
        if lo <= n < hi:
            return f"{lo}-{hi if hi < 10**9 else 'inf'}"
    return "?"


def emit_verbosity(recs: list[ClaimRecord], out_dir: Path, json_dir: Path) -> Path:
    by_bin: dict[tuple, list[ClaimRecord]] = defaultdict(list)
    for r in recs:
        by_bin[(r.model, _text_bin_label(r.text_len))].append(r)
    rows: list[dict] = []
    bin_order = [_text_bin_label(lo) for lo, _ in _TEXT_BINS]
    for (model, b), members in sorted(by_bin.items(), key=lambda kv: (kv[0][0], bin_order.index(kv[0][1]))):
        n = len(members)
        c = Counter(r.bucket for r in members)
        n_filler = c.get("filler", 0)
        n_nonfiller = n - n_filler
        row = {
            "model": model, "text_len_bin": b, "n_claims": n,
            "filler_share": n_filler / n if n else float("nan"),
        }
        for buc in NON_FILLER_BUCKETS:
            row[f"{buc}_share"] = c.get(buc, 0) / n_nonfiller if n_nonfiller else float("nan")
        rows.append(row)
    path = out_dir / "verbosity_vs_verified.csv"
    _write_csv(path, rows, list(rows[0].keys()) if rows else [])
    _dump_json_twin(path, rows, json_dir)
    return path


# ---------------------------------------------------------------------------
# 2.F + 2.G Tool / canonical-ID stats (require raw payload re-scan)
# ---------------------------------------------------------------------------

def emit_canonical_id_frequency(
    canonical_by_batch: dict[tuple, set[str]], out_dir: Path, json_dir: Path,
    top_n: int = 100,
) -> Path:
    counter: Counter[str] = Counter()
    for ids in canonical_by_batch.values():
        for cid in ids:
            counter[cid] += 1
    rows = [{"canonical_id": cid, "prefix": cid.split("_", 1)[0], "n_batches_cited": n}
            for cid, n in counter.most_common(top_n)]
    path = out_dir / "canonical_id_frequency_top.csv"
    _write_csv(path, rows, ["canonical_id", "prefix", "n_batches_cited"])
    _dump_json_twin(path, rows, json_dir)
    # also full per-prefix histogram
    by_prefix: Counter[str] = Counter()
    for cid in counter:
        by_prefix[cid.split("_", 1)[0]] += 1
    pref_rows = [{"prefix": p, "n_unique_ids": n} for p, n in by_prefix.most_common()]
    pref_path = out_dir / "canonical_id_prefix_histogram.csv"
    _write_csv(pref_path, pref_rows, ["prefix", "n_unique_ids"])
    _dump_json_twin(pref_path, pref_rows, json_dir)
    return path


def emit_prompt_evidence_breadth(
    canonical_by_batch: dict[tuple, set[str]], out_dir: Path, json_dir: Path
) -> Path:
    by_mq: dict[tuple, set[str]] = defaultdict(set)
    for (model, qid, _), ids in canonical_by_batch.items():
        by_mq[(model, qid)] |= ids
    rows = [{"model": m, "question_id": q, "n_unique_canonical_ids": len(ids)}
            for (m, q), ids in sorted(by_mq.items())]
    path = out_dir / "prompt_evidence_breadth.csv"
    _write_csv(path, rows, ["model", "question_id", "n_unique_canonical_ids"])
    _dump_json_twin(path, rows, json_dir)
    return path


def emit_tool_usage(
    tool_counts_by_model_mode: dict[tuple, Counter],
    out_dir: Path,
    json_dir: Path,
) -> Path:
    rows: list[dict] = []
    for (model, mode), c in sorted(tool_counts_by_model_mode.items()):
        for tool, n in c.most_common():
            if str(tool).startswith("0_"):
                continue
            rows.append({"model": model, "eval_mode": mode, "tool": tool, "n_invocations": n})
    path = out_dir / "tool_usage_distribution.csv"
    _write_csv(path, rows, ["model", "eval_mode", "tool", "n_invocations"])
    _dump_json_twin(path, rows, json_dir)
    return path


def emit_tools_per_support_class(recs: list[ClaimRecord], out_dir: Path, json_dir: Path) -> Path:
    by_ms: dict[tuple, list[int]] = defaultdict(list)
    for r in recs:
        by_ms[(r.model, r.support_class)].append(r.n_tool_snippets)
    rows: list[dict] = []
    for (model, sup), counts in sorted(by_ms.items()):
        rows.append({
            "model": model, "support_class": sup, "n_claims": len(counts),
            "tool_snippets_mean": safe_mean(counts),
            "tool_snippets_median": statistics.median(counts) if counts else float("nan"),
            "tool_snippets_zero_share": sum(1 for c in counts if c == 0) / len(counts) if counts else float("nan"),
        })
    path = out_dir / "tools_per_support_class.csv"
    _write_csv(path, rows, ["model", "support_class", "n_claims", "tool_snippets_mean", "tool_snippets_median", "tool_snippets_zero_share"])
    _dump_json_twin(path, rows, json_dir)
    return path


# ---------------------------------------------------------------------------
# Public orchestrator
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class AggregateOutputs:
    out_dir: Path
    json_dir: Path
    written: dict[str, Path]


__all__ = [
    "AggregateOutputs",
    "BatchSummary",
    "BUCKETS",
    "CLAIM_TYPES",
    "EVAL_MODE_EXPECTED_DOMINANT",
    "NON_FILLER_BUCKETS",
    "SUPPORT_CLASSES",
    "emit_batch_agreement_canonical",
    "emit_pairwise_jaccard_by_model_major_section",
    "emit_batch_agreement_numeric",
    "emit_batch_outliers",
    "emit_batch_stability",
    "emit_best_vs_worst_batch",
    "emit_bucket_rates",
    "emit_canonical_id_frequency",
    "emit_claim_count_by_batch_position",
    "emit_claim_type_share_by_model_major_section",
    "emit_class_marker",
    "emit_coverage_saturation",
    "emit_cross_model_agreement_canonical",
    "emit_cross_model_rank_correlation",
    "emit_eval_mode_profile",
    "emit_position_effects",
    "emit_prompt_difficulty",
    "emit_prompt_evidence_breadth",
    "emit_prompt_instability",
    "emit_support_by_claim_type",
    "emit_tool_usage",
    "emit_tools_per_support_class",
    "emit_verified_share_by_claim_type_model_major_section_matrix",
    "emit_verified_share_by_claim_type_model_major_section",
    "emit_verbosity",
    "jaccard",
    "safe_mean",
    "safe_stdev",
    "summarize_batches",
    "wilson_ci",
]
