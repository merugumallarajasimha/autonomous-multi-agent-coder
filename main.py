import os
import sys

# Ensure project root directory is added to sys.path for autocoder module imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Ensure workspace is in Python path for local test execution
workspace_path = os.path.abspath("./workspace")
if workspace_path not in sys.path:
    sys.path.insert(0, workspace_path)

from typing import Any, Dict, List, TypedDict
from langgraph.graph import END, StateGraph

# Import node implementations
from autocoder.agents.coder import coder_node
from autocoder.agents.fixer import fixer_node
from autocoder.agents.planner import planner_node
from autocoder.agents.reviewer import reviewer_node
from autocoder.agents.verifier import verifier_node
from autocoder.events.emitter import get_events
from autocoder.reporting.summary import render_summary_report


# 1. Define Agent State Schema
class AgentState(TypedDict, total=False):
    user_prompt: str
    user_request: str
    repo_path: str
    plan: Any
    written_files: List[str]
    is_refactored: bool
    verification_passed: bool
    test_passed: bool
    test_logs: str
    history: List[Dict[str, Any]]
    git_approval: bool
    iteration_count: int
    max_iterations: int
    review_findings: List[Dict[str, Any]]


# Dummy/Placeholder node for git approval step
def git_approval_node(state: AgentState) -> Dict[str, Any]:
    """Handles git approval/commit logic before completion."""
    print("📌 Git Approval Node: Execution complete.")
    return {"git_approval": True}


# Helper node to guarantee prompt normalization
def normalize_input(state: AgentState) -> Dict[str, Any]:
    """Ensures user_prompt and user_request state keys are synced."""
    prompt = state.get("user_prompt") or state.get("user_request") or ""
    return {
        "user_prompt": prompt,
        "user_request": prompt,
        "iteration_count": state.get("iteration_count", 0),
        "max_iterations": state.get("max_iterations", 3),
        "written_files": state.get("written_files", []),
    }


# 2. Build and Compile the LangGraph Workflow
def build_graph():
    workflow = StateGraph(AgentState)

    # Add Nodes
    workflow.add_node("normalize_input", normalize_input)
    workflow.add_node("planner", planner_node)
    workflow.add_node("coder", coder_node)
    workflow.add_node("verifier", verifier_node)
    workflow.add_node("reviewer", reviewer_node)
    workflow.add_node("fixer", fixer_node)
    workflow.add_node("git_approval", git_approval_node)

    # Set Entry Point
    workflow.set_entry_point("normalize_input")

    # Linear Edges (NEW ORDER: Coder -> Verifier -> Reviewer)
    workflow.add_edge("normalize_input", "planner")
    workflow.add_edge("planner", "coder")
    workflow.add_edge("coder", "verifier")

    # Conditional Routing after Verifier (unchanged logic)
    def decide_after_verifier(state: AgentState) -> str:
        passed = state.get("verification_passed", False) or state.get("test_passed", False)
        iteration = state.get("iteration_count", 0)
        max_iterations = state.get("max_iterations", 3)

        if passed:
            print("✅ Verification passed. Proceeding to Reviewer.")
            return "reviewer"

        if iteration >= max_iterations:
            print(f"⚠️ Max iterations reached ({iteration}/{max_iterations}). Halting retry loop.")
            return "git_approval"

        print(f"🔄 Verification failed. Routing to Fixer Agent (Attempt {iteration + 1}/{max_iterations})...")
        return "fixer"

    workflow.add_conditional_edges(
        "verifier",
        decide_after_verifier,
        {
            "reviewer": "reviewer",
            "fixer": "fixer",
            "git_approval": "git_approval",
        },
    )

    # Conditional Routing after Reviewer (NEW: route high/critical findings to Fixer)
    def decide_after_reviewer(state: AgentState) -> str:
        findings = state.get("review_findings", [])
        has_high_or_critical = any(
            f.get("severity", "").lower() in ("high", "critical") for f in findings
        )

        if has_high_or_critical:
            print(f"🔍 Reviewer found {len([f for f in findings if f.get('severity', '').lower() in ('high', 'critical')])} high/critical issue(s). Routing to Fixer.")
            return "fixer"

        print("✅ Reviewer passed. Proceeding to Git approval.")
        return "git_approval"

    workflow.add_conditional_edges(
        "reviewer",
        decide_after_reviewer,
        {
            "fixer": "fixer",
            "git_approval": "git_approval",
        },
    )

    # Loop Fixer back to Verifier (re-verify after fix)
    workflow.add_edge("fixer", "verifier")
    workflow.add_edge("git_approval", END)

    return workflow.compile()


# Export compiled app instance for main_api.py
app = build_graph()


def _build_run_report(final_state: Dict[str, Any]) -> Dict[str, Any]:
    """Assemble run report from final graph state and event log."""
    events = get_events()
    
    # Determine overall status
    test_passed = final_state.get("test_passed", False)
    git_approval = final_state.get("git_approval", False)
    history = final_state.get("history", [])
    escalated = any(step.get("agent") == "escalate" for step in history)
    
    if escalated:
        status = "ESCALATED"
    elif test_passed and git_approval:
        status = "SUCCESS"
    elif test_passed:
        status = "PARTIAL (tests passed, awaiting approval)"
    else:
        status = "FAILED"
    
    # Count tasks completed (agents that finished)
    tasks_completed = len(set(step.get("agent") for step in history if step.get("agent")))
    
    # Files modified
    files_modified = final_state.get("written_files", [])
    
    # Test results
    tests_passed = 1 if final_state.get("test_passed") else 0
    tests_failed = 0 if final_state.get("test_passed") else 1
    
    # Fix iterations
    fix_iterations = final_state.get("iteration_count", 0)
    
    # Review issues resolved
    review_findings = final_state.get("review_findings", [])
    review_issues_resolved = len([f for f in review_findings if f.get("severity", "").lower() in ("high", "critical")])
    
    # Determine sandbox type from events
    sandbox_type = "Docker"
    for event in events:
        if "host" in event.get("message", "").lower() or "fallback" in event.get("message", "").lower():
            sandbox_type = "Host"
            break
    
    # Git status
    if git_approval:
        git_status = "Approved & committed"
    elif final_state.get("git_approval") is not None:
        git_status = "Awaiting approval"
    else:
        git_status = "N/A"
    
    return {
        "status": status,
        "tasks_completed": tasks_completed,
        "files_modified": files_modified,
        "tests_passed": tests_passed,
        "tests_failed": tests_failed,
        "fix_iterations": fix_iterations,
        "review_issues_resolved": review_issues_resolved,
        "sandbox_type": sandbox_type,
        "git_status": git_status,
    }


# 3. Direct Execution Block
if __name__ == "__main__":
    sample_state: AgentState = {
        "user_prompt": "Add a multiply(a, b) function to math_utils.py with unit tests.",
        "repo_path": "./workspace",
        "history": [],
        "iteration_count": 0,
        "max_iterations": 3,
    }

    print("🚀 Running Autonomous Multi-Agent Graph...")
    result = app.invoke(sample_state)
    print("\n🏁 Workflow Execution Completed:")
    print(result)
    
    # Generate and print summary report
    run_report = _build_run_report(result)
    summary = render_summary_report(run_report)
    print("\n" + summary)