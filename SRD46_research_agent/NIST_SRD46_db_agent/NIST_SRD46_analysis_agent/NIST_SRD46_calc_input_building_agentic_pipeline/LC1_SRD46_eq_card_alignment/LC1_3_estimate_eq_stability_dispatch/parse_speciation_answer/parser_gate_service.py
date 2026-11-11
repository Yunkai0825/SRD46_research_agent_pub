"""Deterministic entry and whole-network gates for parser-created drafts."""

from __future__ import annotations

import difflib
import json
import math
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

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
    SOLVENT_MAPPING_TOKEN,
    TopologyResolutionError,
    _extract_reaction,
    _is_metal_species,
    _metal_symbol,
    _normalize_rendering,
    _side_terms,
    _split_reaction,
    beta_names_equal,
    diagnose_topology_excerpt,
    has_reaction_arrow,
    resolve_canonical_topology,
    written_beta_names,
)
from .evidence_gate import EvidenceGateError, validate_evidence_snapshot
from .no_estimate_conclusion import has_no_estimate_conclusion
from .excerpt_resolution import EXCERPT_RESOLUTION_RULE
from .parser_working_state import ParserWorkingState, canonical_sha256
from .source_grounding import (
    _NUMBER_RE,
    SourceGroundingError,
    _bind_number,
    _canonical_source_text,
    _source_contains,
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
        "one contiguous answer span containing beta_def_<id>; when that span "
        "also states a reaction or a catalog-style name ([ML]/[M][L]), the "
        "host reads them and rejects a token that names a different "
        "equilibrium — the stated reaction is the chemistry, the ID is a label"
    ),
    "constant_value_excerpt": (
        "one contiguous answer span containing constant_value; on the "
        "topology route it must contain the topology_excerpt reaction (use "
        "the complete reaction row), on the legacy beta_definition_id route "
        "it must contain beta_def_<id>"
    ),
    "uncertainty_excerpt": (
        "one contiguous answer span containing uncertainty_log10; on the "
        "topology route it must contain the topology_excerpt reaction, and "
        "in a multi-beta answer on the legacy route also beta_def_<id>"
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
    details: Mapping[str, Any] | None = None,
) -> GateIssue:
    return GateIssue(
        code=code,
        owner=owner,
        message=message,
        draft_id=draft_id,
        missing_topics=tuple(topic for topic in topics if topic),
        details=dict(details or {}),
    )


_TOPOLOGY_SPECIES_MAPPING_RULE = (
    "Optional, for a topology_excerpt whose chemist notation the host grammar "
    "does not read (explicit aqua ligands such as [Fe(H2O)6]3+, a hydroxo or "
    "protonated ligand written inside the complex, outer-sphere braces). The "
    "grammar reads one scoped metal, one scoped ligand, and H, OH, H2O, e. "
    "Keep the verbatim span and state, per written species exactly as it "
    "appears there, which canonical SRD-46 species it is (M, L, ML, ML2, HL, "
    f"M(OH)L, ...) or {SOLVENT_MAPPING_TOKEN!r} for spectator water only. The "
    "host validates every entry against the span and the catalog vocabulary, "
    "records the mapping in the resolution receipt, and still derives "
    "beta_definition_id itself. Never rewrite the reaction span instead."
)

_CATALOG_READ_TOOLS = ["inspect_beta_definition", "search_canonical_betas"]
_CATALOG_READ_TOOLS_RULE = (
    "Read-only lookups of the materializable SRD-46 catalog (beta IDs, names, "
    "equations, species tokens) for interpreting gate findings. They are "
    "never evidence and never bind a draft: a draft's equilibrium is proven "
    "only by its verbatim answer span (plus topology_species_mapping) or by "
    "a beta_def_<id> token written in the answer."
)


_EVIDENCE_RULE = (
    "evidence_vlm_ids, evidence_network_ids and evidence_citation_ids may cite "
    "only records listed in prose_cited_authorized_ids: records the QueryAgent "
    "saw through a tool in this session AND cited in its answer. Ids the "
    "answer names without such a record are listed in "
    "prose_cited_unauthorized_ids and cannot be cited by the parser; drop them "
    "from evidence_vlm_ids and the evidence_excerpt, or, when the answer's "
    "argument rests on them, request_followup with topic supporting_evidence "
    "so the QueryAgent grounds them through a tool. On the beta_def token "
    "route at least one cited VLM must carry that beta_def itself; after a "
    "host topology resolution analogue VLMs (other beta_defs, other metals) "
    "are accepted."
)

_EVIDENCE_HINT_ID_LIMIT = 12

# How many QueryAgent follow-ups the entry gate may spend on anchors the
# answer cites without a tool record before committing on the authorized
# evidence alone. The orchestrator caps it by
# LC13Settings.query_clarification_retries.
_UNGROUNDED_ANCHOR_FOLLOWUP_BUDGET = 3

_ANSWER_PRECEDENCE_RULE = (
    "The transcript is the QueryAgent's assistant answers in order: the "
    "initial answer, then each follow-up addendum (answer_turns). Where a "
    "later answer restates the same equilibrium for the same metal ion at "
    "the same conditions, bind constant_value_excerpt and "
    "uncertainty_excerpt to the later statement. A row for another ion "
    "(Fe2+ in a Fe3+ pair), at other conditions (another temperature, ionic "
    "strength or medium) or for another equilibrium is a different quantity, "
    "never a restatement. A follow-up that only adds a missing topic leaves "
    "the earlier statements valid. The host does not enforce this: the entry "
    "gate reports later rows that state other numbers under the same "
    "equilibrium template as other_value_statements, with the ion and "
    "conditions it parsed from each row, and you decide (statement_review)."
)

_LATEST_STATEMENTS_RULE = (
    "Host-parsed index of the answers' value rows: a reading aid, never a "
    "gate, and it can be wrong - confirm it against the text. equilibria: "
    "one entry per canonical equilibrium template the host grammar resolves, "
    "listing every row that states that reaction with a value (statements, "
    "in turn order) together with what the host read from the row: "
    "metal_species (the bare metal ion as written, its charge, whether it "
    "matches the scoped metal), conditions (temperature_C, ionic_strength_M, "
    "medium when the row states them, else null) and in_scope (the ion and "
    "the stated conditions agree with the request). latest_in_scope is the "
    "host's suggestion of the row to bind; the span you bind is still "
    "checked literally. token_mentions: rows that write a beta_def_<id> token "
    "beside a number without a resolvable reaction; the answer is often citing "
    "an anchor record under that beta id there, so a mention is not a "
    "statement of the target unless the answer binds by token (legacy route). "
    "unresolved_value_rows: reaction rows with a value the host could not "
    "place (anchor systems outside the scope, notation needing a species "
    "mapping) - they may hold estimates you must read yourself."
)
# How many unplaceable reaction-with-value rows the index quotes back.
_UNRESOLVED_VALUE_ROW_SAMPLE = 10
_LATEST_BETA_TOKEN_RE = re.compile(r"(?i)\bbeta_def_(\d+)\b")

_HOST_TURN_BUDGET_RULE = (
    "The host sends at most host_turn_ceiling turns to the QueryAgent per "
    "pair (clarifications and continuations together) and none once the "
    "assistant-answer transcript reaches transcript_char_ceiling characters "
    "(0 = no ceiling). Past either, a request_followup cannot be served: the "
    "pair ends reference_only with the ceiling recorded in the audit. So "
    "request a follow-up only for chemistry genuinely absent from the prose, "
    "and bind everything else from the transcript at hand. host_turns_used "
    "counts the accepted QueryAgent turns after the initial answer."
)

_ASSUMPTIONS_RULE = (
    "assumptions are the premises the answer itself states the estimate rests "
    "on: coordination mode or donor atom, solvent or medium model, the "
    "transfer or scaling rule, the ionic-strength and temperature treatment, "
    "reference-state choices. Copy each as one contiguous span into "
    "assumption_excerpts (one-to-one with assumptions, or omit assumptions and "
    "the host copies the spans). A premise stated inside the method sentence "
    "('treating DMF as a carbonyl-O donor') is an assumption. Never infer one "
    "the answer does not state: assumptions absent from the prose are a "
    "request_followup topic."
)

_HOST_COPIES_RULE = (
    "estimation_method, rationale and assumptions may be omitted: the host "
    "copies each whole from estimation_method_excerpt, rationale_excerpt and "
    "assumption_excerpts, so a long reasoning chain is sent once. Send the "
    "value only when it should be a sub-span of its excerpt."
)

_OPTIONAL_ROWS_RULE = (
    "Rows or estimates the answer marks optional, tentative or 'if needed' "
    "are still estimates: extract each as its own draft. The host records "
    "the marker on the committed entry (answer_marked_optional) and "
    "downstream decides whether to use it; say in the annotation that the "
    "answer marked it optional and why."
)

_UNGROUNDED_ANCHOR_RULE = (
    "An anchor is a record the answer's reasoning rests on (a value used in "
    "the chain). When the draft's estimation_method, evidence or rationale "
    "span names a vlm_N listed in prose_cited_unauthorized_ids (the QueryAgent "
    "never read it through a tool in this session), the entry gate reports "
    "ungrounded_anchor_evidence and authorizes request_followup with topic "
    "supporting_evidence so the QueryAgent grounds it. This repeats up to the "
    "follow-up budget; afterwards the entry passes and the committed record "
    "lists ungrounded_anchor_vlm_ids for downstream review."
)

_GLOSSARY = {
    "topology route": (
        "the draft binds its equilibrium through source_excerpts.topology_excerpt "
        "(a stated reaction, plus topology_species_mapping when the notation "
        "needs it); the host derives beta_definition_id and analogue evidence "
        "is accepted"
    ),
    "token route (legacy)": (
        "the draft binds through beta_definition_id plus a "
        "beta_definition_excerpt span containing that literal beta_def_<id>; "
        "at least one cited VLM must carry the same beta_def"
    ),
    "session-observed": (
        "a record the QueryAgent read through a tool in this conversation; it "
        "is in the evidence snapshot whether or not the answer cites it"
    ),
    "prose_cited_authorized_ids": (
        "session-observed records that the answer also cites: the only ids a "
        "draft may cite"
    ),
    "prose_cited_unauthorized_ids": (
        "ids the answer names without a session tool record; they cannot be "
        "cited (drop them, or request_followup with topic supporting_evidence)"
    ),
    "matching_beta_vlm_ids": (
        "cited VLMs whose SRD-46 record carries the draft's own beta_def; on "
        "the token route at least one is required"
    ),
    "analogue_vlm_ids": (
        "cited VLMs recorded under another beta_def or another metal; accepted "
        "as evidence only after a host topology resolution"
    ),
    "written_labels_overridden": (
        "beta_def tokens or [ML]/[M][L] names written beside the stated "
        "reaction that name a different equilibrium; the reaction governs and "
        "the labels are reported, not enforced"
    ),
    "other_value_statements": (
        "reported by the entry gate, never blocking: later answer rows that "
        "state other numbers under the draft's equilibrium template, each "
        "with the metal ion and conditions the host parsed from the row and "
        "its relation to the bound row (same_ion_same_conditions, other_ion, "
        "other_conditions, unconfirmed); a same-ion same-conditions later row "
        "is the one to bind, the others are different quantities - record "
        "your reading in statement_review"
    ),
    "statement_review": (
        "parser-writable list of your verdicts on host-parsed value rows "
        "({row prefix, verdict, note, corrected}); the host checks only that "
        "the row is in the transcript and the verdict is in the vocabulary; "
        "reviewed rows leave other_value_statements and the review travels "
        "with the committed entry"
    ),
    "latest_statements": (
        "the host's parsed index of value rows: per canonical equilibrium "
        "template every row stating its reaction with a value, with the "
        "metal ion, charge and conditions read from the row and whether it "
        "is in scope; latest_in_scope is a suggestion; token_mentions are "
        "beta_def tokens written beside a number without a reaction (often "
        "an anchor citation); a reading aid, never a gate (bound spans are "
        "still checked literally)"
    ),
    "host_turn_budget": (
        "the host's ceilings on QueryAgent turns per pair (clarifications "
        "plus continuations) and on the transcript size; past either, a "
        "request_followup cannot be served and the pair ends reference_only "
        "with the ceiling recorded"
    ),
    "ungrounded_anchor_vlm_ids": (
        "VLMs the reasoning rests on that were never tool-observed; sent back "
        "to the QueryAgent while the follow-up budget lasts, recorded on the "
        "committed entry afterwards"
    ),
    "answer_marked_optional": (
        "the answer marked this row optional, tentative or 'if needed'; the "
        "entry is committed with the marker for downstream to weigh"
    ),
    "truncation_suspected": (
        "the host's tail heuristic that an assistant answer ends mid-text; "
        "spans from that turn's tail are unreliable and chemistry missing "
        "because of the cut is a request_followup topic"
    ),
    "output_truncated": (
        "from the model's usage record: true means the turn stopped at the "
        "QueryAgent output cap (certain, not a heuristic); false means the "
        "model stopped on its own, so an odd-looking tail is deliberate"
    ),
    "continuation": (
        "an answer turn the host requested after a cut (kind: continuation): "
        "the QueryAgent resuming its preceding answer; read it as that "
        "answer's tail, not as a correction, unless it says so"
    ),
    "reporting": (
        "an answer turn the host requested after the exploration answer (kind: "
        "reporting): the QueryAgent restating each estimate in a structured "
        "form with ids, conditions and step-by-step provenance; where it "
        "restates an equilibrium for the same metal ion at the same "
        "conditions, bind from the report"
    ),
}

_OPTIONAL_MARKER_RE = re.compile(
    r"(?i)\b(?:optional(?:ly)?|tentative(?:ly)?|if (?:needed|required|desired)|"
    r"only if|not required|speculative)\b"
)
# A later-turn row "restates the quantity" when it announces a value: a log K
# or log beta label, an approximation or equality sign (not the <=> arrow),
# or the words value/estimate, followed within 40 non-digit characters by a
# number.  The "10" of a "log10" label is not that number ("estimate log10 K
# = 0.3" states 0.3, not 10).
_VALUE_STATEMENT_RE = re.compile(
    r"(?i)(?:log\s*(?:10)?\s*(?:k|β|beta)\w*|≈|~|(?<![<=>])=(?![>=])|\bvalue\b|"
    r"\bestimate[sd]?\b)[^\d\n]{0,40}?(?<!log)[-+]?\d+(?:\.\d+)?"
)
# The number a value statement ends with, and the numbers written after "±".
_STATED_NUMBER_TAIL_RE = re.compile(r"[-+]?\d+(?:\.\d+)?$")
_STATED_UNCERTAINTY_RE = re.compile(r"±\s*([-+]?\d+(?:\.\d+)?)")


def _stated_numbers(
    canonical_row: str, statements: list[re.Match[str]],
) -> tuple[list[float], list[float]]:
    """What a row states as values (closing each value statement) and as uncertainties (after ±)."""

    values = [
        float(tail.group(0))
        for tail in (
            _STATED_NUMBER_TAIL_RE.search(match.group(0)) for match in statements
        )
        if tail is not None
    ]
    uncertainties = [
        float(match.group(1))
        for match in _STATED_UNCERTAINTY_RE.finditer(canonical_row)
    ]
    return values, uncertainties


_SUPERSEDED_RETRY_OPTIONS = [
    "topology_excerpt", "constant_value_excerpt", "uncertainty_excerpt",
    "constant_value", "uncertainty_log10",
]

# --------------------------------------------------------------------------
# Host-parsed reading of value rows (never a gate)
# --------------------------------------------------------------------------
#
# Hard gates cover the structured downstream requirements: the equilibrium
# map (beta definition and its equilibrium), literal spans, and materializable
# evidence. Which row of the answer states which value, for which ion, at
# which conditions, is secondary information: the host parses it, shows what
# it read, and the parser confirms or corrects it.

_STATEMENT_REVIEW_VERDICTS = (
    "same_quantity_later",      # the listed row is the same quantity and later: rebind to it
    "same_quantity_restated",   # same quantity, same numbers (a confirmation)
    "other_ion",                # another metal ion (Fe2+ in a Fe3+ pair)
    "other_conditions",         # another temperature, ionic strength or medium
    "other_equilibrium",        # another reaction the host grammar conflated
    "anchor_citation",          # an anchor record quoted under the template, not the estimate
    "not_a_value_statement",    # the host read a number that is not a value (an ordinal, a label)
)
_STATEMENT_REVIEW_CORRECTABLE = (
    "metal_species", "temperature_C", "ionic_strength_M", "medium",
)
_STATEMENT_REVIEW_MIN_ROW_CHARS = 20
_STATEMENT_REVIEW_RULE = (
    "statement_review (optional, never gated): your reading of the "
    "host-parsed value rows the entry gate lists under other_value_statements "
    "(or any row of latest_statements). A list of objects {row: a literal "
    f"prefix of that transcript row, at least {_STATEMENT_REVIEW_MIN_ROW_CHARS} "
    "characters copied as written; verdict: one of "
    + ", ".join(_STATEMENT_REVIEW_VERDICTS)
    + "; note: optional free text; corrected: optional object with any of "
    + ", ".join(_STATEMENT_REVIEW_CORRECTABLE)
    + " when the host read an attribute wrongly}. The host checks only that "
    "the row occurs in the transcript and the verdict is in the list; "
    "reviewed rows leave other_value_statements and the review is recorded on "
    "the committed entry. same_quantity_later means the draft should be "
    "rebound to that row (patch the excerpts and numbers)."
)

_ROW_TEMPERATURE_RE = re.compile(
    r"(?<![\d.])(-?\d{1,3}(?:\.\d+)?)\s*(?:°\s*C\b|℃|deg(?:rees)?\s*C\b)"
    r"|(?:\bT\s*=\s*)(-?\d{1,3}(?:\.\d+)?)\b"
)
_ROW_IONIC_RE = re.compile(
    r"(?:\bI\s*(?:=|≈|~)\s*)(\d+(?:\.\d+)?)\s*(?:M\b|mol)?"
    r"|(?<![\w.])(\d+(?:\.\d+)?)\s*(?:M\b|mol\s*(?:/|per)\s*(?:L|dm))"
    r"|(\binfinite dilution\b)"
)
_ROW_MEDIUM_WORDS = (
    ("water", ("water", "aqueous", "aq)", "(aq", "h2o")),
    ("acetonitrile", ("acetonitrile", "mecn", "ch3cn")),
    ("methanol", ("methanol", "meoh")),
    ("ethanol", ("ethanol", "etoh")),
    ("dmso", ("dmso", "dimethyl sulfoxide", "dimethylsulfoxide")),
    ("dmf", ("neat dmf", "in dmf", "dmf solvent", "dimethylformamide solvent")),
    ("mixed", ("mixed solvent", "mixture", "% ", "v/v", "w/w")),
)
_WATER_MEDIA = {"water", "aqueous", "aq"}
# A reporting-table triplet of condition cells: | 25.0 | 0.1 | water |
_ROW_CONDITION_CELLS_RE = re.compile(
    r"\|\s*(-?\d{1,3}(?:\.\d+)?)\s*\|\s*(\d+(?:\.\d+)?)\s*\|\s*"
    r"([A-Za-z][A-Za-z0-9 ,./()%-]{0,40}?)\s*\|"
)
_METAL_CHARGE_RE = re.compile(r"\^?\[?(\d*)([+-]+)\]?$")


def _row_conditions(row: str) -> dict[str, Any]:
    """Temperature, ionic strength and medium a row states (null when it does not).

    Explicit markers first (``25 °C``, ``T = 25``, ``I = 0.1 M``, ``infinite
    dilution``, a solvent word), then the reporting table's condition cells
    ``| T | I | medium |``.  Heuristic by design: the result is shown to the
    parser as host-parsed and can be corrected in ``statement_review``.
    """

    text = _normalize_rendering(row)
    lowered = text.lower()
    temperature: float | None = None
    ionic: float | None = None
    medium: str | None = None
    match = _ROW_TEMPERATURE_RE.search(text)
    if match:
        temperature = float(match.group(1) or match.group(2))
    match = _ROW_IONIC_RE.search(text)
    if match:
        if match.group(3):
            ionic = 0.0
        else:
            ionic = float(match.group(1) or match.group(2))
    for name, words in _ROW_MEDIUM_WORDS:
        if any(word in lowered for word in words):
            medium = name
            break
    if temperature is None and ionic is None:
        cells = _ROW_CONDITION_CELLS_RE.search(text)
        if cells:
            t_cell, i_cell, m_cell = cells.groups()
            if -50.0 <= float(t_cell) <= 350.0 and 0.0 <= float(i_cell) <= 20.0:
                temperature = float(t_cell)
                ionic = float(i_cell)
                if medium is None:
                    medium = m_cell.strip().lower()
    if medium in _WATER_MEDIA:
        medium = "water"
    return {
        "temperature_C": temperature,
        "ionic_strength_M": ionic,
        "medium": medium,
    }


def _species_charge(species: str) -> int | None:
    """Signed charge written on a species (``Fe^[3+]`` 3, ``Fe2+`` 2, ``OH-`` -1)."""

    text = _normalize_rendering(species)
    text = re.sub(r"\((?:aq|l|g|s)\)$", "", text, flags=re.I).strip()
    match = _METAL_CHARGE_RE.search(text)
    if match is None:
        return None
    digits, signs = match.group(1), match.group(2)
    magnitude = int(digits) if digits else len(signs)
    return -magnitude if signs[0] == "-" else magnitude


def _scope_metal(scope: Mapping[str, Any]) -> dict[str, Any]:
    """The scoped metal's element symbol and the charge its name carries."""

    try:
        symbol = _metal_symbol(scope)
    except TopologyResolutionError:
        symbol = ""
    return {
        "symbol": symbol,
        "charge": _species_charge(str(scope.get("metal_name") or "")),
        "name": str(scope.get("metal_name") or ""),
    }


def _row_metal_species(row: str, scope: Mapping[str, Any]) -> dict[str, Any]:
    """The bare metal ion a reaction row writes, its charge, and whether it is the scoped metal.

    ``matches_scope`` is None when either the row or the scope carries no
    charge (``Fe`` alone is read as the scoped metal).
    """

    scoped = _scope_metal(scope)
    written: str | None = None
    try:
        lhs, rhs = _split_reaction(_extract_reaction(row))
        for term, _coefficient in _side_terms(lhs) + _side_terms(rhs):
            if scoped["symbol"] and _is_metal_species(term, scoped["symbol"]):
                written = term
                break
    except TopologyResolutionError:
        written = None
    charge = _species_charge(written) if written else None
    matches: bool | None = None
    if charge is not None and scoped["charge"] is not None:
        matches = charge == scoped["charge"]
    return {"written": written, "charge": charge, "matches_scope": matches}


def _conditions_agree(
    stated: Mapping[str, Any], reference: Mapping[str, Any],
) -> bool | None:
    """Whether a row's stated conditions agree with a reference (None = unstated)."""

    seen_any = False
    for key, tolerance in (("temperature_C", 0.5), ("ionic_strength_M", 1e-6)):
        value, expected = stated.get(key), reference.get(key)
        if value is None or expected is None:
            continue
        seen_any = True
        if abs(float(value) - float(expected)) > tolerance:
            return False
    medium, expected_medium = stated.get("medium"), reference.get("medium")
    if medium is not None and expected_medium is not None:
        seen_any = True
        if str(medium).lower() != str(expected_medium).lower():
            return False
    return True if seen_any else None


def _statement_relation(
    *,
    other_metal: Mapping[str, Any],
    other_conditions: Mapping[str, Any],
    bound_conditions: Mapping[str, Any],
    request_conditions: Mapping[str, Any],
) -> str:
    """How a later same-template row relates to the bound row, as the host reads it."""

    if other_metal.get("matches_scope") is False:
        return "other_ion"
    reference = {
        key: (
            bound_conditions.get(key)
            if bound_conditions.get(key) is not None
            else request_conditions.get(key)
        )
        for key in ("temperature_C", "ionic_strength_M", "medium")
    }
    agreement = _conditions_agree(other_conditions, reference)
    if agreement is False:
        return "other_conditions"
    if other_metal.get("matches_scope") is None:
        # The row writes no charge on the metal (or no bare metal the host
        # can read): the parser decides.
        return "unconfirmed"
    # A row that states no conditions is read under the same implicit
    # conditions as the bound row; the parser can still rule otherwise.
    return "same_ion_same_conditions"


_NEAREST_LINE_LIMIT = 3
_OTHER_VALUE_STATEMENT_LIMIT = 6


def _nearest_transcript_lines(
    needle: str,
    transcript: str,
    *,
    limit: int = _NEAREST_LINE_LIMIT,
    prefer_reaction: bool = False,
) -> list[dict[str, Any]]:
    """The transcript lines most similar to a span the host could not trace.

    Shown to the parser so it copies the row it meant instead of guessing at
    the spelling; ``prefer_reaction`` restricts the candidates to lines that
    write an equilibrium arrow when any exist.
    """

    target = _canonical_source_text(needle)
    if not target:
        return []
    lines = [line.strip() for line in str(transcript).splitlines() if line.strip()]
    if prefer_reaction:
        reaction_lines = [line for line in lines if has_reaction_arrow(line)]
        if reaction_lines:
            lines = reaction_lines
    scored: list[tuple[float, str]] = []
    for line in lines:
        candidate = _canonical_source_text(line)
        matcher = difflib.SequenceMatcher(None, candidate, target)
        if matcher.quick_ratio() < 0.3:
            continue
        scored.append((matcher.ratio(), line))
    scored.sort(key=lambda item: -item[0])
    return [
        {"row": line[:240], "similarity": round(score, 2)}
        for score, line in scored[:limit]
    ]


def _untraceable_span_hint(nearest: list[Mapping[str, Any]], *, what: str) -> str:
    """Refinement text for a span that is not the answer's text."""

    parts = [
        f" The host did not read the chemistry of this {what} because it is "
        "not a span of the QueryAgent answer (only rendering-equivalent "
        "Unicode, whitespace, paired Markdown emphasis and inline code are "
        "tolerated; an ASCII respelling of charges or arrows, an ellipsis, a "
        "paraphrase or stitched fragments are not)."
    ]
    if nearest:
        parts.append(
            " Nearest answer lines: "
            + "; ".join(
                f"{index}) {row['row']!r} (similarity {row['similarity']})"
                for index, row in enumerate(nearest, start=1)
            )
            + "."
        )
    parts.append(
        " Copy the line you mean exactly as it stands there. If its notation "
        "lies outside the host grammar, keep that verbatim span and add "
        "topology_species_mapping; never respell the reaction."
    )
    return "".join(parts)


def _untraceable_excerpts_hint(details: Mapping[str, Any]) -> str:
    """Refinement text for ``source_binding_failed`` naming each untraceable span."""

    untraceable = details.get("untraceable_excerpts") or {}
    if not untraceable:
        return ""
    parts = [
        " Spans that are not the answer's text (copy the row you mean exactly "
        "as it stands; only rendering-equivalent Unicode, whitespace, paired "
        "Markdown emphasis and inline code are tolerated):"
    ]
    for label, row in untraceable.items():
        nearest = row.get("nearest_transcript_lines") or []
        parts.append(f" {label}: {str(row.get('excerpt_head'))[:80]!r}")
        if nearest:
            parts.append(
                " - nearest answer lines: "
                + "; ".join(
                    f"{line['row'][:160]!r} (similarity {line['similarity']})"
                    for line in nearest
                )
            )
        parts.append(";")
    return "".join(parts).rstrip(";") + "."


def _evidence_failure_hint(details: Mapping[str, Any]) -> str:
    """Route-first text for an ``evidence_gate_failed`` issue.

    Names the offending ids and the ids that remain citable, so the parser
    (or the next cycle, which only sees this text) can repair the cite list
    without bisecting it against ``prose_cited_authorized_ids``.
    """

    parts: list[str] = []
    unobserved = list(details.get("unobserved_vlm_ids") or [])
    if unobserved:
        parts.append(
            " — " + ", ".join(f"vlm_{value}" for value in unobserved)
            + (" is" if len(unobserved) == 1 else " are")
            + " not in prose_cited_authorized_ids (the QueryAgent never saw "
            "them through a tool in this session): remove them from "
            "evidence_vlm_ids and the evidence_excerpt, or request_followup "
            "with topic supporting_evidence if the answer's argument rests "
            "on them"
        )
    non_canonical = list(details.get("non_canonical_vlm_ids") or [])
    if non_canonical:
        parts.append(
            " — " + ", ".join(f"vlm_{value}" for value in non_canonical)
            + " cannot be materialized from SRD-46 (non-canonical record); "
            "drop it from evidence_vlm_ids"
        )
    if details.get("evidence_rule") == "same_beta_evidence":
        parts.append(
            f" — on the beta_def token route at least one cited VLM must carry "
            f"beta_def_{details.get('beta_definition_id')} itself; analogue "
            "records count only after a host topology resolution (rebind the "
            "draft through source_excerpts.topology_excerpt), otherwise cite a "
            "same-beta VLM from prose_cited_authorized_ids"
        )
    for key, prefix in (
        ("unobserved_network_ids", "ref_eq_net"),
        ("unobserved_literature_ids", "lit"),
    ):
        values = list(details.get(key) or [])
        if values:
            parts.append(
                " — " + ", ".join(f"{prefix}_{value}" for value in values)
                + " not in prose_cited_authorized_ids; drop or request_followup"
            )
    citable = list(details.get("prose_cited_authorized_vlm_ids") or [])
    if citable and (unobserved or non_canonical):
        shown = ", ".join(f"vlm_{value}" for value in citable[:_EVIDENCE_HINT_ID_LIMIT])
        more = len(citable) - _EVIDENCE_HINT_ID_LIMIT
        parts.append(
            "; citable VLMs here: " + shown
            + (f" (+{more} more in inspect_parser_context)" if more > 0 else "")
        )
    return "".join(parts)


def _topology_failure_hint(diagnosis: Mapping[str, Any]) -> str:
    """Route-first text for a ``topology_resolution_failed`` issue.

    The structured ``diagnosis`` travels in ``GateIssue.details``; this text
    is what the parser (and the next-cycle feedback) reads first, so the
    unreadable species and the retry routes come before the candidate list.
    """

    parts: list[str] = []
    unresolved = [str(item) for item in diagnosis.get("unresolved_species") or []]
    if unresolved:
        parts.append(
            " The host grammar read species it cannot place in the canonical "
            "vocabulary: " + ", ".join(unresolved) + "."
        )
    elif diagnosis.get("parse_error"):
        parts.append(" Grammar: " + str(diagnosis["parse_error"]) + ".")
    suggested = diagnosis.get("suggested_resolution") or {}
    mapping = diagnosis.get("suggested_species_mapping") or {}
    if suggested and mapping:
        parts.append(
            " Under SRD-46's implicit-solvent convention this span matches "
            f"beta_def_{suggested['beta_definition_id']} "
            f"`{suggested['equation_python']}`; if that is the chemistry the "
            "answer states, confirm it by patching topology_species_mapping "
            + json.dumps(mapping, ensure_ascii=False)
            + " (the host records the mapping in the receipt)."
        )
    candidates = [
        row for row in (diagnosis.get("closest_candidates") or [])
        if not suggested
        or row.get("beta_definition_id") != suggested.get("beta_definition_id")
    ][:3]
    if candidates:
        parts.append(
            " Closest materializable candidates: "
            + "; ".join(
                f"beta_def_{row['beta_definition_id']} `{row['equation_python']}` "
                f"(score {float(row['score']):.2f})"
                for row in candidates
            )
            + "."
        )
    elif not suggested:
        parts.append(
            " No materializable canonical candidates exist for this pair; if "
            "the answer names no matching canonical equilibrium, conclude the "
            "cycle honestly."
        )
    readable = diagnosis.get("readable_reaction_rows") or []
    if readable:
        parts.append(
            " Answer rows the host grammar already resolves (copy one verbatim "
            "if it states this estimate): "
            + "; ".join(
                f"turn {row.get('turn')}: {str(row.get('row'))[:120]!r} -> "
                f"beta_def_{row.get('beta_definition_id')}"
                + ("" if row.get("in_scope") is not False else " (host reads it as out of scope)")
                for row in readable
            )
            + "."
        )
    parts.append(
        " Retry with (a) a topology_excerpt that is one contiguous answer span "
        "stating one concrete reaction (real species, not generic [M]/[L] "
        "placeholder rows); (b) when the answer binds this estimate to a beta "
        "ID, a source_excerpts.beta_definition_excerpt span containing that "
        "literal beta_def_<id> token; or (c) when the chemist's notation is "
        "the problem, keep the verbatim span and patch topology_species_mapping "
        f"{{written species -> canonical token, {SOLVENT_MAPPING_TOKEN!r} for "
        "spectator water only}}; search_canonical_betas / "
        "inspect_beta_definition show the catalog vocabulary (read-only; "
        "lookups are not evidence)."
    )
    return "".join(parts)


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
        ungrounded_anchor_followup_budget: int = _UNGROUNDED_ANCHOR_FOLLOWUP_BUDGET,
        host_turn_ceiling: int = 0,
        transcript_char_ceiling: int = 0,
    ) -> None:
        self.state = state
        self.base_eq_map_card = base_eq_map_card
        self.session_id = str(session_id)
        self.artifact_dir = Path(artifact_dir)
        self.catalog = catalog or DEFAULT_CATALOG
        self.ungrounded_anchor_followup_budget = max(
            0, int(ungrounded_anchor_followup_budget)
        )
        # Host-enforced ceilings (0 = none), shown in the parser context.
        self.host_turn_ceiling = max(0, int(host_turn_ceiling))
        self.transcript_char_ceiling = max(0, int(transcript_char_ceiling))
        self.committed_query: ParsedQuery | None = None
        self.last_support_document: dict[str, Any] | None = None
        # latest_statements() per transcript digest; a new answer turn moves it.
        self._latest_statements_cache: tuple[str, dict[str, Any]] | None = None
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

    def _prose_cited_id_partition(
        self,
    ) -> tuple[dict[str, list[int]], dict[str, list[int]], dict[str, int]]:
        """Split every id the answer names into citable and non-citable.

        Citable ("authorized") means the QueryAgent saw the record through a
        tool in this session, so it is in the evidence snapshot.  The
        remainder — ids the answer wrote from memory or elided lists — is
        surfaced too, so the parser knows before the entry gate which anchors
        of the argument it cannot cite and must drop or send back.
        """

        snapshot = self.state.evidence_snapshot
        transcript = self.state.transcript
        authorized_ids: dict[str, list[int]] = {}
        unauthorized_ids: dict[str, list[int]] = {}
        totals: dict[str, int] = {}
        for public_key, snapshot_key in _SNAPSHOT_ID_KEYS.items():
            authorized = {
                int(value) for value in (snapshot.get(snapshot_key) or [])
            }
            mentioned = {
                int(match.group(1))
                for match in _ANSWER_ID_PATTERNS[public_key].finditer(transcript)
            }
            authorized_ids[public_key] = sorted(authorized & mentioned)
            unauthorized_ids[public_key] = sorted(mentioned - authorized)
            totals[public_key] = len(authorized)
        return authorized_ids, unauthorized_ids, totals

    def prose_cited_unauthorized_ids(self) -> dict[str, list[int]]:
        """Ids the answers name that no tool in this session returned.

        Only the record kinds the QueryAgent cites in its own tokens (vlm,
        network, literature); beta-definition tokens are left out because
        the host never echoes them to the Query side.
        """

        _, unauthorized, _ = self._prose_cited_id_partition()
        return {
            key: list(values)
            for key, values in unauthorized.items()
            if key != "beta_definition_ids"
        }

    def parser_context(self) -> dict[str, Any]:
        active_followup_receipts = (
            self.state.active_query_followup_authorizations()
        )
        cited_authorized_ids, cited_unauthorized_ids, authorization_totals = (
            self._prose_cited_id_partition()
        )
        beta_ids = cited_authorized_ids["beta_definition_ids"]
        beta_catalog = [self.catalog.inspect_beta(int(value)) for value in beta_ids]
        return {
            "query_id": self.state.query_id,
            "scope": self.state.scope,
            "requested_conditions": {
                "temperature_C": self.state.request_T_C,
                "ionic_strength_M": self.state.request_I_M,
            },
            "answer_turns": self.state.answer_turn_summaries(),
            "answer_precedence_rule": _ANSWER_PRECEDENCE_RULE,
            "latest_statements": self.latest_statements(),
            "prose_cited_authorized_ids": cited_authorized_ids,
            "prose_cited_unauthorized_ids": cited_unauthorized_ids,
            "evidence_rule": _EVIDENCE_RULE,
            "ungrounded_anchor_policy": {
                "rule": _UNGROUNDED_ANCHOR_RULE,
                "followup_budget": self.ungrounded_anchor_followup_budget,
                "followups_used": self.state.clarification_rounds_used,
            },
            "host_turn_budget": {
                "rule": _HOST_TURN_BUDGET_RULE,
                "host_turn_ceiling": self.host_turn_ceiling,
                "host_turns_used": max(0, len(self.state.answer_turns) - 1),
                "transcript_char_ceiling": self.transcript_char_ceiling,
                "transcript_chars": len(self.state.transcript),
            },
            "authorization_totals": authorization_totals,
            "canonical_beta_catalog": beta_catalog,
            "catalog_read_tools": list(_CATALOG_READ_TOOLS),
            "catalog_read_tools_rule": _CATALOG_READ_TOOLS_RULE,
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
                    "topology_species_mapping",
                    "statement_review",
                ],
                "topology_species_mapping_rule": _TOPOLOGY_SPECIES_MAPPING_RULE,
                "statement_review_rule": _STATEMENT_REVIEW_RULE,
                "statement_review_verdicts": list(_STATEMENT_REVIEW_VERDICTS),
                "host_copies_from_excerpts": _HOST_COPIES_RULE,
                "assumptions_rule": _ASSUMPTIONS_RULE,
                "optional_rows_rule": _OPTIONAL_ROWS_RULE,
                "source_excerpts": dict(_SOURCE_EXCERPT_CONTRACT),
                "excerpt_resolution_rule": EXCERPT_RESOLUTION_RULE,
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
            "glossary": dict(_GLOSSARY),
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
        details: dict[str, Any] = {}
        topology_excerpt = draft.source_excerpts.get("topology_excerpt")
        token_excerpt = draft.source_excerpts.get("beta_definition_excerpt")
        catalog_records: list[dict[str, Any]] | None = None

        def records() -> list[dict[str, Any]]:
            nonlocal catalog_records
            if catalog_records is None:
                catalog_records = list(
                    self.catalog.enumerate_materializable_betas().get("records")
                    or []
                )
            return catalog_records

        if topology_excerpt:
            try:
                resolution = resolve_canonical_topology(
                    topology_excerpt=str(topology_excerpt),
                    transcript=self.state.transcript,
                    scope=self.state.scope,
                    canonical_beta_records=records(),
                    authorization_context_id=self.state.query_id,
                    answer_sha256=self.state.transcript_sha256,
                    species_mapping=draft.topology_species_mapping,
                )
                resolved_id = int(resolution["beta_definition_id"])
                if (
                    draft.beta_definition_id is not None
                    and int(draft.beta_definition_id) != resolved_id
                ):
                    issues.append(_issue(
                        "topology_beta_mismatch",
                        GateOwner.PARSER,
                        f"the prose reaction resolves to beta_def_{resolved_id} "
                        f"`{resolution['equation_python']}`, not "
                        f"beta_def_{draft.beta_definition_id}; when repointing "
                        "topology_excerpt, patch beta_definition_id to null in "
                        "the same call",
                        draft_id,
                        details={
                            "stored_beta_definition_id": int(draft.beta_definition_id),
                            "reaction_resolved_beta": resolved_id,
                            "reaction_resolved_equation": str(
                                resolution["equation_python"]
                            ),
                            "retry_options": ["beta_definition_id"],
                        },
                    ))
                    draft.topology_resolution = None
                else:
                    # Host-owned derivation: the parser selected prose, not an ID.
                    draft.beta_definition_id = resolved_id
                    draft.topology_resolution = resolution
                    # Say what was resolved, so a wrong span is visible to the
                    # parser at the check rather than only at commit.
                    details["topology_resolution"] = {
                        "beta_definition_id": resolved_id,
                        "beta_definition_name": str(resolution["beta_definition_name"]),
                        "equation_python": str(resolution["equation_python"]),
                        "species_mapping": dict(
                            resolution.get("species_mapping") or {}
                        ),
                    }
                    overridden = self._written_labels_overridden(
                        draft=draft,
                        resolved_id=resolved_id,
                        resolved_name=str(resolution["beta_definition_name"]),
                        canonical_beta_records=records(),
                    )
                    if overridden:
                        details["topology_resolution"][
                            "written_labels_overridden"
                        ] = overridden
            except TopologyResolutionError as exc:
                draft.topology_resolution = None
                span = str(topology_excerpt)
                if (
                    _normalize_rendering(span)
                    not in _normalize_rendering(self.state.transcript)
                ):
                    # Traceability first: a span that is not the answer's text
                    # gets the nearest answer lines and no grammar advice;
                    # candidate and mapping hints apply only to traced spans.
                    nearest = _nearest_transcript_lines(
                        span, self.state.transcript, prefer_reaction=True,
                    )
                    issues.append(_issue(
                        "topology_resolution_failed",
                        GateOwner.PARSER,
                        str(exc) + _untraceable_span_hint(nearest, what="topology_excerpt"),
                        draft_id,
                        details={
                            "untraceable": True,
                            "excerpt_head": span[:160],
                            "nearest_transcript_lines": nearest,
                            "retry_options": ["topology_excerpt"],
                        },
                    ))
                else:
                    diagnosis = diagnose_topology_excerpt(
                        topology_excerpt=span,
                        scope=self.state.scope,
                        canonical_beta_records=records(),
                        species_mapping=draft.topology_species_mapping,
                    )
                    diagnosis["readable_reaction_rows"] = self._readable_reaction_rows()
                    issues.append(_issue(
                        "topology_resolution_failed",
                        GateOwner.PARSER,
                        str(exc) + _topology_failure_hint(diagnosis),
                        draft_id,
                        details=diagnosis,
                    ))
        else:
            draft.topology_resolution = None
            if token_excerpt and draft.beta_definition_id is not None:
                token_issues, token_details = self._cross_check_beta_token(
                    draft=draft,
                    excerpt=str(token_excerpt),
                    canonical_beta_records=records(),
                )
                issues.extend(token_issues)
                details.update(token_details)

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
                if field_name == "target_equilibrium_definition":
                    message = (
                        "no target equilibrium is resolved yet: supply "
                        "source_excerpts.topology_excerpt (the stated reaction; "
                        "the host resolves it, plus topology_species_mapping when "
                        "the notation needs it) or, on the legacy route, "
                        "beta_definition_id with a beta_definition_excerpt span "
                        "containing that beta_def token; this clears once "
                        "check_draft resolves the topology"
                    )
                elif field_name in {"estimation_method", "assumptions", "rationale"}:
                    message = (
                        f"{field_name} is required: send it, or send its excerpt "
                        "and the host copies the span"
                    )
                else:
                    message = f"{field_name} is required"
                issues.append(_issue(
                    f"missing_{field_name}",
                    self._owner_for_absent_topic(topic),
                    message,
                    draft_id,
                    topic,
                ))
        marker = self._optional_marker(draft)
        if marker is not None:
            details["answer_marked_optional"] = marker
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
            details=details,
        )
        self._record_report(report)
        return report

    def _readable_reaction_rows(self, limit: int = 3) -> list[dict[str, Any]]:
        """Answer rows whose reaction the host grammar already resolves (from the index).

        Offered with a grammar failure so the parser can bind one of them
        instead of respelling: each row with its beta id and the host's
        in-scope reading.
        """

        rows: list[dict[str, Any]] = []
        for entry in self.latest_statements().get("equilibria") or []:
            for statement in entry.get("statements") or []:
                if statement.get("route") != "topology":
                    continue
                rows.append({
                    "turn": statement.get("turn"),
                    "row": statement.get("row"),
                    "beta_definition_id": entry.get("beta_definition_id"),
                    "in_scope": statement.get("in_scope"),
                })
        rows.sort(key=lambda row: (row["in_scope"] is not True, -(row["turn"] or 0)))
        return rows[:limit]

    def _optional_marker(self, draft: EquilibriumDraft) -> dict[str, str] | None:
        """The answer's own optional/tentative marker on this draft's row.

        Looked for in the draft's binding spans and in the transcript line
        that holds the constant excerpt (table rows carry the marker in a
        notes column).  Reported, never enforced: the estimate is still
        extracted and the marker rides on the committed entry.
        """

        candidates: list[str] = [
            str(draft.source_excerpts.get(key) or "")
            for key in ("topology_excerpt", "constant_value_excerpt", "beta_definition_excerpt")
            if draft.source_excerpts.get(key)
        ]
        constant_excerpt = draft.source_excerpts.get("constant_value_excerpt")
        if constant_excerpt:
            candidates.extend(
                line for line in self.state.transcript.splitlines()
                if line.strip() and _source_contains(line, constant_excerpt)
            )
        for candidate in candidates:
            match = _OPTIONAL_MARKER_RE.search(_canonical_source_text(candidate))
            if match:
                return {
                    "marker": match.group(0),
                    "span": candidate.strip()[:240],
                }
        return None

    def request_conditions(self) -> dict[str, Any]:
        """The requested T, I and medium (SRD-46 scope: water) as a conditions dict."""

        return {
            "temperature_C": float(self.state.request_T_C),
            "ionic_strength_M": float(self.state.request_I_M),
            "medium": "water",
        }

    def _read_statement(self, span: str) -> dict[str, Any]:
        """What the host reads from a value row: metal ion, conditions, scope agreement.

        Shown to the parser as host-parsed; never used to block.
        """

        metal = _row_metal_species(span, self.state.scope)
        conditions = _row_conditions(span)
        agreement = _conditions_agree(conditions, self.request_conditions())
        in_scope: bool | None
        if metal["matches_scope"] is False or agreement is False:
            in_scope = False
        elif metal["matches_scope"] is None and agreement is None:
            in_scope = None
        else:
            in_scope = True
        return {
            "metal_species": metal,
            "conditions": conditions,
            "in_scope": in_scope,
        }

    def latest_statements(self) -> dict[str, Any]:
        """Host-parsed index of the answers' value rows (a reading aid, never a gate).

        Every answer turn is read in order (a continuation is the tail of the
        turn before it, so turn order is statement order).  A row that states
        an equilibrium - a reaction the host grammar resolves, else a
        ``beta_def_<id>`` token the answer wrote - together with a value
        statement is placed under its canonical beta id.  A beta id is a
        topology template shared by every metal ion and every condition, so
        each entry lists all its rows (``statements``) with what the host read
        from each: the bare metal ion as written and whether it is the scoped
        metal, the temperature / ionic strength / medium the row states, and
        ``in_scope``.  ``latest_in_scope`` is the host's suggestion of the row
        to bind; the parser confirms it against the text (``statement_review``)
        and the entry gate only reports disagreements
        (``other_value_statements``).  Reaction rows with a value the host
        cannot place (anchor systems outside the scope, notation needing a
        species mapping) are counted and sampled so the parser knows they
        exist.  Bare number sentences without a reaction or token are anchor
        prose and are not indexed.  Cached per transcript digest; every
        caller gets its own copy.
        """

        key = self.state.transcript_sha256
        cached = self._latest_statements_cache
        if cached is not None and cached[0] == key:
            return deepcopy(cached[1])
        records: list[dict[str, Any]] | None = None
        by_beta: dict[int, dict[str, Any]] = {}
        mentions: dict[int, dict[str, Any]] = {}
        unresolved: list[dict[str, Any]] = []
        unresolved_count = 0
        for turn_index, turn in enumerate(self.state.answer_turns, start=1):
            for raw_line in str(turn).splitlines():
                row = raw_line.strip()
                if not row:
                    continue
                canonical_row = _canonical_source_text(row)
                statements = list(_VALUE_STATEMENT_RE.finditer(canonical_row))
                if not statements:
                    continue
                token = _LATEST_BETA_TOKEN_RE.search(row)
                arrow = has_reaction_arrow(row)
                if not arrow and token is None:
                    continue
                beta_id: int | None = None
                route: str | None = None
                if arrow:
                    if records is None:
                        records = list(
                            self.catalog.enumerate_materializable_betas().get("records")
                            or []
                        )
                    try:
                        resolution = resolve_canonical_topology(
                            topology_excerpt=row,
                            transcript=self.state.transcript,
                            scope=self.state.scope,
                            canonical_beta_records=records,
                            authorization_context_id=self.state.query_id,
                            answer_sha256=key,
                            species_mapping={},
                        )
                    except (TopologyResolutionError, ValueError):
                        resolution = None
                    if resolution is not None:
                        beta_id = int(resolution["beta_definition_id"])
                        route = "topology"
                stated_values, stated_uncertainties = _stated_numbers(
                    canonical_row, statements,
                )
                optional = _OPTIONAL_MARKER_RE.search(canonical_row)
                entry = {
                    "turn": turn_index,
                    "row": row[:240],
                    "route": route,
                    "stated_values": stated_values,
                    "stated_uncertainties": stated_uncertainties,
                    "optional_marker": optional.group(0) if optional else None,
                }
                if arrow:
                    entry.update(self._read_statement(row))
                if beta_id is None and arrow:
                    # A stated reaction the host cannot place is never read
                    # as the token's equilibrium.
                    unresolved_count += 1
                    if len(unresolved) < _UNRESOLVED_VALUE_ROW_SAMPLE:
                        unresolved.append({
                            "turn": turn_index,
                            "row": row[:240],
                            "beta_tokens": sorted({
                                int(value) for value in _LATEST_BETA_TOKEN_RE.findall(row)
                            }),
                        })
                    continue
                if beta_id is None:
                    # A beta_def token beside a number without a reaction is
                    # a mention; it may cite an anchor rather than state the target.
                    mention_id = int(token.group(1))
                    entry["route"] = "token"
                    mention = mentions.setdefault(mention_id, {
                        "beta_definition_id": mention_id,
                        "latest": None,
                        "earlier": [],
                    })
                    if mention["latest"] is not None:
                        mention["earlier"].append(mention["latest"])
                    mention["latest"] = entry
                    continue
                slot = by_beta.setdefault(beta_id, {
                    "beta_definition_id": beta_id,
                    "statements": [],
                    "latest_in_scope": None,
                })
                slot["statements"].append(entry)
                if entry.get("in_scope") is not False:
                    # The host's suggestion only: the last row the host does
                    # not read as another ion or other conditions.
                    slot["latest_in_scope"] = entry
        result = {
            "rule": _LATEST_STATEMENTS_RULE,
            "host_parsed": True,
            "scope_metal": _scope_metal(self.state.scope),
            "request_conditions": self.request_conditions(),
            "equilibria": [by_beta[beta_id] for beta_id in sorted(by_beta)],
            "token_mentions": [mentions[beta_id] for beta_id in sorted(mentions)],
            "unresolved_value_rows": unresolved,
            "unresolved_value_row_count": unresolved_count,
        }
        self._latest_statements_cache = (key, deepcopy(result))
        return result

    def _row_states_equilibrium(
        self,
        *,
        row: str,
        draft: EquilibriumDraft,
        canonical_beta_records: list[dict[str, Any]],
    ) -> bool:
        """Whether a later-turn row restates the draft's equilibrium.

        A reaction-bound draft (topology route) is restated only by a row that
        states a reaction resolving to the same beta id; a bare beta_def token
        beside a number is a mention and may cite an anchor. The estimation
        prompt asks the agent to restate a corrected estimate complete, with
        its reaction. A token-bound draft (legacy route) is restated by a row
        carrying its token.
        """

        beta_id = int(draft.beta_definition_id)
        token_re = re.compile(rf"(?i)\bbeta_def_{beta_id}\b")
        if draft.topology_resolution is None:
            return token_re.search(row) is not None
        if not has_reaction_arrow(row):
            return False
        mappings: list[dict[str, str]] = []
        if draft.topology_species_mapping:
            mappings.append(dict(draft.topology_species_mapping))
        mappings.append({})
        for mapping in mappings:
            try:
                resolution = resolve_canonical_topology(
                    topology_excerpt=row,
                    transcript=self.state.transcript,
                    scope=self.state.scope,
                    canonical_beta_records=canonical_beta_records,
                    authorization_context_id=self.state.query_id,
                    answer_sha256=self.state.transcript_sha256,
                    species_mapping=mapping,
                )
            except (TopologyResolutionError, ValueError):
                continue
            return int(resolution["beta_definition_id"]) == beta_id
        return False

    def _bound_statement(self, draft: EquilibriumDraft) -> dict[str, Any] | None:
        """What the host reads from the span the draft's value is bound to.

        The constant excerpt carries the reaction (source excerpt contract),
        so the metal ion and any stated conditions are read from it, falling
        back to the topology excerpt for the ion.  Reported, never gated.
        """

        constant_excerpt = draft.source_excerpts.get("constant_value_excerpt")
        topology_excerpt = draft.source_excerpts.get("topology_excerpt")
        span = str(constant_excerpt or topology_excerpt or "")
        if not span:
            return None
        turns = self.state.answer_turns
        value_turn = next(
            (
                index for index in range(len(turns), 0, -1)
                if _source_contains(turns[index - 1], span)
            ),
            None,
        )
        reading = self._read_statement(span)
        if reading["metal_species"]["written"] is None and topology_excerpt:
            reading["metal_species"] = _row_metal_species(
                str(topology_excerpt), self.state.scope,
            )
        reading.update({
            "turn": value_turn,
            "row": span[:240],
            "stated_values": (
                [float(draft.constant_value)]
                if draft.constant_value is not None else []
            ),
            "stated_uncertainties": (
                [float(draft.uncertainty_log10)]
                if draft.uncertainty_log10 is not None else []
            ),
        })
        return reading

    def _other_value_statements(
        self,
        *,
        draft: EquilibriumDraft,
        bound: Mapping[str, Any] | None,
        canonical_beta_records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Later rows that state other numbers under the draft's equilibrium template.

        Reported to the parser (entry-gate details and the committed entry),
        never blocking: whether such a row is the same quantity restated
        later, another ion, other conditions or an anchor citation is a
        chemistry judgment the parser makes and records in
        ``statement_review``.  Each row carries what the host read from it
        (ion, conditions) and its ``relation`` to the bound row as the host
        sees it.  Rows the parser has already reviewed are left out.  A row
        repeating the bound numbers is a confirmation and is not listed.
        """

        turns = self.state.answer_turns
        if (
            len(turns) < 2
            or draft.constant_value is None
            or bound is None
            or bound.get("turn") is None
            or int(bound["turn"]) == len(turns)
        ):
            return []
        value_turn = int(bound["turn"])
        reviewed_rows = [
            str(item.get("row") or "")
            for item in (draft.statement_review or [])
            if isinstance(item, Mapping) and item.get("row")
        ]

        def present(numbers: list[float], expected: float) -> bool:
            return any(
                math.isclose(number, expected, rel_tol=0.0, abs_tol=1e-12)
                for number in numbers
            )

        rows: list[dict[str, Any]] = []
        for later_index in range(value_turn + 1, len(turns) + 1):
            for raw_line in turns[later_index - 1].splitlines():
                row = raw_line.strip()
                if not row:
                    continue
                canonical_row = _canonical_source_text(row)
                statements = list(_VALUE_STATEMENT_RE.finditer(canonical_row))
                if not statements:
                    continue
                if not self._row_states_equilibrium(
                    row=row, draft=draft, canonical_beta_records=canonical_beta_records,
                ):
                    continue
                numbers = [
                    float(match.group(0)) for match in _NUMBER_RE.finditer(canonical_row)
                ]
                # Compare the bound value with what the row STATES as the value
                # (the number closing each value statement) and the bound
                # uncertainty with what follows "±". For 0.5 ± 0.6 -> 0.8 ± 0.5,
                # the new uncertainty equals the old value, so a bare number
                # search would miss the change.
                stated_values, stated_uncertainties = _stated_numbers(
                    canonical_row, statements,
                )
                if not present(stated_values or numbers, float(draft.constant_value)):
                    differs_in = "constant_value"
                elif (
                    draft.uncertainty_log10 is not None
                    and ("±" in canonical_row or "uncertain" in canonical_row.lower())
                    and not present(
                        stated_uncertainties or numbers, float(draft.uncertainty_log10),
                    )
                ):
                    differs_in = "uncertainty_log10"
                else:
                    continue
                if any(_source_contains(row, reviewed) for reviewed in reviewed_rows):
                    continue
                reading = self._read_statement(row)
                relation = _statement_relation(
                    other_metal=reading["metal_species"],
                    other_conditions=reading["conditions"],
                    bound_conditions=bound.get("conditions") or {},
                    request_conditions=self.request_conditions(),
                )
                rows.append({
                    "turn": later_index,
                    "row": row[:240],
                    "differs_in": differs_in,
                    "stated_values": stated_values,
                    "stated_uncertainties": stated_uncertainties,
                    "row_numbers": numbers,
                    "metal_species": reading["metal_species"],
                    "conditions": reading["conditions"],
                    "in_scope": reading["in_scope"],
                    "relation": relation,
                })
                if len(rows) >= _OTHER_VALUE_STATEMENT_LIMIT:
                    return rows
        return rows

    def _statement_review_hint(
        self,
        *,
        draft: EquilibriumDraft,
        bound: Mapping[str, Any] | None,
        others: list[Mapping[str, Any]],
    ) -> str | None:
        """Refinement text that accompanies host-parsed statement readings (not a gate)."""

        parts: list[str] = []
        scoped = _scope_metal(self.state.scope)
        if bound is not None and bound["metal_species"].get("matches_scope") is False:
            parts.append(
                "The host reads the bound span's metal ion as "
                f"{bound['metal_species']['written']!r} (charge "
                f"{bound['metal_species']['charge']}) while the scoped metal is "
                f"{scoped['name']!r} (charge {scoped['charge']}). If the host is "
                "right this draft binds another ion's value: discard it or rebind "
                "to a row for the scoped ion. If the host misread the ion, record "
                "statement_review [{row: <this span's prefix>, verdict: "
                "'same_quantity_restated', corrected: {metal_species: <as "
                "written>}}] and the reading travels with the entry."
            )
        if others:
            same = [row for row in others if row["relation"] == "same_ion_same_conditions"]
            parts.append(
                f"{len(others)} later answer row(s) state other numbers under this "
                f"equilibrium template (beta_def_{draft.beta_definition_id}); the "
                "host attached the ion and conditions it parsed from each row and "
                "its relation to the bound row. This is information, not a gate: "
                "decide as a chemist. A row that is the same quantity for the "
                "same ion at the same conditions and later than the bound one is "
                "the one to bind (patch topology_excerpt, constant_value_excerpt, "
                "uncertainty_excerpt, constant_value and uncertainty_log10 to it, "
                "verdict same_quantity_later); another ion, other conditions, "
                "another equilibrium or an anchor citation is a different "
                "quantity (record that verdict). Reviewed rows leave this list."
            )
            if same:
                parts.append(
                    "Host reading: row(s) "
                    + ", ".join(f"turn {row['turn']}: {row['row'][:80]!r}" for row in same[:3])
                    + " look like the same ion at the same conditions."
                )
        return " ".join(parts) if parts else None

    def _ungrounded_anchor_vlm_ids(self, draft: EquilibriumDraft) -> list[int]:
        """VLMs the draft's reasoning spans name that no session tool showed."""

        _, unauthorized, _ = self._prose_cited_id_partition()
        unauthorized_vlms = set(unauthorized["vlm_ids"])
        if not unauthorized_vlms:
            return []
        spans = [
            str(draft.source_excerpts.get(key) or "")
            for key in ("estimation_method_excerpt", "evidence_excerpt", "rationale_excerpt")
        ]
        assumption_spans = draft.source_excerpts.get("assumption_excerpts")
        if isinstance(assumption_spans, list):
            spans.extend(str(span or "") for span in assumption_spans)
        written = {
            int(match.group(1))
            for match in _ANSWER_ID_PATTERNS["vlm_ids"].finditer("\n".join(spans))
        }
        return sorted(written & unauthorized_vlms)

    def _written_labels_overridden(
        self,
        *,
        draft: EquilibriumDraft,
        resolved_id: int,
        resolved_name: str,
        canonical_beta_records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Beta labels in the draft's spans that the stated reaction overrode.

        On the topology route the host binds the reaction, not the
        ``beta_def_<id>`` token or ``[ML]/[M][L]`` name the QueryAgent wrote
        beside it without the catalog.  A label naming another equilibrium is
        reported rather than enforced, so the parser sees that the answer's
        own label was wrong instead of the gate passing in silence.
        """

        text = "\n".join(
            str(draft.source_excerpts.get(key) or "")
            for key in ("topology_excerpt", "constant_value_excerpt", "uncertainty_excerpt")
            if draft.source_excerpts.get(key)
        )
        if not text:
            return []
        by_id: dict[int, dict[str, Any]] = {}
        for row in canonical_beta_records:
            try:
                by_id[int(row["beta_definition_id"])] = row
            except (KeyError, TypeError, ValueError):
                continue
        findings: list[dict[str, Any]] = []
        seen_tokens: set[int] = set()
        for match in _ANSWER_ID_PATTERNS["beta_definition_ids"].finditer(text):
            token = int(match.group(1))
            if token == resolved_id or token in seen_tokens:
                continue
            seen_tokens.add(token)
            row = by_id.get(token) or self.catalog.inspect_beta(token)
            findings.append({
                "written_token": f"beta_def_{token}",
                "catalog_name": str(row.get("beta_definition_name") or ""),
                "catalog_equation": str(row.get("equation_python") or ""),
                "catalog_status": str(row.get("status") or ""),
                "resolved_beta": resolved_id,
                "note": (
                    "label ignored; the stated reaction resolved to "
                    f"beta_def_{resolved_id}"
                ),
            })
        seen_names: set[str] = set()
        for name in written_beta_names(text):
            if name in seen_names or beta_names_equal(name, resolved_name):
                continue
            seen_names.add(name)
            findings.append({
                "written_name": name,
                "resolved_name": resolved_name,
                "resolved_beta": resolved_id,
                "note": (
                    "name ignored; the stated reaction resolved to "
                    f"beta_def_{resolved_id}"
                ),
            })
        return findings

    def _cross_check_beta_token(
        self,
        *,
        draft: EquilibriumDraft,
        excerpt: str,
        canonical_beta_records: list[dict[str, Any]],
    ) -> tuple[list[GateIssue], dict[str, Any]]:
        """Route (b): the answer binds the estimate to a literal beta_def token.

        The QueryAgent writes that token without seeing the catalog, so it is
        a label, not a derivation.  When the same span also states the
        reaction, or a catalog-style name, the host reads those and refuses a
        token that names a different equilibrium.  The stated reaction is the
        chemistry; the parser rebinds through ``topology_excerpt`` (plus
        ``topology_species_mapping`` when the notation needs it).  A name
        contradiction with no readable reaction is the answer's own
        inconsistency, which only the QueryAgent can settle.
        """

        issues: list[GateIssue] = []
        details: dict[str, Any] = {}
        beta_token = int(draft.beta_definition_id)
        written_tokens = {
            int(match.group(1))
            for match in _ANSWER_ID_PATTERNS["beta_definition_ids"].finditer(excerpt)
        }
        if beta_token not in written_tokens:
            # Source grounding reports the absent token with its own message.
            return issues, details
        catalog_row = self.catalog.inspect_beta(beta_token)
        catalog_name = str(catalog_row.get("beta_definition_name") or "")
        catalog_equation = str(catalog_row.get("equation_python") or "")
        check: dict[str, Any] = {
            "beta_token": beta_token,
            "beta_token_name": catalog_name,
            "beta_token_equation": catalog_equation,
        }

        reaction_beta: int | None = None
        reaction_equation = ""
        basis = ""
        suggested_mapping: dict[str, str] = {}
        if has_reaction_arrow(excerpt):
            try:
                resolution = resolve_canonical_topology(
                    topology_excerpt=excerpt,
                    transcript=self.state.transcript,
                    scope=self.state.scope,
                    canonical_beta_records=canonical_beta_records,
                    authorization_context_id=self.state.query_id,
                    answer_sha256=self.state.transcript_sha256,
                    species_mapping=draft.topology_species_mapping,
                )
                reaction_beta = int(resolution["beta_definition_id"])
                reaction_equation = str(resolution["equation_python"])
                basis = "host_grammar"
            except TopologyResolutionError:
                diagnosis = diagnose_topology_excerpt(
                    topology_excerpt=excerpt,
                    scope=self.state.scope,
                    canonical_beta_records=canonical_beta_records,
                    species_mapping=draft.topology_species_mapping,
                )
                suggested = diagnosis.get("suggested_resolution") or {}
                suggested_mapping = dict(
                    diagnosis.get("suggested_species_mapping") or {}
                )
                if suggested and suggested_mapping:
                    reaction_beta = int(suggested["beta_definition_id"])
                    reaction_equation = str(suggested["equation_python"])
                    basis = "implicit_solvent_suggestion"
        if reaction_beta is not None:
            check["reaction_resolved_beta"] = reaction_beta
            check["reaction_resolved_equation"] = reaction_equation
            check["basis"] = basis
            if suggested_mapping:
                check["suggested_species_mapping"] = suggested_mapping
            check["agrees"] = reaction_beta == beta_token

        written_names = written_beta_names(excerpt)
        if written_names and catalog_name and not any(
            beta_names_equal(name, catalog_name) for name in written_names
        ):
            written = written_names[0]
            if reaction_beta is not None:
                owner, topic = GateOwner.PARSER, ""
                remedy = (
                    "; the answer's label is unreliable — bind through the "
                    "reaction stated in the span (source_excerpts.topology_excerpt "
                    "with beta_definition_id null"
                    + (
                        ", plus topology_species_mapping "
                        + json.dumps(suggested_mapping, ensure_ascii=False)
                        if basis == "implicit_solvent_suggestion"
                        else ""
                    )
                    + ") instead of the token"
                )
            else:
                owner, topic = GateOwner.QUERY_AGENT, "target_equilibrium_definition"
                remedy = (
                    "; the answer's own label is inconsistent and the span states "
                    "no readable reaction, so which equilibrium is meant must "
                    "come from the QueryAgent"
                )
            issues.append(_issue(
                "beta_token_name_mismatch",
                owner,
                f"the span labels beta_def_{beta_token} as {written!r}, but the "
                f"catalog's beta_def_{beta_token} is {catalog_name!r} "
                f"`{catalog_equation}`" + remedy,
                draft.draft_id,
                topic,
                details={
                    "beta_token": beta_token,
                    "written_name": written,
                    "catalog_name": catalog_name,
                    "catalog_equation": catalog_equation,
                    "retry_options": (
                        ["topology_excerpt", "topology_species_mapping"]
                        if reaction_beta is not None else []
                    ),
                },
            ))

        if reaction_beta is not None and reaction_beta != beta_token:
            convention = (
                " under SRD-46's implicit-solvent convention (topology_species_mapping "
                + json.dumps(suggested_mapping, ensure_ascii=False) + ")"
                if basis == "implicit_solvent_suggestion" else ""
            )
            issues.append(_issue(
                "beta_token_contradicts_reaction",
                GateOwner.PARSER,
                f"the answer binds this estimate to beta_def_{beta_token} "
                f"`{catalog_equation}`, but the reaction stated in the same span "
                f"resolves to beta_def_{reaction_beta} `{reaction_equation}`"
                + convention
                + "; the stated reaction is the chemistry and the ID is a label "
                "the QueryAgent attached without the catalog — rebind through "
                "source_excerpts.topology_excerpt (that reaction span, "
                "beta_definition_id null"
                + (", plus the mapping above" if suggested_mapping else "")
                + "), or discard the draft if the answer's equilibrium cannot "
                "be determined",
                draft.draft_id,
                details={
                    "beta_token": beta_token,
                    "beta_token_equation": catalog_equation,
                    "reaction_resolved_beta": reaction_beta,
                    "reaction_resolved_equation": reaction_equation,
                    "basis": basis,
                    "suggested_species_mapping": suggested_mapping,
                    "retry_options": ["topology_excerpt", "topology_species_mapping"],
                },
            ))
        details["beta_token_check"] = check
        return issues, details

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
            binding_details = self._untraceable_excerpt_details(draft)
            issues.append(_issue(
                "source_binding_failed", GateOwner.PARSER,
                str(exc) + _untraceable_excerpts_hint(binding_details),
                draft_id,
                details=binding_details or None,
            ))
        bound_statement: dict[str, Any] | None = None
        other_statements: list[dict[str, Any]] = []
        if not issues:
            # Host-parsed reading of the bound row and of later rows under the
            # same template: reported for the parser's judgment, never gated.
            bound_statement = self._bound_statement(draft)
            other_statements = self._other_value_statements(
                draft=draft,
                bound=bound_statement,
                canonical_beta_records=list(
                    self.catalog.enumerate_materializable_betas().get("records") or []
                ),
            )

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
            if bound_statement is not None and (
                bound_statement["metal_species"].get("written") is not None
                or any(
                    value is not None
                    for value in bound_statement["conditions"].values()
                )
            ):
                canonical["bound_statement"] = deepcopy(bound_statement)
            if other_statements:
                canonical["other_value_statements"] = deepcopy(other_statements)
            if draft.statement_review:
                canonical["statement_review"] = deepcopy(draft.statement_review)
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
                evidence_details = dict(getattr(exc, "details", None) or {})
                if owner is GateOwner.QUERY_AGENT:
                    # The gate owner is the QueryAgent (it cited what it never
                    # saw), but the parser can usually repair the cite list
                    # itself; name the ids so it need not bisect them.
                    cited_authorized, _, _ = self._prose_cited_id_partition()
                    evidence_details["prose_cited_authorized_vlm_ids"] = (
                        cited_authorized["vlm_ids"]
                    )
                    evidence_details.setdefault(
                        "retry_options", ["evidence_vlm_ids", "evidence_excerpt"]
                    )
                    message += _evidence_failure_hint(evidence_details)
                issues.append(_issue(
                    "evidence_gate_failed", owner, message, draft_id,
                    "supporting_evidence" if owner is GateOwner.QUERY_AGENT else "",
                    details=evidence_details,
                ))
            evidence = self.catalog.inspect_evidence(draft.evidence_vlm_ids)
            if evidence.get("status") != "ok":
                unusable = [
                    {
                        "vlm_id": row.get("vlm_id"),
                        "status": row.get("status"),
                        "conflict_reason": row.get("conflict_reason"),
                    }
                    for row in (evidence.get("records") or [])
                    if isinstance(row, Mapping) and row.get("status") != "ok"
                ]
                named = ", ".join(
                    f"vlm_{row['vlm_id']} ({row['status']}"
                    + (f": {row['conflict_reason']}" if row.get("conflict_reason") else "")
                    + ")"
                    for row in unusable
                )
                issues.append(_issue(
                    "canonical_evidence_unavailable", GateOwner.QUERY_AGENT,
                    "one or more cited SRD-46 evidence records are unusable"
                    + (f": {named}" if named else "")
                    + "; drop them from evidence_vlm_ids and the evidence_excerpt, "
                    "or request_followup with topic supporting_evidence",
                    draft_id,
                    "supporting_evidence",
                    details={
                        "unusable_vlm_ids": [
                            int(row["vlm_id"]) for row in unusable
                            if row.get("vlm_id") is not None
                        ],
                        "unusable_records": unusable,
                        "retry_options": ["evidence_vlm_ids", "evidence_excerpt"],
                    },
                ))
        if not issues and canonical is not None:
            marker = self._optional_marker(draft)
            if marker is not None:
                canonical["answer_marked_optional"] = marker
            anchors = self._ungrounded_anchor_vlm_ids(draft)
            if anchors:
                used = self.state.clarification_rounds_used
                budget = self.ungrounded_anchor_followup_budget
                named = ", ".join(f"vlm_{value}" for value in anchors)
                if used < budget:
                    issues.append(_issue(
                        "ungrounded_anchor_evidence",
                        GateOwner.QUERY_AGENT,
                        f"the estimate's reasoning rests on {named} (named in the "
                        "draft's method/evidence/rationale spans), which the "
                        "QueryAgent cited without reading through a tool in this "
                        "session (prose_cited_unauthorized_ids); finish_parser_cycle"
                        "(request_followup, missing_topics_csv='supporting_evidence') "
                        f"so the QueryAgent grounds them (follow-up {used + 1} of "
                        f"{budget}); once the budget is spent the entry passes with "
                        "ungrounded_anchor_vlm_ids recorded on the committed entry",
                        draft_id,
                        "supporting_evidence",
                        details={
                            "ungrounded_anchor_vlm_ids": anchors,
                            "followups_used": used,
                            "followup_budget": budget,
                            "retry_options": ["request_followup"],
                        },
                    ))
                else:
                    canonical["ungrounded_anchor_vlm_ids"] = anchors
                    canonical["ungrounded_anchor_policy"] = (
                        f"committed on authorized evidence after {used} QueryAgent "
                        f"follow-up(s) (budget {budget}); {named} were cited by the "
                        "QueryAgent without a tool record in this session"
                    )
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
                "bound_statement": bound_statement,
                "other_value_statements": other_statements,
                "statement_review_hint": self._statement_review_hint(
                    draft=draft, bound=bound_statement, others=other_statements,
                ),
            },
        )
        self._record_report(report)
        return report

    def _untraceable_excerpt_details(self, draft: EquilibriumDraft) -> dict[str, Any]:
        """Which stored spans are not the answer's text, with the nearest answer lines.

        Attached to ``source_binding_failed`` so the parser can copy the row
        it meant instead of guessing at the spelling; ``retry_options`` names
        the failing keys.
        """

        transcript = self.state.transcript
        untraceable: dict[str, dict[str, Any]] = {}
        for key, value in draft.source_excerpts.items():
            spans: list[tuple[str, str]]
            if isinstance(value, str):
                spans = [(str(key), value)]
            elif isinstance(value, (list, tuple)):
                spans = [
                    (f"{key}[{index}]", str(item))
                    for index, item in enumerate(value)
                    if isinstance(item, str)
                ]
            else:
                continue
            for label, span in spans:
                if not span.strip() or _source_contains(transcript, span):
                    continue
                untraceable[label] = {
                    "excerpt_head": span[:160],
                    "nearest_transcript_lines": _nearest_transcript_lines(
                        span, transcript,
                        prefer_reaction=label.startswith("topology_excerpt"),
                    ),
                }
        if not untraceable:
            return {}
        return {
            "untraceable_excerpts": untraceable,
            "retry_options": sorted({
                label.split("[", 1)[0] for label in untraceable
            }),
        }

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
            # What the host stored, so the parser can see its call arrived
            # whole (its own earlier calls are shown abbreviated in the history).
            "stored": {
                "discussion_chars": len(discussion),
                "core_source_ids": list(core),
                "secondary_source_ids": list(secondary),
            },
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


__all__ = ["ParserGateService", "_UNGROUNDED_ANCHOR_FOLLOWUP_BUDGET"]
