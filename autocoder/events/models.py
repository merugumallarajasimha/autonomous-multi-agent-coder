# autocoder/events/models.py
from typing import TypedDict, FrozenSet

class AgentEvent(TypedDict):
    """Represents a single event in the agent workflow lifecycle.
    
    Timestamp format: datetime.utcnow().isoformat() (e.g. '2026-09-20T07:13:19.123456')
    This provides ISO 8601 UTC timestamps with microsecond precision,
    suitable for sorting and cross-system correlation.
    """
    timestamp: str
    agent: str
    event: str
    status: str
    message: str
    metadata: dict


# Canonical event types used throughout the workflow. Do not add or rename.
EVENT_TYPES: frozenset[str] = frozenset([
    "AGENT_STARTED",
    "AGENT_FINISHED",
    "READING_REPOSITORY",
    "READING_FILE",
    "PLANNING",
    "PLAN_CREATED",
    "GENERATING_CODE",
    "FILE_CREATED",
    "FILE_MODIFIED",
    "RUNNING_BUILD",
    "RUNNING_TESTS",
    "TEST_FAILED",
    "TEST_PASSED",
    "ANALYZING_FAILURE",
    "APPLYING_FIX",
    "REVIEW_STARTED",
    "REVIEW_FINDING",
    "ROLLBACK",
    "ITERATION_STARTED",
    "WORKFLOW_COMPLETED",
    "BUILDING_REPO_MAP",
    "REPO_MAP_FAILED",
    "RELEVANCE_FALLBACK",
    "RELEVANCE_FILTERED",
    "PLANNING",
    "STATIC_CHECKS_STARTED",
    "STATIC_CHECKS_COMPLETED",
    "LLM_REVIEW_STARTED",
    "LLM_REVIEW_COMPLETED",
    "LLM_REVIEW_ERROR",
    "VALIDATION_DROPPED",
    "REVIEW_COMPLETED",
    "SECURITY_STATIC_CHECKS_STARTED",
    "SECURITY_STATIC_CHECKS_COMPLETED",
    "LLM_SECURITY_REVIEW_STARTED",
    "LLM_SECURITY_REVIEW_COMPLETED",
    "LLM_SECURITY_REVIEW_ERROR",
    "SECURITY_REVIEW_COMPLETED",
    "SECURITY_FINDING",
    "FINDINGS_ROUTER_STARTED",
    "FINDINGS_ROUTED",
    "REPORT_ONLY_FINDING",
    "REFRACTOR_LLM_ERROR",
    "NO_REFACTOR_FINDINGS",
    "PROCESSING_FINDINGS",
    "SKIPPED_FINDING",
    "APPLYING_REFACTOR",
])