"""Build reproducible ligand fingerprints from the published SRD46 cards.

Retain the curated molecular graph, including fragments, formal charges and
protonation/tautomer state. Morgan fingerprints describe constitution (radius 2,
2048 bits, no chirality); they do not establish molecular identity or affinity.
RDKit's 166 public MACCS keys are serialized as 167 bits (bit zero is unused).
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import logging
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from typing import Any, Mapping, Sequence
from urllib.parse import quote

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).absolute().parents[2]))

from rdkit import Chem, rdBase
from rdkit.Chem import MACCSkeys, rdFingerprintGenerator

from srd46_pipeline.manual_rules import ligand_is_placeholder, ligand_placeholder_fields
from srd46_pipeline.paths import OutputPaths

log = logging.getLogger("fp-builder")
MORGAN_RADIUS = 2
MORGAN_NBITS = 2048
MACCS_NBITS = 167
MORGAN_INCLUDE_CHIRALITY = False
INCHI_CONNECTIVITY_LOSS_POLICY = "reject_fallback_if_components_increase_from_parseable_raw_smiles"
SOURCE_FIELDS = (
    "ligand_id", "ligand_name_SRD", "definition_HxL", "ligand_SMILES",
    "ligand_InChi", "formula", "figure_definition",
)
STRUCTURE_POLICY = (
    "SMILES first, valid InChI fallback unless connected components increase "
    "from parseable raw SMILES; unsanitized graphs used only for this guard; "
    "LIG-04 whole-record placeholders and "
    "missing structures excluded; empty, dummy and query graphs excluded; "
    "preserve all fragments, formal charge, protonation and tautomer state; "
    "retain curated SMILES when identifiers disagree and record the difference; "
    "Morgan chirality disabled; zero-on-bit vectors have undefined similarity"
)


def connect_readonly(path: Path) -> sqlite3.Connection:
    """Open an existing database without creating it; supports Windows UNC paths."""
    path = Path(path).absolute()
    if not path.is_file():
        raise FileNotFoundError(f"Cards database does not exist: {path}")
    # Keep Windows backslashes: file://server is an unsupported URI authority
    # on SQLite builds that do not enable SQLITE_ALLOW_URI_AUTHORITY.
    uri = "file:" + quote(str(path), safe="/\\:") + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def load_source_rows(cards_db: Path) -> list[sqlite3.Row]:
    """Read fingerprint inputs in ligand-ID order; never modify the cards."""
    db = connect_readonly(cards_db)
    try:
        db.row_factory = sqlite3.Row
        return db.execute(
            "SELECT " + ", ".join(SOURCE_FIELDS) + " FROM ligand_card ORDER BY ligand_id"
        ).fetchall()
    finally:
        db.close()


def source_digest(rows: Sequence[Mapping[str, Any]]) -> str:
    """Hash selected source fields, including nulls and column names, deterministically."""
    digest = hashlib.sha256()
    digest.update(json.dumps(SOURCE_FIELDS, separators=(",", ":")).encode("utf-8"))
    digest.update(b"\n")
    for row in sorted(rows, key=lambda item: item["ligand_id"]):
        values = [row[field] for field in SOURCE_FIELDS]
        digest.update(json.dumps(values, ensure_ascii=False, separators=(",", ":"),
                                 allow_nan=False).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _identifier(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    if not text or set(text) == {"*"} or text.casefold() in {"none", "null", "nan", "n/a"}:
        return None
    return text


def _parse_structure(text: str | None, source: str) -> tuple[Chem.Mol | None, str | None]:
    if text is None:
        return None, None
    try:
        with rdBase.BlockLogs():
            if source == "smiles":
                params = Chem.SmilesParserParams()
                params.parseName = False
                mol = Chem.MolFromSmiles(text, params)
            else:
                mol = Chem.MolFromInchi(text)
        if mol is None:
            return None, f"{source}_parse_error"
        if mol.GetNumAtoms() == 0:
            return None, f"{source}_empty_molecule"
        if any(atom.GetAtomicNum() == 0 for atom in mol.GetAtoms()):
            return None, f"{source}_dummy_atoms"
        if any(atom.HasQuery() for atom in mol.GetAtoms()) or any(bond.HasQuery() for bond in mol.GetBonds()):
            return None, f"{source}_query_graph"
        return mol, None
    except (ValueError, RuntimeError, TypeError) as exc:
        log.debug("%s parsing failed: %s", source, exc)
        return None, f"{source}_parse_error"


def _inchi_loses_connectivity(smiles: str | None, inchi_mol: Chem.Mol) -> bool:
    """Detect connectivity lost by InChI fallback without fingerprinting an invalid graph.

    Standard InChI may disconnect metal coordination bonds. A parseable raw
    SMILES graph provides evidence of that loss even when valence sanitization
    fails. Preserve genuinely disconnected sources when component counts agree.
    """
    if smiles is None:
        return False
    params = Chem.SmilesParserParams()
    params.parseName = False
    params.sanitize = False
    params.removeHs = False
    try:
        with rdBase.BlockLogs():
            raw_mol = Chem.MolFromSmiles(smiles, params)
        return raw_mol is not None and len(Chem.GetMolFrags(raw_mol)) < len(Chem.GetMolFrags(inchi_mol))
    except (ValueError, RuntimeError, TypeError):
        return False


def _select_structure(row: Mapping[str, Any]) -> tuple[Chem.Mol | None, str | None, str, list[str]]:
    """Return molecule, selected identifier source, status and auditable notes."""
    fields = ligand_placeholder_fields(row["figure_definition"], row["formula"], row["ligand_SMILES"])
    if ligand_is_placeholder(fields):
        return None, None, "no_structure", ["record_placeholder_lig04"]
    smiles, inchi = _identifier(row["ligand_SMILES"]), _identifier(row["ligand_InChi"])
    if smiles is None and inchi is None:
        return None, None, "no_structure", ["missing_or_placeholder_identifiers"]
    smiles_mol, smiles_error = _parse_structure(smiles, "smiles")
    inchi_mol, inchi_error = _parse_structure(inchi, "inchi")
    notes = [error for error in (smiles_error, inchi_error) if error]
    if smiles_mol is not None:
        mol, source = smiles_mol, "smiles"
    elif inchi_mol is not None:
        if _inchi_loses_connectivity(smiles, inchi_mol):
            notes.append("inchi_connectivity_loss")
            return None, None, "parse_error", notes
        mol, source = inchi_mol, "inchi"
        notes.append("inchi_fallback")
    else:
        return None, None, "parse_error", notes
    if smiles_mol is not None and inchi_mol is not None:
        if Chem.MolToSmiles(smiles_mol, isomericSmiles=True) != Chem.MolToSmiles(inchi_mol, isomericSmiles=True):
            # InChI may reconstruct a different tautomer. This is informative,
            # not evidence to discard the authoritative SMILES.
            notes.append("identifier_graph_difference")
            with rdBase.BlockLogs():
                try:
                    smiles_key = Chem.MolToInchiKey(smiles_mol)
                    inchi_key = Chem.MolToInchiKey(inchi_mol)
                    if smiles_key and inchi_key and smiles_key != inchi_key:
                        notes.append("identifier_inchikey_mismatch")
                    elif not smiles_key or not inchi_key:
                        notes.append("identifier_inchikey_unavailable")
                except (ValueError, RuntimeError):
                    notes.append("identifier_inchikey_unavailable")
    if len(Chem.GetMolFrags(mol)) > 1:
        notes.append("disconnected_structure_preserved")
    if any(atom.GetFormalCharge() for atom in mol.GetAtoms()):
        notes.append("formal_charge_preserved")
    if any(atom.GetNumRadicalElectrons() for atom in mol.GetAtoms()):
        notes.append("radical_structure_preserved")
    return mol, source, "ok", notes


def _check_paths(cards_db: Path, out_db: Path) -> None:
    if cards_db.resolve() == out_db.resolve() or (
        cards_db.exists() and out_db.exists() and os.path.samefile(cards_db, out_db)
    ):
        raise ValueError("Fingerprint output must differ from the source cards database")
    if out_db.exists() and not out_db.is_file():
        raise ValueError(f"Fingerprint output is not a regular file: {out_db}")
    # Do not associate a pre-existing live journal with the new database file.
    for suffix in ("-wal", "-shm", "-journal"):
        if out_db.with_name(out_db.name + suffix).exists():
            raise ValueError(f"Fingerprint output has an active SQLite side file: {out_db.name + suffix}")


def build(cards_db: Path, out_db: Path) -> dict[str, int]:
    """Build in a unique sibling file and publish only after a complete commit."""
    cards_db, out_db = Path(cards_db).absolute(), Path(out_db).absolute()
    _check_paths(cards_db, out_db)
    rows = load_source_rows(cards_db)
    source_hash = source_digest(rows)
    generator = rdFingerprintGenerator.GetMorganGenerator(
        radius=MORGAN_RADIUS, fpSize=MORGAN_NBITS,
        includeChirality=MORGAN_INCLUDE_CHIRALITY, useBondTypes=True,
        countSimulation=False, includeRingMembership=True,
        onlyNonzeroInvariants=False, includeRedundantEnvironments=False,
    )
    counts = Counter({key: 0 for key in (
        "total", "ok", "no_structure", "parse_error", "inchi_fallback",
        "identifier_graph_difference", "identifier_inchikey_mismatch", "audited",
        "zero_maccs", "zero_morgan", "record_placeholder_lig04", "inchi_connectivity_loss",
    )})
    records = []
    for row in rows:
        mol, source, status, notes = _select_structure(row)
        fingerprint_smiles = maccs_bits = morgan_bits = None
        maccs_on = morgan_on = None
        if mol is not None:
            try:
                with rdBase.BlockLogs():
                    maccs = MACCSkeys.GenMACCSKeys(mol)
                    morgan = generator.GetFingerprint(mol)
                if maccs.GetNumBits() != MACCS_NBITS or morgan.GetNumBits() != MORGAN_NBITS:
                    raise RuntimeError("RDKit returned an unexpected fingerprint length")
                fingerprint_smiles = Chem.MolToSmiles(mol, isomericSmiles=True)
                maccs_bits, morgan_bits = maccs.ToBitString(), morgan.ToBitString()
                maccs_on, morgan_on = maccs.GetNumOnBits(), morgan.GetNumOnBits()
                if not maccs_on:
                    notes.append("zero_maccs")
                if not morgan_on:
                    notes.append("zero_morgan")
            except (ValueError, RuntimeError) as exc:
                log.debug("Fingerprint failed for ligand %s: %s", row["ligand_id"], exc)
                status = "parse_error"
                notes.append("fingerprint_error")
                fingerprint_smiles = maccs_bits = morgan_bits = None
                maccs_on = morgan_on = None
        counts["total"] += 1
        counts[status] += 1
        if notes:
            counts["audited"] += 1
        for note in notes:
            counts[note] += 1
        records.append((
            row["ligand_id"], row["ligand_name_SRD"] or "", row["definition_HxL"],
            row["ligand_SMILES"], row["ligand_InChi"], maccs_bits, morgan_bits, status,
            source, fingerprint_smiles, json.dumps(notes, separators=(",", ":")),
            maccs_on, morgan_on,
        ))
    metadata = {
        "schema_version": 1, "rdkit_version": rdBase.rdkitVersion,
        "morgan_radius": MORGAN_RADIUS, "morgan_nbits": MORGAN_NBITS,
        "morgan_include_chirality": MORGAN_INCLUDE_CHIRALITY,
        "morgan_use_bond_types": True, "morgan_count_simulation": False,
        "morgan_include_ring_membership": True,
        "morgan_include_redundant_environments": False,
        "morgan_generator": generator.GetInfoString(), "maccs_nbits": MACCS_NBITS,
        "serialization": "bitstring", "structure_policy": STRUCTURE_POLICY,
        "inchi_connectivity_loss_policy": INCHI_CONNECTIVITY_LOSS_POLICY,
        "reject_inchi_connectivity_loss": True,
        "source_ligand_sha256": source_hash, "source_ligand_count": len(rows),
        "source_fields": SOURCE_FIELDS, "build_counts": dict(counts),
    }
    out_db.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=out_db.name + ".", suffix=".tmp", dir=out_db.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    db = None
    try:
        db = sqlite3.connect(str(temporary))
        db.execute("PRAGMA journal_mode=DELETE")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("""CREATE TABLE ligand_fingerprint (
            ligand_id INTEGER PRIMARY KEY,
            ligand_name TEXT NOT NULL,
            HxL_canonical TEXT,
            ligand_smiles TEXT,
            ligand_inchi TEXT,
            maccs_fingerprint TEXT,
            morgan_fingerprint TEXT,
            fp_status TEXT NOT NULL CHECK(fp_status IN ('ok','no_structure','parse_error')),
            fingerprint_source TEXT CHECK(fingerprint_source IN ('smiles','inchi')),
            fingerprint_smiles TEXT,
            structure_note TEXT NOT NULL,
            maccs_on_bits INTEGER,
            morgan_on_bits INTEGER
        )""")
        db.execute("CREATE INDEX idx_fp_status ON ligand_fingerprint(fp_status)")
        db.execute("CREATE TABLE fingerprint_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        db.executemany("INSERT INTO ligand_fingerprint VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", records)
        db.executemany("INSERT INTO fingerprint_metadata VALUES (?,?)", [
            (key, json.dumps(value, ensure_ascii=False, separators=(",", ":")))
            for key, value in metadata.items()
        ])
        db.commit()
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise RuntimeError("Fingerprint SQLite integrity check failed")
        db.close()
        db = None
        _check_paths(cards_db, out_db)
        os.replace(temporary, out_db)
    finally:
        if db is not None:
            db.close()
        for candidate in (temporary, temporary.with_name(temporary.name + "-journal")):
            if candidate.exists():
                candidate.unlink()
    log.info("Fingerprint database: %s; %s", out_db, dict(counts))
    return dict(counts)


def main() -> None:
    paths = OutputPaths()
    parser = argparse.ArgumentParser(description="Build auditable SRD46 ligand fingerprints")
    parser.add_argument("--cards", type=Path, default=paths.cards_db, help="Source cards database")
    parser.add_argument("--out", type=Path, default=paths.fingerprints_db, help="Output fingerprint database")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)-5s | %(message)s")
    build(args.cards, args.out)


if __name__ == "__main__":
    main()

