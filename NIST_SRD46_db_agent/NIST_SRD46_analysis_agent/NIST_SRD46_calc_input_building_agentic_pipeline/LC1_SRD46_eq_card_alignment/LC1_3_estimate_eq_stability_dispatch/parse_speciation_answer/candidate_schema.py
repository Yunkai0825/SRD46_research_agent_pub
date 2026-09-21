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
