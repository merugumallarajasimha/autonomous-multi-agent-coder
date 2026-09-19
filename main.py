import os
import json
from datetime import datetime
from typing import TypedDict, List, Dict, Any, Optional

from langgraph.graph import StateGraph, END

# Import nodes from package structure
# pyrefly: ignore [missing-import]
from autocoder.agents.planner import planner_node
# pyrefly: ignore [missing-import]
from autocoder.agents.coder import coder_node
# pyrefly: ignore [missing-import]
from autocoder.agents.fixer import fixer_node
# pyrefly: ignore [missing-import]
from autocoder.agents.verifier import verifier_node
# pyrefly: ignore [missing-import]
from autocoder.agents.reviewer import reviewer_node
# pyrefly: ignore [missing-import]
from autocoder.agents.git_node import git_approval_node

# Import Git utilities
from autocoder.tools.git_tools import generate_pr_summary

# Define Graph State Schema
class AgentState(TypedDict):
    user_request: str
    repo_path: str
    feature_branch: Optional[str]  # Added explicit type declaration
    plan: List[str]
    test_passed: bool
    test_logs: str
    static_checks_passed: bool
    is_refactored: bool
    iteration_count: int
    max_iterations: int
    approved: bool
    history: List[Dict[str, Any]]
    bug_report: Optional[Dict[str, Any]]
    review_findings: List[Dict[str, Any]]

# Routing Logic
def route_after_verifier(state: AgentState) -> str:
    # Max iteration cap to prevent infinite retry loops
    if state.get("iteration_count", 0) >= state.get("max_iterations", 3) and not state.get("test_passed", False):
        print("\n[Router] Max iteration limit reached. Stopping fix attempts.")
        return "git_approval"

    if state.get("test_passed", False):
        if state.get("is_refactored", False):
            return "git_approval"
        return "reviewer"
    else:
        print("\n[Router] Tests failed! Routing to Fixer node for surgical patch.")
        return "fixer"

def build_graph():
    workflow = StateGraph(AgentState)

    # Add Nodes
    workflow.add_node("planner", planner_node)
    workflow.add_node("coder", coder_node)
    workflow.add_node("fixer", fixer_node)
    workflow.add_node("verifier", verifier_node)
    workflow.add_node("reviewer", reviewer_node)
    workflow.add_node("git_approval", git_approval_node)

    # Set Entry Point
    workflow.set_entry_point("planner")

    # Connect Edges
    workflow.add_edge("planner", "coder")
    workflow.add_edge("coder", "verifier")
    workflow.add_edge("fixer", "verifier")
    
    # Conditional Routing after Verification
    workflow.add_conditional_edges(
        "verifier",
        route_after_verifier,
        {
            "fixer": "fixer",
            "reviewer": "reviewer",
            "git_approval": "git_approval"
        }
    )
    
    workflow.add_edge("reviewer", "verifier")
    workflow.add_edge("git_approval", END)

    return workflow.compile()

def main():
    print("==========================================================")
    print("   Autonomous Multi-Agent AI Coding Framework (Phase 8)   ")
    print("==========================================================")
    print("Type 'exit' or 'quit' to exit the CLI.\n")

    app = build_graph()
    repo_directory = os.path.abspath("./target_repo")
    os.makedirs(repo_directory, exist_ok=True)

    while True:
        try:
            user_input = input("\nEnter your coding task request: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit"]:
                print("Exiting framework. Goodbye!")
                break

            initial_state: AgentState = {
                "user_request": user_input,
                "repo_path": repo_directory,
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
                "review_findings": []
            }

            print(f"\n[Framework] Initializing state graph for: '{user_input}'")
            final_state = app.invoke(initial_state)

            print("\n==========================================================")
            print("                Workflow Execution Summary                ")
            print("==========================================================")
            for idx, step in enumerate(final_state.get("history", []), 1):
                print(f"Step {idx}: {step}")

            # Generate Auto-PR Summary
            print("\n" + generate_pr_summary(final_state))

            # Save execution trace
            os.makedirs("runs", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            trace_path = f"runs/run_{timestamp}.json"
            with open(trace_path, "w") as f:
                json.dump(final_state, f, indent=2)

            print(f"\n[Framework] Execution trace saved to: {trace_path}")

        except KeyboardInterrupt:
            print("\n[Framework] Interrupted by user. Exiting...")
            break
        except Exception as e:
            print(f"\n[Framework Error]: {e}")

if __name__ == "__main__":
    main()