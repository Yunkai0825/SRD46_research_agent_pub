# health_check_helper

Pre-flight validation for tool and compactor catalogs. Runs **once** at
agent startup, before the first `agent_turn()` call.

## Public API

```python
from .heath_check_tools_compactors_catalogs import (
    run_health_check,          # validator function
    CatalogHealthCheckError,   # exception on mismatch
)
```

### `run_health_check(catalog, *, compactor_catalog, actual_tools, label)`

| Parameter | Type | Purpose |
|-----------|------|---------|
| `catalog` | `AgentToolCatalog` | Class-based tool catalog for the agent layer |
| `compactor_catalog` | `CompactorCatalog \| None` | Explicit compactor catalog (falls back to `catalog._compactor_catalog`) |
| `actual_tools` | `dict[str, Callable] \| None` | Final `{name: callable}` dict passed to `agent_turn()` |
| `label` | `str` | Human-readable label for log messages (e.g. `"analysis-L0"`) |

### Validation Rules

1. **MISSING_COMPACTOR** — Every entry with `skip_compactor=False` must have `compactor_fn`
2. **COMPACTOR_NOT_IN_CATALOG** — Every compacted tool must appear in the `CompactorCatalog`
3. **COMPACTOR_MISMATCH** — `ToolEntry.compactor_fn` must match the `CompactorCatalog` entry
4. **ORPHAN_COMPACTOR** — `CompactorCatalog` entries must map back to a registered tool or extra compactor
5. **UNREGISTERED_TOOL** — Every tool in `actual_tools` must be registered in the catalog

### `CatalogHealthCheckError`

Subclass of `RuntimeError`. Contains a multi-line summary of all failing
rules. Raised when one or more validation rules fail.
