import os
import sys
from autocoder.state import AgentState
from autocoder.tools.docker_sandbox import run_in_sandbox


def verifier_node(state: AgentState) -> dict:
    """
    Runs unit tests using python -m pytest with recursive PYTHONPATH resolution 
    via the Docker sandbox runner (or host fallback).
    Tracks iterations to prevent infinite graph execution.
    """
    repo = os.path.abspath(state["repo_path"])
    iteration = state.get("iteration_count", 0) + 1
    print(f"\n🧪 Verifier Node: Executing test suite (Iteration {iteration})...")

    # Build relative paths for Docker container mounting
    python_paths = ["/app" if os.name != "nt" else repo]
    for root, dirs, _ in os.walk(repo):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("__pycache__", "venv")]
        for d in dirs:
            rel_path = os.path.relpath(os.path.join(root, d), repo)
            python_paths.append(f"/app/{rel_path.replace('\\', '/')}")

    pythonpath_env = ":".join(python_paths)
    
    # Force pytest execution using python module launcher
    command = f'export PYTHONPATH="$PYTHONPATH:{pythonpath_env}" && python -m pytest'

    try:
        result = run_in_sandbox(repo_path=repo, command=command, timeout=30)
        passed = (result.get("returncode", 1) == 0)
        stdout = result.get("stdout", "")
        stderr = result.get("stderr", "")
        test_logs = stdout if stdout else stderr
    except Exception as e:
        print(f"⚠️ Sandbox execution failed ({e}). Attempting host fallback...")
        import subprocess

        env = os.environ.copy()
        env["PYTHONPATH"] = repo + os.pathsep + env.get("PYTHONPATH", "")

        host_res = subprocess.run(
            [sys.executable, "-m", "pytest", repo, "-v"],
            capture_output=True,
            text=True,
            env=env,
        )
        passed = (host_res.returncode == 0)
        test_logs = host_res.stdout + "\n" + host_res.stderr

    if passed:
        print("✅ Unit test suite executed successfully.")
    else:
        print(f"❌ Test failures or execution errors detected (Iteration {iteration}).")

    return {
        "verification_passed": passed,
        "test_passed": passed,
        "test_logs": test_logs,
        "iteration_count": iteration,  # Prevents infinite loop in graph execution
        "history": state.get("history", []) + [{
            "agent": "verifier",
            "passed": passed,
            "logs": test_logs,
            "iteration": iteration,
        }],
    }