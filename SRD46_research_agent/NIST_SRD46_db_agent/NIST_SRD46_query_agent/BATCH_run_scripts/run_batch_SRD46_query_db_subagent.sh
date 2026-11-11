#!/usr/bin/env bash
#
# NOT THE REGEX ENRICHMENT BATCH RUN
# Full benchmark: 4 models × 5 repeats × all prompts
# Output: _output/Model_{name}/Q{id}/Q{id}_{result|history}_batch{n}.md
#
# Argo model aliases (verified from codebase conventions):
#   claudeopus46   — Claude Opus 4.6
#   claudesonnet46 — Claude Sonnet 4.6
#   gpt5           — GPT-5
#   gpt54          — GPT-5.4  (inferred from gpt5/gpt52 pattern; adjust if wrong)
#
# Usage:
#   cd N:/_DB_parsing_pdf/20260316_fullSQL_MCP/SRD46_db_subagent
#   bash run_batch_SRD46_query_db_subagent.sh                         # full run
#   bash run_batch_SRD46_query_db_subagent.sh --section 1             # only section 1.x
#   bash run_batch_SRD46_query_db_subagent.sh 1.1.1 2.1.3             # specific prompt IDs

set -euo pipefail
cd "$(dirname "$0")"

python run_batch_SRD46_query_db_subagent.py \
    --models claudeopus46 claudesonnet46 gpt5 gpt54 \
    --repeats 5 \
    --parallel 6 \
    --argo-max-inflight 2 \
    --argo-min-interval 1.5 \
    --argo-cooldown 15 \
    "$@"
