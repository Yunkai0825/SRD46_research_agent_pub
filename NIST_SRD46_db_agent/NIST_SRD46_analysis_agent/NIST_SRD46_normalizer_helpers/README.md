# `NIST_SRD46_normalizer_helpers/`

Shared normalization helpers for the SRD-46 **analysis agent**. These
modules turn free / LLM-authored input into the *exact* canonical tokens
the downstream stages consume, so no agent ever has to guess a spelling or
an id. They live at the analysis-agent level (rather than inside any single
LC stage) because they are imported by more than one consumer.

```text
NIST_SRD46_normalizer_helpers/
  chemical_name_normalizer/      — free chemical text -> canonical metal/ligand
    normalizer.py                  (quick_fact tokenizer + ranking)
  constr_card_normalizer/        — LC3 constraint-card catalog + self-healer
    constr_variable_catalog.py     authoritative LC3 variable catalog
    constr_normalizer.py           LC3 pre-compile card self-healer
    system_catalog_normalizer.py   prune catalog to the realised card species
```

---

## `chemical_name_normalizer/`

A general-purpose chemical-name resolver that re-uses, unchanged, the three
normalization strategies the SRD-46 **query agent** relies on (metal name ->
symbol+charge, ligand name -> InChI/SMILES via RDKit+PubChemPy, and
`difflib`-based disambiguation). Exposed through a single `quick_fact`
entry point. No hard-coded chemistry lives here — all aliases, regexes and
lookups happen inside the query-agent helpers.

Consumer: `analysis_agent_orchestration/L1_subagent/l1_subagent.py`.

---

## `constr_card_normalizer/constr_variable_catalog.py` — authoritative LC3 variable catalog

`build_variable_catalog(report, system_catalog=None) -> VariableCatalog`

Builds the authoritative catalog of every variable the LC3 constraint /
initial-condition designer may reference, mirroring the lc3_2 card namespace
**exactly** (`s.E_V`, `s.pH`, `s.temperature`, `s.ionic_strength`,
`s.total["<id>"]`, `s.species["<id>"]`, `s.conc[...]`, `s.lnconc[...]`). The
catalog is derived from the solver's own `FreeEnergyReport` (via the
numcalc-side `build_default_catalog` / `merge_catalog_overrides`), i.e. the
same source the downstream solver consumes, so the ids always agree.

Returns a `VariableCatalog` carrying both the rendered prompt text and the
flat `components` / `species` id sets the card compiler validates against.

The numcalc import
(`sweep_pipelines._sweep_input_entry_point.constraint_compiler`) is done
lazily inside the function, so the module stays importable without the
numcalc path bootstrap until it is actually used.

Consumers: LC3_2 initial-condition agent and LC3_3 constraint agent (both
`from ....NIST_SRD46_normalizer_helpers.constr_card_normalizer.constr_variable_catalog import
build_variable_catalog`).

---

## `constr_card_normalizer/constr_normalizer.py` — LC3 pre-compile card self-healer

`normalize_card_source(source, *, components, species, intensives=None) -> str`

A conservative, **line-preserving** self-healer that fixes the surface
details an LLM reliably hallucinates *before* the strict allowlist / id walk
of the card compiler — handle spellings, oxidation-state tokens, `np.*`
functions, `"="` vs `"=="` operators, axis attribute access, and similar.
An already-canonical card is returned unchanged, so this only ever rescues
cards the compiler would otherwise reject. Cards are parsed with `ast` and
**never executed**.

It borrows the compiler's vocabulary (`_INTENSIVES`, `_STATE_SUBNS`,
`_FUNC_WHITELIST`) from
`...LC3_3_constraint_designer/_constraint_helpers/constr_code_card_compiler.py`
when available, and falls back to a local last-resort copy of those
constants so the module stays importable on its own.

Consumer: `constr_code_card_compiler.compile_card(..., normalize=True)`
(`from .....NIST_SRD46_normalizer_helpers.constr_card_normalizer.constr_normalizer import
normalize_card_source`).

---

## `constr_card_normalizer/system_catalog_normalizer.py` — catalog-vs-card reconciler

`prune_system_catalog_to_report(system_catalog, report) -> list[str]`

LC1 enumerates *every* plausible oxidation state per metal (e.g.
`Cu$+3`/`Cu$+2`/`Cu$+1`), while the LC2 card realises only the subset that
carries SRD-46 data. The solver's
`constraint_compiler.validate_catalog_against_report` rejects catalogs that
declare unrealised entries, so this module prunes those phantom
metals/ligands **in place** before the catalog is folded into the
calc-input card. It only ever removes entries absent from the card, so it
can never change the meaning of a constraint. Returns human-readable notes
describing each drop.

---

## Import / contract notes

- This is a namespace sub-package of `NIST_SRD46_analysis_agent`; consumers
  reference it with relative imports whose dot-count is measured from the
  consumer's own directory (e.g. `....` from an LC3 stage agent, `.....`
  from the LC3_3 `_constraint_helpers` compiler, `...` from an
  `analysis_agent_orchestration` subagent).
- The LC3 catalog/normalizer obey a strict **normalize-only-when-the-
  canonical-target-is-unambiguous** contract: ids always come from the
  solver report, and the normalizer leaves anything it cannot safely map
  untouched for the compiler to reject with a precise diagnostic.
