# autocoder/tools/file_ops.py
import os
import re

def clean_code_markdown(content: str) -> str:
    """
    Strips markdown code blocks (e.g., ```python ... ```) if present,
    handling extra text, leading whitespace, and different line endings.
    """
    if not content:
        return ""

    # Search for code block anywhere in content
    pattern = r"```(?:[a-zA-Z0-9_]+)?\r?\n(.*?)\r?\n```"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # Fallback: remove lone backticks at start/end without destroying internal code
    return content.strip()


def read_file(arg1: str, arg2: str = None) -> str:
    """
    Reads file content safely across single and dual argument signatures.
    """
    filepath = os.path.join(arg1, arg2) if arg2 is not None else arg1

    if not os.path.exists(filepath):
        return ""

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        print(f"⚠️ Error reading file {filepath}: {e}")
        return ""


def write_file(arg1: str, arg2: str, arg3: str = None) -> None:
    """
    Writes content to a file, auto-creating parent directories if missing.
    Supports both write_file(filepath, content) and write_file(repo, rel_path, content).
    """
    if arg3 is not None:
        filepath = os.path.join(arg1, arg2)
        content = arg3
    else:
        filepath = arg1
        content = arg2

    abs_path = os.path.abspath(filepath)
    parent_dir = os.path.dirname(abs_path)
    
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    # Clean markdown fences before writing
    sanitized_content = clean_code_markdown(content)

    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(sanitized_content)


def list_files(repo_path: str) -> list[str]:
    """Lists relative Python file paths, ignoring binary files and cache directories."""
    file_list = []
    for root, _, files in os.walk(repo_path):
        for file in files:
            if not file.startswith(".") and "__pycache__" not in root and file.endswith(".py"):
                rel_path = os.path.relpath(os.path.join(root, file), repo_path)
                file_list.append(rel_path)
    return file_list