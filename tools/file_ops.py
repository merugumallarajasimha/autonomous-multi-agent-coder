import os
import re

IGNORED_DIRS = {".git", "__pycache__", ".pytest_cache", ".venv", "venv"}
IGNORED_EXTS = {".pyc", ".pyo", ".pyd", ".png", ".jpg", ".jpeg", ".zip", ".exe"}

def list_files(repo_path: str) -> list[str]:
    """Returns relative paths of non-binary, non-system files in the target repo."""
    file_list = []
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if not file.startswith(".") and ext not in IGNORED_EXTS:
                rel_path = os.path.relpath(os.path.join(root, file), repo_path)
                file_list.append(rel_path)
    return file_list

def read_file(repo_path: str, filepath: str) -> str:
    """Reads content of a file safely with fallback decoding."""
    full_path = os.path.join(repo_path, filepath)
    if os.path.exists(full_path):
        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception:
            return ""
    return ""

def clean_code_block(content: str) -> str:
    """Strips Markdown code block formatting from LLM string output."""
    pattern = r"^```(?:\w+)?\n?(.*?)\n?```$"
    match = re.search(pattern, content.strip(), re.DOTALL)
    if match:
        return match.group(1).strip()
    return content.strip("` \n")

def write_file(repo_path: str, filepath: str, content: str) -> None:
    """Sanitizes content and writes to file, creating subdirectories if needed."""
    full_path = os.path.join(repo_path, filepath)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    
    clean_content = clean_code_block(content)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(clean_content)