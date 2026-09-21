"""Walk ``_output_eval/Model_*/Q*/claims_batch*.json`` and flatten into rows.

One row per claim. Stdlib only (json/csv) — pandas is optional and only used
downstream for analysis.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

_WORKSPACE_ROOT = Path(__file__).absolute().parents[4]
_QUERY_OUTPUT_ROOT = _WORKSPACE_ROOT / "_output" / "Query"
_QUERY_EVAL_ROOT = _QUERY_OUTPUT_ROOT / "_evaluation"

from .prompt_registry import EVAL_MODE_BY_PREFIX, load_prompt_registry  # noqa: F401
from .section_policy import DEFAULT_SECTION_POLICY, SectionPolicy

# ---------------------------------------------------------------------------
# Bucket taxonomy (verified / domain / unverified / filler)
# ---------------------------------------------------------------------------

BUCKETS = ("verified", "domain", "unverified", "filler")

BUCKET_BY_SUPPORT = {
    "direct": "verified",
    "inferred": "verified",
    "domain_knowledge": "domain",
    "unsupported": "unverified",
    "no_tool_data": "unverified",
}

# Filler claim_type overrides whatever the grounder said (it is always
# ``no_tool_data`` by design, but reporting filler as its own bucket keeps the
# verified/domain/unverified denominators clean).
FILLER_CLAIM_TYPE = "filler"

CLAIMS_FILE_RE = re.compile(r"^claims_batch(?P<batch>\d+)\.json$")
MODEL_DIR_RE = re.compile(r"^Model_(?P<model>.+)$")
QUESTION_DIR_RE = re.compile(r"^Q(?P<qid>[\d.]+)$")

DEFAULT_OUTPUT_EVAL = _QUERY_EVAL_ROOT


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class ClaimRecord:
    """One row per claim across the entire corpus."""

    model: str
    question_id: str
    section: str
    section_title: str
    eval_mode: str
    batch: int
    paragraph_index: int
    claim_index: int
    claim_type: str
    support_class: str
    bucket: str
    n_canonical_ids: int
    n_tool_snippets: int
    evidence_present: bool
    text_len: int
    cache_format: int
    classifier_strategy_version: str
    classifier_model: str
    grounder_model: str
    complete: bool
    source_path: str
    major_section: str = ""


@dataclass(slots=True)
class IncompleteBatch:
    model: str
    question_id: str
    batch: int
    reason: str
    source_path: str


@dataclass(slots=True)
class LoadResult:
    records: list[ClaimRecord] = field(default_factory=list)
    incomplete: list[IncompleteBatch] = field(default_factory=list)
    unknown_questions: list[tuple[str, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def _bucket_for(claim_type: str, support_class: str) -> str:
    if claim_type == FILLER_CLAIM_TYPE:
        return "filler"
    return BUCKET_BY_SUPPORT.get(support_class, "unverified")


def _iter_batch_files(root: Path) -> Iterator[tuple[str, str, int, Path]]:
    """Yield (model, question_id, batch, path) tuples.

    Skips any directory under the eval root whose name is not ``Model_<x>`` —
    in particular this excludes ``backup*`` siblings.
    """
    if not root.exists():
        return
    for model_dir in sorted(root.iterdir()):
        if not model_dir.is_dir():
            continue
        m = MODEL_DIR_RE.match(model_dir.name)
        if not m:
            continue
        model = m.group("model")
        for q_dir in sorted(model_dir.iterdir()):
            if not q_dir.is_dir():
                continue
            qm = QUESTION_DIR_RE.match(q_dir.name)
            if not qm:
                continue
            question_id = f"Q{qm.group('qid')}"
            for f in sorted(q_dir.iterdir()):
                fm = CLAIMS_FILE_RE.match(f.name)
                if not fm:
                    continue
                yield model, question_id, int(fm.group("batch")), f


def _load_one(
    model: str,
    question_id: str,
    batch: int,
    path: Path,
    registry: dict,
    section_policy: SectionPolicy,
    result: LoadResult,
) -> None:
    try:
        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        result.incomplete.append(
            IncompleteBatch(model, question_id, batch, f"unreadable: {exc}", str(path))
        )
        return

    complete = bool(payload.get("complete", False))
    if not complete:
        result.incomplete.append(
            IncompleteBatch(model, question_id, batch, "complete=false", str(path))
        )
        return

    spec = registry.get(question_id)
    if spec is None:
        result.unknown_questions.append((question_id, str(path)))
        section = "?"
        section_title = "?"
        eval_mode = "unknown"
        major_section = "?"
    else:
        section = section_policy.group_section(spec.section)
        section_title = section_policy.group_title(spec.section, spec.section_title)
        eval_mode = spec.eval_mode
        major_section = section_policy.group_major_section(spec.section)

    cache_format = int(payload.get("cache_format", 0) or 0)
    classifier_strategy_version = str(payload.get("classifier_strategy_version", ""))
    classifier_model = str(payload.get("classifier_model", ""))
    grounder_model = str(payload.get("grounder_model", ""))

    doc = payload.get("doc") or {}
    paragraphs = doc.get("paragraphs") or []
    for paragraph in paragraphs:
        p_idx = int(paragraph.get("paragraph_index", 0))
        claims = paragraph.get("claims") or []
        grounded = paragraph.get("grounded_claims") or []
        grounded_by_idx = {int(g.get("claim_index", i)): g for i, g in enumerate(grounded)}

        for c_idx, claim in enumerate(claims):
            claim_type = str(claim.get("claim_type", "filler"))
            text = str(claim.get("text", ""))
            g = grounded_by_idx.get(c_idx, {})
            support_class = str(g.get("support_class", "no_tool_data"))
            canonical_ids = g.get("canonical_ids") or []
            tool_snippets = g.get("tool_snippets") or []
            evidence_snippet = str(g.get("evidence_snippet", ""))
            bucket = _bucket_for(claim_type, support_class)

            result.records.append(
                ClaimRecord(
                    model=model,
                    question_id=question_id,
                    section=section,
                    section_title=section_title,
                    eval_mode=eval_mode,
                    batch=batch,
                    paragraph_index=p_idx,
                    claim_index=c_idx,
                    claim_type=claim_type,
                    support_class=support_class,
                    bucket=bucket,
                    n_canonical_ids=len(canonical_ids),
                    n_tool_snippets=len(tool_snippets),
                    evidence_present=bool(evidence_snippet.strip()),
                    text_len=len(text),
                    cache_format=cache_format,
                    classifier_strategy_version=classifier_strategy_version,
                    classifier_model=classifier_model,
                    grounder_model=grounder_model,
                    complete=complete,
                    source_path=str(path),
                    major_section=major_section,
                )
            )


def iter_claim_records(
    root: str | Path | None = None,
    *,
    include_models: Iterable[str] | None = None,
    include_questions: Iterable[str] | None = None,
    include_sections: Iterable[str] | None = None,
    registry: dict | None = None,
    section_policy: SectionPolicy | None = None,
) -> LoadResult:
    """Walk the eval root and return a :class:`LoadResult`.

    Parameters
    ----------
    root
        Defaults to the repository-local query evaluation directory.
    include_models, include_questions, include_sections
        Optional whitelists; ``None`` keeps everything.
    registry
        Pre-loaded prompt registry; loaded from ``TEST_PROMPTS.md`` if absent.
    """
    eval_root = Path(root) if root else DEFAULT_OUTPUT_EVAL
    registry = registry if registry is not None else load_prompt_registry()
    policy = section_policy or DEFAULT_SECTION_POLICY
    model_set = set(include_models) if include_models else None
    q_set = set(include_questions) if include_questions else None
    sec_set = set(include_sections) if include_sections else None

    result = LoadResult()
    for model, question_id, batch, path in _iter_batch_files(eval_root):
        if model_set is not None and model not in model_set:
            continue
        if q_set is not None and question_id not in q_set:
            continue
        spec = registry.get(question_id)
        if spec is not None and not policy.include_raw_section(spec.section):
            continue
        if sec_set is not None:
            if spec is None or not policy.matches_requested_sections(spec.section, sec_set):
                continue
        _load_one(model, question_id, batch, path, registry, policy, result)
    return result


def load_long_table(
    root: str | Path | None = None,
    **kwargs,
) -> LoadResult:
    """Convenience alias for :func:`iter_claim_records`."""
    return iter_claim_records(root, **kwargs)


# ---------------------------------------------------------------------------
# CSV writers
# ---------------------------------------------------------------------------

_CLAIM_FIELDS = list(ClaimRecord.__slots__)
_INCOMPLETE_FIELDS = list(IncompleteBatch.__slots__)


def write_long_csv(records: list[ClaimRecord], path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_CLAIM_FIELDS)
        writer.writeheader()
        for rec in records:
            writer.writerow(asdict(rec))
    return out


def write_incomplete_csv(rows: list[IncompleteBatch], path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_INCOMPLETE_FIELDS)
        writer.writeheader()
        for rec in rows:
            writer.writerow(asdict(rec))
    return out


# ---------------------------------------------------------------------------
# Payload-extras scanner (canonical_ids, tool names, claim text)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class PayloadExtras:
    """Side data needed by Phase 2 that doesn't fit on :class:`ClaimRecord`.

    Attributes
    ----------
    canonical_by_batch
        ``(model, question_id, batch) -> set of canonical_ids cited``.
    tools_by_model_mode
        ``(model, eval_mode) -> Counter of tool names invoked``.
    claim_texts
        ``(model, question_id, batch) -> {(p_idx, c_idx): claim_text}``.
    """

    canonical_by_batch: dict[tuple, set] = field(default_factory=dict)
    tools_by_model_mode: dict[tuple, "Counter"] = field(default_factory=dict)  # noqa: F821
    claim_texts: dict[tuple, dict] = field(default_factory=dict)


def scan_payload_extras(
    root: str | Path | None = None,
    *,
    include_models: Iterable[str] | None = None,
    include_questions: Iterable[str] | None = None,
    include_sections: Iterable[str] | None = None,
    registry: dict | None = None,
    section_policy: SectionPolicy | None = None,
) -> PayloadExtras:
    """Second pass over the same files producing canonical_ids / tool / text maps."""
    from collections import Counter

    eval_root = Path(root) if root else DEFAULT_OUTPUT_EVAL
    registry = registry if registry is not None else load_prompt_registry()
    policy = section_policy or DEFAULT_SECTION_POLICY
    model_set = set(include_models) if include_models else None
    q_set = set(include_questions) if include_questions else None
    sec_set = set(include_sections) if include_sections else None

    extras = PayloadExtras()
    for model, qid, batch, path in _iter_batch_files(eval_root):
        if model_set is not None and model not in model_set:
            continue
        if q_set is not None and qid not in q_set:
            continue
        spec = registry.get(qid)
        eval_mode = spec.eval_mode if spec else "unknown"
        if spec is not None and not policy.include_raw_section(spec.section):
            continue
        if sec_set is not None and (spec is None or not policy.matches_requested_sections(spec.section, sec_set)):
            continue

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not payload.get("complete"):
            continue

        key = (model, qid, batch)
        canon: set[str] = set()
        tools: "Counter[str]" = Counter()
        texts: dict[tuple, str] = {}

        for paragraph in (payload.get("doc") or {}).get("paragraphs") or []:
            p_idx = int(paragraph.get("paragraph_index", 0))
            for c_idx, claim in enumerate(paragraph.get("claims") or []):
                texts[(p_idx, c_idx)] = str(claim.get("text", ""))
            for g in paragraph.get("grounded_claims") or []:
                for cid in g.get("canonical_ids") or []:
                    canon.add(str(cid))
                for ts in g.get("tool_snippets") or []:
                    t = ts.get("tool")
                    if t:
                        tools[str(t)] += 1

        extras.canonical_by_batch[key] = canon
        extras.claim_texts[key] = texts
        mm_key = (model, eval_mode)
        if mm_key not in extras.tools_by_model_mode:
            extras.tools_by_model_mode[mm_key] = Counter()
        extras.tools_by_model_mode[mm_key].update(tools)

    return extras


__all__ = [
    "BUCKETS",
    "BUCKET_BY_SUPPORT",
    "ClaimRecord",
    "DEFAULT_OUTPUT_EVAL",
    "IncompleteBatch",
    "LoadResult",
    "PayloadExtras",
    "iter_claim_records",
    "load_long_table",
    "scan_payload_extras",
    "write_incomplete_csv",
    "write_long_csv",
]
