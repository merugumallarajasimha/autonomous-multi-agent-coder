# autocoder/languages/java.py
import os
import subprocess
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any

from autocoder.languages.base import LanguageAdapter


class JavaAdapter(LanguageAdapter):
    language_name = "java"

    def detect(self, repo_path: str) -> bool:
        """Returns True if .java files or pom.xml/build.gradle exist."""
        repo = Path(repo_path)
        if any(repo.rglob("*.java")):
            return True
        if (repo / "pom.xml").is_file() or (repo / "build.gradle").is_file() or (repo / "build.gradle.kts").is_file():
            return True
        return False

    def install(self, repo_path: str) -> Dict[str, Any]:
        """No-op for Java - dependencies resolved by build system."""
        return {"success": True, "output": "Java dependencies resolved by build system"}

    def build(self, repo_path: str) -> Dict[str, Any]:
        """Build using Maven (pom.xml) or Gradle (build.gradle)."""
        repo = Path(repo_path)
        try:
            if (repo / "pom.xml").is_file():
                # Maven
                result = subprocess.run(
                    ["mvn", "compile"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
                return {"success": result.returncode == 0, "output": result.stdout + result.stderr}
            elif (repo / "build.gradle").is_file() or (repo / "build.gradle.kts").is_file():
                # Gradle
                result = subprocess.run(
                    ["gradle", "compileJava"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
                return {"success": result.returncode == 0, "output": result.stdout + result.stderr}
            else:
                return {"success": False, "output": "no pom.xml or build.gradle found"}
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "build timed out after 180s"}
        except Exception as e:
            return {"success": False, "output": str(e)}

    def test(self, repo_path: str, test_paths: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run tests via Maven (mvn test) or Gradle (gradle test) matching detected build system."""
        repo = Path(repo_path)
        try:
            if (repo / "pom.xml").is_file():
                result = subprocess.run(
                    ["mvn", "test"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
                return {"success": result.returncode == 0, "output": result.stdout + result.stderr, "exit_code": result.returncode}
            elif (repo / "build.gradle").is_file() or (repo / "build.gradle.kts").is_file():
                result = subprocess.run(
                    ["gradle", "test"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
                return {"success": result.returncode == 0, "output": result.stdout + result.stderr, "exit_code": result.returncode}
            else:
                return {"success": True, "output": "no build system detected for test", "exit_code": 0}
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "test timed out after 180s", "exit_code": 124}
        except Exception as e:
            return {"success": False, "output": str(e), "exit_code": -1}

    def lint(self, repo_path: str) -> Dict[str, Any]:
        """No default linter assumed for Java - skip gracefully."""
        return {"success": True, "output": "no default linter for Java, skipping"}

    def format(self, repo_path: str) -> Dict[str, Any]:
        """No default formatter assumed for Java - skip gracefully."""
        return {"success": True, "output": "no default formatter for Java, skipping"}

    def clean(self, repo_path: str) -> Dict[str, Any]:
        """Run mvn clean or gradle clean matching detected build system."""
        repo = Path(repo_path)
        try:
            if (repo / "pom.xml").is_file():
                result = subprocess.run(
                    ["mvn", "clean"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                return {"success": result.returncode == 0, "output": result.stdout + result.stderr}
            elif (repo / "build.gradle").is_file() or (repo / "build.gradle.kts").is_file():
                result = subprocess.run(
                    ["gradle", "clean"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                return {"success": result.returncode == 0, "output": result.stdout + result.stderr}
            else:
                # Fallback: remove target/ and build/ directories
                removed = []
                for d in ["target", "build"]:
                    path = repo / d
                    if path.is_dir():
                        shutil.rmtree(path, ignore_errors=True)
                        removed.append(d)
                return {"success": True, "output": f"removed: {', '.join(removed) if removed else 'nothing to clean'}"}
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "clean timed out after 60s"}
        except Exception as e:
            return {"success": False, "output": str(e)}