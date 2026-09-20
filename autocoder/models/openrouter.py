# autocoder/models/openrouter.py
import os
import json
import requests
from typing import Any, Optional, Type

from autocoder.models.base import ModelProvider


class OpenRouterProvider(ModelProvider):
    provider_name = "openrouter"

    def __init__(self, model_name: str = "openrouter/auto"):
        self.model_name = model_name
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"

    def invoke(self, prompt: str, structured_output_schema: Optional[Type[Any]] = None) -> dict:
        if not self.api_key:
            return {"success": False, "error": "OPENROUTER_API_KEY not set", "raw": ""}

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/autocoder",
                "X-Title": "Autocoder",
            }

            messages = [{"role": "user", "content": prompt}]

            # For structured output, we ask the model to return JSON and parse it
            if structured_output_schema:
                schema_desc = structured_output_schema.model_json_schema()
                messages.append({
                    "role": "system",
                    "content": f"Return only valid JSON matching this schema: {json.dumps(schema_desc)}"
                })

            payload = {
                "model": self.model_name,
                "messages": messages,
                "temperature": 0,
            }

            response = requests.post(self.api_url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]
            raw_text = content

            if structured_output_schema:
                try:
                    parsed = structured_output_schema.model_validate_json(content)
                    return {"success": True, "data": parsed, "raw": raw_text}
                except Exception as e:
                    return {"success": False, "error": f"Failed to parse structured output: {e}", "raw": raw_text}

            return {"success": True, "data": raw_text, "raw": raw_text}

        except Exception as e:
            return {"success": False, "error": str(e), "raw": ""}

    def is_available(self) -> bool:
        return bool(self.api_key)

    def estimate_cost(self, prompt: str) -> float:
        # Rough estimate: ~$0.001 per 1K tokens (conservative, varies by model)
        # This is approximate - actual cost depends on the routed model
        token_estimate = len(prompt) / 4  # rough char-to-token
        return (token_estimate / 1000) * 0.001