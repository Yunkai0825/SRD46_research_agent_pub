"""
grid_solver_sweep_retry_patching
================================
Package-private helpers for the coarse N-D grid solver.

All modules in this package are called *only* from
``NDGridSolver`` (via :meth:`NDGridSolver.solve`) or from the
boundary refiner / downstream fine-label-map assembler.  External
code must go through ``NDGridSolver``.

Modules
-------
- :mod:`solver_sweep_and_seed`  — phases 1-3: seed, BFS flood-fill,
  axis sweeps.
- :mod:`solver_retry_helpers`   — phases 4-5: back-scan retry and
  interpolation retry on cells still unconverged after the sweeps.
- :mod:`solver_hole_patcher`    — sub-grid hole patching used by the
  multi-layer boundary refiner and by the fine-label-map assembler.
"""
