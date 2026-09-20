# autocoder/languages/base.py
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any


class LanguageAdapter(ABC):
    """Abstract base class for language-specific operations.
    
    Each subclass must set the `language_name` class attribute and implement
    all abstract methods. All methods return a dict with at least "success"
    and "output" keys — no exceptions should propagate out of these methods.
    """
    language_name: str  # Class attribute, must be set by each subclass

    @abstractmethod
    def detect(self, repo_path: str) -> bool:
        """Returns True if this adapter applies to repo_path."""
        ...

    @abstractmethod
    def install(self, repo_path: str) -> Dict[str, Any]:
        """Installs dependencies. Returns {"success": bool, "output": str}."""
        ...

    @abstractmethod
    def build(self, repo_path: str) -> Dict[str, Any]:
        """Compiles/builds if applicable. Returns {"success": bool,
        "output": str}. For interpreted languages with no build step, return
        {"success": True, "output": "no build step required"}."""
        ...

    @abstractmethod
    def test(self, repo_path: str, test_paths: Optional[List[str]] = None) -> Dict[str, Any]:
        """Runs tests, optionally scoped to test_paths. Returns
        {"success": bool, "output": str, "exit_code": int}."""
        ...

    @abstractmethod
    def lint(self, repo_path: str) -> Dict[str, Any]:
        """Returns {"success": bool, "output": str}."""
        ...

    @abstractmethod
    def format(self, repo_path: str) -> Dict[str, Any]:
        """Returns {"success": bool, "output": str}."""
        ...

    @abstractmethod
    def clean(self, repo_path: str) -> Dict[str, Any]:
        """Removes build artifacts. Returns {"success": bool, "output": str}."""
        ...