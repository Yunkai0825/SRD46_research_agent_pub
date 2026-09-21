# Timing comparison plots

Both figures use stacked bars and exclude solver time. Claude runs also exclude waiting between turns.

| Comparison | Plot | Redraw data |
|---|---|---|
| All L1 prompts: framework and web models | [PNG](L1_framework_vs_web_stacked.png) | [CSV](L1_stacked_bars.csv) |
| All prompts: framework and Opus high | [PNG](all_prompts_framework_vs_opus_high_stacked.png) | [CSV](all_prompts_stacked_bars.csv) |

- **exports/** — editable SVG versions.
- **scripts/** — redraw and data-preparation scripts.

To regenerate the PNG, PDF, and SVG figures from the two CSVs, run from this folder:

    python scripts/redraw_plots.py --from-plot-csv

Flags: **P** = no preserved plot; **S** = no recorded solver; **H** = plot only in history. Estimated or bounded timings and incomplete framework runs are marked in the plots.
