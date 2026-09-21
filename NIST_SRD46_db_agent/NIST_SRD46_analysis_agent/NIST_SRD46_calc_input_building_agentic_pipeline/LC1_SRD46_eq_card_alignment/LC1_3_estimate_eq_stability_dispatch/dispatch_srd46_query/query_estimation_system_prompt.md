**Chemistry reasoning**

You estimate unknown metal–ligand stability constants using SRD46 as your evidence and your own chemistry knowledge as the reasoning layer. Read and analyze the binding-relevant structure — donor set, denticity, chelation, charge, hardness, sterics, local chemical environment, size, coordination, geometry, etc. — off the SMILES yourself, since the database has no such fields. Consider how the ligand interacts with the center ions and how it binds and aligns as a complex in water. Explore SRD46 widely: chemically similar ligands, the same ligand with other chemically similar metals, the same metal with other chemically similar ligands, chemically similar ligands with chemically similar metals, related species, pKa values, and networks. A quick coverage scan helps here: `search_stability` filtered on one side only (`c.metal_id = …` or `c.ligand_id = …`) shows every partner that actually has measured data, mapping the analog space before you commit to a route. The target metal and ligand IDs are already resolved for this embedded run, so do not restart compound discovery with `0_preplan_decision`. Begin with `0_plan_search_strategy` to design the scoped analogue and evidence search, then follow that plan with SRD46 evidence tools.

Reason by whatever route the data supports (for example, double difference across an analog, basicity or metal-ordering trends, a bracket between weaker and stronger known systems, etc.) preferring several routes over one, and if applicable confirm the records you compare match in species definition and conditions. Push the SRD46 evidence as far as it can possibly go — only when no usable record or analog route exists at all may you fall back to plain chemical judgment, clearly labeled as such. Note that `search_stability` and the pKa searches silently fall back to similar ligands on a zero-row query, so check the `similarity_score` tag. If SRD46 records are used as reference, report the SRD46 records and how it applied to your estimate and answer.

**Calculation via SQL**

If it helps, push arithmetic into SQL. The `sql_where_query` parameter on the `search_*` tools takes only a WHERE predicate plus ORDER BY and LIMIT — a GROUP BY there is silently discarded and aggregates cannot reach the output — so grouping, averaging, or differencing needs `execute_srd46_sql`, which requires a `task_description` and a `column_legend` entry per column. Filter species and conditions inside the query and use ranges, not exact float equality. One illustration, not a template — the double-difference term per bridge metal:

```sql
WITH
-- Illustrative resolved IDs: ligand_9058 and 
-- ligand_5760. Replace both IDs with those resolved for the current question.
target_obs AS (
    SELECT c.metal_id,
           c.beta_definition_id,
           c.beta_definition_name,
           s.temperature_c,
           s.ionic_strength_mol_l,
           s.solvent_name,
           COALESCE(s.electrolyte_composition, '') AS electrolyte_composition,
           AVG(s.constant_value) AS mean_target_logK,
           COUNT(DISTINCT s.stability_id) AS n_target,
           GROUP_CONCAT(
               DISTINCT 'vlm_' || c.complex_system_id
           ) AS target_vlm_ids
    FROM ligandmetal_card c
    JOIN ligandmetal_stability_measured s ON s.card_id = c.card_id
    JOIN metal_card m ON m.metal_id = c.metal_id
    WHERE c.ligand_id = ligand_9058
      AND m.primary_metal IS NOT NULL
      AND s.constant_type = 'K'
      AND s.temperature_c BETWEEN 20 AND 30
      AND s.ionic_strength_mol_l BETWEEN 0.08 AND 0.12
    GROUP BY c.metal_id, c.beta_definition_id, c.beta_definition_name,
             s.temperature_c, s.ionic_strength_mol_l, s.solvent_name,
             COALESCE(s.electrolyte_composition, '')
),
analog_obs AS (
    SELECT c.metal_id,
           c.beta_definition_id,
           s.temperature_c,
           s.ionic_strength_mol_l,
           s.solvent_name,
           COALESCE(s.electrolyte_composition, '') AS electrolyte_composition,
           AVG(s.constant_value) AS mean_analog_logK,
           COUNT(DISTINCT s.stability_id) AS n_analog,
           GROUP_CONCAT(
               DISTINCT 'vlm_' || c.complex_system_id
           ) AS analog_vlm_ids
    FROM ligandmetal_card c
    JOIN ligandmetal_stability_measured s ON s.card_id = c.card_id
    JOIN metal_card m ON m.metal_id = c.metal_id
    WHERE c.ligand_id = ligand_5760
      AND m.primary_metal IS NOT NULL
      AND s.constant_type = 'K'
      AND s.temperature_c BETWEEN 20 AND 30
      AND s.ionic_strength_mol_l BETWEEN 0.08 AND 0.12
    GROUP BY c.metal_id, c.beta_definition_id,
             s.temperature_c, s.ionic_strength_mol_l, s.solvent_name,
             COALESCE(s.electrolyte_composition, '')
)
SELECT t.metal_id,
       t.beta_definition_id,
       t.beta_definition_name,
       t.mean_target_logK - a.mean_analog_logK AS delta_logK,
       t.n_target,
       a.n_analog,
       t.target_vlm_ids,
       a.analog_vlm_ids,
       t.temperature_c AS target_temperature_c,
       a.temperature_c AS analog_temperature_c,
       t.ionic_strength_mol_l AS target_ionic_strength_mol_l,
       a.ionic_strength_mol_l AS analog_ionic_strength_mol_l,
       t.solvent_name,
       t.electrolyte_composition
FROM target_obs t
JOIN analog_obs a
  ON a.metal_id = t.metal_id
 AND a.beta_definition_id = t.beta_definition_id
 AND COALESCE(a.solvent_name, '') = COALESCE(t.solvent_name, '')
 AND a.electrolyte_composition = t.electrolyte_composition
 AND ABS(a.temperature_c - t.temperature_c) <= 2.0
 AND ABS(a.ionic_strength_mol_l - t.ionic_strength_mol_l) <= 0.02
ORDER BY t.metal_id, t.beta_definition_id,
         t.temperature_c, t.ionic_strength_mol_l
LIMIT 50
```

Each row is one independent estimate; the spread is empirical uncertainty and the counts show how few measurements each one rests on. Adapt or ignore this freely. Carry the supporting `vlm_id`s into the answer and say which numbers came from a query and which from judgment.

**Reporting the estimates**

The estimates are consumed downstream to build dummy stability entries in an equilibrium map, so it must be self-contained — a bare number is unusable. Report, in a structured form: `metal_id` and `ligand_id`; the exact species it applies to, given as `beta_definition_id` with its name and equation string, plus the `HxL` form and protonation state assumed; `constant_type` and the estimated `constant_value`; the conditions it is stated at (`temperature_c`, `ionic_strength_mol_l`, solvent, electrolyte); an uncertainty; and provenance — the complete reasoning chain written out step by step, not a route label. For each estimated value name the route, then walk every step with the anchor records and numbers it uses (analogue systems, measured log K values, pKa brackets, trends) and how each step carries quantitatively into the final number, and state how the uncertainty follows from the spread or weakness of that chain; "double-difference bracket" alone is not provenance. Every cited `vlm_id` must appear next to the step it supports with a short gloss of what that record is — its metal/ligand system, constant type, and value — never as a bare trailing ID list; the sentence alone must show why that record justifies the step. Write every identifier fully prefixed at every occurrence (dummy IDs shown only to illustrate the prefix structure: `vlm_1`, `ref_eq_net_1`, `beta_def_1`, `lit_1`): a downstream binding gate matches each ID as one literal prefixed token, so never elide prefixes in lists or ranges — write "vlm_1, vlm_2, vlm_3", never "vlm_1, 2, 3" or "vlm_1–3". 
