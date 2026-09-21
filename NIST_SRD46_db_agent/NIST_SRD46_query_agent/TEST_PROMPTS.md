# Test Prompts for the SRD-46 Chatbot

Researcher-style queries for validating the agentic chatbot.
Prompts are grouped by the kind of reasoning they demand.

---

## 1.1 — Direct Lookup (baseline)

These should succeed in 1–2 tool calls.

| # | Prompt |
|---|--------|
| 1.1.1 | What are the stability constants reported for the copper(II)–glycine system? |
| 1.1.2 | List all the pKa values that have been measured for citric acid. |
| 1.1.3 | Give me the full citation for the shortcut code "62Pc". |
| 1.1.4 | What stability constants are available for Ag⁺ with ammonia? |
| 1.1.5 | Look up the pKa values for oxalic acid. How many dissociation steps are there? |
| 1.1.6 | Search for all ligands in the "Amino Acids" class. How many are there? |

---

## 1.2 — Cross-Database & Provenance

Force the model to join information across the cards, equilibrium, and literature databases.

| # | Prompt |
|---|--------|
| 1.2.1 | For the Cu²⁺–EDTA measurement with the highest reported log K, trace back to the original publication. Who are the authors and when was it published? |
| 1.2.2 | How many independent literature sources have reported stability constants for the Cd²⁺–chloride system? Summarise the range of values and conditions. |
| 1.2.3 | Pick any equilibrium network that contains more than 5 nodes for a zinc complex and describe what species are involved. |
| 1.2.4 | For the Ni²⁺–EDTA system, how many distinct equilibrium networks exist? Pick the largest one and list all the VLM node IDs it contains. |
| 1.2.5 | Find a stability constant measurement for Pb²⁺–chloride that has at least 2 linked literature citations. List those citations with authors and year. |

---

## 2.1 — Comparison & Ranking

The model must pull data for multiple species and compare.

| # | Prompt |
|---|--------|
| 2.1.1 | Between EDTA and NTA, which ligand forms the more stable complex with Fe³⁺? Show the log K values side by side. |
| 2.1.2 | Rank the first-row divalent transition metals (Mn²⁺ through Zn²⁺) by their log β₁ with ammonia. Does the ordering follow the Irving–Williams series? |
| 2.1.3 | Compare the pKa values of glycine and alanine. Are they significantly different? |
| 2.1.4 | Compare the stability constants of Cu²⁺ with chloride ion vs bromide ion. Which halide forms a stronger copper complex? |
| 2.1.5 | Between ammonia and ethylenediamine, which ligand binds more strongly to Ni²⁺? Quantify the difference in log K. |
| 2.1.6 | Rank Cd²⁺, Pb²⁺, and Hg²⁺ by their log K with thiocyanic acid. Which soft metal has the highest affinity? |

---

## 2.2 — Schema Discovery & Data Profiling

The model must introspect the database before it can answer.

| # | Prompt |
|---|--------|
| 2.2.1 | What percentage of stability-constant measurements in the database were conducted at 25 °C? |
| 2.2.2 | Which metal ion has the largest number of different ligands studied? |
| 2.2.3 | Are there any ligands in the database that have more than 6 reported pKa values? What are they? |
| 2.2.4 | How many distinct ligand classes exist in the database? List the five classes with the most ligands. |
| 2.2.5 | What is the distribution of constant types (K, β, etc.) in the stability constant measurements? Show counts for each type. |
| 2.2.6 | How many metals in the database have fewer than 5 VLM measurements total? What fraction of all metals is that? |

---

## 3.1 — Indirect / Multi-Step Reasoning

The user never names a specific table, tool, or ID — the model must figure out
the lookup path on its own.

| # | Prompt |
|---|--------|
| 3.1.1 | I'm designing a chelation therapy protocol for lead poisoning. Which ligands in the database have the highest affinity for Pb²⁺, and are any of them used clinically? |
| 3.1.2 | If I wanted to selectively complex Cu²⁺ in the presence of Ni²⁺ at pH 7, which amino-acid ligand would give me the best selectivity ratio? |
| 3.1.3 | A colleague published a study on zinc–histidine equilibria around 2005. Can you find the citation and tell me what constants they reported? |
| 3.1.4 | How many distinct ligands have been studied with both iron(II) and iron(III)? For those ligands, is the complex consistently more stable with Fe³⁺? |
| 3.1.5 | I need to mask Ca²⁺ interference in a trace-metal analysis. Which ligands bind Ca²⁺ strongly but have relatively weak affinity for Cu²⁺? |
| 3.1.6 | Which carboxylic acid ligands form the most stable complexes with La³⁺? Find at least three and report their log K values. |
| 3.1.7 | Is there any data on cobalt(II) with bipyridine ligands? If so, how many independent measurements exist and what range of log K values do they span? |

---

## 3.2 — Thermodynamic Reasoning

These require the model to interpret or derive quantities, not just return raw numbers.

| # | Prompt |
|---|--------|
| 3.2.1 | Using the stepwise constants K₁ and K₂ for Cu²⁺–glycine, estimate the overall β₂. Compare your calculated value with the β₂ that is directly reported in the database. |
| 3.2.2 | For the Ni²⁺–ethylenediamine system, how does the stability constant change with ionic strength? Is there a clear trend? |
| 3.2.3 | Based on the pKa values of oxalic acid and the stability constant of Ca²⁺–oxalate, at what approximate pH would you expect calcium oxalate precipitation to become significant? |
| 3.2.4 | Survey the available Fe(II) and Fe(III) ligand systems in the database. What trend do you see in the stability constants across ligand classes, and what thermodynamic reasoning (e.g., hard/soft acid–base theory, chelate effect, crystal-field considerations) explains the ordering and edge cases? |
| 3.2.5 | The stability constant for Zn²⁺–EDTA is reported at several ionic strengths. Extrapolate the trend to I = 0 and compare with any zero-ionic-strength value in the database. |
| 3.2.6 | Using pKa values for malonic acid and the Cu²⁺–malonate log K, estimate the conditional stability constant at pH 4. Explain your calculation. |
| 3.2.7 | Compare the stepwise constants K₁, K₂, K₃, K₄ for Cu²⁺–ammonia. Do they decrease monotonically? What does this tell you about the coordination geometry? |

---

## 4 — Hypothesis Generation

The model must go beyond lookup and reasoning to propose hypotheses,
predict missing values, or identify patterns that suggest new experiments.

| # | Prompt |
|---|--------|
| 4.1 | Can you evaluate the complexation constants for DMF–Fe(II)/Fe(III), acetonitrile–Fe(II)/Fe(III), THF–Fe(II)/Fe(III), and ethylene glycol–Fe(II)/Fe(III)? If they are not available in the database, look at similar solvent/ligand systems with Fe²⁺ and provide a reasoned estimate. |
| 4.2 | Look at the stability constants for Hg²⁺ across different ligand classes. Can you form a hypothesis about whether Hg²⁺ prefers sulfur-donor, nitrogen-donor, or oxygen-donor ligands? Support your hypothesis with specific log K values from the database. |
| 4.3 | Compare the chelate effect across different metal ions: for Cu²⁺, Ni²⁺, and Zn²⁺, compare the stability of ethylenediamine complexes vs. ammonia complexes. Is the magnitude of the chelate effect (log K_en − 2·log K_NH₃) consistent across metals, or does it vary? Propose a hypothesis for any differences. |
| 4.4 | Based on the pKa values and stability constants available for amino-acid ligands, can you predict which amino acid not yet studied with Zn²⁺ would likely form the most stable zinc complex? Explain your reasoning. |
| 4.5 | Examine the relationship between ligand pKa values and their stability constants with Ca²⁺. Is there a correlation? Formulate a hypothesis about how basicity relates to binding strength for alkaline-earth metals. |
| 4.6 | The Irving–Williams series predicts a specific ordering of divalent transition-metal complex stability. Using data from the database, identify any metal–ligand systems that violate this ordering. Propose a hypothesis for why those exceptions occur. |
| 4.7 | For ligands that have been studied with both Co²⁺ and Co³⁺, compare the stability constants. Based on the magnitude of the difference and crystal-field theory, predict how a new polydentate amine ligand might behave with each oxidation state. |


---

## 5.1 — Ambiguous / Under-Specified (robustness)

These test whether the model asks for clarification or makes reasonable assumptions.

| # | Prompt |
|---|--------|
| 5.1.1 | Tell me about mercury complexes. |
| 5.1.2 | What's the binding constant for DTPA? |
| 5.1.3 | Compare iron and copper. |
| 5.1.4 | What data do you have on zinc? |
| 5.1.5 | Is EDTA a good chelator? |
| 5.1.6 | Show me something interesting about rare earth metals. |

---

## 5.2 — Negative / Edge-Case

Queries that should return "not found" or require the model to explain limitations.

| # | Prompt |
|---|--------|
| 5.2.1 | What is the stability constant of uranium(VI) with crown ethers? |
| 5.2.2 | Do you have any data on metal–protein binding (e.g., transferrin)? |
| 5.2.3 | What are the stability constants at 200 °C and 50 bar pressure? |
| 5.2.4 | Look up the stability constant of plutonium(IV) with aspirin. |
| 5.2.5 | What is the electrode potential of Cu²⁺/Cu⁰? |
| 5.2.6 | Find stability constants measured in supercritical CO₂ as solvent. |

---

## How to Use

1. Run an interactive session with `python agent_runtime.py`, or execute prompts in batch with `python run_batch_SRD46_query_db_subagent.py`.
2. For batch runs, select prompts by ID or section. Examples:

   ```bash
   python run_batch_SRD46_query_db_subagent.py 1.1.1
   python run_batch_SRD46_query_db_subagent.py 1.1.1 2.1.3 3.2.4
   python run_batch_SRD46_query_db_subagent.py --section 4
   python run_batch_SRD46_query_db_subagent.py -m gpt5 gpt54 -r 3 -j 4
   ```

3. Watch the log output to verify:
   - The correct tools are selected.
   - Multi-step prompts trigger multiple sequential tool calls.
   - Comparison prompts pull data for all requested species.
   - The final answer cites real values (not hallucinated).
4. Check `_output/` for generated result, history, and ref-ID files, and `transcripts/` for interactive-session transcripts.
5. If you want post-run claim extraction and stats publication, run `python run_batch_output_claim_eval_subagent.py --model gpt54 --question Q1.1.1 --workers 1 --force` or call the orchestrator module directly.
6. Run automated tests with `pytest -q tests` or `pytest -q DEBUG_test_scripts`.

### Expected tool-call counts (approximate)

| Section | Typical calls per prompt |
|---------|------------------------:|
| 1.1 — Direct Lookup | 1–2 |
| 1.2 — Cross-Database & Provenance | 3–5 |
| 2.1 — Comparison & Ranking | 2–4 |
| 2.2 — Schema Discovery | 1–3 (SQL) |
| 3.1 — Indirect / Multi-Step | 3–6 |
| 3.2 — Thermodynamic Reasoning | 2–7 |
| 4 — Hypothesis Generation | 3–8 |
| 5.1 — Ambiguous | 1–3 |
| 5.2 — Negative / Edge-Case | 1–2 |
