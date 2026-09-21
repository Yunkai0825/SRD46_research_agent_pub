
"""
SRD46_pd_molfile_decoding-pip-1.py
----------------------------------

Pipeline 1c-1: Molfile Decoding

Read a CSV with a column `mol_string_encoded`,
decode that field (URL-decode → base64 → zlib-inflate → MDL molfile),
and write a new CSV that contains all original columns + a MOLBLOCK column.

Everything is quoted (csv.QUOTE_ALL) so embedded new-lines are preserved.

I/O Configuration:
- Input:  _input/SRD46_SQL_and_CSV/Export/CSV files/mol_data__12.csv
- Output: pip1c_parse_liganden_moldata_pKa_SRD46/_build/pip1c_1_molfile_output/
"""

import csv
import sys
import urllib.parse
import base64
import zlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# ────────────────────────────────────────────────────────────
# 1. PATH CONFIGURATION
# ────────────────────────────────────────────────────────────
now = datetime.now()
TIMESTAMP = now.strftime("%Y-%m-%d-%H-%M-%S")

CODE_ROOT = Path(__file__).resolve().parent
PIPELINE_ROOT = CODE_ROOT.parent  # pip1c_parse_liganden_moldata_pKa_SRD46
PROJECT_ROOT = PIPELINE_ROOT.parent.parent  # NIST_SRD46_Correction_and_Parser

# Input: from _input/SRD46_SQL_and_CSV/Export/CSV files/
INPUT_DIR = PROJECT_ROOT / "_input" / "SRD46_SQL_and_CSV" / "Export" / "CSV files"
INPUT_FILE = INPUT_DIR / "mol_data__12.csv"

# Build: all outputs go to _build/pip1c_1_molfile_output/
BUILD_DIR = PIPELINE_ROOT / "_build" / "pip1c_1_molfile_output"

# Output files
OUTPUT_CSV = BUILD_DIR / "mol_data_with_molblock.csv"
FAILED_DUPLICATES_CSV = BUILD_DIR / "FAILED_duplicate_ligandenNR.csv"
SUMMARY_MD = BUILD_DIR / f"molfile_decoding_summary_{TIMESTAMP}.md"
LOG_FILE = BUILD_DIR / f"molfile_decoding_log_{TIMESTAMP}.txt"

VERBOSE_RUN = True
LOG_EVERY_N_ROWS = 1_000  # progress note every N rows (set 0 → disable)

# ────────────────────────────────────────────────────────────
# 2. LOGGING HELPERS
# ────────────────────────────────────────────────────────────
_log_messages: List[str] = []  # Store log messages for file output


def _timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str, force: bool = False):
    """Time-stamped logger that honours VERBOSE_RUN."""
    timestamped = f"[{_timestamp()}] {msg}"
    _log_messages.append(timestamped)
    if VERBOSE_RUN or force:
        print(timestamped, flush=True)


def write_log_file(log_path: Path):
    """Write all log messages to a file."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(_log_messages))
    print(f"[INFO] Log file written → {log_path}")


# ────────────────────────────────────────────────────────────
# 3. DECODER
# ────────────────────────────────────────────────────────────
def decode_mol_string(encoded: str) -> str:
    """Decode mol_string_encoded: URL-decode → base64 → zlib-inflate → MDL molfile."""
    raw = zlib.decompress(base64.b64decode(urllib.parse.unquote(encoded)))
    try:
        return raw.decode("utf-8").rstrip("\n")
    except UnicodeDecodeError:
        # lossless mapping of bytes→codepoints; preserves 0xB4 as U+00B4
        return raw.decode("latin-1").rstrip("\n")


# ────────────────────────────────────────────────────────────
# 4. SUMMARY MARKDOWN GENERATOR
# ────────────────────────────────────────────────────────────
def generate_summary_markdown(
    stats: Dict,
    out_path: Path,
):
    """Generate a markdown summary of the molfile decoding run."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    lines = [
        f"# Molfile Decoding Pipeline Summary",
        f"",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"",
        f"## Configuration",
        f"",
        f"| Setting | Value |",
        f"|---------|-------|",
        f"| Input File | `{stats.get('input_file', 'N/A')}` |",
        f"| Output CSV | `{stats.get('output_file', 'N/A')}` |",
        f"| Build Directory | `{stats.get('build_dir', 'N/A')}` |",
        f"",
        f"## Results",
        f"",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Total Rows | {stats.get('total_rows', 0):,} |",
        f"| Successfully Decoded | {stats.get('success_count', 0):,} |",
        f"| Failed to Decode | {stats.get('fail_count', 0):,} |",
        f"| Duplicate ligandenNR (skipped) | {stats.get('duplicate_count', 0):,} |",
        f"| Unique ligandenNR in output | {stats.get('success_count', 0) - stats.get('fail_count', 0):,} |",
        f"| Success Rate | {stats.get('success_rate', 0):.2f}% |",
        f"",
    ]
    
    # Add duplicate details if any
    dup_ids = stats.get('duplicate_ligandenNR', [])
    if dup_ids:
        lines.extend([
            f"## Duplicate ligandenNR Entries (Removed)",
            f"",
            f"The following `ligandenNR` values had duplicate entries (only first kept):",
            f"",
        ])
        for did in dup_ids:
            lines.append(f"- `{did}`")
        lines.append("")
    
    # Add failed row details if any
    failed_ids = stats.get('failed_ids', [])
    if failed_ids:
        lines.extend([
            f"## Failed Rows",
            f"",
            f"The following `mol_dataID` values failed to decode:",
            f"",
        ])
        for fid in failed_ids[:20]:  # Show first 20
            lines.append(f"- `{fid}`")
        if len(failed_ids) > 20:
            lines.append(f"- ... and {len(failed_ids) - 20} more")
        lines.append("")
    
    lines.extend([
        f"## Output Files",
        f"",
        f"- **CSV with molblock:** `{stats.get('output_file', 'N/A')}`",
        f"- **Log file:** `{stats.get('log_file', 'N/A')}`",
        f"- **This summary:** `{out_path.name}`",
        f"",
    ])
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    log(f"[SUMMARY] Wrote markdown summary → {out_path}")


# ────────────────────────────────────────────────────────────
# 5. MAIN PROCESSING
# ────────────────────────────────────────────────────────────
def process_file(in_csv: Path, out_csv: Path, failed_dups_csv: Path) -> Dict:
    """
    Process the mol_data CSV and decode molblock strings.
    
    Also detects and removes duplicate ligandenNR entries, keeping only the first.
    Duplicates are written to a separate FAILED file.
    
    Returns:
        Dict with statistics about the run.
    """
    log(f"Input : {in_csv}")
    log(f"Output: {out_csv}")
    log(f"Failed duplicates: {failed_dups_csv}")
    
    # Ensure output directory exists
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    
    stats = {
        'input_file': str(in_csv),
        'output_file': str(out_csv),
        'build_dir': str(out_csv.parent),
        'total_rows': 0,
        'success_count': 0,
        'fail_count': 0,
        'failed_ids': [],
        'duplicate_count': 0,
        'duplicate_ligandenNR': [],
    }

    with in_csv.open(newline="", encoding="utf-8") as f_in, \
         out_csv.open("w", newline="", encoding="utf-8") as f_out, \
         failed_dups_csv.open("w", newline="", encoding="utf-8") as f_dups:

        reader = csv.DictReader(f_in)
        if "mol_string_encoded" not in reader.fieldnames:
            log("ERROR: column 'mol_string_encoded' not found!", force=True)
            sys.exit(1)
        if "ligandenNR" not in reader.fieldnames:
            log("ERROR: column 'ligandenNR' not found!", force=True)
            sys.exit(1)

        fieldnames_out = list(reader.fieldnames) + ["molblock"]
        writer = csv.DictWriter(
            f_out,
            fieldnames=fieldnames_out,
            quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()
        
        # Writer for duplicate entries (with reason column)
        fieldnames_dups = list(reader.fieldnames) + ["molblock", "duplicate_reason"]
        writer_dups = csv.DictWriter(
            f_dups,
            fieldnames=fieldnames_dups,
            quoting=csv.QUOTE_ALL,
        )
        writer_dups.writeheader()
        
        # Track seen ligandenNR to detect duplicates
        seen_ligandenNR: Dict[str, int] = {}  # ligandenNR -> first mol_dataID

        idx = 0
        for idx, row in enumerate(reader, start=1):
            ligandenNR = row.get('ligandenNR', '')
            mol_dataID = row.get('mol_dataID', f'row_{idx}')
            
            # Check for duplicate ligandenNR
            if ligandenNR and ligandenNR in seen_ligandenNR:
                first_id = seen_ligandenNR[ligandenNR]
                log(f"WARNING: Duplicate ligandenNR={ligandenNR} at mol_dataID={mol_dataID} "
                    f"(first seen at mol_dataID={first_id}) - SKIPPING")
                
                # Decode molblock anyway for the record
                try:
                    row["molblock"] = decode_mol_string(row["mol_string_encoded"])
                except Exception:
                    row["molblock"] = ""
                
                row["duplicate_reason"] = f"Duplicate of ligandenNR={ligandenNR}, first mol_dataID={first_id}"
                writer_dups.writerow(row)
                stats['duplicate_count'] += 1
                if ligandenNR not in stats['duplicate_ligandenNR']:
                    stats['duplicate_ligandenNR'].append(ligandenNR)
                continue  # Skip this row, don't write to main output
            
            # Record this ligandenNR as seen
            if ligandenNR:
                seen_ligandenNR[ligandenNR] = mol_dataID
            try:
                row["molblock"] = decode_mol_string(row["mol_string_encoded"])
                stats['success_count'] += 1
            except Exception as exc:
                mol_id = row.get('mol_dataID', f'row_{idx}')
                log(f"WARNING: row {idx} (id={mol_id}) failed to decode: {exc}")
                row["molblock"] = ""
                stats['fail_count'] += 1
                stats['failed_ids'].append(mol_id)

            writer.writerow(row)

            # lightweight progress indicator
            if LOG_EVERY_N_ROWS and idx % LOG_EVERY_N_ROWS == 0:
                log(f"... processed {idx:,} rows")

            # optional preview of first three rows
            if idx <= 3:
                log(f"Decoded row {idx} – {len(row['molblock'].splitlines())} "
                    f"lines in molfile")

        stats['total_rows'] = idx
        if stats['total_rows'] > 0:
            stats['success_rate'] = (stats['success_count'] / stats['total_rows']) * 100
        else:
            stats['success_rate'] = 0.0
            
        log(f"Finished. Total rows: {idx:,}")
    
    return stats


# ────────────────────────────────────────────────────────────
# 6. SCRIPT ENTRY POINT
# ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 70)
    print("NIST SRD 46 Molfile Decoding Pipeline (pip1c-1)")
    print("=" * 70)
    
    # Print configuration
    log(f"[CONFIG] CODE_ROOT: {CODE_ROOT}")
    log(f"[CONFIG] INPUT_FILE: {INPUT_FILE}")
    log(f"[CONFIG] BUILD_DIR: {BUILD_DIR}")
    log(f"[CONFIG] Input exists: {INPUT_FILE.exists()}")
    
    if not INPUT_FILE.exists():
        log(f"ERROR: Input file not found: {INPUT_FILE}", force=True)
        sys.exit(1)
    
    # Create build directory
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    
    # Allow overriding paths from the command line
    input_path = INPUT_FILE
    output_path = OUTPUT_CSV
    
    if len(sys.argv) >= 2:
        input_path = Path(sys.argv[1])
    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2])

    try:
        # Process file
        print("\n[STEP 1] Decoding molfile strings (with duplicate detection)...")
        stats = process_file(input_path, output_path, FAILED_DUPLICATES_CSV)
        
        # Add log file path to stats
        stats['log_file'] = str(LOG_FILE)
        
        # Generate summary markdown
        print("\n[STEP 2] Generating summary markdown...")
        generate_summary_markdown(stats, SUMMARY_MD)
        
        # Write log file
        print("\n[STEP 3] Writing log file...")
        write_log_file(LOG_FILE)
        
        # Print final summary
        print("\n" + "=" * 70)
        print("FINAL SUMMARY")
        print("=" * 70)
        print(f"  Total rows:         {stats['total_rows']:,}")
        print(f"  Decoded (unique):   {stats['success_count']:,}")
        print(f"  Failed to decode:   {stats['fail_count']:,}")
        print(f"  Duplicates removed: {stats['duplicate_count']:,}")
        if stats['duplicate_ligandenNR']:
            print(f"  Duplicate IDs:      {stats['duplicate_ligandenNR']}")
        print(f"  Success rate:       {stats['success_rate']:.2f}%")
        print("=" * 70)
        print("[DONE] Molfile decoding pipeline complete.")
        print("=" * 70)
        
    except Exception as e:
        log(f"FATAL ERROR: {e}", force=True)
        write_log_file(LOG_FILE)
        sys.exit(1)