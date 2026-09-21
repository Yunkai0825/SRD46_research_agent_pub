"""Pairwise similarities of the recorded ligand graphs, with atomic table replacement.

Tanimoto measures overlap of set fingerprint bits. Tversky uses alpha=0.9,
 beta=0.1: the forward column penalizes query-only bits more than target-only
bits. Neither metric proves substructure containment or predicts binding affinity.
Absent structures and metrics with zero set bits receive NULL, including diagonals.
The upper triangle (ligand_id_1 <= ligand_id_2) retains both Tversky directions.
"""
from __future__ import annotations

import argparse
from collections.abc import Callable
import json
import logging
import sqlite3
import sys
import time
from pathlib import Path
from urllib.parse import quote

from rdkit.DataStructs import BulkTanimotoSimilarity, BulkTverskySimilarity, CreateFromBitString

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).absolute().parents[2]))

from srd46_pipeline.paths import OutputPaths

log = logging.getLogger(__name__)
INSERT_BATCH = 50_000
TVERSKY_ALPHA = 0.9
TVERSKY_BETA = 0.1


def _connect_existing(path: Path) -> sqlite3.Connection:
    path = Path(path).absolute()
    if not path.is_file():
        raise FileNotFoundError(path)
    # Four slashes after file: represent a UNC path without a URI hostname.
    value = path.as_posix()
    if value.startswith('//'):
        value = '//' + value
    return sqlite3.connect('file:' + quote(value, safe='/:') + '?mode=rw', uri=True)


def _load_fingerprints(db: sqlite3.Connection):
    """Validate bit serialization; return IDs and vectors for valid structures."""
    ids, maccs, morgan = [], {}, {}
    for lid, m_bits, g_bits, status in db.execute(
        'SELECT ligand_id, maccs_fingerprint, morgan_fingerprint, fp_status '
        'FROM ligand_fingerprint ORDER BY ligand_id'
    ):
        ids.append(lid)
        if status not in ('ok', 'no_structure', 'parse_error'):
            raise ValueError(f'ligand {lid}: invalid fp_status {status!r}')
        if status != 'ok':
            if m_bits is not None or g_bits is not None:
                raise ValueError(f'ligand {lid}: failed structure carries fingerprints')
            continue
        for name, value, size in (('MACCS', m_bits, 167), ('Morgan', g_bits, 2048)):
            if not isinstance(value, str) or len(value) != size or set(value) - {'0', '1'}:
                raise ValueError(f'ligand {lid}: invalid {name} bit string (expected {size} bits)')
        if m_bits[0] != '0':
            raise ValueError(f'ligand {lid}: unused MACCS bit 0 must be unset')
        maccs[lid] = CreateFromBitString(m_bits)
        morgan[lid] = CreateFromBitString(g_bits)
    return ids, maccs, morgan


def build(db_path: Path, batch_size: int = INSERT_BATCH,
          progress: Callable[[str], None] | None = None) -> dict:
    """Replace similarity table in one transaction; failure preserves the prior table."""
    if not isinstance(batch_size, int) or isinstance(batch_size, bool) or batch_size <= 0:
        raise ValueError('batch_size must be a positive integer')
    db = _connect_existing(db_path)
    started = time.perf_counter()
    try:
        # Lock a consistent fingerprint snapshot for the entire build. No intermediate commits.
        db.execute('BEGIN IMMEDIATE')
        ids, maccs, morgan = _load_fingerprints(db)
        n = len(ids)
        if not n:
            raise ValueError('ligand_fingerprint is empty')
        ok_ids = sorted(morgan)
        ok_pos = {lid: index for index, lid in enumerate(ok_ids)}
        maccs_vectors = [maccs[lid] for lid in ok_ids]
        morgan_vectors = [morgan[lid] for lid in ok_ids]
        maccs_valid = {lid for lid in ok_ids if maccs[lid].GetNumOnBits()}
        morgan_valid = {lid for lid in ok_ids if morgan[lid].GetNumOnBits()}
        db.execute('DROP TABLE IF EXISTS ligand_similarity')
        db.execute('''CREATE TABLE ligand_similarity (
            ligand_id_1 INTEGER NOT NULL REFERENCES ligand_fingerprint(ligand_id),
            ligand_id_2 INTEGER NOT NULL REFERENCES ligand_fingerprint(ligand_id),
            tanimoto_maccs REAL CHECK(tanimoto_maccs BETWEEN 0 AND 1),
            tanimoto_morgan REAL CHECK(tanimoto_morgan BETWEEN 0 AND 1),
            tversky_morgan_1to2 REAL CHECK(tversky_morgan_1to2 BETWEEN 0 AND 1),
            tversky_morgan_2to1 REAL CHECK(tversky_morgan_2to1 BETWEEN 0 AND 1),
            PRIMARY KEY(ligand_id_1, ligand_id_2),
            CHECK(ligand_id_1 <= ligand_id_2)
        ) WITHOUT ROWID''')
        total = n * (n + 1) // 2
        batch, written = [], 0
        last_log = started
        for index, lid in enumerate(ids):
            pos = ok_pos.get(lid)
            if pos is not None:
                # Only compute the useful half of the matrix, with no redundant reverse rows.
                m_sims = BulkTanimotoSimilarity(maccs_vectors[pos], maccs_vectors[pos:])
                g_sims = BulkTanimotoSimilarity(morgan_vectors[pos], morgan_vectors[pos:])
                forward = BulkTverskySimilarity(morgan_vectors[pos], morgan_vectors[pos:],
                                                TVERSKY_ALPHA, TVERSKY_BETA)
                reverse = BulkTverskySimilarity(morgan_vectors[pos], morgan_vectors[pos:],
                                                TVERSKY_BETA, TVERSKY_ALPHA)
            for other in ids[index:]:
                other_pos = ok_pos.get(other)
                if pos is None or other_pos is None:
                    record = (lid, other, None, None, None, None)
                else:
                    j = other_pos - pos
                    m_value = m_sims[j] if lid in maccs_valid and other in maccs_valid else None
                    if lid in morgan_valid and other in morgan_valid:
                        record = (lid, other, m_value, g_sims[j], forward[j], reverse[j])
                    else:
                        record = (lid, other, m_value, None, None, None)
                batch.append(record)
                if len(batch) >= batch_size:
                    db.executemany('INSERT INTO ligand_similarity VALUES (?,?,?,?,?,?)', batch)
                    written += len(batch)
                    batch.clear()
                    now = time.perf_counter()
                    if now - last_log >= 15:
                        message = f'Similarities: {written:,} / {total:,} pairs ({100 * written / total:.1f}%)'
                        (progress or log.info)(message)
                        last_log = now
        if batch:
            db.executemany('INSERT INTO ligand_similarity VALUES (?,?,?,?,?,?)', batch)
            written += len(batch)
        db.execute('CREATE INDEX idx_sim_id2 ON ligand_similarity(ligand_id_2)')
        stats = {
            'ligands': n, 'pairs': written, 'valid_structures': len(ok_ids),
            'maccs_pairs': len(maccs_valid) * (len(maccs_valid) + 1) // 2,
            'morgan_pairs': len(morgan_valid) * (len(morgan_valid) + 1) // 2,
        }
        if written != total:
            raise ValueError(f'incomplete similarity matrix: {written} != {total}')
        metadata = {
            'tversky_alpha': TVERSKY_ALPHA, 'tversky_beta': TVERSKY_BETA,
            'similarity_pair_count': total, 'similarities_complete': True,
            'zero_feature_similarity': 'NULL if either vector has no set bits',
            'similarity_semantics': 'recorded-graph fingerprint overlap; not identity, substructure proof, or affinity',
        }
        db.executemany('INSERT OR REPLACE INTO fingerprint_metadata(key,value) VALUES (?,?)',
                       [(key, json.dumps(value)) for key, value in metadata.items()])
        db.commit()
        stats['elapsed_s'] = round(time.perf_counter() - started, 3)
        log.info('Built %s similarity pairs in %.1fs', written, stats['elapsed_s'])
        return stats
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=OutputPaths().fingerprints_db)
    parser.add_argument('--batch', type=int, default=INSERT_BATCH)
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format='%(message)s')
    build(args.db, args.batch)


if __name__ == '__main__':
    main()
