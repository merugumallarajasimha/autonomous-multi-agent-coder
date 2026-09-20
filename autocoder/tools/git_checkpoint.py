# autocoder/tools/git_checkpoint.py
import subprocess
import os
from typing import Dict


def _run_git(repo_path: str, *args: str) -> subprocess.CompletedProcess:
    """Run a git command in repo_path, return CompletedProcess."""
    if not os.path.isdir(os.path.join(repo_path, ".git")):
        raise RuntimeError(f"Not a git repository: {repo_path}")
    return subprocess.run(
        ["git", *args],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )


def create_checkpoint(repo_path: str, label: str = "") -> str:
    """Stages and commits all current changes in repo_path as a checkpoint commit.
    Returns the commit hash. If there are no changes to commit, still return the
    current HEAD hash without creating an empty commit."""
    # Check if there are any changes (staged or unstaged)
    status = _run_git(repo_path, "status", "--porcelain")
    if status.stdout.strip() == "":
        # No changes - return current HEAD
        head = _run_git(repo_path, "rev-parse", "HEAD")
        return head.stdout.strip()

    # Stage all changes
    add_result = _run_git(repo_path, "add", "-A")
    if add_result.returncode != 0:
        raise RuntimeError(f"git add failed: {add_result.stderr}")

    # Build commit message
    msg = f"checkpoint: {label}" if label else "checkpoint"
    commit_result = _run_git(repo_path, "commit", "-m", msg)
    if commit_result.returncode != 0:
        raise RuntimeError(f"git commit failed: {commit_result.stderr}")

    # Return new commit hash
    head = _run_git(repo_path, "rev-parse", "HEAD")
    return head.stdout.strip()


def get_diff(repo_path: str, checkpoint_hash: str) -> str:
    """Returns the full git diff between checkpoint_hash and the current working
    tree state as a string."""
    diff_result = _run_git(repo_path, "diff", checkpoint_hash)
    if diff_result.returncode != 0:
        raise RuntimeError(f"git diff failed: {diff_result.stderr}")
    return diff_result.stdout


def rollback_checkpoint(repo_path: str, checkpoint_hash: str) -> Dict[str, object]:
    """Hard-resets repo_path to checkpoint_hash, discarding all changes made after
    it. Returns {"success": bool, "message": str}. This is destructive by design —
    do not add a confirmation prompt inside this function, the caller is
    responsible for deciding when to call it."""
    reset_result = _run_git(repo_path, "reset", "--hard", checkpoint_hash)
    if reset_result.returncode != 0:
        return {"success": False, "message": f"git reset failed: {reset_result.stderr}"}
    return {"success": True, "message": f"Hard reset to {checkpoint_hash}"}


def restore_checkpoint(repo_path: str, checkpoint_hash: str) -> Dict[str, object]:
    """Like rollback_checkpoint, but creates a new commit that reverts to the
    checkpoint state instead of hard-resetting history (non-destructive, keeps
    history intact). Returns {"success": bool, "message": str}."""
    # Use git checkout to get the tree at checkpoint_hash, then commit it
    # First, get the tree hash
    tree_result = _run_git(repo_path, "rev-parse", f"{checkpoint_hash}^{{tree}}")
    if tree_result.returncode != 0:
        return {"success": False, "message": f"Failed to get tree: {tree_result.stderr}"}
    tree_hash = tree_result.stdout.strip()

    # Read the tree into the index
    read_tree_result = _run_git(repo_path, "read-tree", tree_hash)
    if read_tree_result.returncode != 0:
        return {"success": False, "message": f"git read-tree failed: {read_tree_result.stderr}"}

    # Create a commit from the index
    msg = f"restore: revert to checkpoint {checkpoint_hash[:8]}"
    commit_result = _run_git(repo_path, "commit", "-m", msg)
    if commit_result.returncode != 0:
        return {"success": False, "message": f"git commit failed: {commit_result.stderr}"}

    return {"success": True, "message": f"Created restore commit reverting to {checkpoint_hash}"}