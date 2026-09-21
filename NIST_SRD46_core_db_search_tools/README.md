# SRD-46 Search Tools & Result Compactors

> NIST Standard Reference Database 46 — Critically Selected Stability Constants of Metal Complexes

This root package is shared by the query agent, analysis agent, browser, and generic query engine. Search implementations and result compactors live here once; agent-specific planning and runtime code remain in the query-agent package. Both `inspect_card` and `inspect_literature` return the full citation list for a VLM. Stability results retain ligand-similarity scores, and stability/network summaries retain concrete measurement IDs.

## Architecture

```
 Agent calls MCP tool
       |
       v
 NIST_SRD46_core_db_search_tools/<tool>.py          SQL query + enrichment
       |
       v
 raw JSON (list[dict] or dict)   Full database rows with prefixed IDs
       |
       v
 _tools_results_compactors/      Hardcoded per-tool markdown renderer
       |
       v
 compact markdown (str)          Agent-readable, tiered by output length
       |
       v
 _agentic_ref_id_extractor.py    Extract all entity IDs (evaluation only)
```

---

## Directory Layout

```
NIST_SRD46_core_db_search_tools/
|-- __init__.py                          Public API exports (16 search tools + helpers)
|-- _db_connection.py                    SQLite context managers (4 databases)
|-- _sql_ast.py                          sqlglot-AST WHERE/SQL normalizer
|                                        (validate_read_only, resolve_prefixed_ids,
|                                         apply_rewrites, fix_django_filters,
|                                         expand_ligand_id_with_similar,
|                                         extract_ligand_from_where, normalize_clause)
|-- _search_helpers.py                   WHERE validation + similarity-expansion
|                                        wrappers over `_sql_ast`; HARD_LIMIT=200
|
|-- entity_search.py                     search_metals, search_ligands
|-- stability_search.py                  search_stability
|-- network_search.py                    search_networks
|-- pka_search.py                        search_pka_values, search_pka_ligands
|-- citation_search.py                   search_citations
|-- card_inspect.py                      inspect_card (all VLM citations), inspect_literature
|-- system_catalog.py                    build_system_catalog
|-- similarity_search.py                 search_similar_ligands
|-- aggregate_and_sql.py                 db_count_records, db_distribution,
|                                        db_ranked_pairs, get_table_schema,
|                                        execute_srd46_sql
|
|-- _normalization_helpers/
|   |-- id_prefixer.py                   Canonical prefix system (metal_41, vlm_93847, ...)
|   |-- metal_resolution.py              Name expansion (copper -> Cu^[2+], ferric -> Fe3+)
|   |-- ligand_resolution.py             PubChemPy + RDKit chemical canonicalization
|   `-- functional_group_catalog.py      25+ SMARTS patterns for substructure filtering
|
`-- _tools_results_compactors/
    |-- __init__.py                       Auto-wiring via _compacts_tools tags
    |-- _compactor_helpers.py             Shared: _cell, _esc, _ctype, _num, _range_str
    |-- _agentic_ref_id_extractor.py      Per-tool entity ID extraction
    |-- _sql_entity_enricher.py           Gap-only entity enrichment for execute_srd46_sql
    |                                     (metal_id / ligand_id / beta_definition_id →
    |                                      missing canonical fields, pKa brackets, equation_str)
    |-- entity_search_compactors.py       search_metals, search_ligands
    |-- stability_compactor.py            search_stability (3 tiers)
    |-- network_compactor.py              search_networks (3 tiers)
    |-- pka_values_compactor.py           search_pka_values (2 tiers)
    |-- pka_ligands_compactor.py          search_pka_ligands (1 tier, flat)
    |-- citation_compactor.py             search_citations (1 tier, flat)
    |-- similar_ligand_compactor.py       search_similar_ligands + diff histogram
    |-- system_catalog_compactor.py       build_system_catalog (3 tiers)
    |-- inspect_card_compactor.py         inspect_card (3 card types; all VLM citations)
    |-- inspect_literature_compactor.py   inspect_literature
    |-- preplan_compactor.py              0_preplan_decision
    |-- sql_query_compactor.py            execute_srd46_sql (<tool_context> + auto-enrichment +
    |                                     constant-column hoisting)
    `-- aggregate_compactor.py            db_count/distribution/ranked/schema
```

---

## Databases

| Database | Size | Content |
|----------|------|---------|
| `srd46_cards.db` | 158 MB | metal_card, ligand_card, ligandmetal_card, stability, pKa, brackets |
| `srd46_equilibrium_maps.db` | 28 MB | eq_node, eq_network, eq_map, eq_map_collection |
| `srd46_literature.db` | 44 MB | ref_vlm_literature_alt, ref_literature_alt, ref_author |
| `srd46_ligand_fingerprints.db` | 1 GB | Pre-computed Morgan/MACCS Tanimoto/Tversky similarities |

---

## Prefixed ID System

All tool outputs use canonical prefixed IDs (never raw integers).
Tools also accept prefixed IDs as input (auto-resolved to raw ints in WHERE clauses).

| DB Column | Prefix | Example |
|-----------|--------|---------|
| `metal_id` | `metal_` | `metal_41` |
| `ligand_id` | `ligand_` | `ligand_5760` |
| `vlm_id` | `vlm_` | `vlm_93847` |
| `source_vlm_id` | `vlm_` | `vlm_100001` |
| `example_vlm_id` | `vlm_` | `vlm_93847` |
| `beta_definition_id` | `beta_def_` | `beta_def_812` |
| `pka_id` | `pka_` | `pka_1` |
| `map_id` | `ref_eq_map_` | `ref_eq_map_14` |
| `network_db_id` | `ref_eq_net_` | `ref_eq_net_86` |
| `network_id` | `ref_eq_net_` | `ref_eq_net_3` |
| `node_id` | `eq_node_` | `eq_node_5` |
| `literature_alt_id` | `lit_` | `lit_4321` |

---

## WHERE-Clause Normalization & Similarity Fallback

All search tools that accept a free-form `where=` parameter route the
clause through a single AST-based pipeline (`_sql_ast.py`, backed by
sqlglot). String literals are never touched — only identifiers, columns,
and operators are rewritten — so values containing reserved words,
underscores, or operator symbols are preserved verbatim.

### End-to-end flow (agent string → SQL → rows)

```
Agent JSON tool-call
        │  {"name":"search_stability","arguments":{"where":"metal_name_SRD = 'cupric'"}}
        ▼
server.py (FastMCP)  ─►  decodes JSON, dispatches to @mcp.tool wrapper
        │
        ▼
tool_arg_normalizer.normalize_tool_arguments(tool, args)
        │   • structured kwargs → WHERE fragments
        │   • aliases / nicknames normalized
        │   • _append_where merges fragments with " AND "
        │   (still pure string)
        ▼
NIST_SRD46_core_db_search_tools/<tool>.py
        │   calls _search_helpers.validate_clause(where, kind="where")
        ▼
_sql_ast.normalize_clause(text, kind="where")    ── string → AST → string
        │   1. apply_rewrites          (s.value → s.constant_value)
        │   2. fix_django_filters      (col__like → col LIKE)
        │   3. normalize_chem_literals (Cu2+ → Cu^[2+])
        │   4. expand_metal_name_literals
        │      (EQ → IN ('cupric','copper','Cu^[2+]','Cu','Cu2+'))
        │   5. resolve_prefixed_ids    (metal_41 → 41)
        │   6. validate_read_only      (reject Insert/Drop/Attach…)
        │   7. expand_where_with_similar  (ligand 0-row fallback)
        │   each pass walks the tree and only mutates the NODE TYPES
        │   it cares about; string literals are never touched.
        ▼
Tool builds final SELECT, runs sqlite3.execute on srd46_cards.db
        ▼
list[dict] → _tools_results_compactors/<tool>.py → compact markdown
        ▼
Returned to the agent (alias expansion is invisible to the agent)
```

Both raw `where=` and structured kwargs (e.g. `metal_name="cupric"`)
funnel into the same `normalize_clause`, so the alias expansion above
fires for either input.

### Ligand & metal-ligand parsing — the parallel paths

The pipeline above handles SQL fragments. There are two other paths
that look like SQL but go through name-resolution layers first:

- **`search_metals(name=…)` / `search_ligands(name=…)`** — name-resolution
  entry tools that return canonical prefixed IDs.
  - Metals: `_expand_metal_name(name)` (Latin / English / oxidation-state
    / DB-format / bare symbol) joined with `OR` against `metal_name`
    + `metal_name_SRD`. Same alias set the AST `expand_metal_name_literals`
    pass uses, so name-tool results and `where=` literals match the
    same rows.
  - Ligands: `_resolve_ligand_identifiers(name)` tries InChI →
    SMILES (RDKit) → PubChemPy network lookup → canonical InChI.
    Falls back to substring `LIKE` if RDKit / PubChemPy unavailable.

- **Structured kwargs on `search_stability` / `search_networks`** —
  `metal_name="cupric"` and `ligand_name="glycine"` are translated by
  `tool_arg_normalizer` into WHERE fragments and joined with `AND`,
  then sent through the same `normalize_clause` pipeline:
  - Metal kwarg → `c.metal_name_SRD = 'cupric'` (EQ — alias-expanded
    by the AST pass to an `IN`-list).
  - Ligand kwarg → `c.ligand_name_SRD LIKE '%glycine%'` (substring,
    deliberately; ligand names too varied to alias-expand at parse time).

#### Why metal expansion is eager but ligand-name expansion is lazy

RDKit (local, sub-millisecond) and PubChemPy (HTTP to NCBI, 200 ms – 3 s
plus ~5 req/s rate limits) are treated very differently:

| | Metal names | SMILES / InChI | Ligand common names |
|---|---|---|---|
| Pass | `expand_metal_name_literals` (AST) | `normalize_chem_literals` (AST, RDKit) | 0-row similarity fallback |
| Source | hand-curated `metal_resolution.py` | RDKit canonical | PubChemPy → RDKit → fingerprint DB |
| Cost | microseconds | sub-millisecond | 200 ms – 3 s (network), rate-limited |
| Strategy | **eager** — every WHERE | **eager** — every WHERE | **lazy** — only on 0 rows, once per query |
| Visible to agent | invisible | invisible | visible: `similarity_score` column |

RDKit is fast and runs eagerly; PubChem is the network call we
explicitly avoid in the per-WHERE hot path. PubChemPy is invoked at
most once per query, lazily, to seed the similarity lookup when an
exact match returned zero rows; the actual fan-out then happens in
local SQLite (`srd46_ligand_fingerprints.db`, pre-computed Morgan /
MACCS / Tversky). RDKit alone can't widen `'EDTA'` into an IN-list
because it needs SMILES/InChI as input and returns one canonical form,
not a list of aliases — that's why the name → structure step lives in
the lazy path, not the AST.

#### Ligand-similarity 0-row fallback (wired into `search_stability`, `search_pka_values`, `search_networks`)

```
zero rows from the exact query?
        │
        ▼
_ast_extract_ligand_info(where_tree)        ← pulls the first ligand_id = N
        │                                     or ligand_name [LIKE|=] '…'
        ▼
seed → _fetch_top_similar(seed, k)           ← srd46_ligand_fingerprints.db
        │                                     (Morgan / MACCS / Tversky)
        ▼
expand_ligand_id_with_similar(where, ids)
        │   replaces  ligand_id = N         with  ligand_id IN (N, N1, N2, …)
        │   appends   OR c.ligand_id IN (…) to a ligand_name LIKE branch
        ▼
re-run SELECT — rows now carry `similarity_score` so the agent can
sort / filter the fuzzy matches explicitly.
```

#### How metal-ligand combined queries land in SQLite

All three filter paths (raw WHERE, structured kwargs, name-tool IDs)
end up running essentially the same JOIN — only the WHERE composition
differs:

```sql
SELECT s.constant_value, s.constant_type, c.metal_name_SRD,
       c.ligand_name_SRD, c.metal_id, c.ligand_id, …
  FROM stability s
  JOIN ligandmetal_card c USING (complex_id)
 WHERE <normalized predicate>
 ORDER BY <normalized order_by>
 LIMIT  <hard-capped at HARD_LIMIT=200>
```

`ligandmetal_card c` is the central denormalized table — every
(metal_id, ligand_id) pairing that appears in a stability or pKa row
has a `c` row with the canonical `c.metal_name_SRD`,
`c.ligand_name_SRD`, SMILES, InChI. That's why `c.` is the alias the
AST passes preserve verbatim, and why the per-tool column-rewrite
tables in `tool_arg_normalizer.py` map `s.metal_id` / `m.metal_id` to
`c.metal_id` before the AST takes over.

### Pipeline (per WHERE clause)

| Step | Function | Effect |
|------|----------|--------|
| 1. Column aliasing | `apply_rewrites` | `value` -> `s.constant_value`, etc. (per-tool maps in `tool_arg_normalizer.py`) |
| 2. Django-style filters | `fix_django_filters` | `col__like='%X%'` -> `col LIKE '%X%'` |
| 3. Chem-literal canonicalization | `normalize_chem_literals` | RHS literals on chemistry columns (`metal_name_SRD`, `symbol`, `*_smiles`, `*_inchi`) folded to canonical form. Composite WHEREs (AND/OR/NOT, `IN (...)`, `NOT IN`, `LIKE`, `<>`, sub-SELECTs) are walked node-by-node so every comparison is normalized independently. |
| 4. Metal-name alias expansion | `expand_metal_name_literals` | `metal_name_SRD = 'copper(II)'` -> `metal_name_SRD IN ('copper(II)', 'copper', 'Cu2+', 'Cu^[2+]')` (via `_expand_metal_name`). NEQ becomes `NOT IN`; IN-lists are expanded element-wise. `LIKE 'cupric'` (no `%`/`_` wildcards) is treated as `=` and expanded the same way; `LIKE '%cupric%'` (with wildcards) is left as a substring match. `LOWER(col)` / `UPPER(col)` wrappers on the LHS are preserved (expansion terms are case-transformed to match). Table aliases (`c.metal_name_SRD`, `m.metal_name_SRD`, ...) flow through verbatim. Closes the GPT-5.4 *"try once, give up"* failure mode where English oxidation-state names returned 0 rows. |
| 5. Prefixed-ID resolution | `resolve_prefixed_ids` | `metal_41` -> `41`, `ligand_5760` -> `5760`, `beta_def_812` -> `812` |
| 6. Read-only validation | `validate_read_only` | Rejects DDL/DML node types at any depth; allows `EXISTS (SELECT …)` and `IN (SELECT …)` sub-SELECTs |
| 7. Ligand-similarity expansion | `expand_where_with_similar` | (see below) |

### Ligand-similarity fallback (the "no exact hits → show similar ligands" path)

Wired into `search_stability`, `search_pka_values`, and `search_networks`.

1. **Eager mode** (`ligand_similarity=True` arg): the WHERE clause is
   widened *before* execution by replacing `ligand_id = N` with
   `ligand_id IN (N, N1, N2, …)`, where `N1, N2, …` are the top-K most
   similar ligands from `srd46_ligand_fingerprints.db`. If the WHERE
   uses `ligand_name LIKE …` instead, the expansion is appended as
   `OR c.ligand_id IN (…)`.
2. **0-row fallback**: if the user did *not* request `ligand_similarity`
   but the exact query returned no rows, the same expansion is retried
   automatically. The agent sees the similar-ligand rows tagged with a
   `similarity_score` column.

The ligand criterion is detected by `extract_ligand_from_where`, which
walks the AST looking for `ligand_id = <int>` (raw or prefixed
`ligand_NNN`) and `ligand_name [LIKE|=] '...'` predicates. Sub-SELECTs
in the same WHERE do not interfere with detection.

### Chemistry alias normalization

| Surface | What it normalizes | Helper |
|---------|---------------------|--------|
| `search_metals(name=…)`, `search_ligands(name=…)` | English names + oxidation state + SMILES + InChI -> search variants / canonical InChI | `_expand_metal_name`, `_resolve_ligand_identifiers` (PubChemPy + RDKit) |
| Browser free-text `q=` boxes (7 search routes) | metal-charge shorthand (`Cu2+`/`Cu²⁺`/`Cu+2`/`Cu^2+`) -> `Cu^[2+]` before `LIKE '%q%'` | `_normalization_helpers/chem_query.py::normalize_chem_query` (re-exported by browser `search_utils.py`) |
| Free-form `where=` literals on **metal-name columns** | charge shorthand -> canonical (`normalize_chem_literals`) **plus** English/oxidation-state/Latin alias expansion (`expand_metal_name_literals`) — `'copper(II)'`, `'cupric'`, `'Cu2+'` all match `'Cu^[2+]'` rows | `_sql_ast.normalize_chem_literals` + `_sql_ast.expand_metal_name_literals` |
| Free-form `where=` literals on **SMILES / InChI columns** | RDKit canonical SMILES / InChI | `_sql_ast.normalize_chem_literals` |
| Free-form `where=` literals on **ligand-name columns** | **NOT** PubChem-resolved at WHERE time (too slow). Use `search_ligands(name=…)` first to get IDs, OR rely on the 0-row similarity fallback (which DOES call PubChem internally). | — |
| Free-form `where=` literals on **non-chemistry columns** (`note`, `comment`, …) | **untouched** — values like `'observed Cu2+ binding'` round-trip verbatim | — |

#### Columns recognised by `normalize_chem_literals` and `expand_metal_name_literals`

| Helper | Columns | Behaviour |
|--------|---------|-----------|
| Metal-charge folding (`normalize_chem_literals`) | `metal_name`, `metal_name_SRD`, `symbol`, `metal_symbol` | `Cu2+`/`Cu²⁺`/`Cu+2`/`Cu^2+`/`Cu+` -> `Cu^[2+]`, `Cu^[1+]` etc. Wildcards in `LIKE '%Cu2+%'` preserved. |
| Metal-name alias expansion (`expand_metal_name_literals`) | same metal-name columns | EQ on a single literal -> IN-list of all variants (`'copper(II)'` -> `IN ('copper(II)', 'copper', 'Cu2+', 'Cu^[2+]')`). NEQ -> `NOT IN`. IN/NOT IN -> per-element expansion + dedupe. `LIKE 'cupric'` (no wildcards) -> same expansion as `=`; `LIKE '%cupric%'` (with wildcards) left as substring match. `LOWER(col)` / `UPPER(col)` wrappers preserved with case-transformed expansion terms. Table aliases (`c.metal_name_SRD`, ...) flow through verbatim. |
| RDKit SMILES canonicalize (`normalize_chem_literals`) | `smiles`, `SMILES`, `metal_smiles`, `ligand_smiles`, `canonical_smiles` | Non-canonical SMILES -> RDKit canonical SMILES. `LIKE '%…%'` patterns left alone (RDKit can't parse partial SMILES). |
| RDKit InChI canonicalize (`normalize_chem_literals`) | `inchi`, `InChI`, `metal_inchi`, `ligand_inchi` | Non-canonical InChI -> RDKit canonical InChI. `LIKE` patterns left alone. |

#### Composite-WHERE handling

Every comparison node (`EQ`, `NEQ`/`<>`, `LIKE`, `IN`, `NOT IN`, etc.)
is visited independently during the AST walk, so all of these work
without any special-casing — including arbitrary nesting, parens,
`AND`/`OR`/`NOT`, `BETWEEN`, and read-only sub-SELECTs:

```sql
-- IN list, all elements canonicalized AND alias-expanded:
metal_name_SRD IN ('Cu2+', 'iron(III)', 'zinc(II)')
   -> metal_name_SRD IN
        ('Cu2+', 'Cu^[2+]', 'Cu', 'copper',
         'iron(III)', 'iron', 'Fe3+', 'Fe^[3+]', 'Fe',
         'zinc(II)', 'zinc', 'Zn2+', 'Zn^[2+]', 'Zn')

-- NEQ becomes NOT IN so the canonical form is excluded too:
metal_name_SRD <> 'cupric'
   -> NOT metal_name_SRD IN ('cupric', 'copper', 'Cu^[2+]', 'Cu', 'Cu2+')

-- The "GPT-5.4 failure mode" — agent writes a Latin alias, gets 0 rows
-- in the old pipeline, gives up. Now: matches the canonical row.
metal_name_SRD = 'cupric'
   -> metal_name_SRD IN ('cupric', 'copper', 'Cu^[2+]', 'Cu', 'Cu2+')

-- Mixed metals + numeric + ligand LIKE + ranking:
(metal_name_SRD = 'cupric' OR metal_name_SRD = 'ferric')
   AND s.constant_value > 5
   AND lc.ligand_name_SRD LIKE '%glycine%'
ORDER BY s.constant_value DESC
   -> each metal-name node expanded independently;
      numeric and ligand-name predicates untouched.

-- Shorthand inside a sub-SELECT:
c.metal_id IN (SELECT metal_id FROM metal_card WHERE metal_name_SRD = 'cupric')
   -> ... WHERE metal_name_SRD IN ('cupric', 'copper', 'Cu^[2+]', 'Cu', 'Cu2+')

-- LIKE pattern on a metal column WITH wildcards: chem-fold inside wildcards, no expansion:
metal_name_SRD LIKE '%Cu2+%'  ->  metal_name_SRD LIKE '%Cu^[2+]%'

-- LIKE pattern on a metal column WITHOUT wildcards: treated as EQ + alias-expanded:
metal_name_SRD LIKE 'cupric'  ->  metal_name_SRD IN ('cupric', 'copper', 'Cu^[2+]', 'Cu', 'Cu2+')

-- LOWER() wrapper on LHS: preserved, expansion terms lowercased to match:
LOWER(c.metal_name_SRD) = 'cu2+'
   ->  LOWER(c.metal_name_SRD) IN ('cu2+', 'cu^[2+]', 'cu', 'copper')

-- Same shorthand inside a non-chemistry column literal — preserved:
c.note = 'observed Cu2+ binding'  ->  unchanged
```

#### Logic at a glance (the most complicated case)

For an arbitrarily nested WHERE, the AST walker dispatches **per
comparison node by type**:

```
                ┌─ exp.EQ  ──► chem-fold RHS literal (always)
                │              + alias-expand → IN-list   (metal cols only)
                │
                ├─ exp.NEQ ──► chem-fold RHS literal
                │              + alias-expand → NOT IN     (metal cols only)
WHERE root ───►│
                ├─ exp.In  ──► chem-fold each element
                │              + alias-expand each + dedupe (metal cols only)
                │
                ├─ exp.Like ─► chem-fold inside wildcards (no expansion)
                │
                ├─ exp.Not  ─► descend into child (covers NOT IN, NOT LIKE)
                │
                ├─ exp.And/Or/Paren ─► descend into both branches
                │
                └─ exp.Subquery ─────► descend into nested SELECT.WHERE
```

Each visit is a pure function of one node — there is no global state, no
"first metal wins" coupling between branches, no special-casing for
AND-vs-OR. So the most complicated possible WHERE — say, `(m=A OR m IN
(B,C)) AND s BETWEEN 1 AND 5 AND lig_id IN (SELECT id FROM ligand_card
WHERE smiles LIKE '%COOH%') AND m <> 'iron'` — is normalized correctly in
one pass: every metal predicate (whether EQ, IN, or NEQ) is independently
expanded, the SMILES `LIKE` is folded inside the wildcards, the numeric
`BETWEEN` and the integer `IN (SELECT …)` flow through unchanged.

> **`ligand_name`/`ligand_name_SRD` literals are not expanded at WHERE
> time**: PubChem lookup is too slow for every query. Two clean recovery
> paths exist instead:
>
> 1. **Eager**: call `search_ligands(name='glycine')` first to resolve to
>    `ligand_id`, then filter by ID.
> 2. **Automatic 0-row fallback**: if `WHERE ligand_name LIKE '%X%'`
>    returns no rows in `search_stability`/`pka`/`networks`, the
>    similarity expansion (which DOES call PubChem internally) retries
>    with structurally similar ligand IDs. The agent never has to ask.
>
> SMILES / InChI literals on `ligand_smiles`/`ligand_inchi` columns *are*
> RDKit-canonicalized.

---

## Data Linking & Enrichment Per Tool

Each tool does more than query a single table — it joins across databases and enriches
the raw SQL result with computed fields, cross-referenced counts, and parsed structures.
The compactor then renders this enriched output, not just the raw query result.

### Database cross-reference map

```
                    srd46_cards.db
  ┌──────────────┬──────────────┬─────────────────────┬──────────────────┐
  │ metal_card   │ ligand_card  │ ligandmetal_card     │ ligand_pka_*     │
  │              │              │ ligandmetal_stab_*   │                  │
  └──────┬───────┴──────┬───────┴──────────┬──────────┴────────┬─────────┘
         │              │                  │                   │
         │   ┌──────────┼──────────────────┼───────────────────┘
         │   │          │                  │
  ┌──────▼───▼──────────▼──────────────────▼─────────┐
  │               srd46_equilibrium_maps.db           │
  │  eq_map_collection, eq_map, eq_network, eq_node  │
  └──────────────────────┬───────────────────────────┘
                         │
  ┌──────────────────────▼───────────────────────────┐
  │               srd46_literature.db                 │
  │  ref_vlm_literature_alt, ref_literature_alt       │
  └──────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────┐
  │         srd46_ligand_fingerprints.db              │
  │  ligand_similarity (pre-computed Morgan/MACCS)    │
  └──────────────────────────────────────────────────┘
```

### Per-tool enrichment detail

---

#### `search_metals`

| Stage | Source | Output field(s) |
|-------|--------|-----------------|
| Main query | `metal_card` | metal_id, metal_name, symbol, charge, is_simple_ion, SMILES, InChI |
| Name expansion | `_expand_metal_name()` | Generates all search variants: `"copper(II)"` -> `["copper(II)", "Cu", "Cu2+", "Cu^[2+]"]` |
| **Enrichment: data-richness counts** | `ligandmetal_card` GROUP BY metal_id | `beta_def_count`, `ligand_count`, `vlm_count` |
| ID prefixing | all ID columns | `metal_41` format |

```
metal_card ──(metal_id)──> ligandmetal_card
                              │
                              ├── COUNT(DISTINCT beta_definition_id) → beta_def_count
                              ├── COUNT(DISTINCT ligand_id)           → ligand_count
                              └── COUNT(DISTINCT complex_system_id)   → vlm_count
```

---

#### `search_ligands`

| Stage | Source | Output field(s) |
|-------|--------|-----------------|
| Main query | `ligand_card` | ligand_id, ligand_name, HxL_definition, formula, class, SMILES, InChI |
| Name fallback | PubChemPy -> RDKit | canonical InChI/SMILES for retry (triggers on 0-row name-only search) |
| Functional group filter | RDKit substructure (post-SQL) | `excluded_by_groups` count |
| **Enrichment: pKa brackets** | `ligand_pka_bracket` WHERE is_estimated=0 | `pka_brackets` list per ligand |
| **Enrichment: VLM count** | `ligandmetal_card` GROUP BY ligand_id | `vlm_count` |
| **Enrichment: all SMILES** | `ligand_card` (full WHERE, no LIMIT) | `all_smiles` list (for functional-group stats in compactor) |
| ID prefixing | all ID columns | `ligand_5760` format |

```
ligand_card ──(ligand_id)──> ligand_pka_bracket    → pka_brackets
             ──(ligand_id)──> ligandmetal_card      → vlm_count
             ──(WHERE, no LIMIT)──> ligand_card     → all_smiles (for compactor RDKit scan)
```

The compactor then uses `all_smiles` to compute a functional-group prevalence table via RDKit.

---

#### `search_stability`

| Stage | Source | Output field(s) |
|-------|--------|-----------------|
| Main query | `ligandmetal_card c` JOIN `ligandmetal_stability_measured s` | vlm_id, metal_id, ligand_id, beta_definition_id, constant_type, log_K, temperature, ionic_strength, equation_str, equation_tree_json, HxL_involved_json, ... |
| Similarity expansion | `ligand_similarity` (fingerprint DB) | Rewrites WHERE to include similar ligands (on 0-row fallback) |
| Functional group filter | RDKit substructure (post-SQL) | Filters rows by SMILES patterns |
| **Enrichment: eq map ID** | `eq_node` JOIN `eq_network` (equilibrium DB) | `map_id` (ref_eq_map) per vlm_id |
| **Enrichment: HxL parsing** | `HxL_involved_json` column (in-row) | `HxL_involved` (parsed string) |
| **Enrichment: pKa bracket matching** | `ligand_pka_bracket` (cards DB) | `pKa_bracket_involved` per row |
| ID prefixing | all ID columns | prefixed format |

```
ligandmetal_card ─┬─ JOIN ligandmetal_stability_measured   → main result rows
                  │
(vlm_id) ─────────┼──> eq_node JOIN eq_network             → map_id (EQUILIBRIUM DB)
                  │
(ligand_id) ──────┼──> ligand_pka_bracket                  → pKa_bracket_involved
                  │
(HxL_involved_json)──> in-row JSON parse                   → HxL_involved (string)
```

The compactor further extracts `non_aqueous_phases` from `equation_tree_json` during rendering.

---

#### `search_networks`

| Stage | Source | Output field(s) |
|-------|--------|-----------------|
| Main query | `eq_map_collection c` JOIN `eq_map m` JOIN `eq_network n` JOIN `eq_node nd` (equilibrium DB) | network_db_id, node_id, vlm_id, beta_definition_id, equation, constant_type, log_K, node_count, edge_count, temp/ionic ranges |
| **Cross-DB JOIN: ligand metadata** | `cardsdb.ligand_card lc` LEFT JOIN (ATTACH cards DB) | `ligand_HxL_definition`, `ligand_SMILES` |
| Two-step query | Step 1: fetch distinct network IDs; Step 2: fetch ALL nodes for those networks | Ensures complete networks (no partial truncation) |
| Similarity expansion | `ligand_similarity` (fingerprint DB) | Rewrites WHERE on 0-row fallback |
| ID prefixing | all ID columns | prefixed format |

```
EQUILIBRIUM DB:
eq_map_collection ──> eq_map ──> eq_network ──> eq_node   → main result

CARDS DB (ATTACHed as cardsdb):
ligand_card ──(ligand_id)──> LEFT JOIN                     → ligand_HxL_definition, ligand_SMILES
```

---

#### `search_pka_values` / `search_pka_ligands`

| Stage | Source | Output field(s) |
|-------|--------|-----------------|
| Main query | `ligand_card lc` JOIN `ligand_pka_measured p` | ligand_id, ligand_name, pKa, pKa_type, temperature, ionic_strength, bracket_from/to, method, quality, source_vlm_id |
| Similarity expansion | `ligand_similarity` (fingerprint DB) | Rewrites WHERE; attaches `similarity_score` |
| Functional group filter | RDKit substructure (post-SQL) | Filters rows |
| **Enrichment: M_tot** | `ligandmetal_card` GROUP BY ligand_id | `M_tot` (total distinct metals for this ligand) |
| **Enrichment: M_above / M_below** | `ligandmetal_stability_measured` JOIN `ligandmetal_card` + `json_each(HxL_involved_json)` | `M_above` (metals binding deprotonated form), `M_below` (metals binding protonated form) |
| ID prefixing | all ID columns | prefixed format |

```
ligand_card ──> JOIN ligand_pka_measured                   → main pKa rows

(ligand_id) ───> ligandmetal_card                          → M_tot

(ligand_id) ───> ligandmetal_stability_measured
                   + json_each(HxL_involved_json)
                   cross-matched with bracket_from/to      → M_above, M_below
```

`M_above`/`M_below` answer: "how many metals bind this ligand in each protonation state?"
This uses SQLite's `json_each()` to parse the `HxL_involved_json` array and match each
HxL form against the pKa bracket boundaries.

The pKa_values compactor groups rows into 0.5-unit bands and renders per-band RDKit
functional-group statistics.

---

#### `search_citations`

| Stage | Source | Output field(s) |
|-------|--------|-----------------|
| Main query | `ref_vlm_literature_alt rv` JOIN `ref_literature_alt la` | example_vlm_id, vlm_count, literature_alt_id, shortcut, citation |
| GROUP BY deduplication | GROUP BY (literature_alt_id, shortcut, citation) | Collapses multiple VLM mappings into one citation row |
| **Aggregation** | `MIN(rv.vlm_id)` -> example_vlm_id; `COUNT(DISTINCT rv.vlm_id)` -> vlm_count | Representative VLM + total count per citation |
| ID prefixing | all ID columns | prefixed format |

```
ref_vlm_literature_alt ──> JOIN ref_literature_alt
                              GROUP BY citation
                              ├── MIN(vlm_id)            → example_vlm_id
                              └── COUNT(DISTINCT vlm_id) → vlm_count
```

---

#### `inspect_card` (metal)

| Stage | Source | Output field(s) |
|-------|--------|-----------------|
| Primary card | `metal_card` WHERE metal_id=? | Full metal record |
| **Enrichment: ligand partners** | `ligandmetal_card` JOIN `ligandmetal_stability_measured` JOIN `ligand_card` | Top 5 ligand partners by measurement count |
| **Enrichment: totals** | `ligandmetal_card` GROUP BY | `total_ligand_partners`, `total_vlm_measurements` |

The compactor queries the DB again for ALL ligand partner SMILES to compute a
functional-group prevalence table.

```
metal_card ──(metal_id)──> ligandmetal_card
                              ├── JOIN ligand_card   → ligand_name, top 5 partners
                              └── COUNT(*)           → totals
```

---

#### `inspect_card` (ligand)

| Stage | Source | Output field(s) |
|-------|--------|-----------------|
| Primary card | `ligand_card` WHERE ligand_id=? | Full ligand record |
| **Enrichment: pKa values** | `ligand_pka_measured` | pka_id, pKa, type, temperature, ionic_strength, bracket_from/to, method, quality, `source_vlm_id` (parsed from vlm_ids_json) |
| **Enrichment: metal partners** | `ligandmetal_card` JOIN `ligandmetal_stability_measured` JOIN `metal_card` | Top 5 metal partners by measurement count |
| **Enrichment: totals** | `ligandmetal_card` GROUP BY | `total_metal_partners`, `total_vlm_measurements` |

```
ligand_card ──(ligand_id)──> ligand_pka_measured     → pKa values + source VLM
             ──(ligand_id)──> ligandmetal_card
                                 ├── JOIN metal_card → metal_name, top 5 partners
                                 └── COUNT(*)        → totals
```

---

#### `inspect_card` (vlm)

| Stage | Source | Output field(s) |
|-------|--------|-----------------|
| Primary card | `ligandmetal_card` JOIN `ligandmetal_stability_measured` | Full VLM record with speciation, equation trees, all JSON fields |
| **Enrichment: pKa context** | `_enrich_stability_with_hxl_pka()` (same as search_stability) | `HxL_involved`, `pKa_bracket_involved` |
| **Enrichment: networks** | `eq_node` JOIN `eq_network` (EQUILIBRIUM DB, ATTACHed as `eqdb`) | network_id, node_count, edge_count, node_id, is_duplicate |
| **Enrichment: citations** | `vlm_literature_sic` JOIN `literature_alt` (LITERATURE DB, ATTACHed as `litdb`) | literature_alt_id, shortcut, citation (top 5 + total count) |
| JSON parsing | in-row | equation_tree_json, LHS/RHS_species_json, HxL_involved_json parsed to Python objects |

```
ligandmetal_card ──> JOIN ligandmetal_stability_measured   → primary VLM card

(vlm_id) ──────────> eqdb.eq_node JOIN eq_network          → network membership (EQUILIBRIUM DB)

(vlm_id) ──────────> litdb.vlm_literature_sic
                        JOIN literature_alt                 → citations (LITERATURE DB)

(HxL_involved_json) ──> ligand_pka_bracket                 → pKa bracket context
```

Three databases queried via `attach_all_dbs()`.

---

#### `inspect_literature`

| Stage | Source | Output field(s) |
|-------|--------|-----------------|
| Query | `litdb.vlm_literature_sic` JOIN `litdb.literature_alt` (LITERATURE DB) | All citations for one VLM + total count |

---

#### `build_system_catalog`

| Stage | Source | Output field(s) |
|-------|--------|-----------------|
| Pair resolution | `ligandmetal_card` (cards DB) | metal_id, ligand_id, metal_name, ligand_name (up to 20 pairs) |
| **Enrichment: species catalog** | `ligandmetal_card` JOIN `ligandmetal_stability_measured` GROUP BY beta_definition_id | species_catalog: [{beta_definition_id, beta_definition_name, equation_str, n_entries, phases}] |
| Phase extraction | `equation_tree_json` (in-row parse) | `phases` field per species (aqueous/solid/gas/liquid/organic) |
| **Enrichment: VLM IDs** | `ligandmetal_card` (cards DB) | `vlm_ids` list (up to 200 per pair, with total count) |
| **Enrichment: HxL definition** | `ligand_card` (cards DB, bulk lookup) | `definition_HxL` per ligand |
| **Enrichment: equilibrium maps** | `eq_map_collection` JOIN `eq_map` JOIN `eq_network` (EQUILIBRIUM DB, separate connection) | network_id, node_count, edge_count, temp/ionic ranges per pair |
| Summary | computed | `n_metals`, `n_ligands`, `n_pairs`, `total_species` |

```
CARDS DB:
ligandmetal_card ──> resolve pairs (metal_id, ligand_id)
                 ──> JOIN ligandmetal_stability_measured
                        GROUP BY beta_definition_id        → species_catalog
                 ──> complex_system_id list                → vlm_ids
ligand_card      ──> definition_HxL                        → per-ligand HxL

EQUILIBRIUM DB (separate connection):
eq_map_collection ──> eq_map ──> eq_network                → equilibrium_maps per pair
```

---

#### `search_similar_ligands`

| Stage | Source | Output field(s) |
|-------|--------|-----------------|
| Similarity ranking | `ligand_similarity` (FINGERPRINT DB) | family_score (MACCS), similarity_score (Morgan), tversky_query_in_target, tversky_target_in_query |
| **Enrichment: ligand metadata** | `ligand_card` (cards DB, bulk lookup) | ligand_name, smiles, HxL_canonical (for query + all similar ligands) |
| **Enrichment: eq richness (query)** | `eq_map_collection` + `eq_node` JOIN chain (EQUILIBRIUM DB) | metals_covered, n_metals, n_beta_defs, top_maps |
| **Enrichment: eq richness (each similar)** | same as above, per ligand | eq_richness per similar ligand |

```
FINGERPRINT DB:
ligand_similarity ──(ligand_id)──> ranked similar ligands  → similarity scores

CARDS DB:
ligand_card ──(bulk ligand_ids)──> metadata                → ligand_name, smiles, HxL

EQUILIBRIUM DB:
eq_map_collection ──> eq_map ──> eq_network ──> eq_node    → eq_richness per ligand
                                                              (metals_covered, n_beta_defs, top_maps)
```

The compactor further queries the fingerprint DB for ALL ligands above similarity > 0.5
to build the diff-signature histogram, and runs RDKit functional-group detection on
each similar ligand's SMILES.

---

### Compactor-side enrichment

Some compactors perform their own DB queries or RDKit analysis beyond what the tool provides:

| Compactor | Extra work | Source |
|-----------|-----------|--------|
| `compact_search_ligands` | Functional-group prevalence table across all SQL matches | RDKit scan of `all_smiles` |
| `compact_search_stability` | Non-aqueous phase extraction per row | Parses `equation_tree_json` during rendering |
| `compact_search_pka_values` | Per-band functional-group detection | RDKit scan of band SMILES |
| `compact_inspect_card` (metal) | Functional-group stats across all ligand partners | Queries `ligand_card` for ALL partner SMILES, then RDKit scan |
| `compact_search_similar_ligands` | Functional-group diff per similar ligand; diff-signature histogram over all DB ligands with sim > 0.5 | RDKit diff + query to fingerprint DB |

---

## Compactor Pipeline

### How compaction works

1. Tool returns raw JSON (list or dict with prefixed IDs).
2. `compact_tool_result_immediately()` in `compactor.py` looks up a hardcoded compactor via `_compacts_tools` tags on each function.
3. The compactor renders markdown, picking a detail tier based on output length.
4. The agent sees the compacted markdown; the raw JSON is preserved in `tool_history` for diagnostics.

### Auto-wiring

Each compactor function has a `_compacts_tools` attribute set in `__init__.py`:

```python
compact_search_stability._compacts_tools = ("search_stability",)
compact_system_catalog._compacts_tools = ("build_system_catalog", "system_catalog")
```

`COMPACTOR_FUNCTIONS` lists all 16 compactor functions for catalog discovery.

### Shared helpers (`_compactor_helpers.py`)

| Helper | Purpose |
|--------|---------|
| `_cell(val, max_len=80)` | Stringify for table cell; `None`/blank -> `***`; truncate with `...` |
| `_esc(val)` | Like `_cell` but wraps in backticks if `[` or `]` present |
| `_ctype(raw)` | `"K"` -> `"logK"`, `"H"` -> `"DH"`, `"S"` -> `"DS"` |
| `_num(val)` | Round floats to 4 decimals with zero suppression; `None` -> `***` |
| `_range_str(lo, hi)` | `lo~hi` if different, else single value |

---

## Per-Tool Compactor Details

### 1. `search_metals` -> `compact_search_metals`

**Tiers:** 1 (flat table)

**Raw input:** `list[dict]` with enrichment counts per metal.

**Output columns:**

```
| metal_id | metal_name | symbol | charge | simple_ion | smiles | inchi
| beta_def_count | ligand_count | vlm_count |
```

- Count columns formatted as tokens: `beta_totN_42`, `ligand_totN_127`, `vlm_totN_3847`
- InChI truncated to 40 chars
- `simple_ion` shown as checkmark

---

### 2. `search_ligands` -> `compact_search_ligands`

**Tiers:** 1 (flat table + optional functional-group section)

**Raw input:** `dict` with `results`, `total_sql_matches`, `excluded_by_groups`, `limit`, `all_smiles`.

**Output structure:**

```
## search_ligands -- N result(s)
**stats:** M SQL matches . showing N . limit L

| ligand_id | ligand_name | HxL_def | ligand_class | vlm_count | smiles | pka_brackets |

### Functional groups across all SQL matches (K parseable SMILES)
| group | count | % |
```

- SMILES wrapped in backticks
- pKa brackets rendered as `(-inf, H2L, 2.33, HL, 8.18, L, +inf)` with `*est*` suffix if estimated
- Functional-group table scans ALL SQL-matched SMILES (not just displayed rows) via RDKit

---

### 3. `search_stability` -> `compact_search_stability`

**Tiers:** 3 (threshold: 5,000 chars)

**Raw input:** `list[dict]` grouped by (metal_id, ligand_id) pair.

#### Tier 1: Full

One subsection per metal-ligand pair. Every measurement is its own row.

```
### Metal + Ligand -- N measurement(s)
metal_id: X | ligand_id: Y
ligand_HxL_def: Z | ligand_SMILES: S

| vlm_id | ref_eq_map | beta_def | type | value | T C | I(M)
| equation | non_aqueous_phases | HxL_involved | pKa_bracket_involved |
```

- Non-aqueous phases extracted from `equation_tree_json`
- HxL_involved and pKa_bracket_involved from enrichment

#### Tier 2: Merged

Rows sharing the same `(equation_str, constant_type)` collapsed into range rows.

```
| equation | type | vlm_counts | vlm_ids | ref_eq_map | value_range | T C_range | I(M)_range
| beta_defs | non_aqueous_phases | HxL_involved | pKa_bracket_involved |

Summary stats
| type | vlm_counts | beta_counts | T C_range | I(M)_range | non_aqueous_phases | ref_eq_map_counts |
```

- Per-section summary stats table appended

#### Tier 3: Global stats

All per-section detail replaced by one summary table per constant type (logK, DH, DS).

```
### logK -- N metal-ligand pair(s)
| metal_id | metal_name | ligand_id | ligand_name | ligand_HxL_def | ligand_SMILES
| vlm_counts | beta_counts | T C_range | I(M)_range | non_aqueous_phases | ref_eq_map_counts |
```

- Pairs ranked by measurement count within each constant type

---

### 4. `search_networks` -> `compact_search_networks`

**Tiers:** 3 (threshold: 5,000 chars)

**Raw input:** `list[dict]` -- all nodes for qualifying networks (limit applies to distinct networks, not rows).

#### Tier 1: Full

Per metal-ligand pair section with beta-def legend and per-network table.

```
### Metal + Ligand -- N network(s)
metal_id: X | ligand_id: Y | ligand_def_HxL: Z | ligand_SMILES: S

| beta_def | equation |     <-- legend table

| network_id | node_counts | edge_counts | T_range | I_range
| vlm_ids | beta_def_ids | type | values |

#### Reference-state network: net_id (N nodes)
| beta_def | equation | type | value |     <-- sorted by logK ascending
```

- Beta-def IDs: list if <=3, else `"N diff beta_def"` token
- Values grouped by constant type with ranges

#### Tier 2: Compact

Global beta-def legend + pair summary table + max-node-per-pair table + global max detail.

```
### Beta-definition legend
### Metal-ligand pair summary
| metal | metal_id | ligand | ligand_id | HxL | T_range | I_range | net_count | max_nodes | ligand_SMILES |

### Max-node network per pair
| ... | max_net_id | max_nodes | max_edge_counts | max_T_range | max_I_range
| max_vlm_ids | max_beta_def_ids | max_type | max_values |

### Global max-node network: Metal + Ligand
| beta_def | equation | type | value |
```

#### Tier 3: Ultra-compact

Pair summary merges `max_net_id` inline; separate max-node table dropped.

```
### Metal-ligand pair summary
| ... | max_nodes | max_net_id | ligand_SMILES |

### Global max-node network: Metal + Ligand
| beta_def | equation | type | value |
```

---

### 5. `search_pka_values` -> `compact_search_pka_values`

**Tiers:** 2 (threshold: 5,000 chars)

**Raw input:** `list[dict]` with per-protonation metal binding counts.

Rows sorted by pKa ascending, grouped into 0.5-unit bands.

#### Tier 1: Full

Every row shown within its band.

```
### pKa 2.0-2.5 (N entries)
| vlm_id | ligand_id | ligand_name | HxL_def | smiles | pKa | T C | I(M)
| bracket_from->to | M_bind_totN_below | M_bind_totN_above | [similarity_score] |
```

- `similarity_score` column only shown when ligand-similarity expansion was used

#### Tier 2: Truncated

Each band capped at 5 rows; per-band statistics appended.

```
[...first 5 rows...]

**Band stats (all N entries):**
| stat | value |
| entries | N |
| unique ligands | M |
| pKa range | lo -- hi |
| T C range | lo -- hi |
| I(M) range | lo -- hi |
| HxL forms | H2L(3), HL(5), ... |
| functional groups | carboxyl(4), amine(3), ... |
```

---

### 6. `search_pka_ligands` -> `compact_search_pka_ligands`

**Tiers:** 1 (flat table, one row per ligand)

**Raw input:** `list[dict]` grouped by ligand.

```
| ligand_id | ligand_name | HxL_def | formula | smiles | pH_ladder | T C_range | I(M)_range | similarity_score |
```

- **pH ladder** encodes full protonation sequence:
  `-inf; H3L (M_tot_0); (pKa1, vlm_X); H2L- (M_tot_5); (pKa2, vlm_Y); HL2- (M_tot_12); +inf`
- Each segment shows dominant form and how many metals bind it

---

### 7. `search_citations` -> `compact_search_citations`

**Tiers:** 1 (flat table)

**Raw input:** `list[dict]` deduplicated by citation.

```
| example_vlm_id | vlm_count | lit_id | shortcut | citation |
```

- Citation truncated to 80 chars

---

### 8. `search_similar_ligands` -> `compact_search_similar_ligands`

**Tiers:** 1 (main table + diff histogram)

**Raw input:** `dict` with `query_ligand`, `query_eq_richness`, `metal_filter`, `similar_ligands`.

**Output structure:**

```
**Query:** ligand_name
**Eq-map coverage:** N metal partner(s)

| ligand_id | ligand_name | smiles | family_score | similarity_score
| tversky_query_in_target | tversky_target_in_query | diff_catalog_fun_group |
```

- Query ligand shown as first reference row (all similarities = `--`)
- SMILES: full length, no truncation
- `diff_catalog_fun_group`: RDKit-computed per-group diff vs query (e.g. `+thiol(+1); -carboxyl(-1)`)

**Diff signature histogram** (appended):

Queries fingerprint DB for ALL ligands with similarity > 0.5 and builds a pivot table:

```
### Diff signature summary (N ligand(s) with similarity > 0.5)
| group | <-2 | -2 | -1 | 0 | +1 | +2 | >+2 | avg_beta_counts_per_ligand |
```

- Rows sorted by total occurrences descending
- First row `no_diff_catalog_fun` counts ligands with identical functional-group profile

---

### 9. `build_system_catalog` -> `compact_system_catalog`

**Tiers:** 3 (thresholds: 5,000 / 8,000 chars)

**Raw input:** `dict` with `pairs` list and `summary`.

#### Tier 1: Full

Per-pair section with species catalog table, VLM ID listing, and equilibrium map table.

```
### Metal + Ligand
**metal_id:** X | **ligand_id:** Y | **ligand_def_HxL:** Z
**entries:** N | **species:** M | **vlm_count:** V

| beta_definition_id | beta_definition_name | equation_str | phases | n_entries |

**vlm_ids:** vlm_1, vlm_2, ... (or first 5 + last 3 with ellipsis if >10)

**equilibrium_maps:** N preset reference network(s)
| network_id | nodes | edges | T range | I range |
```

#### Tier 2: Compact

Slim species table (no name column, non-aqueous phases inline), VLM count+range only, one-line eq_maps summary.

```
### Metal + Ligand
*(all species aqueous)*
| beta_def_id | equation_str | n |

**vlm_ids:** N (first...last)
**eq_maps:** N ref nets (ids) | T: range | I: range | max N nodes, M edges
```

#### Tier 3: Ultra-compact

Global equation legend + numbered list items with sub-bullets.

```
### Equation legend
| beta_def_id | equation | note |

*(all species aqueous unless noted)*

**1. Metal + Ligand** (ids) -- ligand_def_HxL: X | N ent, M sp, V vlms (range)
   - species: beta_def_78(42) beta_def_79(38) ...
   - eq:N nets T:range I:range max Nn/Me
```

---

### 10. `inspect_card` -> `compact_inspect_card`

**Tiers:** 1 per card type (auto-detected from `prefix_id` prefix)

#### Metal card (`metal_*`)

```
## inspect_card -- Metal | metal_41
**Name:** Cu^[2+]
**Symbol:** Cu | **Charge:** 2
**SMILES:** [Cu+2]
**Flags:** simple-ion
**Partners:** 127 ligand(s), 3847 measurement(s) total

| ligand_id | Ligand | # meas |

### Functional groups across all ligand partners (N parseable SMILES)
| group | count | % |
```

- Ligand partner table shows top 5 by measurement count
- Functional-group section scans ALL partner SMILES (queries DB directly)

#### Ligand card (`ligand_*`)

```
## inspect_card -- Ligand | ligand_5760
**Name:** Aminoacetic acid (Glycine)
**Formula:** C2H5N1O2 | **Class:** Amino Acids
**SMILES:** NCC(=O)O
**HxL definition:** H2L+

**pKa values:** N
| source_vlm | pKa | T (C) | I (M) | From -> To | Solvent | Method | Quality |

**Partners:** M metal(s), V measurement(s) total
| metal_id | Metal | # meas |
```

#### VLM card (`vlm_*`)

```
## inspect_card -- VLM | vlm_93847

### Metal
**metal_id:** metal_41 | **metal_name:** Cu^[2+]
**metal_SMILES:** [Cu+2]

### Ligand
**ligand_id:** ligand_5760 | **ligand_name:** Aminoacetic acid (Glycine)
**ligand_HxL_definition:** H2L+
**ligand_SMILES:** NCC(=O)O

### Stability
**vlm_id:** vlm_93847
**beta_definition_id:** beta_def_78 | **beta_definition_name:** [ML]/[M][L]
**data_type:** log_K | **log_K:** 8.47
**temperature:** 25 C | **ionic_strength:** 0.1 M
**equation:** [Cu2+] + [Gly-] <=> [CuGly+]
**Ligand_HxL_involved:** [HL], [L-] | **pKa_bracket_involved:** ...
**LHS_species:** Cu2+, Gly- | **RHS_species:** CuGly+

### Networks
| network_id | Nodes | Edges | node_id | dup? |

**total_citations:** N

| lit_id | shortcut | citation |
```

---

### 11. `inspect_literature` -> `compact_inspect_literature`

**Tiers:** 1 (flat table)

```
## inspect_literature -- vlm_93847 -- N citation(s)
| lit_id | shortcut | citation |
```

---

### 12. `0_preplan_decision` -> `compact_preplan_decision`

**Tiers:** 1 (bullet list)

```
## Pre-Plan Decision
- **Task type:** comparison
- **Metals to search:** copper, zinc
- **Ligands to search:** EDTA, glycine
- **L0 tools needed:** search_metals, search_ligands, build_system_catalog
- **Notes:** ...
```

---

### 13-16. Aggregate compactors

#### `db_count_records` -> `compact_db_count_records`

```
## db_count_records
| table | where | count |
```

#### `db_distribution` -> `compact_db_distribution`

```
## db_distribution - table by column
**total_rows:** N
| value | count | pct |
```

#### `db_ranked_pairs` -> `compact_db_ranked_pairs`

```
## db_ranked_pairs - ligands_per_metal
| metal_id | name | count |
```

#### `get_table_schema` -> `compact_get_table_schema`

```
## get_table_schema - N column(s)
| cid | name | type | notnull | pk |
```

---

## Reference ID Extraction (`_agentic_ref_id_extractor.py`)

Separate from compaction. Scans raw tool JSON and extracts all entity IDs for evaluation diagnostics.

### Three extraction tiers

| Tier | Entity types | Fields captured |
|------|-------------|-----------------|
| Full-resolved | metal, ligand, beta_def | prefixed_id + name + detail (SMILES, equation) |
| Prefixed-ID only | vlm, ref_eq_net, eq_node, ref_eq_map, lit, pka | prefixed_id only |
| Skip | db_count_records, get_table_schema, 0_preplan_decision | no entity IDs |

### Per-tool extractor map (`_TOOL_EXTRACTORS`)

| Tool | Extractor | Strategy |
|------|-----------|----------|
| `search_stability` | `_extract_from_rows` | Generic row scanner for `list[dict]` |
| `search_networks` | `_extract_from_rows` | Generic row scanner |
| `search_citations` | `_extract_from_rows` | Generic row scanner |
| `search_pka_values` | `_extract_from_rows` | Generic row scanner |
| `search_pka_ligands` | `_extract_from_rows` | Generic row scanner |
| `search_similar_ligands` | `_extract_from_similar_ligands` | Query + similar ligands + eq_richness nesting |
| `search_ligands` | `_extract_from_search_ligands` | Scan `results` list |
| `search_metals` | `_extract_from_search_metals` | Flat list scan |
| `inspect_card` | `_extract_from_inspect_card` | Card-type dispatch (metal/ligand/vlm) with deep nesting |
| `inspect_literature` | `_extract_from_inspect_card` | Same dispatcher |
| `build_system_catalog` | `_extract_from_system_catalog` | Pairs with species_catalog + vlm_ids + equilibrium_maps |
| `db_ranked_pairs` | `_extract_rows_from_dict_key` | Scan `results` key |
| `db_distribution` | `_extract_rows_from_dict_key` | Scan `groups` key |
| `db_count_records` | `-> []` | No IDs |
| `get_table_schema` | `-> []` | No IDs |
| `0_preplan_decision` | `-> []` | No IDs |

### Generic row scanner (`_extract_from_rows`)

Scans every dict in a list for ALL known ID columns:

| Column | Prefix | Entity type |
|--------|--------|-------------|
| `metal_id` | `metal` | metal |
| `ligand_id` | `ligand` | ligand |
| `beta_definition_id` | `beta_def` | beta_def |
| `vlm_id` | `vlm` | vlm |
| `source_vlm_id` | `vlm` | vlm |
| `example_vlm_id` | `vlm` | vlm |
| `network_db_id` / `network_id` | `ref_eq_net` | network |
| `node_id` | `eq_node` | node |
| `map_id` | `ref_eq_map` | map |
| `literature_alt_id` | `lit` | lit |
| `pka_id` | `pka` | pka |

### Output format

Appended to compacted markdown only when `len(compact_md) >= 500` chars.

Two tables: full-resolved entities (with name/detail columns) and plain-ID entities.

```markdown
### Referenced entity IDs

| type | prefixed_id | name | detail |
|------|-------------|------|--------|
| metal | metal_41 | Cu^[2+] | |
| ligand | ligand_5760 | Glycine | SMILES: NCC(=O)O; HxL: H2L+ |

| type | prefixed_id | label |
|------|-------------|-------|
| vlm | vlm_93847 | |
| network | ref_eq_net_3 | |
```

---

## Normalization Helpers

### Metal resolution (`metal_resolution.py`)

Expands user input into all matching search terms:

```
"copper"       -> ["copper", "Cu", "Cu2+", "Cu^[2+]"]
"copper(II)"   -> ["copper(II)", "copper", "Cu", "Cu2+", "Cu^[2+]"]
"ferric"       -> ["Fe3+", "Fe^[3+]", "Fe", "iron"]
"Cu2+"         -> ["Cu2+", "Cu^[2+]", "Cu"]
```

### Ligand resolution (`ligand_resolution.py`)

First-match pipeline when name search yields 0 rows:

1. InChI string -> RDKit canonicalize
2. SMILES string -> RDKit -> canonical InChI + SMILES
3. Common name -> PubChemPy lookup -> RDKit canonicalize

### Functional group catalog (`functional_group_catalog.py`)

25+ SMARTS patterns for coordination chemistry (carboxyl, primary_amine, thiol, pyridine, imidazole, phosphate, ...). Used for:

- **Post-SQL filtering** in search_ligands, search_stability, search_pka: `include_groups` (must match ALL), `exclude_groups` (excludes if ANY match)
- **Statistics** in ligand/metal card compactors: prevalence table across all partner SMILES
- **Diff analysis** in similar_ligand compactor: per-group count differences vs query
