"""auto_fetch.py
Auto-fetch auxiliary equilibrium networks from SRD-46.

Given a primary metal–ligand pair, this module discovers and returns:
  • metal-hydroxide species  (e.g. Cu(OH)⁺, Cu(OH)₂, …)
  • ligand protonation (pKa) species  (e.g. HL, H₂L, …)
  • valence-sibling species  (e.g. Cu⁺ alongside Cu²⁺)

Each function returns equilibrium_network dicts compatible with the
builder's input JSON format (ready to be appended to the network list).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

# ── path bootstrapping ──────────────────────────────────────────
_THIS = Path(__file__).absolute()
_CALC_ROOT = _THIS.parents[3]                       # NIST_SRD46_core_calc_tools/
_SRD46_ROOT = _THIS.parents[6]                      # SRD46_research_agent/

if str(_CALC_ROOT) not in sys.path:
    sys.path.insert(0, str(_CALC_ROOT))
if str(_SRD46_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRD46_ROOT))

# ── DB search imports ──────────────────────────────────────────
from NIST_SRD46_core_db_search_tools.network_search import search_networks
from NIST_SRD46_core_db_search_tools.entity_search import search_metals as _search_metals
from NIST_SRD46_core_db_search_tools._db_connection import get_cards_db

# ── Constants ──────────────────────────────────────────────────
PROTON_METAL_ID = 68
HYDROXIDE_LIGAND_ID = 10076

# Regex to extract the base element symbol from a metal_name_SRD like "Cu^[2+]", "MeHg^[+]"
_ELEMENT_RE = re.compile(r'([A-Z][a-z]?)(?=\^?\[|$)')


# ═══════════════════════════════════════════════════════════════════
#  Hydroxide auto-fetch
# ═══════════════════════════════════════════════════════════════════

def auto_fetch_hydroxide_networks(
    metal_id: int,
    temperature: float,
    ionic_strength: float,
) -> List[dict]:
    """Find hydroxide eq_networks for *metal_id* in SRD-46.

    Returns equilibrium_networks entries compatible with the input JSON
    format, or an empty list if none found.
    """
    if metal_id == PROTON_METAL_ID:
        return []

    where = f"c.metal_id = {metal_id} AND c.ligand_id = {HYDROXIDE_LIGAND_ID} LIMIT 20"
    rows = search_networks(where)
    if not rows:
        return []

    # Group rows by network_db_id, pick the best-matching network
    nets: Dict[int, List[dict]] = {}
    for r in rows:
        nets.setdefault(r["network_db_id"], []).append(r)

    # Score each network by T/I proximity
    def _score(net_rows: List[dict]) -> float:
        r0 = net_rows[0]
        t_min = r0.get("temp_min", temperature)
        t_max = r0.get("temp_max", temperature)
        i_min = r0.get("ionic_min", ionic_strength)
        i_max = r0.get("ionic_max", ionic_strength)
        t_mid = (t_min + t_max) / 2 if t_min is not None and t_max is not None else temperature
        i_mid = (i_min + i_max) / 2 if i_min is not None and i_max is not None else ionic_strength
        return abs(t_mid - temperature) + 100 * abs(i_mid - ionic_strength)

    best_net_id = min(nets, key=lambda nid: _score(nets[nid]))
    best_rows = nets[best_net_id]
    r0 = best_rows[0]

    return [{
        "eq_network": f"ref_eq_net_{best_net_id}",
        "node_count": r0.get("node_count", len(best_rows)),
        "temperature": temperature,
        "ionic_strength": ionic_strength,
        "metal_id": metal_id,
        "metal_name": r0.get("metal_name", ""),
        "ligand_id": HYDROXIDE_LIGAND_ID,
        "ligand_SMILES": None,
        "ligand_canonical_HxL": None,
        "_notes": f"auto-fetched hydroxide network (network_db_id={best_net_id})",
        "_auto_fetched": "hydroxide",
    }]


# ═══════════════════════════════════════════════════════════════════
#  Primary metal–ligand network auto-fetch
# ═══════════════════════════════════════════════════════════════════

def auto_fetch_primary_network(
    metal_id: int,
    ligand_id: int,
    temperature: float = 25.0,
    ionic_strength: float = 0.1,
) -> Optional[dict]:
    """Find the best eq_network for a (metal_id, ligand_id) pair.

    Same SQL pattern as ``auto_fetch_pka_networks`` /
    ``auto_fetch_hydroxide_networks``: query
    ``eq_map_collection`` for matching rows, group by
    ``network_db_id``, pick the network closest to (T, I).

    Returns a single network dict (the same shape as elements of the
    list returned by the other ``auto_fetch_*`` helpers), or ``None``
    if no network exists for that pair in SRD-46.
    """
    where = f"c.metal_id = {metal_id} AND c.ligand_id = {ligand_id} LIMIT 20"
    rows = search_networks(where)
    if not rows:
        return None

    nets: Dict[int, List[dict]] = {}
    for r in rows:
        nets.setdefault(r["network_db_id"], []).append(r)

    def _score(net_rows: List[dict]) -> float:
        r0 = net_rows[0]
        t_min = r0.get("temp_min", temperature)
        t_max = r0.get("temp_max", temperature)
        i_min = r0.get("ionic_min", ionic_strength)
        i_max = r0.get("ionic_max", ionic_strength)
        t_mid = (t_min + t_max) / 2 if t_min is not None and t_max is not None else temperature
        i_mid = (i_min + i_max) / 2 if i_min is not None and i_max is not None else ionic_strength
        return abs(t_mid - temperature) + 100 * abs(i_mid - ionic_strength)

    best_net_id = min(nets, key=lambda nid: _score(nets[nid]))
    r0 = nets[best_net_id][0]

    return {
        "eq_network": f"ref_eq_net_{best_net_id}",
        "node_count": r0.get("node_count", len(nets[best_net_id])),
        "temperature": temperature,
        "ionic_strength": ionic_strength,
        "metal_id": metal_id,
        "metal_name": r0.get("metal_name", ""),
        "ligand_id": ligand_id,
        "ligand_SMILES": r0.get("ligand_SMILES", None),
        "ligand_canonical_HxL": r0.get("ligand_HxL_definition", None),
        "_notes": f"auto-fetched primary network (network_db_id={best_net_id})",
        "_auto_fetched": "primary",
    }


# ═══════════════════════════════════════════════════════════════════
#  pKa auto-fetch
# ═══════════════════════════════════════════════════════════════════

def auto_fetch_pka_networks(
    ligand_id: int,
    temperature: float,
    ionic_strength: float,
) -> List[dict]:
    """Find protonation (pKa) eq_networks for *ligand_id* in SRD-46.

    Queries for metal_id=68 (H⁺) + ligand_id=X, returning the
    ligand's protonation equilibria (H⁺ + L⁻ ⇌ HL, etc.).
    """
    if ligand_id == HYDROXIDE_LIGAND_ID:
        return []

    where = f"c.metal_id = {PROTON_METAL_ID} AND c.ligand_id = {ligand_id} LIMIT 20"
    rows = search_networks(where)
    if not rows:
        return []

    # Group by network_db_id
    nets: Dict[int, List[dict]] = {}
    for r in rows:
        nets.setdefault(r["network_db_id"], []).append(r)

    # Score by T/I proximity and pick the best
    def _score(net_rows: List[dict]) -> float:
        r0 = net_rows[0]
        t_min = r0.get("temp_min", temperature)
        t_max = r0.get("temp_max", temperature)
        i_min = r0.get("ionic_min", ionic_strength)
        i_max = r0.get("ionic_max", ionic_strength)
        t_mid = (t_min + t_max) / 2 if t_min is not None and t_max is not None else temperature
        i_mid = (i_min + i_max) / 2 if i_min is not None and i_max is not None else ionic_strength
        return abs(t_mid - temperature) + 100 * abs(i_mid - ionic_strength)

    best_net_id = min(nets, key=lambda nid: _score(nets[nid]))
    best_rows = nets[best_net_id]
    r0 = best_rows[0]

    return [{
        "eq_network": f"ref_eq_net_{best_net_id}",
        "node_count": r0.get("node_count", len(best_rows)),
        "temperature": temperature,
        "ionic_strength": ionic_strength,
        "metal_id": PROTON_METAL_ID,
        "metal_name": "H+",
        "ligand_id": ligand_id,
        "ligand_SMILES": r0.get("ligand_SMILES", None),
        "ligand_canonical_HxL": r0.get("ligand_HxL_definition", None),
        "_notes": f"auto-fetched pKa network (network_db_id={best_net_id})",
        "_auto_fetched": "pka",
    }]


# ═══════════════════════════════════════════════════════════════════
#  Element / sibling discovery
# ═══════════════════════════════════════════════════════════════════

def get_element_for_metal(metal_id: int) -> Optional[str]:
    """Return the base element symbol for a metal_id (e.g. 71 → 'Hg')."""
    rows = _search_metals(metal_id=metal_id, limit=1)
    if not rows:
        return None
    metal_name = rows[0].get("metal_name", "")
    m = _ELEMENT_RE.search(metal_name)
    return m.group(1) if m else None


def find_sibling_metal_ids(element: str, exclude_id: int) -> List[dict]:
    """Find all metal_ids for the same element, excluding *exclude_id*.

    Returns list of dicts: {metal_id, metal_name, charge}.
    """
    with get_cards_db() as conn:
        rows = conn.execute(
            """
            SELECT metal_id, metal_name_SRD, charge
            FROM metal_card
            WHERE metal_name_SRD LIKE ?
              AND metal_id != ?
              AND metal_id != ?
            ORDER BY charge DESC
            """,
            (f"%{element}%", exclude_id, PROTON_METAL_ID),
        ).fetchall()
    return [
        {"metal_id": r[0], "metal_name": r[1], "charge": r[2]}
        for r in rows
    ]


# ═══════════════════════════════════════════════════════════════════
#  Valence-sibling auto-fetch
# ═══════════════════════════════════════════════════════════════════

def auto_fetch_valence_networks(
    metal_id: int,
    ligand_id: int,
    temperature: float,
    ionic_strength: float,
) -> List[dict]:
    """Find eq_networks for all other valences of the same element + ligand.

    E.g. if metal_id=71 (Hg²⁺) and ligand_id=5760 (glycine), this returns
    networks for MeHg⁺+glycine, Hg⁺+glycine, EtHg⁺+glycine, etc.
    """
    element = get_element_for_metal(metal_id)
    if not element:
        return []

    siblings = find_sibling_metal_ids(element, exclude_id=metal_id)
    if not siblings:
        return []

    results: List[dict] = []
    for sib in siblings:
        sib_mid = sib["metal_id"]
        where = f"c.metal_id = {sib_mid} AND c.ligand_id = {ligand_id} LIMIT 20"
        rows = search_networks(where)
        if not rows:
            continue

        # Group by network_db_id, pick best by T/I proximity
        nets: Dict[int, List[dict]] = {}
        for r in rows:
            nets.setdefault(r["network_db_id"], []).append(r)

        def _score(net_rows: List[dict]) -> float:
            r0 = net_rows[0]
            t_min = r0.get("temp_min", temperature)
            t_max = r0.get("temp_max", temperature)
            i_min = r0.get("ionic_min", ionic_strength)
            i_max = r0.get("ionic_max", ionic_strength)
            t_mid = (t_min + t_max) / 2 if t_min is not None and t_max is not None else temperature
            i_mid = (i_min + i_max) / 2 if i_min is not None and i_max is not None else ionic_strength
            return abs(t_mid - temperature) + 100 * abs(i_mid - ionic_strength)

        best_net_id = min(nets, key=lambda nid: _score(nets[nid]))
        best_rows = nets[best_net_id]
        r0 = best_rows[0]

        results.append({
            "eq_network": f"ref_eq_net_{best_net_id}",
            "node_count": r0.get("node_count", len(best_rows)),
            "temperature": temperature,
            "ionic_strength": ionic_strength,
            "metal_id": sib_mid,
            "metal_name": sib["metal_name"],
            "ligand_id": ligand_id,
            "ligand_SMILES": r0.get("ligand_SMILES", None),
            "ligand_canonical_HxL": r0.get("ligand_HxL_definition", None),
            "_notes": f"auto-fetched valence sibling (element={element}, network_db_id={best_net_id})",
            "_auto_fetched": "valence",
        })

    return results
