"""
solver_parse_check.py — Validate a free-energy card with the SOLVER's own parser.
================================================================================

LC2_4's job is to confirm that the post-deduplication free-energy card is
*actually parseable* by the very same importer the numerical solver uses
at run time.  We deliberately do **not** re-implement a card parser here.
Instead we dynamically import the solver's public entry point —

    ``numcalc_input_cards_reader.resolve_card_source``

which is exactly the call ``SRD46_numcalculator_api.run_calculation`` makes
to turn a card source into a ``FreeEnergyReport`` before sweeping.  A clean
return means the card is solver-legit; any exception is captured verbatim
(message + traceback) so the LC2_4 repair agent can act on the real solver
error rather than a paraphrase.

The import is performed lazily (``importlib``) at call time, mirroring the
``sys.path`` bootstrap used elsewhere in the calc-input pipeline (e.g.
``lc2_2_orchestrator``), so the solver package and its bare sub-imports
resolve identically to a real solver invocation.
"""
from __future__ import annotations

import importlib
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

# ── path bookkeeping ────────────────────────────────────────────────
# .../LC2_4_card_validator/_card_validation/solver_parse_check.py
_THIS = Path(__file__).absolute()
_ANALYSIS_ROOT = _THIS.parents[4]            # NIST_SRD46_analysis_agent/
_NUMCALC_ROOT = _ANALYSIS_ROOT / "NIST_SRD46_core_numcalc_pipeline"
_PIPELINE_ROOT = _THIS.parents[3]            # NIST_SRD46_calc_input_building_agentic_pipeline/
# Directory holding ``free_energy_md_card_reader.py`` — the solver's
# ``resolve_card_source`` performs a *bare* ``from free_energy_md_card_reader
# import …`` for ``.md`` sources, so this directory must be importable.
_CARD_HELPERS = _PIPELINE_ROOT / "card_management_helpers"


@dataclass
class SolverParseResult:
    """Outcome of a single solver-parser invocation against a card."""
    ok: bool
    report: Optional[Any] = None
    error: Optional[str] = None
    traceback: Optional[str] = None
    parser_qualname: str = ""

    def short_error(self, *, max_chars: int = 2000) -> str:
        """One-line-ish error suitable for an LLM user message."""
        msg = (self.error or "").strip()
        if len(msg) > max_chars:
            msg = msg[:max_chars] + " …(truncated)"
        return msg


def _load_resolve_card_source() -> Callable[..., Any]:
    """Dynamically import the solver's own ``resolve_card_source``.

    This is the identical entry point ``SRD46_numcalculator_api`` uses;
    we never fork or re-implement it.
    """
    # ``free_energy_md_card_reader`` imports
    # ``card_management_helpers.longpath_io`` by package name.  The helper
    # directory resolves its bare-module import, while its parent pipeline
    # root is required for that package-qualified import in a clean process.
    for _root in (_NUMCALC_ROOT, _PIPELINE_ROOT, _CARD_HELPERS):
        if _root.exists() and str(_root) not in sys.path:
            sys.path.insert(0, str(_root))
    mod = importlib.import_module("numcalc_input_cards_reader")
    return getattr(mod, "resolve_card_source")


def validate_card_with_solver(
    card_path: str | Path,
    *,
    temperature_K: Optional[float] = None,
) -> SolverParseResult:
    """Run the solver's ``resolve_card_source`` on ``card_path``.

    Returns a :class:`SolverParseResult`.  ``ok=True`` means the card
    parses cleanly (and ``report`` holds the resulting
    ``FreeEnergyReport``); ``ok=False`` captures the verbatim exception
    message and traceback.
    """
    card_path = Path(card_path)
    if not card_path.exists():
        return SolverParseResult(
            ok=False, error=f"card not found: {card_path}",
        )

    try:
        resolve = _load_resolve_card_source()
    except Exception as exc:                                  # pragma: no cover
        return SolverParseResult(
            ok=False,
            error=f"could not import solver parser (resolve_card_source): {exc!r}",
            traceback=traceback.format_exc(),
        )

    qual = f"{getattr(resolve, '__module__', '?')}.{getattr(resolve, '__name__', 'resolve_card_source')}"
    try:
        report = resolve(str(card_path), temperature_K=temperature_K)
    except Exception as exc:
        return SolverParseResult(
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
            traceback=traceback.format_exc(),
            parser_qualname=qual,
        )
    return SolverParseResult(ok=True, report=report, parser_qualname=qual)


def validate_card_text(
    card_text: str,
    *,
    scratch_dir: str | Path,
    filename: str = "_lc2_4_validate_scratch.md",
    temperature_K: Optional[float] = None,
) -> SolverParseResult:
    """Validate an in-memory card by writing it to ``scratch_dir`` and
    parsing the file with the solver's resolver.

    The solver resolves ``.md`` *files* (it dispatches on the path
    suffix), so in-memory text must be materialised first.  The scratch
    file is overwritten on each call.
    """
    scratch_dir = Path(scratch_dir)
    scratch_dir.mkdir(parents=True, exist_ok=True)
    p = scratch_dir / filename
    p.write_text(card_text, encoding="utf-8")
    return validate_card_with_solver(p, temperature_K=temperature_K)
