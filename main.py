import os
import json
import argparse
from datetime import datetime
from typing import TypedDict, List, Dict, Any, Optional

from langgraph.graph import StateGraph, END

# Import config-driven graph builder and node registry
from autocoder.graph_builder import build_graph_from_workflow, build_node_registry
from autocoder.config.loader import load_workflow

# Import nodes from package structure (kept for --legacy-graph path)
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
from autocoder.agents.security_reviewer import security_reviewer_node
# pyrefly: ignore [missing-import]
from autocoder.agents.refactorer import refactorer_node
# pyrefly: ignore [missing-import]
from autocoder.agents.git_node import git_approval_node

# Import routing and utilities
from autocoder.routing.finding_router import route_findings, requires_human_approval
from autocoder.tools.git_tools import generate_pr_summary
from autocoder.tools.git_checkpoint import create_checkpoint, rollback_checkpoint
from autocoder.events.emitter import emit, clear_events
from autocoder.models.router import ModelRouter

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
    security_findings: List[Dict[str, Any]]          # New: from security_reviewer
    all_findings: List[Dict[str, Any]]               # New: combined findings
    routed_findings: Dict[str, List[Dict[str, Any]]]  # New: output of route_findings()
    pending_approval: List[Dict[str, Any]]            # New: findings awaiting human approval
    current_fix_target: Optional[Dict[str, Any]]      # New: finding currently being fixed
    all_reviews_done: bool                            # New: flag when both reviewers complete
    first_checkpoint: Optional[str]                   # Checkpoint before FIRST coder run
    last_checkpoint: Optional[str]                    # Checkpoint before most recent coder run

# Routing Logic
def route_after_verifier(state: AgentState) -> str:
    # Max iteration cap to prevent infinite retry loops
    if state.get("iteration_count", 0) >= state.get("max_iterations", 3) and not state.get("test_passed", False):
        print("\n[Router] Max iteration limit reached. Routing to escalation (rollback).")
        return "escalate"

    if state.get("test_passed", False):
        # Tests passed - check if we've already done the review cycle
        if state.get("all_reviews_done", False):
            # Already completed review + re-verification, go to git approval
            return "git_approval"
        # First time tests pass - route to reviewer (then security_reviewer)
        return "reviewer"
    else:
        print("\n[Router] Tests failed! Routing to Fixer node for surgical patch.")
        return "fixer"


def route_after_reviewer(state: AgentState) -> str:
    """After reviewer completes, route to security_reviewer."""
    return "security_reviewer"


def route_after_security_reviewer(state: AgentState) -> str:
    """After security_reviewer completes, route to findings_router."""
    return "findings_router"


def route_from_findings_router(state: AgentState) -> str:
    """Route based on what findings need action."""
    routed = state.get("routed_findings", {})
    pending = state.get("pending_approval", [])
    
    # Check if there are any actionable findings
    has_fixer = len(routed.get("fixer", [])) > 0
    has_security_fixer = len(routed.get("security_fixer", [])) > 0
    has_refactorer = len(routed.get("refactorer", [])) > 0
    
    if has_fixer or has_security_fixer or has_refactorer:
        # There are findings to act on - findings_router will set up pending_approval
        # and current_fix_target, then we route to the appropriate handler
        return "process_findings"
    else:
        # Only report_only findings or no findings - go to git approval
        return "git_approval"


def route_process_findings(state: AgentState) -> str:
    """Route to the appropriate handler for the current finding."""
    target = state.get("current_fix_target")
    if not target:
        # No more findings to process
        return "git_approval"
    
    category = target.get("category")
    if category == "bug":
        return "fixer"
    elif category == "security":
        return "human_approval"  # Security ALWAYS goes through approval
    elif category == "refactor":
        # Check confidence gate
        if requires_human_approval(target):
            return "human_approval"
        return "refactorer"
    
    return "git_approval"


def route_after_human_approval(state: AgentState) -> str:
    """After human approval, route to appropriate fixer/refactorer."""
    target = state.get("current_fix_target")
    if not target:
        return "check_more_findings"
    
    category = target.get("category")
    if category == "bug":
        return "fixer"
    elif category == "security":
        # Security findings go to fixer (same node handles the fix)
        return "fixer"
    elif category == "refactor":
        return "refactorer"
    
    return "check_more_findings"


def route_check_more_findings(state: AgentState) -> str:
    """Check if there are more findings to process."""
    pending = state.get("pending_approval", [])
    routed = state.get("routed_findings", {})
    
    # First check pending approvals
    if pending:
        return "process_findings"
    
    # Check routed findings for any unprocessed actionable findings
    # Look for findings that don't require approval and haven't been processed
    for category in ["security_fixer", "fixer", "refactorer"]:
        findings = routed.get(category, [])
        for finding in findings:
            if not requires_human_approval(finding):
                # This finding hasn't been processed yet
                return "process_findings"
    
    # No more findings to process - go to re-verification (create_checkpoint -> coder -> verifier)
    return "reverify"


def create_checkpoint_node(state: AgentState) -> Dict[str, Any]:
    """Creates a git checkpoint before coder runs. On first run, stores as both
    first_checkpoint and last_checkpoint. On retries, updates only last_checkpoint."""
    repo_path = state["repo_path"]
    iteration = state.get("iteration_count", 0)
    is_first_run = iteration == 0

    # Emit ITERATION_STARTED for retry iterations (not the initial run)
    if not is_first_run:
        emit(agent="workflow", event="ITERATION_STARTED", message=f"Starting fix iteration {iteration}", metadata={"iteration": iteration})

    label = "pre-coder" if is_first_run else f"pre-coder-retry-{iteration}"
    checkpoint_hash = create_checkpoint(repo_path, label)

    updates = {"last_checkpoint": checkpoint_hash, "history": state.get("history", []) + [{"agent": "checkpoint", "hash": checkpoint_hash}]}
    if is_first_run:
        updates["first_checkpoint"] = checkpoint_hash

    return updates


def escalate_node(state: AgentState) -> Dict[str, Any]:
    """Rolls back to the first_checkpoint (pre-task state) when all retries exhausted."""
    repo_path = state["repo_path"]
    first_cp = state.get("first_checkpoint")

    if not first_cp:
        return {"history": state.get("history", []) + [{"agent": "escalate", "status": "no_checkpoint_to_rollback"}]}

    result = rollback_checkpoint(repo_path, first_cp)
    emit(agent="workflow", event="ROLLBACK", message=f"Rolled back to checkpoint {first_cp[:8]}", metadata={"checkpoint": first_cp, "success": result["success"]})
    status = "rolled_back" if result["success"] else f"rollback_failed: {result['message']}"
    return {"history": state.get("history", []) + [{"agent": "escalate", "status": status}]}


def findings_router_node(state: AgentState) -> Dict[str, Any]:
    """Combines review_findings + security_findings, routes them, and sets up
    pending_approval + current_fix_target for the first actionable finding."""
    emit(agent="workflow", event="FINDINGS_ROUTER_STARTED", message="Routing findings to handlers")
    
    # Combine findings from both reviewers
    review_findings = state.get("review_findings", [])
    security_findings = state.get("security_findings", [])
    all_findings = review_findings + security_findings
    
    # Route findings to handlers
    routed = route_findings(all_findings)
    
    # Build pending_approval list and determine first target
    pending_approval = []
    current_target = None
    
    # Process in priority order: security_fixer > fixer > refactorer
    for category in ["security_fixer", "fixer", "refactorer"]:
        findings = routed.get(category, [])
        for finding in findings:
            if requires_human_approval(finding):
                pending_approval.append(finding)
            elif current_target is None:
                current_target = finding
    
    # If no auto-fix target but we have pending approvals, take first pending
    if current_target is None and pending_approval:
        current_target = pending_approval[0]
    
    # Log routing results
    emit(agent="workflow", event="FINDINGS_ROUTED", message=f"Routed findings: fixer={len(routed.get('fixer', []))}, security_fixer={len(routed.get('security_fixer', []))}, refactorer={len(routed.get('refactorer', []))}, report_only={len(routed.get('report_only', []))}")
    
    # Emit report_only findings for final report
    for finding in routed.get("report_only", []):
        emit(agent="workflow", event="REPORT_ONLY_FINDING", message=f"Report-only: {finding['file']}:{finding['line']}", metadata=finding)
    
    return {
        "all_findings": all_findings,
        "routed_findings": routed,
        "pending_approval": pending_approval,
        "current_fix_target": current_target,
        "all_reviews_done": True,
        "history": state.get("history", []) + [{"agent": "findings_router", "routed": {k: len(v) for k, v in routed.items()}}],
    }


def human_approval_node(state: AgentState) -> Dict[str, Any]:
    """Presents a finding to human for approval (y/N), similar to git_approval_node."""
    target = state.get("current_fix_target")
    if not target:
        return {"approved": False}
    
    print(f"\n🔍 Human Approval Required:")
    print(f"  File: {target.get('file', 'unknown')}:{target.get('line', 0)}")
    print(f"  Category: {target.get('category', 'unknown')}")
    print(f"  Severity: {target.get('severity', 'unknown')}")
    print(f"  Description: {target.get('description', 'No description')}")
    print(f"  Suggested Fix: {target.get('suggested_fix', 'No suggestion')}")
    print(f"  Confidence: {target.get('confidence', 0.0):.2f}")
    
    user_approval = input("\nApprove this fix? (y/n): ").strip().lower()
    
    if user_approval in ["y", "yes"]:
        print("✅ Fix approved.")
        # Remove from pending_approval
        pending = state.get("pending_approval", [])
        if target in pending:
            pending.remove(target)
        return {
            "approved": True,
            "pending_approval": pending,
            "history": state.get("history", []) + [{"agent": "human_approval", "status": "approved", "finding": target}],
        }
    else:
        print("❌ Fix rejected by user. Skipping.")
        # Remove from pending_approval
        pending = state.get("pending_approval", [])
        if target in pending:
            pending.remove(target)
        return {
            "approved": False,
            "pending_approval": pending,
            "history": state.get("history", []) + [{"agent": "human_approval", "status": "rejected", "finding": target}],
        }


def check_more_findings_node(state: AgentState) -> Dict[str, Any]:
    """After a fix/refactor, clear current_fix_target and find the next one."""
    routed = state.get("routed_findings", {})
    pending = state.get("pending_approval", [])
    
    # Clear current target
    current_target = None
    
    # First check pending approvals
    if pending:
        current_target = pending[0]
    else:
        # Check routed findings for next unprocessed one
        # Simple strategy: look through each category in priority order
        for category in ["security_fixer", "fixer", "refactorer"]:
            findings = routed.get(category, [])
            for finding in findings:
                if not requires_human_approval(finding):
                    current_target = finding
                    break
            if current_target:
                break
    
    return {
        "current_fix_target": current_target,
        "history": state.get("history", []) + [{"agent": "check_more_findings", "next_target": current_target.get("file") if current_target else None}],
    }


def process_findings_node(state: AgentState) -> Dict[str, Any]:
    """Pass-through node - the actual routing is done by the conditional edge
    route_process_findings which reads current_fix_target from state."""
    return {"history": state.get("history", []) + [{"agent": "process_findings", "target": state.get("current_fix_target", {}).get("file") if state.get("current_fix_target") else None}]}


def build_graph_legacy():
    workflow = StateGraph(AgentState)

    # Add Nodes
    workflow.add_node("planner", planner_node)
    workflow.add_node("create_checkpoint", create_checkpoint_node)
    workflow.add_node("coder", coder_node)
    workflow.add_node("fixer", fixer_node)
    workflow.add_node("verifier", verifier_node)
    workflow.add_node("reviewer", reviewer_node)
    workflow.add_node("security_reviewer", security_reviewer_node)
    workflow.add_node("refactorer", refactorer_node)
    workflow.add_node("findings_router", findings_router_node)
    workflow.add_node("human_approval", human_approval_node)
    workflow.add_node("check_more_findings", check_more_findings_node)
    workflow.add_node("process_findings", process_findings_node)
    workflow.add_node("git_approval", git_approval_node)
    workflow.add_node("escalate", escalate_node)

    # Set Entry Point
    workflow.set_entry_point("planner")

    # Connect Edges
    workflow.add_edge("planner", "create_checkpoint")
    workflow.add_edge("create_checkpoint", "coder")
    workflow.add_edge("coder", "verifier")
    workflow.add_edge("fixer", "create_checkpoint")  # On retry, create new checkpoint before coder
    
    # Conditional Routing after Verification
    workflow.add_conditional_edges(
        "verifier",
        route_after_verifier,
        {
            "fixer": "fixer",
            "reviewer": "reviewer",
            "git_approval": "git_approval",
            "escalate": "escalate"
        }
    )
    
    # Review pipeline (sequential: reviewer -> security_reviewer -> findings_router)
    workflow.add_conditional_edges(
        "reviewer",
        route_after_reviewer,
        {"security_reviewer": "security_reviewer"}
    )
    
    workflow.add_conditional_edges(
        "security_reviewer",
        route_after_security_reviewer,
        {"findings_router": "findings_router"}
    )
    
    # Findings router decides what to do next
    workflow.add_conditional_edges(
        "findings_router",
        route_from_findings_router,
        {
            "process_findings": "process_findings",
            "git_approval": "git_approval"
        }
    )
    
    # Process findings: route to appropriate handler based on current_fix_target
    workflow.add_conditional_edges(
        "process_findings",
        route_process_findings,
        {
            "fixer": "fixer",
            "human_approval": "human_approval",
            "refactorer": "refactorer",
            "git_approval": "git_approval"
        }
    )
    
    # After fixer/refactorer, check for more findings
    workflow.add_edge("fixer", "check_more_findings")
    workflow.add_edge("refactorer", "check_more_findings")
    
    # After human approval, route to appropriate handler
    workflow.add_conditional_edges(
        "human_approval",
        route_after_human_approval,
        {
            "fixer": "fixer",
            "refactorer": "refactorer",
            "check_more_findings": "check_more_findings"
        }
    )
    
    # Check more findings loops back to process_findings or goes to re-verification
    workflow.add_conditional_edges(
        "check_more_findings",
        route_check_more_findings,
        {
            "process_findings": "process_findings",
            "reverify": "create_checkpoint",  # Re-test after all fixes applied
        }
    )
    
    workflow.add_edge("git_approval", END)
    workflow.add_edge("escalate", END)

    return workflow.compile()


def build_graph(workflow_name: str = "default"):
    """Build graph from config-driven workflow."""
    node_registry = build_node_registry()
    workflow_list = load_workflow(workflow_name)
    return build_graph_from_workflow(workflow_list, node_registry)

def main():
    parser = argparse.ArgumentParser(description="Autonomous Multi-Agent AI Coding Framework")
    parser.add_argument("--workflow", "-w", default="default", help="Workflow config name (config/workflows/<name>.yaml)")
    parser.add_argument("--legacy-graph", action="store_true", help="Use hardcoded legacy graph construction (for comparison)")
    args = parser.parse_args()

    print("==========================================================")
    print("   Autonomous Multi-Agent AI Coding Framework (Phase 8)   ")
    print("==========================================================")
    print("Type 'exit' or 'quit' to exit the CLI.\n")

    # Initialize ModelRouter with config file, fallback to defaults
    try:
        model_router = ModelRouter.from_config_file()
        print("[Framework] Loaded model config from config/models.yaml")
    except (FileNotFoundError, ValueError) as e:
        print(f"[Framework] Warning: Could not load config/models.yaml ({e}). Falling back to hardcoded defaults.")
        model_router = ModelRouter(ModelRouter.get_default_config())

    # Build graph
    if args.legacy_graph:
        print("[Framework] Using legacy hardcoded graph construction (--legacy-graph)")
        app = build_graph_legacy()
    else:
        print(f"[Framework] Using config-driven graph from workflow: {args.workflow}")
        app = build_graph(args.workflow)

    repo_directory = os.path.abspath("./target_repo")
    os.makedirs(repo_directory, exist_ok=True)

    while True:
        try:
            print("\nEnter your coding task request: ", end="")
            user_input = input().strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit"]:
                print("Exiting framework. Goodbye!")
                break

            clear_events()

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

            print(f"\n[Framework] Initializing state graph for: '{user_input}'")
            final_state = app.invoke(initial_state)

            # Determine workflow outcome
            workflow_success = final_state.get("test_passed", False)
            workflow_escalated = final_state.get("history", []) and any(
                step.get("agent") == "escalate" for step in final_state.get("history", [])
            )
            outcome = "escalated" if workflow_escalated else ("success" if workflow_success else "failed")
            emit(agent="workflow", event="WORKFLOW_COMPLETED", message=f"Workflow {outcome}", metadata={"outcome": outcome, "test_passed": workflow_success, "iterations": final_state.get("iteration_count", 0)})

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