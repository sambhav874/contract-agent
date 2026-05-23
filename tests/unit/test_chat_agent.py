"""Comprehensive tests for ChatAgent."""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from unittest.mock import AsyncMock as _AsyncMock

from app.agents.chat_agent import ChatAgent, classify_intent, Intent
from app.agents.safety import SafetyGuard


class TestClassifyIntent:
    @pytest.mark.asyncio
    async def test_classify_intent_fallback(self):
        with patch("app.agents.chat_agent.call_gemini", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = Exception("error")
            res = await classify_intent("What is the penalty clause?", [])
            assert res["intent"] == Intent.GENERAL_QUERY


class TestChatAgent:

    @pytest.fixture
    def mock_safety_config(self):
        return {"max_cost_usd": 1.0, "max_iterations": 3}

    @pytest.fixture
    def chat_agent(self, mock_safety_config):
        with patch("app.agents.chat_agent.get_retriever") as mock_retriever:
            mock_r = MagicMock()
            mock_r.fetch = AsyncMock(return_value=[])
            mock_retriever.return_value = mock_r
            agent = ChatAgent("test-contract-1", safety_config=mock_safety_config)
            return agent

    @pytest.mark.asyncio
    async def test_agent_init(self, chat_agent):
        assert chat_agent.contract_id == "test-contract-1"
        assert chat_agent.safety.max_cost_usd == 1.0
        assert chat_agent.safety.max_iterations == 3
        assert chat_agent.memory.size == 0

    @pytest.mark.asyncio
    async def test_build_system_prompt(self, chat_agent):
        ctx = {
            "name": "Test Contract",
            "type": "service",
            "parties": [{"name": "Acme", "role": "supplier"}],
            "effective_date": "2024-01-01",
            "governing_law": "US",
            "jurisdiction": "Delaware",
            "currency": "USD",
            "summary": "A test contract.",
        }
        prompt = chat_agent._build_system_prompt(Intent.CONVERSATIONAL, ctx, include_contract_context=True)
        assert "Test Contract" in prompt
        assert "Acme" in prompt
        assert "CONTRACT CONTEXT" in prompt

    @pytest.mark.asyncio
    async def test_tool_registry_build(self, chat_agent):
        schemas = chat_agent.tool_registry.get_schemas()
        names = [s["name"] for s in schemas]
        assert "search_contract_clauses" in names
        assert "query_contract_database" in names
        assert "get_kpi_registry" in names
        assert "summarize_contract" in names
        assert "search_contract_answers" in names
        assert len(schemas) >= 5

    @pytest.mark.asyncio
    async def test_safety_guard_triggers(self, chat_agent):
        # Override with very low limit
        chat_agent.safety.max_cost_usd = 0.001
        chat_agent.safety.cost_tracker = 0.01  # exceed the limit
        halt, reason = chat_agent.safety.should_halt([], 1)
        assert halt is True
        assert "Cost cap" in reason

    @pytest.mark.asyncio
    async def test_safety_guard_allows(self, chat_agent):
        halt, reason = chat_agent.safety.should_halt([], 1)
        assert halt is False

    @pytest.mark.asyncio
    async def test_working_memory(self, chat_agent):
        chat_agent.memory.append({"role": "user", "content": "hello"})
        chat_agent.memory.append({"role": "assistant", "content": "hi"})
        assert chat_agent.memory.size == 2

    @pytest.mark.asyncio
    async def test_memory_eviction(self, chat_agent):
        # Fill memory beyond limit
        for i in range(10):
            chat_agent.memory.append({"role": "user", "content": f"msg-{i}"})
        assert chat_agent.memory.size <= 5

    @pytest.mark.asyncio
    async def test_planner_decompose_simple(self, chat_agent):
        with patch("app.agents.planner.call_gemini") as mock_llm:
            mock_llm.return_value = {
                "steps": [
                    {"step_id": "1", "description": "Find penalties clause", "tools_needed": [], "depends_on": [], "success_criteria": "Found", "fallback": "Search"}
                ]
            }
            result = await chat_agent.planner.decompose("What are the penalties?")
            assert len(result) > 0
            assert "penalties" in result[0]["description"].lower()

    @pytest.mark.asyncio
    async def test_answer_question_stream_introspection(self, chat_agent):
        """Test that introspection shortcut works."""
        with patch("app.db.mongodb.MongoDB.get_contract", new_callable=AsyncMock) as mock_get_contract:
            mock_get_contract.return_value = {}
            chunks = []
            async for chunk in chat_agent.answer_question_stream("What can you do?"):
                chunks.append(chunk)
            assert any(c["type"] == "done" for c in chunks)

    @pytest.mark.asyncio
    async def test_hallucination_guard(self):
        from app.agents.chat_agent import _hallucination_guard
        # CONVERSATIONAL mode should always pass
        assert _hallucination_guard("some text", Intent.CONVERSATIONAL) is True
