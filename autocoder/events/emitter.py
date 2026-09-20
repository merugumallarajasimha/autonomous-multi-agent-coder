# autocoder/events/emitter.py
from datetime import datetime
from typing import Optional

from autocoder.events.models import AgentEvent, EVENT_TYPES


# In-memory event log
_event_log: list[AgentEvent] = []


def emit(
    agent: str,
    event: str,
    status: str = "info",
    message: str = "",
    metadata: Optional[dict] = None,
) -> AgentEvent:
    """Record an event to the in-memory log.
    
    Args:
        agent: Name of the agent emitting the event (e.g., "planner", "coder")
        event: Event type from EVENT_TYPES
        status: Status string (e.g., "info", "success", "error", "warning")
        message: Human-readable message
        metadata: Optional additional structured data
    
    Returns:
        The created AgentEvent dict
    
    Raises:
        ValueError: If event is not in EVENT_TYPES
    """
    if event not in EVENT_TYPES:
        raise ValueError(f"Invalid event type: {event!r}. Must be one of {sorted(EVENT_TYPES)}")
    
    event_dict: AgentEvent = {
        "timestamp": datetime.utcnow().isoformat(),
        "agent": agent,
        "event": event,
        "status": status,
        "message": message,
        "metadata": metadata or {},
    }
    
    _event_log.append(event_dict)
    return event_dict


def get_events() -> list[AgentEvent]:
    """Return a copy of the current event log."""
    return _event_log.copy()


def clear_events() -> None:
    """Clear the event log (call at start of each new task run)."""
    _event_log.clear()