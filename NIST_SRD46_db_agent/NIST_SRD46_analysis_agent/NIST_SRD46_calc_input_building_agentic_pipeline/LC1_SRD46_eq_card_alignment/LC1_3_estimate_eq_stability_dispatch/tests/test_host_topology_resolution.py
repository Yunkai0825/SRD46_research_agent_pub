"""Host-owned mapping of ordinary QueryAgent reactions to SRD-46 topology."""

from __future__ import annotations

from copy import deepcopy

import pytest

from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.parse_speciation_answer.canonical_topology import (  # noqa: E501
    TopologyResolutionError,
    resolve_canonical_topology,
    validate_topology_resolution_receipt,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.parse_speciation_answer.parser_gate_service import (  # noqa: E501
    ParserGateService,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.parse_speciation_answer.parser_working_state import (  # noqa: E501
    ParserWorkingState,
)
from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent.NIST_SRD46_calc_input_building_agentic_pipeline.LC1_SRD46_eq_card_alignment.LC1_3_estimate_eq_stability_dispatch.parse_speciation_answer.srd46_catalog import (  # noqa: E501
    StaticCatalog,
)


BETAS = {
    726: {
        "status": "ok",
        "beta_definition_id": 726,
        "beta_definition_name": "hydrolysis-coupled analogue",
        "equation_python": "[M] + [L] <=> [M(H-1L)] + [H]",
    },
    812: {
        "status": "ok",
        "beta_definition_id": 812,
        "beta_definition_name": "[ML]/[M][L]",
        "equation_python": "[M] + [L] <=> [ML]",
    },
    840: {
        "status": "ok",
        "beta_definition_id": 840,
        "beta_definition_name": "[ML2]/[M][L]^2",
        "equation_python": "[M] + [L]^2 <=> [ML2]",
    },
    956: {
        "status": "ok",
        "beta_definition_id": 956,
        "beta_definition_name": "[M(OH)(H-2L)]/[M(OH)3][L]",
        "equation_python": (
            "[M(OH)3] + [L] <=> [M(OH)(H-2L)] + [H2O]^2"
        ),
    },
}


def _resolve(excerpt: str, *, metal_name: str = "Fe^[2+]") -> dict:
    return resolve_canonical_topology(
        topology_excerpt=excerpt,
        transcript="Recommended entries:\n" + excerpt,
        scope={
            "metal_id": 62,
            "metal_name": metal_name,
            "ligand_id": 9621,
            "ligand_name": "Ethane-1,2-diol (Ethylene glycol)",
        },
        canonical_beta_records=BETAS.values(),
        authorization_context_id="q002",
        answer_sha256="a" * 64,
    )


def test_neutral_ml_prose_maps_to_beta_812_not_956() -> None:
    receipt = _resolve(
        "| Fe2/EG | `Fe^2+ + EG ⇌ Fe(EG)^2+` | logβ1 | 0.3 | ±0.5 |"
    )
    assert receipt["beta_definition_id"] == 812
    assert receipt["equation_python"] == "[M] + [L] <=> [ML]"


def test_neutral_ml2_prose_maps_to_beta_840() -> None:
    receipt = _resolve(
        "| Fe2/EG | `Fe^2+ + 2 EG ⇌ Fe(EG)2^2+` | logβ2 | 0.4 | ±0.8 |"
    )
    assert receipt["beta_definition_id"] == 840
    assert receipt["equation_python"] == "[M] + [L]^2 <=> [ML2]"


def test_fe3_neutral_adduct_rejects_cited_hydrolysis_beta_726() -> None:
    receipt = _resolve(
        "| Fe3/EG | Fe^[3+] + EG ⇌ Fe(EG)^[3+] | -7.1 | ±0.8 |",
        metal_name="Fe^[3+]",
    )
    assert receipt["beta_definition_id"] == 812
    assert receipt["beta_definition_id"] != 726


def test_nonmaterializable_beta_is_not_a_topology_candidate() -> None:
    unavailable = deepcopy(BETAS[812])
    unavailable["status"] = "not_materializable"
    with pytest.raises(TopologyResolutionError, match="no materializable"):
        resolve_canonical_topology(
            topology_excerpt="Fe^2+ + EG ⇌ Fe(EG)^2+",
            transcript="Fe^2+ + EG ⇌ Fe(EG)^2+",
            scope={
                "metal_name": "Fe^[2+]",
                "ligand_name": "Ethane-1,2-diol (Ethylene glycol)",
            },
            canonical_beta_records=[unavailable, BETAS[956]],
            authorization_context_id="q002",
            answer_sha256="a" * 64,
        )


@pytest.mark.parametrize(
    "reaction, expected_beta, observed_beta_ids",
    [
        ("Fe3+ + EG ⇌ Fe(EG)^3+", 812, [726, 956]),
        ("Fe3+ + 2 EG ⇌ Fe(EG)2^3+", 840, []),
    ],
)
def test_parser_gate_uses_global_static_catalog_not_observed_beta_ids(
    tmp_path,
    reaction: str,
    expected_beta: int,
    observed_beta_ids: list[int],
) -> None:
    answer = (
        f"For {reaction}, I estimate log beta = 0.4 with uncertainty 0.8. "
        "The method is analogue transfer. I assume the same reference state. "
        "The rationale is similar donor chemistry, supported by vlm_1."
    )
    state = ParserWorkingState.create(
        query_id="q001",
        scope={
            "metal_id": 63,
            "metal_name": "Fe^[3+]",
            "ligand_id": 9621,
            "ligand_name": "Ethane-1,2-diol (Ethylene glycol)",
        },
        request_T_C=25.0,
        request_I_M=0.0,
        base_eq_map_card={"equilibrium_networks": []},
        initial_answer=answer,
        evidence_snapshot={
            "observed_beta_definition_ids": observed_beta_ids,
            "observed_vlm_ids": [1],
        },
    )
    state.create_draft({
        "constant_value": 0.4,
        "evidence_vlm_ids": [1],
        "uncertainty_log10": 0.8,
        "estimation_method": "analogue transfer",
        "assumptions": ["the same reference state"],
        "rationale": "similar donor chemistry",
        "source_excerpts": {"topology_excerpt": reaction},
    })
    service = ParserGateService(
        state=state,
        base_eq_map_card={"equilibrium_networks": []},
        session_id="test",
        artifact_dir=tmp_path,
        catalog=StaticCatalog(betas=deepcopy(BETAS)),
    )

    report = service.check_draft("d001")

    assert report.status == "pass"
    assert state.drafts["d001"].beta_definition_id == expected_beta
    receipt = state.drafts["d001"].topology_resolution
    assert receipt is not None
    assert receipt["beta_definition_id"] == expected_beta
    assert "candidate_beta_ids_sha256" not in receipt


@pytest.mark.parametrize(
    "metal_rendering",
    ["Fe3+", "Fe³⁺", "Fe+++", "Fe3+(aq)"],
)
def test_common_bare_metal_charge_renderings_resolve_to_ml(
    metal_rendering: str,
) -> None:
    receipt = _resolve(
        f"{metal_rendering} + EG ⇌ Fe(EG)^3+",
        metal_name="Fe^[3+]",
    )
    assert receipt["beta_definition_id"] == 812


def test_complex_charge_does_not_consume_ligand_stoichiometry() -> None:
    receipt = _resolve(
        "Fe3+ + 2 EG ⇌ Fe(EG)2+",
        metal_name="Fe^[3+]",
    )
    assert receipt["beta_definition_id"] == 840


def test_persisted_topology_receipt_is_tamper_evident() -> None:
    receipt = _resolve("Fe^2+ + EG ⇌ Fe(EG)^2+")
    validate_topology_resolution_receipt(
        receipt,
        beta_definition_id=812,
        beta_definition_name="[ML]/[M][L]",
        equation_python="[M] + [L] <=> [ML]",
        query_id="q002",
        answer_sha256="a" * 64,
    )
    tampered = deepcopy(receipt)
    tampered["beta_definition_id"] = 956
    with pytest.raises(TopologyResolutionError, match="receipt digest"):
        validate_topology_resolution_receipt(
            tampered,
            beta_definition_id=956,
            beta_definition_name="[ML]/[M][L]",
            equation_python="[M] + [L] <=> [ML]",
            query_id="q002",
            answer_sha256="a" * 64,
        )
