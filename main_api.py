import os
import sys

# Ensure project root directory is added to sys.path for autocoder module imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typing import Any, Dict, List, Optional
# pyrefly: ignore [missing-import]
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Import compiled graph builder
from main import build_graph, _build_run_report
from autocoder.reporting.summary import render_summary_report

app = FastAPI(title="Autonomous Coding Agent API")
graph = build_graph()


class CodeRequest(BaseModel):
    user_prompt: str
    repo_path: str
    workflow: str = "default"


@app.post("/generate")
async def run_agent_workflow(request: CodeRequest):
    initial_state = {
        "user_prompt": request.user_prompt,
        "user_request": request.user_prompt,
        "repo_path": request.repo_path,
        "feature_branch": "main",
        "plan": [],
        "test_passed": False,
        "test_logs": "",
        "static_checks_passed": True,
        "is_refactored": False,
        "iteration_count": 0,
        "max_iterations": 3,
        "approved": False,
        "history": [],
        "bug_report": None,
        "review_findings": [],
        "security_findings": [],
        "all_findings": [],
        "routed_findings": {},
        "pending_approval": [],
        "current_fix_target": None,
        "all_reviews_done": False,
        "first_checkpoint": None,
        "last_checkpoint": None,
    }
    try:
        final_state = graph.invoke(initial_state)
        
        # Build run report and summary
        run_report = _build_run_report(final_state)
        summary_str = render_summary_report(run_report)
        
        return {
            "status": "success",
            "files_changed": final_state.get("written_files", []),
            "test_passed": final_state.get("test_passed", False),
            "test_logs": final_state.get("test_logs", ""),
            "review_findings": final_state.get("review_findings", []),
            "security_findings": final_state.get("security_findings", []),
            "all_findings": final_state.get("all_findings", []),
            "is_refactored": final_state.get("is_refactored", False),
            "history": final_state.get("history", []),
            "iteration_count": final_state.get("iteration_count", 0),
            "summary_report": summary_str,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Windows multiprocessing guard
if __name__ == "__main__":
    # pyrefly: ignore [missing-import]
    import uvicorn

    uvicorn.run("main_api:app", host="127.0.0.1", port=8000, reload=True)