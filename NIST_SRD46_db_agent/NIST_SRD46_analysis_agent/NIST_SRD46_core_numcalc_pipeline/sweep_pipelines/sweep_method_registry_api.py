"""
Sweep Method Registry API
=========================
Central registry for all sweep methods. Each sweep method package
exports:

  **Sweep execution:**
  - ``SWEEP_ID``          : str — unique identifier
  - ``SWEEP_DESCRIPTION`` : str — human-readable description
  - ``SWEEP_PARAMS``      : dict — parameter metadata
  - ``sweep_fn``          : callable — the pH/titration/… sweep function

  **Output generation:**
  - ``generate_all_output``     : callable — master output orchestrator
  - ``generate_dp_envelope_csv``: callable — Douglas-Peucker envelope
  - ``read_envelope_csv``       : callable — read an envelope CSV back
  - ``export_csv``              : callable — full-resolution CSV export
  - ``export_envelope_csv``     : callable — sampled fraction envelopes
  - ``write_verdict_document``  : callable — calculation-based verdict
  - ``plot_fraction``           : callable — fraction diagram
  - ``plot_log_conc``           : callable — log-concentration diagram
  - ``plot_multi_fraction``     : callable — multi-component fraction diagram

All external code should go through this registry rather than
importing directly from sweep-method sub-packages.

Public API
----------
- ``get_sweep_method(name)``        → sweep callable
- ``get_output_generator(name)``    → ``generate_all_output`` callable
- ``get_envelope_generator(name)``  → ``generate_dp_envelope_csv`` callable
- ``get_envelope_reader(name)``     → ``read_envelope_csv`` callable
- ``get_sweep_output_tools(name)``  → dict of all output callables
- ``list_sweep_methods()``          → dict of {id: description}
- ``get_sweep_params(name)``        → parameter metadata
- ``DEFAULT_SWEEP_METHOD``          — the default sweep method id
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict

log = logging.getLogger("SWEEP-REGISTRY")

DEFAULT_SWEEP_METHOD = "pH_sweep"

# ── Lazy registry — populated on first access ────────────────

_registry: Dict[str, Dict[str, Any]] | None = None


def _build_registry() -> Dict[str, Dict[str, Any]]:
    """Import and register all sweep method modules."""
    reg: Dict[str, Dict[str, Any]] = {}

    # ── pH sweep (always available) ──────────────────────────
    from .pH_sweep.pH_sweep_export import (
        sweep_fn as ph_fn,
        SWEEP_ID as ph_id,
        SWEEP_DESCRIPTION as ph_desc,
        SWEEP_PARAMS as ph_params,
        generate_all_output as ph_gen_all,
        generate_dp_envelope_csv as ph_gen_env,
        read_envelope_csv as ph_read_env,
        export_csv as ph_export_csv,
        export_envelope_csv as ph_export_env,
        write_verdict_document as ph_write_verdict,
    )
    from .pH_sweep.pH_sweep_plot import (
        plot_fraction as ph_plot_frac,
        plot_log_conc as ph_plot_log,
        plot_multi_fraction as ph_plot_multi,
    )
    reg[ph_id] = {
        "fn": ph_fn,
        "description": ph_desc,
        "params": ph_params,
        # output tools
        "generate_all_output": ph_gen_all,
        "generate_dp_envelope_csv": ph_gen_env,
        "read_envelope_csv": ph_read_env,
        "export_csv": ph_export_csv,
        "export_envelope_csv": ph_export_env,
        "write_verdict_document": ph_write_verdict,
        "plot_fraction": ph_plot_frac,
        "plot_log_conc": ph_plot_log,
        "plot_multi_fraction": ph_plot_multi,
    }

    # ── Pourbaix sweep ───────────────────────────────────────
    try:
        from .pourbaix_sweep.pourbaix_sweep_export import (
            sweep_fn as pbx_fn,
            SWEEP_ID as pbx_id,
            SWEEP_DESCRIPTION as pbx_desc,
            SWEEP_PARAMS as pbx_params,
            generate_all_output as pbx_gen_all,
        )
        reg[pbx_id] = {
            "fn": pbx_fn,
            "description": pbx_desc,
            "params": pbx_params,
            "generate_all_output": pbx_gen_all,
        }
    except ImportError:
        log.debug("Pourbaix sweep module not available")

    # ── Nernst simple mode ───────────────────────────────────
    # Lives outside this pipeline in NIST_SRD46_post_calc_tools (plain dir,
    # not a package), so it is imported top-level after a path bootstrap.
    try:
        try:
            from nernst_simple.nernst_simple_export import (
                sweep_fn as nst_fn,
                SWEEP_ID as nst_id,
                SWEEP_DESCRIPTION as nst_desc,
                SWEEP_PARAMS as nst_params,
                generate_all_output as nst_gen_all,
                export_csv as nst_export_csv,
                plot_e_vs_ph as nst_plot,
            )
        except ImportError:
            import sys
            from pathlib import Path
            _pct = Path(__file__).resolve().parents[2] / "NIST_SRD46_post_calc_tools"
            if not _pct.is_dir():
                raise
            if str(_pct) not in sys.path:
                sys.path.insert(0, str(_pct))
            from nernst_simple.nernst_simple_export import (
                sweep_fn as nst_fn,
                SWEEP_ID as nst_id,
                SWEEP_DESCRIPTION as nst_desc,
                SWEEP_PARAMS as nst_params,
                generate_all_output as nst_gen_all,
                export_csv as nst_export_csv,
                plot_e_vs_ph as nst_plot,
            )
        reg[nst_id] = {
            "fn": nst_fn,
            "description": nst_desc,
            "params": nst_params,
            "generate_all_output": nst_gen_all,
            "export_csv": nst_export_csv,
            "plot_fraction": nst_plot,
        }
    except ImportError:
        log.debug("Nernst simple module not available")

    # ── Titration sweep (placeholder) ────────────────────────
    try:
        from .titration_sweep.titration_sweep_main import (
            sweep_fn as tit_fn,
            SWEEP_ID as tit_id,
            SWEEP_DESCRIPTION as tit_desc,
            SWEEP_PARAMS as tit_params,
        )
        reg[tit_id] = {
            "fn": tit_fn,
            "description": tit_desc,
            "params": tit_params,
        }
    except ImportError:
        log.debug("Titration sweep module not available")

    # ── Freeform sweep (catch-all N-D) ───────────────────────
    try:
        from .freeform_sweep import (
            sweep_fn as ff_fn,
            SWEEP_ID as ff_id,
            SWEEP_DESCRIPTION as ff_desc,
            SWEEP_PARAMS as ff_params,
            generate_all_output as ff_gen_all,
        )
        reg[ff_id] = {
            "fn": ff_fn,
            "description": ff_desc,
            "params": ff_params,
            "generate_all_output": ff_gen_all,
        }
    except ImportError:
        log.debug("Freeform sweep module not available")

    log.info("[SWEEP-REG] Registered %d sweep methods: %s",
             len(reg), list(reg.keys()))
    return reg


def _ensure_registry() -> Dict[str, Dict[str, Any]]:
    global _registry
    if _registry is None:
        _registry = _build_registry()
    return _registry


def _get_entry(name: str) -> Dict[str, Any]:
    """Return the full registry entry, raising ValueError if missing."""
    reg = _ensure_registry()
    if name not in reg:
        available = ", ".join(reg.keys())
        raise ValueError(
            f"Unknown sweep method '{name}'. Available: {available}"
        )
    return reg[name]


# ── Sweep execution ──────────────────────────────────────────

def get_sweep_method(name: str = DEFAULT_SWEEP_METHOD) -> Callable:
    """Return the sweep callable for the given method name."""
    return _get_entry(name)["fn"]


# ── Output tools ─────────────────────────────────────────────

def get_output_generator(name: str = DEFAULT_SWEEP_METHOD) -> Callable:
    """Return the ``generate_all_output`` callable for a sweep method."""
    return _get_entry(name)["generate_all_output"]


def get_envelope_generator(name: str = DEFAULT_SWEEP_METHOD) -> Callable:
    """Return the ``generate_dp_envelope_csv`` callable for a sweep method."""
    return _get_entry(name)["generate_dp_envelope_csv"]


def get_envelope_reader(name: str = DEFAULT_SWEEP_METHOD) -> Callable:
    """Return the ``read_envelope_csv`` callable for a sweep method."""
    return _get_entry(name)["read_envelope_csv"]


_OUTPUT_TOOL_KEYS = frozenset({
    "generate_all_output", "generate_dp_envelope_csv", "read_envelope_csv",
    "export_csv", "export_envelope_csv", "write_verdict_document",
    "plot_fraction", "plot_log_conc", "plot_multi_fraction",
})


def get_sweep_output_tools(name: str = DEFAULT_SWEEP_METHOD) -> Dict[str, Callable]:
    """Return a dict of all output callables for a sweep method.

    Keys match the function names (``generate_all_output``, etc.).
    Only keys that exist in the registered entry are returned,
    so partially-implemented sweep methods work gracefully.
    """
    entry = _get_entry(name)
    return {k: entry[k] for k in _OUTPUT_TOOL_KEYS if k in entry}


# ── Metadata / introspection ────────────────────────────────

def list_sweep_methods() -> Dict[str, str]:
    """Return {method_id: description} for all registered sweep methods."""
    reg = _ensure_registry()
    return {k: v["description"] for k, v in reg.items()}


def get_sweep_params(name: str = DEFAULT_SWEEP_METHOD) -> Dict[str, Any]:
    """Return parameter metadata for a sweep method."""
    return _get_entry(name)["params"]


def get_sweep_info() -> str:
    """Return a compact multi-line summary of all sweep methods for LLM context."""
    reg = _ensure_registry()
    lines = []
    for sid, info in reg.items():
        status = "(not implemented)" if "not yet implemented" in info["description"].lower() else "(available)"
        lines.append(f"- {sid} {status}: {info['description']}")
    return "\n".join(lines)
