"""
Shared workflow-skill markdown parser and schema.
=================================================
Both the query agent and analysis agent use this module to parse
workflow ``.md`` files into structured dicts for orchestrator use.

Public API
----------
parse_workflow   — parse a workflow markdown file into a structured dict
render_prompt    — substitute template variables into the prompt template
"""

from .subworkflow_md_parser import parse_workflow, render_prompt

__all__ = ["parse_workflow", "render_prompt"]
