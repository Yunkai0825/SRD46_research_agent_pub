"""LC1_1 — Deterministic post-commit enrichment helpers.

Pure-Python, side-effect-free utilities that turn the bare
``{metals:[{db_id,name}], ligands:[{db_id,name}]}`` payload committed
by the LC1_1 ReAct sub-agent into the full
``system_catalog.chemical_system`` block the downstream calc-input
pipeline expects (``element``, ``redox_states``, ``smiles``).

Note: a metal's oxidation states are **distinct SRD-46 rows with
distinct ``metal_<int>`` IDs**, so each entry in ``redox_states`` carries
its own ``internal_id`` + ``db_id`` (the metal-level ``internal_id`` /
``db_id`` are intentionally not emitted).

This module performs **DB-row lookups only** — no LLM, no text
parsing. It can be re-used by any layer that already has canonical
SRD-46 ``metal_<int>`` / ``ligand_<int>`` IDs and needs the full
schema.

Public API
----------
``build_system_catalog(committed)``
    Top-level enricher. ``committed`` shape: ``{"metals":[{"db_id",
    "name"}], "ligands":[{"db_id","name"}]}``. Returns
    ``{"system_catalog": {"chemical_system": {"metals":[...],
    "ligands":[...]}}}``.
"""
from __future__ import annotations

import logging
import hashlib
import json
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote
from urllib.request import Request, urlopen

# ── path bootstrap (so this module is usable stand-alone) ──────────
_THIS = Path(__file__).absolute()
_SRD46_ROOT = _THIS.parents[5]   # SRD46_research_agent/
_sp = str(_SRD46_ROOT)
if _sp not in sys.path:
    sys.path.insert(0, _sp)

from NIST_SRD46_core_db_search_tools.entity_search import (  # noqa: E402
    search_ligands,
    search_metals,
)
try:  # deterministic structure validation; absence keeps the gate fail-closed
    from rdkit import Chem
    from rdkit.Chem.inchi import MolToInchi
    from rdkit.Chem.rdMolDescriptors import CalcMolFormula
except ImportError:  # pragma: no cover - exercised by dependency-free installs
    Chem = None
    MolToInchi = None
    CalcMolFormula = None

log = logging.getLogger("LC1_1.id_enrichment")


# ════════════════════════════════════════════════════════════════════
#  Low-level DB-row lookups (ID-keyed, single row)
# ════════════════════════════════════════════════════════════════════

_METAL_ID_RE  = re.compile(r"^metal_(\d+)$")
_LIGAND_ID_RE = re.compile(r"^ligand_(\d+)$")

# Aqueous self-system species (water auto-injection).
_PROTON_DB_ID    = "metal_68"      # H\u207a  (treated as a metal)
_HYDROXIDE_DB_ID = "ligand_10076"  # OH\u207b (treated as a ligand)


def _signed_charge(c: int) -> str:
    return f"+{int(c)}" if c >= 0 else str(int(c))


def metal_internal_id(element: str, charge: int) -> str:
    """Schema-canonical per-species ID, e.g. ``"Cu$+2"``."""
    return f"{element}${_signed_charge(charge)}"


def safe_metal_row(db_id: str) -> Optional[Dict[str, Any]]:
    """Single ``search_metals(metal_id=...)`` row, or ``None`` on miss/error."""
    m = _METAL_ID_RE.match(db_id or "")
    if not m:
        return None
    try:
        rows = search_metals(metal_id=int(m.group(1)), limit=1)
    except Exception as exc:                    # pragma: no cover
        log.warning("safe_metal_row(%s) failed: %s", db_id, exc)
        return None
    return rows[0] if rows else None


def safe_ligand_row(db_id: str) -> Optional[Dict[str, Any]]:
    """Single ``search_ligands(ligand_id=...)`` row, or ``None`` on miss/error."""
    m = _LIGAND_ID_RE.match(db_id or "")
    if not m:
        return None
    try:
        res = search_ligands(ligand_id=int(m.group(1)), limit=1) or {}
    except Exception as exc:                    # pragma: no cover
        log.warning("safe_ligand_row(%s) failed: %s", db_id, exc)
        return None
    rows = res.get("results") or []
    return rows[0] if rows else None


def sibling_metal_rows(element: str) -> List[Dict[str, Any]]:
    """Every SRD-46 row sharing this element symbol (all charge states)."""
    try:
        rows = search_metals(symbol=element, limit=200) or []
    except Exception:                           # pragma: no cover
        return []
    return [r for r in rows
            if str(r.get("symbol") or "").strip() == element]


# ════════════════════════════════════════════════════════════════════
#  Enrichment (commit row → full schema row)
# ════════════════════════════════════════════════════════════════════

_LIGAND_COMMON_RE = re.compile(r"\(([^()]+)\)\s*$")


def _short_ligand_name(committed_name: str, db_row_name: str) -> str:
    """Prefer the trailing parenthesised common name."""
    for src in (committed_name, db_row_name):
        if not src:
            continue
        mo = _LIGAND_COMMON_RE.search(src)
        if mo:
            return mo.group(1).strip()
    return (committed_name or db_row_name or "").strip()


def enrich_metals(metals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Attach ``element`` + ``redox_states``; dedupe by element.

    Each oxidation state is a distinct SRD-46 row, so every entry in
    ``redox_states`` carries its own ``internal_id`` + ``db_id``. No
    metal-level ``internal_id`` / ``db_id`` is emitted.
    """
    out: List[Dict[str, Any]] = []
    seen_elements: set = set()
    for entry in metals:
        db_id = entry.get("db_id", "")
        row = safe_metal_row(db_id)
        sym = (str(row.get("symbol")) if row else "").strip() or entry.get("name", "")
        element = sym.split("+")[0].split("-")[0].strip() or sym
        try:
            charge = int(row.get("charge")) if row and row.get("charge") is not None else 0
        except (TypeError, ValueError):
            charge = 0
        if element in seen_elements:
            continue
        seen_elements.add(element)

        # Collect every oxidation state for this element, each carrying its
        # OWN internal_id + db_id.  Seed with the committed row so its db_id
        # survives even if the sibling scan misses it.
        redox_raw: List[Tuple[int, str, str]] = []
        if element:
            redox_raw.append(
                (charge, metal_internal_id(element, charge), db_id)
            )
        for sib in sibling_metal_rows(element):
            try:
                c_sib = int(sib.get("charge"))
            except (TypeError, ValueError):
                continue
            redox_raw.append((
                c_sib,
                metal_internal_id(element, c_sib),
                str(sib.get("metal_id") or ""),
            ))
        # dedupe by internal_id (prefer a non-empty db_id) + sort by
        # descending charge
        db_by_iid: Dict[str, str] = {}
        charge_by_iid: Dict[str, int] = {}
        for c_val, iid, did in redox_raw:
            if not iid:
                continue
            if iid not in db_by_iid:
                db_by_iid[iid] = did
                charge_by_iid[iid] = c_val
            elif not db_by_iid[iid] and did:
                db_by_iid[iid] = did
        redox: List[Dict[str, str]] = [
            {"internal_id": iid, "db_id": db_by_iid[iid]}
            for iid in sorted(db_by_iid, key=lambda k: -charge_by_iid[k])
        ]

        out.append({
            "name":         entry.get("name") or element,
            "element":      element,
            "redox_states": redox,
        })
    return out


def enrich_ligands(
    ligands: List[Dict[str, Any]],
    *,
    free_ligand_state_cache_path: str | Path | None = None,
) -> List[Dict[str, Any]]:
    """Attach identity-preserving metadata and sequential component IDs.

    The committed SRD-46 ``ligand_<int>`` ID is authoritative.  PubChem can
    only supply a run-local metadata overlay for missing SRD fields; its CID
    is provenance and can never replace or create a component ID.  Existing
    non-placeholder SRD values always win.

    Free-ligand-state inference is a separate, stricter decision.  It is only
    attempted when SRD-46 has no HxL/pKa/explicit figure state and the resolved
    molecular structure is both neutral and non-protic.
    """
    cache = _load_free_ligand_state_cache(free_ligand_state_cache_path)
    cache_entries = cache["entries"]
    cache_changed = False
    out: List[Dict[str, Any]] = []
    for i, entry in enumerate(_dedupe_ligands_by_db_id(ligands), start=1):
        db_id = str(entry.get("db_id") or "")
        row = safe_ligand_row(db_id)
        row_db_id = _canonical_ligand_db_id(
            row.get("ligand_id") if row else None
        )
        exact_row = row if row and row_db_id == db_id else None
        short = _short_ligand_name(
            entry.get("name", ""),
            str(exact_row.get("ligand_name") or "") if exact_row else "",
        )
        ligand_out: Dict[str, Any] = {
            "name":        short,
            "db_id":       db_id,
            "internal_id": f"L{i}",
        }
        canonical_srd_name = (
            str(exact_row.get("ligand_name") or "").strip()
            if exact_row else ""
        )

        # Copy valid SRD metadata first.  Placeholders are treated as absent,
        # never as values which an external source is allowed to overwrite.
        for field_name in _LIGAND_STRUCTURE_FIELDS:
            value = exact_row.get(field_name) if exact_row else None
            if not _is_missing_ligand_metadata(value):
                ligand_out[field_name] = str(value).strip()

        metadata_overlay = None
        free_state = None
        needs_overlay = bool(
            exact_row and any(
                _is_missing_ligand_metadata(exact_row.get(field_name))
                for field_name in _REQUIRED_LIGAND_STRUCTURE_FIELDS
            )
        )
        if exact_row and canonical_srd_name:
            cache_entry = cache_entries.get(db_id)
            if cache_entry is not None and not _cache_identity_matches(
                cache_entry,
                ligand_db_id=db_id,
                canonical_srd_name=canonical_srd_name,
            ):
                # Wrong/stale SRD bindings invalidate the whole entry.  A
                # PubChem payload is never rebound to a different ligand ID.
                cache_entries.pop(db_id, None)
                cache_entry = None
                cache_changed = True

            if needs_overlay:
                metadata_overlay = _cached_ligand_metadata_overlay(
                    cache_entries=cache_entries,
                    ligand_db_id=db_id,
                    canonical_srd_name=canonical_srd_name,
                )
                if metadata_overlay is None:
                    metadata_overlay = _resolved_ligand_metadata_overlay(
                        committed_entry=entry,
                        ligand_row=exact_row,
                    )
                    if metadata_overlay is not None:
                        cache_entry = _cache_entry_for_identity(
                            cache_entries.get(db_id),
                            ligand_db_id=db_id,
                            canonical_srd_name=canonical_srd_name,
                        )
                        cache_entry["metadata_overlay"] = metadata_overlay
                        cache_entries[db_id] = cache_entry
                        cache_changed = True

            # Copy only fields absent from SRD.  This is the actual overlay:
            # it cannot modify any valid database metadata.
            if metadata_overlay is not None:
                for field_name in _LIGAND_STRUCTURE_FIELDS:
                    if (
                        field_name not in ligand_out
                        and not _is_missing_ligand_metadata(
                            metadata_overlay.get(field_name)
                        )
                    ):
                        ligand_out[field_name] = str(
                            metadata_overlay[field_name]
                        ).strip()

            if not _has_srd46_reference_state(exact_row):
                free_state = _cached_free_ligand_state(
                    cache_entries=cache_entries,
                    ligand_db_id=db_id,
                    canonical_srd_name=canonical_srd_name,
                )
                if free_state is None and metadata_overlay is not None:
                    free_state = _free_ligand_state_from_metadata_overlay(
                        ligand_db_id=db_id,
                        metadata_overlay=metadata_overlay,
                    )
                    if free_state is not None:
                        cache_entry = _cache_entry_for_identity(
                            cache_entries.get(db_id),
                            ligand_db_id=db_id,
                            canonical_srd_name=canonical_srd_name,
                        )
                        cache_entry["free_ligand_state"] = free_state
                        cache_entries[db_id] = cache_entry
                        cache_changed = True
            elif isinstance(cache_entries.get(db_id), dict) and (
                "free_ligand_state" in cache_entries[db_id]
            ):
                # A later/updated explicit SRD state always wins.  Retain a
                # valid structural overlay but remove stale inferred state.
                cache_entries[db_id].pop("free_ligand_state", None)
                cache_changed = True

        if free_state is not None:
            ligand_out["free_ligand_state"] = free_state
        out.append(ligand_out)
    if free_ligand_state_cache_path is not None and (
        cache_changed
        or bool(cache.get("_needs_rewrite"))
        or not Path(free_ligand_state_cache_path).is_file()
    ):
        _write_free_ligand_state_cache(
            free_ligand_state_cache_path,
            cache,
        )
    return out


def _has_srd46_reference_state(ligand_row: Dict[str, Any]) -> bool:
    hxl = str(ligand_row.get("ligand_HxL_definition") or "").strip()
    if hxl and hxl != "***":
        return True
    if list(ligand_row.get("pka_brackets") or []):
        return True
    figure = re.sub(
        r"\s+", "", str(ligand_row.get("ligand_figure_definition") or "")
    )
    return bool(re.fullmatch(r"L(?:/)?(?:\d+[+-]|[+-]+)?", figure))


_LIGAND_STRUCTURE_FIELDS = ("formula", "smiles", "inchi", "iupac_name")
_REQUIRED_LIGAND_STRUCTURE_FIELDS = ("formula", "smiles", "inchi")
_MISSING_LIGAND_METADATA = {
    "",
    "-",
    "n/a",
    "na",
    "none",
    "null",
    "not defined",
    "not available",
    "unknown",
}


def _is_missing_ligand_metadata(value: Any) -> bool:
    """Recognise null and legacy placeholder values without guessing."""

    if value is None:
        return True
    text = str(value).strip()
    if text.lower() in _MISSING_LIGAND_METADATA:
        return True
    return bool(text and set(text) <= {"*"})


_PUBCHEM_TIMEOUT_SECONDS = 15.0
_PUBCHEM_MAX_RESPONSE_BYTES = 2_000_000


def _structure_query_names(ligand_row: Dict[str, Any]) -> List[str]:
    """Return only SRD-bound name forms used for external resolution.

    Agent-committed display names are deliberately excluded: they may improve
    presentation, but cannot redirect a component-state identity lookup.
    """

    candidates = [
        str(ligand_row.get("ligand_name") or "").strip(),
    ]
    expanded: List[str] = []
    for candidate in candidates:
        if not candidate:
            continue
        expanded.append(candidate)
        without_suffix = re.sub(r"\s*\([^()]+\)\s*$", "", candidate).strip()
        if without_suffix and without_suffix != candidate:
            expanded.append(without_suffix)
    return list(dict.fromkeys(expanded))


def _resolved_ligand_metadata_overlay(
    *,
    committed_entry: Dict[str, Any],
    ligand_row: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Resolve a PubChem metadata overlay bound to one exact SRD ligand."""

    if not ligand_row or Chem is None or MolToInchi is None:
        return None
    ligand_id = _numeric_catalog_id(
        committed_entry.get("db_id") or ligand_row.get("ligand_id"),
        prefix="ligand",
    )
    row_ligand_id = _numeric_catalog_id(
        ligand_row.get("ligand_id"), prefix="ligand"
    )
    if ligand_id is None or row_ligand_id != ligand_id:
        return None
    resolved: Dict[str, Any] = {}
    query_name = ""
    for candidate in _structure_query_names(ligand_row):
        result = _resolve_unique_pubchem_structure(candidate)
        if result is not None:
            resolved = result
            query_name = candidate
            break
    if not resolved:
        return None
    molecule = Chem.MolFromSmiles(str(resolved["smiles"]))
    if molecule is None or len(Chem.GetMolFrags(molecule)) != 1:
        return None
    canonical_smiles = Chem.MolToSmiles(molecule)
    canonical_inchi = MolToInchi(molecule)
    if canonical_smiles != str(resolved["smiles"]):
        return None
    if canonical_inchi != str(resolved["inchi"]):
        return None
    formula = str(resolved.get("formula") or "").strip()
    if _is_missing_ligand_metadata(formula) and CalcMolFormula is not None:
        formula = str(CalcMolFormula(molecule)).strip()
    if _is_missing_ligand_metadata(formula):
        return None
    if CalcMolFormula is not None and formula != str(CalcMolFormula(molecule)):
        return None
    ligand_db_id = f"ligand_{ligand_id}"
    canonical_srd_name = str(ligand_row.get("ligand_name") or "").strip()
    if not canonical_srd_name:
        return None
    payload = {
        "formula": formula,
        "smiles": canonical_smiles,
        "inchi": canonical_inchi,
        "iupac_name": resolved.get("iupac"),
        "provenance": {
            "kind": "PubChem",
            "source_database_ID": ligand_db_id,
            "canonical_srd_name": canonical_srd_name,
            "compound_id": int(resolved["cid"]),
            "query_name": query_name,
            "source_payload_sha256": str(resolved["source_payload_sha256"]),
            "identity_binding": (
                "unique PubChem name result bound to exact SRD-46 ligand ID"
            ),
        },
    }
    payload["receipt_sha256"] = hashlib.sha256(json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")).hexdigest()
    return payload


def _free_ligand_state_from_metadata_overlay(
    *,
    ligand_db_id: str,
    metadata_overlay: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Derive ``L/0`` only from a neutral, non-protic molecular overlay."""

    if Chem is None:
        return None
    molecule = Chem.MolFromSmiles(str(metadata_overlay.get("smiles") or ""))
    if molecule is None or len(Chem.GetMolFrags(molecule)) != 1:
        return None
    charge = int(Chem.GetFormalCharge(molecule))
    if charge != 0 or any(
        atom.GetAtomicNum() not in {1, 6}
        and atom.GetTotalNumHs(includeNeighbors=True) > 0
        for atom in molecule.GetAtoms()
    ):
        return None
    overlay_provenance = metadata_overlay.get("provenance") or {}
    if overlay_provenance.get("source_database_ID") != ligand_db_id:
        return None
    payload = {
        "canonical_HOL": "L",
        "charge": charge,
        "reference_state_classification": "neutral_nonprotic_free_ligand/v1",
        "provenance": {
            "kind": "PubChem",
            "source_database_ID": ligand_db_id,
            "compound_id": int(overlay_provenance["compound_id"]),
            "query_name": str(overlay_provenance["query_name"]),
            "resolved_iupac_name": metadata_overlay.get("iupac_name"),
            "canonical_smiles": str(metadata_overlay["smiles"]),
            "inchi": str(metadata_overlay["inchi"]),
            "source_payload_sha256": str(
                overlay_provenance["source_payload_sha256"]
            ),
            "identity_binding": (
                "unique PubChem name result bound to exact SRD-46 ligand ID"
            ),
        },
        "derivation": {
            "rule": "pubchem_rdkit_neutral_nonprotic_free_ligand/v1",
            "formal_charge_method": "RDKit Chem.GetFormalCharge",
            "nonprotic_check": "no non-carbon heteroatom bears hydrogen",
        },
    }
    payload["receipt_sha256"] = hashlib.sha256(json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")).hexdigest()
    return payload


def _resolved_free_ligand_state(
    *,
    committed_entry: Dict[str, Any],
    ligand_row: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Compatibility helper for strict free-state resolution.

    Metadata resolution itself is independent of the acid/base state.  This
    helper deliberately adds the stricter state gate before deriving ``L``.
    """

    if not ligand_row or _has_srd46_reference_state(ligand_row):
        return None
    overlay = _resolved_ligand_metadata_overlay(
        committed_entry=committed_entry,
        ligand_row=ligand_row,
    )
    if overlay is None:
        return None
    ligand_db_id = _canonical_ligand_db_id(committed_entry.get("db_id"))
    return _free_ligand_state_from_metadata_overlay(
        ligand_db_id=ligand_db_id,
        metadata_overlay=overlay,
    )


def _numeric_catalog_id(value: Any, *, prefix: str) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    text = str(value).strip()
    marker = f"{prefix}_"
    if text.startswith(marker):
        text = text[len(marker):]
    if not text.isdigit():
        return None
    parsed = int(text)
    return parsed if parsed > 0 else None


_FREE_LIGAND_CACHE_SCHEMA_V1 = "lc1_1_pubchem_free_ligand_cache/v1"
_FREE_LIGAND_CACHE_SCHEMA = "lc1_1_pubchem_ligand_enrichment_cache/v2"
_LIGAND_METADATA_OVERLAY_KEYS = {
    "formula",
    "smiles",
    "inchi",
    "iupac_name",
    "provenance",
    "receipt_sha256",
}
_LIGAND_METADATA_PROVENANCE_KEYS = {
    "kind",
    "source_database_ID",
    "canonical_srd_name",
    "compound_id",
    "query_name",
    "source_payload_sha256",
    "identity_binding",
}
_FREE_LIGAND_CONTRACT_KEYS = {
    "canonical_HOL",
    "charge",
    "reference_state_classification",
    "provenance",
    "derivation",
    "receipt_sha256",
}
_FREE_LIGAND_PROVENANCE_KEYS = {
    "kind",
    "source_database_ID",
    "compound_id",
    "query_name",
    "resolved_iupac_name",
    "canonical_smiles",
    "inchi",
    "source_payload_sha256",
    "identity_binding",
}
_FREE_LIGAND_DERIVATION = {
    "rule": "pubchem_rdkit_neutral_nonprotic_free_ligand/v1",
    "formal_charge_method": "RDKit Chem.GetFormalCharge",
    "nonprotic_check": "no non-carbon heteroatom bears hydrogen",
}


def _canonical_ligand_db_id(value: Any) -> str:
    ligand_id = _numeric_catalog_id(value, prefix="ligand")
    if ligand_id is not None:
        return f"ligand_{ligand_id}"
    return str(value or "").strip()


def _dedupe_ligands_by_db_id(
    ligands: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Coalesce ligand rows by their canonical, existing SRD-46 ID.

    First occurrence wins, preserving the commit order used for ``L1``,
    ``L2``, ... assignment.  Canonicalization changes only spelling such as
    ``ligand_011422`` to the same existing ``ligand_11422`` identity; no
    external identifier can become a component ID.
    """

    out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for raw in ligands:
        if not isinstance(raw, dict):
            continue
        entry = dict(raw)
        canonical_db_id = _canonical_ligand_db_id(entry.get("db_id"))
        if canonical_db_id:
            entry["db_id"] = canonical_db_id
            if canonical_db_id in seen:
                continue
            seen.add(canonical_db_id)
        out.append(entry)
    return out


def _empty_free_ligand_state_cache() -> Dict[str, Any]:
    return {
        "schema_version": _FREE_LIGAND_CACHE_SCHEMA,
        "entries": {},
        "_needs_rewrite": False,
    }


def _load_free_ligand_state_cache(
    cache_path: str | Path | None,
) -> Dict[str, Any]:
    if cache_path is None:
        return _empty_free_ligand_state_cache()
    path = Path(cache_path)
    if not path.is_file():
        return _empty_free_ligand_state_cache()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        log.warning("Ignoring unreadable LC1_1 ligand enrichment cache: %s", exc)
        return _empty_free_ligand_state_cache()
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version", "entries",
    }:
        return _empty_free_ligand_state_cache()
    schema_version = payload.get("schema_version")
    if schema_version not in {
        _FREE_LIGAND_CACHE_SCHEMA,
        _FREE_LIGAND_CACHE_SCHEMA_V1,
    }:
        return _empty_free_ligand_state_cache()
    entries = payload.get("entries")
    if not isinstance(entries, dict):
        return _empty_free_ligand_state_cache()
    migrated_entries = dict(entries)
    # V1 entries carry only the state contract.  Preserve them for strict
    # revalidation, but always write the expanded V2 envelope afterward.
    return {
        "schema_version": _FREE_LIGAND_CACHE_SCHEMA,
        "entries": migrated_entries,
        "_needs_rewrite": schema_version != _FREE_LIGAND_CACHE_SCHEMA,
    }


def _write_free_ligand_state_cache(
    cache_path: str | Path,
    cache: Dict[str, Any],
) -> None:
    """Write the run-local enrichment cache atomically; never mutate SRD."""

    path = Path(cache_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": _FREE_LIGAND_CACHE_SCHEMA,
        "entries": {
            key: cache["entries"][key]
            for key in sorted(cache.get("entries") or {})
        },
    }
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _cache_identity_matches(
    entry: Any,
    *,
    ligand_db_id: str,
    canonical_srd_name: str,
) -> bool:
    return bool(
        isinstance(entry, dict)
        and entry.get("ligand_db_id") == ligand_db_id
        and canonical_srd_name
        and entry.get("canonical_srd_name") == canonical_srd_name
        and set(entry).issubset({
            "ligand_db_id",
            "canonical_srd_name",
            "metadata_overlay",
            "free_ligand_state",
        })
        and {"ligand_db_id", "canonical_srd_name"}.issubset(entry)
    )


def _cache_entry_for_identity(
    entry: Any,
    *,
    ligand_db_id: str,
    canonical_srd_name: str,
) -> Dict[str, Any]:
    if _cache_identity_matches(
        entry,
        ligand_db_id=ligand_db_id,
        canonical_srd_name=canonical_srd_name,
    ):
        return dict(entry)
    return {
        "ligand_db_id": ligand_db_id,
        "canonical_srd_name": canonical_srd_name,
    }


def _cached_ligand_metadata_overlay(
    *,
    cache_entries: Dict[str, Any],
    ligand_db_id: str,
    canonical_srd_name: str,
) -> Optional[Dict[str, Any]]:
    entry = cache_entries.get(ligand_db_id)
    if not _cache_identity_matches(
        entry,
        ligand_db_id=ligand_db_id,
        canonical_srd_name=canonical_srd_name,
    ):
        return None
    return _validated_cached_ligand_metadata_overlay(
        entry.get("metadata_overlay"),
        ligand_db_id=ligand_db_id,
        canonical_srd_name=canonical_srd_name,
    )


def _validated_cached_ligand_metadata_overlay(
    overlay: Any,
    *,
    ligand_db_id: str,
    canonical_srd_name: str,
) -> Optional[Dict[str, Any]]:
    """Revalidate a metadata overlay, its receipt, molecule, and SRD bind."""

    if Chem is None or MolToInchi is None or CalcMolFormula is None:
        return None
    if not isinstance(overlay, dict) or set(overlay) != (
        _LIGAND_METADATA_OVERLAY_KEYS
    ):
        return None
    unsigned = dict(overlay)
    receipt = unsigned.pop("receipt_sha256", None)
    expected_receipt = hashlib.sha256(json.dumps(
        unsigned,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")).hexdigest()
    if receipt != expected_receipt:
        return None
    provenance = overlay.get("provenance")
    if not isinstance(provenance, dict) or set(provenance) != (
        _LIGAND_METADATA_PROVENANCE_KEYS
    ):
        return None
    compound_id = provenance.get("compound_id")
    if (
        provenance.get("kind") != "PubChem"
        or provenance.get("source_database_ID") != ligand_db_id
        or provenance.get("canonical_srd_name") != canonical_srd_name
        or isinstance(compound_id, bool)
        or not isinstance(compound_id, int)
        or compound_id <= 0
    ):
        return None
    if re.fullmatch(
        r"[0-9a-f]{64}", str(provenance.get("source_payload_sha256") or "")
    ) is None:
        return None
    for field_name in ("query_name", "identity_binding"):
        if _is_missing_ligand_metadata(provenance.get(field_name)):
            return None
    for field_name in ("formula", "smiles", "inchi"):
        if _is_missing_ligand_metadata(overlay.get(field_name)):
            return None
    molecule = Chem.MolFromSmiles(str(overlay["smiles"]))
    if molecule is None or len(Chem.GetMolFrags(molecule)) != 1:
        return None
    if Chem.MolToSmiles(molecule) != overlay["smiles"]:
        return None
    if MolToInchi(molecule) != overlay["inchi"]:
        return None
    if str(CalcMolFormula(molecule)) != overlay["formula"]:
        return None
    return json.loads(json.dumps(overlay))


def _cached_free_ligand_state(
    *,
    cache_entries: Dict[str, Any],
    ligand_db_id: str,
    canonical_srd_name: str,
) -> Optional[Dict[str, Any]]:
    entry = cache_entries.get(ligand_db_id)
    if not _cache_identity_matches(
        entry,
        ligand_db_id=ligand_db_id,
        canonical_srd_name=canonical_srd_name,
    ):
        return None
    return _validated_cached_free_ligand_state(
        entry.get("free_ligand_state"),
        ligand_db_id=ligand_db_id,
    )


def _validated_cached_free_ligand_state(
    contract: Any,
    *,
    ligand_db_id: str,
) -> Optional[Dict[str, Any]]:
    """Revalidate a cache hit against its receipt, structure, and SRD ID."""

    if Chem is None or MolToInchi is None:
        return None
    if not isinstance(contract, dict) or set(contract) != (
        _FREE_LIGAND_CONTRACT_KEYS
    ):
        return None
    unsigned = dict(contract)
    receipt = unsigned.pop("receipt_sha256", None)
    expected_receipt = hashlib.sha256(json.dumps(
        unsigned,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")).hexdigest()
    if receipt != expected_receipt:
        return None
    if (
        contract.get("canonical_HOL") != "L"
        or isinstance(contract.get("charge"), bool)
        or contract.get("charge") != 0
        or contract.get("reference_state_classification")
        != "neutral_nonprotic_free_ligand/v1"
    ):
        return None
    provenance = contract.get("provenance")
    derivation = contract.get("derivation")
    if not isinstance(provenance, dict) or set(provenance) != (
        _FREE_LIGAND_PROVENANCE_KEYS
    ):
        return None
    if derivation != _FREE_LIGAND_DERIVATION:
        return None
    compound_id = provenance.get("compound_id")
    if (
        provenance.get("kind") != "PubChem"
        or provenance.get("source_database_ID") != ligand_db_id
        or isinstance(compound_id, bool)
        or not isinstance(compound_id, int)
        or compound_id <= 0
    ):
        return None
    if re.fullmatch(
        r"[0-9a-f]{64}", str(provenance.get("source_payload_sha256") or "")
    ) is None:
        return None
    for field_name in (
        "query_name", "canonical_smiles", "inchi", "identity_binding",
    ):
        value = provenance.get(field_name)
        if not isinstance(value, str) or not value.strip():
            return None
    molecule = Chem.MolFromSmiles(provenance["canonical_smiles"])
    if molecule is None or len(Chem.GetMolFrags(molecule)) != 1:
        return None
    if Chem.MolToSmiles(molecule) != provenance["canonical_smiles"]:
        return None
    if MolToInchi(molecule) != provenance["inchi"]:
        return None
    if int(Chem.GetFormalCharge(molecule)) != 0 or any(
        atom.GetAtomicNum() not in {1, 6}
        and atom.GetTotalNumHs(includeNeighbors=True) > 0
        for atom in molecule.GetAtoms()
    ):
        return None
    return json.loads(json.dumps(contract))


@lru_cache(maxsize=128)
def _resolve_unique_pubchem_structure(name: str) -> Optional[Dict[str, Any]]:
    """Resolve one exact name through bounded PUG REST, or fail closed.

    PubChemPy delegates to ``urlopen`` without a timeout.  A bounded request is
    used here so an unavailable enrichment service cannot consume an agent's
    entire run budget.  The in-process cache also prevents duplicate calls for
    the canonical and display copies of one ligand.
    """

    if Chem is None or MolToInchi is None:
        return None
    property_names = (
        "Title,IUPACName,MolecularFormula,CanonicalSMILES,"
        "ConnectivitySMILES,InChI"
    )
    url = (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
        f"{quote(name, safe='')}/property/{property_names}/JSON"
    )
    try:
        request = Request(url, headers={"User-Agent": "SRD46-research-agent/1"})
        with urlopen(request, timeout=_PUBCHEM_TIMEOUT_SECONDS) as response:
            raw = response.read(_PUBCHEM_MAX_RESPONSE_BYTES + 1)
    except Exception as exc:  # pragma: no cover - network/service dependent
        log.warning("PubChem component-state lookup failed for %r: %s", name, exc)
        return None
    if len(raw) > _PUBCHEM_MAX_RESPONSE_BYTES:
        log.warning("PubChem component-state response was too large for %r", name)
        return None
    try:
        doc = json.loads(raw.decode("utf-8"))
        compounds = doc["PropertyTable"]["Properties"]
    except (KeyError, TypeError, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(compounds, list) or len(compounds) != 1:
        return None
    compound = compounds[0]
    if not isinstance(compound, dict):
        return None
    raw_smiles = (
        compound.get("ConnectivitySMILES")
        or compound.get("CanonicalSMILES")
    )
    cid = compound.get("CID")
    if not raw_smiles or isinstance(cid, bool) or not isinstance(cid, int) or cid <= 0:
        return None
    molecule = Chem.MolFromSmiles(str(raw_smiles))
    if molecule is None or len(Chem.GetMolFrags(molecule)) != 1:
        return None
    canonical_smiles = Chem.MolToSmiles(molecule)
    canonical_inchi = MolToInchi(molecule)
    reported_inchi = str(compound.get("InChI") or "")
    if not reported_inchi or canonical_inchi != reported_inchi:
        return None
    return {
        "cid": cid,
        "formula": compound.get("MolecularFormula"),
        "smiles": canonical_smiles,
        "inchi": canonical_inchi,
        "iupac": compound.get("IUPACName") or compound.get("Title"),
        "source_payload_sha256": hashlib.sha256(raw).hexdigest(),
    }

def build_system_catalog(
    committed: Dict[str, Any],
    *,
    water_system: bool = True,
    free_ligand_state_cache_path: str | Path | None = None,
) -> Dict[str, Any]:
    """Wrap enriched metals + ligands in the canonical ``system_catalog`` block.

    When ``water_system`` is ``True`` (default) the aqueous self-system
    proton H\u207a (a metal, ``metal_68``) and hydroxide OH\u207b (a ligand,
    ``ligand_10076``) are injected as first-class catalog entries so the
    downstream pipeline treats them as ordinary system species. They are
    de-duplicated by ``db_id`` so an explicit LLM commit of either is not
    doubled. ``free_ligand_state_cache_path`` is the backward-compatible
    argument name for the caller's run-local PubChem enrichment cache; it may
    supplement missing metadata but never changes SRD identifiers.
    """
    metals = enrich_metals(committed.get("metals") or [])
    ligands = enrich_ligands(
        committed.get("ligands") or [],
        free_ligand_state_cache_path=free_ligand_state_cache_path,
    )
    if water_system:
        metals = _inject_proton_metal(metals)
        ligands = _inject_hydroxide_ligand(ligands)
    ligands = _dedupe_ligands_by_db_id(ligands)
    return {
        "system_catalog": {
            "chemical_system": {
                "metals":  metals,
                "ligands": ligands,
            }
        }
    }


def _inject_proton_metal(metals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Prepend the aqueous proton H\u207a (``metal_68``) as a metal entry.

    The entry is surfaced from SRD-46 (name from the ``metal_68`` row)
    and treated like any other metal. Idempotent: if any committed metal
    already carries the proton db_id in its redox states, the list is
    returned unchanged.
    """
    for m in metals:
        for rs in m.get("redox_states") or []:
            if str(rs.get("db_id") or "") == _PROTON_DB_ID:
                return metals
    row = safe_metal_row(_PROTON_DB_ID) or {}
    name = str(row.get("symbol") or "H+").strip() or "H+"
    proton = {
        "name":         name,
        "element":      "H",
        "redox_states": [
            {"internal_id": metal_internal_id("H", 1), "db_id": _PROTON_DB_ID},
        ],
        "water_species": True,
    }
    return [proton] + list(metals)


def _inject_hydroxide_ligand(ligands: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Append the aqueous hydroxide OH\u207b (``ligand_10076``) as a ligand entry.

    Surfaced from SRD-46 (name + SMILES from the ``ligand_10076`` row) and
    treated like any other ligand. Idempotent on ``db_id``. Uses the
    reserved ``L0`` internal id so the real ligands keep their
    ``L1``/``L2``/\u2026 numbering and the downstream OH\u207b machinery is untouched.
    """
    for l in ligands:
        if str(l.get("db_id") or "") == _HYDROXIDE_DB_ID:
            return ligands
    row = safe_ligand_row(_HYDROXIDE_DB_ID) or {}
    short = _short_ligand_name("", str(row.get("ligand_name") or "")) or "OH-"
    hydroxide: Dict[str, Any] = {
        "name":         short,
        "db_id":        _HYDROXIDE_DB_ID,
        "internal_id":  "L0",
        "water_species": True,
    }
    smiles = str(row.get("smiles") or "").strip()
    if smiles:
        hydroxide["smiles"] = smiles
    return list(ligands) + [hydroxide]


__all__ = [
    "build_system_catalog",
    "enrich_metals",
    "enrich_ligands",
    "metal_internal_id",
    "safe_metal_row",
    "safe_ligand_row",
    "sibling_metal_rows",
]
