"""Tests for ToolRegistry and BaseTool."""

import pytest
from unittest.mock import AsyncMock, MagicMock
import asyncio

from app.tools.base import BaseTool, ToolResult
from app.tools.registry import ToolRegistry


class FakeTool(BaseTool):
    name = "fake_tool"
    description = "A fake tool"
    input_schema = {"type": "object", "properties": {}, "required": []}

    def __init__(self):
        pass

    async def _execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, data={"executed": True})


class TestToolRegistry:
    def test_register_and_get_schemas(self):
        registry = ToolRegistry()
        assert registry.get_schemas() == []

        fake = FakeTool()
        registry.register(fake)
        schemas = registry.get_schemas()
        assert len(schemas) == 1
        assert schemas[0]["name"] == "fake_tool"

    def test_to_gemini_tools(self):
        registry = ToolRegistry()
        registry.register(FakeTool())
        tools = registry.to_gemini_tools()
        assert len(tools) == 1

    def test_execute_tool_not_found(self):
        registry = ToolRegistry()
        result = asyncio.run(registry.execute("nonexistent"))
        assert not result.success
        assert "not found" in result.error

    def test_execute_tool_found(self):
        registry = ToolRegistry()
        registry.register(FakeTool())
        result = asyncio.run(registry.execute("fake_tool"))
        assert result.success

    def test_tool_result_metadata(self):
        result = ToolResult(success=True, data={"key": "value"})
        assert result.success
        assert result.data == {"key": "value"}
        assert result.error == ""

    def test_base_tool_call_tracks_duration(self):
        import time
        tool = FakeTool()
        result = asyncio.run(tool(test="value"))
        assert result.metadata["duration_ms"] >= 0
        assert result.metadata["tool"] == "fake_tool"
