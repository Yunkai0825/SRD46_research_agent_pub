"""What the host already holds from the QueryAgent's answers (follow-up prompts).

A chemistry clarification tells the QueryAgent which of its own statements
the host already holds, so it adds only what is missing instead of re-emitting
the whole report. Every row quotes the agent's own span - the reaction as it
wrote it - and the numbers the parser bound from that answer. Nothing
host-owned goes in: no resolved beta id, no canonical equation or catalog
name, so the Query side still sees no SRD-46 notation.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

# Bounds on what one clarification prompt carries.
HELD_DIGEST_MAX_ROWS = 12
HELD_STATEMENT_CHARS = 160

# Draft content -> the clarification topic that content satisfies.  The
# excerpt alternative covers drafts where the host copies the value from the
# span (estimation_method, assumptions and rationale may be omitted).
_HELD_FIELD_TOPICS = (
    ("constant_value", None, "estimated_log10_K"),
    ("uncertainty_log10", None, "uncertainty"),
    ("estimation_method", "estimation_method_excerpt", "estimation_method"),
    ("assumptions", "assumption_excerpts", "assumptions"),
    ("rationale", "rationale_excerpt", "rationale"),
    ("evidence_vlm_ids", "evidence_excerpt", "supporting_evidence"),
)
# The agent's own statement of the equilibrium, in order of preference.
_STATEMENT_KEYS = ("topology_excerpt", "constant_value_excerpt", "beta_definition_excerpt")


def _collapse(text: Any, limit: int = HELD_STATEMENT_CHARS) -> str:
    collapsed = " ".join(str(text or "").split())
    if len(collapsed) > limit:
        collapsed = collapsed[: limit - 1].rstrip() + "…"
    return collapsed


def _present(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, (str, list, tuple, dict)):
        return len(value) > 0
    return True


def _topics_by_draft(receipts: Iterable[Mapping[str, Any]]) -> dict[str, set[str]]:
    """Missing topics per draft, from the issues inside the active receipts."""

    by_draft: dict[str, set[str]] = {}
    for receipt in receipts:
        for issue in receipt.get("issues") or []:
            if not isinstance(issue, Mapping):
                continue
            draft_id = issue.get("draft_id")
            if not draft_id:
                continue
            by_draft.setdefault(str(draft_id), set()).update(
                str(topic) for topic in (issue.get("missing_topics") or []) if str(topic)
            )
    return by_draft


def build_held_digest(state: Any, *, missing_topics: Iterable[str]) -> list[dict[str, Any]]:
    """Rows for ``render_query_clarification(held=...)`` from the parser drafts.

    One row per draft that carries the agent's own statement of its
    equilibrium (``topology_excerpt``, else the constant or beta-token span):
    the statement, the bound value and uncertainty, the topics the draft
    already holds, and the topics still missing for that draft (from the
    receipt issues naming it; the global topics when there is one draft).
    Drafts without such a span are not mentioned: the host holds nothing
    quotable for them.  Host-owned fields (``beta_definition_id``,
    ``canonical_equilibrium``, ``topology_resolution``) are never read.
    """

    topics = sorted({str(value).strip() for value in missing_topics if str(value).strip()})
    try:
        receipts = list(state.active_query_followup_authorizations())
    except Exception:  # a minimal state double without receipts
        receipts = []
    by_draft = _topics_by_draft(receipts)
    drafts = list((getattr(state, "drafts", None) or {}).values())
    rows: list[dict[str, Any]] = []
    for draft in drafts:
        excerpts = getattr(draft, "source_excerpts", None) or {}
        statement = next(
            (_collapse(excerpts.get(key)) for key in _STATEMENT_KEYS if excerpts.get(key)),
            "",
        )
        if not statement:
            continue
        draft_id = str(getattr(draft, "draft_id", ""))
        named = sorted(by_draft.get(draft_id, set()))
        if named:
            draft_missing = [topic for topic in named if topic in topics] or named
        elif len(drafts) == 1:
            draft_missing = list(topics)
        else:
            draft_missing = []
        excluded = set(topics) | set(draft_missing)
        held_topics = []
        for attr, excerpt_key, topic in _HELD_FIELD_TOPICS:
            value = getattr(draft, attr, None)
            if not _present(value) and excerpt_key:
                value = excerpts.get(excerpt_key)
            if _present(value) and topic not in excluded:
                held_topics.append(topic)
        constant = getattr(draft, "constant_value", None)
        uncertainty = getattr(draft, "uncertainty_log10", None)
        rows.append({
            "draft_id": draft_id,
            "status": str(getattr(draft, "status", "") or ""),
            "statement": statement,
            "value": float(constant) if _present(constant) else None,
            "uncertainty": float(uncertainty) if _present(uncertainty) else None,
            "held_topics": held_topics,
            "missing_topics": draft_missing,
        })
        if len(rows) >= HELD_DIGEST_MAX_ROWS:
            break
    return rows


__all__ = ["HELD_DIGEST_MAX_ROWS", "HELD_STATEMENT_CHARS", "build_held_digest"]
