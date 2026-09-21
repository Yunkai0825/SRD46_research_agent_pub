"""
Unified sweep entry point — the single import for running any sweep.

Usage::

    from sweep_pipelines._sweep_input_entry_point import run_sweep

    results = run_sweep(
        "path/to/free_energy_card.md",
        sweep_type="pourbaix",
        output_dir="output/",
        n_pH=50, n_E=50,
    )
"""
from .sweep_dispatcher import run_sweep, build_solver_chain, parse_source

__all__ = ["run_sweep", "build_solver_chain", "parse_source"]
