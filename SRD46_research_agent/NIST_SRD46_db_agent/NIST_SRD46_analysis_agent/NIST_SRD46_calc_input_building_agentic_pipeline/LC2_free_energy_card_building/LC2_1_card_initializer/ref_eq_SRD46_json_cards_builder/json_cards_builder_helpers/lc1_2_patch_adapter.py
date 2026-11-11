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
      "source_vlm_ids":      [93885],    # set_value: the rows behind the value
      "source_operation":    "row",      # host reading: "row" | "median" |
                                         # "mean" | "estimate"
      "derivation":          "...",      # the agent's own account of the value
      "source":              "estimated: ...",  # host label, estimate only
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

A ``set_value`` patch the host read as the value of its source rows
(``source_operation`` ``row``, ``median`` or ``mean``) maps instead to
``pick_vlm`` (one row, kept with its own value, T and I) or to
``median_K`` / ``mean_K`` over those rows.  An ``estimate`` keeps the
legacy ``set_value`` (examined row, agent's ``chosen_value``) and
carries the host's ``source`` label and the agent's trace
(``derivation``, cited ``source_vlm_ids``) onto the card.
"""
from __future__ import annotations

import json
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
            "action": op,                 # set_value with source rows: remapped below
            "vlm_id": vlm_id,             # examined row = the one being curated
            "metal_id": int(metal_id),
            "ligand_id": int(ligand_id),
            "rationale": p.get("rationale", ""),
            "_lc1_2_node_key": p.get("node_key"),
            "_lc1_2_examined_value": p.get("examined_value"),
        }
        if (op == "set_value" and p.get("source_vlm_ids")
                and p.get("source_operation") != "estimate"):
            ids = [int(v) for v in p["source_vlm_ids"]]
            how = str(p.get("source_operation") or "row")
            actions = {"row": "pick_vlm", "median": "median_K", "mean": "mean_K"}
            if how not in actions or (how == "row") != (len(ids) == 1):
                raise ValueError(
                    f"LC1_2 'set_value' patch has source_operation={how!r} "
                    f"for {len(ids)} source row(s): {p!r}"
                )
            ov["action"] = actions[how]
            if how == "row":
                ov["vlm_id"] = ids[0]
            else:
                ov["include_vlm_ids"] = ids
        elif op == "set_value":
            if "chosen_value" not in p:
                raise ValueError(
                    f"LC1_2 'set_value' patch missing 'chosen_value': {p!r}"
                )
            ov["chosen_value"] = float(p["chosen_value"])
            if p.get("source"):
                # An LC1_2 estimate keeps the host's ``estimated: ...`` label
                # and the agent's trace.
                ov["source"] = str(p["source"])
                for key in ("derivation", "source_vlm_ids"):
                    if p.get(key):
                        ov[key] = p[key]

        overrides.append(ov)

    return overrides


def decorate_report_with_patch_estimates(report: Any, card_json: dict[str, Any]) -> Any:
    """Label the species built from an LC1_2 estimate.

    An estimate reaches the card as a ``set_value`` equilibrium whose
    ``reference.source`` is the host's ``estimated: ...`` label.  Every
    species whose cumulative chain uses it adds that label to its source
    cell (after an LC1_3 ``estimated: ...`` label, before the legacy LC1_3
    label) and the estimate (patched id, value, rationale, trace) as a
    notes marker; ``|`` is written as its JSON escape so the Markdown
    table cell stays whole.
    """
    records: dict[str, dict[str, Any]] = {}
    equations = card_json.get("equations") or {}
    for blocks in (equations.values() if isinstance(equations, dict) else equations):
        for block in (blocks if isinstance(blocks, list) else [blocks]):
            entries = block.get("equilibria") if isinstance(block, dict) else None
            for entry in entries or []:
                reference = entry.get("reference") or {}
                notes = entry.get("patch_notes") or {}
                label = str(reference.get("source") or "")
                if notes.get("operation") != "set_value" or not label.startswith("estimated"):
                    continue
                source_id = str(reference.get("source_database_ID") or "")
                records[source_id] = {
                    "source": label,
                    "source_database_ID": source_id,
                    "patched_log_K": notes.get("patched_log_K"),
                    "rationale": notes.get("rationale"),
                }
                for key in ("derivation", "source_vlm_ids"):
                    if notes.get(key):
                        records[source_id][key] = notes[key]
    for species in getattr(report, "species", None) or []:
        chain = {
            value.strip()
            for value in str(getattr(species, "vlm_id", "") or "").split(",")
            if value.strip()
        }
        used = [records[value] for value in sorted(chain & set(records))]
        if not used:
            continue
        marker = json.dumps(
            {"lc1_2_estimates": used},
            ensure_ascii=True, sort_keys=True, separators=(",", ":"),
        ).replace("|", "\\u007c")
        prior = str(getattr(species, "additional_notes", "") or "").strip()
        species.additional_notes = f"{prior}; {marker}".strip("; ")
        prior_source = str(getattr(species, "source", "") or "")
        labels = [prior_source] if prior_source.startswith("estimated") else []
        labels += [record["source"] for record in used]
        if prior_source == "SRD46 query estimated values":
            # The legacy LC1_3 label stays, after the "estimated: ..." ones
            # so the cell still starts with "estimated".
            labels.append(prior_source)
        species.source = "; ".join(dict.fromkeys(labels))
    return report


__all__ = ["decorate_report_with_patch_estimates", "lc1_2_patches_to_vlm_overrides"]
