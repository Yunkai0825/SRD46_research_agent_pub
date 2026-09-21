"""
point_solver.py
===============
Newton-Raphson solver for a single (pH, E) grid point.

Solves the element/ligand mass-balance system using log-space unknowns.
Core numerical methods (residual/Jacobian assembly, NR iteration with
line search) are in ``eq_numerical_methods``.  This module wraps them
with Pourbaix-specific setup (pH/E conversion, initial guesses).
"""

from __future__ import annotations

import numpy as np
from typing import Optional, Tuple

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).absolute().parents[1]))

from solver_settings import (
    NEWTON_TOL, NEWTON_MAX_ITER, BACKTRACK_MAX,
    DAMPING_INITIAL, FALLBACK_STEP, MIN_LOG, MAX_LOG,
    NERNST_FACTOR, DEBUG,
)
from numerical_solvers.eq_numerical_methods import (
    residual_jacobian,
    expanded_residual_jacobian,
    newton_solve,
)


class PourbaixPointSolver:
    """Solve aqueous speciation at one (pH, E) point."""

    def __init__(self, log_beta_eff: np.ndarray, stoich_pq: np.ndarray,
                 stoich_r: np.ndarray, stoich_s: np.ndarray,
                 nu_matrix: np.ndarray, n_basis: int,
                 debug: bool = False):
        """
        Pre-cache numpy arrays from BuiltSystem for fast
        residual/Jacobian evaluation.

        Parameters
        ----------
        log_beta_eff : (N_aq,) effective formation constants
        stoich_pq    : (N_aq, N_basis) combined element + ligand stoich
        stoich_r     : (N_aq,) H+ coefficients
        stoich_s     : (N_aq,) e- coefficients
        nu_matrix    : (N_basis, N_aq) mass-balance multipliers
        n_basis      : number of basis unknowns
        debug        : print debug messages
        """
        self.log_beta_eff = log_beta_eff.copy()
        self.stoich_pq = stoich_pq.copy()
        self.stoich_r = stoich_r.copy()
        self.stoich_s = stoich_s.copy()
        self.nu_matrix = nu_matrix.copy()
        self.n_basis = n_basis
        self.n_species = len(log_beta_eff)
        self.debug = debug

    def update_log_beta_eff(self, new_values: np.ndarray) -> None:
        """Replace log_beta_eff in-place (for auto-I iteration)."""
        np.copyto(self.log_beta_eff, new_values)

    @staticmethod
    def _initial_log_basis(C_all: np.ndarray) -> np.ndarray:
        """Map declared totals to a finite log-basis initial guess.

        Exact zero totals are physical absence constraints, not an implicit
        concentration floor.  Their corresponding variables are initialized
        at ``MIN_LOG`` and pinned there by the residual/Jacobian assembly.
        """
        totals = np.asarray(C_all, dtype=float)
        x_init = np.full(totals.shape, MIN_LOG, dtype=float)
        positive = totals > 0.0
        x_init[positive] = np.log10(totals[positive])
        return x_init

    def _log_electron_activity(
        self,
        E_V: Optional[float],
        *extra_electron_stoich: np.ndarray,
    ) -> float:
        """Resolve log(e-) while distinguishing absent E from zero volts."""
        electron_rows = (self.stoich_s, *extra_electron_stoich)
        has_electron_term = any(
            np.any(np.abs(np.asarray(row, dtype=float)) > 1e-12)
            for row in electron_rows
        )
        if E_V is None:
            if has_electron_term:
                raise ValueError(
                    "E_V is 'Not defined' but electron stoichiometry is "
                    "nonzero; declare a potential or exclude redox before "
                    "constructing the numerical system")
            return 0.0
        if isinstance(E_V, bool) or not np.isfinite(float(E_V)):
            raise ValueError(f"E_V must be a finite number, got {E_V!r}")
        return -float(E_V) / NERNST_FACTOR

    def residual_jacobian(
        self,
        x: np.ndarray,
        logH: float,
        logE: float,
        C_all: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Compute residual f, Jacobian J, and species concentrations c."""
        return residual_jacobian(
            x, logH, logE, C_all,
            self.log_beta_eff, self.stoich_pq,
            self.stoich_r, self.stoich_s, self.nu_matrix,
        )

    def solve_aqueous(
        self,
        pH: float,
        E_V: Optional[float],
        C_all: np.ndarray,
        x0: Optional[np.ndarray] = None,
        deadline_t: float = 0.0,
    ) -> Tuple[np.ndarray, bool, int, float, np.ndarray]:
        """Pure aqueous solve (no solids) at one (pH, E) point.

        Returns (x, converged, iters, res_norm, c).
        """
        logH = -pH
        # With redox excluded, electron stoichiometries are identically zero
        # and E is absent.  A neutral multiplier is sufficient internally;
        # it is not a reported or assumed potential.
        logE = self._log_electron_activity(E_V)

        if x0 is None:
            x_init = self._initial_log_basis(C_all)
        else:
            x_init = x0.copy()

        def _rj(x):
            return residual_jacobian(
                x, logH, logE, C_all,
                self.log_beta_eff, self.stoich_pq,
                self.stoich_r, self.stoich_s, self.nu_matrix,
            )

        return newton_solve(
            x_init, _rj,
            deadline_t=deadline_t, debug=self.debug,
        )

    def solve_expanded(
        self,
        pH: float,
        E_V: Optional[float],
        C_all: np.ndarray,
        active_solid_p: np.ndarray,
        active_solid_r: np.ndarray,
        active_solid_s: np.ndarray,
        active_solid_logK: np.ndarray,
        active_solid_nu: np.ndarray,
        x0: Optional[np.ndarray] = None,
        ns0: Optional[np.ndarray] = None,
        deadline_t: float = 0.0,
    ) -> Tuple[np.ndarray, np.ndarray, bool, int, float, np.ndarray]:
        """Solve expanded system with active solids.

        Returns (x, n_s, converged, iters, res_norm, c).
        """
        logH = -pH
        logE = self._log_electron_activity(E_V, active_solid_s)
        N = self.n_basis
        K = len(active_solid_logK)

        if x0 is None:
            x_init = self._initial_log_basis(C_all)
        else:
            x_init = x0.copy()
        x_init = np.clip(x_init, MIN_LOG, MAX_LOG)

        if ns0 is None:
            ns_init = np.full(K, 1e-10)
        else:
            ns_init = ns0.copy()

        z0 = np.concatenate([x_init, ns_init])

        def _rj(z):
            xv, nsv = z[:N], z[N:]
            f, J, c = expanded_residual_jacobian(
                xv, nsv, logH, logE, C_all,
                self.log_beta_eff, self.stoich_pq,
                self.stoich_r, self.stoich_s, self.nu_matrix,
                active_solid_p, active_solid_r, active_solid_s,
                active_solid_logK, active_solid_nu,
            )
            return f, J, c

        def _clip(z):
            z[:N] = np.clip(z[:N], MIN_LOG, MAX_LOG)
            z[N:] = np.maximum(z[N:], 0.0)
            return z

        z, conv, iters, res_norm, c = newton_solve(
            z0, _rj, clip_fn=_clip,
            deadline_t=deadline_t, debug=self.debug,
        )

        x_out = z[:N]
        ns_out = z[N:]

        if self.debug and not conv:
            print(f"    [NR-expanded] NOT converged, ||f|| = {res_norm:.2e}")

        return x_out, ns_out, conv, iters, res_norm, c


    def solve_augmented(
        self,
        pH: float,
        E_V: Optional[float],
        C_all: np.ndarray,
        active_solid_p: np.ndarray,
        active_solid_r: np.ndarray,
        active_solid_s: np.ndarray,
        active_solid_logK: np.ndarray,
        active_solid_nu: np.ndarray,
        pin_species_rows: np.ndarray,
        pin_targets: np.ndarray,
        released_idx: np.ndarray,
        C_ref: np.ndarray,
        x0: Optional[np.ndarray] = None,
        ns0: Optional[np.ndarray] = None,
        T0: Optional[np.ndarray] = None,
        deadline_t: float = 0.0,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, bool, int, float, np.ndarray]:
        """Solve the fully augmented system (mass + solids + species pins).

        Unknown vector ``z = [x (N) ; n_s (K) ; T_rel (P)]``.  Each pin
        adds one constraint row and releases one component total
        (``released_idx``), keeping the system square (``P`` pins ⇒ ``P``
        released totals).  Falls through to the existing expanded/aqueous
        solvers when ``P == 0``.

        Returns ``(x, n_s, T_rel, converged, iters, res_norm, c)``.
        """
        logH = -pH
        logE = self._log_electron_activity(E_V, active_solid_s)
        N = self.n_basis
        K = len(active_solid_logK)
        P = len(pin_targets)

        if x0 is None:
            x_init = self._initial_log_basis(C_all)
        else:
            x_init = x0.copy()
        x_init = np.clip(x_init, MIN_LOG, MAX_LOG)

        ns_init = (np.full(K, 1e-10) if ns0 is None else ns0.copy())

        # Released-total unknowns: warm-start from the baseline totals
        # (the fixed C_all value at each released component) unless given.
        if T0 is None:
            T_init = np.array([max(float(C_all[int(k)]), 1e-12)
                               for k in released_idx], dtype=float)
        else:
            T_init = T0.copy()

        z0 = np.concatenate([x_init, ns_init, T_init])

        from numerical_solvers.eq_numerical_methods import (
            augmented_residual_jacobian,
        )

        def _rj(z):
            xv = z[:N]
            nsv = z[N:N + K]
            tv = z[N + K:]
            return augmented_residual_jacobian(
                xv, nsv, tv, logH, logE, C_all,
                self.log_beta_eff, self.stoich_pq,
                self.stoich_r, self.stoich_s, self.nu_matrix,
                active_solid_p, active_solid_r, active_solid_s,
                active_solid_logK, active_solid_nu,
                pin_species_rows, pin_targets, released_idx, C_ref,
            )

        def _clip(z):
            z[:N] = np.clip(z[:N], MIN_LOG, MAX_LOG)
            z[N:N + K] = np.maximum(z[N:N + K], 0.0)
            z[N + K:] = np.maximum(z[N + K:], 0.0)   # released totals ≥ 0
            return z

        z, conv, iters, res_norm, c = newton_solve(
            z0, _rj, clip_fn=_clip,
            deadline_t=deadline_t, debug=self.debug,
        )

        x_out = z[:N]
        ns_out = z[N:N + K]
        T_out = z[N + K:]

        if self.debug and not conv:
            print(f"    [NR-augmented] NOT converged, ||f|| = {res_norm:.2e}")

        return x_out, ns_out, T_out, conv, iters, res_norm, c


# ---------------------------------------------------------------------------
#  Self-test
# ---------------------------------------------------------------------------
