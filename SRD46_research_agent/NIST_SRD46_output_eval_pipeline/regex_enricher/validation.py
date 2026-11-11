"""Validation reports for claim-annotation outputs."""

from __future__ import annotations

from pathlib import Path

from .regex_support_helpers.models import ClaimAnnotatedDocument


def write_validation(
	doc: ClaimAnnotatedDocument,
	model: str,
	question_id: str,
	batch: int,
	eval_root: str | Path,
) -> Path | None:
	"""Write ``validation_batch{N}.md`` for one run."""

	unsupported: list[dict[str, object]] = []
	total = 0

	for paragraph in doc.paragraphs:
		total += len(paragraph.claims)
		grounding_map = {grounded.claim_index: grounded for grounded in paragraph.grounded_claims}
		for claim_index, claim in enumerate(paragraph.claims):
			grounded = grounding_map.get(claim_index)
			support = grounded.support_class if grounded else "unsupported"
			if support == "unsupported":
				context_start = max(0, claim.start - 40)
				context_end = min(len(paragraph.text), claim.end + 40)
				unsupported.append(
					{
						"para": paragraph.paragraph_index,
						"type": claim.claim_type,
						"text": claim.text,
						"context": paragraph.text[context_start:context_end],
					}
				)

	if not unsupported:
		return None

	out_dir = Path(eval_root) / f"Model_{model}" / question_id
	out_dir.mkdir(parents=True, exist_ok=True)
	path = out_dir / f"validation_batch{batch}.md"

	lines = [
		f"# {question_id} - Validation (batch {batch})\n",
		f"**{len(unsupported)} of {total} claims unsupported**\n",
		"| # | Para | Type | Unsupported Claim | Context |",
		"|---|------|------|-------------------|---------|",
	]
	for index, item in enumerate(unsupported, start=1):
		text_escaped = str(item["text"]).replace("|", "\\|").replace("\n", " ")
		context_escaped = str(item["context"]).replace("|", "\\|").replace("\n", " ")
		lines.append(
			f"| {index} | {item['para']} | {item['type']} | {text_escaped} | ...{context_escaped}... |"
		)

	path.write_text("\n".join(lines), encoding="utf-8")
	return path


def write_validation_summary(model: str, eval_root: str | Path) -> Path | None:
	"""Aggregate all per-batch validation files into a model-level summary."""

	eval_dir = Path(eval_root) / f"Model_{model}"
	if not eval_dir.exists():
		return None

	entries: list[tuple[str, int, int, int]] = []
	import re

	for question_dir in sorted(eval_dir.iterdir()):
		if not question_dir.is_dir():
			continue
		for validation_file in sorted(question_dir.glob("validation_batch*.md")):
			text = validation_file.read_text(encoding="utf-8", errors="replace")
			match = re.search(r"\*\*(\d+) of (\d+) claims unsupported\*\*", text)
			if not match:
				continue
			batch_match = re.search(r"batch(\d+)", validation_file.name)
			entries.append(
				(
					question_dir.name,
					int(batch_match.group(1)) if batch_match else 0,
					int(match.group(1)),
					int(match.group(2)),
				)
			)

	if not entries:
		return None

	total_unsupported = sum(entry[2] for entry in entries)
	total_claims = sum(entry[3] for entry in entries)
	lines = [
		f"# Validation Summary - {model}\n",
		f"**{total_unsupported} of {total_claims} claims unsupported across {len(entries)} runs**\n",
		"| Question | Batch | Unsupported | Total | Rate |",
		"|----------|-------|-------------|-------|------|",
	]
	for question_id, batch, unsupported, total in entries:
		rate = f"{unsupported / total * 100:.0f}%" if total > 0 else "-"
		lines.append(f"| {question_id} | {batch} | {unsupported} | {total} | {rate} |")

	path = eval_dir / "validation_summary.md"
	path.write_text("\n".join(lines), encoding="utf-8")
	return path


__all__ = ["write_validation", "write_validation_summary"]
