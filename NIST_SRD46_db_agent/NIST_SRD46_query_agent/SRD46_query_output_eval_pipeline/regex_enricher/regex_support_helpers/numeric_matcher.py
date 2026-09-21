"""Top-10 closest numeric match finder.

For each numeric value found in an LLM answer, queries ALL measurement
tables across ALL ref_ids from the run (type-agnostic) and returns the
10 closest DB values ranked by absolute distance.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Sequence

from .models import NumericMatch, NumericSpan

log = logging.getLogger("regex_enricher.numeric_matcher")

# ---------------------------------------------------------------------------
# SQL queries for fetching measurements from each table
# ---------------------------------------------------------------------------

# Each tuple: (query, value_column, id_column, id_prefix, detail_template)
# The queries join on ref_ids using IN-clauses built at runtime.
_MEASUREMENT_QUERIES: list[tuple[str, str, str, str, str]] = [
    # Stability constants (log K / log β) via vlm_id
    (
        """SELECT s.constant_value, s.constant_type, s.temperature, s.ionic_strength,
                  c.complex_system_id AS vlm_id, c.metal_id, c.ligand_id
           FROM cards.ligandmetal_stability_measured s
           JOIN cards.ligandmetal_card c ON s.card_id = c.card_id
           WHERE c.complex_system_id IN ({placeholders})""",
        "constant_value",
        "vlm_id",
        "vlm",
        "{constant_type} @ {temperature}°C, I={ionic_strength}",
    ),
    # Stability constants via beta_def_id
    (
        """SELECT s.constant_value, s.constant_type, s.temperature, s.ionic_strength,
                  c.beta_definition_id AS beta_def_id, c.metal_id, c.ligand_id
           FROM cards.ligandmetal_stability_measured s
           JOIN cards.ligandmetal_card c ON s.card_id = c.card_id
           WHERE c.beta_definition_id IN ({placeholders})""",
        "constant_value",
        "beta_def_id",
        "beta_def",
        "{constant_type} @ {temperature}°C, I={ionic_strength}",
    ),
    # Stability constants via metal_id
    (
        """SELECT s.constant_value, s.constant_type, s.temperature, s.ionic_strength,
                  c.complex_system_id AS vlm_id, c.metal_id, c.ligand_id
           FROM cards.ligandmetal_stability_measured s
           JOIN cards.ligandmetal_card c ON s.card_id = c.card_id
           WHERE c.metal_id IN ({placeholders})""",
        "constant_value",
        "metal_id",
        "metal",
        "{constant_type} @ {temperature}°C, I={ionic_strength}",
    ),
    # Stability constants via ligand_id
    (
        """SELECT s.constant_value, s.constant_type, s.temperature, s.ionic_strength,
                  c.complex_system_id AS vlm_id, c.metal_id, c.ligand_id
           FROM cards.ligandmetal_stability_measured s
           JOIN cards.ligandmetal_card c ON s.card_id = c.card_id
           WHERE c.ligand_id IN ({placeholders})""",
        "constant_value",
        "ligand_id",
        "ligand",
        "{constant_type} @ {temperature}°C, I={ionic_strength}",
    ),
    # pKa values via ligand_id
    (
        """SELECT p.pKa AS constant_value, p.temperature, p.ionic_strength,
                  p.ligand_id
           FROM cards.ligand_pka_measured p
           WHERE p.ligand_id IN ({placeholders})""",
        "constant_value",
        "ligand_id",
        "ligand",
        "pKa @ {temperature}°C, I={ionic_strength}",
    ),
]


def find_closest_matches(
    span: NumericSpan,
    ref_ids: dict[str, list[int]],
    conn: sqlite3.Connection,
    top_k: int = 10,
) -> list[NumericMatch]:
    """Find *top_k* closest DB measurements to *span.value*.

    Parameters
    ----------
    ref_ids
        Mapping from ID prefix (``"vlm"``, ``"metal"``, ``"ligand"``,
        ``"beta_def"``) to lists of raw integer IDs.
    conn
        SQLite connection with all 4 databases attached (via
        ``db_reference.open_reference_connection``).
    """
    all_candidates: list[NumericMatch] = []

    for query_template, val_col, id_col, id_prefix, detail_tpl in _MEASUREMENT_QUERIES:
        ids = ref_ids.get(id_prefix, [])
        if not ids:
            continue
        placeholders = ",".join("?" for _ in ids)
        sql = query_template.format(placeholders=placeholders)
        try:
            rows = conn.execute(sql, ids).fetchall()
        except sqlite3.OperationalError:
            log.debug("Query failed for prefix=%s (table may not exist)", id_prefix)
            continue

        for row in rows:
            db_val = row[val_col] if isinstance(row, dict) else row[0]
            if db_val is None:
                continue
            try:
                db_val = float(db_val)
            except (ValueError, TypeError):
                continue

            distance = abs(db_val - span.value)
            row_dict = dict(row) if hasattr(row, "keys") else {}
            # Build source_id
            raw_source_id = row_dict.get(id_col, "")
            source_id = f"{id_prefix}_{raw_source_id}" if raw_source_id else id_prefix

            # Build detail string
            try:
                detail = detail_tpl.format(**{
                    "constant_type": row_dict.get("constant_type", ""),
                    "temperature": row_dict.get("temperature", "?"),
                    "ionic_strength": row_dict.get("ionic_strength", "?"),
                })
            except (KeyError, IndexError):
                detail = f"value={db_val}"

            all_candidates.append(NumericMatch(
                db_value=db_val,
                distance=distance,
                source_id=source_id,
                source_type=id_prefix,
                measurement_detail=detail,
            ))

    # Sort by distance, return top-k
    all_candidates.sort(key=lambda m: (m.distance, m.source_id))
    return all_candidates[:top_k]


def collect_ref_ids_by_prefix(
    entity_refs: Sequence,
) -> dict[str, list[int]]:
    """Group EntityRef objects by their ID prefix for SQL queries.

    Returns mapping like ``{"vlm": [123, 456], "metal": [41], ...}``.
    """
    import re
    grouped: dict[str, list[int]] = {}
    for ref in entity_refs:
        prefixed_id = ref.prefixed_id if hasattr(ref, "prefixed_id") else str(ref)
        m = re.match(r"^([a-z_]+?)_(\d+)$", prefixed_id)
        if not m:
            continue
        prefix, raw_id = m.group(1), int(m.group(2))
        grouped.setdefault(prefix, []).append(raw_id)
    # Deduplicate
    return {k: sorted(set(v)) for k, v in grouped.items()}
