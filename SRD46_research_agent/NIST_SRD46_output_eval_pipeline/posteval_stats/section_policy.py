from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


def _clean_section(value: str | None) -> str:
    return (value or "").strip()


def section_matches_prefix(section: str | None, prefix: str | None) -> bool:
    section_text = _clean_section(section)
    prefix_text = _clean_section(prefix)
    if not section_text or not prefix_text:
        return False
    return section_text == prefix_text or section_text.startswith(prefix_text + ".")


@dataclass(slots=True, frozen=True)
class SectionPolicy:
    include_section_4: bool = False
    separate_section_5: bool = True
    separate_section_1: bool = False
    separate_section_2: bool = False
    separate_section_3: bool = False

    def include_raw_section(self, raw_section: str | None) -> bool:
        section = _clean_section(raw_section)
        if not section or section == "?":
            return True
        major = section.split(".", 1)[0]
        return major != "4" or self.include_section_4

    def group_section(self, raw_section: str | None) -> str:
        section = _clean_section(raw_section)
        if not section or section == "?":
            return section
        major = section.split(".", 1)[0]
        if major == "1":
            return section if self.separate_section_1 else "1"
        if major == "2":
            return section if self.separate_section_2 else "2"
        if major == "3":
            return section if self.separate_section_3 else "3"
        if major == "5":
            return section if self.separate_section_5 else "5"
        return section

    def group_major_section(self, raw_section: str | None) -> str:
        return self.group_section(raw_section)

    def group_title(self, raw_section: str | None, raw_title: str | None = None) -> str:
        grouped = self.group_section(raw_section)
        raw = _clean_section(raw_section)
        title = (raw_title or "").strip()
        if not grouped or not title or grouped == raw:
            return title
        return f"Section {grouped}"

    def matches_requested_sections(self, raw_section: str | None, requested_sections: Iterable[str] | None) -> bool:
        if requested_sections is None:
            return True
        return any(section_matches_prefix(raw_section, requested) for requested in requested_sections)

    def to_dict(self) -> dict[str, bool]:
        return {
            "include_section_4": self.include_section_4,
            "separate_section_1": self.separate_section_1,
            "separate_section_2": self.separate_section_2,
            "separate_section_3": self.separate_section_3,
            "separate_section_5": self.separate_section_5,
        }


DEFAULT_SECTION_POLICY = SectionPolicy()


__all__ = [
    "DEFAULT_SECTION_POLICY",
    "SectionPolicy",
    "section_matches_prefix",
]