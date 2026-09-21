# batch_qupkake_pka.py
# requirements: pip install rdkit-pypi pandas
import os, re, csv, json, gzip, hashlib
from pathlib import Path
from typing import List, Dict, Optional
import pandas as pd
from rdkit import Chem
from rdkit.Chem import rdDepictor
from rdkit.Chem.inchi import MolToInchi, MolToInchiKey
from rdkit.Chem.rdmolfiles import MolToMolBlock
from rdkit.Chem.rdMolDescriptors import CalcMolFormula
from rdkit.Chem.Draw import MolsToGridImage
import ast
from collections import Counter
from datetime import datetime

now = datetime.now()
formatted_datetime = now.strftime("%Y-%m-%d-%H-%M-%S")

# --- debug/verbosity toggles ---
DEBUG_MODE = True          # write a _debug.jsonl per ligand with step-by-step snapshots
SUPPRESS_RD_WARN = True   # set True to hide RDKit warnings

from rdkit import RDLogger
if SUPPRESS_RD_WARN:
    RDLogger.DisableLog('rdApp.warning')   # hide "Proton(s) added/removed", valence chatter
    RDLogger.DisableLog('rdApp.error')     # optionally hide error prints too (keeps exceptions)


# --------------------
# CONFIG - pip1c pipeline standard paths
# --------------------
CODE_ROOT = Path(__file__).resolve().parent
PIPELINE_ROOT = CODE_ROOT.parent  # pip1c_parse_liganden_moldata_pKa_SRD46
PROJECT_ROOT = PIPELINE_ROOT.parent.parent  # NIST_SRD46_Correction_and_Parser

# Input: SDF files from QupKake output (pip1c-5a) or pre-existing collection
# Default: the pre-existing SDF collection shipped with the project (repo-relative).
# Override with env QUPKAKE_SDF_DIR (e.g. a fresh QupKake WSL output folder such as C:\qupkake_io\qupkake_main\output).
SDF_INPUT_DIR = Path(os.environ.get("QUPKAKE_SDF_DIR") or (PROJECT_ROOT / "_input" / "Qupkake_ligand_pKa_ML" / "pip1c_Qupkake_SDF"))

# Build: all outputs go to _build/pip1c_5b_SDF_parsed_output/
BUILD_DIR = PIPELINE_ROOT / "_build" / "pip1c_5b_SDF_parsed_output"

# Per-ligand parsed output folders go here (one folder per SDF)
PARSED_OUTPUT_DIR = BUILD_DIR / "parsed_ligands"

# Final aggregated CSV
OUT_CSV = BUILD_DIR / "qupkake_pka_liganden.csv"

# Summary log
LOG_DIR = BUILD_DIR / "logs"
SUMMARY_LOG = LOG_DIR / f"summary_log_pip-5b_{formatted_datetime}.txt"

# Legacy compatibility alias
RAW_ROOT = SDF_INPUT_DIR

DRAW_IMAGES  = True
MOLS_PER_ROW = 4
CELL_SIZE    = (350, 300)

# Skip controls
SKIP_PROCESSED       = True   # set False to force reprocessing
MARKER_FILENAME      = "_processed.json"
REQUIRED_OUTPUTS     = ("{id}_between_windows.sdf", "{id}_windows.tsv")  # must exist to count as processed
REQUIRE_IMAGE_IF_SET = True   # if DRAW_IMAGES is True, also require "{id}_windows.png"

# Debug
STRICT_VALIDATE   = False   # if True, raise on validation errors (halts that ligand)
PH_TOL            = 1e-6    # tolerance to treat pKa ties or bracket joins
DEBUG_SUMMARY_TSV = BUILD_DIR / "run_debug_summary.tsv"
VERBOSE_OUTPUT    = False

# === RUN EVENTS (for [skip] / processed stats) ===
RUN_EVENTS = []  # list of {"event": "processed|skip_up_to_date|error|skip_incomplete", "ligandennr": id, ...}

def log_event(event: str, lig_id: str, **kw):
    RUN_EVENTS.append({"event": event, "ligandennr": lig_id, **kw})

# --------------------
# SPECIAL FILTERS (Aqueous sanity checks for QupKake sites)
# --------------------
# Toggle + numeric limits for "water window"
DROP_OXONIUM = True                 # drop any BASIC site on oxygen (O-protonation)
DROP_SULFONIUM = True               # drop any BASIC site on sulfur (S-protonation)
DROP_UNACTIVATED_CARBANION = True   # drop ACIDIC sites on unactivated carbon

# pKa clipping (25 °C, with a little slack)
BASIC_MIN, BASIC_MAX   = -2.0, 16.0     # BH+ acidity pKa outside → drop
ACIDIC_MIN, ACIDIC_MAX = -3.0, 20.0     # HA acidity pKa outside → drop
ACIDIC_MAX_ACTIVATED_C = 24.0           # looser cap if α-activated carbon

# SMARTS helpers (compiled once)
from rdkit import Chem as _Chem

# α-activated carbon acids (anchor atom = first atom in SMARTS)
_SMARTS_ALPHA_ACTIVATED = [
    _Chem.MolFromSmarts("[CH1,CH2,CH3]-[CX3](=O)[#6,#7,#8]"),  # α to carbonyl
    _Chem.MolFromSmarts("[CH1,CH2,CH3]-[N+](=O)[O-]"),        # α to nitro
    _Chem.MolFromSmarts("[CH1,CH2,CH3]-C#N"),                 # α to nitrile
    _Chem.MolFromSmarts("[CH1,CH2,CH3]-[S](=O)(=O)[#6,#7,#8]"),  # α to sulfone
    _Chem.MolFromSmarts("[CH1,CH2,CH3]-[S+](=O)[O-]"),        # α to sulfoxide (resonance)
]

# strong-acid “handles” (anchor at the acidic atom) - Those cases will be accepted instead of filtered out
_SMARTS_SULFONIC_O   = _Chem.MolFromSmarts("[OX2H]-S(=O)(=O)")   # –SO2–OH (acidic O)
_SMARTS_SULFONIMIDE_N = _Chem.MolFromSmarts("[NX3H]-[SX4](=O)(=O)-[NX3]-[CX3](=O)")
_SMARTS_PHOSPHONIC_O = _Chem.MolFromSmarts("[OX2H]-P(=O)(O)O")   # –P(=O)(OH)–OH (pKa1 ~1–2)
_SMARTS_SULFONATE_O  = _Chem.MolFromSmarts("[O-]-S(=O)(=O)")
_SMARTS_IMIDE_N        = _Chem.MolFromSmarts("[NX3H]-[CX3](=O)-[NX3]-[CX3](=O)")
_SMARTS_SULFONAMIDE_N  = _Chem.MolFromSmarts("[NX3H]-[SX4](=O)(=O)[#6]")
_SMARTS_PHENOL_O     = _Chem.MolFromSmarts("[OX2H][c]")
_SMARTS_ALPHA_CF3    = _Chem.MolFromSmarts("[OX2H]-[CX4]([F])([F])[F]")
_SMARTS_ALPHA_POLYF  = _Chem.MolFromSmarts("[OX2H]-[CX4]([F])([F])")  # ≥2 F on α-C
_SMARTS_ALPHA_CARBONYL = _Chem.MolFromSmarts("[OX2H]-[CX4]-[CX3](=O)")
_SMARTS_ALPHA_SULFONYL = _Chem.MolFromSmarts("[OX2H]-[CX4]-[SX4](=O)(=O)")
_SMARTS_N_ACYLSULFONAMIDE_N = _Chem.MolFromSmarts("[NX3H](-[SX4](=O)(=O))-[CX3](=O)")
_SMARTS_SULFONYLUREA_N      = _Chem.MolFromSmarts("[NX3H](-[SX4](=O)(=O))-[CX3](=O)-[NX3]")
_SMARTS_SP3_ALCOHOL = _Chem.MolFromSmarts("[OX2H]-[CX4]")

# --- Filter policy & site signature (cache-busting for SKIP_PROCESSED) ---
FILTER_POLICY = json.dumps({
    "DROP_OXONIUM": DROP_OXONIUM,
    "DROP_SULFONIUM": DROP_SULFONIUM,
    "DROP_UNACTIVATED_CARBANION": DROP_UNACTIVATED_CARBANION,
    "BASIC_MIN": BASIC_MIN, "BASIC_MAX": BASIC_MAX,
    "ACIDIC_MIN": ACIDIC_MIN, "ACIDIC_MAX": ACIDIC_MAX,
    "ACIDIC_MAX_ACTIVATED_C": ACIDIC_MAX_ACTIVATED_C,
}, sort_keys=True)
FILTER_POLICY_HASH = hashlib.sha1(FILTER_POLICY.encode("utf-8")).hexdigest()[:12]

FILTER_STATS = Counter()

def site_fingerprint(base_mol, sites):
    """
    Deterministic hash of the filtered site list + local atom identity.
    Uses (atom_idx, atom_symbol, type, round(pKa,3)) in pKa/occ order.
    """
    if not base_mol or not sites:
        return ""
    items = []
    for _, sd in sites:
        idx = int(sd["idx"])
        typ = (sd["type"] or "").lower().strip()
        pka = round(float(sd["pka"]), 3)
        sym = base_mol.GetAtomWithIdx(idx).GetSymbol()
        items.append((idx, sym, typ, pka))
    return hashlib.sha1(repr(items).encode("utf-8")).hexdigest()

def _match_anchor(mol, patt, anchor_idx, site_idx):
    if patt is None: 
        return False
    for match in mol.GetSubstructMatches(patt):
        if match[anchor_idx] == site_idx:
            return True
    return False

def _is_alpha_activated_carbon(mol, site_idx):
    at = mol.GetAtomWithIdx(site_idx)
    if at.GetSymbol() != "C":
        return False
    for patt in _SMARTS_ALPHA_ACTIVATED:
        if _match_anchor(mol, patt, 0, site_idx):
            return True
    return False

def _has_strong_acid_handle_at_site(mol, site_idx):
    at = mol.GetAtomWithIdx(site_idx)
    sym = at.GetSymbol()
    if sym == "O":
        if _match_anchor(mol, _SMARTS_SULFONIC_O, 0, site_idx):
            return True
        if _match_anchor(mol, _SMARTS_PHOSPHONIC_O, 0, site_idx):
            return True
        if _match_anchor(mol, _SMARTS_SULFONATE_O, 0, site_idx):
            return True
    if sym == "N":
        if _match_anchor(mol, _SMARTS_SULFONIMIDE_N, 0, site_idx):  # true sulfonimide
            return True
        if _match_anchor(mol, _SMARTS_SULFONAMIDE_N, 0, site_idx):  # sulfonamide
            return True
        if _match_anchor(mol, _SMARTS_IMIDE_N, 0, site_idx):        # imide
            return True
        if _match_anchor(mol, _SMARTS_N_ACYLSULFONAMIDE_N, 0, site_idx): 
            return True
        if _match_anchor(mol, _SMARTS_SULFONYLUREA_N, 0, site_idx):      
            return True
    return False

def _is_plain_aliphatic_alcohol(mol, site_idx):
    at = mol.GetAtomWithIdx(site_idx)
    if at.GetSymbol() != "O": return False
    if not _match_anchor(mol, _SMARTS_PHENOL_O, 0, site_idx):
        if _match_anchor(mol, _SMARTS_SP3_ALCOHOL, 0, site_idx):
            if not any(_match_anchor(mol, p, 0, site_idx) for p in
                       (_SMARTS_ALPHA_CF3, _SMARTS_ALPHA_POLYF, _SMARTS_ALPHA_CARBONYL, _SMARTS_ALPHA_SULFONYL)):
                return True
    return False

def _is_heteroaromatic_strong_nh(mol, site_idx):
    at = mol.GetAtomWithIdx(site_idx)
    if not (at.GetSymbol() == "N" and at.GetIsAromatic() and at.GetTotalNumHs(includeNeighbors=True) >= 1):
        return False
    # Count ring nitrogens in the same smallest ring(s)
    ri = mol.GetRingInfo()
    in_rings = [ring for ring in ri.AtomRings() if site_idx in ring]
    for ring in in_rings:
        n_count = sum(1 for aidx in ring if mol.GetAtomWithIdx(aidx).GetSymbol() == "N")
        if n_count >= 3:  # hits tetrazoles & most triazoles
            return True
    return False

def filter_sites(base_mol, sites, dropped_out=None):
    """
    Input: sites = list[(occ, {'idx','type','pka'})]  (already ordered)
    Output: same shape, with obviously non-aqueous events removed.
    Rules:
      - drop BASIC on O or S (oxonium / sulfonium),
      - numeric clip: BASIC pKa ∉ [BASIC_MIN, BASIC_MAX] → drop,
      - numeric clip: ACIDIC pKa < ACIDIC_MIN → keep only if site is true strong acid,
      - numeric clip: ACIDIC pKa > ACIDIC_MAX → keep only if α-activated carbon AND pKa ≤ ACIDIC_MAX_ACTIVATED_C.
    """
    if not sites:
        return []

    filtered = []
    for occ, sd in sites:
        try:
            idx = int(sd["idx"])
            typ = (sd["type"] or "").strip().lower()
            pka = float(sd["pka"])
        except Exception:
            # malformed triple → drop
            continue

        # guard against out-of-range indices
        if idx < 0 or idx >= base_mol.GetNumAtoms():
            continue

        atom = base_mol.GetAtomWithIdx(idx)
        sym  = atom.GetSymbol()

        if typ == "basic":
            # O/S protonations are out-of-scope in water
            if DROP_OXONIUM and sym == "O":
                FILTER_STATS["drop_oxonium"] += 1
                if dropped_out is not None: dropped_out.append((occ, idx, typ, pka, "drop_oxonium (basic on O)"))
                continue
            if DROP_SULFONIUM and sym == "S":
                FILTER_STATS["drop_sulfonium"] += 1
                if dropped_out is not None: dropped_out.append((occ, idx, typ, pka, "drop_sulfonium (basic on S)"))
                continue
            # numeric clipping for BH+ acidity pKa
            if (pka < BASIC_MIN):
                FILTER_STATS["drop_basic_clip_low"]  += 1
                if dropped_out is not None: dropped_out.append((occ, idx, typ, pka, f"drop_basic_clip_low (<{BASIC_MIN})"))
                continue
            if  (pka > BASIC_MAX):
                FILTER_STATS["drop_basic_clip_high"] += 1
                if dropped_out is not None: dropped_out.append((occ, idx, typ, pka, f"drop_basic_clip_high (>{BASIC_MAX})"))
                continue
            filtered.append((occ, sd))
            FILTER_STATS["keep_basic"]  += (typ == "basic")
        elif typ == "acidic":
            if sym == "N" and not (_has_strong_acid_handle_at_site(base_mol, idx) or _is_heteroaromatic_strong_nh(base_mol, idx)):
                # If the N doesn't even have an H, it's doubly invalid as an "acidic" N–H site
                try:
                    if atom.GetTotalNumHs(includeNeighbors=True) < 1:
                        FILTER_STATS["drop_acidic_nitrogen_no_h"] += 1
                        if dropped_out is not None: dropped_out.append((occ, idx, typ, pka, "drop_acidic_nitrogen_no_h"))
                        continue
                except Exception:
                    FILTER_STATS["drop_acidic_nitrogen_no_h"] += 1
                    if dropped_out is not None: dropped_out.append((occ, idx, typ, pka, "drop_acidic_nitrogen_no_h (except)"))
                    pass
                FILTER_STATS["drop_acidic_nitrogen_no_handle"] += 1
                if dropped_out is not None: dropped_out.append((occ, idx, typ, pka, "drop_acidic_nitrogen_no_handle"))
                continue
            # Acidic O must actually have an O–H unless it's a strong-acid handle (sulfonic/phosphonic etc.)
            if sym == "O" and not _has_strong_acid_handle_at_site(base_mol, idx):
                try:
                    if atom.GetTotalNumHs(includeNeighbors=True) < 1:
                        FILTER_STATS["drop_acidic_oxygen_no_h"] += 1
                        if dropped_out is not None: dropped_out.append((occ, idx, typ, pka, "drop_acidic_oxygen_no_h"))
                        continue
                except Exception:
                    FILTER_STATS["drop_acidic_oxygen_no_h"] += 1
                    if dropped_out is not None: dropped_out.append((occ, idx, typ, pka, "drop_acidic_oxygen_no_h (except)"))
                    continue
            # Plain aliphatic alcohol O–H (no strong α-EWG): drop as non-acidic at aqueous pH ≤ 14
            if sym == "O" and _is_plain_aliphatic_alcohol(base_mol, idx):
                FILTER_STATS["drop_plain_alcohol_oh"] += 1
                if dropped_out is not None:
                    dropped_out.append((occ, idx, typ, pka, "drop_plain_alcohol_oh"))
                continue
            # Acidic S (thiols etc.) must carry an S–H; otherwise drop
            if sym == "S":
                try:
                    if atom.GetTotalNumHs(includeNeighbors=True) < 1:
                        FILTER_STATS["drop_acidic_sulfur_no_h"] += 1
                        if dropped_out is not None: dropped_out.append((occ, idx, typ, pka, "drop_acidic_sulfur_no_h"))
                        continue
                except Exception:
                    FILTER_STATS["drop_acidic_sulfur_no_h"] += 1
                    if dropped_out is not None: dropped_out.append((occ, idx, typ, pka, "drop_acidic_sulfur_no_h (except)"))
                    continue
            # very low pKa: keep only if the site is a bona fide strong acid handle
            if pka < ACIDIC_MIN and not _has_strong_acid_handle_at_site(base_mol, idx):
                FILTER_STATS["drop_acidic_clip_low_rejected"] += 1
                if dropped_out is not None: dropped_out.append((occ, idx, typ, pka, f"drop_acidic_clip_low_rejected (<{ACIDIC_MIN})"))
                continue
            # very high pKa: keep only stabilized carbon acids
            if pka > ACIDIC_MAX:
                if DROP_UNACTIVATED_CARBANION and not _is_alpha_activated_carbon(base_mol, idx):
                    FILTER_STATS["drop_acidic_clip_high_unactivated"] += 1
                    if dropped_out is not None: dropped_out.append((occ, idx, typ, pka, "drop_acidic_clip_high_unactivated (non-α-activated C)"))
                    continue
                if pka > ACIDIC_MAX_ACTIVATED_C:
                    FILTER_STATS["drop_acidic_clip_high_cap"] += 1
                    if dropped_out is not None: dropped_out.append((occ, idx, typ, pka, f"drop_acidic_clip_high_cap (>{ACIDIC_MAX_ACTIVATED_C})"))
                    continue
            filtered.append((occ, sd))
            FILTER_STATS["keep_acidic"] += (typ == "acidic")
        else:
            # Unknown label (neither acidic/basic) → safest to drop
            if dropped_out is not None: dropped_out.append((occ, sd.get("idx", -1), typ, sd.get("pka", None), "unknown_type"))
            continue

    # maintain non-decreasing pKa order (defensive)
    filtered.sort(key=lambda kv: (kv[1]["pka"], kv[0]))
    return filtered

# --------------------
# I/O & utilities
# --------------------
def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def sha256_file(path: Path, chunk_size=1024*1024):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b: break
            h.update(b)
    return h.hexdigest()

def load_sdf_anyhow(path: Path, removeHs=False, sanitize=True):
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(p)
    try:
        sup = Chem.SDMolSupplier(str(p), removeHs=removeHs, sanitize=sanitize)
        _ = sup[0]
        return [m for m in sup if m is not None]
    except OSError:
        fh = gzip.open(p, "rb") if p.suffix.lower()==".gz" else open(p, "rb")
        sup = Chem.ForwardSDMolSupplier(fh, removeHs=removeHs, sanitize=sanitize)
        return [m for m in sup if m is not None]

def parse_sd_properties(block_text: str):
    props = []
    lines = block_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith(">"):
            m = re.search(r"> *<([^>]+)>\s*(?:\((\d+)\))?", line)
            if m:
                name = m.group(1).strip()
                occ  = int(m.group(2)) if m.group(2) else 1
                i += 1
                vals = []
                while i < len(lines) and not lines[i].startswith(">") and lines[i].strip() != "$$$$":
                    vals.append(lines[i]); i += 1
                props.append((name, occ, "\n".join(vals).strip()))
                continue
        i += 1
    return props

def collect_sites_from_sdf_text(sdf_text: str):
    """
    Read site triples strictly from SD props across *all* records:
      > <idx> (n), > <pka_type> (n), > <pka> (n)
    Merge by occurrence n; if repeated across records, later non-empty values win.
    Returns list[(occ, {'idx','type','pka'})] sorted by pKa then occ.
    """
    blocks = sdf_text.split("$$$$")
    if not blocks:
        return []

    merged: Dict[int, Dict[str, str]] = {}
    for block in blocks[:-1]:  # ignore trailing empty after last $$$$
        if not block.strip():
            continue
        props = parse_sd_properties(block)
        for name, occ, val in props:
            name_l = name.lower()
            if name_l not in ("idx", "pka_type", "pka"):
                continue
            d = merged.setdefault(occ, {})
            # prefer later non-empty values to fix malformed repeats like "idx (2)\n(2)"
            if val is not None and str(val).strip() != "":
                d[name_l] = str(val).strip()

    sites_by_occ: Dict[int, Dict[str, float]] = {}
    for occ, d in merged.items():
        if {"idx","pka_type","pka"} <= d.keys():
            try:
                # idx may contain stray "(2)" etc → strip parentheses and spaces
                idx_clean = re.sub(r"\(\d+\)", "", d["idx"])
                idx = int(re.sub(r"\s+", "", idx_clean))
                typ = d["pka_type"].strip().lower()
                m = re.search(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", d["pka"])
                if m:
                    sites_by_occ[occ] = {"idx": idx, "type": typ, "pka": float(m.group(0))}
            except Exception:
                # skip bad triple; keep going
                pass

    ordered = sorted(sites_by_occ.items(), key=lambda kv: (kv[1]["pka"], kv[0]))
    if VERBOSE_OUTPUT:
        print("[sites] parsed across all blocks:", ordered)
    return ordered

def parse_bracket(br):
    # "(a, b)" -> ("a","b")
    s = (br or "").strip()
    if not (s.startswith("(") and s.endswith(")")):
        return "", ""
    a, b = s[1:-1].split(",", 1)
    return a.strip(), b.strip()

def harvest_from_build_dirs(raw_root: Path = None):
    """
    Scan all *_pKa folders and reconstruct rows for the final CSV.
    Returns (rows, set_of_Qs_seen).
    
    If raw_root is None, uses PARSED_OUTPUT_DIR.
    """
    if raw_root is None:
        raw_root = PARSED_OUTPUT_DIR
    rows = []
    all_Qs = set()
    for out_dir in sorted(raw_root.glob("*_pKa")):
        lig_id = out_dir.name[:-4]  # strip "_pKa"
        win_tsv = out_dir / f"{lig_id}_windows.tsv"
        if not win_tsv.exists():
            continue

        # 1) per-Q windows from TSV
        try:
            dfw = pd.read_csv(win_tsv, sep="\t")
        except Exception:
            continue
        byQ = {}
        for _, r in dfw.iterrows():
            try:
                Q = int(r["Q"])
            except Exception:
                # tolerate floats like "0.0"
                Q = int(float(r["Q"]))
            lo, hi = parse_bracket(r.get("pH_bracket", ""))
            byQ[Q] = {
                "formula": r.get("formula", ""),
                "smiles":  r.get("smiles", ""),
                "inchi":   r.get("inchi", ""),
                "lo": lo, "hi": hi, "Q": Q
            }
            all_Qs.add(Q)

        # 2) molfile_original
        molfile_txt = ""
        # prefer in-tree states.sdf
        states_path = next(raw_root.glob(f"{lig_id}_states*.sdf"), None) \
              or next(raw_root.glob(f"{lig_id}_states*.sdf.gz"), None)
        if states_path and states_path.exists():
            try:
                mols = load_sdf_anyhow(states_path, removeHs=False, sanitize=True)
                if mols:
                    molfile_txt = molblock_original(mols[0])
            except Exception:
                pass
        # try marker's input path
        if not molfile_txt and (out_dir / "_processed.json").exists():
            try:
                meta = json.loads((out_dir / "_processed.json").read_text(encoding="utf-8"))
                ipath = meta.get("input_path", "")
                if ipath:
                    ipath = Path(ipath)
                    if ipath.exists():
                        mols = load_sdf_anyhow(ipath, removeHs=False, sanitize=True)
                        if mols:
                            molfile_txt = molblock_original(mols[0])
            except Exception:
                pass
        # final fallback: first molecule of between_windows.sdf
        if not molfile_txt:
            win_sdf = out_dir / f"{lig_id}_between_windows.sdf"
            if win_sdf.exists():
                try:
                    mols = load_sdf_anyhow(win_sdf, removeHs=False, sanitize=True)
                    if mols:
                        molfile_txt = molblock_original(mols[0])
                except Exception:
                    pass

        w0 = byQ.get(0)
        row = {
            "ligandennr": lig_id,
            "molfile_original": molfile_txt,
            "formula_Q0":  (w0["formula"] if w0 else ""),
            "bracket_Q0":  (f"({w0['lo']}, {w0['hi']})" if w0 else ""),
            "smiles_Q0":   (w0["smiles"] if w0 else ""),
            "inchi_Q0":    (w0["inchi"] if w0 else ""),
            "_windows_by_Q": byQ
        }
        rows.append(row)

    return rows, all_Qs

def net_charge(m): return sum(a.GetFormalCharge() for a in m.GetAtoms())

def _ensure_explicitHs(m):
    """Return a copy with all implicit Hs made explicit (keeps heavy-atom indices)."""
    mc = Chem.Mol(m)
    mc = Chem.AddHs(mc, addCoords=True)
    return mc

def _atom_summary(m, idx):
    a = m.GetAtomWithIdx(idx)
    return {
        "idx": idx,
        "symbol": a.GetSymbol(),
        "formal_charge": a.GetFormalCharge(),
        "explicit_valence": a.GetExplicitValence(),
        "implicit_valence": a.GetImplicitValence(),
        "num_explicit_h": a.GetNumExplicitHs(),
        "total_hs": a.GetTotalNumHs(includeNeighbors=True),
    }

def _snap(m, label, site_idx=None):
    d = {
        "label": label,
        "Q": net_charge(m),
        "formula": CalcMolFormula(m),
        "smiles": Chem.MolToSmiles(m, isomericSmiles=True, canonical=True),
    }
    if site_idx is not None:
        d["site"] = _atom_summary(m, site_idx)
    return d

def _add_h_and_charge(m, idx, dQ, dbg=None):
    nm = _ensure_explicitHs(m)
    if dbg is not None: dbg.append(_snap(nm, "before_addH", idx))
    em = Chem.EditableMol(nm)
    h = em.AddAtom(Chem.Atom(1))
    em.AddBond(idx, h, Chem.BondType.SINGLE)
    nm = em.GetMol()
    at = nm.GetAtomWithIdx(idx)
    at.SetFormalCharge(at.GetFormalCharge() + dQ)
    Chem.SanitizeMol(nm, catchErrors=True)
    if dbg is not None: dbg.append(_snap(nm, "after_addH", idx))
    return nm

def _remove_one_H_and_charge(m, idx, dQ, dbg=None):
    nm = _ensure_explicitHs(m)
    if dbg is not None: dbg.append(_snap(nm, "before_removeH", idx))
    nbrHs = [n.GetIdx() for n in nm.GetAtomWithIdx(idx).GetNeighbors() if n.GetAtomicNum()==1]
    if nbrHs:
        hidx = nbrHs[0]
        em = Chem.EditableMol(nm)
        em.RemoveBond(idx, hidx)
        em.RemoveAtom(hidx)
        nm = em.GetMol()
    at = nm.GetAtomWithIdx(idx)
    at.SetFormalCharge(at.GetFormalCharge() + dQ)
    Chem.SanitizeMol(nm, catchErrors=True)
    if dbg is not None: dbg.append(_snap(nm, "after_removeH", idx))
    return nm

def set_acidic_protonated(m, idx, dbg=None):
    nm = _ensure_explicitHs(m)
    # neutralize O- (if present) before adding H
    at = nm.GetAtomWithIdx(idx)
    if at.GetFormalCharge() < 0:
        at.SetFormalCharge(at.GetFormalCharge() + 1)
    # add H only if none explicitly present
    hasH = any(n.GetAtomicNum() == 1 for n in at.GetNeighbors())
    if not hasH:
        nm = _add_h_and_charge(nm, idx, 0, dbg)
    Chem.SanitizeMol(nm, catchErrors=True)
    return nm

def set_acidic_deprotonated(m, idx, dbg=None):
    nm = _ensure_explicitHs(m)
    # remove H first, then apply -1 charge
    nm = _remove_one_H_and_charge(nm, idx, 0, dbg)
    at = nm.GetAtomWithIdx(idx)
    at.SetFormalCharge(at.GetFormalCharge() - 1)
    Chem.SanitizeMol(nm, catchErrors=True)
    return nm

def set_basic_protonated(m, idx, dbg=None):
    nm = _ensure_explicitHs(m)
    # apply +1 charge first, then add H
    at = nm.GetAtomWithIdx(idx)
    at.SetFormalCharge(at.GetFormalCharge() + 1)
    nm = _add_h_and_charge(nm, idx, 0, dbg)
    Chem.SanitizeMol(nm, catchErrors=True)
    return nm

def set_basic_deprotonated(m, idx, dbg=None):
    nm = _ensure_explicitHs(m)
    # remove H first, then reduce charge by 1
    nm = _remove_one_H_and_charge(nm, idx, 0, dbg)
    at = nm.GetAtomWithIdx(idx)
    at.SetFormalCharge(at.GetFormalCharge() - 1)
    Chem.SanitizeMol(nm, catchErrors=True)
    return nm

def build_fully_protonated(m, sites_ordered, dbg=None):
    nm = _ensure_explicitHs(m)
    if dbg is not None: dbg.append(_snap(nm, "start_fully_protonated"))
    for _, sd in sites_ordered:
        idx = sd["idx"]; typ = sd["type"]
        nm = set_acidic_protonated(nm, idx, dbg) if typ=="acidic" else set_basic_protonated(nm, idx, dbg)
    Chem.SanitizeMol(nm, catchErrors=True)
    if dbg is not None: dbg.append(_snap(nm, "end_fully_protonated"))
    return nm

def titration_windows(base_mol, sites_ordered, debug_sink=None):
    if not sites_ordered: return []
    pKas = [sd["pka"] for _, sd in sites_ordered]
    dbg = [] if DEBUG_MODE else None

    cur = build_fully_protonated(base_mol, sites_ordered, dbg)
    windows = []

    def describe(m, lo, hi, label):
        mc = Chem.Mol(m)
        try: rdDepictor.Compute2DCoords(mc)
        except: pass
        entry = {
            "lo": lo, "hi": hi, "state": mc, "Q": net_charge(mc),
            "formula": CalcMolFormula(mc),
            "smiles": Chem.MolToSmiles(mc, isomericSmiles=True, canonical=True),
            "inchi": MolToInchi(mc) if hasattr(Chem, "MolToInchi") else ""
        }
        if dbg is not None: dbg.append({"label": label, **_snap(mc, "window_snapshot")})
        return entry

    windows.append(describe(cur, "-inf", f"{pKas[0]:.6g}", "window0"))

    for i, (_, sd) in enumerate(sites_ordered, start=1):
        idx, typ, pk = sd["idx"], sd["type"], sd["pka"]
        before_Q = net_charge(cur)
        cur = set_acidic_deprotonated(cur, idx, dbg) if typ=="acidic" else set_basic_deprotonated(cur, idx, dbg)
        Chem.SanitizeMol(cur, catchErrors=True)
        after_Q = net_charge(cur)
        # sanity: acidic step should Q-1; basic step should Q-1 (losing +1)
        expected_delta = -1
        if dbg is not None:
            dbg.append({"label":"step_check", "occ":i, "idx":idx, "type":typ,
                        "pKa":pk, "Q_before":before_Q, "Q_after":after_Q,
                        "deltaQ": after_Q-before_Q, "expected_delta": expected_delta})
        lo = f"{pKas[i-1]:.6g}"
        hi = f"{pKas[i]:.6g}" if i < len(pKas) else "+inf"
        windows.append(describe(cur, lo, hi, f"window{i}"))

    # persist debug snapshots if requested
    if DEBUG_MODE and debug_sink is not None:
        ensure_dir(debug_sink.parent)
        with open(debug_sink, "w", encoding="utf-8") as fh:
            for rec in dbg:
                fh.write(json.dumps(rec)+"\n")

    return windows

def molblock_original(m: Chem.Mol):
    txt = MolToMolBlock(m, includeStereo=True, kekulize=False)
    return txt.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n")

def draw_windows_png(windows: List[Dict], out_png: Path):
    if not windows: return
    mols = [w["state"] for w in windows]
    legends = [f"({w['lo']}, {w['hi']}) | Q={w['Q']}" for w in windows]
    mols2d = []
    for m in mols:
        mc = Chem.Mol(m)
        try: rdDepictor.Compute2DCoords(mc)
        except: pass
        mols2d.append(mc)
    img = MolsToGridImage(mols2d, molsPerRow=MOLS_PER_ROW, legends=legends, subImgSize=CELL_SIZE)
    ensure_dir(out_png.parent)
    if hasattr(img, "save"): img.save(str(out_png))
    else:
        data = getattr(img, "data", None) or (img._repr_png_() if hasattr(img, "_repr_png_") else None)
        if data is not None:
            with open(out_png, "wb") as f: f.write(data)

# --------------------
# Skip logic 
# --------------------
def should_skip_processed(sdf_path: Path, out_dir: Path, id_str: str) -> bool:
    """Return True if outputs are fresh for *this* input AND *this* filter policy + site list."""
    if not SKIP_PROCESSED:
        return False
    marker = out_dir / MARKER_FILENAME
    if not marker.exists():
        return False

    # marker must parse
    try:
        meta = json.loads(marker.read_text(encoding="utf-8"))
    except Exception:
        return False

    # 1) Input file unchanged?
    try:
        if meta.get("input_sha256") != sha256_file(sdf_path):
            return False
    except Exception:
        return False

    # 2) Required outputs present?
    for patt in REQUIRED_OUTPUTS:
        if not (out_dir / patt.format(id=id_str)).exists():
            return False
    if DRAW_IMAGES and REQUIRE_IMAGE_IF_SET and not (out_dir / f"{id_str}_windows.png").exists():
        return False

    # 3) Filter policy changed? → rebuild
    if meta.get("filter_policy_hash") != FILTER_POLICY_HASH:
        return False

    # 4) Site list (after current filters) changed? → rebuild
    try:
        mols = load_sdf_anyhow(sdf_path, removeHs=False, sanitize=True)
        base = mols[0] if mols else None
        sdf_text = sdf_path.read_text(encoding="utf-8", errors="ignore")
        sites_now = collect_sites_from_sdf_text(sdf_text) if sdf_text else []
        if base and sites_now:
            sites_now = filter_sites(base, sites_now)
        cur_sig = site_fingerprint(base, sites_now)
    except Exception:
        cur_sig = ""
    if meta.get("site_sig", "") != cur_sig:
        return False

    return True

def write_marker(sdf_path: Path, out_dir: Path, id_str: str, sites, windows):
    # compute base molecule for site_sig
    try:
        mols = load_sdf_anyhow(sdf_path, removeHs=False, sanitize=True)
        base = mols[0] if mols else None
    except Exception:
        base = None

    meta = {
        "ligandennr": id_str,
        "input_path": str(sdf_path),
        "input_size": sdf_path.stat().st_size,
        "input_mtime": sdf_path.stat().st_mtime,
        "input_sha256": sha256_file(sdf_path),
        "sites": [{"occ": occ, **sd} for occ, sd in sites],
        "num_windows": len(windows),
        "filter_policy_hash": FILTER_POLICY_HASH,
        "site_sig": site_fingerprint(base, sites),
    }
    (out_dir / MARKER_FILENAME).write_text(json.dumps(meta, indent=2), encoding="utf-8")

# ----------------
# Debug diagnosis
# ----------------
def _float_eq(a, b, tol=PH_TOL):
    try:
        return abs(float(a) - float(b)) <= tol
    except Exception:
        return False

def _string_is_neg_inf(s): return str(s).strip().lower() in ("-inf", "-infinity")
def _string_is_pos_inf(s): return str(s).strip().lower() in ("+inf", "inf", "infinity")

def _windows_from_tsv_df(dfw: pd.DataFrame):
    """
    Build a lite 'windows' list (lo, hi, Q) from an existing windows.tsv DataFrame.
    Only used for the SKIP path so we can still validate/write the summary row.
    """
    wins = []
    for _, r in dfw.iterrows():
        br = str(r.get("pH_bracket","")).strip()
        lo, hi = "", ""
        if br.startswith("(") and br.endswith(")") and "," in br:
            lo, hi = br[1:-1].split(",", 1)
            lo, hi = lo.strip(), hi.strip()
        wins.append({"lo": lo, "hi": hi, "Q": int(float(r["Q"]))})
    # sort by bracket lower bound (keeping -inf first)
    def _key(w):
        if _string_is_neg_inf(w["lo"]): return float("-inf")
        try: return float(w["lo"])
        except: return float("inf")
    wins.sort(key=_key)
    return wins

def _ops_signature(sites_ordered):
    """Return a compact string like 'A,B,A' using site types in pKa order."""
    return ",".join(("A" if sd["type"]=="acidic" else "B") for _, sd in sites_ordered)

def validate_sequence(lig_id: str, sites_ordered, windows) -> dict:
    """
    Pure checker. No chemistry guesses. Uses only the parsed SD props and built windows.
    Returns a dict with booleans + reasons; caller decides how to act.
    """
    diag = {
        "ligandennr": lig_id,
        "n_sites": len(sites_ordered or []),
        "n_windows": len(windows or []),
        "expected_windows": (len(sites_ordered or []) + 1),
        "has_windows": bool(windows),
        "has_sites": bool(sites_ordered),
        "issues": [],
    }

    # pKa analysis (from sites)
    pka_list = [sd["pka"] for _, sd in (sites_ordered or [])]
    pka_sorted = all(pka_list[i] <= pka_list[i+1] + PH_TOL for i in range(len(pka_list)-1))
    tie_groups = sum(1 for i in range(len(pka_list)-1) if _float_eq(pka_list[i], pka_list[i+1]))
    acidic_count = sum(1 for _, sd in (sites_ordered or []) if sd["type"]=="acidic")
    basic_count  = sum(1 for _, sd in (sites_ordered or []) if sd["type"]=="basic")
    diag.update(dict(
        pKa_sorted_nondec=pka_sorted,
        pKa_tie_groups=tie_groups,
        acidic_sites=acidic_count,
        basic_sites=basic_count,
        ops_signature=_ops_signature(sites_ordered or []),
    ))
    if not pka_sorted:
        diag["issues"].append("pKa_not_non_decreasing")

    # window analysis
    if windows:
        q_list = [int(w["Q"]) for w in windows]
        dq = [q_list[i+1]-q_list[i] for i in range(len(q_list)-1)]
        dq_all_neg1 = all(d == -1 for d in dq) if dq else True
        diag.update(dict(
            Q_first=q_list[0], Q_last=q_list[-1],
            Q_span=(q_list[0]-q_list[-1]) if len(q_list)>1 else 0,
            deltaQ_str=",".join(str(d) for d in dq) if dq else "",
            deltaQ_all_minus1=dq_all_neg1
        ))
        if not dq_all_neg1:
            diag["issues"].append("missing_link_or_bad_edit(ΔQ!=−1)")

        # Charge span should equal number of sites
        if len(q_list) >= 2:
            span_ok = ( (q_list[0] - q_list[-1]) == len(sites_ordered or []) )
            diag["Q_span_ok"] = span_ok
            if not span_ok:
                diag["issues"].append("charge_span_mismatch")
        else:
            diag["Q_span_ok"] = (len(sites_ordered or []) in (0,1))

        # brackets monotonic & fully covering (-inf, +inf)
        lo_list = [w["lo"] for w in windows]
        hi_list = [w["hi"] for w in windows]
        lo_ok = _string_is_neg_inf(lo_list[0]) or _float_eq(lo_list[0], "-inf")
        hi_ok = _string_is_pos_inf(hi_list[-1]) or _float_eq(hi_list[-1], "+inf")
        diag["bracket_has_-inf_to_+inf"] = (lo_ok and hi_ok)

        # Consecutive joins: hi[i] == lo[i+1] (within tol or textual equality for infinities)
        joins_ok = True
        for i in range(len(windows)-1):
            a = str(windows[i]["hi"]).strip()
            b = str(windows[i+1]["lo"]).strip()
            if _string_is_pos_inf(a) and _string_is_pos_inf(b): 
                joins_ok = True; break
            if _string_is_neg_inf(a) and _string_is_neg_inf(b):
                joins_ok = True; break
            if not (_float_eq(a, b) or a == b):
                joins_ok = False; break
        diag["brackets_chain_ok"] = joins_ok
        if not joins_ok:
            diag["issues"].append("pH_brackets_disjoint_or_out_of_order")

        # Neutral window presence/uniqueness
        zero_idxs = [i for i, q in enumerate(q_list) if q == 0]
        diag["neutral_window_count"] = len(zero_idxs)
        diag["neutral_unique"] = (len(zero_idxs) == 1)
        if len(zero_idxs) == 0:
            diag["issues"].append("no_Q0_window")
        elif len(zero_idxs) > 1:
            diag["issues"].append("multiple_Q0_windows")

        # Window count check
        diag["windows_match_expected"] = (len(windows) == diag["expected_windows"])
        if not diag["windows_match_expected"]:
            diag["issues"].append("window_count_mismatch")

    else:
        # no windows produced
        diag.update(dict(
            Q_first=None, Q_last=None, Q_span=None,
            deltaQ_str="", deltaQ_all_minus1=False,
            Q_span_ok=False, bracket_has_beginf_to_posinf=False,
            brackets_chain_ok=False, neutral_window_count=0,
            neutral_unique=False, windows_match_expected=False
        ))
        diag["issues"].append("no_windows_built")

    diag["status"] = "ok" if (not diag["issues"]) else "needs_review"
    return diag

def write_ligand_validation(out_dir: Path, lig_id: str, diag: dict):
    """Persist per-ligand validation JSON."""
    out_path = out_dir / f"{lig_id}_validation.json"
    ensure_dir(out_path.parent)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(diag, fh, indent=2)
    return out_path

def _to_list_safe(v):
    if isinstance(v, list): return v
    s = "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)
    s = s.strip()
    if not s: return []
    try:
        x = json.loads(s);  return x if isinstance(x, list) else [x]
    except Exception:
        try:
            x = ast.literal_eval(s);  return x if isinstance(x, list) else [x]
        except Exception:
            return [s]
        
# === DIAGNOSE EXISTING OUTPUTS ===
def diagnose_existing_outputs(parsed_root: Path = None, write_tsv: bool = True):
    if parsed_root is None:
        parsed_root = PARSED_OUTPUT_DIR
    debug_rows = []
    for out_dir in sorted(parsed_root.glob("*_pKa*")):
        lig_id = out_dir.name[:-4]  # strip "_pKa*"
        win_tsv = out_dir / f"{lig_id}_windows.tsv"
        if not win_tsv.exists():
            continue
        try:
            dfw = pd.read_csv(win_tsv, sep="\t")
        except Exception:
            continue
        wins = _windows_from_tsv_df(dfw)

        # Parse sites from the original SDF if available (or marker's input_path)
        sites, text = [], ""
        try:
            states_path = next(SDF_INPUT_DIR.glob(f"{lig_id}_states*.sdf"), None) \
              or next(SDF_INPUT_DIR.glob(f"{lig_id}_states*.sdf.gz"), None)
            if states_path.exists():
                text = states_path.read_text(encoding="utf-8", errors="ignore")
            else:
                marker = out_dir / "_processed.json"
                if marker.exists():
                    meta = json.loads(marker.read_text(encoding="utf-8"))
                    ip = Path(meta.get("input_path", ""))
                    if ip.exists():
                        text = ip.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            text = ""
        if text:
            sites = collect_sites_from_sdf_text(text)

        diag = validate_sequence(lig_id, sites, wins)
        try:
            write_ligand_validation(out_dir, lig_id, diag)
        except Exception:
            pass
        debug_rows.append(diag)

    if write_tsv and debug_rows:
        df_dbg = pd.DataFrame(debug_rows)
        ensure_dir(DEBUG_SUMMARY_TSV.parent)
        df_dbg.to_csv(DEBUG_SUMMARY_TSV, sep="\t", index=False, encoding="utf-8")
        print(f"[debug] (rehydrate) wrote run summary: {DEBUG_SUMMARY_TSV} rows={len(df_dbg)}")
    return debug_rows

def print_summary(debug_rows: list = None,
                  tsv_path: Path = None,
                  sample_n: int = 6,
                  run_events: list = None,
                  parsed_root: Path = None,
                  rehydrate_if_missing: bool = True):
    """
    Pretty console summary of SDF→windows results.
    - Uses `debug_rows` if provided; else reads `tsv_path` (defaults to DEBUG_SUMMARY_TSV).
    - If TSV missing and `rehydrate_if_missing=True`, tries to rebuild diagnostics from outputs
      using `parsed_root` (defaults to PARSED_OUTPUT_DIR).
    - Prints [warning] sections with examples and [skip] statistics if run_events are provided.
    """
    # ---- load diagnostics table ----
    df = None
    if debug_rows:
        df = pd.DataFrame(debug_rows)
    else:
        tsv = tsv_path or DEBUG_SUMMARY_TSV
        if not tsv.exists() and rehydrate_if_missing:
            rr = parsed_root or PARSED_OUTPUT_DIR
            print(f"[summary] {tsv} missing → rehydrating from existing *_pKa* outputs under {rr} …")
            debug_rows = diagnose_existing_outputs(rr, write_tsv=True)
            df = pd.DataFrame(debug_rows)
        elif tsv.exists():
            df = pd.read_csv(tsv, sep="\t")
        else:
            print(f"[summary] no data: {tsv} not found and rehydrate disabled.")
            return

    if df.empty:
        print("[summary] no ligands found.")
        return

    # normalize numeric/int-ish fields
    for c in ("n_sites","n_windows","expected_windows","neutral_window_count"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

    # header
    n = len(df)
    ok = int((df.get("status","ok") == "ok").sum())
    bad = n - ok
    print("\n=== QupKake SDF → windows summary ===")
    print(f"Ligands analyzed: {n:,}")
    print(f"OK: {ok:,} ({ok/max(n,1):.2%})   needs_review: {bad:,} ({bad/max(n,1):.2%})")

    # window integrity
    wc     = int((df.get("windows_match_expected", False) == True).sum())
    dqok   = int((df.get("deltaQ_all_minus1", False) == True).sum())
    spanok = int((df.get("Q_span_ok", False) == True).sum())
    chain  = int((df.get("brackets_chain_ok", False) == True).sum())
    cover  = int((df.get("bracket_has_-inf_to_+inf", False) == True).sum())
    print("\nWindow integrity:")
    print(f"  windows = sites+1:     {wc:>5}/{n} ({wc/max(n,1):.2%})")
    print(f"  ΔQ per step = −1:      {dqok:>5}/{n} ({dqok/max(n,1):.2%})")
    print(f"  charge span matches:   {spanok:>5}/{n} ({spanok/max(n,1):.2%})")
    print(f"  brackets chain OK:     {chain:>5}/{n} ({chain/max(n,1):.2%})")
    print(f"  covers -inf→+inf:      {cover:>5}/{n} ({cover/max(n,1):.2%})")

    # neutral window presence/uniqueness
    zc = df.get("neutral_window_count", pd.Series([None]*n))
    n0 = int((zc == 0).sum()); n1 = int((zc == 1).sum()); nM = int((pd.to_numeric(zc, errors="coerce") > 1).sum())
    print("\nNeutral state (Q=0):")
    print(f"  none: {n0:>5}   unique: {n1:>5}   multiple: {nM:>5}")

    # pKa ordering / ties
    nondec = int((df.get("pKa_sorted_nondec", False) == True).sum())
    ties_any = int((pd.to_numeric(df.get("pKa_tie_groups", 0), errors="coerce").fillna(0) > 0).sum())
    print("\npKa order (from SD props):")
    print(f"  non-decreasing: {nondec:>5}/{n} ({nondec/max(n,1):.2%})")
    print(f"  has ties:       {ties_any:>5}/{n} ({ties_any/max(n,1):.2%})")

    # ops signature
    if "ops_signature" in df.columns:
        sig = df["ops_signature"].fillna("")
        sc = sig.value_counts().head(8)
        if len(sc):
            print("\nMost common site-type sequences (A=acidic, B=basic):")
            for s, cnt in sc.items():
                print(f"  {s if s else '(none)':<16} {cnt:>5} ({cnt/max(n,1):.2%})")

    # ---- [skip] / run action stats ----
    if run_events:
        dfE = pd.DataFrame(run_events)
        total = len(dfE)
        n_proc = int((dfE["event"] == "processed").sum())
        n_skip = int((dfE["event"] == "skip_up_to_date").sum())
        n_incm = int((dfE["event"] == "skip_incomplete").sum())
        n_err  = int((dfE["event"] == "error").sum())
        print("\n[skip] run actions:")
        print(f"  processed:       {n_proc:>5} / {total}")
        print(f"  skipped (fresh): {n_incm:>5} / {total}")
        print(f"  skipped (uptod): {n_skip:>5} / {total}")
        print(f"  errors:          {n_err:>5} / {total}")
        # examples
        for label in ("skip_incomplete","skip_up_to_date","error"):
            ids = dfE[dfE["event"] == label]["ligandennr"].astype(str).tolist()[:sample_n]
            if ids:
                print(f"  examples {label}: {', '.join(ids)}")
    else:
        print("\n[skip] run actions: n/a (no run_events provided)")

    # ---- Issues & warnings ----
    # 1) gather explicit 'issues' the validator recorded
    issues_col = df.get("issues", pd.Series([[]]*n)).apply(_to_list_safe)
    issue_pairs = []
    for i, lst in issues_col.items():
        for it in lst:
            issue_pairs.append((it, str(df.iloc[i]["ligandennr"])))
    # 2) synthesize "pKa_ties" warning if tie_groups > 0
    tk = pd.to_numeric(df.get("pKa_tie_groups", 0), errors="coerce").fillna(0)
    for i, v in enumerate(tk.tolist()):
        if v > 0:
            issue_pairs.append(("pKa_ties", str(df.iloc[i]["ligandennr"])))

    if issue_pairs:
        tmp = pd.DataFrame(issue_pairs, columns=["issue","ligandennr"])
        frq = tmp["issue"].value_counts()
        print("\n[warning] / [issues] by frequency:")
        for issue, cnt in frq.items():
            print(f"  {issue:<36} {cnt:>5} ({cnt/max(len(tmp),1):.2%})")
        print("\nExamples per top issue:")
        for issue in frq.index[:6]:
            ids = tmp.loc[tmp["issue"] == issue, "ligandennr"].unique().tolist()[:sample_n]
            print(f"  {issue}: {', '.join(ids)}")
    else:
        print("\n[warning] no issues recorded.")

def print_debug(debug_string: str, debug_output = SUMMARY_LOG):  # Append to log and echo to console
    print(debug_string)
    try:
        p = Path(debug_output)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(str(debug_string).rstrip("\n") + "\n")
    except Exception:
        # Don't let logging failures break the run
        pass
    return

# --------------------
# Batch
# --------------------
def run_batch():
    # Ensure output directories exist
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    PARSED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    sdf_files = sorted(SDF_INPUT_DIR.glob("*_states*.sdf")) + sorted(SDF_INPUT_DIR.glob("*_states*.sdf.gz"))
    print_debug(f"[batch] found {len(sdf_files)} files under {SDF_INPUT_DIR}")
    all_rows = []
    all_Qs  = set()
    debug_rows = [] 

    for sdf_path in sdf_files:
        name = sdf_path.name
        m = re.match(r"^(?P<id>.+?)_states(?P<extra>.*)\.sdf(?:\.gz)?$", name, re.IGNORECASE)
        lig_id   = m.group("id") if m else name.split("_states")[0]
        extra    = m.group("extra") if m else ""
        id_str   = f"{lig_id}{extra}" 
        out_dir = PARSED_OUTPUT_DIR / f"{id_str}_pKa"
        ensure_dir(out_dir)

        # Skip processing path
        if should_skip_processed(sdf_path, out_dir, id_str):
            if VERBOSE_OUTPUT:
                print_debug(f"[skip] {id_str}: already processed and up-to-date.")
            # For the aggregate CSV, we still need to load the windows TSV so this ligand appears
            win_tsv = out_dir / f"{id_str}_windows.tsv"
            if not win_tsv.exists():
                log_event("skip_incomplete", id_str, reason="windows_tsv_missing")
                continue
            if win_tsv.exists():
                try:
                    dfw = pd.read_csv(win_tsv, sep="\t")
                    log_event("skip_up_to_date", id_str, reason="hash_match_and_outputs_present")
                    # reconstruct per-Q mapping
                    byQ = {}
                    for _, row in dfw.iterrows():
                        Q = int(row["Q"])
                        lo, hi = parse_bracket(row.get("pH_bracket", ""))   # <— use helper
                        byQ[Q] = {
                            "formula": row.get("formula", ""),
                            "smiles":  row.get("smiles", ""),
                            "inchi":   row.get("inchi", ""),
                            "lo": lo, "hi": hi, "Q": Q
                        }
                        all_Qs.add(Q)
                    # original molfile from base SDF (load first mol)
                    mols = load_sdf_anyhow(sdf_path, removeHs=False, sanitize=True)
                    base = mols[0] if mols else None
                    molfile_txt = molblock_original(base) if base else ""
                    w0 = byQ.get(0, None)
                    row = {
                        "ligandennr": id_str, "molfile_original": molfile_txt,
                        "formula_Q0": (w0["formula"] if w0 else ""),
                        "bracket_Q0": (f"({w0['lo']}, {w0['hi']})" if w0 else ""),
                        "smiles_Q0":  (w0["smiles"] if w0 else ""),
                        "inchi_Q0":   (w0["inchi"] if w0 else ""),
                        "_windows_by_Q": byQ
                    }

                    # === DEBUG (SKIP PATH) ===
                    # Re-parse sites from the SDF text so validation sees the site list:
                    try:
                        sdf_text = sdf_path.read_text(encoding="utf-8", errors="ignore")
                    except Exception:
                        sdf_text = ""
                    sites = collect_sites_from_sdf_text(sdf_text) if sdf_text else []
                    if base and sites:
                        sites = filter_sites(base, sites)
                    # Reconstruct lite windows list from the TSV (lo,hi,Q)
                    wins = _windows_from_tsv_df(dfw)
                    diag = validate_sequence(id_str, sites, wins)

                    # Persist per-ligand JSON and append to run-level TSV buffer
                    try:
                        write_ligand_validation(out_dir, id_str, diag)
                    except Exception as _e:
                        log_event("error", id_str, msg=str(_e))
                        print_debug(f"[warn] could not write validation for {id_str}: {_e}")
                    debug_rows.append(diag)
                    
                    all_rows.append(row)
                except Exception as e:
                    log_event("skip_incomplete", id_str, reason="windows_tsv_unreadable", msg=str(e))
                    print_debug(f"[warn] could not include {id_str} from cached TSV: {e}")

            if dfw.empty:
                log_event("skip_incomplete", id_str, reason="windows_tsv_empty")
                continue
            continue

        # Fresh processing path
        mols = load_sdf_anyhow(sdf_path, removeHs=False, sanitize=True)
        if not mols:
            log_event("skip_incomplete", id_str, reason="empty_sdf")
            print_debug(f"[WARN] empty SDF: {sdf_path}")
            continue
        base = mols[0]
        sdf_text = sdf_path.read_text(encoding="utf-8", errors="ignore")
        sites = collect_sites_from_sdf_text(sdf_text)
        if not sites:
            log_event("skip_incomplete", id_str, reason="no_sites")
            if VERBOSE_OUTPUT:
                print_debug(f"[SKIP] {id_str}: no <idx>/<pka_type>/<pka> in SD props")
            continue
        sites = filter_sites(base, sites)
        debug_file = out_dir / f"{id_str}_debug.jsonl"
        windows = titration_windows(base, sites, debug_sink=debug_file)
        if not windows:
            write_ligand_validation(out_dir, id_str, validate_sequence(id_str, sites, []))
            log_event("skip_incomplete", id_str, reason="no_windows")
            continue

        # 1) SDF per window
        win_sdf = out_dir / f"{id_str}_between_windows.sdf"
        w = Chem.SDWriter(str(win_sdf))
        for i, wi in enumerate(windows):
            m = Chem.Mol(wi["state"])
            m.SetProp("_Name", f"{id_str}_w{i}_Q{wi['Q']}")
            m.SetProp("pH_lo", str(wi["lo"])); m.SetProp("pH_hi", str(wi["hi"]))
            m.SetProp("net_charge", str(wi["Q"]))
            m.SetProp("formula", wi["formula"])
            m.SetProp("smiles", wi["smiles"])
            m.SetProp("inchi", wi["inchi"])
            w.write(m)
        w.close()

        # 2) TSV summary
        win_tsv = out_dir / f"{id_str}_windows.tsv"
        with open(win_tsv, "w", newline="", encoding="utf-8") as fh:
            cw = csv.writer(fh, delimiter="\t")
            cw.writerow(["ligandennr","window_index","pH_bracket","Q","formula","smiles","inchi"])
            for i, wi in enumerate(windows):
                cw.writerow([id_str, i, f"({wi['lo']}, {wi['hi']})", wi["Q"], wi["formula"], wi["smiles"], wi["inchi"]])

        # 3) Image
        if DRAW_IMAGES: 
            draw_windows_png(windows, out_png=out_dir / f"{id_str}_windows.png")

        # 4) Marker
        write_marker(sdf_path, out_dir, id_str, sites, windows)

        # Aggregate for CSV
        molfile_txt = molblock_original(base)
        byQ = {}
        for wi in windows:
            byQ[wi["Q"]] = wi
            all_Qs.add(wi["Q"])
        w0 = byQ.get(0, None)
        row = {
            "ligandennr": id_str, "molfile_original": molfile_txt,
            "formula_Q0": (w0["formula"] if w0 else ""),
            "bracket_Q0": (f"({w0['lo']}, {w0['hi']})" if w0 else ""),
            "smiles_Q0":  (w0["smiles"] if w0 else ""),
            "inchi_Q0":   (w0["inchi"] if w0 else ""),
            "_windows_by_Q": byQ
        }

        # === DEBUG (FRESH PATH) ===
        diag = validate_sequence(id_str, sites, [{"lo": w["lo"], "hi": w["hi"], "Q": int(w["Q"])} for w in windows])
        write_ligand_validation(out_dir, id_str, diag)
        if STRICT_VALIDATE and diag["status"] != "ok":
            raise RuntimeError(f"[validate] {id_str} failed: {diag['issues']}")
        debug_rows.append(diag)
        log_event("processed", id_str, windows=len(windows))
        all_rows.append(row)

    # --- collect rows from this run as before ---
    rows_from_run = all_rows          # produced by the loop above
    Qs_from_run   = all_Qs

    # --- NEW: also harvest every existing *_pKa* folder, regardless of SKIP_PROCESSED ---
    rows_from_builds, Qs_from_builds = harvest_from_build_dirs(PARSED_OUTPUT_DIR)

    # Merge (builds provide a baseline, current run overrides same ID)
    by_id = {r["ligandennr"]: r for r in rows_from_builds}
    for r in rows_from_run:
        by_id[r["ligandennr"]] = r

    merged_rows = list(by_id.values())
    all_Qs_union = set(Qs_from_builds) | set(Qs_from_run)

    if not merged_rows:
        print_debug("[batch] nothing to write to CSV.")
    else:
        Qs_sorted = sorted(all_Qs_union, reverse=True)  # most protonated to least
        cols = ["ligandennr","molfile_original","formula_Q0","bracket_Q0","smiles_Q0","inchi_Q0"]
        for Q in Qs_sorted:
            cols += [f"formula_Q_{Q}", f"bracket_Q_{Q}", f"smiles_Q_{Q}", f"inchi_Q_{Q}"]

        materialized = []
        for r in merged_rows:
            row = {k: r.get(k, "") for k in ["ligandennr","molfile_original","formula_Q0","bracket_Q0","smiles_Q0","inchi_Q0"]}
            byQ = r.get("_windows_by_Q", {})
            for Q in Qs_sorted:
                wi = byQ.get(Q)
                row[f"formula_Q_{Q}"] = (wi["formula"] if wi else "")
                row[f"bracket_Q_{Q}"] = (f"({wi['lo']}, {wi['hi']})" if wi else "")
                row[f"smiles_Q_{Q}"]  = (wi["smiles"] if wi else "")
                row[f"inchi_Q_{Q}"]   = (wi["inchi"] if wi else "")
            materialized.append(row)

        df = pd.DataFrame(materialized, columns=cols)
        ensure_dir(OUT_CSV.parent)
        df.to_csv(OUT_CSV, index=False, encoding="utf-8")
        print_debug(f"[batch] wrote CSV: {OUT_CSV}  rows={len(df)}  cols={len(df.columns)}")

    # === DEBUG === run-level summary TSV
    if debug_rows:
        df_dbg = pd.DataFrame(debug_rows)
        ensure_dir(DEBUG_SUMMARY_TSV.parent)
        df_dbg.to_csv(DEBUG_SUMMARY_TSV, sep="\t", index=False, encoding="utf-8")
        print_debug(f"[debug] wrote run summary: {DEBUG_SUMMARY_TSV} rows={len(df_dbg)}")

    # === SUMMARY PRINT ===
    print_summary(tsv_path=DEBUG_SUMMARY_TSV,
              sample_n=6,
              run_events=RUN_EVENTS,
              parsed_root=PARSED_OUTPUT_DIR,
              rehydrate_if_missing=True)
    
    # === FILTER SUMMARY (optional but recommended) ===
    if FILTER_STATS:
        print_debug("\n=== Special filter summary (all ligands) ===")
        for k, v in FILTER_STATS.most_common():
            print_debug(f"{k:>32} : {v}")    

def summarize_fresh_incomplete(sdf_input_dir: Path = None, parsed_output_dir: Path = None, out_csv: Optional[Path] = None):
    """
    Reconstruct the set of ligands that would be considered "fresh/incomplete" by
    inspecting inputs and build outputs. For each *_states*.sdf input, check whether
    the required outputs exist. If not, try to infer a short reason:
        - empty_sdf: input SDF has no molecules
        - parse_error: RDKit failed to parse SDF
        - no_sites: no <idx>/<pka_type>/<pka> triples found in SD props
        - filtered_no_sites: site triples exist but are all filtered out by policy
        - no_windows: windows generation produced none
        - windows_tsv_missing / windows_tsv_empty / windows_tsv_unreadable: output TSV issues
    Also annotates fallback (id contains "_fallback").
    Writes a CSV under build/ if out_csv not provided.
    """
    if sdf_input_dir is None:
        sdf_input_dir = SDF_INPUT_DIR
    if parsed_output_dir is None:
        parsed_output_dir = PARSED_OUTPUT_DIR
    rows = []
    sdf_files = sorted(sdf_input_dir.glob("*_states*.sdf")) + sorted(sdf_input_dir.glob("*_states*.sdf.gz"))
    for sdf_path in sdf_files:
        name = sdf_path.name
        m = re.match(r"^(?P<id>.+?)_states(?P<extra>.*)\.sdf(?:\.gz)?$", name, re.IGNORECASE)
        lig_id   = m.group("id") if m else name.split("_states")[0]
        extra    = m.group("extra") if m else ""
        id_str   = f"{lig_id}{extra}"
        out_dir = parsed_output_dir / f"{id_str}_pKa"
        win_tsv = out_dir / f"{id_str}_windows.tsv"
        marker  = out_dir / MARKER_FILENAME

        # If outputs are present and windows.tsv is readable+non-empty, not incomplete
        tsv_status = None
        if win_tsv.exists():
            try:
                dfw = pd.read_csv(win_tsv, sep="\t")
                if dfw.empty:
                    tsv_status = "windows_tsv_empty"
                else:
                    # healthy, skip
                    continue
            except Exception as e:
                tsv_status = "windows_tsv_unreadable"
                tsv_error = str(e)
        else:
            tsv_status = "windows_tsv_missing"

        # Diagnose underlying input cause
        reason = tsv_status
        note = ""
        try:
            mols = load_sdf_anyhow(sdf_path, removeHs=False, sanitize=True)
        except Exception as e:
            mols = []
            reason = "parse_error"
            note = str(e)

        if reason == tsv_status and not mols:
            # Could still be an empty file case
            try:
                size = sdf_path.stat().st_size
                if size >= 0:
                    # Differentiate empty_sdf from parse_error
                    if reason != "parse_error":
                        reason = "empty_sdf"
            except Exception:
                pass

        if mols:
            base = mols[0]
            try:
                sdf_text = sdf_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                sdf_text = ""
            sites_raw = collect_sites_from_sdf_text(sdf_text) if sdf_text else []
            if not sites_raw:
                reason = "no_sites"
            else:
                sites_f = filter_sites(base, sites_raw)
                if not sites_f:
                    reason = "filtered_no_sites"
                else:
                    try:
                        wins = titration_windows(base, sites_f, debug_sink=None)
                    except Exception as e:
                        wins = []
                        note = f"titration_error: {e}"
                    if not wins:
                        reason = "no_windows"

        rows.append({
            "ligandennr": id_str,
            "is_fallback": ("_fallback" in lig_id.lower()),
            "reason": reason,
            "marker_present": marker.exists(),
            "out_dir": str(out_dir),
            "input_path": str(sdf_path),
            "notes": note,
        })

    df = pd.DataFrame(rows)
    if out_csv is None:
        out_csv = BUILD_DIR / "incomplete_ligands.csv"
    ensure_dir(Path(out_csv).parent)
    df.to_csv(out_csv, index=False, encoding="utf-8")
    print_debug(f"[report] wrote incomplete report: {out_csv}  rows={len(df)}")
    # Also echo a tiny frequency table of reasons
    if not df.empty and "reason" in df.columns:
        vc = df["reason"].value_counts()
        print_debug("[report] reasons:")
        for k, v in vc.items():
            print_debug(f"  {k:<24} {v}")
    return rows

def explain_incomplete(sdf_input_dir: Path = None, out_tsv: Optional[Path] = None):
    """Generate per-ligand, per-site explanations for the current incomplete set.
    No command-line flags; callable from code or main.
    """
    if sdf_input_dir is None:
        sdf_input_dir = SDF_INPUT_DIR
    inc_csv = BUILD_DIR / "incomplete_ligands.csv"
    if not inc_csv.exists():
        print_debug("[explain] incomplete_ligands.csv not found; generating it first …")
        summarize_fresh_incomplete()
    try:
        inc_df = pd.read_csv(inc_csv)
    except Exception as e:
        print_debug(f"[explain] cannot read {inc_csv}: {e}")
        return None

    rows = []
    for _, r in inc_df.iterrows():
        lig = str(r.get("ligandennr", "")).strip()
        if not lig:
            continue
        sdf_path = sdf_input_dir / f"{lig}_states.sdf"
        if (not sdf_path.exists()):
            gz = sdf_input_dir / f"{lig}_states.sdf.gz"
            if gz.exists():
                sdf_path = gz
        if (not sdf_path.exists()):
            rows.append({"ligandennr": lig, "phase": "input", "note": "states.sdf not found"})
            continue
        try:
            mols = load_sdf_anyhow(sdf_path, removeHs=False, sanitize=True)
        except Exception as e:
            rows.append({"ligandennr": lig, "phase": "input", "note": f"parse_error: {e}"})
            continue
        if not mols:
            rows.append({"ligandennr": lig, "phase": "input", "note": "empty_sdf"})
            continue
        base = mols[0]
        text = sdf_path.read_text(encoding="utf-8", errors="ignore") if sdf_path.suffix.lower() == ".sdf" else ""
        sites = collect_sites_from_sdf_text(text) if text else []
        if not sites:
            rows.append({"ligandennr": lig, "phase": "sites", "note": "no_sites_props_found"})
            continue
        # record raw sites
        for occ, sd in sites:
            rows.append({
                "ligandennr": lig, "phase": "sites_raw", "occ": occ,
                "idx": sd.get("idx"), "type": sd.get("type"), "pka": sd.get("pka"),
            })
        # apply filters (with diagnostics)
        dropped = []
        sites_f = filter_sites(base, sites, dropped_out=dropped)
        # kept
        for occ, sd in sites_f:
            rows.append({
                "ligandennr": lig, "phase": "kept", "occ": occ,
                "idx": sd.get("idx"), "type": sd.get("type"), "pka": sd.get("pka"),
                "reason": "kept",
            })
        # dropped
        for occ, idx, typ, pka, why in dropped:
            rows.append({
                "ligandennr": lig, "phase": "dropped", "occ": occ,
                "idx": idx, "type": typ, "pka": pka, "reason": why,
            })

    df = pd.DataFrame(rows)
    out_path = out_tsv or (BUILD_DIR / "incomplete_explanations.tsv")
    ensure_dir(out_path.parent)
    df.to_csv(out_path, sep="\t", index=False, encoding="utf-8")
    print_debug(f"[explain] wrote {out_path}  rows={len(df)}")
    return out_path

if __name__ == "__main__":
    # Default non-CLI execution: run batch, write incomplete report, then explanations.
    run_batch()
    summarize_fresh_incomplete()
    explain_incomplete()
        
