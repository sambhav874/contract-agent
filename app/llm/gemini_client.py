"""Gemini API client using official google-genai SDK."""

import json
import time
import asyncio
from typing import Any

from google import genai
from google.genai import types

from app.config import settings


class GeminiClient:
    """Client for interacting with Google Gemini API via official SDK."""

    def __init__(self):
        # Use the new SDK's client
        self.client = genai.Client(api_key=settings.gemini_api_key)

    async def call(
        self,
        model: str,
        system_prompt: str,
        user_message: str,
        response_schema: dict[str, Any] | None = None,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        """
        Call Gemini model and return structured response.
        
        Uses response_json_schema for robust JSON extraction as suggested by user.
        """
        start_time = time.time()
        
        # Configure the generation
        config = {
            "temperature": temperature,
            "system_instruction": system_prompt,
        }
        
        if response_schema:
            config["response_mime_type"] = "application/json"
            # Note: the new SDK handles the translation from standard JSON schema 
            # to Gemini's internal format, so we can pass the raw schema.
            config["response_json_schema"] = response_schema

        try:
            # The SDK is primarily synchronous for generate_content currently in the stable version,
            # so we run it in a thread to avoid blocking the event loop.
            # (Note: google-genai 0.x/1.x is evolving, so we use a safe async wrapper)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.models.generate_content(
                    model=model,
                    contents=user_message,
                    config=config,
                )
            )
            
            latency_ms = int((time.time() - start_time) * 1000)
            self._log_call(model, temperature, latency_ms, 200)

            return self._parse_response(response)

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            self._log_call(model, temperature, latency_ms, 500)
            raise ValueError(f"Gemini API call failed: {e}")

    def _parse_response(self, response: Any) -> dict[str, Any]:
        """Parse SDK response."""
        try:
            # The SDK response has a .text attribute for the combined response parts
            text = response.text
            
            print("DEBUG: Gemini response text:", repr(text))
            
            text = text.strip()
            
            # Use json.loads directly as response_mime_type="application/json" 
            # should prevent the model from wrapping in Markdown blocks.
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                # If it still has markdown blocks for some reason, clean them
                if text.startswith("```json"):
                    text = text[7:]
                elif text.startswith("```"):
                    text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"text": text}

        except Exception as e:
            raise ValueError(f"Failed to parse SDK response: {e}")

    def _log_call(
        self,
        model: str,
        temperature: float,
        latency_ms: int,
        status_code: int,
    ) -> None:
        """Log API call metadata."""
        # In production, this would log to a monitoring system
        pass


# Global client instance
_gemini_client: GeminiClient | None = None


def get_gemini_client() -> GeminiClient:
    """Get or create the Gemini client."""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiClient()
    return _gemini_client


async def call_gemini(
    model: str,
    system_prompt: str,
    user_message: str,
    response_schema: dict[str, Any] | None = None,
    temperature: float = 0.0,
) -> dict[str, Any]:
    """Convenience function to call Gemini API."""
    client = get_gemini_client()
    return await client.call(
        model=model,
        system_prompt=system_prompt,
        user_message=user_message,
        response_schema=response_schema,
        temperature=temperature,
    )


async def call_gemini_structured(
    prompt: str,
    output_schema: Any,
    model: str = "gemini-2.0-flash",
    temperature: float = 0.0,
) -> Any:
    """Call Gemini and parse response into a Pydantic model."""
    # Use Pydantic's model_json_schema() to generate the schema for the model
    schema = output_schema.model_json_schema()
    
    # We pass the schema directly to the SDK
    result = await call_gemini(
        model=model,
        system_prompt="Return the response in strict JSON format matching the provided schema.",
        user_message=prompt,
        response_schema=schema,
        temperature=temperature,
    )
    
    return output_schema.model_validate(result)
