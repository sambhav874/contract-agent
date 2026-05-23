"""Tool registry for discovering and executing tools."""

from typing import Any
from google.genai import types
from app.tools.base import BaseTool, ToolResult


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    async def execute(self, name: str, **kwargs) -> ToolResult:
        if name not in self._tools:
            return ToolResult(success=False, error=f"Tool {name} not found")
        return await self._tools[name](**kwargs)

    def get_schemas(self) -> list[dict]:
        return [t.to_anthropic_schema() for t in self._tools.values()]

    def to_gemini_tools(self) -> list[types.Tool]:
        decls = []
        for tool in self._tools.values():
            decls.append(
                types.FunctionDeclaration(
                    name=tool.name,
                    description=tool.description,
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            k: types.Schema(type=v.get("type", "STRING"), description=v.get("description", ""))
                            for k, v in (tool.input_schema.get("properties", {}) or {}).items()
                        },
                        required=tool.input_schema.get("required", []),
                    ),
                )
            )
        return [types.Tool(function_declarations=decls)]
