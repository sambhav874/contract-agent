"""Gemini API client using official google-genai SDK.

Thinking support:
    When enable_thinking=True, the config includes
    types.ThinkingConfig(include_thoughts=True) so Gemini 2.5+/3
    models stream thought-summary parts alongside answer parts.
    Callers detect thought parts via `part.thought == True`.
"""

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
        tools: list[Any] | None = None,
        temperature: float = 0.0,
        enable_thinking: bool = False,
    ) -> Any:
        """
        Call Gemini model and return structured response.

        Uses response_json_schema for robust JSON extraction as suggested by user.
        When enable_thinking=True, includes ThinkingConfig so the model returns
        thought-summary parts alongside the answer.
        """
        start_time = time.time()

        # Configure the generation
        config: dict[str, Any] = {
            "temperature": temperature,
            "system_instruction": system_prompt,
        }
        if tools:
            config["tools"] = tools

        if response_schema:
            config["response_mime_type"] = "application/json"
            # Note: the new SDK handles the translation from standard JSON schema
            # to Gemini's internal format, so we can pass the raw schema.
            config["response_json_schema"] = response_schema

        # Enable native Gemini thinking (thought summaries)
        if enable_thinking:
            config["thinking_config"] = types.ThinkingConfig(
                include_thoughts=True,
            )

        try:
            response = await self.client.aio.models.generate_content(
                model=model,
                contents=user_message,
                config=config,
            )

            latency_ms = int((time.time() - start_time) * 1000)
            self._log_call(model, temperature, latency_ms, 200)

            return self._parse_response(response, include_thoughts=enable_thinking)

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            self._log_call(model, temperature, latency_ms, 500)
            raise ValueError(f"Gemini API call failed: {e}")

    async def call_stream(
        self,
        model: str,
        system_prompt: str,
        user_message: str,
        tools: list[Any] | None = None,
        temperature: float = 0.0,
        enable_thinking: bool = False,
    ):
        """
        Call Gemini model with streaming enabled.

        When enable_thinking=True, streamed chunks may contain parts with
        part.thought=True (rolling thought summaries). Callers should check
        `part.thought` to separate reasoning from answer content.
        """
        config: dict[str, Any] = {
            "temperature": temperature,
            "system_instruction": system_prompt,
        }
        if tools:
            config["tools"] = tools

        # Enable native Gemini thinking (streamed thought summaries)
        if enable_thinking:
            config["thinking_config"] = types.ThinkingConfig(
                include_thoughts=True,
            )

        stream = await self.client.aio.models.generate_content_stream(
            model=model,
            contents=user_message,
            config=config,
        )
        async for chunk in stream:
            yield chunk

    def _parse_response(
        self, response: Any, include_thoughts: bool = False
    ) -> dict[str, Any]:
        """Parse SDK response, optionally extracting thought summaries."""
        try:
            # When thinking is enabled, iterate parts to separate thoughts from answer
            thought_text = ""
            answer_text = ""

            if include_thoughts and hasattr(response, "candidates") and response.candidates:
                for part in response.candidates[0].content.parts:
                    if not getattr(part, "text", None):
                        continue
                    if getattr(part, "thought", False):
                        thought_text += part.text
                    else:
                        answer_text += part.text
            else:
                # Fallback: use .text attribute
                answer_text = response.text or ""

            answer_text = answer_text.strip()

            # Use json.loads directly as response_mime_type="application/json"
            # should prevent the model from wrapping in Markdown blocks.
            try:
                result = json.loads(answer_text)
            except json.JSONDecodeError:
                # If it still has markdown blocks for some reason, clean them
                cleaned = answer_text
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                elif cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()
                try:
                    result = json.loads(cleaned)
                except json.JSONDecodeError:
                    result = {"text": answer_text}

            # Attach thought summary if present
            if thought_text:
                result["_thought_summary"] = thought_text.strip()

            return result

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
    tools: list[Any] | None = None,
    temperature: float = 0.0,
    enable_thinking: bool = False,
) -> Any:
    """Convenience function to call Gemini API."""
    client = get_gemini_client()
    return await client.call(
        model=model,
        system_prompt=system_prompt,
        user_message=user_message,
        response_schema=response_schema,
        tools=tools,
        temperature=temperature,
        enable_thinking=enable_thinking,
    )


async def call_gemini_stream(
    model: str,
    system_prompt: str,
    user_message: str,
    tools: list[Any] | None = None,
    temperature: float = 0.0,
    enable_thinking: bool = False,
):
    """Convenience function to call Gemini API with streaming."""
    client = get_gemini_client()
    async for chunk in client.call_stream(
        model=model,
        system_prompt=system_prompt,
        user_message=user_message,
        tools=tools,
        temperature=temperature,
        enable_thinking=enable_thinking,
    ):
        yield chunk


async def call_gemini_structured(
    prompt: str,
    output_schema: Any,
    model: str | None = None,
    temperature: float = 0.0,
    enable_thinking: bool = False,
) -> Any:
    """Call Gemini and parse response into a Pydantic model."""
    if model is None:
        model = settings.gemini_fast_model

    # Use Pydantic's model_json_schema() to generate the schema for the model
    schema = output_schema.model_json_schema()

    # We pass the schema directly to the SDK
    result = await call_gemini(
        model=model,
        system_prompt="Return the response in strict JSON format matching the provided schema.",
        user_message=prompt,
        response_schema=schema,
        temperature=temperature,
        enable_thinking=enable_thinking,
    )

    return output_schema.model_validate(result)
