# autocoder/agents/verifier.py
import os
from autocoder.state import AgentState
from autocoder.tools.docker_sandbox import run_in_sandbox

def verifier_node(state: AgentState) -> dict:
    """
    Runs unit tests (pytest) with recursive PYTHONPATH resolution 
    via the Docker sandbox runner (or host fallback).
    """
    repo = os.path.abspath(state["repo_path"])
    print("\n🧪 Verifier Node: Executing test suite...")

    # Build relative paths, skipping hidden folders (.git, .pytest_cache, etc.)
    python_paths = ["/app" if os.name != "nt" else repo]
    for root, dirs, _ in os.walk(repo):
        # Filter out hidden or internal folders in-place
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("__pycache__", "venv")]
        for d in dirs:
            rel_path = os.path.relpath(os.path.join(root, d), repo)
            python_paths.append(f"/app/{rel_path.replace('\\', '/')}")

    # Quote "$PYTHONPATH:..." so bash handles spaces in path names cleanly
    pythonpath_env = ":".join(python_paths)
    command = f'export PYTHONPATH="$PYTHONPATH:{pythonpath_env}" && pytest'

    result = run_in_sandbox(repo_path=repo, command=command, timeout=30)

    passed = (result["returncode"] == 0)
    stdout = result["stdout"]
    stderr = result["stderr"]

    test_logs = stdout if stdout else stderr

    if passed:
        print("✅ Unit test suite executed successfully.")
    else:
        print("❌ Test failures or execution errors detected.")

    return {
        "test_passed": passed,
        "test_logs": test_logs,
        "history": state.get("history", []) + [{
            "agent": "verifier",
            "passed": passed,
            "logs": test_logs
        }],
    }