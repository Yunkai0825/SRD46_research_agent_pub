"""Deterministic, LLM-facing verdicts for predominance sweeps.

The topology JSON is the lossless machine artifact used by plotting and other
programs.  This module produces a second, normalized representation intended
for scientific inspection:

* ``*_verdict.md`` contains the complete compact report that can be placed in
  an agent context without feeding the raw topology JSON.
* ``*_verdict.json`` is a normalized sidecar.  It preserves the mapping from
  canonical report IDs to source topology IDs so a read tool can resolve one
  requested feature without exposing the whole raw topology document.

Reference-line cuts are read from the final classified label raster.  They
are never reverse-inferred from compact/RDP geometry.  For dimensions greater
than two, features are named by their actual intrinsic dimension; in
particular a 2-D surface in a 3-D domain is not described as a polyline edge.

In the Markdown view every coordinate value is rendered inside a full named
tuple in coordinate order — e.g. ``(pH=7, E_V=0.2V)`` — with the axis unit
attached to the number (no space); no bare, axis-unpaired coordinate value is
emitted.  The JSON sidecar stays lossless and machine-shaped.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
import json
import math
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np


JsonObject = Dict[str, Any]
_MISSING = object()


# ---------------------------------------------------------------------------
#  Card-sourced grouping (phase + label redox) for the verdict layout
# ---------------------------------------------------------------------------
# Regions, boundaries, and junctions are ordered into chemistry-first groups so
# their canonical IDs increment down each rendered table.  Redox is a label
# property taken from the card's formal oxidation states; it is never inferred
# from a boundary's geometry.
_PHASE_PAIR_RANK: Dict[frozenset, Tuple[int, str]] = {
    frozenset({"aqueous"}): (0, "liquid\u2013liquid"),
    frozenset({"aqueous", "solid"}): (1, "solid\u2013liquid"),
    frozenset({"solid"}): (2, "solid\u2013solid"),
}
_SOLID_COUNT_WORD = {
    0: "all liquid",
    1: "one solid",
    2: "two solids",
    3: "three solids",
}


def _norm_phase(phase: Any) -> Optional[str]:
    return phase if phase in ("solid", "aqueous") else None


def _region_group(phase: Optional[str]) -> Tuple[int, str]:
    if phase == "solid":
        return (0, "solid")
    if phase == "aqueous":
        return (1, "liquid")
    return (2, "phase unresolved")


def _boundary_group(
    phase_a: Optional[str],
    phase_b: Optional[str],
    ox_a: Optional[int],
    ox_b: Optional[int],
) -> Tuple[Tuple[int, int], str]:
    if phase_a is None or phase_b is None:
        return ((3, 0), "phase unresolved")
    pair_rank, pair_label = _PHASE_PAIR_RANK[frozenset({phase_a, phase_b})]
    if ox_a is None or ox_b is None:
        redox_rank, redox_label = 2, "redox unresolved"
    elif ox_a != ox_b:
        redox_rank, redox_label = 0, "redox (by species definition)"
    else:
        redox_rank, redox_label = 1, (
            "non-redox (by species definition, may vary with detailed "
            "converged topo)"
        )
    return ((pair_rank, redox_rank), f"{pair_label} \u00b7 {redox_label}")


def _junction_group(phases: Sequence[Optional[str]]) -> Tuple[int, str]:
    if not phases or any(phase is None for phase in phases):
        return (10_000, "phase unresolved")
    n_solid = sum(1 for phase in phases if phase == "solid")
    return (n_solid, _SOLID_COUNT_WORD.get(n_solid, f"{n_solid} solids"))


def build_predominance_verdict(
    topology: Any,
    *,
    axes: Optional[Sequence[Any]] = None,
    final_label_map: Any = None,
    built_metadata: Any = None,
    sweep_method: str = "predominance",
    display_axis_order: Optional[Sequence[str]] = None,
) -> JsonObject:
    """Build a normalized predominance report from an N-D topology.

    Parameters
    ----------
    topology
        A raw ``TopologyND`` or compact ``CompactTopologyND`` instance.
        Duck typing is intentional so the exporter remains usable when the
        core package was imported through different module roots.
    axes
        Ordered ``GridAxis`` objects, or axis-like mappings.  When omitted,
        names and ranges are taken from the topology settings.
    final_label_map
        The final classified field, normally ``(axis_values, labels,
        label_catalog)``.  A mapping with the same fields is also accepted.
        It is optional; without it the report simply contains no exact cuts.
    built_metadata
        Caller-supplied calculation metadata (mapping or built-system object).
        Missing metadata remains explicitly absent rather than being guessed.
    sweep_method
        Human-readable route name, such as ``"Pourbaix"``.
    display_axis_order
        Optional leading axis order for the report.  Any omitted axes retain
        their declared relative order.  The permutation is applied to the
        classified raster and every coordinate-bearing topology record; it
        never merely relabels coordinate columns.
    """

    if not hasattr(topology, "ndim"):
        raise TypeError("topology must provide an integer ndim attribute")
    ndim = int(topology.ndim)
    if ndim < 1:
        raise ValueError("predominance topology must have at least one dimension")

    metadata = _metadata_mapping(built_metadata)
    axis_records, raster, source_axis_names, axis_permutation = (
        _normalize_axes_and_raster(
            topology,
            ndim=ndim,
            axes=axes,
            final_label_map=final_label_map,
            display_axis_order=display_axis_order,
        )
    )
    metadata = _permute_axis_ordered_metadata(
        metadata,
        axis_permutation=axis_permutation,
        ndim=ndim,
    )
    axis_names = [record["name"] for record in axis_records]

    source_regions = sorted(
        list(getattr(topology, "regions", None) or []),
        key=lambda item: _natural_key(getattr(item, "id", "")),
    )
    features = _collect_features(topology, ndim, source_axis_names)
    if axis_permutation != list(range(ndim)):
        for feature in features:
            feature["geometry"] = _permute_coordinate_geometry(
                feature["geometry"],
                source_axis_names=source_axis_names,
                axis_permutation=axis_permutation,
            )
            feature["simplification"] = _permute_simplification_coordinates(
                feature["simplification"],
                source_axis_names=source_axis_names,
                axis_permutation=axis_permutation,
            )

    topology_catalog = dict(getattr(topology, "label_catalog", None) or {})
    raster_catalog = raster[2] if raster is not None else {}
    label_catalog = dict(topology_catalog)
    for key, value in raster_catalog.items():
        label_catalog.setdefault(_canonical_scalar(key), value)

    # A catalog is a name lookup, not evidence that a phase survives the
    # final classified field.  Coarse-only phases may legitimately disappear
    # after refinement or declared-domain cropping.  Build the report catalog
    # only from final raster cells and exported topology objects.
    source_label_ids = set()
    if raster is not None:
        source_label_ids.update(
            _canonical_scalar(value)
            for value in np.unique(raster[1])
            if _canonical_scalar(value) != -1
        )
    source_label_ids.update(
        _canonical_scalar(getattr(region, "label", None))
        for region in source_regions
    )
    for feature in features:
        source_label_ids.update(feature["labels"])
    source_label_ids.discard(None)
    ordered_label_ids = sorted(source_label_ids, key=_natural_key)

    label_id_map = {
        source_id: f"Dms_{index}"
        for index, source_id in enumerate(ordered_label_ids, start=1)
    }
    label_text_map = {
        source_id: _display_label(
            label_catalog.get(source_id, label_catalog.get(str(source_id))),
            fallback=label_id_map[source_id],
        )
        for source_id in ordered_label_ids
    }

    # Card-sourced phase and label-redox attributes drive both the grouped
    # ordering and the incremental canonical IDs.  Absent maps leave every
    # feature "unresolved", which collapses to the plain natural-order layout.
    raw_phase_map = metadata.get("species_phase_map")
    raw_phase_map = dict(raw_phase_map) if isinstance(raw_phase_map, Mapping) else {}
    raw_oxidation_map = metadata.get("species_oxidation_state_map")
    raw_oxidation_map = (
        dict(raw_oxidation_map) if isinstance(raw_oxidation_map, Mapping) else {}
    )
    grouping_active = bool(raw_phase_map)
    grouping_parser_failure = metadata.get("species_card_maps_error")
    grouping_parser_failure = (
        str(grouping_parser_failure) if grouping_parser_failure else None
    )

    def _label_phase(label_source_id: Any) -> Optional[str]:
        return _norm_phase(raw_phase_map.get(label_text_map.get(label_source_id)))

    def _label_oxidation(label_source_id: Any) -> Optional[int]:
        value = raw_oxidation_map.get(label_text_map.get(label_source_id))
        if isinstance(value, bool):
            return None
        return value if isinstance(value, int) else None

    def _region_group_of(region: Any) -> Tuple[int, str]:
        return _region_group(
            _label_phase(_canonical_scalar(getattr(region, "label", None)))
        )

    def _boundary_group_of(feature: Mapping[str, Any]) -> Tuple[Tuple[int, int], str]:
        labels = list(feature.get("labels") or [])
        if len(labels) == 2:
            return _boundary_group(
                _label_phase(labels[0]),
                _label_phase(labels[1]),
                _label_oxidation(labels[0]),
                _label_oxidation(labels[1]),
            )
        return ((3, 0), "phase unresolved")

    def _junction_group_of(feature: Mapping[str, Any]) -> Tuple[int, str]:
        return _junction_group(
            [_label_phase(label) for label in (feature.get("labels") or [])]
        )

    source_regions = sorted(
        source_regions,
        key=lambda region: (
            _region_group_of(region)[0],
            _natural_key(getattr(region, "id", "")),
        ),
    )
    region_id_map = {
        _canonical_scalar(getattr(region, "id", index)): f"DmsReg_{index}"
        for index, region in enumerate(source_regions, start=1)
    }

    codim_one = [feature for feature in features if feature["dim"] == ndim - 1]
    codim_one.sort(
        key=lambda feature: (_boundary_group_of(feature)[0], _feature_sort_key(feature))
    )
    boundary_id_map = {
        (feature["dim"], feature["source_id"]): f"DmsRegEq_{index}"
        for index, feature in enumerate(codim_one, start=1)
    }

    junction_features = [feature for feature in features if feature["dim"] < ndim - 1]
    junction_features.sort(
        key=lambda feature: (
            _junction_group_of(feature)[0],
            feature["dim"],
            _feature_sort_key(feature),
        )
    )
    junction_id_map = {
        (feature["dim"], feature["source_id"]): f"DmsRegEqJnc_{index}"
        for index, feature in enumerate(junction_features, start=1)
    }

    # Region boundary IDs refer to source codimension-one features.
    source_boundary_by_id = defaultdict(list)
    for feature in codim_one:
        source_boundary_by_id[feature["source_id"]].append(feature)

    regions_by_boundary: Dict[Tuple[int, Any], List[Any]] = defaultdict(list)
    for region in source_regions:
        region_source_id = _canonical_scalar(getattr(region, "id", None))
        for boundary_source_id in list(getattr(region, "boundary_ids", None) or []):
            boundary_source_id = _canonical_scalar(boundary_source_id)
            matches = source_boundary_by_id.get(boundary_source_id, [])
            for feature in matches:
                regions_by_boundary[(feature["dim"], feature["source_id"])].append(
                    region_source_id
                )

    lower_feature_maps: Dict[int, Dict[Any, str]] = defaultdict(dict)
    for key, canonical_id in junction_id_map.items():
        lower_feature_maps[key[0]][key[1]] = canonical_id

    # Resolve immediate child-feature incidence and then its transitive closure.
    all_feature_by_key = {
        (feature["dim"], feature["source_id"]): feature for feature in features
    }
    child_keys_by_feature: Dict[Tuple[int, Any], List[Tuple[int, Any]]] = {}
    for feature in features:
        key = (feature["dim"], feature["source_id"])
        child_keys: List[Tuple[int, Any]] = []
        for child_source_id in feature["boundary_ids"]:
            child_source_id = _canonical_scalar(child_source_id)
            # The regular contract points to the immediately lower dimension.
            candidate = (feature["dim"] - 1, child_source_id)
            if candidate in all_feature_by_key:
                child_keys.append(candidate)
                continue
            # Be tolerant of older files that omitted an intermediate feature.
            matches = [
                other_key
                for other_key in all_feature_by_key
                if other_key[1] == child_source_id and other_key[0] < feature["dim"]
            ]
            if len(matches) == 1:
                child_keys.append(matches[0])
        child_keys_by_feature[key] = child_keys

    descendants_by_boundary = {
        key: _feature_descendants(key, child_keys_by_feature)
        for key in boundary_id_map
    }

    boundary_records: List[JsonObject] = []
    for feature in codim_one:
        key = (feature["dim"], feature["source_id"])
        adjacent_regions = _unique(
            region_id_map[source_id]
            for source_id in regions_by_boundary.get(key, [])
            if source_id in region_id_map
        )
        child_ids = [
            junction_id_map[child_key]
            for child_key in child_keys_by_feature.get(key, [])
            if child_key in junction_id_map
        ]
        boundary_records.append(
            {
                "id": boundary_id_map[key],
                "display_group": _boundary_group_of(feature)[1],
                "intrinsic_dimension": feature["dim"],
                "ambient_dimension": ndim,
                "boundary_type": feature["btype"],
                "dominant_species_ids": [
                    label_id_map[label]
                    for label in feature["labels"]
                    if label in label_id_map
                ],
                "region_pair": [
                    label_text_map.get(label, str(label)) for label in feature["labels"]
                ],
                "neighboring_regions": adjacent_regions,
                "boundary_features": child_ids,
                "geometry_basis": feature["geometry_basis"],
                "geometry_kind": _geometry_kind(feature["geometry"], feature["dim"]),
                "geometry": _json_safe(feature["geometry"]),
                "simplification": _json_safe(feature["simplification"]),
            }
        )

    junction_records: List[JsonObject] = []
    for feature in junction_features:
        key = (feature["dim"], feature["source_id"])
        connected_boundary_keys = [
            boundary_key
            for boundary_key, descendants in descendants_by_boundary.items()
            if key in descendants
        ]
        neighboring_region_ids: List[str] = []
        for boundary_key in connected_boundary_keys:
            neighboring_region_ids.extend(
                region_id_map[source_id]
                for source_id in regions_by_boundary.get(boundary_key, [])
                if source_id in region_id_map
            )
        junction_records.append(
            {
                "id": junction_id_map[key],
                "display_group": _junction_group_of(feature)[1],
                "intrinsic_dimension": feature["dim"],
                "ambient_dimension": ndim,
                "dominant_species_ids": [
                    label_id_map[label]
                    for label in feature["labels"]
                    if label in label_id_map
                ],
                "dominant_species": [
                    label_text_map.get(label, str(label)) for label in feature["labels"]
                ],
                "neighboring_regions": _unique(neighboring_region_ids),
                "connected_boundary_manifolds": [
                    boundary_id_map[boundary_key]
                    for boundary_key in connected_boundary_keys
                ],
                "at_sweep_limit": bool(feature["is_domain_edge"]),
                "geometry_basis": feature["geometry_basis"],
                "geometry_kind": _geometry_kind(feature["geometry"], feature["dim"]),
                "geometry": _json_safe(feature["geometry"]),
                "simplification": _json_safe(feature["simplification"]),
            }
        )

    boundary_record_by_key = {
        key: record for key, record in zip(boundary_id_map, boundary_records)
    }
    region_records: List[JsonObject] = []
    for region in source_regions:
        source_region_id = _canonical_scalar(getattr(region, "id", None))
        source_label = _canonical_scalar(getattr(region, "label", None))
        neighboring: List[JsonObject] = []
        canonical_boundary_ids: List[str] = []
        canonical_junction_ids: List[str] = []
        for boundary_source_id in list(getattr(region, "boundary_ids", None) or []):
            for feature in source_boundary_by_id.get(_canonical_scalar(boundary_source_id), []):
                boundary_key = (feature["dim"], feature["source_id"])
                boundary_id = boundary_id_map.get(boundary_key)
                if boundary_id is None:
                    continue
                canonical_boundary_ids.append(boundary_id)
                for other_source_region in regions_by_boundary.get(boundary_key, []):
                    if other_source_region == source_region_id:
                        continue
                    other_region_id = region_id_map.get(other_source_region)
                    if other_region_id is None:
                        continue
                    other_region = next(
                        item
                        for item in source_regions
                        if _canonical_scalar(getattr(item, "id", None))
                        == other_source_region
                    )
                    other_label = _canonical_scalar(getattr(other_region, "label", None))
                    neighboring.append(
                        {
                            "region_id": other_region_id,
                            "region_label": label_text_map.get(other_label, str(other_label)),
                            "boundary_manifold_id": boundary_id,
                        }
                    )
                for descendant in descendants_by_boundary.get(boundary_key, set()):
                    if descendant in junction_id_map:
                        canonical_junction_ids.append(junction_id_map[descendant])
        region_records.append(
            {
                "id": region_id_map[source_region_id],
                "phase_group": _region_group_of(region)[1],
                "dominant_species_id": label_id_map.get(source_label),
                "label": label_text_map.get(source_label, str(source_label)),
                "name": str(getattr(region, "name", "") or ""),
                "measure": _finite_or_none(getattr(region, "measure", None)),
                "flags": [
                    str(flag)
                    for flag in (getattr(region, "flags", None) or [])
                ],
                "boundary_manifolds": _unique(canonical_boundary_ids),
                "neighboring_regions": _dedupe_records(
                    neighboring,
                    key=lambda item: (
                        item["region_id"], item["boundary_manifold_id"]
                    ),
                ),
                "junction_features": _unique(canonical_junction_ids),
            }
        )

    labels_to_regions: Dict[str, List[str]] = defaultdict(list)
    for region in region_records:
        labels_to_regions[region["label"]].append(region["id"])

    cuts = _build_exact_cuts(
        raster,
        axis_records=axis_records,
        label_id_map=label_id_map,
        label_text_map=label_text_map,
    )

    source_mapping: JsonObject = {
        "dominant_species": {
            label_id_map[source_id]: {
                "source_label_id": _json_safe(source_id),
                "source_catalog_value": _json_safe(
                    label_catalog.get(source_id, label_catalog.get(str(source_id)))
                ),
            }
            for source_id in ordered_label_ids
        },
        "regions": {
            region_id_map[_canonical_scalar(getattr(region, "id", None))]: {
                "source_id": _json_safe(getattr(region, "id", None)),
                "source_collection": "regions",
            }
            for region in source_regions
        },
        "boundary_manifolds": {
            boundary_id_map[(feature["dim"], feature["source_id"])]: {
                "source_id": _json_safe(feature["source_id"]),
                "source_collection": feature["source_collection"],
                "intrinsic_dimension": feature["dim"],
            }
            for feature in codim_one
        },
        "junction_features": {
            junction_id_map[(feature["dim"], feature["source_id"])]: {
                "source_id": _json_safe(feature["source_id"]),
                "source_collection": feature["source_collection"],
                "intrinsic_dimension": feature["dim"],
            }
            for feature in junction_features
        },
    }

    report: JsonObject = {
        "schema_name": "srd46.predominance_verdict",
        "schema_version": 1,
        "report_kind": "predominance",
        "sweep_method": str(sweep_method),
        "system": _system_record(
            metadata,
            sweep_method=sweep_method,
            axis_records=axis_records,
            raster=raster,
        ),
        "dominant_species_catalog": [
            {"id": label_id_map[source_id], "label": label_text_map[source_id]}
            for source_id in ordered_label_ids
        ],
        "topology_stats": {
            "ambient_dimension": ndim,
            "dominant_species_labels": len(ordered_label_ids),
            "connected_regions": len(region_records),
            "pairwise_boundary_manifolds": len(boundary_records),
            "junction_features_by_intrinsic_dimension": {
                str(dim): sum(
                    feature["intrinsic_dimension"] == dim
                    for feature in junction_records
                )
                for dim in sorted({item["intrinsic_dimension"] for item in junction_records})
            },
            "internal_junction_features": sum(
                not item["at_sweep_limit"] for item in junction_records
            ),
            "sweep_limit_junction_features": sum(
                item["at_sweep_limit"] for item in junction_records
            ),
            "disconnected_species": [
                {"label": label, "region_ids": region_ids}
                for label, region_ids in labels_to_regions.items()
                if len(region_ids) > 1
            ],
        },
        "example_cuts": cuts,
        "calculation_species_by_principal_element": (
            _calculation_species_records(metadata)
        ),
        "topology_details": {
            "coordinate_order": axis_names,
            "grouped": grouping_active,
            "grouping_parser_failure": grouping_parser_failure,
            "regions": region_records,
            "boundary_manifolds": boundary_records,
            "junction_features": junction_records,
        },
        "source_mapping": source_mapping,
    }
    return report


def export_predominance_verdict(
    topology: Any,
    output_path: str | Path,
    *,
    axes: Optional[Sequence[Any]] = None,
    final_label_map: Any = None,
    built_metadata: Any = None,
    sweep_method: str = "predominance",
    display_axis_order: Optional[Sequence[str]] = None,
) -> JsonObject:
    """Write a complete Markdown verdict and normalized JSON sidecar.

    ``output_path`` may be the desired ``.md`` path or a stem.  A stem ending
    in ``_verdict`` is used as-is; otherwise ``_verdict`` is appended.  The
    returned dictionary contains both paths and the in-memory report.
    """

    report = build_predominance_verdict(
        topology,
        axes=axes,
        final_label_map=final_label_map,
        built_metadata=built_metadata,
        sweep_method=sweep_method,
        display_axis_order=display_axis_order,
    )
    markdown_path, json_path = _output_paths(output_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_predominance_verdict(report), encoding="utf-8")
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return {
        "markdown_path": str(markdown_path),
        "json_path": str(json_path),
        "report": report,
    }


def verdict_feature_id_maps(report: Mapping[str, Any]) -> Dict[str, Any]:
    """Invert ``report["source_mapping"]`` for id-consistent sidecar exports.

    Returns ``{"features": {(intrinsic_dim, source_id): canonical_id},
    "regions": {source_id: canonical_id}, "labels": {source_label_id:
    canonical_id}}`` so sidecar artifacts (e.g. the topo feature CSVs) can
    name every feature exactly as the verdict report does.
    """

    mapping = (report or {}).get("source_mapping") or {}
    features: Dict[Tuple[int, Any], str] = {}
    for section in ("boundary_manifolds", "junction_features"):
        for canonical_id, record in (mapping.get(section) or {}).items():
            features[
                (int(record["intrinsic_dimension"]), record["source_id"])
            ] = canonical_id
    regions = {
        record["source_id"]: canonical_id
        for canonical_id, record in (mapping.get("regions") or {}).items()
    }
    labels = {
        record["source_label_id"]: canonical_id
        for canonical_id, record in (
            mapping.get("dominant_species") or {}
        ).items()
    }
    return {"features": features, "regions": regions, "labels": labels}


def render_predominance_verdict(report: Mapping[str, Any]) -> str:
    """Render a normalized report in the reference Markdown fashion."""

    system = report["system"]
    stats = report["topology_stats"]
    details = report["topology_details"]
    grouped = bool(details.get("grouped"))
    axes = details["coordinate_order"]
    ndim = int(stats["ambient_dimension"])
    geometry_decimal_places = _geometry_decimal_places(
        system.get("final_grid_spacing")
    )
    lines = [f"# Solver report ({report['sweep_method']})", "", "## System"]
    lines.append(f"- Components: {_list_text(system['components'])}")
    lines.append("- Constraints:")
    if system["constraints"]:
        lines.extend(f"  -- {item}" for item in system["constraints"])
    else:
        lines.append("  -- not reported")
    lines.append(
        f"- Potential reference: {_value_text(system['potential_reference'])}"
    )
    lines.append(
        "- Domain (axis-aligned sweep box): "
        + _named_coordinate_tuple(
            [
                (
                    str(item["axis"]),
                    _coordinate_interval_text(
                        item["range"], _axis_unit(item["axis"])
                    ),
                )
                for item in system["domain"]
            ]
        )
    )
    lines.append(
        "- Coarse grid spacing: "
        + _spacing_text(system.get("coarse_grid_spacing"), axes)
    )
    lines.append(
        "- Final classified-grid spacing: "
        + _spacing_text(system.get("final_grid_spacing"), axes)
    )
    lines.append(f"- Semantics: {system['semantics']}")
    lines.append(
        "- Cut basis: Final classified label grid; no cut transition is "
        "inferred from compact/RDP geometry."
    )

    lines.extend(["", "## Dominant species catalog"])
    catalog = report["dominant_species_catalog"]
    if catalog:
        lines.extend(f"- {item['id']}: {item['label']}" for item in catalog)
    else:
        lines.append("- none")

    lines.extend(["", "## Topology stats"])
    lines.append(f"- {stats['dominant_species_labels']} dominant-species labels")
    lines.append(f"- {stats['connected_regions']} connected regions")
    lines.append(
        f"- {stats['pairwise_boundary_manifolds']} pairwise boundary "
        f"{_dimensional_noun(ndim - 1, plural=True)}"
    )
    lines.append(f"- {stats['internal_junction_features']} internal junction features")
    lines.append(
        f"- {stats['sweep_limit_junction_features']} junction features at a sweep limit"
    )
    lines.append("- Disconnected dominant species:")
    if stats["disconnected_species"]:
        for item in stats["disconnected_species"]:
            lines.append(
                f"  -- {item['label']}: {len(item['region_ids'])} separate regions "
                f"{_list_text(item['region_ids'])}"
            )
    else:
        lines.append("  -- none")

    for cut in report["example_cuts"]:
        sweep_axis = str(cut["sweep_axis"])
        lines.extend(
            ["", f"## Reference line (classified-grid cut) along {sweep_axis}"]
        )
        fixed_entries: List[Tuple[str, str]] = []
        index_entries: List[Tuple[str, str]] = []
        for name, coordinate, sample_index in zip(
            axes, cut["fixed_coordinates"], cut["fixed_sample_indices"]
        ):
            axis = str(name)
            if axis == sweep_axis:
                fixed_entries.append((axis, "swept"))
                index_entries.append((axis, "swept"))
            else:
                fixed_entries.append(
                    (axis, _coordinate_value_text(coordinate, _axis_unit(axis)))
                )
                index_entries.append(
                    (
                        axis,
                        "sample not reported"
                        if sample_index is None
                        else f"sample {sample_index}",
                    )
                )
        lines.append(
            "- One grid line; every other axis is fixed at its grid sample "
            "nearest the domain center: " + _named_coordinate_tuple(fixed_entries)
        )
        lines.append(
            "- Fixed sample indices: " + _named_coordinate_tuple(index_entries)
        )
        for segment in cut["segments"]:
            text = (
                f"- samples {segment['sample_index_interval'][0]}–"
                f"{segment['sample_index_interval'][1]}, "
                + _reference_line_tuple(
                    axes,
                    sweep_axis,
                    cut["fixed_coordinates"],
                    segment["sample_coordinate_interval"],
                )
                + f": {segment['dominant_label']} ({segment['dominant_species_id']})"
            )
            lines.append(text)
            if segment["transition_bracket_before"] is not None:
                lines.append(
                    "  -- preceding label change is bracketed by adjacent samples "
                    + _reference_line_tuple(
                        axes,
                        sweep_axis,
                        cut["fixed_coordinates"],
                        segment["transition_bracket_before"],
                    )
                )

    lines.extend(
        [
            "",
            "## Topology details",
            f"// Coordinate order: {_list_text(axes)}",
        ]
    )
    parser_failure = details.get("grouping_parser_failure")
    if parser_failure:
        lines.extend(
            [
                f"// PARSER FAILURE — species attribute resolution: {parser_failure}",
                "// Phase/redox grouping is unavailable; features appear in "
                "natural source order. Judge from the free-energy card whether "
                "this ungrouped listing is credible before quoting phase or "
                "redox claims.",
            ]
        )
    lines.extend(
        [
            "",
            "### canonical topology convention",
            "| Canonical family | Meaning |",
            "|---|---|",
            "| `Dms_i` | Dominant-species label |",
            "| `DmsReg_i` | Connected region |",
            "| `DmsRegEq_i` | Connected pairwise boundary manifold |",
            "| `DmsRegEqJnc_i` | Lower-dimensional junction feature |",
        ]
    )
    lines.extend(["", "### regions"])
    if details["regions"]:
        current_group = None
        for region in details["regions"]:
            if grouped:
                group_label = region.get("phase_group")
                if group_label != current_group:
                    current_group = group_label
                    lines.append(f"#### {group_label}")
            lines.append(f"- **{region['id']} {{{region['label']}}}**")
            lines.append(
                f"  -- Measure in the solver coordinate frame: "
                f"{_value_text(region['measure'])}"
            )
            lines.append("  -- Neighboring regions:")
            if region["neighboring_regions"]:
                for neighbor in region["neighboring_regions"]:
                    lines.append(
                        f"    --- {neighbor['region_id']} "
                        f"{{{neighbor['region_label']}}} via "
                        f"{neighbor['boundary_manifold_id']}"
                    )
            else:
                lines.append("    --- none recorded")
            lines.append(
                "  -- Junction features: " + _list_text(region["junction_features"])
            )
    else:
        lines.append("- none")

    if ndim == 1:
        boundary_heading = "### boundary points/equilibria"
    elif ndim == 2:
        boundary_heading = "### boundary curves/equilibria"
    else:
        boundary_heading = (
            f"### pairwise boundary manifolds "
            f"(intrinsic dimension {ndim - 1})"
        )
    lines.extend(["", boundary_heading])
    if details["boundary_manifolds"]:
        current_group = None
        for boundary in details["boundary_manifolds"]:
            if grouped:
                group_label = boundary.get("display_group")
                if group_label != current_group:
                    current_group = group_label
                    lines.append(f"#### {group_label}")
            pair = " | ".join(boundary["region_pair"]) or "labels not recorded"
            lines.append(f"- **{boundary['id']}: {pair}**")
            lines.append(
                f"  -- Intrinsic dimension: {boundary['intrinsic_dimension']} "
                f"({_dimensional_noun(boundary['intrinsic_dimension'])})"
            )
            lines.append(
                "  -- Neighboring regions: "
                + _list_text(boundary["neighboring_regions"])
            )
            lines.append(
                f"  -- Geometry: {boundary['geometry_basis']} "
                f"{boundary['geometry_kind']}"
            )
            if ndim == 2 and boundary["geometry_kind"] == "polyline":
                lines.append(
                    "  -- Primary compact boundary vertices: "
                    + _geometry_markdown_text(
                        boundary["geometry"],
                        axes,
                        decimal_places=geometry_decimal_places,
                    )
                )
            elif ndim == 1 and boundary["geometry_kind"] == "point":
                lines.append(
                    "  -- Boundary location: "
                    + _geometry_markdown_text(
                        boundary["geometry"],
                        axes,
                        decimal_places=geometry_decimal_places,
                    )
                )
            else:
                lines.append(
                    "  -- Compact geometry record: "
                    + _geometry_markdown_text(
                        boundary["geometry"],
                        axes,
                        decimal_places=geometry_decimal_places,
                    )
                )
            lines.append(
                "  -- Boundary/junction features: "
                + _list_text(boundary["boundary_features"])
            )
            if boundary["simplification"]:
                lines.append(
                    "  -- Simplification metadata: "
                    + _simplification_markdown_text(
                        boundary["simplification"],
                        axes,
                        decimal_places=geometry_decimal_places,
                    )
                )
    else:
        lines.append("- none")

    lines.extend(["", "### junction features"])
    if details["junction_features"]:
        current_group = None
        for junction in details["junction_features"]:
            if grouped:
                group_label = junction.get("display_group")
                if group_label != current_group:
                    current_group = group_label
                    lines.append(f"#### {group_label}")
            lines.append(
                f"- **{junction['id']}** — intrinsic dimension "
                f"{junction['intrinsic_dimension']} "
                f"({_dimensional_noun(junction['intrinsic_dimension'])})"
            )
            lines.append(
                "  -- Dominant species: " + _list_text(junction["dominant_species"])
            )
            lines.append(
                "  -- Neighboring regions: "
                + _list_text(junction["neighboring_regions"])
            )
            lines.append(
                "  -- Connected boundary manifolds: "
                + _list_text(junction["connected_boundary_manifolds"])
            )
            lines.append(
                f"  -- At sweep limit: {str(junction['at_sweep_limit']).lower()}"
            )
            lines.append(
                f"  -- Geometry: {junction['geometry_basis']} "
                f"{junction['geometry_kind']} "
                + _geometry_markdown_text(
                    junction["geometry"],
                    axes,
                    decimal_places=geometry_decimal_places,
                )
            )
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Canonical-to-source lookup",
            "The normalized JSON sidecar preserves the source collection, source ID, "
            "and intrinsic dimension for every canonical topology ID. Use that mapping "
            "for ID-scoped topology reads; the raw topology JSON is not part of this "
            "verdict text.",
        ]
    )

    lines.extend(["", "## Calculation species by principal element"])
    species_records = report.get(
        "calculation_species_by_principal_element", []
    )
    if species_records:
        for item in species_records:
            lines.append(f"- **{item['principal_element']}**")
            lines.append(
                "  -- included: " + _list_text(item.get("included", []))
            )
            lines.append(
                "  -- excluded: " + _list_text(item.get("excluded", []))
            )
    else:
        lines.append("- not reported")
    return "\n".join(lines) + "\n"


def _collect_features(topology: Any, ndim: int, axis_names: Sequence[str]) -> List[JsonObject]:
    """Normalize raw and compact topology feature objects."""

    result: List[JsonObject] = []
    compact_features = getattr(topology, "features", None)
    if isinstance(compact_features, Mapping):
        for raw_dim, feature_items in compact_features.items():
            dim = int(raw_dim)
            for feature in feature_items or []:
                geometry_compact = getattr(feature, "geometry_compact", None)
                geometry_raw = getattr(feature, "geometry_raw", None)
                use_compact = geometry_compact is not None
                result.append(
                    {
                        "source_id": _canonical_scalar(getattr(feature, "id", None)),
                        "source_collection": f"features_{dim}d",
                        "dim": dim,
                        "labels": [
                            _canonical_scalar(item)
                            for item in list(getattr(feature, "labels", None) or [])
                        ],
                        "btype": str(getattr(feature, "btype", "") or ""),
                        "boundary_ids": [
                            _canonical_scalar(item)
                            for item in list(getattr(feature, "boundary_ids", None) or [])
                        ],
                        "is_domain_edge": bool(
                            getattr(feature, "is_domain_edge", False)
                        ),
                        "geometry": geometry_compact if use_compact else geometry_raw,
                        "geometry_basis": "compact" if use_compact else "raw",
                        "simplification": dict(
                            getattr(feature, "simplification_params", None) or {}
                        ),
                    }
                )
        return result

    # Raw TopologyND: pairwise boundaries are codimension one.
    for boundary in list(getattr(topology, "boundaries", None) or []):
        result.append(
            {
                "source_id": _canonical_scalar(getattr(boundary, "id", None)),
                "source_collection": f"features_{ndim - 1}d",
                "dim": ndim - 1,
                "labels": [
                    _canonical_scalar(getattr(boundary, "left_label", None)),
                    _canonical_scalar(getattr(boundary, "right_label", None)),
                ],
                "btype": str(getattr(boundary, "btype", "") or ""),
                "boundary_ids": [
                    _canonical_scalar(item)
                    for item in list(getattr(boundary, "junction_ids", None) or [])
                ],
                "is_domain_edge": False,
                "geometry": getattr(boundary, "geometry", None),
                "geometry_basis": "raw",
                "simplification": {},
            }
        )
    for junction in list(getattr(topology, "junctions", None) or []):
        explicit_dim = int(getattr(junction, "intrinsic_dim", 0) or 0)
        labels = [
            _canonical_scalar(item)
            for item in list(getattr(junction, "adjacent_labels", None) or [])
        ]
        inferred_dim = max(ndim - len(labels) + 1, 0) if labels else 0
        dim = explicit_dim if explicit_dim > 0 else inferred_dim
        geometry = getattr(junction, "geometry", None)
        if geometry is None:
            geometry = {
                axis: float(getattr(junction, "coords", {}).get(axis))
                for axis in axis_names
                if axis in getattr(junction, "coords", {})
            }
        result.append(
            {
                "source_id": _canonical_scalar(getattr(junction, "id", None)),
                "source_collection": f"features_{dim}d",
                "dim": dim,
                "labels": labels,
                "btype": "junction",
                "boundary_ids": [],
                "is_domain_edge": bool(getattr(junction, "is_domain_edge", False)),
                "geometry": geometry,
                "geometry_basis": "raw",
                "simplification": {},
            }
        )

    # Raw boundary -> junction incidence lives on the boundary, not junction.
    return result


def _normalize_axes_and_raster(
    topology: Any,
    *,
    ndim: int,
    axes: Optional[Sequence[Any]],
    final_label_map: Any,
    display_axis_order: Optional[Sequence[str]],
) -> Tuple[
    List[JsonObject],
    Optional[Tuple[List[np.ndarray], np.ndarray, Dict[Any, Any]]],
    List[str],
    List[int],
]:
    settings = dict(getattr(topology, "settings", None) or {})
    topology_axis_names = list(
        getattr(topology, "axis_names", None)
        or settings.get("axis_names", [])
        or []
    )
    topology_axis_ranges = dict(
        getattr(topology, "axis_ranges", None)
        or settings.get("axis_ranges", {})
        or {}
    )

    axis_items = list(axes or [])
    names: List[str] = []
    for index in range(ndim):
        if index < len(axis_items):
            item = axis_items[index]
            if isinstance(item, Mapping):
                name = item.get("name")
            else:
                name = getattr(item, "name", None)
            names.append(str(name or f"axis_{index + 1}"))
        elif index < len(topology_axis_names):
            names.append(str(topology_axis_names[index]))
        else:
            names.append(f"axis_{index + 1}")

    raster = _normalize_label_map(final_label_map, preferred_axis_names=names)

    records: List[JsonObject] = []
    for index, name in enumerate(names):
        values: Optional[np.ndarray] = None
        declared_range: Optional[Tuple[float, float]] = None
        display_label = name
        if index < len(axis_items):
            item = axis_items[index]
            if isinstance(item, Mapping):
                if item.get("values") is not None:
                    values = np.asarray(item["values"], dtype=float)
                candidate_range = item.get("range", item.get("domain_range"))
                if candidate_range is not None:
                    declared_range = tuple(float(value) for value in candidate_range)
                display_label = str(item.get("display_label") or name)
            else:
                candidate_values = getattr(item, "values", None)
                if candidate_values is not None:
                    values = np.asarray(candidate_values, dtype=float)
                candidate_range = getattr(item, "range", None)
                if candidate_range is not None:
                    declared_range = tuple(float(value) for value in candidate_range)
                display_label = str(getattr(item, "display_label", None) or name)
        if raster is not None:
            # Effective/final values are authoritative for exact cuts.
            values = raster[0][index]
        if declared_range is None and name in topology_axis_ranges:
            declared_range = tuple(float(value) for value in topology_axis_ranges[name])
        if declared_range is None and values is not None and values.size:
            declared_range = (float(values[0]), float(values[-1]))
        if declared_range is None:
            declared_range = (0.0, 0.0)
        records.append(
            {
                "name": name,
                "display_label": display_label,
                "range": [float(declared_range[0]), float(declared_range[1])],
                "values": values,
            }
        )

    if raster is not None:
        axis_values, labels, catalog = raster
        if len(axis_values) != ndim or labels.ndim != ndim:
            raise ValueError(
                "final_label_map dimensionality does not match topology.ndim"
            )
        expected = tuple(len(values) for values in axis_values)
        if labels.shape != expected:
            raise ValueError(
                f"final label shape {labels.shape} does not match axis lengths {expected}"
            )

    source_names = list(names)
    axis_permutation = _axis_permutation(source_names, display_axis_order)
    if axis_permutation != list(range(ndim)):
        records = [records[index] for index in axis_permutation]
        if raster is not None:
            axis_values, labels, catalog = raster
            raster = (
                [axis_values[index] for index in axis_permutation],
                np.transpose(labels, axes=axis_permutation),
                catalog,
            )
    return records, raster, source_names, axis_permutation


def _axis_permutation(
    source_axis_names: Sequence[str],
    display_axis_order: Optional[Sequence[str]],
) -> List[int]:
    """Return a validated coordinate permutation for an LLM-facing report."""

    source_names = [str(name) for name in source_axis_names]
    if display_axis_order is None:
        return list(range(len(source_names)))
    requested = [str(name) for name in display_axis_order]
    if len(set(requested)) != len(requested):
        raise ValueError("display_axis_order must not contain duplicate axes")
    unknown = [name for name in requested if name not in source_names]
    if unknown:
        raise ValueError(
            "display_axis_order contains axes absent from the sweep: "
            + ", ".join(unknown)
        )
    ordered_names = requested + [
        name for name in source_names if name not in requested
    ]
    return [source_names.index(name) for name in ordered_names]


def _permute_axis_ordered_metadata(
    metadata: Mapping[str, Any],
    *,
    axis_permutation: Sequence[int],
    ndim: int,
) -> JsonObject:
    """Keep sequence-valued axis metadata aligned with the report order."""

    result = dict(metadata)
    spacing = result.get("coarse_grid_spacing")
    if (
        isinstance(spacing, Sequence)
        and not isinstance(spacing, (str, bytes))
        and len(spacing) == ndim
    ):
        result["coarse_grid_spacing"] = [
            spacing[index] for index in axis_permutation
        ]
    return result


def _permute_coordinate_geometry(
    geometry: Any,
    *,
    source_axis_names: Sequence[str],
    axis_permutation: Sequence[int],
) -> Any:
    """Permute coordinate-bearing geometry without touching connectivity.

    Topology geometry occurs as coordinate dictionaries, point arrays,
    polylines, point clouds, or ``(vertices, triangles)`` surface meshes.
    Triangle indices and all non-coordinate metadata remain unchanged.
    """

    if geometry is None or np.isscalar(geometry):
        return geometry

    ndim = len(source_axis_names)
    output_axis_names = [source_axis_names[index] for index in axis_permutation]

    if isinstance(geometry, Mapping):
        # A named coordinate record has no ambiguous columns, but preserve the
        # same visible order as all array-valued geometry in the report.
        if all(name in geometry for name in source_axis_names):
            result = {name: geometry[name] for name in output_axis_names}
            result.update(
                (key, value)
                for key, value in geometry.items()
                if key not in source_axis_names
            )
            return result

        result = dict(geometry)
        for key in ("vertices", "points", "point_cloud", "polyline"):
            if key in result:
                result[key] = _permute_coordinate_geometry(
                    result[key],
                    source_axis_names=source_axis_names,
                    axis_permutation=axis_permutation,
                )
        # Mesh connectivity is intentionally not passed through the generic
        # point-sequence path: in three dimensions a triangle also has length
        # three, but its entries are vertex indices rather than coordinates.
        return result

    if isinstance(geometry, tuple) and len(geometry) == 2:
        first, second = geometry
        if hasattr(first, "shape") and hasattr(second, "shape"):
            return (
                _permute_coordinate_geometry(
                    first,
                    source_axis_names=source_axis_names,
                    axis_permutation=axis_permutation,
                ),
                second,
            )

    if isinstance(geometry, np.ndarray):
        if geometry.ndim == 1 and geometry.shape[0] == ndim:
            return geometry[np.asarray(axis_permutation, dtype=int)]
        if geometry.ndim >= 2 and geometry.shape[-1] == ndim:
            return geometry[..., np.asarray(axis_permutation, dtype=int)]
        return geometry

    if isinstance(geometry, (list, tuple)):
        if len(geometry) == ndim and all(np.isscalar(item) for item in geometry):
            reordered = [geometry[index] for index in axis_permutation]
            return tuple(reordered) if isinstance(geometry, tuple) else reordered
        reordered_items = [
            _permute_coordinate_geometry(
                item,
                source_axis_names=source_axis_names,
                axis_permutation=axis_permutation,
            )
            for item in geometry
        ]
        return tuple(reordered_items) if isinstance(geometry, tuple) else reordered_items

    return geometry


def _permute_simplification_coordinates(
    simplification: Mapping[str, Any],
    *,
    source_axis_names: Sequence[str],
    axis_permutation: Sequence[int],
) -> JsonObject:
    """Permute only known coordinate arrays in simplification metadata."""

    result = dict(simplification or {})
    for key in (
        "adaptive_pts",
        "envelope_pts",
        "control_points",
        "compact_points",
        "vertices",
        "points",
    ):
        if key in result:
            result[key] = _permute_coordinate_geometry(
                result[key],
                source_axis_names=source_axis_names,
                axis_permutation=axis_permutation,
            )
    return result


def _normalize_label_map(
    final_label_map: Any,
    *,
    preferred_axis_names: Optional[Sequence[str]] = None,
) -> Optional[Tuple[List[np.ndarray], np.ndarray, Dict[Any, Any]]]:
    if final_label_map is None:
        return None
    if isinstance(final_label_map, Mapping):
        axis_values_raw = final_label_map.get(
            "axis_values", final_label_map.get("axes")
        )
        labels_raw = final_label_map.get("labels")
        catalog_raw = final_label_map.get(
            "label_catalog", final_label_map.get("catalog", {})
        )
        if isinstance(axis_values_raw, Mapping):
            if preferred_axis_names and all(
                name in axis_values_raw for name in preferred_axis_names
            ):
                axis_values_raw = [axis_values_raw[name] for name in preferred_axis_names]
            else:
                axis_values_raw = list(axis_values_raw.values())
    elif isinstance(final_label_map, (tuple, list)) and len(final_label_map) >= 2:
        axis_values_raw = final_label_map[0]
        labels_raw = final_label_map[1]
        catalog_raw = final_label_map[2] if len(final_label_map) > 2 else {}
    else:
        raise TypeError(
            "final_label_map must be (axis_values, labels, catalog) or a mapping"
        )
    if axis_values_raw is None or labels_raw is None:
        raise ValueError("final_label_map must contain axis values and labels")
    axis_values = [np.asarray(values, dtype=float) for values in axis_values_raw]
    if any(values.ndim != 1 for values in axis_values):
        raise ValueError("each final-label-map axis must be one-dimensional")
    labels = np.asarray(labels_raw)
    catalog = {
        _canonical_scalar(key): value for key, value in dict(catalog_raw or {}).items()
    }
    return axis_values, labels, catalog


def _build_exact_cuts(
    raster: Optional[Tuple[List[np.ndarray], np.ndarray, Dict[Any, Any]]],
    *,
    axis_records: Sequence[Mapping[str, Any]],
    label_id_map: Mapping[Any, str],
    label_text_map: Mapping[Any, str],
) -> List[JsonObject]:
    if raster is None:
        return []
    axis_values, labels, _catalog = raster
    if labels.size == 0 or any(len(values) == 0 for values in axis_values):
        return []

    cuts: List[JsonObject] = []
    ndim = labels.ndim
    midpoint_indices = []
    for values, record in zip(axis_values, axis_records):
        lo, hi = record["range"]
        midpoint = (float(lo) + float(hi)) / 2.0
        midpoint_indices.append(int(np.argmin(np.abs(values - midpoint))))

    for sweep_dim in range(ndim):
        selector: List[Any] = list(midpoint_indices)
        selector[sweep_dim] = slice(None)
        cut_labels = np.asarray(labels[tuple(selector)]).reshape(-1)
        values = axis_values[sweep_dim]
        fixed_coordinates: List[Optional[float]] = []
        fixed_indices: List[Optional[int]] = []
        for dim in range(ndim):
            if dim == sweep_dim:
                fixed_coordinates.append(None)
                fixed_indices.append(None)
            else:
                fixed_coordinates.append(float(axis_values[dim][midpoint_indices[dim]]))
                fixed_indices.append(int(midpoint_indices[dim]))

        segments: List[JsonObject] = []
        start = 0
        for index in range(1, len(cut_labels) + 1):
            if index < len(cut_labels) and _labels_equal(
                cut_labels[index], cut_labels[start]
            ):
                continue
            source_label = _canonical_scalar(cut_labels[start])
            segments.append(
                {
                    "sample_index_interval": [start, index - 1],
                    "sample_coordinate_interval": [
                        float(values[start]),
                        float(values[index - 1]),
                    ],
                    "dominant_species_id": label_id_map.get(
                        source_label, f"unmapped:{source_label}"
                    ),
                    "dominant_label": label_text_map.get(
                        source_label, str(source_label)
                    ),
                    "transition_bracket_before": (
                        [float(values[start - 1]), float(values[start])]
                        if start > 0
                        else None
                    ),
                }
            )
            start = index
        cuts.append(
            {
                "name": (
                    "reference line (mid-domain classified-grid cut) along "
                    f"{axis_records[sweep_dim]['name']}"
                ),
                "sweep_axis": axis_records[sweep_dim]["name"],
                "fixed_coordinates": fixed_coordinates,
                "fixed_sample_indices": fixed_indices,
                "segments": segments,
                "source": "final_classified_label_grid",
            }
        )
    return cuts


def _system_record(
    metadata: Mapping[str, Any],
    *,
    sweep_method: str,
    axis_records: Sequence[Mapping[str, Any]],
    raster: Optional[Tuple[List[np.ndarray], np.ndarray, Dict[Any, Any]]],
) -> JsonObject:
    components = _metadata_list(
        metadata,
        "components",
        "system_components",
        "component_names",
    )
    if not components:
        system_name = _metadata_value(metadata, "system_name", "name")
        if system_name not in (None, ""):
            components = [str(system_name)]
    constraints = _metadata_list(
        metadata,
        "constraints",
        "constraint_summary",
        "declared_constraints",
    )
    potential_reference = _metadata_value(
        metadata,
        "potential_reference",
        "electrode_reference",
        "reference_electrode",
    )
    coarse_spacing = _ordered_metadata_spacing(
        metadata.get("coarse_grid_spacing"), axis_records
    )
    final_spacing: List[Optional[float]] = []
    for index, record in enumerate(axis_records):
        values = raster[0][index] if raster is not None else record.get("values")
        if values is None or len(values) < 2:
            final_spacing.append(None)
        else:
            differences = np.abs(np.diff(np.asarray(values, dtype=float)))
            final_spacing.append(float(np.median(differences)))

    semantics = _metadata_value(metadata, "semantics")
    if not semantics:
        semantics = (
            "Each connected region is the dominant calculated entity for the "
            "reported classification rule, not the exclusive entity present "
            "and not a kinetic prediction."
        )
    return {
        "components": components,
        "constraints": constraints,
        "potential_reference": _json_safe(potential_reference),
        "domain": [
            {"axis": record["name"], "range": list(record["range"])}
            for record in axis_records
        ],
        "coarse_grid_spacing": coarse_spacing,
        "final_grid_spacing": final_spacing,
        "final_grid_shape": list(raster[1].shape) if raster is not None else None,
        "classification_basis": (
            "final_classified_label_grid" if raster is not None else "topology_only"
        ),
        "semantics": str(semantics),
        "sweep_method": str(sweep_method),
    }


def _metadata_mapping(value: Any) -> JsonObject:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    result: JsonObject = {}
    for name in (
        "system_name",
        "name",
        "components",
        "system_components",
        "component_names",
        "constraints",
        "constraint_summary",
        "declared_constraints",
        "potential_reference",
        "electrode_reference",
        "reference_electrode",
        "coarse_grid_spacing",
        "semantics",
        "calculation_species_by_principal_element",
    ):
        if hasattr(value, name):
            result[name] = getattr(value, name)
    return result


def _calculation_species_records(
    metadata: Mapping[str, Any],
) -> List[JsonObject]:
    """Normalize the solver's principal-element species audit for output."""

    raw = metadata.get("calculation_species_by_principal_element")
    if not isinstance(raw, Mapping):
        return []

    records: List[JsonObject] = []
    for principal_element, selection in raw.items():
        if not isinstance(selection, Mapping):
            continue
        included = _unique(
            str(value)
            for value in _sequence_or_empty(selection.get("included"))
        )
        included_set = set(included)
        excluded = [
            value
            for value in _unique(
                str(value)
                for value in _sequence_or_empty(selection.get("excluded"))
            )
            if value not in included_set
        ]
        records.append(
            {
                "principal_element": str(principal_element),
                "included": included,
                "excluded": excluded,
            }
        )
    return records


def _sequence_or_empty(value: Any) -> Sequence[Any]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return [value]
    if isinstance(value, Sequence):
        return value
    return [value]


def _metadata_value(metadata: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name not in metadata:
            continue
        value = metadata[name]
        if value is None:
            continue
        if isinstance(value, str) and value == "":
            continue
        return value
    return None


def _metadata_list(metadata: Mapping[str, Any], *names: str) -> List[str]:
    value = _metadata_value(metadata, *names)
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [f"{key} = {_display_label(item, fallback='null')}" for key, item in value.items()]
    if isinstance(value, Iterable):
        return [str(item) for item in value]
    return [str(value)]


def _ordered_metadata_spacing(
    value: Any, axis_records: Sequence[Mapping[str, Any]]
) -> List[Optional[float]]:
    if value is None:
        return [None] * len(axis_records)
    if isinstance(value, Mapping):
        return [
            _finite_or_none(value.get(record["name"])) for record in axis_records
        ]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        if len(value) != len(axis_records):
            return [None] * len(axis_records)
        return [_finite_or_none(item) for item in value]
    if len(axis_records) == 1:
        return [_finite_or_none(value)]
    return [None] * len(axis_records)


def _feature_descendants(
    root: Tuple[int, Any],
    child_keys: Mapping[Tuple[int, Any], Sequence[Tuple[int, Any]]],
) -> set[Tuple[int, Any]]:
    result: set[Tuple[int, Any]] = set()
    pending = list(child_keys.get(root, []))
    while pending:
        key = pending.pop()
        if key in result:
            continue
        result.add(key)
        pending.extend(child_keys.get(key, []))
    return result


def _geometry_kind(geometry: Any, intrinsic_dim: int) -> str:
    if geometry is None:
        return "missing"
    if np.isscalar(geometry):
        return "point"
    if isinstance(geometry, Mapping):
        if "vertices" in geometry and "triangles" in geometry:
            return "surface_mesh"
        if intrinsic_dim == 0:
            return "point"
        if "point_cloud" in geometry:
            return "point_cloud"
        if "polyline" in geometry:
            return "polyline"
        return "coordinate_record"
    if isinstance(geometry, tuple) and len(geometry) == 2:
        if hasattr(geometry[0], "shape") and hasattr(geometry[1], "shape"):
            return "surface_mesh"
    if isinstance(geometry, (list, tuple, np.ndarray)):
        if intrinsic_dim == 0:
            return "point"
        if intrinsic_dim == 1:
            return "polyline"
        return "point_cloud"
    return "opaque_geometry"


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, tuple) and len(value) == 2:
        first, second = value
        if hasattr(first, "shape") and hasattr(second, "shape"):
            return {
                "vertices": _json_safe(first),
                "triangles": _json_safe(second),
            }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item) for item in value]
    return str(value)


def _canonical_scalar(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, str):
        stripped = value.strip()
        if re.fullmatch(r"[-+]?\d+", stripped):
            try:
                return int(stripped)
            except ValueError:
                pass
        return stripped
    return value


def _display_label(value: Any, *, fallback: str) -> str:
    if value is None or value == "":
        return fallback
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        for key in ("name", "label", "species", "species_name"):
            if value.get(key):
                return str(value[key])
        return json.dumps(_json_safe(value), ensure_ascii=False, sort_keys=True)
    if isinstance(value, (tuple, list)):
        return " + ".join(str(item) for item in value)
    return str(value)


def _feature_sort_key(feature: Mapping[str, Any]) -> Tuple[Any, ...]:
    return (_natural_key(feature["source_id"]), str(feature["source_collection"]))


def _natural_key(value: Any) -> Tuple[Any, ...]:
    if isinstance(value, (int, float)):
        return (0, float(value))
    parts = re.split(r"(\d+)", str(value))
    return (1,) + tuple(int(part) if part.isdigit() else part.lower() for part in parts)


def _unique(values: Iterable[Any]) -> List[Any]:
    result = []
    seen = set()
    for value in values:
        marker = json.dumps(_json_safe(value), sort_keys=True)
        if marker not in seen:
            result.append(value)
            seen.add(marker)
    return result


def _dedupe_records(values: Iterable[JsonObject], *, key) -> List[JsonObject]:
    result = []
    seen = set()
    for value in values:
        marker = key(value)
        if marker not in seen:
            result.append(value)
            seen.add(marker)
    return result


def _labels_equal(left: Any, right: Any) -> bool:
    left_value = _canonical_scalar(left)
    right_value = _canonical_scalar(right)
    try:
        return bool(left_value == right_value)
    except (TypeError, ValueError):
        return False


def _finite_or_none(value: Any) -> Optional[float]:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _output_paths(output_path: str | Path) -> Tuple[Path, Path]:
    path = Path(output_path)
    if path.suffix.lower() == ".md":
        markdown_path = path
    elif path.suffix:
        stem = path.stem
        if stem.endswith("_topology"):
            stem = stem[: -len("_topology")]
        if not stem.endswith("_verdict"):
            stem += "_verdict"
        markdown_path = path.with_name(stem + ".md")
    else:
        name = path.name if path.name.endswith("_verdict") else path.name + "_verdict"
        markdown_path = path.with_name(name + ".md")
    return markdown_path, markdown_path.with_suffix(".json")


def _value_text(value: Any) -> str:
    if value is None:
        return "not reported"
    if isinstance(value, float):
        return f"{value:.8g}"
    return str(value)


def _list_text(values: Sequence[Any]) -> str:
    return "[" + ", ".join(str(value) for value in values) + "]"


# Units attached to rendered coordinate values (no space before the unit).
# pH and a_w are dimensionless; unknown axes stay unit-less but are always
# rendered paired with their axis name.
_AXIS_UNIT_SUFFIXES = {"pH": "", "E_V": "V", "a_w": ""}

# Simplification-metadata keys whose values are coordinate point sequences.
_COORDINATE_SEQUENCE_KEYS = (
    "adaptive_pts",
    "envelope_pts",
    "control_points",
    "compact_points",
    "vertices",
    "points",
)


def _axis_unit(axis_name: Any) -> str:
    return _AXIS_UNIT_SUFFIXES.get(str(axis_name), "")


def _coordinate_value_text(
    value: Any, unit: str, *, decimal_places: Optional[int] = None
) -> str:
    numeric = _finite_or_none(value)
    if numeric is None:
        return _value_text(value)
    if decimal_places is not None:
        numeric = round(numeric, decimal_places)
        if numeric == 0.0:
            numeric = 0.0
    return f"{_value_text(numeric)}{unit}"


def _named_coordinate_tuple(entries: Sequence[Tuple[str, str]]) -> str:
    return "(" + ", ".join(f"{name}={text}" for name, text in entries) + ")"


def _coordinate_interval_text(
    values: Sequence[Any], unit: str, *, decimal_places: Optional[int] = None
) -> str:
    return (
        "["
        + ", ".join(
            _coordinate_value_text(value, unit, decimal_places=decimal_places)
            for value in values
        )
        + "]"
    )


def _reference_line_tuple(
    axis_names: Sequence[Any],
    sweep_axis: str,
    fixed_coordinates: Sequence[Any],
    sweep_values: Sequence[Any],
) -> str:
    """Full coordinate tuple for one reference-line record.

    The swept axis carries the value interval; every other axis carries its
    fixed coordinate, so no quoted value is separated from its context.
    """

    entries: List[Tuple[str, str]] = []
    for name, coordinate in zip(axis_names, fixed_coordinates):
        axis = str(name)
        if axis == sweep_axis:
            entries.append(
                (axis, _coordinate_interval_text(sweep_values, _axis_unit(axis)))
            )
        else:
            entries.append(
                (axis, _coordinate_value_text(coordinate, _axis_unit(axis)))
            )
    return _named_coordinate_tuple(entries)


def _point_tuple_text(
    point: Sequence[Any],
    axis_names: Sequence[Any],
    *,
    decimal_places: Optional[int] = None,
) -> str:
    return _named_coordinate_tuple(
        [
            (
                str(name),
                _coordinate_value_text(
                    value, _axis_unit(name), decimal_places=decimal_places
                ),
            )
            for name, value in zip(axis_names, point)
        ]
    )


def _is_scalar_point(value: Any, ndim: int) -> bool:
    return (
        isinstance(value, list)
        and len(value) == ndim
        and all(
            item is None or isinstance(item, (int, float))
            for item in value
        )
    )


def _is_point_sequence(value: Any, ndim: int) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(_is_scalar_point(item, ndim) for item in value)
    )


def _point_sequence_text(
    points: Sequence[Sequence[Any]],
    axis_names: Sequence[Any],
    *,
    decimal_places: Optional[int] = None,
) -> str:
    return (
        "["
        + ", ".join(
            _point_tuple_text(point, axis_names, decimal_places=decimal_places)
            for point in points
        )
        + "]"
    )


def _geometry_markdown_text(
    geometry: Any,
    axis_names: Sequence[Any],
    *,
    decimal_places: Optional[int] = None,
) -> str:
    """Render geometry with every coordinate axis-named and unit-suffixed."""

    safe = _json_safe(geometry)
    ndim = len(axis_names)
    if isinstance(safe, (int, float)) and not isinstance(safe, bool) and ndim == 1:
        return _point_tuple_text([safe], axis_names, decimal_places=decimal_places)
    if isinstance(safe, Mapping):
        axis_keys = {str(name) for name in axis_names}
        if all(str(name) in safe for name in axis_names):
            text = _named_coordinate_tuple(
                [
                    (
                        str(name),
                        _coordinate_value_text(
                            safe[str(name)],
                            _axis_unit(name),
                            decimal_places=decimal_places,
                        ),
                    )
                    for name in axis_names
                ]
            )
            extras = {
                key: value for key, value in safe.items() if key not in axis_keys
            }
            if extras:
                text += " " + _compact_json(extras, decimal_places=decimal_places)
            return text
        rendered_items = []
        for key, value in safe.items():
            if key == "triangles":
                # Triangle rows are vertex indices, never coordinates.
                rendered = _compact_json(value)
            elif _is_point_sequence(value, ndim):
                rendered = _point_sequence_text(
                    value, axis_names, decimal_places=decimal_places
                )
            elif _is_scalar_point(value, ndim):
                rendered = _point_tuple_text(
                    value, axis_names, decimal_places=decimal_places
                )
            else:
                rendered = _compact_json(value, decimal_places=decimal_places)
            rendered_items.append(f'"{key}": {rendered}')
        return "{" + ", ".join(rendered_items) + "}"
    if _is_scalar_point(safe, ndim):
        return _point_tuple_text(safe, axis_names, decimal_places=decimal_places)
    if _is_point_sequence(safe, ndim):
        return _point_sequence_text(safe, axis_names, decimal_places=decimal_places)
    return _compact_json(safe, decimal_places=decimal_places)


def _simplification_markdown_text(
    simplification: Any,
    axis_names: Sequence[Any],
    *,
    decimal_places: Optional[int] = None,
) -> str:
    safe = _json_safe(simplification)
    if not isinstance(safe, Mapping):
        return _compact_json(safe, decimal_places=decimal_places)
    ndim = len(axis_names)
    rendered_items = []
    for key, value in safe.items():
        if key in _COORDINATE_SEQUENCE_KEYS and _is_point_sequence(value, ndim):
            rendered = _point_sequence_text(
                value, axis_names, decimal_places=decimal_places
            )
        else:
            rendered = _compact_json(value, decimal_places=decimal_places)
        rendered_items.append(f'"{key}": {rendered}')
    return "{" + ", ".join(rendered_items) + "}"


def _spacing_text(values: Optional[Sequence[Any]], axes: Sequence[str]) -> str:
    if not values:
        return "not reported"
    return _named_coordinate_tuple(
        [
            (f"Δ{axis}", _coordinate_value_text(value, _axis_unit(axis)))
            for axis, value in zip(axes, values)
        ]
    )


def _dimensional_noun(dim: int, *, plural: bool = False) -> str:
    names = {0: "point", 1: "curve", 2: "surface", 3: "volume"}
    value = names.get(dim, f"{dim}-D manifold")
    if plural:
        return value + ("s" if not value.endswith("s") else "")
    return value


def _geometry_decimal_places(
    final_grid_spacing: Optional[Sequence[Any]],
    *,
    subdivisions: int = 16,
) -> Optional[int]:
    """Choose report precision finer than the finest classified-grid interval.

    Geometry in the normalized JSON remains lossless.  Only the Markdown view
    is rounded, using a decimal quantum no coarser than ``1 / subdivisions``
    of the smallest reported final-grid spacing.
    """

    if not final_grid_spacing:
        return None
    spacings: List[float] = []
    for value in final_grid_spacing:
        try:
            spacing = abs(float(value))
        except (TypeError, ValueError):
            continue
        if math.isfinite(spacing) and spacing > 0.0:
            spacings.append(spacing)
    if not spacings:
        return None
    quantum = min(spacings) / max(int(subdivisions), 1)
    return min(14, max(0, int(math.ceil(-math.log10(quantum)))))


def _round_report_floats(value: Any, decimal_places: int) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _round_report_floats(item, decimal_places)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_round_report_floats(item, decimal_places) for item in value]
    if isinstance(value, (float, np.floating)):
        rounded = round(float(value), decimal_places)
        return 0.0 if rounded == 0.0 else rounded
    return value


def _compact_json(value: Any, *, decimal_places: Optional[int] = None) -> str:
    safe_value = _json_safe(value)
    if decimal_places is not None:
        safe_value = _round_report_floats(safe_value, decimal_places)
    return json.dumps(safe_value, ensure_ascii=False, separators=(", ", ": "))


__all__ = [
    "build_predominance_verdict",
    "export_predominance_verdict",
    "render_predominance_verdict",
]
