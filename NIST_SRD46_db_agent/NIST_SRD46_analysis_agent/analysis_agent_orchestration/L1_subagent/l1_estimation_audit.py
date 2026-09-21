"""Deterministic model-coverage and enabled-estimation report guards for L1."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .l1_state import (
    _L1State,
    _rel_path_under,
    _rel_to_session,
    _stat_incr,
    _wm_append,
)


_ANALYSIS_CHUNK_MAX_CHARS = 3_500


def _read_json_object(path_value: Any) -> Dict[str, Any]:
    """Load a JSON object from ``path_value``; return ``{}`` on failure."""

    if not path_value:
        return {}
    try:
        payload = json.loads(Path(path_value).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _chemical_system(payload: Any) -> Dict[str, Any]:
    """Return the native ``chemical_system`` object from a catalog/card."""

    if not isinstance(payload, dict):
        return {}
    catalog = payload.get("system_catalog")
    if isinstance(catalog, dict):
        system = catalog.get("chemical_system")
        if isinstance(system, dict):
            return system
    system = payload.get("chemical_system")
    return system if isinstance(system, dict) else {}


def _is_water_ligand(item: Dict[str, Any]) -> bool:
    if item.get("water_species") is True:
        return True
    db_id = str(item.get("db_id") or "").strip().lower()
    name = str(item.get("name") or "").strip().lower()
    return db_id in {"ligand_10076", "10076"} or name in {
        "hydroxide",
        "hydroxide ion",
        "oh-",
        "oh−",
    }


def _ligand_descriptor(item: Dict[str, Any]) -> Dict[str, Any]:
    """Keep the stable identity fields needed for a coverage audit."""

    out: Dict[str, Any] = {"name": str(item.get("name") or "").strip()}
    for key in ("db_id", "internal_id"):
        value = item.get(key)
        if value not in (None, ""):
            out[key] = str(value)
    return out


def _name_keys(value: Any) -> set[str]:
    """Build conservative alias keys from one catalog display name."""

    text = str(value or "").strip().lower()
    if not text:
        return set()
    pieces = [text, re.sub(r"\([^)]*\)", " ", text)]
    pieces.extend(re.findall(r"\(([^)]*)\)", text))
    keys = {
        re.sub(r"[^a-z0-9]+", "", piece)
        for piece in pieces
        if piece.strip()
    }
    return {key for key in keys if len(key) >= 2}


def _same_ligand(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    for key in ("db_id", "internal_id"):
        lhs = str(left.get(key) or "").strip().lower()
        rhs = str(right.get(key) or "").strip().lower()
        if lhs and rhs and lhs == rhs:
            return True
    return bool(_name_keys(left.get("name")) & _name_keys(right.get("name")))


def _build_model_coverage(
    built: Dict[str, Any],
    *,
    call_dir: Path,
) -> Dict[str, Any]:
    """Compare resolved LC1 ligands with the final solver-card ligands."""

    lc1 = built.get("lc1") if isinstance(built.get("lc1"), dict) else {}
    requested_payload = (lc1 or {}).get("system_catalog")
    if not isinstance(requested_payload, dict):
        requested_payload = _read_json_object(built.get("system_catalog_path"))

    calc_path_value = built.get("calc_input_card_path")
    calc_payload = _read_json_object(calc_path_value)
    requested_raw = _chemical_system(requested_payload).get("ligands") or []
    modeled_raw = _chemical_system(calc_payload).get("ligands") or []
    requested = [
        _ligand_descriptor(item)
        for item in requested_raw
        if isinstance(item, dict) and not _is_water_ligand(item)
    ]
    modeled = [
        _ligand_descriptor(item)
        for item in modeled_raw
        if isinstance(item, dict) and not _is_water_ligand(item)
    ]
    omitted = [
        item for item in requested
        if not any(_same_ligand(item, candidate) for candidate in modeled)
    ]
    matched = [item for item in requested if item not in omitted]

    calc_path = Path(calc_path_value) if calc_path_value else None
    path_ok = bool(calc_path and calc_path.is_file())
    catalog_ok = bool(requested_payload)
    determinable = path_ok and catalog_ok
    complete = bool(determinable and not omitted)
    if not determinable:
        audit_status = "unknown"
        warning = (
            "Model coverage could not be verified from both the resolved LC1 "
            "catalog and final LC3 calculation card. Treat the scientific "
            "scope as unverified."
        )
    elif omitted:
        audit_status = "partial"
        names = ", ".join(item.get("name") or "(unnamed)" for item in omitted)
        warning = (
            f"The final calculation card omitted requested ligands: {names}. "
            "They were not modeled. Do not claim that this calculation tests "
            "their complexation, binding strength, or effect on the diagram."
        )
    else:
        audit_status = "complete"
        warning = "All requested non-water ligands are present in the final card."

    try:
        calc_rel = (
            calc_path.resolve().relative_to(call_dir.resolve()).as_posix()
            if calc_path else None
        )
    except Exception:
        calc_rel = str(calc_path) if calc_path else None

    return {
        "status": audit_status,
        "complete": complete,
        "scientific_scope": (
            "requested_system" if complete else "reduced_or_unverified_system"
        ),
        "requested_ligands": requested,
        "modeled_ligands": modeled,
        "matched_requested_ligands": matched,
        "omitted_requested_ligands": omitted,
        "final_calc_input_card_path": calc_rel,
        "warning": warning,
    }


def _build_topology_summary(
    solver_dir: Optional[Path],
    *,
    call_dir: Path,
) -> Dict[str, Any]:
    """Read every complete ``topo_regions.csv`` without LLM compaction."""

    if solver_dir is None or not solver_dir.exists():
        return {
            "status": "unavailable",
            "n_maps": 0,
            "n_regions": 0,
            "maps": [],
            "warning": "Solver topology directory is unavailable.",
        }

    maps: list[Dict[str, Any]] = []
    for path in sorted(solver_dir.rglob("topo_regions.csv")):
        regions: list[Dict[str, Any]] = []
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    item: Dict[str, Any] = {
                        "id": str(row.get("id") or ""),
                        "label": str(row.get("label") or ""),
                        "name": str(row.get("name") or ""),
                    }
                    raw_measure = row.get("measure")
                    try:
                        item["measure"] = (
                            float(raw_measure)
                            if raw_measure not in (None, "") else None
                        )
                    except (TypeError, ValueError):
                        item["measure"] = raw_measure
                    regions.append(item)
        except Exception as exc:
            maps.append({
                "path": _rel_path_under(path, call_dir),
                "n_regions": 0,
                "regions": [],
                "error": f"{type(exc).__name__}: {exc}",
            })
            continue
        maps.append({
            "path": _rel_path_under(path, call_dir),
            "n_regions": len(regions),
            "regions": regions,
        })

    topology_status = (
        "ok" if maps and all("error" not in item for item in maps) else (
            "unavailable" if not maps else "partial"
        )
    )
    return {
        "status": topology_status,
        "n_maps": len(maps),
        "n_regions": sum(int(item.get("n_regions") or 0) for item in maps),
        "maps": maps,
        "warning": (
            "Region counts and rows were parsed deterministically from the "
            "complete topology CSV files; use these values instead of a "
            "truncated tool preview."
            if topology_status == "ok" else (
                "At least one topology CSV could not be parsed completely; "
                "do not report a complete region count."
                if topology_status == "partial"
                else "No topo_regions.csv file was produced."
            )
        ),
    }


_ESTIMATION_PROVENANCE_HEADING = "## Estimated-value provenance (deterministic)"


def _append_estimation_provenance(state: _L1State, body: str) -> str:
    """Attach enabled-run estimation facts beneath the committed prose.

    The agent's committed analysis is the L1-to-L0 handoff; this appendix is
    the deterministic transport for how each session-estimated constant was
    obtained, so synthesis never depends on the agent restating the
    enrichment payload.
    """

    if _ESTIMATION_PROVENANCE_HEADING in body:
        return body
    enrichment = (
        (state.pipeline_status or {}).get("estimated_equilibrium_enrichment")
        or {}
    )
    lines = [_ESTIMATION_PROVENANCE_HEADING, ""]
    if not isinstance(enrichment, dict) or not enrichment:
        lines.append(
            "No enabled estimation status was published for this call; no "
            "session-estimated constant may be quoted from it."
        )
        return body.rstrip() + "\n\n" + "\n".join(lines) + "\n"
    status = str(enrichment.get("status") or "unknown")
    used_count = int(
        enrichment.get("materialized_estimated_entry_count") or 0
    )
    raw_complete = enrichment.get("estimation_search_complete")
    if isinstance(raw_complete, bool):
        search_complete = raw_complete
    else:
        search_complete = status not in {"reference_only", "failed", "unknown"}
    source = str(enrichment.get("source") or "SRD46 query estimated values")
    lines.append(
        f"- Estimation status: `{status}`; search "
        f"{'complete' if search_complete else 'INCOMPLETE'}; "
        f"{used_count} materialized entries; source: {source}."
    )
    if not search_complete:
        failure = enrichment.get("failure_summary") or {}
        reason = str(enrichment.get("reference_only_reason") or "unspecified")
        lines.append(
            f"- Reference-only fallback after an incomplete search (reason: "
            f"`{reason}`; parser failures: "
            f"{int(failure.get('n_parser_failures') or 0)}; scope-limit "
            f"omissions: {int(failure.get('n_scope_limit_omissions') or 0)}). "
            "A zero estimate count here is not evidence that no relevant "
            "equilibrium exists."
        )
    rows = [
        row
        for row in (enrichment.get("estimated_stability_constants") or [])
        if isinstance(row, dict)
    ]
    if rows:
        lines.append(
            "- Session-local estimates (not measured SRD46 entries) and the "
            "validated per-entry estimation justification:"
        )
        for row in rows:
            evidence = ", ".join(
                str(item) for item in (row.get("evidence_vlm_ids") or [])
            ) or "none"
            lines.append(
                f"  - {row.get('metal_name', row.get('metal_id', ''))} / "
                f"{row.get('ligand_name', row.get('ligand_id', ''))} — "
                f"beta_def_{row.get('beta_definition_id', '')}: "
                f"log10 K = {row.get('log10_K', '')} ± "
                f"{row.get('uncertainty_log10', '')} "
                f"(T = {row.get('temperature_C', '')} C, "
                f"I = {row.get('ionic_strength_M', '')} mol/L). Method: "
                f"{row.get('estimation_method') or 'not recorded'} "
                f"[evidence: {evidence}]"
            )
            annotation = row.get("agent_annotation")
            if isinstance(annotation, dict):
                discussion = str(annotation.get("discussion") or "").strip()
                if discussion:
                    core = ", ".join(
                        str(item)
                        for item in (annotation.get("core_source_ids") or [])
                    ) or "none"
                    lines.append(
                        f"    Parser digest: {discussion} "
                        f"[core sources: {core}]"
                    )
    else:
        lines.append(
            "- No estimated stability constant was materialized for this run."
        )
    return body.rstrip() + "\n\n" + "\n".join(lines) + "\n"


def _persist_enabled_quality(state: _L1State, report: str) -> None:
    """Persist deterministic enabled-run coverage/report acceptance facts."""

    quality = {
        "call": state.idx,
        "estimation_enabled": True,
        "agent_committed_report": state.agent_committed_report,
        "model_coverage": state.model_coverage,
        "topology_summary": state.topology_summary,
        "estimated_equilibrium_enrichment": (
            (state.pipeline_status or {}).get("estimated_equilibrium_enrichment")
        ),
        "ld_verdict": state.last_ld_verdict,
        "report_path": _rel_to_session(state.call_dir / "l1_report.md"),
    }
    try:
        (state.call_dir / "l1_scientific_quality.json").write_text(
            json.dumps(quality, indent=2, default=str), encoding="utf-8"
        )
        (state.call_dir / "l1_report.md").write_text(report, encoding="utf-8")
        (state.call_dir / "l1_analysis.json").write_text(
            json.dumps(
                {"analysis": report, "artifacts": state.artifacts},
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:  # pragma: no cover
        pass
    _wm_append("l1_scientific_quality", quality)


def _persist_analysis_draft(state: _L1State, *, committed: bool = False) -> None:
    """Persist the exact staged report plus a small recovery/audit ledger."""

    body = "".join(state.analysis_draft_chunks)
    try:
        (state.call_dir / "l1_report.draft.md").write_text(
            body,
            encoding="utf-8",
        )
        (state.call_dir / "l1_report_draft.json").write_text(
            json.dumps(
                {
                    "generation": state.analysis_draft_generation,
                    "chunk_count": len(state.analysis_draft_chunks),
                    "chunk_chars": [
                        len(chunk) for chunk in state.analysis_draft_chunks
                    ],
                    "total_chars": len(body),
                    "committed": bool(committed),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:  # pragma: no cover - audit persistence is best effort
        pass


def _make_append_analysis_chunk(state: _L1State) -> Callable[..., str]:
    def append_analysis_chunk(
        chunk_index: int = 0,
        analysis_markdown_chunk: str = "",
        reset: bool = False,
    ) -> str:
        """Stage one ordered piece of a long L1 report (NONTERMINAL).

        Args:
            chunk_index: One-based contiguous chunk number. Send one chunk per
                model turn. An identical replay is accepted idempotently.
            analysis_markdown_chunk: At most 3500 characters of the final
                Markdown report, preferably ending at a paragraph boundary.
            reset: Set true only with chunk 1 to start or replace a draft.

        Returns:
            An ``OK`` receipt with the next expected index, or an actionable
            ``ERROR``. This tool does not commit or end the L1 turn.
        """

        if isinstance(chunk_index, bool) or not isinstance(chunk_index, int):
            return "ERROR: 'chunk_index' must be a one-based integer."
        if chunk_index < 1:
            return "ERROR: 'chunk_index' must be at least 1."
        if not isinstance(analysis_markdown_chunk, str):
            return "ERROR: 'analysis_markdown_chunk' must be text."
        if not analysis_markdown_chunk.strip():
            return "ERROR: 'analysis_markdown_chunk' is empty."
        if len(analysis_markdown_chunk) > _ANALYSIS_CHUNK_MAX_CHARS:
            return (
                "ERROR: analysis chunk is too large "
                f"({len(analysis_markdown_chunk)} > "
                f"{_ANALYSIS_CHUNK_MAX_CHARS} characters). Split it at a "
                "paragraph boundary and retry this index."
            )
        if not isinstance(reset, bool):
            return "ERROR: 'reset' must be true or false."
        if reset and chunk_index != 1:
            return "ERROR: 'reset=true' is allowed only for chunk_index=1."

        if reset:
            state.analysis_draft_chunks.clear()
            state.analysis_draft_generation += 1
            # A revised draft supersedes an earlier terminal report. If the
            # revision never commits, callers must not silently reuse it.
            state.agent_committed_report = False
            state.committed_report = None
            state.artifacts = []

        existing_count = len(state.analysis_draft_chunks)
        if chunk_index <= existing_count:
            existing = state.analysis_draft_chunks[chunk_index - 1]
            if existing != analysis_markdown_chunk:
                return (
                    f"ERROR: chunk {chunk_index} already exists with different "
                    "content. Restart the draft with reset=true at chunk 1."
                )
            _persist_analysis_draft(state)
            return (
                f"OK — chunk {chunk_index} already staged identically "
                f"(idempotent replay; next index {existing_count + 1})."
            )

        expected = existing_count + 1
        if chunk_index != expected:
            return (
                f"ERROR: out-of-order chunk {chunk_index}; next expected "
                f"chunk_index is {expected}."
            )

        state.analysis_draft_chunks.append(analysis_markdown_chunk)
        _persist_analysis_draft(state)
        total_chars = sum(len(chunk) for chunk in state.analysis_draft_chunks)
        return (
            f"OK — staged chunk {chunk_index} "
            f"({len(analysis_markdown_chunk)} chars; {total_chars} total; "
            f"next index {chunk_index + 1})."
        )

    return append_analysis_chunk


def _make_record_analysis(state: _L1State) -> Callable[..., str]:
    def record_analysis(
        analysis_markdown: str = "",
        artifact_paths: str = "",
        expected_chunks: int = 0,
    ) -> str:
        """Submit the final analysis and end the turn (REQUIRED terminal tool).

        Args:
            analysis_markdown: The self-contained scientific write-up (the
                report L0 reads). Use the Doability / Result / Analysis /
                Artifacts sections. For a staged long report, leave this empty.
            artifact_paths: Comma- or newline-separated relative paths to
                the key output files the user should open.
            expected_chunks: For a staged long report, the exact number of
                chunks accepted by append_analysis_chunk. Leave zero when the
                complete short report is supplied in analysis_markdown.

        Returns:
            ``"OK — analysis recorded."`` or an ``ERROR: ...`` asking you
            to resubmit.
        """

        if not isinstance(analysis_markdown, str):
            return "ERROR: 'analysis_markdown' must be text."
        if isinstance(expected_chunks, bool) or not isinstance(
            expected_chunks, int
        ):
            return "ERROR: 'expected_chunks' must be a non-negative integer."
        if expected_chunks < 0:
            return "ERROR: 'expected_chunks' must be a non-negative integer."
        if not isinstance(artifact_paths, str):
            return "ERROR: 'artifact_paths' must be text."

        inline_body = analysis_markdown.strip()
        if inline_body:
            if expected_chunks:
                return (
                    "ERROR: do not mix inline 'analysis_markdown' with "
                    "'expected_chunks'. Use one report path only."
                )
            # A complete inline submission intentionally supersedes any
            # uncommitted draft while preserving the historical short-report
            # contract.
            had_draft = bool(state.analysis_draft_chunks)
            state.analysis_draft_chunks.clear()
            if had_draft:
                state.analysis_draft_generation += 1
                _persist_analysis_draft(state)
            body = inline_body
        else:
            actual_chunks = len(state.analysis_draft_chunks)
            if not expected_chunks:
                return (
                    "ERROR: 'analysis_markdown' is empty. Submit a short "
                    "write-up inline, or stage a long report and provide its "
                    "positive 'expected_chunks' count."
                )
            if actual_chunks != expected_chunks:
                return (
                    "ERROR: staged report is incomplete: "
                    f"expected_chunks={expected_chunks}, but "
                    f"{actual_chunks} chunk(s) are present."
                )
            body = "".join(state.analysis_draft_chunks).strip()
            if not body:
                return "ERROR: the staged analysis report is empty."

        artifacts = [
            item.strip()
            for item in re.split(r"[\n,]+", artifact_paths or "")
            if item.strip()
        ]
        state.agent_committed_report = True
        if state.estimate_missing_equilibria:
            # Provenance rides with the prose so LD reviews both together.
            body = _append_estimation_provenance(state, body)
        state.committed_report = body
        state.artifacts = artifacts
        if state.analysis_draft_chunks:
            _persist_analysis_draft(state, committed=True)

        try:
            (state.call_dir / "l1_report.md").write_text(body, encoding="utf-8")
            (state.call_dir / "l1_analysis.json").write_text(
                json.dumps(
                    {"analysis": body, "artifacts": artifacts},
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception:  # pragma: no cover
            pass

        _wm_append("l1_analysis_reports", {
            "call": state.idx,
            "purpose": state.purpose,
            "report_path": _rel_to_session(state.call_dir / "l1_report.md"),
            "artifacts": artifacts,
        })
        _stat_incr("record", "ok")
        return (
            f"OK — analysis recorded ({len(body)} chars, "
            f"{len(artifacts)} artifacts)."
        )

    return record_analysis


__all__ = [
    "_ANALYSIS_CHUNK_MAX_CHARS",
    "_append_estimation_provenance",
    "_build_model_coverage",
    "_build_topology_summary",
    "_make_append_analysis_chunk",
    "_make_record_analysis",
    "_persist_enabled_quality",
]
