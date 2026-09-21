"""lc1_2_patch_adapter.py
Translate LC1_2 validator ``patch_notes.patches`` into the legacy
``vlm_overrides`` shape consumed by
:func:`equation_builder._apply_vlm_overrides`.

LC1_2 patch shape (see
``LC1_2_SRD46_eq_map_node_validator/eqmap_validation_helpers/patch_validator.py``)::

    { "node_key":            "metal61_ligand5760_beta812_net96",
      "beta_definition_id":  812,
      "examined_vlm_id":     93881,
      "examined_value":      -9.25,
      "operation":           "set_value" | "drop_node",
      "chosen_value":        -8.57,      # only when operation='set_value'
      "rationale":           "..." }

Legacy ``vlm_overrides`` shape (see
``equation_builder._apply_vlm_overrides``)::

    { "beta_definition_id": 812,
      "action":             "set_value" | "drop_node",
      "vlm_id":             93881,       # = examined_vlm_id
      "chosen_value":       -8.57,       # passthrough for set_value
      "metal_id":           61,
      "ligand_id":          5760,
      "rationale":          "..." }

The two operations LC1_2 emits map 1:1 onto the corresponding equation-
builder actions; no other LC1_2 operations exist.  Any unknown
``operation`` is rejected loudly so a future schema drift is caught at
the boundary rather than silently dropped.
"""
from __future__ import annotations

from typing import Any, Iterable, List

_SUPPORTED_LC1_2_OPS = {"set_value", "drop_node"}


def lc1_2_patches_to_vlm_overrides(
    patches: Iterable[dict[str, Any]] | None,
    *,
    metal_id: int,
    ligand_id: int,
) -> List[dict[str, Any]]:
    """Convert LC1_2 ``patch_notes.patches`` into ``vlm_overrides``.

    Parameters
    ----------
    patches
        The list under
        ``lc1_2_eqmap_card.json[equilibrium_networks[i]].patch_notes.patches``,
        or ``None`` / empty for a pair that needed no curation.
    metal_id, ligand_id
        Stamped onto each override so the equation builder can perform
        cross-network DB lookups when ``set_value`` targets a vlm row
        that lives outside the originally selected networks for this
        pair.

    Returns
    -------
    list of override dicts ready to be attached to a pair entry under
    ``"vlm_overrides"`` in the maps JSON.
    """
    if not patches:
        return []

    overrides: list[dict[str, Any]] = []
    for p in patches:
        op = str(p.get("operation", "")).strip()
        if op not in _SUPPORTED_LC1_2_OPS:
            raise ValueError(
                f"unsupported LC1_2 patch operation {op!r} on node "
                f"{p.get('node_key')!r}; expected one of "
                f"{sorted(_SUPPORTED_LC1_2_OPS)}"
            )
        try:
            beta_id = int(p["beta_definition_id"])
            vlm_id = int(p["examined_vlm_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"malformed LC1_2 patch {p!r}: {exc}"
            ) from exc

        ov: dict[str, Any] = {
            "beta_definition_id": beta_id,
            "action": op,                 # "set_value" or "drop_node" map 1:1
            "vlm_id": vlm_id,             # examined row = the one being curated
            "metal_id": int(metal_id),
            "ligand_id": int(ligand_id),
            "rationale": p.get("rationale", ""),
            "_lc1_2_node_key": p.get("node_key"),
            "_lc1_2_examined_value": p.get("examined_value"),
        }
        if op == "set_value":
            if "chosen_value" not in p:
                raise ValueError(
                    f"LC1_2 'set_value' patch missing 'chosen_value': {p!r}"
                )
            ov["chosen_value"] = float(p["chosen_value"])

        overrides.append(ov)

    return overrides


__all__ = ["lc1_2_patches_to_vlm_overrides"]
