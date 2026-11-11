# Stacked timing comparisons

The two figures compare elapsed time excluding numerical solver execution. Claude web bars also exclude waiting between response turns, as requested.

- **L1_framework_vs_web_stacked.{png,pdf,svg}**: all 11 L1 prompts; framework, Opus 4.7 high/max, Fable 5.1 medium/max. There are 45 recorded bars. Ten unavailable Fable slots show a dash.
- **all_prompts_framework_vs_opus_high_stacked.{png,pdf,svg}**: all 32 benchmark prompts; 64 bars comparing the framework with Opus 4.7 high.

## Redraw directly from CSV

Run from this folder:

    python redraw_plots.py --from-plot-csv

This reads only:
- L1_stacked_bars.csv
- all_prompts_stacked_bars.csv

Each row represents one bar. The ten component columns ending in _min contain its stack heights in minutes. Only the five components for that harness are nonzero. stack_total_min is the sum. The script exports PNG at 300 dpi, editable-text SVG, and PDF with embedded TrueType fonts.

all_stacked_components_long.csv gives one component per row, in both seconds and minutes. The corresponding long and wide comparison CSVs preserve raw elapsed time, excluded solver time, between-turn waiting, model/effort, output flags, uncertainty, and source paths. all_run_timings.csv includes all 87 recorded runs (32 framework + 55 web).

**Use plotted_non_solver_min or stack_total_min for the figures.** non_solver_wall_min deliberately retains the earlier wall-time calculation and does not remove between-turn waiting. Missing runs are blank, not zero.

## Timing definitions

### Framework

Normal runs use manifest elapsed_s minus the summed numerical solver durations in the saved logs. The 2D marker is "Solver pipeline done"; the 1D/general marker is "Coarse solve". Pipeline calls were sequential, and successful solver-log counts were checked against pipeline status files.

The five stack components are:
1. LC1: system and equation mapping
2. LC2: thermodynamic data assembly
3. LC3: solver configuration
4. LD: validation
5. Orchestration, reporting, and other/unattributed time

Canonical LC parent-stage timers count their internal parallel work once. Nested worker/restart timers are not added to their parents. LD durations come from recorded verdict timings. The residual is explicit; it is not assigned using tokens, costs, or estimated proportions. These coarse stages are available consistently enough to reconcile all 32 runs. The finer component split in the reference cost figure cannot be recovered consistently from these timing logs.

L1_1 was resumed. Its manifest contains only the final 28-second recovery step, so it cannot be used as full-run elapsed time. Checkpoint events reconstruct original preparation, restart preludes, and the final remainder, giving approximately 809.759 seconds (13.5 minutes) of active non-solver time. Interrupted solver windows and unknown downtime are excluded. The bar has an asterisk.

Hatched framework bars retain their recorded incomplete/timeout/execution-failed status. These are log statuses, not independent scientific-quality judgments.

### Claude web harness

Only the displayed conversation branch contributes to the bar time. Its active duration is the sum of assistant response segments from first content-block start to last content-block stop. All gaps between these segments, including typed and automatic continuations, are excluded.

Solver execution is estimated from the end of a tool-use block to the start of its matching tool result. This excludes time generating the code/command. Commands that rerun solvers while plotting or building reports are included; commands that only read saved results are excluded. Startup, plotting, and reporting inside a solver command cannot be isolated and are therefore excluded with that command.

The remaining timeline is partitioned into five exclusive components:
1. Thinking
2. Code / tool-input generation
3. Answer writing
4. Non-solver tool execution
5. Other within-turn overhead

The partition uses timestamps, not token counts. It has no overlapping explicit content blocks, and sums to each web bar within one microsecond. Millisecond clock differences can make the first response start slightly precede the human-message creation timestamp; raw wall time and timestamp_clock_skew_s retain this fact, and reported between-turn waits are never negative.

All-history solver totals are retained separately in solver_all_history_command_s. They include alternative branches and must not be subtracted from displayed-branch elapsed time. This is why some solver deductions in these figures differ from the earlier history-wide table.

## Output flags

The audit checks both answer presentation and the entire preserved run history, including original scientific images, HTML/SVG plots, chart/widget calls, and sandbox outputs.

- **P**: no scientific plot found anywhere in the saved history.
- **S**: no recorded solver execution anywhere in the saved history.
- **H**: a plot was generated in history, but not presented in the current answer.
- **P+S**: both absent.
- **Dash**: no exported run for that model/prompt.

There are 20 web runs with no preserved plot and 16 with no recorded solver execution. Two have history-only plots: Opus high L2_3 and Fable max L1_10. These flags describe recorded deliverables, not whether a plot or solver was necessary for a particular prompt, and absence from an export is not proof that an unrecorded action never occurred.

claude_plot_presence.csv records evidence for each flag; fable_solver_calls.csv and solver_command_audit.csv record the execution classifications and tool IDs.

## Uncertainty

- Fable max L1_10 has an interrupted background solver. Its progress log proves at least 44.1 seconds, while the complete duration is unknown. The bar is an **upper bound** on non-solver active time, marked with a less-than-or-equal sign. The 44.1-second deduction fits within a 45.303-second recorded tool-wait interval, so the stack removes it from tool execution without assigning it to thinking or writing. Additional unmeasured solver time may reduce this bar further.
- Opus max L1_2 contains one truncated shell command with no input/result. Neighboring records suggest report assembly, but its function cannot be proven. Only identifiable solver executions are deducted.
- The exports contain hidden thinking contents, but recorded thinking timestamps remain usable. Missing/truncated history may conceal other work.
- Framework solver-stage timers and web solver-command proxies cover somewhat different setup/output overhead. These are not controlled measurements of identical numerical workloads.
- There is one archived run per available prompt/configuration, not repeated timing trials; no error bars or statistical uncertainty intervals are implied.

## Rebuild from the preserved archives

Run in this order:

    python build_timings.py
    python framework_stage_breakdown.py
    python build_web_stacks.py
    python redraw_plots.py

The scripts read the repo's existing benchmark and model ZIPs directly. They do not execute historical solver code, extract/modify original artifacts, or contact a model service. The audited Fable command-selection CSV and plot-presence CSV are inputs.

validation.json, framework_stage_breakdown_audit.json, web_stage_validation.json, and final_validation.json record the reconciliation checks. All generated artifacts remain inside the repo's ignored __tmp__/timing_comparison folder.

