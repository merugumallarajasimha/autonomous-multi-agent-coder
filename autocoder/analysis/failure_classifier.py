# autocoder/analysis/failure_classifier.py
import re
from typing import Dict


def classify_failure(report: Dict) -> Dict:
    """Takes a FailureReport-shaped dict and returns the same dict with
    'failure_type' and 'probable_root_cause' filled in, using deterministic
    string/pattern matching only — no LLM call."""
    if not isinstance(report, dict):
        return report

    stdout = report.get("stdout", "") or ""
    stderr = report.get("stderr", "") or ""
    traceback = report.get("traceback", "") or ""
    exit_code = report.get("exit_code", 0)
    command = report.get("command", "") or ""
    combined = stdout + "\n" + stderr + "\n" + traceback

    # Timeout check first (exit code 124 is standard timeout)
    if exit_code == 124 or "timed out" in combined.lower() or "timeout" in combined.lower():
        report["failure_type"] = "timeout"
        report["probable_root_cause"] = "Command timed out"
        return report

    # SyntaxError in traceback
    if "SyntaxError" in traceback or "SyntaxError" in stderr or "SyntaxError" in stdout:
        # Extract the actual syntax error message
        msg = _extract_error_message(traceback, "SyntaxError") or _extract_error_message(stderr, "SyntaxError")
        report["failure_type"] = "syntax_error"
        report["probable_root_cause"] = f"Syntax error: {msg}" if msg else "Syntax error in code"
        return report

    # ModuleNotFoundError / ImportError (dependency errors)
    for err_type in ["ModuleNotFoundError", "ImportError"]:
        if err_type in traceback or err_type in stderr or err_type in stdout:
            pkg = _extract_missing_package(combined, err_type)
            report["failure_type"] = "dependency_error"
            report["probable_root_cause"] = f"Missing Python package: {pkg}" if pkg else f"{err_type}: missing dependency"
            return report

    # TypeError (could be runtime or type checker)
    if "TypeError" in traceback or "TypeError" in stderr:
        # Check if it's from mypy/type checker
        if "mypy" in command.lower() or "mypy" in combined.lower() or "type checking" in combined.lower():
            report["failure_type"] = "type_error"
            msg = _extract_error_message(combined, "TypeError")
            report["probable_root_cause"] = f"Type error: {msg}" if msg else "Type checking failed"
            return report
        # Otherwise runtime TypeError
        report["failure_type"] = "runtime_error"
        msg = _extract_error_message(traceback, "TypeError")
        report["probable_root_cause"] = f"Runtime TypeError: {msg}" if msg else "TypeError at runtime"
        return report

    # Lint tool patterns (ruff, flake8, pylint, eslint, etc.)
    lint_patterns = [
        r"(ruff|flake8|pylint|eslint|golint|clippy)\s",
        r"^(.*?):\d+:\d+:\s*(E|W|F)\d+",  # lint error codes like E302, W291
        r"Linting failed",
        r"Style violations",
    ]
    if any(re.search(p, combined, re.IGNORECASE | re.MULTILINE) for p in lint_patterns):
        report["failure_type"] = "lint_error"
        report["probable_root_cause"] = "Linter reported style/quality violations"
        return report

    # Compile errors (Go, Rust, C++, Java, etc.)
    compile_patterns = [
        r"(go build|cargo build|cargo check|javac|g\+\+|clang|rustc)\b.*error",
        r"compilation failed",
        r"cannot find module",
        r"undefined reference",
        r"syntax error before",
    ]
    if any(re.search(p, combined, re.IGNORECASE) for p in compile_patterns):
        report["failure_type"] = "compile_error"
        report["probable_root_cause"] = "Compilation failed"
        return report

    # Test failures (pytest, jest, etc.) - assertions failed but code ran
    if re.search(r"(FAILED|FAILURES|failed).*test", combined, re.IGNORECASE) or report.get("failed_tests"):
        # Check it's not a runtime exception masquerading as test failure
        if not _has_exception_traceback(traceback):
            report["failure_type"] = "test_failure"
            count = len(report.get("failed_tests", []))
            report["probable_root_cause"] = f"{count} test(s) failed" if count else "Test assertions failed"
            return report

    # Runtime errors - any exception in traceback that isn't caught above
    if _has_exception_traceback(traceback):
        exc_name = _extract_exception_name(traceback)
        msg = _extract_error_message(traceback, exc_name) if exc_name else ""
        report["failure_type"] = "runtime_error"
        report["probable_root_cause"] = f"Runtime {exc_name}: {msg}" if msg else f"Runtime {exc_name or 'exception'}"
        return report

    # Environment errors - missing binary, permission, path issues
    env_patterns = [
        r"(command not found|No such file or directory|Permission denied|not found in \$PATH)",
        r"(docker|python|node|npm|pip|go|cargo)\b.*not found",
        r"executable file not found",
    ]
    if any(re.search(p, combined, re.IGNORECASE) for p in env_patterns):
        report["failure_type"] = "environment_error"
        report["probable_root_cause"] = "Missing tool/binary or permission issue"
        return report

    # Fallback
    report["failure_type"] = "unclassified"
    report["probable_root_cause"] = "Unable to classify failure from logs"
    return report


def _has_exception_traceback(text: str) -> bool:
    """Check if text contains a Python traceback with an exception."""
    return "Traceback (most recent call last):" in text and any(
        exc in text for exc in [
            "Error:", "Exception:", "ValueError:", "KeyError:", "IndexError:",
            "AttributeError:", "NameError:", "ZeroDivisionError:", "FileNotFoundError:",
            "RuntimeError:", "AssertionError:", "TypeError:", "ImportError:",
            "ModuleNotFoundError:", "SyntaxError:"
        ]
    )


def _extract_exception_name(text: str) -> str:
    """Extract the exception class name from a traceback."""
    for line in text.splitlines():
        line = line.strip()
        if line.endswith(":") and any(line.startswith(e) for e in [
            "ValueError", "KeyError", "IndexError", "AttributeError", "NameError",
            "ZeroDivisionError", "FileNotFoundError", "RuntimeError", "AssertionError",
            "TypeError", "ImportError", "ModuleNotFoundError", "SyntaxError", "Exception", "Error"
        ]):
            return line.rstrip(":")
    return ""


def _extract_error_message(text: str, exc_name: str) -> str:
    """Extract the error message after the exception name."""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(exc_name + ":"):
            return line[len(exc_name) + 1:].strip()
    return ""


def _extract_missing_package(text: str, err_type: str) -> str:
    """Extract package name from ModuleNotFoundError or ImportError."""
    patterns = [
        rf"{err_type}: No module named ['\"]([^'\"]+)['\"]",
        rf"No module named ['\"]([^'\"]+)['\"]",
        rf"cannot import name ['\"]([^'\"]+)['\"]",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return ""