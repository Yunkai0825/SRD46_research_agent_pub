"""
Stage pip2a: metal-ligand equilibrium maps -> srd46_equilibrium_maps.db.

The original builder/exporter read four CSV hand-offs from disk through ``lru_cache``d loaders.
Here the loaders are replaced (in BOTH modules, which bind them by name) with closures over
DataFrames materialised from staging via the same ``read_csv`` inference the files would get.
verkn_ligand_metal comes from the canonical table of stage raw_canonical (manual rule SRC-01).
The soft-filter reference conditions and the K constant type are manual rule REF-01: the
``equilibrium_map_helpers.data_structures`` defaults are asserted equal to the declared values
and one policy row is written to the ledger.
"""
from __future__ import annotations

import logging
import sys
from typing import Any, Dict

import pandas as pd

from srd46_pipeline import manual_rules as mr
from srd46_pipeline.legacy import ensure_sys_path
from srd46_pipeline.paths import PIP2A_HELPERS_DIR
from srd46_pipeline.publish import publish, temp_path
from srd46_pipeline.runner import Context, PipelineError
from srd46_pipeline.staging import df_csv_roundtrip

STAGE = "pip2a_equilibrium_maps"
_VLM_COLS = ["verkn_ligand_metalID", "metalNr", "ligandenNr", "beta_definitionNr",
             "constanttypNr", "constant", "temperature", "ionicstrength"]


def _canonical_vlm_frame(ctx: Context) -> pd.DataFrame:
    """verkn_ligand_metal as the original builder expects it, values from stage raw_canonical.

    ``constant`` / ``temperature`` / ``ionicstrength`` are the parsed numbers (manual rules
    VLM-01..03: '*' -> NaN, '(x)' -> x, '30tv' -> 30). ``metalNr`` uses the guarded
    VLM-04 correction; original IDs remain in staging/``metalNr_raw``. Other columns get the same
    ``read_csv`` inference the CSV file used to receive.
    """
    ctx.staging.require_table("verkn_ligand_metal_canonical", "raw_canonical")
    canon = ctx.staging.read_df("verkn_ligand_metal_canonical")
    if "metalNr_value" not in canon:
        raise PipelineError("pip2a: canonical metalNr_value missing; rerun raw_canonical for VLM-04")
    canon["metalNr"] = canon["metalNr_value"]
    for col in ("constant", "temperature", "ionicstrength"):
        canon[col] = canon[f"{col}_value"]
    return df_csv_roundtrip(canon, low_memory=False)


def _ledger_ref01(ctx: Context) -> int:
    """REF-01: the module defaults must equal the declared policy; ledger the conditions used."""
    from equilibrium_map_helpers import data_structures as ds  # noqa: WPS433

    expected = {"CONSTANT_TYPE_K": mr.REF01_CONSTANT_TYPE_K, "DEFAULT_TEMPERATURE": mr.REF01_TEMPERATURE_C,
                "DEFAULT_TEMP_TOLERANCE": mr.REF01_TEMPERATURE_TOLERANCE_C, "DEFAULT_IONIC_STRENGTH": mr.REF01_IONIC_STRENGTH_M,
                "DEFAULT_IONIC_TOLERANCE": mr.REF01_IONIC_STRENGTH_TOLERANCE_M}
    drift = {k: (getattr(ds, k, None), v) for k, v in expected.items() if getattr(ds, k, None) != v}
    if drift:
        raise PipelineError(f"pip2a: equilibrium-map module defaults differ from REF-01: {drift}")
    return ctx.staging.log_manual_fixes(STAGE, [{
        "table_name": "equilibrium_maps.db", "record_id": None, "field": "reference_conditions", "old_value": None,
        "new_value": (f"K = constanttyp {mr.REF01_CONSTANT_TYPE_K}; soft filter T={mr.REF01_TEMPERATURE_C:g} C "
                      f"+-{mr.REF01_TEMPERATURE_TOLERANCE_C:g}, I={mr.REF01_IONIC_STRENGTH_M:g} M +-{mr.REF01_IONIC_STRENGTH_TOLERANCE_M:g}"),
        "reason": mr.RULES["REF-01"].summary, "source": mr.ledger_source("REF-01"), "status": "policy"}])


def run(ctx: Context) -> Dict[str, Any]:
    st = ctx.staging
    for tbl, producer in [("beta_definition_augmented", "pip1a_beta_definition"), ("metal_augmented", "pip1b_metal"),
                          ("liganden_w_moldata_qupkake_parsed", "pip1c_6_qupkake_merge")]:
        st.require_table(tbl, producer)
    ensure_sys_path(PIP2A_HELPERS_DIR)
    import equilibrium_map_builder_v3 as builder      # noqa: WPS433
    import equilibrium_map_sql_exporter as exporter   # noqa: WPS433
    n_ref01 = _ledger_ref01(ctx)

    # Logging: route the two module loggers into the (captured) stdout of this stage.
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(levelname)-7s %(name)s: %(message)s"))
    level = logging.INFO if ctx.options.verbose else logging.WARNING
    for lg in (builder.logger, exporter.logger):
        lg.handlers.clear()
        lg.addHandler(handler)
        lg.setLevel(level)
        lg.propagate = False
    exporter.print = lambda *a, **k: ctx.log(" ".join(str(x) for x in a))   # progress lines to console

    ctx.log("pip2a: materialising inputs from staging")
    vlm_df = _canonical_vlm_frame(ctx)
    beta_df = df_csv_roundtrip(st.read_df("beta_definition_augmented"))
    if "beta_definitionID" in beta_df.columns:
        beta_df = beta_df.set_index("beta_definitionID", drop=False)
    metals_df = df_csv_roundtrip(st.read_df("metal_augmented"))
    if "metalID" in metals_df.columns:
        metals_df = metals_df.set_index("metalID", drop=False)
    ligands_df = df_csv_roundtrip(st.read_df("liganden_w_moldata_qupkake_parsed"), low_memory=False)
    if "ligandenID" in ligands_df.columns:
        ligands_df = ligands_df.set_index("ligandenID", drop=False)
    frames = {"load_vlm_data": vlm_df, "load_beta_definitions": beta_df,
              "load_metals": metals_df, "load_ligands": ligands_df}
    for fn_name, frame in frames.items():
        loader = (lambda f: (lambda: f))(frame)
        setattr(builder, fn_name, loader)
        setattr(exporter, fn_name, loader)
    ctx.log(f"pip2a: vlm={len(vlm_df)} beta={len(beta_df)} metals={len(metals_df)} ligands={len(ligands_df)}")

    eq_db = ctx.paths.eq_db
    eq_db.parent.mkdir(parents=True, exist_ok=True)
    tmp = temp_path(eq_db)
    exp = exporter.EquilibriumMapSQLExporter(tmp)
    exp.open()
    try:
        ctx.log(f"pip2a: exporting equilibrium maps (limit={ctx.limit}); the full set takes ~10-15 min")
        report = exp.export_all(max_pairs=ctx.limit)
        exp.conn.execute("PRAGMA journal_mode=DELETE")
        exp.conn.commit()
    finally:
        exp.close()
    if not tmp.exists():
        raise PipelineError("pip2a: exporter produced no database file")
    publish(tmp, eq_db)

    # Diagnostics the original run wrote as JSON/CSV files -> staging
    rep = report.to_dict()
    rep["invalid_beta_vlm_ids"] = list(report.invalid_beta_vlm_ids)
    rep["invalid_metal_vlm_ids"] = list(report.invalid_metal_vlm_ids)
    rep["invalid_ligand_vlm_ids"] = list(report.invalid_ligand_vlm_ids)
    rep["no_species_beta_ids"] = list(report.no_species_beta_ids)
    st.put_json("pip2a_debug_report", rep, STAGE)
    st.write_df("pip2a_processing_errors", pd.DataFrame(report.processing_errors), STAGE)
    cols = [c for c in _VLM_COLS if c in vlm_df.columns]
    st.write_df("pip2a_unassigned_vlm", vlm_df[vlm_df["verkn_ligand_metalID"].isin(exp._unassigned_vlm_ids)][cols], STAGE)
    st.write_df("pip2a_no_species_vlm", vlm_df[vlm_df["verkn_ligand_metalID"].isin(report.no_species_vlm_ids)][cols], STAGE)
    return {"pairs": rep.get("unique_metal_ligand_pairs"), "vlm_assigned": rep.get("vlm_assigned_to_networks"),
            "vlm_stray": rep.get("vlm_stray"), "vlm_unassigned": rep.get("vlm_unassigned"),
            "no_species_vlm": rep.get("no_species_vlm_count"), "processing_errors": rep.get("processing_errors_count"),
            "coverage_pct": round(rep.get("coverage_rate", 0.0), 2), "db": str(eq_db), "ref01_ledger_rows": n_ref01}
