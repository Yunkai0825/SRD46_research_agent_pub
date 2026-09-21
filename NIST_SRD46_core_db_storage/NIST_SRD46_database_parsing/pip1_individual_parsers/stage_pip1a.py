"""Stage pip1a: beta_definition parsing (equations, trees, species library, codified manual fixes).

Manual rules applied / ledgered here (all declared in ``srd46_pipeline/manual_rules.py``):

* BETA-02  raw-text repairs, applied by the parser through the ``MANUAL_NAME_FIXES`` shim
           (guarded by the exact raw string), plus the orphan beta rows filled from the sic table
           into the in-memory input BEFORE parsing (ledger status ``row_filled``);
* BETA-03  equation-side corrections after parsing (``MANUAL_CORRECTIONS`` shim);
* BETA-04  polymetal HOL tokens consumed by the tokenizer (one ledger row per beta id x token);
* BETA-01  register check: the set of beta ids the parser leaves unparsed must equal the declared
           register and the verkn -> beta orphan references must equal the declared list (filled
           orphans are ledgered ``orphan_ref_filled``). Deviations are ledgered and logged as WARNING.
"""
from __future__ import annotations

import csv
import io
from typing import Any, Dict, List, Set, Tuple

import pandas as pd

from srd46_pipeline import manual_rules as mr
from srd46_pipeline.legacy import load_script
from srd46_pipeline.paths import LEGACY_SCRIPTS, PIP1A_DIR
from srd46_pipeline.runner import Context
from srd46_pipeline.sources import read_source_table, source_csv

STAGE = "pip1a_beta_definition"


def _csv_with_orphan_rows(src: io.StringIO) -> Tuple[io.StringIO, List[Dict[str, Any]]]:
    """BETA-02: append declared orphan rows to the dump-derived input in memory."""
    records = list(csv.reader(src))
    columns, rows = records[0], records[1:]
    n_cols = len(columns)
    present: Set[int] = {int(row[0]) for row in rows if row and row[0].strip().isdigit()}
    tail_start = len(rows)
    while tail_start and not any(rows[tail_start - 1]):
        tail_start -= 1
    entries: List[Dict[str, Any]] = []
    new_rows: List[List[str]] = []
    src_id = mr.ledger_source("BETA-02", "orphan_row")
    for bid, fill in mr.BETA_ORPHAN_ROW_FILLS.items():
        reason = f"{fill.notes}; sic table: {fill.sic}; evidence: {fill.evidence}"
        if bid in present:
            entries.append({"table_name": "beta_definition", "record_id": bid, "field": "name_beta_definition",
                            "old_value": None, "new_value": fill.name,
                            "reason": f"row now present in the dump, fill not needed; {reason}",
                            "source": src_id, "status": "stale"})
            continue
        new_rows.append([str(bid), fill.name, mr.CANONICAL_NULL_TOKEN, mr.CANONICAL_NULL_TOKEN]
                        + [""] * (n_cols - 4))
        entries.append({"table_name": "beta_definition", "record_id": bid, "field": "name_beta_definition",
                        "old_value": None, "new_value": fill.name, "reason": reason,
                        "source": src_id, "status": "row_filled"})
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows([columns, *rows[:tail_start], *new_rows, *rows[tail_start:]])
    buf.seek(0)
    return buf, entries


def _beta02_entries(by_id: Dict[int, Dict[str, Any]]) -> List[Dict[str, Any]]:
    src = mr.ledger_source("BETA-02")
    out: List[Dict[str, Any]] = []
    for bid, fix in mr.BETA_NAME_FIXES.items():
        row = by_id.get(int(bid))
        if row is None:
            status = "missing"
        elif bool(row.get("manual_name_fix")):
            status = "applied"
        else:
            status = "stale" if "STALE" in str(row.get("manual_name_fix_note", "")) else "not_applied"
        reason = fix.notes + (f"; evidence: {fix.evidence}" if fix.evidence else "")
        out.append({"table_name": "beta_definition", "record_id": bid, "field": "name_beta_definition",
                    "old_value": fix.raw, "new_value": fix.fixed, "reason": reason, "source": src, "status": status})
    return out


def _beta03_entries(by_id: Dict[int, Dict[str, Any]]) -> List[Dict[str, Any]]:
    src = mr.ledger_source("BETA-03")
    out: List[Dict[str, Any]] = []
    for bid, corr in mr.BETA_EQUATION_CORRECTIONS.items():
        row = by_id.get(int(bid))
        if row is None:
            status = "missing"
        elif not bool(row.get("manual_correction")):
            status = "not_applied"
        elif str(row.get("element_conserved_final")) == "True":
            status = "applied"
        else:
            status = "applied_unbalanced"
        out.append({"table_name": "beta_definition", "record_id": bid, "field": "equation_sides",
                    "old_value": None if row is None else row.get("name_beta_definition"),
                    "new_value": corr.equation, "reason": f"[{corr.verdict}] {corr.notes}",
                    "source": src, "status": status})
    return out


def _beta04_entries(by_id: Dict[int, Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """One row per (beta id, polymetal token) the tokenizer resolved; unused tokens are ledgered once."""
    from pip1a_helpers.constants import POLYMETAL_TOKEN_PATTERN  # noqa: WPS433  (path inserted by load_script)
    src = mr.ledger_source("BETA-04")
    canonical = {k.lower(): k for k in mr.BETA_POLYMETAL_HOL_TOKENS}
    out: List[Dict[str, Any]] = []
    used: Set[str] = set()
    for bid in sorted(by_id):
        row = by_id[bid]
        eq = str(row.get("equation_python") or "")
        if eq in ("", "*", "None", "nan"):
            continue
        tokens = sorted({canonical[m.group(1).lower()] for m in POLYMETAL_TOKEN_PATTERN.finditer(eq)
                         if m.group(1).lower() in canonical})
        for tok in tokens:
            used.add(tok)
            out.append({"table_name": "beta_definition", "record_id": bid, "field": "equation_python",
                        "old_value": tok, "new_value": str(mr.BETA_POLYMETAL_HOL_TOKENS[tok]),
                        "reason": "polymetal token expanded to H/O/L(/M) counts by the tokenizer",
                        "source": src, "status": "token_used"})
    for tok in mr.BETA_POLYMETAL_HOL_TOKENS:
        if tok not in used:
            out.append({"table_name": "beta_definition", "record_id": None, "field": "equation_python",
                        "old_value": tok, "new_value": str(mr.BETA_POLYMETAL_HOL_TOKENS[tok]),
                        "reason": "token declared in BETA-04 but matched by no parsed equation of this dump",
                        "source": src, "status": "token_unused"})
    return out, len(used)


def _beta01_register_check(ctx: Context, aug: pd.DataFrame, filled: Set[int]) -> Dict[str, Any]:
    """BETA-01: compare actual unparsed ids / orphan references with the declared register."""
    st = ctx.staging
    ids = pd.to_numeric(aug["beta_definitionID"], errors="coerce")
    eq = aug["equation_python"].astype(str).str.strip() if "equation_python" in aug.columns else pd.Series("", index=aug.index)
    unparsed: Set[int] = {int(i) for i, e in zip(ids, eq) if pd.notna(i) and e in ("*", "", "None", "nan")}
    declared: Set[int] = {bid for _, (_, bids) in mr.BETA_KNOWN_UNPARSEABLE.items() for bid in bids}
    src = mr.ledger_source("BETA-01")
    entries: List[Dict[str, Any]] = []
    unexpected = sorted(unparsed - declared)
    stale = sorted(declared - unparsed)
    for bid in sorted(unparsed):
        cat = mr.beta_known_category(bid)
        reason = mr.BETA_KNOWN_UNPARSEABLE[cat][0] if cat else "NOT in the known-unparseable register"
        if cat and bid in mr.BETA_UNRESOLVED_CANDIDATES:
            reason = f"{reason}; considered: {mr.BETA_UNRESOLVED_CANDIDATES[bid]}"
        entries.append({"table_name": "beta_definition", "record_id": bid, "field": "equation_python",
                        "old_value": None, "new_value": None, "reason": f"{cat or 'unexpected'}: {reason}",
                        "source": src, "status": "known_unparseable" if cat else "unexpected_unparseable"})
    for bid in stale:
        entries.append({"table_name": "beta_definition", "record_id": bid, "field": "equation_python",
                        "old_value": None, "new_value": None,
                        "reason": "listed as known-unparseable but the parser now succeeds (register stale)",
                        "source": src, "status": "register_stale"})

    # orphan references: beta ids used by verkn_ligand_metal that have no beta_definition row in the DUMP
    # (rows filled by BETA-02 are excluded from the parsed id set so the fact stays visible)
    beta_ids = {int(i) for i in ids if pd.notna(i)} - filled
    if st.table_exists("verkn_ligand_metal_canonical"):
        vlm_beta = st.read_df("verkn_ligand_metal_canonical")["beta_definitionNr"]
    else:   # raw_canonical not run in this invocation: read the dump directly (never the Excel-derived CSV)
        _, vlm_rows = read_source_table("verkn_ligand_metal")
        vlm_beta = pd.Series([r["beta_definitionNr"] for r in vlm_rows], dtype=str)
    vlm_beta = pd.to_numeric(vlm_beta, errors="coerce").dropna().astype(int)
    orphan_counts = vlm_beta[~vlm_beta.isin(beta_ids)].value_counts().to_dict()
    orphans = set(orphan_counts)
    declared_orphans = set(mr.BETA_ORPHAN_VERKN_REFS)
    for bid in sorted(orphans | declared_orphans):
        if bid in orphans and bid in declared_orphans:
            status = "orphan_ref_filled" if bid in filled else "known_orphan_ref"
            reason = mr.BETA_ORPHAN_VERKN_REFS[bid] + ("; row filled from the sic table (BETA-02)" if bid in filled else "")
        elif bid in orphans:
            status, reason = "unexpected_orphan_ref", f"{orphan_counts[bid]} verkn rows reference beta {bid}; not in register"
        else:
            status, reason = "register_stale", f"declared orphan reference {bid} no longer occurs"
        entries.append({"table_name": "beta_definition", "record_id": bid, "field": "beta_definitionNr (verkn_ligand_metal)",
                        "old_value": None, "new_value": str(orphan_counts.get(bid, 0)), "reason": reason,
                        "source": src, "status": status})
    n_logged = st.log_manual_fixes(STAGE, entries)
    unexpected_orphans = sorted(orphans - declared_orphans)
    stale_orphans = sorted(declared_orphans - orphans)
    unfilled = sorted((orphans & declared_orphans) - filled)
    if unexpected or stale or unexpected_orphans or stale_orphans:
        ctx.log(f"pip1a: WARNING BETA-01 register mismatch: unexpected_unparseable={unexpected} register_stale={stale} "
                f"unexpected_orphan_refs={unexpected_orphans} stale_orphan_refs={stale_orphans}")
    else:
        ctx.log(f"pip1a: BETA-01 register matches ({len(unparsed)} known-unparseable ids, {len(orphans)} orphan refs, "
                f"{len(orphans & filled)} filled by BETA-02, {len(unfilled)} left unfilled)")
    return {"beta01_unparsed": len(unparsed), "beta01_unexpected_unparseable": len(unexpected),
            "beta01_register_stale": len(stale) + len(stale_orphans), "beta01_orphan_refs": len(orphans),
            "beta01_orphan_refs_filled": len(orphans & filled),
            "beta01_unexpected_orphan_refs": len(unexpected_orphans), "beta01_ledger_rows": n_logged}


def run(ctx: Context) -> Dict[str, Any]:
    mod = load_script(LEGACY_SCRIPTS["pip1a"], "srd46_legacy_pip1a", [PIP1A_DIR])
    mod.VERBOSE_FLAG = ctx.options.verbose
    mod.EXPORT_FLAG = False
    import pip1a_helpers  # noqa: WPS433  (path inserted by load_script)
    from pip1a_helpers import build_augmented_dataframe, COLUMN_METADATA
    from pip1a_helpers.manual_correction_helpers import MANUAL_CORRECTIONS, MANUAL_NAME_FIXES
    if hasattr(pip1a_helpers, "set_verbose"):
        pip1a_helpers.set_verbose(ctx.options.verbose)
    # the parser-side shims must serve the register, not a private copy
    assert set(MANUAL_NAME_FIXES) == set(mr.BETA_NAME_FIXES), "pip1a: MANUAL_NAME_FIXES shim out of sync with BETA-02"
    assert set(MANUAL_CORRECTIONS) == set(mr.BETA_EQUATION_CORRECTIONS), "pip1a: MANUAL_CORRECTIONS shim out of sync with BETA-03"

    src = source_csv("beta_definition")
    buf, orphan_entries = _csv_with_orphan_rows(src)
    filled = {int(e["record_id"]) for e in orphan_entries if e["status"] == "row_filled"}
    ctx.log(f"pip1a: parsing {src.name} (+{len(filled)} orphan rows filled by BETA-02: {sorted(filled)})")
    df, species_lib = mod.run_full_beta_pipeline(buf)
    aug = build_augmented_dataframe(df, prefix="beta_eq", mark_unsuccessful_with_star=True)

    st = ctx.staging
    st.write_df("beta_definition_augmented", aug, STAGE)
    st.write_df("beta_definition_full", df, STAGE)
    if species_lib is not None:
        st.write_df("species_library", species_lib.to_dataframe(), STAGE)
    st.put_json("pip1a_column_meta", dict(COLUMN_METADATA), STAGE)
    st.put_json("pip1a_beta_definition_column_meta", mod.build_beta_definition_column_meta("beta_eq"), STAGE)

    # --- manual fixes: every codified fix becomes a visible ledger row -----------------------
    ids = pd.to_numeric(aug["beta_definitionID"], errors="coerce")
    by_id = {int(i): r for i, r in zip(ids, aug.to_dict("records")) if pd.notna(i)}
    for bid in filled:   # a filled row that did not parse is a defect of the fill, not a data fact
        row = by_id.get(bid)
        ok = row is not None and str(row.get("equation_python", "*")).strip() not in ("*", "", "None", "nan")
        if not ok:
            ctx.log(f"pip1a: WARNING BETA-02 orphan row {bid} was filled but did not parse")
    beta04_entries, n_tokens_used = _beta04_entries(by_id)
    n_logged = st.log_manual_fixes(STAGE, orphan_entries + _beta02_entries(by_id) + _beta03_entries(by_id) + beta04_entries)
    beta01 = _beta01_register_check(ctx, aug, filled)

    n_name_fix = int(aug["manual_name_fix"].astype(bool).sum()) if "manual_name_fix" in aug.columns else 0
    n_corr = int(aug["manual_correction"].astype(bool).sum()) if "manual_correction" in aug.columns else 0
    conserved = int(aug["element_conserved_final"].astype(str).eq("True").sum()) if "element_conserved_final" in aug.columns else None
    return {"rows": len(aug), "columns": aug.shape[1], "orphan_rows_filled": len(filled),
            "manual_name_fixes_applied": n_name_fix, "manual_corrections_applied": n_corr,
            "polymetal_tokens_used": n_tokens_used, "manual_fix_ledger_rows": n_logged,
            "element_conserved_final": conserved,
            "species": species_lib.unique_count if species_lib is not None else None, **beta01}
