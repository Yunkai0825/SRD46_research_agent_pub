"""
solid_manager.py
================
Active-set loop for solid precipitation at one (pH, E) point.

Delegates to PourbaixPointSolver for the Newton-Raphson solve, managing
the activation/deactivation of solid phases when saturation indices
indicate supersaturation.
"""

from __future__ import annotations

import numpy as np
from collections import OrderedDict, deque
from fractions import Fraction
from math import gcd, lcm
from typing import Dict, List, Optional, Tuple

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).absolute().parents[1]))
_calc_root = str(pathlib.Path(__file__).absolute().parents[2])
if _calc_root not in sys.path:
    sys.path.insert(0, _calc_root)

from solver_settings import (
    SI_THRESHOLD, ACTIVE_SET_MAX, SOLID_AMOUNT_TOL,
    NERNST_FACTOR, MIN_LOG, MAX_LOG, DEBUG, MULTI_START_N,
    POINT_TIMEOUT_S,
    AUTO_I_MAX_ITER, AUTO_I_TOL,
)
from solver_core_api import SolverEquilibrium
from support_TD_helpers.activity_model_entry_point import (
    compute_ionic_strength, recompute_activity_at_I,
)
from numerical_solvers.eq_numerical_methods import compute_saturation_index, compute_log_concentrations

from nd_grid.data_types import PointResult


_STOICH_ATOL = 1e-10
_STOICH_MAX_DENOMINATOR = 1_000_000


def primitive_saturation_reference_frame(
    conserved_stoich: np.ndarray,
    *,
    atol: float = _STOICH_ATOL,
) -> Tuple[float, Tuple[int, ...]]:
    """Return the formula scale and primitive closed-component frame.

    A dissolution saturation residual is a dimensionless grand-formation
    affinity *per mole of the formula unit written on the card*.  Therefore
    two residuals may be ranked thermodynamically only after proportional
    formulae have been reduced to the same closed-component reference.  For
    example, ``Cu2O`` has the closed-component vector ``[2 Cu]`` and is
    represented as ``scale=2, frame=[1 Cu]``; ``Cu(s)`` has ``scale=1`` in
    that same frame.

    Hydrogen, electrons, and solvent are open reservoirs and are already
    present in the saturation residual.  ``conserved_stoich`` consequently
    contains only the mass-balanced element and ligand components.  A
    different primitive vector is a different thermodynamic frame; scalar
    affinities from different frames must not be used to declare a dominant
    phase.

    Fractional but rational stoichiometry is accepted.  Invalid, negative,
    irrational-within-tolerance, or empty formula footprints are rejected
    instead of receiving an arbitrary normalization.
    """
    row = np.asarray(conserved_stoich, dtype=np.float64)
    if row.ndim != 1:
        raise ValueError("solid conserved stoichiometry must be one-dimensional")
    if not np.all(np.isfinite(row)):
        raise ValueError("solid conserved stoichiometry must be finite")
    if np.any(row < -atol):
        raise ValueError("solid conserved stoichiometry cannot be negative")

    row = np.where(np.abs(row) <= atol, 0.0, row)
    if not np.any(row > 0.0):
        raise ValueError(
            "solid has no closed-component footprint and therefore no "
            "formation-energy reference frame"
        )

    rational: List[Fraction] = []
    for value in row:
        if value == 0.0:
            rational.append(Fraction(0, 1))
            continue
        frac = Fraction(float(value)).limit_denominator(
            _STOICH_MAX_DENOMINATOR
        )
        if abs(float(frac) - float(value)) > atol * max(1.0, abs(float(value))):
            raise ValueError(
                f"solid stoichiometric coefficient {value!r} cannot be "
                "reduced to a reliable rational reference frame"
            )
        rational.append(frac)

    common_denominator = 1
    for value in rational:
        common_denominator = lcm(common_denominator, value.denominator)
    integer_row = [
        value.numerator * (common_denominator // value.denominator)
        for value in rational
    ]
    common_numerator = 0
    for value in integer_row:
        common_numerator = gcd(common_numerator, abs(value))
    if common_numerator <= 0:  # defensive; the non-empty check above forbids it
        raise ValueError("unable to construct a solid reference frame")

    signature = tuple(value // common_numerator for value in integer_row)
    scale = common_numerator / common_denominator
    return float(scale), signature


def build_saturation_reference_frames(
    solid_nu: np.ndarray,
) -> Tuple[np.ndarray, List[Tuple[int, ...]]]:
    """Build primitive formation-energy frames for all solid formulae."""
    matrix = np.asarray(solid_nu, dtype=np.float64)
    if matrix.ndim != 2:
        raise ValueError("solid stoichiometry matrix must be two-dimensional")
    scales: List[float] = []
    signatures: List[Tuple[int, ...]] = []
    for row in matrix:
        scale, signature = primitive_saturation_reference_frame(row)
        scales.append(scale)
        signatures.append(signature)
    return np.asarray(scales, dtype=np.float64), signatures


class SolidManager:
    """Coordinate solid precipitation for one (pH, E) point."""

    def __init__(self, point_solver, dissolution_eqs: List[SolverEquilibrium],
                 n_basis: int, species_list, debug: bool = False,
                 built=None):
        """
        Parameters
        ----------
        point_solver   : PourbaixPointSolver instance
        dissolution_eqs: list of SolverEquilibrium
        n_basis        : number of basis unknowns
        species_list   : list of SolverSpecies (for labelling)
        debug          : print debug messages
        built          : BuiltSystem (needed for auto-I mode)
        """
        self.solver = point_solver
        self.dissolution_eqs = dissolution_eqs
        self.n_basis = n_basis
        self.species_list = species_list
        self.debug = debug
        self.built = built  # stored for auto-I recomputation

        # Pre-build numpy arrays for dissolution equilibria
        n_diss = len(dissolution_eqs)
        self.n_diss = n_diss
        if n_diss > 0:
            self.diss_logK = np.array([d.log_K_diss_eff for d in dissolution_eqs])
            self.diss_p = np.array([d.stoich_metals + d.stoich_ligands for d in dissolution_eqs], dtype=np.float64)
            self.diss_r = np.array([d.stoich_H for d in dissolution_eqs], dtype=np.float64)
            self.diss_s = np.array([d.stoich_e for d in dissolution_eqs], dtype=np.float64)
            self.diss_nu = np.array([d.nu_elements + d.nu_ligands for d in dissolution_eqs],
                                   dtype=np.float64)
            try:
                (self.diss_reference_scale,
                 self.diss_reference_frame) = build_saturation_reference_frames(
                    self.diss_nu
                )
            except ValueError as exc:
                raise ValueError(
                    "invalid dissolution formula/reference frame: "
                    f"{exc}"
                ) from exc
        else:
            self.diss_logK = np.array([])
            self.diss_p = np.zeros((0, n_basis))
            self.diss_r = np.array([])
            self.diss_s = np.array([])
            self.diss_nu = np.zeros((0, n_basis))
            self.diss_reference_scale = np.array([], dtype=np.float64)
            self.diss_reference_frame = []

    def _update_activity_arrays(self, log_beta_app: np.ndarray,
                                diss_logK_app: np.ndarray) -> None:
        """Push recomputed apparent arrays into point solver + dissolution."""
        self.solver.update_log_beta_eff(log_beta_app)
        if self.n_diss > 0 and len(diss_logK_app) > 0:
            np.copyto(self.diss_logK, diss_logK_app)

    def compute_SI(self, x: np.ndarray, logH: float, logE: float) -> np.ndarray:
        """Compute raw formula-unit saturation indices for reporting.

        Raw SI remains useful as the exact card-equation residual and is kept
        for output compatibility.  It must *not* be used to rank phases whose
        formula units or conserved-component reference frames differ.
        """
        if self.n_diss == 0:
            return np.array([])
        return compute_saturation_index(
            x, logH, logE,
            self.diss_logK, self.diss_p, self.diss_r, self.diss_s,
        )

    def compute_normalized_affinity(
        self,
        x: np.ndarray,
        logH: float,
        logE: float,
    ) -> np.ndarray:
        """Return dimensionless grand-formation affinity per reference unit.

        For raw formula-unit saturation index ``SI_i`` and primitive formula
        scale ``q_i``, the ranking quantity is ``A_i = SI_i / q_i``.  Its
        energy equivalent is

        ``delta_G_drive_i = -R*T*ln(10) * A_i``.

        Thus larger ``A_i`` means a more negative formation driving energy.
        The dimensionless value is sufficient for ordering and avoids any
        temperature fallback here.  Even normalized values are comparable
        only when their primitive reference-frame signatures are identical.
        """
        if self.n_diss == 0:
            return np.array([])
        return self.compute_SI(x, logH, logE) / self.diss_reference_scale

    def _normalized_active_arrays(
        self,
        active_indices: List[int],
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Return saturation rows in a common primitive formula scaling.

        Scaling a saturation equation by a positive constant does not change
        its zero.  It does remove arbitrary card formula multiplication from
        both the residual and its Jacobian.  Mass-balance columns remain per
        mole of the physical solid formula and are deliberately not scaled.
        """
        indices = np.asarray(active_indices, dtype=int)
        scales = self.diss_reference_scale[indices]
        return (
            self.diss_p[indices] / scales[:, None],
            self.diss_r[indices] / scales,
            self.diss_s[indices] / scales,
            self.diss_logK[indices] / scales,
            self.diss_nu[indices],
        )

    def _ordered_supersaturated_candidates(
        self,
        normalized_affinity: np.ndarray,
        active_indices: Tuple[int, ...],
    ) -> List[int]:
        """Return candidates without comparing unlike reference frames.

        Candidates are partitioned by primitive closed-component signature.
        Within one signature, larger normalized SI means lower grand
        formation energy and is tried first.  Different signatures are kept
        in deterministic card order; their scalar SI values are never used
        to assert dominance over one another.  The active-set search still
        tries every supersaturated candidate as a separate complementarity
        constraint.
        """
        active = set(active_indices)
        groups: "OrderedDict[Tuple[int, ...], List[int]]" = OrderedDict()
        for k in range(self.n_diss):
            if k in active or normalized_affinity[k] <= SI_THRESHOLD:
                continue
            groups.setdefault(self.diss_reference_frame[k], []).append(k)

        ordered: List[int] = []
        for candidates in groups.values():
            candidates.sort(key=lambda k: (-float(normalized_affinity[k]), k))
            ordered.extend(candidates)
        return ordered

    def solve_point(
        self,
        pH: float,
        E_V: Optional[float],
        C_all: np.ndarray,
        x0: Optional[np.ndarray] = None,
        timeout_s: float = POINT_TIMEOUT_S,
        pin_plan: Optional[List[Tuple[int, int, float]]] = None,
    ) -> PointResult:
        """
        Solve at one (pH, E) point including solid precipitation.

        ``pin_plan`` (Tier-2): optional list of
        ``(aqueous_row, released_component, log10_target)`` triples.  When
        non-empty the augmented solver pins each listed species to its
        target log10 concentration and releases the paired component total
        (kept square per the DOF rule).  When empty/``None`` the solver
        behaves exactly as before (verified Tier-1 path untouched).

        In **fixed** ionic-strength mode this delegates directly to the
        single-shot solver.  In **auto** mode it iterates:

        1. Solve with current apparent logβ / logK.
        2. Compute I from the solved charged-species concentrations.
        3. Recompute logβ / logK at the new I via the Gibbs helpers.
        4. Re-solve until |ΔI| < AUTO_I_TOL or AUTO_I_MAX_ITER reached.
        """
        if E_V is None:
            aqueous_has_e = np.any(np.abs(self.solver.stoich_s) > 1e-12)
            solid_has_e = np.any(np.abs(self.diss_s) > 1e-12)
            if aqueous_has_e or solid_has_e:
                raise ValueError(
                    "E_V is 'Not defined' but aqueous or dissolution "
                    "electron stoichiometry is nonzero; declare a potential "
                    "or exclude redox before solving")
        elif isinstance(E_V, bool) or not np.isfinite(float(E_V)):
            raise ValueError(f"E_V must be a finite number, got {E_V!r}")

        ionic_mode = getattr(self.built, "ionic_mode", "Not defined")
        if ionic_mode not in {"fixed", "auto"}:
            raise ValueError(
                "ionic_mode is 'Not defined' on the built system; declare "
                "fixed or auto before solving")
        if ionic_mode != "auto":
            return self._solve_point_once(pH, E_V, C_all, x0, timeout_s,
                                          pin_plan=pin_plan)

        # ── Auto-I iteration ──
        I_prev = float(self.built.ionic_strength)
        I_accepted = I_prev
        result = self._solve_point_once(pH, E_V, C_all, x0, timeout_s,
                                        pin_plan=pin_plan)
        if not result.converged:
            return result

        for auto_it in range(AUTO_I_MAX_ITER):
            # Compute I from solved concentrations
            conc_arr = np.array([result.conc[sp.id] for sp in self.species_list])
            charges_arr = np.array([sp.charge for sp in self.species_list])
            I_species = compute_ionic_strength(conc_arr, charges_arr)
            I_new = I_species

            if abs(I_new - I_prev) < AUTO_I_TOL:
                I_accepted = I_new
                log_beta_app, diss_logK_app = recompute_activity_at_I(
                    self.built, I_accepted)
                self._update_activity_arrays(log_beta_app, diss_logK_app)
                break

            # Recompute apparent arrays via the Gibbs helpers
            log_beta_app, diss_logK_app = recompute_activity_at_I(
                self.built, I_new)
            self._update_activity_arrays(log_beta_app, diss_logK_app)
            # Re-solve using previous solution as initial guess
            candidate = self._solve_point_once(
                pH, E_V, C_all, result.x, timeout_s, pin_plan=pin_plan)
            if not candidate.converged:
                # Keep the model arrays and the declared state synchronized
                # with the last successfully accepted auto-I iterate.
                log_beta_app, diss_logK_app = recompute_activity_at_I(
                    self.built, I_accepted)
                self._update_activity_arrays(log_beta_app, diss_logK_app)
                result = candidate
                break
            result = candidate
            I_prev = I_new
            I_accepted = I_new
        else:
            # Exhausting the iteration budget without satisfying the I
            # fixed-point criterion is a numerical nonconvergence, even if
            # the last inner speciation solve itself converged.
            conc_arr = np.array([
                result.conc[sp.id] for sp in self.species_list
            ])
            charges_arr = np.array([sp.charge for sp in self.species_list])
            ionic_residual = abs(
                compute_ionic_strength(conc_arr, charges_arr) - I_accepted
            )
            result.converged = False
            result.residual = max(float(result.residual), float(ionic_residual))
            result._auto_ionic_strength_not_converged = True

        self.built.ionic_strength = float(I_accepted)
        return result

    def _solve_point_once(
        self,
        pH: float,
        E_V: Optional[float],
        C_all: np.ndarray,
        x0: Optional[np.ndarray] = None,
        timeout_s: float = POINT_TIMEOUT_S,
        pin_plan: Optional[List[Tuple[int, int, float]]] = None,
    ) -> PointResult:
        """
        Single-shot solve at one (pH, E) point including solid precipitation.

        Algorithm:
        1. Aqueous-only solve (pin-aware when ``pin_plan`` is non-empty)
        2. Compute SI for all solids
        3. Complementarity active-set search:
           - Partition supersaturated solids by primitive reference frame
           - Rank only candidates in the same frame by normalized SI
           - Explore unlike frames as independent phase constraints
           - Reject failed/negative-amount active sets and try alternatives
           - Accept only if every inactive normalized SI is non-positive
        4. Return PointResult
        """
        import time as _time
        _t0 = _time.perf_counter()
        _deadline = _t0 + timeout_s if timeout_s > 0 else 0.0

        logH = -pH
        pe = None if E_V is None else E_V / NERNST_FACTOR
        # For redox-excluded systems every electron coefficient is zero.
        # logE=0 is only the neutral numerical multiplier; E remains absent.
        logE = 0.0 if pe is None else -pe

        # ── Tier-2 pin plan -> solver arrays ──
        has_pins = bool(pin_plan)
        if has_pins:
            pin_rows = np.array([int(t[0]) for t in pin_plan], dtype=int)
            released_idx = np.array([int(t[1]) for t in pin_plan], dtype=int)
            pin_targets = np.array([float(t[2]) for t in pin_plan], dtype=float)
            # Fixed reference scale for released mass rows: the baseline
            # total at each released component (floored so it never -> 0).
            C_ref = np.maximum(C_all.astype(float), 1e-12)
            T_rel = None     # warm-start carried across the active-set loop
        else:
            pin_rows = released_idx = pin_targets = None
            C_ref = None
            T_rel = None

        # Step 1: Aqueous(-pinned) solve (possibly with multi-start)
        if has_pins:
            empty_p = np.zeros((0, self.n_basis))
            empty_v = np.zeros(0)
            x, _ns0, T_rel, conv, iters, res, c = self.solver.solve_augmented(
                pH, E_V, C_all,
                empty_p, empty_v, empty_v, empty_v, empty_p,
                pin_rows, pin_targets, released_idx, C_ref,
                x0=x0, deadline_t=_deadline)
        else:
            x, conv, iters, res, c = self.solver.solve_aqueous(
                pH, E_V, C_all, x0, deadline_t=_deadline)

        if not conv and MULTI_START_N > 1:
            # Multi-start: try different initial guesses
            for trial in range(1, MULTI_START_N):
                if _deadline and _time.perf_counter() > _deadline:
                    break
                x0_trial = np.log10(np.maximum(C_all, 1e-30))
                x0_trial += np.random.uniform(-3, 3, size=self.n_basis)
                x0_trial = np.clip(x0_trial, MIN_LOG, MAX_LOG)
                if has_pins:
                    x_t, _n_t, T_t, conv_t, it_t, res_t, c_t = \
                        self.solver.solve_augmented(
                            pH, E_V, C_all,
                            empty_p, empty_v, empty_v, empty_v, empty_p,
                            pin_rows, pin_targets, released_idx, C_ref,
                            x0=x0_trial, deadline_t=_deadline)
                else:
                    x_t, conv_t, it_t, res_t, c_t = self.solver.solve_aqueous(
                        pH, E_V, C_all, x0_trial, deadline_t=_deadline)
                if conv_t and res_t < res:
                    x, conv, iters, res, c = x_t, conv_t, it_t, res_t, c_t
                    if has_pins:
                        T_rel = T_t
                    break

        if not conv:
            result = self._pack_result(pH, E_V, pe, x, conv, iters, res, c,
                                       {}, {}, [])
            if has_pins and T_rel is not None:
                result._released_totals = {int(released_idx[i]): float(T_rel[i])
                                           for i in range(len(T_rel))}
            if _time.perf_counter() - _t0 > timeout_s:
                result._timed_out = True
            return result

        # Step 2: Compute SI for all solids
        SI = self.compute_SI(x, logH, logE)
        solid_amounts: Dict[str, float] = {}
        active_ids: List[str] = []
        all_SI: Dict[str, float] = {self.dissolution_eqs[k].id: float(SI[k])
                                    for k in range(self.n_diss)}

        if self.n_diss == 0:
            result = self._pack_result(pH, E_V, pe, x, conv, iters, res, c,
                                       solid_amounts, all_SI, active_ids)
            if has_pins and T_rel is not None:
                result._released_totals = {int(released_idx[i]): float(T_rel[i])
                                           for i in range(len(T_rel))}
            return result

        # Step 3: active-set search.  A state is accepted only when it
        # satisfies the full phase complementarity conditions:
        #
        #   active amount > 0, active SI = 0, inactive SI <= threshold.
        #
        # The old greedy loop stopped after a failed candidate addition and
        # could consequently return ``converged=True`` with a strongly
        # supersaturated inactive solid.  Here failed sets are discarded and
        # alternative candidate sets remain searchable.
        root_state = {
            "active": tuple(),
            "x": np.asarray(x, dtype=np.float64),
            "c": np.asarray(c, dtype=np.float64),
            "ns": np.zeros(0, dtype=np.float64),
            "T_rel": T_rel,
            "res": float(res),
        }
        pending = deque([root_state])
        solved_subsets = {tuple()}
        attempted_from = set()
        stable_states: List[dict] = []
        timed_out = False
        total_iters = int(iters)
        max_active = min(self.n_basis, self.n_diss, ACTIVE_SET_MAX)

        def _enqueue_solved_subset(
            subset: Tuple[int, ...],
            parent_state: dict,
        ) -> None:
            """Solve one exact active set and enqueue it when feasible."""
            nonlocal total_iters, timed_out
            subset = tuple(sorted(set(subset)))
            parent_active = tuple(parent_state["active"])
            attempt_key = (subset, parent_active)
            if (subset in solved_subsets or attempt_key in attempted_from
                    or not subset or len(subset) > max_active):
                return
            attempted_from.add(attempt_key)

            if _deadline and _time.perf_counter() > _deadline:
                timed_out = True
                return

            act_p, act_r, act_s, act_logK, act_nu = \
                self._normalized_active_arrays(list(subset))

            parent_amount = {
                k: float(parent_state["ns"][i])
                for i, k in enumerate(parent_active)
            }
            ns0 = np.full(len(subset), 1e-8, dtype=np.float64)
            for i, k in enumerate(subset):
                if k in parent_amount and parent_amount[k] > SOLID_AMOUNT_TOL:
                    ns0[i] = parent_amount[k]
                    continue
                for j in range(self.n_basis):
                    if act_nu[i, j] <= 0:
                        continue
                    deficit = C_all[j] - (
                        self.solver.nu_matrix[j] @ parent_state["c"]
                    )
                    if deficit > 0:
                        ns0[i] = max(ns0[i], deficit / act_nu[i, j])

            if self.debug:
                names = [self.dissolution_eqs[k].id for k in subset]
                print(f"    [solid] Trying active set {names}")

            if has_pins:
                (x_new, ns_new, T_new, conv_new, it_new,
                 res_new, c_new) = self.solver.solve_augmented(
                    pH, E_V, C_all,
                    act_p, act_r, act_s, act_logK, act_nu,
                    pin_rows, pin_targets, released_idx, C_ref,
                    x0=parent_state["x"], ns0=ns0,
                    T0=parent_state["T_rel"], deadline_t=_deadline,
                )
            else:
                (x_new, ns_new, conv_new, it_new,
                 res_new, c_new) = self.solver.solve_expanded(
                    pH, E_V, C_all,
                    act_p, act_r, act_s, act_logK, act_nu,
                    x0=parent_state["x"], ns0=ns0,
                    deadline_t=_deadline,
                )
                T_new = None
            total_iters += int(it_new)
            if _deadline and _time.perf_counter() > _deadline:
                timed_out = True
                return
            if not conv_new:
                if self.debug:
                    print(f"    [solid] Rejected non-converged set {names}")
                return
            # A failed solve from one parent's basin must not permanently
            # poison the active subset.  A converged but non-positive state
            # is likewise left retryable from a distinct parent.
            if np.all(np.asarray(ns_new) > SOLID_AMOUNT_TOL):
                solved_subsets.add(subset)
            pending.append({
                "active": subset,
                "x": np.asarray(x_new, dtype=np.float64),
                "c": np.asarray(c_new, dtype=np.float64),
                "ns": np.asarray(ns_new, dtype=np.float64),
                "T_rel": T_new,
                "res": float(res_new),
            })

        while pending:
            if _deadline and _time.perf_counter() > _deadline:
                timed_out = True
                if self.debug:
                    elapsed = _time.perf_counter() - _t0
                    print(f"    [solid] TIMEOUT after {elapsed:.1f}s")
                break

            state = pending.popleft()
            state_active = tuple(state["active"])

            # A mathematically converged equality solve is not physically
            # feasible when any active phase has a non-positive amount.  The
            # corresponding reduced set is re-solved; the equality solution
            # itself is never reused as though the removed constraint were
            # absent.
            nonpositive = [
                i for i, amount in enumerate(state["ns"])
                if amount <= SOLID_AMOUNT_TOL
            ]
            if nonpositive:
                reduced = tuple(
                    k for i, k in enumerate(state_active)
                    if i not in nonpositive
                )
                if reduced:
                    _enqueue_solved_subset(reduced, state)
                continue

            state_SI = self.compute_SI(state["x"], logH, logE)
            state_affinity = state_SI / self.diss_reference_scale
            candidates = self._ordered_supersaturated_candidates(
                state_affinity, state_active
            )
            if not candidates:
                state["SI"] = state_SI
                stable_states.append(state)
                # Do not stop at the first certified state.  Another branch
                # may also satisfy complementarity but use an incomparable
                # conserved-component frame.  Such ambiguity must be exposed,
                # not resolved by card order.
                continue

            for candidate in candidates:
                if timed_out:
                    break
                candidate_frame = self.diss_reference_frame[candidate]
                same_frame = tuple(
                    k for k in state_active
                    if self.diss_reference_frame[k] == candidate_frame
                )

                if same_frame:
                    # Proportional closed-component formulae are directly
                    # comparable in their primitive frame.  A positive SI for
                    # the inactive candidate means it replaces the less stable
                    # active member(s), except exactly on coexistence where SI
                    # would be zero and it would not be a candidate.
                    child = tuple(
                        k for k in state_active if k not in same_frame
                    ) + (candidate,)
                else:
                    # Different conserved-component signatures are not ranked
                    # against one another.  Add the candidate as a distinct
                    # complementarity constraint and let mass balance decide
                    # whether coexistence has positive amounts.
                    if len(state_active) >= max_active:
                        # The set cannot accept another independent phase.
                        # Other queued/replacement sets remain searchable.
                        continue
                    child = state_active + (candidate,)

                _enqueue_solved_subset(child, state)

        stable_state = None
        tie_states: List[dict] = []
        ambiguous_states: List[dict] = []
        if timed_out:
            # The search order is only an implementation detail.  A stable
            # state found before the deadline cannot be certified while
            # other queued phase assemblages remain unexplored.
            if len(stable_states) > 1:
                ambiguous_states = stable_states
        elif len(stable_states) == 1:
            stable_state = stable_states[0]
        elif len(stable_states) > 1:
            # Compare alternatives only component-wise within identical
            # primitive reference signatures.  The root aqueous activities
            # are a common chemical-potential point; differences between
            # proportional phase affinities are invariant to the closed-basis
            # activity term.  No sum or scalar comparison is made across
            # unlike signatures.
            root_affinity = SI / self.diss_reference_scale

            def _frame_affinity_map(state: dict):
                mapping = {}
                for k in state["active"]:
                    frame = self.diss_reference_frame[k]
                    # The replacement rule normally permits one active phase
                    # per frame.  ``max`` remains safe for an exact-degenerate
                    # equality set.
                    mapping[frame] = max(
                        mapping.get(frame, -np.inf), float(root_affinity[k])
                    )
                return mapping

            maps = [_frame_affinity_map(state) for state in stable_states]
            common_keys = set(maps[0])
            same_frames = all(set(mapping) == common_keys for mapping in maps)
            if same_frames:
                dominators = []
                for i, mapping_i in enumerate(maps):
                    dominates_all = True
                    strictly_better_somewhere = False
                    for j, mapping_j in enumerate(maps):
                        if i == j:
                            continue
                        if any(
                            mapping_i[frame] < mapping_j[frame] - SI_THRESHOLD
                            for frame in common_keys
                        ):
                            dominates_all = False
                            break
                        if any(
                            mapping_i[frame] > mapping_j[frame] + SI_THRESHOLD
                            for frame in common_keys
                        ):
                            strictly_better_somewhere = True
                    if dominates_all and strictly_better_somewhere:
                        dominators.append(i)
                if len(dominators) == 1:
                    stable_state = stable_states[dominators[0]]

                if stable_state is None:
                    reference_map = maps[0]
                    energies_tied = all(
                        all(
                            abs(mapping[frame] - reference_map[frame])
                            <= SI_THRESHOLD
                            for frame in common_keys
                        )
                        for mapping in maps[1:]
                    )

                    def _same_optional_vector(left, right) -> bool:
                        if left is None or right is None:
                            return left is None and right is None
                        return bool(np.allclose(
                            np.asarray(left, dtype=np.float64),
                            np.asarray(right, dtype=np.float64),
                            rtol=1e-8, atol=SI_THRESHOLD,
                        ))

                    reference_state = stable_states[0]
                    same_solution = all(
                        np.allclose(
                            state["x"], reference_state["x"],
                            rtol=1e-8, atol=SI_THRESHOLD,
                        ) and _same_optional_vector(
                            state["T_rel"], reference_state["T_rel"]
                        )
                        for state in stable_states[1:]
                    )
                    if energies_tied and same_solution:
                        # At an exact solid-solid boundary the equilibrium
                        # aqueous state is valid, while allocation among tied
                        # phases is underdetermined.  Retain one deterministic
                        # representative and expose every tied assemblage.
                        tie_states = sorted(
                            stable_states, key=lambda state: state["active"]
                        )
                        stable_state = tie_states[0]

            if stable_state is None:
                ambiguous_states = stable_states

        if stable_state is not None:
            x = stable_state["x"]
            c = stable_state["c"]
            T_rel = stable_state["T_rel"]
            res = stable_state["res"]
            conv = True
            active_indices = tuple(stable_state["active"])
            solid_amounts = {
                self.dissolution_eqs[k].id: float(stable_state["ns"][i])
                for i, k in enumerate(active_indices)
            }
            active_ids = [self.dissolution_eqs[k].id for k in active_indices]
            SI = stable_state["SI"]
            all_SI = {
                self.dissolution_eqs[k].id: float(SI[k])
                for k in range(self.n_diss)
            }
        else:
            # There is no certified complementarity solution.  Return the
            # aqueous values for diagnostics, explicitly non-converged; this
            # prevents label/topology code from treating an invalid phase
            # choice as a physical result.
            x = root_state["x"]
            c = root_state["c"]
            T_rel = root_state["T_rel"]
            res = max(
                float(root_state["res"]),
                float(np.max(np.maximum(
                    SI / self.diss_reference_scale, 0.0
                ))) if SI.size else 0.0,
            )
            conv = False
            solid_amounts = {}
            active_ids = []
            all_SI = {
                self.dissolution_eqs[k].id: float(SI[k])
                for k in range(self.n_diss)
            }
            if self.debug:
                if ambiguous_states:
                    print(
                        "    [solid] Multiple incomparable complementarity "
                        "states; point flagged thermodynamically ambiguous"
                    )
                else:
                    print(
                        "    [solid] No phase-complementarity solution; "
                        "point flagged non-converged"
                    )

        result = self._pack_result(
            pH, E_V, pe, x, conv, total_iters, res, c,
            solid_amounts, all_SI, active_ids,
        )
        result.saturation_reference_scales = {
            self.dissolution_eqs[k].id: float(self.diss_reference_scale[k])
            for k in range(self.n_diss)
        }
        result.saturation_reference_frames = {
            self.dissolution_eqs[k].id: tuple(self.diss_reference_frame[k])
            for k in range(self.n_diss)
        }
        final_affinity = self.compute_normalized_affinity(x, logH, logE)
        result.normalized_formation_affinities = {
            self.dissolution_eqs[k].id: float(final_affinity[k])
            for k in range(self.n_diss)
        }
        if self.built is not None and hasattr(self.built, "temperature_C"):
            temperature_K = float(self.built.temperature_C) + 273.15
            if np.isfinite(temperature_K) and temperature_K > 0.0:
                # kJ mol^-1 per primitive conserved-component formula.
                factor_kJ = 8.31446261815324e-3 * temperature_K * np.log(10.0)
                result.formation_driving_energies_kJ_per_mol_reference = {
                    self.dissolution_eqs[k].id:
                        float(-factor_kJ * final_affinity[k])
                    for k in range(self.n_diss)
                }
        if tie_states:
            result.thermodynamic_tie_active_sets = [
                [self.dissolution_eqs[k].id for k in state["active"]]
                for state in tie_states
            ]
        if ambiguous_states:
            result.thermodynamic_ambiguity_active_sets = [
                [self.dissolution_eqs[k].id for k in state["active"]]
                for state in ambiguous_states
            ]
        if has_pins and T_rel is not None:
            result._released_totals = {
                int(released_idx[i]): float(T_rel[i])
                for i in range(len(T_rel))
            }
        if timed_out:
            result.phase_search_timed_out = True
            # Backward-compatible marker used by existing grid diagnostics.
            result._timed_out = True
        return result

    def _pack_result(self, pH, E_V, pe, x, conv, iters, res, c,
                     solid_amounts, SI_dict, active_ids) -> PointResult:
        """Pack solver output into PointResult (N-D unified type)."""
        logH = -pH
        logE = 0.0 if pe is None else -pe

        # Build concentration dicts
        log_c_arr, c_arr = compute_log_concentrations(
            x, logH, logE,
            self.solver.log_beta_eff, self.solver.stoich_pq,
            self.solver.stoich_r, self.solver.stoich_s,
        )

        log_conc = {}
        conc = {}
        for i, sp in enumerate(self.species_list):
            log_conc[sp.id] = float(log_c_arr[i])
            conc[sp.id] = float(c_arr[i])

        coords = {"pH": pH}
        if E_V is not None:
            coords["E_V"] = E_V

        return PointResult(
            coords=coords,
            converged=conv, iterations=iters, residual=res,
            x=x,
            log_conc=log_conc, conc=conc,
            frac_element={}, frac_ligand={},  # filled by labeler
            active_solid_ids=active_ids,
            solid_amounts=solid_amounts,
            saturation_indices=SI_dict,
        )


# ---------------------------------------------------------------------------
#  Self-test
# ---------------------------------------------------------------------------
