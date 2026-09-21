"""
Species Library Builder and Phase Classifier for beta_definition parsing.
Extracts all unique species from parsed equations and classifies them by phase.
"""
import re
import json
from typing import Dict, List, Tuple, Optional, Set, NamedTuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import pandas as pd

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE CLASSIFICATION PATTERNS
# ═══════════════════════════════════════════════════════════════════════════════

# Phase tag patterns - capture phase annotation from species labels
RE_PHASE_TAG = re.compile(r'\((s|g|l|aq)(?:\s*,\s*[^)]+)?\)\s*$', re.IGNORECASE)
RE_PHASE_IN_MIDDLE = re.compile(r'\((s|g|l|aq)(?:\s*,\s*[^)]+)?\)', re.IGNORECASE)

# Common gas phase indicators (beyond explicit (g) tag)
GAS_INDICATORS = {
    'CO2', 
}

# Common solid phase indicators (mineral/precipitate names)
SOLID_INDICATORS = { 
}


# ═══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════

class PhaseType:
    """Enumeration of phase types."""
    AQUEOUS = "aqueous"      # (aq) or default for ions/complexes
    SOLID = "solid"          # (s)
    GAS = "gas"              # (g)
    LIQUID = "liquid"        # (l) - rare, for pure liquids like H2O(l)
    UNKNOWN = "unknown"      # Cannot determine


@dataclass
class SpeciesEntry:
    """Single species entry in the library."""
    species_raw: str              # Original species string with phase tags
    species_clean: str            # Species with phase tags removed
    phase: str                    # Phase classification
    phase_source: str             # How phase was determined: "explicit_tag", "inferred", "default"
    
    # Elemental composition (from parsing)
    elements: Dict[str, float] = field(default_factory=dict)
    
    # Occurrence tracking
    beta_ids: List[int] = field(default_factory=list)
    occurrence_count: int = 0
    in_numerator: bool = False
    in_denominator: bool = False
    
    # Chemical classification hints
    is_metal_species: bool = False     # Contains M
    is_ligand_species: bool = False    # Contains L
    is_proton_carrier: bool = False    # Contains H (as H+, not in H2O/OH)
    is_water: bool = False             # H2O
    is_hydroxide: bool = False         # OH-
    is_polymetal: bool = False         # Polymetal cluster (Mo7O24, V10O28, etc.)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON export."""
        return asdict(self)


class SpeciesLibrary:
    """
    Container for all unique species extracted from beta definitions.
    Provides phase classification and lookup capabilities.
    """
    
    def __init__(self):
        self._species: Dict[str, SpeciesEntry] = {}  # key = species_raw
        self._by_phase: Dict[str, Set[str]] = defaultdict(set)
        self._by_clean: Dict[str, List[str]] = defaultdict(list)  # clean → [raw variants]
    
    def add_species(
        self,
        species_raw: str,
        elements: Dict[str, float] = None,
        beta_id: int = None,
        in_numerator: bool = False,
        in_denominator: bool = False,
    ) -> SpeciesEntry:
        """Add or update a species entry."""
        if species_raw in self._species:
            entry = self._species[species_raw]
            if beta_id and beta_id not in entry.beta_ids:
                entry.beta_ids.append(beta_id)
            entry.occurrence_count += 1
            entry.in_numerator = entry.in_numerator or in_numerator
            entry.in_denominator = entry.in_denominator or in_denominator
            return entry
        
        # New species - classify it
        phase, phase_source = self._classify_phase(species_raw)
        clean = self._strip_phase_tags(species_raw)
        
        entry = SpeciesEntry(
            species_raw=species_raw,
            species_clean=clean,
            phase=phase,
            phase_source=phase_source,
            elements=elements or {},
            beta_ids=[beta_id] if beta_id else [],
            occurrence_count=1,
            in_numerator=in_numerator,
            in_denominator=in_denominator,
        )
        
        # Set chemical classification flags
        entry.is_metal_species = 'M' in entry.elements
        entry.is_ligand_species = 'L' in entry.elements
        entry.is_proton_carrier = 'H' in entry.elements and clean not in ('H2O', 'OH')
        entry.is_water = clean == 'H2O'
        entry.is_hydroxide = clean == 'OH'
        entry.is_polymetal = self._is_polymetal(clean)
        
        # Register
        self._species[species_raw] = entry
        self._by_phase[phase].add(species_raw)
        self._by_clean[clean].append(species_raw)
        
        return entry
    
    def _classify_phase(self, species: str) -> Tuple[str, str]:
        """
        Classify species phase based on annotations and chemical intuition.
        Returns (phase, source).
        """
        # Check for explicit phase tag at end: [X(s)], [X(g)], [X(l)], [X(aq)]
        m = RE_PHASE_TAG.search(species)
        if m:
            tag = m.group(1).lower()
            if tag == 's':
                return PhaseType.SOLID, "explicit_tag"
            elif tag == 'g':
                return PhaseType.GAS, "explicit_tag"
            elif tag == 'l':
                return PhaseType.LIQUID, "explicit_tag"
            elif tag == 'aq':
                return PhaseType.AQUEOUS, "explicit_tag"
        
        # Check for phase tag in middle (less common)
        m = RE_PHASE_IN_MIDDLE.search(species)
        if m:
            tag = m.group(1).lower()
            if tag == 's':
                return PhaseType.SOLID, "explicit_tag_internal"
            elif tag == 'g':
                return PhaseType.GAS, "explicit_tag_internal"
            elif tag == 'l':
                return PhaseType.LIQUID, "explicit_tag_internal"
            elif tag == 'aq':
                return PhaseType.AQUEOUS, "explicit_tag_internal"
        
        # Clean species for pattern matching
        clean = self._strip_phase_tags(species)
        clean_upper = clean.upper()
        
        # Check for known gas indicators
        for gas_pattern in GAS_INDICATORS:
            if clean_upper == gas_pattern or clean_upper.startswith(gas_pattern + '('):
                return PhaseType.GAS, "inferred_gas_pattern"
        
        # Default: most species in aqueous equilibria are in solution
        return PhaseType.AQUEOUS, "default_aqueous"
    
    def _strip_phase_tags(self, species: str) -> str:
        """Remove phase annotations but keep chemical formula."""
        # Remove brackets first
        s = species.strip()
        if s.startswith('[') and s.endswith(']'):
            s = s[1:-1]
        elif s.startswith('['):
            s = s[1:]
        
        # Remove phase tags like (s), (g), (l), (aq), (s, red), etc.
        s = RE_PHASE_TAG.sub('', s)
        s = RE_PHASE_IN_MIDDLE.sub('', s)
        
        return s.strip()
    
    def _is_polymetal(self, clean_species: str) -> bool:
        """Check if species is a polymetal cluster."""
        polymetal_patterns = [
            r'Mo\d+O\d+', r'W\d+O\d+', r'V\d+O\d+',  # Molybdate, tungstate, vanadate
            r'Cr\d+O\d+', r'Mn\d+O\d+',              # Chromate, manganate
            r'As\d+O\d+', r'Si\d+O\d+',              # Arsenate, silicate
        ]
        for pat in polymetal_patterns:
            if re.search(pat, clean_species):
                return True
        return False
    
    def get(self, species_raw: str) -> Optional[SpeciesEntry]:
        """Get species entry by raw string."""
        return self._species.get(species_raw)
    
    def get_by_phase(self, phase: str) -> List[SpeciesEntry]:
        """Get all species of a given phase."""
        return [self._species[s] for s in self._by_phase.get(phase, [])]
    
    def get_all_phases(self) -> Dict[str, List[SpeciesEntry]]:
        """Get species grouped by phase."""
        return {
            phase: [self._species[s] for s in species_set]
            for phase, species_set in self._by_phase.items()
        }
    
    @property
    def all_species(self) -> List[SpeciesEntry]:
        """Get all species entries."""
        return list(self._species.values())
    
    @property
    def unique_count(self) -> int:
        """Number of unique species."""
        return len(self._species)
    
    def phase_counts(self) -> Dict[str, int]:
        """Count species by phase."""
        return {phase: len(species) for phase, species in self._by_phase.items()}
    
    def to_dataframe(self) -> pd.DataFrame:
        """Export library to DataFrame."""
        records = []
        for entry in self._species.values():
            record = {
                'species_raw': entry.species_raw,
                'species_clean': entry.species_clean,
                'phase': entry.phase,
                'phase_source': entry.phase_source,
                'elements_json': json.dumps(entry.elements),
                'beta_ids': json.dumps(entry.beta_ids),
                'occurrence_count': entry.occurrence_count,
                'in_numerator': entry.in_numerator,
                'in_denominator': entry.in_denominator,
                'is_metal_species': entry.is_metal_species,
                'is_ligand_species': entry.is_ligand_species,
                'is_proton_carrier': entry.is_proton_carrier,
                'is_water': entry.is_water,
                'is_hydroxide': entry.is_hydroxide,
                'is_polymetal': entry.is_polymetal,
            }
            records.append(record)
        
        df = pd.DataFrame(records)
        # Sort by phase, then by species
        if not df.empty:
            phase_order = {PhaseType.AQUEOUS: 0, PhaseType.SOLID: 1, PhaseType.GAS: 2, 
                          PhaseType.LIQUID: 3, PhaseType.UNKNOWN: 4}
            df['_phase_order'] = df['phase'].map(lambda x: phase_order.get(x, 5))
            df = df.sort_values(['_phase_order', 'species_clean']).drop(columns=['_phase_order'])
        
        return df
    
    def to_json(self) -> str:
        """Export library to JSON string."""
        data = {
            'summary': {
                'total_species': self.unique_count,
                'phase_counts': self.phase_counts(),
            },
            'species': [entry.to_dict() for entry in self._species.values()]
        }
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    def summary(self) -> str:
        """Generate summary string."""
        counts = self.phase_counts()
        lines = [
            f"Species Library Summary",
            f"-" * 40,
            f"Total unique species: {self.unique_count}",
            "",
            "By phase:",
        ]
        for phase, count in sorted(counts.items()):
            lines.append(f"  {phase:12s}: {count:5d}")
        
        # Count by chemical type
        metal_count = sum(1 for e in self._species.values() if e.is_metal_species)
        ligand_count = sum(1 for e in self._species.values() if e.is_ligand_species)
        polymetal_count = sum(1 for e in self._species.values() if e.is_polymetal)
        
        lines.extend([
            "",
            "By chemical type:",
            f"  Metal species (contains M): {metal_count}",
            f"  Ligand species (contains L): {ligand_count}",
            f"  Polymetal clusters:          {polymetal_count}",
        ])
        
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# BUILDER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def build_species_library_from_df(
    df: pd.DataFrame,
    tree_col: str = "equation_tree_json",
    beta_id_col: str = "beta_definitionID",
) -> SpeciesLibrary:
    """
    Build species library from processed beta_definition DataFrame.
    
    Args:
        df: DataFrame with parsed equation trees
        tree_col: Column containing equation tree JSON
        beta_id_col: Column with beta definition IDs
        
    Returns:
        Populated SpeciesLibrary
    """
    library = SpeciesLibrary()
    
    for idx, row in df.iterrows():
        tree_json = row.get(tree_col)
        if pd.isna(tree_json) or not tree_json:
            continue
        
        # Parse tree JSON
        try:
            if isinstance(tree_json, str):
                tree = json.loads(tree_json)
            else:
                tree = tree_json
        except (json.JSONDecodeError, TypeError):
            continue
        
        beta_id = row.get(beta_id_col)
        if pd.notna(beta_id):
            try:
                beta_id = int(float(beta_id))
            except (ValueError, TypeError):
                beta_id = None
        else:
            beta_id = None
        
        # Extract species from numerator
        numerator = tree.get('numerator', [])
        for sp_entry in numerator:
            if isinstance(sp_entry, dict):
                species_raw = sp_entry.get('species', '')
                elements = sp_entry.get('elements_total', {})
                if species_raw:
                    library.add_species(
                        species_raw=species_raw,
                        elements=elements,
                        beta_id=beta_id,
                        in_numerator=True,
                    )
        
        # Extract species from denominator
        denominator = tree.get('denominator', [])
        for sp_entry in denominator:
            if isinstance(sp_entry, dict):
                species_raw = sp_entry.get('species', '')
                elements = sp_entry.get('elements_total', {})
                if species_raw:
                    library.add_species(
                        species_raw=species_raw,
                        elements=elements,
                        beta_id=beta_id,
                        in_denominator=True,
                    )
    
    return library


def add_species_phase_columns(
    df: pd.DataFrame,
    library: SpeciesLibrary,
    tree_col: str = "equation_tree_json",
    out_prefix: str = "species",
) -> pd.DataFrame:
    """
    Add species classification columns to the DataFrame.
    
    Adds columns:
        - {prefix}_list_all: All species in equation
        - {prefix}_list_solid: Solid phase species
        - {prefix}_list_gas: Gas phase species  
        - {prefix}_list_aqueous: Aqueous phase species
        - {prefix}_count_by_phase: JSON dict of phase counts
    """
    df = df.copy()
    
    all_species_list = []
    solid_list = []
    gas_list = []
    aqueous_list = []
    phase_counts_list = []
    
    for idx, row in df.iterrows():
        tree_json = row.get(tree_col)
        
        row_species = {'all': [], 'solid': [], 'gas': [], 'aqueous': [], 'liquid': []}
        
        if pd.notna(tree_json) and tree_json:
            try:
                if isinstance(tree_json, str):
                    tree = json.loads(tree_json)
                else:
                    tree = tree_json
                
                # Collect all species from tree
                for side in ['numerator', 'denominator']:
                    for sp_entry in tree.get(side, []):
                        if isinstance(sp_entry, dict):
                            species_raw = sp_entry.get('species', '')
                            if species_raw:
                                entry = library.get(species_raw)
                                if entry:
                                    row_species['all'].append(species_raw)
                                    if entry.phase == PhaseType.SOLID:
                                        row_species['solid'].append(species_raw)
                                    elif entry.phase == PhaseType.GAS:
                                        row_species['gas'].append(species_raw)
                                    elif entry.phase == PhaseType.AQUEOUS:
                                        row_species['aqueous'].append(species_raw)
                                    elif entry.phase == PhaseType.LIQUID:
                                        row_species['liquid'].append(species_raw)
            except (json.JSONDecodeError, TypeError):
                pass
        
        # Deduplicate
        for key in row_species:
            row_species[key] = list(dict.fromkeys(row_species[key]))
        
        all_species_list.append(json.dumps(row_species['all']))
        solid_list.append(json.dumps(row_species['solid']))
        gas_list.append(json.dumps(row_species['gas']))
        aqueous_list.append(json.dumps(row_species['aqueous']))
        
        phase_counts = {
            'solid': len(row_species['solid']),
            'gas': len(row_species['gas']),
            'aqueous': len(row_species['aqueous']),
            'liquid': len(row_species['liquid']),
        }
        phase_counts_list.append(json.dumps(phase_counts))
    
    df[f'{out_prefix}_list_all'] = all_species_list
    df[f'{out_prefix}_list_solid'] = solid_list
    df[f'{out_prefix}_list_gas'] = gas_list
    df[f'{out_prefix}_list_aqueous'] = aqueous_list
    df[f'{out_prefix}_count_by_phase'] = phase_counts_list
    
    return df


def enrich_equation_tree_with_phase(
    df: pd.DataFrame,
    library: SpeciesLibrary,
    tree_col: str = "equation_tree_json",
    inplace: bool = True,
) -> pd.DataFrame:
    """
    Enrich the equation tree JSON by adding phase state information to each species.
    
    For each species in the tree, adds:
        - phase: "aqueous", "solid", "gas", "liquid", or "unknown"
        - phase_source: How the phase was determined
        - species_clean: Species label with phase tags removed
    
    Args:
        df: DataFrame with equation tree JSON column
        library: SpeciesLibrary with phase classifications
        tree_col: Column containing equation tree JSON
        inplace: If True, overwrites the original tree_col. If False, creates a new column.
        
    Returns:
        DataFrame with enriched equation tree column
    """
    df = df.copy()
    
    enriched_trees = []
    
    for idx, row in df.iterrows():
        tree_json = row.get(tree_col)
        
        if pd.isna(tree_json) or not tree_json:
            enriched_trees.append(tree_json)  # Keep original (None or empty)
            continue
        
        try:
            if isinstance(tree_json, str):
                tree = json.loads(tree_json)
            else:
                tree = dict(tree_json)  # Make a copy
            
            # Enrich numerator species
            if 'numerator' in tree:
                for sp_entry in tree['numerator']:
                    if isinstance(sp_entry, dict) and 'species' in sp_entry:
                        species_raw = sp_entry['species']
                        lib_entry = library.get(species_raw)
                        if lib_entry:
                            sp_entry['phase'] = lib_entry.phase
                            sp_entry['phase_source'] = lib_entry.phase_source
                            sp_entry['species_clean'] = lib_entry.species_clean
                        else:
                            # Classify on the fly if not in library
                            phase, phase_source = library._classify_phase(species_raw)
                            clean = library._strip_phase_tags(species_raw)
                            sp_entry['phase'] = phase
                            sp_entry['phase_source'] = phase_source
                            sp_entry['species_clean'] = clean
            
            # Enrich denominator species
            if 'denominator' in tree:
                for sp_entry in tree['denominator']:
                    if isinstance(sp_entry, dict) and 'species' in sp_entry:
                        species_raw = sp_entry['species']
                        lib_entry = library.get(species_raw)
                        if lib_entry:
                            sp_entry['phase'] = lib_entry.phase
                            sp_entry['phase_source'] = lib_entry.phase_source
                            sp_entry['species_clean'] = lib_entry.species_clean
                        else:
                            phase, phase_source = library._classify_phase(species_raw)
                            clean = library._strip_phase_tags(species_raw)
                            sp_entry['phase'] = phase
                            sp_entry['phase_source'] = phase_source
                            sp_entry['species_clean'] = clean
            
            enriched_trees.append(json.dumps(tree, ensure_ascii=False))
            
        except (json.JSONDecodeError, TypeError) as e:
            enriched_trees.append(tree_json)  # Keep original on error
    
    # Overwrite the original column (inplace behavior)
    df[tree_col] = enriched_trees
    
    return df


def classify_reaction_type(
    df: pd.DataFrame,
    library: SpeciesLibrary,
    tree_col: str = "equation_tree_json",
    out_col: str = "reaction_type",
) -> pd.DataFrame:
    """
    Classify reaction type based on species phases.
    
    Reaction types:
        - homogeneous_aqueous: All species aqueous
        - precipitation: Aqueous → Solid (solid in numerator or denominator)
        - dissolution: Solid → Aqueous (solid in denominator)
        - gas_absorption: Gas → Aqueous
        - gas_evolution: Aqueous → Gas
        - mixed: Multiple phase transitions
    """
    df = df.copy()
    
    reaction_types = []
    
    for idx, row in df.iterrows():
        tree_json = row.get(tree_col)
        
        if pd.isna(tree_json) or not tree_json:
            reaction_types.append("unknown")
            continue
        
        try:
            if isinstance(tree_json, str):
                tree = json.loads(tree_json)
            else:
                tree = tree_json
            
            # Collect phases for numerator and denominator
            num_phases = set()
            den_phases = set()
            
            for sp_entry in tree.get('numerator', []):
                if isinstance(sp_entry, dict):
                    species_raw = sp_entry.get('species', '')
                    if species_raw:
                        entry = library.get(species_raw)
                        if entry:
                            num_phases.add(entry.phase)
            
            for sp_entry in tree.get('denominator', []):
                if isinstance(sp_entry, dict):
                    species_raw = sp_entry.get('species', '')
                    if species_raw:
                        entry = library.get(species_raw)
                        if entry:
                            den_phases.add(entry.phase)
            
            # Classify based on phase distribution
            all_phases = num_phases | den_phases
            
            if len(all_phases) == 0:
                reaction_types.append("unknown")
            elif all_phases == {PhaseType.AQUEOUS}:
                reaction_types.append("homogeneous_aqueous")
            elif PhaseType.SOLID in den_phases and PhaseType.SOLID not in num_phases:
                reaction_types.append("dissolution")
            elif PhaseType.SOLID in num_phases and PhaseType.SOLID not in den_phases:
                reaction_types.append("precipitation")
            elif PhaseType.GAS in den_phases and PhaseType.GAS not in num_phases:
                reaction_types.append("gas_absorption")
            elif PhaseType.GAS in num_phases and PhaseType.GAS not in den_phases:
                reaction_types.append("gas_evolution")
            elif PhaseType.SOLID in all_phases or PhaseType.GAS in all_phases:
                reaction_types.append("heterogeneous_mixed")
            else:
                reaction_types.append("homogeneous_aqueous")
                
        except (json.JSONDecodeError, TypeError):
            reaction_types.append("parse_error")
    
    df[out_col] = reaction_types
    
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def export_species_library(
    library: SpeciesLibrary,
    out_dir,
    prefix: str = "species_library",
) -> Dict[str, str]:
    """
    Export species library to CSV and JSON files.
    
    Returns dict of exported file paths.
    """
    from pathlib import Path
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    paths = {}
    
    # Full library CSV
    df = library.to_dataframe()
    csv_path = out_dir / f"{prefix}_full.csv"
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    paths['csv_full'] = str(csv_path)
    
    # JSON export
    json_path = out_dir / f"{prefix}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        f.write(library.to_json())
    paths['json'] = str(json_path)
    
    # Phase-specific CSVs
    if not df.empty and 'phase' in df.columns:
        for phase in [PhaseType.AQUEOUS, PhaseType.SOLID, PhaseType.GAS, PhaseType.LIQUID]:
            phase_df = df[df['phase'] == phase]
            if not phase_df.empty:
                phase_path = out_dir / f"{prefix}_{phase}.csv"
                phase_df.to_csv(phase_path, index=False, encoding='utf-8-sig')
                paths[f'csv_{phase}'] = str(phase_path)
    
    # Summary text file
    summary_path = out_dir / f"{prefix}_summary.txt"
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(library.summary())
    paths['summary'] = str(summary_path)
    
    return paths
