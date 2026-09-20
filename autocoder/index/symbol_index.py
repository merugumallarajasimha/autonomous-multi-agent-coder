# autocoder/index/symbol_index.py
import ast
from typing import List, Dict, Any


def extract_python_symbols(file_path: str) -> Dict[str, Any]:
    """Uses Python's built-in `ast` module to parse file_path and return:
    {
      "classes": [{"name": str, "line": int, "methods": [str]}],
      "functions": [{"name": str, "line": int, "args": [str]}],
      "imports": [str]   # module names imported, e.g. "os", "requests"
    }
    If the file fails to parse (SyntaxError), return
    {"classes": [], "functions": [], "imports": [], "parse_error": str(error)}
    rather than raising."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
    except (OSError, UnicodeDecodeError) as e:
        return {
            "classes": [],
            "functions": [],
            "imports": [],
            "parse_error": f"Could not read file: {e}"
        }

    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError as e:
        return {
            "classes": [],
            "functions": [],
            "imports": [],
            "parse_error": str(e)
        }

    classes: List[Dict[str, Any]] = []
    functions: List[Dict[str, Any]] = []
    imports: List[str] = []

    for node in ast.walk(tree):
        # Classes
        if isinstance(node, ast.ClassDef):
            methods = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    methods.append(item.name)
            classes.append({
                "name": node.name,
                "line": node.lineno,
                "methods": methods,
            })

        # Functions (top-level only, not methods inside classes)
        elif isinstance(node, ast.FunctionDef):
            # Check if this is a top-level function (not inside a class)
            parent = getattr(node, "parent", None)
            if parent is None or not isinstance(parent, ast.ClassDef):
                args = [arg.arg for arg in node.args.args]
                functions.append({
                    "name": node.name,
                    "line": node.lineno,
                    "args": args,
                })

        # Imports
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                if module:
                    imports.append(f"{module}.{alias.name}")
                else:
                    imports.append(alias.name)

    # Add parent references for function detection
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child.parent = node

    return {
        "classes": classes,
        "functions": functions,
        "imports": imports,
    }


def extract_symbols_for_file(file_path: str, language: str) -> Dict[str, Any]:
    """Dispatches to extract_python_symbols() if language == "python".
    For any other language, return
    {"classes": [], "functions": [], "imports": [], "unsupported": True} —
    do not attempt regex-based parsing for other languages in this step,
    that risks producing wrong data that looks confident. Extending to other
    languages is explicitly out of scope here."""
    if language == "python":
        return extract_python_symbols(file_path)
    else:
        return {
            "classes": [],
            "functions": [],
            "imports": [],
            "unsupported": True,
        }