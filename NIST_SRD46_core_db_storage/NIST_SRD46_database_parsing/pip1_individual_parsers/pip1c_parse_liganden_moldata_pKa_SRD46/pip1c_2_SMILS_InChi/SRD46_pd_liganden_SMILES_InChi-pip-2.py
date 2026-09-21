"""
SRD46_pd_liganden_SMILES_InChi-pip-2.py
---------------------------------------

Pipeline 1c-2: SMILES/InChI/Composition Enrichment

Four-stage enrichment pipeline:

Stage 0 (Recovery): For entries with missing/empty molblock, attempt to 
    recover structure using chemical name lookup via PubChem.
    -> FIXED_by_name.csv (recovered entries)
    -> FAILED_no_molblock.csv (unrecoverable entries)

Stage 1-3 (Enrichment): For entries with valid molblock:
    1. add  InChI          ->  FAILED_INCHI.csv (failed only)
    2. add  SMILES         ->  FAILED_SMILES.csv (failed only)
    3. add  COMPOSITION    ->  final enriched CSV + FAILED_FORMULA.csv

The final output contains both:
- Entries with original molblock from pip1c-1
- Entries recovered via chemical name lookup

I/O Configuration:
- Input:  _build/pip1c_1_molfile_output/mol_data_with_molblock.csv
- Input:  _input/SRD46_SQL_and_CSV/Export/CSV files/liganden__8__7.csv (for names)
- Output: _build/pip1c_2_SMILS_InChi_output/
"""

import csv
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import json
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from rdkit import Chem, RDLogger
from rdkit.Chem import rdMolDescriptors

# ----------------------------------------------------------------------
# PATH CONFIGURATION
# ----------------------------------------------------------------------
now = datetime.now()
TIMESTAMP = now.strftime("%Y-%m-%d-%H-%M-%S")

CODE_ROOT = Path(__file__).resolve().parent
PIPELINE_ROOT = CODE_ROOT.parent  # pip1c_parse_liganden_moldata_pKa_SRD46
PROJECT_ROOT = PIPELINE_ROOT.parent.parent  # NIST_SRD46_Correction_and_Parser

# Input: from pip1c_1_molfile_output (output of previous stage)
INPUT_DIR = PIPELINE_ROOT / "_build" / "pip1c_1_molfile_output"
INPUT_CSV = INPUT_DIR / "mol_data_with_molblock.csv"

# Input: liganden file with chemical names (for recovery)
LIGANDEN_CSV = PROJECT_ROOT / "_input" / "SRD46_SQL_and_CSV" / "Export" / "CSV files" / "liganden__8__7.csv"

# Build: all outputs go to _build/pip1c_2_SMILS_InChi_output/
BUILD_DIR = PIPELINE_ROOT / "_build" / "pip1c_2_SMILS_InChi_output"

# Output files
SUMMARY_MD = BUILD_DIR / f"smiles_inchi_summary_{TIMESTAMP}.md"
LOG_FILE = BUILD_DIR / f"smiles_inchi_log_{TIMESTAMP}.txt"
FINAL_CSV = BUILD_DIR / "mol_data_enriched.csv"

# Recovery stage output files
FIXED_BY_NAME_CSV = BUILD_DIR / "FIXED_by_name.csv"
FAILED_NO_MOLBLOCK_CSV = BUILD_DIR / "FAILED_no_molblock.csv"

VERBOSE = True       # lots of progress info
LOG_EVERY = 100       # progress line every N rows
PUBCHEM_DELAY = 0.25  # delay between PubChem API calls (seconds)

# ----------------------------------------------------------------------
# LOGGING
# ----------------------------------------------------------------------
_log_messages: List[str] = []
_stage_stats: Dict[str, Dict] = {}  # Track stats per stage


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
    """Generate a markdown summary of the SMILES/InChI enrichment run."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Calculate actual enrichment stats (excluding placeholders)
    total = stats.get('total_output_rows', 0)
    truly_enriched = stats.get('truly_enriched_count', 0)
    placeholder_count = stats.get('placeholder_count', 0)
    true_success_rate = (truly_enriched / total * 100) if total > 0 else 0.0
    
    lines = [
        f"# SMILES/InChI Enrichment Pipeline Summary",
        f"",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"",
        f"## Configuration",
        f"",
        f"| Setting | Value |",
        f"|---------|-------|",
        f"| Input File | `{stats.get('input_file', 'N/A')}` |",
        f"| Liganden File | `{stats.get('liganden_file', 'N/A')}` |",
        f"| Build Directory | `{stats.get('build_dir', 'N/A')}` |",
        f"",
        f"## Data Sources",
        f"",
        f"| Source | Count |",
        f"|--------|-------|",
        f"| mol_data (with molblock) | {stats.get('initial_rows', 0):,} |",
        f"| Liganden total | {stats.get('total_liganden', 0):,} |",
        f"| Orphan liganden (no mol_data) | {stats.get('orphan_liganden_count', 0):,} |",
        f"",
        f"## Molblock Recovery (Stage 0)",
        f"",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Orphan liganden processed | {stats.get('orphan_liganden_count', 0):,} |",
        f"| Recovered via PubChem | {stats.get('recovered_count', 0):,} |",
        f"| Failed recovery (placeholder '*') | {stats.get('failed_recovery_count', 0):,} |",
        f"",
        f"## Enrichment Results (ACTUAL)",
        f"",
        f"| Metric | Count | Percentage |",
        f"|--------|-------|------------|",
        f"| **Total Output Rows** | {total:,} | 100% |",
        f"| ✅ Truly Enriched (valid InChI/SMILES/COMPOSITION) | {truly_enriched:,} | {true_success_rate:.2f}% |",
        f"| ⚠️ Placeholder ('*') entries | {placeholder_count:,} | {(placeholder_count/total*100) if total else 0:.2f}% |",
        f"",
        f"## Placeholder Breakdown",
        f"",
        f"| Column | Placeholder Count |",
        f"|--------|-------------------|",
        f"| InChI = '*' | {stats.get('inchi_placeholder_count', 0):,} |",
        f"| SMILES = '*' | {stats.get('smiles_placeholder_count', 0):,} |",
        f"| COMPOSITION = '*' | {stats.get('composition_placeholder_count', 0):,} |",
        f"",
        f"## Output Files",
        f"",
        f"### Final Enriched CSV",
        f"- `{stats.get('final_csv', 'N/A')}`",
        f"",
        f"### Recovery Stage CSVs",
        f"- **Recovered entries:** `{stats.get('fixed_by_name_csv', 'N/A')}`",
        f"- **Unrecoverable entries:** `{stats.get('failed_no_molblock_csv', 'N/A')}`",
        f"",
        f"### Log File",
        f"- `{stats.get('log_file', 'N/A')}`",
        f"",
    ]
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    log(f"[SUMMARY] Wrote markdown summary -> {out_path}")


# ----------------------------------------------------------------------
# PUBCHEM LOOKUP FUNCTIONS
# ----------------------------------------------------------------------
def pubchem_get_compound_by_name(name: str) -> Optional[Dict]:
    """
    Look up a compound by name on PubChem.
    Returns dict with CID, InChI, SMILES, and molblock (SDF) if found.
    Returns None if lookup fails.
    """
    if not name or not name.strip():
        return None
    
    # URL-encode the compound name
    encoded_name = urllib.parse.quote(name.strip())
    
    # Step 1: Get CID from compound name
    cid_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{encoded_name}/cids/JSON"
    
    try:
        with urllib.request.urlopen(cid_url, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
            cid_list = data.get("IdentifierList", {}).get("CID", [])
            if not cid_list:
                return None
            cid = cid_list[0]  # Take first match
    except urllib.error.HTTPError as exc:
        if exc.code == 404:          # PUGREST.NotFound: PubChem knows no compound by this name
            return None
        # 400/429/5xx: request or server problem, NOT "unknown name" -> caller must not cache a miss
        raise RuntimeError(f"PubChem name lookup failed for {name!r}: HTTP {exc.code}") from exc
    except Exception as exc:         # timeouts / connection errors -> transient, not a miss
        raise RuntimeError(f"PubChem name lookup failed for {name!r}: {exc}") from exc
    
    time.sleep(PUBCHEM_DELAY)
    
    # Step 2: Get properties (InChI, SMILES) for this CID
    props_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/property/InChI,CanonicalSMILES/JSON"
    
    try:
        with urllib.request.urlopen(props_url, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
            props = data.get("PropertyTable", {}).get("Properties", [{}])[0]
            inchi = props.get("InChI", "")
            smiles = props.get("CanonicalSMILES", "")
    except Exception:
        inchi = ""
        smiles = ""
    
    time.sleep(PUBCHEM_DELAY)
    
    # Step 3: Get SDF (molblock) for this CID
    sdf_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/SDF"
    
    try:
        with urllib.request.urlopen(sdf_url, timeout=15) as response:
            sdf_data = response.read().decode("utf-8")
            # SDF contains molblock followed by $$$$
            # Extract the molblock portion
            if "$$$$" in sdf_data:
                molblock = sdf_data.split("$$$$")[0].strip()
            else:
                molblock = sdf_data.strip()
    except Exception as exc:         # a CID exists but the SDF fetch failed -> transient, retry later
        raise RuntimeError(f"PubChem SDF fetch failed for CID {cid} ({name!r}): {exc}") from exc
    
    return {
        "CID": cid,
        "InChI": inchi,
        "SMILES": smiles,
        "molblock": molblock,
    }


def load_liganden_names(liganden_path: Path) -> Tuple[Dict[str, str], List[Dict[str, str]]]:
    """
    Load liganden file and create ligandenNR -> name_ligand lookup.
    Also returns all liganden rows for processing orphans.
    
    Returns:
        Tuple of (lookup_dict, all_liganden_rows)
        - lookup_dict: maps ligandenID (as string) to name_ligand
        - all_liganden_rows: list of all liganden rows as dicts
    """
    lookup = {}
    all_rows = []
    
    if not liganden_path.exists():
        log(f"[WARN] Liganden file not found: {liganden_path}")
        return lookup, all_rows
    
    with liganden_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # liganden file has 'ligandenID' as the key column
            lig_id = row.get("ligandenID", "").strip()
            name = row.get("name_ligand", "").strip()
            if lig_id:
                all_rows.append(row)
                if name:
                    lookup[lig_id] = name
    
    return lookup, all_rows


def recover_molblock_from_name(
    mol_data_rows: List[Dict[str, str]],
    all_liganden_rows: List[Dict[str, str]],
    liganden_lookup: Dict[str, str],
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], List[Dict[str, str]]]:
    """
    For rows with missing/empty molblock AND orphan liganden entries,
    attempt recovery using chemical name via PubChem.
    
    Args:
        mol_data_rows: Rows from mol_data CSV (from pip1c-1)
        all_liganden_rows: All liganden entries
        liganden_lookup: Dict mapping ligandenID -> name_ligand
    
    Returns:
        Tuple of (all_valid_rows, fixed_rows, failed_rows)
        - all_valid_rows: rows with valid molblock (original + recovered)
        - fixed_rows: rows that were recovered via PubChem
        - failed_rows: rows that could not be recovered
    """
    valid_rows = []
    fixed_rows = []
    failed_rows = []
    
    # Track which ligandenIDs are in mol_data
    mol_data_liganden_ids = set()
    for row in mol_data_rows:
        lig_nr = row.get("ligandenNR", "").strip()
        if lig_nr:
            mol_data_liganden_ids.add(lig_nr)
    
    n_with_molblock = 0
    n_missing_in_moldata = 0
    n_orphan_liganden = 0
    n_recovered = 0
    n_failed = 0
    
    # Phase 1: Process mol_data rows (check for invalid molblocks)
    log(f"\n[RECOVERY] Phase 1: Checking mol_data rows ({len(mol_data_rows):,} entries)...")
    
    for i, row in enumerate(mol_data_rows):
        molblock = row.get("molblock", "").strip()
        liganden_nr = row.get("ligandenNR", "").strip()
        
        # Check if molblock is valid (not empty and parses to a mol)
        has_valid_molblock = False
        if molblock:
            mol = mol_from_block(molblock)
            if mol is not None:
                has_valid_molblock = True
        
        if has_valid_molblock:
            # Row already has valid molblock, keep as-is
            valid_rows.append(row)
            n_with_molblock += 1
        else:
            # Missing or invalid molblock - attempt recovery
            n_missing_in_moldata += 1
            
            # Get chemical name from liganden lookup
            chem_name = liganden_lookup.get(liganden_nr, "")
            
            if chem_name:
                log(f"[RECOVERY] mol_data row {i+1}: ligandenNR={liganden_nr} -> name='{chem_name[:50]}...'")
                
                # Try PubChem lookup
                result = pubchem_get_compound_by_name(chem_name)
                
                if result and result.get("molblock"):
                    # Verify the recovered molblock is valid
                    recovered_mol = mol_from_block(result["molblock"])
                    if recovered_mol is not None:
                        # Success! Update the row
                        row["molblock"] = result["molblock"]
                        row["RECOVERY_SOURCE"] = "PubChem"
                        row["RECOVERY_CID"] = str(result.get("CID", ""))
                        row["RECOVERY_NAME"] = chem_name
                        
                        valid_rows.append(row)
                        fixed_rows.append(row.copy())
                        n_recovered += 1
                        log(f"[RECOVERY] ✓ Recovered ligandenNR={liganden_nr} via PubChem (CID={result.get('CID', '')})")
                        continue
            
            # Could not recover
            row["ERROR_RECOVERY"] = f"No valid molblock; name lookup failed (name='{chem_name}')"
            failed_rows.append(row)
            n_failed += 1
        
        # Progress logging
        if LOG_EVERY and (i + 1) % LOG_EVERY == 0:
            log(f"... {i+1:,} checked  (valid: {n_with_molblock:,}  recovered: {n_recovered:,}  failed: {n_failed:,})")
    
    # Phase 2: Process orphan liganden entries (not in mol_data)
    log(f"\n[RECOVERY] Phase 2: Processing orphan liganden entries...")
    
    orphan_count = 0
    for lig_row in all_liganden_rows:
        lig_id = lig_row.get("ligandenID", "").strip()
        
        # Skip if already in mol_data
        if lig_id in mol_data_liganden_ids:
            continue
        
        orphan_count += 1
        n_orphan_liganden += 1
        chem_name = lig_row.get("name_ligand", "").strip()
        
        # Create a new row for this orphan liganden
        new_row = {
            "ligandenNR": lig_id,
            "mol_dataID": "",  # No mol_data record
            "mol_string_encoded": "",
            "molblock": "",
            "ORPHAN_LIGANDEN": "True",
        }
        
        if chem_name:
            log(f"[RECOVERY] Orphan {orphan_count}: ligandenID={lig_id} -> name='{chem_name[:50]}...'")
            
            # Try PubChem lookup
            result = pubchem_get_compound_by_name(chem_name)
            
            if result and result.get("molblock"):
                # Verify the recovered molblock is valid
                recovered_mol = mol_from_block(result["molblock"])
                if recovered_mol is not None:
                    # Success! Update the row
                    new_row["molblock"] = result["molblock"]
                    new_row["RECOVERY_SOURCE"] = "PubChem"
                    new_row["RECOVERY_CID"] = str(result.get("CID", ""))
                    new_row["RECOVERY_NAME"] = chem_name
                    
                    valid_rows.append(new_row)
                    fixed_rows.append(new_row.copy())
                    n_recovered += 1
                    log(f"[RECOVERY] ✓ Recovered orphan ligandenID={lig_id} via PubChem (CID={result.get('CID', '')})")
                    continue
        
        # Could not recover
        new_row["ERROR_RECOVERY"] = f"Orphan liganden; name lookup failed (name='{chem_name}')"
        failed_rows.append(new_row)
        n_failed += 1
        
        # Progress logging
        if LOG_EVERY and orphan_count % LOG_EVERY == 0:
            log(f"... {orphan_count:,} orphans checked  (recovered: {n_recovered - n_with_molblock:,}  failed: {n_failed - n_missing_in_moldata:,})")
    
    log(f"\n[RECOVERY] Summary:")
    log(f"  mol_data with valid molblock: {n_with_molblock:,}")
    log(f"  mol_data with missing molblock: {n_missing_in_moldata:,}")
    log(f"  Orphan liganden (no mol_data): {n_orphan_liganden:,}")
    log(f"  Total recovered via PubChem:  {n_recovered:,}")
    log(f"  Total failed recovery:        {n_failed:,}")
    log(f"  Total valid for enrichment:   {len(valid_rows):,}")
    
    return valid_rows, fixed_rows, failed_rows


# ----------------------------------------------------------------------
# PIPELINE STAGES DEFINITION
# ----------------------------------------------------------------------
# Three stages: inchi, smiles, formula
# Names stage moved to pip1c-4
PIPELINE: list[tuple[str, list[str], Callable[[dict[str, str]], None]]] = [
    ("inchi",   ["InChI"],       None),
    ("smiles",  ["SMILES"],      None),
    ("formula", ["COMPOSITION"], None),
]

# Flags we want *on* (everything except the valence check)
RDLogger.DisableLog("rdApp.error")          # silence noisy valence logs
PARTIAL_SAN = (Chem.SanitizeFlags.SANITIZE_ALL ^
               Chem.SanitizeFlags.SANITIZE_PROPERTIES)   # skip valence test

# silence RDKit's tsunami of warnings
RDLogger.DisableLog("rdApp.warning")


# ----------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------
def mol_from_block(mb: str) -> Chem.Mol | None:
    # fast path: try normal load
    m = Chem.MolFromMolBlock(mb, sanitize=True)
    if m:
        return m
    # fallback: load unsanitised, then run partial sanitisation
    m = Chem.MolFromMolBlock(mb, sanitize=False, strictParsing=False)
    if not m:
        return None
    Chem.SanitizeMol(m, sanitizeOps=PARTIAL_SAN, catchErrors=True)
    m.UpdatePropertyCache(strict=False)
    return m


def calc_inchi(mol: Chem.Mol) -> str:
    return Chem.MolToInchi(mol, treatWarningAsError=False)


def calc_smiles(mol: Chem.Mol) -> str:
    return Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)


def calc_formula(mol: Chem.Mol) -> str:
    return rdMolDescriptors.CalcMolFormula(mol)


# ----------------------------------------------------------------------
# Core : "run one stage" - processes rows, returns ok_rows list, writes failed CSV
# ----------------------------------------------------------------------
def run_stage(
    rows: List[Dict[str, str]],
    out_fail: Path,
    *,
    new_cols: list[str],
    worker: Callable[[dict[str, str]], None],
    err_tag: str,
    fieldnames: list[str],
) -> tuple[List[Dict[str, str]], Dict[str, int]]:
    """
    Process rows in memory, write only failed rows to CSV.
    
    Returns:
        - list of successful rows (with new columns added)
        - dict with 'total', 'ok', 'fail' counts
    """
    log(f"\n-- Stage {err_tag.upper():<8}  -> {out_fail.name} (failed only)")

    ok_rows: List[Dict[str, str]] = []
    n_total = n_ok = n_fail = 0

    # Ensure output directory exists
    out_fail.parent.mkdir(parents=True, exist_ok=True)

    # Extended fieldnames for this stage
    extended_fieldnames = fieldnames + [c for c in new_cols if c not in fieldnames]
    fail_fieldnames = extended_fieldnames + [f"ERROR_{err_tag.upper()}"]

    with out_fail.open("w", newline="", encoding="utf-8") as f_fail:
        fail_writer = csv.DictWriter(
            f_fail,
            fieldnames=fail_fieldnames,
            quoting=csv.QUOTE_ALL,
        )
        fail_writer.writeheader()

        for row in rows:
            n_total += 1
            # make sure the new cols exist before we try to write
            for c in new_cols:
                row.setdefault(c, "")

            try:
                worker(row)
            except Exception as exc:
                row[f"ERROR_{err_tag.upper()}"] = str(exc)
                fail_writer.writerow(row)
                n_fail += 1
            else:
                ok_rows.append(row)
                n_ok += 1

            if LOG_EVERY and n_total % LOG_EVERY == 0:
                log(f"... {n_total:,} processed  (OK: {n_ok:,}  Fail: {n_fail:,})")

    log(f"Stage finished  ->  OK: {n_ok:,}  Fail: {n_fail:,}")
    
    # Store stage stats
    _stage_stats[err_tag] = {'total': n_total, 'ok': n_ok, 'fail': n_fail}
    
    return ok_rows, {'total': n_total, 'ok': n_ok, 'fail': n_fail}


# ----------------------------------------------------------------------
# Definitions for the three stages
# ----------------------------------------------------------------------

def stage_inchi(row):
    """Add InChI to row. Uses '*' as placeholder if molblock is invalid."""
    molblock = row.get("molblock", "").strip()
    if not molblock:
        row["InChI"] = "*"
        return
    mol = mol_from_block(molblock)
    if mol is None:
        row["InChI"] = "*"
        return
    row["InChI"] = Chem.MolToInchi(mol, treatWarningAsError=False) or "*"


def stage_smiles(row: dict[str, str]) -> None:
    """Add SMILES to row. Uses '*' as placeholder if molblock is invalid."""
    molblock = row.get("molblock", "").strip()
    if not molblock:
        row["SMILES"] = "*"
        return
    mol = mol_from_block(molblock)
    if mol is None:
        row["SMILES"] = "*"
        return
    row["SMILES"] = calc_smiles(mol) or "*"


def stage_formula(row: dict[str, str]) -> None:
    """Add COMPOSITION to row. Uses '*' as placeholder if molblock is invalid."""
    molblock = row.get("molblock", "").strip()
    if not molblock:
        row["COMPOSITION"] = "*"
        return
    mol = mol_from_block(molblock)
    if mol is None:
        row["COMPOSITION"] = "*"
        return
    row["COMPOSITION"] = calc_formula(mol) or "*"


# plug the real worker callables into the pipeline declared at the top
PIPELINE[0] = PIPELINE[0][:2] + (stage_inchi,)
PIPELINE[1] = PIPELINE[1][:2] + (stage_smiles,)
PIPELINE[2] = PIPELINE[2][:2] + (stage_formula,)


# ----------------------------------------------------------------------
# Run everything
# ----------------------------------------------------------------------
def main() -> None:
    print("=" * 70)
    print("NIST SRD 46 SMILES/InChI Enrichment Pipeline (pip1c-2)")
    print("=" * 70)
    
    # Print configuration
    log(f"[CONFIG] CODE_ROOT: {CODE_ROOT}")
    log(f"[CONFIG] INPUT_CSV: {INPUT_CSV}")
    log(f"[CONFIG] LIGANDEN_CSV: {LIGANDEN_CSV}")
    log(f"[CONFIG] BUILD_DIR: {BUILD_DIR}")
    log(f"[CONFIG] Input exists: {INPUT_CSV.exists()}")
    log(f"[CONFIG] Liganden exists: {LIGANDEN_CSV.exists()}")
    
    if not INPUT_CSV.exists():
        log(f"ERROR: Input file not found: {INPUT_CSV}", force=True)
        sys.exit(1)
    
    # Create build directory
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load input CSV into memory
    log(f"[LOAD] Reading input CSV: {INPUT_CSV}")
    with INPUT_CSV.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        current_rows = list(reader)
    
    initial_rows = len(current_rows)
    log(f"[LOAD] Loaded {initial_rows:,} rows")
    
    # ------------------------------------------------------------------
    # STAGE 0: Recovery of missing molblocks using chemical names
    # ------------------------------------------------------------------
    print("\n[STEP 0] Loading liganden names for molblock recovery...")
    liganden_lookup, all_liganden_rows = load_liganden_names(LIGANDEN_CSV)
    log(f"[LOAD] Loaded {len(liganden_lookup):,} liganden name mappings")
    log(f"[LOAD] Total liganden entries: {len(all_liganden_rows):,}")
    
    # Identify orphan liganden (not in mol_data)
    mol_data_ids = {row.get("ligandenNR", "").strip() for row in current_rows}
    orphan_count = sum(1 for r in all_liganden_rows if r.get("ligandenID", "").strip() not in mol_data_ids)
    log(f"[LOAD] Orphan liganden (no mol_data): {orphan_count:,}")

    print("\n[STEP 1] Recovering missing molblocks via PubChem...")
    valid_rows, fixed_rows, failed_recovery_rows = recover_molblock_from_name(
        current_rows, all_liganden_rows, liganden_lookup
    )
    
    # IMPORTANT: Include ALL entries in processing, not just valid ones
    # Failed recovery rows will get '*' placeholders in enrichment stages
    current_rows = valid_rows + failed_recovery_rows
    log(f"[LOAD] Total rows for enrichment (valid + failed): {len(current_rows):,}")
    
    # Add recovery tracking columns to fieldnames if needed
    for col in ["RECOVERY_SOURCE", "RECOVERY_CID", "RECOVERY_NAME", "ORPHAN_LIGANDEN", "ERROR_RECOVERY"]:
        if col not in fieldnames:
            fieldnames.append(col)
    
    # Write FIXED_by_name.csv (entries recovered via chemical name)
    if fixed_rows:
        log(f"\n[RECOVERY] Writing recovered entries: {FIXED_BY_NAME_CSV}")
        fixed_fieldnames = fieldnames + ["RECOVERY_SOURCE", "RECOVERY_CID", "RECOVERY_NAME", "ORPHAN_LIGANDEN"]
        fixed_fieldnames = list(dict.fromkeys(fixed_fieldnames))  # dedupe
        with FIXED_BY_NAME_CSV.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fixed_fieldnames, quoting=csv.QUOTE_ALL, extrasaction='ignore')
            writer.writeheader()
            for row in fixed_rows:
                writer.writerow(row)
        log(f"[RECOVERY] Wrote {len(fixed_rows):,} recovered entries")
    
    # Write FAILED_no_molblock.csv (entries that could not be recovered)
    if failed_recovery_rows:
        log(f"\n[RECOVERY] Writing unrecoverable entries: {FAILED_NO_MOLBLOCK_CSV}")
        fail_fieldnames = fieldnames + ["ERROR_RECOVERY", "ORPHAN_LIGANDEN"]
        fail_fieldnames = list(dict.fromkeys(fail_fieldnames))  # dedupe
        with FAILED_NO_MOLBLOCK_CSV.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fail_fieldnames, quoting=csv.QUOTE_ALL, extrasaction='ignore')
            writer.writeheader()
            for row in failed_recovery_rows:
                writer.writerow(row)
        log(f"[RECOVERY] Wrote {len(failed_recovery_rows):,} unrecoverable entries")
    
    # Track recovery stats
    recovery_stats = {
        'total': initial_rows,
        'ok': len(current_rows),
        'fail': len(failed_recovery_rows),
        'recovered': len(fixed_rows),
    }
    _stage_stats['recovery'] = recovery_stats
    
    # ------------------------------------------------------------------
    # STAGES 1-3: Enrichment (InChI, SMILES, Formula)
    # ------------------------------------------------------------------
    rows_after_recovery = len(current_rows)
    total_failed = len(failed_recovery_rows)

    print("\n[STEP 2] Running enrichment stages...")
    
    for tag, new_cols, func in PIPELINE:
        # Failed file goes to BUILD_DIR
        fail_path = BUILD_DIR / f"FAILED_{tag.upper()}.csv"

        current_rows, stats = run_stage(
            current_rows,
            fail_path,
            new_cols=new_cols,
            worker=func,
            err_tag=tag,
            fieldnames=fieldnames,
        )
        
        # Update fieldnames for next stage
        for col in new_cols:
            if col not in fieldnames:
                fieldnames.append(col)
        
        total_failed += stats['fail']

    # Write final enriched CSV
    log(f"\n[FINAL] Writing enriched CSV: {FINAL_CSV}")
    with FINAL_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL, extrasaction='ignore')
        writer.writeheader()
        for row in current_rows:
            writer.writerow(row)
    log(f"[FINAL] Wrote {len(current_rows):,} rows to {FINAL_CSV.name}")

    # ------------------------------------------------------------------
    # Calculate ACTUAL enrichment stats (placeholder vs truly enriched)
    # ------------------------------------------------------------------
    print("\n[STEP 3] Calculating enrichment statistics...")
    
    total_output_rows = len(current_rows)
    inchi_placeholder_count = sum(1 for r in current_rows if r.get("InChI", "") == "*")
    smiles_placeholder_count = sum(1 for r in current_rows if r.get("SMILES", "") == "*")
    composition_placeholder_count = sum(1 for r in current_rows if r.get("COMPOSITION", "") == "*")
    
    # An entry is "truly enriched" only if ALL three columns have non-placeholder values
    placeholder_count = sum(
        1 for r in current_rows 
        if r.get("InChI", "") == "*" or r.get("SMILES", "") == "*" or r.get("COMPOSITION", "") == "*"
    )
    truly_enriched_count = total_output_rows - placeholder_count
    true_success_rate = (truly_enriched_count / total_output_rows * 100) if total_output_rows > 0 else 0.0
    
    log(f"[STATS] Total output rows: {total_output_rows:,}")
    log(f"[STATS] Truly enriched (all valid): {truly_enriched_count:,} ({true_success_rate:.2f}%)")
    log(f"[STATS] Placeholder entries: {placeholder_count:,}")
    log(f"[STATS]   - InChI = '*': {inchi_placeholder_count:,}")
    log(f"[STATS]   - SMILES = '*': {smiles_placeholder_count:,}")
    log(f"[STATS]   - COMPOSITION = '*': {composition_placeholder_count:,}")
    
    # Prepare summary stats
    summary_stats = {
        'input_file': str(INPUT_CSV),
        'liganden_file': str(LIGANDEN_CSV),
        'build_dir': str(BUILD_DIR),
        'stages': _stage_stats,
        'initial_rows': initial_rows,
        'total_liganden': len(all_liganden_rows),
        'orphan_liganden_count': len(all_liganden_rows) - len(mol_data_ids.intersection({r.get('ligandenID', '') for r in all_liganden_rows})),
        'recovered_count': len(fixed_rows),
        'failed_recovery_count': len(failed_recovery_rows),
        'total_output_rows': total_output_rows,
        'truly_enriched_count': truly_enriched_count,
        'placeholder_count': placeholder_count,
        'inchi_placeholder_count': inchi_placeholder_count,
        'smiles_placeholder_count': smiles_placeholder_count,
        'composition_placeholder_count': composition_placeholder_count,
        'true_success_rate': true_success_rate,
        'final_csv': str(FINAL_CSV),
        'fixed_by_name_csv': str(FIXED_BY_NAME_CSV),
        'failed_no_molblock_csv': str(FAILED_NO_MOLBLOCK_CSV),
        'log_file': str(LOG_FILE),
    }
    
    # Generate summary markdown
    print("\n[STEP 4] Generating summary markdown...")
    generate_summary_markdown(summary_stats, SUMMARY_MD)
    
    # Write log file
    print("\n[STEP 5] Writing log file...")
    write_log_file(LOG_FILE)
    
    # Print final summary
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    print(f"  mol_data input rows:    {initial_rows:,}")
    print(f"  Liganden total:         {len(all_liganden_rows):,}")
    print(f"  Orphan liganden:        {summary_stats['orphan_liganden_count']:,}")
    print("-" * 70)
    print(f"  Recovered via PubChem:  {len(fixed_rows):,}")
    print(f"  Failed recovery:        {len(failed_recovery_rows):,}")
    print("-" * 70)
    print(f"  Total output rows:      {total_output_rows:,}")
    print(f"  ✅ Truly enriched:      {truly_enriched_count:,} ({true_success_rate:.2f}%)")
    print(f"  ⚠️ Placeholder ('*'):   {placeholder_count:,} ({(placeholder_count/total_output_rows*100) if total_output_rows else 0:.2f}%)")
    print("=" * 70)
    print(f"Final enriched file:  {FINAL_CSV}")
    print(f"Recovered entries:    {FIXED_BY_NAME_CSV.name}")
    print(f"Unrecoverable:        {FAILED_NO_MOLBLOCK_CSV.name}")
    print("=" * 70)
    print("[DONE] SMILES/InChI enrichment pipeline complete.")
    print("=" * 70)


# ----------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) >= 2:
        # allow overriding the initial input from the CLI
        INPUT_CSV = Path(sys.argv[1])
    main()
