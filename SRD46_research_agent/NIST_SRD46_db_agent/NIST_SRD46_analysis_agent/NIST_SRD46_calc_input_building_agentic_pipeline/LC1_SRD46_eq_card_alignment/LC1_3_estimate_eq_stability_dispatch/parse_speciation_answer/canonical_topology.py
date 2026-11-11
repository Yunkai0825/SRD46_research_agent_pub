"""Host-owned resolution of prose reactions to canonical SRD-46 beta topologies.

The QueryAgent is intentionally free to write ordinary chemistry prose.  It
does not own SRD-46 schema identifiers.  This module converts a *verbatim*
reaction excerpt selected by the downstream parser into a symbolic reaction
signature and matches that signature against the complete, read-only
canonical beta catalog.  Query-tool observations are evidence diagnostics;
they never restrict downstream schema assembly.

The parser may additionally state, per written species, which canonical
SRD-46 species it is (``species_mapping``).  That statement is a labelled
reading of the chemist's notation, not a schema selection: the host checks
every entry against the reaction span and the catalog vocabulary, records it
in the tamper-evident receipt, and still derives the beta ID itself by
signature matching.  When resolution fails, :func:`diagnose_topology_excerpt`
reports what the grammar read, which written species it could not place, the
closest catalog topologies, and (under SRD-46's implicit-solvent convention)
a suggested mapping the parser may confirm or reject.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
import unicodedata
from typing import Any, Iterable, Mapping


TOPOLOGY_RESOLUTION_PROFILE = "lc1_3_host_topology_resolution/v2"

# The only mapping value that is not a canonical species: it drops a written
# solvent-water term that SRD-46 leaves implicit (aqua exchange reactions).
SOLVENT_MAPPING_TOKEN = "(solvent)"
_WATER_TOKENS = {"H2O", "OH2", "WATER"}
_LIGHT_SPECIES = {"H", "H2O", "OH", "e", "e-"}
_METAL_TOKEN_RE = re.compile(r"(?<![A-Za-z])M(?![a-z])")
_AQUA_LIGAND_RE = re.compile(r"\(H2O\)\d*(?:\.\d+)?")
_PARENTHESISED_L_RE = re.compile(r"\(L\)(\d*)")
_RETRY_OPTIONS = (
    "topology_excerpt",
    "beta_definition_excerpt",
    "topology_species_mapping",
)


class TopologyResolutionError(ValueError):
    """Raised when prose topology cannot be resolved unambiguously."""


_ARROW_RE = re.compile(r"<=>|<->|⇌|↔|⇄|\s=\s")
# Explicit equilibrium arrows.  A bare `` = `` is accepted as a last resort
# only, because answer rows also write ``log K = 1.6`` next to the reaction.
_STRONG_ARROW_RE = re.compile(r"<=>|<->|⇌|↔|⇄")
# A catalog-style beta definition name written in prose: bracketed species
# (optionally powered) over bracketed species, e.g. ``[ML2]/[M][L]^2`` or
# ``[M(OH)L][H]/[M][L]``.
_BETA_NAME_RE = re.compile(
    r"(?:\[[^\[\]\s]+\](?:\^?\d+(?:\.\d+)?)?)+\s*/\s*"
    r"(?:\[[^\[\]\s]+\](?:\^?\d+(?:\.\d+)?)?)+"
)
# A canonical power is ``^N`` or a decimal ``^N.M`` (``[OH]^1.5`` in the
# half-formula-unit solids SRD-46 writes).
_CANONICAL_SPECIES_RE = re.compile(r"\[([^\]]+)\](?:\^(\d+(?:\.\d+)?))?")
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
    reaction_cells = (
        [cell for cell in cells if _STRONG_ARROW_RE.search(cell)]
        or [cell for cell in cells if _ARROW_RE.search(cell)]
    )
    if len(reaction_cells) == 1:
        return reaction_cells[0]

    # Otherwise retain the smallest semicolon/newline-delimited clause with
    # exactly one arrow.
    pieces = re.split(r"[\r\n;]", text)
    clauses = [
        clause.strip(" .;:")
        for clause in pieces
        if _STRONG_ARROW_RE.search(clause)
    ] or [
        clause.strip(" .;:")
        for clause in pieces
        if _ARROW_RE.search(clause)
    ]
    if len(clauses) == 1:
        return clauses[0]
    raise TopologyResolutionError(
        "topology excerpt must identify exactly one reaction"
    )


def _split_reaction(reaction: str) -> tuple[str, str]:
    arrow = _STRONG_ARROW_RE if _STRONG_ARROW_RE.search(reaction) else _ARROW_RE
    parts = arrow.split(reaction, maxsplit=1)
    if len(parts) != 2 or not all(part.strip() for part in parts):
        raise TopologyResolutionError("reaction must have nonempty left and right sides")
    return parts[0].strip(), parts[1].strip()


def has_reaction_arrow(text: str) -> bool:
    """True when the span writes a reaction with an explicit equilibrium arrow."""

    return _STRONG_ARROW_RE.search(_normalize_rendering(text)) is not None


def written_beta_names(text: str) -> list[str]:
    """Catalog-style beta names (``[ML]/[M][L]``, ``[ML2]/[M][L]^2``) in a span."""

    normalized = _normalize_rendering(text)
    return [
        re.sub(r"\s+", "", match.group(0))
        for match in _BETA_NAME_RE.finditer(normalized)
    ]


def _beta_name_key(value: str) -> str:
    # Rendering differences that do not change the definition: whitespace,
    # sub/superscript markup, and the caret of a power ([L]^2 vs [L]²).
    return re.sub(r"[\s^]", "", _normalize_rendering(value)).casefold()


def beta_names_equal(written: str, catalog_name: str) -> bool:
    """Compare a prose beta name with a catalog name up to rendering."""

    return _beta_name_key(written) == _beta_name_key(catalog_name)


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


# A species is one whitespace-free token.  Whatever follows it after
# whitespace, wrapped in parentheses, is a chemist's note on the reaction
# ("H⁺ (mono-glycolato / alkoxide)"), not part of the species: left glued to
# the last term it makes that term unmatchable, so neither the grammar nor a
# parser-stated species mapping keyed by the written species can reach it.
_TRAILING_NOTE_RE = re.compile(r"^(\S+)\s+\((?P<note>.*)\)$", re.DOTALL)


def _detach_trailing_note(term: str) -> str:
    match = _TRAILING_NOTE_RE.match(term.strip())
    return match.group(1) if match else term


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
        term = _detach_trailing_note(term)
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


def _strip_coordination_wrapper(species: str) -> str:
    """Remove one balanced square-bracket pair enclosing the whole species."""
    if not species.startswith("["):
        return species
    depth = 0
    for index, character in enumerate(species):
        if character == "[":
            depth += 1
        elif character == "]":
            depth -= 1
            if depth == 0:
                return species[1:-1].strip() if index == len(species) - 1 else species
    return species


def _abstract_species(species: str, *, metal: str, ligand: str) -> str:
    if _is_metal_species(species, metal):
        return "M"
    token = _strip_charge(species)
    if token.casefold() == ligand.casefold():
        return "L"

    token = _strip_coordination_wrapper(token)

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


# --------------------------------------------------------------------------
# Parser-stated species mapping (notation the host grammar does not read)
# --------------------------------------------------------------------------


def _term_key(term: str) -> str:
    """Comparison key shared by reaction terms and mapping keys."""
    return _normalize_rendering(term).strip(" `")


def _clean_species_mapping(species_mapping: Any) -> dict[str, str]:
    """Return the mapping as written (stripped), rejecting malformed entries."""

    if not species_mapping:
        return {}
    if not isinstance(species_mapping, Mapping):
        raise TopologyResolutionError(
            "species mapping must be an object of written species -> "
            "canonical SRD-46 species token"
        )
    cleaned: dict[str, str] = {}
    for raw_key, raw_value in species_mapping.items():
        key = str(raw_key or "").strip()
        value = str(raw_value or "").strip()
        if not key or not value:
            raise TopologyResolutionError(
                "species mapping keys and values must be non-empty strings"
            )
        cleaned[key] = value
    return cleaned


def _mapping_lookup(cleaned: Mapping[str, str]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for raw_key, value in cleaned.items():
        key = _term_key(raw_key)
        if key in lookup and lookup[key] != value:
            raise TopologyResolutionError(
                f"species mapping lists {raw_key!r} twice with different tokens"
            )
        lookup[key] = value
    return lookup


def _is_water_term(term: str) -> bool:
    compact = re.sub(r"\s+", "", _strip_charge(_term_key(term))).upper()
    return compact in _WATER_TOKENS


def _validate_mapping_against_reaction(
    cleaned: Mapping[str, str],
    *,
    terms: list[tuple[str, int]],
    reaction: str,
    metal: str,
) -> None:
    present = {_term_key(species) for species, _ in terms}
    for raw_key, value in cleaned.items():
        key = _term_key(raw_key)
        if key not in present:
            raise TopologyResolutionError(
                f"species mapping key {raw_key!r} does not occur as one "
                f"species of the reaction {reaction!r}; keys must be the "
                "written species exactly as they appear in topology_excerpt, "
                "without coefficients"
            )
        if value == SOLVENT_MAPPING_TOKEN:
            if not _is_water_term(key):
                raise TopologyResolutionError(
                    f"species mapping may use {SOLVENT_MAPPING_TOKEN!r} only "
                    f"for solvent water, not for {raw_key!r}"
                )
            continue
        bare_metal = _is_metal_species(key, metal)
        if bare_metal and value != "M":
            raise TopologyResolutionError(
                f"species mapping may not relabel the scoped metal ion "
                f"{raw_key!r} as {value!r}; the bare scoped metal is always M"
            )
        if (
            _METAL_TOKEN_RE.search(value)
            and not bare_metal
            and not re.search(rf"(?i)\b{re.escape(metal)}\b", key)
        ):
            raise TopologyResolutionError(
                f"species mapping assigns the metal-containing token "
                f"{value!r} to {raw_key!r}, which does not contain the "
                f"scoped metal {metal}"
            )


def canonical_species_vocabulary(
    canonical_beta_records: Iterable[Mapping[str, Any]],
) -> dict[str, int]:
    """Map each canonical species token to the number of usable equations using it."""

    counts: dict[str, int] = {}
    for raw_beta in canonical_beta_records or []:
        beta = dict(raw_beta or {})
        if beta.get("status") != "ok" or not beta.get("materializable", True):
            continue
        equation = str(beta.get("equation_python") or "").strip()
        if not equation or equation == "*":
            continue
        for match in _CANONICAL_SPECIES_RE.finditer(equation):
            token = match.group(1)
            counts[token] = counts.get(token, 0) + 1
    return counts


def _vocabulary_hint(vocabulary: Mapping[str, int], *, limit: int = 24) -> str:
    if not vocabulary:
        return "the materializable catalog is empty"
    ranked = sorted(vocabulary.items(), key=lambda item: (-item[1], item[0]))
    shown = ", ".join(token for token, _ in ranked[:limit])
    more = len(ranked) - min(limit, len(ranked))
    suffix = f" (+{more} more; search_canonical_betas lists them)" if more > 0 else ""
    return (
        "canonical species tokens are written with M (scoped metal), L "
        "(scoped ligand), H, OH, H2O, e only; most frequent in the catalog: "
        + shown + suffix
    )


def _validate_mapping_vocabulary(
    cleaned: Mapping[str, str], vocabulary: Mapping[str, int]
) -> None:
    for raw_key, value in cleaned.items():
        if value == SOLVENT_MAPPING_TOKEN or value in vocabulary:
            continue
        raise TopologyResolutionError(
            f"species mapping value {value!r} (for {raw_key!r}) is not a "
            "canonical SRD-46 species token of the materializable catalog; "
            + _vocabulary_hint(vocabulary, limit=12)
        )


def prose_reaction_signature(
    excerpt: str,
    scope: Mapping[str, Any],
    species_mapping: Mapping[str, str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Return an orientation-preserving symbolic signature from prose.

    ``species_mapping`` (optional) maps written species, exactly as they
    appear in the excerpt, to canonical SRD-46 species tokens; mapped terms
    bypass the host grammar, ``(solvent)`` drops a written water term, and
    every unmapped term is still read by the grammar.  Vocabulary membership
    is checked by :func:`resolve_canonical_topology`, which has the catalog.
    """

    reaction = _extract_reaction(excerpt)
    lhs_text, rhs_text = _split_reaction(reaction)
    lhs = _side_terms(lhs_text)
    rhs = _side_terms(rhs_text)
    metal = _metal_symbol(scope)
    cleaned = _clean_species_mapping(species_mapping)
    lookup = _mapping_lookup(cleaned)
    if cleaned:
        _validate_mapping_against_reaction(
            cleaned, terms=lhs + rhs, reaction=reaction, metal=metal
        )

    unmapped_lhs = [(s, p) for s, p in lhs if _term_key(s) not in lookup]
    unmapped_rhs = [(s, p) for s, p in rhs if _term_key(s) not in lookup]
    ligand: str | None = None
    if unmapped_lhs or unmapped_rhs:
        try:
            ligand = _infer_ligand_alias(unmapped_lhs, metal=metal, scope=scope)
        except TopologyResolutionError:
            mapped_free_ligand = next(
                (_term_key(key) for key, value in cleaned.items() if value == "L"),
                None,
            )
            if mapped_free_ligand is None:
                raise
            ligand = mapped_free_ligand

    def convert(terms: list[tuple[str, int]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for species, power in terms:
            key = _term_key(species)
            if key in lookup:
                token = lookup[key]
                if token == SOLVENT_MAPPING_TOKEN:
                    continue
            else:
                assert ligand is not None
                token = _abstract_species(species, metal=metal, ligand=ligand)
            rows.append({"species": token, "power": int(power)})
        if not rows:
            raise TopologyResolutionError(
                "reaction side has no species left after dropping solvent water"
            )
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
            {"species": match.group(1), "power": _canonical_power(match.group(2))}
            for match in _CANONICAL_SPECIES_RE.finditer(side)
        ]
        if not rows:
            raise TopologyResolutionError("canonical equation side has no species")
        return sorted(rows, key=lambda row: (row["species"], row["power"]))

    return {"lhs": parse(parts[0]), "rhs": parse(parts[1])}


def _canonical_power(text: str | None) -> int | float:
    """``^N`` -> int N; ``^N.M`` -> float (int when integral); absent -> 1."""
    value = float(text) if text else 1.0
    return int(value) if value.is_integer() else value


def _usable_catalog_records(
    canonical_beta_records: Iterable[Mapping[str, Any]],
    *,
    strict: bool,
) -> dict[tuple[int, str, str], Mapping[str, Any]]:
    """Index the materializable catalog by (id, name, equation).

    ``strict`` raises on malformed or conflicting identities (resolution);
    diagnostics pass ``strict=False`` and simply skip such rows.
    """

    catalog_identities: dict[int, set[tuple[str, str]]] = {}
    usable_records: dict[tuple[int, str, str], Mapping[str, Any]] = {}
    for raw_beta in canonical_beta_records or []:
        beta = dict(raw_beta or {})
        if beta.get("status") != "ok" or not beta.get("materializable", True):
            continue
        try:
            beta_id = int(beta["beta_definition_id"])
        except (KeyError, TypeError, ValueError) as exc:
            if strict:
                raise TopologyResolutionError(
                    "canonical beta catalog contains an invalid beta ID"
                ) from exc
            continue
        if beta_id <= 0:
            if strict:
                raise TopologyResolutionError(
                    "canonical beta catalog contains a nonpositive beta ID"
                )
            continue
        beta_name = str(beta.get("beta_definition_name") or "").strip()
        equation = str(beta.get("equation_python") or "").strip()
        if not beta_name or not equation or equation == "*":
            continue
        identity = (beta_name, equation)
        catalog_identities.setdefault(beta_id, set()).add(identity)
        usable_records[(beta_id, beta_name, equation)] = beta

    if strict:
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
    return usable_records


def resolve_canonical_topology(
    *,
    topology_excerpt: str,
    transcript: str,
    scope: Mapping[str, Any],
    canonical_beta_records: Iterable[Mapping[str, Any]],
    authorization_context_id: str,
    answer_sha256: str,
    species_mapping: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Resolve one source reaction to exactly one canonical beta topology.

    ``canonical_beta_records`` must come from the host's read-only catalog
    enumeration.  In particular, this function deliberately has no argument
    for QueryAgent-observed or prose-cited beta IDs.  ``species_mapping`` is
    the parser's labelled reading of the written species; it is validated
    against the span and the catalog vocabulary, recorded in the receipt
    (only when non-empty, so unmapped receipts keep their shape), and never
    names a beta ID.
    """

    excerpt = str(topology_excerpt or "").strip()
    if not excerpt:
        raise TopologyResolutionError("topology excerpt is missing")
    normalized_excerpt = _normalize_rendering(excerpt)
    if normalized_excerpt not in _normalize_rendering(transcript):
        raise TopologyResolutionError(
            "topology excerpt is not traceable to one contiguous answer span"
        )
    usable_records = _usable_catalog_records(canonical_beta_records, strict=True)
    cleaned_mapping = _clean_species_mapping(species_mapping)
    if cleaned_mapping:
        _validate_mapping_vocabulary(
            cleaned_mapping, canonical_species_vocabulary(usable_records.values())
        )
    query_signature = prose_reaction_signature(
        excerpt, scope, species_mapping=cleaned_mapping
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
    if cleaned_mapping:
        payload["species_mapping"] = dict(cleaned_mapping)
        payload["species_mapping_source"] = "parser"
    payload["receipt_sha256"] = _sha256(payload)
    return payload


# --------------------------------------------------------------------------
# Diagnostics for failed resolutions (never resolve a draft)
# --------------------------------------------------------------------------


def _signature_rows(sig: Mapping[str, Any]) -> set[tuple[str, str, int]]:
    rows: set[tuple[str, str, int]] = set()
    for side in ("lhs", "rhs"):
        for row in sig.get(side) or []:
            rows.add((side, str(row["species"]), int(row["power"])))
    return rows


def _row_weight(row: tuple[str, str, int]) -> float:
    # Solvent, proton, hydroxide and electron terms are shared by many
    # unrelated topologies; the metal/ligand-bearing species carry the match.
    return 0.5 if row[1] in _LIGHT_SPECIES else 1.0


def _weighted_overlap(
    query_rows: set[tuple[str, str, int]],
    canonical_rows: set[tuple[str, str, int]],
) -> float:
    union = query_rows | canonical_rows
    if not union:
        return 0.0
    shared = sum(_row_weight(row) for row in query_rows & canonical_rows)
    return shared / sum(_row_weight(row) for row in union)


def _implicit_convention_token(token: str) -> str:
    """Rewrite a grammar token into SRD-46's implicit-aqua spelling."""

    candidate = _AQUA_LIGAND_RE.sub("", token)
    candidate = _PARENTHESISED_L_RE.sub(r"L\1", candidate)
    return candidate


def _written_terms(excerpt: str) -> dict[str, str]:
    """Map each normalized term key to the species as the chemist wrote it.

    A suggested mapping is echoed back to the parser, whose rule is to key
    the mapping by the written species; the grammar works on normalized
    text, so the written spellings are recovered from the raw excerpt here.
    """

    pieces = re.split(
        r"\s+\+\s+|\||<=>|<->|⇌|↔|⇄|\s=\s|[\r\n;]", str(excerpt or "")
    )
    written: dict[str, str] = {}
    for piece in pieces:
        term = piece.strip().strip("`*_").strip()
        match = re.match(r"^(\d+)\s+(.+)$", term)
        if match:
            term = match.group(2).strip()
        term = _detach_trailing_note(term)
        if term:
            written.setdefault(_term_key(term), term)
    return written


def suggest_species_mapping(
    *,
    topology_excerpt: str,
    scope: Mapping[str, Any],
    canonical_beta_records: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Propose a species mapping under SRD-46's implicit-solvent convention.

    Diagnostic only.  The host rewrites the species the grammar produced but
    the catalog does not know (explicit aqua ligands ``(H2O)n`` dropped, a
    parenthesised ``(L)`` collapsed) and, if needed, treats written free
    water as solvent; the suggestion is returned together with the unique
    canonical equation it would match, when one exists.  The parser must
    assert the mapping itself through ``topology_species_mapping``; nothing
    here resolves a draft.
    """

    records = list(canonical_beta_records or [])
    vocabulary = canonical_species_vocabulary(records)
    empty = {"species_mapping": {}, "resolves_to": None}
    try:
        reaction = _extract_reaction(str(topology_excerpt or ""))
        lhs_text, rhs_text = _split_reaction(reaction)
        lhs = _side_terms(lhs_text)
        rhs = _side_terms(rhs_text)
        metal = _metal_symbol(scope)
        ligand = _infer_ligand_alias(lhs, metal=metal, scope=scope)
    except TopologyResolutionError:
        return empty

    written = _written_terms(str(topology_excerpt or ""))
    rewritten: dict[str, str] = {}
    water_terms: list[str] = []
    for species, _ in lhs + rhs:
        key = _term_key(species)
        label = written.get(key, key)
        if _is_water_term(key):
            water_terms.append(label)
            continue
        try:
            token = _abstract_species(species, metal=metal, ligand=ligand)
        except TopologyResolutionError:
            continue
        if token in vocabulary:
            continue
        candidate = _implicit_convention_token(token)
        if candidate != token and candidate in vocabulary:
            rewritten[label] = candidate

    variants: list[dict[str, str]] = []
    if rewritten:
        variants.append(dict(rewritten))
    if water_terms:
        variants.append({
            **rewritten,
            **{term: SOLVENT_MAPPING_TOKEN for term in water_terms},
        })
    if not variants:
        return empty

    signatures: dict[tuple[int, str, str], dict[str, Any]] = {}
    for identity in sorted(_usable_catalog_records(records, strict=False)):
        try:
            signatures[identity] = canonical_equation_signature(identity[2])
        except TopologyResolutionError:
            continue
    for variant in variants:
        try:
            signature = prose_reaction_signature(
                str(topology_excerpt or ""), scope, species_mapping=variant
            )
        except TopologyResolutionError:
            continue
        hits = [
            identity for identity, candidate in signatures.items()
            if candidate == signature
        ]
        if len({identity[0] for identity in hits}) == 1:
            beta_id, beta_name, equation = hits[0]
            return {
                "species_mapping": variant,
                "resolves_to": {
                    "beta_definition_id": beta_id,
                    "beta_definition_name": beta_name,
                    "equation_python": equation,
                },
            }
    return {"species_mapping": variants[0], "resolves_to": None}


def closest_canonical_candidate_rows(
    *,
    topology_excerpt: str,
    scope: Mapping[str, Any],
    canonical_beta_records: Iterable[Mapping[str, Any]],
    species_mapping: Mapping[str, str] | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Score materializable beta definitions against a failed prose excerpt.

    Diagnostic only: the returned rows never resolve a draft.  A unique
    match under the implicit-solvent suggestion ranks first; otherwise
    weighted signature overlap (when the prose reaction parses, mapping
    applied) outranks plain text similarity.  Whitespace inside species
    tokens is never altered.
    """

    records = list(canonical_beta_records or [])
    usable = sorted(_usable_catalog_records(records, strict=False))
    if not usable:
        return []

    rows: list[dict[str, Any]] = []
    suggestion = suggest_species_mapping(
        topology_excerpt=topology_excerpt,
        scope=scope,
        canonical_beta_records=records,
    )
    if suggestion["resolves_to"] is not None:
        rows.append({
            **suggestion["resolves_to"],
            "score": 1.0,
            "match": "exact_with_suggested_species_mapping",
        })

    query_signature: dict[str, list[dict[str, Any]]] | None = None
    try:
        query_signature = prose_reaction_signature(
            str(topology_excerpt or ""), scope, species_mapping=species_mapping
        )
    except TopologyResolutionError:
        try:
            query_signature = prose_reaction_signature(
                str(topology_excerpt or ""), scope
            )
        except TopologyResolutionError:
            query_signature = None

    normalized_excerpt = _normalize_rendering(str(topology_excerpt or ""))
    query_rows = (
        _signature_rows(query_signature) if query_signature is not None else None
    )
    scored: list[tuple[float, int, str, str, str]] = []
    for beta_id, beta_name, equation in usable:
        if query_rows is not None:
            try:
                canonical_rows = _signature_rows(
                    canonical_equation_signature(equation)
                )
            except TopologyResolutionError:
                canonical_rows = set()
            score = _weighted_overlap(query_rows, canonical_rows)
            kind = "signature_overlap"
        else:
            score = difflib.SequenceMatcher(
                None, normalized_excerpt, _normalize_rendering(equation)
            ).ratio()
            kind = "text_similarity"
        scored.append((score, beta_id, beta_name, equation, kind))
    scored.sort(key=lambda row: (-row[0], row[1]))

    seen = {row["beta_definition_id"] for row in rows}
    for score, beta_id, beta_name, equation, kind in scored:
        if len(rows) >= limit:
            break
        if beta_id in seen:
            continue
        seen.add(beta_id)
        rows.append({
            "beta_definition_id": beta_id,
            "beta_definition_name": beta_name,
            "equation_python": equation,
            "score": round(score, 2),
            "match": kind,
        })
    return rows[:limit]


def closest_canonical_candidates(
    *,
    topology_excerpt: str,
    scope: Mapping[str, Any],
    canonical_beta_records: Iterable[Mapping[str, Any]],
    species_mapping: Mapping[str, str] | None = None,
    limit: int = 5,
) -> list[str]:
    """String form of :func:`closest_canonical_candidate_rows` for messages."""

    return [
        f"beta_def_{row['beta_definition_id']} `{row['equation_python']}` "
        f"({row['beta_definition_name']}; score {row['score']:.2f})"
        for row in closest_canonical_candidate_rows(
            topology_excerpt=topology_excerpt,
            scope=scope,
            canonical_beta_records=canonical_beta_records,
            species_mapping=species_mapping,
            limit=limit,
        )
    ]


def diagnose_topology_excerpt(
    *,
    topology_excerpt: str,
    scope: Mapping[str, Any],
    canonical_beta_records: Iterable[Mapping[str, Any]],
    species_mapping: Mapping[str, str] | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Structured account of why an excerpt did not resolve.

    Returns what the host grammar read (``parsed_signature``), which abstract
    species have no counterpart in the catalog vocabulary
    (``unresolved_species``), the scored closest candidates, the
    implicit-solvent suggestion, a vocabulary hint, and the parser-side
    retry routes.  Diagnostic only.
    """

    records = list(canonical_beta_records or [])
    vocabulary = canonical_species_vocabulary(records)
    parse_error: str | None = None
    parsed: dict[str, list[dict[str, Any]]] | None = None
    try:
        parsed = prose_reaction_signature(
            str(topology_excerpt or ""), scope, species_mapping=species_mapping
        )
    except TopologyResolutionError as exc:
        parse_error = str(exc)
    unresolved: list[str] = []
    if parsed is not None:
        unresolved = sorted({
            str(row["species"])
            for side in ("lhs", "rhs")
            for row in parsed.get(side) or []
            if str(row["species"]) not in vocabulary
        })
    try:
        cleaned_mapping = _clean_species_mapping(species_mapping)
    except TopologyResolutionError:
        cleaned_mapping = {}
    suggestion = suggest_species_mapping(
        topology_excerpt=topology_excerpt,
        scope=scope,
        canonical_beta_records=records,
    )
    return {
        "parse_error": parse_error,
        "parsed_signature": parsed,
        "unresolved_species": unresolved,
        "species_mapping_applied": cleaned_mapping,
        "suggested_species_mapping": suggestion["species_mapping"],
        "suggested_resolution": suggestion["resolves_to"],
        "closest_candidates": closest_canonical_candidate_rows(
            topology_excerpt=topology_excerpt,
            scope=scope,
            canonical_beta_records=records,
            species_mapping=species_mapping,
            limit=limit,
        ),
        "canonical_species_hint": _vocabulary_hint(vocabulary),
        "canonical_species_vocabulary_size": len(vocabulary),
        "retry_options": list(_RETRY_OPTIONS),
    }


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
    if "species_mapping" in value:
        mapping = value.get("species_mapping")
        if not isinstance(mapping, Mapping) or not mapping or any(
            not isinstance(key, str) or not isinstance(token, str)
            or not key.strip() or not token.strip()
            for key, token in mapping.items()
        ):
            raise TopologyResolutionError(
                "topology resolution species mapping is malformed"
            )
    return {**value, "receipt_sha256": claimed}


__all__ = [
    "SOLVENT_MAPPING_TOKEN",
    "TOPOLOGY_RESOLUTION_PROFILE",
    "TopologyResolutionError",
    "beta_names_equal",
    "canonical_equation_signature",
    "canonical_species_vocabulary",
    "closest_canonical_candidate_rows",
    "closest_canonical_candidates",
    "diagnose_topology_excerpt",
    "has_reaction_arrow",
    "prose_reaction_signature",
    "resolve_canonical_topology",
    "suggest_species_mapping",
    "validate_topology_resolution_receipt",
    "written_beta_names",
]
