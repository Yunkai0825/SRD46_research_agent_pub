"""Canned Q4.4 (Zn(II) hypothesis-generation) artifacts for the agent-page simulation.

Historical source: ``_output/Model_gpt54/Q4.4/Q4.4_*_batch1.md`` (a real prior run).

This is a deliberately *complicated* example: 13 tool calls, ~622 s wall-clock,
with phase-gating recovery (premature planner call at step 4 returns
``[PHASE ERROR]`` and forces ``build_system_catalog`` first), exploratory SQL
queries that return zero rows (steps 10–11), and a planner *revision* at
step 9. The replayed log mirrors all of these events so the SRD-46 browser
can faithfully demonstrate what a real run looks like.
"""

SIM_PROMPT = (
    "Based on the pKa values and stability constants available for amino-acid "
    "ligands, can you predict which amino acid not yet studied with Zn\u00b2\u207a "
    "would likely form the most stable zinc complex? Explain your reasoning."
)


SIM_ANSWER_MD = """\
Using the SRD-46 data now in hand, my **best prediction is methionine** as the
**proteinogenic amino acid not yet represented with Zn²⁺ stability constants
in the retrieved SRD-46 Zn–amino-acid set** that would most likely form the
**most stable Zn complex**.

## What SRD-46 shows

### 1) Proteinogenic amino acids with Zn²⁺ data already present

| Ligand        | ligand_id      | Zn²⁺ data present? | Notes                          |
|---------------|----------------|---------------------|--------------------------------|
| Glycine       | `ligand_5760`  | Yes                 | simple α-amino acid benchmark |
| Cysteine      | `ligand_5856`  | Yes (catalog)       | thiol/thiolate benchmark       |
| Histidine     | `ligand_5898`  | Yes (catalog)       | imidazole benchmark            |
| Alanine       | `ligand_5761`  | Yes (catalog)       | simple α-amino acid benchmark |
| Penicillamine | `ligand_5857`  | Yes                 | non-proteinogenic sulfur ref. |

### 2) Proteinogenic amino acids with pKa data but **no** Zn²⁺ entry

| Ligand          | ligand_id     | pKa pattern            | Zn²⁺ in retrieved set? |
|-----------------|---------------|------------------------|-------------------------|
| Serine          | `ligand_5828` | 2.16, 9.05             | No                      |
| Threonine       | `ligand_5829` | 2.20, 8.94             | No                      |
| Aspartic acid   | `ligand_5802` | 1.95, 3.71, 9.66       | No                      |
| Glutamic acid   | `ligand_5804` | 2.16, 4.15, 9.58       | No                      |
| Tyrosine        | `ligand_5819` | 2.24, 9.04, 10.1       | No                      |
| **Methionine**  | (not numerically resolved in pKa excerpt) | sulfur side chain | No |

## Why methionine is the strongest prediction

| Donor motif (Zn²⁺ in SRD-46) | Expected strength |
|------------------------------|--------------------|
| thiolate-containing          | highest            |
| imidazole-containing         | next               |
| ordinary N,O amino acids     | lower              |

| Candidate      | Side-chain donor   | Expected Zn²⁺ consequence                                     |
|----------------|--------------------|----------------------------------------------------------------|
| **Methionine** | thioether sulfur   | best chance among unstudied standards to gain extra stabilization |
| Asp/Glu        | extra carboxylate  | stronger than Gly-like, but less specifically Zn-favored      |
| Ser/Thr        | alcohol O          | weak donor unless deprotonated                                 |
| Tyr            | phenol O (pKa ≈ 10)| useful only at high pH                                         |
| Aliphatic AAs  | none               | should resemble Gly/Ala-type binding                           |

## Final prediction

| Predicted strongest unstudied AA for Zn²⁺ | Confidence | Reason |
|--------------------------------------------|------------|--------|
| **Methionine**                             | Moderate   | Best unstudied analog to the sulfur-favored Zn²⁺ binding seen for Cys/Pen in SRD-46. |

In short: **Zn²⁺ stability rises sharply when an amino acid offers a stronger
side-chain donor than the default amino/carboxylate pair.** Since His and Cys
are already studied, **methionine** is the most plausible unstudied standard
amino acid to give the most stable Zn complex.

**Source:** NIST SRD-46.
"""


SIM_PREPLAN_MD = """\
## Pre-Plan Decision

- **Task type:** multi-step
- **Metals to search:** H⁺, Zn(II)
- **Ligands to search:** cysteine, histidine, aspartic acid, glutamic acid,
  glycine, alanine, tyrosine, serine, threonine, methionine, lysine, proline
- **L0 tools needed:** `search_metals`, `search_ligands`, `build_system_catalog`
- **Notes:** Survey proteinogenic amino acids, find those lacking Zn(II)
  constants, then use their pKa profiles and patterns from other metals to
  infer likely strongest Zn binders.
"""


SIM_PLAN_MD = """\
**TYPE:** multi-step  *(planner revision = True, gpt5, 57.2s)*

**APPROACH:**

1. Enumerate the standard amino acids with protonation data: use
   `search_pka_ligands` with `ligand_class='amino acid'`, restricted to
   proteinogenic names (Gly, Ala, Val, Leu, Ile, Pro, Phe, Tyr, Trp, Ser,
   Thr, Asp, Glu, Asn, Gln, Lys, Arg, His, Cys, Met). Capture α-COOH,
   α-NH₃⁺, and side-chain pKa values and medium.
2. Determine which of those have Zn²⁺ constants: `search_stability` with
   `metal_id=metal_208` over the same ligand set; collect distinct
   `ligand_id`s with any Zn complex. Subtract → "unstudied with Zn" list.
3. Benchmark studied AAs: retrieve Zn constants under matched conditions
   (25 ± 2 °C, aqueous, similar I) for `ligand_5760` (Gly), `ligand_5761`
   (Ala), `ligand_5898` (His), `ligand_5856` (Cys); add Asp, Glu, Pro, Lys
   if present. Prefer mononuclear ZnL (β₁) and ZnL₂ (β₂); use `inspect_card`
   to verify species definitions.
4. For each unstudied candidate, evaluate donor availability from pKa and
   classify donor set (Tyr phenolate-O, Met thioether-S, Lys amine-N,
   Ser/Thr alcohol-O, Trp indole-N, Asn/Gln amide, Arg guanidinium).
   Prioritize stronger donors and chelation potential.
5. Strengthen prediction with analogs: `search_similar_ligands`
   (`metal_ids=[metal_208]`) for phenolate/carboxylate analogs (e.g.,
   salicylate for Tyr), thioether analogs for Met, diamine analogs for Lys.
6. Synthesize: rank unstudied AAs by expected Zn affinity combining
   (a) donor basicity/softness implied by pKa, (b) chelate potential,
   (c) analogous Zn constants. Use `inspect_literature` on 1–2 key
   comparator cards to confirm provenance before stating the prediction.

**WATCH OUT:**

- Do not mix peptide/dipeptide ligands with free amino acids; filter strictly
  to single amino-acid entries.
- Match T and I across Zn constants; avoid hydroxo/polynuclear species and
  nonaqueous media.
- Side-chain phenolate (Tyr) or amine (Lys) donors engage only when pH > pKa.
- Mind synonym/tautomer duplicates so an amino acid isn't double-counted.

**DONE WHEN:** At least one proteinogenic amino acid lacking Zn²⁺ data in
SRD-46 is identified and justified as the likely strongest Zn complex former,
with numeric pKa and Zn β values from matched-condition comparators (with IDs)
supporting the prediction.

`[_meta: model=gpt5, elapsed=57.2s, revision=True]`
"""


SIM_TOOL_RESULTS_MD = """\
> 13 tool calls · 622 s wall-clock · includes a phase-gating recovery and
> two zero-result exploratory queries before the final successful broad scan.

### Step 1 — `0_preplan_decision`  *(19.3 s)*

Returned the pre-plan above (task_type = multi-step).

### Step 2 — `search_metals` (parallel 2×, 0.4 s)

```json
{"name": "Zn(II), H+", "limit": 10}
```

| Result | rows |
|--------|-----:|
| *(no results)* | 0 |

### Step 3 — `search_ligands` (parallel 2×, 0.4 s)

```json
{"name": "cysteine, histidine, aspartic acid, ...", "limit": 50,
 "include_groups": ["amino acid"]}
```

| Result | rows |
|--------|-----:|
| *(no results)* | 0 |

### Step 4 — `0_plan_search_strategy`  ❌ **PHASE ERROR**  *(0.0 s)*

```text
[PHASE ERROR] Cannot call planner yet. You must first call these L0 tools:
build_system_catalog.
```

### Step 5 — `build_system_catalog` (no args)  *(0.0 s)*

```text
Error: Provide at least one of metal_id, ligand_id, or beta_definition_id.
```

### Step 6 — `search_metals` (retry with `symbol`)  *(1.2 s)*

```json
{"symbol": "Zn", "limit": 20}
```

| metal_id    | metal_name | symbol | charge | beta_def_count | ligand_count | vlm_count |
|-------------|-----------|--------|-------:|----------------|--------------|-----------|
| `metal_208` | Zn^[2+]   | Zn     | +2     | 122            | 1 169        | 4 095     |

### Step 7 — `search_ligands` (broaden by class)  *(0.5 s)*

```json
{"ligand_class": "amino acid", "limit": 100}
```

297 SQL matches, returning 100 ligands. Excerpt:

| ligand_id      | ligand_name                                | pKa brackets                     |
|----------------|--------------------------------------------|----------------------------------|
| `ligand_5760`  | Aminoacetic acid (Glycine)                 | 2.33, 9.57                       |
| `ligand_5761`  | L-2-Aminopropanoic acid (Alanine)          | 2.33, 9.71                       |
| `ligand_5765`  | L-Valine                                   | 2.27, 9.52                       |
| `ligand_5766`  | L-Leucine                                  | 2.32, 9.58                       |
| `ligand_5802`  | L-Aspartic acid                            | 1.95, 3.71, 9.66                 |
| `ligand_5804`  | L-Glutamic acid                            | 2.16, 4.15, 9.58                 |
| `ligand_5819`  | L-Tyrosine                                 | 2.24, 9.04, 10.1                 |
| `ligand_5828`  | L-Serine                                   | 2.16, 9.05                       |
| `ligand_5829`  | L-Threonine                                | 2.20, 8.94                       |
| `ligand_5856`  | L-Cysteine                                 | 1.97, 8.18, 10.41                |
| `ligand_5857`  | DL-Penicillamine                           | 1.96, 7.94, 10.55                |
| `ligand_5898`  | L-Histidine                                | 1.83, 6.07, 9.32                 |

*(…85 more rows)*

### Step 8 — `build_system_catalog` (Zn²⁺-scoped)  *(2.6 s)*

```json
{"metal_id": "metal_208"}
```

Catalog summary (excerpt):

| ligand_id      | ligand_name | beta_defs (count) | networks |
|----------------|-------------|-------------------|---------:|
| `ligand_5760`  | Glycine     | β_812, β_840      | 7        |
| `ligand_5761`  | Alanine     | β_811, β_839      | 4        |
| `ligand_5856`  | Cysteine    | β_815, β_843      | 6        |
| `ligand_5857`  | Penicillamine | β_815, β_843    | 5        |
| `ligand_5898`  | Histidine   | β_817, β_845, β_867 | 8     |

### Step 9 — `0_plan_search_strategy` (revised)  *(57.2 s, gpt5)*

Returned the 6-step plan above. Compactor: 39 534 chars across 23 turns →
2 parallel compression tasks.

### Step 10 — `search_pka_ligands` (parallel 2×, 1.8 s)

```sql
WHERE lc.ligand_name_SRD IN ('Glycine','Alanine','Valine', ...)
ORDER BY lc.ligand_name_SRD ASC, p.pKa ASC
LIMIT 200
```

| Result | rows |
|--------|-----:|
| *(no results — name match failed)* | 0 |

### Step 11 — `search_stability` (parallel 2×, 1.8 s)

```sql
WHERE c.metal_id = metal_208
  AND c.ligand_name_SRD IN ('Glycine','Alanine', ...)
  AND s.constant_type = 'logB'
```

| Result | rows |
|--------|-----:|
| *(no results — name match failed)* | 0 |

### Step 12 — `search_pka_ligands` (broadened, parallel 2×, 1.0 s)

```sql
WHERE lc.ligand_class_name LIKE '%amino acid%'
ORDER BY lc.ligand_name_SRD ASC, p.pKa ASC
LIMIT 200
```

200 rows. pKa data for all proteinogenic amino acids, including Met
(`ligand_5819`-class entry shows thioether side chain).

### Step 13 — `search_stability` (broadened, parallel 2×, 2.5 s)

```sql
WHERE c.metal_id = metal_208
  AND c.ligand_class_name LIKE '%amino acid%'
  AND s.constant_type = 'logB'
LIMIT 200
```

72 rows of Zn²⁺ logβ values. Distinct ligands with Zn²⁺ data:
Gly, Ala, Cys, His, Pen, Ser-glycyl-, β-Ala, … — but **no Met, Tyr, Asp, Glu,
Ser, Thr, Lys, Arg, Trp, Phe, Asn, Gln, Pro, Val, Leu, Ile**.
"""


SIM_HISTORY_MD = """\
| Step | Tool                       | Mode      | Time (s) | Result |
|----:|----------------------------|-----------|---------:|--------|
| 1   | `0_preplan_decision`       | sequential| 19.3     | OK     |
| 2   | `search_metals`            | ‖ 2×      |  0.4     | 0 rows |
| 3   | `search_ligands`           | ‖ 2×      |  0.4     | 0 rows |
| 4   | `0_plan_search_strategy`   | sequential|  0.0     | **PHASE ERROR** |
| 5   | `build_system_catalog`     | sequential|  0.0     | error (no args) |
| 6   | `search_metals` (retry)    | sequential|  1.2     | 1 row → metal_208 |
| 7   | `search_ligands` (retry)   | sequential|  0.5     | 100 / 297 rows |
| 8   | `build_system_catalog`     | sequential|  2.6     | Zn catalog |
| 9   | `0_plan_search_strategy`   | sequential| 57.2     | OK *(revision=True)* |
| 10  | `search_pka_ligands`       | ‖ 2×      |  1.8     | 0 rows |
| 11  | `search_stability`         | ‖ 2×      |  1.8     | 0 rows |
| 12  | `search_pka_ligands`       | ‖ 2× (broadened) | 1.0 | 200 rows |
| 13  | `search_stability`         | ‖ 2× (broadened) | 2.5 | 72 rows |

‖ = ran in parallel.

**Totals:** 13 calls · 259 s planning + 356 s execution + 7 s verdict = 622 s.
"""


# (sleep_seconds_before_emit, level, message) — emitted in order
# Faithfully replays the full 13-step run including phase-gating recovery.
SIM_LOG_SCRIPT: list[tuple[float, str, str]] = [
    (0.05, "INFO",  "SRD46-UI | === Freeform query starting ==="),
    (0.10, "INFO",  f"SRD46-UI | prompt: {SIM_PROMPT[:80]!r}..."),
    (0.10, "INFO",  "SRD46-UI | Launching MCP server (stdio transport)"),
    (0.30, "INFO",  "SRD46-UI | MCP session established  tools=42"),
    # iter 1: preplan
    (0.10, "INFO",  "SRD46-UI | [>] agent iter=1 prompt_len=820 memory_turns=1 elapsed=0.0s"),
    (0.30, "DEBUG", "SRD46-argo | call_argo  model=gpt54  prompt_chars=830  reasoning_cap=3000"),
    (0.40, "INFO",  "SRD46-UI |    [iter 1] Tool call(s): 0_preplan_decision"),
    (0.50, "DEBUG", "SRD46-server | 0_preplan_decision  task_type=multi-step  l0_needed=[search_metals, search_ligands, build_catalog]"),
    (0.10, "INFO",  "SRD46-UI | [PG] Preplan set l0_required={'search_metals', 'search_ligands', 'build_system_catalog'}"),
    (0.10, "INFO",  "SRD46-UI |    [iter 1] completed in 19.3s  (total 27s)"),
    # iter 2: parallel L0 -> 0 rows
    (0.10, "INFO",  "SRD46-UI | [>] agent iter=2 prompt_len=1240 memory_turns=3 elapsed=27s"),
    (0.20, "INFO",  "SRD46-UI |    [iter 2] Running 2 tools in PARALLEL: search_metals, search_ligands"),
    (0.20, "DEBUG", "SRD46-server | search_metals  name='Zn(II), H+'  -> 0 hits  in 0.4s"),
    (0.10, "DEBUG", "SRD46-server | search_ligands  name='cysteine, histidine, ...' include_groups=['amino acid']  -> 0 hits  in 0.4s"),
    (0.10, "INFO",  "SRD46-compactor | [M] Hardcoded compactor used for search_metals (42 chars)"),
    (0.10, "INFO",  "SRD46-compactor | [M] Hardcoded compactor used for search_ligands (43 chars)"),
    (0.10, "WARN",  "SRD46-UI | L0 entity resolution returned no hits; agent will need to broaden queries"),
    (0.10, "INFO",  "SRD46-UI |    [iter 2] completed in 0.4s  (total 41s)"),
    # iter 3: ERROR planner phase gating
    (0.10, "INFO",  "SRD46-UI | [>] agent iter=3 prompt_len=1380 memory_turns=5 elapsed=41s"),
    (0.20, "INFO",  "SRD46-UI |    [iter 3] Tool call(s): 0_plan_search_strategy"),
    (0.20, "ERROR", "SRD46-server | [PHASE ERROR] Cannot call planner yet. You must first call these L0 tools: build_system_catalog."),
    (0.10, "WARN",  "SRD46-UI | [PG] planner blocked; reverting to L0 phase"),
    (0.10, "INFO",  "SRD46-UI |    [iter 3] completed in 0.0s  (total 48s)"),
    # iter 4: build_catalog with no args -> error
    (0.10, "INFO",  "SRD46-UI |    [iter 4] Tool call(s): build_system_catalog"),
    (0.20, "ERROR", "SRD46-server | build_system_catalog  args={}  -> Error: Provide at least one of metal_id, ligand_id, or beta_definition_id."),
    (0.10, "INFO",  "SRD46-UI |    [iter 4] completed in 0.0s  (total 59s)"),
    # iter 5: retry search_metals with symbol
    (0.10, "INFO",  "SRD46-UI |    [iter 5] Tool call(s): search_metals"),
    (0.30, "DEBUG", "SRD46-server | search_metals  symbol='Zn' limit=20  -> 1 hit  metal_208 (Zn^2+)  in 1.2s"),
    (0.10, "INFO",  "SRD46-UI |    [iter 5] completed in 1.2s  (total 99s)"),
    # iter 6: search_ligands by class
    (0.10, "INFO",  "SRD46-UI |    [iter 6] Tool call(s): search_ligands"),
    (0.30, "DEBUG", "SRD46-server | search_ligands  ligand_class='amino acid' limit=100  -> 100 / 297 SQL matches  in 0.5s"),
    (0.10, "INFO",  "SRD46-compactor | [M] Hardcoded compactor used for search_ligands (16254 chars)"),
    (0.10, "INFO",  "SRD46-UI |    [iter 6] completed in 0.5s  (total 106s)"),
    # iter 7: build_catalog scoped to Zn
    (0.10, "INFO",  "SRD46-UI |    [iter 7] Tool call(s): build_system_catalog"),
    (0.30, "DEBUG", "SRD46-server | build_system_catalog  metal_id=metal_208  -> Zn catalog (5 ligands w/ Zn data)  in 2.6s"),
    (0.10, "INFO",  "SRD46-UI |    [iter 7] completed in 2.6s  (total 139s)"),
    # iter 8: planner with revision (gpt5, 57.2s)
    (0.10, "INFO",  "SRD46-UI | [>] agent iter=8 prompt_len=4120 memory_turns=15 elapsed=139s"),
    (0.20, "INFO",  "SRD46-UI |    [iter 8] Tool call(s): 0_plan_search_strategy  revision=True"),
    (0.40, "DEBUG", "SRD46-argo | planner   model=gpt5  reasoning... 57.2s"),
    (0.10, "INFO",  "SRD46-compactor | [M] Context window: 39534 chars across 23 turns"),
    (0.10, "INFO",  "SRD46-compactor | [M] Argo selected candidates [1, 2] for compression"),
    (0.10, "INFO",  "SRD46-compactor | [M] Running 2 compression task(s) in parallel"),
    (0.10, "INFO",  "SRD46-UI |    [iter 8] completed in 57.2s  (total 259s)"),
    # iter 9: parallel pka + stability with name list -> 0 rows
    (0.10, "INFO",  "SRD46-UI | [>] agent iter=9 prompt_len=2150 memory_turns=23 elapsed=331s"),
    (0.20, "INFO",  "SRD46-UI |    [iter 9] Running 2 tools in PARALLEL: search_pka_ligands, search_stability"),
    (0.20, "DEBUG", "SRD46-server | search_pka_ligands WHERE ligand_name_SRD IN ('Glycine','Alanine',...)  -> 0 rows  in 1.8s"),
    (0.10, "DEBUG", "SRD46-server | search_stability   WHERE metal_id=metal_208 AND ligand_name_SRD IN (...)  -> 0 rows  in 1.8s"),
    (0.10, "WARN",  "SRD46-UI | name-based SQL filter returned 0 rows; agent will broaden via ligand_class"),
    (0.10, "INFO",  "SRD46-UI |    [iter 9] completed in 1.8s  (total 337s)"),
    # iter 10: broaden via class -> success
    (0.10, "INFO",  "SRD46-UI | [>] agent iter=10 prompt_len=2280 memory_turns=27 elapsed=476s"),
    (0.20, "INFO",  "SRD46-UI |    [iter 10] Running 2 tools in PARALLEL: search_pka_ligands, search_stability"),
    (0.20, "DEBUG", "SRD46-server | search_pka_ligands WHERE ligand_class_name LIKE '%amino acid%'  -> 200 rows (19137 chars)  in 1.0s"),
    (0.20, "DEBUG", "SRD46-server | search_stability   WHERE metal_id=metal_208 AND ligand_class_name LIKE '%amino acid%'  -> 72 rows  in 2.5s"),
    (0.10, "INFO",  "SRD46-compactor | [M] Argo selected candidates [2, 3, 1] for compression"),
    (0.10, "INFO",  "SRD46-compactor | [M] Running 3 compression task(s) in parallel"),
    (0.10, "INFO",  "SRD46-UI |    [iter 10] completed in 2.5s  (total 484s)"),
    # final answer
    (0.10, "INFO",  "SRD46-UI | [>] agent iter=11 prompt_len=5910 memory_turns=31 elapsed=486s"),
    (0.30, "DEBUG", "SRD46-argo | call_argo  model=gpt54  prompt_chars=5910  reasoning... finalizing"),
    (0.10, "INFO",  "SRD46-UI | [<] agent finished without further tool calls (final answer)"),
    (0.10, "INFO",  "freeform-runner | Freeform query artifacts written under _output/Query/Model_demo/Qfree_simulated"),
    (0.10, "INFO",  "SRD46-eval | extract_run done; writing answer_batch1.md + tool_eval_batch1.md"),
    (0.10, "INFO",  "SRD46-eval | regex enricher done; claims_batch1.json (18 claims)"),
    (0.05, "INFO",  "[browser] Simulated run complete (no real Argo calls were made)"),
]


# Mermaid diagram drawn AFTER simulation completes (gated to status=completed).
# Reflects the full 13-step Q4.4 trajectory including the phase-gating error.
SIM_FLOW_MERMAID = """\
flowchart TD
    U([User prompt: predict best unstudied AA for Zn²⁺]) --> P0
    P0[<b>iter 1 — Pre-Plan</b><br/>0_preplan_decision<br/>task_type=multi-step]:::phase --> L0a

    subgraph L0a [iter 2 — L0 attempt #1 ‖]
        direction LR
        SM1[search_metals<br/>name='Zn(II), H+'<br/>0 hits]:::fail
        SL1[search_ligands<br/>name=AA list<br/>0 hits]:::fail
    end
    L0a --> ERR[<b>iter 3 — PHASE ERROR</b><br/>0_plan_search_strategy<br/>blocked: build_system_catalog required]:::error
    ERR --> BC0[<b>iter 4</b><br/>build_system_catalog &lpar;&rpar;<br/>error: needs metal_id]:::error
    BC0 --> SM2[<b>iter 5</b><br/>search_metals<br/>symbol='Zn' → metal_208]:::tool
    SM2 --> SL2[<b>iter 6</b><br/>search_ligands<br/>ligand_class='amino acid'<br/>100 / 297]:::tool
    SL2 --> BC1[<b>iter 7</b><br/>build_system_catalog<br/>metal_id=metal_208 → 5 ligands]:::tool
    BC1 --> PL[<b>iter 8 — Planner</b><br/>0_plan_search_strategy<br/>gpt5, 57.2s, revision=True]:::phase

    subgraph EX1 [iter 9 — exploratory ‖]
        direction LR
        PK1[search_pka_ligands<br/>WHERE name IN (...)<br/>0 rows]:::fail
        ST1[search_stability<br/>WHERE name IN (...)<br/>0 rows]:::fail
    end
    PL --> EX1
    EX1 --> EX2

    subgraph EX2 [iter 10 — broadened ‖]
        direction LR
        PK2[search_pka_ligands<br/>WHERE ligand_class LIKE '%amino acid%'<br/>200 rows]:::tool
        ST2[search_stability<br/>WHERE ligand_class LIKE '%amino acid%'<br/>72 rows]:::tool
    end
    EX2 --> CO[Compactors<br/>3 tasks in parallel]:::sys
    CO --> ANS([<b>Final answer</b>: methionine<br/>moderate confidence]):::done
    ANS --> EV[Eval pipeline<br/>extract_run → enrich_run_claims]:::sys

    classDef phase fill:#e7f1ff,stroke:#0d6efd,color:#0a3d8f;
    classDef tool  fill:#fff3cd,stroke:#caa204,color:#5c4400;
    classDef sys   fill:#f3e5f5,stroke:#8e24aa,color:#4a148c;
    classDef done  fill:#d4edda,stroke:#198754,color:#0f5132;
    classDef fail  fill:#fde2e4,stroke:#c8385f,color:#7a1f3a,stroke-dasharray:4 3;
    classDef error fill:#f8d7da,stroke:#a72734,color:#58151c,font-weight:bold;
"""
