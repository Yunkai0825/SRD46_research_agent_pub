"""Convert EnrichedDocument to annotated HTML with inline highlights.

Span types are wrapped in ``<span>`` tags with CSS classes:
- ``.num-match`` (blue) — numeric values, with tooltip showing top-10 matches
- ``.chem-name`` (green) — chemical names / formulas
- ``.canon-id`` (orange) — canonical IDs, rendered as hyperlinks to the browser
"""
from __future__ import annotations

import html
import re
from typing import Sequence

from .models import (
    ChemSpan,
    EnrichedDocument,
    IdSpan,
    NumericMatch,
    NumericSpan,
    ParagraphAnnotation,
    TokenSpan,
)

# ---------------------------------------------------------------------------
# URL routing for canonical IDs → browser pages
# ---------------------------------------------------------------------------

_ENTITY_URL_MAP: dict[str, str] = {
    "metal":      "/metals/{raw_id}",
    "ligand":     "/ligands/{raw_id}",
    "vlm":        "/stability?vlm_id={raw_id}",
    "beta_def":   "/stability?beta_def_id={raw_id}",
    "network":    "/equilibrium/network/{raw_id}",
    "map":        "/equilibrium?map_id={raw_id}",
    "literature": "/literature?q={raw_id}",
    "pka":        "/pka?pka_id={raw_id}",
}


def _entity_url(span: IdSpan) -> str:
    template = _ENTITY_URL_MAP.get(span.entity_type)
    if template:
        return template.format(raw_id=span.raw_id)
    return "#"


# ---------------------------------------------------------------------------
# Tooltip for numeric matches
# ---------------------------------------------------------------------------

def _numeric_tooltip(matches: list[NumericMatch]) -> str:
    if not matches:
        return ""
    lines = ["Top-10 closest DB matches:"]
    for i, m in enumerate(matches[:10], 1):
        lines.append(
            f"{i}. {m.db_value:.4g} (Δ={m.distance:.4g}) — "
            f"{m.source_id}: {m.measurement_detail}"
        )
    return "&#10;".join(html.escape(line) for line in lines)


# ---------------------------------------------------------------------------
# Paragraph → HTML
# ---------------------------------------------------------------------------

def render_paragraph(annotation: ParagraphAnnotation) -> str:
    """Render a single paragraph's text with span highlights as HTML."""
    text = annotation.text
    if not annotation.spans:
        return f"<p>{html.escape(text)}</p>"

    # Sort spans by start position (they should already be sorted)
    sorted_spans = sorted(annotation.spans, key=lambda s: s.start)

    parts: list[str] = []
    cursor = 0

    for span_idx, span in enumerate(sorted_spans):
        # Text before this span
        if span.start > cursor:
            parts.append(html.escape(text[cursor:span.start]))

        span_text = html.escape(text[span.start:span.end])

        if isinstance(span, IdSpan):
            url = _entity_url(span)
            parts.append(
                f'<a class="canon-id" href="{url}" '
                f'title="{html.escape(span.entity_type)}:{span.raw_id}" '
                f'data-entity-type="{html.escape(span.entity_type)}" '
                f'data-prefixed-id="{html.escape(span.text)}">'
                f'{span_text}</a>'
            )
        elif isinstance(span, NumericSpan):
            matches = annotation.numeric_matches.get(span_idx, [])
            tooltip = _numeric_tooltip(matches)
            qty_attr = f' data-qty="{html.escape(span.quantity_type)}"' if span.quantity_type else ""
            parts.append(
                f'<span class="num-match"{qty_attr} '
                f'title="{tooltip}">{span_text}</span>'
            )
        elif isinstance(span, ChemSpan):
            parts.append(
                f'<span class="chem-name" '
                f'title="{html.escape(span.normalized_name)}">'
                f'{span_text}</span>'
            )
        else:
            parts.append(f'<span class="enriched">{span_text}</span>')

        cursor = span.end

    # Remaining text after last span
    if cursor < len(text):
        parts.append(html.escape(text[cursor:]))

    return f'<p>{"".join(parts)}</p>'


# ---------------------------------------------------------------------------
# Full document → HTML
# ---------------------------------------------------------------------------

def render_document(doc: EnrichedDocument) -> str:
    """Render an entire EnrichedDocument as annotated HTML."""
    parts = [
        f'<div class="enriched-doc" data-doc-type="{html.escape(doc.doc_type)}">'
    ]
    for para in doc.paragraphs:
        parts.append(render_paragraph(para))
    parts.append("</div>")
    return "\n".join(parts)


def render_documents_side_by_side(
    docs: dict[str, EnrichedDocument],
) -> dict[str, str]:
    """Render multiple documents, returning a dict of doc_type → HTML."""
    return {doc_type: render_document(doc) for doc_type, doc in docs.items()}


# ═══════════════════════════════════════════════════════════════════════
# Claim-based rendering
# ═══════════════════════════════════════════════════════════════════════

import json as _json

from .models import (
    Claim,
    ClaimAnnotatedDocument,
    ClaimParagraph,
    GroundedClaim,
)


def _claim_css_class(claim_type: str, support_class: str) -> str:
    """Build CSS class string for a claim span."""
    return f"claim claim-{claim_type} claim-{support_class}"


_BLOCK_SEP_RE = re.compile(r"(?:\r?\n){2,}")
_TABLE_RULE_RE = re.compile(r"^\s*\|?(?:\s*:?-+:?\s*\|)+\s*:?-+:?\s*\|?\s*$")


def _render_markdown_fragment(text: str, *, extensions: Sequence[str] | None = None) -> str:
    try:
        import markdown as _md
        return _md.markdown(
            text,
            extensions=list(extensions or ["tables", "fenced_code", "nl2br"]),
        )
    except ImportError:
        return f"<pre>{html.escape(text)}</pre>"


def _render_inline_markdown(text: str) -> str:
    rendered = _render_markdown_fragment(text, extensions=["nl2br"])
    match = re.fullmatch(r"<p>(.*)</p>", rendered, flags=re.DOTALL)
    return match.group(1) if match else rendered


def _claim_attr_string(
    claim_idx: int,
    claim: Claim,
    grounded: GroundedClaim | None,
    *,
    extra_classes: Sequence[str] = (),
) -> str:
    support = grounded.support_class if grounded else "unsupported"
    ref_ids = ",".join(grounded.canonical_ids) if grounded and grounded.canonical_ids else ""
    evidence = html.escape(grounded.evidence_snippet) if grounded and grounded.evidence_snippet else ""
    snippets_json = ""
    if grounded and grounded.tool_snippets:
        snippets_json = html.escape(_json.dumps(grounded.tool_snippets, ensure_ascii=False))

    classes = [_claim_css_class(claim.claim_type, support), *extra_classes]
    title = f"{claim.claim_type} — {support}"
    if evidence:
        title += f"&#10;Evidence: {evidence}"

    return " ".join([
        f'class="{" ".join(classes)}"',
        f'data-claim-idx="{claim_idx}"',
        f'data-claim-type="{html.escape(claim.claim_type)}"',
        f'data-ref-ids="{html.escape(ref_ids)}"',
        f'data-support="{html.escape(support)}"',
        f'data-snippets="{snippets_json}"',
        f'title="{title}"',
    ])


def _iter_markdown_blocks(text: str) -> list[tuple[str, int]]:
    blocks: list[tuple[str, int]] = []
    cursor = 0
    for match in _BLOCK_SEP_RE.finditer(text):
        block = text[cursor:match.start()]
        if block.strip():
            blocks.append((block, cursor))
        cursor = match.end()
    tail = text[cursor:]
    if tail.strip():
        blocks.append((tail, cursor))
    return blocks


def _claims_in_range(cp: ClaimParagraph, start: int, end: int) -> list[tuple[int, Claim]]:
    return [
        (idx, claim)
        for idx, claim in enumerate(cp.claims)
        if start <= claim.start and claim.end <= end
    ]


def _inject_claim_placeholders(
    block_text: str,
    block_start: int,
    claims: list[tuple[int, Claim]],
    grounding_map: dict[int, GroundedClaim],
) -> tuple[str, dict[str, str]]:
    if not claims:
        return block_text, {}

    parts: list[str] = []
    replacements: dict[str, str] = {}
    cursor = 0
    for claim_idx, claim in claims:
        local_start = claim.start - block_start
        local_end = claim.end - block_start
        if local_start < cursor or local_end > len(block_text):
            continue
        parts.append(block_text[cursor:local_start])
        token = f"CLAIMTOKEN{claim_idx}X{local_start}Y"
        attrs = _claim_attr_string(claim_idx, claim, grounding_map.get(claim_idx))
        claim_html = _render_inline_markdown(block_text[local_start:local_end])
        replacements[token] = f"<span {attrs}>{claim_html}</span>"
        parts.append(token)
        cursor = local_end
    parts.append(block_text[cursor:])
    return "".join(parts), replacements


def _is_table_block(block_text: str) -> bool:
    lines = [line.strip() for line in block_text.splitlines() if line.strip()]
    return len(lines) >= 2 and "|" in lines[0] and bool(_TABLE_RULE_RE.match(lines[1]))


_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+\S")


def _is_heading_block(block_text: str) -> bool:
    """True if the entire block is a single markdown heading line."""
    lines = [line for line in block_text.splitlines() if line.strip()]
    return len(lines) == 1 and bool(_HEADING_RE.match(lines[0]))


def _split_table_line(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _render_claim_table(
    block_text: str,
    block_start: int,
    cp: ClaimParagraph,
    grounding_map: dict[int, GroundedClaim],
    *,
    heading_block: tuple[str, int] | None = None,
) -> str:
    lines: list[tuple[str, int]] = []
    offset = block_start
    for raw_line in block_text.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        if line.strip():
            lines.append((line, offset))
        offset += len(raw_line)

    if len(lines) < 2:
        return _render_markdown_fragment(block_text)

    header_cells = _split_table_line(lines[0][0])
    body_rows = lines[2:]
    row_claims = {
        (claim.start, claim.end): (claim_idx, claim)
        for claim_idx, claim in _claims_in_range(cp, block_start, block_start + len(block_text))
    }

    wrap_classes = ["claim-table-wrap"]
    if heading_block is not None:
        wrap_classes.append("table-section")

    parts = [f'<div class="{" ".join(wrap_classes)}">']

    if heading_block is not None:
        heading_text, heading_start = heading_block
        heading_claims = _claims_in_range(
            cp, heading_start, heading_start + len(heading_text)
        )
        injected, replacements = _inject_claim_placeholders(
            heading_text, heading_start, heading_claims, grounding_map
        )
        rendered_heading = _render_markdown_fragment(injected)
        for token, replacement in replacements.items():
            rendered_heading = rendered_heading.replace(token, replacement)
        # Tag the rendered heading element so CSS / JS can group it with the table.
        rendered_heading = re.sub(
            r'<(h[1-6])\b',
            r'<\1 class="table-section-heading"',
            rendered_heading,
            count=1,
        )
        parts.append(rendered_heading)

    parts.extend(['<table class="claim-table">', "<thead><tr>"])
    for cell in header_cells:
        parts.append(f"<th>{_render_inline_markdown(cell)}</th>")
    parts.append("</tr></thead><tbody>")

    for row_text, row_start in body_rows:
        row_end = row_start + len(row_text)
        claim_match = row_claims.get((row_start, row_end))
        row_attrs = ""
        if claim_match:
            claim_idx, claim = claim_match
            row_attrs = " " + _claim_attr_string(
                claim_idx,
                claim,
                grounding_map.get(claim_idx),
                extra_classes=("claim-row",),
            ) + ' tabindex="0"'
        cells = _split_table_line(row_text)
        parts.append(f"<tr{row_attrs}>")
        for cell in cells:
            parts.append(f"<td>{_render_inline_markdown(cell)}</td>")
        parts.append("</tr>")

    parts.append("</tbody></table></div>")
    return "".join(parts)


def render_claim_paragraph(cp: ClaimParagraph) -> str:
    """Render a section of markdown with claim annotations preserved."""
    text = cp.text
    if not text.strip():
        return ""

    grounding_map: dict[int, GroundedClaim] = {
        g.claim_index: g for g in cp.grounded_claims
    }

    blocks = _iter_markdown_blocks(text)
    rendered_blocks: list[str] = []
    i = 0
    while i < len(blocks):
        block_text, block_start = blocks[i]
        # Pair a heading with the immediately following table so they render
        # together inside one claim-table-wrap (visual + claim grouping).
        if (
            _is_heading_block(block_text)
            and i + 1 < len(blocks)
            and _is_table_block(blocks[i + 1][0])
        ):
            next_text, next_start = blocks[i + 1]
            rendered_blocks.append(
                _render_claim_table(
                    next_text,
                    next_start,
                    cp,
                    grounding_map,
                    heading_block=(block_text, block_start),
                )
            )
            i += 2
            continue

        if _is_table_block(block_text):
            rendered_blocks.append(
                _render_claim_table(block_text, block_start, cp, grounding_map)
            )
            i += 1
            continue

        block_claims = _claims_in_range(cp, block_start, block_start + len(block_text))
        injected, replacements = _inject_claim_placeholders(
            block_text, block_start, block_claims, grounding_map
        )
        rendered = _render_markdown_fragment(injected)
        for token, replacement in replacements.items():
            rendered = rendered.replace(token, replacement)
        rendered_blocks.append(rendered)
        i += 1

    return "\n".join(rendered_blocks)


def render_claim_document(doc: ClaimAnnotatedDocument) -> str:
    """Render a ClaimAnnotatedDocument as annotated HTML."""
    parts = [
        '<div class="claim-doc md-doc" data-doc-type="answer">'
    ]
    for cp in doc.paragraphs:
        parts.append(
            f'<section class="claim-paragraph" data-paragraph-index="{cp.paragraph_index}">'
            f'{render_claim_paragraph(cp)}'
            '</section>'
        )
    parts.append("</div>")
    return "\n".join(parts)
