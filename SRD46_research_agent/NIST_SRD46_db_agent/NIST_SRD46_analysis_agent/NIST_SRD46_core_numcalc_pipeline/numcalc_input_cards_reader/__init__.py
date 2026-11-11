"""
numcalc_cards_reader
====================
Two distinct input families consumed by the calc-tools entry point
(:mod:`SRD46_numcalculator_api`):

* **Card source** — a free-energy MD card (path, directory, or in-memory
  ``FreeEnergyReport``).  Resolved by :mod:`numcalc_cards_reader.card_input`.
* **Calculation-modes input** — a JSON describing *what* sweep to run
  (sweep_method, axes, ionic strength, concentrations, …).  Schema in
  :mod:`numcalc_cards_reader.calc_input`.

Public re-exports for convenience::

    from numcalc_cards_reader import (
        CalcInput, load_calc_input, dump_calc_input,
        SUPPORTED_SWEEP_METHODS,
        resolve_card_source,
    )
"""
from .calc_json_input_reader import (
    CalcInput,
    SweepAxis,
    IonicStrengthSpec,
    GridRefineSpec,
    SUPPORTED_SWEEP_METHODS,
    load_calc_input,
    dump_calc_input,
)
from .card_md_input_reader import resolve_card_source

__all__ = [
    "CalcInput",
    "SweepAxis",
    "IonicStrengthSpec",
    "GridRefineSpec",
    "SUPPORTED_SWEEP_METHODS",
    "load_calc_input",
    "dump_calc_input",
    "resolve_card_source",
]
