#!/usr/bin/env python
"""
SRD46_pd_liganden_Qupkake-pip-5.py
----------------------------------

Pipeline 1c-5: QupKake pKa Simulation via WSL

Enrich ligand CSV with QupKake protonation states (Windows driver -> runs QupKake in WSL).
Generates SDF files with pKa values for each protonation state.

This generator is run out of band (it needs a WSL conda environment with QupKake); the
pipeline itself only parses the SDF states it produced (stage pip1c_5b, ``--qupkake existing``).

Input:  CSV with InChI and SMILES columns (pip1c_4 output)
        - _input/PubChem_cache_seeds/mol_data_with_names.csv (override: env QUPKAKE_INPUT_CSV)
Output: SDF files with pKa values in the WSL qupkake_io folder
        - Status logs in _output/pip1c_5_Qupkake_output/

Environment (WSL side): QUPKAKE_WSL_USER (WSL user name), QUPKAKE_CONDA_BIN (conda executable
that owns the ``qupkake`` environment).

Notes:
- figure_definition accepted: "HL", "L", "H2L", "H-2L", "H2L/+","H2L/-", with spaces tolerated.
- States ordered from highest to lowest protonation (HnL; n can be negative).
- Uses WSL to call: conda run -n qupkake qupkake ...
"""

import csv
import re
import sys
import subprocess
import glob
import os
import logging
import json
import time
import itertools
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from rdkit import Chem

# ======================================================================
# PATH CONFIGURATION (pip1c standard)
# ======================================================================
CODE_ROOT = Path(__file__).resolve().parent
PIPELINE_ROOT = CODE_ROOT.parent  # pip1c_parse_liganden_moldata_pKa_SRD46
PROJECT_ROOT = PIPELINE_ROOT.parent.parent  # project root (holds _input/ and _output/)

# Input: pip1c_4 chemical-names output (archived copy under _input/; override with QUPKAKE_INPUT_CSV)
INPUT_CSV = Path(os.environ.get("QUPKAKE_INPUT_CSV",
                                PROJECT_ROOT / "_input" / "PubChem_cache_seeds" / "mol_data_with_names.csv"))

# Build: all status outputs go to _output/pip1c_5_Qupkake_output/
BUILD_DIR = PROJECT_ROOT / "_output" / "pip1c_5_Qupkake_output"

# Timestamp for output files
TIMESTAMP = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

# ======================================================================
# DEBUG MODE CONFIGURATION
# ======================================================================
DEBUG_MODE = True        # Set to True to limit to DEBUG_LIMIT rows
DEBUG_LIMIT = 1          # Number of rows to process in DEBUG mode
DRY_RUN = False          # If True, skip QupKake calls (IO test only); False = real run

# --- pipeline flags ---
MAKE_SDF_FLAG = True     # generate SDFs and write failures
MAKE_HxL_CSV = False     # compute protonation pKa/HxL and write enriched CSVs
SKIP_EXISTING_SDF = True # don't regenerate if a usable SDF is already on disk
MAX_SEC_PER_MOL = 600 * 60

# -- WSL paths / settings --
WIN_ROOT = Path(r"C:\qupkake_io\qupkake_main")
WSL_ROOT = "/mnt/c/qupkake_io/qupkake_main"
QUP_ENV = "qupkake"
MP_WORKERS = 6  # 0 = serial (safe for WSL tempfiles). Raise after it works well.
start_at = "1"  # ligandID to resume the process

# Output file paths (initialized in setup_paths)
OUTPUT_ENRICH = None
OUTPUT_FAIL = None
OUTPUT_SKIP = None
LOG_FILE = None
OUTPUT_OK_IDS_TXT = None
OUTPUT_FAIL_IDS_TXT = None
OUTPUT_BYPASS_IDS_TXT = None
OUTPUT_TIMEOUT_IDS_TXT = None

WSL_USER = os.environ.get("QUPKAKE_WSL_USER", "")        # WSL user name that owns the qupkake environment
CONDA_BIN = os.environ.get("QUPKAKE_CONDA_BIN", f"/home/{WSL_USER}/miniconda3/bin/conda")  # conda that owns qupkake


def setup_paths():
    """Initialize output paths based on DEBUG_MODE."""
    global OUTPUT_ENRICH, OUTPUT_FAIL, OUTPUT_SKIP, LOG_FILE
    global OUTPUT_OK_IDS_TXT, OUTPUT_FAIL_IDS_TXT, OUTPUT_BYPASS_IDS_TXT, OUTPUT_TIMEOUT_IDS_TXT
    
    if DEBUG_MODE:
        output_dir = BUILD_DIR / "DEBUG"
    else:
        output_dir = BUILD_DIR
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    OUTPUT_ENRICH = output_dir / "ligands_enriched.csv"
    OUTPUT_FAIL = output_dir / "ligands_failed.csv"
    OUTPUT_SKIP = output_dir / "ligands_skipped.csv"
    LOG_FILE = output_dir / f"run_{TIMESTAMP}.log"
    OUTPUT_OK_IDS_TXT = output_dir / "ligands_success_ids.txt"
    OUTPUT_FAIL_IDS_TXT = output_dir / "ligands_failed_ids.txt"
    OUTPUT_BYPASS_IDS_TXT = output_dir / "ligands_bypassed_ids.txt"
    OUTPUT_TIMEOUT_IDS_TXT = output_dir / "ligands_timeouts_ids.txt"

    # DEBUG mode configuration
    global MAKE_SDF_FLAG, INPUT_CSV, start_at
    if DEBUG_MODE:
        # Use a local debug input CSV (one row) to avoid dependency on upstream outputs
        debug_dir = CODE_ROOT / "DEBUG"
        debug_dir.mkdir(parents=True, exist_ok=True)
        debug_csv = debug_dir / "debug_input.csv"
        if not debug_csv.exists():
            # create a minimal valid row
            import csv as _csv
            hdr = ["ligandenID", "name_ligand", "InChI", "SMILES", "figure_definition"]
            row = {
                "ligandenID": "DEBUG1",
                "name_ligand": "debug_mol",
                "InChI": "InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3",
                "SMILES": "CCO",
                "figure_definition": "HL",
            }
            with debug_csv.open("w", encoding="utf-8", newline="") as _fh:
                w = _csv.DictWriter(_fh, fieldnames=hdr)
                w.writeheader()
                w.writerow(row)
        INPUT_CSV = debug_csv
        # Clear resume/start point so the single debug row is processed
        start_at = None
        # If DRY_RUN, skip QupKake calls entirely (IO test only)
        if DRY_RUN:
            MAKE_SDF_FLAG = False


def setup_logging():
    """Configure logging after paths are set."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
        ],
        force=True,
    )


EXPORT_DIRS = [
    WIN_ROOT,
    WIN_ROOT / "output",
    WIN_ROOT / "data" / "output",
]
SDF_ID_RX = re.compile(r"^(?P<id>[A-Za-z0-9_-]+?)_.*\.sdf$", re.IGNORECASE)

# -- helpers: tag parsing / ordering --
TAG_RX = re.compile(r"^\s*(HL|L|H[+-]?\d+L)\s*(?:/[+-])?\s*$", re.IGNORECASE)


def clean_init_tag(s: str) -> str:
    """Normalize initial protonation tag."""
    s = (s or "").strip()
    if s == "***":
        return "***"
    m = TAG_RX.match(s)
    if not m:
        raise ValueError(f"Unrecognized figure_definition tag: {s!r}")
    tag = m.group(1).upper()
    if tag in ("HL", "L"):
        return tag
    n = int(tag[1:-1])  # between 'H' and 'L'
    return f"H{n}L"


def tag_to_n(tag: str) -> int:
    if tag == "HL":
        return 1
    if tag == "L":
        return 0
    m = re.fullmatch(r"H([+-]?\d+)L", tag)
    if not m:
        raise ValueError(f"Unrecognised tag: {tag!r}")
    return int(m.group(1))


def n_to_tag(n: int) -> str:
    return "HL" if n == 1 else ("L" if n == 0 else f"H{n}L")


def total_H(mol: Chem.Mol) -> int:
    molH = Chem.AddHs(mol)
    return sum(1 for a in molH.GetAtoms() if a.GetAtomicNum() == 1)


def _emit(prefix: str, line: str):
    msg = f"{prefix}{line.rstrip()}"
    logging.info(msg)


def _bash_single_quote(s: str) -> str:
    return "'" + s.replace("'", "'\"'\"'") + "'"


def _append_status_line(path: Path, lig_id: str, status: str) -> None:
    first_write = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        if first_write:
            w.writerow(["id", "status"])
        w.writerow([lig_id or "-", status])
        fh.flush()


def log_ok(lig_id: str) -> None:
    _append_status_line(OUTPUT_OK_IDS_TXT, lig_id, "ok")


def log_fail(lig_id: str) -> None:
    _append_status_line(OUTPUT_FAIL_IDS_TXT, lig_id, "fail")


def log_skip(lig_id: str) -> None:
    _append_status_line(OUTPUT_BYPASS_IDS_TXT, lig_id, "skip")


def log_timeout(lig_id: str) -> None:
    _append_status_line(OUTPUT_TIMEOUT_IDS_TXT, lig_id, "timeout")


def load_states_from_sdf(sdf_path: Path):
    """Read all valid RDKit molecules from an SDF (skip None)."""
    suppl = Chem.SDMolSupplier(str(sdf_path), removeHs=False)
    return [m for m in suppl if m is not None]


def _latest(paths):
    paths = [Path(p) for p in paths if Path(p).exists()]
    if not paths:
        return None
    return max(paths, key=lambda p: p.stat().st_mtime)


def locate_sdf_after_run(name: str, expected: Path, win_root: Path) -> Path | None:
    if expected.exists():
        return expected
    candidates = []
    patterns = [
        f"{name}.sdf",
        f"{name}_states.sdf",
        f"{name}_*.sdf",
        f"{name}*.sdf",
    ]
    for pat in patterns:
        candidates += glob.glob(str(win_root / pat))
        candidates += glob.glob(str((win_root / "output") / pat))
        candidates += glob.glob(str((win_root / "data" / "output") / pat))
    return _latest(candidates)


def load_done_ids() -> set[str]:
    if LOG_FILE is None or not LOG_FILE.exists():
        return set()
    done = set()
    with LOG_FILE.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                obj = json.loads(line.rsplit(" ", 1)[-1])
                if obj.get("status") == "ok":
                    done.add(obj["id"])
            except Exception:
                pass
    return done


def scan_exported_ids() -> set[str]:
    """Return all ligand IDs that already have *_states.sdf on disk."""
    ids = set()
    for folder in EXPORT_DIRS:
        if not folder.exists():
            continue
        for p in itertools.chain(
            folder.glob("*_states.sdf"),
            folder.glob("*_t*.sdf"),
        ):
            m = SDF_ID_RX.match(p.name)
            if m:
                ids.add(m.group("id"))
    return ids


def _parse_pka_numbers(s: str) -> List[float]:
    """Extract numeric pKa values from any string."""
    nums = []
    for m in re.finditer(r"[-+]?\d+(?:\.\d+)?", s or ""):
        try:
            nums.append(float(m.group(0)))
        except Exception:
            pass
    return nums


def get_start_at(argv: list[str]) -> str | None:
    """Returns the starting target from env or CLI."""
    val = (os.environ.get("START_AT") or "").strip()
    if val:
        return val
    for i, a in enumerate(argv):
        if a.startswith("--start-at="):
            return a.split("=", 1)[1].strip() or None
        if a == "--start-at" and i + 1 < len(argv):
            return (argv[i + 1] or "").strip() or None
    return None


def run_qupkake_in_wsl(smiles: str, name: str, sdf_out_win: Path, verbose: bool = True) -> None:
    sdf_out_wsl = f"{WSL_ROOT}/{sdf_out_win.name}"
    smiles_q = _bash_single_quote(smiles)
    name_q = _bash_single_quote(name)
    out_q = _bash_single_quote(sdf_out_wsl)
    root_q = _bash_single_quote(WSL_ROOT)

    bash_cmd = (
        "set -Eeop pipefail\n"
        "unset XTBPATH\n"
        f"'{CONDA_BIN}' --version || true\n"
        f"'{CONDA_BIN}' info --envs || true\n"
        "stdbuf -oL -eL "
        f"'{CONDA_BIN}' run -n {QUP_ENV} "
        f"qupkake smiles {smiles_q} "
        f"-n {name_q} "
        f"-o {out_q} "
        f"-r {root_q} "
        f"--tautomerize "
        f"--multiprocessing {MP_WORKERS}\n"
    )

    env = {
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", r"C:\Windows"),
        "WINDIR": os.environ.get("WINDIR", r"C:\Windows"),
        "COMSPEC": os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe"),
        "WSLENV": "",
        "XTBPATH": "",
    }

    proc = subprocess.Popen(
        ["wsl", "-u", WSL_USER, "--cd", "~", "bash", "-lc", bash_cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=env,
        cwd="C:\\",
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )

    def _kill_tree(p: subprocess.Popen):
        try:
            subprocess.run(
                ["taskkill", "/PID", str(p.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
            )
        except Exception:
            try:
                p.kill()
            except Exception:
                pass

    try:
        out, err = proc.communicate(timeout=MAX_SEC_PER_MOL)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        try:
            out, err = proc.communicate(timeout=5)
        except Exception:
            out, err = "", ""
        if verbose and out:
            for line in out.splitlines(True):
                _emit("[WSL:out] ", line)
        if verbose and err:
            for line in err.splitlines(True):
                _emit("[WSL:err] ", line)
        raise RuntimeError("qupkake_timeout")

    if verbose and out:
        for line in out.splitlines(True):
            _emit("[WSL:out] ", line)
    last_stderr = ""
    if err:
        for line in err.splitlines(True):
            last_stderr = line
            if verbose:
                _emit("[WSL:err] ", line)

    rc = proc.returncode

    if rc != 0:
        try:
            if sdf_out_win.exists() and is_valid_qupkake_sdf(sdf_out_win):
                _emit("", f"[wrap] qupkake exited {rc} but wrote a valid SDF -> continuing ({sdf_out_win.name})\n")
                return
        except Exception:
            pass

    if rc == 124:
        raise RuntimeError("qupkake_timeout")
    elif rc != 0:
        raise RuntimeError(f"qupkake_failed (exit {rc}): {last_stderr.strip() or 'no stderr'}")


def is_valid_qupkake_sdf(p: Path) -> bool:
    try:
        txt = p.read_text(errors="ignore")
        if "$$$$" not in txt.strip().splitlines()[-1]:
            return False
        suppl = Chem.SDMolSupplier(str(p), removeHs=False)
        mols = [m for m in suppl if m is not None]
        if not mols:
            return False
        for m in mols:
            if m.HasProp("pka"):
                return True
            for k in m.GetPropNames():
                if "pka" in k.lower():
                    return True
        return False
    except Exception:
        return False


def process_row(row: Dict[str, Any], done_ids: set[str]) -> Dict[str, Any]:
    """
    Process a single row to generate QupKake SDF.
    
    Returns:
      {
        "__placeholder__": bool,
        "__error__": Optional[str],
        "__states__": [ {InChI, n, tag, H, pKa}, ... ]
      }
    """
    # 0) Check for placeholder SMILES from pip1c-2/3/4
    smiles_val = (row.get("SMILES") or "").strip()
    if smiles_val == "*":
        return {"__placeholder__": True, "__error__": "placeholder_from_upstream", "__states__": []}
    
    # 1) Check figure_definition for *** placeholder
    figdef = (row.get("figure_definition") or "").strip()
    if figdef == "***":
        return {"__placeholder__": True, "__error__": None, "__states__": []}

    # 2) initial tag, input molecule
    try:
        init_tag = clean_init_tag(figdef)
    except Exception as e:
        return {"__placeholder__": False, "__error__": f"bad_tag:{e}", "__states__": []}

    inchi = (row.get("InChI") or "").strip()
    if inchi == "*" or not inchi.startswith("InChI="):
        return {"__placeholder__": False, "__error__": "missing_or_bad_InChI", "__states__": []}

    molobj = Chem.MolFromInchi(inchi)
    if molobj is None:
        return {"__placeholder__": False, "__error__": "rdkit_inchi_parse_failed", "__states__": []}

    smiles = Chem.MolToSmiles(molobj, isomericSmiles=True)
    H_input = total_H(molobj)
    n_ref = tag_to_n(init_tag)

    # 3) choose name and expected SDF path
    name = (row.get("ligandenID") or row.get("name_ligand") or "mol").strip() or "mol"
    sdf_out = WIN_ROOT / f"{name}_states.sdf"

    MAKE_SDF_FOR_THIS_ROW = MAKE_SDF_FLAG
    
    if SKIP_EXISTING_SDF:
        existing = locate_sdf_after_run(name, sdf_out, WIN_ROOT)
        if existing and is_valid_qupkake_sdf(existing):
            _emit("", f"[skip] {name}: found existing and valid SDF ({existing.name})\n")
            if not MAKE_HxL_CSV:
                return {"__placeholder__": True, "__error__": None, "__states__": []}
            else:
                sdf_out = existing
                MAKE_SDF_FOR_THIS_ROW = False

    # Clean old outputs
    try:
        if MAKE_SDF_FOR_THIS_ROW:
            if sdf_out.exists():
                sdf_out.unlink()
            for old in (WIN_ROOT / "output").glob(f"{name}*.sdf"):
                try:
                    old.unlink()
                except:
                    pass
            for old in (WIN_ROOT / "data" / "output").glob(f"{name}*.sdf"):
                try:
                    old.unlink()
                except:
                    pass
    except:
        pass

    # Generate SDF
    if MAKE_SDF_FOR_THIS_ROW:
        try:
            run_qupkake_in_wsl(smiles, name, sdf_out)
            print()
            logging.info("OK %s  SDF generated", name)
        except RuntimeError as e:
            if "qupkake_timeout" in str(e):
                return {"__placeholder__": False, "__error__": "timeout", "__states__": []}
            return {"__placeholder__": False, "__error__": f"qupkake_failed:{e}", "__states__": []}

    # If only generating SDFs, stop here
    if not MAKE_HxL_CSV:
        return {"__placeholder__": True, "__error__": None, "__states__": []}

    # 4) locate actual SDF and load records
    sdf_found = locate_sdf_after_run(name, sdf_out, WIN_ROOT)
    if not sdf_found:
        return {"__placeholder__": False, "__error__": "sdf_not_found_after_run", "__states__": []}

    records = load_states_from_sdf(sdf_found)
    if not records:
        return {"__placeholder__": False, "__error__": "no_states", "__states__": []}

    # 5) Collect pKas from records
    basic_pkas: List[float] = []
    acidic_pkas: List[float] = []
    for m in records:
        ptype = ""
        pval = None
        if m.HasProp("pka_type"):
            ptype = (m.GetProp("pka_type") or "").strip().lower()
        if m.HasProp("pka"):
            try:
                pval = float((m.GetProp("pka") or "").strip())
            except Exception:
                pval = None
        if pval is None:
            for k in m.GetPropNames():
                if "pka" in k.lower():
                    nums = _parse_pka_numbers(m.GetProp(k))
                    if nums:
                        pval = nums[0]
                        break

        if pval is None:
            continue

        if "basic" in ptype:
            basic_pkas.append(pval)
        elif "acid" in ptype:
            acidic_pkas.append(pval)

    basic_pkas.sort(reverse=True)
    acidic_pkas.sort()

    final_rows = []

    # Baseline original
    baseline_inchi = Chem.MolToInchi(molobj)
    final_rows.append({
        "InChI": baseline_inchi,
        "n": n_ref,
        "tag": n_to_tag(n_ref),
        "H": H_input,
        "pKa": "original",
    })

    # Protonation-side rows
    for i, p in enumerate(basic_pkas, start=1):
        n_this = n_ref + i
        final_rows.append({
            "InChI": baseline_inchi,
            "n": n_this,
            "tag": n_to_tag(n_this),
            "H": H_input + i,
            "pKa": f"{p:g}",
        })

    # Deprotonation-side rows
    for i, p in enumerate(acidic_pkas, start=1):
        n_this = n_ref - i
        final_rows.append({
            "InChI": baseline_inchi,
            "n": n_this,
            "tag": n_to_tag(n_this),
            "H": H_input - i,
            "pKa": f"{p:g}",
        })

    final_rows.sort(key=lambda r: r["n"], reverse=True)

    return {"__placeholder__": False, "__error__": None, "__states__": final_rows}


def write_status_txt(ok_rows, fail_rows, skip_rows, timeout_rows) -> None:
    def _write(path: Path, rows):
        with path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["id", "status"])
            for r in rows:
                w.writerow([r.get("id", ""), r.get("status", "")])
    _write(OUTPUT_OK_IDS_TXT, ok_rows)
    _write(OUTPUT_FAIL_IDS_TXT, fail_rows)
    _write(OUTPUT_BYPASS_IDS_TXT, skip_rows)
    _write(OUTPUT_TIMEOUT_IDS_TXT, timeout_rows)


def main():
    # Setup paths first
    setup_paths()
    setup_logging()
    
    print("=" * 70)
    print("NIST SRD 46 QupKake pKa Pipeline (pip1c-5)")
    print("=" * 70)
    
    if DEBUG_MODE:
        print(f"*** DEBUG MODE: Processing only {DEBUG_LIMIT} row(s) ***")
        print(f"*** Output to: {BUILD_DIR / 'DEBUG'} ***")
    
    logging.info("[CONFIG] CODE_ROOT: %s", CODE_ROOT)
    logging.info("[CONFIG] INPUT_CSV: %s", INPUT_CSV)
    logging.info("[CONFIG] BUILD_DIR: %s", BUILD_DIR)
    logging.info("[CONFIG] DEBUG_MODE: %s (limit=%d)", DEBUG_MODE, DEBUG_LIMIT)
    if not DRY_RUN and not WSL_USER:
        sys.exit("QUPKAKE_WSL_USER is not set (WSL user that owns the qupkake conda environment); "
                 "set it and optionally QUPKAKE_CONDA_BIN, or use DRY_RUN = True")
    
    # Load done IDs
    DONE_IDS = load_done_ids() | scan_exported_ids()

    # Per-category summaries
    ok_ids_summ: List[Dict[str, str]] = []
    fail_ids_summ: List[Dict[str, str]] = []
    skip_ids_summ: List[Dict[str, str]] = []
    timeout_ids_summ: List[Dict[str, str]] = []

    if not INPUT_CSV.exists():
        sys.exit(f"Input CSV not found: {INPUT_CSV}")

    # Resume point
    started = (start_at is None)
    if start_at:
        logging.info("Resume requested from ligandenID=%s", start_at)
    start_num = None
    if start_at:
        m = re.search(r"\d+", start_at)
        if m:
            try:
                start_num = int(m.group(0))
            except Exception:
                start_num = None

    successes: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    raw_rows: List[Dict[str, Any]] = []
    processed: List[Dict[str, Any]] = []
    max_states = 0
    counter = 0
    n_placeholder = 0
    
    logging.info("Starting; %d rows already finished -> skipped", len(DONE_IDS))
    
    with INPUT_CSV.open(encoding="utf-8-sig", newline="") as fh:
        rdr = csv.DictReader(fh)
        for row in rdr:
            # Extract ligand ID
            lig_id = (row.get("ligandenID")
                      or row.get("LigandenID")
                      or row.get("ligandID")
                      or row.get("LigandID")
                      or row.get("id")
                      or row.get("ID")
                      or row.get("name_ligand")
                      or row.get("name")
                      or "")
            lig_id = str(lig_id).strip()
            if not lig_id:
                for k, v in row.items():
                    if 'id' in (k or '').lower():
                        s = str(v or '').strip()
                        if s:
                            lig_id = s
                            break
            if not lig_id:
                for v in row.values():
                    s = str(v or '').strip()
                    if s.isdigit():
                        lig_id = s
                        break

            # Honor resume point
            if not started:
                if lig_id and start_at and lig_id == start_at:
                    started = True
                    logging.info("Resuming at ligandenID=%s (exact)", lig_id or "-")
                else:
                    if start_num is not None:
                        m2 = re.search(r"\d+", lig_id or "")
                        if m2:
                            try:
                                lig_num = int(m2.group(0))
                            except Exception:
                                lig_num = None
                        else:
                            lig_num = None
                        if lig_num is not None and lig_num > start_num:
                            started = True
                            logging.info("Resuming at ligandenID=%s (next higher than %s)", lig_id or "-", start_at)
                        else:
                            continue
                    else:
                        continue

            # DEBUG limit check
            if DEBUG_MODE and counter >= DEBUG_LIMIT:
                logging.info("DEBUG_LIMIT reached (%d), stopping.", DEBUG_LIMIT)
                break

            if lig_id in DONE_IDS:
                logging.info("%-6s  already done - skipping", lig_id or "-")
                skipped.append({**row, "reason": "already_done"})
                skip_ids_summ.append({"id": lig_id or "-", "status": "skip"})
                log_skip(lig_id)
                continue
            
            logging.info("%-6s  processing ...", lig_id or "-")
            raw_rows.append(row)
            info = process_row(row, DONE_IDS)
            counter += 1
            print(f"processing_SDF_file_#{counter}\nRow ID: {lig_id}")
            processed.append(info)
            
            if info["__error__"]:
                if info["__error__"] == "placeholder_from_upstream":
                    n_placeholder += 1
                    skipped.append({**row, "reason": info["__error__"]})
                else:
                    failures.append({**row, "reason": info["__error__"]})
            elif info["__placeholder__"]:
                if MAKE_HxL_CSV:
                    skipped.append({**row, "reason": "placeholder"})
                else:
                    successes.append(row)
            else:
                successes.append(row)
                max_states = max(max_states, len(info["__states__"]))
            
            status = (
                "ok" if (not info["__error__"] and (not info["__placeholder__"] or not MAKE_HxL_CSV))
                else "skip" if info["__placeholder__"] or info["__error__"] == "placeholder_from_upstream"
                else "timeout" if info["__error__"] == "timeout"
                else "fail"
            )
            logging.info(json.dumps({"id": lig_id, "status": status}))
            
            if status == "ok":
                ok_ids_summ.append({"id": lig_id or "-", "status": "ok"})
                log_ok(lig_id)
            elif status == "skip":
                skip_ids_summ.append({"id": lig_id or "-", "status": "skip"})
                log_skip(lig_id)
            elif status == "timeout":
                timeout_ids_summ.append({"id": lig_id or "-", "status": "timeout"})
                log_timeout(lig_id)
            else:
                fail_ids_summ.append({"id": lig_id or "-", "status": "fail"})
                log_fail(lig_id)

    # Write outputs
    if not MAKE_HxL_CSV:
        write_status_txt(ok_ids_summ, fail_ids_summ, skip_ids_summ, timeout_ids_summ)
        if failures:
            fail_fields = list(failures[0].keys())
            with OUTPUT_FAIL.open("w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=fail_fields)
                w.writeheader()
                w.writerows(failures)
        else:
            with OUTPUT_FAIL.open("w", encoding="utf-8", newline="") as fh:
                fh.write("")

        if skipped:
            skip_fields = list(skipped[0].keys())
            with OUTPUT_SKIP.open("w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=skip_fields)
                w.writeheader()
                w.writerows(skipped)
        else:
            with OUTPUT_SKIP.open("w", encoding="utf-8", newline="") as fh:
                fh.write("")
        
        # Print final summary
        print("\n" + "=" * 70)
        print("FINAL SUMMARY")
        print("=" * 70)
        print(f"  Total processed:     {counter:,}")
        print()
        print("INPUT QUALITY:")
        print(f"  Rows with valid data: {counter - n_placeholder:,}")
        print(f"  Placeholder ('*'):    {n_placeholder:,}")
        print()
        print("QUPKAKE RESULTS:")
        print(f"  OK (SDF generated):   {len(ok_ids_summ):,}")
        print(f"  Failed:               {len(fail_ids_summ):,}")
        print(f"  Skipped:              {len(skip_ids_summ):,}")
        print(f"  Timeout:              {len(timeout_ids_summ):,}")
        print("=" * 70)
        print("SDF generation pass complete.")
        print(f"Failed log: {OUTPUT_FAIL}")
        print(f"Skipped log: {OUTPUT_SKIP}")
        print("=" * 70)
        return

    # Prepare enriched header
    base_fields = list(raw_rows[0].keys()) if raw_rows else []
    state_cols = []
    for i in range(1, max_states + 1):
        state_cols += [f"InChI{i}", f"tag_to_n{i}", f"H_count{i}", f"pKa_qupkake_{i}"]
    out_fields = base_fields + state_cols

    with OUTPUT_ENRICH.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=out_fields)
        w.writeheader()
        for row, info in zip(raw_rows, processed):
            if info["__placeholder__"] or info["__error__"]:
                continue
            out = dict(row)
            states = info["__states__"]
            for idx, st in enumerate(states, start=1):
                out[f"InChI{idx}"] = st["InChI"]
                out[f"tag_to_n{idx}"] = st["tag"]
                out[f"H_count{idx}"] = str(st["H"])
                out[f"pKa_qupkake_{idx}"] = st["pKa"]
            for idx in range(len(states) + 1, max_states + 1):
                out[f"InChI{idx}"] = out[f"tag_to_n{idx}"] = out[f"H_count{idx}"] = out[f"pKa_qupkake_{idx}"] = ""
            w.writerow(out)

    if failures:
        fail_fields = list(failures[0].keys())
        with OUTPUT_FAIL.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fail_fields)
            w.writeheader()
            w.writerows(failures)
    else:
        with OUTPUT_FAIL.open("w", encoding="utf-8", newline="") as fh:
            fh.write("")

    if skipped:
        skip_fields = list(skipped[0].keys())
        with OUTPUT_SKIP.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=skip_fields)
            w.writeheader()
            w.writerows(skipped)
    else:
        with OUTPUT_SKIP.open("w", encoding="utf-8", newline="") as fh:
            fh.write("")

    print(f"Wrote: {OUTPUT_ENRICH}")
    print(f"Wrote: {OUTPUT_FAIL}")
    print(f"Wrote: {OUTPUT_SKIP}")


if __name__ == "__main__":
    main()
