# autocoder/tools/docker_sandbox.py
import os
import shutil
import subprocess


def is_docker_available() -> bool:
    """Checks whether the Docker CLI is installed and the daemon is responsive."""
    if shutil.which("docker") is None:
        return False
    try:
        res = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return res.returncode == 0
    except Exception:
        return False


def run_in_sandbox(repo_path: str, command: str, timeout: int = 45) -> dict:
    """
    Runs shell commands inside a restricted Docker container or host fallback.
    """
    abs_repo_path = os.path.abspath(repo_path)
    sandboxed_command = f"python -m pip install --quiet pytest > /dev/null 2>&1 || true; {command}"

    if not is_docker_available():
        print("⚠️ Docker daemon not accessible or not running. Falling back to host execution...")
        try:
            res = subprocess.run(
                sandboxed_command,
                cwd=abs_repo_path,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return {
                "returncode": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr
            }
        except subprocess.TimeoutExpired:
            return {
                "returncode": 124,
                "stdout": "",
                "stderr": f"Error: Host execution timed out after {timeout} seconds."
            }

    docker_cmd = [
        "docker", "run", "--rm",
        "-v", f"{abs_repo_path}:/app",
        "-w", "/app",
        "--memory", "512m",
        "python:3.11-slim",
        "bash", "-c", sandboxed_command
    ]

    try:
        res = subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL
        )
        return {
            "returncode": res.returncode,
            "stdout": res.stdout,
            "stderr": res.stderr
        }
    except subprocess.TimeoutExpired:
        print("⚠️ Sandbox container timed out!")
        return {
            "returncode": 124,
            "stdout": "",
            "stderr": f"Error: Command timed out after {timeout} seconds inside sandbox container."
        }