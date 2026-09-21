"""
eq_numerical_methods.py
=======================
Core numerical methods for equilibrium solvers:

* ``residual_jacobian``          — mass-balance residual + Jacobian assembly
* ``expanded_residual_jacobian`` — extended system (aqueous + active solids)
* ``compute_log_concentrations`` — species log-conc and conc from solver arrays
* ``compute_saturation_index``   — saturation index for dissolution equilibria
* ``newton_solve``               — generic Newton-Raphson loop with
                                   backtracking line search, damping,
                                   steepest-descent fallback, and
                                   best-solution tracking
* ``compute_saturation_index``   — saturation index for dissolution equilibria

These are pure numerical functions with **no** references to domain
dataclasses (``BuiltSystem``, ``SolverPointResult``, etc.).
They operate entirely on numpy arrays.
"""

from __future__ import annotations

import time as _time
import numpy as np
from typing import Callable, Optional, Tuple

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).absolute().parents[1]))

from solver_settings import (
    NEWTON_TOL, NEWTON_MAX_ITER, BACKTRACK_MAX,
    DAMPING_INITIAL, FALLBACK_STEP, MIN_LOG, MAX_LOG, LN10,
    LM_LAMBDA_INIT, LM_LAMBDA_MIN, LM_LAMBDA_MAX,
    LM_GAIN_GOOD, LM_GAIN_POOR, LM_FACTOR_UP, LM_FACTOR_DOWN,
    ARMIJO_C1, JACOBIAN_EQUIL,
)

LOG10 = LN10  # ln(10)


# ---------------------------------------------------------------------------
#  Residual + Jacobian assembly
# ---------------------------------------------------------------------------

def residual_jacobian(
    x: np.ndarray,
    logH: float,
    logE: float,
    C_all: np.ndarray,
    log_beta_eff: np.ndarray,
    stoich_pq: np.ndarray,
    stoich_r: np.ndarray,
    stoich_s: np.ndarray,
    nu_matrix: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute mass-balance residual, Jacobian, and species concentrations.

    Parameters
    ----------
    x            : (N_basis,) log10[free basis species]
    logH         : log10[H+]
    logE         : log10[e-]
    C_all        : (N_basis,) total concentrations
    log_beta_eff : (N_aq,) effective formation constants
    stoich_pq    : (N_aq, N_basis) element + ligand stoichiometry
    stoich_r     : (N_aq,) H+ coefficients
    stoich_s     : (N_aq,) e- coefficients
    nu_matrix    : (N_basis, N_aq) mass-balance multipliers

    Returns
    -------
    f : (N_basis,) normalised residual  ``(sum - T) / T``
    J : (N_basis, N_basis) Jacobian
    c : (N_aq,) species concentrations (mol/L)
    """
    log_c = log_beta_eff + stoich_pq @ x + stoich_r * logH + stoich_s * logE
    # Only clip below (negligible species → 0).  Do NOT clip above:
    # the upper clip flattens the cost landscape and stalls Newton
    # when dominant species have huge raw concentrations far from
    # equilibrium (e.g. pH > 12, high |E|).
    log_c_raw = np.clip(log_c, MIN_LOG, None)
    c = np.power(10.0, log_c_raw)

    sums = nu_matrix @ c            # (N_basis,)

    # An explicitly declared zero analytical total is a valid physical
    # constraint: that conserved component is absent.  A log-concentration
    # variable cannot represent mathematical zero, so pin its free-basis
    # value to the numerical floor instead of forming the undefined 0/0
    # normalised mass-balance row.  Positive totals retain the original
    # relative residual exactly.
    zero_total = C_all == 0.0
    scale = np.where(zero_total, 1.0, C_all)
    f = (sums - C_all) / scale

    dc_dx = c[:, None] * stoich_pq * LOG10   # (N_aq, N_basis)
    J = (nu_matrix @ dc_dx) / scale[:, None]
    if np.any(zero_total):
        f[zero_total] = x[zero_total] - MIN_LOG
        J[zero_total, :] = 0.0
        zero_idx = np.flatnonzero(zero_total)
        J[zero_idx, zero_idx] = 1.0

    # Return display-safe concentrations (clipped for aux output)
    c_safe = np.power(10.0, np.clip(log_c, MIN_LOG, MAX_LOG))
    return f, J, c_safe


def expanded_residual_jacobian(
    x: np.ndarray,
    n_s: np.ndarray,
    logH: float,
    logE: float,
    C_all: np.ndarray,
    log_beta_eff: np.ndarray,
    stoich_pq: np.ndarray,
    stoich_r: np.ndarray,
    stoich_s: np.ndarray,
    nu_matrix: np.ndarray,
    solid_p: np.ndarray,
    solid_r: np.ndarray,
    solid_s: np.ndarray,
    solid_logK: np.ndarray,
    solid_nu: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Residual and Jacobian for the expanded aqueous + solids system.

    Parameters
    ----------
    x, n_s       : aqueous log-concs (N,) and solid amounts (K,)
    solid_p      : (K, N_basis) stoich for saturation constraints
    solid_r/s    : (K,) H+ / e- coefficients for solids
    solid_logK   : (K,) effective dissolution logK
    solid_nu     : (K, N_basis) mass-balance contribution per mol

    Returns
    -------
    f_full : (N+K,) concatenated residual [mass-balance ; saturation]
    J_full : (N+K, N+K) expanded Jacobian
    c      : (N_aq,) species concentrations
    """
    N = len(x)
    K = len(n_s)

    # Aqueous block
    f_aq, J_aq, c = residual_jacobian(
        x, logH, logE, C_all,
        log_beta_eff, stoich_pq, stoich_r, stoich_s, nu_matrix,
    )

    zero_total = C_all == 0.0
    scale = np.where(zero_total, 1.0, C_all)

    # Solid contribution to mass balance
    for k in range(K):
        f_aq += solid_nu[k, :] * n_s[k] / scale
    if np.any(zero_total):
        # Keep an absent component pinned even in the expanded system.
        # A solid requiring that component is strongly undersaturated at
        # x=MIN_LOG and therefore cannot become a physical active phase.
        f_aq[zero_total] = x[zero_total] - MIN_LOG

    # Saturation constraints: logK_stored + p*x + r*logH + s*logE = 0
    g_sat = solid_logK + solid_p @ x + solid_r * logH + solid_s * logE

    f_full = np.concatenate([f_aq, g_sat])

    # Expanded Jacobian (N+K) x (N+K)
    J_full = np.zeros((N + K, N + K))
    J_full[:N, :N] = J_aq                                 # top-left
    for k in range(K):                                     # top-right
        J_full[:N, N + k] = solid_nu[k, :] / scale
    if np.any(zero_total):
        zero_idx = np.flatnonzero(zero_total)
        J_full[zero_idx, N:N + K] = 0.0
    J_full[N:, :N] = solid_p                               # bottom-left
    # bottom-right = 0

    return f_full, J_full, c


def augmented_residual_jacobian(
    x: np.ndarray,
    n_s: np.ndarray,
    T_rel: np.ndarray,
    logH: float,
    logE: float,
    C_all: np.ndarray,
    log_beta_eff: np.ndarray,
    stoich_pq: np.ndarray,
    stoich_r: np.ndarray,
    stoich_s: np.ndarray,
    nu_matrix: np.ndarray,
    solid_p: np.ndarray,
    solid_r: np.ndarray,
    solid_s: np.ndarray,
    solid_logK: np.ndarray,
    solid_nu: np.ndarray,
    pin_species_rows: np.ndarray,
    pin_targets: np.ndarray,
    released_idx: np.ndarray,
    C_ref: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Residual + Jacobian for the fully augmented system.

    Combines three coupled blocks (any of solids / pins may be empty):

    * **mass balance** for every component ``k``.  For a *released*
      component (one whose total is an unknown ``T``), the fixed total
      ``C_all[k]`` is replaced by the unknown and the row is normalised
      by the fixed reference scale ``C_ref[k]`` (so the divisor stays
      constant and the row remains well conditioned).  All other rows
      keep the existing ``(sum - C)/C`` normalisation.
    * **solid saturation** for every active solid (same as
      ``expanded_residual_jacobian``).
    * **species pins**, one per pinned species ``j``:
      ``g = (logβ_eff_j + pq_j·x + r_j·logH + s_j·logE) - ℓ_j = 0``,
      which is *linear* in ``x``.

    Unknown vector ordering ``z = [x (N) ; n_s (K) ; T_rel (P)]``;
    residual ordering ``[mass (N) ; saturation (K) ; pin (P)]``.  The
    system is square iff ``len(T_rel) == len(pin_targets)`` (the DOF
    rule ``|U| == |P|`` enforced upstream).

    Parameters
    ----------
    x                : (N,)  log10[free basis species]
    n_s              : (K,)  active-solid amounts
    T_rel            : (P,)  unknown released totals (parallel to
                             ``released_idx``)
    pin_species_rows : (P,)  aqueous row index ``j`` of each pinned species
    pin_targets      : (P,)  pin targets ``ℓ`` (log10 concentration)
    released_idx     : (P,)  basis component index released per unknown total
    C_ref            : (N,)  fixed normalisation scale for released rows

    Returns
    -------
    f_full : (N+K+P,)        concatenated residual
    J_full : (N+K+P, N+K+P)  block Jacobian
    c      : (N_aq,)         species concentrations (display-clipped)
    """
    N = len(x)
    K = len(n_s)
    P = len(pin_targets)

    # Species log-concentrations (un-clipped form used for pin rows so
    # the constraint stays exact; clip only below for the mass sums).
    log_c = log_beta_eff + stoich_pq @ x + stoich_r * logH + stoich_s * logE
    c = np.power(10.0, np.clip(log_c, MIN_LOG, None))

    sums = nu_matrix @ c                                  # (N,)
    for k in range(K):
        sums = sums + solid_nu[k, :] * n_s[k]

    # Per-row target total and normalisation scale.  Released rows take
    # the unknown total and the fixed reference scale.
    target = C_all.copy().astype(float)
    released_mask = np.zeros(N, dtype=bool)
    scale = np.where(C_all == 0.0, 1.0, C_all).astype(float)
    for i in range(P):
        k = int(released_idx[i])
        released_mask[k] = True
        target[k] = T_rel[i]
        scale[k] = C_ref[k]

    f_mass = (sums - target) / scale
    fixed_zero = (C_all == 0.0) & ~released_mask
    if np.any(fixed_zero):
        f_mass[fixed_zero] = x[fixed_zero] - MIN_LOG

    g_sat = (solid_logK + solid_p @ x + solid_r * logH + solid_s * logE
             if K > 0 else np.zeros(0))

    g_pin = np.empty(P)
    for p in range(P):
        g_pin[p] = log_c[int(pin_species_rows[p])] - pin_targets[p]

    f_full = np.concatenate([f_mass, g_sat, g_pin])

    # ── Block Jacobian (N+K+P) x (N+K+P) ──
    M = N + K + P
    J_full = np.zeros((M, M))

    # Mass-balance rows wrt x: ν · diag(c) · pq · ln10, row-scaled.
    dc_dx = c[:, None] * stoich_pq * LOG10                # (N_aq, N)
    J_full[:N, :N] = (nu_matrix @ dc_dx) / scale[:, None]

    # Mass-balance rows wrt solid amounts.
    for k in range(K):
        J_full[:N, N + k] = solid_nu[k, :] / scale

    # Mass-balance rows wrt released totals: ∂f_k/∂T_i = −1/scale[k].
    for i in range(P):
        k = int(released_idx[i])
        J_full[k, N + K + i] = -1.0 / scale[k]

    if np.any(fixed_zero):
        zero_idx = np.flatnonzero(fixed_zero)
        J_full[zero_idx, :] = 0.0
        J_full[zero_idx, zero_idx] = 1.0

    # Saturation rows wrt x.
    if K > 0:
        J_full[N:N + K, :N] = solid_p

    # Pin rows wrt x (constant pq rows; linear constraint).
    for p in range(P):
        J_full[N + K + p, :N] = stoich_pq[int(pin_species_rows[p]), :]

    c_safe = np.power(10.0, np.clip(log_c, MIN_LOG, MAX_LOG))
    return f_full, J_full, c_safe


# ---------------------------------------------------------------------------
#  Species concentration helpers
# ---------------------------------------------------------------------------

def compute_log_concentrations(
    x: np.ndarray,
    logH: float,
    logE: float,
    log_beta_eff: np.ndarray,
    stoich_pq: np.ndarray,
    stoich_r: np.ndarray,
    stoich_s: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute log-concentrations and concentrations for all species.

    Returns
    -------
    log_c : (N_aq,) clipped log10 concentrations
    c     : (N_aq,) concentrations (mol/L)
    """
    log_c = log_beta_eff + stoich_pq @ x + stoich_r * logH + stoich_s * logE
    log_c = np.clip(log_c, MIN_LOG, MAX_LOG)
    c = np.power(10.0, log_c)
    return log_c, c


# ---------------------------------------------------------------------------
#  Saturation index
# ---------------------------------------------------------------------------

def compute_saturation_index(
    x: np.ndarray,
    logH: float,
    logE: float,
    diss_logK: np.ndarray,
    diss_p: np.ndarray,
    diss_r: np.ndarray,
    diss_s: np.ndarray,
) -> np.ndarray:
    """Saturation index for all dissolution equilibria.

    ``SI = diss_logK + p @ x + r * logH + s * logE``

    SI > 0 indicates supersaturation (solid should precipitate).
    """
    return diss_logK + diss_p @ x + diss_r * logH + diss_s * logE


# ---------------------------------------------------------------------------
#  Newton-Raphson driver
# ---------------------------------------------------------------------------

def _equilibrate_jacobian(J, f):
    """Row/column equilibration of J and f.

    Returns (J_eq, f_eq, D_row, D_col) where
        J_eq = diag(1/D_row) @ J @ diag(1/D_col)
        f_eq = f / D_row
    After solving J_eq @ dx_eq = -f_eq, recover dx = dx_eq / D_col.
    """
    _EPS = 1e-30
    D_row = np.maximum(np.max(np.abs(J), axis=1), _EPS)
    J_eq = J / D_row[:, None]
    f_eq = f / D_row
    D_col = np.maximum(np.max(np.abs(J_eq), axis=0), _EPS)
    J_eq = J_eq / D_col[None, :]
    return J_eq, f_eq, D_row, D_col


def _cauchy_point(J, f):
    """Optimal steepest-descent step (Cauchy point).

    Minimises ||f + J dx||^2 along dx = -alpha * J^T f.
    Returns the dx vector.
    """
    g = J.T @ f                          # gradient of 0.5*||f||^2
    Jg = J @ g
    denom = np.dot(Jg, Jg)
    if denom < 1e-60:
        return -g * FALLBACK_STEP         # degenerate: tiny fixed step
    alpha_sd = np.dot(g, g) / denom
    return -alpha_sd * g


def newton_solve(
    x0: np.ndarray,
    residual_and_jacobian: Callable[
        [np.ndarray], Tuple[np.ndarray, np.ndarray, np.ndarray]
    ],
    clip_fn: Optional[Callable[[np.ndarray], np.ndarray]] = None,
    tol: float = NEWTON_TOL,
    max_iter: int = NEWTON_MAX_ITER,
    backtrack_max: int = BACKTRACK_MAX,
    damping: float = DAMPING_INITIAL,
    fallback_step: float = FALLBACK_STEP,
    deadline_t: float = 0.0,
    debug: bool = False,
) -> Tuple[np.ndarray, bool, int, float, np.ndarray]:
    """Newton-Raphson with Jacobian equilibration, LM damping, and
    Armijo line search.

    Parameters
    ----------
    x0 : initial guess (will be copied).
    residual_and_jacobian :
        ``f(x) -> (residual, Jacobian, aux)`` where ``aux`` is any
        auxiliary output (e.g. species concentrations) passed through
        unchanged.
    clip_fn :
        Optional ``clip(x) -> x_clipped``.  Applied after every step.
        Default clips to ``[MIN_LOG, MAX_LOG]``.
    tol, max_iter, backtrack_max, damping, fallback_step :
        Standard NR control parameters.
    deadline_t :
        ``time.perf_counter()`` value at which to abort (0 = no limit).
    debug : print diagnostics on slow convergence.

    Returns
    -------
    x        : best solution found
    converged: True if ||f|| < tol
    iters    : number of iterations used
    res_norm : final ||f||
    aux      : auxiliary output from the last successful evaluation
    """
    if clip_fn is None:
        clip_fn = lambda v: np.clip(v, MIN_LOG, MAX_LOG)

    x = clip_fn(x0.copy())
    best_x = x.copy()
    best_norm = np.inf
    aux = np.empty(0)
    best_aux = aux
    lam = LM_LAMBDA_INIT

    for it in range(max_iter):
        if deadline_t and it % 20 == 0 and _time.perf_counter() > deadline_t:
            break

        f, J, aux = residual_and_jacobian(x)
        res_norm = np.linalg.norm(f)
        cost = 0.5 * res_norm * res_norm

        if res_norm < best_norm:
            best_norm = res_norm
            best_x = x.copy()
            best_aux = aux

        if res_norm < tol:
            if debug and it > 10:
                print(f"    [NR] converged in {it} iters, ||f|| = {res_norm:.2e}")
            return x, True, it, res_norm, aux

        # ── Jacobian equilibration ──
        if JACOBIAN_EQUIL:
            J_eq, f_eq, D_row, D_col = _equilibrate_jacobian(J, f)
        else:
            J_eq, f_eq, D_col = J, f, np.ones(len(x))

        # ── LM step: solve (J^T J + λ diag(J^T J)) dx = -J^T f ──
        JtJ = J_eq.T @ J_eq
        Jtf = J_eq.T @ f_eq
        diag_JtJ = np.diag(JtJ).copy()
        diag_JtJ = np.maximum(diag_JtJ, 1e-30)  # safeguard zero diagonal

        dx_eq = None
        for _lm in range(5):
            A = JtJ + lam * np.diag(diag_JtJ)
            try:
                dx_eq = np.linalg.solve(A, -Jtf)
                break
            except np.linalg.LinAlgError:
                lam = min(lam * LM_FACTOR_UP, LM_LAMBDA_MAX)

        if dx_eq is None:
            # All LM attempts failed — Cauchy fallback
            dx = _cauchy_point(J, f)
        else:
            dx = dx_eq / D_col   # unscale columns

        # ── Armijo backtracking line search ──
        grad_dot_dx = np.dot(J.T @ f, dx)  # directional derivative
        alpha = damping
        accepted = False
        overflow = not (np.isfinite(cost) and np.isfinite(grad_dot_dx))

        if overflow:
            # Cost or gradient overflows — trust LM direction, skip Armijo
            x_new = clip_fn(x + alpha * dx)
            f_new, _, _ = residual_and_jacobian(x_new)
            cost_new = 0.5 * np.dot(f_new, f_new)
            accepted = True
        else:
            for _bt in range(backtrack_max):
                x_new = clip_fn(x + alpha * dx)
                f_new, _, _ = residual_and_jacobian(x_new)
                cost_new = 0.5 * np.dot(f_new, f_new)

                if cost_new < cost + ARMIJO_C1 * alpha * grad_dot_dx:
                    accepted = True
                    break
                alpha *= 0.5

        if not accepted:
            # Armijo exhausted — use Cauchy point with its own line search
            dx_c = _cauchy_point(J, f)
            grad_dot_c = np.dot(J.T @ f, dx_c)
            alpha_c = 1.0
            for _bt2 in range(backtrack_max):
                x_cand = clip_fn(x + alpha_c * dx_c)
                f_cand, _, _ = residual_and_jacobian(x_cand)
                cost_cand = 0.5 * np.dot(f_cand, f_cand)
                if cost_cand < cost + ARMIJO_C1 * alpha_c * grad_dot_c:
                    x_new = x_cand
                    f_new = f_cand
                    cost_new = cost_cand
                    accepted = True
                    break
                alpha_c *= 0.5

        if not accepted:
            # Ultimate fallback — tiny Cauchy step (always take it)
            x_new = clip_fn(x + 0.01 * dx_c)
            f_new, _, _ = residual_and_jacobian(x_new)
            cost_new = 0.5 * np.dot(f_new, f_new)

        # ── LM λ adaptation via gain ratio ──
        if dx_eq is not None and np.isfinite(cost) and np.isfinite(cost_new):
            predicted_reduction = -np.dot(Jtf, dx_eq) - 0.5 * dx_eq @ JtJ @ dx_eq
            if abs(predicted_reduction) > 1e-60:
                actual_reduction = cost - cost_new
                rho = actual_reduction / abs(predicted_reduction)
                if rho > LM_GAIN_GOOD:
                    lam = max(lam * LM_FACTOR_DOWN, LM_LAMBDA_MIN)
                elif rho < LM_GAIN_POOR:
                    lam = min(lam * LM_FACTOR_UP, LM_LAMBDA_MAX)

        x = x_new

    if debug:
        print(f"    [NR] NOT converged after {max_iter} iters, "
              f"||f|| = {best_norm:.2e}")
    return best_x, False, max_iter, best_norm, best_aux
