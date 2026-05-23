"""Episodic memory — stores past agent runs with embedding-based retrieval."""

import time
import uuid
from typing import Any
from app.db.mongodb import MongoDB


class EpisodicMemory:
    """Stores past agent runs and retrieves them via semantic search on goal."""

    def __init__(self):
        self.collection_name = "episodic_memory"

    async def store(
        self,
        session_id: str,
        goal: str,
        result: str,
        outcome: str,
        trace: list[dict[str, Any]],
    ) -> str:
        """Store an episode."""
        doc = {
            "session_id": session_id,
            "goal": goal,
            "result": result,
            "outcome": outcome,
            "trace": trace,
            "timestamp": time.time(),
        }
        collection = MongoDB.get_collection(self.collection_name)
        await collection.insert_one(doc)
        return doc["session_id"]

    async def retrieve_relevant(self, goal: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Retrieve past episodes whose goals are semantically similar."""
        collection = MongoDB.get_collection(self.collection_name)
        # For now use simple text-based matching; in production use embeddings
        cursor = collection.find({
            "goal": { "$regex": goal[:50], "$options": "i" }
        }).sort("timestamp", -1).limit(top_k)
        results = await cursor.to_list(length=top_k)
        return results

    async def list_sessions(self, limit: int = 20) -> list[dict[str, Any]]:
        """List recent session summaries."""
        collection = MongoDB.get_collection(self.collection_name)
        cursor = collection.find({}, {"goal": 1, "outcome": 1, "timestamp": 1}).sort("timestamp", -1).limit(limit)
        return await cursor.to_list(length=limit)
