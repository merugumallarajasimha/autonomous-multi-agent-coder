from typing import Dict, Any, List, Callable
from langgraph.graph import StateGraph, END
from autocoder.state import AgentState


def build_node_registry() -> Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]]:
    """Returns the full mapping of every possible node name to its function,
    importing from the existing agent files. This is the single source of
    truth for 'what node names exist' — used by both build_graph_from_workflow
    and validate_workflow from the config loader."""
    from autocoder.agents.planner import planner_node
    from autocoder.agents.coder import coder_node
    from autocoder.agents.fixer import fixer_node
    from autocoder.agents.verifier import verifier_node
    from autocoder.agents.reviewer import reviewer_node
    from autocoder.agents.security_reviewer import security_reviewer_node
    from autocoder.agents.refactorer import refactorer_node
    from autocoder.agents.git_node import git_approval_node

    return {
        "planner": planner_node,
        "coder": coder_node,
        "fixer": fixer_node,
        "verifier": verifier_node,
        "reviewer": reviewer_node,
        "security_reviewer": security_reviewer_node,
        "refactorer": refactorer_node,
        "git_approval": git_approval_node,
        "create_checkpoint": _create_checkpoint_node,
        "escalate": _escalate_node,
        "findings_router": _findings_router_node,
        "human_approval": _human_approval_node,
        "check_more_findings": _check_more_findings_node,
        "process_findings": _process_findings_node,
    }


def build_graph_from_workflow(
    workflow: List[str],
    node_registry: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]]
) -> StateGraph:
    """Takes an ordered list of node names (from load_workflow()) and a
    node_registry dict mapping name -> actual node function, and builds a
    LangGraph StateGraph by adding nodes in that order and connecting them
    with add_edge() sequentially, EXCEPT at points where the current main.py
    has conditional routing (verifier -> fixer or reviewer, reviewer ->
    fixer or done) — at those specific points, replicate the exact same
    conditional edge functions from main.py rather than a plain sequential
    edge, so behavior for those nodes is unchanged regardless of what config
    is loaded.

    If a node name in the workflow list isn't in node_registry, raise a
    clear ValueError naming the missing node — do not skip it silently."""
    for node_name in workflow:
        if node_name not in node_registry:
            raise ValueError(f"Node '{node_name}' not found in node registry. Available nodes: {list(node_registry.keys())}")

    workflow_graph = StateGraph(AgentState)

    for node_name in workflow:
        workflow_graph.add_node(node_name, node_registry[node_name])

    workflow_graph.set_entry_point(workflow[0])

    for i in range(len(workflow) - 1):
        current = workflow[i]
        next_node = workflow[i + 1]

        if current == "verifier":
            workflow_graph.add_conditional_edges(
                current,
                _route_after_verifier,
                {
                    "fixer": "fixer",
                    "reviewer": "reviewer",
                    "git_approval": "git_approval",
                    "escalate": "escalate",
                }
            )
        elif current == "reviewer":
            workflow_graph.add_conditional_edges(
                current,
                _route_after_reviewer,
                {"security_reviewer": "security_reviewer"}
            )
        elif current == "security_reviewer":
            workflow_graph.add_conditional_edges(
                current,
                _route_after_security_reviewer,
                {"findings_router": "findings_router"}
            )
        elif current == "findings_router":
            workflow_graph.add_conditional_edges(
                current,
                _route_from_findings_router,
                {
                    "process_findings": "process_findings",
                    "git_approval": "git_approval"
                }
            )
        elif current == "process_findings":
            workflow_graph.add_conditional_edges(
                current,
                _route_process_findings,
                {
                    "fixer": "fixer",
                    "human_approval": "human_approval",
                    "refactorer": "refactorer",
                    "git_approval": "git_approval"
                }
            )
        elif current == "human_approval":
            workflow_graph.add_conditional_edges(
                current,
                _route_after_human_approval,
                {
                    "fixer": "fixer",
                    "refactorer": "refactorer",
                    "check_more_findings": "check_more_findings"
                }
            )
        elif current == "check_more_findings":
            workflow_graph.add_conditional_edges(
                current,
                _route_check_more_findings,
                {
                    "process_findings": "process_findings",
                    "reverify": "create_checkpoint",
                }
            )
        elif current == "fixer":
            if next_node == "create_checkpoint":
                workflow_graph.add_edge(current, next_node)
            else:
                workflow_graph.add_edge(current, "check_more_findings")
        elif current == "refactorer":
            workflow_graph.add_edge(current, "check_more_findings")
        elif current == "git_approval" or current == "escalate":
            pass
        else:
            workflow_graph.add_edge(current, next_node)

    return workflow_graph.compile()


# Conditional edge functions (replicated from main.py)
def _route_after_verifier(state: AgentState) -> str:
    if state.get("iteration_count", 0) >= state.get("max_iterations", 3) and not state.get("test_passed", False):
        return "escalate"
    if state.get("test_passed", False):
        if state.get("all_reviews_done", False):
            return "git_approval"
        return "reviewer"
    else:
        return "fixer"


def _route_after_reviewer(state: AgentState) -> str:
    return "security_reviewer"


def _route_after_security_reviewer(state: AgentState) -> str:
    return "findings_router"


def _route_from_findings_router(state: AgentState) -> str:
    routed = state.get("routed_findings", {})
    has_fixer = len(routed.get("fixer", [])) > 0
    has_security_fixer = len(routed.get("security_fixer", [])) > 0
    has_refactorer = len(routed.get("refactorer", [])) > 0
    if has_fixer or has_security_fixer or has_refactorer:
        return "process_findings"
    else:
        return "git_approval"


def _route_process_findings(state: AgentState) -> str:
    target = state.get("current_fix_target")
    if not target:
        return "git_approval"
    category = target.get("category")
    if category == "bug":
        return "fixer"
    elif category == "security":
        return "human_approval"
    elif category == "refactor":
        if _requires_human_approval(target):
            return "human_approval"
        return "refactorer"
    return "git_approval"


def _route_after_human_approval(state: AgentState) -> str:
    target = state.get("current_fix_target")
    if not target:
        return "check_more_findings"
    category = target.get("category")
    if category == "bug":
        return "fixer"
    elif category == "security":
        return "fixer"
    elif category == "refactor":
        return "refactorer"
    return "check_more_findings"


def _route_check_more_findings(state: AgentState) -> str:
    pending = state.get("pending_approval", [])
    routed = state.get("routed_findings", {})
    if pending:
        return "process_findings"
    for category in ["security_fixer", "fixer", "refactorer"]:
        findings = routed.get(category, [])
        for finding in findings:
            if not _requires_human_approval(finding):
                return "process_findings"
    return "reverify"


# Inline node functions (replicated from main.py)
def _create_checkpoint_node(state: AgentState) -> Dict[str, Any]:
    from autocoder.tools.git_checkpoint import create_checkpoint
    from autocoder.events.emitter import emit
    repo_path = state["repo_path"]
    iteration = state.get("iteration_count", 0)
    is_first_run = iteration == 0
    if not is_first_run:
        emit(agent="workflow", event="ITERATION_STARTED", message=f"Starting fix iteration {iteration}", metadata={"iteration": iteration})
    label = "pre-coder" if is_first_run else f"pre-coder-retry-{iteration}"
    checkpoint_hash = create_checkpoint(repo_path, label)
    updates = {"last_checkpoint": checkpoint_hash, "history": state.get("history", []) + [{"agent": "checkpoint", "hash": checkpoint_hash}]}
    if is_first_run:
        updates["first_checkpoint"] = checkpoint_hash
    return updates


def _escalate_node(state: AgentState) -> Dict[str, Any]:
    from autocoder.tools.git_checkpoint import rollback_checkpoint
    from autocoder.events.emitter import emit
    repo_path = state["repo_path"]
    first_cp = state.get("first_checkpoint")
    if not first_cp:
        return {"history": state.get("history", []) + [{"agent": "escalate", "status": "no_checkpoint_to_rollback"}]}
    result = rollback_checkpoint(repo_path, first_cp)
    emit(agent="workflow", event="ROLLBACK", message=f"Rolled back to checkpoint {first_cp[:8]}", metadata={"checkpoint": first_cp, "success": result["success"]})
    status = "rolled_back" if result["success"] else f"rollback_failed: {result['message']}"
    return {"history": state.get("history", []) + [{"agent": "escalate", "status": status}]}


def _findings_router_node(state: AgentState) -> Dict[str, Any]:
    from autocoder.routing.finding_router import route_findings, requires_human_approval
    from autocoder.events.emitter import emit
    emit(agent="workflow", event="FINDINGS_ROUTER_STARTED", message="Routing findings to handlers")
    review_findings = state.get("review_findings", [])
    security_findings = state.get("security_findings", [])
    all_findings = review_findings + security_findings
    routed = route_findings(all_findings)
    pending_approval = []
    current_target = None
    for category in ["security_fixer", "fixer", "refactorer"]:
        findings = routed.get(category, [])
        for finding in findings:
            if requires_human_approval(finding):
                pending_approval.append(finding)
            elif current_target is None:
                current_target = finding
    if current_target is None and pending_approval:
        current_target = pending_approval[0]
    emit(agent="workflow", event="FINDINGS_ROUTED", message=f"Routed findings: fixer={len(routed.get('fixer', []))}, security_fixer={len(routed.get('security_fixer', []))}, refactorer={len(routed.get('refactorer', []))}, report_only={len(routed.get('report_only', []))}")
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


def _human_approval_node(state: AgentState) -> Dict[str, Any]:
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
        pending = state.get("pending_approval", [])
        if target in pending:
            pending.remove(target)
        return {
            "approved": False,
            "pending_approval": pending,
            "history": state.get("history", []) + [{"agent": "human_approval", "status": "rejected", "finding": target}],
        }


def _check_more_findings_node(state: AgentState) -> Dict[str, Any]:
    from autocoder.routing.finding_router import requires_human_approval
    routed = state.get("routed_findings", {})
    pending = state.get("pending_approval", [])
    current_target = None
    if pending:
        current_target = pending[0]
    else:
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


def _process_findings_node(state: AgentState) -> Dict[str, Any]:
    return {"history": state.get("history", []) + [{"agent": "process_findings", "target": state.get("current_fix_target", {}).get("file") if state.get("current_fix_target") else None}]}


def _requires_human_approval(finding: Dict[str, Any]) -> bool:
    from autocoder.routing.finding_router import requires_human_approval
    return requires_human_approval(finding)