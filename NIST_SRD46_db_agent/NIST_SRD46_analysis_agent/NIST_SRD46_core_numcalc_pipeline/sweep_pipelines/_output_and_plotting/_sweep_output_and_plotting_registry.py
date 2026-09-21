"""
_sweep_output_and_plotting_registry.py
======================================
Convenience registry mapping sweep_id → output/plotting functions.

Delegates to the central ``sweep_method_registry_api`` for actual
registration. This module provides a focused interface for output
and plotting code that doesn't need sweep execution functions.

Public API
----------
- ``get_output_tools(sweep_id)`` → dict of output callables
- ``get_plot_tools(sweep_id)``   → dict of plot callables
- ``list_registered()``          → list of sweep_ids with output support
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List

_OUTPUT_KEYS = frozenset({
    "generate_all_output",
    "generate_dp_envelope_csv",
    "read_envelope_csv",
    "export_csv",
    "export_envelope_csv",
    "write_verdict_document",
})

_PLOT_KEYS = frozenset({
    "plot_fraction",
    "plot_log_conc",
    "plot_multi_fraction",
})


def _get_entry(sweep_id: str) -> Dict[str, Any]:
    from ..sweep_method_registry_api import _get_entry
    return _get_entry(sweep_id)


def get_output_tools(sweep_id: str) -> Dict[str, Callable]:
    """Return output-generation callables for the given sweep method."""
    entry = _get_entry(sweep_id)
    return {k: entry[k] for k in _OUTPUT_KEYS if k in entry}


def get_plot_tools(sweep_id: str) -> Dict[str, Callable]:
    """Return plotting callables for the given sweep method."""
    entry = _get_entry(sweep_id)
    return {k: entry[k] for k in _PLOT_KEYS if k in entry}


def list_registered() -> List[str]:
    """Return sweep IDs that have at least one output tool registered."""
    from ..sweep_method_registry_api import _ensure_registry
    reg = _ensure_registry()
    return [sid for sid, info in reg.items()
            if any(k in info for k in _OUTPUT_KEYS | _PLOT_KEYS)]
