"""Stage pip1b: metal table parsing (charges, stoichiometry, SMILES/InChI) + manual rules MET-01/MET-02."""
from __future__ import annotations

import json
from collections import Counter
from typing import Any, Dict, List

import pandas as pd

from srd46_pipeline import manual_rules as mr
from srd46_pipeline.legacy import load_script
from srd46_pipeline.paths import LEGACY_SCRIPTS, PIP1B_DIR
from srd46_pipeline.runner import Context, PipelineError
from srd46_pipeline.sources import source_csv

STAGE = "pip1b_metal"


def _apply_metal_smiles_rule(ctx: Context, mod: Any, df: pd.DataFrame) -> Dict[str, Any]:
    """MET-01: fill SMILES/InChI/InChIKey for the polyatomic 'metals' the parser leaves empty.

    Every entry is validated with RDKit before use: formal charge == charge parsed from the
    name, element counts (explicit H) == ``calculate_stoichiometry`` of the parsed components
    (or the declared ``formula`` override, which then also replaces the parser stoichiometry).
    A mismatch aborts the stage - a wrong manual SMILES must never reach the cards.
    """
    from rdkit import Chem  # noqa: WPS433

    entries: List[Dict[str, Any]] = []
    applied = shadowed = 0
    unmatched: List[str] = []
    for idx, row in df.iterrows():
        name = str(row.get("name_metal") or "").strip()
        smiles_missing = pd.isna(row.get("SMILES")) or str(row.get("SMILES")).strip() == ""
        rule = mr.METAL_SMILES_MANUAL.get(name)
        if rule is None:
            if smiles_missing:
                unmatched.append(name)
            continue
        record_id = row.get("metalID")
        if not smiles_missing:
            shadowed += 1
            entries.append({"table_name": "metal_augmented", "record_id": record_id, "field": "SMILES",
                            "old_value": row.get("SMILES"), "new_value": rule.smiles,
                            "reason": "parser already produced a SMILES for this name; manual rule not applied (shadowed)",
                            "source": mr.ledger_source("MET-01"), "status": "not_applied"})
            continue
        parsed = mod.parse_metal_formula(name)
        expect = rule.formula or mod.calculate_stoichiometry(parsed["components"])
        expect = {k: int(v) for k, v in expect.items() if int(v) > 0}
        mol = Chem.MolFromSmiles(rule.smiles)
        if mol is None:
            raise PipelineError(f"MET-01 {name!r}: RDKit cannot parse SMILES {rule.smiles!r}")
        got = dict(Counter(a.GetSymbol() for a in Chem.AddHs(mol).GetAtoms()))
        charge = Chem.GetFormalCharge(mol)
        if got != expect or charge != int(parsed["charge"]):
            raise PipelineError(f"MET-01 {name!r}: SMILES {rule.smiles!r} gives {got} charge {charge}, "
                                f"expected {expect} charge {parsed['charge']}")
        inchi, inchikey = mod.generate_inchi(rule.smiles)
        df.at[idx, "SMILES"] = rule.smiles
        df.at[idx, "InChI"] = inchi
        df.at[idx, "InChIKey"] = inchikey
        note = mr.METAL_SMILES_PARSE_NOTE + (f"; {rule.note}" if rule.note else "")
        old_notes = row.get("parse_notes")
        df.at[idx, "parse_notes"] = note if (old_notes is None or pd.isna(old_notes) or not str(old_notes).strip()) \
            else f"{old_notes}; {note}"
        if rule.formula is not None and "stoichiometry" in df.columns:
            df.at[idx, "stoichiometry"] = json.dumps(rule.formula)
            entries.append({"table_name": "metal_augmented", "record_id": record_id, "field": "stoichiometry",
                            "old_value": row.get("stoichiometry"), "new_value": json.dumps(rule.formula),
                            "reason": rule.note, "source": mr.ledger_source("MET-01"), "status": "applied"})
        entries.append({"table_name": "metal_augmented", "record_id": record_id, "field": "SMILES",
                        "old_value": None, "new_value": rule.smiles,
                        "reason": mr.RULES["MET-01"].summary + (f"; {rule.note}" if rule.note else ""),
                        "source": mr.ledger_source("MET-01"), "status": "applied"})
        applied += 1
    names = set(df["name_metal"].astype(str).str.strip())
    for name, rule in mr.METAL_SMILES_MANUAL.items():
        if name not in names:
            entries.append({"table_name": "metal_augmented", "record_id": None, "field": "SMILES",
                            "old_value": None, "new_value": rule.smiles,
                            "reason": f"rule entry {name!r} matches no row of the metal table (register stale?)",
                            "source": mr.ledger_source("MET-01"), "status": "missing"})
    n_logged = ctx.staging.log_manual_fixes(STAGE, entries)
    if unmatched:
        ctx.log(f"pip1b: WARNING {len(unmatched)} metals still without SMILES and without a MET-01 entry: {unmatched}")
    ctx.log(f"pip1b: MET-01 applied to {applied} metals (shadowed {shadowed}, ledger rows {n_logged})")
    return {"met01_applied": applied, "met01_shadowed": shadowed, "met01_unmatched": len(unmatched),
            "met01_ledger_rows": n_logged}


def _ledger_met02(ctx: Context, mod: Any, df: pd.DataFrame) -> Dict[str, Any]:
    """MET-02: one ledger row per metal the parser classified through an organic substituent abbreviation.

    The parser itself consumed ``mr.MET02_ORGANIC_SUBSTITUENTS`` (its ``ORGANIC_SUBSTITUENTS`` is a re-export);
    this only makes the effect visible. A row flagged organometallic AND simple ion is the documented
    element clash (Pr = praseodymium vs propyl) and is ledgered ``suspect_element_clash``.
    """
    assert dict(mod.ORGANIC_SUBSTITUENTS) == dict(mr.MET02_ORGANIC_SUBSTITUENTS), "pip1b: ORGANIC_SUBSTITUENTS shim out of sync with MET-02"
    entries: List[Dict[str, Any]] = []
    applied = suspect = 0
    for _, row in df.iterrows():
        if not bool(row.get("is_organometallic")):
            continue
        comps = row.get("formula_components")
        keys = list(json.loads(comps).keys()) if isinstance(comps, str) and comps.strip() else []
        used = [k for k in keys if k in mr.MET02_ORGANIC_SUBSTITUENTS]
        clash = bool(row.get("is_simple_ion"))
        expansion = ", ".join(f"{k} -> {mr.MET02_ORGANIC_SUBSTITUENTS[k]}" for k in used) or "(abbreviation matched as a substring only)"
        entries.append({"table_name": "metal_augmented", "record_id": row.get("metalID"), "field": "is_organometallic",
                        "old_value": str(row.get("name_metal")), "new_value": expansion,
                        "reason": ("abbreviation equals an element symbol; classified organometallic and simple ion, stoichiometry None"
                                   if clash else mr.RULES["MET-02"].summary),
                        "source": mr.ledger_source("MET-02"), "status": "suspect_element_clash" if clash else "applied"})
        applied += not clash
        suspect += clash
    n_logged = ctx.staging.log_manual_fixes(STAGE, entries)
    ctx.log(f"pip1b: MET-02 classified {applied} organometallic metals ({suspect} element-clash suspects, ledger rows {n_logged})")
    return {"met02_organometallic": applied, "met02_suspect": suspect, "met02_ledger_rows": n_logged}


def run(ctx: Context) -> Dict[str, Any]:
    mod = load_script(LEGACY_SCRIPTS["pip1b"], "srd46_legacy_pip1b", [PIP1B_DIR])
    mod.CONFIG.VERBOSE = ctx.options.verbose
    src = source_csv("metal")
    ctx.log(f"pip1b: parsing {src.name}")
    # Preserve the legacy loader's pandas inference without its filesystem-only CSV check.
    df = mod.parse_all_metals(pd.read_csv(src, encoding="utf-8"))
    for col in ("SMILES", "InChI", "InChIKey", "parse_notes", "stoichiometry"):
        if col in df.columns:
            df[col] = df[col].astype(object)
    met01 = _apply_metal_smiles_rule(ctx, mod, df)
    met02 = _ledger_met02(ctx, mod, df)
    st = ctx.staging
    st.write_df("metal_augmented", df, STAGE)
    st.put_json("pip1b_column_meta", dict(mod.METAL_COLUMN_METADATA), STAGE)
    st.put_json("pip1b_parsed_export_cols", list(mod.METAL_PARSED_EXPORT_COLS), STAGE)
    return {"rows": len(df), "columns": df.shape[1],
            "with_smiles": int(df["SMILES"].notna().sum()) if "SMILES" in df.columns else None,
            "simple_ions": int(df["is_simple_ion"].sum()) if "is_simple_ion" in df.columns else None,
            **met01, **met02}
