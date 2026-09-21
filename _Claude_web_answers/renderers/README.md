# Renderers and parser for the saved reference answers

`Fable5_1.zip` and `Opus4_7.zip` are the two self-contained model archives. Each
`<configuration>/<prompt_id>/` folder contains the original conversation and
artifacts, `final_answer.md`, its figures, rendered PNG/HTML files, and
`view_images/`. The scripts read these ZIPs directly; extraction is unnecessary.

## Setup

Install the workspace's root requirements, then install the rendering browser:

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
```

Alternatively, set `RENDER_CHROMIUM` to an installed Chrome or Edge executable.
The standalone rendering dependencies are Playwright and Pillow; the parser uses
Matplotlib for summary plots.

## Refresh the saved visualizations

From the repository root:

```powershell
python _Claude_web_answers/renderers/build_renderings.py all
```

The command discovers `Fable5_1.zip` and `Opus4_7.zip` beside `renderers/`, stages
its work in the operating system's temporary directory, and updates each archive
atomically after checking every member's SHA-256. It creates no separate
renderings ZIP and leaves the existing `parsed/` folder unchanged. Select another
location with `--root DIR`, or specific archives with repeated `--export PATH` arguments.

Figures stay beside the answer in their own prompt folder. Identical files are
reused. A newly rendered figure that differs from an existing file gets a
`rendered_` filename; the original is retained. If that filename already holds
different bytes, the new file also gets a content-hash suffix. Every existing
archive member remains unchanged. Shared audits are root files such as
`renderings_audit.csv` and `regenerated_fetch_list.json`; differing rebuilds add
files with content-hash suffixes instead of replacing an existing audit.

`all` refreshes visualizations from saved chart data, widget code, HTML pages and
preview images. It does not rerun scientific calculations. Existing
`final_answer.md`, its linked original figures and the saved statistical summaries
remain unchanged. The new audit identifies the refreshed figures, including any
`rendered_` variants. Rebuilding answer snapshots and summary plots requires the
explicit `parse` command below.

`--theme dark` selects a dark rendering theme. Preview images retain their exact
saved bytes unless `--view-png` requests conversion. `--work DIR` creates a new
staging subdirectory inside DIR and preserves its existing contents;
`--keep-work` retains that new staging directory for inspection.

## Download missing preview images

The archives already contain the available downloaded previews. If additional
previews are needed, the fetching step is explicit:

1. Run `plan` below and read `WORK/_plan/fetch_list.json`, or pass
   `--fetch-list PATH` to `all` to write a combined list to a chosen location.
2. In a logged-in claude.ai tab, paste `fetch_claude_assets.js` into the developer
   console and provide the list. It makes GET requests and downloads a temporary
   `claude_assets.zip`.
3. Run `all --assets PATH/claude_assets.zip`. Original downloaded bytes are added
   to their run's `view_images/` or `artifacts/`; existing archive assets provide
   the fallback for entries absent from the download.

The asset bundle is an input, not a separate publication output. Missing previews
are recorded in the audit; the renderer does not authenticate or fetch them
itself.

## Explicit individual steps

These commands write only to the destinations you specify:

```powershell
python _Claude_web_answers/renderers/build_renderings.py plan --export _Claude_web_answers/Opus4_7.zip --out WORK
python _Claude_web_answers/renderers/build_renderings.py render WORK --assets _Claude_web_answers/Opus4_7.zip
python _Claude_web_answers/renderers/build_renderings.py parse --export _Claude_web_answers/Opus4_7.zip --renderings _Claude_web_answers/Opus4_7.zip --out DESTINATION
```

`parse` reconstructs answer snapshots and statistics in DESTINATION without
modifying the archives. Its metrics cover timings, continuations, tool calls,
errors, web searches, answer lengths, alternate branches and visible code writes.
Edits through commands such as `sed -i` cannot always be reconstructed, so some
code-length measures are approximate.

The low-level `plan`, `render`, `pack` and `parse` APIs still accept legacy export
layouts. `all --root NEW_DIRECTORY --export ORIGINAL.zip` renders and parses in
temporary storage, then uses `consolidate_archive.py` to publish one self-contained ZIP per model.
The legacy conversion requires unused destination archive paths and retains its
original source ZIPs. It does not publish the temporary rendering or parsed trees.
The consolidation
helper can also reorganize existing results without rendering anything, and
`consolidate_archive.py --verify MODEL.zip` checks preserved source bytes and
answer links without writing files.

Each renderer remains usable on its own:

```powershell
python _Claude_web_answers/renderers/render_chart.py chart_1_x.json --out DIR
python _Claude_web_answers/renderers/render_widget.py widget_1_x.html --out DIR --keep-html
python _Claude_web_answers/renderers/render_page.py report.html --out DIR
```

## Files and rendering fidelity

- `export_zip.py` reads both the self-contained model archives and legacy exports.
  It discovers runs from their own `run.json` and reads original data directly;
  provenance records are used only for preservation checks.
- `build_renderings.py` plans, renders and merges files into the model archives.
- `consolidate_archive.py` reorganizes existing saved files and verifies their bytes.
- `parse_exports.py` reconstructs answers and statistical summaries on request.
- `render_chart.py`, `render_widget.py`, `render_page.py`, `browser.py` and
  `claude_theme.py` implement the standalone renderers.
- `offline_assets.py` serves supported Chart.js/font assets from local packages.
- `fetch_claude_assets.js` downloads preview images and missing output files when
  explicitly run in the authenticated browser.

Charts and widgets use saved data/code with Claude-style theme variables and a
system sans-serif font. Pages are full-page screenshots at 1280 px width and
1.5× scale. Saved chat previews can show intermediate states rather than the
final artifact. Rendering HTML may load its referenced external resources;
`--offline-assets DIR` supplies supported local assets.
