"""
LigandEntry schema - ligand.json dataclass model.

This dataclass models the ligand entry including synonyms, pKa data,
and bracket information from the SRD46 database.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ._utils import MissingFieldTracker, DEFAULT_MISSING_TRACKER, _is_empty, _load_json_like


@dataclass
class LigandEntry:
    """Ligand entry schema for ligand.json."""
    
    # --- nested helper types (to avoid leaking into module scope) ---
    @dataclass
    class Synonyms:
        """Ligand name synonyms."""
        iupac_name: Optional[str] = None
        common_name: Optional[str] = None

    @dataclass
    class PkaBracketBlock:
        """pKa bracket information block."""
        
        @dataclass
        class LigandPkaBracketBase:
            """Base pKa bracket entry with common fields."""
            
            @dataclass
            class PkaBracketEvidence:
                """Evidence links for pKa bracket entries."""
                verkn_ligand_metal_ids_upper: List[int] = field(default_factory=list)
                verkn_ligand_metal_ids_lower: List[int] = field(default_factory=list)

            state_id: str
            charge: Optional[int]  # NULL when the parent charge/protonation reference is unresolved
            formula: Optional[str] = None
            HxL_form: Optional[str] = None
            bracket_label: Optional[str] = None
            SMILES: Optional[str] = None
            InChi: Optional[str] = None
            notes: Optional[str] = None
            reference_verkn_ligand_metal_ids: 'LigandEntry.PkaBracketBlock.LigandPkaBracketBase.PkaBracketEvidence' = field(
                default_factory=lambda: LigandEntry.PkaBracketBlock.LigandPkaBracketBase.PkaBracketEvidence()
            )

        @dataclass
        class LigandPkaBracketMeasuredEntry(LigandPkaBracketBase):
            """Measured (SRD) pKa bracket entry fields."""
            measurement_method: Optional[str] = None  # e.g., potentiometry, spectrophotometry
            quality: Optional[str] = None  # freeform quality/grade flag

        @dataclass
        class LigandPkaBracketEstimatedEntry(LigandPkaBracketBase):
            """Estimated (Qupkake/other) pKa bracket entry fields."""
            model_name: Optional[str] = None
            model_version: Optional[str] = None
            confidence: Optional[float] = None
            uncertainty: Optional[float] = None

        measured_pKa_bracket: List['LigandEntry.PkaBracketBlock.LigandPkaBracketMeasuredEntry'] = field(default_factory=list)
        estimated_pKa_bracket: List['LigandEntry.PkaBracketBlock.LigandPkaBracketEstimatedEntry'] = field(default_factory=list)

    @dataclass
    class PkaBlock:
        """Provenance-aware pKa groupings under a single subroot."""
        
        @dataclass
        class LigandPkaBase:
            """Common fields shared by measured and estimated pKa entries."""

            @dataclass
            class PkaEvidence:
                """Evidence links for pKa entries."""
                verkn_ligand_metal_ids: List[int] = field(default_factory=list)

            @dataclass
            class PkaConditions:
                """Experimental conditions for pKa measurement."""
                
                @dataclass
                class SolventInfo:
                    """Solvent information."""
                    solvent_id: Optional[int] = None
                    name: Optional[str] = None
                    electrolyte_and_composition: Optional[str] = None  # stub

                temperature_c: Optional[float] = None
                ionic_strength_mol_l: Optional[float] = None
                solvent: 'LigandEntry.PkaBlock.LigandPkaBase.PkaConditions.SolventInfo' = field(
                    default_factory=lambda: LigandEntry.PkaBlock.LigandPkaBase.PkaConditions.SolventInfo()
                )
                electrolyte: Optional[str] = None

            source: str  # 'SRD', 'Qupkake', or provider label
            # Required bracket identifiers must come before defaults
            bracket_from_state: str
            bracket_to_state: str
            SMILES_from_state: Optional[str] = None
            InChi_from_state: Optional[str] = None
            SMILES_to_state: Optional[str] = None
            InChi_to_state: Optional[str] = None
            pKa: Optional[float] = None
            pKa_type: Optional[str] = None  # e.g., 'macro', 'micro'
            notes: Optional[str] = None
            conditions: 'LigandEntry.PkaBlock.LigandPkaBase.PkaConditions' = field(
                default_factory=lambda: LigandEntry.PkaBlock.LigandPkaBase.PkaConditions()
            )
            evidence: 'LigandEntry.PkaBlock.LigandPkaBase.PkaEvidence' = field(
                default_factory=lambda: LigandEntry.PkaBlock.LigandPkaBase.PkaEvidence()
            )

        @dataclass
        class LigandPkaMeasuredEntry(LigandPkaBase):
            """Measured (SRD) pKa entry fields."""
            measurement_method: Optional[str] = None  # e.g., potentiometry, spectrophotometry
            quality: Optional[str] = None  # freeform quality/grade flag

        @dataclass
        class LigandPkaEstimatedEntry(LigandPkaBase):
            """Estimated (Qupkake/other) pKa entry fields."""
            model_name: Optional[str] = None
            model_version: Optional[str] = None
            confidence: Optional[float] = None
            uncertainty: Optional[float] = None

        measured_pKa: List['LigandEntry.PkaBlock.LigandPkaMeasuredEntry'] = field(default_factory=list)
        estimated_pKa: List['LigandEntry.PkaBlock.LigandPkaEstimatedEntry'] = field(default_factory=list)

    # --- primary fields ---
    ligand_id: int
    ligand_name_SRD: str
    ligand_class_id: Optional[int] = None
    ligand_class_name: Optional[str] = None
    ligand_SMILES: Optional[str] = None
    ligand_InChi: Optional[str] = None
    formula: Optional[str] = None
    composition: Optional[str] = None
    synonyms: 'LigandEntry.Synonyms' = field(default_factory=lambda: LigandEntry.Synonyms())
    figure_definition: Optional[str] = None
    definition_HxL: Optional[str] = None
    pKa_bracket: 'LigandEntry.PkaBracketBlock' = field(default_factory=lambda: LigandEntry.PkaBracketBlock())
    pKa: 'LigandEntry.PkaBlock' = field(default_factory=lambda: LigandEntry.PkaBlock())


# =============================================================================
# Builder functions
# =============================================================================

def create_ligand_entry(data: Dict[str, Any] | None = None, tracker: MissingFieldTracker | None = None) -> LigandEntry:
    """Create a LigandEntry from a dictionary of ligand data.
    
    This function handles complex nested structures including synonyms, pKa blocks,
    and pKa bracket entries with full evidence and condition parsing.
    """
    tracker = tracker or DEFAULT_MISSING_TRACKER
    data = data or {}

    # Nested synonyms block (optional)
    syn_data = data.get("synonyms") or {}
    synonyms = LigandEntry.Synonyms(
        iupac_name=(None if _is_empty(syn_data.get("iupac_name")) else str(syn_data.get("iupac_name"))),
        common_name=(None if _is_empty(syn_data.get("common_name")) else str(syn_data.get("common_name"))),
    )

    # Required core fields with fallbacks
    ligand_id = data.get("ligand_id")
    if _is_empty(ligand_id):
        tracker.mark_missing("LigandEntry", "ligand_id")
        ligand_id = 0
    ligand_name = data.get("ligand_name_SRD")
    if _is_empty(ligand_name):
        tracker.mark_missing("LigandEntry", "ligand_name_SRD")
        ligand_name = ""

    entry = LigandEntry(
        ligand_id=int(ligand_id),
        ligand_name_SRD=str(ligand_name),
        ligand_class_id=(None if _is_empty(data.get("ligand_class_id")) else int(data.get("ligand_class_id"))),
        ligand_class_name=(None if _is_empty(data.get("ligand_class_name")) else str(data.get("ligand_class_name"))),
        # structural identifiers: accept both new keys (ligand_SMILES/ligand_InChi) and legacy SMILES/InChi
        ligand_SMILES=(None if _is_empty(data.get("ligand_SMILES") or data.get("SMILES")) else str(data.get("ligand_SMILES") or data.get("SMILES"))),
        ligand_InChi=(None if _is_empty(data.get("ligand_InChi") or data.get("InChi")) else str(data.get("ligand_InChi") or data.get("InChi"))),
        formula=(None if _is_empty(data.get("formula")) else str(data.get("formula"))),
        composition=(None if _is_empty(data.get("composition")) else str(data.get("composition"))),
        synonyms=synonyms,
        figure_definition=(None if _is_empty(data.get("figure_definition")) else str(data.get("figure_definition"))),
        definition_HxL=(None if _is_empty(data.get("definition_HxL")) else str(data.get("definition_HxL"))),
    )

    # Optional pKa block construction from input dict
    pka_in = data.get("pKa")
    if isinstance(pka_in, dict):
        # measured
        measured_list = pka_in.get("measured_pKa") or []
        if not isinstance(measured_list, list):
            tracker.mark_invalid("LigandEntry.PkaBlock", "measured_pKa")
            measured_list = []
        for item in measured_list:
            if not isinstance(item, dict):
                tracker.mark_invalid("LigandEntry.PkaBlock", "measured_pKa")
                continue
            try:
                base = LigandEntry.PkaBlock.LigandPkaMeasuredEntry(
                    source=str(item.get("source") or "SRD"),
                    bracket_from_state=str(item.get("bracket_from_state") or ""),
                    bracket_to_state=str(item.get("bracket_to_state") or ""),
                    pKa=(None if _is_empty(item.get("pKa")) else float(item.get("pKa"))),
                )
            except Exception:
                tracker.mark_invalid("LigandEntry.PkaBlock", "measured_pKa")
                continue
            # optional conditions
            cond = item.get("conditions") or {}
            if isinstance(cond, dict):
                if not _is_empty(cond.get("temperature_c")):
                    try:
                        base.conditions.temperature_c = float(cond.get("temperature_c"))
                    except Exception:
                        tracker.mark_invalid("LigandEntry.PkaBlock.PkaConditions", "temperature_c")
                if not _is_empty(cond.get("ionic_strength_mol_l")):
                    try:
                        base.conditions.ionic_strength_mol_l = float(cond.get("ionic_strength_mol_l"))
                    except Exception:
                        tracker.mark_invalid("LigandEntry.PkaBlock.PkaConditions", "ionic_strength_mol_l")
                s_val = cond.get("solvent")
                if not _is_empty(s_val):
                    try:
                        if isinstance(s_val, dict):
                            if not _is_empty(s_val.get("solvent_id")):
                                try:
                                    base.conditions.solvent.solvent_id = int(s_val.get("solvent_id"))
                                except Exception:
                                    base.conditions.solvent.solvent_id = s_val.get("solvent_id")
                            if not _is_empty(s_val.get("name")):
                                base.conditions.solvent.name = str(s_val.get("name"))
                            if not _is_empty(s_val.get("electrolyte_and_composition")):
                                base.conditions.solvent.electrolyte_and_composition = str(s_val.get("electrolyte_and_composition"))
                        else:
                            base.conditions.solvent.name = str(s_val)
                    except Exception:
                        try:
                            base.conditions.solvent.name = str(s_val)
                        except Exception:
                            pass
                if not _is_empty(cond.get("electrolyte")):
                    base.conditions.electrolyte = str(cond.get("electrolyte"))

            # optional hxl_states -> populate new pKa_bracket LigandPkaBracketBase objects
            hxl_states = item.get("hxl_states") or []
            if isinstance(hxl_states, list):
                for st in hxl_states:
                    if not isinstance(st, dict):
                        continue
                    try:
                        bs = LigandEntry.PkaBracketBlock.LigandPkaBracketBase(
                            state_id=str(st.get("state_id")),
                            charge=int(st.get("charge")),
                            formula=(None if _is_empty(st.get("formula")) else str(st.get("formula"))),
                            HxL_form=(None if _is_empty(st.get("HxL_form")) else str(st.get("HxL_form"))),
                            bracket_label=(None if _is_empty(st.get("bracket_label")) else str(st.get("bracket_label"))),
                            SMILES=(None if _is_empty(st.get("SMILES")) else str(st.get("SMILES"))),
                            InChi=(None if _is_empty(st.get("InChi")) else str(st.get("InChi"))),
                        )
                        ref_ids = st.get("reference_verkn_ligand_metal_ids") or st.get("verkn_ligand_metal_ids") or []
                        try:
                            if isinstance(ref_ids, list):
                                bs.reference_verkn_ligand_metal_ids.verkn_ligand_metal_ids_upper = []
                                bs.reference_verkn_ligand_metal_ids.verkn_ligand_metal_ids_lower = []
                                for rid in ref_ids:
                                    try:
                                        bs.reference_verkn_ligand_metal_ids.verkn_ligand_metal_ids_upper.append(int(rid))
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                    except Exception:
                        tracker.mark_invalid("LigandEntry.PkaBracketBlock.LigandPkaBracketBase", "state")
                        
            # optional evidence
            ev = item.get("evidence") or {}
            if isinstance(ev, dict):
                ids = ev.get("verkn_ligand_metal_ids") or []
                if isinstance(ids, list):
                    for vid in ids:
                        try:
                            base.evidence.verkn_ligand_metal_ids.append(int(vid))
                        except Exception:
                            tracker.mark_invalid("LigandEntry.PkaEvidence", "verkn_ligand_metal_ids")

            entry.pKa.measured_pKa.append(base)

        # Build measured_pKa_bracket from pKa.measured_pKa entries
        _build_measured_pka_bracket(entry, tracker, reference_charge=data.get("definition_HxL_charge"))

        # estimated
        estimated_list = pka_in.get("estimated_pKa") or []
        if not isinstance(estimated_list, list):
            tracker.mark_invalid("LigandEntry.PkaBlock", "estimated_pKa")
            estimated_list = []

        for item in estimated_list:
            if not isinstance(item, dict):
                tracker.mark_invalid("LigandEntry.PkaBlock", "estimated_pKa")
                continue

            item_model_name = (None if _is_empty(item.get("model_name")) else str(item.get("model_name")))
            item_model_version = (None if _is_empty(item.get("model_version")) else str(item.get("model_version")))
            try:
                item_conf = (None if _is_empty(item.get("confidence")) else float(item.get("confidence")))
            except Exception:
                item_conf = None
            try:
                item_unc = (None if _is_empty(item.get("uncertainty")) else float(item.get("uncertainty")))
            except Exception:
                item_unc = None

            hxl_states = item.get("hxl_states") or []
            if isinstance(hxl_states, list):
                for st in hxl_states:
                    if not isinstance(st, dict):
                        continue
                    try:
                        be = LigandEntry.PkaBracketBlock.LigandPkaBracketEstimatedEntry(
                            state_id=str(st.get("state_id")),
                            charge=int(st.get("charge")),
                            formula=(None if _is_empty(st.get("formula")) else str(st.get("formula"))),
                            HxL_form=(None if _is_empty(st.get("HxL_form")) else str(st.get("HxL_form"))),
                            bracket_label=(None if _is_empty(st.get("bracket_label")) else str(st.get("bracket_label"))),
                            SMILES=(None if _is_empty(st.get("SMILES")) else str(st.get("SMILES"))),
                            InChi=(None if _is_empty(st.get("InChi")) else str(st.get("InChi"))),
                            notes=(None if _is_empty(st.get("notes") or item.get("notes"))
                                   else str(st.get("notes") or item.get("notes"))),
                            model_name=item_model_name,
                            model_version=item_model_version,
                            confidence=item_conf,
                            uncertainty=item_unc,
                        )
                        ref_ids = st.get("reference_verkn_ligand_metal_ids") or st.get("verkn_ligand_metal_ids") or []
                        try:
                            if isinstance(ref_ids, list):
                                for rid in ref_ids:
                                    try:
                                        be.reference_verkn_ligand_metal_ids.verkn_ligand_metal_ids_upper.append(int(rid))
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                        entry.pKa_bracket.estimated_pKa_bracket.append(be)
                    except Exception:
                        tracker.mark_invalid("LigandEntry.PkaBracketBlock.LigandPkaBracketEstimatedEntry", "state")

        # Sort estimated bracket states by protonation
        _sort_estimated_bracket(entry)
        
        # Derive flat estimated_pKa entries from bracket-style estimated_pKa_bracket
        _derive_estimated_pka_from_bracket(entry, tracker)

    return entry


def _derive_formula_for_state(composition: str | None, definition_hxl: str | None, state_hxl: str) -> str | None:
    """Derive molecular formula for a protonation state based on composition and HxL forms.
    
    Args:
        composition: Base molecular formula (e.g., "C2H5NO2")
        definition_hxl: The figure definition HxL form (e.g., "HL" means base has 1 H on ligand)
        state_hxl: The target state HxL form (e.g., "L", "HL", "H2L")
    
    Returns:
        Derived molecular formula for the state, or None if unable to derive.
    """
    import re
    
    if not composition or not state_hxl:
        return None
    
    def _parse_hxl_h_count(hxl: str) -> int:
        parsed = _hxl_counts_for_charge(hxl)
        if parsed is None:
            raise ValueError(f"unresolved HxL form {hxl!r}")
        return parsed[0]

    def _parse_formula(formula: str) -> dict:
        """Parse molecular formula into element counts."""
        counts = {}
        pattern = re.compile(r'([A-Z][a-z]?)(\d*)')
        for el, num in pattern.findall(formula):
            if el:
                n = int(num) if num else 1
                counts[el] = counts.get(el, 0) + n
        return counts
    
    def _format_formula(counts: dict) -> str:
        """Format element counts back to molecular formula (Hill notation: C, H, then alphabetical)."""
        result = []
        # Carbon first
        if 'C' in counts:
            c = counts['C']
            result.append(f"C{c}" if c > 1 else "C")
        # Hydrogen second
        if 'H' in counts:
            h = counts['H']
            if h > 0:
                result.append(f"H{h}" if h > 1 else "H")
        # Rest alphabetically
        for el in sorted(counts.keys()):
            if el not in ('C', 'H'):
                n = counts[el]
                if n > 0:
                    result.append(f"{el}{n}" if n > 1 else el)
        return ''.join(result)
    
    try:
        # Parse base composition
        base_counts = _parse_formula(composition)
        base_h = base_counts.get('H', 0)
        
        # Get H count from definition and state
        reference_counts = _hxl_counts_for_charge(definition_hxl)
        state_counts = _hxl_counts_for_charge(state_hxl)
        if reference_counts is None or state_counts is None or reference_counts[1] != state_counts[1]:
            return None
        def_h_count = _parse_hxl_h_count(definition_hxl)
        state_h_count = _parse_hxl_h_count(state_hxl)
        
        # Calculate H difference: state_h - base_def_h
        h_diff = state_h_count - def_h_count
        
        # Adjust formula
        new_counts = base_counts.copy()
        new_counts['H'] = base_h + h_diff
        if new_counts['H'] < 0:
            return None
        
        return _format_formula(new_counts)
    except Exception:
        return None


def _hxl_counts_for_charge(hxl: str | None) -> tuple[int, int] | None:
    """Strict H/L counts for one protonation reference, including negative H states."""
    import re

    match = re.fullmatch(r"(?:H(?P<h>-?\d*))?L(?P<l>\d*)", str(hxl or "").strip())
    if match is None:
        return None
    h_text, l_text = match.group("h"), match.group("l")
    if h_text == "-":
        return None
    h_count = 0 if h_text is None else (int(h_text) if h_text else 1)
    l_count = int(l_text) if l_text else 1
    return (h_count, l_count) if l_count > 0 else None


def _reference_charge_for_brackets(entry: LigandEntry, supplied: object = None) -> int | None:
    """Use pip1c_3's validated charge, with a structure fallback for standalone callers.

    Do not infer neutrality from the absence of a formula charge suffix: a salt's
    composition may include the counterion while HxL describes its desalted ligand.
    """
    import math

    if not _is_empty(supplied):
        try:
            number = float(supplied)
            return int(number) if math.isfinite(number) and number.is_integer() else None
        except (TypeError, ValueError):
            return None
    try:
        from rdkit import Chem
        for structure, parser in ((entry.ligand_SMILES, Chem.MolFromSmiles),
                                  (entry.ligand_InChi, Chem.MolFromInchi)):
            if not structure or structure in ("*", "***"):
                continue
            try:
                mol = parser(structure)
                if (mol is not None and len(Chem.GetMolFrags(mol)) == 1
                        and all(atom.GetAtomicNum() > 0 for atom in mol.GetAtoms())):
                    return int(Chem.GetFormalCharge(mol))
            except (ValueError, RuntimeError):
                continue
    except ImportError:
        pass
    return None


def _active_formula_for_brackets(entry: LigandEntry, reference_charge: int | None) -> str | None:
    """Formula of the validated ligand component, never the original bulk salt composition."""
    try:
        from rdkit import Chem
        from rdkit.Chem.rdMolDescriptors import CalcMolFormula
        for structure, parser in ((entry.ligand_SMILES, Chem.MolFromSmiles),
                                  (entry.ligand_InChi, Chem.MolFromInchi)):
            if not structure or structure in ("*", "***"):
                continue
            try:
                mol = parser(structure)
                if (mol is not None and len(Chem.GetMolFrags(mol)) == 1
                        and all(atom.GetAtomicNum() > 0 for atom in mol.GetAtoms())
                        and (reference_charge is None or Chem.GetFormalCharge(mol) == reference_charge)):
                    return CalcMolFormula(mol)
            except (ValueError, RuntimeError):
                continue
    except ImportError:
        pass
    return None


def _charge_for_protonation_state(reference_hxl: str | None, state_hxl: str,
                                   reference_charge: int | None) -> int | None:
    """Each added/removed proton changes charge by +1/-1 at fixed ligand count."""
    reference = _hxl_counts_for_charge(reference_hxl)
    state = _hxl_counts_for_charge(state_hxl)
    if reference_charge is None or reference is None or state is None or reference[1] != state[1]:
        return None
    return reference_charge + state[0] - reference[0]


def _build_measured_pka_bracket(entry: LigandEntry, tracker: MissingFieldTracker,
                               reference_charge: object = None) -> None:
    """Build measured_pKa_bracket from pKa.measured_pKa entries."""
    import re
    
    def _hxl_index(hxl):
        try:
            if not hxl:
                return None
            s = str(hxl)
            m = re.search(r'-?\d+', s)
            if m:
                return int(m.group(0))
            su = s.upper()
            if 'HL' in su:
                return 1
            if 'L' in su:
                return 0
            if 'H' in su:
                return 1
            return None
        except Exception:
            return None

    try:
        measured = entry.pKa.measured_pKa
        if not isinstance(measured, list) or not measured:
            return
            
        edges = {}
        nodes = set()
        incoming = {}
        
        for m in measured:
            try:
                f = getattr(m, 'bracket_from_state', '') or ''
                t = getattr(m, 'bracket_to_state', '') or ''
                if not f or not t:
                    continue
                f_idx = _hxl_index(f)
                t_idx = _hxl_index(t)
                if f_idx is not None and t_idx is not None and f_idx < t_idx:
                    f, t = t, f
                    
                nodes.add(f)
                nodes.add(t)
                incoming.setdefault(t, set()).add(f)
                key = (f, t)
                pk = getattr(m, 'pKa', None)
                try:
                    pk_val = None if _is_empty(pk) else float(pk)
                except Exception:
                    pk_val = None
                evlist = []
                try:
                    evlist = list(getattr(m, 'evidence').verkn_ligand_metal_ids) if getattr(m, 'evidence', None) is not None else []
                except Exception:
                    evlist = []
                edges.setdefault(key, {'pKas': [], 'evidence': [], 'smi_from': None, 'smi_to': None, 'inchi_from': None, 'inchi_to': None})
                if pk_val is not None:
                    edges[key]['pKas'].append(pk_val)
                if evlist:
                    edges[key]['evidence'].extend(evlist)
            except Exception:
                continue

        # Produce linear ordering of states
        ordered = []
        try:
            starts = [n for n in nodes if n not in incoming]
            if len(starts) == 1:
                cur = starts[0]
                ordered.append(cur)
                seen = {cur}
                while True:
                    next_node = None
                    for (a, b) in edges.keys():
                        if a == cur and b not in seen:
                            next_node = b
                            break
                    if next_node is None:
                        break
                    ordered.append(next_node)
                    seen.add(next_node)
                    cur = next_node
            else:
                def _idx_or_zero(x):
                    i = _hxl_index(x)
                    return i if i is not None else 0
                ordered = sorted(list(nodes), key=_idx_or_zero, reverse=True)
        except Exception:
            ordered = sorted(list(nodes))

        if not ordered:
            return
            
        parent_charge = _reference_charge_for_brackets(entry, reference_charge)
        parent_formula = _active_formula_for_brackets(entry, parent_charge)
        reference_hxl = entry.definition_HxL
        if not reference_hxl:
            # Raw figure notation may carry a /charge suffix; its HxL core is still usable.
            reference_hxl = (entry.figure_definition or "").split("/", 1)[0]
        trans_pkas = []
        for i in range(len(ordered) - 1):
            k = (ordered[i], ordered[i + 1])
            info = edges.get(k) or {}
            pvals = info.get('pKas') or []
            bval = None
            try:
                if pvals:
                    bval = sum(pvals) / len(pvals)
            except Exception:
                bval = pvals[0] if pvals else None
            trans_pkas.append(bval)

        for i, state in enumerate(ordered):
            try:
                if i == 0:
                    lower = float('-inf')
                    upper = trans_pkas[0] if trans_pkas else float('inf')
                elif i == len(ordered) - 1:
                    lower = trans_pkas[i - 1] if trans_pkas else float('-inf')
                    upper = float('inf')
                else:
                    lower = trans_pkas[i - 1] if i - 1 < len(trans_pkas) else None
                    upper = trans_pkas[i] if i < len(trans_pkas) else None

                lo_val = lower if lower is not None else float('-inf')
                hi_val = upper if upper is not None else float('inf')
                try:
                    if lo_val is not None and hi_val is not None and lo_val > hi_val:
                        lo_val, hi_val = hi_val, lo_val
                except Exception:
                    pass
                lbl = f"({('-inf' if lo_val == float('-inf') else ('%g' % lo_val))}, {('+inf' if hi_val == float('inf') else ('%g' % hi_val))})"

                verkn_block = {'verkn_ligand_metal_ids_upper': [], 'verkn_ligand_metal_ids_lower': []}
                if i > 0:
                    prev = ordered[i - 1]
                    info_prev = edges.get((prev, state)) or {}
                    if info_prev.get('evidence'):
                        verkn_block['verkn_ligand_metal_ids_lower'].extend(info_prev.get('evidence'))
                if i < len(ordered) - 1:
                    nxt = ordered[i + 1]
                    info_next = edges.get((state, nxt)) or {}
                    if info_next.get('evidence'):
                        verkn_block['verkn_ligand_metal_ids_upper'].extend(info_next.get('evidence'))

                # Derive formula from composition and HxL state
                state_formula = _derive_formula_for_state(
                    parent_formula,
                    reference_hxl,
                    str(state)
                )

                be = LigandEntry.PkaBracketBlock.LigandPkaBracketMeasuredEntry(
                    state_id=str(state),
                    charge=_charge_for_protonation_state(reference_hxl, str(state), parent_charge),
                    formula=state_formula,
                    notes=("Formula derived from the active ligand structure; original source composition "
                           "is retained in ligand_card.composition."
                           if parent_formula and parent_formula != entry.composition else None),
                    HxL_form=str(state),
                    bracket_label=(None if (lower == float('-inf') and upper == float('inf')) else str(lbl)),
                    SMILES=None,
                    InChi=None,
                    measurement_method=None,
                    quality=None,
                )
                try:
                    for v in verkn_block.get('verkn_ligand_metal_ids_upper', []):
                        be.reference_verkn_ligand_metal_ids.verkn_ligand_metal_ids_upper.append(int(v))
                except Exception:
                    pass
                try:
                    for v in verkn_block.get('verkn_ligand_metal_ids_lower', []):
                        be.reference_verkn_ligand_metal_ids.verkn_ligand_metal_ids_lower.append(int(v))
                except Exception:
                    pass

                entry.pKa_bracket.measured_pKa_bracket.append(be)
            except Exception:
                continue
    except Exception:
        pass


def _sort_estimated_bracket(entry: LigandEntry) -> None:
    """Sort estimated bracket states by protonation (most-H -> least-H)."""
    import re
    
    def _obj_hxl_index(o):
        try:
            hf = getattr(o, 'HxL_form', None)
            s = '' if hf is None else str(hf)
            m = re.search(r'-?\d+', s)
            if m:
                return int(m.group(0))
            su = s.upper()
            if 'HL' in su:
                return 1
            if 'L' in su and 'HL' not in su:
                return 0
            if 'H' in su:
                return 1
            return 0
        except Exception:
            return 0

    try:
        entry.pKa_bracket.estimated_pKa_bracket.sort(key=_obj_hxl_index, reverse=True)
    except Exception:
        pass


def _derive_estimated_pka_from_bracket(entry: LigandEntry, tracker: MissingFieldTracker) -> None:
    """Derive flat estimated_pKa entries from bracket-style estimated_pKa_bracket."""
    try:
        bracket_states = entry.pKa_bracket.estimated_pKa_bracket
        if not isinstance(bracket_states, list) or not bracket_states:
            return
            
        parsed = []
        for s in bracket_states:
            lbl = getattr(s, "bracket_label", None)
            lower = float("-inf")
            upper = float("inf")
            if isinstance(lbl, str) and lbl.strip():
                try:
                    txt = lbl.strip().lstrip('(').rstrip(')')
                    left_s, right_s = [p.strip() for p in txt.split(',')]
                    if left_s.lower() not in ("-inf", "-infty", "-infinity"):
                        lower = float(left_s)
                    if right_s.lower() not in ("+inf", "inf", "+infty", "+infinity"):
                        upper = float(right_s)
                except Exception:
                    pass
            parsed.append((lower, upper, getattr(s, "HxL_form", None), getattr(s, "SMILES", None), 
                          getattr(s, "InChi", None), getattr(s, "model_name", None), 
                          getattr(s, "confidence", None), getattr(s, "uncertainty", None), 
                          getattr(s, "reference_verkn_ligand_metal_ids", None), getattr(s, "notes", None)))

        bounds = set()
        for lo, hi, *_ in parsed:
            if lo not in (float("-inf"), float("inf")):
                bounds.add(lo)
            if hi not in (float("-inf"), float("inf")):
                bounds.add(hi)

        for b in sorted(bounds):
            left = None
            right = None
            for lo, hi, hxl, smi, inchi, mname, conf, unc, refs, notes in parsed:
                try:
                    if hi == b:
                        left = (lo, hi, hxl, smi, inchi, mname, conf, unc, refs, notes)
                    if lo == b:
                        right = (lo, hi, hxl, smi, inchi, mname, conf, unc, refs, notes)
                except Exception:
                    continue

            if left is None or right is None:
                continue

            try:
                l_hxl = left[2] or ""
                r_hxl = right[2] or ""
                l_smi = left[3]
                r_smi = right[3]
                l_inchi = left[4]
                r_inchi = right[4]
                model_name = right[5] or left[5] or None
                confidence = right[6] or left[6] or None
                uncertainty = right[7] or left[7] or None

                def _hxl_index(hxl):
                    try:
                        if not hxl:
                            return None
                        s = str(hxl)
                        num = ''.join(ch for ch in s if ch.isdigit())
                        return int(num) if num else None
                    except Exception:
                        return None

                l_idx = _hxl_index(l_hxl)
                r_idx = _hxl_index(r_hxl)

                if l_idx is not None and r_idx is not None and l_idx > r_idx:
                    bf_state, bt_state = str(r_hxl), str(l_hxl)
                    smi_from, smi_to = r_smi, l_smi
                    inchi_from, inchi_to = r_inchi, l_inchi
                else:
                    bf_state, bt_state = str(l_hxl), str(r_hxl)
                    smi_from, smi_to = l_smi, r_smi
                    inchi_from, inchi_to = l_inchi, r_inchi

                est = LigandEntry.PkaBlock.LigandPkaEstimatedEntry(
                    source=(model_name or "estimated"),
                    bracket_from_state=bf_state,
                    bracket_to_state=bt_state,
                    SMILES_from_state=(None if _is_empty(smi_from) else str(smi_from)),
                    InChi_from_state=(None if _is_empty(inchi_from) else str(inchi_from)),
                    SMILES_to_state=(None if _is_empty(smi_to) else str(smi_to)),
                    InChi_to_state=(None if _is_empty(inchi_to) else str(inchi_to)),
                    pKa=(None if _is_empty(b) else float(b)),
                    pKa_type=None,
                    notes=(right[9] or left[9] or None),
                    model_name=(None if _is_empty(model_name) else str(model_name)),
                    model_version=None,
                    confidence=(None if _is_empty(confidence) else float(confidence)),
                    uncertainty=(None if _is_empty(uncertainty) else float(uncertainty)),
                )
                entry.pKa.estimated_pKa.append(est)
            except Exception:
                tracker.mark_invalid("LigandEntry.PkaBlock", "estimated_pKa_from_bracket")
    except Exception:
        pass


def load_ligand_entry_from_json(source: Any, tracker: MissingFieldTracker | None = None) -> LigandEntry:
    """Load a LigandEntry from a JSON file path, JSON string, or dict.

    Returns a LigandEntry instance by delegating to create_ligand_entry when a
    dict-like object is supplied. If a LigandEntry is supplied, it is returned
    unchanged.
    """
    tracker = tracker or DEFAULT_MISSING_TRACKER
    if isinstance(source, LigandEntry):
        return source
    obj = _load_json_like(source)
    if isinstance(obj, dict):
        return create_ligand_entry(obj, tracker)
    raise TypeError("Unsupported source for load_ligand_entry_from_json: expected file path, JSON string, dict, or LigandEntry")




__all__ = [
    "LigandEntry",
    "create_ligand_entry",
    "load_ligand_entry_from_json",
]
