# SRD-46 outputs before topology cleanup

This folder restores the latest recoverable pre-fix output for each of 33 prompt IDs: six August 30-31 diagnostic runs and 27 June 9 benchmark runs. It is a collection of historical runs, not one new batch.

The original questions, answers, figures, solver data, cards, logs and available checkpoints are copied byte for byte. Outer run folders use `ID_YYYYMMDD`, with the original run start date from `run_history.jsonl` in America/Chicago time. Embedded original absolute paths are preserved. No model, solver or plotter was run for this restoration.

Every restored file was checked against its saved recovery SHA-256 and checked again after copying. RESTORATION_MANIFEST.json records the source mapping, file inventory and hashes.

The historical recovery cutoff is September 3, 2026, 00:00 America/Chicago. The topology fixer first appears in Git commit bdf50547f (September 8); that commit date is not treated as its exact deployment date. The selected source runs precede the cutoff, and none of their saved topology metadata records an applied topology fix.

## Coverage and limitations

- 33 prompt folders are present; 32 contain a final answer in its original Markdown or HTML format.
- L3_6 is an incomplete historical run and has no final answer; its available artifacts are preserved.
- L1_4 and L1_10 retain original August HTML answers. A later edited Markdown answer is not substituted.
- L1_7 predates the added hydroxide-preference instruction. L4_5 asks about Unobtainium, not the later Cuprium prompt.
- These historical answers are not assumed identical to current benchmark or October-November answers. Each answer is unchanged from its selected cache.
- The two _batch_summary_20260609_*.json files are original June batch summaries; they do not summarize this combined collection.

## Restored outputs

| ID | Run folder | Source period | Original folder | Final answer |
|---|---|---|---|---|
| FF_1 | [`FF_1_20260831`](FF_1_20260831/) | August 30-31 diagnostic run | FF_1_Fe_mixed_solvent_speciation | [answer.md](FF_1_20260831/answer.md) |
| L1_1 | [`L1_1_20260609`](L1_1_20260609/) | June 9 benchmark run | L1_1_Ni_glycine_pourbaix_2D | [answer.md](L1_1_20260609/answer.md) |
| L1_2 | [`L1_2_20260609`](L1_2_20260609/) | June 9 benchmark run | L1_2_FeCu_citrate_chloride_joint | [answer.md](L1_2_20260609/answer.md) |
| L1_3 | [`L1_3_20260830`](L1_3_20260830/) | August 30-31 diagnostic run | L1_3_Cu_ammonia_pourbaix_2D | [answer.md](L1_3_20260830/answer.md) |
| L1_4 | [`L1_4_20260830`](L1_4_20260830/) | August 30-31 diagnostic run | L1_4_Fe_EDTA_vs_citrate | [answer.html](L1_4_20260830/answer.html) |
| L1_5 | [`L1_5_20260609`](L1_5_20260609/) | June 9 benchmark run | L1_5_Cu_EDTA_vs_NTA | [answer.md](L1_5_20260609/answer.md) |
| L1_6 | [`L1_6_20260609`](L1_6_20260609/) | June 9 benchmark run | L1_6_Cu_vs_Ag_chloride_redox | [answer.md](L1_6_20260609/answer.md) |
| L1_7 | [`L1_7_20260609`](L1_7_20260609/) | June 9 benchmark run | L1_7_CuZn_glycine_ammonia_joint | [answer.md](L1_7_20260609/answer.md) |
| L1_8 | [`L1_8_20260609`](L1_8_20260609/) | June 9 benchmark run | L1_8_CuZnFe_chloride_pourbaix_triptych | [answer.md](L1_8_20260609/answer.md) |
| L1_9 | [`L1_9_20260830`](L1_9_20260830/) | August 30-31 diagnostic run | L1_9_Cu_ammonia_speciation_E0265 | [answer.md](L1_9_20260830/answer.md) |
| L1_10 | [`L1_10_20260830`](L1_10_20260830/) | August 30-31 diagnostic run | L1_10_CuFe_cit_gly_Cl_NH3_pourbaix | [answer.html](L1_10_20260830/answer.html) |
| L1_11 | [`L1_11_20260830`](L1_11_20260830/) | August 30-31 diagnostic run | L1_11_CuFe_cit_gly_Cl_NH3_pourbaix_hydr | [answer.md](L1_11_20260830/answer.md) |
| L2_1 | [`L2_1_20260609`](L2_1_20260609/) | June 9 benchmark run | L2_1_CuZnNi_chelator_survey | [answer.md](L2_1_20260609/answer.md) |
| L2_2 | [`L2_2_20260609`](L2_2_20260609/) | June 9 benchmark run | L2_2_FeCaMg_sequestrant_survey | [answer.md](L2_2_20260609/answer.md) |
| L2_3 | [`L2_3_20260609`](L2_3_20260609/) | June 9 benchmark run | L2_3_PbZnCa_chelation_survey | [answer.md](L2_3_20260609/answer.md) |
| L2_4 | [`L2_4_20260609`](L2_4_20260609/) | June 9 benchmark run | L2_4_CoNiCu_amino_acid_survey | [answer.md](L2_4_20260609/answer.md) |
| L2_5 | [`L2_5_20260609`](L2_5_20260609/) | June 9 benchmark run | L2_5_Ni_antiscale_ligand_rank | [answer.md](L2_5_20260609/answer.md) |
| L2_6 | [`L2_6_20260609`](L2_6_20260609/) | June 9 benchmark run | L2_6_CuNiZn_chelator_matrix_3x3 | [answer.md](L2_6_20260609/answer.md) |
| L2_7 | [`L2_7_20260609`](L2_7_20260609/) | June 9 benchmark run | L2_7_FeCaMgZn_antiscale_EDTA_vs_citrate | [answer.md](L2_7_20260609/answer.md) |
| L2_8 | [`L2_8_20260609`](L2_8_20260609/) | June 9 benchmark run | L2_8_CuZn_shared_limiting_EDTA | [answer.md](L2_8_20260609/answer.md) |
| L3_1 | [`L3_1_20260609`](L3_1_20260609/) | June 9 benchmark run | L3_1_IrvingWilliams_glycine_test | [answer.md](L3_1_20260609/answer.md) |
| L3_2 | [`L3_2_20260609`](L3_2_20260609/) | June 9 benchmark run | L3_2_ChelateEffect_en_vs_ammonia | [answer.md](L3_2_20260609/answer.md) |
| L3_3 | [`L3_3_20260609`](L3_3_20260609/) | June 9 benchmark run | L3_3_HSAB_Cd_chloride_vs_ammonia | [answer.md](L3_3_20260609/answer.md) |
| L3_4 | [`L3_4_20260609`](L3_4_20260609/) | June 9 benchmark run | L3_4_HSAB_CdZn_chloride_ammonia_competition | [answer.md](L3_4_20260609/answer.md) |
| L3_5 | [`L3_5_20260609`](L3_5_20260609/) | June 9 benchmark run | L3_5_IrvingWilliams_two_ligand_robustness | [answer.md](L3_5_20260609/answer.md) |
| L3_6 | [`L3_6_20260609`](L3_6_20260609/) | June 9 benchmark run | L3_6_Chelate_denticity_trend_NH3_en_EDTA | Not present in the original cache |
| L4_1 | [`L4_1_20260609`](L4_1_20260609/) | June 9 benchmark run | L4_1_UTh_crown_EDTA_not_in_db | [answer.md](L4_1_20260609/answer.md) |
| L4_2 | [`L4_2_20260609`](L4_2_20260609/) | June 9 benchmark run | L4_2_FeCu_citrate_chloride_hot_out_of_envelope | [answer.md](L4_2_20260609/answer.md) |
| L4_3 | [`L4_3_20260609`](L4_3_20260609/) | June 9 benchmark run | L4_3_Acetic_acid_titration_curve | [answer.md](L4_3_20260609/answer.md) |
| L4_4 | [`L4_4_20260609`](L4_4_20260609/) | June 9 benchmark run | L4_4_PuAm_aspirin_citrate_not_in_db | [answer.md](L4_4_20260609/answer.md) |
| L4_5 | [`L4_5_20260609`](L4_5_20260609/) | June 9 benchmark run | L4_5_Unobtainium_fake_metal | [answer.md](L4_5_20260609/answer.md) |
| L4_6 | [`L4_6_20260609`](L4_6_20260609/) | June 9 benchmark run | L4_6_CuZn_glycine_EDTA_kinetics | [answer.md](L4_6_20260609/answer.md) |
| L4_7 | [`L4_7_20260609`](L4_7_20260609/) | June 9 benchmark run | L4_7_Ni_glycine_ammonia_ternary | [answer.md](L4_7_20260609/answer.md) |
