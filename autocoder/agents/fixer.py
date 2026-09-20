# autocoder/agents/fixer.py
import os
import re
from typing import Dict, Any, List
from langchain_ollama import ChatOllama
from autocoder.tools.file_ops import list_files, read_file, write_file
from autocoder.events.emitter import emit


def _strip_markdown_fences(code: str) -> str:
    """Removes leading and trailing ```python / ``` markdown blocks from LLM responses."""
    code = code.strip()
    pattern = r"^```(?:python)?\s*\n(.*?)\n```$"
    match = re.search(pattern, code, re.DOTALL)
    if match:
        return match.group(1).strip()
    return code.strip("` \n")


def fixer_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Surgical Fixer Node: Applies minimal targeted patches
    based on static check failures, unit test logs, or code review findings.
    Consumes structured FailureReport from verifier.
    """
    emit(agent="fixer", event="AGENT_STARTED", message="Fixer node started")
    repo_path = state["repo_path"]
    bug_report = state.get("bug_report", {})
    iteration = state.get("iteration_count", 0) + 1

    print(f"🔧 Fixer Agent active (Iteration {iteration})...")

    existing_files = list_files(repo_path)
    if not existing_files:
        print("⚠️ Fixer found no files in target repository.")
        emit(agent="fixer", event="AGENT_FINISHED", message="No files to fix", metadata={"status": "no_files"})
        return {
            "iteration_count": iteration,
            "history": state.get("history", []) + [{"agent": "fixer", "status": "no_files"}]
        }

    # Aggregate code context from existing repository files
    context_blocks = []
    for file_rel in existing_files:
        full_p = os.path.join(repo_path, file_rel)
        content = read_file(full_p)
        context_blocks.append(f"--- File: {file_rel} ---\n{content}\n")

    repo_context = "\n".join(context_blocks)

    llm = ChatOllama(
        model="qwen2.5-coder:7b",
        temperature=0,
        timeout=60
    )

    # Build structured error context from FailureReport
    if isinstance(bug_report, dict) and "failed_tests" in bug_report:
        # New structured format
        failed_tests = bug_report.get("failed_tests", [])
        traceback = bug_report.get("traceback", "")
        affected_files = bug_report.get("affected_files", [])
        exit_code = bug_report.get("exit_code", -1)
        command = bug_report.get("command", "")

        error_context = (
            f"=== STRUCTURED FAILURE REPORT ===\n"
            f"Failure Type: {bug_report.get('failure_type', 'unclassified')}\n"
            f"Exit Code: {exit_code}\n"
            f"Command: {command}\n"
            f"Failed Tests: {', '.join(failed_tests) if failed_tests else 'none detected'}\n"
            f"Affected Test Files: {', '.join(affected_files) if affected_files else 'none'}\n"
            f"Probable Root Cause: {bug_report.get('probable_root_cause', 'unclassified')}\n\n"
            f"=== TRACEBACK ===\n{traceback}\n\n"
            f"=== FULL STDOUT ===\n{bug_report.get('stdout', '')}\n\n"
            f"=== FULL STDERR ===\n{bug_report.get('stderr', '')}\n"
        )
    else:
        # Backward compatibility: old string format
        error_context = f"=== ERROR LOGS ===\n{bug_report}\n"

    emit(agent="fixer", event="ANALYZING_FAILURE", message="Analyzing failure report", metadata={"failure_type": bug_report.get('failure_type') if isinstance(bug_report, dict) else 'legacy'})

    prompt = (
        f"You are an expert Python Debugger and Fixer Agent.\n"
        f"The test suite or static verification failed with the following structured error output:\n\n"
        f"{error_context}\n"
        f"=== CURRENT REPOSITORY FILES ===\n{repo_context}\n\n"
        f"CRITICAL INSTRUCTIONS:\n"
        f"1. Identify which file caused the error.\n"
        f"2. Provide the entire corrected Python code for ONLY the broken file.\n"
        f"3. Do NOT wrap code inside ```python or ``` markdown fences.\n"
        f"4. Do NOT add explanation text before or after the code.\n"
        f"5. Start your response with a comment specifying the target relative file path on line 1, e.g.:\n"
        f"# FILE: test_banking_utils.py\n\n"
        f"Generate corrected code now:"
    )

    try:
        response = llm.invoke(prompt)
        raw_output = response.content.strip() if hasattr(response, "content") else str(response)

        # Strip markdown fences if present
        clean_code = _strip_markdown_fences(raw_output)

        # Parse target file header if present (# FILE: path/to/file.py)
        target_file = None
        lines = clean_code.splitlines()
        if lines and lines[0].startswith("# FILE:"):
            target_file = lines[0].replace("# FILE:", "").strip()
            clean_code = "\n".join(lines[1:]).strip()

        # Fallback: target file from bug report or existing files
        if not target_file:
            # Try to use affected_files from structured report
            if isinstance(bug_report, dict) and bug_report.get("affected_files"):
                for f in bug_report["affected_files"]:
                    if f in existing_files:
                        target_file = f
                        break
            if not target_file:
                for file_rel in existing_files:
                    if isinstance(bug_report, str) and file_rel in bug_report:
                        target_file = file_rel
                        break
            if not target_file and existing_files:
                target_file = existing_files[0]

        emit(agent="fixer", event="APPLYING_FIX", message=f"Patching {target_file}", metadata={"target_file": target_file})
        target_path = os.path.join(repo_path, target_file)
        write_file(target_path, clean_code)
        print(f"✅ Fixer applied surgical patch to: {target_file}")

    except Exception as e:
        print(f"⚠️ Fixer LLM failed to patch code: {e}")

    emit(agent="fixer", event="AGENT_FINISHED", message="Fixer node completed", metadata={"status": "patched"})
    return {
        "iteration_count": iteration,
        "history": state.get("history", []) + [{"agent": "fixer", "status": "patched"}],
    }