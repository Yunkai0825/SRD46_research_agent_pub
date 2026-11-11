"""Read-only SRD-46 source selection.

A changed value binds to SRD-46 rows: one selected row, or the value
recomputed from the rows a patch names. A number the LC1_2 agent worked
out itself binds through the host's source label and the trace the
patch carries (cited rows, derivation, rationale).
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics
from copy import deepcopy


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), default=str).encode()).hexdigest()


def pair_ids(pair):
    return tuple(int(str(pair[k]).rsplit("_", 1)[-1]) for k in ("metal_id", "ligand_id"))


def pair_key(pair):
    mid, lid = pair_ids(pair)
    return f"metal_{mid}_ligand_{lid}"


def candidate_rows(metal_id, ligand_id):
    """All reactions in all source networks for this fixed catalog pair."""
    from NIST_SRD46_core_db_search_tools._db_connection import get_equilibrium_db
    with get_equilibrium_db() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM eq_node WHERE metal_id=? AND ligand_id=? "
            "ORDER BY network_db_id, node_db_id", (int(metal_id), int(ligand_id)))]
        for row in rows:
            row["species"] = [dict(r) for r in conn.execute(
                "SELECT species, side FROM eq_node_species WHERE node_db_id=? "
                "ORDER BY side, species", (row["node_db_id"],))]
    return rows


def selected_rows(pair, candidates=None):
    rows = candidate_rows(*pair_ids(pair)) if candidates is None else candidates
    selection = pair.get("source_selection")
    if selection:
        ids = set(map(int, selection["vlm_ids"]))
        return [r for r in rows if int(r["vlm_id"]) in ids]
    nid = int(str(pair["eq_network"]).rsplit("_", 1)[-1])
    return [r for r in rows if int(r["network_db_id"]) == nid]


def make_selection(pair, vlm_ids, *, condition_justification, coverage_justification,
                   request_T_C, request_I_M, candidates=None):
    """Bind IDs to complete immutable database rows, never to proposed constants."""
    ids = list(map(int, vlm_ids))
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("Provide a nonempty, unique list of source VLM IDs")
    if not str(condition_justification).strip() or not str(coverage_justification).strip():
        raise ValueError("Condition and coverage justifications are both required")
    available = candidate_rows(*pair_ids(pair)) if candidates is None else candidates
    rows = [r for r in available if int(r["vlm_id"]) in set(ids)]
    if len(rows) != len(ids) or set(int(r["vlm_id"]) for r in rows) != set(ids):
        raise ValueError("Every selected VLM must identify one actual row of this catalog pair")
    for row in rows:
        equation = str(row.get("equation_python") or "").strip()
        if not equation or equation == "*" or not row.get("species"):
            raise ValueError(f"VLM {row['vlm_id']} is not parser-ready")
        if not math.isfinite(float(row["constant_value"])):
            raise ValueError("A source constant must be finite")
    rows.sort(key=lambda r: int(r["vlm_id"]))
    return {
        "schema": "srd46-source-selection/v1", "pair_key": pair_key(pair),
        "vlm_ids": sorted(ids), "source_rows": deepcopy(rows), "sha256": digest(rows),
        "request_T_C": float(request_T_C), "request_I_M": float(request_I_M),
        "condition_justification": str(condition_justification).strip(),
        "coverage_justification": str(coverage_justification).strip(),
        "source_conditions": [{"vlm_id": r["vlm_id"], "temperature": r.get("temperature"),
                               "ionic_strength": r.get("ionic_strength")} for r in rows],
    }


def verify_selection(pair):
    """Refuse modified source metadata, mismatched identities, or stale sources."""
    selection = pair.get("source_selection")
    if not selection:
        return None
    rebuilt = make_selection(pair, selection["vlm_ids"],
        condition_justification=selection.get("condition_justification", ""),
        coverage_justification=selection.get("coverage_justification", ""),
        request_T_C=selection["request_T_C"], request_I_M=selection["request_I_M"])
    for key in ("pair_key", "source_rows", "sha256", "source_conditions"):
        if selection.get(key) != rebuilt[key]:
            raise ValueError(f"Source selection {key} differs from the authoritative SRD-46 rows")
    return rebuilt


def apply_selection(pair, selection):
    out = deepcopy(pair)
    out["source_selection"] = deepcopy(selection)
    # An exact source selection replaces the old node-value patch, including
    # its stale temperature/source binding. All retained rows are explicit.
    previous = out.pop("patch_notes", None)
    if previous:
        out["source_selection"]["superseded_patch_notes"] = previous
    return out


def maps_binding(pair):
    selection = verify_selection(pair)
    if not selection:
        return {"selected_network_ids": [int(str(pair["eq_network"]).rsplit("_", 1)[-1])]}
    return {"selected_network_ids": sorted({int(r["network_db_id"]) for r in selection["source_rows"]}),
            "selected_vlm_ids": selection["vlm_ids"], "source_selection": selection}


def provenance_issues(pair):
    """Source metadata mismatches and value patches that do not bind.

    A legacy patch must equal its examined row, a patch naming
    source_vlm_ids must equal the value recomputed from those rows, and an
    estimate needs the host label and a trace of where it comes from.
    """
    issues = []
    try:
        verify_selection(pair)
    except Exception as exc:
        issues.append({"error_code": "source_metadata_mismatch", "message": str(exc)})
        return issues
    rows = {int(r["vlm_id"]): r for r in selected_rows(pair)}
    pair_rows = None
    for patch in (pair.get("patch_notes") or {}).get("patches", []):
        op = patch.get("operation") or patch.get("action") or patch.get("op")
        if op not in ("set_value", "median_K", "mean_K"):
            continue
        vlm = patch.get("examined_vlm_id", patch.get("vlm_id"))
        reason = "chosen_value differs from the value of the named rows"
        estimate = patch.get("source_operation") == ESTIMATE_OPERATION
        try:
            if estimate:
                # An agent's estimate binds through the host's source label
                # and its reason, never through a source row.
                reason = estimate_problem(patch)
                bound = not reason
            elif patch.get("source_vlm_ids"):
                # A patch that names its source rows binds to them in any
                # network of this pair; its value is recomputed from them.
                if pair_rows is None:
                    pair_rows = {int(r["vlm_id"]): r for r in candidate_rows(*pair_ids(pair))}
                bound = math.isclose(float(patch.get("chosen_value")),
                                     named_patch_value(patch, pair_rows), abs_tol=1e-9)
            else:
                row = rows[int(str(vlm).removeprefix("vlm_"))]
                bound = float(patch.get("chosen_value")) == float(row["constant_value"])
        except (KeyError, TypeError, ValueError) as exc:
            bound, reason = False, str(exc)
        if not bound:
            message = "Changed value must be selected as an actual source row with its own conditions"
            if estimate:
                message = ("An estimated value must carry the host's source label, a finite "
                           f"chosen_value and a trace of where it comes from; it does not bind: {reason}")
            elif patch.get("source_vlm_ids"):
                message += f"; named source rows {patch['source_vlm_ids']} do not bind: {reason}"
            issues.append({"error_code": "unbound_constant_patch", "patch": patch, "message": message})
    return issues


# A set_value whose number is not the value, median or mean of the rows it
# names is the LC1_2 agent's own. Its source label is written by the host,
# never by the agent: it names the agent that worked the value out and,
# when known, the file that records the patch and its trace.
ESTIMATE_OPERATION = "estimate"
ESTIMATE_SOURCE = "estimated: LC1_2 eq-map validator"


def estimate_source_label(record_path=""):
    """The host's source label of an LC1_2 estimate."""
    path = str(record_path or "").strip()
    return f"{ESTIMATE_SOURCE} ({path})" if path else ESTIMATE_SOURCE


def estimate_problem(patch):
    """Why an estimated set_value cannot bind ('' when it can)."""
    if not str(patch.get("source") or "").startswith(ESTIMATE_SOURCE):
        return f"it lacks the host source label {ESTIMATE_SOURCE!r}"
    try:
        value = float(patch.get("chosen_value"))
    except (TypeError, ValueError):
        value = math.nan
    if not math.isfinite(value):
        return "it has no finite chosen_value"
    if not (patch.get("source_vlm_ids") or str(patch.get("derivation") or "").strip()
            or str(patch.get("rationale") or "").strip()):
        return "it carries no trace of where the value comes from"
    return ""


def source_row_problem(row, beta_definition_id):
    """Why a row cannot be a source of a set_value patch ('' when it can)."""
    if row is None:
        return "is not an eq_node row of this pair"
    if int(row["beta_definition_id"]) != int(beta_definition_id):
        return f"measures beta_definition_id={row['beta_definition_id']}, not {beta_definition_id}"
    if str(row.get("constant_type") or "").strip().upper() != "K":
        return f"is a constant_type={row.get('constant_type')!r} row, not K"
    equation = str(row.get("equation_python") or "").strip()
    if not equation or equation == "*" or not row.get("species"):
        return "has no parser-ready equation"
    try:
        finite = math.isfinite(float(row["constant_value"]))
    except (TypeError, ValueError):
        finite = False
    return "" if finite else "has no finite constant_value"


def derived_constant(values, operation):
    """The value a patch takes from its source rows: one row, or their median or mean."""
    values = [float(v) for v in values]
    if operation == "row" and len(values) == 1:
        return values[0]
    if operation == "median" and len(values) >= 2:
        return float(statistics.median(values))
    if operation == "mean" and len(values) >= 2:
        return sum(values) / len(values)
    raise ValueError(f"source_operation {operation!r} does not apply to {len(values)} source row(s)")


def named_patch_value(patch, rows_by_id):
    """Recompute a set_value patch from the rows it names (same beta definition, any network)."""
    beta = int(patch["beta_definition_id"])
    values = []
    for vlm in patch["source_vlm_ids"]:
        row = rows_by_id.get(int(vlm))
        problem = source_row_problem(row, beta)
        if problem:
            raise ValueError(f"VLM {vlm} {problem}")
        values.append(row["constant_value"])
    return derived_constant(values, patch.get("source_operation") or "row")
