"""Session-scoped tools exposed only to the downstream parser agent."""

from __future__ import annotations

import json
from typing import Any, Callable

from .candidate_schema import ParserAction
from .parser_gate_service import ParserGateService


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, default=str)


def _object(raw: str, label: str) -> dict[str, Any]:
    text = str(raw or "")
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        try:
            # Literal newlines/tabs inside string values arrive frequently
            # from multi-line excerpt payloads; strict=False preserves the
            # characters verbatim instead of rejecting the whole call.
            value = json.loads(text, strict=False)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{label} must be one JSON object: {exc}. Correct and "
                f"retry: resend the complete tool call with {label} as "
                "exactly one JSON object, with every newline inside a "
                "string value escaped as \\n and every inner double "
                "quote escaped as \\\"; never truncate the payload or "
                "abbreviate it with an ellipsis."
            ) from exc
    if not isinstance(value, dict):
        raise ValueError(
            f"{label} must be one JSON object, not "
            f"{type(value).__name__}; resend the full corrected call."
        )
    return value


class ParserToolbox:
    """Thin tool facade; the gate service remains the only authority."""

    def __init__(self, service: ParserGateService) -> None:
        self.service = service

    def inspect_parser_context(self) -> str:
        """Inspect scope, conditions, prose-cited authorized IDs, and draft contract."""

        return _json(self.service.parser_context())

    def create_equilibrium_draft(self, draft_json: str = "") -> str:
        """Create a partial target-equilibrium draft from a JSON object.

        The only writable top-level keys are beta_definition_id,
        constant_value, evidence_vlm_ids, evidence_network_ids,
        evidence_citation_ids, uncertainty_log10, estimation_method,
        assumptions, rationale, and source_excerpts. source_excerpts must use
        topology_excerpt, beta_definition_excerpt, constant_value_excerpt, uncertainty_excerpt,
        evidence_excerpt, estimation_method_excerpt, assumption_excerpts, and
        rationale_excerpt. Each excerpt must identify one contiguous QueryAgent
        answer span. Only rendering-equivalent Unicode, whitespace, paired
        Markdown emphasis, and inline-code differences are normalized;
        ellipses, paraphrases, and stitched spans fail the source gate.
        assumption_excerpts is a list corresponding one-to-one to assumptions.
        Read and reuse the returned draft_id. Canonical names,
        reactions, species, conditions, solvent fields, constant type, and
        native equilibrium-map row/node IDs are host-owned and forbidden.
        Prefer topology_excerpt and omit beta_definition_id: the host resolves
        the verbatim prose reaction to a canonical definition.  An explicit
        beta-definition remains a legacy parser selector.  Evidence IDs are
        parser-writable selectors.
        """

        draft = self.service.state.create_draft(_object(draft_json, "draft_json"))
        return _json({"status": "saved_partial", "draft": draft.as_dict()})

    def update_equilibrium_draft(
        self, draft_id: str = "", patch_json: str = ""
    ) -> str:
        """Patch the exact returned draft_id using the same writable contract.

        source_excerpts patches merge per excerpt key: send only the excerpts
        you are changing, and send null for a key to delete its stored span;
        omitted keys keep their stored spans. All other fields are replaced
        whole by the patch value.
        """

        draft = self.service.state.update_draft(
            str(draft_id), _object(patch_json, "patch_json")
        )
        return _json({"status": "updated", "draft": draft.as_dict()})

    def inspect_drafts(self) -> str:
        """Inspect all partial drafts, their annotations, and the workspace revision."""

        state = self.service.state
        return _json({
            "revision": state.revision,
            "drafts": [draft.as_dict() for draft in state.drafts.values()],
            "annotations": [
                {
                    **annotation.as_dict(),
                    "liveness": state.annotation_liveness(annotation.draft_id),
                }
                for annotation in state.annotations.values()
            ],
        })

    def discard_draft(self, draft_id: str = "") -> str:
        """Discard an incorrect or exact-duplicate partial draft."""

        self.service.state.discard_draft(str(draft_id))
        return _json({"status": "discarded", "draft_id": draft_id})

    def check_draft(self, draft_id: str = "") -> str:
        """Check one exact returned draft_id before running the entry gate."""

        return _json(self.service.check_draft(str(draft_id)).as_dict())

    def run_entry_gate(self, draft_id: str = "") -> str:
        """After check_draft passes, validate verbatim source and evidence binding."""

        return _json(self.service.run_entry_gate(str(draft_id)).as_dict())

    def run_network_gate(self) -> str:
        """After every entry passes, rebuild native and solver-facing maps."""

        return _json(self.service.run_network_gate().as_dict())

    def annotate_equilibrium_draft(
        self, draft_id: str = "", annotation_json: str = ""
    ) -> str:
        """After the network gate passes, attach your interpretive digest to one draft.

        annotation_json must be one JSON object with keys discussion,
        core_source_ids, and secondary_source_ids. discussion is your own
        concise reading of the answer's argument for this one equilibrium \u2014
        what anchors it, how the chain reaches the value, what limits
        confidence \u2014 and must state the committed constant_value as a number.
        core_source_ids lists the load-bearing evidence as fully prefixed IDs
        (vlm_<n>, ref_eq_net_<n>, lit_<n>) drawn from the draft's cited
        evidence; secondary_source_ids lists corroborating session-observed
        records, disjoint from core. Every source ID mentioned in discussion
        must appear in one of the two lists. Each annotation must stand alone:
        never reference draft IDs or other entries' annotations, because
        committed entries may be separated downstream. Annotation calls are
        independent: a failed or truncated call discards only itself \u2014 correct
        and resend just that call; earlier successes persist. Calling again
        for the same draft replaces its stored annotation.
        """

        return _json(self.service.annotate_draft(
            str(draft_id), _object(annotation_json, "annotation_json")
        ))

    def finish_parser_cycle(
        self,
        action: str = "",
        reason: str = "",
        missing_topics_csv: str = "",
    ) -> str:
        """Finish with commit, request_followup, or no_estimate.

        `request_followup` is for chemistry facts absent from QueryAgent prose;
        parser extraction mistakes must instead be corrected with draft tools.
        """

        try:
            requested = ParserAction(str(action).strip())
        except ValueError as exc:
            raise ValueError(
                "action must be commit, request_followup, or no_estimate"
            ) from exc
        if requested is ParserAction.COMMIT:
            committed, report = self.service.commit()
            if committed is not None:
                return _json({
                    "status": "committed",
                    "query_id": committed.query_id,
                    "network_gate_receipt_sha256": report.receipt_sha256,
                })
            routed = self.service.action_for_report(report)
            topics = self.service.query_agent_followup_topics(report)
            self.service.state.set_terminal(routed, reason or "commit gate failed", topics)
            return _json({
                "status": "not_committed",
                "routed_action": routed.value,
                "gate_report": report.as_dict(),
            })
        if requested is ParserAction.REQUEST_FOLLOWUP:
            asserted_topics = sorted({
                item.strip() for item in str(missing_topics_csv).split(",")
                if item.strip()
            })
            topics = self.service.query_agent_followup_topics()
            if not topics:
                raise ValueError(
                    "request_followup is not authorized by an active "
                    "QueryAgent-source-bound gate receipt"
                )
            if asserted_topics != topics:
                raise ValueError(
                    "missing_topics_csv must exactly match the active gate-owned "
                    f"QueryAgent topics: {topics}"
                )
            self.service.state.set_terminal(requested, reason, topics)
            return _json({
                "status": "query_followup_requested",
                "missing_topics": topics,
            })
        if requested is ParserAction.NO_ESTIMATE:
            committed = self.service.commit_no_estimate(reason)
            return _json({"status": "no_estimate_committed", "query_id": committed.query_id})
        raise ValueError("parser may not directly finish with an internal routing action")

    def tools(self) -> dict[str, Callable[..., str]]:
        return {
            "inspect_parser_context": self.inspect_parser_context,
            "create_equilibrium_draft": self.create_equilibrium_draft,
            "update_equilibrium_draft": self.update_equilibrium_draft,
            "inspect_drafts": self.inspect_drafts,
            "discard_draft": self.discard_draft,
            "check_draft": self.check_draft,
            "run_entry_gate": self.run_entry_gate,
            "run_network_gate": self.run_network_gate,
            "annotate_equilibrium_draft": self.annotate_equilibrium_draft,
            "finish_parser_cycle": self.finish_parser_cycle,
        }


__all__ = ["ParserToolbox"]
