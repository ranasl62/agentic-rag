"""
Semantic chunking: split by paragraphs/sentences with size limits, not fixed character count.
"""
from __future__ import annotations

import re
from typing import List

# Target chunk size in chars; overlap not used for simplicity (can add later)
DEFAULT_MAX_CHARS = 1200
MIN_CHARS = 200


def semantic_chunk(text: str, max_chars: int = DEFAULT_MAX_CHARS, min_chars: int = MIN_CHARS) -> List[str]:
    """
    Split text into chunks on paragraph boundaries, then sentence boundaries,
    keeping chunks between min_chars and max_chars when possible.
    """
    if not text or len(text.strip()) <= max_chars:
        return [text.strip()] if text.strip() else []
    chunks: List[str] = []
    paragraphs = re.split(r"\n\s*\n", text)
    current: List[str] = []
    current_len = 0
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if current_len + len(p) + 2 <= max_chars:
            current.append(p)
            current_len += len(p) + 2
        else:
            if current:
                chunk = "\n\n".join(current)
                if len(chunk) > max_chars:
                    for sent in _split_sentences(chunk, max_chars, min_chars):
                        chunks.append(sent)
                else:
                    chunks.append(chunk)
            current = [p]
            current_len = len(p) + 2
    if current:
        chunk = "\n\n".join(current)
        if len(chunk) > max_chars:
            chunks.extend(_split_sentences(chunk, max_chars, min_chars))
        else:
            chunks.append(chunk)
    return chunks


def _split_sentences(text: str, max_chars: int, min_chars: int) -> List[str]:
    """Fallback: split by sentences."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    out: List[str] = []
    buf: List[str] = []
    buf_len = 0
    for s in sentences:
        if buf_len + len(s) + 1 <= max_chars:
            buf.append(s)
            buf_len += len(s) + 1
        else:
            if buf:
                out.append(" ".join(buf))
            buf = [s]
            buf_len = len(s) + 1
    if buf:
        out.append(" ".join(buf))
    return out
