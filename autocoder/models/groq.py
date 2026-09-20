# autocoder/models/groq.py
import os
from typing import Any, Optional, Type

from openai import OpenAI

from autocoder.models.base import ModelProvider


class GroqProvider(ModelProvider):
    provider_name = "groq"

    def __init__(self, model_name: str = "llama-3.3-70b-versatile"):
        self.model_name = model_name
        self.api_key = os.environ.get("GROQ_API_KEY")
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.groq.com/openai/v1"
        ) if self.api_key else None

    def invoke(self, prompt: str, structured_output_schema: Optional[Type[Any]] = None) -> dict:
        if not self.api_key or not self.client:
            return {"success": False, "error": "GROQ_API_KEY not set", "raw": ""}

        try:
            messages = [{"role": "user", "content": prompt}]

            if structured_output_schema:
                # Use OpenAI's beta structured output with Groq
                schema = structured_output_schema.model_json_schema()
                response = self.client.beta.chat.completions.parse(
                    model=self.model_name,
                    messages=messages,
                    response_format=structured_output_schema,
                    temperature=0,
                )
                parsed = response.choices[0].message.parsed
                raw_text = response.choices[0].message.content or ""
                return {"success": True, "data": parsed, "raw": raw_text}
            else:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=0,
                )
                raw_text = response.choices[0].message.content or ""
                return {"success": True, "data": raw_text, "raw": raw_text}

        except Exception as e:
            return {"success": False, "error": str(e), "raw": ""}

    def is_available(self) -> bool:
        return bool(self.api_key)

    def estimate_cost(self, prompt: str) -> float:
        # Groq free tier: 0.0, paid tier varies
        # Conservative placeholder: $0.0005 per 1K tokens (approximate)
        token_estimate = len(prompt) / 4
        return (token_estimate / 1000) * 0.0005