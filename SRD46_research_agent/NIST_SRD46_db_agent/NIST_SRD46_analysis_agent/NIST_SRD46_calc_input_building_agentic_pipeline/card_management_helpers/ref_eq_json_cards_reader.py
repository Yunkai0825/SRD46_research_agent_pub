"""ref_eq_json_cards_reader.py
Read a ref-eq JSON card into a ``FreeEnergyReport``.

This is the JSON counterpart of ``free_energy_md_card_reader.py``.  A
ref-eq JSON card is the per-metal-ligand-pair card emitted by the
``ref_eq_SRD46_json_cards_builder`` (``components`` + ``equations``
sections).  Computing the standard chemical potentials over that
network yields the same ``FreeEnergyReport`` dataclass that the MD
generator (``ref_eq_free_energy_md_card_generation.py``) consumes.

Design goals:
  • Symmetric with the MD reader: both readers return a
    ``FreeEnergyReport``.
  • Accepts either a path (``str``/``Path`` to a ``.json`` file) or an
    already-parsed ``dict`` (the card_json returned by the builder).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Union

from thermodynamics_helpers.gibbs_value_calc_from_logK_eq_map_helpers.free_energy_network_calc_helper import (
    FreeEnergyReport,
    compute_free_energy_network,
)


def parse_ref_eq_json_card(
    source: Union[str, Path, dict],
    *,
    temperature_K: Optional[float] = None,
) -> FreeEnergyReport:
    """Parse a ref-eq JSON card into a ``FreeEnergyReport``.

    Parameters
    ----------
    source : str | Path | dict
        Path to a ref-eq ``.json`` card, or the already-parsed card
        dict (``components`` + ``equations``).
    temperature_K : float, optional
        Override the reference temperature (Kelvin).

    Returns
    -------
    FreeEnergyReport
    """
    if isinstance(source, dict):
        raw = source
    else:
        raw = json.loads(Path(source).read_text(encoding="utf-8"))

    return compute_free_energy_network(raw, temperature_K=temperature_K)
