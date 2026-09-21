"""
general_text_context_marker_catalog
====================================
Centralized registry of **all** XML-style context markers used by the
ThermoML ReAct agent pipeline.

Every marker (tag string **and** compiled regex) is defined once in
``context_markers.py`` and exposed through the canonical ``MARKERS`` registry.

Usage::

    from ...general_text_context_marker_catalog import (
        MARKERS,
        ALL_CONTEXT_MARKERS_RE,
    )
"""

from .context_markers import ALL_CONTEXT_MARKERS_RE, ContextMarkerCatalog, MARKERS, TagPair, strip_reasoning

__all__ = ["TagPair", "ContextMarkerCatalog", "MARKERS", "ALL_CONTEXT_MARKERS_RE", "strip_reasoning"]
