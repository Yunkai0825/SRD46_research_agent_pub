"""
Chemical-name normalizer for the SRD-46 analysis agent.
========================================================

A general-purpose chemical-name resolver that re-uses, *unchanged*,
the three normalization strategies the SRD-46 **query agent** relies
on:

============================================================  ========================================================
Stage                                                         Code re-used
============================================================  ========================================================
Metal name -> canonical symbol+charge + search variants       ``metal_resolution._normalize_metal_query`` /
                                                              ``metal_resolution._expand_metal_name``
                                                              (consumed automatically by ``search_metals``)
Ligand name -> canonical InChI / SMILES (RDKit + PubChemPy)   ``ligand_resolution._resolve_ligand_identifiers``
                                                              (consumed automatically by ``search_ligands`` as
                                                              the 0-row fallback)
Disambiguation when 0 or >=2 hits                             :func:`difflib.SequenceMatcher` ranking, identical
                                                              to the query agent's
                                                              ``QuickFactGuidance._rank_matches``
============================================================  ========================================================

We invoke those strategies through the LC1 ``quick_fact`` adapter, which is
backed by the shared NIST_SRD46_core_db_search_tools. This module adds
**only**:

* a thin tokenizer that walks free user text into candidate
  unigrams + bigrams (so this can run *before* an LLM gets the text,
  unlike the query agent which delegates extraction to the LLM); and
* the ``QuickFactGuidance``-style ranking, applied automatically here
  because the analysis-agent L0 has no LLM to refine an ambiguous
  match.

No hard-coded chemistry lives in this file.  All aliases, regexes,
RDKit calls, and PubChemPy lookups happen inside the query-agent
helpers.
"""

from __future__ import annotations

import difflib
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


log = logging.getLogger("L0.normalizer")

CHEM_KIND_METAL  = "metal"
CHEM_KIND_LIGAND = "ligand"

# difflib cutoff used by the query agent's similarity helper
# (``QuickFactGuidance._suggest_similar`` uses ``cutoff=0.4`` for
# *suggestions*; we pick a stricter floor here because there is no
# LLM in the loop to reject bad guesses).
_RANK_CUTOFF = 0.55


# ════════════════════════════════════════════════════════════════════
#  Output dataclass
# ════════════════════════════════════════════════════════════════════

@dataclass
class NormalizedChemical:
    """A chemical mention resolved against the SRD-46 DB."""
    raw_name:        str
    canonical_name:  str
    chem_kind:       str                          # "metal" | "ligand"
    db_id:           Optional[str] = None         # "metal_29", "ligand_142"
    element_symbol:  Optional[str] = None         # metals only
    aliases_matched: List[str] = field(default_factory=list)
    search_handles:  Dict[str, str] = field(default_factory=dict)


# ════════════════════════════════════════════════════════════════════
#  Free-text tokenizer (the only piece NOT inherited from the
#  query agent -- the query agent leaves extraction to its L0 LLM).
# ════════════════════════════════════════════════════════════════════

_GENERIC_STOPWORDS: set = {
    "a", "an", "the", "of", "in", "on", "at", "by", "for", "with",
    "and", "or", "to", "from", "as", "is", "are", "be", "vs",
    "this", "that", "these", "those", "some", "any", "all",
    "build", "compute", "calculate", "draw", "make", "show", "give",
    "plot", "generate", "construct", "find", "report", "predict",
    "estimate", "model", "simulate", "run", "do",
    "ph", "pourbaix", "diagram", "potential", "redox", "speciation",
    "stability", "field", "complex", "complexes", "system",
    "equilibrium", "equilibria", "function", "curve", "map",
    "molar", "millimolar", "ionic", "strength", "temperature",
    "pressure", "aqueous", "solution", "solid", "solids", "gas",
    "liquid", "phase", "concentration", "total", "mm", "mol",
    "axis", "range", "between", "across", "over",
    "ligand", "ligands", "metal", "metals", "element", "elements",
    "ion", "ions", "species",
    "no", "yes", "if", "then", "else", "when",
    "acid", "acids", "base", "bases", "salt", "salts",
}

_NUMERIC_RE = re.compile(r"^[\d\.\-\+e]+$", re.IGNORECASE)

# Allow internal '(', ')', digits, '+/-', '^[]' so "Cu(II)", "Fe2+",
# "Cu^[2+]" survive as a single token.
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9\(\)\^\[\]\+\-]*")


def _surface_tokens(text: str) -> List[str]:
    """All raw token surface-forms (pre-stopword filter)."""
    out: List[str] = []
    for m in _TOKEN_RE.finditer(text):
        tok = m.group(0).strip("+-^")
        if tok.count("(") != tok.count(")"):
            tok = tok.strip("()")
        if tok.count("[") != tok.count("]"):
            tok = tok.strip("[]")
        if not tok or len(tok) < 2 or _NUMERIC_RE.match(tok):
            continue
        out.append(tok)
    return out


def _candidate_tokens(text: str) -> List[str]:
    """Tokenise ``text`` into name candidates (bigrams first, then
    unigrams) so multi-word names like ``"citric acid"`` resolve as a
    unit before partial unigrams compete.
    """
    surface  = _surface_tokens(text)
    bigrams  = [f"{a} {b}" for a, b in zip(surface, surface[1:])]
    unigrams = [t for t in surface if t.lower() not in _GENERIC_STOPWORDS]

    out: List[str] = []
    seen: set = set()
    for tok in bigrams + unigrams:
        key = tok.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(tok)
    return out


# ════════════════════════════════════════════════════════════════════
#  DB resolution via the LC1 quick_fact adapter over shared NIST_SRD46_core_db_search_tools
#  -------------------------------------------------------------------
#  The adapter calls:
#      * ``search_metals``  -> ``_expand_metal_name`` (alias table +
#                              regex passes for ``(II)``, ``2+``,
#                              ``Cu^[2+]``)
#      * ``search_ligands`` -> ``_resolve_ligand_identifiers``
#                              (InChI direct -> SMILES via RDKit ->
#                              name via PubChemPy, cached)
#  We just call it -- *no* re-implementation here.
# ════════════════════════════════════════════════════════════════════

def _quick_fact_call(name: str) -> List[Dict[str, Any]]:
    """Run ``quick_fact(name=name)`` and return its match list."""
    try:
        from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.analysis_agent_toolbox.quick_fact_tool import (
            quick_fact,
        )
    except Exception as exc:                        # pragma: no cover
        log.debug("quick_fact unavailable: %s", exc)
        return []
    try:
        out = quick_fact(name=name)
    except Exception as exc:
        log.debug("quick_fact(%r) failed: %s", name, exc)
        return []
    if not isinstance(out, dict) or out.get("error"):
        return []
    return list(out.get("matches") or [])


class _no_pubchem_fallback:
    """Context manager that suppresses the PubChemPy network fallback
    inside ``search_ligands``.

    Implementation: pre-seed the query-agent's
    ``_LIGAND_RESOLVE_CACHE`` with a null result for ``name`` so
    ``_resolve_ligand_identifiers`` short-circuits on the cache hit
    instead of calling ``pcp.get_compounds()``.  The pre-seeded entry
    is removed on exit so genuine resolutions made elsewhere stay
    cacheable.
    """

    def __init__(self, name: str) -> None:
        self.key = (name or "").lower().strip()
        self._cache = None
        self._was_present = False

    def __enter__(self) -> "_no_pubchem_fallback":
        try:
            from NIST_SRD46_core_db_search_tools._normalization_helpers.ligand_resolution import (
                _LIGAND_RESOLVE_CACHE,
            )
        except Exception:                          # pragma: no cover
            return self
        self._cache = _LIGAND_RESOLVE_CACHE
        self._was_present = self.key in _LIGAND_RESOLVE_CACHE
        if not self._was_present and self.key:
            _LIGAND_RESOLVE_CACHE[self.key] = {
                "inchi": None, "smiles": None, "iupac": None,
            }
        return self

    def __exit__(self, *exc) -> None:
        if self._cache is not None and not self._was_present:
            self._cache.pop(self.key, None)
        return None


def _quick_fact_with_metal_expansion(
    name: str, *, pubchem: bool = True,
) -> List[Dict[str, Any]]:
    """``quick_fact`` first, then -- if the input *looks* like a metal
    token (``Fe2+``, ``ferric``, ``Cu^[2+]``) and produced no hits --
    retry through ``_expand_metal_name`` so we exercise the full
    metal-alias table the query agent uses internally.

    ``pubchem=False`` suppresses the PubChemPy network fallback
    inside ``search_ligands`` -- intended for the bulk free-text
    walker, which would otherwise hit PubChem once per garbage token.
    """
    if pubchem:
        hits = _quick_fact_call(name)
    else:
        with _no_pubchem_fallback(name):
            hits = _quick_fact_call(name)
    if hits:
        return hits

    try:
        from NIST_SRD46_core_db_search_tools._normalization_helpers.metal_resolution import (
            _expand_metal_name,
        )
        expansions = list(_expand_metal_name(name) or [])
    except Exception:                               # pragma: no cover
        expansions = []

    seen_pids: set = set()
    aggregated: List[Dict[str, Any]] = []
    for alt in expansions:
        if not alt or alt == name:
            continue
        if pubchem:
            extra = _quick_fact_call(alt)
        else:
            with _no_pubchem_fallback(alt):
                extra = _quick_fact_call(alt)
        for h in extra:
            pid = h.get("prefix_id")
            if not pid or pid in seen_pids:
                continue
            seen_pids.add(pid)
            aggregated.append(h)
        if aggregated:
            break
    return aggregated


# ════════════════════════════════════════════════════════════════════
#  Disambiguation -- mirrors QuickFactGuidance._rank_matches
# ════════════════════════════════════════════════════════════════════

def _candidate_names_for_match(m: Dict[str, Any]) -> List[str]:
    """All name-like fields on a match worth scoring against."""
    out: List[str] = []
    for key in ("name", "common_name", "iupac_name", "symbol", "formula"):
        v = m.get(key)
        if v:
            out.append(str(v))
            # Trailing parenthetical synonym -- SRD46 stores the
            # common name there: ``"Aminoacetic acid (Glycine)"``.
            mo = re.search(r"\(([^()]+)\)\s*$", str(v))
            if mo:
                out.append(mo.group(1).strip())
    return out


def _string_score(query: str, m: Dict[str, Any]) -> float:
    """Best ``SequenceMatcher.ratio()`` over all name-like fields."""
    q = query.lower().strip()
    best = 0.0
    for n in _candidate_names_for_match(m):
        r = difflib.SequenceMatcher(None, q, n.lower()).ratio()
        if r > best:
            best = r
    return best


def _metal_charge_match(query: str, m: Dict[str, Any]) -> bool:
    """True iff ``query`` parses to a metal symbol+charge that
    matches this metal hit exactly.  Uses the query-agent helper
    ``_normalize_metal_query`` -- no local alias table.
    """
    if m.get("entity_type") != "metal":
        return False
    try:
        from NIST_SRD46_core_db_search_tools._normalization_helpers.metal_resolution import (
            _normalize_metal_query,
        )
    except Exception:                               # pragma: no cover
        return False
    norm = (_normalize_metal_query(query) or "").strip()
    if not norm:
        return False
    mo = re.match(r"^([A-Z][a-z]?)(\d*)\s*([+\-]?)$", norm)
    if not mo:
        return False
    sym_q   = mo.group(1)
    digits  = mo.group(2)
    sign    = mo.group(3) or ""
    sym_h   = (m.get("symbol") or "").strip()
    chg_h   = m.get("charge")
    if sym_q != sym_h:
        return False
    if not sign:                                    # bare element name
        return True
    chg_q = int(digits) if digits else 1
    if sign == "-":
        chg_q = -chg_q
    return chg_h is not None and int(chg_h) == chg_q


def _query_mentions_metal_symbol(query: str, m: Dict[str, Any]) -> bool:
    """True iff the query token plausibly refers to *this* metal.

    Required because the SRD-46 metals table contains organoboron
    entries such as ``MeB(OH)_[2]``, ``m-NO_[2]PhB(OH)_[2]``, and
    ``PhB(OH)_[2]``.  Their trailing ``(OH)`` parenthetical is
    extracted by ``_candidate_names_for_match`` as a synonym, which
    scores ~0.8 SequenceMatcher ratio against the user-supplied
    hydroxide token ``OH-`` -- well above ``_RANK_CUTOFF`` (0.55).
    Without this guard, every analysis request that mentions
    ``OH-``/``hydroxide`` silently injects a phantom boronic-acid
    metal into the chemical_system and breaks card assembly.

    A genuine metal mention always contains either the element
    symbol (``Cu``, ``Fe``), a long-form alias caught by
    :func:`_metal_charge_match` (``copper(II)``, ``ferric``), or the
    full canonical name as a substring.  Anything else is a false
    positive from the difflib similarity pass and should be dropped.
    """
    if m.get("entity_type") != "metal":
        return True
    if _metal_charge_match(query, m):
        return True
    q = (query or "").lower()
    sym = (m.get("symbol") or "").lower().strip()
    name = (m.get("name") or "").lower().strip()
    # Accept if the bare element symbol or the full canonical name
    # appears in the query.  ``len(sym) >= 2`` keeps us from matching
    # the lone ``"b"`` in ``"buformin"`` or the ``"n"`` in ``"nitrogen"``.
    if sym and len(sym) >= 2 and sym in q:
        return True
    if name and len(name) >= 4 and name in q:
        return True
    return False


def _disambiguate(query: str,
                  hits: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Pick the best match, mirroring ``QuickFactGuidance``:

    * 0 hits  -> ``None`` (no LLM here to refine, no point guessing).
    * 1 hit   -> auto-pick *if* it survives the metal-mention guard
      (otherwise return ``None`` -- a single false-positive metal hit
      is still a false positive).
    * >1 hits -> rank by :func:`difflib.SequenceMatcher` ratio
      (matches ``_rank_matches``); reject if the top score is below
      :data:`_RANK_CUTOFF`.

    Charge-aware metal match is treated as a perfect score so that
    ``"copper(II)"`` deterministically picks ``metal_41`` (Cu^[2+])
    over ``metal_42`` (Cu^[+]) without depending on string similarity
    of the canonical names.

    Metal hits whose element symbol does not appear in the query are
    dropped entirely (see :func:`_query_mentions_metal_symbol`).
    """
    # Drop metal hits that are not plausibly referenced by ``query`` --
    # this prevents the SRD-46 organoboron metals (``MeB(OH)_[2]``,
    # ``m-NO_[2]PhB(OH)_[2]``, ``PhB(OH)_[2]``, ``Nb(OH)_[2]^[+]``)
    # from being picked up by tokens like ``"OH-"`` or ``"hydroxide"``.
    hits = [h for h in (hits or []) if _query_mentions_metal_symbol(query, h)]

    if not hits:
        return None
    if len(hits) == 1:
        return hits[0]

    def _score(h: Dict[str, Any]) -> float:
        if _metal_charge_match(query, h):
            return 1.0
        return _string_score(query, h)

    ranked = sorted(hits, key=_score, reverse=True)
    top = ranked[0]
    if _score(top) < _RANK_CUTOFF:
        return None
    return top


# ════════════════════════════════════════════════════════════════════
#  Match -> NormalizedChemical
# ════════════════════════════════════════════════════════════════════

def _to_normalized(raw: str, m: Dict[str, Any]) -> NormalizedChemical:
    if m.get("entity_type") == "metal":
        return NormalizedChemical(
            raw_name=raw,
            canonical_name=str(m.get("name") or raw),
            chem_kind=CHEM_KIND_METAL,
            db_id=m.get("prefix_id"),
            element_symbol=str(m.get("symbol") or "") or None,
            aliases_matched=[raw],
            search_handles={
                "name":    str(m.get("name") or ""),
                "element": str(m.get("symbol") or ""),
            },
        )
    return NormalizedChemical(
        raw_name=raw,
        canonical_name=str(m.get("name") or raw),
        chem_kind=CHEM_KIND_LIGAND,
        db_id=m.get("prefix_id"),
        aliases_matched=[raw],
        search_handles={
            "name":    str(m.get("name") or ""),
            "smiles":  str(m.get("smiles") or ""),
            "formula": str(m.get("formula") or ""),
        },
    )


# ════════════════════════════════════════════════════════════════════
#  Public API
# ════════════════════════════════════════════════════════════════════

def normalize_chemical_name(
    name: str, *, pubchem: bool = True,
) -> Optional[NormalizedChemical]:
    """Resolve a single chemical name to one DB entity.

    Pipeline (re-uses query-agent helpers, no local chemistry):

    1. ``quick_fact(name=...)`` -- which internally drives
       ``_expand_metal_name`` for metals and
       ``_resolve_ligand_identifiers`` (RDKit + PubChemPy) for ligands.
    2. If no metal hits and the input parses as a metal token, retry
       through ``_expand_metal_name`` directly to reach
       ``ferric``/``Fe2+``-style aliases.
    3. If no acceptable hit and the input ends in ``-ate`` / ``-ite``,
       retry as the corresponding ``-ic acid`` / ``-ous acid``
       (``citrate`` -> ``citric acid``, ``oxalate`` -> ``oxalic acid``,
       ``sulfite`` -> ``sulfurous acid``).  This is a purely
       grammatical naming convention -- no chemistry table involved.
    4. Disambiguate via :func:`difflib.SequenceMatcher` -- identical
       scoring to the query agent's ``QuickFactGuidance._rank_matches``.

    ``pubchem=False`` skips the PubChemPy network fallback inside
    ``search_ligands`` (used by the bulk free-text walker; for direct
    callers leave this on so an unfamiliar ligand can still resolve).
    """
    if not name or not isinstance(name, str):
        return None
    raw = name.strip()
    if not raw or _NUMERIC_RE.match(raw):
        return None

    hits = _quick_fact_with_metal_expansion(raw, pubchem=pubchem)
    chosen = _disambiguate(raw, hits)
    if chosen is not None:
        return _to_normalized(raw, chosen)

    # ``-ate`` / ``-ite`` -> ``-ic acid`` / ``-ous acid`` retry.
    for alt in _anion_to_acid_variants(raw):
        hits = _quick_fact_with_metal_expansion(alt, pubchem=pubchem)
        chosen = _disambiguate(alt, hits)
        if chosen is not None:
            return _to_normalized(raw, chosen)

    return None


def _anion_to_acid_variants(name: str) -> List[str]:
    """Generate ``-ic acid`` / ``-ous acid`` variants for a token
    ending in ``-ate`` or ``-ite``.  No-op for everything else.
    """
    n = name.strip()
    low = n.lower()
    out: List[str] = []
    if low.endswith("ate") and len(low) > 4:
        out.append(n[:-3] + "ic acid")
    elif low.endswith("ite") and len(low) > 4:
        out.append(n[:-3] + "ous acid")
    return out


def extract_chemicals_from_text(text: str) -> List[NormalizedChemical]:
    """Walk free text, resolve every candidate token via
    :func:`normalize_chemical_name`.

    Order: metals first (in text-occurrence order), then ligands.
    Tokens already absorbed by a longer span (bigram) are skipped to
    avoid ``"citric"`` re-resolving after ``"citric acid"`` won.
    """
    if not text or not isinstance(text, str):
        return []

    metals:    List[NormalizedChemical] = []
    ligands:   List[NormalizedChemical] = []
    seen_ids:  set = set()
    seen_spans: set = set()

    for tok in _candidate_tokens(text):
        if any(tok.lower() in span for span in seen_spans):
            continue
        # pubchem=False: do NOT trigger network lookup on every
        # surface token (would hit pubchem.ncbi.nlm.nih.gov for each
        # garbage word).  Direct callers of ``normalize_chemical_name``
        # still get the full pipeline.
        chem = normalize_chemical_name(tok, pubchem=False)
        if chem is None or not chem.db_id:
            continue
        if chem.db_id in seen_ids:
            continue
        seen_ids.add(chem.db_id)
        seen_spans.add(tok.lower())
        if chem.chem_kind == CHEM_KIND_METAL:
            metals.append(chem)
        else:
            ligands.append(chem)

    return metals + ligands


__all__ = [
    "CHEM_KIND_METAL",
    "CHEM_KIND_LIGAND",
    "NormalizedChemical",
    "normalize_chemical_name",
    "extract_chemicals_from_text",
]
