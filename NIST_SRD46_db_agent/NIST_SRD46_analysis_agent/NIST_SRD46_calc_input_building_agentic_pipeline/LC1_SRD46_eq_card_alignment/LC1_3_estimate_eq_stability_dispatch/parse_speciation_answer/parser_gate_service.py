"""Deterministic entry and whole-network gates for parser-created drafts."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

from ..dispatch_srd46_query.clarification_renderer import KNOWN_CLARIFICATION_TOPICS
from .candidate_schema import (
    DraftAnnotation,
    EquilibriumDraft,
    GateIssue,
    GateOwner,
    GateReport,
    ParsedQuery,
    ParserAction,
)
from .canonical_topology import (
    TopologyResolutionError,
    closest_canonical_candidates,
    resolve_canonical_topology,
)
from .evidence_gate import EvidenceGateError, validate_evidence_snapshot
from .no_estimate_conclusion import has_no_estimate_conclusion
from .parser_working_state import ParserWorkingState, canonical_sha256
from .source_grounding import (
    SourceGroundingError,
    _bind_number,
    validate_draft_source_bindings,
)
from .srd46_catalog import Catalog, DEFAULT_CATALOG


_TOPIC_PATTERNS = {
    "target_equilibrium_definition": re.compile(
        r"(?i)(?:\bbeta_def_\d+\b|<=>|<->|⇌|↔|⇄)"
    ),
    "estimated_log10_K": re.compile(
        r"(?i)(?:estimated?|recommend(?:ed)?)\D{0,80}"
        r"(?:log(?:10)?\s*(?:K|beta|β)|constant)"
    ),
    "uncertainty": re.compile(
        r"(?i)(?:\buncertaint\w*\D{0,24}\d|\d\D{0,24}\buncertaint)"
    ),
    "estimation_method": re.compile(
        r"(?i)\b(?:method|route|basis|reasoning|analogue|analog|transfer|"
        r"estimated\s+from)\b"
    ),
    "assumptions": re.compile(r"(?i)\bassum"),
    "rationale": re.compile(r"(?i)\b(?:rationale|because|weaker|stronger)\b"),
    "supporting_evidence": re.compile(r"(?i)\bvlm_\d+\b"),
}

_ANSWER_ID_PATTERNS = {
    "beta_definition_ids": re.compile(r"(?i)\bbeta_def_(\d+)\b"),
    "vlm_ids": re.compile(r"(?i)\bvlm_(\d+)\b"),
    "network_ids": re.compile(r"(?i)\bref_eq_net_(\d+)\b"),
    "literature_ids": re.compile(r"(?i)\blit_(\d+)\b"),
}

_SNAPSHOT_ID_KEYS = {
    "beta_definition_ids": "observed_beta_definition_ids",
    "vlm_ids": "observed_vlm_ids",
    "network_ids": "observed_network_ids",
    "literature_ids": "observed_literature_ids",
}

_SOURCE_EXCERPT_CONTRACT = {
    "topology_excerpt": (
        "preferred: one contiguous answer span containing exactly one stated "
        "reaction; the host resolves it to a canonical beta definition"
    ),
    "beta_definition_excerpt": (
        "legacy alternative used only when no topology_excerpt is supplied: "
        "one contiguous answer span containing beta_def_<id>"
    ),
    "constant_value_excerpt": (
        "one contiguous answer span containing beta_def_<id> and "
        "constant_value"
    ),
    "uncertainty_excerpt": (
        "one contiguous answer span containing uncertainty_log10; in "
        "a multi-beta answer it must also contain beta_def_<id>"
    ),
    "evidence_excerpt": (
        "one contiguous answer span containing every cited vlm_N, "
        "ref_eq_net_N, and lit_N identifier"
    ),
    "estimation_method_excerpt": (
        "one contiguous answer span from which estimation_method is copied"
    ),
    "assumption_excerpts": (
        "list of contiguous answer spans corresponding one-to-one "
        "with assumptions"
    ),
    "rationale_excerpt": (
        "one contiguous answer span from which rationale is copied"
    ),
}

# The annotation is the parser's own labeled digest, so unlike draft fields it
# is not excerpt-bound; these deterministic checks keep it anchored to the
# committed value and to evidence the session actually authorized.
_ANNOTATION_PAYLOAD_KEYS = {"discussion", "core_source_ids", "secondary_source_ids"}
_ANNOTATION_ID_PREFIXES = {
    "vlm_ids": "vlm",
    "network_ids": "ref_eq_net",
    "literature_ids": "lit",
}
_ANNOTATION_SOURCE_ID_RE = re.compile(r"^(?:vlm|ref_eq_net|lit)_[1-9]\d*$")
_ANNOTATION_DRAFT_TOKEN_RE = re.compile(r"(?i)\bd\d{3}\b")
_ANNOTATION_MIN_CHARS = 40
_ANNOTATION_MAX_CHARS = 1200


def _issue(
    code: str,
    owner: GateOwner,
    message: str,
    draft_id: str | None = None,
    *topics: str,
) -> GateIssue:
    return GateIssue(
        code=code,
        owner=owner,
        message=message,
        draft_id=draft_id,
        missing_topics=tuple(topic for topic in topics if topic),
    )


class ParserGateService:
    """Owns every state mutation and the atomic solver-facing commit."""

    def __init__(
        self,
        *,
        state: ParserWorkingState,
        base_eq_map_card: dict[str, Any],
        session_id: str,
        artifact_dir: str | Path,
        catalog: Catalog | None = None,
    ) -> None:
        self.state = state
        self.base_eq_map_card = base_eq_map_card
        self.session_id = str(session_id)
        self.artifact_dir = Path(artifact_dir)
        self.catalog = catalog or DEFAULT_CATALOG
        self.committed_query: ParsedQuery | None = None
        self.last_support_document: dict[str, Any] | None = None
        self.last_working_map: dict[str, Any] | None = None
        self.last_network_audit: dict[str, Any] | None = None

    def _record_report(self, report: GateReport) -> None:
        """Record a gate result and latch any well-formed QueryAgent gap.

        A deterministic gate is the sole authority that may create a
        QueryAgent-follow-up receipt.  The receipt is source-bound by
        ``ParserWorkingState`` and therefore survives parser-only draft
        revisions without allowing parser-owned failures to open this route.
        """

        self.state.record_report(report)
        if any(issue.owner is GateOwner.HOST for issue in report.issues):
            return
        query_issues = [
            issue for issue in report.issues
            if issue.owner is GateOwner.QUERY_AGENT
        ]
        if not query_issues:
            return
        if any(not issue.missing_topics for issue in query_issues):
            return
        topics = sorted({
            topic
            for issue in query_issues
            for topic in issue.missing_topics
        })
        if not topics or any(
            topic not in KNOWN_CLARIFICATION_TOPICS for topic in topics
        ):
            return
        self.state.authorize_query_followup(
            report=report,
            topics=topics,
            issues=[issue.as_dict() for issue in query_issues],
        )

    def parser_context(self) -> dict[str, Any]:
        snapshot = self.state.evidence_snapshot
        transcript = self.state.transcript
        active_followup_receipts = (
            self.state.active_query_followup_authorizations()
        )
        cited_authorized_ids: dict[str, list[int]] = {}
        authorization_totals: dict[str, int] = {}
        for public_key, snapshot_key in _SNAPSHOT_ID_KEYS.items():
            authorized = {
                int(value) for value in (snapshot.get(snapshot_key) or [])
            }
            mentioned = {
                int(match.group(1))
                for match in _ANSWER_ID_PATTERNS[public_key].finditer(transcript)
            }
            cited_authorized_ids[public_key] = sorted(authorized & mentioned)
            authorization_totals[public_key] = len(authorized)
        beta_ids = cited_authorized_ids["beta_definition_ids"]
        beta_catalog = [self.catalog.inspect_beta(int(value)) for value in beta_ids]
        return {
            "query_id": self.state.query_id,
            "scope": self.state.scope,
            "requested_conditions": {
                "temperature_C": self.state.request_T_C,
                "ionic_strength_M": self.state.request_I_M,
            },
            "prose_cited_authorized_ids": cited_authorized_ids,
            "authorization_totals": authorization_totals,
            "canonical_beta_catalog": beta_catalog,
            "parser_writable_contract": {
                "top_level_keys": [
                    "beta_definition_id",
                    "constant_value",
                    "evidence_vlm_ids",
                    "evidence_network_ids",
                    "evidence_citation_ids",
                    "uncertainty_log10",
                    "estimation_method",
                    "assumptions",
                    "rationale",
                    "source_excerpts",
                ],
                "source_excerpts": dict(_SOURCE_EXCERPT_CONTRACT),
                "source_span_rule": (
                    "Every excerpt is one contiguous QueryAgent-answer span. "
                    "Only rendering-equivalent Unicode, whitespace, paired "
                    "Markdown emphasis, and inline-code differences are "
                    "normalized; no paraphrase, ellipsis, or stitched fragments."
                ),
                "draft_id_rule": (
                    "Use the exact draft_id returned by create_equilibrium_draft."
                ),
            },
            "annotation_contract": {
                "tool": "annotate_equilibrium_draft",
                "when": (
                    "after run_network_gate passes at the current revision "
                    "and before finish_parser_cycle(commit); commit is "
                    "blocked until every draft carries a live annotation"
                ),
                "payload_keys": [
                    "discussion", "core_source_ids", "secondary_source_ids",
                ],
                "rules": [
                    "discussion is your own concise reading of the answer's "
                    "argument for this one equilibrium: what anchors it, how "
                    "the chain reaches the value, what limits confidence "
                    f"({_ANNOTATION_MIN_CHARS}-{_ANNOTATION_MAX_CHARS} "
                    "characters); it must state the committed constant_value "
                    "as a number",
                    "each annotation must stand alone: never reference "
                    "workspace draft IDs or other entries' annotations, "
                    "because committed entries may be separated downstream",
                    "core_source_ids: the load-bearing evidence, fully "
                    "prefixed (vlm_<n>, ref_eq_net_<n>, lit_<n>), non-empty, "
                    "a subset of the draft's cited evidence",
                    "secondary_source_ids: corroborating session-observed "
                    "records only, disjoint from core_source_ids",
                    "every source ID mentioned in discussion must appear in "
                    "core_source_ids or secondary_source_ids",
                    "annotations survive edits to other drafts; only drafts "
                    "whose own content changed report stale and need a "
                    "rewritten annotation",
                ],
            },
            "workspace_revision": self.state.revision,
            "drafts": [draft.as_dict() for draft in self.state.drafts.values()],
            "active_query_followup_authorization": {
                "topics": sorted({
                    str(topic)
                    for receipt in active_followup_receipts
                    for topic in (receipt.get("topics") or [])
                }),
                "receipt_sha256": [
                    str(receipt["receipt_sha256"])
                    for receipt in active_followup_receipts
                ],
            },
        }

    def _owner_for_absent_topic(self, topic: str) -> GateOwner:
        pattern = _TOPIC_PATTERNS.get(topic)
        return (
            GateOwner.PARSER
            if pattern is not None and pattern.search(self.state.transcript)
            else GateOwner.QUERY_AGENT
        )

    def check_draft(self, draft_id: str) -> GateReport:
        draft = self.state.drafts.get(draft_id)
        if draft is None:
            report = GateReport(
                gate="draft_completeness",
                status="fail",
                state_revision=self.state.revision,
                issues=[_issue(
                    "unknown_draft", GateOwner.PARSER,
                    f"unknown draft_id {draft_id!r}", draft_id,
                )],
            )
            self._record_report(report)
            return report
        issues: list[GateIssue] = []
        topology_excerpt = draft.source_excerpts.get("topology_excerpt")
        if topology_excerpt:
            try:
                resolution = resolve_canonical_topology(
                    topology_excerpt=str(topology_excerpt),
                    transcript=self.state.transcript,
                    scope=self.state.scope,
                    canonical_beta_records=(
                        self.catalog.enumerate_materializable_betas().get(
                            "records"
                        ) or []
                    ),
                    authorization_context_id=self.state.query_id,
                    answer_sha256=self.state.transcript_sha256,
                )
                resolved_id = int(resolution["beta_definition_id"])
                if (
                    draft.beta_definition_id is not None
                    and int(draft.beta_definition_id) != resolved_id
                ):
                    issues.append(_issue(
                        "topology_beta_mismatch",
                        GateOwner.PARSER,
                        f"the prose reaction resolves to beta_def_{resolved_id}, "
                        f"not beta_def_{draft.beta_definition_id}",
                        draft_id,
                    ))
                    draft.topology_resolution = None
                else:
                    # Host-owned derivation: the parser selected prose, not an ID.
                    draft.beta_definition_id = resolved_id
                    draft.topology_resolution = resolution
            except TopologyResolutionError as exc:
                draft.topology_resolution = None
                candidates = closest_canonical_candidates(
                    topology_excerpt=str(topology_excerpt),
                    scope=self.state.scope,
                    canonical_beta_records=(
                        self.catalog.enumerate_materializable_betas().get(
                            "records"
                        ) or []
                    ),
                )
                hint = (
                    " Closest materializable candidates: "
                    + "; ".join(candidates)
                    + ". Retry with (a) a topology_excerpt that is one "
                    "contiguous answer span stating one concrete reaction "
                    "(real species, not generic [M]/[L] placeholder rows), "
                    "or (b) when the answer binds this estimate to a beta "
                    "ID, a source_excerpts.beta_definition_excerpt span "
                    "containing that literal beta_def_<id> token."
                ) if candidates else (
                    " No materializable canonical candidates exist for "
                    "this pair; if the answer names no matching canonical "
                    "equilibrium, conclude the cycle honestly."
                )
                issues.append(_issue(
                    "topology_resolution_failed",
                    GateOwner.PARSER,
                    str(exc) + hint,
                    draft_id,
                ))
        else:
            draft.topology_resolution = None

        requirements = (
            ("target_equilibrium_definition", draft.beta_definition_id, "target_equilibrium_definition"),
            ("constant_value", draft.constant_value, "estimated_log10_K"),
            ("uncertainty_log10", draft.uncertainty_log10, "uncertainty"),
            ("estimation_method", draft.estimation_method, "estimation_method"),
            ("assumptions", draft.assumptions, "assumptions"),
            ("rationale", draft.rationale, "rationale"),
            ("evidence_vlm_ids", draft.evidence_vlm_ids, "supporting_evidence"),
        )
        for field_name, value, topic in requirements:
            if value is None or value == "" or value == []:
                issues.append(_issue(
                    f"missing_{field_name}",
                    self._owner_for_absent_topic(topic),
                    f"{field_name} is required",
                    draft_id,
                    topic,
                ))
        if draft.beta_definition_id is not None and draft.beta_definition_id <= 0:
            issues.append(_issue(
                "invalid_beta_definition_id", GateOwner.PARSER,
                "beta_definition_id must be positive", draft_id,
            ))
        for field_name, values in (
            ("evidence_vlm_ids", draft.evidence_vlm_ids),
            ("evidence_network_ids", draft.evidence_network_ids),
            ("evidence_citation_ids", draft.evidence_citation_ids),
        ):
            if any(value <= 0 for value in values) or len(values) != len(set(values)):
                issues.append(_issue(
                    f"invalid_{field_name}", GateOwner.PARSER,
                    f"{field_name} must contain unique positive IDs", draft_id,
                ))
        for field_name, value in (
            ("constant_value", draft.constant_value),
            ("uncertainty_log10", draft.uncertainty_log10),
        ):
            if value is not None and not math.isfinite(float(value)):
                issues.append(_issue(
                    f"invalid_{field_name}", GateOwner.PARSER,
                    f"{field_name} must be finite", draft_id,
                ))
        if draft.uncertainty_log10 is not None and draft.uncertainty_log10 < 0:
            issues.append(_issue(
                "negative_uncertainty", GateOwner.PARSER,
                "uncertainty_log10 cannot be negative", draft_id,
            ))
        report = GateReport(
            gate="draft_completeness",
            status="pass" if not issues else "fail",
            state_revision=self.state.revision,
            issues=issues,
        )
        self._record_report(report)
        return report

    def run_entry_gate(self, draft_id: str) -> GateReport:
        completeness = self.check_draft(draft_id)
        if not completeness.passed:
            return completeness
        draft = self.state.drafts[draft_id]
        issues: list[GateIssue] = []
        pair = self.catalog.inspect_pair(
            int(self.state.scope["metal_id"]), int(self.state.scope["ligand_id"])
        )
        if pair.get("status") != "ok":
            issues.append(_issue(
                "canonical_pair_unavailable", GateOwner.HOST,
                "the scoped SRD-46 metal/ligand identities cannot be resolved",
                draft_id,
            ))
        assert draft.beta_definition_id is not None
        beta = self.catalog.inspect_beta(draft.beta_definition_id)
        if beta.get("status") != "ok":
            issues.append(_issue(
                "beta_not_materializable", GateOwner.QUERY_AGENT,
                f"beta_def_{draft.beta_definition_id} has no unambiguous K reaction",
                draft_id,
                "target_equilibrium_definition",
            ))
        source_receipts: list[dict[str, Any]] = []
        try:
            source_receipts = validate_draft_source_bindings(
                transcript=self.state.transcript,
                draft=draft,
            )
        except SourceGroundingError as exc:
            issues.append(_issue(
                "source_binding_failed", GateOwner.PARSER, str(exc), draft_id,
            ))

        canonical: dict[str, Any] | None = None
        evidence_receipt: dict[str, Any] | None = None
        if not issues:
            canonical = {
                "beta_definition_id": int(draft.beta_definition_id),
                "beta_definition_name": str(beta["beta_definition_name"]),
                "equation_python": str(beta["equation_python"]),
                "node_species": list(beta["node_species"]),
                "constant_type": "K",
                "constant_value": float(draft.constant_value),
                "temperature": float(self.state.request_T_C),
                "ionic_strength": float(self.state.request_I_M),
                "evidence_vlm_ids": list(draft.evidence_vlm_ids),
                "evidence_network_ids": list(draft.evidence_network_ids),
                "evidence_citation_ids": list(draft.evidence_citation_ids),
                "estimation_method": draft.estimation_method,
                "uncertainty_log10": float(draft.uncertainty_log10),
                "assumptions": list(draft.assumptions),
                "rationale": draft.rationale,
                "topology_resolution": (
                    dict(draft.topology_resolution)
                    if draft.topology_resolution is not None else None
                ),
            }
            try:
                evidence_receipt, _ = validate_evidence_snapshot(
                    equilibria=[canonical],
                    scope=self.state.scope,
                    snapshot=self.state.evidence_snapshot,
                    expected_context_id=self.state.query_id,
                    allow_analogue_topology=(
                        draft.topology_resolution is not None
                    ),
                )
                canonical["evidence_topology_diagnostics"] = dict(
                    evidence_receipt["validated_claims"][0]
                )
            except EvidenceGateError as exc:
                message = str(exc)
                owner = (
                    GateOwner.HOST
                    if "digest" in message or "scope" in message
                    else GateOwner.QUERY_AGENT
                )
                issues.append(_issue(
                    "evidence_gate_failed", owner, message, draft_id,
                    "supporting_evidence" if owner is GateOwner.QUERY_AGENT else "",
                ))
            evidence = self.catalog.inspect_evidence(draft.evidence_vlm_ids)
            if evidence.get("status") != "ok":
                issues.append(_issue(
                    "canonical_evidence_unavailable", GateOwner.QUERY_AGENT,
                    "one or more cited SRD-46 evidence records are unusable",
                    draft_id,
                    "supporting_evidence",
                ))
        receipt = None
        if not issues and canonical is not None:
            receipt = canonical_sha256({
                "state_revision": self.state.revision,
                "draft": canonical,
                "source_receipts": source_receipts,
                "evidence_receipt": evidence_receipt,
            })
            draft.canonical_equilibrium = canonical
            draft.entry_gate_receipt_sha256 = receipt
            draft.status = "entry_valid"
            # A re-seal of unchanged content transparently re-attaches an
            # existing annotation; content changes leave it stale on purpose.
            self.state.rebind_annotation(
                draft_id,
                entry_receipt_sha256=receipt,
                canonical_sha256_value=canonical_sha256(canonical),
            )
        else:
            draft.canonical_equilibrium = None
            draft.entry_gate_receipt_sha256 = None
            draft.status = "rejected"
        report = GateReport(
            gate="entry",
            status="pass" if not issues else "fail",
            state_revision=self.state.revision,
            issues=issues,
            receipt_sha256=receipt,
            details={
                "draft_id": draft_id,
                "canonical_equilibrium": canonical if not issues else None,
                "source_binding_receipts": source_receipts,
                "evidence_receipt": evidence_receipt,
            },
        )
        self._record_report(report)
        return report

    def network_passed_at_current_revision(self) -> bool:
        """Return whether the newest network gate passed at this revision."""

        revision = self.state.revision
        for report in reversed(self.state.gate_reports):
            if report.gate != "network":
                continue
            if report.state_revision != revision:
                continue
            return report.passed
        return False

    def _draft_cited_prefixed_ids(self, draft: EquilibriumDraft) -> set[str]:
        cited: set[str] = set()
        for prefix, values in (
            ("vlm", draft.evidence_vlm_ids),
            ("ref_eq_net", draft.evidence_network_ids),
            ("lit", draft.evidence_citation_ids),
        ):
            cited.update(f"{prefix}_{int(value)}" for value in values)
        return cited

    def _observed_prefixed_ids(self) -> set[str]:
        snapshot = self.state.evidence_snapshot
        observed: set[str] = set()
        for public_key, prefix in _ANNOTATION_ID_PREFIXES.items():
            snapshot_key = _SNAPSHOT_ID_KEYS[public_key]
            observed.update(
                f"{prefix}_{int(value)}"
                for value in (snapshot.get(snapshot_key) or [])
            )
        return observed

    @staticmethod
    def _annotation_id_list(payload: dict[str, Any], key: str) -> list[str]:
        value = payload.get(key) or []
        if not isinstance(value, list) or any(
            not isinstance(item, str) for item in value
        ):
            raise ValueError(
                f"{key} must be a list of prefixed source-ID strings such as "
                "vlm_123, ref_eq_net_45, or lit_67"
            )
        normalized = sorted({item.strip() for item in value if item.strip()})
        malformed = [
            item for item in normalized
            if not _ANNOTATION_SOURCE_ID_RE.fullmatch(item)
        ]
        if malformed:
            raise ValueError(
                f"{key} contains malformed source IDs {malformed}; use the "
                "fully prefixed forms vlm_<n>, ref_eq_net_<n>, or lit_<n>"
            )
        return normalized

    def annotate_draft(self, draft_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Validate and store the parser's interpretive digest for one draft.

        The digest is deliberately not excerpt-bound \u2014 it is the parser's own
        labeled reading of the QueryAgent answer \u2014 so every deterministic
        anchor that can hold is enforced here instead: the draft must already
        be sealed by a passed current-revision network gate, the discussion
        must state the committed value, every evidence ID it mentions must be
        declared, core IDs must come from the draft's own cited evidence, and
        secondary IDs from the session's observed snapshot.  Violations raise
        ValueError so the agent corrects and resends only this call.
        """

        draft = self.state.drafts.get(draft_id)
        if draft is None:
            raise ValueError(
                f"unknown draft_id {draft_id!r}; use the exact id returned by "
                "create_equilibrium_draft"
            )
        if not self.network_passed_at_current_revision():
            raise ValueError(
                "annotation requires a passed network gate at the current "
                "workspace revision; run run_network_gate first, then "
                "annotate each draft"
            )
        if draft.entry_gate_receipt_sha256 is None or draft.canonical_equilibrium is None:
            raise ValueError(
                f"draft {draft_id} holds no current entry-gate receipt; run "
                "run_network_gate first"
            )
        unknown = set(payload) - _ANNOTATION_PAYLOAD_KEYS
        if unknown:
            raise ValueError(
                f"annotation_json contains unknown keys {sorted(unknown)}; "
                f"allowed keys are {sorted(_ANNOTATION_PAYLOAD_KEYS)}"
            )
        discussion_raw = payload.get("discussion")
        if not isinstance(discussion_raw, str):
            raise ValueError(
                "discussion must be one string "
                f"(got {type(discussion_raw).__name__})"
            )
        discussion = discussion_raw.strip()
        if len(discussion) < _ANNOTATION_MIN_CHARS:
            raise ValueError(
                "discussion is too short to be a usable digest "
                f"(minimum {_ANNOTATION_MIN_CHARS} characters); summarize in "
                "your own words how the answer argues from its anchor "
                "evidence to the committed value"
            )
        if len(discussion) > _ANNOTATION_MAX_CHARS:
            raise ValueError(
                f"discussion exceeds {_ANNOTATION_MAX_CHARS} characters; it "
                "is a digest, not a transcript \u2014 condense it"
            )
        draft_tokens = sorted({
            match.group(0)
            for match in _ANNOTATION_DRAFT_TOKEN_RE.finditer(discussion)
        })
        if draft_tokens:
            raise ValueError(
                f"discussion references workspace draft IDs {draft_tokens}; "
                "each annotation must stand alone because committed entries "
                "may be separated downstream \u2014 restate the chemistry instead "
                "of pointing at another draft"
            )
        core = self._annotation_id_list(payload, "core_source_ids")
        if not core:
            raise ValueError(
                "core_source_ids must name at least one load-bearing source "
                "from the draft's cited evidence"
            )
        secondary = self._annotation_id_list(payload, "secondary_source_ids")
        cited = self._draft_cited_prefixed_ids(draft)
        outside_cited = sorted(set(core) - cited)
        if outside_cited:
            raise ValueError(
                f"core_source_ids {outside_cited} are not cited evidence of "
                f"draft {draft_id}; its cited prefixed IDs are {sorted(cited)}"
            )
        observed = self._observed_prefixed_ids()
        outside_observed = sorted(set(secondary) - observed)
        if outside_observed:
            raise ValueError(
                f"secondary_source_ids {outside_observed} were never observed "
                "in this session's authorized evidence snapshot"
            )
        overlap = sorted(set(core) & set(secondary))
        if overlap:
            raise ValueError(
                f"{overlap} appear in both core_source_ids and "
                "secondary_source_ids; keep the two roles disjoint"
            )
        mentioned: set[str] = set()
        for public_key, prefix in _ANNOTATION_ID_PREFIXES.items():
            mentioned.update(
                f"{prefix}_{int(match.group(1))}"
                for match in _ANSWER_ID_PATTERNS[public_key].finditer(discussion)
            )
        undeclared = sorted(mentioned - set(core) - set(secondary))
        if undeclared:
            raise ValueError(
                f"discussion mentions source IDs {undeclared} that are listed "
                "in neither core_source_ids nor secondary_source_ids"
            )
        assert draft.constant_value is not None
        try:
            _bind_number(discussion, float(draft.constant_value), "constant_value")
        except SourceGroundingError as exc:
            raise ValueError(
                "discussion must state the committed value as a number: "
                f"{exc}"
            ) from exc
        annotation_sha256 = canonical_sha256({
            "discussion": discussion,
            "core_source_ids": core,
            "secondary_source_ids": secondary,
        })
        replaced_previous = draft_id in self.state.annotations
        self.state.set_annotation(DraftAnnotation(
            draft_id=draft.draft_id,
            discussion=discussion,
            core_source_ids=core,
            secondary_source_ids=secondary,
            annotation_sha256=annotation_sha256,
            bound_entry_receipt_sha256=draft.entry_gate_receipt_sha256,
            bound_canonical_sha256=canonical_sha256(draft.canonical_equilibrium),
        ))
        return {
            "status": "annotated",
            "draft_id": draft.draft_id,
            "annotation_sha256": annotation_sha256,
            "replaced_previous": replaced_previous,
            "liveness": self.state.annotation_liveness(draft.draft_id),
        }

    def annotation_gaps(self) -> list[dict[str, str]]:
        """Per-draft annotation liveness gaps that block the atomic commit."""

        return [
            {"draft_id": draft_id, "liveness": liveness}
            for draft_id in self.state.drafts
            if (liveness := self.state.annotation_liveness(draft_id)) != "annotated"
        ]

    def _canonical_parsed_query(
        self, *, include_annotations: bool = False
    ) -> ParsedQuery:
        pair = self.catalog.inspect_pair(
            int(self.state.scope["metal_id"]), int(self.state.scope["ligand_id"])
        )
        equilibria: list[dict[str, Any]] = []
        annotation_sha256s: dict[str, str] = {}
        for draft in self.state.drafts.values():
            if draft.canonical_equilibrium is None:
                continue
            equilibrium = dict(draft.canonical_equilibrium)
            if include_annotations:
                annotation = self.state.annotations.get(draft.draft_id)
                if annotation is not None:
                    equilibrium["agent_annotation"] = {
                        "discussion": annotation.discussion,
                        "core_source_ids": list(annotation.core_source_ids),
                        "secondary_source_ids": list(
                            annotation.secondary_source_ids
                        ),
                        "annotation_sha256": annotation.annotation_sha256,
                        "bound_entry_receipt_sha256": (
                            annotation.bound_entry_receipt_sha256
                        ),
                    }
                    annotation_sha256s[draft.draft_id] = (
                        annotation.annotation_sha256
                    )
            equilibria.append(equilibrium)
        receipts: dict[str, Any] = {
            "pair": pair,
            "entry_gate_receipts": [
                draft.entry_gate_receipt_sha256
                for draft in self.state.drafts.values()
                if draft.entry_gate_receipt_sha256
            ],
        }
        if include_annotations:
            receipts["annotation_sha256s"] = annotation_sha256s
        snapshot_digest = str(self.state.evidence_snapshot.get("snapshot_sha256") or "")
        return ParsedQuery(
            query_id=self.state.query_id,
            scope=dict(self.state.scope),
            parsed_speciation={"chemical_pairs": [{
                "metal_id": int(self.state.scope["metal_id"]),
                "metal_name": pair.get("metal_name") or self.state.scope.get("metal_name"),
                "ligand_id": int(self.state.scope["ligand_id"]),
                "ligand_name": pair.get("ligand_name") or self.state.scope.get("ligand_name"),
                "equilibria": equilibria,
            }]},
            receipts=receipts,
            evidence_authorization=dict(self.state.evidence_snapshot),
            evidence_authorization_sha256=snapshot_digest,
            answer_sha256=self.state.transcript_sha256,
            artifact_dir=str(self.artifact_dir),
        )

    def run_network_gate(self) -> GateReport:
        issues: list[GateIssue] = []
        for draft_id in list(self.state.drafts):
            report = self.run_entry_gate(draft_id)
            issues.extend(report.issues)
        identities: dict[tuple[int, float, float], EquilibriumDraft] = {}
        for draft in self.state.drafts.values():
            if draft.canonical_equilibrium is None:
                continue
            identity = (
                int(draft.beta_definition_id),
                float(self.state.request_T_C),
                float(self.state.request_I_M),
            )
            prior = identities.get(identity)
            if prior is None:
                identities[identity] = draft
            elif canonical_sha256(prior.canonical_equilibrium) != canonical_sha256(
                draft.canonical_equilibrium
            ):
                issues.append(_issue(
                    "conflicting_duplicate", GateOwner.PARSER,
                    "two drafts assign different values to the same equilibrium",
                    draft.draft_id,
                ))
            else:
                issues.append(_issue(
                    "exact_duplicate", GateOwner.PARSER,
                    "remove the duplicate draft before committing",
                    draft.draft_id,
                ))
        support_document = None
        working_map = None
        network_audit = None
        if not issues and not self.state.drafts:
            issues.append(_issue(
                "no_drafts", GateOwner.PARSER,
                "commit requires at least one equilibrium draft",
            ))
        if not issues:
            candidate = self._canonical_parsed_query()
            try:
                from ..validate_support_eq_map.session_working_map import (
                    build_session_working_map,
                    validate_session_working_map,
                )
                from ..validate_support_eq_map.support_eq_map_assembler import (
                    assemble_support_eq_map,
                )
                from ..validate_support_eq_map.support_eq_map_validator import (
                    validate_support_eq_map,
                )

                support_document, _ = assemble_support_eq_map(
                    parsed_queries=[candidate],
                    session_id=self.session_id,
                    base_eq_map_sha256=self.state.base_eq_map_sha256,
                    request_T_C=self.state.request_T_C,
                    request_I_M=self.state.request_I_M,
                    created_at="parser-gate-preview",
                )
                support_audit = validate_support_eq_map(
                    support_document, catalog=self.catalog
                )
                working_map = build_session_working_map(
                    base_eq_map_card=self.base_eq_map_card,
                    support_document=support_document,
                )
                working_audit = validate_session_working_map(
                    working_map,
                    base_eq_map_card=self.base_eq_map_card,
                    support_document=support_document,
                )
                network_audit = {
                    "support_eq_map": support_audit,
                    "session_working_map": working_audit,
                }
            except Exception as exc:
                issues.append(_issue(
                    "network_materialization_failed", GateOwner.HOST,
                    f"{type(exc).__name__}: {exc}",
                ))
        receipt = None
        if not issues and support_document is not None and working_map is not None:
            receipt = canonical_sha256({
                "state_revision": self.state.revision,
                "support_document": support_document,
                "working_map": working_map,
            })
            self.last_support_document = support_document
            self.last_working_map = working_map
            self.last_network_audit = network_audit
        report = GateReport(
            gate="network",
            status="pass" if not issues else "fail",
            state_revision=self.state.revision,
            issues=issues,
            receipt_sha256=receipt,
            details=network_audit or {},
        )
        self._record_report(report)
        return report

    def commit(self) -> tuple[ParsedQuery | None, GateReport]:
        expected_revision = self.state.revision
        report = self.run_network_gate()
        if not report.passed:
            return None, report
        if self.state.revision != expected_revision:
            report = GateReport(
                gate="atomic_commit",
                status="fail",
                state_revision=self.state.revision,
                issues=[_issue(
                    "stale_revision", GateOwner.HOST,
                    "workspace changed while validation was running",
                )],
            )
            self._record_report(report)
            return None, report
        if canonical_sha256(self.base_eq_map_card) != self.state.base_eq_map_sha256:
            report = GateReport(
                gate="atomic_commit",
                status="fail",
                state_revision=self.state.revision,
                issues=[_issue(
                    "base_map_changed", GateOwner.HOST,
                    "base equilibrium map changed before commit",
                )],
            )
            self._record_report(report)
            return None, report
        gaps = self.annotation_gaps()
        if gaps:
            report = GateReport(
                gate="atomic_commit",
                status="fail",
                state_revision=self.state.revision,
                issues=[_issue(
                    (
                        "annotation_stale"
                        if gap["liveness"] == "stale"
                        else "annotation_missing"
                    ),
                    GateOwner.PARSER,
                    (
                        "the draft content changed after it was annotated; "
                        "rewrite its annotation with annotate_equilibrium_draft"
                        if gap["liveness"] == "stale"
                        else "every committed draft needs one live annotation; "
                        "call annotate_equilibrium_draft after the network "
                        "gate passes"
                    ),
                    gap["draft_id"],
                ) for gap in gaps],
            )
            self._record_report(report)
            return None, report
        self.committed_query = self._canonical_parsed_query(
            include_annotations=True
        )
        self.state.set_terminal(ParserAction.COMMIT, "all entry and network gates passed")
        return self.committed_query, report

    def commit_no_estimate(self, reason: str) -> ParsedQuery:
        if self.state.drafts:
            raise ValueError("no_estimate cannot be committed while drafts exist")
        if not has_no_estimate_conclusion(self.state.transcript):
            raise ValueError(
                "QueryAgent transcript does not contain an explicit no-estimate conclusion"
            )
        # Even an empty claim verifies the session receipt digest/scope.
        validate_evidence_snapshot(
            equilibria=[],
            scope=self.state.scope,
            snapshot=self.state.evidence_snapshot,
            expected_context_id=self.state.query_id,
        )
        self.committed_query = self._canonical_parsed_query()
        self.state.set_terminal(ParserAction.NO_ESTIMATE, reason)
        return self.committed_query

    def record_query_agent_gap(
        self,
        *,
        code: str,
        message: str,
        missing_topics: list[str],
    ) -> GateReport:
        """Record a host-recognized chemistry omission at this revision."""

        topics = sorted({
            str(value).strip() for value in missing_topics if str(value).strip()
        })
        if not topics:
            raise ValueError("a QueryAgent gap requires at least one topic")
        unknown = sorted(set(topics) - KNOWN_CLARIFICATION_TOPICS)
        if unknown:
            raise ValueError(f"unknown chemistry clarification topics: {unknown}")
        report = GateReport(
            gate="query_answer_admissibility",
            status="fail",
            state_revision=self.state.revision,
            issues=[_issue(
                str(code).strip() or "missing_query_chemistry",
                GateOwner.QUERY_AGENT,
                str(message).strip() or "QueryAgent chemistry is incomplete",
                None,
                *topics,
            )],
        )
        self._record_report(report)
        return report

    def latest_query_agent_issues(
        self, report: GateReport | None = None
    ) -> tuple[GateIssue, ...]:
        """Return source-bound QueryAgent omissions authorized by host gates.

        With an explicit report, retain the strict direct-report check used by
        callers routing an immediate gate failure.  Without one, aggregate the
        active authorization receipts for the unchanged QueryAgent transcript
        and evidence snapshot.  Parser draft revisions do not invalidate those
        receipts because they cannot resolve an upstream chemistry omission.
        """

        if report is not None:
            if report not in self.state.gate_reports:
                return ()
            issues = tuple(
                issue for issue in report.issues
                if issue.owner is GateOwner.QUERY_AGENT
            )
            if any(not issue.missing_topics for issue in issues):
                return ()
            if any(
                topic not in KNOWN_CLARIFICATION_TOPICS
                for issue in issues
                for topic in issue.missing_topics
            ):
                return ()
            serialized = [issue.as_dict() for issue in issues]
            if not any(
                receipt.get("gate") == report.gate
                and receipt.get("gate_state_revision") == report.state_revision
                and receipt.get("issues") == serialized
                for receipt in self.state.active_query_followup_authorizations()
            ):
                return ()
            return issues

        issues: list[GateIssue] = []
        for receipt in self.state.active_query_followup_authorizations():
            for raw_issue in receipt.get("issues") or []:
                try:
                    issue = GateIssue(
                        code=str(raw_issue["code"]),
                        owner=GateOwner(str(raw_issue["owner"])),
                        message=str(raw_issue["message"]),
                        draft_id=(
                            None
                            if raw_issue.get("draft_id") is None
                            else str(raw_issue["draft_id"])
                        ),
                        missing_topics=tuple(
                            str(topic)
                            for topic in (raw_issue.get("missing_topics") or [])
                        ),
                    )
                except (KeyError, TypeError, ValueError):
                    continue
                if issue.owner is GateOwner.QUERY_AGENT:
                    issues.append(issue)
        return tuple(issues)

    def query_agent_followup_topics(
        self, report: GateReport | None = None
    ) -> list[str]:
        """Derive the only topics authorized for a QueryAgent follow-up."""

        return sorted({
            topic
            for issue in self.latest_query_agent_issues(report)
            for topic in issue.missing_topics
        })

    @staticmethod
    def action_for_report(report: GateReport) -> ParserAction:
        owners = {issue.owner for issue in report.issues}
        if GateOwner.HOST in owners:
            return ParserAction.FATAL_HOST
        if GateOwner.QUERY_AGENT in owners:
            return ParserAction.REQUEST_FOLLOWUP
        return ParserAction.PARSER_REVISE


__all__ = ["ParserGateService"]
