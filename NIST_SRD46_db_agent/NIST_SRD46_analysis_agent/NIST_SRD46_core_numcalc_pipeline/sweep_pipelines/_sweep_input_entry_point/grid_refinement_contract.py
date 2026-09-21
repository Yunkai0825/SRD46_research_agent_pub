"""Shared declaration contract for optional boundary refinement.

At the runtime boundary, ``n_layers`` is the sole enable/disable switch.  At
the card boundary, an explicit ``mode`` distinguishes ``none`` from
``boundary`` so a disabled declaration need not carry unused numeric fields.
"""
from __future__ import annotations

from numbers import Integral
from typing import Any, Optional, Tuple


def normalize_grid_refinement(
    *,
    n_layers: Any,
    factor: Any,
    context: str = "grid_refine",
) -> Tuple[int, Optional[int]]:
    """Validate and normalize an explicitly declared refinement policy.

    Returns ``(n_layers, factor)`` with ordinary Python integers.  Disabled
    refinement is represented only as ``(0, None)``; no unused factor is
    manufactured or accepted.
    """
    if isinstance(n_layers, bool) or not isinstance(n_layers, Integral):
        raise ValueError(f"{context}.n_layers must be an integer")
    layers = int(n_layers)
    if layers < 0:
        raise ValueError(f"{context}.n_layers must be >= 0")

    if layers == 0:
        if factor is not None:
            raise ValueError(
                f"{context}.factor must be omitted or null when "
                "n_layers is 0 (refinement disabled)"
            )
        return 0, None

    if factor is None:
        raise ValueError(
            f"{context}.factor is required when n_layers is >= 1"
        )
    if isinstance(factor, bool) or not isinstance(factor, Integral):
        raise ValueError(f"{context}.factor must be an integer")
    normalized_factor = int(factor)
    if normalized_factor < 2:
        raise ValueError(
            f"{context}.factor must be >= 2 when n_layers is >= 1"
        )
    return layers, normalized_factor


def normalize_grid_refinement_declaration(
    *,
    mode: Any,
    n_layers: Any = None,
    factor: Any = None,
    context: str = "grid_refine",
) -> Tuple[str, int, Optional[int]]:
    """Validate the explicit card-level ``mode`` representation."""
    if not isinstance(mode, str):
        raise ValueError(f"{context}.mode must be 'none' or 'boundary'")
    normalized_mode = mode.strip().lower()
    if normalized_mode == "none":
        if n_layers is not None or factor is not None:
            raise ValueError(
                f"{context} mode 'none' must omit factor and n_layers"
            )
        return "none", 0, None
    if normalized_mode != "boundary":
        raise ValueError(f"{context}.mode must be 'none' or 'boundary'")
    if (isinstance(n_layers, Integral) and not isinstance(n_layers, bool)
            and int(n_layers) == 0):
        raise ValueError(
            f"{context} mode 'boundary' requires n_layers >= 1"
        )
    layers, normalized_factor = normalize_grid_refinement(
        n_layers=n_layers,
        factor=factor,
        context=context,
    )
    if layers == 0:
        raise ValueError(
            f"{context} mode 'boundary' requires n_layers >= 1"
        )
    return "boundary", layers, normalized_factor
