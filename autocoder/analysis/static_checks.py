import json
import os
import shutil
import subprocess
import ast
from pathlib import Path
from typing import List, Dict, Any


def _is_potential_path_injection(node: ast.AST) -> bool:
    """Heuristic: detect string concatenation or f-string that could involve user input.
    Returns False for safe literals (ast.Constant strings), True for variables/calls/f-strings."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        # String literal is safe
        return False
    
    if isinstance(node, ast.JoinedStr):
        for value in node.values:
            if isinstance(value, ast.FormattedValue):
                return True
    
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _is_potential_path_injection(node.left) or _is_potential_path_injection(node.right)
    
    if isinstance(node, ast.Name):
        # Variable reference - could be user input
        return True
    
    if isinstance(node, ast.Call):
        # Function call - could return user input
        return True
    
    if isinstance(node, ast.Attribute):
        # Attribute access - could be user input
        return True
    
    if isinstance(node, ast.Subscript):
        # Subscript - could be user input
        return True
    
    return False


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
    """Runs deterministic static analysis tools against the given files and returns
    a normalized list of findings."""
    all_findings = []
    
    if not file_paths:
        return all_findings

    # 1. Run Ruff if installed
    if shutil.which("ruff"):
        cmd = ["ruff", "check", "--output-format=json"] + file_paths
        raw_output = _run_tool(cmd, cwd=repo_path)
        all_findings.extend(_parse_ruff_output(raw_output, repo_path))

    # 2. Run Bandit if installed
    if shutil.which("bandit"):
        cmd = ["bandit", "-f", "json"] + file_paths
        raw_output = _run_tool(cmd, cwd=repo_path)
        all_findings.extend(_parse_bandit_output(raw_output, repo_path))

    return all_findings


def run_security_checks(repo_path: str, file_paths: List[str]) -> List[Dict[str, Any]]:
    """Deterministic, pattern-based security checks (no LLM)."""
    import re
    
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
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == "pickle":
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
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == "yaml":
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
                
                # Path operations with potential unsanitized input
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