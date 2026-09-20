# autocoder/languages/python.py
import os
import subprocess
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any

from autocoder.languages.base import LanguageAdapter


class PythonAdapter(LanguageAdapter):
    language_name = "python"

    def detect(self, repo_path: str) -> bool:
        """Returns True if .py files or pyproject.toml/requirements.txt exist."""
        repo = Path(repo_path)
        # Check for .py files
        if any(repo.rglob("*.py")):
            return True
        # Check for Python config files
        if (repo / "pyproject.toml").is_file() or (repo / "requirements.txt").is_file():
            return True
        return False

    def install(self, repo_path: str) -> Dict[str, Any]:
        """Install dependencies via pip if requirements.txt or pyproject.toml exists."""
        repo = Path(repo_path)
        try:
            if (repo / "requirements.txt").is_file():
                result = subprocess.run(
                    ["pip", "install", "-r", "requirements.txt"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                return {"success": result.returncode == 0, "output": result.stdout + result.stderr}
            elif (repo / "pyproject.toml").is_file():
                # Try pip install -e . for editable install
                result = subprocess.run(
                    ["pip", "install", "-e", "."],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                return {"success": result.returncode == 0, "output": result.stdout + result.stderr}
            else:
                return {"success": True, "output": "no requirements.txt or pyproject.toml found, skipping install"}
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "pip install timed out after 120s"}
        except Exception as e:
            return {"success": False, "output": str(e)}

    def build(self, repo_path: str) -> Dict[str, Any]:
        """Python is interpreted, no build step required."""
        return {"success": True, "output": "no build step required"}

    def test(self, repo_path: str, test_paths: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run tests via pytest. Use test_paths if provided, else let pytest discover."""
        try:
            cmd = ["python", "-m", "pytest"]
            if test_paths:
                cmd.extend(test_paths)
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=120,
            )
            return {"success": result.returncode == 0, "output": result.stdout + result.stderr, "exit_code": result.returncode}
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "pytest timed out after 120s", "exit_code": 124}
        except Exception as e:
            return {"success": False, "output": str(e), "exit_code": -1}

    def lint(self, repo_path: str) -> Dict[str, Any]:
        """Run ruff check if available, else skip gracefully."""
        # Check if ruff is available
        try:
            subprocess.run(["ruff", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            return {"success": True, "output": "ruff not available, skipping lint"}

        try:
            result = subprocess.run(
                ["ruff", "check", "."],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60,
            )
            return {"success": result.returncode == 0, "output": result.stdout + result.stderr}
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "ruff check timed out after 60s"}
        except Exception as e:
            return {"success": False, "output": str(e)}

    def format(self, repo_path: str) -> Dict[str, Any]:
        """Run ruff format if available, else skip gracefully."""
        try:
            subprocess.run(["ruff", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            return {"success": True, "output": "ruff not available, skipping format"}

        try:
            result = subprocess.run(
                ["ruff", "format", "."],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60,
            )
            return {"success": result.returncode == 0, "output": result.stdout + result.stderr}
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "ruff format timed out after 60s"}
        except Exception as e:
            return {"success": False, "output": str(e)}

    def clean(self, repo_path: str) -> Dict[str, Any]:
        """Remove __pycache__, .pytest_cache, *.egg-info directories."""
        repo = Path(repo_path)
        removed = []
        try:
            for pattern in ["**/__pycache__", "**/.pytest_cache", "**/*.egg-info"]:
                for path in repo.glob(pattern):
                    if path.is_dir():
                        shutil.rmtree(path, ignore_errors=True)
                        removed.append(str(path))
            return {"success": True, "output": f"removed: {', '.join(removed) if removed else 'nothing to clean'}"}
        except Exception as e:
            return {"success": False, "output": str(e)}