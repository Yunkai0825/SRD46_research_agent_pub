# general_DEBUG_test_runner_helpers — Test Runner Infrastructure

> **DEBUG-only.** These modules are forbidden for production queries.
> The real entry points for the agents are the `*_api.py` files.

---

## Purpose

Provides the shared test orchestration layer used by each agent's
`_DEBUG_script/test_run.py` to execute batch test prompts, capture
outputs, and summarise results.

## Files

| File | Purpose |
|------|---------|
| `DEBUG_test_orchestration.py` | `run_debug_test()` — executes a batch of test prompts against an agent API, captures session outputs, writes summary |
| `DEBUG_test_prompt_parser.py` | Parses `test_prompt.md` files into structured prompt records |

## Usage

Each agent has a `_DEBUG_script/test_run.py` that imports from here:

```python
from ...general_DEBUG_test_runner_helpers.DEBUG_test_orchestration import run_debug_test
from ...general_DEBUG_test_runner_helpers.DEBUG_test_prompt_parser import parse_test_prompts
```

Test results are written to `_outputs_user/<bucket>/<DB>/<Agent>/Diagnostics/test_run_YYYYMMDD_HHMMSS/`.