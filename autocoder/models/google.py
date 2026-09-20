# autocoder/models/google.py
import os
from typing import Any, Optional, Type

# NOTE: google-generativeai is NOT currently a project dependency.
# Add it with: pip install google-generativeai
try:
    import google.generativeai as genai
except ImportError:
    genai = None

from autocoder.models.base import ModelProvider


class GoogleAIProvider(ModelProvider):
    provider_name = "google"

    def __init__(self, model_name: str = "gemini-1.5-flash"):
        self.model_name = model_name
        self.api_key = os.environ.get("GOOGLE_API_KEY")
        self._model = None
        
        if self.api_key and genai:
            try:
                genai.configure(api_key=self.api_key)
                self._model = genai.GenerativeModel(model_name)
            except Exception:
                self._model = None

    def invoke(self, prompt: str, structured_output_schema: Optional[Type[Any]] = None) -> dict:
        if not self.api_key:
            return {"success": False, "error": "GOOGLE_API_KEY not set", "raw": ""}
        if not genai:
            return {"success": False, "error": "google-generativeai package not installed", "raw": ""}
        if not self._model:
            return {"success": False, "error": "Failed to initialize Gemini model", "raw": ""}

        try:
            if structured_output_schema:
                # Use Gemini's structured output via response_schema
                schema = structured_output_schema.model_json_schema()
                response = self._model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        response_mime_type="application/json",
                        response_schema=schema,
                        temperature=0,
                    ),
                )
                raw_text = response.text or ""
                try:
                    parsed = structured_output_schema.model_validate_json(raw_text)
                    return {"success": True, "data": parsed, "raw": raw_text}
                except Exception as e:
                    return {"success": False, "error": f"Failed to parse structured output: {e}", "raw": raw_text}
            else:
                response = self._model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(temperature=0),
                )
                raw_text = response.text or ""
                return {"success": True, "data": raw_text, "raw": raw_text}

        except Exception as e:
            return {"success": False, "error": str(e), "raw": ""}

    def is_available(self) -> bool:
        # Only checks env var presence - no network call
        return bool(self.api_key and genai)

    def estimate_cost(self, prompt: str) -> float:
        # NOTE: Approximate placeholder rates for Gemini.
        # Free tier: 15 RPM, 1M tokens/day free. Paid: ~$0.075/1M input tokens (Flash).
        # This is a ROUGH ESTIMATE ONLY - check Google AI Studio pricing for actual rates.
        token_estimate = len(prompt) / 4
        return (token_estimate / 1_000_000) * 0.075