"""
SRD46 DB Search Tool Registry — auto-discovered catalog of all search tools.
=============================================================================
Scans ``NIST_SRD46_core_db_search_tools/`` at import time to build a
structured registry of every public search function and its compactor.

Source of truth
---------------
- **Search functions** — discovered by AST-scanning ``entity_search.py``,
  ``stability_search.py``, ``pka_search.py``, ``network_search.py``,
  ``citation_search.py``, ``aggregate_and_sql.py``, ``similarity_search.py``,
  ``system_catalog.py``, and ``card_inspect.py`` for public ``def`` lines.
- **Compactors** — discovered from ``COMPACTOR_FUNCTIONS`` in
  ``_tools_results_compactors/__init__.py`` by reading each function's
  ``_compacts_tools`` attribute (set by the ``@compacts(...)`` decorator).
"""

from __future__ import annotations

import ast
import inspect
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

log = logging.getLogger("srd46-search-tool-registry")

# ── Locate NIST_SRD46_core_db_search_tools/ root ──────────────
_HERE = Path(__file__).resolve().parent
_ENGINE_ROOT = _HERE.parent                     # general_db_query_engine/
_DB_AGENT = _ENGINE_ROOT.parent                 # NIST_SRD46_db_agent/
_SRD46_ROOT = _DB_AGENT.parent                  # SRD46_research_agent/
_SEARCH_ROOT = _SRD46_ROOT / "NIST_SRD46_core_db_search_tools"
_COMPACTOR_ROOT = _SEARCH_ROOT / "_tools_results_compactors"

# Tool modules and their categories
_TOOL_MODULES = {
    "entity_search.py":      "entity_search",
    "stability_search.py":   "stability",
    "pka_search.py":         "pka",
    "network_search.py":     "network",
    "citation_search.py":    "citation",
    "aggregate_and_sql.py":  "aggregate",
    "similarity_search.py":  "similarity",
    "system_catalog.py":     "system_catalog",
    "card_inspect.py":       "card_inspect",
}

# Public helpers that are NOT user-facing tools (exclude from registry)
_EXCLUDED_FUNCTIONS = {
    "inject_phases_strip_tree",   # internal post-processor used by search_stability_constants
}


# ═══════════════════════════════════════════════════════════════
#  Dataclass
# ═══════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SearchToolEntry:
    """Describes one public search function in NIST_SRD46_core_db_search_tools."""

    tool_name: str
    """Canonical name used in agent tool dicts and compactor registries."""

    category: str
    """One of: entity_search, joined_search, external_db, cross_db, similarity."""

    module_file: str
    """Filename that defines the function."""

    description: str
    """First line of the docstring (auto-extracted)."""

    compactor_fn_name: Optional[str] = None
    """Name of the ``compact_*`` function (None = no compactor)."""

    compactor_module_file: Optional[str] = None
    """Compactor's module path relative to _tools_results_compactors/."""


# ═══════════════════════════════════════════════════════════════
#  Static AST scanner
# ═══════════════════════════════════════════════════════════════

def _scan_module_for_public_fns(filepath: Path) -> List[dict]:
    """Parse *filepath* with AST and return info on each public function."""
    try:
        source = filepath.read_text(encoding="utf-8")
    except OSError:
        return []
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []

    results = []
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name.startswith("_"):
            continue
        doc = ast.get_docstring(node) or ""
        first_line = doc.split("\n")[0].strip() if doc else ""
        results.append({"name": node.name, "docstring": first_line})
    return results


# ═══════════════════════════════════════════════════════════════
#  Compactor discovery
# ═══════════════════════════════════════════════════════════════

def _discover_compactors() -> Dict[str, dict]:
    """Import COMPACTOR_FUNCTIONS and build {tool_name: info} from tags."""
    # Make ``NIST_SRD46_core_db_search_tools`` importable as a top-level
    # package; we then access the compactor sub-package through it so
    # internal relative imports (``from .._db_connection import ...``)
    # in the compactor modules resolve correctly.
    if str(_SRD46_ROOT) not in sys.path:
        sys.path.insert(0, str(_SRD46_ROOT))

    compactor_map: Dict[str, dict] = {}
    try:
        from NIST_SRD46_core_db_search_tools._tools_results_compactors import (
            COMPACTOR_FUNCTIONS,
        )
    except ImportError as e:
        log.warning("Cannot import COMPACTOR_FUNCTIONS: %s", e)
        return compactor_map

    for fn in COMPACTOR_FUNCTIONS:
        tool_names = getattr(fn, "_compacts_tools", ())
        try:
            mod = inspect.getmodule(fn)
            if mod and hasattr(mod, "__file__") and mod.__file__:
                mod_path = Path(mod.__file__).resolve()
                try:
                    rel = mod_path.relative_to(_COMPACTOR_ROOT)
                    module_file = str(rel).replace("\\", "/")
                except ValueError:
                    module_file = mod_path.name
            else:
                module_file = "?"
        except Exception:
            module_file = "?"

        for tool_name in tool_names:
            compactor_map[tool_name] = {
                "fn_name": fn.__name__,
                "module_file": module_file,
                "fn": fn,
            }
    return compactor_map


# ═══════════════════════════════════════════════════════════════
#  Build the registry
# ═══════════════════════════════════════════════════════════════

def _build_registry() -> List[SearchToolEntry]:
    """Scan tool modules + compactors and return a list of SearchToolEntry."""
    compactor_map = _discover_compactors()

    entries: List[SearchToolEntry] = []
    for module_name, category in _TOOL_MODULES.items():
        filepath = _SEARCH_ROOT / module_name
        if not filepath.exists():
            log.warning("Tool module not found: %s", filepath)
            continue
        for fn_info in _scan_module_for_public_fns(filepath):
            if fn_info["name"] in _EXCLUDED_FUNCTIONS:
                continue
            c = compactor_map.get(fn_info["name"])
            entries.append(SearchToolEntry(
                tool_name=fn_info["name"],
                category=category,
                module_file=module_name,
                description=fn_info["docstring"],
                compactor_fn_name=c["fn_name"] if c else None,
                compactor_module_file=c["module_file"] if c else None,
            ))
    return entries


_ALL_ENTRIES = _build_registry()


# ═══════════════════════════════════════════════════════════════
#  Derived look-ups
# ═══════════════════════════════════════════════════════════════

SEARCH_TOOL_REGISTRY: Dict[str, SearchToolEntry] = {
    e.tool_name: e for e in _ALL_ENTRIES
}

COMPACTOR_MODULE_MAP: Dict[str, str] = {
    e.tool_name: e.compactor_module_file
    for e in _ALL_ENTRIES
    if e.compactor_module_file is not None
}

CATEGORIES = sorted({e.category for e in _ALL_ENTRIES})


def list_tools_with_compactors() -> List[str]:
    return [e.tool_name for e in _ALL_ENTRIES if e.compactor_fn_name is not None]


def list_tools_without_compactors() -> List[str]:
    return [e.tool_name for e in _ALL_ENTRIES if e.compactor_fn_name is None]


def tools_by_category(category: str) -> List[SearchToolEntry]:
    return [e for e in _ALL_ENTRIES if e.category == category]


# ═══════════════════════════════════════════════════════════════
#  Markdown report
# ═══════════════════════════════════════════════════════════════

def generate_report_md() -> str:
    """Generate a markdown report of all SRD46 search tools and compactors."""
    lines: List[str] = []
    w = lines.append

    n_total = len(_ALL_ENTRIES)
    n_with = len(list_tools_with_compactors())
    n_without = len(list_tools_without_compactors())

    w("# SRD46 DB Search Tool & Compactor Registry")
    w("")
    w("*Auto-generated by `srd46_db_search_tool_registry.py`*")
    w("")
    w("## Summary")
    w("")
    w("| Metric | Count |")
    w("|--------|-------|")
    w(f"| Total search tools | {n_total} |")
    w(f"| With compactor | {n_with} |")
    w(f"| Without compactor | {n_without} |")
    w(f"| Categories | {len(CATEGORIES)} |")
    w("")

    for cat in CATEGORIES:
        cat_tools = tools_by_category(cat)
        w(f"## {cat.replace('_', ' ').title()}  ({len(cat_tools)} tools)")
        w("")
        w("| Tool | Module | Compactor | Compactor Module |")
        w("|------|--------|-----------|------------------|")
        for e in cat_tools:
            comp_name = e.compactor_fn_name or "—"
            comp_mod = e.compactor_module_file or "—"
            w(f"| `{e.tool_name}` | `{e.module_file}` | `{comp_name}` | `{comp_mod}` |")
        w("")

    no_comp = list_tools_without_compactors()
    if no_comp:
        w("## Tools Without Compactors")
        w("")
        for name in no_comp:
            e = SEARCH_TOOL_REGISTRY[name]
            w(f"- `{name}` — {e.description or '(no description)'}")
        w("")

    return "\n".join(lines)
