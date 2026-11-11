"""Compatibility exports for effective N-D label-map assembly.

The implementation lives with the solver because the exact same final field
is the causal source for ``ElementResult.topology`` and every persisted
artifact.  Existing output-layer imports remain valid through these aliases.
"""

from solvers_and_topology.nd_grid.effective_label_map import (
    EffectiveLabelMap,
    build_and_patch_effective_label_map,
    build_and_patch_fine_label_map,
    compose_effective_label_map,
    compose_fine_label_map,
)


__all__ = [
    "EffectiveLabelMap",
    "compose_effective_label_map",
    "build_and_patch_effective_label_map",
    "compose_fine_label_map",
    "build_and_patch_fine_label_map",
]
