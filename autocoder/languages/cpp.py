# autocoder/languages/cpp.py
import os
import subprocess
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any

from autocoder.languages.base import LanguageAdapter


class CppAdapter(LanguageAdapter):
    language_name = "cpp"

    def detect(self, repo_path: str) -> bool:
        """Returns True if .cpp/.cc/.cxx/.hpp files or CMakeLists.txt/Makefile exist."""
        repo = Path(repo_path)
        for ext in [".cpp", ".cc", ".cxx", ".hpp", ".h", ".c"]:
            if any(repo.rglob(f"*{ext}")):
                return True
        if (repo / "CMakeLists.txt").is_file() or (repo / "Makefile").is_file():
            return True
        return False

    def install(self, repo_path: str) -> Dict[str, Any]:
        """No-op for C++ - system libraries assumed present."""
        return {"success": True, "output": "C++ uses system libraries, no install step"}

    def build(self, repo_path: str) -> Dict[str, Any]:
        """Build using CMake, Makefile, or direct g++ compilation as fallback."""
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

            # Fallback: compile all .cpp/.cc/.cxx files directly with g++
            else:
                cpp_files = []
                for ext in [".cpp", ".cc", ".cxx"]:
                    cpp_files.extend(repo.rglob(f"*{ext}"))
                if not cpp_files:
                    return {"success": False, "output": "no C++ source files found to compile"}
                main_files = [f for f in cpp_files if "main" in f.name.lower()]
                target = main_files[0] if main_files else cpp_files[0]
                output_exe = repo / "build_output"
                cmd = ["g++", "-o", str(output_exe)] + [str(f) for f in cpp_files]
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
        """If GoogleTest is detected in CMakeLists.txt, run the built test binary;
        otherwise report no test framework found rather than guessing."""
        repo = Path(repo_path)
        
        # Check if GoogleTest is mentioned in CMakeLists.txt
        cmake_file = repo / "CMakeLists.txt"
        has_gtest = False
        if cmake_file.is_file():
            try:
                content = cmake_file.read_text()
                if "gtest" in content.lower() or "googletest" in content.lower() or "GTest" in content:
                    has_gtest = True
            except Exception:
                pass

        if not has_gtest:
            return {"success": True, "output": "no GoogleTest detected in CMakeLists.txt, skipping test run (no test framework found)", "exit_code": 0}

        # GoogleTest detected - look for test binary
        test_names = ["test", "run_tests", "tests", "unit_test", "gtest", "check"]
        test_binary = None
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

        if not test_binary:
            return {"success": False, "output": "GoogleTest detected but no test binary found in build/", "exit_code": 1}

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
        """No default linter assumed for C++ - skip gracefully."""
        return {"success": True, "output": "no default linter for C++, skipping"}

    def format(self, repo_path: str) -> Dict[str, Any]:
        """No default formatter assumed for C++ - skip gracefully."""
        return {"success": True, "output": "no default formatter for C++, skipping"}

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