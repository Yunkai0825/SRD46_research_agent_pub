# Workflow Skill Markdown — Parsing Schema

Every subagent is fully defined by a single `.md` file that follows this
schema.  The `workflow_parser.py` module reads such a file and returns a
structured `dict` that the orchestrator (or any parent agent) uses to
assemble prompts, select tools, and enforce output contracts.

---

## File Layout

```
<YAML front-matter>
---
agent_id:           <string>   # unique agent identifier (e.g. L2_comp_eval)
layer:              <int>      # 0 | 1 | 2
parent:             <string>   # agent_id of the parent that invokes this agent
max_output_tokens:  <int>      # hard cap on output length (tokens)
---

# System Prompt
<free-form markdown — injected verbatim as the system message>

# Tools
## <group_name>
- <tool_signature>   # one line per tool, with brief description after " — "
## <group_name>
- ...

# Prompt Template
<markdown with {{variable}} placeholders>
Supported variables:
  {{purpose}}       — goal text from the parent agent
  {{instruction}}   — detailed instruction from the parent agent
  {{context}}       — serialised context (ids, card data, prior results)
  {{id_catalog}}    — current ID catalog from working memory

# Output Schema
```json
{ ... }              # JSON schema for the structured return value
```

# Phases
## phase_<N>: <phase_name>
tools: [<group_name>, ...]
parallel_dispatch: <optional — see below>
guidance: |
  <free-form instruction for this phase>

## phase_<N>: <phase_name>
...
```

---

## Parsing Rules

1. **Front-matter** — everything between the first pair of `---` lines.
   Parsed as YAML.  All keys are required.

2. **Sections** — each `# Heading` at H1 level starts a new top-level
   section.  Section body is everything until the next H1.

3. **Tools** — inside `# Tools`, each `## group_name` collects a list
   of tool signatures from bullet lines (`- tool_name(...) — description`).

4. **Phases** — inside `# Phases`, each `## phase_N: name` contains:
   - `tools:` line — comma-separated list of tool group names in brackets
   - `parallel_dispatch:` line (optional) — controls async fan-out.
     See **Parallel Dispatch** section below.
   - `guidance:` block — everything after the `guidance:` line until the
     next `##` or end of section.

5. **Output Schema** — the first fenced JSON block inside
   `# Output Schema` is parsed as JSON.

6. **Prompt Template** — captured verbatim (no parsing of placeholders at
   parse time; substitution happens at runtime).

---

## Parallel Dispatch

A phase may declare `parallel_dispatch:` to indicate that multiple tool
calls within that phase should be executed concurrently via
`asyncio.gather()`.  The value is a YAML-like inline dict:

```
parallel_dispatch: {tool_group: <group_name>, fan_out_over: <variable>, max_concurrent: <int>}
```

Fields:
- **tool_group** (str, required) — which tool group contains the tools to
  fan out.  Every tool in this group will be called once per item.
- **fan_out_over** (str, required) — the name of the context variable
  whose items drive the fan-out (e.g. `blocks_found`, `compounds`).
  At runtime the runner iterates this list and dispatches one call per item.
- **max_concurrent** (int, optional, default 8) — concurrency cap passed
  to `asyncio.Semaphore` to avoid overwhelming the LLM backend.

If `parallel_dispatch` is absent, the phase runs sequentially (the
default behaviour).

The async runner (`async_runner.py`) reads this field and handles the
`asyncio.gather()` dispatch automatically.

---

## Parsed Dict Structure

```python
{
    "front_matter": {
        "agent_id": str,
        "layer": int,
        "parent": str,
        "max_output_tokens": int,
    },
    "system_prompt": str,          # raw markdown
    "tools": {
        "group_name": [
            {"name": str, "signature": str, "description": str},
            ...
        ],
    },
    "prompt_template": str,        # raw markdown with {{var}} placeholders
    "output_schema": dict,         # parsed JSON
    "phases": [
        {
            "number": int,
            "name": str,
            "tools": [str, ...],   # group names
            "parallel_dispatch": {  # None if absent
                "tool_group": str,
                "fan_out_over": str,
                "max_concurrent": int,  # default 8
            },
            "guidance": str,       # raw markdown
        },
    ],
}
```
