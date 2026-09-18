from typing import TypedDict
from langgraph.graph import StateGraph, END
from agents.planner import planner_node
from agents.coder import coder_node
from agents.verifier import verifier_node
from agents.reviewer import reviewer_node
from agents.git_agent import git_checkout_node, git_commit_node

class AgentState(TypedDict):
    user_request: str
    repo_path: str
    plan: list[str]
    target_files: list[str]
    test_passed: bool
    test_logs: str
    iteration_count: int
    is_refactored: bool
    branch: str
    committed: bool
    history: list[dict]

def route_verifier(state: AgentState) -> str:
    if state.get("test_passed", False):
        if state.get("is_refactored", False):
            print("\n[Router] Post-refactor tests PASSED! Proceeding to Git Commit.")
            return "git_commit"
        print("\n[Router] Tests PASSED! Passing code to Reviewer for refactoring.")
        return "reviewer"
    
    if state.get("iteration_count", 0) >= 3:
        print(f"\n[Router] Max iterations ({state.get('iteration_count')}) reached. Halting.")
        return END

    print(f"\n[Router] Tests FAILED (Attempt {state.get('iteration_count', 0)})! Routing back to Coder.")
    return "coder"

builder = StateGraph(AgentState)

# Add Nodes
builder.add_node("git_checkout", git_checkout_node)
builder.add_node("planner", planner_node)
builder.add_node("coder", coder_node)
builder.add_node("verifier", verifier_node)
builder.add_node("reviewer", reviewer_node)
builder.add_node("git_commit", git_commit_node)

# Flow Setup
builder.set_entry_point("git_checkout")
builder.add_edge("git_checkout", "planner")
builder.add_edge("planner", "coder")
builder.add_edge("coder", "verifier")
builder.add_edge("reviewer", "verifier")
builder.add_edge("git_commit", END)

builder.add_conditional_edges(
    "verifier",
    route_verifier,
    {
        "coder": "coder",
        "reviewer": "reviewer",
        "git_commit": "git_commit",
        END: END
    }
)

app = builder.compile()

if __name__ == "__main__":
    initial_state = {
        "user_request": "Build a multi-file calculator module with math_ops.py, validator.py, and test_calculator.py covering add, subtract, multiply, and divide with zero-division error handling.",
        "repo_path": "./target_repo",
        "plan": [],
        "target_files": [],
        "test_passed": False,
        "test_logs": "",
        "iteration_count": 0,
        "is_refactored": False,
        "branch": "",
        "committed": False,
        "history": []
    }
    
    print("Executing Phase 5: Multi-File Complex Module Generation...")
    result = app.invoke(initial_state)
    print("\nExecution Completed!")
    
    for idx, step in enumerate(result["history"]):
        print(f"Step {idx+1}: {step}")