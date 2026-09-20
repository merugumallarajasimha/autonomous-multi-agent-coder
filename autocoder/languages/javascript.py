# autocoder/languages/javascript.py
import json
import subprocess
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any

from autocoder.languages.base import LanguageAdapter


class JavaScriptAdapter(LanguageAdapter):
    language_name = "javascript"

    def detect(self, repo_path: str) -> bool:
        """Returns True if .js/.ts/.jsx/.tsx files or package.json exist."""
        repo = Path(repo_path)
        for ext in [".js", ".jsx", ".ts", ".tsx"]:
            if any(repo.rglob(f"*{ext}")):
                return True
        if (repo / "package.json").is_file():
            return True
        return False

    def install(self, repo_path: str) -> Dict[str, Any]:
        """Install dependencies via npm install."""
        try:
            result = subprocess.run(
                ["npm", "install"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=180,
            )
            return {"success": result.returncode == 0, "output": result.stdout + result.stderr}
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "npm install timed out after 180s"}
        except Exception as e:
            return {"success": False, "output": str(e)}

    def build(self, repo_path: str) -> Dict[str, Any]:
        """Run npm run build only if a build script exists in package.json."""
        repo = Path(repo_path)
        pkg_file = repo / "package.json"
        if not pkg_file.is_file():
            return {"success": True, "output": "no package.json, skipping build"}

        try:
            pkg = json.loads(pkg_file.read_text(encoding="utf-8"))
            scripts = pkg.get("scripts", {})
            if "build" not in scripts:
                return {"success": True, "output": "no build script in package.json, skipping"}
        except (json.JSONDecodeError, OSError):
            return {"success": False, "output": "failed to read package.json"}

        try:
            result = subprocess.run(
                ["npm", "run", "build"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=120,
            )
            return {"success": result.returncode == 0, "output": result.stdout + result.stderr}
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "npm run build timed out after 120s"}
        except Exception as e:
            return {"success": False, "output": str(e)}

    def test(self, repo_path: str, test_paths: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run tests via npm test."""
        try:
            result = subprocess.run(
                ["npm", "test"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=120,
            )
            return {"success": result.returncode == 0, "output": result.stdout + result.stderr, "exit_code": result.returncode}
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "npm test timed out after 120s", "exit_code": 124}
        except Exception as e:
            return {"success": False, "output": str(e), "exit_code": -1}

    def lint(self, repo_path: str) -> Dict[str, Any]:
        """Run npm run lint if that script exists in package.json."""
        repo = Path(repo_path)
        pkg_file = repo / "package.json"
        if not pkg_file.is_file():
            return {"success": True, "output": "no package.json, skipping lint"}

        try:
            pkg = json.loads(pkg_file.read_text(encoding="utf-8"))
            scripts = pkg.get("scripts", {})
            if "lint" not in scripts:
                return {"success": True, "output": "no lint script in package.json, skipping"}
        except (json.JSONDecodeError, OSError):
            return {"success": False, "output": "failed to read package.json"}

        try:
            result = subprocess.run(
                ["npm", "run", "lint"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60,
            )
            return {"success": result.returncode == 0, "output": result.stdout + result.stderr}
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "npm run lint timed out after 60s"}
        except Exception as e:
            return {"success": False, "output": str(e)}

    def format(self, repo_path: str) -> Dict[str, Any]:
        """Run npm run format if that script exists in package.json."""
        repo = Path(repo_path)
        pkg_file = repo / "package.json"
        if not pkg_file.is_file():
            return {"success": True, "output": "no package.json, skipping format"}

        try:
            pkg = json.loads(pkg_file.read_text(encoding="utf-8"))
            scripts = pkg.get("scripts", {})
            if "format" not in scripts:
                return {"success": True, "output": "no format script in package.json, skipping"}
        except (json.JSONDecodeError, OSError):
            return {"success": False, "output": "failed to read package.json"}

        try:
            result = subprocess.run(
                ["npm", "run", "format"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60,
            )
            return {"success": result.returncode == 0, "output": result.stdout + result.stderr}
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "npm run format timed out after 60s"}
        except Exception as e:
            return {"success": False, "output": str(e)}

    def clean(self, repo_path: str) -> Dict[str, Any]:
        """Remove node_modules, dist, build directories if present."""
        repo = Path(repo_path)
        removed = []
        try:
            for d in ["node_modules", "dist", "build"]:
                path = repo / d
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                    removed.append(d)
            return {"success": True, "output": f"removed: {', '.join(removed) if removed else 'nothing to clean'}"}
        except Exception as e:
            return {"success": False, "output": str(e)}