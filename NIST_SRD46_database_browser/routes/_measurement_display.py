"""Plain display text for source definitions and optional database fields."""
from __future__ import annotations

from html.parser import HTMLParser
from typing import Any


def optional_text(value: Any) -> str | None:
    """Hide source null markers without changing a recorded numeric zero."""
    if value is None:
        return None
    text = str(value).strip()
    return None if text in ('', '\\N', '*') else text


class _DefinitionText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == 'sup':
            self.parts.append('^(')

    def handle_endtag(self, tag):
        if tag == 'sup':
            self.parts.append(')')

    def handle_data(self, data):
        self.parts.append(data)


def plain_definition(value: Any) -> str | None:
    """Convert SRD46 sub/sup markup to plain text; Jinja still escapes the result."""
    text = optional_text(value)
    if text is None:
        return None
    parser = _DefinitionText()
    parser.feed(text)
    parser.close()
    return ''.join(parser.parts)
