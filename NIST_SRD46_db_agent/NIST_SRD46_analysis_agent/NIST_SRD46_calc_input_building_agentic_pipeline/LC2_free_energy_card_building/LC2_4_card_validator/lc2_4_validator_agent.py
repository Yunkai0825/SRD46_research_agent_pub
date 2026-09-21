"""LC2_4 — Free-energy card validator (solver-parse gate + LLM repair).

Pipeline position
-----------------
LC2_3 emits ``free_energy_card_deduplicated.md`` per chemical system.
LC2_4 is the **last gate** before the solver-parameter card stages: it
confirms the deduplicated card is *actually parseable* by the solver's
own card reader, and — if it is not — hands the verbatim parse error and
the card to an LLM repair agent that edits it back to a parseable state.

Design
------
1. **Validate** the card by dynamically importing the SOLVER's own
   resolver (``numcalc_input_cards_reader.resolve_card_source`` — the
   identical call ``SRD46_numcalculator_api.run_calculation`` makes) and
   running it against the card.  No parser is re-implemented here.
2. If the card parses cleanly → emit it unchanged as the validated card.
3. If it fails → invoke :func:`run_repair_agent`, which edits the card
   with generic markdown tools and re-validates against the same solver
   parser after each edit until it is VALID.
4. A final hard validation is run on the repaired text.  If the card
   still fails to parse, LC2_4 **raises** — a non-parseable card must not
   be forwarded to the solver-parameter stages.

Public API
----------
* :func:`configure_lc2_4_session`
* :func:`run_lc2_4`
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── path bootstrap: import the analysis toolbox helper as a bare
#    top-level package, never via the heavy NIST_SRD46_analysis_agent
#    package __init__ chain. ────────────────────────────────────────────
_ANALYSIS_ROOT = Path(__file__).absolute().parents[3]   # NIST_SRD46_analysis_agent/
if str(_ANALYSIS_ROOT) not in sys.path:
    sys.path.insert(0, str(_ANALYSIS_ROOT))

from analysis_agent_toolbox.calc_wrappers import _require_purpose_tasks
from ._card_validation import validate_card_text, validate_card_with_solver
from ._repair_subagent import run_repair_agent
from ..agent_context_artifacts import write_agent_context_index

log = logging.getLogger("Analysis.LC2_4")


class CardValidationError(RuntimeError):
    """Raised when a card cannot be made parseable by the solver."""


_SRD_DUP_RE = re.compile(r"\[(srd_\d+) (\d+)/(\d+) (frame|data)\]")
_TABLE_SEP_CHARS = {"|", "-", ":", " "}


def _assert_srd_twins_resolved(card_text: str) -> None:
    """Fail closed when ≥2 included rows belong to one certified twin set.

    LC2_1 keeps conflicting SRD-SRD duplicate copies in the card for
    LC2_3 to adjudicate, tagging each with a compact ``[srd_<set> r/n
    frame|data]`` token (full provenance in srd_srd_duplicates.json).
    ``frame`` certifies one SRD record rendered in different temperature
    frames: at most one copy per set may remain ``include=true`` at the
    solver gate, anything else double-counts a species.  ``data`` sets
    (different SRD records sharing a formula) pass freely.
    """
    included_by_set: Dict[str, List[str]] = {}
    in_table = False
    cols: Dict[str, int] = {}
    for line in card_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            in_table = False
            cols = {}
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        lower = [c.lower() for c in cells]
        if ("label" in lower and "include" in lower
                and "additional_notes" in lower):
            in_table = True
            cols = {name: i for i, name in enumerate(lower)}
            continue
        if not in_table or set(stripped) <= _TABLE_SEP_CHARS:
            continue
        inc_i = cols.get("include", -1)
        notes_i = cols.get("additional_notes", -1)
        if not (0 <= inc_i < len(cells) and 0 <= notes_i < len(cells)):
            continue
        if cells[inc_i].lower() != "true":
            continue
        m = _SRD_DUP_RE.search(cells[notes_i])
        if not m:
            continue
        set_id, _rank, _n, kind = m.groups()
        if kind != "frame":
            continue
        label_i = cols.get("label", -1)
        label = cells[label_i] if 0 <= label_i < len(cells) else "?"
        included_by_set.setdefault(set_id, []).append(label)
    conflicts = {s: ls for s, ls in included_by_set.items() if len(ls) > 1}
    if conflicts:
        details = "; ".join(
            f"{set_id}: {', '.join(labels)}"
            for set_id, labels in sorted(conflicts.items())
        )
        raise CardValidationError(
            "LC2_4: unresolved SRD-SRD frame twins remain included in "
            "the card (LC2_3 must keep exactly one per certified set) — "
            f"{details}"
        )


# ════════════════════════════════════════════════════════════════════
#  Session state
# ════════════════════════════════════════════════════════════════════

_SESSION: Dict[str, Any] = {
    "session_dir":    None,
    "history":        None,
    "stats":          None,
    "working_memory": None,
    "debug":          False,
    "call_index":     0,
}


def configure_lc2_4_session(
    *,
    session_dir: str | Path,
    history: Any = None,
    stats: Any = None,
    working_memory: Any = None,
    debug: bool = False,
) -> None:
    """Bind the per-session side-channel."""
    _SESSION["session_dir"]    = Path(session_dir)
    _SESSION["history"]        = history
    _SESSION["stats"]          = stats
    _SESSION["working_memory"] = working_memory
    _SESSION["debug"]          = bool(debug)
    _SESSION["call_index"]     = 0


def _per_call_dir() -> Path:
    base = _SESSION["session_dir"] or Path.cwd()
    Path(base).mkdir(parents=True, exist_ok=True)
    # Keep each audit bundle immutable and prevent stale manifests from a
    # prior configured session from contaminating completeness accounting.
    while True:
        _SESSION["call_index"] += 1
        out = Path(base) / f"LC2_4_call_{_SESSION['call_index']:02d}"
        try:
            out.mkdir(exist_ok=False)
        except FileExistsError:
            continue
        return out


def _artifact(path: str | Path | None) -> Optional[Dict[str, Any]]:
    if path is None:
        return None
    item = Path(path)
    if not item.is_file():
        return {"path": str(item.resolve()), "exists": False}
    data = item.read_bytes()
    return {
        "path": str(item.resolve()),
        "exists": True,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _write_manifest(call_dir: Path, payload: Dict[str, Any]) -> Path:
    path = call_dir / "lc2_4_manifest.json"
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return path


# ════════════════════════════════════════════════════════════════════
#  Report rendering
# ════════════════════════════════════════════════════════════════════

def _render_report(
    *,
    call_index: int,
    validated_card: Path,
    enriched_card_path: Path,
    initial_ok: bool,
    initial_error: Optional[str],
    repaired: bool,
    repair_result: Optional[Dict[str, Any]],
    parser_qualname: str,
    elapsed: float,
) -> str:
    lines = [
        f"# LC2_4 validation report (call {call_index:02d})",
        "",
        f"- input_card:     `{enriched_card_path}`",
        f"- validated_card: `{validated_card}`",
        f"- solver_parser:  `{parser_qualname or 'numcalc_input_cards_reader.resolve_card_source'}`",
        f"- elapsed_s:      {elapsed:.2f}",
        "",
        "## Phase: LC2_4 — solver-parse validation",
        "",
    ]
    if initial_ok:
        lines.append("**Status**: OK — card parsed cleanly on first attempt "
                     "(no repair needed).")
        return "\n".join(lines)

    lines.append("**Initial parse**: FAILED")
    lines.append("")
    lines.append("```")
    lines.append((initial_error or "").strip())
    lines.append("```")
    lines.append("")

    if repaired and repair_result:
        lines.append(f"**Repair**: OK — card repaired in "
                     f"{repair_result.get('n_edits', 0)} edit(s), "
                     f"{repair_result.get('iterations', 0)} LLM iteration(s).")
    elif repair_result:
        lines.append("**Repair**: FAILED — card still does not parse.")
        lines.append("")
        lines.append("```")
        lines.append((repair_result.get("final_error") or "").strip())
        lines.append("```")
    return "\n".join(lines)


# ════════════════════════════════════════════════════════════════════
#  Public entry point
# ════════════════════════════════════════════════════════════════════

def run_lc2_4(
    *,
    purpose: str,
    tasks: str,
    enriched_card_path: str | Path,
    output_dir: str | Path,
    temperature_K: Optional[float] = None,
) -> Dict[str, Any]:
    """Validate (and, if needed, repair) the post-dedup free-energy card.

    Parameters
    ----------
    purpose, tasks
        L0 audit contract (same fields passed to L1 / LC2_3).
    enriched_card_path
        Path to the LC2_3 deduplicated card markdown.
    output_dir
        Where to write the validated card + artefacts.
    temperature_K
        Optional temperature forwarded to the solver resolver (matches
        the solver's own ``resolve_card_source`` signature; defaults to
        None, which is what ``.md`` parsing uses).

    Returns
    -------
    dict
        ``status`` (always ``"ok"`` on return — failures raise),
        ``output_dir``, ``validated_card_path``, ``repaired`` (bool),
        ``n_edits``, ``elapsed_s``, ``report``.

    Raises
    ------
    FileNotFoundError
        If ``enriched_card_path`` does not exist.
    CardValidationError
        If the card cannot be made parseable by the solver after repair.
    """
    purpose, tasks_text = _require_purpose_tasks(purpose, tasks)

    if _SESSION["session_dir"] is None:
        configure_lc2_4_session(session_dir=Path.cwd() / "_lc2_4_adhoc_session")

    call_dir = _per_call_dir()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    enriched_card_path = Path(enriched_card_path)
    if not enriched_card_path.exists():
        raise FileNotFoundError(
            f"LC2_4: deduplicated card not found: {enriched_card_path}")
    card_text = enriched_card_path.read_text(encoding="utf-8")
    # Deterministic gate before solver parsing: duplicate twins kept by
    # LC2_1 must have been resolved to a single included copy by LC2_3.
    _assert_srd_twins_resolved(card_text)
    manifest_payload: Dict[str, Any] = {
        "schema_version": 1,
        "artifact_kind": "LC2_4 solver-card validation run",
        "stage": "LC2_4",
        "call_id": call_dir.name,
        "invocation": {
            "purpose": purpose,
            "tasks": tasks_text,
            "temperature_K": temperature_K,
            "debug": _SESSION["debug"],
        },
        "inputs": {"candidate_card": _artifact(enriched_card_path)},
    }

    history = _SESSION["history"]
    stats   = _SESSION["stats"]
    debug   = _SESSION["debug"]

    if history is not None:
        history.log("LC2_4_validate_start",
                    call_index=_SESSION["call_index"],
                    enriched_card_path=str(enriched_card_path),
                    card_chars=len(card_text))

    t0 = time.time()
    validated_card = output_dir / "free_energy_card_validated.md"

    # ── 1. Initial solver-parse validation ────────────────────────
    initial = validate_card_with_solver(
        enriched_card_path, temperature_K=temperature_K)

    repaired = False
    repair_result: Optional[Dict[str, Any]] = None
    final_card_text = card_text

    if initial.ok:
        log.info("LC2_4 card parsed cleanly on first attempt: %s",
                 enriched_card_path)
    else:
        log.warning("LC2_4 card failed solver parse; invoking repair agent. "
                    "error=%s", initial.short_error())
        if history is not None:
            history.log("LC2_4_repair_start",
                        call_index=_SESSION["call_index"],
                        error=initial.short_error())

        repair_result = run_repair_agent(
            purpose=purpose,
            tasks=tasks_text,
            card_text=card_text,
            parse_error=initial.short_error(),
            parse_traceback=initial.traceback,
            scratch_dir=call_dir,
            debug=debug,
        )
        final_card_text = repair_result.get("repaired_card_text") or card_text

        # ── 3. Final hard validation of the repaired text ─────────
        final = validate_card_text(
            final_card_text, scratch_dir=call_dir,
            filename="_lc2_4_final_check.md", temperature_K=temperature_K)
        repaired = bool(final.ok)

        if not final.ok:
            elapsed = time.time() - t0
            report = _render_report(
                call_index=_SESSION["call_index"],
                validated_card=validated_card,
                enriched_card_path=enriched_card_path,
                initial_ok=False, initial_error=initial.short_error(),
                repaired=False, repair_result=repair_result,
                parser_qualname=initial.parser_qualname,
                elapsed=elapsed,
            )
            (call_dir / "report.md").write_text(report, encoding="utf-8")
            context_json, context_md = write_agent_context_index(call_dir)
            context_index = json.loads(context_json.read_text(encoding="utf-8"))
            manifest_payload.update({
                "status": "failed",
                "initial_solver_parse": {
                    "ok": False,
                    "error": initial.short_error(),
                    "parser": initial.parser_qualname,
                },
                "final_solver_parse": {
                    "ok": False,
                    "error": final.short_error(),
                },
                "repair": {
                    "invoked": True,
                    "status": repair_result.get("status"),
                    "n_edits": repair_result.get("n_edits", 0),
                },
                "agent_context": {
                    "index_json": _artifact(context_json),
                    "index_markdown": _artifact(context_md),
                    "expected_calls": 1,
                    "documented_calls": context_index["agent_turn_count"],
                    "complete": (
                        context_index["agent_turn_count"] == 1
                        and context_index.get(
                            "all_context_bundles_complete", False
                        )
                    ),
                },
                "outputs": {"human_report": _artifact(call_dir / "report.md")},
                "elapsed_s": round(elapsed, 3),
            })
            _write_manifest(call_dir, manifest_payload)
            if stats is not None:
                stats.incr("LC2_4", "validate_calls", 1)
                stats.incr("LC2_4", "failed", 1)
            if history is not None:
                history.log("LC2_4_validate_end",
                            call_index=_SESSION["call_index"],
                            elapsed_s=elapsed, status="failed",
                            error=final.short_error())
            raise CardValidationError(
                "LC2_4: card still fails the solver parser after repair "
                f"({repair_result.get('n_edits', 0)} edit(s)). "
                f"Last error: {final.short_error()}"
            )

    # ── 2./4. Emit the validated card ─────────────────────────────
    validated_card.write_text(final_card_text, encoding="utf-8")
    elapsed = time.time() - t0

    report = _render_report(
        call_index=_SESSION["call_index"],
        validated_card=validated_card,
        enriched_card_path=enriched_card_path,
        initial_ok=initial.ok, initial_error=initial.short_error() if not initial.ok else None,
        repaired=repaired, repair_result=repair_result,
        parser_qualname=initial.parser_qualname,
        elapsed=elapsed,
    )
    (call_dir / "report.md").write_text(report, encoding="utf-8")
    context_json, context_md = write_agent_context_index(call_dir)
    context_index = json.loads(context_json.read_text(encoding="utf-8"))
    expected_contexts = 1 if not initial.ok else 0
    context_complete = (
        context_index["agent_turn_count"] == expected_contexts
        and context_index.get("all_context_bundles_complete", False)
    )
    manifest_payload.update({
        "status": "ok",
        "initial_solver_parse": {
            "ok": initial.ok,
            "error": initial.short_error() if not initial.ok else None,
            "parser": initial.parser_qualname,
        },
        "final_solver_parse": {"ok": True, "error": None},
        "repair": {
            "invoked": not initial.ok,
            "status": (repair_result or {}).get("status"),
            "n_edits": int((repair_result or {}).get("n_edits", 0)),
        },
        "agent_context": {
            "index_json": _artifact(context_json),
            "index_markdown": _artifact(context_md),
            "expected_calls": expected_contexts,
            "documented_calls": context_index["agent_turn_count"],
            "complete": context_complete,
        },
        "outputs": {
            "validated_card": _artifact(validated_card),
            "human_report": _artifact(call_dir / "report.md"),
        },
        "elapsed_s": round(elapsed, 3),
    })
    manifest_path = _write_manifest(call_dir, manifest_payload)
    if not context_complete:
        manifest_payload["status"] = "failed"
        manifest_payload["failure"] = (
            f"documented {context_index['agent_turn_count']} of "
            f"{expected_contexts} expected LC2_4 agent turns"
        )
        _write_manifest(call_dir, manifest_payload)
        raise CardValidationError(
            "LC2_4 agent-context audit is incomplete; refusing the otherwise "
            "parseable card. " + manifest_payload["failure"]
        )

    n_edits = int((repair_result or {}).get("n_edits", 0))

    if stats is not None:
        stats.incr("LC2_4", "validate_calls", 1)
        stats.incr("LC2_4", "ok", 1)
        if repaired:
            stats.incr("LC2_4", "repaired", 1)
            stats.incr("LC2_4", "edits_applied", n_edits)
            stats.incr("LC2_4", "llm_iterations",
                       int((repair_result or {}).get("iterations", 0)))
        else:
            stats.incr("LC2_4", "clean", 1)

    if _SESSION["working_memory"] is not None:
        try:
            _SESSION["working_memory"].set(
                "validated_card_path", str(validated_card))
        except Exception as exc:                # pragma: no cover
            log.warning("working_memory.set failed: %s", exc)

    if history is not None:
        history.log("LC2_4_validate_end",
                    call_index=_SESSION["call_index"],
                    elapsed_s=elapsed, status="ok",
                    repaired=repaired, n_edits=n_edits)

    return {
        "status":              "ok",
        "output_dir":          str(call_dir),
        "validated_card_path": str(validated_card),
        "manifest_path":       str(manifest_path),
        "agent_context_index_path": str(context_json),
        "agent_context_complete": context_complete,
        "repaired":            repaired,
        "n_edits":             n_edits,
        "elapsed_s":           round(elapsed, 3),
        "report":              report,
    }
