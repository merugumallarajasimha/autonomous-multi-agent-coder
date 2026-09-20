# autocoder/agents/reviewer.py
import os
import re
from typing import List, Dict, Any
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

from autocoder.state import AgentState
from autocoder.tools.file_ops import list_files, read_file
from autocoder.events.emitter import emit
from autocoder.analysis.static_checks import run_python_static_checks
from autocoder.analysis.finding import Finding, validate_finding


# Pydantic model matching the Finding TypedDict shape for structured output
class ReviewFinding(BaseModel):
    severity: str = Field(description="critical | high | medium | low")
    category: str = Field(description="bug | security | refactor | cosmetic")
    file: str = Field(description="Relative file path")
    line: int = Field(description="Line number (1-indexed), 0 if file-level")
    description: str = Field(description="Human-readable issue description")
    suggested_fix: str = Field(description="Concrete suggested fix")
    confidence: float = Field(description="0.0 to 1.0", ge=0.0, le=1.0)
    source: str = Field(description="static_analysis | llm_review")


class ReviewOutput(BaseModel):
    findings: List[ReviewFinding] = Field(description="List of review findings")


def _clean_code(code: str) -> str:
    """Strips markdown code fences (```python ... ```) if LLM embeds them."""
    if not code:
        return ""
    pattern = r"```(?:[a-zA-Z0-9_]+)?\r?\n(.*?)\r?\n```"
    match = re.search(pattern, code, re.DOTALL)
    if match:
        return match.group(1).strip()
    return code.strip("` \n")


def reviewer_node(state: AgentState) -> dict:
    emit(agent="reviewer", event="AGENT_STARTED", message="Reviewer node started")
    repo = state["repo_path"]
    written_files = state.get("written_files", [])
    
    print("\n[Reviewer] Conducting code review (static + LLM)...")
    
    if not written_files:
        # Fallback: scan repo for Python files if no written_files tracked
        all_files = list_files(repo)
        # Filter out test files (test_*.py or *_test.py)
        written_files = [
            f for f in all_files
            if f.endswith(".py") and not (f.startswith("test_") or f.endswith("_test.py"))
        ]
        if written_files:
            print(f"[Reviewer] No written_files in state, scanning repo found {len(written_files)} Python files")
        else:
            print("[Reviewer] No written files to review. Skipping.")
            emit(agent="reviewer", event="AGENT_FINISHED", message="No files to review", metadata={"status": "skipped"})
            return {
                "review_findings": [],
                "is_refactored": True,
                "history": state.get("history", []) + [{"agent": "reviewer", "status": "skipped"}],
            }
    
    # Filter to Python files only for static checks
    python_files = [f for f in written_files if f.endswith(".py")]
    
    # 1. Run deterministic static analysis tools
    static_findings = []
    if python_files:
        emit(agent="reviewer", event="STATIC_CHECKS_STARTED", message=f"Running static checks on {len(python_files)} files")
        static_findings = run_python_static_checks(repo, python_files)
        emit(agent="reviewer", event="STATIC_CHECKS_COMPLETED", message=f"Static checks found {len(static_findings)} issues", metadata={"count": len(static_findings)})
    
    # 2. Run LLM-based review pass for issues static tools can't catch
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
        ).with_structured_output(ReviewOutput)
        
        prompt = (
            f"You are a Senior Code Reviewer.\n"
            f"Review the following Python code for issues that static analysis tools "
            f"typically miss: logic bugs, unclear error handling, missing edge cases, "
            f"naming problems, unnecessary complexity, and security concerns.\n\n"
            f"File: {file_path}\n"
            f"Content:\n{code_content}\n\n"
            f"Return a list of findings. Each finding must include:\n"
            f"- severity: critical | high | medium | low\n"
            f"- category: bug | security | refactor | cosmetic\n"
            f"- file: {file_path}\n"
            f"- line: integer line number (1-indexed, 0 for file-level)\n"
            f"- description: what is wrong\n"
            f"- suggested_fix: concrete fix suggestion\n"
            f"- confidence: 0.0 to 1.0\n"
            f"- source: \"llm_review\"\n\n"
            f"Be thorough but precise. Only report real issues."
        )
        
        emit(agent="reviewer", event="LLM_REVIEW_STARTED", message=f"Starting LLM review of {file_path}")
        
        try:
            review: ReviewOutput = llm.invoke(prompt)
            # Convert Pydantic models to dicts and add source
            for finding in review.findings:
                finding_dict = finding.model_dump()
                finding_dict["source"] = "llm_review"
                llm_findings.append(finding_dict)
            emit(agent="reviewer", event="LLM_REVIEW_COMPLETED", message=f"LLM review of {file_path} produced {len(review.findings)} findings")
        except Exception as e:
            emit(agent="reviewer", event="LLM_REVIEW_ERROR", message=f"LLM review failed for {file_path}: {e}")
            # Add a finding indicating the review failed
            llm_findings.append({
                "severity": "low",
                "category": "bug",
                "file": file_path,
                "line": 0,
                "description": f"LLM review failed: {e}",
                "suggested_fix": "Manual review recommended",
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
        emit(agent="reviewer", event="VALIDATION_DROPPED", message=f"Dropped {dropped_count} invalid LLM findings", metadata={"dropped": dropped_count})
    
    # Emit one summary event with all findings
    emit(agent="reviewer", event="REVIEW_COMPLETED", message=f"Review completed with {len(validated_findings)} validated findings", metadata={"findings": validated_findings})
    
    # Also emit one REVIEW_FINDING per finding for granular tracking
    for finding in validated_findings:
        emit(agent="reviewer", event="REVIEW_FINDING", message=f"Finding in {finding['file']}:{finding['line']}", metadata=finding)
    
    emit(agent="reviewer", event="AGENT_FINISHED", message="Reviewer node completed", metadata={"total_findings": len(validated_findings), "dropped_invalid": dropped_count})
    
    return {
        "review_findings": validated_findings,
        "is_refactored": True,
        "history": state.get("history", []) + [{"agent": "reviewer", "findings_count": len(validated_findings)}],
    }