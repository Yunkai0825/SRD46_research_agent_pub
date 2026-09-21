"""Shared checks that distinguish operative answer data from quoted examples."""

from __future__ import annotations

import re


FENCED_BLOCK_RE = re.compile(
    r"(?ms)^[ \t]*(?:`{3,}|~{3,})[^\r\n]*\r?\n.*?"
    r"^[ \t]*(?:`{3,}|~{3,})[ \t]*(?:\r?\n|$)"
)
_HTML_CONTEXT_TOKEN_RE = re.compile(
    r"(?is)<(?P<close>/)?(?P<tag>blockquote|q|pre|code)\b[^>]*>",
)
_HTML_COMMENT_RE = re.compile(r"(?s)<!--.*?(?:-->|\Z)")
_FENCE_LINE_RE = re.compile(
    r"(?m)^[ \t]*(?P<marker>`{3,}|~{3,})(?P<tail>[^\r\n]*)$",
)
_DOUBLE_QUOTE_TOKEN_RE = re.compile(r'(?:\\")|(?<!\\)"|&quot;|&#34;', re.I)
_SINGLE_QUOTE_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])'|'(?![A-Za-z0-9])")
_BACKTICK_RUN_RE = re.compile(r"`+")
_INDENTED_CODE_LINE_RE = re.compile(
    r"(?m)^(?: {4,}|\t)[^\r\n]*(?:\r?\n|$)",
)
_ATX_HEADING_TOKEN_RE = re.compile(
    r"(?m)^[ ]{0,3}(?P<marks>#{1,6})[ \t]+(?P<title>[^\r\n]*?)"
    r"[ \t]*#*[ \t]*$"
)
_COLON_SECTION_HEADING_RE = re.compile(
    r"^[ ]{0,3}(?:[*_]{1,3})?(?P<title>[^|\r\n]{2,160}?):"
    r"(?:[*_]{1,3})?[ \t]*$"
)
_SETEXT_UNDERLINE_RE = re.compile(r"^[ ]{0,3}(?P<marks>=+|-+)[ \t]*$")
DISQUALIFYING_ROLE_RE = re.compile(
    r"\b(?:not|no|never|reject(?:ed|ion)?|withdraw(?:n|al)?|"
    r"discard(?:ed|ing)?|invalid|excluded?|omit(?:ted)?|conflict(?:ing)?|"
    r"unsupported|irrelevant|inapplicable|unreliable|contradictory|"
    r"unverified|uncorroborated|unusable|superseded|"
    r"not[ \t]+applicable|must[ \t]+not|do[ \t]+not|"
    r"not[ \t]+(?:use|used|support(?:ed)?|adopted))\b",
    re.IGNORECASE,
)


def role_is_disqualified(value: str) -> bool:
    """Return whether *value* explicitly rejects or negates a declaration."""

    surface = re.sub(r"[_-]+", " ", value or "")
    return bool(DISQUALIFYING_ROLE_RE.search(surface))


def _span_overlaps(start: int, end: int, other_start: int, other_end: int) -> bool:
    return start < other_end and other_start < end


def _fenced_ranges(text: str):
    opening: tuple[str, int, int] | None = None
    for match in _FENCE_LINE_RE.finditer(text):
        marker = match.group("marker")
        if opening is None:
            opening = (marker[0], len(marker), match.start())
            continue
        opening_char, opening_length, opening_start = opening
        if (
            marker[0] == opening_char
            and len(marker) >= opening_length
            and not match.group("tail").strip()
        ):
            yield opening_start, match.end()
            opening = None
    if opening is not None:
        yield opening[2], len(text)


def _html_blockquote_ranges(text: str):
    opening_starts: dict[str, list[int]] = {}
    for match in _HTML_CONTEXT_TOKEN_RE.finditer(text):
        tag = match.group("tag").casefold()
        starts = opening_starts.setdefault(tag, [])
        if match.group("close"):
            if not starts:
                continue
            yield starts.pop(), match.end()
        else:
            starts.append(match.start())
    for starts in opening_starts.values():
        for opening_start in starts:
            yield opening_start, len(text)


def _markdown_blockquote_ranges(text: str):
    lines = text.splitlines(keepends=True)
    offsets: list[int] = []
    offset = 0
    for line in lines:
        offsets.append(offset)
        offset += len(line)
    index = 0
    while index < len(lines):
        content = lines[index].rstrip("\r\n")
        if not content.lstrip().startswith(">"):
            index += 1
            continue
        start = offsets[index]
        index += 1
        # Include CommonMark lazy continuation lines through the next blank.
        while index < len(lines) and lines[index].strip():
            index += 1
        end = offsets[index] if index < len(lines) else len(text)
        yield start, end


def _symmetric_quote_ranges(text: str, token_re: re.Pattern[str]):
    opening: int | None = None
    for match in token_re.finditer(text):
        if opening is None:
            opening = match.start()
        else:
            yield opening, match.end()
            opening = None
    if opening is not None:
        yield opening, len(text)


def _asymmetric_quote_ranges(text: str, opening: str, closing: str):
    opening_start: int | None = None
    token_re = re.compile(f"{re.escape(opening)}|{re.escape(closing)}")
    for match in token_re.finditer(text):
        if match.group(0) == opening:
            if opening_start is None:
                opening_start = match.start()
        elif opening_start is not None:
            yield opening_start, match.end()
            opening_start = None
    if opening_start is not None:
        yield opening_start, len(text)


def _multiline_backtick_ranges(text: str):
    openings: dict[int, int] = {}
    for match in _BACKTICK_RUN_RE.finditer(text):
        length = len(match.group(0))
        opening = openings.pop(length, None)
        if opening is None:
            openings[length] = match.start()
            continue
        if "\n" in text[opening:match.end()] or "\r" in text[opening:match.end()]:
            yield opening, match.end()
    for length, opening in openings.items():
        suffix = text[opening:]
        if length >= 3 or "\n" in suffix or "\r" in suffix:
            yield opening, len(text)


def contextual_ranges(text: str) -> tuple[tuple[int, int], ...]:
    """Return merged answer ranges that are examples rather than declarations."""

    body = text or ""
    ranges = [
        *_fenced_ranges(body),
        *_html_blockquote_ranges(body),
        *((match.start(), match.end()) for match in _HTML_COMMENT_RE.finditer(body)),
        *_markdown_blockquote_ranges(body),
        *((match.start(), match.end()) for match in _INDENTED_CODE_LINE_RE.finditer(body)),
        *_symmetric_quote_ranges(body, _DOUBLE_QUOTE_TOKEN_RE),
        *_symmetric_quote_ranges(body, _SINGLE_QUOTE_TOKEN_RE),
        *_asymmetric_quote_ranges(body, "“", "”"),
        *_asymmetric_quote_ranges(body, "‘", "’"),
        *_asymmetric_quote_ranges(body, "«", "»"),
        *_multiline_backtick_ranges(body),
    ]
    merged: list[list[int]] = []
    for start, end in sorted(ranges):
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return tuple((start, end) for start, end in merged)


def operative_text(text: str) -> str:
    """Mask all contextual ranges while preserving offsets and line breaks."""

    body = text or ""
    if not body:
        return body
    characters = list(body)
    for start, end in contextual_ranges(body):
        for index in range(start, end):
            if characters[index] not in "\r\n":
                characters[index] = " "
    return "".join(characters)


def markdown_heading_ancestry(text: str, position: int) -> tuple[str, ...]:
    """Return active rendered section titles at *position*, outermost first.

    ATX and Setext headings retain their Markdown levels. Standalone colon
    headings are treated as a common deepest-level report subsection so a
    later colon heading closes its predecessor, while any formal Markdown
    heading closes colon subsections beneath it.
    """

    body = operative_text(text or "")
    bounded_position = max(0, min(int(position), len(body)))
    events: list[tuple[int, int, str]] = []
    for match in _ATX_HEADING_TOKEN_RE.finditer(body):
        events.append((match.start(), len(match.group("marks")), match.group("title").strip()))

    lines = body.splitlines(keepends=True)
    offsets: list[int] = []
    offset = 0
    for line in lines:
        offsets.append(offset)
        offset += len(line)
    for index, line in enumerate(lines):
        surface = line.rstrip("\r\n")
        colon = _COLON_SECTION_HEADING_RE.fullmatch(surface)
        if colon is not None and not surface.lstrip().startswith(("#", ">")):
            events.append((offsets[index], 7, colon.group("title").strip()))
        if index + 1 >= len(lines) or not surface.strip():
            continue
        underline = _SETEXT_UNDERLINE_RE.fullmatch(
            lines[index + 1].rstrip("\r\n")
        )
        if underline is None or surface.lstrip().startswith(("#", ">", "|")):
            continue
        level = 1 if underline.group("marks").startswith("=") else 2
        events.append((offsets[index], level, surface.strip()))

    stack: list[tuple[int, str]] = []
    seen_starts: set[tuple[int, int, str]] = set()
    for event_start, level, title in sorted(events):
        if event_start >= bounded_position:
            break
        identity = (event_start, level, title)
        if identity in seen_starts:
            continue
        seen_starts.add(identity)
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
    return tuple(title for _level, title in stack)


def _is_markdown_blockquote_continuation(text: str, start: int) -> bool:
    line_start = max(text.rfind("\n", 0, start), text.rfind("\r", 0, start)) + 1
    current_prefix = text[line_start:start]
    if current_prefix.lstrip().startswith(">"):
        return True

    # CommonMark permits lazy continuation lines in a blockquote paragraph.
    # Walk back only within the current nonblank paragraph.
    preceding_lines = text[:line_start].splitlines()
    for line in reversed(preceding_lines):
        if not line.strip():
            break
        if line.lstrip().startswith(">"):
            return True
    return False


def span_is_contextual(text: str, start: int, end: int) -> bool:
    """Return whether a declared span is fenced, blockquoted, or inline-quoted.

    The LC1.3 answer contracts accept only operative declarations. Examples or
    rejected proposals reproduced as Markdown/code quotations must therefore
    never become parser input merely because they contain contract syntax.
    """

    body = text or ""
    if start < 0 or end <= start or end > len(body):
        return True

    # A declaration is contextual only when it begins inside an enclosing
    # contextual range. Quoted strings *inside* an operative structured JSON
    # declaration are payload syntax and must not invalidate the outer block.
    if any(
        range_start <= start < range_end
        for range_start, range_end in contextual_ranges(body)
    ):
        return True

    line_start = max(body.rfind("\n", 0, start), body.rfind("\r", 0, start)) + 1
    line_end_candidates = [
        position for position in (body.find("\n", end), body.find("\r", end))
        if position >= 0
    ]
    line_end = min(line_end_candidates) if line_end_candidates else len(body)
    prefix = body[line_start:start]
    suffix = body[end:line_end]
    if _is_markdown_blockquote_continuation(body, start):
        return True

    # Symmetric delimiters are contextual when the declaration starts inside
    # an unmatched delimiter and a matching close follows on the same line.
    for delimiter in ('"', "'", "`"):
        if prefix.count(delimiter) % 2 == 1 and delimiter in suffix:
            return True

    # Straight double quotes can delimit a quotation across physical lines.
    # An unmatched opening quote remains contextual through EOF.
    if len(_DOUBLE_QUOTE_TOKEN_RE.findall(body[:start])) % 2 == 1:
        return True

    # Unicode typographic quotation marks have distinct open/close tokens.
    for opening, closing in (("“", "”"), ("‘", "’"), ("«", "»")):
        if body[:start].rfind(opening) > body[:start].rfind(closing):
            return True
    return False


__all__ = [
    "DISQUALIFYING_ROLE_RE",
    "FENCED_BLOCK_RE",
    "contextual_ranges",
    "markdown_heading_ancestry",
    "operative_text",
    "role_is_disqualified",
    "span_is_contextual",
]
