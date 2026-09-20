# autocoder/agents/verifier.py
import os
from typing import TypedDict, List
from autocoder.state import AgentState
from autocoder.analysis.failure_classifier import classify_failure
from autocoder.events.emitter import emit
from autocoder.project.analyzer import analyze_project
from autocoder.languages.registry import get_adapter


class FailureReport(TypedDict):
    failure_type: str
    command: str
    exit_code: int
    stdout: str
    stderr: str
    failed_tests: List[str]
    traceback: str
    affected_files: List[str]
    probable_root_cause: str


def _extract_failed_tests(stdout: str) -> List[str]:
    """Extract failed test names from pytest verbose output."""
    failed = []
    for line in stdout.splitlines():
        if "FAILED" in line or "ERROR" in line:
            # Typical pytest -v output: "test_module.py::test_name FAILED"
            parts = line.split()
            for p in parts:
                if "::" in p and ("FAILED" in line or "ERROR" in line):
                    failed.append(p)
                    break
    return failed


def _extract_traceback(stderr: str, stdout: str) -> str:
    """Extract traceback from stderr/stdout."""
    # Tracebacks typically in stderr, but pytest -v puts some in stdout
    combined = stderr + "\n" + stdout
    lines = combined.splitlines()
    traceback_lines = []
    in_traceback = False
    for line in lines:
        if line.startswith("Traceback (most recent call last):"):
            in_traceback = True
        if in_traceback:
            traceback_lines.append(line)
    return "\n".join(traceback_lines) if traceback_lines else combined[-2000:]  # fallback


def verifier_node(state: AgentState) -> dict:
    """
    Runs unit tests scoped to only the files created or modified
    during THIS task, avoiding leftover tests from previous tasks.
    Returns structured FailureReport in bug_report field.
    """
    emit(agent="verifier", event="AGENT_STARTED", message="Verifier node started")
    repo = os.path.abspath(state["repo_path"])
    print("\n🧪 Verifier Node: Executing test suite...")

    # Analyze project to get language info
    try:
        profile = analyze_project(repo)
        primary_lang = profile.primary_language
        adapter = get_adapter(primary_lang)
    except (ValueError, Exception) as e:
        # Fallback to Python behavior if language unknown or adapter not found
        primary_lang = "python"
        adapter = get_adapter("python")
        print(f"⚠️ Language detection failed ({e}), falling back to Python adapter")

    # Get files written in this task iteration
    written_files = state.get("written_files", [])
    
    # Filter to test files only (pytest naming convention: test_*.py or *_test.py)
    test_files = [
        f for f in written_files
        if f.startswith("test_") and f.endswith(".py") or f.endswith("_test.py")
    ]
    
    if not test_files:
        # Fallback: if no test files written this iteration, check for any test files in repo
        # but prefer the most recent ones (by mtime) to avoid stale tests
        all_files = []
        for root, dirs, files in os.walk(repo):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("__pycache__", "venv")]
            for f in files:
                if (f.startswith("test_") and f.endswith(".py")) or f.endswith("_test.py"):
                    full = os.path.join(root, f)
                    all_files.append((full, os.path.getmtime(full)))
        all_files.sort(key=lambda x: x[1], reverse=True)
        test_files = [os.path.relpath(f[0], repo) for f in all_files[:5]]  # limit to 5 most recent

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
    
    # Use adapter's test method instead of hardcoded pytest command
    emit(agent="verifier", event="RUNNING_BUILD", message="Preparing test environment", metadata={"test_files": test_files, "language": primary_lang})
    emit(agent="verifier", event="RUNNING_TESTS", message=f"Running tests via {adapter.language_name} adapter")
    test_result = adapter.test(repo, test_paths=test_files if test_files else None)

    passed = test_result.get("success", False)
    stdout = test_result.get("output", "") if passed else ""
    stderr = test_result.get("output", "") if not passed else ""
    exit_code = test_result.get("exit_code", 1)

    test_logs = stdout if stdout else stderr

    if passed:
        print("✅ Unit test suite executed successfully.")
        emit(agent="verifier", event="TEST_PASSED", message="All tests passed", metadata={"test_files": test_files})
    else:
        print("❌ Test failures or execution errors detected.")
        emit(agent="verifier", event="TEST_FAILED", message="Tests failed", metadata={"exit_code": exit_code, "test_files": test_files})

    # Build structured failure report
    failure_report: FailureReport = {
        "failure_type": "unclassified",
        "command": f"{adapter.language_name} adapter test",
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "failed_tests": _extract_failed_tests(stdout),
        "traceback": _extract_traceback(stderr, stdout),
        "affected_files": test_files,
        "probable_root_cause": "unclassified",
    }

    # Add language fallback warning if applicable
    if primary_lang != "python" and primary_lang != "unknown":
        failure_report.setdefault("metadata", {})["language_fallback_warning"] = f"Fell back to Python adapter from {primary_lang}"

    # Classify failure deterministically (fills in failure_type and probable_root_cause)
    failure_report = classify_failure(failure_report)

    emit(agent="verifier", event="AGENT_FINISHED", message="Verifier node completed", metadata={"passed": passed, "test_files": test_files})
    return {
        "test_passed": passed,
        "test_logs": test_logs,  # kept for backward compatibility
        "bug_report": failure_report,  # structured report for fixer
        "history": state.get("history", []) + [{
            "agent": "verifier",
            "passed": passed,
            "logs": test_logs
        }],
    }