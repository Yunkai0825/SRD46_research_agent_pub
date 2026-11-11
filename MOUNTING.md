# Install SRD-46 Analysis

Clone or unpack this repository into a short local path. Install Python 3.12 or
newer, then run from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/run_analysis.py --check
python run_browser.py --check
python run_browser.py
```

Startup restores missing large source databases from `_large_files`. To restore
them explicitly, run `python zip_images/large_file_packs.py --root . unpack`.
Keep every part and manifest; no Git LFS client is needed. Generated runs are
stored in `_output`; `_benchmark` contains published examples. Configure your
own provider in `srd46_analysis_settings.json` and supply credentials through
environment variables. See [README.md](README.md) and
the embedded guide: `python scripts/run_analysis.py --guide`.
