"""ref_eq_SRD46_cards_builder.py
Build or load cached per-metal-ligand-pair reference equilibrium cards.

Each ref card is a full free-energy MD card (Sections 1-6, include=true)
for **one** metal–ligand pair, auto-augmented with:
  • metal-hydroxide species from SRD-46 (e.g. Cu(OH)⁺, Cu(OH)₂, …)
  • ligand protonation (pKa) species from SRD-46 (e.g. HL, H₂L, …)
  • (optionally) Pourbaix Atlas species for the metal element

Cards are stored in ``_ref_eq_cards_storage/`` with metadata-rich filenames
and companion JSONs.

This is the **thin orchestrator** — all heavy logic lives in the
``ref_eq_SRD46_cards_builder_helpers/`` sub-package.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Collection, List, Mapping, Optional, Tuple, Union

# ── path bootstrapping ──────────────────────────────────────────
_THIS = Path(__file__).absolute()
_CALC_ROOT = _THIS.parents[2]                       # LC2_free_energy_card_building/
_PIPELINE_ROOT = _THIS.parents[3]                   # NIST_SRD46_calc_input_building_agentic_pipeline/
_WORKSPACE_ROOT = _THIS.parents[6]                  # SRD46_research_agent/
_DEFAULT_STORAGE = _CALC_ROOT / "_ref_eq_cards_storage"

for _p in (_WORKSPACE_ROOT, _CALC_ROOT, _PIPELINE_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


def _extended_windows_path(path: Path) -> str:
    """Return an import-search path that bypasses legacy MAX_PATH."""

    value = os.path.abspath(os.fspath(path))
    if os.name != "nt" or value.startswith("\\\\?\\"):
        return value
    if value.startswith("\\\\"):
        return "\\\\?\\UNC\\" + value[2:]
    return "\\\\?\\" + value


# ``json_cards_builder_helpers`` is deep enough to cross MAX_PATH in the
# mapped Windows workspace.  A top-level fallback rooted at the extended
# builder directory lets Python resolve the same package without renaming or
# duplicating it.  Normal platforms continue to use package-relative imports.
_EXTENDED_BUILDER_DIR = _extended_windows_path(_THIS.parent)
if os.name == "nt" and _EXTENDED_BUILDER_DIR not in sys.path:
    sys.path.insert(0, _EXTENDED_BUILDER_DIR)

# ── helper imports ─────────────────────────────────────────────
try:
    from .json_cards_builder_helpers.auto_fetch import (
        auto_fetch_hydroxide_networks,
        auto_fetch_pka_networks,
        auto_fetch_primary_network,
        auto_fetch_valence_networks,
        HYDROXIDE_LIGAND_ID,
        PROTON_METAL_ID,
    )
    from .json_cards_builder_helpers.ref_card_cache import (
        build_ref_card_filename,
        find_existing_ref_card,
    )
    from .json_cards_builder_helpers.single_pair_pipeline import (
        parse_id,
        extract_eq_net_id,
        write_eq_map_artefacts,
        render_card_from_eq_map_files,
        write_text_long,
        read_text_long,
    )
except (ImportError, ModuleNotFoundError) as _relative_helper_error:
    if os.name != "nt":
        raise
    from json_cards_builder_helpers.auto_fetch import (
        auto_fetch_hydroxide_networks,
        auto_fetch_pka_networks,
        auto_fetch_primary_network,
        auto_fetch_valence_networks,
        HYDROXIDE_LIGAND_ID,
        PROTON_METAL_ID,
    )
    from json_cards_builder_helpers.ref_card_cache import (
        build_ref_card_filename,
        find_existing_ref_card,
    )
    from json_cards_builder_helpers.single_pair_pipeline import (
        parse_id,
        extract_eq_net_id,
        write_eq_map_artefacts,
        render_card_from_eq_map_files,
        write_text_long,
        read_text_long,
    )

# ── free-energy MD card emission (JSON → FreeEnergyReport → MD) ──
from card_management_helpers.ref_eq_json_cards_reader import (
    parse_ref_eq_json_card,
)
from LC2_free_energy_card_building.LC2_1_card_initializer.ref_eq_SRD46_md_cards_builder.ref_eq_free_energy_md_card_generation import (
    generate_free_energy_card_md,
)


def _cache_has_undefined_reference_totals(card_json: dict) -> bool:
    """Return true only for reference cards using the current total sentinel.

    Pre-sentinel cache entries embedded 1 mM/10 mM template concentrations.
    They are invalidated rather than allowed to masquerade as declarations.
    """
    components = card_json.get("components") if isinstance(card_json, dict) else None
    if not isinstance(components, dict) or not components:
        return False
    saw_solver_component = False
    for name, info in components.items():
        if not isinstance(info, dict) or name in {"H+", "OH-"}:
            continue
        saw_solver_component = True
        if info.get("total") != "Not defined":
            return False
    return saw_solver_component


def _ligand_component_contract_sha256(
    contracts: Optional[Mapping[int, Mapping[str, Any]]],
) -> Optional[str]:
    """Hash the exact catalog-owned free-ligand declarations for a card."""

    if not contracts:
        return None
    payload = [
        {
            "ligand_id": int(ligand_id),
            "free_ligand_state": contract,
        }
        for ligand_id, contract in sorted(
            contracts.items(), key=lambda item: int(item[0])
        )
    ]
    return hashlib.sha256(json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")).hexdigest()


def _ligand_component_contract_receipts(
    contracts: Optional[Mapping[int, Mapping[str, Any]]],
) -> dict[str, object]:
    """Return the provenance receipts surfaced in LC2 audit artefacts."""

    return {
        f"ligand_{int(ligand_id)}": contract.get("receipt_sha256")
        for ligand_id, contract in sorted(
            (contracts or {}).items(), key=lambda item: int(item[0])
        )
    }


# ═══════════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════════

def build_or_load_ref_pair_eq_map(
    pair_entry: dict,
    storage_dir: Union[str, Path] = None,
    eq_map_dir: Union[str, Path, None] = None,
    *,
    dependency_networks: Optional[List[dict]] = None,
    auto_hydroxide: bool = True,
    auto_pka: bool = True,
) -> dict:
    """Resolve IDs + augment networks + persist eq-map JSONs.

    This is the **first half** of :func:`build_or_load_ref_card`.  It
    stops *before* the equation builder runs so the L2_1_1 validator
    can inspect / patch the selected_map JSON before card rendering.

    Parameters
    ----------
    pair_entry : dict
        Same shape as for :func:`build_or_load_ref_card`.
    storage_dir : Path
        Reserved for cache lookups (not used yet by this function;
        kept for symmetry).
    eq_map_dir : Path | None
        Where to persist the eq-map JSONs.  Defaults to
        ``_DEFAULT_STORAGE / "_eq_maps"``.
    auto_hydroxide, auto_pka
        Mirror :func:`build_or_load_ref_card`.

    Returns
    -------
    dict with keys:
      ``metal_id``, ``ligand_id``, ``temperature``, ``ionic_strength``,
      ``eq_net_id``, ``system_name``,
      ``ids_json_path``, ``maps_json_path``, ``augmented_networks_path``,
      ``augmented_networks`` (in-memory list, for downstream screen),
      ``pair_key`` (``"metal_<m>_ligand_<l>"``),
      ``eq_map_dir`` (str).
    """
    if storage_dir is None:
        storage_dir = _DEFAULT_STORAGE
    storage_dir = Path(storage_dir)
    if eq_map_dir is None:
        eq_map_dir = storage_dir / "_eq_maps"
    eq_map_dir = Path(eq_map_dir)

    metal_id = parse_id(pair_entry["metal_id"])
    ligand_id = parse_id(pair_entry["ligand_id"])
    temperature = float(pair_entry.get("temperature", 25.0))
    ionic_strength = float(pair_entry.get("ionic_strength", 0.1))

    if not pair_entry.get("eq_network"):
        primary = auto_fetch_primary_network(
            metal_id, ligand_id, temperature, ionic_strength,
        )
        if primary is None:
            raise LookupError(
                f"No eq_network found in SRD-46 for "
                f"metal_id={metal_id} + ligand_id={ligand_id}"
            )
        pair_entry = {**pair_entry, "eq_network": primary["eq_network"]}

    eq_net_id = extract_eq_net_id(pair_entry["eq_network"])
    pair_key = f"metal_{metal_id}_ligand_{ligand_id}"
    # Patches from LC1_2: the validator may have attached
    # ``patch_notes.patches`` to the primary network entry.  They flow
    # through extract_maps_json() -> the persisted maps JSON as
    # ``vlm_overrides`` on that pair.
    primary_patches = list(
        (pair_entry.get("patch_notes") or {}).get("patches") or []
    )
    # ── Build augmented network list ───────────────────────────
    augmented: List[dict] = [pair_entry]
    augmented.extend(list(dependency_networks or ()))

    if auto_hydroxide and ligand_id != HYDROXIDE_LIGAND_ID:
        oh_nets = auto_fetch_hydroxide_networks(
            metal_id, temperature, ionic_strength,
        )
        augmented.extend(oh_nets)

    if auto_pka and ligand_id != HYDROXIDE_LIGAND_ID and metal_id != PROTON_METAL_ID:
        pka_nets = auto_fetch_pka_networks(
            ligand_id, temperature, ionic_strength,
        )
        augmented.extend(pka_nets)

    # A validated support pair can also be returned by an optional auto-fetch.
    # Keep the authoritative first occurrence and avoid materializing the same
    # network twice in one dependency-complete card.
    unique_augmented: List[dict] = []
    seen_networks: set[tuple[int, int, int]] = set()
    for entry in augmented:
        identity = (
            parse_id(entry["metal_id"]),
            parse_id(entry["ligand_id"]),
            extract_eq_net_id(entry["eq_network"]),
        )
        if identity in seen_networks:
            continue
        seen_networks.add(identity)
        unique_augmented.append(entry)
    augmented = unique_augmented

    # ── Persist draft eq-map artefacts (version v0) ────────────
    pair_eq_map_dir = eq_map_dir / pair_key
    paths = write_eq_map_artefacts(augmented, pair_eq_map_dir, file_stem="v0")

    return {
        "metal_id":               metal_id,
        "ligand_id":              ligand_id,
        "temperature":            temperature,
        "ionic_strength":         ionic_strength,
        "eq_net_id":              eq_net_id,
        "system_name":            f"metal_{metal_id} + ligand_{ligand_id}",
        "pair_key":               pair_key,
        "eq_map_dir":             str(pair_eq_map_dir),
        "ids_json_path":          paths["ids_json_path"],
        "maps_json_path":         paths["maps_json_path"],
        "augmented_networks_path": paths["augmented_networks_path"],
        "augmented_networks":     augmented,
        "patches":                primary_patches,
    }


def render_ref_pair_card_from_eq_map(
    eq_map_meta: dict,
    storage_dir: Union[str, Path] = None,
    *,
    atlas_merge: bool = False,
    ligand_component_contracts: Optional[
        Mapping[int, Mapping[str, Any]]
    ] = None,
) -> Tuple[str, dict, Path]:
    """Render the ref-eq card (JSON + free-energy MD) from an eq-map.

    Reads ``ids_json_path`` + ``maps_json_path`` from ``eq_map_meta``,
    builds the ref-eq card JSON, computes the free-energy network, and
    persists BOTH a ``.json`` card and a companion ``.md`` free-energy
    card into ``storage_dir`` under the same filename stem.

    Returns ``(md_text, card_json, md_path)``.
    """
    if storage_dir is None:
        storage_dir = _DEFAULT_STORAGE
    storage_dir = Path(storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)

    card_json = render_card_from_eq_map_files(
        ids_json_path=eq_map_meta["ids_json_path"],
        maps_json_path=eq_map_meta["maps_json_path"],
        temperature=eq_map_meta["temperature"],
        ionic_strength=eq_map_meta["ionic_strength"],
        system_name=eq_map_meta["system_name"],
        **({
            "ligand_component_contracts": ligand_component_contracts,
        } if ligand_component_contracts else {}),
    )

    db_sources = ["SRD46"]
    if atlas_merge:
        db_sources.append("PAtlas")

    # Collect per-equilibrium T / I from card_json for filename ranges.
    t_seen: set = set()
    i_seen: set = set()
    equations = card_json.get("equations") or {}
    if isinstance(equations, dict):
        sys_entries = equations.values()
    elif isinstance(equations, list):
        sys_entries = equations
    else:
        sys_entries = []
    for sys_entry in sys_entries:
        if not isinstance(sys_entry, dict):
            continue
        for eq in sys_entry.get("equilibria") or []:
            t_v = eq.get("data_source_temperature")
            i_v = eq.get("data_source_ionic_strength")
            if t_v is not None:
                t_seen.add(t_v)
            if i_v is not None:
                i_seen.add(i_v)
    t_vals = sorted(t_seen) if t_seen else [eq_map_meta["temperature"]]
    i_vals = sorted(i_seen) if i_seen else [eq_map_meta["ionic_strength"]]

    stem = build_ref_card_filename(
        eq_map_meta["metal_id"],
        eq_map_meta["ligand_id"],
        eq_map_meta["eq_net_id"],
        db_sources,
        eq_map_meta["temperature"],
        eq_map_meta["ionic_strength"],
        t_range=t_vals,
        i_range=i_vals,
        patches=eq_map_meta.get("patches"),
    )
    component_contract_sha256 = _ligand_component_contract_sha256(
        ligand_component_contracts
    )
    if component_contract_sha256 is not None:
        # The historical cache filename does not know about catalog-owned
        # component metadata.  A digest suffix prevents two contracts for the
        # same SRD pair from sharing or overwriting a card artefact.
        stem = f"{stem}_component-{component_contract_sha256[:16]}"
    json_path = storage_dir / f"{stem}.json"
    write_text_long(
        json_path,
        json.dumps(card_json, indent=2, ensure_ascii=False),
    )

    # ── Free-energy MD card (downstream consumes the .md) ─────
    report = parse_ref_eq_json_card(card_json)
    md_text = generate_free_energy_card_md(
        report, system_name=eq_map_meta["system_name"],
    )
    md_path = storage_dir / f"{stem}.md"
    write_text_long(md_path, md_text)
    return md_text, card_json, md_path


def build_or_load_ref_card(
    pair_entry: dict,
    storage_dir: Union[str, Path] = None,
    *,
    dependency_networks: Optional[List[dict]] = None,
    auto_hydroxide: bool = True,
    auto_pka: bool = True,
    atlas_merge: bool = False,
    ligand_component_contracts: Optional[
        Mapping[int, Mapping[str, Any]]
    ] = None,
) -> Tuple[str, dict, Path]:
    """Build or load a cached ref-eq free-energy card for one pair.

    Emits both a ``.json`` card and a companion ``.md`` free-energy
    card; downstream consumers read the ``.md``.

    Returns
    -------
    (md_text, card_json, md_path)
    """
    if storage_dir is None:
        storage_dir = _DEFAULT_STORAGE
    storage_dir = Path(storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)

    metal_id = parse_id(pair_entry["metal_id"])
    ligand_id = parse_id(pair_entry["ligand_id"])
    temperature = float(pair_entry.get("temperature", 25.0))
    ionic_strength = float(pair_entry.get("ionic_strength", 0.1))

    # Auto-discover the primary eq_network when the caller did not
    # supply one (the L1 card-assembler dispatcher does this -- it only
    # knows the metal/ligand IDs from the chemical_system).
    if not pair_entry.get("eq_network"):
        primary = auto_fetch_primary_network(
            metal_id, ligand_id, temperature, ionic_strength,
        )
        if primary is None:
            raise LookupError(
                f"No eq_network found in SRD-46 for "
                f"metal_id={metal_id} + ligand_id={ligand_id}"
            )
        pair_entry = {**pair_entry, "eq_network": primary["eq_network"]}

    eq_net_id = extract_eq_net_id(pair_entry["eq_network"])

    primary_patches = list(
        (pair_entry.get("patch_notes") or {}).get("patches") or []
    )

    # ── Check cache (.md free-energy card) ──────────────────
    existing = None
    if not dependency_networks and not ligand_component_contracts:
        existing = find_existing_ref_card(
            storage_dir, metal_id, ligand_id, eq_net_id,
            patches=primary_patches,
        )
    if existing is not None:
        md_text = read_text_long(existing)
        json_sidecar = existing.with_suffix(".json")
        card_json = (
            json.loads(read_text_long(json_sidecar))
            if json_sidecar.exists() else {}
        )
        if _cache_has_undefined_reference_totals(card_json):
            return md_text, card_json, existing
        # Legacy cached reference cards carried implicit template totals.
        # Fall through and regenerate the same cache key with visible
        # ``Not defined`` sentinels.

    # ── Build eq-map (stage A) then render card (stage B) ──────
    eq_map_meta = build_or_load_ref_pair_eq_map(
        pair_entry,
        storage_dir=storage_dir,
        dependency_networks=dependency_networks,
        auto_hydroxide=auto_hydroxide,
        auto_pka=auto_pka,
    )
    return render_ref_pair_card_from_eq_map(
        eq_map_meta,
        storage_dir=storage_dir,
        atlas_merge=atlas_merge,
        **({
            "ligand_component_contracts": ligand_component_contracts,
        } if ligand_component_contracts else {}),
    )


def build_all_ref_cards(
    input_json_path: Union[str, Path],
    storage_dir: Union[str, Path] = None,
    *,
    auto_hydroxide: bool = True,
    auto_pka: bool = True,
    auto_valence: bool = True,
    atlas_merge: bool = False,
    ligand_component_contracts: Optional[
        Mapping[int, Mapping[str, Any]]
    ] = None,
) -> List[Path]:
    """Build ref cards for every pair in an input JSON.

    Reads the ``equilibrium_networks`` list, expands with valence
    siblings (all metal species of the same element), then calls
    :func:`build_or_load_ref_card` for each pair.

    Parameters
    ----------
    auto_valence : bool
        Auto-discover sibling metal valences for each element and
        build ref cards for every (sibling_metal, ligand) pair that
        has SRD-46 data.  E.g. Cu²⁺+glycine → also Cu⁺+glycine.

    Returns list of ``.md`` file paths (one per pair).
    """
    input_json_path = Path(input_json_path)
    test_input = json.loads(input_json_path.read_text(encoding="utf-8"))
    networks = test_input.get("equilibrium_networks", [])

    # ── Expand with valence siblings ──────────────────────────
    expanded: List[dict] = list(networks)
    if auto_valence:
        seen_pairs: set = set()
        for net in networks:
            mid = parse_id(net["metal_id"])
            lid = parse_id(net["ligand_id"])
            seen_pairs.add((mid, lid))

        for net in list(networks):
            mid = parse_id(net["metal_id"])
            lid = parse_id(net["ligand_id"])
            temperature = float(net.get("temperature", 25.0))
            ionic_strength = float(net.get("ionic_strength", 0.1))

            valence_nets = auto_fetch_valence_networks(
                mid, lid, temperature, ionic_strength,
            )
            for vn in valence_nets:
                vn_mid = parse_id(vn["metal_id"])
                vn_lid = parse_id(vn["ligand_id"])
                if (vn_mid, vn_lid) not in seen_pairs:
                    expanded.append(vn)
                    seen_pairs.add((vn_mid, vn_lid))

    # ── Build ref cards for each pair ─────────────────────────
    paths: List[Path] = []
    for pair_entry in expanded:
        _md, _card, md_path = build_or_load_ref_card(
            pair_entry,
            storage_dir=storage_dir,
            **({
                "ligand_component_contracts": ligand_component_contracts,
            } if ligand_component_contracts else {}),
            auto_hydroxide=auto_hydroxide,
            auto_pka=auto_pka,
            atlas_merge=atlas_merge,
        )
        paths.append(md_path)

    return paths


# ═══════════════════════════════════════════════════════════════════
#  LC1_2 → LC2_1 entry point
# ═══════════════════════════════════════════════════════════════════

def _validate_support_handoff(
    *,
    support_eq_map_path: Union[str, Path, None],
    expected_support_session_id: Optional[str],
    expected_support_eq_map_sha256: Optional[str],
    session_working_map_path: Union[str, Path, None],
    expected_session_working_map_sha256: Optional[str],
) -> None:
    """Require both validated LC1_3 publications on every support call."""

    enabled_receipts = (
        expected_support_session_id,
        expected_support_eq_map_sha256,
        session_working_map_path,
        expected_session_working_map_sha256,
    )
    if support_eq_map_path is None:
        if any(value is not None for value in enabled_receipts):
            raise ValueError(
                "enabled support receipts require support_eq_map_path"
            )
        return
    if not str(support_eq_map_path).strip():
        raise ValueError("support_eq_map_path must be a nonempty path")
    if not isinstance(expected_support_session_id, str) or not (
        expected_support_session_id.strip()
    ):
        raise ValueError(
            "support_eq_map_path requires expected_support_session_id"
        )
    if re.fullmatch(
        r"[0-9a-f]{64}", str(expected_support_eq_map_sha256)
    ) is None:
        raise ValueError(
            "support_eq_map_path requires an exact lowercase "
            "expected_support_eq_map_sha256"
        )
    if session_working_map_path is None or not str(
        session_working_map_path
    ).strip():
        raise ValueError(
            "support_eq_map_path requires session_working_map_path"
        )
    if re.fullmatch(
        r"[0-9a-f]{64}", str(expected_session_working_map_sha256)
    ) is None:
        raise ValueError(
            "support_eq_map_path requires an exact lowercase "
            "expected_session_working_map_sha256"
        )

def _validated_dependency_networks(
    target: dict,
    system_networks: Collection[dict],
) -> List[dict]:
    """Return already-validated water/ligand prerequisites for *target*.

    LC1 emits H+/ligand protonation and metal/OH- hydrolysis as independent
    auditable pairs.  A metal/ligand reaction may nevertheless use formulas
    established by those pairs (for example Fe + HCitrate -> FeHCitrate).
    Materialize those selected pairs in the target's calculation card so the
    formula graph is resolved in one shared registry.  This does not fetch or
    select new chemistry; it propagates only networks already present in the
    authoritative LC1 card, including their reviewed patches.
    """
    target_mid = parse_id(target["metal_id"])
    target_lid = parse_id(target["ligand_id"])
    wanted: set[tuple[int, int]] = set()
    if target_lid != HYDROXIDE_LIGAND_ID:
        wanted.add((PROTON_METAL_ID, target_lid))
    if target_mid != PROTON_METAL_ID:
        wanted.add((target_mid, HYDROXIDE_LIGAND_ID))
    wanted.discard((target_mid, target_lid))

    dependencies: List[dict] = []
    seen: set[tuple[int, int, int]] = set()
    for entry in system_networks:
        pair = (parse_id(entry["metal_id"]), parse_id(entry["ligand_id"]))
        if pair not in wanted or not entry.get("eq_network"):
            continue
        identity = (*pair, extract_eq_net_id(entry["eq_network"]))
        if identity in seen:
            continue
        seen.add(identity)
        dependencies.append(entry)
    return dependencies


def build_ref_cards_from_lc1_2_card(
    lc1_2_eqmap_card_path: Union[str, Path],
    storage_dir: Union[str, Path] = None,
    *,
    auto_hydroxide: bool = True,
    auto_pka: bool = True,
    atlas_merge: bool = False,
    support_eq_map_path: Union[str, Path, None] = None,
    expected_support_session_id: Optional[str] = None,
    expected_support_eq_map_sha256: Optional[str] = None,
    session_working_map_path: Union[str, Path, None] = None,
    expected_session_working_map_sha256: Optional[str] = None,
    allowed_system_pairs: Optional[Collection[tuple[int, int]]] = None,
    system_catalog_sha256: Optional[str] = None,
    ligand_component_contracts: Optional[
        Mapping[int, Mapping[str, Any]]
    ] = None,
) -> List[Path]:
    """Build ref cards directly from a LC1_2 ``lc1_2_eqmap_card.json``.

    Each entry in ``equilibrium_networks`` already carries the validated
    primary network plus its ``patch_notes.patches`` (possibly empty).
    The patches ride along with the pair entry into
    :func:`build_or_load_ref_card`, which extracts them, threads them
    into the cache fingerprint, and persists them as ``vlm_overrides``
    in the per-pair maps JSON before the equation builder runs.

    No valence-sibling expansion is performed here: LC1_2 has already
    chosen the canonical set of (metal, ligand, eq_network) triples for
    this prompt.  Auto-hydroxide and auto-pKa fetches still apply per
    pair (those auxiliary networks are not validated by LC1_2 yet, so
    they enter the card unpatched).
    """
    lc1_2_eqmap_card_path = Path(lc1_2_eqmap_card_path)
    _validate_support_handoff(
        support_eq_map_path=support_eq_map_path,
        expected_support_session_id=expected_support_session_id,
        expected_support_eq_map_sha256=expected_support_eq_map_sha256,
        session_working_map_path=session_working_map_path,
        expected_session_working_map_sha256=(
            expected_session_working_map_sha256
        ),
    )

    # Literal legacy fast path.  In particular, do not import the optional
    # compiler, inspect a conventional sidecar filename, alter cache keys, or
    # add any enabled-only files when the handoff is absent.
    if support_eq_map_path is None:
        card = json.loads(lc1_2_eqmap_card_path.read_text(encoding="utf-8"))
        networks = card.get("equilibrium_networks", [])
        paths: List[Path] = []
        for pair_entry in networks:
            dependencies = _validated_dependency_networks(
                pair_entry, networks,
            )
            _md, _card, md_path = build_or_load_ref_card(
                pair_entry,
                storage_dir=storage_dir,
                **({
                    "ligand_component_contracts": ligand_component_contracts,
                } if ligand_component_contracts else {}),
                **({"dependency_networks": dependencies} if dependencies else {}),
                auto_hydroxide=auto_hydroxide,
                auto_pka=auto_pka,
                atlas_merge=atlas_merge,
            )
            paths.append(md_path)
        return paths

    return _build_ref_cards_with_native_support_eq_map(
        lc1_2_eqmap_card_path,
        support_eq_map_path=Path(support_eq_map_path),
        expected_support_session_id=str(expected_support_session_id),
        expected_support_eq_map_sha256=str(expected_support_eq_map_sha256),
        session_working_map_path=Path(session_working_map_path),
        expected_session_working_map_sha256=str(
            expected_session_working_map_sha256
        ),
        allowed_system_pairs=allowed_system_pairs,
        system_catalog_sha256=system_catalog_sha256,
        ligand_component_contracts=ligand_component_contracts,
        storage_dir=storage_dir,
        auto_hydroxide=auto_hydroxide,
        auto_pka=auto_pka,
        atlas_merge=atlas_merge,
    )


def _support_card_stem(
    *,
    metal_id: int,
    ligand_id: int,
    eq_net_id: Optional[int],
    temperature_C: float,
    ionic_strength_M: float,
    fingerprint: str,
) -> str:
    network = f"ref_eq_net_{eq_net_id}" if eq_net_id is not None else "support_only"
    t_value = f"{temperature_C:g}".replace("-", "m").replace(".", "p")
    i_value = f"{ionic_strength_M:g}".replace("-", "m").replace(".", "p")
    return (
        f"refeqcard_metal_{metal_id}_ligand_{ligand_id}_{network}_"
        f"support-{fingerprint[:16]}_T{t_value}_I{i_value}"
    )


def _render_working_support_card(
    *,
    eq_map_meta: dict,
    storage_dir: Path,
    support_sha256: str,
    support_session_id: str,
    support_input_base_eq_map_sha256: str,
    reviewed_base_eq_map_sha256: str,
    system_catalog_sha256: Optional[str],
    system_catalog_pair_set_sha256: str,
    ligand_component_contracts: Optional[
        Mapping[int, Mapping[str, Any]]
    ] = None,
) -> Tuple[Path, dict]:
    """Render the ordinary equation/free-energy pipeline from a working map."""

    card_json = render_card_from_eq_map_files(
        ids_json_path=eq_map_meta["ids_json_path"],
        maps_json_path=eq_map_meta["maps_json_path"],
        temperature=eq_map_meta["temperature"],
        ionic_strength=eq_map_meta["ionic_strength"],
        system_name=eq_map_meta["system_name"],
        **({
            "ligand_component_contracts": ligand_component_contracts,
        } if ligand_component_contracts else {}),
    )
    fingerprint_record = {
        "support_input_base_eq_map_sha256": support_input_base_eq_map_sha256,
        "reviewed_base_eq_map_sha256": reviewed_base_eq_map_sha256,
        "support_eq_map_sha256": support_sha256,
        "support_session_id": support_session_id,
        "system_catalog_sha256": system_catalog_sha256,
        "system_catalog_pair_set_sha256": system_catalog_pair_set_sha256,
        "maps_json_sha256": hashlib.sha256(
            read_text_long(eq_map_meta["maps_json_path"]).encode("utf-8")
        ).hexdigest(),
        "compiler_version": "lc2-native-support-eq-map/v1",
        "temperature_C": float(eq_map_meta["temperature"]),
        "ionic_strength_M": float(eq_map_meta["ionic_strength"]),
        "canonical_reference_policy": "free-energy-rulebook/current",
    }
    component_contract_sha256 = _ligand_component_contract_sha256(
        ligand_component_contracts
    )
    if component_contract_sha256 is not None:
        fingerprint_record["ligand_component_contract_sha256"] = (
            component_contract_sha256
        )
    fingerprint_payload = json.dumps(
        fingerprint_record, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    fingerprint = hashlib.sha256(fingerprint_payload).hexdigest()
    stem = _support_card_stem(
        metal_id=eq_map_meta["metal_id"],
        ligand_id=eq_map_meta["ligand_id"],
        eq_net_id=eq_map_meta.get("eq_net_id"),
        temperature_C=eq_map_meta["temperature"],
        ionic_strength_M=eq_map_meta["ionic_strength"],
        fingerprint=fingerprint,
    )
    json_path = storage_dir / f"{stem}.json"
    md_path = storage_dir / f"{stem}.md"
    audit_path = storage_dir / f"{stem}.support_audit.json"
    write_text_long(json_path, json.dumps(card_json, indent=2, ensure_ascii=False))
    entries = [
        equilibrium
        for blocks in (card_json.get("equations") or {}).values()
        if isinstance(blocks, list)
        for block in blocks
        for equilibrium in block.get("equilibria", [])
    ]
    estimated_entries = [
        entry for entry in entries
        if (entry.get("reference") or {}).get("source")
        == "SRD46 query estimated values"
    ]
    report = parse_ref_eq_json_card(card_json)
    from LC2_free_energy_card_building.LC2_1_card_initializer.native_support_eq_map import (
        decorate_report_with_estimated_provenance,
    )
    decorate_report_with_estimated_provenance(report, estimated_entries)
    md_text = generate_free_energy_card_md(
        report,
        system_name=eq_map_meta["system_name"],
    )
    write_text_long(md_path, md_text)
    audit = {
        "compiler_version": "lc2-native-support-eq-map/v1",
        "pair": {
            "metal_id": eq_map_meta["metal_id"],
            "ligand_id": eq_map_meta["ligand_id"],
        },
        "selected_network_ids": [
            network_id
            for pair in json.loads(read_text_long(eq_map_meta["maps_json_path"])).get("pairs", [])
            if int(pair["metal_id"]) == int(eq_map_meta["metal_id"])
            and int(pair["ligand_id"]) == int(eq_map_meta["ligand_id"])
            for network_id in pair.get("selected_network_ids", [])
        ],
        "n_materialized_entries": len(entries),
        "n_materialized_estimated_entries": len(estimated_entries),
        "estimated_source_database_IDs": sorted(
            str(entry["reference"]["source_database_ID"])
            for entry in estimated_entries
        ),
        "support_eq_map_sha256": support_sha256,
        "support_session_id": support_session_id,
        "support_input_base_eq_map_sha256": support_input_base_eq_map_sha256,
        "reviewed_base_eq_map_sha256": reviewed_base_eq_map_sha256,
        "system_catalog_sha256": system_catalog_sha256,
        "system_catalog_pair_set_sha256": system_catalog_pair_set_sha256,
        "ligand_component_contract_sha256": component_contract_sha256,
        "ligand_component_contract_ids": [
            f"ligand_{int(ligand_id)}"
            for ligand_id in sorted(
                ligand_component_contracts or {}, key=int
            )
        ],
        "ligand_component_contract_receipts": (
            _ligand_component_contract_receipts(
                ligand_component_contracts
            )
        ),
        "working_maps_json_path": str(eq_map_meta["maps_json_path"]),
        "compiled_card_sha256": hashlib.sha256(json.dumps(
            card_json,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")).hexdigest(),
        "compiled_json_path": str(json_path),
        "compiled_md_path": str(md_path),
        "fingerprint": fingerprint,
    }
    write_text_long(audit_path, json.dumps(audit, indent=2, ensure_ascii=False))
    return md_path, audit


def _build_ref_cards_with_native_support_eq_map(
    lc1_2_eqmap_card_path: Path,
    *,
    support_eq_map_path: Path,
    expected_support_session_id: str,
    expected_support_eq_map_sha256: str,
    session_working_map_path: Path,
    expected_session_working_map_sha256: str,
    allowed_system_pairs: Optional[Collection[tuple[int, int]]],
    system_catalog_sha256: Optional[str],
    ligand_component_contracts: Optional[
        Mapping[int, Mapping[str, Any]]
    ],
    storage_dir: Union[str, Path, None],
    auto_hydroxide: bool,
    auto_pka: bool,
    atlas_merge: bool,
) -> List[Path]:
    """Enabled-only native eq-map compiler; never touches shared storage."""

    if storage_dir is None:
        raise ValueError("support_eq_map_path requires an explicit session-local storage_dir")
    storage = Path(storage_dir).resolve()
    if storage == _DEFAULT_STORAGE.resolve() or _DEFAULT_STORAGE.resolve() in storage.parents:
        raise ValueError("Estimated support cards cannot be written to _ref_eq_cards_storage")
    if allowed_system_pairs is None:
        raise ValueError(
            "support_eq_map_path requires the active system catalog pair set"
        )
    storage.mkdir(parents=True, exist_ok=True)

    from LC2_free_energy_card_building.LC2_1_card_initializer.native_support_eq_map import (
        amend_measured_working_map,
        build_support_only_working_map,
        load_native_support_eq_map,
        load_session_working_map,
        select_rows_at_conditions,
    )

    base_card = json.loads(read_text_long(lc1_2_eqmap_card_path))
    support = load_native_support_eq_map(
        support_eq_map_path,
        base_eq_map_card=base_card,
        allowed_system_pairs=allowed_system_pairs,
        expected_support_session_id=expected_support_session_id,
        expected_support_eq_map_sha256=expected_support_eq_map_sha256,
    )
    session_working_map = load_session_working_map(
        session_working_map_path,
        expected_session_working_map_sha256=(
            expected_session_working_map_sha256
        ),
        support_rows_by_pair=support.rows_by_pair,
        base_eq_map_card=base_card,
        allowed_system_pairs=allowed_system_pairs,
    )
    working_rows_by_pair = session_working_map.rows_by_pair
    measured_networks = list(base_card.get("equilibrium_networks", []) or [])
    measured_pairs = {
        (parse_id(entry["metal_id"]), parse_id(entry["ligand_id"]))
        for entry in measured_networks
    }
    output_paths: List[Path] = []
    audits: List[dict] = []

    # Preserve authoritative input order.  Native support rows are inserted
    # into the selected map before the ordinary equation builder runs.
    for pair_entry in measured_networks:
        metal_id = parse_id(pair_entry["metal_id"])
        ligand_id = parse_id(pair_entry["ligand_id"])
        pair = (metal_id, ligand_id)
        dependencies = _validated_dependency_networks(
            pair_entry, measured_networks,
        )
        support_rows = list(working_rows_by_pair.get(pair, ()))
        if not support_rows:
            _md, _card, md_path = build_or_load_ref_card(
                pair_entry,
                storage_dir=storage,
                **({
                    "ligand_component_contracts": ligand_component_contracts,
                } if ligand_component_contracts else {}),
                **({"dependency_networks": dependencies} if dependencies else {}),
                auto_hydroxide=auto_hydroxide,
                auto_pka=auto_pka,
                atlas_merge=atlas_merge,
            )
            output_paths.append(md_path)
            continue

        temperature = float(pair_entry.get("temperature", 25.0))
        ionic_strength = float(pair_entry.get("ionic_strength", 0.1))
        selected_support_rows = select_rows_at_conditions(
            support_rows,
            temperature=temperature,
            ionic_strength=ionic_strength,
        )
        eq_meta = build_or_load_ref_pair_eq_map(
            pair_entry,
            storage_dir=storage,
            eq_map_dir=storage / "_working_eq_maps",
            **({"dependency_networks": dependencies} if dependencies else {}),
            auto_hydroxide=auto_hydroxide,
            auto_pka=auto_pka,
        )
        working_maps_path = Path(eq_meta["eq_map_dir"]) / "maps_with_estimates.json"
        eq_meta["maps_json_path"] = amend_measured_working_map(
            maps_json_path=eq_meta["maps_json_path"],
            metal_id=metal_id,
            ligand_id=ligand_id,
            estimated_rows=selected_support_rows,
            output_path=working_maps_path,
        )
        md_path, audit = _render_working_support_card(
            eq_map_meta=eq_meta,
            storage_dir=storage,
            support_sha256=support.sha256,
            support_session_id=support.session_id,
            support_input_base_eq_map_sha256=support.base_eq_map_sha256,
            reviewed_base_eq_map_sha256=support.reviewed_base_eq_map_sha256,
            system_catalog_sha256=system_catalog_sha256,
            system_catalog_pair_set_sha256=support.system_catalog_pair_set_sha256,
            ligand_component_contracts=ligand_component_contracts,
        )
        audit["n_selected_support_nodes"] = len(selected_support_rows)
        output_paths.append(md_path)
        audits.append(audit)

    # Deterministic support-only tail.  Each condition group gets a working
    # target pair with selected_network_ids=[] and validated session nodes.
    # Any hydroxide/pKa auxiliaries retain only real SRD46 network IDs.
    for pair in sorted(set(working_rows_by_pair) - measured_pairs):
        metal_id, ligand_id = pair
        condition_groups: dict[tuple[float, float], list[dict]] = {}
        for row in working_rows_by_pair[pair]:
            condition_groups.setdefault(
                (float(row["temperature"]), float(row["ionic_strength"])),
                [],
            ).append(row)
        for condition_index, ((temperature, ionic_strength), rows) in enumerate(
            sorted(condition_groups.items())
        ):
            support_target = {
                "metal_id": metal_id,
                "ligand_id": ligand_id,
            }
            auxiliaries: List[dict] = _validated_dependency_networks(
                support_target, measured_networks,
            )
            if auto_hydroxide and ligand_id != HYDROXIDE_LIGAND_ID:
                auxiliaries.extend(auto_fetch_hydroxide_networks(
                    metal_id, temperature, ionic_strength,
                ))
            if (
                auto_pka
                and ligand_id != HYDROXIDE_LIGAND_ID
                and metal_id != PROTON_METAL_ID
            ):
                auxiliaries.extend(auto_fetch_pka_networks(
                    ligand_id, temperature, ionic_strength,
                ))
            pair_dir = (
                storage / "_working_eq_maps" /
                f"metal_{metal_id}_ligand_{ligand_id}" /
                f"condition_{condition_index}"
            )
            paths = build_support_only_working_map(
                metal_id=metal_id,
                ligand_id=ligand_id,
                estimated_rows=list(rows),
                auxiliary_networks=auxiliaries,
                output_dir=pair_dir,
            )
            eq_meta = {
                "metal_id": metal_id,
                "ligand_id": ligand_id,
                "temperature": temperature,
                "ionic_strength": ionic_strength,
                "eq_net_id": None,
                "system_name": f"metal_{metal_id} + ligand_{ligand_id}",
                "pair_key": f"metal_{metal_id}_ligand_{ligand_id}",
                "eq_map_dir": str(pair_dir),
                **paths,
                "patches": [],
            }
            md_path, audit = _render_working_support_card(
                eq_map_meta=eq_meta,
                storage_dir=storage,
                support_sha256=support.sha256,
                support_session_id=support.session_id,
                support_input_base_eq_map_sha256=support.base_eq_map_sha256,
                reviewed_base_eq_map_sha256=support.reviewed_base_eq_map_sha256,
                system_catalog_sha256=system_catalog_sha256,
                system_catalog_pair_set_sha256=support.system_catalog_pair_set_sha256,
                ligand_component_contracts=ligand_component_contracts,
            )
            audit["n_selected_support_nodes"] = len(rows)
            output_paths.append(md_path)
            audits.append(audit)

    selected_support_node_count = sum(
        int(audit.get("n_selected_support_nodes", 0)) for audit in audits
    )
    materialized_estimated_entry_count = sum(
        int(audit.get("n_materialized_estimated_entries", 0))
        for audit in audits
    )
    compile_manifest = {
        "schema_version": "srd46.lc2_1.native_support_compile_manifest/v1",
        "source": "SRD46 query estimated values",
        "authoritative": False,
        "support_eq_map_path": str(support.path),
        "support_eq_map_sha256": support.sha256,
        "support_session_id": support.session_id,
        "expected_support_eq_map_sha256": expected_support_eq_map_sha256,
        "expected_support_session_id": expected_support_session_id,
        "session_working_map_path": str(session_working_map.path),
        "session_working_map_sha256": session_working_map.sha256,
        "expected_session_working_map_sha256": (
            expected_session_working_map_sha256
        ),
        "session_working_map_binding_verified": True,
        "provenance_binding_verified": True,
        "base_eq_map_path": str(lc1_2_eqmap_card_path.resolve()),
        "support_input_base_eq_map_sha256": support.base_eq_map_sha256,
        "reviewed_base_eq_map_sha256": support.reviewed_base_eq_map_sha256,
        "system_catalog_sha256": system_catalog_sha256,
        "system_catalog_pair_set_sha256": support.system_catalog_pair_set_sha256,
        "ligand_component_contract_sha256": (
            _ligand_component_contract_sha256(
                ligand_component_contracts
            )
        ),
        "ligand_component_contract_ids": [
            f"ligand_{int(ligand_id)}"
            for ligand_id in sorted(
                ligand_component_contracts or {}, key=int
            )
        ],
        "ligand_component_contract_receipts": (
            _ligand_component_contract_receipts(
                ligand_component_contracts
            )
        ),
        "allowed_system_pairs": [
            {"metal_id": metal_id, "ligand_id": ligand_id}
            for metal_id, ligand_id in support.allowed_system_pairs
        ],
        "support_node_count": support.node_count,
        "candidate_count": support.node_count,
        "selected_support_node_count": selected_support_node_count,
        "materialized_estimated_entry_count": materialized_estimated_entry_count,
        "card_paths": [str(path) for path in output_paths],
        "pair_audits": audits,
    }
    write_text_long(
        storage / "support_eq_map_compile_manifest.json",
        json.dumps(compile_manifest, indent=2, ensure_ascii=False),
    )
    return output_paths
