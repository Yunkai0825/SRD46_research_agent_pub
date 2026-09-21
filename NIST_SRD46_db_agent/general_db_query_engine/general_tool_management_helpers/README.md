# general_tool_management_helpers

Shared tool management infrastructure used by all ThermoML agents.
Contains the class-based tool catalog system, compactor registries,
health-check validation, and the KEEP/DISCARD LLM subagent.

---

## Top-Level Modules

| Module | Purpose |
|--------|---------|
| `_tool_hooks_anchors_catalog.py` | Tool-level anchor types (19 types: TOOL_EXEC 11, TOOL_COMPACTION 7, SUBAGENT 1) for sync/async tool execution hooks |

---

## Sub-packages

### `general_agent_tool_catalog/`

Class-based tool catalogs with two-stage compaction.

| Module | Exports | Purpose |
|--------|---------|---------|
| `tool_entry.py` | `ToolEntry` | Frozen dataclass pairing a tool callable with compaction metadata (compactor_fn, condense_fn, ultra_condense_fn, skip flags) |
| `agent_tool_catalog.py` | `AgentToolCatalog` | Base class for agent-level registries — `register()`, `register_many()`, `wrapped_tools()`, `compact_tool_result()` |
| `agent_tool_compactor_hooks_catalog.py` | `CompactorCatalog`, `CompactorEntry`, `@compacts`, `@uses_compactors` | Structured registry for tool compactors + decorator-based auto-wiring |
| `health_check_helper/` | `run_health_check()`, `CatalogHealthCheckError` | Pre-flight startup validation (see below) |

**Condensation tiers** — tools may support up to three compaction levels:
- **full** — default `compactor_fn` (richest output)
- **condense** — `condense_fn` (strips data-table rows, keeps metadata)
- **ultra_condense** — `ultra_condense_fn` (one-liner per result block)

Tools that handle condensation internally set `adaptive_condense=True`.

Agent subclasses: `QueryL0Catalog`, `QueryL1Catalog`, `AnalysisCatalog`.

### `health_check_helper/`

Pre-flight catalog consistency validation — runs once at agent startup.

**Rules checked by `run_health_check()`:**
1. Every tool with `skip_compactor=False` has a `compactor_fn`
2. CompactorCatalog entries match ToolEntry compactors (no mismatches)
3. No orphan compactors (every CompactorCatalog entry maps to a real tool)
4. Every tool in the `agent_turn()` dict is registered in the catalog

Raises `CatalogHealthCheckError` with a multi-line summary on failure.

### `general_tool_results_compactor_agentic_hooks/`

Shared KEEP/DISCARD LLM subagent for tool-result triage.

| Export | Purpose |
|--------|---------|
| `ToolResult` | Dataclass: `raw` (dict), `text` (markdown), `discarded` (bool) |
| `ToolResultCompactor` | Base dataclass for agent-specific compaction wrappers |
| `call_tool_subagent()` | ReAct-style LLM call (500 tokens) that examines compacted markdown and decides KEEP (extract) or DISCARD (explain + suggest) |
| `parse_subagent_response()` | Extract `(thought, action, output)` from LLM response text |

### `general_tool_options_interactive_hooks/`

Anchor-compatible pre-execution guidance hooks.

| Export | Purpose |
|--------|---------|
| `PreExecutionGuidance` | Frozen dataclass base class — `target_tools`, `required_params`, `context_params`. Bound to `SYNC_TOOL_GUIDANCE_CHECK`. Returns `None` (skip), `""` (OK, auto-filled), or non-empty `str` (blocked with guidance) |
| `block_msg()` | Standalone helper — builds a human-readable block message listing missing parameters |

Agent-specific subclasses (e.g. `FittingVariableGuidance` in the analysis agent)
override `check_and_fill()` to implement domain-specific auto-fill logic.

Each agent provides its own `client_factory` and `cfg` via thin wrappers
in `{agent}_context_hooks/compactor_hooks/tool_result_compactor.py`.

### `general_tool_menu_tools/`

Reserved for future tool-menu utilities. Currently empty.

---

## Usage

```python
from NIST_ThermoML_agents.general_tool_management_helpers.general_agent_tool_catalog import (
    AgentToolCatalog, ToolEntry, CompactorCatalog, compacts, uses_compactors,
    run_health_check, CatalogHealthCheckError,
)
from NIST_ThermoML_agents.general_tool_management_helpers.general_tool_results_compactor_agentic_hooks import (
    ToolResult, call_tool_subagent,
)
```
