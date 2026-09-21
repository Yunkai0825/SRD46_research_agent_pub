from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


_THIS = Path(__file__).absolute()
_PIPELINE_ROOT = _THIS.parents[3]
_HELPERS_ROOT = (
    _THIS.parents[1]
    / "ref_eq_SRD46_json_cards_builder"
    / "json_cards_builder_helpers"
)
for _path in (_PIPELINE_ROOT,):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

# On Windows this repository path can exceed the legacy path limit.  Load the
# one target module through an extended-length filename in that environment.
_PARSER_PATH = _HELPERS_ROOT / "speciation_json_input_parser.py"
_PARSER_TEXT = str(_PARSER_PATH)
if os.name == "nt":
    if _PARSER_TEXT.startswith("\\\\"):
        _PARSER_TEXT = "\\\\?\\UNC\\" + _PARSER_TEXT.lstrip("\\")
    else:
        _PARSER_TEXT = "\\\\?\\" + _PARSER_TEXT
_SPEC = importlib.util.spec_from_file_location("srd_formula_parser", _PARSER_TEXT)
assert _SPEC is not None and _SPEC.loader is not None
_parser = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _parser
_SPEC.loader.exec_module(_parser)

_validated_formula_hlx = _parser._validated_formula_hlx


def test_literal_oxide_formula_cannot_replace_complete_flat_stoichiometry():
    grouped = _validated_formula_hlx(
        "<M1>O(s)",
        "H",
        "OH",
        {"M1": 1},
        {},
        {"M1": 1, "H": -2},
    )

    assert grouped is None


def test_tokenized_hydroxide_ligand_formula_round_trips_losslessly():
    grouped = _validated_formula_hlx(
        "<M1>(<OH>)<L1>",
        "H",
        "OH",
        {"M1": 1},
        {"L1": 1},
        {"M1": 1, "L1": 1, "H": -1},
    )

    assert grouped == [("M1", 1), ("OH", 1), ("L1", 1)]
