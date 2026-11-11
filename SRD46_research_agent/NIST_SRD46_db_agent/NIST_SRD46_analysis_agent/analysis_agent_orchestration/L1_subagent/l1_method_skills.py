"""Per-sweep-method briefing skills for the L1 analysis agent.

Each supported solver ``sweep_method`` has one Markdown briefing under
``method_skills/`` showing the verdict schema that method supplies and
the reading hints that govern how to interpret it.  The briefing is
deterministic prompt text, not evidence: it never contains run-specific
numbers.  It is appended to the L1 system prompt when the dispatch text
names the method unambiguously, and otherwise delivered with the
pipeline result keyed on the solver-reported method.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Optional, Tuple


_SKILLS_DIR = Path(__file__).resolve().parent / "method_skills"

KNOWN_SWEEP_METHODS: Tuple[str, ...] = (
    "pH_sweep",
    "pourbaix_sweep",
    "titration_sweep",
    "freeform_sweep",
)

# Solver dispatcher aliases (see SRD46_numcalculator_api) map to canonical
# method names; keys are casefolded.
_METHOD_ALIASES: Dict[str, str] = {
    "ph_sweep": "pH_sweep",
    "pourbaix": "pourbaix_sweep",
    "pourbaix_sweep": "pourbaix_sweep",
    "titration": "titration_sweep",
    "titration_sweep": "titration_sweep",
    "freeform": "freeform_sweep",
    "freeform_sweep": "freeform_sweep",
}

_BRIEFING_CACHE: Dict[str, Optional[str]] = {}

# Pre-run intent inference from L0 dispatch text.  Word-bounded patterns
# keep substrings like "side-phase" from matching "e-ph"; the pipeline
# result keyed on the solver-reported method remains the ground truth.
_METHOD_HINT_PATTERNS: Dict[str, str] = {
    "pourbaix_sweep": (
        r"\bpourbaix\b|\bpredominance\s+(?:diagram|map)\b"
        r"|\be+h?\s*[-\u2013\u2014/]\s*ph\b|\bpotential\s*[-\u2013\u2014/]\s*ph\b"
    ),
    "pH_sweep": (
        r"\bph[\s_-]*sweep\b"
        r"|\bspeciation\s+(?:vs\.?|versus|against|over)\s+ph\b"
    ),
    "titration_sweep": r"\btitration\b",
    "freeform_sweep": r"\bfree[\s_-]?form\b",
}


def infer_sweep_methods(text: str) -> Tuple[str, ...]:
    """Canonical methods whose keywords appear in dispatch text."""

    lowered = (text or "").casefold()
    return tuple(
        method
        for method in KNOWN_SWEEP_METHODS
        if re.search(_METHOD_HINT_PATTERNS[method], lowered)
    )


def canonical_method(sweep_method: str) -> Optional[str]:
    """Resolve a solver-reported sweep method to its canonical name."""

    return _METHOD_ALIASES.get((sweep_method or "").strip().casefold())


def get_method_briefing(sweep_method: str) -> Optional[str]:
    """Return the briefing Markdown for one sweep method, or ``None``."""

    canonical = canonical_method(sweep_method)
    if canonical is None:
        return None
    if canonical not in _BRIEFING_CACHE:
        try:
            text = (_SKILLS_DIR / f"{canonical}.md").read_text(
                encoding="utf-8"
            ).strip()
        except OSError:
            text = ""
        _BRIEFING_CACHE[canonical] = text or None
    return _BRIEFING_CACHE[canonical]


def render_method_briefing(sweep_method: str) -> Optional[str]:
    """Render the bracketed briefing block for the pipeline result."""

    text = get_method_briefing(sweep_method)
    if text is None:
        return None
    return "\n".join([
        f"[METHOD BRIEFING — {canonical_method(sweep_method)}]",
        "This deterministic briefing describes the evidence supplied for "
        "this calculation method and the caveats that govern how to read "
        "it. Follow it when writing the analysis:",
        "-" * 60,
        text,
        "-" * 60,
        "[END METHOD BRIEFING]",
    ])
