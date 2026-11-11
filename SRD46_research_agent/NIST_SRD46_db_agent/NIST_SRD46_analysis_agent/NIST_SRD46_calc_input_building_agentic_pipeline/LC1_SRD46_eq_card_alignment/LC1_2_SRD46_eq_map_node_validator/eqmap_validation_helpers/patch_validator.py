"""patch_validator.py — structural + semantic validation of LC1_2 patches.

The LC1_2 subagent emits a list of patches per (metal, ligand) pair.
A patch is a **pure data instruction** with no LLM math left to do at
parse time: if the operation rewrites a value, the new value is
already baked in as ``chosen_value``, with a trace of where it comes
from: the SRD-46 rows it rests on (``source_vlm_ids``) and, in free
text, how the agent got from them to the number (``derivation``).
The host reads that trace; the agent names no mode.

Patch shape (closed enum, one entry per node):

.. code-block:: jsonc

   { "node_key":           "metal62_ligand9058_beta812_net22168",
     "beta_definition_id": 812,
     "examined_vlm_id":    157620,    // the row currently in the draft
     "examined_value":     -4.80,     // its current constant_value
     "operation":          "set_value" | "drop_node",
     "chosen_value":       4.56,      // required iff operation == "set_value"
     "source_vlm_ids":     [157619, 157621, 157622],  // set_value: rows behind it
     "derivation":         "median of the three rows",  // set_value: how
     "rationale":          "..." }

Semantics (downstream pipeline reads these and hardcodes the edits):

* ``set_value``:
    - Replace ``examined_value`` with ``chosen_value`` for the row
      identified by ``examined_vlm_id`` at this ``beta_definition_id``.
    - The host looks up every named row and writes how it read the
      trace into ``source_operation``: ``row`` when ``chosen_value``
      is the value of one named row (the card takes that row with its
      own T and I), ``median`` / ``mean`` when it is that aggregate of
      the named K rows of this beta definition, else ``estimate``: the
      number is kept as written and the host adds ``source`` (an
      ``estimated: ...`` label the agent never sees or fills).
    - ``source_conditions`` keeps what the host found for every named
      row (value, T, I, network, beta definition, constant type).
* ``drop_node``:
    - Remove the whole ``beta_definition_id`` from the network.

This module does NOT touch the database. It only validates the JSON
payload against:

  1. **Structural rules** — required keys, types, closed-enum operation.
  2. **Pair binding** — every patch must reference the pair's
     ``metal_id`` / ``ligand_id`` (carried in the patch context).
  3. **Screen-cross-ref rules** — ``node_key`` must exist in the
     screen, ``examined_vlm_id`` must match the screen's chosen
     ``vlm_id`` for that node, ``examined_value`` must match the
     screen's chosen ``constant_value`` (±1e-6).
  4. **Operation-specific rules** — ``set_value`` requires a finite
     ``chosen_value`` within the sanity bound; ``drop_node`` forbids
     one. The trace is recorded, never a ground for rejection. A
     ``set_value`` that changes nothing is skipped with a note.
     Rationale is always required and must reference at least one
     numeric fact (digit).

When validation fails, the orchestrator feeds the structured error
list back to the subagent for one or more retries. The error
messages are written in the imperative ("Patch[2]: ...") so the
agent can map each error back to the patch it must fix.

Public API
----------

:func:`validate_patches(patches, *, pair_key, metal_id, ligand_id, screen, source_rows=None, estimate_source=None)`
    Return a :class:`PatchValidationResult` carrying ``ok`` /
    ``errors`` / ``patches_norm`` / ``notes`` (how the host read each
    ``set_value``). Pure function, idempotent.

:func:`format_errors_for_agent(result)`
    Render the errors as a markdown block ready for the retry
    user-message.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ════════════════════════════════════════════════════════════════════
#  Closed enum
# ════════════════════════════════════════════════════════════════════

VALID_OPERATIONS: Tuple[str, ...] = ("set_value", "drop_node")

# Required keys for EVERY patch, regardless of operation.
_REQUIRED_KEYS: Tuple[str, ...] = (
    "node_key",
    "beta_definition_id",
    "examined_vlm_id",
    "examined_value",
    "operation",
    "rationale",
)

# Numeric tolerance for matching examined_value to screen-chosen value.
_VALUE_TOL = 1e-6

# Allowed bound on |chosen_value| to catch obvious unit / decimal errors.
# logK values in SRD-46 are essentially always in [-30, +30]; anything
# outside that almost certainly indicates a typo or wrong-unit ingestion.
_CHOSEN_VALUE_MAX_ABS = 50.0

# A chosen_value counts as the value of its named rows (one row, or their
# median or mean) when it agrees with it to SRD-46's reporting precision.
_SOURCE_VALUE_TOL = 0.01

# What the host keeps of every source row a set_value names.
_TRACE_KEYS: Tuple[str, ...] = (
    "vlm_id", "constant_value", "temperature", "ionic_strength",
    "network_db_id", "beta_definition_id", "constant_type",
)


# ════════════════════════════════════════════════════════════════════
#  Result container
# ════════════════════════════════════════════════════════════════════

@dataclass
class PatchValidationResult:
    """Outcome of validating one pair's patch list."""
    ok:           bool
    errors:       List[str] = field(default_factory=list)
    patches_norm: List[Dict[str, Any]] = field(default_factory=list)
    n_set_value:  int = 0
    n_drop_node:  int = 0
    notes:        List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ok":           self.ok,
            "n_patches":    len(self.patches_norm),
            "n_set_value":  self.n_set_value,
            "n_drop_node":  self.n_drop_node,
            "errors":       list(self.errors),
            "notes":        list(self.notes),
        }


# ════════════════════════════════════════════════════════════════════
#  Helpers
# ════════════════════════════════════════════════════════════════════

def _is_finite_number(x: Any) -> bool:
    if isinstance(x, bool):                # bool is a subclass of int
        return False
    if not isinstance(x, (int, float)):
        return False
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def _coerce_int(x: Any) -> Optional[int]:
    if x is None or isinstance(x, bool):
        return None
    if isinstance(x, float) and not x.is_integer():
        return None                        # reject, never truncate
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def _coerce_vlm_id(x: Any) -> Optional[int]:
    """A vlm_id given as an int or as the ``vlm_<id>`` label the host prints."""
    if isinstance(x, str):
        x = x.strip().removeprefix("vlm_")
    return _coerce_int(x)


def _build_screen_index(screen: Any) -> Dict[str, Any]:
    """Map ``node_key -> EqMapNode`` from an :class:`EqMapScreen`.

    Pure-Python: doesn't import EqMapScreen so this module stays
    cycle-safe and unit-testable with stub objects.
    """
    out: Dict[str, Any] = {}
    nodes = getattr(screen, "nodes", None) or []
    for ns in nodes:
        n = getattr(ns, "node", None)
        if n is None:
            continue
        key = getattr(n, "node_key", None)
        if key:
            out[str(key)] = n
    return out


def _contains_digit(s: Any) -> bool:
    return any(ch.isdigit() for ch in str(s or ""))


def _row_label(row: Dict[str, Any]) -> str:
    return (f"vlm_{row.get('vlm_id')}={row.get('constant_value')} "
            f"({row.get('temperature')} C, {row.get('ionic_strength')} M, "
            f"network {row.get('network_db_id')})")


def _read_trace(
    value: Optional[float],
    raw_ids: List[Any],
    source_rows: Dict[int, Dict[str, Any]],
    beta_id: int,
    wording: str,
) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """How the host reads the trace of a ``set_value``.

    Returns ``(reading, used, conditions)``. ``reading`` is ``row``,
    ``median`` or ``mean`` when ``value`` is the value of one named row
    or that aggregate of the named K rows of this beta definition
    (``used``), else ``estimate``. ``conditions`` holds what the host
    found for every named id. Nothing here rejects a patch.
    """
    from ...source_repair.records import (
        ESTIMATE_OPERATION, derived_constant, source_row_problem)
    conditions: List[Dict[str, Any]] = []
    usable: List[Dict[str, Any]] = []
    seen: set = set()
    for raw in raw_ids:
        vid = _coerce_vlm_id(raw)
        if vid is None:
            conditions.append({"cited": str(raw), "note": "not a vlm_id"})
            continue
        if vid in seen:
            continue
        seen.add(vid)
        row = source_rows.get(vid)
        if row is None:
            conditions.append(
                {"vlm_id": vid, "note": "not an eq_node row of this pair"})
            continue
        entry = {key: row.get(key) for key in _TRACE_KEYS}
        problem = source_row_problem(row, beta_id)
        if problem:
            entry["note"] = problem
        else:
            usable.append(row)
        conditions.append(entry)

    if value is None:
        # No number typed: one named row can only mean that row's value.
        if len(usable) == 1 and len(conditions) == 1:
            return "row", usable, conditions
        return ESTIMATE_OPERATION, [], conditions
    values = [float(r["constant_value"]) for r in usable]
    if len(usable) >= 2:
        fits = [how for how in ("median", "mean")
                if abs(value - derived_constant(values, how)) <= _SOURCE_VALUE_TOL]
        if fits:
            says_mean = (re.search(r"\b(mean|average)\b", wording, re.IGNORECASE)
                         and not re.search(r"\bmedian\b", wording, re.IGNORECASE))
            how = "mean" if fits == ["mean"] or (says_mean and "mean" in fits) else "median"
            return how, usable, conditions
    near = [r for r in usable
            if abs(value - float(r["constant_value"])) <= _SOURCE_VALUE_TOL]
    if len(near) == 1:
        return "row", near, conditions
    return ESTIMATE_OPERATION, [], conditions


# ════════════════════════════════════════════════════════════════════
#  Per-patch validation
# ════════════════════════════════════════════════════════════════════

def _validate_one_patch(
    idx: int,
    patch: Any,
    *,
    metal_id: int,
    ligand_id: int,
    screen_index: Dict[str, Any],
    source_rows: Optional[Dict[int, Dict[str, Any]]] = None,
    estimate_source: Optional[str] = None,
) -> Tuple[Optional[Dict[str, Any]], List[str], str]:
    """Validate one patch dict.

    Returns ``(normalized_or_None, errors, note)``. ``note`` says how the
    host read a ``set_value``; a patch with no errors and no normalized
    record changes nothing and is skipped.
    """
    tag = f"patches[{idx}]"
    errs: List[str] = []

    if not isinstance(patch, dict):
        return None, [f"{tag}: must be a JSON object (got {type(patch).__name__})."], ""

    # ── 1. Required keys ──────────────────────────────────────────
    missing = [k for k in _REQUIRED_KEYS if k not in patch]
    if missing:
        errs.append(f"{tag}: missing required key(s) {missing}.")
        # Cannot continue without basic shape.
        return None, errs, ""

    # ── 2. Closed-enum operation ──────────────────────────────────
    op = str(patch.get("operation") or "").strip()
    if op not in VALID_OPERATIONS:
        errs.append(
            f"{tag}: operation={op!r} not in {list(VALID_OPERATIONS)}."
        )
        return None, errs, ""

    # ── 3. ID coercion ────────────────────────────────────────────
    beta_id = _coerce_int(patch.get("beta_definition_id"))
    if beta_id is None:
        errs.append(
            f"{tag}: 'beta_definition_id' must be an int "
            f"(got {patch.get('beta_definition_id')!r})."
        )
    examined_vid = _coerce_int(patch.get("examined_vlm_id"))
    if examined_vid is None:
        errs.append(
            f"{tag}: 'examined_vlm_id' must be an int "
            f"(got {patch.get('examined_vlm_id')!r})."
        )

    # ── 4. examined_value structural check ────────────────────────
    examined_val_raw = patch.get("examined_value")
    if not _is_finite_number(examined_val_raw):
        errs.append(
            f"{tag}: 'examined_value' must be a finite number "
            f"(got {examined_val_raw!r})."
        )
    examined_val = float(examined_val_raw) if _is_finite_number(examined_val_raw) else None

    # ── 5. Rationale ──────────────────────────────────────────────
    rationale = str(patch.get("rationale") or "").strip()
    if not rationale:
        errs.append(f"{tag}: 'rationale' is required and must be non-empty.")
    elif not _contains_digit(rationale):
        errs.append(
            f"{tag}: 'rationale' must reference at least one numeric "
            f"fact (vlm_id, logK, T, sibling count); got "
            f"{rationale!r}."
        )

    # ── 6. Screen cross-reference ─────────────────────────────────
    node_key = str(patch.get("node_key") or "").strip()
    if not node_key:
        errs.append(f"{tag}: 'node_key' is required and must be non-empty.")
    node_obj = screen_index.get(node_key) if node_key else None
    if node_key and node_obj is None:
        errs.append(
            f"{tag}: node_key={node_key!r} is not in this pair's screen. "
            f"Valid node_keys: {sorted(screen_index.keys())}."
        )

    # ── 7. Pair binding via the node object ───────────────────────
    if node_obj is not None:
        node_metal  = _coerce_int(getattr(node_obj, "metal_id",  None))
        node_ligand = _coerce_int(getattr(node_obj, "ligand_id", None))
        node_beta   = _coerce_int(getattr(node_obj, "beta_definition_id", None))
        node_vid    = _coerce_int(getattr(node_obj, "vlm_id",    None))
        node_val    = getattr(node_obj, "constant_value", None)

        if node_metal != int(metal_id):
            errs.append(
                f"{tag}: node_key references metal_id={node_metal}, "
                f"but this pair is metal_id={int(metal_id)}."
            )
        if node_ligand != int(ligand_id):
            errs.append(
                f"{tag}: node_key references ligand_id={node_ligand}, "
                f"but this pair is ligand_id={int(ligand_id)}."
            )
        if beta_id is not None and node_beta is not None and beta_id != node_beta:
            errs.append(
                f"{tag}: beta_definition_id={beta_id} does not match "
                f"the screen's beta_definition_id={node_beta} for "
                f"node_key={node_key!r}."
            )
        if (examined_vid is not None and node_vid is not None
                and examined_vid != node_vid):
            errs.append(
                f"{tag}: examined_vlm_id={examined_vid} does not match "
                f"the screen's chosen vlm_id={node_vid} for "
                f"node_key={node_key!r}. Patch only the row that is "
                f"currently in the draft."
            )
        if (examined_val is not None and _is_finite_number(node_val)
                and abs(examined_val - float(node_val)) > _VALUE_TOL):
            errs.append(
                f"{tag}: examined_value={examined_val:+.6f} does not "
                f"match the screen's chosen value="
                f"{float(node_val):+.6f} for node_key={node_key!r}."
            )

    # ── 8. Operation-specific rules ───────────────────────────────
    chosen_val: Optional[float] = None
    reading = ""
    used: List[Dict[str, Any]] = []
    conditions: List[Dict[str, Any]] = []
    derivation = ""
    note = ""
    if op == "set_value" and beta_id is not None:
        from ...source_repair.records import (
            ESTIMATE_OPERATION, derived_constant, estimate_source_label)
        typed = patch.get("chosen_value")
        raw_ids = patch.get("source_vlm_ids")
        raw_list = [] if raw_ids is None else (
            raw_ids if isinstance(raw_ids, list) else [raw_ids])
        derivation = str(patch.get("derivation") or "").strip()
        hint = str(patch.get("source_operation") or "").strip().lower()
        if typed is not None and not _is_finite_number(typed):
            errs.append(
                f"{tag}: 'chosen_value' must be a finite number "
                f"(got {typed!r})."
            )
        elif typed is not None and abs(float(typed)) > _CHOSEN_VALUE_MAX_ABS:
            errs.append(
                f"{tag}: |chosen_value|={abs(float(typed)):.3f} exceeds "
                f"sanity bound {_CHOSEN_VALUE_MAX_ABS}; check "
                f"units / decimal place."
            )
        elif raw_list and source_rows is None:
            errs.append(
                f"{tag}: the host could not load this pair's SRD-46 rows, "
                f"so source_vlm_ids cannot be looked up. Re-call "
                f"`finalize_patches` with the same payload."
            )
        else:
            value = None if typed is None else float(typed)
            reading, used, conditions = _read_trace(
                value, raw_list, source_rows or {}, beta_id,
                f"{derivation} {hint}")
            if hint == ESTIMATE_OPERATION and value is not None:
                reading, used = ESTIMATE_OPERATION, []
            found = [_row_label(c) for c in conditions if "constant_value" in c]
            if reading == ESTIMATE_OPERATION and value is None:
                errs.append(
                    f"{tag}: operation='set_value' requires 'chosen_value', "
                    f"the number to write."
                    + (f" Rows you named: {found}." if found else "")
                )
            elif reading == ESTIMATE_OPERATION:
                chosen_val = value
                label = estimate_source or estimate_source_label()
                missing_rows = [str(c.get("vlm_id", c.get("cited")))
                                for c in conditions if "constant_value" not in c]
                note = (f"{tag}: kept as your number {value:+.4f}; the card "
                        f"labels it {label!r}."
                        + (f" Not found among this pair's eq_node rows: "
                           f"{missing_rows}." if missing_rows else ""))
            else:
                chosen_val = derived_constant(
                    [r["constant_value"] for r in used], reading)
                note = (f"{tag}: read as the {reading} of "
                        f"{[_row_label(r) for r in used]}: {chosen_val:+.4f}.")
            if chosen_val is not None and (
                    (reading == "row" and used[0].get("vlm_id") == examined_vid)
                    or (reading == ESTIMATE_OPERATION and examined_val is not None
                        and abs(chosen_val - examined_val) < _VALUE_TOL)):
                if not errs:
                    return None, [], (
                        f"{tag}: not applied; it changes nothing (the examined "
                        f"row's own value, no other row behind it).")
    elif op == "drop_node":
        if "chosen_value" in patch:
            errs.append(
                f"{tag}: operation='drop_node' forbids 'chosen_value' "
                f"(got {patch.get('chosen_value')!r}); drop_node removes "
                f"the whole node from the network."
            )

    if errs:
        return None, errs, ""

    # ── 9. Normalize to a canonical record ────────────────────────
    norm: Dict[str, Any] = {
        "node_key":           node_key,
        "beta_definition_id": int(beta_id),
        "examined_vlm_id":    int(examined_vid),
        "examined_value":     float(examined_val),
        "operation":          op,
    }
    if op == "set_value":
        norm["chosen_value"] = float(chosen_val)
        cited = [int(c["vlm_id"]) for c in (used or conditions) if "vlm_id" in c]
        if cited:
            norm["source_vlm_ids"] = cited
        # Written by the host: how it read the trace.
        norm["source_operation"] = reading
        if not used:
            norm["source"] = estimate_source or estimate_source_label()
        if derivation:
            norm["derivation"] = derivation
        if conditions:
            norm["source_conditions"] = conditions
    norm["rationale"] = rationale
    return norm, [], note


# ════════════════════════════════════════════════════════════════════
#  Public entry point
# ════════════════════════════════════════════════════════════════════

def validate_patches(
    patches: Any,
    *,
    pair_key: str,
    metal_id: int,
    ligand_id: int,
    screen: Any,
    source_rows: Optional[Dict[int, Dict[str, Any]]] = None,
    estimate_source: Optional[str] = None,
) -> PatchValidationResult:
    """Validate a patch list for ONE (metal, ligand) pair.

    Parameters
    ----------
    patches:
        Either ``{"patches": [...]}`` or a bare ``[...]``. Empty list
        is legal and is the expected result for a clean pair.
    pair_key, metal_id, ligand_id:
        The pair this batch belongs to. Each patch must bind to the
        same pair via its ``node_key`` (cross-checked against
        ``screen``).
    screen:
        The :class:`EqMapScreen` produced by
        :func:`screen_eq_map` for this pair. Used to look up the
        chosen vlm/value/beta_def per ``node_key``.
    source_rows:
        ``vlm_id -> eq_node row`` (with ``species``) for every network of
        this pair, as returned by ``source_repair.records.candidate_rows``.
        ``set_value`` patches are checked and computed against it.
    estimate_source:
        The host's label written as the ``source`` of every ``estimate``
        patch (``source_repair.records.estimate_source_label``); the
        agent never writes it. Defaults to the label without a path.
    """
    # Accept either envelope or bare list, including null.
    if isinstance(patches, dict):
        plist = patches.get("patches", [])
    else:
        plist = patches

    if plist is None:
        plist = []

    if not isinstance(plist, list):
        return PatchValidationResult(
            ok=False,
            errors=[
                f"payload['patches'] must be a JSON list "
                f"(got {type(plist).__name__})."
            ],
        )

    screen_index = _build_screen_index(screen)

    normalised: List[Dict[str, Any]] = []
    all_errors: List[str] = []
    notes: List[str] = []
    n_set = n_drop = 0

    for i, p in enumerate(plist):
        norm, errs, note = _validate_one_patch(
            i, p,
            metal_id=metal_id,
            ligand_id=ligand_id,
            screen_index=screen_index,
            source_rows=source_rows,
            estimate_source=estimate_source,
        )
        if errs:
            all_errors.extend(errs)
            continue
        if note:
            notes.append(note)
        if norm is None:              # changes nothing: skipped, not an error
            continue
        normalised.append(norm)
        if norm["operation"] == "set_value":
            n_set += 1
        elif norm["operation"] == "drop_node":
            n_drop += 1

    # ── Cross-patch invariant: no duplicate (node_key, operation) ─
    if not all_errors:
        seen: Dict[str, int] = {}
        for i, p in enumerate(normalised):
            nk = p["node_key"]
            if nk in seen:
                all_errors.append(
                    f"patches[{i}]: duplicate node_key={nk!r} "
                    f"(also at patches[{seen[nk]}]). One patch per node only."
                )
            else:
                seen[nk] = i

    return PatchValidationResult(
        ok=(len(all_errors) == 0),
        errors=all_errors,
        patches_norm=normalised if not all_errors else [],
        n_set_value=n_set if not all_errors else 0,
        n_drop_node=n_drop if not all_errors else 0,
        notes=notes if not all_errors else [],
    )


def format_errors_for_agent(result: PatchValidationResult) -> str:
    """Render validation errors as a markdown block for the retry message."""
    if result.ok:
        return ""
    header = (
        "## Validator rejected your patch list\n\n"
        "Fix EACH of the following and re-call `finalize_patches` "
        "with a corrected JSON payload. Operations must be one of "
        f"{list(VALID_OPERATIONS)}; `set_value` requires a finite "
        "`chosen_value`; `drop_node` forbids one.\n\n"
    )
    bullets = "\n".join(f"- {e}" for e in result.errors)
    return header + bullets + "\n"


__all__ = [
    "VALID_OPERATIONS",
    "PatchValidationResult",
    "validate_patches",
    "format_errors_for_agent",
]
