"""Deterministic builder for SRD46 speciation-card equations.

Queries the equilibrium maps database directly and builds the
``equations`` section of a speciation card.
"""

from __future__ import annotations

import json
import math
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any
import sys

# ── DB access setup (NIST_SRD46_core_db_search_tools) ─────────────
_SRD46_ROOT = Path(__file__).absolute().parents[6]  # SRD46_query_agent/
if str(_SRD46_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRD46_ROOT))

from NIST_SRD46_core_db_search_tools._db_connection import (
    get_equilibrium_db,
)


PROTON_METAL_ID = 68
HYDROXIDE_LIGAND_ID = 10076


# ═══════════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════════

def build_card_from_component_template(
    *,
    component_template_json_path: str | Path,
    selected_map_json_path: str | Path,
    output_json_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build a full card by filling only the ``equations`` section.

    Parameters
    ----------
    component_template_json_path : path to a JSON with ``components``
    selected_map_json_path : path to the equilibrium-map selection JSON
    output_json_path : optional output path for the completed card
    """
    card = _read_json(component_template_json_path)
    card["equations"] = build_equations_from_map_json(
        components=card["components"],
        selected_map_json_path=selected_map_json_path,
    )
    card.setdefault("excluded_species", [])
    recompute_include_calculation(card)
    if output_json_path is not None:
        _write_json(output_json_path, card)
    return card


def build_final_card(
    *,
    component_template_json_path: str | Path,
    selected_map_json_path: str | Path,
    output_json_path: str | Path,
    temperature: float,
    ionic_strength: float,
) -> dict[str, Any]:
    """High-level assembly: components + equations.

    This replaces the old agentic workflow's ``execute_build_final_card``.
    """
    for name, value in (("temperature", temperature),
                        ("ionic_strength", ionic_strength)):
        if isinstance(value, bool):
            raise ValueError(f"{name} must be an explicit numeric value")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be an explicit numeric value") from exc
        if not math.isfinite(number):
            raise ValueError(f"{name} must be finite")
        if name == "ionic_strength" and number < 0:
            raise ValueError("ionic_strength must be >= 0")
    final_card = build_card_from_component_template(
        component_template_json_path=component_template_json_path,
        selected_map_json_path=selected_map_json_path,
        output_json_path=None,
    )
    ordered_card: dict[str, Any] = {}
    ordered_card["components"] = final_card["components"]
    ordered_card["ionic_strength"] = float(ionic_strength)
    # This card records an explicitly supplied reference condition.  Zero
    # ionic strength is still a fixed value; it must not silently select auto-I.
    ordered_card["ionic_strength_mode"] = "fixed"
    for key in final_card:
        if key not in ("components", "ionic_strength", "ionic_strength_mode"):
            ordered_card[key] = final_card[key]
    _write_json(output_json_path, ordered_card)
    return ordered_card


def build_equations_from_map_json(
    *,
    components: dict[str, Any],
    selected_map_json_path: str | Path,
) -> dict[str, Any]:
    """Build only the ``equations`` object from selected equilibrium maps."""
    selected_map_payload = _read_json(selected_map_json_path)
    component_index = _build_component_index(components)

    aqueous_blocks: list[dict[str, Any]] = []
    dissociation_blocks: list[dict[str, Any]] = []

    for pair in selected_map_payload.get("pairs", []):
        pair_rows = _fetch_pair_rows(pair)  # raises ValueError if no rows

        block_header = _build_pair_block_header(pair, component_index)
        aqueous_entries: list[dict[str, Any]] = []
        dissociation_entries: list[dict[str, Any]] = []

        for row in pair_rows:
            entry = _build_equilibrium_entry(row, pair, component_index)
            if _is_dissociation_entry(entry):
                dissociation_entries.append(entry)
            else:
                aqueous_entries.append(entry)

        network_ids = pair.get("selected_network_ids", [])
        if aqueous_entries:
            aqueous_blocks.append({
                "metal_ligand_system": deepcopy(block_header),
                "selected_network_ids": list(network_ids),
                "equilibria": aqueous_entries,
            })
        if dissociation_entries:
            dissociation_blocks.append({
                "metal_ligand_system": deepcopy(block_header),
                "selected_network_ids": list(network_ids),
                "equilibria": dissociation_entries,
            })

    equations: dict[str, Any] = {}
    if aqueous_blocks:
        equations["metal_ligand_system_aqueous_only"] = aqueous_blocks
    if dissociation_blocks:
        equations["metal_ligand_system_dissociation_only"] = dissociation_blocks
    return equations


# ═══════════════════════════════════════════════════════════════════
#  include_calculation recomputation
# ═══════════════════════════════════════════════════════════════════

def recompute_include_calculation(card: dict[str, Any]) -> None:
    """Recompute ``include_calculation`` on every equilibrium from ``excluded_species``."""
    excluded = set(card.get("excluded_species", []))
    for _section_key, eq_groups in card.get("equations", {}).items():
        if not isinstance(eq_groups, list):
            continue
        for group in eq_groups:
            for eq in group.get("equilibria", []):
                rhs_species = {item["species"] for item in eq.get("RHS", [])}
                lhs_species = {item["species"] for item in eq.get("LHS", [])}
                all_species = rhs_species | lhs_species
                eq["include_calculation"] = not bool(all_species & excluded)


# ═══════════════════════════════════════════════════════════════════
#  DB fetch helpers — direct queries against eq_node + eq_node_species
# ═══════════════════════════════════════════════════════════════════

_EQ_SPECIES_RE = re.compile(r"\[([^\]]+)\](\^(\d+))?")


def _parse_equation_powers(equation_python: str | None) -> dict[str, int]:
    """Parse stoichiometric powers from the ``equation_python`` string.

    The format is ``[SpeciesA]^p + [SpeciesB] <=> [ProductC]^q``.
    Returns a dict mapping the raw species token (without brackets) to
    its integer power (defaults to 1 when ``^N`` is absent).
    """
    if not equation_python:
        raise ValueError(
            "equation_python is Not defined; stoichiometric powers cannot be inferred")
    powers: dict[str, int] = {}
    for m in _EQ_SPECIES_RE.finditer(equation_python):
        token = m.group(1)
        p = int(m.group(3)) if m.group(3) else 1
        powers[token] = p
    if not powers:
        raise ValueError(
            f"equation_python contains no parseable species: {equation_python!r}")
    return powers


def _fetch_network_nodes(network_db_id: int) -> list[dict[str, Any]]:
    """Fetch all nodes for a network with their LHS/RHS species.

    Powers are read from ``eq_node.equation_python`` (``[M]^2 + [L] <=> [M2L]``
    notation) rather than being hardcoded to 1.  The ``eq_node_species`` table
    does not store per-species stoichiometric coefficients, so the ``equation_python``
    column is the authoritative source for non-unity powers.
    """
    with get_equilibrium_db() as conn:
        nodes = conn.execute(
            """
            SELECT node_db_id, vlm_id, constant_type,
                   constant_value AS log_K, temperature, ionic_strength,
                   equation_python, beta_definition_id, metal_id, ligand_id
            FROM eq_node
            WHERE network_db_id = ?
            """,
            (network_db_id,),
        ).fetchall()

        result: list[dict[str, Any]] = []
        for node in nodes:
            node_dict = dict(node)
            eq_python = node_dict.pop("equation_python", None)
            powers = _parse_equation_powers(eq_python)

            species_rows = conn.execute(
                "SELECT species, side FROM eq_node_species WHERE node_db_id = ?",
                (node_dict["node_db_id"],),
            ).fetchall()

            lhs: list[dict[str, Any]] = []
            rhs: list[dict[str, Any]] = []
            for sp in species_rows:
                species_str = sp["species"]
                phase = "solid" if "(s" in species_str else "aqueous"
                # Strip brackets to look up the power parsed from equation_python
                bare = _strip_brackets(species_str)
                if bare not in powers:
                    raise ValueError(
                        f"species {species_str!r} is absent from equation_python; "
                        "its stoichiometric power is Not defined")
                power = powers[bare]
                entry = {"species": species_str, "power": power, "phase": phase}
                if sp["side"] == "LHS":
                    lhs.append(entry)
                else:
                    rhs.append(entry)

            node_dict["LHS_species_json"] = lhs
            node_dict["RHS_species_json"] = rhs
            result.append(node_dict)

        return result


def _fetch_node_by_vlm_id(
    vlm_id: int,
    metal_id: int,
    ligand_id: int,
    beta_definition_id: int,
) -> dict[str, Any] | None:
    """Fetch a single eq_node row by vlm_id (cross-network).

    Used by the ``vlm_overrides`` machinery so the L3 fixer can
    promote a sibling row that was NOT in the originally selected
    networks for this pair.  Returns the row dict in the same shape
    as :func:`_fetch_network_nodes` (with ``LHS_species_json`` /
    ``RHS_species_json``), or ``None`` if no eq_node row matches.
    """
    with get_equilibrium_db() as conn:
        row = conn.execute(
            """
            SELECT node_db_id, vlm_id, constant_type,
                   constant_value AS log_K, temperature, ionic_strength,
                   equation_python, beta_definition_id, metal_id, ligand_id
            FROM eq_node
            WHERE vlm_id = ? AND metal_id = ? AND ligand_id = ?
              AND beta_definition_id = ?
            ORDER BY node_db_id
            LIMIT 1
            """,
            (int(vlm_id), int(metal_id), int(ligand_id), int(beta_definition_id)),
        ).fetchone()
        if row is None:
            return None
        node_dict = dict(row)
        eq_python = node_dict.pop("equation_python", None)
        powers = _parse_equation_powers(eq_python)
        species_rows = conn.execute(
            "SELECT species, side FROM eq_node_species WHERE node_db_id = ?",
            (node_dict["node_db_id"],),
        ).fetchall()
        lhs: list[dict[str, Any]] = []
        rhs: list[dict[str, Any]] = []
        for sp in species_rows:
            species_str = sp["species"]
            phase = "solid" if "(s" in species_str else "aqueous"
            bare = _strip_brackets(species_str)
            if bare not in powers:
                raise ValueError(
                    f"species {species_str!r} is absent from equation_python; "
                    "its stoichiometric power is Not defined")
            power = powers[bare]
            entry = {"species": species_str, "power": power, "phase": phase}
            if sp["side"] == "LHS":
                lhs.append(entry)
            else:
                rhs.append(entry)
        node_dict["LHS_species_json"] = lhs
        node_dict["RHS_species_json"] = rhs
        return node_dict


def _fetch_pair_rows(pair: dict[str, Any]) -> list[dict[str, Any]]:
    """Fetch equilibrium nodes for a pair using its ``selected_network_ids``.

    Measured pairs declare at least one ``selected_network_id``.  On the
    enabled LC1_3 path, a support-only pair may instead carry validated
    ``estimated_eq_nodes`` with negative session IDs.  Fetching by raw
    measured ``vlm_ids`` remains unsupported.

    Raises
    ------
    ValueError
        If neither measured networks nor validated estimated nodes are
        present, or if declared network IDs return no equilibrium nodes.
    """
    network_ids = pair.get("selected_network_ids", [])
    estimated_rows = pair.get("estimated_eq_nodes", [])
    if not network_ids and not estimated_rows:
        raise ValueError(
            f"Pair (metal_id={pair.get('metal_id')!r}, "
            f"ligand_id={pair.get('ligand_id')!r}) has no "
            f"'selected_network_ids'.  Every pair must reference at least "
            f"one curated equilibrium network."
        )

    rows: list[dict[str, Any]] = []
    for network_id in network_ids:
        rows.extend(_fetch_network_nodes(int(network_id)))

    if network_ids and not rows:
        raise ValueError(
            f"Pair (metal_id={pair.get('metal_id')!r}, "
            f"ligand_id={pair.get('ligand_id')!r}) with "
            f"selected_network_ids={network_ids!r} returned no equilibrium "
            f"nodes from the database.  Verify the network IDs are correct."
        )

    rows = _dedupe_rows(rows)
    rows = _apply_vlm_overrides(rows, pair.get("vlm_overrides", []))
    rows = _merge_estimated_rows(rows, estimated_rows, pair=pair)
    if not rows:
        raise ValueError(
            f"Pair (metal_id={pair.get('metal_id')!r}, "
            f"ligand_id={pair.get('ligand_id')!r}) has no usable measured "
            "or estimated equilibrium nodes after deterministic merging."
        )
    return rows


def _reaction_signature(row: dict[str, Any]) -> tuple[Any, ...]:
    """Return an orientation-preserving species/stoichiometry signature."""

    def side(value: Any) -> tuple[tuple[str, int, str], ...]:
        entries = _load_species_list(value)
        normalized = []
        for item in entries:
            if "power" not in item or isinstance(item["power"], bool):
                raise ValueError("estimated equilibrium species power is Not defined")
            power = item["power"]
            if isinstance(power, float) and power.is_integer():
                power = int(power)
            phase = item.get("phase")
            if phase is None or not str(phase).strip():
                raise ValueError("estimated equilibrium species phase is Not defined")
            normalized.append((
                str(item.get("species", "")).strip(),
                int(power),
                str(phase).strip().lower(),
            ))
        return tuple(sorted(normalized))

    return side(row.get("LHS_species_json")), side(row.get("RHS_species_json"))


def _merge_estimated_rows(
    measured_rows: list[dict[str, Any]],
    estimated_rows: Any,
    *,
    pair: dict[str, Any],
) -> list[dict[str, Any]]:
    """Merge native support nodes before equation materialization.

    A measured row for the same pair and beta definition always wins.  An
    estimate that assigns a different beta definition to an already-present
    reaction is rejected because that would disconnect the value from the
    canonical SRD46 beta topology used to build the support map.
    """

    if not estimated_rows:
        return measured_rows
    if not isinstance(estimated_rows, list):
        raise ValueError("estimated_eq_nodes must be a list of native adapted rows")

    pair_ids = (int(pair["metal_id"]), int(pair["ligand_id"]))
    result = list(measured_rows)
    measured_beta_ids = {
        int(row["beta_definition_id"])
        for row in measured_rows
        if row.get("beta_definition_id") is not None
    }
    reaction_beta: dict[tuple[Any, ...], int] = {}
    for row in measured_rows:
        beta_id = row.get("beta_definition_id")
        if beta_id is not None:
            reaction_beta.setdefault(_reaction_signature(row), int(beta_id))

    appended_beta_ids: set[int] = set()
    for index, raw in enumerate(estimated_rows):
        if not isinstance(raw, dict):
            raise ValueError(f"estimated_eq_nodes[{index}] must be an object")
        row = deepcopy(raw)
        required = {
            "node_db_id", "vlm_id", "constant_type", "log_K", "temperature",
            "ionic_strength", "equation_python", "beta_definition_id",
            "beta_definition_name", "metal_id", "ligand_id",
            "LHS_species_json", "RHS_species_json", "_estimated_provenance",
        }
        missing = sorted(required - set(row))
        if missing:
            raise ValueError(
                f"estimated_eq_nodes[{index}] lacks required fields: {missing}"
            )
        if (int(row["metal_id"]), int(row["ligand_id"])) != pair_ids:
            raise ValueError(
                f"estimated_eq_nodes[{index}] belongs to another chemical pair"
            )
        if int(row["node_db_id"]) >= 0 or int(row["vlm_id"]) >= 0:
            raise ValueError(
                f"estimated_eq_nodes[{index}] must retain negative session IDs"
            )
        beta_id = int(row["beta_definition_id"])
        if beta_id in measured_beta_ids:
            # Authoritative measured coverage takes precedence regardless of
            # the estimated value or its uncertainty.
            continue
        signature = _reaction_signature(row)
        existing_beta = reaction_beta.get(signature)
        if existing_beta is not None and existing_beta != beta_id:
            raise ValueError(
                "reaction/beta-definition collision for "
                f"metal_{pair_ids[0]}/ligand_{pair_ids[1]}: the same reaction "
                f"is assigned to beta_def_{existing_beta} and beta_def_{beta_id}"
            )
        if beta_id in appended_beta_ids:
            raise ValueError(
                f"ambiguous duplicate estimated beta_def_{beta_id} for "
                f"metal_{pair_ids[0]}/ligand_{pair_ids[1]}"
            )
        reaction_beta[signature] = beta_id
        appended_beta_ids.add(beta_id)
        result.append(row)
    return result


# ═══════════════════════════════════════════════════════════════════
#  vlm_overrides — patches emitted by the L2_1_1b L3 fixer agent
# ═══════════════════════════════════════════════════════════════════

_OVERRIDE_ACTIONS = {"pick_vlm", "median_K", "mean_K", "drop_node", "set_value"}


def _apply_vlm_overrides(
    rows: list[dict[str, Any]],
    overrides: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Apply per-(beta_definition_id) curation patches to fetched rows.

    Each override dict has the shape produced by
    ``l2_1_1b_eqmap_l3_fixer_agent.finalize_patch``::

        { "beta_definition_id": 812,
          "action": "pick_vlm" | "median_K" | "mean_K" | "drop_node" | "set_value",
          "vlm_id": 157619,            # required for 'pick_vlm' and 'set_value'
          "include_vlm_ids": [...],    # required for median_K / mean_K
          "chosen_value": -8.57,       # required for 'set_value'
          "rationale": "..." }

    Behaviour by action:

    * ``pick_vlm``    — keep only the row whose ``vlm_id`` matches; drop
                        all other rows for that beta_definition_id.
    * ``median_K`` /
      ``mean_K``      — replace all rows for that beta_definition_id
                        with one synthetic row carrying the median /
                        mean of the rows in ``include_vlm_ids``.  The
                        synthetic row inherits its equation / phases
                        from the first ``include_vlm_ids`` member.
    * ``drop_node``   — remove every row for that beta_definition_id.
    * ``set_value``   — locate the row with ``vlm_id`` (cross-network
                        fetch if absent), overwrite its ``log_K`` with
                        ``chosen_value``, keep that single row.  The
                        original ``vlm_id`` is preserved for provenance;
                        the override is recorded under
                        ``_synthetic_origin``.  Emitted by the LC1_2
                        validator for at-request / cluster-median picks.
    """
    if not overrides:
        return rows

    by_beta: dict[int, list[dict[str, Any]]] = {}
    untouched: list[dict[str, Any]] = []
    for r in rows:
        bd = r.get("beta_definition_id")
        if bd is None:
            untouched.append(r)
        else:
            by_beta.setdefault(int(bd), []).append(r)

    for ov in overrides:
        try:
            bd = int(ov["beta_definition_id"])
            action = str(ov["action"])
            metal_id_ov = int(ov.get("metal_id") or 0)
            ligand_id_ov = int(ov.get("ligand_id") or 0)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"malformed vlm_override {ov!r}: {exc}") from exc
        if action not in _OVERRIDE_ACTIONS:
            raise ValueError(
                f"vlm_override action {action!r} not in {sorted(_OVERRIDE_ACTIONS)}"
            )
        bucket = by_beta.get(bd, [])
        # Determine metal/ligand from bucket if not in override
        if (not metal_id_ov or not ligand_id_ov) and bucket:
            metal_id_ov = int(bucket[0].get("metal_id") or 0)
            ligand_id_ov = int(bucket[0].get("ligand_id") or 0)

        if action == "drop_node":
            by_beta[bd] = []
            continue

        if action == "pick_vlm":
            target_vlm = ov.get("vlm_id")
            if target_vlm is None:
                raise ValueError(
                    f"vlm_override action='pick_vlm' missing 'vlm_id': {ov!r}"
                )
            kept = [r for r in bucket if r.get("vlm_id") == int(target_vlm)]
            if not kept:
                # Cross-network fetch: promote a sibling vlm_id from
                # another network into this pair.
                fetched = _fetch_node_by_vlm_id(
                    int(target_vlm), metal_id_ov, ligand_id_ov, bd,
                )
                if fetched is None:
                    raise ValueError(
                        f"vlm_override pick_vlm={target_vlm} not found in DB "
                        f"for (metal_id={metal_id_ov}, ligand_id={ligand_id_ov}, "
                        f"beta_definition_id={bd})"
                    )
                kept = [fetched]
            picked = deepcopy(kept[0])
            picked["_synthetic_origin"] = {
                "action": "pick_vlm",
                "selected_vlm_id": int(target_vlm),
                "rationale": ov.get("rationale", ""),
            }
            by_beta[bd] = [picked]
            continue

        if action == "set_value":
            target_vlm = ov.get("vlm_id")
            if target_vlm is None:
                raise ValueError(
                    f"vlm_override action='set_value' missing 'vlm_id': {ov!r}"
                )
            if "chosen_value" not in ov:
                raise ValueError(
                    f"vlm_override action='set_value' missing 'chosen_value': {ov!r}"
                )
            chosen = float(ov["chosen_value"])
            kept = [r for r in bucket if r.get("vlm_id") == int(target_vlm)]
            if not kept:
                fetched = _fetch_node_by_vlm_id(
                    int(target_vlm), metal_id_ov, ligand_id_ov, bd,
                )
                if fetched is None:
                    raise ValueError(
                        f"vlm_override set_value vlm_id={target_vlm} not found in DB "
                        f"for (metal_id={metal_id_ov}, ligand_id={ligand_id_ov}, "
                        f"beta_definition_id={bd})"
                    )
                kept = [fetched]
            proto = deepcopy(kept[0])
            original = proto.get("log_K")
            proto["log_K"] = chosen
            proto["_synthetic_origin"] = {
                "action": "set_value",
                "source_vlm_id": int(target_vlm),
                "original_log_K": original,
                "chosen_value": chosen,
                "rationale": ov.get("rationale", ""),
            }
            by_beta[bd] = [proto]
            continue

        # median_K / mean_K
        include = ov.get("include_vlm_ids") or []
        if not include:
            raise ValueError(
                f"vlm_override action={action!r} requires non-empty "
                f"'include_vlm_ids': {ov!r}"
            )
        include_set = {int(x) for x in include}
        members = [r for r in bucket if r.get("vlm_id") in include_set]
        # Pull any missing members from the DB (cross-network).
        missing_vlms = include_set - {int(r["vlm_id"]) for r in members
                                       if r.get("vlm_id") is not None}
        for vid in sorted(missing_vlms):
            fetched = _fetch_node_by_vlm_id(
                vid, metal_id_ov, ligand_id_ov, bd,
            )
            if fetched is None:
                raise ValueError(
                    f"vlm_override {action} include_vlm_ids member {vid} not "
                    f"found in DB for (metal_id={metal_id_ov}, "
                    f"ligand_id={ligand_id_ov}, beta_definition_id={bd})"
                )
            members.append(fetched)
        if not members:
            raise ValueError(
                f"vlm_override {action} include_vlm_ids={sorted(include_set)} "
                f"matched no row in beta_definition_id={bd}"
            )
        K_members = [r for r in members
                     if str(r.get("constant_type") or "").upper() == "K"]
        if not K_members:
            raise ValueError(
                f"vlm_override {action} on beta_definition_id={bd}: none of "
                f"the included rows have constant_type='K'"
            )
        values = [float(r["log_K"]) for r in K_members]
        if action == "median_K":
            import statistics as _stats
            agg = float(_stats.median(values))
            tag = "median"
        else:
            agg = float(sum(values)) / len(values)
            tag = "mean"
        proto = deepcopy(K_members[0])
        proto["log_K"] = agg
        proto["vlm_id"] = None  # synthetic: not from any single source row
        proto["_synthetic_origin"] = {
            "action": action,
            "include_vlm_ids": sorted(include_set),
            "n_rows": len(K_members),
            "agg": tag,
            "value": agg,
            "rationale": ov.get("rationale", ""),
        }
        by_beta[bd] = [proto]

    out: list[dict[str, Any]] = list(untouched)
    for bd, bucket in by_beta.items():
        out.extend(bucket)
    return out


# ═══════════════════════════════════════════════════════════════════
#  Component index
# ═══════════════════════════════════════════════════════════════════

def _build_component_index(components: dict[str, Any]) -> dict[str, Any]:
    by_metal_id: dict[int, dict[str, Any]] = {}
    by_ligand_id: dict[int, dict[str, Any]] = {}

    for display_name, entry in components.items():
        reference_id = str(entry.get("reference", {}).get("source_database_ID", ""))
        info = {
            "display_name": display_name,
            "spec_id": entry["spec_id"],
            "entry": entry,
        }
        if reference_id.startswith("metal_"):
            by_metal_id[int(reference_id.split("_", 1)[1])] = info
        elif reference_id.startswith("ligand_"):
            by_ligand_id[int(reference_id.split("_", 1)[1])] = info

    return {
        "metals": by_metal_id,
        "ligands": by_ligand_id,
        "proton": by_metal_id[PROTON_METAL_ID],
        "hydroxide": by_ligand_id[HYDROXIDE_LIGAND_ID],
    }


def _build_pair_block_header(
    pair: dict[str, Any], component_index: dict[str, Any],
) -> dict[str, Any]:
    metal_id = int(pair["metal_id"])
    ligand_id = int(pair["ligand_id"])
    metal_info = component_index["metals"][metal_id]
    ligand_info = component_index["ligands"][ligand_id]
    ligand_entry = ligand_info["entry"]

    return {
        "metal": [[metal_info["spec_id"], metal_info["display_name"]]],
        "ligand": [[ligand_info["spec_id"], ligand_info["display_name"]]],
        "ligand_canonical_HOL": deepcopy(ligand_entry["ligand_canonical_HOL"]),
    }


# ═══════════════════════════════════════════════════════════════════
#  Equilibrium entry builder
# ═══════════════════════════════════════════════════════════════════

def _build_equilibrium_entry(
    row: dict[str, Any],
    pair: dict[str, Any],
    component_index: dict[str, Any],
) -> dict[str, Any]:
    lhs_raw = _load_species_list(row.get("LHS_species_json"))
    rhs_raw = _load_species_list(row.get("RHS_species_json"))
    raw_log_k = row.get("log_K")
    if raw_log_k is None or isinstance(raw_log_k, bool):
        raise ValueError("equilibrium log_K is Not defined")
    try:
        log_k = float(raw_log_k)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"equilibrium log_K must be numeric, got {raw_log_k!r}") from exc
    if not math.isfinite(log_k):
        raise ValueError("equilibrium log_K must be finite")

    lhs = [_transform_species_entry(item, pair, component_index) for item in lhs_raw]
    rhs = [_transform_species_entry(item, pair, component_index) for item in rhs_raw]

    equation_str = _format_equation_str(lhs, rhs)

    additional_notes = ""
    if _contains_solid_phase(lhs) and "H2O" in equation_str:
        lhs_species = " ".join(item["species"] for item in lhs)
        if "OOH" in lhs_species and "alpha" in lhs_species:
            additional_notes = "H2O (activity=1) omitted from LHS array; goethite dissolution"
        elif "O3" in lhs_species and "alpha" in lhs_species:
            additional_notes = "H2O (activity=1) omitted from LHS array; hematite dissolution"
        else:
            additional_notes = "H2O (activity=1) omitted from LHS array"

    vlm_id_raw = row.get("vlm_id")
    synth = row.get("_synthetic_origin")
    estimated = row.get("_estimated_provenance")
    patch_notes: dict[str, Any] | None = None
    reference_source = "NIST SRD-46"
    if estimated:
        node_db_id = int(row["node_db_id"])
        source_id = f"session_eq_node_{node_db_id}"
        reference_source = "SRD46 query estimated values"
        provenance_note = {
            "source": reference_source,
            "source_database_ID": source_id,
            "session_vlm_id": int(row["vlm_id"]),
            "beta_definition_id": int(row["beta_definition_id"]),
            "beta_definition_name": str(row["beta_definition_name"]),
            "evidence_vlm_ids": list(estimated.get("evidence_vlm_ids") or []),
            "evidence_network_ids": list(estimated.get("evidence_network_ids") or []),
            "evidence_citation_ids": list(estimated.get("evidence_citation_ids") or []),
            "estimation_method": estimated.get("estimation_method"),
            "uncertainty_log10": estimated.get("uncertainty_log10"),
            "assumptions": list(estimated.get("assumptions") or []),
            "rationale": estimated.get("rationale"),
            "query_id": estimated.get("query_id"),
            "query_answer_sha256": estimated.get("query_answer_sha256"),
            "evidence_authorization_context_id": estimated.get(
                "evidence_authorization_context_id"
            ),
            "evidence_authorization_sha256": estimated.get(
                "evidence_authorization_sha256"
            ),
        }
        marker = json.dumps(
            provenance_note,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        additional_notes = f"{additional_notes}; {marker}" if additional_notes else marker
        patch_notes = {
            "operation": "estimated_support_eq_map",
            "beta_definition_id": int(row["beta_definition_id"]),
            "beta_definition_name": str(row["beta_definition_name"]),
            "session_node_db_id": node_db_id,
            "session_vlm_id": int(row["vlm_id"]),
            "provenance": deepcopy(estimated),
        }
    elif synth:
        action = synth.get("action")
        if action == "set_value":
            # Same source row, value overwritten: keep original vlm id but
            # mark it as patched (rule: not a source-id swap).
            src_vlm = int(synth["source_vlm_id"])
            source_id = f"vlm_{src_vlm}_patched"
            patch_notes = {
                "operation": "set_value",
                "original_source_database_ID": f"vlm_{src_vlm}",
                "raw_log_K": synth.get("original_log_K"),
                "patched_log_K": synth.get("chosen_value"),
                "rationale": synth.get("rationale", ""),
            }
        elif action == "pick_vlm":
            # A different source row was selected: use the new source id.
            selected = int(synth["selected_vlm_id"])
            source_id = f"vlm_{selected}"
            patch_notes = {
                "operation": "pick_vlm",
                "selected_source_database_ID": f"vlm_{selected}",
                "rationale": synth.get("rationale", ""),
            }
        elif action in ("median_K", "mean_K"):
            included = synth.get("include_vlm_ids") or []
            included_str = ",".join(str(v) for v in included)
            source_id = f"vlm_{synth.get('agg', 'agg')}({included_str})"
            patch_notes = {
                "operation": action,
                "include_source_database_IDs": [f"vlm_{v}" for v in included],
                "patched_log_K": synth.get("value"),
                "rationale": synth.get("rationale", ""),
            }
        elif vlm_id_raw is not None:
            source_id = f"vlm_{int(vlm_id_raw)}"
        else:
            source_id = "vlm_unknown"
    else:
        source_id = f"vlm_{int(vlm_id_raw)}"

    return {
        "equation_str": equation_str,
        "log_K": log_k,
        "constant_type": _format_constant_type(row.get("constant_type")),
        "data_source_temperature": row.get("temperature"),
        "data_source_ionic_strength": row.get("ionic_strength"),
        "reference": {
            "source": reference_source,
            "source_database_ID": source_id,
        },
        "include_calculation": True,
        "additional_notes": additional_notes,
        "patch_notes": patch_notes,
        "LHS": lhs,
        "RHS": rhs,
    }


def _transform_species_entry(
    item: dict[str, Any],
    pair: dict[str, Any],
    component_index: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError(f"equilibrium species entry must be an object, got {item!r}")
    raw_species = item.get("species")
    if raw_species is None or not str(raw_species).strip():
        raise ValueError("equilibrium species token is Not defined")
    species = _transform_species_token(
        _strip_brackets(str(raw_species)),
        metal_id=int(pair["metal_id"]),
        ligand_id=int(pair["ligand_id"]),
        component_index=component_index,
    )
    if "power" not in item or isinstance(item["power"], bool):
        raise ValueError(f"equilibrium species {raw_species!r} power is Not defined")
    try:
        power_number = float(item["power"])
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"equilibrium species {raw_species!r} power must be numeric") from exc
    if not math.isfinite(power_number) or not power_number.is_integer():
        raise ValueError(
            f"equilibrium species {raw_species!r} power must be a finite integer")
    power = int(power_number)
    phase = item.get("phase")
    if phase is None or not str(phase).strip():
        raise ValueError(f"equilibrium species {raw_species!r} phase is Not defined")
    phase = str(phase).strip().lower()
    if phase not in {"aqueous", "solid", "dissolution", "gas"}:
        raise ValueError(
            f"equilibrium species {raw_species!r} has unsupported phase {phase!r}")
    return {
        "species": species,
        "power": power,
        "phase": phase,
    }


def _transform_species_token(
    token: str,
    *,
    metal_id: int,
    ligand_id: int,
    component_index: dict[str, Any],
) -> str:
    metal_spec = component_index["metals"][metal_id]["spec_id"]
    ligand_spec = component_index["ligands"][ligand_id]["spec_id"]
    proton_spec = component_index["proton"]["spec_id"]
    hydroxide_spec = component_index["hydroxide"]["spec_id"]

    phase_suffix = ""
    phase_match = re.search(r"\(s(?:,[^)]*)?\)$", token)
    if phase_match:
        phase_suffix = phase_match.group(0)
        token = token[: phase_match.start()]

    # Parse the source placeholder grammar in one pass.  The old sequence of
    # string replacements first inserted ``<OH>`` and then scanned that new
    # text again, so the H inside the generated token was transformed a
    # second time (``M(OH)L`` became ``<M1>(<O<H>>)<L1>``).  Only characters
    # from the original token may be interpreted as M/L/H placeholders.
    out: list[str] = []
    idx = 0
    while idx < len(token):
        if token.startswith("H2O", idx):
            out.append("H2O")
            idx += 3
            continue
        if token.startswith("(OH)", idx):
            out.append(f"(<{hydroxide_spec}>)")
            idx += 4
            continue
        if token.startswith("OH", idx):
            out.append(f"<{hydroxide_spec}>")
            idx += 2
            continue
        if token[idx] == "<":
            # Be idempotent for already-tokenized inputs and never inspect
            # the contents of an existing angle-bracket token.
            end = token.find(">", idx + 1)
            if end < 0:
                raise ValueError(
                    f"unclosed angle-bracket species token in {token!r}")
            inner = token[idx + 1 : end]
            mapped = {
                "M": metal_spec,
                "L": ligand_spec,
                "H": proton_spec,
                "OH": hydroxide_spec,
            }.get(inner, inner)
            out.append(f"<{mapped}>")
            idx = end + 1
            continue
        char = token[idx]
        if char == "M":
            out.append(f"<{metal_spec}>")
        elif char == "L":
            out.append(f"<{ligand_spec}>")
        elif char == "H":
            out.append(f"<{proton_spec}>")
        else:
            out.append(char)
        idx += 1
    return "".join(out) + phase_suffix


# ═══════════════════════════════════════════════════════════════════
#  Formatting helpers
# ═══════════════════════════════════════════════════════════════════

def _format_equation_str(
    lhs: list[dict[str, Any]], rhs: list[dict[str, Any]],
) -> str:
    return f"{_format_side(lhs)} <=> {_format_side(rhs)}"


def _format_side(entries: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for item in entries:
        if item["power"] == 1:
            parts.append(f"[{item['species']}]")
        else:
            parts.append(f"[{item['species']}]^{item['power']}")
    return " + ".join(parts)


def _format_constant_type(value: Any) -> str:
    if str(value) == "K":
        return "log(K)"
    return f"log({value})"


def _contains_solid_phase(entries: list[dict[str, Any]]) -> bool:
    return any(item.get("phase") == "solid" for item in entries)


def _is_dissociation_entry(entry: dict[str, Any]) -> bool:
    return _contains_solid_phase(entry["LHS"])


def _load_species_list(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, str):
        return json.loads(value)
    return list(value)


def _strip_brackets(species: str) -> str:
    if species.startswith("[") and species.endswith("]"):
        return species[1:-1]
    return species


def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[int] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        vlm_id = int(row["vlm_id"])
        if vlm_id in seen:
            continue
        seen.add(vlm_id)
        out.append(row)
    return out


# ═══════════════════════════════════════════════════════════════════
#  JSON I/O
# ═══════════════════════════════════════════════════════════════════

def _read_json(path: str | Path) -> dict[str, Any]:
    value = os.path.abspath(os.fspath(path))
    if os.name == "nt" and not value.startswith("\\\\?\\"):
        if value.startswith("\\\\"):
            value = "\\\\?\\UNC\\" + value[2:]
        else:
            value = "\\\\?\\" + value
    with open(value, "r", encoding="utf-8") as handle:
        return json.load(handle)
# The paired writer applies the same Windows extended-path normalization.
def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    parent = os.path.abspath(os.fspath(target.parent))
    value = os.path.abspath(os.fspath(target))
    if os.name == "nt":
        if not parent.startswith("\\\\?\\"):
            parent = (
                "\\\\?\\UNC\\" + parent[2:]
                if parent.startswith("\\\\")
                else "\\\\?\\" + parent
            )
        if not value.startswith("\\\\?\\"):
            value = (
                "\\\\?\\UNC\\" + value[2:]
                if value.startswith("\\\\")
                else "\\\\?\\" + value
            )
    os.makedirs(parent, exist_ok=True)
    with open(value, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
