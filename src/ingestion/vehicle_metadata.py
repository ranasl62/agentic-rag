"""
Vehicle metadata and wildcard matching for document scope.
See docs/DOCUMENT_SCOPE_AND_VEHICLE_METADATA.md.

- Pattern: fixed-length string with '*' = any single character (e.g. C** => CA1, CA2, CB1).
- '*' as field value: matches any user value.
- model_year: document has min/max; user value must be in range.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


def match_pattern(user_value: str, pattern: str) -> bool:
    """
    Match user value against a fixed-length pattern. '*' in pattern = any character.
    Lengths must match. E.g. C** matches CA1, CA2, CB1; *** matches any 3-char code.
    """
    if not isinstance(user_value, str) or not isinstance(pattern, str):
        return False
    if len(user_value) != len(pattern):
        return False
    for u, p in zip(user_value, pattern):
        if p != "*" and p != u:
            return False
    return True


def match_vehicle_context(
    doc_metadata: Optional[Dict[str, Any]],
    user_vehicle: Optional[Dict[str, Any]],
) -> bool:
    """
    Return True if document's vehicle_metadata matches the user's vehicle context.
    - doc_metadata: from document (book/edition), e.g. model_year_min, model_year_max, model_code_pattern, engine, transmission.
    - user_vehicle: from request, e.g. model_year=2018, model_code=CA2, engine=2ZR-FE, transmission=CVT.
    - Missing doc field or '*' in doc = any user value. Missing user field = skip that dimension (or treat as no match).
    """
    if not doc_metadata:
        return True
    if not user_vehicle:
        return True

    # Model year: document range [min, max]
    year_min = doc_metadata.get("model_year_min")
    year_max = doc_metadata.get("model_year_max")
    user_year = user_vehicle.get("model_year")
    if user_year is not None and (year_min is not None or year_max is not None):
        try:
            y = int(user_year)
            if year_min is not None and y < year_min:
                return False
            if year_max is not None and y > year_max:
                return False
        except (TypeError, ValueError):
            return False

    # Model code: pattern match (e.g. C**, ***)
    doc_code = doc_metadata.get("model_code_pattern")
    user_code = user_vehicle.get("model_code")
    if user_code is not None and doc_code is not None and doc_code != "*":
        if not match_pattern(user_code, doc_code):
            return False

    # Engine: exact or doc = *
    doc_engine = doc_metadata.get("engine")
    user_engine = user_vehicle.get("engine")
    if user_engine is not None and doc_engine is not None and doc_engine != "*":
        if doc_engine != user_engine:
            return False

    # Transmission: exact or doc = *
    doc_trans = doc_metadata.get("transmission")
    user_trans = user_vehicle.get("transmission")
    if user_trans is not None and doc_trans is not None and doc_trans != "*":
        if doc_trans != user_trans:
            return False

    return True
