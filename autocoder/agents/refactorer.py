# autocoder/agents/refactorer.py
import os
import re
from typing import Dict, Any, List
from langchain_ollama import ChatOllama
from autocoder.tools.file_ops import list_files, read_file, write_file
from autocoder.events.emitter import emit
from autocoder.analysis.finding import validate_finding


def _strip_markdown_fences(code: str) -> str:
    """Removes leading and trailing ```python / ``` markdown blocks from LLM responses."""
    code = code.strip()
    pattern = r"^```(?:python)?\s*\n(.*?)\n```$"
    match = re.search(pattern, code, re.DOTALL)
    if match:
        return match.group(1).strip()
    return code.strip("` \n")


def _apply_cosmetic_fix(repo_path: str, file_path: str, finding: Dict[str, Any]) -> str:
    """Apply a minimal cosmetic/refactor fix to a single file based on a finding.
    Reuses the type-hint/docstring logic from the original reviewer.py."""
    full_path = os.path.join(repo_path, file_path) if not os.path.isabs(file_path) else file_path
    code_content = read_file(full_path)
    
    llm = ChatOllama(
        model="qwen2.5-coder:7b",
        temperature=0,
        timeout=30
    )
    
    prompt = (
        f"You are a Senior Code Refactoring Specialist.\n"
        f"Apply a MINIMAL, targeted edit to address this specific finding:\n\n"
        f"File: {file_path}\n"
        f"Finding: {finding['description']}\n"
        f"Suggested Fix: {finding['suggested_fix']}\n"
        f"Category: {finding['category']}\n\n"
        f"Current Code:\n{code_content}\n\n"
        f"CRITICAL RULES:\n"
        f"1. ONLY address the specific finding above — do NOT make other changes.\n"
        f"2. Do NOT change any function's behavior, return values, control flow, or logic.\n"
        f"3. Only add/adjust type hints, docstrings, naming, or structural cleanup that "
        f"provably doesn't alter runtime behavior.\n"
        f"4. If the finding seems to require an actual behavior change to address, "
        f"return the original code unchanged with a comment explaining why.\n"
        f"5. Return ONLY the complete corrected file content — no markdown fences, "
        f"no explanation, no extra text.\n"
    )
    
    try:
        response = llm.invoke(prompt)
        raw_output = response.content.strip() if hasattr(response, "content") else str(response)
        clean_code = _strip_markdown_fences(raw_output)
        
        # If LLM returned unchanged code with explanation, detect and use original
        if "unchanged" in clean_code.lower() or "behavior change" in clean_code.lower():
            return code_content
            
        return clean_code
    except Exception as e:
        emit(agent="refactorer", event="REFRACTOR_LLM_ERROR", message=f"LLM error for {file_path}: {e}")
        return code_content


def refactorer_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Refactorer Node: Applies minimal targeted cosmetic/refactor edits
    based on findings from the Reviewer (category == "refactor" or "cosmetic").
    Does NOT run tests — returns edited files for the existing Verifier to re-test.
    """
    emit(agent="refactorer", event="AGENT_STARTED", message="Refactorer node started")
    repo_path = state["repo_path"]
    iteration = state.get("iteration_count", 0) + 1
    
    # Get findings from state (produced by reviewer_node)
    findings = state.get("review_findings", [])
    
    # Filter for refactor/cosmetic findings only
    refactor_findings = [
        f for f in findings
        if isinstance(f, dict) and f.get("category") in ("refactor", "cosmetic")
        and validate_finding(f)
    ]
    
    if not refactor_findings:
        emit(agent="refactorer", event="NO_REFACTOR_FINDINGS", message="No refactor/cosmetic findings to address")
        return {
            "iteration_count": iteration,
            "refactored_files": [],
            "history": state.get("history", []) + [{"agent": "refactorer", "status": "no_findings"}],
        }
    
    emit(agent="refactorer", event="PROCESSING_FINDINGS", message=f"Processing {len(refactor_findings)} refactor/cosmetic findings")
    
    refactored_files = []
    
    for finding in refactor_findings:
        file_path = finding.get("file", "")
        if not file_path:
            emit(agent="refactorer", event="SKIPPED_FINDING", message="Finding missing file path, skipping", metadata={"finding": finding})
            continue
        
        emit(agent="refactorer", event="APPLYING_REFACTOR", message=f"Applying refactor to {file_path}", metadata={"file": file_path, "finding": finding})
        
        # Apply the fix
        new_code = _apply_cosmetic_fix(repo_path, file_path, finding)
        
        # Write the fixed code
        full_path = os.path.join(repo_path, file_path) if not os.path.isabs(file_path) else file_path
        write_file(full_path, new_code)
        
        refactored_files.append(file_path)
        print(f"✅ Refactorer applied cosmetic fix to: {file_path}")
    
    emit(agent="refactorer", event="AGENT_FINISHED", message="Refactorer node completed", metadata={"refactored_files": refactored_files})
    return {
        "iteration_count": iteration,
        "refactored_files": refactored_files,
        "history": state.get("history", []) + [{"agent": "refactorer", "refactored_files": refactored_files}],
    }