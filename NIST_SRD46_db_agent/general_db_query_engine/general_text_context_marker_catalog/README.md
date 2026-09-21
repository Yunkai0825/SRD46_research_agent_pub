# general_text_context_marker_catalog — Centralized XML Text Markers

Defines all XML-style context markers used as structural delimiters in
the flat prompt and LLM responses throughout the agent pipeline.

---

## Purpose

Context markers are **text-level** tags (`<tool_call>`, `<reasoning>`,
`<answer>`, etc.) that mark boundaries in the data flowing through the
pipeline.  The ReAct engine and hook modules parse these markers via
compiled regexes to extract tool calls, identify reasoning blocks,
delimit answers, and manage compaction.

> **Not to be confused with anchor points** (`engine_hooks_anchors.py`), which
> are **code-level** dispatch slots in the Python control flow.
> Markers handle data format; anchors handle code behaviour.

---

## Modules

| File | Purpose |
|------|---------|
| `context_markers.py` | `TagPair` frozen dataclass, `ContextMarkerCatalog` frozen dataclass (13 tag families), module-level `MARKERS` singleton, backward-compatible flat aliases |
| `__init__.py` | Re-exports all symbols from `context_markers.py` via `from .context_markers import *` |

---

## Data Structures

### `TagPair` (frozen dataclass)

```python
@dataclass(frozen=True)
class TagPair:
    open: str    # e.g. "<tool_call>"
    close: str   # e.g. "</tool_call>"
```

### `ContextMarkerCatalog` (frozen dataclass)

Groups all 13 tag families with their `TagPair` instances and compiled
regexes for extraction.

| Family | Open Tag | Purpose |
|--------|----------|---------|
| `tool_call` | `<tool_call>` | Wraps LLM tool invocations |
| `wait` | `<wait>` | Pause marker between parallel calls |
| `tool_result` | `<tool_result>` | Wraps tool execution results |
| `reasoning` | `<reasoning>` | Extended thinking / chain-of-thought |
| `summary` | `<summary>` | Compacted summaries |
| `compress` | `<compress>` | Agent-initiated compaction request |
| `compaction_guidance` | `<compaction_guidance>` | Mid-turn guidance prompt |
| `compaction_reminder` | `<compaction_reminder>` | Compaction reminder nudge |
| `compact_note` | `<compact_note>` | Compaction metadata note |
| `retry` | `<retry>` | Retry instruction |
| `system_prompt` | `<system_prompt>` | System prompt boundary |
| `answer` | `<answer>` | Final answer boundary |
| `memory` | `<memory>` | Working memory snapshot |

### Module-Level Singleton

```python
MARKERS = ContextMarkerCatalog(...)  # canonical instance
```

### Backward-Compatible Aliases

Flat module-level names like `TAG_TOOL_CALL_OPEN`, `TOOL_CALL_RE`, etc.
are provided for existing imports that predate the catalog class.

---

## Consumer Pattern

```python
from NIST_ThermoML_agents.general_text_context_marker_catalog import MARKERS

# Use tag pair
prompt += MARKERS.tool_result.open + result_text + MARKERS.tool_result.close

# Use compiled regex
match = MARKERS.tool_call_re.search(response)
```
