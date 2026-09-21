"""ref_card_cache.py
Filename construction and cache lookup for reference cards.

Reference cards are stored in ``_ref_eq_cards_storage/`` with
metadata-rich filenames encoding metal/ligand/network IDs and T/I
ranges.  Cache lookup matches on IDs only (T/I range may vary).

When the primary pair has been curated by the LC1_2 validator, a short
deterministic ``_patch-<hash>`` tag is appended so that patched and
unpatched cards for the same ``(metal, ligand, eq_net)`` triple do not
collide on disk.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, List, Optional


def fmt_range(vals: List[float]) -> str:
    """Format a list of values as 'min~max' if they differ, else just the value."""
    if not vals:
        return "0"
    lo, hi = min(vals), max(vals)
    if lo == hi:
        return f"{lo:g}"
    return f"{lo:g}~{hi:g}"


def patches_fingerprint(patches: Iterable[dict[str, Any]] | None) -> str:
    """Return a short hex hash of the patch list, or '' if no patches.

    Each patch is reduced to its semantically meaningful fields only
    (``beta_definition_id``, ``operation``/``action``, ``examined_vlm_id``/
    ``vlm_id``, ``chosen_value``) and sorted by ``beta_definition_id`` so
    that two patch lists that differ only in ordering or in irrelevant
    metadata (rationale, node_key) produce the same fingerprint.
    """
    if not patches:
        return ""
    canon: list[tuple] = []
    for p in patches:
        bd = p.get("beta_definition_id")
        op = p.get("operation") or p.get("action")
        vlm = p.get("examined_vlm_id") or p.get("vlm_id")
        cv = p.get("chosen_value")
        canon.append((
            int(bd) if bd is not None else None,
            str(op) if op is not None else None,
            int(vlm) if vlm is not None else None,
            float(cv) if cv is not None else None,
        ))
    canon.sort(key=lambda t: (t[0] is None, t[0]))
    blob = json.dumps(canon, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha1(blob).hexdigest()[:6]


def build_ref_card_filename(
    metal_id: int,
    ligand_id: int,
    eq_net_id: int,
    db_sources: List[str],
    temperature: float,
    ionic_strength: float,
    *,
    t_range: Optional[List[float]] = None,
    i_range: Optional[List[float]] = None,
    patches: Iterable[dict[str, Any]] | None = None,
) -> str:
    """Build a deterministic filename for a reference card.

    When *t_range* / *i_range* are provided (lists of all T/I values across
    all included eq networks), the filename uses the actual range.
    Otherwise falls back to the single T/I value.

    When *patches* is non-empty, a ``_patch-<hash6>`` tag is appended so
    patched and unpatched cards coexist without colliding.

    Example:
        refeqcard_metal_41_ligand_5760_ref_eq_net_86_SRD46_T25.0_I0~0.1
        refeqcard_metal_41_ligand_5760_ref_eq_net_86_SRD46_T25.0_I0~0.1_patch-a1b2c3
    """
    db_tag = "_".join(db_sources)
    t_str = fmt_range(t_range) if t_range else f"{temperature:g}"
    i_str = fmt_range(i_range) if i_range else f"{ionic_strength:g}"
    stem = (
        f"refeqcard_metal_{metal_id}_ligand_{ligand_id}"
        f"_ref_eq_net_{eq_net_id}_{db_tag}"
        f"_T{t_str}_I{i_str}"
    )
    fp = patches_fingerprint(patches)
    if fp:
        stem = f"{stem}_patch-{fp}"
    return stem


def find_existing_ref_card(
    storage_dir: Path,
    metal_id: int,
    ligand_id: int,
    eq_net_id: int,
    *,
    patches: Iterable[dict[str, Any]] | None = None,
) -> Optional[Path]:
    """Look for an existing ref card in *storage_dir*.

    Matches on metal_id, ligand_id, and eq_net_id.  The db_sources tag
    and T/I range are allowed to vary (they depend on auto-fetched data).

    When *patches* is non-empty, only files carrying the matching
    ``_patch-<hash6>`` suffix are considered.  When *patches* is empty,
    only unpatched files (without ``_patch-`` suffix) are returned, so
    a previously-patched card is not silently reused for an unpatched
    request.
    """
    fp = patches_fingerprint(patches)
    if fp:
        pattern = (
            f"refeqcard_metal_{metal_id}_ligand_{ligand_id}"
            f"_ref_eq_net_{eq_net_id}_*_patch-{fp}.md"
        )
        hits = sorted(storage_dir.glob(pattern))
        return hits[0] if hits else None
    pattern = (
        f"refeqcard_metal_{metal_id}_ligand_{ligand_id}"
        f"_ref_eq_net_{eq_net_id}_*.md"
    )
    hits = [p for p in sorted(storage_dir.glob(pattern))
            if "_patch-" not in p.stem]
    return hits[0] if hits else None
