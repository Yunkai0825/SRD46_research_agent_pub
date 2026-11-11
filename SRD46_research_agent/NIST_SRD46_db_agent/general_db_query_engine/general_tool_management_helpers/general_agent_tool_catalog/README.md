# general_agent_tool_catalog — Class-Based Tool Catalogs

Registry infrastructure for agent tools: registration, compaction
metadata, health-check validation, and wrapped-tool dictionaries.

---

## Purpose

Every agent layer uses a subclass of `AgentToolCatalog` to register
its tools with compaction metadata.  The catalog produces the flat
`tools: dict[str, callable]` consumed by `agent_turn()` and
validates compactor consistency at startup via health checks.

---

## Modules

| File | Exports | Purpose |
|------|---------|---------|
| `tool_entry.py` | `ToolEntry` | Frozen dataclass pairing a tool callable with compaction metadata (`compactor_fn`, `condense_fn`, `ultra_condense_fn`, skip flags, `adaptive_condense`) |
| `agent_tool_catalog.py` | `AgentToolCatalog` | Base class — `register()`, `register_many()`, `wrapped_tools()`, `compact_tool_result()`, `get_entry()` |
| `agent_tool_compactor_hooks_catalog.py` | `CompactorCatalog`, `CompactorEntry`, `@compacts`, `@uses_compactors` | Auto-wiring registry for compactors via decorators |
| `health_check_helper/` | `run_health_check()`, `CatalogHealthCheckError` | Pre-flight startup validation (see below) |

---

## Condensation Tiers

Tools may support up to three compaction levels:

| Tier | Field | Richness | Use Case |
|------|-------|----------|----------|
| **Full** | `compactor_fn` | Richest | Default — dict→markdown with all metadata |
| **Condense** | `condense_fn` | Medium | Strips data-table rows, keeps metadata |
| **Ultra-condense** | `ultra_condense_fn` | Minimal | One-liner per result block |

Tools that handle condensation internally set `adaptive_condense=True`.

---

## Agent Subclasses

```
AgentToolCatalog (base)
├── QueryL0Catalog        — query_agent_toolbox/tool_catalog.py
├── QueryL1Catalog        — query_agent_workflows/L1_workers/
├── AnalysisCatalog       — analysis_agent_toolbox/tool_catalog.py
└── MainCatalog           — main_agent_toobox/tool_catalog.py
```

---

## Health Check Rules

`run_health_check()` validates at startup:

1. Every tool with `skip_compactor=False` has a `compactor_fn`
2. `CompactorCatalog` entries match `ToolEntry` compactors (no mismatches)
3. No orphan compactors (every `CompactorCatalog` entry maps to a real tool)
4. Every tool in the `agent_turn()` dict is registered in the catalog

Raises `CatalogHealthCheckError` with a multi-line summary on failure.
