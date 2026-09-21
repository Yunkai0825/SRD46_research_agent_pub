"""Pourbaix-atlas external-DB interface for LC2_2.

``atlas_data``   — runtime data contract (AtlasSpecies, symbol→name).
``atlas_loader`` — reads the pre-cleaned atlas CSV every pipeline run.
``pourbaix_merge`` — ``merge_card_hardcoded``: parse + merge atlas
species into a free-energy card (LLM-free, no deduplication).
"""
