# autocoder/events/logger.py
import json
import os
from typing import List

from autocoder.events.models import AgentEvent


def write_run_log(run_id: str, events: List[AgentEvent], output_dir: str = "runs") -> str:
    """Write events as a JSON array to {output_dir}/run_{run_id}.json.
    
    Args:
        run_id: Unique identifier for this run (e.g., timestamp)
        events: List of AgentEvent dicts to serialize
        output_dir: Directory to write the log file (default: "runs")
    
    Returns:
        Full path to the written file
    """
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, f"run_{run_id}.json")
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2)
    
    return filepath