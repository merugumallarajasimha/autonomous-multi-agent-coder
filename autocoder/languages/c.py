# autocoder/languages/c.py
import os
import subprocess
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any

from autocoder.languages.base import LanguageAdapter


class CAdapter(LanguageAdapter):
    language_name = "c"

    def detect(self, repo_path: str) -> bool:
        """Returns True if .c files or CMakeLists.txt/Makefile exist."""
        repo = Path(repo_path)
        if any(repo.rglob("*.c")):
            return True
        if (repo / "CMakeLists.txt").is_file() or (repo / "Makefile").is_file():
            return True
        return False

    def install(self, repo_path: str) -> Dict[str, Any]:
        """No-op for C - system libraries assumed present."""
        return {"success": True, "output": "C uses system libraries, no install step"}

    def build(self, repo_path: str) -> Dict[str, Any]:
        """Build using CMake, Makefile, or direct gcc compilation as fallback."""
        repo = Path(repo_path)
        try:
            # Prefer CMake if CMakeLists.txt exists
            if (repo / "CMakeLists.txt").is_file():
                # Configure
                result = subprocess.run(
                    ["cmake", "-B", "build"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode != 0:
                    return {"success": False, "output": f"cmake configure failed: {result.stdout + result.stderr}"}
                # Build
                result = subprocess.run(
                    ["cmake", "--build", "build"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                return {"success": result.returncode == 0, "output": result.stdout + result.stderr}

            # Fallback to Makefile
            elif (repo / "Makefile").is_file():
                result = subprocess.run(
                    ["make"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                return {"success": result.returncode == 0, "output": result.stdout + result.stderr}

            # Fallback: compile all .c files directly with gcc
            else:
                c_files = list(repo.rglob("*.c"))
                if not c_files:
                    return {"success": False, "output": "no .c files found to compile"}
                # Try to find a main file or compile all to an executable
                main_files = [f for f in c_files if "main" in f.name.lower()]
                target = main_files[0] if main_files else c_files[0]
                output_exe = repo / "build_output"
                cmd = ["gcc", "-o", str(output_exe)] + [str(f) for f in c_files]
                result = subprocess.run(
                    cmd,
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                return {"success": result.returncode == 0, "output": result.stdout + result.stderr}
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "build timed out after 120s"}
        except Exception as e:
            return {"success": False, "output": str(e)}

    def test(self, repo_path: str, test_paths: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run the built test binary if one exists (look for common names)."""
        repo = Path(repo_path)
        # Common test binary names
        test_names = ["test", "run_tests", "tests", "unit_test", "check"]
        test_binary = None
        # Check build directory first (CMake)
        build_dir = repo / "build"
        for name in test_names:
            candidate = build_dir / name
            if candidate.is_file() and os.access(candidate, os.X_OK):
                test_binary = candidate
                break
            candidate = build_dir / f"{name}.exe"
            if candidate.is_file():
                test_binary = candidate
                break
        # Check repo root
        if not test_binary:
            for name in test_names:
                candidate = repo / name
                if candidate.is_file() and os.access(candidate, os.X_OK):
                    test_binary = candidate
                    break
        # Check current directory for test binary
        if not test_binary:
            for f in repo.iterdir():
                if f.is_file() and os.access(f, os.X_OK) and f.name.startswith("test"):
                    test_binary = f
                    break

        if not test_binary:
            return {"success": True, "output": "no test binary found (looked for: test, run_tests, tests, unit_test, check)", "exit_code": 0}

        try:
            result = subprocess.run(
                [str(test_binary)],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60,
            )
            return {"success": result.returncode == 0, "output": result.stdout + result.stderr, "exit_code": result.returncode}
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "test binary timed out after 60s", "exit_code": 124}
        except Exception as e:
            return {"success": False, "output": str(e), "exit_code": -1}

    def lint(self, repo_path: str) -> Dict[str, Any]:
        """No default linter assumed for C - skip gracefully."""
        return {"success": True, "output": "no default linter for C, skipping"}

    def format(self, repo_path: str) -> Dict[str, Any]:
        """No default formatter assumed for C - skip gracefully."""
        return {"success": True, "output": "no default formatter for C, skipping"}

    def clean(self, repo_path: str) -> Dict[str, Any]:
        """Remove build/ directory."""
        repo = Path(repo_path)
        build_dir = repo / "build"
        try:
            if build_dir.is_dir():
                shutil.rmtree(build_dir, ignore_errors=True)
                return {"success": True, "output": "removed build/ directory"}
            return {"success": True, "output": "no build/ directory to clean"}
        except Exception as e:
            return {"success": False, "output": str(e)}