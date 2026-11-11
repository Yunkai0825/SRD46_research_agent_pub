# Workflow Markdown parser

This package parses agent workflow Markdown into configuration and prompt fields. It does not execute Markdown as Python.

## Format and API

The front matter requires `agent_id`, `layer` and `parent`. The system prompt must be inside `<system_prompt>` tags. A minimal workflow is:

```markdown
---
agent_id: example
layer: 1
parent: null
---
<system_prompt>
Follow the supplied instruction.
</system_prompt>

# Prompt Template
{{instruction}}
{{context}}
```

From the repository root:

```python
from SRD46_research_agent.NIST_SRD46_db_agent.general_db_query_engine.general_subagent_skill_schema_and_parser.subworkflow_md_parser import parse_workflow, render_prompt

parsed = parse_workflow("example.md")
prompt = render_prompt(parsed, instruction="Summarize the supplied context.", context="Example context.")
system_prompt = parsed["system_prompt"]
```

`render_prompt` accepts `purpose`, `instruction`, `context` and `id_catalog` keyword values. It does not prepend the system prompt. `_subworkflow_parsing_schema.md` defines the workflow contract; `subworkflow_md_tool_descriptions.py` renders tool descriptions from parsed definitions.

## Parallel workflow execution

`general_argo_engine_helpers.async_runner` supplies `fan_out`, `run_phase` and `run_workflow`. The runner executes phases in order and uses bounded parallel fan-out for phases declaring parallel dispatch. Import these helpers through the full `NIST_SRD46_db_agent.general_db_query_engine` package path after normal import-path setup.
