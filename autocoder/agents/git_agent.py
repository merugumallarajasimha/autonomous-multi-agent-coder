from tools.git_ops import commit_changes
from tools.git_ops import create_branch
from autocoder.tools.file_ops import list_files

def git_checkout_node(state: dict) -> dict:
    repo = state["repo_path"]
    branch_name = "ai-fix-branch"
    create_branch(repo, branch_name)
    return {
        "branch": branch_name,
        "history": state.get("history", []) + [{"agent": "git", "action": f"Checked out {branch_name}"}]
    }

def git_commit_node(state: dict) -> dict:
    repo = state["repo_path"]
    commit_msg = f"fix(agent): auto-resolved task - {state['user_request']}"
    success = commit_changes(repo, commit_msg)
    return {
        "committed": success,
        "history": state.get("history", []) + [{"agent": "git", "action": f"Committed: {commit_msg}"}]
    }