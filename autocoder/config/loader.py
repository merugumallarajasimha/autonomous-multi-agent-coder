# autocoder/config/loader.py
import os
from typing import Dict, List, Tuple, Set, Any

import yaml


def load_workflow(name: str, config_dir: str = "config/workflows") -> List[str]:
    """Loads config/workflows/{name}.yaml and returns the 'workflow' list of
    node names. Raises FileNotFoundError with a clear message if the file
    doesn't exist — do not silently fall back to 'default'."""
    path = os.path.join(config_dir, f"{name}.yaml")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Workflow config not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data or "workflow" not in data:
        raise ValueError(f"Workflow config {path} missing 'workflow' key")

    workflow = data["workflow"]
    if not isinstance(workflow, list):
        raise ValueError(f"Workflow config {path}: 'workflow' must be a list")

    return workflow


def load_agents_config(config_dir: str = "config") -> Dict[str, Any]:
    """Loads config/agents.yaml, returns the 'agents' dict."""
    path = os.path.join(config_dir, "agents.yaml")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Agents config not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data or "agents" not in data:
        raise ValueError(f"Agents config {path} missing 'agents' key")

    return data["agents"]


def load_models_config(config_dir: str = "config") -> Dict[str, List[Tuple[str, str]]]:
    """Loads config/models.yaml, returns the 'models' dict in the same
    shape ModelRouter.get_default_config() from Phase 6 produces (list of
    {provider, model} dicts per agent) — convert the YAML's dict-of-dicts
    into the list-of-tuples shape ModelRouter expects, e.g.
    [("ollama", "qwen2.5-coder:7b")]. Show the exact conversion logic."""
    path = os.path.join(config_dir, "models.yaml")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Models config not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data or "models" not in data:
        raise ValueError(f"Models config {path} missing 'models' key")

    models = data["models"]
    if not isinstance(models, dict):
        raise ValueError(f"Models config {path}: 'models' must be a dict")

    result: Dict[str, List[Tuple[str, str]]] = {}
    for agent, providers in models.items():
        if not isinstance(providers, list):
            raise ValueError(f"Models config {path}: agent '{agent}' must be a list")

        converted = []
        for p in providers:
            if not isinstance(p, dict):
                raise ValueError(f"Models config {path}: provider entry must be a dict")
            provider = p.get("provider")
            model = p.get("model")
            if not provider or not model:
                raise ValueError(f"Models config {path}: missing 'provider' or 'model' in {p}")
            converted.append((provider, model))
        result[agent] = converted

    return result


def validate_workflow(workflow: List[str], known_agents: Set[str]) -> List[str]:
    """Returns a list of any node names in `workflow` that are NOT present
    in known_agents. Empty list means fully valid. Does not raise — the
    caller decides what to do with invalid names."""
    unknown = []
    for node in workflow:
        if node not in known_agents:
            unknown.append(node)
    return unknown