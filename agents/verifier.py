import subprocess
import os

def verifier_node(state: dict) -> dict:
    repo = os.path.abspath(state["repo_path"])
    
    # Recursively add target_repo AND its subfolders to PYTHONPATH
    env = os.environ.copy()
    python_paths = [repo]
    for root, dirs, _ in os.walk(repo):
        for d in dirs:
            if not d.startswith(".") and d not in ("__pycache__", "venv"):
                python_paths.append(os.path.join(root, d))
                
    env["PYTHONPATH"] = os.pathsep.join(python_paths) + os.pathsep + env.get("PYTHONPATH", "")
    
    try:
        res = subprocess.run(
            ["pytest", repo],
            capture_output=True,
            text=True,
            timeout=30,
            env=env
        )
        passed = (res.returncode == 0)
        stdout = res.stdout
        stderr = res.stderr
    except Exception as e:
        passed = False
        stdout = ""
        stderr = str(e)

    test_logs = stdout if stdout else stderr
    
    return {
        "test_passed": passed,
        "test_logs": test_logs,
        "history": state.get("history", []) + [{
            "agent": "verifier",
            "passed": passed,
            "logs": test_logs
        }],
    }