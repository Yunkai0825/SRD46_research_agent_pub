"""Host-owned resolution of prose reactions to canonical SRD-46 beta topologies.

The QueryAgent is intentionally free to write ordinary chemistry prose.  It
does not own SRD-46 schema identifiers.  This module converts a *verbatim*
reaction excerpt selected by the downstream parser into a symbolic reaction
signature and matches that signature against the complete, read-only
canonical beta catalog.  Query-tool observations are evidence diagnostics;
they never restrict downstream schema assembly.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
import unicodedata
from typing import Any, Iterable, Mapping


TOPOLOGY_RESOLUTION_PROFILE = "lc1_3_host_topology_resolution/v2"


class TopologyResolutionError(ValueError):
    """Raised when prose topology cannot be resolved unambiguously."""


_ARROW_RE = re.compile(r"<=>|<->|⇌|↔|⇄|\s=\s")
_CANONICAL_SPECIES_RE = re.compile(r"\[([^\]]+)\](?:\^(\d+))?")
_SUBSCRIPT_TRANSLATION = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
_SUPERSCRIPT_TRANSLATION = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻", "0123456789+-")
_MARKDOWN_RE = re.compile(r"[`*_]")
_SUPERSCRIPT_CHARGE_RE = re.compile(r"([⁰¹²³⁴⁵⁶⁷⁸⁹]*[⁺⁻]+)")


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalize_rendering(value: Any) -> str:
    raw = str(value or "")
    # NFKC would collapse a superscript charge (Fe(EG)³⁺) into the same text
    # as a ligand subscript followed by a sign (Fe(EG)3+).  Preserve the
    # former explicitly before compatibility normalization.
    raw = _SUPERSCRIPT_CHARGE_RE.sub(
        lambda match: "^[" + match.group(1).translate(
            _SUPERSCRIPT_TRANSLATION
        ) + "]",
        raw,
    )
    text = unicodedata.normalize("NFKC", raw)
    text = text.translate(_SUBSCRIPT_TRANSLATION).translate(_SUPERSCRIPT_TRANSLATION)
    text = re.sub(r"(?is)<sub>\s*([^<]+?)\s*</sub>", r"\1", text)
    text = re.sub(r"(?is)<sup>\s*([^<]+?)\s*</sup>", r"^\1", text)
    text = _MARKDOWN_RE.sub("", text)
    return " ".join(text.split())


def _extract_reaction(excerpt: str) -> str:
    text = _normalize_rendering(excerpt)
    if not _ARROW_RE.search(text):
        raise TopologyResolutionError("topology excerpt contains no reaction arrow")

    # Markdown tables are the common case.  Select the one cell containing the
    # arrow so neighbouring values cannot be mistaken for stoichiometry.
    cells = [cell.strip() for cell in text.split("|") if cell.strip()]
    reaction_cells = [cell for cell in cells if _ARROW_RE.search(cell)]
    if len(reaction_cells) == 1:
        return reaction_cells[0]

    # Otherwise retain the smallest semicolon/newline-delimited clause with
    # exactly one arrow.
    clauses = [
        clause.strip(" .;:")
        for clause in re.split(r"[\r\n;]", text)
        if _ARROW_RE.search(clause)
    ]
    if len(clauses) == 1:
        return clauses[0]
    raise TopologyResolutionError(
        "topology excerpt must identify exactly one reaction"
    )


def _split_reaction(reaction: str) -> tuple[str, str]:
    parts = _ARROW_RE.split(reaction, maxsplit=1)
    if len(parts) != 2 or not all(part.strip() for part in parts):
        raise TopologyResolutionError("reaction must have nonempty left and right sides")
    return parts[0].strip(), parts[1].strip()


def _strip_charge(species: str) -> str:
    text = species.strip()
    # Remove a phase tag first so charges immediately before ``(aq)`` remain
    # visible to the charge grammar.
    text = re.sub(r"\((?:aq|l|g)\)$", "", text, flags=re.I).strip()
    # Explicit caret/bracket charge forms used throughout QueryAgent prose:
    # Fe^[3+], Fe^3+, Fe(EG)2^[2+].
    text = re.sub(r"\^\[?\d*[+-]\]?$", "", text)
    text = re.sub(r"\^\{?\d*[+-]\}?$", "", text)
    # One or several trailing signs are charge.  Do not remove a preceding
    # digit here because it can be ligand stoichiometry in Fe(EG)2+.
    text = re.sub(r"[+-]+$", "", text)
    return text.strip()


def _side_terms(side: str) -> list[tuple[str, int]]:
    # Charge signs are not surrounded by whitespace in the supported prose
    # grammar, while reaction addition signs are.
    raw_terms = re.split(r"\s+\+\s+", side.strip())
    terms: list[tuple[str, int]] = []
    for raw in raw_terms:
        term = raw.strip(" `")
        coefficient = 1
        match = re.match(r"^(\d+)\s+(.+)$", term)
        if match:
            coefficient = int(match.group(1))
            term = match.group(2).strip()
        if not term:
            raise TopologyResolutionError("reaction contains an empty species")
        terms.append((term, coefficient))
    return terms


def _metal_symbol(scope: Mapping[str, Any]) -> str:
    name = _normalize_rendering(scope.get("metal_name") or "")
    match = re.search(r"\b([A-Z][a-z]?)\b", name)
    if match is None:
        raise TopologyResolutionError("scoped metal name has no chemical symbol")
    return match.group(1)


def _is_metal_species(species: str, metal: str) -> bool:
    rendered = _normalize_rendering(species)
    rendered = re.sub(r"\((?:aq|l|g)\)$", "", rendered, flags=re.I).strip()
    # For a bare element only, a digit immediately before the final sign is an
    # oxidation-state charge (Fe3+).  The equivalent digit in a complex such as
    # Fe(EG)2+ is ligand stoichiometry and is intentionally preserved.
    bare_ion = re.fullmatch(
        rf"{re.escape(metal)}(?:\^?(?:\[?\d*[+-]+\]?|\{{?\d*[+-]+\}}?))?",
        rendered,
        flags=re.I,
    )
    if bare_ion is not None:
        return True
    return re.fullmatch(
        re.escape(metal), _strip_charge(rendered), flags=re.I
    ) is not None


def _infer_ligand_alias(
    lhs: list[tuple[str, int]], *, metal: str, scope: Mapping[str, Any]
) -> str:
    candidates = [
        species
        for species, _ in lhs
        if not _is_metal_species(species, metal)
        and not re.search(rf"(?i)\b{re.escape(metal)}\b", species)
        and _strip_charge(species).upper() not in {
            "H", "H2O", "OH", "E", "E-"
        }
    ]
    if len(candidates) == 1:
        return candidates[0]

    ligand_name = _normalize_rendering(scope.get("ligand_name") or "")
    parenthetical = re.findall(r"\(([^()]+)\)", ligand_name)
    names = parenthetical + [re.sub(r"\([^()]+\)", "", ligand_name).strip()]
    aliases = {
        "".join(word[0] for word in re.findall(r"[A-Za-z]+", name)).upper()
        for name in names
        if name
    }
    for species in candidates:
        compact = re.sub(r"[^A-Za-z0-9]", "", species).upper()
        if compact in aliases:
            return species
    raise TopologyResolutionError(
        "cannot infer one free-ligand species from the reaction left side"
    )


def _abstract_species(species: str, *, metal: str, ligand: str) -> str:
    if _is_metal_species(species, metal):
        return "M"
    token = _strip_charge(species)
    if token.casefold() == ligand.casefold():
        return "L"

    # Replace only the scoped identities.  This preserves H/OH/H2O and other
    # topology-bearing tokens rather than guessing chemistry from evidence IDs.
    token = re.sub(re.escape(metal), "M", token, flags=re.I)
    token = re.sub(re.escape(ligand), "L", token, flags=re.I)
    token = token.replace(" ", "")
    token = re.sub(r"^M\(L\)(\d*)$", lambda m: "ML" + (m.group(1) or ""), token)
    token = re.sub(r"^M\[L\](\d*)$", lambda m: "ML" + (m.group(1) or ""), token)
    if "M" not in token and "L" not in token:
        # Canonical water/proton/electron species may occur unchanged.
        if token in {"H", "H2O", "OH", "e", "e-"}:
            return token
        raise TopologyResolutionError(f"unrecognized reaction species {species!r}")
    return token


def prose_reaction_signature(
    excerpt: str, scope: Mapping[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    """Return an orientation-preserving symbolic signature from prose."""

    reaction = _extract_reaction(excerpt)
    lhs_text, rhs_text = _split_reaction(reaction)
    lhs = _side_terms(lhs_text)
    rhs = _side_terms(rhs_text)
    metal = _metal_symbol(scope)
    ligand = _infer_ligand_alias(lhs, metal=metal, scope=scope)

    def convert(terms: list[tuple[str, int]]) -> list[dict[str, Any]]:
        rows = [
            {
                "species": _abstract_species(species, metal=metal, ligand=ligand),
                "power": int(power),
            }
            for species, power in terms
        ]
        return sorted(rows, key=lambda row: (row["species"], row["power"]))

    return {"lhs": convert(lhs), "rhs": convert(rhs)}


def canonical_equation_signature(
    equation_python: str,
) -> dict[str, list[dict[str, Any]]]:
    """Return the same signature shape for a canonical SRD-46 equation."""

    parts = str(equation_python or "").split("<=>", maxsplit=1)
    if len(parts) != 2:
        raise TopologyResolutionError("canonical equation has no <=> arrow")

    def parse(side: str) -> list[dict[str, Any]]:
        rows = [
            {"species": match.group(1), "power": int(match.group(2) or 1)}
            for match in _CANONICAL_SPECIES_RE.finditer(side)
        ]
        if not rows:
            raise TopologyResolutionError("canonical equation side has no species")
        return sorted(rows, key=lambda row: (row["species"], row["power"]))

    return {"lhs": parse(parts[0]), "rhs": parse(parts[1])}


def resolve_canonical_topology(
    *,
    topology_excerpt: str,
    transcript: str,
    scope: Mapping[str, Any],
    canonical_beta_records: Iterable[Mapping[str, Any]],
    authorization_context_id: str,
    answer_sha256: str,
) -> dict[str, Any]:
    """Resolve one source reaction to exactly one canonical beta topology.

    ``canonical_beta_records`` must come from the host's read-only catalog
    enumeration.  In particular, this function deliberately has no argument
    for QueryAgent-observed or prose-cited beta IDs.
    """

    excerpt = str(topology_excerpt or "").strip()
    if not excerpt:
        raise TopologyResolutionError("topology excerpt is missing")
    normalized_excerpt = _normalize_rendering(excerpt)
    if normalized_excerpt not in _normalize_rendering(transcript):
        raise TopologyResolutionError(
            "topology excerpt is not traceable to one contiguous answer span"
        )
    query_signature = prose_reaction_signature(excerpt, scope)
    catalog_identities: dict[int, set[tuple[str, str]]] = {}
    usable_records: dict[tuple[int, str, str], Mapping[str, Any]] = {}
    for raw_beta in canonical_beta_records:
        beta = dict(raw_beta or {})
        if beta.get("status") != "ok" or not beta.get("materializable", True):
            continue
        try:
            beta_id = int(beta["beta_definition_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise TopologyResolutionError(
                "canonical beta catalog contains an invalid beta ID"
            ) from exc
        if beta_id <= 0:
            raise TopologyResolutionError(
                "canonical beta catalog contains a nonpositive beta ID"
            )
        beta_name = str(beta.get("beta_definition_name") or "").strip()
        equation = str(beta.get("equation_python") or "").strip()
        if not beta_name or not equation or equation == "*":
            continue
        identity = (beta_name, equation)
        catalog_identities.setdefault(beta_id, set()).add(identity)
        usable_records[(beta_id, beta_name, equation)] = beta

    conflicting_ids = sorted(
        beta_id
        for beta_id, identities in catalog_identities.items()
        if len(identities) != 1
    )
    if conflicting_ids:
        raise TopologyResolutionError(
            "canonical beta catalog contains conflicting identities for: "
            + ", ".join(f"beta_def_{value}" for value in conflicting_ids)
        )

    matches: list[Mapping[str, Any]] = []
    for identity in sorted(usable_records):
        beta = usable_records[identity]
        try:
            signature = canonical_equation_signature(str(beta["equation_python"]))
        except TopologyResolutionError:
            continue
        if signature == query_signature:
            matches.append(beta)
    if not matches:
        raise TopologyResolutionError(
            "no materializable canonical beta definition matches the prose reaction"
        )
    identities = {
        (
            int(row["beta_definition_id"]),
            str(row["beta_definition_name"]),
            str(row["equation_python"]),
        )
        for row in matches
    }
    if len(identities) != 1:
        raise TopologyResolutionError(
            "more than one canonical beta definition matches the prose reaction: "
            + ", ".join(f"beta_def_{row[0]}" for row in sorted(identities))
        )
    beta_id, beta_name, equation = next(iter(identities))
    payload = {
        "profile": TOPOLOGY_RESOLUTION_PROFILE,
        "authorization_context_id": str(authorization_context_id),
        "answer_sha256": str(answer_sha256),
        "topology_excerpt": excerpt,
        "topology_excerpt_sha256": hashlib.sha256(
            normalized_excerpt.encode("utf-8")
        ).hexdigest(),
        "query_signature": query_signature,
        "beta_definition_id": beta_id,
        "beta_definition_name": beta_name,
        "equation_python": equation,
        "canonical_signature": canonical_equation_signature(equation),
        "canonical_catalog_materializable_count": len(usable_records),
        "canonical_catalog_sha256": _sha256([
            {
                "beta_definition_id": beta_id,
                "beta_definition_name": beta_name,
                "equation_python": canonical_equation,
            }
            for beta_id, beta_name, canonical_equation in sorted(usable_records)
        ]),
    }
    payload["receipt_sha256"] = _sha256(payload)
    return payload


def closest_canonical_candidates(
    *,
    topology_excerpt: str,
    scope: Mapping[str, Any],
    canonical_beta_records: Iterable[Mapping[str, Any]],
    limit: int = 5,
) -> list[str]:
    """Score materializable beta definitions against a failed prose excerpt.

    Diagnostic only: the returned strings never resolve a draft. Signature
    similarity (when the prose reaction parses) outranks plain text
    similarity, and whitespace inside species tokens is never altered.
    """

    usable: list[tuple[int, str, str]] = []
    for raw_beta in canonical_beta_records or []:
        beta = dict(raw_beta or {})
        if beta.get("status") != "ok" or not beta.get("materializable", True):
            continue
        try:
            beta_id = int(beta["beta_definition_id"])
        except (KeyError, TypeError, ValueError):
            continue
        beta_name = str(beta.get("beta_definition_name") or "").strip()
        equation = str(beta.get("equation_python") or "").strip()
        if beta_id > 0 and beta_name and equation and equation != "*":
            usable.append((beta_id, beta_name, equation))
    if not usable:
        return []

    query_signature: dict[str, list[dict[str, Any]]] | None = None
    try:
        query_signature = prose_reaction_signature(
            str(topology_excerpt or ""), scope
        )
    except TopologyResolutionError:
        query_signature = None

    normalized_excerpt = _normalize_rendering(str(topology_excerpt or ""))

    def _signature_rows(sig: Mapping[str, Any]) -> set[tuple[str, str, int]]:
        rows: set[tuple[str, str, int]] = set()
        for side in ("lhs", "rhs"):
            for row in sig.get(side) or []:
                rows.add((side, str(row["species"]), int(row["power"])))
        return rows

    scored: list[tuple[float, int, str, str]] = []
    query_rows = (
        _signature_rows(query_signature) if query_signature is not None else None
    )
    for beta_id, beta_name, equation in sorted(set(usable)):
        score = 0.0
        if query_rows is not None:
            try:
                canonical_rows = _signature_rows(
                    canonical_equation_signature(equation)
                )
            except TopologyResolutionError:
                canonical_rows = set()
            union = query_rows | canonical_rows
            if union:
                score = len(query_rows & canonical_rows) / len(union)
        else:
            score = difflib.SequenceMatcher(
                None, normalized_excerpt, _normalize_rendering(equation)
            ).ratio()
        scored.append((score, beta_id, beta_name, equation))

    scored.sort(key=lambda row: (-row[0], row[1]))
    return [
        f"beta_def_{beta_id} `{equation}` ({beta_name}; score {score:.2f})"
        for score, beta_id, beta_name, equation in scored[:limit]
    ]


def validate_topology_resolution_receipt(
    receipt: Mapping[str, Any],
    *,
    beta_definition_id: int,
    beta_definition_name: str,
    equation_python: str,
    query_id: str,
    answer_sha256: str,
) -> dict[str, Any]:
    """Revalidate a persisted host topology receipt without source transcript."""

    value = dict(receipt or {})
    claimed = str(value.pop("receipt_sha256", ""))
    if value.get("profile") != TOPOLOGY_RESOLUTION_PROFILE:
        raise TopologyResolutionError("topology resolution profile is invalid")
    if claimed != _sha256(value):
        raise TopologyResolutionError("topology resolution receipt digest is invalid")
    if value.get("authorization_context_id") != str(query_id):
        raise TopologyResolutionError("topology resolution query context changed")
    if value.get("answer_sha256") != str(answer_sha256):
        raise TopologyResolutionError("topology resolution answer digest changed")
    if int(value.get("beta_definition_id", 0)) != int(beta_definition_id):
        raise TopologyResolutionError("topology resolution beta ID changed")
    if value.get("beta_definition_name") != str(beta_definition_name):
        raise TopologyResolutionError("topology resolution beta name changed")
    if value.get("equation_python") != str(equation_python):
        raise TopologyResolutionError("topology resolution equation changed")
    if value.get("canonical_signature") != canonical_equation_signature(
        equation_python
    ):
        raise TopologyResolutionError("topology resolution signature changed")
    excerpt = str(value.get("topology_excerpt") or "")
    if hashlib.sha256(_normalize_rendering(excerpt).encode("utf-8")).hexdigest() != value.get(
        "topology_excerpt_sha256"
    ):
        raise TopologyResolutionError("topology resolution excerpt digest changed")
    if value.get("query_signature") != value.get("canonical_signature"):
        raise TopologyResolutionError("prose and canonical topology signatures differ")
    return {**value, "receipt_sha256": claimed}


__all__ = [
    "TOPOLOGY_RESOLUTION_PROFILE",
    "TopologyResolutionError",
    "canonical_equation_signature",
    "prose_reaction_signature",
    "resolve_canonical_topology",
    "validate_topology_resolution_receipt",
]
