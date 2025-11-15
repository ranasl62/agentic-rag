"""
Extract hierarchical structure (chapters, sections, subsections) from raw text or parsed DOM.
Generic so it can be driven by PDF/EPUB parsers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SectionBlock:
    """One section: heading + content."""

    chapter_number: Optional[int] = None
    chapter_title: Optional[str] = None
    section_number: Optional[int] = None
    section_title: Optional[str] = None
    subsection_number: Optional[int] = None
    subsection_title: Optional[str] = None
    content: str = ""
    sequence_number: int = 0


class StructureExtractor:
    """
    Parse flat text or list of (heading, level) + content into SectionBlocks.
    Handles patterns like "Chapter 3", "3.2 Section Title", "### Subsection".
    """

    CHAPTER_PATTERNS = [
        re.compile(r"^chapter\s+(\d+)(?:\s*[.:\-]\s*(.+))?$", re.I),
        re.compile(r"^ch\.?\s*(\d+)(?:\s*[.:\-]\s*(.+))?$", re.I),
        re.compile(r"^(\d+)\s*[.:]\s*(.+)$"),  # "3. Title"
    ]
    SECTION_PATTERNS = [
        re.compile(r"^section\s+(\d+)(?:\s*[.:\-]\s*(.+))?$", re.I),
        re.compile(r"^(\d+)\.(\d+)(?:\s+(.+))?$"),  # 3.2 or 3.2 Title
    ]
    SUBSECTION_PATTERNS = [
        re.compile(r"^subsection\s+(\d+)(?:\s*[.:\-]\s*(.+))?$", re.I),
        re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:\s+(.+))?$"),
    ]

    def parse_lines(self, lines: List[str]) -> List[SectionBlock]:
        """Parse a list of lines into section blocks. Headings detected by pattern or level."""
        blocks: List[SectionBlock] = []
        current = SectionBlock(sequence_number=0)
        seq = 0
        for line in lines:
            line = line.rstrip()
            if not line:
                continue
            ch, sec, subsec, title = self._classify_line(line)
            if ch is not None or sec is not None or subsec is not None:
                if current.content or current.chapter_number is not None:
                    current.sequence_number = seq
                    blocks.append(current)
                    seq += 1
                current = SectionBlock(
                    chapter_number=ch if isinstance(ch, int) else None,
                    chapter_title=title if ch is not None else current.chapter_title,
                    section_number=sec if isinstance(sec, int) else None,
                    section_title=title if sec is not None else current.section_title,
                    subsection_number=subsec if isinstance(subsec, int) else None,
                    subsection_title=title if subsec is not None else current.subsection_title,
                    sequence_number=seq,
                )
                if ch is not None and isinstance(ch, int):
                    current.chapter_number = ch
                    current.chapter_title = title or current.chapter_title
                if sec is not None and isinstance(sec, int):
                    current.section_number = sec
                    current.section_title = title or current.section_title
                if subsec is not None and isinstance(subsec, int):
                    current.subsection_number = subsec
                    current.subsection_title = title or current.subsection_title
            else:
                current.content += line + "\n"
        if current.content or current.chapter_number is not None:
            current.sequence_number = seq
            blocks.append(current)
        return blocks

    def _classify_line(self, line: str) -> tuple[Optional[int], Optional[int], Optional[int], Optional[str]]:
        """Return (chapter_num, section_num, subsection_num, title)."""
        stripped = line.strip()
        for p in self.CHAPTER_PATTERNS:
            m = p.match(stripped)
            if m:
                g = m.groups()
                num = int(g[0]) if g[0].isdigit() else None
                title = g[1].strip() if len(g) > 1 and g[1] else None
                return (num, None, None, title)
        for p in self.SUBSECTION_PATTERNS:
            m = p.match(stripped)
            if m:
                g = m.groups()
                if len(g) >= 3:
                    return (None, None, int(g[2]) if str(g[2]).isdigit() else None, g[3].strip() if len(g) > 3 and g[3] else None)
        for p in self.SECTION_PATTERNS:
            m = p.match(stripped)
            if m:
                g = m.groups()
                if len(g) >= 2:
                    return (None, int(g[1]) if str(g[1]).isdigit() else None, None, g[2].strip() if len(g) > 2 and g[2] else None)
        return (None, None, None, None)
