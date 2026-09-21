"""
Stage pip1c: liganden / mol_data enrichment chain (six sub-stages).

1c_1 molfile decode      -> mol_data_with_molblock
1c_2 SMILES/InChI        -> mol_data_enriched            (PubChem name recovery, cached)
1c_3 HxL parse           -> liganden_moldata_HxL_parsed
1c_4 chemical names      -> mol_data_with_names          (PubChem SMILES->names, cached)
1c_5b Qupkake SDF parse  -> qupkake_pka_liganden         (existing results only, or off)
1c_6 Qupkake merge       -> liganden_w_moldata_qupkake_parsed  (pip1c hand-off, 140 columns)

All PubChem traffic goes through ``PubChemAccess`` which fronts the staging caches
(seeded from the archived results of the original network runs) so a rebuild is
reproducible offline (``--pubchem cache-only``).

Manual rules applied in this chain (declared in ``srd46_pipeline/manual_rules.py``):
LIG-01a/b/c name variants for the PubChem molblock recovery (1c_2), HXL-01..04 data-driven
charge-reconciliation rules consumed by pip3_hxl and ledgered per row (1c_3), LIG-02 name-based
IUPAC/common-name fallback (1c_4), QUP-01 Qupkake archive fill (1c_5b).
"""
from __future__ import annotations

import csv
import json
import os
import re
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd

from srd46_pipeline import manual_rules as mr
from srd46_pipeline.legacy import ensure_sys_path, load_script
from srd46_pipeline.paths import (LEGACY_SCRIPTS, PIP1C_3_DIR, PUBCHEM_SEEDS, QUPKAKE_PARSED_CSV_CANDIDATES,
                    QUPKAKE_INPUT_DB_DEFAULT, QUPKAKE_SDF_DIR_DEFAULT)
from srd46_pipeline.runner import Context, PipelineError
from srd46_pipeline.sources import read_source_table, source_csv
from srd46_pipeline.staging import df_csv_roundtrip, df_to_rows, rows_to_df

S1, S2, S3, S4, S5B, S6 = ("pip1c_1_molfile_decode", "pip1c_2_smiles_inchi", "pip1c_3_hxl_parse",
                           "pip1c_4_chemical_names", "pip1c_5b_qupkake_parse", "pip1c_6_qupkake_merge")

_RE_NAME_FAILED = re.compile(r"name lookup failed \(name='(.*)'\)$")


def _json_safe_records(records: List[Dict[str, Any]]) -> pd.DataFrame:
    """Rows whose values may be lists/dicts -> DataFrame with those cells JSON-encoded."""
    out = []
    for r in records:
        out.append({k: (json.dumps(v, default=str, ensure_ascii=False) if isinstance(v, (list, dict, tuple, set))
                        else v) for k, v in r.items()})
    return pd.DataFrame(out)


# =============================================================================
# PubChem cache front
# =============================================================================
_RE_HTTP_DEFINITIVE = re.compile(r"HTTP (400|404)\b")
NETWORK_SOURCE = "network:post"     # entries produced by the fixed (POST form-data) request path


def _stereo_smiles(smiles: str) -> bool:
    return "/" in smiles or "\\" in smiles


def _definitive_failure(error: str) -> bool:
    """HTTP 400 (PubChem cannot parse the structure) / 404 (unknown) are properties of the
    query itself and may be cached; timeouts, connection errors, 429 and 5xx are not."""
    return bool(_RE_HTTP_DEFINITIVE.search(error or ""))


def _request_bug_failure(smiles: str, error: str) -> bool:
    """The original GET request put the SMILES in the URL path; PubChem un-escapes %2F, so every stereo
    SMILES answered HTTP 400. Those 'failures' are artefacts of the request, not of the data."""
    return "HTTP 400" in (error or "") and _stereo_smiles(smiles)


class PubChemAccess:
    def __init__(self, ctx: Context):
        self.ctx = ctx
        self.st = ctx.staging
        self.mode = ctx.options.pubchem_mode
        self.stats: Dict[str, int] = {"cache_hits": 0, "cache_misses": 0, "network_calls": 0, "network_failures": 0}
        self._pending = 0

    def _tick(self) -> None:
        self._pending += 1
        if self._pending >= 25:
            self.st.commit()
            self._pending = 0

    def seed(self) -> Dict[str, Any]:
        """Load archived PubChem answers into the caches (INSERT OR IGNORE; idempotent)."""
        st, info = self.st, {}
        p = PUBCHEM_SEEDS["fixed_by_name"]
        if p.exists():
            n = 0
            with p.open(newline="", encoding="utf-8-sig") as f:
                for r in csv.DictReader(f):
                    name = (r.get("RECOVERY_NAME") or "").strip()
                    mb = r.get("molblock") or ""
                    if name and mb:
                        cid = (r.get("RECOVERY_CID") or "").strip() or None
                        st.name_cache_put(name, "ok", cid, mb, f"seed:{p.name}", overwrite=False)
                        n += 1
            info["name_ok_from_fixed_by_name"] = n
        p = PUBCHEM_SEEDS["mol_data_enriched"]
        if p.exists():
            n = 0
            with p.open(newline="", encoding="utf-8-sig") as f:
                for r in csv.DictReader(f):
                    m = _RE_NAME_FAILED.search(r.get("ERROR_RECOVERY") or "")
                    if m and m.group(1).strip():
                        st.name_cache_put(m.group(1).strip(), "miss", None, None, f"seed:{p.name}", overwrite=False)
                        n += 1
            info["name_miss_from_mol_data_enriched"] = n
        failed_smiles = set()
        p = PUBCHEM_SEEDS["failed_names"]
        if p.exists():
            n = 0
            with p.open(newline="", encoding="utf-8-sig") as f:
                for r in csv.DictReader(f):
                    smiles = r.get("SMILES") or ""
                    err = r.get("ERROR_NAMES") or ""
                    if not smiles or smiles == "*":
                        continue
                    failed_smiles.add(smiles)
                    # only failures that are properties of the SMILES itself are worth caching;
                    # request-bug (stereo SMILES in URL path) and transient errors get retried
                    if _definitive_failure(err) and not _request_bug_failure(smiles, err):
                        st.smiles_cache_put(smiles, "fail", None, None, err, f"seed:{p.name}", overwrite=False)
                        n += 1
            info["smiles_fail_from_failed_names"] = n
        # purge poisoned rows written by earlier runs (buggy GET path / transient errors cached)
        cur = st.conn.execute(
            "DELETE FROM pubchem_smiles_names_cache WHERE status='fail' AND source != ? AND "
            "((error LIKE '%HTTP 400%' AND (smiles LIKE '%/%' OR smiles LIKE ?)) "
            " OR (error NOT LIKE '%HTTP 400%' AND error NOT LIKE '%HTTP 404%'))",
            (NETWORK_SOURCE, "%\\%"))   # second parameter = '%\%' (single backslash)
        info["smiles_fail_purged_retryable"] = cur.rowcount
        p = PUBCHEM_SEEDS["mol_data_with_names"]
        if p.exists():
            n = 0
            with p.open(newline="", encoding="utf-8-sig") as f:
                for r in csv.DictReader(f):
                    smiles = r.get("SMILES") or ""
                    if smiles in ("", "*") or smiles in failed_smiles:
                        continue
                    st.smiles_cache_put(smiles, "ok", r.get("IUPAC_NAME") or "", r.get("COMMON_NAME") or "",
                                        None, f"seed:{p.name}", overwrite=False)
                    n += 1
            info["smiles_ok_from_mol_data_with_names"] = n
        info["missing_seed_files"] = [str(q) for q in PUBCHEM_SEEDS.values() if not q.exists()]
        st.commit()
        info["cache_counts"] = st.cache_counts()
        self.st.put_json("pubchem_seed_info", info, "pubchem")
        return info

    # -- pip1c_2: compound-by-name -> {"CID", "InChI", "SMILES", "molblock"} | None ------------
    def name_lookup(self, real: Callable[[str], Optional[Dict]]) -> Callable[[str], Optional[Dict]]:
        def lookup(name: str) -> Optional[Dict]:
            key = (name or "").strip()
            if not key:
                return None
            if self.mode != "network":
                hit = self.st.name_cache_get(key)
                if hit is not None:
                    self.stats["cache_hits"] += 1
                    if hit["status"] == "ok" and hit["molblock"]:
                        return {"CID": hit["cid"] or "", "InChI": "", "SMILES": "", "molblock": hit["molblock"]}
                    return None
                self.stats["cache_misses"] += 1
                if self.mode == "cache-only":
                    return None
            self.stats["network_calls"] += 1
            try:
                res = real(name)
            except Exception as exc:      # transient (timeout / HTTP 5xx): not cached, retried next run
                self.stats["network_failures"] += 1
                self.ctx.log(f"pip1c: PubChem transient failure (not cached): {exc}")
                return None
            if res and res.get("molblock"):
                self.st.name_cache_put(key, "ok", str(res.get("CID", "")), res["molblock"], NETWORK_SOURCE)
            else:                          # HTTP 404 / no CID -> definitive miss
                self.st.name_cache_put(key, "miss", None, None, NETWORK_SOURCE)
            self._tick()
            return res
        return lookup

    # -- pip1c_4: SMILES -> (iupac, title); raises RuntimeError on failure ---------------------
    def smiles_lookup(self, real: Callable[[str], Tuple[str, str]]) -> Callable[[str], Tuple[str, str]]:
        def lookup(smiles: str) -> Tuple[str, str]:
            if self.mode != "network":
                hit = self.st.smiles_cache_get(smiles)
                if hit is not None:
                    self.stats["cache_hits"] += 1
                    if hit["status"] == "ok":
                        return hit["iupac"] or "", hit["title"] or ""
                    raise RuntimeError(hit["error"] or "PubChem query failed: cached failure")
                self.stats["cache_misses"] += 1
                if self.mode == "cache-only":
                    raise RuntimeError("PubChem query skipped: cache miss (--pubchem cache-only)")
            self.stats["network_calls"] += 1
            try:
                iupac, title = real(smiles)
            except Exception as exc:
                self.stats["network_failures"] += 1
                if _definitive_failure(str(exc)):   # 400/404: property of this SMILES -> cache
                    self.st.smiles_cache_put(smiles, "fail", None, None, str(exc), NETWORK_SOURCE)
                    self._tick()
                else:                                # timeout / 5xx / 429: retried next run
                    self.ctx.log(f"pip1c: PubChem transient failure (not cached): {exc}")
                raise
            self.st.smiles_cache_put(smiles, "ok", iupac, title, None, NETWORK_SOURCE)
            self._tick()
            return iupac, title
        return lookup


# =============================================================================
# 1c_1  molfile decode
# =============================================================================
def run_pip1c_1(ctx: Context) -> Dict[str, Any]:
    mod = load_script(LEGACY_SCRIPTS["pip1c_1"], "srd46_legacy_pip1c_1")
    mod.VERBOSE_RUN = ctx.options.verbose
    ctx.log("pip1c_1: decoding molfiles from the mol_data SQL dump")
    fieldnames, rows = read_source_table("mol_data")
    for col in ("mol_string_encoded", "ligandenNR"):
        if col not in fieldnames:
            raise PipelineError(f"mol_data SQL dump: column '{col}' not found")

    seen: Dict[str, str] = {}
    out_rows: List[Dict[str, str]] = []
    dup_rows: List[Dict[str, str]] = []
    n_ok = n_fail = 0
    failed_ids: List[str] = []
    for idx, row in enumerate(rows, start=1):
        lig = row.get("ligandenNR", "") or ""
        mid = row.get("mol_dataID", f"row_{idx}")
        if lig and lig in seen:
            try:
                row["molblock"] = mod.decode_mol_string(row["mol_string_encoded"])
            except Exception:
                row["molblock"] = ""
            row["duplicate_reason"] = f"Duplicate of ligandenNR={lig}, first mol_dataID={seen[lig]}"
            dup_rows.append(row)
            continue
        if lig:
            seen[lig] = mid
        try:
            row["molblock"] = mod.decode_mol_string(row["mol_string_encoded"])
            n_ok += 1
        except Exception as exc:
            mod.log(f"WARNING: row {idx} (id={mid}) failed to decode: {exc}")
            row["molblock"] = ""
            n_fail += 1
            failed_ids.append(str(mid))
        out_rows.append(row)

    st = ctx.staging
    st.write_rows("mol_data_with_molblock", out_rows, S1, fieldnames + ["molblock"])
    st.write_rows("mol_data_duplicates", dup_rows, S1, fieldnames + ["molblock", "duplicate_reason"])
    stats = {"input_rows": len(rows), "output_rows": len(out_rows), "decoded_ok": n_ok, "decode_failed": n_fail,
             "failed_mol_dataIDs": failed_ids, "duplicates_removed": len(dup_rows)}
    st.put_json("pip1c1_stats", stats, S1)
    return {k: v for k, v in stats.items() if k != "failed_mol_dataIDs"}


# =============================================================================
# 1c_2  SMILES / InChI / formula (+ PubChem molblock recovery by name)
# =============================================================================
def _load_liganden_names() -> Tuple[Dict[str, str], List[Dict[str, str]]]:
    """Build the legacy name lookup directly from original dump rows."""
    _, rows = read_source_table("liganden")
    all_rows = [row for row in rows if row.get("ligandenID", "").strip()]
    lookup = {row["ligandenID"].strip(): row["name_ligand"].strip()
              for row in all_rows if row.get("name_ligand", "").strip()}
    return lookup, all_rows


def run_pip1c_2(ctx: Context) -> Dict[str, Any]:
    st = ctx.staging
    st.require_table("mol_data_with_molblock", S1)
    mod = load_script(LEGACY_SCRIPTS["pip1c_2"], "srd46_legacy_pip1c_2")
    mod.VERBOSE = ctx.options.verbose
    access = PubChemAccess(ctx)
    seed_info = access.seed()
    ctx.log(f"pip1c_2: PubChem mode={access.mode}; cache={seed_info['cache_counts']}")
    cached_lookup = access.name_lookup(mod.pubchem_get_compound_by_name)

    # LIG-01: exact name first (cached), then the declared name variants (each cached too).
    # A variant hit must pass the structure guard (single fragment); rejects are ledgered.
    variant_hits: Dict[str, Tuple[str, str, str]] = {}      # original name -> (variant, rule id, CID)
    variant_rejects: List[Dict[str, Any]] = []
    pinned_hits: Dict[str, Tuple[str, str, str]] = {}       # original name -> (lookup name, CID, desalt note)

    def lookup_pinned(name: str) -> Optional[Dict]:
        """LIG-01d: pinned lookup name, CID and parent formula asserted; salts desalted."""
        pin = mr.LIG01_PINNED_LOOKUPS.get(name)
        if pin is None:
            return None
        res = cached_lookup(pin.lookup_name)
        reject = None
        if not (res and res.get("molblock")):
            reject = f"pinned lookup name {pin.lookup_name!r} returned nothing"
        elif str(res.get("CID", "")) != str(pin.cid):
            reject = f"pinned lookup returned CID {res.get('CID')} != pinned CID {pin.cid}"
        else:
            parent, note = mr.desalt_to_parent(res["molblock"], pin.parent_formula)
            if parent is None:
                reject = note
            else:
                pinned_hits[name] = (pin.lookup_name, str(pin.cid), note)
                return {**res, "molblock": parent}
        variant_rejects.append({"table_name": "mol_data_enriched", "record_id": pin.ligand_id, "field": "molblock",
                                "old_value": name, "new_value": f"{pin.lookup_name} (CID {pin.cid})",
                                "reason": f"pinned lookup rejected: {reject}", "source": mr.ledger_source("LIG-01d"),
                                "status": "rejected"})
        return None

    def lookup_with_variants(name: str) -> Optional[Dict]:
        res = cached_lookup(name)
        if res and res.get("molblock"):
            return res
        for variant, rule_id in mr.ligand_name_variants(name):
            res = cached_lookup(variant)
            if not (res and res.get("molblock")):
                continue
            ok, why = mr.ligand_variant_structure_ok(res["molblock"])
            if ok:
                variant_hits[(name or "").strip()] = (variant, rule_id, str(res.get("CID", "")))
                return res
            variant_rejects.append({"table_name": "mol_data_enriched", "record_id": None, "field": "molblock",
                                    "old_value": (name or "").strip(), "new_value": f"{variant} (CID {res.get('CID', '')})",
                                    "reason": f"variant hit rejected by structure guard: {why}",
                                    "source": mr.ledger_source(rule_id), "status": "rejected"})
        return lookup_pinned((name or "").strip())
    mod.pubchem_get_compound_by_name = lookup_with_variants

    fieldnames, rows = st.read_rows("mol_data_with_molblock")
    lookup, all_lig_rows = _load_liganden_names()
    ctx.log(f"pip1c_2: {len(rows)} mol_data rows, {len(all_lig_rows)} liganden rows ({len(lookup)} named)")
    # the pinned / stereo registers are keyed by exact SRD46 name resp. id: assert they still match the table
    name_to_ids: Dict[str, List[str]] = {}
    for lig_id, lig_name in lookup.items():
        name_to_ids.setdefault((lig_name or "").strip(), []).append(str(lig_id))
    for name, pin in mr.LIG01_PINNED_LOOKUPS.items():
        if name_to_ids.get(name) != [pin.ligand_id]:
            raise PipelineError(f"LIG-01d: pinned name {name!r} maps to ligand ids {name_to_ids.get(name)}, expected [{pin.ligand_id}]")
    for lig_id, entry in mr.LIG03_STEREO_STRUCTURES.items():
        if (lookup.get(lig_id) or "").strip() != entry.name:
            raise PipelineError(f"LIG-03: ligand {lig_id} is named {lookup.get(lig_id)!r} in SRD46, register says {entry.name!r}")
    valid, fixed, failed = mod.recover_molblock_from_name(rows, all_lig_rows, lookup)
    current = valid + failed
    for col in ["RECOVERY_SOURCE", "RECOVERY_CID", "RECOVERY_NAME", "ORPHAN_LIGANDEN", "ERROR_RECOVERY"]:
        if col not in fieldnames:
            fieldnames.append(col)

    # LIG-01 bookkeeping: the recovery worker wrote the ORIGINAL name; record the variant that hit.
    # ``fixed`` holds copies of the recovered rows (the originals live in ``valid``): patch both,
    # log once per recovered row.
    lig01_entries: List[Dict[str, Any]] = []
    for group, log_it in ((fixed, True), (valid, False)):
        for row in group:
            original = (row.get("RECOVERY_NAME") or "").strip()
            if row.get("RECOVERY_SOURCE") != "PubChem":
                continue
            if original in pinned_hits:
                lookup_name, cid, note = pinned_hits[original]
                row["RECOVERY_NAME"] = lookup_name
                row["RECOVERY_SOURCE"] = mr.ligand_pinned_source()
                if log_it:
                    lig01_entries.append({"table_name": "mol_data_enriched", "record_id": row.get("ligandenNR"),
                                          "field": "molblock", "old_value": original, "new_value": f"{lookup_name} (CID {cid}; {note})",
                                          "reason": mr.LIG01_PINNED_LOOKUPS[original].why,
                                          "source": mr.ledger_source("LIG-01d"), "status": "applied"})
                continue
            if original not in variant_hits:
                continue
            variant, rule_id, cid = variant_hits[original]
            row["RECOVERY_NAME"] = variant
            row["RECOVERY_SOURCE"] = mr.ligand_variant_source(rule_id)
            if log_it:
                lig01_entries.append({"table_name": "mol_data_enriched", "record_id": row.get("ligandenNR"),
                                      "field": "molblock", "old_value": original, "new_value": f"{variant} (CID {cid})",
                                      "reason": mr.RULES[rule_id.split('+')[0]].summary,
                                      "source": mr.ledger_source(rule_id), "status": "applied"})
    n_lig01 = st.log_manual_fixes(S2, lig01_entries)
    # rejected variant hits: attribute to the ligand id(s) carrying that name (the ligand may still
    # have been recovered by a later variant, so the failed rows alone are not enough)
    for entry in variant_rejects:
        if entry["record_id"] is None:
            entry["record_id"] = ",".join(name_to_ids.get(entry["old_value"], [])) or None
    st.log_manual_fixes(S2, variant_rejects)
    ctx.log(f"pip1c_2: LIG-01 name variants/pins recovered {n_lig01} ligands ({len(pinned_hits)} pinned LIG-01d); "
            f"{len(variant_rejects)} hit(s) rejected by the structure guard / pin assertion")

    # LIG-03: stereoisomer members get their stereo-specific structure (replaces whatever the
    # name lookup produced, or fills a failed row). Patch every list that carries the row.
    lig03_entries: List[Dict[str, Any]] = []
    seen_lig03: set = set()
    for group in (valid, fixed, failed):
        for row in group:
            lig_id = str(row.get("ligandenNR", "")).strip()
            entry = mr.LIG03_STEREO_STRUCTURES.get(lig_id)
            if entry is None:
                continue
            before = f"{row.get('RECOVERY_SOURCE') or 'molfile'} CID {row.get('RECOVERY_CID') or '-'}"
            row["molblock"] = mr.stereo_molblock(entry)
            row["RECOVERY_SOURCE"] = mr.ligand_stereo_source()
            row["RECOVERY_CID"] = str(entry.cid)
            row["RECOVERY_NAME"] = entry.name
            row.pop("ERROR_RECOVERY", None)
            if lig_id not in seen_lig03:
                seen_lig03.add(lig_id)
                lig03_entries.append({"table_name": "mol_data_enriched", "record_id": lig_id, "field": "molblock",
                                      "old_value": before, "new_value": f"CID {entry.cid} {entry.smiles} ({entry.inchikey})",
                                      "reason": entry.why, "source": mr.ledger_source("LIG-03"), "status": "applied"})
    if len(seen_lig03) != len(mr.LIG03_STEREO_STRUCTURES):
        raise PipelineError(f"LIG-03: only {sorted(seen_lig03)} of {sorted(mr.LIG03_STEREO_STRUCTURES)} found in the recovery output")
    # a LIG-03 row that had failed recovery is now valid: move it
    moved = [r for r in failed if str(r.get("ligandenNR", "")).strip() in seen_lig03]
    for r in moved:
        failed.remove(r)
        valid.append(r)
        fixed.append(dict(r))
    current = valid + failed
    st.log_manual_fixes(S2, lig03_entries)
    ctx.log(f"pip1c_2: LIG-03 stereo-specific structures applied to {len(seen_lig03)} ligands ({len(moved)} moved from failed)")

    stage_stats: Dict[str, Dict[str, int]] = {}
    stage_failures: List[Dict[str, str]] = []
    error_cols: List[str] = []
    for tag, new_cols, worker in mod.PIPELINE:
        ok_rows: List[Dict[str, str]] = []
        n_fail = 0
        err_col = f"ERROR_{tag.upper()}"
        error_cols.append(err_col)
        for row in current:
            for c in new_cols:
                row.setdefault(c, "")
            try:
                worker(row)
            except Exception as exc:
                row[err_col] = str(exc)
                stage_failures.append(row)
                n_fail += 1
            else:
                ok_rows.append(row)
        stage_stats[tag] = {"total": len(current), "ok": len(ok_rows), "fail": n_fail}
        current = ok_rows
        for c in new_cols:
            if c not in fieldnames:
                fieldnames.append(c)
        ctx.log(f"pip1c_2: stage {tag}: ok={len(ok_rows)} fail={n_fail}")

    st.write_rows("mol_data_enriched", current, S2, fieldnames)
    st.write_rows("pip1c2_recovery_fixed", fixed, S2, fieldnames)
    st.write_rows("pip1c2_recovery_failed", failed, S2, fieldnames)
    st.write_rows("pip1c2_stage_failures", stage_failures, S2, fieldnames + error_cols)
    st.commit()
    placeholders = {c: sum(1 for r in current if r.get(c, "") == "*") for c in ("InChI", "SMILES", "COMPOSITION")}
    stats = {"input_rows": len(rows), "valid_molblock": len(valid) - len(fixed), "recovered_via_pubchem": len(fixed),
             "recovery_failed": len(failed), "output_rows": len(current), "stage_stats": stage_stats,
             "placeholder_counts": placeholders, "pubchem": access.stats,
             "lig01_variant_hits": {k: list(v) for k, v in variant_hits.items()},
             "lig01_pinned_hits": {k: list(v) for k, v in pinned_hits.items()},
             "lig03_stereo_applied": sorted(seen_lig03),
             "lig01_variant_rejects": [{k: e[k] for k in ("record_id", "old_value", "new_value", "reason")} for e in variant_rejects]}
    st.put_json("pip1c2_stats", stats, S2)
    return {"output_rows": len(current), "recovered": len(fixed), "recovered_via_name_variant": n_lig01,
            "pinned_lig01d": len(pinned_hits), "stereo_lig03": len(seen_lig03),
            "variant_rejected": len(variant_rejects), "recovery_failed": len(failed),
            "smiles_placeholder": placeholders["SMILES"], **{f"pubchem_{k}": v for k, v in access.stats.items()}}


# =============================================================================
# 1c_3  liganden + mol_data merge, HxL parse, charge reconciliation
# =============================================================================
# pip3_hxl rule tag (its ``rules_applied`` column) -> declared manual rule; Rule2/2b/3 are algorithmic.
_HXL_RULE_IDS = {"Rule1": "HXL-01", "Rule4": "HXL-02", "Rule4b": "HXL-02", "Rule5": "HXL-03", "Rule6": "HXL-04"}


def _ledger_hxl_rules(ctx: Context, out: pd.DataFrame) -> Dict[str, Any]:
    """One ledger row per (ligand row, data-driven HxL rule) that pip3_hxl reports in ``rules_applied``.

    The rule data (counter-ion templates, salt-name tokens, superatom figure, pinned figures) is imported by
    pip3_hxl from manual_rules; this makes each application visible. Rule1 is ledgered on the SMILES
    (the molblock is too large for a ledger cell), the others on figure_definition.
    """
    entries: List[Dict[str, Any]] = []
    algorithmic: Counter = Counter()
    per_rule: Counter = Counter()
    for _, row in out.iterrows():
        tags = [t.strip() for t in str(row.get("rules_applied") or "").split(";") if t.strip()]
        if not tags:
            continue
        note = str(row.get("correction_applied") or "")
        for tag in tags:
            rid = _HXL_RULE_IDS.get(tag)
            if rid is None:
                algorithmic[tag] += 1
                continue
            per_rule[rid] += 1
            if rid == "HXL-01":
                field, old, new = "SMILES", row.get("SMILES_before"), row.get("SMILES")
            else:
                field, old, new = "figure_definition", row.get("figure_definition_original"), row.get("figure_definition")
            entries.append({"table_name": "liganden_moldata_HxL_parsed", "record_id": row.get("ligandenID"), "field": field,
                            "old_value": None if pd.isna(old) else str(old), "new_value": None if pd.isna(new) else str(new),
                            "reason": mr.RULES[rid].summary + (f" | {note}" if note else ""),
                            "source": mr.ledger_source(rid, tag), "status": "applied"})
    n_logged = ctx.staging.log_manual_fixes(S3, entries)
    for rid in ("HXL-01", "HXL-02", "HXL-03", "HXL-04"):
        if per_rule[rid] == 0:
            ctx.log(f"pip1c_3: WARNING {rid} fired on no row (rule data stale?)")
    ctx.log(f"pip1c_3: HxL manual rules {dict(per_rule)} (algorithmic {dict(algorithmic)}), ledger rows {n_logged}")
    return {"hxl_rule_rows": dict(per_rule), "hxl_algorithmic_rows": dict(algorithmic), "hxl_ledger_rows": n_logged}


def run_pip1c_3(ctx: Context) -> Dict[str, Any]:
    st = ctx.staging
    st.require_table("mol_data_enriched", S2)
    ensure_sys_path(PIP1C_3_DIR)
    import pip3_hxl  # noqa: WPS433
    pip3_hxl.logging_utils.VERBOSE = ctx.options.verbose
    from pip3_hxl import EXPORT_COLS, RDKit_OK, compute_debug_stats, manual_review_reason, process_row

    liganden = pd.read_csv(source_csv("liganden"), sep=",", encoding="utf-8-sig", dtype={"ligandenID": "Int64"})
    fieldnames, rows = st.read_rows("mol_data_enriched")
    mol_data = rows_to_df(rows, fieldnames, sep=",", dtype={"ligandenNR": "Int64"})
    ctx.log(f"pip1c_3: liganden={len(liganden)} mol_data={len(mol_data)} RDKit={RDKit_OK}")

    mol_ids = set(mol_data["ligandenNR"].dropna().astype(int))
    lig_ids = set(liganden["ligandenID"].dropna().astype(int))
    orphan_mol_mask = ~mol_data["ligandenNR"].isin(lig_ids)
    orphan_lig = liganden[~liganden["ligandenID"].isin(mol_ids)].copy()
    if len(orphan_lig):
        orphan_lig["failure_reason"] = "No molfile data available (missing from mol_data table)"

    merged = mol_data.merge(liganden, left_on="ligandenNR", right_on="ligandenID", how="left",
                            suffixes=("_mol", "_lig"))
    orphan_mask_merged = merged["ligandenID"].isna()
    if orphan_mask_merged.any():
        merged.loc[orphan_mask_merged, "ligandenID"] = merged.loc[orphan_mask_merged, "ligandenNR"]
    lig_cols = [c for c in merged.columns if c.endswith("_lig") or c in liganden.columns]
    other_cols = [c for c in merged.columns if c not in lig_cols]
    merged = merged[lig_cols + other_cols]
    for col in ["molblock", "InChI", "SMILES", "COMPOSITION", "formula",
                "IUPAC_NAME", "COMMON_NAME", "ERROR_NAMES", "figure_definition"]:
        if col not in merged.columns:
            merged[col] = None

    ctx.log(f"pip1c_3: processing {len(merged)} merged rows")
    out = merged.apply(process_row, axis=1)
    out["manual_review_reason"] = out.apply(manual_review_reason, axis=1)
    stats = compute_debug_stats(out)
    failed_rows = out[out["needs_manual_review"].fillna(False).astype(bool)].copy()
    for c in [c for c in EXPORT_COLS if c not in out.columns]:
        out[c] = pd.NA
    out_export = out.reindex(columns=EXPORT_COLS)
    if list(out_export.columns) != list(EXPORT_COLS) or len(out_export) != len(merged):
        raise PipelineError("pip1c_3: export validation failed (columns/rows)")

    st.write_df("liganden_moldata_HxL_parsed", out_export, S3)
    st.write_df("pip1c3_debug", out, S3)
    st.write_df("pip1c3_failed", failed_rows, S3)
    st.write_df("pip1c3_orphan_liganden", orphan_lig, S3)
    stats = {k: (v.item() if hasattr(v, "item") else v) for k, v in dict(stats).items()}
    stats["orphan_mol_data_included"] = int(orphan_mol_mask.sum())
    stats["orphan_liganden_excluded"] = int(len(orphan_lig))
    st.put_json("pip1c3_stats", stats, S3)
    hxl = _ledger_hxl_rules(ctx, out)
    return {"rows": len(out_export), "columns": out_export.shape[1],
            "needs_manual_review": int(stats.get("needs_manual_review_count", len(failed_rows))),
            "orphan_liganden": int(len(orphan_lig)), "orphan_mol_data": int(orphan_mol_mask.sum()), **hxl}


# =============================================================================
# 1c_4  chemical names (PubChem by SMILES)
# =============================================================================
def _pubchem_names_by_name(name: str) -> Tuple[str, str]:
    """LIG-02 network call: PubChem IUPACName/Title by compound name (raises on failure)."""
    import urllib.parse   # noqa: WPS433
    import requests       # noqa: WPS433
    url = mr.PUBCHEM_NAME_PROPERTY_URL.format(name=urllib.parse.quote(name, safe=""))
    r = requests.get(url, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"PubChem name query failed: HTTP {r.status_code}")
    props = r.json()["PropertyTable"]["Properties"][0]
    return props.get("IUPACName", ""), props.get("Title", "")


def _apply_lig02_name_fallback(ctx: Context, access: "PubChemAccess", fail_rows: List[Dict[str, str]]) -> int:
    """LIG-02: rows whose SMILES query got HTTP 400 are retried by SRD46 ligand name (cached)."""
    def real(key: str) -> Tuple[str, str]:
        return _pubchem_names_by_name(key[len(mr.LIG02_CACHE_PREFIX):])
    by_name = access.smiles_lookup(real)
    entries: List[Dict[str, Any]] = []
    n_ok = 0
    for row in list(fail_rows):
        name = (row.get("name_ligand") or "").strip()
        if mr.LIG02_TRIGGER_SUBSTRING not in (row.get("ERROR_NAMES") or "") or not name:
            continue
        entry = {"table_name": "mol_data_with_names", "record_id": row.get("ligandenID") or row.get("ligandenNR"),
                 "field": "IUPAC_NAME/COMMON_NAME", "old_value": row.get("ERROR_NAMES"),
                 "source": mr.ledger_source("LIG-02"), "reason": mr.RULES["LIG-02"].summary}
        try:
            iupac, title = by_name(mr.LIG02_CACHE_PREFIX + name)
        except Exception as exc:
            entries.append({**entry, "new_value": None, "status": "failed", "reason": f"{entry['reason']}; {exc}"})
            continue
        if not (iupac or title):
            entries.append({**entry, "new_value": None, "status": "failed", "reason": f"{entry['reason']}; empty answer"})
            continue
        row["IUPAC_NAME"], row["COMMON_NAME"] = iupac, title
        row["ERROR_NAMES"] = ""
        fail_rows.remove(row)
        entries.append({**entry, "new_value": f"{iupac} | {title}", "status": "applied"})
        n_ok += 1
    ctx.staging.log_manual_fixes(S4, entries)
    ctx.log(f"pip1c_4: LIG-02 name fallback resolved {n_ok} of {len(entries)} HTTP-400 rows")
    return n_ok


def run_pip1c_4(ctx: Context) -> Dict[str, Any]:
    st = ctx.staging
    st.require_table("liganden_moldata_HxL_parsed", S3)
    mod = load_script(LEGACY_SCRIPTS["pip1c_4"], "srd46_legacy_pip1c_4")
    mod.VERBOSE = ctx.options.verbose
    access = PubChemAccess(ctx)
    seed_info = access.seed()
    ctx.log(f"pip1c_4: PubChem mode={access.mode}; cache={seed_info['cache_counts']}")
    mod.pubchem_names = access.smiles_lookup(mod.pubchem_names)

    fieldnames, rows = df_to_rows(st.read_df("liganden_moldata_HxL_parsed"))
    all_rows, fail_rows, stats = mod.process_names(rows, fieldnames)
    stats = dict(stats)
    stats["lig02_resolved"] = _apply_lig02_name_fallback(ctx, access, fail_rows)
    stats["ok"] += stats["lig02_resolved"]
    stats["fail"] -= stats["lig02_resolved"]
    ext = list(fieldnames)
    for col in ["IUPAC_NAME", "COMMON_NAME"]:
        if col not in ext:
            ext.append(col)
    st.write_rows("mol_data_with_names", [{k: r.get(k, "") for k in ext} for r in all_rows], S4, ext)
    st.write_rows("pip1c4_failed_names", [{k: r.get(k, "") for k in ext + ["ERROR_NAMES"]} for r in fail_rows],
                  S4, ext + ["ERROR_NAMES"])
    st.commit()
    stats["pubchem"] = access.stats
    st.put_json("pip1c4_stats", stats, S4)
    return {"rows": len(all_rows), "names_ok": stats["ok"], "names_failed": stats["fail"],
            "names_by_lig02_fallback": stats["lig02_resolved"],
            "placeholder": stats["placeholder"], **{f"pubchem_{k}": v for k, v in access.stats.items()}}


# =============================================================================
# 1c_5b  Qupkake SDF parsing (existing results only) / off
# =============================================================================
_SDF_ID_RE = re.compile(r"^(?P<id>.+?)_states(?P<extra>.*)\.sdf(?:\.gz)?$", re.IGNORECASE)
_QUP_BASE_COLS = ["ligandennr", "molfile_original", "formula_Q0", "bracket_Q0", "smiles_Q0", "inchi_Q0"]


def _qupkake_input_db(ctx: Context) -> Optional[Path]:
    explicit = getattr(ctx.options, "qupkake_input_db", None)
    if explicit:
        return Path(explicit)
    if ctx.options.qupkake_sdf_dir or ctx.options.qupkake_parsed_csv or os.environ.get("QUPKAKE_SDF_DIR"):
        return None
    from srd46_pipeline.qupkake_bundle import ensure_packaged_file
    ensure_packaged_file(QUPKAKE_INPUT_DB_DEFAULT)
    return QUPKAKE_INPUT_DB_DEFAULT if QUPKAKE_INPUT_DB_DEFAULT.is_file() else None


def _qupkake_sdf_dir(ctx: Context) -> Path:
    if ctx.options.qupkake_sdf_dir:
        return Path(ctx.options.qupkake_sdf_dir)
    env = os.environ.get("QUPKAKE_SDF_DIR")
    return Path(env) if env else QUPKAKE_SDF_DIR_DEFAULT


def _parse_qupkake_sdfs(ctx: Context, files: List[Path]) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, int]]:
    mod = load_script(LEGACY_SCRIPTS["pip1c_5b"], "srd46_legacy_pip1c_5b")
    mod.DEBUG_MODE = False
    mod.VERBOSE_OUTPUT = ctx.options.verbose
    mod.print_debug = lambda s, debug_output=None: print(s)      # the module appends to a log FILE; route to stdout
    mod.RUN_EVENTS.clear()
    mod.FILTER_STATS.clear()

    all_rows: List[Dict[str, Any]] = []
    all_Qs: set = set()
    diag_rows: List[Dict[str, Any]] = []
    skipped = {"empty_sdf": 0, "no_sites": 0, "no_windows": 0}
    for i, sdf_path in enumerate(files, start=1):
        m = _SDF_ID_RE.match(sdf_path.name)
        lig_id = m.group("id") if m else sdf_path.name.split("_states")[0]
        extra = m.group("extra") if m else ""
        id_str = f"{lig_id}{extra}"
        mols = mod.load_sdf_anyhow(sdf_path, removeHs=False, sanitize=True)
        if not mols:
            mod.log_event("skip_incomplete", id_str, reason="empty_sdf")
            skipped["empty_sdf"] += 1
            continue
        base = mols[0]
        sdf_text = sdf_path.read_text(encoding="utf-8", errors="ignore")
        sites = mod.collect_sites_from_sdf_text(sdf_text)
        if not sites:
            mod.log_event("skip_incomplete", id_str, reason="no_sites")
            skipped["no_sites"] += 1
            continue
        sites = mod.filter_sites(base, sites)
        windows = mod.titration_windows(base, sites, debug_sink=None)
        if not windows:
            diag_rows.append(mod.validate_sequence(id_str, sites, []))
            mod.log_event("skip_incomplete", id_str, reason="no_windows")
            skipped["no_windows"] += 1
            continue
        byQ = {wi["Q"]: wi for wi in windows}
        all_Qs.update(byQ.keys())
        w0 = byQ.get(0)
        all_rows.append({
            "ligandennr": id_str, "molfile_original": mod.molblock_original(base),
            "formula_Q0": (w0["formula"] if w0 else ""),
            "bracket_Q0": (f"({w0['lo']}, {w0['hi']})" if w0 else ""),
            "smiles_Q0": (w0["smiles"] if w0 else ""),
            "inchi_Q0": (w0["inchi"] if w0 else ""),
            "_windows_by_Q": byQ,
        })
        diag_rows.append(mod.validate_sequence(id_str, sites, [{"lo": w["lo"], "hi": w["hi"], "Q": int(w["Q"])} for w in windows]))
        mod.log_event("processed", id_str, windows=len(windows))
        if i % 250 == 0:
            ctx.log(f"pip1c_5b: {i}/{len(files)} SDF files parsed")

    Qs_sorted = sorted(all_Qs, reverse=True)
    cols = list(_QUP_BASE_COLS)
    for Q in Qs_sorted:
        cols += [f"formula_Q_{Q}", f"bracket_Q_{Q}", f"smiles_Q_{Q}", f"inchi_Q_{Q}"]
    materialized = []
    for r in all_rows:
        row = {k: r.get(k, "") for k in _QUP_BASE_COLS}
        byQ = r["_windows_by_Q"]
        for Q in Qs_sorted:
            wi = byQ.get(Q)
            row[f"formula_Q_{Q}"] = (wi["formula"] if wi else "")
            row[f"bracket_Q_{Q}"] = (f"({wi['lo']}, {wi['hi']})" if wi else "")
            row[f"smiles_Q_{Q}"] = (wi["smiles"] if wi else "")
            row[f"inchi_Q_{Q}"] = (wi["inchi"] if wi else "")
        materialized.append(row)
    wide = pd.DataFrame(materialized, columns=cols)
    validation = _json_safe_records(diag_rows)
    events = _json_safe_records(list(mod.RUN_EVENTS))
    filter_stats = {str(k): int(v) for k, v in mod.FILTER_STATS.items()}
    ctx.staging.put_json("qupkake_filter_stats", filter_stats, S5B)
    return wide, validation, events, skipped


def _qupkake_archive_candidates(ctx: Context) -> List[Path]:
    return ([Path(ctx.options.qupkake_parsed_csv)] if ctx.options.qupkake_parsed_csv else []) + list(QUPKAKE_PARSED_CSV_CANDIDATES)


def _apply_qup01_archive_fill(ctx: Context, wide: pd.DataFrame, all_files: List[Path], *,
                              archived_rows: Optional[pd.DataFrame] = None,
                              archive_label: Optional[str] = None) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """QUP-01: append archived parsed rows for ligands that have NO SDF file at all."""
    archive = (Path("qupkake_pka_liganden.csv") if archived_rows is not None
               else next((p for p in _qupkake_archive_candidates(ctx) if p.is_file()), None))
    info: Dict[str, Any] = {"archive": archive_label or (str(archive) if archive else None), "appended": 0, "appended_ids": []}
    if archive is None:
        ctx.log("pip1c_5b: QUP-01 skipped (no archived parsed CSV found)")
        return wide, info
    sdf_ids = set()
    for f in all_files:
        m = _SDF_ID_RE.match(f.name)
        sdf_ids.add(f"{m.group('id')}{m.group('extra')}" if m else f.name.split("_states")[0])
    arch = archived_rows if archived_rows is not None else pd.read_csv(archive, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    if "ligandennr" not in arch.columns:
        raise PipelineError(f"QUP-01: archived Qupkake CSV lacks 'ligandennr': {archive}")
    missing = arch[~arch["ligandennr"].astype(str).isin(sdf_ids) & ~arch["ligandennr"].astype(str).isin(set(wide["ligandennr"].astype(str)))]
    if missing.empty:
        ctx.log("pip1c_5b: QUP-01 nothing to fill (every archived ligand has an SDF file)")
        return wide, info
    wide = pd.concat([wide, missing], ignore_index=True).fillna("")
    entries = []
    for _, r in missing.iterrows():
        n_states = sum(1 for c in missing.columns if c.startswith("bracket_Q_") and str(r[c]).strip())
        entries.append({"table_name": "qupkake_pka_liganden", "record_id": r["ligandennr"], "field": "row",
                        "old_value": None, "new_value": f"{n_states} Q-state windows from archive",
                        "reason": mr.RULES["QUP-01"].summary + "; no SDF file for this ligand in the SDF directory",
                        "source": mr.ledger_source("QUP-01", archive.name), "status": "applied"})
    ctx.staging.log_manual_fixes(S5B, entries)
    info.update(appended=len(missing), appended_ids=list(missing["ligandennr"]))
    ctx.log(f"pip1c_5b: QUP-01 appended {len(missing)} archived ligand row(s) without SDF: {info['appended_ids']}")
    return wide, info


def run_pip1c_5b(ctx: Context) -> Dict[str, Any]:
    st = ctx.staging
    mode = ctx.options.qupkake_mode
    if mode == "off":
        wide = pd.DataFrame({"ligandennr": pd.Series([], dtype="string")})
        st.write_df("qupkake_pka_liganden", wide, S5B)
        st.put_json("qupkake_source", {"mode": "off", "note": "Qupkake disabled: pip1c_6 fills Q0 columns from "
                                       "SMILES/InChI/formula with bracket (-inf, +inf) for every ligand"}, S5B)
        ctx.log("pip1c_5b: qupkake=off -> no ML pKa states; Q0 fallback for all ligands")
        return {"mode": "off", "ligands": 0}

    bundle_path = _qupkake_input_db(ctx)
    bundle = None
    if bundle_path is not None:
        from srd46_pipeline.qupkake_bundle import read_predictions
        try:
            bundle = read_predictions(bundle_path, ctx.limit)
        except (OSError, ValueError, sqlite3.Error) as exc:
            raise PipelineError(f"cannot read QupKake SQLite bundle {bundle_path}: {exc}") from exc
    sdf_dir = _qupkake_sdf_dir(ctx)
    files: List[Path] = []
    if bundle is not None:
        files = bundle["all_files"]
    elif sdf_dir.is_dir():
        files = sorted(sdf_dir.glob("*_states*.sdf")) + sorted(sdf_dir.glob("*_states*.sdf.gz"))
    if files:
        n_total = len(files)
        all_files = list(files)
        if ctx.limit is not None:
            files = files[:ctx.limit]
        if bundle is not None:
            ctx.log(f"pip1c_5b: reading {len(files)}/{n_total} precomputed Qupkake SDF results from {bundle_path}")
            wide, validation, events, skipped = (bundle[key] for key in ("wide", "validation", "events", "skipped"))
            st.put_json("qupkake_filter_stats", bundle["filter_stats"], S5B)
            if bundle["archive"] is None:
                qup01 = {"archive": None, "appended": 0, "appended_ids": []}
            else:
                wide, qup01 = _apply_qup01_archive_fill(ctx, wide, all_files, archived_rows=bundle["archive"],
                                                     archive_label=f"{bundle_path}#archived_prediction")
        else:
            ctx.log(f"pip1c_5b: parsing {len(files)}/{n_total} existing Qupkake SDF files from {sdf_dir}")
            wide, validation, events, skipped = _parse_qupkake_sdfs(ctx, files)
            wide, qup01 = _apply_qup01_archive_fill(ctx, wide, all_files)
        st.write_df("qupkake_pka_liganden", wide, S5B)
        st.write_df("qupkake_validation", validation, S5B)
        st.write_df("qupkake_run_events", events, S5B)
        status_counts = validation["status"].value_counts().to_dict() if "status" in validation.columns else {}
        st.put_json("qupkake_source", {"mode": "existing", "kind": "sqlite" if bundle is not None else "sdf_dir", "path": str(bundle_path if bundle is not None else sdf_dir),
                                       "files_found": n_total, "files_parsed": len(files), "ligands": len(wide),
                                       "skipped": skipped, "validation_status": status_counts,
                                       "qup01_archive_fill": qup01}, S5B)
        return {"mode": "existing:sdf", "files": len(files), "ligands": len(wide), "columns": wide.shape[1],
                "qup01_appended": qup01["appended"],
                "needs_review": int(status_counts.get("needs_review", 0)), **{f"skip_{k}": v for k, v in skipped.items()}}

    if bundle is not None:
        wide = bundle["archive"]
        if wide is None:
            raise PipelineError(f"QupKake SQLite bundle has no SDF results or archived predictions: {bundle_path}")
        st.write_df("qupkake_pka_liganden", wide, S5B)
        st.put_json("qupkake_source", {"mode": "existing", "kind": "sqlite:archived_prediction", "path": str(bundle_path),
                                       "rows": len(wide), "warning": "loaded pre-parsed Qupkake results as-is (no SDF states found)"}, S5B)
        ctx.log(f"pip1c_5b: no SDF states in {bundle_path}; using archived SQL predictions ({len(wide)} rows)")
        return {"mode": "existing:parsed_csv", "ligands": len(wide), "columns": wide.shape[1]}

    # No SDF states -> fall back to a previously parsed wide CSV, loaded as-is (provenance recorded)
    candidates = _qupkake_archive_candidates(ctx)
    for p in candidates:
        if p.is_file():
            wide = pd.read_csv(p, dtype=str, keep_default_na=False, encoding="utf-8-sig")
            if "ligandennr" not in wide.columns:
                raise PipelineError(f"pre-parsed Qupkake CSV lacks 'ligandennr': {p}")
            st.write_df("qupkake_pka_liganden", wide, S5B)
            prov = {"mode": "existing", "kind": "parsed_csv", "path": str(p), "rows": len(wide),
                    "mtime": pd.Timestamp(p.stat().st_mtime, unit="s").isoformat(),
                    "warning": "loaded pre-parsed Qupkake results as-is (no SDF states found)"}
            st.put_json("qupkake_source", prov, S5B)
            ctx.log(f"pip1c_5b: WARNING no SDF states in {sdf_dir}; using pre-parsed CSV {p} ({len(wide)} rows)")
            return {"mode": "existing:parsed_csv", "ligands": len(wide), "columns": wide.shape[1]}
    searched = [f"SDF dir: {sdf_dir}"] + [f"CSV: {p}" for p in candidates]
    raise PipelineError("qupkake=existing but no results found. Searched:\n  " + "\n  ".join(searched)
                        + "\nUse --qupkake off, --qupkake-sdf-dir, or --qupkake-parsed-csv.")


# =============================================================================
# 1c_6  merge Qupkake states into the liganden table  (pip1c hand-off)
# =============================================================================
def run_pip1c_6(ctx: Context) -> Dict[str, Any]:
    st = ctx.staging
    st.require_table("mol_data_with_names", S4)
    st.require_table("qupkake_pka_liganden", S5B)
    mod = load_script(LEGACY_SCRIPTS["pip1c_6"], "srd46_legacy_pip1c_6")
    normalize_id, ensure_columns = mod._normalize_id, mod._ensure_columns

    fieldnames, rows = st.read_rows("mol_data_with_names")
    lig_df = rows_to_df(rows, fieldnames, engine="python")
    lig_id_col = next((c for c in ["ligandennr", "ligandenID", "ligandenId", "liganden_id", "LigandenID"]
                       if c in lig_df.columns), None)
    if lig_id_col is None:
        raise PipelineError("pip1c_6: no ligand ID column in mol_data_with_names")
    lig_df["merge_id"] = lig_df[lig_id_col].apply(normalize_id)

    qup_raw = st.read_df("qupkake_pka_liganden")
    qup_df = df_csv_roundtrip(qup_raw, engine="python") if len(qup_raw) else pd.DataFrame({"ligandennr": []})
    qup_df["merge_id"] = qup_df["ligandennr"].apply(normalize_id)
    qup_cols = [c for c in qup_df.columns if c not in ("ligandennr", "merge_id")]
    merged = lig_df.merge(qup_df[["merge_id", *qup_cols]], on="merge_id", how="left")
    merged = ensure_columns(merged, ["formula_Q0", "bracket_Q0", "smiles_Q0", "inchi_Q0",
                                     "formula_Q_0", "bracket_Q_0", "smiles_Q_0", "inchi_Q_0"])
    missing_mask = merged["inchi_Q0"].isna()
    n_missing = int(missing_mask.sum())
    if n_missing:
        formula_col = "formula" if "formula" in merged.columns else ("COMPOSITION" if "COMPOSITION" in merged.columns else None)
        if formula_col:
            merged.loc[missing_mask, "formula_Q0"] = merged[formula_col][missing_mask]
        if "SMILES" in merged.columns:
            merged.loc[missing_mask, "smiles_Q0"] = merged["SMILES"][missing_mask]
        if "InChI" in merged.columns:
            merged.loc[missing_mask, "inchi_Q0"] = merged["InChI"][missing_mask]
        merged.loc[missing_mask, "bracket_Q0"] = "(-inf, +inf)"
        for c in ("formula", "bracket", "smiles", "inchi"):
            merged.loc[missing_mask, f"{c}_Q_0"] = merged.loc[missing_mask, f"{c}_Q0"]
    merged[lig_id_col] = merged["merge_id"].where(merged["merge_id"].notna(),
                                                 merged[lig_id_col].apply(normalize_id)).astype("string")
    merged = merged.drop(columns=["merge_id"])
    st.write_df("liganden_w_moldata_qupkake_parsed", merged, S6)
    src = st.get_json("qupkake_source", {})
    return {"rows": len(merged), "columns": merged.shape[1], "qupkake_matched": len(merged) - n_missing,
            "q0_fallback": n_missing, "qupkake_mode": src.get("mode")}
