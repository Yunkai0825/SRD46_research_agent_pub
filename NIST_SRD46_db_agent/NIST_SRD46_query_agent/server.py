#!/usr/bin/env python
"""
SRD-46 MCP Server - FastMCP
===========================
Terminal-based MCP server exposing NIST SRD-46 database search tools
via the FastMCP ``stdio`` transport.

Launch:
    python server.py            # starts on stdio (for MCP clients)
    python server.py --sse      # starts on SSE  (for web clients)
"""

from mcp.server.fastmcp import FastMCP
import json
import logging
import re
import sys
from pathlib import Path
from typing import Annotated, Literal, Optional
from pydantic import Field, StrictInt

# Keep the shared search package available for direct MCP script launches.
_REPO_ROOT = Path(__file__).absolute().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from NIST_SRD46_db_agent.NIST_SRD46_query_agent.argo_config import is_mcp_tool_enabled

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-5s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("SRD46")

# ── Import search modules ───────────────────────────────────
import NIST_SRD46_core_db_search_tools as NT

_EXECUTE_SRD46_SQL_ENABLED = is_mcp_tool_enabled("execute_srd46_sql")
_SERVER_INSTRUCTIONS = (
    "You are an expert assistant for the NIST Standard Reference Database 46 "
    "(SRD-46) — Critically Selected Stability Constants of Metal Complexes. "
    "Use the provided tools to search metals, ligands, stability constants, "
    "pKa values, equilibrium networks, literature citations, and inspect "
    "database structure where needed. "
)
if _EXECUTE_SRD46_SQL_ENABLED:
    _SERVER_INSTRUCTIONS += (
        "The capped read-only SQL execution tool is enabled for this runtime. "
    )
_SERVER_INSTRUCTIONS += (
    "All entity IDs use canonical prefixes: metal_N, ligand_N, vlm_N, "
    "beta_def_N (e.g. metal_41, ligand_5760, vlm_93847, beta_def_812). "
    "Use these prefixed IDs when passing results between tools."
)

# ═════════════════════════════════════════════════════════════
# FastMCP instance
# ═════════════════════════════════════════════════════════════
mcp = FastMCP(
    "SRD46",
    instructions=_SERVER_INSTRUCTIONS,
    log_level="ERROR",
)

# ═════════════════════════════════════════════════════════════
# Argo API configuration  (imported from argo_config.py)
# ═════════════════════════════════════════════════════════════
_NUMBER_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")
_INTEGER_RE = re.compile(r"\d+")


def _coerce_optional_float(value: Optional[float | str], field_name: str) -> Optional[float]:
    """Accept floats or numeric strings such as '25', '25 C', or '0.1 M'."""
    if value is None or isinstance(value, float):
        return value
    if isinstance(value, int):
        return float(value)
    if isinstance(value, str):
        match = _NUMBER_RE.search(value.strip())
        if match:
            return float(match.group(0))
    raise ValueError(f"{field_name} must be numeric, got {value!r}")


def _coerce_optional_int(value: Optional[int | str], field_name: str) -> Optional[int]:
    """Accept ints or SRD46-style identifier strings such as 'metal_68'."""
    if value is None or isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        match = _INTEGER_RE.search(value.strip())
        if match:
            return int(match.group(0))
    raise ValueError(f"{field_name} must be an integer identifier, got {value!r}")


def _coerce_optional_bool(value: Optional[bool | str], field_name: str) -> Optional[bool]:
    """Accept booleans or common string forms such as 'true' / 'false'."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off"}:
            return False
    raise ValueError(f"{field_name} must be boolean, got {value!r}")


def _coerce_csv_ids(value: Optional[str | list | tuple], field_name: str) -> Optional[str]:
    """Accept comma-separated IDs or SRD46-style identifier strings/lists."""
    if value is None:
        return None
    if isinstance(value, (list, tuple, set)):
        parts = list(value)
    else:
        parts = str(value).split(",")

    ids = [str(_coerce_optional_int(part, field_name)) for part in parts if str(part).strip()]
    if not ids:
        return None
    return ",".join(ids)


# ═════════════════════════════════════════════════════════════
#  MCP TOOLS — Database searches
# ═════════════════════════════════════════════════════════════

@mcp.tool(name="search_metals")
def search_metals(
    name: Optional[str] = None,
    symbol: Optional[str] = None,
    metal_id: Optional[int | str] = None,
    smiles: Optional[str] = None,
    inchi: Optional[str] = None,
    limit: int = 50,
    exclude: Optional[str] = None,
) -> str:
    """Resolve metal entities in SRD-46.

    Returns a JSON array of metal records with prefixed IDs and
    data-richness counts (`beta_def_count`, `ligand_count`, `vlm_count`).
    """
    metal_id = _coerce_optional_int(metal_id, "metal_id")
    log.info("🔧 TOOL CALL: search_metals(name=%r, symbol=%r, metal_id=%r, limit=%d)",
             name, symbol, metal_id, limit)
    rows = NT.search_metals(
        name=name,
        symbol=symbol,
        metal_id=metal_id,
        smiles=smiles,
        inchi=inchi,
        limit=limit,
        exclude=exclude,
    )
    log.info("   ↳ returned %d rows", len(rows))
    return json.dumps(rows, indent=2, default=str)


@mcp.tool(name="search_ligands")
def search_ligands(
    name: Optional[str] = None,
    formula: Optional[str] = None,
    ligand_class: Optional[str] = None,
    ligand_id: Optional[int | str] = None,
    smiles: Optional[str] = None,
    inchi: Optional[str] = None,
    limit: int = 25,
    exclude: Optional[str] = None,
    include_groups: Optional[list[str]] = None,
    exclude_groups: Optional[list[str]] = None,
) -> str:
    """Resolve ligand entities in SRD-46.

    Returns a JSON object with `results`, `total_sql_matches`,
    `excluded_by_groups`, `limit`, and `all_smiles`.
    """
    ligand_id = _coerce_optional_int(ligand_id, "ligand_id")
    log.info("🔧 TOOL CALL: search_ligands(name=%r, formula=%r, ligand_class=%r, ligand_id=%r, limit=%d)",
             name, formula, ligand_class, ligand_id, limit)
    rows = NT.search_ligands(
        name=name,
        formula=formula,
        ligand_class=ligand_class,
        ligand_id=ligand_id,
        smiles=smiles,
        inchi=inchi,
        limit=limit,
        exclude=exclude,
        include_groups=include_groups,
        exclude_groups=exclude_groups,
    )
    log.info("   ↳ returned %d rows (%d SQL matches)",
             len(rows.get("results", [])),
             rows.get("total_sql_matches", 0))
    return json.dumps(rows, indent=2, default=str)


@mcp.tool(name="build_system_catalog")
def build_system_catalog(
    metal_id: Optional[int | str] = None,
    ligand_id: Optional[int | str] = None,
    beta_definition_id: Optional[int | str] = None,
) -> str:
    """Build an overview catalog for resolved systems.

    Accepts raw numeric IDs or prefixed IDs such as `metal_41`,
    `ligand_10103`, or `beta_def_87`.
    """
    log.info("🔧 TOOL CALL: build_system_catalog(metal_id=%r, ligand_id=%r, beta_definition_id=%r)",
             metal_id, ligand_id, beta_definition_id)
    result = NT.build_system_catalog(
        metal_id=metal_id,
        ligand_id=ligand_id,
        beta_definition_id=beta_definition_id,
    )
    log.info("   ↳ catalog pairs=%d", len(result.get("pairs", [])))
    return "[CATALOG]\n" + json.dumps(result, indent=2, default=str)


@mcp.tool(name="search_stability")
def search_stability(
    sql_where_query: str = "1=1",
    ligand_similarity: bool = False,
    include_groups: Optional[list[str]] = None,
    exclude_groups: Optional[list[str]] = None,
) -> str:
    """SQL-WHERE stability search over ligandmetal_card (c) JOIN ligandmetal_stability_measured (s).
    See SQL-WHERE NOTES below for syntax + auto-normalization.

    WHERE/ORDER BY columns:
      c.: metal_id, ligand_id, beta_definition_id, beta_definition_name,
          metal_name_SRD, ligand_name_SRD, ligand_class_name, ligand_SMILES
      s.: constant_type, constant_value, temperature_c, ionic_strength_mol_l,
          reaction_type, solvent_name, electrolyte_composition

    Example: sql_where_query="c.metal_id IN (41, 61, 62) AND c.ligand_id IN (5760, 9058, 9163) ORDER BY c.metal_id, c.ligand_id"

    Agent receives: per-(metal, ligand) log_K measurements with conditions
    and equilibrium context; auto-collapses to ranges then per-pair summaries
    when oversize.
    """

    ligand_similarity = bool(_coerce_optional_bool(ligand_similarity, "ligand_similarity"))
    log.info("🔧 TOOL CALL: search_stability(sql_where_query=%r, ligand_similarity=%s)",
             sql_where_query[:200], ligand_similarity)
    rows = NT.search_stability(
        sql_where_query=sql_where_query,
        ligand_similarity=ligand_similarity,
        include_groups=include_groups,
        exclude_groups=exclude_groups,
    )
    log.info("   ↳ returned %d rows", len(rows))
    return json.dumps(rows, indent=2, default=str)


@mcp.tool(name="search_pka_values")
def search_pka_values(
    sql_where_query: str = "1=1",
    ligand_similarity: bool = False,
    include_groups: Optional[list[str]] = None,
    exclude_groups: Optional[list[str]] = None,
) -> str:
    """Value-centric pKa search over ligand_card (lc) JOIN ligand_pka_measured (p).
    See SQL-WHERE NOTES below for syntax + auto-normalization.

    WHERE/ORDER BY columns:
      lc.: ligand_id, ligand_name_SRD, ligand_class_name, formula, ligand_SMILES
      p.:  pKa, pKa_type, temperature_c, ionic_strength_mol_l, solvent_name,
           electrolyte, quality

    Example: sql_where_query="lc.ligand_id IN (5760, 9058, 9163) AND p.pKa BETWEEN 4 AND 9"

    Agent receives: pKa measurements bucketed into 0.5-unit bands with
    conditions and metal-binding context on each side; bands trimmed to
    samples + stats when oversize.
    """
    ligand_similarity = bool(_coerce_optional_bool(ligand_similarity, "ligand_similarity"))
    log.info("🔧 TOOL CALL: search_pka_values(sql_where_query=%r, ligand_similarity=%s)",
             sql_where_query[:200], ligand_similarity)
    rows = NT.search_pka_values(
        sql_where_query=sql_where_query,
        ligand_similarity=ligand_similarity,
        include_groups=include_groups,
        exclude_groups=exclude_groups,
    )
    log.info("   ↳ returned %d rows", len(rows))
    return json.dumps(rows, indent=2, default=str)


@mcp.tool(name="search_pka_ligands")
def search_pka_ligands(
    sql_where_query: str = "1=1",
    ligand_similarity: bool = False,
    include_groups: Optional[list[str]] = None,
    exclude_groups: Optional[list[str]] = None,
) -> str:
    """Ligand-centric pKa search over ligand_card (lc) JOIN ligand_pka_measured (p).
    Same SQL surface + columns as search_pka_values. See SQL-WHERE NOTES below.

    Example: sql_where_query="lc.ligand_name_SRD LIKE '%oxalic%'"

    Agent receives: one row per ligand with its full protonation ladder,
    pKa transitions, and metal-binding counts per state. Use for "all pKas
    of these ligands" rather than "all measurements in a pKa range".
    """
    ligand_similarity = bool(_coerce_optional_bool(ligand_similarity, "ligand_similarity"))
    log.info("🔧 TOOL CALL: search_pka_ligands(sql_where_query=%r, ligand_similarity=%s)",
             sql_where_query[:200], ligand_similarity)
    rows = NT.search_pka_ligands(
        sql_where_query=sql_where_query,
        ligand_similarity=ligand_similarity,
        include_groups=include_groups,
        exclude_groups=exclude_groups,
    )
    log.info("   ↳ returned %d rows", len(rows))
    return json.dumps(rows, indent=2, default=str)


@mcp.tool(name="search_networks")
def search_networks(
    sql_where_query: str = "1=1",
    ligand_similarity: bool = False,
) -> str:
    """SQL-WHERE equilibrium-network search. See SQL-WHERE NOTES below.
    Note: ``LIMIT`` applies to *distinct networks* (all node rows for matching
    networks are returned).

    WHERE/ORDER BY columns:
      c.:  metal_id, ligand_id, metal_name, ligand_name
      n.:  network_db_id, node_count, edge_count
      nd.: vlm_id, beta_definition_id, constant_type, constant_value
      m.:  condition_temp_min/max, condition_ionic_min/max

    Example: sql_where_query="c.metal_id IN (41, 61) AND c.ligand_id IN (5760, 9058)"

    Agent receives: per-system equilibrium networks with summary stats,
    reaction lookup, and reference-state details; collapses to summary only
    when oversize.
    """

    ligand_similarity = bool(_coerce_optional_bool(ligand_similarity, "ligand_similarity"))
    log.info("🔧 TOOL CALL: search_networks(sql_where_query=%r, ligand_similarity=%s)",
             sql_where_query[:200], ligand_similarity)
    rows = NT.search_networks(
        sql_where_query=sql_where_query,
        ligand_similarity=ligand_similarity,
    )
    log.info("   ↳ returned %d rows", len(rows))
    return json.dumps(rows, indent=2, default=str)


@mcp.tool(name="search_citations")
def search_citations(
    sql_where_query: str = "1=1",
) -> str:
    """SQL-WHERE literature citation search. See SQL-WHERE NOTES below.

    WHERE/ORDER BY columns:
      la.: literature_alt_id, shortcut, citation
      rv.: vlm_id

    Example: sql_where_query="rv.vlm_id IN (93606, 93607, 93847) ORDER BY la.citation LIMIT 20"

    Agent receives: one row per distinct citation with VLM grouping counts.
    """
    log.info("🔧 TOOL CALL: search_citations(sql_where_query=%r)",
             sql_where_query[:200])
    rows = NT.search_citations(sql_where_query=sql_where_query)
    log.info("   ↳ returned %d rows", len(rows))
    return json.dumps(rows, indent=2, default=str)


@mcp.tool(name="inspect_card")
def inspect_card(prefix_id: str) -> str:
    """Deep inspection of one prefixed entity ID.

    Supported IDs: `metal_N`, `ligand_N`, and `vlm_N`.
    """
    log.info("🔧 TOOL CALL: inspect_card(prefix_id=%r)", prefix_id)
    result = NT.inspect_card(prefix_id=prefix_id)
    log.info("   ↳ returned keys=%s", sorted(result.keys()))
    return json.dumps(result, indent=2, default=str)


@mcp.tool(name="inspect_literature")
def inspect_literature(prefix_id: str) -> str:
    """Return all citation rows for one `vlm_N` prefixed ID.

    Use this after `search_citations` when you need the full citation set
    attached to a specific VLM measurement.
    """
    log.info("🔧 TOOL CALL: inspect_literature(prefix_id=%r)", prefix_id)
    result = NT.inspect_literature(prefix_id=prefix_id)
    log.info("   ↳ citations=%d", len(result.get("citations", [])))
    return json.dumps(result, indent=2, default=str)


@mcp.tool(name="db_count_records")
def db_count_records(
    table: str,
    where: Optional[str] = None,
) -> str:
    """Count rows in an allowed SRD-46 table, optionally filtered.

    Agent receives: a single integer ``count`` for the table (+ filter).
    """
    log.info("🔧 TOOL CALL: db_count_records(table=%r, where=%r)", table, where)
    result = NT.db_count_records(table=table, where=where)
    return json.dumps(result, indent=2, default=str)


@mcp.tool(name="db_distribution")
def db_distribution(
    table: str,
    group_column: str,
    where: Optional[str] = None,
    limit: int = 25,
) -> str:
    """Compute a grouped value distribution for an allowed table/column.

    Agent receives: a ranked table of ``group_value`` → ``row_count`` for the
    grouped column (primary: counts per distinct value, top ``limit`` only).
    """
    log.info("🔧 TOOL CALL: db_distribution(table=%r, group_column=%r, where=%r, limit=%d)",
             table, group_column, where, limit)
    result = NT.db_distribution(
        table=table,
        group_column=group_column,
        where=where,
        limit=limit,
    )
    return json.dumps(result, indent=2, default=str)


@mcp.tool(name="db_ranked_pairs")
def db_ranked_pairs(
    rank_by: str = "ligands_per_metal",
    limit: int = 20,
    where: Optional[str] = None,
) -> str:
    """Rank metals or ligands by partner count / measurement count.

    Agent receives: a ranked table of pair-coverage stats (primary: entity
    name/id + the ranking metric chosen by ``rank_by``, e.g.
    ``ligands_per_metal``; truncated to ``limit`` rows).
    """
    log.info("🔧 TOOL CALL: db_ranked_pairs(rank_by=%r, limit=%d, where=%r)",
             rank_by, limit, where)
    result = NT.db_ranked_pairs(rank_by=rank_by, limit=limit, where=where)
    return json.dumps(result, indent=2, default=str)


@mcp.tool(name="get_table_schema")
def get_table_schema(
    table_name: str,
    database: str = "cards",
) -> str:
    """Return schema information for a cards/equilibrium/literature table."""
    log.info("🔧 TOOL CALL: get_table_schema(table=%r, db=%r)", table_name, database)
    result = NT.get_table_schema(table_name=table_name, database=database)
    log.info("   ↳ returned %d columns", len(result))
    return json.dumps(result, indent=2, default=str)


if _EXECUTE_SRD46_SQL_ENABLED:
    get_table_schema.__doc__ = (
        "Return schema information for a cards/equilibrium/literature table.\n\n"
        "    Use this before `execute_srd46_sql` or when a domain tool cannot answer."
    )
else:
    get_table_schema.__doc__ = (
        "Return schema information for a cards/equilibrium/literature table.\n\n"
        "    Use this when a domain tool cannot answer."
    )


def execute_srd46_sql(
    sql_query: str,
    task_description: Optional[str] = None,
    column_legend: Optional[dict] = None,
    attach_equilibrium: bool = False,
    attach_literature: bool = False,
) -> str:
    """** Accepts full read-only SQL cross-database SRD-46 query commands. Advanced tool.**

    Most versatile and efficient query path. Handle more complicated cross-db composite queries than 
    ``search_*`` tools (multi-table joins, self-joins, calcs, window functions, custom aggregations,
    etc.). Best used once you are (1) already familiar with all the dbs, and (2) acknowledging how 
    those data values scientifically constrain each other in chemistry problems.

    REQUIRED:
      • ``task_description`` (>= 40 chars) — ONE BRIEF SENTENCE saying what
        chemistry question this SQL answers. Be terse and to the point;
        do NOT restate the SQL in prose.
      • ``column_legend`` — a dict mapping every output column (including
        SELECT aliases such as ``logK_Fe3`` and computed columns such as
        ``delta_logK``) to a chemistry-aware string describing (1) source
        table.column or formula, (2) filter/join, (3) physical meaning +
        units + species / protonation / oxidation state, and (4) for
        computed columns the formula AND its interpretation.
    """
    attach_equilibrium = bool(_coerce_optional_bool(attach_equilibrium, "attach_equilibrium"))
    attach_literature = bool(_coerce_optional_bool(attach_literature, "attach_literature"))
    log.info(
        "🔧 TOOL CALL: execute_srd46_sql(eq=%s, lit=%s, task=%r, legend_keys=%s)\n   SQL: %s",
        attach_equilibrium, attach_literature,
        (task_description or "")[:80],
        list(column_legend.keys()) if isinstance(column_legend, dict) else None,
        sql_query[:200],
    )
    result = NT.execute_srd46_sql(
        sql_query=sql_query,
        task_description=task_description,
        column_legend=column_legend,
        attach_equilibrium=attach_equilibrium,
        attach_literature=attach_literature,
    )
    if isinstance(result, dict) and "error" in result:
        log.warning("   ↳ rejected: %s", result["error"][:120])
    else:
        log.info("   ↳ returned %d rows", result.get("row_count", 0) if isinstance(result, dict) else 0)
    return json.dumps(result, indent=2, default=str)


if _EXECUTE_SRD46_SQL_ENABLED:
    execute_srd46_sql = mcp.tool(name="execute_srd46_sql")(execute_srd46_sql)
else:
    log.info("Tool execute_srd46_sql blocked by config; omitting from MCP registration.")


@mcp.tool(name="search_similar_ligands")
def search_similar_ligands(
    ligand_id: Optional[StrictInt | str] = None,
    ligand_name: Optional[str] = None,
    top_k: Annotated[int, Field(strict=True, ge=1, le=100)] = 10,
    metal_ids: Optional[str | list[StrictInt | str]] = None,
    metric: Literal["tanimoto_morgan", "tanimoto_maccs", "tversky_query_in_target", "tversky_target_in_query"] = "tanimoto_morgan",
    min_similarity: Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)] = 0.0,
) -> str:
    """Find similar ligands, excluding self and NULL selected scores.

    metric: tanimoto_morgan (default), tanimoto_maccs,
    tversky_query_in_target, or tversky_target_in_query. Directional
    Tversky uses alpha=0.9/beta=0.1; query-in-target penalizes query-only
    bits more strongly, and target-in-query reverses the direction.
    top_k must be 1..100; min_similarity is an inclusive [0,1] threshold.
    Scores describe fingerprint overlap, not binding affinity or an exact
    substructure match. metal_ids filters map coverage, not structure ranks.
    Legacy similarity_score remains Morgan; ranking_score uses metric.
    """
    metal_id_list = metal_ids
    if isinstance(metal_ids, str):
        metal_id_list = [value.strip() for value in metal_ids.split(",") if value.strip()]
    result = NT.search_similar_ligands(
        ligand_id=ligand_id,
        ligand_name=ligand_name,
        top_k=top_k,
        metal_ids=metal_id_list,
        metric=metric,
        min_similarity=min_similarity,
    )
    log.info("Similarity tool returned %d ligands for metric=%s", len(result.get("similar_ligands", [])), metric)
    return json.dumps(result, indent=2, default=str)


# FastMCP's default argument model ignores extra keys. For this tool, reject
# misspelled filters rather than silently executing a different search. Update
# both runtime validation and the published schema from this same model.
_similarity_tool = mcp._tool_manager.get_tool("search_similar_ligands")
_similarity_args = _similarity_tool.fn_metadata.arg_model
_similarity_args.model_config["extra"] = "forbid"
_similarity_args.model_rebuild(force=True)
_similarity_tool.parameters = _similarity_args.model_json_schema(by_alias=True)
del _similarity_args, _similarity_tool


# ═════════════════════════════════════════════════════════════
#  MCP TOOL — Pre-plan Decision (triage)
# ═════════════════════════════════════════════════════════════

from NIST_SRD46_db_agent.NIST_SRD46_query_agent.SRD46_tools.strategy_planner import preplan_decision as _preplan_decision


@mcp.tool(name="0_preplan_decision")
def preplan_decision(question: str) -> str:
    """Fast triage: identify task type, metals, and ligands of interest.

    Call this FIRST — before any other tool.  It uses a lightweight LLM
    call to decide:
      • task_type  — lookup, comparison, pKa, citation, provenance,
                     exploration, multi-step
      • metals     — metal names/symbols to search in L0
      • ligands    — ligand names to search in L0
      • notes      — one-sentence special instructions

    The agent then uses these to guide its L0 search_metals /
    search_ligands calls.

    Parameters
    ----------
    question : the user's original chemistry question

    Returns JSON with keys: task_type, metals, ligands, notes, _meta
    """
    log.info("🔧 TOOL CALL: preplan_decision(question=%.80s…)", question)
    result = _preplan_decision(question=question)
    log.info("   ↳ preplan returned %d chars", len(result))
    return result


# ═════════════════════════════════════════════════════════════
#  MCP TOOL — Strategy Planner
# ═════════════════════════════════════════════════════════════

from NIST_SRD46_db_agent.NIST_SRD46_query_agent.SRD46_tools.strategy_planner import plan_search_strategy as _plan_search_strategy


@mcp.tool(name="0_plan_search_strategy")
def plan_search_strategy(
    question: str,
    context: str = "",
    revision_note: str = "",
    system_prompt_module: str = "",
) -> str:
    """Ask the strategy planner to design (or revise) a search plan.

    The planner knows all SRD-46 tools, data schemas, domain pitfalls,
    and common workflow patterns.  It returns a structured JSON strategy
    prefixed with ``[PLAN]`` that the agent can follow, edit, or reject.

    The ``[PLAN]`` prefix makes the plan **incompressible** while it is
    still active.  When the agent delivers a final answer the system
    promotes it to ``[PLAN:DONE]``, making it compressible for future
    turns (useful in multi-plan conversations).

    **First call** — pass the user's question.  The planner produces a
    fresh strategy.

    **Revision** — pass the previous plan in ``context`` and describe
    what to change in ``revision_note``.  The planner updates only the
    affected steps.

    Parameters
    ----------
    question : the user's original chemistry question
    context  : prior tool results, catalog JSON, or the previous plan
    revision_note : if non-empty, requests edits to the plan in context
    system_prompt_module : optional supplemental planner/evaluator system
        instructions.  These are appended below the established prompts and
        cannot replace their higher-priority contract.  Omit this argument to
        retain the default prompts exactly.

    Returns a plain-text advisory prefixed with [PLAN] that suggests
    an approach, pitfalls to watch, and success criteria.  The agent
    decides exact tool calls and parameters — the plan guides, not commands.
    """
    log.info("🔧 TOOL CALL: plan_search_strategy(question=%.80s…, revision=%s)",
             question, bool(revision_note))
    result = _plan_search_strategy(
        question=question,
        context=context,
        revision_note=revision_note,
        system_prompt_module=system_prompt_module,
    )
    log.info("   ↳ planner returned %d chars", len(result))
    return result


# ═════════════════════════════════════════════════════════════
#  WHERE-clause normalization manual — appended to every tool that
#  accepts a free-form WHERE / SQL string so the agent always sees the
#  same warning. Single source of truth lives in
#  ``NIST_SRD46_core_db_search_tools._search_helpers.WHERE_NORMALIZATION_NOTES``.
# ═════════════════════════════════════════════════════════════

from NIST_SRD46_core_db_search_tools._search_helpers import WHERE_NORMALIZATION_NOTES as _WN

_WHERE_NOTE_FUNCTIONS = [
    search_stability,
    search_pka_values,
    search_pka_ligands,
    search_networks,
    db_count_records,
    db_distribution,
    db_ranked_pairs,
]
_REFRESH_DOC_TOOL_NAMES = [
    "get_table_schema",
    "search_stability",
    "search_pka_values",
    "search_pka_ligands",
    "search_networks",
    "db_count_records",
    "db_distribution",
    "db_ranked_pairs",
]

if _EXECUTE_SRD46_SQL_ENABLED:
    _WHERE_NOTE_FUNCTIONS.append(execute_srd46_sql)
    _REFRESH_DOC_TOOL_NAMES.append("execute_srd46_sql")

for _fn in _WHERE_NOTE_FUNCTIONS:
    _fn.__doc__ = (_fn.__doc__ or "").rstrip() + "\n\n" + _WN

# Best-effort: also refresh the description on any FastMCP tool object
# that already cached the docstring at decoration time.
try:
    _tool_registry = getattr(mcp, "_tool_manager", None) or getattr(mcp, "tool_manager", None)
    _tools = getattr(_tool_registry, "_tools", None) if _tool_registry else None
    if isinstance(_tools, dict):
        for _name in _REFRESH_DOC_TOOL_NAMES:
            _tool = _tools.get(_name)
            if _tool is None:
                continue
            _fn = globals().get(_name)
            if _fn and _fn.__doc__:
                # FastMCP exposes description under `description` (and sometimes
                # caches a parsed version on the underlying schema). Best-effort
                # update; ignore if attribute is read-only.
                try:
                    _tool.description = _fn.__doc__
                except Exception:
                    pass
except Exception as _e:
    log.debug("MCP tool description refresh skipped: %s", _e)

del _fn, _REFRESH_DOC_TOOL_NAMES, _WHERE_NOTE_FUNCTIONS, _WN


# ═════════════════════════════════════════════════════════════
#  Entry point
# ═════════════════════════════════════════════════════════════

if __name__ == "__main__":
    transport = "sse" if "--sse" in sys.argv else "stdio"
    mcp.run(transport=transport)
