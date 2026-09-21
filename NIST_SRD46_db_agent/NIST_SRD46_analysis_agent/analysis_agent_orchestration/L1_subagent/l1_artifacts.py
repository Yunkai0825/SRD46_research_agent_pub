"""Solver-artifact delivery and bounded inspection tools for L1.

The normal evidence path is intentionally asymmetric: complete deterministic
``*_verdict.md`` files are injected in the build-and-solve tool result, while
raw topology JSON is never placed in model context.  Narrow follow-up tools
can read a named verdict section or one canonical topology feature ID.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .l1_method_skills import canonical_method, render_method_briefing
from .l1_state import _L1State, _SESSION, _rel_to_session


_READ_DEFAULT_MAX_CHARS = 8000
_READ_HARD_MAX_CHARS = 60000
_VERDICT_FALLBACK_HEAD_CHARS = 20000
_VERDICT_FALLBACK_TAIL_CHARS = 10000
_REFERENCE_CONSTANTS_MAX_CHARS = 60000


def _list_solver_files(state: _L1State) -> List[Path]:
    if state.solver_dir is None or not state.solver_dir.exists():
        return []
    return [path for path in sorted(state.solver_dir.rglob("*")) if path.is_file()]


def _resolve_call_file(state: _L1State, relative_path: str) -> Optional[Path]:
    """Resolve one advertised output path without allowing directory escape."""

    call_base = Path(state.call_dir).resolve()
    rel = (relative_path or "").strip().replace("\\", "/").lstrip("/")
    if not rel:
        return None
    candidates: List[Path] = []
    session_dir = _SESSION.get("session_dir")
    if session_dir is not None:
        candidates.append((Path(session_dir) / rel).resolve())
    candidates.append((call_base / rel).resolve())
    for candidate in candidates:
        try:
            candidate.relative_to(call_base)
        except ValueError:
            continue
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _collect_default_verdicts(output_paths: List[Path]) -> List[tuple[Path, str]]:
    """Load every solver-written Markdown verdict exactly once, in full."""

    verdict_paths = sorted({
        path.resolve()
        for path in output_paths
        if path.suffix.lower() == ".md"
        and path.name.lower().endswith("verdict.md")
        and path.exists()
        and path.is_file()
    })
    return [
        (path, path.read_text(encoding="utf-8", errors="replace"))
        for path in verdict_paths
    ]


def _markdown_cells(line: str) -> List[str]:
    stripped = line.strip()
    if not (stripped.startswith("|") and stripped.endswith("|")):
        return []
    return [cell.strip() for cell in stripped[1:-1].split("|")]


def _build_reference_constants_artifact(
    state: _L1State,
    free_energy_card_path: Path,
) -> Optional[tuple[Path, str]]:
    """Persist a compact evidence table from included LC2 species rows.

    The artifact deliberately copies card values without chemically renaming
    them.  In particular, ``log_beta`` is exposed as the card field; whether a
    protonation row is also a pKa follows from that row's reaction convention,
    not from this renderer.
    """

    card = Path(free_energy_card_path)
    if not card.is_file():
        return None
    lines = card.read_text(encoding="utf-8", errors="replace").splitlines()
    selected_columns = (
        "species_id",
        "label",
        "phase",
        "log_beta",
        "stoich",
        "source",
        "include",
    )
    rows: List[List[str]] = []
    index = 0
    while index < len(lines):
        header = _markdown_cells(lines[index])
        normalized = [cell.casefold() for cell in header]
        if not set(selected_columns).issubset(normalized):
            index += 1
            continue
        positions = {name: normalized.index(name) for name in selected_columns}
        index += 2  # skip the Markdown alignment row
        while index < len(lines):
            cells = _markdown_cells(lines[index])
            if not cells:
                break
            if len(cells) <= max(positions.values()):
                index += 1
                continue
            if cells[positions["include"]].strip().casefold() == "true":
                rows.append([cells[positions[name]] for name in selected_columns])
            index += 1
        continue

    if not rows:
        return None

    artifact_path = Path(state.call_dir) / "thermodynamic_reference_constants.md"
    rendered = [
        "# Deterministic thermodynamic reference constants",
        "",
        f"- Source card: `{_rel_to_session(card)}`",
        "- Selection: species rows whose final LC2 `include` field is `true`.",
        "- Reaction convention: the source card defines `log_beta` as the "
        "cumulative formation constant from free components; each row below "
        "reports its `stoich` reaction basis and product species. For a "
        "protonated ligand, the card convention is `x H+ + L <=> HxL`. Only "
        "the `x = 1` single-protonation value is directly the conjugate-acid "
        "pKa; higher `x` values are cumulative protonation constants.",
        "- Interpretation: values and source are copied exactly. Do not rename "
        "a generic `log_beta` as a pKa, dissolution constant, or another named "
        "constant unless that row's reaction/species definition supports it.",
        "",
        "| species_id | product label | phase | log_beta | reaction basis (stoich) | source | include |",
        "|---|---|---|---:|---|---|---|",
    ]
    for row in rows:
        escaped = [cell.replace("|", "\\|") for cell in row]
        rendered.append("| " + " | ".join(escaped) + " |")
    text = "\n".join(rendered) + "\n"
    if len(text) > _REFERENCE_CONSTANTS_MAX_CHARS:
        text = (
            text[:_REFERENCE_CONSTANTS_MAX_CHARS]
            + "\n\n_(reference table capped; open the source card for the "
            "remaining included rows)_\n"
        )
    artifact_path.write_text(text, encoding="utf-8")
    return artifact_path, text


def _api_error_fallback_text(text: str) -> str:
    """Build the deterministic fallback used only after prompt rejection."""

    keep = _VERDICT_FALLBACK_HEAD_CHARS + _VERDICT_FALLBACK_TAIL_CHARS
    if len(text) <= keep:
        return text
    omitted = len(text) - keep
    return (
        text[:_VERDICT_FALLBACK_HEAD_CHARS]
        + "\n\n"
        + f"[... {omitted} characters omitted only because Argo rejected "
          "the full verdict prompt; use inspect_verdict_section for the "
          "persisted section ...]"
        + "\n\n"
        + text[-_VERDICT_FALLBACK_TAIL_CHARS:]
    )


def _render_pipeline_result(
    state: _L1State,
    status: Dict[str, Any],
    *,
    already_ran: bool = False,
) -> str:
    """Render status plus automatically supplied deterministic verdict text."""

    payload = dict(status)
    payload["default_verdict_count"] = len(state.default_verdicts)
    payload["default_verdict_paths"] = [
        _rel_to_session(path) for path, _text in state.default_verdicts
    ]
    payload["default_verdict_delivery"] = (
        "full_untruncated"
        if state.verdict_delivery_mode == "full"
        else "truncated_after_argo_prompt_rejection"
    )
    payload["default_reference_constants_path"] = (
        _rel_to_session(state.default_reference_constants[0])
        if state.default_reference_constants is not None
        else None
    )
    if already_ran:
        payload["already_ran"] = True
        payload["note"] = (
            "Pipeline already completed for this call; outputs are unchanged. "
            "The deterministic verdict is supplied again below."
        )

    parts = [json.dumps(payload, indent=2, default=str)]
    method = canonical_method(str(payload.get("sweep_method") or ""))
    if method is not None and method in state.briefed_methods:
        parts.append(
            f"[METHOD BRIEFING — {method}] is already part of your system "
            "instructions; its verdict schema and reading hints apply to "
            "the evidence below."
        )
    else:
        briefing = render_method_briefing(
            str(payload.get("sweep_method") or "")
        )
        if briefing is not None:
            parts.append(briefing)
    if state.default_reference_constants is not None:
        reference_path, reference_text = state.default_reference_constants
        parts.append(
            "\n".join([
                "[DEFAULT THERMODYNAMIC REFERENCE CONSTANTS — FULL TEXT]",
                f"Artifact path: `{_rel_to_session(reference_path)}`",
                "This deterministic LC2-card projection is already-opened "
                "evidence for constants quoted in the analysis:",
                "------------------------------------------------------------",
                reference_text,
                "------------------------------------------------------------",
                "[END DEFAULT THERMODYNAMIC REFERENCE CONSTANTS]",
            ])
        )
    if not state.default_verdicts:
        parts.append(
            "[DEFAULT SOLVER VERDICT]\n"
            "No *_verdict.md artifact was returned by the solver. Do not "
            "substitute a raw topology JSON dump for this missing contract."
        )
        return "\n\n".join(parts)

    for path, full_text in state.default_verdicts:
        delivered = (
            full_text
            if state.verdict_delivery_mode == "full"
            else _api_error_fallback_text(full_text)
        )
        mode = (
            "FULL UTF-8 TEXT; NOT TRUNCATED"
            if state.verdict_delivery_mode == "full"
            else "API-ERROR FALLBACK; ON-DISK FILE REMAINS COMPLETE"
        )
        parts.append(
            "\n".join([
                f"[DEFAULT SOLVER VERDICT — {mode}]",
                f"Artifact path: `{_rel_to_session(path)}`",
                "The following deterministic solver verdict is already-opened "
                "evidence; no read tool call is required:",
                "------------------------------------------------------------",
                delivered,
                "------------------------------------------------------------",
                "[END DEFAULT SOLVER VERDICT]",
            ])
        )
    return "\n\n".join(parts)


def _make_list_outputs(state: _L1State) -> Callable[[], str]:
    def list_outputs() -> str:
        """List the solver output files produced for this call.

        Returns a markdown bullet list of relative paths + byte sizes.
        Empty until ``run_analysis_pipeline`` has succeeded.
        """

        files = _list_solver_files(state)
        if state.default_reference_constants is not None:
            reference_path = state.default_reference_constants[0]
            if reference_path.is_file() and reference_path not in files:
                files = [reference_path, *files]
        if not files:
            return "_(no solver outputs yet — run the pipeline first)_"
        rows = [f"# Solver outputs ({len(files)} files)", ""]
        for path in files:
            rows.append(
                f"- `{_rel_to_session(path)}` ({path.stat().st_size} B)"
            )
        return "\n".join(rows)

    return list_outputs


def _make_read_output_file(state: _L1State) -> Callable[..., str]:
    def read_output_file(
        relative_path: str = "",
        max_chars: int = _READ_DEFAULT_MAX_CHARS,
    ) -> str:
        """Read one solver text output (CSV / markdown / card) as text.

        Args:
            relative_path: Path as shown by ``list_outputs`` (relative to
                the session root; forward slashes ok). A call-relative
                path is also accepted.
            max_chars: Truncate cap (default 8000, hard max 60000).

        Binary files (PNG/JPG/PDF) are not returned. Paths outside this
        call's directory are rejected.
        """

        rel = (relative_path or "").strip().replace("\\", "/").lstrip("/")
        if not rel:
            return "_(empty path)_"
        target = _resolve_call_file(state, relative_path)
        if target is None:
            return f"_(no such file: '{relative_path}')_"
        if target.suffix.lower() in {
            ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".bin",
        }:
            return (
                f"_(binary file '{relative_path}', "
                f"{target.stat().st_size} bytes — open it on disk)_"
            )
        lower_name = target.name.lower()
        if target.suffix.lower() == ".json" and (
            "topology" in lower_name
            or lower_name.endswith("_verdict.json")
        ):
            return (
                f"_(raw topology JSON is not returned to L1. Use "
                f"`inspect_topology_feature` with a canonical verdict ID; "
                f"use `inspect_verdict_section` for report text. File: "
                f"'{relative_path}')_"
            )
        cap = max(
            1,
            min(
                int(max_chars or _READ_DEFAULT_MAX_CHARS),
                _READ_HARD_MAX_CHARS,
            ),
        )
        text = target.read_text(encoding="utf-8", errors="replace")
        truncated = len(text) > cap
        header = (
            f"# `{rel}` ({target.stat().st_size} B"
            + (f", first {cap} chars" if truncated else "")
            + ")\n\n"
        )
        return header + text[:cap] + ("\n\n_(truncated)_" if truncated else "")

    return read_output_file


def _make_inspect_verdict_section(state: _L1State) -> Callable[..., str]:
    def inspect_verdict_section(
        relative_path: str = "",
        section: str = "",
        max_chars: int = _READ_HARD_MAX_CHARS,
    ) -> str:
        """Read one named Markdown section from a persisted solver verdict.

        Omit ``section`` to list the available headings. If exactly one
        verdict exists, ``relative_path`` may be omitted.
        """

        target: Optional[Path]
        if relative_path.strip():
            target = _resolve_call_file(state, relative_path)
        else:
            candidates = [
                path for path, _text in state.default_verdicts
                if path.exists() and path.suffix.lower() == ".md"
            ]
            if len(candidates) != 1:
                shown = ", ".join(_rel_to_session(path) for path in candidates)
                return (
                    "_(relative_path is required when the run has "
                    f"{len(candidates)} verdicts: {shown or 'none'})_"
                )
            target = candidates[0]
        if target is None or not target.is_file():
            return f"_(no such verdict file: '{relative_path}')_"
        if (
            target.suffix.lower() != ".md"
            or not target.name.lower().endswith("verdict.md")
        ):
            return f"_(not a solver verdict Markdown file: '{relative_path}')_"

        text = target.read_text(encoding="utf-8", errors="replace")
        matches = list(re.finditer(r"(?m)^(#{1,6})[ \t]+(.+?)[ \t]*$", text))
        query = (section or "").strip().lstrip("#").strip().casefold()
        if not query:
            headings = [
                f"- {'#' * len(match.group(1))} {match.group(2).strip()}"
                for match in matches
            ]
            return (
                f"# Verdict sections in `{_rel_to_session(target)}`\n\n"
                + ("\n".join(headings) if headings else "_(no Markdown headings)_")
            )

        selected = [
            match
            for match in matches
            if match.group(2).strip().casefold() == query
        ]
        if not selected:
            selected = [
                match
                for match in matches
                if query in match.group(2).strip().casefold()
            ]
        if len(selected) != 1:
            names = [match.group(2).strip() for match in selected]
            return (
                f"_(section query {section!r} matched {len(selected)} headings"
                + (f": {names}" if names else "")
                + ")_"
            )
        match = selected[0]
        level = len(match.group(1))
        end = len(text)
        start_index = matches.index(match)
        for following in matches[start_index + 1:]:
            if len(following.group(1)) <= level:
                end = following.start()
                break
        section_text = text[match.start():end].rstrip() + "\n"
        cap = max(
            1,
            min(
                int(max_chars or _READ_HARD_MAX_CHARS),
                _READ_HARD_MAX_CHARS,
            ),
        )
        truncated = len(section_text) > cap
        return (
            f"# `{_rel_to_session(target)}` — section "
            f"`{match.group(2).strip()}`\n\n"
            + section_text[:cap]
            + ("\n_(section truncated by explicit tool cap)_" if truncated else "")
        )

    return inspect_verdict_section


def _walk_records_with_id(
    value: Any,
    wanted: str,
    path: str = "$",
) -> List[tuple[str, Dict[str, Any]]]:
    hits: List[tuple[str, Dict[str, Any]]] = []
    if isinstance(value, dict):
        if str(value.get("id", "")) == wanted:
            hits.append((path, value))
        for key, child in value.items():
            hits.extend(_walk_records_with_id(child, wanted, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(_walk_records_with_id(child, wanted, f"{path}[{index}]"))
    return hits


_CANONICAL_ID_FAMILIES = (
    ("Dms_", "dominant species"),
    ("DmsReg_", "regions"),
    ("DmsRegEq_", "boundary manifolds"),
    ("DmsRegEqJnc_", "junction features"),
)
_CANONICAL_ID_HINT = (
    "Valid `feature_id` values are the canonical prefixed IDs printed in "
    "`*_verdict.md` — families `Dms_i` (dominant species), `DmsReg_i` "
    "(regions), `DmsRegEq_i` (boundary manifolds), `DmsRegEqJnc_i` "
    "(junction features). The `topo_csv_*` feature CSVs use the same "
    "canonical IDs in their `id` columns; their `source_id` columns are "
    "solver-internal and not accepted here."
)


def _unresolved_feature_id_hint(
    wanted: str,
    documents: List[tuple[Path, Any]],
) -> str:
    """Self-correction hint when a feature_id fails to resolve."""

    canonical_ids: List[str] = []
    by_source: Dict[str, List[str]] = {}
    for _path, document in documents:
        mapping = (
            document.get("source_mapping")
            if isinstance(document, dict)
            else None
        )
        if not isinstance(mapping, dict):
            continue
        for records in mapping.values():
            if not isinstance(records, dict):
                continue
            for canonical_id, record in records.items():
                canonical_ids.append(str(canonical_id))
                if isinstance(record, dict):
                    for key in ("source_id", "source_label_id"):
                        if key in record:
                            by_source.setdefault(
                                str(record[key]), []
                            ).append(str(canonical_id))
    parts = [_CANONICAL_ID_HINT]
    translations = sorted(set(by_source.get(wanted, [])))
    if translations:
        parts.append(
            f"Solver-internal id {wanted!r} corresponds to canonical "
            f"{translations}; retry with that canonical ID."
        )
    if canonical_ids:
        roster: List[str] = []
        unique_ids = set(canonical_ids)
        for prefix, label in _CANONICAL_ID_FAMILIES:
            family = sorted(
                (cid for cid in unique_ids if cid.startswith(prefix)),
                key=lambda cid: (
                    int(cid.rsplit("_", 1)[-1])
                    if cid.rsplit("_", 1)[-1].isdigit()
                    else -1
                ),
            )
            if family:
                span = (
                    family[0]
                    if len(family) == 1
                    else f"{family[0]}..{family[-1]}"
                )
                roster.append(f"{len(family)} {label} ({span})")
        if roster:
            parts.append("Available here: " + "; ".join(roster) + ".")
    else:
        parts.append(
            "Re-read the verdict (`inspect_verdict_section`) to copy an "
            "exact ID from its topology tables."
        )
    return " ".join(parts)


def _verdict_sidecar_candidates(
    state: _L1State,
    relative_path: str,
) -> List[Path]:
    if relative_path.strip():
        target = _resolve_call_file(state, relative_path)
        if target is None:
            return []
        lower = target.name.lower()
        if lower.endswith("_verdict.json"):
            return [target]
        if lower.endswith("_verdict.md"):
            sibling = target.with_suffix(".json")
            return [sibling] if sibling.is_file() else []
        if target.suffix.lower() == ".json" and lower.startswith("topology"):
            sibling = target.with_name(f"{target.stem}_verdict.json")
            return [sibling] if sibling.is_file() else []
        return []
    if state.solver_dir is None or not state.solver_dir.exists():
        return []
    return sorted(state.solver_dir.rglob("*_verdict.json"))


def _make_inspect_topology_feature(state: _L1State) -> Callable[..., str]:
    def inspect_topology_feature(
        feature_id: str = "",
        relative_path: str = "",
    ) -> str:
        """Inspect exactly one canonical topology record from a verdict sidecar.

        ``feature_id`` is a canonical ID printed in ``*_verdict.md`` (for
        example ``DmsReg_2``, ``DmsRegEq_4``, or ``DmsRegEqJnc_1``); the
        ``topo_csv_*`` feature CSVs carry the same IDs in their ``id``
        columns. The tool parses normalized JSON server-side and returns
        only that record, never the complete raw topology document.
        """

        wanted = (feature_id or "").strip()
        if not wanted:
            return (
                "_(feature_id is required; copy one canonical ID from the "
                f"verdict. {_CANONICAL_ID_HINT})_"
            )
        candidates = _verdict_sidecar_candidates(state, relative_path)
        if not candidates:
            return (
                "_(no normalized *_verdict.json sidecar found; supply the "
                "verdict Markdown, verdict sidecar, or matching topology path)_"
            )

        documents: List[tuple[Path, Any]] = []
        errors: List[str] = []
        for candidate in candidates:
            try:
                documents.append(
                    (
                        candidate,
                        json.loads(candidate.read_text(encoding="utf-8")),
                    )
                )
            except Exception as exc:
                errors.append(
                    f"{_rel_to_session(candidate)}: {type(exc).__name__}: {exc}"
                )

        all_hits: List[tuple[Path, str, Dict[str, Any]]] = []
        for candidate, document in documents:
            for record_path, record in _walk_records_with_id(document, wanted):
                all_hits.append((candidate, record_path, record))
        if not all_hits:
            detail = f" Parse errors: {errors}." if errors else ""
            return (
                f"_(canonical ID {wanted!r} resolved to 0 records.{detail} "
                + _unresolved_feature_id_hint(wanted, documents)
                + ")_"
            )
        if len(all_hits) > 1:
            locations = [
                f"{_rel_to_session(path)}:{record_path}"
                for path, record_path, _record in all_hits
            ]
            detail = f" Matches: {locations}."
            if errors:
                detail += f" Parse errors: {errors}."
            return (
                f"_(canonical ID {wanted!r} resolved to {len(all_hits)} records."
                f"{detail} Supply relative_path when multiple element verdicts "
                "reuse the same canonical namespace.)_"
            )

        sidecar, record_path, record = all_hits[0]
        return (
            f"# Topology feature `{wanted}`\n\n"
            f"- Normalized sidecar: `{_rel_to_session(sidecar)}`\n"
            f"- Record location: `{record_path}`\n"
            "- Scope: this canonical record only; the raw topology JSON was "
            "not placed in model context.\n\n"
            "```json\n"
            + json.dumps(record, indent=2, ensure_ascii=False, default=str)
            + "\n```"
        )

    return inspect_topology_feature


__all__ = [
    "_build_reference_constants_artifact",
    "_collect_default_verdicts",
    "_make_inspect_topology_feature",
    "_make_inspect_verdict_section",
    "_make_list_outputs",
    "_make_read_output_file",
    "_render_pipeline_result",
]
