"""Revisioned, host-owned workspace for one QueryAgent conversation."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .candidate_schema import (
    DraftAnnotation,
    EquilibriumDraft,
    GateReport,
    ParserAction,
)
from .answer_integrity import answer_turn_summaries
from .excerpt_resolution import resolve_source_excerpts
from .source_grounding import _source_contains, compose_answer_transcript

# Verdict vocabulary of ``statement_review`` (mirrored in the gate service's
# context text).  Host-parsed value rows are information the parser confirms
# or corrects; a review entry is checked for shape and for its row's presence
# in the transcript at write time and is never a gate.
STATEMENT_REVIEW_VERDICTS = (
    "same_quantity_later", "same_quantity_restated", "other_ion",
    "other_conditions", "other_equilibrium", "anchor_citation",
    "not_a_value_statement",
)
STATEMENT_REVIEW_CORRECTABLE = (
    "metal_species", "temperature_C", "ionic_strength_M", "medium",
)
STATEMENT_REVIEW_MIN_ROW_CHARS = 20


def clean_statement_review(value: Any, transcript: str) -> list[dict[str, Any]]:
    """Validate the shape of a ``statement_review`` list against the transcript.

    Each item: ``row`` (a literal prefix of one transcript row, at least
    ``STATEMENT_REVIEW_MIN_ROW_CHARS`` characters, traceable under the same
    normalization as the bound spans), ``verdict`` (one of
    ``STATEMENT_REVIEW_VERDICTS``), optional ``note`` (text) and optional
    ``corrected`` (object with any of ``STATEMENT_REVIEW_CORRECTABLE``).
    Raises ``ValueError`` with a message naming the item and what to fix.
    """

    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise ValueError(
            "statement_review must be a list of objects {row, verdict, note?, "
            f"corrected?}}, not {type(value).__name__}"
        )
    cleaned: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(
                f"statement_review[{index}] must be an object {{row, verdict, "
                "note?, corrected?}"
            )
        row = str(item.get("row") or "").strip()
        verdict = str(item.get("verdict") or "").strip()
        if len(row) < STATEMENT_REVIEW_MIN_ROW_CHARS:
            raise ValueError(
                f"statement_review[{index}].row must be a literal prefix of the "
                f"transcript row of at least {STATEMENT_REVIEW_MIN_ROW_CHARS} "
                "characters, copied as written"
            )
        if not _source_contains(transcript, row):
            raise ValueError(
                f"statement_review[{index}].row {row[:60]!r} is not a span of the "
                "QueryAgent answer: copy the row's opening characters exactly as "
                "they stand in the transcript (latest_statements shows each "
                "row's text)"
            )
        if verdict not in STATEMENT_REVIEW_VERDICTS:
            raise ValueError(
                f"statement_review[{index}].verdict {verdict!r} is not one of "
                + ", ".join(STATEMENT_REVIEW_VERDICTS)
            )
        entry: dict[str, Any] = {"row": row, "verdict": verdict}
        note = item.get("note")
        if note not in (None, ""):
            entry["note"] = str(note).strip()
        corrected = item.get("corrected")
        if corrected not in (None, "", {}):
            if not isinstance(corrected, dict):
                raise ValueError(
                    f"statement_review[{index}].corrected must be an object with "
                    "any of " + ", ".join(STATEMENT_REVIEW_CORRECTABLE)
                )
            unknown = set(corrected) - set(STATEMENT_REVIEW_CORRECTABLE)
            if unknown:
                raise ValueError(
                    f"statement_review[{index}].corrected has unknown keys "
                    f"{sorted(unknown)}; allowed: "
                    + ", ".join(STATEMENT_REVIEW_CORRECTABLE)
                )
            fixed: dict[str, Any] = {}
            for key, raw in corrected.items():
                if raw in (None, ""):
                    fixed[key] = None
                elif key in {"temperature_C", "ionic_strength_M"}:
                    fixed[key] = float(raw)
                else:
                    fixed[key] = str(raw).strip()
            entry["corrected"] = fixed
        cleaned.append(entry)
    return cleaned


def _budget_or_none(value: Any) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, dict) else None


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass
class ParserWorkingState:
    query_id: str
    scope: dict[str, Any]
    request_T_C: float
    request_I_M: float
    base_eq_map_sha256: str
    answer_turns: list[str]
    evidence_snapshot: dict[str, Any]
    initial_answer_sha256: str
    revision: int = 0
    drafts: dict[str, EquilibriumDraft] = field(default_factory=dict)
    annotations: dict[str, DraftAnnotation] = field(default_factory=dict)
    gate_reports: list[GateReport] = field(default_factory=list)
    query_followup_authorizations: list[dict[str, Any]] = field(default_factory=list)
    clarification_history: list[dict[str, Any]] = field(default_factory=list)
    # One record per answer turn: kind (initial / clarification /
    # continuation) and the Argo output budget of the round that wrote it.
    answer_turn_meta: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    terminal_action: ParserAction | None = None
    terminal_reason: str = ""
    terminal_missing_topics: list[str] = field(default_factory=list)
    _next_draft_index: int = field(default=1, repr=False)

    @classmethod
    def create(
        cls,
        *,
        query_id: str,
        scope: dict[str, Any],
        request_T_C: float,
        request_I_M: float,
        base_eq_map_card: dict[str, Any],
        initial_answer: str,
        evidence_snapshot: dict[str, Any],
        initial_output_budget: dict[str, Any] | None = None,
    ) -> "ParserWorkingState":
        answer = str(initial_answer or "").strip()
        return cls(
            query_id=str(query_id),
            scope=dict(scope),
            request_T_C=float(request_T_C),
            request_I_M=float(request_I_M),
            base_eq_map_sha256=canonical_sha256(base_eq_map_card),
            answer_turns=[answer] if answer else [],
            evidence_snapshot=dict(evidence_snapshot or {}),
            initial_answer_sha256=hashlib.sha256(answer.encode("utf-8")).hexdigest(),
            answer_turn_meta=(
                [{"kind": "initial", "output_budget": _budget_or_none(initial_output_budget)}]
                if answer else []
            ),
        )

    def _turn_meta(self) -> list[dict[str, Any]]:
        meta = getattr(self, "answer_turn_meta", None)
        if meta is None:  # workspace pickled before the field existed
            meta = []
            self.answer_turn_meta = meta
        return meta

    @property
    def clarification_rounds_used(self) -> int:
        """Chemistry follow-ups so far.

        The host's reporting turn and its continuations do not count.
        """

        return sum(
            1 for row in self.clarification_history
            if str(row.get("kind") or "clarification") == "clarification"
        )

    @property
    def transcript(self) -> str:
        return compose_answer_transcript(self.answer_turns)

    @property
    def transcript_sha256(self) -> str:
        return hashlib.sha256(self.transcript.encode("utf-8")).hexdigest()

    def answer_turn_summaries(self) -> list[dict[str, Any]]:
        """Per-turn role, size, the Argo output budget and the tail heuristic."""

        return answer_turn_summaries(self.answer_turns, self._turn_meta())

    def _mutated(self, event: str, details: dict[str, Any] | None = None) -> None:
        self.revision += 1
        self.terminal_action = None
        self.terminal_reason = ""
        self.terminal_missing_topics = []
        for draft in self.drafts.values():
            draft.entry_gate_receipt_sha256 = None
            if draft.canonical_equilibrium is not None:
                draft.status = "draft"
        self.events.append({
            "revision": self.revision,
            "event": event,
            "details": dict(details or {}),
        })

    def add_answer_turn(
        self,
        *,
        answer: str,
        evidence_snapshot: dict[str, Any],
        prompt_sha256: str,
        kind: str = "clarification",
        output_budget: dict[str, Any] | None = None,
    ) -> None:
        """Append an accepted QueryAgent turn.

        ``kind`` is ``reporting`` (the host's structured-restatement turn
        after the exploration answer), ``clarification`` (a chemistry
        follow-up the parser asked for) or ``continuation`` (the host asked
        the agent to resume an answer cut at the output cap); only
        clarifications count toward the follow-up budgets.
        """

        value = str(answer or "").strip()
        if not value:
            raise ValueError("follow-up QueryAgent answer is empty")
        kind = str(kind or "clarification")
        if kind not in {"clarification", "continuation", "reporting"}:
            raise ValueError(f"unknown answer turn kind: {kind!r}")
        if self.query_followup_authorizations:
            self.events.append({
                "revision": self.revision,
                "event": "query_followup_authorizations_invalidated",
                "details": {
                    "reason": "query_answer_changed",
                    "receipt_count": len(self.query_followup_authorizations),
                },
            })
            self.query_followup_authorizations.clear()
        self.answer_turns.append(value)
        self._turn_meta().append({
            "kind": kind, "output_budget": _budget_or_none(output_budget),
        })
        self.evidence_snapshot = dict(evidence_snapshot)
        self.clarification_history.append({
            "round": len(self.clarification_history) + 1,
            "kind": kind,
            "prompt_sha256": prompt_sha256,
            "answer_sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
        })
        self._mutated("query_followup_added", {
            "answer_turn": len(self.answer_turns),
            "kind": kind,
        })

    def create_draft(self, fields: dict[str, Any]) -> EquilibriumDraft:
        draft_id = f"d{self._next_draft_index:03d}"
        draft = EquilibriumDraft(draft_id=draft_id)
        fields, resolution = self._with_resolved_excerpts(fields)
        self._apply_fields(draft, self._with_clean_statement_review(fields))
        self._note_resolved_excerpts(draft, fields, resolution)
        self.drafts[draft_id] = draft
        self._next_draft_index += 1
        self._mutated("draft_created", {"draft_id": draft_id})
        return draft

    def update_draft(self, draft_id: str, fields: dict[str, Any]) -> EquilibriumDraft:
        key = str(draft_id)
        try:
            current = self.drafts[key]
        except KeyError as exc:
            raise ValueError(f"unknown draft_id {draft_id!r}") from exc
        draft = deepcopy(current)
        fields, resolution = self._with_resolved_excerpts(fields)
        self._apply_fields(draft, self._with_clean_statement_review(fields))
        self._note_resolved_excerpts(draft, fields, resolution)
        self.drafts[key] = draft
        self._mutated("draft_updated", {"draft_id": draft.draft_id})
        return draft

    def _with_resolved_excerpts(
        self, fields: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Let the host copy an answer line the parser only pointed at.

        A row-bound excerpt sent as the opening characters of exactly one
        table row / reaction line, or any excerpt that closely resembles
        exactly one answer line, is replaced by that line before the draft
        stores it (see excerpt_resolution).  The parser's other values are
        untouched; the gates check the stored span literally as before.
        """

        excerpts = fields.get("source_excerpts")
        if not isinstance(excerpts, dict):
            return fields, {"resolved": {}, "unresolved": {}}
        patched, resolved, unresolved = resolve_source_excerpts(
            excerpts, self.transcript
        )
        out = dict(fields)
        out["source_excerpts"] = patched
        return out, {"resolved": resolved, "unresolved": unresolved}

    def _note_resolved_excerpts(
        self,
        draft: EquilibriumDraft,
        fields: dict[str, Any],
        resolution: dict[str, Any],
    ) -> None:
        """Record on the draft which stored excerpts the host resolved.

        Every key the parser re-sends drops its earlier note (a literal span
        or a deletion replaces the host's copy); the notes of this call are
        added.  ``last_excerpt_resolution`` lets the create/update receipt
        tell the parser what the host stored in this very call.
        """

        excerpts = fields.get("source_excerpts")
        if isinstance(excerpts, dict):
            notes = dict(draft.host_resolved_excerpts)
            for key in excerpts:
                for label in [
                    label for label in notes
                    if label == key or label.startswith(key + "[")
                ]:
                    notes.pop(label, None)
            notes.update(resolution.get("resolved") or {})
            draft.host_resolved_excerpts = notes
        self.last_excerpt_resolution = {"draft_id": draft.draft_id, **resolution}

    def _with_clean_statement_review(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Validate ``statement_review`` against this workspace's transcript."""

        if not isinstance(fields, dict) or "statement_review" not in fields:
            return fields
        cleaned = dict(fields)
        cleaned["statement_review"] = clean_statement_review(
            fields["statement_review"], self.transcript,
        )
        return cleaned

    def discard_draft(self, draft_id: str) -> None:
        if draft_id not in self.drafts:
            raise ValueError(f"unknown draft_id {draft_id!r}")
        del self.drafts[draft_id]
        dropped_annotation = self.annotations.pop(draft_id, None) is not None
        self._mutated("draft_discarded", {
            "draft_id": draft_id,
            "annotation_dropped": dropped_annotation,
        })

    def set_annotation(self, annotation: DraftAnnotation) -> None:
        """Store one gate-validated annotation without advancing the revision.

        The annotation is not draft content: it never enters entry-gate
        receipts, so storing or overwriting one must not clear receipts or
        invalidate a passed network gate.  Liveness is enforced through the
        bound entry receipt instead.
        """

        if annotation.draft_id not in self.drafts:
            raise ValueError(f"unknown draft_id {annotation.draft_id!r}")
        self.annotations[annotation.draft_id] = annotation
        self.events.append({
            "revision": self.revision,
            "event": "draft_annotated",
            "details": {
                "draft_id": annotation.draft_id,
                "annotation_sha256": annotation.annotation_sha256,
            },
        })

    def rebind_annotation(
        self, draft_id: str, *, entry_receipt_sha256: str, canonical_sha256_value: str
    ) -> None:
        """Rebind a dangling annotation after a re-seal of unchanged content.

        Every draft mutation clears all entry receipts, so annotations on
        untouched drafts dangle until the next entry-gate seal.  When the
        re-sealed canonical content digest matches the digest the annotation
        was written against, the annotation transparently follows the new
        receipt; when content changed, it stays stale and must be rewritten.
        """

        annotation = self.annotations.get(draft_id)
        if annotation is None:
            return
        if annotation.bound_canonical_sha256 != canonical_sha256_value:
            return
        if annotation.bound_entry_receipt_sha256 == entry_receipt_sha256:
            return
        annotation.bound_entry_receipt_sha256 = entry_receipt_sha256
        self.events.append({
            "revision": self.revision,
            "event": "annotation_rebound",
            "details": {
                "draft_id": draft_id,
                "annotation_sha256": annotation.annotation_sha256,
            },
        })

    def annotation_liveness(self, draft_id: str) -> str:
        """Return unannotated, annotated, or stale for one existing draft."""

        annotation = self.annotations.get(draft_id)
        if annotation is None:
            return "unannotated"
        draft = self.drafts.get(draft_id)
        receipt = draft.entry_gate_receipt_sha256 if draft is not None else None
        if receipt is not None and receipt == annotation.bound_entry_receipt_sha256:
            return "annotated"
        return "stale"

    @staticmethod
    def _apply_fields(draft: EquilibriumDraft, fields: dict[str, Any]) -> None:
        allowed = {
            "beta_definition_id", "constant_value", "evidence_vlm_ids",
            "evidence_network_ids", "evidence_citation_ids",
            "uncertainty_log10", "estimation_method", "assumptions",
            "rationale", "source_excerpts", "topology_species_mapping",
            "statement_review",
        }
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"parser cannot write host-owned fields: {sorted(unknown)}")
        excerpts_before = dict(draft.source_excerpts)
        for key, value in fields.items():
            if key in {
                "beta_definition_id",
            }:
                value = None if value in (None, "") else int(value)
            elif key == "topology_species_mapping":
                if value in (None, ""):
                    value = {}
                elif not isinstance(value, dict):
                    raise ValueError(
                        "topology_species_mapping must be an object mapping each "
                        "written species of topology_excerpt to one canonical "
                        "SRD-46 species token (or \"(solvent)\" for spectator "
                        f"water), not {type(value).__name__}"
                    )
                else:
                    cleaned: dict[str, str] = {}
                    for raw_key, raw_token in value.items():
                        written = str(raw_key or "").strip()
                        token = (
                            "" if raw_token is None else str(raw_token).strip()
                        )
                        if not written or not token:
                            raise ValueError(
                                "topology_species_mapping keys and values must "
                                "be non-empty strings"
                            )
                        cleaned[written] = token
                    value = cleaned
            elif key == "statement_review":
                # Already validated against the transcript by the caller
                # (create_draft / update_draft); a direct call gets the
                # shape check without traceability.
                value = (
                    list(value) if isinstance(value, list)
                    else clean_statement_review(value, "")
                )
            elif key in {"constant_value", "uncertainty_log10"}:
                value = None if value in (None, "") else float(value)
            elif key in {
                "evidence_vlm_ids", "evidence_network_ids",
                "evidence_citation_ids",
            }:
                if not isinstance(value, list):
                    raise ValueError(f"{key} must be a list")
                value = [int(item) for item in value]
            elif key == "assumptions":
                if not isinstance(value, list):
                    raise ValueError("assumptions must be a list")
                value = [str(item).strip() for item in value if str(item).strip()]
            elif key == "source_excerpts":
                if not isinstance(value, dict):
                    raise ValueError("source_excerpts must be an object")
                allowed_excerpt_keys = {
                    "topology_excerpt",
                    "beta_definition_excerpt",
                    "constant_value_excerpt",
                    "uncertainty_excerpt",
                    "evidence_excerpt",
                    "estimation_method_excerpt",
                    "assumption_excerpts",
                    "rationale_excerpt",
                }
                unknown_excerpt_keys = set(value) - allowed_excerpt_keys
                if unknown_excerpt_keys:
                    raise ValueError(
                        "source_excerpts contains unknown keys: "
                        f"{sorted(unknown_excerpt_keys)}; allowed keys are "
                        f"{sorted(allowed_excerpt_keys)}"
                    )
                # Merge per excerpt key so fixing one span never wipes the rest.
                merged = dict(draft.source_excerpts)
                for excerpt_key, excerpt_value in value.items():
                    if excerpt_value is None:
                        merged.pop(excerpt_key, None)
                        continue
                    if excerpt_key == "assumption_excerpts":
                        if not isinstance(excerpt_value, list) or any(
                            not isinstance(item, str) for item in excerpt_value
                        ):
                            raise ValueError(
                                "source_excerpts.assumption_excerpts must be a "
                                "list of strings (got "
                                f"{type(excerpt_value).__name__}); wrap each "
                                "assumption span as its own quoted string, or "
                                "send null to delete the stored list"
                            )
                    elif not isinstance(excerpt_value, str):
                        raise ValueError(
                            f"source_excerpts.{excerpt_key} must be a string "
                            f"(got {type(excerpt_value).__name__}); pass one "
                            "contiguous quoted span copied from the QueryAgent "
                            "answer, or send null to delete the stored excerpt "
                            "— never a list or an object. Omitted keys keep "
                            "their stored spans"
                        )
                    merged[excerpt_key] = excerpt_value
                value = merged
            elif key in {"estimation_method", "rationale"}:
                value = str(value or "").strip()
            setattr(draft, key, value)
        ParserWorkingState._copy_values_from_excerpts(draft, fields, excerpts_before)
        draft.canonical_equilibrium = None
        draft.topology_resolution = None
        draft.entry_gate_receipt_sha256 = None
        draft.status = "draft"

    @staticmethod
    def _copy_values_from_excerpts(
        draft: EquilibriumDraft,
        fields: dict[str, Any],
        excerpts_before: dict[str, Any],
    ) -> None:
        """Host copies: an omitted value is its whole excerpt.

        Source binding only requires the value to be contained in its span,
        so the parser never has to retype a long reasoning chain twice (the
        blind testers' payloads were ~70 % repeated text).  A value the parser
        wrote explicitly is kept; a value the host copied from an earlier span
        follows the span when the span is re-pointed.
        """

        def explicit(key: str) -> bool:
            return key in fields and fields[key] not in (None, "", [])

        for value_key, excerpt_key in (
            ("estimation_method", "estimation_method_excerpt"),
            ("rationale", "rationale_excerpt"),
        ):
            if explicit(value_key):
                continue
            span = draft.source_excerpts.get(excerpt_key)
            if not isinstance(span, str) or not span.strip():
                continue
            current = getattr(draft, value_key)
            previous = excerpts_before.get(excerpt_key)
            if not current or (
                isinstance(previous, str) and current == previous.strip()
            ):
                setattr(draft, value_key, span.strip())
        if explicit("assumptions"):
            return
        spans = draft.source_excerpts.get("assumption_excerpts")
        if not isinstance(spans, list) or not spans or any(
            not isinstance(span, str) or not span.strip() for span in spans
        ):
            return
        previous_spans = excerpts_before.get("assumption_excerpts")
        previous_values = (
            [str(span).strip() for span in previous_spans]
            if isinstance(previous_spans, list) else None
        )
        if not draft.assumptions or draft.assumptions == previous_values:
            draft.assumptions = [span.strip() for span in spans]

    def record_report(self, report: GateReport) -> None:
        self.gate_reports.append(report)

    def authorize_query_followup(
        self,
        *,
        report: GateReport,
        topics: list[str],
        issues: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Persist a gate-owned gap against immutable QueryAgent source state.

        Draft edits and discards advance ``revision`` but cannot add chemistry
        to the QueryAgent transcript.  Consequently this receipt is bound to
        the transcript and evidence snapshot rather than to the mutable draft
        revision.  A later QueryAgent answer invalidates all such receipts.
        """

        normalized_topics = sorted({
            str(value).strip() for value in topics if str(value).strip()
        })
        if not normalized_topics:
            raise ValueError("query follow-up authorization requires topics")
        payload = {
            "query_id": self.query_id,
            "gate": report.gate,
            "gate_state_revision": report.state_revision,
            "transcript_sha256": self.transcript_sha256,
            "evidence_snapshot_sha256": canonical_sha256(self.evidence_snapshot),
            "base_eq_map_sha256": self.base_eq_map_sha256,
            "scope_sha256": canonical_sha256(self.scope),
            "topics": normalized_topics,
            "issues": list(issues),
        }
        receipt = dict(payload)
        receipt["receipt_sha256"] = canonical_sha256(payload)
        if not any(
            row.get("receipt_sha256") == receipt["receipt_sha256"]
            for row in self.query_followup_authorizations
        ):
            self.query_followup_authorizations.append(receipt)
            self.events.append({
                "revision": self.revision,
                "event": "query_followup_authorized",
                "details": {
                    "gate": report.gate,
                    "topics": normalized_topics,
                    "receipt_sha256": receipt["receipt_sha256"],
                },
            })
        return receipt

    def active_query_followup_authorizations(self) -> list[dict[str, Any]]:
        """Return intact receipts for the unchanged QueryAgent source state."""

        transcript_sha256 = self.transcript_sha256
        evidence_sha256 = canonical_sha256(self.evidence_snapshot)
        scope_sha256 = canonical_sha256(self.scope)
        active: list[dict[str, Any]] = []
        for receipt in self.query_followup_authorizations:
            payload = {
                key: value
                for key, value in receipt.items()
                if key != "receipt_sha256"
            }
            if canonical_sha256(payload) != receipt.get("receipt_sha256"):
                continue
            if receipt.get("query_id") != self.query_id:
                continue
            if receipt.get("transcript_sha256") != transcript_sha256:
                continue
            if receipt.get("evidence_snapshot_sha256") != evidence_sha256:
                continue
            if receipt.get("base_eq_map_sha256") != self.base_eq_map_sha256:
                continue
            if receipt.get("scope_sha256") != scope_sha256:
                continue
            active.append(deepcopy(receipt))
        return active

    def set_terminal(
        self, action: ParserAction, reason: str = "", missing_topics: list[str] | None = None
    ) -> None:
        self.terminal_action = action
        self.terminal_reason = str(reason or "").strip()
        self.terminal_missing_topics = sorted({
            str(value).strip() for value in (missing_topics or []) if str(value).strip()
        })
        self.events.append({
            "revision": self.revision,
            "event": "parser_cycle_finished",
            "details": {
                "action": action.value,
                "reason": self.terminal_reason,
                "missing_topics": self.terminal_missing_topics,
            },
        })

    def as_dict(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "scope": self.scope,
            "request_temperature_C": self.request_T_C,
            "request_ionic_strength_M": self.request_I_M,
            "base_eq_map_sha256": self.base_eq_map_sha256,
            "initial_answer_sha256": self.initial_answer_sha256,
            "transcript_sha256": self.transcript_sha256,
            "n_answer_turns": len(self.answer_turns),
            "answer_turns": self.answer_turn_summaries(),
            "revision": self.revision,
            "drafts": [draft.as_dict() for draft in self.drafts.values()],
            "annotations": [
                {
                    **annotation.as_dict(),
                    "liveness": self.annotation_liveness(annotation.draft_id),
                }
                for annotation in self.annotations.values()
            ],
            "gate_reports": [report.as_dict() for report in self.gate_reports],
            "query_followup_authorizations": [
                deepcopy(receipt) for receipt in self.query_followup_authorizations
            ],
            "clarification_history": list(self.clarification_history),
            "events": list(self.events),
            "terminal_action": (
                None if self.terminal_action is None else self.terminal_action.value
            ),
            "terminal_reason": self.terminal_reason,
            "terminal_missing_topics": list(self.terminal_missing_topics),
        }


__all__ = ["ParserWorkingState", "canonical_sha256"]
