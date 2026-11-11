# Claude web reference answers

The saved references are available in two self-contained archives. The `parsed/` folder supports direct browsing:

| Archive | Configurations | Runs |
|---|---|---:|
| [Opus4_7.zip](Opus4_7.zip) | Opus4_7_high, Opus4_7_max | 43 |
| [Fable5_1.zip](Fable5_1.zip) | Fable5_1_medium, Fable5_1_max | 12 |

Inside each archive, open `<configuration>/<prompt_id>/final_answer.md`. Each prompt folder contains its conversation, original transcript and JSON export, original `artifacts/`, figures, HTML reports, and saved chat previews. Figures and reports are beside the answer, and `view_images/` is inside that same prompt. Full prompt titles and conversation IDs are in each prompt's `README.md` and `run.json`.

For example, `Opus4_7.zip` contains `Opus4_7_high/L1_11/pourbaix_diagram.png`, `pourbaix_report.html`, and `page_pourbaix_report.png` beside its answer, together with the original artifact files and viewed previews.

Global statistics, comparison plots, export metadata and fetch reports are named files at each archive's root. Both archives include cross-model statistics. `provenance.json` records each source member, destination, byte count and SHA-256 for auditing the stored files.

The two model ZIPs are self-contained. The browser can read archived outputs directly and uses unpacked files when available.

The [renderer instructions](renderers/README.md) describe the archive-aware workflow. To verify either archive without extracting or changing it, run from this `_Claude_web_answers` directory:

```powershell
python -B renderers/consolidate_archive.py --verify Opus4_7.zip
python -B renderers/consolidate_archive.py --verify Fable5_1.zip
```
