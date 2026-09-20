# autocoder/agents/security_reviewer.py
import os
from typing import List, Dict, Any
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

from autocoder.state import AgentState
from autocoder.tools.file_ops import list_files, read_file
from autocoder.events.emitter import emit
from autocoder.analysis.static_checks import run_security_checks
from autocoder.analysis.finding import Finding, validate_finding


# Pydantic model matching the Finding TypedDict shape for structured output
class SecurityFinding(BaseModel):
    severity: str = Field(description="critical | high | medium | low")
    category: str = Field(description="security")
    file: str = Field(description="Relative file path")
    line: int = Field(description="Line number (1-indexed), 0 if file-level")
    description: str = Field(description="Human-readable security issue description")
    suggested_fix: str = Field(description="Concrete suggested fix")
    confidence: float = Field(description="0.0 to 1.0", ge=0.0, le=1.0)
    source: str = Field(description="static_analysis | llm_review")


class SecurityReviewOutput(BaseModel):
    findings: List[SecurityFinding] = Field(description="List of security findings")


def security_reviewer_node(state: AgentState) -> dict:
    emit(agent="security_reviewer", event="AGENT_STARTED", message="Security reviewer node started")
    repo = state["repo_path"]
    written_files = state.get("written_files", [])
    
    print("\n🔒 Security Reviewer Node: Conducting security-focused review...")
    
    if not written_files:
        print("⚠️ No written files to review. Skipping.")
        emit(agent="security_reviewer", event="AGENT_FINISHED", message="No files to review", metadata={"status": "skipped"})
        return {
            "security_findings": [],
            "history": state.get("history", []) + [{"agent": "security_reviewer", "status": "skipped"}],
        }
    
    # Filter to Python files only for security checks
    python_files = [f for f in written_files if f.endswith(".py")]
    
    # 1. Run deterministic security pattern checks
    static_findings = []
    if python_files:
        emit(agent="security_reviewer", event="SECURITY_STATIC_CHECKS_STARTED", message=f"Running security static checks on {len(python_files)} files")
        static_findings = run_security_checks(repo, python_files)
        emit(agent="security_reviewer", event="SECURITY_STATIC_CHECKS_COMPLETED", message=f"Security static checks found {len(static_findings)} issues", metadata={"count": len(static_findings)})
    
    # 2. Run LLM-based security review pass for issues deterministic patterns can't catch
    llm_findings = []
    
    for file_path in python_files:
        full_path = os.path.join(repo, file_path) if not os.path.isabs(file_path) else file_path
        code_content = read_file(full_path)
        
        if not code_content.strip():
            continue
        
        llm = ChatOllama(
            model="qwen2.5-coder:7b",
            temperature=0,
            timeout=60
        ).with_structured_output(SecurityReviewOutput)
        
        prompt = (
            f"You are a Senior Application Security Engineer.\n"
            f"Review the following Python code SPECIFICALLY FOR SECURITY ISSUES that "
            f"deterministic pattern matching cannot reliably detect:\n\n"
            f"- Authentication/authorization logic flaws (bypass, privilege escalation, missing checks)\n"
            f"- Injection risks: how user input flows into SQL queries, shell commands, "
            f"template rendering, LDAP queries, XPath, NoSQL queries\n"
            f"- Insecure defaults: permissive CORS, missing security headers, debug modes\n"
            f"- Missing input validation on security-relevant boundaries (API endpoints, "
            f"file uploads, deserialization, auth flows)\n"
            f"- Cryptographic misuse: weak algorithms, hardcoded keys, improper IV/nonce\n"
            f"- Information disclosure: stack traces in production, logging sensitive data\n"
            f"- Session/token management issues: fixation, missing expiry, weak generation\n\n"
            f"File: {file_path}\n"
            f"Content:\n{code_content}\n\n"
            f"Return a list of findings. Each finding MUST have category=\"security\".\n"
            f"Each finding must include:\n"
            f"- severity: critical | high | medium | low\n"
            f"- category: security (ONLY this value)\n"
            f"- file: {file_path}\n"
            f"- line: integer line number (1-indexed, 0 for file-level)\n"
            f"- description: what is the security issue\n"
            f"- suggested_fix: concrete remediation\n"
            f"- confidence: 0.0 to 1.0\n"
            f"- source: \"llm_review\"\n\n"
            f"Do NOT report style, refactor, or cosmetic issues — only security.\n"
            f"Be thorough but precise. Only report real, exploitable or likely-exploitable issues."
        )
        
        emit(agent="security_reviewer", event="LLM_SECURITY_REVIEW_STARTED", message=f"Starting LLM security review of {file_path}")
        
        try:
            review: SecurityReviewOutput = llm.invoke(prompt)
            # Convert Pydantic models to dicts and add source
            for finding in review.findings:
                finding_dict = finding.model_dump()
                finding_dict["source"] = "llm_review"
                # Ensure category is security (LLM might occasionally drift)
                finding_dict["category"] = "security"
                llm_findings.append(finding_dict)
            emit(agent="security_reviewer", event="LLM_SECURITY_REVIEW_COMPLETED", message=f"LLM security review of {file_path} produced {len(review.findings)} findings")
        except Exception as e:
            emit(agent="security_reviewer", event="LLM_SECURITY_REVIEW_ERROR", message=f"LLM security review failed for {file_path}: {e}")
            # Add a finding indicating the review failed
            llm_findings.append({
                "severity": "low",
                "category": "security",
                "file": file_path,
                "line": 0,
                "description": f"LLM security review failed: {e}",
                "suggested_fix": "Manual security review recommended",
                "confidence": 0.5,
                "source": "llm_review",
            })
    
    # 3. Combine and validate all findings
    all_findings = static_findings + llm_findings
    
    # Validate each LLM finding, drop invalid ones
    validated_findings = []
    dropped_count = 0
    for f in all_findings:
        if validate_finding(f):
            validated_findings.append(f)
        else:
            dropped_count += 1
    
    if dropped_count > 0:
        emit(agent="security_reviewer", event="VALIDATION_DROPPED", message=f"Dropped {dropped_count} invalid LLM findings", metadata={"dropped": dropped_count})
    
    # Emit one summary event with all findings
    emit(agent="security_reviewer", event="SECURITY_REVIEW_COMPLETED", message=f"Security review completed with {len(validated_findings)} validated findings", metadata={"findings": validated_findings})
    
    # Also emit one SECURITY_FINDING per finding for granular tracking
    for finding in validated_findings:
        emit(agent="security_reviewer", event="SECURITY_FINDING", message=f"Security finding in {finding['file']}:{finding['line']}", metadata=finding)
    
    emit(agent="security_reviewer", event="AGENT_FINISHED", message="Security reviewer node completed", metadata={"total_findings": len(validated_findings), "dropped_invalid": dropped_count})
    
    return {
        "security_findings": validated_findings,
        "history": state.get("history", []) + [{"agent": "security_reviewer", "findings_count": len(validated_findings)}],
    }