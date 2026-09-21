"""
Stage pip2c: assemble the card database (metal / ligand / ligand-metal / references) -> srd46_cards.db.

The pip1/pip2b hand-off tables and the canonical verkn_ligand_metal table (stage raw_canonical,
manual rule SRC-01) are registered in memory with the pip2c helper layer (``register_table``) so
the entry builders read their inputs in memory. Raw SRD46 tables are loaded directly from
the original MySQL dump; canonical and parsed staging tables take precedence.
"""
from __future__ import annotations

import json
import math
import time
from typing import Any, Callable, Dict, List

import pandas as pd

from srd46_pipeline import manual_rules as mr
from srd46_pipeline.legacy import ensure_sys_path
from srd46_pipeline.paths import PIP2C_DIR
from srd46_pipeline.publish import publish, temp_path
from srd46_pipeline.runner import Context, PipelineError
from srd46_pipeline.sources import read_source_table
from srd46_pipeline.staging import df_to_rows

STAGE = "pip2c_cards"
REGISTERED_TABLES = {
    # FILENAMES key         : (staging table,                       producer stage)
    "verkn_ligand_metal": ("verkn_ligand_metal_canonical", "raw_canonical"),   # SRC-01: mysqldump, not CSV
    "liganden_moldata": ("liganden_w_moldata_qupkake_parsed", "pip1c_6_qupkake_merge"),
    "beta_definition_fixed": ("beta_definition_augmented", "pip1a_beta_definition"),
    "metal_parsed": ("metal_augmented", "pip1b_metal"),
    "preferred_ligand_pka_chains": ("preferred_ligand_pka_chains", "pip2b_ligand_pka_chains"),
}
REF_TABLE_KEYS = ["verkn_ligand_metal_literature", "verkn_ligand_metal_literature_sic", "literature",
                  "literature_alt", "paper", "author", "footnote", "verk_literature_author"]
RAW_TABLE_KEYS = ["liganden", "ligand_class", "metal", "constanttyp", "solvent",
                  "beta_definition", *REF_TABLE_KEYS]


def _ids(rows: List[Dict[str, Any]], keys: List[str]) -> List[int]:
    out = set()
    for r in rows:
        for k in keys:
            v = (r.get(k) or "").strip()
            if v:
                out.add(int(float(v)))
                break
    return sorted(out)


def _registered_rows(st, key: str) -> List[Dict[str, str]]:
    """Materialise a helper table, using effective metal IDs for cards and citation joins."""
    table, _ = REGISTERED_TABLES[key]
    frame = st.read_df(table)
    if key == "verkn_ligand_metal":
        if "metalNr_value" not in frame:
            raise PipelineError("pip2c: canonical metalNr_value missing; rerun raw_canonical for VLM-04")
        frame["metalNr"] = frame["metalNr_value"]
    rows = df_to_rows(frame)[1]
    if key == "beta_definition_fixed":
        # The augmented table intentionally omits sides. Its final equation tree retains
        # exactly the species and powers, including manual repairs and fractional powers.
        for row in rows:
            row["equation_sides"] = _equation_sides_from_tree(row)
    return rows


def _register_input_tables(ctx: Context, register_table: Callable) -> None:
    """Load dump tables first, then replace handoffs with their canonical staging data."""
    for key in RAW_TABLE_KEYS:
        _, rows = read_source_table(key)
        register_table(key, rows)
        ctx.log(f"pip2c: registered {key} <- MySQL dump ({len(rows)} rows)")
    for key, (tbl, _) in REGISTERED_TABLES.items():
        rows = _registered_rows(ctx.staging, key)
        register_table(key, rows)
        ctx.log(f"pip2c: registered {key} <- staging.{tbl} ({len(rows)} rows)")


def _equation_sides_from_tree(row: Dict[str, str]) -> str:
    """Project final parser tree terms into the existing card sides representation."""
    if row.get("equation_python", "").strip() in ("", "*"):
        return ""
    try:
        tree = json.loads(row["equation_tree_json"])
        if not isinstance(tree, dict):
            raise ValueError("equation tree must be an object")
        sides = {}
        for side in ("numerator", "denominator"):
            terms = tree[side]
            if not isinstance(terms, list):
                raise ValueError(f"{side} must be an array")
            sides[side] = []
            for term in terms:
                species, power = term["species"], term["power"]
                if not isinstance(species, str) or not species.strip():
                    raise ValueError("species label is missing")
                if isinstance(power, bool) or not isinstance(power, (int, float)) or not math.isfinite(power):
                    raise ValueError("species power must be finite and numeric")
                sides[side].append([species, power])
        return json.dumps(sides, ensure_ascii=False)
    except (KeyError, TypeError, ValueError) as exc:
        raise PipelineError(
            f"pip2c: beta {row.get('beta_definitionID', '?')} has a parsed equation but invalid final tree; "
            "rerun pip1a_beta_definition"
        ) from exc


def _apply_vlm_source_review(data: Dict[str, Any]) -> bool:
    """Append the guarded VLM-05 warning to existing notes without changing chemistry."""
    rid = str(data.get("complex_system_id", ""))
    review = mr.VLM_SOURCE_REVIEWS.get(rid)
    if review is None:
        return False
    info = data.get("stability_info", {})
    expected = review.expected
    for field, source_field in (("ligand_id", "ligandenNr"), ("metal_id", "metalNr"),
                                 ("beta_definition_id", "beta_definitionNr")):
        if str(data.get(field)) != expected[source_field]:
            raise PipelineError(f"VLM-05 card guard failed for {rid}: {field}")
    constant = info.get("constant", {})
    conditions = info.get("conditions", {})
    try:
        valid = (
            info.get("equation_python") == mr.VLM_SOURCE_REVIEW_EQUATION
            and str(info.get("equation_info", {}).get("element_conserved")).lower() in ("true", "1")
            and str(constant.get("constanttypNr")) == expected["constanttypNr"]
            and float(constant["entry_value"]) == float(expected["constant"])
            and str(constant.get("entry_value_raw")) == expected["constant"]
            and float(conditions["temperature_c"]) == float(expected["temperature"])
            and float(conditions["ionic_strength_mol_l"]) == float(expected["ionicstrength"])
        )
    except (KeyError, TypeError, ValueError):
        valid = False
    if not valid:
        raise PipelineError(f"VLM-05 card guard failed for {rid}: equation, balance, value or conditions changed")
    original = info.get("notes")
    if original is not None and not isinstance(original, list):
        raise PipelineError(f"VLM-05 card guard failed for {rid}: notes must retain list representation")
    notes = list(original or [])
    for note in (mr.parser_note("source_convention_review", 1), review.note):
        if note not in notes:
            notes.append(note)
    info["notes"] = notes
    return True


def run(ctx: Context) -> Dict[str, Any]:
    st = ctx.staging
    for key, (tbl, producer) in REGISTERED_TABLES.items():
        st.require_table(tbl, producer)
    ensure_sys_path(PIP2C_DIR)
    import SRD46mod_entrybuilder as eb  # noqa: WPS433
    from pip2c_1_json_schemas import (MissingFieldTracker, build_reference_indexes, create_cation_entry,  # noqa: WPS433
                                      create_ligand_entry, create_metal_ligand_complex_entry,
                                      create_references_entry_by_ligand_metal)
    from pip2c_1_json_schemas.cards_sql_exporter import CardsSQLExporter  # noqa: WPS433
    from pip2c_2_entry_builder_helpers import clear_registered_tables, read_csv_dicts, register_table  # noqa: WPS433
    from pip2c_2_entry_builder_helpers.pka_builder import reset_pka_chain_index  # noqa: WPS433

    # ---- feed the helper layer from staging (no hand-off files) -------------------------
    clear_registered_tables()
    eb.clear_builder_caches()
    reset_pka_chain_index()
    _register_input_tables(ctx, register_table)

    metals_csv = read_csv_dicts("metal")
    ligands_csv = read_csv_dicts("liganden")
    vlm_csv = read_csv_dicts("verkn_ligand_metal")          # registered canonical rows, not the CSV
    if not (metals_csv and ligands_csv and vlm_csv):
        raise PipelineError("pip2c: source metal/liganden tables or the canonical verkn_ligand_metal table not readable")

    # Validate the complete canonical rows and original citation context before any
    # cards-stage ledger writes, including limited builds. The note changes no source data.
    ref_tables = {k: read_csv_dicts(k) for k in REF_TABLE_KEYS}
    try:
        mr.validate_vlm_source_review_rows(vlm_csv, ref_tables)
    except ValueError as exc:
        raise PipelineError(str(exc)) from exc

    # LIG-04: ligand-level placeholder verdict, computed from the SRD46 record (figure_definition,
    # formula) + the enriched structure and LEDGERED per ligand. ligand_card gets no column for it
    # (schema frozen to the downstream readers, NOTE-01): the same verdict is derived from the
    # published table by mr.LIGAND_PLACEHOLDER_SQL and cross-checked against this count below.
    formula_by_id = {str(r.get("ligandenID") or r.get("ligandenNr") or "").strip(): r.get("formula") for r in ligands_csv}
    _, mol_rows = df_to_rows(st.read_df(REGISTERED_TABLES["liganden_moldata"][0]))
    lig04_entries: List[Dict[str, Any]] = []
    n_placeholder_ligands = 0
    for r in mol_rows:
        lid = str(r.get("ligandenID") or "").strip()
        fields = mr.ligand_placeholder_fields(r.get("figure_definition"), formula_by_id.get(lid), r.get("SMILES"))
        if fields:
            is_ph = mr.ligand_is_placeholder(fields)
            n_placeholder_ligands += int(is_ph)
            lig04_entries.append({"table_name": "ligand_card", "record_id": lid, "field": "placeholder",
                                  "old_value": ",".join(fields), "new_value": "1" if is_ph else "0",
                                  "reason": mr.RULES["LIG-04"].summary, "source": mr.ledger_source("LIG-04"),
                                  "status": "applied"})
    n_lig04 = st.log_manual_fixes(STAGE, lig04_entries)
    ctx.log(f"pip2c: LIG-04: {n_placeholder_ligands} whole-record placeholder ligands, "
            f"{n_lig04} ligands with any placeholder field (ledgered)")
    metal_ids = _ids(metals_csv, ["metalID", "metalNr"])
    ligand_ids = _ids(ligands_csv, ["ligandenID", "ligandenNr"])
    vlm_ids = _ids(vlm_csv, ["verkn_ligand_metalID"])
    if ctx.limit is not None:
        metal_ids, ligand_ids, vlm_ids = metal_ids[:ctx.limit], ligand_ids[:ctx.limit], vlm_ids[:ctx.limit]
    ctx.log(f"pip2c: {len(metal_ids)} metals, {len(ligand_ids)} ligands, {len(vlm_ids)} complexes")

    pair_vlm_ids: Dict[tuple, List[int]] = {}
    for r in vlm_csv:
        lig, met, vid = (r.get("ligandenNr") or "").strip(), (r.get("metalNr") or "").strip(), (r.get("verkn_ligand_metalID") or "").strip()
        if lig and met and vid:
            try:
                pair_vlm_ids.setdefault((int(float(lig)), int(float(met))), []).append(int(float(vid)))
            except ValueError:
                continue

    tracker = MissingFieldTracker()
    failures: List[Dict[str, Any]] = []

    def build(kind: str, ids: List[int], builder, creator, every: int) -> List[Any]:
        entries = []
        t0 = time.time()
        for i, _id in enumerate(ids, start=1):
            try:
                data = builder(_id)
                if kind == "complex":
                    _apply_vlm_source_review(data)
                entry = creator(data, tracker)
                if entry:
                    entries.append(entry)
            except PipelineError:
                raise  # guarded source-review drift must abort publication, not drop a target
            except Exception as exc:  # recorded, never silently dropped
                failures.append({"kind": kind, "id": _id, "error_type": type(exc).__name__, "error": str(exc)[:500]})
            if i % every == 0:
                ctx.log(f"pip2c: {kind} {i}/{len(ids)} ({time.time() - t0:.0f}s)")
        return entries

    metal_entries = build("metal", metal_ids, eb.build_cation_data, create_cation_entry, 100)
    ligand_entries = build("ligand", ligand_ids, eb.build_ligand_data, create_ligand_entry, 1000)
    complex_entries = build("complex", vlm_ids, eb.build_complex_data, create_metal_ligand_complex_entry, 10000)
    ctx.log(f"pip2c: built {len(metal_entries)} metals, {len(ligand_entries)} ligands, "
            f"{len(complex_entries)} complexes; {len(failures)} build failures")

    # ---- export to a temp DB, then publish atomically -----------------------------------
    cards_db = ctx.paths.cards_db
    cards_db.parent.mkdir(parents=True, exist_ok=True)
    tmp = temp_path(cards_db)
    ref_indexes = build_reference_indexes(ref_tables)
    ref_count = 0
    ref_errors: List[Dict[str, Any]] = []
    with CardsSQLExporter(tmp) as exporter:
        exporter.begin_bulk()
        ctx.log("pip2c: exporting metals / ligands / complexes")
        exporter.export_all_metals(metal_entries, verbose=False)
        exporter.export_all_ligands(ligand_entries, verbose=False)
        exporter.export_all_ligand_metals(complex_entries, verbose=False)
        unique_pairs = sorted({(int(e.ligand_id), int(e.metal_id)) for e in complex_entries if e.ligand_id and e.metal_id})
        ctx.log(f"pip2c: exporting references for {len(unique_pairs)} ligand-metal pairs")
        for i, (lid, mid) in enumerate(unique_pairs, start=1):
            try:
                refs_entry = create_references_entry_by_ligand_metal(lid, mid, ref_tables, tracker, indexes=ref_indexes)
                ids = pair_vlm_ids.get((lid, mid), [])
                if refs_entry and ids:
                    exporter.export_references(refs_entry, ids)
                    ref_count += 1
            except Exception as exc:
                ref_errors.append({"kind": "references", "id": f"{lid}:{mid}", "error_type": type(exc).__name__,
                                   "error": str(exc)[:500]})
            if i % 5000 == 0:
                ctx.log(f"pip2c: references {i}/{len(unique_pairs)}")
        exporter.end_bulk()
        # NOTE-01: placeholder / accepted split derived from the frozen schema (notes tokens, LIG-04 SQL)
        split: Dict[str, Dict[str, int]] = {}
        for table, query in mr.PLACEHOLDER_SPLIT_QUERIES.items():
            ph, acc, total = exporter.conn.execute(query).fetchone()
            split[table] = {"placeholder": int(ph or 0), "accepted": int(acc or 0), "total": int(total or 0)}
        n_parser_notes = exporter.conn.execute(
            "SELECT COUNT(*) FROM ligandmetal_stability_measured WHERE notes LIKE '%' || ? || '%'",
            (mr.PARSER_NOTE_PREFIX,)).fetchone()[0]
        db_stats = exporter.get_stats()
    if ctx.limit is None and split["ligand_card"]["placeholder"] != n_placeholder_ligands:
        raise PipelineError(f"pip2c: LIG-04 disagreement: rule flags {n_placeholder_ligands} placeholder ligands, "
                            f"LIGAND_PLACEHOLDER_SQL selects {split['ligand_card']['placeholder']} in ligand_card")
    expected_review_count = sum(str(vid) in mr.VLM_SOURCE_REVIEWS for vid in vlm_ids)
    with_source_review = sum(
        1 for entry in complex_entries if str(entry.complex_system_id) in mr.VLM_SOURCE_REVIEWS
    )
    if with_source_review != expected_review_count:
        raise PipelineError(f"VLM-05 publication guard: built {with_source_review}/{expected_review_count} reviewed rows")
    st.log_manual_fixes(STAGE, [
        {"table_name": "ligandmetal_stability_measured", "record_id": str(vid), "field": "notes",
         "old_value": None, "new_value": mr.parser_note("source_convention_review", 1),
         "reason": mr.VLM_SOURCE_REVIEWS[str(vid)].note, "source": mr.ledger_source("VLM-05"),
         "status": "source_review"}
        for vid in vlm_ids if str(vid) in mr.VLM_SOURCE_REVIEWS
    ])
    publish(tmp, cards_db)
    ctx.log(f"pip2c: NOTE-01: {n_parser_notes} measured rows carry parser notes; placeholder split {split}")

    st.write_df("pip2c_build_failures", pd.DataFrame(failures + ref_errors), STAGE)
    st.put_json("pip2c_stats", {"metals": len(metal_entries), "ligands": len(ligand_entries),
                                "complexes": len(complex_entries), "reference_pairs": ref_count,
                                "build_failures": len(failures), "reference_errors": len(ref_errors),
                                "db_stats": db_stats, "rows_with_parser_notes": int(n_parser_notes),
                                "placeholder_split": {**split, "ligands_any_placeholder_field": n_lig04}}, STAGE)
    st.put_json("pip2c_missing_field_report", tracker.summary_text(), STAGE)
    by_kind = pd.Series([f["kind"] for f in failures]).value_counts().to_dict() if failures else {}
    return {"metals": len(metal_entries), "ligands": len(ligand_entries), "complexes": len(complex_entries),
            "reference_pairs": ref_count, "build_failures": len(failures), "reference_errors": len(ref_errors),
            "failures_by_kind": by_kind, "ligandmetal_card": db_stats.get("ligandmetal_card"),
            "rows_with_parser_notes": int(n_parser_notes), "placeholder_split": split,
            "ligand_pka_measured": db_stats.get("ligand_pka_measured"), "db": str(cards_db)}
