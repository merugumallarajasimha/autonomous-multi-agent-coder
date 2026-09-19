import subprocess
import os

def init_git_repo(repo_path: str) -> None:
    """Initializes a git repository if one does not exist."""
    repo = os.path.abspath(repo_path)
    if not os.path.exists(os.path.join(repo, ".git")):
        subprocess.run(["git", "init"], cwd=repo, capture_output=True)
        subprocess.run(["git", "config", "user.name", "AI Agent"], cwd=repo, capture_output=True)
        subprocess.run(["git", "config", "user.email", "agent@local.ai"], cwd=repo, capture_output=True)

def create_branch(repo_path: str, branch_name: str) -> None:
    """Creates and checks out a new branch for feature/fix isolation."""
    repo = os.path.abspath(repo_path)
    init_git_repo(repo)
    subprocess.run(["git", "checkout", "-b", branch_name], cwd=repo, capture_output=True)

def commit_changes(repo_path: str, message: str) -> bool:
    """Stages all changes and creates a commit."""
    repo = os.path.abspath(repo_path)
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    res = subprocess.run(["git", "commit", "-m", message], cwd=repo, capture_output=True, text=True)
    return res.returncode == 0