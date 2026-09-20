# autocoder/routing/finding_router.py
from typing import Dict, List

from autocoder.analysis.finding import VALID_CATEGORIES


def route_finding(finding: dict) -> str:
    """Given a single Finding dict, returns exactly one of:
    "fixer" | "security_fixer" | "refactorer" | "report_only"
    based purely on this deterministic mapping:
    - category == "bug" -> "fixer"
    - category == "security" -> "security_fixer"
    - category == "refactor" -> "refactorer"
    - category == "cosmetic" -> "report_only"
    Raise ValueError for any category outside VALID_CATEGORIES rather than
    guessing a default route."""
    
    category = finding.get("category")
    
    if category not in VALID_CATEGORIES:
        raise ValueError(f"Invalid category '{category}' — must be one of {sorted(VALID_CATEGORIES)}")
    
    if category == "bug":
        return "fixer"
    elif category == "security":
        return "security_fixer"
    elif category == "refactor":
        return "refactorer"
    elif category == "cosmetic":
        return "report_only"
    
    # This should never be reached due to the check above, but satisfies type checkers
    raise ValueError(f"Unhandled category: {category}")


def route_findings(findings: List[dict]) -> Dict[str, List[dict]]:
    """Applies route_finding() to every finding and groups them into
    {"fixer": [...], "security_fixer": [...], "refactorer": [...],
    "report_only": [...]} — all four keys always present, empty lists where
    nothing routed there."""
    
    routed = {
        "fixer": [],
        "security_fixer": [],
        "refactorer": [],
        "report_only": [],
    }
    
    for finding in findings:
        try:
            destination = route_finding(finding)
            routed[destination].append(finding)
        except ValueError:
            # Invalid category — skip this finding rather than crashing
            # (could also log a warning here if needed)
            pass
    
    return routed


def requires_human_approval(finding: dict, threshold: float = 0.85) -> bool:
    """Returns True if finding["confidence"] < threshold, meaning it should
    go to human approval instead of automatic fixing. Returns False (safe to
    auto-fix) only when confidence >= threshold AND category is "bug" or
    "refactor" (never security findings — those should ALWAYS require human
    approval regardless of confidence, since a wrong auto-fix on a security
    issue is higher-stakes than a wrong bug fix). Document this security
    exception clearly in a comment."""
    
    # SECURITY EXCEPTION: Security findings ALWAYS require human approval.
    # A wrong auto-fix on a security issue (e.g., incorrectly "fixing" an
    # auth bypass or injection vulnerability) can silently introduce
    # exploitable vulnerabilities. The stakes are fundamentally higher than
    # for bug/refactor fixes, so we never auto-route security findings.
    if finding.get("category") == "security":
        return True
    
    confidence = finding.get("confidence", 0.0)
    category = finding.get("category")
    
    # Only bug and refactor findings can be auto-fixed (at high confidence)
    if category not in ("bug", "refactor"):
        return True
    
    return confidence < threshold