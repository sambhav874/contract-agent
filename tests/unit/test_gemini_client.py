"""Unit tests for GeminiClient and module-level convenience functions."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.llm.gemini_client import (
    GeminiClient,
    call_gemini,
    call_gemini_stream,
    call_gemini_structured,
    get_gemini_client,
)


# ── _parse_response ───────────────────────────────────────────────────

class TestParseResponse:
    def setup_method(self):
        with patch("app.llm.gemini_client.genai"):
            self.client = GeminiClient.__new__(GeminiClient)

    def _mock_response(self, text: str):
        r = MagicMock()
        r.text = text
        return r

    def test_valid_json(self):
        r = self._mock_response('{"key": "value"}')
        result = self.client._parse_response(r)
        assert result == {"key": "value"}

    def test_json_in_markdown_block(self):
        r = self._mock_response('```json\n{"k": 1}\n```')
        result = self.client._parse_response(r)
        assert result == {"k": 1}

    def test_json_in_plain_code_block(self):
        r = self._mock_response('```\n{"k": 2}\n```')
        result = self.client._parse_response(r)
        assert result == {"k": 2}

    def test_fallback_on_bad_json(self):
        r = self._mock_response("not json at all")
        result = self.client._parse_response(r)
        assert "text" in result
        assert result["text"] == "not json at all"

    def test_whitespace_stripped(self):
        r = self._mock_response('  {"x": 99}  ')
        result = self.client._parse_response(r)
        assert result == {"x": 99}


# ── call_gemini convenience function ─────────────────────────────────

class TestCallGemini:
    @pytest.mark.asyncio
    async def test_returns_parsed_dict(self):
        mock_response = MagicMock()
        mock_response.text = '{"intent": "risk"}'

        mock_aio = AsyncMock()
        mock_aio.models.generate_content = AsyncMock(return_value=mock_response)

        with patch("app.llm.gemini_client.genai") as mock_genai:
            mock_genai.Client.return_value = MagicMock(aio=mock_aio)
            client = GeminiClient()
            client.client.aio = mock_aio

            result = await client.call(
                model="gemini-test",
                system_prompt="You are a test agent.",
                user_message="What is the risk?",
            )
        assert result == {"intent": "risk"}

    @pytest.mark.asyncio
    async def test_raises_on_api_error(self):
        mock_aio = AsyncMock()
        mock_aio.models.generate_content = AsyncMock(side_effect=RuntimeError("API down"))

        with patch("app.llm.gemini_client.genai") as mock_genai:
            mock_genai.Client.return_value = MagicMock(aio=mock_aio)
            client = GeminiClient()
            client.client.aio = mock_aio

            with pytest.raises(ValueError, match="Gemini API call failed"):
                await client.call(
                    model="gemini-test",
                    system_prompt="sys",
                    user_message="msg",
                )


# ── call_gemini_stream ────────────────────────────────────────────────

class TestCallGeminiStream:
    @pytest.mark.asyncio
    async def test_streams_chunks(self):
        chunk1 = MagicMock()
        chunk1.candidates = [MagicMock(content=MagicMock(parts=[MagicMock(text="hello", function_call=None)]))]
        chunk2 = MagicMock()
        chunk2.candidates = [MagicMock(content=MagicMock(parts=[MagicMock(text=" world", function_call=None)]))]

        async def fake_stream(*args, **kwargs):
            async def gen():
                yield chunk1
                yield chunk2
            return gen()

        # generate_content_stream returns a coroutine that resolves to an async generator
        mock_aio = MagicMock()
        mock_aio.models.generate_content_stream = fake_stream

        with patch("app.llm.gemini_client.genai") as mock_genai:
            mock_genai.Client.return_value = MagicMock(aio=mock_aio)
            client = GeminiClient()
            client.client = MagicMock(aio=mock_aio)

            chunks = []
            async for c in client.call_stream(
                model="gemini-test",
                system_prompt="sys",
                user_message="msg",
            ):
                chunks.append(c)

        assert len(chunks) == 2


# ── call_gemini_structured ────────────────────────────────────────────

class TestCallGeminiStructured:
    @pytest.mark.asyncio
    async def test_calls_with_correct_model(self):
        from pydantic import BaseModel
        from app.config import settings

        class MyOutput(BaseModel):
            result: str

        with patch("app.llm.gemini_client.call_gemini", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"result": "yes"}

            result = await call_gemini_structured(
                prompt="Test prompt",
                output_schema=MyOutput,
            )

        # Should use settings.gemini_fast_model (not any OTHER hardcoded name)
        call_args = mock_call.call_args
        assert call_args.kwargs["model"] == settings.gemini_fast_model
        assert result.result == "yes"

    @pytest.mark.asyncio
    async def test_accepts_explicit_model(self):
        from pydantic import BaseModel

        class MyOutput(BaseModel):
            value: int = 0

        with patch("app.llm.gemini_client.call_gemini", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"value": 42}

            result = await call_gemini_structured(
                prompt="Test",
                output_schema=MyOutput,
                model="gemini-explicit-model",
            )

        call_args = mock_call.call_args
        assert call_args.kwargs["model"] == "gemini-explicit-model"
        assert result.value == 42
