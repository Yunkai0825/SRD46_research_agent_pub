"""patch_validator.py — structural + semantic validation of LC1_2 patches.

The LC1_2 subagent emits a list of patches per (metal, ligand) pair.
A patch is a **pure data instruction** with no LLM math left to do at
parse time: if the operation rewrites a value, the new value is
already baked in as ``chosen_value``.

Patch shape (closed enum, one entry per node):

.. code-block:: jsonc

   { "node_key":           "metal62_ligand9058_beta812_net22168",
     "beta_definition_id": 812,
     "examined_vlm_id":    157620,    // the row currently in the draft
     "examined_value":     -4.80,     // its current constant_value
     "operation":          "set_value" | "drop_node",
     "chosen_value":       4.55,      // required iff operation == "set_value"
     "rationale":          "..." }

Semantics (downstream pipeline reads these and hardcodes the edits):

* ``set_value``:
    - Replace ``examined_value`` with ``chosen_value`` for the row
      identified by ``examined_vlm_id`` at this ``beta_definition_id``.
    - ``chosen_value`` is the FINAL number to hardcode. The LLM has
      already chosen one logK from neighbours (or computed a median /
      flipped the sign) — downstream does NOT re-aggregate.
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
     ``chosen_value``; ``drop_node`` forbids one. Rationale is always
     required and must reference at least one numeric fact (digit).

When validation fails, the orchestrator feeds the structured error
list back to the subagent for one or more retries. The error
messages are written in the imperative ("Patch[2]: ...") so the
agent can map each error back to the patch it must fix.

Public API
----------

:func:`validate_patches(patches, *, pair_key, metal_id, ligand_id, screen)`
    Return a :class:`PatchValidationResult` carrying ``ok`` /
    ``errors`` / ``patches_norm``. Pure function, idempotent.

:func:`format_errors_for_agent(result)`
    Render the errors as a markdown block ready for the retry
    user-message.
"""
from __future__ import annotations

import math
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

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ok":           self.ok,
            "n_patches":    len(self.patches_norm),
            "n_set_value":  self.n_set_value,
            "n_drop_node":  self.n_drop_node,
            "errors":       list(self.errors),
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
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


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
) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """Validate one patch dict. Returns ``(normalized_or_None, errors)``."""
    tag = f"patches[{idx}]"
    errs: List[str] = []

    if not isinstance(patch, dict):
        return None, [f"{tag}: must be a JSON object (got {type(patch).__name__})."]

    # ── 1. Required keys ──────────────────────────────────────────
    missing = [k for k in _REQUIRED_KEYS if k not in patch]
    if missing:
        errs.append(f"{tag}: missing required key(s) {missing}.")
        # Cannot continue without basic shape.
        return None, errs

    # ── 2. Closed-enum operation ──────────────────────────────────
    op = str(patch.get("operation") or "").strip()
    if op not in VALID_OPERATIONS:
        errs.append(
            f"{tag}: operation={op!r} not in {list(VALID_OPERATIONS)}."
        )
        return None, errs

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
    if op == "set_value":
        if "chosen_value" not in patch:
            errs.append(
                f"{tag}: operation='set_value' requires 'chosen_value'."
            )
        elif not _is_finite_number(patch.get("chosen_value")):
            errs.append(
                f"{tag}: 'chosen_value' must be a finite number "
                f"(got {patch.get('chosen_value')!r})."
            )
        else:
            chosen_val = float(patch["chosen_value"])
            if abs(chosen_val) > _CHOSEN_VALUE_MAX_ABS:
                errs.append(
                    f"{tag}: |chosen_value|={abs(chosen_val):.3f} exceeds "
                    f"sanity bound {_CHOSEN_VALUE_MAX_ABS}; check "
                    f"units / decimal place."
                )
            elif (examined_val is not None
                    and abs(chosen_val - examined_val) < _VALUE_TOL):
                errs.append(
                    f"{tag}: chosen_value={chosen_val:+.6f} equals "
                    f"examined_value; patch is a no-op. Either omit it "
                    f"or set the actual corrected number."
                )
    elif op == "drop_node":
        if "chosen_value" in patch:
            errs.append(
                f"{tag}: operation='drop_node' forbids 'chosen_value' "
                f"(got {patch.get('chosen_value')!r}); drop_node removes "
                f"the whole node from the network."
            )

    if errs:
        return None, errs

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
    norm["rationale"] = rationale
    return norm, []


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
    n_set = n_drop = 0

    for i, p in enumerate(plist):
        norm, errs = _validate_one_patch(
            i, p,
            metal_id=metal_id,
            ligand_id=ligand_id,
            screen_index=screen_index,
        )
        if errs:
            all_errors.extend(errs)
            continue
        assert norm is not None  # invariant: norm is set when no errors
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
