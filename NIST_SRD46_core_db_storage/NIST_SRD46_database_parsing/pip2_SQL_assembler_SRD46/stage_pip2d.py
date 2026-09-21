"""Build ligand fingerprints and all upper-triangle similarities as one atomic output."""
from __future__ import annotations

from typing import Any, Dict

from srd46_pipeline.publish import finalize_sqlite, publish, temp_path
from srd46_pipeline.runner import Context, PipelineError

STAGE = "pip2d_ligand_similarity"


def run(ctx: Context) -> Dict[str, Any]:
    cards_db = ctx.paths.cards_db
    if not cards_db.is_file():
        raise PipelineError(f"pip2d: source cards database missing: {cards_db}")
    cards_status = ctx.staging.stage_status("pip2c_cards")
    if cards_status in ("failed", "stale", "running"):
        raise PipelineError(f"pip2d: pip2c_cards is {cards_status}; rebuild cards before descriptors")

    from .pip2d_ligand_similarity.build_ligand_fingerprints import build as build_fingerprints
    from .pip2d_ligand_similarity.build_ligand_similarities import build as build_similarities
    from .pip2d_ligand_similarity import verify_database

    final = ctx.paths.fingerprints_db
    final.parent.mkdir(parents=True, exist_ok=True)
    tmp = temp_path(final)
    ctx.log(f"pip2d: building ligand fingerprints from {cards_db.name}")
    fingerprint_stats = build_fingerprints(cards_db, tmp)
    ctx.log(f"pip2d: {fingerprint_stats['ok']:,} usable structures / {fingerprint_stats['total']:,} ligands")
    ctx.log("pip2d: building complete upper-triangle ligand similarities")
    similarity_stats = build_similarities(tmp, progress=ctx.log)
    ctx.log("pip2d: verifying descriptor source and complete similarity matrix")
    verification = verify_database(cards_db, tmp)
    finalize_sqlite(tmp)
    publish(tmp, final)
    ctx.staging.put_json("ligand_fingerprint_stats", fingerprint_stats, STAGE)
    ctx.staging.put_json("ligand_similarity_stats", similarity_stats, STAGE)
    ctx.staging.put_json("ligand_similarity_verification", verification, STAGE)
    return {"db": str(final), "fingerprints": fingerprint_stats,
            "similarities": similarity_stats, "verification": verification}
