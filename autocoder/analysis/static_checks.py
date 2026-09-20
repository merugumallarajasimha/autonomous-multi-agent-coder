# autocoder/analysis/static_checks.py
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Any


def _run_tool(cmd: List[str], cwd: str) -> str:
    """Run a command and return stdout, or empty string on failure."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.stdout
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
        return ""


def _parse_ruff_output(output: str, repo_path: str) -> List[Dict[str, Any]]:
    """Parse ruff JSON output into normalized findings."""
    findings = []
    if not output.strip():
        return findings
    
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return [{
            "severity": "low",
            "category": "style",
            "file": "",
            "line": 0,
            "description": "failed to parse output",
            "source_tool": "ruff",
            "confidence": 1.0,
        }]
    
    for item in data:
        file_path = item.get("filename", "")
        if file_path:
            try:
                file_path = str(Path(file_path).relative_to(repo_path))
            except ValueError:
                pass
        
        code = item.get("code", "")
        category = "bug" if code.startswith("B") else "style"
        
        findings.append({
            "severity": "high" if category == "bug" else "low",
            "category": category,
            "file": file_path,
            "line": item.get("location", {}).get("row", 0),
            "description": item.get("message", ""),
            "source_tool": "ruff",
            "confidence": 1.0,
        })
    
    return findings


def _parse_bandit_output(output: str, repo_path: str) -> List[Dict[str, Any]]:
    """Parse bandit JSON output into normalized findings."""
    findings = []
    if not output.strip():
        return findings
    
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return [{
            "severity": "low",
            "category": "security",
            "file": "",
            "line": 0,
            "description": "failed to parse output",
            "source_tool": "bandit",
            "confidence": 1.0,
        }]
    
    results = data.get("results", [])
    for item in results:
        file_path = item.get("filename", "")
        if file_path:
            try:
                file_path = str(Path(file_path).relative_to(repo_path))
            except ValueError:
                pass
        
        bandit_severity = item.get("issue_severity", "LOW").lower()
        severity_map = {"high": "high", "medium": "medium", "low": "low"}
        
        findings.append({
            "severity": severity_map.get(bandit_severity, "low"),
            "category": "security",
            "file": file_path,
            "line": item.get("line_number", 0),
            "description": item.get("issue_text", ""),
            "source_tool": "bandit",
            "confidence": 1.0,
        })
    
    return findings


def run_python_static_checks(repo_path: str, file_paths: List[str]) -> List[Dict[str, Any]]:
    """Runs deterministic static analysis tools against the given files (not
    the whole repo) and returns a normalized list of findings:
    {
      "severity": "high" | "medium" | "low",
      "category": "bug" | "security" | "style",
      "file": str,
      "line": int,
      "description": str,
      "source_tool": str,
      "confidence": 1.0
    }
    (confidence is always 1.0 for deterministic tool output — these are not
    guesses)

    Use these tools if available on the system (check with shutil.which first,
    skip gracefully with no findings if a tool isn't installed — do not error):
    - `ruff check {files}` for style/bug-pattern findings (category="style" for
      most ruff rules, category="bug" for rules in ruff's bugbear/B-prefixed
      set specifically)
    - `bandit -f json {files}` for security findings (category="security"),
      mapping bandit's severity (LOW/MEDIUM/HIGH) to lowercase

    Parse each tool's actual output format (ruff has a --output-format=json
    option, bandit has -f json) — do not attempt to regex-parse human-readable
    tool output.

    If a tool's output can't be parsed, skip that tool's findings and include
    one finding with source_tool=<tool name>, description="failed to parse
    output", severity="low" so failures are visible rather than silent."""
    
    all_findings = []
    
    if not file_paths:
return all_findings


def run_security_checks(repo_path: str, file_paths: List[str]) -> List[Dict[str, Any]]:
    """Deterministic, pattern-based security checks (no LLM), returning
    findings in the same Finding-compatible shape as
    run_python_static_checks(), all with category="security" and
    confidence=1.0. Checks for:
    - Hardcoded secrets: regex patterns matching common key/token/password
      assignment patterns (e.g. `api_key = "..."`, `password = "..."` with a
      non-empty literal string, `AWS_SECRET` patterns) — flag as "high"
    - subprocess calls with shell=True — flag as "medium" (unsafe if
      combined with untrusted input, but flag regardless since it's a risk
      pattern)
    - Use of eval() or exec() — flag as "high"
    - pickle.loads() or yaml.load() without Loader=SafeLoader — flag as
      "high" (unsafe deserialization)
    - Path operations using unsanitized user input concatenated directly
      into a path (heuristic: string concatenation or f-string directly
      into open()/os.path.join() involving a variable — flag as "medium",
      acknowledge in the description this is a heuristic that may have false
      positives)

    These are regex/AST pattern checks only — do not attempt full taint
    analysis or claim high confidence beyond what simple pattern matching
    actually supports. Say so in code comments where a check is a rough
    heuristic vs. a solid detection."""
    import re
    import ast
    
    findings = []
    
    if not file_paths:
        return findings
    
    # Regex patterns for hardcoded secrets
    secret_patterns = [
        (r'(?i)(api_key|apikey|api_secret|access_token|secret_key|aws_secret|aws_access_key)\s*=\s*["\'][^"\']{8,}["\']', "Hardcoded API key/secret"),
        (r'(?i)(password|passwd|pwd)\s*=\s*["\'][^"\']{3,}["\']', "Hardcoded password"),
        (r'(?i)(private_key|private_token)\s*=\s*["\'][^"\']{16,}["\']', "Hardcoded private key/token"),
        (r'(?i)["\']?aws_secret_access_key["\']?\s*:\s*["\'][^"\']{20,}["\']', "AWS secret access key"),
    ]
    
    for file_rel in file_paths:
        full_path = os.path.join(repo_path, file_rel) if not os.path.isabs(file_rel) else file_rel
        
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                source = f.read()
        except (OSError, UnicodeDecodeError):
            continue
        
        lines = source.splitlines()
        
        # 1. Hardcoded secrets (regex on source lines)
        for line_num, line in enumerate(lines, 1):
            for pattern, desc in secret_patterns:
                if re.search(pattern, line):
                    findings.append({
                        "severity": "high",
                        "category": "security",
                        "file": file_rel,
                        "line": line_num,
                        "description": f"{desc} detected via pattern match",
                        "source_tool": "security_checks",
                        "confidence": 1.0,
                    })
        
        # 2-5. AST-based checks for more precise detection
        try:
            tree = ast.parse(source, filename=file_rel)
        except SyntaxError:
            continue
        
        for node in ast.walk(tree):
            # subprocess with shell=True
            if isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                
                if func_name in ("run", "Popen", "call", "check_call", "check_output"):
                    for kw in node.keywords:
                        if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                            findings.append({
                                "severity": "medium",
                                "category": "security",
                                "file": file_rel,
                                "line": node.lineno,
                                "description": "subprocess call with shell=True — unsafe if combined with untrusted input",
                                "source_tool": "security_checks",
                                "confidence": 1.0,
                            })
                
                # eval() or exec()
                if func_name in ("eval", "exec"):
                    findings.append({
                        "severity": "high",
                        "category": "security",
                        "file": file_rel,
                        "line": node.lineno,
                        "description": f"Use of {func_name}() — arbitrary code execution risk",
                        "source_tool": "security_checks",
                        "confidence": 1.0,
                    })
                
                # pickle.loads() or yaml.load() without SafeLoader
                if func_name == "loads" and isinstance(node.func, ast.Attribute):
                    if node.func.value.id == "pickle":
                        findings.append({
                            "severity": "high",
                            "category": "security",
                            "file": file_rel,
                            "line": node.lineno,
                            "description": "pickle.loads() — unsafe deserialization, can execute arbitrary code",
                            "source_tool": "security_checks",
                            "confidence": 1.0,
                        })
                
                if func_name == "load" and isinstance(node.func, ast.Attribute):
                    if node.func.value.id == "yaml":
                        # Check if Loader=SafeLoader is passed
                        has_safe_loader = False
                        for kw in node.keywords:
                            if kw.arg == "Loader":
                                if (isinstance(kw.value, ast.Attribute) and kw.value.attr == "SafeLoader") or \
                                   (isinstance(kw.value, ast.Name) and kw.value.id == "SafeLoader"):
                                    has_safe_loader = True
                        if not has_safe_loader:
                            findings.append({
                                "severity": "high",
                                "category": "security",
                                "file": file_rel,
                                "line": node.lineno,
                                "description": "yaml.load() without Loader=SafeLoader — unsafe deserialization",
                                "source_tool": "security_checks",
                                "confidence": 1.0,
                            })
                
                # Path operations with potential unsanitized input (heuristic)
                # Look for open() or os.path.join() with string concatenation/f-string involving variables
                if func_name in ("open", "join") or (isinstance(node.func, ast.Attribute) and node.func.attr in ("open", "join")):
                    for arg in node.args:
                        if _is_potential_path_injection(arg):
                            findings.append({
                                "severity": "medium",
                                "category": "security",
                                "file": file_rel,
                                "line": node.lineno,
                                "description": "Path operation with potential unsanitized input concatenation (heuristic — may have false positives)",
                                "source_tool": "security_checks",
                                "confidence": 1.0,
                            })
    
    return findings


def _is_potential_path_injection(node: ast.AST) -> bool:
    """Heuristic: detect string concatenation or f-string that could involve user input.
    This is a rough heuristic — may have false positives."""
    # f-string (JoinedStr)
    if isinstance(node, ast.JoinedStr):
        # Check if any formatted value is a variable (not a constant)
        for value in node.values:
            if isinstance(value, ast.FormattedValue):
                return True
    
    # String concatenation (BinOp with +)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _is_potential_path_injection(node.left) or _is_potential_path_injection(node.right)
    
    # Variable name (could be user input)
    if isinstance(node, ast.Name):
        return True
    
    # Function call result (could be user input)
    if isinstance(node, ast.Call):
        return True
    
    return False