# autocoder/agents/fixer.py
import os
import re
from typing import Dict, Any
from langchain_ollama import ChatOllama
from autocoder.tools.file_ops import list_files, read_file, write_file


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
    """
    repo_path = state["repo_path"]
    bug_report = state.get("bug_report", "")
    iteration = state.get("iteration_count", 0) + 1
    
    print(f"🔧 Fixer Agent active (Iteration {iteration})...")

    existing_files = list_files(repo_path)
    if not existing_files:
        print("⚠️ Fixer found no files in target repository.")
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

    prompt = (
        f"You are an expert Python Debugger and Fixer Agent.\n"
        f"The test suite or static verification failed with the following error output:\n\n"
        f"=== ERROR LOGS ===\n{bug_report}\n\n"
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
            for file_rel in existing_files:
                if file_rel in bug_report:
                    target_file = file_rel
                    break
            if not target_file and existing_files:
                target_file = existing_files[0]

        target_path = os.path.join(repo_path, target_file)
        write_file(target_path, clean_code)
        print(f"✅ Fixer applied surgical patch to: {target_file}")

    except Exception as e:
        print(f"⚠️ Fixer LLM failed to patch code: {e}")

    return {
        "iteration_count": iteration,
        "history": state.get("history", []) + [{"agent": "fixer", "status": "patched"}],
    }