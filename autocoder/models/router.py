# autocoder/models/router.py
from typing import Dict, List, Tuple, Optional

from autocoder.models.base import ModelProvider
from autocoder.models.ollama import OllamaProvider
from autocoder.models.openrouter import OpenRouterProvider
from autocoder.models.groq import GroqProvider
from autocoder.models.google import GoogleAIProvider


# Provider name -> constructor mapping
_PROVIDER_MAP: Dict[str, type] = {
    "ollama": OllamaProvider,
    "openrouter": OpenRouterProvider,
    "groq": GroqProvider,
    "google": GoogleAIProvider,
}


class ModelRouter:
    def __init__(self, config: dict):
        """config maps agent name -> ordered list of (provider_name,
        model_name) tuples to try in priority order, e.g.:
        {
          "planner": [("ollama", "qwen2.5:3b")],
          "coder": [("ollama", "qwen2.5-coder:7b"), ("groq", "llama-3.3-70b")],
        }
        Stores this config and lazily instantiates provider objects on
        first use (don't construct all providers up front if they're not
        needed)."""
        self._config = config
        self._instances: Dict[str, ModelProvider] = {}  # key: "provider_name:model_name"

    def _get_instance(self, provider_name: str, model_name: str) -> Optional[ModelProvider]:
        """Lazily instantiate and cache a provider instance."""
        key = f"{provider_name}:{model_name}"
        if key in self._instances:
            return self._instances[key]

        provider_class = _PROVIDER_MAP.get(provider_name)
        if not provider_class:
            return None

        try:
            instance = provider_class(model_name=model_name)
            self._instances[key] = instance
            return instance
        except Exception:
            return None

    def get(self, agent: str, complexity: str = "normal") -> ModelProvider:
        """Returns the first available provider (via is_available()) from
        the ordered list configured for `agent`. Ignores the `complexity`
        parameter's exact value for now (accept it for future use) but DO
        NOT implement complexity-based model selection logic yet — that's
        explicitly out of scope for this step, just accept and ignore the
        parameter without raising.
        If NONE of the configured providers for this agent are available,
        raise a clear RuntimeError naming the agent and which providers were
        tried and failed — do not silently return None or fall back to an
        unconfigured default."""
        # Accept complexity parameter for future use, but ignore it
        _ = complexity

        agent_config = self._config.get(agent)
        if not agent_config:
            raise RuntimeError(f"No model configuration found for agent: {agent}")

        tried = []
        for provider_name, model_name in agent_config:
            tried.append(f"{provider_name}:{model_name}")
            instance = self._get_instance(provider_name, model_name)
            if instance and instance.is_available():
                return instance

        raise RuntimeError(
            f"No available provider for agent '{agent}'. Tried (in order): {', '.join(tried)}"
        )

    @staticmethod
    def get_default_config() -> dict:
        """A module-level or static helper returning this exact default
        mapping, matching the user's stated hardware setup:
        {
          "planner":  [("ollama", "qwen2.5:3b")],
          "coder":    [("ollama", "qwen2.5-coder:7b")],
          "verifier": [("ollama", "qwen2.5-coder:7b")],
          "reviewer": [("ollama", "qwen2.5-coder:7b")],
          "fixer":    [("ollama", "qwen2.5-coder:7b")],
        }
        No cloud fallbacks in the default — those are opt-in via a
        different config, not the default behavior."""
        return {
            "planner": [("ollama", "qwen2.5:3b")],
            "coder": [("ollama", "qwen2.5-coder:7b")],
            "verifier": [("ollama", "qwen2.5-coder:7b")],
            "reviewer": [("ollama", "qwen2.5-coder:7b")],
            "fixer": [("ollama", "qwen2.5-coder:7b")],
        }

    @classmethod
    def from_config_file(cls, config_dir: str = "config") -> "ModelRouter":
        """Builds a ModelRouter by calling load_models_config() from the config
        loader instead of using the hardcoded get_default_config() dict. If the
        config file is missing or fails to load, raise clearly rather than
        silently falling back to get_default_config() — the caller should
        decide explicitly whether to fall back, not have it happen invisibly."""
        from autocoder.config.loader import load_models_config
        config = load_models_config(config_dir)
        return cls(config)