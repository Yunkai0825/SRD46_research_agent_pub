#!/usr/bin/env python3
"""Thin wrapper around the reusable regex_enricher orchestrator."""
from __future__ import annotations

import sys
from pathlib import Path

# This script lives in <project_root>/BATCH_run_scripts/, so the project root is parent.parent.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from NIST_SRD46_db_agent.NIST_SRD46_query_agent.SRD46_query_output_eval_pipeline.regex_enricher_orchestrator import main


if __name__ == "__main__":
    raise SystemExit(main())
