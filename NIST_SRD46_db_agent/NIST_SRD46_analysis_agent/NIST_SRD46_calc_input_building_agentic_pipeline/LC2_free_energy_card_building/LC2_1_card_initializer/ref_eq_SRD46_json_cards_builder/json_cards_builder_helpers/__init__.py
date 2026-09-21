"""Builder helpers — DB queries, auto-fetch, caching, and pipeline stages."""

from __future__ import annotations

import os


# This package crosses the legacy Windows MAX_PATH boundary on the standard
# network workspace.  Let importlib discover the leaf modules through an
# extended-length spelling while retaining the ordinary path for diagnostics.
if os.name == "nt":
    _package_dir = os.path.abspath(os.path.dirname(__file__))
    _extended = (
        "\\\\?\\UNC\\" + _package_dir[2:]
        if _package_dir.startswith("\\\\")
        else "\\\\?\\" + _package_dir
    )
    if _extended not in __path__:
        __path__.insert(0, _extended)

from .component_builder import build_components_from_ids_json
from .equation_builder import (
    build_card_from_component_template,
    build_equations_from_map_json,
    build_final_card,
    recompute_include_calculation,
)
from .auto_fetch import (
    auto_fetch_hydroxide_networks,
    auto_fetch_pka_networks,
    auto_fetch_primary_network,
    auto_fetch_valence_networks,
)
from .ref_card_cache import build_ref_card_filename, find_existing_ref_card
from .single_pair_pipeline import (
    render_card_from_eq_map_files,
    write_eq_map_artefacts,
)
from .lc1_2_patch_adapter import lc1_2_patches_to_vlm_overrides

__all__ = [
    "build_components_from_ids_json",
    "build_card_from_component_template",
    "build_equations_from_map_json",
    "build_final_card",
    "recompute_include_calculation",
    "auto_fetch_hydroxide_networks",
    "auto_fetch_pka_networks",
    "auto_fetch_primary_network",
    "auto_fetch_valence_networks",
    "build_ref_card_filename",
    "find_existing_ref_card",
    "render_card_from_eq_map_files",
    "write_eq_map_artefacts",
    "lc1_2_patches_to_vlm_overrides",
]
