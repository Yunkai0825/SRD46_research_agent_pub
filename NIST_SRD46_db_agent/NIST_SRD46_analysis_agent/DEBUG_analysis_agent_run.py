#!/usr/bin/env python
r"""
DEBUG entry point for the SRD-46 **analysis** agent.
====================================================

A convenience launcher that lives next to ``SRD46_analysis_api.py`` so you can
run selected *layers* or individual *prompts* from the analysis test suite
without remembering the deeper ``_DEBUG_script/`` path.

Prompts are read from ``_DEBUG_input/TEST_PROMPTS.md`` (4-column
``| # | layer | label | prompt |`` table). Per-prompt output is written to
``Diagnostics/<label>/`` and a batch summary JSON is dropped alongside it.

This file is a thin wrapper: all logic lives in
``_DEBUG_script/test_analysis_prompts_batch.py`` (single source of truth).

Usage
-----
    # list everything that would run
    python DEBUG_analysis_agent_run.py --list

    # run whole layers (DIAG / MULTI / HYPO / HALL)
    python DEBUG_analysis_agent_run.py --layer HYPO HALL

    # run specific prompts by label
    python DEBUG_analysis_agent_run.py --only L1_1_Ni_glycine_pourbaix_2D

    # keep pre-existing per-prompt session dirs / disable debug forwarding
    python DEBUG_analysis_agent_run.py --layer DIAG --keep --no-debug

Windows MAX_PATH note
---------------------
On old Windows hosts without long-path support, run the repository from a
short checkout path or a short substituted drive before launching this script.
"""
from __future__ import annotations

import sys
from pathlib import Path



import sys
from pathlib import Path

# Make the workspace root importable so ``NIST_SRD46_db_agent`` resolves
# whether this file is launched as a script or imported as a module.
_HERE = Path(__file__).absolute()
_REPO = _HERE.parents[2]  # NIST_SRD46_analysis_agent -> NIST_SRD46_db_agent -> <repo root>
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from NIST_SRD46_db_agent.NIST_SRD46_analysis_agent._DEBUG_script.test_analysis_prompts_batch import (
    main as _batch_main,
)


if __name__ == "__main__":
    raise SystemExit(_batch_main())
