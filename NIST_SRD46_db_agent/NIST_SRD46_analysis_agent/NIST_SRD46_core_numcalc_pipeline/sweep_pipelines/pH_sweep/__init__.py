"""pH sweep method package.

Imports are lazy to avoid circular dependencies.
"""

_EXPORT_NAMES = {
    "run_pH_sweep", "sweep_fn",
    "SWEEP_ID", "SWEEP_DESCRIPTION", "SWEEP_PARAMS",
    "generate_all_output", "export_csv", "export_envelope_csv",
    "generate_dp_envelope_csv", "read_envelope_csv",
    "write_verdict_document",
    "plot_fraction", "plot_log_conc", "plot_multi_fraction",
}

_PLOT_NAMES = {"plot_fraction", "plot_log_conc", "plot_multi_fraction"}


def __getattr__(name):
    if name == "run_pH_sweep":
        from .pH_sweep_main import run_pH_sweep
        return run_pH_sweep
    if name in _PLOT_NAMES:
        from . import pH_sweep_plot as _plt
        return getattr(_plt, name)
    if name in _EXPORT_NAMES:
        from . import pH_sweep_export as _exp
        return getattr(_exp, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = sorted(_EXPORT_NAMES)
