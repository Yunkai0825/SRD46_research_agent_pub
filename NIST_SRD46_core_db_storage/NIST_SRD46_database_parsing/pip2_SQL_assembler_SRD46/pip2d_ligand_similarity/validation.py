"""Validate the descriptor artifact against its source cards and chemical settings."""
from __future__ import annotations

import json
import math
from pathlib import Path

from rdkit.DataStructs import TanimotoSimilarity, TverskySimilarity

from .build_ligand_fingerprints import connect_readonly, load_source_rows, source_digest
from .build_ligand_similarities import TVERSKY_ALPHA, TVERSKY_BETA, _load_fingerprints


def verify_database(cards_db: Path, fingerprints_db: Path) -> dict:
    """Raise ValueError on stale source, incomplete pairs, or invalid metric semantics."""
    rows = load_source_rows(cards_db)
    source_ids = [row['ligand_id'] for row in rows]
    if not source_ids:
        raise ValueError('source ligand_card is empty')
    db = connect_readonly(fingerprints_db)
    try:
        metadata = {key: json.loads(value) for key, value in db.execute(
            'SELECT key,value FROM fingerprint_metadata')}
        expected = {
            'schema_version': 1, 'source_ligand_count': len(rows),
            'source_ligand_sha256': source_digest(rows),
            'morgan_radius': 2, 'morgan_nbits': 2048, 'morgan_include_chirality': False,
            'morgan_use_bond_types': True, 'morgan_count_simulation': False,
            'morgan_include_ring_membership': True, 'morgan_include_redundant_environments': False,
            'reject_inchi_connectivity_loss': True,
            'maccs_nbits': 167, 'serialization': 'bitstring',
            'tversky_alpha': TVERSKY_ALPHA, 'tversky_beta': TVERSKY_BETA,
            'similarities_complete': True,
            'similarity_pair_count': len(rows) * (len(rows) + 1) // 2,
        }
        for key, value in expected.items():
            if key not in metadata or metadata[key] != value:
                raise ValueError(f'descriptor metadata mismatch: {key} (rebuild descriptors from current cards)')
        if not metadata.get('rdkit_version') or not metadata.get('structure_policy'):
            raise ValueError('descriptor generation provenance is missing')
        ids, maccs, morgan = _load_fingerprints(db)
        if ids != source_ids:
            raise ValueError('descriptor ligand IDs differ from ligand_card')
        informative_maccs = {lid for lid in maccs if maccs[lid].GetNumOnBits()}
        informative_morgan = {lid for lid in morgan if morgan[lid].GetNumOnBits()}
        for lid, status, m_count, g_count in db.execute(
            'SELECT ligand_id,fp_status,maccs_on_bits,morgan_on_bits FROM ligand_fingerprint'
        ):
            if status == 'ok':
                if (m_count, g_count) != (maccs[lid].GetNumOnBits(), morgan[lid].GetNumOnBits()):
                    raise ValueError(f'ligand {lid}: fingerprint feature counts differ')
            elif m_count is not None or g_count is not None:
                raise ValueError(f'ligand {lid}: failed structure carries feature counts')
        summary = db.execute('''SELECT COUNT(*), COUNT(tanimoto_maccs), COUNT(tanimoto_morgan),
            COUNT(tversky_morgan_1to2), COUNT(tversky_morgan_2to1),
            MIN(tanimoto_maccs), MAX(tanimoto_maccs), MIN(tanimoto_morgan), MAX(tanimoto_morgan),
            MIN(tversky_morgan_1to2), MAX(tversky_morgan_1to2),
            MIN(tversky_morgan_2to1), MAX(tversky_morgan_2to1),
            SUM(ligand_id_1 > ligand_id_2),
            SUM((tanimoto_morgan IS NULL) != (tversky_morgan_1to2 IS NULL)
                OR (tanimoto_morgan IS NULL) != (tversky_morgan_2to1 IS NULL)),
            SUM((tanimoto_maccs IS NOT NULL) != (
                ligand_id_1 IN (SELECT ligand_id FROM ligand_fingerprint WHERE maccs_on_bits>0)
                AND ligand_id_2 IN (SELECT ligand_id FROM ligand_fingerprint WHERE maccs_on_bits>0))),
            SUM((tanimoto_morgan IS NOT NULL) != (
                ligand_id_1 IN (SELECT ligand_id FROM ligand_fingerprint WHERE morgan_on_bits>0)
                AND ligand_id_2 IN (SELECT ligand_id FROM ligand_fingerprint WHERE morgan_on_bits>0)))
            FROM ligand_similarity''').fetchone()
        m_pairs = len(informative_maccs) * (len(informative_maccs) + 1) // 2
        g_pairs = len(informative_morgan) * (len(informative_morgan) + 1) // 2
        if tuple(summary[:5]) != (expected['similarity_pair_count'], m_pairs, g_pairs, g_pairs, g_pairs):
            raise ValueError('similarity pair counts or NULL coverage differ from fingerprints')
        if any(value is not None and not 0 <= value <= 1 for value in summary[5:13]):
            raise ValueError('similarities must be finite numbers in [0,1]')
        if any(summary[13:17]):
            raise ValueError('similarity triangle or per-pair NULL masks are invalid')
        for column in ('ligand_id_1', 'ligand_id_2'):
            endpoints = [row[0] for row in db.execute(f'SELECT DISTINCT {column} FROM ligand_similarity ORDER BY {column}')]
            if endpoints != source_ids:
                raise ValueError('similarity endpoints differ from source ligand IDs')
        diagonals = db.execute('''SELECT ligand_id_1,tanimoto_maccs,tanimoto_morgan,
            tversky_morgan_1to2,tversky_morgan_2to1 FROM ligand_similarity
            WHERE ligand_id_1=ligand_id_2 ORDER BY ligand_id_1''').fetchall()
        if len(diagonals) != len(ids):
            raise ValueError('missing self-similarity rows')
        for lid, *values in diagonals:
            m_value = 1.0 if lid in informative_maccs else None
            g_value = 1.0 if lid in informative_morgan else None
            expected_values = [m_value, g_value, g_value, g_value]
            if any((value is None) != (expected_value is None) or
                   (value is not None and not math.isclose(value, expected_value,
                                                          rel_tol=1e-12, abs_tol=1e-12))
                   for value, expected_value in zip(values, expected_values)):
                raise ValueError(f'ligand {lid}: invalid self-similarity')
        # Independently recompute representative off-diagonal scores and both asymmetric directions.
        anchors = sorted(set(ids[::max(1, len(ids)//8)] + [ids[-1]]))
        checked = 0
        for index, first in enumerate(anchors):
            for second in anchors[index + 1:]:
                actual = db.execute('''SELECT tanimoto_maccs,tanimoto_morgan,tversky_morgan_1to2,
                    tversky_morgan_2to1 FROM ligand_similarity WHERE ligand_id_1=? AND ligand_id_2=?''',
                    (first, second)).fetchone()
                m_value = TanimotoSimilarity(maccs[first], maccs[second]) if first in informative_maccs and second in informative_maccs else None
                if first in informative_morgan and second in informative_morgan:
                    g1, g2 = morgan[first], morgan[second]
                    values = [m_value, TanimotoSimilarity(g1, g2),
                              TverskySimilarity(g1, g2, TVERSKY_ALPHA, TVERSKY_BETA),
                              TverskySimilarity(g2, g1, TVERSKY_ALPHA, TVERSKY_BETA)]
                else:
                    values = [m_value, None, None, None]
                if actual is None or any((a is None) != (b is None) or
                    (a is not None and not math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12))
                    for a, b in zip(actual, values)):
                    raise ValueError(f'similarity values differ from RDKit for pair {first},{second}')
                checked += 1
        integrity = db.execute('PRAGMA quick_check').fetchall()
        if [row[0] for row in integrity] != ['ok']:
            raise ValueError(f'descriptor database integrity check failed: {integrity}')
        return {
            'ligands': len(ids), 'valid_structures': len(morgan), 'pairs': summary[0],
            'maccs_pairs': m_pairs, 'morgan_pairs': g_pairs, 'sample_pairs_checked': checked,
            'source_ligand_sha256': metadata['source_ligand_sha256'], 'integrity': 'ok',
        }
    finally:
        db.close()
