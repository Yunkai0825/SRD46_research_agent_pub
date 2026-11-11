"""Session-scoped tools exposed only to the downstream parser agent."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Callable

from .candidate_schema import ParserAction
from .parser_gate_service import ParserGateService


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, default=str)


# --- read-only catalog lookups -------------------------------------------

_SEARCH_ARROW_RE = re.compile(r"<=>|<->|⇌|↔|⇄|→|->|=")
_BETA_TOKEN_RE = re.compile(r"(?i)^\s*(?:beta_def_)?(\d+)\s*$")
_SEARCH_LIMIT_MAX = 50
_SEARCH_HINT_NO_MATCH = (
    "no materializable canonical equation matches; canonical species are "
    "written with M (scoped metal), L (scoped ligand), H, OH, H2O, e only — "
    "e.g. ML, ML2, HL, M(OH)L, [M] + [L] <=> [ML] — and equilibria with a "
    "second ligand (L') lie outside this one-metal/one-ligand catalog"
)
_SEARCH_HINT_MATCH = (
    "lookups are not evidence: a draft is bound only through "
    "source_excerpts.topology_excerpt (plus topology_species_mapping when the "
    "notation needs it) or a beta_def_<id> token written in the answer"
)


def _normalize_search_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = _SEARCH_ARROW_RE.sub("<=>", text)
    text = re.sub(r"[\[\]`\s]", "", text)
    return text.casefold()


def _parse_beta_token(value: str) -> int:
    match = _BETA_TOKEN_RE.match(str(value or ""))
    if match is None or int(match.group(1)) <= 0:
        raise ValueError(
            "beta_definition_id must be a positive integer or a beta_def_<id> token"
        )
    return int(match.group(1))


def _parse_limit(value: Any, default: int = 10) -> int:
    try:
        limit = int(str(value).strip()) if str(value).strip() else default
    except ValueError as exc:
        raise ValueError("limit must be a positive integer") from exc
    return max(1, min(limit, _SEARCH_LIMIT_MAX))


def _search_rows(records: list[dict[str, Any]], query: str, limit: int) -> dict[str, Any]:
    """Rank materializable catalog rows: beta token, whole equation, species token, text."""

    normalized_query = _normalize_search_text(query)
    beta_match = _BETA_TOKEN_RE.match(str(query or ""))
    beta_id = int(beta_match.group(1)) if beta_match is not None else None
    ranked: list[tuple[int, int, dict[str, Any]]] = []
    for record in records:
        try:
            record_id = int(record.get("beta_definition_id"))
        except (TypeError, ValueError):
            continue
        equation = str(record.get("equation_python") or "")
        name = str(record.get("beta_definition_name") or "")
        tokens = {
            _normalize_search_text(token)
            for token in re.findall(r"\[([^\]]+)\]", equation)
        }
        norm_equation = _normalize_search_text(equation)
        norm_name = _normalize_search_text(name)
        if beta_id is not None and record_id == beta_id:
            rank, kind = 0, "beta_id"
        elif normalized_query and normalized_query == norm_equation:
            rank, kind = 1, "equation"
        elif normalized_query and normalized_query in tokens:
            rank, kind = 2, "species"
        elif normalized_query and (
            normalized_query in norm_equation or normalized_query in norm_name
        ):
            rank, kind = 3, "text"
        else:
            continue
        ranked.append((rank, record_id, {
            "beta_definition_id": record_id,
            "beta_definition_name": name,
            "equation_python": equation,
            "match": kind,
        }))
    ranked.sort(key=lambda item: (item[0], item[1]))
    rows = [row for _, _, row in ranked]
    return {"n_matches": len(rows), "records": rows[:limit]}


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


_DRAFT_VALUE_KEYS = (
    "beta_definition_id", "constant_value", "uncertainty_log10",
    "estimation_method", "assumptions", "rationale", "evidence_vlm_ids",
    "evidence_network_ids", "evidence_citation_ids", "topology_species_mapping",
    "statement_review",
)
_CANONICAL_SUMMARY_KEYS = (
    "beta_definition_id", "beta_definition_name", "equation_python",
    "constant_type", "constant_value", "uncertainty_log10", "temperature",
    "ionic_strength", "evidence_vlm_ids", "evidence_network_ids",
    "evidence_citation_ids", "ungrounded_anchor_vlm_ids",
    "ungrounded_anchor_policy", "answer_marked_optional",
    "bound_statement", "other_value_statements", "statement_review",
)
# Keys of the committed entry carried into the finish_parser_cycle reply so
# the cycle record shows what downstream receives beside the numbers.
_COMMITTED_ENTRY_MARKER_KEYS = (
    "ungrounded_anchor_vlm_ids", "answer_marked_optional",
    "other_value_statements", "statement_review",
)


def _excerpt_resolution_receipt(
    draft: Any, resolution: Any
) -> dict[str, Any]:
    """What the host stored for excerpts the parser only pointed at.

    Added to the create/update receipt of the call that resolved them, so the
    parser sees the stored line at once and confirms (or re-points) it
    without spending a round on ``inspect_drafts``.
    """

    if not isinstance(resolution, dict) or resolution.get("draft_id") != draft.draft_id:
        return {}
    resolved = resolution.get("resolved") or {}
    unresolved = resolution.get("unresolved") or {}
    receipt: dict[str, Any] = {}
    notes: list[str] = []
    if resolved:
        receipt["host_resolved_excerpts"] = {
            key: {
                "how": note["how"],
                "similarity": note["similarity"],
                "stored_line": note["stored_line"],
            }
            for key, note in resolved.items()
        }
        parts = [
            f"{key} ("
            + (
                "its opening characters"
                if note["how"] == "prefix"
                else f"a close match, similarity {note['similarity']}"
            )
            + ")"
            for key, note in resolved.items()
        ]
        notes.append(
            "The host stored the answer's own line for " + ", ".join(parts)
            + "; see stored_line. Confirm each stored line is the row you "
            "meant; if not, patch that key with the opening characters of "
            "the right line."
        )
    if unresolved:
        receipt["unresolved_excerpts"] = unresolved
        notes.append(
            ", ".join(unresolved)
            + ": the text opens or resembles several answer lines and was "
            "stored as sent; see candidates and send more of the opening "
            "characters of the line you mean."
        )
    if notes:
        receipt["host_note"] = " ".join(notes) + " This note needs no reply."
    return receipt


def _draft_receipt(
    draft: Any, status: str, revision: int, resolution: Any = None
) -> dict[str, Any]:
    """Compact create/update reply: what is stored, not the whole draft.

    Echoing the full draft made the parser retype ~9k characters per call
    (about 70 % of the blind testers' payload); ``inspect_drafts`` still
    shows the complete stored content whenever it is needed.
    """

    excerpts = dict(draft.source_excerpts)
    host_copied = [
        key for key, excerpt_key in (
            ("estimation_method", "estimation_method_excerpt"),
            ("rationale", "rationale_excerpt"),
        )
        if getattr(draft, key)
        and isinstance(excerpts.get(excerpt_key), str)
        and getattr(draft, key) == excerpts[excerpt_key].strip()
    ]
    spans = excerpts.get("assumption_excerpts")
    if (
        draft.assumptions
        and isinstance(spans, list)
        and draft.assumptions == [str(span).strip() for span in spans]
    ):
        host_copied.append("assumptions")
    receipt = {
        "status": status,
        "draft_id": draft.draft_id,
        "workspace_revision": revision,
        "fields_stored": [
            key for key in _DRAFT_VALUE_KEYS
            if getattr(draft, key) not in (None, "", [], {})
        ],
        "excerpt_keys_stored": sorted(excerpts),
        "host_copied_from_excerpts": host_copied,
    }
    receipt.update(_excerpt_resolution_receipt(draft, resolution))
    receipt["next"] = (
        "check_draft(draft_id) validates completeness and resolves the "
        "topology; inspect_drafts shows the stored content"
    )
    return receipt


def _slim_entry_report(report: Any) -> dict[str, Any]:
    """Entry-gate reply without the excerpt texts echoed back.

    The full canonical entry, source receipts and evidence receipt stay on
    the draft and in the cycle record; the parser needs the verdict, the
    issues and a summary of what was sealed.
    """

    payload = report.as_dict()
    details = dict(payload.get("details") or {})
    canonical = details.get("canonical_equilibrium")
    if isinstance(canonical, dict):
        summary = {
            key: canonical[key] for key in _CANONICAL_SUMMARY_KEYS if key in canonical
        }
        resolution = canonical.get("topology_resolution")
        if isinstance(resolution, dict):
            summary["topology_resolution"] = {
                key: resolution.get(key)
                for key in (
                    "beta_definition_id", "beta_definition_name",
                    "equation_python", "species_mapping",
                )
                if key in resolution
            }
        summary["estimation_method_chars"] = len(str(canonical.get("estimation_method") or ""))
        summary["assumptions_count"] = len(canonical.get("assumptions") or [])
        summary["rationale_chars"] = len(str(canonical.get("rationale") or ""))
        details["canonical_equilibrium"] = summary
    receipts = details.get("source_binding_receipts")
    if isinstance(receipts, list):
        details["source_binding_receipts"] = [
            {
                "draft_id": receipt.get("draft_id"),
                "source_binding_profile": receipt.get("source_binding_profile"),
                "bound_excerpt_keys": sorted(
                    key for key, value in receipt.items()
                    if (key.endswith("_excerpt") or key == "assumption_excerpts")
                    and value
                ),
            }
            for receipt in receipts if isinstance(receipt, dict)
        ]
    evidence = details.get("evidence_receipt")
    if isinstance(evidence, dict):
        slim = {
            key: value for key, value in evidence.items()
            if not isinstance(value, (list, dict))
        }
        claims = evidence.get("validated_claims")
        if isinstance(claims, list):
            slim["validated_claims_count"] = len(claims)
        details["evidence_receipt"] = slim
    details["view"] = (
        "compact; the full canonical entry, source receipts and evidence "
        "receipt are stored on the draft and in the cycle record"
    )
    payload["details"] = details
    return payload


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
        assumptions, rationale, source_excerpts, topology_species_mapping
        (optional object {written species exactly as in topology_excerpt ->
        canonical SRD-46 species token, "(solvent)" for spectator water only}
        for chemist notation the host grammar does not read; the host
        validates it and still derives the beta ID) and statement_review
        (optional list of your verdicts on host-parsed value rows, see
        parser_writable_contract.statement_review_rule; never gated).
        source_excerpts must use
        topology_excerpt, beta_definition_excerpt, constant_value_excerpt, uncertainty_excerpt,
        evidence_excerpt, estimation_method_excerpt, assumption_excerpts, and
        rationale_excerpt. Each excerpt must identify one contiguous QueryAgent
        answer span. Only rendering-equivalent Unicode, whitespace, paired
        Markdown emphasis, and inline-code differences are normalized;
        ellipses, paraphrases, and stitched spans fail the source gate.
        Row-bound excerpts (topology, beta_definition, constant_value,
        uncertainty, evidence) may be sent as the opening characters (>= 20,
        verbatim) of the one answer row you mean, and a respelled excerpt
        that closely matches exactly one answer line is replaced by that
        line; the receipt reports both under host_resolved_excerpts with the
        stored line - confirm it.
        assumption_excerpts is a list corresponding one-to-one to assumptions.
        Read and reuse the returned draft_id. Canonical names,
        reactions, species, conditions, solvent fields, constant type, and
        native equilibrium-map row/node IDs are host-owned and forbidden.
        Prefer topology_excerpt and omit beta_definition_id: the host resolves
        the verbatim prose reaction to a canonical definition.  An explicit
        beta-definition remains a legacy parser selector.  Evidence IDs are
        parser-writable selectors. estimation_method, assumptions and
        rationale may be omitted when their excerpts are sent: the host copies
        each whole span (send a value only when it should be a sub-span of
        its excerpt). The reply is a compact receipt; inspect_drafts shows
        the stored content.
        """

        state = self.service.state
        draft = state.create_draft(_object(draft_json, "draft_json"))
        return _json(_draft_receipt(
            draft, "saved_partial", state.revision,
            getattr(state, "last_excerpt_resolution", None),
        ))

    def update_equilibrium_draft(
        self, draft_id: str = "", patch_json: str = ""
    ) -> str:
        """Patch the exact returned draft_id using the same writable contract.

        source_excerpts patches merge per excerpt key: send only the excerpts
        you are changing, and send null for a key to delete its stored span;
        omitted keys keep their stored spans. All other fields are replaced
        whole by the patch value. The same row-pointer rule applies to
        patched excerpts.
        """

        state = self.service.state
        draft = state.update_draft(
            str(draft_id), _object(patch_json, "patch_json")
        )
        return _json(_draft_receipt(
            draft, "updated", state.revision,
            getattr(state, "last_excerpt_resolution", None),
        ))

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
        """Check one exact returned draft_id before running the entry gate.

        A passing check reports the host-resolved equilibrium under
        details.topology_resolution; a failing topology check names the
        written species the host grammar could not place, the closest
        canonical candidates, an implicit-solvent species mapping when one
        makes the span match exactly one catalog equation, and the retry
        routes.
        """

        return _json(self.service.check_draft(str(draft_id)).as_dict())

    def inspect_beta_definition(self, beta_definition_id: str = "") -> str:
        """Read one canonical SRD-46 beta definition by number or beta_def_<id> token.

        Returns the catalog's name, equation_python (written with M, L, H,
        OH, H2O, e tokens), node species, and materializability status.
        Read-only lookup for interpreting gate findings; it is never evidence
        and never binds a draft: a draft's equilibrium is proven only by its
        verbatim answer span (plus topology_species_mapping) or by a
        beta_def_<id> token written in the answer.
        """

        beta_id = _parse_beta_token(beta_definition_id)
        return _json(self.service.catalog.inspect_beta(beta_id))

    def search_canonical_betas(self, query: str = "", limit: str = "10") -> str:
        """Search the materializable canonical catalog, read-only.

        query is a canonical species token ("ML2", "M(OH)L", "HL"), an
        equation written with M/L tokens ("M + L <=> ML",
        "[M] + [L]^2 <=> [ML2]"), or a beta token ("beta_def_812", "812").
        Returns up to `limit` matching beta definitions with their canonical
        names and equations, ranked exact-token, exact-equation, species,
        then text. Results are lookups, never evidence, and never bind a
        draft.
        """

        records = list(
            self.service.catalog.enumerate_materializable_betas().get("records")
            or []
        )
        result = _search_rows(records, str(query or ""), _parse_limit(limit))
        return _json({
            "query": str(query or ""),
            "materializable_count": len(records),
            "n_matches": result["n_matches"],
            "records": result["records"],
            "hint": _SEARCH_HINT_MATCH if result["records"] else _SEARCH_HINT_NO_MATCH,
        })

    def run_entry_gate(self, draft_id: str = "") -> str:
        """After check_draft passes, validate verbatim source and evidence binding.

        The reply is compact: issues in full, the sealed entry as a summary
        (excerpt texts are not echoed back).
        """

        return _json(_slim_entry_report(self.service.run_entry_gate(str(draft_id))))

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
        for the same draft replaces its stored annotation. The receipt's
        stored block reports the discussion length and the id lists as the
        host holds them; your earlier calls appear abbreviated in the
        history, not truncated.
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
                state = self.service.state
                entries: list[dict[str, Any]] = []
                for draft in state.drafts.values():
                    canonical = draft.canonical_equilibrium
                    if canonical is None:
                        continue
                    annotation = state.annotations.get(draft.draft_id)
                    entry: dict[str, Any] = {
                        "draft_id": draft.draft_id,
                        "beta_definition_id": canonical.get("beta_definition_id"),
                        "beta_definition_name": canonical.get("beta_definition_name"),
                        "equation_python": canonical.get("equation_python"),
                        "constant_value": canonical.get("constant_value"),
                        "uncertainty_log10": canonical.get("uncertainty_log10"),
                        "evidence_vlm_ids": list(canonical.get("evidence_vlm_ids") or []),
                        "core_source_ids": (
                            list(annotation.core_source_ids) if annotation else []
                        ),
                    }
                    for key in _COMMITTED_ENTRY_MARKER_KEYS:
                        if canonical.get(key):
                            entry[key] = canonical[key]
                    entries.append(entry)
                return _json({
                    "status": "committed",
                    "query_id": committed.query_id,
                    "network_gate_receipt_sha256": report.receipt_sha256,
                    "n_entries": len(entries),
                    "committed_entries": entries,
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
            "inspect_beta_definition": self.inspect_beta_definition,
            "search_canonical_betas": self.search_canonical_betas,
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
