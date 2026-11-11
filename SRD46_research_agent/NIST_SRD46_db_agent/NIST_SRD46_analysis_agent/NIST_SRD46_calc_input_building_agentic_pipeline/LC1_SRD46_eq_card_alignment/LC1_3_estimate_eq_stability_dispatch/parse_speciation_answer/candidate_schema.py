"""Host-owned state and handoff records for the LC1.3 parser gate.

The QueryAgent writes ordinary chemistry prose.  These records belong only to
the downstream parser/gate boundary; none of them is a response contract for
the QueryAgent.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class GateOwner(str, Enum):
    PARSER = "parser"
    QUERY_AGENT = "query_agent"
    HOST = "host"


class ParserAction(str, Enum):
    COMMIT = "commit"
    REQUEST_FOLLOWUP = "request_followup"
    NO_ESTIMATE = "no_estimate"
    PARSER_REVISE = "parser_revise"
    FATAL_HOST = "fatal_host"


@dataclass(frozen=True)
class GateIssue:
    code: str
    owner: GateOwner
    message: str
    draft_id: str | None = None
    missing_topics: tuple[str, ...] = ()
    # Structured, JSON-serializable account of the finding (what the host
    # read, what it could not place, which retry routes exist).  The message
    # stays the human/agent-readable summary; details survive truncation of
    # the message in cross-cycle feedback.
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["owner"] = self.owner.value
        payload["missing_topics"] = list(self.missing_topics)
        return payload


@dataclass
class GateReport:
    gate: str
    status: str
    state_revision: int
    issues: list[GateIssue] = field(default_factory=list)
    receipt_sha256: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == "pass" and not self.issues

    def as_dict(self) -> dict[str, Any]:
        return {
            "gate": self.gate,
            "status": self.status,
            "state_revision": self.state_revision,
            "issues": [issue.as_dict() for issue in self.issues],
            "receipt_sha256": self.receipt_sha256,
            "details": self.details,
        }


@dataclass
class EquilibriumDraft:
    draft_id: str
    beta_definition_id: int | None = None
    constant_value: float | None = None
    evidence_vlm_ids: list[int] = field(default_factory=list)
    evidence_network_ids: list[int] = field(default_factory=list)
    evidence_citation_ids: list[int] = field(default_factory=list)
    uncertainty_log10: float | None = None
    estimation_method: str = ""
    assumptions: list[str] = field(default_factory=list)
    rationale: str = ""
    source_excerpts: dict[str, Any] = field(default_factory=dict)
    # Parser-stated reading of the written species in topology_excerpt
    # ({written species -> canonical SRD-46 token, "(solvent)" for spectator
    # water}).  The host validates it against the span and the catalog and
    # still derives beta_definition_id itself.
    topology_species_mapping: dict[str, str] = field(default_factory=dict)
    # Parser verdicts on host-parsed value rows ({row prefix, verdict, note,
    # corrected}).  Information the parser confirms or corrects; the host
    # checks only the row's presence in the transcript and the verdict
    # vocabulary, never gates on it, and carries it to the committed entry.
    statement_review: list[dict[str, Any]] = field(default_factory=list)
    # Host-owned record of the excerpts the host resolved to an answer line
    # on the parser's behalf ({excerpt key -> {how, similarity, stored_line,
    # sent}}; ``how`` is ``prefix`` or ``nearest_match``, see
    # excerpt_resolution).  Cleared per key when the parser re-sends it.
    host_resolved_excerpts: dict[str, Any] = field(default_factory=dict)
    status: str = "partial"
    canonical_equilibrium: dict[str, Any] | None = None
    topology_resolution: dict[str, Any] | None = None
    entry_gate_receipt_sha256: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DraftAnnotation:
    """Parser-authored interpretive digest bound to one gate-sealed draft.

    The digest never enters entry-gate receipts: it is validated separately
    and attached to the committed claim at commit assembly.  ``bound_*``
    digests make the binding tamper-evident: the annotation is live only
    while the draft's current entry receipt equals
    ``bound_entry_receipt_sha256``, and it silently rebinds after a re-seal
    only when the canonical content digest is unchanged.
    """

    draft_id: str
    discussion: str
    core_source_ids: list[str]
    secondary_source_ids: list[str]
    annotation_sha256: str
    bound_entry_receipt_sha256: str
    bound_canonical_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ParsedQuery:
    """Canonical, gate-approved claim set consumed by native map assembly."""

    query_id: str
    scope: dict[str, Any]
    parsed_speciation: dict[str, Any]
    receipts: dict[str, Any]
    evidence_authorization: dict[str, Any]
    evidence_authorization_sha256: str
    answer_sha256: str
    artifact_dir: str
    # Session-relative path of the QueryAgent ``answer.md`` the parser bound
    # to (the reporting turn when accepted, else the exploration answer);
    # "" when the host could not match it.  Travels to the card's source cell.
    answer_path: str = ""


@dataclass
class ParserCycleResult:
    action: ParserAction
    reason: str = ""
    missing_topics: list[str] = field(default_factory=list)
    tool_history: list[dict[str, Any]] = field(default_factory=list)
    agent_answer: str = ""
    final_context: str = ""
    elapsed_s: float = 0.0
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "reason": self.reason,
            "missing_topics": list(self.missing_topics),
            "tool_history": list(self.tool_history),
            "agent_answer": self.agent_answer,
            "final_context": self.final_context,
            "elapsed_s": self.elapsed_s,
            "error": self.error,
        }


@dataclass
class ParseResult:
    parsed_queries: list[ParsedQuery]
    failures: list[dict[str, Any]]
    manifest_path: str
    workspaces: dict[str, Any] = field(default_factory=dict, repr=False)
    source_transcripts: dict[str, str] = field(default_factory=dict, repr=False)
    repair_audit: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "manifest_path": self.manifest_path,
            "n_parsed": len(self.parsed_queries),
            "n_failed": len(self.failures),
            "failures": list(self.failures),
            "repair_audit": dict(self.repair_audit),
            "queries": [
                {
                    "query_id": row.query_id,
                    "scope": row.scope,
                    "answer_sha256": row.answer_sha256,
                    "answer_path": row.answer_path,
                    "evidence_authorization_sha256": (
                        row.evidence_authorization_sha256
                    ),
                    "artifact_dir": row.artifact_dir,
                    "n_equilibria": len(
                        row.parsed_speciation.get("chemical_pairs", [{}])[0]
                        .get("equilibria", [])
                    ),
                }
                for row in self.parsed_queries
            ],
        }


__all__ = [
    "EquilibriumDraft",
    "GateIssue",
    "GateOwner",
    "GateReport",
    "ParseResult",
    "ParsedQuery",
    "ParserAction",
    "ParserCycleResult",
]
