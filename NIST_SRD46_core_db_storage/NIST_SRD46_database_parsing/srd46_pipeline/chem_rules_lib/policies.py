"""Reference-condition and archived Qupkake selection policies (REF/QUP)."""
from __future__ import annotations

from .registry import Rule, _declare


# =============================================================================
# REF  reference-condition policy (pip2a soft filter, pip2b preferred-pKa selection)
# =============================================================================
# Not corrections but hand-chosen policy numbers that decide which measurement a card prefers.
# Declared once here; stage_pip2b passes them explicitly, stage_pip2a asserts the wrapped
# module's defaults still equal them (its dataclass defaults stay in place), and both
# write one policy row to the ledger so a reader of manual_fix_log sees the conditions used.
REF01_TEMPERATURE_C = 25.0
REF01_TEMPERATURE_TOLERANCE_C = 5.0
REF01_IONIC_STRENGTH_M = 0.1
REF01_IONIC_STRENGTH_TOLERANCE_M = 0.15
REF01_HPLUS_METAL_ID = 68          # SRD46 metal id of H+ (protonation constants)
REF01_CONSTANT_TYPE_K = 3          # constanttyp id of an equilibrium constant K (2 = dH, 4 = dS, 1 = '*')
_declare(Rule("REF-01", "pip2a_equilibrium_maps / pip2b_ligand_pka_chains", "equilibrium_maps.db / preferred_ligand_pka_chains",
              f"reference conditions {REF01_TEMPERATURE_C:g} C +-{REF01_TEMPERATURE_TOLERANCE_C:g}, I = {REF01_IONIC_STRENGTH_M:g} M "
              f"+-{REF01_IONIC_STRENGTH_TOLERANCE_M:g}; H+ = metal {REF01_HPLUS_METAL_ID}; K = constanttyp {REF01_CONSTANT_TYPE_K}",
              "the preferred pKa chain and the condition bins depend on these numbers; they are policy, not data"))


# =============================================================================
# QUP  Qupkake pKa archive fill
# =============================================================================
# The Qupkake ML pKa states are read from the SDF directory. One ligand (10175) has parsed
# results only in the archived wide CSV of the earlier run (no SDF file was kept). Rows of
# ligands that have NO SDF file at all are appended from the first existing archive CSV;
# parse failures of existing SDFs are NOT back-filled (they are diagnostics, not gaps).
_declare(Rule("QUP-01", "pip1c_5b_qupkake_parse", "qupkake_pka_liganden",
              "ligands without any SDF file are appended from the archived parsed CSV",
              "the archive is the only surviving record of those states (ligand 10175: Q_-1/Q_-2 brackets)"))
QUP01_ONLY_IDS_WITHOUT_SDF = True


__all__ = [
    'REF01_TEMPERATURE_C',
    'REF01_TEMPERATURE_TOLERANCE_C',
    'REF01_IONIC_STRENGTH_M',
    'REF01_IONIC_STRENGTH_TOLERANCE_M',
    'REF01_HPLUS_METAL_ID',
    'REF01_CONSTANT_TYPE_K',
    'QUP01_ONLY_IDS_WITHOUT_SDF',
]
