# autocoder/project/analyzer.py
from autocoder.project.profile import build_profile, ProjectProfile


def analyze_project(repo_path: str) -> ProjectProfile:
    """A single public entry point that calls build_profile(repo_path) and
    returns the result. This function exists so callers only need one import
    (autocoder.project.analyzer.analyze_project) instead of knowing about
    detector.py/profile.py internals."""
    return build_profile(repo_path)