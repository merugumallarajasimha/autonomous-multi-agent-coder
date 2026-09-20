# autocoder/project/detector.py
import os
from pathlib import Path
from typing import Dict


# Directories to skip during file walking
SKIP_DIRS = {".git", "node_modules", "venv", "__pycache__", "target", "build"}

# Extension to language mapping
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

# Config files that unambiguously map to a language
CONFIG_TO_LANG = {
    "Cargo.toml": "rust",
    "go.mod": "go",
    "pom.xml": "java",
    "build.gradle": "java",
    "CMakeLists.txt": "cpp",
    "package.json": "javascript",
    "pyproject.toml": "python",
    "requirements.txt": "python",
}

# Config files to check for presence
CONFIG_FILES = [
    "pyproject.toml",
    "requirements.txt",
    "CMakeLists.txt",
    "pom.xml",
    "build.gradle",
    "package.json",
    "go.mod",
    "Cargo.toml",
]


def detect_languages(repo_path: str) -> Dict[str, int]:
    """Walks repo_path (skip .git, node_modules, venv, __pycache__, target,
    build directories) and returns a dict mapping language name to file count,
    based purely on file extensions:
    .py -> "python", .c -> "c", .h alone is ambiguous, skip it,
    .cpp/.cc/.cxx/.hpp -> "cpp", .java -> "java", .js/.jsx -> "javascript",
    .ts/.tsx -> "typescript", .go -> "go", .rs -> "rust"
    Only count source files, not config files."""
    counts: Dict[str, int] = {}
    repo = Path(repo_path).resolve()

    for root, dirs, files in os.walk(repo):
        # Skip unwanted directories in-place
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for f in files:
            ext = Path(f).suffix.lower()
            if ext in EXT_TO_LANG:
                lang = EXT_TO_LANG[ext]
                counts[lang] = counts.get(lang, 0) + 1

    return counts


def detect_config_files(repo_path: str) -> Dict[str, bool]:
    """Checks for the presence (top-level and one level deep only, do not
    recursively search the whole tree) of these exact files and returns a dict
    of filename -> bool:
    pyproject.toml, requirements.txt, CMakeLists.txt, pom.xml, build.gradle,
    package.json, go.mod, Cargo.toml"""
    repo = Path(repo_path).resolve()
    found: Dict[str, bool] = {fname: False for fname in CONFIG_FILES}

    # Check top-level
    for fname in CONFIG_FILES:
        if (repo / fname).is_file():
            found[fname] = True

    # Check one level deep (immediate subdirectories)
    try:
        for item in repo.iterdir():
            if item.is_dir() and item.name not in SKIP_DIRS:
                for fname in CONFIG_FILES:
                    if (item / fname).is_file():
                        found[fname] = True
    except (PermissionError, OSError):
        pass

    return found


def detect_primary_language(repo_path: str) -> str:
    """Combines detect_languages() and detect_config_files(): if a config file
    unambiguously points to one language (e.g. Cargo.toml -> rust, go.mod ->
    go), prefer that. Otherwise return the language with the highest file
    count from detect_languages(). Return "unknown" if nothing is detected."""
    config_presence = detect_config_files(repo_path)

    # First priority: config files that unambiguously map to a language
    for fname, present in config_presence.items():
        if present and fname in CONFIG_TO_LANG:
            return CONFIG_TO_LANG[fname]

    # Fallback: language with highest file count
    lang_counts = detect_languages(repo_path)
    if lang_counts:
        return max(lang_counts.items(), key=lambda x: x[1])[0]

    return "unknown"