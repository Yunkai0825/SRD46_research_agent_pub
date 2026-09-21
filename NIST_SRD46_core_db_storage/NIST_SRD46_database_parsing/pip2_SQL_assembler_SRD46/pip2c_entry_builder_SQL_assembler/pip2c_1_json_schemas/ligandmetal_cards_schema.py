"""
MetalLigandComplexEntry schema - metal_ligand_complex.json dataclass model.

This dataclass models the metal-ligand complex entry including stability
constants, conditions, and equation information from the SRD46 database.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from ._utils import MissingFieldTracker, DEFAULT_MISSING_TRACKER, _is_empty, _load_json_like


@dataclass
class MetalLigandComplexEntry:
    """Metal-ligand complex entry schema for metal_ligand_complex.json."""
    
    # --- nested helper types ---
    
    class ConstantType(str, Enum):
        """Constant type per constanttyp.name_constanttyp.

        Semantic notes:
        - "K" represents log(K) (logarithm of the equilibrium/stability constant)
        - "H" represents Enthalpy (H)
        - "S" represents Entropy (S)
        - "*" remains unspecified
        """
        UNSPECIFIED = "*"
        H = "H"
        K = "K"
        S = "S"

    class SpeciesPresence(str, Enum):
        """Flags for species presence relative to the parsed equilibrium equation.

        Values indicate if a species class appears on which side of the parsed equation:
        - none: not present in equation
        - lhs_only: only on left-hand side
        - rhs_only: only on right-hand side
        - both: appears on both sides (usually indicates a problematic entry)
        """
        NONE = "none"
        LHS_ONLY = "lhs_only"
        RHS_ONLY = "rhs_only"
        BOTH = "both"

    @dataclass
    class ConstantBlock:
        """Stability constant value and type.

        entry_value_raw / in_parentheses / is_placeholder are in-memory provenance only: the SQL
        exporter writes no column for them (the cards schema is frozen to its downstream readers);
        they travel as 'parser:<key>=<value>' strings in ligandmetal_stability_measured.notes
        (srd46_pipeline/manual_rules.py NOTE-01) and cards_sql_reader rebuilds them from there.
        """
        entry_type: 'MetalLigandComplexEntry.ConstantType'
        entry_value: Optional[float] = None       # None for SRD46 placeholder rows ('*'); never a fabricated 0.0
        entry_value_raw: Optional[str] = None     # verbatim SRD46 text when a rule changed it, e.g. '(3.5)' or '*' (notes: parser:constant_raw)
        in_parentheses: Optional[bool] = None     # SRD46 tentative-value notation '(x)' (VLM-02; notes: parser:constant_in_parentheses=1)
        is_placeholder: Optional[bool] = None     # SRD46 '*' placeholder row (VLM-01; notes: parser:placeholder=1)

    @dataclass
    class ConditionsBlock:
        """Experimental conditions for the measurement."""
        
        @dataclass
        class SolventInfo:
            """Solvent information."""
            solvent_id: Optional[int] = None
            name: Optional[str] = None
            electrolyte_and_composition: Optional[str] = None  # stub

        temperature_c: Optional[float] = None
        ionic_strength_mol_l: Optional[float] = None
        solvent: 'MetalLigandComplexEntry.ConditionsBlock.SolventInfo' = field(
            default_factory=lambda: MetalLigandComplexEntry.ConditionsBlock.SolventInfo()
        )

    @dataclass
    class EquationInfo:
        """Equilibrium equation information."""
        
        @dataclass
        class EquationSpecies:
            """Species in the equilibrium equation."""
            species: str
            power: float

        @dataclass
        class PresenceFlags:
            """Flags indicating presence of species on LHS/RHS of equation."""
            proton_flag: 'MetalLigandComplexEntry.SpeciesPresence' = field(
                default_factory=lambda: MetalLigandComplexEntry.SpeciesPresence.NONE
            )
            ligand_flag: 'MetalLigandComplexEntry.SpeciesPresence' = field(
                default_factory=lambda: MetalLigandComplexEntry.SpeciesPresence.NONE
            )
            metal_flag: 'MetalLigandComplexEntry.SpeciesPresence' = field(
                default_factory=lambda: MetalLigandComplexEntry.SpeciesPresence.NONE
            )

        raw_definition: str
        normalized_definition: Optional[str] = None
        equation_sides: Optional[Dict[str, Any]] = None
        equation_str: Optional[str] = None
        equation_tree: Optional[Dict[str, Any]] = None
        LHS_species: Optional[List['MetalLigandComplexEntry.EquationInfo.EquationSpecies']] = None
        RHS_species: Optional[List['MetalLigandComplexEntry.EquationInfo.EquationSpecies']] = None
        HxL_involved: Optional[Union[bool, List[str]]] = None
        presence_flags: 'MetalLigandComplexEntry.EquationInfo.PresenceFlags' = field(
            default_factory=lambda: MetalLigandComplexEntry.EquationInfo.PresenceFlags()
        )
        # Additional fields from augmented beta_definition parsing
        reaction_type: Optional[str] = None  # e.g., "homogeneous_aqueous", "dissolution"
        element_conserved: Optional[bool] = None  # True if element balance is conserved

    @dataclass
    class StabilityInfoBlock:
        """Provenance-aware stability info groupings under a single subroot."""
        
        @dataclass
        class StabilityInfoBaseEntry:
            """Base stability info entry with common fields."""
            constant: 'MetalLigandComplexEntry.ConstantBlock' = field(
                default_factory=lambda: MetalLigandComplexEntry.ConstantBlock(
                    entry_type=MetalLigandComplexEntry.ConstantType.UNSPECIFIED,
                    entry_value=None
                )
            )
            conditions: 'MetalLigandComplexEntry.ConditionsBlock' = field(
                default_factory=lambda: MetalLigandComplexEntry.ConditionsBlock()
            )
            equation_python: Optional[str] = None
            equation_info: 'MetalLigandComplexEntry.EquationInfo' = field(
                default_factory=lambda: MetalLigandComplexEntry.EquationInfo(raw_definition="")
            )
            notes: Optional[str] = None

        @dataclass
        class StabilityInfoMeasuredEntry(StabilityInfoBaseEntry):
            """Measured stability info entry."""
            # Inherits constant, conditions, equation from StabilityInfoBaseEntry
            audit_timestamp: Optional[str] = None
            error: Optional[str] = None

        @dataclass
        class StabilityInfoEstimatedEntry(StabilityInfoBaseEntry):
            """Estimated stability info entry."""
            # Inherits constant, conditions, equation from StabilityInfoBaseEntry
            # Set a default to satisfy dataclass ordering with base defaults
            source: Optional[str] = None
            model_name: Optional[str] = None
            model_version: Optional[str] = None
            confidence: Optional[float] = None
            uncertainty: Optional[float] = None
            notes: Optional[str] = None

        measured_value: List['MetalLigandComplexEntry.StabilityInfoBlock.StabilityInfoMeasuredEntry'] = field(
            default_factory=list
        )
        estimated_value: List['MetalLigandComplexEntry.StabilityInfoBlock.StabilityInfoEstimatedEntry'] = field(
            default_factory=list
        )

    # --- primary fields ---
    complex_system_id: int
    metal_id: int
    ligand_id: int
    beta_definition_id: int
    complex_id: str
    # optional/diagnostic fields (defaults after required ones)
    ligand_class_id: Optional[int] = None  # made optional to allow builders to omit
    metal_name_SRD: Optional[str] = None
    metal_SMILES: Optional[str] = None
    metal_InChi: Optional[str] = None
    ligand_class_name: Optional[str] = None
    ligand_name_SRD: Optional[str] = None
    ligand_SMILES: Optional[str] = None
    ligand_InChi: Optional[str] = None
    ligand_HxL_definition_SRD: Optional[str] = None  # ADDED
    beta_definition_name: Optional[str] = None
    stability_info: 'MetalLigandComplexEntry.StabilityInfoBlock' = field(
        default_factory=lambda: MetalLigandComplexEntry.StabilityInfoBlock()
    )


# =============================================================================
# Builder functions
# =============================================================================

def _maybe_json(val):
    """Parse JSON if string, otherwise return as-is."""
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        s = val.strip()
        if s.startswith("{") or s.startswith("["):
            try:
                import json as _json
                return _json.loads(s)
            except Exception:
                return val
    return val


def _float_or_none(val: Any, tracker: MissingFieldTracker, cls_name: str, field_name: str) -> Optional[float]:
    """float(val) for non-empty values; None (and tracker.mark_invalid) for placeholders like '*'."""
    if _is_empty(val):
        return None
    try:
        return float(val)
    except Exception:
        tracker.mark_invalid(cls_name, field_name)
        return None


def _build_measured_entry_from_dict(
    d: Dict[str, Any],
    tracker: MissingFieldTracker
) -> 'MetalLigandComplexEntry.StabilityInfoBlock.StabilityInfoMeasuredEntry':
    """Build a StabilityInfoMeasuredEntry from a dictionary."""
    measured = MetalLigandComplexEntry.StabilityInfoBlock.StabilityInfoMeasuredEntry()
    
    # constant
    c = d.get("constant") or {}
    if c:
        et = c.get("entry_type")
        ev = c.get("entry_value")
        if not _is_empty(et):
            try:
                measured.constant.entry_type = MetalLigandComplexEntry.ConstantType(et)
            except Exception:
                tracker.mark_invalid("StabilityInfoMeasuredEntry.ConstantBlock", "entry_type")
        if not _is_empty(ev):
            try:
                measured.constant.entry_value = float(ev)
            except Exception:
                tracker.mark_invalid("StabilityInfoMeasuredEntry.ConstantBlock", "entry_value")
        if not _is_empty(c.get("entry_value_raw")):
            measured.constant.entry_value_raw = str(c.get("entry_value_raw"))
        ip = c.get("in_parentheses")
        if not _is_empty(ip):
            measured.constant.in_parentheses = ip if isinstance(ip, bool) else str(ip).strip().lower() in ("1", "true", "yes")
        ph = c.get("is_placeholder")
        if not _is_empty(ph):
            measured.constant.is_placeholder = ph if isinstance(ph, bool) else str(ph).strip().lower() in ("1", "true", "yes")

    # conditions
    cond = d.get("conditions") or {}
    if cond:
        # SRD46 uses "*" as a placeholder for unknown T / I; keep the entry, mark the field invalid
        measured.conditions.temperature_c = _float_or_none(
            cond.get("temperature_c"), tracker, "StabilityInfoMeasuredEntry.Conditions", "temperature_c")
        measured.conditions.ionic_strength_mol_l = _float_or_none(
            cond.get("ionic_strength_mol_l"), tracker, "StabilityInfoMeasuredEntry.Conditions", "ionic_strength_mol_l")
        s = cond.get("solvent") or {}
        if s:
            if not _is_empty(s.get("solvent_id")):
                try:
                    measured.conditions.solvent.solvent_id = int(s.get("solvent_id"))
                except Exception:
                    tracker.mark_invalid("StabilityInfoMeasuredEntry.Conditions.Solvent", "solvent_id")
            if not _is_empty(s.get("name")):
                measured.conditions.solvent.name = str(s.get("name"))
            if not _is_empty(s.get("electrolyte_and_composition")):
                measured.conditions.solvent.electrolyte_and_composition = str(s.get("electrolyte_and_composition"))

    # equation_info
    eq = d.get("equation_info") or {}
    if eq:
        if not _is_empty(eq.get("raw_definition")):
            measured.equation_info.raw_definition = str(eq.get("raw_definition"))
        if not _is_empty(eq.get("normalized_definition")):
            measured.equation_info.normalized_definition = str(eq.get("normalized_definition"))
        if not _is_empty(eq.get("equation_sides")):
            measured.equation_info.equation_sides = _maybe_json(eq.get("equation_sides"))
        if not _is_empty(eq.get("equation_str")):
            measured.equation_info.equation_str = str(eq.get("equation_str"))
        if not _is_empty(eq.get("equation_tree")):
            measured.equation_info.equation_tree = _maybe_json(eq.get("equation_tree"))
        if not _is_empty(eq.get("reaction_type")):
            measured.equation_info.reaction_type = str(eq.get("reaction_type"))
        if eq.get("element_conserved") is not None:
            val = eq.get("element_conserved")
            if isinstance(val, bool):
                measured.equation_info.element_conserved = val
            elif isinstance(val, str):
                measured.equation_info.element_conserved = val.lower() in ('true', '1', 'yes')
        # LHS/RHS species
        lhs = eq.get("LHS_species")
        if isinstance(lhs, list):
            measured.equation_info.LHS_species = []
            for it in lhs:
                if isinstance(it, dict) and "species" in it:
                    try:
                        sp = MetalLigandComplexEntry.EquationInfo.EquationSpecies(
                            species=str(it.get("species")),
                            power=float(it.get("power", 1.0)),
                        )
                        measured.equation_info.LHS_species.append(sp)
                    except Exception:
                        pass
        rhs = eq.get("RHS_species")
        if isinstance(rhs, list):
            measured.equation_info.RHS_species = []
            for it in rhs:
                if isinstance(it, dict) and "species" in it:
                    try:
                        sp = MetalLigandComplexEntry.EquationInfo.EquationSpecies(
                            species=str(it.get("species")),
                            power=float(it.get("power", 1.0)),
                        )
                        measured.equation_info.RHS_species.append(sp)
                    except Exception:
                        pass
        if eq.get("HxL_involved") is not None:
            measured.equation_info.HxL_involved = eq.get("HxL_involved")
        pf = eq.get("presence_flags")
        if isinstance(pf, dict):
            def _pf(v):
                try:
                    return MetalLigandComplexEntry.SpeciesPresence(str(v))
                except:
                    return None
            v = _pf(pf.get("proton_flag"))
            if v:
                measured.equation_info.presence_flags.proton_flag = v
            v = _pf(pf.get("ligand_flag"))
            if v:
                measured.equation_info.presence_flags.ligand_flag = v
            v = _pf(pf.get("metal_flag"))
            if v:
                measured.equation_info.presence_flags.metal_flag = v

    # equation_python
    if not _is_empty(d.get("equation_python")):
        measured.equation_python = str(d.get("equation_python"))
    
    # audit/error fields
    if not _is_empty(d.get("audit_timestamp")):
        measured.audit_timestamp = str(d.get("audit_timestamp"))
    if not _is_empty(d.get("error")):
        measured.error = str(d.get("error"))
    if not _is_empty(d.get("notes")):
        measured.notes = str(d.get("notes"))

    return measured


def _build_estimated_entry_from_dict(
    d: Dict[str, Any],
    tracker: MissingFieldTracker
) -> 'MetalLigandComplexEntry.StabilityInfoBlock.StabilityInfoEstimatedEntry':
    """Build a StabilityInfoEstimatedEntry from a dictionary."""
    estimated = MetalLigandComplexEntry.StabilityInfoBlock.StabilityInfoEstimatedEntry()
    
    # source/model info
    if not _is_empty(d.get("source")):
        estimated.source = str(d.get("source"))
    if not _is_empty(d.get("model_name")):
        estimated.model_name = str(d.get("model_name"))
    if not _is_empty(d.get("model_version")):
        estimated.model_version = str(d.get("model_version"))
    
    # constant
    c = d.get("constant") or {}
    if c:
        et = c.get("entry_type")
        ev = c.get("entry_value")
        if not _is_empty(et):
            try:
                estimated.constant.entry_type = MetalLigandComplexEntry.ConstantType(et)
            except Exception:
                pass
        if not _is_empty(ev):
            try:
                estimated.constant.entry_value = float(ev)
            except Exception:
                pass

    # conditions
    cond = d.get("conditions") or {}
    if cond:
        estimated.conditions.temperature_c = _float_or_none(
            cond.get("temperature_c"), tracker, "StabilityInfoEstimatedEntry.Conditions", "temperature_c")
        estimated.conditions.ionic_strength_mol_l = _float_or_none(
            cond.get("ionic_strength_mol_l"), tracker, "StabilityInfoEstimatedEntry.Conditions", "ionic_strength_mol_l")
    
    # confidence/uncertainty
    if d.get("confidence") is not None:
        estimated.confidence = _float_or_none(d.get("confidence"), tracker, "StabilityInfoEstimatedEntry", "confidence")
    if d.get("uncertainty") is not None:
        estimated.uncertainty = _float_or_none(d.get("uncertainty"), tracker, "StabilityInfoEstimatedEntry", "uncertainty")
    if not _is_empty(d.get("notes")):
        estimated.notes = str(d.get("notes"))

    return estimated


def create_metal_ligand_complex_entry(
    data: Dict[str, Any] | None = None, tracker: MissingFieldTracker | None = None
) -> MetalLigandComplexEntry:
    """Create a MetalLigandComplexEntry from a dictionary of complex data.
    
    This function handles complex nested structures including stability info,
    conditions, equation info, and citations.
    """
    # Import here to avoid circular imports
    from .ligand_cards_schema import LigandEntry
    from .metal_cards_schema import CationEntry
    
    tracker = tracker or DEFAULT_MISSING_TRACKER
    data = data or {}

    # Required primitive fields
    required_fields = ["complex_system_id", "metal_id", "ligand_id", "beta_definition_id"]
    prim: Dict[str, Any] = {}
    for f in required_fields:
        v = data.get(f)
        if _is_empty(v):
            tracker.mark_missing("MetalLigandComplexEntry", f)
            prim[f] = 0
        else:
            prim[f] = int(v)

    def _derive_complex_id(metal_id: Any, ligand_id: Any, beta_definition_id: Any) -> str:
        try:
            m = int(metal_id)
            l = int(ligand_id)
            b = int(beta_definition_id)
            return f"{m}-{l}-{b}"
        except Exception:
            return ""

    complex_id = data.get("complex_id")
    if _is_empty(complex_id):
        tracker.mark_missing("MetalLigandComplexEntry", "complex_id")
        complex_id = _derive_complex_id(prim["metal_id"], prim["ligand_id"], prim["beta_definition_id"])

    entry = MetalLigandComplexEntry(
        complex_system_id=prim["complex_system_id"],
        metal_id=prim["metal_id"],
        ligand_id=prim["ligand_id"],
        beta_definition_id=prim["beta_definition_id"],
        complex_id=str(complex_id or ""),
    )

    # Copy human-readable / class fields
    try:
        if not _is_empty(data.get("metal_name_SRD")):
            entry.metal_name_SRD = str(data.get("metal_name_SRD"))
        if not _is_empty(data.get("ligand_name_SRD")):
            entry.ligand_name_SRD = str(data.get("ligand_name_SRD"))
        if not _is_empty(data.get("ligand_class_id")):
            try:
                entry.ligand_class_id = int(data.get("ligand_class_id"))
            except Exception:
                tracker.mark_invalid("MetalLigandComplexEntry", "ligand_class_id")
        if not _is_empty(data.get("ligand_class_name")):
            entry.ligand_class_name = str(data.get("ligand_class_name"))
        bd = data.get("beta_definition_name")
        if _is_empty(bd):
            si_tmp = data.get("stability_info") or {}
            eqi = (si_tmp.get("equation_info") or {}) if isinstance(si_tmp, dict) else {}
            bd = eqi.get("raw_definition") if isinstance(eqi, dict) else bd
        if not _is_empty(bd):
            entry.beta_definition_name = str(bd)
    except Exception:
        pass

    # Structural identifiers
    def _pick_key(d: Dict[str, Any], *keys: str) -> Optional[str]:
        for k in keys:
            v = d.get(k)
            if not _is_empty(v):
                return str(v)
        lower = {kk.lower(): vv for kk, vv in d.items()}
        for k in keys:
            lk = k.lower()
            if lk in lower and not _is_empty(lower[lk]):
                return str(lower[lk])
        return None

    m_smiles = _pick_key(data, "metal_SMILES", "metal_smiles", "metal_SMILE", "metal_SMILEs")
    m_inchi = _pick_key(data, "metal_InChi", "metal_inchi", "metal_inchi_key", "metal_inchi_str")
    l_smiles = _pick_key(data, "ligand_SMILES", "ligand_smiles", "ligand_SMILE", "ligand_SMILEs")
    l_inchi = _pick_key(data, "ligand_InChi", "ligand_inchi", "ligand_inchi_key", "ligand_inchi_str")

    if m_smiles is not None:
        entry.metal_SMILES = m_smiles
    if m_inchi is not None:
        entry.metal_InChi = m_inchi
    if l_smiles is not None:
        entry.ligand_SMILES = l_smiles
    if l_inchi is not None:
        entry.ligand_InChi = l_inchi

    # Handle ligand/metal provided as dataclass instances or dicts
    try:
        for src_key in ('ligand_entry', 'ligand'):
            if src_key not in data or data.get(src_key) is None:
                continue
            src = data.get(src_key)
            if isinstance(src, LigandEntry):
                if not _is_empty(getattr(src, 'ligand_name_SRD', None)):
                    entry.ligand_name_SRD = str(getattr(src, 'ligand_name_SRD'))
                if not _is_empty(getattr(src, 'ligand_SMILES', None)):
                    entry.ligand_SMILES = str(getattr(src, 'ligand_SMILES'))
                if not _is_empty(getattr(src, 'ligand_InChi', None)):
                    entry.ligand_InChi = str(getattr(src, 'ligand_InChi'))
                if not _is_empty(getattr(src, 'definition_HxL', None)):
                    entry.ligand_HxL_definition_SRD = str(getattr(src, 'definition_HxL'))
                break
            if isinstance(src, str):
                loaded = _load_json_like(src)
            else:
                loaded = src
            if isinstance(loaded, dict):
                l_name = loaded.get('ligand_name_SRD') or loaded.get('ligand_name') or loaded.get('name')
                l_smiles = loaded.get('ligand_SMILES') or loaded.get('SMILES') or loaded.get('smiles')
                l_inchi = loaded.get('ligand_InChi') or loaded.get('InChi') or loaded.get('inchi')
                l_def = loaded.get('definition_HxL') or loaded.get('figure_definition_parsed')
                if not _is_empty(l_name):
                    entry.ligand_name_SRD = str(l_name)
                if not _is_empty(l_smiles):
                    entry.ligand_SMILES = str(l_smiles)
                if not _is_empty(l_inchi):
                    entry.ligand_InChi = str(l_inchi)
                if not _is_empty(l_def):
                    entry.ligand_HxL_definition_SRD = str(l_def)
                break

        for src_key in ('metal_entry', 'metal'):
            if src_key not in data or data.get(src_key) is None:
                continue
            src = data.get(src_key)
            if isinstance(src, CationEntry):
                if not _is_empty(getattr(src, 'metal_name_SRD', None)):
                    entry.metal_name_SRD = str(getattr(src, 'metal_name_SRD'))
                if not _is_empty(getattr(src, 'SMILES', None)):
                    entry.metal_SMILES = str(getattr(src, 'SMILES'))
                if not _is_empty(getattr(src, 'InChi', None)):
                    entry.metal_InChi = str(getattr(src, 'InChi'))
                break
            if isinstance(src, str):
                loaded = _load_json_like(src)
            else:
                loaded = src
            if isinstance(loaded, dict):
                m_name = loaded.get('metal_name_SRD') or loaded.get('metal_name') or loaded.get('name')
                m_smiles = loaded.get('SMILES') or loaded.get('smiles')
                m_inchi = loaded.get('InChi') or loaded.get('inchi')
                if not _is_empty(m_name):
                    entry.metal_name_SRD = str(m_name)
                if not _is_empty(m_smiles):
                    entry.metal_SMILES = str(m_smiles)
                if not _is_empty(m_inchi):
                    entry.metal_InChi = str(m_inchi)
                break
    except Exception:
        pass

    # Copy ligand canonical HxL form
    try:
        l_hxl = None
        for key in ("ligand_HxL_definition_SRD", "definition_HxL", "figure_definition_parsed"):
            v = data.get(key)
            if not _is_empty(v):
                l_hxl = v
                break
        if l_hxl is not None:
            entry.ligand_HxL_definition_SRD = str(l_hxl)
    except Exception:
        pass

    # Stability info - handle both list form and flat single-entry form
    si = data.get("stability_info") or {}
    if si:
        # Check if we have pre-built measured_value and estimated_value lists
        mv_list = si.get("measured_value")
        ev_list = si.get("estimated_value")
        
        if isinstance(mv_list, list) and mv_list:
            # Process list of measured entries (used by SQL reader roundtrip)
            for mv_item in mv_list:
                measured = _build_measured_entry_from_dict(mv_item, tracker)
                entry.stability_info.measured_value.append(measured)
        else:
            # Handle the flat single-entry form (legacy/original)
            measured = _build_measured_entry_from_dict(si, tracker)
            entry.stability_info.measured_value.append(measured)
        
        if isinstance(ev_list, list) and ev_list:
            # Process list of estimated entries
            for ev_item in ev_list:
                estimated = _build_estimated_entry_from_dict(ev_item, tracker)
                entry.stability_info.estimated_value.append(estimated)

    return entry


def _parse_equation_species(measured: 'MetalLigandComplexEntry.StabilityInfoBlock.StabilityInfoMeasuredEntry', 
                            eq: Dict[str, Any], tracker: MissingFieldTracker) -> None:
    """Parse LHS/RHS species from equation_tree or direct equation keys."""
    et = measured.equation_info.equation_tree
    filled_from_tree = False
    
    if isinstance(et, dict):
        lhs_tree = et.get("LHS_species") or et.get("lhs_species") or et.get("LHS") or et.get("lhs")
        rhs_tree = et.get("RHS_species") or et.get("rhs_species") or et.get("RHS") or et.get("rhs")
        
        if isinstance(lhs_tree, list):
            measured.equation_info.LHS_species = []
            for it in lhs_tree:
                if isinstance(it, dict) and "species" in it:
                    try:
                        sp = MetalLigandComplexEntry.EquationInfo.EquationSpecies(
                            species=str(it.get("species")),
                            power=float(it.get("power", 1.0)),
                        )
                        measured.equation_info.LHS_species.append(sp)
                    except Exception:
                        continue
            filled_from_tree = True
            
        if isinstance(rhs_tree, list):
            measured.equation_info.RHS_species = []
            for it in rhs_tree:
                if isinstance(it, dict) and "species" in it:
                    try:
                        sp = MetalLigandComplexEntry.EquationInfo.EquationSpecies(
                            species=str(it.get("species")),
                            power=float(it.get("power", 1.0)),
                        )
                        measured.equation_info.RHS_species.append(sp)
                    except Exception:
                        continue
            filled_from_tree = True
            
        if "HxL_involved" in et and measured.equation_info.HxL_involved is None:
            measured.equation_info.HxL_involved = et.get("HxL_involved")
            
        pf = et.get("presence_flags") or et.get("presence")
        if isinstance(pf, dict):
            _apply_presence_flags(measured, pf)

    if not filled_from_tree:
        lhs = eq.get("LHS_species")
        if isinstance(lhs, list):
            measured.equation_info.LHS_species = []
            for it in lhs:
                if isinstance(it, dict) and "species" in it:
                    try:
                        sp = MetalLigandComplexEntry.EquationInfo.EquationSpecies(
                            species=str(it.get("species")),
                            power=float(it.get("power", 1.0)),
                        )
                        measured.equation_info.LHS_species.append(sp)
                    except Exception:
                        continue
        rhs = eq.get("RHS_species")
        if isinstance(rhs, list):
            measured.equation_info.RHS_species = []
            for it in rhs:
                if isinstance(it, dict) and "species" in it:
                    try:
                        sp = MetalLigandComplexEntry.EquationInfo.EquationSpecies(
                            species=str(it.get("species")),
                            power=float(it.get("power", 1.0)),
                        )
                        measured.equation_info.RHS_species.append(sp)
                    except Exception:
                        continue
        if "HxL_involved" in eq and measured.equation_info.HxL_involved is None:
            measured.equation_info.HxL_involved = eq.get("HxL_involved")
        pf = eq.get("presence_flags")
        if isinstance(pf, dict):
            _apply_presence_flags(measured, pf)


def _apply_presence_flags(measured: 'MetalLigandComplexEntry.StabilityInfoBlock.StabilityInfoMeasuredEntry', 
                          pf: Dict[str, Any]) -> None:
    """Apply presence flags from a dictionary to the measured entry."""
    def _pf(v):
        try:
            return MetalLigandComplexEntry.SpeciesPresence(str(v))
        except Exception:
            return None
    v = _pf(pf.get("proton_flag"))
    if v:
        measured.equation_info.presence_flags.proton_flag = v
    v = _pf(pf.get("ligand_flag"))
    if v:
        measured.equation_info.presence_flags.ligand_flag = v
    v = _pf(pf.get("metal_flag"))
    if v:
        measured.equation_info.presence_flags.metal_flag = v


def _build_equation_python(measured: 'MetalLigandComplexEntry.StabilityInfoBlock.StabilityInfoMeasuredEntry') -> str:
    """Build a pythonic symbolic relation from LHS/RHS species."""
    import re
    
    def _species_token(label: str) -> str:
        try:
            core = label.strip()
            if core.startswith("[") and core.endswith("]"):
                core = core[1:-1]
            core = re.sub(r"[^A-Za-z0-9_]", "_", core)
            return f"C_{core}" if core else "C_species"
        except Exception:
            return "C_species"

    def _product(species_list: Optional[list]) -> str:
        if not species_list:
            return "1"
        terms = []
        for sp in species_list:
            try:
                label = str(getattr(sp, 'species', None) or sp.get('species'))
                power = float(getattr(sp, 'power', None) if hasattr(sp, 'power') else sp.get('power', 1.0))
            except Exception:
                label = None
                power = 1.0
            if not label:
                continue
            token = _species_token(label)
            if abs(power - 1.0) < 1e-12:
                terms.append(token)
            else:
                terms.append(f"{token}**{power}")
        return "*".join(terms) if terms else "1"

    et = measured.constant.entry_type
    lhs = measured.equation_info.LHS_species or []
    rhs = measured.equation_info.RHS_species or []
    
    if et == MetalLigandComplexEntry.ConstantType.K:
        num = _product(rhs)
        den = _product(lhs)
        return f"log(K)={num}/({den})"
    if et == MetalLigandComplexEntry.ConstantType.H:
        return "H"
    if et == MetalLigandComplexEntry.ConstantType.S:
        return "S"
    return "*"


def load_metal_ligand_complex_entry_from_json(source: Any, tracker: MissingFieldTracker | None = None) -> MetalLigandComplexEntry:
    """Load a MetalLigandComplexEntry from JSON file path, JSON string, or dict.

    Delegates to create_metal_ligand_complex_entry when a dict is supplied.
    """
    tracker = tracker or DEFAULT_MISSING_TRACKER
    if isinstance(source, MetalLigandComplexEntry):
        return source
    obj = _load_json_like(source)
    if isinstance(obj, dict):
        return create_metal_ligand_complex_entry(obj, tracker)
    raise TypeError("Unsupported source for load_metal_ligand_complex_entry_from_json: expected file path, JSON string, dict, or MetalLigandComplexEntry")


# =============================================================================
# Equilibrium map integration - stability measurements
# =============================================================================

def get_species_from_entry(entry: MetalLigandComplexEntry) -> set:
    """Extract target species from a MetalLigandComplexEntry.
    
    Returns the set of species that appear in the stability constant equation
    (both LHS and RHS species).
    """
    species = set()
    
    # Get species from measured values
    for measured in entry.stability_info.measured_value:
        if measured.equation_info.LHS_species:
            for sp in measured.equation_info.LHS_species:
                if hasattr(sp, 'species'):
                    species.add(sp.species)
                elif isinstance(sp, dict) and 'species' in sp:
                    species.add(sp['species'])
        if measured.equation_info.RHS_species:
            for sp in measured.equation_info.RHS_species:
                if hasattr(sp, 'species'):
                    species.add(sp.species)
                elif isinstance(sp, dict) and 'species' in sp:
                    species.add(sp['species'])
    
    # If no species found in measured, try beta_definition_name
    if not species and entry.beta_definition_name:
        import re
        # Extract species from definition like "[ML]/[M][L]"
        matches = re.findall(r'\[([^\]]+)\]', entry.beta_definition_name)
        for m in matches:
            species.add(f"[{m}]")
    
    return species




__all__ = [
    "MetalLigandComplexEntry",
    "create_metal_ligand_complex_entry",
    "load_metal_ligand_complex_entry_from_json",
    "get_species_from_entry",
    "populate_stability_from_equilibrium_maps",
]
