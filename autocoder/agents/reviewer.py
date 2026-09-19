# autocoder/agents/reviewer.py
import os
import re
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

from autocoder.state import AgentState
from autocoder.tools.file_ops import list_files, read_file, write_file


class ReviewEdit(BaseModel):
    filepath: str = Field(description="Target file path relative to repo root")
    clean_code: str = Field(description="Refactored code with type hints and docstrings")


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
    repo = state["repo_path"]
    print("\n🔍 Reviewer Node: Conducting code review & refactoring...")

    existing_files = list_files(repo)
    
    # Target non-test Python files for review
    target_file = ""
    for f in existing_files:
        if not os.path.basename(f).startswith("test_") and f.endswith(".py"):
            target_file = f
            break
            
    if not target_file:
        print("⚠️ No suitable python files found to review. Skipping.")
        return {
            "is_refactored": True,
            "history": state.get("history", []) + [{"agent": "reviewer", "status": "skipped"}]
        }

    # Pass target file path to read_file
    full_target_path = os.path.join(repo, target_file) if not os.path.isabs(target_file) else target_file
    code_content = read_file(full_target_path)

    llm = ChatOllama(
        model="qwen2.5-coder:7b", 
        temperature=0,
        timeout=30
    ).with_structured_output(ReviewEdit)
    
    prompt = (
        f"You are a Senior Code Reviewer.\n"
        f"Refactor the following Python code to include type hints and clear Google-style docstrings.\n"
        f"Do NOT change any core functional logic or broken logic that tests rely on.\n\n"
        f"File: {target_file}\n"
        f"Content:\n{code_content}\n"
    )

    try:
        review: ReviewEdit = llm.invoke(prompt)
        
        # Strip markdown fences if Ollama placed them inside the Pydantic string field
        clean_code = _clean_code(review.clean_code)
        
        save_path = review.filepath if os.path.isabs(review.filepath) else os.path.join(repo, review.filepath)
        write_file(save_path, clean_code)
        reviewed_file = review.filepath
        print(f"✅ Code review completed and saved for: {reviewed_file}")

    except Exception as e:
        print(f"⚠️ Reviewer LLM parsing/timeout issue ({e}). Retaining original source code...")
        reviewed_file = target_file
        write_file(full_target_path, _clean_code(code_content))

    return {
        "is_refactored": True,
        "history": state.get("history", []) + [{"agent": "reviewer", "file": reviewed_file}],
    }