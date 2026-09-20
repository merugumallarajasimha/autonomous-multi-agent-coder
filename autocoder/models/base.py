# autocoder/models/base.py
from abc import ABC, abstractmethod
from typing import Any, Optional, Type


class ModelProvider(ABC):
    provider_name: str  # class attribute set by each subclass

    @abstractmethod
    def invoke(self, prompt: str, structured_output_schema: Optional[Type[Any]] = None) -> dict:
        """Sends prompt to the underlying model. If structured_output_schema
        is provided (a Pydantic model class), the response must be parsed
        into that schema and returned as {"success": True, "data": <parsed
        instance>, "raw": <raw text>}. If no schema, return
        {"success": True, "data": <raw text>, "raw": <raw text>}.
        On any failure (network error, parse failure, timeout), return
        {"success": False, "error": str, "raw": <raw text or "">} instead
        of raising."""

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if this provider is currently reachable/configured
        (e.g. API key present, or for Ollama, the local server responds).
        Must not raise — catch exceptions internally and return False."""

    @abstractmethod
    def estimate_cost(self, prompt: str) -> float:
        """Returns an estimated cost in USD for this call. Return 0.0 for
        free/local providers. This is an estimate for logging/routing
        decisions only, not a billing-accurate calculation."""