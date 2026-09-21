"""node_screen.py — deterministic anomaly flags for eq-map nodes.

Inputs
------
- One **eq-map node**: the row chosen by the deterministic
  selected_map.json for some (metal, ligand, beta_definition) triple.
- The **full neighbor list** for that triple from
  :func:`neighbor_query.get_node_neighbors`.
- The **request conditions** ``(T_request_C, I_request_M)`` the card
  is being built for.

Flags emitted (any combination per node):

* ``sign_discord``       — node value's sign opposes ≥ 2 sibling K-rows.
* ``sibling_sign_split`` — K-siblings span both signs (≥ 1 positive
                           AND ≥ 1 negative), regardless of which
                           side the chosen row sits on. A latent
                           data-quality signal: the population itself
                           is internally inconsistent.
* ``mad_outlier``        — |x − median(K-siblings)| > 3 · MAD; with
                           tiny populations the threshold is loosened
                           to 5 · MAD (≤ 4 siblings).
* ``mean_median_gap``    — |mean − median| over K-siblings exceeds
                           1.0 logK with ≥ 3 K-siblings. Indicates a
                           hidden outlier yanking the mean even when
                           the chosen value happens to sit on the
                           median side.
* ``nearest_request_sign_mismatch``
                         — the sibling closest to the request
                           (T_C, I_M) lies within ±5 °C / ±0.05 M of
                           the request, is NOT the chosen row, AND
                           its sign opposes the chosen value. Means
                           the deterministic selector bypassed the
                           at-request datum because it conflicts with
                           the rest of the population.
* ``single_observation`` — only the chosen row, no siblings at all.
* ``wide_TI_distance``   — chosen row's (T, I) is the only point in
                           its (T, I) bucket while a denser bucket
                           sits closer to the request, AND no sibling
                           is within ±5 °C / ±0.05 M of the request.
* ``K_H_S_contamination``— chosen row's ``constant_type`` is not 'K'
                           (the value is enthalpy / entropy and was
                           ingested as logK by mistake), OR the
                           K-siblings list is empty while H/S siblings
                           exist for the same triple.
* ``beta_def_orphan``    — chosen row has no other K-sibling at the
                           same beta_definition (no cross-validation
                           possible from the DB itself).

Severity classification:

* ``critical``  — ``sign_discord`` OR ``K_H_S_contamination`` OR
                  ``nearest_request_sign_mismatch``.
* ``warn``      — ``sibling_sign_split`` OR ``mean_median_gap`` OR
                  ``mad_outlier`` OR ``wide_TI_distance`` OR
                  (``beta_def_orphan`` AND ``single_observation``).
* ``ok``        — everything else (no flags, or only
                  ``beta_def_orphan`` / ``single_observation``).

The screen is **purely informational**: it never decides what to do.
The L2_1_1 LLM validator reads the per-node flags + neighbors table
and emits the verdict.
"""
from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .neighbor_query import NeighborRow, get_node_neighbors


# Tunables (kept as module-level so tests can monkeypatch).
MAD_K_LARGE_POP        = 3.0   # > 4 siblings: 3·MAD
MAD_K_SMALL_POP        = 5.0   # ≤ 4 siblings: 5·MAD
T_BUCKET_TOL_C         = 5.0   # group siblings within ±5 °C
I_BUCKET_TOL_M         = 0.05  # group siblings within ±0.05 M
T_NEAR_TOL_C           = 5.0   # "near the request" tolerance
I_NEAR_TOL_M           = 0.05
MEAN_MEDIAN_GAP_LOGK   = 1.0   # |mean - median| > this → flag
MEAN_MEDIAN_GAP_MIN_N  = 3     # minimum K-siblings to evaluate it


@dataclass
class EqMapNode:
    """One node from the deterministic selected_map.

    Mirrors the rows in ``maps.json`` plus the chosen vlm_id and
    constant value pulled from the DB by the equation builder.
    """
    metal_id:           int
    ligand_id:          int
    beta_definition_id: int
    network_db_id:      int
    vlm_id:             Optional[int]
    constant_type:      str
    constant_value:     float
    temperature_C:      Optional[float]
    ionic_strength_M:   Optional[float]
    equation_str:       str = ""
    node_db_id:         Optional[int] = None

    @property
    def node_key(self) -> str:
        return (
            f"metal{self.metal_id}_ligand{self.ligand_id}"
            f"_beta{self.beta_definition_id}_net{self.network_db_id}"
        )

    def as_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["node_key"] = self.node_key
        return d


@dataclass
class NodeScreen:
    """Per-node screen result emitted by :func:`screen_node`."""
    node:         EqMapNode
    flags:        List[str] = field(default_factory=list)
    severity:     str = "ok"
    n_neighbors:  int = 0
    n_K_neighbors: int = 0
    K_neighbor_summary: Dict[str, Any] = field(default_factory=dict)
    nearest_K_at_request: Optional[Dict[str, Any]] = None
    notes:        List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "node":               self.node.as_dict(),
            "flags":              list(self.flags),
            "severity":           self.severity,
            "n_neighbors":        self.n_neighbors,
            "n_K_neighbors":      self.n_K_neighbors,
            "K_neighbor_summary": dict(self.K_neighbor_summary),
            "nearest_K_at_request": self.nearest_K_at_request,
            "notes":              list(self.notes),
        }


@dataclass
class EqMapScreen:
    """Full screen across every node of one (metal, ligand) pair."""
    pair_key:        str
    request_T_C:     float
    request_I_M:     float
    nodes:           List[NodeScreen] = field(default_factory=list)

    @property
    def critical_node_keys(self) -> List[str]:
        return [n.node.node_key for n in self.nodes if n.severity == "critical"]

    @property
    def warn_node_keys(self) -> List[str]:
        return [n.node.node_key for n in self.nodes if n.severity == "warn"]

    @property
    def has_anomaly(self) -> bool:
        return bool(self.critical_node_keys or self.warn_node_keys)

    def node_by_key(self, key: str) -> Optional[NodeScreen]:
        for n in self.nodes:
            if n.node.node_key == key:
                return n
        return None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "pair_key":          self.pair_key,
            "request_T_C":       self.request_T_C,
            "request_I_M":       self.request_I_M,
            "n_nodes":           len(self.nodes),
            "n_critical":        len(self.critical_node_keys),
            "n_warn":            len(self.warn_node_keys),
            "critical_node_keys": self.critical_node_keys,
            "warn_node_keys":    self.warn_node_keys,
            "nodes":             [n.as_dict() for n in self.nodes],
        }


# ════════════════════════════════════════════════════════════════════
#  Per-node screen
# ════════════════════════════════════════════════════════════════════

def screen_node(
    node: EqMapNode,
    neighbors: Sequence[NeighborRow],
    *,
    request_T_C: float,
    request_I_M: float,
) -> NodeScreen:
    """Compute the flags + severity for one node.

    ``neighbors`` is the FULL sibling list from
    :func:`neighbor_query.get_node_neighbors`.  The chosen node's own
    vlm_id is included in that list (it is *one of* the siblings); the
    screen consults only the OTHER vlm_ids when comparing.
    """
    flags: List[str] = []
    notes: List[str] = []

    same_vlm = lambda r: (r.vlm_id is not None and r.vlm_id == node.vlm_id)
    others = [r for r in neighbors if not same_vlm(r)]
    K_others = [r for r in others if r.constant_type.upper() == "K"]
    K_all_incl = [r for r in neighbors if r.constant_type.upper() == "K"]
    H_others = [r for r in others if r.constant_type.upper() == "H"]
    S_others = [r for r in others if r.constant_type.upper() == "S"]

    # ── K_H_S_contamination ───────────────────────────────────
    if node.constant_type.upper() != "K":
        flags.append("K_H_S_contamination")
        notes.append(
            f"chosen row constant_type={node.constant_type!r} "
            f"(not 'K'); the equation builder treats it as logK"
        )
    elif not K_all_incl and (H_others or S_others):
        flags.append("K_H_S_contamination")
        notes.append(
            "no K siblings exist for this triple but H/S rows do; "
            "the chosen row may itself be miscoded"
        )

    # ── single_observation / beta_def_orphan ─────────────────
    if not others:
        flags.append("single_observation")
    if not K_others:
        flags.append("beta_def_orphan")

    # ── sign_discord (need ≥ 2 sign-opposite K-siblings) ─────
    if K_others:
        opposite_sign = [
            r for r in K_others
            if _sgn(r.constant_value) != 0
            and _sgn(node.constant_value) != 0
            and _sgn(r.constant_value) != _sgn(node.constant_value)
        ]
        if len(opposite_sign) >= 2:
            flags.append("sign_discord")
            notes.append(
                f"chosen K = {node.constant_value:+.3f}; "
                f"{len(opposite_sign)} of {len(K_others)} K-siblings "
                f"have the opposite sign "
                f"(values: {[round(r.constant_value, 3) for r in opposite_sign]})"
            )

    # ── sibling_sign_split (population spans both signs) ─────
    # Looks at K_others alone; the chosen row's sign is irrelevant
    # because the point is that the *population* is internally
    # inconsistent regardless of which side we landed on.
    if K_others:
        pos_sibs = [r for r in K_others if _sgn(r.constant_value) > 0]
        neg_sibs = [r for r in K_others if _sgn(r.constant_value) < 0]
        if pos_sibs and neg_sibs:
            flags.append("sibling_sign_split")
            notes.append(
                f"K-sibling pool is bimodal in sign: "
                f"{len(pos_sibs)} positive (e.g. vlm_"
                f"{pos_sibs[0].vlm_id}={pos_sibs[0].constant_value:+.3f}) "
                f"vs {len(neg_sibs)} negative (e.g. vlm_"
                f"{neg_sibs[0].vlm_id}={neg_sibs[0].constant_value:+.3f})"
            )

    # ── mad_outlier ──────────────────────────────────────────
    if K_others:
        K_vals = [r.constant_value for r in K_others]
        med = statistics.median(K_vals)
        mad = statistics.median([abs(v - med) for v in K_vals]) or 1e-9
        threshold = MAD_K_SMALL_POP if len(K_others) <= 4 else MAD_K_LARGE_POP
        if abs(node.constant_value - med) > threshold * mad:
            flags.append("mad_outlier")
            notes.append(
                f"chosen K = {node.constant_value:+.3f} deviates by "
                f"{abs(node.constant_value - med):.2f} from sibling median "
                f"{med:+.3f} (MAD {mad:.2f}, threshold {threshold:g}·MAD)"
            )

    # ── mean_median_gap (hidden outlier in the population) ───
    # Even when the chosen value sits on the median, a wide
    # mean↔median gap means one sibling is yanking the mean — i.e.
    # there's a latent outlier worth surfacing for review.
    if len(K_others) >= MEAN_MEDIAN_GAP_MIN_N:
        K_vals = [r.constant_value for r in K_others]
        med = statistics.median(K_vals)
        mn = statistics.mean(K_vals)
        gap = abs(mn - med)
        if gap > MEAN_MEDIAN_GAP_LOGK:
            flags.append("mean_median_gap")
            notes.append(
                f"K-siblings: mean={mn:+.3f} vs median={med:+.3f} "
                f"(gap {gap:.2f} > {MEAN_MEDIAN_GAP_LOGK:g} logK over "
                f"n={len(K_others)} siblings); a hidden outlier is "
                f"distorting the mean"
            )

    # ── nearest_request_sign_mismatch ────────────────────────
    # Fires when the at-request sibling exists, is NOT the chosen
    # row itself, and its sign opposes the chosen value. Captures
    # the case where the deterministic selector deliberately
    # bypassed the at-request datum (because it conflicts with the
    # rest of the population) — that bypass is itself worth
    # surfacing to the agent.
    if K_others:
        at_request = [
            r for r in K_others
            if r.temperature_C is not None
            and r.ionic_strength_M is not None
            and abs(r.temperature_C - request_T_C) <= T_NEAR_TOL_C
            and abs(r.ionic_strength_M - request_I_M) <= I_NEAR_TOL_M
        ]
        sign_opp = [
            r for r in at_request
            if _sgn(r.constant_value) != 0
            and _sgn(node.constant_value) != 0
            and _sgn(r.constant_value) != _sgn(node.constant_value)
        ]
        if sign_opp:
            r0 = sign_opp[0]
            flags.append("nearest_request_sign_mismatch")
            notes.append(
                f"sibling vlm_{r0.vlm_id} sits at request "
                f"(T={r0.temperature_C}, I={r0.ionic_strength_M}) with "
                f"K={r0.constant_value:+.3f}, sign-opposite to chosen "
                f"K={node.constant_value:+.3f}; the selector bypassed "
                f"the at-request datum"
            )

    # ── wide_TI_distance ─────────────────────────────────────
    near_request_K = _siblings_near_request(
        K_all_incl, request_T_C, request_I_M,
        T_tol=T_NEAR_TOL_C, I_tol=I_NEAR_TOL_M,
    )
    chosen_at_request = (
        node.temperature_C is not None
        and node.ionic_strength_M is not None
        and abs(node.temperature_C - request_T_C) <= T_NEAR_TOL_C
        and abs(node.ionic_strength_M - request_I_M) <= I_NEAR_TOL_M
    )
    if not chosen_at_request and not near_request_K:
        flags.append("wide_TI_distance")
        notes.append(
            f"chosen (T={node.temperature_C}, I={node.ionic_strength_M}) "
            f"is far from request "
            f"(T={request_T_C}, I={request_I_M}); "
            f"no K-sibling within ±{T_NEAR_TOL_C} °C / ±{I_NEAR_TOL_M} M either"
        )

    # ── severity ─────────────────────────────────────────────
    if (
        "sign_discord" in flags
        or "K_H_S_contamination" in flags
        or "nearest_request_sign_mismatch" in flags
    ):
        severity = "critical"
    elif (
        "sibling_sign_split" in flags
        or "mean_median_gap" in flags
        or "mad_outlier" in flags
        or "wide_TI_distance" in flags
        or ("beta_def_orphan" in flags and "single_observation" in flags)
    ):
        severity = "warn"
    else:
        severity = "ok"

    nearest_summary = _nearest_K_summary(K_all_incl, request_T_C, request_I_M)
    K_summary = _K_summary(K_all_incl)

    return NodeScreen(
        node=node,
        flags=flags,
        severity=severity,
        n_neighbors=len(neighbors),
        n_K_neighbors=len(K_all_incl),
        K_neighbor_summary=K_summary,
        nearest_K_at_request=nearest_summary,
        notes=notes,
    )


# ════════════════════════════════════════════════════════════════════
#  Eq-map level screen (consumed by validator orchestrator)
# ════════════════════════════════════════════════════════════════════

def screen_eq_map(
    *,
    pair_key: str,
    eq_map_meta: Dict[str, Any],
    request_T_C: float,
    request_I_M: float,
) -> EqMapScreen:
    """Screen every node of a draft eq-map for one (metal, ligand) pair.

    Reads the persisted ``maps.json`` and ``ids.json`` from
    ``eq_map_meta`` (paths produced by
    :func:`build_or_load_ref_pair_eq_map`), expands every selected
    network into its eq_node rows (the same SQL the equation builder
    runs), then calls :func:`screen_node` for each.
    """
    nodes = _materialize_nodes_from_eq_map(eq_map_meta)
    screens: List[NodeScreen] = []
    for n in nodes:
        neighbors = get_node_neighbors(
            n.metal_id, n.ligand_id, n.beta_definition_id,
        )
        screens.append(screen_node(
            n, neighbors,
            request_T_C=request_T_C,
            request_I_M=request_I_M,
        ))
    return EqMapScreen(
        pair_key=pair_key,
        request_T_C=float(request_T_C),
        request_I_M=float(request_I_M),
        nodes=screens,
    )


# ════════════════════════════════════════════════════════════════════
#  Internals — materialize nodes from selected_map JSON
# ════════════════════════════════════════════════════════════════════

def _materialize_nodes_from_eq_map(eq_map_meta: Dict[str, Any]) -> List[EqMapNode]:
    """Re-run the eq_node SQL the equation builder uses, per selected
    network in the maps.json, and return the resulting EqMapNode list.
    """
    import sys
    _SRD46_ROOT = Path(__file__).absolute().parents[6]
    if str(_SRD46_ROOT) not in sys.path:
        sys.path.insert(0, str(_SRD46_ROOT))
    from NIST_SRD46_core_db_search_tools._db_connection import (
        get_equilibrium_db,
    )

    maps_path = Path(eq_map_meta["maps_json_path"])
    payload = json.loads(maps_path.read_text(encoding="utf-8"))
    pairs = payload.get("pairs", [])

    sql = """
        SELECT node_db_id, vlm_id, network_db_id,
               metal_id, ligand_id, beta_definition_id,
               constant_type, constant_value,
               temperature, ionic_strength,
               equation_python
        FROM eq_node
        WHERE network_db_id = ?
    """
    out: List[EqMapNode] = []
    seen_keys: set = set()
    with get_equilibrium_db() as conn:
        for pair in pairs:
            for nid in pair.get("selected_network_ids", []):
                rows = conn.execute(sql, (int(nid),)).fetchall()
                for r in rows:
                    try:
                        val = float(r["constant_value"])
                    except (TypeError, ValueError):
                        continue
                    node = EqMapNode(
                        metal_id=int(r["metal_id"]),
                        ligand_id=int(r["ligand_id"]),
                        beta_definition_id=int(r["beta_definition_id"]),
                        network_db_id=int(r["network_db_id"]),
                        vlm_id=int(r["vlm_id"]) if r["vlm_id"] is not None else None,
                        constant_type=str(r["constant_type"] or "?").strip(),
                        constant_value=val,
                        temperature_C=_safe_float(r["temperature"]),
                        ionic_strength_M=_safe_float(r["ionic_strength"]),
                        equation_str=str(r["equation_python"] or ""),
                        node_db_id=int(r["node_db_id"]),
                    )
                    if node.node_key in seen_keys:
                        continue
                    seen_keys.add(node.node_key)
                    out.append(node)
    return out


def _siblings_near_request(
    rows: Iterable[NeighborRow],
    T_C: float,
    I_M: float,
    *,
    T_tol: float,
    I_tol: float,
) -> List[NeighborRow]:
    out: List[NeighborRow] = []
    for r in rows:
        if r.temperature_C is None or r.ionic_strength_M is None:
            continue
        if abs(r.temperature_C - T_C) <= T_tol and abs(r.ionic_strength_M - I_M) <= I_tol:
            out.append(r)
    return out


def _nearest_K_summary(
    K_rows: Sequence[NeighborRow],
    T_C: float,
    I_M: float,
) -> Optional[Dict[str, Any]]:
    if not K_rows:
        return None
    def _dist(r: NeighborRow) -> float:
        if r.temperature_C is None or r.ionic_strength_M is None:
            return math.inf
        # Normalize T by 25 °C, I by 0.1 M for a unitless distance.
        return math.hypot((r.temperature_C - T_C) / 25.0,
                          (r.ionic_strength_M - I_M) / 0.1)
    nearest = min(K_rows, key=_dist)
    return {
        "vlm_id":          nearest.vlm_id,
        "K":               nearest.constant_value,
        "T_C":             nearest.temperature_C,
        "I_M":             nearest.ionic_strength_M,
        "dT_C":            (nearest.temperature_C - T_C) if nearest.temperature_C is not None else None,
        "dI_M":            (nearest.ionic_strength_M - I_M) if nearest.ionic_strength_M is not None else None,
        "source_table":    nearest.source_table,
    }


def _K_summary(K_rows: Sequence[NeighborRow]) -> Dict[str, Any]:
    if not K_rows:
        return {"n": 0}
    vals = [r.constant_value for r in K_rows]
    return {
        "n":      len(vals),
        "min":    min(vals),
        "max":    max(vals),
        "median": statistics.median(vals),
        "mean":   statistics.mean(vals),
    }


def _sgn(x: float) -> int:
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0


def _safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
