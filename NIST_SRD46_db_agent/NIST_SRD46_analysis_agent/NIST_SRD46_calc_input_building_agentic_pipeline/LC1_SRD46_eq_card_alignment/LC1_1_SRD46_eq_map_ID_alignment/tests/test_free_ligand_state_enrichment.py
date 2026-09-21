from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest


_PIPELINE_ROOT = Path(__file__).resolve().parents[3]
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from LC1_SRD46_eq_card_alignment.LC1_1_SRD46_eq_map_ID_alignment import (  # noqa: E402
    id_enrichment_helpers as enrichment,
)


pytestmark = pytest.mark.skipif(
    enrichment.Chem is None or enrichment.MolToInchi is None,
    reason="RDKit is required for free-ligand-state validation",
)


def _resolved_structure(smiles: str, *, cid: int = 6228) -> dict[str, object]:
    molecule = enrichment.Chem.MolFromSmiles(smiles)
    assert molecule is not None
    return {
        "cid": cid,
        "smiles": enrichment.Chem.MolToSmiles(molecule),
        "inchi": enrichment.MolToInchi(molecule),
        "iupac": "N,N-dimethylformamide",
        "source_payload_sha256": "a" * 64,
    }


def _unresolved_dmf_row(*, ligand_id: str = "ligand_11422") -> dict[str, object]:
    return {
        "ligand_id": ligand_id,
        "ligand_name": "N,N-Dimethylformamide (DMF)",
        "ligand_HxL_definition": None,
        "ligand_figure_definition": "***",
        "pka_brackets": [],
        "smiles": None,
    }


def test_dmf_enrichment_emits_verified_exact_id_bound_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = _unresolved_dmf_row()
    resolved = _resolved_structure("CN(C)C=O")
    queries: list[str] = []

    monkeypatch.setattr(enrichment, "safe_ligand_row", lambda _db_id: row)

    def resolve(name: str) -> dict[str, object]:
        queries.append(name)
        return resolved

    monkeypatch.setattr(enrichment, "_resolve_unique_pubchem_structure", resolve)

    [ligand] = enrichment.enrich_ligands([{
        "db_id": "ligand_11422",
        "name": "N,N-Dimethylformamide (DMF)",
    }])
    contract = ligand["free_ligand_state"]

    assert queries == ["N,N-Dimethylformamide (DMF)"]
    assert contract["canonical_HOL"] == "L"
    assert contract["charge"] == 0
    assert contract["provenance"]["source_database_ID"] == "ligand_11422"
    assert contract["provenance"]["canonical_smiles"] == resolved["smiles"]
    unsigned = dict(contract)
    receipt = unsigned.pop("receipt_sha256")
    assert receipt == hashlib.sha256(json.dumps(
        unsigned,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")).hexdigest()


@pytest.mark.parametrize(
    "smiles",
    [
        "CCO",                 # neutral but protic (ethanol)
        "C[N+](C)(C)C",       # nonprotic but charged
    ],
)
def test_protic_or_charged_structure_does_not_authorize_free_ligand_state(
    monkeypatch: pytest.MonkeyPatch,
    smiles: str,
) -> None:
    monkeypatch.setattr(
        enrichment,
        "_resolve_unique_pubchem_structure",
        lambda _name: _resolved_structure(smiles),
    )

    contract = enrichment._resolved_free_ligand_state(
        committed_entry={"db_id": "ligand_11422"},
        ligand_row=_unresolved_dmf_row(),
    )

    assert contract is None


def test_exact_srd46_ligand_id_mismatch_fails_before_external_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_resolver(_name: str) -> dict[str, object]:
        raise AssertionError("identity mismatch must fail before resolution")

    monkeypatch.setattr(
        enrichment,
        "_resolve_unique_pubchem_structure",
        unexpected_resolver,
    )

    contract = enrichment._resolved_free_ligand_state(
        committed_entry={"db_id": "ligand_11423"},
        ligand_row=_unresolved_dmf_row(ligand_id="ligand_11422"),
    )

    assert contract is None


@pytest.mark.parametrize(
    "state_field,state_value",
    [
        ("ligand_HxL_definition", "L"),
        ("pka_brackets", [{"HxL_form": "HL", "is_estimated": 0}]),
        ("ligand_figure_definition", "L"),
    ],
)
def test_explicit_srd46_reference_state_skips_external_resolution(
    monkeypatch: pytest.MonkeyPatch,
    state_field: str,
    state_value: object,
) -> None:
    row = _unresolved_dmf_row()
    row[state_field] = state_value

    def unexpected_resolver(_name: str) -> dict[str, object]:
        raise AssertionError("an SRD-46 reference state must take precedence")

    monkeypatch.setattr(
        enrichment,
        "_resolve_unique_pubchem_structure",
        unexpected_resolver,
    )

    contract = enrichment._resolved_free_ligand_state(
        committed_entry={"db_id": "ligand_11422"},
        ligand_row=row,
    )

    assert contract is None


def test_run_local_cache_hit_is_revalidated_without_resolver_call(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    row = _unresolved_dmf_row()
    resolved = _resolved_structure("CN(C)C=O")
    cache_path = tmp_path / "LC1_1_call_01" / "_temporary" / "cache.json"
    resolver_calls: list[str] = []

    monkeypatch.setattr(enrichment, "safe_ligand_row", lambda _db_id: row)

    def initial_resolver(name: str) -> dict[str, object]:
        resolver_calls.append(name)
        return resolved

    monkeypatch.setattr(
        enrichment,
        "_resolve_unique_pubchem_structure",
        initial_resolver,
    )
    committed = [{
        "db_id": "ligand_11422",
        "name": "N,N-Dimethylformamide (DMF)",
    }]
    first = enrichment.enrich_ligands(
        committed,
        free_ligand_state_cache_path=cache_path,
    )

    def forbidden_resolver(_name: str) -> dict[str, object]:
        raise AssertionError("a validated cache hit must not call PubChem")

    monkeypatch.setattr(
        enrichment,
        "_resolve_unique_pubchem_structure",
        forbidden_resolver,
    )
    second = enrichment.enrich_ligands(
        committed,
        free_ligand_state_cache_path=cache_path,
    )

    assert resolver_calls == ["N,N-Dimethylformamide (DMF)"]
    assert second == first
    cached = json.loads(cache_path.read_text(encoding="utf-8"))
    assert cached["entries"]["ligand_11422"]["ligand_db_id"] == (
        "ligand_11422"
    )
    assert cached["entries"]["ligand_11422"]["canonical_srd_name"] == (
        "N,N-Dimethylformamide (DMF)"
    )


def test_explicit_srd46_state_takes_precedence_over_existing_cache(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cache_path = tmp_path / "cache.json"
    unresolved = _unresolved_dmf_row()
    monkeypatch.setattr(
        enrichment,
        "safe_ligand_row",
        lambda _db_id: unresolved,
    )
    monkeypatch.setattr(
        enrichment,
        "_resolve_unique_pubchem_structure",
        lambda _name: _resolved_structure("CN(C)C=O"),
    )
    committed = [{"db_id": "ligand_11422", "name": "DMF"}]
    enrichment.enrich_ligands(
        committed,
        free_ligand_state_cache_path=cache_path,
    )

    explicit = {**unresolved, "ligand_HxL_definition": "L"}
    monkeypatch.setattr(
        enrichment,
        "safe_ligand_row",
        lambda _db_id: explicit,
    )

    def forbidden_resolver(_name: str) -> dict[str, object]:
        raise AssertionError("explicit SRD-46 state must bypass cache/resolver")

    monkeypatch.setattr(
        enrichment,
        "_resolve_unique_pubchem_structure",
        forbidden_resolver,
    )
    [ligand] = enrichment.enrich_ligands(
        committed,
        free_ligand_state_cache_path=cache_path,
    )

    assert "free_ligand_state" not in ligand


@pytest.mark.parametrize(
    "tamper",
    ["canonical_name", "free_state_receipt", "metadata_receipt"],
)
def test_stale_or_tampered_cache_entry_is_not_reused(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    tamper: str,
) -> None:
    row = _unresolved_dmf_row()
    resolved = _resolved_structure("CN(C)C=O")
    cache_path = tmp_path / "cache.json"
    committed = [{"db_id": "ligand_11422", "name": "DMF"}]
    monkeypatch.setattr(enrichment, "safe_ligand_row", lambda _db_id: row)
    monkeypatch.setattr(
        enrichment,
        "_resolve_unique_pubchem_structure",
        lambda _name: resolved,
    )
    enrichment.enrich_ligands(
        committed,
        free_ligand_state_cache_path=cache_path,
    )
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    entry = cache["entries"]["ligand_11422"]
    if tamper == "canonical_name":
        entry["canonical_srd_name"] = "A different SRD ligand"
    elif tamper == "free_state_receipt":
        entry["free_ligand_state"]["receipt_sha256"] = "0" * 64
    else:
        entry["metadata_overlay"]["receipt_sha256"] = "0" * 64
    cache_path.write_text(json.dumps(cache), encoding="utf-8")
    resolver_calls: list[str] = []

    def repair_resolver(name: str) -> dict[str, object]:
        resolver_calls.append(name)
        return resolved

    monkeypatch.setattr(
        enrichment,
        "_resolve_unique_pubchem_structure",
        repair_resolver,
    )
    [repaired] = enrichment.enrich_ligands(
        committed,
        free_ligand_state_cache_path=cache_path,
    )

    if tamper == "free_state_receipt":
        # The invalid state contract is rebuilt from the independently
        # validated metadata overlay; no second network request is needed.
        assert resolver_calls == []
    else:
        assert resolver_calls == ["N,N-Dimethylformamide (DMF)"]
    assert repaired["free_ligand_state"]["receipt_sha256"] != "0" * 64


def test_duplicate_inputs_coalesce_to_existing_canonical_srd_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = {
        **_unresolved_dmf_row(),
        "ligand_HxL_definition": "L",
    }
    seen_lookups: list[str] = []

    def safe_row(db_id: str) -> dict[str, object]:
        seen_lookups.append(db_id)
        return row

    monkeypatch.setattr(enrichment, "safe_ligand_row", safe_row)
    catalog = enrichment.build_system_catalog(
        {
            "metals": [],
            "ligands": [
                {"db_id": "ligand_011422", "name": "DMF first"},
                {"db_id": "ligand_11422", "name": "DMF duplicate"},
            ],
        },
        water_system=False,
    )

    ligands = catalog["system_catalog"]["chemical_system"]["ligands"]
    assert len(ligands) == 1
    assert ligands[0]["db_id"] == "ligand_11422"
    assert ligands[0]["internal_id"] == "L1"
    assert seen_lookups == ["ligand_11422"]


def test_eg_keeps_srd_figure_and_formula_but_enriches_missing_structure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    row = {
        "ligand_id": "ligand_9621",
        "ligand_name": "Ethane-1,2-diol (Ethylene glycol)",
        "ligand_HxL_definition": None,
        "ligand_figure_definition": "L",
        "formula": "C2H6O2",
        "iupac_name": None,
        "smiles": None,
        "inchi": None,
        "pka_brackets": [],
    }
    resolved = _resolved_structure("OCCO", cid=174)
    resolved["iupac"] = "ethane-1,2-diol"
    resolver_calls: list[str] = []
    monkeypatch.setattr(enrichment, "safe_ligand_row", lambda _db_id: row)

    def resolve(name: str) -> dict[str, object]:
        resolver_calls.append(name)
        return resolved

    monkeypatch.setattr(enrichment, "_resolve_unique_pubchem_structure", resolve)
    cache_path = tmp_path / "LC1_1_call_01" / "_temporary" / "cache.json"
    [ligand] = enrichment.enrich_ligands(
        [{"db_id": "ligand_9621", "name": "EG"}],
        free_ligand_state_cache_path=cache_path,
    )

    assert resolver_calls == ["Ethane-1,2-diol (Ethylene glycol)"]
    assert ligand["db_id"] == "ligand_9621"
    assert ligand["formula"] == "C2H6O2"  # valid SRD value wins
    assert ligand["smiles"] == resolved["smiles"]
    assert ligand["inchi"] == resolved["inchi"]
    assert "free_ligand_state" not in ligand  # explicit SRD figure L wins
    cached = json.loads(cache_path.read_text(encoding="utf-8"))
    assert cached["schema_version"] == (
        "lc1_1_pubchem_ligand_enrichment_cache/v2"
    )
    overlay = cached["entries"]["ligand_9621"]["metadata_overlay"]
    assert overlay["provenance"]["source_database_ID"] == "ligand_9621"
    assert overlay["provenance"]["compound_id"] == 174


def test_dmf_placeholder_formula_is_filled_without_changing_srd_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = {**_unresolved_dmf_row(), "formula": "********", "inchi": None}
    resolved = _resolved_structure("CN(C)C=O", cid=6228)
    monkeypatch.setattr(enrichment, "safe_ligand_row", lambda _db_id: row)
    monkeypatch.setattr(
        enrichment,
        "_resolve_unique_pubchem_structure",
        lambda _name: resolved,
    )

    [ligand] = enrichment.enrich_ligands([
        {"db_id": "ligand_11422", "name": "DMF"},
    ])

    assert ligand["db_id"] == "ligand_11422"
    assert ligand["db_id"] != "ligand_6228"
    assert ligand["formula"] == "C3H7NO"
    assert ligand["smiles"] == resolved["smiles"]
    assert ligand["inchi"] == resolved["inchi"]


def test_acn_complete_srd_structure_does_not_call_pubchem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = {
        "ligand_id": "ligand_9825",
        "ligand_name": "Cyanomethane (Acetonitrile)",
        "ligand_HxL_definition": "L",
        "ligand_figure_definition": "L",
        "formula": "C2H3N1",
        "iupac_name": None,
        "smiles": "CC#N",
        "inchi": "InChI=1S/C2H3N/c1-2-3/h1H3",
        "pka_brackets": [],
    }
    monkeypatch.setattr(enrichment, "safe_ligand_row", lambda _db_id: row)

    def unexpected_resolver(_name: str) -> dict[str, object]:
        raise AssertionError("complete SRD structure must not query PubChem")

    monkeypatch.setattr(
        enrichment,
        "_resolve_unique_pubchem_structure",
        unexpected_resolver,
    )
    [ligand] = enrichment.enrich_ligands([
        {"db_id": "ligand_9825", "name": "ACN"},
    ])

    assert ligand["db_id"] == "ligand_9825"
    assert ligand["formula"] == "C2H3N1"
    assert ligand["smiles"] == "CC#N"
    assert ligand["inchi"] == "InChI=1S/C2H3N/c1-2-3/h1H3"


def test_mismatched_srd_row_cannot_redirect_pubchem_or_component_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = {**_unresolved_dmf_row(ligand_id="ligand_11423")}
    monkeypatch.setattr(enrichment, "safe_ligand_row", lambda _db_id: row)

    def unexpected_resolver(_name: str) -> dict[str, object]:
        raise AssertionError("mismatched SRD row must fail closed")

    monkeypatch.setattr(
        enrichment,
        "_resolve_unique_pubchem_structure",
        unexpected_resolver,
    )
    [ligand] = enrichment.enrich_ligands([
        {"db_id": "ligand_11422", "name": "DMF"},
    ])

    assert ligand == {
        "name": "DMF",
        "db_id": "ligand_11422",
        "internal_id": "L1",
    }


def test_v1_state_cache_is_safely_migrated_to_v2_metadata_envelope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    row = {**_unresolved_dmf_row(), "formula": "***", "inchi": None}
    resolved = _resolved_structure("CN(C)C=O")
    monkeypatch.setattr(enrichment, "safe_ligand_row", lambda _db_id: row)
    monkeypatch.setattr(
        enrichment,
        "_resolve_unique_pubchem_structure",
        lambda _name: resolved,
    )
    committed = [{"db_id": "ligand_11422", "name": "DMF"}]
    [uncached] = enrichment.enrich_ligands(committed)
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(json.dumps({
        "schema_version": "lc1_1_pubchem_free_ligand_cache/v1",
        "entries": {
            "ligand_11422": {
                "ligand_db_id": "ligand_11422",
                "canonical_srd_name": "N,N-Dimethylformamide (DMF)",
                "free_ligand_state": uncached["free_ligand_state"],
            },
        },
    }), encoding="utf-8")

    [migrated] = enrichment.enrich_ligands(
        committed,
        free_ligand_state_cache_path=cache_path,
    )

    assert migrated["db_id"] == "ligand_11422"
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    assert cache["schema_version"] == (
        "lc1_1_pubchem_ligand_enrichment_cache/v2"
    )
    assert "metadata_overlay" in cache["entries"]["ligand_11422"]
    assert "free_ligand_state" in cache["entries"]["ligand_11422"]
