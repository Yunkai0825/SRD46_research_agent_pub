"""
Merge qupkake pKa information into liganden_w CSV.

Behavior:
- Left-join on ligand ID (ligandenID or ligandennr) to bring in all qupkake columns.
- If a liganden row has no match in qupkake, fill only these defaults:
  - formula_Q0: from liganden's 'formula' if present else 'COMPOSITION'
  - smiles_Q0: from liganden's 'SMILES'
  - inchi_Q0: from liganden's 'InChI'
  - bracket_Q0: "(-inf, +inf)"
- Do not use argparse; configure paths below.

Notes:
- ID normalization is robust: accepts int/float/string IDs (e.g., 5760.0 -> '5760').
- Preserves all original liganden columns and appends qupkake columns.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, List
from datetime import datetime

import pandas as pd


# =====================
# PATH CONFIGURATION - pip1c pipeline standard
# =====================
CODE_ROOT = Path(__file__).resolve().parent
PIPELINE_ROOT = CODE_ROOT.parent  # pip1c_parse_liganden_moldata_pKa_SRD46
PROJECT_ROOT = PIPELINE_ROOT.parent.parent  # NIST_SRD46_Correction_and_Parser

# Input: liganden CSV from pip1c-4 (with chemical names)
INPUT_DIR_PIP4 = PIPELINE_ROOT / "_build" / "pip1c_4_chemical_names_output"
LIGANDEN_CSV = str(INPUT_DIR_PIP4 / "mol_data_with_names.csv")

# Input: qupkake pKa CSV from pip1c-5b (SDF parsing). 5b writes to
# _build/pip1c_5b_SDF_parsed_output/qupkake_pka_liganden.csv; fall back to the
# copied _output location if the build file is absent.
INPUT_DIR_PIP5B = PIPELINE_ROOT / "_build" / "pip1c_5b_SDF_parsed_output"
if not (INPUT_DIR_PIP5B / "qupkake_pka_liganden.csv").exists():
	INPUT_DIR_PIP5B = PROJECT_ROOT / "_output" / "pip1c_5b_Qupkake_parsed"
QUPKAKE_CSV = str(INPUT_DIR_PIP5B / "qupkake_pka_liganden.csv")

# Build: all outputs go to _build/pip1c_6_pKa_enriched_output/
BUILD_DIR = PIPELINE_ROOT / "_build" / "pip1c_6_pKa_enriched_output"
OUTPUT_CSV = str(BUILD_DIR / "liganden_w_moldata_qupkake_parsed.csv")

# Optional: Path to the original liganden CSV (pre-parsed master list). If None, we'll auto-discover.
ORIGINAL_LIGANDEN_CSV = None

# ============== Debug/Logging setup ==============
NOW = datetime.now()
TIMESTAMP = NOW.strftime("%Y-%m-%d-%H-%M-%S")
LOG_DIR = BUILD_DIR / "logs"
LOG_FILE = str(LOG_DIR / f"summary_log_pip-7-merge-qupkake_{TIMESTAMP}.txt")


def _ensure_dir(path) -> Path:
	"""Ensure directory exists; accepts str or Path."""
	p = Path(path)
	if p.exists() and not p.is_dir():
		raise FileExistsError(f"Expected directory but found file at: {p}")
	p.mkdir(parents=True, exist_ok=True)
	return p


def print_debug(debug_string: str, debug_output = LOG_FILE) -> None:
	print(debug_string)
	try:
		_ensure_dir(Path(debug_output).parent)
		with open(debug_output, "a", encoding="utf-8") as f:
			f.write(str(debug_string) + "\n")
	except Exception:
		# Best-effort logging; ignore file I/O errors
		pass


def _normalize_id(val) -> Optional[str]:
	"""Normalize various ID formats to a comparable string integer.

	Examples:
	- 5760.0 -> '5760'
	- '5760' -> '5760'
	- ' 5760.000 ' -> '5760'
	- None/NaN -> None
	"""
	if pd.isna(val):
		return None
	try:
		# Some datasets store as float-like strings; coerce to float then to int safely.
		num = float(str(val).strip())
		return str(int(num))
	except Exception:
		# Fallback: keep only leading integer digits if present
		s = str(val).strip()
		digits = []
		for ch in s:
			if ch.isdigit():
				digits.append(ch)
			elif digits:
				# stop at first non-digit after digits started
				break
		return "".join(digits) if digits else None


def _ensure_columns(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
	"""Ensure the DataFrame has the given columns; create empty ones if missing."""
	for c in cols:
		if c not in df.columns:
			df[c] = pd.NA
	return df


def _find_original_liganden_csv() -> Optional[Path]:
	"""Attempt to auto-discover the original liganden CSV.

	Checks pipeline build directories and project input folders.
	Returns the first existing path or None.
	"""
	candidates = [
		# pip1c-3 output (HxL parsed)
		PIPELINE_ROOT / "_build" / "pip1c_3_HxL_output" / "liganden_moldata_HxL_parsed.csv",
		# pip1c-2 output
		PIPELINE_ROOT / "_build" / "pip1c_2_SMILS_InChi_output" / "mol_data_enriched.csv",
		# pip1c-1 output
		PIPELINE_ROOT / "_build" / "pip1c_1_molfile_output" / "mol_data_decoded.csv",
		# Project input folder
		PROJECT_ROOT / "_input" / "SRD46_SQL_and_CSV" / "liganden.csv",
	]
	for p in candidates:
		try:
			if p.exists() and p.is_file():
				return p
		except Exception:
			pass
	return None


def _augment_with_original(
	out_df: pd.DataFrame,
	original_path: Optional[Path],
	lig_id_col: str,
	placeholder: str = "*",
) -> pd.DataFrame:
	"""Append rows that exist in the original liganden CSV but are missing
	in the current out_df (by normalized ID). For appended rows, preserve any
	columns present in the original file; fill all other columns with a placeholder.

	This mirrors the "keep placeholders for missing" pattern used elsewhere.
	"""
	# Ensure we have a merge_id in out_df for comparison
	if "merge_id" not in out_df.columns:
		if lig_id_col not in out_df.columns:
			print_debug("augment_with_original: lig_id_col not in output; skipping augmentation")
			return out_df
		out_df = out_df.copy()
		out_df["merge_id"] = out_df[lig_id_col].apply(_normalize_id)

	# Resolve original path if not provided
	orig_path = Path(original_path) if original_path else _find_original_liganden_csv()
	if not orig_path or not orig_path.exists():
		print_debug(f"Original liganden CSV not found; tried: {orig_path or '[auto-discovery failed]'}")
		return out_df

	print_debug(f"Augmentation: loading original liganden CSV from: {orig_path}")
	orig_df = pd.read_csv(orig_path, engine="python")

	# Determine key column in original
	orig_id_col = None
	for candidate in ["ligandennr", "ligandenID", "ligandenId", "liganden_id", "LigandenID"]:
		if candidate in orig_df.columns:
			orig_id_col = candidate
			break
	if orig_id_col is None:
		print_debug("Original liganden CSV has no recognizable ID column; skipping augmentation")
		return out_df

	# Compute normalized IDs
	orig_df = orig_df.copy()
	orig_df["merge_id"] = orig_df[orig_id_col].apply(_normalize_id)
	cur_ids = set(out_df["merge_id"].dropna().astype(str))
	orig_ids = set(x for x in orig_df["merge_id"].dropna().astype(str))
	missing_ids = sorted(orig_ids - cur_ids)
	if not missing_ids:
		print_debug("Augmentation: no additional IDs found in original file.")
		return out_df

	print_debug(f"Augmentation: appending {len(missing_ids)} missing rows from original file.")
	# Build rows with placeholders for columns not available in original
	cols_out = list(out_df.columns)
	rows = []
	orig_subset = orig_df[orig_df["merge_id"].isin(missing_ids)].copy()
	for _, row in orig_subset.iterrows():
		new_row = {}
		for c in cols_out:
			if c in orig_subset.columns:
				new_row[c] = row[c]
			else:
				# Fill placeholders for non-original columns (e.g., qupkake Q0 fields)
				new_row[c] = placeholder
		# Ensure merge_id is normalized and lig_id_col is preserved if missing
		new_row["merge_id"] = _normalize_id(new_row.get("merge_id", row.get("merge_id")))
		if lig_id_col not in orig_subset.columns:
			# If original lacked the exact lig_id_col name, attempt to backfill from orig_id_col
			new_row[lig_id_col] = row.get(orig_id_col, placeholder)
		rows.append(new_row)

	appended = pd.DataFrame(rows)
	aug_df = pd.concat([out_df, appended], ignore_index=True)

	# Export a small report for the augmented set
	try:
		_ensure_dir(BUILD_DIR)
		rep = BUILD_DIR / f"liganden_missing_from_original_{TIMESTAMP}.csv"
		appended.loc[:, [c for c in [orig_id_col, "merge_id"] if c in appended.columns]].to_csv(rep, index=False)
		print_debug(f"Augmentation report written: {rep}")
	except Exception:
		pass

	return aug_df


def main():
	print("=" * 70)
	print("NIST SRD 46 QupKake pKa Merge Pipeline (pip1c-6)")
	print("=" * 70)
	
	# Ensure build directory exists
	_ensure_dir(BUILD_DIR)
	_ensure_dir(LOG_DIR)
	
	print(f"[CONFIG] LIGANDEN_CSV: {LIGANDEN_CSV}")
	print(f"[CONFIG] QUPKAKE_CSV: {QUPKAKE_CSV}")
	print(f"[CONFIG] OUTPUT_CSV: {OUTPUT_CSV}")
	
	print("\nLoading liganden CSV ...")
	# Use the python engine to be tolerant of embedded newlines in fields like 'molblock'.
	lig_df = pd.read_csv(LIGANDEN_CSV, engine="python")

	# Determine which column to use as the liganden key
	lig_id_col = None
	for candidate in ["ligandennr", "ligandenID", "ligandenId", "liganden_id", "LigandenID"]:
		if candidate in lig_df.columns:
			lig_id_col = candidate
			break
	if lig_id_col is None:
		raise KeyError(
			"Could not find an ID column in liganden CSV. Expected one of: "
			"ligandennr, ligandenID, ligandenId, liganden_id, LigandenID"
		)

	# Normalize liganden IDs
	lig_df["merge_id"] = lig_df[lig_id_col].apply(_normalize_id)

	# Cache columns used for defaults
	col_inchi = "InChI" if "InChI" in lig_df.columns else None
	col_smiles = "SMILES" if "SMILES" in lig_df.columns else None
	col_formula_pref = "formula" if "formula" in lig_df.columns else None
	col_formula_alt = "COMPOSITION" if "COMPOSITION" in lig_df.columns else None

	# Load qupkake if available
	if Path(QUPKAKE_CSV).exists():
		print("Loading qupkake CSV ...")
		qup_df = pd.read_csv(QUPKAKE_CSV, engine="python")

		# Guard: ensure the key exists
		if "ligandennr" not in qup_df.columns:
			raise KeyError("qupkake CSV missing required 'ligandennr' column")

		# Normalize qupkake IDs
		qup_df["merge_id"] = qup_df["ligandennr"].apply(_normalize_id)

		# Build list of qupkake columns to bring (exclude original key to avoid duplication)
		qup_cols = [c for c in qup_df.columns if c not in ("ligandennr", "merge_id")]

		# Left-join
		print("Merging datasets ...")
		merged = lig_df.merge(qup_df[["merge_id", *qup_cols]], on="merge_id", how="left")

		# Ensure the key qupkake columns exist even if qupkake had none (edge case)
		merged = _ensure_columns(
			merged,
			[
				"formula_Q0",
				"bracket_Q0",
				"smiles_Q0",
				"inchi_Q0",
				# Also ensure underscore variants are available for mirroring
				"formula_Q_0",
				"bracket_Q_0",
				"smiles_Q_0",
				"inchi_Q_0",
			],
		)


		# Determine which rows are missing qupkake info (based on inchi_Q0 absent)
		missing_mask = merged["inchi_Q0"].isna()
		missing_count = int(missing_mask.sum())
		total_rows = len(merged)

		# Prepare debug header
		print_debug("\n=== Merge qupkake into liganden_w ===")
		print_debug(f"Timestamp: {TIMESTAMP}")
		print_debug(f"Input liganden: {LIGANDEN_CSV}")
		print_debug(f"Input qupkake : {QUPKAKE_CSV}")
		print_debug(f"Rows: {total_rows}; missing qupkake entries: {missing_count}")

		# Fill defaults only for missing rows
		if missing_count:
			print(f"Filling defaults for {missing_count} / {total_rows} rows with no qupkake match ...")
			# Export a CSV of missing rows for debug/inspection
			_missing_df = merged.loc[missing_mask].copy()
			# Select a useful subset of columns if available
			prefer_name_cols = [c for c in ["name_ligand", "IUPAC_NAME", "COMMON_NAME"] if c in _missing_df.columns]
			prefer_src_cols = [c for c in ["InChI", "SMILES", "formula", "COMPOSITION"] if c in _missing_df.columns]
			prefer_q0_cols  = [c for c in ["formula_Q0", "bracket_Q0", "smiles_Q0", "inchi_Q0"] if c in _missing_df.columns]
			cols_export = [c for c in [lig_id_col, "merge_id", *prefer_name_cols, *prefer_src_cols, *prefer_q0_cols] if c in _missing_df.columns]
			_ensure_dir(BUILD_DIR)
			missing_csv_path = BUILD_DIR / f"liganden_missing_qupkake_{TIMESTAMP}.csv"
			_missing_df.loc[:, cols_export].to_csv(missing_csv_path, index=False)
			print_debug(f"Missing rows exported to: {missing_csv_path}")
			# Show a few examples
			try:
				examples = _missing_df.loc[:, [c for c in [lig_id_col, "merge_id", "InChI", "SMILES"] if c in _missing_df.columns]].head(5)
				print_debug("Examples of missing entries (up to 5):")
				for _, row in examples.iterrows():
					rid = row.get(lig_id_col, None)
					mid = row.get("merge_id", None)
					inchi = row.get("InChI", None)
					smi = row.get("SMILES", None)
					print_debug(f" - ID={rid} merge_id={mid} InChI={inchi} SMILES={smi}")
			except Exception:
				pass
			if col_formula_pref or col_formula_alt:
				# Prefer 'formula' else 'COMPOSITION'
				formula_series = (
					merged[col_formula_pref]
					if col_formula_pref
					else merged[col_formula_alt]
				)
				merged.loc[missing_mask, "formula_Q0"] = formula_series[missing_mask]
			else:
				# Nothing to derive from; leave as NA
				pass

			if col_smiles:
				merged.loc[missing_mask, "smiles_Q0"] = merged[col_smiles][missing_mask]
			if col_inchi:
				merged.loc[missing_mask, "inchi_Q0"] = merged[col_inchi][missing_mask]

			merged.loc[missing_mask, "bracket_Q0"] = "(-inf, +inf)"

			# Mirror defaults into underscore columns specifically for missing rows
			merged.loc[missing_mask, "formula_Q_0"] = merged.loc[missing_mask, "formula_Q0"]
			merged.loc[missing_mask, "bracket_Q_0"] = merged.loc[missing_mask, "bracket_Q0"]
			merged.loc[missing_mask, "smiles_Q_0"] = merged.loc[missing_mask, "smiles_Q0"]
			merged.loc[missing_mask, "inchi_Q_0"] = merged.loc[missing_mask, "inchi_Q0"]

		else:
			print("All rows had qupkake data; no default fills needed.")

		# Drop helper
		# Note: Keep merge_id until after augmentation

		# Augment with original liganden entries that are missing
		aug_src = ORIGINAL_LIGANDEN_CSV if ORIGINAL_LIGANDEN_CSV else None
		merged_aug = _augment_with_original(merged, aug_src, lig_id_col, placeholder="*")

		# Finally drop helper and write
		# Ensure the original liganden ID column is written as normalized string (avoid floats like 5760.0)
		if lig_id_col in merged_aug.columns and "merge_id" in merged_aug.columns:
			merged_aug[lig_id_col] = (
				merged_aug["merge_id"].where(
					merged_aug["merge_id"].notna(),
					merged_aug[lig_id_col].apply(_normalize_id),
				)
				.astype("string")
			)

		# Finally drop helper and write
		if "merge_id" in merged_aug.columns:
			merged_aug = merged_aug.drop(columns=["merge_id"])  # safe if present

		# Save
		print(f"Writing merged CSV to: {OUTPUT_CSV}")
		merged_aug.to_csv(OUTPUT_CSV, index=False)

		# Summary
		matched_count = total_rows - missing_count
		msg = f"Done. Rows: {total_rows}. Matched: {matched_count}. Defaults filled: {missing_count}."
		print(msg)
		print_debug(msg)
	else:
		print(
			f"WARNING: qupkake CSV not found at {QUPKAKE_CSV}. Will create default Q0 columns for all rows."
		)
		print_debug("\n=== Merge qupkake into liganden_w ===")
		print_debug(f"Timestamp: {TIMESTAMP}")
		print_debug(f"Input liganden: {LIGANDEN_CSV}")
		print_debug(f"Input qupkake : {QUPKAKE_CSV} [NOT FOUND]")

		# Create empty columns for Q0 and fill defaults for all rows
		lig_df = _ensure_columns(
			lig_df,
			[
				"formula_Q0",
				"bracket_Q0",
				"smiles_Q0",
				"inchi_Q0",
				# Also ensure underscore variants exist so we can mirror to them
				"formula_Q_0",
				"bracket_Q_0",
				"smiles_Q_0",
				"inchi_Q_0",
			],
		)

		# Fill from liganden columns
		if col_formula_pref or col_formula_alt:
			formula_series = lig_df[col_formula_pref] if col_formula_pref else lig_df[col_formula_alt]
			lig_df["formula_Q0"] = formula_series
		if col_smiles:
			lig_df["smiles_Q0"] = lig_df[col_smiles]
		if col_inchi:
			lig_df["inchi_Q0"] = lig_df[col_inchi]
		lig_df["bracket_Q0"] = "(-inf, +inf)"

		# Mirror defaults to underscore columns for all rows (since all defaulted)
		lig_df["formula_Q_0"] = lig_df["formula_Q0"]
		lig_df["bracket_Q_0"] = lig_df["bracket_Q0"]
		lig_df["smiles_Q_0"] = lig_df["smiles_Q0"]
		lig_df["inchi_Q_0"] = lig_df["inchi_Q0"]

		# Note: Keep merge_id until after augmentation

		# Export 'all missing' CSV for debug
		_ensure_dir(BUILD_DIR)
		missing_csv_path = BUILD_DIR / f"liganden_missing_qupkake_{TIMESTAMP}_ALL.csv"
		lig_df.to_csv(missing_csv_path, index=False)
		print_debug(f"All rows defaulted; exported to: {missing_csv_path}")

		# Augment with original liganden entries that are missing
		aug_src = ORIGINAL_LIGANDEN_CSV if ORIGINAL_LIGANDEN_CSV else None
		lig_df_aug = _augment_with_original(lig_df, aug_src, lig_id_col, placeholder="*")

		# Finally drop helper and write
		# Ensure the original liganden ID column is written as normalized string (avoid floats like 5760.0)
		if lig_id_col in lig_df_aug.columns and "merge_id" in lig_df_aug.columns:
			lig_df_aug[lig_id_col] = (
				lig_df_aug["merge_id"].where(
					lig_df_aug["merge_id"].notna(),
					lig_df_aug[lig_id_col].apply(_normalize_id),
				)
				.astype("string")
			)

		# Finally drop helper and write
		if "merge_id" in lig_df_aug.columns:
			lig_df_aug = lig_df_aug.drop(columns=["merge_id"])  # safe if present

		print(f"Writing CSV to: {OUTPUT_CSV}")
		lig_df_aug.to_csv(OUTPUT_CSV, index=False)
		msg = f"Done. Rows: {len(lig_df_aug)}. All rows received default Q0 values (qupkake missing); augmented with original where needed."
		print(msg)
		print_debug(msg)


if __name__ == "__main__":
	main()

