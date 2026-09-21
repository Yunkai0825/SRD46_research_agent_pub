"""
system_resolution — Bridge between FreeEnergyReport and solver arrays.
======================================================================

Public API
----------
- ``BuiltSystem``                      — solver-ready container
- ``build_from_free_energy_report()``  — FreeEnergyReport → BuiltSystem
"""

from .built_system_from_dGreport import BuiltSystem, build_from_free_energy_report

__all__ = ["BuiltSystem", "build_from_free_energy_report"]
