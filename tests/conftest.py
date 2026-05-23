"""Shared pytest fixtures and test utilities."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json
import sys
from types import ModuleType

# Stub google.genai before any code imports it
google_mod = ModuleType("google")
google_mod.__path__ = []
sys.modules["google"] = google_mod
genai_mod = ModuleType("google.genai")
genai_mod.__path__ = []
genai_mod.types = ModuleType("google.genai.types")
sys.modules["google.genai"] = genai_mod
sys.modules["google.genai.types"] = genai_mod.types

# ── Low-level types stubs ─────────────────────────────────────────────────────

class _MockSchema:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

class _MockPart:
    """Mirrors google.genai.types.Part for test purposes."""
    def __init__(self, text=None, function_call=None, function_response=None, **kwargs):
        self.text = text
        self.function_call = function_call
        self.function_response = function_response

class _MockContent:
    """Mirrors google.genai.types.Content for test purposes."""
    def __init__(self, role="user", parts=None, **kwargs):
        self.role = role
        self.parts = parts or []

class _MockFunctionResponse:
    """Mirrors google.genai.types.FunctionResponse for test purposes."""
    def __init__(self, name="", response=None, **kwargs):
        self.name = name
        self.response = response or {}

class _MockGenerateContentConfig:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

# Register all stubs on the fake types module
genai_mod.types.Schema = _MockSchema
genai_mod.types.Part = _MockPart
genai_mod.types.Content = _MockContent
genai_mod.types.FunctionResponse = _MockFunctionResponse
genai_mod.types.FunctionDeclaration = lambda **kwargs: MagicMock(**kwargs)
genai_mod.types.Tool = lambda **kwargs: MagicMock(**kwargs)
genai_mod.types.GenerateContentConfig = _MockGenerateContentConfig
genai_mod.types.HarmCategory = MagicMock()
genai_mod.types.HarmBlockThreshold = MagicMock()
genai_mod.__all__ = ["types"]


class MockGeminiChunk:
    def __init__(self, text=None, function_call=None):
        self.text = text
        self.function_call = function_call
        self.candidates = [
            MagicMock(content=MagicMock(parts=[MagicMock()] if text or function_call else []))
        ]
        if text:
            self.candidates[0].content.parts[0].text = text
            self.candidates[0].content.parts[0].function_call = None
        elif function_call:
            self.candidates[0].content.parts[0].function_call = function_call
            self.candidates[0].content.parts[0].text = None

    def __iter__(self):
        if self.text or self.function_call:
            return iter(self.candidates[0].content.parts)
        return iter([])


def mock_gemini_stream_factory(responses):
    """
    Factory to create a mock call_gemini_stream function.
    responses is a list of dicts: [{"text": "..."}, {"function_call": {...}}]
    """
    async def _mock_stream(*, model, system_prompt, user_message, tools=None):
        chunks = []
        for resp in responses:
            if "text" in resp:
                chunks.append(MagicMock(
                    candidates=[MagicMock(content=MagicMock(parts=[
                        MagicMock(text=resp["text"], function_call=None)
                    ]))]
                ))
            elif "function_call" in resp:
                fc = MagicMock()
                fc.name = resp["function_call"]["name"]
                fc.args = resp["function_call"]["args"]
                chunks.append(MagicMock(
                    candidates=[MagicMock(content=MagicMock(parts=[
                        MagicMock(text=None, function_call=fc)
                    ]))]
                ))
        return chunks
    return _mock_stream


def mock_gemini_factory(response):
    """Factory for sync mock call_gemini."""
    async def _mock(*, model, system_prompt, user_message, temperature=0):
        return response
    return _mock
