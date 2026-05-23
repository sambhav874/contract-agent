import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.agents.chat_agent import ChatAgent

@pytest.fixture
def chat_agent():
    return ChatAgent(contract_id="test-contract")

@pytest.mark.asyncio
async def test_chat_agent_process(chat_agent):
    with patch("app.agents.chat_agent.MongoDB") as mock_mongo:
        mock_mongo.get_contract = AsyncMock(return_value={"name": "test", "contract_type": "MSA"})
        mock_mongo.get_kpis = AsyncMock(return_value=[])
        mock_mongo.get_breaches = AsyncMock(return_value=[])
        mock_mongo.get_all_actuals = AsyncMock(return_value=[])

        with patch.object(chat_agent.retriever, "fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [{"text": "summary chunk"}]

            with patch("app.agents.chat_agent.SemanticMemory") as mock_memory:
                with patch.object(chat_agent.planner, "maybe_replan", new_callable=AsyncMock) as mock_plan:
                    mock_plan.return_value = ([], "No replanning")

                    with patch("app.agents.chat_agent.call_gemini_stream") as mock_gemini:
                        async def mock_stream(*args, **kwargs):
                            yield MagicMock(candidates=[MagicMock(content=MagicMock(parts=[MagicMock(text="<thought>Test thought</thought> Test answer", function_call=None)]))])

                        mock_gemini.side_effect = mock_stream

                        chunks = []
                        async for chunk in chat_agent.answer_question_stream("test query", session_id="session-1"):
                            chunks.append(chunk)

                        assert len(chunks) > 0

                        # verify history was saved
                        from app.agents.chat_agent import get_session_history
                        history = await get_session_history("session-1")
                        assert len(history) > 0

@pytest.mark.asyncio
async def test_chat_agent_process_no_plan(chat_agent):
    with patch("app.agents.chat_agent.MongoDB") as mock_mongo:
        mock_mongo.get_contract = AsyncMock(return_value={"name": "test", "contract_type": "MSA"})
        mock_mongo.get_kpis = AsyncMock(return_value=[])
        mock_mongo.get_breaches = AsyncMock(return_value=[])
        mock_mongo.get_all_actuals = AsyncMock(return_value=[])

        with patch.object(chat_agent.retriever, "fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [{"text": "summary chunk"}]

            with patch("app.agents.chat_agent.call_gemini_stream") as mock_gemini:
                async def mock_stream(*args, **kwargs):
                    yield MagicMock(candidates=[MagicMock(content=MagicMock(parts=[MagicMock(text="Direct answer", function_call=None)]))])

                mock_gemini.side_effect = mock_stream

                chunks = []
                async for chunk in chat_agent.answer_question_stream("test query"):
                    chunks.append(chunk)

                assert len(chunks) > 0
                assert any(c.get("content") == "Direct answer" for c in chunks if c.get("type") == "content")
