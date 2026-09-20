# autocoder/languages/registry.py
from typing import List
from autocoder.languages.base import LanguageAdapter
from autocoder.languages.python import PythonAdapter
from autocoder.languages.c import CAdapter
from autocoder.languages.cpp import CppAdapter
from autocoder.languages.java import JavaAdapter
from autocoder.languages.javascript import JavaScriptAdapter


# Registry mapping lowercase language names to adapter classes
_ADAPTER_CLASSES = {
    "python": PythonAdapter,
    "c": CAdapter,
    "cpp": CppAdapter,
    "java": JavaAdapter,
    "javascript": JavaScriptAdapter,
    # "typescript": TypeScriptAdapter,  # not implemented yet
    # "go": GoAdapter,                  # not implemented yet
    # "rust": RustAdapter,              # not implemented yet
}

# Cache of instantiated adapters (singleton per process)
_ADAPTER_INSTANCES: dict[str, LanguageAdapter] = {}


def get_adapter(language: str) -> LanguageAdapter:
    """Returns an instance of the matching adapter class for the given
    language string (as produced by detect_primary_language() in
    detector.py — match on the same lowercase names: python, c, cpp, java,
    javascript, typescript, go, rust). Raise ValueError with a clear message
    if no adapter exists for that language — do not return a fallback/default
    adapter silently."""
    normalized = language.strip().lower()
    if normalized not in _ADAPTER_CLASSES:
        supported = ", ".join(sorted(_ADAPTER_CLASSES.keys()))
        raise ValueError(f"No language adapter for '{language}'. Supported languages: {supported}")
    
    # Return cached instance or create new one
    if normalized not in _ADAPTER_INSTANCES:
        _ADAPTER_INSTANCES[normalized] = _ADAPTER_CLASSES[normalized]()
    return _ADAPTER_INSTANCES[normalized]


def list_supported_languages() -> List[str]:
    """Returns the list of language names that have a registered adapter."""
    return sorted(_ADAPTER_CLASSES.keys())