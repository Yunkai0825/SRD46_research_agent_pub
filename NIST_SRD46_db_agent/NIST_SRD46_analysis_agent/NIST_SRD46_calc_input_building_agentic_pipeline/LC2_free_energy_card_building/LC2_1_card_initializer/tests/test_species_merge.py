from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


_THIS = Path(__file__).absolute()
_PIPELINE_ROOT = _THIS.parents[3]
_ANALYSIS_ROOT = _THIS.parents[4]
_CORE_ROOT = _ANALYSIS_ROOT / "NIST_SRD46_core_numcalc_pipeline"
_MERGER_ROOT = _THIS.parents[1] / "ref_eq_SRD46_md_cards_merger"
_BUILDER_ROOT = _THIS.parents[1] / "ref_eq_SRD46_md_cards_builder"
for _path in (_PIPELINE_ROOT, _ANALYSIS_ROOT, _CORE_ROOT, _MERGER_ROOT,
              _BUILDER_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from species_concatenator import concatenate_species  # noqa: E402
from thermodynamics_helpers.gibbs_value_calc_from_logK_eq_map_helpers.free_energy_network_calc_helper import (  # noqa: E402,E501
    SpeciesEnergy,
)


def _solid(species_id: str, label: str, vlm_id: str, mu0: float) -> SpeciesEnergy:
    return SpeciesEnergy(
        species_id=species_id,
        original_id=species_id,
        label=label,
        stoich={"M1": 1, "H": -3},
        charge=0,
        phase="dissolution",
        log_beta=-10.0,
        app_log_beta=-10.0,
        mu0_free=mu0,
        mu0_canonical=mu0,
        mu_aligned=mu0,
        vlm_id=vlm_id,
    )


def test_same_formula_solids_with_distinct_species_ids_are_preserved():
    hematite = _solid("[M1].[H-3].[z+0(s)][1]", "hematite", "vlm_170828", 1.0)
    hydroxide = _solid("[M1].[H-3].[z+0(s)][2]", "Fe(OH)3", "vlm_170825", 2.0)

    merged, collisions = concatenate_species(
        [SimpleNamespace(species=[hematite, hydroxide])],
        [{}],
    )

    assert [item.vlm_id for item in merged] == ["vlm_170828", "vlm_170825"]
    assert collisions == []


def test_repeated_dependency_copies_are_collapsed_by_stable_identity():
    first = [
        _solid("solid[1]", "hematite", "vlm_170828", 1.0),
        _solid("solid[2]", "Fe(OH)3", "vlm_170825", 2.0),
    ]
    second = [
        _solid("solid[1]", "hematite", "vlm_170828", 1.0),
        _solid("solid[2]", "Fe(OH)3", "vlm_170825", 2.0),
    ]

    merged, collisions = concatenate_species(
        [SimpleNamespace(species=first), SimpleNamespace(species=second)],
        [{}, {}],
    )

    assert len(merged) == 2
    assert collisions == []


def test_conflicting_payloads_keep_both_copies_tagged_for_lc2_3():
    first = _solid("solid", "hematite", "vlm_170828", 1.0)
    conflicting = _solid("solid", "hematite", "vlm_170828", 9.0)

    provenances = [
        {"card": "pair_A", "T_C": 25.0, "I_M": 0.1, "factor": 5.7077},
        {"card": "pair_B", "T_C": 20.0, "I_M": 4.0, "factor": 5.6120},
    ]
    merged, collisions = concatenate_species(
        [SimpleNamespace(species=[first]),
         SimpleNamespace(species=[conflicting])],
        [{}, {}],
        provenances,
    )

    assert len(merged) == 2
    # log_beta ties -> higher frame T ranks first (pair_A, 25C).
    assert [s.species_id for s in merged] == ["solid.dup1", "solid.dup2"]
    assert merged[0].label == "hematite @25C"
    assert merged[1].label == "hematite @20C"
    assert merged[0].additional_notes == "[srd_1 1/2 frame]"
    assert merged[1].additional_notes == "[srd_1 2/2 frame]"

    assert len(collisions) == 1
    record = collisions[0]
    assert record["set_id"] == "srd_1"
    assert record["identity"]["species_id"] == "solid"
    assert record["kind"] == "frame"           # same vlm_id + log_beta
    assert [c["card"] for c in record["copies"]] == ["pair_A", "pair_B"]
    # Verbose provenance lives in the sidecar record, not the card note.
    assert record["copies"][0]["T_C"] == 25.0
    assert record["copies"][0]["vlm_id"] == "vlm_170828"


def test_different_vlm_records_marked_kind_data():
    first = _solid("solid", "hematite", "vlm_170828", 1.0)
    conflicting = _solid("solid", "hematite", "vlm_999999", 9.0)

    merged, collisions = concatenate_species(
        [SimpleNamespace(species=[first]),
         SimpleNamespace(species=[conflicting])],
        [{}, {}],
    )

    assert len(merged) == 2
    assert len(collisions) == 1
    assert collisions[0]["kind"] == "data"    # different SRD records
    assert merged[0].additional_notes == "[srd_1 1/2 data]"
    assert merged[1].additional_notes == "[srd_1 2/2 data]"
    assert {c["vlm_id"] for c in collisions[0]["copies"]} == {
        "vlm_170828", "vlm_999999",
    }


def test_solid_dup_id_suffix_and_tokenizer_roundtrip():
    first = _solid("M1.H-3.z+0(s)", "Fe(OH)3(s)", "vlm_1", 1.0)
    conflicting = _solid("M1.H-3.z+0(s)", "Fe(OH)3(s)", "vlm_1", 2.0)

    merged, collisions = concatenate_species(
        [SimpleNamespace(species=[first]),
         SimpleNamespace(species=[conflicting])],
        [{}, {}],
    )

    assert [s.species_id for s in merged] == [
        "M1.H-3.z+0.dup1(s)", "M1.H-3.z+0.dup2(s)",
    ]
    assert len(collisions) == 1

    from ref_eq_free_energy_md_card_generation import (  # noqa: E402
        _tokenize_species_id,
    )
    from card_management_helpers.free_energy_md_card_reader import (  # noqa: E402
        _detokenize_species_id,
    )
    for sid in ("M1.OH.z+0.dup1", "M1.H-3.z+0.dup2(s)"):
        assert _detokenize_species_id(_tokenize_species_id(sid)) == sid
