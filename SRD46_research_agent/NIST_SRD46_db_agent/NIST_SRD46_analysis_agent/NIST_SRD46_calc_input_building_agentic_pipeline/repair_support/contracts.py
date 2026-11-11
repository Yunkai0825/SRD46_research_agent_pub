"""Structured source-repair diagnostics shared by LC1, the compiler and LC2."""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path

# Both native package and pipeline-root imports refer to one exception class.
sys.modules.setdefault("repair_support.contracts", sys.modules[__name__])
sys.modules.setdefault("NIST_SRD46_calc_input_building_agentic_pipeline.repair_support.contracts", sys.modules[__name__])
from typing import Any, Mapping

DEFAULT_MAX_REPAIR_ATTEMPTS = 2


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


class SourceRepairRequired(ValueError):
    """A source-selection defect; never a licence to edit scientific values."""
    def __init__(self, diagnostic: Mapping[str, Any], message: str | None = None):
        self.diagnostic = json.loads(json.dumps(dict(diagnostic), allow_nan=False))
        self.diagnostic.setdefault("schema_version", 1)
        self.diagnostic.setdefault("repair_scope", "source_selection")
        self.diagnostic.setdefault("error_code", "source_repair_required")
        self.diagnostic.setdefault("message", message or "Source selection requires repair")
        super().__init__(message or self.diagnostic["message"])

    def as_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(self.diagnostic))


class BroaderReviewRequired(SourceRepairRequired):
    """The local delta cannot preserve the accepted basis/scope safely."""
    def __init__(self, message: str, **details: Any):
        super().__init__({"error_code": "needs_broader_review", "repair_scope": "broader_review",
                          "message": message, **details}, message)


def bind_compiler_diagnostic(diagnostic: Mapping[str, Any], output_dir: Any) -> dict[str, Any]:
    """Bind a dict-based compiler failure to its saved, exact intermediate."""
    import os
    import re
    result = json.loads(json.dumps(dict(diagnostic)))
    root = Path(output_dir).absolute()
    if os.name == "nt" and not str(root).startswith(chr(92) * 2 + "?"):
        root = Path(chr(92) * 2 + "?" + chr(92) + str(root))
    expected = result.get("input_sha256")
    if expected:
        for candidate in root.rglob("*.json"):
            try:
                value = json.loads(candidate.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                continue
            if canonical_sha256(value) != expected:
                continue
            result["source_path"] = str(candidate)
            match = re.search(r"metal_(\d+)_ligand_(\d+)", candidate.name)
            if match:
                result["metal_id"], result["ligand_id"] = map(int, match.groups())
                result["pair_key"] = f"metal_{match[1]}_ligand_{match[2]}"
                result["pair_keys"] = [result["pair_key"]]
                result["issue_key"] = result["pair_key"]
            break
    return result


def source_identity(data: Mapping[str, Any]) -> dict[str, Any]:
    metals, ligands = [], []
    for row in (data.get("components") or {}).values():
        reference = row.get("reference") or {}
        key = str(reference.get("source_database_ID") or "")
        if key.startswith("metal_") and key != "metal_68":
            metals.append(int(key.split("_")[-1]))
        if key.startswith("ligand_") and key != "ligand_10076":
            ligands.append(int(key.split("_")[-1]))
    pairs = sorted({f"metal_{m}_ligand_{l}" for m in metals for l in ligands})
    result = {"pair_keys": pairs}
    if len(pairs) == 1:
        result.update(pair_key=pairs[0], issue_key=pairs[0], metal_id=metals[0], ligand_id=ligands[0])
    return result
