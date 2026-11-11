"""
freeform_sweep
==============
Generic N-D freeform sweep package — the catch-all handler for any
sweep whose axes / constraints do not match ``pH_sweep`` (strict 1-D
pH) or ``pourbaix_sweep`` (2-D pH x E_V, optionally 3-D with a_w).
"""
from __future__ import annotations

from .freeform_sweep_main import run_freeform_sweep
from .freeform_sweep_export import (
    SWEEP_ID,
    SWEEP_DESCRIPTION,
    SWEEP_PARAMS,
    sweep_fn,
    generate_all_output,
    emit_cell_table_csv,
    emit_fraction_csvs,
    emit_1d_fraction_plots,
    emit_2d_label_heatmaps,
    write_run_params_json,
)

__all__ = [
    "run_freeform_sweep",
    "sweep_fn",
    "SWEEP_ID",
    "SWEEP_DESCRIPTION",
    "SWEEP_PARAMS",
    "generate_all_output",
    "emit_cell_table_csv",
    "emit_fraction_csvs",
    "emit_1d_fraction_plots",
    "emit_2d_label_heatmaps",
    "write_run_params_json",
]
