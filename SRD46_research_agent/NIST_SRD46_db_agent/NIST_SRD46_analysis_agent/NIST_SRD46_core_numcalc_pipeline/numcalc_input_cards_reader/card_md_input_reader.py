"""
card_md_input_reader.py
=============
Resolve a *card source* into a ``FreeEnergyReport``.

A card source can be:

  - ``FreeEnergyReport``                 — used as-is.
  - ``Path`` / ``str`` ending in ``.md`` — parsed with the MD card reader.
  - ``Path`` / ``str`` directory         — searched for a free-energy card:
      preferred ``free_energy_card_enriched.md``, fallback
      ``free_energy_card.md``, fallback ``free_energy_card_with_include.md``.
  - ``Path`` / ``str`` ending in ``.json`` — treated as an
    equilibrium-network spec and passed to ``compute_free_energy_network``.
  - ``dict``                             — same as JSON spec, in-memory.

Card-building inputs (the equilibrium-network JSONs in
``_DEBUG_input/``) are deliberately distinct from the calculation-modes
input handled by :mod:`input_entry_points.calc_input`.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any, Optional, Union

# Put the calc-tools root on sys.path so bare imports inside the helpers
# (e.g. ``from free_energy_md_card_reader import …``) resolve.
_THIS = pathlib.Path(__file__).absolute()
_CALC_ROOT = _THIS.parent.parent
_CARD_IO = (_CALC_ROOT / "input_entry_points" /
            "card_pipeline" / "card_md_io")
for p in (_CALC_ROOT, _CARD_IO):
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))


_CARD_FILE_PRIORITY = (
    "free_energy_card_numcalc.md",
    "free_energy_card_enriched.md",
    "free_energy_card.md",
    "free_energy_card_with_include.md",
)


def _find_card_in_dir(directory: pathlib.Path) -> pathlib.Path:
    for name in _CARD_FILE_PRIORITY:
        candidate = directory / name
        if candidate.exists():
            return candidate
    # Last resort: any *.md file directly inside the directory.
    md_files = sorted(directory.glob("*.md"))
    if md_files:
        return md_files[0]
    raise FileNotFoundError(
        f"No free-energy card found in {directory}. "
        f"Looked for: {_CARD_FILE_PRIORITY}")


def resolve_card_source(
    source: Union[str, pathlib.Path, dict, Any],
    *,
    temperature_K: Optional[float] = None,
):
    """Return a ``FreeEnergyReport`` from any supported source form."""
    from thermodynamics_helpers.gibbs_value_calc_from_logK_eq_map_helpers.free_energy_network_calc_helper import (
        compute_free_energy_network, FreeEnergyReport,
    )

    if isinstance(source, FreeEnergyReport):
        return source

    if isinstance(source, dict):
        return compute_free_energy_network(source, temperature_K=temperature_K)

    if isinstance(source, (str, pathlib.Path)):
        p = pathlib.Path(source)
        if p.is_dir():
            p = _find_card_in_dir(p)
        if p.suffix.lower() == ".md":
            from free_energy_md_card_reader import parse_free_energy_card_md
            return parse_free_energy_card_md(p)
        # JSON or any other extension → treat as spec
        return compute_free_energy_network(str(p), temperature_K=temperature_K)

    raise TypeError(
        f"Unsupported card source type: {type(source).__name__}")
