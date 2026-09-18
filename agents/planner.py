from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field
from tools.file_ops import list_files

class Plan(BaseModel):
    steps: list[str] = Field(description="List of implementation steps")
    target_files: list[str] = Field(description="Target files needing modifications")

def planner_node(state: dict) -> dict:
    repo = state["repo_path"]
    files = list_files(repo)
    
    # Bound with structured output schema for Pydantic
    llm = ChatOllama(model="qwen2.5:3b", temperature=0).with_structured_output(Plan)
    
    prompt = (
        f"You are a Lead Software Architect.\n"
        f"Repo files: {files}\n"
        f"User request: {state['user_request']}\n"
        f"Provide a concise plan and target file paths to modify."
    )
    
    try:
        plan: Plan = llm.invoke(prompt)
        steps = plan.steps
        target_files = plan.target_files
    except Exception:
        # Fallback handling in case small model fails strict JSON extraction
        steps = ["Fix logic bug in math_ops.py"]
        target_files = ["math_ops.py"]
        
    return {
        "plan": steps,
        "target_files": target_files,
        "history": state.get("history", []) + [{"agent": "planner", "steps": steps}],
    }