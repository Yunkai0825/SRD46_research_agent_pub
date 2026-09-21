"""Stage pip2b: per-ligand preferred pKa chains from the H+ equilibrium maps -> staging table.

Reference conditions come from manual rule REF-01 (``manual_rules.REF01_*``); the helper module's
defaults are asserted equal to them and one policy row is written to the ledger.
"""
from __future__ import annotations

import inspect
from typing import Any, Dict

from srd46_pipeline import manual_rules as mr
from srd46_pipeline.legacy import ensure_sys_path
from srd46_pipeline.paths import PIP2B_HELPERS_DIR
from srd46_pipeline.runner import Context, PipelineError

STAGE = "pip2b_ligand_pka_chains"


def _ledger_ref01(ctx: Context, builder: Any, reader: Any) -> int:
    """REF-01: check the helper module's defaults against the declared policy and ledger the conditions used."""
    defaults = {k: v.default for k, v in inspect.signature(builder.build_pka_for_ligand).parameters.items()}
    expected = {"target_temperature": mr.REF01_TEMPERATURE_C, "target_ionic_strength": mr.REF01_IONIC_STRENGTH_M,
                "temp_tolerance": mr.REF01_TEMPERATURE_TOLERANCE_C, "ionic_tolerance": mr.REF01_IONIC_STRENGTH_TOLERANCE_M}
    drift = {k: (defaults.get(k), v) for k, v in expected.items() if defaults.get(k) != v}
    if drift or reader.HPLUS_METAL_ID != mr.REF01_HPLUS_METAL_ID:
        raise PipelineError(f"pip2b: pKa-chain helper defaults differ from REF-01: {drift} "
                            f"HPLUS_METAL_ID={reader.HPLUS_METAL_ID} (REF-01 {mr.REF01_HPLUS_METAL_ID})")
    return ctx.staging.log_manual_fixes(STAGE, [{
        "table_name": "preferred_ligand_pka_chains", "record_id": None, "field": "reference_conditions",
        "old_value": None,
        "new_value": (f"T={mr.REF01_TEMPERATURE_C:g} C +-{mr.REF01_TEMPERATURE_TOLERANCE_C:g}; "
                      f"I={mr.REF01_IONIC_STRENGTH_M:g} M +-{mr.REF01_IONIC_STRENGTH_TOLERANCE_M:g}; H+ metal {mr.REF01_HPLUS_METAL_ID}"),
        "reason": mr.RULES["REF-01"].summary, "source": mr.ledger_source("REF-01"), "status": "policy"}])


def run(ctx: Context) -> Dict[str, Any]:
    eq_db = ctx.paths.eq_db
    if not eq_db.exists():
        raise PipelineError(f"pip2b: equilibrium map DB missing ({eq_db}); run stage pip2a_equilibrium_maps first")
    ensure_sys_path(PIP2B_HELPERS_DIR)
    import hplus_map_reader  # noqa: WPS433
    import pka_chain_builder  # noqa: WPS433
    from pka_chain_builder import build_pka_for_all_ligands, pka_chains_to_dataframe  # noqa: WPS433

    n_logged = _ledger_ref01(ctx, pka_chain_builder, hplus_map_reader)
    ctx.log(f"pip2b: building pKa chains (REF-01: T={mr.REF01_TEMPERATURE_C:g} C, I={mr.REF01_IONIC_STRENGTH_M:g} M) from {eq_db.name}")
    chains = build_pka_for_all_ligands(mr.REF01_TEMPERATURE_C, mr.REF01_IONIC_STRENGTH_M, eq_db,
                                       include_all=False, verbose=True)
    df = pka_chains_to_dataframe(chains, include_all_json=False)
    ctx.staging.write_df("preferred_ligand_pka_chains", df, STAGE)
    total_steps = int(sum(c.n_steps for c in chains.values()))
    detail = {"ligands_with_hplus": len(chains), "total_pka_steps": total_steps,
              "avg_steps": round(total_steps / len(chains), 3) if chains else 0.0, "rows": len(df),
              "ref01_ledger_rows": n_logged}
    ctx.staging.put_json("pip2b_stats", detail, STAGE)
    return detail
