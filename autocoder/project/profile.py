# autocoder/project/profile.py
import json
import os
from pathlib import Path
from typing import Dict, List, Any

from autocoder.project.detector import detect_languages, detect_config_files, detect_primary_language


class ProjectProfile:
    def __init__(
        self,
        languages: Dict[str, int],
        primary_language: str,
        framework: str,
        build_system: str,
        package_manager: str,
        test_framework: str,
        source_dirs: List[str],
        test_dirs: List[str],
    ):
        self.languages = languages
        self.primary_language = primary_language
        self.framework = framework
        self.build_system = build_system
        self.package_manager = package_manager
        self.test_framework = test_framework
        self.source_dirs = source_dirs
        self.test_dirs = test_dirs

    def to_dict(self) -> Dict[str, Any]:
        return {
            "languages": self.languages,
            "primary_language": self.primary_language,
            "framework": self.framework,
            "build_system": self.build_system,
            "package_manager": self.package_manager,
            "test_framework": self.test_framework,
            "source_dirs": self.source_dirs,
            "test_dirs": self.test_dirs,
        }


def _read_package_json(repo_path: str) -> Dict[str, Any]:
    """Read package.json if it exists and is valid JSON."""
    path = Path(repo_path) / "package.json"
    if path.is_file():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _read_pyproject_toml(repo_path: str) -> Dict[str, Any]:
    """Read pyproject.toml for framework detection (basic parsing)."""
    path = Path(repo_path) / "pyproject.toml"
    if path.is_file():
        try:
            # Try tomllib (Python 3.11+), fallback to tomli if available
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib
            with open(path, "rb") as f:
                return tomllib.load(f)
        except Exception:
            pass
    return {}


def _find_common_dirs(repo_path: str, candidates: List[str]) -> List[str]:
    """Return list of candidate directories that actually exist in repo_path."""
    repo = Path(repo_path).resolve()
    found = []
    for name in candidates:
        p = repo / name
        if p.is_dir():
            found.append(name)
    return found


def build_profile(repo_path: str) -> ProjectProfile:
    """Uses detect_languages() and detect_primary_language() from detector.py
    to populate languages and primary_language. For the remaining fields
    (framework, build_system, package_manager, test_framework, source_dirs,
    test_dirs), use ONLY simple deterministic rules based on config file
    presence."""
    languages = detect_languages(repo_path)
    primary_language = detect_primary_language(repo_path)
    config = detect_config_files(repo_path)

    # Initialize all to unknown
    framework = "unknown"
    build_system = "unknown"
    package_manager = "unknown"
    test_framework = "unknown"

    # JavaScript / Node.js
    if config.get("package.json"):
        package_manager = "npm"
        build_system = "npm"  # default
        pkg = _read_package_json(repo_path)
        scripts = pkg.get("scripts", {})
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

        # Detect test framework
        if "jest" in deps or "jest" in scripts.get("test", ""):
            test_framework = "jest"
        elif "mocha" in deps or "mocha" in scripts.get("test", ""):
            test_framework = "mocha"
        elif "vitest" in deps:
            test_framework = "vitest"
        elif "test" in scripts:
            test_framework = "npm test"

        # Detect common frameworks
        if "react" in deps:
            framework = "react"
        elif "vue" in deps:
            framework = "vue"
        elif "angular" in deps or "@angular/core" in deps:
            framework = "angular"
        elif "next" in deps:
            framework = "next.js"
        elif "express" in deps:
            framework = "express"
        elif "fastify" in deps:
            framework = "fastify"

        # Detect build system
        if "vite" in deps:
            build_system = "vite"
        elif "webpack" in deps:
            build_system = "webpack"
        elif "esbuild" in deps:
            build_system = "esbuild"

    # Rust
    if config.get("Cargo.toml"):
        build_system = "cargo"
        package_manager = "cargo"
        test_framework = "cargo test"

    # Go
    if config.get("go.mod"):
        build_system = "go build"
        package_manager = "go mod"
        test_framework = "go test"

    # Java
    if config.get("pom.xml"):
        build_system = "maven"
        package_manager = "maven"
        test_framework = "junit"
    elif config.get("build.gradle") or config.get("build.gradle.kts"):
        build_system = "gradle"
        package_manager = "gradle"
        test_framework = "junit"

    # C++
    if config.get("CMakeLists.txt"):
        build_system = "cmake"

    # Python
    if config.get("pyproject.toml") or config.get("requirements.txt"):
        package_manager = "pip"
        test_framework = "pytest"
        pyproject = _read_pyproject_toml(repo_path)
        if pyproject:
            # Check for framework in pyproject.toml
            if "project" in pyproject:
                deps = pyproject["project"].get("dependencies", [])
                if any("django" in d.lower() for d in deps):
                    framework = "django"
                elif any("fastapi" in d.lower() for d in deps):
                    framework = "fastapi"
                elif any("flask" in d.lower() for d in deps):
                    framework = "flask"
            # Check tool config for test framework
            tool = pyproject.get("tool", {})
            if "pytest" in tool:
                test_framework = "pytest"
            if "poetry" in tool:
                package_manager = "poetry"
            if "uv" in tool:
                package_manager = "uv"

    # Source and test directories (conventional names that actually exist)
    source_dirs = _find_common_dirs(repo_path, ["src", "lib", "source", "app"])
    test_dirs = _find_common_dirs(repo_path, ["tests", "test", "testing", "spec", "__tests__"])

    return ProjectProfile(
        languages=languages,
        primary_language=primary_language,
        framework=framework,
        build_system=build_system,
        package_manager=package_manager,
        test_framework=test_framework,
        source_dirs=source_dirs,
        test_dirs=test_dirs,
    )