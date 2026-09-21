"""
SRD46_pd_chemical_names-pip-4.py
--------------------------------

Pipeline 1c-4: Chemical Name Identification via PubChem

Queries PubChem REST API to retrieve IUPAC and common names for molecules
based on their SMILES strings.

Input:  CSV with SMILES column (from pip1c-3 output)
Output: Enriched CSV with IUPAC_NAME and COMMON_NAME columns

I/O Configuration:
- Input:  _build/pip1c_3_HxL_output/liganden_moldata_HxL_parsed.csv
- Output: _build/pip1c_4_chemical_names_output/
"""

import csv
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import requests

# ----------------------------------------------------------------------
# PATH CONFIGURATION
# ----------------------------------------------------------------------
now = datetime.now()
TIMESTAMP = now.strftime("%Y-%m-%d-%H-%M-%S")

CODE_ROOT = Path(__file__).resolve().parent
PIPELINE_ROOT = CODE_ROOT.parent  # pip1c_parse_liganden_moldata_pKa_SRD46
PROJECT_ROOT = PIPELINE_ROOT.parent.parent  # NIST_SRD46_Correction_and_Parser

# Input: from pip1c_3_HxL_output (output of previous stage)
INPUT_DIR = PIPELINE_ROOT / "_build" / "pip1c_3_HxL_output"
INPUT_CSV = INPUT_DIR / "liganden_moldata_HxL_parsed.csv"

# Build: all outputs go to _build/pip1c_4_chemical_names_output/
BUILD_DIR = PIPELINE_ROOT / "_build" / "pip1c_4_chemical_names_output"

# Output files
FINAL_CSV = BUILD_DIR / "mol_data_with_names.csv"
FAILED_CSV = BUILD_DIR / "FAILED_NAMES.csv"
SUMMARY_MD = BUILD_DIR / f"chemical_names_summary_{TIMESTAMP}.md"
LOG_FILE = BUILD_DIR / f"chemical_names_log_{TIMESTAMP}.txt"

VERBOSE = True         # lots of progress info
SLEEP_PUBCHEM = 0.20   # seconds between PubChem hits (rate limiting)
LOG_EVERY = 100        # progress line every N rows

# ----------------------------------------------------------------------
# LOGGING
# ----------------------------------------------------------------------
_log_messages: List[str] = []
_stats: Dict[str, int] = {}


def _timestamp_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str, force: bool = False) -> None:
    timestamped = f"[{_timestamp_str()}] {msg}"
    _log_messages.append(timestamped)
    if VERBOSE or force:
        print(timestamped, flush=True)


def write_log_file(log_path: Path):
    """Write all log messages to a file."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(_log_messages))
    print(f"[INFO] Log file written -> {log_path}")


# ----------------------------------------------------------------------
# SUMMARY MARKDOWN GENERATOR
# ----------------------------------------------------------------------
def generate_summary_markdown(stats: Dict, out_path: Path):
    """Generate a markdown summary of the chemical names lookup run."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    total = stats.get('total', 0)
    ok = stats.get('ok', 0)
    fail = stats.get('fail', 0)
    placeholder = stats.get('placeholder', 0)
    truly_enriched = stats.get('truly_enriched', ok)
    
    # Calculate rates
    rate = (ok / total * 100) if total > 0 else 0.0
    placeholder_rate = (placeholder / total * 100) if total > 0 else 0.0
    true_rate = (truly_enriched / total * 100) if total > 0 else 0.0
    
    lines = [
        f"# Chemical Names Pipeline Summary (pip1c-4)",
        f"",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"",
        f"## Configuration",
        f"",
        f"| Setting | Value |",
        f"|---------|-------|",
        f"| Input File | `{stats.get('input_file', 'N/A')}` |",
        f"| Build Directory | `{stats.get('build_dir', 'N/A')}` |",
        f"| PubChem Delay | {SLEEP_PUBCHEM}s |",
        f"",
        f"## Input Quality (from pip1c-3)",
        f"",
        f"| Metric | Count | Percentage |",
        f"|--------|-------|------------|",
        f"| **Total Rows** | {total:,} | 100% |",
        f"| Rows with valid SMILES | {total - placeholder:,} | {((total - placeholder) / total * 100) if total else 0:.2f}% |",
        f"| ⚠️ Placeholder ('*') entries | {placeholder:,} | {placeholder_rate:.2f}% |",
        f"",
        f"## PubChem Lookup Results",
        f"",
        f"| Metric | Count | Percentage |",
        f"|--------|-------|------------|",
        f"| ✅ Names found (truly enriched) | {ok:,} | {rate:.2f}% |",
        f"| ❌ PubChem lookup failed | {fail:,} | {(fail / total * 100) if total else 0:.2f}% |",
        f"| ⚠️ Skipped (placeholder) | {placeholder:,} | {placeholder_rate:.2f}% |",
        f"",
        f"## Output Files",
        f"",
        f"| File | Description |",
        f"|------|-------------|",
        f"| `{FINAL_CSV.name}` | All rows with IUPAC_NAME and COMMON_NAME (including placeholders) |",
        f"| `{FAILED_CSV.name}` | Rows where PubChem lookup failed (excludes placeholders) |",
        f"| `{LOG_FILE.name}` | Detailed processing log |",
        f"",
    ]
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    log(f"[SUMMARY] Wrote markdown summary -> {out_path}")


# ----------------------------------------------------------------------
# PubChem API
# ----------------------------------------------------------------------
_PUBCHEM_CACHE: dict[str, tuple[str, str]] = {}   # SMILES -> (iupac, title)


def pubchem_names(smiles: str) -> tuple[str, str]:
    """
    Query PubChem for IUPAC name and title (common name) given a SMILES string.
    
    Returns:
        tuple of (iupac_name, common_name)
    
    Raises:
        RuntimeError if the query fails
    """
    if smiles in _PUBCHEM_CACHE:
        return _PUBCHEM_CACHE[smiles]

    # The SMILES is sent as POST form data, NOT in the URL path: PubChem's router
    # un-escapes %2F back into '/', so every stereo SMILES ('/' or '\') sent in the
    # path answered "HTTP 400 - Unable to standardize the given structure"
    # (243 of the 255 historical FAILED_NAMES were exactly this request bug).
    url = (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound"
        "/smiles/property/IUPACName,Title/JSON"
    )
    iupac = title = ""
    try:
        r = requests.post(url, data={"smiles": smiles}, timeout=20)
        if r.status_code == 200:
            data: dict[str, Any] = r.json()
            props = data["PropertyTable"]["Properties"][0]
            iupac = props.get("IUPACName", "")
            title = props.get("Title", "")
        else:
            raise RuntimeError(f"HTTP {r.status_code}")
    except Exception as exc:
        raise RuntimeError(f"PubChem query failed: {exc}") from exc

    _PUBCHEM_CACHE[smiles] = (iupac, title)
    time.sleep(SLEEP_PUBCHEM)
    return iupac, title


# ----------------------------------------------------------------------
# Main processing
# ----------------------------------------------------------------------
def process_names(
    rows: List[Dict[str, str]],
    fieldnames: list[str],
) -> tuple[List[Dict[str, str]], List[Dict[str, str]], Dict[str, int]]:
    """
    Process rows to add IUPAC_NAME and COMMON_NAME via PubChem.
    
    Returns:
        - list of all rows (with names added where possible)
        - list of failed rows
        - stats dict
    """
    new_cols = ["IUPAC_NAME", "COMMON_NAME"]
    all_rows: List[Dict[str, str]] = []
    fail_rows: List[Dict[str, str]] = []
    
    n_total = n_ok = n_fail = n_placeholder = n_skipped = 0
    
    for row in rows:
        n_total += 1
        
        # Initialize new columns
        for c in new_cols:
            row.setdefault(c, "")
        
        smiles = row.get("SMILES", "")
        
        # Handle placeholder entries from pip1c-2 ("*" means no valid molblock)
        if smiles == "*":
            # Keep placeholder value, skip PubChem query
            row["IUPAC_NAME"] = "*"
            row["COMMON_NAME"] = "*"
            row["ERROR_NAMES"] = "Placeholder entry (no valid molblock from pip1c-2)"
            all_rows.append(row)
            n_placeholder += 1
        elif not smiles:
            row["ERROR_NAMES"] = "SMILES missing - cannot query PubChem"
            all_rows.append(row)
            fail_rows.append(row)
            n_fail += 1
        else:
            try:
                iupac, title = pubchem_names(smiles)
                row["IUPAC_NAME"] = iupac
                row["COMMON_NAME"] = title
                all_rows.append(row)
                n_ok += 1
            except Exception as exc:
                row["ERROR_NAMES"] = str(exc)
                all_rows.append(row)
                fail_rows.append(row)
                n_fail += 1
        
        if LOG_EVERY and n_total % LOG_EVERY == 0:
            log(f"... {n_total:,} processed  (OK: {n_ok:,}  Fail: {n_fail:,}  Placeholder: {n_placeholder:,})")
    
    log(f"Processing finished  ->  OK: {n_ok:,}  Fail: {n_fail:,}  Placeholder: {n_placeholder:,}")
    
    return all_rows, fail_rows, {
        'total': n_total,
        'ok': n_ok,
        'fail': n_fail,
        'placeholder': n_placeholder,
        'truly_enriched': n_ok,
    }


def main() -> None:
    print("=" * 70)
    print("NIST SRD 46 Chemical Names Pipeline (pip1c-4)")
    print("=" * 70)
    
    # Print configuration
    log(f"[CONFIG] CODE_ROOT: {CODE_ROOT}")
    log(f"[CONFIG] INPUT_CSV: {INPUT_CSV}")
    log(f"[CONFIG] BUILD_DIR: {BUILD_DIR}")
    log(f"[CONFIG] Input exists: {INPUT_CSV.exists()}")
    log(f"[CONFIG] PubChem delay: {SLEEP_PUBCHEM}s per query")
    
    if not INPUT_CSV.exists():
        log(f"ERROR: Input file not found: {INPUT_CSV}", force=True)
        sys.exit(1)
    
    # Create build directory
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load input CSV
    log(f"\n[LOAD] Reading input CSV: {INPUT_CSV}")
    with INPUT_CSV.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)
    
    initial_rows = len(rows)
    log(f"[LOAD] Loaded {initial_rows:,} rows")
    
    # Estimate time
    est_time = initial_rows * SLEEP_PUBCHEM
    log(f"[INFO] Estimated time: ~{est_time/60:.1f} minutes ({SLEEP_PUBCHEM}s delay per query)")
    
    print("\n[STEP 1] Querying PubChem for chemical names...")
    
    all_rows, fail_rows, stats = process_names(rows, fieldnames)
    
    # Extend fieldnames for output
    extended_fieldnames = fieldnames.copy()
    for col in ["IUPAC_NAME", "COMMON_NAME"]:
        if col not in extended_fieldnames:
            extended_fieldnames.append(col)
    
    fail_fieldnames = extended_fieldnames + ["ERROR_NAMES"]
    
    # Write final enriched CSV (all rows including placeholders)
    print("\n[STEP 2] Writing output files...")
    log(f"[FINAL] Writing enriched CSV: {FINAL_CSV}")
    with FINAL_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=extended_fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for row in all_rows:
            writer.writerow({k: row.get(k, "") for k in extended_fieldnames})
    log(f"[FINAL] Wrote {len(all_rows):,} rows to {FINAL_CSV.name}")
    
    # Write failed CSV (excludes placeholders - only actual PubChem failures)
    log(f"[FAILED] Writing failed CSV: {FAILED_CSV}")
    with FAILED_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fail_fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for row in fail_rows:
            writer.writerow({k: row.get(k, "") for k in fail_fieldnames})
    log(f"[FAILED] Wrote {len(fail_rows):,} rows to {FAILED_CSV.name}")
    
    # Prepare summary stats
    summary_stats = {
        'input_file': str(INPUT_CSV),
        'build_dir': str(BUILD_DIR),
        'total': stats['total'],
        'ok': stats['ok'],
        'fail': stats['fail'],
        'placeholder': stats.get('placeholder', 0),
        'truly_enriched': stats.get('truly_enriched', stats['ok']),
    }
    
    # Generate summary markdown
    print("\n[STEP 3] Generating summary markdown...")
    generate_summary_markdown(summary_stats, SUMMARY_MD)
    
    # Write log file
    print("\n[STEP 4] Writing log file...")
    write_log_file(LOG_FILE)
    
    # Print final summary with placeholder breakdown
    total = stats['total']
    ok = stats['ok']
    fail = stats['fail']
    placeholder = stats.get('placeholder', 0)
    truly_enriched = stats.get('truly_enriched', ok)
    
    rate = (ok / total * 100) if total > 0 else 0.0
    placeholder_rate = (placeholder / total * 100) if total > 0 else 0.0
    
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    print(f"  Total rows:          {total:,}")
    print()
    print("INPUT QUALITY (from pip1c-3):")
    print(f"  Rows with valid SMILES: {total - placeholder:,} ({((total - placeholder) / total * 100) if total else 0:.2f}%)")
    print(f"  ⚠️ Placeholder ('*'):   {placeholder:,} ({placeholder_rate:.2f}%)")
    print()
    print("PUBCHEM LOOKUP RESULTS:")
    print(f"  ✅ Names found:      {ok:,} ({rate:.2f}%)")
    print(f"  ❌ Lookup failed:    {fail:,} ({(fail / total * 100) if total else 0:.2f}%)")
    print(f"  ⚠️ Skipped (placeh): {placeholder:,} ({placeholder_rate:.2f}%)")
    print("=" * 70)
    print(f"Final enriched file: {FINAL_CSV}")
    print(f"Failed file:         {FAILED_CSV}")
    print("=" * 70)
    print("[DONE] Chemical names pipeline complete.")
    print("=" * 70)


# ----------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) >= 2:
        # allow overriding the initial input from the CLI
        INPUT_CSV = Path(sys.argv[1])
    main()
