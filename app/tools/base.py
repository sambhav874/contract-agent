"""Base tool abstraction for agentic AI."""

from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel
import time


class ToolResult(BaseModel):
    success: bool
    data: Any = None
    error: str = ""
    metadata: dict = {}


class BaseTool(ABC):
    name: str
    description: str
    input_schema: dict

    @abstractmethod
    async def _execute(self, **kwargs) -> ToolResult:
        pass

    async def __call__(self, **kwargs) -> ToolResult:
        start = time.time()
        try:
            result = await self._execute(**kwargs)
        except Exception as e:
            result = ToolResult(success=False, error=str(e))
        finally:
            result.metadata["duration_ms"] = int((time.time() - start) * 1000)
            result.metadata["tool"] = self.name
        return result

    def to_anthropic_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }
