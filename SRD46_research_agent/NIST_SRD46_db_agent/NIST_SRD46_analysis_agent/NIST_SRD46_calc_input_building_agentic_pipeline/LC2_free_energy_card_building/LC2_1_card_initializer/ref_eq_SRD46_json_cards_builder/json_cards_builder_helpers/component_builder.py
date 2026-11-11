"""Deterministic builder for the `components` section of the speciation JSON.

Queries the NIST SRD-46 database (via NIST_SRD46_core_db_search_tools)
and constructs the component template used by the equation builder.
"""

from __future__ import annotations

import json
import hashlib
import math
import os
import re
import sys
import time
from pathlib import Path
from typing import Any


# ── DB access setup (NIST_SRD46_core_db_search_tools) ─────────────
_SRD46_ROOT = Path(__file__).absolute().parents[7]  # SRD46_research_agent/ (holds NIST_SRD46_core_db_search_tools)
if str(_SRD46_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRD46_ROOT))

from NIST_SRD46_core_db_search_tools.entity_search import (
    search_metals as _search_metals,
    search_ligands as _search_ligands,
)
from NIST_SRD46_core_db_search_tools._db_connection import get_cards_db

try:
    from rdkit import Chem
    from rdkit.Chem.inchi import MolToInchi
except ImportError:  # pragma: no cover - contracts remain fail-closed
    Chem = None
    MolToInchi = None

PROTON_METAL_ID = 68
HYDROXIDE_LIGAND_ID = 10076
NOT_DEFINED = "Not defined"


# ═══════════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════════

def build_components_from_ids_json(
    *,
    ids_json_path: str | Path,
    output_json_path: str | Path | None = None,
    metal_total: float | str = NOT_DEFINED,
    ligand_total: float | str = NOT_DEFINED,
    ligand_component_contracts: dict[int, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the ``components`` section from the minimal IDs JSON.

    Parameters
    ----------
    ids_json_path : path to the small ID JSON produced by the first agent
    output_json_path : optional path to write the components JSON
    metal_total : explicitly declared total concentration for non-proton
        metals, or the literal ``"Not defined"`` placeholder.  The
        reference-card builder intentionally does not invent a calculation
        concentration.
    ligand_total : explicitly declared total concentration for
        non-hydroxide ligands, or ``"Not defined"``.
    ligand_component_contracts : optional explicit, provenance-bearing
        free-ligand declarations from the active system catalog. They are
        consulted only after SRD-46 HxL, pKa, and figure declarations.
    """
    ids_payload = _read_json(ids_json_path)

    components: dict[str, Any] = {}

    components["H+"] = _build_proton_component()
    components["OH-"] = _build_hydroxide_component()

    metal_entries = sorted(
        ids_payload.get("metals", []),
        key=lambda item: int(item["metal_id"]),
    )
    ligand_entries = sorted(
        ids_payload.get("ligands", []),
        key=lambda item: int(item["ligand_id"]),
    )

    next_metal_index = 2
    for item in metal_entries:
        metal_id = int(item["metal_id"])
        if metal_id == PROTON_METAL_ID:
            continue
        row = _fetch_metal_row(metal_id)
        display_name = _metal_display_name_from_row(row, metal_id)
        components[display_name] = _build_metal_component(
            metal_id=metal_id,
            row=row,
            spec_id=f"M{next_metal_index - 1}",
            total=metal_total,
        )
        next_metal_index += 1

    next_ligand_index = 2
    for item in ligand_entries:
        ligand_id = int(item["ligand_id"])
        if ligand_id == HYDROXIDE_LIGAND_ID:
            continue
        ligand_row = _fetch_ligand_row(ligand_id)
        display_name = _ligand_display_name_from_row(ligand_row, ligand_id)
        components[display_name] = _build_ligand_component(
            ligand_id=ligand_id,
            ligand_row=ligand_row,
            spec_id=f"L{next_ligand_index - 1}",
            total=ligand_total,
            free_ligand_state_contract=(
                (ligand_component_contracts or {}).get(ligand_id)
                or (ligand_component_contracts or {}).get(str(ligand_id))
            ),
        )
        next_ligand_index += 1

    payload = {"components": components}
    if output_json_path is not None:
        _write_json(output_json_path, payload)
    return payload


# ═══════════════════════════════════════════════════════════════════
#  Component template builders
# ═══════════════════════════════════════════════════════════════════

def _build_proton_component() -> dict[str, Any]:
    return {
        "spec_id": "H",
        "type": "metal",
        "total": "auto",
        "charge": 1,
        "reference": {
            "source": "NIST SRD-46",
            "source_database_ID": f"metal_{PROTON_METAL_ID}",
        },
    }


def _build_hydroxide_component() -> dict[str, Any]:
    return {
        "spec_id": "OH",
        "type": "ligand",
        "total": "auto",
        "charge": -1,
        "reference": {
            "source": "NIST SRD-46",
            "source_database_ID": f"ligand_{HYDROXIDE_LIGAND_ID}",
        },
        "ligand_canonical_HOL": {"H": 0, "O": 0, "L": 1},
    }


def _build_metal_component(
    *,
    metal_id: int,
    row: dict[str, Any],
    spec_id: str,
    total: float | str,
) -> dict[str, Any]:
    return {
        "spec_id": spec_id,
        "type": "metal",
        "total": total,
        "charge": _required_integer(
            row.get("charge"), field="charge", context=f"metal_{metal_id}"),
        "reference": {
            "source": "NIST SRD-46",
            "source_database_ID": f"metal_{metal_id}",
            "name": row.get("metal_name"),
            "smiles": row.get("smiles"),
            "inchi": row.get("inchi"),
        },
    }


def _build_ligand_component(
    *,
    ligand_id: int,
    ligand_row: dict[str, Any],
    spec_id: str,
    total: float | str,
    free_ligand_state_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    canonical_hol = _canonical_hol_from_brackets(ligand_id, ligand_row)
    contract = _validate_free_ligand_state_contract(
        ligand_id=ligand_id,
        contract=free_ligand_state_contract,
    )
    if canonical_hol is None:
        if contract is None:
            raise ValueError(
                f"ligand_{ligand_id} has no explicit canonical HxL/HOL state")
        canonical_hol = str(contract["canonical_HOL"])
        ligand_charge = int(contract["charge"])
    else:
        ligand_charge = _ligand_charge_from_brackets(
            ligand_id,
            ligand_row=ligand_row,
        )
        if contract is not None and (
            canonical_hol != contract["canonical_HOL"]
            or ligand_charge != contract["charge"]
        ):
            raise ValueError(
                f"ligand_{ligand_id} catalog free-ligand state conflicts with "
                "the SRD-46 reference state"
            )
    db_hol_series = _db_hol_series(ligand_row, ligand_id=ligand_id)
    if not db_hol_series:
        db_hol_series = [canonical_hol]

    component: dict[str, Any] = {
        "spec_id": spec_id,
        "type": "ligand",
        "total": total,
        "charge": ligand_charge,
        "reference": {
            "source": "NIST SRD-46",
            "source_database_ID": f"ligand_{ligand_id}",
            "name": ligand_row.get("ligand_name"),
            "smiles": ligand_row.get("smiles"),
            "inchi": ligand_row.get("inchi"),
            "figure_definition": ligand_row.get(
                "ligand_figure_definition"
            ),
            "canonical_HOL_series": db_hol_series,
        },
        "ligand_canonical_HOL": _hol_to_dict(canonical_hol),
    }
    if canonical_hol is not None:
        component["HOL"] = canonical_hol
    if contract is not None:
        component["reference"]["catalog_free_ligand_state"] = contract
    return component


def _validate_free_ligand_state_contract(
    *,
    ligand_id: int,
    contract: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if contract is None:
        return None
    if not isinstance(contract, dict):
        raise ValueError(f"ligand_{ligand_id} free_ligand_state must be an object")
    expected_keys = {
        "canonical_HOL",
        "charge",
        "reference_state_classification",
        "provenance",
        "derivation",
        "receipt_sha256",
    }
    if set(contract) != expected_keys:
        raise ValueError(
            f"ligand_{ligand_id} free_ligand_state fields must be exactly "
            f"{sorted(expected_keys)}"
        )
    unsigned = dict(contract)
    receipt = str(unsigned.pop("receipt_sha256") or "")
    actual_receipt = hashlib.sha256(json.dumps(
        unsigned,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")).hexdigest()
    if receipt != actual_receipt:
        raise ValueError(
            f"ligand_{ligand_id} free_ligand_state receipt does not verify"
        )
    hol = _validated_hol_label(
        str(contract["canonical_HOL"]), ligand_id=ligand_id
    )
    if hol != "L":
        raise ValueError(
            f"ligand_{ligand_id} catalog fallback may declare only canonical L"
        )
    charge = _required_integer(
        contract["charge"], field="charge",
        context=f"ligand_{ligand_id} free_ligand_state",
    )
    if charge != 0 or contract["reference_state_classification"] != (
        "neutral_nonprotic_free_ligand/v1"
    ):
        raise ValueError(
            f"ligand_{ligand_id} catalog fallback must be the neutral, "
            "nonprotic v1 contract"
        )
    provenance = contract["provenance"]
    derivation = contract["derivation"]
    if not isinstance(provenance, dict) or not isinstance(derivation, dict):
        raise ValueError(
            f"ligand_{ligand_id} free_ligand_state provenance and derivation "
            "must be objects"
        )
    required_provenance = {
        "kind", "source_database_ID", "compound_id", "query_name",
        "resolved_iupac_name", "canonical_smiles", "inchi",
        "source_payload_sha256", "identity_binding",
    }
    if set(provenance) != required_provenance:
        raise ValueError(
            f"ligand_{ligand_id} free_ligand_state provenance fields must be "
            f"exactly {sorted(required_provenance)}"
        )
    if provenance["kind"] != "PubChem" or (
        isinstance(provenance["compound_id"], bool)
        or not isinstance(provenance["compound_id"], int)
        or provenance["compound_id"] <= 0
    ):
        raise ValueError(
            f"ligand_{ligand_id} free_ligand_state needs a positive PubChem CID"
        )
    if provenance["source_database_ID"] != f"ligand_{ligand_id}":
        raise ValueError(
            f"ligand_{ligand_id} free_ligand_state is bound to a different "
            "SRD-46 ligand ID"
        )
    if re.fullmatch(
        r"[0-9a-f]{64}", str(provenance["source_payload_sha256"])
    ) is None:
        raise ValueError(
            f"ligand_{ligand_id} free_ligand_state has an invalid source "
            "payload digest"
        )
    for field_name in ("query_name", "canonical_smiles", "inchi", "identity_binding"):
        if not isinstance(provenance[field_name], str) or not provenance[field_name].strip():
            raise ValueError(
                f"ligand_{ligand_id} free_ligand_state provenance "
                f"{field_name!r} is missing"
            )
    expected_derivation = {
        "rule": "pubchem_rdkit_neutral_nonprotic_free_ligand/v1",
        "formal_charge_method": "RDKit Chem.GetFormalCharge",
        "nonprotic_check": "no non-carbon heteroatom bears hydrogen",
    }
    if derivation != expected_derivation:
        raise ValueError(
            f"ligand_{ligand_id} free_ligand_state derivation is unsupported"
        )
    if Chem is None or MolToInchi is None:
        raise ValueError(
            f"ligand_{ligand_id} free_ligand_state requires RDKit validation"
        )
    molecule = Chem.MolFromSmiles(provenance["canonical_smiles"])
    if molecule is None or Chem.MolToSmiles(molecule) != provenance["canonical_smiles"]:
        raise ValueError(
            f"ligand_{ligand_id} free_ligand_state SMILES is not canonical"
        )
    if MolToInchi(molecule) != provenance["inchi"]:
        raise ValueError(
            f"ligand_{ligand_id} free_ligand_state InChI does not match SMILES"
        )
    if Chem.GetFormalCharge(molecule) != charge or any(
        atom.GetAtomicNum() not in {1, 6}
        and atom.GetTotalNumHs(includeNeighbors=True) > 0
        for atom in molecule.GetAtoms()
    ):
        raise ValueError(
            f"ligand_{ligand_id} free_ligand_state is not neutral nonprotic"
        )
    return dict(contract)


# ═══════════════════════════════════════════════════════════════════
#  DB fetch helpers
# ═══════════════════════════════════════════════════════════════════

def _fetch_metal_row(metal_id: int) -> dict[str, Any]:
    rows = _search_metals(metal_id=metal_id, limit=1)
    if not rows:
        raise ValueError(f"metal_id {metal_id} not found in SRD-46")
    return rows[0]


def _fetch_ligand_row(ligand_id: int) -> dict[str, Any]:
    result = _search_ligands(ligand_id=ligand_id, limit=1)
    # New API returns dict with 'results' key
    if isinstance(result, dict):
        rows = result.get("results", [])
    else:
        rows = result
    if not rows:
        raise ValueError(f"ligand_id {ligand_id} not found in SRD-46")
    return rows[0]


# ═══════════════════════════════════════════════════════════════════
#  HOL / pKa helpers
# ═══════════════════════════════════════════════════════════════════

def _canonical_hol_from_brackets(ligand_id: int, ligand_row: dict[str, Any]) -> str | None:
    # Prefer the authoritative HxL definition from the ligand card table
    hxl_def = ligand_row.get("ligand_HxL_definition")
    if hxl_def and str(hxl_def).strip() != "***":
        return _validated_hol_label(str(hxl_def), ligand_id=ligand_id)
    # Last resort when the card has no definition: the MOST protonated
    # bracket by HOL rank, measured or estimated alike (a guess at the drawn
    # form, not a derivation).  A label outside the HxL grammar never
    # outranks an HxL form and, when it is all there is, fails the
    # validation below exactly as a bad declaration would.
    brackets = [b for b in ligand_row.get("pka_brackets", []) if isinstance(b, dict)]
    if not brackets:
        explicit_free_state = _explicit_free_ligand_state(ligand_row)
        return "L" if explicit_free_state is not None else None
    best = min(
        brackets,
        key=lambda item: _hol_rank(
            _required_state_label(item, ligand_id=ligand_id),
        ),
    )
    value = _required_state_label(best, ligand_id=ligand_id)
    return _validated_hol_label(value, ligand_id=ligand_id)


def _ligand_charge_from_brackets(
    ligand_id: int,
    *,
    ligand_row: dict[str, Any] | None = None,
) -> int:
    """Charge of the free ligand ``L`` exactly as SRD-46 writes its equilibria.

    SRD-46's own declaration comes first; the Qupkake estimate is the last
    resort (it is a placeholder ``Q0 (-inf, +inf) charge 0`` for every ligand,
    so taking it first made strong-acid anions such as chloride neutral):

    1. the measured pKa states (``is_estimated = 0``): every state gives
       ``charge - protons(HxL_form)`` and all of them must agree;
    2. the ligand card's declared figure form (``figure_definition``: ``L``,
       ``L/-``, ``HL``, ``H2L/+`` ...) with the charge of that form read from
       the card ``formula`` (``Cl1/-`` -> -1, ``C7H11N2+`` -> +1, no token ->
       neutral) or, without a formula, from the figure's own charge token;
    3. the estimated (Qupkake) states: the least charge, as before;

    otherwise a hard error.  ``ligand_row`` is the ``search_ligands`` row; when
    it is not given the declaration is read from the ``ligand_card`` table.
    """
    with get_cards_db() as conn:
        rows = conn.execute(
            """
            SELECT state_id, charge, HxL_form, is_estimated
            FROM ligand_pka_bracket
            WHERE ligand_id = ?
            ORDER BY is_estimated, bracket_id
            """,
            (ligand_id,),
        ).fetchall()
        card = ligand_row
        if card is None:
            found = conn.execute(
                "SELECT figure_definition, formula FROM ligand_card WHERE ligand_id = ?",
                (ligand_id,),
            ).fetchone()
            card = {
                "ligand_figure_definition": found["figure_definition"],
                "formula": found["formula"],
            } if found is not None else {}

    parsed = [dict(row) for row in rows]
    for row in parsed:
        flag = _required_integer(
            row.get("is_estimated"), field="is_estimated",
            context=f"ligand_{ligand_id} pKa state")
        if flag not in {0, 1}:
            raise ValueError(
                f"ligand_{ligand_id} pKa is_estimated must be 0 or 1")
        row["is_estimated"] = flag
        if row.get("charge") is not None:
            row["charge"] = _required_integer(
                row["charge"], field="charge",
                context=f"ligand_{ligand_id} pKa state")

    measured = [row for row in parsed if row["is_estimated"] == 0]
    derived: dict[int, list[str]] = {}
    for row in measured:
        if row.get("charge") is None:
            continue
        label = _required_state_label(row, ligand_id=ligand_id)
        protons = _state_proton_count(label)
        if protons is None:
            raise ValueError(
                f"ligand_{ligand_id} measured pKa state label {label!r} "
                "is not an HxL form")
        derived.setdefault(int(row["charge"]) - protons, []).append(label)
    if len(derived) > 1:
        raise ValueError(
            f"ligand_{ligand_id} measured pKa states disagree on the free "
            f"ligand charge: {derived}")
    if derived:
        return next(iter(derived))

    declared = _declared_free_ligand_charge(card)
    if declared is not None:
        return declared

    estimated = [row for row in parsed if row["is_estimated"] == 1]
    if estimated:
        if any(row.get("charge") is None for row in estimated):
            raise ValueError(f"ligand_{ligand_id} estimated pKa state has no charge")
        best = min(estimated, key=lambda row: row["charge"])
        return int(best["charge"])

    raise ValueError(
        f"ligand_{ligand_id} has neither a pKa state nor an explicit "
        "unprotonated L charge declaration")


_FIGURE_FORM_RE = re.compile(r"(?P<form>H-?\d*L|L)(?:/?(?P<charge>\d*[+-]+))?")
_CHARGE_TOKEN_RE = re.compile(r"(?P<digits>\d*)(?P<signs>[+-]+)")
_FORMULA_CHARGE_RE = re.compile(
    r"(?P<body>[A-Za-z][A-Za-z0-9().\[\]]*?)"
    r"(?:/(?P<slash>\d*[+-]+)|(?P<bare>[+-]+))?"
)


def _charge_token_value(
    token: str | None,
    *,
    digits_allowed: bool = True,
) -> int | None:
    """``'-'`` -> -1, ``'2-'`` -> -2, ``'++'`` -> 2, ``''`` -> 0; mixed signs -> None.

    With ``digits_allowed=False`` the digits are not a magnitude (in a bare
    ``C7H7N1O2+`` they belong to the element count) and only the signs count.
    """
    if token is None or token == "":
        return 0
    match = _CHARGE_TOKEN_RE.fullmatch(token)
    if match is None or len(set(match.group("signs"))) != 1:
        return None
    digits = match.group("digits")
    magnitude = (
        int(digits) if digits and digits_allowed
        else len(match.group("signs"))
    )
    return magnitude if match.group("signs")[0] == "+" else -magnitude


def _state_proton_count(label: str) -> int | None:
    """Protons of an HxL state label; None when the label is not one.

    ``L`` / ``H0L`` -> 0, ``HL`` / ``H1L`` -> 1, ``H2L`` -> 2, ``H-1L`` -> -1.
    """
    token = re.sub(r"\s+", "", str(label or ""))
    if token == "L":
        return 0
    match = re.fullmatch(r"H(?P<count>-?\d+)?L", token)
    if match is None:
        return None
    count = match.group("count")
    return 1 if count is None else int(count)


def _formula_charge(formula: Any) -> int | None:
    """Charge of an SRD-46 card formula; None when there is no formula.

    ``Cl1/-`` -> -1, ``H1O1/-`` -> -1, ``X/2-`` -> -2, ``C7H11N2+`` -> +1 (a
    bare trailing sign run: the digits before it are the element count),
    ``C2H4O2`` -> 0 (no token means neutral).
    """
    text = re.sub(r"\s+", "", str(formula or ""))
    if not text:
        return None
    match = _FORMULA_CHARGE_RE.fullmatch(text)
    if match is None:
        return None
    if match.group("slash") is not None:
        return _charge_token_value(match.group("slash"))
    if match.group("bare") is not None:
        return _charge_token_value(match.group("bare"), digits_allowed=False)
    return 0


def _declared_free_ligand_charge(ligand_row: dict[str, Any]) -> int | None:
    """Charge of ``L`` from the ligand card's own declaration.

    The ``figure_definition`` names the form SRD-46 draws (``HL``, ``L/-``,
    ``H2L/+`` ...); the charge of that form is the card ``formula``'s token
    (the figure token is missing in a few pyridinium cards, the formula's
    never is) or, without a formula, the figure's own token.  ``L`` is that
    form less its protons.  None when the card declares no figure form
    (``***`` placeholders).
    """
    raw_figure = ligand_row.get("ligand_figure_definition")
    if raw_figure is None:
        return None
    match = _FIGURE_FORM_RE.fullmatch(re.sub(r"\s+", "", str(raw_figure)))
    if match is None:
        return None
    protons = _state_proton_count(match.group("form"))
    if protons is None:
        return None
    form_charge = _formula_charge(ligand_row.get("formula"))
    if form_charge is None:
        form_charge = _charge_token_value(match.group("charge") or "")
    if form_charge is None:
        return None
    return form_charge - protons


def _explicit_free_ligand_state(ligand_row: dict[str, Any]) -> int | None:
    """Return the charge of an explicitly declared free ``L`` state.

    Some non-protonatable SRD-46 ligands have no H+/ligand network and no
    pKa brackets.  Their ligand card instead declares the reference state in
    ``figure_definition`` (for example chloride is ``L/-``).  Only a literal
    unprotonated ``L`` declaration is accepted here; placeholders such as
    ``***`` and protonated declarations such as ``HL`` remain hard errors.
    """
    raw = ligand_row.get("ligand_figure_definition")
    if raw is None:
        return None
    token = re.sub(r"\s+", "", str(raw))
    match = re.fullmatch(
        r"L(?:/)?(?P<charge>(?:\d+[+-]|[+-]+))?",
        token,
    )
    if match is None:
        return None
    charge_token = match.group("charge")
    if not charge_token:
        return 0
    sign = 1 if charge_token.endswith("+") else -1
    magnitude_text = charge_token[:-1]
    magnitude = (
        int(magnitude_text)
        if magnitude_text.isdigit()
        else len(charge_token)
    )
    return sign * magnitude


def _hol_to_dict(hol: str | None) -> dict[str, int]:
    if not hol:
        raise ValueError("ligand canonical HOL is Not defined")
    return {
        "H": _hol_proton_count(hol),
        "O": _hol_oxygen_count(hol),
        "L": 1,
    }


def _required_state_label(row: dict[str, Any], *, ligand_id: int) -> str:
    value = row.get("HxL_form") or row.get("state_id")
    if value is None or not str(value).strip():
        raise ValueError(f"ligand_{ligand_id} pKa state has no HxL/state label")
    return str(value).strip()


def _validated_hol_label(label: str, *, ligand_id: int) -> str:
    normalized = _normalize_hol_label(label)
    if re.fullmatch(r"(?:L|HL|H\d+L)", normalized) is None:
        raise ValueError(
            f"ligand_{ligand_id} canonical HxL/HOL declaration "
            f"{label!r} is invalid"
        )
    return normalized


def _required_integer(value: Any, *, field: str, context: str) -> int:
    if value is None or value == NOT_DEFINED or isinstance(value, bool):
        raise ValueError(f"{context} field {field!r} is Not defined")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context} field {field!r} must be numeric") from exc
    if not math.isfinite(number) or not number.is_integer():
        raise ValueError(f"{context} field {field!r} must be a finite integer")
    return int(number)


def _normalize_hol_label(label: str) -> str:
    label = label.strip()
    if label in {"L", "H0L"}:
        return "L"
    label = label.replace("H1L", "HL")
    return label


def _hol_rank(label: str) -> tuple[int, int]:
    """Sort key of a bracket label in a HOL series: the most protonated first.

    ``(0, -x)`` for an ``HxL`` form, ``x`` the signed proton count of
    :func:`_hol_proton_count`; ``(1, 0)`` for a label outside the grammar
    (SRD-46 writes ``H0L0`` on its Qupkake placeholder states), so such a
    label sorts after every HxL form and is carried as written.  The
    ORDERING is lenient; the canonical pick (:func:`_validated_hol_label`),
    the HOL dict (:func:`_hol_to_dict`) and the charge rule
    (:func:`_ligand_charge_from_brackets`) stay strict.
    """
    protons = _state_proton_count(_normalize_hol_label(label))
    if protons is None:
        return (1, 0)
    return (0, -protons)


def _hol_proton_count(label: str) -> int:
    """Protons ``x`` of an ``HxL`` label, counted against the ligand's canonical ``L``.

    SRD-46 writes every ligand state relative to the canonical free form
    ``L`` of the ligand card (``definition_HxL``), so ``x`` is a signed proton
    count and never a charge: ``L`` / ``H0L`` -> 0, ``HL`` / ``H1L`` -> 1,
    ``H2L`` -> 2 and the deprotonated ``H-1L`` -> -1 (one proton fewer than
    the canonical form).  The same grammar as :func:`_state_proton_count`;
    a label outside it is a hard error, never a silent count.
    """
    protons = _state_proton_count(label)
    if protons is None:
        raise ValueError(f"HxL/HOL label {label!r} is not an HxL form")
    return protons


def _hol_oxygen_count(label: str) -> int:
    if "OH" in label:
        return 1
    match = re.search(r"O(\d*)", label)
    if not match:
        return 0
    return int(match.group(1)) if match.group(1) else 1


def _db_hol_series(
    ligand_row: dict[str, Any],
    *,
    ligand_id: int,
) -> list[str]:
    brackets = list(ligand_row.get("pka_brackets", []))
    normalized: list[dict[str, Any]] = []
    for bracket in brackets:
        if not isinstance(bracket, dict):
            raise ValueError(f"ligand_{ligand_id} pKa bracket must be an object")
        flag = _required_integer(
            bracket.get("is_estimated"), field="is_estimated",
            context=f"ligand_{ligand_id} pKa bracket")
        if flag not in {0, 1}:
            raise ValueError(f"ligand_{ligand_id} pKa is_estimated must be 0 or 1")
        normalized.append({**bracket, "is_estimated": flag})
    non_est = [b for b in normalized if b["is_estimated"] == 0]
    if not non_est:
        non_est = normalized
    non_est.sort(
        key=lambda b: _hol_rank(
            _required_state_label(b, ligand_id=ligand_id),
        ),
    )
    return [
        _required_state_label(b, ligand_id=ligand_id)
        for b in non_est
    ]


def _metal_display_name_from_row(row: dict[str, Any], metal_id: int) -> str:
    raw = row.get("metal_name", f"M{metal_id}")
    return raw.replace("^[", "").replace("]", "")


def _ligand_display_name_from_row(row: dict[str, Any], ligand_id: int) -> str:
    raw = row.get("ligand_name", f"L{ligand_id}")
    m = re.search(r"\(([^)]+)\)\s*$", raw)
    if m:
        return m.group(1)
    return raw


# ═══════════════════════════════════════════════════════════════════
#  JSON I/O — long-path (>260 char) safe with bounded SMB retry
# ═══════════════════════════════════════════════════════════════

def _winlong(path: str | Path) -> str:
    sp = os.fspath(path)
    if os.name != "nt":
        return sp
    ap = os.path.abspath(sp)
    if ap.startswith("\\\\?\\"):
        return ap
    if ap.startswith("\\\\"):                       # UNC share
        return "\\\\?\\UNC\\" + ap[2:]
    return "\\\\?\\" + ap


_SMB_READ_ATTEMPTS = 4
_SMB_READ_BACKOFF_S = (0.2, 0.5, 1.0)


def _read_json(path: str | Path) -> dict[str, Any]:
    # Session eq-map artefacts live on deep network-share run trees where a
    # freshly written file can be transiently invisible to a new handle.
    last_error: OSError | None = None
    for attempt in range(_SMB_READ_ATTEMPTS):
        try:
            with open(_winlong(path), "r", encoding="utf-8") as handle:
                return json.loads(handle.read())
        except (FileNotFoundError, PermissionError, OSError) as exc:
            last_error = exc
            if attempt < _SMB_READ_ATTEMPTS - 1:
                time.sleep(_SMB_READ_BACKOFF_S[attempt])
    assert last_error is not None
    raise last_error


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    os.makedirs(_winlong(target.parent), exist_ok=True)
    with open(_winlong(target), "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2))
        handle.flush()
        os.fsync(handle.fileno())
