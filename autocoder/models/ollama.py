# autocoder/models/ollama.py
import os
import requests
from typing import Any, Optional, Type

from langchain_ollama import ChatOllama

from autocoder.models.base import ModelProvider


class OllamaProvider(ModelProvider):
    provider_name = "ollama"

    def __init__(self, model_name: str = "qwen2.5-coder:7b", base_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.base_url = base_url
        self._client = ChatOllama(model=model_name, base_url=base_url)

    def invoke(self, prompt: str, structured_output_schema: Optional[Type[Any]] = None) -> dict:
        try:
            if structured_output_schema:
                structured_llm = self._client.with_structured_output(structured_output_schema)
                result = structured_llm.invoke(prompt)
                raw_text = str(result)
                return {"success": True, "data": result, "raw": raw_text}
            else:
                response = self._client.invoke(prompt)
                raw_text = response.content if hasattr(response, "content") else str(response)
                return {"success": True, "data": raw_text, "raw": raw_text}
        except Exception as e:
            return {"success": False, "error": str(e), "raw": ""}

    def is_available(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return response.status_code == 200
        except Exception:
            return False

    def estimate_cost(self, prompt: str) -> float:
        return 0.0