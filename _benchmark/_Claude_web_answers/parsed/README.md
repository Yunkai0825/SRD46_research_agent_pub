# Parsed runs

One folder per configuration (`<export>_<effort>`) and prompt, built by `renderers/parse_exports.py` from the export zips.

| Configuration | Runs |
|---|---|
| Fable5_1_max | 6 |
| Fable5_1_medium | 6 |
| Opus4_7_high | 32 |
| Opus4_7_max | 11 |

Each prompt folder has:
- `conversation.json`: the run's `messages.json` from the export, unchanged (shown branch first, then any alternate continuation).
- `final_answer.md`: Claude's final answer, taken from the branch claude.ai shows: everything after the last working tool call (text, charts, widgets, presented images and published pages, in order). Front matter holds the model, effort and times.
- the images `final_answer.md` embeds: presented output images from the export, and chart/widget PNGs from Renderings.
- HTML reports the run saved to its outputs, when there are any.

`_summary/` holds the statistics:
- `runs.csv`: one row per run, with prompt metadata, timings, Continues, tool calls by tool and category, web pages reached and code written.
- `prompts.csv`: one row per prompt, with every configuration's metrics side by side.
- `metrics_long.csv`: one row per run and metric, for plotting any way you like.
- `tool_calls_by_prompt.csv`: one row per run and tool.
- `segments.csv` (turns), `tools.csv` (tool calls) and `code_files.csv` (scripts written).
- `summary.md`: tables, plots and definitions.
- `plots/`: comparisons across configurations, using only prompt levels that more than one configuration ran.
- `plots/<config>_by_level/`: the same views across every prompt of a configuration that also ran other levels.
