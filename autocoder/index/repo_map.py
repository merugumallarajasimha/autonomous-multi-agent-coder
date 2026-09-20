# autocoder/index/repo_map.py
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from autocoder.index.repo_indexer import index_files, find_entry_points, find_config_files
from autocoder.index.symbol_index import extract_symbols_for_file
from autocoder.index.dependency_graph import build_import_graph


def build_repo_map(repo_path: str) -> Dict[str, Any]:
    """Assembles the full repo map by calling the existing functions from
    the three files above — do not reimplement any of their logic here, only
    call them and combine results:
    {
      "files": <output of index_files()>,
      "symbols": {file_path: extract_symbols_for_file(...) for each file},
      "import_graph": <output of build_import_graph()>,
      "entry_points": <output of find_entry_points()>,
      "config_files": <output of find_config_files()>,
      "generated_at": <ISO timestamp>
    }"""
    repo = Path(repo_path).resolve()
    
    # Index all files
    indexed_files = index_files(repo_path)
    
    # Extract symbols for each file
    symbols: Dict[str, Any] = {}
    for file_info in indexed_files:
        file_path = file_info["path"]
        language = file_info["language"]
        abs_path = repo / file_path
        symbols[file_path] = extract_symbols_for_file(str(abs_path), language)
    
    # Build import graph
    import_graph = build_import_graph(repo_path, indexed_files)
    
    # Find entry points
    entry_points = find_entry_points(repo_path, indexed_files)
    
    # Find config files
    config_files = find_config_files(repo_path)
    
    return {
        "files": indexed_files,
        "symbols": symbols,
        "import_graph": import_graph,
        "entry_points": entry_points,
        "config_files": config_files,
        "generated_at": datetime.utcnow().isoformat(),
    }


def save_repo_map(repo_path: str, output_path: str = "repo_map.json") -> str:
    """Calls build_repo_map() and writes it as JSON to output_path (relative
    to repo_path). Returns the full path written."""
    repo = Path(repo_path).resolve()
    output_file = repo / output_path
    repo_map = build_repo_map(repo_path)
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(repo_map, f, indent=2)
    
    return str(output_file)


def load_repo_map(repo_path: str, map_path: str = "repo_map.json") -> Optional[Dict[str, Any]]:
    """Loads a previously saved repo_map.json if it exists, returns None if
    not found. Does not regenerate it — that's the caller's decision."""
    repo = Path(repo_path).resolve()
    map_file = repo / map_path
    
    if not map_file.is_file():
        return None
    
    try:
        with open(map_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None