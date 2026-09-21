"""
srd46_pipeline - end-to-end runner for the NIST SRD 46 parsing chain.

One command (``python run_srd46_pipeline.py``) drives every parser module
(pip1a, pip1b, pip1c_1..6, pip2a, pip2b, pip2c, literature, pip2d) in-process.
Intermediates live in a single staging SQLite database; the only files
written by default are the four end products consumed downstream:

    _output/pip2c_cards_sql/srd46_cards.db
    _output/pip2c_cards_sql/srd46_equilibrium_maps.db
    _output/pip2c_cards_sql/srd46_literature.db
    _output/pip2c_cards_sql/srd46_ligand_fingerprints.db

Per-stage intermediate artifacts (CSV/JSON/log) are exported only with ``--debug``.
"""

__all__ = ["paths", "staging", "legacy", "runner"]
