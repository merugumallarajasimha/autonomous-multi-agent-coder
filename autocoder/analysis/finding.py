# autocoder/analysis/finding.py
from typing import TypedDict, FrozenSet


class Finding(TypedDict):
    severity: str        # "critical" | "high" | "medium" | "low"
    category: str        # "bug" | "security" | "refactor" | "cosmetic"
    file: str
    line: int
    description: str
    suggested_fix: str
    confidence: float    # 0.0 to 1.0
    source: str          # "static_analysis" | "llm_review"


VALID_SEVERITIES: FrozenSet[str] = frozenset(["critical", "high", "medium", "low"])
VALID_CATEGORIES: FrozenSet[str] = frozenset(["bug", "security", "refactor", "cosmetic"])
VALID_SOURCES: FrozenSet[str] = frozenset(["static_analysis", "llm_review"])


def validate_finding(f: dict) -> bool:
    """Returns True only if f has all required keys with values in the valid
    sets above and confidence is a float between 0.0 and 1.0 inclusive.
    Does not raise — just returns False for anything invalid, so callers can
    filter out malformed LLM output rather than crashing on it."""
    
    required_keys = {"severity", "category", "file", "line", "description", "suggested_fix", "confidence", "source"}
    
    # Check all required keys present
    if not isinstance(f, dict):
        return False
    if not required_keys.issubset(f.keys()):
        return False
    
    # Validate severity
    if f["severity"] not in VALID_SEVERITIES:
        return False
    
    # Validate category
    if f["category"] not in VALID_CATEGORIES:
        return False
    
    # Validate source
    if f["source"] not in VALID_SOURCES:
        return False
    
    # Validate file is string
    if not isinstance(f["file"], str):
        return False
    
    # Validate line is int >= 0
    if not isinstance(f["line"], int) or f["line"] < 0:
        return False
    
    # Validate description is string
    if not isinstance(f["description"], str):
        return False
    
    # Validate suggested_fix is string
    if not isinstance(f["suggested_fix"], str):
        return False
    
    # Validate confidence is float between 0.0 and 1.0 inclusive
    if not isinstance(f["confidence"], (int, float)):
        return False
    confidence = float(f["confidence"])
    if confidence < 0.0 or confidence > 1.0:
        return False
    
    return True