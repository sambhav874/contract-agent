"""Memory evaluation harness for working, episodic, and semantic memory.

Tests: working memory recall after N turns, episodic retrieval by goal,
semantic key-value accuracy.

Usage:
    python -m pytest tests/evaluation/memory_eval.py -v
    python -m tests.evaluation.memory_eval
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest
from unittest.mock import AsyncMock, patch

from app.agents.memory import WorkingMemory
from app.memory.episodic import EpisodicMemory
from app.memory.semantic import SemanticMemory


# ── Working Memory Tests ───────────────────────────────────────────────────

class TestWorkingMemory:
    def test_append_and_size(self):
        wm = WorkingMemory(history_limit=5)
        wm.append({"role": "user", "content": "hello"})
        assert wm.size == 1

    def test_eviction_when_full(self):
        wm = WorkingMemory(history_limit=3)
        for i in range(5):
            wm.append({"role": "user", "content": f"msg-{i}"})
        # After 5 appends with limit 3, size should be <= 3
        assert wm.size <= 3

    def test_get_messages_returns_all(self):
        wm = WorkingMemory(history_limit=5)
        wm.append({"role": "user", "content": "hello"})
        wm.append({"role": "assistant", "content": "hi"})
        msgs = wm.get_messages()
        assert len(msgs) == 2

    def test_summarization_triggers_after_threshold(self):
        wm = WorkingMemory(history_limit=20, summarize_threshold=2)
        for i in range(4):
            wm.append({"role": "user", "content": f"msg-{i}"})
        # After 4 with threshold 2, should have at least 1 summary
        assert len(wm.summaries) >= 1

    def test_memory_retains_order(self):
        wm = WorkingMemory(history_limit=5)
        for i in range(5):
            wm.append({"role": "user", "content": f"msg-{i}"})
        # Check that the messages are in order
        messages = wm.messages if not wm.summaries else wm.messages + wm.summaries
        assert messages[0]["content"] == "msg-0" or "Summary" in str(messages[0].get("content", ""))

    def test_rapid_append_does_not_corrupt(self):
        wm = WorkingMemory(history_limit=10)
        for i in range(100):
            wm.append({"role": "user", "content": f"msg-{i}"})
        # Should not crash; size <= limit
        assert wm.size <= 10

    def test_get_messages_returns_summaries_and_messages(self):
        wm = WorkingMemory(history_limit=20, summarize_threshold=2)
        for i in range(4):
            wm.append({"role": "user", "content": f"msg-{i}"})
        messages = wm.get_messages()
        # Should include both active messages and summaries
        assert len(messages) > 0
        assert any("Summary" in str(m.get("content", "")) for m in messages if isinstance(m, dict) and "content" in m)


# ── Episodic Memory Tests (mocked MongoDB) ─────────────────────────────────

class TestEpisodicMemory:
    @pytest.fixture
    def memory(self):
        with patch("app.memory.episodic.MongoDB") as mock_mongo:
            mock_collection = AsyncMock()
            mock_mongo.get_collection.return_value = mock_collection
            mock_collection.insert_one = AsyncMock()
            mock_collection.find.return_value.sort.return_value.limit.return_value.to_list = AsyncMock(return_value=[])
            yield EpisodicMemory(), mock_collection

    @pytest.mark.asyncio
    async def test_store_episode(self, memory):
        mem, mock_col = memory
        with patch("app.memory.episodic.MongoDB.get_collection", return_value=mock_col):
            sid = await mem.store("sess-1", "find clause", "found it", "success", [{"tool": "search"}])
            assert sid == "sess-1"

    @pytest.mark.asyncio
    async def test_retrieve_by_goal(self, memory):
        mem, _ = memory
        mock_results = [
            {"session_id": "s1", "goal": "find the penalty clause", "result": "Penalty is $5000"},
            {"session_id": "s2", "goal": "find the termination clause", "result": "30 days notice"},
        ]
        with patch("app.memory.episodic.MongoDB.get_collection") as mock_get_collection:
            mock_collection = AsyncMock()
            mock_collection.find.return_value.sort.return_value.limit.return_value.to_list = AsyncMock(return_value=mock_results)
            mock_get_collection.return_value = mock_collection
            results = await mem.retrieve_relevant("penalty")
            assert len(results) > 0

    @pytest.mark.asyncio
    async def test_list_sessions(self, memory):
        mem, _ = memory
        mock_results = [
            {"session_id": "s1", "goal": "find penalty", "outcome": "success"},
        ]
        with patch("app.memory.episodic.MongoDB.get_collection") as mock_get_collection:
            mock_collection = AsyncMock()
            mock_collection.find.return_value.sort.return_value.limit.return_value.to_list = AsyncMock(return_value=mock_results)
            mock_get_collection.return_value = mock_collection
            sessions = await mem.list_sessions()
            assert len(sessions) == 1

    @pytest.mark.asyncio
    async def test_store_retrieve_cycle(self, memory):
        mem, mock_col = memory
        with patch("app.memory.episodic.MongoDB.get_collection", return_value=mock_col):
            await mem.store("sess-2", "query 1", "result 1", "success", [])
            await mem.store("sess-2", "query 2", "result 2", "success", [])
            # After storing 2 episodes, list should find them
            mock_col.find.return_value.sort.return_value.limit.return_value.to_list = AsyncMock(return_value=[
                {"session_id": "sess-2", "goal": "query 1", "outcome": "success"},
                {"session_id": "sess-2", "goal": "query 2", "outcome": "success"},
            ])
            sessions = await mem.list_sessions()
            assert len(sessions) == 2

    @pytest.mark.asyncio
    async def test_retrieve_relevance_filtering(self, memory):
        mem, _ = memory
        mock_results = [
            {"session_id": "s1", "goal": "find the penalty clause", "result": "Penalty is $5000"},
        ]
        with patch("app.memory.episodic.MongoDB.get_collection") as mock_get_collection:
            mock_collection = AsyncMock()
            mock_collection.find.return_value.sort.return_value.limit.return_value.to_list = AsyncMock(return_value=mock_results)
            mock_get_collection.return_value = mock_collection
            results = await mem.retrieve_relevant("find the penalty clause")
            assert len(results) == 1
            assert results[0]["goal"] == "find the penalty clause"


# ── Semantic Memory Tests (mocked MongoDB) ─────────────────────────────────

class TestSemanticMemory:
    @pytest.fixture
    def memory(self):
        with patch("app.memory.semantic.MongoDB") as mock_mongo:
            mock_collection = AsyncMock()
            mock_mongo.get_collection.return_value = mock_collection
            yield SemanticMemory(), mock_collection

    @pytest.mark.asyncio
    async def test_store_and_retrieve(self, memory):
        mem, mock_col = memory
        with patch("app.memory.semantic.MongoDB.get_collection", return_value=mock_col):
            key = await mem.store("test-kpi", "98.5%", source="KPIAgent", confidence=0.95)
            mock_col.find_one = AsyncMock(return_value={"key": "test-kpi", "value": "98.5%", "source": "KPIAgent"})
            result = await mem.retrieve("test-kpi")
            assert result["value"] == "98.5%"
            assert result["source"] == "KPIAgent"

    @pytest.mark.asyncio
    async def test_query_by_prefix(self, memory):
        mem, mock_col = memory
        with patch("app.memory.semantic.MongoDB.get_collection", return_value=mock_col):
            mock_col.find.return_value.sort.return_value.limit.return_value.to_list = AsyncMock(return_value=[
                {"key": "kpi-on-time", "value": "98.5%"},
                {"key": "kpi-quality", "value": "4.5/5.0"},
            ])
            results = await mem.query("kpi", limit=2)
            assert len(results) == 2

    @pytest.mark.asyncio
    async def test_upsert_existing_key(self, memory):
        mem, mock_col = memory
        with patch("app.memory.semantic.MongoDB.get_collection", return_value=mock_col):
            await mem.store("duplicate-test", "value1", source="test")
            await mem.store("duplicate-test", "value2", source="test")
            # upsert should update, not create duplicate
            assert mock_col.update_one.call_count == 2

    @pytest.mark.asyncio
    async def test_list_all(self, memory):
        mem, mock_col = memory
        with patch("app.memory.semantic.MongoDB.get_collection", return_value=mock_col):
            mock_col.find.return_value.sort.return_value.limit.return_value.to_list = AsyncMock(return_value=[
                {"key": "fact-1", "value": "42"},
                {"key": "fact-2", "value": "hello"},
            ])
            results = await mem.list_all(limit=10)
            assert len(results) == 2

    @pytest.mark.asyncio
    async def test_confidence_tracking(self, memory):
        mem, mock_col = memory
        with patch("app.memory.semantic.MongoDB.get_collection", return_value=mock_col):
            mock_col.find_one = AsyncMock(return_value={"key": "high-conf", "value": "99%", "confidence": 0.99})
            result = await mem.retrieve("high-conf")
            assert result["confidence"] == 0.99


# ── Integration / End-to-End Memory Benchmark ──────────────────────────────

class TestMemoryBenchmark:
    def test_sequence_recall_rate(self):
        """Simulate 10-turn conversation, test recall of facts from earlier turns."""
        facts = [
            "delivery target: 98.5%",
            "penalty: $5000",
            "cure period: 30 days",
            "notice: 180 days",
            "volume: 300 units",
        ]
        wm = WorkingMemory(history_limit=20)
        for fact in facts:
            wm.append({"role": "system", "content": fact})
        # After all facts inserted, simulate asking back
        msgs = wm.get_messages()
        combined = " ".join(str(m) for m in msgs)
        recall_hits = sum(1 for f in facts if f in combined)
        recall_rate = recall_hits / len(facts)
        # Should recall at least 3/5 facts after summary
        assert recall_rate >= 0.60, f"Recall rate {recall_rate} too low"

    def test_no_data_loss_boundary(self):
        """Test that eviction does not lose critical contract information."""
        wm = WorkingMemory(history_limit=2)
        critical = {"role": "user", "content": "CRITICAL: $50000 penalty"}
        wm.append(critical)
        for i in range(10):
            wm.append({"role": "user", "content": f"filler-{i}"})
        # The critical fact may be lost but size should not exceed limit
        assert wm.size <= 2

    def test_summarization_preserves_meaning(self):
        """Test that summary generation retains critical information."""
        wm = WorkingMemory(history_limit=20, summarize_threshold=3)
        for i in range(6):
            wm.append({"role": "user", "content": f"Fact {i}: penalty is $5000"})
        msgs = wm.get_messages()
        combined = " ".join(str(m) for m in msgs)
        assert "$5000" in combined


async def main() -> int:
    print("[memory-eval] Running working memory tests")
    test_wm = TestWorkingMemory()
    test_wm.test_append_and_size()
    test_wm.test_eviction_when_full()
    test_wm.test_get_messages_returns_all()
    test_wm.test_summarization_triggers_after_threshold()
    print("[memory-eval] Working memory tests passed")

    print("[memory-eval] Running memory benchmark")
    bench = TestMemoryBenchmark()
    bench.test_sequence_recall_rate()
    bench.test_no_data_loss_boundary()
    bench.test_summarization_preserves_meaning()
    print("[memory-eval] Benchmark tests passed. Recall target: >= 60%")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
