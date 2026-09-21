"""Build a ligand-fingerprint database from srd46_cards.db.

Iterates every row in ``ligand_card``, computes MACCS-166 and Morgan
(radius=2, 2048-bit) fingerprints via RDKit, and writes the results
into ``srd46_ligand_fingerprints.db`` (single table ``ligand_fingerprint``).

Usage
-----
    python build_ligand_fingerprints.py          # default paths
    python build_ligand_fingerprints.py --cards path/to/srd46_cards.db --out fp.db
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem, MACCSkeys
from rdkit.DataStructs import ExplicitBitVect

# Suppress RDKit warnings for invalid SMILES (we handle them ourselves)
RDLogger.DisableLog("rdApp.*")

log = logging.getLogger("fp-builder")

_THIS_DIR = Path(__file__).absolute().parent
_DEFAULT_CARDS_DB = _THIS_DIR / "srd46_cards.db"
_DEFAULT_OUT_DB = _THIS_DIR / "srd46_ligand_fingerprints.db"

MORGAN_RADIUS = 2
MORGAN_NBITS = 2048


# ── helpers ──────────────────────────────────────────────────────────

def _mol_from_row(smiles: str | None, inchi: str | None) -> Chem.Mol | None:
    """Try SMILES first, fall back to InChI."""
    if smiles:
        mol = Chem.MolFromSmiles(smiles)
        if mol is not None:
            return mol
    if inchi:
        mol = Chem.MolFromInchi(inchi)
        if mol is not None:
            return mol
    return None


def _bitvect_to_hex(bv: ExplicitBitVect) -> str:
    """Compact hex encoding of an RDKit bit vector."""
    return bv.ToBitString()  # '0'/'1' string — easy to reconstruct
    # For truly compact storage, switch to:
    #   return bv.ToBase64()


def _compute_fingerprints(mol: Chem.Mol) -> tuple[str, str]:
    """Return (maccs_hex, morgan_hex) for a molecule."""
    maccs = MACCSkeys.GenMACCSKeys(mol)
    morgan = AllChem.GetMorganFingerprintAsBitVect(mol, MORGAN_RADIUS, nBits=MORGAN_NBITS)
    return _bitvect_to_hex(maccs), _bitvect_to_hex(morgan)


# ── main ─────────────────────────────────────────────────────────────

def build(cards_db: Path, out_db: Path) -> None:
    log.info("Reading ligands from %s", cards_db)
    src = sqlite3.connect(str(cards_db))
    src.row_factory = sqlite3.Row
    rows = src.execute(
        "SELECT ligand_id, ligand_name_SRD, definition_HxL, "
        "       ligand_SMILES, ligand_InChi "
        "FROM ligand_card ORDER BY ligand_id"
    ).fetchall()
    src.close()
    log.info("Loaded %d ligand cards", len(rows))

    # Create output database
    if out_db.exists():
        out_db.unlink()
    dst = sqlite3.connect(str(out_db))
    dst.execute("""
        CREATE TABLE ligand_fingerprint (
            ligand_id        INTEGER PRIMARY KEY,
            ligand_name      TEXT    NOT NULL,
            HxL_canonical    TEXT,
            ligand_smiles    TEXT,
            ligand_inchi     TEXT,
            maccs_fingerprint TEXT,
            morgan_fingerprint TEXT,
            fp_status        TEXT NOT NULL
                             CHECK(fp_status IN ('ok','no_structure','parse_error'))
        )
    """)
    dst.execute("CREATE INDEX idx_fp_status ON ligand_fingerprint(fp_status)")

    ok = skip = err = 0
    batch: list[tuple] = []

    for row in rows:
        lid = row["ligand_id"]
        name = row["ligand_name_SRD"]
        hxl = row["definition_HxL"]
        smiles = row["ligand_SMILES"]
        inchi = row["ligand_InChi"]

        mol = _mol_from_row(smiles, inchi)

        if mol is None and not smiles and not inchi:
            batch.append((lid, name, hxl, smiles, inchi, None, None, "no_structure"))
            skip += 1
            continue

        if mol is None:
            log.debug("Parse error for ligand_id=%d  smiles=%r  inchi=%r", lid, smiles, inchi)
            batch.append((lid, name, hxl, smiles, inchi, None, None, "parse_error"))
            err += 1
            continue

        maccs_bits, morgan_bits = _compute_fingerprints(mol)
        batch.append((lid, name, hxl, smiles, inchi, maccs_bits, morgan_bits, "ok"))
        ok += 1

    dst.executemany(
        "INSERT INTO ligand_fingerprint "
        "(ligand_id, ligand_name, HxL_canonical, ligand_smiles, ligand_inchi, "
        " maccs_fingerprint, morgan_fingerprint, fp_status) "
        "VALUES (?,?,?,?,?,?,?,?)",
        batch,
    )
    dst.commit()
    dst.close()

    log.info("Done → %s", out_db)
    log.info("  ok=%d  no_structure=%d  parse_error=%d  total=%d", ok, skip, err, len(rows))


def main() -> None:
    ap = argparse.ArgumentParser(description="Build ligand fingerprint DB from SRD-46 cards")
    ap.add_argument("--cards", type=Path, default=_DEFAULT_CARDS_DB, help="Path to srd46_cards.db")
    ap.add_argument("--out", type=Path, default=_DEFAULT_OUT_DB, help="Output DB path")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-5s | %(message)s",
    )
    build(args.cards, args.out)


if __name__ == "__main__":
    main()
