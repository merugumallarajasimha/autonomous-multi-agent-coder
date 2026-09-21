# autocoder/tools/docker_sandbox.py
import os
import shutil
import subprocess


# Language to Docker image mapping
LANGUAGE_IMAGE_MAP = {
    "python": "python:3.11-slim",
    "c": "gcc:latest",
    "cpp": "gcc:latest",
    "java": "eclipse-temurin:21-jdk",
    "javascript": "node:20-slim",
    "typescript": "node:20-slim",
    "go": "golang:1.22",
    "rust": "rust:1.79",
}


# Module-level constant: allowed command prefixes for sandbox execution
ALLOWED_COMMANDS = (
    "python",
    "pytest",
    "pip install",
    "npm install",
    "npm test",
    "npm run",
    "go test",
    "go build",
    "cargo test",
    "cargo build",
    "mvn test",
    "mvn compile",
    "gradle test",
    "gradle build",
    "make test",
    "make",
    "gcc",
    "g++",
    "javac",
    "java",
    "ruff check",
    "ruff format",
    "black",
    "mypy",
    "go vet",
    "cargo check",
    "shellcheck",
)


def _is_command_allowed(command: str) -> bool:
    """Check if command starts with an allowed prefix."""
    cmd_stripped = command.strip().lower()
    for allowed in ALLOWED_COMMANDS:
        if cmd_stripped.startswith(allowed.lower()):
            return True
    return False


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


def run_in_sandbox(repo_path: str, command: str, timeout: int = 45, language: str = "python", allow_network: bool = False) -> dict:
    """
    Runs shell commands inside a restricted Docker container or host fallback.
    """
    abs_repo_path = os.path.abspath(repo_path)

    # Command allowlist validation
    if not _is_command_allowed(command):
        return {
            "returncode": 1,
            "stdout": "",
            "stderr": f"Error: Command '{command}' not in allowed command list. Allowed prefixes: {', '.join(ALLOWED_COMMANDS)}"
        }

    # Select Docker image based on language
    lang_key = language.strip().lower()
    if lang_key not in LANGUAGE_IMAGE_MAP:
        supported = ", ".join(sorted(LANGUAGE_IMAGE_MAP.keys()))
        raise ValueError(f"Unsupported language '{language}'. Supported languages: {supported}")
    docker_image = LANGUAGE_IMAGE_MAP[lang_key]

    # Language-specific install preamble (pytest for python, no-op for others)
    if lang_key == "python":
        sandboxed_command = f"python -m pip install --quiet pytest > /dev/null 2>&1 || true; {command}"
    else:
        sandboxed_command = command

    if not is_docker_available():
        print("⚠️ Docker daemon not accessible or not running. Falling back to host execution...")
        try:
            res = subprocess.run(
                command,
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
        "-v", f"{abs_repo_path}:/app:rw",
        "-w", "/app",
        "--memory", "512m",
        "--cpus", "1",
        "--cap-drop", "ALL",
        "--read-only",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=100m",
    ]

    # Network control: default to none, only allow when explicitly requested
    if not allow_network:
        docker_cmd.extend(["--network", "none"])

    docker_cmd.extend([
        docker_image,
        "bash", "-c", sandboxed_command
    ])

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