"""Tests for WorkingMemory, EpisodicMemory, and SemanticMemory."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.memory import WorkingMemory


class TestWorkingMemory:
    def test_append_and_get_messages(self):
        mem = WorkingMemory(history_limit=5)
        mem.append({"role": "user", "content": "hello"})
        mem.append({"role": "assistant", "content": "hi"})
        assert len(mem.get_messages()) == 2

    def test_summarization(self):
        mem = WorkingMemory(history_limit=5, summarize_threshold=2)
        for i in range(5):
            mem.append({"role": "user", "content": f"msg{i}"})
        assert len(mem.summaries) > 0

    def test_eviction(self):
        mem = WorkingMemory(history_limit=3)
        for i in range(10):
            mem.append({"role": "user", "content": f"msg{i}"})
        assert mem.size <= 3

    def test_size_property(self):
        mem = WorkingMemory()
        assert mem.size == 0
        mem.append({"role": "user", "content": "test"})
        assert mem.size == 1


class TestEpisodicMemory:
    @pytest.mark.asyncio
    async def test_store_and_retrieve(self):
        from app.memory.episodic import EpisodicMemory
        mem = EpisodicMemory()

        # Mock the collection
        mock_collection = AsyncMock()
        mock_collection.insert_one = AsyncMock()
        mock_collection.find = AsyncMock(return_value=mock_collection)
        mock_collection.sort.return_value = mock_collection
        mock_collection.limit.return_value = mock_collection
        mock_collection.to_list.return_value = []

        with patch("app.memory.episodic.MongoDB.get_collection", return_value=mock_collection):
            sid = await mem.store(
                session_id="test-123",
                goal="analyze contract",
                result="found 5 risks",
                outcome="success",
                trace=[{"event": "started"}, {"event": "done"}],
            )
            assert sid == "test-123"
            mock_collection.insert_one.assert_awaited_once()


class TestSemanticMemory:
    @pytest.mark.asyncio
    async def test_store_and_retrieve(self):
        from app.memory.semantic import SemanticMemory
        mem = SemanticMemory()

        mock_collection = AsyncMock()
        mock_collection.update_one = AsyncMock()
        mock_collection.find_one = AsyncMock(return_value={"key": "party_concessionaire", "value": "xyz corp"})

        with patch("app.memory.semantic.MongoDB.get_collection", return_value=mock_collection):
            key = await mem.store(key="party_concessionaire", value="xyz corp", confidence=0.95)
            assert key == "party_concessionaire"
            mock_collection.update_one.assert_awaited()

    @pytest.mark.asyncio
    async def test_retrieve_nonexistent(self):
        from app.memory.semantic import SemanticMemory
        mem = SemanticMemory()

        mock_collection = AsyncMock()
        mock_collection.find_one = AsyncMock(return_value=None)

        with patch("app.memory.semantic.MongoDB.get_collection", return_value=mock_collection):
            result = await mem.retrieve("nonexistent_key_xyz")
            assert result is None
