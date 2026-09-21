"""Post-evaluation claim statistics & validation pipeline.

Reads ``_output_eval/Model_*/Q*/claims_batch*.json`` artifacts produced by the
claim classifier + grounder and emits aggregation tables, plots, and audit
reports under ``SRD46_query_output_eval_pipeline/posteval_stats/_data``, ``json/``, ``figures/``.
"""

from .loader import (
    BUCKET_BY_SUPPORT,
    BUCKETS,
    ClaimRecord,
    iter_claim_records,
    load_long_table,
    write_long_csv,
)
from .pipeline import audit_stats_bundle, build_stats_bundle, run_stats_bundle
from .section_policy import SectionPolicy

__all__ = [
    "BUCKET_BY_SUPPORT",
    "BUCKETS",
    "ClaimRecord",
    "SectionPolicy",
    "audit_stats_bundle",
    "build_stats_bundle",
    "iter_claim_records",
    "load_long_table",
    "run_stats_bundle",
    "write_long_csv",
]
