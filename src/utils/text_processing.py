"""Text normalization and safe truncation for citations and previews."""

def truncate(text: str, max_length: int = 200, suffix: str = "...") -> str:
    if not text or len(text) <= max_length:
        return text or ""
    return text[: max_length - len(suffix)].rstrip() + suffix
