"""
General working-memory base class — shared by query and analysis agents.
========================================================================
Provides a **unified ID Catalog** for all entity types (compounds,
properties, variables, constraints, measurements, solvents, phases),
along with core serialisation helpers and merge logic.

Each agent subclasses and adds its own session management, persistence,
and tool-result extraction.  Literature (``lit_num_id``) is handled
separately outside the catalog.

Supported entity types and their num_id keys
---------------------------------------------
| type    | num_id key      |
|---------|-----------------|
| comp    | comp_num_id     |
| prop    | prop_num_id     |
| var     | var_num_id      |
| constr  | constr_num_id   |
| meas    | meas_num_id     |
| solvent | solvent_num_id  |
| phase   | phase_num_id    |

Public API
----------
BaseWorkingMemory
    .add_entity(entity_type, name, num_id, **extras)
    .merge_entity(entity_type, name, **fields)
    .find_entity_by_num_id(entity_type, num_id) -> (name, info) | None
    .find_entity_by_name(entity_type, name)     -> (key, info) | None
    .add_compound / merge_compound / find_compound_by_*  (convenience)
    .add_property  (convenience)
    .ingest_block_metadata(metadata)            -> None
    .render_id_catalog() -> str
normalize_name(raw) -> str
extract_entities_from_block_metadata(metadata) -> dict[str, list[dict]]
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict

log = logging.getLogger("BASE-WM")


# ── Name normalisation ───────────────────────────────────────

_BOLD_RE = re.compile(r"\*\*?|__?")
_STOP_WORDS = frozenset({
    "for", "the", "of", "and", "or", "in", "at", "to", "by",
    "is", "a", "an", "with",
})


def normalize_name(raw: str) -> str:
    """Canonical lowercase name: strip markdown, leading stop-words."""
    name = _BOLD_RE.sub("", raw).strip().strip(",;. ").lower()
    parts = name.split()
    while parts and parts[0] in _STOP_WORDS:
        parts.pop(0)
    return " ".join(parts)


# ── Entity-type metadata ────────────────────────────────────

# Maps entity type → the key used for its numeric ID inside info dicts.
_NUM_ID_KEY: dict[str, str] = {
    "comp":    "comp_num_id",
    "prop":    "prop_num_id",
    "var":     "var_num_id",
    "constr":  "constr_num_id",
    "meas":    "meas_num_id",
    "solvent": "solvent_num_id",
    "phase":   "phase_num_id",
}

# Entity types that can carry pure_values (shown in the catalog column)
_PURE_VALUE_TYPES = frozenset({"comp"})


def _num_id_key(entity_type: str) -> str:
    """Return the dict key for a given entity type's numeric ID."""
    return _NUM_ID_KEY.get(entity_type, f"{entity_type}_num_id")


# ── Shared entity extraction from block metadata ────────────

def extract_entities_from_block_metadata(metadata: dict) -> dict[str, list[dict]]:
    """Extract all entity types from block metadata (from ``11_block_data_extractor``).

    The block metadata has:
      - ``compounds``: ``[{comp_num_id, name, org_name, formula}]``
      - ``variables``: ``[{var_num_id, var_id, column_name, compound}]``
      - ``properties``: ``[{prop_num_id, prop_ID, column_name, prop_group, compound}]``
      - ``constraints``: ``[{constr_num_id, constr_id, column_name, compound}]``

    Returns a dict keyed by entity type.  Each value is a list of
    ``{name: str, num_id: int|None, ...extras}``.  Literature is excluded.
    """
    entities: dict[str, list[dict]] = {}

    # ── Compounds ──
    comps = []
    for c in metadata.get("compounds", []):
        if not isinstance(c, dict):
            continue
        name = c.get("name") or c.get("org_name") or c.get("formula")
        if name:
            comps.append({
                "name": name,
                "num_id": c.get("comp_num_id"),
                "formula": c.get("formula"),
            })
    if comps:
        entities["comp"] = comps

    # ── Variables ──
    vars_ = []
    for v in metadata.get("variables", []):
        if not isinstance(v, dict):
            continue
        name = v.get("column_name") or v.get("var_id")
        if name:
            vars_.append({
                "name": name,
                "num_id": v.get("var_num_id"),
                "var_id": v.get("var_id"),
            })
    if vars_:
        entities["var"] = vars_

    # ── Properties ──
    props = []
    for p in metadata.get("properties", []):
        if not isinstance(p, dict):
            continue
        name = p.get("column_name") or p.get("prop_ID")
        if name:
            props.append({
                "name": name,
                "num_id": p.get("prop_num_id"),
                "prop_ID": p.get("prop_ID"),
                "prop_group": p.get("prop_group"),
            })
    if props:
        entities["prop"] = props

    # ── Constraints ──
    constrs = []
    for c in metadata.get("constraints", []):
        if not isinstance(c, dict):
            continue
        name = c.get("column_name") or c.get("constr_id")
        if name:
            constrs.append({
                "name": name,
                "num_id": c.get("constr_num_id"),
                "constr_id": c.get("constr_id"),
            })
    if constrs:
        entities["constr"] = constrs

    return entities


# ── Base class ───────────────────────────────────────────────

class BaseWorkingMemory:
    """Core ID-catalog state shared by every agent.

    All resolved entities live in ``self._catalog[entity_type][name]``.
    Convenience properties ``resolved_compounds`` and ``resolved_properties``
    provide direct references to the most-used sub-dicts.

    Subclasses must call ``super().__init__()`` and may override
    ``render()`` to append agent-specific sections after the catalog.
    """

    def __init__(self) -> None:
        # entity_type → {normalised_name → {num_id_key: int, ...}}
        self._catalog: dict[str, dict[str, dict]] = defaultdict(dict)

    # ── Convenience properties (backward-compat) ─────────────

    @property
    def resolved_compounds(self) -> dict[str, dict]:
        return self._catalog["comp"]

    @resolved_compounds.setter
    def resolved_compounds(self, value: dict[str, dict]) -> None:
        self._catalog["comp"] = value

    @property
    def resolved_properties(self) -> dict[str, dict]:
        return self._catalog["prop"]

    @resolved_properties.setter
    def resolved_properties(self, value: dict[str, dict]) -> None:
        self._catalog["prop"] = value

    # ── Generic entity operations ────────────────────────────

    def add_entity(
        self,
        entity_type: str,
        name: str,
        num_id: int | None = None,
        **extras,
    ) -> None:
        """Register or update an entity in the ID catalog.

        If an entity with the same *num_id* already exists under a
        different name within the same type, the entries are merged
        under the new canonical ``name`` and the old key is removed.
        """
        key = normalize_name(name)
        if not key:
            return

        nid_key = _num_id_key(entity_type)
        section = self._catalog[entity_type]

        # Dedup: merge if same num_id exists under different name
        if num_id is not None:
            for existing_key, info in list(section.items()):
                if (
                    existing_key != key
                    and isinstance(info, dict)
                    and info.get(nid_key) == num_id
                ):
                    merged = dict(info)
                    merged.update(extras)
                    merged[nid_key] = num_id
                    section[key] = merged
                    del section[existing_key]
                    log.debug(
                        "Merged %s '%s' into '%s' (%s_%d)",
                        entity_type, existing_key, key, entity_type, num_id,
                    )
                    return

        entry = section.get(key)
        if isinstance(entry, dict):
            if num_id is not None:
                entry[nid_key] = num_id
            entry.update(extras)
        else:
            d: dict = {}
            if num_id is not None:
                d[nid_key] = num_id
            d.update(extras)
            section[key] = d

    def merge_entity(self, entity_type: str, name: str, **fields) -> None:
        """Merge fields into an existing entity, matching by name then num_id.

        Creates a new entry only as a last resort.
        """
        key = normalize_name(name)
        if not key:
            return

        nid_key = _num_id_key(entity_type)
        section = self._catalog[entity_type]

        # Exact name match
        entry = section.get(key)
        if isinstance(entry, dict):
            entry.update(fields)
            return

        # Fallback: match by num_id
        num_id = fields.get(nid_key)
        if num_id is not None:
            for _k, info in section.items():
                if isinstance(info, dict) and info.get(nid_key) == num_id:
                    info.update(fields)
                    return

        # No match — create new
        section[key] = dict(fields)

    def find_entity_by_num_id(
        self, entity_type: str, num_id: int,
    ) -> tuple[str, dict] | None:
        """Lookup entity by numeric ID → (name, info) or None."""
        nid_key = _num_id_key(entity_type)
        for name, info in self._catalog.get(entity_type, {}).items():
            if isinstance(info, dict) and info.get(nid_key) == num_id:
                return name, info
        return None

    def find_entity_by_name(
        self, entity_type: str, name: str,
    ) -> tuple[str, dict] | None:
        """Lookup entity by normalised name → (key, info) or None."""
        key = normalize_name(name)
        entry = self._catalog.get(entity_type, {}).get(key)
        if isinstance(entry, dict):
            return key, entry
        return None

    # ── Compound convenience methods ─────────────────────────

    def add_compound(self, name: str, comp_num_id: int | None = None, **extras) -> None:
        self.add_entity("comp", name, comp_num_id, **extras)

    def merge_compound(self, name: str, **fields) -> None:
        self.merge_entity("comp", name, **fields)

    def find_compound_by_num_id(self, num_id: int) -> tuple[str, dict] | None:
        return self.find_entity_by_num_id("comp", num_id)

    def find_compound_by_name(self, name: str) -> tuple[str, dict] | None:
        return self.find_entity_by_name("comp", name)

    # ── Property convenience methods ─────────────────────────

    def add_property(self, name: str, prop_num_id: int | None = None, **extras) -> None:
        self.add_entity("prop", name, prop_num_id, **extras)

    # ── Bulk ingestion from block metadata ───────────────────

    def ingest_block_metadata(self, metadata: dict) -> None:
        """Register all entities from block metadata in the catalog.

        Calls ``extract_entities_from_block_metadata`` and then
        ``add_entity`` for each item.  Subclasses can override to
        add agent-specific logic (e.g. storing inspected-blocks list).
        """
        for etype, items in extract_entities_from_block_metadata(metadata).items():
            for item in items:
                name = item.pop("name")
                num_id = item.pop("num_id", None)
                self.add_entity(etype, name, num_id, **item)

    # ── Serialisation ────────────────────────────────────────

    def render_id_catalog(self) -> str:
        """Render the ID Catalog as a markdown table.

        All entity types with at least one entry are included.
        Compounds get a ``pure_values`` column; other types leave it
        blank.

        ``| type | num_id | name | pure_values |``
        """
        rows: list[str] = []

        for etype in ("comp", "prop", "var", "constr", "meas", "solvent", "phase"):
            section = self._catalog.get(etype)
            if not section:
                continue
            nid_key = _num_id_key(etype)

            for name, info in section.items():
                if not isinstance(info, dict):
                    continue
                num_id = info.get(nid_key)
                nid_str = f"{etype}_{num_id}" if num_id is not None else "?"
                # Pure-values column (compounds only)
                pv_str = ""
                if etype in _PURE_VALUE_TYPES:
                    pv = info.get("pure_values")
                    if pv is not None:
                        if isinstance(pv, dict):
                            pv_str = "; ".join(f"{k}={v}" for k, v in pv.items())
                        else:
                            pv_str = str(pv)
                rows.append(f"| {etype} | {nid_str} | {name} | {pv_str} |")

        if not rows:
            return ""
        header = (
            "### ID Catalog\n"
            "| type | num_id | name | pure_values |\n"
            "|------|--------|------|-------------|"
        )
        return header + "\n" + "\n".join(rows)

    def render(self) -> str:
        """Render the full working memory.  Subclasses extend this."""
        return self.render_id_catalog()
