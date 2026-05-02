"""Gemini API client wrapper with retry logic."""

import asyncio
import time
from typing import Any

import httpx
from pydantic import BaseModel

from app.config import settings


class GeminiClient:
    """Gemini API client with retry logic and logging."""

    def __init__(self):
        self.api_key = settings.gemini_api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.max_retries = 3
        self.base_delay = 1.0

    async def call(
        self,
        model: str,
        system_prompt: str,
        user_message: str,
        response_schema: dict[str, Any] | None = None,
        temperature: float = 0.0,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """
        Call Gemini API with retry logic.

        Args:
            model: Model name (e.g., gemini-1.5-pro)
            system_prompt: System instruction
            user_message: User message
            response_schema: Optional JSON schema for structured output
            temperature: Temperature for generation
            max_retries: Maximum retry attempts

        Returns:
            Parsed response dict
        """
        start_time = time.time()

        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=300.0) as client:
                    payload = self._build_payload(
                        system_prompt=system_prompt,
                        user_message=user_message,
                        response_schema=response_schema,
                        temperature=temperature,
                    )

                    response = await client.post(
                        f"{self.base_url}/models/{model}:generateContent",
                        params={"key": self.api_key},
                        json=payload,
                    )

                    latency_ms = int((time.time() - start_time) * 1000)

                    # Log the call
                    self._log_call(
                        model=model,
                        temperature=temperature,
                        latency_ms=latency_ms,
                        status_code=response.status_code,
                    )

                    response.raise_for_status()
                    result = response.json()

                    # Parse response
                    return self._parse_response(result)

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:  # Rate limit
                    if attempt < max_retries:
                        delay = self.base_delay * (2 ** attempt)
                        await asyncio.sleep(delay)
                        continue
                print(f"DEBUG HTTP Error: {e.response.status_code} - {e.response.text}")
                raise

        raise RuntimeError(f"Failed after {max_retries} retries")

    def _build_payload(
        self,
        system_prompt: str,
        user_message: str,
        response_schema: dict[str, Any] | None,
        temperature: float,
    ) -> dict[str, Any]:
        """Build API request payload."""
        payload: dict[str, Any] = {
            "contents": [{
                "parts": [{
                    "text": f"{system_prompt}\n\n{user_message}"
                }]
            }],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 8192,
            },
        }

        if response_schema:
            payload["generationConfig"]["responseMimeType"] = "application/json"
            payload["generationConfig"]["responseSchema"] = self._clean_schema_for_gemini(response_schema)

        return payload

    def _parse_response(self, result: dict[str, Any]) -> dict[str, Any]:
        """Parse API response."""
        try:
            candidates = result.get("candidates", [])
            if not candidates:
                raise ValueError("No candidates in response")

            content = candidates[0].get("content", {})
            parts = content.get("parts", [])

            if not parts:
                raise ValueError("No parts in content")

            text = parts[0].get("text", "")

            print("DEBUG: Gemini response text:", repr(text))

            text = text.strip()
            if text.startswith("```json"):
                text = text[7:]
            elif text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            import json
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                # If we didn't ask for JSON, return as text
                return {"text": text}

        except Exception as e:
            if "text" in locals():
                with open("failed_gemini_response.txt", "w") as f:
                    f.write(text)
            raise ValueError(f"Failed to parse response: {e}. Raw response saved to failed_gemini_response.txt")

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

    def _clean_schema_for_gemini(self, schema: dict[str, Any], defs: dict[str, Any] | None = None) -> dict[str, Any]:
        """Clean a JSON schema to be compatible with Gemini REST API responseSchema."""
        if defs is None:
            defs = schema.get("$defs", {})
            
        cleaned: dict[str, Any] = {}
        
        allowed_keys = {
            "type", "format", "description", "nullable", "enum",
            "maxItems", "minItems", "properties", "required", "items"
        }
        
        for k, v in schema.items():
            if k == "$ref" and isinstance(v, str):
                ref_name = v.split("/")[-1]
                if ref_name in defs:
                    resolved = self._clean_schema_for_gemini(defs[ref_name], defs)
                    for rk, rv in resolved.items():
                        cleaned[rk] = rv
                continue
                
            if k not in allowed_keys:
                continue
                
            if isinstance(v, dict):
                if k == "properties":
                    cleaned[k] = {pk: self._clean_schema_for_gemini(pv, defs) for pk, pv in v.items()}
                elif k == "items":
                    cleaned[k] = self._clean_schema_for_gemini(v, defs)
                else:
                    cleaned[k] = self._clean_schema_for_gemini(v, defs)
            elif isinstance(v, list) and k == "items":
                cleaned[k] = [self._clean_schema_for_gemini(item, defs) for item in v]
            else:
                cleaned[k] = v
                
        if "type" in cleaned and isinstance(cleaned["type"], str):
            cleaned["type"] = cleaned["type"].upper()
            
        return cleaned


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
