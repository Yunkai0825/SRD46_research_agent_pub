# Chemistry rule library

Edit rules in the module for their family. `srd46_pipeline/manual_rules.py` remains a small compatibility facade for existing pipeline and legacy-parser imports; it re-exports the same objects, with no duplicate rule tables.

| Module | Contents |
|---|---|
| `registry.py` | Shared `Rule` type, `RULES`, registration, stable ledger IDs |
| `sources.py` | SRC: authoritative MySQL dump selection and source audit policy |
| `source_corrections.py` | SRC-02: guarded archived beta curation and deterministic beta/metal/solvent markup normalization |
| `measurements.py` | VLM/NOTE: numeric normalization, guarded source-row corrections, published provenance |
| `ligands.py` | LIG: name recovery, pinned structures, stereochemistry, placeholders |
| `metals.py` | MET: metal SMILES and organic substituents |
| `hxl.py` | HXL: protonation and molfile charge reconciliation |
| `policies.py` | REF/QUP: reference conditions and Qupkake archive policy |
| `beta_names.py` | BETA-02: definition text fixes and missing-row recovery |
| `beta_tokens.py` | BETA-04: explicit species/component mappings |
| `beta_corrections.py` | BETA-03: equation-side corrections and retained history |
| `beta_unresolved.py` | BETA-01: unresolved candidates, evidence, orphan references |
| `validation.py` | Cross-family validation and CLI rule descriptions |

Each family imports the shared registry directly. Validation imports the families after their declarations; family modules must not import the compatibility facade. `__all__` defines each module's public API. When adding a public helper or register, also export it through the package's `__all__`.

Rules retain their historical provenance identifiers, `manual_rules.<RULE-ID>`, so existing audit queries keep working. Raw source files remain unchanged; derived values and source-backed repairs are recorded in staging and carried into card notes.

```powershell
python -B run_srd46_pipeline.py --list-rules
python -B -u run_srd46_pipeline.py --stages all --pubchem cache-only
```

Retained beta-definition decisions and unresolved evidence are recorded in [beta_corrections.py](beta_corrections.py) and [beta_unresolved.py](beta_unresolved.py). Descriptor chemistry and validation are implemented in [the ligand-similarity stage](../../pip2_SQL_assembler_SRD46/pip2d_ligand_similarity/).
