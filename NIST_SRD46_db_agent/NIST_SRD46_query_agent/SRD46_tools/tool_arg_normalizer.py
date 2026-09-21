import logging
import re
from typing import Dict

from NIST_SRD46_core_db_search_tools import _sql_ast as _sa


log = logging.getLogger("SRD46-UI")


_INT_RE = re.compile(r"\d+")
_FLOAT_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


_PARAM_ALIASES: Dict[str, Dict[str, str]] = {
    "0_preplan_decision": {
        "query": "question",
        "q": "question",
        "user_question": "question",
    },
    "0_plan_search_strategy": {
        "query": "question",
        "q": "question",
        "user_question": "question",
        "ctx": "context",
        "prior": "context",
        "plan": "context",
        "revision": "revision_note",
        "edit": "revision_note",
        "note": "revision_note",
        "change": "revision_note",
        "planner_system_prompt_module": "system_prompt_module",
        "planning_system_prompt_module": "system_prompt_module",
        "prompt_module": "system_prompt_module",
    },
    "search_metals": {
        "metal_name": "name",
        "metal_name_srd": "name",
        "metal": "name",
        "symbol_pure": "symbol",
        "ion_symbol": "symbol",
        "smiles_string": "smiles",
        "smiles_code": "smiles",
        "inchi_string": "inchi",
        "inchikey": "inchi",
    },
    "search_ligands": {
        "ligand_name": "name",
        "ligand_name_srd": "name",
        "ligand": "name",
        "chemical_formula": "formula",
        "class": "ligand_class",
        "ligand_class_name": "ligand_class",
        "smiles_string": "smiles",
        "smiles_code": "smiles",
        "inchi_string": "inchi",
        "inchikey": "inchi",
    },
    "build_system_catalog": {
        "metal_ids": "metal_id",
        "ligand_ids": "ligand_id",
        "beta_def_id": "beta_definition_id",
        "beta_id": "beta_definition_id",
    },
    "search_stability": {
        "where": "sql_where_query",
        "sql_where": "sql_where_query",
        "sql": "sql_where_query",
        "query": "sql_where_query",
        "q": "sql_where_query",
        "metal": "metal_name",
        "name": "metal_name",
        "ligand": "ligand_name",
        "type": "constant_type",
        "beta_def_id": "beta_definition_id",
        "beta_id": "beta_definition_id",
        "temp": "temperature",
        "temperature_c": "temperature",
        "t": "temperature",
        "i": "ionic_strength",
        "ionic": "ionic_strength",
    },
    "search_pka_values": {
        "where": "sql_where_query",
        "sql_where": "sql_where_query",
        "sql": "sql_where_query",
        "query": "sql_where_query",
        "q": "sql_where_query",
        "ligand": "ligand_name",
        "name": "ligand_name",
        "temp": "temperature",
        "temperature_c": "temperature",
        "t": "temperature",
        "i": "ionic_strength",
        "ionic": "ionic_strength",
    },
    "search_pka_ligands": {
        "where": "sql_where_query",
        "sql_where": "sql_where_query",
        "sql": "sql_where_query",
        "query": "sql_where_query",
        "q": "sql_where_query",
        "ligand": "ligand_name",
        "name": "ligand_name",
        "temp": "temperature",
        "temperature_c": "temperature",
        "t": "temperature",
        "i": "ionic_strength",
        "ionic": "ionic_strength",
    },
    "search_networks": {
        "where": "sql_where_query",
        "sql_where": "sql_where_query",
        "sql": "sql_where_query",
        "query": "sql_where_query",
        "q": "sql_where_query",
        "metal": "metal_name",
        "name": "metal_name",
        "ligand": "ligand_name",
    },
    "search_citations": {
        "where": "sql_where_query",
        "sql_where": "sql_where_query",
        "sql": "sql_where_query",
        "query": "sql_where_query",
        "q": "sql_where_query",
        "shortcut_code": "shortcut",
        "code": "shortcut",
        "text": "citation_text",
        "citation": "citation_text",
        "vlm": "vlm_id",
        "id": "vlm_id",
    },
    "inspect_card": {
        "id": "prefix_id",
        "vlm_id": "prefix_id",
        "metal_id": "prefix_id",
        "ligand_id": "prefix_id",
    },
    "inspect_literature": {
        "id": "prefix_id",
        "vlm_id": "prefix_id",
    },
    "db_count_records": {
        "table_name": "table",
    },
    "db_distribution": {
        "table_name": "table",
        "groupby": "group_column",
        "group_by": "group_column",
        "group": "group_column",
        "sql_where": "where",
    },
    "db_ranked_pairs": {
        "ranking": "rank_by",
        "mode": "rank_by",
        "sql_where": "where",
    },
    "get_table_schema": {
        "table": "table_name",
        "name": "table_name",
        "db": "database",
    },
    "execute_srd46_sql": {
        "sql": "sql_query",
        "query": "sql_query",
        "description": "task_description",
        "task": "task_description",
        "purpose": "task_description",
        "intent": "task_description",
        "reasoning": "task_description",
        "explanation": "task_description",
        "columns": "column_legend",
        "column_explanation": "column_legend",
        "columns_explanation": "column_legend",
        "table_explanation": "column_legend",
        "legend": "column_legend",
        "schema_legend": "column_legend",
        "eq": "attach_equilibrium",
        "equilibrium": "attach_equilibrium",
        "lit": "attach_literature",
        "literature": "attach_literature",
    },
    "search_similar_ligands": {
        "id": "ligand_id",
        "name": "ligand_name",
        "limit": "top_k",
        "k": "top_k",
        "metal_id": "metal_ids",
    },
}

_TABLE_VALUE_ALIASES = {
    "ligand": "ligand_card",
    "ligands": "ligand_card",
    "metal": "metal_card",
    "metals": "metal_card",
    "stability": "ligandmetal_stability_measured",
    "stability_measured": "ligandmetal_stability_measured",
    "pka": "ligand_pka_measured",
    "citations": "ref_literature_alt",
    "citation": "ref_literature_alt",
}

_GROUP_COLUMN_VALUE_ALIASES = {
    "ligand_class": "ligand_class_name",
    "class": "ligand_class_name",
}

_WHERE_COLUMN_ALIASES = {
    "ligand_class": "ligand_class_name",
}

# ── Per-tool SQL clause rewrites ────────────────────────────────────
# Fix both table-prefix errors (s.X → c.X) and column-name
# abbreviations (ionic_strength → ionic_strength_mol_l) that LLMs
# commonly produce.  Applied to WHERE *and* ORDER BY clauses.

_STABILITY_CLAUSE_REWRITES = {
    # -- wrong table prefix: card columns attributed to measurement table --
    "s.beta_definition_id":   "c.beta_definition_id",
    "s.beta_definition_name": "c.beta_definition_name",
    "s.metal_id":             "c.metal_id",
    "s.ligand_id":            "c.ligand_id",
    "s.metal_name_SRD":       "c.metal_name_SRD",
    "s.ligand_name_SRD":      "c.ligand_name_SRD",
    "s.ligand_class_name":    "c.ligand_class_name",
    "s.ligand_SMILES":        "c.ligand_SMILES",
    # -- abbreviated column names (any prefix) --
    "s.ionic_strength":       "s.ionic_strength_mol_l",
    "c.ionic_strength":       "s.ionic_strength_mol_l",
    "s.temperature":          "s.temperature_c",
    "c.temperature":          "s.temperature_c",
    "s.metal_name":           "c.metal_name_SRD",
    "c.metal_name":           "c.metal_name_SRD",
    "s.ligand_name":          "c.ligand_name_SRD",
    "c.ligand_name":          "c.ligand_name_SRD",
    "s.beta_def_label":       "c.beta_definition_name",
    "c.beta_def_label":       "c.beta_definition_name",
    "s.beta_def_name":        "c.beta_definition_name",
    "c.beta_def_name":        "c.beta_definition_name",
    "s.beta_def_id":          "c.beta_definition_id",
    "c.beta_def_id":          "c.beta_definition_id",
    "s.log_K":                "s.constant_value",
    "c.log_K":                "s.constant_value",
    "s.value":                "s.constant_value",
    "c.value":                "s.constant_value",
    "s.constant":             "s.constant_value",
    "c.constant":             "s.constant_value",
    "s.logK":                 "s.constant_value",
    "c.logK":                 "s.constant_value",
    "s.electrolyte":          "s.electrolyte_composition",
    "c.electrolyte":          "s.electrolyte_composition",
    "s.solvent":              "s.solvent_name",
    "c.solvent":              "s.solvent_name",
    "s.ligand_class":         "c.ligand_class_name",
    "c.ligand_class":         "c.ligand_class_name",
}

_PKA_CLAUSE_REWRITES = {
    # -- wrong table prefix: ligand_card uses alias lc, not c --
    "c.ligand_id":            "lc.ligand_id",
    "c.ligand_name_SRD":      "lc.ligand_name_SRD",
    "c.ligand_class_name":    "lc.ligand_class_name",
    "c.formula":              "lc.formula",
    "c.ligand_SMILES":        "lc.ligand_SMILES",
    "c.definition_HxL":       "lc.definition_HxL",
    # -- LLM uses stability prefix "s" instead of pKa prefix "p" --
    "s.pKa":                  "p.pKa",
    "s.pKa_type":             "p.pKa_type",
    "s.temperature_c":        "p.temperature_c",
    "s.ionic_strength_mol_l": "p.ionic_strength_mol_l",
    "s.solvent_name":         "p.solvent_name",
    "s.electrolyte":          "p.electrolyte",
    "s.quality":              "p.quality",
    "s.ligand_id":            "lc.ligand_id",
    "s.ligand_name_SRD":      "lc.ligand_name_SRD",
    "s.ligand_class_name":    "lc.ligand_class_name",
    # -- abbreviated column names --
    "s.value":                "p.pKa",
    "p.value":                "p.pKa",
    "lc.value":               "p.pKa",
    "c.value":                "p.pKa",
    "p.ionic_strength":       "p.ionic_strength_mol_l",
    "s.ionic_strength":       "p.ionic_strength_mol_l",
    "lc.ionic_strength":      "p.ionic_strength_mol_l",
    "c.ionic_strength":       "p.ionic_strength_mol_l",
    "p.temperature":          "p.temperature_c",
    "s.temperature":          "p.temperature_c",
    "lc.temperature":         "p.temperature_c",
    "c.temperature":          "p.temperature_c",
    "c.ligand_name":          "lc.ligand_name_SRD",
    "s.ligand_name":          "lc.ligand_name_SRD",
    "lc.ligand_name":         "lc.ligand_name_SRD",
    "p.ligand_name":          "lc.ligand_name_SRD",
    "c.ligand_class":         "lc.ligand_class_name",
    "s.ligand_class":         "lc.ligand_class_name",
    "lc.ligand_class":        "lc.ligand_class_name",
    "p.solvent":              "p.solvent_name",
    "s.solvent":              "p.solvent_name",
    "c.solvent":              "p.solvent_name",
}


def _extract_int(value):
    if value is None:
        return None
    if isinstance(value, int):
        return value
    match = _INT_RE.search(str(value))
    return int(match.group(0)) if match else None


def _extract_float(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = _FLOAT_RE.search(str(value))
    return float(match.group(0)) if match else None


def _sql_quote(value) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _coerce_prefix(value, prefix: str):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.startswith(prefix + "_"):
        return text
    num = _extract_int(text)
    if num is not None:
        return f"{prefix}_{num}"
    return text


def _append_where(args: dict, *clauses: str) -> None:
    """Append AND-conjoined predicates to args['sql_where_query']'s WHERE part.

    Preserves any trailing ORDER BY / LIMIT in the existing query and
    handles the case where the agent emits a leading ``WHERE`` keyword.
    """
    raw = str(args.get("sql_where_query", "") or "").strip()
    new_clauses = [c for c in clauses if c]
    if not raw:
        if new_clauses:
            args["sql_where_query"] = " AND ".join(f"({c})" for c in new_clauses)
        return
    try:
        where, order_by, limit = _sa.parse_sql_where_query(raw)
    except Exception:
        # Fallback: treat the whole string as a WHERE fragment.
        where, order_by, limit = raw, "", ""
    parts: list[str] = []
    if where and where.strip() and where.strip() != "1=1":
        parts.append(where)
    parts.extend(new_clauses)
    if not parts:
        new_where = "1=1"
    elif len(parts) == 1:
        new_where = parts[0]
    else:
        new_where = " AND ".join(f"({p})" for p in parts)
    tail = ""
    if order_by:
        tail += f" ORDER BY {order_by}"
    if limit:
        tail += f" LIMIT {limit}"
    args["sql_where_query"] = new_where + tail


def _merge_legacy_order_limit(args: dict) -> None:
    """Fold a legacy ``order_by`` / ``limit`` arg into ``sql_where_query``.

    Older callers (and some agents prompted with the old signature) may
    still emit separate ``order_by`` / ``limit`` arguments. Merge them
    into the query string and drop the keys.
    """
    order_by = args.pop("order_by", None)
    limit = args.pop("limit", None)
    if not order_by and limit in (None, ""):
        return
    raw = str(args.get("sql_where_query", "") or "").strip()
    try:
        where, existing_order, existing_limit = _sa.parse_sql_where_query(raw)
    except Exception:
        where, existing_order, existing_limit = raw or "1=1", "", ""
    if order_by and not existing_order:
        existing_order = str(order_by).strip()
    if limit not in (None, "") and not existing_limit:
        try:
            existing_limit = str(int(limit))
        except (TypeError, ValueError):
            existing_limit = str(limit).strip()
    rebuilt = where or "1=1"
    if existing_order:
        rebuilt += f" ORDER BY {existing_order}"
    if existing_limit:
        rebuilt += f" LIMIT {existing_limit}"
    args["sql_where_query"] = rebuilt


def _rewrite_sql_where_query(args: dict, rewrites: dict) -> None:
    """Apply column/table rewrites to the WHERE portion of sql_where_query.

    The trailing ORDER BY / LIMIT pieces are split off, the WHERE part is
    rewritten through the AST, then the pieces are reassembled. Also
    strips a leading ``WHERE`` keyword the agent may have included.
    """
    raw = args.get("sql_where_query")
    if not raw or not str(raw).strip():
        return
    try:
        where, order_by, limit = _sa.parse_sql_where_query(str(raw))
    except Exception:
        # Best-effort fallback: rewrite the raw string as a WHERE clause.
        new_where = _rewrite_clause(str(raw), rewrites, kind="where")
        args["sql_where_query"] = new_where
        return
    new_where = _rewrite_clause(where, rewrites, kind="where") or "1=1"
    if order_by:
        new_order = _rewrite_clause(order_by, rewrites, kind="order_by") or order_by
    else:
        new_order = ""
    rebuilt = new_where
    if new_order:
        rebuilt += f" ORDER BY {new_order}"
    if limit:
        rebuilt += f" LIMIT {limit}"
    args["sql_where_query"] = rebuilt


_DJANGO_FILTER_RE = re.compile(
    r"(\w+)__like\s*=\s*('[^']*'|\"[^\"]*\")",
    re.IGNORECASE,
)


def _fix_django_filters(clause: str, *, kind: str = "where") -> str:
    """Convert Django-style ``col__like = 'val'`` to SQL ``col LIKE 'val'``.

    AST-backed via :mod:`NIST_SRD46_core_db_search_tools._sql_ast`, so the literal
    substring ``__like`` inside a quoted value is no longer corrupted.
    """
    return _sa.fix_django_filters(clause, kind=kind)


def _rewrite_clause(clause: str | None, rewrites: dict, *, kind: str = "where") -> str | None:
    """AST-aware column / table rewrite.

    Replaces the legacy ``re.sub(r'\\b{key}\\b', value, clause)`` loop, which
    matched inside string literals. Rewrites are applied to identifier
    nodes only.
    """
    if not clause:
        return clause
    result = _sa.apply_rewrites(str(clause), rewrites, kind=kind)
    if result != clause:
        log.info("   -> clause rewrite: %s => %s", str(clause)[:120], result[:120])
    return result


def _rewrite_where_aliases(where: str | None) -> str | None:
    if not where:
        return where
    updated = str(where)
    for source, target in _WHERE_COLUMN_ALIASES.items():
        updated = re.sub(rf"\b{re.escape(source)}\b", target, updated)
    return updated


def _where_from_mapping(where) -> str | None:
    if not isinstance(where, dict):
        return None

    clauses = []
    for key, value in where.items():
        column = _WHERE_COLUMN_ALIASES.get(str(key).strip(), str(key).strip())
        if value is None:
            clauses.append(f"{column} IS NULL")
        elif isinstance(value, (int, float)):
            clauses.append(f"{column} = {value}")
        else:
            clauses.append(f"{column} = {_sql_quote(value)}")
    return " AND ".join(clauses)


def _pop_prefixed_int(args: dict, key: str):
    value = args.pop(key, None)
    return _extract_int(value)


def _rewrite_search_stability(args: dict) -> dict:
    _merge_legacy_order_limit(args)
    clauses = []

    metal_id = _pop_prefixed_int(args, "metal_id")
    ligand_id = _pop_prefixed_int(args, "ligand_id")
    beta_id = _pop_prefixed_int(args, "beta_definition_id")
    metal_name = args.pop("metal_name", None)
    ligand_name = args.pop("ligand_name", None)
    constant_type = args.pop("constant_type", None)
    temperature = args.pop("temperature", None)
    ionic_strength = args.pop("ionic_strength", None)

    if metal_id is not None:
        clauses.append(f"c.metal_id = {metal_id}")
    if ligand_id is not None:
        clauses.append(f"c.ligand_id = {ligand_id}")
    if beta_id is not None:
        clauses.append(f"c.beta_definition_id = {beta_id}")
    if metal_name:
        # Use EQ (not substring-LIKE) so the downstream AST metal-alias
        # expander can rewrite this as IN-list (e.g. 'cupric' →
        # ('cupric','Cu^[2+]','Cu','Cu2+','copper')). Substring on metal
        # names rarely helps — alias expansion is what the user wants.
        clauses.append(f"c.metal_name_SRD = {_sql_quote(metal_name)}")
    if ligand_name:
        clauses.append(f"c.ligand_name_SRD LIKE '%' || {_sql_quote(ligand_name)} || '%'")
    if constant_type:
        clauses.append(f"s.constant_type = {_sql_quote(constant_type)}")
    temperature = _extract_float(temperature)
    ionic_strength = _extract_float(ionic_strength)
    if temperature is not None:
        clauses.append(f"ABS(s.temperature_c - {temperature}) <= 5")
    if ionic_strength is not None:
        clauses.append(f"ABS(s.ionic_strength_mol_l - {ionic_strength}) <= 0.5")

    _append_where(args, *clauses)
    _rewrite_sql_where_query(args, _STABILITY_CLAUSE_REWRITES)
    return args


def _rewrite_search_pka(args: dict) -> dict:
    _merge_legacy_order_limit(args)
    clauses = []

    ligand_id = _pop_prefixed_int(args, "ligand_id")
    ligand_name = args.pop("ligand_name", None)
    pka_type = args.pop("pka_type", None)
    temperature = args.pop("temperature", None)
    ionic_strength = args.pop("ionic_strength", None)

    if ligand_id is not None:
        clauses.append(f"lc.ligand_id = {ligand_id}")
    if ligand_name:
        clauses.append(f"lc.ligand_name_SRD LIKE '%' || {_sql_quote(ligand_name)} || '%'")
    if pka_type:
        clauses.append(f"p.pKa_type = {_sql_quote(pka_type)}")
    temperature = _extract_float(temperature)
    ionic_strength = _extract_float(ionic_strength)
    if temperature is not None:
        clauses.append(f"ABS(p.temperature_c - {temperature}) <= 5")
    if ionic_strength is not None:
        clauses.append(f"ABS(p.ionic_strength_mol_l - {ionic_strength}) <= 0.5")

    _append_where(args, *clauses)
    _rewrite_sql_where_query(args, _PKA_CLAUSE_REWRITES)
    return args


def _rewrite_search_networks(args: dict) -> dict:
    _merge_legacy_order_limit(args)
    clauses = []

    metal_id = _pop_prefixed_int(args, "metal_id")
    ligand_id = _pop_prefixed_int(args, "ligand_id")
    metal_name = args.pop("metal_name", None)
    ligand_name = args.pop("ligand_name", None)

    if metal_id is not None:
        clauses.append(f"c.metal_id = {metal_id}")
    if ligand_id is not None:
        clauses.append(f"c.ligand_id = {ligand_id}")
    if metal_name:
        # See note in _rewrite_search_stability — EQ enables alias expansion.
        clauses.append(f"c.metal_name = {_sql_quote(metal_name)}")
    if ligand_name:
        clauses.append(f"c.ligand_name LIKE '%' || {_sql_quote(ligand_name)} || '%'")

    _append_where(args, *clauses)
    return args


def _rewrite_search_citations(args: dict) -> dict:
    _merge_legacy_order_limit(args)
    clauses = []

    shortcut = args.pop("shortcut", None)
    citation_text = args.pop("citation_text", None)
    vlm_id = _pop_prefixed_int(args, "vlm_id")

    if shortcut:
        clauses.append(f"la.shortcut = {_sql_quote(shortcut)}")
    if citation_text:
        clauses.append(f"la.citation LIKE '%' || {_sql_quote(citation_text)} || '%'")
    if vlm_id is not None:
        clauses.append(f"rv.vlm_id = {vlm_id}")

    _append_where(args, *clauses)
    return args


def _rewrite_db_count_records(args: dict) -> dict:
    table = args.get("table")
    if table is not None:
        args["table"] = _TABLE_VALUE_ALIASES.get(str(table).strip().lower(), str(table).strip())
    where = args.get("where")
    args["where"] = _where_from_mapping(where) if isinstance(where, dict) else _rewrite_where_aliases(where)
    return args


def _rewrite_db_distribution(args: dict) -> dict:
    table = args.get("table")
    if table is not None:
        args["table"] = _TABLE_VALUE_ALIASES.get(str(table).strip().lower(), str(table).strip())

    group_column = args.get("group_column")
    if group_column is not None:
        group_key = str(group_column).strip().lower()
        args["group_column"] = _GROUP_COLUMN_VALUE_ALIASES.get(group_key, str(group_column).strip())
    where = args.get("where")
    args["where"] = _where_from_mapping(where) if isinstance(where, dict) else _rewrite_where_aliases(where)
    return args


def _rewrite_db_ranked_pairs(args: dict) -> dict:
    where = args.get("where")
    if isinstance(where, dict):
        args["where"] = _where_from_mapping(where)
        log.info("   -> coerced dict to WHERE string for db_ranked_pairs.where")
    where = args.get("where")
    if where and isinstance(where, str):
        args["where"] = _rewrite_clause(where, _RANKED_PAIRS_WHERE_REWRITES, kind="where")
    return args


def _rewrite_inspect_card(args: dict) -> dict:
    prefix_id = args.get("prefix_id")
    if prefix_id is None:
        return args

    text = str(prefix_id)
    if text.startswith(("metal_", "ligand_", "vlm_")):
        return args

    if "vlm_id" in text:
        args["prefix_id"] = _coerce_prefix(prefix_id, "vlm")
    return args


def _finalize_prefix_args(tool_name: str, args: dict) -> dict:
    if tool_name == "inspect_card":
        raw = args.get("prefix_id")
        if raw is not None:
            text = str(raw)
            if text.startswith(("metal_", "ligand_", "vlm_")):
                return args
            if args.get("source_kind") == "metal":
                args["prefix_id"] = _coerce_prefix(raw, "metal")
            elif args.get("source_kind") == "ligand":
                args["prefix_id"] = _coerce_prefix(raw, "ligand")
            else:
                args["prefix_id"] = _coerce_prefix(raw, "vlm")
        args.pop("source_kind", None)
    elif tool_name == "inspect_literature":
        raw = args.get("prefix_id")
        if raw is not None:
            args["prefix_id"] = _coerce_prefix(raw, "vlm")
    return args


_RAW_SQL_REWRITES = {
    "nd.network_id":     "nd.network_db_id",
    "n.network_id":      "n.network_db_id",
    "nd.node_id":        "nd.node_db_id",
    "n.node_id":         "n.node_db_id",
    "network_id":        "network_db_id",
    "node_id":           "node_db_id",
    "eq_network_node":   "eq_node",
    "c.vlm_id":          "c.complex_system_id",
    "v.vlm_id":          "v.complex_system_id",
    "lc.vlm_id":         "lc.complex_system_id",
    "s.vlm_id":          "c.complex_system_id",
    "m.metal_name":      "m.metal_name_SRD",
    "mc.map_id":         "c.collection_id",
    "c.map_id":          "c.collection_id",
    "ref_vlm":           "ref_vlm_literature_alt",
}

_RANKED_PAIRS_WHERE_REWRITES = {
    "metal_id":    "lc.metal_id",
    "ligand_id":   "lc.ligand_id",
    "card_id":     "lc.card_id",
}

_LIST_PARAMS = {
    "exclude_groups",
    "include_groups",
    "metal_ids",
}


def normalize_tool_arguments(tool_name: str, raw_args: dict) -> dict:
    """
    Soft-parse LLM argument dictionaries into the current public tool
    signatures. This keeps the public tool surface strict while still
    tolerating minor naming drift in model outputs.
    """
    alias_map = _PARAM_ALIASES.get(tool_name, {})

    normalised: dict = {}
    for key, value in raw_args.items():
        lower_key = key.lower()
        canonical = alias_map.get(lower_key, lower_key)
        if canonical != key:
            log.info("   -> alias: %s => %s", key, canonical)
        if tool_name == "inspect_card" and lower_key in {"metal_id", "ligand_id", "vlm_id"}:
            normalised["source_kind"] = lower_key.split("_", 1)[0]
        if isinstance(value, list) and value:
            if canonical in _LIST_PARAMS:
                pass
            elif canonical.endswith("_id"):
                value = value[0]
                log.info("   -> coerced list to first element for %s.%s", tool_name, canonical)
            else:
                value = ", ".join(str(v) for v in value)
                log.info("   -> coerced list to string for %s.%s", tool_name, canonical)
        elif isinstance(value, str) and canonical in _LIST_PARAMS:
            value = [v.strip() for v in value.split(",") if v.strip()]
            log.info("   -> coerced string to list for %s.%s", tool_name, canonical)
        normalised[canonical] = value

    if tool_name == "search_stability":
        normalised = _rewrite_search_stability(normalised)
    elif tool_name in {"search_pka_values", "search_pka_ligands"}:
        normalised = _rewrite_search_pka(normalised)
    elif tool_name == "search_networks":
        normalised = _rewrite_search_networks(normalised)
    elif tool_name == "search_citations":
        normalised = _rewrite_search_citations(normalised)
    elif tool_name == "db_count_records":
        normalised = _rewrite_db_count_records(normalised)
    elif tool_name == "db_distribution":
        normalised = _rewrite_db_distribution(normalised)
    elif tool_name == "db_ranked_pairs":
        normalised = _rewrite_db_ranked_pairs(normalised)
    elif tool_name == "execute_srd46_sql":
        sql = normalised.get("sql_query")
        if sql and isinstance(sql, str):
            normalised["sql_query"] = _rewrite_clause(sql, _RAW_SQL_REWRITES, kind="sql")

    normalised = {k: v for k, v in normalised.items() if v is not None}

    # Django-style __like filter conversion. The `where` key is used by
    # the aggregate / utility tools (db_count_records, db_distribution,
    # db_ranked_pairs); the search_* tools use `sql_where_query`.
    where = normalised.get("where")
    if where and isinstance(where, str) and "__like" in where.lower():
        normalised["where"] = _fix_django_filters(where)
        log.info("   -> converted Django-style __like filter to SQL LIKE")

    sql_where_query = normalised.get("sql_where_query")
    if (
        sql_where_query
        and isinstance(sql_where_query, str)
        and "__like" in sql_where_query.lower()
    ):
        try:
            w, ob, lim = _sa.parse_sql_where_query(sql_where_query)
            new_w = _fix_django_filters(w)
            rebuilt = new_w
            if ob:
                rebuilt += f" ORDER BY {ob}"
            if lim:
                rebuilt += f" LIMIT {lim}"
            normalised["sql_where_query"] = rebuilt
        except Exception:
            normalised["sql_where_query"] = _fix_django_filters(sql_where_query)
        log.info("   -> converted Django-style __like filter to SQL LIKE")

    return _finalize_prefix_args(tool_name, normalised)
