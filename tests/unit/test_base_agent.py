import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.agents.base_agent import BaseAgent

from pydantic import BaseModel

class DummyOutput(BaseModel):
    fixed: bool

class DummyAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.output_schema = DummyOutput
        self.prompt_file = "dummy.md"

    async def analyze(self, *args, **kwargs):
        pass

@pytest.mark.asyncio
async def test_base_agent_load_prompt():
    with patch("builtins.open", new_callable=MagicMock) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = "System Prompt"
        agent = DummyAgent()
        prompt = agent.load_prompt()
        assert "System" in prompt

@pytest.mark.asyncio
async def test_base_agent_self_correct():
    with patch("app.agents.base_agent.call_gemini", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.return_value = '{"fixed": true}'
        agent = DummyAgent()
        from pydantic import ValidationError
        # Create a mock ValidationError
        class MockError:
            def __str__(self): return "error"
        result = await agent._self_correct({"bad": "data"}, MockError(), [])
        assert result is not None
