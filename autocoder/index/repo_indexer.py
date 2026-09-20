# autocoder/index/repo_indexer.py
import os
from pathlib import Path
from typing import List, Dict, Any

# Extension to language mapping (mirrored from autocoder/project/detector.py)
EXT_TO_LANG = {
    ".py": "python",
    ".c": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".java": "java",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
}

# Directories to skip during file walking
SKIP_DIRS = {".git", "node_modules", "venv", "__pycache__", "build", "dist", "target"}

# Common entry point file names
ENTRY_POINT_NAMES = {
    "main.py",
    "app.py",
    "index.js",
    "server.js",
    "main.go",
    "main.rs",
    "main.java",
    "main.cpp",
    "main.cc",
    "main.cxx",
    "main.c",
}

# Config files to check at top level
TOP_LEVEL_CONFIG_FILES = [
    "pyproject.toml",
    "requirements.txt",
    "package.json",
    "go.mod",
    "Cargo.toml",
    "CMakeLists.txt",
    "pom.xml",
    "build.gradle",
    "Dockerfile",
    ".env.example",
]


def index_files(repo_path: str) -> List[Dict[str, Any]]:
    """Walks repo_path (skip .git, node_modules, venv, __pycache__, build,
    dist, target directories) and returns a list of dicts, one per source
    file:
    {
      "path": <relative path>,
      "language": <inferred from extension, reuse the same extension mapping
                   logic as detect_languages() in autocoder/project/detector.py>,
      "size_bytes": int,
      "line_count": int
    }
    Do not read full file contents beyond what's needed to count lines.
    Skip binary files (detect via a simple heuristic: if reading as UTF-8
    raises UnicodeDecodeError, skip and don't include it)."""
    repo = Path(repo_path).resolve()
    indexed: List[Dict[str, Any]] = []

    for root, dirs, files in os.walk(repo):
        # Skip unwanted directories in-place
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for f in files:
            file_path = Path(root) / f
            ext = file_path.suffix.lower()

            # Only index files with known extensions
            if ext not in EXT_TO_LANG:
                continue

            # Get relative path
            try:
                rel_path = file_path.relative_to(repo)
            except ValueError:
                continue

            # Get file size
            try:
                size_bytes = file_path.stat().st_size
            except (OSError, PermissionError):
                continue

            # Count lines - read as UTF-8, skip binary files
            line_count = 0
            try:
                with open(file_path, "r", encoding="utf-8") as fp:
                    for _ in fp:
                        line_count += 1
            except UnicodeDecodeError:
                # Binary file - skip
                continue
            except (OSError, PermissionError):
                continue

            indexed.append({
                "path": str(rel_path).replace("\\", "/"),
                "language": EXT_TO_LANG[ext],
                "size_bytes": size_bytes,
                "line_count": line_count,
            })

    return indexed


def find_entry_points(repo_path: str, indexed_files: List[Dict[str, Any]]) -> List[str]:
    """Returns a list of relative paths that look like entry points, using
    simple deterministic patterns: files named main.py, app.py, index.js,
    server.js, main.go, main.rs, or files containing 'if __name__ ==
    "__main__"' for Python. Do not use an LLM. If none found, return an
    empty list — don't guess."""
    repo = Path(repo_path).resolve()
    entry_points: List[str] = []

    for file_info in indexed_files:
        rel_path = file_info["path"]
        file_name = Path(rel_path).name

        # Check by name
        if file_name in ENTRY_POINT_NAMES:
            entry_points.append(rel_path)
            continue

        # Check for Python __main__ pattern
        if file_info["language"] == "python":
            file_path = repo / rel_path
            try:
                with open(file_path, "r", encoding="utf-8") as fp:
                    content = fp.read()
                    if 'if __name__ == "__main__"' in content:
                        entry_points.append(rel_path)
            except (UnicodeDecodeError, OSError, PermissionError):
                pass

    return entry_points


def find_config_files(repo_path: str) -> List[str]:
    """Returns paths of any of these that exist at the top level:
    pyproject.toml, requirements.txt, package.json, go.mod, Cargo.toml,
    CMakeLists.txt, pom.xml, build.gradle, Dockerfile, .env.example"""
    repo = Path(repo_path).resolve()
    found: List[str] = []

    for fname in TOP_LEVEL_CONFIG_FILES:
        file_path = repo / fname
        if file_path.is_file():
            found.append(fname)

    return found