# autocoder/index/dependency_graph.py
import os
from pathlib import Path
from typing import List, Dict, Any, Set

from autocoder.index.symbol_index import extract_symbols_for_file


def _build_module_to_file_map(indexed_files: List[Dict[str, Any]], repo_path: str) -> Dict[str, str]:
    """Build a mapping from Python module paths to file paths.
    
    For a file like src/auth/utils.py, the module path would be "src.auth.utils"
    and also "src.auth" (for package imports)."""
    repo = Path(repo_path).resolve()
    module_to_file: Dict[str, str] = {}
    
    for file_info in indexed_files:
        if file_info.get("language") != "python":
            continue
        
        file_path = file_info["path"]
        # Convert file path to module path: src/auth/utils.py -> src.auth.utils
        # Remove .py extension and replace / with .
        module_path = file_path[:-3].replace("/", ".")
        
        # Map the full module path
        module_to_file[module_path] = file_path
        
        # Also map parent packages (src.auth -> src/auth/__init__.py if it exists)
        parts = module_path.split(".")
        for i in range(1, len(parts)):
            parent_module = ".".join(parts[:i])
            parent_file = "/".join(parts[:i]) + "/__init__.py"
            if parent_module not in module_to_file:
                # Check if __init__.py exists
                init_path = repo / parent_file
                if init_path.is_file():
                    module_to_file[parent_module] = parent_file
    
    return module_to_file


def _resolve_import(import_name: str, current_file: str, module_to_file: Dict[str, str], repo_path: str) -> str | None:
    """Resolve an import name to a file path within the repo.
    
    Handles:
    - Absolute imports: from src.auth import X -> src.auth
    - Relative imports: from . import utils -> same directory
    - Relative imports: from ..models import User -> parent directory
    
    Returns the resolved file path or None if not found/internal."""
    repo = Path(repo_path).resolve()
    current_dir = Path(current_file).parent
    
    # Handle relative imports (starting with .)
    if import_name.startswith("."):
        # Count leading dots
        level = 0
        for ch in import_name:
            if ch == ".":
                level += 1
            else:
                break
        
        # Get the module part after the dots
        module_part = import_name[level:] if level < len(import_name) else ""
        
        # Go up 'level' directories from current file's directory
        target_dir = current_dir
        for _ in range(level):
            target_dir = target_dir.parent
            # Don't go above repo root
            if not str(target_dir).startswith(str(repo)):
                return None
        
        if module_part:
            # e.g., from .utils import X -> resolve utils in target_dir
            candidate = target_dir / f"{module_part.replace('.', '/')}.py"
            if candidate.is_file():
                return str(candidate.relative_to(repo)).replace("\\", "/")
            
            # Try as package with __init__.py
            init_candidate = target_dir / module_part.replace('.', '/') / "__init__.py"
            if init_candidate.is_file():
                return str(init_candidate.relative_to(repo)).replace("\\", "/")
        else:
            # e.g., from . import X -> look for __init__.py in target_dir
            init_candidate = target_dir / "__init__.py"
            if init_candidate.is_file():
                return str(init_candidate.relative_to(repo)).replace("\\", "/")
        
        return None
    
    # Absolute import - check module_to_file map
    # First try exact match
    if import_name in module_to_file:
        return module_to_file[import_name]
    
    # Try prefix matches (e.g., import_name="src.auth" might match "src.auth.utils")
    for module, file_path in module_to_file.items():
        if module.startswith(import_name + "."):
            return file_path
    
    return None


def build_import_graph(repo_path: str, indexed_files: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """For each Python file in indexed_files, uses extract_symbols_for_file()
    to get its imports, then resolves which of those imports correspond to
    OTHER FILES WITHIN THIS REPO (not external packages) by matching import
    names against other files' module paths (e.g. `from src.auth import X`
    maps to src/auth.py if it exists in indexed_files).
    Returns a dict: {file_path: [list of repo-internal files it imports]}
    For non-Python files, or imports that don't resolve to an internal file,
    omit them — do not guess at a match.
    Do not attempt to resolve external/third-party package imports to
    anything — only internal repo files matter for this graph."""
    repo = Path(repo_path).resolve()
    module_to_file = _build_module_to_file_map(indexed_files, repo_path)
    graph: Dict[str, List[str]] = {}
    
    for file_info in indexed_files:
        if file_info.get("language") != "python":
            continue
        
        file_path = file_info["path"]
        abs_file_path = repo / file_path
        
        # Extract symbols to get imports
        symbols = extract_symbols_for_file(str(abs_file_path), "python")
        
        if symbols.get("unsupported") or symbols.get("parse_error"):
            continue
        
        imports = symbols.get("imports", [])
        internal_imports: Set[str] = set()
        
        for imp in imports:
            resolved = _resolve_import(imp, file_path, module_to_file, repo_path)
            if resolved and resolved != file_path:
                internal_imports.add(resolved)
        
        if internal_imports:
            graph[file_path] = sorted(internal_imports)
    
    return graph


def find_importers(repo_path: str, target_file: str, import_graph: Dict[str, List[str]]) -> List[str]:
    """Returns the list of files that import target_file, i.e. the reverse
    lookup of the graph built above. Returns empty list if none found."""
    importers = []
    for file_path, imports in import_graph.items():
        if target_file in imports:
            importers.append(file_path)
    return sorted(importers)