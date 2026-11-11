"""Apply a source-backed LC1 revision without repeating unaffected LC2 reviews.

The source compiler supplies before/after reference cards. This module never
accepts model-authored energies. It computes their deterministic delta, retains
the existing merged reference frame, and invalidates decisions by group content.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import copy
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from .contracts import BroaderReviewRequired, SourceRepairRequired, canonical_sha256


def _path(value: Any) -> Path:
    path = Path(value).absolute()
    text = str(path)
    if os.name == "nt" and not text.startswith("\\\\?\\"):
        text = "\\\\?\\UNC\\" + text[2:] if text.startswith("\\\\") else "\\\\?\\" + text
    return Path(text)


def _read(path: Any) -> str:
    return _path(path).read_text(encoding="utf-8-sig")


def _write(path: Any, text: str) -> None:
    _path(path).parent.mkdir(parents=True, exist_ok=True)
    _path(path).write_text(text, encoding="utf-8")


def _json(path: Any) -> Any:
    return json.loads(_read(path))


def _receipt(path: Any) -> dict[str, Any]:
    data = _path(path).read_bytes()
    return {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def _cells(line: str) -> list[str]:
    return [item.strip() for item in line.strip().strip("|").split("|")]


def _section(text: str, number: str) -> str:
    match = re.search(r"(?m)^#{2,3}\s+" + re.escape(number) + r"\.?(?:\s|$)", text)
    if not match:
        return ""
    end = re.search(r"(?m)^#{2,3}\s+\d", text[match.end():])
    return text[match.start():match.end() + end.start()] if end else text[match.start():]


def _source(row: Mapping[str, str]) -> str:
    value = row.get("source", "") or row.get("calc_source", "")
    return value if value in {"Atlas", "CRC", "SRD46 query estimated values"} else "SRD-46"


@dataclass(frozen=True)
class CardRow:
    index: int
    headers: tuple[str, ...]
    cells: tuple[str, ...]
    section: str

    @property
    def data(self) -> dict[str, str]:
        return dict(zip(self.headers, self.cells))

    @property
    def key(self) -> tuple[str, str, str]:
        value = self.data
        # A canonical species_id encodes composition, not phase identity:
        # native Atlas oxide/hydroxide alternatives can share it. The native
        # dedup/card editor selects source-qualified labels; retain phase too.
        return value.get("phase", self.section), value["label"], _source(value)


def _rows(text: str) -> list[CardRow]:
    rows: list[CardRow] = []
    headers: tuple[str, ...] = ()
    section = ""
    for index, line in enumerate(text.splitlines(keepends=True)):
        heading = re.match(r"^#{2,3}\s+(\d+(?:\.\d+)?)\b", line)
        if heading:
            section = heading[1]
            headers = ()
        if not section.startswith("5.") or section == "5.4":
            continue
        if not line.lstrip().startswith("|"):
            if not line.strip() or line.startswith("#"):
                headers = ()
            continue
        cells = tuple(_cells(line))
        if "species_id" in cells and "include" in cells:
            headers = cells
            continue
        if not headers or all(re.fullmatch(r"[-: ]+", c) for c in cells):
            continue
        if len(cells) != len(headers):
            raise BroaderReviewRequired("Cannot patch an irregular species table", line=index + 1)
        rows.append(CardRow(index, headers, cells, section))
    keys = [row.key for row in rows]
    # Native inclusion edits use (label, source) without phase. Refuse truly
    # ambiguous editor identities, including one label reused across phases.
    editor_keys = [(row.data["label"], _source(row.data)) for row in rows]
    if len(keys) != len(set(keys)) or len(editor_keys) != len(set(editor_keys)):
        raise BroaderReviewRequired("Source-qualified species labels are ambiguous in the source card")
    if not rows:
        raise BroaderReviewRequired("No native species tables were found")
    return rows


def _scientific(row: CardRow) -> dict[str, str]:
    return {k: v for k, v in row.data.items() if k not in {"include", "additional_notes"}}


def _number(value: str, field: str) -> Decimal:
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise BroaderReviewRequired("Non-numeric compiled field", field=field, value=value) from exc
    if not result.is_finite():
        raise BroaderReviewRequired("Non-finite compiled field", field=field)
    return result


def _reference_offsets(before: str, baseline: str) -> dict[str, Decimal]:
    def parse(text: str) -> dict[str, Decimal]:
        header: list[str] = []
        result = {}
        for line in _section(text, "3.1").splitlines():
            if not line.startswith("|"):
                continue
            cells = _cells(line)
            if "component_id" in cells:
                header = cells
            elif header and len(cells) == len(header) and not cells[0].startswith("-"):
                row = dict(zip(header, cells))
                result[row["component_id"]] = _number(row["mu0_ref_kJ"], "mu0_ref_kJ")
        return result
    old, merged = parse(before), parse(baseline)
    if not old or set(old) != set(merged):
        raise BroaderReviewRequired("Merged component references differ from the compiled source basis")
    return {key: merged[key] - old[key] for key in old}


def _offset(stoich: str, offsets: Mapping[str, Decimal]) -> Decimal:
    from LC2_free_energy_card_building.LC2_2_card_db_merger._md_card_merge_core.reference_alignment import _parse_stoich
    total = Decimal(0)
    terms = _parse_stoich(stoich)
    if not terms:
        if stoich.strip() in {"—", "-", ""}:
            return total
        raise BroaderReviewRequired("Cannot prove the reference offset for a new row", stoich=stoich)
    for name, count in terms.items():
        if name in {"H", "H2O"}:
            continue
        if name not in offsets:
            raise BroaderReviewRequired("New row requires an unbound reference component", component=name)
        total += Decimal(str(count)) * offsets[name]
    return total


def apply_compiled_delta(*, baseline_text: str, before_reference_text: str,
                         after_reference_text: str) -> tuple[str, dict[str, Any]]:
    """Splice compiler-produced changes into a merged card; never infer new μ.

    Before/after cards must use the same global component and reference basis.
    Existing Atlas/CRC rows and unrelated literal lines are kept byte-for-byte.
    Removing an existing species or changing the global basis requires broader
    review rather than a hidden scope reduction.
    """
    for number in ("2", "2.1", "2.2", "2.3", "2.4", "2.5", "3", "3.1", "3.2", "4.1", "5.4"):
        if _section(before_reference_text, number) != _section(after_reference_text, number):
            raise BroaderReviewRequired("Repair changes the model basis or global settings", section=number)
    old = {row.key: row for row in _rows(before_reference_text)}
    new = {row.key: row for row in _rows(after_reference_text)}
    merged = {row.key: row for row in _rows(baseline_text)}
    removed = sorted(set(old) - set(new))
    if removed:
        raise BroaderReviewRequired("Repair removes existing species; explicit wider coverage review required", removed=removed)
    changed = {key for key in set(old) & set(new) if _scientific(old[key]) != _scientific(new[key])}
    added = set(new) - set(old)
    offsets = _reference_offsets(before_reference_text, baseline_text)
    lines = baseline_text.splitlines(keepends=True)
    changes = []
    additions: dict[str, list[tuple[CardRow, dict[str, str]]]] = {}
    for key in sorted(changed | added):
        after = new[key]
        values = after.data
        if _source(values) != "SRD-46":
            raise BroaderReviewRequired("Local source repair cannot alter external or estimated rows", key=key)
        existing = merged.get(key)
        if key in changed and existing is None:
            raise BroaderReviewRequired("Changed source row cannot be located uniquely in merged card", key=key)
        offset = _offset(values.get("stoich", ""), offsets)
        if existing:
            before = old[key].data
            current = existing.data
            # Prevent a stale baseline or already edited numeric row being silently patched.
            for field in ("log_beta", "mu0_free_kJ", "mu0_canon_kJ"):
                expected = _number(before[field], field) + (offset if field.startswith("mu0_") else 0)
                if abs(_number(current[field], field) - expected) > Decimal("0.0002"):
                    raise BroaderReviewRequired("Existing energy row is not in the declared source/reference frame", key=key, field=field)
            for field in ("charge", "stoich", "phase"):
                if current.get(field) != before.get(field):
                    raise BroaderReviewRequired("Existing row chemistry differs from its source snapshot", key=key, field=field)
            output = dict(current)
            for field in values:
                if field in output and field not in {"include", "additional_notes", "source"}:
                    output[field] = values[field]
            for field in ("mu0_free_kJ", "mu0_canon_kJ"):
                output[field] = f"{_number(values[field], field) + offset:+.4f}"
            # This is the original pre-dedup baseline. Its false flags are
            # source/scope exclusions, not the prior review's decisions.
            output["include"] = current["include"]
            output["additional_notes"] = values.get("additional_notes", "")
            lines[existing.index] = "| " + " | ".join(output.get(h, "") for h in existing.headers) + " |\n"
        else:
            output = dict(values)
            for field in ("mu0_free_kJ", "mu0_canon_kJ"):
                output[field] = f"{_number(values[field], field) + offset:+.4f}"
            output["include"] = values["include"]
            additions.setdefault(after.section, []).append((after, output))
        changes.append({"key": list(key), "operation": "add" if key in added else "replace",
                        "before": old[key].data if key in old else None, "after": output})
    for section, pending in sorted(additions.items(), reverse=True):
        targets = [row for row in merged.values() if row.section == section]
        if not targets:
            raise BroaderReviewRequired("New phase table requires broader review", section=section)
        target = max(targets, key=lambda row: row.index)
        extra = []
        for _, values in pending:
            values.setdefault("source", "SRD-46")
            extra.append("| " + " | ".join(values.get(h, "") for h in target.headers) + " |\n")
        lines[target.index] += "".join(extra)
    candidate = "".join(lines)
    old_conditions, new_conditions = _section(before_reference_text, "4.2"), _section(after_reference_text, "4.2")
    if old_conditions != new_conditions:
        if not old_conditions or candidate.count(old_conditions) != 1:
            raise BroaderReviewRequired("Cannot bind the changed pair-condition provenance table")
        candidate = candidate.replace(old_conditions, new_conditions, 1)
    return candidate, {"schema_version": 1, "row_key_fields": ["phase", "label", "source"], "changes": changes,
                       "baseline_sha256": hashlib.sha256(baseline_text.encode()).hexdigest(),
                       "before_compiler_sha256": hashlib.sha256(before_reference_text.encode()).hexdigest(),
                       "after_compiler_sha256": hashlib.sha256(after_reference_text.encode()).hexdigest(),
                       "candidate_sha256": hashlib.sha256(candidate.encode()).hexdigest()}


def decision_delta(*, old_inventory: Sequence[Mapping[str, Any]],
                   new_inventory: Sequence[Mapping[str, Any]],
                   decisions: Sequence[Mapping[str, Any]],
                   overrides: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Content-sensitive reuse, including excluded peers of a changed candidate."""
    def group(row):
        return str(row["phase"]), str(row["core_label"])
    def fingerprint(row):
        return canonical_sha256({key: value for key, value in row.items()
                                 if key not in {"original_include", "include", "current_include"}})
    old = {str(row["entry_key"]): row for row in old_inventory}
    new = {str(row["entry_key"]): row for row in new_inventory}
    touched = {group(row) for key, row in old.items()
               if key not in new or fingerprint(row) != fingerprint(new[key])}
    touched |= {group(row) for key, row in new.items()
                if key not in old or fingerprint(row) != fingerprint(old[key])}
    # A source change can affect an element-level phase-family decision beyond its
    # immediate duplicate group. Include those existing peers, not unrelated elements.
    families = {(element, row.get("phase_family")) for row in [*old.values(), *new.values()]
                if group(row) in touched for element in row.get("elements", [])
                if row.get("phase_family")}
    touched |= {group(row) for row in new.values() if any(
        (element, row.get("phase_family")) in families for element in row.get("elements", []))}
    retained = [dict(row) for row in decisions if group(row) not in touched]
    discarded = [dict(row) for row in decisions if group(row) in touched]
    retained_overrides, invalidated_overrides = {}, {}
    for key, value in (overrides or {}).items():
        row = new.get(key)
        if row is not None and group(row) not in touched:
            retained_overrides[key] = value
        else:
            invalidated_overrides[key] = value
    return {"touched_groups": [list(key) for key in sorted(touched)],
            "retained_decisions": retained, "invalidated_decisions": discarded,
            "retained_overrides": retained_overrides, "invalidated_overrides": invalidated_overrides,
            "pending_entry_keys": sorted(key for key, row in new.items() if group(row) in touched)}


def _native_inventory(card_text: str, system_name: str):
    from LC2_free_energy_card_building.LC2_2_card_db_merger._md_card_merge_core.reference_alignment import _parse_stoich
    from LC2_free_energy_card_building.LC2_2_card_db_merger._md_card_merge_core.species_unifier import (
        UnifiedSpecies, group_by_core, _normalise_stoich, _phase_bucket,
    )
    from LC2_free_energy_card_building.LC2_2_card_db_merger._md_card_merge_core.species_dedup_report_writer import generate_dedup_markdown
    from LC2_free_energy_card_building.LC2_2_card_db_merger.element_inventory import build_element_inventory
    from card_management_helpers.free_energy_md_card_reader import parse_free_energy_card_md
    from card_management_helpers.dedup_md_card_reader import parse_dedup_markdown
    parsed = parse_free_energy_card_md(card_text)
    elements = {}
    for cm in parsed.component_meta:
        if cm.comp_type == "metal":
            match = re.match(r"\[?([A-Z][a-z]?)", cm.name)
            if match and match[1] != "H":
                elements[cm.internal_id] = match[1]
    unified = []
    for row in _rows(card_text):
        data = row.data
        stoich = _parse_stoich(data["stoich"])
        core, mult = _normalise_stoich(stoich)
        unified.append(UnifiedSpecies(
            name=data["label"], source=_source(data), phase=_phase_bucket(data["phase"]),
            charge=int(data["charge"]), mu_aligned_kJ=float(data["mu0_canon_kJ"]),
            raw_stoich=stoich, core_stoich=core, multiplier=mult,
            elements=tuple(sorted({elements[key] for key in stoich if elements.get(key)})),
            extra={"species_id": data["species_id"], "source_chain": data.get("calc_source", "")},
        ))
    grouped = group_by_core(unified)
    text = generate_dedup_markdown(system_name, grouped, {}, [], {})
    inventory = build_element_inventory(grouped, merged_card_text=card_text, valence_table=[])
    return parse_dedup_markdown(text), inventory, text


def _inventory_data(inventory, card_text):
    from dataclasses import asdict
    source_hashes = {(row.data["label"], _source(row.data)): canonical_sha256(_scientific(row))
                     for row in _rows(card_text)}
    return [asdict(row) | {"evidence_sha256": source_hashes.get((row.label, row.source))}
            for row in inventory]


def _bound_json(receipt: Mapping[str, Any]) -> dict[str, Any]:
    current = _receipt(receipt["path"])
    if receipt.get("sha256") and current["sha256"] != receipt["sha256"]:
        raise BroaderReviewRequired("An accepted decision artifact changed", path=receipt["path"])
    return _json(receipt["path"])


def _load_overlay(lc2_3: Mapping[str, Any]) -> dict[str, Any]:
    direct = lc2_3.get("accepted_decision_overlay_path")
    if direct and _path(direct).is_file():
        expected = lc2_3.get("accepted_decision_overlay_sha256")
        if expected and _receipt(direct)["sha256"] != expected:
            raise BroaderReviewRequired("Accepted decision overlay changed", path=direct)
        overlay = _json(direct)
        accepted_hash = overlay.get("accepted_card_sha256") or (overlay.get("accepted_card") or {}).get("sha256")
        accepted_path = lc2_3.get("enriched_card_path") or (overlay.get("accepted_card") or {}).get("path")
        if accepted_hash and (not accepted_path or _receipt(accepted_path)["sha256"] != accepted_hash):
            raise BroaderReviewRequired("Accepted reviewed card changed", path=accepted_path)
        return overlay
    manifest = _json(lc2_3["manifest_path"])
    if not (manifest.get("commit") or {}).get("completed"):
        raise BroaderReviewRequired("Previous deduplication was not accepted")
    decisions, overrides, last_generation = [], {}, None
    for step in manifest.get("state_transitions", []):
        kind = step["kind"]
        if kind in {"initial_dedup_generation", "full_dedup_restart"}:
            generation = _bound_json(step["generation_manifest"])
            decisions = generation["decisions"]
            overrides = {}
            last_generation = Path(step["generation_manifest"]["path"]).parent
        elif kind == "targeted_redispatch":
            target = _bound_json(step["target_manifest"])
            generation = _json(target["generation_manifest"])
            replacements = {(d["phase"], d["core_label"]) for d in generation["decisions"]}
            decisions = [d for d in decisions if (d["phase"], d["core_label"]) not in replacements] + generation["decisions"]
        elif kind == "direct_entry_override":
            action = _bound_json(step["action_artifact"])["accepted_action"]
            overrides[action["entry_key"]] = [action["include"], action["reason"]]
    if last_generation is None:
        raise BroaderReviewRequired("Previous decision history lacks an accepted generation")
    return {"decisions": decisions, "overrides": overrides,
            "element_instructions": _json(last_generation / "element_instructions.json"),
            "plan": _read(last_generation / "plan_supplied_to_workers.md"),
            "case_recommendations": _read(last_generation / "case_recommendations.md"),
            "reconstructed_from": _receipt(lc2_3["manifest_path"])}


def _selection(result: Mapping[str, Any]) -> dict[str, Any]:
    path = result.get("eq_map_card_path") or (result.get("lc1_2") or {}).get("eq_map_card_path")
    if not path:
        raise BroaderReviewRequired("LC1 result does not identify its exact source selection")
    return _json(path)


def _pair_key(row: Mapping[str, Any]) -> str:
    return f"metal_{int(row['metal_id'])}_ligand_{int(row['ligand_id'])}"


def _compile_changed_sources(previous_lc2, previous_lc1, revised_lc1, output_dir):
    from LC1_SRD46_eq_card_alignment.source_repair import compile_repaired_pairs
    from LC2_free_energy_card_building.LC2_1_card_initializer.ref_eq_SRD46_md_cards_merger.ref_eq_SRD46_cards_merger import merge_ref_cards
    before, after = _selection(previous_lc1), _selection(revised_lc1)
    old = {_pair_key(row): row for row in before.get("equilibrium_networks", [])}
    new = {_pair_key(row): row for row in after.get("equilibrium_networks", [])}
    if set(old) != set(new):
        raise BroaderReviewRequired("Local repair changes the selected metal/ligand coverage")
    def selection(row):
        return {key: row.get(key) for key in ("eq_network", "source_selection", "temperature", "ionic_strength")} | {
            "patches": (row.get("patch_notes") or {}).get("patches", [])}
    changed = sorted(key for key in old if canonical_sha256(selection(old[key])) != canonical_sha256(selection(new[key])))
    if not changed:
        raise BroaderReviewRequired("LC1 revision contains no changed source selection")
    for key in changed:
        if int(new[key]["metal_id"]) == 68 or int(new[key]["ligand_id"]) == 10076:
            raise BroaderReviewRequired("Auxiliary protonation/hydrolysis source changes require dependent-pair review", pair_key=key)
        source = new[key].get("source_selection") or {}
        if not source.get("vlm_ids") or not source.get("source_rows") or not source.get("sha256"):
            raise BroaderReviewRequired("Revised pair lacks its exact source-selection receipt", pair_key=key)
    if previous_lc1.get("support_eq_map_path") or revised_lc1.get("support_eq_map_path"):
        raise BroaderReviewRequired("An estimated support overlay needs revalidation against the changed source selection")
    compiled = compile_repaired_pairs(after, changed, _path(output_dir) / "compiled_pairs",
                                      chemical_system=revised_lc1.get("chemical_system"))
    replacement = {item["pair_key"]: item for item in compiled}
    if set(replacement) != set(changed):
        raise BroaderReviewRequired("Scoped compiler did not return every changed pair")
    native = previous_lc2.get("lc2_1") or {}
    originals = native.get("ref_card_paths") or []
    if not originals:
        raise BroaderReviewRequired("Previous LC2 result has no immutable per-pair compiled sources")
    paths, replaced = [], set()
    for path in originals:
        match = re.search(r"metal_(\d+)_ligand_(\d+)", Path(path).name)
        key = f"metal_{match[1]}_ligand_{match[2]}" if match else None
        if key in replacement:
            if key in replaced:
                raise BroaderReviewRequired("One pair has multiple source cards; local replacement is ambiguous", pair_key=key)
            paths.append(replacement[key]["md_path"])
            replaced.add(key)
        else:
            paths.append(path)
    if replaced != set(changed):
        raise BroaderReviewRequired("A changed source card was absent from the original compilation")
    # Reassembly is deterministic and reads the unchanged saved pair cards; it
    # does not regenerate LC2 instructions, call the archive merger, or models.
    updated, _, collisions = merge_ref_cards(paths, system_name=native.get("system_name", "LC2 system"))
    output = _path(output_dir) / "recompiled_reference_card.md"
    _write(output, updated)
    receipt = {"changed_pairs": changed, "source_compilations": compiled,
               "ref_card_paths": [str(p) for p in paths],
               "unchanged_source_cards": [_receipt(p) for p in originals if p in paths],
               "srd_srd_collisions": collisions, "reference_card": _receipt(output)}
    return _read(native["merged_card_path"]), updated, receipt


def repair_existing_card(*, baseline_card_path, before_reference_text, after_reference_text,
                         accepted_overlay, output_dir, system_name="LC2 system", debug=False):
    """Review only source-affected groups, then validate the entire resulting card."""
    from LC2_free_energy_card_building.LC2_3_card_deduplicator.lc2_3_dedup_agent import _run_dedup_pass, _subset_report
    from LC2_free_energy_card_building.LC2_3_card_deduplicator._element_dedup_orchestrator.review_report import materialize_review
    from LC2_free_energy_card_building.agent_context_artifacts import write_agent_context_index
    out = _path(output_dir)
    out.mkdir(parents=True, exist_ok=False)
    baseline = _read(baseline_card_path)
    expected_baseline = accepted_overlay.get("baseline_card_sha256") or (accepted_overlay.get("baseline_card") or {}).get("sha256")
    if expected_baseline and _receipt(baseline_card_path)["sha256"] != expected_baseline:
        raise BroaderReviewRequired("Accepted baseline hash does not match this card")
    candidate, delta = apply_compiled_delta(baseline_text=baseline, before_reference_text=before_reference_text,
                                          after_reference_text=after_reference_text)
    _, old_inventory, _ = _native_inventory(baseline, system_name)
    report, inventory, report_text = _native_inventory(candidate, system_name)
    covered = {(entry.label, entry.source) for entry in inventory}
    uncovered = [change["key"] for change in delta["changes"]
                 if (change["after"]["label"], _source(change["after"])) not in covered]
    if uncovered:
        raise BroaderReviewRequired("Source delta affects rows outside the metal review inventory", rows=uncovered)
    decision_changes = decision_delta(old_inventory=_inventory_data(old_inventory, baseline),
                                     new_inventory=_inventory_data(inventory, candidate),
                                     decisions=accepted_overlay["decisions"], overrides=accepted_overlay.get("overrides", {}))
    # Start from pre-dedup baseline, not the accepted card: previously dropped
    # peers are already present and eligible. Preserve source/scope exclusions.
    _write(out / "candidate_card.md", candidate)
    _write(out / "deduplication_check.md", report_text)
    _write(out / "element_inventory.json", json.dumps(_inventory_data(inventory, candidate), indent=2))
    _write(out / "source_delta.json", json.dumps(delta, indent=2, ensure_ascii=False))
    _write(out / "decision_delta.json", json.dumps(decision_changes, indent=2, ensure_ascii=False))
    _write(out / "previous_accepted_overlay.json", json.dumps(accepted_overlay, indent=2, ensure_ascii=False))
    touched = {tuple(group) for group in decision_changes["touched_groups"]}
    target_report = _subset_report(report, touched)
    returned = {"decisions": [], "failures": [], "agent_call_count": 0}
    if target_report.groups:
        guidance = "\n\n[Scoped source repair]\n" + json.dumps(delta, ensure_ascii=False) + (
            "\nThe source values changed. Reconsider every candidate in these groups, including formerly excluded rows. "
            "The requested chemistry, state, and accepted element instructions remain unchanged.")
        returned = _run_dedup_pass(report_obj=target_report, inventory=inventory,
                                  plan=accepted_overlay.get("plan", "") + guidance,
                                  element_instructions=accepted_overlay.get("element_instructions", {}),
                                  case_recommendations=accepted_overlay.get("case_recommendations", ""),
                                  generation_dir=out / "targeted_review", debug=debug)
    expected = {(g.phase, g.core_label) for g in target_report.groups}
    received = [(d["phase"], d["core_label"]) for d in returned["decisions"]]
    if returned["failures"] or len(received) != len(set(received)) or set(received) != expected:
        raise BroaderReviewRequired("Targeted review did not commit exactly one decision for every affected group",
                                    expected=sorted(expected), received=received, failures=returned["failures"])
    decisions = decision_changes["retained_decisions"] + returned["decisions"]
    overrides = decision_changes["retained_overrides"]
    materialized = materialize_review(original_card_text=candidate, report=report,
                                      decision_dicts=decisions, overrides=overrides, inventory=inventory)
    repaired = out / "free_energy_card_deduplicated.md"
    _write(repaired, materialized.card_text)
    context_path, context_md = write_agent_context_index(out)
    context = _json(context_path)
    if (context.get("agent_turn_count") != int(returned.get("agent_call_count", 0))
            or not context.get("all_context_bundles_complete")):
        raise BroaderReviewRequired("Scoped review provenance is incomplete", context_index=str(context_path))
    overlay = {**accepted_overlay, "decisions": decisions, "overrides": overrides,
               "baseline_card_sha256": _receipt(out / "candidate_card.md")["sha256"],
               "accepted_card_sha256": _receipt(repaired)["sha256"], "source_repair_pending": False,
               "baseline_card": _receipt(out / "candidate_card.md"), "accepted_card": _receipt(repaired)}
    overlay_path = out / "accepted_decision_overlay.json"
    _write(overlay_path, json.dumps(overlay, indent=2, ensure_ascii=False))
    return {"status": "ok", "enriched_card_path": str(repaired), "output_dir": str(out),
            "candidate_card_path": str(out / "candidate_card.md"),
            "element_inventory_path": str(out / "element_inventory.json"),
            "dedup_report_path": str(out / "deduplication_check.md"),
            "accepted_decision_overlay_path": str(overlay_path), "source_delta": delta,
            "accepted_decision_overlay_sha256": _receipt(overlay_path)["sha256"],
            "decision_delta": decision_changes, "agent_context": context,
            "agent_context_index_path": str(context_path), "agent_context_complete": True,
            "n_groups": len(report.groups), "n_decisions": len(decisions),
            "n_targeted_groups": len(expected), "final_committed": True}


def repair_lc2_from_delta(*, previous_lc2, previous_lc1, revised_lc1, diagnostic,
                          purpose, tasks, output_dir, debug=False):
    """Controller seam for a late source fault; early build faults use run_lc2."""
    out = _path(output_dir)
    out.mkdir(parents=True, exist_ok=False)
    result = {"status": "needs_broader_review", "output_dir": str(out), "purpose": purpose,
              "tasks": tasks, "final_card_path": None, "stages_run": [], "source_repair": diagnostic,
              "lc2_1": previous_lc2.get("lc2_1"), "lc2_2": previous_lc2.get("lc2_2"), "lc2_3": None, "lc2_4": None}
    try:
        previous_dedup = previous_lc2.get("lc2_3") or {}
        if not (previous_dedup.get("final_committed") or previous_dedup.get("source_repair_pending")):
            raise BroaderReviewRequired("Late delta repair requires an accepted prior deduplication")
        if purpose != previous_lc2.get("purpose") or tasks != previous_lc2.get("tasks"):
            raise BroaderReviewRequired("Source repair cannot change the original question or tasks")
        baseline = (previous_lc2.get("lc2_2") or {}).get("merged_card_path")
        if not baseline:
            raise BroaderReviewRequired("The accepted pre-deduplication baseline is unavailable")
        overlay = _load_overlay(previous_dedup)
        before, after, receipt = _compile_changed_sources(previous_lc2, previous_lc1, revised_lc1, out)
        _write(out / "source_compilation_receipt.json", json.dumps(receipt, indent=2, ensure_ascii=False))
        reviewed = repair_existing_card(baseline_card_path=baseline, before_reference_text=before,
                                        after_reference_text=after, accepted_overlay=overlay,
                                        output_dir=out / "LC2_3_delta", system_name=previous_lc2.get("system_name", "LC2 system"), debug=debug)
        result["lc2_3"] = reviewed
        result["lc2_1"] = {**previous_lc2["lc2_1"], "merged_card_path": receipt["reference_card"]["path"],
                            "ref_card_paths": receipt["ref_card_paths"], "output_dir": str(out),
                            "source_delta_compilation_receipt": str(out / "source_compilation_receipt.json")}
        result["lc2_2"] = {**previous_lc2["lc2_2"], "merged_card_path": reviewed["candidate_card_path"],
                            "element_inventory_path": reviewed["element_inventory_path"],
                            "dedup_report_path": reviewed["dedup_report_path"], "output_dir": str(out)}
        result["stages_run"].extend(["LC2_source_delta", "LC2_3_targeted"])
        from LC2_free_energy_card_building.LC2_4_card_validator.lc2_4_validator_agent import run_lc2_4
        validated = run_lc2_4(purpose=purpose, tasks=tasks, enriched_card_path=reviewed["enriched_card_path"],
                             output_dir=out / "LC2_4")
        result.update(status="ok", lc2_4=validated, final_card_path=validated["validated_card_path"])
        result["stages_run"].append("LC2_4")
    except SourceRepairRequired as exc:
        result["status"] = "needs_broader_review"
        result["source_repair"] = exc.as_dict()
        result["_error"] = str(exc)
    except Exception as exc:
        result["status"] = "error"
        result["_error"] = f"{type(exc).__name__}: {exc}"
        result["final_card_path"] = None
    _write(out / "summary" / "LC2_summary.json", json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return result
