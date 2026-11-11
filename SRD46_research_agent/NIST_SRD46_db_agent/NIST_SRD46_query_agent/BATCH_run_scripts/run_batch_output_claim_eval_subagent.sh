#!/usr/bin/env bash
#
# CLAIM EVALUATION BATCH RUN
# Scans existing run artifacts under _output/ and writes claim-eval artifacts
# under _output_eval/. Additional published summaries are written when the
# corresponding --publish-* flags are provided.
#
# Usage:
#   cd N:/_DB_parsing_pdf/20260316_fullSQL_MCP/SRD46_db_subagent
#   bash run_batch_output_claim_eval_subagent.sh
#   bash run_batch_output_claim_eval_subagent.sh --extract-only
#   bash run_batch_output_claim_eval_subagent.sh --model gpt5 --question Q1.1.1 --workers 1 --force
#   bash run_batch_output_claim_eval_subagent.sh --publish-eval-stats --publish-tool-stats

set -euo pipefail
cd "$(dirname "$0")"

exec python run_batch_output_claim_eval_subagent.py "$@"
