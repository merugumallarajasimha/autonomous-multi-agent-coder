# autocoder/events/models.py
from typing import TypedDict, frozenset


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
])