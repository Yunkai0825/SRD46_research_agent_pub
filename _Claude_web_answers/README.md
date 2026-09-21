# Claude web reference answers

The saved references are available in exactly two self-contained archives. The existing `parsed/` folder is also retained unchanged for direct browsing:

| Archive | Configurations | Runs |
|---|---|---:|
| [Opus4_7.zip](Opus4_7.zip) | Opus4_7_high, Opus4_7_max | 43 |
| [Fable5_1.zip](Fable5_1.zip) | Fable5_1_medium, Fable5_1_max | 12 |

Inside each archive, open `<configuration>/<prompt_id>/final_answer.md`. Each prompt folder contains its conversation, original transcript and JSON export, original `artifacts/`, figures, HTML reports, and saved chat previews. Figures and reports are beside the answer, and `view_images/` is inside that same prompt. Full prompt titles and conversation IDs are in each prompt's `README.md` and `run.json`.

For example, `Opus4_7.zip` contains `Opus4_7_high/L1_11/pourbaix_diagram.png`, `pourbaix_report.html`, and `page_pourbaix_report.png` beside its answer, together with the original artifact files and viewed previews.

Global statistics, comparison plots, export metadata and fetch reports are clearly named files at each archive's root. Cross-model statistics are duplicated in both archives to retain the original comparisons. `provenance.json` records each original source member, destination, byte count and SHA-256; it is an audit record, not an alias used to locate outputs. All 758 source files were compared directly with their archived copies. No calculations or figures were regenerated during consolidation.

The original `parsed/` tree remains at `_Claude_web_answers/parsed/`; all 183 files match their original SHA-256 hashes. Backups of that tree and the original ZIPs remain under the ignored `__tmp__/claude_archive_consolidation_20260920/originals/` directory. The two model ZIPs are self-contained, and rebuilding their renderings does not change `parsed/`.

The [renderer instructions](renderers/README.md) describe the archive-aware workflow. To verify either archive without extracting or changing it, run from the repository root:

```powershell
python -B _Claude_web_answers/renderers/consolidate_archive.py --verify _Claude_web_answers/Opus4_7.zip
python -B _Claude_web_answers/renderers/consolidate_archive.py --verify _Claude_web_answers/Fable5_1.zip
```
