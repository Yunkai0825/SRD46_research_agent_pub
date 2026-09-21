"""free_energy_md_card_generation.py
Parsable Markdown Free-Energy Card Generator.

Extracts metadata from raw JSON input and generates a machine-parsable
markdown card containing notation, components, canonical references,
settings, and standard chemical potentials.
"""

import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from thermodynamics_helpers.gibbs_value_calc_from_logK_eq_map_helpers.free_energy_network_calc_helper import (
    FreeEnergyReport,
    SpeciesEnergy,
    ComponentMeta,
    ValenceGroup,
    ValenceGroupEntry,
    LigandMicroValence,
)


# ══════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════

def _stoich_str(
    stoich: Dict[str, int],
    stoich_hlx: Optional[List[Tuple[str, int]]] = None,
) -> str:
    """Bracket-tokenized stoich display.

    When *stoich_hlx* is provided, renders the grouped HxLy format::

        [Cu$+2]:+2, [H-1L2]:+1, [L2]:+1

    Otherwise falls back to the flat stoich dict::

        [Cu$+2]:+1, [L2]:+1, [H]:-1
    """
    if stoich_hlx:
        parts = [f"{_render_hlx_bracket(key)}:{count:+d}" for key, count in stoich_hlx]
        return ", ".join(parts) if parts else "\u2014"
    if not stoich:
        return "\u2014"
    parts = []
    for k in sorted(stoich, key=lambda k: (2 if k == "H" else 1 if k.startswith("L") else 0, k)):
        parts.append(f"[{k}]:{stoich[k]:+d}")
    return ", ".join(parts)


def _species_calc_source(se: "SpeciesEnergy") -> str:
    """One-cell provenance string for a species row in Section 5.

    Reference species (defining the μ°≡0 frame) get a short rule tag.
    Derived species show the VLM ID(s) used in their logβ calculation.

    Format:
    - Derived species (logβ from VLM records): ``"vlm_93862"`` or ``"vlm_93862, vlm_93847"``
    - Metal reference (logβ≡0, R1):            ``"R1: μ°≡0 (aquo-ion ref)"``
    - Ligand reference (logβ≡0, R4):           ``"R4: μ°≡0 (free-ligand ref)"``
    """
    # Enabled support compilation adds an in-memory source attribute.  The
    # legacy MD reader reconstructs SpeciesEnergy and cannot retain arbitrary
    # attributes, so the same exact label is also recognized in the serialized
    # note marker.  Keep this dependency-free so the disabled path does not
    # import the optional compiler package.
    estimated_source = "SRD46 query estimated values"
    if getattr(se, "source", "") == estimated_source:
        return estimated_source
    if '"source":"SRD46 query estimated values"' in (se.additional_notes or ""):
        return estimated_source
    if se.vlm_id:
        return f"{se.vlm_id}"
    has_ligand = any(k.startswith("L") for k in se.stoich)
    has_metal  = any(k != "H" and not k.startswith("L") for k in se.stoich)
    if has_ligand and not has_metal:
        return "R4: μ°≡0 (free-ligand ref)"
    return "R1: μ°≡0 (aquo-ion ref)"


def _hxl_bracket_str(h_count: int, ligand_id: str) -> str:
    """Format canonical HxL as bracket notation, e.g. '[[H]3[L2]]', '[[H][L1]]', '[[L1]]'.

    Outer brackets denote the combined species (e.g. [[H][L1]] = glycine),
    distinguishing it from separate components ([H][L1] = H⁺ + L1⁻).
    """
    if h_count == 0:
        return f"[[{ligand_id}]]"
    h_display = "" if h_count == 1 else str(h_count)
    return f"[[H]{h_display}[{ligand_id}]]"


_EMPTY = "***"   # placeholder for empty fields


def _cell(value: str) -> str:
    """Return *value* if non-empty, else the placeholder ``***``."""
    return value if value else _EMPTY


def _tokenize_name(name: str) -> str:
    """Wrap a component name in brackets with charge suffix.

    Cu2+ → [Cu]2+,  MeHg+ → [MeHg]+,  Glycine → [Glycine],  OH- → [OH]-
    """
    m = re.match(r'^(.+?)(\d*[+-])$', name)
    if m:
        return f"[{m.group(1)}]{m.group(2)}"
    return f"[{name}]"


def _tokenize_label(label: str) -> str:
    """Wrap a species label in bracket-charge format for Section 5 tables.

    Already-bracketed labels like [Cu(OH)]+ are left as-is.
    Simple ions like Cu2+ → [Cu]2+.
    Neutral species like HGlycine → [HGlycine].
    Solid suffix (s) handled: Cu(OH)2(s) → [Cu(OH)2](s).
    """
    if label.startswith("["):
        return label  # already bracketed
    # Handle solid suffix
    solid = ""
    base = label
    if base.endswith("(s)"):
        solid = "(s)"
        base = base[:-3]
    # Try to split off charge suffix
    m = re.match(r'^(.+?)(\d*[+-])$', base)
    if m:
        return f"[{m.group(1)}]{m.group(2)}{solid}"
    return f"[{base}]{solid}"


_TOK_COUNT_RE = re.compile(r'^(.+?)\((\d+)\)$')  # e.g. Cu$+1(2)
_OH_COUNT_RE  = re.compile(r'^(OH)(\d+)$')        # e.g. OH2
_H_COUNT_RE   = re.compile(r'^(H)(\d+)$')         # e.g. H3
_HXL_SEG_RE   = re.compile(r'^H(-?\d*)(L\d+)$')  # e.g. H-1L2, H2L1, HL1


def _render_hlx_bracket(key: str) -> str:
    """Render a stoich key with nested brackets for HxLy groups.

    HxLy keys → ``[[H]2[L1]]``; regular keys → ``[Cu$+2]``.
    """
    m = _HXL_SEG_RE.match(key)
    if m:
        h_digits = m.group(1)
        lig = m.group(2)
        h_display = "" if (not h_digits or h_digits == "1") else h_digits
        return f"[[H]{h_display}[{lig}]]"
    return f"[{key}]"

def _tokenize_species_id(sid: str) -> str:
    """Convert internal species_id to bracket-tokenized display format.

    Cu$+2(2).L2(2).z-2       -> [Cu$+2]2.[L2]2.[z-2]
    Cu$+1(2).OH2.z+0(s)      -> [Cu$+1]2.[OH]2.[z+0]_(s)
    Fe$+3.L1.H.z+3           -> [Fe$+3].[L1].[H].[z+3]
    """
    solid = ""
    if sid.endswith("(s)"):
        solid = "_(s)"
        sid = sid[:-3]
    tokens = sid.split(".")
    result = []
    for tok in tokens:
        # Charge token: z+N or z-N
        if tok.startswith("z"):
            result.append(f"[{tok}]")
            continue
        # Component with count in parens: Cu$+1(2), L2(2), H-1L2(2)
        m = _TOK_COUNT_RE.match(tok)
        if m:
            result.append(f"{_render_hlx_bracket(m.group(1))}{m.group(2)}")
            continue
        # OH with count suffix: OH2, OH3, ...
        m = _OH_COUNT_RE.match(tok)
        if m:
            result.append(f"[OH]{m.group(2)}")
            continue
        # H with count suffix: H2, H3, ...
        m = _H_COUNT_RE.match(tok)
        if m:
            result.append(f"[H]{m.group(2)}")
            continue
        # HxLy groups and simple tokens: Cu$+2, L1, H, OH, H-1L2, etc.
        result.append(_render_hlx_bracket(tok))
    return ".".join(result) + solid


# ══════════════════════════════════════════════════════════════════
#  Section 6: Validation — Equilibrium Map Coverage
# ══════════════════════════════════════════════════════════════════

def _write_eq_map_validation(w, report: "FreeEnergyReport") -> None:
    """Write Section 6 — Equilibrium Map Coverage.

    Lists every raw equilibrium entry from the eq map, its stepwise logK,
    VLM source, inclusion flag, and which species in the free-energy card
    reference this VLM in their cumulative chain.  A summary counts how
    many entries were resolved into species vs. left unresolved.
    """
    w("## 6. Validation: Equilibrium Map Coverage")
    w("")

    eq_meta_list = report.equilibrium_meta or []
    all_species = list(report.species)

    # Build vlm_id → [species labels] map from all species
    vlm_to_labels: Dict[str, List[str]] = {}
    for se in all_species:
        if not se.vlm_id:
            continue
        tok_lbl = _tokenize_label(se.label)
        for vlm in se.vlm_id.split(","):
            vlm = vlm.strip()
            if vlm:
                vlm_to_labels.setdefault(vlm, [])
                if tok_lbl not in vlm_to_labels[vlm]:
                    vlm_to_labels[vlm].append(tok_lbl)

    # Counts
    n_total    = len(eq_meta_list)
    n_included = sum(1 for em in eq_meta_list if em.include)
    n_excluded = n_total - n_included
    n_resolved = sum(
        1 for em in eq_meta_list
        if em.include and em.db_id in vlm_to_labels
    )
    n_chain_only = sum(
        1 for em in eq_meta_list
        if em.include and em.db_id in vlm_to_labels
        and not any(
            # "chain-only" = VLM appears in a chain but not as the sole VLM
            # (i.e. at least one species has more than one VLM in its chain)
            len(se.vlm_id.split(",")) > 1
            for se in all_species
            if em.db_id in se.vlm_id
        )
    )
    n_unresolved = n_included - n_resolved

    w("### 6.1 Summary")
    w("")
    w("| metric | count |")
    w("|--------|-------|")
    w(f"| Total eq-map entries | {n_total} |")
    w(f"| Included in calculation | {n_included} |")
    w(f"| Excluded (include_calculation=false) | {n_excluded} |")
    w(f"| Resolved → ≥1 species in card | {n_resolved} |")
    w(f"| Unresolved (no species in card) | {n_unresolved} |")
    w("")

    w("### 6.2 Per-Entry Detail")
    w("")
    w("| # | vlm_id | equation | stepwise_logK | T_°C | I_M | included | species_in_card |")
    w("|---|--------|----------|---------------|------|-----|----------|-----------------|")

    for i, em in enumerate(eq_meta_list, 1):
        incl_str = "yes" if em.include else "no"
        resolved_labels = vlm_to_labels.get(em.db_id, [])
        if resolved_labels:
            resolved_str = ", ".join(resolved_labels)
        else:
            resolved_str = "—" if em.include else "(excluded)"
        eq_str = em.equation_str.replace("|", "\\|")  # escape pipe in MD
        w(f"| {i} | {em.db_id} | {eq_str} "
          f"| {em.log_K:+.4f} | {em.T_source_C:.1f} | {em.I_source_M:.3f} "
          f"| {incl_str} | {resolved_str} |")

    w("")


# ══════════════════════════════════════════════════════════════════
#  Parsable Markdown Free Energy Card Generator
# ══════════════════════════════════════════════════════════════════

def generate_free_energy_card_md(
    report: FreeEnergyReport,
    *,
    system_name: str = "",
) -> str:
    """Generate a machine-parsable markdown card for the free energy analysis.

    The card contains:
    - Notation conventions
    - Component metadata with database references
    - Canonical reference states (with rule book strategy)
    - Settings (T, I, Kw, 2.303RT)
    - Standard chemical potentials table (μ°_free, μ°_canon)
    - Formation reaction free energies table
    - Equilibrium map metadata (nested under database name)

    All tables use pipe-delimited markdown format for reliable parsing.
    """
    if not report.solvents:
        raise ValueError(
            "FreeEnergyReport.solvents is Not defined; card generation may not "
            "manufacture a default water solvent")
    lines: List[str] = []
    w = lines.append

    # ── Header ────────────────────────────────────────────────
    w("# Free Energy Analysis Card")
    w("")
    if system_name:
        w(f"**System**: {system_name}")
    metals_str = ", ".join(_tokenize_name(n) for n in report.metal_names)
    ligands_str = ", ".join(_tokenize_name(n) for n in report.ligand_names)
    w(f"**Metals**: {metals_str}")
    w(f"**Ligands**: {ligands_str}")
    w(f"**Generated**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    w("")

    # ── Section 1: Notation Conventions ───────────────────────
    w("## 1. Notation Conventions")
    w("")
    w("| Symbol | Meaning |")
    w("|--------|---------|")
    w("| M0 | Always H⁺ (proton reference, pH-controlled) |")
    for i, mid in enumerate(report.metal_ids):
        w(f"| {mid} | Metal component: {_tokenize_name(report.metal_names[i])} |")
    w("| L0 | Always OH⁻ (derived from Kw) |")
    for j, lid in enumerate(report.ligand_ids):
        w(f"| {lid} | Ligand component: {_tokenize_name(report.ligand_names[j])} |")
    w("| H | Net proton count (H⁺); negative values denote hydroxide (OH⁻) contributions |")
    w("| μ°_free | Standard chemical potential (kJ/mol) with free-component reference (metal aquo ion, free ligand) |")
    w("| μ°_canon | Standard chemical potential (kJ/mol) with canonical HₓL ligand reference |")
    w("| μ°_eff | Effective chemical potential at a given pH: μ°_canon + r × 2.303RT × pH |")
    w("| stoich | Stoichiometry dictionary mapping component keys to integer coefficients |")
    w("| log_beta | Cumulative formation constant log₁₀(β) from free components |")
    w("| (s) | Solid/dissolution phase |")
    w("")
    w("### Species ID Convention")
    w("")
    w("Species IDs are dot-separated bracket-tokenized component keys:")
    w("")
    w("- Each component wrapped in brackets: `[Cu$+2]`, `[L1]`, `[H]`, `[OH]`")
    w("- Count > 1 after closing bracket: `[Cu$+2]2`, `[L1]3`, `[OH]2`")
    w("- Negative H rendered as OH: `[OH]`, `[OH]2`, `[OH]3`")
    w("- Charge in brackets: `[z+2]`, `[z-1]`, `[z+0]`")
    w("- Solids: `_(s)` suffix")
    w("- Collision disambiguation: `[1]`, `[2]` (log_beta descending); "
      "cross-card SRD-SRD duplicates: `.dup1`, `.dup2` id suffix + "
      "label `@<T>C` frame tag + `[srd_<set> r/n frame|data]` note "
      "(full trace in srd_srd_duplicates.json)")
    w("")
    w("### Reference State Rules")
    w("")
    w("| Rule | Description |")
    w("|------|-------------|")
    w("| R1 | Metal reference: μ°(Mᵢ) = 0 for free aquo ion |")
    w("| R2 | Proton reference: μ°(H⁺) = 0 |")
    w("| R3 | Hydroxide: μ°(OH⁻) = 2.303RT × \\|Kw\\| (derived from water) |")
    w("| R4 | Ligand canonical: μ°(HₓLⱼ) = 0 where x = declared canonical_H |")
    w("| R5 | μ°_canon = μ°_free + Σⱼ qⱼ × 2.303RT × logβ(HₓLⱼ) |")
    w("")

    # ── Section 2: Components ─────────────────────────────────
    w("## 2. Components")
    w("")

    # 2.1 Solvent
    w("### 2.1 Solvent")
    w("")
    for solv in report.solvents:
        w(f"#### {solv.internal_id}: {solv.name} (db_id: {solv.db_id})")
        w("")
        w("| property | value |")
        w("|----------|-------|")
        w(f"| name | {solv.name} |")
        w(f"| formula | {solv.formula} |")
        sd_str = "true" if solv.self_dissociation else "false"
        w(f"| self_dissociation | {sd_str} |")
        if solv.self_dissociation:
            w(f"| dissociation_reaction | {solv.dissociation_reaction} |")
            w(f"| pK | {solv.pK:.2f} |")
            w(f"| K_log10 | {solv.K_log10:.2f} |")
        w("")
        if solv.self_dissociation and solv.dissociation_species:
            w("| internal_id | name | charge | stoich_coeff | db_id |")
            w("|-------------|------|--------|-------------|-------|")
            # Look up H+ and OH- from component_meta
            cm_by_id = {cm.internal_id: cm for cm in report.component_meta}
            for sp_id in solv.dissociation_species:
                cm = cm_by_id.get(sp_id)
                if cm:
                    # Use known db_ids for H+ and OH-
                    db_id = cm.db_id
                    if not db_id:
                        if cm.name == "H+" or sp_id == "M0":
                            db_id = "metal_68"
                        elif cm.name == "OH-" or sp_id == "L0":
                            db_id = "ligand_10076"
                    w(f"| {cm.internal_id} | {_tokenize_name(cm.name)} | {cm.charge:+d} | +1 | {_cell(db_id)} |")
            w("")

    # 2.2 Metals (real metals only, M0=H+ is under Solvent)
    w("### 2.2 Metals")
    w("")
    w("| internal_id | name | charge | total_M | db_source | db_id |")
    w("|-------------|------|--------|---------|-----------|-------|")
    for cm in report.component_meta:
        if cm.comp_type == "metal" and cm.internal_id != "M0":
            total_text = (f"{cm.total:.4g}"
                          if isinstance(cm.total, (int, float))
                          else str(cm.total))
            w(f"| {cm.internal_id} | {_tokenize_name(cm.name)} | {cm.charge:+d} "
              f"| {total_text} | {_cell(cm.db_source)} | {_cell(cm.db_id)} |")
    w("")

    # 2.3 Ligands (real ligands only, L0=OH- is under Solvent)
    w("### 2.3 Ligands")
    w("")
    w("| internal_id | name | charge | total_M | canonical_HxL | db_source | db_id | smiles |")
    w("|-------------|------|--------|---------|---------------|-----------|-------|--------|")
    for cm in report.component_meta:
        if cm.comp_type == "ligand" and cm.internal_id != "L0":
            hol_str = ""
            if cm.canonical_HOL:
                h = cm.canonical_HOL.get("H", 0)
                hol_str = _hxl_bracket_str(h, cm.internal_id)
            total_text = (f"{cm.total:.4g}"
                          if isinstance(cm.total, (int, float))
                          else str(cm.total))
            w(f"| {cm.internal_id} | {_tokenize_name(cm.name)} | {cm.charge:+d} "
              f"| {total_text} | {_cell(hol_str)} "
              f"| {_cell(cm.db_source)} | {_cell(cm.db_id)} | {_cell(cm.smiles)} |")
    w("")

    # 2.4 Metal Valence Alignment (only when multiple oxidation states exist)
    if report.valence_groups:
        w("### 2.4 Metal Valence Alignment")
        w("")
        w("Groups metals of the same element by oxidation state. "
          "The reference state (μ° ≡ 0) is the charge closest to 0, "
          "then +1, −1, +2, −2, …  Editable: change `is_reference` "
          "to reassign the reference oxidation state.")
        w("")
        w("| element | internal_id | name | charge | is_reference | n_valences |")
        w("|---------|-------------|------|--------|--------------|------------|")
        for vg in report.valence_groups:
            for entry in vg.entries:
                ref_str = "true" if entry.is_reference else "false"
                w(f"| {vg.element} | {entry.internal_id} | {_tokenize_name(entry.name)} "
                  f"| {entry.charge:+d} | {ref_str} | {vg.n_valences} |")
        w("")

    # 2.5 Ligand Micro-Valence (only when RDKit analysis is available)
    if report.ligand_micro_valences:
        w("### 2.5 Ligand Micro-Valence Analysis")
        w("")
        w("Per-atom oxidation-state analysis of organic ligands "
          "(via electronegativity assignment). "
          "Dynamic atoms have multiple distinct OS values and may "
          "participate in redox reactions.")
        w("")
        w("| ligand_id | ligand_name | smiles | atom_element | oxidation_states | is_dynamic |")
        w("|-----------|-------------|--------|-------------|------------------|------------|")
        for mv in report.ligand_micro_valences:
            for elem_sym in sorted(mv.atom_os_summary):
                os_list = mv.atom_os_summary[elem_sym]
                os_str = ", ".join(str(v) for v in os_list)
                dyn = "true" if elem_sym in mv.dynamic_atoms else "false"
                w(f"| {mv.ligand_id} | {_tokenize_name(mv.ligand_name)} | {mv.smiles} "
                  f"| {elem_sym} | [{os_str}] | {dyn} |")
        w("")

    # ── Section 3: Canonical Reference States ─────────────────
    w("## 3. Canonical Reference States")
    w("")

    # 3.1 Component Reference Declarations (ALL components)
    w("### 3.1 Component Reference Declarations")
    w("")
    w("| component_id | name | type | reference_form | mu0_ref_kJ | rule | element | charge | is_valence_ref |")
    w("|-------------|------|------|----------------|------------|------|---------|--------|----------------|")

    # Build valence-group lookup for enrichment
    _vg_lookup: Dict[str, Tuple[str, bool]] = {}
    if report.valence_groups:
        for vg in report.valence_groups:
            for entry in vg.entries:
                _vg_lookup[entry.internal_id] = (vg.element, entry.is_reference)

    # M0 = H+ (R2)
    w(f"| M0 | [H]+ | proton | [H]+(aq) | +0.0000 | R2 | {_EMPTY} | +1 | {_EMPTY} |")
    # Real metals (R1)
    cm_by_id = {cm.internal_id: cm for cm in report.component_meta}
    for i, mid in enumerate(report.metal_ids):
        mname = report.metal_names[i]
        tname = _tokenize_name(mname)
        cm = cm_by_id.get(mid)
        charge_val = cm.charge if cm else 0
        elem, is_ref = _vg_lookup.get(mid, ("", False))
        is_ref_str = "true" if is_ref else ("false" if mid in _vg_lookup else _EMPTY)
        w(f"| {mid} | {tname} | metal | {tname}(aq) | +0.0000 | R1 "
          f"| {_cell(elem)} | {charge_val:+d} | {is_ref_str} |")
    # L0 = OH- (R3)
    mu_OH = report.factor * (-report.Kw_log)
    w(f"| L0 | [OH]- | hydroxide | [OH]-(aq) from Kw | {mu_OH:+.4f} | R3 | {_EMPTY} | -1 | {_EMPTY} |")
    # Real ligands canonical HxL (R4)
    if report.rulebook:
        for j, lid in enumerate(report.ligand_ids):
            lig_idx = int(lid[1:])
            ref = report.rulebook.refs.get(lig_idx)
            lname = report.ligand_names[j]
            tname = _tokenize_name(lname)
            cm = cm_by_id.get(lid)
            lcharge = cm.charge if cm else 0
            if ref:
                canonical_form = _hxl_bracket_str(ref.canonical_H, lid)
                w(f"| {lid} | {tname} | ligand_canonical | {canonical_form} | +0.0000 | R4 "
                  f"| {_EMPTY} | {lcharge:+d} | {_EMPTY} |")
            else:
                w(f"| {lid} | {tname} | ligand | {tname}(aq) | +0.0000 | R4 "
                  f"| {_EMPTY} | {lcharge:+d} | {_EMPTY} |")
    else:
        for j, lid in enumerate(report.ligand_ids):
            lname = report.ligand_names[j]
            tname = _tokenize_name(lname)
            cm = cm_by_id.get(lid)
            lcharge = cm.charge if cm else 0
            w(f"| {lid} | {tname} | ligand | {tname}(aq) | +0.0000 | R4 "
              f"| {_EMPTY} | {lcharge:+d} | {_EMPTY} |")
    w("")

    # 3.2 Ligand Canonical Resolution
    w("### 3.2 Ligand Canonical Resolution")
    w("")
    w("Documents how the canonical reference μ°(HₓL) ≡ 0 was anchored for each ligand.")
    w("The protonation reaction is: x H⁺ + L ⇌ HₓL (cumulative logβ).")
    w("mu_shift converts from the free-ligand frame (μ°(L)=0) to the canonical frame (μ°(HₓL)=0):")
    w("μ°_canon = μ°_free + Σ (copies of L) × mu_shift, where mu_shift = 2.303RT × logβ(HₓL).")
    w("")
    w("| ligand_id | ligand_name | rebase | declared_H | resolved_H | log_beta_HxL | mu_shift_kJ | strategy | vlm_source |")
    w("|-----------|-------------|--------|------------|------------|--------------|-------------|----------|------------|")
    if report.rulebook:
        for lig_idx in sorted(report.rulebook.refs):
            ref = report.rulebook.refs[lig_idx]
            lid = f"L{ref.ligand_idx}"
            hxl_form = _hxl_bracket_str(ref.canonical_H, lid)
            # Arrow: free ligand → canonical HxL (the new zero-reference)
            rebase_str = f"[{lid}] -> {hxl_form}"
            if ref.canonical_H == 0:
                vlm_src = "R4a: canonical_H=0; shift≡0"
            elif ref.vlm_id:
                vlm_src = ref.vlm_id
            else:
                vlm_src = ""
            w(f"| {lid} | {_tokenize_name(ref.ligand_name)} | {rebase_str} | {ref.canonical_H} "
              f"| {ref.resolved_H} | {ref.log_beta_HxL:+.4f} "
              f"| {ref.mu_shift_kJ:+.4f} | {ref.strategy} | {vlm_src} |")
    w("")

    if report.rulebook and report.rulebook.notes:
        w("### 3.3 Edge Case Notes")
        w("")
        for note in report.rulebook.notes:
            w(f"- {note}")
        w("")

    # ── Name lookup (shared by Section 4.2 and 5) ──────────────
    _name_map: Dict[str, str] = {}
    for i, mid in enumerate(report.metal_ids):
        _name_map[mid] = report.metal_names[i]
    for j, lid in enumerate(report.ligand_ids):
        _name_map[lid] = report.ligand_names[j]
    for cm in report.component_meta:
        if cm.internal_id not in _name_map:
            _name_map[cm.internal_id] = cm.name

    def _species_pair_key(se: SpeciesEnergy) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
        """Classify a species by its metal(s) and ligand(s) from stoich keys.

        Returns (metal_ids_tuple, ligand_ids_tuple) for grouping.
        - Bare metal ions (only metal, no OH, no ligand) → (('M1',), ())
        - Metal-hydroxide complexes (metal + OH)         → (('M1',), ('OH',))
        - Metal-ligand complexes                         → (('M1',), ('L1',))
        - Protonation/reference (no metal, no ligand)    → (('reference',), ())

        Note: OH is represented as H with negative count in internal stoich,
        or as explicit 'OH' key after round-trip through the reader.
        """
        metals_in = []
        ligands_in = []
        has_oh = False
        for key, count in se.stoich.items():
            if key == "H":
                # Negative H count = hydroxide (OH⁻) contribution
                if count < 0:
                    has_oh = True
                continue
            if key == "OH":
                has_oh = True
                continue
            if key.startswith("L"):
                ligands_in.append(key)
            elif key.startswith("M") or "$" in key:
                metals_in.append(key)
            # HxLy grouped keys
            elif re.match(r"H-?\d*L\d+", key):
                lig = re.search(r"(L\d+)", key)
                if lig:
                    ligands_in.append(lig.group(1))
        if not metals_in and not ligands_in:
            return (("reference",), ())
        if has_oh and not ligands_in:
            return (tuple(sorted(set(metals_in))), ("OH",))
        return (tuple(sorted(set(metals_in))), tuple(sorted(set(ligands_in))))

    # ── Section 4: Settings ───────────────────────────────────
    w("## 4. Settings")
    w("")

    # 4.1 Common thermodynamic constants
    w("### 4.1 Common Settings")
    w("")
    w("| parameter | value | unit |")
    w("|-----------|-------|------|")
    # Reference-card source conditions are provenance, not calculation-card
    # declarations.  Keep the solver environment visibly unresolved here.
    w("| ionic_strength | Not defined | mol/L |")
    w("| ionic_strength_mode | Not defined | - |")
    w(f"| Kw_log10 | {report.Kw_log:.2f} | - |")
    w(f"| 2.303RT | {report.factor:.4f} | kJ/mol |")
    w(f"| RT | {report.RT:.6f} | kJ/mol |")
    w("")

    # 4.2 Per metal–ligand pair T/I from VLM equilibrium metadata
    if report.equilibrium_meta:
        # Group VLM entries by (metal_system, ligand_system) pair
        from collections import OrderedDict as _OD
        pair_groups: Dict[Tuple[str, str], List] = _OD()
        for em in report.equilibrium_meta:
            m_key = ", ".join(_tokenize_name(n) for n in em.metal_system) if em.metal_system else _EMPTY
            l_key = ", ".join(_tokenize_name(n) for n in em.ligand_system) if em.ligand_system else _EMPTY
            pair_groups.setdefault((m_key, l_key), []).append(em)

        w("### 4.2 Per Metal–Ligand Pair Conditions")
        w("")
        w("| pair | T_source (°C) | I_source (mol/L) | ref_eq_net | vlm_count |")
        w("|------|---------------|------------------|------------|-----------|")
        for (m_key, l_key), em_list in pair_groups.items():
            t_vals = sorted(set(em.T_source_C for em in em_list))
            i_vals = sorted(set(em.I_source_M for em in em_list))
            t_str = f"{t_vals[0]:.1f}" if len(t_vals) == 1 else f"{t_vals[0]:.1f}~{t_vals[-1]:.1f}"
            i_str = f"{i_vals[0]:.4g}" if len(i_vals) == 1 else f"{i_vals[0]:.4g}~{i_vals[-1]:.4g}"
            # Collect unique ref_eq_net IDs
            all_net_ids: List[int] = []
            for em in em_list:
                for nid in em.ref_eq_net_ids:
                    if nid not in all_net_ids:
                        all_net_ids.append(nid)
            net_str = ", ".join(str(n) for n in all_net_ids) if all_net_ids else _EMPTY
            pair_label = f"{m_key} + {l_key}"
            w(f"| {pair_label} | {t_str} | {i_str} | {net_str} "
              f"| {len(em_list)} |")
        w("")

    # ── Section 5: Standard Chemical Potentials ───────────────
    w("## 5. Standard Chemical Potentials")
    w("")
    w("All values in kJ/mol. Sorted by μ°_canon ascending (most stable canonical state first).")
    w("")

    _SP_HEADER = (
        "| species_id | label | charge | phase "
        "| log_beta | mu0_free_kJ | mu0_canon_kJ | mu_aligned_kJ | stoich "
        "| calc_source | include | additional_notes |"
    )
    _SP_SEP = (
        "|------------|-------|--------|-------"
        "|----------|-------------|--------------|---------------|--------"
        "|-------------|---------|------------------|"
    )

    def _pair_label(
        metals: Tuple[str, ...],
        ligands: Tuple[str, ...],
        name_map: Dict[str, str],
        *,
        phase_suffix: str = "",
    ) -> str:
        """Tokenized label for a metal-ligand pair group.

        Returns e.g. ``[Cu]2+ + [Glycine]. aqueous``.
        Bare metal ions (no ligand, no OH) → ``[Cu]2+. aqueous``.
        Metal-hydroxide (ligands=('OH',)) → ``[Cu]2+ + [Hydroxide]. aqueous``.
        """
        if metals == ("reference",):
            base = "Reference & Protonation Species"
        else:
            metal_parts = [_tokenize_name(name_map.get(m, m)) for m in metals]
            if ligands == ("OH",):
                lig_label = "[Hydroxide]"
            elif ligands:
                lig_parts = [_tokenize_name(name_map.get(lg, lg)) for lg in ligands]
                lig_label = " + ".join(lig_parts)
            else:
                lig_label = ""
            if metal_parts and lig_label:
                base = " + ".join(metal_parts) + " + " + lig_label
            elif metal_parts:
                base = " + ".join(metal_parts)
            else:
                base = lig_label + " (protonation)" if lig_label else "Unknown"
        if phase_suffix:
            return f"{base}. {phase_suffix}"
        return base

    # Phase label lookup for #### headers
    _PHASE_LABEL = {
        "aqueous": "aqueous",
        "dissolution": "solid",
        "gas": "gas",
    }

    def _write_phase_block(
        phase_name: str,
        phase_species: List[SpeciesEnergy],
        subsection: str,
        phase_key: str,
    ) -> None:
        """Write a phase subsection with species grouped by metal-ligand pair."""
        w(f"### {subsection} {phase_name}")
        w("")
        if not phase_species:
            w(f"(No {phase_name.lower()} species in this system.)")
            w("")
            return

        phase_suffix = _PHASE_LABEL.get(phase_key, phase_key)

        # Group by metal-ligand pair
        from collections import OrderedDict as _OD2
        groups: Dict[Tuple, List[SpeciesEnergy]] = _OD2()
        for se in phase_species:
            pk = _species_pair_key(se)
            groups.setdefault(pk, []).append(se)

        # Sort order: reference species first, then by pair key
        sorted_keys = sorted(groups.keys(), key=lambda k: (0 if k[0] == ("reference",) else 1, k))

        for pk in sorted_keys:
            sp_list = groups[pk]
            metals, ligands = pk
            label = _pair_label(metals, ligands, _name_map, phase_suffix=phase_suffix)
            w(f"#### {label}")
            w("")
            w(_SP_HEADER)
            w(_SP_SEP)
            for se in sorted(sp_list, key=lambda s: s.mu0_canonical):
                st = _stoich_str(se.stoich, se.stoich_hlx)
                notes = _cell(se.additional_notes or "")
                mu_aligned = se.mu0_canonical
                calc_src = _species_calc_source(se)
                if not isinstance(se.include, bool):
                    raise ValueError(
                        f"species {se.species_id!r} include must be explicitly "
                        "declared true or false"
                    )
                include = "true" if se.include else "false"
                w(f"| {_tokenize_species_id(se.species_id)} | {_tokenize_label(se.label)} "
                  f"| {se.charge:+d} | {se.phase} "
                  f"| {se.log_beta:+.4f} | {se.mu0_free:+.4f} "
                  f"| {se.mu0_canonical:+.4f} | {mu_aligned:+.4f} | {st} "
                  f"| {calc_src} | {include} | {notes} |")
            w("")

    # Separate by phase
    aqueous_species = [se for se in report.species if se.phase == "aqueous"]
    dissolution_species = [se for se in report.species if se.phase == "dissolution"]
    gas_species = [se for se in report.species if se.phase == "gas"]

    _write_phase_block("Aqueous Species", aqueous_species, "5.1", "aqueous")
    _write_phase_block("Dissolution / Solid Species", dissolution_species, "5.2", "dissolution")
    _write_phase_block("Gas Species", gas_species, "5.3", "gas")

    # 5.4 Supportive Thermodynamic Data
    w("### 5.4 Supportive Thermodynamic Data")
    w("")
    w("| entity_id | property | value | unit | derived_mu0_kJ | notes |")
    w("|-----------|----------|-------|------|----------------|-------|")
    for solv in report.solvents:
        if solv.self_dissociation:
            mu_kw = report.factor * solv.pK
            w(f"| {solv.internal_id} | pKw | {solv.pK:.2f} | - | {mu_kw:+.4f} "
              f"| water self-dissociation |")
    # Electron thermodynamics (always present — needed by Pourbaix)
    F_kJ = 96.48533212            # Faraday constant kJ/(mol·V)
    nernst = report.factor / F_kJ  # 2.303RT/F  in V
    F_over = F_kJ / report.factor  # F/(2.303RT) in V⁻¹
    w(f"| e- | charge | -1 | - | +0.0000 | electron reference μ°≡0 |")
    w(f"| e- | F_over_RT_ln10 | {F_over:.4f} | V⁻¹ | - "
      f"| F/(2.303RT) at {report.temperature_C:.0f}°C |")
    w(f"| e- | nernst_factor | {nernst:.5f} | V | - "
      f"| 2.303RT/F at {report.temperature_C:.0f}°C |")
    w("")

    # ── Section 6: Validation — Equilibrium Map Coverage ─────────
    _write_eq_map_validation(w, report)

    # ── Footer ────────────────────────────────────────────────
    w("---")
    w("*This card was generated by `free_energy_md_card_generation.py`. "
      "Speciation should be computed using free energies (μ°), "
      "not equilibrium βs directly.*")
    w("")

    return "\n".join(lines)
