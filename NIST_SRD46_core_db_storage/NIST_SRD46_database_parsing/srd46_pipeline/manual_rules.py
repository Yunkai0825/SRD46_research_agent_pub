"""Compatibility imports for the chemistry rules in :mod:`.chem_rules_lib`.

Definitions live in the family modules under ``srd46_pipeline/chem_rules_lib``.
This facade preserves existing parser imports and the historical
``manual_rules.<RULE-ID>`` provenance identifiers. Validation and the CLI rule
listing still operate on the same shared registry.
"""
from .chem_rules_lib import *  # noqa: F401,F403 - compatibility API
from .chem_rules_lib import __all__
