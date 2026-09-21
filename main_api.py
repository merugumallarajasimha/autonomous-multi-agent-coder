from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from main import build_graph

app = FastAPI(title="Autonomous Coding Agent API")
graph = build_graph()

class CodeRequest(BaseModel):
    user_prompt: str
    repo_path: str
    workflow: str = "default"

@app.post("/generate")
async def run_agent_workflow(request: CodeRequest):
    initial_state = {
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
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))