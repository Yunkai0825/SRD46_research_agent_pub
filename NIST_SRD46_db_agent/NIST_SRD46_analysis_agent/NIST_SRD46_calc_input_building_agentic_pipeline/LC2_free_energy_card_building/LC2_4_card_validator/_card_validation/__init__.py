"""Card-validation engine for LC2_4.

Dynamically imports the SOLVER's own card resolver
(``numcalc_input_cards_reader.resolve_card_source``) and runs it against
a free-energy card.  No parser is re-implemented here.
"""
from .solver_parse_check import (
    SolverParseResult,
    validate_card_text,
    validate_card_with_solver,
)

__all__ = [
    "SolverParseResult",
    "validate_card_text",
    "validate_card_with_solver",
]
