# autocoder/state.py
from typing import TypedDict, List, Dict, Any, Optional

class AgentState(TypedDict):
    user_request: str
    repo_path: str
    feature_branch: str
    allowed_files: List[str]
    
    # Execution & Retry Counters
    iteration_count: int
    max_iterations: int
    
    # Verification & Test Diagnostics
    static_checks_passed: bool
    test_passed: bool
    test_logs: str
    
    # Review Findings & Bugs
    bug_report: Optional[Dict[str, Any]]
    review_findings: List[Dict[str, Any]]
    
    # Gatekeeper Outcomes
    escalated: bool
    escalation_reason: Optional[str]
    approved: bool
    commit_message: Optional[str]