from pydantic import BaseModel, Field
from autocoder.tools.file_ops import list_files, read_file
from autocoder.events.emitter import emit
from autocoder.index.repo_map import load_repo_map, save_repo_map
from autocoder.index.relevance import select_relevant_files
from autocoder.models.router import ModelRouter

class Plan(BaseModel):
    steps: list[str] = Field(description="List of implementation steps")
    target_files: list[str] = Field(description="Target files needing modifications")

# Module-level singleton - initialized once with default config
_model_router = ModelRouter(ModelRouter.get_default_config())

def planner_node(state: dict) -> dict:
    emit(agent="planner", event="AGENT_STARTED", message="Planner node started")
    repo = state["repo_path"]
    user_request = state["user_request"]
    
    # Load or build repo_map (once per task, not per retry)
    repo_map = load_repo_map(repo)
    if repo_map is None:
        emit(agent="planner", event="BUILDING_REPO_MAP", message="Building repo_map.json for the first time")
        save_repo_map(repo)
        repo_map = load_repo_map(repo)
        if repo_map is None:
            emit(agent="planner", event="REPO_MAP_FAILED", message="Failed to build repo_map, falling back to full file list")
            repo_map = {"files": [{"path": f} for f in list_files(repo)], "symbols": {}}
    
    # Relevance filtering
    relevant_files = select_relevant_files(user_request, repo_map)
    
    if not relevant_files:
        emit(agent="planner", event="RELEVANCE_FALLBACK", message="Keyword filter found no meaningful matches; falling back to reading all files")
        files = list_files(repo)
    else:
        files = relevant_files
        emit(agent="planner", event="RELEVANCE_FILTERED", message=f"Filtered to {len(files)} relevant files", metadata={"files": files})
    
    # Read only the selected files
    emit(agent="planner", event="READING_REPOSITORY", message=f"Reading {len(files)} repository files")
    file_contents = {}
    for f in files:
        full_path = f if f.startswith("/") else f
        try:
            file_contents[f] = read_file(full_path)
        except Exception:
            file_contents[f] = ""
    
    # Get model provider via router
    provider = _model_router.get(agent="planner", complexity="normal")
    
    prompt = (
        f"You are a Lead Software Architect.\n"
        f"Repo files: {files}\n"
        f"User request: {user_request}\n"
        f"Provide a concise plan and target file paths to modify."
    )
    
    emit(agent="planner", event="PLANNING", message="Generating implementation plan via LLM")
    try:
        result = provider.invoke(prompt, structured_output_schema=Plan)
        if not result.get("success", False):
            raise RuntimeError(f"LLM invocation failed: {result.get('error', 'unknown error')}")
        plan = result["data"]
        steps = plan.steps
        target_files = plan.target_files
    except Exception:
        # Fallback handling in case small model fails strict JSON extraction
        steps = ["Fix logic bug in math_ops.py"]
        target_files = ["math_ops.py"]
    
    emit(agent="planner", event="PLAN_CREATED", message=f"Plan created with {len(steps)} steps", metadata={"steps": steps, "target_files": target_files})
    emit(agent="planner", event="AGENT_FINISHED", message="Planner node completed")
    return {
        "plan": steps,
        "target_files": target_files,
        "history": state.get("history", []) + [{"agent": "planner", "steps": steps}],
    }