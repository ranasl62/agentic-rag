"""
Stable section identifiers for matching the same section across editions.
Format: book_<slug>_ch<nn>_sec<nn>_subsec<nn> (optional).
"""
from __future__ import annotations

import hashlib
import re
from typing import Optional


def normalize_number(text: str) -> str:
    """Map 'Chapter Three', 'Ch. 3', '3' -> '3' for stable ordering."""
    if not text:
        return "0"
    text = text.strip().lower()
    # Already numeric
    if text.isdigit():
        return text.zfill(2)
    # Roman numerals (simple)
    roman = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10}
    if text in roman:
        return str(roman[text]).zfill(2)
    # "chapter 3" -> 3
    m = re.search(r"(?:chapter|ch\.?|section|sec\.?)\s*(\d+)", text, re.I)
    if m:
        return m.group(1).zfill(2)
    return "0"


def slug(text: str, max_len: int = 20) -> str:
    """Short alphanumeric slug for book id."""
    if not text:
        return "unknown"
    s = re.sub(r"[^a-z0-9]+", "_", text.lower().strip())[:max_len]
    return s.strip("_") or "unknown"


class SectionIdGenerator:
    """
    Generate canonical_section_id and semantic_hash for a section.
    """

    def __init__(self, book_id_slug: str) -> None:
        self.book_id_slug = book_id_slug

    def canonical_section_id(
        self,
        chapter_number: Optional[int] = None,
        chapter_title: Optional[str] = None,
        section_number: Optional[int] = None,
        section_title: Optional[str] = None,
        subsection_number: Optional[int] = None,
        subsection_title: Optional[str] = None,
        sequence_number: int = 0,
    ) -> str:
        parts = [self.book_id_slug]
        ch = chapter_number if chapter_number is not None else (chapter_title and normalize_number(chapter_title))
        if ch is not None:
            parts.append("ch" + (str(ch).zfill(2) if isinstance(ch, int) else str(ch)))
        sec = section_number if section_number is not None else (section_title and normalize_number(section_title))
        if sec is not None:
            parts.append("sec" + (str(sec).zfill(2) if isinstance(sec, int) else str(sec)))
        if subsection_number is not None or subsection_title:
            sub = subsection_number if subsection_number is not None else normalize_number(subsection_title or "0")
            parts.append("subsec" + (str(sub).zfill(2) if isinstance(sub, int) else str(sub)))
        if len(parts) == 1:
            parts.append(f"seq{sequence_number}")
        return "_".join(str(p) for p in parts)

    def semantic_hash(self, location_path: str, heading_text: str, content_preview: str = "") -> str:
        """Hash of structure + heading for fuzzy matching."""
        blob = f"{location_path}|{heading_text}|{content_preview[:500]}"
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]

    def location_path(
        self,
        chapter_number: Optional[int],
        chapter_title: Optional[str],
        section_number: Optional[int],
        section_title: Optional[str],
        subsection_number: Optional[int],
        subsection_title: Optional[str],
    ) -> str:
        parts = []
        if chapter_number is not None or chapter_title:
            parts.append(f"Chapter {chapter_number or chapter_title or '?'}")
        if section_number is not None or section_title:
            parts.append(f"Section {section_number or section_title or '?'}")
        if subsection_number is not None or subsection_title:
            parts.append(f"Subsection {subsection_number or subsection_title or '?'}")
        return " → ".join(parts) if parts else "Unknown"
