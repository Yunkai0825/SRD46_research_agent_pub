#!/usr/bin/env bash
# cd /n/_DB_parsing_pdf/20260316_fullSQL_MCP/SRD46_db_subagent
# bash run_freeform_fe_corrected.sh

set -euo pipefail

cd /n/_DB_parsing_pdf/20260316_fullSQL_MCP/SRD46_db_subagent

PY="C:/ProgramData/anaconda3/python.exe"
PROMPT="@_output/_freeform_prompts/fe_iii_vs_fe_ii_ligand_corrected.txt"
TITLE="Fe(III)/Fe(II) ligand selection (corrected)"
MAX_TURNS=40
TIMEOUT=30000

for MODEL in claudeopus46 gpt54; do
  LOG="_output/_freeform_prompts/_run_fe_corrected_${MODEL}.log"
  echo ">>> Running freeform prompt with model=${MODEL}"
  echo ">>> Log: ${LOG}"
  "$PY" freeform_runner.py "$PROMPT" \
    -m "$MODEL" \
    --title "$TITLE" \
    --max-turns "$MAX_TURNS" \
    -t "$TIMEOUT" \
    2>&1 | tee "$LOG"
  echo
done